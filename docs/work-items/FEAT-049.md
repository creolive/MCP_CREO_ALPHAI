# FEAT-049：约束快照回放

类型：功能

优先级：P1

状态：待规划

目标版本：后续 MINOR（0.5.0 反馈第三批）

来源与关联：[装配编辑流程改进建议 P1-3](../validation/feedback-0.5.0-2026-10-22/2026-10-22_CREO10_v0.5.0_装配编辑流程改进建议.md)（外部 Creo 10 / 0.5.0 实操）；[0.5.0 反馈整合计划](../development/0.5.0-FEEDBACK-PLAN-2026-10-22.md) 第三批；关联 [FEAT-045](FEAT-045.md)、[FEAT-048](FEAT-048.md)、[DEV-046](DEV-046.md)。

## 问题或目标

FEAT-045 的约束快照（type: align/mate/orient/align_offset、type_code、item_id、item_type、occurrence_path、offset）完整返回了约束，但 `assemble_component` 的 `constraints` 入参是 `additionalProperties: true` 的自由对象，没有公开的字段映射契约，快照无法直接喂回。外部实操只能用 `placement: fixed` + 平移兜底——约束语义（尤其 mate 的几何依附关系）在重建中丢失，装配改动后不能像原装配那样自动调整。

## 范围

包含（规划方向）：

- 先补约束双侧方向、引用身份及可回放诊断；提供字段映射文档或专用桥接（如 `creo_assemble_from_inspection`，直接读 FEAT-045 快照 + 已收养组件按约束重建），或在 inspect 结果中输出 `assemble_component.constraints` 可直接使用的形态。
- 首期限单层装配和现有六种写入类型，建立 occurrence→新组件、源引用→副本引用映射。
- 回放先插入组件，再设置约束，末尾统一保存重载；失败验证检查点、引用和 revision 保持。
- 未知类型、缺失映射或无法还原的根装配引用明确拒绝，不静默退化为固定放置。

不包含：嵌套子装配与新增约束类型（继续分期）；约束求解器语义扩展。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| 本机 Creo 12.4 / E 盘 dev 服务 | 单层装配约束回落实机（须先满足会话核对条件） | 约束驱动实际几何联动：改变驱动条件后组件位置随动，不只比较初始位姿；保存重载后约束保持；未知类型/缺失映射结构化拒绝且 revision 不变 |

## 实现与证据

2026-10-23 预登记，未实施。
