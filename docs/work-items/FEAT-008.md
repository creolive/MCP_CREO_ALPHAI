# FEAT-008：工具输入、引用与能力说明的一致性

日期：2026-10-16 补全。类型：功能。优先级：P2。状态：待规划。目标版本：未排期。

## 当前进度（2026-10-21）

0.4.5已交付NO_CURRENT_MODEL结构化转换、接管预检阶段诊断及README默认摘要/分页接口用法，见[实施证据](../validation/BUG076-FEEDBACK042-2026-10-21.md)。已有稳定拒绝原因、实际单位/未知字段与支持状态表继续有效，不重复当成待开发；预算根因仍由BUG-076定位，装配只读检查归FEAT-045。

整卡仍待规划首批底板holes、对称深度/编辑和平面引用构造。后续说明还须覆盖逐工具引用与互斥示例、矩阵/组件label/源件快照、revolve实际选轴回显、drawing_view默认模型、恢复空值与原生名称。曲面支持标记和版本历史展示仍是建议；creo_execute_plan已支持单job顺序多op，“没有批量接口”的反馈先核实能力发现或具体限制，不重复开发同义入口。

来源：既有能力契约项、[DEV-028 WorkBuddy 复核](../validation/DEV-028-WorkBuddy-review-20261016.md)、[履带反馈](../validation/TRACK-FEEDBACK-2026-10-16.md)第十一、十二、十四、十五节。回调实际加载/兼容预检由 FEAT-029 独立承接，其余范围继续归本卡。

## 首批范围与顺序

1. **底板 holes 传参。** 核对公开 schema、WorkBuddy 实际送出的原始请求和原始校验错误，再用独立 MCP 客户端提交真正 JSON 数组作对照，覆盖省略、空数组、有效单/多孔、null 及非法字符串。客户端 anyOf 序列化是报告线索，不能从 `/holes: must be array` 直接确定服务端根因，也不预先承诺改成 array 即解决。
2. **对称深度和编辑闭环。** 核对 extrude 的 positive/negative/symmetric、depth 与原生驱动尺寸，公开说明总深/单侧深及坐标方向；报告称 symmetric 是总深，须在本机回读确认后才写成当前契约。以检查尺寸归属/可编辑性 → 修改已有自由驱动尺寸为标准例，不把新建重复切除当成尺寸修正。
3. **平面与构造特征。** 结合 BUG-031 区分已有面匹配、显式基准特征引用及字符串+offset 建面；说明可见的隐式构造特征和数量。结果回显选中/创建对象的范围先选型，不擅改全部工具引用语义。

capabilities compact/full/section、逐工具包装与互斥示例继续按实际工具分批核对；body 必须从当前 inspection 查询，不能用列表下标。不得用本次三项通过关闭整份能力文档工作；底板 one_shot/续编能力另归 FEAT-028。

## 验收标准

| 场景 | 可判断的预期结果 |
| --- | --- |
| 原始请求对照 | 保留 schema、客户端身份/版本、真正传输形状和原始错误；明确失败发生在客户端、MCP 解析还是服务校验，无法取得请求时保留未确认 |
| 专用底板单孔 | 40×30×6、中心 Ø6 通孔通过 creo_create_plate 本身创建，体积 7200−54π≈7030.353996706 mm³；原生孔、保存重载 true。通用 execute_plan 替代不计此入口通过 |
| 默认/空/多孔/非法 holes | 按已确认契约兼容或给准确迁移/错误指引，合法几何与孔位置正确；无隐式丢孔或客户端字符串绕过 |
| 对称拉伸 | 固定平面和轮廓，positive/negative 与 symmetric 实际材料区间、尺寸和体积可独立核对；例如确认总深 96.375 时对应两侧 48.1875，而非把 48.19 当精确值 |
| 尺寸编辑和引用 | 当前查询得到的自由尺寸可驱动修改，保存重载/revision 正确；关系控制拒绝明确，模糊平面按 BUG-031 契约处理 |
| 文档与接口 | 示例真实可调用，工具 schema/描述/能力/说明一致，未支持的组合明确标识；语义变化有兼容与迁移说明 |

开发：Windows x64 / Creo 12.4 / 匹配 SDK，校验改动补回归，原生改动做相应构建与保存重载。WorkBuddy 直接通过已连接 MCP 验收，不读取仓库/配置或运行本地测试；客户端原始传输证据由可取得该证据的测试发起者留档，不能让黑盒 Agent 用源码推断补齐。

## 实现与证据

本次只补任务卡，没有修改 holes 可空数组 schema、对称深度或原生工具；专用底板在旧 WorkBuddy 报告中仍未执行。正式修改前先确定根因和最小兼容方案。

## 2026-10-17：0.3.3 新增契约细节

[四份反馈补录](../validation/FEEDBACK-0.3.3-2026-10-17.md)在原有范围补充以下细节，不改变首批三项顺序：

- 报告 B 的组件身份可由 aliases 的业务 label 和 source_model_id/source_revision 还原。评估在 components compact 内联这些字段，保留现有 aliases 兼容，具体体量与裁剪归 FEAT-023；不能将自动生成的 model_name 直接认定为身份信息丢失。
- 明确 source_snapshot 的当前快照语义：源件修改不会自动联动；显式源件更新方案归 [FEAT-012](FEAT-012.md)，不把尚未实现的联动写成已支持。
- 补 revolve 的省略 axis 规则、实际选用轴/坐标系及回显范围。默认内部参考不当然是错误，须用显式轴与省略轴的几何对照核实；材料无变化的切除反馈另归 BUG-054。
- 报告 D 提出独立 drawing_view 与计划 op 的 model 默认/必填差异，核对 schema、默认模型解析及返回身份，合法请求结果一致或给准确差异说明；无效/歧义引用不得误用其他模型。round 的 radius/size 差异仍归 BUG-019。
- 报告 A 的 wall/flange aliases 已带构造明细，可作为参数文档线索，字段含义仍需对照当前接口和实际几何，不因存在回显关闭 depth/thickness、flip 等缺陷。

上述均为 0.3.3 外部观察，当前 0.3.4 未复测。后续验证需覆盖默认/显式输入、实际引用与几何、保存重载及兼容说明；本轮不改工具或支持声明。

## 2026-10-17：0.3.4 恢复空值、特征引用与分页契约

[新反馈](../validation/FEEDBACK-0.3.4-2026-10-17.md)补恢复可空参数经真实 MCP 的契约核对（缺陷归 BUG-055），以及 dump_feature_tree 的别名 h34 可用、原生名 H34 不匹配；与 FEAT-006 共同明确可接受的引用类型/大小写及错误指引，不直接开放模糊名称匹配。

list_models 的 complete=false / next_cursor 为报告方实际分页正例，说明书需强调第一页不等于全量、按游标继续查询；未取得全部预算边界证据，不据此关闭整项。支持文案应按具体环境/功能分支标已测、外部失败或未知，种子生产版本及失败根因未核实前不把报告建议写成确定事实。

## 2026-10-18：revolve.sketch 与 loft.sections 的引用差异

[0.3.7 外部反馈](../validation/FEEDBACK-0.3.7-CREO13-2026-10-18.md)（[原件](../validation/feedback-0.3.7-creo13-2026-10-18/report.md)问题 1 附带说明）称 revolve 的 sketch 标签字符串可解析，整数 feature_id=40 报 `Unknown feature label: 40`，job `2dea38904e644da7819bda098a424ab6`。该 job 在原件的旋转失败列表也出现，具体请求待核对；本项不把引用失败算成原生创建失败。

补入逐工具引用支持矩阵：分别核对独立 revolve、计划 revolve 的标签/整数/数字字符串，与 loft.sections 的已声明支持对照。loft 的整数兼容范围归 [BUG-028](BUG-028.md)，不能自动扩展为全部 sketch 参数契约。先明确现有支持，选择准确的字段说明/校验错误，或在身份解析无歧义时提供兼容整数引用；不直接把数字字符串一律解释成标签或 ID。

验收应覆盖合法标签、整数、数字字符串、未知 ID 和不存在标签；文档/schema/错误提示一致。若只支持标签，拒绝须说明使用标签及查询方式；若新增整数支持，须验证实际选中特征、几何、revision、失败回滚与保存重载，覆盖真实 MCP 两入口。状态仍为待规划，本次未改接口或复测；旋转创建 -1 另见 [BUG-067](BUG-067.md)，命名规则另见 [BUG-069](BUG-069.md)。

## 2026-10-19：接管拒绝错误与会话诊断说明

[WorkBuddy接管补录](../validation/ADOPTION-WorkBuddy-2026-10-19.md)报告assembly只读inspect被明确拒绝，但返回工具级文本错误，没有可直接读取的code/reason字段。在本卡补统一拒绝错误契约的改进线索：评估稳定机器可读原因与现有MCP工具级isError/文本的兼容方式，保持类型、证据、revision和通道保护；尚未选型或修改运行格式，不新增一个同义缺陷ID，首批三项顺序保持。

同报告观察session_model_id在part/assembly间重复，不能单独当身份键；query_codes.subtype只在part/sheetmetal分支出现。FEAT-043及接管说明已澄清临时发现ID与按实际查询输出诊断的边界，0是查询成功码而非modified值；这两点不直接登记为实现缺陷。真正的未知业务字段仍按既定null语义处理，不把缺失诊断等同于查询失败。

同日后续非毫米inspect则返回结构化available=false/reason，而assembly为工具级错误，两种不可接管形式的兼容与稳定原因分类继续归本卡；本轮两种保护均有通过报告。非毫米载荷内units="mm"及未换算volume_mm3是独立真实摘要缺陷，已登记[BUG-072](BUG-072.md)，不混作本卡错误格式问题。

后续外部依赖及含抑制特征的健康拒绝亦通过；健康理由合并failed/suppressed/incomplete，没有公开逐特征原因。若后续增加细粒度诊断，保持稳定原因分类与原错误兼容，不能从feature_count=9推断具体DTM1状态，也不能据抑制用例判真实再生失败已验收。当前仅补改进线索，不新增同义条目或扩大本卡首批范围。

## 2026-10-25：0.5.0 反馈第二批第二阶段（官方装配重建管线配套）

来源：[0.5.0 反馈整合计划第二批](../development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)与
[装配编辑流程改进建议](../validation/feedback-0.5.0-2026-10-22/2026-10-22_CREO10_v0.5.0_装配编辑流程改进建议.md)
P1-2/P2-3/P3 及 §3。范围（本阶段实现，实机/WorkBuddy 仍待验收）：

1. **官方流程示例与说明**：`examples/assembly_rebuild_pipeline.json`（检查原装配→
   按路径收养→新建托管装配→单个 execute_plan 多组件→统一保存重载→回读验证）
   与 `examples/assembly_multicomponent_plan.json`（单作业批量插入）；配套
   `docs/ASSEMBLY_REBUILD.md` 说明 inspect 归一化毫米变换约定（行向量 4×4，
   3×3 R 加独立毫米 translation，p_parent=p_local·R+t；不自动转置/修正；原
   变换未知或不支持时明确拒绝）、source_snapshot 语义与变更摘要/type_name 用法；
   开发者 MCP 集成入口 `tools/test_assembly_pipeline.py`。首期单层、健康毫米
   独立零件/钣金；重复 occurrence 复用收养 model_id、独立组件 label。
2. **source_snapshot 明确**：源件编辑不自动更新已插入组件；当前重新生成方式
   为 remove_component 后重新 assemble_component（按当前源 revision，原 label/
   位姿需重新指定，引用与约束需重新核对）或新建装配重建；文档与示例不承诺
   component_placement/regenerate/save 可更新源件快照，不实现显式源件更新与
   嵌套装配。
3. **组件变更摘要**：含组件操作的作业结果增加有界 `component_changes`
   （committed/rolled_back/unknown_outcome 三态；added/moved/constraints_changed/
   removed 清单，值取自原生操作结果、受管别名与已验证检查，Python 不模拟几何；
   失败/回滚/unknown 不报为已生效）；复用现有 preview.jpg，不新增同义批量装配
   工具。
4. **list_components 约束符号名**：保留 `constraints[].type` 数字码，新增
   `type_name`（统一复用 FEAT-045 会话装配原生约束映射，未知码保留数字并标
   `unknown`）；不扩第三批约束回放。

验收：示例参数经真实 schema 校验单测；变更摘要三态单测；约束符号名离线
helper 与 SDK 编译；matrix/批量收养/管线三个实机驱动编写待用（唯一报告目录）；
WorkBuddy 纯 MCP 场景文档。环境：Windows 11 x64 / Python 3.12.14 / 本机
Creo 12.4 SDK 离线编译；不连接 Toolkit、不故障注入。底板 holes/对称深度/
平面引用等首批范围不受影响，整卡不关闭。

### 2026-10-25 第二阶段实现与离线结果

已实现并离线验证（提交见批次证据
[BATCH2-STAGE2-IMPLEMENTATION-2026-10-25.md](../development/BATCH2-STAGE2-IMPLEMENTATION-2026-10-25.md)）：

- 示例：`examples/assembly_rebuild_pipeline.json`（八步官方管线，含快照再
  生成步骤）、`examples/assembly_multicomponent_plan.json`（单作业三组件），
  参数与真实 MCP schema 一致并由 `tests/unit/test_assembly_examples.py` 锁定；
  说明文档 `docs/ASSEMBLY_REBUILD.md`（毫米行向量约定、source_snapshot 语义、
  变更摘要与 type_name 用法、开发者入口）。
- `component_changes`：含组件操作的 generic 作业 manifest 增加有界摘要
  （committed/rolled_back/unknown_outcome 三态；added 含真实
  feature_id/source_revision，moved 含查询矩阵 from/to，removed 按既有别名
  解析 label）；失败/回滚/unknown 不报为已生效；现有结果字段不变；
  `src/creo_mechdog/component_changes.py` + `tests/unit/test_component_changes.py`
  （纯契约 6 项 + run_generic_job 挂载 4 项）。
- `list_components` 约束符号名：原生 `native/constraint_names.h` 统一
  FEAT-045 会话装配与受管组件清单映射（SDK 枚举 static_assert 钉住数值，
  离线回退值仅供无 SDK harness）；`inspect_constraints` 保留数字 `type` 并新增
  `type_name`，未知码输出 `"unknown"`；离线 harness
  `tools/test_constraint_names.py`（13 组符号 + 未知码）通过，SDK 编译 exit 0。
- 实机驱动：`tools/test_assembly_matrix.py` 补真实普通失败后回滚断言与
  type_name/数字码断言、唯一报告目录；`tools/test_file_adoption.py` 补
  provenance/拒绝原因断言、唯一报告目录；新增
  `tools/test_assembly_pipeline.py`（单作业多组件、预览/摘要/符号名、快照
  语义与再生成）。三者仅编写待用，未连接 Toolkit。
- WorkBuddy 纯 MCP 场景：`docs/WORKBUDDY_FEAT008_PIPELINE.md`。

未测：实机放置/收养/管线、保存重载、WorkBuddy 黑盒、其他 Creo 版本；第三
批约束回放（FEAT-049）未扩。

### 2026-10-25 第二批第三阶段登记（复审收口，行为修改前）

上游逐段读码复审确认六项缺陷，本阶段最小修复（不改写历史 validation
与 stage1/2 测试事实，新证据另建）：

1. **旧装配约束记录不兼容（真实生产缺陷）**：`native/advanced.cpp`
   `inspect_constraints` 新增展示性 `type_name` 后，`native/generic.cpp`
   `verify_saved` 仍整段 JSON 严格比较 `constraints`；旧保存检查点只有
   `{"type":13}`，新查询为 `{"type":13,"type_name":"fix"}`，旧装配后续编辑
   被误报 "Saved assembly constraints changed"。修复：提取生产 helper 只把
   `type_name` 从兼容比较中投影掉，数字 `type`/`offset`/引用/方向/数量/顺序
   校验完整保留；真实 helper 离线 harness 证明旧→新等价通过、真实变化仍拒绝。
2. **变更摘要不得编造回滚**：`component_changes` 对一切非 succeeded 作业一律称
   `rolled_back`；busy 拒绝/未执行分支并无回滚证据。改为按原生
   `rollback_succeeded`/`model_unchanged`/终态/保护信息区分：确证回滚才称
   `rolled_back`；未执行（busy/未启动）称 `no_effect`；执行后失败但回滚未确证
   称 `unknown_outcome`；汇总异常只报 `unavailable` 且不得改变已确认终态
   （成功作业不得滞留 running 或被改成 unknown）。同 job remove+reinsert 同
   label 时 removed 用旧 feature_id、added 用结果别名新 id。compact 投影纳入
   `component_changes`（有界）。
3. **guard 异常收尾**：`tools/guarded_live_run.py` 原假定“driver 退出=作业终态”，
   改为启动前记录基线作业集，成功/失败/异常后持 main guard 期间轮询本轮新
   作业到终态并探针确认 md050 通道静止后才释放；unknown 停止后续 driver、保留
   md050 保护，不证明静止不得声称安全释放；文档不再把“子进程退出前必终态”写成
   已验证保证。
4. **管线驱动修夹具与快照对象**：`tools/test_assembly_pipeline.py` 原把 MCP
   托管输出直接送收养（必被 `managed_output` 拒绝）、快照场景编辑原 source
   而非收养副本、重建场景非可靠验证。改为制备唯一命名外部夹具（记录源 SHA、
   只读）、编辑实际收养 `source_model_id` 并真实改变几何（外伸凸台，体积/bbox
   可核）、用 inspect 归一化毫米变换+来源映射重建并对上冻结快照；fixture 名
   每次唯一。
5. **矩阵驱动补真实回滚与独立几何断言**：单作业先合法移动再以无效 native
   组件引用失败，要求 failed+rollback_succeeded、revision 不变、位姿恢复、
   后续合法修改成功；增加原生保存重载 inspection 体积/bbox 独立物理断言
   （源盒 8 角刚体变换期望边界，非自证矩阵）。
6. **文档/示例/提示词**：`assembly_rebuild_pipeline.json` 不再固定
   `capture.revision=0`；guard 文档给可直接运行的 `--run` PowerShell 单行；
   WorkBuddy 回滚场景改为“先成功变更再普通 native 失败”；快照场景编辑实际
   source_model_id 并区分缓存与刚实测原生数据。

验收：针对性单测、全量 dev_check、约束比较生产 helper harness、Creo 12.4 SDK
离线编译；记录提交/dirty/指纹/SHA/命令/未测范围。不放宽 style baseline；
实机/WorkBuddy 仍待统一安排，本卡不关闭；首批底板 holes 等继续开放。

### 2026-10-25 第三阶段实现与离线结果

六项复审缺陷已全部最小修复并离线验收：约束兼容比较生产 helper
（`native/constraint_compare.h` + 离线 harness，旧→新等价、真实变化拒绝）；
变更摘要四态（`rolled_back` 仅回滚确证、新增 `no_effect`/`unavailable`、
compact 投影、remove+reinsert 双身份）；guard 异常路径终态确认释放
（基线+轮询+通道探针，unknown 保留，exit 3 不声称安全，7 项离线回归）；
管线驱动外部夹具制备/收养副本编辑/inspect 归一化变换重建与体积取证；
矩阵驱动单作业真实回滚 + 原生体积/bbox 独立断言；文档/示例/提示词/CLI
修正（`--run` 单行命令、`revision=0` 固定值移除、WorkBuddy 回滚与快照
场景重写）。676 项单测、全量 dev_check（exit 0）、三个 C++ helper harness、
Creo 12.4 SDK 编译通过；未放宽 style baseline。完整证据见
[BATCH2-STAGE3-REVIEW-CLOSEOUT-2026-10-25.md](../development/BATCH2-STAGE3-REVIEW-CLOSEOUT-2026-10-25.md)。
实机/WorkBuddy 仍待统一安排，本卡不关闭。

### 2026-10-25 第四阶段复审收口（残余缺陷最小修复）

上游最终源码读码确认的四项残余缺陷已最小修复并离线验收：

1. **guard 真实锁释放语义**：释放 main 真实锁唯一条件是本轮全部受理作业
   终态 + 无 md050 原生 worker 存活（checkpoint `native_pid` 进程身份 +
   `creo_worker.exe` 镜像只读扫描双证据，空闲锁不算）+ 字节锁探针空闲；
   unknown 安静后可释放但返回失败并保留 unknown 保护；不可证实时
   `--settle-timeout` 只写报警，入口持续存活持真锁直至可证实，Ctrl+C
   唯一提前退出。`_snapshot_jobs/_new_jobs` 仅 FileNotFoundError 当空，
   每轮重新发现累计晚到作业。11 项离线回归用独立进程真实抢锁断言。
2. **管线驱动**：原生模型/外部源名改用 tag 的 SHA256[:8] 短后缀（≤31，
   旧 24 字符 tag 命名被真实 `normalize_model_name` 拒绝已锁定）；末尾
   replace 操作保留 `op`；全部动态请求提取为 builder 并用真实
   `normalize_model_name`/`validate_operations` 离线校验（+8 项单测）。
3. **矩阵驱动**：AABB 体积不变量仅对有符号置换旋转断言（`[30,90,60]`
   严格增大已数学锁定，+4 项单测）；记录 bbox 明确为预期派生值而非
   Creo 实测装配 bbox。
4. **摘要辅助路径**：作业前快照只对有组件操作的请求读取，读取失败仅
   降级 `component_changes.status=unavailable`（busy/no_effect/unknown
   原语义不变）；committed 摘要改为按真实 feature_id 的净变更
   （add+move→仅 added、add+remove→无净变更、重插双身份、连续 move
   单次净移动、缺结果别名→unavailable，+9 项单测）。

全量 701 项单测、dev_check（exit 0）、四个 C++ helper harness、
Creo 12.4 SDK 编译通过；未放宽 style baseline。证据见
[BATCH2-STAGE4-REVIEW-CLOSEOUT-2026-10-25.md](../development/BATCH2-STAGE4-REVIEW-CLOSEOUT-2026-10-25.md)。
实机/WorkBuddy 仍待统一安排，本卡不关闭。

## 2026-10-20：0.4.1 顶层支持状态与接管拒绝稳定原因

[v0.4.1 反馈](../validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md) P2-2/P1-1/P3-1：能力边界只由"MCP-owned"措辞隐式表达；接管拒绝为文本错误且缺实际单位；空窗口为裸 Toolkit 码。本轮三项：

1. capabilities 顶层新增**支持状态表**（磁盘打开、会话枚举、接管、装配检查各自的支持/工具/边界一句话），把"是否支持打开磁盘外部文件"从隐式措辞变为显式声明；随 FEAT-044/023 的结构变化一并发布并补迁移说明。
2. 接管拒绝（inspect 的 available=false 路径）在文本 reason 之外增加**稳定原因代码**，并携带实际单位字符串与可靠取得的依赖/健康字段；取不到的详情明确标记未知，不补造。毫米、无外部依赖与健康的准入边界本身不变（放宽另按 P1-1 整体评估）。
3. 空窗口裸错误码归 FEAT-006 本轮 NO_CURRENT_MODEL。

装配只读检查另登记 FEAT-045；本卡 2026-10-19 的统一 code/reason 契约评估与本轮稳定原因代码衔接，不重复登记。

三项当日实现并随[验证记录](../validation/FEAT-044-live-2026-10-20.md)实测：支持状态表与分页一并经 stdio 直连确认（compact 含 support_status）；native 八处接管拒绝错误文本加稳定原因前缀；空窗口 NO_CURRENT_MODEL 见 FEAT-006。2026-10-20 晚按 WorkBuddy 黑盒第 16 项反馈（refusal_details 未在错误表面出现）补齐：inspect 对 native 稳定前缀拒绝返回结构化 `{available:false, reason_code, refusal_details}`（native 先于 live 摘要拒绝时单位/依赖/健康如实标 unknown，不留 staging 登记），实机装配窗口验证通过、新增 2 项单元；同轮 `version.py` 定版 0.4.2（用户 2026-10-20 指定 PATCH、弃用 0.5.0 编号）、缺件错误码/幂等键/session_model_id 提示同步（见验证记录第六节）。整卡仍待规划中首批三项（底板/对称深度/平面构造）未动，不据此关闭。
