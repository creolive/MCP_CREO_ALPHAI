# MCP_CREO_MechDog 0.12.1 版本说明

2026-11-04，PATCH；条目：[DEV-068](work-items/DEV-068.md)。

README 改为面向使用者的项目介绍：徽章、项目定位、环境与安装、圆柱建模示例、功能表、文档导航、已知限制和许可证。详细版本历史与验收记录通过 docs 和 Releases 查阅。

- 保留用户确认的改版结构，对齐主干的 **97 个工具**，补上 `creo_sheetmetal_planar_wall` 与 `creo_resize_sheetmetal_planar_wall` 导航。
- 快速开始明确调用 `creo_execute_plan`；尺寸修改示例列出模型、revision、草图与尺寸名。保留毫米/度、忙碌立即拒绝、已接受任务只轮询和修改前核对 revision 的约定。
- GitHub CI 在全量检查前从样例生成离线配置并关闭自动启动 Creo，修复主干原有的两项缺配置测试报错；不更改测试断言或运行时代码。
- 版本入口、两份种子清单及受信摘要同步至 **0.12.1**。工具、参数语义、Python/C++ 业务实现与种子 PRT 字节均未改变。

验证命令为 `python tools/dev_check.py`，另检查 README 链接、JSON/计划输入、工具清单与版本、源码分发白名单、种子重建及四附件校验。结果与受测源码身份见[发布记录](validation/RELEASE-0.12.1.md)和本次 PR 的主干交付核对。

本版为文档与版本元数据补丁，未连接 Toolkit，未进行本轮 Creo 原生建模、安装建模或 WorkBuddy 黑盒验收。Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测。0.12.0 的实机结果保留原版本归属，不作为本版测试数。BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.12.1-source.zip` 与 `MCP_CREO_MechDog-0.12.1-seed-library.zip`，按安装说明更新环境并重启 MCP 服务。旧种子包会被版本闸门拒绝；本版无新增原生编译要求、回调注册变化或参数迁移。
