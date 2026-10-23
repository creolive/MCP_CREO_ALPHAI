# FEAT-045：外部装配只读检查

日期：2026-10-20 登记。类型：功能。优先级：P2。状态：待规划。目标版本：未排期。

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

装配 walk 三处一致性修正：组件特征状态查询（`ProFeatureStatusGet`）失败置 incomplete，不再误称 complete；子模型身份查询码（name/origin/modified/id）合并保留进节点 `query_codes`，不再被覆盖丢失；局部原始矩阵查询成功但含 NaN/Infinity 时 `transform_known=false` 且原始矩阵为 null（原因 `non_finite`），经共用 helper `local_transform_known` 与根链同一有限语义。证据阶段：离线原生 24-case 与 Python 8 tests 已实跑通过，离线生产构建 exit 0；新增 case 25–27 尚待控制者运行，全量 dev_check 待短路径 checkout；实机/WorkBuddy 未验收，修正涉及的生产失败分支未实机触发。

## 2026-10-23 BUG-080 审查 Important 修复（walk 状态共享化，待控制者运行）

walk 状态/判定/节点写入逻辑提取至共享 `native/assembly_walk.h`（`AssemblyWalkState`：`record_missing_component` 自盖缺件标志、`apply_query_outcome` 真实查询码驱动置 incomplete、`visit_subtree` 深度 32 先判限再执行访问且失败码写实际节点 `node_index`、`init_root_chain` 真实 root_scale 初始化根链并置 incomplete、`complete` 统一规则，budget=4096/深度 32 契约不变）；`generic.cpp` 生产回调改经同一实现。新增离线夹具 `tests/native/test_assembly_walk.cpp`（12 case，SDK 查询替换、注入 visitor 计数非真实 ProSolidFeatVisit）由 `tools\test_assembly_units.py` 同批构建运行（已修正 native 包含路径引号），覆盖缺件标志由生产操作产出/真实零非零查询码逐个驱动/深度 31–33 真实调用次数与父节点索引诊断/budget 边界/根失败保同级/根单位经真实换算由共享初始化影响链与 complete。尚待控制者运行该夹具并复编生产构建；实机触发与 WorkBuddy 仍按卡保留未验收。
