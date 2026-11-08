# DEV-066 新报告离线补步验收（2026-11-08）

分支`codex/DEV-075-feedback0181-offline`，本批代码`8def1e4`，版本仍0.18.0，未合main/发布。报告原文和对照见[归档](../validation/feedback-dev066-0.18.1-2026-11-07/MAPPING.md)。

## 对比与来源

现有公共helper及25入口先复用。恢复/审查冻结副本中17处来源迁移，保留不同工具的原报告字段；独立审查指出3个`source_commit`消费键错误和7个适配器证据丢失，均新增反例观察失败后修复。额外缺失源文件明确incomplete，不能把部分哈希冒充完整源码指纹。

当前tools中43个文件直接导入共同helper（含新增test_unit），没有直接Git进程调用；报告旧43文件数字是其版本的字面匹配口径，不外推“旧版43硬依赖均属同形”。冻结历史`docs/validation/.../g0_driver.py`不改。目录模式complete仅表示发现的文件集合可读，不证明官方包文件齐全。

## 本次验证

- Windows x64 / Python3.12.14，Ruff0.17.0、clang-format23.1.3；无原生修改，不需要本批重编译。不连接Creo/Toolkit，不做故障注入，不查询远端。
- RED→GREEN：来源迁移6例最初1 failure/16 errors后通过；报告/缺文件3 errors后通过；可选Git环境诊断KeyError后通过；审查入口/证据4 errors后全部通过。最后定向51项0失败/0错误（final-targeted.log），含本机两项SDK检查。
- `tools/dev_check.py --skip-unit --work-item DEV-066` success=true；23 lint/11个格式欠账为存量，未重建基线；具体源码指纹见机器报告development_check.json。本命令仅样式，单测另记。
- 取消session_activity跟踪前后1876 bytes完全一致，SHA256 `c02fbf5404f6c7839fa51136f3d5a63e7ed903ef66822060829899661a5edcf6`；文件仍在本机原路径且ignore命中，旧历史不改。此处不是一次真实升级演练。
- 默认离线`tools/test_arc_direction.py --output .../report.json`：无Git/无.git，exit0、29项通过，报告与sidecar生成。`test_update_check`网络更新流程没有运行，来源构建已离线测试。
- 最终冻结分发`tools/test_unit.py`：2884项，0失败/0错误、2项SDK跳过，exit0。机器报告直接列出两项跳过原因和duration_seconds=358.797；无Git身份commit/branch/dirty全为null，source_scope=distributed_source、source_status=complete，453个发现范围内源文件、source_errors=[]；目录源码指纹`1392198e45b840f822254ca847d9bc0204ca8747fd1879da5e56fd9d9fa9ee32`。完整日志无裸`ERROR:`行（accepted-checks.json）。

## 冻结环境与范围

使用package.source_files白名单副本、独立venv，通过本地pth复用既装依赖并固定导入该副本。PATH只移除Git，保留PowerShell；PIP_NO_INDEX=1、本机缓存setuptools80.9.0 wheel，无下载。无.git、无本机config.json；跳过项和耗时以新unit_test_report字段直接记录。源码清单、目录、指纹在`build/dev066_20261108/frozen-identity.json`；该副本不是从零安装全部依赖的验证。

冻结目录`C:/d066_a8501d`，全部470个分发代码文件快照指纹`b6f919191242d2a20ca663bb75c214db48e8095df118f1ac3ece2ab936e6b10a`（路径排序，拼接路径+NUL+LF归一化文件SHA256+换行后SHA256）。该快照覆盖C++测试夹具等额外文件，算法/范围不同于单测报告公共helper指纹。28个本批代码文件在8def1e4提交/当前工作树/副本之间LF归一化后三方一致。样式受测8def1e4、dirty=true，checked_source_sha256=`650ca2c19ff960c6baf70571ee78490947314c277f86a2230d3123272883e180`。工作区其它DEV-054/DEV-074/FEAT-058文档及.trae/、FEAT-014计划仍保留，不随本批提交。DEV-066工作卡只将本批新增段落/状态登记入提交，既有用户未提交段落保留。没有实机、WorkBuddy、真实远端或跨版本升级通过结论，见[接手清单](DEV-075-HANDOFF.md)。
