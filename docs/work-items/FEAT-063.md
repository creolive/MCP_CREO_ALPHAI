# FEAT-063：版本化产品规则与只读改型计划

类型：功能。优先级：P2。状态：开发中：离线内核已交付，MCP接入/实机待验。目标版本：未排期。

来源：2026-11-03 用户要求比较 alphai 项目并建立由用户自行派工的计划；静态参考源码不构成当前实机证据。

关联：现有种子/UDF/execute_plan；不包含壁挂14步完整自动化或气弹簧力学/运动仿真。

## 目标与范围

仓库自带脱敏箱体/机架模板、参数范围/单位/版本摘要到现有 execute_plan 的纯转换；只读不连接 Toolkit、不提交作业，不接受任意路径/脚本或任意表达式。

明确边界及拟接口见[设计依据](../superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)。本卡固定身份不能被历史反馈中的同号误写引用替代。

## 派工与验收

- 任务号：D02；负责人：unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-d-workflow-plan.md)；[主计划](../superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)。
- 判据：同输入确定性输出；非法参数/模板/能力缺失明确拒绝或 blocked；生成计划通过现有 schema，附独立几何判据；没有实机执行证据只交付规划器，不宣称模板建模已通过。
- 开发环境：Windows x64 / Python 3.12+；原生适用时 Creo 12.4.0.0 / 匹配 SDK/许可，先满足 BUG-001 条件并由会话负责人串行安排。Creo 9/10 未测不能外推。
- 对应专项 unittest、默认离线驱动、构建、实机命令与错误/恢复矩阵见子计划；所有 live 驱动默认离线。WorkBuddy 如安排则只做公开 MCP 黑盒，不替代内部验证。

## 实现与证据

2026-11-03 仅登记和规划；未修改产品代码，未运行产品测试、未连接 Creo、未提交/合入 main/发布。执行者按主计划交接实际提交、dirty、受测源码指纹、命令、环境、结果和未测范围；完成后由集成人同步主台账、能力边界与发布记录。


## 2026-11-04 D02 离线内核增量

本阶段负责人：codex/FEAT-063-offline-product-rules 独立任务；只实现 box_frame 固定配方、
四个毫米参数、版本/原始字节摘要、现有 schema 校验、快照准入与完整 JSON 预算。
目标版本仍未排期；未注册 MCP 工具，不连接 Creo，不提交作业。

基线 main@90dbd6c33e9f732d1a5bd969bcf19d30b4b3a62c（已发布 0.12.0）。
验收范围：专项 unittest、离线 driver 两组解析体积与拒绝/阻断、Ruff、整仓离线 dev_check。
环境：Windows x64、独立工作树 .venv。详细结果见
[D02 本阶段验收记录](../development/ALPHAI-D02-ACCEPTANCE.md)。
后续由集成人登记公共工具/源码身份、资源分发和部署清单，并取得 Creo 保存重载证据。
上文 2026-11-03 记录保留历史含义，不把解析预期外推为实机通过。
