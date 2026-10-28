# DEV-049 T06 验收记录：种子驱动证据边界收紧与 15+2 清单离线验证（离线阶段，2026-10-28）

任务：[DEV-049](0.6.1-FEEDBACK-TASKS-2026-10-27.md) T06（离线阶段）。上游交接：[DEV049-T01-ACCEPTANCE.md](DEV049-T01-ACCEPTANCE.md) 第七节。

**结论先行：离线阶段完成，实机 15+2 未执行。** 本次只收紧 `tools/test_installation_loft.py` 的执行/证据边界并离线核对 manifest、9 个种子 SHA256、15 正例与 2 负例输入。未创建 MCP 客户端、未连接 Toolkit/Creo、未提交任何建模作业。0.6.1 的 `matrix_five_smooth` 历史成功不作为本次通过，FEAT-030 验收状态不变。

## 一、交付身份与环境

| 项 | 值 |
| --- | --- |
| 任务分支 | `codex/dev049-t06-seed-matrix`（自集成分支 `codex/dev049-feedback061` 建立） |
| 依赖提交（开工基线） | `38521324207239a610fd46953be04efc30b2ab8a`（DEV-049: integrate T05 input-gap review） |
| 工作区状态 | dirty：`M session_activity.json`（本机运行数据，未读取业务内容、未提交、未 stash、未 checkout）；未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/*` 等运行数据，全部未提交 |
| 核对时段 | 2026-10-28 00:45–00:55（Asia/Shanghai）/ 2026-10-27T16:45–16:55Z（UTC） |
| 环境 | Windows 11 Enterprise x64；Python 3.12.14（`.venv`）；Creo 12.4.0.0 / 匹配 SDK 在机但**未连接、未探测**；Ruff 0.17.0 / clang-format 23.1.3 |
| 受测源码指纹 | 驱动 `provenance.source_fingerprint = 1c022cd091f733872d38b527835327259a547ea06e8ce6af0a83347a76221537`（覆盖全部 git 跟踪 *.py 与 native C++ 头/源，含本次两文件）<br>`tools/dev_check.py --skip-unit` 的 `checked_source_sha256 = d02b1f2e9924c788d4868004cc804ee9894c381be474e739260dd29d430e6111` |

## 二、本次改动（仅两个文件）

- `tools/test_installation_loft.py`：按 T06 契约重写执行/证据边界（保留 `native_result_details`、`seed_cases` 的既有签名与语义，现按派发表固定顺序返回）。
- `tests/unit/test_seed_regression_contract.py`：保留原 4 项，新增 24 项离线契约回归。

未改生产实现、未改原生 `native/**`、未改 `version.py`（仍 0.7.1）、未合 main、未发布、未动 `session_*` 运行数据、未实施 T07/T08、未新增 MCP 工具。

### CLI 契约落地

| 契约 | 实现 |
| --- | --- |
| 保留 `--seed-library` | 保留，仍是必填 |
| 默认离线 | 不给实机开关即离线：不实例化 MCP 客户端（`mcp` 仅在 `live()` 内惰性导入），只做 manifest/哈希/输入校验并写报告 |
| 实机双门槛 | 必须同时 `--live --confirm-session-usable`；单独任一开关仍走离线并打印原因，单测用会抛错的假 `mcp.Client` 证明不会连接 |
| 新增 `--case NAME`（可重复） | 选择未做项，按派发表顺序执行；未知名称、同一名称重复在**连接前**以退出码 2 拒绝（`REFUSED BEFORE CONNECTION`）；每次运行创建新独立模型（`model_name=t06_<序号>_<run_tag>`，run_tag 来自 run_id） |
| 新增 `--output PATH` | 默认 `build/dev049_t06/<run_id>/report.json`；启动时（连接前）拒绝覆盖任何已存在报告，退出码 2 |
| 不做自动重放 / resume | 无 resume、无自动重提：`submit/admit` 对同一 case key 只受理一次，超时或未知终态只记录并提示人工检查，不重提 |
| 逐次持久化 | 受理前持久化输入，受理后立刻持久化 job ID，创建/编辑每阶段终态即时写盘；异常经 `finally: save()` 保留报告 |
| 不同指纹不合并 | `CROSS_REPORT_POLICY` 写入每份报告；`summarize_reports()` 对 `provenance.source_fingerprint` 不一致的报告直接拒绝合并 |

### 边界收紧对照（T01 交接要点）

- **four 类必须改真实草图尺寸而非 SECTION datum**：多截面（3/4/5/6 截面）编辑固定取 `section_1` 的**非零草图尺寸** `set_dimensions`；两截面沿用 TOP_PLANE 驱动尺寸（0.6.1 已证有效）。
- **固定输出路径覆盖历史**：已消除——默认输出改为唯一 `build/dev049_t06/<run_id>/report.json`，旧的 `build/installation_loft_validation.json` 不再写。
- **不得挪用 0.6.1 的 five_smooth 结果**：报告声明本次不承载历史证据；实机阶段必须在同一受测源码指纹上重新取得 `matrix_five_smooth` 创建+编辑闭环。
- **首个 five_smooth 未闭环不启动其余 14 项**：实机 `run_all()` 在 `matrix_five_smooth` 失败时记录 `five_smooth_gate=not_closed` 与 `stopping_reason` 并停止后续提交。
- **有界只读等待**：沿用 `tools/mcp_readiness.wait_for_startup`（只读 `creo_startup_status`，130 s 有界），不使用 `retry=true`。

## 三、离线验证结果

### manifest 与 9 个种子 SHA256（全部一致）

`seed_library/seed_manifest.json`（`compatible_server_version=0.7.1`，与 `version.py` 一致）逐项核对；每个种子文件存在、路径安全（无绝对路径/无 `..`）、字节数与 SHA256 与清单一致：

| 种子 | SHA256（与 manifest 一致） |
| --- | --- |
| two_straight | `7d2dbeb4f3bea4839b6501e31110573bfc752a0033f72039f8230b6aa61f5f2` |
| two_smooth | `865204bea18f5098342e97a5fadb670e27cdd10a174cb7c45e2192e6c14b0518` |
| five_smooth | `818c1e8c364725aeb1a37e6e1f9ff6424baf4a3b16e2b75cc7a93c4c3c9148b5` |
| three_straight | `e93d2870467363567cfb938c73875019b8d61be33d4b0c2965e6e69d15860b05` |
| three_smooth | `0334374eab104bb2355129da243403a8681b6a1d9246b3285706e46ef3070d9e` |
| four_straight | `487ec48bb9b9046eae7b916e444438b8224bda4326b1776d42c2f9c1450a9b5f` |
| four_smooth | `fff48c00adc53cf1377203b6f3cc6482b362d53cd63473be7eaed27e28258fb5` |
| six_straight | `5e3c31948e01ecc0525a86910d47fd62f30a08a5efad557003a3ea4f5358f03b` |
| six_smooth | `a199fa1df46af34a15ceba93f7e076ab7b49288885ae405329539daa6ecc476f` |

### 15 正例 + 2 负例清单核对（与派发表 T06 表逐项一致）

顺序固定为派发表顺序（单测以字面表断言，不依赖排序函数）：

| 序号 | 正例 | 基础种子 | 截面 | 插值 | 本次离线状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | matrix_five_smooth | five_smooth | 5 | smooth | 输入已构建并校验；**实机未执行** |
| 2 | matrix_four_smooth | four_smooth | 4 | smooth | 同上 |
| 3 | matrix_four_straight | four_straight | 4 | straight | 同上 |
| 4 | matrix_six_smooth | six_smooth | 6 | smooth | 同上 |
| 5 | matrix_six_straight | six_straight | 6 | straight | 同上 |
| 6 | matrix_three_smooth | three_smooth | 3 | smooth | 同上 |
| 7 | matrix_three_straight | three_straight | 3 | straight | 同上 |
| 8 | matrix_two_smooth | two_smooth | 2 | smooth | 同上 |
| 9 | matrix_two_straight | two_straight | 2 | straight | 同上 |
| 10 | rectangle_empty_A | two_straight | 2 | straight | 同上 |
| 11 | rectangle_explicit_B | two_straight | 2 | straight | 同上 |
| 12 | rectangle_empty_C | two_straight | 2 | straight | 同上 |
| 13 | rectangle_smooth_empty | two_smooth | 2 | smooth | 同上 |
| 14 | five_rectangle_empty | five_smooth | 5 | smooth | 同上 |
| 15 | five_airfoil_empty | five_smooth | 5 | smooth（翼型截面） | 同上 |

| 序号 | 负例 | 显式构造 | 本次离线状态 |
| --- | --- | --- | --- |
| 负 1 | invalid_seed_feature_id | 显式有效 two_straight 基础输入 + `seed_feature_id=2147483647`，与基础输入仅此一处差异 | 输入已构建并校验差异字段；实机未执行 |
| 负 2 | interpolation_mismatch | 显式有效 two_straight 基础输入 + 请求 `interpolation="smooth"`（种子为 straight），仅此一处差异 | 同上 |

负例基础输入由 `negative_base_args()` **每次现建**（fresh two_straight 输入，两截面矩形、无尺寸），不依赖上一循环遗留的 `args`；单测以“污染上一次循环产物后重建”“两次调用对象互不影响”“偏离基础输入即拒绝”三种方式证明。

## 四、命令与结果

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_seed_regression_contract tests.unit.test_mcp_readiness -v
# Ran 31 tests in 1.925s — OK（test_seed_regression_contract 28 项：原有 4 + 新增 24；test_mcp_readiness 3 项）

.\.venv\Scripts\python.exe tools\test_installation_loft.py --seed-library .\seed_library
# OFFLINE ONLY (no live flags given): no MCP client, no Toolkit call, no Creo connection.
# manifest_seed_count=9 hashes_verified=9
# positive_cases=15 negative_cases=2 validated
# report=E:\Projects\MCP_CREO_MechDog\build\dev049_t06\20261028T005301_a3cd7992\report.json
# LIVE NOT RUN: no 15+2 native result was produced or claimed.

.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-049
# success=true；unit_tests=not_run；unit_test_timeout_seconds=900；
# style_summary: lint_findings=30 / unformatted_files=16（均为既有基线，无新增诊断，本次两文件已格式化）
```

离线驱动证据：`build/dev049_t06/20261028T005301_a3cd7992/report.json`（run_id `20261028T005301_a3cd7992`，132 398 B，SHA256 `aff59ad35642244e94f85254e90f9038e0a9d02c40d10a99ff4ecfc019d922a7`）。报告含 `mode=offline`、`live_run=false`、`native_acceptance=not_run`、15+2 输入全文、9 个种子哈希、`manifest_matches_server_version=true` 与 `provenance`（commit `3852132`、branch `codex/dev049-t06-seed-matrix`、dirty=true、source_fingerprint `1c022cd0…21537`）。同路径下另有一个格式化前的中间报告目录已被移除，避免指纹不一致的重复证据；本节引用的报告由最终提交源码生成（其文件内容哈希与交付源码一致）。

## 五、未测项与边界

- **实机 15+2 全部未执行**：15 正例的创建+真实尺寸编辑闭环、2 负例的实际拒绝阶段/原始错误/回滚与保护，均待用户指派实机并按 BUG-001 纪律人工确认会话可操作后串行补跑；本次不解除 FEAT-030 的验收状态。
- 历史 0.6.1 的 `matrix_five_smooth` 通过、`matrix_four_smooth` 创建成功均为**别的源码指纹/别的会话**证据，未移植为本次通过。
- 未创建 MCP 客户端、未实例化 `mcp.Client`、未调用任何 MCP 工具、未连接 Toolkit/Creo、未启动/结束/重启 Creo、未清 unknown/保护、未探测、未故障注入、无 `retry=true`。
- 未自动重放旧作业、未实现 resume；未做跨报告合并。
- 未改生产/原生实现、未改 `version.py`、未合 main、未发布、未动 `session_activity.json` 与 `session_erase/`；T07/T08 未实施。
- 外部 Creo 9/10 环境、种子库重生成、9 种子在其他会话的原生加载继续未测（沿用 FEAT-030/BUG-034 既有口径）。

## 六、2026-10-28 实机阶段：15+2 全部通过（单源码单会话闭环）

**会话核对（本次人工）**：与 T04 同日上午同一会话（2026-10-27 21:21 本地启动），用户亲眼确认 GUI 可操作、无初始化告警后执行；未以 ready/`session_health` 替代。T04 六例失败但回滚干净、通道正常释放后串行开始本任务。

**命令与结果**：`.\.venv\Scripts\python.exe tools\test_installation_loft.py --seed-library .\seed_library --live --confirm-session-usable` → exit 0，`native_acceptance=recorded`。run_id `20261028T094752_93168e17`，报告 SHA256 `8275d37842fa3c489a51604a5cf02aff9fe63479b12b95245feabc924dcef018`；provenance：commit `5c03b106…`（集成分支 `codex/dev049-feedback061`）、dirty=true、source_fingerprint `c2007bb1…`。dirty 项为当日 T04 驱动编辑（`tools/test_dev049_tilted_cut.py` 及其单测），不在本驱动与生产路径上，如实记录。

**15 正例（15/15 全过，同一源码身份一次取得）**：`create_saved_reloaded_verified`、`edit_saved_reloaded_verified`、`volume_changed_by_edit`（>0.01 mm³）、`seed_sha256_verified`（源种子哈希不变）、`edit_revision > create_revision` 五项硬校验各 **15/15**。示例 `matrix_five_smooth`：创建 job `df9c1bffc2724ed1af6f2a9e2feef610`、编辑 job `cae2d341adf240ea87f3ebcf6faaca63`，体积 69220.871→77170.616 mm³（真实草图尺寸编辑生效）。0.6.1 历史的 five_smooth/four_smooth 证据未被挪用。

**2 负例（按预期拒绝，原始错误保留）**：`invalid_seed_feature_id`（two_straight 基础输入 + `feature_id=2147483647`）在 `native_execution` 阶段被拒，原始错误 `Toolkit call ProFeatureInit((ProSolid)board, binding.at("feature_id"), …)`；`interpolation_mismatch`（相反插值）在 `native_execution` 阶段被拒，原始错误 `Seed Blend interpolation does not match requested interpolation`。两例均未伪称保存成功。

**FEAT-030 状态**：派发表 T06 的实机闭环条件（15 正例 + 2 负例在同一受测源码身份上取得有效证据）已满足，[FEAT-030](../work-items/FEAT-030.md) 按当日阶段记录更新为已验收（未收口）；未测范围（Creo 9/10、种子重生成、UGC 版本来源）保持不变。

**边界**：逐次受理即持久化、无自动重放/resume、未跨报告合并；未改生产/原生、未改 `version.py`、未合 main、未发布；会话无 busy/断连/unknown。
