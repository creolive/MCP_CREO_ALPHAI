# FEAT-042：显式接管用户已打开模型的受控入口

日期：2026-10-18。类型：功能。优先级：P1。状态：验收中（第二阶段；0.4.0首阶段已交付）。目标版本：未排期。

## 当前状态（2026-10-21）

第二阶段无盘快照接管已随0.4.1交付，当前仍有剩余验收。[接管黑盒补录](../validation/ADOPTION-WorkBuddy-2026-10-19.md)保存主链、冻结/续签、放弃及来源保护的已测范围；0.4.5预算诊断首批不代表预算阻断已修复，另由BUG-076跟进。

2026-10-20 已补关闭原件后副本续作：来源wb_unsaved_03经打开/inspect/apply接管为wb_close_orig，6000mm³/revision1/重载verified；操作者擦除原件后只剩副本，加10×10×5凸台后6000→6500mm³、revision1→2、重载verified，原件文件SHA256不变。同日通道级真实并发验证A运行时B立即busy并携blocking_job_id/operation，A保存重载通过、无排队或自动重试；这不能替代接管/同模型并发编辑验收。见[实施记录](../validation/FEEDBACK-0.3.7-IMPLEMENTATION-2026-10-20.md)。

仍需接管/同模型并发编辑、真实再生失败、钣金专有语义及prepare字段的WorkBuddy复核。prepare full/compact的adopted=false、apply对照true已在连接器重启后完成开发者实机复验；早期extrude引用边角后由BUG-073独立修复验收，不继续作为本卡待登记项。下列章节保留各时点事实，旧“未合入/未发布/关闭原件未测”不代表当前状态。

## 第二阶段实施与早期验收记录（2026-10-18～19）

用户确认完整续作流程，沿用受管副本；新增显式 prepare，在一次原生事务中复制从未保存的当前模型、保存重载核验，原模型不保存/改名/擦除，准备时不切窗口。prepare 需幂等键，返回独立job/model；准备后revision=0、adopt_pending。apply 确认已冻结快照后ready/revision=1，后续原模型变化不进入快照。十分钟令牌过期可 inspect(model_id=...) 续签，不重复制；abandon_new 放弃并保留文件。普通建模与其他恢复接纳不得绕过确认。

保留有文件模型inspect/apply；非空来源缺失/不可读不得降级。补 adopted/来源摘要，关联 BUG-071 预检收尾、FEAT-043 会话发现、FEAT-022 重启指引。

验收：从未保存001长方体40×30×20→prepare/apply→去顶面壁厚2的shell，体积7152±0.01、revision0→1→2及保存重载；另测外部文件clean/dirty、钣金、冻结语义、篡改拒绝、续签、幂等/并发/未知结果与WorkBuddy。开发与黑盒证据分别记录；会话限制保留。下方为首阶段历史，不据其成功外推新范围。

第二阶段实现已完成，原生prepare复制→源/副本完整核验→保存/重载，确认仅加载受管快照；Python实现幂等任务、提交决策后轮询补登记、过期续签、摘要来源及仅abandon恢复边界。403项全量单元及统一开发检查、匹配SDK构建通过。2026-10-18开发脚本首次9秒就绪探测timeout、cases为空的[历史证据](../validation/ADOPTION-COMPLETION-2026-10-18.md)保持原样。2026-10-19用户转贴WorkBuddy报告支持无盘续作主链、24000→7152体积、revision0→1→2、保存重载、原件/窗口保护、未确认保护与幂等重放；后续过期拒绝、同身份续签确认、原件改到35×40×10/14000后副本仍20000 mm³/同哈希，以及独立约6000 mm³来源prepare→abandon_new→abandoned/revision0→普通编辑拒绝与原件保留亦有通过报告，见[黑盒补录](../validation/ADOPTION-WorkBuddy-2026-10-19.md)。外部clean接管亦通过（model d573a11f766c4679aae4e46858b8e803，约6000 mm³、ready/revision1、保存重载verified、原件保留与adopted_copy_model_id关联）。独立平板钣金接管通过（model ec76df179b254f688c79acf85f858d91、2400 mm³、ready/revision1、保存重载与原件关联）；sheets实际为工程图图纸页，不据其不可用认定钣金缺陷，钣金特征名称映射及专有语义仍未验证。clean/钣金接管后源文件SHA256与准备时一致另以开发者只读文件证据补录，不归入WorkBuddy公开接口结论。dirty接管亦通过（model 6343b3f7640746f4b2c1bfa209bd8a63、约6750 mm³、35×20×10尺寸、5×5贯穿方孔与参数WB_DIRTY_CHECK=42.0逐项核对、ready/revision1及保存重载）；源磁盘重载几何和WorkBuddy接管后源哈希仍未验证。装配、非毫米、外部依赖及含抑制特征拒绝、会话真实五页遍历通过；非毫米载荷单位/体积误标已在BUG-072修正（P2验收中）；关闭原件、真实再生失败与真实并发仍未验收。prepare顶层result.adopted=false已修正，原生与Python提交均区分prepare/apply，历史任务不改写；406项单元与统一检查、8例隔离C++及匹配SDK构建通过，待连接器重启后的实机及公开复验；续签current_model沿用准备时摘要、无model_id检查当前来源的区别已补文档。放弃时显式null变空串被拒、省略参数成功的现象映射既有BUG-055，提示词已补说明，不放宽空串保护。本卡保持验收中，未合入main或发布。

来源：[0.3.7 / Creo 13 反馈补录](../validation/FEEDBACK-0.3.7-CREO13-2026-10-18.md)第 2 项；[原件](../validation/feedback-0.3.7-creo13-2026-10-18/report.md)问题 2。关联 [FEAT-018](FEAT-018.md)（受管模型恢复）、[FEAT-019](FEAT-019.md)（自动启动边界，不接管未保存模型）、[BUG-070](BUG-070.md)（模型名称可信性）、[BUG-069](BUG-069.md)（名称与身份）。

2026-10-19晚连接器重启后（部署指纹与补录一致）完成prepare/apply字段实机复验：无盘WB_FIELDS_UNSAVED（40×30草绘特征已由GUI精确改尺）inspect提示prepare；prepare（job `4e68bcfc…`）返回full/compact顶层`result.adopted=false`、`adopt_pending`/revision0、快照保存重载verified（sha256 `7771effd…`）、证据令牌600秒；apply（job `422d8abe…`）`adoption_committed`/revision1/`adopted=true`且快照哈希不变；副本续作40×30×20拉伸revision1→2、24000 mm³、保存重载verified；原件保持无盘/modified/未改名/窗口在。同轮完成BUG-072英寸实机复验与一次-11连接事故的恢复记录（Creo停在拉伸Dashboard模态叠加警告框循环，ESC取消后恢复，未结束Creo/未清unknown，不改BUG-001结论）。边角观察：extrude以整数特征ID引用快照草图被按标签查找拒绝（回滚成功），与loft数字串规范化不一致，待评估登记。详见[接管补录](../validation/ADOPTION-WorkBuddy-2026-10-19.md)同日晚间各节。WorkBuddy公开复验与既有未测边界保持，未合入main或发布。

## 问题与目标

用户希望在 Creo 手动打开的 `001.prt` 中继续建模。报告称会话查询可看到当前模型，但建模接口要求已登记 model_id，`creo_reconcile_model` 返回 `Unsupported/unproven ownership`。这是已声明的所有权边界，不能按恢复缺陷处理或通过放宽该拒绝直接接管。

目标是在操作者明确选择模型后，为符合范围的已有模型建立可验证的受管基线，使后续 inspect、编辑、revision、保存重载和失败恢复能使用现有机制。`creo_adopt_current_model`、`ProMdlCurrentGet` 与“一次快照登记”为反馈中的候选接口/实现，尚未选型，当前不存在本卡承诺的新工具。

## 方案范围与待决策

1. **选择与预检。** 明确当前模型的可靠身份、类型、来源路径、修改/保存状态、单位、外部依赖及是否已登记；名称仅用于展示，不能独立证明身份。防止预检后用户切换模型、另存、关闭或修改导致接管错误对象。
2. **首批支持范围。** 优先评估独立 part；是否包含 sheetmetal、未保存新件或有手工未保存修改的模型分别决策。assembly/drawing、外部依赖、同名异路径模型和已受其他登记保护的对象，不预先承诺支持；无法证明条件时给明确拒绝。
3. **原件与受管副本。** 选择原模型就地管理还是建立受管副本，并明确用户将编辑哪个对象、保存位置和原始文件影响。不能默认覆盖原件、丢弃未保存修改或擦除用户模型；必须先形成具体可审查的流程与身份/文件契约。
4. **基线与登记。** 原生模型健康/几何核验、快照、哈希、初始 revision、路径映射及原生对象/特征 ID 在保存重载后的对应关系要有验证。任一步失败不能留下半登记；重复接管应返回同一受管身份或明确冲突，不产生多套所有者。
5. **后续编辑与恢复。** 接管后取得真实模型与特征引用；人工再修改时准确提示刷新/冲突。复用 FEAT-018 的适用机制前先证明新来源模型已建立足够归属证据，不能自动清除 existing pending/unknown/recovery 保护。
6. **通道与协议。** 新工具如被采用，登记到 capabilities 并同步 schema、文档及安装/能力说明。使用既有单一通道；busy 立即拒绝、不排队、不自动重试，受理后只轮询 job。明确预检/应用边界、预检失效条件和重放行为。

本卡不扩展任意文件导入、装配依赖管理、自动接管所有会话模型、故障自愈或通用恢复权限。接管流程中操作者的模型选择属于产品设计要求；本次仅建卡，不要求用户批准实施方案。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| 方案完成 | 写出支持矩阵、身份与原件/副本契约、状态转换及失败收尾 | 接口与影响可审查；未保存修改、同名异路径、重复登记和不支持类型有确定行为 |
| Windows / Python | 实现后 `tools/dev_check.py`，针对性登记/保护/协议回归 | 无新增诊断；预检过期、错误对象、重复请求、快照失败和原有保护均正确处理 |
| 本机 Creo 12.4 / 匹配 SDK | 按最终方案手动打开独立零件→显式接管→inspect→编辑已有特征/追加特征→保存重载 | 模型身份及特征引用正确；基线和 revision 可追溯，编辑几何/参数正确、`saved_file_reloaded_and_verified=true`，原件影响严格符合所选契约 |
| 失败与冲突 | 预检后切换/修改模型、非法类型、重复接管、创建基线失败、编辑失败 | 不误接管或覆盖；原始用户成果保留，登记原子收尾；合法编辑失败恢复基线、revision 符合终态，无自动解保护 |
| 并发与人工修改 | 实际并行调用准入；接管后人工改模再请求编辑 | busy 返回 blocking 字段且未排队；人工偏离被识别并按明确流程处理。未实际并行时标并发未验证 |
| WorkBuddy | 仅通过公开 MCP 接口执行上述用户流程 | 记录模型选择、完整输入、job_id/model_id、终态、几何、revision、回滚和重载；接口未暴露的快照/原子性内部细节不推测通过 |

开发者与 WorkBuddy 证据分开。按本机实际环境验收，不新增 Creo 10 独立复测或全项目多版本门槛；外部报告环境若未测如实保留。本机连接/故障注入限制继续有效，先满足根因核对与会话可操作条件，再安排实际接管试验。

## 实现与证据

2026-10-18 仅登记需求，未选择或新增接口，未接管、保存或修改任何 Creo 模型。后续证据记录方案决策、实际版本、提交/dirty、源码指纹、SDK/运行环境、命令、原件保护结果和未测范围。

## 2026-10-18：受管副本方案实现（creo_adopt_current_model）

方案决策（用户当日确认）：**受管副本**——`ProMdlnameCopy` 复制当前会话模型为受管对象，保存到新 `models/<id>/output/` 并按既有保存闭环验证；用户磁盘原件与会话中原模型不修改、不擦除、不改名。首批类型 **独立 part + sheetmetal**（mm 主单位、无外部依赖、无不健康特征），assembly/drawing/非 mm/带依赖明确拒绝。身份依据 origin 路径 + 磁盘 sha256 + live inspection 全量比对 + 会话指纹，显示名仅尽力展示（不因 [BUG-070](BUG-070.md) 乱码阻塞）。

实现：`native/generic.cpp` 新增 `adopt_native`（inspect/apply 两 action；apply 复核会话指纹/origin/类型/live 快照后 `ProMdlnameCopy` → `ProMdlnameBackup` → erase/load/regenerate → `verify_recovery`，`recovery_dependency_free` 参数化为 `dependency_free(ProMdl)`）；`src/creo_mechdog/adoption.py`（inspect 建 adopt_pending 登记 + evidence token，apply 幂等提交 kind=adoption job，失败按 unknown_outcome 保护并用 reconcile abandon_new 收尾；同源重复接管在 inspect/apply 双层拒绝并指向已有 model_id）；`bridge.py` run_job/get_job 分发；`server.py` 注册 `creo_adopt_current_model`（85 个工具）；`capabilities.py` model_adoption family。未放宽任何既有保护（origin 前缀、checkpointless 拒绝、依赖/单位检查原样保留）。

验证：单测 `tests/unit/test_adoption.py` 9 用例（MCP stdio 协议 + 业务规则补丁模式）；全量 375 单测过（三处工具数断言 84→85 同步）；`tools/dev_check.py` 通过（指纹 70114af0…）；本机 Creo 12.4.0.0/SDK/许可实机 `tools/test_adoption.py --current` 全链路（详见 [验证记录](../validation/FEAT-042-adoption-2026-10-18.md)）：inspect 身份/哈希正确、apply 复制 8 特征体积 4523.893421169301 逐位一致、原件 sha256 前后不变、接管后 execute_plan 编辑凸台保存重载 verified、同源重复接管冲突拒绝。

状态更新：待规划 → 已完成（本机）；未测范围与外部环境见验证记录。
