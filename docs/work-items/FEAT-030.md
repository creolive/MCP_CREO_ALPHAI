# FEAT-030：区分种子文件有效性与原生加载兼容性

日期：2026-10-16。类型：能力。优先级：P2。状态：已验收（未收口）（2026-10-28 T06 实机 15+2 于单一受测源码全部通过；未测范围见文末）。目标版本：未排期。

2026-10-20 按用户确认的 0.3.7 剩余计划实施：生产版本无来源则 null；普通查询明确只验证文件/哈希，附按种子 SHA256、实际原生 release_numeric 和 session_fingerprint 绑定的历史加载记录。真实创建链路记录加载 API 状态，不新增隐式连接或主动探针。记录保存为本机 build 诊断数据；写诊断失败不得改变已完成建模终态，必须在返回中明示。新增字段、未测环境与实机证据分别核对。

6 项新增隔离单测、全量 455 项单元、增量检查与匹配 SDK 构建通过；实机加载证据因会话就绪失败未取得，Creo 9 加载问题仍开放。详见[本轮验证记录](../validation/FEEDBACK-0.3.7-IMPLEMENTATION-2026-10-20.md)。下文历史日期的未实现描述保留其当时状态。

同日续做通过实际 MCP_CREO_MechDog_dev 只读核对 list 与全部九个 validate：哈希有效、生产版本null、当前原生兼容未验证、无历史加载记录，公开根路径为E盘。无隐式原生加载，非WorkBuddy或加载验收；最新全量458项通过。原始返回保存在build/feedback037-public-readonly-followup.json，范围见本轮记录。

来源：[Creo 9 / 0.3.0 报告](../validation/feedback-2026-10-16/2026-10-15_CREO_0.3.0_叶片种子加载失败与筋特征失败.md) P0-1 检测盲区；[补录](../validation/FEEDBACK-2026-10-16.md)。关联 BUG-034、FEAT-008、DEV-005/006。

目标：list/validate/install 现有 available/哈希信息不应被理解为当前 Creo 原生可加载。评估独立可选的原生加载探针或清晰的兼容状态、种子生产版本及证据；不能在普通元数据查询中隐式加载全部模型或假定文件头足以判兼容。

范围待细化：字段与旧调用兼容、未知/未验证/可加载/不可加载、测试环境与时间/指纹、种子来源变化或会话变化后的失效；原生探针只使用自有隔离副本并有界等待，不改原种子或用户模型、不清理未知对象。具体接口和缓存方案未定，不据此承诺种子在 Creo 9 原生可加载；整体有限支持定位见 [兼容矩阵](../COMPATIBILITY.md)。

验收：纯文件校验无会话仍可用且明确原生未验证；会话不可用/探针超时不误报兼容，保留错误与下一步；可加载/加载失败的受控夹具状态可区分，已验证结果绑定具体环境和种子指纹，普通查询载荷有界。若实际执行探针，确认原件哈希不变、只回收自有测试对象、用户模型/revision 不变，并保留完整返回和后续建模可用性证据。

后续在 Windows x64 / 本机 Creo 12.4 / 匹配 SDK 做适用开发检查和隔离加载实机验证；旧版不兼容夹具若无法取得，只记录未测，不将模拟错误当真实版本兼容结论。本次未实现或测试。

## 2026-10-16：0.3.2 / Creo 9 复现证据

[0.3.2 报告 B](../validation/FEEDBACK-0.3.2.md) P0-1 复现两截面种子 `ProMdlFiletypeLoad=-16`，且 `creo_list_seeds`/`creo_validate_seed` 仍只校验哈希并显示 `available: true`，检测盲区与上一轮一致；报告未提供种子 ID、作业/模型标识与源码身份。该证据不改变本卡"不承诺 Creo 9 运行时支持"的边界，探针与状态字段方案仍待细化。

## 2026-10-17：0.3.4 种子生产版本与兼容元数据建议

[Creo 9 / 0.3.4 报告](../validation/FEEDBACK-0.3.4-2026-10-17.md)再报种子原生加载 -16，但 9 个 PRT 哈希有效且 available。生产版本字段（如 seed_build_version）及按种子/环境的已测兼容状态沿用本项，不重复建卡；字段须有可追溯生成或原生证据，无来源时明确未知。

报告建议直接宣称全部由 Creo 12.4 构建、Creo 9/10 无法加载，本轮不采为已证实支持结论：摘要不变和单一 Creo 9 失败不足以证明生产版本或全部目标环境不可用。BUG-034 继续核实实际失败，本项仍待规划，普通 list/validate 不隐式执行加载探针。

## 2026-10-17：0.3.4 Creo 10 三截面种子正例

[0.3.4 / Creo 10 报告](../validation/FEEDBACK-0.3.4-CREO10-2026-10-17.md)在 Creo 10.0.0.0 实测三截面自动匹配混合 succeeded（体积 22159.999999999996、`saved_file_reloaded_and_verified=true`），与同日 Creo 9 加载 -16 形成环境对照。该正例支持"不由哈希或单一环境失败推断全部种子不可加载"的既有口径，也为本项未来的按环境兼容状态提供 Creo 10 数据点；无 job/model 标识，不外推为完整 Creo 10 运行时验收或全部九个种子在该环境可加载。

## 2026-10-23 外部 Creo 9 证据补录（第八/九轮，2026-10-25 归档登记）

- 环境：外部 Windows 10 / Creo 9.0.0.0（release 41）/ 服务 0.5.0、0.5.1。
- 外部环境观察：Creo 9 会话种子加载 -16 持续复现（叶片与种子放样同病，详见 [BUG-034](BUG-034.md)）；另有 Creo 10 三截面种子放样成功的历史记录——两者分开记录，不写"所有种子在 Creo 10+ 可加载"，也不写未经证实的最低 Creo 要求。
- UGC 头与生产版本为待核实线索：2128/2023/1934 与产品版本对应未获可追溯证明，不建立 2128=12.4 等映射；来源不足时 `seed_build_version` 继续为 null。
- 0.5.3 计划范围（未实施）：list/validate 的 available 只表示文件及哈希有效，不代表当前 Creo 可加载；loft/airfoil 加载失败保留原始 API、错误码、实际阶段、种子标识/哈希与可取得的运行版本，不硬写"由 Creo 12.4 构建，当前版本无法加载"；capabilities/种子说明/兼容矩阵写明"外部 Creo 9 已报告受测种子 -16；另有 Creo 10 三截面成功历史；当前会话/其他种子未验证"。归档见 [feedback-0.5.0-0.5.1-2026-10-23](../validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)。

## 2026-10-25：来源与兼容信息透明化实现（开发分支，未做实机连接）

实现范围（Python 侧，未改原生 C++，无需重新编译执行器）：

- `src/creo_mechdog/seed_compatibility.py`：来源解析与加载失败诊断。
  - 生产版本只接受两种来源，且都必须与**实际种子 SHA256** 绑定：`docs/seed_manifest.json` 中的可追溯生成记录（`seed_build_version` + `sha256` 一致才采纳），或 `build/seed_provenance/<sha256>/` 下由原生会话写下的证据记录（`record_native_build_evidence()` 写入，需 `row["seed_sha256"] == digest`）。文件字节变化后来源不归属，`seed_build_version` 回到 null、`seed_build_version_status` 回到 `unknown`。
  - UGC 头解析为 `seed_file_diagnostic.ugc_part_version_token`（首行 `#UGC:2 PART 2128 …`），`ugc_interpretation` 固定为 `unverified_clue`；不建立 2128=12.4 之类映射，也永不用于填 `seed_build_version`。
  - `load_failure_diagnosis()` 保留原始 API（`ProMdlFiletypeLoad`）、错误码、实际阶段（`failed_stage`）、种子标识与 SHA256、可取得的运行版本（`creo_release_numeric` / `creo_release_query_code` / `session_fingerprint`）与原生消息原文，并给出核对兼容性与来源的提示。只有当存在绑定该 SHA256 的来源记录且其 release 高于当前会话 release 时才给出有界的 `version_incompatibility`（`cause = recorded_release_newer_than_session_release`），否则 `cause = undetermined_by_error_alone`。
  - 加载成功与后续建模成功分别记录（`seed_load_succeeded` / `modeling_succeeded`）；历史加载记录按种子 SHA256 隔离，只说明别的会话发生过什么，`native_compatibility.status` 恒为 `not_verified_for_current_session`。
- `seeds.py`（根兼容包装）：`list_seeds()` / `validate_seed()` 增加 `available_scope`、`native_load_probe`（`not_performed`）与 `compatibility_evidence`；`available` 判定改为"实际文件哈希 == 清单哈希"，来源与历史随实际字节走；新增 `manifest_entry_by_digest()`。
- `generic_bridge.py`：放样/翼型任务提交时对种子副本计算 SHA256 并绑定清单条目（`snapshot_sha256` / `seed_name` / `seed_manifest_sha256` / `seed_source`）；任务收尾调用 `observe_load()` 写加载证据，失败时把诊断并入终态消息（`native_message` 保留原生原文）。诊断写入失败不改变建模终态，原因留在 `seed_load_evidence.evidence_error`。
- `capabilities.py`：`seed_library` 与 `loft_seed` 族增加 `available_scope` / `native_load_probe` / `compatibility_evidence` / `production_version` / `load_failure_diagnosis`。
- `server.py`：`creo_list_seeds`、`creo_validate_seed`、`creo_new_loft_part`、`creo_new_airfoil_blade` 的说明写明 available 只代表文件字节、普通查询不建立 Toolkit 连接也不试载、失败诊断口径，且不承诺最低 Creo 版本。
- 文档：[兼容矩阵](../COMPATIBILITY.md)、[种子库说明](../SEED_LIBRARY.md)、[放样种子说明](../LOFT_SEED.md) 均写明"外部 Creo 9 已报告受测种子 -16；另有 Creo 10 三截面成功历史；当前会话/其他种子未验证"，不写未经证实的最低 Creo 要求或笼统"Creo 10+ 已验证"。

本轮为开发分支改动，**未连接 Creo 会话、未做实机建模与保存重载**：加载成功与后续建模成功的实机核对留给回归收口任务。种子库重生成是另列的环境受阻子项，本机无匹配旧版生成/验收环境，未承诺完成，也未新增双版本发布门槛。新增 17 项隔离单测、全量 585 项单元与 `tools/dev_check.py` 通过；证据见[本轮验证记录](../validation/FEAT030-BUG034-SEED-TRANSPARENCY-2026-10-25.md)。

## 2026-10-25 阶段三验收证据（收口，实机种子加载）

环境：主仓 dev 环境，Windows 11 x64 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 SDK / Python 3.12.14；集成尖 `e2bba08`，受测指纹 `checked_source_sha256=da558d9e…b28b5f0`。命令与偏差见[阶段三收口](../validation/PHASE3-CLOSEOUT-2026-10-25.md)。

- 实现摘要：来源与兼容信息透明化已随 `e2bba08` 进入集成尖（`seed_compatibility.py`、`seeds.py` 包装、`generic_bridge.py` 证据写入、`capabilities.py` 与文档），本轮不新增字段，只做**实机取证**。
- 本次证据（`-m tools.test_feedback037_modeling --cases seeds`）：
  - `seed_straight`（种子 `two_straight`，sha256 `7d2dbeb4…aa61f5f2`）：job `d161f855adac4c279c3630c74d9f95df` / model `97f2b13d1d8c46c29a34312b9a01d22d`，`revision=1` 成功，体积 **5131.268000863329**（=4900π/3）、`inspection_source=saved_reloaded`、`seed_native_load=loaded`、`seed_load_evidence.status=loaded`、`evidence_persisted=true`，保存重载 true。
  - `smooth`（种子 `two_smooth`，sha256 `865204be…6c14b0518`）：job `fe8bf5ed89c54de0bd50fcdfbefd97d8` / model `d67cd032a25e4457b38ea0698be2f6fa`，成功，`seed_load_evidence.status=loaded`、`evidence_persisted=true`、`modeling_saved_reloaded_verified=true`，体积 5131.268000863329。
  - `creo_validate_seed(two_smooth)`：`available=true`、`native_status=not_verified_for_current_session`、`observation_job_ids` 含本次作业（`fe8bf5ed…`、`7e2c0273…`）、`seed_build_version=null`、`seed_build_version_status=unknown`、UGC 头 `#UGC:2 PART 2128 …` 仍为 `unverified_clue`。
- 偏差：该脚本在 `seed_straight` 之后因 `KeyError('inspection')` 退出 1——字段已改名 `inspection_summary`，属测试脚本过期，**不是建模失败**（作业终态为 succeeded、保存重载 true）；`smooth` 与 validate 另行执行成功。
- 未测范围：生产版本仍无可追溯生成记录（UGC 值不建立版本映射）；Creo 9/10 等其他环境的实际加载未复验（Creo 9 -16 归 [BUG-034](BUG-034.md)）；9 种子安装库回归与种子重生成未执行。因此保持“验收中”，不迁入完成档案。

## 2026-10-26：测试驱动修复与九种子矩阵部分实证（0.6.0 基线反馈计划 Task 3）

- **驱动修复**（离线 20 项单测过，`tests/unit/test_seed_regression_contract.py` 新建）：`tools/test_installation_loft.py` 经 `native_result_details`（`inspection_refs.full_inspection` + `model_registry.aliases_of`）读取完整 inspection/aliases，基础矩阵由 manifest 驱动（9 个 `matrix_*` 场景 + 6 个既有附加场景），mismatch 负例改为与所选种子相反插值；`tools/test_feedback037_modeling.py` 的 seeds 体积断言改读 `inspection_refs.summary_of`，补 ROOT 路径插入；observations 断言改为尊重有界历史（registry 仅保留按记录名序最近 2 条，新作业可能合法地不在列，本次加载证据以作业自身 `seed_load_evidence` 为准），并给安装驱动补 `wait_for_startup`。
- **实机部分证据**（Creo 12.4.0.0 会话，修复批同源码）：`--cases seeds` 两种子 smoke 通过（`seed_straight` job `cda3ba3f…`、`seed_smooth` job `49268b14…`，volume 4900π/3 断言经 summary 读取通过）。安装矩阵执行至第 2 场景：`matrix_five_smooth` 完整通过（blend id 93、revision 1→2、体积 69220.871→70471.929、创建与编辑保存重载 true、源件哈希核对通过）；`matrix_four_smooth` 创建成功（job `6c8ed77b…`，blend id 82、体积 32554.802），并实证**种子行为差异**：four 类种子的 SECTION_n_PLANE datum 尺寸（10/20/30）不镜像请求 offsets（0/20/40/60）且不驱动 Blend（平面尺寸 +5 后体积不变），驱动已改为编辑 section_1 草图的真实非零尺寸。
- **环境受阻**：第三次矩阵重跑时 Toolkit 通道断开（worker exit 20、`connection_state=not_found_or_unreadable`，coordinator 两次显式 retry 均超时；xtop 主窗口在、隐藏"重新生成进度"框残留、无可见模态框；通道断开前最后一轮完整作业为编辑专项 16/16）。按 BUG-001 纪律未处置 Creo。按驱动清单重新核数：共 15 个正向场景（9 种子 + 6 附加），仅 matrix_five_smooth 完整通过；matrix_four_smooth 尚缺编辑闭环，其后 13 个正向场景及 2 个负例待会话恢复后补跑；作业级证据保留于 `jobs/471d5301…`、`633de212…`、`6c8ed77b…`、`14560f1b…`。
- 种子重生成与生产版本来源不变（仍环境受阻/无绑定记录）；本节不改变 `available` 语义与 `seed_build_version=null` 口径。

## 2026-10-28：DEV-049 T06 离线阶段（种子驱动证据边界收紧，实机 15+2 未执行）

- 范围（仅离线，未连接 Toolkit/Creo）：按 [0.6.1 派发表 T06](../development/0.6.1-FEEDBACK-TASKS-2026-10-27.md) 收紧 `tools/test_installation_loft.py` 的执行/证据边界：默认离线、实机双门槛（`--live --confirm-session-usable`）、可重复 `--case` 与 `--output`、默认输出 `build/dev049_t06/<run_id>/report.json` 且拒绝覆盖旧报告、逐次持久化输入/job ID/分阶段终态、无自动重放与 resume、跨源码指纹报告不合并；负例 `invalid_seed_feature_id`、`interpolation_mismatch` 改为显式新建 two_straight 基础输入并仅改一个字段。
- 离线核对：manifest 与 9 个种子 SHA256 全部一致（`compatible_server_version=0.7.1`），15 正例按派发表固定顺序与 2 负例输入全部构建并校验；专项回归 `tests.unit.test_seed_regression_contract` + `tests.unit.test_mcp_readiness` 共 31 项通过（新增 24 项），离线驱动默认路径已跑通并生成新 run_id 报告，`tools/dev_check.py --skip-unit --work-item DEV-049` success=true。
- **本节不改变本卡验收状态**：15 正例创建+真实尺寸编辑闭环与 2 负例的实际拒绝/回滚证据均未取得，历史 0.6.1 的 five_smooth 结果不作为本次通过；实机补跑待用户指派并按 BUG-001 纪律人工确认会话后串行执行。详见 [DEV049-T06-ACCEPTANCE.md](../development/DEV049-T06-ACCEPTANCE.md)。

## 2026-10-28：DEV-049 T06 实机补验——15+2 全部通过（验收状态更新）

- 用户人工确认会话可操作后（2026-10-28 上午，2026-10-27 21:21 新会话），`tools/test_installation_loft.py --seed-library .\seed_library --live --confirm-session-usable` 串行完成全部 17 例，exit 0。run_id `20261028T094752_93168e17`，报告 SHA256 `8275d37842fa3c489a51604a5cf02aff9fe63479b12b95245feabc924dcef018`，provenance commit `5c03b10`（集成分支）、source_fingerprint `c2007bb1…`。
- **15 正例在同一受测源码身份上一次取得**：创建/编辑双作业保存重载、编辑体积变化 >0.01 mm³、源种子 SHA256 不变、revision 递进五项硬校验各 15/15（示例 five_smooth 69220.871→77170.616 mm³，创建 job `df9c1bff…`、编辑 job `cae2d341…`）。**2 负例** `invalid_seed_feature_id`、`interpolation_mismatch` 均在 `native_execution` 阶段按预期拒绝，原始错误保留，未伪称保存成功。
- 2026-10-26 阻断清单就此收口：four_smooth 编辑闭环及其后 13 正例、2 负例全部补齐；未挪用 0.6.1 历史 five_smooth 证据。派发表 T06 的实机闭环条件（15+2 于同一受测源码）已满足。
- **状态：本卡矩阵范围转为已验收（未收口）**；未测范围不变（生产版本无生成记录、Creo 9/10 实际加载、种子重生成），`available` 与 `seed_build_version=null` 口径不变。详见 [DEV049-T06-ACCEPTANCE.md 第六节](../development/DEV049-T06-ACCEPTANCE.md)。
