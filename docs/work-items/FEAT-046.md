# FEAT-046：显式擦除会话模型（creo_erase_session_models）

日期：2026-10-21。类型：功能。优先级：P1。状态：验收中（单元与构建已过；实机与 WorkBuddy 待验）。目标版本：0.4.6（用户 2026-10-21 指定，含新增公开工具作为 PATCH 例外）。

来源：[0.4.3 反馈完善计划](../development/0.4.3-feedback-improvement-plan-2026-10-21.md) 第二批；关联 FEAT-043/044（会话可观察性）、FEAT-045（外部装配树检查另期，不混入本工具）。

## 目标

新增 `creo_erase_session_models`，覆盖用户选定的装配及其组件清单的显式会话擦除：inspect 出计划并签发 600 秒令牌，apply 仅执行令牌中的清单并返回 `job_id` 轮询。不保存模型、不删除磁盘文件。

## 范围

- `inspect(targets)`：`targets` 为 `{"name","model_type"}` 列表（与会话枚举条目的定位方式一致）。返回每项目标身份（name/model_type/origin/modified/is_current/session_model_id/query_codes）、阻断原因、擦除顺序、擦除后剩余对象清单和 `evidence_token`（600 秒）。
- `apply(evidence_token, idempotency_key)`：仅执行令牌中的清单；同键重放返回原 job，不同参数拒绝。返回 `job_id`，通过 `creo_get_job` 轮询。
- 资格：仅有盘（has_saved_origin）、`modified=false`、非托管（origin 不在服务输出目录）的对象；查询不完整（枚举错误/截断）、清单外引用（清单内目标被清单外会话模型依赖）、依赖环均拒绝。
- 顺序：按"装配→子装配→零件"依赖拓扑逐项执行；不自动扩大清单，不调用全局或递归擦除接口。
- 每项执行前复核身份、修改状态和引用关系；擦除后分阶段查询确认消失，不能仅凭 API 返回零报告成功。
- 全作业持有同一通道锁；中途失败停止剩余项，明确报告已完成和未确认清单，不自动重载或重放。
- 允许处理符合条件的当前显示模型；不保存、不删除磁盘文件、不触碰托管模型与 unknown 保护。

不包含：外部装配完整组件树与约束检查（FEAT-045）、托管模型清理（reconcile 已有 abandon_new）、绘制/布局等其他类型对象的擦除。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | 单元测试（隔离构造令牌/清单/拒绝场景） | 令牌篡改、缺失、过期、清单外引用、dirty、托管目标均准确拒绝；幂等键重放一致；无半执行 |
| Windows / Python | `python -m unittest discover -s tests -v` 与 `tools/dev_check.py` | 全部通过，无新增语言问题 |
| 本机 Creo 12.4 / E 盘 dev 服务 | 装配+组件清单 inspect→apply | 擦除顺序符合拓扑；擦除后装配可再次 `creo_open_file`；剩余对象与预期一致 |
| 本机 Creo 12.4 | 阻断场景 | dirty/未保存/托管/清单外引用/环返回结构化原因，无擦除发生 |

## 实现与证据

2026-10-21 实施于分支 `codex/dev-043-ledger-simplification`，见[实施记录](../validation/FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)。

- `native/generic.cpp` `session_erase_native`（inspect/apply）：完整清单、资格阻断、全会话依赖图（清单外引用/依赖环拒绝）、装配先于组件的拓扑序、预期剩余对象；apply 逐项复核（存在性/修改/origin/受管）→ ProMdlErase → 两次独立查询确认消失，中途失败停止并报告 erased/unconfirmed/remaining。
- `src/creo_mechdog/session_erase.py`：inspect 同步探查+600 秒令牌（仅 available 清单签发，内容冻结不可扩大）；apply 令牌校验（缺失/过期/跨键拒绝）+幂等 journal+后台 job，全作业单一通道锁；成功后记录 `session_activity`。
- 注册：`server.py` `creo_erase_session_models`（工具数 88）、`capabilities.py` `session_erase` 家族、README 用法与运行目录说明。
- 验证：`tests/unit/test_session_erase.py` 5 项（令牌签发条件、非法 targets 不建 job、令牌缺失/过期拒绝、幂等重放与跨键拒绝、成功记录会话变化）；全量 502 项单测与 dev_check 通过；SDK 构建通过。
- 开放：本机 Creo 12.4 实机（装配+组件清单 inspect→apply、擦除后再次 `creo_open_file`、dirty/托管/清单外引用/环阻断场景）、WorkBuddy 黑盒。

### 2026-10-22 外部实机主链路证据补录（0.4.6 反馈）

[0.4.6 验收报告 §3.1/§3.2](../validation/feedback-0.4.6-2026-10-21/manifest.json)（Windows 10 / Creo 10.0.0.0）实测 inspect→apply 两轮全过：第一轮 10 目标（ASM_MX + 8 组件 + P02/P06）全部 `erased`、`stopped_early=false`、`remaining_after` 与计划一致、当前窗口模型正常纳入；第二轮 UP_MX 单目标后会话归零。装配先序、逐项重验、双查询确认、源文件 sha256 无变化与托管模型隔离均按契约兑现；随后 `creo_open_file(asm_mx.asm.16)` 干净会话一次成功（8 组件加载、sha256 双审计一致），"擦除→干净会话→打开装配→组件回读"链路外部闭环。本条关闭**外部实机主链路**子项；本机 Creo 12.4 矩阵、阻断场景（dirty/未保存/清单外引用/环）与 WorkBuddy 黑盒仍开放，外部通过不外推本机。
