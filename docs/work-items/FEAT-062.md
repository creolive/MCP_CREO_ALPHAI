# FEAT-062：独立受管模型重命名与副本派生

类型：功能。优先级：P2。状态：待规划（派工方案已建，未指派、未实施）。目标版本：未排期。

来源：2026-11-03 用户要求比较 alphai 项目并建立由用户自行派工的计划；静态参考源码不构成当前实机证据。

关联：FEAT-018、FEAT-048、FEAT-059 共享事务（按需）；装配联合改名、气弹簧限位改型不在首版。

## 目标与范围

首版独立无依赖 part/sheetmetal；rename 保留 model_id/revision+1，derive 新 model_id/revision=1 且源件字节不变；统一会话/磁盘/登记名称冲突检查和检查点恢复。

明确边界及拟接口见[设计依据](../superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)。本卡固定身份不能被历史反馈中的同号误写引用替代。

## 派工与验收

- 任务号：C04；负责人：unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-c-editing-plan.md)；[主计划](../superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)。
- 判据：改名后继续编辑/重载；派生改尺寸几何正确且原 revision/hash 不变；冲突/依赖/非法名称拒绝；保存或登记失败不得发布半成品，恢复需读回或保持 unknown。
- 开发环境：Windows x64 / Python 3.12+；原生适用时 Creo 12.4.0.0 / 匹配 SDK/许可，先满足 BUG-001 条件并由会话负责人串行安排。Creo 9/10 未测不能外推。
- 对应专项 unittest、默认离线驱动、构建、实机命令与错误/恢复矩阵见子计划；所有 live 驱动默认离线。WorkBuddy 如安排则只做公开 MCP 黑盒，不替代内部验证。

## 实现与证据

2026-11-03 仅登记和规划；未修改产品代码，未运行产品测试、未连接 Creo、未提交/合入 main/发布。执行者按主计划交接实际提交、dirty、受测源码指纹、命令、环境、结果和未测范围；完成后由集成人同步主台账、能力边界与发布记录。

