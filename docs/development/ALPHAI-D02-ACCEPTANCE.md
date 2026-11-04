# ALPHAI D02 / FEAT-063 本阶段离线验收（2026-11-04）

交付范围为固定 box_frame 规则内核，状态：开发中：离线内核已交付，MCP接入/实机待验。
没有新增 MCP 工具，也没有原生执行或保存重载结果。

## 源码与环境身份

测试时 HEAD=90dbd6c33e9f732d1a5bd969bcf19d30b4b3a62c（已发布 0.12.0），
分支 codex/FEAT-063-offline-product-rules；dirty=true（本次实现与初始计划；验收文档在检查后补齐）。
测试源码以原始字节 SHA256 标识，不把基线提交冒充已包含本次实现的提交。
最终提交与基线范围由同工作树忽略的 task-1-report.md 记录；提交后不改 Python/模板。

工作树根目录：`C:\Users\Administrator\.codex\worktrees\feat063-product-rules\MCP_CREO_MechDog`。
解释器：该根目录下 `.venv\Scripts\python.exe`（Python 3.12.14、Windows 11 x64）。
包导入为该根目录下 `src\creo_mechdog\__init__.py`，实现为
`src\creo_mechdog\product_rules.py`；SOURCE_PATHS.resource_root 等于本工作树根目录。
完整绝对路径证据保存在下述 import_roots.json；没有从其他 checkout 导入本包。

## 原始证据与命令

所有下列路径相对于本工作树根目录，原始证据持久保存在忽略目录
`build/feat063_offline_product_rules_20261104/`，没有放在临时 SDD 工作空间。
表内 python 均指上述本工作树解释器。

| 命令/检查 | 结果 | 原始证据 |
| --- | --- | --- |
| `python -m unittest tests.unit.test_product_rules -v`（实现前） | RED：缺少 product_rules 的 ImportError，1 个模块加载错误 | red.log |
| 同一专项命令（实现后） | GREEN：9 项通过，0 失败/错误 | green.log |
| `python tools/test_adoption_product_rules.py --output build/feat063_offline_product_rules_20261104/driver` | exit 0；4 个离线场景通过 | driver.log、driver/report.json |
| `python tools/test_adoption_product_rules.py` | exit 0；默认唯一 build 子目录报告通过 | driver_default.log（含实际路径） |
| `python tools/test_adoption_product_rules.py --live --output build/feat063_offline_product_rules_20261104/should_not_exist` | exit 2；argparse 拒绝，输出目录未创建 | driver_live_rejected.log、driver_live_rejected_exit.txt |
| `python -m ruff check src/creo_mechdog/product_rules.py tests/unit/test_product_rules.py tools/test_adoption_product_rules.py` | exit 0，All checks passed | ruff_check.log |
| `python -m ruff format --check` 加同三文件 | exit 0，3 files already formatted | ruff_format.log |
| `python tools/dev_check.py --work-item FEAT-063-offline-product-rules` | exit 1；语言回归闸门通过，2295 单测中 3 errors、0 failures、2 skipped | dev_check.log、dev_check_exit.txt、development_check.json |
| 作者范围/契约自查 | 未发现需修改问题；独立审查交控制者 | self_review.md |

## 受测源码指纹

driver/report.json 的 source_sha256 包含六个相关文件（schema/paths 只读消费）：

| 文件 | 原始字节 SHA256 |
| --- | --- |
| src/creo_mechdog/product_rules.py | 2f119705bc67d143671aa448ecf570ddcaacf18919c1ef6b09fa3c195765343a |
| examples/product_rules/box_frame.json | cbc3f10e13aef0d33b92a3e3aa2e400a0b654f6da60dec52a7d8f53a63549c5d |
| tests/unit/test_product_rules.py | 967947b3c5a07276a9687bbe8d8ab4715a9dd7db5246c8f7e5b12112472adaa6 |
| tools/test_adoption_product_rules.py | cb5f37c5cf4486af4234e510332c6a07f67a237f156d5e1ec3b909fd05b100c0 |
| src/creo_mechdog/schema.py | dbd66fccf6b648b63617ad5587bc12bc1c96dcd294f297c5f089f4017a251aef |
| src/creo_mechdog/paths.py | 389dca158e3a7d02337ca3a099a1872bf858e38cc8108d78172cff235256dff5 |

## 判据与未测范围

专项覆盖默认和 120×80×50/t3 两组尺寸；以独立底板+四壁分解式确认解析体积
35712/83508 mm³。覆盖既有 schema、固定方向/offset、闭区间/退化、未知 ID/路径逃逸/参数、
bool/非有限/巨大整数、资源错误/模板声明、能力未知/缺失/格式错误、确定性和输入/返回隔离、
完整 UTF-8 32KiB 预算以及无写盘/进程/网络的核心行为。

预期包络/体积均为解析预期；schema=passed，native=not_run，saved_reload=not_run。
未连接真实 Creo/Toolkit 开发服务，未运行 native 编译、live driver、WorkBuddy 黑盒、Creo 9/10/12 实机或部署/打包。
整仓单测包含隔离 MCP stdio fixture（原生入口替换/禁止），不构成真实服务或 Creo 黑盒验收。
未修改公共源码身份/能力登记/桥接层。后续集成人需登记 MCP 工具、核资源分发白名单及部署清单，
明确快照适配来源，并安排原生执行、几何回读和保存重载；当前 executable 仅表示离线准入。
未推送、合入 main 或发布。

## 整仓检查实际限制

完整 dev_check 只运行一次，未通过；不能以专项绿色或语言闸门通过替代该结果。
整仓受测源码聚合指纹 checked_source_sha256=
3e5b0ec60c4f3820d743d4ced203a42b9e7ad3f60cb2741ac41c6502449c3aff。
语言存量统计为 24 lint findings、13 unformatted files（现有基线容许，无新增回归）；
检查 331 Python 和 36 C++ 文件，Ruff 0.17.0、clang-format 23.1.3。
单测实际运行 2295 项，耗时 300.750 秒，0 failures / 3 errors / 2 skipped：

- test_job_stage_reporting.JobStageReporting.test_running_job_reports_substage_progress：
  bridge.config() 抛 Missing config.json。
- test_model_naming.SubmitAdmissionNameRule.test_digit_first_name_passes_admission：
  bridge.config() 抛 Missing config.json。
- test_dev040_blackbox_fixture.FixtureProtocol.test_rejection_unknown_success_idempotency_and_audit_over_stdio：
  reconcile fixture 返回 Errno 2，reconciliation/evidence-*.json.*.tmp 路径不存在；
  实际完整路径保留在 dev_check.log。长工作树路径可能相关，原因未确认，不声明为既有已证明缺陷。

两项跳过明确为 no local config.json 的 SDK 契约。未复制/编造 config、常量或 SDK，
未修其他模块/测试、未调整基线，未再次执行整仓检查或另跑 test_unit 冒充成功。
unit_test_report.json 和 development_check.json 原件均已复制到上述持久证据目录。
日志中的 seed archive 摘要拒绝来自单元测试场景输出，实际失败项以上述三个 error 为准。

聚焦只读诊断：DEV-040 报错临时路径长度为 264 字符（文件名 83 字符，正式目标路径 227 字符），
超过传统 Windows MAX_PATH。调用链为 rec.inspect → _directory.mkdir → bridge.write_json → temp.open('x')。
该路径长度是已确认事实；Windows 长路径处理是否为此 Errno 2 根因仍未独立证明。
fixture/test/reconciliation/bridge/generic_bridge/server 均无 product_rules 引用，D02 未注册且无调用关系。
未重跑单例：原始异常及只读调用链已足够区分确定事实和未定原因。
证据 dev040_diagnosis.json、dev040_call_relation.txt 保留在同目录。
