# DEV-075 离线验收记录（2026-11-07）

分支：`codex/DEV-075-feedback0181-offline`。基线：`828b1f2` / 0.18.0，验证时dirty=true。下载目录三份报告逐字节归档；历史validation文件不改。变更身份和结果以本文件及`build/dev075/`机器日志为准。

## 环境与范围

Windows x64 / Python3.12.14，Ruff0.17.0、clang-format23.1.3；原生离线组合编译使用本机Creo12.4.0.0匹配Toolkit SDK/MSVC。没有主动远端查询、启动/连接/结束Creo、故障注入或清unknown。最终分发回归`PIP_NO_INDEX=1`，只允许本机缓存wheel；普通工作树首轮单测未全局限制其安装子进程的pip索引，不能据此声称所有子进程均被网络隔离。单元测试的锁/子进程mock不等于真实Toolkit连接。

工作区开始时有用户DEV-054、tools/test_toolkit_recovery.py、tools/test_update_check.py、.trae/与FEAT-014计划。开发期间另有流程修改native/planar_wall.cpp、tools/dev_check.py及多个来源/建模测试驱动、新增旧批次POSTCHECK和来源测试，全部保留，不纳入本批提交。为通过组合样式门禁，仅对其中planar_wall.cpp和test_planar_wall_origin_resize.py运行格式工具，未改其实现逻辑，也未纳入提交。组合编译/全量测试若覆盖它们，仅证明受测工作区组合，不代表本批拥有其实现或已验收原生resize。

最终冻结分发副本基于`6c53ce388509c7f59a82e2240c5be81072c24c59`、dirty=true；14个本批代码文件在commit/工作树/副本之间LF归一化后三方一致（`build/dev075/final-owned-code-identity.json`）。全部468个分发代码文件快照指纹`28e942236b114ac5a50995990990767b8c6ec2b1c378994f73628ed909f1548d`；算法为按路径排序，将每项`路径+NUL+LF归一化文件SHA256+换行`拼接再SHA256，机器清单`distribution-accepted-identity.json`。该算法与原生构建指纹不同。

## 本次验证

| 命令 / 检查 | 结果与证据 |
| --- | --- |
| 校验诊断先复现 | 新增6例最初全部失败，出现tagged-union/input_value；修后通过。公开execute_plan外层另复现输入回显，使用SDK公开call_tool覆盖层保留原schema并净化错误，新增反例RED→GREEN。 |
| 质量字段/装配专项 | 子任务29项通过；新增mass_value_unit冲突反例RED→GREEN。材料失败原因和原生装配拒绝仅静态核对/编译，不记实机通过。 |
| 组合专项 | 最终`last-delta-green.log`166项通过，含标准孔、质量、装配、预算、公开MCP错误和输出崩溃遮蔽；后者先RED后GREEN。完整保留已有plane提示的74项兼容回归通过，打包专项26项通过。 |
| 原生编译 | 首轮`.venv/Scripts/python.exe bridge.py build`退出0，`native-build.log`，本批generic.cpp此后未改。其它流程修改原生resize后两次构建被busy拒绝（`native-build-final.log`/`native-verified-build.log`），未清锁；不能把首次通过冒充最新组合原生重编译。未连接Creo，非几何验收。 |
| 全量Git工作树 | 首轮2869项：5失败、0错误；3条因诊断截短，已修；2条因运行中改源码导致source_changed_since_startup=true。冻结源码后身份48项通过（`source-identity-green.log`），最后全量以独立冻结分发为准。 |
| 无.git / PATH无Git分发 | 显式source_files白名单副本，独立venv复用本机已装依赖目录，通过持久.pth固定导入，不改工作区editable安装。最终`tools/test_unit.py`2878项，0失败/0错误，2项SDK检查跳过；exit0。日志`distribution-accepted-unit.log`、JSON`distribution-accepted-unit-report.json`，耗时531.156秒。原报告T07与本批专项117项已在无Git环境通过（`distribution-targeted.log`）。 |
| 离线安装 / SDK | 保留PowerShell而仅从PATH移除Git，`PIP_NO_INDEX=1`、PIP_FIND_LINKS指向本机缓存setuptools80.9.0 wheel；安装19项通过（`installation-offline-green.log`）。分发无config而跳过的两项LocalSdkContractTests在本机单独2/2通过。 |
| 开发检查 | 最终`dev_check.py --skip-unit --work-item DEV-075` success=true，源码指纹`24a7253d91a4e692c6b5d4104db514f7fabf5c039b273c734b347b0b2297f02e`、dirty=true（6c53ce3）；24条lint/12个未格式化文件为存量基线，未重建。此命令只验样式，单测结果分别记录。 |

早期分发轮次还发现导入路径不持久、PATH误移除PowerShell、离线安装缺setuptools构建wheel及遗漏7件C++夹具；前三项修测试环境，最后一项修打包白名单。失败/中止轮次保留日志，不算通过。缓存wheel SHA256为`062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922`，未下载新依赖；这不是从零安装全部依赖的验收。

## 审查

独立审查发现公开execute_plan外层校验绕过错误映射，已写反例观察失败后修复。SDK原生call_tool流程、typed schema、resolver和其它ToolError行为保持，校验失败仅转换安全文本。审查另指出英寸体积原有null边界，已在FEAT-057卡和接手清单保留，未宣称新增英寸质量支持。

测试中故意失败的打包/安装负例可能输出ERROR字样，结论以unittest汇总、进程实际退出码和JSON报告为准，不按日志是否出现error判成功。报告方“宿主删除守卫干扰全量”的条件未复现，隔离副本不证明已修其宿主限制。

本批没有Creo实机、保存重载、WorkBuddy、真实远端Release/附件验证；余项见[接手清单](DEV-075-HANDOFF.md)。本次不合main、不改版本、不发布。
