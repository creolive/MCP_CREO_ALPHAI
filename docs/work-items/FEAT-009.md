# FEAT-009：放样曲面模式与多截面能力

日期：2026-10-31（工作卡补建）。类型：功能。优先级：P2。状态：待规划。目标版本：未排期。

来源：[0.3.5 曲面反馈](../validation/feedback-0.3.5-surface-2026-10-18/report.md) 与[能力边界反馈](../validation/FEEDBACK-0.3.5-CAPABILITY-2026-10-18.md)；[0.10.0 晚间包 02_G5 曲面能力方案](../validation/feedback-0.10.0-2026-11-01/originals/02_G5曲面能力方案.md) §2（`surface_loft` 元素树路线）；[逐章映射](../validation/feedback-0.10.0-2026-11-01/MAPPING.md)。关联 [FEAT-039](FEAT-039.md)（纯曲面链路算子）、[FEAT-053](FEAT-053.md)（三点定面）、[BUG-052](BUG-052.md)（曲面类型查询）。

## 目标与范围

扩展放样切除、曲面、非平行截面及相切/曲率控制。7～20 截面种子、截面增删和模式转换分别测试，**不能用其中一项通过代表全部可用**。

可乐瓶任务书第 2 步（两 50° 截面放样曲面）直接命中：0.3.5 的 loft 仅 solid/add/XY 平行截面/默认 body，外部只能用 revolve{new_body} 几何等价绕道。曲面模式与 FEAT-039 的 MVR 第 4 步联动。

2026-10-31 晚间包补充的方向：`surface_loft` 走元素树（`PRO_E_BLEND_SECTIONS` + `PRO_E_BLEND_ATTRIBUTES`），可像 `extrude/revolve` 一样在执行器内直接 `ProFeatureCreate`，不需要常驻回调与 UI 宏；截面可位于任意平面，不受"XY 平面 + Z 单调"限制。该路线与外部"复用回调切 Surface 模式"并列，**元素树路线优先**。回执字段 `surface_area_mm2` 由 Q07 契约冻结后确定。

本卡范围：**放样曲面模式与多截面**。`project_curve` 与 `surface_trim` 归 [FEAT-039](FEAT-039.md)；三点定面归 [FEAT-053](FEAT-053.md)。已有实体 loft 的 XY、add 及回调契约保持不变，不被本项替换；`thicken`/`solidify` 不重复开发。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `python -m unittest tests.unit.test_surface_loft -v` 与专项驱动 | 引用/参数/非法枚举校验与错误可判读；capabilities 与能力说明同步 |
| 本机 Creo 12.4 / 匹配 SDK | 两条平行直线生成矩形曲面，以解析面积核验 | 曲面类型正确、无意外实体体积；回执 `surface_area_mm2` 与解析值一致 |
| 本机 Creo 12.4 / 匹配 SDK | 扭转截面 / 多截面 / 非平行截面夹具 | 截面顺序、引用唯一性与方向语义符合契约；未支持的 `smooth`/`closed`/连续性明确拒绝而非静默降级 |
| 本机 Creo 12.4 / 匹配 SDK | 编辑或下游引用、失败回滚、保存重载 | 特征可重载引用稳定；失败回滚成立且 revision 契约不变；`saved_file_reloaded_and_verified == true` |
| 回归 | 既有 solid loft 与 thicken/solidify | 无回归；实体 loft 行为不变 |

原生范围不适用时写明原因。按当前项目规则，不要求 Creo 10 独立复测或双版本验收；外部 Creo 10 结果保留原环境归属。

## 实现与证据

2026-10-31 仅补建工作卡并按晚间包补充方向，无实现。实现前须先由 Q07 冻结原生契约（sections 顺序、quilt/curve 引用唯一性、方向坐标系/单位、回执字段），不得照抄未经证明的外部元素树数值 ID。Q07 未冻结前不承诺具体模型/函数名。
