# FEAT-043：只读枚举当前 Creo 会话模型

日期：2026-10-18。类型：功能。优先级：P2。状态：验收中。目标版本：未排期。

来源：现有模型无法纳管反馈第5项；关联 FEAT-042、FEAT-023。

## 当前进度（2026-10-21）

会话枚举已交付；0.4.5在磁盘打开成功结果复用单模型观察字段opened_session_model及observed_at，直接查询已打开句柄，不额外全量枚举。实机两作业核对is_current/origin/query_codes及compact/full一致性，见[实施证据](../validation/BUG076-FEEDBACK042-2026-10-21.md)。README已明确省略cursor实时重采、携cursor冻结快照；快照过期显式提示尚未实现。

剩余unknown、其他类型、真实并发枚举及新增打开结果字段的WorkBuddy复核；已有9模型/5页遍历不能代表这些范围通过。

## 目标与范围

新增 creo_list_session_models(limit=20, cursor=None)，最大50条；返回名称、类型、是否当前、origin、有无保存来源、未保存修改状态及可证明的受管关联。分页绑定同一快照，无法确认的字段为 null。查询不加载、保存或切换模型，不自动接管；用户在 Creo 切到目标后使用现有接管工具。通道 busy 立即拒绝，无自动重试。

## 验收

单元与真实 stdio MCP 覆盖分页、过期/非法cursor、状态未知、读取失败、受管关联和busy；本机 Creo12.4/匹配SDK 枚举已保存、无盘、dirty、不支持类型与已受管对象，检查当前窗口不变。开发证据与 WorkBuddy 黑盒分开；当前会话限制满足前不建立新连接。

## 实现与证据

本轮在 codex/feat-042-adoption-completion 实施。原生枚举受支持查询类型，不支持/失败的类型保留type_errors与complete=false；逐字段返回query_codes/null。Python固定快照分页，十分钟有效、32KiB分页上限，只按已核验文件身份关联登记。规则及真实stdio（原生边界替换）回归、全量403项单元和匹配12.4 SDK构建通过。2026-10-18开发脚本首次就绪探测超时的[历史记录](../validation/ADOPTION-COMPLETION-2026-10-18.md)保持原样。2026-10-19用户转贴WorkBuddy报告已真实发现无盘WB_UNSAVED_01（origin空、has_saved_origin=false、modified=true、model_id=null），并观察准备前后原件/副本及当前窗口；一次真实busy含blocking字段，不能据此判定实际并发测试通过。见[黑盒补录](../validation/ADOPTION-WorkBuddy-2026-10-19.md)。后续WorkBuddy在9模型会话以limit=2遍历5页，相同snapshot_id/checked_at、无重复遗漏、末页next_cursor=null且不切窗，真实多页通过；同时观察无盘、clean、dirty、sheetmetal、assembly与受管副本。unknown字段失败路径、其他类型及实际并发仍未验。session_model_id跨类型重复沿用临时发现提示边界，不作身份键；query_codes仅保留实际查询的诊断，subtype目前只查询part分支。

## 2026-10-20：session_model_id 取 0 与重复的再确认

[0.5.0 open-file 黑盒验收](../validation/WORKBUDDY-0.5.0-open-file-2026-10-20.md)附带发现：重启后的新会话中 WBOPEN_V1 与残留 WBOPEN_ASM2 同时返回 session_model_id=0，上一会话也出现过装配与子件同值——与既有定性一致（Creo 会话内整数 ID 可为 0 且跨类型重复，仅作临时发现提示）。工具描述已补写"可能取 0 或跨类型重复，定位模型用 name+model_type"；session_fingerprint 标识连接/进程会话、不随会话内容变化这一语义也已写入描述，避免以指纹判断会话内容。不改字段行为。

### 2026-10-21 快照年龄与会话变化记录

按[0.4.3 反馈完善计划](../development/0.4.3-feedback-improvement-plan-2026-10-21.md)实施（分支 `codex/dev-043-ledger-simplification`，[实施记录](../validation/FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)）：`creo_list_session_models` 响应新增 `snapshot_age_seconds`、`refresh_guidance` 与 `service_session_changes`（自快照创建起、有界、跨进程 `session_activity.json`）；`creo_open_file`/收养 apply/confirm/恢复各动作/擦除成功后记录服务引起的会话内容变化，GUI 手工变化明确标注未实时复核。省略 cursor 实时重采、携 cursor 冻结快照语义不变；既有测试 44 项通过。剩余实机复核与 WorkBuddy。

### 2026-10-21 opened_session_model 行为核对（FEAT-043/044）

[0.4.5/Creo 10 反馈](../validation/feedback-0.4.4-2026-10-21/report-registry-bloat.md) §4.2 报告"Creo 10 环境 open_file 成功结果中没有 `opened_session_model` 字段"。2026-10-21 源码核对结论（三个场景逐一对照）：

- **显示成功后必生成**：`native/generic.cpp` 仅在 `displayed == true` 之后才写 `open_file.opened_session_model`（单句柄观测，不做全量枚举），Python closeout 补 `observed_at`/`observed_at_source`。
- **同名已驻留模型不会走到该分支**：预检阶段按 name+model_type 命中即 `SESSION_NAME_CONFLICT` 拒绝并返回 `conflicting_session_model`，文件未取回。反馈方的会话正是延续多轮验收（部件已驻留），最可能是该路径而非字段缺失。
- **显示失败同样不生成**：显示失败时只返回 `displayed=false`+`display_message`，模型仍在会话中（0.4.6 的 `loaded_session_models` 在显示成功后补充会话概览）。

结论：**字段缺失不等于实现缺陷**，符合计划"确认新成功作业确有缺失后再修复"的前置条件——源码核对未发现成功打开却缺字段的路径。本条不改代码；原环境复测（明确区分冲突拒绝/显示失败/成功三类结果的字段完整性）继续开放，与 FEAT-044 的剩余矩阵一并验证。
