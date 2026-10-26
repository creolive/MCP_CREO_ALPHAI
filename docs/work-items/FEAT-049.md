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


## 2026-10-26 v0.5.2 反馈来源与本次子项（T00）

来源：[三份原件清单](../validation/feedback-0.5.2-2026-10-26/manifest.json)；[逐章映射](../validation/feedback-0.5.2-2026-10-26/MAPPING.md#r1-13)。R1/R3 为外部实机报告，R2 为无 Toolkit 连接的升级/编译/静态报告。

R1 §5 P1-3延续快照无法回放请求，本卡为T09/0.7.0子项。已确认只读creo_plan_assembly_rebuild(snapshot_id, component_mapping, reference_mapping)生成execute_plan operations及绑定源身份；双侧引用/方向/偏移单位、replayable/reason，先全插入后约束、同层兄弟引用、六既有写入类型。源revision/摘要提交和原生使用前复核；旧/过期证据、缺映射、未知类型、嵌套明确拒绝，不转fixed，不拆多事务。真实随动及保存重载验收；FEAT-050公共比对不纳入。本段取代历史候选桥接工具选型，未实施。

共享接口遵循 [DEV-047 基线](DEV-047.md#interface-baseline)。本段仅补来源与已确认的本次子项；T00 未实现业务、未新增实机证据，不据此关闭父卡其他范围。
