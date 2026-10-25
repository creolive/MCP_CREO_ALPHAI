# FEAT-030 / BUG-034 种子来源与兼容信息透明化实施记录（2026-10-25）

按 [0.5.0-0.5.1 反馈计划](../development/0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md) 阶段三实施。分支 `codex/feat030-seed-transparency`（自 `0729fee`）。条目：[FEAT-030](../work-items/FEAT-030.md)、[BUG-034](../work-items/BUG-034.md)。

**本轮为开发分支改动，未连接 Creo 会话、未做实机建模与保存重载**；实机成功核对留给回归收口任务。种子库重生成是另列的环境受阻子项，本机无匹配旧版生成/验收环境，未承诺完成，也未新增双版本发布门槛。

## 实现

### 来源（生产版本）

`src/creo_mechdog/seed_compatibility.py` 把 `seed_build_version` 的取值收紧为两种**与实际种子 SHA256 绑定**的来源：

- 可追溯生成记录：`docs/seed_manifest.json` 条目中的 `seed_build_version`，仅当该条目的 `sha256` 与实际文件哈希一致时采纳（`seed_build_version_source = seed_manifest`）。
- 可靠原生证据：`build/seed_provenance/<sha256>/<release>-<job>.json`，由 `record_native_build_evidence()` 写入并校验 `row["seed_sha256"] == digest`（`seed_build_version_source = native_evidence`）。

两者都不满足时 `seed_build_version` 保持 `null`，`seed_build_version_status = unknown`。当前九个已发布种子**没有**可追溯生成记录，因此发布状态下该字段恒为 null。

UGC 头解析为诊断线索：读取首行 `#UGC:2 PART 2128 1860 810 …`，输出 `seed_file_diagnostic.ugc_part_version_token = 2128`，`ugc_interpretation` 固定为 `unverified_clue`。**不建立 2128=12.4 之类映射**，也永不用于填 `seed_build_version`；单测断言返回结构中不出现 `12.4` 字符串。

### 查询语义（available 只代表文件与哈希）

- `seeds.list_seeds()` / `seeds.validate_seed()` 增加 `available_scope`（"文件字节与发布 SHA256 一致；不代表当前 Creo 会话能加载"）、`native_load_probe`（`not_performed`）与 `compatibility_evidence`。
- `available` 判定改为"实际文件哈希 == 清单哈希"；来源与历史加载记录随**实际字节**走，文件被改动后来源不归属、历史清空、`seed_build_version` 回到 null。
- `native_compatibility.status` 恒为 `not_verified_for_current_session`，`current_session_loadable` 恒为 null；历史加载记录按种子 SHA256 隔离存放（`build/seed_compatibility/<sha256>/`），只说明别的会话发生过什么。
- 普通查询**不建立 Toolkit 连接、不隐式试载**：单测用 `side_effect=AssertionError` 替换 `bridge.build_native`、`bridge.toolkit_lock`、`generic_bridge.submit`、`generic_bridge.run_generic_job`，列表与校验仍正常返回。

### 加载失败诊断

`seed_compatibility.load_failure_diagnosis()` 保留原始 API（`ProMdlFiletypeLoad`）、错误码、实际阶段（`failed_stage`）、种子标识与 SHA256、可取得的运行版本（`creo_release_numeric` / `creo_release_query_code` / `session_fingerprint`）与原生消息原文，并给出核对兼容性与来源的提示。

- **只有**在存在绑定该 SHA256 的来源记录、且其 `release_numeric` 高于当前会话 release 时，才给出有界的 `version_incompatibility`（`cause = recorded_release_newer_than_session_release`），并注明"不证明原因"。
- 否则 `cause = undetermined_by_error_alone`，**不硬写"由 Creo 12.4 构建，当前版本无法加载"**。
- 加载成功与后续建模成功分别记录（`seed_load_succeeded` / `modeling_succeeded`）。

`generic_bridge.run_generic_job()` 在收尾时调用 `observe_load()` 写加载证据；加载失败时把诊断并入终态消息，`native_message` 保留原生原文。**诊断写入失败不改变建模终态**：原因留在 `seed_load_evidence.evidence_error`，`evidence_persisted = false`，任务仍按原路径终态为 `failed`。

### 能力与说明

- `capabilities.py`：`seed_library` 族增加 `available_scope` / `native_load_probe` / `compatibility_evidence` / `production_version`；`loft_seed` 族增加 `compatibility_evidence` / `load_failure_diagnosis`。
- `server.py`：`creo_list_seeds`、`creo_validate_seed`、`creo_new_loft_part`、`creo_new_airfoil_blade` 的工具说明写明 available 只代表文件字节、普通查询不建立 Toolkit 连接也不试载、失败诊断口径，不承诺最低 Creo 版本。
- 文档：[兼容矩阵](../COMPATIBILITY.md)、[种子库说明](../SEED_LIBRARY.md)、[放样种子说明](../LOFT_SEED.md) 统一写明"**外部 Creo 9 已报告受测种子 -16；另有 Creo 10 三截面成功历史；当前会话/其他种子未验证**"；不写未经证实的最低 Creo 要求，也不写笼统的"Creo 10+ 已验证"。`docs/SEED_LIBRARY.md` 与 `docs/LOFT_SEED.md` 的历史验收段落保留其原环境与日期，另起新章节记录当前口径。

## 验证

- 新增/扩展单测 23 项（`tests/unit/test_seed_compatibility.py` 16 项、`tests/unit/test_seed_listing.py` 7 项），其中新增 17 项：未知来源保持 null、UGC 线索不产生版本、生成记录只对同字节生效、原生证据绑定字节、历史按种子隔离、失败诊断保留 API/码/阶段/标识/版本、无证据不判版本原因、失败消息保留原生措辞、加载与建模成功分开记录、available 只代表文件、查询不建连接、字节变化清空来源与历史、缺文件保持未知、清单按摘要匹配、失败终态保留诊断、诊断写失败不改终态。
- 全量 585 项单元通过（`Ran 585 tests in 157.618s` / `OK`），基线 568 项。
- `.\.venv\Scripts\python.exe tools/dev_check.py`：`success: true`，`unit_tests: passed`，语言检查零回归（`build/development_check.json` 为本机生成物，不入库）。
- 环境：Windows 11 x64 / Python 3.12.14 / `ruff 0.17.0` / `clang-format 23.1.3`；源码提交 `0729fee42aec67dc01633bca7022c8eb4bea52a8`（dirty，脏改动为本条目内容）。
- 本轮无原生 C++ 改动，未重新编译执行器，未调用 `tools/test_*.py` 实机脚本。

## 未验证（如实保留）

- **实机加载与建模**：本轮不连接 Creo，会话内放样/翼型加载成功、参数与几何、保存重载（`saved_file_reloaded_and_verified`）均由回归收口任务在实机取得。
- **外部 Creo 9 的 -16 根因**：未复现、未定位、未修复；本轮只做诊断信息与来源透明化。BUG-034 仍开放。
- **Creo 10 三截面成功**：沿用 2026-10-17 报告历史（无 job/model 标识），不外推为完整 Creo 10 运行时验收或九个种子在该环境均可加载。
- **种子库重生成**：环境受阻子项，本机无匹配旧版生成/验收环境，未承诺完成。
- **其他种子与其他环境**：当前会话/其他种子未验证；本机 Windows x64 / Creo 12.4.0.0 的历史成功记录不外推到其他环境。
