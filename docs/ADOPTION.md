# 继续编辑 Creo 中的现有模型

本页对应 FEAT-042 第二阶段与 FEAT-043（随 0.4.1 发布）及 0.4.2 的拒绝诊断增强（NO_CURRENT_MODEL、reason_code/refusal_details，87 工具）；0.4.5 起空窗口 NO_CURRENT_MODEL 在 Python 侧同为结构化拒绝、元数据读取超限返回 `ADOPTION_METADATA_BUDGET_EXCEEDED`（BUG-076 首批定位诊断）。0.4.0 及以前的历史验收保持原范围。

## 升级与发现

等待已受理任务结束，更新安装后重启客户端中的目标 MCP 连接器。调用 `creo_capabilities` 核对实际运行版本（0.4.2）、`runtime.server_entry`、`runtime.code_root`、启动源码指纹及 `source_changed_since_startup=false`，并确认工具清单含 `creo_list_session_models` 与 `creo_open_file`、接管 mode 含 `prepare`。发现来源变化时重启连接器；只修改配置不会替换已运行进程。

`creo_list_models` 返回本服务登记的模型；`creo_list_session_models` 返回已在 Creo 会话中的模型。后者默认20条、最多50条、每页32KiB，同一cursor读取十分钟内同次快照。返回名称/类型、`is_current`、`origin`、`has_saved_origin`、`modified`、可证明的 `model_id` 和原文件对应的 `adopted_copy_model_id`。无法确认的值为null，`query_codes` 保留原始诊断；`complete=false` 或 `truncated=true` 表示覆盖不完整。临时 `session_model_id` 仅用于发现，可能跨类型重复，不作为全局唯一或永久身份，也不用于选择接管对象；在Creo切到目标后使用正式预检返回的受管ID。`query_codes`只保留实际查询的诊断，0表示查询成功，不是modified=false；未查询/不适用的诊断项可省略（例如assembly不查询part的subtype），不要将缺失推断为0或失败。

枚举不自动打开或切换模型。请先在 Creo 激活目标窗口，再执行下面的接管流程。

## 已有保存文件的模型

调用 `creo_adopt_current_model`，省略mode即只读inspect。`available=true` 时检查返回的来源路径、哈希、类型及几何摘要；使用返回的model_id、evidence_token以及新的8～80字符幂等键执行apply：

```json
{"mode":"apply","model_id":"<inspect返回值>","evidence_token":"<inspect返回值>","idempotency_key":"adopt_saved_20261018"}
```

有文件但包含未保存修改的模型走同一流程，复制目标为inspect核对过的live状态。来源文件消失或不可读时明确失败，不能把该情况当作从未保存。

## 从未保存的新模型

inspect返回 `available=false`、`available_modes=["prepare"]`，没有可用model_id或令牌。准备步骤会创建受管副本，请显式调用：

```json
{"mode":"prepare","model_name":"managed_001","idempotency_key":"prepare_001_20261018"}
```

只轮询返回的 `job_id`。成功时stage为 `snapshot_prepared`，`result.adoption` 包含快照摘要、文件哈希、model_id和十分钟证据令牌。此时任务result.adopted=false，模型仍为 `adopt_pending`、revision=0；只有确认apply提交后才为adopted=true。prepare复制的是原生步骤开始执行时的当前窗口模型，不保存、改名或擦除原模型，完成后保留原窗口。

检查快照后确认：

```json
{"mode":"apply","model_id":"<result.adoption.model_id>","evidence_token":"<result.adoption.evidence_token>","idempotency_key":"confirm_001_20261018"}
```

确认后ready/revision=1，显示受管副本，可通过inspect取得真实特征/面/边引用后继续建模。确认使用已冻结快照，prepare之后对原模型的修改不会进入副本。确认不能更改已准备的副本名称。

令牌过期后使用 `{"mode":"inspect","model_id":"<快照ID>"}` 重新核验并续签，不再次复制。快照被改写则拒绝续签/确认。相同prepare幂等键返回原任务，参数不同拒绝；不同键代表显式创建另一份独立快照，不按名称推断原模型所有权。

检查原件变化时，先在 Creo 激活原件，调用 `creo_adopt_current_model({"mode":"inspect"})`，**省略model_id**。它检查当前窗口；从未保存的原件仍返回prepare指引和当前几何摘要，无登记ID/令牌。仅记录摘要，不再次prepare。

带model_id的续签检查已有快照的文件身份，返回的 `current_model` 沿用prepare时保存的来源摘要，不是对原件当前活体的重新读取。普通 `creo_inspect_model` 在adopt_pending时可能返回inspection_available=false；这表示该查询尚未提供几何，不能据此认定准备快照文件不存在。确认前用prepare/续签证据核对身份；apply成功后再用普通模型检查核对实际副本几何与保存重载结果。

## 失败与范围

首批支持独立part/钣金、毫米单位、无外部依赖、无失败/抑制/不完整特征。装配、工程图等类型明确拒绝。普通受管模型的origin、检查点、revision及unknown保护保持有效。

inspect 拒绝时除文本 `reason` 外携带稳定 `reason_code`（`unsupported_model_type` / `non_millimeter_units` / `external_dependencies` / `unhealthy_features` / `managed_output` / `already_adopted` / `snapshot_required` / `NO_CURRENT_MODEL`）与 `refusal_details`：报告实际长度单位（未知时 `actual_units=null` 并标记 `actual_units_known=false`）；依赖清单当前无法可靠取得，标记 `unknown` 并附合并口径说明，不补造细节。毫米、无依赖与健康的准入边界不变。`unhealthy_features` 拒绝携带原生健康扫描的有界逐特征诊断（FEAT-006，0.5.0 反馈计划第一批，开发分支待实机验收）：`refusal_details.unhealthy_features` 报告 `unhealthy_total`（真实不健康特征总数）、`returned`、`truncated` 与 `items`——每条含特征 `id`、`name`、`type_name`、`status_code`（原生 `ProFeatureStatusGet` 整码）、可读 `status` 标签与 `incomplete` 标记；原生侧只输出前 20 条，超出以 `truncated` 明示，完整特征清单仍在检查 sidecar。`status` 标签仅为可读性提示，SDK 枚举之外的整码标记 `unknown_status_code`，不猜测成因；执行器未提供该数据时 `health_breakdown` 保持合并口径"逐特征原因不可得"，不虚构明细。Creo 窗口无当前模型时返回 `NO_CURRENT_MODEL` 结构化拒绝（保留 `ProMdlCurrentGet` 调用名与 -8 原码，refusal_details 未知值如实标记），可先经 `creo_list_session_models` 查看会话清单；需要把磁盘既有模型放进会话时先用 `creo_open_file` 只读检入显示，再切换/接管。

收养元数据读取有 16 MiB 预算（BUG-076 定位诊断，0.4.5）：超限返回稳定原因码 `ADOPTION_METADATA_BUDGET_EXCEEDED`（同步错误为同一 JSON 文本与 structuredContent），携带 `metadata_kind`（native_result/model_registry/evidence_token/commit_journal 四类读取之一）、服务内相对路径、`actual_bytes`/`budget_bytes`、`failed_stage`、job/model 标识与恢复指引。失败预检 job 保留结构化诊断与超限文件本体供定位；错误收尾与轮询遇二次超限不覆盖原始诊断（`failure_read_budget_exceeded`/`commit_read_budget_exceeded` 附注）；预算错误不重放 native、不清保护。预检后段（来源核验/冲突扫描/令牌发布）失败在预检 job 上标注 `failed_stage`。不通过提高限额、跳过登记或删减核验消除报错；取得原环境超限文件类别后按对应读取路径精修。

[BUG-072](work-items/BUG-072.md)已在开发源码修正，尚待重启部署后的实机复验：inspection.units为查询到的模型长度单位，未知时为null，units_query_code保留查询诊断；只有确认毫米且数值有限时才提供volume_mm3。非毫米/未知单位的两层volume_mm3均为null，volume_query_code=0不代表已换算成mm³。坐标、半径等仍采用所示模型长度单位，不扩大非毫米接管支持。旧连接器可能仍返回原生体积误标mm³，需按本页入口核对启动身份后再采用新语义。

未确认模型不能普通建模或通过accept_saved/live绕过确认。需要放弃时使用 `creo_reconcile_model` 的inspect→`abandon_new`，保留文件和审计。派发后结果不确定则保持保护，先查询原job，不重交建模计划、不修改登记或清锁。单一Toolkit通道busy立即拒绝，受理后只轮询。

本轮实测范围见[第二阶段记录](work-items/FEAT-042.md)；Creo13外部环境未验收。开发者检查与[WorkBuddy黑盒场景](WORKBUDDY_ADOPTION.md)分别留证。
