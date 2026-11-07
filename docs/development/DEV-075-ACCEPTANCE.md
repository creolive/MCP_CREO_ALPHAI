# DEV-075 离线验收记录（2026-11-07）

分支：`codex/DEV-075-feedback0181-offline`。基线：`828b1f2` / 0.18.0，验证时dirty=true。下载目录三份报告逐字节归档；历史validation文件不改。变更身份和结果以本文件及`build/dev075/`机器日志为准。

## 环境与范围

Windows x64 / Python3.12.14，Ruff0.17.0、clang-format23.1.3；原生离线组合编译使用本机Creo12.4.0.0匹配Toolkit SDK/MSVC。没有联网、启动/连接/结束Creo、故障注入或清unknown。单元测试的锁/子进程mock不等于真实Toolkit连接。

工作区开始时有用户DEV-054、tools/test_toolkit_recovery.py、tools/test_update_check.py、.trae/与FEAT-014计划。开发期间另有流程修改native/planar_wall.cpp、tools/dev_check.py及多个来源/建模测试驱动、新增旧批次POSTCHECK和来源测试，全部保留，不纳入本批提交。组合编译/全量测试若覆盖它们，仅证明受测工作区组合，不代表本批拥有其实现或已验收原生resize。

## 本次验证

| 命令 / 检查 | 结果与证据 |
| --- | --- |
| 校验诊断先复现 | 新增6例最初全部失败，出现tagged-union/input_value；修后通过。公开execute_plan外层另复现输入回显，使用SDK公开call_tool覆盖层保留原schema并净化错误，新增反例RED→GREEN。 |
| 质量字段/装配专项 | 子任务29项通过；新增mass_value_unit冲突反例RED→GREEN。材料失败原因和原生装配拒绝仅静态核对/编译，不记实机通过。 |
| 组合专项 | `build/dev075/targeted.log` 54项通过；外层修复后`mcp-validation-green.log` 55项通过，覆盖已有装配/预算错误不被新适配器改变。 |
| 原生编译 | `.venv/Scripts/python.exe bridge.py build`退出0，`build/dev075/native-build.log`；未连接Creo，非几何验收。 |
| 全量Git工作树 | 运行中，最终结果待补。 |
| 无.git / PATH无Git分发 | `tools/package.py:source_files`显式白名单复制到独立短路径，包导入和`git: None`已确认；全量运行中，最终结果待补。未修改editable安装或下载依赖。 |
| 开发检查 | 首轮捕获本批schema导入顺序（已修）和其它流程未格式化的planar_wall.cpp；最终门禁待补。未重建风格基线。 |

## 审查

独立审查发现公开execute_plan外层校验绕过错误映射，已写反例观察失败后修复。SDK原生call_tool流程、typed schema、resolver和其它ToolError行为保持，校验失败仅转换安全文本。审查另指出英寸体积原有null边界，已在FEAT-057卡和接手清单保留，未宣称新增英寸质量支持。

本批没有Creo实机、保存重载、WorkBuddy、真实远端Release/附件验证；余项见[接手清单](DEV-075-HANDOFF.md)。本次不合main、不改版本、不发布。
