# FEAT-058 / H01：非零 origin 大跨度 resize 的实机根因与修复（Creo 12.4.0.0，2026-11-07）

关联条目：[FEAT-058](../../work-items/FEAT-058.md)、[DEV-074 接手清单 H01](../../development/DEV-074-HANDOFF.md)。外部反馈原件在
`docs/validation/feedback-0.17.4-2026-11-07/originals/`（本节未改动其任何字节）。

## 1. 环境与来源

- Windows x64，Creo 12.4.0.0（`config.json` 的 `creo_root`），用户已手工启动 xtop，`auto_start_creo=false`；本轮未启动/关闭 Creo、未清 unknown、未做故障注入。
- 执行时工作区分支为 `codex/DEV-075-feedback0181-offline`（任务给定起点为 `codex/DEV-074-feedback0174-offline`/HEAD `828b1f2`，执行期间另一 agent 切到该分支并改动工作区；本证据对应的工作区源码即下文所列文件）。
- 执行器：`build/creo_worker.exe`（13 784 064 B，SHA256 `71EE9AD462AEB5A10B93B978F596C47C390C7B97615D614EA1DE5E63DF5FE0C1`），`bridge.py build` 退出 0。
- 受测源码 SHA256 见各矩阵报告的 `source.source_sha256`（`native/planar_wall.cpp`、`native/planar_wall.h`、`native/generic.cpp`、`src/creo_mechdog/native_planar_wall.py`、`tools/test_planar_wall_origin_resize.py`）。

## 2. 已报告的缺陷（复现）

`origin=[-92.5,-116]`、185×232×1 → `resize 100×60` 在修复前解出 v 跨度 172（`[-116, 56]`），体积 17200 ≠ 6000，被体积守卫回滚。

本机同一会话复现：`build/h01_probe/20261107T190058.json`（job `9f721835d84d44ff8c6c63d547f542f8`），
原生日志摘录见 `artifacts/native_prefix_resize_failed.log`：

```
PLANAR_WALL_RESIZE axes u=1,v=0 slope=1,-1 offset=0,0 origin=-92.500000000,-116.000000000
PLANAR_WALL_RESIZE_CORNER phase=before entity=wall_1 start=116,-92.5 end=-116,92.5
PLANAR_WALL_RESIZE_DIMENSION name=coord_wall_1_end_y id=7 recorded_signed_mm=-116 target_signed_mm=56 current_mm=116
PLANAR_WALL_RESIZE_CORNER phase=after_solve entity=wall_1 start=116,7.5 end=-56,7.5
PLANAR_WALL_VOLUME phase=resized measured_mm3=17200.000000000 expected_mm3=6000.000000000
```

（行内数值已截断；原始行见摘录文件。）修复前报错已附实测包络：`measured u=[-92.5,7.5] v=[-116,56] n=[0,1]`。

## 3. 实测到的尺寸语义（不是推断）

截面定位矩阵（XY、命名平面、`origin=[-92.5,-116]`）：

```
m = 0,-1,0,0 ; 1,0,0,0 ; 0,0,1,0 ; 0,0,0,1
```

即 section x = −frame v、section y = +frame u。初始矩形在截面坐标为 x∈[−116,116]、y∈[−92.5,92.5]。
`dimension_count=5` 的 5 个尺寸实测为（`ProSecdimReferencesGet` 的 `entity:point`）：

| 名称 | id | 类型 | 引用 | 当前值 | 有向记录值 | 写入值（修复后） |
| --- | --- | --- | --- | --- | --- | --- |
| `coord_wall_0_end_x` | 6 | 8 = PNT_PNT_VERT | 2:4（坐标系原点）, 5:3（wall_0 终点） | 92.5 | +92.5 | +7.5 |
| `coord_wall_0_start_x` | 4 | 8 | 2:4, 5:2 | 92.5 | −92.5 | +92.5 |
| `coord_wall_0_start_y` | 5 | 7 = PNT_PNT_HORIZ | 2:4, 5:2 | 116 | +116 | +116 |
| `coord_wall_1_end_y` | 7 | 7 | 2:4, 6:3（wall_1 终点 = 上边另一角） | 116 | −116 | **−56** |
| `coord_wall_2_end_x` | 8 | 8 | 2:4, 7:3 | 92.5 | −92.5 | +92.5 |

结论：矩形 4 个角只需要 4 个坐标分量，但坐标标注对每个非共享顶点分别标注，且相邻水平/竖直线段共享的那一维被跳过，因此是 5 个（`wall_0` 起点 2 个 + 终点 1 个、`wall_1` 终点 1 个、`wall_2` 终点 1 个）。每个尺寸都是"到截面轴的距离"，值是**沿该尺寸自身创建方向的有向距离**；方向在创建时固定，无法从数值本身读出。

尺寸 id 4/6/8 是 `PRO_TK_DIM_PNT_PNT_VERT`（截面 y），id 5/7 是 `PRO_TK_DIM_PNT_PNT_HORIZ`（截面 x），与 `COORDINATE_AXES` 的 `_x`/`_y` 后缀（按 frame 轴命名）一致，不是按截面轴命名。

## 4. 追加实验：负值可以把角点翻到轴的另一侧

在新建的同参数模型上只改 `coord_wall_1_end_y`（`set_sketch_dimensions`，与原生 resize 走同一段 `ProSecdimValueSet`+`ProSectionRegenerate`+redefine 代码），
证据 `artifacts/negative_dimension_experiment.json`：

| 写入值 | 实测 bbox | 体积 | 结论 |
| --- | --- | --- | --- |
| −56 | y `[-116, -56]` | 11 100 = 185×60×1 | 负值使该角点落到轴的另一侧 |
| +56 | y `[-116, 56]` | 31 820 = 185×172×1 | 正值保持原侧 |

修复前的 `fabs()` 写法永远落在原侧，所以跨过原点的目标尺寸必然解成 2×|origin|±… 的错误跨距。

## 5. 修复（`native/planar_wall.cpp`）

1. `planar_wall_dimension_side()`（[425–461 行](../../../native/planar_wall.cpp)）：用 `ProSecdimReferencesGet` 找到该尺寸引用的线段端点，按 `value = side × coordinate` 求方向 `side = sign(value × coordinate)`。
   这一步是必需的：方向只能由"当前值 + 当前点坐标"实测得出，**不能**用记录尺寸推导（见 §6 的连续改型失败）。
2. 写值 `written = side * resized_coordinate`（[874–897 行](../../../native/planar_wall.cpp)），替代 `fabs(resized_coordinate)`；读回校验改为 `fabs(fabs(current) - expected)`，允许 Creo 以负值保存该尺寸。
3. 诊断（未删除守卫）：`PLANAR_WALL_RESIZE_LOCATION`（定位矩阵）、`PLANAR_WALL_RESIZE_CORNER`（求解前后四个角点的截面坐标）、`PLANAR_WALL_RESIZE_DIMREF`（类型/引用/放置点）、`PLANAR_WALL_RESIZE_ENVELOPE`，并在体积不符时报错附带实测 u/v/n 包络（[379–400 行](../../../native/planar_wall.cpp)）。

未改动：feature id、origin、厚度、`origin=[0,0]` 路径（该路径下所有坐标非负，`side` 恒为 +1，写入值与旧实现逐字节相同）、体积/包络/子特征/身份守卫。

## 6. 一次中间版本的失败（保留为证据）

第一版按"记录值的符号"推断方向。首例通过，但连续改型 100×60 → 150×180 失败：体积 7800，实测 v `[-116,-64]`。
原因是方向属于尺寸本身、不随当前几何翻转（首改把该尺寸写成 −56 后，记录值变成 +56，符号推导反转）。这直接促成了 §5.1 的实测方案。
中间版本报告：`build/planar_wall_origin_resize/20261107T190710_b2caf981/report.json`（未归档，仅记录现象）。

## 7. 实机矩阵（全部 Creo 12.4.0.0，同一会话，串行提交）

驱动：`tools/test_planar_wall_origin_resize.py --live --confirm-session-usable`；每个用例都断言：任务成功、体积、实测 bbox、原生包络、feature id 前后一致、origin、厚度、`saved_file_reloaded_and_verified=true`、revision 前进。

| 用例 | 参数 | create job | resize job | 体积 mm³ | bbox mm | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `xy_neg_cross` | XY+，origin(−92.5,−116)，185×232→100×60（跨过） | `9ac43f8f86ae4b2594f5ae51b092fa40` | `c408c6796ab2489e900ab7e70727bbfa` | 6000 | `[-92.5,-116,0]..[7.5,-56,1]` | 通过 |
| `xy_neg_identity` | 同上，→185×232（恒等） | `c80d1f0d209b4c8eac277dbfa43ba1f2` | `9efc6c18f91946e2bdffb37d2f651b57` | 42 920 | `[-92.5,-116,0]..[92.5,116,1]` | 通过 |
| `xy_neg_shrink` | 同上，→180×230（小改） | `9f1763a5349e40f482708c9e3ecf841f` | `37263f7847614650b4f63b1c2447dd47` | 41 400 | `[-92.5,-116,0]..[87.5,114,1]` | 通过 |
| `xy_neg_no_cross` | 同上，→100×200（v 不跨） | `652e7902c3294f239d73235c68c0c49f` | `ad77c73c90d34afab0bc5b6fc3211c5e` | 20 000 | `[-92.5,-116,0]..[7.5,84,1]` | 通过 |
| `xy_neg_cross_consecutive` | 185×232→100×60→150×180 | `a0e77978bba2448fbfbcf3439313ae2c` | `b49d029a970a4f6381f5e36b1eef859c`、`a0366dd7d6e04c0d919e167e7d8af77f` | 6000→27 000 | `[-92.5,-116,0]..[57.5,64,1]` | 通过 |
| `xy_neg_grow` | 100×60→185×232（放大跨过） | `7b361bc3bb444ad7bdc2e379b052a6cd` | `5f91aba0854940d4adfb8bf79f67e66f` | 42 920 | `[-92.5,-116,0]..[92.5,116,1]` | 通过 |
| `xy_zero_cross` | origin(0,0)，185×232→100×60 | `439019b35f924fbda60a5c8398b0ef76` | `ff1600a0b6ad46b1bccb71e7d732265c` | 6000 | `[0,0,0]..[100,60,1]` | 通过 |
| `xy_positive` | origin(60,40)，100×60→60×40 | `8c62c0387aa248e09459c69eafb5e52d` | `fe4050d14a9148dfa63f0b9d18eac846` | 2400 | `[60,40,0]..[120,80,1]` | 通过 |
| `xy_mixed` | origin(−92.5,40)，100×60→50×30（u 跨） | `603154ec7a4b4e999d585c36acbde9ff` | `71f2d0ae3d4b4ef6b96cb50fafafd5da` | 1500 | `[-92.5,40,0]..[-42.5,70,1]` | 通过 |
| `xz_neg_cross` | XZ+，185×232→100×60 | `2953c4363da849e59c15ea6e46e0ba55` | `342be25eb88b4dabb6c8fd194e2ed3e5` | 6000 | `[-92.5,-1,-116]..[7.5,0,-56]` | 通过 |
| `yz_neg_cross` | YZ+，185×232→100×60 | `49a8d42884f74ff8942e35862d258107` | `67761b5f7f3a40ac8e95640d31b87387` | 6000 | `[0,-92.5,-116]..[1,7.5,-56]` | 通过 |
| `xy_neg_negative_direction` | XY，厚度方向 negative，185×232→100×60 | `27587abc4e6141e7be877a6f16feac28` | `e143772f69e049a58894b2d4f449206d` | 6000 | `[-92.5,-116,-1]..[7.5,-56,0]` | 通过 |
| `xy_neg_same_plan` | 同计划 create+resize 185×232→100×60 | — | `61d4f87e835e4ee0a703ece625552c72`（同一 job） | 6000 | `[-92.5,-116,0]..[7.5,-56,1]` | 通过 |
| `xy_neg_save_reload` | 185×232 → save/reload（rev2）→ resize 100×60 | `237ba0d6fa0a4bb0b57c5c232c079700` | save `2c00395f4adb42c0b3dced74ff5775f8`；resize `f4fc899501c04a8180e83f65aa0d096f`（rev3） | 6000 | `[-92.5,-116,0]..[7.5,-56,1]` | 通过 |

报告与 SHA256：`artifacts/20261107T191757_bf1a2865_report.json`（4 例，`543b095a…`）、`20261107T192000_36175391`（3 例，`b8a8649f…`）、
`20261107T192146_38dee554`（3 例，`e5bff464…`）、`20261107T192325_86be80e9`（2 例，`5e5a6e9a…`）、
`20261107T192511_5297e0fa`（同计划，`92a487e7…`）、`20261107T192854_2dc6287f`（保存重载，`3a935b21…`）。完整 SHA 见同名 `.sha256`。

分批执行的原因：会话通道与其它客户端共享，执行期间另一个 MCP 客户端反复调用 `session_status` 占用通道，
驱动的提交被 `ToolkitBusy` 合法拒绝（拒绝先于受理，未重投已受理任务）；驱动据此结束本次运行并记录 `stopped_at_case`，
剩余用例在下一批执行。`build/planar_wall_origin_resize/20261107T192325_86be80e9` 的 `stopped` 字段即为该次拒绝原文。

## 8. 编译与测试

- `bridge.py build`：退出 0（worker `71EE9AD4…`，13 784 064 B）。
- `python -m unittest tests.unit.test_native_planar_wall`：53 项 OK（新增 `OriginCrossingResizeTest` 3 项：原生写入有向值、体积守卫附带包络、矩阵跨轴期望）。
- `tools/test_planar_wall_origin_resize.py`（离线）：`crossing_case_is_100x60_not_100x172=true`，14 个用例负载通过 schema。
- `tools/test_adoption_planar_wall.py`（离线）：`passed=true`；`tools/test_first_wall_origin.py`（离线）：10/10；`tools/test_sheetmetal_planar_box.py`（离线）：通过。
- `ruff check` / `ruff format --check`：两个改动 Python 文件通过。

## 9. 未覆盖 / 未验证

- **未做字面上的"会话擦除后重载"**：`creo_erase_session_models` 拒绝受管模型；把受管输出文件重新 adopt 会被拒绝（`managed_output`，复制到其它目录后为 `source_origin_mismatch`，说明模型仍在会话中）。
  本轮以"native save（含保存、重载、校验）+ 之后新 job 的 resize"和"跨 job resize（每个 job 都从存档读回壁体与厚度）"覆盖保存-重载路径。
- `tools/test_adoption_planar_wall.py --live`（77 项，含拒绝/回滚、XZ/YZ origin、同计划、跨作业）本轮两次被外部 `session_status` 占道打断（`ToolkitBusy`，`build/planar_wall/20261107T113051Z`、`20261107T113436Z`），未取得完整通过结果；该驱动上次完整通过记录仍是 2026-11-07 的 `build/planar_wall/20261107T023240Z`（修复前源码）。
- Creo 9 / Creo 10 实机未测（本机只有 12.4.0.0）；WorkBuddy 黑盒未做。
- XZ/YZ 的 `direction=negative` 组合、非轴对齐/旋转 frame 的 resize（原生仍会以"截面轴与记录 frame 不对齐"拒绝）、带下游子特征时的拒绝路径未在本轮重跑。
- 矩阵每例只用固定的矩形起点方向（`wall_0` 为 u0→u1 的边）；其它创建顺序的重排在创建代码中不可达，因此未测。
