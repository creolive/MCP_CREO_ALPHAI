# FEAT-044：磁盘原生模型检索与显示（creo_open_file）

日期：2026-10-20 登记。类型：功能。优先级：P1。状态：验收中。目标版本：0.4.2（用户 2026-10-20 指定 PATCH，含新增工具，按约定本应为 MINOR，作为例外；已交付）。

来源：[v0.4.1 / Creo 10 反馈](../validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md)（P0）及关联 v0.4.0 报告。属新增能力需求，非回归修复。实施安排见[处理计划](../development/CREO10-0.4.1-FEEDBACK-PLAN.md)。

## 当前进度（2026-10-21）

0.4.2磁盘打开及WorkBuddy黑盒16/16已交付，0.4.4补钣金件、显式.asm.N与窗口目视验收；0.4.5新增opened_session_model单句柄观察，开发者实机通过，见[实施证据](../validation/BUG076-FEEDBACK042-2026-10-21.md)。下方早期“钣金/数字版本/WorkBuddy待执行”仅属当时状态。

仍需asm_mx.asm.16原环境复验、显示失败/unknown/真实并发，以及新增打开结果字段的WorkBuddy复核；不以已发布替代这些验收。

## 目标与范围

提供 `creo_open_file(file_path, idempotency_key)`：把磁盘既有 `.prt` / `.asm`（含 `.prt.N` / `.asm.N` 数字版本）检索进当前 Creo 会话并显示激活。这是**只读检入显示**，不建立受管关系：成功返回 `model_id=null`、`adopted=false`，不创建受管 revision。托管收养仍走 `creo_adopt_current_model` 既有契约；装配受管编辑与 reconcile 另期（FEAT-045）。

## 接口契约

- 接受 Windows 本机绝对路径；扩展名限 `.prt` / `.asm`，可带 `.` + 十进制数字的显式版本。
- 显式版本只打开指定文件；省略版本时在同目录选择最高数字版本，无任何数字版本才使用无后缀文件。同数字版本出现多个大小写不同的磁盘条目等歧义时拒绝，不猜选。
- 提交后立即返回 `job_id`；通过 `creo_get_job` 轮询终态。复用单通道 busy、幂等与 unknown_outcome 契约，不排队、不自动重试、不自动重放。
- 幂等：同一 `idempotency_key` 重放返回原 job；同 key 换参数拒绝。
- 返回：请求路径、选定文件路径及身份（sha256/size）、实际 origin、模型类型（part/sheetmetal/assembly）、会话指纹、加载与显示结果、会话内剩余对象观察。

## 保护措施

- 会话存在同名同类型模型时拒绝；装配另要求加载前会话没有任何零件或装配；会话枚举无法完成也拒绝。检查与加载在同一 Toolkit 通道内一次执行。
- 原生流程：完整路径检索（`ProMdlFiletypeLoad`）、立即检查检索错误、核对模型类型、显示并激活。子组件解析沿用 Creo 当前搜索规则，不修改搜索配置。
- 装配检索不完整（缺件）时报告明确失败及可能残留的会话对象；缺件清单无法取得时明确标记未知。加载成功但显示失败分别报告，不互相掩盖。
- 不自动保存、覆盖、擦除、重命名或接管源模型；源文件身份在提交与收尾各记录一次，执行期间变化如实标注，不视为加载失败也不回滚。
- 超时、断连或结果不完整沿用 `unknown_outcome`，保留证据，禁止自动重放。
- 新业务实现放包内（`creo_mechdog/open_file.py`），补齐任务分发（bridge run-job）、轮询摘要（compact）、源码指纹与打包覆盖。

## 验收标准

| 场景 | 可判断的预期结果 |
| --- | --- |
| 零件打开 | 存量 `.prt` 检索成功、显示激活；返回 origin/类型/会话指纹；`model_id=null`、`adopted=false`；源文件字节与保存版本不变 |
| 完整装配打开 | 空会话下 `.asm` 全组件检索并显示；`asm_mx.asm.16` 场景保持“待原环境复验”，以本机完整装配样件为准 |
| 缺件装配 | 明确失败；报告可能残留的会话对象；无法取得缺件清单时标记未知 |
| 显示失败 | 加载与显示结果分别报告；不误报整体成功 |
| 数字版本 | 同目录几何不同的 `.1/.2`：省略版本选最高；显式 `.1`/`.2` 打开指定版本；歧义拒绝 |
| 同名冲突 | 会话已有同名同类型模型时拒绝，不加载 |
| 非空会话装配拒绝 | 会话存在零件/装配时 `.asm` 拒绝；枚举失败也拒绝 |
| 路径与非法输入 | 中文及空格路径可用；相对路径、非 `.prt/.asm`、不存在文件、非法版本后缀拒绝 |
| 提交后文件变化 | 收尾身份对比如实标注，不静默 |
| 幂等与 busy | 同 key 重放返回原 job；同 key 换参数拒绝；通道忙碌立即拒绝并携带 blocking_* |
| unknown 结果 | 超时/断连置 unknown_outcome 保留证据，不自动重放 |
| 协议回归 | 单元测试覆盖上述 Python 侧分支；compact/full 一致 |

开发环境 Windows x64 / Creo 12.4 / 匹配 SDK。实机验收按 BUG-001 联调约束先确认会话可操作。WorkBuddy 黑盒提示词另备（见验证记录），只记录实际调用、任务终态、Creo 显示与公开字段。

## 实现与证据

2026-10-20 实现并完成本机 Creo 12.4 实机验收，证据见[验证记录](../validation/FEAT-044-live-2026-10-20.md)：

- 实现：包内 `creo_mechdog/open_file.py`（版本选择/幂等/任务收尾）、native `open_file_native`（同通道前置检查+检索+核对+显示）、bridge run-job 分发与 compact 摘要、server `creo_open_file` 工具、capabilities `disk_open` 族、源码指纹与 `.gitignore` 覆盖。
- 离线：432 项单元（新增 21）、dev_check、SDK 构建通过。
- 实机 12 场景全过：完整/缺件装配、显式与最高数字版本、同名冲突、非空会话装配拒绝、中文空格路径、幂等重放、非法输入、身份前后一致。
- **关键发现**：`ProMdlFiletypeLoad` 对缺件装配不报错（组件静默缺失）；已补组件完整性核对（`ProSolidFeatVisit`+`ProAsmcompMdlGet`），缺件时 `RETRIEVE_INCOMPLETE` 明确失败并报告残留与 unknown 缺件计数。
- 剩余：`asm_mx.asm.16` 原环境复验、显示失败注入、unknown/并发、钣金件打开、`.asm` 数字版本选择、WorkBuddy 公开黑盒复验待执行（[提示词](../WORKBUDDY_0.5.0_OPEN_FILE.md)）。

## 2026-10-21 补验收：钣金件、显式 .asm.N 与窗口目视

按[完善计划](../development/CREO10-0.4.1-FEEDBACK-IMPROVEMENT-PLAN-2026-10-20.md)第 3 节补齐（stdio 直连驱动 `build/dev044_openfile.py`，wbopen_* 白名单素材）：

- **钣金件打开**：受管钣金 `wbopen_sm01.prt.5` → succeeded、model_id=null、adopted=false、model_type=sheetmetal、displayed=true。
- **显式 `.asm.N`**：`wbopen_asmv.asm.4`=2 组件、`.asm.6`=3 组件，均 succeeded/displayed=true/origin_matches_selected_file=true，打开前后副本 SHA 不变。
- **窗口目视**：PrintWindow 只读截图，窗口标题 "WBOPEN_ASMV (启用的) - Creo Parametric 12"，图存 `build/dev044_visual_final.bmp`。
- 残留：SM_FLANGE1 两个 section 对象（失败 plan 遗留，非 PART/ASM 不阻塞）；`asm_mx.asm.16` 原环境、显示失败注入、unknown/并发维持未测。详见[验证记录](../validation/DEV-027-030-IMPROVEMENT-2026-10-21.md)。

### 2026-10-21 loaded_session_models 摘要

按[0.4.3 反馈完善计划](../development/0.4.3-feedback-improvement-plan-2026-10-21.md)实施（分支 `codex/dev-043-ledger-simplification`，[实施记录](../validation/FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)）：`creo_open_file` 成功结果新增 `open_file.loaded_session_models`（会话模型数、本次装配打开的组件实例数及统计口径、有界 20 条页、has_more 与 `creo_list_session_models` 详情入口），显示成功后一次全量枚举生成；`SESSION_NAME_CONFLICT` 消息补充装配依赖加载来源提示。既有测试通过；剩余实机装配打开观察与原环境验收。

## 2026-10-23 外部 Creo 9 证据补录（第八轮，2026-10-25 归档登记）

- 外部第八轮：`creo_open_file` 同名冲突正确拒绝（`SESSION_NAME_CONFLICT`，文件未打开）；成功路径返回 display_name/displayed/loaded、opened_session_model、源文件 identity_before/identity_after 与 source_file_changed_during_open；`model_id: null`、不创建受管模型——符合只读检索承诺。归档见 [feedback-0.5.0-0.5.1-2026-10-23](../validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)。
