# FEAT-058 原生矩形平面壁契约（sheetmetal_planar_wall / resize_sheetmetal_planar_wall）

状态：**冻结（实机已验收，2026-11-04）**。关联条目：[FEAT-058](../work-items/FEAT-058.md)、BUG-032、FEAT-014。实现：`native/planar_wall.{h,cpp}`、`src/creo_mechdog/native_planar_wall.py`、`server.py`。

本文件是这两个算子的唯一接口依据：元素树、方向语义、测量字段、拒绝条件和"已验证 / 未验证"边界都以本文件为准，需要改动时先改本文件、再改代码。

## 0. 范围与证据边界

| 项 | 内容 |
| --- | --- |
| 本机 SDK | `C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit\includes` |
| 实机环境 | Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit 与许可（2026-11-04） |
| 实机证据 | `build/planar_wall/20261104T032633Z/adoption_live.json`（67 项全通过，含 8 个实机场景） |
| 离线证据 | `tests/unit/test_native_planar_wall.py`、`tools/test_adoption_planar_wall.py` 默认离线部分 |
| 未实测 | Creo 9 / 10 实机；非矩形截面；显式支撑面上 `plane` 的 origin 覆写；翻转支撑面以外的自定义方向 |

## 1. SDK 依据（已核实）

| 条目 | 结论 | 依据 |
| --- | --- | --- |
| 首壁不是 `PRO_FEAT_WALL` | `PRO_FEAT_WALL` + `PRO_SMT_WALL_TYPE_FLAT` 在本机返回 `ProFeatureWithoptionsCreate=-1`，元素错误 0 条 | 2026-11-04 探针（FEAT-058 记录） |
| 首壁＝Fill 特征 + 钣金分支 | `PRO_FEAT_DATUM_SURF` + `PRO_FLAT`，加 `PRO_E_IS_UNATTACHED_WALL`、`PRO_E_STD_DIRECTION`、`PRO_E_STD_SMT_SWAP_DRV_SIDE`、`PRO_E_BODY{PRO_E_BODY_USE=PRO_BODY_USE_NEW}`、`PRO_E_SMT_NEW_BODY_LINKED` | `ProFlatSrf.h` 表 4；`online_help/creo_toolkit/user_guide/Unattached_Planar_Wall_based_on_the_Fill_Tool.html` |
| 厚度元素 | 零件已有钣金厚度参数时 `PRO_E_STD_SMT_THICKNESS` 不可写；实现改为先驱动 `SMT_THICKNESS` 参数，无参数时才写元素 | `ProFlatSrf.h` 表 4；`online_help/.../Sheet_metal_Wall_Features.html` |
| 零件子类型 | 同一棵树在实体零件上"创建成功但重生成失败"，因此要求 `PROMDLSTYPE_PART_SHEETMETAL`；这是**本条直接首壁路线**的要求，不代表实体零件永远无法转换为钣金 | 2026-11-04 探针（模板诊断） |
| 壁体厚度读回 | `ProSmtBodyThicknessValueGet(ProSolidBody*, double*)`、`ProSmtBodyIsLinkedToPart(ProSolidBody*, ProBoolean*)` | `ProSheetmetal.h:603,623` |
| 零件厚度读回不可用于本模板 | 新鲜钣金模板中 `ProSmtPartThicknessValueGet` 读到 0，故本次以**壁体厚度**为独立证据 | 2026-11-04 实机日志 `PLANAR_WALL_BODIES` |
| SDK 差异保护 | 上述 Body 读回在 `tools/generate_constants.py` 的 `FUNCTION_PROBES` 中生成 `MECHDOG_HAS_*` 宏，缺失该 API 的 SDK 仍可编译，厚度记为未验证 | `native/planar_wall.cpp` 的 `#ifdef MECHDOG_HAS_ProSmtBodyThicknessValueGet` |

## 2. 创建（`sheetmetal_planar_wall`）

元素树（符号名，不写数值）：

```
PRO_E_FEATURE_TREE
├ PRO_E_FEATURE_TYPE              = PRO_FEAT_DATUM_SURF
├ PRO_E_FEATURE_FORM              = PRO_FLAT
├ PRO_E_STD_FEATURE_NAME          = <label>
├ PRO_E_STD_SECTION               = PRO_E_SEC_USE_SKETCH → 草图 <label>_sk
├ PRO_E_IS_UNATTACHED_WALL        = PRO_B_TRUE
├ PRO_E_STD_DIRECTION             = ±1（见 §4）
├ PRO_E_STD_SMT_SWAP_DRV_SIDE     = PRO_B_FALSE
├ PRO_E_STD_SMT_THICKNESS         = 仅当零件没有 SMT_THICKNESS 参数
├ PRO_E_BODY
│ └ PRO_E_BODY_USE                = PRO_BODY_USE_NEW
└ PRO_E_SMT_NEW_BODY_LINKED       = PRO_B_TRUE
```

驱动草图：`<label>_sk`，平面由 `plane`（`XY`/`XZ`/`YZ`）决定，实体为一个 `rectangle`，范围 `0..length` × `0..width`，`dimensioning=coordinates`。草图是真实特征名，因此**同时参与重名、计划内冲突与墓碑保护**：`<label>` 或 `<label>_sk` 已被占用时，准入与原生两侧都会拒绝，绝不覆盖受管别名。

创建后必须全部成立，否则该 op 失败并回滚：

1. 重生成成功；
2. 体积 = `length × width × thickness`（相对容差 1e-6，绝对容差 0.01 mm³）；
3. 存在至少一个承载几何的钣金 body；
4. 草图点尺寸 ≥ 4（矩形不被降维为等边）；
5. 有符号包络符合 §3；
6. 壁体厚度可读且等于请求厚度（SDK 缺 API 时记为未验证，Python 判定随之为未通过）。

## 3. 有符号包络（唯一形状证据）

包络按草图 frame（`origin/u_axis/v_axis/normal`）投影，取**带符号**区间，不是跨度，也不是世界包围盒排序：

| 轴 | direction=positive | direction=negative |
| --- | --- | --- |
| u | `[0, length]` | `[0, length]` |
| v | `[0, width]` | `[0, width]` |
| n | `[0, thickness]` | `[-thickness, 0]` |

只比跨度会放过"长在平面另一侧且整体偏移"的壁（2026-11-04 复核复现），因此原生 `planar_wall_require_envelope` 与 Python `envelope_problem` 都按上表逐轴比对上下界（容差 1e-6 相对、1e-6 绝对下限）。

## 4. 方向语义（实机测得，含修正）

* `direction=positive` 表示材料长在 **frame normal 的 + 侧**，`negative` 为 − 侧。
* `PRO_E_STD_DIRECTION=+1` 实际沿 **支撑面法向**增长，而具名平面的 sketch frame normal 是"请求轴"，两者可能反向：XZ 支撑面法向为 +Y 时 frame normal 为 −Y，直接用 `+1` 会得到 `n[-1,0]`（实机 job `c4753cb6…` 失败并暴露该缺陷）。
* 实现因此读取草图实际支撑面法向，`tree_direction = (support_flipped == negative) ? +1 : -1`，并在日志 `PLANAR_WALL_DIRECTION` 记录 `support_flipped`、`tree`、两个法向。
* 修正后 XY/negative、XZ/positive、YZ/positive 全部落在请求侧（见实机证据）。

## 5. 改型（`resize_sheetmetal_planar_wall`）

* 只接受由 `sheetmetal_planar_wall` 创建的壁；标签未知、由其他算子创建、或存在下游子特征时**在建模前**拒绝（准入读保存的 inspection 找子特征，原生再以 `ProFeatureChildrenGet` 复核）。
* 实现方式：按当前尺寸比例驱动该草图已有的点坐标尺寸，再重定义草图；不改壁特征、不重建、不动其它约束。
* 完成后必须成立：壁 `feature_id` 不变；点尺寸仍 ≥ 4；体积 = 新 `length × width × thickness`；有符号包络按 §3（沿用记录的 direction）；壁体厚度与记录一致。
* 改型开始前会从**已保存的文件**读出壁体厚度并与记录比对（`PLANAR_WALL_BODIES phase=loaded`），因此"保存重载后厚度保持"由改型作业自身证明。

## 6. 公开结果（`planar_wall`）

`creo_get_job` 的 `detail=compact` 与 `detail=full` 都会带 `planar_wall`（compact 白名单在 `bridge.compact_job`）。字段：`op`、`feature`、`feature_id`、`feature_id_before`（改型）、`feature_id_unchanged`、`sketch`、`length`、`width`、`thickness`、`direction`、`square`、`dimension_count`、`volume_mm3`、`frame`、`envelope`、`sheetmetal_body`、`sheetmetal_bodies`、`material_bodies`、`thickness_source`、`thickness_measured_mm`、`thickness_verified`、`thickness_body_code`、`thickness_loaded_mm`（改型）、`body_linked`、`problems`、`verified`。

`verified=true` 仅当 §2/§5 的证据项全部具备且一致；缺体积、缺方向、缺厚度读回都会变成 `problems` 而不是默认通过。

## 7. 已验证 / 未验证

已实机验证（2026-11-04，`build/planar_wall/20261104T032633Z`）：

* 100×60×1 → 6000 mm³；改型 120×80 → 9600 mm³，`feature_id` 49 不变，`saved_file_reloaded_and_verified=true`；
* `direction=negative` → 6000 mm³，包络 `n[-1,0]`；
* XZ / YZ 支撑面 → 各 6000 mm³；
* 方形 60×60×1 → 3600 mm³（`square=true`，5 个点尺寸），改型为 90×60 → 5400 mm³，同一 `feature_id`；
* 原生壁上挂 `sheetmetal_flange` 成功（壁出现子特征 104），随后改型在建模前被拒（`downstream dependencies ([104])`）；
* 默认（转换）模板模型上原生首壁被原生拒绝、revision 不变，随后旧 `sheetmetal_wall` 仍成功（42920 mm³）；
* 旧首壁 + 折边链路：42920 mm³ → 加折边 47178.64 mm³，保存重载通过。

未验证：Creo 9/10 实机；非矩形/多环截面；`plane` 传显式支撑面并覆写 origin；原生壁上第二个折边与四壁（受 FEAT-014/corner relief 限制）；WorkBuddy 黑盒。
