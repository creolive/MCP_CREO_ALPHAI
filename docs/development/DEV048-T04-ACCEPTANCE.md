# DEV-048 T04 验收记录：Right 面 ±Z 定向驱动（实机三例通过）

日期：2026-10-27（Asia/Shanghai）。任务：[DEV-048](../work-items/DEV-048.md) T04。分支 `codex/dev048-t04-plane-evidence`，基于 T03 验收提交 `df08fd1`。

**结论：T04 实机三例通过（2026-10-27）。** 第 1—10 节记录的是离线准备阶段当时的事实：那一轮没有连接 Creo，`800 mm³` 只是按输入推算的期望值。此后在用户明确授权的会话中执行了实机矩阵，Right 面 `u_axis=[0,0,1]` 与 `[0,0,-1]` 两例均通过，平行法向拒绝一例取得原生回滚证据，结果见 §11。离线阶段的结论保持不变，不追溯改写。

## 1. 依赖与基线

| 项目 | 实际值 |
| --- | --- |
| T00 文档基线 | `c0a3e55b2124c2ae08cbf577cdbd4a3bd65b52b7` |
| T01 实现 | `23ddcb7371288008f0b599cf8ee1c83c5d561c2a` |
| T02 实现与收口 | `b65b14d8621e4347ca346f84d655ce5621975d09`、`07cc8e4ead08b86ce79a278f69d2718555a827c9`、`eef464ddadca09931d7d1dbe94d0c82bac3a06cb` |
| T03 验收提交（本分支起点） | `df08fd14ba43cade3a3c3c7e76794b1cf6c328b2` |
| main / `v0.7.0^{}` | 均为 `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d` |
| `version.py` | 0.7.0（本轮未改） |
| 本机环境 | Windows 11 x64、Python 3.12.14；Creo 12.4.0.0（离线阶段未核验、未使用；实机阶段见 §11） |

工作区非干净，均为保留的本机运行产物：`session_activity.json` 有修改，另有未跟踪的 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/`。以上未暂存、未提交、未删除。

## 2. 历史证据审阅：缺的正是 Right 面纯 Z 正、负两个实例

审阅对象为 0.7.0 的 T03/T05/T13 验收记录与既有平面参考单测：

| 来源 | 实际内容 | 对 Right 面 ±Z 的结论 |
| --- | --- | --- |
| [DEV047-T03](../development/DEV047-T03-ACCEPTANCE-2026-10-26.md) | 离线 18 项、全量 779 项、SDK 构建通过；`T13 实机验收矩阵（本次未执行）` 第 2 条写明"Right 面以 `u_axis=[0,0,1]` 和 `[0,0,-1]` 创建真实草图"，结论为"T03 离线实现完成，实机未验收" | 这两个实例被明确列为**未执行**，无实机结果 |
| [DEV047-T05](../development/DEV047-T05-ACCEPTANCE-2026-10-26.md) | Live03 毫米矩阵 18/18 通过，但拉伸 9 案例是"倾斜面与主平面 × 正/负/对称盲深"；倾斜面固定法向 `(0.587785,0.809017,0)`，主平面为 XY | 覆盖的是倾斜面和主平面，**不含** Right 面（法向平行 X） |
| 同上"未测与保留范围" | "斜交平面建轴、单平面法向建轴、surface+autodim 与 Right ±Z 的完整历史回归未在本轮执行（归 T03/T04 实机矩阵与 T13 集成复跑）" | 明确把 Right ±Z 留给 T04 |
| [DEV047-T13](../development/DEV047-T13-ACCEPTANCE-2026-10-26.md) | 实机矩阵只复跑了 T06 等专项，并直接引用 T05 的 18/18 | 没有新增 Right 面案例 |
| `tests/unit/test_t03_plane_reference.py` | 覆盖 `u_axis=[0,0,±1]` 的准入透传与 compact 帧字段保留 | 只有解析层证据，**不含**几何、体积或保存重载 |

结论：0.7.0 没有任何可追溯、同实现的 Right 面 `u_axis=+Z`／`-Z` 实机证据可以引用。缺失的正是这两个具体实例（含 `V = N × U` 手性、800 mm³、AABB 与重心、保存重载），因此不存在"引用既有证据"的降级路径，也没有虚增执行次数；本轮按计划新建定向驱动。

## 3. 本轮交付

### 3.1 `tools/test_dev048_plane_frame.py`（新建）

默认只做离线校验；只有 `--live` 与 `--confirm-session-usable` 同时给出时才可能连接。

| 组成 | 行为 |
| --- | --- |
| 输入计划 | `sketch_plan`／`extrude_plan` 构造 `datum_plane.id` + `origin` + `u_axis` 的字典平面，矩形 `min=[0,0]`、`max=[10,20]`、`dimensioning=coordinates`，随后 `+4` 正向盲深拉伸；不写死几何 ID |
| 平面选择 | `select_right_plane` 从巡检 `datum_planes` 中要求**唯一**同时满足"法向平行 X"与"平面过全局原点"的平面，否则报错 |
| 帧断言 | `check_frame`：实际 U 等于输入、N 平行 X、`V = N × U`、三轴正交且为单位向量 |
| 八点几何 | `box_measurements` 用上报帧映射矩形 8 个角点，独立求 AABB 与重心；体积由 `10×20×4` 推算 |
| 测量断言 | `check_measurements`：`length_unit=mm`、`volume_query_code=0`、体积、重心、单实体 bbox |
| 拒绝断言 | `check_unchanged`：revision、aliases、体积、重心、bbox 全部不变 |
| 拒绝分类 | `parallel_case` 区分入口拒绝（无 job、模型未改）与原生拒绝（job failed、`rollback_succeeded=true`、消息匹配原生 `parallel to the support plane normal`）；busy 与无关失败一律中止，不计为"正确拒绝" |
| 复用 | `near`／`dot`／`cross`／`unit`／`require_manual_start` 取自 `tools/test_t05_native.py`；只读启动观察用 `tools/mcp_readiness.wait_for_startup`；快照用 `creo_mechdog.query_client.read_full_model` |
| 证据 | 每次调用前先落盘 `response_received=false`／`outcome=unknown`，异常保留类型与消息；报告含 provenance（源码指纹、提交、dirty、环境） |

### 3.2 `tests/unit/test_dev048_plane_frame.py`（新建，17 项）

| 类 | 覆盖 |
| --- | --- |
| `InputPlanTests` | 两组纯 Z 方向经 `validate_operations` 保真（引用、U、origin、矩形、coordinates、4 mm 正向盲深）；平行 U 在入口**未被**拒绝（因此拒绝必须来自原生边界，并核对 `native/generic.cpp` 的实际报错文本）；几何 ID 只取自巡检（源码级断言 live 路径不含 `163`）；平面选择拒绝偏移面、非 X 法向与重复平面 |
| `FrameAssertionTests` | N=±X × U=±Z 组合通过；错 U、N 非 X、`V` 翻转、非单位 U、斜法向分别被拒 |
| `MeasurementTests` | 8 角点给出 800 mm³ 与手算 AABB／重心（N=±X 两种）；体积／bbox／重心不符被拒；拒绝态 revision／aliases／体积／bbox 任一变化被拒 |
| `RefusalTests` | 入口拒绝：无 job、无模型改动、revision 不变；busy 与无关入口错误**不计**为正确拒绝；原生拒绝：要求 `rollback_succeeded=true` 且状态不变；无回滚、其它原生错误、快照被改动均判失败；平行用例复用同一 Right 面所在模型与 revision |
| `OfflineEntryTests` | 无标志、仅 `--live`、仅 `--confirm-session-usable` 三种组合都只走离线、退出码 0、不触发实机入口；双标志才调用实机入口 |

## 4. 离线验证（真实输出）

环境：Windows 11 x64；Python 3.12.14；`.venv` 内 Python。本轮未连接 Creo、未调用 Toolkit。

```text
PS> .\.venv\Scripts\python.exe -m unittest tests.unit.test_dev048_plane_frame tests.unit.test_t03_plane_reference -v
test_reported_frame_echoes_u_and_keeps_v_equal_to_n_cross_u ... ok
test_wrong_u_non_x_normal_flipped_v_and_non_unit_are_rejected ... ok
test_both_pure_z_directions_survive_validation_with_the_exact_section ... ok
test_geometry_id_comes_from_the_inspection_not_a_constant ... ok
test_parallel_u_axis_passes_entry_so_the_native_boundary_must_reject_it ... ok
test_right_plane_selection_requires_origin_and_x_normal_only ... ok
test_eight_corners_give_800_mm3_and_an_independent_box ... ok
test_native_measurements_must_match_the_independent_box ... ok
test_refusal_state_must_keep_revision_aliases_volume_and_bbox ... ok
test_wrong_volume_bbox_or_center_is_rejected ... ok
test_both_flags_reach_the_live_entry_point_only ... ok
test_default_and_single_flag_runs_are_offline_and_exit_zero ... ok
test_entry_refusal_creates_no_job_and_changes_nothing ... ok
test_native_refusal_requires_rollback_and_unchanged_state ... ok
test_native_refusal_without_rollback_or_other_error_fails ... ok
test_parallel_case_reuses_the_last_valid_part ... ok
test_unrelated_entry_refusal_or_busy_is_not_counted_as_the_expected_refusal ... ok
test_both_public_sketch_paths_reject_ambiguous_reference_before_submission ... ok
test_public_examples_include_geometry_id_and_label_forms ... ok
test_both_pure_z_directions_remain_available_for_native_plane_check ... ok
test_compact_job_preserves_the_native_resolved_frame ... ok
test_dictionary_frame_requires_reference_and_nonzero_u_axis ... ok
test_explicit_geometry_id_and_feature_label_survive_without_reinterpretation ... ok
test_id_and_each_filter_are_mutually_exclusive_even_at_default_values ... ok
test_invalid_id_types_and_range_fail_before_toolkit_lock ... ok
test_selector_mode_remains_valid_without_an_id ... ok
----------------------------------------------------------------------
Ran 26 tests in 0.186s

OK
```

```text
PS> .\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py
OFFLINE ONLY (no live flags given): no MCP client, no Toolkit call, no Creo connection.
  ok  select_right_plane picks one plane through the origin
  ok  both +Z and -Z plans survive input validation
  ok  parallel U is currently rejected by the native boundary, not entry
  ok  eight-corner oracle with N=+X
  ok  eight-corner oracle with N=-X
  ok  frame assertions accept U/N/V and reject bad frames
  ok  measurement assertions reject wrong volume, bbox or center
  ok  unchanged assertions reject a revision or volume change
offline_checks=8/8 passed
LIVE NOT RUN: no native geometry result was produced or claimed.
```

```text
PS> .\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py --live
OFFLINE ONLY (both --live and --confirm-session-usable are required): no MCP client, no Toolkit call, no Creo connection.
  ...（同样 8 项离线检查）
offline_checks=8/8 passed
LIVE NOT RUN: no native geometry result was produced or claimed.
```

两次进程退出码均为 0。退出码 0 只代表离线校验通过，**不代表**任何实机结论。

语言检查（同两个文件）：

```text
PS> .\.venv\Scripts\python.exe -m ruff check tools\test_dev048_plane_frame.py tests\unit\test_dev048_plane_frame.py
All checks passed!
PS> .\.venv\Scripts\python.exe -m ruff format --check tools\test_dev048_plane_frame.py tests\unit\test_dev048_plane_frame.py
2 files already formatted
```

## 5. 断言覆盖的几何性质

| 性质 | 离线（本轮） | 实机（未执行） |
| --- | --- | --- |
| 输入保真 | 两组 `u_axis`、`datum_plane.id`、origin、矩形、深度经准入后不变 | 待测 |
| 实际 U | 断言代码对错 U 拒绝 | 待测 |
| N 平行 X | 断言代码对 N=±X 通过、对 Y／斜法向拒绝 | 待测 |
| `V = N × U` | 手性与翻转检测已覆盖两种 N 符号 | 待测 |
| 正交单位帧 | 三轴两两点积为 0、模长为 1 | 待测 |
| 体积 800 mm³ | 由 `10×20×4` 推算，仅作期望值 | 待测（原生 `volume_mm3`） |
| AABB／重心 | 8 角点独立求解，与解析结果比较 | 待测（`bodies[0].bbox`、`center_of_gravity`） |
| 保存重载 | 断言代码要求 `saved_file_reloaded_and_verified=true` | 待测 |
| 平行法向拒绝 | 分类入口／原生两条路径，均要求模型状态不变 | 待测（预期原生拒绝，见 `native/generic.cpp:919-921`） |

## 6. 双标志守门位置

`tools/test_dev048_plane_frame.py`：

- `main`（608–625）：`614` 行 `if not (args.live and args.confirm_session_usable):` 是唯一分支点；缺任一标志时打印 `OFFLINE ONLY (...)`、跑离线检查、打印 `LIVE NOT RUN`、`return 0`（619–623）。
- 只有双标志才走到 `624` 行 `asyncio.run(live(args.output))`。
- `live`（446–457）：`447` 行先 `require_manual_start(ROOT / "config.json")`（`auto_start_creo` 不为 false 直接报错，不建客户端），`448–454` 才导入并创建 MCP 客户端。
- 启动准备只读轮询 `creo_startup_status`，非 readiness 状态立即停止，不提交启动、不重试、不重启 Creo。

单测 `OfflineEntryTests` 对三种标志组合断言"不触发实机入口"，对双标志断言只调用一次实机入口。

## 7. 缺失的实机证据（已由 §11 补齐）

本轮未产生、也未声称以下任何一项：

1. Right 面 `u_axis=[0,0,1]` 与 `[0,0,-1]` 两个实例的成功几何（实际帧、800 mm³、AABB、重心、`saved_file_reloaded_and_verified`、revision）。
2. 平行 X 的 U 在真实 Right 面上的明确拒绝（入口或原生）及回滚后的 revision／aliases／体积不变。
3. 真实 Right 面几何 ID 与"平面过原点、法向平行 X"的实机核对（仅代码与断言就绪）。
4. 任何 Creo 会话可操作性、构建身份、部署版本或补丁部署状态的核对——本机 Creo 会话**未核验**，`VERSION=0.7.0` 也不代表尚未定稿的补丁已部署。

本轮也没有：探测会话、启动／结束／重启 Creo、清理 unknown、触碰 BUG-078 三个旧现场、做任何故障注入、重跑完整旧矩阵或重建完整旧工程。

## 8. 会话核验后需要执行的命令

前置：用户确认本机 Creo 会话可操作（BUG-001 恢复纪律），且 `config.json` 的 `auto_start_creo` 为 `false`；同一时间只允许一个 Toolkit 客户端。

```powershell
Set-Location 'E:\Projects\MCP_CREO_MechDog'
git switch codex/dev048-t04-plane-evidence   # 若已合入 T05，改用当时的集成分支

# 1) 先复核离线部分（不连接）
.\.venv\Scripts\python.exe -m unittest tests.unit.test_dev048_plane_frame tests.unit.test_t03_plane_reference -v
.\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py

# 2) 会话核验通过后，仅由单一通道执行
.\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py --live --confirm-session-usable
```

实机执行后：

- 报告写到 `build/dev048_t04_plane_frame.json`（本机生成物，不入库），内含每次调用的输入、`job_id`／`model_id`、终态、实际帧、体积、AABB、重心、revision 与 provenance。
- `plane_frame_matrix=passed` 只在 `u_positive_z`、`u_negative_z`、`parallel_u_axis_refusal` 三例全部满足断言时出现；整体仍写 `native_acceptance=partial`，因为该驱动只覆盖 Right 面这两个实例。
- 驱动会新建两个受管毫米测试零件（写入本机 `models/`，不入库），不擦除会话模型；若出现 busy／unknown／失联，立即停止，不重试、不修复旧模型。
- 若任一断言失败，如实记录复现与影响；T04 仍为未验收，几何实现不在本任务内修改。

## 9. 未测与保留（离线阶段结论；实机部分见 §11）

- 本轮全部结论只来自离线输入校验、几何推算与断言自检，不构成任何 Creo、Toolkit 或原生几何证据。
- 外部 Creo 10 的原始现象（R3 §3 `datum_plane id=2` 纯 Z 失败、§5 倾斜面去料）未在本机复现，也不因驱动就绪而转为通过。
- 未重跑 DEV-047 完整矩阵，未重建原 Creo 10 工程、gear10 附件或 Part1/Part2；不宣称逐字回放。
- 未改 `src/`、`native/` 业务实现，未改 `version.py`，未合入 main、未推标签、未发布；T05 未启动。
- 离线阶段维持"未验收"；实机执行结果见 §11，由该节给出最终结论。

## 10. 受测源码与文件指纹

受测源码 = `df08fd1` + 本分支新增的两个文件（提交前工作区为 dirty，仅含这两个待提交文件与本记录）：

| 文件 | SHA256 |
| --- | --- |
| `tools/test_dev048_plane_frame.py` | `DBFC366F7C5ECDD496D0D88E11CD6A998DE4711C4BC8C267F3F9CA5B59B5771D` |
| `tests/unit/test_dev048_plane_frame.py` | `2782F12624BD9DCEDC7E3AC5CBE91496632B7AEE01187AD8BE2259B27E8AFBC8` |

驱动与用例的提交为 `519950cd6e66f84db17793715fc1311f4f5d60c3`（父提交 `df08fd1`）；本记录随其后的小提交补录该提交号。

实机执行时驱动会把提交、分支、dirty 与全部源码文件哈希写入报告的 `provenance`，届时以报告中的 `source_fingerprint` 为准。

## 11. 实机执行结果（2026-10-27，Creo 12.4.0.0）

### 11.1 执行条件

| 项目 | 实际值 |
| --- | --- |
| 授权 | 用户在对话中明确选择"连接 Toolkit 跑 T04 驱动"，并确认会话可操作 |
| 会话 | `xtop` pid 27388，`Responding=True`；Creo Parametric 12.4.0.0 |
| 启动配置 | 本机 `config.json` 增设 `auto_start_creo=false`（该文件在 `.gitignore` 中，未入库、未提交） |
| 通道 | `toolkit-owner.lock` 无持有者；执行期间未并发其它客户端 |
| 驱动分支 | `codex/dev048-t04-plane-evidence`，受测提交 `8be9cbc`（驱动修复已提交并格式化），执行时工作区 dirty（仅本记录与工作卡尚未提交） |
| 报告指纹 | `provenance.source_fingerprint = 126361ff4dd7bc52cbb18e166a9310c6f946e0ee680c32675ed8c049bc5af805`（对 `8be9cbc` 的已格式化源码计算） |
| 证据文件 | `build/dev048_t04_plane_frame.json`（本机生成目录，不入库） |

执行命令：

```powershell
.\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py --live --confirm-session-usable
```

结果：`plane_frame_matrix = passed`，`native_acceptance = partial`。`partial` 是因为本任务只覆盖 Right 面 ±Z 与平行法向拒绝三项，不代表重跑 DEV-047 的完整历史矩阵。

### 11.2 三例证据

Right 面几何 ID 由巡检选出（"过原点且法向平行 X"的唯一平面），实际取到 `id=2`；这个 2 是本次会话的真实值，不是驱动里写死的常量。

| 用例 | 输入 | 实际帧 | 体积 / AABB / 重心 | 保存重载 | revision | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `u_positive_z` | `u_axis=[0,0,1]` | `u=[0,0,1]`、`v=[0,-1,0]`、`n=[1,0,0]`，`v = n × u` | `799.9999999999998` mm³；`[[0,-20,0],[4,0,10]]`；`[2,-10,5]` | `true` | `2` | passed |
| `u_negative_z` | `u_axis=[0,0,-1]` | `u=[0,0,-1]`、`v=[0,1,0]`、`n=[1,0,0]`，`v = n × u` | `799.9999999999998` mm³；`[[0,0,-10],[4,20,0]]`；`[2,10,-5]` | `true` | `2` | passed |
| `parallel_u_axis_refusal` | `u_axis=[1,0,0]`（平行于面法向） | 空零件，无几何 | — | — | `1 → 1` | refusal_verified（原生回滚，别名不变） |

两例有效方向的补充事实：`solver.final_units=mm`、`coordinate_scaling=false`、`max_deviation_mm≈7.5e-48`（坐标建草与原生查询一致）；模型分别为 `79166d508a274366a83d466bc38e256f`、`b1b0309ffd9d46b68cb2534a2c8ea36b`，作业 `4bb87812c0d54a45abb5e5cc5eecb743`、`2903e5fc910245df8b62222afde894ec`。

平行法向一例：入口**没有**拒绝（返回 job），由原生边界拒绝，`rollback_succeeded=true`，`revision` 保持 1，`aliases` 不变；作业 `9c748e25180c4cd3b555d8e332af0e55`，模型 `840a50498d7143389e40d80d8133f60a`。模型是新建的空零件，因此体积为 `null`——"无几何"不等于"体积 0"，报告如实记录为 `null`，不以 0 代替。

### 11.3 为取得该结果修复的三处驱动缺陷

三次失败都出在驱动，不在 Creo 或几何实现。原始报文保留：

1. `creo_execute_plan: Feature labels already exist: ['profile', 'solid']` —— 平行法向用例复用了前一个已建模的零件，计划在入口因标签冲突被拒，根本没走到方向边界。改为每次新建专用空零件，并新增 `expected_entry_refusal()`：标签冲突、`expected_revision`、`busy` 一律不算预期拒绝，只有方向类报文才算。
2. `New model name already exists in the Creo session` —— 重复运行时零件名固定，Creo 会话中已有同名零件。改为每次运行带 `RUN_TAG` 唯一后缀。
3. `TypeError: must be real number, not NoneType` —— 空零件 `volume_mm3` 为 `None`，`check_unchanged` 直接做数值比较。新增 `same_measure()`：两侧同为 `None` 视为未变，一侧有几何一侧没有则判为"状态被改"。

对应离线回归（`tests/unit/test_dev048_plane_frame.py`）：`EntryRefusalTests` 3 项、`UnchangedStateTests` 2 项，`test_parallel_case_uses_a_fresh_part` 覆盖"不得复用已建模零件"。

### 11.4 本节未覆盖的范围

- 未重跑 DEV-047 的完整实机矩阵；`native_acceptance=partial` 即为该事实的声明。
- 未验证倾斜面、多轮廓、纯 Z `u_axis` 的历史现象（R4 报告项），本任务只做 Right 面 ±Z 的定向补证。
- 未做故障注入、未动 BUG-078 三个旧现场、未结束或重启 Creo。
- 未改 `src/`、`native/` 业务实现与 `version.py`；未合入 main、未推标签、未发布。