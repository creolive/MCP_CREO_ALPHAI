# FEAT-039：纯曲面链路算子（trim / merge / boundary_blend / offset 与检测查询）

> **当前状态（2026-11-07，DEV-072 对账）：** 0.13.0 / 0.14.0 / 0.15.0 所列子项已交付，R01 计量保护随 0.16.1 取得实机证据；**H04 曲面组级测量（open_edges/gap/overlap 四态）已于 2026-11-07 实机交付**（见文末 H04 段）；**H09 的替代路线「旋转球面」已实机交付**（见文末 H09 段，任意非平面 fill 仍不可用）；余项未排期，整卡不关闭。下方0.15.0段中“四壁仍gated”为该版本时点；钣金四壁BLIND miter基础现已由[FEAT-014](FEAT-014.md)随0.16.0交付。曲面merge、多截面放样及trim偏置门禁仍保持（H03 曲面合并已于 2026-11-07 按 INCOMPLETE 骨架路线实机反证，见文末 H03 段）；四壁成功不改变这些曲面边界。DEV-069剩余范围见[当前对账](../development/DEV069-MAIN-RECONCILIATION-2026-11-06.md)。

日期：2026-10-18。类型：功能。优先级：P1。状态：所列子项已交付，余项开放。**0.13.0 已交付**：S02 曲面修剪、S04 投影曲线、S05 曲面扫掠（开放/加盖/实体化）、S06 实体化判据、S07 法向偏置（`creo_surface_offset`）、S08 完整链路、S09 模块化、W01 端点焊接本体；**0.14.0 已交付**（2026-11-06 发布）：W05 `extrude_depth` 回执与 W06 只读预览/失败回滚。**0.15.0 已交付**（2026-11-06）：R05 矩阵/失败上下文、R07 曲面引用契约与 R09 折边文案。**0.18.3 已交付**（2026-11-07）：H04 曲面组级 `open_edges`/`gap_max_mm`/`overlap` 四态测量（新增只读公开工具 `creo_measure_surface_group`）与 H06 `surface_trim` 保留侧真实形心/bbox/世界方向，见 [H04 证据](../validation/feat039-h04-surface-group-2026-11-07/EVIDENCE.md)与 [H06 证据](../validation/feat039-h06-kept-side-2026-11-07/EVIDENCE.md)。**仍 gated / 未排期**：S03 缝合——H03 已按 INCOMPLETE 骨架路线实机反证，仍 4 个 `PRO_SURFACE`、0 个 `PRO_QUILT`，见 [H03 证据](../validation/feat039-h03-quilt-merge-incomplete-2026-11-07/EVIDENCE.md)；独立 quilt offset、任意非平面填充（无原生闭环输入通道；中心 R8 场景的旋转球面替代路线见文末 H09 段，fill 本体仍不开放）、多截面/边界混合及 `surface_trim` 的 `offset_mm`/`offset_side` 新语义未排期。S10 的发布交付见 0.13.0 发布记录。公开工具 102→104（含本卡 `creo_measure_surface_group` 与 FEAT-009 `creo_surface_loft`）。目标版本：0.13.0 / 0.14.0 / 0.15.0 / 0.18.3（均已交付子项）；余下曲面项未排期。

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

**能力边界（契约 §3.3）：** 目标恰好 1 个 quilt；工具为 1 个 quilt、基准面（use-quilt 变体）或 1 条曲线（use-curve 变体，2026-11-04 实机加入）；`keep_side` ∈ `{one,two}`。薄壳、多工具、多区域/孔环**不公开**；曲线工具下"两侧都保留"也不公开。**body 布尔不可替代 quilt 修剪语义**（`boolean_bodies` 只接受 body）。

**返回字段冻结（契约 §4.4.2）：** `area_before_mm2`/`area_after_mm2`（各带 `*_status`）、`kept_side`（`"one"|"two"|null`）、`kept_side_basis`（含 `tool_normal`、`target_centroid`、`kept_centroid`、`signed_offset_mm`，使保留侧可被独立验证，不按 GUI 正负命名）。单位查询失败 ⇒ 数值 null + 原因，**不得填 0**。

**下一步：** Q09 实现 `project_curve`（模型 `ProjectCurveOp`；原生 `generic_project_curve`），Q10 实现 `surface_trim`（模型 `SurfaceTrimOp`；原生 `generic_surface_trim`）。两者开工前必须分别完成契约 §7 的 **P2 / P3 实机探针**并回填实际元素树。P2 判定"路线不成立"**只阻断 Q09**（Q10 的 trim 仍可开工，但"投影曲线作为 trim 工具"的子路径一并阻断），**不得用 body 布尔或曲面求交冒充投影曲线**；P3 判定"路线不成立"**只阻断 Q10**。共享测量 helper 唯一归属 `native/surface_measure.h`（契约 §4.7，由 FEAT-009 实现者维护，本卡实现者只消费）。


### 2026-11-01 P2/P3 实机探针：均不成立

- **P2（COPYTRIM）**：圆柱面 quilt + 沿 Z 源直线（真实曲线 id 73）尝试 `PRO_FEAT_CURVE` + `PRO_E_COPYTRIM_CURVE_DATA`，作业 `68a4ec1edb8f42a8866bb9d9645ce64d` 失败，`ProFeatureWithoptionsCreate` 未通过；COPYTRIM 族在本机仍无可证树。**Q09 不开工**。
- **P3（use-quilt trim）**：40×20 `surface_fill` + 过 x=20 基准面，按 `ProTrim.h` §2 完整树（含补 `PRO_E_BODY`）两次创建：`ProFeatureWithoptionsCreate=0`，但特征 87 `P3_ONE` type 916 停在 status 6（`PRO_FEAT_UNREGENERATED`）、无 geometry item，作业按不健康特征回滚。**Q10 不开工**。
- 详见[契约 §9](../development/G5-NATIVE-CONTRACT.md#9-2026-11-01-实机探针结果p1p3)；证据 `build/live-0.11.1/p2_probe.json`、`p3_probe.json`。

## 2026-11-01 Q15 离线集成状态

离线开发完成，待实机验收。来源及合并提交见 [Q15 集成报告](DEV-053-Q15-integration-2026-11-01.md)。此状态不表示原生构建、Creo 实机、主干合入或发布完成。

## 2026-11-04 S00 增量：派工登记与契约修订

- 0.11.7 反馈（F03，Creo 10）证实：低层 10 元素树 trim 成功并保存重载，merge 引用 trim 结果 `ProFeatureGeomitemVisit -4` 两版同码；`-4` 的单一含义未证实，不写死翻译。
- [0.11.7 计划](../superpowers/plans/2026-11-04-0.11.7-surface-chain-improvement-plan.md) 的 S02（surface_trim）/ S03（quilt_merge）/ S04（project_curve，含 use-curve 消费）派工归本卡；原生入口统一 `static void generic_<op>(const J &op)`。
- G5 契约按 S00 修订（[§0.1](../development/G5-NATIVE-CONTRACT.md)）：显式 `{"kind":"quilt","id"}` 引用（与 `quilt_feature` 并存）、quilt/surface ID 不可互换、schema 不建 job 与运行时引用失效分层（已受理 job 可失败并回滚）、O2 投影 oracle 纠偏、O3 两侧判据改实测位置与 `signed_offset_mm`（不跨模型比 ID）。
- P1/P2/P3 旧探针失败历史保留为 `route_not_established`/`unverified`（`tools/test_g5_native_probe.py` `ROUTE_HISTORY`），任何路线升级为 feasible 必须有新的实机证据。本轮离线，实机项未验证。

## 2026-11-04 S01 交付：quilt 引用修复与共享测量底座

- F03 的 merge 引用 trim 结果 `ProFeatureGeomitemVisit -4` 两版同码问题，从引用解析层修复：`native/generic.cpp` 的 `quilt_feature` 分支改走 `resolve_quilt_reference`——0 个或多个 `PRO_QUILT` 几何项一律拒绝，错误信息附 ≤20 个有界候选（`quilt_id`/`feature_ids`/`face_count`/`area_mm2`）；不引入自动选取，也不做 `require_single` 宽松模式。
- 显式 `{"kind":"quilt","id":<int>}` 引用经校验后解析（非负 32 位整数、`ProQuiltInit` 探测存在性），失败附候选清单；`resolve()` 中旧的盲选 PRO_QUILT 一行式分支移除。
- `native/surface_measure.h`：quilt 面积（外环−内环轮廓面积和）、曲线长度/端点、`measurement_status_json` 的唯一实现；S02—S07 的原生模块一律复用，不得各自复制测量逻辑。`quilt_area_mm2`/`curve_length_mm`/`curve_endpoints_mm` 语义与 G5 契约 §4.4.2 一致。
- 验证：编译通过、`tests/unit/test_quilt_query_contract.py` 10 项通过、全量 2 286 项单元测试通过；`tools/test_surface_chain.py --case quilts` 离线通过。实机未验证；merge/trim 的实机修复证据仍待 S02/S03 实机阶段。

## 2026-11-04 S02 离线交付：高层 surface_trim

- 契约：`src/creo_mechdog/schema.py::SurfaceTrimOp`（`op="surface_trim"`、`label`、`target`、`tool`、`keep_side ∈ {one,two}`）。target 只接受一个 quilt（`{kind:"quilt",id}` 或 `{kind:"quilt_feature",label}`）；tool 额外接受 `{kind:"datum_plane",label}`；body、曲线（use-curve 变体）、多工具、缺 kind、非整数/负 quilt id、target 与 tool 同一引用均在受理前拒绝，不建 job。
- 原生：`native/surface_trim.cpp::generic_surface_trim`，按 G5 契约 §2.3 的 `ProTrim.h` use-quilt 树（`PRO_FEAT_CUT` + `PRO_USE_SURFS` + 两个 trim type 元素取值一致 + `PRO_E_TRIM_QUILT`/`PRO_E_STD_USEQLT_QLT`），材料侧固定 `PRO_TRIM_MATL_SIDE_ONE`、`PRO_E_KEEP_TRIM_SURF_OPT_NO`，只有 `PRO_E_PRIMARY_QLTSIDE` 跟随 `keep_side`。引用解析与面积测量全部复用 S01（`resolve_quilt_reference`、`quilt_area_native`），不复制测量实现。
- 回执：`area_before_mm2`/`area_after_mm2` 及各自 status、`keep_side`、`kept_side_basis`（`primary_quilt_side_value`/`material_side_value`/`tool_normal`/`target_centroid`/`kept_centroid`/`signed_offset_mm`）、`kept_quilt_id`、`kept_quilt_source`。质心没有可依据的公开 quilt 查询，一律 null 并附 `centroid_status`，不用外框中心估算；`signed_offset_mm` 因此为 null，方向判定与“矛盾即失败”的强制项留待 P3 实机回填。
- 修剪结果归属（计划评审焦点 1）：先枚举结果特征的 `PRO_QUILT` 几何项，恰好 1 个记为 `feature_quilt_geomitem`；0 个按“修改既有 quilt”处理、重新核实 target quilt 并记 `retrimmed_target_quilt`；多个则判歧义失败。面积未减少、结果不可测量、特征未再生成功都按失败处理并回滚，不以构树返回 0 判成功。
- 接线：`generic.cpp` 单点 `#include "surface_trim.cpp"` 与 `execute_operation_body` 分发；`server.py` 注册 `creo_surface_trim`（写入 `_SOURCE_NAMES` 的 `surface_trim.cpp`/`quilt_query.h`/`surface_measure.h`）；`surface_trim` 列入 `creo_mechdog/capabilities.py::UNAVAILABLE_OPERATIONS`，`server.py` 的既有钩子把 `creo_surface_trim` 从 MCP 工具面移除，`require_available` 在提交前拒绝并说明原因。
- 驱动：`tools/test_surface_chain.py --case trim`（默认离线，校验契约、门禁与原生接线）；`--case trim --live` 先用 `creo_capabilities` 确认算子是否公开，未公开时如实记 `native_surface_trim="gated"` 并不提交几何；公开后按两个独立模型分别 `keep_side=one/two` 实测面积 400 mm²（±0.5）与 x 覆盖区间，不跨模型比较 quilt id。
- 验证：`bridge.py build` 编译通过；`tests/unit/test_surface_trim_schema.py` 20 项通过；`tests.unit.test_surface_trim_schema + test_quilt_query_contract + test_g5_native_contract` 49 项通过；全量 2 316 项单测通过；`tools/dev_check.py --skip-unit` 无新增风格回归（同时按项目格式器整理了 S01 的 `quilt_query.h`/`surface_measure.h` 与两个契约测试的行尾与格式）。
- **未验证**：`keep_side` 与工具法向的绑定（P3）、真实修剪面积/位置、保存重载后同一引用仍可被 `thicken` 消费、`ProFeatureGeomitemVisit -4` 在处理后的引用链上是否消失、失败回滚的实机表现。工具在取得这些证据前保持 gated，不登记为可用能力。

## 2026-11-04 S03 离线交付：quilt_merge（两面 join）

- 契约：`schema.py::QuiltMergeOp`（`op="quilt_merge"`、`label`、`target`、`tool`）。两侧都必须是显式 quilt 引用且互不相同；基准面、曲线、body、缺 kind、`tolerance` 等未知字段在受理前拒绝。`boolean_bodies` 不作为缝合替代。
- 原生：`native/quilt_merge.cpp::generic_quilt_merge`，按 `ProMerge.h` 文档化的当前（数组）树构建：`PRO_E_FEATURE_TYPE=PRO_FEAT_DATUM_QUILT`、`PRO_E_SRF_MRG_TYPE=PRO_SRF_MRG_JOIN`（**显式写 join，因为 SDK 默认是 INTERSECT**）、`PRO_E_SRF_MRG_QUILT_ARR` 两个成员经 `ProElementArraySet` 写入，每个成员 `PRO_E_SRF_MRG_QUILT_REF` 走 S01 解析。`PRO_E_SRF_MRG_QUILT_SIDE` 是 optional，首版不设置，保留区域靠实测而不靠假设。
- 回执：`result_quilt_id`、`area_mm2`/`area_status`、`input_area_mm2`/`input_area_status`（合并前两个输入之和）、`closed`/`closed_status`（只来自 `ProQuiltVolumeEval`，开放报 `false`、探测失败报 `null`）、`merge_type="join"`、`inputs`。不提供容差与间隙测量。
- 共享 helper 收敛：闭包探测从 `quilt_query.h` 下沉为 `surface_measure.h::quilt_closed_native`，quilt 选择 ID 收敛为 `quilt_query.h::quilt_selection_id`，面积字段拼装收敛为 `surface_measure.h::area_fields_json`；trim/merge/查询三处消费同一实现。
- 接线：`generic.cpp` 单点 include 与分发；`server.py` 注册 `creo_quilt_merge` 并纳入 `_SOURCE_NAMES`；`quilt_merge` 列入 `UNAVAILABLE_OPERATIONS`（工具从 MCP 面移除、提交前拒绝）。
- 驱动：`--case merge`（离线校验契约/门禁/树与 join 显式写入）；`--case merge --live` 先用 `creo_capabilities` 判公开，未公开记 `gated` 不提交几何；公开后两个相邻 20×20 共面 fill 合并，校验面积 800 mm²（±0.5）、`result_quilt_id` 非空、开放 quilt 报 `closed=false`。立方体闭合用例尚未实现（等实机窗口）。
- 验证：`bridge.py build` 编译通过；`tests/unit/test_quilt_merge_schema.py` 18 项通过；S02+S03+S01+G5 四条契约共 63 项通过；`tools/test_surface_chain.py --case merge/trim/quilts` 三条离线用例 passed。
- **未验证**：实机 join 再生、合并面积/位置、结果 quilt 引用在保存重载后仍可被 `thicken` 消费、闭合用例、空白间隙与不连续边界的失败行为。工具继续保持 gated。

## 2026-11-04 S02 P3 实机交付：keep_side 绑定与门禁解除

环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK；单会话串行窗口；`bridge.py build` 后执行。

- **绑定结论（实测）**：`keep_side="one"` 保留**工具法向正侧**，`"two"` 保留负侧。判据是两次独立模型的面积 + 保留 quilt 外框，不跨模型比 ID（契约 R5）。
- **几何与读数**：40×20 平面填充（800 mm²）被 x=5 基准面（RIGHT，法向 +X）修剪 → `one` 700 mm²、外框 x∈[5,40]；`two` 100 mm²、外框 x∈[0,5]。圆柱曲面（1256.64 mm²）被 z=5 平面（法向 +Z）修剪 → `one` 314.16 mm²（z>5）、`two` 942.48 mm²（z<5）。两次运行 `kept_quilt_id` 均为目标 quilt（`kept_quilt_source="retrimmed_target_quilt_visit_failed"`、访问码 `-4`），`closed=false`（开放 quilt，符合预期），`saved_file_reloaded_and_verified=true`。
- **缺陷 1（keep_side 无效，已修）**：原实现只让 `PRO_E_PRIMARY_QLTSIDE` 跟随 `keep_side`，`PRO_E_MATERIAL_SIDE` 固定 ONE。实机对比：`one`/`two` 在非对称切削下得到**同一侧同一面积**（700/700、314.16/314.16），证明确实没有翻转。现两个元素同时跟随 `keep_side`，重跑后为 700/100 与 314.16/942.48。
- **缺陷 2（基准面引用丢 label，已修）**：`{kind:'datum_plane',label:'RIGHT'}` 被 `resolve()` 的几何分支接受但丢弃 label，默认轴过滤（axis z、offset 0）选中 TOP，修剪平面落到别处并停在 `PRO_FEAT_UNREGENERATED`（status 6）。`references.py::validate_datum_plane_reference_kind` 现在拒绝几何类 kind（`datum_plane`/`plane`/`surface`）上的 label，指引用 `{kind:'datum_feature',label:...}`；原生 `resolve()` 有同语义 backstop；`tools/test_surface_chain.py` 驱动改用 `{kind:'datum_plane',axis:'x',offset:0}`。
- **修剪失败可诊断**：再生失败分支现在把 `regeneration`（`failed_stage`、`feature_id`、`feature_status`、`target_quilt_id`、`tool_kind`、`primary_quilt_side_value`、`material_side_value`、结果特征 quilt 访问码与 id 列表）与已测得的面积字段一起暂存，失败消息带同一组数值。此前失败只给一句提示、无可查数值。
- **门禁**：`surface_trim` 已从 `UNAVAILABLE_OPERATIONS` 移除（`creo_surface_trim` 重新出现在 MCP 工具面）；`quilt_merge` 仍在门禁内。
- **证据**：`build/live_trim_report.json`（驱动 `build/_live_trim.py`，非对称几何 + 期望面积断言）；`build/surface_chain/20261104-094447-635200/report.json`（`--case trim --live --confirm-session-usable`，`native_surface_trim="verified"`，jobs `247f76de…`、`7ae993e6…`）；诊断矩阵 `build/live_trim_probe.json`（10 个配置：平面/曲面目标 × 基准面/quilt 工具 × 偏移）。
- **验证**：`bridge.py build` 通过；`test_surface_trim_schema.py` 20 项、`test_datum_plane_contract.py` 18 项通过；`tools/test_surface_chain.py --case trim`（离线）与 `--case trim --live`（实机）均 passed。
- **仍未验证**：修剪结果在保存重载后被 `thicken` 消费、质心判据（本机无 quilt 质心查询，`signed_offset_mm` 仍为 null）、失败回滚的实机表现、`PRO_E_PRIMARY_QLTSIDE` 在薄修剪/双侧变体下的语义。

## 2026-11-04 S03 实机：join 三条路线均未产出结果 quilt（保持门禁）

环境同上（Creo 12.4.0.0，单会话串行）。驱动 `tools/test_surface_chain.py --case merge --live` 现含三个模型：两张共边的 20×20 面 join、圆柱筒 + 上下盖两次 join 后 `solidify`、以及 2 mm 间隙负例。

**实测结果（job `86fd9e55…`、`c2d95902…`）**：join 特征的 `feature_status=0`（`PRO_FEAT_ACTIVE`），但 `ProFeatureGeomitemVisit(PRO_QUILT)` 返回 **-4** 且 0 个 quilt；改为访问 `PRO_SURFACE` 返回 0 且**恰好 4 个** surface 项（`132/134/136/138`，type=5）。合并后模型 quilt 列表为空，两张输入 quilt（91、127）被消耗。输入面积 800 mm² 可测，结果面积/闭合不可测，故 op 按设计失败，工具保持 gated。

**已排除的路线**：

1. 文档数组树（`PRO_E_SRF_MRG_QUILT_ARR` + CMPD/REF），默认 side → ACTIVE、4 surface、0 quilt。
2. 同一棵树显式写 `PRO_E_SRF_MRG_QUILT_SIDE=PRO_SRF_MRG_QLT_SIDE_1` → 结果完全相同。
3. 文档 legacy 平面树（`PRO_E_SRF_MRG_PRNT_QLT` / `PRO_E_SRF_MRG_ADTL_QLT`）→ `ProFeatureWithoptionsCreate` 返回 **-1**，Creo 12 已不接受该树。
4. 强制 `ProSolidRegenerate(PRO_REGEN_FORCE_REGEN)` 后再访问 → 仍是 ACTIVE、4 surface、0 quilt。

**诊断保留**：`quilt_merge` 的 details 现在固定回写 `merge_tree`、`feature_status`、`feature_id`、`quilt_item_ids`、`surface_item_ids`、`surface_visit_code`、`result_quilt_visit_code`，失败时随已测得的 `input_area_mm2` 一起发布，便于下一步定位。

**下一步候选**（按成本排序）：① 用 `ProFeatureRedefine` 重建特征后复查 quilt 归属；② 先用 `ProSurfaceMergeElementsGet` 之类读取一个手工建立的 merge 特征树（需在 Creo 界面手工建一次）作为参照树；③ 改用 `ProQuiltInit` 遍历合并后模型，确认 quilt 是否以别的 id 空间存在；④ 若确认 API 不可用，S03 按"能力未实现"结项，join 需求改走 `solidify` + 布尔路线。

补充（2026-11-04 同日）：交叉合并同步复测——把类型改成 `PRO_SRF_MRG_INTSCT`、并把第二张面移到真正相交的位置（`cross` 用例）后，结果仍是 **ACTIVE + 0 quilt**，与 JOIN 一致。四条路线加这次交叉复测都不产 quilt，`quilt_merge` 继续 gated，门禁消息已按实测更新。

## 2026-11-04 S04 实机交付：project_curve 走扫掠面 + 交线（已公开）

**两族投影元素都不可用（实测）**：`PRO_E_COPYTRIM_*` 与 `PRO_E_PROJ_CRV_*` 在本机 SDK 中只出现在 `ProElemId.h`，无父子关系、合法值或必需兄弟节点说明；`ProCurveType` 也没有"投影"类型值。用已注册的 `feature_tree` 逐条提交候选树（不重新编译，结论由内核给出）：

- COPYTRIM 三个布局（`_CURVE_DATA`+`_CURVE_TBL`、平铺 `_QUILT`+`_CURVE`、`_CURVES` 数组）→ 全部 `ProFeatureWithoptionsCreate = -1`；
- PROJECT 四个布局（`_SURFS`+`_DIR`+`PROJ_TYPE=ALONGDIR`、`_ONESRF_REF`、追加 `PRO_E_CRV_PROJCRV_TYPE`、`PROJ_TYPE=NORM2SRF`）→ 同样全部 -1；
- 引用本身可解析（单独提交 quilt / curve / datum_feature 引用都进入创建阶段），所以被拒的是树形而不是引用。

**交付路线**（文档化的两步，不是冒充）：扫掠辅助面（`ProExtrude.h`：`PRO_FEAT_DATUM_SURF` + `PRO_EXTRUDE` + surface 模式 + `PRO_E_SEC_USE_SKETCH` 指向源草图 + 对称盲深）∩ 目标 quilt（`ProDtmCrv.h` INTERSECT，`PRO_E_CRV_IP_REF_TYPE` 与 `PRO_E_CURVE_TYPE` 同取 `PRO_CURVE_TYPE_INTSRF`）。扫掠面由源曲线本身沿方向平移生成，交线逐点等于投影。细节与树形见 [G5 契约 §2.2](../development/G5-NATIVE-CONTRACT.md)。

**实测（Creo 12.4.0.0，单会话串行；`build/_live_project_probe2.py`）**：

| 用例 | 结果 |
| --- | --- |
| 源直线 (5,10,10)→(35,10,10)，方向 −Z，目标 z=0 的 40×20 填充 | 长度 **30.000 mm**，端点 **(5,10,0)/(35,10,0)**，`curve_id` 为真实几何项，`saved_file_reloaded_and_verified=true` |
| 源圆弧 半径 8、圆心 (20,10,10)、0°→180° | 长度 **25.133 mm**（π·8），端点 **(12,10,0)/(28,10,0)** |
| 同一模型 `side="positive"`（+Z，目标在背侧） | 按预期拒绝：`project_curve target quilt lies behind the source curve for side 'positive'` |

**实现要点**：交线特征会同时产出曲线与其复合包络（实测 2 个 `PRO_CURVE` 项），只报非复合曲线；出现两条及以上非复合曲线判为多分支并拒绝。直线源的辅助面有 8 个面、圆弧源被拆成 5 张柱面，扫掠面按"法向与方向平行的平面是端盖、其余面都属于扫掠面"筛选，多面时用 `PRO_CURVE_TYPE_MULTIPLE_SEL` 一次全部作为 REF1。辅助面保留在模型中（删它会连带删掉交线），其 id 以 `helper_feature_id` 返回。

**同批修复的真实缺陷**：① `curve_endpoints_native` 对复合曲线传导数数组，`ProCurveXyzdataEval` 返回 `PRO_TK_NOT_IMPLEMENTED`，改为传 NULL（端点读数已由解析端点验证）；② `feature_geometry` 的自动合并列表不含交线特征的 `PRO_CURVE` 项，补 `PRO_CURVE` 类型访问并按 id 去重合并，客户端因此能再次引用投影曲线。

**验证**：`bridge.py build` 通过；`tests/unit/test_project_curve_schema.py` 22 项通过；`tools/test_surface_chain.py --case project`（离线）通过。

**统一驱动实机通过**（重启 Creo 会话后）：`tools/test_surface_chain.py --case project --live --confirm-session-usable`，run `20261104-134443-396700`，6 个作业、18 项检查全通过——直线 30.000 mm、圆弧 25.1327 mm、端点均精确到 1e-6、两次 `saved_file_reloaded_and_verified`、`route=swept_surface_intersect`/`helper_feature_id=95`/`direction_basis=datum_plane_normal`、反向拒绝。驱动同时修了两处自身缺陷：`wait_ready` 首次轮询只请求一次 retry（否则每轮都重开协调器尝试、旧状态停在 active 相位永不结束），提交改用作业回报的 revision 而不是另发只读刷新作业占住 `pending_job`。

**未验证/剩余**：多分支拒绝、非平面（圆柱）目标与边界裁切、方向与草图法向不平行的拒绝只在实现内存在，未在实机触发。

## 2026-11-04 S04 消费者：surface_trim 加入 Use Curve 变体（已公开）

`ProTrim.h` §(3.1)/(3.2) 的 "Use Curve" 树与 "Use Quilt" 是两套元素：没有 `PRO_E_FEATURE_FORM`、没有 `PRO_E_KEEP_TRIM_SURF_OPT`，修剪几何来自 `PRO_E_STD_CURVE_COLLECTION_APPL`（`PRO_CURVE`/`PRO_COMP_CRV`/curve_chain），两个类型元素取 `PRO_SURF_TRIM_USE_CRV`。实机矩阵（10 个模型，`build/_live_usecurve_trim_probe.py`）：

- `PRO_E_MATERIAL_SIDE` 决定保留侧：1/2 各保留一侧（200 / 600 mm²），3 表示两侧都保留（两个 quilt）；`PRO_E_PRIMARY_QLTSIDE`（1/2/-1）实测不改变结果。
- 保留侧相对**曲线方向**：同一材质侧下把直线反向，保留区域随之交换。因此 `kept_side_basis` 报告 `side_reference="curve_direction"`、`tool_curve_id`、`tool_kind="curve"`，不报 `tool_normal`。
- 用内核的 `feature_tree` 通道逐条提交这棵树可被接受，属于文档化路线而非猜测。

操作符验证（`build/_live_op_trim_probe.py` 的 `flat` 形态）：z=0 草图直线经公开 `surface_trim` 修剪同平面填充，面积 800→600，`saved_file_reloaded_and_verified=true`。实现中修正一处真实缺陷：use-curve 特征创建后立即读状态为 `PRO_FEAT_FAILED(6)`（集合在再生时才解析），必须先 `ProSolidRegenerate` 再判状态；use-quilt 变体创建后已是 ACTIVE。

**已知边界（实测，未绕过）**：先投影到某 quilt、再用该投影曲线修剪同一 quilt 的链在保存阶段失败——`ProMdlnameBackup=-1`，作业回滚、目标保持未修剪（同模型里的投影作业本身可保存）。该投影曲线是交线特征，持有被修剪 quilt 的几何项选择；修剪消费掉该 quilt 后曲线参考悬空，内核拒绝写出模型。所以"独立曲线修剪"可用，"曲线依赖目标 quilt"会在保存阶段失败并明确报错，不会被当成成功。

**消费者剩余**：跨面曲线链、投影曲线对非本 quilt 的修剪、两侧同时保留（`BOTH`）都未公开；投影—修剪同一 quilt 的串联要等真实投影特征或多分支交线之外的路线。

## 2026-11-04 S06 实机交付：闭合曲面实体化的体积与闭合判据

`solidify` 的原生树早就在（`PRO_FEAT_PROTRUSION` + `PRO_USE_SURFS` + `PRO_E_PATCH_QUILT` + 材质侧），缺的是**判据**：以前只建特征，不报体积，也不管闭合性。

- **闭合是量出来的**：`quilt_closed_native()` 用 `ProQuiltVolumeEval` 问闭合性，开放 quilt 返回 `PRO_TK_INVALID_TYPE(-18)`。开放 quilt 在建特征**之前**被拒绝，消息带该码（`solidify requires a closed quilt; the referenced quilt is open (ProQuiltVolumeEval=-18, quilt_is_open)`），作业失败并回滚，不留半个实体。`cut` 与 `thicken` 不受此限制（开放面加厚合法）。
- **体积是量出来的**：`volume_before_mm3` / `volume_after_mm3` 走共享质量属性 helper，没有实体时为 `null`（不是 0），随算子结果返回。
- **schema 收紧**：`solidify` 的 `mode="add"` 只接受一个 quilt 引用；body 不是 quilt，布尔 body 工具不能替代 quilt 语义。

实机（绕 X 轴 360° 旋转 5×20 矩形）：闭合 quilt 面积 1000π mm²，实体化体积 **6283.185307179587 mm³**（解析 2000π，差 <1e-9），`saved_file_reloaded_and_verified=true`；开放 quilt（40×20 填充面）按上述理由拒绝，模型保持 800 mm² 开放面。驱动 `--case solidify --live`（run `20261104-145403-398500`）8 项检查全通过。解析期望值由实测外框推导，不写死常数。

**闭合 quilt 的来源**：用 360° 旋转曲面得到，**不依赖仍 gated 的 `quilt_merge`**。这也给出 S03 之外的一条闭合面路径。

**未验证**：thicken 的体积字段未实机核对；`cut` 模式的体积字段未核对；闭合判据只覆盖 `mode="add"`。

## 2026-11-04 S07 取证：偏置的文档树存在，但实测不生效（保持门禁）

本机 SDK 与偏置有关的文档只有 `ProTrim.h` 的 thin trim（修剪面先按 `PRO_E_THICKNESS` 沿
`PRO_E_STD_USEQLT_SIDE` 偏置再切）与 `ProThicken.h` 的加厚偏移参数；**没有**独立的偏置曲面/偏置 quilt
特征树（`ProQuilt.h` 只有查询 API，`PRO_E_SRF_OFFS_*` 只作为 thicken/trim 的子元素出现）。

实机（`build/_live_offset_probe.py`）：40×20 填充 + x=20 基准面与竖直 quilt 工具，请求 `offset_mm=5`：

- 基准面工具：作业成功，但保留面积仍是 **400/400**（切口没有移到 x=15/x=25）；
- quilt 工具：同样 400/400，两个偏置方向的保留区不互换；
- `offset_mm=50`（必定不相交）：作业成功且**没有拒绝**，切口仍在 x=20。

即：偏置元素被内核接受却不产生可测量的偏置，公开距离等于骗人。因此 `surface_trim` 的
`offset_mm`/`offset_side` 字段保留在 schema（请求良构），但由 `capabilities.require_available`
在排队前拒绝，消息带实测依据。偏置能力维持门禁，等能真正移动切口的路线（真实偏置曲面树，
或按法向扫掠构造等距面——与 S04 的扫掠思路同源）。

## 2026-11-06 偏置新规格复测：Thin 树生效，但语义是带移除且方向不可控（仍门禁）

S07 的失败原因是偏置元素挂在了 Use Quilt 树（两个 type 元素仍是 `PRO_SURF_TRIM_USE_QLT`）。
`ProTrim.h` §(4.1)/(4.2) 规定 `PRO_E_THICKNESS`/`PRO_E_STD_USEQLT_SIDE`/`PRO_E_SRF_OFFS_METHOD`
属于 **Thin** 变体，两个 type 元素必须是 `PRO_SURF_TRIM_THIN`。本轮用低层
`creo_create_feature_tree` 直接构 Thin 树复测（不改公开入口），40×20 填充 + x=`tool_x` 的竖直
YZ quilt/基准面，按 quilt 面积判读（驱动 `build/_live_thin_trim_probe2.py`，证据
`build/live_thin_trim_probe2.json`）：

| 工具 | 厚度 | side | 目标面积 | 工具 quilt 盒 |
| --- | --- | --- | --- | --- |
| use-quilt 对照（x=20） | — | one | 400/400 | — |
| 基准面 | 5 | one | 400/400（厚度被忽略） | — |
| quilt x=2 | 5 | one/two/both | **760** | x∈[-3, 2] |
| quilt x=20 | 5 | one/two/both | **700** | x∈[15, 20] |
| quilt x=20 | 10 | one | **600** | x∈[10, 20] |
| quilt x=20 | -5 | one | 再生成失败 | — |

结论：`offset_mm` 只对 **quilt 工具**生效，几何是**移除一条厚度带、带两侧都保留**，不是"切口整体
移动"，也与公开契约的 `keep_side`（保留 one/two 一侧）冲突；`offset_side` 无法兑现
（`PRO_E_STD_USEQLT_SIDE` one/two/both、附加 material/primary side、`PRO_E_SRF_OFFS_DIRECTION`
六种写法结果完全相同，方向由工具 quilt 自身朝向决定；负厚度再生成失败）。因此两字段继续保持
`capabilities.require_available` 门禁，schema 不变。

原生树已按文档修正：`native/surface_trim.cpp` 在 `offset_mm` 存在时把两个 type 元素切换为
`PRO_SURF_TRIM_THIN`，并不写 Thin 树不存在的 `PRO_E_MATERIAL_SIDE`/`PRO_E_PRIMARY_QLTSIDE`。
该分支目前不可达（Python 门禁先拒绝），只为后续开放时不误用旧树。

## 2026-11-05 S08 交付：两条完整曲面链用例（实机）

驱动新增 `--case chain_open` 与 `--case chain_closed`（`tools/surface_chain_chains.py`、
`tools/surface_chain_closed.py`），每条链的期望都是**解析 oracle**，每个作业都必须
`saved_file_reloaded_and_verified=true`。

**开放链**（run `20261105-042923-088700`，14 项全通过）：填充 40×20 → 投影 z=10 的源线
→ 实测投影曲线 **40.000 mm**（源线 50 mm，投影被目标面裁到 40 mm）→ 用同平面的独立直线
做 use-curve 修剪 → 保留面积 **600.000 mm²**（40×15）→ 查询确认保留 quilt 仍为开放面 →
对称加厚 2 mm → 体积 **1200.000 mm³**（面积×厚度）→ 陈旧 revision 被拒
（`Stale revision: current model revision is 4`）。

**闭合链**（run `20261105-043026-636000`，12 项全通过）：绕轴 360° 旋转得到闭合 quilt
（面积 **3141.592653589793 mm²** = 1000π，oracle 由实测外框推导）→ 实体化体积
**6283.185307179587 mm³** = 2000π → 改写轮廓（5×20 → 5×30）后重新生成，曲面面积变为
6597.344572538569 mm² → 失败作业（引用不存在的 quilt）整批回滚，几何保持不变，
失败消息带真实诊断（列出已知 quilt）。

**未覆盖并已如实标注**：开放链的放样步骤（曲面放样仍 gated）、闭合链的"逐步缝合"
（`quilt_merge` 仍 gated，闭合面改用旋转曲面得到）。

## 2026-11-05 W01 第二步实测：草图 epsilon 不是端点重合容差（维持门禁）

原生侧试过唯一的"受控焊接"杠杆——草图求解的 `ProSectionEpsilonSet`。实测结论：

- 把 epsilon 从默认 1e-4 提到 **2e-3 mm**（请求 `max_endpoint_move_mm=1e-3`）后，
  一个 **5e-4 mm** 的端点间隙**仍然张开**（求解后 `geometry_deviation.max_deviation_mm`
  仍是 4.9999e-4 mm）；
- 同一个模型在**默认路径**下，**8.2e-7 mm** 的间隙会被内核自己合上（偏差为 0），
  与 BUG-101 当日观察一致。

即：epsilon 不是重合容差，内核自己有一套未文档化的端点合并阈值，**受控焊接无法通过
文档化的 SDK 面实现**。因此：

- 原生侧保留诊断（结果里的 `endpoint_weld_native`：本次用的 epsilon、是否请求了焊接），
  但不再改 epsilon；
- `endpoint_policy="weld"` 继续被拒绝，理由改为带实测数据（原文见能力门禁）；
- 策略层的候选尺度回到闭合诊断的 1e-4 mm：单靠"请求最大移动量"放宽候选会承诺内核做不到的事；
- 回执不再被 Python 侧覆盖：原生块并入 `endpoint_weld.native`，`applied`/`max_residual_mm`
  在内核没有查询接口前保持 `null` 并附原因。

**W01 仍开放的部分**：原生重合求解、焊接后几何读回与残差、原案 gear10 体积基准、
以及"原默认调用路径"是否达标——目前只知道默认路径会自己合上 ≤1e-4 量级的间隙，
这不等于受控焊接可用。

## 2026-11-05 S03：join 需求的可测量并集（替代路线，实机通过）

`quilt_merge` 算子仍 gated（四条原生路线 + 交叉复测：ACTIVE 特征、4 个 `PRO_SURFACE`、0 quilt），
但计划允许的替代路线（solidify/加厚 + 布尔）已经能给出**可测量的并集**，驱动新增
`--case join`（`tools/surface_chain_join.py`），实机 13 项检查全通过（连续三次复跑稳定）：

| 步骤 | 实测 |
| --- | --- |
| 两张 40×20 填充面重叠 10×20 | A: x∈[0,40]、B: x∈[30,70] |
| 用共享边所在基准面（x=40）修剪 B | 保留 **600.000 mm²**（外侧部分），重叠部分 200 mm² |
| 并集面积 | 800 + 600 = **1400 mm²**（= 800 + 800 − 200） |
| 加厚 2 mm（symmetric） | 第一个实体 **1600.000 mm³**，合并后 **2799.9999999999995 mm³**（= 1400×2） |
| 实体数量 | 1 个 body（两个加厚合入同一 body），`saved_file_reloaded_and_verified=true` |

重叠只算一次这件事由体积证明：两个实体简单相加是 3200 mm³，合并后是 2800 mm³。

**边界**：两张共面 quilt 互剪是退化工具（实机失败），因此重叠量用共享边所在基准面量；
合并后得到的是**一个实体**而不是**单一 quilt**，后者仍需 Merge 特征的真实元素树。

**同时修掉的驱动缺陷**：作业轮询改用 `detail=compact`，并在终态后取一次完整视图——
体量大的作业用完整视图会被拒（`Query metadata exceeds response budget`），
而紧凑视图带状态但不带测量值，两者都要才读得到数。

## 2026-11-05 曲面链示例文件：可运行的分阶段计划

计划里点名的 `examples/p12_surface_blade.json` 与 `examples/surface_trim_merge.json` 已补齐，
并让统一驱动能真正跑它们：`tools/test_surface_chain.py --example <file>`。

示例是**分阶段**的（一个阶段一次作业、同一模型继续），id 用占位符声明
（`$curve:<特征名>`、`$quilt:<特征名>`、`$body:<特征名>`），运行前按检查结果解析，
所以示例不写死会话 id、可重放。离线条断言 schema 通过且没有用到被门禁的算子。

实机：`p12_surface_blade.json` 三阶段全通过（修剪面积 800 → **600.000 mm²**，加厚 committed，
保存重载通过）；`surface_trim_merge.json` 同样三阶段全通过（修剪 800 → 600 mm² = 并集的外侧部分，
加厚 committed）。测试见 `tests/unit/test_surface_examples.py`。

## 2026-11-05 S05 落地：文档化的曲面扫掠（实机 11 项通过）

子任务勘察 SDK 头文件后的结论：`ProSweep.h` 里有**完整的父子文档**
（`PRO_E_EXT_SURF_CUT_SOLID_TYPE` = `PRO_SWEEP_FEAT_TYPE_SURFACE`，
`PRO_E_END_SRF_ATTR` 决定端盖），而 `sweep` 算子本来就已经实现了 surface 模式——
S05 缺的不是能力，是**证据**。

实机（run `20261105-073051-135500`，11 项全通过）：40×20 矩形沿 20 mm 直线扫掠，

- 开放曲面：面积 **2400.000 mm²**、未闭合（oracle：2×(40+20)×20 = 2400）；
- 加盖曲面：面积 **4000.000 mm²**、闭合（oracle：2400 + 2×40×20 = 4000）；
- 加盖曲面实体化：体积 **15999.999999999998 mm³**（oracle：40×20×20 = 16000）。

用例在 `--case sweep_surface`，三个 oracle 全部由几何参数推导；作业均要求
`saved_file_reloaded_and_verified=true`。契约测试 `tests/unit/test_surface_sweep_contract.py`。

**仍未达成**：多截面放样/边界混合。`ProSweep.h` 文档明确只支持常量截面
（`PRO_SWEEP_CONST_SECTION`），本机也没有 `ProBlend.h`，所以 `loft` 的 `mode="surface"`
仍按 §2.8b 的实测理由在排队前被拒，用例里标为 blocked step。

## 2026-11-05 W01 本体交付：受控端点焊接（实机）

子任务勘察确认：内核**没有任何位移上限 API**，所以显式点重合约束无法"受控"；可行且能保证上限的
只有**坐标规整**——先按请求上限把端点坐标对齐，再让内核求解。

实现：策略层（`creo_mechdog.endpoint_welding`）决定配对并把 `weld_pairs` 交给原生侧；
原生侧（`native/endpoint_weld.h`）在写入实体前把每对端点各移动 gap/2，超过上限的对**拒绝应用**
并记录原因；求解后从 section 回读两端点距离作为残差。创建与编辑两条路径同一套实现。

实机（闭合矩形，间隙 5e-5 mm）：焊策略 `applied=true`、`applied_pairs=1`、
`move_mm=2.4999999999941735e-05`（≤ 上限 1e-4）、**`max_residual_mm=0.0`**、`saved_file_reloaded_and_verified=true`；
同一轮廓默认路径 `applied=false`、间隙保持。没有 `max_endpoint_move_mm` 的请求在排队前被拒。

**边界**：只处理直线端点（弧端点按"unsupported_entity_or_point"跳过并记录）；配对规则
（唯一性、不跨环、同圆）仍在策略层；内核自身的合并阈值（≤1e-6 量级）不受本能力影响。

## 2026-11-05 参照树任务：读取链路产品化 + Direct Blend 实测判决

新增 `tools/read_reference_tree.py`：adopt（inspect → apply）→ inspect features → dump_tree，
内核拒绝的特征也按原样记录（这是证据，不是猜测）。

对种子放样参照件实测：9 个特征树读回成功（基准面、坐标系、两条 `PRO_FEAT_CURVE` 的
`LOFT_BOTTOM`/`LOFT_TOP`，其截面里带 `PRO_E_STD_SEC_BLN_VERTS` = 混合顶点的选择）；
**Direct Blend 本体（id 60）的元素树抽取返回 -18**。

因此："用元素树实现混合"这条路被实测关闭，`loft` 的 surface 模式与 `quilt_merge` 的门禁
都改为引用这条判决。种子库清点后确认**没有 Merge/Offset 参照件**，S03/S07 仍需手工件；
拿到之后上面这个工具一次就能读回元素树。

## 2026-11-05 参照树（自有特征）：偏置与合并元素的真实父子关系

参照树不必来自外部件：**从本服务自己能建出的特征上读回**即可。读回结果见
[REFERENCE-TREES](../development/REFERENCE-TREES.md)。

- **偏置（S07）**：`PRO_E_SRF_OFFS_METHOD`（=1）、`PRO_E_SRF_OFFS_CTRLFIT`（compound，内含
  `PRO_E_SRF_OFFS_SCALINGCSYS`）、`PRO_E_SRF_OFFS_AXES`、`PRO_E_SRF_OFFS_HANDLINGS`（数组）
  挂在**加厚/凸台特征树**下——此前 12 个候选挂在 `PRO_FEAT_DATUM_SURF`/`PRO_FEAT_OFFSET` 下被拒，
  根因是挂载位置错了。
- **合并（S03）**：`PRO_E_SMT_MERGE_DATA`（compound，含 `PRO_E_SMT_MERGE_AUTO`、
  `PRO_E_SMT_MERGE_KEEP_LINES`、`PRO_E_SMT_MERGE_KEEP_BEND_EDGES`）、
  `PRO_E_SWP_MERGE_ENDS`、`PRO_E_TRIM_QUILT` 出现在**曲面特征树**里——本机似乎没有独立的
  "合并面"特征，合并语义落在曲面特征的元素上。
- **混合（S05）**：Direct Blend 的元素树抽取返回 -18，无树可依（面板路线唯一）。

## 2026-11-05 S07 规格确定：偏置走 `ProThicken.h` 的法向偏移

`ProThicken.h` 把偏移的规格写全了：`PRO_E_FEATURE_FORM=PRO_USE_SURFS`、
`PRO_E_FEAT_FORM_ALWAYS_THIN=PRO_THIN`、`PRO_E_STD_USEQLT_QLT`（quilt）、`PRO_E_THICKNESS`、
`PRO_E_SRF_OFFS_METHOD`（法向到曲面 / 自动缩放 / 手动缩放）、方向 `PRO_E_STD_USEQLT_SIDE`、
逐面处理 `PRO_E_SRF_OFFS_HANDLING`。自建 `PAD` 树与规格逐项吻合，**此前 12 个候选被拒是因为
挂错了父节点**。实现规格因此确定：加厚凸台 + 法向偏移 + 显式方向，oracle = 面积 × 距离。

S03 侧：合并元素属钣金族语义，本机没有独立的"合并面"特征树，算子继续门禁。

## 2026-11-05 S07 实现：受控曲面偏置算子 `surface_offset`

按 `ProThicken.h` 的规格实现了公开算子 `creo_surface_offset`（quilt + 距离 + 方向），
原生侧用法向偏移方法（`PRO_OFFS_METH_NORMTOSURF`）、薄壁形式与显式方向；回执里的
`measured_offset_distance_mm` 由"建特征后体积 ÷ 源 quilt 面积"实测得到，不是回显。

**未完成**：实机验收（会话未连接时提交）。oracle 已定：40×20 的 quilt 偏置 5 mm →
体积 4000 mm³、实测距离 5.000 mm、方向 positive。S03 侧维持门禁（合并元素属钣金族，
本机无独立合并面特征树）。

## 2026-11-05 W05 交付：`extrude_depth` 回执（requested/effective 分离）

**目的**：拉伸结果此前看不出"调用方到底给了多少"。省略 depth / depth_type 会被
Pydantic 默认值吞掉，回执只能复述 1 mm / blind，`through_all` 更是无从判断。

**实现**

- `schema.py::ExtrudeOp` 保留 `depth=1`、`depth_type="blind"` 默认（既有归一化契约不变），
  新增 `dump_plan_operations()`：`creo_execute_plan` 按 `model_fields_set` 丢弃调用方
  未设置的 depth/depth_type，`validate_operations` 因此仍能识别省略并在归一化输出写
  `defaulted_fields`。计划文档原定的"默认值下沉到内核"会让既有 `test_t01` 归一化契约
  断言失效，故改用入口 dump 保留省略——效果相同，边界更小。
- `server.py::creo_extrude`：`depth` / `depth_type` 改为可省略，仅在显式给出时写入 op；
  docstring 说明省略按 blind / 1 mm 执行、回执会标 `defaulted_fields`。
- `native/generic.cpp::extrude_depth_report`：`requested_*` 按 `defaulted_fields` 置 null；
  `effective_*` 从创建后特征树实读
  `PRO_E_STD_EXT_DEPTH → PRO_E_EXT_DEPTH_TO → PRO_E_EXT_DEPTH_TO_TYPE / _VALUE`；
  `through_all` 的 `effective_depth_mm` 恒为 null（不回填 1）；树读失败保留 `query_code`，
  `source="unknown"`，两个 effective 保持 null，不伪造。
- `operation_results.normalize_extrude_depth` / `annotate_extrude_depth`：7 键冻结，null 保留，
  未知键与非法值丢弃，无块不补造；`bridge.py` compact 操作白名单加入 `extrude_depth`。
- 单测 `tests/unit/test_extrude_depth_receipt.py` 14 项（省略捕获、plan 入口 dump 往返、
  through_all 不伪造、归一化、工具 schema `default is None`）。
- 契约测试辅助 `_enum_consts` 支持可空参数在 `anyOf` 中的 `enum`（`creo_extrude` 的
  `depth_type` 现在是 `Literal[...] | None`）。

**实机（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK，单会话串行）**

`tools/test_t05_native.py --live --confirm-session-usable --section extrude-depth`，
报告 `build/w05_live/t05_extrude_depth.json`，SHA256
`724BE1601190CFECF5CCD8BDB56FBEB0316BB204D18BD44505FA99C8530CB43D`，
`native_acceptance="partial"`（只跑本段）。最后一次重建执行器后复跑（SHA256
`A621B45720DA6B3E9D25A94939576F851D7412E792476B9365A672046492B6D8`）结论相同。

| 用例 | 入口 | 体积 | requested | effective | defaulted_fields | source / query_code |
| --- | --- | --- | --- | --- | --- | --- |
| `standalone_omitted_both` | `creo_extrude`（不传 depth/depth_type） | 99.99999999999997 mm³（≈100.000） | null / null | blind / **1.0 mm** | `["depth","depth_type"]` | feature_tree / 0 |
| `plan_depth_only` | `creo_execute_plan`（只给 `depth=10`） | 999.9999999999999 mm³（≈1000.000） | null / **10.0 mm** | blind / **10.0 mm** | `["depth_type"]` | feature_tree / 0 |

两例 `saved_file_reloaded_and_verified=true`，`extrude_depth_receipt="passed"`。

**未验证**：只跑了本段（`--section extrude-depth`），本轮未重跑完整 metric matrix；
`through_all` 的 null 只在单测覆盖，未实机取回执；Creo 9 / Creo 10 未测。

## 2026-11-05 W06 交付：只读预览入口与失败编辑回滚（实机）

**入口**：不新增工具。`creo_export_model(format="jpeg")` 即只读预览入口——提交 READ 作业、
不保存、revision 不推进，作业结果的 `preview` 块（`status`/`path`）供界面显示；
docstring 已写明空件 `status="skipped_no_geometry"`、渲染失败 `status="failed"` 带
`failed_step`/`failed_code`。能力清单未变。

**T07 三段预览（本机 Windows x64 / Creo 12.4.0.0）**

`tools/test_t07_preview.py --live --confirm-session-usable`，run `20261106T004546_2a364d3b`，
报告 `build/post090_n11_preview/20261106T004546_2a364d3b/report.json`，SHA256
`0EBDA9BA0BA3F59F9995955904C71CDF797653DC8CF5A364EDC825EA0695DF5C`，`preview_acceptance="passed"`。

| 段 | 用例 | 实测 |
| --- | --- | --- |
| 空件 | `empty_part` | `status="skipped_no_geometry"`，无图片文件，不报错 |
| 有几何 | `empty_part_solid` / `disk` | `status="written"`、`file_verified=true`、`preview_code=0`，9 个渲染步骤码全 0 |
| 修改后 | `disk_cut`（rev 2）、`disk_cut_pattern`（rev 3） | 每次编辑后重新生成预览，图片文件独立 |
| 只读导出 | `explicit_jpeg_export` | 作业成功，产出 `preview.jpg` 与导出的 jpg 同 sha256，**revision 3→3 未推进**（`read_only_revision_unchanged=true`） |

所有预览用例 `saved_file_reloaded_and_verified=true`。`image_content_verification="human_review_pending"`
——图片是否"画的是这个件"仍需人工看图，不由本服务断言。

**失败编辑回滚（BUG-096 场景）**

`tools/test_failed_model_cleanup.py --live --confirm-session-usable`，
run `20261106T004748_84fc913a`，报告
`build/bug096_failed_model_cleanup/20261106T004748_84fc913a/report.json`，SHA256
`7DA2D3D93DF260A101E39D0E227CA7E88ABE3D68C28A52301680C7405564050D`，三个场景全 `passed`：

| 场景 | 实测 |
| --- | --- |
| `S1_main_path` 新建件建特征失败 | 作业失败（`ProModelitemInit -23`），孤儿模型被擦除（`reason="cleaned"`、`absence_verified=true`、`erase_code=0`），同名重试成功（`revision=1`） |
| `S2_preexisting_same_name` 同名件已存在 | 冲突作业失败，`reason="preexisting_same_name"`、不谎报"已擦除"，既有件 revision 仍为 1 且可读 |
| `S3_saved_model_rollback` 已保存件的失败编辑 | `rollback_status="succeeded"`、`failed_model_cleanup.reason="not_new_model_job"`、revision 1→1 不变、模型与文件仍可继续编辑 |

**未验证**：`unknown_outcome` 记为 `not_injected (fault injection forbidden)`——按 BUG-001
恢复约定不做故障注入，只有离线契约；预览图片内容需人工复核；Creo 9 / Creo 10 未测。



## 2026-11-06 R01：偏置距离适用性保护（离线 + SDK 编译，未实机）

- 源码闸门（`native/surfaces.cpp::generic_surface_offset`）：不再无条件用 `volume_after/source_area`。仅当源 quilt 为**单一平面面**（新增 `native/quilt_query.h::QuiltPlanarity/quilt_planarity_native`，按 `PRO_SRF_PLANE` 计面）、偏置前体积≈0、结果体积为有限正值、源面积可用时，才发布 `measured_offset_distance_mm`；其余一律 null 并给 reason：`source_area_unavailable` / `source_surface_visit_failed` / `source_quilt_not_a_single_plane` / `pre_offset_volume_unavailable` / `pre_existing_volume` / `result_volume_unavailable`。
- 新块 `offset_distance_status={available,source,query_code,reason}`，与 `source_area_status` 分离：面积可测但距离不可用时，面积照常发布。归一化（`operation_results.normalize_offset_distance_status/annotate_offset_distance_status`）只认 `volume_over_source_area` 来源，未知来源、非有限值、畸形块降级为不可用并 null 距离；缺字段的历史作业不补造。compact 白名单加入新键。
- 新增 9 项单测：`test_existing_solid_does_not_become_offset_distance`（800 mm²、5 mm、已存 1000 mm³、总量 5000 的 6.25 不得当实测）、`test_curved_source_has_unverified_distance`、可用来源保留、未知来源/非有限值/畸形块降级、历史记录不动、归一化默认值、原生闸门源码锁。
- 验证：`tests/unit/test_surface_measure_guard` + `test_surface_offset_contract` 28 项 OK；`bridge.py build` 退出 0（SDK 头实际编译新代码）；全量单测与 dev_check 见本轮汇总。
- 未验证：Creo 实机 40×20/±5 mm 空件、已有实体、曲面源的实际几何/来源/保存重载/失败回滚；Creo 10 无新证据。空件若 `volume()` 在无实体时抛错，会保守落入 `pre_offset_volume_unavailable` 而非误报。

## 2026-11-06 R01 实机验收（Creo 12.4.0.0 / 匹配 SDK）

命令：`.\.venv\Scripts\python.exe tools\test_surface_chain.py --case offset --live --confirm-session-usable`
（新增驱动 `tools/surface_chain_offset.py`，注册为 `--case offset`；默认离线）。
报告：`build/surface_chain/20261106-121417-172300/report.json`，`passed=true`、`native_offset_distance=verified`，27 项检查全通过，8 个 job。

| 场景 | 结果 |
| --- | --- |
| 空件 40×20 fill，偏置 +5 | `measured_offset_distance_mm≈5`、`source=volume_over_source_area`、`direction=positive`、壁体积≈4000 mm³、保存重载 true（job `9cc254dc…`） |
| 空件 40×20 fill，偏置 -5（另一新件） | 同上，`direction=negative`（job `fccba0e7…`） |
| 已有实体 8000 mm³ + fill | `available=false`、`reason=pre_existing_volume`、`measured_offset_distance_mm=null`，`volume_before_mm3≈8000` 实报 |
| 圆柱面 quilt（surface extrude R20/H12） | `available=false`、`reason=source_quilt_not_a_single_plane`、距离 null，源面积≈1507.96 mm² 照常发布 |

结论：偏置距离只在“单一平面源 + 前置体积≈0”时发布，已有实体和曲面源改为 null 加原因，与离线闸门一致；未验证 Creo 10、offset 失败回滚与 `offset_mm` 变体。


## 2026-11-07 DEV-074 反馈对照（离线）

0.17.4 四份外部 Creo 10 报告与当前代码已逐项对照。已有正证据、此次离线增量和未完成边界见 [MAPPING](../validation/feedback-0.17.4-2026-11-07/MAPPING.md) 与 [接手清单](../development/DEV-074-HANDOFF.md)。本轮未连接 Creo；不以离线编译/单元测试关闭原生几何或保存重载验收，不改变历史证据结论。

## 2026-11-07 H06 交付：保留侧真实几何测量（实机）

H06 的缺口是“保留侧缺 centroid/bbox/世界方向”，此前 `kept_side_basis` 的质心恒为 null
（`quilt_centroid_not_measured`）。本轮确认 `ProQuilt.h` 没有质心/bbox 查询，但
`ProQuiltSurfaceVisit` 暴露成员面，`ProSurfaceTessellationGet`（`ProSurface.h:701`）能取到
**修剪后**面的三角网格；据此在 `native/surface_measure.h` 新增统一 `RegionGeometry` /
`quilt_region_geometry()`，用面片面积加权得到质心、轴对齐 bbox 与绕向对齐的平均法向。
非平面区域不报方向（`region_not_planar`），单位未知时毫米值保持 null，失败一律带 reason 与 query_code。

`surface_trim` 现在报告 `target_centroid`/`kept_centroid`、`centroid_delta_mm`、`target_bbox_mm`/
`kept_bbox_mm`、`target_direction`/`kept_direction` 及各自 `*_status`；`tool_normal` 对平面 quilt 工具
给出实测面法向并标注 `tool_normal_source`；`signed_offset_mm` 只在法向符号可锚定（基准面）时发布，
并按契约 §4.5 在符号与 `keep_side` 矛盾时失败回滚。Python 侧新增
`operation_results.normalize_kept_side_basis/annotate_kept_side_basis`，只做“值不脱离状态”的投影。

实机（run `20261107-121303-781400`，41 项检查全通过，6 个 job）：

| 工具 | keep_side | job_id | 面积 mm² | target→kept 形心 | 差值 mm | 保留 bbox x | 方向 | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 基准面 x=5 | one | `557ad826…` | 700.0 | (20,10,0)→(22.5,10,0) | +2.5 | [5,40] | (0,0,−1) planar | true |
| 基准面 x=5 | two | `b4313225…` | 100.0 | (20,10,0)→(2.5,10,0) | −17.5 | [0,5] | (0,0,−1) planar | true |
| quilt x=5 | one | `549773db…` | 700.0 | (20,10,0)→(22.5,10,0) | +2.5 | [5,40] | (0,0,−1) planar | true |
| quilt x=5 | two | `2316d276…` | 100.0 | (20,10,0)→(2.5,10,0) | −17.5 | [0,5] | (0,0,−1) planar | true |

两个保留侧的形心分别落在工具平面 x=5 两侧（+17.5 / −2.5），不再用面积减小证明“外侧”。
quilt 工具实测面法向为 `(−1,0,0)`（与草图支撑面相反），因此其 `signed_offset_mm` 保持 null 并给
`tool_normal_unavailable`，侧别由形心坐标证明。失败用例（x=100 的工具不相交）：job
`1fde1a0c…` 失败、`rollback_succeeded=true`、模型仍为 800.0 mm² 未修剪填充、revision 1→1。

证据：[EVIDENCE](../validation/feat039-h06-kept-side-2026-11-07/EVIDENCE.md)、
[live_trim_report.json](../validation/feat039-h06-kept-side-2026-11-07/live_trim_report.json)
（SHA256 `4911D20D…0936C6A`）。**未覆盖**：非平面区域、非 mm 单位、多面 quilt、quilt 工具法向跨重建稳定性、
Creo 9/10；`rollback_kept_the_revision` 不含 unknown_outcome。

## 2026-11-07 H04 交付：曲面组级测量（实机）

H04 的缺口是"组级闭合、公差 0.01、缝隙/重叠"，此前只有逐 quilt 的 `ProQuiltVolumeEval` 布尔。
本轮新增 `native/surface_group.cpp` 与只读算子 `surface_group_measure`
（MCP 工具 `creo_measure_surface_group`）：把一组 quilt 的全部成员面当作组，用真实边界拓扑回答
`open_edges`、`gap_max_mm`（含 `tolerance_mm`/`gap_search_mm`）、`overlap_area_mm2` 与四态
`state`（`closed`/`open`/`micro_gap`/`overlap`），每值独立 `*_status`，单位未知时 mm 值保持 null。

- **拓扑/几何依据**：`ProQuiltSurfaceVisit` → `ProSurfaceContourVisit` → `ProContourEdgeVisit`；
  同一 `ProEdge` 被两个成员面引用即拓扑共享缝；其余边界边按采样折线做一对一配对（横向距离 +
  纵向重叠 ≥10%），容差内 joined、容差外但在 `gap_search_mm` 内计 gap。
- **重叠**：面网格细分采样 + `ProSurfaceParamEval`/`ProSurfaceXyzdataEval`/`ProSurfaceUvpntVerify`
  判断采样点是否落在另一面裁剪域内；另计"埋入边界"，使细于采样间距的重叠带也能检出。
  面积是估计值，`area_below_sample_resolution` 明确标出"检出重叠但面积估计为 0"。
- **入口**：`surface_chain` 的 `surface_loft` 回执新增 `surface_group` 块（单 quilt 自身面组）；
  独立只读查询 `creo_measure_surface_group`。Python 侧 `operation_results.normalize_surface_group`
  只做"值不脱离状态"的投影，不重算任何量。
- **实机（run `20261107-132056-710000`，42 项检查全通过）**：两张 40×20 填充按 offset 构造
  ①共边 → `closed`、`open_edges=6`、`gap_max=0.0`；②0.005 mm 缝 → `micro_gap`、
  `gap_max=0.005000000000009663`；③0.5 mm 缝 → `open`、`gap_max=0.5`；④0.5 mm 重叠 →
  `overlap`、`buried_boundary_edges=2`、面积为 0 并标 `area_below_sample_resolution=true`。
  四例 revision 均 1→1（只读测量不推进），建模作业 `saved_file_reloaded_and_verified=true`。
- **构造限制（实测）**：autodim 会把草图轮廓量化到 0.01 mm（请求 40.005 实测 40.01），
  0.005 mm 用例必须用 `dimensioning="coordinates"`；共面两片仍无法 `quilt_merge`（H03 gated），
  因此组级测量只对独立 quilt 集合取证。
- 证据：[EVIDENCE](../validation/feat039-h04-surface-group-2026-11-07/EVIDENCE.md)（报告 SHA256
  `D530B999…2D5C9970`）。**未覆盖**：Creo 9/10、非 mm 单位、多面/曲面成员、`open_edges=0` 的
  闭合壳体组、重叠面积精度与 `gap_search_mm` 之外的间距量化。

## 2026-11-07 H03 反证：INCOMPLETE 骨架路线未救回 quilt_merge（实机，保持门禁）

按 `surface_loft` 的成功经验（`PRO_FEAT_CR_INCOMPLETE_FEAT` 只建最小骨架、抽取后 redefine，
不预先手写可选元素）重试两片共边 20×20 填充的 join。结果与历史失败形态逐项相同：

| 尝试 | job_id | create | extract | ProErrorlist | feature_status | quilt 访问 | quilt 数 | surface 数 | 输入面积 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HEAD 一次性创建 | `0065877624af4cf4932a8179682908b3` | —（旧实现未记录） | — | — | 0（ACTIVE） | -4 | 0 | 4（132/134/136/138） | 800.0 mm² |
| INCOMPLETE → extract → redefine | `80adc5a5ae714cf5bc40f9936ec6122d` | **0** | **0** | **total=0** | 0（ACTIVE） | **-4** | **0** | 4（同上） | 800.0 mm² |

内核补全后的抽取树共 11 个元素：`PRO_E_FEATURE_TYPE=946`、`PRO_E_SRF_MRG_QUILT_ARR` 两个
`PRO_E_SRF_MRG_QUILT_CMPD`（各含 `PRO_E_SRF_MRG_QUILT_REF` 与**内核自补**的
`PRO_E_SRF_MRG_QUILT_SIDE=1`）、`PRO_E_SRF_MRG_TYPE=1`（JOIN）、特征名。即：**是否预先写
SIDE 并不改变结果**，内核补全值与显式值一致；`surface_loft` 的「少写可选值」根因在此不成立。
特征再生成功但只拥有 4 个 `PRO_SURFACE`，不拥有 `PRO_QUILT`，`result_quilt_id`、面积、闭合
都无法测量，也没有可交给 `thicken`/`solidify` 的对象。

两次失败作业的 `terminal_effect.managed_model` 均为 `no_effect / new_model_cleanup_confirmed`
（新建模型被清理），未产生半成品。诊断期间一次 `ProQuiltInit` id 扫描使原生 worker 超时
（job `9b64c0fb330b49a285200d286934bc06`，`unknown_outcome`）；按 BUG-001 约定未重试、未清
unknown 保护、未改模型，诊断代码已删除。

**结论**：`quilt_merge` 继续保持 `UNAVAILABLE_OPERATIONS`，门禁文案与能力边界不变；
链式三片、保存重载、失败回滚等验收项在没有结果 quilt 前无可验收对象。下一步若继续，应先
在 Creo 界面手工建一个 Merge 特征并用 `tools/read_reference_tree.py` 读回真实树
（种子库没有 Merge 参照件），而不是再猜 `ProMerge.h` 数组树。

证据：[EVIDENCE](../validation/feat039-h03-quilt-merge-incomplete-2026-11-07/EVIDENCE.md)、
[merge_probe_report.json](../validation/feat039-h03-quilt-merge-incomplete-2026-11-07/merge_probe_report.json)
（SHA256 `BCE2E488…7071FF16`）。**未覆盖**：结果 quilt 的链式/重载/回滚验收、Creo 9/10、
非 mm 单位、非平面成员。

## 2026-11-07 H09 交付：旋转球面替代路线（实机；任意非平面 fill 仍不可用）

H09 的缺口是“任意非平面闭合边界填充”。勘察结论：`FillOp` 只有 `sketch`（平面草图），原生
`native/surfaces.cpp::generic_fill` 只写 `PRO_FEAT_DATUM_SURF` + `PRO_FLAT` +
`PRO_E_SEC_USE_SKETCH`，没有 3D 闭环/边界集合输入，因此非平面填充不是“门禁太严”，而是**没有
输入通道**。本轮不放宽 planar fill、也不新增“看似能做”的 `surface_fill` 变体。

中心 R8 场景改走**已有的曲面旋转**：一条半圆子午弧 + 一条构造中心线，
`revolve{mode="surface", angle=360}`（原生 `PRO_REV_AXIS_INT_REF`）。该能力此前只有“曲面旋转
可用”的声明，没有球面读数；本轮补齐实机。

驱动 `tools/test_surface_revolve.py`（默认离线 12 项；`--live` 22 项），run
`20261107-235346-03398b`，5 个作业全部成功：

| 步骤 | 实测 |
| --- | --- |
| R8 半圆 360° 旋转 | 特征 49 `type=942`/ACTIVE、quilt **74**、2 面、bbox `[-8,-8,-8]..[8,8,8]`、面积 **804.247719319002 mm²**（4πR² 差 1.5e-11）、`closed=true`、无实体、保存重载 true |
| 基准面 x=4 trim（one） | 保留球冠 **201.06192982974773 mm²**（oracle 201.06192982974676），保存重载 true、rev 2 |
| 球冠 2 mm 对称 thicken | 体积 **404.21825476170756 mm³**：精确球壳 oracle 406.31264986427993（−0.52%），面积×厚度 402.12385965949545（+0.52%），容差 2% 运行前固定 |
| 同一刀另一侧（two，独立模型） | **603.1857894892481 mm²**，两侧和 804.2477193190 |
| 闭合球面 solidify（独立模型） | 体积 **2144.6605848506724 mm³** = 4/3πR³，独立证明 quilt 闭合 |

**非平面 fill 的拒绝证据**：带 `boundary:{kind:"quilt"}` 的 `surface_fill` 计划经公开
`creo_execute_plan` 返回 `isError=true`、无 `job_id`（`sketch Field required` 与
`boundary Extra inputs are not permitted`）；离线 `boundary`/`edges`/`sections` 三种写法同样在
受理前被拒。planar fill 的 schema/原生树未做任何修改。

新增单测 `tests/unit/test_surface_revolve_contract.py`（14 项）：曲面旋转准入、开放子午弧、
实体旋转仍要求闭合轮廓、fill 拒绝 3D 边界通道、planar fill 不变、`revolve` 已公开、
原生 surface 分支与 fill 的 `PRO_FLAT` 源码锁。`bridge.py build` 退出 0（本轮无原生改动）、
ruff check/format 干净。

证据：[EVIDENCE](../validation/feat039-h09-surface-revolve-2026-11-07/EVIDENCE.md)、
[live_surface_revolve_report.json](../validation/feat039-h09-surface-revolve-2026-11-07/live_surface_revolve_report.json)
（SHA256 `1AA72913…40BDCBD7`）。**未覆盖/仍不可用**：任意非平面闭合边界 fill（无原生路线，
未排期）；Creo 9/10、非 mm 单位、部分角度球带、显式外部基准轴、倾斜轴；0.3 mm 壁厚整链归 H10。

