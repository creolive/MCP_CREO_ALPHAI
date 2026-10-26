# FEAT-008/012 第二批驱动响应契约修复证据（2026-10-26）

分支 `codex/feat012-matrix-pipeline`，修复基线 HEAD `c6f75b8`（第一批驱动窄修复，
43 项针对性测试通过）。本轮只离线编辑/测试，只改两个驱动及其测试 + 本证据文档；
未触碰 canonical、生产 `server.py`/`bridge.py`/`src/creo_mechdog/`/`native/`、
配置、原始报告与历史原件；未连 Toolkit / 真 MCP、未启动真 server。

## 未改动的原始证据（只读引用）

- Matrix 原始报告（canonical）：`E:\Projects\MCP_CREO_MechDog\build\assembly_matrix_live_20261025T154117Z\report.json`
  及 guard `build/guarded_live_20261025T154116178338/report.json`：37 个 job，
  11 组位姿全过，预设普通失败原生 rollback 已验证（after.revision == before
  快照，后续合法修改成功），随后 matrix 驱动 line 323
  `source_inspect['volume_mm3']` KeyError，套件中止。
- 主代理取得的实际 API 语义副本：`E:\Projects\md050\build\driver_real_contract_20261025T1555\mcp_payloads.json`
  （公开 MCP 缓存只读 asm 检查，无改模；本轮逐字读取整份，未写入）。

## 核对后的真实公开契约（以实际 server 代码 + 上述语义副本双重确认）

1. `creo_inspect_model` compact：`volume_mm3`/`units`/`units_query_code`/
   `volume_query_code`/`inspection_available`/`inspection_source` 全部在
   `payload.inspection` 内（`bridge.py` 经 `inspection_summary` 归约，
   `model_queries.py:55`；BUG-072：非毫米单位合法地 `volume_mm3=None` +
   非零 query code）；`revision` 仍为顶层。真实源件样本：volume 30、revision 1。
2. `creo_inspect_model` full section（bodies）：记录在 `payload.data.bodies`
   （`data.bodies[0].bbox`），顶层没有 `bodies` 键（`model_queries.py:147-199`）。
3. 同一根级 occurrence 在不同 API 下展示名不同：`creo_list_components` 的
   `model_name='▩C_A3C874E18A0445A10001'` vs `creo_inspect_session_assembly` 的
   `name='C_A3C874E18A0445A1_0'`，同一 component `feature_id`/`component_id`=40、
   `occurrence_path=[40]`。展示名不能当 join 身份；重复 occurrence 还共享同一
   原生 copy 名。稳定身份 = 根级 `occurrence_path`（depth 0 时 ==
   `[component_id]`，与已查询 `feature_id` 一致）。

## 缺陷与最小修复（仅驱动，生产返回语义不变）

### matrix 驱动（tools/test_assembly_matrix.py）

- 新增共享 helper `compact_inspection(payload)`（line 48）与
  `full_section_records(payload, section)`（line 78）：按真实 compact/full
  契约取值；保留并加强验证强度（`inspection_available`、`units=='mm'`、
  `units_query_code==0`、`volume_query_code==0`、volume 必须为正数且存在，
  缺失值一律断言失败，绝不默认 0/通过——BUG-072 非毫米语义不被绕开）。
- line 323/329/344 三处 compact 体积读取改经 `compact_inspection`；line 364
  bodies 读取改经 `full_section_records(..., "bodies")`。
- 其余字段使用系统核对后无需改动：`creo_list_components` 内
  `aliases[label].feature_id` ↔ `components[].feature_id` 为同一响应内
  稳定 ID 关联；job manifest 的 `revision`/`model_id`/
  `saved_file_reloaded_and_verified` 契约不变；rollback 验证、
  bbox derived 免责声明、knownpoint、save-reload 断言全部保留。

### pipeline 驱动（tools/test_assembly_pipeline.py）

- `volume_of`（line 393）原样 `return call(...)` 且直接读顶层
  `volume_mm3`，两处皆错：改为 async，compact 查询后走与 matrix 同一个
  `compact_inspection`（从 matrix 驱动导入，单一实现防再漂移）。
- occurrence 关联改为根级路径：`index_occurrences(components)` 按
  `tuple(occurrence_path)` 建索引并断言 `depth==0`（本批无嵌套，非根级
  拒绝而非猜测）、路径唯一、路径非空；`rebuild_operations` 用
  `(feature_id,)` 查根级 occurrence，并断言 `component_id==feature_id`、
  `transform_mm_known`。`copy_name` 仍记录在 frozen 快照与报告中作为证据，
  不再作为身份键。step 7 另断言 `next_cursor is None`（整页取齐，防止
  分页静默漏 occurrence）。
- offline 原型 `request_plan`/`validate_plan` 同步：原型 occurrence 输入
  改为真实 session component 形状（`occurrence_path`/`component_id`/`depth`/
  `transform_mm_known`/`transform_to_parent`），且刻意使用与 copy_name
  不同的展示名（真实样本 '▩C_A3C874E18A0445A10001' vs
  'C_A3C874E18A0445A1_0'），锁死路径 join；占位 ID 重绑定
  （`bind_adopted_sources`）不变，任何提交分支仍不得残留占位值。

## 离线复现与回归（真实载荷形状，不再只测 schema 形状）

新 `tests/unit/test_driver_inspect_contract.py`（13 项）：用最小化真实 DTO
（compact volume 30/revision 1/units mm/全零 query code；bodies 在
`data.bodies`）先复现旧访问的 KeyError（顶层 `volume_mm3`/`bodies`），再
验证修复路径；缺失 volume、非毫米单位（BUG-072 语义）、缺失顶层 revision、
空 section 全部必须断言失败，不默认 0/通过；并锁定两个驱动共享同一个
`compact_inspection` 实现。

`tests/unit/test_assembly_pipeline_requests.py` 改写（37 项全过）：
frozen 快照带 `feature_id`；occurrence 用真实 session 形状；
`OccurrencePathBinding` 新增回归——跨 API 名称不同但根级路径一致可绑定、
重复来源共享 copy 名但不同 occurrence 路径各自绑定、同名 occurrence 不
塌缩、depth!=0 / component_id 不匹配 / 重复路径 / 空路径 / 未知 mm 变换
全部拒绝；占位 ID 相关回归原样保留。

## 验证命令与结果（2026-10-26，本机 .venv）

- `python -m unittest tests.unit.test_driver_inspect_contract
  tests.unit.test_assembly_pipeline_requests tests.unit.test_assembly_matrix_poses
  tests.unit.test_assembly_matrix_rollback` → 43 项全过，exit 0。
- `python -m unittest tests.unit.test_tool_driver_entries` → 全过，exit 0。
- `python tools/test_assembly_matrix.py --help`、`tools/test_assembly_pipeline.py
  --help`、`tools/test_assembly_units.py --help` → 均 exit 0（离线入口，
  无 Toolkit 连接）。
- Ruff `check` 4 个改动文件 → All checks passed；`format` 后
  `format --check` → 4 文件全过。

## 未测范围

- 修复后的两个 live 驱动未在真实 Creo 会话重跑（按约定本轮全部离线；
  实机、WorkBuddy 与发布由主代理负责；上一全量 726 项中 1 项锁测试因
  主代理并行持有实际守卫而 ToolkitBusy，未记通过，由主代理在 native 后
  独立全量重跑）。
- 全量 dev_check 未跑（按本次范围要求）；嵌套子装配不在本批，
  depth!=0 在驱动侧显式拒绝。
- 生产返回语义未做任何改动；未将任何缺失值默认为 0/通过。
