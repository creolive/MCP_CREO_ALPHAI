# FEAT-007：任务长轮询（`creo_get_job wait_seconds`）

类型：功能

优先级：P2

状态：验收中（离线实现完成；实机、MCP stdio 客户端与真实取消未验证）

目标版本：未排期（按 0.13.0 反馈修复计划 R12 实施）

来源与关联：[台账](../BACKLOG.md) FEAT-007 行；[履带反馈](../validation/TRACK-FEEDBACK-2026-10-16.md)；[0.13.0 反馈修复计划](../superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md) R12。关联 FEAT-006、FEAT-023、FEAT-033、BUG-053、BUG-109。

## 问题或目标

台账 FEAT-007 同时记录两类请求：任务进度细分（已完成/总操作数、当前操作与阶段）与 `creo_get_job` 长轮询。本卡只落长轮询子项：外部反馈单个 job 需 4～6 次轮询，16 个 job 约 50 次（2026-11-03 Creo 10 曲面复测），要求 `wait_seconds ≤ 30`、完成即返回。

本卡不声明任务进度细分已交付；完成百分比、当前原生操作与“建模/保存/重载/登记/回滚”阶段展示仍留在 FEAT-007 待规划范围，`wait_seconds` 只改变一次读取的返回时机。

## 范围

接口：

- `server.creo_get_job(job_id, detail, section, limit, cursor, sections, wait_seconds=0)`；`wait_seconds` 为严格整数 0..30，默认 0；浮点、布尔、字符串、负数与超过 30 的值在读取任务目录前以参数错误拒绝。
- `bridge.get_job(..., wait_seconds=0, *, clock, sleep)`；时钟与睡眠可注入，测试不实际等待。

等待语义：

- 终态集合 `succeeded` / `failed` / `cancelled` / `aborted` / `unknown_outcome` 立即返回。
- 未终态时只轮询持久化 `job.json`（约每 0.25 s），不持 Toolkit 通道锁、不新建 job、不修改任何超时、不重新提交、不写任务文件；等待期间通道是否 busy 与结果无关（busy 不属于 `get_job`）。
- 到期返回当时的真实状态，并带 `wait_seconds`（原样回显）、`waited_seconds`（实测秒数）与 `wait_expired=true`；不伪称完成。
- 等待可被中断（进程中断或客户端取消）：中断只结束等待，不取消 job、不清保护；之后的普通查询仍读到原状态。
- 并发客户端各自等待同一或不同 job 互不影响，没有共享等待状态、队列或公平调度保证。

非目标：不新增并发队列或调度；不自动重试、不自动重交、不自动改超时；不改变 `status="busy"` 立即拒绝契约；不新增 job 取消接口；不扩展进度百分比或 `progress` 机制；不改原生执行器与 `job_projection.py`。

兼容性：新增字段插入现有返回 dict，compact/full 原有字段、分页、`sections` 选择和 32 KiB 预算路径不变；默认 `wait_seconds=0` 的调用保持即时返回。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python 离线 | `python -m unittest tests.unit.test_job_long_poll tests.unit.test_surface_chain_results -v` | 默认 0、终态立即返回、到期、等待中完成、非法参数、不持通道/不提交、中断、并发等待与 server 接线全部通过 |
| 格式 | `python -m ruff format server.py bridge.py tests\unit\test_job_long_poll.py` | 无未格式化差异，无新增语言问题 |
| MCP stdio 客户端 | 对已接受的真实 job 调用 `creo_get_job(wait_seconds=N)` | 回显三个等待字段；终态/到期行为与离线一致；等待期间不产生新 job，客户端取消后 job 仍可查询 |
| 本机 Creo 12.4 / 匹配 SDK | 对真实长任务轮询 | 完成即返回；未完成到期如实返回；通道锁、超时、保护与 revision 不受影响 |
| WorkBuddy | 仅公开 MCP 操作 | 未执行；不作为本卡通过依据 |

## 实现与证据

2026-11-06 离线实现（未连接 Creo、未启动 Creo、未发 Toolkit 调用）：

- `server.py`：仅 `creo_get_job` 新增 `wait_seconds` 参数并透传；字段使用严格整数、0..30 边界。
- `bridge.py`：`get_job` 新增等待包装与私有 `_validate_wait_seconds`、`_manifest_status`；原读取/投影逻辑移入 `_read_job`，语义未改。
- `tests/unit/test_job_long_poll.py`：9 个用例，覆盖默认立即返回、5 个终态立即返回、未终态到期、等待中完成、非法参数不读任务、等待不提交/不持通道、中断只结束等待、并发等待独立与 server 参数透传。

环境：Windows 11 10.0.26100、Python 3.12.14；测试命令 `python -m unittest tests.unit.test_job_long_poll tests.unit.test_surface_chain_results -v`，13 项通过（本卡 9 项 + surface chain 回归 4 项）；另跑 `test_compact_sections`、`test_job_stage_reporting`、`test_job_projection`、`tests.test_job_query` 回归共 58 项全部通过；`ruff format` 已执行。时间 2026-11-06。未记录提交号与源码指纹，本次交付不涉及提交、构建或发布。

已实现（离线）与未验证范围：

- 已实现：参数校验、manifest-only 等待、终态/到期回执、不持通道/不提交、线程级并发等待与中断语义；工具参数模型的严格整数校验另以 schema 核对（浮点 1.0 被 pydantic 拒绝，整数通过）。
- 未验证：真实 Creo 会话与真实长任务；MCP stdio 客户端从外部发送参数及断流/取消；`asyncio.to_thread` 取消后后台线程可能继续完成等待（它不触碰 job，但客户端取消的精确时序未验证）；多进程并发客户端；真实 30 秒边界与客户端自身读超时；WorkBuddy 黑盒。上述均不得据离线结果宣称通过。
