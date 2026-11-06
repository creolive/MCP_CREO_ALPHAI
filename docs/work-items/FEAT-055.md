# FEAT-055：Q08–Q10 三曲面操作链重规划

日期：2026-11-02。类型：功能/技术路线。优先级：P2。状态：部分交付（0.11.5/0.11.7/0.12.0 反馈批的归档与逐条映射挂在本卡下，派工编号 Q00—Q07；0.13.0 反馈批见修复计划）。Q00 归档已完成；Q09 投影曲线与 Q10 曲面修剪/加厚测量已由 [FEAT-039](FEAT-039.md) 在 **0.13.0** 实机公开（`creo_project_curve`、`creo_surface_trim`）；Q08 边界混合/`surface_loft` 路线仍不成立，没有公开工具或已注册操作；Q01—Q07 尚未整体实现，按 [0.13.0 修复计划](../superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md) 分批推进（本轮仅完成 R07 契约文档的离线部分）。目标版本：未排期。关联 [DEV-053](DEV-053.md)、[FEAT-053](FEAT-053.md)、[FEAT-039](FEAT-039.md)、[FEAT-054](FEAT-054.md)、[DEV-064](DEV-064.md)。

## 来源

- 台账登记：`docs/BACKLOG.md`（2026-11-02 发布后缺口）。
- [G5 原生契约](../development/G5-NATIVE-CONTRACT.md)、[四轮实机记录](../validation/DEV-053-Q15-live-2026-11-01.md)。
- 外部反馈：[0.11.1 F01 核心问题 4](../validation/feedback-0.11.1-2026-11-02/MAPPING.md)。

## 现状

`surface_loft`（边界混合）/`project_curve`（投影曲线）/`surface_trim`（曲面修剪）→ thicken 三条探针路线实机均判"路线不成立"（特征 UNREGENERATED、无几何或建树失败）。曲面探测头已备（台账 DEV-055，未建独立卡），但探测符号与调用序列尚不足以支撑可用特征。

## 目标

重拟三算子的技术路线（Toolkit 调用序列、失败重生成策略、与 thicken 的几何闭合条件），先做可复现探针，再按 G5 契约实现。

## 范围与顺序（草案）

1. 逐算子重新设计调用序列，保留"探针失败即回滚、不留半成品"的既有失败清理契约。
2. 单算子最小可用：投影曲线 → 边界混合 → 曲面修剪，每步都要能保存重载验证。
3. 三算子串联 + thicken，验证法向与闭合；再回到 P12（FEAT-054）评估是否能替换 194 ops 替代路线。

## 验收方式（草案）

- 每个算子独立实机用例：特征生成成功、可重生成、几何断言通过、`saved_file_reloaded_and_verified=true`。
- 串联用例：thicken 后体积/曲面面积在容差内，且不依赖 194 ops 替代路线。
- 未达成时保留"路线不成立"记录与失败原因，不得以部分几何交付。

## 与本批关系

本批（R12 / 0.11.4）**不做**实现，只归档 0.11.1 的"仍未实现"事实；P12 仍只能走 194 ops 替代路线，贴近 200 ops 上限的风险由 FEAT-054 处理。

## 2026-11-03 R13 增量：0.11.5 曲面链逐字未变（Creo 10 实测）

- 0.11.5 反馈 F04（Creo 10）逐项复测：`creo_check_environment` / capabilities 的 `surface_solid` 家族 scope 与 limits 与 0.3.5、0.11.1 **逐字一致**，`operations` 仍 60 项；`surface_loft` / `project_curve` / `surface_trim` 仍无高层工具。
- 新发现（已登记在本卡待办，不在 R13 实现）：`inspect_model(section="surfaces")` 对纯曲面模型返回 `[]`（走 `ProSolidBodySurfaceVisit` 只枚举实体面）；`{"kind":"quilt_feature"}` 对 trim 结果特征在 `ProFeatureGeomitemVisit` 报 `-4`，导致"修剪 → 缝合"第二环无合法引用；`counts.surfaces/edges` 恒 0、无 quilt 面积/`closed`。
- 曲面前提事实：低层 `creo_create_feature_tree` 已能修剪（10 元素树，job `7045d780…`，`saved_file_reloaded_and_verified=true`），漏 `PRO_E_MATERIAL_SIDE` 会再生失败且无缺口提示；`PRO_FEAT_TRIM` 在 Creo 10 SDK 不存在，须 `PRO_FEAT_CUT` + `PRO_E_SRF_TRIM_TYPE`。
- MVR 顺序维持报告方建议：`inspect_model(section="quilts")` → `creo_surface_trim` → `creo_quilt_merge` → `creo_quilt_offset` → `creo_boundary_blend` → `loft{mode:"surface"}`。
- R13 只登记事实与顺序，**不实现**；若后续开工，先做 quilts 查询（不解决它，后续全部卡住）。

## 2026-11-04 S00 增量：0.11.7 反馈归档、派工登记与契约修订

- 0.11.7 四份原件逐字节归档（[manifest](../validation/feedback-0.11.7-2026-11-04/manifest.json)）；逐条映射与证据分级见 [MAPPING](../validation/feedback-0.11.7-2026-11-04/MAPPING.md)。F03 证实：`sections_available` 仍无 `quilts`、merge 引用 trim 结果 `ProFeatureGeomitemVisit -4` 两版同码；本卡状态保持待规划。
- 派工登记：[0.11.7 计划](../superpowers/plans/2026-11-04-0.11.7-surface-chain-improvement-plan.md) 的 S00—S10 / C01—C04 / W01—W06 复用既有行，Sxx 是派工编号；S01（quilts 查询、共享测量、quilt 引用修复）归本卡与 FEAT-039，S02—S07 归 FEAT-039/FEAT-009，S08 集成、S09 归 FEAT-054、S10 交付。
- G5 契约按 S00 修订（[§0.1](../development/G5-NATIVE-CONTRACT.md)）：显式 `{"kind":"quilt","id"}` 引用、quilt/surface ID 不可互换、schema 不建 job 与运行时引用失效分层、投影 oracle 纠偏（O2 平面用例 + O2b 圆柱待定义）、修剪两侧按实测位置判、旧路线失败历史保留。
- 契约测试同步：`tests/unit/test_g5_native_contract.py` 19 项全过（新增 oracle 域内性、显式 quilt 类型、候选清单、旧路线状态断言）。本轮不连 Creo、不运行 Toolkit、不合 main、不发布；实机项均未验证。

## 2026-11-04 S01 交付：quilts 查询、共享测量与 quilt 引用修复

- 查询面：`inspection.quilts` 新分区（记录含 `quilt_id`/`feature_ids`/`face_count`/`surface_ids`/`area_mm2`/`area_status`/`closed`/`closed_status`/`bbox_mm`/`bbox_status`，各测量带单位上下文，未知尺度保持 null）、`counts.quilts`、分页与快照绑定；`sections_available` 20→21 项。旧 `surfaces`/`edges`/`counts` 语义不变；旧快照无 quilts 记 unavailable 而非 0。装配为 null。
- 原生面：新增 `native/surface_measure.h`（共享测量：外环−内环面积、曲线长度/端点、`measurement_status_json`；失败不伪造零）与 `native/quilt_query.h`（`collect_model_quilts`/`quilt_reference_candidates`/`resolve_quilt_reference`，候选 ≤20 有界）；`generic.cpp` inspection 接线并改走引用解析。显式 `{"kind":"quilt","id"}` 与 `quilt_feature`（0/多候选拒绝并附候选清单）统一入口；不再有盲选 PRO_QUILT 的一行式分支。
- 统一驱动：`tools/test_surface_chain.py --case quilts`（离线默认；`--live --confirm-session-usable` 双开关；未知用例连接前拒绝；报告写 `build/surface_chain/<run_id>/` 不覆盖）。离线报告明确 `native_quilt_query=not_verified`。
- 验证：`bridge.py build` 编译通过；`tests/unit/test_quilt_query_contract.py` 10 项全过；全量 2 286 项单元测试通过；驱动离线用例通过（含游标绑定、旧快照 unavailable、ID 不混用）。**实机未验证**：quilts 分区的真实几何、面积/闭合/外框值、`ProQuiltVolumeEval` 闭合探测与候选诊断均待实机串行窗口；不得把编译通过当作建模能力。

## 2026-11-04 S02 增量：quilt 引用被高层 trim 消费

- `native/surface_trim.cpp` 只经 `resolve_quilt_reference` 解析 target/tool，不自行枚举 quilt，也不新开第二条 PRO_QUILT 选取路径；S01 的 0/多候选拒绝与有界候选清单对高层算子同样生效。
- `creo_surface_trim` 已注册进 `REGISTERED_OPERATIONS`，同时列入 `UNAVAILABLE_OPERATIONS`：`server.py` 的既有钩子把它从 MCP 工具面移除，`require_available` 在受理前拒绝并给出原因（保留侧绑定与 trim 结果引用仍需实机证据）。因此 quilts 查询面不变（`sections_available` 仍 21 项、`counts.quilts` 语义不变），新增的只是被门禁的算子和其原生实现。
- 详见 [FEAT-039 S02 段](FEAT-039.md)。

