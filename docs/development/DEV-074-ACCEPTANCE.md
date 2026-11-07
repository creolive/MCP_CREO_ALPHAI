# DEV-074 离线验收记录（2026-11-07）

分支：`codex/DEV-074-feedback0174-offline`。受测基线提交：`8d71e6c0d1c04352fa959e4e0437c311f54fe5c7`，dirty=true；测试覆盖的是本次工作区源码，不能仅用基线提交代表。服务版本保持0.18.0。

## 身份、环境与证据

- Windows x64 / Python3.12.14；开发检查工具Ruff0.17.0、clang-format23.1.3。原生编译使用本机Creo12.4.0.0匹配ToolkitSDK/MSVC，未启动或连接Creo。
- 最终 `dev_check.py --skip-unit` 源码指纹：`7602302e1f59e22108bc9be4aba2f8dd5c7beca7995e0e2be83f3892ede9c8a8`。Git工作树2850项全量门禁的指纹为`030b7905014908b983d63fefc58d8db95187374a4f010b9712424b9abbac9cde`，其后仅折叠三点定面/生命周期两个开发来源入口，18项定向通过，再以最终源码运行无Git全量。机器记录：`build/dev074/development_check.json`、`style-check-final.json`、`unit_test_report.json`、`final-all-dev-check.log`。
- 验证前发现本仓库`.venv`的editable导入指向另一目录`C:\i0182_pkg\...`。使用本机pip缓存中的setuptools80.9.0 wheel（未下载新依赖）完成`pip install --no-deps --no-build-isolation -e .`，确认包导入来自本仓库后重新验收。此前结果不作为本次最终源码证据。
- 四份反馈原件长度/SHA256/字节序列4/4一致，见[归档清单](../validation/feedback-0.17.4-2026-11-07/manifest.json)。旧`docs/validation/`跟踪文件无修改。

## 验证

| 命令 / 检查 | 本次结果 |
| --- | --- |
| `.venv\Scripts\python.exe tools/dev_check.py --work-item DEV-074` | exit0，success=true；2850项、0失败、0错误。24条lint/12个未格式化文件为存量，没有修改基线。 |
| `.venv\Scripts\python.exe bridge.py build` | exit0，最新原生候选诊断/预览依据/尺寸日志组合编译通过；日志`build/dev074/final-native-build.log`。 |
| 来源入口定向回归 | 先前四入口123项、后续23入口与新增命中模块73项通过，再补25入口与生命周期18项通过；缺Git/无仓库降级、离线oracle、单个live标志不连接和报告覆盖保护。 |
| 当前板厚/预览/阶段/候选定向回归 | 77项通过，后续有效厚度反例与正例、格式化后断言14项通过；均被最终2850项覆盖。 |
| 独立短路径分发目录，无`.git`且PATH无Git | exit0，2850项、0失败、0错误、2项本地SDK检查跳过（分发目录无本机配置）。PIP_NO_INDEX=1，只允许本机缓存setuptools wheel；包路径`C:/d074_b3aa94/src/creo_mechdog`，464个源码文件与最终工作树归一化后全一致。日志`build/dev074/distribution-clean-tests.log`，报告`distribution-unit-report.json`，身份`distribution-code-identity.json`。 |
| 最终样式门禁 | `dev_check.py --skip-unit --work-item DEV-074` exit0、success=true；401个Python/45个C++文件检查，存量基线未改。 |
| 差异与原件检查 | `git diff --check`通过；Git暂存区中4份原件哈希与manifest一致；未修改用户原有DEV-054、`.trae`或FEAT-014计划，不纳入提交。 |

最初一轮工作树全量有1项格式敏感的旧源码断言失败，修正为不依赖clang-format换行后重跑2850项全部通过。分发目录初轮暴露其它同形Git来源入口，已将25个来源函数接入公共模块并保留各自额外文件列表；长临时目录造成Windows文件名过长、独立环境未加载pywin32路径、临时安装缺离线build依赖分别修正测试环境。最终只以表中最后一轮结果为准，不用中断或失败轮次冒充通过。

## 审查与范围限制

独立审查代理因额度不足未完成，最终为主代理逐文件自审。自审发现有效板厚布尔只看status、未核对请求厚度的问题，新增反例观察失败后修复，并覆盖当前/loaded上下文和正确厚度正例。结构化候选由原生失败结果产生，保护证据和compact路径保留，不解析报错字符串。

没有真实Creo/MCP建模实机、保存重载、WorkBuddy、真实远端附件/API下载结论。非零origin大跨度resize仍未修复，不能因新增日志或编译通过标为完成；其余13类接手任务见[清单](DEV-074-HANDOFF.md)。本次不合main、不改版本、不发布。
