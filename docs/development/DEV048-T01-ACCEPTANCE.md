# DEV-048 / T01 sidecar 完整性、回退与公开诊断验收

日期：2026-10-27（Asia/Shanghai）。范围：sidecar 大小与完整 SHA256 核验、原生文件 helper 提取、写入/发布失败回退、`inspection_warnings` 贯通收养/恢复/批量每项/`creo_get_job`。不含 T02 的拒绝后引用生命周期、T03 台账回填、T04 实机几何与 T05 集成发布。

## 交付与来源身份

- 依赖基准：T00 提交 `c0a3e55`（分支 `codex/dev048-feedback060`，基线 main / `v0.7.0^{}` = `2a78358`，`version.py` 0.7.0，未改动）。
- 本任务分支：`codex/dev048-t01-sidecar`，从 `c0a3e55` 建立。
- 起始 dirty：`session_activity.json` 的既有修改；`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1` 与 `session_erase/` 下 30 个运行证据/意向 JSON。运行数据全部保留、不纳入提交。
- 环境：Windows 11 x64（10.0.26100）、Python 3.12.14、Git 2.50.1.windows.1、MSVC（`vcvars64_local.cmd`）、本机 Creo 12.4.0.0 Toolkit SDK（`config.json`）。工作区 `E:\Projects\MCP_CREO_MechDog`。
- 未连接 Creo、未调用 Toolkit、未做真实故障注入；全部文件错误注入在离线临时目录或对 helper 的单元测试打桩中实施。

## 三类现象复现（先于实现）

复现夹具位于本机生成目录 `build/dev048_t01_repro/`（不入库）：`repro_python.py` 直接调用当时的 `inspection_refs` / `adoption._split_result`；`native_repro.cpp` 逐行复制当时的 `write_inspection_ref` / `split_report_inspections`，用替身 `folder`/`log` 离线编译运行（不链接 Toolkit）。输入全部为临时目录内的构造资料。

```powershell
.\.venv\Scripts\python.exe -X utf8 build\dev048_t01_repro\repro_python.py
.\.venv\Scripts\python.exe -X utf8 build\dev048_t01_repro\repro_native.py
```

| 现象 | 复现输入 | 实际结果（实现前） | 预计错误 |
| --- | --- | --- | --- |
| Python 同大小不同内容 | 76 字节 payload；同名目标写入等长的 `volume_mm3: 99` 变体 | `ref_points_at_decoy=true`、`ref_resolves_to_payload=false`，`load_ref` 报 “Inspection reference file hash changed” | 只比大小的复用把引用发布到别人的字节上，公开引用不可读 |
| Python 发布失败 | 打桩 `os.replace` 抛 `OSError(13)` | `PermissionError` 直接逃逸；目录残留 `inspection-live-…tmp` | 失败阶段未分类，临时文件不清理 |
| Python 收尾失败 | 打桩 `make_ref` 抛 `OSError(28)` | `OSError` 逃逸；`inspection_warnings=null`，live/verified 仍内联 | 无阶段/原因/回退状态，收养预检被异常终止 |
| 原生 live 写失败 | 目标目录不存在 | 仅 `INSPECTION_SPLIT_FAILED=Cannot write the inspection sidecar file`；`live_inline=1 verified_inline=1 live_ref=0 verified_ref=0 warnings=0` | 前者失败后 verified 阶段被静默跳过，结果无诊断 |
| 原生临时写成但发布失败 | 目标名被目录占用 | `case2_published_ref=1`、`case2_ref_points_at_directory=1` | `exists(file)` 被当成“同内容已存在”，发布出指向目录的坏引用 |
| 原生同大小不同内容 | 同名等长他人文件 | `case3_same_size=1 ref_published=1 target_untouched=0` | `std::filesystem::rename` 带 REPLACE_EXISTING，无条件覆盖了别人的文件 |

三类现象（原生 live/verified 写失败、临时写成但发布失败、同名同大小内容不同）均复现成立；中文路径与长路径不是本批复现到的根因，未据此下结论。

## 实现

- `src/creo_mechdog/inspection_refs.py`
  - 新增共用 `split_result(result, directory)`、`add_warning(holder, *, stage, reason_code, fallback_status, message)`、`warnings_of(holder)`；`make_ref` / `split` / `load_ref` 调用签名不变。
  - `make_ref` 复用前必须同时满足“自有普通文件（拒绝符号链接/目录）+ 大小 + 完整 SHA256”；同名冲突保留原文件，改用完整摘要名发布，两个名字都被占用时报 `SidecarPublishFailed`。
  - 发布路径改为临时文件 → 校验（大小 + 完整 SHA256）→ `os.link` 原子发布（无硬链接卷回退到 `O_EXCL` 独占创建），不再使用会覆盖的 `os.replace`；失败只清理本次自有临时文件。
  - 新增 `SidecarWriteFailed` / `SidecarPublishFailed`（携带固定原因码）、`verify_ref`、`bounded_message`（≤256 UTF-8 字节且不截断编码字符）。
  - `split_result` 对 live / verified 独立收尾：已有引用先做大小 + 完整 SHA256 核验（失败改为 `inspection_ref_invalid` 并不再发布坏引用）；内联资料回退成功才把原生 `not_attempted` 升级为 `verified`，双重失败保留内联并记 `failed`。
- `src/creo_mechdog/adoption.py`：`_split_result` 委派共用实现；`_native` 把结果诊断记入 manifest；`inspect` 预检在共用收尾后读取诊断，并把 `inspection_warnings` 带入 evidence、拒绝摘要 `current_model` 与证据令牌记录（`_summary_only` 一并投影）。
- `src/creo_mechdog/file_adoption.py`：路径收养 inspect 与逐项提交（含 `resume_committed` 物化）把每项诊断挂到对应 item。
- `src/creo_mechdog/reconciliation.py`：恢复 `_native` 在读取结果后执行共用收尾；`_live` 与 `_snapshot` 候选件保留同义诊断。
- `bridge.py::compact_job`：compact 顶层与 `result` 白名单加入 `inspection_warnings`，full 保持原样。
- `native/inspection_sidecar.h`（新）：无 Toolkit 调用的文件 helper（临时写、SHA256 核验、`MoveFileExW` 不含 REPLACE 的发布、同名冲突换名、诊断去重/上限/截断、两阶段收尾）。
- `native/generic.cpp`：改为包含新 header 并委派 `split_report_inspections`；`read_inspection_ref` / `choice_inspection` 原样保留。
- `server.py`：`_SOURCE_NAMES` 增加 `native/inspection_sidecar.h`；`reconciliation._deployment` 同步该文件。callback/loader 的源码依赖清单未改动，因此不会因本 helper 触发无关回调换代（worker 构建指纹本就覆盖 `native/**`）。

## 验证命令与真实输出

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_adoption_split tests.unit.test_adoption_budget tests.unit.test_inspection_warnings tests.unit.test_file_adoption tests.unit.test_reconciliation tests.unit.test_reconciliation_mcp -v
.\.venv\Scripts\python.exe tools\test_inspection_sidecar.py
.\.venv\Scripts\python.exe bridge.py build
.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-048
```

| 命令 | 结果 |
| --- | --- |
| 6 个专项 unittest 模块 | `Ran 110 tests in 51.533s`，`OK`，退出码 0（基线同 6 模块为 91 项；本任务新增 17 项诊断用例 + 2 项 split 扩展用例） |
| `tools/test_inspection_sidecar.py` | `build_exit_code=0`，`exit_code=0`，输出 `INSPECTION_SIDECAR_OK cases=7; no Toolkit call, plain file I/O and SHA256 only`，`success=true` |
| `bridge.py build` | 退出码 0，输出 `E:\Projects\MCP_CREO_MechDog\build\creo_worker.exe`（MSVC + 本机 SDK，bcrypt.lib） |
| `tools/dev_check.py --skip-unit --work-item DEV-048` | `success=true`，`checked_source_sha256=07d80891363400d489fb9722fcb9dfc908474a2d901250e6a0348cbd2f7075cd`，`cpp_files_checked=33`，`python_files_checked=213`，`lint_findings=30`、`unformatted_files=16`（均为既有基线项，无新增回归） |

额外执行（不属于派发表规定命令，用于确认无相邻回归）：`.\.venv\Scripts\python.exe tools\test_unit.py` → `Ran 985 tests in 319.735s`、`OK`、退出码 0（0.7.0 基线 966 项 + 本任务新增 19 项）。

`dev_check` 的 `regressions` 在首次运行时仅指出新文件未过格式化；对 `native/inspection_sidecar.h`、`native/generic.cpp`、`tests/native/test_inspection_sidecar.cpp` 执行 `clang-format -i` 后复跑为 `success=true`，未修改既有基线、未放宽任何检查。本机进程在每条命令末尾都会打印一条 `reg.exe` 沙箱黑名单提示（与命令结果无关，退出码仍为 0/1 如实记录）。

## 必测场景逐条结论

| 场景 | 覆盖证据 | 结论 |
| --- | --- | --- |
| 正常重复内容幂等 | `test_repeating_a_payload_reuses_one_verified_file`、`test_make_ref_is_content_addressed_and_idempotent`、native case 1 | 通过：同内容只保留一个文件，引用完全相同 |
| 同大小损坏目标 | `test_same_size_conflict_keeps_the_other_file_and_republishes`、`test_make_ref_never_reuses_a_same_named_file_with_other_bytes`、native case 2 | 通过：他人文件字节不变，payload 改发到完整摘要名 |
| 缺失/截断/越界引用 | `test_verify_ref_refuses_missing_truncated_and_outside_files`、`test_an_unreadable_reference_is_not_published`、既有 `test_load_ref_*` | 通过：三类均拒绝；坏引用不再对外发布并记 `inspection_ref_invalid` |
| write/flush/publish 错误 | `test_write_failure_is_classified_and_leaves_no_temporary_file`、`test_blocked_directory_is_a_write_failure`、`test_publish_conflict_keeps_names_and_cleans_its_temporary_file`、native cases 3/4 | 通过：写入与发布分别归入两个固定原因码，临时文件不残留，占用名保留 |
| 原生失败 + Python 成功 | `test_native_failure_is_upgraded_after_the_python_fallback`、`test_split_result_records_a_failed_python_fallback`（对照） | 通过：`not_attempted` → `verified`，消息为“Native sidecar write failed; Python fallback was verified” |
| 双重失败 | `test_double_failure_keeps_the_inline_payload_and_reports_failed` | 通过：两个阶段均记 `failed`，内联资料保留，不伪报引用 |
| live 成功 + verified 失败及相反 | `test_each_stage_closes_independently`（两个子用例）、native case 6 | 通过：失败阶段单独记录，健康阶段照常产出引用 |
| 旧二进制内联结果 | `test_legacy_inline_result_splits_without_a_warning`、`test_oversized_payload_flows_through_inspect_without_budget_hit` | 通过：正常拆分不产生警告，旧结果语义不变 |
| 超预算失败不伪报成功 | `test_adoption_budget` 全模块（含 `ServerBudgetContract`）、上述 >16 MiB 贯通用例 | 通过：预算错误仍以结构化 JSON 失败，未提高 16 MiB 上限 |
| 诊断去重/截断与 compact/full | `WarningShape` 四项、`test_compact_and_full_projection_keep_the_diagnostics`、`test_window_adoption_publishes_a_failed_fallback_and_still_returns` | 通过：按 (stage, reason_code) 去重、上限 4 条、256 字节内不截断字符，compact 顶层与 `result` 均保留 |
| 原生两阶段独立 | native case 6、native case 7 | 通过：live 发布被占用时 verified 仍完成；普通建模计划不拆分 |

## 提交

- 依赖基准：`c0a3e55b2124c2ae08cbf577cdbd4a3bd65b52b7`（T00）。
- 本任务提交：`23ddcb7371288008f0b599cf8ee1c83c5d561c2a`（分支 `codex/dev048-t01-sidecar`）。提交内容见下，运行数据未纳入。
- 改动文件：`src/creo_mechdog/inspection_refs.py`、`adoption.py`、`file_adoption.py`、`reconciliation.py`、`bridge.py`、`server.py`、`native/inspection_sidecar.h`（新）、`native/generic.cpp`、`tests/native/test_inspection_sidecar.cpp`（新）、`tests/unit/test_inspection_warnings.py`（新）、`tests/unit/test_adoption_split.py`、`tools/test_inspection_sidecar.py`（新）、本记录与 DEV-048 卡。
- 未合入 main、未创建标签、未发布、未改版本号、未启动 T02 及后续任务。

## 源码指纹（SHA256）

| 文件 | SHA256 |
| --- | --- |
| `src/creo_mechdog/inspection_refs.py` | `3abb2c262bd669c6eb97e8d62a9924d0a9ab844c72c0c08feaedbf293c92fb94` |
| `src/creo_mechdog/adoption.py` | `2ec505229b51d56a1c6d6dc105072ef1ed0a7e98bb8e871d12196157a365e9a1` |
| `src/creo_mechdog/file_adoption.py` | `06b3fb3f0aa615315ff9d9866be0e282bc1e6a56c40d827418e22e35ccb2156a` |
| `src/creo_mechdog/reconciliation.py` | `97cf1812cbcf53c61e4f2809d6b04425532214c5348dcf380ddb477200d22fbc` |
| `bridge.py` | `cc519f0cf2cbafd1c682faeeb501bd3fd4b4c775604b774d7595c97bd10c3a34` |
| `server.py` | `97cd7bcc84ab341170ca016176a9a8173434382a2207186982b526ca33d57a4c` |
| `native/inspection_sidecar.h` | `101fb13bbfdf965f039abc637723210d2c12bb7928a90afd7821208c911ef11a` |
| `native/generic.cpp` | `47ba7c1245e95328fa63acc9c8698bb17c081a3d16ae1402c9cbb0432e2c4a22` |
| `tests/native/test_inspection_sidecar.cpp` | `b1fbbf155053d0c5394671ce540ece34c939ca585a93b11c0dca205b0d9c4544` |
| `tests/unit/test_adoption_split.py` | `ca8b451763bc7156aea33efcbb8e1326151027c0e1c253aed5b9151fd8923f2a` |
| `tests/unit/test_inspection_warnings.py` | `5429fda076962c7e2ac6adb7392eecb5cf38bce818568d64c70e1782396a03fa` |
| `tools/test_inspection_sidecar.py` | `cb73dbfc85b396a5409b754b26caadc31f6110cfb2c09ad192aab52c25117c53` |

## 未测与交回

- 未连接 Creo、未调用 Toolkit、未做真实占用/断连/旧现场故障注入；原生 helper 的行为只在离线夹具与替身输入上验证，不构成实机 sidecar 证据。
- 未在中文或超长合法目录下做端到端原生实机写入；`native_repro` 与 `tools/test_inspection_sidecar.py` 仅使用系统临时目录。路径编码按真实 UTF-8 处理，未修改全局长路径策略或 SDK 文件。
- 未验证被替换的旧二进制在真实 worker 进程中的行为；用离线注入模拟“原生已失败、结果仍内联”。
- 未复测旧结果在历史 job.json/登记中的分页与嵌套场景；只覆盖 compact/full 投影与批量 item 投影的单测。
- T02 的拒绝后引用清理、批量 unknown 停止语义、T04 实机几何与 T05 集成发布均未开始；本记录不改变其状态。