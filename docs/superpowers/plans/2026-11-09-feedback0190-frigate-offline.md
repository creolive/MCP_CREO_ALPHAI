# 0.19.0 护卫舰反馈 A 批（离线修复） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉第四份 0.19.0 反馈里可由 Python 层验证的六个缺口（F02/F03/F04 回执/F05 compact 提示/F07/F11 文档契约），把需要 Creo SDK、实机或黑盒的 F01/F06/F08/F09/F10 留在 DEV-081 台账，不冒充已修。

**Architecture:** A 批只改 `src/creo_mechdog/` 的校验、文案与 compact 投影以及文档；`schema.validate_operations` 在提交前做轮廓预检，`generic_bridge.py` 的 `endpoint_welding.prepare_operations` 在其之后，因此 F02 的修复点在预检判定本身而不是调用顺序。所有改动都以新增 `tests/unit/test_feedback0190_*.py` 的 unittest 用例先红后绿，不触碰原生执行器、公开工具签名和 `version.py`。

**Tech Stack:** Python 3.12+、Pydantic v2、`unittest`、MCP stdio 工具注册、PowerShell 命令（`.venv\Scripts\python.exe`）。

**Spec:** `docs/validation/feedback-0.19.0-frigate-2026-11-08/originals/2026-11-08+CREO+0.19.0+原生放样不可用与草图圆弧预检误拒 (1).md`；逐项对照 `docs/validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md`；工作卡 `docs/work-items/DEV-081.md`。执行者先读这三份，报告里的精确数值以原件为准。

## Global Constraints

- 长度用毫米，角度用度；特征 label 以小写字母开头、仅 `[a-z0-9_]`、最多 28 个字符。
- 服务标准输出只承载 MCP 协议消息；Toolkit 通道忙碌立即 `isError=true`、`status="busy"` 并带 `blocking_*`，不排队、不自动重试。
- 新增用例放 `tests/unit/test_*.py`，使用 `unittest`，方法名 `test_*`；命令前缀一律 `.venv\Scripts\python.exe`。
- 离线边界：不连接 Creo/Toolkit、不启动或结束 Creo 会话、不清 unknown 保护、不故障注入、不联网、不编译原生执行器（BUG-001 恢复记录约束）；本机原生环境是 Creo 12.4.0.0，无 Creo 10 SDK。
- `docs/validation/` 历史反馈原件逐字节保持一致，不得重排或格式化；`native/constants.inc` 是本机生成物，不提交、不复制。
- `tools/check_backlog_counts.py` 三方计数必须一致，当前为 **172 / BUG 75 / FEAT 61 / DEV 36**。
- `version.py` 保持 `0.19.2`；已发布 `v0.19.2` 标签与四附件不得覆盖；本计划只在本开发分支提交，合入 `main` 时才按 `docs/development/RELEASING.md` 同流程发布。
- 不要求 Creo 10 独立复测或双版本验收（2026-10-15 用户决定）；其他环境收到具体反馈后再跟进，证据标明实际环境。

## Review Focus

1. **显式 `closure_tolerance_mm`（如 `1e-6`）与 `near_tolerance` 的交互**：调用方收紧容差后，合法轮廓不能被新的放行逻辑静默改判 → Task 1 的 `test_explicit_closure_tolerance_still_controls_near_tolerance`。
2. **`endpoint_policy=weld` 的阶段语义**：错误信息不得声称 weld 已在计划校验前生效 → Task 1 的 `test_weld_policy_order_is_stated_in_error`。
3. **放宽半径上限后的类型与非半径字段**：`bool`/`0`/负值/`nan`/`inf` 仍拒绝，`GeometryTransformOp.translation` 的 100000 上限不变 → Task 2 的 `test_boolean_zero_negative_nan_inf_rejected` 与 `test_translation_100001_still_rejected`。
4. **更新检查失败时的版本口径**：`status=failed` 不得声称已是最新，缓存的 `latest_version` 必须带 stale 说明 → Task 3 的 `test_failed_check_never_claims_latest`。
5. **只读回执与文档不越界**：connect `-4` 指引不得诱导自动重启、重提或清保护；平面语义文档不得改变 XZ 的 −Y 法向 → Task 5 的 `test_retry_step_never_clears_protection` 与 Task 4 的 `test_xz_offset_behavior_unchanged`。

---

### Task 1: F02 精确圆弧闭合轮廓不再被 near_tolerance 误拒

**Files:**
- Modify: `src/creo_mechdog/profile_diagnostics.py:678-731`（`validate_solid_profile`）
- Create: `tests/unit/test_feedback0190_arc_closure.py`

**Interfaces:**
- Consumes: `analyze_profile(entities, tolerance=CLOSURE_TOLERANCE_MM) -> dict`，其键 `closed_contour_count`、`open_contour_count`、`categories["near_tolerance"]["items"][].gap_mm`、`closure_tolerance_mm`；`src/creo_mechdog/schema.py:2207` 的 `validate_operations(operations) -> list[dict]`。
- Produces: `validate_solid_profile(entities, dimensioning="auto", operation="extrude", tolerance=CLOSURE_TOLERANCE_MM) -> dict`，签名与返回结构不变。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_arc_closure.py`，常量 `DECK_ENTITIES` 取报告 §四最小用例：`line a [0,680]→[0,-680]`、`line b [0,-680]→[6830,-690]`、`arc d4 center=[6830,917.6086957] radius=1607.6086957 start_angle=270 end_angle=325.194591737`、`arc d5 center=[6830,-917.6086957]` 同半径 `34.805408263→90`、`line c [6830,690]→[0,680]`。七个测试：

```python
report = validate_solid_profile(DECK_ENTITIES, "coordinates")
self.assertEqual(report["closed_contour_count"], 1)
self.assertEqual(report["open_contour_count"], 0)
```

`test_coordinate_deck_arc_closure_is_accepted`（上面断言）、`test_plan_validation_accepts_deck_with_weld_policy`（`validate_operations` 收 `sketch`+`extrude` 两个 op：sketch 为 `{"op":"sketch","label":"deck","plane":"XY","offset":0,"dimensioning":"coordinates","endpoint_policy":"weld","entities":DECK_ENTITIES}`，extrude 为 `{"op":"extrude","label":"hull","sketch":"deck","mode":"add","direction":"negative","depth":660}`，断言返回 2 项且不抛 `ValueError`）、`test_open_near_tolerance_profile_still_rejected`（把 d5 的 `start_angle` 改成 `34.9` 制造真实开口，断言 `ValueError` 且文本含 `open`）、`test_rejection_text_names_remediation`（同一开口，断言文本含 `closure_tolerance_mm`、`polyline`、`snap_endpoints`）、`test_explicit_closure_tolerance_still_controls_near_tolerance`（`tolerance=1e-6` 时上述开口仍被拒）、`test_weld_policy_order_is_stated_in_error`（拒绝文本含 `submission`，说明 weld 在提交阶段生效）、`test_larger_near_tolerance_gap_still_rejected`（`GAPPED_SQUARE` 四段直线在 (0,0) 留 `5e-7` mm 间隙，断言 `ValueError` 且文本含 `near_tolerance`）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_arc_closure -v`
Expected: 4 FAIL / 3 PASS。FAIL 的是 `test_coordinate_deck_arc_closure_is_accepted`、`test_plan_validation_accepts_deck_with_weld_policy`（当前 `ValueError: Solid extrude profile rejected: ... [near_tolerance]`）以及 `test_rejection_text_names_remediation`、`test_weld_policy_order_is_stated_in_error`（错误文本尚无补救建议）；PASS 的是 `test_open_near_tolerance_profile_still_rejected`、`test_explicit_closure_tolerance_still_controls_near_tolerance` 与 `test_larger_near_tolerance_gap_still_rejected`。

- [ ] **Step 3: Implement the acceptance rule in `validate_solid_profile`**

新增模块常量 `RESIDUAL_RATIO = 1e-3`（相对本次 `tolerance` 的浮点残差界）。仅当 `dimensioning == "coordinates"` 且报告满足「`closed_contour_count >= 1`、`open_contour_count == 0`、`near_tolerance.items` 非空、该 category 未截断、且每项 `gap_mm <= tolerance * RESIDUAL_RATIO`」时，不把 `near_tolerance` 加入 fatal；其余情况维持原有拒绝。默认 `tolerance=1e-4` 时残差界为 `1e-7` mm：报告的 `2.78e-8` 放行，既有 `5e-7` 及以上保护用例仍拒绝；显式收紧 `tolerance` 同步收紧残差界。`near_tolerance` 仍留在 `report["categories"]` 供回执。在抛出任何 profile rejection 前追加一句以分号分隔的补救建议（对所有拒绝生效），含 `closure_tolerance_mm`、`snap_endpoints` / `endpoint_policy=weld`、「合并为一条 polyline」以及「weld is applied at submission time, not during plan validation」。不改 `CLOSURE_TOLERANCE_MM=1e-4`、`EXACT_TOLERANCE_MM=1e-9`，不改 `analyze_profile`，不改 `schema.py` 的调用顺序。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_arc_closure tests.unit.test_profile_endpoint_diagnostics tests.unit.test_profile_checks tests.unit.test_endpoint_weld_gate tests.unit.test_sketch_stability tests.unit.test_t06_multi_contours -v`
Expected: 全部 PASS，无 `Ran 0 tests`。

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_feedback0190_arc_closure.py src/creo_mechdog/profile_diagnostics.py
git commit -m "DEV-081: accept exact-arc closed contours"
```

### Task 2: F03 半径与草图尺寸的 API 上限

**Files:**
- Modify: `src/creo_mechdog/schema_base.py:47`
- Modify: `src/creo_mechdog/schema.py:190-208, 270-275, 289-305`
- Create: `tests/unit/test_feedback0190_dimension_limit.py`

**Interfaces:**
- Consumes: `Positive = Annotated[float, Field(gt=0, le=100000)]`（保留，供平移等非半径字段）。
- Produces: `Dimension = Annotated[float, BeforeValidator(_reject_bool), Field(gt=0, le=1000000), WrapValidator(_explain_dimension_limit)]`，其中 `_reject_bool` 拒绝 `bool`、`_explain_dimension_limit(value, handler)` 把 `less_than_equal` 换成带 `API limit` 说明的 `PydanticCustomError`；`Circle.radius`（`Arc` 继承）、`Ellipse.x_radius/y_radius`、`SketchDimension.value` 改用 `Dimension`。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_dimension_limit.py`：`test_arc_radius_105000_accepted`（`Arc(type="arc", name="a", center=[0,0], radius=105000, start_angle=0, end_angle=90)` 构造成功且 `.radius == 105000`）、`test_ellipse_and_sketch_dimension_105000_accepted`（`Ellipse(type="ellipse",name="e1",center=[0,0],x_radius=105000,y_radius=105000)` 与 `SketchDimension(name="d1",type="radius",refs=[{"entity":"a"}],value=105000)` 成功）、`test_dimension_over_1e6_rejected_with_api_limit_text`（`radius=1000001` 抛 `ValidationError`，文本含 `1000000` 与 `API limit`）、`test_boolean_zero_negative_nan_inf_rejected`、`test_translation_100001_still_rejected`（`GeometryTransformOp.translation=100001` 仍按 `test_transform_rotation_range.py:73-75` 口径拒绝）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_dimension_limit -v`
Expected: 4 FAIL / 1 PASS。`test_arc_radius_105000_accepted`、`test_ellipse_and_sketch_dimension_105000_accepted`（`Input should be less than or equal to 100000`）、`test_dimension_over_1e6_rejected_with_api_limit_text`（错误文本只有 100000）、`test_boolean_zero_negative_nan_inf_rejected`（`Positive` 会把 `True` 转成 1.0）FAIL；`test_translation_100001_still_rejected` PASS。

- [ ] **Step 3: Implement `Dimension`**

在 `schema_base.py` 仿 `_explain_label_pattern` 新增 `_explain_dimension_limit`：捕获 `less_than_equal` 时用 `PydanticCustomError("less_than_equal", "radius/dimension API limit is 1000000 mm; this is a service schema limit, not a Creo kernel limit", {"le": 1000000})` 重新抛出，其它错误原样交给 handler。新增 `_reject_bool`（`isinstance(value, bool)` 抛 `ValueError`），因为 Pydantic 默认会把 `True` 转成 `1.0`。定义 `Dimension = Annotated[float, BeforeValidator(_reject_bool), Field(gt=0, le=1000000), WrapValidator(_explain_dimension_limit)]`；在 `schema.py` 只把上述四个字段从 `Positive` 换成 `Dimension`，`Positive` 定义与其它引用一律不动。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_dimension_limit tests.unit.test_transform_rotation_range tests.unit.test_general_validation tests.unit.test_dimension_guards tests.unit.test_arc_direction -v`
Expected: 全部 PASS；`test_transform_rotation_range` 的 100001 拒绝断言仍成立。

- [ ] **Step 5: Commit**

```bash
git add src/creo_mechdog/schema_base.py src/creo_mechdog/schema.py tests/unit/test_feedback0190_dimension_limit.py
git commit -m "DEV-081: raise radius and sketch dimension API limit"
```

### Task 3: F07 更新检查失败时给出可执行的下一步

**Files:**
- Modify: `src/creo_mechdog/update_check.py:265-296`
- Create: `tests/unit/test_feedback0190_update_guidance.py`

**Interfaces:**
- Consumes: `NETWORK_SECONDS=5`、`RETRY_SECONDS=15*60`、`_network_timeout_seconds()`（环境变量 `MECHDOG_UPDATE_TIMEOUT_SECONDS`，有效范围 1..30）、`UpdateChecker.snapshot()` 的 `network_timeout_seconds` 字段。
- Produces: `UpdateChecker.snapshot() -> dict`，字段结构不变；失败时 `error`/`message` 为新增文案。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_update_guidance.py`，复用 `tests/unit/test_update_check.py` 的超时夹具（mock `fetch_releases` 抛 `TimeoutError`，`force=True` 触发刷新）：`test_timeout_error_names_configurable_budget`（`status="failed"` 且 `error` 含 `MECHDOG_UPDATE_TIMEOUT_SECONDS`）、`test_timeout_message_names_force_retry_tool`（`message` 含 `creo_check_update` 与 `force=true`）、`test_failed_check_never_claims_latest`（`message` 含「不代表已是最新版本」且缓存 `latest_version` 带 `stale` 说明）、`test_default_network_budget_is_five_seconds`（`snapshot()["network_timeout_seconds"] == 5`）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_update_guidance -v`
Expected: 前两个 FAIL（现有文案只有「GitHub 更新检查超过 5 秒网络预算。」），后两个 PASS。

- [ ] **Step 3: Implement the guidance text**

保持 `NETWORK_SECONDS=5` 与 `1 <= value <= 30` 不变（5 秒是 MCP 启动路径预算，本任务不放宽默认）。在 `:265-269` 的超时 `error` 追加「可设置 `MECHDOG_UPDATE_TIMEOUT_SECONDS`（1—30 秒）后重试」；在 failed 分支的 `if/else` 之后、`self._expires` 之前统一给 `message` 追加「可设置 `MECHDOG_UPDATE_TIMEOUT_SECONDS`（1—30 秒）后重试；也可用 `creo_check_update(force=true)` 立即重试。」，使有/无缓存两个分支都生效。保留「失败不代表已是最新版本」「过期缓存」原句。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_update_guidance tests.unit.test_update_check tests.unit.test_feedback0174_status tests.unit.test_capability_pages -v`
Expected: 全部 PASS，`status=failed` 的四态与预算断言不变。

- [ ] **Step 5: Commit**

```bash
git add src/creo_mechdog/update_check.py tests/unit/test_feedback0190_update_guidance.py
git commit -m "DEV-081: make update timeout failures actionable"
```

### Task 4: F11 草图平面 offset/direction 语义文档契约

**Files:**
- Modify: `src/creo_mechdog/schema.py:325-359`（`SketchOp.offset` 字段描述）
- Modify: `server.py:861-872`（`creo_execute_plan` docstring 开头）
- Modify: `docs/REFERENCE_SYNTAX.md`（`create_sketch.plane` 行，约 :177，追加三平面对照小节）
- Create: `tests/unit/test_feedback0190_plane_semantics.py`

**Interfaces:**
- Consumes: `native/generic.cpp:1306-1327` 的 `sketch_frame` 映射：XY → `origin=[0,0,offset]`、`normal=[0,0,1]`；YZ → `origin=[offset,0,0]`、`normal=[1,0,0]`；XZ → `origin=[0,offset,0]`、`normal=[0,-1,0]`；`ExtrudeOp.direction` 是相对法向的 `positive`/`negative`。
- Produces: 仅描述文本，不改字段类型、默认值、返回结构或原生行为。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_plane_semantics.py`：`test_offset_field_description_names_plane_coordinate`（`SketchOp.model_fields["offset"].description` 含 `plane_coordinate` 与 `global`）、`test_execute_plan_docstring_states_three_plane_frames`（`server.creo_execute_plan.__doc__` 含 `XZ`、`negative Y`、`plane_coordinate`）、`test_reference_syntax_table_states_xz_negative_y`（`docs/REFERENCE_SYNTAX.md` 新增小节含三行 `origin`/`normal` 与「offset 是全局坐标，不是沿法向位移」）、`test_xz_offset_behavior_unchanged`（`SketchOp(label="xz_sk", plane="XZ", offset=500, dimensioning="coordinates", entities=[{"type":"line","name":"a","start":[0,0],"end":[10,0]}])` 仍接受且 `.offset == 500`；`direction` 仍不属于 `SketchOp` 字段）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_plane_semantics -v`
Expected: 前三个 FAIL（描述与文档尚无这些词），第四个 PASS。

- [ ] **Step 3: Implement the descriptions**

给 `SketchOp.offset` 加 `Field(description=...)`，写明 `plane_coordinate`（全局坐标值，不是沿法向的位移）与 `direction` 属于 extrude/revolve 的相对法向语义；在 `creo_execute_plan` docstring 追加三平面 `origin`/`normal` 对照，字面包含 `plane_coordinate`、`XZ`、`negative Y`，并说明 XZ 的 `positive` 使 Y 减小；在 `docs/REFERENCE_SYNTAX.md` 的 `create_sketch.plane` 行后追加「主平面 offset 与切除方向」小节，明确**字典引用内的 `offset` 是平面筛选条件**（该文件 :43 的既有语义），与字符串主平面的全局 `offset` 不是同一字段。不改 `native/generic.cpp`，不改 `ExtrudeOp`。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_plane_semantics tests.unit.test_dev048_plane_frame tests.unit.test_datum_plane_contract tests.unit.test_cut_material -v`
Expected: 全部 PASS；`test_cut_material` 的零去料错误文案断言不变。

- [ ] **Step 5: Commit**

```bash
git add src/creo_mechdog/schema.py server.py docs/REFERENCE_SYNTAX.md tests/unit/test_feedback0190_plane_semantics.py
git commit -m "DEV-081: document sketch plane offset and direction frames"
```

### Task 5: F04 connect -4 的只读下一步指引

**Files:**
- Modify: `src/creo_mechdog/session_health.py:413`（`_next_steps`）、`:689`（`snapshot` 调用点）
- Create: `tests/unit/test_feedback0190_connect_guidance.py`

**Interfaces:**
- Consumes: `_connection_fact(records, now) -> dict | None`，返回扁平 `toolkit_code`（`:344`）与 `outcome`（`:334`）；`snapshot()` 已发布 `read_only=True`、`toolkit_connections=0`、`next_steps`。
- Produces: `_next_steps(status, reason, busy, toolkit_code: int | None = None, connected: bool | None = None) -> list[dict]`，其余调用点保持默认参数。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_connect_guidance.py`，用 `tempfile.TemporaryDirectory` 在临时 root 写一条 `jobs/<id>/job.json` 失败连接记录（`result.connected=false`、`toolkit_code=-4`、`worker_exit_code=20`），`snapshot_for(code)` 覆盖同一文件后以 `refresh=True` 重算：`test_connect_minus_four_step_names_startup_retry`（`snapshot(..., now=NOW, refresh=True)["next_steps"]` 含 `step="retry_startup"`、`tool="creo_startup_status"`，`detail` 含 `retry=true` 与 `explicit`）、`test_non_minus_four_has_no_retry_step`（`-1` 与 `None` 用 subTest 遍历）、`test_retry_step_never_clears_protection`（`next_steps` 仍含 `preserve`、`read_only is True`、`toolkit_connections == 0`，且 `retry_startup` 排在 `preserve` 之前；旧代码缺该步骤时 `list.index` 抛 `ValueError`）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_connect_guidance -v`
Expected: 1 FAIL / 1 ERROR / 1 PASS。`test_connect_minus_four_step_names_startup_retry` FAIL（`AssertionError: 0 != 1`）；`test_retry_step_never_clears_protection` ERROR（旧代码无 `retry_startup`，`steps.index` 抛 `ValueError`）；`test_non_minus_four_has_no_retry_step` PASS。两者都源于同一步骤缺失。

- [ ] **Step 3: Implement the read-only step**

`_next_steps` 增加两个可选参数；当 `toolkit_code == -4 and connected is False` 时，在 `preserve` 之前插入一条 `{"step":"retry_startup","action":"Request an explicit startup retry","tool":"creo_startup_status","detail":"... retry=true ... the service never restarts Creo automatically and no unknown protection is cleared"}`。`snapshot()` 先算 `connection_fact = _connection_fact(records, moment)`（同时供 `facts.last_connection` 复用，不重复解析），把 `connection_fact.get("toolkit_code")` 与 `(connection_fact or {}).get("outcome") == "connected"` 传入；其它分支、`operator` 文案与 `caveats` 原样保留。不改 `creo_startup.py`、不新增自动重试。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_connect_guidance tests.unit.test_t10_session_health tests.unit.test_failed_operation_context tests.unit.test_job_stage_reporting -v`
Expected: 全部 PASS；`next_steps` 的状态分支与 `read_only` 断言不变。

- [ ] **Step 5: Commit**

```bash
git add src/creo_mechdog/session_health.py tests/unit/test_feedback0190_connect_guidance.py
git commit -m "DEV-081: point connect -4 receipts at explicit retry"
```

### Task 6: F05 compact 视图暴露 surface_loft 限制

**Files:**
- Modify: `src/creo_mechdog/capability_pages.py:97-105`（`_section_summary`）
- Create: `tests/unit/test_feedback0190_loft_limits.py`

**Interfaces:**
- Consumes: `src/creo_mechdog/capabilities.py:992-1010` 的 `families["surface_loft"]["limits"]`（唯一真源）；`UNAVAILABLE_OPERATIONS`（`capabilities.py:108`）。
- Produces: `_section_summary(payload) -> dict`，其它 family 的 `enabled`/`tool` 结构不变；仅对 `COMPACT_LIMITS` 中的 family 增加 `limits_note`。

- [ ] **Step 1: Write the failing tests**

新建 `tests/unit/test_feedback0190_loft_limits.py`，用真实 `server._capabilities_payload([])` 作 payload 并调用 `pages.capabilities_response`：`test_compact_families_surface_loft_has_limits_note`（先 `assertIn("limits_note", ...)` 再断言 `limits_note` 含 `two sections only` 与 `no smooth`、长度 ≤160 字符）、`test_full_families_limits_unchanged`（跟随 `next_cursor` 在 `detail="full", section="families"` 分页中找到 `surface_loft`，断言其 `limits` 等于 `capabilities.families()` 全文）、`test_boundary_fill_stays_unavailable`（compact 的 `unavailable_operations` 仍含 `surface_boundary_fill`，门禁未放宽）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_loft_limits -v`
Expected: 第一个 FAIL（compact 只有 `enabled`/`tool`），后两个 PASS。

- [ ] **Step 3: Implement the compact note**

新增模块常量 `COMPACT_LIMITS = ("surface_loft",)` 与 `COMPACT_LIMITS_CHARS = 160`；在 `_section_summary` 先把 comprehension 结果存为 `summary`，再对 `name in COMPACT_LIMITS`、`name in summary`、`family` 为 dict 且 `limits` 为 str 的条目加 `"limits_note": family["limits"][:COMPACT_LIMITS_CHARS]`，最后返回 `summary`。不改 `CAPABILITY_FAMILIES` 的 `limits` 全文、不改 `KNOWN_LIMITATIONS`、不放宽 `UNAVAILABLE_OPERATIONS`；compact 只对这一个 family 增字段，避免响应预算膨胀。

- [ ] **Step 4: Run tests and regressions to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0190_loft_limits tests.unit.test_capability_pages tests.unit.test_large_plan_result_budget tests.unit.test_compact_sections -v`
Expected: 全部 PASS，`detail=full` 分页与预算断言不变。

- [ ] **Step 5: Commit**

```bash
git add src/creo_mechdog/capability_pages.py tests/unit/test_feedback0190_loft_limits.py
git commit -m "DEV-081: surface loft limits in compact capabilities"
```

### Task 7: 收尾回归、台账与证据同步（不发布）

**Files:**
- Modify: `docs/work-items/DEV-081.md`（「本批验证」节）
- Modify: `docs/validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md`（A 批处置列改为已交付并注明未测范围）
- Modify: `docs/BACKLOG.md`（DEV-081 行状态与最新证据，计数保持 172）

**Interfaces:**
- Consumes: Task 1—6 的六个新测试模块与提交。
- Produces: 一份 DEV-081 验收记录，含命令、结果、环境、dirty 状态、受测源码指纹与未测范围。

- [ ] **Step 1: Run the unified check**

Run: `.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-081 --unit-timeout-seconds 1200`
Expected: `build/development_check.json` 中 `success=true`，全量 `unittest discover` 通过（不以分拆测试代替），无新增语言问题；超时不算通过，出现 `timed_out` 时调整预算重跑而非拆分。

- [ ] **Step 2: Run the ledger and repository checks**

Run: `.venv\Scripts\python.exe tools\check_backlog_counts.py` 与 `git diff --check`
Expected: 前者 exit 0 且 `172 / BUG 75 / FEAT 61 / DEV 36` 三方一致；后者 exit 0。

- [ ] **Step 3: Record the evidence**

在 DEV-081 的「本批验证」写入实际结果：HEAD/提交号、工作树 dirty、受测源码指纹、Windows/Python/Ruff/clang-format 版本、上述命令与结果；明确「未编译原生执行器、未连接 Creo 9/10/12.4、未做 WorkBuddy 黑盒、未跑源码包解压全量单测、未做远端 Release 核对」。MAPPING 的 A 批各行标为「离线已交付，实机未验」，B/C 批保持留卡；BACKLOG 的 DEV-081 行更新状态但不改计数。

- [ ] **Step 4: Verify no release artifacts changed**

Run: `git status --short` 与 `git --no-pager diff --stat`
Expected: 只有本计划的源码/测试/文档改动；无 `version.py`、`native/constants.inc`、`build/`、已发布附件或历史反馈原件的改动；`version.py` 仍为 `0.19.2`。

- [ ] **Step 5: Commit the evidence only**

```bash
git add docs/work-items/DEV-081.md docs/validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md docs/BACKLOG.md
git commit -m "DEV-081: record offline acceptance evidence"
```

不合 `main`、不建标签、不发 Release；B/C 批另出子计划并在具备 Creo SDK / 实机 / WorkBuddy 条件后执行。

---

## 自审（writing-plans）

- **Spec coverage：** F02→Task 1、F03→Task 2、F04→Task 5、F05 的 compact 缺口→Task 6、F07→Task 3、F11 的文档部分→Task 4；F01/F06/F08/F09/F10 与 F11 的原生错误上下文属于 B/C 批，在 Spec（MAPPING 第三节）和工作卡留卡，不在本计划冒充覆盖。F06 的 tail 截断已由 DEV-077 修复，不重复。
- **Step scan：** 每个 Step 只做一件事；测试步骤给出测试名、断言和报告里的精确数值；代码步骤给出函数签名、文件与固定值；验证步骤给出命令与通过标志。
- **Type consistency：** `validate_solid_profile`、`validate_operations`、`Dimension`、`_next_steps`、`_section_summary`、`snapshot()` 在前后任务中的名字与返回类型一致；`limits_note` 只在 Task 6 定义并使用。
- **Review Focus：** 五条各自的任务与测试名已在上面标出，对应测试写在各任务 Step 1。
- **Proportion：** 计划只给签名、断言值和决策，不抄写实现代码；`DECK_ENTITIES` 是 Spec 的固定输入，不是实现。
