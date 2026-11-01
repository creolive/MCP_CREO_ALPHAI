# FEAT-039：纯曲面链路算子（trim / merge / boundary_blend / offset 与检测查询）

日期：2026-10-18。类型：功能。优先级：P1。状态：待规划。目标版本：未排期。

来源：外部 0.3.5 曲面链路反馈 §1/§4（Creo 10.0.0.0 / release 42），触发场景为[可乐瓶五爪花瓣瓶底任务书](../validation/feedback-0.3.5-surface-2026-10-18/可乐瓶五爪花瓣瓶底建模任务书.docx)纯曲面法——8 步中 5 步无对应工具，链路几何上不可执行。见[反馈原件](../validation/feedback-0.3.5-surface-2026-10-18/report.md)。关联 [FEAT-009](FEAT-009.md)（loft 曲面模式）、[FEAT-017](FEAT-017.md)（曲面用法扩展）、[BUG-052](BUG-052.md)（曲面类型查询）。

## 缺口清单（反馈定 P0，供排期参考）

| 算子 | 现状 | SDK 常量就绪度 |
| --- | --- | --- |
| `surface_trim`（曲面修剪，keep_side/material_side） | 无任何 trim；`solidify{cut}` 仅基准面裁实体 | 元素名已导出，**ProSurfTrimType 等 5 个枚举 15 个常量未导出**（薄修剪另加 11 个） |
| `quilt_merge`（面组合并/缝合，返回 closed） | `boolean_bodies` 只接受 body 不接受 quilt | `PRO_FEAT_MERGE`/`PRO_E_MERGE` 已导出，**只差封装与验证** |
| `boundary_blend`（边界混合/G1 桥接，逐侧连续性与权重） | `surface_fill` 仅平面填充 | `PRO_E_BNDRY*` 已导出 21 条 |
| `quilt_offset`（面组偏置） | 无；`thicken` 是加厚成实体，语义不同 | 未核对 |
| loft 曲面模式/非平行截面 | 归 [FEAT-009](FEAT-009.md) | — |
| 检测查询：面积、`min_wall_thickness`/采样、斑马纹/曲率 | inspect 仅 volume_mm3 | — |

## 建议实施顺序（反馈 MVR，每步独立可验收）

1. 补 `constants.inc`：`ProTrim.h` 核心枚举 → 低层 `creo_create_feature_tree` 立即可构造曲面修剪；
2. 高层 `creo_surface_trim`（target/tool/keep_side，返回修剪前后面积）；
3. 高层 `creo_quilt_merge`（targets/tools/intersect，返回 closed——能否 solidify 的判据）；
4. `creo_loft` 曲面模式与 new_body（FEAT-009 范围，本项联动）；
5. `creo_boundary_blend`；6. `creo_quilt_offset`；7. 面积/最小壁厚查询。

做到 1–3 即完成"修剪 + 缝合 + 实体化"最小闭环。外部已提供 STL 回归基准（加料版/求差版两个模型）。

## 范围

- 每个算子先定输入引用格式（quilt_feature label/edge id）、keep_side 语义与返回字段（closed、面积前后值），再实现；沿用 capabilities 登记（`capabilities.py`）与 compact 白名单。
- 不改变既有 `solidify`/`thicken`/`surface_fill` 语义；loft 曲面模式在 FEAT-009 内推进、本项只联动验收。
- 曲面模式下 `axis_pattern` 对 quilt 的阵列有效性需补验证（反馈标注未验证）。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | schema + 单测 | 每算子的引用/参数校验与错误可判读；capabilities/文档同步 |
| 本机 Creo 12.4 | 任务书纯曲面法逐步最小用例（筒面+半球修剪、两截面放样曲面、五爪阵列修剪、中心封闭、merge→solidify） | 几何与体积对照解析值；保存重载通过；失败路径回滚与 revision 契约不变 |
| 回归基准 | 可乐瓶任务书整链 + 外部 STL 对比 | 仰视五瓣 72° 对称、爪尖着地、壁厚 0.3 无破面（min_wall 查询自证） |

## 实现与证据

2026-10-18 仅登记。正向旁证：同轮 `boolean_bodies` subtract 单 tool 成功（407,482.40 mm³，与手算差 0.6 mm³）、`revolve{new_body}` 绕道可生成独立爪实体。原始证据见反馈原件 §1/§4/§5。

### Q07 契约冻结（2026-11-01）

**冻结契约：[docs/development/G5-NATIVE-CONTRACT.md](../development/G5-NATIVE-CONTRACT.md)**。本卡的 `surface_trim` / `project_curve` 归该契约 Q09（project_curve）与 Q10（surface_trim）消费；`quilt_merge` / `boundary_blend` / `quilt_offset` / 面积与最小壁厚查询**不在**本契约范围，仍按本卡原缺口清单另行规划。

本机 SDK 核实结论（Creo 12.4.0.0，逐项见契约 §1.3、§1.4）：

| 结论 | 内容 |
| --- | --- |
| **已核实** | `ProTrim.h` 的**完整**曲面修剪元素树与四种变体（use-quilt / use-curve / thin / silhouette）；`ProSurfTrimType` 五个枚举值；`ProTrimMatlSideOpts`(1/2/3)、`ProTrimPrimaryQltSide`(-1/+1)、`ProTrimStdQuiltSideOpts`(1/2/3)、`ProKeepTrimSurfOpts`(0/1)；`PRO_E_TRIM_QUILT`/`PRO_E_SRF_TRIM_TYPE`/`PRO_E_SURF_TRIM_TYPE`/`PRO_E_STD_USEQLT_QLT`/`PRO_E_STD_CURVE_COLLECTION_APPL`/`PRO_E_MATERIAL_SIDE`/`PRO_E_PRIMARY_QLTSIDE`/`PRO_E_KEEP_TRIM_SURF_OPT`；`PRO_E_SRF_MRG_*` 合并族(`ProMerge.h`)；`PRO_E_CRV_IP_*` 交线曲线族(`ProDtmCrv.h`)；`ProContourAreaEval`（外环内面积、扣孔洞）、`ProSurfaceAreaEval`、`ProQuiltVolumeEval`（**仅闭合 quilt**）、`ProCurveLengthEval`、`ProCurveXyzdataEval` |
| **本机 SDK 差异** | 外部方案把 surface_trim 说成"Copy-Trim 特征本身"，**不成立**：本机 COPYTRIM 五个元素无任何父子关系文档；真正的曲面修剪是独立的 `PRO_FEAT_CUT` + `PRO_USE_SURFS` + `PRO_E_SRF_TRIM_TYPE` 特征。`PRO_E_TRIM_QLT_SIDE` **不是通用 trim 侧元素**（其语义按父特征族分化为 `ProExtTrimQltSide`/`ProRevTrimQltSide`/`pro_sweep_trimqlt_side`，而 `ProTrim.h` 根本不含该元素）；trim 侧用 `PRO_E_MATERIAL_SIDE`/`PRO_E_PRIMARY_QLTSIDE`/`PRO_E_STD_USEQLT_SIDE`。0.3.5 反馈所称"`PRO_E_BNDRY*` 已导出 21 条"在本机**只有 1 条**（`PRO_E_BNDRY_CONTRS`） |
| **未验证** | `keep_side` 的 `one`/`two` 与工具法向的物理绑定；`PRO_E_SURF_TRIM_TYPE` 的合法值在本机 `constants.inc` 未导出（`ProTrim.h` 不在 `HEADERS`） |

**首版能力边界（契约 §3.3）：** 目标恰好 1 个 quilt、工具恰好 1 个 quilt 或基准面（use-quilt 变体）、`keep_side` ∈ `{one,two}`；薄壳、曲线工具（use-curve 变体）、多区域/孔环**不公开**。**body 布尔不可替代 quilt 修剪语义**（`boolean_bodies` 只接受 body）。

**返回字段冻结（契约 §4.4.2）：** `area_before_mm2`/`area_after_mm2`（各带 `*_status`）、`kept_side`（`"one"|"two"|null`）、`kept_side_basis`（含 `tool_normal`、`target_centroid`、`kept_centroid`、`signed_offset_mm`，使保留侧可被独立验证，不按 GUI 正负命名）。单位查询失败 ⇒ 数值 null + 原因，**不得填 0**。

**下一步：** Q09 实现 `project_curve`（模型 `ProjectCurveOp`；原生 `generic_project_curve`），Q10 实现 `surface_trim`（模型 `SurfaceTrimOp`；原生 `generic_surface_trim`）。两者开工前必须分别完成契约 §7 的 **P2 / P3 实机探针**并回填实际元素树。P2 判定"路线不成立"**只阻断 Q09**（Q10 的 trim 仍可开工，但"投影曲线作为 trim 工具"的子路径一并阻断），**不得用 body 布尔或曲面求交冒充投影曲线**；P3 判定"路线不成立"**只阻断 Q10**。共享测量 helper 唯一归属 `native/surface_measure.h`（契约 §4.7，由 FEAT-009 实现者维护，本卡实现者只消费）。


## 2026-11-01 Q15 离线集成状态

离线开发完成，待实机验收。来源及合并提交见 [Q15 集成报告](DEV-053-Q15-integration-2026-11-01.md)。此状态不表示原生构建、Creo 实机、主干合入或发布完成。
