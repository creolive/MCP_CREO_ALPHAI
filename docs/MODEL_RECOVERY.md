# 未知作业与受控模型恢复

当前版本0.3.5已补齐恢复MCP空值/省略契约、畸形ID精确错误及stale诊断，BUG-055的核心WorkBuddy验收见[记录](validation/BUG-055-WorkBuddy-acceptance-2026-10-17.md)。客户端不能保真发送null时省略该字段；M2终态因BUG-056通道掉线未取得，禁止自动清保护或重放。FEAT-018完整范围仍验收中，BUG-001按用户决定关闭。本机开发只使用指向E盘的MCP_CREO_MechDog_dev，部署身份按公开启动指纹核对。

适用于0.3.4提供的 `creo_reconcile_model`；历史公开0.3.3没有该工具。通过 `creo_capabilities` 确认实际部署，更新源码后构建执行器并重新连接 MCP，不能仅凭磁盘上的版本说明判断客户端已经加载新工具。

超时或失联不证明建模没有发生。先保留原 `job_id`，用 `creo_get_job` 查证据；不要重交原计划、编辑 `model.json` 或删除 reservation。`creo_startup_status(retry=true)` 只复核通道，模型处置使用下述独立接口。

## 查询

开发分支 BUG-074 为缺少完整进程身份的历史作业增加严格的跨启动证据，包含只有 PID 而没有创建时间的旧身份及 native_pid 检查点：Windows 启动时间须经 WMI/内核时钟交叉核验；原作业目录及控制记录的创建、修改时间和作业声明时间均须早于该启动时间。完整但仍活动或不可读的身份不得走此兜底，格式错误的身份也不能借此绕过保护。同次启动、记录缺失、时钟不一致或文件变化仍拒绝；owners 返回原因及操作指引，不要求删除模型。四动作各自的基线/候选/健康会话条件不变。此证据绑定令牌，准入和原生派发前后重新核对，文件仅触碰时间戳也使旧证据失效。跨启动证明不表示当前 Creo 已就绪，实际处置仍须显式 apply。

```json
{"model_id":"<异常模型ID>","mode":"inspect"}
```

持久化查询不连接 Creo，通道忙或没有 Creo 时仍可使用。返回 revision、pending_job、原任务/执行器身份、基线与候选 SHA256、各动作的 `available/reason`、有 10 分钟有效期的 `evidence_token` 及已有处置。查询不会解除模型保护。

需要核对会话时显式加 `"live":true`。实时预检使用同一 Toolkit 通道，繁忙时返回 busy；检查模型来源、健康、单位、外部依赖及相对登记基线的偏离。它不保存、擦除或接受几何。失联或权限不足表示无法确认，不等于安全。accept_live 必须先做实时预检。

## 挂起现场的用户处置指引（BUG-078 反馈补录）

- **保留一切原状**：原 `job_id`/`model_id`、失败恢复作业、inspect 返回与全部诊断（job 结果、native 日志、evidence）都保留；不要重交原计划、删 reservation、手工清保护或按消息文本解除 unknown。
- **重新 inspect 后再选择**：处置前先重新 `creo_reconcile_model(mode="inspect")`，按本次返回的各动作 `available/reason` 与 10 分钟有效的 `evidence_token` 选择动作；`live:true` 实时预检同样须先满足会话核对条件，会话条件变化会使旧证据失效，以最新 inspect 为准。
- **accept 两动作已在健康会话闭环**：accept_saved/accept_live 在健康会话各 3/3 实机通过（[BUG-078 根因记录](validation/BUG078-ROOT-CAUSE-2026-10-22.md)）；若仍遇 Backup -1，保留现场与诊断转 BUG-078，不自行用延迟、重试或替换保存路径规避。
- **三个历史挂起模型**（`de6f0bb5…`/`bebe7e2b…`/`57294ff8…`）live 已缺失、仅 `restore_baseline` 可用：绝不自动 apply 或清保护，等待操作者明确选择后执行，原始异常历史保留。

## 会话健康证据（session_health，BUG-078）

`creo_startup_status` 与 `creo_session_status` 的响应新增只读字段 `session_health`，用于在**不产生任何新 Toolkit 调用**的前提下说明“这台会话最近的保存/连接事实”。`creo_startup_status()` 本身不连接 Creo，因此该字段可在通道冻结或会话可疑时安全查询；`creo_session_status` 复用本次探测已完成的结果，不额外连接、不保存、不探测。

| `status` | 含义 | 用户下一步 |
| --- | --- | --- |
| `unknown` | 无证据、证据不可读、超过证据窗口（600 秒）、会话身份不明，或身份已过期 | 先用 `creo_session_status` 取得一次只读观测；崩溃/失联后按本文件前述流程保留作业并 inspect |
| `suspected_damage` | 当前会话内记录了保存失败（如 `ProMdlnameBackup` -1）或 `unknown_outcome` 保护 | 立即停止重试，保留原作业与诊断，先持久化 `creo_reconcile_model(mode="inspect")` |
| `no_failure_observed` | 当前会话在窗口内有一次已验证保存 | 仅表示“近期没观察到失败”，**不是健康保证** |

使用要点：

- **只读**：该字段不取 Toolkit 通道锁、不建连接、不保存、不写文件、不清保护；它只汇总已落盘的作业结果与最近一次探针结果，所以查询它不会改变模型、revision、未知保护或恢复历史。
- **不是健康保证**：`no_failure_observed` 只代表当前会话在窗口内没有保存失败记录；连接成功和历史成功都不证明下一次 `Backup` 会成功。保存是否成功只看作业的 `saved_file_reloaded_and_verified`。
- **会话重建会让旧证据失效**：字段里的 `session.identity` 是原生会话指纹。换会话后 `session.changed=true`，旧会话的成功不会被沿用；请重新观测后再写模型。
- **繁忙如实表达**：`facts.channel.busy=true` 表示通道登记里有正在进行的调用，此时 `next_steps` 首条是等待占用作业；本字段不会因为无法刷新而假装健康，也不会去试锁造成误判。
- **不可读如实表达**：证据文件权限不足或损坏时返回 `unknown` 且 `reason=evidence_unreadable`，并在 `evidence.jobs_unreadable`/`evidence.problems` 列出，不猜测结论。

`suspected_damage` 的建议顺序（与上面的挂起现场指引一致）：保留原 `job_id`/`model_id`、失败作业与 native 日志 → 持久化 inspect 取得最新 `available/reason` 与 `evidence_token` → 由操作者选择动作并 apply → 若会话已损坏，**人工确认**关闭并重新打开 Creo，本服务不会自动重启 Creo、不会自动清保护 → 重建后重新观测再保存。

## 明确选择动作

| action | 结果 | revision |
| --- | --- | --- |
| restore_baseline | 丢弃本模型受管会话副本的偏离，从摘要匹配的已登记检查点重载核验 | 保持 r |
| accept_saved | 仅选择原作业核验检查点绑定的保存候选，核对几何/特征/参数后保存重载并登记 | r+1，一次 |
| accept_live | 接纳实时预检中明确选中的健康自有会话几何，保存重载核验后登记；不保证原计划全部完成 | r+1，一次 |
| abandon_new | 放弃 revision=0 且无基线的新件，只擦除可证明归属的会话副本；保留文件、输入和审计 | 不推进，状态 abandoned |

只支持可证明独立、受管的 part/sheetmetal。assembly/drawing、外部依赖、未记录进程身份或缺失/改动的基线等不能通过本接口强制接受；保留证据并按返回原因人工核对。没有 model_id 的 legacy plate 产物不在本接口范围。

调用者必须明确选定动作；会丢弃会话修改的 restore/abandon 及会接纳成果的 accept 都不能由 Agent 因超时自行选择。下例只是字段格式，实际值必须来自本次预检，不能照抄占位符：

```json
{
  "model_id":"<异常模型ID>",
  "mode":"apply",
  "action":"restore_baseline",
  "expected_revision":1,
  "expected_pending_job_id":"<本次预检返回的pending_job；为null时发送JSON null或省略字段>",
  "evidence_token":"<本次预检令牌>",
  "idempotency_key":"operator_recovery_001"
}
```

`expected_pending_job_id` 契约：必须逐字等于本次预检返回的 `pending_job`。预检返回 null（无待定作业）时发送 JSON null 或省略该字段，两者等价；**不要发送空字符串 `""`**——空串/空白串会被作为请求缺陷精确拒绝（错误引用实际收到的值），不会与 null 混同，也不会被当作模型 revision 冲突。客户端确实无法发送 null 时优先省略字段；字面字符串 `"null"` 在当前 SDK 下会被预解析为 null，但不要依赖该行为。revision 与 pending 不匹配分别返回独立的 stale 错误并给出模型实际值。

接受后只轮询返回的恢复 `job_id`，不重复提交原计划。同一幂等键与相同输入返回同一恢复任务；换动作或输入必须换键并重新预检。文件、部署、revision 或 reservation 改变会拒绝旧证据。busy 表示本次未获准，遵循其 blocking 字段，不假设排队。

## 判断完成

恢复作业必须 `succeeded`；除 abandon 外还须 `saved_file_reloaded_and_verified=true`。核对处置动作、revision、保存文件与摘要、原生特征/尺寸/参数/体积，再用最新 revision 继续正常编辑。原未知作业仍保持原历史；其 recovery.resolution 和模型 reconciliation 记录此次独立处置，不能把 accept 解释为原计划剩余操作已执行。

开发分支 DEV-040 按实际失败阶段记录终态；`creo_get_job(detail="compact")` 和同参幂等重放均保留 `reason`、`failure_phase`、`recovery_pending_released`，不能仅凭消息中出现 “refused” 判断是否已进入原生阶段：

| 阶段 | 返回与保护 |
| --- | --- |
| apply 准入校验 | 过期/缺失 token、stale revision/pending 等直接拒绝；不创建恢复作业或预留。token 仍在准入时按 600 秒校验，不刷新或延长 |
| `failure_phase="before_native"` | 原生派发前证据/配置校验拒绝为 `failed / reconciliation_refused`，附稳定 `reason`；在通道锁内只清除此作业自己的 `recovery_pending`，释放通道后发布终态。恢复 runner 启动失败同样处理 |
| `failure_phase="channel_admission"` | 已接受的 runner 未取得通道，作业 `failed`，保留 busy 信息与预留；未取得锁时不能修改保护，不自动重试或排队 |
| `failure_phase="native_worker_started"` | 已进入原生派发，worker **可能已开工**；仍为 `unknown_outcome / reconciliation_unconfirmed`，保留原 pending 及 recovery_pending。该字段沿用派发前持久化的标记，不证明进程实际启动或修改了模型 |

Python 侧的 `reason="session_selection_changed"` 表示准入后配置中的 Creo 会话选择发生变化，在 `_native` 前拒绝。原生消息 `Recovery refused: Creo session changed since recorded evidence` 则发生在 worker 已连接 Creo、读取会话指纹后，在恢复模型查找/擦除/加载前比较指纹；当前原生协议没有结构化的“恢复动作未开始且模型未修改”证明，因此保守保留 unknown 与保护，并通过 `result.failed_stage`、原始 `result.message` 及失败阶段说明判定位置。不得将这两种会话变化混为同一分支，也不得按消息文本清保护。

其他确定性证据拒绝的 `reason` 包括 `reservation_changed`、`model_changed`、`deployment_changed`、`job_evidence_changed`、`original_worker_unconfirmed`、`source_changed`；runner 启动失败为 `runner_start_failed`。同样的证据检查若在原生派发后失败，仍按 `native_worker_started` 保留 unknown。真正超时、派发异常或交付未确认也保留保护，通常返回 `reason="native_outcome_unconfirmed"`。

`recovery_pending_released=true` 只表示本次失败恢复任务的预留已清除，不表示原任务被恢复：原 `pending_job`、unknown 状态、revision 和历史不变，`recovery_required` 仍可为 true。清理失败时 `recovery_pending_released=false` 并给出 `recovery_pending_cleanup_error`；锁收尾异常另列 `channel_finalization_error`，不覆盖此前拒绝原因或清理结果。只轮询并核对返回证据，不手工清保护。同一幂等键继续返回原失败作业；确需再次处置时先重新预检并使用新键。

成功作业通常不带 `failure_phase`；该字段缺失不能单独用于识别旧版本或判断成功，应同时核对 job.status 与公开服务版本。`before_native` 的准入后竞争窗口由开发者隔离夹具验证，不提供生产故障开关；WorkBuddy 仅验证公开接口实际可达场景，无法触发的内部阶段标为未验证。

登记采用持久化提交决策：决定提交前中断须重新核对；决定提交后查询可仅补全元数据，不再次推进 revision。即使通道已经空闲，也不能据此解除模型保护。原生动作不自动重跑。

单文件摘要采用流式读取，最多 1 GiB/8 秒，持久化快照预算 12 秒；超过预算准确拒绝。原生恢复/实时预检阶段 90 秒、断开 20 秒、Python 外层 115 秒，仅约束此次执行器，不终止 Creo。构建沿用既有有界流程。新旧版本、开发者注入与 WorkBuddy 黑盒的实测边界见联合任务卡及本次验证记录。
