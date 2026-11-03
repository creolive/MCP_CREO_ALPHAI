# FEAT-004：尺寸归属、可编辑性与修改旧值保护

类型：功能。优先级：P2。状态：验收中（A02分支离线实现2804d5a；实机与0.12.0基线集成待验）。目标版本：未排期。

来源：原主台账既有同ID条目；2026-11-03补建缺失工作卡，不新增台账身份，不改历史结论。

## 原目标与当前边界

尺寸查询说明所属特征、驱动/从属/参考属性及可编辑性；关系控制提示修改驱动参数或关系，拒绝时revision不变，以自由尺寸对照。现有代码已有relation_driven查询和关系驱动拒绝，不能重做或误记完全缺失。

## 2026-11-03 alphai 比较新增子项

本次增加可选 expected_value/expected_symbol/expected_owner，保留 id/value 旧接口；同一尺寸操作先全部核验再写入，旧值比较容差 max(1e-8,abs(expected_value)*1e-8)，查询失败不能假装可编辑。

任务号 A02，负责人unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-a-foundation-plan.md)，统一协调[DEV-067](DEV-067.md)。

## 验收标准与环境

旧接口兼容；旧值/符号/归属/关系失败可诊断；批内第二项不符无部分提交；成功保存重载true；原生守卫失败核回滚与后续编辑，原ID其余尺寸分类验收继续保留。

具体专项unittest、默认离线驱动、当前原生/MCP断言见子计划。Windows x64/Python 3.12+；原生适用时本机Creo 12.4.0.0/匹配SDK及许可，实机先满足BUG-001条件并由会话负责人串行安排；Creo 9/10未测保留，WorkBuddy只做公开MCP黑盒。

## 实现与证据

### 2026-11-03 A02 实现（分支 `codex/FEAT-004-dimension-guards`，基线 `88a02dc`）

- **契约**：[P00 接口冻结](../development/ALPHAI-ADOPTION-CONTRACT.md) 的 A02 段。
- **Python**：`src/creo_mechdog/dimension_guards.py`（新）提供 `check_dimension_guard`、`has_guard`、`value_tolerance`；`schema.py::DimensionValue` 增加可选 `expected_value`/`expected_symbol`/`expected_owner`，拒绝布尔、非有限值与空归属，旧 `{id,value}` 载荷行为不变。
- **原生**：`native/generic.cpp` 的 `set_dimensions` 改为两遍——先 `read_dimension_target` 读完每个目标的当前值、符号、关系状态与归属（`ProDimensionValueGet`/`ProDimensionSymbolGet`/`ProDimensionIsReldriven`/`ProDimensionOwnerfeatureGet`），再 `check_dimension_targets` 统一判定，最后才 `ProDimensionValueSet`；任一不符直接抛错，整计划按既有检查点回滚，不出现"批内第二项不符但第一项已写"。尺寸巡检记录新增 `owner_feature_id`/`owner_feature_name`/`owner_query_code`/`editable`（关系查询失败时 `editable=null`，不假装可编辑）。
- **工具描述**：`server.py::creo_set_dimensions` 说明三个可选 pin 与拒绝语义。
- **离线证据**：`tests/unit/test_dimension_guards.py` 17 项（判定 9 项 + schema 5 项 + 原生源码护栏 3 项）全通过；A02 工作树 `tools/dev_check.py --work-item FEAT-004-dimension-guards` → `success=true`、`unit_tests=passed`、无新增风格问题；`bridge.py build` 编译通过（`E:\Projects\codex-A02\build\creo_worker.exe`）。
- **未验证**：实机 Creo 行为（本轮用户授权不连 Creo）——旧值漂移拒绝、归属不匹配拒绝、整批回滚与后续编辑、`owner_feature_*`/`editable` 的实际取值；Creo 9/10；WorkBuddy 黑盒。实机须在满足 BUG-001 条件后由会话负责人串行安排。

## 2026-11-04 跨工作树核验与后续动作

2804d5a/7b3d90e已有守卫代码、17项专项与构建/dev_check记录；本次未重跑或连接Creo。接续R01，先基于0.12.0整合再取当前几何/revision/回滚/保存重载证据，原尺寸分类余项不一并关闭。

详见[核验记录](../development/DEV067-POST0120-AUDIT-2026-11-04.md)和[后续计划](../superpowers/plans/2026-11-04-alphai-post0120-integration-plan.md)。本次只改记录/计划，未修改该任务产品代码或进行新实机。
