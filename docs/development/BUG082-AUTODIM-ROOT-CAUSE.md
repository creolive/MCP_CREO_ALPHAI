# BUG-082 根因调查：在轴扇形 autodim 就地编辑再生失败（2026-10-26）

按 [0.5.0/0.5.1 反馈计划](0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md) Task 2 执行：先取证、后准入、再修复。本文记录调查环境、每步对照、假设排除与修复准入结论；修复实施与全套回归见文末。

## 环境

- Windows 11 Enterprise x64；Creo Parametric 12.4.0.0（`release_numeric=44`，匹配 Toolkit SDK）；Python 3.12.14。
- 受测源码：分支 `codex/bug082-feedback-plan-main060`，诊断批提交 `8b19917`（`BUG-082: trace on-axis autodim regeneration`）之后的工作区；`tools/dev_check.py --work-item BUG-082` success=true；`bridge.py build` exit 0。
- 驱动：`tools/test_editing_closeout.py`（stdio 直连 `server.py`，单一 Toolkit 通道串行，busy 即停）。
- 会话：`creo_session_status` connected=true、toolkit_code=0 后才开始提交；全程无并发、无故障注入。

## 原生阶段诊断（提交 8b19917）

`native/sketch_edit.cpp` 的 `generic_sketch_edit` 在四个阶段记录有界截面状态（尺寸/约束/实体各最多 128 项，`BUG082_*` 前缀）：`before_delete`（删除尺寸/约束前）、`after_rebuild`（实体重建后）、`after_solve`（`solve_profile` 后）、`after_redefine`（`ProFeatureWithoptionsRedefine` 后，经 `ProFeatureSectionCopy` 只读副本）。`native/sketch_solver.cpp` 的 `solve_profile` 补记 `SectionRegenerate` 返回码（Solve/Autodim 返回码原有）。查询失败只记原始码，不覆盖建模错误；不改变求解顺序与行为。

## 修改前失败证据

| 作业 | 组合 | 关键观察 |
| --- | --- | --- |
| `0cf38b56…`（2026-10-26 03:53，模型 `8aa3df0c…`） | autodim 创建 90° → autodim 编辑 90→80 | `failed_stage=execute_update_sketch_geometry`、`toolkit_code=-1`、message `Regeneration produced a failed, suppressed or incomplete feature`；trace：`before_delete` 1 尺寸+13 约束，`after_rebuild` 0+0，`SKETCH_SOLVE=-1`、`AutodimensionSketch=0`、`SectionRegenerate=0`，`after_solve` **1 尺寸**+12 约束；`failed_features` REV_SK id40/REV1 id51 均 status=6；`rollback_succeeded=true`，体积复原 2094.395102392602 |
| `713181e2…`（判别实验 E3，模型 `1209754d…` 创建） | autodim 创建 80°（E1 成功）→ autodim 编辑 80→90 | `after_solve` **0 尺寸**+13 约束；`UNHEALTHY_FEATURES`：REV_SK 尺寸 d0/d1/d10 全为 0.0、`sketch_constraint_count=13`、status=6；REV1 除 d9=360° 外 d5/d6=0.0、status=6；回滚干净 |

对照成功（同源码、同会话）：

| 作业 | 组合 | 关键观察 |
| --- | --- | --- |
| `20515e99…` | autodim 创建 90° | `SKETCH_SOLVE=-1`、`AutodimensionSketch=0`、`SectionRegenerate=0`，特征全部 ACTIVE，体积 2094.395102392602 |
| `1209754d…`（E1） | autodim 创建 80° | 同上返回码组合；succeeded，体积 2062.5765347066654 = 解析值（容差内） |
| `e72ffbdc…` 等 7 步（`onaxis_sector_coordinate_edit`） | coordinates 创建→编辑（改角/回程/改半径/回程+直接新建） | `SKETCH_SOLVE=0 mode=coordinates`、`AutodimensionSketch=SKIPPED_COMPLETE_COORDINATE_DIMENSIONS`；7/7 成功 |

枚举对照（SDK 头文件）：约束 type 0=SAME_POINT、1=HORIZONTAL_ENT、2=VERTICAL_ENT、9=COLLINEAR_LINES；实体 type 2=LINE、3=CENTER_LINE、4=ARC、6=COORD_SYS。90°→80° 时约束 13→12 的差异是几何自然结果（80° 的 l2 不再水平，HORIZONTAL 不再适用），不是约束丢失。

## 假设核对

| 假设 | 对照 | 结论 |
| --- | --- | --- |
| 实体替换/残留尺寸关联 | `after_rebuild` 0 尺寸+0 约束，无残留；变更实体 Delete+Add 后无约束引用已删除 ID（7、8） | 排除 |
| 推断约束丢失/引用悬空 | `after_solve` 约束全部引用存活实体；约束数变化与几何一致 | 排除 |
| 求解模式转换（`ProSectionSolve=-1`） | 创建（成功）与编辑（失败）solve 均返回 -1，非判别因素；`SECTION_ERRORS count=0` 不代表无约束问题（外部与计划均已提示） | 排除为直接原因 |
| 回转轴引用断裂 | 中心线经 Replace 保留原 ID；REV_SK/REV1 特征 ID（40/51）编辑前后一致 | 排除 |
| **autodim 欠约束 + 特征级重解失败** | 创建与编辑的 section 求解返回码完全相同，但创建的特征初次构建直接采用截面实体几何；编辑 `ProFeatureWithoptionsRedefine` 后特征级再生须从尺寸方案重解——autodim 仅留 0–1 个尺寸，无法支撑重解，REV_SK 与下游 REV1 留在 `PRO_FEAT_UNREGENERATED`（status=6），REV_SK 特征尺寸值被清零 | **确认（根因）** |

判别实验（`build/bug082_e1_probe.py`，stdio 直连，作业 `1209754d…`/`713181e2…`）：E1 autodim 直接创建 80° 剖面成功且体积等于解析值——证明 80° 剖面对 autodim 本身合法，失败是**编辑路径特有**，与外部"草图成功/回转失败"及本机"草图和回转均失败"的表现一致（两者都是特征级再生失败的投影）。

## 修复准入与实施

准入核对（计划 Task 2 Step 5）：能指向具体函数/阶段（`generic_sketch_edit` 的 redefine 后特征级再生 × `solve_profile` autodim 分支的欠约束尺寸方案）；有修改前失败与对照成功原始证据（上表）；函数改动、兼容影响与回归集合如下。

**修复**（`native/sketch_edit.cpp`，提交见下）：把 BUG-079 已有的"主平面 auto 编辑升级坐标尺寸"路由扩展到显式 `autodim`——升级条件由 `op.value("dimensioning","auto") == "auto"` 放宽为 `!= "coordinates"`。升级条件其余不变：主平面（normal 主分量 ≥0.99999）、实体类型受坐标模式支持、截面含坐标系。非主平面或类型不受支持时保持 autodim，失败仍按既有保护回滚。

**非静默契约说明**（公开行为变化，随版发布时写入版本说明）：响应 `solver` 信息记录 `requested="autodim"`、`used="coordinates"`；模型 aliases 的 `last_dimensioning` 保留请求值；工具描述与 [SKETCH_STABILITY_0.2.5.md](../SKETCH_STABILITY_0.2.5.md) 同步更新。显式 `coordinates` 语义不变；创建路径（`creo_create_sketch`、计划 `sketch`）的 dimensioning 选择不变。

**修复验证**（同会话，修复提交工作区）：

- E1/E3 探针复跑：E1 autodim 创建 80° succeeded（体积 2062.5765347066654）；E3 autodim 编辑 80→90 由 failed 转 **succeeded**，`SKETCH_SOLVE=0 mode=coordinates`，`solver: {"requested":"autodim","used":"coordinates"}`，坐标回读最大偏差 3.06e-15 mm，特征 ID 40 保留。
- 开环非法几何夹具（`build/bug082_e7_probe.py`）：autodim 编辑为开环剖面（l2 止于 (0,5)）→ failed、`rollback_succeeded=true`、`failed_features=[{REV1 id 51 status 6}]`——失败回滚与特征级诊断不依赖保留旧缺陷。
- 全套编辑专项实机：`tools/test_editing_closeout.py` **16/16 CASE_PASS**（含 BUG-079 离轴弧、BUG-062 中心线、legacy 夹具、reorder no-op、dimensioning 交替与新增四用例），`EDITING_CLOSEOUT_SUCCESS=1`。
- 离线：`tests.unit.test_editing_closeout` 14 项通过（含 `verify_onaxis_edits` 的 revision 链/显式模式/失败即停回归与几何公式参考值断言）。

## 边界与未测范围

- 非主平面、含样条/椭圆等不受坐标模式支持实体的显式 autodim 编辑仍走原生 autodim，欠约束时如实失败并回滚（既有边界，不全局拒绝贴轴剖面）。
- 外部 Windows 10 / Creo 9.0.0.0 / 0.5.1 环境未复测；本机 Creo 12.4 证据不外推。
- 外部报告的"coordinates/改半径也失败"未在本机复现过（本机修复前 coordinates 全部成功），保留外部待核对。
- 球体/半圆贴轴基线失败仍是本卡独立观察子项，未并入本根因。
