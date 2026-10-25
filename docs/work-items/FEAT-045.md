# FEAT-045：外部装配只读检查

日期：2026-10-20 登记。类型：功能。优先级：P2。状态：验收中（只读检查已随 0.5.0 交付并通过本机/外部主线；四类受限场景与 WorkBuddy 按卡保留）。目标版本：0.5.0。

来源：[v0.4.1 / Creo 10 反馈](../validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md) P1-2 及 v0.4.0 报告 §3.4 建议 2。实施边界见[处理计划](../development/CREO10-0.4.1-FEEDBACK-PLAN.md)第 5 节。

## 目标与现状

对外部装配（如经 FEAT-044 检入显示的 `.asm`）提供**只读**检查能力：组件树、per-component transform 与放置/约束快照，满足"打开 + 审计"需求。当前装配既不能收养（adopt 拒绝 assembly/drawing）、也不能通过 reconcile 恢复，写操作继续排除。

## 范围与前置

- 依赖 FEAT-044 落地后的会话装配观察；不含任何写路径。
- 开放装配受管编辑时，必须同时设计恢复链路（reconcile 覆盖），否则装配托管将成为"只进不出"的单向门。
- 设计前核对 Toolkit 装配遍历/约束读取 API 的实际可得字段，未知项如实标记。

## 验收方向（待细化）

只读枚举组件树与 transform 不改变会话；缺件/失败装配的报告语义与 FEAT-044 一致；不产生受管 revision；WorkBuddy 黑盒可验。

## 实现与证据

2026-10-20 仅登记，未实施。

## 2026-10-22 实施与本机实机验收（主线通过）

[实施与验收记录](../validation/FEAT045-ASSEMBLY-INSPECT-2026-10-22.md)（分支 `codex/feat045-assembly-inspect`，目标 0.5.0 MINOR，工具数 90→91）：新增 `creo_inspect_session_assembly`——按名称选定驻留装配，树序返回组件 occurrence/parent 路径、来源/加载/抑制/封装状态、约束快照（含引用尽力解析与原始查询码）、4×4 行向量解算变换（到父级+累积到根，平移末行，毫米）；首采单通道忙拒+10 分钟冻结快照分页 32 KiB；只读五不原则。单元 5 项+全量 544 项+dev_check 过；本机 Creo 12.4 实机：托管链与外部装配（open_file 载入）检查均通过，变换末行与放置平移逐位一致，fix 约束快照、分页无重无漏、结构化拒绝、会话不变。

崩溃修复：`ProMdlMdlnameGet` 缓冲须 `ProMdlName`（80）误用 `ProName`（32）致栈溢出；`ProAsmcompConstraintsWithComppathGet` NULL path 在 Creo 12 崩溃，改构造 owner comppath。

未验证（按卡保留）：嵌套子装配/重复实例/抑制/缺件四场景实机触发（本机构造手段受限，native 路径与单测覆盖，外部环境复测定论）、外部 Creo 10 复核、WorkBuddy 黑盒。矩阵放置/重建编辑/整体收养为后续路线单列（见记录末节）。

## 2026-10-23 0.5.0 反馈补录：外部单层检查复核

[0.5.0 验收报告 §3.1](../validation/feedback-0.5.0-2026-10-22/2026-10-22_CREO10_v0.5.0_FEAT045交付与死锁根治但变换单位存疑.md)（外部 Creo 10 / 0.5.0）：`creo_inspect_session_assembly(ASM_MX, limit=5)` 8 组件树序、occurrence/parent 路径齐备、双份 4×4 行向量变换（平移末行）、逐约束快照（align/mate/orient/align_offset + 双侧 item_id/item_type/occurrence_path/offset）、分页 `complete/truncated/incomplete` 三态与 600s 过期——**外部 Creo 10 单层装配复核子项通过关闭**。嵌套子装配/重复实例/抑制/缺件四场景实机触发与 WorkBuddy 黑盒仍按卡保留；变换数值单位疑点归 [BUG-080](BUG-080.md)，矩阵直入参建议归 FEAT-012/BUG-045。

## 2026-10-23 BUG-080 联动：变换单位契约修正

变换字段口径随 [BUG-080](BUG-080.md) 修正：`transform_to_parent`/`transform_to_root` 为规范化毫米完整坐标映射，`transform_to_parent_raw`/`transform_to_root_raw` 保留原始矩阵；每节点 `units.component`/`units.parent` 与装配 `length_unit` 携带真实单位名称、查询码与毫米比例；未知单位/变换时规范化矩阵为 null（`transform_unknown_reason`）并使完整性标志如实反映（新增 `depth_limited`/`root_visit_code`/缺件 `subtree_not_visited`）。同单位场景下规范化结果与旧毫米输出一致。实机混合单位验证与四受限场景按 BUG-080/本卡保留，不随本次关闭。

## 2026-10-23 BUG-080 开发验证修正（待独立审查）

装配 walk 三处一致性修正：组件特征状态查询（`ProFeatureStatusGet`）失败置 incomplete，不再误称 complete；子模型身份查询码（name/origin/modified/id）合并保留进节点 `query_codes`，不再被覆盖丢失；局部原始矩阵查询成功但含 NaN/Infinity 时 `transform_known=false` 且原始矩阵为 null（原因 `non_finite`），经共用 helper `local_transform_known` 与根链同一有限语义。证据阶段：离线原生 case 1–27 与 Python 8 tests 已实跑通过（947f40e exit 0），离线生产构建 exit 0；947f40e 短路径全量 557 项单测与统一 dev_check 通过（success=true）；实机/WorkBuddy 未验收，修正涉及的生产失败分支未实机触发。

## 2026-10-23 BUG-080 审查 Important 修复（walk 状态共享化）

walk 状态/判定/节点写入逻辑提取至共享 `native/assembly_walk.h`（`AssemblyWalkState`：`record_missing_component` 自盖缺件标志、`apply_query_outcome` 真实查询码驱动置 incomplete、`visit_subtree` 深度 32 先判限再执行访问且失败码写实际节点 `node_index`、`init_root_chain` 真实 root_scale 初始化根链并置 incomplete、`complete` 统一规则，budget=4096/深度 32 契约不变）；`generic.cpp` 生产回调改经同一实现。新增离线夹具 `tests/native/test_assembly_walk.cpp`（12 case，SDK 查询替换、注入 visitor 计数非真实 ProSolidFeatVisit）由 `tools\test_assembly_units.py` 同批构建运行（已修正 native 包含路径引号），覆盖缺件标志由生产操作产出/真实零非零查询码逐个驱动/深度 31–33 真实调用次数与父节点索引诊断/budget 边界/根失败保同级/根单位经真实换算由共享初始化影响链与 complete。该夹具 12 case 与生产复编已实跑通过（947f40e exit 0；SDK 查询替换、注入 visitor 非真实 ProSolidFeatVisit，不声称实机/完整 callback 几何覆盖）；实机触发与 WorkBuddy 仍按卡保留未验收。

## 2026-10-23 外部 Creo 9 证据补录（第八轮，2026-10-25 归档登记）

- 环境：外部 Windows 10 / Creo 9.0.0.0（release 41）/ 服务 0.5.0；单组件装配（报告者称"本版质量标杆"）。
- 通过子项：组件清单含 occurrence 路径、depth、类型、origin/has_saved_origin/modified/is_current/session_model_id、resolved/suppressed/packaged 与逐项 query_codes；约束快照（mate+align+align 全部解析 code 0，含双侧引用与 comppath、offset、orientation）；`transform_to_parent`/`transform_to_root` 完整 4×4 与行向量约定说明；冻结快照（10 分钟）+ 游标 + readonly_note（只读五不）；重复实例分别记录声明。
- **单组件装配检查正例补录**；多组件分页（limit=1 + next_cursor）未实测，嵌套/抑制/缺件场景未覆盖。
- 数值的毫米声明须结合 [BUG-080](BUG-080.md) 单位契约核对（该报告数值呈 x/25.4 特征，BUG-080 已随 0.5.2 交付修复并黑盒复验）。
- 后续小修（0.5.3）：`capabilities.support_status.assembly_checks` 仍写 planned/not available(FEAT-045)，与已交付且外部实测可用的 `creo_inspect_session_assembly` 矛盾，须同步为只读及受限场景的准确状态。归档见 [feedback-0.5.0-0.5.1-2026-10-23](../validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)。

## 2026-10-25 0.5.3 阶段三小修：support_status 状态对齐

分支 `codex/chores053-wording`。`server.py` 的 `support_status.assembly_checks` 由 planned/not available 修正为 `supported_limited`，`tool` 指向已发布的 `creo_inspect_session_assembly`：summary 明确只读范围（树序组件、逐约束快照、毫米规范化+原始 4×4 变换、未知单位为 null）、嵌套子装配/重复实例/抑制/缺件四类受限场景按节点报告但参考机未实机触发，以及无写路径（不加载/激活/保存/收养/受管 revision，装配收养与 reconcile 仍拒绝）。整体装配收养未宣称支持；变换单位口径只在描述本工具返回时陈述，毫米契约以 [BUG-080](BUG-080.md) 卡为限。

核对结果：`capabilities.py` 的 `session_assembly` 家族登记与 `creo_inspect_session_assembly` 工具描述本已准确，未改动；compact 与分节返回经 capability_pages 携带同一 `support_status` 载荷，随本次修正自动一致；工具清单由注册驱动，无需变更。新增 `tests/unit/test_support_status.py` 3 项单测锁定状态、工具名与 capabilities 登记一致及不得回退为"not available"。本项为状态字段/文案修正，无行为改动，未重复实机与 WorkBuddy；dev_check 通过（本机 `build/development_check.json`，生成物不入库）。

## 2026-10-25 阶段三验收证据（收口）

集成尖 `e2bba08`（含 `0729fee` 小修），受测指纹 `checked_source_sha256=da558d9e…b28b5f0`；环境 Windows 11 x64 / Creo 12.4.0.0 / 匹配 SDK / Python 3.12.14，见[阶段三收口](../validation/PHASE3-CLOSEOUT-2026-10-25.md)。

- 实现摘要：`server.py` 的 `support_status.assembly_checks` 改为 `supported_limited` 并指向 `creo_inspect_session_assembly`，明确只读（树序组件、逐约束快照、毫米规范化 + 原始 4×4、未知单位为 null）与四类受限场景按节点报告；无写路径、装配收养与 reconcile 仍拒绝。`capabilities.py` 家族登记与工具描述已准确，未改。
- 本次证据：离线全量 612 项单测通过（含 `test_support_status.py` 3 项）、`tools/test_unit.py` exit 0、`tools/dev_check.py` exit 0（success=true）、`bridge.py build` exit 0；本卡为状态字段修正，未重复实机装配检查。
- 未测范围：嵌套子装配/重复实例/抑制/缺件四场景实机触发、WorkBuddy 黑盒仍开放；整体装配收养、矩阵放置与重建编辑仍属后续路线，不因本次文案对齐而宣称支持。
