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

## 2026-10-26 T09 离线实现子项

本次子项状态：**离线完成，实机未验收**（[T09 验收记录](../development/DEV047-T09-ACCEPTANCE-2026-10-26.md)）。只读快照升级到 schema 3，新增双侧引用身份、`asm_side`/`comp_side`、`offset_unit`/`offset_mm`、`placement_kind` 与 `replayable`/`reason`；旧快照明确拒绝。新增只读 `creo_plan_assembly_rebuild(snapshot_id, component_mapping, reference_mapping)`，按“全部插入 → 设置约束”生成 `creo_execute_plan` 操作，复用 `mate`/`align`/`mate_offset`/`align_offset`/`insert`/`csys` 六种写入类型；装配侧引用可用 `assembly_component` 指向同层兄弟组件。fixed/default 按真实放置语义单列，未知类型、缺失/歧义映射、不可还原根引用、嵌套、过期/旧证据、源件变化及超过 200 操作均明确拒绝，不转 fixed、不拆事务。每个插入绑定源件 revision/摘要，提交与原生使用前复核；规划本身不加载/收养/修改、不建写作业/revision、不连接 Toolkit，也没有 `operation_results`。

`tools/test_t09_assembly_replay.py` 已覆盖六类型、同层引用、随动、保存重载及拒绝/不变性场景，但**未运行**；六类真实约束效果与随动证据仍待 T13。FEAT-050 公共比对、嵌套回放和新约束类型不在本次范围。

### T13 实机矩阵（2026-10-26）

`tools/test_t09_assembly_replay.py --live` 本机 Creo 12.4 通过：六类约束+default 完整回放、同层兄弟引用、偏移与源件编辑两条路径的真实随动、五类拒绝与源/目标不变性。实机发现并修复规划器逐约束生成 component_constraints（原生整组替换只留最后一条）缺陷，改为每组件一条操作。证据 `build/t09_assembly_replay.json`。
