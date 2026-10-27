# DEV-047 / T11 显式世代安全回收离线验收

日期：2026-10-26（Asia/Shanghai）。条目：DEV-027 实际回收子项，DEV-047 T11。基线 `0522625`（T00—T10 已纳入）；分支 `codex/dev047-t11-reclaim-generations`。本次源码版本仍为 0.6.1，0.7.0 集成与发布由 T13 收口。

执行说明：本任务由用户指派的实现子代理开始实施；其在专项单测阶段因客户端后端异常中断（连续三次 spawn 即拒，未再产生变更）。遗留实现经集成负责人逐行核对符合接口基线第 6 节后，由集成负责人补齐格式化、全量验证与文档并提交；实现内容本身全部来自中断前的子代理工作区，集成负责人未改写其语义。

## 接口与实现

- 新工具 `creo_reclaim_generations(mode="inspect"|"apply", generation_keys, evidence_token, idempotency_key)`（`server.py` 只注册/适配，注册数 93→94；能力族 `generation_reclaim` 与 support_status 同步登记）。
- `generation_keys` 只接受显式 `[{root: blend_loader|blend_callback, key: <十六进制世代目录名>}]`（1—50 项，去重）；路径、盘符、`..`、非自有命名一律准入拒绝。inspect 传 token/key 拒绝，apply 传 generation_keys 拒绝，`idempotency_key` 限 8—80 位字母/数字/下划线/连字符。
- inspect 复用 `blend_callback.generation_inventory` 的引用三态（current、本地注册、runtime 证据、records 状态与冲突），另做：根目录/目标目录 `resolve(strict=True)` 且必须位于 `build/blend_loader|blend_callback` 之内、目录名不得被重定向、符号链接/junction/重解析点拒绝（根与目标双层）、扁平目录内容逐文件 SHA256 摘要并标记非自有/意外条目、独占写打开探测文件占用。当前、注册、被 loader 世代引用、runtime 引用、回退保留（每个根最新非当前世代）以及记录缺失/冲突/复核原因的全部判 `kept` 并逐项给原因；"非当前"或"没查到记录"不授权删除。
- 证据令牌：仅对 reclaimable 项签发 uuid 令牌，600 秒有效，持久化于 `build/generation_reclaim/evidence-<token>.json`，绑定目标清单、目录内容摘要、引用证据与盘点记录状态；inspect 不删除任何内容。
- apply 复用 `bridge.toolkit_lock`（与构建/世代发布同一把锁，互斥期间忙即拒绝）；先核验令牌记录、有效期，再重盘引用并逐项比对内容摘要与引用证据（`content_changed`/`reference_changed` 拒绝旧证据），执行前对每个目录重跑完整审计（含占用与回退保留变化）。回收意图以幂等键 SHA256 指针持久化（`intent-<hash>.json`），同键重放返回上次结果不再删除，同键换令牌拒绝；中断意图重放时未完成项如实标 `unknown`/`interrupted`。逐项返回 `reclaimed/kept/failed/unknown` 与删除进度，部分失败不假装整体回滚。
- 不在启动、升级或 `callback_status` 查询中自动清理；不加载 DLL；不建立 Toolkit 连接；inspect/apply 响应均带 `toolkit_connections: 0`、`dll_loaded: false`。

## 离线夹具覆盖（tests/unit/test_t11_reclaim_generations.py，21 项）

隔离临时目录夹具覆盖任务书验收点：当前/注册/runtime 引用与回退保留世代保留；占用世代保留；记录缺失与记录冲突保留；意外内容与非世代目录保留；目录链接与目录内文件链接拒绝；选择层拒绝穿越/绝对路径/非法模式；成功回收只删授权项；同键重放不重复删除；同键换令牌拒绝；证据过期拒绝；inspect 后内容变化拒绝；inspect 后新引用拒绝；与构建并发时两模式均按锁拒绝；apply 前回退保留变化保持该项；部分失败如实报告；中断意图重放不删除；未授权目标 apply 保持；夹具外世代零触碰；回收与 generation_inventory 共享同一引用分类。

## 已执行的离线检查

环境：Windows 11 x64；Python 3.12.14；Ruff（.venv）。无原生改动，未运行 SDK 构建（本任务纯 Python）。

| 命令/检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t11_reclaim_generations -q` | 21 项通过（格式化后复跑 2.029 秒 OK） |
| `python -m unittest discover -s tests -q` | 958 项通过，203.618 秒，exit 0（`build/t11-unit.log`） |
| ruff check + format --check（5 个变更 Python 文件） | check 全过；两个新文件按格式化输出重排后 5 文件全部符合，无基线豁免 |
| `python tools/dev_check.py --work-item DEV-027` | exit 0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；证据 `build/development_check.json`、`build/t11-devcheck.log` |

dev_check 指纹：基线提交 `052262547464f7a2fd891638b5cd9c7374b804d2`、dirty=true（验证时含本次改动）、`checked_source_sha256=5be7ddacf1241af82f7c94d24b17bd43dede3c10cc13d95bd72d6a522ef87d26`。提交后仅追加本记录与台账文档，未再改源码。

工作区原有 `session_activity.json` 修改与未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/*` 保持原状，未提交。真实 `build/blend_loader|blend_callback` 世代目录未做任何删除或写操作；单测夹具全部位于隔离临时目录。

## 未测与保留范围

- **实机未验收**：真实世代目录的只读盘点（`creo_reclaim_generations(mode="inspect")` 对本机 build/ 的实际输出）未执行；真实环境删除仅限未来专门创建且已证明无引用的测试世代，本轮未创建。
- 并行构建进程与 apply 的真实竞争（非单测内锁模拟）、真实占用 DLL 场景、外部 `..` 注入请求未实测。
- DEV-027 二进制可复现性子项与副本被外部改动的分支仍开放，不因本子项关闭父卡。
- 本轮未连接 Toolkit、未创建 MCP 客户端、未启动/结束 Creo、无会话探测/故障注入、未清 unknown 保护；工具数 94 仅由单元注册检查确认，活 MCP `creo_capabilities` 复核归 T13。
