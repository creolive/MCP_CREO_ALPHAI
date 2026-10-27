# DEV-049 T01 验收记录：0.6.1 断连事故离线核对（2026-10-27）

任务：[DEV-049](0.6.1-FEEDBACK-TASKS-2026-10-27.md) T01（离线取证，不做主动探测）。缺陷主卡：[BUG-085](../work-items/BUG-085.md)。旧案：[BUG-056](../work-items/BUG-056.md)、[DEV-036](../work-items/DEV-036.md)。

**结论先行：证据不足以认定本次与 BUG-056 同一机制，BUG-085 保持根因未定。** 本次唯一与 BUG-056 相同的部分是错误映射（`-4` / worker exit `20` / `not_found_or_unreadable`）和"连接在探测阶段快速失败"，这两项都不构成同根证据。本次事故另有 BUG-056 不具备的变量：`parametric.exe` 三个窗口全部隐藏且观测到 hung 窗口，以及事故窗口内 `native/sketch_edit.cpp` 正在被修改并可能触发 worker 重建。关键区分证据（名字服务器批次、连接请求是否到达 Creo）本次分别缺失和自相矛盾。

本次只读取证：未创建 MCP 客户端、未调用任何 MCP 工具、未探测、未连接 Toolkit/Creo、未结束或重启 Creo、未清任何保护、未改动运行数据。

## 一、交付身份与环境

| 项 | 值 |
| --- | --- |
| 任务分支 | `codex/dev049-t01-incident`（自 `codex/dev049-feedback061` 建立） |
| 依赖提交 | `354ceff`（T00 归档+登记）、`2e5bbc9`（T00 验收记录） |
| 开工基线 HEAD | `2e5bbc947b4d4a88494730d0598e89738f4c5a43` |
| 工作区状态 | dirty：`M session_activity.json`；未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/*`（共 33 条）。以上均为本机运行数据，本次未读取、未修改、未提交 |
| 核对时段 | 2026-10-27 23:06–23:20（Asia/Shanghai）/ 2026-10-27T15:06–15:20Z（UTC） |
| 环境 | Windows 11 Enterprise x64；Python 3.12.14（`.venv`）；Creo 12.4.0.0 / 匹配 SDK；只读文件系统取证，无 Toolkit 会话 |
| 受测指纹（本次核对的证据原件） | `build/installation_loft_validation.json` `aad76b8730041fb69a09161e2db0e8530b9aa8e5622c2563f46b495eb93fe016`（448 863 B）<br>`build/creo_session/trail.txt.67` `85ae1defac69c223b7dcf329e308a3044be3be6f56e8dec7a25639de157dc007`（356 603 B）<br>`%LOCALAPPDATA%/MCP_CREO_MechDog/startup/6235eee8…/startup.log` `a657144a2ffd7baecfc412ace8d49b03f2c7439eb0d1e659e7c557ad810a603c`（769 258 B）<br>四个 job.json：`94eb5484…`（471d5301）、`ff0ca9d4…`（633de212）、`dd981928…`（6c8ed77b）、`95bb7d82…`（14560f1b） |

事故当日的源码身份无法还原为提交指纹：当时工作区 dirty，未采集 `source.sha256`；现有 `build/source.sha256` 与 `build/creo_worker.exe` 均为 2026-10-27 重建产物（08:17Z）。可用的最近锚点是当时 HEAD 序列 `83bd7b6`（2026-10-26T11:48:31+08:00）与事故后 6 分钟提交的 `f54cda8`（12:36:29+08:00）。**这一缺口保留，详见第六节。**

## 二、四个 job 与同一会话的其余作业

FEAT-030 的 2026-10-26 记录只给出 `471d5301…`、`633de212…`、`6c8ed77b…`、`14560f1b…` 四个短前缀；本次在同目录展开为完整 ID 并逐项核对。四份原件全部存在，无缺失。

| 完整 job ID | 输入 | 原生连接阶段 | worker exit | 连接码 | 最后成功操作 | 持久化终态 |
| --- | --- | --- | --- | --- | --- | --- |
| `471d5301e20b43febb10db36725d5a07` | 种子 `five_smooth`（sha256 `818c1e8c…c9148b5`）；5 个 `sketch`（矩形 ±6/±13/±17/±11/±4，XY 0/20/50/80/100） | `PHASE=connect` → `connect_creo=0` → `ProEngineerConnectIdGet=0` → … → `PHASE=disconnect` `DISCONNECT=0` → `PHASE=result_delivery_complete` | 未记录（作业路径无该字段） | `toolkit_code=0`、`disconnect_code=0`、`connected=true`、`completion_stage=result_delivery` | blend id 93、5 段、smooth；`saved_file_reloaded_and_verified=true`，体积 69 220.870 919 843 95 | `succeeded`，revision 1，`inspection_source=saved_reloaded`，part `.prt.2` sha256 `27ecf481…`，`seed_load_evidence.status=loaded`、`evidence_persisted=true` |
| `633de21212f7425f9bdfb8a3d5fdc11d` | 同模型 `1e1fb40a…`；`set_dimensions` id 37 → 55.0（section_1 草图真实尺寸） | 同上（`PHASE=connect` … `DISCONNECT=0`） | 未记录 | `toolkit_code=0`、`disconnect_code=0` | 编辑后 5 段 smooth 保持一致，体积 69 220.871 → 70 471.928 731 742 55，保存重载 true | `succeeded`，revision 2 |
| `6c8ed77b9da0424fbd23889ae5fb1e48` | 种子 `four_smooth`（sha256 `fff48c00…8258fb5`）；4 个 `sketch` | 同上 | 未记录 | `toolkit_code=0`、`disconnect_code=0` | blend id 82、4 段、smooth；体积 32 554.802 436 816 87；保存重载 true | `succeeded`，revision 1，model `4171cb54…` |
| `14560f1b98bd41f4abda91d0ff2a6b8c` | 同模型 `4171cb54…`；`set_dimensions` **id 9 → 25.0**（SECTION 基准面尺寸） | 同上；`native.log` 记录 `ProDimensionValueSet=0`、`ProSolidRegenerate=0` | 未记录 | `toolkit_code=0`、`disconnect_code=0` | 再生成功但**体积未变**：32 554.802 436 816 87 → 32 554.802 436 816 87 | `succeeded`，revision 2 —— 作业成功，但不构成编辑闭环 |

结论要点：

- 四个 job 都**在断连之前成功完成**，连接码全为 0，均有 `saved_file_reloaded_and_verified=true`。断连发生在**作业之外**（启动/连接阶段），不是作业执行中被中断。这与 BUG-056 的 M2 作业在 native 执行中被 `-4` 打断（`unknown_outcome`）不同。
- `14560f1b` 是"four 类种子 SECTION datum 不驱动 Blend"的实证：id 9 加到 25.0，`ProSolidRegenerate=0`，体积一位不变。**该 job 的 `succeeded` 不能被当作 `matrix_four_smooth` 编辑闭环通过。**
- 同一 Creo 会话内另有 6 个作业可佐证连接健康度（均在 12:23–12:28 本地时间）：`b4bd95ca`（two_straight，04:23:54Z）、`cda3ba3f`（two_straight，04:26:13Z）、`49268b14`（two_smooth，04:26:22Z）、`7c283eaf`（five_smooth 创建，04:27:42Z）、`7f72eba7`（five_smooth 编辑，04:27:54Z）、`cf41d9f9`（four_smooth 创建，04:28:01Z）。全部 `succeeded`。
- 四个 job 的 `session_fingerprint` 一致（`8109163335419786528`）；报告内 9 个种子 `source_hashes` 与 `seed_library/seed_manifest.json` 逐项一致（本次复核，无偏差），说明矩阵输入在事故时未被改动。

## 三、时间线（UTC / Asia/Shanghai，UTC+8）

| UTC（2026-10-26） | Asia/Shanghai | 事件 | 来源 |
| --- | --- | --- | --- |
| 00:07:11.125 796Z | 08:07:11 | 会话创建：`parametric.exe` PID 20180；`xtop.exe` PID 20164（00:07:11.802 922Z）。此后至 04:38 未变 | 事故时 `creo_process_snapshot`（报告内，observed_at 04:38:23.209 686Z） |
| 04:11 | 12:11 | 编辑专项 16/16（断连前最后一轮完整作业） | [0.6.1 发布记录](../validation/RELEASE-0.6.1.md) |
| 04:23:54 | 12:23:54 | 种子 smoke：`b4bd95ca` two_straight 成功，体积 5131.268 000 863 329 | job.json |
| 04:26:13 / 04:26:22 | 12:26:13 / 12:26:22 | `cda3ba3f` two_straight、`49268b14` two_smooth 成功 | job.json |
| 04:27:42 – 04:28:01 | 12:27:42 – 12:28:01 | `7c283eaf` five 创建 → `7f72eba7` five 编辑（69 220.871→70 471.929）→ `cf41d9f9` four 创建（32 554.802）；此后无作业直到 04:29:56 | job.json |
| 04:29:56.99 – 04:30:09.55 | 12:29:57 – 12:30:09 | 第二轮：`471d5301` five 创建成功（rev 1） | job.json |
| 04:30:09.97 – 04:30:18.49 | 12:30:10 – 12:30:18 | `633de212` five 编辑成功（rev 2，70 471.929） | job.json |
| 04:30:18.82 – 04:30:31.96 | 12:30:19 – 12:30:32 | `6c8ed77b` four 创建成功（rev 1，32 554.802） | job.json |
| 04:30:32.31 – 04:30:44.69 | 12:30:32 – 12:30:45 | `14560f1b` four "编辑" id 9→25 成功但体积不变（rev 2） | job.json、`native.log` |
| 04:30:42 | 12:30:42 | trail 最后一次 `connected to Pro/E`（`creo_worker.exe`，asynchronous），对应 `14560f1b` | `trail.txt.67` 第 5801–5807 行 |
| 04:30:48.282 – 04:30:48.392 | 12:30:48 | 协调器 `checking` → `waiting_for_channel` → `building_worker`；**此后 4 分 37 秒无任何状态发布**（无 ready、无 timeout） | `startup.log` |
| 04:35:25.114 – 04:35:31.598 | 12:35:25 – 12:35:32 | 新周期 `checking` → `building_worker` → **`ready connected=True`**；`trail` 中**无**对应 IPC 初始化记录 | `startup.log`；`trail.txt.67` |
| 04:36:23.926 – 04:36:29.472 | 12:36:24 – 12:36:29 | 再次 `checking` → `building_worker`（5.53 s）→ `waiting_for_connection`；native `connected=false`、`connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`、`release_numeric=0` | `startup.log`；报告 `startup_queries`（119 条） |
| 04:36:29 | 12:36:29 | 提交 `f54cda8`（`native/sketch_edit.cpp`、`server.py`、`tools/test_editing_closeout.py` 等） | `git show --stat f54cda8` |
| 04:38:23.209 686 | 12:38:23 | 报告侧取到 `state=timeout`、`in_flight_phase=waiting_for_connection`、`phase_remaining_budget_seconds=0`、`coordinator_pid=10004`、`launch_attempt=46` | 报告 `startup` |
| 04:38:24 | 12:38:24 | 第三次启动写出 **空汇总** `installation_loft_validation.json`：`success=false`、`cases={}`、`jobs=[]`、`version=0.6.0` | 报告文件 mtime |
| 04:38:25 – 04:40:29 | 12:38–12:40 | 再一周期 → `timeout`（"Startup total budget expired"） | `startup.log` |
| 04:43:18 – 04:45:20 | 12:43–12:45 | 再一周期 → `timeout` | `startup.log` |
| 05:48:13 | 13:48:13 | **人工退出 Creo**：`ProCmdWinCloseGroup` → `ProCmdOSExit`，警告框"未保存的工作将丢失，确认要退出?" 选择是；trail 结束 | `trail.txt.67` 尾部 |
| 06:04:36 | 14:04:36 | 0.6.1 合并提交 `2af3853` | `git log` |

时间线读法：

- **首次异常停止点是 04:30:48 的 `building_worker` 悬挂**（4 分 37 秒无终态），不是 04:36:29 的 `-4`。第一次显式失败记录是 04:36:29.472。
- 04:35:31 的 `ready` 是事故窗口内**唯一一次连接成功**，但 trail 没有对应 IPC 记录。两种解释都无法排除：(a) 2 秒探测的连接/断开在 trail 中不留记录；(b) 该次 ready 指向了当时的另一个会话端点。**因此本次不能用"trail 无 IPC 记录"独立证明连接请求未到达 Creo**——这一条与 BUG-056 的推理前提不同。
- 报告 `startup_queries` 全部属于 `launch_attempt=46`，时间跨度 04:36:23.946 – 04:38:23.210，只覆盖其中一个周期；04:30:48 与 04:35:25 两个周期来自启动协调器日志，不是该报告采集。
- 发布记录与 R1 反馈称"两次 coordinator 重试超时"。`startup.log` 在该窗口记录到 **5 个协调器周期**（04:30:48 静默结束、04:35:25 成功、04:36:23 由报告侧判定超时、04:38:25 与 04:43:18 各记录一次 `timeout`）。由于日志不记录 `retry` 标志，**无法把"两次"逐次对应到具体周期**；口径差异按实记录，不改写文档结论。

## 四、会话身份、进程关系与 GUI 观测

| 项 | 值 | 来源 |
| --- | --- | --- |
| `session_fingerprint` | `8109163335419786528`（四个 job 一致） | job.json |
| `parametric.exe` | PID 20180，创建 2026-10-26T00:07:11.125 796Z，image `C:/Program Files/PTC/Creo 12.4.0.0/Parametric/bin/parametric.exe` | 04:38:23 快照 |
| `xtop.exe` | PID 20164，创建 2026-10-26T00:07:11.802 922Z，18 个顶层窗口 / 1 个可见 / `hung_window_observed=false` | 同上 |
| `parametric` 窗口 | `state=hidden_only`，3 个顶层窗口 / 0 个可见 / **`hung_window_observed=true`** | 同上 |
| 再生进度框 | FEAT-030 记录"隐藏的『重新生成进度』框残留、无可见模态框"；**无截图或窗口枚举原件**，与上行的 `hidden_only`+`hung` 相吻合 | [FEAT-030](../work-items/FEAT-030.md) |
| `creo_session_id` | 空（`selected_session_configured=false`） → worker 的会话核对分支（`ProEngineerConnectIdGet` 比对）未触发，`-4` 直接来自 `ProEngineerConnect` | 报告 `startup_queries`；`native/worker.cpp` |
| 父进程/启动参数 | **缺失**：快照只含 Creo 两进程，无 `ParentProcessId`、无 `nmsd`/`pro_comm_msg` 记录 | — |

**不得用今日进程快照补写**：本次没有读取当前 `parametric`/`xtop`/`nmsd` 进程列表来"确认"事故时状态；上表全部取自 04:38:23 的当次快照。

## 五、与 BUG-056 的异同与判据

对照原件：[BUG-056](../work-items/BUG-056.md)、[DEV-036](../work-items/DEV-036.md)、[核实记录](../validation/BUG-056-DEV-036-investigation-2026-10-17.md)。

| 维度 | BUG-056（2026-10-17） | 本次（2026-10-26） | 判读 |
| --- | --- | --- | --- |
| 错误映射 | `connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20` | 完全相同 | **只证明映射相同。** `exit 20` 是 `connect_creo` 失败后探测分支的固定退出码（`native/worker.cpp` `return result ? 20 : 0`），不代表 worker 崩溃或进程级异常；BUG-085/R1 的"worker 进程级退出"说法不成立为区分依据 |
| 失败速度 | 30 秒预算下 4.8 s 快速返回 `-4`（非 `E_BUSY`、非超时） | 2 秒预算下 5.53 s（04:36:23.946→04:36:29.472） | 都是快速失败，符合"名字服务器层不可读"语义，但仅是同类而非同因 |
| 会话核对分支 | `creo_session_id=""`，分支从未触发 | 同上（`selected_session_configured=false`） | 相同；排除"配置会话不匹配"这一解释 |
| 失败前最后一次成功 | M1 作业 11:36:27 成功 | `14560f1b` 04:30:44.689 成功（trail 04:30:42 最后一次 IPC） | 相同点：都在稳定作业之后突然失效 |
| 失败发生位置 | **作业内**：M2 恢复作业 `connect_creo` `-4` → `unknown_outcome` | **作业外**：连接/启动阶段；04:30:45 之后**没有任何 job 目录生成**，第三轮 `cases={}` | **不同**。本次没有"作业被中断"的风险处置面 |
| Creo 进程 | 存活（PID 18720/24056） | 存活（20180/20164，自 00:07:11 持续至 04:38+） | 相同 |
| GUI / 窗口 | `IsHungAppWindow=false`，无可见弹窗 | `xtop` 未 hung；但 `parametric` `hidden_only` 且 `hung_window_observed=true` | **不同**。本次多出一个"隐藏且 hung"的端点窗口，指向 Creo 侧消息循环/进度框占用，而非纯名字服务问题 |
| 跨批次 nmsd | **已证**：nmsd.exe 06:03Z 上一批次遗留，跨批次存活 15 h+；清理后复测通过 | **未证实**：无 `nmsd` 进程原件（PID/创建时间/父进程全部缺失） | 本次不具备 BUG-056 的核心根因证据 |
| 请求是否到达 Creo | trail 证明失败期无 IPC 初始化 → 未到达 | trail 在 04:30:42 后无 IPC；但 04:35:31 的 `ready` 也无 IPC 记录 → **缺证且自相矛盾** | 本次不能用 trail 缺失作结论 |
| 处置后稳定性 | 清遗留 nmsd + 重启后 38/38 探测、建模闭环、空闲对照通过 | **未处置**（T01 边界）；13:48 人工退出 Creo，之后会话不构成处置复测 | 本次无处置证据 |
| 运行期源码/二进制变更 | 无记录 | 事故窗口内 `native/sketch_edit.cpp` 被修改（`f54cda8` 于 04:36:29 提交），`building_worker` 阶段可能重建并替换 `build/creo_worker.exe` | **本次特有变量，未证实**；BUG-056 无此项 |

判据与结论：

1. 同码 `-4`/exit 20 只落在"错误映射"层，**不进入同根判断**。
2. BUG-056 的根因链是「跨批次遗留 nmsd + trail 证明请求未到达 Creo + 快速 `-4`」。本次三条中只有第三条成立，前两条分别**缺失**和**自相矛盾**。
3. 本次另有 BUG-056 不存在的两个变量（`parametric` 隐藏且 hung、运行期 native 改动/可能重建 worker），在没有排除它们之前不能归并。
4. 因此结论为**证据不足，根因未定**：BUG-085 保持"待复现 / 根因未定"，**不重开 BUG-056**、不清任何保护、不改写 BUG-056 的历史关闭结论。

## 六、未完成清单：four_smooth 编辑闭环 + 13 正例 + 2 负例

0.6.1 驱动 `seed_cases()` 生成 15 个正例（9 个 `matrix_*` 按种子名排序 + 6 个附加）+ 2 个负例；顺序与 [T06 派发表](0.6.1-FEEDBACK-TASKS-2026-10-27.md) 的表格逐项一致。本次逐项对照结果：

| # | 正例 | 0.6.1 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | `matrix_five_smooth` | **完整通过（两次）** | `7c283eaf`+`7f72eba7`（12:27:42/12:27:54）、`471d5301`+`633de212`（12:29:57/12:30:10）；体积 69 220.871→70 471.929，rev 1→2，保存重载 true |
| 2 | `matrix_four_smooth` | **创建通过，编辑未闭环** | 创建 `cf41d9f9`、`6c8ed77b`（32 554.802）；编辑仅 `14560f1b`（datum id 9→25），体积不变 |
| 3 | `matrix_four_straight` | 未执行 | 无 job |
| 4 | `matrix_six_smooth` | 未执行 | 无 job |
| 5 | `matrix_six_straight` | 未执行 | 无 job |
| 6 | `matrix_three_smooth` | 未执行 | 无 job |
| 7 | `matrix_three_straight` | 未执行 | 无 job |
| 8 | `matrix_two_smooth` | 未执行（仅 smoke 创建，不计入） | `49268b14` 为 `--cases seeds` smoke，无编辑步 |
| 9 | `matrix_two_straight` | 未执行（仅 smoke 创建，不计入） | `b4bd95ca`、`cda3ba3f` 同上 |
| 10 | `rectangle_empty_A` | 未执行 | 无 job |
| 11 | `rectangle_explicit_B` | 未执行 | 无 job |
| 12 | `rectangle_empty_C` | 未执行 | 无 job |
| 13 | `rectangle_smooth_empty` | 未执行 | 无 job |
| 14 | `five_rectangle_empty` | 未执行 | 无 job |
| 15 | `five_airfoil_empty` | 未执行 | 无 job |
| 负 1 | `invalid_seed_feature_id`（`seed_feature_id=2147483647`） | 未执行 | 驱动第 218–219 行定义，位于全部正例之后 |
| 负 2 | `interpolation_mismatch`（相反插值） | 未执行 | 驱动第 220–224 行 |

**合计：15 个正例中 1 项完整通过（five_smooth）、1 项仅创建（four_smooth），其余 13 项（上表 3–15 行）未执行；2 个负例均未执行。**"其后 13 个场景"即上表第 3–15 行，与 T06 的 15+2 清单一一对应。空汇总（`cases={}`）不代表通过，`jobs/` 中不存在任何第 3 轮作业原件。

前两轮矩阵的 summary 原件**已丢失**：现驱动固定写 `build/installation_loft_validation.json`（`tools/test_installation_loft.py` 第 66 行），第三轮启动即以空汇总覆盖；磁盘上只剩第三轮这一份（mtime 04:38:24Z）。T06 的 `--output` 唯一目录要求正是为消除这一丢失路径。

## 七、交接

### T04（R20／54°／4×6 原斜槽回放）

- **已有证据**：断连前 04:11Z 的编辑专项 16/16 通过（含 BUG-079/062、legacy、reorder、主平面 autodim 改角/改半径回程），可作为"同一会话、同一源码批、原生命令路径可用"的基线引用；同会话 10 个成功作业的 job.json/native.log 结构可直接作为报告字段模板。
- **仍需人工核对的会话条件**：按 BUG-001 纪律由人确认 GUI 可操作、无初始化告警、无残留模态框；不得用 `--confirm-session-usable`、`session_health`、`ready` 或历史记录代替。本次会话已于 2026-10-26T05:48:13Z 退出，T04 必须在**新会话**上执行，不能假设旧端点已恢复。
- **本次事故给出的额外约束**：运行期间不要修改 `native/**` 或触发 worker 重建；开工前记录 `creo_process_snapshot` 与源码指纹，事后可比对。
- **首次异常停止点**：本次是 04:30:48 的 `building_worker` 悬挂（无 ready/无 timeout），随后 04:36:29 出现 `-4`/exit 20。T04 一旦出现同类征兆（`building_worker` 长时间无终态、或 `not_found_or_unreadable`）立即停止提交，不重试、不重启。

### T06（种子 15+2 独立补验）

- **已有证据**：`matrix_five_smooth` 两轮完整通过；`matrix_four_smooth` 两轮创建成功；`14560f1b` 证明 four 类种子 SECTION datum（id 9）不驱动 Blend，**编辑必须落在 section_1 的真实草图尺寸**（five 用的是 id 37→55，可作对照）。
- **驱动风险**：现驱动固定输出路径会覆盖历史（本次前两轮 summary 就是这样丢的）；T06 必须用 `--output` 新目录，且不得把 0.6.1 的 `five_smooth` 结果挪作本次通过。
- **仍需人工核对的会话条件**：同 T04（BUG-001 纪律 + 新会话 + 人工确认）；矩阵全程串行，异常即停。
- **首次异常停止点**：同上；另外若首个 `matrix_five_smooth` 的创建/编辑任一阶段未在同一源码身份上取得 `saved_file_reloaded_and_verified=true`，后续 14 项不启动。

## 八、缺失材料清单（逐项）

1. **事故时点的 `build/toolkit_health.json`** —— 已被今日探测覆盖（现文件 391 B，mtime 2026-10-27T14:25:17Z）。替代证据：报告内 `startup.native`（04:38:23Z）。
2. **`nmsd.exe`（及 `pro_comm_msg.exe`）的 PID / 创建时间 / 父进程** —— 无任何 2026-10-26 原件；跨批次判断因此不可做。
3. **前两轮矩阵的 summary** —— 固定输出路径被第三轮空汇总覆盖。
4. **三轮驱动 stdout/stderr 与异常栈** —— 未归档（`build/` 下无对应日志）。
5. **事故时点源码指纹** —— 工作区 dirty，`source.sha256`/worker 二进制均为 2026-10-27 08:17Z 重建值；只能用 `83bd7b6`（当时 HEAD）与 `f54cda8`（04:36:29Z 提交）夹逼，且 `native` 快照 `320cedaa…` 是事后回顾值，非当时采集。
6. **`retry=true` 的调用记录与次数** —— 日志无该字段；文档"两次"无法逐次对应（日志为 5 个周期）。
7. **断连时 GUI / 再生进度框的截图或窗口枚举** —— 仅 FEAT-030 文字与 04:38 快照的窗口计数。
8. **事故会话的 `std.err` / `std.out`** —— `build/creo_session` 仅有 2026-10-26T10:49:50Z 的 `std.out`（65 B，属后续会话）。
9. **作业路径的 worker 退出码** —— `job.json` 未保存该字段；只有探测路径记录。

## 九、未测项与边界

- 未创建 MCP 客户端、未调用 `session_status` 或任何 MCP 工具、未连接 Toolkit/Creo、未探测、未故障注入、未自动重连。
- 未处置 Creo（未结束、未重启）、未清 unknown/恢复保护、未对 BUG-078 旧现场 apply、未改动 `session_activity.json` 与 `session_erase/`。
- 未实施 T02–T08；未改 `version.py`、未合 main、未发布、未改生产代码。
- 离线核对完成**不代表连接已恢复**；13+2 补验与稳定性结论仍待 T06/T08 在满足 BUG-001 条件的会话上取得。
- 未定位到需要生产改动的确定根因。若后续确认"运行期重建 worker 与活动通道冲突"，那将是独立的最小修复范围（构建互斥/延后替换），**不在本任务内实施**。

## 十、复核命令（只读，可重放）

```powershell
cd E:\Projects\MCP_CREO_MechDog
# 四个 job 的终态与连接码
Get-Content jobs\471d5301e20b43febb10db36725d5a07\job.json -Raw | ConvertFrom-Json | Select status,stage,created_at,finished_at,revision
# 原生连接阶段与断连
Select-String -Path jobs\471d5301e20b43febb10db36725d5a07\native.log -Pattern 'PHASE=connect|connect_creo|DISCONNECT|result_delivery_complete'
# 空汇总与 -4/exit20 现场
Get-Content build\installation_loft_validation.json -Raw | ConvertFrom-Json | Select success,version,@{n='cases';e={$_.cases.Count}},@{n='jobs';e={$_.jobs.Count}},@{n='state';e={$_.startup.state}},@{n='native';e={$_.startup.native}}
# 协调器状态序列
Select-String -Path "$env:LOCALAPPDATA\MCP_CREO_MechDog\startup\6235eee86323f49c8d99f96a\startup.log" -Pattern '2026-10-26T04:(2|3|4)' | Select -First 20
# trail 中最后一次 IPC 与退出
Select-String -Path build\creo_session\trail.txt.67 -Pattern 'connected to Pro/E|ProCmdOSExit|End of Trail'
```
