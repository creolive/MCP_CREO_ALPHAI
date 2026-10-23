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
