# 0.5.3 阶段三收口：离线全量回归与实机矩阵证据（2026-10-25）

日期：2026-10-25（Asia/Shanghai）。本文件只记录本轮实际执行的命令、返回与未测范围，不代表 0.5.3 已发布，也不把本机 Creo 12.4 通过外推为 Creo 9 复验。

## 条目与源码身份

| 项 | 值 |
| --- | --- |
| 收口范围 | 0.5.3 阶段三：[BUG-081](../work-items/BUG-081.md)、[BUG-082](../work-items/BUG-082.md)、[BUG-083](../work-items/BUG-083.md)、[FEAT-030](../work-items/FEAT-030.md)/[BUG-034](../work-items/BUG-034.md)，以及既有条目小修 [FEAT-045](../work-items/FEAT-045.md)、[BUG-058](../work-items/BUG-058.md)、[FEAT-020](../work-items/FEAT-020.md)、[BUG-019](../work-items/BUG-019.md) |
| 计划来源 | [0.5.0/0.5.1 Creo 9 反馈计划](../development/0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md) 阶段三 |
| 集成态 | `codex/feedback05051-phase1` @ `e2bba08`（阶段一 `2f3eb6e` + 小修 `0729fee` + BUG-083 `50a3c94` + 合并 task/5 BUG-081 + 合并 task/6 BUG-082 + FEAT-030/BUG-034 `e2bba08`） |
| 服务版本（`version.py`） | `0.5.2`；0.5.3 为目标版本，**未发布**（无标签、无 Release、`version.py` 未改） |
| 离线回归工作树 | `E:\Projects\MCP_CREO_MechDog-task-9`（分支 `task/9`），HEAD `e2bba08d64d0859496aa7047412e954b3f27ea3f`，`git status --porcelain` 为空（dirty=false） |
| 实机回归运行环境 | `E:\Projects\MCP_CREO_MechDog`（主仓，只读参考，不在其上提交），HEAD 同为 `e2bba08`，`git status --porcelain` 有未跟踪 scratch 产物（`.codebuddy/`、`session_erase/*`、`examples/wb_unsaved_03.prt.1` 等），报告内 `git.dirty=true` |

### 受测源码指纹

两处 `build/development_check.json` 的 `source.checked_source_sha256` **相同**，说明已跟踪源码集合一致，主仓 `dirty=true` 只来自未跟踪 scratch 产物：

| 位置 | `source.commit` | `source.dirty` | `checked_source_sha256` |
| --- | --- | --- | --- |
| task/9 工作树 `build/development_check.json` | `e2bba08d64d0859496aa7047412e954b3f27ea3f` | `false` | `da558d9e3dca1a963a77f9e8467926e38c8006a34179ef94518c608b2e28b5f0` |
| 主仓 `build/development_check.json`（实机同源） | `e2bba08d64d0859496aa7047412e954b3f27ea3f` | `true`（未跟踪产物） | `da558d9e3dca1a963a77f9e8467926e38c8006a34179ef94518c608b2e28b5f0` |

配置与工具指纹（两份报告一致）：`pyproject.toml` `4b786c9741c35ba69a3e27a08b686fbf2989821d4ab8d1daf00fe9889e09d0aa`、`.clang-format` `b084ba4a767e8fede2f3d47e7dfb3ae120528cb76fceb113ce27e3dd7e0a77a0`、`requirements-dev.txt` `f325c41a3f7288bd4dfb08310276c9790b1ca5fcafc9bd68704559b64ec5decc`；ruff 0.17.0、clang-format 23.1.3、C++ 25 文件、Python 158 文件。

## 环境

- 开发/实机：Windows 11 Enterprise x64；Creo Parametric 12.4.0.0（`release_numeric=44`，匹配 Toolkit SDK，`feature_creation_license=requires_actual_modeling_test`）；Python 3.12.14。
- 离线工作树使用**隔离 venv**（`requirements-dev.txt` 锁定版本、`pip install -e .`），`config.json` 从主仓只读复制（该文件已被 Git 忽略）；`native/constants.inc` 由本机 SDK 在 `bridge.py build` 中生成，未入库。
- 实机侧会话：`parametric.exe` PID 8080（`created 2026-10-25T00:21:17Z`）、`xtop.exe` PID 18944（`created 2026-10-25T00:21:19Z`），`launch_attempt=42`、`state=ready`、`connected=true`；`creo_process_snapshot` 记录 `parametric.exe` 窗口 `state=hidden_only`（`hung_window_observed=true`、`visible_hung_window_observed=false`），按既有口径判为非阻塞，未做任何处置。

### 开测前清场（按 BUG-001 恢复纪律）

| 动作 | 结果 |
| --- | --- |
| 结束 PID 19396（codex 运行时拉起的 `server.py`） | 已结束，未影响 Creo 会话 |
| 结束 PID 18548 | 已结束 |
| 删除 1 字节陈旧 `toolkit.lock` | 已删除（本机生成物，非源码） |
| Creo 三进程（`parametric.exe`/`xtop.exe`/`creoagent.exe`） | 未动，`Responding` |
| 恢复动作（reconcile/abandon/清保护） | 未执行 |

## 离线回归（task/9 工作树）

| 命令 | 结果 |
| --- | --- |
| `-m unittest discover -s tests -v` | **612 项全过**。首轮唯一 error 为工作树缺 `config.json`（隔离 venv + fresh worktree）；从主仓只读复制 `config.json` 后重跑受影响 6 项 **6/6 通过**，随后全量 612 通过（`build/unit_test_report.json`：`tests_run=612`、`success=true`、`failures=0`、`errors=0`） |
| `tools/test_unit.py` | exit 0；`build/unit_test_report.json` `success=true`、`failures=0`、`errors=0`、`tests_run=612` |
| `tools/dev_check.py` | exit 0；`success=true`、`unit_tests=passed`、`lint_findings=31`、`unformatted_files=19`、`native_validation=not_run`（31/19 与基线欠账一致，非本轮引入） |
| `bridge.py build` | exit 0；`creo_worker.exe` 复编（12614656 B），`native/constants.inc` 本机重新生成未入库 |

## 实机回归（主仓 dev 环境）

| 命令 | 结果 |
| --- | --- |
| `bridge.py build` | exit 0 |
| `tools/test_editing_closeout.py` | **EXIT 0**，`EDITING_CLOSEOUT_SUCCESS=1`，**13/13 `CASE_PASS`**，耗时 7m38s；报告 `build/editing-closeout/ad8cc893695c4d2a8b9042e4f4858793/report.json`（866 KB，525 次调用，49 个作业，`success=true`） |
| `tools/test_extended.py revolve_modes` | 3/3 成功（surface 180°、thin 2mm=800π、symmetric 90°=500π） |
| `examples/revolve_external_axis.json`（隔离新件） | 成功，`revision=1`，体积 `3141.592653589793`（=1000π），`saved_file_reloaded_and_verified=true`，无失败特征 |
| `-m tools.test_feedback037_modeling --cases seeds` | `seed_straight` 成功；随后脚本 `KeyError('inspection')` 退出 1（字段已改名 `inspection_summary`，脚本过期，非建模失败）；`smooth` 成功 |
| `creo_validate_seed two_smooth` | `available=true`、`native_status=not_verified_for_current_session`、`observation_job_ids` 含本次作业 |

### 编辑矩阵 13 个用例

`label_dimension_edit`、`integer_dimension_edit`、`numeric_string_dimension_edit`、`legacy_unchanged`、`legacy_changed`、`dimensioning_and_clean_repeat`、`parameter_driven_cache`、`rectangle_native_verification`、`entity_branch_native_verification`、`reorder_noop_revision_plus_one`、`arc_radius_inplace_edit`、`onaxis_sector_coordinate_edit`、`onaxis_sector_autodim_failure` —— 全部 `passed=true`。

保存重载校验：`saved_file_reloaded_and_verified` 共出现 100 处（含同一作业的重复轮询），**97 true / 3 false**；3 处 false 全部属于同一个预期失败作业 `754365a2…`（见下）。按作业去重为 49 个作业结果（48 true / 1 预期 false），两种计数口径不冲突。

### BUG-082 在轴扇形：成功路径 7/7

模型 `dccfd8e5642243a88f84c39cf2f2ef1e`（`session_fingerprint=18294318788830540455`），全部 `saved_file_reloaded_and_verified=true`：

| 步骤 | job_id | revision | 体积 mm³ |
| --- | --- | --- | --- |
| 基线扇形 R10、90° | `3531da0e51d74de6ab0b365983c819b4` | 1 | 2094.395102392602 |
| coordinates 改角 90°→80° | `02d2bfae5f9a40a794d0a630ac050335` | 2 | 2062.5765347066654 |
| 回程 80°→90° | `3644999ffabb463b9b780b91665f2b58` | 3 | 2094.395102392601 |
| coordinates 改半径 R10→R12 | `779f9944c9fb4aab8820edf01ce893fc` | 4 | 3619.1147383778516 |
| 回程 R12→R10 | `e01cd5a240b740a19a4a41651c09e347` | 5 | 2094.395102392602 |
| 同几何直接建 80°（新件） | `89e9a2a6a993471d8a71fd24b9cfd1bb`（模型 `f45c37d6…`） | 1 | 2062.5765347066654 |
| 同几何直接建 R12（新件） | `d106816104114cb686483c82b6148dbf`（模型 `42e17f95…`） | 1 | 3619.1147383778516 |

体积与独立推导 `V=(2πR³/3)·sinθ_max` 逐位一致（θ=80° 时 `sin80°=0.9848078`）。回程复位后体积与基线相同，说明成功路径可逆。

### BUG-082 在轴扇形：autodim 改角失败与回滚（预期失败）

模型 `9f54ffa86cc0411893438f39adb68855`：

- 基线 `b8e477cb2b734e078ebbed77c8c8963c` 成功，`revision=1`，体积 2094.395102392602。
- 编辑 `754365a2e9124465b641b57a83ae2593` **failed**：`failed_stage=execute_update_sketch_geometry`、`failed_operation_index=0`、`toolkit_code=-1`，message `Regeneration produced a failed, suppressed or incomplete feature`。
- `failed_features`（结构化）：`REV_SK` id=40、`type_name=sketch_or_curve`、`status=6`、`incomplete=false`、`sketch_constraint_count=12`、草绘尺寸 d4=80.00000000000003；`REV1` id=51、`type_name=protrusion`、`status=6`、`incomplete=false`。
- 回滚：`rollback_succeeded=true`、`inspection_source=rollback_verified`、体积复原 2094.395102392602、`part_file=null`、`saved_file_reloaded_and_verified=false`（预期，失败作业无保存）。
- **revision 未取得**：报告格式不含 revision 字段（失败作业只登记 `status/stage/message`），仅有 inspection `eecf93192557c960…`（9431 B）与 aliases `7bc618a126de878f…`（1608 B）两个引用文件的 SHA256。按计划此缺口保留。
- 结论口径：autodim 改角 90°→80° 的再生失败**本体仍在**，本轮只补齐了失败特征级诊断，不是修复。

### BUG-079 回归（矩阵内 `arc_radius_inplace_edit`）

`a286958ca45e4873ac5929fb6dcd8983`（rev1，1973.920881015659）→ `71e9fa8e43494399810418238d8865e3`（rev2，2842.446068079807）→ `69ed9046ab094b5aabe4d9d0eb24ef36`（rev3，1973.9208810156592），离轴夹具 R5→R6→R5 与外部 Creo 9 数值同量级，未退化。

### 夹具与登记保护

两个 legacy 夹具原样还原并能通过控制文件哈希核对：`88dd2644…`（`part_sha256=d92bfaba5e0ca971c84e34db9d9adff0b38887c8007aee88941e4c745aa79495`，`original_control_sha256=90cefb34…`）、`6ac8f924…`（`part_sha256=f3fe6b3c55a98ea2061e569e0bb4c1a25861008b0edc0969c9e4648d6a5a3bdf`，`original_control_sha256=5777a9d0…`）。登记保护未被突破（矩阵内 `reorder_noop_revision_plus_one` 通过，重排 no-op 仍 rev+1）。

### FEAT-030 种子实机证据

| 用例 | job_id / model_id | 结果 |
| --- | --- | --- |
| `seed_straight`（种子 `two_straight`，sha256 `7d2dbeb4f3bea4839b6501e311105753bfc752a0033f72039f8230b6aa61f5f2`） | job `d161f855adac4c279c3630c74d9f95df` / model `97f2b13d1d8c46c29a34312b9a01d22d`，`revision=1` | 成功，体积 5131.268000863329（=4900π/3），`inspection_source=saved_reloaded`，`seed_load_evidence.status=loaded`、`evidence_persisted=true`、`seed_native_load=loaded`，保存重载 true |
| `smooth`（种子 `two_smooth`，sha256 `865204bea18f5098342e97a5fadb670e27cdd10a174cb7c45e2192e6c14b0518`） | job `fe8bf5ed89c54de0bd50fcdfbefd97d8` / model `d67cd032a25e4457b38ea0698be2f6fa` | 成功，`seed_load_evidence.status=loaded`、`evidence_persisted=true`、`modeling_saved_reloaded_verified=true`，体积 5131.268000863329 |
| `creo_validate_seed(two_smooth)` | — | `available=true`、`native_status=not_verified_for_current_session`、`observation_job_ids=[fe8bf5ed…, 7e2c0273…]`、`seed_build_version=null`、`seed_build_version_status=unknown`、UGC 头 `#UGC:2 PART 2128 1860 810 1 1 15 4100 2023073 00000285` 仍标 `unverified_clue` |

口径：本机 Creo 12.4 加载成功只证明**本机本会话**可加载；`available` 仍只表示文件字节与哈希一致；生产版本因无绑定该 SHA256 的可追溯记录而保持 null。Creo 9 的 -16 未复验。

### BUG-083 双路径实机

- 省略 axis + 内部构造中心线：`tools/test_extended.py revolve_modes` 3/3（surface/thin/symmetric），说明省略语义与既有行为一致。
- 显式轴：`examples/revolve_external_axis.json` 在隔离新件上成功，`revision=1`、体积 3141.592653589793、`saved_file_reloaded_and_verified=true`、无失败特征。
- 未覆盖：原生 `validate_revolve_axis` 在真实执行器中触发（Python 预检先拒，原生层为纵深防御，实测不会到达）。

### 偏差与处置（如实披露）

1. `tools/test_general.py --help` 无 argparse 支持，被当作全套运行；实际跑完 `GENERAL_CORE_SUCCESS=1`、`BRACKET_VOLUME=10600`，全部通过，不构成失败，但**不是**本次刻意的定向回归。
2. `tools/test_extended.py --help` 被当成 case 名，`failures["--help"]`、`EXTENDED_SUCCESS=0`；同一报告内 `revolve_modes=true`。故 `--help` 的 0 是脚本参数处理缺陷，建模结论以 `revolve_modes` 子项为准。
3. 冷启动首查出现 `building_worker`（非 -11/-4），用 `tools/mcp_readiness.wait_for_startup` 预热后正常调用；未按故障处理。
4. `tools/test_installation_loft.py` 未运行（本轮未安排安装回归）。
5. FEAT-030 脚本 `KeyError('inspection')` 属脚本字段过期（已改名 `inspection_summary`），建模作业本身成功；本轮未改脚本。

## 未测范围

- **Creo 9 全部未复验**：本机无 Creo 9 SDK 与实机环境，[BUG-034](../work-items/BUG-034.md) 的 -16 根因与 FEAT-030 的兼容提示均未在 Creo 9 上验证；本机 Creo 12.4 通过**不等于** Creo 9 已修复或已复验，不新增双版本发布门槛。
- 编辑矩阵的 **revision 字段**未取得（报告格式不含），失败作业 revision 仍为空白。
- **9 种子安装库回归**未执行（只覆盖 `two_straight`/`two_smooth` 两个种子的实际加载与建模）。
- 种子重生成（环境受阻子项）未做；生产版本仍为 null。
- BUG-081 的 MCP 端到端拒绝负载未走实机（无同型残留 worker 现场；单测直接断言 `owner_block` payload）。
- BUG-083 原生预检分支、外部 Creo 9 复测未触发。
- WorkBuddy 黑盒未在本轮执行；本轮全部为开发者离线 + 实机脚本证据。

## 结论

- 离线：612 单测、`dev_check`、原生复编全部通过，无新增语言问题（31/19 为既有基线）。
- 实机（本机 Creo 12.4）：编辑收口矩阵 13/13、在轴扇形成功路径 7/7 与体积逐位一致、autodim 改角失败带特征级诊断且回滚干净、BUG-083 双路径成功、FEAT-030 两种子加载与保存重载成功。
- 阶段三未闭合项：autodim 改角再生失败本体（BUG-082）、Creo 9 兼容（BUG-034/FEAT-030 环境侧）、revision 字段、种子重生成与安装库回归。
