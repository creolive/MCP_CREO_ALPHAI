# FEAT-055：Q08–Q10 三曲面操作链重规划

日期：2026-11-02。类型：功能/技术路线。优先级：P2。状态：待规划。目标版本：未排期。关联 [DEV-053](DEV-053.md)、[FEAT-053](FEAT-053.md)、[FEAT-039](FEAT-039.md)、[FEAT-054](FEAT-054.md)、[DEV-064](DEV-064.md)。

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
