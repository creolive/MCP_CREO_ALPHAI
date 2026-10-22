# MCP_CREO_MechDog 0.5.0 版本说明（开发分支，未发布）

日期：2026-10-22。本次为 0.4.6 反馈整合计划第二批（MINOR，新增公开工具，按现行 MINOR 规则不延用 0.4.6 的 PATCH 例外）。基于 0.4.8，工具数 90→91。

## 变更

- **FEAT-045 装配只读检查**：新增 `creo_inspect_session_assembly(name, limit=20, cursor=None)`，按名称选定已驻留装配（从 `creo_list_session_models` 选择），只读返回：
  - 树序组件清单，每项含 occurrence 路径（根到该组件的特征 id 序列）、父路径、depth、名称/类型（part/sheetmetal/assembly）、origin/has_saved_origin/modified/session_model_id/is_current（与 `creo_list_session_models` 条目同构，未知为 null+query_codes）、`resolved`（组件未解析如缺件时 false 并保留节点）、`suppressed`（含族表/简化表示/程序抑制）、`packaged`（封装放置）。
  - 约束快照：每条约束的 type（fix/mate/mate_offset/align/align_offset/insert/orient/csys/tangent/pnt_on_srf/edge_on_srf/default/auto）、offset、orientation（yellow/red/none）、装配侧与组件侧引用（经 comppath/modelitem 尽力解析，失败为 null+原始查询码）。
  - 完整 4×4 解算变换：`transform_to_parent`（成员→所属装配）与 `transform_to_root`（成员→受检根装配，嵌套累积）；行向量约定（p' = p × M），平移位于最后一行，单位毫米；响应内附约定说明。
  - 首次采集使用单一 Toolkit 通道（忙即拒绝）；分页读取同一份十分钟冻结快照，32 KiB 响应预算，游标防篡改（kind/snapshot/fingerprint/name/offset），过期或会话选择变化拒绝。
  - 只读五不原则：不加载组件、不切换当前模型、不再生、不保存、不收养，不创建受管 revision。
- 缺件、抑制与单节点查询失败逐项标记（含 `subassembly_visit_code`、整体 `complete/truncated/incomplete` 标志），不因单点失败毁整份报告。
- 实施中修复两处 native 崩溃：`ProMdlMdlnameGet` 输出缓冲必须为 `ProMdlName`（80 宽字符），此前误用 `ProName`（32）导致栈溢出；`ProAsmcompConstraintsWithComppathGet` 传 NULL comppath 在 Creo 12 崩溃，改为始终构造 owner comppath。

## 用法与兼容

`creo_inspect_session_assembly(name="ASM_MX", limit=50)` 一次读全（预算内），或 `limit=2` 翻页直至 `next_cursor=null`。游标页不重新采集；省略 cursor 重新采集。装配编辑/收养不属于本工具：矩阵放置、受限重建与装配整体收养为后续路线（见 [验收记录](validation/FEAT045-ASSEMBLY-INSPECT-2026-10-22.md) 后续路线节）。

## 验证与未测

见 [FEAT-045 实施与验收记录](validation/FEAT045-ASSEMBLY-INSPECT-2026-10-22.md)：单元 5 项（树序/重复实例分别记录/游标五类拒绝/分页预算/busy 与失败不建 job）+全量 544 项+dev_check 通过；本机 Creo 12.4 实机——托管链与外部装配（open_file 载入）检查均通过，变换末行与放置平移逐位一致（[50,0,0]/[10,10,5]），fix 约束快照、分页无重无漏、结构化拒绝、会话不变。未验证如实保留：嵌套子装配/重复实例/抑制/缺件四场景的实机触发（本机构造手段受限：assemble_component 不支持嵌套插入、受管插入即复制快照、无抑制工具、缺件 fixture 被搜索路径解析；native 路径与单测覆盖，外部环境复测定论）、外部 Creo 10 复核、WorkBuddy 黑盒（提示词见 [WORKBUDDY-0.5.0-FEAT045](development/WORKBUDDY-0.5.0-FEAT045-2026-10-22.md)）。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1，待排期）不变：恢复 accept 路径 `ProMdlnameBackup` 稳定 -1，`accept_saved`/`accept_live` 实机不可用；三个 dirty 现场模型保护挂起待修复收尾。
- BUG-077 原环境（track_p01b 21.4MB）迁移复测与 485 条真实旧登记批量迁移继续开放。
