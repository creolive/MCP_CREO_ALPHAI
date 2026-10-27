# DEV-047 / T08 零件特征生命周期离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[FEAT-036](../work-items/FEAT-036.md)、[FEAT-027](../BACKLOG.md)。任务分支：`codex/dev047-t08-feature-state`，基线 `dda9c3c`（集成分支 `codex/dev047-feedback052`，含 T00—T07）。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。**本轮结论：离线实现完成，实机未验收；`tools/test_t08_feature_state.py` 已编写但未运行。**

## 范围与素材边界

本任务只做离线工作：**未创建 MCP 客户端、未连接 Toolkit、未启动/结束 Creo、未做会话探测或故障注入、未清理 unknown 保护**。`tools/test_t08_feature_state.py` 仅以离线模式运行并输出 `OFFLINE ONLY`。FEAT-036 的原始需求（0.3.3 反馈 B 第 11 节）与 FEAT-027 的原始疑问（删除后 label 是否保留）来自历史文档；本轮没有实机复放，也没有用返回码推断 Creo 行为。装配组件删除仍由 `remove_component` 负责，不是本能力的替代或扩展；本任务未修改该路径。

## 接口与实现

复用 `creo_execute_plan`，新增 `op="feature_state"`，`action="delete"|"suppress"|"resume"`，`targets` 为显式特征标签或非负特征 ID 列表（最多 100 个、必须互不重复、digit-only 字符串按既有 BUG-073 约定归一为 ID）。没有新增独立删除工具，`model_id`、`expected_revision`、单作业事务、失败回滚和 unknown 保护全部复用。

### 原生依赖巡检

`native/generic.cpp` 的 `inspect_feature` 增加真实依赖证据，全部来自本机 Creo 12.4 Toolkit：

| 字段 | 来源 |
| --- | --- |
| `parent_ids` / `parents_query_code` | `ProFeatureParentsGet` |
| `child_ids` / `children_query_code` | `ProFeatureChildrenGet` |
| `group_status` / `group_query_code` | `ProFeatureGroupStatusGet` |
| `pattern_status` / `pattern_query_code` | `ProFeaturePatternStatusGet` |
| `grppattern_status` / `grppattern_query_code` | `ProFeatureGrppatternStatusGet` |
| `embedded` / `embedded_query_code` | `ProFeatureIsEmbedded` |
| `system_required` | 巡检汇总：默认坐标系（第一个 `PRO_FEAT_CSYS`）与模板基准面（非嵌入且父特征为空、父查询成功） |

查询失败只记录原码与 `null`/空数组，不猜测依赖。成员判定只使用真实 `ProGroupStatus`/`ProPatternStatus`/`ProGrppatternStatus` 值；`system_required` 的定义写在结果里，便于调用方复核，不把未验证的名称当作身份。

### 准入与执行

- **Python 准入**（`src/creo_mechdog/feature_state.py`，作业创建前）：`targets` 语法与重复、`action` 枚举、目标存在性、墓碑、`system_required`、组/阵列成员、`incomplete`、状态边界（resume 只接受已抑制；suppress 拒绝重复抑制）逐项检查；依赖闭包（delete/suppress 的全部后代，resume 的已抑制父特征）未在 `targets` 中显式列出时返回依赖清单并拒绝，不自动级联。被组/阵列头覆盖的成员不要求单独列出，因为成员本身被禁止单独操作。
- **原生复核**：同一组规则在 live 模型上再执行一次（依赖闭包、成员、系统对象、状态），使用 `PRO_FEAT_DELETE_NO_OPTS`/`PRO_FEAT_RESUME_NO_OPTS`，没有使用 `PRO_FEAT_DELETE_CLIP*` 或 `PRO_FEAT_RESUME_INCLUDE_PARENTS` 等自动级联/包含父项选项。执行后重新巡检并逐目标核对真实结果（删除后不存在、抑制后 `PRO_FEAT_SUPPRESSED`、恢复后 `PRO_FEAT_ACTIVE`），不符即失败并走既有回滚。
- **装配边界**：原生和 Python 都拒绝 assembly/drawing 模型，信息指向 `remove_component`；组件删除不当作零件特征删除。

### 身份、墓碑与抑制登记

- 删除成功后移除该特征的全部 alias，并写入 `feature_tombstones`（label 或 `#<id>` 键，含 `feature_id`/`label`/`name`/`type_name`/`job_id`）。后续用该标签创建新特征、作为 `feature_state` 目标、或通过 `{kind:"feature"|"datum_feature"|...}`/`sketch` 标签引用，都在 Python 或原生被明确拒绝，不会指向其他对象。
- 抑制不移除 alias，也不改变特征 ID；`suppressed_features` 记录 `{feature_id,label,name,type_name,job_id}`，恢复或删除时移除对应条目。
- `feature_tombstones`/`suppressed_features` 作为模型控制记录字段持久化（`generic_bridge.run_generic_job` 只在成功作业后写入），并进入 `creo_inspect_model` 的 `feature_state` 摘要（计数 + 最多 20 条预览 + `entries_truncated`，保持 32 KiB 摘要预算）。

### 健康、保存重载与回滚

- `inspection()` 只接受登记在 `suppressed_features` 中且实际状态为 `PRO_FEAT_SUPPRESSED` 的对象；未登记抑制、登记对象已不存在或已恢复都会让模型保持 unhealthy，日志 `SUPPRESSION_REGISTRY_MISMATCH=` 记录真实 id/查询结果。原有 "Regeneration produced a failed, suppressed or incomplete feature" 语义没有放宽，`temporarily_suppressed_loft` 的既有种子抑制行为保留。
- 保存重载校验 `verify_saved` 新增“feature_state 提交”模式：仅在该计划确实执行过 feature_state 时允许特征数减少（删除）、状态变化（抑制/恢复）、体积与 body 数变化；其余特征仍逐个核对 id/type/name/dimensions/status，删除集合之外消失的特征（组/阵列成员除外）仍报错。重载后额外核对“实际抑制集合 == 登记集合”。
- 回滚路径先用请求中的原始登记恢复 `feature_tombstones`/`suppressed_features`，再按原有严格 `verify_saved` 与健康检查核对恢复后的模型；部分执行的抑制/删除不会污染登记集合。失败作业不写回登记。

### 结果契约

`feature_state` 是一个输入操作，只产生一条 T02 终态结果（零基 `index`、`execution_status`、`effect_status`）。目标级明细放在该结果的专有字段：

- `feature_state`：`action`、`applied`、`explicit_targets`、`tombstone_count`、`suppressed_count`。
- `targets`：逐目标的 `target`、`feature_id`、`label`、真实 `before`/`after`（`present`/`status`/`suppressed`/`incomplete`/`name`/`type_name`）与 `effect`（`deleted`/`suppressed`/`resumed`）。
- 结果级附带 `feature_tombstones`/`suppressed_features`；compact 投影保留上述字段，`operation_results.annotate_feature_state` 只补 `target_count`/`requested_target_count`/`targets_complete`，原生缺失的明细不会被补造。

T02—T07 的既有字段（`unchanged`、`native_geometry_verified`、帧/轴/单位、`profile`、`native_section`、`preview` 等）未改；忙拒、不排队、不重试与 unknown 保护未改。

## 实机驱动（未运行）

`tools/test_t08_feature_state.py`：

- 默认严格离线：只校验 `planned_cases()` 的 schema 并打印解析体积，不导入 MCP 客户端。
- `--live` 必须同时给 `--confirm-session-usable`；运行前只读取 `config.json` 并要求 `auto_start_creo=false`（不修改）。
- 实机阶段只用 180 秒预算观察 `creo_startup_status`，`busy`/`unknown_outcome`/其它非等待状态立即停止；不自动重试、不重新提交；只轮询 `creo_get_job`。
- 夹具：120×80×10 基板（96000 mm³）→ 圆心 Ø20、高 5 的凸台草图+拉伸（+1570.796327 mm³）。
- 场景：探针草图/凸台基线 → 只删草图被依赖拒绝 → suppress 两目标（体积回 96000）→ resume（回 97570.796327）→ 抑制后失败的体积断言触发回滚（revision/体积/登记不变）→ 过期 revision 拒绝 → 删除两目标（体积 96000、两个墓碑、alias 消失）→ 旧 `pad_sketch` 标签建新草图被拒 → 删除后新增 `pad2` 合法编辑成功。
- 每个成功作业断言 `saved_file_reloaded_and_verified=true`、`execution_status=succeeded`、`effect_status=committed`、`target_count` 与逐目标 before/after；失败作业断言 `rollback_succeeded=true` 且 revision 未推进。报告持久化到 `build/t08_feature_state.json` 并带 provenance（提交、分支、dirty、源码哈希）。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4.0.0 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t08_feature_state -q` | 32 项通过；覆盖准入、依赖、墓碑、抑制一致性、resume 边界、结果投影、提交级拒绝与原生结构守卫 |
| `python -m unittest discover -s tests -q` | 888 项通过，耗时 208.835 秒；既有套件无回归 |
| `python tools/test_t08_feature_state.py` | 输出 `OFFLINE ONLY`，9 组计划输入全部 `valid`；期望体积 base=96000、with_pad=97570.796327 mm³ |
| `python tools/test_t08_feature_state.py --live`（缺确认标志） | 按设计拒绝并退出（exit 2），未连接 |
| 变更 Python 的 Ruff check / format --check | 10 个变更 Python 文件全部通过，未新增风格基线豁免 |
| clang-format 23.1.3 对 `native/generic.cpp`、`native/feature_state.cpp` | `--style=file --fallback-style=none --dry-run --Werror` 通过；`generic.cpp` 的格式化差异只落在本次新增区域 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `3A6FC9050CF0429C5267F42EFE962175B43DB220B183105FE0F8A9A6D729D80F`，该生成物不入库 |
| `python tools/dev_check.py --work-item FEAT-036` | exit 0、`success=true`、`unit_tests=passed`（888 项）、`native_validation=not_run`；`style_summary` 为既有基线（lint 30、未格式化 16），无新增违规；证据 `build/development_check.json`、`build/t08-devcheck.log` |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `dda9c3c7001f0b2aac8ee9db719103c267da3cb2`（dirty=true，含本次 T08 源码/文档改动、既有 `session_activity.json` 本地改写与未跟踪运行文件），受测源码 `checked_source_sha256=457f2bad4f038afe3ec6732a140731f4fabc7d856d842eb18db6b924345ae2de`，生成时间 `2026-10-26T17:15:19Z`；单元结果 `Ran 888 tests` → `OK`（`build/unit_test_report.json`：tests_run=888、failures=0、errors=0）。源码提交后只追加文档，未再改源码。

### 新增单测覆盖

`tests/unit/test_t08_feature_state.py`（32 项）：

- 准入：targets 语法（label/ID/digit 字符串、空、负数、布尔、非法标签）、action 枚举、跨 label/ID 重复；依赖闭包缺失返回清单、全显式集合通过、组头覆盖成员、成员单独操作拒绝、系统必需对象拒绝、未知/不存在目标拒绝。
- 墓碑：tombstone 标签不能作目标、ID 不能重复删除、新特征不能复用、引用对象不能引用；登记只从合法结果写入。
- 抑制一致性：登记但未抑制、未登记却抑制、登记目标消失、记录与实际一致四种情形；resume 只接受抑制对象、重复抑制拒绝、抑制父特征必须同批恢复。
- 装配/图纸拒绝与缺失巡检拒绝；T02 单条结果 + 目标明细、缺失明细不补造、compact 保留字段。
- 提交级：依赖拒绝与墓碑拒绝都不创建 job；成功作业后 `feature_tombstones`/`suppressed_features` 写入模型且 revision 只推进一次。
- 原生结构守卫：三个 `ProFeatureWithoptions*` 存在、无自动级联选项、原生依赖/成员/系统对象复核和保存重载状态断言存在；`feature_state` 已登记到 `REGISTERED_OPERATIONS` 与 `feature_lifecycle` 能力族。

## 未测范围与 T13 实机矩阵（本次未执行）

1. Creo 12.4 上草图/拉伸/切除/基准的实际 delete/suppress/resume：核对特征树、体积、alias、`suppressed_features`/`feature_tombstones` 与 MCP 返回一致；成功保存重载 true、revision 只推进一次。
2. 依赖拒绝的真实依赖清单（`ProFeatureChildrenGet` 的返回是否包含期望子特征）与“显式全目标”操作是否一次成功；若 Creo 对 sketch+extrude 同批抑制有顺序要求，需记录真实返回码，不用离线推断。
3. 组/阵列头的实际行为：本轮只按成员状态拒绝单独操作、放行头/leader；没有实机验证“删除头时成员随动”与组模式下的 tombstone 数量。若实测与假设不符，按原码记录并修正规则，不把猜测写成通过。
4. `system_required` 的模板基准面判定（父特征为空的非嵌入 datum）需要在实机模型上核对：默认坐标系和三个模板基准面应被拒绝；用户创建的基准面应可操作。结果不符时以真实 `parent_ids`/`embedded` 证据修正。
5. 失败回滚的真实性：抑制后断言失败是否确实恢复体积、特征状态与登记集合；没有 `rollback_succeeded=true` 的证据不得报通过。
6. 外部 Creo 9/10 与 WorkBuddy 本轮未执行；本机通过不外推到其他版本或客户端。

本次验收结论：**T08 离线实现完成，实机未验收，live 驱动未运行**。接口、依赖准入、墓碑/抑制登记、健康与保存重载比较、T02 结果投影均已离线落地；FEAT-036/FEAT-027 的实机特征树、体积恢复、回滚与后续编辑证据待 T13 在同一集成源码上取得。`docs/validation/` 历史原件、`session_activity.json` 本地修改及未跟踪运行文件保持原状。
