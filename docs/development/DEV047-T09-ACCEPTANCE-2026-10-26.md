# DEV-047 / T09 约束快照回放离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[FEAT-049](../work-items/FEAT-049.md)。任务分支：`codex/dev047-t09-assembly-replay`，基线 `14fff0b`（集成分支 `codex/dev047-feedback052`，含 T00—T08）。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。**本轮结论：离线实现完成，实机未验收；`tools/test_t09_assembly_replay.py` 已编写但未运行。**

## 范围与素材边界

本任务只做离线工作：**未创建 MCP 客户端、未连接 Toolkit、未启动/结束 Creo、未做会话探测或故障注入、未清理 unknown 保护**。实机驱动仅以离线模式运行并输出 `OFFLINE ONLY`。本轮不新增 FEAT-050 公共装配比对工具，不实现嵌套回放或新约束类型；现有六种写入类型、事务与忙拒语义全部复用。

快照扩充是原生侧读取真实约束对象的查询结果；离线单测使用合成快照验证规划规则，**不能替代**实机对 `owner_scope`、`occurrence_label`、`asm_side`/`comp_side` 与偏移单位的真实性核对。`docs/validation/` 历史原件、`session_activity.json` 本地修改及未跟踪运行文件保持不变。

## 接口与实现

### 只读快照 schema 3

`creo_inspect_session_assembly` 的快照版本由 2 升到 3。v2 及其游标按旧规则拒绝；回放工具同样明确拒绝旧快照，不静默升级。新增/扩充字段（全部来自本机 Creo 12.4 Toolkit 查询）：

| 字段 | 来源与含义 |
| --- | --- |
| `components[].occurrence_label` / `occurrence_label_query_code` | 组件特征名（`ProModelitemNameGet`），同层兄弟引用的稳定身份；失败为 null + 原码 |
| `constraints[].asm_reference` / `comp_reference` | 双侧引用身份：`owner_scope`（`assembly`/`component`/`nested`/`unknown`）、`occurrence_path`、`occurrence_component_id`、`owner_name`、`item_type`、`item_id` 及原始查询码 |
| `constraints[].asm_side` / `comp_side` | 两侧 `ProDatumside`（`yellow`/`red`/`none`）；`orientation` 保留为组件侧兼容字段 |
| `constraints[].offset` / `offset_unit` / `offset_mm` | 原始偏移、所属装配长度单位（名称/查询码/毫米比例）与毫米口径值；单位未知时 `offset_mm` 为 null |
| `constraints[].placement_kind` | `fixed`/`default`/`auto`，仅放置约束才有 |
| `constraints[].replayable` / `reason` | 可回放判定与稳定原因码 |

`reason` 取值：`type_query_failed`、`unsupported_type`、`automatic_placement`、`missing_assembly_reference`、`missing_component_reference`、`nested_reference`、`component_reference_not_own_component`、`offset_query_failed`、`offset_unit_unknown`。`fix`/`default` 判为可回放的放置语义；`auto` 明确不可回放。

### 只读规划 `creo_plan_assembly_rebuild`

`src/creo_mechdog/assembly_replay.py` 实现 `plan_assembly_rebuild(snapshot_id, component_mapping, reference_mapping)`，`server.py` 只做注册/适配，能力登记在 `capabilities.py` 的 `assembly_replay` 族与 `support_status.assembly_replay`。工具只读：

- 仅读取 `jobs/<snapshot_id>/session_assembly.json` 与受管模型登记/源文件，不建作业目录、不写 revision、不取通道锁、不连接 Toolkit；返回中没有 `operation_results`。
- 快照必须 schema 3、`complete=true`、未截断/未限深、600 秒内；超期明确要求重新快照。十分钟只作为规划证据，计划绑定的源 revision/摘要才是提交授权。
- `component_mapping` 每 occurrence 一条 `{occurrence, label, source_model_id}`，`occurrence` 接受快照 `occurrence_label` 或 `occurrence_path`；重复标签必须用路径区分，缺失/多余/重复/非法标签/非法 model_id 均指出具体条目。
- `reference_mapping` 每源引用一条 `{source:{component,item_type,item_id,side?}, target, target_component?, target_side?}`；`component=null` 表示装配根引用，字符串表示同层兄弟 occurrence。引用按显式身份匹配，不凭 item_id 跨模型猜测；同一源引用多条匹配视为歧义拒绝。
- 操作顺序固定为“全部插入 → 按快照顺序设置约束”。带约束组件先以 `fixed` 插入再 `component_constraints`；源 `fixed`/`default` 保持各自的真实放置操作；无记录约束的组件按观测位姿冻结，并在 `placements[].source_placement` 标为 `packaged`/`unconstrained`。偏移统一用快照单位换算成毫米。
- 规划数超过既有 200 操作上限直接拒绝并声明不拆分事务；`component_constraints` 沿用每组件最多 20 条既有边界。
- 装配侧同层兄弟引用通过约束内的 `assembly_component` 显式表达；`ComponentConstraints` 原生解析在该组件模型内解析引用并构造同级 comppath，禁止把被约束组件自身作为装配侧。

### 源件绑定与复核

每个 `assemble_component` 携带 `rebuild_binding`：`source_model_id`、`source_revision`、`source_part_sha256`、源模型名/文件、occurrence 和 target label。`generic_bridge.submit` 在通道锁内、创建作业前重读登记并流式计算文件 SHA256：

- revision 或 `part_sha256` 变化、文件缺失/越出 `models/<id>/output`、状态非 ready、pending/unknown 均拒绝，错误路径指向 `operations[i].rebuild_binding`。
- 原生执行器加载源件前再次核对绑定 revision 与请求组件登记，不符即拒绝；加载后仍走既有 `verify_saved` 检查。
- 绑定只允许出现在 `assemble_component`；其他操作携带即拒绝。

### 拒绝边界

旧/缺失 schema、超期、不完整/截断/限深快照、嵌套 occurrence、子装配源、未解析/抑制组件、未知毫米变换、未知/不可回放约束类型、`auto` 放置、fixed/default 与其他约束混用、缺失/歧义/多余映射、不可还原的根引用、组件侧 `target_component`、源件变化与超过 200 操作均明确拒绝。失败不创建作业；已受理作业失败仍由既有单作业事务整批回滚。

### 契约保留

T02 每输入一条 `index`/`execution_status`/`effect_status` 的结果投影、T03 帧字段、T05 轴/单位、T06 `profile`/`native_section`、T07 `preview`、T08 `feature_state` 均未改；本工具不产生 `operation_results`。忙拒、不排队、不重试、unknown 保护与单一 Toolkit 通道不变。公开工具数由 92 增至 93（新增只读规划工具），服务注册键仍为 `MCP_CREO_MechDog`。

## 实机驱动（未运行）

`tools/test_t09_assembly_replay.py`：

- 默认严格离线：用真实 schema 校验四类计划输入（fixed/default 插入、兄弟/根引用约束），打印 `OFFLINE ONLY`，不导入 MCP 客户端。
- `--live` 必须同时给 `--confirm-session-usable`；运行前只读 `config.json` 并要求 `auto_start_creo=false`。
- 只用 180 秒预算观察 `creo_startup_status`，非等待状态立即停止；不自动重试、不重新提交；只轮询已受理作业。
- 夹具：120×80×10 基板 + Ø20×20 凸台、Ø18×30 销；源装配含 `default` 放置的基板和四条销，覆盖 `mate`+`align`、`mate_offset`+`align_offset`、`insert`（同层兄弟柱面）、根 `csys`。
- 场景：快照 schema 3 与偏移毫米口径 → 规划（先插后约束、同层 `assembly_component`、每插入带绑定）→ 在新装配执行并核对六类型/偏移 → 移动同层基板 10 mm 验证受约束销真实随动、根引用销不随动 → 改 `mate_offset` 25→40 验证随动 → 缺失映射/缺根引用/过期/旧 schema 拒绝 → 修改源件后再提交旧计划被绑定拒绝，核对目标 revision 与源文件均未变。
- 每个成功作业断言 `saved_file_reloaded_and_verified=true`；报告持久化到 `build/t09_assembly_replay.json` 并带 provenance。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4.0.0 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t09_assembly_replay -q` | 30 项通过 |
| `python -m unittest discover -s tests -q` | 918 项通过，耗时 208.709 秒；既有套件无回归 |
| `python tools/test_t09_assembly_replay.py` | 输出 `OFFLINE ONLY`；4 组计划输入全部通过真实 `validate_operations` |
| `python tools/test_t09_assembly_replay.py --live`（缺确认标志） | 按设计拒绝并退出（argparse exit 2），未连接 |
| 变更 Python 的 Ruff check / format --check | 9 个变更 Python 文件全部通过，未新增风格基线豁免 |
| clang-format 23.1.3 对 `native/advanced.cpp`、`native/generic.cpp` | `--style=file --fallback-style=none --dry-run --Werror` 通过；差异仅落在本次新增/改写区域 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `CEF533E3F30EFC4B5B065629E2240DD7E235DAD0BF8A535C9153B6CE429CDF35`，该生成物不入库 |
| `python tools/dev_check.py --work-item FEAT-049` | `success=true`、`unit_tests=passed`（918 项）、`native_validation=not_run`；`style_summary` 为既有基线（lint 30、未格式化 16），无新增违规；证据 `build/development_check.json`、`build/t09-devcheck.log` |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `14fff0b1dfd76f1aac989e53d44dcf772ed5e53a`（dirty=true，含本次 T09 源码/文档改动、既有 `session_activity.json` 本地改写与未跟踪运行文件），受测源码 `checked_source_sha256=28d90d8022e6b1b7b507106b5b8a7a03c4e16232f9836a753efca096f29e15a9`，生成时间 `2026-10-26T17:55:25Z`；单元结果 `Ran 918 tests` → `OK`（`build/unit_test_report.json`：tests_run=918、failures=0、errors=0）。

### 新增单测覆盖

`tests/unit/test_t09_assembly_replay.py`（30 项）：

- 快照证据：schema 3 接受与窗口报告；缺失版本/旧 schema/超期拒绝；不完整/截断/限深/嵌套拒绝；snapshot_id 与链接目录拒绝。
- 计划：六类型各生成一条约束操作且全部插入在前；fixed/default 各自单列；无约束组件显式冻结；规划不建作业、不取通道锁、无 `operation_results`；201 操作拒绝且不拆分。
- 映射：缺失组件映射点名 occurrence；重复标签用路径区分；非法标签/model_id/多余字段/重复映射；目标标签唯一；源模型状态/类型/revision/摘要/文件校验；非刚体位姿与未知变换拒绝。
- 约束：未知类型、不可回放原因、`auto`、fixed/default 混用；缺兄弟/根引用点名 item_type/item_id；歧义引用；引用映射字段校验；`target_component` 必须已规划且不得用于组件侧。
- 绑定：合法绑定通过；revision/摘要/磁盘字节/文件缺失拒绝；绑定只能出现在 `assemble_component`。
- Schema/原生守卫：计划操作通过真实 `validate_operations`；`assembly_component` 标签/ID/`none` 方向契约；原生源码包含绑定复核、兄弟组件解析、`none` 方向、六类型映射与快照新字段。

## 未测范围与 T13 实机矩阵（本次未执行）

1. 六类约束在 Creo 12.4 的真实效果：`mate`/`align`/`insert`/`csys` 的实际自由度和 `mate_offset`/`align_offset` 的毫米偏移；保存重载后约束与位姿保持。
2. 同层兄弟组件引用的真实解析：`assembly_component` 的 comppath、被引用兄弟件几何 id 与源件副本的一致性；本机未验证跨组件引用是否需要在插入后重新生成。
3. “改变驱动条件后的真实随动”：移动基板 10 mm 与修改偏移 15 mm 后，受约束组件的实际 transform 变化；初始 transform 相同不作为通过证据。
4. 快照新字段的真实性：`owner_scope`、`occurrence_label`、`asm_side`/`comp_side` 与 `offset_mm` 来自实机约束对象，而不是合成夹具。
5. 失败整批回滚：约束设置阶段失败时目标装配的 revision/文件/约束集合恢复；本次只复用既有事务，未注入失败。
6. 源件变化拒绝的实际时点：规划后编辑源件再提交旧计划是否确实在受理阶段被拒，而不是进入原生后才失败。
7. 外部 Creo 9/10 与 WorkBuddy 本轮未执行；本机通过不外推到其他版本或客户端。

本次验收结论：**T09 离线实现完成，实机未验收，live 驱动未运行**。快照身份/方向/单位、只读规划、同层引用表达、绑定复核及拒绝边界均已离线落地；FEAT-049 的六类真实约束、随动与保存重载证据待 T13 在同一集成源码上取得。
