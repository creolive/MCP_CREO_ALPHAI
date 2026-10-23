# BUG-030 缓存入口与旧登记继续收口

日期：2026-10-22（Asia/Shanghai）。状态：**补修已实现，编译与离线检查通过；最新专项 4/9 通过，余项因连接 -4 中断**。沿用 BUG-030，关联 BUG-029 的报告纠正，不合入或发布。

## 源码与环境

- 目录 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/bug062-editing-batch2`，HEAD `dcfb8e19ddd7f213b231a800034c7be0dd1aec6c`，dirty=true。下列新改动未提交，不能只用 HEAD 标识受测代码。
- Windows x64 / Python 3.12.14 / 本机 Creo 12.4.0.0 与匹配 Toolkit SDK。前期连接失败时未能读取 release_numeric；后续本轮专项已实测 release 44，见末节。不将历史探测冒充本轮结果。
- SDK 构建成功，格式化后再次构建成功。`build/source.sha256` 为 `e833fb192d1c84256a1f88fbf3e0cacddb7d1d0624d432d0690b78409c70dd70`。
- 当前执行器 `build/creo_worker.exe` SHA256：`a99be308754bf72a013f891cf193c206f796cb029ad2e5246bf49b50d5c938c1`。
- `native/generic.cpp` SHA256：`7280d3260365b2055cb3e82676f959f9d76bb8e29cb5a18edf5f53650d3fb776`；`native/sketch_edit.cpp`：`4a279bcf555179dbed77da22322a30b140dff9bd63c597571032fe39c5d8eb3d`。

## 实现范围

1. `set_sketch_dimensions` 在原生 redefine 成功后统一将草图几何缓存置 stale，覆盖标签、整数特征 ID 与数字字符串规范化后的 ID。保守失效全部草图，包含关系传播可能影响的其他草图。
2. `set_parameters` 补同样的失效处理，已有 `set_dimensions` 与 `set_relations` 保留。创建路径显式初始化 `geometry_stale=false`。
3. 对相同历史实体描述，跳过原生改写前还读取当前 ProSection 核对实际实体类型、构造属性及几何，且 requested dimensioning 必须相同；原生结果增加 `native_geometry_verified=true`。不再依赖旧登记缺字段时的默认可信值。旧登记的请求模式可从已有 `solver.requested` 读取；无法证明则不走快捷路径。完整与跳过路径均维护缓存状态。
4. 新增 `tools/test_editing_closeout.py`：通过当前目录独立 stdio MCP 服务测试；新建隔离模型，提交一次并只轮询原 job，busy/unknown/连接失败停止，要求成功作业 revision +1 和保存重载通过。旧格式夹具仅对本轮创建的 `cache_*` 模型在锁内删除两项缓存字段，保留控制文件原件和 PRT 哈希，不修改历史模型。`--retry-startup` 为显式单次重试参数，不自动重试建模提交。

## 离线验证

| 命令 | 本轮结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | 匹配 SDK 编译通过；native 文件格式化后重编译通过 |
| `.\.venv\Scripts\python.exe tools\dev_check.py --work-item BUG-030` | 553 单测通过，0 failures/errors，增量语言检查通过；源码指纹 `ad12965395f3a0310d8dbfaa70c6a2fc1ad4904da6a37b341b38ca08e57635fe` |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_editing_closeout -v` | 5 项通过；最后添加显式启动重试 CLI 参数后再次通过 |
| `.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item BUG-030` | 最终语言检查通过；指纹 `ba18d4b60fece8a37e3c68887c67be17719ddc275660a039d34b60020811288c`，该次未运行单测/原生验收 |
| `git diff --check` | 通过；仅 Windows 工作区换行提示 |

553 项报告在 `build/unit_test_report.json`；最后语言报告在 `build/development_check.json`。存量 31 条 lint 和 19 个未格式化文件仍按既有基线处理，没有重建基线或添加容许项。“检查通过”不代表全库严格风格清零。

## 实机尝试与阻断

所有下列报告的 `calls=[]`、`cases=[]`，没有提交建模作业，因此没有可报告的 job_id/model_id、体积、保存重载或几何通过结论。

| 本机时间 / 报告 | 事实 |
| --- | --- |
| 18:10 左右，`build/editing-closeout/683753dd327248148ccefd46fae6e1e5/report.json` | 首次就绪观测持续未连接、Toolkit -4；在确认未提交模型后只停止本轮测试帮助进程，未结束 Creo/nmsd。报告原件保留。 |
| 18:19:16，`build/editing-closeout/41d04c1002c041c788e64a54a86736fc/report.json` | 用户告知重启后重查，本机当时没有 Creo 主进程；E 盘 0.5.0 服务保留上次启动未确认状态，要求显式 retry。 |
| 18:19:52–54，`build/editing-closeout/514c2f2a9d8c4efaa8be93167e92a14d/report.json` | 按用户“再试”指示执行一次 `--retry-startup`，launch_attempt 21→22；新 parametric/xtop/nmsd 启动。新进程启动初期返回 -4，脚本在建模前停止。此时尚无可见主窗口，不能将该瞬时 -4 单独归为稳定连接故障。 |
| 18:20 窗口核对后，`build/editing-closeout/bb773070978443ca86a8791e3e40ec1a/report.json` | 新 Creo 12 窗口可读取启动首页，无可见模态框；随后独立 E 盘服务仍返回 `not_found_or_unreadable` / `toolkit_code=-4` / `worker_exit_code=20`，脚本停止。没有重复启动 Creo，没有模型提交。 |

本轮新进程 parametric PID 22604、xtop PID 3096、nmsd PID 19840、pro_comm_msg PID 20184，均在 Windows SessionId=1，与检查进程相同；当前没有证据证明属于跨 Windows session 错配。GUI 状态通过 computer-use 读取；因截图基础设施异常使用可访问性文本，不把它当作完整视觉验收。

客户端已挂载连接器曾返回旧 0.4.7 缓存；未用它提交建模。本轮开发脚本明确由 E 盘 Python 启动 E 盘 `server.py`，其公开启动状态报告 current_version=0.5.0。旧缓存不用于本轮就绪或源码身份结论。

`-4` 在本机 SDK 枚举为 `PRO_TK_E_NOT_FOUND`，只证明此次异步连接未找到会话；不能据此判定草图修复失败、Creo 卡死或 nmsd 根因复发。既往同码调查见 BUG-056/BUG-058；此次没有终止 Creo/nmsd、清除保护或开展故障注入。

## 两处报告纠正与剩余验收

- 原 0.3.1 反馈原件同为 **Creo 12.4/release 44**。此前“Creo 10 差异”的归因错误，已纠正 BUG-030 工作卡、台账和批次说明；原改尺寸失败仍未复现，历史部署身份与完整输入待核实。原始外部反馈文件未修改。
- BUG-029 原位 no-op 表示不执行原生树重排；外围成功作业仍保存重载并 revision +1。历史 `build/bug029/accept2.json` 已记录前一步 revision 3、原位请求 revision 4。此前“revision 不变”汇报错误，新脚本补 +1 断言；本轮尚未执行到该场景。

连接恢复后先运行 `tools/test_editing_closeout.py` 的 9 个专项场景（标签/整数/数字字符串改尺寸、旧字段缺失的已变/未变、标注模式与干净重复、参数关系驱动、矩形原生核验、重排原位 revision），再运行硬性原生核心回归 `tools/test_general.py`，补 BUG-062 的 arc/centerline 编辑回归。当前新几何核验各实体分支均仅完成编译，不能宣称实机通过。前轮 548 单测、核心 7/7 与 BUG-062 实机记录保留其原源码范围，不能代替本轮验证。

三个 BUG-078 受保护现场与既有工作区资料均保留；未合并 main、未发布、未调整版本号。WorkBuddy 黑盒及 Creo 9/10 仍未测。

## 18:30 用户重启 Codex、关闭 Creo 后的续验

用户要求继续，说明已重启 Codex 并关闭 Creo。复核已挂载 dev 连接器为 E 盘 0.5.0、91 工具，旧 0.4.7 缓存问题已消失。启动前只有遗留 `nmsd.exe` PID 19840（创建于 18:19:54），没有 Creo 主进程；本轮一次显式 `creo_startup_status(retry=true)` 启动 launch_attempt=23，parametric PID 14880、xtop PID 8068 创建于 18:30:37。窗口可读取、没有可见挂起，服务仍返回 -4，并于约 18:32:36 等待超时，coordinator_running=false。没有建模作业提交。

证据保存在 `build/editing-closeout/restart-20261022-1830/`：启动前后进程身份、连接状态、此前 553 单元报告与最后语言检查快照。遗留 nmsd 与新 Creo 跨批次并存，符合 BUG-056 历史处置的候选条件，尚不能据此认定本次根因。已向用户申请关闭本轮新建空白 Creo、核对身份后清理遗留名字服务再启动；授权到达前保留进程，不自行结束 Creo/nmsd，不循环重试，不清保护。

## 用户授权清理后的结果

用户明确回复“允许清理并继续”后，使用 computer-use 读取启动首页，按窗口退出本轮空白 Creo；确认 xtop/parametric 均退出，再核对 nmsd PID 19840、SessionId=1、创建时间 18:19:54 及 Creo 12.4 路径后结束该遗留进程。证据为 `authorized-cleanup.json`。没有通过强杀处理 Creo，也未清任何模型保护。

18:42 再启动（launch_attempt=24）：parametric PID 22592、xtop PID 19592、**新的** nmsd PID 10500。等待预算结束仍 `Toolkit -4`，因此“清理遗留 nmsd 即能恢复”在本轮未成立，不能据既往 BUG-056 结论宣告此次恢复。

进一步只读诊断（均持 E 盘 Toolkit 通道锁、无模型写入、不随机选择会话）：

- PTC 自带 `nmsq -query` 能读到 PID 19592 / Creo release 44 的会话登记。`_UserID=ADMINISTRATOR` 匹配 1 条，而 `Administrator` 匹配 0 条；但仅调整探测子进程 USERNAME 后仍 -4，用户名大小写不足以解释此次故障。
- 用本机 SDK 编译忽略目录内的最小诊断程序 `connect_filters.cpp`，分别指定登记中的 display/user、取消 display/user 筛选但禁止随机选择、以及按 SDK 公布格式明确指定登记会话 ID，三次均返回 -4。指定 ID 的诊断设计为连接成功后再严格核对实际 ID，未成功到达该步骤。未修改生产连接代码或本机配置。
- 当前 `trail.txt.52` 只见启动记录，未见这些请求的异步 IPC 初始化；std.err 最后写入早于本轮，不作本轮新增错误使用。匹配进程仍在，GUI 可读取，不能据 -4 宣称 Creo 卡死。
- [PTC ProEngineerConnect 官方说明](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r13/chinese_cn/creo_toolkit/486.html)将该码解释为未找到符合条件的会话，或无法读取名字服务中的会话信息；该说明不能进一步证明本机根因。

原始证据在同目录的 `uppercase-username-probe.json`、`exact-filter-probe.json`、`unique-filter-probe.json`、`selected-id-probe.json`、`registered-creo-session.txt`、`processes-after.json`、`health-after-cleanup.json` 与 `startup-after-cleanup.json`。最小诊断程序不是建模验收，也不算测试通过。已请求用户在 Codex 外普通 PowerShell 执行同一 E 盘 `bridge.py status`，以比较宿主启动环境；等待该对照前停止新的 Toolkit 探测。

本轮专项和 `tools/test_general.py` 仍未取得新实机结果；工作项继续验收中。当前 Creo 保留打开，源码修复、553 单元与风格检查结论不变，未合并发布。

## 普通 PowerShell 对照：连接成功，验收执行入口准备

用户在 Codex 外普通 PowerShell 执行同一 E 盘 `bridge.py status`，贴回 `connected=true`、`toolkit_code=0`、`release_numeric=44`、`disconnect_code=0`、`worker_exit_code=0`。原样数值及用户报告来源见 `user-terminal-status.json`。该结果确认此时的 Creo 可经该宿主连接；它不代表建模许可和几何验收通过。

Codex 子进程与 Windows 默认环境的常用系统字段对比，仅发现 SESSIONNAME 缺失；仅对一次探测补 `SESSIONNAME=Console` 后仍 -4（`sessionname-probe.json`），因此不据此修改生产环境代码。当前证据指向宿主执行上下文差异，尚未确定具体约束，不能继续归因为 Creo/nmsd 故障。

computer-use 启动普通 PowerShell 被产品策略拒绝（`product policy blocks this app`），未尝试绕过。已准备 `build/editing-closeout/run_native_checks.py`，完成语法和独立 Ruff 检查，并请用户在刚才连接成功的普通终端执行一次：

```powershell
E:\Projects\MCP_CREO_MechDog\.venv\Scripts\python.exe E:\Projects\MCP_CREO_MechDog\build\editing-closeout\run_native_checks.py
```

该入口顺序执行当前 E 盘编辑专项、`tools/test_general.py`、BUG-062 两入口与负例复验，失败即停，不自动 retry。每次生成唯一 `terminal-<uuid>` 目录，记录提交/dirtiness、执行器/源码哈希、命令、退出码和原始 stdout，并备份既有核心报告。BUG-062 复用已有 fixture 的纯客户端定义，不运行 BUG-078 故障注入入口；使用唯一模型名和独立输出，保护旧证据。没有创建常驻服务或新生产传输入口。当前等待启动/执行报告，不将该入口准备就绪计为实机通过。

## 19:51–19:53 普通终端实机：4 项通过，连接中断

用户实际运行后，报告为 `build/editing-closeout/terminal-2d307504c30c4980b745c2ce9dcd7f22/manifest.json`；编辑专项原始报告为 `build/editing-closeout/c5da3db0a88a4274b0c297ff60edca37/report.json`。19:51:39 就绪、19:51:40 公开会话状态 connected=true、release 44；提交号仍 dcfb8e1、dirty=true，两个 native 文件及执行器 SHA256 与本文构建值完全一致。

| 已完成场景 | model_id | 最后一个成功 job_id | 实测结果 |
| --- | --- | --- | --- |
| 标签引用改尺寸再恢复原几何 | 3b3e160d6d0941eb8647f005e624930b | 784903e065d743f49567dc5f07c5fbf6 | 体积 2010.619298→3141.592654→2010.619298，revision 1→2→3；恢复未误走 unchanged |
| 整数 ID 引用改尺寸再恢复 | 791e45bfeae448a0baf8ed9dae37c78a | a1dbecadd129440581e96a8d7eee8da8 | 同上；整数入口失效标记与实际替换通过 |
| 数字字符串 ID 引用改尺寸再恢复 | 6fd044e00f034d3b84d35ffee0136150 | 4f6a19712c2d49d1a625af8997bb4025 | 同上；规范化后入口通过 |
| 旧登记缺两项缓存字段，几何未变 | 14cd106d7d214ff2bcf28f545ea8fa99 | 09a3e25104864fe88cca00ac9c609b34 | 体积保持 2010.619298，revision 1→2；unchanged=true 且 native_geometry_verified=true，缓存安全重建 |

表内成功步骤均 `saved_file_reloaded_and_verified=true`。总计 **12 个作业成功、1 个连接失败**；第 12 个成功作业是下一“旧登记已变”场景的新建夹具，不构成该完整场景通过。

失败作业 `d0ba4dd8d7324fffaf9addea04b0e973`、model_id=`495267f4947648e18d5ec458a1506c9d`：19:53:25–19:53:30 在 `connect_creo(&process)` 返回 -4，`failed_stage=connect`、`failed_operation_index=null`、操作列表为空、保存未执行。`AssertionError` 是驱动检查到作业失败后停止，不是 legacy_unchanged 失败，也不是新的 Python 协议根因。模型登记为 failed，revision 保持 1、pending_job=null；PRT 实际 SHA256 与登记一致，为 `d28520f595d6ca22099e53f9ed2bc9502c3c142505aa9e958303a80b3b7dfe0e`。未清 failed 状态、未重提该作业，失败原件完整保留。

同一 Creo/新 nmsd（xtop PID 19592、nmsd PID 10500，创建于 18:42）在普通终端先连通并成功建模，随后再次掉线。因此此前“Codex 宿主执行上下文差异”的推断**证据不足**；普通终端成功只能证明那个时点连通，不能证明宿主导致失败或通道稳定。此次记录交叉关联 BUG-058，不据此重开 BUG-001/BUG-056，也不凭同码认定根因相同。读取时当前只见 E 盘 dev 服务，未见 C 盘服务或仍运行的本轮测试；这不是对故障时全部并发行为的证明。

后两阶段按设计没有启动：最新 `tools/test_general.py` 与 BUG-062 复验仍未完成。剩余专项为旧登记已变、标注模式/干净重复、参数关系驱动、矩形原生核验、重排原位 revision。

为避免重复已通过的前四项，验收脚本新增 `--from-case`，报告显式列出 selected_cases，所有场景仍新建隔离模型。通道条件确认后可用同一入口加 `--from-case legacy_changed` 运行剩余五项及后两阶段；**当前未执行此续验命令**。新增离线回归验证从最后一项开始时不会执行任何前置场景、不会使用旧失败模型；6 项驱动保护单测通过，完整统一检查另记最终结果。此改动只涉及验收驱动，不改变已受测的 native 文件和执行器。

最后检查：`python tools/dev_check.py --work-item BUG-030` 通过，**554 单元、0 failures/errors**，源码指纹 `ebf27b34cec2664ef931c1710329b8e64e55cc010a75d9769f3a79b34949d137`（dirty，HEAD dcfb8e1）。`git diff --check` 通过；报告快照为本次 terminal 目录下 `dev-check-554.json`、`unit-tests-554.json`。没有调整风格基线。

20:12 只读界面核对后，做一次公开 `creo_session_status` 实时检查：仍 connected=false / toolkit_code=-4，xtop 可见主窗口未报告挂起，coordinator_running=false。结果保存为同目录 `review-live-status.json`。仅据可访问性文本不能完整排除 Dashboard 状态；未进入剩余场景、未新建模型、未恢复旧失败模型。当前 Toolkit 通道仍为后续验收阻断，停止继续连接探测，等待用户提供异常时的界面/其他客户端活动信息。

## 2026-10-22/23：-4 根因排查、授权恢复与最终全量收口（本机验收完成）

全部诊断快照、抓包与连接监控保存在 `build/editing-closeout/bug058-rpc-snap-2100/` 与 `bug058-snap2/`；根因链条、已证伪假设与授权操作详见 [BUG-058](../work-items/BUG-058.md) 2026-10-22/23 节。要点：失败连接的直接原因是客户端侧 RPC 端点自举端口错位（bind 826 未 listen、两次连接被 RST）；广播地址失效与主机名解析两个假设被证伪；仅重启 nmsd 不能恢复；经用户授权经窗口正常退出 Creo 后以 `creo_startup_status(retry=true)` 拉起新会话恢复。机器 23:12 重启（Event 1074/6005/6006）解释了当晚之后的所有 -4，与草图修复无关。失败作业 `d0ba4dd8…` 与模型 `495267f4…` 保留，未进入几何操作。

### 恢复后的剩余五项与全部回归

会话（launch_attempt=25 段）`run_native_checks.py --from-case legacy_changed` 取得：legacy_changed、dimensioning_and_clean_repeat 通过；随后修复驱动一处缺陷（`creo_inspect_model` 分节响应不内嵌 `dimensions`，改为 `section=dimensions` 查询）；续跑 parameter_driven_cache、rectangle_native_verification、reorder_noop_revision_plus_one 全部通过（**九项专项 9/9**）；general_core 7/7。BUG-062 阶段首跑因上阶段收尾竞态被就绪门拒绝（17 秒即失败），单独重跑生成脚本通过：两入口 R5→R6（523.599→904.779、rev 1→2、保存重载通过）、缺实体/改名/改类型拒绝、失败后合法编辑（rev 3、体积回到 523.599），报告 `terminal-8655b8b6…/verify3.json`。

### 新增实体分支核验与两处实现修正

按计划补测圆弧与中心线同几何重复提交及 ellipse、spline 分支（`tools/test_editing_closeout.py` 新场景 `entity_branch_native_verification`）：arc+line、centerline+circle、ellipse、开放 spline 四分支均 `unchanged=true`+`native_geometry_verified=true`。闭合周期 spline 经新增只读 `verification_probe`（`native/sketch_edit.cpp`）证实求解后 `point_arr` 存储拟合控制点（如 (3.5,9)/(-3.5,11)），与请求插值点逐点比对不可能成立；该分支按保守路径执行实体替换并刷新缓存，断言其不返回 unchanged。另按 clang-format 规范格式化 `sketch_edit.cpp`。

### 最终源码与最终证据

因改动 native，格式化后重编译并**全量重跑**：10 项编辑场景全过、general_core STAGE_PASS（7/7）、BUG-062 复验 STAGE_PASS（`run-native-checks-final2.txt`，编辑报告 `4ed1e86f…/report.json`，75 处 `saved_file_reloaded_and_verified=true`、0 失败）。`dev_check` 通过：**554 单测、0 failures/errors**、增量语言检查通过、风格无新增（`build/development_check.json`，14:55Z）。重启后新会话（launch_attempt=30）连续 5 场景新建/编辑/保存重载通过，空闲约 12.5 分钟后 `bridge.py status` 仍 `connected=true`——同会话空闲复连完成条件达成。

结论：BUG-030 本机实机验收完成（状态见工作卡）；BUG-062/BUG-029 复验结论已同步；未合并 main、未发布。WorkBuddy 黑盒验收与版本发布另行安排；Creo 9/10 外部复测按现行规则不阻塞。

### 提交与最终指纹

本轮源码、测试与文档已单独提交为 `3331854`（BUG-030/BUG-062: 编辑缓存守卫收口、原生核验探针与实体分支验证）；本节指纹补记为其后续小提交。BUG-078 卡、会话记录与运行生成物排除在外，工作区剩余 dirty 项均非本轮条目。最终执行器 `build/creo_worker.exe` SHA256 `f36de8b0c94f94efdd0ad840c18e972d7e86389e114d82c5d03532bbab172267`（格式化后重建）；`native/sketch_edit.cpp` `0ff9b18e…`、`native/generic.cpp` `7280d326…`（未变）；`build/source.sha256` `f74648c9…`。上表前期构建值（`a99be308…` 等）为当时源码，最终证据以本节指纹为准。
