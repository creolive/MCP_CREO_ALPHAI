# FEAT-008/012 实机驱动失败窄修复证据（2026-10-25）

分支 `codex/feat012-matrix-pipeline`，修复基线 HEAD `aac3c84`（FEAT-048 readiness
收养前置，39 项针对性测试通过；全量 710 项通过见 `78c4bfe`）。本次只改驱动与驱动
测试，不碰生产业务源码、canonical 工作树、配置或 native。

## 未改动的原始证据（只读引用）

两份失败报告与两份 guard 报告均位于 canonical `E:\Projects\MCP_CREO_MechDog`，
本次未做任何写入；guard 两轮均 `released`，无自然 unknown：

- Matrix：`build/assembly_matrix_live_20261025T151808Z/report.json`
  （guard `build/guarded_live_20261025T151807442040/report.json` 及 `child_0.log`）
- Pipeline：`build/assembly_pipeline_live_20261025T152542Z955f3b2d/report.json`
  （guard `build/guarded_live_20261025T152541178279/report.json` 及 `child_0.log`）

## 缺陷 1：matrix 驱动对失败 manifest 的 revision 字段假设

现象：35 个作业 succeeded（11 组姿态矩阵 + Euler 实际保存重载/查询）后，第 36 号
预设 compound 作业（move + remove invalid 424242，job
`47d5dfc90089459080fb5a0b7e57674a`）按设计原生 failed（toolkit-23），
`result.rollback_succeeded=true`、`inspection_source="rollback_verified"`、
`component_changes.status="rolled_back"`。生产侧失败 manifest **合法地没有顶层
revision 字段**（回滚后无新 revision 可登记）。驱动
`tools/test_assembly_matrix.py` 原第 281 行
`assert failed["revision"] == assembly["revision"]` 抛 KeyError，套件中止，
回滚与快照之后的断言未执行。

复现（离线）：`tests/unit/test_assembly_matrix_rollback.py`
`test_revision_less_manifest_matches_unmodified_live_evidence` 用与原始报告一致的
manifest 形状（无 revision 键）先复现旧行为的 KeyError，再验证新逻辑通过。

修复（仅驱动）：新增模块级 `verify_rolled_back_failure(failed,
assembly_revision, before, after)`（tools/test_assembly_matrix.py:48）：

- 保留原有强度：`status=="failed"`、`rollback_succeeded is True`、
  `component_changes.status=="rolled_back"`、`before == after`（接受动作一并回滚）。
- 用**实际 MCP `creo_list_components` 查询**的 `after.revision` 核对
  `assembly["revision"]`，失败 manifest 有 revision 时才附加一致性核对，
  缺失字段不编造默认成功值。
- 后续合法修改、独立体积/bbox 断言原样保留。

## 缺陷 2：pipeline 驱动提交离线原型占位 ID

现象：两源件创建成功、外部只读副本成功、`creo_adopt_file` inspect/apply 两项独立
成功、空原装配成功；随后 original assembly 的 `creo_execute_plan`（原始报告 call 48，
model_id `59545a5f...`）仍携带离线 validate_plan 原型占位 `source_model_id`
`aaaa...`/`bbbb...`，入口以 Unknown model_id 拒绝且无新 job。真实
`adopted_ids`（按 `input_path` 键控）建立后未重绑定 `plan.original_operations`。

修复（仅驱动）：新增 `bind_adopted_sources(plan, adopted_ids, external)`
（tools/test_assembly_pipeline.py:196），在 adoption 成功后按 `input_path` 取真实
受测返回 ID 重建 `original_operations` 并经真实 `validate_operations` 复核；run()
其余分支逐一核对——rebuild/replace 自真实 list_components / inspect 数据构建，现在
提交前同样过真实校验器；offline validate_plan 与全部 geometry/revision/save
reload/snapshot 断言强度不变。

复现与回归（离线假数据，不启动真实 server）：
`tests/unit/test_assembly_pipeline_requests.py` 新增 `AdoptedSourceBinding`：
随机非占位 adopted IDs + 真实样式 `input_path` 走通 original/rebuild/replace 全
数据流，任何提交分支不得残留占位 ID；未知 input_path 必须报错；
`validate_plan` 只校验 schema 形状、不校验 ID 真实性（占位通过校验），以此登记
"只测形状漏占位 ID" 的缺口。

## 验证命令与结果

- `python -m unittest tests.unit.test_assembly_matrix_rollback
  tests.unit.test_assembly_pipeline_requests tests.unit.test_assembly_matrix_poses -v`
  → 24 项全过。
- `python -m unittest tests.unit.test_tool_driver_entries
  tests.unit.test_helper_layout -v` → 7 项全过（三 driver CLI `--help` 直跑与
  `-m` 入口）。
- Ruff `check` + `format --check`（4 个改动文件）→ 全过。
- `tools/test_assembly_units.py --help`、`tools/test_assembly_pose.py --help`
  → 离线入口成功（SDK 调用替换，无 Toolkit 连接）。

## 未测范围

- 修复后的两个 live 驱动未在真实 Creo 会话重跑（按约定本轮全部离线；实机、
  WorkBuddy 与发布由主代理负责）。
- 生产失败 manifest 无 revision 的行为按原始报告实际字段为准，未要求生产增字段。
- 全量 dev_check 未跑（按本次范围要求）；上次全量 710 项通过在 `78c4bfe`。
