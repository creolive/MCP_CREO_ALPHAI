# DEV-048 / T02 拒绝后的引用生命周期与批量语义验收

日期：2026-10-27（Asia/Shanghai）。范围：窗口收养与路径收养拒绝后的 `inspection_ref` 生命周期、清理状态如实记录、批量逐件继续/未知停止与保护语义。不含 T01 的 sidecar 写入/发布完整性、T03 台账回填、T04 实机几何与 T05 集成发布。

## 交付与来源身份

- 依赖基准：`715890b`（T01 验收记录提交，分支 `codex/dev048-t01-sidecar`）；T01 实现提交 `23ddcb7`；T00 提交 `c0a3e55`；`main` 与 `v0.7.0^{}` 仍为 `2a78358`，`version.py` 0.7.0 未改。
- 本任务分支：`codex/dev048-t02-ref-lifecycle`，从 `715890b` 建立。
- 起始 dirty：`session_activity.json` 的既有修改；`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1` 与 `session_erase/` 下运行证据 JSON。运行数据全部保留、未纳入提交。
- 环境：Windows 11 x64（10.0.26100）、Python 3.12.14、Git 2.50.1.windows.1、工作区 `E:\Projects\MCP_CREO_MechDog`。
- 未连接 Creo、未调用 Toolkit、未做真实 worker 超时/断连或真实占用故障注入；全部拒绝场景由离线临时根目录 + 替身 native 边界构造。

## 前置核实（实测）

| 项 | 结果 |
| --- | --- |
| `inspection_refs.add_warning` / `warnings_of` / `split_result` | 存在，分别在 `src/creo_mechdog/inspection_refs.py` 第 344、390、498 行 |
| `adoption._split_result` | 第 136 行，委派 `inspection_refs.split_result` |
| 分支配对 | 分支自 `715890b` 建立，`git rev-parse HEAD` = `715890bdb783a700df4c5583b898d508042414a9` |

## 拒绝后的引用归属复现（先于实现）

复现夹具为本机生成目录 `build/dev048_t02_probe/`（不入库），在系统临时目录内构造 `jobs/`、`models/` 与用户源件，用替身 `adoption._native` 复刻真实 worker 的两种 sidecar 位置。真实 worker 在收养请求里把 `folder` 设为模型的 `output_directory`（`native/generic.cpp` 的 `run_generic`），因此窗口收养的 sidecar 落在 `models/<model_id>/output/`；路径收养 inspect 时该目录尚不存在，原生写入失败后由 Python 回退写入 `jobs/<probe_id>/`。

窗口收养拒绝（非毫米，替身按真实位置写入 `models/<model_id>/output/`，修复前）：

| 观察点 | 实际值 |
| --- | --- |
| 直接响应 `current_model.inspection_ref.file` | `...\models\e0188189d2b1462c9c1a1a1a9711fa9a\output\inspection-live-368632733cc61756.json`（218 字节） |
| 拒绝后该文件 | 不存在（`exists after refusal: False`），`verify_ref` 报 `Inspection reference file is missing` |
| `models/` 清理后 | 空目录（staging 已删除） |
| 预检 `job.json` 的 `result.live.inspection_ref` | 同一已删除路径，`job ref exists: False` |
| `compact` 的 `result.live.inspection_ref` | 同一已删除路径 |
| 结论 | 直接响应、job.json、compact、full 四处都仍把已删除文件当作可读取引用 |

路径收养拒绝（同一非毫米件，实测同形态）：

| 观察点 | 实际值 |
| --- | --- |
| `source.inspection_ref.file` | `...\jobs\<probe_id>\inspection-live-<digest>.json` |
| 拒绝后该文件 | 仍存在，`verify_ref` 通过（大小 + 完整 SHA256 + 受控路径） |
| 证据 job | 保留 `job.json`/`request.json`/`native_result.json`，两侧引用一致 |
| 结论 | 路径收养的拒绝证据本来就该保留，不能被“统一清理”误删 |

修复后同一窗口拒绝夹具复跑：直接响应 `inspection_ref` 为 `None`、`job.json` 与 `compact` 均为 `None`、`models/` 为空，`current_model.inspection_summary.units` 仍为 `inch`。

## 实现

- `src/creo_mechdog/inspection_refs.py`
  - `_close_stage`（第 463—484 行）的 verified 分支恢复 0.7.0 语义：`verify_ref` 通过后先 `holder.pop("inspection", None)`，再 `holder.setdefault("inspection_summary", summary_of(holder))`，然后返回。不新建 sidecar、不新增警告、不改 `fallback_status`，详见下文“T01 共用层修复”。
- `src/creo_mechdog/adoption.py`
  - 新增 `_cleanup_staging`：返回 `{"state": "removed" | "failed", "staging": <绝对路径>, "error": ...}`；清理失败不再让拒绝结果丢失，也不声称文件已消失。
  - 新增 `_prune_removed_refs`：仅当 `inspection_refs.verify_ref`（大小 + 完整 SHA256 + 受控路径）失败时才移除引用，并用共用 `add_warning` 记 `inspection_ref_removed_after_refusal` + `fallback_status=not_attempted`；仍能校验的引用原样保留。
  - `inspect` 的两处拒绝分支（原生稳定前缀拒绝、拒绝判定）改为：记录清理真实状态 → 修剪已失效引用 → 重新写 `job.json` → 返回带 `staging_cleanup` 的同义结果。没有删除任何 `jobs/` 证据或用户模型；摘要由共用收尾提供，拒绝响应与 job 投影保留 units/volume。
- `src/creo_mechdog/file_adoption.py`
  - `_verify_reference`：在 `_reserve` 之前校验 item 的 `inspection_ref`（或旧内联资料）；不可读时按 `inspection_reference_unavailable` 已知拒绝处理，不产生半登记、不推进 revision，后项继续。
  - `_public_item` 重复投影时只修剪已不存在的引用（拒绝件记 `inspection_ref_removed_after_refusal`，其余记 `inspection_ref_invalid`）；`refusal_details` 直接使用收尾写入的摘要。
- `src/creo_mechdog/reconciliation.py`
  - `_snapshot` 的候选件在发布前校验 `inspection_ref`：不可读时移除该引用并记 `inspection_ref_invalid` / `not_attempted`，候选身份与动作可用性不变，不再让恢复 inspect 直接报错。
- `inspection_refs` 的公开函数签名、原因码集合与去重/上限规则均未改：本任务只在 `_close_stage` 的 verified 分支恢复旧摘要行为；`inspection_warnings` 仍按 `(stage, reason_code)` 去重、上限 4 条、消息 ≤256 UTF-8 字节。

### T01 共用层修复：`_close_stage` 恢复摘要（集成负责人确认）

- 改动位置：`src/creo_mechdog/inspection_refs.py` 的 `_close_stage`（`verify_ref` 通过的分支，本次改动前在第 480—481 行直接 `return`）。
- 发现者与确认：T02 在复现窗口拒绝时实测发现——原生已给出可验证 `inspection_ref` 时，收养成功后的 `current_model`、evidence 记录 live 均缺少 `inspection_summary`，非毫米拒绝把已知单位报成 unknown（与 DEV-047 T05 的 inch / 查询码 0 实机证据相反）。T02 先报告集成负责人，负责人核对 0.7.0 基线后确认这是回归，并指定改共用层而不是在 `_summary_only` 局部绕行。
- 为什么是恢复而非新契约：0.7.0 的 `inspection_refs.split()` 在“只带引用、没有内联”的 holder 上仍然执行 `holder.pop("inspection", None)` + `holder.setdefault("inspection_summary", summary_of(holder))`。T01 的重构只在 verified 分支漏掉了这两行。恢复后与原语义一致：不写新文件、不产生警告、不改 `fallback_status`、不改任何公开字段结构。
- 边界：`verify_ref` 失败的分支不变，仍移除坏引用并记 `inspection_ref_invalid` / `not_attempted`，且不会为不可读引用补任何摘要。
- `DEV048-T01-ACCEPTANCE.md` 的既有结论未改动（那是 T01 当时的事实记录）。

## 验证命令与真实输出

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_adoption tests.unit.test_adoption_split tests.unit.test_file_adoption tests.unit.test_reconciliation tests.unit.test_reconciliation_mcp -v
.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-048
# 共用层修复后另跑 T01 专项，确认没有把 T01 打回去
.\.venv\Scripts\python.exe -m unittest tests.unit.test_inspection_warnings tests.unit.test_adoption_split tests.unit.test_adoption_budget -v
.\.venv\Scripts\python.exe tools\test_inspection_sidecar.py
```

| 命令 | 结果 |
| --- | --- |
| 5 个专项 unittest 模块 | `Ran 122 tests in 75.852s`，`OK`，退出码 0（基线同 5 模块 114 项；本任务新增 8 项：3 项窗口拒绝生命周期、1 项 MCP 直接响应投影、3 项路径/批量、1 项恢复候选引用） |
| T01 专项（共用层修复后） | `Ran 40 tests in 5.283s`，`OK`（`test_inspection_warnings` 含新增 2 项收尾摘要用例） |
| `tools/test_inspection_sidecar.py` | `success=true`，`exit_code=0`，输出 `INSPECTION_SIDECAR_OK cases=7; no Toolkit call, plain file I/O and SHA256 only` |
| `tools/dev_check.py --skip-unit --work-item DEV-048` | `success=true`，`checked_source_sha256=f33f51b01b89f5d4362e95c8a209e828f7419d1c262a25de58f1f400ef3ce80e`，`cpp_files_checked=33`，`python_files_checked=213`，`lint_findings=30`、`unformatted_files=16`（均为既有基线项，无新增回归）；`dirty=true` 仅来自 `session_activity.json` 与既有未跟踪运行数据 |

额外执行（不属于派发表规定命令，用于确认无相邻回归）：`.\.venv\Scripts\python.exe tools\test_unit.py` → `Ran 995 tests in 309.424s`、`OK`、`build/unit_test_report.json` 记录 `success=true`。过程说明：一次较早的全量运行出现过 3 项源码身份用例失败，原因是该次运行期间 `src/creo_mechdog/adoption.py` 正被继续修改（`_LOADED_FINGERPRINTS` 与磁盘内容不一致）；源码定稿后重跑通过，未放宽任何断言。

## 必测场景逐条结论

| 场景 | 覆盖证据 | 结论 |
| --- | --- | --- |
| 窗口收养拒绝的引用归属 | `test_window_refusal_drops_the_reference_its_staging_removed`、`test_window_refusal_never_publishes_a_removed_reference`（MCP stdio） | 通过：ref 指向 `models/<model_id>/output/`，清理后四处（直接响应/job.json/compact/full）都不再公布该引用 |
| 只移除确已不存在的引用 | `test_window_refusal_keeps_a_reference_that_still_verifies` | 通过：sidecar 位于存活 job 目录时拒绝后仍保留引用并通过校验，未为“看起来干净”而删除证据 |
| 清理成功/失败如实记录 | `test_window_refusal_drops_...`、`test_window_refusal_records_a_failed_cleanup_truthfully` | 通过：`staging_cleanup.state=removed` 时目录确已消失；注入 `rmtree` 失败时为 `failed` + 原始错误、目录仍在、引用仍校验、不声称文件消失 |
| 拒绝保留单位等摘要 | `test_window_refusal_keeps_a_reference_that_still_verifies`（英寸件、引用存活）、`test_path_refusal_keeps_verifiable_evidence_and_known_units` | 通过：`inspection_summary.units` 与 `refusal_details.actual_units=inch/_known=true`、查询码 0 均保留，`inspection_ref` 未被降级 |
| 路径收养拒绝证据仍可校验 | `test_path_refusal_keeps_verifiable_evidence_and_known_units` | 通过：`verify_ref`（大小 + 完整 SHA256 + 受控路径）通过，证据 job 的 job/request/native_result 保留 |
| 重复投影 / job 重新读取 | 窗口用例内连续 `creo_get_job` full/compact 两次 | 通过：两次投影一致，警告不重复（按 `(stage, reason_code)` 去重） |
| 幂等回放 | `test_unreadable_item_reference_refuses_without_reservation_or_revision` 的同键重放、既有 `test_replay_after_expiry_and_while_channel_busy_never_executes` | 通过：回放返回同一作业且不再调用 native，引用含义不变 |
| 批量 `[健康件, 普通拒绝件, 健康件]` | `test_inspect_healthy_refused_healthy_continues_with_live_references`、既有 `test_ordinary_refusal_after_success_continues` | 通过：后项继续，三件引用均可校验，拒绝件保留 `refusal_details` |
| 中间不确定 → 后项 `not_attempted`、保护不释放、不重提 | 既有 `test_inspect_refusals_and_unknown_stop_are_per_item`、`test_unknown_after_success_stops_and_retains_item_protection`、`test_timeout_stops_and_does_not_reexecute_on_poll_or_runner_restart` | 通过：`[refused, unknown_outcome, not_attempted]`，未知项 `pending_job` 保留、revision 不推进、轮询与 runner 重启都不重复执行 |
| 引用错误不产生半登记或额外 revision | `test_unreadable_item_reference_refuses_without_reservation_or_revision` | 通过：`inspection_reference_unavailable` 已知拒绝，`models/<id>` 不存在、无 model.json、前后两件各推进 1 次 revision，后项继续 |
| 共用收尾恢复摘要（T01 回归） | `test_a_verified_native_reference_gains_its_summary`、`test_an_unreadable_reference_is_not_given_a_summary` | 通过：可验证原生引用收尾后有摘要且与 ref 内容一致、不新增 sidecar/警告；引用不可读时仍记 `inspection_ref_invalid`/`not_attempted` 且不补伪造摘要 |
| 恢复路径候选引用 | `test_unreadable_candidate_reference_is_dropped_not_published` | 通过：不可读候选引用被移除并记 `inspection_ref_invalid`/`not_attempted`，候选身份与 `accept_saved` 可用性不变 |

## 提交

- 依赖基准：`715890bdb783a700df4c5583b898d508042414a9`（T01 验收记录）。
- 本任务实现提交：`b65b14d`（分支 `codex/dev048-t02-ref-lifecycle`，改动文件与指纹见上；运行数据未纳入）。本记录提交：本文件所在提交。
- 改动文件：`src/creo_mechdog/inspection_refs.py`（共用层摘要恢复）、`adoption.py`、`file_adoption.py`、`reconciliation.py`、`tests/unit/test_adoption.py`、`test_inspection_warnings.py`、`test_file_adoption.py`、`test_reconciliation.py`、本记录与 `docs/work-items/DEV-048.md` 的 T02 相关区域；`tests/unit/test_adoption_split.py` 最终与 T01 版本一致（本任务曾加的需求在共用层覆盖后移除）。
- 未合入 main、未创建标签、未发布、未改版本号、未启动 T03/T04/T05、未改动已归档原件与 `.gitattributes`、未改 `docs/BACKLOG.md` 统计区。

## 源码指纹（SHA256）

| 文件 | SHA256 |
| --- | --- |
| `src/creo_mechdog/inspection_refs.py` | `cca0efbd5854dd2a873cc65fb64311c33abc21431d48196ec7204a7c85ac8e86` |
| `src/creo_mechdog/adoption.py` | `bb4eca7bd143b73ed42d1cc2ebe9a7a3c23e8f4b29aab8a40e2e03f84d698b77` |
| `src/creo_mechdog/file_adoption.py` | `ac9dc5389546348a34bcd9c41977eec21ca98d811c2632c29e6fb4f697f5242a` |
| `src/creo_mechdog/reconciliation.py` | `62a5754be756a7d7fd0b42b090a2ea1efb91b0cb04cf7b097859d003f25bf650` |
| `tests/unit/test_adoption.py` | `e7740a85f5d9e58619075676080969ca525c06edd990db790fa8898f5e9c55b0` |
| `tests/unit/test_adoption_split.py` | `ca8b451763bc7156aea33efcbb8e1326151027c0e1c253aed5b9151fd8923f2a` |
| `tests/unit/test_file_adoption.py` | `80d704b9cda7f643e011df1c2236cecb25c5e195126143cd8f9aa1b5224d7c36` |
| `tests/unit/test_reconciliation.py` | `1c9d216e32d42d9605b3095d5ecd4acc172e22eb4d96e76549e25c2c7d0eacca` |
| `tests/unit/test_inspection_warnings.py` | `fbcdddd86545e8def9adfb05c36486d94fbcc861585df64ca38aee2ea8f4c9bb` |

## 未测与交回

- 未连接 Creo、未调用 Toolkit：窗口/路径拒绝的真实 worker 行为由离线替身按 `native/generic.cpp` 的 sidecar 位置复刻，不构成实机证据；实机窗口与源文件不变性由 T05 在安全新夹具验证。
- 未做真实 worker 超时、断连、真实占用或旧现场故障注入；未知停止与保护保留沿用既有离线回归。
- 清理失败场景当前用 `shutil.rmtree` 注入（目录被占用/权限的替身），未在真实 Windows 文件锁下复测。
- 共用收尾恢复摘要后，evidence 令牌 live 也随收尾写入 `inspection_summary`；本次未在真实 Creo/Toolkit 环境复测该字段的实机取值。