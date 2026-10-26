# 统一开发台账

建立：2026-10-13；最近更新：2026-10-26。当前服务／源码与交付版本为 0.6.1，BUG-082 主平面 autodim 编辑修复与回归驱动适配见[版本说明](RELEASE_NOTES_0.6.1.md)和[发布验收记录](validation/RELEASE-0.6.1.md)。修复批本机 Creo 12.4 编辑专项 16/16 通过；种子矩阵剩余场景因 Toolkit 断开受阻，WorkBuddy、外部 Creo 9 未验收。前一版为 [0.6.0](validation/RELEASE-0.6.0.md)；第二批装配管线已交付，第三批及各父卡未覆盖范围继续开放。

本页只安排未完成工作和单列的历史观察；完成结论见[完成档案](BACKLOG_COMPLETED.md)。各固定 ID 只出现一条任务记录，工作卡和原始证据保存详细输入、历史过程与已测范围。

## 当前安排

- [0.5.2 三份反馈完整交付计划](development/0.5.2-FEEDBACK-PLAN-2026-10-26.md)已按用户选择保存，目标 0.7.0，由 [DEV-047](work-items/DEV-047.md) 汇总；[T00—T13 派发表](development/0.5.2-FEEDBACK-TASKS-2026-10-26.md)列出依赖、步骤、接口、验收与新对话提示词，由用户指定负责人。新增 [BUG-084](work-items/BUG-084.md) 记录公共平面引用忽略显式 id 的静态缺口，其原生影响待复现；既有条目只推进本次子项。当前只保存文档，未实施功能、连接 Toolkit 或派发新 agent。本批仅开发者离线与本机 Creo 12.4 实机验收，不要求 WorkBuddy；旧现场和会话限制保持，最终统一合入 main 并发布一次 Release。

- [0.5.0反馈整合计划](development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)（三份[原件](validation/feedback-0.5.0-2026-10-22/manifest.json)已逐字节归档）：第一批证据、状态与正确性由 [DEV-046](work-items/DEV-046.md) 收口（BUG-080 装配变换单位契约与 FEAT-006 收养拒绝逐特征诊断已随 0.5.2 交付，验收范围见卡）；第二批可靠装配重建管线（[FEAT-048](work-items/FEAT-048.md) 按路径/批量收养，矩阵入参归 FEAT-012/BUG-045，Task 4 已完成开发者实机验收，WorkBuddy 经用户取消未执行，多组件单作业批量装配官方示例与验收归 FEAT-008 现有 `creo_execute_plan`）；第三批约束保真、比对与运维（[FEAT-049](work-items/FEAT-049.md) 约束回放、[FEAT-050](work-items/FEAT-050.md) 装配比对、DEV-027 显式世代回收）。原环境 Creo 10 证据与本机 Creo 12 证据分开记录，报告预计性能收益仅作建议。

- [0.5.0/0.5.1 Creo 9 反馈计划](development/0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md)：BUG-082 根因修复、完整编辑回滚证据与 FEAT-030 受控引用/manifest 测试驱动适配随 0.6.1 交付；编辑专项 16/16 通过。[BUG-081](work-items/BUG-081.md) 保留 MCP 拒绝时序、[BUG-083](work-items/BUG-083.md) 保留原生非法分支与外部验证；[FEAT-030](work-items/FEAT-030.md)/[BUG-034](work-items/BUG-034.md) 剩余九种子矩阵因 Toolkit 通道断开受阻，待用户人工检查 Creo 并满足 BUG-001 恢复纪律后补跑。Creo 9 -16、种子生产来源/重生成、外部复验与 WorkBuddy 继续开放；哈希校验不等于建模通过。

- [0.4.6反馈整合计划](development/0.4.6-FEEDBACK-PLAN-2026-10-21.md)（三份[原件](validation/feedback-0.4.6-2026-10-21/manifest.json)已归档补录，0.4.7 发布后开工）分两批推进：第一批盘点口径补齐与证据收口（DEV-027 loader/payload 盘点区分引用三态、FEAT-046/FEAT-043/044/DEV-027 外部通过子项关闭、DEV-045 附件名 0.4.7 起定名核对通过、BUG-077 原环境复测单列）；第二批 FEAT-045 装配只读检查（新增 `creo_inspect_session_assembly`）按 MINOR（0.5.0）随版交付，四类受限场景与外部复核按卡开放。矩阵放置、重建编辑与装配整体收养为后续路线不随本轮实施。
- [0.4.4反馈整合计划](development/0.4.4-FEEDBACK-PLAN-2026-10-21.md)（覆盖 v0.4.4 构建验收与 v0.4.5 运行反馈两份[原件](validation/feedback-0.4.4-2026-10-21/manifest.json)）：BUG-077/FEAT-047/DEV-044 五组验收已随 0.4.7 交付（[发布核对](validation/RELEASE-0.4.7.md)）；BUG-078（恢复 accept 路径 Backup 稳定 -1）自该计划登记待修。
- [0.4.3反馈完善计划](development/0.4.3-feedback-improvement-plan-2026-10-21.md)两批已随 0.4.6 交付（用户指定 PATCH，含新工具例外；[发布核对](validation/RELEASE-0.4.6.md)）：BUG-076/BUG-057/FEAT-046/FEAT-043/044/DEV-027 的单元、构建与本机实机核心+改动点验收完成；各条剩余原环境、外部锁复验、擦除矩阵与 WorkBuddy 黑盒按卡推进。
- 恢复、回调生命周期、接管/枚举与磁盘打开仍有验收空缺，按各卡剩余动作推进；已发布不等于整项完成。
- 其他建模失败先取得最小输入和受测环境再复现；功能候选与工程迁移按下表规划，不增加双版本验收门槛。

## 分类与使用规则

| 状态 | 数量 | 下一步 |
| --- | --- | --- |
| 开发中 | 4 | 继续已登记的分期工作 |
| 待复现 | 20 | 补齐输入与环境，复现并定位（新增 BUG-084：静态引用缺口已确认，原生影响待验证） |
| 待核实 | 12 | 明确输入、规则或预期后再定性 |
| 验收中 | 29 | 按卡补齐剩余验证，不重复计入旧成功（FEAT-048 按当前工作卡归类；BUG-081、BUG-083 转入） |
| 待规划 | 45 | 确定范围、兼容规则与验收方法 |
| 待开发 | 1 | DEV-047 方案与派发表已保存，由用户指定负责人后推进 |
| 观察中 | 2 | 出现新证据后再转回调查 |
| 已交付/已修复/已验收（未收口，状态保留） | 7 | 归类口径：已交付2、已修复，WorkBuddy复验通过（待发布）1、已修复（验收中）3（BUG-082 根因修复+全套回归，2026-10-26 入列）、已验收（本机）1；均有另期保留范围，按各卡待收口下一步收口后再移档，不改原状态凑数 |

共 120 项：118 项未完成工作、2 项历史观察。历史观察的原优先级仅保留来源，不代表当前排期或发布阻断。2026-10-26 在原 118 个唯一 ID 的基础上新增 DEV-047、BUG-084；FEAT-048 继续按“验收中”归类，其余分类数量保持。

- 收到失败报告不等于根因已确认；部分实现/通过只缩小剩余范围，不批量关闭。状态变化同时同步工作卡，完成项及时移入档案。
- 新工作先登记固定 ID、目标、范围、环境与验收要求；执行过程写入工作卡或证据，使用[模板](templates/WORK_ITEM.md)。
- 当前验收按本机 Windows x64 / Creo 12.4 / 匹配 SDK 的实际改动范围取得证据；其他环境按反馈跟进，不把本机通过外推。完整约定见[开发入口](DEVELOPMENT.md)。
- Toolkit 通道忙时立即拒绝，不排队、不自动重试；已接受作业只轮询。unknown_outcome/recovery_pending 继续保留保护，不因文档精简、重启或清字段而解除。
- 本机只用 E 盘 dev 服务；新的Toolkit连接/故障注入仍须满足根级规范中的会话核对条件，不擅自结束Creo或清保护。WorkBuddy仅通过公开MCP黑盒验收，开发者证据分开记录。

## 开发中

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| [DEV-047](work-items/DEV-047.md) | P1 | 待开发 | 0.7.0 | [0.5.2 反馈计划](development/0.5.2-FEEDBACK-PLAN-2026-10-26.md)与 [14 项任务派发表](development/0.5.2-FEEDBACK-TASKS-2026-10-26.md)已保存，用户自行指定 agent/新对话。完整范围含引用/坐标/方向/多环、操作结果、预览、特征生命周期、约束回放、只读健康和显式世代回收；优先复用已有工具，开发者离线+本机 Creo 12.4 验收，本批不要求 WorkBuddy。当前只文档准备，T00 源件归档待执行；未实施、未连接 Toolkit，最终一次 main+Release。 |
| [DEV-046](work-items/DEV-046.md) | P1 | 第二批实机通过，WorkBuddy 取消未执行；第二批已随 0.6.0 交付 | 0.6.0 | 第一批 BUG-080/FEAT-006 已随 0.5.2 交付。第二批 Task 4 FEAT-012/BUG-045 矩阵创建/更新管线已实现并完成开发者实机验收（38 父作业含故意失败成功回滚、11 姿态基向量/已知点、rev 递进、保存重载、约束符号名、体积 330 独立断言；补充 4 次真实改变位姿 rev 36→40）；第二阶段（2026-10-25）FEAT-008 官方管线示例/说明、组件变更摘要、list_components 约束符号名与 FEAT-048 锁顺序小修复已实现；FEAT-048 两批真实夹具实机（2+1 成功、3+2 拒绝、0 unknown、rev 1、窗口/源字节不变、same-key 回放、依赖探针分支）与最终管线 b86 实机（10 父作业全成功，快照刷新新唯一 label，7200→7800、12384→12984、装配 rev 3→4）通过；独立全量 dev_check 748 项 0 失败 0 错误（b86 干净树）。用户 2026-10-26 决定取消本批 WorkBuddy 测试（未执行，不记通过）并授权合入 main+Release；第二批已随 0.6.0 交付。FEAT-048/FEAT-008 其余范围及第三批 FEAT-049/050、DEV-027 回收、FEAT-012 显式源件更新/嵌套继续开放。 |
| [BUG-077](work-items/BUG-077.md) | P0 | 验收中 | 0.4.7 | 530项单测及[0.4.7黑盒](validation/WORKBUDDY-0.4.7-2026-10-21.md)正常主线、分页、拒绝保护和并发busy通过；[小型真实非空迁移、同键回放及后续编辑/保存重载已通过](validation/WORKBUDDY-0.4.7-NONEMPTY-2026-10-21.md)；[>16 MiB超限迁移→收养→编辑实机链路通过](validation/BUG077-OVERSIZE-MIGRATION-2026-10-21.md)；[恢复链路四动作矩阵+restore_baseline/abandon_new通过](validation/BUG077-RECOVERY-2026-10-22.md)；[图纸消费点+两处拆分遗漏修复随版交付](validation/BUG077-DRAWING-2026-10-22.md)。accept_saved/accept_live两动作[健康会话各3/3通过](validation/BUG078-ROOT-CAUSE-2026-10-22.md)，事故会话关联及旧现场仍保留、待操作者选择收尾；原环境复测继续开放。485条真实旧登记未迁移，不清保护。0.4.7已随版交付（d23866a/v0.4.7/Release 420203117）。 |
| [BUG-078](work-items/BUG-078.md) | P1 | 验收中 | 待排期 | [根因已定位](validation/BUG078-ROOT-CAUSE-2026-10-22.md)：全部-1集中于复用孤儿nmsd的事故会话（trail 70条dbg_err_crash），代码序列无罪、零行为改动；accept_saved/accept_live健康会话各3/3独立夹具闭环（同键重放、恢复后编辑过）；偶发编辑-1十组对照未复现保留子项；三个旧现场仅restore_baseline可用待操作者收尾。 |
| [DEV-044](work-items/DEV-044.md) | P1 | 已交付 | 0.4.7 | 0.4.7五组验收全部执行完毕（超限迁移/恢复链路/图纸消费点/health异常/发布），[发布核对](validation/RELEASE-0.4.7.md)；DEV-027二进制可复现性/安全回收另期保留，不标全计划完成。 |
| [FEAT-047](work-items/FEAT-047.md) | P1 | 已交付 | 0.4.7 | 正常/异常场景与32KiB均实测； 正常数据526条/11页公开黑盒无重无漏；[预警/损坏/超限/32KiB逐页实测通过](validation/BUG077-HEALTH-2026-10-22.md)（单条损坏不中断扫描、最大页19,895B、其他543条登记不变）；[0.5.0 外部报告 §3.2](validation/feedback-0.5.0-2026-10-22/manifest.json) 212条目正常数据与超限条目明细外部确认。原环境异常数据还原与32KiB原始字节未覆盖，按卡保留。 |
| [DEV-002](work-items/DEV-002.md) | P2 | 开发中 | 未排期 | 继续Python包迁移，下一批处理seeds/capabilities及后续服务/启动/桥接依赖；前两批证据见卡，安装入口、资源和运行数据定位须同步核对。 |
| [DEV-030](work-items/DEV-030.md) | P1 | 开发中 | 未排期 | 继续G2底板与编辑、G3履带基础/性能、G4阵列及完整履带分期；恢复与回调剩余验收分别归 FEAT-018/029。三键放宽子项已交付并取得[外部七键复测通过](validation/feedback-0.4.4-2026-10-21/report-dev027-030.md)，不再重复调查。 |

## 需要复现或核对的问题

<a id="待核实缺陷"></a>

### 有失败报告，待当前环境复现

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| [BUG-084](work-items/BUG-084.md) | P1 | 待复现 | 0.7.0 | 静态确认 main 2af3853 的 plane/datum_plane 解析忽略显式 id，按默认 Z 或 normal/axis/offset 筛选；Python 同分支亦未校验 id。先统一 ID/几何筛选/特征标签契约和实际帧回显，再复现 Right 面纯 Z U 轴、倾斜拉伸及两平面交线轴，关联 BUG-063/064/065；尚无当前实机证据，不直接采信“拉伸固定 Z”或认定所有问题同根。执行见 T03/T05。 |
| [BUG-080](work-items/BUG-080.md) | P1 | 实机+A/B通过，WorkBuddy第三轮待复验 | 0.5.2 | [装配变换呈 x/25.4 指纹、文档声明 mm](validation/feedback-0.5.0-2026-10-22/manifest.json)（外部 Creo 10 / 0.5.0）：inspect 显式输出装配单位、变换统一毫米坐标映射并保留原始矩阵与单位信息；混合单位验证完整坐标映射，无法确认标未知并传播不完整标志；关联 FEAT-045。2026-10-23 实现独立复审通过（无必修，4 项 Minor 已登记见卡；单位查询+毫米完整映射+原始矩阵+完整性传播+特征状态失败置 incomplete/身份查询码保留/局部非有限矩阵修正；离线原生 case 1–27 与 walk 状态共享化夹具（assembly_walk.h/test_assembly_walk.cpp）已实跑通过、生产复编 exit 0（947f40e，886eb0d 尖端复现夹具/单测/复编；SDK 查询替换/注入 visitor 非真实 ProSolidFeatVisit）；947f40e 全量 557 项单测与统一 dev_check 通过（success=true）），实机混合单位验收 2026-10-24 通过（英寸装配+毫米组件：length_unit in/25.4、组件 mm/父 in、归一平移 25.4/50.8/76.2 与 raw 1/2/3、complete、会话不变，[记录](validation/BUG080-FEAT006-LIVE-2026-10-24.md)），WorkBuddy 黑盒待执行。 |
| [BUG-081](work-items/BUG-081.md) | P1 | 验收中 | 诊断已随 0.5.3 交付；剩余验证未排期 | [0.5.0 外部报告 §五](validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)（外部 Creo 9/0.5.0）：终态作业的仍存活 owner 使 `creo_migrate_registry` 两次拒绝且负载无停止证据（alive=None 不区分 Windows 错误），inspect 不预标注阻塞条目；本地同参直调通过发生在 owner 死亡后，不据此定性误判。**2026-10-25 阶段三已实现诊断**：inspect 预标注 `owner_block` + 顶层 `blocked_entries`，apply 在锁内重验并返回有界 `owner_block`（recorded/observed、Windows 错误、reason_code、next_steps），15 项单测与 612 例全量、dev_check 通过；停止判定语义与 BUG-074 时间证据适用面**未改**。剩余：实机 MCP 拒绝时序未复现（无同型残留 worker 现场，不新增故障注入），需外部 Creo 9 或用受控现场确认后才决定是否改停止判定。见[阶段三收口](validation/PHASE3-CLOSEOUT-2026-10-25.md)。 |
| [BUG-082](work-items/BUG-082.md) | P1 | 已修复（验收中），随 0.6.1 交付 | 0.6.1 | [0.5.1 外部报告 §三](validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)（外部 Creo 9/0.5.1）：在轴扇形初始回转成功，就地改角/改半径失败、REV1 status=6、回滚干净。**2026-10-26 根因实证并修复**（[根因记录](development/BUG082-AUTODIM-ROOT-CAUSE.md)）：`ProSectionAutodim` 在重建截面仅生成 0–1 个尺寸，截面级再生容忍欠约束，但 `ProFeatureWithoptionsRedefine` 后特征级从尺寸方案重解失败（REV_SK/REV1 均 UNREGENERATED、特征尺寸清零）；创建路径因直接采用截面几何不受影响（判别实验：autodim 创建 80° 成功、编辑失败）。修复：显式 `autodim` 编辑在主平面复用 BUG-079 坐标尺寸升级路由（非静默：solver 记录 requested/used，[SKETCH_STABILITY](SKETCH_STABILITY_0.2.5.md) 与工具描述同步）；全套编辑专项实机 16/16（含外部组合 auto→autodim、autodim 四连编辑、开环非法几何失败回滚夹具），离线 14 项单测。剩余：外部 Creo 9 复测与 WorkBuddy 黑盒按需；非主平面 autodim 编辑保持既有边界；球体/半圆贴轴基线失败仍为独立观察子项。 |
| [BUG-083](work-items/BUG-083.md) | P2 | 验收中 | 预检已随 0.5.3 交付；剩余验证未排期 | [0.5.1 外部报告 §四](validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)（外部 Creo 9/0.5.1）：`revolve.axis={"entity":"ax"}` 透出 nlohmann 裸异常（key 'kind' not found），无可操作信息，回滚干净。**2026-10-25 实机双路径通过**（[收口记录](validation/PHASE3-CLOSEOUT-2026-10-25.md)）：省略 axis + 内部中心线 `revolve_modes` 3/3；`examples/revolve_external_axis.json` 显式轴隔离新件成功（revision 1、体积 3141.592653589793=1000π、保存重载 true、无失败特征）。负路径为入口离线预检：缺 kind/错误类型/空对象/不适用引用被拒且不派发原生作业，省略与 null 等价、空对象按缺 kind 拒绝。剩余：原生 `validate_revolve_axis` 未在真实执行器触发（Python 先拒），外部 Creo 9 未复测，WorkBuddy 按需；按卡留验收中，不外推为 Creo 9 已修复。 |
| [BUG-079](work-items/BUG-079.md) | P1 | 已修复，WorkBuddy 复验通过（待发布） | 下一PATCH | 就地改弧半径再生失败根因已核实：autodim 在半径变化截面上欠约束（缺 y 位置尺寸），残留孤儿特征尺寸使草绘特征再生失败；显式坐标尺寸路径成功对照确认。修复：未变实体跳过/变更实体 Delete+Add（centerline 保 Replace）+ 主平面 auto 编辑路由到坐标尺寸路径；MSVC lambda 捕获缺陷一并规避。原生全套（回转/拉伸变体、BUG-062 夹具、编辑专项 11 项、general_core、554 单测）通过；WorkBuddy 复验场景 1–3 通过、场景 4 经提示词输入勘误后实证修复有效（见卡内复验表）；外部 Creo 9 离轴构型复验通过（R5→R6→R5 逐位一致，见卡 2026-10-23 补录）。 |
| [BUG-058](work-items/BUG-058.md) | P1 | 待复现 | 未排期 | 窗口观测与指引已实现；外部无主窗口 -11 根因仍待复现。本机同码 -4 已定位客户端侧 RPC 端点自举端口错位（详见卡 2026-10-22/23 节），触发条件未定；历史外部 -11 为不同层，保持待复现。**2026-10-25 小修**：guidance 区分挂起窗口（hidden/visible）与活动 Dashboard/模态框，统一前置核对清单，结束进程只作为操作者明确选择的恢复项，3 项单测通过；仅文案，状态机与观测字段未动，仍需外部现场复现 -11。 |
| [BUG-062](work-items/BUG-062.md) | P1 | 已修复（验收中） | 下一PATCH | [centerline 加入就地编辑允许集合](validation/BATCH2-EDITING-2026-10-22.md)：schema 缺口补齐（原生分支本就存在），回转草图 R5→R6 两入口实机通过（体积/ID/rev/保存重载），负面三路径保持拒绝；2026-10-23 会话重启后独立复验通过，WorkBuddy 黑盒验收 centerline 核心行为与三拒绝路径通过；改弧半径失败为独立缺陷 [BUG-079](work-items/BUG-079.md)。 |
| [BUG-063](work-items/BUG-063.md) | P1 | 待复现 | 未排期 | 复现非原点轴 10×36° 阵列去料错误，与过原点轴、柱面取轴对照；核对实例变换及实际轴位置。自校验告警和显式轴参数仍需方案，关联 BUG-065。 |
| [BUG-064](work-items/BUG-064.md) | P1 | 待复现 | 未排期 | 复现 surface 平面引用失败及纯 Z 向 u_axis 报 Zero direction vector 两条路径，核对引用分支与坐标帧计算；明确平行法向的拒绝，免引用平面输入另评估。 |
| [BUG-065](work-items/BUG-065.md) | P2 | 待复现 | 未排期 | 复现两平面交线轴并断言原点/方向，核对是否误取首平面法向；评估公开 origin/direction 与 inspect axes，保留柱面取轴对照，关联 BUG-063。 |
| [BUG-066](work-items/BUG-066.md) | P2 | 待复现 | 未排期 | 复现体积正确但 preview.jpg 断裂失真的模型，定位显示集/曲面/网格路径；视角选择归 FEAT-041，预览不能代替几何验收。 |
| [BUG-030](work-items/BUG-030.md) | P1 | 已验收（本机） | 下一PATCH | [最终收口](validation/BUG030-CACHE-CLOSEOUT-2026-10-22.md)（2026-10-22/23 节）：连接恢复后九项专项 9/9、实体分支核验（arc/centerline/ellipse/spline；闭合样条按保守路径）、general_core 7/7、BUG-062 复验、554 单测、同会话空闲复连全部通过；以最终源码重取全部证据。原 0.3.1 改尺寸失败仍未复现，保留历史现象。WorkBuddy 黑盒与发布待安排。 |
| [BUG-029](work-items/BUG-029.md) | P1 | 已修复（验收中） | 下一PATCH | [重排槽位修正与矩阵](validation/BATCH2-EDITING-2026-10-22.md)：new_feat_num 为原树编号，按移动方向折算，连续性/重叠/重复前置校验；5 正例、6 负例及连续块后移等补测通过。原三次 -2 根因未确认；原位 no-op 仍保存验证且 revision +1（历史证据 3→4）。2026-10-23 随最终收口以最终源码复验通过（reordered=false、树序/ID 保持、rev+1）；WorkBuddy 黑盒与外部环境未测。 |
| [BUG-034](work-items/BUG-034.md) | P1 | 待复现 | 未排期 | 取得 Creo 9 种子加载 -16 的完整输入和环境，查生产版本与加载原因；哈希 available 不等于可加载，本机其他版本成功不能关闭此项。兼容观察与 FEAT-030 联动。**2026-10-25**：-16 失败诊断与来源透明化已实现（保留原始 API/错误码/阶段/种子哈希/运行版本，原因无证据时为 `undetermined_by_error_alone`，不硬写“由 12.4 构建”）；本机 12.4 两种子加载与保存重载成功只证明本机，Creo 9 未复验，**保持待复现**。 |
| [BUG-035](work-items/BUG-035.md) | P1 | 待复现 | 未排期 | 复现 shell=2 后 dimension_pattern 孔阵列增料与 r7 环箍，检查 leader、树顺序和阵列规则；以无抽壳及 axis_pattern 对照实际去料与重载。 |
| [BUG-032](work-items/BUG-032.md) | P2 | 待复现 | 未排期 | 核对钣金开放/闭合壁 depth、thickness 和草图轴语义，复现 depth=1、thickness=232、线长185得到185×232×232的报告；逐类验证几何、折弯、重载及回滚。 |
| [BUG-046](work-items/BUG-046.md) | P1 | 待复现 | 未排期 | 复现钣金实体与增料块真实重叠仍 -1、同件 cut 正常的对照，先确认原生规则；支持路径须保留钣金/展开能力并重载，不支持组合给出限制。 |
| [BUG-049](work-items/BUG-049.md) | P1 | 待复现 | 未排期 | 先复现两个不相交 R1 圆贯穿切除，再比较相交、相离、嵌套和相切轮廓；随后核对履带63站/奇偶分组，不预先改成布尔并集或认定嵌套非法。 |
| [BUG-051](work-items/BUG-051.md) | P1 | 待复现 | 未排期 | 复现相切直线/圆弧闭合轮廓 solve/autodim=-1，与纯直线对照后核对 Intent Manager 和调用顺序，不全库倒序或默认降级。 |
| [BUG-053](work-items/BUG-053.md) | P1 | 待复现 | 未排期 | 对报告552～644秒的大模型记录各阶段耗时和查询次数，再评估引用解析/遍历复用及失效规则；优化后仍保留保存重载与保护检查。 |
| BUG-003 | P1 | 待复现 | 未排期 | 检查倾斜草图的尺寸是否正确：用 30° 矩形拉伸 4 mm，核对体积是否为 800 mm³。还要测试尺寸编辑、保存后重新打开，以及失败时能否恢复修改前的模型。 |
| BUG-004 | P1 | 待复现 | 未排期 | 在实验环境检查 Creo 12 的两截面种子。先核对 Blend 引用、对象句柄和种子文件身份，再对比直线、平滑及三截面情况。完成要求包括几何、尺寸编辑和保存后重新打开均正确。 |
| BUG-015 | P2 | 待复现 | 未排期 | t30_probe 中，对 body id=52 做 translation=[0,0,15]，特征创建后保存失败，干净模型的对照测试却成功。用查询得到的真实 body ID，分别测试 group、pattern、shell 与 transform 的组合，查清保存阶段的问题。成功时体积不变、位置正确且能重载；失败时保留保存点和 revision，并检查模型是否仍可用。返回字段的含义另由 BUG-012 处理。 |
| [BUG-039](work-items/BUG-039.md) | P2 | 待复现 | 未排期 | 核对 thicken(new_body=true) 的实际材料归属，与 extrude 对照 body 数、几何及重载；不能只改计数或以分离团块代替原生 body。 |
| [BUG-048](work-items/BUG-048.md) | P2 | 待复现 | 未排期 | 用等价序列对比镜像有无、顺序、变换、分组和抽壳引用，复现抽壳 status 6；提供真实原因，保留回滚，不把状态码直接认定为几何限制。 |
| BUG-011 | P1 | 待复现 | 未排期 | 通道异常时，状态查询有时给空错误或仍显示旧 ready。已有会话首次查询还出现 building_worker/connected=false，跨日出现 checking 不结束，建模返回 connect=-4。需要说明结果来自实时检查还是旧快照，并显示验证时间和是否过期；查询、提交都应在规定时间内返回明确原因。TimeoutExpired/launch_reserved 的新反馈尚未复测，关联 FEAT-001；异常通道恢复与未知任务保护按现行恢复契约处理。 |
| [BUG-075](work-items/BUG-075.md) | P2 | 待复现 | 未排期 | 对一次 invalid_probe_result 取得探针日志，定位worker异常或连接竞争；显式retry曾恢复ready，尚不足以证明自愈或根因。见[黑盒报告](WORKBUDDY_037_REMAINING_RESULT.md)第0.1节。 |

### 输入或规则待核实

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| BUG-012 | P1 | 待核实 | 未排期 | transform 失败后，几何和 revision 没变，模型却被标为 failed；0.3.1 还有成功作业返回 rollback_succeeded=false，履带报告也出现同样误读。0.3.5/Creo 10 实机再现：新建零件失败（自交轮廓）时 inspection=null、rollback_succeeded=false 并残留 failed/revision 0 的登记与 .prt.1——新件无检查点可回滚是事实，但 false 易被误读为"回滚失败"，反馈建议改 null/not_applicable；另守卫触发时作业级 toolkit_code=-1 属异常路径汇总码（disconnect_code=0、通道健康），建议与真实 Toolkit 故障区分。需要分别说明回滚未尝试、成功、失败和无法确认时的含义，以及模型还能否使用，并检查保存点和旧字段兼容性。false 本身不能证明模型损坏，unknown_outcome 保护也不能直接清除。关联 FEAT-018。 |
| BUG-016 | P2 | 待核实 | 未排期 | solidify(cut) 用 z=30、positive 侧的基准面裁剪 z=20..40 的实体后，体积和 bbox 未变，却显示特征成功。先查清 side、pull_direction 和引用是否适用，再对比两侧裁剪并检查重载。应区分允许不改材料的操作、无效输入和真正切除，不能把所有零变化都判失败。 |
| BUG-018 | P2 | 待核实 | 未排期 | 旧报告中 export/dump_tree/update_sketch_geometry 的结果重复；0.3.1 和 0.3.2 的失败计划又只返回 null 或空 operations。每个请求应对应一条带序号的结果，说明已执行、已回滚、失败、未执行或结果未知，并带上文件、特征和参数。0.3.5 钣金回归中 5 次失败计划仍均返回空 operations 数组，调用方无法知道哪些已成功、只能整批重发。核对成功及失败时的数量、顺序和失败位置；operation_outcomes 的接口建议仍待评估，不能据此自动重跑后半段。关联 FEAT-006。 |
| [BUG-031](work-items/BUG-031.md) | P1 | 待核实 | 未排期 | 明确 mirror 平面 offset 是匹配已有面还是要求建面，核对 offset=45 失败与0/省略对照；验证多共面最小ID规则及无匹配/多匹配提示，不全局改变选面。 |
| [BUG-037](work-items/BUG-037.md) | P1 | 待核实 | 未排期 | 核对 horizontal/vertical 单whole、distance 双whole 的 -2 与双点对照，逐类检查端点解析；支持组合须驱动几何并重载，零距离先查实际坐标。 |
| [BUG-040](work-items/BUG-040.md) | P2 | 待核实 | 未排期 | 核对钣金恒报2个body、负ID/无bbox与履带state=3/4对象的原生含义及取数来源；不能据此删体或认定同源，未知数量仍为null。 |
| [BUG-041](work-items/BUG-041.md) | P2 | 待核实 | 未排期 | 明确 mate/align 与偏移约束的参数规则，核对非零offset静默为0；支持时实际面距、保存值与重载一致，不支持时明确拒绝。 |
| [BUG-045](work-items/BUG-045.md) | P2 | 离线+开发者实机已核对；WorkBuddy 取消未执行；随 0.6.0 候选交付 | 0.6.0 | XYZ Euler 旧语义保持，行向量局部到父级契约及唯一 3×3 矩阵输入已实现；生产 helper 核对 XYZ ±90°、组合/奇异姿态、基向量/已知点；2026-10-26 实机核对：11 组姿态按实际查询矩阵基向量/已知点验证、Euler/矩阵双入口放置回读一致、保存重载 true、补充 4 次真实改变位姿 rev 36→40 一致；用户 2026-10-26 取消本批 WorkBuddy（未执行）；外部 Creo 9/10 环境未验证，继续开放。 |
| [BUG-047](work-items/BUG-047.md) | P1 | 待核实 | 未排期 | 固定边和高度只切换flip，核对内折bbox、材料侧、原生特征及重载；厚底板方向敏感报告单列，四壁释放归 FEAT-014。 |
| [BUG-052](work-items/BUG-052.md) | P2 | 待核实 | 未排期 | 区分模型对象类别与几何曲面类别，核对全为type=34的报告，再兼容返回真实类型与参数；bbox不能证明SDK类型错误。 |
| [BUG-060](work-items/BUG-060.md) | P2 | 待核实 | 未排期 | 核对 sheetmetal_unbend.fixed_surface 接受的引用类型，支持组合验证展开与重载；若只接受面引用，明确给出 surface ID 查询和输入示例。 |
| [BUG-061](work-items/BUG-061.md) | P2 | 待核实 | 未排期 | 核对字典平面非零offset的引用/建面语义，与mirror offset共查解析路径；说明现有datum_plane替代，验证方向、重载及拒绝时revision不变。 |

## 剩余验收

<a id="当前优先功能"></a>
<a id="已确认待开发"></a>

已实现/已交付的历史与测试细节见工作卡；下表只列尚未完成的动作，不把本轮文档检查当作建模验收。

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| [FEAT-048](work-items/FEAT-048.md) | P1 | 开发者实机通过；WorkBuddy 取消未执行；随 0.6.0 候选交付 | 0.6.0 | Task 5 path/batch adoption implemented: 1-20 paths, inspect/apply, explicit resident provenance, independent commits, unknown stop. Offline tests/build/helper evidence in card; stage-2 lock-order fix committed 2026-10-25. 2026-10-26 开发者实机两批通过（aac3c84）：批次一父作业 536d15c0，2 成功（existing_resident/fresh_retrieval）+3 拒绝（unhealthy/non-mm/duplicate）+0 unknown；批次二父作业 0df31918，真实历史依赖件 external_dependencies 拒绝→继续→健康件成功→duplicate 拒绝，1 成功 2 拒绝；rev 1、保存重载/窗口/源字节不变、same-key 回放、依赖探针 9e48e7ec（健康毫米但 dependency_free=false）均核实。modified/wrong-origin/token 超时仍只离线；用户 2026-10-26 取消本批 WorkBuddy（未执行）；[Contract](FILE_ADOPTION.md)；[实机证据](development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md)。 |
| [FEAT-044](work-items/FEAT-044.md) | P1 | 验收中 | 0.4.6 | 磁盘打开已交付；本轮 `loaded_session_models` 有界摘要（会话模型数/组件实例数/详情入口）与冲突提示装配依赖来源已在[开发分支](validation/FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)实施；剩余 `asm_mx.asm.16` 原环境、显示失败、unknown、真实并发验收与实机观察。 |
| [DEV-027](work-items/DEV-027.md) | P2 | 验收中 | 0.4.6 | 指纹稳定化已取得[外部 Win10/Creo 10 实测通过](validation/feedback-0.4.4-2026-10-21/report-dev027-030.md)（json.hpp 换行翻转场景注册/DLL/目录数稳定），该子项关闭；0.4.6 外部 dry-run 静态确认+[盘点口径补齐](work-items/DEV-027.md)实施中（loader/payload 双维度、引用三态分类、记录缺失损坏冲突保留+needs_review，回应"记录丢失误列回收"，保持零删除）；剩余盘点实机复核、同源码二进制可复现性及安全回收。 |
| [BUG-050](work-items/BUG-050.md) | P1 | 验收中 | 未排期 | 中心线轴向漂移主线已修复；仍缺原 Creo 10 切线链0.487mm、0.3.5的22.264mm完整输入及斜中心线验证，取得后复现。成形实体与1e-5守卫阈值保持。 |
| [BUG-074](work-items/BUG-074.md) | P1 | 验收中 | 未排期 | 历史身份停止证明已实现；剩余真实Windows跨启动四种恢复动作与WorkBuddy验收，同次启动/身份不明继续拒绝，不清unknown或原作业。 |
| [BUG-076](work-items/BUG-076.md) | P1 | 验收中 | 0.4.6 | 0.4.5诊断与资料分离精修均交付；[原环境根因已取得](validation/feedback-0.4.4-2026-10-21/report-registry-bloat.md)（注册表条目 21,472,751 B、origin_conflict_scan），阻断修复与 reconcile 死锁移交 BUG-077；剩余实机真实零件全链路与 WorkBuddy 复核，不统一提高限额。 |
| [BUG-057](work-items/BUG-057.md) | P1 | 验收中 | 0.4.6 | 包内统一锁机制（OPEN_EXISTING→CREATE_NEW→一次共享回退）与启动协调lock_error分类已实施，双路径诊断本机三状态60轮全过；剩余双进程200轮与 Win10/Python3.13 原环境重跑。保持忙即拒绝、无重试/排队。 |
| [FEAT-046](work-items/FEAT-046.md) | P1 | 验收中 | 0.4.6 | `creo_erase_session_models` 已实施（native inspect/apply+令牌+幂等+拓扑序+逐项复核消失确认），单元5项+全量502项+构建过；[外部 Creo 10 实机主链路通过](validation/feedback-0.4.6-2026-10-21/manifest.json)（两轮 inspect→apply、会话归零、擦除后打开装配闭环），该子项关闭；剩余本机 Creo 12.4 矩阵、阻断场景及 WorkBuddy 黑盒。 |
| [BUG-036](work-items/BUG-036.md) | P1 | 验收中 | 未排期 | 实际组件到装配变换查询已修复并经本机约束/重载对照；仍缺面位置/法向直接量测与Creo9原失败完整输入。 |
| [FEAT-030](work-items/FEAT-030.md) | P2 | 验收中 | 未排期 | 种子元数据与会话加载观察首批已交付；继续补可追溯生产版本及各环境实际加载证据，available只代表哈希。Creo9兼容加载失败仍由 BUG-034 跟进。**2026-10-25**：种子实机证据取得（`two_straight` job `d161f855…` 体积 5131.268000863329/（4900π/3）、`two_smooth` job `fe8bf5ed…`，均 `seed_load_evidence.status=loaded`、`evidence_persisted=true`、保存重载通过；validate 仍 `not_verified_for_current_session`、`seed_build_version=null`，[收口记录](validation/PHASE3-CLOSEOUT-2026-10-25.md)）。**2026-10-26**：测试驱动修复（受控 ref/summary 读取、manifest 驱动 9+6 场景、20 项离线单测）随反馈计划交付；seeds smoke 两种子经 summary 读取通过；九种子矩阵部分实证（matrix_five_smooth 全过、matrix_four_smooth 创建过并发现 SECTION 平面不驱动 Blend 的种子行为差异，编辑改用 section_1 草图真实尺寸），后因 Toolkit 通道断开（worker exit 20，两次 retry 超时，按 BUG-001 未处置 Creo）环境受阻，剩余 13 场景待会话恢复补跑。剩余：生产版本可追溯生成记录、Creo 9/10 等其他环境加载、矩阵补跑；种子重生成另列环境受阻子项，保持验收中。 |
| [FEAT-042](work-items/FEAT-042.md) | P1 | 验收中 | 未排期 | 剩余接管/同模型并发编辑、真实再生失败、钣金专有语义及prepare字段的WorkBuddy复核。原件关闭后副本续作已验证，通道级busy不能代替接管并发验收。 |
| [BUG-072](work-items/BUG-072.md) | P2 | 验收中 | 未排期 | 非毫米units/体积误标已修复且本机英寸拒绝复验通过；剩余WorkBuddy公开复核，保持毫米准入与原件不变，拒绝格式说明与 FEAT-008 联动。 |
| [FEAT-043](work-items/FEAT-043.md) | P2 | 验收中 | 0.4.6 | 剩余unknown、其他模型类型及真实并发枚举；本轮快照年龄/刷新指引/`service_session_changes`（跨进程有界记录，GUI变化标未实时复核）已实施，省略cursor实时重采/携cursor冻结语义保持；`opened_session_model` 原环境观察子项已[外部实测到位关闭](validation/feedback-0.4.6-2026-10-21/manifest.json)（含 loaded_session_models 9 项回读）；session_model_id 524288+ 大数段保留观察不作身份键；剩余实机与 WorkBuddy 复核。 |
| [FEAT-022](work-items/FEAT-022.md) | P2 | 验收中 | 未排期 | 部署指纹与重启指引已实现；仍需真实连接器升级前后对照，确认路径、启动身份和工具版本一致，不能只看版本号。 |
| [BUG-019](work-items/BUG-019.md) | P2 | 验收中 | 未排期 | 三入口别名、size回显、冲突拒绝与本机尺寸/重载已通过；剩余WorkBuddy终验，其他环境不据本机成功推定。**2026-10-25 小修**：三入口等价请求示例与三步部署核对方法前移至 REFERENCE_SYNTAX.md（只读源码核对，无行为改动，既有 10 项单测复跑通过）；未新增别名，参数名差异反馈仍须先核对真实请求与受测部署。 |
| [FEAT-029](work-items/FEAT-029.md) | P1 | 验收中 | 0.3.4 | 首次注册→启动→ready→直接放样→重启后再放样的本机主线已过；剩余不同代际兼容升级、回退、多目录并存及对应公开验收。自动注册、last_known_readiness和签名仍待评估。 |
| [FEAT-018](work-items/FEAT-018.md) | P1 | 验收中 | 0.3.4 | 补四种恢复动作的revision、600秒凭证/过期、幂等、活动owner、跨文件登记、再次中断及后续编辑与WorkBuddy矩阵；清字段或重启不能代替恢复验收。 |
| BUG-010 | P1 | 验收中 | 未排期 | 旧报告中 drawing_view_update(scale=2) 失败，但 0.3.1 已成功把 v_front 从 1 放大到 2。还要查清两次测试的差异，测试位置更新、图纸保存重载和 revision；失败时应保留原图。  本次只调整为剩余验收，不认定位置更新和保存重载已通过。 |
| [BUG-013](work-items/BUG-013.md) | P1 | 验收中 | 未排期 | 摘要/分页已有成功证据；仍缺模型查询精确32KiB上限及单项超限验收，capabilities分页通过不能代替本项。完整性标志待评估，jobs日志归 FEAT-023。 |
| [BUG-014](work-items/BUG-014.md) | P1 | 验收中 | 未排期 | 查清作业counts=null、后续查询有值的时点与取数差异，补恢复失败路径；未知计数保持null。 |
| [BUG-017](work-items/BUG-017.md) | P1 | 验收中 | 未排期 | 本机筋特征已测范围保留；Creo9材料侧再生失败仍缺完整轮廓、平面、部署与job/model，补输入后定位，不能直接归因该版本不支持。 |
| [BUG-028](work-items/BUG-028.md) | P2 | 验收中 | 未排期 | 补计划入口的整数、数字字符串和混合草图引用最终建模/重载结果；独立工具与标签成功、仅通过输入校验都不能代替。 |
| [FEAT-020](work-items/FEAT-020.md) | P2 | 验收中 | 0.3.0 | 补local_dev与公开版本语义、断网/限流/高版本与重复提示，以及联网失败后可继续建模的验证；current=latest只表示可比较的最高公开版本。**2026-10-25 小修**：失败 message 明确“未取得最新版本信息”（此前无成功检查时 `latest_version=null`；有旧缓存时标注须结合 `status=failed`/`stale`/`error`），`creo_check_update` 描述与 UPDATE_CHECK.md 同步，1 项单测通过；真实断网/限流与失败期间建模仍缺。 |
| [FEAT-023](work-items/FEAT-023.md) | P2 | 验收中 | 0.4.2 | capabilities摘要/分页子项已闭环；剩余jobs日志、组件业务label/源件身份、翼型/履带请求与union错误体量。保持UTF-8预算、身份/矩阵/放置与详情入口，不能代替 BUG-053 计算优化。 |

## 功能与接口改进（待规划）

<a id="未来能力候选"></a>

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| FEAT-001 | P1 | 待规划 | 未排期 | 补齐 Creo 关闭、启动、重连和多会话时的检测，区分首次准备、跨日重连、未就绪和无法确认。连接不可用时，应在规定时间内等待或明确拒绝，不能先把任务收下。自动启动不代表普通 retry 与损坏通道恢复的完整验收；普通 retry 检测归本项，恢复保护按现行恢复契约处理。0.3.2 的 S7 未复测，开始时只看到 checking；0.3.5 钣金回归会话起始同样只见 checking。 |
| FEAT-002 | P2 | 待规划 | 未排期 | 遇到 DLL 提示等需要人工处理的情况时，说明正在等什么。测试等待超时后，任务上下文是否保留、相关模块能否清理。 |
| FEAT-003 | P2 | 待规划 | 未排期 | 支持并测试带单位的关系式，例如 `8[mm]`。确认它能真实驱动尺寸、带动相关参数变化，并保留用户对单位的检查设置。 |
| FEAT-004 | P2 | 待规划 | 未排期 | 尺寸查询应说明尺寸属于哪个特征，是驱动、从属还是参考尺寸，以及能否编辑。关系控制的尺寸应提示改参数或关系；拒绝编辑时 revision 不变，并用自由尺寸做对照。 |
| FEAT-005 | P2 | 待规划 | 未排期 | revision 冲突时，返回 model_id、current_revision 和 expected_revision，让调用者看到哪个版本不一致。继续拒绝过期请求，拒绝时不创建 job。 |
| [FEAT-006](work-items/FEAT-006.md) | P2 | 验收完成 | 0.5.2 | 接管空窗口结构化与预检阶段诊断已随0.4.5交付；收养拒绝有界逐特征诊断（0.5.0反馈计划第一批P1-5）已实现并通过单元/编译/dev_check（2026-10-24 回收核对独立复跑558例通过；整合树561例通过），实机取证与 WorkBuddy 黑盒均通过（unhealthy_features 本码+真实抑制特征明细+会话不变性，NO_CURRENT_MODEL 分支同日闭环，[记录](validation/BUG080-FEAT006-LIVE-2026-10-24.md)）；剩余其他操作的原生失败特征/引用/错误详情、轮廓自交预检方案和union长错误精简，未知原因不得猜测。 |
| FEAT-007 | P2 | 待规划 | 未排期 | 长任务应显示已完成和总操作数、当前操作，以及正在建模、保存、重载、登记、回滚还是等人工处理。已执行的操作可能还没保存；没有可靠进度或结果未知时，不显示编造的完成百分比。曲面反馈另建议 creo_get_job 增加 wait_seconds 长轮询（现单 job 需 4～6 次轮询，长链路耗时翻倍），完成即返回并与 MCP progress 机制配合。 |
| [FEAT-008](work-items/FEAT-008.md) | P2 | 待规划（第二批配套随 0.6.0 候选交付，WorkBuddy 取消未执行） | 未排期 | 2026-10-25 第二批第二阶段配套已交付离线实现：官方装配重建管线示例与说明（docs/ASSEMBLY_REBUILD.md + examples）、source_snapshot 语义与再生成方式、组件变更摘要、list_components 约束符号名、实机驱动与 WorkBuddy 场景文档；开发者实机通过，WorkBuddy 经用户 2026-10-26 决定取消（未执行，不记通过）。继续底板holes真实数组、对称深度与编辑、平面引用/构造三项首批及逐工具引用/矩阵/源件说明。0.4.5摘要用法与拒绝说明已交付，装配只读检查另见 FEAT-045。**2026-10-26 实机收口小修**：管线实机 step 9e 以原 label 复用 remove+re-assemble 被入口拒绝（`Feature labels already exist: ['plate_a']`，无新作业，证据 `build/assembly_pipeline_live_20261025T162553Z`）；驱动/示例/说明改为一个作业内 remove 旧 label+新唯一 label 重插（同 source、原 pose），保留原 label 须拆两个作业各自 revision+1；别名预检离线回归 3 项，见卡与 [development 记录](development/BATCH2-PIPELINE-REPLACE-LABEL-2026-10-26.md)。**同日最终管线 b86 实机重跑通过**（`build/assembly_pipeline_live_20261025T170907Zf5978fb3`，guard `guarded_live_20261025T170905774374` 子 exit 0、settle quiet/released、16 个新发现作业全 success）：10 父作业全成功，快照刷新新唯一 label `plate_a_refreshed`（体积 12384→12984、装配 rev 3→4、removed/added 实际 feature_id），源编辑 +600 后 regenerate+保存重载仍 12384；源只读 hash 不变，见卡与 [实机验收证据](development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md)。 |
| FEAT-009 | P2 | 待规划 | 未排期 | 扩展放样切除、曲面、非平行截面及相切/曲率控制。7～20 截面种子、截面增删和模式转换分别测试，不能用其中一项通过代表全部可用。可乐瓶任务书第 2 步（两 50° 截面放样曲面）直接命中：0.3.5 的 loft 仅 solid/add/XY 平行截面/默认 body，外部只能用 revolve{new_body} 几何等价绕道，见[曲面反馈](validation/feedback-0.3.5-surface-2026-10-18/report.md)；曲面模式与 FEAT-039 的 MVR 第 4 步联动。 |
| FEAT-010 | P2 | 待规划 | 未排期 | 给坐标草图增加明确的驱动尺寸和基础约束，并逐种测试。基础约束可用，不代表任意约束组合都支持。0.3.5/Creo 10 反馈请求解除 coordinates 的主平面限制（倾斜面被拒后只能退 autodim，失去坐标保真度；坐标尺寸本身与平面无关，见[能力边界反馈](validation/FEEDBACK-0.3.5-CAPABILITY-2026-10-18.md) §4.1）。 |
| FEAT-011 | P2 | 待规划 | 未排期 | 增加复合轨迹、可变截面和螺旋扫掠，分别明确范围并测试。 |
| [FEAT-012](work-items/FEAT-012.md) | P2 | 矩阵子项开发者实机通过；WorkBuddy 取消未执行；随 0.6.0 候选交付 | 0.6.0 | 创建/更新公开工具及 execute_plan 支持互斥的嵌套 3×3 rotation_matrix，1e-6 校验且不修正；离线证据见卡；2026-10-26 实机：38 父作业（37 成功+1 故意失败成功回滚）、11 姿态基向量/已知点、非法拒绝、rev 递进、保存重载、约束符号名、体积 330、补充 4 次真实改变位姿 rev 36→40；用户 2026-10-26 取消本批 WorkBuddy（未执行）。第二阶段配套已实现；显式源件更新和嵌套装配继续开放，source_snapshot 不实时联动。 |
| FEAT-013 | P2 | 待规划 | 未排期 | 增加剖视、局部放大、装配图和 BOM（物料清单），逐项检查模型变化后图纸能否同步更新。 |
| FEAT-014 | P2 | 待规划 | 未排期 | 补钣金止裂槽、成形、折边和过渡。已有两道相对折边成功、第 3/4 道垂直折边失败的报告；0.3.2 的 S3 再现第 3 道失败、整体回滚且没有 bend relief（折弯释放）；0.3.5 第四轮仍未修（模型 acc35_sm2，job 45334bda…）：一次挂 4 道 flange（h=80、R2.54、Y=0.5）时前 2 道 ±X 成功、第 3 道 −Y 失败 ProFeatureWithoptionsCreate -1，行为与 0.3.1～0.3.3 完全一致。本轮新发现：厚底板（185×232×232）时连第 1 道折边都失败（Regeneration produced a failed, suppressed or incomplete feature）——折边被折向驱动面一侧、全部落在既有实体内不产生新材料，方向对底板厚度敏感且 flip 不可控（佐证 BUG-047）。评估角部裁剪和释放结构，并说明限制。释放结构缺失是已知能力缺口，但角部干涉是否为失败原因仍待查，不能直接认定四壁箱都建不了。 |
| FEAT-015 | P3 | 待规划 | 未排期 | 评估模具、NC 加工和仿真能力，先选一个最小场景做完整流程，暂不承诺支持全部模块。 |
| FEAT-016 | P2 | 待规划 | 未排期 | 增加翼型凸度和 NACA 四位数系列，检查能否通过原生参数编辑，并验证实际几何。 |
| FEAT-017 | P2 | 待规划 | 未排期 | 分别复现并测试布尔、曲面和拔模中尚未测过的用法，再决定扩大哪些支持范围。 |
| FEAT-021 | P1 | 待规划 | 未排期 | 设计受控取消任务，先说明 queued、running、unknown_outcome 各能否取消，再检查执行器和模型状态。不能安全中断时说明原因。取消后要检查最终状态、保存点、revision、锁和下一次任务是否正常；不能把杀 worker 或清 pending_job 当作取消成功。与未知结果恢复分别验收，任务状态名称不表示当前已有排队能力。 |
| FEAT-024 | P3 | 待规划 | 未排期 | lookup_constants 没找到结果时，说明没有匹配，并提示可用前缀。测试不存在的前缀、空条件、合法前缀及旧返回规则；保留正常命中的行为。当前按体验改进处理，不直接把空字典认定为缺陷。 |
| FEAT-025 | P2 | 待规划 | 未排期 | 评估 creo_loft 在回调未就绪时，能否用 2～6 截面种子完成部分操作。先说明支持哪些截面和模式、怎样保留模型身份，再检查已有特征、编辑、revision、保存重载和失败恢复。种子能新建零件，不代表能追加到已有零件；不自动加载 DLL 或改变策略，也不预先承诺实现成本低。 |
| FEAT-026 | P3 | 待规划 | 未排期 | 提供 create_feature_tree 能运行的最小 dict 示例，说明 dump XML 能否转换或导入。先让示例建模、参数、几何和重载通过，非法树能指出问题元素，再评估导出后重新导入。无效示例失败不能证明工具不可用。 |
| FEAT-027 | P3 | 待规划 | 未排期 | 说明删除实体后是否保留 label，以及何时可以安全释放或重新绑定。测试创建、删除、同名重用和旧引用、历史作业、revision 的关系，防止旧别名误指新对象。先说明现有规则，再评估可选接口，不默认允许覆盖。 |
| FEAT-028 | P3 | 待规划 | 未排期 | create_plate为一次性产物，未注册为可继续编辑的模型；[0.4.7黑盒](validation/WORKBUDDY-0.4.7-2026-10-21.md)再次确认1000mm³成功但无model_id，属既有边界。评估是否返回 one_shot/registered 或支持可选注册。若增加后续编辑，须检查列表和 inspect 能找到模型、revision 正确、编辑和保存重载通过，失败后可恢复。计数问题仍由 BUG-014 处理。 |
| [FEAT-031](work-items/FEAT-031.md) | P2 | 待规划 | 未排期 | 规划装配与引用快照一起交付，明确文件清单、缺失/外部引用、大小和路径隐私；现有导出不变，不预先承诺跨机重建。 |
| [FEAT-032](work-items/FEAT-032.md) | P2 | 待规划 | 未排期 | 评估原生沿曲线阵列：先简单平面，再闭环弧长、相位、切向、种子计数和跳站，最后履带63站与多特征；多次切除不算原生阵列验收。 |
| [FEAT-033](work-items/FEAT-033.md) | P1 | 待规划 | 未排期 | 明确作业时间预算、阶段耗时与来源，核对执行器/看门狗/客户端超时；不套用报告公式，不以取消保存重载缩时，未知结果继续保护。 |
| [FEAT-034](work-items/FEAT-034.md) | P1 | 待规划 | 未排期 | 规划圆弧方向/扫角及实际几何回显，明确跨零、整圆、互斥和旧输入兼容；按报告90°/270°体积差对照验收，合法优弧不能一律拒绝。 |
| [FEAT-035](work-items/FEAT-035.md) | P2 | 待规划 | 未排期 | 核对SDK后规划原生平底沉孔/锥形沉头孔参数组合，验收单个原生孔的参数、去料、编辑与重载，不能以孔加回转切除拼接代替。 |
| [FEAT-036](work-items/FEAT-036.md) | P2 | 待规划 | 未排期 | 规划零件特征删除/抑制/恢复，明确支持范围、依赖级联、身份与label复用、revision和恢复重载；不静默删下游，关联 FEAT-027。 |
| [FEAT-037](work-items/FEAT-037.md) | P3 | 待规划 | 未排期 | 先补参数误写的最小输入，再明确模型/特征参数目标与同名规则，评估少量建议；不自动猜改，验证关系、revision及重载。 |
| FEAT-038 | P2 | 待规划 | 未排期 | 提供不建立 Toolkit 连接的安装自检路径：校验部署产物与配置一致性（常量表、执行器与源码指纹、种子哈希与清单、protk/loader 注册文件），让按约束停止 Toolkit 连接的受限环境也能确认安装正确性，不必冒卡死风险连 Creo。先确定自检覆盖哪些项、怎样判定"一致"，以及自检通过与实机就绪的关系（自检通过不等于通道可用）。来源见[Creo 10 反馈](validation/FEEDBACK-0.3.5-CREO10-2026-10-18.md)，关联 FEAT-022。 |
| [FEAT-039](work-items/FEAT-039.md) | P1 | 待规划 | 未排期 | 规划纯曲面最小闭环：常量核对→修剪→缝合→loft曲面模式，再推进G1边界混合、quilt偏置、面积/最小壁厚；定义引用与返回，使用已有STL回归基准，关联 FEAT-009。 |
| [FEAT-040](work-items/FEAT-040.md) | P2 | 待规划 | 未排期 | 核对SDK后评估变半径表与收尾控制，补真实冲突边/可行半径诊断；恒定半径行为及回滚保持，与 FEAT-039 联动。 |
| [FEAT-041](work-items/FEAT-041.md) | P3 | 待规划 | 未排期 | 评估可选输出目录与预览/导出视角、正交投影；保持默认行为，输出目录不开放任意写路径。 |
| [FEAT-049](work-items/FEAT-049.md) | P1 | 待规划 | 后续MINOR | [0.5.0 反馈第三批](development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)：约束快照回放——补双侧方向/引用身份/可回放诊断，首期限单层与现有六种写入类型；未知类型/缺失映射明确拒绝，不静默退化 fixed 放置。 |
| [FEAT-050](work-items/FEAT-050.md) | P2 | 待规划 | 后续MINOR | [0.5.0 反馈第三批](development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)：装配结果比对——冻结基准（FEAT-045 快照）+显式组件映射，比对组件集/毫米位置/旋转/约束/包围盒体积，缺失数据标未验证。 |
| [FEAT-045](work-items/FEAT-045.md) | P2 | 验收中 | 0.5.0 | [0.4.6 反馈整合计划](development/0.4.6-FEEDBACK-PLAN-2026-10-21.md)第二批：新增 `creo_inspect_session_assembly` 只读检查（树序 occurrence 路径/来源/加载抑制状态/约束欠约束快照、完整 4×4 行向量解算变换含单位与平移末行约定、缺件/抑制/单节点失败逐项标记+原始查询码+整体完整性标志、首采单通道忙拒+分页十分钟冻结快照 32 KiB、五不原则）。[实施与本机实机验收](validation/FEAT045-ASSEMBLY-INSPECT-2026-10-22.md)：托管链+外部装配主线通过（变换与放置平移逐位一致、fix 约束快照、分页、结构化拒绝、会话不变），单测5项+全量544项+dev_check过；[0.5.0 外部报告 §3.1](validation/feedback-0.5.0-2026-10-22/manifest.json) 单层装配复核外部通过关闭；嵌套/重复实例/抑制/缺件四场景实机触发与 WorkBuddy 黑盒按卡开放，单位疑点归 BUG-080。矩阵放置、重建编辑与装配整体收养为后续路线单列。**2026-10-25 小修**：`support_status.assembly_checks` 由 planned/not available 改为 `supported_limited` 并指向已发布的 `creo_inspect_session_assembly`，写明只读范围、四类受限场景与无写路径，3 项单测锁定不回退；仅文案/状态字段，未重复实机，四场景与 WorkBuddy 仍开放。 |

## 工程整理（待规划）

结构迁移见[架构计划](development/ARCHITECTURE.md)；每批独立核对安装、资源/数据位置和受影响回归。

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| BUG-020 | P2 | 待规划 | 未排期 | STEP 导出会留下 *_out.log.N。需要说明哪些文件是交付产物、哪些是诊断附件，只清理本作业生成的副产物。检查 STEP 仍有效、用户文件未受影响。文件清理由开发者检查，MCP 黑盒只验证返回的文件说明。 |
| [DEV-031](work-items/DEV-031.md) | P2 | 待规划 | 未排期 | 先澄清履带TXT的相位、闭合、近似与容差，再分步安排63站/90凸台、性能和恢复；报告−1.46%偏差仍未满足±1%，本条不直接建模。 |
| DEV-003 | P2 | 待规划 | 未排期 | 整理 C++ 的执行上下文、模块接口和资源由谁创建、释放，再用受影响的 SDK 构建并运行原生测试。 |
| DEV-004 | P2 | 待规划 | 未排期 | 在 DEV-003 完成后，让各模块可以独立编译，并整理原生测试目录。检查构建缓存、安装、保存重载和失败回滚。 |
| DEV-005 | P2 | 待规划 | 未排期 | 按工具和参数用法记录本机哪些测过、哪些没测，并注明真实环境，同步安装和能力说明。其他环境收到具体反馈再补；不要求双版本验收，也不能拿“82 工具测过”的汇总代替每种用法的兼容性测试。 |
| DEV-006 | P2 | 待规划 | 未排期 | 补测会话、中断、真正并发、倾斜草图、两截面和 Creo 12 直接混合。0.3.1 还缺回调就绪的 loft、有效 UDF 和元素树、种子 directory/archive、JPEG 和图纸 PDF 的成功用例。记录完整输入、ID、几何、编辑、重载和回滚。Creo 9 的种子、筋和放样冒烟测试要有实际环境再做；新工具还须经真实 stdio MCP 测试空值、省略、非法字段、错误传递及 inspect→apply。模拟协议、原生和 WorkBuddy 结果分别记录，不能用输入被拒绝或工具总数代替成功用例，也不新增双版本发布门槛。 |
| DEV-007 | P2 | 待规划 | 未排期 | 与 DEV-006 共用一份回归清单，在发布候选上执行，避免维护两套记录。包括 0.3.3 提出的 Creo 9 最小冒烟，以及新工具的空值、省略和非法字段 MCP 调用检查，逐环境标明已测、未测。外部编译通过或一个孔成功，不能代表全部运行时可用；本地 Python 直调也不能代替 MCP 协议测试。 |
| DEV-008 | P3 | 待规划 | 未排期 | 查清旧清单第 5/6/7/9 项分别来自哪里、现在归哪个任务，补上对照关系。来源是 NEXT_STEPS_025 的“完善建议 5”。 |
| DEV-009 | P2 | 待规划 | 未排期 | 按模块分别整理代码格式，每批完成后做回归检查，不自动增加历史问题的豁免项。2026-10-14 的历史统计为 67 条 Ruff 问题、36 个 Python 和 14 个 C++ 文件，见[历史记录](BACKLOG_COMPLETED.md)。 |

## 历史观察

收到同类新失败及完整证据后再转回调查，不登记为已修复。

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| [BUG-021](work-items/BUG-021.md) | P1 | 观察中 | 未排期 | 原尺寸编辑失败未在本机复现，原因未确认；收到同类新失败及完整输入/运行身份/原始错误后转调查，暂不安排独立复测或阻断发布。 |
| [BUG-005](work-items/BUG-005.md) | P1 | 观察中 | 未排期 | 不同客户端Toolkit连接差异仍未定因，本机超时与其他客户端通过分开保留；有同类新失败及完整输入/运行身份/原始错误后转调查，暂不主动独立复测。 |

## 历史资料

<a id="workbuddy-030-全量实测问题映射"></a>

完成事项、[历史来源索引](BACKLOG_COMPLETED.md#历史来源索引)和[历史进展补录](BACKLOG_COMPLETED.md#历史进展与反馈补录)集中在[完成档案](BACKLOG_COMPLETED.md)。原始报告和历史进度资料保留其日期，不作为当前排期。
