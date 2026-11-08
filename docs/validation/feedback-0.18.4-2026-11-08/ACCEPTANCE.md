# DEV-076：0.18.4三件反馈合并验收

日期：2026-11-08。分支`codex/DEV-075-feedback0181-offline`。[工作卡](../../work-items/DEV-076.md)、[逐项映射](MAPPING.md)、[未完成清单](../../development/DEV-075-HANDOFF.md)。本轮仅合入当前开发分支，不改main、标签或Release；没有连接/启停Creo、Creo/Toolkit故障注入或清unknown。

## 身份与范围

- 起点8583566（较旧0.18.0基线），52aca5e合入本地v0.18.4 / 04927a99a9b8e2ac2a572b11ac9be66ea3f9f391；8cb2434补归档patch分发；95d52c95894e43ef0494fceeb8d1c3a58d2332d7修文案契约。
- 最终受测提交95d52c9，dirty=true（用户文档、未跟踪本地内容与文档收尾）；源码版本0.18.4继承基线，新增修复尚未发布。后续收尾只改文档/JSON，没有改受测代码。
- 489个分发代码文件（py/cpp/h/hpp），规范化CRLF为LF；按路径排序，每项`path + NUL + file_sha256 + LF`再做SHA256（sha256-path-lf-filehash-v1）：`33254791ad55214dbd865e53eced227e15c1e626cca474d20a95bd913272168b`。运行结束及收尾前均核对未变。
- 无Git分发目录`C:\d076_e1a293`由`tools.package.source_files()`复制1590件，含3份原件和所有native测试夹具；没有.git/config.json。此为源码清单独立分发回归，不声称生成或发布了官方ZIP。包内版本与模块导入均来自该独立目录，依赖从已安装venv复用；PIP_NO_INDEX=1、缓存setuptools80.9.0，PATH移除Git且保留PowerShell。
- Python3.12.14 / Windows x64；本机Creo12.4.0.0 SDK仅用于编译。身份明细见[SOURCE-IDENTITY](SOURCE-IDENTITY.json)，不同采集器指纹范围分别标注，不能直接互换。

## 最终结果

| 验证 | 命令/方法 | 本轮结果 |
| --- | --- | --- |
| 工作区完整开发检查 | `python tools/dev_check.py --work-item DEV-076 --unit-timeout-seconds 1800`，PIP_NO_INDEX=1 | success=true；2976项、0失败/0错误、0跳过，501.109s |
| 无Git分发全量 | 独立venv执行`python tools/test_unit.py`，无.git、PATH无Git、禁pip索引 | 2976项、0失败/0错误、4跳过，436.422s，exit0 |
| 样式 | 上述开发检查，基线未扩充 | 21 lint、10未格式化均存量，无新增诊断；Ruff0.17.0、clang-format23.1.3 |
| 当前SDK组合编译 | `python bridge.py build` | exit0；8cb2434+dirty构建（native源码与95d52c9一致）；worker 13907968 B，SHA256 `4538e7b8250a95b86c43f466db0924c01fd6c6b0ffb94c788e41a90e53ac1459` |
| 自动缺头分支/独立包导入/SDK契约等 | test_optional_loft_header、test_tool_package_imports、test_gated_headers、test_surface_loft_schema、test_source_provenance_entrypoints | 28项通过；缺头夹具不加SDK路径、包含生产单元、自动检测并编译执行明确拒绝，不调用Toolkit |
| 来源与预览组合 | test_merged_provenance、test_t07_provenance、test_source_provenance_drivers、test_t07_preview | 73项通过 |
| 归档与打包清单 | test_release_integrity | 27项通过；三份原件manifest成员全部在源码清单且SHA256匹配 |
| 安装离线专项 | test_installer_native_failure_leaves_client_config_and_resume_instructions，PIP_NO_INDEX=1 | 1项通过，23.472s |
| 文案修复专项 | test_sheetmetal_solid_add_admission、test_merged_provenance | 6项通过 |

机器记录：[ROOT-UNIT](ROOT-UNIT-REPORT.json)、[DISTRIBUTION-UNIT](DISTRIBUTION-UNIT-REPORT.json)、[DEVELOPMENT-CHECK](DEVELOPMENT-CHECK.json)。原始日志保存在本机被忽略的build/feedback0184_20261108，不提交二进制、SDK、配置或日志。

## 红绿过程与复验

缺头C1083和三个裸名导入均先用新回归复现，再修复。合并的8个来源入口先复现绕过共同采集器/缺失源码无诊断，再统一到source_provenance，兼容旧aliases；归档patch遗漏先失败后补白名单。

第一轮工作区/无Git分发均运行2976项，各1失败0错误：钣金诊断从“Creo 10 is untested”变成“Creo 10 fusion is untested”，与原契约不一致。95d52c9恢复兼容短语并补上下文，保留新Creo12反证及thin/revolve归属未验证边界；专项6项通过后，重新冻结并重跑上述两轮完整检查，均通过。第一轮日志/JSON以first-前缀保留，没有当作成功证据。首次专项还误写不存在的test_multibody_contract模块，已纠正测试选择，该加载错误不算产品缺陷。

无Git跳过项如下；前3项均在工作区完整检查中实际通过；最后一项仅适用于Git仓库，缺Git降级由其他用例验证：

- `test_generated_constants_only_include_present_headers (unit.test_gated_headers.LocalSdkContractTests.test_generated_constants_only_include_present_headers)`：no local config.json
- `test_local_sdk_present_and_missing_sets_are_disjoint (unit.test_gated_headers.LocalSdkContractTests.test_local_sdk_present_and_missing_sets_are_disjoint)`：no local config.json
- `test_missing_header_branch_compiles_and_refuses_the_operation (unit.test_optional_loft_header.OptionalLoftHeaderTests.test_missing_header_branch_compiles_and_refuses_the_operation)`：local Windows compiler configuration not available
- `test_provenance_keeps_git_facts_in_a_checkout (unit.test_t07_preview.DriverCoverage.test_provenance_keeps_git_facts_in_a_checkout)`：git unavailable; the degradation case covers this environment

## 审查、保护与取舍

唯一独立审查由fresh-context gpt-6-astra执行，只读对照v0.18.4..HEAD及8583566..HEAD，未发现可行动Bug；末尾文案失败由完整回归发现，按红绿修复并用两轮全量复验，没有重复派审查。

合并前已有的全部docs/validation Git blob未变；从标签新增的历史原件保持标签字节。3份归档工作区及Git索引与Downloads原件逐字节一致。session_activity.json仍为1876 B / SHA256 c02fbf5404f6c7839fa51136f3d5a63e7ed903ef66822060829899661a5edcf6，继续不跟踪。

开始时用户文档和FEAT014计划已备份，并定向stash后恢复：有冲突处保留新版已交付结论及已有用户新增内容，已被标签包含的同义改动不重复追加。DEV054/066原dirty内容、未跟踪计划和.trae保留；备份build/feedback0184_20261108/pre-merge-user-files及stash“DEV-075 pre-0.18.4 user documents”仍保留，未删除。DEV074的最终差异仅为本轮纠正H09/H10状态。

执行决定及代价：

- 合并本地v0.18.4补齐旧基线缺失模块；代价是整合范围扩大，已用完整回归覆盖可离线部分。
- 历史validation保留，以新勘误/统一索引补状态；代价是旧模板仍可见，需沿链接读取当前说明。
- 八个旧驱动保留provenance_mode/git_unavailable及空commit/branch aliases，内部统一完整性采集；代价是旧aliases仍为空字符串，不能与新null字段混同。
- 资料所称17处待填未完全重现，按本地标签真实剩余占位记录；代价是报告与包/tag来源差异仍需外部核对。
- 实机/远端事项按本轮离线和禁止Toolkit连接范围交接；代价是这些平台行为尚未由本轮验证。

## 未完成

Creo9/10真实SDK完整构建、缺头SDK公开MCP明确拒绝、正常SDK放样几何/保存重载、WorkBuddy重启后黑盒，以及0.18.3/4远端四附件/body/main/真实后核对时间，均未在本轮验证。H10—H12及原H02—H09余项见[DEV-075-HANDOFF](../../development/DEV-075-HANDOFF.md)。本轮不把既有Creo12历史证据、报告方Creo10结果或本地编译外推为运行时通过。
