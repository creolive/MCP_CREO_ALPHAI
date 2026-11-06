# FEAT-001：会话检测、重连与统一上下文

类型：功能。优先级：P1。状态：部分交付 **0.15.0**（会话回执与 health 事实分层、启动重试身份/阶段/预算、Toolkit 忙立即返回；真实断连、`-4`、挂起现场未验证）。目标版本：0.15.0（部分）。

来源：原主台账既有同ID条目；2026-11-03补建缺失工作卡，不新增台账身份，不改历史结论。

## 原目标与当前边界

补齐 Creo 关闭、启动、重连和多会话时检测，区分准备、未就绪和无法确认；连接不可用时明确拒绝，不能先收任务。原有普通 retry/跨日重连未验事实保留。

## 2026-11-03 alphai 比较新增子项

本次只扩展逐字段有来源和时间的会话上下文：默认本地证据聚合、显式 live 走同一只读通道，旧ready不当作实时；不实现自动选最新PID、自动重连、重启或恢复解锁。

任务号 D01，负责人unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-d-workflow-plan.md)，统一协调[DEV-067](DEV-067.md)。

## 验收标准与环境

默认不连接、live同通道忙拒、空模型/旧记录/身份冲突明确unknown；原模型、目录、窗口、revision不变；其余原ID会话生命周期范围继续开放。

具体专项unittest、默认离线驱动、当前原生/MCP断言见子计划。Windows x64/Python 3.12+；原生适用时本机Creo 12.4.0.0/匹配SDK及许可，实机先满足BUG-001条件并由会话负责人串行安排；Creo 9/10未测保留，WorkBuddy只做公开MCP黑盒。

## 实现与证据

本次仅补卡和规划，未实施新子项、未连接Creo、未运行产品测试、未合入main/发布；现有能力不因补卡变为本轮验证通过。后续记录提交、dirty、受测源码指纹、实际命令/环境与未测范围。

## 2026-11-04 R05：连接阶段-38观察增量

0.12.0发布首轮d580ff17…在connect阶段-38/no_effect，未执行建模，后轮67/67通过。当前只能确认阶段与后轮成功，根因仍未定，不能据重跑推断与版本无关。按[后续计划R05](../superpowers/plans/2026-11-04-alphai-post0120-integration-plan.md)收集身份/时间/原始错误，不自动重试/故障注入；BUG-001关闭决定和unknown保护保持。本次未连接Creo，原条目整体仍待规划。

## 2026-11-06 R06 离线实现：会话进度、health 与 busy 的可解释性

本节按 0.13.0 反馈修复计划 R06 追加，只记录离线实现与离线证据，不改变条目原有状态。

启动回执在保留 `launch_attempt`（仅实际启动时递增）与既有 `state`、`retry_allowed` 语义的前提下，新增：稳定 `retry_id`（同一次 retry 内不变，轮询 `creo_startup_status` 不会新建 retry）、`phase`、ISO-8601 的 `started_at`/`deadline_at`/`phase_deadline_at`、`failure_code`、`terminal_reason`、`retry_blocked_by`；`next_allowed_retry_at` 在服务无法保证时返回 `null` 并附 `next_allowed_retry_reason`。总预算与阶段预算分别标注 `budget_scope="total"`、`phase_budget_scope="phase"`，并提供 `budget_active`。`creo_session_status` 标记 `mode="explicit_live"`、`live_probe` 和 `channel_policy`，通道忙时立即返回 busy，不排队、不重试、不开第二通道。

`session_health.snapshot()` 增加 `path="local_evidence"` 与 `path_note`，为最近连接、最近保存、历史保存、历史损坏和旧身份分别标注来源（recorded_job / toolkit_probe / attributed）、时间与 `stale`；补充 `historic_saves`、`worker` 事实（`causality="suspected_only"`）及 `session.identity_stale`。连接成功仍不会把整体状态升级为“健康”，历史失败也不会覆盖当前 `connected` 事实。窗口观察保持只读有界：不激活/关闭窗口、不读取标题，回执明确 `window_title` 不可得的原因，并以 `hung_implies_modal=false` 说明 hung 不等于 modal。

离线验证：`tests/test_creo_startup.py` 41 项、`tests.unit.test_startup_retry` 9 项、`tests.unit.test_t10_session_health` 26 项全部通过，覆盖正在探测、通道忙、进程存在但 IPC 不可读、无进程、预算到期、`retry_id` 稳定、轮询不新建 retry、无启动不增 `launch_attempt`、默认路径零 Toolkit 调用且不启动进程。本次未连接 Creo、未新建 Toolkit 通道、未启动或结束进程、未做故障注入。

仍未验证：真实断连后的重试行为、WorkBuddy 公开 MCP 黑盒、实机启动/窗口状态与 `-4/exit 20` 现场，均需在 BUG-001 准入条件下另行串行执行；按任务约束未改 `capabilities.py` 工具描述。
