# DEV-047 / T02 原生操作结果统一离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[BUG-018](../work-items/BUG-018.md)（主项，仅主台账行）、[BUG-030](../work-items/BUG-030.md)（受影响路径）。任务分支：`codex/dev047-t02-operation-results`，基线 `ff65740cf0ecc2d89a9924a6f8bcc7bb62d6def7`（集成分支 `codex/dev047-feedback052`，已含 T00/T01/T03/T04/T05）。源码提交 `f3f844e`。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。

## 改动与接口

- 原生以单一收集入口取代“子分支各自 push + 公共收尾再 push”：`execute_operation` 先清空暂存，`generic.cpp`、`drawing.cpp`、`placement.cpp`、`sketch_edit.cpp`、`surfaces.cpp`、`udf.cpp` 只调用 `stage_operation_result`，公共收尾合并细节后由 `append_operation_result` 追加**一条**终态结果。全部原生源码仅保留一个 `operation_results.push_back`（在收集函数内）。
- 每个已受理输入对应一条有序结果，`index` 为请求中的零基位置（`operation_position`），与输入一一对应；不再把请求回显另 push 一次。`update_sketch_geometry`、`reorder_features`、`export`、`dump_tree`、`udf_inspect`、`datum_csys`、drawing 各操作及 seed 绑定不再产生第二条记录。
- 失败输入由 `execute_operation` 的包装器补一条 `failed` 记录后重新抛出；作业级 `finalize_operation_results` 在回滚尝试之后收口：成功后已执行项为 `committed`（只读作业为 `no_effect`），失败后已执行/失败项仅在 `rollback_succeeded=true`（已恢复并核对保存基线）时填 `rolled_back`，否则 `unknown`；其后未启动的输入按请求补齐 `not_executed` + `no_effect`。失败作业的 `native_result` 现在也包含完整 `operations`。
- 新增字段：`execution_status`（succeeded/failed/not_executed/unknown）、`effect_status`（committed/rolled_back/no_effect/unknown）。既有 `succeeded` 仅在执行结果可确认时为 true；未知、失败、未执行不会补成成功。`unchanged=true`（同几何快捷路径）与 `unchanged` 重排无操作仍保留原值，且成功作业保存重载后只提交一次 revision；`set_dimensions` 同值写入不新增 `unchanged`。
- 种子绑定（`bind_loft_seed`）是计划级构造步骤，不再向 `operations` 追加一条非输入记录，改为返回并写入结果旁的 `loft_seed_feature`（label/feature_id/construction/seed_sha256 不变）；compact 投影同步保留该字段。
- 依赖结果条数生成名称的两处改为使用稳定的操作位置：`advanced.cpp` 的组件副本名与 `drawing.cpp` 的图纸源副本名不再随去重改变编号，也不会在同一作业内碰撞。
- Python 新增 `src/creo_mechdog/operation_results.py`：`generic_bridge.run_generic_job` 在持久化前按原生事实补齐/保留两状态（原生给出的 `unknown` 保持 `unknown`，不补造记录；无 `operations` 时保持缺失）。compact 投影新增 `index`、两状态、`unchanged`、`native_geometry_verified`、`metadata`、`preserved_feature_id`、`reordered`、`sheet`、`parameters`，并保留既有 `file`/`feature_id`/`size`/`material_removed_mm3` 与 T03 帧、T05 轴/单位字段；`component_changes.status` 不参与本契约。
- `server.py` 的 `creo_execute_plan`、`creo_get_job` 说明补充零基 index 与两状态语义；`src/creo_mechdog/operation_results.py` 纳入源码身份清单。未新增/停用工具，忙拒、不排队、不重试与 unknown 保护未改。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t02_operation_results -q` | 18 项通过；覆盖单一收集入口/零基 index/失败收口/回滚证据/未知不得升级/只读 `no_effect`/compact 专有字段、首项与中项失败、成功一项 revision、无 operations 不补造 |
| `python -m unittest discover -s tests -q` | 822 项通过，耗时 217.390 秒（在 `tools/dev_check.py` 内执行）；既有套件无回归 |
| `python -m ruff check` / `ruff format --check`（5 个变更 Python 文件） | `All checks passed!`、`5 files already formatted`；未新增风格基线豁免 |
| 项目 clang-format 23.1.3 对 8 个变更原生文件 | 全部通过；`udf.cpp` 属于本次变更文件，按检查规则整体格式化（存量基线条目未改），其余文件只格式化了本次改动区域 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `2DC23892AEFB2DEF9DE6CE17820B29AF973D43892194F75FFC34B97DD9F0AA7E`，该生成物不入库 |
| `python tools/dev_check.py --work-item BUG-018` | exit 0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；`style_summary` 无新增违规（lint 30 为既有基线，未格式化文件 16 均为既有豁免）；证据 `build/development_check.json`、`build/t02-devcheck.log` |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `ff65740cf0ecc2d89a9924a6f8bcc7bb62d6def7`（dirty=true，含本次 T02 文档改动），受测源码 `checked_source_sha256=0aa026f28c0a42925ef9f36642b9b875c89697c615cfac2922f5e2c9a3cfd2ea`，生成时间 2026-10-26T15:21:45Z；单元结果 `Ran 822 tests in 217.390s` → `OK`。源码提交 `f3f844e` 的受测内容与该指纹对应，提交后只追加文档，未再改源码。

### T13 实机验收矩阵（本次未执行）

1. 同一既有模型计划分别提交 `update_sketch_geometry`（含同几何快捷路径）、`reorder_features`、`export`、`dump_tree`、`udf_inspect`、drawing 操作与 seed 新建：核对 `operations` 条数等于输入数、`index=0..N-1`、`unchanged`/`native_geometry_verified`/`file`/`metadata`/`size`/`material_removed_mm3` 与帧/轴字段仍在，且 compact 与 full 一致。
2. 首项失败、中项失败与末项失败：核对已执行项、失败项、`not_executed`+`no_effect` 的分界，以及 `failed_operation_index`；已有检查点且回滚核验成功时为 `rolled_back`，无检查点或回滚未证实时为 `unknown`（不得凭作业 failed 或历史检查点推断）。
3. 一次成功计划只增加一次 revision，`saved_file_reloaded_and_verified=true`；同几何快捷路径仍是已提交作业（`committed`，不是 `no_effect`）；同值 `set_dimensions` 不出现 `unchanged`。失败后模型/别名可继续合法操作。
4. 组件副本与图纸源副本名称在实际作业中仍唯一，既有别名/特征身份不变；seed 作业的 `loft_seed_feature` 与实际 Blend 特征一致。
5. 只读 `export`/`dump_tree` 作业的 `no_effect`（模型未写入）与 `file` 输出并存，确认不会让调用方误判为失败。

本次验收结论：**T02 离线实现完成，实机未验收**。原生成功/失败/回滚/未执行分支的真实几何与绘图/种子/UDF 行为待上述矩阵取证；`docs/validation/` 历史原件、`session_activity.json` 本地修改及未跟踪运行文件保持原状。
