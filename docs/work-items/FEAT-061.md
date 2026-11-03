# FEAT-061：装配组件抑制恢复与成对切换

类型：功能。优先级：P2。状态：待规划（派工方案已建，未指派、未实施）。目标版本：未排期。

来源：2026-11-03 用户要求比较 alphai 项目并建立由用户自行派工的计划；静态参考源码不构成当前实机证据。

关联：FEAT-012、FEAT-036、FEAT-052；FEAT-036 的零件生命周期边界不改变。

## 目标与范围

仅受管单层装配，按 occurrence label/feature_id 抑制、恢复，两个 op 表达原子切换；保留标签、源绑定、约束、位姿、appearance；不支持嵌套写入或显示隐藏替代抑制。

明确边界及拟接口见[设计依据](../superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)。本卡固定身份不能被历史反馈中的同号误写引用替代。

## 派工与验收

- 任务号：C01；负责人：unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-c-editing-plan.md)；[主计划](../superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)。
- 判据：同零件两实例只影响指定 occurrence；恢复保持 feature_id；A/B 切换与后项失败回滚、revision/源件 hash、保存重载通过；未知/嵌套/旧 revision 拒绝。
- 开发环境：Windows x64 / Python 3.12+；原生适用时 Creo 12.4.0.0 / 匹配 SDK/许可，先满足 BUG-001 条件并由会话负责人串行安排。Creo 9/10 未测不能外推。
- 对应专项 unittest、默认离线驱动、构建、实机命令与错误/恢复矩阵见子计划；所有 live 驱动默认离线。WorkBuddy 如安排则只做公开 MCP 黑盒，不替代内部验证。

## 实现与证据

2026-11-03 仅登记和规划；未修改产品代码，未运行产品测试、未连接 Creo、未提交/合入 main/发布。执行者按主计划交接实际提交、dirty、受测源码指纹、命令、环境、结果和未测范围；完成后由集成人同步主台账、能力边界与发布记录。

