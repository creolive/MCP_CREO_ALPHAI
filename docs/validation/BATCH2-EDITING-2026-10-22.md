# 第二批编辑子批（BUG-062 / BUG-030 / BUG-029）实机验收记录

日期：2026-10-22（下午）。开发者侧实机验证，分支 `codex/bug062-editing-batch2`，基线 main `6d360a4`（0.5.0）。

## 环境

- Windows x64 / Creo 12.4.0.0（release_numeric 44）/ E 盘 dev 服务 `MCP_CREO_MechDog_dev` 0.5.0 / 会话指纹 `13822995897450650751`（健康会话，trail 零 dbg_err_crash，见 BUG-078 记录）
- 夹具脚本：`build/bug062/verify.py`、`build/bug030/verify.py`、`build/bug029/probe.py`、`build/bug029/accept.py`（各自防重复执行；报告 JSON 留存同目录）
- 全部新建隔离模型；未触碰三个 BUG-078 挂起现场

## 1. BUG-062：centerline 就地编辑

- **改前复现**：`SketchGeometryOp` 含 centerline 被 schema 拒绝（`In-place editing supports line, polyline, rectangle, circle, arc, ellipse and spline`，src/creo_mechdog/schema.py:269）；省略中心线的 native 拒绝路径（`must retain every named sketch entity`）为设计保护、保持不变。
- **修复**：允许集合加入 `centerline`，错误消息与 `creo_update_sketch_geometry` 工具说明同步；原生编辑器既有 `PRO_2D_CENTER_LINE` 分支（native/sketch_edit.cpp）零改动。
- **实机验收**（bug062_rev_c/rev_e 独立工具、rev_d/rev_f 计划入口）：
  - XY 面 R5 上半圆+直径线+水平中心线 revolve 360°：体积 `500π/3=523.5988` mm³ ✓；
  - 全量更新 R6（centerline 保持 centerline）：体积 `288π=904.7787` mm³、bbox 三向 12 mm ✓，`profile`/`ball` 特征 ID（40/50）保持，revision 1→2 仅一次，`saved_file_reloaded_and_verified=true`，两入口几何与 ID 布局一致；
  - 负面三例（省略 axis、改名、centerline→line）分别在 native 准确拒绝（`must retain`/`cannot rename`/`Entity type cannot change`），失败后模型 revision 保持，随后计划入口合法编辑（R6→R5）成功 rev 2→3。
- 单测：`tests/unit/test_sketch_geometry_edit.py` 4 项（接受 centerline、计划入口同构、第二条 centerline 拒绝、命名唯一）。
- 范围保持：未引入 `preserve_unlisted`，未扩约束能力，全部命名实体保留语义不变。

## 2. BUG-030：同几何替换的再生失败

- **复现（修复前）**：20×10 矩形+拉伸 4（体积 800）模型上，同几何矩形替换失败：`failed_stage=execute_update_sketch_geometry`、`Regeneration produced a failed, suppressed or incomplete feature`、`toolkit_code=-1`、`failed_toolkit_call=null`、rollback 成功体积回 800——与 0.3.1 原报告 job `7225624f8fe2` 同现象。**边界**：裸独立草图同几何替换成功；宽度 20→25 的替换成功——失败集中于"同几何+下游特征"组合。
- **根因**：byte-identical 的 `ProFeatureRedefine` 把草图与下游特征标记为 `PRO_FEAT_UNREGENERATED(6)`（active-but-unregenerated，UNHEALTHY_FEATURES 日志佐证：RECT_SK 与 PAD 均 status=6）；`ProSolidRegenerate(PRO_REGEN_NO_FLAGS)` 与 `PRO_REGEN_FORCE_REGEN` 均不清除该状态；inspection 健康检查按设计拒绝。中途试过"检测 UNREGENERATED 后强制再生"方案，实机证明 FORCE 亦无效后放弃。
- **修复（native/sketch_edit.cpp）**：`generic_sketch_edit` 开头对与登记几何 byte-identical 的实体集直接跳过原生改写（特征树不动，操作结果标记 `unchanged`），作业仍走完整保存/擦除/重载验证——同几何替换交付为成功作业（revision +1，符合"本批不新增同几何无修改优化"的计划语义）；非同几何路径零改动。
- **修复后矩阵**（bug030_gx1/gx2/gx3）：同几何替换 succeeded、体积保持 800、rev 1→2、ID 保持；宽度 25 体积 1000、bbox 25×10×4；计划入口同结果；裸草图同几何成功；`stale revision` 与退化矩形（min=max）均确定性拒绝（schema 层 `Rectangle max must exceed min`）；拒绝后合法编辑成功 rev→4。
- 原报告另例（改尺寸失败 job `0bc48959c8bd`）本机未复现（尺寸变化路径全过）；原环境为 Creo 10.0.0.0/release 42，差异保留，不据此关闭历史现象。

## 3. BUG-029：特征重排

- **定位**：探针（bug029_probe/pr2）实测 SDK 语义：`ProFeatureWithoptionsReorder` 的 `new_feat_num` 是**移除移动集合后**树中的插入槽位——原实现 `before=number(anchor)-1 / after=number(anchor)` 在两个方向上各有一种情形错位一格（探针中 `[dtp2] before dtp1` 把 dtp2 落到了 disk_solid 之前）。同时 SDK 文档要求 `feat_ids` 为**连续**特征集合；原报告两个拉伸之间隔有特征（草图等），非连续输入直接 `PRO_TK_BAD_INPUTS(-2)`，即原报告的三次 `-2` 失败。
- **修复（native/placement.cpp）**：`generic_reorder` 基于 `top_feature_order` 做顶层特征连续性校验（非连续、非顶层、锚点重叠、重复目标均前置拒绝）并按缩减树计算槽位（`before=锚点缩减序号`、`after=锚点缩减序号+1`）。
- **实机验收**（bug029_ac2：disk 拉伸+三个独立基准面）：5 个正例全部树序精准符合请求（`[dtp2] before dtp1`、`[dtp2] after dtp1`、连续对 `[dtp2,dtp3] before dtp1`、原生 ID 引用、计划入口），体积 `100π` 与 bbox `[10,10,4]` 全程不变、特征 ID 全程保持、每步 rev+1、保存重载通过；6 个负例（草图移到其拉伸后=依赖冲突、未知 label、重复目标、目标=锚点、非连续集合、stale revision）全部准确拒绝，拒绝后树序与 revision 不变，随后合法重排可用。
- 计划步骤 2（重构原报告两拉伸核对依赖）以等价的"草图→拉伸"依赖冲突负例覆盖（同构依赖关系），原模型输入未交付故不重建原件。

## 4. 回归与完整性

- 全量单测 548 全过（含新增 4 项）；`tools/dev_check.py` 对四个改动文件要求整体格式化（项目规则：改动文件必须过格式器），格式化与功能提交分离处理。
- 原生核心回归 `tools/test_general.py` `GENERAL_CORE_SUCCESS=1`（7/7：草图/拉伸/尺寸/计划/体积与 bbox 断言/plate）。
- BUG-062 场景在 BUG-030/029 native 改动后复验（bug062_rev_e/rev_f）全部通过。
- 构建为匹配本机 SDK 的重编译产物；`native/constants.inc` 未变更。

## 5. 未验证与保留

- WorkBuddy 黑盒复核与外部环境（Creo 10/9）未测。
- BUG-030 原报告"改尺寸失败"未在本机复现（见第 2 节）；BUG-029 原报告模型原件未重建。
- 三个 BUG-078 挂起现场保持保护，收尾动作仍待操作者选择（不随本批处置）。
