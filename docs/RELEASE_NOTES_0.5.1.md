# MCP_CREO_MechDog 0.5.1 版本说明

日期：2026-10-23。本次为编辑链路缺陷修复批次（PATCH，无新增公开工具，工具数 91 不变）。基于 0.5.0。

## 变更

- **BUG-062 `update_sketch_geometry` 支持构造中心线**：回转草图不再"天生不可就地编辑"。含 centerline 的截面可整体传入就地编辑；centerline 以保留实体身份的方式重建，维持回转轴引用。缺实体、改名、改类型仍按既有规则准确拒绝并干净回滚。
- **BUG-030 同几何重复提交守卫修正**：同一几何重复提交的 `unchanged` 快捷路径在"先经尺寸编辑/参数驱动、再提交原几何"以及标注模式切换后不再错误跳过——守卫只在当前原生几何与提交几何逐类型一致时生效，改动仍按保护策略落地、再生并保存重载核验。同几何重复提交返回 `unchanged=true` 且 revision +1（既有语义不变）。
- **BUG-029 `reorder_features` 槽位与校验修正**：目标槽位按原特征树编号解释并沿方向折叠；非连续特征集合被拒绝；就地无操作请求仍创建任务并使 revision +1，不重排特征。
- **BUG-079 就地修改圆弧半径修复**（P1，WorkBuddy 黑盒验收暴露）：此前任何圆弧半径变化（回转与拉伸上下文）都会导致草绘特征再生失败并回滚。根因：就地重建后 autodim 在半径变化截面上欠约束（缺位置尺寸），残留孤儿特征尺寸使 REV_SK 再生失败；`SKETCH_SOLVE=-1` 无诊断条目为伴生现象而非判别点。修复：
  - 未变实体直接跳过（保持实体 ID），变更实体删除后重建并回写新 ID；centerline 保留 Replace 路径以维持回转轴引用；
  - `dimensioning=auto` 的就地编辑在主平面、实体类型全部支持坐标标注（line/centerline/circle/arc）且截面存在坐标系时，改走完全约束的坐标尺寸路径（显式 `autodim` 请求、非主平面、含 ellipse/spline 的截面仍走原 autodim 路径）；
  - 附带规避 MSVC 传统 lambda 处理器（/std:c++17）的捕获登记缺陷（C2065），不影响行为。

## 兼容与迁移

- 无接口变化、无新增/停用工具。客户端无需修改。
- 就地编辑后的截面尺寸符号不再保证沿用旧编号（坐标尺寸路径整体重映射，如 d12 起）；需要引用截面尺寸时先经 `creo_inspect_model` 重新查询，不要缓存假设。
- 同几何重复提交在"尺寸值已被改回"的场景下现在返回 `unchanged=true`（此前可能错误地按改动处理）。

## 验证与未测

- 开发侧（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC）：编辑专项 `tools/test_editing_closeout.py` 全套 11 项通过（新增 `arc_radius_inplace_edit`：回转 R5→R6→R5，体积 200π²/288π²、特征 ID 保持）；BUG-062 夹具两入口（含三拒绝路径与失败后合法编辑）通过；`wb-r6-repro.py` 变体 C/D、`wb-r6-extrude.py`、`wb-r6-coords.py` 通过；`tools/test_general.py` 通过；`tools/dev_check.py` 通过（554 单测，无新增语言回归）。受测源码提交 `e1e67ee`，执行器 SHA256 `a66ff88c…`。
- WorkBuddy 黑盒复验（MCP_CREO_MechDog_dev，服务 0.5.0 修复构建，Creo 12.4.0.0）：回转就地改弧半径 R5→R6→R5（1973.9209→2842.4461→1973.9209，revision 递增，`preserved_feature_id=40`，特征 ID 保持）、同几何重复 `unchanged=true`、拉伸上下文修正剖面后 R5→R6（78.5398→113.0973）均通过；两次失败输入均干净回滚。复验表见 [BUG-079](work-items/BUG-079.md)。
- 未测范围（如实披露）：Creo 9 / Creo 10 实机未测（按 2026-10-15 用户决定不作为发布门槛）；并发能力维持 [BUG-009](work-items/BUG-009.md) 记录的边界（单通道忙拒，无队列）；BUG-058 外部 -11 待复现；WorkBuddy 未实施并发调用。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1）：恢复 accept 路径 `ProMdlnameBackup` 稳定 -1。根因已定位为损坏会话级（建模/恢复代码零改动，健康会话实机闭环通过），三个历史 dirty 现场仅 `restore_baseline` 可用，收尾动作待操作者选择。
- [BUG-058](work-items/BUG-058.md)（P1）：外部无主窗口 -11 待复现；本机同码 -4 已定位客户端侧 RPC 端点自举端口错位。
- [BUG-063](work-items/BUG-063.md)/[BUG-064](work-items/BUG-064.md)（P1）：非原点轴阵列、surface 平面引用与纯 Z 向 u_axis 两条拒绝路径待复现。
