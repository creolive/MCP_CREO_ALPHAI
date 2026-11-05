# 端点焊接契约（FEAT-039/W01）

## 范围

本契约冻结"端点焊接"的**策略层**：Python 只生成端点配对/拒绝建议和原始输入证据，
不模拟原生求解，也不移动几何。真正的重合、求解与读回由 Toolkit 完成；在原生焊接
落地之前，`endpoint_policy="weld"` 被明确拒绝，`applied` 永远是 `false`。

## 请求字段（草图创建与草图更新共用同一份定义）

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `endpoint_policy` | `report` / `reject` / `weld` | `report` 只报告配对证据；`reject` 在排队前拒绝可焊接的轮廓；`weld` 目前被拒绝 |
| `max_endpoint_move_mm` | 正数，可选 | 允许的对称移动上限；每端所需移动为 `gap/2` |

默认值是 `report`，**不靠删除旧边界默认启用吸附**。

## 配对规则（按顺序）

1. 候选对：两条**不同**曲线端点间距落在聚类容差 `1e-4 mm`（闭合诊断尺度）内，且间距不为 0
   （完全重合的点本来就是一个点，不是候选）；
2. 唯一性：一个端点最多参与一个被接受的配对；同距并列时判为 `ambiguous_pair` 并拒绝，
   不做任意挑选；
3. 不跨环搭桥：按严格容差（`1e-9 mm`）把曲线连成链，只有**同一条链**的两端可以焊接，
   两条不同的链（两个环）之间一律拒绝（`separate_loops`）；
4. 圆弧守卫：两条圆弧必须同圆（圆心、半径一致）且扫角非零；在聚类容差下这一条已由端点
   接近蕴含，属于防止几何被改写的兜底检查；
5. 位移上限：每端所需对称移动为 `gap/2`，超过 `max_endpoint_move_mm` 的配对拒绝
   （`max_move_exceeded`）。

## 回执字段（`endpoint_weld`，随作业结果发布）

`policy`、`applied`、`native_applied`、`threshold_mm`、`threshold_source`、
`kernel_weld_bound_mm`、`kernel_weld_bound_source`、`observed_kernel_weld_mm`、
`candidate_pairs`、`accepted_pairs`、`welded_pairs`、`refused_pairs`、`max_move_mm`、
`max_residual_mm`、`failure_reason`、`pairs`（≤20 条样本）、`refused`（≤20 条样本）、
`requested_geometry`（请求实体数与曲线数）、`actual_geometry`（原生落地前为 `null`）。

两个尺度必须分开读：`threshold_mm=1e-4` 是闭合诊断的聚类尺度，`kernel_weld_bound_mm=1e-9`
是已发布的原生草图 epsilon；2026-10-31 的反馈里内核实际焊接过 `8.215e-7 mm` 的间隙，
因此 `1e-9` 只是风险界，不是保证。**待标定**：可接受输入间隙与最大移动量。

## 当前边界

- 已交付：策略层、回执、创建与更新共用的策略、`reject` 的排队前拒绝、`weld` 的明确拒绝、
  10 条契约测试。
- 未交付：原生焊接求解（`weld` 策略）、焊接后的几何读回与残差、原案 gear10 的
  体积基准 `1849.8028532376422 mm³` 对比、以及"原默认调用路径"是否达标的判定。
