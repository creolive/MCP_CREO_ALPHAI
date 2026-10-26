# DEV-047 / T10 会话只读证据诊断离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[BUG-078](../work-items/BUG-078.md)。任务分支：`codex/dev047-t10-session-health`，基线 `1415fdf`（集成分支 `codex/dev047-feedback052`，含 T00—T09）。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。**本轮结论：离线实现完成，实机未验收；未创建 MCP 客户端、未连接 Toolkit、未启动/结束 Creo。**

## 范围与素材边界

本任务只做离线工作：没有创建 MCP 客户端、没有连接 Toolkit、没有启动或结束 Creo、没有会话探测或故障注入、没有清理 unknown 保护，也没有读写三个历史现场的运行登记。`session_health` 的实现只读取已落盘的执行结果；单测使用临时目录夹具，**不实际触碰本机运行数据**。

`docs/validation/` 历史原件、`session_activity.json` 本地修改、未跟踪的 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/` 全部保持原状，未纳入本次提交。

## 现有状态调用与连接边界

按现有代码逐个核对（`server.py`、`creo_startup.py`、`bridge.py`）：

| 公开状态 | 是否主动连接 Toolkit/Creo | 说明 |
| --- | --- | --- |
| `creo_startup_status()` | 否 | 只返回协调器内存快照与 `build/creo_startup/state.json` 的既有结果 |
| `creo_startup_status(retry=true)` | 是 | 启动/复用协调器并在预算内重新探测通道 |
| `creo_session_status` | 是 | `bridge.session_status` 以 2 秒连接预算执行原生 `status` 探针 |
| `creo_callback_status` | 是 | 原生 `callback-status` 探针（9 秒）；仅协调器运行中提前返回 |
| `creo_capabilities` 等静态说明 | 否 | 不读会话 |

因此 `session_health` 只在**不触发新 Toolkit 调用**的 `creo_startup_status()` 路径首次公开，并在 `creo_session_status` 的已完成结果上复用（该工具本身已连接，附加字段不增加任何调用）。没有新增工具，公开注册数仍为 93。

## 接口与实现

新增 `src/creo_mechdog/session_health.py`；`server.py` 只做导入、注册说明与响应适配。

### 证据来源（均为既有结构化结果）

| 来源 | 取出的事实 | 会话身份 |
| --- | --- | --- |
| `jobs/*/job.json` 中非只读终态作业 | 保存结果：`succeeded`（`saved_file_reloaded_and_verified=true`）、`failed`（`failed_stage` 含 save/reload 或 `failed_toolkit_call=ProMdlnameBackup`）、`unknown`（`unknown_outcome`）、`not_attempted`（建模失败未到保存） | `result.session_fingerprint`（原生 `ProEngineerConnectIdGet` 哈希） |
| `jobs/*/job.json` 中只读终态作业 | 连接结果：`connected` / `failed`，附 `connection_state`、`disconnect_code` | 同上 |
| `build/toolkit_health.json` | 最近一次探针的连接结果与 `connection_state`、`checked_at` | 无（由时间归因） |
| `toolkit-owner.lock` | 通道当前登记的持有者（只读，不取锁） | 无 |

只读作业、`session_erase`、`open_file`、`adoption_file` 不作为保存事实；板块创建（无 `kind`）与探针记录没有会话指纹，按时间归因到当时已观测的会话并标记 `session_source="attributed"`，与 `recorded` 区分。读取有界：按 `job.json` 修改时间取最新 120 个目录、单文件 2 MiB、单次合计 8 MiB，超出计入 `jobs_skipped`。证据扫描结果在进程内缓存 5 秒（轮询友好），但状态、年龄、繁忙与时间戳每次重算。

### 状态判定（固定三值）

判定按下列顺序执行，`reason` 给出稳定原因码：

| 顺序 | 条件 | 结果 |
| --- | --- | --- |
| 1 | 没有任何可用证据（目录缺失或从未有终态作业） | `unknown` / `no_evidence` |
| 2 | 有证据但全部不可读（权限/损坏） | `unknown` / `evidence_unreadable` |
| 3 | 最新证据早于 600 秒窗口 | `unknown` / `evidence_expired` |
| 4 | 没有任何已记录会话指纹（身份不明） | `unknown` / `session_identity_unknown` |
| 5 | 会话指纹本身早于窗口（身份未再被观测） | `unknown` / `session_identity_stale` |
| 6 | 当前会话在窗口内存在损坏迹象 | `suspected_damage` / `save_failure` 或 `unknown_outcome_protection` |
| 7 | 当前会话在窗口内有已验证保存 | `no_failure_observed` / `recent_verified_save` |
| 8 | 当前会话在窗口内只有连接/只读事实 | `unknown` / `no_recent_verified_save` |

- 会话身份取**最新一条带指纹的证据**；更早会话的成功不会升级为新会话的结论，冲突时 `session.changed=true` 并给出观测到的会话数（会话重建后旧证据失效）。
- 损坏迹象只按当前会话计；更早会话的失败列为 `historic_damage_signals` 且 `current_session=false`，不因此把新会话判成损坏，也不因此宣称新会话健康。
- “连接成功”只进入 `facts.last_connection`，不构成保存证据；只读查询即使用例也不产生 `no_failure_observed`。
- 权限不可读如实降级为 `evidence_unreadable`；部分不可读时保留结论并在 `evidence.jobs_unreadable` / `evidence.problems` 中记录。
- **繁忙**：`toolkit-owner.lock` 存在时 `facts.channel.busy=true`、`next_steps` 首条为“等待占用作业”，但**不重写状态**——该记录无法与崩溃残留区分，且本查询不会去试锁（试锁可能让真实提交被误判 busy）。这一点在 `facts.channel.note` 中明写。

### 响应结构

`session_health`：`status`、`reason`、`evaluated_at`、`observed_at`、`evidence_age_seconds`、`freshness_window_seconds`、`session{identity, identity_source, identity_observed_at, changed, sessions_observed}`、`facts{last_connection, last_save, recent_saves, channel}`、`damage_signals`、`historic_damage_signals`、`next_steps`、`caveats`、`evidence{jobs_scanned, jobs_unreadable, jobs_skipped, sources, problems}`、`read_only=true`、`toolkit_connections=0`、`guarantee="evidence_only"`。

`next_steps` 按状态给出恢复指引，措辞不出现“健康保证”“自动重启”：

- `unknown`：保留原作业/模型/诊断 → 取得一次只读观测（`creo_session_status`）→ 未确认的作业按 `creo_get_job` + `creo_reconcile_model` 的既有证据处置 → 由操作者人工确认是否需要重建会话。
- `suspected_damage`：保留 → 先持久化 `creo_reconcile_model(mode="inspect")` → 按本次 `available/reason` 选择恢复动作 → 人工确认会话重建 → 重建后重新观测，旧成功不沿用。
- `no_failure_observed`：保留作业直到保存被核实 → 下一次保存仍视为未证明（连接成功或历史成功都不等于下次 `Backup` 成功）→ 若保存失败立即停止并保留现场交 BUG-078。
- 全部状态都声明：不重放 `unknown_outcome` 作业、不自动清保护、不由本服务重启或擦除会话。

### 只读保证

查询路径不取 `toolkit.lock`、不调用 `bridge.session_status`、不构建执行器、不写任何文件。单测以 patch 方式断言 `toolkit_lock`/`session_status`/`build_native`/`write_json` 均未被调用，并对查询前后的临时目录做逐文件 SHA256 比对。

### 契约保留

T02 每输入一条 `index`/`execution_status`/`effect_status`、T03 帧、T04 回读阈值、T05 轴/单位、T06 `profile`/`native_section`、T07 `preview`、T08 `feature_state`、T09 约束回放均未改动；没有新增原生代码，没有改 `version.py`，忙拒/不排队/不重试/unknown 保护不变。

## 恢复流程文档

- [MODEL_RECOVERY.md](../MODEL_RECOVERY.md) 新增“会话健康证据（session_health）”节：三值的含义、证据窗口、只读边界、`unknown`/`suspected_damage` 的用户步骤，并重申不自动重启 Creo、不清保护、不重放作业。
- [BUG-078](../work-items/BUG-078.md) 补本次子项与用户恢复流程摘要，明确本轮结论为“证据诊断与恢复路径交付”，不追加延迟、重试、替换保存接口或主动保存探针。

## 三现场口径核对（只读文档核对，未触碰运行登记）

核对对象：BUG-078 2026-10-22 记录、MODEL_RECOVERY 2026-10-23 补录、FEAT-006 2026-10-24“会话核对”段、本批计划与 DEV-047 基线第 5 节。事实按时间与可核对证据列出，**不改写任何历史记录或现场状态**：

1. **2026-10-22（BUG-078，原始现场记录）**：三个挂起模型（`de6f0bb5…`/`bebe7e2b…`/`57294ff8…`）的 live 已随损坏会话消失；live inspect 显示 baseline SHA 核验通过、owners stopped、**只有 `restore_baseline` 可用**，`accept_live` 因 live not loaded 不可用、`accept_saved` 因无 candidate 不可用；收尾动作待操作者明确选择。
2. **2026-10-23（MODEL_RECOVERY 补录，晚于第 1 条）**：仍写“三个历史挂起模型 live 已缺失、仅 `restore_baseline` 可用：绝不自动 apply 或清保护，等待操作者明确选择后执行”，与第 1 条一致，未记录任何已执行的收尾动作。
3. **2026-10-24（FEAT-006 会话核对段，最晚）**：称“BUG-078 三个旧现场已于 10-22/23 经 accept 动作收口”，同段另称 822 项登记无 `recovery_pending`/`pending_job`、含 unknown 字样的 8 项均为终态。
4. **核对结论**：第 3 条的“经 accept 动作收口”与第 1 条记录的当时可用性直接冲突——10-22 明确记录 `accept_saved`/`accept_live` 均不可用，`accept` 动作在该时点不具备执行条件；`restore_baseline` 不属于 accept。第 3 条的两项登记事实（无 pending、unknown 项为终态）与“现场已不再挂起”相容，但“终态”本身不能证明是**哪一次操作、由谁、何时**收尾，也无法区分 `restore_baseline`、`abandon_new` 或从未保护成功。第 2 条（10-23）仍待操作者选择，进一步说明 10-24 的表述缺少中间证据。
5. **本轮处置**：T10 不据此改写 FEAT-006 或 BUG-078，也不读 `models/*/model.json` 判定现场归属（本轮禁止触碰运行数据做结论），因此三个现场当前状态仍按 BUG-078/总计划记为**待操作者选择、未确认**，未知保护与恢复历史保留。要落定该冲突必须由 T13（或获授权的操作者）在满足会话核对条件后，用一次**只读** `creo_reconcile_model(mode="inspect")` 取得实际 `status`/`pending_job`/`available`/`reason`，再按结果回填；在此之前任何“已收口”结论都不成立。

## 离线验证

环境：Windows 11 x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3（本次无原生改动，未使用）；本机 Creo 12.4.0.0 与匹配 SDK 未参与。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t10_session_health -q` | 19 项通过 |
| `python -m unittest discover -s tests -q` | 937 项通过，耗时 216.432 秒；既有 918 项无回归 |
| 变更 Python 的 `ruff check` / `ruff format --check` | 3 个变更 Python 文件通过；未新增风格基线豁免 |
| `python tools/dev_check.py --work-item BUG-078` | `success=true`、`unit_tests=passed`（937 项）、`native_validation=not_run`；`style_summary` 为既有基线（lint 30、未格式化 16），无新增违规；证据 `build/development_check.json`、`build/t10-devcheck.log` |

dev_check 指纹（`build/development_check.json`）：基线提交 `1415fdf72fe5780dd9e7277f5f64045764099ead`（dirty=true，含本次 T10 源码/文档改动、既有 `session_activity.json` 本地改写与未跟踪运行文件），受测源码 `checked_source_sha256=9a071a21e347a7561d97c97dae498df9b83ff3c1360768f8b8327791992eb1bd`；单元结果 `Ran 937 tests` → `OK`（`build/unit_test_report.json`：tests_run=937、failures=0、errors=0）。

### 新增单测覆盖

`tests/unit/test_t10_session_health.py`（19 项，全部使用临时目录夹具）：

- 状态判定：无证据=`unknown`；历史失败（`save_and_reload` + `ProMdlnameBackup`）=`suspected_damage/save_failure`；`unknown_outcome` 保护=`suspected_damage/unknown_outcome_protection`；新会话（指纹变化）=`unknown/no_recent_verified_save` 且 `session.changed=true`；过期=`unknown/evidence_expired`；身份未再观测=`unknown/session_identity_stale`；无指纹=`unknown/session_identity_unknown`；只读连接不算保存。
- 归因与范围：无指纹的板块保存按时间归因为 `attributed` 并计入当前会话；上一会话的保存失败只进 `historic_damage_signals`，不污染当前会话。
- 证据边界：全部不可读=`unknown/evidence_unreadable`；部分不可读保留结论并计 `jobs_unreadable`；超限清单计入 `jobs_skipped`。
- 繁忙：`toolkit-owner.lock` 存在时 `facts.channel.busy`/`owner`/`note` 与首条 `wait` 指引齐备，且不重写状态；有损坏时保持 `suspected_damage`。
- 只读结构断言：查询前后逐文件 SHA256 不变；`toolkit_lock`/`session_status`/`build_native`/`write_json` 均未被调用；`read_only=true`、`toolkit_connections=0`；缓存命中时年龄仍按当前时间重算。
- 措辞：三值集合固定；不出现“健康保证”“自动重启”；`guarantee=evidence_only`。

## 未测范围（本次未执行）

1. 真实会话上的 `session_health` 表现：本机 Toolkit 连接保持冻结，`no_failure_observed` 需要一次真实的已验证保存后由 MCP 客户端观测，未取得。
2. 真实 `session_fingerprint` 变化（会话重建）对状态的端到端影响：只有夹具覆盖，未在实机重建会话（禁止项）。
3. 权限拒绝、文件占用、部分不可读的真实 Windows 场景：仅以 patch 注入覆盖，未做真实注入。
4. 三个历史现场的当前实际状态：按本轮纪律未读运行登记、未 inspect，冲突仅按文档时间线核对；结论为“未确认”，交 T13。
5. 状态响应进入真实 MCP 客户端（stdio）后的序列化与体积：仅经全量单测中的既有 server 路径间接覆盖，未做客户端黑盒。
6. 外部 Creo 9/10 与 WorkBuddy 本轮未执行；本机通过不外推到其他版本或客户端。

本次验收结论：**T10 离线实现完成，实机未验收**。`session_health` 已在不产生新 Toolkit 调用的状态路径公开并在已完成探测结果上复用；证据三值、会话身份绑定、过期/权限/繁忙表达、恢复指引与只读保证均已离线落地；BUG-078 本轮交付结论为证据诊断与恢复路径，未追加延迟、重试、替换保存接口或主动保存探针。
