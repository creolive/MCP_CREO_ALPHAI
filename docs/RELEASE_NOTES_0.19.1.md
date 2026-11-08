# MCP_CREO_MechDog 0.19.1 版本说明

发布日期：2026-11-08。性质：PATCH。本版不新增公开工具（仍为 107），公开工具名称与既有计划 schema 无不兼容变更；新增可选 `rotation_tolerance`、结构化能力限制/示例段，并放宽 `creo_get_job` 长轮询上限到 300 秒。不可用结论与门禁保持不变。

## 本版变更

- **DEV-076 / H13：worker 构建身份驱动的动态 SDK 准入。** `creo_worker.exe build-info` 自报编译期 `source_digest`、`surface_loft` 的 `Probbl.h` 条件状态与 `worker_sha256`；`creo_session_status` 返回 `worker_build_identity`，`creo_capabilities.families.surface_loft` 按已验证身份投影 `available/availability/enabled/unavailable_reason`，`generic_bridge.submit` 在创建 job 前拒绝被编译掉的 `surface_loft`。身份未知时保持 `sdk_conditional`，不以 Python 本机 SDK 或 `release_numeric` 推断。Creo 12.4.0.0 实机返回 verified / compiled；缺头分支由真实 C++ 夹具与单测覆盖，Creo 10 缺头实机仍未验证。
- **DEV-076 / H15：overlap 预算与覆盖诊断。** `surface_group_measure` 在面积不可用时仍保持 `overlap_area_mm2=null`，新增 `sample_budget`、`faces_sampled/faces_total`、`budget_exceeded`、`partial`、`sample_tests_required/attempted`、`sample_test_coverage` 与 `containment_*_observed`。Creo 12.4 四态组实机返回 `sample_budget=20000`、`faces 2/2`、`tests 220/220`、`coverage=1.0`；大面真实预算耗尽样本仍缺。
- **DEV-076 / H16：trim 结果句柄与连续 trim。** `surface_trim` 在 `ProQuiltInit` 接受保留 quilt 后发布 `result_quilt_id` 与 `result_quilt_handle`（`available/id/source/visit_code/basis/reusable_as`）。Creo 12.4 四个 trim 均 `visit_code=-4`、句柄可用；同一模型第二次 trim 以 `result_quilt_id=82` 为目标，面积 600 mm²、保存重载 true、revision 1→2。
- **DEV-077 / R01：可配装配旋转容差。** `assemble_component` / `component_placement` 新增可选 `rotation_tolerance`；默认仍为 1e-6，严格语义不变。显式容差只放宽准入，矩阵按调用方原值回显，不转置、不正交化、不修复；4 位小数方向向量可在声明容差后装配。
- **DEV-077 / R02：契约与体验补强。** `creo_get_mass_properties` 的装配拒绝文本补 `use_tool: creo_inspect_model` 与无副作用说明；`creo_get_job.wait_seconds` 上限由 30 提高到 300（仍只读持久化记录、不占 Toolkit 通道、不重提）；capabilities 新增结构化 `known_limitations`（12 条，含条件、release、证据、是否可配、效果）与 6 个 `plan_examples`，compact 给出计数，full 分页读取且保持 32 KiB 预算。
- **DEV-077 离线补漏沿用。** 质量属性归一化冲突的有界诊断、`native.log` 截断时回退 `result.verify_stages` 的 `timing_source=verify_stages`、台账自动计数门禁 168、0.18.2 四份反馈归档与 RELEASING/POSTCHECK 回填。

## 兼容性与接口

- 公开工具数不变（107）。`rotation_tolerance` 为可选新增字段；未提供时行为与 0.19.0 完全一致。
- `creo_get_job.wait_seconds` 合法区间由 0–30 变为 0–300；超过 300 仍在读取 job 前拒绝。
- `creo_capabilities` 新增 `known_limitations` 与 `plan_examples` 分节；compact 新增两个计数提示。既有 `families`、`operations`、`references` 字段不删改。
- `surface_loft` 的 `enabled` 与 `availability` 现由已验证 worker 身份投影；无已构建 worker 或身份不可信时保持 `sdk_conditional`，不声称可用或不可用。

## 验收摘要

- 全量 Windows 单测：3071 项，0 失败 / 0 错误 / 0 跳过；`tools/dev_check.py --skip-unit --work-item DEV-077` 成功，无新增 lint/未格式化项；`tools/check_backlog_counts.py` exit 0（168）。
- 原生编译：`bridge.py build` 退出 0（Creo 12.4.0.0 SDK / MSVC x64）。
- Creo 12.4.0.0 实机：只读 `session_status(5)` 连通并返回 worker 身份；`tools/test_surface_chain.py --case trim --live` 7 作业通过（含结果句柄与连续 trim）；`--case group --live` 通过（含预算/覆盖诊断）。未做故障注入、未清 unknown、未结束 Creo。
- 远端发布后核对：见发布记录与统一 POSTCHECK。

## 环境

- Windows x64；Creo 12.4.0.0（release numeric 44）；匹配的 Creo Toolkit SDK；MSVC x64 构建工具；Python 3.12（`.venv`）。

## 未测范围与未完成项

- **Creo 9 / Creo 10**：本机无 Creo 9 SDK，Creo 10 未复测；worker 缺头拒绝只在离线 C++ 夹具与单测覆盖，公开 MCP 黑盒未执行。
- **R01 剩余**：草图容差链（可配 `closure_tolerance_mm`、吸附回执、geometry deviation 断言）与 `origin+normal+u_axis` 一等公民建面工具未实现。
- **R02 剩余**：`creo_mirror` 特征子树、无 callback 的 `creo_loft` 退化路线未实现。
- **R03**：`session_health` 的 identity stale 与新鲜 connected 冲突策略未定，unknown 保护未改动。
- **R04**：`quilt_merge` 的 INTERSECT、三片以上、被消耗工具 quilt 内核残留、quilt 边 id、变半径/过渡、圆角后实体化、真实凹谷瓣底、非 mm 与 Creo 9/10 仍未取证；格栅 cut 与 BUG-046 的矛盾未定因。
- **R06**：WorkBuddy 公开 MCP 黑盒、源码包解压后全量单测、Creo 9/10 实机均未执行。
- 大面 overlap 真实 `budget_exceeded` 现场样本未取得；`surface_trim` 开放弧交线诊断仍未实现。

## 附件

发布时生成并上传以下四个附件（两个 ZIP 与两个 `.zip.sha256`）：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.1-source.zip` | 9 160 836 | `eb1644599cff11fb53450c3f02ee5625a71d9b194a6a6170bd515d55cb5b71ef` |
| `MCP_CREO_MechDog-0.19.1-source.zip.sha256` | 101 | `e6b776917e8492b044659b8c97fbebaa9a4a94c3548376a4e148fc1ba1ca3442` |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip` | 493 442 | `a7d864271b2e188e1f2a51eeea2046d15cf8615b10fde9b87beb466e8350657f` |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip.sha256` | 107 | `16206fd52e2aa91f755bfc321beb02fa2403fd8049132d26d34f333befb161e2` |

源码包内含本说明与发布记录，归档生成时无法写入自身 ZIP 的摘要，包内副本保留回填前占位；工作树、Release body 与本表以上述最终值为准。
