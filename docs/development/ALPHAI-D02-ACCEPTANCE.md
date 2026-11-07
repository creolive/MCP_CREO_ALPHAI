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


## 2026-11-06 公共接入增量

当前状态：只读规划器软件已完成，开发分支未发布，原生模板未验。
新增 READ 工具 creo_plan_product_variant；工具总数 100→101，原生操作数量不变。
能力只取当前服务 REGISTERED_OPERATIONS 减 UNAVAILABLE_OPERATIONS；不查询运行时。
接口参数保留 dict[str, Any]，避免在内核之前把 bool/字符串尺寸转成合法数字。
实现与固定 JSON 纳入 server 的源码身份；现有源码递归分发白名单无需修改。
回归复制 source_files 中源码到独立短临时目录，在子进程中从副本导入并运行默认规划，
resource_root 确认指向副本；这证明源码资源可独立定位，不等同全新机器安装或 native 验收。

tests.unit.test_product_rules_mcp 经 MCPServer.call_tool 验成功与拒绝。
本机 MCP SDK 的直接 call_tool 遇非法输入抛 ToolError；真实 wire handler 才返回 isError，
回归分别验证二者，沿用已有服务错误契约。SDK 忽略额外顶层参数，缺 extrude 时即使
客户端额外自报完整能力仍 blocked，不会被客户端声明解除。

本次仅在 FEAT-063 工作树与其 .venv 运行；独立分发测试使用系统临时夹具并清理。
未修改 DEV-069 工作树/服务/配置，没有启动真实服务生命周期、连接 Creo/Toolkit、
编译 native、复制 SDK/config/constants、推送、合入 main 或发布。版本保持 0.16.0。
测试时 HEAD=64db947fa738cdac73082860ea8545a1223b1113，dirty=true（本次待提交实现）。
环境 Python 3.12.14 / Windows-11-10.0.26100-SP0；Ruff 0.17.0 / clang-format 23.1.3。
证据目录 build/feat063_completion_20261106，以下 python 均为本工作树 .venv 解释器。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 新增 MCP/分发/driver 回归（实现前） | RED，8 tests；3 failures、12 errors，未注册/身份遗漏与报告覆盖风险 | red.log |
| planner/MCP/driver/能力/身份/数量回归（最终） | GREEN，71 tests，0 failures/errors | green_final.log |
| Ruff check/format 改动 Python | 通过；最终冻结源码由 dev_check 再验证 | ruff_check_final.log、ruff_format_final.log |
| driver --output build/feat063_completion_20261106/driver_final | exit 0，四场景通过；含版本/时间/平台/Git/11文件指纹 | driver_final.log、driver_final/report.json |
| driver --live | exit 2，拒绝未知参数；未创建 should_not_exist 目录 | live_rejected.log、live_rejected_exit.txt |

报告使用 x 模式独占创建；回归验证已有 report.json 原字节保留，run_checks 禁止外部进程。
首轮 dev_check 因改动 PRODUCT_RULES.md 的旧 Python 围栏需格式化而在单元前失败；
格式化后第二轮发现第四处旧 100 工具断言（test_callback_admission），并因需要冻结最终
描述/副本测试调整而终止本树单测子进程。dev_check.log、dev_check_retry.log 和相应 JSON
保留原件；它们不作为通过证据。最终轮在冻结 Python/JSON 上独立运行。

### 本次受测原始字节指纹

- server.py: `1f3e38d3a03d71621f000f1378e8a8cc176fcd5f5a87321c300c10daf7ab0195`
- src/creo_mechdog/capabilities.py: `76069017a83948b001b5126b590f4d58c5dc2901763b5e296e2d7b777b1607ec`
- version.py: `448adffc4b06ec09e4c4ad839483d47bff4481d0122ddf749cd21fed69d7ade2`
- tests/unit/test_product_rules_mcp.py: `515a20091604995dd468920dc32a30fee53521c7ee4620c7da540bd83f6f7e8f`
- tests/unit/test_product_rules_driver.py: `dfa7fe8496facb70f25099f53ebef8afa0f155bc08d874b0af91be717c56443a`
- src/creo_mechdog/product_rules.py: `2f119705bc67d143671aa448ecf570ddcaacf18919c1ef6b09fa3c195765343a`
- src/creo_mechdog/schema.py: `eacf1b90a639c504e01a6b36ccf9200b08f967cfdfce2bb246bc3a4cf97f7fa2`
- src/creo_mechdog/paths.py: `389dca158e3a7d02337ca3a099a1872bf858e38cc8108d78172cff235256dff5`
- examples/product_rules/box_frame.json: `cbc3f10e13aef0d33b92a3e3aa2e400a0b654f6da60dec52a7d8f53a63549c5d`
- tools/test_adoption_product_rules.py: `c8dc5c33e369ad53d8eedac508d5d93948e4b66f02c7f7bf1c79bba42bbb933d`
- tests/unit/test_product_rules.py: `967947b3c5a07276a9687bbe8d8ab4715a9dd7db5246c8f7e5b12112472adaa6`


### 完整检查实际结果与环境限制

冻结规划器源码的完整轮 dev_check_final.log：2663 tests / 0 failures / 1 error / 2 skipped，
耗时 310.835 秒；unit_tests=failed、success=false，不能用专项绿色替代全量结论。
语言回归闸门通过（24 lint 存量、12 未格式化存量，无新增回归）。
checked_source_sha256=89dd3fd39f3eca7230a4e58886d2e483a1ca854520a4f4614ee41b7e4e8fb386。
唯一错误是既有 DEV-040 stdio 黑盒夹具写 reconciliation 临时证据文件 Errno 2：
原失败路径 264 字符；缩短测试前缀后 evidence 路径 255 字符可通过，但后续 intent
临时路径仍 285 字符并失败。测量见 fixture_path_lengths.json、fixture_short_prefix.log。
本树 build 下的纯路径探针确认父目录存在且组件长度合法时，255 字符写入成功，
264/285 字符均 FileNotFoundError(2)；详见 path_probe.json。
没有为此改变生产路径、注册表或系统长路径设置，也没有 skip 夹具测试。


### 最终测试契约补充

报告 CLI 的 Git 身份允许未知，新增回归不再要求宿主必须是 Git checkout。
旧测试在定向 mock 未知身份时 RED（len(None)）；改后成功/不可用身份两条契约通过，
driver_git_unknown_red.log / driver_git_unknown_green.log 为证据。
最终本树专项 green_verified.log 为 72/72，Ruff check/format *_verified.log 通过。
最终 driver_verified/report.json 补充本次最新原始字节指纹；测试文件新增一例后，
此前 71 项记录和 driver_final 的旧指纹保持其阶段含义。
DEV-040 前缀尝试已完全撤回，没有夹具或生产路径变更进入交付。
经控制者授权，建立 E:/f63-89873d66 一次性短路径源码验证副本，复制白名单源码及本任务
自有 .venv；逐文件原始字节一致证据 short_copy_identity_final.json。副本没有复制本机
config/constants/SDK/jobs/models。仅在副本补 setuptools==80.9.0 并重装 editable，已核对
sys.executable/sys.prefix/package/resource_root 全为副本。副本本地 Git 快照
b87be074338aa975a7b38d37fc23f16f1a0a6e07 仅为验证身份，不能冒充原树提交。
副本保留供控制者核对；没有修改原树环境或 DEV-069。


短副本首轮 2664 tests / 0 failures / 1 error / 2 skipped，DEV-040 长路径场景通过；
唯一错误是 source_files 白名单未包含 tests/native/test_axis_geometry.cpp，导致既有
T05 来源指纹测试无法读取其依赖。证据 short_dev_check.log / short_development_check.json，
checked_source_sha256=c03195646a8c2cee001bcf3d960b884d428bbf39093976b9bae5220c7a5f3927。
经授权仅向验证副本补入 git ls-files tests/native 中缺失的 7 个 .cpp，逐项双哈希相同，
证据 short_copy_added_test_dependencies.json。没有修改发布白名单或原树；验证副本此后定义为
源码包加原有受控测试依赖，不声称发布包已包含全部旧测试依赖。
完整 T05 模块 16/16 通过；副本本地验证身份更新为
e0a13e051a58bc92eeb53c177c177021d025838d，最终完整 dev_check 仍在运行，尚不能宣称门禁通过。


### 最终完整环境门禁（2026-11-06）

短路径源码加受控测试依赖副本执行同一命令
`python tools/dev_check.py --work-item FEAT-063-completion`：exit 0，success=true，
unit_tests=passed，2664 tests / 0 failures / 0 errors / 2 skipped，耗时 385.563 秒。
证据 short_dev_check_complete.log、short_development_check_complete.json、
short_unit_test_report_complete.json 均已复制回本树证据目录。
受测验证身份 e0a13e051a58bc92eeb53c177c177021d025838d，dirty=true（验证日志）；
checked_source_sha256=c03195646a8c2cee001bcf3d960b884d428bbf39093976b9bae5220c7a5f3927。
Ruff 0.17.0 / clang-format 23.1.3；372 Python、43 C++ 检查，24 lint/12 未格式化存量，
语言回归闸门通过，未修改基线。

原任务实现提交 448297a75a466c88adefe35cd0582b92a9a42654；提交后 driver_committed 通过，
Git dirty=false。committed_python_template_equivalence.json 确认副本受测 Python 与固定模板
和该实现提交原始字节相同；副本 Git 身份不是原源码提交。
长工作树全量的路径错误与首轮不完备副本缺件均保留，不宣称这些旧轮通过。
验证副本仍保留 E:/f63-89873d66；无需修改系统长路径设置、生产路径或 DEV-040 夹具。
软件范围完成；未发布、未连接 Creo，原生模板、保存重载、WorkBuddy 与全新机器安装未验。
本任务未对 DEV-069 工作树写入、提交或切换；其自身并行推进不属于本次改动。
