# G5 曲面链路原生契约（surface_loft / project_curve / surface_trim）

状态：**冻结**（Q07 交付，2026-11-01；S00 修订，2026-11-04）。关联条目：[FEAT-009](../work-items/FEAT-009.md)、[FEAT-039](../work-items/FEAT-039.md)、[FEAT-055](../work-items/FEAT-055.md)。消费方：Q08（surface_loft）、Q09（project_curve）、Q10（surface_trim）；S01–S08 按同名派工编号消费。

本文件是 Q08–Q10 的唯一接口依据。**未经本文件冻结的原生元素树、引用形态、测量字段和单位语义，三个任务都不得自行实现**；需要改动时先改本文件，再改代码。

## 0. 范围与证据边界

| 项 | 内容 |
| --- | --- |
| 调查对象 | [0.10.0 晚间包 02_G5 曲面能力方案](../validation/feedback-0.10.0-2026-11-01/originals/02_G5曲面能力方案.md)（**仅作来源，逐项核实，未照抄其数值 ID 与树形**） |
| 本机 SDK | `C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit\includes`（430 个头文件），Creo 12.4.0.0 / Toolkit x86e_win64 |
| 本机来源 | 主 checkout `E:\Projects\MCP_CREO_MechDog\config.json` 的 `creo_root`（只读）；`native/constants.inc` 为本机生成物，**本任务不复制、不入库、不修改** |
| 原生实测 | **本任务未执行任何实机探针**（不连 Creo、不编译、不占 Toolkit 通道）。所有"实际原生元素树"均为**待实机验证的候选项**，见 §7 探针清单 |
| 常量来源规则 | 元素 ID 与枚举值一律**由 `tools/generate_constants.py` 机制按 SDK 头文件符号名解析**；本文件只写符号名，不写数值 |

> **硬边界**：文档中凡标注"待实机验证"的条目，Q08–Q10 实现时必须先跑 §7 的对应探针并把结论回填本文件，再进入公开 op 的实现。**不能用"编译通过"或"元素名存在"代替真实原生证据。**

### 0.1 S00 修订记录（2026-11-04）

来源：[0.11.7 反馈归档](../validation/feedback-0.11.7-2026-11-04/MAPPING.md)。旧契约不变的部分继续有效；本节列出被修订的条款及理由，`tools/test_g5_native_probe.py` 与 `tests/unit/test_g5_native_contract.py` 同步锁定。

| 修订 | 旧表述 | 现表述 | 依据 |
| --- | --- | --- | --- |
| R1 显式 quilt 引用 | 只有 `{"kind":"quilt_feature","label":...}` | 增加 `{"kind":"quilt","id":<int>}`；并明确 quilt ID 与 surface ID **不可互换** | F03 §3：`resolve()` 已区分 `PRO_QUILT` 与 `PRO_SURFACE`；修剪结果特征不必然有可直接枚举的 `PRO_QUILT` 几何项 |
| R2 错误分层 | 引用解析失败一律"不建 job" | 只有 **schema 可判定**的错误不建 job；原生运行时才发现的引用失效**允许已受理 job 失败并回滚** | 引用是否仍存在只能由原生侧判定 |
| R3 候选唯一性 | "命中 ≥2 个拒绝"（无候选清单） | 拒绝**并返回有界候选清单**；仍不得自动选取第一个或"最大面积" | F03 §3 建议 B 的部分采纳 |
| R4 投影 oracle | 高 20 mm 圆柱承载长 30 mm 源线 | 首个可解析用例改为 40×20 平面、z=10 的 30 mm 直线沿 −Z 投影到 z=0；圆柱用例单列并标"有效域/多交点待定义" | 旧用例几何不自洽（源线长于承载面高度） |
| R5 跨模型 ID 比较 | O3 用两次 `kept_quilt_id` 不同证明两侧不同 | 改为面积、位置与 `signed_offset_mm` 判据；只有**同一模型内**两次保留侧运行才比较 ID | 不同模型/不同 revision 的 ID 数字相同不代表同一对象 |
| R6 旧路线失败状态 | 只记"待验证" | 明确记录"路线失败"与"未验证"两种状态，失败历史不删除 | 旧三路线本机探针失败事实保持 |

### 0.2 S02/S03 实施状态（2026-11-04）

- `surface_trim`（S02）与 `quilt_merge`（S03）的 schema、原生模块、驱动离线用例已完成并编译通过；两者都**已注册但列入 `UNAVAILABLE_OPERATIONS`**：`server.py` 把对应工具从 MCP 面移除，`require_available` 在提交前拒绝。**因此它们对客户端仍不可用，不构成已公开能力。**
- 未验证项保持不变：§2.3/§2.4 的树在实机再生结果、§4.4.2 的真实面积/位置、§4.5 的 `keep_side` 法向绑定（P3）、修剪/合并结果保存重载后能否被 `thicken` 消费、失败回滚表现。
- §4.4.2 的质心字段（`target_centroid`/`kept_centroid`/`signed_offset_mm`）在本机没有可依据的 quilt 质心查询，实现**一律返回 null 并附原因**，不用外框中心估算；P3 回填前也不做"方向矛盾即失败"的强制判定。

### 0.3 S02 P3 实机回填（2026-11-04）

环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK，单会话串行。

- **`keep_side` 绑定已实测**（§4.5）：`one` 保留工具法向正侧、`two` 保留负侧；决定性元素是 `PRO_E_MATERIAL_SIDE`，`PRO_E_PRIMARY_QLTSIDE` 单独不改变保留区域。`surface_trim` 已从 `UNAVAILABLE_OPERATIONS` 移除，成为公开算子；`quilt_merge` 仍在门禁内。
- **基准面引用写法事故（已修）**：`{kind:'datum_plane',label:'RIGHT'}` 被几何解析分支接受但**丢弃 label**，默认轴过滤（axis z、offset 0）选中 TOP，修剪平面落在别处并停在 `PRO_FEAT_UNREGENERATED`（status 6）。现在 Python 契约与原生 `resolve()` 都拒绝几何类引用上的 label，只允许 `{kind:'datum_feature',label:...}` 携带标签。
- **修剪失败可诊断**：再生失败分支回写 `regeneration`（`feature_status`、`feature_id`、`target_quilt_id`、`tool_kind`、两侧枚举值、结果特征的 quilt 访问码），失败消息带同一组数值；`area_before/after`、`kept_quilt_*` 等测量字段在失败记录里保持可见。
- **仍未验证**：修剪结果在保存重载后被 `thicken` 消费、质心判据（本机无 quilt 质心查询）、失败回滚的实机表现、`quilt_merge` 全套实机项。证据：`build/live_trim_report.json`、`build/surface_chain/20261104-094447-635200/report.json`（jobs `247f76de…`、`7ae993e6…`）。

---

## 1. SDK 逐项核实结论表

核实方式：对本机 SDK 每个头文件做符号检索，并把每个符号与 02 方案的用法逐条比对。"已核实"= 本机头文件中存在且用法与方案一致或更明确；"本机 SDK 差异"= 本机存在但与方案描述不符，或方案元素在本机不存在；"未验证"= 本机头文件未给出足够信息，须实机探针判定。

### 1.1 surface_loft（02 方案 §2）

| 02 方案条目 | 本机 SDK 结论 | 依据（本机路径:行） | 状态 |
| --- | --- | --- | --- |
| `PRO_E_FEATURE_TYPE = PRO_FEAT_DATUM_SURF (942)` | `PRO_FEAT_DATUM_SURF` = 942 存在 | `ProFeatType.h:44` | 已核实（数值一致，但**仍按符号名取**） |
| `PRO_E_FEATURE_FORM = PRO_BLEND_SURF / PRO_STD_BLEND` | **本机 SDK 无 `PRO_BLEND_SURF`、无 `PRO_STD_BLEND`**。`PRO_FEAT_FORM` 可用值中与曲面放样相关的是 `PRO_USE_SURFS`(512)、`PRO_BLEND`(8)、`PRO_FLAT`(1024) | `ProFeatForm.h:15-31` | **本机 SDK 差异**：方案的 form 名不存在 |
| `PRO_E_BLEND_SECTIONS`（ARRAY，按序） | **本机 SDK 无此元素**。最接近的是 `PRO_E_BNBLN_CURVES`(661) → `PRO_E_BNBLN_1DIR`(651)/`PRO_E_BNBLN_2DIR`(652) → `PRO_E_BNBLN_DIR_CURVES`(657, ARRAY of chain holders) | `Probbl.h:53-66`、`ProElemId.h:743-754` | **本机 SDK 差异**：方案元素名不存在；**真实边界混合树见 §2.1** |
| `PRO_E_BLEND_ATTRIBUTES`（straight/smooth） | **本机 SDK 无此元素**。`Probbl.h` 未定义任何 attributes 元素；`PRO_E_BNBLN_RULED`(1206) 只在 `ProElemId.h` 出现、无任何头文件解释其语义 | `ProElemId.h:1296`（孤立定义） | **本机 SDK 差异**：方案元素名不存在；`PRO_E_BNBLN_RULED` 语义**未验证** |
| `PRO_E_STD_SEC_METHOD = PRO_SEC_SKETCH` | `PRO_E_STD_SEC_METHOD`(725) 存在；`PRO_SEC_SKETCH`=25、`PRO_SEC_SELECT`=26 定义于 `ProStdSection.h` | `ProElemId.h:827`、`ProStdSection.h:159-165` | 已核实（但边界混合用的是 chain holder，不是 section；见 §2.1） |
| `PRO_E_STD_SEC_SELECT` | 存在(726) | `ProElemId.h:828` | 已核实（边界混合路径不适用） |
| `PRO_BLEND`（form 值） | 存在 = 8 | `ProFeatForm.h:21` | 已核实 |
| 边界混合（Boundary Blend）特征类型 | `PRO_FEAT_DATUM_SURF` + `PRO_USE_SURFS` + `PRO_E_DTM_SRF_TYPE = PRO_E_DTM_SRF_TYPE_BND_BLEND`（=11），特征树在 `Probbl.h` | `Probbl.h:163-218` | 已核实（**这是本机唯一有文档的曲面放样元素树**） |
| 边界混合截面表达 | 截面是**曲线链集合**：`PRO_E_BNBLN_DIR_CURVES` 为 ARRAY，每项 `PRO_E_STD_CHAIN_HOLDER` → `PRO_E_STD_CURVE_COLLECTION_APPL`（PRO_VALUE_TYPE_SELECTION，curve collection）。**不是** `PRO_E_STD_SECTION`/sketch section | `Probbl.h:58-66,137-140` | 已核实（与 02 方案"截面=草图 section"**不同**） |
| 边界混合方向数 | `PRO_E_BNBLN_1DIR` 至少 2 条曲线；`PRO_E_BNBLN_2DIR` 至少 2 条曲线；至少定义一个方向 | `Probbl.h:178-186` | 已核实 |
| 边界混合闭合 | `PRO_E_BBL_ADD_CLOSED`（元素 ID 3175），`PRO_B_TRUE` 仅在 ≥3 曲线时可行 | `Probbl.h:63,66,191-193` | 已核实（**首版不公开 closed**，见 §3.1） |
| 边界混合切向条件 | `PRO_E_BNBLN_TAN_COND_TYPE` 有效值 `TAN_COND_FREE`（该宏在头文件中**只有文字、没有可解析的定义**） | `Probbl.h:196-197` | **未验证**：`TAN_COND_FREE` 无符号定义；**首版不公开连续性** |
| `PRO_E_CTRL_PTS` / `PRO_E_BLEND_TYPE` | `PRO_E_CTRL_PTS`(662) 是特征树下一级 compound，其下挂 `PRO_E_BLEND_TYPE`(646, INT) | `Probbl.h:118-119,155-156`、`ProElemId.h:738,754` | 已核实存在；**取值语义未验证**（头文件未给合法值表） |

### 1.2 project_curve（02 方案 §3）

| 02 方案条目 | 本机 SDK 结论 | 依据 | 状态 |
| --- | --- | --- | --- |
| `PRO_E_COPYTRIM_QUILT` (1630) | 存在，值 1630 | `ProElemId.h:1666` | 已核实（数值一致，按符号名取） |
| `PRO_E_COPYTRIM_CURVES` (1631) | 存在，值 1631 | `ProElemId.h:1667` | 已核实（**头文件未给任何语义/父子关系说明**） |
| `PRO_E_COPYTRIM_CURVE_TBL` (1632) | 存在，值 1632 | `ProElemId.h:1668` | 已核实（**同上，语义未说明**） |
| `PRO_E_COPYTRIM_CURVE_DATA` (1633) | 存在，值 1633 | `ProElemId.h:1669` | 已核实（**同上**） |
| `PRO_E_COPYTRIM_CURVE` (1634) | 存在，值 1634 | `ProElemId.h:1670` | 已核实（**同上**） |
| 02 方案的 COPYTRIM 树形（`PRO_E_FEATURE_TYPE=PRO_FEAT_CURVE` 下挂 `PRO_E_COPYTRIM_CURVE_DATA`，内含 `PRO_E_COPYTRIM_QUILT` + `PRO_E_COPYTRIM_CURVE_TBL`） | **本机 SDK 无任何头文件描述 COPYTRIM 的父子关系、合法值或必需的兄弟节点**。五个元素只在 `ProElemId.h` 的 ID 表里出现，无特征树文档 | 全 SDK 检索：`copytrim` 仅命中 `ProElemId.h:1666-1670` | **未验证**：树形只是外部方案假设，**本机无可依据的官方树**。必须实机探针判定 |
| `PRO_E_FEATURE_TYPE = PRO_FEAT_CURVE` | `PRO_FEAT_CURVE` = 949 存在 | `ProFeatType.h:51` | 已核实 |
| 02 方案的 `direction_ref` 语义 | `ProDirection.h` 只为**方向容器**定义 `PRO_E_DIRECTION_COMPOUND`/`PRO_E_DIRECTION_REFERENCE`/`PRO_E_DIRECTION_FLIP`（`PRO_DIRECTION_FLIP_ALONG`=1 / `PRO_DIRECTION_FLIP_AGAINST`=-1），合法引用为直边/直曲线/平面/基准面/基准轴/基准坐标系轴。**没有任何 COPYTRIM 元素引用该容器** | `ProDirection.h:10-49` | **未验证**：COPYTRIM 与方向容器的连接方式无文档 |
| 02 方案的 `side: positive/negative` | 同上，方向翻转只有 `FLIP_ALONG`/`FLIP_AGAINST` 两值，且**绑在 `PRO_E_DIRECTION_COMPOUND` 下** | `ProDirection.h:27-41` | **未验证**：语义与归属未验证 |
| 可替代的、有官方文档的"曲面投影曲线"路线 | `ProDtmCrv.h` 的 **Intersect / Two Projections** 曲线特征：`PRO_CURVE_TYPE_INTSRF`=2、`PRO_CURVE_TYPE_TWO_PROJ`=15；元素 `PRO_E_CRV_IP_REF1`/`REF2`（接受 `PRO_QUILT`/`PRO_SURFACE`/`PRO_DATUM_PLANE`/`PRO_SOLID_GEOMETRY`）、`PRO_E_CRV_IP_COMP_SEC1`/`SEC2`（各含 `PRO_E_STD_SECTION`） | `ProDtmCrv.h:144-249`、`ProElemId.h:2308-2316` | 已核实（**这是本机唯一有文档的"把曲线投到曲面上"特征族**；语义是"两曲面求交曲线"，与 COPYTRIM 不同） |

### 1.3 surface_trim（02 方案 §3）

| 02 方案条目 | 本机 SDK 结论 | 依据 | 状态 |
| --- | --- | --- | --- |
| 02 方案："`surface_trim` 同样有元素树路线：Copy-Trim 特征本身既是投影剪裁" | **不成立**。本机 SDK 中 COPYTRIM 五个元素**没有任何文档化的父子关系**（见 §1.2）；真正的曲面修剪特征是独立的 `PRO_FEAT_CUT` + `PRO_USE_SURFS` + `PRO_E_SRF_TRIM_TYPE` | `ProTrim.h:10-60` | **本机 SDK 差异**：方案把 trim 与 copytrim 混为一谈 |
| `PRO_E_TRIM_QUILT` | 存在(11)，类型 `PRO_VALUE_TYPE_SELECTION`，接受 `PRO_SURFACE`/`PRO_QUILT` | `ProElemId.h:21`、`ProTrim.h:73` | 已核实 |
| `PRO_E_SRF_TRIM_TYPE` | 存在(3218)；**non-redefinable mandatory**，取值 `ProSurfTrimType` | `ProElemId.h:2488`、`ProTrim.h:70,276-278` | 已核实 |
| `PRO_E_SURF_TRIM_TYPE` | 存在(3087)，取值同为 `ProSurfTrimType` | `ProElemId.h:2333`、`ProTrim.h:72` | 已核实 |
| `ProSurfTrimType` 枚举值 | `PRO_SURF_TRIM_TYPE_UNDEF`=0、**`PRO_SURF_TRIM_USE_CRV`=1**、**`PRO_SURF_TRIM_USE_QLT`=2**、`PRO_SURF_TRIM_THIN`=3、`PRO_SURF_TRIM_SILH`=4 | `ProTrim.h:339-346` | 已核实 |
| `ProTrimMatlSideOpts` | `PRO_TRIM_MATL_SIDE_ONE`=1、`PRO_TRIM_MATL_SIDE_TWO`=2、`PRO_TRIM_MATL_BOTH_SIDES`=3 | `ProTrim.h:350-356` | 已核实 |
| `ProTrimPrimaryQltSide` | `PRO_TRIM_PRIM_QLT_SIDE_ONE`=-1、`PRO_TRIM_PRIM_QLT_SIDE_TWO`=1 | `ProTrim.h:359-364` | 已核实 |
| `ProTrimStdQuiltSideOpts` | `PRO_TRIM_STD_QUILT_SIDE_ONE`=1、`..._TWO`=2、`..._BOTH_SIDES`=3 | `ProTrim.h:367-373` | 已核实 |
| `ProKeepTrimSurfOpts` | `PRO_KEEP_TRIM_SURF_OPT_NO`=0、`PRO_KEEP_TRIM_SURF_OPT_YES`=1 | `ProTrim.h:376-381` | 已核实 |
| `PRO_E_MATERIAL_SIDE` | 存在(1146)，类型 INT | `ProElemId.h:1225`、`ProTrim.h:77` | 已核实 |
| `PRO_E_PRIMARY_QLTSIDE` | 存在(3088)，类型 INT | `ProElemId.h:2334`、`ProTrim.h:78` | 已核实 |
| `PRO_E_KEEP_TRIM_SURF_OPT` | 存在(3091)，类型 INT | `ProElemId.h:2337`、`ProTrim.h:80` | 已核实 |
| `PRO_E_STD_USEQLT_QLT` | 存在(754)，接受 `PRO_SURFACE`/`PRO_QUILT`/`PRO_DATUM_PLANE` | `ProElemId.h:864`、`ProTrim.h:74` | 已核实（**trim 的"工具"侧引用元素**） |
| `PRO_E_STD_CURVE_COLLECTION_APPL` | 存在(2121)，类型 `PRO_VALUE_TYPE_SELECTION`，接受 `PRO_CURVE`/`PRO_COMP_CRV`/curve_chain | `ProElemId.h:2121`、`ProTrim.h:75` | 已核实（**use-curve 变体的工具侧引用元素**） |
| 02 方案："`PRO_E_TRIM_QLT_SIDE` 已在 ProSweep.h 元素表出现，通用" | `PRO_E_TRIM_QLT_SIDE`(1147) 存在，但**其语义按父特征族分化**：`ProSweep.h` 为 `pro_sweep_trimqlt_side`（-1/+1，仅 sweep 双面裁剪时用）、`ProExtrude.h` 为 `ProExtTrimQltSide`（-1/+1）、`ProRevolve.h` 为 `ProRevTrimQltSide`（-1/+1）。**`ProTrim.h` 的 trim 特征树根本不包含该元素**——它用 `PRO_E_MATERIAL_SIDE` / `PRO_E_PRIMARY_QLTSIDE` / `PRO_E_STD_USEQLT_SIDE` | `ProSweep.h:184-189`、`ProExtrude.h:847-853`、`ProRevolve.h:769-775`、`ProTrim.h:104-136` | **本机 SDK 差异**：`PRO_E_TRIM_QLT_SIDE` **不是通用 trim 侧元素**，不可用于本契约的 surface_trim |
| 02 方案："body 布尔可替代 quilt 修剪" | 本机 `ProBooleanBodies.h` 的布尔只接受 body，`boolean_bodies` op 亦只接受 body（`schema.py:BooleanOp` 强制 `kind=="body"`） | `src/creo_mechdog/schema.py:1440-1463` | 已核实：**body 布尔不可替代 quilt 语义**（且本契约禁止用 body 布尔冒充 quilt 修剪） |
| `PRO_E_TRIM_SILH_PLANE` | 存在(3238)，仅 silhouette 变体 | `ProElemId.h:2509` | 已核实（首版不用） |

### 1.4 测量与单位 API

| 项 | 本机 SDK 结论 | 依据 | 状态 |
| --- | --- | --- | --- |
| 02 方案："`ProSurfaceEval` 面积或用 Measurable 对 quilt 的面积" | **本机 SDK 无 `ProSurfaceEval`，无 `ProMeasurable`**。真实可用的是 `ProSurfaceAreaEval(ProSurface, double*)`（单曲面面积）、`ProQuiltVolumeEval`（**仅闭合 quilt**）、`ProContourAreaEval(ProSurface, ProContour, double*)`（外环内面积，扣内部孔） | `ProSurface.h:274`、`ProQuilt.h:137`、`ProContour.h:140` | **本机 SDK 差异**：方案 API 名不存在 |
| 曲面面积 | `ProSurfaceAreaEval` 对**单张曲面**求面积；`ProContourAreaEval` 对**外环围合区域**求面积（含孔洞扣除），是"修剪后区域面积"的正确 API | `ProSurface.h:274-289`、`ProContour.h:140-160` | 已核实 |
| 曲线长度 | `ProCurveLengthEval(ProCurve, double*)` | `ProCurve.h:139` | 已核实 |
| 曲线端点 | `ProCurveXyzdataEval(ProCurve, param, xyz, deriv1, deriv2)` 在 param=0/1 求值（复合曲线时 deriv 必须为 NULL） | `ProCurve.h:88-116` | 已核实 |
| quilt 体积 | `ProQuiltVolumeEval`，**要求 quilt 闭合**，否则 `PRO_TK_INVALID_TYPE` | `ProQuilt.h:137-154` | 已核实（故体积不能代替面积） |
| 长度单位换算 | 本机已有 `native/inspection_units.h` 的 `InspectionLengthUnits`（主单位系 + 长度单位名）与 `native/assembly_units.h` 的 `length_scale_to_mm`（真实换算比例） | `native/inspection_units.h:8-30`、`native/assembly_units.h:21-56` | 已核实（**复用，不另写**） |
| 面积单位换算 | SDK 无面积单位；面积是长度²，须用 `scale_to_mm²` | 同上（比例的平方） | 已核实（推导规则见 §4.4） |

### 1.5 常量导出机制（生成物正确来源）

`tools/generate_constants.py` 只扫描 `HEADERS` 列表里的头文件，抽取 `PRO_E_*`/`PRO_FEAT_*` 的 `#define` 与 `enum` 成员，写入 `native/constants.inc`；`native/generic.cpp:141` 的 `constant()` 按**符号名**查表。本机 `constants.inc`（只读检查，未复制、未修改）当前状态：

| 符号 | 已导出 | 说明 |
| --- | --- | --- |
| `PRO_E_BNBLN_CURVES` / `_1DIR` / `_2DIR` / `_DIR_CURVES` / `_TAN_COND_TYPE` / `_STRETCH` / `_CONNECT_SURF_CHAIN` | 是 | 来自 `ProElemId.h`（在 `HEADERS` 内） |
| `PRO_E_STD_CHAIN_HOLDER` / `PRO_E_STD_CURVE_COLLECTION_APPL` / `PRO_E_SURF_CHAIN_*` | 是 | 同上 |
| `PRO_E_CTRL_PTS` / `PRO_E_BLEND_TYPE` / `PRO_E_BBL_ADD_CLOSED` / `PRO_E_BNBLN_RULED` | 是 | 同上 |
| `PRO_E_COPYTRIM_QUILT` / `_CURVES` / `_CURVE_TBL` / `_CURVE_DATA` / `_CURVE` | 是 | 同上 |
| `PRO_E_TRIM_QUILT` / `PRO_E_SRF_TRIM_TYPE` / `PRO_E_SURF_TRIM_TYPE` / `PRO_E_STD_USEQLT_QLT` / `PRO_E_STD_USEQLT_SIDE` / `PRO_E_MATERIAL_SIDE` / `PRO_E_PRIMARY_QLTSIDE` / `PRO_E_KEEP_TRIM_SURF_OPT` | 是 | 同上 |
| `PRO_E_DTM_SRF_TYPE_BND_BLEND` | **否** | 定义在 `Probbl.h`（**不在** `HEADERS` 内） |
| `PRO_SURF_TRIM_USE_CRV` / `PRO_SURF_TRIM_USE_QLT` / `PRO_TRIM_MATL_SIDE_*` / `PRO_TRIM_PRIM_QLT_SIDE_*` / `PRO_TRIM_STD_QUILT_SIDE_*` / `PRO_KEEP_TRIM_SURF_OPT_*` | **否** | 定义在 `ProTrim.h`（**不在** `HEADERS` 内） |
| `PRO_SEC_SKETCH` / `PRO_SEC_SELECT` | **否** | 定义在 `ProStdSection.h`（**不在** `HEADERS` 内） |
| `PRO_SRF_MRG_JOIN` / `PRO_SRF_MRG_INTSCT` / `PRO_SRF_MRG_QLT_SIDE_*` | **否** | 定义在 `ProMerge.h`（**不在** `HEADERS` 内） |
| `PRO_E_BNDRY*` | 只有 `PRO_E_BNDRY_CONTRS`(171) 一条 | 0.3.5 反馈所称"已导出 21 条"**在本机 SDK 不成立** |

**结论（写给 Q08–Q10 的硬规则）**：

1. **禁止**在源码、示例、文档或测试数据里写任何 `PRO_E_*` / `PRO_FEAT_*` / 枚举的**数值**。
2. 需要新符号时，**唯一**做法是：在 `tools/generate_constants.py` 的 `HEADERS` 中加入该符号所在的 SDK 头文件（本契约涉及的候选头文件：`Probbl.h`、`ProTrim.h`、`ProStdSection.h`、`ProMerge.h`），由本机 `generate_constants` 重新生成本机 `constants.inc`（本机生成物，不入库、不跨机复制）。
3. 元素 ID 在原生 C++ 侧用**头文件宏**（`#include <Probbl.h>` 等）直接引用；只有"按名字查表"的低层通道（`creo_create_feature_tree` / `creo_lookup_constants`）才依赖 `constants.inc` 的符号表。
4. `tools/generate_constants.py` 的 `HEADERS` 增补是**共享改动**，由集成人统一收取；三个任务各自只提"需要哪些符号"，不得各自改 `HEADERS`。

---

## 2. 预期原生元素树（候选项，待实机验证）

本节写的是**结构骨架与必须满足的约束**，不是"已证实的树"。任何一棵最终采用的树都必须通过 §7 探针，并回填本节。

### 2.1 surface_loft：边界混合（Boundary Blend）

候选树（依据 `Probbl.h`）：

```
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE      = PRO_FEAT_DATUM_SURF
 ├─ PRO_E_FEATURE_FORM      = PRO_USE_SURFS
 ├─ PRO_E_DTM_SRF_TYPE      = PRO_E_DTM_SRF_TYPE_BND_BLEND
 ├─ PRO_E_STD_FEATURE_NAME  = <label>
 ├─ PRO_E_BNBLN_CURVES
 │   └─ PRO_E_BNBLN_1DIR
 │       └─ PRO_E_BNBLN_DIR_CURVES      (ARRAY, 按序 = 截面顺序)
 │           └─ PRO_E_STD_CHAIN_HOLDER
 │               └─ PRO_E_STD_CURVE_COLLECTION_APPL   (curve collection 选择)
 └─ PRO_E_CTRL_PTS
     └─ PRO_E_BLEND_TYPE                (取值语义未验证)
```

必须满足的约束（来自 `Probbl.h`，非猜测）：

- 至少定义一个方向；首版只用 `PRO_E_BNBLN_1DIR`。
- `PRO_E_BNBLN_1DIR` 至少 2 条曲线。
- 曲线以 chain holder + `PRO_E_STD_CURVE_COLLECTION_APPL` 表达；本机已有可复用的 `native/generic.cpp:2393` `curve_collection()`（`ProCrvcollectionAlloc` + `PRO_CURVCOLL_ADD_ONE_INSTR`）。
- **首版不写** `PRO_E_BBL_ADD_CLOSED`、不写 `PRO_E_BNBLN_TAN_COND`（`TAN_COND_FREE` 无符号定义）。

### 2.2 project_curve：实测定论与实际实现树（S04 回填，2026-11-04）

#### 2.2.1 两族投影元素都不可用（实测，P2 结论）

`PRO_E_COPYTRIM_*` 与 `PRO_E_PROJ_CRV_*` 在本机 SDK 里都只有 `ProElemId.h` 的 ID 条目，
没有任何父子关系、合法值或必需兄弟节点的说明。用已注册的 `feature_tree` 逐条提交候选树
（不重新编译、结论由内核给出），2026-11-04 的实测结果：

| 候选树 | 结构 | 结果 |
| --- | --- | --- |
| `copytrim_contract_tree` | `PRO_E_COPYTRIM_CURVE_DATA` → `_QUILT` + `_CURVE_TBL`/`_CURVE` | `ProFeatureWithoptionsCreate` 拒绝（-1） |
| `copytrim_flat` | `_QUILT` 与 `_CURVE` 平铺为根子元素 | 同上（-1） |
| `copytrim_curves_array` | `_QUILT` + `_CURVES`/`_CURVE` | 同上（-1） |
| `proj_crv_surfs` | 根挂 `PRO_E_PROJ_CRV_CURVE`/`_SURFS`/`_DIR`/`_PROJ_TYPE(=ALONGDIR)` | 同上（-1） |
| `proj_crv_onesrf` | 用 `PRO_E_PROJ_CRV_ONESRF_REF` 替代 `_SURFS` | 同上（-1） |
| `proj_crv_surfs_with_curve_type` | 追加 `PRO_E_CRV_PROJCRV_TYPE(=PRO_PROJCRV_CURVE)` | 同上（-1） |
| `proj_crv_normal_to_srf` | `PRO_E_PROJ_CRV_PROJ_TYPE(=NORM2SRF)`，无 `_DIR` | 同上（-1） |

同一批探针里引用本身可解析（单独的 quilt/curve/datum_feature 引用都进入创建阶段），
所以拒绝的是树形，不是引用。`ProCurveType` 里也没有"投影"类型值，
`PRO_PROJ_*` 只出现在 `ProElemId.h`。结论：**投影特征没有可依据的官方树，Q09 不得据此创建几何**。

#### 2.2.2 交付路线：扫掠辅助面 + 文档化交线（实测通过）

`ProDtmCrv.h` §"INTERSECT" 是本机唯一有文档的"把面投到面上"特征族。它的语义是两曲面交线，
单独使用**不是**投影；但"源曲线沿方向扫掠出的曲面 ∩ 目标曲面"在几何上**恰好等于**该曲线沿该方向的
投影（扫掠面包含曲线上每一点沿方向的平移）。因此 `native/project_curve.cpp` 分两步构建：

```
1) 辅助扫掠面（ProExtrude.h，PRO_FEAT_DATUM_SURF + PRO_EXTRUDE，surface 模式）
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE            = PRO_FEAT_DATUM_SURF
 ├─ PRO_E_FEATURE_FORM            = PRO_EXTRUDE
 ├─ PRO_E_EXT_SURF_CUT_SOLID_TYPE = PRO_EXT_FEAT_TYPE_SURFACE
 ├─ PRO_E_STD_FEATURE_NAME        = "<label>_sweep"
 ├─ PRO_E_STD_SECTION ── PRO_E_SEC_USE_SKETCH   (源曲线所属草图)
 └─ PRO_E_STD_EXT_DEPTH
     ├─ PRO_E_EXT_DEPTH_FROM ── PRO_E_EXT_DEPTH_FROM_TYPE = PRO_EXT_DEPTH_FROM_NONE
     └─ PRO_E_EXT_DEPTH_TO   ── PRO_E_EXT_DEPTH_TO_TYPE   = PRO_EXT_DEPTH_SYMMETRIC
                              └ PRO_E_EXT_DEPTH_TO_VALUE  = 2*(到目标包围盒的距离 + 0.5)
```

```
2) 交线曲线（ProDtmCrv.h INTERSECT，唯一有文档的树）
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE     = PRO_FEAT_CURVE
 ├─ PRO_E_CURVE_TYPE       = PRO_CURVE_TYPE_INTSRF
 ├─ PRO_E_CRV_IP_REF_TYPE  = PRO_CURVE_TYPE_INTSRF   (ProDtmCrv.h 注：与 PRO_E_CURVE_TYPE 同值)
 ├─ PRO_E_STD_FEATURE_NAME = <label>
 ├─ PRO_E_CRV_IP_COMP_REF1
 │   ├─ PRO_E_CRV_IP_REF1            (扫掠面：1 面用 PRO_CURVE_TYPE_WHOLE，多面用 MULTIPLE_SEL)
 │   └─ PRO_E_CRV_IP_REF_SEL1_TYPE
 └─ PRO_E_CRV_IP_COMP_REF2
     ├─ PRO_E_CRV_IP_REF2           (目标 quilt，WHOLE)
     └─ PRO_E_CRV_IP_REF_SEL2_TYPE
```

实测要点：

- 较早的 `REF_TYPE=0` 与"REF2 用与目标平行的平面"两次都判为失败（后者再生失败、`feature_status=6`），
  说明 `REF_TYPE` 必须取 `PRO_CURVE_TYPE_INTSRF`，且两参考必须真的相交。
- 直线源：辅助面 8 个面（3 平面 + 5 曲面），只有法向垂直于扫掠方向的那一张是扫掠面；
  圆弧源：扫掠面被拆成 5 张柱面，必须用 `MULTIPLE_SEL` 一次性全部作为 REF1。
  规则因此写成"法向与方向平行的平面是端盖，其余面都属于扫掠面"。
- 交线特征会同时产出曲线与其包络复合曲线（实测 2 个 `PRO_CURVE` 项）。只报非复合曲线；
  出现两条及以上非复合曲线即判为多分支并拒绝，不挑选其中一条。

#### 2.2.3 该路线的已声明限制（实现内检查，不是猜测）

- 方向必须与源草图平面法向平行（`ProExtrude.h` 只沿草图法向扫掠）。实测做法：建好辅助面后读取
  其平面法向与方向的 `|dot|`；不平行即拒绝，消息里给出两者数值。
- 目标必须真的位于请求侧：用目标 quilt 包围盒角点相对源曲线起点的有符号距离判定，
  全部在背侧时拒绝（`side="positive"` 朝 +Z 而目标在 z=0 的实测即为此）。
- 源曲线必须属于曲线特征（草图）；辅助面保留在模型里，因为删掉它等于删掉依赖它的交线。
- 未实测：多分支拒绝路径、非平面目标、方向与草图法向不平行的拒绝路径只在实现内存在证据，
  未在实机触发过。

### 2.3 surface_trim：ProTrim.h 族（候选，结构有文档）

依据 `ProTrim.h` §(2.1)/(2.2) "Use Quilt" 变体：

```
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE      = PRO_FEAT_CUT
 ├─ PRO_E_FEATURE_FORM      = PRO_USE_SURFS
 ├─ PRO_E_SRF_TRIM_TYPE     = PRO_SURF_TRIM_USE_QLT
 ├─ PRO_E_SURF_TRIM_TYPE    = PRO_SURF_TRIM_USE_QLT
 ├─ PRO_E_STD_FEATURE_NAME  = <label>
 ├─ PRO_E_TRIM_QUILT        (被修剪的 quilt: PRO_QUILT/PRO_SURFACE)
 ├─ PRO_E_STD_USEQLT_QLT    (修剪工具: PRO_SURFACE/PRO_QUILT/PRO_DATUM_PLANE)
 ├─ PRO_E_MATERIAL_SIDE     (ProTrimMatlSideOpts)
 ├─ PRO_E_PRIMARY_QLTSIDE   (ProTrimPrimaryQltSide)
 └─ PRO_E_KEEP_TRIM_SURF_OPT(ProKeepTrimSurfOpts)
```

#### 2.3.1 use-curve 变体（2026-11-04 实机加入）

`ProTrim.h` §(3.1)/(3.2) 的 "Use Curve" 变体单独成树：

```
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE              = PRO_FEAT_CUT
 ├─ PRO_E_SRF_TRIM_TYPE             = PRO_SURF_TRIM_USE_CRV (1)
 ├─ PRO_E_STD_FEATURE_NAME          = <label>
 ├─ PRO_E_SURF_TRIM_TYPE            = PRO_SURF_TRIM_USE_CRV (1)
 ├─ PRO_E_TRIM_QUILT                (被修剪的 quilt)
 ├─ PRO_E_STD_CURVE_COLLECTION_APPL (PRO_CURVE / PRO_COMP_CRV / curve_chain)
 ├─ PRO_E_MATERIAL_SIDE             (ProTrimMatlSideOpts)
 └─ PRO_E_PRIMARY_QLTSIDE           (ProTrimStdQuiltSideOpts)
```

实测要点（2026-11-04，`build/_live_usecurve_trim_probe.py`，40×20 填充被 y=15 直线切开）：

- 该树**没有** `PRO_E_FEATURE_FORM`，也没有 `PRO_E_KEEP_TRIM_SURF_OPT`；写了反而多一层不必要的元素。
- `PRO_E_MATERIAL_SIDE` 才是真正决定保留侧的元素：1/2 分别保留一侧（200 或 600 mm²），3 表示两侧都保留（两个 quilt）。`PRO_E_PRIMARY_QLTSIDE` 实测（1/2/-1）不改变保留结果。
- 保留侧相对**曲线方向**：同一材质侧下把直线方向反过来，保留的区域随之交换。因此 `kept_side_basis` 报告 `side_reference="curve_direction"`、`tool_curve_id` 与 `tool_kind="curve"`，不报告 `tool_normal`。
- 曲线特征创建后立即读状态是 `PRO_FEAT_FAILED(6)`，因为集合要等再生才解析；先 `ProSolidRegenerate` 再读状态即为 ACTIVE。use-quilt 变体创建后已是 ACTIVE，所以只有曲线分支多付一次再生。
- 实机操作符验证（`build/_live_op_trim_probe.py` 的 `flat` 形态）：z=0 的草图直线修剪同平面填充，面积 800→600，`kept_quilt_id` 为保留侧 quilt，作业 `saved_file_reloaded_and_verified=true`。

#### 2.3.2 已知边界：投影曲线不能修剪它自己投影到的那张 quilt

同一台机器上，"投影到 quilt → 用该投影曲线修剪同一 quilt"的链在保存阶段失败：
`ProMdlnameBackup(board, destination) = -1`（`save_and_reload` 阶段），作业回滚，模型恢复为未修剪状态
（`build/_live_op_trim_probe.py` 的 `projected` 形态）。同一模型里的投影作业本身可以保存。

原因是该投影曲线是 `ProDtmCrv.h` 的**交线**，它持有被修剪 quilt 的几何项选择；修剪把这个 quilt 消费掉后，
曲线的参考悬空，内核拒绝写出这个模型。真实投影特征（若可用）会让曲线随父曲面一起再生，这里没有那条树。
因此：**独立曲线（草图曲线、另一张面上的曲线）修剪已验证可用；依赖目标 quilt 的曲线在保存阶段会失败并回滚**，
调用方会看到原始 `ProMdlnameBackup` 失败信息，不会被当成成功。

**注意：`PRO_E_SRF_TRIM_TYPE` 是 non-redefinable mandatory**（`ProTrim.h:276-278`），创建后不可改；`PRO_E_SURF_TRIM_TYPE` 必须与之一致。

### 2.4 quilt_merge：ProMerge.h 当前（数组）树（结构有文档）

`ProMerge.h` 对本机 SDK 的当前曲面合并树是**完整文档化**的，不再属于"候选"：

```
PRO_E_FEATURE_TREE
 ├─ PRO_E_FEATURE_TYPE      = PRO_FEAT_DATUM_QUILT
 ├─ PRO_E_SRF_MRG_TYPE      = ProSrfMrgType（默认 INTERSECT）
 ├─ PRO_E_STD_FEATURE_NAME  = <label>
 └─ PRO_E_SRF_MRG_QUILT_ARR (数组，至少 2 个成员)
     └─ PRO_E_SRF_MRG_QUILT_CMPD
         ├─ PRO_E_SRF_MRG_QUILT_REF  (PRO_QUILT 选择，mandatory)
         └─ PRO_E_SRF_MRG_QUILT_SIDE (ProSrfMrgQltSide，optional)
```

两条必须显式处理的默认值：

- `PRO_E_SRF_MRG_TYPE` 的**默认是 INTERSECT**，首版只要 join，因此必须显式写 `PRO_SRF_MRG_JOIN`；不写就等于悄悄做交集。
- `PRO_E_SRF_MRG_QUILT_SIDE` 是可选项，且在参与者 >2 时不可用；首版不设置它，保留区域由默认行为决定并**测量**，不按 GUI 观感假设。

数组成员用 `ProElementArraySet(root, elempath_of(PRO_E_SRF_MRG_QUILT_ARR), members)` 写入，`members` 由 `ProArrayAlloc` 分配；单个成员元素先以无父方式建出再放入数组。

---

## 3. 第一版能力边界（冻结）

### 3.1 surface_loft

| 项 | 首版公开 | 首版明确拒绝 |
| --- | --- | --- |
| 截面数 | **恰好 2 条** | ≥3（`sections` 长度 ≠ 2 直接拒绝） |
| 截面来源 | **一条曲线一个截面**（chain holder 装 1 条曲线） | 多曲线链、多段截面、闭合截面 |
| 插值 | **straight**（`interpolation` 只能取 `"straight"`） | `smooth` |
| 闭合 | 不提供 `closed` 参数 | `closed:true` |
| 连续性 | 不提供 | 任何 `continuity` / 相切 / 曲率参数 |
| 截面平面 | 两条曲线各自在**任意**平面（不限于 XY，不要求 Z 单调） | — |
| 输出 | 曲面（datum surface），**不是实体** | `mode`/`new_body`（曲面放样不产实体） |

`sections` 顺序 = 放样方向，**index 0 是起点截面**。实现必须把顺序原样写进 `PRO_E_BNBLN_DIR_CURVES` 数组，不排序、不去重（去重由 schema 拒绝重复引用解决）。

### 3.2 project_curve

| 项 | 首版公开 | 首版明确拒绝 |
| --- | --- | --- |
| 目标 | **恰好 1 个 quilt** | 非 quilt 引用、多 quilt、无 quilt |
| 源曲线 | **恰好 1 条曲线** | 多条曲线、无曲线 |
| 投影方向 | **显式给出**（`direction_ref` + `side`） | 隐式默认方向、零向量方向 |
| 输出 | 一条曲线（`PRO_FEAT_CURVE`） | — |

`direction_ref` 只接受**能读出真实方向**的引用：基准面、基准轴、直边、直曲线。`side` 只有 `"positive"`/`"negative"` 两值，**必须**映射到 SDK 的方向翻转（`PRO_DIRECTION_FLIP_ALONG` / `PRO_DIRECTION_FLIP_AGAINST`），并由探针 P2 判定"哪一侧是 positive"——**不得按 GUI 观感命名**。

### 3.3 surface_trim

| 项 | 首版公开 | 首版明确拒绝 |
| --- | --- | --- |
| 目标 | 恰好 1 个 quilt | 非 quilt、多 quilt |
| 工具 | 恰好 1 个 quilt、基准面或曲线（`{kind:'curve',id:N}`） | 多工具、跨表曲线链 |
| 保留侧 | `keep_side` ∈ `{"one","two"}` | 其它值（曲线工具的"两侧都保留"未公开） |
| 薄壳 | 不提供 | `thin` / `thickness` |
| 轮廓/孔环 | 不提供 | 多区域、孔环（首版只处理单外环区域） |
| 输出 | 修剪后的 quilt（可供 `thicken` 消费） | — |

### 3.4 quilt_merge

| 项 | 首版公开 | 首版明确拒绝 |
| --- | --- | --- |
| 参与者 | **恰好 2 个类型明确的 quilt** | 基准面、曲线、body、多个参与者 |
| 合并方式 | 只做 join（`PRO_SRF_MRG_JOIN`） | intersect 变体 |
| 容差 | 不提供 | 任何 `tolerance` 参数（未证明生效前不得接受） |
| 间隙测量 | 不提供 | 任何间隙字段 |
| 闭合 | 只报告真实探测结果（§4.4.1 结构） | 由面积或外框反推 `closed` |
| 输出 | 一个结果 quilt（`result_quilt_id`，可供 `thicken` 消费） | — |

`quilt_merge` **不是** `boolean_bodies` 的替代：实体布尔不在曲面链里，不能用它掩饰缝合失败。

---

## 4. 冻结的 schema 与测量契约

### 4.1 引用表示

**所有引用一律走既有 `{"kind": ..., "label"/"id": ...}` 引用对象**，不新增引用种类：

| 语义 | 引用形态 | 解析规则 |
| --- | --- | --- |
| quilt（放样产物 / 修剪目标 / 修剪工具） | `{"kind":"quilt_feature","label":"<label>"}` | 复用 `native/generic.cpp` 的 `quilt_feature` 分支：特征内**恰好一个** `PRO_QUILT` 几何项；0 个或多个一律拒绝，多个时返回有界候选清单 |
| quilt（显式几何 ID，S01 起） | `{"kind":"quilt","id":<int>}` | 经 S01 的 `inspection.quilts` 取得的 `quilt_id`；原生侧用 `ProQuiltInit` 初始化后读取面/面积/闭合状态 |
| 曲线（投影源） | `{"kind":"curve","id":<int>}` | 复用 `native/generic.cpp` 的 `curve` 分支：`PRO_CURVE` 几何 ID（**非负 32 位**） |
| 方向来源 | `{"kind":"datum_plane","label":...}` / `{"kind":"datum_axis_feature","label":...}` / `{"kind":"edge","id":...}` / `{"kind":"curve","id":...}` | 复用既有 `resolve()`；必须能读出**真实方向向量**，读不出即拒绝 |
| 基准面（trim 工具） | `{"kind":"datum_plane","label":...}` | `ProTrim.h` 允许 `PRO_DATUM_PLANE` 作为 `PRO_E_STD_USEQLT_QLT` |

**ID 类型规则（硬，S00 R1）**：

1. `quilt_id` 与 `surface_id` 是两套命名空间。把 quilt ID 填进 `{"kind":"surface","id":N}`，或把面 ID 填进 `{"kind":"quilt","id":N}`，都是**类型错误**：必须保留类型诊断后拒绝，不得"长得像就试一下"。
2. ID 只对**产生它的模型与 revision** 有效。保存/擦除/重载、重生成或拓扑改变后必须重新查询；跨模型比较 ID 数字**不是**任何验收判据。
3. `surface_ids` 是 quilt 的成员面，**不是** quilt 本身；`surface_ids` 可以直接用于面引用，但不得用来缝合或修剪 quilt。

**唯一性规则（硬）**：

1. 一个引用必须**唯一命中一个**几何项。命中 0 个 → 拒绝（"引用不存在"）；命中 ≥2 个 → 拒绝（"引用不唯一"）。
2. **不得**用"取第一个匹配项"冒充目标。`quilt_feature` 命中多个 quilt 时必须报错并列出候选。
3. 不得用 body 布尔替代 quilt 语义；`body` 引用在三个 op 中一律拒绝。
4. 失效引用（标签不存在、已删除的墓碑标签、几何 ID 不存在）→ 拒绝，不静默降级。

### 4.2 sections 顺序

`surface_loft.sections` 是**有序**列表，首版长度必须为 2：

- 元素为**特征标签或特征 ID**（`str | int`，与既有 `LoftOp.sections` 同型）。
- 顺序即放样方向；index 0 为起点。
- **两个元素必须互不相同**（schema 层拒绝重复）。
- 每个元素必须解析到**一条曲线**（`PRO_CURVE`）；解析到复合曲线（`PRO_ENT_CMP_CRV`）或零条/多条 → 拒绝。
- 两条曲线的**相对位置不做任何规范化**：不排序、不镜像、不重排 Z。几何是否可放样由 Creo 判定，失败时回滚（§4.6）。

### 4.3 方向坐标系与单位

| 项 | 冻结语义 |
| --- | --- |
| 长度单位 | **毫米（mm）**。输入坐标、截面曲线、`endpoints_mm` 全部 mm |
| 角度单位 | **度（°）** |
| 面积单位 | **平方毫米（mm²）**，字段名后缀 `_mm2` |
| 长度字段后缀 | `_mm`（如 `curve_length_mm`） |
| 坐标系 | **模型坐标系**（模型默认 CSYS），不是草图局部坐标系 |
| 方向向量 | 归一化单位向量；长度 0 或非有限 → 拒绝 |
| `side` 语义 | 相对**显式 `direction_ref` 读出的方向**的翻转标志，映射到 `PRO_DIRECTION_FLIP_ALONG`/`PRO_DIRECTION_FLIP_AGAINST`；"positive"= 沿引用方向，"negative"= 相反。**具体哪一侧算 positive 由探针 P2 判定并回填本节**，不得按 GUI 命名 |
| `keep_side` 语义 | 见 §4.5，**不按 GUI 正负命名** |

### 4.4 真实测量字段（冻结）

**测量规则（三个 op 通用）**：

1. 面积必须来自**真实几何查询**，不得由输入参数回显或解析式反推。
2. 面积 API 选择：
   - 修剪后区域面积 → `ProContourAreaEval(ProSurface, ProContour, double*)`（外环围合面积，内部孔洞自动扣除）。
   - 单张未再划分曲面面积 → `ProSurfaceAreaEval(ProSurface, double*)`。
   - `ProQuiltVolumeEval` **不可**用于面积（只对闭合 quilt 有效，返回体积）。
3. 长度用 `ProCurveLengthEval`；端点用 `ProCurveXyzdataEval` 在参数 0 与 1 求值（复合曲线时导数参数传 NULL）。
4. 单位换算：`scale_to_mm` 取自 `length_scale_to_mm`（`native/assembly_units.h`）。
   - 长度：`mm = native_length * scale_to_mm`
   - 面积：`mm² = native_area * scale_to_mm²`
   - 比例未知（单位查询失败）→ **值为 null，并给出原因**（见 §4.4.1）。
5. 测量失败（API 返回非零、`PRO_TK_OUT_OF_RANGE` 面积过小、几何项缺失）→ 字段为 null + 原因，**不得填 0**。

#### 4.4.1 单位/测量不可用时的表达

三个 op 的测量字段统一为**可空数值 + 配套原因对象**：

```json
{
  "surface_area_mm2": 1234.5,
  "surface_area_status": {
    "available": true,
    "reason": null,
    "query_code": 0,
    "unit_name": "mm",
    "scale_to_mm_known": true
  }
}
```

- `available=false` 时：数值为 `null`，`reason` 必填（受控字符串，如 `"unit_scale_unknown"` / `"area_query_failed"` / `"no_measurable_region"`），`query_code` 保留原始 `ProError`（不可得时 `null`）。
- `available=true` 时：`reason` 为 `null`，`query_code` 为 0。
- **单位查询失败 ⇒ 所有测量字段 `null` + 原因**，不得按"看起来是 mm"直接采用原生值。

#### 4.4.2 各 op 返回字段（冻结）

**surface_loft**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `surface_area_mm2` | `float \| null` | 放样曲面的真实面积（mm²） |
| `surface_area_status` | `object` | §4.4.1 结构 |
| `surface_type` | `"datum_surface" \| "unknown"` | 产出确为 datum surface 才写前者 |
| `sections` | `list[str\|int]` | 原样回显输入截面（顺序不变） |

**project_curve**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `curve_length_mm` | `float \| null` | 投影所得曲线的真实长度 |
| `curve_length_status` | `object` | §4.4.1 结构 |
| `endpoints_mm` | `list[list[float]] \| null` | 投影曲线的两个端点，每个 `[x,y,z]`（模型坐标，mm）；**未知时整个字段为 null**，不得给部分端点 |
| `endpoints_status` | `object` | §4.4.1 结构 |
| `curve_id` | `int \| null` | 产出曲线几何 ID，供后续引用 |

**surface_trim**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `area_before_mm2` | `float \| null` | 被修剪 quilt 的面积（mm²） |
| `area_before_status` | `object` | §4.4.1 结构 |
| `area_after_mm2` | `float \| null` | 保留区域的面积（mm²） |
| `area_after_status` | `object` | §4.4.1 结构 |
| `kept_side` | `"one" \| "two" \| null` | 实际保留的一侧 |
| `kept_side_basis` | `object` | 保留侧的判定依据，见 §4.5 |
| `kept_quilt_id` | `int \| null` | 保留区域 quilt 几何 ID，供 `thicken` 消费 |

**quilt_merge**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `result_quilt_id` | `int \| null` | 合并结果 quilt 几何 ID，供 `thicken` 消费 |
| `area_mm2` | `float \| null` | 合并后 quilt 的真实面积（mm²） |
| `area_status` | `object` | §4.4.1 结构 |
| `input_area_mm2` | `float \| null` | 两个输入 quilt 面积之和（合并前测量） |
| `input_area_status` | `object` | §4.4.1 结构 |
| `closed` | `bool \| null` | 只来自 `ProQuiltVolumeEval` 探测：闭合为 `true`，明确开放为 `false`，探测失败为 `null` |
| `closed_status` | `object` | §4.4.1 结构 |
| `merge_type` | `"join"` | 首版唯一取值 |
| `inputs` | `object` | `{"target_quilt_id": int, "tool_quilt_id": int}` |

**所有测量字段在 compact/full 两种投影里都必须存在**（null 也保留字段与 status），compact 不得丢字段。

### 4.5 keep_side 语义（冻结）

**不按 GUI 正负命名。** `keep_side` 只能是 `"one"` / `"two"`，其物理含义由**工具的取向**决定，且必须可被测量验证：

- `keep_side="one"` → `PRO_E_PRIMARY_QLTSIDE = PRO_TRIM_PRIM_QLT_SIDE_ONE` **且** `PRO_E_MATERIAL_SIDE = PRO_TRIM_MATL_SIDE_ONE`。
- `keep_side="two"` → `PRO_E_PRIMARY_QLTSIDE = PRO_TRIM_PRIM_QLT_SIDE_TWO` **且** `PRO_E_MATERIAL_SIDE = PRO_TRIM_MATL_SIDE_TWO`。
- **2026-11-04 实机修正**：仅改 `PRO_E_PRIMARY_QLTSIDE` 不改变保留区域（`one`/`two` 实测同一侧同一面积）；决定保留侧的是 `PRO_E_MATERIAL_SIDE`。两个元素现在同时跟随 `keep_side`，不允许互相矛盾。薄修剪与双侧仍不在首版。
- `PRO_E_KEEP_TRIM_SURF_OPT` 首版固定为 `PRO_KEEP_TRIM_SURF_OPT_NO`（`=0`）。

**实测绑定（2026-11-04，Creo 12.4.0.0）**：`keep_side="one"` 保留**工具法向正侧**，`keep_side="two"` 保留负侧。证据（`build/live_trim_report.json`、`build/surface_chain/20261104-094447-635200/report.json`）：40×20 平面填充（800 mm²）被 x=5 基准面（法向 +X）修剪，`one` 得 700 mm²、外框 x∈[5,40]，`two` 得 100 mm²、外框 x∈[0,5]；圆柱面（1256.64 mm²）被 z=5 平面（法向 +Z）修剪，`one` 得 314.16 mm²（z>5）、`two` 得 942.48 mm²（z<5）。两次运行均 `saved_file_reloaded_and_verified=true`。

**`kept_side_basis` 必须回写判定依据**，使调用方能独立判断保留的是哪一块，而不是相信一个标签：

```json
{
  "keep_side": "one",
  "primary_quilt_side_value": -1,
  "material_side_value": 1,
  "tool_normal": [0.0, 0.0, 1.0],
  "target_centroid": [10.0, 5.0, 0.0],
  "kept_centroid": [10.0, 5.0, 0.0],
  "signed_offset_mm": 0.0
}
```

- `tool_normal`：修剪工具（quilt 或基准面）读出的**单位法向**（模型坐标）。
- `target_centroid` / `kept_centroid`：被修剪 quilt 与保留区域各自的几何质心（模型坐标，mm）；读不出时为 `null`。
- `signed_offset_mm` = `(kept_centroid − target_centroid) · tool_normal`，用于独立判断保留侧确实落在工具法向的一侧。

**一致性与失败规则**：

- 若 `signed_offset_mm` 与 `keep_side` 的预期方向矛盾（`one` 应使 `signed_offset_mm > 0`，`two` 应使 `< 0`），**该 op 必须失败并回滚**，不得回报成功。判据在质心可读时才生效。
- 若质心读不出（`target_centroid` 或 `kept_centroid` 为 null），`kept_side_basis` 保留已知字段、`signed_offset_mm=null`，但**不得**因此判失败（质心只是佐证，不是主判据）。
- `one`/`two` 与法向正负的绑定已于 2026-11-04 由实机回填（见本节实测绑定段）：`one` = 工具法向正侧，`two` = 负侧。`surface_trim` 因此解除门禁；判据仍是"两次独立模型的面积 + 外框"，不跨模型比 ID（R5）。

### 4.6 错误与回滚行为（冻结）

| 场景 | 行为 |
| --- | --- |
| schema 拒绝（非法枚举、截面数不对、引用种类不支持、重复引用、缺 kind、ID 类型不匹配） | **不派发 job**，不产生 `job_id`，不产生特征 |
| 原生运行时引用失效（标签已删除、几何 ID 在当前 revision 不存在、特征不含可用 quilt 几何项） | **允许已受理 job 失败**，走既有事务回滚，`rollback_succeeded=true`；不得承诺"所有引用错误都不建 job"（S00 R2） |
| 原生 `ProFeatureCreate` 失败 | 事务回滚，**不留下**新特征；`rollback_succeeded=true`；revision 不推进 |
| 测量失败（面积/长度查不到、单位未知） | **特征保留**（几何成功即成功），测量字段 `null` + 原因 |
| `keep_side` 与实测方向矛盾 | **op 失败并回滚**（§4.5） |
| 通道忙 | 立即 `isError=true`、`status="busy"`，携带 `blocking_*`；不排队、不重试 |
| 任何终态不确定（`unknown_outcome`） | 停止新提交，保留现场，不清保护 |

**引用稳定性（保存擦除重载后）**：

- 三个 op 的产出必须以**特征标签**注册进既有 `aliases` 机制（`native/generic.cpp:844` `remember()`），使后续 op 可用 `{"kind":"quilt_feature","label":...}` 引用。
- 保存 → 擦除 → 重载后，**同一标签必须仍解析到同一个 quilt 几何项**，且 `surface_area_mm2` 等测量值在重载后保持一致（±1e-6 相对容差）。
- 若重载后标签解析不到或解析到不同几何项，**该 op 不算通过**。

### 4.7 共享测量/引用 helper 的唯一归属

**唯一归属文件：`native/surface_measure.h`**（新建，仅本契约的三个 op 使用）。

- 内容范围（仅此四类，不得扩张）：
  1. `quilt_area_mm2(...)`：经 `ProContourAreaEval` / `ProSurfaceAreaEval` 求真实面积并换算 mm²，失败返回 `null` + 原因。
  2. `curve_length_mm(...)`：经 `ProCurveLengthEval` 求长度并换算 mm。
  3. `curve_endpoints_mm(...)`：经 `ProCurveXyzdataEval` 在参数 0/1 求两端点并换算 mm。
  4. `measurement_status_json(...)`：统一生成 §4.4.1 的 status 结构（含 `length_scale_to_mm` 的比例与原始查询码）。
- **维护人**：FEAT-009（surface_loft）实现者为首个维护人；FEAT-039（project_curve / surface_trim）实现者只**消费**，需要扩展时由集成人统一收取，**不得各自复制 helper**。
- Python 侧不新建共享测量模块：字段投影复用既有 `src/creo_mechdog/operation_results.py` 的投影入口。
- 既有 `native/inspection_units.h`（单位查询）与 `native/assembly_units.h`（比例换算）**只读复用，不改写**。

---

## 5. 最小几何 oracle（三个 op 各一个）

每个 oracle 必须**可独立解析**（有闭式解），不依赖外部参考值。

### O1 surface_loft：两平行直线截面 → 矩形面积

- 构造：在 z=0 平面上画一条直线 `S0`（从 (0,0,0) 到 (40,0,0)）；在 z=20 平面上画一条**平行**直线 `S1`（从 (0,0,20) 到 (40,0,20)）。
- 放样结果：一条矩形曲面，两条 40 mm 直边 + 两条 20 mm 侧边。
- 闭式解：`surface_area_mm2 = 40 × 20 = 800.0`（mm²，±0.5）。
- 附加断言：产出为 datum surface；`surface_type == "datum_surface"`；不是实体（模型无 solid，体积为 null/`has_solid=false`）。
- 失败判据：面积与 800 偏差 > 0.5；或产出是实体；或两截面被静默合并/交换顺序（回显 `sections` 必须仍是 `[S0, S1]`）。

### O2 project_curve：平面上沿 −Z 的投影曲线长度（S00 R4 修订）

- 构造：目标 quilt = 一个 **40 × 20 的平面矩形**（`surface_fill`，z = 0，覆盖 x∈[0,40]、y∈[0,20]）；源曲线 = z = 10 平面上的一条直线 `(5,10,10) → (35,10,10)`（长 30 mm）；投影方向 = **−Z**（垂直落到目标面）。
- 闭式解：投影结果落在 z=0 的平面上，是 x∈[5,35]、y=10 的直线段，长度仍为 30 mm。
- 域内性（新）：投影后的两个端点 `(5,10,0)`、`(35,10,0)` 必须落在目标面的有效域内（x∈[0,40]、y∈[0,20]）；若端点越界，该用例不成立，必须先退回修改构造，不得把截断结果当成功。
- 断言：`curve_length_mm == 30.0`（±0.5）；`endpoints_mm` 两点 z = 0（±1e-6）；两点 x 跨距 30.0（±0.5）；`curve_id` 非空。
- 反方向用例：沿 +Z 投影时源线与目标面无交点 ⇒ 必须返回空结果与原因，**不得回显源曲线**（源线 z=10 ≠ 0，可直接分辨）。
- 失败判据：长度与 30 偏差 > 0.5；或端点 z ≠ 0；或结果端点是源线端点（z = 10）——这直接判定"只回显输入、冒充投影"。

### O2b project_curve：圆柱面投影（有效域与多交点待定义）

- 状态：**候选，定义未冻结**。旧表述"高 20 mm 圆柱承载长 30 mm 源线"几何上不自洽（源线比承载面高），已撤销，不得作为验收 oracle。
- 后续定义必须同时给出：圆柱的有效域（周向角区间 + 轴向区间）、源线的有效域、投影方向与法向关系、多交点（源线穿过圆柱前后两侧）时的分支选择规则。
- 在该定义冻结前，圆柱投影只作**探索性观察**，不进入 oracle 计数与通过判据。


### O3 surface_trim：矩形面直线二分 → 面积守恒

- 构造：目标 quilt = 一个 **40 × 20 的平面矩形**（`surface_fill` 闭合矩形草图，z=0）；工具 = 一张**穿过矩形中部的基准面**（法向 +X，过 x=20 的平面）。
- 闭式解：矩形被二分，两块各 20 × 20 = 400.0 mm²。
- 断言（`keep_side="one"`）：`area_before_mm2 == 800.0`（±0.5）；`area_after_mm2 == 400.0`（±0.5）。
- 守恒断言：再跑一次 `keep_side="two"`，`area_after_mm2 == 400.0`（±0.5），且 `one` 与 `two` 的 `area_after_mm2` 之和 == `area_before_mm2`（±1.0）。
- **两侧产物必须不同（S00 R5 修订）**：判据是**实测位置**——`keep_side="one"` 的保留区域覆盖 x∈[0,20]，`keep_side="two"` 覆盖 x∈[20,40]（各 ±0.5），且 `kept_side_basis.signed_offset_mm` 符号相反。**不得**用不同模型（或不同 revision）之间比较 `kept_quilt_id` 数字来证明两侧不同：ID 只对产生它的模型与 revision 有效。
- 同一模型内两次保留侧运行时，才额外记录 `kept_quilt_id`，并要求两次不同；该字段在该场景外只作诊断。
- 失败判据：两个保留区域的位置区间相同（两侧其实没变）却回报成功；或面积不守恒；或 `area_before_mm2` 为 0/null。

---

## 6. 给 Q08–Q10 的确切交接（函数/模型名）

### 6.1 Python 侧（`src/creo_mechdog/schema.py`）

| op | 模型类 | 字段 |
| --- | --- | --- |
| `surface_loft` | `SurfaceLoftOp` | `op: Literal["surface_loft"]`、`label: Label`、`sections: list[str \| int]`（长度恰 2）、`interpolation: Literal["straight"] = "straight"` |
| `project_curve` | `ProjectCurveOp` | `op: Literal["project_curve"]`、`label: Label`、`target: dict[str, Any]`（quilt 引用）、`source: dict[str, Any]`（curve 引用）、`direction_ref: dict[str, Any]`、`side: Literal["positive","negative"]` |
| `surface_trim` | `SurfaceTrimOp` | `op: Literal["surface_trim"]`、`label: Label`、`target: dict[str, Any]`（quilt 引用）、`tool: dict[str, Any]`（quilt 或基准面）、`keep_side: Literal["one","two"]` |

- 三者都加入既有 `Operation` 联合（`schema.py:1475`）。
- 引用校验复用 `schema.py:1580-1607` 的 `references()` 递归校验；新增 kind 只允许 `quilt_feature` / `curve` / `datum_plane` / `datum_axis_feature` / `edge`。
- 结果投影字段名见 §4.4.2，写在 `src/creo_mechdog/operation_results.py` 的既有投影入口。

### 6.2 原生侧（`native/`）

| op | 建议文件 | 入口函数（静态 `void f(const J &op)`） |
| --- | --- | --- |
| `surface_loft` | `native/surface_loft.cpp`（或并入 `native/surfaces.cpp`） | `generic_surface_loft(const J &op)` |
| `project_curve` | `native/project_curve.cpp` | `generic_project_curve(const J &op)` |
| `surface_trim` | `native/surface_trim.cpp` | `generic_surface_trim(const J &op)` |

- 三者都在 `native/generic.cpp:2907` `execute_operation_body()` 的分发表里挂载（`else if (kind == "surface_loft")` 等），**只加分支，不改既有分支**。
- 共享测量 helper 全部来自 `native/surface_measure.h`（§4.7）。
- 元素 ID 用 SDK 头文件宏（`#include <Probbl.h>` / `<ProTrim.h>`）；**不写字面数值**。

### 6.3 工具/能力登记

- `capabilities.py` 登记三个新 op（`surface_solid` 家族下新增条目），说明首版边界与"未测"范围。
- `server.py` 增三个独立 MCP 工具（`creo_surface_loft` / `creo_project_curve` / `creo_surface_trim`），签名与 `creo_execute_plan` 的 op 一致。
- `references.py` 的参考契约表补三个工具的引用形态说明。

---

## 7. 实机原生探针清单（供集成人在获批串行窗口执行）

**本任务未执行下列任何探针。** 探针必须串行、单个模型、单次连接执行；每次探针独立记录结论"**可行** / **路线不成立** / **未验证**"，并把原始证据（元素树抽取、几何读数、原始错误码）写入报告。

### P1 — surface_loft 元素树探针（目标：边界混合树）

- **探针目标**：判定 `Probbl.h` 的边界混合树能否用两个直线截面在执行器内直接 `ProFeatureCreate` 成功，并读出面积。
- **创建什么**：
  1. 新建 part（`creo_new_part`）。
  2. 两个**独立直线草图**（非闭合）：`S0` 在 z=0，`S1` 在 z=20，两线平行且各长 40（O1 构造）。
  3. 用候选树（§2.1）尝试创建 `PRO_FEAT_DATUM_SURF` + `PRO_USE_SURFS` + `PRO_E_DTM_SRF_TYPE=PRO_E_DTM_SRF_TYPE_BND_BLEND`，`PRO_E_BNBLN_1DIR/PRO_E_BNBLN_DIR_CURVES` 内放两个 chain holder，每个装一条曲线。
- **抽取什么**：
  - 成功后 `ProFeatureElemtreeExtract` 抽取**实际创建出来的元素树**，逐节点与 §2.1 骨架对照，记录实际出现/缺失/多出的元素 ID（**按符号名记录**）。
  - `ProSurfaceAreaEval` / `ProContourAreaEval` 读面积；`ProFeatureTypeGet` 读特征类型；`ProFeatureGeomitemVisit` 读 quilt 几何项数量。
- **比较什么**：
  - 面积 == 800.0 mm²（±0.5）。
  - 特征类型 == `PRO_FEAT_DATUM_SURF`；quilt 几何项恰好 1 个。
  - 抽取树与 §2.1 骨架的差异清单。
  - `PRO_E_BLEND_TYPE` 的实际取值（回填 §2.1）。
- **结论判定**：
  - **可行** → 回填 §2.1 实际树，回填 §3.1 的 straight 语义；Q08 可开工。
  - **路线不成立** → 只阻断 surface_loft（Q08）；Q09/Q10 不受阻。
  - **未验证** → 不得据此开工，也不得据此宣布不可行。

### P2 — project_curve 元素树探针（目标：COPYTRIM 族可用性）

- **探针目标**：判定 COPYTRIM 族（`PRO_E_COPYTRIM_*`）能否构成可创建的特征树，并确定 `side` 的物理含义。
- **创建什么**：
  1. 新建 part；用 `extrude{mode:"surface"}` 造出圆柱面 quilt（O2 构造）。
  2. 造出源直线曲线（沿 Z，长 30，x=15）。
  3. 用候选树（§2.2）尝试创建 `PRO_FEAT_CURVE` + `PRO_E_COPYTRIM_CURVE_DATA`（含 `PRO_E_COPYTRIM_QUILT` 与 `PRO_E_COPYTRIM_CURVE_TBL`/`PRO_E_COPYTRIM_CURVE`）。
  4. 若第 3 步失败：**记录原始 `ProError` 与 `ProErrorlist` 逐项 element/type/error**（`native/geometry.cpp:125` `errors()`），再尝试 `ProDtmCrv.h` 的 `PRO_CURVE_TYPE_INTSRF` / `PRO_CURVE_TYPE_TWO_PROJ` 变体，并**明确记录该变体语义不同**。
- **抽取什么**：
  - 实际元素树（`ProFeatureElemtreeExtract`）+ 原始错误码。
  - 产出曲线几何 ID、`ProCurveLengthEval` 长度、`ProCurveXyzdataEval` 端点。
  - `side="positive"` 与 `side="negative"` 两次的端点差异（用于回填 §4.3 的方向绑定）。
- **比较什么**：
  - 长度 == 30.0 mm（±0.5）；端点 z 差 == 30.0（±0.5）；端点径向距离 == 10.0（±0.5）。
  - **产出曲线与源曲线不同**（端点径向距离 10 ≠ 15）——否则判定"没有真正投影"。
  - 两次 `side` 的端点必须分处圆柱两侧（若相同，说明 `side` 未生效）。
- **结论判定**：
  - **可行** → 回填 §2.2 实际树与 §4.3 的 `side` 绑定；Q09 可开工。
  - **路线不成立** → **只阻断 Q09（project_curve）**；Q10 的 trim 仍可开工，但"投影曲线作为 trim 工具"的子路径一并阻断；**不得用 body 布尔或曲面求交冒充投影曲线**。

#### P2 实测结论（2026-11-04，S04）

- COPYTRIM 族：三个候选树全部被 `ProFeatureWithoptionsCreate` 拒绝（-1）；PROJ_CRV 族四个候选树同样全部拒绝。
  `ProCurveType` 无投影类型值，`PRO_PROJ_*` 只存在于 `ProElemId.h`。**COPYTRIM/PROJECT 路线不成立**（明细见 §2.2.1）。
- 替代路线：`ProDtmCrv.h` INTERSECT 树本身可用（`REF_TYPE` 取 `PRO_CURVE_TYPE_INTSRF`），配合"源草图沿方向
  扫掠出的辅助面"构成真正的投影（明细见 §2.2.2）。这不是用曲面求交冒充投影：扫掠面由源曲线本身产生，
  交线逐点等于源曲线沿该方向的投影。
- 实机结果（`build/_live_project_probe2.py`，模型 `e7aadca24d66462c83d4139744b735bf` 等）：
  源直线 (5,10,10)-(35,10,10)、方向 -Z、目标 z=0 平面 quilt → 曲线长度 **30.000 mm**，
  端点 **(5,10,0)/(35,10,0)**，作业 `saved_file_reloaded_and_verified=true`；
  源圆弧（半径 8，圆心 (20,10,10)，0°→180°）→ 长度 **25.133 mm**（π·8），端点 **(12,10,0)/(28,10,0)**；
  `side="positive"`（方向 +Z，目标在背侧）被拒，消息含 `target quilt lies behind the source curve`。
- **未实测**：多分支拒绝、非平面目标、方向与草图法向不平行的拒绝、圆柱面目标（O2b 仍待定义）。

### P3 — surface_trim 元素树探针（目标：keep_side 物理语义）

- **探针目标**：判定 `ProTrim.h` 的 use-quilt 变体能否成功，并确定 `one`/`two` 与工具法向的绑定。
- **创建什么**：
  1. 新建 part；`surface_fill` 一个 40 × 20 平面矩形（O3 构造）。
  2. 建一张过 x=20、法向 +X 的基准面作工具。
  3. 用候选树（§2.3）创建 `PRO_FEAT_CUT` + `PRO_USE_SURFS` + `PRO_E_SRF_TRIM_TYPE`/`PRO_E_SURF_TRIM_TYPE` = `PRO_SURF_TRIM_USE_QLT`，`PRO_E_TRIM_QUILT` = 目标 quilt，`PRO_E_STD_USEQLT_QLT` = 基准面，`PRO_E_MATERIAL_SIDE` = `PRO_TRIM_MATL_SIDE_ONE`，`PRO_E_PRIMARY_QLTSIDE` = `PRO_TRIM_PRIM_QLT_SIDE_ONE`，`PRO_E_KEEP_TRIM_SURF_OPT` = `PRO_KEEP_TRIM_SURF_OPT_NO`。
  4. 重复一次，`PRO_E_PRIMARY_QLTSIDE` = `PRO_TRIM_PRIM_QLT_SIDE_TWO`。
- **抽取什么**：
  - 实际元素树 + 原始错误码。
  - 两次结果的保留 quilt 几何 ID、面积（`ProContourAreaEval`）、工具法向、目标/保留区域质心。
- **比较什么**：
  - `area_before_mm2` == 800.0（±0.5）；两次 `area_after_mm2` 均 == 400.0（±0.5）；两者之和 == `area_before_mm2`（±1.0）。
  - 两次 `kept_quilt_id` **不同**。
  - 两次 `signed_offset_mm` **符号相反**（用于回填 §4.5 的 `one`/`two` 绑定）。
- **结论判定**：
  - **可行** → 回填 §2.3 实际树与 §4.5 的 `one`/`two` 绑定；Q10 可开工。
  - **路线不成立** → **只阻断 Q10**；Q08/Q09 不受阻。
  - `one`/`two` 绑定在回填前，**不得公开 `keep_side`**（§3.3）。

### 探针通用纪律

- 三个探针**串行**执行，一个失败立即停；不得并发、不得重提已受理 job。
- 不得启动/结束/重启 Creo，不清 unknown 保护，不占用其他工作树的通道。
- 每次探针必须记录：`job_id`、`model_id`、revision、实际创建树的符号名清单、几何读数、原始错误码、是否保存重载、结论三态。
- 探针报告写进新目录（不覆盖历史），并附受测源码指纹与 dirty 状态。

---

## 8. 未验证范围（交接时必须一并说明）

| 项 | 状态 |
| --- | --- |
| 三个 op 的**实际创建元素树** | **未验证**（须 P1–P3） |
| `PRO_E_BLEND_TYPE` 取值语义 | **未验证** |
| `TAN_COND_FREE` 是否有可引用符号 | **未验证**（头文件只有文字） |
| COPYTRIM / PROJECT 族的父子关系与合法值 | **已实测不可用**（7 个候选树全部被内核拒绝，见 §2.2.1） |
| `direction_ref` → `PRO_E_DIRECTION_COMPOUND` 的接线方式 | **未验证**（project_curve 不依赖该容器；方向由扫掠面与包围盒符号距离实测） |
| `keep_side` 的 `one`/`two` 物理绑定 | **已实测**（S02，见 §2.3） |
| `side` 的 `positive`/`negative` 物理绑定 | **部分实测**：方向取 `direction_ref` 向量并按 `side` 取反；目标在背侧时实测拒绝 |
| `PRO_E_BLEND_SECTIONS` / `PRO_E_BLEND_ATTRIBUTES` / `PRO_BLEND_SURF` / `PRO_STD_BLEND` / `ProSurfaceEval` / `ProMeasurable` | **本机 SDK 不存在**（02 方案的这些名字不可用） |
| 本机 `constants.inc` 未导出 `ProTrim.h` / `Probbl.h` / `ProStdSection.h` / `ProMerge.h` 的符号 | **已核实**（需集成人统一补 `HEADERS` 后重新生成） |
| Creo 9 / Creo 10 的同名常量与树 | **未验证**（本机只有 12.4） |
| 本任务未连接 Creo、未编译、未占通道 | 事实记录 |

---

## 9. 2026-11-01 实机探针结果（P1–P3）

环境：Creo 12.4.0.0 / Toolkit x86e_win64 / 本机匹配 SDK；提交 `807cf22` + 实机修复（`native/preview.h` 合并截断、三点定面约束校验改为数组计数、`generate_constants.py` 增补 `Probbl.h`/`ProTrim.h`/`ProStdSection.h`/`ProMerge.h`）。探针通过 `creo_create_feature_tree` 低层入口逐条构造候选树，串行执行；每次新零件、单作业。

| 探针 | 前置 | 创建结果 | 抽取/状态 | 判定 |
| --- | --- | --- | --- | --- |
| P1 surface_loft | 两个平行直线草图（z=0 / z=20，各 40 mm），由 `feature_geometry` 取到真实曲线 id 44/52 | `ProFeatureWithoptionsCreate=0` | 生成特征 54 `P1_BLEND`，type 942（datum surface），**status 6 = `PRO_FEAT_UNREGENERATED`，无 geometry item**；无 `ProErrorlist` 内容 | **路线不成立**（本次树未能再生） |
| P2 project_curve | 圆柱面 quilt + 沿 Z 源直线（feature_geometry 取曲线 73） | 作业 `68a4ec1edb8f42a8866bb9d9645ce64d` 失败 | `ProFeatureWithoptionsCreate` 失败；COPYTRIM 候选树未被接受 | **路线不成立** |
| P3 surface_trim | 40×20 `surface_fill` quilt + 过 x=20 基准面 | `ProFeatureWithoptionsCreate=0`（两次，含补 `PRO_E_BODY`） | 生成特征 87 `P3_ONE`，type 916（cut），**status 6 = `PRO_FEAT_UNREGENERATED`，无 geometry item** | **路线不成立**（本次树未能再生） |

**结论与影响（2026-11-01）：**

- 三棵候选树均未产生可再生的健康特征；P1/P3 的特征停在 `PRO_FEAT_UNREGENERATED`，没有可读 `ProErrorlist`，不能据此宣称“元素树路线可行”。
- `PRO_E_CTRL_PTS`/`PRO_E_BLEND_TYPE`、`PRO_E_BNBLN_TAN_COND_TYPE`（`TAN_COND_FREE` 无符号定义）与 trim 的 body/side 组合仍是未定项；本次没有继续试错，避免把未经证明的树写进公开实现。
- **Q08 / Q09 / Q10 均不开工**，直到重新取得“可行”证据并回填 §2/§3/§4。Q08 只受 P1 阻断，Q09 只受 P2 阻断，Q10 只受 P3 阻断；本次三项同时不成立。
- 证据：`build/live-0.11.1/p1_probe.json`、`p2_probe.json`、`p3_probe.json` 及对应 `jobs/*/native.log`（本机忽略目录）。

### 9.1 2026-11-04 S04 复测与交付（project_curve）

环境：Creo 12.4.0.0 / Toolkit x86e_win64 / 本机匹配 SDK；分支 `codex/DEV-067-alphai-plan`；
`bridge.py build` 重新编译执行器后逐条实机运行（先解除门禁取证，取证后按结论落实发布状态）。

| 用例 | 前置 | 结果 | 判定 |
| --- | --- | --- | --- |
| 7 个候选投影树 | 40×20 fill + z=10 源草图 + 方向平面 | COPYTRIM×3、PROJ_CRV×4 全部 `-1` | 族不可用 |
| 直线投影 | 源 (5,10,10)-(35,10,10)，方向 -Z，目标 z=0 | 长度 30.000 mm，端点 (5,10,0)/(35,10,0)，保存重载已验证 | 通过 |
| 圆弧投影 | 半径 8、圆心 (20,10,10)、0°→180° | 长度 25.133 mm，端点 (12,10,0)/(28,10,0) | 通过 |
| 反向投影 | 同上但 `side="positive"`（+Z） | 拒绝：`target quilt lies behind the source curve` | 通过（拒绝即期望） |

证据：`build/live_project_probe.json`（7 棵候选树逐条）、`build/live_ref_probe.json`（引用隔离）、
`build/live_project_probe2.json`（三条几何用例）及对应 `jobs/*/native.log`（本机忽略目录）。

统一驱动 `tools/test_surface_chain.py --case project --live --confirm-session-usable`
在重启 Creo 会话后跑通（run `20261104-134443-396700`，6 个作业，18 项检查全通过）：
`session_ready`、直线 30.000 mm/端点精确、圆弧 25.1327 mm/端点精确、两次 `saved_file_reloaded_and_verified`、
`route=swept_surface_intersect`、`helper_feature_id=95`、`direction_basis=datum_plane_normal`、
以及 `wrong_side_refused`（`target quilt lies behind the source curve for side 'positive'`）。
驱动为此修了两处自身缺陷：`wait_ready` 现在只在首次轮询请求一次 retry（否则每次轮询都会重开一个协调器尝试，
旧状态永远停在 active 相位），提交用作业自身回报的 revision，不再额外发只读刷新作业占住 `pending_job`。

### 9.2 2026-11-04 S04 消费者：surface_trim 的 use-curve 变体

环境同上（Creo 12.4.0.0，重启会话后单通道串行）。

| 用例 | 前置 | 结果 | 判定 |
| --- | --- | --- | --- |
| 侧向组合矩阵 | 40×20 填充 + z=0 直线（y=15） | `MATERIAL_SIDE`=1/2 → 200 / 600 mm²；=3 → 两个 quilt；`PRIMARY_QLTSIDE` 无影响；曲线反向交换保留侧 | 语义确定 |
| 操作符 `flat` | 同一模型经公开 `surface_trim`，工具为草图曲线 `{kind:curve,id:88}` | 面积 800→600，`kept_quilt_id=82`，`saved_file_reloaded_and_verified=true`，`kept_side_basis={tool_kind:curve, side_reference:curve_direction}` | 通过 |
| 操作符 `projected` | 先投影到该 quilt，再用投影曲线修剪同一 quilt | 修剪几何成立，但保存阶段 `ProMdlnameBackup=-1`，作业回滚、目标仍为 800 | 边界（见 §2.3.2） |

证据：`build/live_usecurve_trim_probe.json`（侧向矩阵，10 个模型）、`build/live_op_trim_probe.json`（两个操作符形态）。
实现侧同时发现并修正一处真实缺陷：use-curve 特征创建后立即读状态是 `PRO_FEAT_FAILED(6)`，必须先再生的模型再判状态。
