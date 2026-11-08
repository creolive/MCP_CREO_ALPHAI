# DEV-074 H08/H09 实机验收证据（2026-11-08）

环境：本机 Windows x64 / Creo 12.4.0.0（xtop 由用户手工启动，PID 14048）/ 匹配 Toolkit SDK；
`config.json` 的 `auto_start_creo=false`。未启动或关闭 Creo、未清 unknown 保护、未做故障注入、
未改动主工作区。工作树 `e:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-forming`，
源码起点 `8d08f11`；`bridge.py build` 通过。所有提交只经公开 MCP 工具、串行单通道，
被接受后只轮询，未重试、未重提。

驱动（本机 `build/` 生成物，不提交）：`build/dev074_live_acceptance.py`（A/B/C）、
`build/_gate_probe.py`（门禁复验）；均通过 stdio 自行拉起 `server.py`。

## A. surface_round / creo_surface_round：实机通过

构造：XY 平面 40×20 矩形草图 → 拉伸曲面 10 mm，quilt 70、4 面、1200.0 mm²、开放；
成员面 62/64/66/68。

| 步骤 | 作业 | 结果 |
| --- | --- | --- |
| 构造 | `31815a61e695408e944887b71cf23340` | succeeded，revision 1 |
| 相邻面 (62,64) R3 | `3dfc36030e4e42779f8fedf112a9d84a` | succeeded，revision 2 |
| 非相邻面 (62,66) R3 | `b9016b1c90c24f35bf6dfc207fca3ae1` | failed，整体回滚 |

相邻面成功回执：`face_count` 4→**5**、`area_before_mm2=1200.0` → `area_mm2=`**1187.1238898038469**、
`quilt_closed_native=open`、`closed=false`（`quilt_is_open`）、`has_solid=false`、
`solid_surface_count=0`、`material_measurement.status=not_applicable`、`feature_id=78`、
`feature_type=913`、`reference_application.applied_set_count=1/query_code=0`、
`saved_file_reloaded_and_verified=true`。重载后 quilt 70 仍 5 面 / 1187.1238898038469 mm²。

解析 oracle（1e-6 mm² 容差）：1200 − 2×3×10 + (π/2×3)×10 = **1187.1238898038469 mm²**，
实机值逐位一致。

非相邻失败回执：`feature_status=6`、`feature_id=114`、`feature_errors.element_errors.total=0`、
`effect_status=rolled_back`、`saved_file_reloaded_and_verified=false`；提交前 revision 2、
提交后 revision 2，quilt 仍 5 面 / 1187.1238898038469 mm²（面积不变）。
说明：非相邻面对按契约允许提交，由内核在再生阶段拒绝，未放宽任何校验。

原始报告：`A_surface_round.json`。

## B. surface_boundary_fill / creo_surface_boundary_fill：实机反证，门禁保持

### ① 平面闭合环（优先验证内核是否接受该树）

同一矩形草图的 4 条 `PRO_CURVE`（id 45–48；`feature_geometry` 中 type 62；type 25 是点，未混用）。
原生 `ProCurveXyzdataEval` 实测相邻端点最大间隙 `1.882820214045141e-31 mm`，链顺序/闭合校验通过。

| 作业 | create_code | extract_code | 抽取树元素 | feature_status | quilt_visit_code | quilt_count | 元素错误 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `4f1705caaa2d4899bc97e38803644ba7` | 0 | 0 | 107 | **6** | **-4** | **0** | total=0 |
| `cd7b435ffa9041e383f8816e6ed9f6e7`（同输入复现） | 0 | 0 | 107 | **6** | **-4** | **0** | total=0 |

两次均 `effect_status=rolled_back`、`rollback_succeeded=true`、
`saved_file_reloaded_and_verified=false`，revision 保持 1，模型无残留特征/几何。
抽取树保留 `PRO_E_BBL_ADD_CLOSED=1`（4 个 `PRO_E_STD_CHAIN_HOLDER`）并由内核补齐
`PRO_E_EXT_SURF_CUT_SOLID_TYPE=PRO_FEAT_DATUM_SURF` 与切向条件默认值（末条链 `-1/0/0.0`），
失败不是元素缺失，而是该树再生不出任何 quilt。

### ② 非平面闭合环

按验收优先级，平面环已否决该树，**未提交**非平面环（不用同一被否定树重复试探）。
非平面闭合填充仍无可用路线。

### 结论

`surface_boundary_fill` 已加入 `UNAVAILABLE_OPERATIONS`；`creo_surface_boundary_fill` 从 MCP
工具面移除（公开工具 107→106）。门禁复验见 `gate_probe.json`：`tool_count=106`、
`surface_boundary_fill_published=false`、提交返回
`Not available in the 0.18.4 release; no native job was queued. ...`（无 job_id）。
planar `surface_fill` 未改动，不作为回退。

原始记录：`B_planar_fill_failure_job1.json`、`B_planar_fill_failure_job2.json`、`gate_probe.json`。

## C. surface_curvature / creo_measure_surface_curvature：实机通过

| 用例 | 模型 / quilt | 作业 | 采样 | 实测 |
| --- | --- | --- | --- | --- |
| ① 平面 | `surface_loft` 800.0 mm²、quilt 61、1 面 | `584b0d9486694db383b4540fd9ede92c` | 12×12，144 面内 / 0 失败 | `max_abs_curvature_per_mm=0.0`；`min_curvature_radius_mm=null`、reason `zero_curvature`；`outside_contour_count=0` |
| ② R8 球面 | 半圆旋转 360°、quilt 74、804.247719319002 mm²、2 面（取 1 面） | `5c79b4c0afc8423592d19416da0ec54f` | 144 / 0 失败 | 曲率 **0.12500000000000003 1/mm**、半径 **7.999999999999998 mm** |
| ③ G1 | 4 面拉伸 quilt、相邻面 (62,64) | `a93e1248e6794984b60032c9d033d528` | 2 面 288 点汇总，G1 17 点 | 共享边 1 条、0 失败、`g1_max_angle_deg=90.0`、`threshold_deg=0.5`、`within_g1=false` |

容差：平面曲率断言 `==0.0`；球面曲率 |Δ|≤1e-6、半径 |Δ|≤1e-3 mm；G1 |Δ|≤1e-3°。
③ 的两面为垂直平面墙，90° 与几何一致，`within_g1=false` 与 0.5° 阈值一致。

只读：三次只读作业返回 `readonly=true`，模型 revision 均为 1（提交前后相同）。
观测（未改语义）：把同一 `surface_curvature` 操作经通用 `creo_execute_plan` 提交会按写作业
保存并推进 revision（本验收驱动曾误用该入口，得到 1→2）；只读语义由专用工具持有。

原始报告：`C_surface_curvature.json`。

## 文件校验

| 文件 | SHA256（仓库提交的 LF 字节） |
| --- | --- |
| `A_surface_round.json` | `B59E79F8312FFEF3F3F485280B2E822CCFE3694B6D0903023484D28AAF524EFB` |
| `B_planar_fill_failure_job1.json` | `55605B309A29940C01A2BE0367AB9F9240F70C3FE576592669B3C23CE7FF38CA` |
| `B_planar_fill_failure_job2.json` | `DC328A2D14D2000E62F462B3A09C8B997E0F0C3BE63F281C643DBB40463F384D` |
| `C_surface_curvature.json` | `A7406557D43E9105E37D856969E423E4708CEB03771901E6D2EC4A632A6382E9` |
| `gate_probe.json` | `68D80183872E7806DE1527F4F77665891887B6927A784EE814E114FECF74A6B5` |

## 未覆盖

- surface_round：变半径/full/chordal/through-curve/过渡、edge-chain（无 quilt 边 id 通道）、
  多组、弯曲 quilt、圆角后 thicken/solidify、非 mm、Creo 9/10。
- surface_boundary_fill：非平面环未提交（平面环已否决该树）；正确树仍待手工参照件读回。
- surface_curvature：非 mm、裁剪面（面内采样比例 <100%）、反向绕向邻面的 G1、多 face 链、
  Creo 9/10。
- 全部：Creo 10 独立复测（用户已取消为发布门槛）、WorkBuddy 黑盒验收未在本批执行。
