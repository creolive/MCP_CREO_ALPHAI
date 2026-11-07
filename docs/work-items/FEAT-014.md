# FEAT-014：钣金折弯释放与四壁能力

> **当前状态（2026-11-06 晚）**：四壁盒子经 `miter_cuts`（`PRO_E_SMT_MTR_CUTS`，BLIND 数值）路线实机建成，四墙均保存重载验证（见文末第二段），已随 **0.16.0** 合入 `main` 并发布。`adjacent_bend_ends` 保护默认行为不变（仅显式传 `miter_cuts` 才放行）；切角量与角部间隙尺寸仍未量化。同日 `sheetmetal_flange.edge` 新增计划内几何选边 `edge_geometry` 并实机验收，见下节；`edge_geometry` 已随 **0.17.0** 合入 `main` 并发布。

## 2026-11-06：R10 计划内 `edge_geometry` 选边（实机）

`sheetmetal_flange.edge` 现在有两种形态，二者都不得再包 `edge`/`reference`：

- `{"kind":"edge","id":N}`：当前巡检的边 ID，语义不变；
- `{"kind":"edge_geometry","endpoints_mm":[[x,y,z],[x,y,z]],"tolerance_mm":1e-6}`：当前模型坐标毫米的两端点点名一条**直线边**。`tolerance_mm` 可省略（默认 `1e-6`，允许 `1e-9..1000`），对象只接受 `endpoints_mm`/`tolerance_mm` 两键，不接受单位字段。坐标必须有限、两端不重合。

原生在**每个 op 执行前**重新遍历当前 body→surface→contour→edge：`ProEdgeIdGet` 去重、`ProEdgeDataGet`+`ProLinedataGet` 取端点，按 `inspect_length_units` 换算到 mm 后做**无向**端点对比较。恰好一条候选才创建；0 条、多条、模型长度单位不可换算都在创建前拒绝，0 条文案给出扫描的直线边数与 tolerance，多条给出候选 id。因此计划不再依赖提交时的 edge id，同一条物理边在重建后改变 id 仍可按几何选中。

实机 Creo 12.4.0.0（`tools/test_flange_edge_geometry.py --live --confirm-session-usable`，17/17）：

- 185×232×1 首壁（模型 `cbbcd27acf374b9c82534c3764b3aa51`）；`+x`、`-x` 两道非干涉折边都用**任何折边创建前**采集的端点提交，两面墙顶面 232 mm、与贴边 `matches`，均 `saved_file_reloaded_and_verified=true`；
- 两道折边把 `-y` 顶边从 185 缩短到 177.92 mm，id 由 **85 变为 267**，旧 id 已不在当前边表；随后同一物理边用当前几何端点 + 显式 `miter_cuts{width:1,offset:1}` 建成并保存重载 true；
- 不存在的几何 `[[900,900,900],[900,901,900]]` 被拒，文案报“扫描 86 条直线边、匹配 0 条”，revision 与体积不变、回滚 `succeeded`；
- 报告 `build/flange_edge_geometry/20261106T235931_f44fd733/report.json`（SHA256 `b84b3e0f5908f6af8932babf70803bbb81982f7ef2bbadf90341db917f13f4ea`）。

**未验证**：Creo 9/10、多候选歧义与未知长度单位的实机拒绝（仅单测）、非轴对齐/斜置边的端点匹配、跨计划重放与真实重启后的 id 重排、WorkBuddy。几何选边只解决“选哪条边”，不改变 `adjacent_bend_ends` 与 miter 的几何门槛。

## 2026-11-06：R09 归因文案、实机对比与能力口径（离线 + 实机第 3 项）

本条只改诊断文案与说明，不改几何、不放宽拒绝条件。**同日已用 `tools/test_sheetmetal_box_live.py` 跑 R09 第 3 项实机对比**（见文末 2026-11-06 节）：自由首壁建成，第三壁在 1 角/2 角上下文均被 `adjacent_bend_ends` 创建前拒绝，`end_trim_mm` 实测被忽略；第 4—6 项仍无可用几何路线。状态口径固定如下：

- **四壁未交付**：0.13.0 没有新增四壁能力，四壁盒仍不可建，FEAT-014 保持开放。
- **`adjacent_bend_ends` 是创建前拒绝规则**：它依据邻接边/弯曲后退让判定并拒绝，不是几何证明，也不是斜接（miter）可行性证明；调用方传 `relief` 不会跳过该 guard。
- **`relief` 是 bend-end relief**：`PRO_E_SMT_BEND_RELIEF` 的弯端释放（`none`/`rectangular`），不是 corner relief，也不是斜接；当前不证明它能解决角部重叠，四壁路线仍需 R09 后续实机取证。
- **报错来源分派**：`native_planar` 首壁的错误只指向 `creo_sheetmetal_planar_wall` 的 frame/envelope，不再引用 `wall_contract` 或 YZ 旧配方；只有确实由 `sheetmetal_wall` 转换首壁建立的模型才引用 `wall_contract`；来源未知时不提供旧首壁配方。
- **折边引用文案**：`sheetmetal_flange` 的入参错误给出 `operations[i].edge` 位置与 `{kind:'edge',id:N}` 示例，并要求用当前巡检的 edge id（2026-11-06 起同时接受 `{kind:'edge_geometry',...}`，见上节）。

离线验证：`tests/unit/test_sheetmetal_flange.py`、`tests/unit/test_flange_direction.py` 的文案断言；未构建执行器、未跑实机，四壁几何与 relief 效果均为未验证。

## 2026-10-31：DEV-053 P08 候选边发现接口冻结（离线）

本轮新增钣金件巡检中的有界 `wall_contour_check`：原生每边最多一次 `ProSmtedgeContourGet`，单次巡检最多 256 边，保留真实 `wall_contour_query_code`；公开巡检按当前 model revision 将每条已查询边投影为 `wall_contour_status=eligible|ineligible|unknown`。`0` 为壁面轮廓候选，`-8` 为不在绿/白壁面轮廓，其余/异常查询码为 unknown；未查询边不伪造状态。以当前巡检几何、壁面/端点选择边，不复用历史 edge id，也不提供无条件 `flange_available`。`eligible` 不表示最终可创建，邻接端仍由 `failure_reason=adjacent_bend_ends` 与 `flange_failure_evidence` 独立解释，并在创建前拒绝。

本轮的接口字段、标准 YZ 首壁例子与描述可独立分批交付：文档/例子属 PATCH；新增 `wall_contract` 帧回显及候选边公开结构属 MINOR。四壁、corner relief/miter 与材料端释放几何仍不支持或未证实；`end_trim_mm` 三轮实测为 `trim_ignored`，不得宣称可用作角部让位。P09 离线调查与后续受限诊断条件见 [交接记录](../development/FEAT014-CORNER-INVESTIGATION-2026-10-31.md)。

P14 待验：构建后以当前源码运行三组首壁帧对照，按几何选自由端首折边并测 `flip` 双向 Z 向增长；逐案试 `unbend`/`bend_back`/`flat_pattern` 的 `fixed_surface`；核候选边壁面边、rim/side 边、邻接端和查询失败的真实码/三态/当前 revision，确认巡检不建 flange、不改变模型；邻接端仍创建前拒绝且 revision 不变。每案保留 job/model、原码、几何、保存重载及回滚。未跑 `bridge.py build` 或 `--live`，本段不构成原生建模验收。

离线证据（提交前 dirty 源码）：定向 `unittest` 69/69、`discover -s tests` 1817/1817、改动 Python 文件 Ruff、`native/generic.cpp`/`advanced.cpp` 的 clang-format dry-run 均通过；两份非 live 报告见 `build/post0100_sheetmetal/20261031T224613/`。报告目录属本机生成物，不入库；P14 应按提交后的源码身份重新构建并实机验证。

日期：2026-10-28（Asia/Shanghai）补工作卡，沿用既有 ID。类型：功能。优先级：P2（既有台账）；状态：**已交付 0.16.0（四壁经 `miter_cuts` 实机建成、`four_walls_complete=true`；`adjacent_bend_ends` 默认拒绝不变，仅显式 `miter_cuts` 放行）；relief 材料几何、切角量/角部间隙仍开放**。历史过程（2026-10-29 第三轮：第一道 `-1` 的根因已定——验收基体实为 232 mm 厚板、所选边不在壁面上——已改基体并在准入层拒绝该类边；修正后两道折边 succeeded 但几何是平铺延伸而非折弯，第三道挂起；四壁与释放能力未完成。2026-10-29 第四轮：截面已按库存 `flange_shapes` 重建（单线、无 centerline、腿在父壁法向）并重建执行器，但实机被会话消失阻塞，折弯仍**未验证**。2026-10-29 第六轮：`direction` 开关从 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM` 改到 `PRO_E_SMT_FLANGE_SEC_FLIP` 后，`tools/test_flange_direction.py --live` 两例均 `saved_file_reloaded_and_verified=true`、rev 2，默认向外（+X 顶边 +Z 79 mm）、`flip=true` 反向（−Z 79 mm），报告 `passed=true`；四壁在第二道后仍于 `f_ny` 回滚（rev 不变、原码保留），1×1 矩形释放体积差 0.000000、无缺口面）。目标版本：0.16.0（四壁 miter cuts 已交付）；relief 材料几何与切角量仍开放。

来源：[统一台账](../BACKLOG.md)既有 FEAT-014 行、[0.7.0 R1 S3](../validation/feedback-0.7.0-2026-10-28/2026-10-27_CREO_0.7.0_钣金增料与四壁折边仍未修复验收报告.md)、[逐章映射](../validation/feedback-0.7.0-2026-10-28/MAPPING.md)。关联 [BUG-047](BUG-047.md) 的折边方向/材料侧缺陷与 [BUG-032](BUG-032.md) 的有效薄底板契约。

## 目标与阶段边界

既有目标包含钣金止裂槽、成形、折边及过渡；本批先将“四壁盒失败定位”和“新增释放/角部能力”拆为两阶段。T05 使用经 BUG-032/T03 确认的 185×232×1 mm 底板、h80/R2.54/Y0.5，按真实几何重新选择边，逐道与同一计划对照，核对方向、材料侧、父体、元素树、失败原码、revision 与回滚。报告中前两道 ±X 成功、第三道 −Y `-1`；角部冲突是报告人的推测，不能先定为根因。`rolled_back` 的前项须重建，不能仅续跑后半段。

若 T05 证据表明需新增 relief/角部规则，T11 才设计最小支持类型及宽深、端部、厚度和兼容默认值，贯通 schema/原生/编辑。若是既有引用或参数缺陷，按 BUG-047/T05 的证据最小修复，不借 FEAT-014 扩成无来源的新功能。更广的止裂槽、成形和过渡仍开放，不因四壁子项完成而全卡关闭。

## 验收与环境

T05 可交付可复现/未复现结论与根因证据，但只有四壁原生特征全成功、角部几何独立核对、展开/折回、尺寸编辑、revision、保存重载及失败回滚均通过，才可宣称四壁能力完成。报告样本的边 104—107 不能硬编码为通用 ID；厚底板失败与独立 flip 问题分开。环境：离线 Windows x64 / Python 3.12+ / C++17；实机为本机 Creo 12.4.0.0 / 匹配 SDK，须另获指派且先确认 BUG-001 会话条件。本次 T00 只补卡，未连接 Creo 或验证几何。

## 2026-10-28：T05 离线阶段（DEV-051）

- 状态：**T05 离线调查完成 / 未复现 / 根因未定**；四壁能力仍未完成。本次未连接 Creo、未创建任何特征、无生产改动。
- 已就绪：按几何选边的四壁夹具（185×232×1 + h80/R2.54/Y0.5，`face` 显式）、逐道刷新与单计划对照、每道预期与 29 个判定字段、四条可反驳假设与判定表、厚底板首道待验分支、`--live` 拒绝的离线驱动（`tools/test_sheetmetal_flange.py`、`tests/unit/test_sheetmetal_flange.py`，单测 33/33）。
- 可离线确定的几何：四道合计新增 66 720 mm³；材料在板内侧时第三道与两条既有壁各有 ≥77.46 mm³ 角部重叠（第三道 2 个角部，下界 154.92 mm³）；前两道之后垂直边界在两端各缩短 ≥1 mm（合计 183 mm）。这些是几何预测，不是已观察到的失败原因，根因仍未定。
- T11 设计输入（未实现）：壁端折弯释放（none/矩形/扯裂/圆形、宽深、单双端）+ 垂直壁角部规则（仅释放/斜接/显式重叠）、字段落点与兼容默认；仍须在四壁 + 角部几何 + 展开/折回 + 编辑 + 重载 + 回滚闭环后才可宣称能力完成。
- 待验清单（实机）：四壁逐道创建与失败原码；材料侧/方向/父体/边有效性/原生树；单计划与逐道刷新对照；`flip` 正交；剪短 20 mm 的第三道探针；厚底板首道（依赖 T03）；展开/折回、编辑、重载与回滚。
- 验收记录见 `docs/development/DEV051-T05-ACCEPTANCE.md`。

## 2026-10-29：T11 离线实现（DEV-051）

- 状态：**离线实现完成 / 四壁与释放能力待原生验收**。本次未连接 Creo、未创建折边或释放、未展开/折回、未编辑或重载；四壁能力仍未完成。
- SDK 核对（本机 Creo 12.4 `ProSmtFlangeWall.h`）：每个弯端有独立释放复合元素 `PRO_E_SMT_BEND_RELIEF_SIDE1/SIDE2`，类型 NONE/RIP/STRETCH/RECTANGULAR/OBROUND/PARAM；深度类型含 BLIND(-4)；角部释放 `PRO_E_SMT_CORNER_RELIEF`、斜接 `PRO_E_SMT_MTR_CUTS`、边撕裂 `PRO_E_SMT_EDGE_RIP` 同在特征树中。
- 已实现（最小形状）：`sheetmetal_flange.relief` 可选对象，`type` 仅 `none`（默认，保持旧行为：两端 `PRO_BEND_RLF_NONE`）与 `rectangular`；`ends` 取 both/side1/side2；`width>0`、`depth>=0` 为绝对模型单位并固定 BLIND，不按板厚缩放；别名记录带实测板厚与 `height-radius` 角部走向算术。schema/独立工具/execute_plan/原生纵深防御与创建期编辑路径说明均已补齐。
- 明确未支持：rip、stretch、obround、param、角部释放全系、斜接、边撕裂、释放长度/角度，以及任何按几何自动选角部规则；这些组合在准入处拒绝而不是降级为 none。
- 未测（实机）：四壁真实创建与释放元素树被接受、体积增量与 `width×depth×t` 的关系、缺口相对折弯边的实际位置、单端释放、`depth ≥ h−R` 档对第三道失败的影响、展开/折回、`height` 尺寸编辑、删除重建改释放、revision、保存重载与失败回滚。
- T05 静态断言已按新事实同步（`bend_relief_none_both_sides` → 默认 NONE + rectangular opt-in 一组断言），不是回退或删除。
- 验收记录见 `docs/development/DEV051-T11-ACCEPTANCE.md`。

## 2026-10-29：T11 实机被第一壁阻断（未创建任何折边）

按 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md)，在手动打开的 Creo 12.4.0.0 上跑两轮四壁（§relief§ 省略 与 §rectangular/both/1x1§）：

- 第 1 轮底板作业 §796092e2085b49a7903787406c9d8879§（模型 §c34f02bd6046425caa45dc50f2762a52§，t11_relief_none_de867f）在 op index 1 就失败：§toolkit_code=-1§、§failed_stage=execute_sheetmetal_wall§，消息 “the section has 2 drawing entities (1 straight lines)”；与 BUG-032 的 T03 实机阻断同一根因（准入把草图 §PRO_2D_COORD_SYS§ 计成第二条曲线）。
- 第 2 轮未提交：同一阻断点，不重复占用通道。
- 因此四壁真实创建、每道体积增量、§relief§ 回显、第三道 §f_ny§ 是否再现 §-1§、失败回滚与 §revision§ 均未取证；也没有用四个普通拉伸块替代折边。报告 §build/sheetmetal_relief/20261029T155905_bb490653/report.json§。

下一轮：先修第一壁准入并重编译执行器，再用同一驱动原样重跑；之后再补 §corner_run§（宽 1、深 77.46）与 §ends=side1/side2§ 对照。


## 2026-10-29 第二轮实机：底板建成，第一道折边即 `-1`

第一壁准入修复后重跑 T11 两轮（relief 省略 / rect 1×1 both 1×1）：两块 185×232×1 底板都建成（42 920 mm³、rev 1、bbox `[0,-116,0]`–`[185,116,1]`），但第一道折边 `f_px`（边 id 125，+X 上边，跨度 232 mm）在两轮都失败：

- job `ef7341d546b34fa28a145771b543b1a4`（none）/ `4c172764b29f4a0d850cfd6a38b73125`（rect 1×1）；
- `toolkit_code=-1`、`failed_stage=execute_sheetmetal_flange`、`failed_toolkit_call=ProFeatureWithoptionsCreate`，消息 “Toolkit call ProFeatureWithoptionsCreate failed with code -1 during execute_sheetmetal_flange”；
- `rollback_succeeded=true`，两轮快照 rev 1→1、体积 42 920→42 920（`rolled_back=true`），无 `relief` 回显。

与 0.7.0 R1 S3 原件的关键差异：原件前两道 ±X 成功、第三道 `f_ny` 才 -1；本轮**第一道**就 -1，此时还没有相邻壁、没有角部。因此 T05 的角部重叠假设不能解释本轮失败，四壁能力仍未完成，`relief` 两档也无法比较（失败早于释放生效）。报告 `build/sheetmetal_relief/20261029T161528_cc1fda94/report.json`。

下一步：用 `PRO_FEAT_CR_INCOMPLETE_FEAT` + `ProFeatureElemtreeExtract` 取回 Creo 补齐的折边元素树，与写入的树比对（flange 类型与 2D 扫掠截面的配对、`PRO_E_SMT_WALL_HEIGHT=NONE`、TAN 曲线集合在转换型壁边上的合法性、SIDE1/SIDE2 TO_END 组合）。

## 2026-10-29 第三轮实机：第一道折边 `-1` 根因（已定）与无折弯（未定）

按 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) 与 [T05 验收卡](../development/DEV051-T05-ACCEPTANCE.md) 的实机记录：

- **`-1` 根因已定**：折边失败路径取回本实现写入的树与 Creo 用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 补全的树，两者在 `PRO_FEAT_WALL`、`PRO_E_SMT_WALL_TYPE=17`、`PRO_E_SMT_FLANGE_TYPE=1`、`DEPTH_TYPE=4/4`（TO_END）、`WALL_HEIGHT_TYPE=0`（NONE）、`SHARPS_TO_BENDS`、`SEC_FLIP`、`THICKNESS_FLIP` 上逐项一致；Creo 的 `ProErrorlist` 为空。真正原因是承载对象：`ProSmtedgeContourGet(edge 125)=-8`（`PRO_TK_BAD_CONTEXT`，边不在 green/white 壁面），因为验收基体 `sheetmetal_wall(depth=1, thickness=232)` 实际是 **232 mm 厚的钣金件**（green/white 相距 232 mm、185×232 大面全是 `SIDE`）。R=2.54 折弯 232 mm 厚板不可能。
- **已改**：① 夹具基体改 `plane="XZ"` + `sheetmetal_wall(depth=232, thickness=1)`（真正的 1 mm 板，体积/bbox 不变）；② 折边入口用 `ProSmtedgeContourGet` 拒绝不在壁面上的边，消息带 `-8` 原始码与可行做法（不再以裸 `-1` 失败）；③ 截面腿按"中心线=对齐线、坐标系=贴附点"量取角度（原 `(90-angle)` 让 90° 请求得到与中心线共线的零折弯腿）；④ 失败路径保留元素树与面类型取证。
- **实机（1 mm 板）**：底板 42 920（rev 1）→ `f_px` 61 480（+18 560，rev 2）→ `f_nx` 80 040（+18 560，rev 3），两次 `saved_file_reloaded_and_verified=true`、`ProSmtedgeContourGet=0`（4 条轮廓边）。
- **未定（关键）**：两道折边是**平铺延伸**：bbox 只在 X 增长 80 mm（185→265、0→-80），Z 仍 ±0.5；体积 232×80×1 与折弯同值，体积断言无法区分。截面如何让 Creo 形成折弯仍未定；候选探针见 T11 卡"仍未决项"。
- **新阻塞**：第三道 `f_ny` 在 `ProFeatureWithoptionsCreate` 内挂起（job `bb5543fb3c66404e95172876fa1ac9aa` 仍 running、`toolkit.lock` 被占用），驱动按规则停止；四壁与释放仍未验证。

状态口径：FEAT-014 = **第一道折边可创建（根因已定并修复准入），折弯几何未定，第三道挂起，四壁与释放未完成**。不得表述为"折边已修复"或"四壁能力已具备"。

## 2026-10-29 第四轮：截面按库存形状重建，实机被会话消失阻塞

- **实机未执行**：交接前提的"新会话"不存在。2026-10-29 19:51:03 Windows 事件日志记录 `xtop.exe` `AppHangB1` 并已关闭；19:53/20:06 两次 `tasklist` 均无 `parametric.exe`/`xtop.exe`；`creo_session_status` 为 `connected=false`、`toolkit_code=-4`、`creo_process_snapshot.processes=[]`。按规则不启动/不重启 Creo、不重提、不清锁，全部实机步骤暂停（现场见 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) §4.1）。
- **离线结论（新增）**：本机 `Common Files\text\smt\flange_shapes` 9 个库存截面全部是"1 条 line + 1 个 coord_sys + 1 个尺寸、无 centerline"；弯弧只出现在 hem 类，`i_wall` 的尺寸是腿长 `5.00` + 角度 `90.00`，即"90° 直腿 = 直壁/平铺延伸"。
- **方向约定（离线，接上一轮现象）**：上一轮 `LINE_wall 0,0 → 0,80`（草图 +y）实机得到 bbox 只增 X、Z 不变 ⇒ 草图 +y = 父壁平面内、草图 +x = 父壁法向；90° 折边必须把腿放在草图 +x。
- **已改**：`generic_sheetmetal_flange` 的截面改为单条线 `(0,0) → (h·sinA, h·cosA)` + `height` 长度尺寸、去掉 centerline，其余元素树不动；`bridge.py build` 已重建执行器，`clang-format` 通过。
- **新增驱动**：`tools/test_flange_direction.py`（单模型单折边、bbox 判定、180 s 挂起预算）与其单测；离线报告 `build/flange_direction/offline_20261029.json`。
- 状态口径：FEAT-014 = **第一道折边可创建（根因已定），折弯几何未定（第四轮改了截面但未实机验证），第三道挂起未复现，四壁与释放未完成**。不得表述为"折边已修复"。

## 2026-10-29 第六轮：方向开关落在截面侧，折弯与反向均实机成立；四壁仍止于第二道，1×1 释放无可观测几何

分支 `codex/dev051-feedback070`，HEAD `cce1922`；手动打开的 Creo 12.4.0.0 会话（PID 15156，22:05:41 由协调器拉起），`creo_startup_status` → `ready/connected=true`，`session_health=no_failure_observed`。本轮未启动/关闭/重启 Creo、未重提已受理 job、未清保护。

### A. 方向（BUG-047）

- **机制定案**：`flip` 原先写 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM`。22:06 的对照（`flip=false`→1、`flip=true`→−1）bbox、体积、方向完全相同，说明该元素不是方向开关；`ProSmtFlangeWall.h` 对该元素只列 `PRO_B_TRUE/PRO_B_FALSE`，−1 不是可用的第二个值。真正的开关是 `PRO_E_SMT_FLANGE_SEC_FLIP`（元素表："Flip Section Side"）。
- **2×2 实测**（同边、h80/R2.54/Y0.5，一次只改一个变量）：

| 依附边 | `SEC_FLIP=FALSE` | `SEC_FLIP=TRUE` |
| --- | --- | --- |
| +X 顶边（z=+0.5） | down，bbox z `[-79.5, 0.5]` | up，bbox z `[-0.5, 79.5]` |
| +X 底边（z=−0.5） | up，bbox z `[-0.5, 79.5]` | down，bbox z `[-79.5, 0.5]` |

  即侧向相对依附面：`TRUE` = 从选中面法向向外，`FALSE` = 材料侧。据此定口径：**默认（`flip=false`）= 向外**，`flip=true` = 反向（材料侧）；轨迹法向固定 `NO_FLIP`（与库存 `UgSmtFlgWallCreate.c` 一致）。证据目录 `build/flange_side_probe/`（`sec_true/20261029T221644_c9ae6ece`、`bottom_default/20261029T221859_a54aec71`、`bottom_sec_true/20261029T221934_470617ee` 等）。
- **收口实机**：`tools/test_flange_direction.py --live --confirm-session-usable` → `passed=true`，报告 `build/flange_direction/20261029T222510_9cebd5e1/report.json`（SHA256 `9464933eb94bdee351361fc2265777bfe8f58145f1882af45c3fcf3c2b5f3745`）。
  - `angle90_outward`：模型 `fe7096c0f0444283bf8482979ee6866d`，base job `41454fd240d349f78955512df154378b`，flange job `f20a09ec980e4d4a8c31a0d840d4c0de`，rev 1→2，42 920→60 945.291234，+18 025.291234 mm³，bbox z `[-0.5, 79.5]`，`direction=up`，回显 `bend_side=outward/sec_flip_element=1`，`saved_file_reloaded_and_verified=true`。
  - `angle90_inward`：模型 `c72271209fa44fa7ba8921590c4834eb`，flange job `bb0cdab24f67453d8c0979781a2a8a41`，rev 1→2，+18 025.291153 mm³，bbox z `[-79.5, 0.5]`，`direction=down`，回显 `inward/0`，重载 true。
  - 驱动 oracle 已改：`|z 增长| ≥ 72 mm` 判折弯、方向必须等于该例显式期望（默认 up、`flip=true` down），不再"只认向上"。

### B. T05 四壁（`build/sheetmetal_relief/20261029T222754_44e6ab6a/report.json`，SHA256 `d2de17487469f10fba9859a0459cfeb64e593537105c8d5a6df5be9bf829d58f`）

模型 `fc04dfaf7e9a4d6eb17b900d5276da33`（t11_relief_none_2b54bc），底板 42 920、rev 1；逐道一 job、每道重新取边：

| 道 | job | rev | 体积增量 | bbox | direction | 重载 |
| --- | --- | --- | --- | --- | --- | --- |
| `f_px`（+x） | `c09759e7d25341d3a98874291273be15` | 1→2 | +18 025.291234 | `[0,-232,-0.5]`–`[185,0,79.5]` | up | true |
| `f_nx`（−x） | `fc097f17478a4d48a8a64deb2a6effef` | 2→3 | +18 025.291234 | 同上 | up | true |
| `f_ny`（−y） | `1a2b487ce90b486fb358494ba6afcc22` | 3→3 | 无（回滚） | 不变 | — | — |

- 第三道**未重提**：`f_ny` 边跨度 177.92 mm（两端各被已有折弯占去 3.54 mm），`toolkit_code=-1`、`message="Regeneration produced a failed, suppressed or incomplete feature"`、`rollback_succeeded=true`、`effect_status=rolled_back`，rev 与体积回到第三道之前。原生日志显示 `F_NY` 创建成功但 `status=6`、`geometry_items=[]`，随后的健康检查判定整件失败并回滚。
- 结论：四壁仍**未完成**；失败点从第一道推进到第三道、且已有真实折弯几何，与前两轮"平铺延伸/第一道 −1"不同。失败边保留 job 与原始码，按规则不再提交该边、也不再续跑第四道。

### C. T11 释放两档（同一报告；`relief_rect_1x1` 模型 `88dcd28eefb4459caf1480cb1803cfb9`）

| 档 | `f_px` job | 体积增量 | 与无释放之差 | 缺口面 | `relief` 回显 |
| --- | --- | --- | --- | --- | --- |
| 省略 | `c09759e7d25341d3a98874291273be15` | +18 025.291234 | — | 0 | 无 |
| rectangular both 1×1 | `e45404d4c09d441791626bb5eb369525` | +18 025.291234 | 0.000000 | 0 | type/ends/width/depth/板厚/两项比较齐全 |

- 差分 oracle（同边、同参数，只有释放不同）期望 −2 mm³；实测 **0.000000 mm³**，且模型上没有 1 mm 级小面（缺口面 0 个）。诊断性第 5 个 job（`6ddadf6487644504a1ebdfd6ef8bd7f4`，`build/relief_probe/w4_d4/20261029T223039_44c271f2/report.json`）把宽深提到 4×4（> 回显板厚 3.71）后体积差仍为 0，说明不是"1×1 太小被忽略"。
- 自由端解释与边界：这两道折边的弯端位于板件自由角，Creo 在该处不切释放缺口；真正需要释放的第三、四道在 `f_ny` 即回滚（有/无释放失败方式相同，job `2bc5bf3184d94d08b472a0cd179c242e`），因此**释放能力未获实机证实**，只是"请求被接受并回显"。
- 回显里的 `part_thickness_mm=3.71` 与 1 mm 薄壁不符（`ProSmtPartThicknessValueGet` 读到的是零件级默认板厚），已登记到 BUG-032 状态行：任何"宽 ≥ 板厚"的规则在修正前不可信。

状态口径：FEAT-014 = **折弯与方向已实机成立（A 通过）；四壁止于第二道（第三道 `f_ny` 回滚，原码保留）；释放请求可接受但无可观测几何**。不得表述为"四壁能力已具备"或"释放已实现"。

## 2026-10-30：T11 释放有效场景离线阶段（实现与回归完成，实机未验）

分支 `codex/dev051-feedback070`，基线 `760aa9b`（T03 板厚同步）。离线定位、实现、回归与构建；未连接 Creo。详见 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) 2026-10-30 节。

- **定位**：第六轮的 0.000000 差全部来自自由端，不能区分"释放未实现"与"自由端无缺口"。SDK 核对确认元素树转写正确；关键未观察点是 Creo 会把未写的释放元素填成默认（探针树 `flange_expected.xml` 为 `TYPE=5 PARAM`、数值全 0），"写入值是否留在创建出的特征里"此前从未读过。
- **实现**：创建+再生成功后回读创建特征树的释放段（`ProFeatureElemtreeExtract` + 按元素路径取值），与请求逐项核对，不一致即失败并回滚；一致则把 `relief_element_echo` 记入别名并写日志 `SHEETMETAL_FLANGE_RELIEF_ELEMS`。`LENGTH_TYPE/LENGTH/ANGLE` 只记录不断言（默认值是实机待答问题）。写路径未变，默认 none 不变，schema 不变。
- **有效材料场景**：`f_px`（+x，自由端负对照）→ `f_ny`（−y 第二道，+x 链端撞 `f_px` 折弯 = 1 个材料端）；none/1×1/4×4/单端对照，去料期望按实际相交材料独立推导（−1/−16 mm³、自由端 0），体积模型锚定第六轮实测（18 025.291233 vs 实测 …234）。verdict 拒绝"参数写了但几何没去料"（第六轮形状）与板厚矛盾。
- **未测（实机）**：`f_ny` 作第二道能否建成、`relief_element_echo` 一致性、缺口位置/尺寸/面/差值、单端映射、LENGTH 三元素默认值、板厚 1.0、保存重载、四壁 profile 新期望（0/−2）复测。

## 2026-10-30：T05 离线续做——第三壁对照设计冻结与 `end_trim_mm` 契约贯通（实机未验）

分支 `codex/dev051-feedback070`，HEAD `641edb3`。接续第六轮"`f_ny` status=6、空几何、回滚"的观察，离线补完对照实验；未连接 Creo。详见 [T05 验收卡](../development/DEV051-T05-ACCEPTANCE.md) 2026-10-30 节。

- **对照设计冻结**：full_length（复现第六轮）/ trimmed_20（第三壁两端各缩 20 mm）/ order_ny_first（0 材料角）/ order_ny_second（1 角）四组，每 fresh 模型逐道一 job、每道重选边；判定表规定角部干涉仅在全长失败 + 低角位成功 + 修剪壁成功且 setback 语义被自由壁探针确认三者齐备时升为 supported。**角部干涉仍是候选，未定因。**
- **`end_trim_mm` 贯通**：`sheetmetal_flange` 可选正数字段，两侧深度 `TO_END`→`BLIND`+offset（`advanced.cpp`），schema/server 同步；缺省时元素树逐字节不变（静态守卫断言）。语义（链端 setback 还是壁长）离线不可定，由自由首壁探针按实测体积分类，仅 setback 确认后才允许修剪第三壁提交。
- **驱动**：`tests/unit/test_sheetmetal_box_live.py`（27 用例）与 `tools/test_sheetmetal_box_live.py`（默认离线、`--live` 拒绝）；单测 27/27、全量 discover 通过、`bridge.py build` 成功。报告 `build/sheetmetal_box/20261030T082547_09fb8658/report.json`。
- **未测（实机）**：trim 语义探针、四组对照创建/失败/回滚、`f_ny` 是否再现 status=6、`end_trim_mm` 真实几何、角部干涉成立或反驳；四壁能力继续开放。

## 2026-10-30：N05 离线阶段——正式探针入口、trim 量测与原生失败取证（实机未验）

分支 `codex/dev051-feedback070`，基线 `b10b9f7`。0.9.0 后接续（DEV-052 N05，详见 [T05 验收卡](../development/DEV051-T05-ACCEPTANCE.md) 同日 N05 节）：

- **正式 live 探针入口**取代 box 驱动原来的"双开关仍拒绝"：三组探针（`ny_first` / `px_then_ny` / `px_nx_then_ny`）固化 10/30 一次性实机对照，加 trim 量测（无 trim vs `end_trim_mm=20` 各一 fresh 自由首壁，按实测增量分类语义）。判定锁：未知测量不判通过、失败墙永不记为成功、`four_walls_complete` 恒 False。
- **原生失败取证**（`native/advanced.cpp`，失败路径专用）：依附边长度/两端点/相邻面与边、regenerate 后特征 status 与 geometry 计数（status 6 = unregenerated 即第六轮形态）、元素树与回滚证据有界保存，未知留 null；字段语义已写入 T05 卡供 N06 消费。未写任何 corner 规则、未实现 corner relief。
- **状态**：离线交付（49 单元、dev_check、`bridge.py build` 通过）；trim 语义、三组探针与取证字段全部待实机；四壁与释放能力仍开放。

## 2026-10-31：N06 离线阶段——邻接明确拒绝（`adjacent_bend_ends`）与取证传播修复（实机未验）

分支 `codex/dev051-feedback070`，基线 `49decae`。**方案裁决（编排方）**：机理证据支持"附着边端部邻接既有折弯 → 特征再生失败（feature_status=6、geometry_item_count=0，2026-10-31 N05 重跑在两组真实板顶边上复现，边长 181.46/177.92 mm）"，但截面越界 vs 相邻料重叠不可区分，SDK 无已证角部 API——本轮**不实现 corner relief/miter**，交付有界能力 + 明确边界；四壁支持不声称，本卡继续开放。未连接 Creo、未运行 `bridge.py build`、未改版本。

- **触发条件确证证据（输入）**：2026-10-30 对照 + 2026-10-31 修复后重跑：自由边可建；一端或两端与既有折弯相邻时均在正确板顶边上复现 created-but-unregenerated（status 6、geometry 0）并回滚；确证形态每端平坦消耗恰为 R+t（=3.54 mm，R2.54/t1）。失败内部机理（截面越界 vs 相邻料重叠）仍不可区分，故只做明确拒绝。
- **原生邻接预检**（`native/advanced.cpp` `generic_sheetmetal_flange`，建树前、附着边校验之后）：对附着边两端各取**双侧正证据**——① 邻接性：该端的轮廓邻接边是弧（`ProEdgeDataGet`/`ProArcdataGet`）且其邻接面含圆柱面（`ProSurfaceDataGet` → `PRO_SRF_CYL`，折弯区边界）；② 消耗：弧半径 ≤ 2×(radius+thickness)+1e-3（弧半径上界实现"边缩短量 ≤ 2×(R+t)+容差"；确证形态实测 3.54 对界限 7.08，90° 内折弯的平坦 setback 不超过外侧弧半径，界限刻意放宽——`part_thickness_read` 可能读到零件级默认板厚，BUG-032 已注明）。**任一端双证据齐备即拒绝**：作业以失败终态返回，消息带 `failure_reason=adjacent_bend_ends`，证据以 `flange_failure_evidence` 嵌套进失败操作记录（`stage=before_create`，含 edge_id/长度/两端点/每端邻接弧边 id、类型、半径、`radius_bound_mm`、折弯面 id 列表）。查询失败、板厚不可读或邻接边为直线时不拒绝，走原路径；自由边（含 T03 首壁契约）行为零变化。静态圆角（非折弯的弧+圆柱）在半径界限内也会命中拒绝，属本边界的保守取舍，宁拒不诈。
- **取证传播修复**：N05 重跑发现 native.log 有 `FLANGE_FAILURE_EVIDENCE`（feature_status=6、geometry_item_count=0）而驱动汇总 `native_failure_evidence=null`——根因是原生把取证块**平铺** stage 成操作记录本身，驱动按 `operations[].flange_failure_evidence` 键读取。两条失败路径（create 失败树取证、regenerate 后不健康特征取证）改为嵌套 stage；`read_native_log` 尾窗 6000→65536 字符（UNHEALTHY_FEATURES 行 10 841 字符、距 EOF 约 16.6k，旧尾窗截掉行首致 `stage_feature_state.line_found=false`）。单元锁定嵌套 stage（计数=3）与长 dump 尾窗。
- **驱动判定更新**（`tools/test_sheetmetal_box_live.py` + `tests/unit/test_sheetmetal_box_live.py`）：第三墙命中预检 → `adjacent_bend_ends_rejected`（passed=true，已知边界按设计生效；失败墙仍列入 `failed_walls`，`four_walls_complete` 恒 false）；未带 `adjacent_bend_ends` 标记的再生失败 → `trigger_reproduced`（自本轮起为**未预期形态**，passed=false，需查原生取证）；`third_wall_built_not_reproduced` 与 ny_first/自由边路径回归不变。`adjacency_rejection` 只按正证据识别（嵌套证据 `failure_reason` 或失败消息 token）。
- **能力边界现状**：四壁仍不支持（3/4 是上限且第 3 壁现在被预检明确拒绝）；corner relief / miter 未实现；`end_trim_mm` 2026-10-30/31 两轮实测均为 `trim_ignored`（trim 与无 trim 增量同为 18 025.291234 mm³），`trimmed_20` 对照继续冻结，trim 不能用于角部让位。`server.py` 工具说明与 `docs/COMPATIBILITY.md` 已补一句边界说明。
- **未测（实机，待编排方安排构建+实机窗口）**：预检的真实拒绝与端点取证、自由边/ny_first 回归、T03 契约回归、无邻接折边回归、`flange_failure_evidence` 嵌套键在 job 结果中的可达性、未标记再生失败路径（trigger_reproduced → passed=false）的新语义。

## 2026-10-31：N06 预检修复——邻接边改按端点枚举（`ProEdgeVertexdataGet`）并加有界诊断日志（实机未验）

分支 `codex/dev051-feedback070`，基线 `28de56e`。接上节：N06 修复后实机重跑（`build/post090_n06_live_20261031T134730/report.json`）预检**未触发**——edge 197/296 两例折边 job 的原生日志均为 `FLANGE_ADJACENT_BEND edge=… end0=0 end1=0 unmatched=0`：预检运行了、邻边 id 正确返回（197 → 207/104，296 → 207/302），但弧+圆柱面+半径三条件从未同时命中。本窗口只做离线：SDK 头文件核实、修复、单测、构建；未连接 Creo。

- **SDK 语义核实（本机 Creo 12.4 `ProEdge.h` 摘录）**：`ProEdgeNeighborsGet` 的输出 `p_face1/p_face2` 是**输入边自己的两个邻接面**（"The first/second adjacent surface"；`flange_edge_forensics` 在实机上已实证 197 → 126/101 正确），`p_edge1/p_edge2` 是"在 p_face1/p_face2 的**轮廓**上的下一条边"——两条邻边**不保证分属两端**，归属由面轮廓的存储遍历方向决定。实机现象据此定因：197 的两条轮廓邻边（顶面轮廓与侧面轮廓）**都落在自由角（x=0 端）**，折弯端（x=181.46）的弧边从未被检查；`unmatched=0` 只表示"都按端点匹配到了某个端"，被误读为"分属两端"。对邻边再调 `ProEdgeNeighborsGet(nb)` 取其两面这一步语义本就正确（返回的就是 nb 自己的两个邻接面），不是缺陷所在。
- **修复**（`flange_adjacent_bend_end_evidence`）：邻接边枚举改用文档明确的按端原语 `ProEdgeVertexdataGet(edge, PRO_EDGE_START/PRO_EDGE_END, …)`（ProEdge.h："Finds the neighbors of the edge at the specified end"，返回该端相交的全部边 `p_vertex_arr` 与邻接这些边的面 `p_surf_arr`），每端独立查询、按 `PRO_EDGE_START/PRO_EDGE_END` 归端，输入边自身按 id 跳过；不再依赖面轮廓遍历方向。判定标准不变：候选边是弧（`ProEdgeDataGet`/`ProArcdataGet`）+ 该弧自己的两面（`ProEdgeNeighborsGet(nb)`，语义同上核实）含圆柱面（`PRO_SRF_CYL`）+ 弧半径 ≤ 2×(radius+thickness)+1e-3。`unmatched_neighbor_edges` 键随按端枚举一并移除（evidence `ends` 行 schema 不变：neighbor_edge_id/neighbor_edge_type/neighbor_arc/neighbor_radius_mm/radius_bound_mm/bend_face_ids/adjacent_bend_end/point_mm）。查询失败仍静默走原路径，自由边行为零变化。
- **有界诊断日志（下次实机自证）**：每端一行 `FLANGE_ADJACENT_BEND_END end=N edges=<fan size> faces=<id:type;…>`（端点面扇区）；每条邻边一行 `FLANGE_ADJACENT_BEND_NB end=N id=<edge id> curve_type=<ProEnttype> is_arc=0/1 radius=<mm> faces=<id:type;… 或 code=<错误码>>`；汇总行去 `unmatched` 列，改为 `FLANGE_ADJACENT_BEND edge=<id> end0=0/1 end1=0/1`。面读取封顶每端 16 条。
- **单测**：`tests/unit/test_sheetmetal_box_live.py` 原生静态守卫新增 `adjacency_per_end_vertex_query`（锁定 `ProEdgeVertexdataGet` 在源码中），其余 11 项守卫继续通过。六个钣金/折边单测模块联测 233/233 通过；`dev_check --work-item FEAT-014` 通过；`bridge.py build` 重编译执行器成功。
- **未测（实机，待编排方窗口）**：同上节清单；本轮新增观察点——两例失败 job 重跑时应看到 `FLANGE_ADJACENT_BEND_END/NB` 行给出折弯端弧边（曲线类型 3、半径 3.54、faces 含圆柱面 id）并触发 `adjacent_bend_ends` 拒绝；若端点面扇区或弧两面与预期不符，日志足以直接定位。

## 2026-10-31：N06 终验实机通过——邻接明确拒绝已实机生效

原始报告 `build/post090_n06_live_20261031T142644/report.json`（SHA256 `5fd12b29…fe768`，`run_id=20261031T142644_dc902bac`，`mode=live`，`passed=true`，`stopped=null`）。本节只追加，不改写上方 2026-10-28～31 的迭代记录。

**邻接明确拒绝（`adjacent_bend_ends`）已在实机按设计生效**：第三墙不再进入再生失败，而是**创建前就被原生预检拒绝**，revision 不变。

| 组 | 底板 model / 作业 | 墙作业 | rev | 结果 |
| --- | --- | --- | --- | --- |
| `ny_first` | `559909ffe92d4202b5d1ecc93f6599a5` / `d69ea37cbc1846418de8b2c32b989281` | `f_ny` `40aae64263a24e65b9e3d360bf435360` | 1→2 | **自由壁建成**，体积 42920.0→57293.61585482106，`saved_file_reloaded_and_verified=true`，`outcome=free_wall_built` |
| `px_then_ny` | `6fb3d627e480477086c5c9db379344d6` / `9582ae64991648acba88fe512acaaf40` | `f_px` `a114cd70e0a94e30a1b90aa8c9d3d855` → `f_ny` `f706af6a78f1483c9a6ce20586605c15` | 1→2，2→**2 不变** | `f_ny` **fast-fail `adjacent_bend_ends_rejected`** |
| `px_nx_then_ny` | `eb91bdf54c6d45a085087dc7a559b5de` / `d7557ac06ed04673861bb9ed3d50f693` | `f_px` `51886e0916b340bab6f4b815ee9812e6` → `f_nx` `42e5e30a9a0f4ca6b0f4b4d4b83fb597` → `f_ny` `94ea4ea25c5b42e3887aafe9688e41aa` | 1→2→3，3→**3 不变** | `f_ny` **fast-fail `adjacent_bend_ends_rejected`** |

取证细节（原生 `flange_failure_evidence`，`stage="before_create"`）：`px_then_ny` 的 `f_ny` 附着边 id 197、长 181.46 mm，两端中 **end1** 命中——邻接弧边 201、半径 2.54 mm（= R2.54）、折弯面 [193]，在折弯退让界限 7.081 mm 内，end0 的邻边 125 是直边不命中；`px_nx_then_ny` 的 `f_ny` 附着边 id 296、长 177.92 mm，**两端均命中**（end0 邻接弧边 298/折弯面 [292]，end1 邻接弧边 201/折弯面 [193]）。两次拒绝的作业终态均为 failed、`toolkit_code=-1`、`rollback_succeeded=true`、`failed_stage=execute_sheetmetal_flange`，消息明确 "sheetmetal_flange rejected before create (failure_reason=adjacent_bend_ends) … 本构建不实现角部释放或斜接，故在提交前拒绝该墙"，并指明四壁尚不支持（FEAT-014 保持开放）。

`trim_probe` 组仍为 `trim_ignored`：完整墙与 `end_trim_mm=20` 修剪墙体积同为 60945.29123405193（增量 18025.291234051932，与基线一致），`setback_confirmed=false`，候选分类中 `trim_ignored` 与基线相同、`setback_from_ends`=14917.482400023644、`length_from_section`=1553.9044166691294、`length_both_sides`=3107.808833338259 均不匹配——trim 语义**仍未确定**，不能用于角部让位。

**能力边界不变**：报告 `capability_claim.four_walls_complete=false`；邻接拒绝是"已知边界按设计生效"，**不是四壁能力达成、也不是触发条件的复现**；corner relief / miter 仍未实现，3/4 仍是上限且第 3 墙被明确拒绝。

**迭代历史（如实记录）**：本轮前已有两轮预检修复——①`ProEdgeNeighborsGet` 的轮廓邻边不保证分属两端，改用 `ProEdgeVertexdataGet` 按端扇区枚举（`582c1a3`）；②端点行被后续直边邻边覆盖导致 summary 取到 null 值崩溃，改为保留首个命中行并对 summary 判空（`b5dce10`）。此前两次实机（`build/post090_n06_live_20261031T134730/`、`build/post090_n06_live_20261031T142121/`）的第三墙仍是 `trigger_reproduced`（前者为再生失败 `feature_status=6`，后者为原生异常 "[json.exception.type_error.302] type must be number, but is null"），本轮 `142644` 才首次得到 `adjacent_bend_ends_rejected`。

## 2026-10-31：N01 relief 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n01relief/run1/report.json`（SHA256 `cefce8ed…643a`，`run_id=20261031T133009_e33744d9`，`mode=live`，`passed=true`，`stopped=null`）。本节只追加。

- **relief_none / relief_rect_1x1 判 `known_t05_boundary`（passed=true）**：两案底板 42920.0 mm³、rev 1。`relief_none`（model `f5c640ff5bee4ebcae312f08a8443372`）与 `relief_rect_1x1`（model `ceb6abdd9a414fca98200cf08a1af5de`）的 `f_px`/`f_nx` 两道自由端折边均 succeeded（各 +18025.291234 mm³，误差 ~6.9e-7，重载 true），第三道 `f_ny` 失败并按双侧正证据归类为 `known_t05_boundary`（原生消息 "Regeneration produced a failed, suppressed or incomplete feature"、`rollback_succeeded=true`、revision 3→3）。案卷 `known_t05_boundary=["f_ny"]`、`relief_geometry_unverified=["f_ny","f_py"]`——**释放几何在受阻折边上仍不可观测，如实记为未验**。
- **材料矩阵全部 `known_t05_boundary`**：`mat_baseline` 与四组 `mat_rect_*`（`mat_rect_both_1x1`、`mat_rect_both_4x4`、`mat_rect_side1_1x1`、`mat_rect_side2_1x1`）的底件均 succeeded、rev 1、体积 42920.0，`wall_contract.part_thickness_mm=1.0`（`part_thickness_synced=true`，`part_thickness_before_mm=3.71`），`f_px` 自由端建成（+18025.291234 mm³），目标 `f_ny` 失败并归 `known_t05_boundary`（`verdict.reasons`："目标折边被已证的 T05 边界挡住（附着边端部与既有折弯相邻）；此场景下释放几何不可观测"）。**relief 几何在这些场景下不可观测，如实记录，不冒充已验。**
- **自由端释放真实建成通过**：`free_rect_both_4x4`（model `b6845c6048cf49ce9aeb7e27554d294e`，底件 job `4ae4f30dc1154e808be8aec94e9d5099`）的 `f_px` 自由端折边 succeeded，rev 1→2、+18025.291234051932 mm³，`saved_file_reloaded_and_verified=true`，`relief_echo` 与 `relief_element_echo` 齐全（side1/side2 宽深各 4.0 mm、blind、`length_type=-31`、`type=3`），`verdict.scenario="free"`、`passed=true`、`reasons=[]`。按自由端口径，**差分为 0 属预期**（`profile_comparison` 中 `f_px`/`f_nx` 的 `measured_delta_mm3=0.0`、`notch_faces_with_relief=0`），故此例证明的是"请求被真实接受并建成 + 元素树回显一致"，**不是"释放几何在材料端生效"**。

释放能力总体状态不变：**自由端真实建成、元素回显一致，但材料端的释放几何本轮仍不可观测**（T05 边界挡住了第三墙）。四壁不支持、corner relief/miter 未实现的边界同样不变。


## 2026-11-01 Q15 离线集成状态

离线开发完成，待实机验收。来源及合并提交见 [Q15 集成报告](DEV-053-Q15-integration-2026-11-01.md)。此状态不表示原生构建、Creo 实机、主干合入或发布完成。

## 2026-11-02 第十轮反馈对接：壁面归属另立 BUG-103，本卡边界不变

来源：[0.10.0 第十轮反馈 F01 §二](../validation/feedback-0.10.0-2026-10-31/MAPPING.md)（[原件](../validation/feedback-0.10.0-2026-10-31/originals/2026-10-31_CREO_0.10.0_水平底板底边无法挂折边_R2仍未解决.md)）。

- **复述确认**：YZ 配方 185×232×1 底板体积正确，四条下边均 Z=0；`f_px`(104)/`f_nx`(105) 成功，`f_ny`(106) 报 `ProSmtedgeContourGet=-8`，`f_py` 未执行并整批回滚。与本卡 T05/N05/N06 记录的“第三道被挡”为同一现象族。
- **本卡已交付的可用诊断**（不重复开发）：`wall_contour_status=eligible|ineligible|unknown` + `wall_contour_query_code`（每边一次查询、256 边预算、按 revision 标注，`native/generic.cpp:419-431` / `src/creo_mechdog/sheetmetal.py:177-260`）、`wall_contract.wall_face_ids`、`parameter_hint`（`thickness >= depth` 时触发，`native/advanced.cpp:624-683`）。`eligible` 不解除 `adjacent_bend_ends` 创建前拒绝。
- **口径矛盾（新增待核对项）**：`advanced.cpp:1396-1412` 的折边失败文案推荐“YZ 平面单线 + depth=板长 + thickness=板厚”，而该反馈正是用此配方失败。文案与 `examples/sheetmetal_base_yz.json` 的指引必须与本卡实测一致，否则会继续误导。
- **分工**：**“为何只有 X=±92.5 短边进入壁面轮廓”的归属定因、人工 UI 对照与配方/准入口径归 [BUG-103](BUG-103.md)**；本卡继续负责四壁/corner relief/材料端释放几何能力，`four_walls_complete` 在第三、四壁真实建成并全链路通过前保持 false。
- A 层矩阵（A1 `ny_first`、A2 `order_ny_second`、A3 trim 读数组、A4 自由端 relief 扩展）与 B 层受限诊断门槛沿用 [交接记录](../development/FEAT014-CORNER-INVESTIGATION-2026-10-31.md)，本轮未执行、未连接 Creo。

## 2026-11-06 四壁/角部对比实机重跑——邻接拒绝仍按设计生效，四壁保持不支持

源码提交 `4201f84`（分支 `codex/FEAT-039-w02-w06-live`；工作树另有其他会话文件，本报告未记录源码指纹），环境 Windows x64 / Creo 12.4.0.0 / 匹配 SDK；原始报告 `build/post090_n05_live_20261106T1505/report.json`（SHA256 `046702f2d2642697ec82e2d674de293821c02700b07a87e63e808072f18e1cf7`，`run_id=20261106T145942_62f3136c`，`mode=live`，`passed=true`，`stopped=null`）。单服务 `MCP_CREO_MechDog_dev`，每道墙一个 job、失败不重交；提交前已确认会话可操作（CREO 启动与挂接阻塞已解除）。

| 组 | 底板 model / base job | 墙作业与 rev | 结果 |
| --- | --- | --- | --- |
| `ny_first` | `689fa772dbc14c46acff50ec92815c86` / `820e4992e78c42648a55af8ad4842ca5` | `f_ny` `2887bd458c63471dab17c71a506bf3d1`，1→2 | **自由首壁建成**，42920.0→57293.61585482106 mm³，`saved_file_reloaded_and_verified=true`，`outcome=free_wall_built` |
| `px_then_ny` | `a240f7c6baa94fe4a470186e9f95592a` / `1e69a18b1c4b4f95baf23cd929b3f682` | `f_px` `50b7a3b906994c228d2e4399f3034aec` 1→2；`f_ny` `1f9b7f51e07342e8a9ac178032744faa` 2→2 | `f_ny` 创建前拒绝 `adjacent_bend_ends`，附着边 span 181.46 / 期望 185（单端邻接弧） |
| `px_nx_then_ny` | `16f525357629443ca5263798a4f9bf7f` / `01e9b839d57a476088b94afa289aaec7` | `f_px` `ed9a7546a01c4dbb813782d56e89a78c` 1→2；`f_nx` `36c0875c24d942f8a1931711723cb54c` 2→3；`f_ny` `1899bde72e67478daa589b297f6de98b` 3→3 | `f_ny` 创建前拒绝 `adjacent_bend_ends`，附着边 id 296、span 177.92 / 期望 185，两端均命中邻接弧（298/201，R2.54，折弯界限 7.081） |

- 两次第三壁拒绝均为 `terminal_status=failed`、`toolkit_code=-1`、`failed_stage=execute_sheetmetal_flange`、`rollback_succeeded=true`，revision 与体积不变（`revision_restored=true`、`volume_restored=true`），失败原文带 "no corner relief or miter route is implemented … four-wall boxes are not supported yet"。
- `trim_probe` 仍为 `trim_ignored`：完整墙与 `end_trim_mm=20` 修剪墙体积同为 60945.29123405193（job `c0f6c4ffa4f64db2a4ac9e016d594200` / `044db8125d0a49b190739c13fefb1d7d`），`setback_confirmed=false`；trim 不能用于角部让位。
- **判定**：本轮只执行了 R09 第 3 项（分离资格/邻接/材料干涉）。结论是第三壁在 1 角与 2 角上下文都被既有的创建前邻接保护拒绝，失败发生在 `before_create`，**不构成 corner relief/miter 的几何证据，也不解除任何四壁门禁**。第 4—6 项（真实角部去料/缺口几何、逐 op 重解析、实机四壁保存重载）仍 blocked：没有已实现的 corner relief/miter 路线，且 `end_trim_mm` 实测被忽略。FEAT-014 保持开放，`four_walls_complete=false`。
- **未验证**：第三壁若绕过保护进入再生的内部机理（截面越界 vs 相邻料重叠）、真实角部缺口几何、材料端释放几何、四壁保存重载。

## 2026-11-06 第二段：miter cuts 路线实现与实机

路线选择：`ProSmtFlangeWall.h` 的 `PRO_E_SMT_MTR_CUTS` 与折边同特征创建，宽度/偏移用 BLIND 直接数值（GAP 实测被重置为 PARAM，见下）；不用需要三条角部引用的独立 `ProSmtCornerRelief` 特征。调研与取舍见 [2026-11-06 计划](../superpowers/plans/2026-11-06-feat-014-miter-cuts-route.md)。

改动：

- 原生 `native/advanced.cpp`：新增 `FlangeMiterRequest`/`flange_miter_request`（`miter_cuts {width, offset}`，布尔/非正/负偏移拒绝）；`adjacent_bend_ends` 保护改为「无 `miter_cuts` 才拒绝」，放行时把原邻接证据带 `allowed_by_miter_cut=true` 记入 `adjacent_bend_ends_allowed`；元素树在 `PRO_E_SMT_BEND_RELIEF` 之后写 `PRO_E_SMT_MTR_CUTS`（ADD=TRUE、WIDTH_TYPE=BLIND、WIDTH_VAL、OFFSET_TYPE=BLIND、OFFSET_VAL；`KEEP_DEF_AREAS` 不设）；创建后从已建特征树回显并逐项核对，不一致即失败。
- Python：`src/creo_mechdog/schema.py` 新增 `FlangeMiterCuts` 与 `SheetmetalFlangeOp.miter_cuts`（offset 省略等于 width）；`server.py` 增加同名可选参数与 `operation["miter_cuts"]`；`capabilities.py` 与 `docs/REFERENCE_SYNTAX.md` 口径改为「miter_cuts 是唯一放行方式，切角量待定标」。
- compact 投影：`src/creo_mechdog/job_projection.py` 的 `sheetmetal_flange` 判据增加 `miter_cuts`、`adjacent_bend_ends_allowed`，避免精简轮询丢掉放行证据。
- 驱动 `tools/test_sheetmetal_box_live.py`：新增 `run_miter_probe`（同一自由首壁带/不带 miter 的两块新模型，按实测体积差分类 `gap_measured`/`no_measurable_cut`）与 `run_miter_box`（`+x`、`-x` 自由，`-y`、`+y` 带 miter，一墙一 job）；`four_walls_complete` 只在四墙全部成功、测量齐全且每墙 `saved_file_reloaded_and_verified=true` 时为 true。
- 单测：`tests/unit/test_sheetmetal_flange.py` 增加 miter schema 用例与保护放行源码契约；`test_sheetmetal_relief.py` 的「未实现形状」清单移除 `PRO_E_SMT_MTR_CUTS`。

离线验证：`bridge.py build` 通过；`tools/test_unit.py`、`tools/dev_check.py` 通过；`tools/test_sheetmetal_box_live.py` 离线 62 用例通过。

实机（2026-11-06，Creo 12.4.0.0，`--live --confirm-session-usable`，单通道一墙一 job）：

- 首次运行 `build/post090_n05/20261106T161433_254305b2/report.json`：GAP 型提交后 Creo 把宽度/偏移类型重置为 PARAM（-18/-19）并把值清 0，创建后回显核对按设计抛错，任务失败回滚（revision 1→1、体积不变）。这证明回显核对能拦住静默重置，也证明 GAP 不是本上下文的直接数值类型。
- 改用 BLIND（`PRO_DIM_ENTER = -4`）重编后 `build/post090_n05/20261106T163234_c086ae9d/report.json`（sha256 `a83f6eea…`，整体 `passed=true`、`capability_claim.four_walls_complete=true`；另有一次同结果运行 `20261106T161949_61da6c2a`）：
  - `miter_probe`：自由首壁带/不带 `miter_cuts` 各建一块新模型，加料体积均为 18025.29 mm³，差值 0 → `classification=no_measurable_cut`。回显 `add=1`、`width_type=-4`、`width_mm=1`、`offset_type=-4`、`offset_mm=1`。自由壁没有重叠可切，此结果只说明该位置无副作用。
  - `miter_box`：`four_walls_complete=true`。`f_px`、`f_nx` 自由壁成功；`f_ny`（附着边 span 177.92，两端邻接折弯）带 `miter_cuts` 成功，回显 `allowed_by_miter_cut=true` 与两端邻接证据；`f_py` 同样成功。四墙均 `saved_file_reloaded_and_verified=true`，revision 1→5，体积 42920 → 106499.16 mm³。模型树为 `F_PX`/`F_NX`/`F_NY`/`F_PY`，Creo 中可见四壁闭合盒子与角部斜切线。
- **仍未量化**：`miter_cuts` 的 width/offset 与实际切除量之间的关系（自由壁探针为空操作对照；角部无法做「不传 miter」的反例，因为保护会拒绝）；角部间隙的尺寸、不同板厚/半径下的行为，以及删除/修改后的回滚，均未验证。结论只到「四壁经 miter_cuts 路线建成并保存重载」，不外推切角尺寸。

### 2026-11-06 R09 复跑与报告身份（Creo 12.4.0.0）

命令：`.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live --confirm-session-usable`；
报告 `build/post090_n05/20261106T203424_b183d2c8/report.json`（`passed=true`，六组全过）：

- `trim_probe`、`ny_first`、`px_then_ny`、`px_nx_then_ny`、`miter_probe`、`miter_box` 全部 `passed=true`；`miter_box` 的 `f_px`/`f_nx`/`f_ny`/`f_py` 四墙均 `saved_file_reloaded_and_verified=true`，`four_walls_complete=true`，`miter_cuts{width=1,offset=1}`。
- 报告新增 `source` 身份块：`commit=a88900cf…`（分支 `codex/DEV-069-feedback-repair`）、`dirty=true`、`source_sha256`/`source_fingerprint`、`worker_sha256=e76a831a…`；顶层 `capability_claim.four_walls_complete` 与 `miter_box` 判定一致，不再出现 161949 那种顶层 false/组 true 的错位。
- **仍未验证**：native_planar+resize 路径、角部切除量与缺口 bbox 定标、板厚/半径独立矩阵、删除/失败修改回滚；本项只关闭“基础路线复跑与报告身份”，不关闭上述子项。

## 2026-11-06 R09 剩余三项：native_planar 路径、切角定标与后续行为（Creo 12.4.0.0）

驱动 `tools/test_sheetmetal_planar_box.py`（默认离线；`--live --confirm-session-usable` 才连接），报告 `build/sheetmetal_planar_box/20261106T212525_1018e92f/report.json`（`passed=true`、`stopped=null`，sha256 `3fffaf07b9686227cee4e6ef8cd8a1567c084ee57d1f856aed634073a043e607`）；源码 `commit=95b9114`（分支 `codex/DEV-069-feedback-repair`）、`dirty=true`、`source_fingerprint=47739186…`、`worker_sha256=e76a831a…`。全部串行单通道，一次运行内不并发其他 MCP 调用。

**native_planar + resize**：`creo_new_sheetmetal(template=native_planar)` 建 180×230×1（41400 mm³，rev 2）；单独作业 resize 到 185×232×1 得 42920 mm³、`thickness_measured_mm=1.0`、`thickness_loaded_mm=1.0`、`feature_id_unchanged=true`、保存重载 true、revision 3。随后四道折边逐 job 从当前顶边选边，`f_px`/`f_nx`（自由）与 `f_ny`/`f_py`（`miter_cuts{width=1,offset=1}`）全部成功、每墙保存重载 true，终 bbox `185×232.1×80`、体积 `106499.15656`，与 `sheetmetal_wall` 转换首壁路线一致。

**切角定标（按面 bbox 实测，不用元素回显）**：水平顶面 run 与真实附着边长比较——`f_px`/`f_nx` 顶面 `run=232.0` = 附着边 `232.0`（`matches`）；`f_ny`/`f_py` 顶面 `run=185.0` 超过已被折弯缩短的附着边 `177.92`（`exceeds`，+7.08 = 2×3.54 退让，各含 5 个顶面片）。四角缺口面按面 bbox 记为 `corner_square_mm=[6,6]`（如 `+x+y` 3 个面）。同几何换参矩阵：gap 2.0@R2.54 → 106074.619423（Δ−424.537137，÷4=−106.134284/角）；gap 1.0@R1.5 → 107041.242367（Δ+542.085806）。体积差分只作 cross-check（独立墙体增量会双计角部材料），不当作“未切角体积”或切角量真值。

**后续行为（同一模型 followup）**：`creo_sheetmetal_unbend` 全展开 rev 7→8、体积 106499.15656→106181.93079、保存重载 true；`creo_sheetmetal_bend_back` rev 8→9、体积回到 106499.15656；带子特征的父壁 resize 在被提交前拒绝、rev 9→9；无效边（id 999999）折边 `status=failed`、`rollback_status=succeeded`、rev 9→9、体积不变。产品没有“折边高度编辑/删除折边”操作，两项按无该能力记录，不模拟。

**边界**：本轮验证的是 miter_cuts 固定 1/1 基线、两组换参、native_planar 路线与展开/折回/失败回滚；relief 材料几何、更大厚度/半径范围、跨计划多级改型仍未覆盖，FEAT-014 的 relief 子项保持开放。


## 2026-11-07 离线接续（未发布）

DEV-071补齐aliases-only的miter_cuts/adjacent_bend_ends_allowed到公开操作回执：新收尾及历史受控sidecar只读投影，compact/full/sections同源。回执保留dict，缺字段不伪造成功。原生切角语义不变。 见[DEV-071](DEV-071.md)与[三件反馈映射](../validation/feedback-0.16.0-2026-11-07/MAPPING.md)。
