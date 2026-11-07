# 开发台账完成事项归档

归档建立：2026-10-15；最近追加：2026-11-04；2026-10-28 登记：[DEV-049](work-items/DEV-049.md) 随 0.7.2 完成交付（0.6.1 两份反馈后续 PATCH，T00—T08；标签 `v0.7.2`，四附件，见[发布验收记录](validation/RELEASE-0.7.2.md)），按台账规则由主台账移入本档案，未测范围原样保留。2026-10-28 登记：[DEV-048](work-items/DEV-048.md) 随 0.7.1 完成交付（0.6.0 四份反馈，T00—T05；main `ffa0a43`，附注标签 `v0.7.1`，四附件），按台账规则由主台账移入本档案，未测范围原样保留。2026-10-27 登记：DEV-047 随 0.7.0 完成交付（0.5.2 三份反馈完整交付，T00—T13；main `2a78358`，附注标签 `v0.7.0`，四附件与 Release 核对一致），按台账规则由主台账移入本档案。2026-10-26 登记：0.6.0 第二批交付（第二批可靠装配重建管线，FEAT-012/BUG-045 矩阵子项、FEAT-048 按路径/批量收养、FEAT-008 第二批配套，开发者实机已通过，WorkBuddy 黑盒经用户决定取消、未执行不记通过）。本轮各卡均有剩余开放范围（FEAT-012 源件更新/嵌套、FEAT-008 首批三项、FEAT-048 准入分支泛化、DEV-046 第三批），无整卡完成，不移动任何行；本批交付状态见[主台账](BACKLOG.md)与 [RELEASE_NOTES_0.6.0.md](RELEASE_NOTES_0.6.0.md)。当前排期与状态统一查看[主台账](BACKLOG.md)；本文件保留完成摘要、证据与历史来源，不承担当前排期。后续完成事项追加到本文件，主台账移除对应行。

## 已完成事项

以下保留原验收范围与目标版本，不因当前源码已到 0.7.1 而改写历史受测身份。2026-10-15 用户取消全项目 Creo 10 独立验收门槛，历史交接/复测安排不再作为当前要求；朋友反馈具体问题后再跟进。BUG-022 按已有本机证据完成并归档；DEV-015 的历史主干集成已核实，公开交付由 DEV-025 / v0.3.2 累计承接。BUG-038/042/043/044 于 2026-10-16 按用户决定采信 0.3.2 外部报告转已完成，均标注"本仓库无对应提交可核实、本机复现失败须重开"，不代表本机复验通过。

| ID | 优先级 | 状态 | 目标版本 | 完成摘要与证据 |
| --- | --- | --- | --- | --- |
| [DEV-068](work-items/DEV-068.md) | P3 | 已完成（交付核对见 PR） | 0.12.1 | 用户 README 改版单独合入，校正版本/97 工具与示例；补 离线测试隔离准备。业务/原生实现与种子 PRT 字节不变；本轮未连接 Toolkit。检查及远端四附件核对见 [PR #12](https://github.com/wudahua/MCP_CREO_MechDog/pull/12)、[发布记录](validation/RELEASE-0.12.1.md)。 |
| [DEV-049](work-items/DEV-049.md) | P1 | 已完成（已随 0.7.2 交付并发布） | 0.7.2 | 2026-10-28：0.6.1 两份反馈后续 PATCH（T00—T08）随 0.7.2 交付：T00 原件逐字节归档与 32 章节映射；T01 断连事故离线核对结论为证据不足、根因未定（BUG-085，13 正例 + 2 负例编辑闭环缺口保留）；T02 `dev_check --unit-timeout-seconds` 默认 900 秒（DEV-050）；T03 PS5.1 安装 stderr 误报修复与 T08 批内补充 `Invoke-ExternalStep` 统一 8 处外部调用（BUG-086）；T04 原斜槽六例经 BUG-087 修复后实机 6/6（autodim run `20261028T102858_b2d5e5c9`、coordinates run `20261028T104324_57f20a2d`）与 Right 面 ±Z 回归无退化；T05 多环/预览查缺与替代夹具离线就绪（差项实机未跑，原输入缺失）；T06 种子 15+2 实机全部通过（FEAT-030 转已验收未收口）；T07 文档收口；T08 集成与发布（main 合并、附注标签 `v0.7.2`、Release 四附件，逐件下载哈希核对）。全量 `dev_check --work-item DEV-049` 1128 项单元通过、无 timed_out；新目录 `setup.ps1` 以 `2> err.log` 重定向形式安装验证通过（exit 0、九种子 SHA256 与清单一致、原生执行器编译成功）；公开工具保持 94。GAP-1/GAP-2（0.7.1 后主干回填 `d2e37b0` 差异）由本版覆盖。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、BUG-085 根因未定、BUG-066 待复现、Creo 9 实机编译与建模未验收、未做新 Toolkit 连接与故障注入。见[发布验收记录](validation/RELEASE-0.7.2.md)与[版本说明](RELEASE_NOTES_0.7.2.md)。 |
| [DEV-047](work-items/DEV-047.md) | P1 | 已完成（已随 0.7.0 交付并发布） | 0.7.0 | 2026-10-27：0.5.2 三份外部反馈完整交付（T00—T13）。main 合并提交 `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d`，附注标签 `v0.7.0` peeled 指向同一提交；[GitHub Release v0.7.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0)（424956318，非草稿、非 prerelease）四附件与正文 SHA256 一致。本机 966 项单元测试、dev_check、SDK 构建、Creo 12.4 实机矩阵（T05 毫米 18/18+英寸、T06—T09、T12、装配专项 38 作业、T07 图像目视）及全新目录 setup.ps1 安装冒烟通过；公开工具 92→94。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、unknown 单位仅离线覆盖、BUG-078 三现场未 apply、BUG-066 原始失真未复现、FEAT-050/嵌套回放/新约束类型/世代二进制可复现性等父卡范围保留。历史阶段记录与未测项保持原日期，见[发布验收记录](validation/RELEASE-0.7.0.md)与[版本说明](RELEASE_NOTES_0.7.0.md)。 |
| [DEV-048](work-items/DEV-048.md) | P1 | 已完成（已随 0.7.1 交付并发布） | 0.7.1 | 2026-10-28：0.6.0 四份反馈批次（T00—T05）随 0.7.1 交付。main 提交 `ffa0a433736917812d1040dba7c6d7190b5f82f6`，附注标签 `v0.7.1` peeled 指向同一提交；[GitHub Release v0.7.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.1)（非草稿、非 prerelease，四附件；源码包 5 365 479 B、种子包 493 394 B，与[发布记录](validation/RELEASE-0.7.1.md)核对表一致）。T01 收养侧车完整性与原子发布、T02 拒绝后引用生命周期、T03 工作卡与发布检查回填、T04 Right 面 ±Z 定向实机（实际帧、800 mm³、八点 AABB 与重心、保存重载 true、平行法向原生拒绝并回滚）、T05 集成与 PATCH 发布；公开工具保持 94，本机 1017 项单元测试。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、T04 只覆盖 Right 面 ±Z（`native_acceptance=partial`，未重跑 DEV-047 完整矩阵）、倾斜面/多轮廓/纯 Z u_axis 历史现象不在本版范围、未做真实 worker 超时与文件锁注入。工作卡历史与未测项保持原日期，见[发布验收记录](validation/RELEASE-0.7.1.md)与[版本说明](RELEASE_NOTES_0.7.1.md)。 |
| [DEV-045](work-items/DEV-045.md) | P2 | 已完成（外部确认关闭） | 未排期 | 2026-10-23：RELEASING 第 7 项"Release body 必含两包文件名与完整 SHA256 并核对远端"已两次实际执行通过（[0.4.7](validation/RELEASE-0.4.7.md) 首次、[0.5.1](validation/RELEASE-0.5.1.md)）；[0.5.0 外部报告三 §4](validation/feedback-0.5.0-2026-10-22/manifest.json)确认两包命名自 0.4.7 起按 `MCP_CREO_MechDog-{version}-source.zip`/`-seed-library.zip` 定名执行、Release body 附两包完整 SHA256 与 `.sha256` 附件且远端下载复核一致（源码包 `dd8b49bb…`/种子包 `fb84a37d…`）。按报告关闭移入本档案，工作卡历史保留。 |
| [DEV-041](work-items/DEV-041.md) | P1 | 已完成（Release 发布与附件核对通过） | 0.3.6 | 2026-10-18：PR #11 合并 `ca105b9`、指纹链提交 `1f38069`（种子清单版本与 seeds.py 指纹同步），`v0.3.6` 标签指向该提交；[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.6)（Pre-release）附源码包（588 文件，SHA256 `6cf1d925…`）与种子包（9 种子，`829474ed…`），远端下载核对一致，核对回填 [PR #11](https://github.com/wudahua/MCP_CREO_MechDog/pull/11#issuecomment-6245231613)。范围：DEV-040 的 BUG-059 修复、BUG-057 随版诊断脚本、六份 0.3.5 反馈补录与台账重构；无 C++ 改动故无原生回归。验收：dev_check 356/356、隔离黑盒三场景、复核 12/12；未测范围见[版本记录](validation/RELEASE-0.3.6.md)。 |
| [DEV-040](work-items/DEV-040.md) | P1 | 已完成（本机诊断与 Python/MCP 修复阶段） | 未排期 | 2026-10-18：BUG-057 本机未复现，交付纯文件竞争/错误分类诊断，原环境根因保留；BUG-059 修复原生前自身占位悬挂并澄清原生后 unknown 阶段；BUG-058 仅静态核对。完整开发检查 356/356，WorkBuddy 隔离 A/B/C 补齐拒绝、保护、幂等与 compact/full，标准 stdio 复核 12/12。按用户收尾要求归档已交付阶段，G2 原环境机制与 G3 锁修复未完成仍归 BUG-057；真实 Creo 恢复、几何与并发未测（该阶段收尾时未合入/发布，修复已随 0.3.6/DEV-041 交付）。见[复核](validation/DEV-040-closeout-review-2026-10-18.md)与[隔离报告](validation/DEV-040-isolated-contract-2026-10-18.md)。 |
| [BUG-059](work-items/BUG-059.md) | P1 | 已修复（Python/MCP 隔离契约验收） | 未排期 | 原生派发前拒绝为 failed/reconciliation_refused，附 reason/failure_phase，锁内仅释放自身 recovery_pending；原生连接后指纹拒绝保留 unknown 与保护。WorkBuddy A 验证实际 Python 拒绝、占位释放与状态不变，B/C 明确合成边界，幂等与 compact/full 一致；标准 stdio 12/12。真实会话切换/中断与原生恢复未测，FEAT-018 继续验收；未合入/发布。见[收尾记录](validation/DEV-040-closeout-review-2026-10-18.md)。 |
| [DEV-039](work-items/DEV-039.md) | P2 | 已完成 | 未排期 | 2026-10-18 重读最新台账，将原 37 项待核实分为 20 待复现、10 规则核对、2 待开发、2 工程规划、1 剩余验收、2 历史观察。全部 87 个 ID、原优先级、目标版本和范围保留；同步 19 份既有任务卡、补 BUG-019 卡并更新模板和开发入口。最新反馈、兼容矩阵及原有未提交修改保留，文档一致性检查通过；没有把分类当作修复或新增测试。 |
| [DEV-036](work-items/DEV-036.md) | P1 | 已完成 | 未排期 | BUG-056 执行卡，四轮闭环（未合入 main/未发布，开发基线 0.3.5）：①定位跨批次遗留 nmsd 会话信息失效（trail 证明失败请求未达 Creo），「40 秒周期」为轮询伪影，服务侧无缺陷，`creo_session_status` 增只读 `creo_process_snapshot`（7 例单测+dev_check）；②用户处置环境后 38 次探测跨 7.5 分钟+建模闭环无掉线（T03～T05）；③T08 M2 经 live 取证 abandon_new 收尾（跨会话指纹保护一次正确拒绝后成功，幂等/审计保留）；④WorkBuddy 黑盒全部通过（新字段、3 次间隔稳定、MCP 建模 rev 0→2、T07 空值协议含字面 "null" 完整终态补齐 BUG-055 遗留、M2 终态确认），开发者核对 9/9。证据见[核实记录](validation/BUG-056-DEV-036-investigation-2026-10-17.md)、[WorkBuddy 验收](validation/DEV-036-WorkBuddy-acceptance-2026-10-17.md)及[提示词](validation/DEV-036-WorkBuddy-test.md)。遗留观察：未知参数键静默忽略未立卡；`creo_process_snapshot` 失败场景黑盒表现待自然出现。 |
| [BUG-056](work-items/BUG-056.md) | P1 | 已完成（用户确认关闭） | 未排期 | Toolkit 通道验证通过后约 37～41 秒静默失效（-4/exit 20），Creo 存活、用户确认非人为。2026-10-17 DEV-036 两轮核实：定位为跨批次遗留 nmsd（名字服务）会话信息失效——失败请求未到达 Creo（trail 无 IPC 初始化记录），「40 秒周期」为客户端轮询+快照 30 秒 stale 期伪影，服务侧探测/快照/分类无缺陷；`creo_session_status` 增只读进程快照（服务重启后生效）。清理遗留 nmsd 并重启 Creo 后，38 次探测跨约 7.5 分钟+空闲对照与建模闭环（rev 0→2、保存重载、体积精确一致）全部通过。nmsd 内部触发器为黑盒残余假设；T07/T08、WorkBuddy 黑盒由 DEV-036 跟踪。证据见[核实记录](validation/BUG-056-DEV-036-investigation-2026-10-17.md)。 |
| [DEV-038](work-items/DEV-038.md) | P2 | 已完成 | 未排期 | 2026-10-17 按 humanizer-zh 改写主台账的 85 项任务说明，解释常见术语，保留任务编号、优先级、目标版本和证据链接。同步另一次 DEV-036 调查的最新进度，未自行关闭任务。任务、表格、链接和其他文件摘要检查通过；本次只改文字，未执行建模或发布。 |
| [DEV-037](work-items/DEV-037.md) | P2 | 已完成 | 未排期 | 2026-10-17 核对较早完成事项均已归档，迁入旧进展与 10 段反馈补录并折叠显示，主台账从 56,381 缩至 34,736 字节（减少 38.4%）。原有 85 项未完成行、39 项完成行及其状态/验收边界保持；ID、链接/入站锚点、表格、历史原件/上一轮修改摘要和 diff 检查通过。仅文档整理，未连接 Toolkit、未升版或发布。 |
| [DEV-035](work-items/DEV-035.md) | P1 | 已完成（发布候选） | 0.3.5 | 用户指定统一交付DEV-033/BUG-054、DEV-034/BUG-055及反馈/BUG-056登记；两目录各307项单元/增量检查、84工具、SDK实际编译/6521常量、12项ABI、独立安装和9种子ZIP通过。已知通道问题和M2未取得范围保留；实际main/Release/四附件SHA256在[PR #10](https://github.com/wudahua/MCP_CREO_MechDog/pull/10)回填，见[验收](validation/RELEASE-0.3.5.md)。 |
| [BUG-054](work-items/BUG-054.md) | P1 | 已完成（本机实机及WorkBuddy已测范围） | 0.3.5 | 拉伸/旋转切除零去料曾静默成功。2026-10-17 在 0.3.4 复现并按 DEV-033 修复：cut 前后测体积，零去料抛错回滚（revision 不变、别名无残留），成功返回 material_removed_mm3；T01～T08 实机与 WorkBuddy 5 场景黑盒均通过，revolve 正反例纳入。外部 Creo 10/9、thin/装配/钣金 cut 未测；BUG-016 不随本项关闭。证据见[验收记录](validation/BUG-054-cut-material-2026-10-17.md)与[黑盒记录](validation/BUG-054-WorkBuddy-acceptance-2026-10-17.md)。 |
| [BUG-055](work-items/BUG-055.md) | P1 | 已完成（WorkBuddy核心范围，M2未完成） | 0.3.5 | 根因链闭环：WorkBuddy 实测客户端把显式 null 降级为空串（服务端回显 received ''），服务端各层无转换；修复后空串精确拒绝、省略字段替代路径端到端成功。M1 abandoned 闭环+幂等+历史保留全过；M2 终态与稳定通道字面 null 对照因通道静默掉线未取得（保护按契约保留），外部 Creo 9 未复测。2026-10-17 补录：BUG-056 关闭后 M2 已按用户确认经 live 取证 abandon_new 收尾（abandoned/rev 0/保护清除），字面 null 稳定通道对照仍归 DEV-036 T07。 |
| [DEV-033](work-items/DEV-033.md) | P1 | 已完成（本机实机及WorkBuddy已测范围） | 0.3.5 | 2026-10-17 按 G0～G5 执行 BUG-054：会话条件核对后复现、确定孔类一致契约、最小修复（native 守卫+docstring+compact 白名单+4 项单元回归）、实机 T01～T08 与 WorkBuddy 5 场景黑盒全通过（revolve 正反例纳入），台账/能力说明同步。未测边界（外部 Creo 10/9、thin/装配/钣金 cut）保留；未合入 main、未发布。 |
| [DEV-034](work-items/DEV-034.md) | P1 | 已完成（WorkBuddy核心范围，M2未完成） | 0.3.5 | G0～G4 完成后 WorkBuddy 核心验收通过（客户端 null→空串降级实证、M1 闭环、空串精确拒绝、字面 null 接受、unknown 保护保留），开发者只读核对一致。未取得：M2 终态与稳定通道对照（通道 37–41 秒静默掉线三次，环境异常，是否另立条目待用户定）、外部 Creo 9。事实边界：同名残留模型触发 abandon owned 保护、journal 临时名过深数据根逼近 260 路径上限。不升版、不合入、不发布。 |
| [DEV-032](work-items/DEV-032.md) | P1 | 已完成（发布候选） | 0.3.4 | 用户指定版本并要求汇总七个待合分支；BUG-001按用户决定关闭，FEAT-018/029仍验收中。两目录各297项单元/增量语言、独立SDK编译、12项ABI、84工具、源码分发及九种子ZIP安装通过；实机/WorkBuddy本轮未执行。实际main/标签/Release/四附件SHA256回填[PR #9](https://github.com/wudahua/MCP_CREO_MechDog/pull/9)，见[本版记录](validation/RELEASE-0.3.4.md)。 |
| [BUG-001](work-items/BUG-001.md) | P0 | 已完成（用户决定关闭） | 0.3.4 | 2026-10-17用户要求先关闭并将待合分支一并交付main。正式恢复实现及部分实机证据保留；IPC初始化通信失败/Creo无响应根因未定，完整恢复与WorkBuddy未完成，不代表全部验收通过。详见[离线排查](validation/BUG-001-hang-offline-2026-10-17.md)；后续复现沿用本ID重开，FEAT-018/029仍验收中。 |
| [DEV-029](work-items/DEV-029.md) | P1 | 已完成 | 0.3.3 | main@9ee923c、v0.3.3 与公开 [Pre-release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.3)一致；两目录各263项、原生回归和主干CI通过，四份主干附件已回下载核对SHA256；最终交付见 [PR #8](https://github.com/wudahua/MCP_CREO_MechDog/pull/8)，[候选验收](validation/RELEASE-0.3.3.md)及未测范围保留。 |
| [DEV-015](work-items/DEV-015.md) | P1 | 已完成（历史主干准备与集成） | 0.3.1 | 已核实 main@515d50b；未存在的 0.3.1 Release 不补造，累计公开交付由 DEV-025 / 0.3.2 承接。 |
| [DEV-025](work-items/DEV-025.md) | P1 | 已完成（发布候选验收） | 0.3.2 | 三批代码及完成文档集成，新目录独立安装、247 项单元、匹配 SDK 构建、8 成功/1 预期回滚作业、82 工具/9 种子和种子 ZIP 实际安装通过。见[本次证据](validation/RELEASE-0.3.2.md)；实际 main/标签/公开附件交付在 [PR #6](https://github.com/wudahua/MCP_CREO_MechDog/pull/6) 回填。 |
| [DEV-028](work-items/DEV-028.md) | P1 | 已完成 | 未排期 | 2026-10-16 Creo 9 编译与安装闭环：统一 BUG-033、DEV-019～022；14 项新增定向回归、260 项完整单元/语言守卫、本机 Creo 12.4 SDK 构建、显式环境真实 x64 编译运行及七个原生作业全部保存重载通过。[本批证据](validation/DEV-028.md)明确桌面启动环境、普通宿主 -4、此前失败与未测范围；Creo 9 实机编译/运行时未验收，版本 0.3.1，一个本地提交，不推送/发布。 后续 [WorkBuddy](validation/DEV-028-WorkBuddy-review-20261016.md) 的部署/通用单孔/通孔+盲孔已测范围通过，底板专用入口参数受阻仍未覆盖；本次仅补录，不改公共接口。 |
| [BUG-033](work-items/BUG-033.md) | P1 | 已完成 | 未排期 | 本机 SDK 生成 MECHDOG_HAS 探针，geometry/generic 两孔调用在两探针均存在时走原路径；常量表包含位置前移。缺失/部分/完整 SDK 夹具及 Creo 12.4 通用孔/底板孔的几何与保存重载通过，见 DEV-028；本机无 Creo 9 SDK，不外推实际旧版编译或运行时。 |
| [DEV-019](work-items/DEV-019.md) | P2 | 已完成 | 未排期 | 构建失败只读日志尾部 128 KiB、最多 15 条 error 摘要；仅实际 C2065 的 PRO_ 标识符提示 SDK 版本方向。纯函数与 bridge 失败路径夹具通过，不改变 MCP stdout，见 DEV-028。 |
| [DEV-020](work-items/DEV-020.md) | P2 | 已完成 | 未排期 | INSTALL 补微软官方 --includeRecommended 命令、静默缺组件症状及与显式环境/Python 占位一致的排错表；官方来源和文档检查通过，未运行 VS 安装器，见 DEV-028。 |
| [DEV-021](work-items/DEV-021.md) | P2 | 已完成 | 未排期 | config.json + setup.ps1 -VcVars64Env 两层完整 INCLUDE/LIB/PATH，校验/回写/环境检查/前置自检与默认路径兼容；PowerShell/cmd 夹具及真实 x64 编译运行通过，受限机器完整安装未验证，见 DEV-028。 |
| [DEV-022](work-items/DEV-022.md) | P2 | 已完成 | 未排期 | WindowsApps Python 在执行前提示 Microsoft Store placeholder 和 -Python；自动发现/显式路径夹具及真实 Python -CheckOnly 通过，真实商店交互未验证，见 DEV-028。 |
| [BUG-008](work-items/BUG-008.md) | P0 | 已完成 | 未排期 | 2026-10-16 按本机 Creo 12.4 已验证范围关闭：246 项单元，断开/探针有界保护，同实现真实冷态自动归档/重建/单次启动，以及新 [WorkBuddy](validation/BUG-008-WorkBuddy-reboot-retest-result-2026-10-16.md) 单次/重叠 retry、120 mm³ 建模/保存重载和 unknown 保护通过；见[关闭复核](validation/BUG-008-closure-2026-10-16.md)。WorkBuddy 冷态/异常环境和历史完整故障链仍未验证；未知任务不解锁，BUG-001/005/011 保留，未推送或发布。 |
| [BUG-009](work-items/BUG-009.md) | P0 | 已完成 | 未排期 | 模型锁内收尾、释放后发布终态；busy 保留协议错误并补占用/重试诊断。210 项开发检查及本机 Creo 12.4 [WorkBuddy 验收](validation/BUG-009-WorkBuddy-acceptance-20261015.md)已测范围通过；报告 33 个作业只读核对一致，协议疑点及即时性边界已[复核](validation/BUG-009.md#2026-10-15-验收复核与关闭)。真实挂死/失联恢复及其他宿主范围不外推，服务仍 0.3.1，未另发布。 |
| [BUG-002](work-items/BUG-002.md) | P1 | 已完成 | 0.2.6 | Windows 共享读取、单步原子替换、有界重试及自有临时文件清理；90 项单元、4,000 次压力写入与 Creo 12.4 并发/MCP 验收通过；原外部复测安排已随 DEV-018 取消。[本次证据](validation/BUG-002.md) |
| [BUG-006](work-items/BUG-006.md) | P1 | 已完成 | 0.3.0 | 修复提交 `ccc7366`：axis_pattern 兼容 datum_feature 轴标签，补齐逐工具引用契约与可操作错误；9 项新回归、158 项检查、stdio schema 与全新安装通过。用户 N1 确认后，本轮报告 P0-1 再次记录别名归一化通过及 by_tool 15 工具；仍无完整任务/模型 ID 清单，其他包装差异归 FEAT-008。开发者 timeout 保留；见 [证据](validation/BUG-006.md)、[引用说明](REFERENCE_SYNTAX.md) 与 [复测步骤](validation/BUG-006-WorkBuddy-test.md) |
| [BUG-007](work-items/BUG-007.md) | P0 | 已完成 | 未排期 | 本环境核心验收通过：标签引用两/三截面straight/smooth、已有底座追加、计划入口、几何/原生参数/保存重载/revision/回滚及后续通道；[最终WorkBuddy报告](validation/BUG-007-WorkBuddy-acceptance-2026-10-14.md)。整数公开引用失败单列BUG-028，开发者stdio整数成功证据保留；Creo10/并发/外部模态/策略未测，不外推 |
| [BUG-022](work-items/BUG-022.md) | P1 | 已完成 | 未排期 | 本机 Creo 12.4 边参考定位修复及 [WorkBuddy 四场景](validation/BUG-022-WorkBuddy-retest-20261015.md)通过，0.3.1 报告补真实去料正例；用户取消 Creo 10 独立验收门槛后按本机已测范围关闭。原报告来源、根因未确认及未测事实保留，收到新反馈再沿用本 ID 跟进。 |
| [FEAT-019](work-items/FEAT-019.md) | P1 | 已完成 | 0.2.6 | 用户接受 WorkBuddy / Creo 12.4 最终 MCP 验收：自动启动与真实 Toolkit 就绪、新建/草图/拉伸/尺寸驱动/倒角、保存重载通过；Codex MCP 只读复核 6 个成功修改任务与 revision=6 / volume=9980 mm³；121 项 Windows 单元/语言检查通过；Creo 10 及真实多客户端并发/退出后重连未测，Codex 冷启动失败单列 BUG-005；见 [证据](validation/FEAT-019.md) |
| [DEV-001](work-items/DEV-001.md) | P1 | 已完成 | 0.2.6 | 开发入口、台账、模板、语言基线与守卫、Windows CI 配置、源码分发同步；[本批验收](validation/DEV-001.md) |
| DEV-010 | P2 | 已完成 | 0.2.6 | 根 AGENTS.md 与[开发入口](DEVELOPMENT.md#workbuddy-测试约定)统一 WorkBuddy 最终 MCP 黑盒测试约定，不查看源码、不运行本地源码测试；2026-10-13 Windows 文档引用与约定一致性检查通过，未执行 WorkBuddy 测试 |
| [DEV-011](work-items/DEV-011.md) | P1 | 已完成 | 0.2.6 | 合并近两日三个开发分支至 main；121 项单元/语言守卫、SDK 构建、协议、解压与九种子 ZIP 安装通过；v0.2.6 预发布，源码/种子附件及 SHA256；本轮 Toolkit 超时、Creo 10 未测、BUG-005 保留，见 [发布证据](validation/RELEASE-0.2.6.md) |
| [DEV-012](work-items/DEV-012.md) | P2 | 已完成 | 0.2.6 文档补充 | 根据用户确认与已有 Creo 12.4 实机证据，统一 Creo 10 / Creo 12 可用性说明并补充 12.4 安装示例；文档链接与范围一致性检查通过，GitHub Release 正文已修改并回读核对；历史测试日期、未测分支、BUG-005、标签及附件保持原样；本次未执行新实机测试，见 [记录](work-items/DEV-012.md) |
| [DEV-013](work-items/DEV-013.md) | P1 | 已完成 | 0.3.0 | PR #3 普通合并保留历史，v0.3.0 Pre-release 已公开；本地/全新安装各 158 项及 Windows CI 通过，82 工具/九种子、四份附件回下载与摘要、公开更新发现通过；FEAT-020 未测场景、DEV-002 后续批次及 BUG-005 保留；见 [发布证据](validation/RELEASE-0.3.0.md) |
| [DEV-014](work-items/DEV-014.md) | P2 | 已完成 | 0.3.0 文档补录 | 原报告归档与原件 SHA256 一致，补录统计/覆盖边界并映射固定 ID，P0 三项建立独立卡；BUG-006/FEAT-020 同步本轮证据与未测范围。文档链接、ID/来源映射、表格和 diff 检查通过，见 [检查记录](validation/DEV-014.json)；仅文档整理，未修复缺陷或新做建模测试 |
| [DEV-016](work-items/DEV-016.md) | P2 | 已完成 | 未排期 | 2026-10-15 精简主台账并归档原有 10 项完成记录，合并三项重复登记；原有 62 个 ID 的状态、优先级与目标版本保留，文档完整性及链接检查通过。 |
| [DEV-017](work-items/DEV-017.md) | P2 | 已完成 | 未排期 | 原样归档0.3.1全量报告，17个问题及部署建议完成去重映射；新增4项待核实缺陷与4项能力建议，同步复验和覆盖边界。报告字节/哈希、ID保留、映射与本次引用检查通过，见[文档证据](validation/DEV-017.json)；DEV-002同期链接单独记录，未修复程序或新增建模测试。 |
| [DEV-018](work-items/DEV-018.md) | P2 | 已完成 | 未排期 | 按用户要求取消全项目 Creo 10 独立复测、双版本验收及正式基线门槛，同步当前规则、台账和任务卡；DEV-002 第二批按开发与 WorkBuddy 已测范围完成，BUG-022 按本机证据归档。历史报告与未测事实保留，收到朋友新反馈再跟进；[文档检查](validation/DEV-018.json)通过，无新程序或实机测试。 |
| DEV-023 | P2 | 已完成 | 流程规范（不升版） | 2026-10-16 按用户要求，将每次合入 main 必须发布对应版本 GitHub Release 写入[根级规范](../AGENTS.md#合入-main-与-release项目全局)、[开发入口](DEVELOPMENT.md)与[发布规则](development/RELEASING.md#合入-main-必须同步发布)，同步 PR 模板；覆盖文档/配置变更，要求版本、主干提交、标签及附件一致，发布未完成则交付未完成。Windows 下 9 项规则检查、13 个本地文档链接及定向 git diff --check 通过；仅文档变更，版本仍为 0.3.1，未执行合并、实际发布或原生测试。 |
| [DEV-024](work-items/DEV-024.md) | P2 | 已完成 | 未排期 | 2026-10-16 阅读并原样归档下载目录4份Markdown，41个编号问题及构建线索去重映射；新增14项待核实缺陷BUG-034～047、2项能力候选FEAT-029～030，同步已有工作卡及证据边界。[文档检查](validation/DEV-024.json)核对原件/哈希、ID、来源、链接与表格；保留同期BUG-008外部更新，仅同步文档，未复现、修复或执行新建模测试。 |
| [BUG-038](work-items/BUG-038.md) | P2 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 B](validation/FEEDBACK-0.3.2.md) 的 Creo 9.0.0.0 实测（`true` 存为 `BOOLEAN(53)=True`，0.3.0 为 REAL(52)=1）转已完成：本仓库无对应修复提交可核实，未在本机复验布尔映射与保存重载；本机复现失败须重开本 ID。 |
| [BUG-042](work-items/BUG-042.md) | P1 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P1（100×100×10 底块 + 2 个互不相邻矩形一次 add，体积 103 000 逐项吻合，job `7fee41d0c5604db2b80b06497c30fb11`）转已完成：本仓库无对应修复提交可核实，未在本机复验多区域增料；本机复现失败须重开本 ID。 |
| [BUG-043](work-items/BUG-043.md) | P1 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P2（面贴合 add 成功并入同一实体 `bodies:1`、体积 +1 000，job `194f59d6ff9e40559d1aa9d1f82313e9`）转已完成：本仓库无对应修复提交可核实，未在本机复验共面合并；本机复现失败须重开本 ID。 |
| [BUG-044](work-items/BUG-044.md) | P2 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P4（闭合 `polyline` 截面拉伸成功、体积 +1 000）转已完成：开放链不可作实体截面属预期限制；本仓库无对应修复提交可核实，未在本机复验 polyline 截面；本机复现失败须重开本 ID。 |
| [DEV-026](work-items/DEV-026.md) | P2 | 已完成 | 未排期 | 2026-10-16 归档并映射下载目录 3 份 0.3.2 报告（A/B/C 与原件逐字节一致），新增 DEV-027、BUG-048、FEAT-031；按用户决定把 BUG-038/042/043/044 转入本归档并标注外部证据边界；Creo 9 与 Toolkit 9 纳入文档支持范围。[文档检查](validation/DEV-026.json)核对原件/哈希、编号覆盖、ID 与链接；仅同步文档，未复现、修复或执行新建模测试。 |

## 历史来源索引

以下仅保留来源编号与固定 ID 的对照；其中涉及未完成事项时，以主台账当前记录为准。报告中的优先级编号不等于仓库优先级或交付状态。

### WorkBuddy 0.3.0 报告编号

来源：[2026-10-14 原始报告](validation/MCP_CREO_MechDog_0.3.0_全量实测问题报告.md)及[证据边界](validation/WORKBUDDY-0.3.0.md)。P0-3.1/3.2 归 BUG-007，P0-3.3/3.4 归 BUG-008，P0-2 归 BUG-009。

| 来源编号 | 固定 ID |
| --- | --- |
| P1-5 | BUG-010 |
| P1-8 | BUG-011 |
| P1-7；P3-2 | BUG-012 |
| P1-6（原 P2-1）；N2；P3-4；Creo10报告问题7 | BUG-013 |
| P1-2/P2-13；P2-8；P3-1/P3-5；Creo10报告问题9 | BUG-014 |
| P1-7 根因补充；第八节 P2 | BUG-015 |
| P2-10 | BUG-016 |
| P2-11（rib）；Creo10尺寸编辑报告问题2 | BUG-017 |
| P2-4；P2-8 的空 operations | BUG-018 |
| P1-3 | BUG-019 |
| P2-12 | BUG-020 |
| P0-3 建议4/5；第八节 | FEAT-021 |
| 第二节2.1；第八节 | FEAT-022 |
| P2-5；P3-3 | FEAT-023 |
| N4；第八节 | FEAT-024 |

对已有条目的复用关系如下，验收条件合并到主台账或独立工作卡中，不在此重复维护。

| 报告项 | 固定 ID / 去向 |
| --- | --- |
| P0-1；兼容别名 | BUG-006 / FEAT-008 |
| P1-1 | FEAT-005 |
| P1-4；P2-3/P2-11；N3 | FEAT-006 |
| P2-9 | FEAT-004 |
| P2-2 | FEAT-008 |
| P2-6 | FEAT-001 / BUG-008 |
| P2-7 | DEV-005 / DEV-012 |
| P3-2；恢复建议 | BUG-001 / FEAT-018 |
| 更新接口及升级后重启连接器 | FEAT-020 / FEAT-022 |
| 全量测试范围、覆盖限制及重启事件 | DEV-006 / DEV-007 / DEV-014 |

### 原问题清单编号

来源：[原问题快照](待完善功能清单.md)。下列编号属于旧清单，不作为新增已证实缺陷；实施前须整理可移植的复现输入和仓库内证据。

| 来源编号 | 固定 ID |
| --- | --- |
| 1 | FEAT-001 |
| 2 | BUG-001 |
| 3 | FEAT-002 |
| 4 | FEAT-003 |
| 5 | FEAT-004 |
| 6 | BUG-002 |
| 7 | BUG-003 |
| 8 | BUG-004 |
| 9 | FEAT-005 |
| 10 | FEAT-006 |
| 11 | FEAT-007 |
| 12 | FEAT-008 |
| 13 | DEV-005 |
| 14 | DEV-006 |

保留原快照澄清：工具/参数名不稳定需原始日志，不能直接认定服务端缺陷；旧关系式再生失败曾因取错尺寸；Creo 12 直接混合因人工加载等待，尚无有效几何验收；翼型入口已统一 `pivot_fraction`。

### 未来能力候选编号

来源：[NEXT_STEPS_025](NEXT_STEPS_025.md)。此处仅供溯源，范围、状态与排期以主台账为准。

| 来源编号 | 固定 ID |
| --- | --- |
| 功能建议 1 | FEAT-009 |
| 功能建议 2 | FEAT-010 |
| 功能建议 3 | FEAT-011 |
| 功能建议 4 | FEAT-012 |
| 功能建议 5 | FEAT-013 |
| 功能建议 6 | FEAT-014 |
| 功能建议 7 | FEAT-015 |
| 完善建议 2 | FEAT-016 |
| 完善建议 3 | FEAT-017 |
| 完善建议 4 | FEAT-018 |
| 完善建议 1 | DEV-007 |


## 历史进展与反馈补录

2026-10-17 按 [DEV-037](work-items/DEV-037.md) 从主台账迁入。以下保存整理前的阶段叙述和反馈映射，包括已完成事项及未完成事项的历史观察；其中“未合入”“待验收”“待用户决定”等均是当时状态，不承担当前排期，也不表示相关未完成条目已经关闭。当前状态统一查看[主台账](BACKLOG.md)。

<details>
<summary>整理前阶段进展（2026-10-15～17）</summary>

- 2026-10-17 根据当前进度建立 [DEV-036：Toolkit 通道静默掉线核实、修复与验收](work-items/DEV-036.md)（P1，待开发），接续 0.3.5 交付后的 BUG-056。先离线区分快照陈旧/探测失败/真实 IPC 失效/进程退出，满足卡死核对与当前会话可操作条件后再做空闲及间隔探测、定位修复和分层验收；M2 保护保持，实际处置另须明确选择。DEV-027/DEV-030 的最新 Creo 10 反馈继续原卡跟踪；BUG-056 仍待核实、FEAT-018/029 仍验收中。本轮仅建卡和文档同步，目标版本未排期，不恢复 Toolkit 联调。

- 2026-10-17 [0.3.4 / Creo 10 构建与回调反馈补录](validation/FEEDBACK-0.3.4-CREO10-2026-10-17.md)（0.3.5 交付后登记，不新建 ID）：[DEV-027](work-items/DEV-027.md) 核心问题获首个外部 Creo 10 实测正例——0.3.4 loader/payload 分层实测修复"重编译致注册失效"（删除 loader.dll 后同 SHA256 恢复、`protk.dat` 不变），剩余范围收窄为 payload 目录清理/当前标记（该环境 6 个/17 MB 只增不减，0.3.5 源码仍无清理逻辑）；vcvars64_env 恰好三键再报归 [DEV-030](work-items/DEV-030.md) 需求核对（0.3.5 源码一致）；[FEAT-029](work-items/FEAT-029.md) 补 readiness 双义观察；[BUG-034](work-items/BUG-034.md)/[FEAT-030](work-items/FEAT-030.md) 补 Creo 10 三截面种子正例对照。原件逐字节归档；本轮仅同步文档，不清理目录、不重演删除测试、不连接 Toolkit。同日 Creo 9 报告此前已随 BUG-055/DEV-034 闭环，不重复登记。

- 2026-10-17 按用户要求通过 [DEV-035](work-items/DEV-035.md)统一提交并交付0.3.5：DEV-033/BUG-054、DEV-034/BUG-055及反馈/BUG-056登记保留全部历史；本轮做适用离线/单元/SDK/分发核对，不新增Creo连接。BUG-054与BUG-055核心范围完成并归档，M2终态未取得、BUG-056待核实、FEAT-018/029验收中保持，实际主干/Release信息在交付PR回填。

- 2026-10-17 新增 [BUG-056：Toolkit 通道验证通过后约 40 秒静默失效](work-items/BUG-056.md)（P1 待核实）。WorkBuddy 验收期间三次"验证通过→37～41 秒→`not_found_or_unreadable`/`connect_creo` -4/探测退出码 20"，Creo 进程存活、可重连、用户确认无手动操作；与 BUG-001 卡死区分不重开。先低风险间隔探测复现并取 Creo 侧证据，再排除许可证/多协调器/空闲超时等假设；不自动重连、不清保护。M2 的收尾受阻于此项。

- 2026-10-17 [BUG-055 WorkBuddy 黑盒验收通过](validation/BUG-055-WorkBuddy-acceptance-2026-10-17.md)（受测 `26a3edd`，开发者只读核对逐项一致）：核心契约全部符合——schema 空值契约可见、M1 经省略字段完整闭环（abandoned/rev 0/幂等/原作业保留）、空串精确拒绝回显 `received ''`、字面 "null" 按 SDK 预解析接受、M2 恢复作业 unknown_outcome 时保护按契约保留未重放。**决定性证据：WorkBuddy 客户端实测把显式 JSON null 降级为空串**——外部报告根因链闭环（转换在客户端序列化层，旧代码误报 stale，修复后可观察且省略字段替代路径可用）。未取得：M2 最终终态与稳定通道下字面 null 对照（通道三次静默掉线 37–41 秒节奏、worker_exit_code=20，环境异常超本卡范围、不据此重开 BUG-001，是否另立条目待用户决定）、工具总数（capabilities 响应超 WorkBuddy 客户端上限）。[DEV-034](work-items/DEV-034.md) G0～G5 完成。

- 2026-10-17 [DEV-034 G0～G4 完成](work-items/DEV-034.md)：服务端各层不存在 null→空串转换（受测 mcp 2.3.0 与 v0.3.4 锁定一致），空串产生与外部报告逐字一致的 stale 错误，字面 "null" 被 SDK 预解析为 null；按此确定契约（null/省略合法等价、空串/空白精确拒绝、非空 ID 精确匹配、stale 拆分报告实际值）完成最小修复并同步 schema 描述与 [MODEL_RECOVERY.md](MODEL_RECOVERY.md)。新增 `tests/unit/test_reconciliation_mcp.py` 真实 stdio 协议回归 6/6，全量单测 307/307，dev_check 通过；实机（Creo 12.4）自然失败模型经真实 MCP 显式 null apply 到 succeeded，空串实机协议得到精确输入错误。BUG-055 转"已修复，WorkBuddy 验收待执行"，[提示词](validation/BUG-055-WorkBuddy-test.md)已备；外部 Creo 9 环境未复测记为未验证；未升版、未合入 main。证据见 [BUG-055-fix-2026-10-17.md](validation/BUG-055-fix-2026-10-17.md)。

- 2026-10-17 根据用户最新修改后的台账，DEV-033/BUG-054 已完成实机及 WorkBuddy 验收；下一轮建立 [DEV-034：恢复工具 MCP 空值契约核实、修复与验收](work-items/DEV-034.md)，聚焦 P1 BUG-055。先以真实 stdio/独立客户端核对 null、省略及 stale 差异，再最小修复、授权保护回归和正式 MCP 恢复闭环；本轮仅建卡，BUG-055 保持待核实，目标版本未排期，FEAT-018/029 不随本卡关闭。

- 2026-10-17 [BUG-054 WorkBuddy 黑盒验收通过](validation/BUG-054-WorkBuddy-acceptance-2026-10-17.md)：5 场景全部符合预期（有效切除 40π、板外/重复/revolve 无交集按契约失败且体积/revision/sha256 不变、失败后可继续编辑），开发者只读核对 11 个作业与本地记录逐项一致；含提示词场景 D 基准歧义说明与 `depth:1.0` 回显次要观察（未登记新条目）。[BUG-054](work-items/BUG-054.md) 三层证据链闭环、[DEV-033](work-items/DEV-033.md) G0～G5 完成；未测边界不变，未合入 main、未发布。本轮仅记录验收与核对，未连接 Creo、未改代码。

- 2026-10-17 [0.3.4 / Creo 9 反馈补录](validation/FEEDBACK-0.3.4-2026-10-17.md)：新增 [BUG-055](work-items/BUG-055.md)（恢复 apply 的 MCP 可空参数/stale 拒绝差异，P1 待核实）。null 转空串仅为根因线索，需真实协议与独立客户端对照；inspect 和 callback_status 补限定正例。token 时效、入队前回调提示、别名/分页和新工具 MCP 冒烟沿用原条目，种子/筋/装配约束/round 不重复建卡。保留当前 BUG-054/DEV-033 的开发实机成果及剩余 WorkBuddy 范围；本轮仅同步文档，不连接 Creo，不重开 BUG-001。

- 2026-10-17 下一轮建议优先推进 [DEV-033：切除材料变化核实、修复与验收](work-items/DEV-033.md)，聚焦新增 P1 BUG-054。先离线核对，满足卡死根因核对与会话可操作条件后再做当前版本最小复现、结果契约、修复和分层验收；BUG-054 保持待核实，FEAT-018/029 保持原验收状态。本轮仅建卡，目标版本未排期，不恢复 Toolkit 联调。

- 2026-10-17 [0.3.3 四份反馈去重补录](validation/FEEDBACK-0.3.3-2026-10-17.md)：新增待核实 [BUG-054](work-items/BUG-054.md)（拉伸切除零去料仍静默成功）及待规划 FEAT-034～037（弧方向/扫角、沉孔/沉头孔、零件特征删除/抑制/恢复、参数作用域）。装配直接矩阵输入补入 FEAT-012；组件身份/快照/选轴/图纸默认值、PATH 示例、签名 DLL 及 Creo 9 冒烟建议沿用已有条目。原件逐字节归档，均为外部 0.3.3 证据，当前 0.3.4 未复测；本轮只补文档，不连接 Creo。

- 2026-10-17 用户决定关闭BUG-001并将全部待合分支统一交付main，明确指定0.3.4。[DEV-032](work-items/DEV-032.md)发布候选已完成，两目录各297项、独立SDK构建/分发通过；实际主干/Release核对见[PR #9](https://github.com/wudahua/MCP_CREO_MechDog/pull/9)；BUG-001移入[关闭归档](BACKLOG_COMPLETED.md)，卡死根因和未完成实机范围保留，不视作全部验收通过。FEAT-018/FEAT-029继续验收中，本轮不恢复Toolkit联调。下面已注明日期的验证与提交记录保留当时阶段。

- 2026-10-17 BUG-001新增[卡死离线排查](validation/BUG-001-hang-offline-2026-10-17.md)：trail确认IPC初始化`-97`/Warning、客户端`-11`，Windows确认同一Creo12.4进程无响应关闭；底层诱因未定，不能认定SDK版本错误。当前快照无Creo进程，待确认会话可操作后再恢复联调；本轮没有Toolkit连接/注入，未关闭、合并或发布。

- 2026-10-17 已补齐 [BUG-001/FEAT-018受控恢复联合执行卡](work-items/BUG-001-FEAT-018-RECOVERY.md)，两项现进入验收中：正式恢复入口、保护和持久化登记已实现，284项单元及四动作部分实机通过；本轮随后Creo卡死，最终实机/WorkBuddy未完成，见[本次验证记录](validation/BUG-001-recovery-2026-10-17.md)。工作目录固定E盘；本机MCP只启用MCP_CREO_MechDog_dev，C盘旧服务退役。未关闭、合并或发布。

- 2026-10-16 [DEV-030 G0已完成](work-items/DEV-030.md)：[BUG-001现版本复现](validation/BUG-001-repro-2026-10-16.md)确认当时0.3.3模型协调阻断，保护层按设计生效但无正式恢复接口；有基线模型人工解锁后门禁循环，无基线模型可能静默采纳半成品，保存后未交付另列一类。2026-10-17恢复实现已提交并进入验收，复现原始记录保持不变，BUG-008锁释放/通道恢复关闭范围保持。

- [DEV-030分期](work-items/DEV-030.md)现为恢复实现验收中、FEAT-029开发分支已集成；剩余为卡死定位、完整验收和主干交付，之后处理底板/编辑闭环及履带基础/性能/阵列。[分支核对](validation/DEV-030-branch-sync-2026-10-17.md)确认建卡、反馈补录、G0复现及E盘同步提交均已包含在当前集成分支。新增[0.3.3构建/回调反馈](validation/FEEDBACK-0.3.3-BUILD.md)关联DEV-021/019/027及FEAT-029：外部三键环境编译正例、额外键兼容与日志展示待核对、目录/缓存/可复现性分别核实，DEV-019/021原完成范围保持。

- [DEV-029：0.3.3 主干交付](work-items/DEV-029.md)已完成：main@9ee923c 与 v0.3.3 指向一致，[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.3)已公开为 Pre-release，四份附件从实际主干生成并下载核对 SHA256；主干 CI、两目录各 263 项与原生回归通过，最终交付见 [PR #8](https://github.com/wudahua/MCP_CREO_MechDog/pull/8)。原[候选记录](validation/RELEASE-0.3.3.md)保留当时阶段与未测范围。

- 2026-10-16 [DEV-028：Creo 9 编译与安装闭环](work-items/DEV-028.md) 已完成，BUG-033 与 DEV-019～022 统一移入[完成归档](BACKLOG_COMPLETED.md)：14 项新增定向回归、260 项完整单元/语言守卫、本机 SDK 构建、显式环境真实编译及桌面环境 Creo 12.4 七个原生作业通过，逐任务保存重载 true，见[本次证据](validation/DEV-028.md)。Creo 9 实机编译/运行时仍未验证；普通 Codex 宿主连接 -4 的限制单独记录。一个本地提交，不推送、不发布、不升版。 后续 [WorkBuddy 复核](validation/DEV-028-WorkBuddy-review-20261016.md)采纳部署和通用计划单孔/双孔通过；底板快捷入口参数受阻，仍未覆盖，序列化原因待核实，线索归 FEAT-008。
- FEAT-029已按2026-10-17用户指令集成到E盘codex/feat-029-integration：297项单元、SDK编译、载荷ABI及84工具stdio离线检查通过。见[本次集成](validation/FEAT-029-integration-2026-10-17.md)。BUG-001卡死未定位，集成环境实机/WorkBuddy待测，未合入main或发布；历史879aebe证据不改标为本轮通过。
- [P1 联合修复](work-items/P1-MODELING-REPAIR.md)：本环境已测分支已有 WorkBuddy 通过记录；查询预算、放样计划入口引用及恢复失败等功能边界按各项继续验收。BUG-022 已完成并归档，原环境反馈保留来源。
- 0.3.1 已合入历史 main@515d50b，未发布 v0.3.1；累计公开交付已由 DEV-025 / v0.3.2 完成。更新提醒仍有未测场景，Python 包迁移继续分批推进。
- P0 通道恢复 BUG-008 按本机 Creo 12.4 已验证范围完成并移入[完成事项归档](BACKLOG_COMPLETED.md)：246 项单元、同实现真实冷态自动归档/重建/单次启动，以及新 WorkBuddy retry/120 mm³ 建模/unknown 保护通过。WorkBuddy 冷态与异常环境、历史完整链仍未验证，分层边界见[关闭复核](validation/BUG-008-closure-2026-10-16.md)。BUG-009 已完成并归档；其他未确定版本的事项保持“未排期”。
- [0.3.1 实测补录](validation/WORKBUDDY-0.3.1.md)：新增 4 项待核实缺陷、4 项能力/体验建议，其余复用已有 ID；报告统计与输入适用性有待核实之处，本次未复现或修复。
- [2026-10-16 四份反馈补录](validation/FEEDBACK-2026-10-16.md)：41 个编号问题及构建绕过线索已去重映射；新增 BUG-034～BUG-047（14 项待核实）和 FEAT-029～FEAT-030（2 项待规划）。保留 Creo 9/10 与具体版本未明的不同来源；回调升级负担、拓扑/API 根因和 Release 状态按证据边界继续核实，本次仅同步文档。
- [2026-10-16 三份 0.3.2 反馈补录](validation/FEEDBACK-0.3.2.md)：A/B/C 三份报告已归档并去重映射。按用户决定把 BUG-038、BUG-042、BUG-043、BUG-044 转已完成并移入[归档](BACKLOG_COMPLETED.md)，标注"采信外部报告、本仓库无对应提交可核实、本机复现失败须重开"；新增 [DEV-027](work-items/DEV-027.md)（回调 DLL 非确定性构建）、[BUG-048](work-items/BUG-048.md)（含镜像特征抽壳失败）、[FEAT-031](work-items/FEAT-031.md)（装配交付打包导出）。Creo 9 与 Toolkit 9 纳入[兼容说明](COMPATIBILITY.md)等文档的支持/要求范围，建模运行时未在本机验收；本次仅同步文档，见 [DEV-026](work-items/DEV-026.md)。
- 2026-10-15 按用户要求取消整个项目的 Creo 10 独立验收门槛，见 [DEV-018](work-items/DEV-018.md)。DEV-002 第二批本机开发与 WorkBuddy 已测场景通过，本批完成；整体迁移继续推进。
- 2026-10-15 收到第三方用户 Creo 9 SDK（Toolkit 9）编译失败反馈，[报告已归档](validation/2026-10-15_CREO_0.3.0_旧版ToolkitSDK原生编译失败.md)，当时登记 BUG-033 与 DEV-019～022。2026-10-16 DEV-026 调整支持文档，DEV-028 现已完成编译探测和安装链实现；本机未验证 Creo 9 实机编译/运行时，后续反馈继续按来源补录。

</details>

<details>
<summary>历次反馈补录与来源映射</summary>

## 2026-10-17 0.3.4 恢复工具与 Creo 9 反馈补录

[原件、环境、方法与去重映射](validation/FEEDBACK-0.3.4-2026-10-17.md)及[SHA256 清单](validation/feedback-0.3.4-2026-10-17/manifest.json)已归档。新增 BUG-055；报告原列 P0，本台账先按 P1 待核实跟踪恢复工具调用差异，未取得全通道封锁或会话损坏证据。直接 Python 驱动作业不是 MCP apply 通过，标准 null 是否被转换及发生在哪层仍需核实。

FEAT-018 补 token 时效/重新 inspect 指引，FEAT-029 补状态查询正例与建模前摘要，FEAT-006/008 补 label/原生名及分页规则，DEV-006/007 补真实 MCP 工具层冒烟。种子生产版本/兼容元数据归 FEAT-030，筋/种子/装配约束/round 继续原 ID；未知 owner 的 busy 回退符合 BUG-009 现有边界，不自动重开。BUG-033 补限定孔正例，所有外部观察均保留缺少完整 job/model/保存重载证据的范围。

本轮未修改代码、配置、token、模型或版本，未执行报告中的升级/Python 绕行/恢复/并发测试，未连接 Toolkit。BUG-001 原关闭、FEAT-018/029 验收中及 BUG-054/DEV-033 当前进度保持，不因报告建议推断种子生产版本、跨环境失败根因或全部兼容性。

## 2026-10-17 0.3.4 Creo 10 构建与回调反馈补录

[原件、环境与去重映射](validation/FEEDBACK-0.3.4-CREO10-2026-10-17.md)及[SHA256 清单](validation/feedback-0.3.4-2026-10-17/manifest.json)已归档（11088 字节，与同日 Creo 9 报告同目录收录、manifest 合并为双来源，登记于 main `8ce644f` / v0.3.5 之后）。本轮不新建 ID：注册解耦正例与 payload 目录累积续报归 [DEV-027](work-items/DEV-027.md)，readiness 双义观察归 [FEAT-029](work-items/FEAT-029.md)，vcvars64_env 三键再报归 [DEV-030](work-items/DEV-030.md) 需求核对，Creo 10 三截面种子正例归 [BUG-034](work-items/BUG-034.md)/[FEAT-030](work-items/FEAT-030.md)。

报告在其 0.3.4 / Creo 10 环境实测：loader/payload 分层修复注册反复失效（含删除 loader.dll 破坏性对照）、三键配置编译成功、三截面混合建模通过（保存重载 true）、直接放样约 9 秒快速失败；反馈人无法在其 Creo 10 完成 GUI 注册安全确认，回调加载后端到端链路仍未验证。本轮已对 0.3.5 源码逐项核对报告三处事实（恰好三键、payload 无目录清理、loader/payload 分层），均一致；未执行报告建议的目录清理/current 指针/键集放宽，未重演删除测试或编译，未连接 Toolkit。报告环境（Creo 10、reg.exe 受限）观察不外推到本机 Creo 12.4 或其他环境。

## 2026-10-17 0.3.3 四份反馈去重补录

[原件、环境与去重映射](validation/FEEDBACK-0.3.3-2026-10-17.md)及[SHA256 清单](validation/feedback-0.3.3-2026-10-17/manifest.json)已补齐。新增 1 个缺陷候选、4 个能力条目；装配直接矩阵输入复用 FEAT-012，不重复建卡。FEAT-008/023 补组件内联身份、快照、实际选轴与 drawing_view 默认值；DEV-021 的 PATH 示例请求、FEAT-029 的签名 DLL 评估、DEV-006/007 的 Creo 9 冒烟切片沿用原 ID。

钣金、种子、筋、装配约束、round 参数、诊断/体量等重复反馈保持原归属和状态。BUG-033 的外部 Creo 9 编译正例与限定孔建模数值已补卡，未取得完整作业身份/重载链；不外推为本机或完整 Creo 9 运行时验收。所有来源均为 0.3.3，当前 0.3.4 未复测；本轮未改代码/版本、未执行来源操作或连接 Creo，BUG-001 关闭和 FEAT-018/029 验收中状态保持。

## 2026-10-16 0.3.3 构建与回调补录

[原件、来源边界、Q1～Q3及去重映射](validation/FEEDBACK-0.3.3-BUILD.md)已归档：三键显式环境在外部Creo10/reg.exe受限环境编译成功；额外SDK键拒绝关联DEV-021，成功warning/note与失败摘要须区分关联DEV-019，目录累积/重新注册负担关联DEV-027和FEAT-029。没有完整日志、环境转储及连续构建序列，根因与计数仍待核实。DEV-019/021历史完成状态不改，不新开重复ID；后续兼容/展示请求由DEV-030核对再明确实施范围。没有执行报告中的清目录、固定current、改缓存或/Brepro建议。

## 2026-10-16 履带案例与反馈映射

两份材料见[原件清单、逐节去重与输入差异](validation/TRACK-FEEDBACK-2026-10-16.md)；新建 BUG-049～053、FEAT-032～033、DEV-030～031，补齐 BUG-001、FEAT-006/008/018 等既有卡。报告中的清锁/重启、自动并集、预算公式和根因解释只作来源，不是本次操作指令；BUG-001对应阻断后续已在G0复现，其余问题不外推为已复现，不改已关闭 BUG-008 的结论。

## 2026-10-16 四份反馈问题映射

[来源、41项编号映射与证据边界](validation/FEEDBACK-2026-10-16.md)收录下载目录全部4份Markdown原件，保留SHA256、报告环境及job/model标识。新增BUG-034～BUG-047与FEAT-029～FEAT-030；回调就绪、会话/状态、查询体量、错误上下文、进度、回滚历史、四壁折弯释放与发布缺口复用已有ID。

报告中的根因、优先修复顺序和替代方案不自动成为实施结论；Q6启动路径未复测、回调重注册负担未实测、两份配电箱具体Creo版本未提供。Q3所述0.3.1 Release缺失按DEV-015待核对，当前远端未查询；Q4旧版本句在本次工作区已不存在，远端/反馈方部署是否更新无法确认。本次只补录，不执行报告中的注册、发布或本地重建步骤，不把旧实例失败覆盖本机已测正例，不改变兼容支持声明。

## 2026-10-16 三份 0.3.2 反馈问题映射

[来源、编号映射与证据边界](validation/FEEDBACK-0.3.2.md)收录下载目录全部 3 份 Markdown 原件，保留 SHA256、报告环境、作业与模型标识。报告 A 的 16 条回归编号、报告 B 的 9 项问题与 2 项已修复确认、报告 C 的 2 项问题及观察项均已落到固定 ID：新增 [DEV-027](work-items/DEV-027.md)、[BUG-048](work-items/BUG-048.md)、[FEAT-031](work-items/FEAT-031.md)；BUG-042、BUG-043、BUG-044（A 的 P1/P2/P4）与 BUG-038（B 的布尔类型实测）按用户决定转已完成并移入[归档](BACKLOG_COMPLETED.md)。

报告 B 的文件名与标题写"Creo10"而正文环境为 Creo 9.0.0.0，两者不一致已如实保留；报告 A 的"已修复"采信为外部结论，本仓库无对应提交可核实，本机复现失败须重开。A 未复测 P6～P10，S2/S6/S7 未复测或据同代码路径推断，不因同一报告其他项通过而外推。报告中的建议、作者提问与本机路径只作来源记录，不构成本轮执行指令，见 [DEV-026](work-items/DEV-026.md)；Creo 9/Toolkit 9 支持声明按[兼容说明](COMPATIBILITY.md)本次调整的口径执行。本次只补录，未执行报告中的注册、重编或建模步骤，未核对远端 Release。

## WorkBuddy 0.3.1 全量实测问题映射

[原始报告](validation/MCP_CREO_MechDog_0.3.1_全量实测问题报告.md)已原样归档，17 个问题、部署建议、修复复验及未测项的固定 ID 对照见[补录与证据边界](validation/WORKBUDDY-0.3.1.md)。新增 BUG-029～BUG-032、FEAT-025～FEAT-028，其余复用已有条目；新增项报告环境为 Windows x64 / Creo 12.4.0.0，其他环境收到具体反馈后再跟进。

“82/82 调用”与 `create_udf` 未调用等统计存在口径不一；直接 loft 仅验证缺回调失败路径，不能关闭 BUG-028 或重开 BUG-007。API/锁/草绘根因推断、种子降级方案均待核实。以上仅补录，未开展新建模测试；报告修复建议顺序不自动变为排期。

## WorkBuddy 0.3.0 全量实测问题映射

[原始报告](validation/MCP_CREO_MechDog_0.3.0_全量实测问题报告.md)与[证据摘要及覆盖限制](validation/WORKBUDDY-0.3.0.md)保留历史结论。报告编号与固定 ID 的[来源索引](BACKLOG_COMPLETED.md#workbuddy-030-报告编号)已归档；未完成事项按本表继续跟踪。报告含内部分析、历史证据复用和未测场景，不代表全工具、全分支或真实并发验收通过。

## 原问题清单映射

[原问题快照](待完善功能清单.md)与[未来建议快照](NEXT_STEPS_025.md)保留原日期和编号；固定 ID 对照见[历史来源索引](BACKLOG_COMPLETED.md#历史来源索引)。

</details>

## 2026-10-18：0.4.0 随版归档（0.3.7 / Creo 13 反馈五项闭环）

随 0.4.0 合入 main 归档；台账状态与证据详见各行验证记录与 [RELEASE_NOTES_0.4.0.md](RELEASE_NOTES_0.4.0.md)。BUG-050（主线成因已修复）、BUG-019、FEAT-029 保持验收中，仍在主台账。

| [BUG-067](work-items/BUG-067.md) | P1 | 已完成 | 未排期 | 2026-10-18 本机 Creo 12.4 经公开 MCP 接口复现定性：两例报告输入（上半圆+竖直轴、31 点折线半圆+竖直轴）均为**非法跨轴旋转截面**，同码复现 -1 且回滚成功；合法画法（轴与直径边界重合，r=5 半圆）得精确球 500π/3、参数可编辑、保存重载通过——**非 Creo 13 元素树不兼容**。产品缺陷"拒绝但不解释"已修复：元素级错误可回传，旋转/拉伸创建失败带跨轴/中心线/闭合提示与草图标签，保护行为不变；dev_check 与 test_general 回归通过。Creo 13 合法输入复测留外部条件，不据此宣称该版本已支持；整数引用报错归 FEAT-008。证据见[复现与修复记录](validation/BUG-067-repro-2026-10-18.md)。 |
| [BUG-068](work-items/BUG-068.md) | P1 | 已完成 | 未排期 | 2026-10-18 本机 Creo 12.4 经公开 MCP 接口复现同码 -2（弧圆心在原点的原报告同款几何）并隔离定位：约束引用固定传 pnt={0,0}，与弧圆心重合时端点参考方位角退化（atan2(0,0)）→ BAD_INPUTS；与 Creo 版本、Intent Manager、名称解析均无关。已修复：按引用类型计算实体上的真实参考点 + idx_pnt=PRO_VALUE_UNUSED（含圆/弧 WHOLE 引用修正），sketch 与 populate_profile 两处共用；约束语义与模式分派不变。回归：复现/对照全过、test_sketch_stability 扩至 8 用例、BUG-067 合法旋转不回归。Creo 13 复测留外部条件。证据见[复现与修复记录](validation/BUG-068-BUG-050-repro-2026-10-18.md)。 |
| [BUG-069](work-items/BUG-069.md) | P3 | 已完成 | 未排期 | 模型命名放宽（用户确认方案）：正则 [a-z0-9][a-z0-9_]{0,30} 允许数字开头，大写输入统一 normalize_model_name 规范化为小写并回显实际名，错误信息含完整规则；plate/generic submit/adopt 三校验点统一。001/PRT001/prt001 实测全部可用（001.prt.2 保存重载 verified），会话大小写碰撞仍拒绝，特征 label 规则不变。2026-10-18 本机 12.4 验证；Creo 13 未测。关联 BUG-070、FEAT-042。 |
| [BUG-070](work-items/BUG-070.md) | P2 | 已完成 | 未排期 | 会话探针 current_model 乱码（▩名0001）根因为 deprecated ProMdlNameGet 失败不写缓冲+ProName 未初始化（本机 hex dump 定案 native 层）；已改用继任 ProMdlMdlnameGet+零初始化+返回值检查并新增 name_read_code 诊断字段。2026-10-18 本机 12.4 探针与 MCP 双层复验返回干净可读名；Creo 13 外部环境未测。关联 BUG-069、FEAT-042。 |

FEAT-042首阶段历史：显式接管用户已打开模型的受控入口 `creo_adopt_current_model`（受管副本形态）：inspect 只读探针登记身份证据（origin+sha256+live inspection+会话指纹，显示名不参与身份），apply 幂等复制当前会话状态到新受管模型并走完整保存验证闭环；原件不动，同源重复接管明确拒绝指向已有 model_id，失败按 unknown_outcome 保护并用 reconcile abandon_new 收尾。首批独立 part/sheetmetal，非 mm/带依赖/不健康特征拒绝；未放宽任何既有保护。2026-10-18 本机 12.4 实机全链路通过（含接管后编辑保存重载与原件不变证明）；Creo 13 外部环境与"未保存修改"场景未测，见验证记录。 第二阶段新增无盘范围已重入[当前台账](BACKLOG.md)，此处保留0.4.0交付事实。

## 2026-10-18：纳管预检收尾（开发分支）

| ID | 优先级 | 状态 | 目标版本 | 已验证范围 |
| --- | --- | --- | --- | --- |
| [BUG-071](work-items/BUG-071.md) | P1 | 已完成 | 未排期 | 预检来源/哈希/冲突/令牌写入统一收尾，登记最后发布；隔离故障回归和403项全量单元/开发检查通过。未合入main，FEAT-042/043实机因首次就绪超时仍未验收。见[本轮证据](validation/ADOPTION-COMPLETION-2026-10-18.md)。 |


## 2026-10-21：DEV-043 台账精简归档

本轮把已完成BUG的展示移出当前台账，不新增建模验收结论。下列BUG已随0.4.1交付；原台账详细叙述归档于此。

文档整理本身的验收范围如下，开发分支完成不表示已合入或发布。

| ID | 优先级 | 状态 | 目标版本 | 已验证范围 |
| --- | --- | --- | --- | --- |
| [DEV-043](work-items/DEV-043.md) | P2 | 已完成（开发分支文档整理） | 未排期 | 重读0.4.5新文档后精简台账与入口；完成项移出，未完成ID/状态/优先级/目标版本及37项无卡任务的唯一信息保留。当前104项含102未完成与2观察；本地链接、表格、数量、diff及283份历史验收原件哈希核对通过，独立审查通过。未改代码/版本，未连接Creo或重跑建模验收，未提交/合入/发布。 |

| ID | 优先级 | 状态 | 目标版本 | 问题与下一步 |
| --- | --- | --- | --- | --- |
| [BUG-073](work-items/BUG-073.md) | P2 | 已完成 | 0.4.1 | WorkBuddy黑盒：接管模型上 `sketch=40`/`"48"`/`features`段`RECT_40X30` 三种写法均 `Unknown feature label` 并正确回滚，仅 `aliases` 小写 `rect_40x30` 成功，与 `creo_loft` 数字串规范化规则矛盾。定位闭环：服务端序列化无缺陷（stdio整数保真，改写发生在LLM客户端对anyOf整数分支加引号）；`feature_id` 大小写敏感且 Creo 将特征名统一大写致 features/aliases 两段名不自洽；aliases 由 `remember()` 统一登记、快照初始为空是设计语义。已实现：schema 层 `SketchRef` 数字串规范化（六处 sketch 字段）+native digit 串/大小写回退/错误候选（`alias_entry` 统一元数据读取，顺带修复大写引用在执行段 null `.value()` 崩溃）。411项单测（新增5）、dev_check、实机四写法/错误候选/回滚（自建+接管模型）通过；WorkBuddy公开复验同轮通过（四写法/候选/重复标签/受管对照，回显归一为整数即规范化生效的公开证据）。实机loft对照未测（单测覆盖无回归）。随0.4.1交付，见[发布记录](validation/RELEASE-0.4.1.md)。 |

<details>
<summary>整理前的各轮当前安排（历史快照，包含尚未完成事项）</summary>

以下保留 `e3848f0` / 0.4.5 下各轮次的原叙述，其中“当前”“本轮”“未发布”等字样只属于原记录时点。涉及未完成事项，以[主台账](BACKLOG.md)和各工作卡当前摘要为准；不因收入本档案而转为完成。

- 2026-10-21 实施用户确认的[0.4.2 反馈首批处理计划](development/CREO10-0.4.2-FEEDBACK-PLAN-2026-10-21.md)：两份反馈原件归档（[feedback-0.4.2-creo10-2026-10-21](validation/feedback-0.4.2-creo10-2026-10-21/report.md)，主报告 SHA256 `59832348…`、构建侧 `72c1a634…`，均与原件逐字节一致）；新增 [BUG-076](work-items/BUG-076.md)（收养 16 MiB 预算阻断定位诊断，P1，首批交付 `ADOPTION_METADATA_BUDGET_EXCEEDED` 结构化诊断与四类超限隔离用例，不预定全量证据存储重构）；FEAT-006/008 补收养预检全阶段诊断与空窗口 `NO_CURRENT_MODEL` Python 结构化转换；FEAT-043/044 打开成功结果增加 `opened_session_model`；FEAT-008/023 README 汇总默认摘要接口用法。481 项单元+dev_check+实机（Creo 12.4 空窗口/open_file/正常预检，[验证记录](validation/BUG076-FEEDBACK042-2026-10-21.md)）；既有边界观察：inspect-only staging 无 MCP 清理路径（0.4.4 同行为，reconcile 另期）。DEV-027/030 已随 0.4.4 交付不在本轮范围；会话擦除、FEAT-045、装配接管/reconcile、旧 DLL 目录回收另期。已随 0.4.5 发版（main `9b7358d`，tag v0.4.5，[Release 419181692](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.4.5) 双附件核对一致，见[发布核对](validation/RELEASE-0.4.5.md)）。BUG-076/FEAT-043/044 转验收中，WorkBuddy 黑盒待复核。

- 2026-10-21 实施用户确认的[IMPROVEMENT 完善计划](development/CREO10-0.4.1-FEEDBACK-IMPROVEMENT-PLAN-2026-10-20.md)（0.4.3 后的下一项工作）：第二份构建侧反馈原件归档（[feedback-0.4.1-creo10-build-2026-10-20](validation/feedback-0.4.1-creo10-build-2026-10-20/report.md)，SHA256 `92590f8c…`）；**DEV-027 指纹稳定化**（保留 json.hpp 于清单、CRLF→LF 归一化算法 `sha256-repo-lf-v1`、缓存 algorithm/generation_key、旧缓存三形式等价复用、元数据先发布后写标记、派生世代键解非确定性冲突死锁）与 **DEV-030 vcvars64_env 放宽**（必须含大写三键、其余键接受并忽略、回写规范化三键）已实现，469 项单元+dev_check+实机迁移/翻转/重建/额外键构建全过；FEAT-044 补验收（钣金件 sheetmetal/displayed、显式 `.asm.4`=2 组件与 `.asm.6`=3 组件、PrintWindow 目视"WBOPEN_ASMV (启用的)"）；FEAT-023 补过期/跨实例 cursor/大内容分页。证据见[验证记录](validation/DEV-027-030-IMPROVEMENT-2026-10-21.md)，随 0.4.4 发版。旧计划补第二份报告修订（第 6 节）、CODING_STANDARD 明确构建依赖按实际引用确定。

- 2026-10-20 按用户要求先拉取 main cfcea22（0.4.2），实施[0.3.7 剩余计划](development/0.3.7-feedback-remaining-plan-2026-10-20.md)：BUG-057/074、BUG-058观测、FEAT-030首批及BUG-036查询修复已实现，458项单元、增量检查、SDK构建与7项SDK契约检查通过，另补齐仅有PID的历史身份恢复保护及九种子元数据公开复验，见[本轮验证记录](validation/FEEDBACK-0.3.7-IMPLEMENTATION-2026-10-20.md)。FEAT-023 capabilities已交付部分直接沿用。原生验收在会话门槛前失败，无建模作业或故障注入；用户授权仅清理指定三个进程的操作已逐项核对完成，后续未擅自处置进程或清保护。用户确认外部原始JSON/Creo9完整请求不在本机；剩余验收和原环境失败保持开放。同日16:10会话恢复后三项原生驱动串行通过：`tools.test_feedback037_modeling` 26作业全过（BUG-036约束求解+重载、FEAT-030两截面种子实机加载、BUG-019三入口size回显与别名冲突拒绝）、`tools/test_general.py` GENERAL_CORE_SUCCESS=1、ribs四组合保存重载全过（BUG-017本机对照），证据见验证记录新增小节；WorkBuddy黑盒与原环境复验仍开放。

- 2026-10-20 v0.4.1/Creo 10 反馈按用户确认[处理计划](development/CREO10-0.4.1-FEEDBACK-PLAN.md)开始实施：核对结论与归档见[反馈核对](validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md)（准确缺口是缺少 `.prt/.asm` 磁盘打开入口，属新增能力需求而非 0.4.1 回归；capabilities 顶层已有 version 字段）。登记 [FEAT-044](work-items/FEAT-044.md)（creo_open_file 磁盘检索显示，P1，当日实现并实机验收转验收中，随 0.4.2 交付）、[FEAT-045](work-items/FEAT-045.md)（外部装配只读检查，待规划）；FEAT-023 细化出[capabilities 分页实施卡](work-items/FEAT-023.md)（compact 默认+section/cursor、32KiB、600s 快照）；FEAT-006/008 补接管空窗口 NO_CURRENT_MODEL、顶层支持状态与拒绝稳定原因；FEAT-022 补 session_status 各分支 server_version。当日 WorkBuddy 黑盒 16/16 通过（[报告](validation/WORKBUDDY-0.5.0-open-file-2026-10-20.md)）；其遗留五项已跟进：version.py 定版 0.4.2（弃用开发期 0.5.0 编号）、缺件错误码/幂等键提示同步、接管 native 前缀拒绝转结构化 refusal_details（实机验证）、session_model_id 语义补写（FEAT-043）。本轮不扩展装配接管及 reconcile；同日另一份构建侧反馈（json.hpp 指纹清单、vcvars64_env 键集）不在计划范围，待后续登记。0.4.2 已交付 main（`24fc3d5`，tag v0.4.2，[Release 418039183](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.4.2) 双附件核对一致，见[发布核对](validation/RELEASE-0.4.2.md)）。

- 2026-10-19 WorkBuddy 公开黑盒复验新增 [BUG-073](work-items/BUG-073.md)（P2，现验收中）：同一接管模型上 `creo_extrude.sketch` 以整数 `40`、数字串 `"48"`、`features` 段大写名 `RECT_40X30` 提交均返回 `Unknown feature label` 并正确回滚，仅 `aliases` 段小写 `rect_40x30` 成功，与 `creo_loft` 公开的“整数 ID / 纯数字串即特征 ID”规则矛盾。回滚、revision 与几何均未受损，故列 P2。同日晚开发者定位闭环（服务端序列化无缺陷，改写发生在LLM客户端；native大小写敏感+Creo特征名大写化）并实现修复：schema 层六处 sketch 字段数字串规范化、native digit串/大小写回退与可用候选提示，顺带修复大写引用在执行段对 null 调 `.value()` 的崩溃；411项单测、dev_check 与实机四写法（自建+接管模型）通过；同日第三轮 WorkBuddy 公开复验通过（四写法/候选标签/重复标签保护/受管对照），随 0.4.1 交付，卡转已完成。同轮“判别联合数组参数在 ZCode 客户端被拒、开发者通道与 WorkBuddy 宿主同载荷成功”判定为调用方环境问题，不登记为服务缺陷。

- 现有模型纳管第二阶段：FEAT-042 无盘冻结快照接管、BUG-071 预检失败收尾、FEAT-043 只读会话枚举，FEAT-022 补重启指引。本轮按用户确认计划实施，保留0.4.0首阶段交付与未测边界；原反馈见[原件](validation/feedback-0.3.7-adoption-2026-10-18/report.md)。

- 2026-10-19用户转贴WorkBuddy无盘接管主链通过：revision0→1→2、24000→7152 mm³、保存重载、原件保留及幂等保护；后续过期拒绝、同身份续签确认、修改原件后副本仍20000 mm³/同哈希，以及独立快照abandon_new→abandoned/revision0→普通编辑拒绝与原件保留亦有通过报告，见[黑盒补录](validation/ADOPTION-WorkBuddy-2026-10-19.md)。外部clean和独立平板钣金接管亦通过（分别6000/2400 mm³、ready/revision1、保存重载与原件关联）。sheets指工程图图纸页，不作为钣金展开查询；钣金专有语义仍未验证。dirty接管亦通过（6750 mm³、35×20×10尺寸、5×5贯穿方孔、参数WB_DIRTY_CHECK=42.0逐项核对及保存重载）。装配/非毫米/外部依赖/含抑制特征拒绝与9模型/5页同快照遍历通过；BUG-072非毫米单位/体积摘要已修正，转P2验收中；FEAT-042/043保持验收中，关闭原件、真实再生失败和实际并发仍待验收。prepare的result.adopted=false修正已实现；续签摘要和放弃时省略null参数的指引已补文档，空值问题映射既有BUG-055；字段修正已通过406项单元、统一检查、8例隔离C++及匹配SDK构建。2026-10-19晚连接器重启（部署指纹一致）后开发者实机复验通过：BUG-072英寸inspect返回units="in"/volume_mm3=null（双层一致、毫米准入拒绝保持）；prepare full/compact顶层adopted=false、apply对照true、副本续作24000 mm³/revision2/保存重载verified、原件无盘保留。同轮记录一次-11连接事故（Creo停拉伸Dashboard模态叠加警告框循环，ESC取消后恢复，未结束Creo/未清unknown）；WorkBuddy公开复验仍待操作者执行。

- 0.3.7旋转与接管反馈的首阶段已随0.4.0交付；BUG-067～070已归档，FEAT-042因本次新增无盘范围重入验收。历史环境及未测事实见[0.4.0发布记录](validation/RELEASE-0.4.0.md)。

- 0.3.6 已由 [DEV-041](work-items/DEV-041.md) 交付（PR #11 合并 `ca105b9`，tag `v0.3.6` → `1f38069`，[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.6) 附件核对一致）：BUG-059/DEV-040 的恢复执行前拒绝修复、BUG-057 随版隔离诊断脚本 `tools/reproduce_toolkit_lock.py`、六份 0.3.5 反馈补录与台账重构；无 C++ 改动故无原生回归，未测范围见[版本记录](validation/RELEASE-0.3.6.md)。[BUG-057](work-items/BUG-057.md) 待原环境用诊断脚本取证，[BUG-058](work-items/BUG-058.md) 待实机定位 -11；BUG-059 修复的真实会话/并发验收未执行，继续保留联调限制及实际 unknown 保护。
- [FEAT-018](work-items/FEAT-018.md) 与 [FEAT-029](work-items/FEAT-029.md) 继续补验收。[BUG-056](work-items/BUG-056.md)/[DEV-036](work-items/DEV-036.md) 已完成，M2 已收尾；证据见[核实记录](validation/BUG-056-DEV-036-investigation-2026-10-17.md)和[WorkBuddy 验收](validation/DEV-036-WorkBuddy-acceptance-2026-10-17.md)。其他 unknown/recovery_pending 保护仍保留。
- 0.3.5 已由 [DEV-035](work-items/DEV-035.md) 交付，见[版本记录](validation/RELEASE-0.3.5.md)。最新七份反馈分别记录[安装与锁文件测试](validation/FEEDBACK-0.3.5-2026-10-17.md)、[Creo 10 文件层升级检查](validation/FEEDBACK-0.3.5-CREO10-2026-10-18.md)、[Creo 9 有限建模测试](validation/FEEDBACK-0.3.5-CREO9-2026-10-18.md)、[Creo 10 实机验收](validation/FEEDBACK-0.3.5-CREO10-2026-10-18-2.md)（BUG-054 六用例与 BUG-022/013 复测通过；弧方向 P1 见 FEAT-034）、[钣金第四轮回归](validation/FEEDBACK-0.3.5-SHEETMETAL-2026-10-18.md)（S1/S3/S5 四轮未修，S6/P3 新登记 BUG-060/061）、[曲面链路缺口](validation/feedback-0.3.5-surface-2026-10-18/report.md)（FEAT-039 曲面算子、BUG-062 回转草图不可就地编辑）和[建模能力边界](validation/FEEDBACK-0.3.5-CAPABILITY-2026-10-18.md)（虹膜机构全量重建：BUG-049 扩展至不相交多环，新登记 BUG-063 非原点轴阵列静默错误、BUG-064 基准面草图硬失败、BUG-065 轴求交退化、BUG-066 预览失真）。BUG-054/055 在外部 Creo 9 与 Creo 10 的已测范围通过；种子、筋、装配约束、弧方向、钣金链路、纯曲面法及多环/偏心阵列仍有失败或缺口反馈；各环境的已测和未测范围见[兼容矩阵](COMPATIBILITY.md)，不推定该环境整体通过。

</details>


## 2026-11-07：DEV-073 归档与历史进展

本节仅为日期档案，不是当前任务入口。以下进展保留原日期与当时结论；部分“已发布”声明在本地集成快照中写早，交付事实以对应发布核对为准。当前状态只看 [BACKLOG](BACKLOG.md)。本轮纯文档复核，未重新运行历史测试。

### 本轮完成项

| ID | 优先级 | 状态 | 目标版本 | 完成摘要与证据 |
| --- | --- | --- | --- | --- |
| [BUG-111](work-items/BUG-111.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.6（已发布） | 选集语义和几何重合/交叠已定因；诊断与文案修正已发布；历史范围与证据见工作卡。 |
| DEV-055 | P2 | 已完成（2026-11-07 复核归档） | 未排期 | BACKLOG 明示 2026-11-02 已完成；四头文件已加入并在本机 SDK 核对；无独立卡；历史范围与证据见工作卡。 |
| [BUG-077](work-items/BUG-077.md) | P0 | 已完成（2026-11-07 复核归档） | 0.4.7 | 注册表治理及迁移/收养主线已交付，外部原环境已验证；健康会话 accept 两动作各 3/3；历史范围与证据见工作卡。 |
| [DEV-060](work-items/DEV-060.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.2（已发布） | 归档/对账任务随 0.11.2 发布；BUG 子卡余项不属 DEV-060；历史范围与证据见工作卡。 |
| [DEV-062](work-items/DEV-062.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 归档/登记任务随 0.11.3 发布；BUG/FEAT 子卡余项另列；历史范围与证据见工作卡。 |
| [BUG-104](work-items/BUG-104.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 0.17.3 实机 15/15 完成补基线、拒绝及 adopted_live；旧检查点样本和失败注入属补证；历史范围与证据见工作卡。 |
| [FEAT-056](work-items/FEAT-056.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 0.17.3 随机与标签色板实机成功，核心能力完成；80 组件夹具归 FEAT-052；历史范围与证据见工作卡。 |
| [BUG-112](work-items/BUG-112.md) | P1 | 已完成（2026-11-07 复核归档） | 0.15.0+ | ProQuiltInit 返回码修复与面积来源保护已交付；偏置计量实机范围由 FEAT-039 承接；历史范围与证据见工作卡。 |
| [DEV-064](work-items/DEV-064.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.4（已发布） | R12 批已随 0.11.4 发布、附件核验；原件缺失属各子卡；历史范围与证据见工作卡。 |
| [BUG-096](work-items/BUG-096.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | 新零件/装配失败清理 S1–S4 实机断言通过；历史范围与证据见工作卡。 |
| [BUG-097](work-items/BUG-097.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | L1/L2 斜面草图修复已于 0.11.1 本机实机通过；历史范围与证据见工作卡。 |
| [BUG-099](work-items/BUG-099.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | 失败 worker 含未提交代码，本树源码不可复现，源码归因已定；历史范围与证据见工作卡。 |
| [BUG-100](work-items/BUG-100.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.1 | 背靠背/并发 busy 与预约释放 0.11.1 实机复验通过；历史范围与证据见工作卡。 |
| [BUG-092](work-items/BUG-092.md) | P2 | 已完成（2026-11-07 复核归档） | 0.10.1 | 驱动退出后 server.py 残留 0，实机尾项已收口；历史范围与证据见工作卡。 |
| [BUG-093](work-items/BUG-093.md) | P2 | 已完成（2026-11-07 复核归档） | 0.10.1 | 五非法例及恢复编辑实机通过，体积同源证据补齐；历史范围与证据见工作卡。 |
| [BUG-089](work-items/BUG-089.md) | P1 | 已完成（2026-11-07 复核归档） | 0.8.2 | 版本/摘要修复、防复发闸门与远端正式附件核对已完成；历史范围与证据见工作卡。 |
| [BUG-087](work-items/BUG-087.md) | P1 | 已完成（2026-11-07 复核归档） | 0.7.2 | 重复第二参照修复 0.7.2 已发布并六例实机通过；后续 T06 属 BUG-064 顺序调查；历史范围与证据见工作卡。 |
| [BUG-086](work-items/BUG-086.md) | P1 | 已完成（2026-11-07 复核归档） | 0.7.2 | PS 5.1 stderr 判断修复、回归与真实新目录安装验证通过；历史范围与证据见工作卡。 |
| [FEAT-034](work-items/FEAT-034.md) | P1 | 已完成（2026-11-07 复核归档） | 0.8.0/0.8.3/0.10.0 | BUG-093 后续五非法例及恢复编辑实机通过，原卡首页滞后；历史范围与证据见工作卡。 |
| [DEV-061](work-items/DEV-061.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.2 | 种子包仓库摘要闸门已随 0.11.2 交付；远端附件人工核验属于发布流程；历史范围与证据见工作卡。 |
| [DEV-050](work-items/DEV-050.md) | P2 | 已完成（2026-11-07 复核归档） | 0.7.2 | 默认 900 秒配置已实现，后续多版 dev_check 全量记录已覆盖 T08 目标；历史范围与证据见工作卡。 |
| [DEV-073](work-items/DEV-073.md) | P2 | 已完成（独立本地文档交付，未合 main） | 未排期 | BUG 分类复核与入口精简、历史字节及链接/状态检查、独立审查完成；未做产品/实机验证，本批仅本地提交。 |

### 存量无独立工作卡的登记

这些 ID 早于工作卡规范，保留原登记和证据；本批按用户要求仅新增 DEV-073，不批量补卡。当前剩余仍在 BACKLOG，一旦实施可在既有相关卡中接续。

<a id="legacy-dev-055"></a>

**DEV-055（原登记）**：`tools/generate_constants.py` 的 HEADERS 已包含 `Probbl.h`、`ProTrim.h`、`ProStdSection.h`、`ProMerge.h`（轮1 `efb0676` 已加入），供后续三曲面操作探测使用；2026-11-02 复核四头文件在本机 Creo 12.4.0.0 SDK `protoolkit/includes` 均存在。

<a id="legacy-bug-003"></a>

**BUG-003（原登记）**：检查倾斜草图的尺寸是否正确：用 30° 矩形拉伸 4 mm，核对体积是否为 800 mm³。还要测试尺寸编辑、保存后重新打开，以及失败时能否恢复修改前的模型。 [0.5.2反馈映射](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r3-12)：T05以倾斜10×20×4=800独立夹具作受影响对照，不关闭本项全部历史范围。

<a id="legacy-bug-004"></a>

**BUG-004（原登记）**：在实验环境检查 Creo 12 的两截面种子。先核对 Blend 引用、对象句柄和种子文件身份，再对比直线、平滑及三截面情况。完成要求包括几何、尺寸编辑和保存后重新打开均正确。

<a id="legacy-bug-015"></a>

**BUG-015（原登记）**：t30_probe 中，对 body id=52 做 translation=[0,0,15]，特征创建后保存失败，干净模型的对照测试却成功。用查询得到的真实 body ID，分别测试 group、pattern、shell 与 transform 的组合，查清保存阶段的问题。成功时体积不变、位置正确且能重载；失败时保留保存点和 revision，并检查模型是否仍可用。返回字段的含义另由 BUG-012 处理。

<a id="legacy-bug-011"></a>

**BUG-011（原登记）**：通道异常时，状态查询有时给空错误或仍显示旧 ready。已有会话首次查询还出现 building_worker/connected=false，跨日出现 checking 不结束，建模返回 connect=-4。需要说明结果来自实时检查还是旧快照，并显示验证时间和是否过期；查询、提交都应在规定时间内返回明确原因。TimeoutExpired/launch_reserved 的新反馈尚未复测，关联 FEAT-001；异常通道恢复与未知任务保护按现行恢复契约处理。

<a id="legacy-bug-012"></a>

**BUG-012（原登记）**：transform 失败后，几何和 revision 没变，模型却被标为 failed；0.3.1 还有成功作业返回 rollback_succeeded=false，履带报告也出现同样误读。0.3.5/Creo 10 实机再现：新建零件失败（自交轮廓）时 inspection=null、rollback_succeeded=false 并残留 failed/revision 0 的登记与 .prt.1——新件无检查点可回滚是事实，但 false 易被误读为"回滚失败"，反馈建议改 null/not_applicable；另守卫触发时作业级 toolkit_code=-1 属异常路径汇总码（disconnect_code=0、通道健康），建议与真实 Toolkit 故障区分。需要分别说明回滚未尝试、成功、失败和无法确认时的含义，以及模型还能否使用，并检查保存点和旧字段兼容性。false 本身不能证明模型损坏，unknown_outcome 保护也不能直接清除。关联 FEAT-018。

<a id="legacy-bug-016"></a>

**BUG-016（原登记）**：solidify(cut) 用 z=30、positive 侧的基准面裁剪 z=20..40 的实体后，体积和 bbox 未变，却显示特征成功。先查清 side、pull_direction 和引用是否适用，再对比两侧裁剪并检查重载。应区分允许不改材料的操作、无效输入和真正切除，不能把所有零变化都判失败。

<a id="legacy-bug-018"></a>

**BUG-018（原登记）**：旧报告中 export/dump_tree/update_sketch_geometry 的结果重复；0.3.1 和 0.3.2 的失败计划又只返回 null 或空 operations。每个请求应对应一条带序号的结果，说明已执行、已回滚、失败、未执行或结果未知，并带上文件、特征和参数。0.3.5 钣金回归中 5 次失败计划仍均返回空 operations 数组，调用方无法知道哪些已成功、只能整批重发。核对成功及失败时的数量、顺序和失败位置；operation_outcomes 的接口建议仍待评估，不能据此自动重跑后半段。关联 FEAT-006。 [0.5.2反馈R1 §4.4](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r1-12)续报重复；T02按[DEV-047接口基线](work-items/DEV-047.md#interface-baseline)固定零基index、execution_status/effect_status及每输入一结果，离线实现完成（[T02记录](development/DEV047-T02-ACCEPTANCE-2026-10-26.md)），实机与集成由T13收口。

<a id="legacy-bug-010"></a>

**BUG-010（原登记）**：旧报告中 drawing_view_update(scale=2) 失败，但 0.3.1 已成功把 v_front 从 1 放大到 2。还要查清两次测试的差异，测试位置更新、图纸保存重载和 revision；失败时应保留原图。  本次只调整为剩余验收，不认定位置更新和保存重载已通过。

<a id="legacy-feat-002"></a>

**FEAT-002（原登记）**：遇到 DLL 提示等需要人工处理的情况时，说明正在等什么。测试等待超时后，任务上下文是否保留、相关模块能否清理。

<a id="legacy-feat-003"></a>

**FEAT-003（原登记）**：支持并测试带单位的关系式，例如 `8[mm]`。确认它能真实驱动尺寸、带动相关参数变化，并保留用户对单位的检查设置。

<a id="legacy-feat-005"></a>

**FEAT-005（原登记）**：revision 冲突时，返回 model_id、current_revision 和 expected_revision，让调用者看到哪个版本不一致。继续拒绝过期请求，拒绝时不创建 job。 **2026-11-07**：`generic_bridge` 过期 revision 拒绝文本改为 `Stale revision: model_id=… current_revision=… expected_revision=…; no job was created`；`tests/test_registry_io.py` 精确断言三字段。纯 Python、无原生依赖。

<a id="legacy-feat-011"></a>

**FEAT-011（原登记）**：增加复合轨迹、可变截面和螺旋扫掠，分别明确范围并测试。

<a id="legacy-feat-013"></a>

**FEAT-013（原登记）**：增加剖视、局部放大、装配图和 BOM（物料清单），逐项检查模型变化后图纸能否同步更新。

<a id="legacy-feat-015"></a>

**FEAT-015（原登记）**：评估模具、NC 加工和仿真能力，先选一个最小场景做完整流程，暂不承诺支持全部模块。

<a id="legacy-feat-016"></a>

**FEAT-016（原登记）**：增加翼型凸度和 NACA 四位数系列，检查能否通过原生参数编辑，并验证实际几何。

<a id="legacy-feat-017"></a>

**FEAT-017（原登记）**：分别复现并测试布尔、曲面和拔模中尚未测过的用法，再决定扩大哪些支持范围。

<a id="legacy-feat-021"></a>

**FEAT-021（原登记）**：设计受控取消任务，先说明 queued、running、unknown_outcome 各能否取消，再检查执行器和模型状态。不能安全中断时说明原因。取消后要检查最终状态、保存点、revision、锁和下一次任务是否正常；不能把杀 worker 或清 pending_job 当作取消成功。与未知结果恢复分别验收，任务状态名称不表示当前已有排队能力。

<a id="legacy-feat-024"></a>

**FEAT-024（原登记）**：lookup_constants 没找到结果时，说明没有匹配，并提示可用前缀。测试不存在的前缀、空条件、合法前缀及旧返回规则；保留正常命中的行为。当前按体验改进处理，不直接把空字典认定为缺陷。

<a id="legacy-feat-025"></a>

**FEAT-025（原登记）**：评估 creo_loft 在回调未就绪时，能否用 2～6 截面种子完成部分操作。先说明支持哪些截面和模式、怎样保留模型身份，再检查已有特征、编辑、revision、保存重载和失败恢复。种子能新建零件，不代表能追加到已有零件；不自动加载 DLL 或改变策略，也不预先承诺实现成本低。

<a id="legacy-feat-026"></a>

**FEAT-026（原登记）**：提供 create_feature_tree 能运行的最小 dict 示例，说明 dump XML 能否转换或导入。先让示例建模、参数、几何和重载通过，非法树能指出问题元素，再评估导出后重新导入。无效示例失败不能证明工具不可用。

<a id="legacy-feat-027"></a>

**FEAT-027（原登记）**：说明删除实体后是否保留 label，以及何时可以安全释放或重新绑定。测试创建、删除、同名重用和旧引用、历史作业、revision 的关系，防止旧别名误指新对象。先说明现有规则，再评估可选接口，不默认允许覆盖。 [0.5.2反馈R3 §6.3](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r3-20)归T08/0.7.0子项；[共享基线](work-items/DEV-047.md#interface-baseline)固定删除墓碑、抑制保留身份，禁止旧别名重新绑定。T08 已实现墓碑登记与旧标签新建/引用拒绝（专项与回归见[记录](development/DEV047-T08-ACCEPTANCE-2026-10-26.md)），[T13](development/DEV047-T13-ACCEPTANCE-2026-10-26.md) 在 Creo 12.4 实机验证删除、墓碑登记与删除后用旧标签建新草图被拒。剩余：显式释放/重绑定接口与跨版本历史作业核对，仍待规划，不默认允许覆盖。

<a id="legacy-feat-028"></a>

**FEAT-028（原登记）**：create_plate为一次性产物，未注册为可继续编辑的模型；[0.4.7黑盒](validation/WORKBUDDY-0.4.7-2026-10-21.md)再次确认1000mm³成功但无model_id，属既有边界。评估是否返回 one_shot/registered 或支持可选注册。若增加后续编辑，须检查列表和 inspect 能找到模型、revision 正确、编辑和保存重载通过，失败后可恢复。计数问题仍由 BUG-014 处理。

<a id="legacy-feat-038"></a>

**FEAT-038（原登记）**：提供不建立 Toolkit 连接的安装自检路径：校验部署产物与配置一致性（常量表、执行器与源码指纹、种子哈希与清单、protk/loader 注册文件），让按约束停止 Toolkit 连接的受限环境也能确认安装正确性，不必冒卡死风险连 Creo。先确定自检覆盖哪些项、怎样判定"一致"，以及自检通过与实机就绪的关系（自检通过不等于通道可用）。来源见[Creo 10 反馈](validation/FEEDBACK-0.3.5-CREO10-2026-10-18.md)，关联 FEAT-022。

<a id="legacy-bug-020"></a>

**BUG-020（原登记）**：STEP 导出会留下 *_out.log.N。需要说明哪些文件是交付产物、哪些是诊断附件，只清理本作业生成的副产物。检查 STEP 仍有效、用户文件未受影响。文件清理由开发者检查，MCP 黑盒只验证返回的文件说明。

<a id="legacy-dev-003"></a>

**DEV-003（原登记）**：整理 C++ 的执行上下文、模块接口和资源由谁创建、释放，再用受影响的 SDK 构建并运行原生测试。

<a id="legacy-dev-004"></a>

**DEV-004（原登记）**：在 DEV-003 完成后，让各模块可以独立编译，并整理原生测试目录。检查构建缓存、安装、保存重载和失败回滚。

<a id="legacy-dev-005"></a>

**DEV-005（原登记）**：按工具和参数用法记录本机哪些测过、哪些没测，并注明真实环境，同步安装和能力说明。其他环境收到具体反馈再补；不要求双版本验收，也不能拿“82 工具测过”的汇总代替每种用法的兼容性测试。

<a id="legacy-dev-006"></a>

**DEV-006（原登记）**：补测会话、中断、真正并发、倾斜草图、两截面和 Creo 12 直接混合。0.3.1 还缺回调就绪的 loft、有效 UDF 和元素树、种子 directory/archive、JPEG 和图纸 PDF 的成功用例。记录完整输入、ID、几何、编辑、重载和回滚。Creo 9 的种子、筋和放样冒烟测试要有实际环境再做；新工具还须经真实 stdio MCP 测试空值、省略、非法字段、错误传递及 inspect→apply。模拟协议、原生和 WorkBuddy 结果分别记录，不能用输入被拒绝或工具总数代替成功用例，也不新增双版本发布门槛。

<a id="legacy-dev-007"></a>

**DEV-007（原登记）**：与 DEV-006 共用一份回归清单，在发布候选上执行，避免维护两套记录。包括 0.3.3 提出的 Creo 9 最小冒烟，以及新工具的空值、省略和非法字段 MCP 调用检查，逐环境标明已测、未测。外部编译通过或一个孔成功，不能代表全部运行时可用；本地 Python 直调也不能代替 MCP 协议测试。

<a id="legacy-dev-008"></a>

**DEV-008（原登记）**：查清旧清单第 5/6/7/9 项分别来自哪里、现在归哪个任务，补上对照关系。来源是 NEXT_STEPS_025 的“完善建议 5”。

<a id="legacy-dev-009"></a>

**DEV-009（原登记）**：按模块分别整理代码格式，每批完成后做回归检查，不自动增加历史问题的豁免项。2026-10-14 的历史统计为 67 条 Ruff 问题、36 个 Python 和 14 个 C++ 文件，见[历史记录](BACKLOG_COMPLETED.md)。

### 原台账日期进展（截至基点 1cf9d3f）

#### 原台账开头

本轮开发：无（[DEV-072](work-items/DEV-072.md) 已于 2026-11-07 随 0.17.4 交付；下一批按下方未完成条目安排）。

建立：2026-10-13；最近更新：2026-11-07。当前服务／源码版本为 **0.17.4**（PATCH：[DEV-072](work-items/DEV-072.md) 0.17.1 反馈修复批——板厚回执 API 来源说明、几何选边有界最近候选、空装配预览判定、gh 失败转官方 API 附件下载；DEV-070/FEAT-007/FEAT-039/FEAT-058 台账回填；公开工具仍 **100**；本次交付的核对记录见 [RELEASE-0.17.4](validation/RELEASE-0.17.4.md)）：[版本说明](RELEASE_NOTES_0.17.4.md)。上一已发布版本 **0.17.3**（PATCH：[DEV-071](work-items/DEV-071.md) 反馈修复批——miter 收尾公开投影、更新检查 `force` 与网络预算、草图求解阶段/模式原因、再生失败特征状态、offset 文案统一；同批附 BUG-032/FEAT-010/BUG-104/BUG-105/FEAT-056 实机验证；公开工具仍 **100**；记录见 [RELEASE-0.17.3](validation/RELEASE-0.17.3.md)）：[版本说明](RELEASE_NOTES_0.17.3.md)。上一已发布版本 **0.17.2**（PATCH：实机验证批——[BUG-115](work-items/BUG-115.md) 准入实机复验、[BUG-108](work-items/BUG-108.md)/[BUG-110](work-items/BUG-110.md)/[BUG-102](work-items/BUG-102.md) 复跑、[FEAT-004](work-items/FEAT-004.md) 与 [FEAT-058](work-items/FEAT-058.md) R03 实机回归；公开工具仍 **100**，无产品代码变更；记录见 [RELEASE-0.17.2](validation/RELEASE-0.17.2.md)）：[版本说明](RELEASE_NOTES_0.17.2.md)。上一已发布版本 **0.17.1**（PATCH：[BUG-115](work-items/BUG-115.md) 同计划 fill→trim→thicken 准入与可执行替代、[FEAT-005](#legacy-feat-005) 过期 revision 回执补齐 `model_id`/`current_revision`/`expected_revision`；公开工具仍 **100**，无新增工具；记录见 [RELEASE-0.17.1](validation/RELEASE-0.17.1.md)）：[版本说明](RELEASE_NOTES_0.17.1.md)。上一已发布版本 **0.17.0**（MINOR 功能批：[FEAT-058](work-items/FEAT-058.md) 首壁可选 `origin` 定位与保持原点的改型（实机 112/112）、[FEAT-014](work-items/FEAT-014.md) `sheetmetal_flange.edge` 几何选边 `edge_geometry`（实机 17/17）；公开工具仍 **100**；记录见 [RELEASE-0.17.0](validation/RELEASE-0.17.0.md)）：[版本说明](RELEASE_NOTES_0.17.0.md)。上一已发布版本 **0.16.1**（PATCH：0.13.0/0.14.0 反馈修复批——R01 偏置距离闸门、R02 定向复现驱动、R03 板厚几何兜底、R04 查询协议补证、R05 旋转矩阵准入诊断、R13 失败清理事务归因、R09/R12 实机验收；公开工具仍 **100**；记录见 [RELEASE-0.16.1](validation/RELEASE-0.16.1.md)）：[版本说明](RELEASE_NOTES_0.16.1.md)。上一已发布版本 **0.16.0**（MINOR 功能批：FEAT-014 四壁盒子经 `miter_cuts`（`PRO_E_SMT_MTR_CUTS`，BLIND 数值）实机建成，`adjacent_bend_ends` 仅在显式传 `miter_cuts` 时放行；FEAT-004 尺寸归属/可编辑性与旧值守卫；公开工具仍 **100**；记录见 [RELEASE-0.16.0](validation/RELEASE-0.16.0.md)）：[版本说明](RELEASE_NOTES_0.16.0.md)、[FEAT-014](work-items/FEAT-014.md)、[FEAT-004](work-items/FEAT-004.md)。上一已发布版本 **0.15.1**（PATCH：BUG-111 发布后修正——撤销 `keep_original` "每批 ≤4 副本"旧建议、选集诊断计数改读巡检实际字段；公开工具仍 **100**；2026-11-06 合入 `main`、标签 `v0.15.1`、四附件发布并远端核对，记录见 [RELEASE-0.15.1](validation/RELEASE-0.15.1.md)）：[版本说明](RELEASE_NOTES_0.15.1.md)、[工作卡](work-items/BUG-111.md)。上一已发布版本 **0.15.0**（MINOR 反馈收口批：0.13.0 四件反馈的稳定性/回执/契约、`creo_get_job wait_seconds` 长轮询与 connect 阶段计时；公开工具仍 **100**；2026-11-06 合入 `main`、标签 `v0.15.0`、四附件发布并远端核对，记录见 [RELEASE-0.15.0](validation/RELEASE-0.15.0.md)）：[版本说明](RELEASE_NOTES_0.15.0.md)、[工作卡](work-items/DEV-069.md)。上一已发布版本 **0.14.0**（PATCH 性质的回执与预览补证批：`extrude_depth` requested/effective 回执（W05）、只读预览入口与失败编辑回滚实机（W06）、`surface_trim` 偏置 Thin 树复测（`offset_mm`/`offset_side` 门禁保持），公开工具仍 **100**；2026-11-06 合入 `main`、标签 `v0.14.0`、四附件发布并远端核对，记录见 [RELEASE-0.14.0](validation/RELEASE-0.14.0.md)）：[版本说明](RELEASE_NOTES_0.14.0.md)、[工作卡](work-items/FEAT-039.md)。上一已发布版本 **0.13.0**（MINOR 功能批，公开 `creo_surface_trim` 与 `creo_project_curve` 至 99（2026-11-04 实机 P3/S04 通过后解除门禁），`creo_surface_offset` 加入后至 **100**（2026-11-05 双侧实机），并补齐曲面链 S03/S05/S07/S08 与 W01 的实机证据；2026-11-05 已合入 `main`（合并提交 `d90d28e`）、标签 `v0.13.0`、四附件发布并远端核对通过，记录见 [RELEASE-0.13.0](validation/RELEASE-0.13.0.md)；更前一已发布版本 **0.12.1**（DEV-068 README 改版与离线测试隔离，PATCH；公开工具 97）；[交付核对](https://github.com/wudahua/MCP_CREO_MechDog/pull/12)）：[版本说明](RELEASE_NOTES_0.12.1.md)、[发布记录](validation/RELEASE-0.12.1.md)、[工作卡](work-items/DEV-068.md)。前一交付版本为 **0.12.0**（FEAT-058 原生矩形钣金首壁与就地改型，MINOR；公开工具 95→97；本机 Creo 12.4 实机 67/67）：[版本说明](RELEASE_NOTES_0.12.0.md)、[发布记录](validation/RELEASE-0.12.0.md)、[工作卡](work-items/FEAT-058.md)。前一交付版本 **0.11.7**（R13 后续定因与实机补证批，PATCH；公开工具仍 95；本机 Creo 12.4 实机 C0—C6 定因，BUG-108/BUG-110 仍开放）：[版本说明](RELEASE_NOTES_0.11.7.md)、[发布记录](validation/RELEASE-0.11.7.md)、[验收摘要](development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。前一交付版本 **0.11.6**（DEV-065，0.11.5 第十三轮反馈批 R13，PATCH；公开工具仍 95；含本机 Creo 12.4 实机）：[版本说明](RELEASE_NOTES_0.11.6.md)、[发布记录](validation/RELEASE-0.11.6.md)、[工作卡](work-items/DEV-065.md)。前一交付版本 **0.11.5**（DEV-002 第三批包化，PATCH；公开工具仍 95；本批离线交付，T5 实机待验）：[版本说明](RELEASE_NOTES_0.11.5.md)、[发布记录](validation/RELEASE-0.11.5.md)。前一交付版本 **0.11.4**（DEV-064 R12）：[版本说明](RELEASE_NOTES_0.11.4.md)、[发布记录](validation/RELEASE-0.11.4.md)。前一交付版本 **0.11.3**（DEV-062 0.11.0 第十一轮反馈批 PATCH：旧检查点 `refresh_baseline` 补基线、零变更失败 `ready` 与 `ack_no_mutation` 注册表恢复、色板唯一标签键与 `random:true`；公开工具仍 95）：[版本说明](RELEASE_NOTES_0.11.3.md)、[发布记录](validation/RELEASE-0.11.3.md)。前一交付版本 **0.11.2**（DEV-060 0.10.0 第十轮反馈批 PATCH：草图 `profile.weldability` 风险标记与拉伸失败簇内间隙归因、draft `requested_flip`/`effective_flip` 与 `draft_failure`、孔 `depth_basis` 三键、种子摘要仓库级闸门；公开工具仍 95）：[版本说明](RELEASE_NOTES_0.11.2.md)、[发布记录](validation/RELEASE-0.11.2.md)。前一交付版本 **0.11.1**（DEV-053 0.10.0 晚间反馈批 PATCH：失败模型清理与同名复用、斜面草图修复、三点定面、草图显式容差、作业阶段上报、结果有界回执与分页、背靠背提交竞态；公开工具仍 95）：[版本说明](RELEASE_NOTES_0.11.1.md)、[发布记录](validation/RELEASE-0.11.1.md)。前一交付版本 **0.11.0**（FEAT-052 装配按零件族上色，MINOR，公开工具 94→95）：[版本说明](RELEASE_NOTES_0.11.0.md)、[发布记录](validation/RELEASE-0.11.0.md)、[工作卡](work-items/FEAT-052.md)。0.11.0 实机（2026-11-01，Creo 12.4.0.0，run `assembly_appearance_live_20261101T060336Z558b3546`）：80 组件/12 族夹具 28/28 检查通过（自动分族、显式合族、第三色板、放置保色、两个故意失败计划回滚、源零件 SHA256 不变、保存重载全 true），装配 pipeline 与 T07 预览回归通过；仍开放：WorkBuddy 黑盒、Creo 9/10、busy/并发实机。前一交付版本 **0.10.1**（DEV-053 PATCH，公开工具仍 94）：[版本说明](RELEASE_NOTES_0.10.1.md)、[发布记录](validation/RELEASE-0.10.1.md)；BUG-092/BUG-093 已随版实机收口（行状态本次同步修正）。前一版 **0.10.0**（DEV-052 N13 集成批次：FEAT-051 round/chamfer/draft 逐操作体积差与方向/引用应用回报、FEAT-008 草图结果 `entity_ids`、FEAT-014 折边邻接折弯端 `adjacent_bend_ends` 拒绝语义，含 FEAT-035/T12 盲孔 tip 口径、FEAT-034/T02 编辑弧回显修复、FEAT-008/T09B 中心线计数修复与 BUG-049 端点诊断，MINOR 性质，公开工具仍 94）：[版本说明](RELEASE_NOTES_0.10.0.md)、[发布验收记录](validation/RELEASE-0.10.0.md)。0.10.0 实机（2026-10-31 第二轮，Creo 12.4.0.0）：N04 七夹具、N06 邻接拒绝终验（RUN PASSED）、N08/N09/N10 六例、N11 含人工图像复核通过，N07 创建 5/5+编辑 3/3 通过（`illegal_dir_zero` 反例待查 BUG-093），N12 发布时 large 每类 n=2，发布后补轮每类 n=3（small 每类 n=3；两轮分开统计）；仍开放：四壁/relief 材料几何、`end_trim_mm` 语义、T05/T06/T08C 缺件、BUG-049 原案、BUG-088 I/O 根因、BUG-090 Creo 10 定向编译、BUG-091 根因、BUG-092/BUG-093。0.9.0 实机：T03 板厚 5/5 通过（1 mm 壁零件厚度读数 1.0）、T13 两段式回导通过、T05 第三道折边定因为“附着边端部与既有折弯相邻”、T09D 出基准；0.8.3 补证 T02 4/4、T06 9/9、T07 3/3、T08A 4/4；0.8.4 修复首壁阻断并补 T03 五组；0.8.5 交付折边方向与钣金 add 边界及 T08B/T09A/T09B/T12 证据。0.8.3—0.9.0 的历史结论保留各自版本归属；WorkBuddy 与 Creo 9/10 未验。

- **2026-11-03 DEV-065 / R13 归档与登记：** `C:\Users\Administrator\Downloads\0.11.5` 五份原件**逐字节归档 5/5**（长度 9 691 / 6 539 / 12 756 / 11 646 / 5 998 B，SHA256 与整文件字节序列比对均一致，[manifest](validation/feedback-0.11.5-2026-11-03/manifest.json)、[逐章映射](validation/feedback-0.11.5-2026-11-03/MAPPING.md)），与 `feedback-0.10.0-2026-10-31`/`feedback-0.10.0-2026-11-01`/`feedback-0.11.0-2026-11-01`/`feedback-0.11.1-2026-11-02` 并存不合并。新登记 [DEV-065](work-items/DEV-065.md)、[BUG-109](work-items/BUG-109.md)（`verify_model` 无子阶段归因）、[BUG-110](work-items/BUG-110.md)（装配失败无恢复动作）、[BUG-111](work-items/BUG-111.md)（`geometry_transform` 第 5 副本与旋转越界）、[DEV-066](work-items/DEV-066.md)（`tools/` git 硬依赖，仅登记），并补 BUG-108/FEAT-054/FEAT-055/BUG-082/BUG-101/BUG-102/FEAT-007/BUG-034/BUG-017/BUG-094/BUG-095 增量。按用户 2026-11-03 决定，本批只做 **A 组四项**（阶段归因、平移判据、装配恢复、旋转范围），**B 曲面链、C 工具链与文档、D 诊断小项只登记不实现**。台账 164→169 行，分类按新增与状态迁移调整（开发中 4→9、待复现 24→23、待规划 42→43）。四项均已离线实现：全量 2241 项单测通过（起点 2196）、`tools/test_unit.py` `success=true`、`dev_check --work-item 0.11.5-feedback-r13` `success=true`、`bridge.py build` exit 0（执行器 `0f556504…`、源码指纹 `cd22b563…`）。计划见 [R13 实施计划](superpowers/plans/2026-11-03-0.11.5-feedback-r13-plan.md)。**以上为登记与离线实现轮时点记录。** 当前状态（2026-11-03 对账）：用户当日授权启动会话，四项夹具已在本机 Creo 12.4 实机执行；版本裁定为 **0.11.6** 并已合入 `main`、打标签 `v0.11.6`、发布（[发布记录](validation/RELEASE-0.11.6.md)）；Creo 9/10 与 WorkBuddy 仍未测。发布不关闭保留子项：BUG-109 卡死根因与真实停滞未验、BUG-108 `accepted_rigid=true` 仅单测、BUG-110 `ack_failure` 成功路径仅单测、BUG-111 第 5 副本未定因。

本页只安排未完成工作和单列的历史观察；完成结论见[完成档案](BACKLOG_COMPLETED.md)。各固定 ID 只出现一条任务记录，工作卡和原始证据保存详细输入、历史过程与已测范围。

#### 当时安排

- **2026-11-07 反馈修复批（0.17.4，DEV-072 离线实现，未连接 Creo）：** 0.17.1 三件反馈的离线增量已交付：① 板厚回执保留原生 API 字段，新增 `thickness_api_scope`/`thickness_api_reason`/`thickness_fallback_source`（resize 为 loaded 对应字段），权威判据仍为有来源的 `thickness_validation`；② `sheetmetal_flange.edge` 失配时附最多五条最近直线边候选（ID、毫米端点、最佳无向配对误差），严格唯一匹配与容差不变；③ 空装配/空零件预览统一 `skipped_no_geometry`，查询失败仍走原预览路径；④ [tools/check_release_assets.py](../tools/check_release_assets.py) 在 gh 缺失/失败/超时/资产不全时转官方 GitHub API 精确 tag 下载，仍只认四个安全文件名并校验 sidecar；⑤ DEV-070/FEAT-007/FEAT-039/FEAT-058 台账回填与发布规范逐 ID 核对。三件原件逐字节归档 3/3（[映射](validation/feedback-0.17.1-2026-11-07/MAPPING.md)）。离线快照 2744 项通过；合并 0.17.3 后组合源码全量 **2762 项、0 失败、0 错误**，`dev_check` `success=true`（`7390f4b`、dirty=false、指纹 `8fce4d00…`），`bridge.py build` 原生组合编译通过，独立审查通过（阻塞项仅为记录一致性，已修正）。**未验证**：涉及原生诊断的 Creo 实机/保存重载（本批未连接 Creo）、真实远端附件下载（发布后核对见 [RELEASE-0.17.4](validation/RELEASE-0.17.4.md)）。见 [工作卡](work-items/DEV-072.md)、[计划](superpowers/plans/2026-11-07-feedback0171-offline.md)。
- **2026-11-07 反馈修复批（0.17.3，DEV-071 合入 + 五项实机）：** 独立离线分支 `codex/DEV-071-feedback016-offline`（`22a3c62`/`d2f9601`/`f1826a2`/`c12f83d`）合入主干：miter 回执公开投影、更新检查 `force` 与 `MECHDOG_UPDATE_TIMEOUT_SECONDS` 网络预算、草图求解阶段/模式原因、再生失败特征状态、offset 文案统一；公开工具仍 100。同批本机 Creo 12.4.0.0 实机：[BUG-032](work-items/BUG-032.md) 5 例体积误差 0、板厚 232/1、三组 frame、reload true；[FEAT-010](work-items/FEAT-010.md) 驱动仅 `prepared_only`，改用 [DEV-048 平面帧](work-items/DEV-048.md) ±Z 两例通过 + 平行 `u_axis` 拒绝（`native_acceptance=partial`）；[BUG-104](work-items/BUG-104.md) 剥离基线后预览建议刷新、未刷新被拒、刷新后 `baseline_source=adopted_live`；[FEAT-056](work-items/FEAT-056.md) `random` 与组件标签键 `palette_source` 均通过；[BUG-105](work-items/BUG-105.md) 放置失败回滚成功、revision 不变、状态 `ready`，随后保存与调色成功（派发前零变更与 `ack_no_mutation` 失败态恢复未实机）。门禁：短路径副本 2741 项 0 失败/0 错误/2 跳过、`dev_check` 通过、种子包两次构建同摘要。WorkBuddy 黑盒、Creo 9/10 实机保持未验。
- **2026-11-07 实机验证批（0.17.2，用户授权直连 Creo 12.4.0.0）：** 六组实机复跑，**无产品代码变更**，只回填证据与状态。① [BUG-115](work-items/BUG-115.md) 准入实机生效：拒绝组 3/3 `refused_expected`（16 项检查 0 失败）、拆分路线 3/3 `ready`（13/13）、投影依赖组 3/3 `ready`（13/13）。② [BUG-108](work-items/BUG-108.md) 九候选 9/9 建成、保存重载 9/9，`detected=false`/`accepted_rigid=false`，目标分支仍未触发，卡保持开放。③ [BUG-110](work-items/BUG-110.md) 零件/装配仍为零变更回滚（`guard_only`），`ack_failure` 成功路径未发生；另记录一次 preflight 证据竞态（重跑通过，未定因、不改代码）。④ [BUG-102](work-items/BUG-102.md) 报告方夹具两变体均成功（+352.044/−353.264 mm³），`-1` 仍未复现。⑤ [FEAT-004](work-items/FEAT-004.md) rebase 后 18/18 实机通过。⑥ [FEAT-058](work-items/FEAT-058.md) R03 矩阵 77/77 通过。WorkBuddy 黑盒、Creo 9/10、外部原件与阻塞项保持原样。
- **2026-11-07 离线收口批（0.17.1，未连接 Creo）：** 用户决定 WorkBuddy 公开 MCP 黑盒由其它机器单独测试，本轮不执行；本轮只做可离线完成的条目，需实机/原件的一律登记阻塞，不伪报完成。① [BUG-115](work-items/BUG-115.md)：`validate_operations` 对“fill→trim→thicken 整链同计划新建”在提交前拒绝并给拆分/显式 quilt id 替代，3 条单测通过；投影依赖组与 fill→thicken 不受影响，原生根因仍未确认。② [FEAT-005](#legacy-feat-005)：过期 revision 拒绝文本补齐 `model_id`/`current_revision`/`expected_revision`，仍不创建 job；单测精确断言。③ R12 断流/取消：离线注入已由 `tests/unit/test_stdio_lifecycle.py` 的客户端突死、未消费管道、EOF 收尾覆盖，未新增生产代码；真实断流仍未实机。④ 阻塞登记：DEV-002 剩余 `server.py`/`bridge.py`/`generic_bridge.py`/`creo_startup.py` 包化未排期，需 MCP stdio 握手与会话级验证，本轮不动；装配 bbox/erase 耗时/rename/managed delete、R11 quilt merge 与多截面 `surface_loft`、DEV-030 履带 G2—G4、FEAT-014 corner relief/relief 材料几何、`offset_mm` 带移除语义，均缺实机参照树或设计前置，保持原状态并写明所需输入。⑤ 其余 P1（BUG-094/063/065/035/051/053/003/004/050/074/036/031/037、FEAT-042）需失败原件或 Creo 会话复现，不据推测改代码。
- **2026-11-06 R01/R03/R09/R12/R13 实机验收（用户授权健康会话，Creo 12.4.0.0 / 匹配 SDK）：** ① R01 新增 `tools/surface_chain_offset.py`（`--case offset`）：空件 40×20 fill 双侧±5 mm 发布 5 mm + `volume_over_source_area`，已有实体 `pre_existing_volume`、圆柱面 `source_quilt_not_a_single_plane` 且距离 null，27 项通过（`build/surface_chain/20261106-121417-172300/report.json`）。② R03 `test_adoption_planar_wall.py --live` 77/77 通过（100×60×1、185×232×1、同计划 `current_plan`、保存重载）。③ R09 复跑六组全过、四墙 `saved_file_reloaded_and_verified=true`，新增报告身份块（commit/dirty/source_fingerprint/worker_sha256，`build/post090_n05/20261106T203424_b183d2c8/report.json`）。④ R09 剩余三项实机：`native_planar` 180×230×1→resize 185×232×1（feature_id 不变、保存重载）、四墙 `f_px/f_nx/f_ny/f_py` 建成（终 bbox 185×232.1×80、体积 106499.15656）、按面 bbox 定标（自由墙 run 232.0=附着边 232.0，miter 墙 run 185.0 vs 附着边 177.92、四角缺口 `[6,6]`）、gap/半径两组矩阵、unbend/bend_back/父壁 resize 被拒/无效边折边回滚（`build/sheetmetal_planar_box/20261106T212525_1018e92f/report.json`，sha256 `3fffaf07…607`）。⑤ R13 新件清理/同名复建/预存同名/已保存件回滚/新装配失败五路通过；装配以 `set_dimensions{id=999999}` 原生 -23 失败后 `erased/absence_verified/cleaned`，四场景全 passed（`build/bug096_failed_model_cleanup/20261106T213848_df2d8987/report.json`）。⑥ R12 长轮询实机六项通过：0/1/30 秒、到期、终态提前返回、边界拒绝、客户端取消不取消作业、第二客户端读取同一 job（`build/job_wait/20261106T214456_b6be82db/report.json`）。⑦ R02 12 例实机：9 例 ready、3 例同计划 trim→thicken 报 -4（基线不变、保护未释放）→ 新登记 [BUG-115](work-items/BUG-115.md)。**未验**：R12 断流注入、R02 外部 Creo 10 原件、R10 origin、R11 曲面路线、FEAT-014 relief 材料几何与更大厚度/半径范围。

- **2026-11-06 R06 离线复核（FEAT-001/BUG-091，未连接）：** `tests/test_creo_startup.py` 41 项、`tests.unit.test_startup_retry` 11 项、`tests.unit.test_t10_session_health` 24 项共 **76 项通过**，覆盖 `retry_id` 轮询稳定、busy 不排队/不开第二通道、health 事实来源/时间/`stale`、`session_status` 的 `mode="explicit_live"`/`live_probe`/`channel_policy`。`creo_session_status` 默认仍走 live 探测，本轮未改默认行为（D01 兼容设计待做）。正常部署现场、`-4`/`exit 20`/hung 无新证据，计划 R06 三项保持未勾；BUG-091 保持开放、根因未定。本轮未连接 Creo、未新建 Toolkit 通道、未做故障注入、未清 unknown。

- **2026-11-06 DEV-069 合并0.14.0两件反馈：** 原0.13.0四件+新增两件共6件原字节归档（[新增manifest](validation/feedback-0.14.0-2026-11-06/manifest.json)、[逐项映射](validation/feedback-0.14.0-2026-11-06/MAPPING.md)）；当前main仍4517e36/0.16.0。R05矩阵新增精确I032/30°A/B，Python/native 1e-6仍放行截断阵，升级P1准入兼容调查；新增[BUG-114](work-items/BUG-114.md)/R13修正已清理新件的效果归因，保留真正unknown保护及rollback兼容字段。R04补请求/归一化来源；through_all与预览外部正证据分列；C4552/闸门/LF重复项不重做。唯一行182→183；BUG-112已0.15交付却仍占待开发统计，本次移至未收口交付并新增BUG-114到待开发，故待开发仍1、未收口57→58，其他分类表口径保持。本轮未改产品/联调/发布。


- **2026-11-06 DEV-069 主干最新对账：** 已fetch main，HEAD/main/origin/main与v0.16.0均为`4517e36`；远端Release非草稿、四附件uploaded（本次未下载重算摘要）。[修订计划](superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)移除已实现基础代码，四壁从blocked改为基础已交付、定标与native_planar路径待证；板厚几何兜底仍未实现，偏置总体积公式风险仍在。A02尺寸守卫已随0.16.0集成，不重复派工。原始报告、旧dirty文档及未跟踪miter草案保留；无新增ID/分类迁移，本轮不联调或发布。

- **2026-11-06 0.16.0 发布（FEAT-014 miter cuts + FEAT-004 尺寸守卫）：** 分支 `codex/FEAT-014-miter-cuts`（提交 `e3f7b66`）与 `codex/FEAT-004-dimension-guards`（`2c1276b`/`3d0c31c`/`90d2c3e`）在 `v0.15.1`（`2b57dd5`）之上合并，无垂直冲突。① FEAT-014：`creo_sheetmetal_flange` 新增可选 `miter_cuts {width, offset}`，原生在折边元素树写 `PRO_E_SMT_MTR_CUTS`（`ADD=TRUE`、宽度/偏移均 `PRO_MITER_CUT_*_TYPE_BLIND`，GAP 型被 Creo 重置为 PARAM 且值清 0 故弃用），`adjacent_bend_ends` 由无条件拒绝改为"显式 `miter_cuts` 才放行"，默认拒绝不变；回显核对写入 `miter_cuts` 与 `adjacent_bend_ends_allowed`。实机四壁 `f_px`/`f_nx`/`f_ny`/`f_py` 全部成功、`saved_file_reloaded_and_verified=true`、revision 1→5、体积 42 920→106 499.16 mm³、`four_walls_complete=true`（`build/post090_n05/20261106T163234_c086ae9d/report.json`）。② FEAT-004：`dimension_guards` + `DimensionValue.expected_value/expected_symbol/expected_owner`，原生 `set_dimensions` 两遍式（先读后判再写），巡检补 `owner_feature_id/name`、`editable`；2026-11-03 实机 19 例为历史证据，rebase 后实机回归未跑。门禁：`bridge.py build` 退出 0、全量单测 0 失败、`dev_check` `success=true`（详见版本说明与发布记录）。**未测**：miter 切角量与角部间隙未量化、自由端对照无体积差；FEAT-004 rebase 后实机待排；Creo 10/9 未复测。
- **2026-11-06 0.15.1 发布（BUG-111 发布后修正批）：** 把 `codex/BUG-111-doc-and-counts-fix`（单个提交 `8798861`）合入 0.15.0 之后的主干（合并提交 `670c54b`），并同步 `version.py` → 0.15.1、README、两份种子清单、`docs/seed_package.json`、版本说明与发布记录。① 工具描述、`capabilities.py` placement 段与 [语法参考](REFERENCE_SYNTAX.md) 撤销"每批 ≤4 个副本并重新引用当前 body"，改为 0.11.7 定因口径；② [native/placement.cpp](../native/placement.cpp) 的 `failed_transform.selection.model_counts_at_start` 改取巡检实际字段（`features`/`surfaces`/`bodies` 数组长度 + `body_counts.active`），缺失记 `null`，不再一律 -1。门禁：`bridge.py build` 退出 0；`tools/test_unit.py` 全量 **2624 项通过**（起点 2616，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint、12 未格式化，未高于基线）；种子包两次重建同摘要 `a1a44ab3…b0`。**未验证**：本版未重跑 `test_geometry_transform_copies` 实机（沿用 2026-11-03 同逻辑 C2/C4 记录）、Creo 10/9、内核重合判据、`body_pattern`、WorkBuddy；BUG-108/BUG-110 保持开放。


- **2026-11-06 R12 connect 计时与剩余项收口（BUG-109、DEV-069；离线实现 + R09 第 3 项实机）：** `native/generic.cpp` 在 `connect_creo` 前后各发一条带 `ts`/`elapsed_ms` 的 `STAGE`（`connect`、`connected`），`native_stage.stall_report` 可把会话附着耗时与首个操作阶段分开，`tests/unit/test_native_stage.py` 增源契约断言。R12 `through_all` 的七键与 `effective_depth_mm=null` 已由既有 `test_extrude_depth_receipt.py` 覆盖，实机正/负/对称矩阵未跑。R09 第 3 项已实机执行（`build/post090_n05_live_20261106T1505/report.json`，`run_id=20261106T145942_62f3136c`，`passed=true`）：自由首壁建成并保存重载；第三壁 1 角/2 角均被 `adjacent_bend_ends` 创建前拒绝（rollback 成功、revision/体积不变），`trim_ignored` 复现；R09 第 4—6 项仍 blocked（无 corner relief/miter 路线，trim 不能让位）；R10 origin 保持 blocked（坐标尺寸以 `fabs` 相对草图原点写入，负 origin 会与正侧同值，resize 的 `max(|value|)` 无法恢复长度）；R11 无新参照树/原生路线证据，按计划不盲试；装配 bbox、erase 耗时、rename、managed delete 未实施。R99 未执行：工作树含其他会话文件，不切 `main`、不打包、不发 Release。门禁：`bridge.py build` 退出 0；`tools/test_unit.py` 全量 **2616 项通过**（起点 2580，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint、12 未格式化，未高于基线）。**未验证**：实机 connect 日志时间线、through_all 实机矩阵、origin/几何选边、corner relief/miter、quilt merge/多截面放样。

- **2026-11-06 Q00 / 0.12.0 四件反馈归档与逐条映射（FEAT-055，仅归档与文档）：** `C:\Users\Administrator\Downloads\0.12.0` 四件原件**逐字节归档 4/4**（F01 16 653 B / F02 6 131 B / F03 9 943 B / F04 6 674 B，长度、SHA256 与整文件字节序列比对均一致，[manifest](validation/feedback-0.12.0-2026-11-06/manifest.json)、[逐条映射](validation/feedback-0.12.0-2026-11-06/MAPPING.md)）。源目录混装两个报告版本：F01 标题写 0.11.7 但内容与 `feedback-0.11.7-2026-11-04` 四件均不同，故归入本批而不追加旧批；本批与既有七个反馈目录并存不合并。按计划 Q00 逐条核对源码：sidecar 缺失已由 0.13.0/0.14.0 四附件 + `check_release_assets.py` 闭环；`creo_export_model(format="native_bundle")` 两段式实机已闭环；G5 三 op 中 `surface_trim`/`project_curve`/`surface_offset` 已随 0.13.0 公开、`surface_loft` 仍缺；板厚回读、结构化失败诊断、`through_all` 深度语义、compact、装配 bbox/回指、`session_unknown`、四壁与折边余项仍按 Q01—Q06/DEV-069 Rxx 未实现。台账仍 182 行、无新增 ID（Qxx 为派工编号）；本批不修改原件、不改产品代码、未运行测试、未连 Creo、未提交/合入/发布，原有 dirty 文档与 `.trae/` 保留。三项收尾同日完成：FEAT-039/055/009 与 BUG-101 首页改写为带日期的交付口径、0.12.0 发布记录补注 sidecar 已补传（远端 `v0.12.0` 现四附件且 `check_release_assets.py` 摘要一致）、旧 S/W 编号映射表写入 MAPPING §七；Q00 已无剩余子项。

- **2026-11-06 Q06+Q02 子 agent 交付 / compact sections 与 failed_operation（FEAT-023、FEAT-008、FEAT-012；离线实现，未实机）：** 两路并行。① `src/creo_mechdog/compact_sections.py` 从 `bridge.compact_job` 抽出结果块/操作块名单；`creo_get_job`/`creo_list_jobs`（detail=compact）新增可选 `sections`，响应带 `sections_applied`/`omitted_sections`，非法块名在读取 job 目录前拒绝并列出全部已知块名；证据字段（status/revision/message/code/toolkit_code、回滚与保存重载、每条 operation 的 `feature_errors`/`failed_stage`/`failed_toolkit_call`/`failed_operation`）恒保留，投影先于 32 KiB 预算与 20 条采样执行。② 原生 `native/generic.cpp` 失败收尾写出 `failed_operation`（固定 14 键；`pro_error` 仅在实际 `catch (ProError)` 时非空并置 `pro_error_source="toolkit"`，`message` 截断 512 并带 `message_truncated`），Python `src/creo_mechdog/failure_context.py` 归一化并对旧执行器结果按 `failed_operation_index`/`failed_stage`/`failed_toolkit_call`/请求 ops 回填，不编造错误码；装配/放置只回显调用方 4×4 行向量 `input_matrix` 与 `determinant`/`orthogonality_residual`，不正交化、不归一化、不转置。门禁：新增 `tests/unit/test_compact_sections.py` 14 项、`tests/unit/test_failed_operation_context.py` 24 项；`tools/test_unit.py` 全量 **2477 项通过**（起点 2439，0 失败 0 错误）、`dev_check.py --skip-unit` `success=true`、`bridge.py build` 退出 0。未验证：实机 Creo、MCP stdio 客户端、WorkBuddy 均未跑，`ProAsmcompAssemble` 返回 -2 与 Euler 展开路径只有单测。工作卡已回填 FEAT-023/FEAT-008/FEAT-012 与 [逐条映射](validation/feedback-0.12.0-2026-11-06/MAPPING.md)；Q01/Q03/Q04/Q05/Q07 仍未实现。

- **2026-11-06 R01/R02/R08 离线实现（BUG-112、BUG-113、DEV-070）：** 三路并行，全部离线，未连 Creo。① [BUG-112](work-items/BUG-112.md)：`native/surfaces.cpp::generic_surface_offset` 原第 168 行 `if (!ProQuiltInit(...); quilt)` 丢弃返回码，改为显式保存 `init_code`、仅在 `quilt_gauge_ready(init_code, quilt)` 为真时测面积，新增 `source_area_status={available,init_code,query_code,reason}`；不可用面积不再产生有限 `measured_offset_distance_mm`。判定抽到 `native/quilt_gauge_guard.h`（已登记 `server._SOURCE_NAMES`），`tests/native/test_surface_measure_guard.cpp` 覆盖 Init 非零+handle 非空、Init 为 0+空 handle、Init 为 0+有效 handle 三组合（后者才测一次）；`bridge.py::build_native` 三条自有原生编译命令加 `/we4552`，C4552 升为编译错误。② [BUG-113](work-items/BUG-113.md)：`native/generic.cpp` 在 `ProMdlnameBackup` 非 0 时先写 `save_failure={call,code,stage,destination,source_checkpoint,candidate_files}` 再抛出，回滚校验失败时写 `rollback_difference={available,status,reason,features,bodies,volume_mm3}`（基线取 `request.model.inspection`，恢复态提到 `verify_saved` 前；id/文件列表 ≤20 带 total/truncated；路径只留受管相对名）。`src/creo_mechdog/operation_results.py` 归一化并保留原始码，`compact_sections.py` 把两键列入恒保留证据；`rollback_succeeded` 判定未改、无重试、无自动 ack。③ [DEV-070](work-items/DEV-070.md)：`release_integrity.py` 新增 `validate_asset_paths`/`write_sidecar`，`validate_directory` 委托前者；`tools/package.py` 种子 sidecar 缺失由 WARNING 改为退出 2、打包后校验实际四路径；`check_release_assets.py --tag` 在 gh 缺失/下载失败时给 `--dir` 降级命令并退出 2，`--dir` 成功明确报 `local_verified`；sidecar 统一 ASCII+LF（读侧仍兼容旧 CRLF）。门禁：`bridge.py build` 退出 0（`/we4552` 生效）；`tools/test_unit.py` 全量 **2520 项通过**（起点 2477，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint/13 未格式化仍为基线存量）。**未验证**：Creo 12.4 实机（BUG-112 40×20/5 mm 双侧基准与保存重载、BUG-113 失败矩阵）、外部 Creo 10 复现、真实 `gh release download` 与远端四附件、WorkBuddy；两处缺 API/缺件路径只有离线替身。

- **2026-11-06 R03/R04 离线实现（FEAT-058、FEAT-023/FEAT-039）：** 两路并行，未连 Creo。① [FEAT-058](work-items/FEAT-058.md) 板厚回执：`native/planar_wall.cpp` 记录 `gauge_source`/`gauge_reason`，多个材料 body 时不再"取最大 body"而是记 `thickness_material_body_not_unique`；创建与改型逐 op 发布 `thickness_validation` / `thickness_loaded_validation`（`status=verified|unverified|mismatch|unavailable`、`source=api|missing_api|not_measured`、`value_mm`、`reason`、`context=current_plan|saved_loaded`），API 缺失记 `thickness_api_unavailable`、查询失败、非有限值、上下文错配各有独立原因；`native_planar_wall.py` 归一化并把非 verified 作为独立判据，**拒绝条件未放宽、未加几何兜底**（兜底仍需实机验证）。② [FEAT-023](work-items/FEAT-023.md) R04 剩余：新增 `src/creo_mechdog/job_projection.py`（`compact_operation`/`compact_progress`/`compact_job_list_item`/`FULL_DETAIL_HINT`），`bridge.compact_job` 先按 `sections` 选块再做 op 白名单投影与预算，compact 去掉 `native_log_tail` 与嵌套 `log_tail`，full 保留原日志与分页路径，新增 `full_detail_hint`；`creo_list_jobs` compact 改为固定小条目（身份/状态/时间/阶段/outcome/有界 message，`job_id` 为详情入口），整列表实测 50 条 32102 B、单条最大 618 B；trim/offset/project/solidify 判据键按原生实际键名保留，null 与 reason 不改写成 0；采样窗外额外保留一条失败记录。门禁：`bridge.py build` 退出 0；`tools/test_unit.py` 全量 **2550 项通过**（起点 2520，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint、12 未格式化，均不高于基线）。**未验证**：钣金创建/改型实机与保存重载读回、缺 API 的 `MECHDOG_HAS_*` 关闭构造、compact 的 stdio 真实字节、WorkBuddy；`creo_list_jobs` 返回结构变化已改描述文字，但旧消费者迁移未实机核对。

- **2026-11-06 R06/R07 离线实现（FEAT-001、BUG-091、DEV-069/DEV-062/FEAT-039，纯离线）：** 两路并行，未连 Creo、未启动/结束进程、未做故障注入。① R06 会话回执：`creo_startup.CreoStartup` 保留 `launch_attempt`（仅实际启动递增）与既有 `state`/`retry_allowed` 语义，新增稳定 `retry_id`（轮询不新建 retry）、`phase`、ISO-8601 `started_at`/`deadline_at`/`phase_deadline_at`、`failure_code`、`terminal_reason`、`retry_blocked_by`；`next_allowed_retry_at` 无法保证时为 `null` 并给 `next_allowed_retry_reason`；总/阶段预算分别标 `budget_scope="total"`/`phase_budget_scope="phase"` 并给 `budget_active`。`creo_session_status` 标 `mode="explicit_live"`、`live_probe`、`channel_policy`，通道忙立即返回（不排队、不开第二通道），启动协调器运行中只返回快照；startup 探测遇 `ToolkitBusy` 保留 busy 证据后等待原阶段预算。`session_health.snapshot()` 增 `path="local_evidence"`，连接/保存/历史保存/历史损坏/旧身份分别标 `source`（recorded_job/toolkit_probe/attributed）、时间与 `stale`，新增 `historic_saves`、`worker`（`causality="suspected_only"`）、`session.identity_stale`；连接成功不升级为“健康”，历史失败不覆盖当前 `connected`。窗口观察明确 `window_title=null` 原因与 `hung_implies_modal=false`。② R07 契约与口径：`references.py::by_tool` 新增 `creo_surface_trim`（target quilt/quilt_feature；tool quilt、基准面标签或曲线几何 ID；`keep_side` 依据 `tool_plane_normal`/`curve_direction`）、`creo_project_curve`（source 仅 `curve` 几何 ID；`direction_ref` 接受 `datum_feature`/`datum_axis_feature` 标签或曲线 ID，拒绝 `datum_plane` 标签与裸向量）、`creo_surface_offset`（quilt 引用 + `distance`，结果为偏置壁而非独立 quilt 或实体厚度壁）、`creo_loft`（仅 `mode="add"`，无 `surface_loft` 工具/操作），并列出被拒 label 写法；`capabilities.py` 抽出 `SURFACE_TRIM_OFFSET_LIMIT` 供门禁与契约共用（文案不变）、新增 `surface_chain` 家族、校正 `surface_solid`/`loft` limits，**未放宽任何门禁**；同步 `REFERENCE_SYNTAX.md`、`README.md`、`COMPATIBILITY.md` 与 FEAT-039/055/058、DEV-067 首页口径（0.14.0 按已发布记录，不降级为候选）。计数核对：运行时 `tool_count=100`；`REGISTERED_OPERATIONS` 68（67 可提交 + `quilt_merge` 门禁），`creo_quilt_merge` 导入时移除。门禁：本轮无原生改动故未重跑 `bridge.py build`；`tools/test_unit.py` 全量 **2580 项通过**（起点 2550，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint、12 未格式化，未高于基线）。**未验证**：真实断连与 `-4/exit 20` 现场、hung/modal 实机区分、startup 回执在真实会话中的时间线、WorkBuddy 公开 MCP 黑盒；R06 未改 `capabilities.py` 工具描述（字段已随返回 dict 透出）。

- **2026-11-06 R05/R09 文案/FEAT-007 长轮询离线实现（BUG-045、FEAT-012、FEAT-008、FEAT-014、FEAT-007，纯离线）：** 三路并行，未连 Creo。① R05 矩阵契约：`schema.py` 新增 `ROTATION_CONVENTION`/`ROTATION_FORMULA`，`AssemblyPose` 的 `translation`/`rotation`/`rotation_matrix` 用 `Field(description=...)` 统一写出 `p_parent = p_local * rotation_matrix + translation`（3×3、正交 det=+1 误差 1e-6、与 Euler 互斥、不转置/不修复），assemble 与 component_placement 两支 schema 逐字一致；`native/assembly_pose.h` 增 `assembly_rotation_convention()`，`native/advanced.cpp::assembly_pose_receipt` 在创建与 `component_placement` 成功后回执 `rotation_convention`、内核实读 `transform`（`component_to_assembly` 4×4）、`transform_source`、`transform_code`、`length_unit`，读取失败 `transform=null` 且不回显请求位姿；`job_projection.ASSEMBLY_POSE_KEYS` 并入两个 op 的 compact 白名单，`failed_operation` 仍整块保留。② R09 文案：`flange_first_wall_guide()` 按 alias 区分 `native_planar`（只指 `creo_sheetmetal_planar_wall` 的 frame/envelope，不引用 `wall_contract`/YZ 旧配方）与 conversion（才给 `wall_contract` 配方），来源未知不给旧配方；`sheetmetal_flange` 入参预检报出 `operations[i].edge` 与 `{kind:'edge',id:N}`；`adjacent_bend_ends` guard 文案改为 bend-end relief 未证明能解决 corner overlap、只修剪弯端非 corner relief/miter、传任何 relief 仍在创建前拒绝（拒绝条件未放宽）；`capabilities.py` limits、`schema.py` 描述、FEAT-014 卡与 `REFERENCE_SYNTAX.md` 同步。③ R12 长轮询（FEAT-007）：`server.creo_get_job`/`bridge.get_job` 新增 `wait_seconds`（严格整数 0–30，默认 0），只读 `job.json` 等终态（0.25 s 间隔），不持 Toolkit 锁、不新建/重交/改超时，返回值追加 `wait_seconds`/`waited_seconds`/`wait_expired`；新增 `docs/work-items/FEAT-007.md` 与 `tests/unit/test_job_long_poll.py` 9 例。门禁：`bridge.py build` 退出 0；`tools/test_unit.py` 全量 **2615 项通过**（起点 2580，0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`（24 lint、12 未格式化，未高于基线）。**未验证**：原生装配回执与 `transform` 实读、共面 extrude/cut-miss 的 `failed_operation` 实机、折边文案在真实失败会话中的表现、四壁/relief 几何、真实长任务与 MCP stdio 客户端取消、WorkBuddy。**仍阻塞（需会话授权）**：R09 第 3—6 项四壁/角部几何、R10 首壁 origin 与计划内几何选边、R11 真实 quilt merge/多截面曲面放样、R12 其余子项（through_all、装配 bbox、connect 计时、erase 耗时、rename/delete）与 R99 发布。

- **2026-11-06 DEV-069 / 0.13.0 四件反馈核对与规划：** Downloads/0.13.0 原件逐字节归档 4/4（[manifest](validation/feedback-0.13.0-2026-11-06/manifest.json)、[逐项映射](validation/feedback-0.13.0-2026-11-06/MAPPING.md)）；以本地 `7002575` / 0.14.0 去重，建立[设计](superpowers/specs/2026-11-06-0.13.0-feedback-repair-design.md)与[分批修复计划](superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)。新增 BUG-112（偏置源面积 Init 返回码丢弃）、BUG-113（Creo 10 追加曲面 Backup 与回滚失败）、DEV-070（四附件自动闸门/LF）；板厚、矩阵、compact、会话与四壁接续既有 ID/Q01—Q06。README 旧链接和 W01 文案冲突当前已修，不重复派工。本轮只分析/文档，未运行产品测试、连接 Creo、提交/合入/发布；原有 dirty 文档与 `.trae/` 保留。台账唯一任务行 178→182，待开发 0→1、待复现 24→25、待规划 47→49，其余分类保持。

- **2026-11-06 R10 首壁 origin 实机验收（FEAT-058，分支 `codex/R10-first-wall-origin`，未合 main、未发布）：** `sheetmetal_planar_wall` 新增 `origin=[u0,v0]`（命名平面 frame 内草图局部 mm，默认 `[0,0]`；字典平面自带 origin，与非零值互斥），矩形改为 `u0..u0+L / v0..v0+W`，包络与体积判据随 origin 移动；`resize` 保持 origin，因坐标尺寸只是"到截面轴的距离"，改为读草图截面定位矩阵把记录 frame 映射到截面轴、按 `wall_0..wall_3` 角点表核对旧值后写入新值，无法解释时拒绝而非猜测。未采用平移 sketch frame：原生探针显示 XZ 显式平面取支撑法向 +Y（named 为 −Y），`v` 翻到 −Z（`z[-348,-116]`），故保留命名帧。实机 Creo 12.4.0.0：`tools/test_first_wall_origin.py --live --confirm-session-usable` **112/112**（`build/first_wall_origin/20261106T152859Z/origin_live.json`），185×232×1 + `origin[-92.5,-116]` 得 bbox `[-92.5,-116,0]..[92.5,116,1]`、质心 `[0,0,0.5]`，同/跨计划 resize 到 200×250 得 `[-92.5,-116,0]..[107.5,134,1]` 且保存重载 true，默认 origin 件几何不变，第二面墙派发前拒绝且 revision 不变；`bridge.py build` 退出 0，`test_native_planar_wall` 44 项、`test_t02_operation_results` 18 项通过。**未验证**：Creo 9/10、显式平面字典 + 非零 origin、斜置 frame 改型、WorkBuddy。

- **2026-11-06 R10 计划内 `edge_geometry` 选边实机验收（FEAT-014，分支 `codex/R10-first-wall-origin`，未合 main、未发布）：** `sheetmetal_flange.edge` 新增第二种形态 `{kind:'edge_geometry',endpoints_mm:[[x,y,z],[x,y,z]],tolerance_mm:1e-6}`（当前模型坐标 mm、可省略 tolerance 1e-9..1000、不接受单位字段），保留 `{kind:'edge',id:N}`；原生在**每个 op 执行前**遍历 body→surface→contour→edge，`ProEdgeDataGet`/`ProLinedataGet` 取直线端点、按无向端点对在 tolerance 内唯一匹配，0/多候选、非有限坐标、退化端点、模型长度单位不可换算时明确拒绝并在文案中给出扫描数与候选 id。实机 Creo 12.4.0.0（模型 `cbbcd27acf374b9c82534c3764b3aa51`、新件 job `87fe58e725f54f039c53cac485edb2b8`）：185×232×1 首壁 + `+x`/`-x` 两道非干涉折边都用**任何折边创建前**采集的端点提交，两面墙顶面 232 mm 与贴边关系 `matches`、均保存重载 true；`-y` 顶边被两道折边缩短 185→177.92 mm 时 id 由 **85 变为 267**，旧 id 已不在当前边表，随后同一边用几何端点 + 显式 `miter_cuts{width:1,offset:1}` 建成并保存重载 true；不存在的几何 `[[900,900,900],[900,901,900]]` 被拒（扫描 86 条直线边），revision 与体积不变、回滚 succeeded。`tools/test_flange_edge_geometry.py --live --confirm-session-usable` **17/17**（`build/flange_edge_geometry/20261106T235931_f44fd733/report.json`，SHA256 `b84b3e0f5908f6af8932babf70803bbb81982f7ef2bbadf90341db917f13f4ea`）。**未验证**：Creo 9/10、多候选歧义与未知单位的实机拒绝（仅单测）、非轴对齐/斜置边的端点匹配、WorkBuddy；跨计划重放与真实重启后的 id 重排未单独构造。


- **2026-11-06 FEAT-039 偏置新规格复测（门禁保持）：** 用低层 `creo_create_feature_tree` 按 `ProTrim.h` §(4.1) 的 **Thin** 树复测（两个 type 元素 = `PRO_SURF_TRIM_THIN`），旧写法把偏置元素挂在 Use Quilt 树上才被内核忽略。实测 40×20 填充 + x=20 竖直 quilt 工具：厚度 5 → 目标面积 **700**、厚度 10 → **600**、x=2 → **760**，工具 quilt 盒按厚度单向移动，即 `offset_mm` 只对 **quilt 工具**生效且语义是**移除厚度带、两侧保留**，与公开契约"保留 one/two 一侧"冲突；`offset_side` 六种写法（`PRO_E_STD_USEQLT_SIDE` one/two/both、附加 material/primary side、`PRO_E_SRF_OFFS_DIRECTION`）结果完全相同，方向由工具 quilt 朝向决定，负厚度再生成失败，基准面工具忽略厚度。原生偏置分支已改为文档 Thin 树，但 `capabilities.require_available` **继续拒绝** `offset_mm`，schema 不变；是否按带移除语义开放需单独决策。证据 `build/live_thin_trim_probe.json`/`live_thin_trim_probe2.json`，契约 [G5 §2.7b](development/G5-NATIVE-CONTRACT.md)，工作卡 [FEAT-039](work-items/FEAT-039.md)。本轮不改公开能力；该复测随后于 `04dcbd5` 提交，并随 0.14.0 发布（`main@c774fa2`、标签 `v0.14.0`）。

- **2026-11-05 0.13.0 发布执行 + W02—W06 补证（分支 `codex/FEAT-039-w02-w06-live`）：** PR #13 合入 `main`（合并提交 `d90d28e163f096f602ca06f60ccd11a91274172a`），标签 `v0.13.0`（附注标签对象 `1ae20806…`），Release 与四附件上传并远端核对通过（见[发布记录](validation/RELEASE-0.13.0.md)）。发布后按 1→5 顺序补证：W02 拔模双向（[BUG-102](work-items/BUG-102.md)，+352.044362 / −353.263560 mm³，`effective_flip` 两次均 true，原始 Creo 10 `-1` 未复现）、W03 基准面方向矩阵与两入口拒绝（[BUG-094](work-items/BUG-094.md)，六例法向/原点解算 + 三拒绝无 job/无特征/revision 不变）、W04 草图 origin 矩阵（[BUG-095](work-items/BUG-095.md)，省略/精确/0.5e-6 通过、2e-6 与 ±1.07e-4 拒绝带 signed/distance 诊断）、W05 `extrude_depth` 回执（[FEAT-039](work-items/FEAT-039.md)，省略→100 mm³、`depth=10` 省略 type→1000 mm³，effective 从特征树实读）、W06 只读预览三段 + 失败编辑回滚（[FEAT-039](work-items/FEAT-039.md)，`preview_acceptance="passed"`、`not_new_model_job` 回滚 revision 不变）。**本轮不合 main、不发布 0.14.0**；W05/W06 归 0.14.0。门禁：`tools/test_unit.py` 全量 **2439 项通过**（`build/unit_test_report.json`，0 失败 0 错误）、`tools/dev_check.py` 通过（24 条 lint 均为基线存量、13 个未格式化文件均在 `style-baseline.json`）、`bridge.py build` 已重建执行器。未测保持：S03 合并算子（4 个 `PRO_SURFACE`、0 quilt）、S05 多截面放样（Direct Blend 树抽取 -18）、原始拔模 -1 未复现、Creo 9 无本机 SDK、Creo 10 独立复测按 2026-10-15 决定取消、WorkBuddy 未执行、预览图片内容待人工复核。

- **2026-11-04 DEV-067 / 0.12.0发布复核与后续派工：** A04已发布，远端main@90dbd6c、v0.12.0@758e87e、两附件SHA256/大小/源码身份、实机67/67和单元2286报告本次均已核验。当前规划工作树仍0.11.7，不与发布工作树混认。[核验记录](development/DEV067-POST0120-AUDIT-2026-11-04.md)；[后续计划](superpowers/plans/2026-11-04-alphai-post0120-integration-plan.md)。A02接实机收口；A03先深度/孔表契约；A01先非有限值/材料重心/回执契约；B01仅日志子项已有，继续骨架探针。任务均接续现有提交，不重复从零派工；本次未改产品代码/连Creo/合main/发布。

- **2026-11-03 BUG-111 口径与诊断计数修正（0.11.7 发布后修正，分支 `codex/BUG-111-doc-and-counts-fix`）：** 复审 0.11.7 交付发现两处与定因结论不符，本轮修正并实机复核。① 对外文案：工具描述、能力边界（placement 段）与[语法参考](REFERENCE_SYNTAX.md)仍建议"每批 ≤4 个副本并重新引用当前 body"，而 C6 已证明拆批无效——本轮撤销该建议，改为"副本集放在同一计划里提交，需要固定原件副本时另建模型"，兼容矩阵 0.11.6 历史段标注被 0.11.7 段取代。② 选集诊断计数：`native/placement.cpp` 原读巡检从不发布的 `state["counts"]`，计数一律退化为 -1（把已有数据写成未知）——改为读 `features`/`surfaces`/`bodies` 数组长度与 `body_counts.active`，缺失项记 `null`。复核：本机 Creo 12.4.0.0、最终执行器 `cb6f3345…`（源码指纹 `7d0bc254…`）复跑 C2/C4（`--cases C2,C4 --model-suffix t7`）→ C2 仍失败于 index 4 且整批干净回滚、后续合法编辑成功，C4 五副本全部成功且保存重载 true；失败回执 `model_counts_at_start` = `{features:12, surfaces:26, bodies:1, active_bodies:1}`。离线全量 2276 项单测 0 失败/0 错误、`dev_check` `success=true`。**BUG-108 与 BUG-110 保持未验证/开放**（`accepted_rigid=true` 9/9 未触发、`ack_success` 未实机发生），本轮不因其关闭；台账行数与各分类状态不变，版本号仍 0.11.7，本轮不合 main、不发布。见[工作卡](work-items/BUG-111.md)与[验收摘要](development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。

- **2026-11-04 S00 / 0.11.7 反馈归档、派工登记与 G5 契约修订（FEAT-055，仅文档与测试）：** `C:\Users\Administrator\Downloads\0.11.7` 四份原件**逐字节归档 4/4**（长度 9 438 / 6 796 / 8 964 / 3 142 B，SHA256 与整文件字节序列比对均一致，[manifest](validation/feedback-0.11.7-2026-11-04/manifest.json)、[逐条映射](validation/feedback-0.11.7-2026-11-04/MAPPING.md)），与 `feedback-0.11.5-2026-11-03` 等既有目录并存不合并。派工依据为 [0.11.7 曲面链与反馈完善计划](superpowers/plans/2026-11-04-0.11.7-surface-chain-improvement-plan.md)：**S00—S10 / C01—C04 / W01—W06 全部复用既有行**（FEAT-055、FEAT-039、FEAT-009、FEAT-054、FEAT-008、BUG-101、BUG-102、BUG-094、BUG-095、BUG-088、BUG-108、BUG-109、BUG-110、BUG-111、DEV-045），Sxx/Wxx/Cxx 只是派工编号，不新增台账 ID；台账仍 178 行、无新增 ID。同窗口 DEV-067 按实际行状态重算了分类计数（开发中 6、验收中 31、待规划 47、未收口 57 等，见其 2026-11-04 行），该重算与 FEAT-057/058/059/FEAT-004 的行状态迁移是并行改动，不属于本批。G5 契约按 S00 修订（[§0.1 修订记录](development/G5-NATIVE-CONTRACT.md)）：补显式 `{"kind":"quilt","id"}` 引用与 quilt/surface ID 不可互换规则、区分 schema 不建 job 与运行时引用失效走回滚、投影 oracle 撤销不自洽的"高 20 圆柱承载长 30 源线"改为 40×20 平面 −Z 投影用例并单列圆柱待定义用例、修剪两侧判据改实测位置与有符号偏移（不跨模型比 ID）、旧路线失败历史保留为 `route_not_established`/`unverified` 状态；`tools/test_g5_native_probe.py` 与 `tests/unit/test_g5_native_contract.py` 同步（19 项契约测试全过，含新增 oracle 域内性、显式 quilt 类型、候选清单与旧路线状态断言）。BUG-101 原"不做几何改写"为历史范围：本次派工新增 W01 端点焊接本体，须补独立设计与回执契约后实现，不得靠删掉旧边界默认启用吸附；`gear10.json` 等原件本轮仍缺，W01 原案保持未验证。本轮不连 Creo、不运行 Toolkit、不合 main、不发布；原生改动（后续 S01 起）均须实机串行窗口验收。

- **2026-11-03 DEV-067 / alphai 能力吸收派工规划（仅规划）：** 已建立[派工主计划](superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)、[设计依据](superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)和四组子计划。13项映射：新增FEAT-057—064八项，复用FEAT-001/004/010/035/049五项；补建FEAT-001/004缺卡，新增DEV-067协调卡。首批建议A01质量/A02尺寸保护/A03标准螺纹孔；A04原生平面壁先探针，骨架关联先冻结多模型身份/恢复契约。负责人均unassigned，由用户自行指派；本轮未启动Agent、未改产品代码、未测试/连接Creo、未合main/发布，目标版本未排期。台账169→178行，待规划43→52；按现有行状态纠正BUG-101统计滞后：开发中4→3、待复现23→24，不改其“实机不复现”状态或历史结论；历史反馈原件不改。

- **2026-11-03 0.11.7 发布（PATCH，R13 后续定因与实机补证批）：** 版本入口同步为 0.11.7（`version.py`、README 标题与当前版本段、两份种子清单、`docs/seed_package.json`），公开工具仍 **95 个**，接口与参数语义不变。交付内容：BUG-111 第 5 个 `keep_original` 副本失败的**定因**（选集语义 + 重合/交叠再生失败）与有界选集诊断 `failed_transform.selection`，撤销"≤4/批"变通建议；BUG-110 重放判据修正；开发者夹具判定口径与 `--cases`/`--model-suffix` 增强。BUG-108（9/9 未触发）与 BUG-110（`ack_success` 未实机发生）**保持开放**，不因本版关闭。台账 169 行与各分类状态不变。见[版本说明](RELEASE_NOTES_0.11.7.md)、[发布记录](validation/RELEASE-0.11.7.md)、[Release v0.11.7](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.7)。

- **2026-11-03 R13 后续开发计划（仅规划，用户接手实施）：** [BUG-111 定因、BUG-108/110 实机补证计划](superpowers/plans/2026-11-03-r13-followup-bug111-108-110.md)沿用三个既有 ID：先隔离副本场景与 body 选集，再依据证据最小修复；分别取得刚性平移放行与失败确认成功路径的真实证据。按 T0—T5 独立验收，未定因/未触发继续开放；未新增台账行、未执行测试或实机，169 行及现有分类状态保持。

- **2026-11-03 R13 后续定因与实机补证（实机轮，BUG-111 / BUG-108 / BUG-110）：** 分支 `codex/BUG-111-r13-followup`（取证时 HEAD `36b5b4c`），接续离线轮；用户当次授权实机，运行目录 `build/r13_followup_20261103T161114/`。**BUG-111 定因完成**：C0—C6 七个独立底板实机，4 个独立模型同型失败于 index 4；C4/C0 推翻"位置/数量上限"与"纯角度"，C6 推翻拆批变通，单 body 推翻引用解析；T2 增有界 `failed_transform.selection` 选集证据（失败 op 复制整个累积体 26 面，行为零改动，执行器 `7071b947…`），根因定为 **`keep_original` 复制整个当前体的选集语义 + 重合/交叠再生失败**，无实现缺陷证据，不做行为修复；"≤4/批建议"作废。**BUG-108**：9/9 候选未触发（体积 oracle 精确），`accepted_rigid=true` 记 unverified，保留外部 Creo 10 补证。**BUG-110**：零件与装配均零变更守卫（guard_only），`ack_success` 未实机发生，装配成功路径未覆盖。重放判据修正补回归（确认二次修改/结果变化判 fail）；驱动判定口径修正并新增 `--cases`/`--model-suffix`。整批定稿后 `dev_check` `success=true`，全量 **2 268 项 0 失败/0 错误**，风格基线未改。台账 169 行不变，三卡按各卡结论保持开放（BUG-111 现象侧收口、边界与诊断交付）。假设记录 `hypotheses.md` 与摘要见 [验收记录](development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。

- **2026-11-03 R13 后续定因与补证（离线轮，BUG-111 / BUG-108 / BUG-110）：** 分支 `codex/BUG-111-r13-followup`（起点 `45780df`），运行目录 `build/r13_followup_20261103T161114/`（指纹 `cd22b563…`、执行器 `0f556504…`，未重编）。三个实机驱动完成场景隔离与三态判定改造（C0—C6 独立底板；9 个草图候选 + 独立复算；ack 三 scope + 不变性 + 同键重放 + 后续可用性），新增 23 项判定回归；全量 **2 264 项 0 失败/0 错误**，`dev_check --work-item BUG-111-BUG-108-BUG-110-followup` `success=true`，风格基线未改。**实机未执行**（无当次会话授权，BUG-001 纪律），第五副本未定因、`accepted_rigid=true` 未触发、`ack_failure` 成功路径未覆盖；三卡均未关闭（同日实机轮已接续，见上条）。摘要见 [验收记录](development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。

- **2026-11-03 DEV-059 / R13 计划对账与缺失工作卡补齐（只整理文档与任务）：** 分支 `codex/DEV-059-plan-reconciliation`，起点 `main@0d8712d`（`version.py`=0.11.6，`origin/main` 同点）。核对 [R13 计划](superpowers/plans/2026-11-03-0.11.5-feedback-r13-plan.md)、[DEV-065](work-items/DEV-065.md)、[BUG-108](work-items/BUG-108.md)—[BUG-111](work-items/BUG-111.md) 与 0.11.6 发布记录后：回填计划勾选与"剩余范围"、修正 DEV-065 任务表（R13-01—04 已实机、R13-07 版本已裁定 0.11.6）、把台账当前版本改为 0.11.6、修正 [DEV-060](work-items/DEV-060.md)/[DEV-062](work-items/DEV-062.md) 与台账行残留的"未提交/未合入/未发布"表述（保留历史登记轮记录并注明当前状态）。**补建缺卡 4 张**（沿用既有 ID，不新增行）：[DEV-056](work-items/DEV-056.md) worker 二进制指纹、[DEV-057](work-items/DEV-057.md) Q14 BCG 剩余验证、[DEV-058](work-items/DEV-058.md) WorkBuddy 黑盒验收、[DEV-059](work-items/DEV-059.md) 发布后计划与工程整理。台账行数与唯一 ID 仍为 169，分类合计复核一致。本轮**未改产品源码与版本号、未运行产品测试或实机、未连接 Creo、未合 main、未推送、未发布**。

- **2026-11-02 DEV-002 / 第三批执行：** 用户后续要求本会话直接执行，[计划](superpowers/plans/2026-11-02-dev002-batch3-package-migration.md)的 seeds/capabilities 包化、根导入与 CLI 兼容、安装依赖和源码指纹已实现，分步提交于 `codex/DEV-002-batch3-package`；95 工具 schema/能力/种子输出前后一致，123 项模块回归、23 项布局回归通过，首轮统一检查 2196 项通过，修复旧测试 .tmp 前提后独立解压安装 64 项通过，最终统一检查通过（2196 项、0 失败/错误）。[本批证据](validation/DEV-002-batch3.md)保留首轮独立副本失败与修复结果。**用户后续授权合入 main 并发布 0.11.5，交付核对见[发布记录](validation/RELEASE-0.11.5.md)；T5 实机待验，整个 DEV-002 保持开发中。** 沿用唯一行，不增加 ID/统计数量；服务/启动/桥接与 C++ 后续分批。

- **2026-11-02 DEV-062 / R11 归档与登记：** `C:\Users\Administrator\Downloads\0.11.0` 三份 v0.11.0 验收原件**逐字节归档 3/3**（长度、SHA256 与源文件一致，[manifest](validation/feedback-0.11.0-2026-11-01/manifest.json)、[逐章映射](validation/feedback-0.11.0-2026-11-01/MAPPING.md)），与 `feedback-0.10.0-2026-10-31`/`feedback-0.10.0-2026-11-01` 并存不合并。新登记 [BUG-104](work-items/BUG-104.md)（旧检查点无 `appearance` 基线）、[BUG-105](work-items/BUG-105.md)（零变更失败无恢复动作）、[FEAT-056](work-items/FEAT-056.md)（色板族名键与 `random:true`）、[BUG-106](work-items/BUG-106.md)（同名会话解锁链路，仅登记）、[DEV-063](work-items/DEV-063.md)（擦除回执体量与预览视角字段，仅登记），并补 FEAT-052/BUG-101/BUG-102/BUG-088/BUG-089/DEV-061 增量。已闭环项（BUG-089 主闸门、DEV-061 仓库级断言、BUG-090 编译证据、FEAT-035 `depth_basis`、FEAT-052 卡状态、0.10.1 三键枚举、draft 双 flip、`weldability` 风险标记、BUG-096 回滚字段）按 MAPPING §三 只记依据、不重复派工。分批见 [R11 分窗计划](superpowers/plans/2026-11-02-feedback0110-r11-plan.md)。**2026-11-02 离线批已随 0.11.3 发布**（[版本说明](RELEASE_NOTES_0.11.3.md)、[发布记录](validation/RELEASE-0.11.3.md)）：BUG-104/BUG-105/FEAT-056 完成实现与专项单测（+27 项，全量 2 158 项 0 失败）、`dev_check.py --work-item 0.11.0-feedback-r11` `success=true`、`bridge.py build` exit 0（执行器 13 250 048 B / `a61fad90…`，`build/source.sha256=5e82d3ad…`）。**未做**：本批全部实机验收（补基线、随机上色、`ack_no_mutation` 恢复）、BUG-106/DEV-063 实现、Creo 9/10 与 WorkBuddy。
- **2026-11-02 DEV-060 / R10 归档与登记：** `C:\Users\Administrator\Downloads\0.10.0` 三份 v0.10.0 验收原件**逐字节归档 3/3**（长度、SHA256 与源文件一致，[manifest](validation/feedback-0.10.0-2026-10-31/manifest.json)、[逐章映射](validation/feedback-0.10.0-2026-10-31/MAPPING.md)），与晚间包 `feedback-0.10.0-2026-11-01` 并存不合并。新登记 [BUG-101](work-items/BUG-101.md)（近容差端点不可焊/归因）、[BUG-102](work-items/BUG-102.md)（draft 倒角圆角面回归与 flip 语义）、[BUG-103](work-items/BUG-103.md)（水平底板壁面归属）、[DEV-061](work-items/DEV-061.md)（种子摘要仓库级闸门），并补 FEAT-014/FEAT-035/FEAT-051/BUG-049/BUG-090 增量。已闭环项（FEAT-051 体积回报、0.10.1 三键枚举、空件预览、BUG-047、FEAT-031、BUG-045、BUG-089 主闸门、`wall_contour_status`）按 MAPPING §三 只记依据、不重复派工。分批见 [R10 分窗计划](superpowers/plans/2026-11-02-feedback0100-r10-plan.md)。**2026-11-02 离线批已交付**：`weldability` 判定与原生归因（BUG-101）、draft `requested/effective_flip` + `draft_failure`（BUG-102）、孔 `depth_basis` 三键（FEAT-035 增量）、壁面归属对照清单与示例/README 纠偏（BUG-103，结论未定因）、种子摘要仓库级闸门（DEV-061）；`tools/dev_check.py --work-item R10` `success=true`、单元 2 130 项 0 失败、`bridge.py build` exit 0（`build/source.sha256=ffe75d9b…`）。**2026-11-02 实机（Creo 12.4.0.0，用户授权）**：draft 10°/`flip=false` → `effective_flip=true`、+264.49 mm³；YZ 底板 42920 mm³、四条下边 104–107 全 `eligible`、对报告方失败的边 106 挂折边成功 57293.62 mm³；8.215e-7 间隙拉伸成功（与报告方 Creo 10 的 `-1` 不一致，`weldable` 因此改为风险标记）。**未做**：draft 元素树 A/B、盲孔 `depth_basis` 实机回执、Creo 9/10 与 WorkBuddy。
- **2026-11-01 DEV-053 / Q15 离线集成与两轮实机：** Q01–Q07、Q11、Q13、Q14 分支按计划合入 `codex/q15-integration`，详见 [Q15 集成报告](work-items/DEV-053-Q15-integration-2026-11-01.md)。首轮在 Q05 `main_plane` 卡死并登记 [BUG-098](work-items/BUG-098.md)（现场保留，未结束 Creo/未清 unknown/未重提）；修复 `preview.h` 合并截断与三点定面约束读取后，第二轮结果：**Q05 live 8/8 通过；Q06 L1/L2 通过（无精确垂直基准面时自动建辅助垂直基准面，体积偏差 1.45e-8）；Q07 P1/P2/P3 三探针均“路线不成立”；Q03 S1 仍因 `window_open` 安全跳过、S3 rollback 字段缺失；Q13 `disk_cut_pattern` 在 `axis_pattern` 后 Backup 与 Save 均 -1（新登记 [BUG-099](work-items/BUG-099.md)）**。Q08–Q10 不开工；0.11.1 未裁定、未发布。Q12 保持 0.11.0 已交付。
- **2026-11-01 DEV-053 接续 / Q00 归档与登记：** 0.10.0 晚间反馈包**十件原件逐字节归档**（10/10 长度、SHA256 与字节一致，[manifest](validation/feedback-0.10.0-2026-11-01/manifest.json)、[逐章映射与缺件表](validation/feedback-0.10.0-2026-11-01/MAPPING.md)），登记 [BUG-096](work-items/BUG-096.md)（E 失败作业遗留会话对象，交叉关联 BUG-012/FEAT-018）、[BUG-097](work-items/BUG-097.md)（斜面草图 L1/L2，关联 FEAT-010/BUG-087/BUG-095）、[FEAT-053](work-items/FEAT-053.md)（三点定面 `thru_points`，关联 FEAT-008），并补建缺失的 [FEAT-009](work-items/FEAT-009.md)、[FEAT-010](work-items/FEAT-010.md) 工作卡。Q 任务负责人：Q02→写程序高手、Q03→代码编写者、Q04→codex代码，其余 unassigned。本轮为文档登记，不连 Creo、不跑产品测试、不合 main、不发布。

- **2026-11-01 DEV-054 / 本地维护：** 重核 [Q00–Q15 后续计划](superpowers/plans/2026-11-01-feedback0100-agent-dispatch.md)，按 0.11.0 已交付事实退出 Q12 开发派工；已删除2个合并分支引用，将重复检查包与旧虚拟环境共94.6 MiB移入可恢复归档（未释放磁盘），保留未合入功能、模型与发布证据。见[工作卡](work-items/DEV-054.md)；本轮不提交 main、不发布。

- **2026-11-01 FEAT-052 / 0.11.0 交付（MINOR）：** 装配按零件族上色随 0.11.0 发布：公开工具 `creo_recolor_assembly`（自动分族/显式族表/`dry_run` 只读预览）与计划操作 `recolor_assembly`，`creo_list_components` 三态 `appearance` 字段，工具数 94→95。实机验收 run `assembly_appearance_live_20261101T060336Z558b3546`（80 组件/12 族 28/28 检查）与装配 pipeline/T07 预览回归通过；实机过程定位并修复三处缺陷（原生外观比对迭代器下标 ×2、结果投影缺回滚核验字段、驱动夹具契约 ×2，均已提交分支）。WorkBuddy 黑盒、Creo 9/10、busy/并发实机仍开放。见[版本说明](RELEASE_NOTES_0.11.0.md)、[发布记录](validation/RELEASE-0.11.0.md)与[工作卡](work-items/FEAT-052.md)。
- **2026-11-01 FEAT-052 / 登记时历史状态（已由上方 0.11.0 交付取代，分支 `codex/FEAT-052-assembly-recolor`）：** 装配按零件族上色已登记为 [FEAT-052](work-items/FEAT-052.md)，新增公开工具 `creo_recolor_assembly` 与计划操作 `recolor_assembly`，开发分支工具数 94→95。默认按组件绑定中唯一的 `source_model_id` 自动分族，也支持显式族表 `families` 与色板 `palette`；`dry_run` 预览分组不连接 Toolkit、不创建作业、不推进 revision，执行走现有作业通道并始终保存。本阶段仅离线开发，**未连接 Creo、实机验收未做**；范围与边界见[工作卡](work-items/FEAT-052.md)与[功能计划](superpowers/plans/2026-10-31-assembly-recolor-plan.md)。

- **2026-10-31 DEV-053 / P00（历史时点，当前按工作卡与 Q 计划接续）：** [五份 0.9.0 原件归档与逐章映射](validation/feedback-0.9.0-2026-10-31/MAPPING.md)已完成；[P00—P16 总计划](superpowers/plans/2026-10-31-post0100-master-plan.md)中仅 P00 执行，P01—P16 尚未开始。新登记 [BUG-094](work-items/BUG-094.md) 与 [BUG-095](work-items/BUG-095.md)；缺件按映射清单保留。N12 发布后补证：small 每类 n=3；large 首轮每类 n=2、补轮每类 n=3，分别统计，见 [T09D 发布后补记](development/DEV051-T09D-ACCEPTANCE.md#2026-10-31-发布后补记n12-large-样本已补满追加不改写上文)。

- **2026-10-31 DEV-052 / N13 集成批次（历史交付，随 0.10.0 交付）：** [0.9.0 后续任务与分窗派发表](superpowers/plans/2026-10-30-post090-task-dispatch.md) 的 **N00—N13 已全部交付**，汇总条目为 [DEV-052](work-items/DEV-052.md)。N00 的 Downloads/0.8.x **七份反馈逐字节归档**（7/7 SHA256 一致，[逐章映射](validation/feedback-0.8.x-2026-10-30/MAPPING.md)含缺件清单）保持原记录；N01—N12 实现与两轮实机复测明细见 [七段实机总报告](development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)与 [0.10.0 发布记录](validation/RELEASE-0.10.0.md)。本批新增登记 [BUG-092](work-items/BUG-092.md)（server.py 子进程残留，待处理）与 [BUG-093](work-items/BUG-093.md)（N07 `illegal_dir_zero` 反例判定待查）；codex 沙箱基础设施挂起已按约定记入 [BUG-091](work-items/BUG-091.md) 附注，不重复登记。

- **DEV-051 历史接续计划（已随 0.9.0 收口）：**[完整逐项对账与当前完善计划](superpowers/plans/2026-10-30-feedback-072-to-085.md)（**该计划为 2026-10-30 计划整理轮的时点记录，保留历史时点**）。19 个叶子任务中 13 项已有指定阶段结论；顺序为 **BUG-032 板厚同步 → T11 弯端靠材料的释放 → T05 四壁/必要角部规则 → T13 完整 bundle 与新目录回导 → T09D 性能调查（P3）**。该顺序已按离线阶段推进到第十个提交（HEAD `768c673`）：板厚同步、释放回读校验与材料端 oracle、四壁对照设计与 `end_trim_mm` 贯通、弧方向判定与编辑/重载覆盖、组件身份同源、组件标签重载回归、中心线计数、性能基准驱动与口径、孔型余项、BUG-085 离线证据调查。**这十个提交随后已随 0.9.0 正式发布**（标签 `v0.9.0` → `7280982`），其中 T03/T13/T05/T09D 取得本机实机结果。三个未定因（BUG-085 根因、T05 第三壁内部机理、T13 废弃 API 实际返回值）**保持未定**；T09A 为生产零改动，T09D 未优化任何逻辑。

- **交付与后续入口（历史）：**[DEV-051](work-items/DEV-051.md) T00—T13 的离线实现／调查随 0.8.0 发布，0.8.1 补齐文档及[0.7.2 四份原件归档](validation/feedback-0.7.2-2026-10-28/manifest.json)，0.8.3 补齐 T02/T06/T07/T08A 指定实机子项，0.8.4 修复首壁阻断并补 T03 五组本机证据，0.8.5 修正折边方向、明确钣金 add 拒绝码并补 T08B/T09A/T09B/T12 证据，0.9.0 交付 T03 板厚实机、T13 两段式回导、T05 第三道定因与 T09D 基准。历史分析按[0.7.2 续版计划](development/0.7.2-FEEDBACK-PLAN-2026-10-28.md)、[原0.7.0 总计划](development/0.7.0-FEEDBACK-PLAN-2026-10-28.md)与[派发表](development/0.7.0-FEEDBACK-TASKS-2026-10-28.md)及[逐章映射](validation/feedback-0.7.2-2026-10-28/MAPPING.md)核对；**0.8.5 时点的「十个离线提交尚未合 main、未发布、无实机验收」为该时点事实，已由 0.9.0 发布取代**。T05 四壁 2/4、relief 去料未证实；T05/T06 原件缺失，T08C 无原图。BUG-085 根因未定，WorkBuddy 未执行。

- [0.6.1 两份反馈后续 PATCH 计划](development/0.6.1-FEEDBACK-PLAN-2026-10-27.md)已按用户指派由 [DEV-049](work-items/DEV-049.md) 汇总，目标为下一未占用 PATCH（暂定 0.7.2，执行前重新核对占用）；[T00—T08 派发表](development/0.6.1-FEEDBACK-TASKS-2026-10-27.md)列出依赖、步骤、共享接口与验收。两份[原件](validation/feedback-0.6.1-2026-10-27/manifest.json)已逐字节归档，[逐章映射](validation/feedback-0.6.1-2026-10-27/MAPPING.md)覆盖 32 个章节与 5 条回复请求。T00 文档基线、T01 断连离线核对（结论：证据不足、**根因未定**）、T02 开发检查超时、T03 安装误报、T04 原斜槽六例、T05 多环/预览查缺、T06 种子驱动与 15+2 均已完成，记录见 [T00](development/DEV049-T00-ACCEPTANCE.md)—[T06](development/DEV049-T06-ACCEPTANCE.md)；2026-10-28 实机：T04 六例经 [BUG-087](work-items/BUG-087.md) 修复后 6/6 通过、T06 15+2 全部通过（T05 差项实机仍未跑）；T07 文档收口、T08 集成与发布已完成，本批随 0.7.2 交付。本批新登记 [BUG-085](work-items/BUG-085.md)（断连调查）、[BUG-086](work-items/BUG-086.md)（安装误报）、[DEV-050](work-items/DEV-050.md)（开发检查超时）。不新增工具（保持 94）；主干 `d2e37b0` 与已发布 `v0.7.1`（`ffa0a43`）的差异由 0.7.2 覆盖（GAP-1/GAP-2），不宣称 `d2e37b0` 属于 0.7.1 附件；DEV-049 已移入[完成档案](BACKLOG_COMPLETED.md)。

- [0.6.0 四份反馈后续 PATCH 计划](development/0.6.0-FEEDBACK-PLAN-2026-10-27.md)已按用户选择保存并由 [DEV-048](work-items/DEV-048.md) 汇总，目标版本 0.7.1（已发布）；[T00—T05 派发表](development/0.6.0-FEEDBACK-TASKS-2026-10-27.md)列出依赖、步骤、共享接口与验收。四份[原件](validation/feedback-0.6.0-2026-10-27/manifest.json)已逐字节归档，[逐章映射](validation/feedback-0.6.0-2026-10-27/MAPPING.md)覆盖 61 个章节与 11 条回复请求。T00 文档基线、T01 sidecar 完整性/同名校验/回退诊断、T02 拒绝后引用生命周期、T03 工作卡与发布检查回填、T04 Right 面 ±Z 定向实机、T05 集成与交付均已完成；本批已随 0.7.1 发布（`ffa0a43`，标签 `v0.7.1`）并移入[完成档案](BACKLOG_COMPLETED.md)。本批不新增工具（保持 94）、不重做 0.7.0 已交付能力；仅开发者离线与本机 Creo 12.4 按范围验收，不要求 WorkBuddy，旧现场与 BUG-001 会话限制保持。分类与唯一 ID 统计已按实际行回填，见下节。

- [0.5.2 三份反馈完整交付计划](development/0.5.2-FEEDBACK-PLAN-2026-10-26.md)目标 0.7.0，由 [DEV-047](work-items/DEV-047.md) 汇总；[T00—T13 派发表](development/0.5.2-FEEDBACK-TASKS-2026-10-26.md)的依赖、接口与验收已按计划执行。T00—T13 已完成并随 0.7.0 交付（main `2a78358`，四附件见 [Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0)）；本批仅开发者离线与本机 Creo 12.4 实机验收，WorkBuddy 经用户 2026-10-26 决定未执行，外部 Creo 9/10 未复测，旧现场与 BUG-001 会话限制保持。DEV-047 已移入[完成档案](BACKLOG_COMPLETED.md)；[BUG-084](work-items/BUG-084.md) 的 Right 面纯 Z U 轴已由 DEV-048 T04 在 0.7.1 取得实机证据（实际帧、800 mm³、保存重载），其余原构型与外部环境范围仍待取证。

- [0.5.0反馈整合计划](development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)（三份[原件](validation/feedback-0.5.0-2026-10-22/manifest.json)已逐字节归档）：第一批证据、状态与正确性由 [DEV-046](work-items/DEV-046.md) 收口（BUG-080 装配变换单位契约与 FEAT-006 收养拒绝逐特征诊断已随 0.5.2 交付，验收范围见卡）；第二批可靠装配重建管线（[FEAT-048](work-items/FEAT-048.md) 按路径/批量收养，矩阵入参归 FEAT-012/BUG-045，Task 4 已完成开发者实机验收，WorkBuddy 经用户取消未执行，多组件单作业批量装配官方示例与验收归 FEAT-008 现有 `creo_execute_plan`）；第三批约束保真、比对与运维（[FEAT-049](work-items/FEAT-049.md) 约束回放、[FEAT-050](work-items/FEAT-050.md) 装配比对、DEV-027 显式世代回收）。原环境 Creo 10 证据与本机 Creo 12 证据分开记录，报告预计性能收益仅作建议。

- [0.5.0/0.5.1 Creo 9 反馈计划](development/0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md)：BUG-079 就地改弧半径修复已随 0.5.1 交付，BUG-082 根因修复、完整编辑回滚证据与 FEAT-030 受控引用/manifest 测试驱动适配随 0.6.1 交付；编辑专项 16/16 通过。[BUG-081](work-items/BUG-081.md) 保留 MCP 拒绝时序、[BUG-083](work-items/BUG-083.md) 保留原生非法分支与外部验证；[FEAT-030](work-items/FEAT-030.md)/[BUG-034](work-items/BUG-034.md) 的九种子矩阵受 2026-10-26 断连事故阻断，现由 [DEV-049](work-items/DEV-049.md) T06 交付 15+2 离线驱动与清单核对（实机未执行），补跑须满足 BUG-001 会话纪律；事故根因按 T01 结论为证据不足、未定。Creo 9 -16、种子生产来源/重生成、外部复验与 WorkBuddy 继续开放；哈希校验不等于建模通过。

- [0.4.6反馈整合计划](development/0.4.6-FEEDBACK-PLAN-2026-10-21.md)（三份[原件](validation/feedback-0.4.6-2026-10-21/manifest.json)已归档补录，0.4.7 发布后开工）分两批推进：第一批盘点口径补齐与证据收口（DEV-027 loader/payload 盘点区分引用三态、FEAT-046/FEAT-043/044/DEV-027 外部通过子项关闭、DEV-045 附件名 0.4.7 起定名核对通过、BUG-077 原环境复测单列）；第二批 FEAT-045 装配只读检查（新增 `creo_inspect_session_assembly`）按 MINOR（0.5.0）随版交付，四类受限场景与外部复核按卡开放。矩阵放置、重建编辑与装配整体收养为后续路线不随本轮实施。
- [0.4.4反馈整合计划](development/0.4.4-FEEDBACK-PLAN-2026-10-21.md)（覆盖 v0.4.4 构建验收与 v0.4.5 运行反馈两份[原件](validation/feedback-0.4.4-2026-10-21/manifest.json)）：BUG-077/FEAT-047/DEV-044 五组验收已随 0.4.7 交付（[发布核对](validation/RELEASE-0.4.7.md)）；BUG-078（恢复 accept 路径 Backup 稳定 -1）自该计划登记待修。
- [0.4.3反馈完善计划](development/0.4.3-feedback-improvement-plan-2026-10-21.md)两批已随 0.4.6 交付（用户指定 PATCH，含新工具例外；[发布核对](validation/RELEASE-0.4.6.md)）：BUG-076/BUG-057/FEAT-046/FEAT-043/044/DEV-027 的单元、构建与本机实机核心+改动点验收完成；各条剩余原环境、外部锁复验、擦除矩阵与 WorkBuddy 黑盒按卡推进。
- 恢复、回调生命周期、接管/枚举与磁盘打开仍有验收空缺，按各卡剩余动作推进；已发布不等于整项完成。
- 其他建模失败先取得最小输入和受测环境再复现；功能候选与工程迁移按下表规划，不增加双版本验收门槛。
