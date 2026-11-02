# 开发入口

**2026-11-02 第十一轮反馈归档与登记（DEV-062 / R11）：** `C:\Users\Administrator\Downloads\0.11.0` 三份 v0.11.0 验收原件**逐字节归档 3/3**（长度与 SHA256 一致），见[归档清单](validation/feedback-0.11.0-2026-11-01/manifest.json)与[逐章映射、已闭环依据与缺件](validation/feedback-0.11.0-2026-11-01/MAPPING.md)；与 0.10.0 两批归档并存，不合并。新登记 [BUG-104](work-items/BUG-104.md)（旧检查点无 `appearance` 基线的补基线路径）、[BUG-105](work-items/BUG-105.md)（零变更失败后的显式恢复动作）、[FEAT-056](work-items/FEAT-056.md)（色板零件名键与 `random:true`）、[BUG-106](work-items/BUG-106.md)（同名会话解锁链路，仅登记）、[DEV-063](work-items/DEV-063.md)（擦除回执体量与预览视角字段，仅登记），并补 FEAT-052/BUG-101/BUG-102/BUG-088/BUG-089/DEV-061 增量。已闭环项（BUG-089 主闸门、DEV-061 仓库级断言、BUG-090 编译证据、FEAT-035 `depth_basis`、FEAT-052 卡状态、0.10.1 三键枚举、draft 双 flip、`weldability` 风险标记）按 MAPPING §三 只记依据不重复派工。分批见 [R11 分窗计划](superpowers/plans/2026-11-02-feedback0110-r11-plan.md)。同批完成 BUG-104/BUG-105/FEAT-056 的离线实现与专项单测（+27 项，全量 2158 项 0 失败；`dev_check` `success=true`；`bridge.py build` exit 0），实机验收、提交、合入与发布另排。本轮未连接 Creo/MCP、未合 main、未发布。

**2026-11-02 第十轮反馈归档与登记（DEV-060 / R10）：** `C:\Users\Administrator\Downloads\0.10.0` 三份 v0.10.0 验收原件**逐字节归档 3/3**（长度与 SHA256 一致），见[归档清单](validation/feedback-0.10.0-2026-10-31/manifest.json)与[逐章映射、已闭环依据与缺件](validation/feedback-0.10.0-2026-10-31/MAPPING.md)；与晚间包 `feedback-0.10.0-2026-11-01` 并存，不合并。新登记 [BUG-101](work-items/BUG-101.md)（近容差端点不可焊与失败归因）、[BUG-102](work-items/BUG-102.md)（draft 倒角圆角面回归与 `flip` 语义）、[BUG-103](work-items/BUG-103.md)（水平底板 Z=0 长边壁面归属）、[DEV-061](work-items/DEV-061.md)（种子摘要仓库级闸门），并补 FEAT-014/FEAT-035/FEAT-051/BUG-049/BUG-090 增量。已闭环项（FEAT-051 体积回报、0.10.1 三键枚举、空件预览、BUG-047、FEAT-031、BUG-045、BUG-089 主闸门、`wall_contour_status`）只记依据不重复派工。分批见 [R10 分窗计划](superpowers/plans/2026-11-02-feedback0100-r10-plan.md)。登记轮本身未连接 Creo/MCP、未跑产品测试、未合 main、未发布；后续实现、实机与发布见下方 0.11.2 条目。

**2026-11-01 晚间反馈归档与登记（DEV-053 接续 / Q00）：** 0.10.0 晚间反馈包**十件原件逐字节归档**（10/10 长度、SHA256 与字节一致），见[归档清单](validation/feedback-0.10.0-2026-11-01/manifest.json)与[逐章映射、缺件表](validation/feedback-0.10.0-2026-11-01/MAPPING.md)。新登记 [BUG-096](work-items/BUG-096.md)（失败作业遗留未保存会话对象占用模型名，交叉关联 BUG-012/FEAT-018）、[BUG-097](work-items/BUG-097.md)（斜面草图 UV 映射与特征完成失败 L1/L2，关联 FEAT-010/BUG-087/BUG-095）、[FEAT-053](work-items/FEAT-053.md)（`datum_plane` 三点定面 `thru_points`，关联 FEAT-008）；补建缺失的 [FEAT-009](work-items/FEAT-009.md)、[FEAT-010](work-items/FEAT-010.md) 工作卡（沿用既有 ID，不另登新编号）。Q 任务负责人：Q02→写程序高手、Q03→代码编写者、Q04→codex代码，其余 unassigned。本轮为文档登记与归档：未连接 Creo/MCP、未跑产品测试、未改产品代码、未合 main、未发布。

**2026-11-02 当前正式版（DEV-064 / 0.11.4，PATCH）：** 0.11.1 第十二轮反馈（R12）已交付——`C:\Users\Administrator\Downloads\0.11.1` 两份原件逐字节归档 2/2 与[逐章映射](validation/feedback-0.11.1-2026-11-02/MAPPING.md)（[DEV-064](work-items/DEV-064.md)）；`tools/generate_constants.py` 的 `HEADERS` 改为存在性门控，Creo 10 缺 `Probbl.h` 不再中断构建（[BUG-107](work-items/BUG-107.md)）；草图创建/编辑新增顶层 `sketch_shifted` 与 `geometry_deviation.shift_detected`/`accepted_by_request`，坐标模式以投影基准线钉住原点（[BUG-108](work-items/BUG-108.md)：可观测已交付，平移未复现、定因未定）；save origin 与 erase `modified` 两处拒绝补可执行链路（[BUG-106](work-items/BUG-106.md)）；补建 [FEAT-054](work-items/FEAT-054.md)/[FEAT-055](work-items/FEAT-055.md) 工作卡，台账 161→164 行。公开工具仍 **95**。全量单元 **2 185 项 0 失败**（新增 27 项）、`dev_check.py --work-item 0.11.1-feedback-r12` `success=true`、`bridge.py build` exit 0（执行器 13 276 672 B / `8ab6978e…`）。本机 Creo 12.4.0.0 实机：4 个细长三角条坐标草图 + 挤出 5 mm 全部成功、保存重载 true、未复现 0.004 mm 平移；**Creo 9/10 实机与 WorkBuddy 未测**。合入 `a4df690` + 补提交 `0bb3998`（首次提交漏暂存 `native/`，同日更正并移动当日标签）、标签 `v0.11.4`、[Release 431483437](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.4)（源码包 `6e9e86c0…`、种子包 `666f9c80…`，四件远端核对一致）。见 [0.11.4 版本说明](RELEASE_NOTES_0.11.4.md)与[发布记录](validation/RELEASE-0.11.4.md)。
**2026-11-02 上一版（DEV-062 / 0.11.3，PATCH）：** 0.11.0 第十一轮反馈批（R11）的离线交付已发布——三份原件逐字节归档 3/3 与[逐章映射](validation/feedback-0.11.0-2026-11-01/MAPPING.md)（[DEV-062](work-items/DEV-062.md)）；`creo_recolor_assembly` 显式 `refresh_baseline` 旧检查点补基线（[BUG-104](work-items/BUG-104.md)，回执 `baseline_source`、`dry_run` 给 `next_action`）；零变更失败保持 `ready` 并新增 `ack_no_mutation` 纯注册表恢复（[BUG-105](work-items/BUG-105.md)）；色板唯一标签键与 `random:true`（[FEAT-056](work-items/FEAT-056.md)）；台账卡头与分类修正（155→161 行）。公开工具仍 **95**。全量单元 **2 158 项 0 失败**（新增 27 项）、`dev_check.py --work-item 0.11.0-feedback-r11` `success=true`、`bridge.py build` exit 0。**本版未执行实机验收**；Creo 9/10 实机与 WorkBuddy 黑盒未测。合入 `7b80a4a`、标签 `v0.11.3`、[Release 431414809](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.3)（四附件远端哈希核对一致）。见 [0.11.3 版本说明](RELEASE_NOTES_0.11.3.md)与[发布记录](validation/RELEASE-0.11.3.md)。
**2026-11-02 前一版（DEV-060 / 0.11.2，PATCH）：** 0.10.0 第十轮反馈批的离线交付已发布——草图 `profile.weldability` 端点可焊性风险标记（阈值沿用 `EXACT_TOLERANCE_MM=1e-9` mm，只报告不拒绝）与原生拉伸失败簇内间隙归因（BUG-101）、draft `requested_flip`/`effective_flip` 与 `draft_failure` 分类（BUG-102）、孔 `depth_basis` 三键（FEAT-035 增量）、种子摘要仓库级闸门（DEV-061），公开工具仍 95。本机 Creo 12.4.0.0 实机（2026-11-02，用户授权）：8.215e-7 mm 间隙 + 拉伸 5 mm 成功（报告方 Creo 10 的 `-1` 未复现，故字段定位为风险标记）、draft 10°/`flip=false` 回读 `effective_flip=true`（+264.49 mm³）、YZ 底板 42920 mm³ 且四条下边 104–107 全 `eligible`、对报告方失败边 106 挂折边成功；全量单元 2 131 项 0 失败、`dev_check.py --work-item R10` success、`bridge.py build` exit 0。合入 `76ddb83`、标签 `v0.11.2`、[Release 431347397](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.2)（四附件远端哈希核对一致）。未测：报告方 Creo 10 现象与 draft 元素树 A/B、盲孔 `depth_basis` 实机回执、Creo 9/10 实机与 WorkBuddy 黑盒。见 [0.11.2 版本说明](RELEASE_NOTES_0.11.2.md)与[发布记录](validation/RELEASE-0.11.2.md)。
**2026-11-02 前一版（DEV-053 / 0.11.1，PATCH）：** 0.10.0 晚间反馈批（Q00–Q15）已交付——失败模型清理与同名复用（BUG-096，`failed_model_cleanup` 回执 + `rollback_status` 终态字段）、斜面草图修复（BUG-097/098，无精确垂直基准面时自动建辅助基准面）、三点定面 `through_points`（FEAT-053）、草图显式容差 `geometry_tolerance_mm`（FEAT-010 增量）、作业 `stage` 上报（FEAT-033 增量）、结果有界回执与分页（FEAT-008 增量）、背靠背提交竞态修复（BUG-100 通道预约）；BUG-099 定因为实验性 worker 与源码不一致（无代码变更，随版披露）。本机 Creo 12.4.0.0 四轮实机（[DEV-053-Q15-live 记录](validation/DEV-053-Q15-live-2026-11-01.md)）与全量 2096 项单测、dev_check 通过；WorkBuddy 黑盒（[提示词已备](validation/WORKBUDDY-0.11.1.md)）与 Creo 9/10 未测。见 [0.11.1 版本说明](RELEASE_NOTES_0.11.1.md)与[发布记录](validation/RELEASE-0.11.1.md)。
**2026-11-01 前一版（FEAT-052 / 0.11.0，MINOR）：** 装配按零件族上色已交付——公开工具 `creo_recolor_assembly`（自动分族/显式族表/`dry_run` 只读预览）与计划操作 `recolor_assembly`，`creo_list_components` 三态 `appearance` 字段，公开工具 94→95。本机 Creo 12.4.0.0 实机验收 run `assembly_appearance_live_20261101T060336Z558b3546`（80 组件/12 族 28/28 检查通过）加装配 pipeline 与 T07 预览回归；WorkBuddy 黑盒与 Creo 9/10 未测。见 [0.11.0 版本说明](RELEASE_NOTES_0.11.0.md)、[发布记录](validation/RELEASE-0.11.0.md)与[工作卡](work-items/FEAT-052.md)。
**2026-11-01 前一版（DEV-053 / 0.10.1，PATCH）：** P00–P09/P10/P12/P14 的离线部分与本版范围实机验收已完成（P02/P03/P06 收口、P04 闸门、P05 对齐、P09 第一阶段、P10/P12 缺件登记），以 0.10.1 发布；P07/P08/P11 的 MINOR 公开结构在开发分支 `codex/dev053-post0100` 待后续候选交付（0.11.0 已被 FEAT-052 占用）；P13 无动作、P16 等原 TXT。实机 run `post0100_20261031T234309_rel0101`。见 [0.10.1 版本说明](RELEASE_NOTES_0.10.1.md)。
**2026-10-31 历史时点（DEV-053 / P00）：** [五份 0.9.0 原件及逐章映射](validation/feedback-0.9.0-2026-10-31/MAPPING.md)已归档，新增 [DEV-053](work-items/DEV-053.md)、[BUG-094](work-items/BUG-094.md)、[BUG-095](work-items/BUG-095.md)。[P00—P16 总计划](superpowers/plans/2026-10-31-post0100-master-plan.md)当前仅 P00 实施；P01—P16 尚未开始。N12 发布后样本已补满：small 每类 n=3，large 首轮每类 n=2、补轮每类 n=3，分开统计，见 [T09D 补记](development/DEV051-T09D-ACCEPTANCE.md#2026-10-31-发布后补记n12-large-样本已补满追加不改写上文)。FEAT-031 两件装配导出与隔离回导已通过，嵌套/外部引用仍开放；FEAT-033 的性能基准已有实测，公开预算/阶段契约仍未实施。

**2026-10-31 N13 集成与发布准备（DEV-052 / 0.10.0）：** N01—N13 分窗批次已交付。本批交付状态：[FEAT-051](work-items/FEAT-051.md) 已交付（round/chamfer/draft 逐操作体积差与方向/引用应用回报，run2 七夹具实机通过）、[FEAT-035](work-items/FEAT-035.md)/T12 已交付（盲孔 `depth` 改 tip 口径，六例实机通过）、[FEAT-034](work-items/FEAT-034.md)/T02 已交付（创建 5/5+编辑 3/3 实机，`illegal_dir_zero` 反例待查见 [BUG-093](work-items/BUG-093.md)）、[FEAT-008](work-items/FEAT-008.md)/T09B 与 [FEAT-023](work-items/FEAT-023.md)/T09A 已交付（entity_ids/中心线计数、组件身份实机通过）、[FEAT-014](work-items/FEAT-014.md) 有界能力交付（`adjacent_bend_ends` 创建前拒绝；四壁保持开放）、[BUG-049](work-items/BUG-049.md) 诊断交付（`max_endpoint_gap_mm` 等；原件缺失保持开放）、[BUG-088](work-items/BUG-088.md) 文件级定因与图像复核通过（I/O 根因未定保持观察）、[BUG-090](work-items/BUG-090.md) 离线修复交付（函数门控；Creo 10 未验保持开放）、[BUG-091](work-items/BUG-091.md) 调查交付（根因未定）；新登记 [BUG-092](work-items/BUG-092.md)（server.py 子进程残留，待处理）与 [BUG-093](work-items/BUG-093.md)（illegal_dir_zero 待查）。见 [0.10.0 版本说明](RELEASE_NOTES_0.10.0.md)、[0.10.0 发布记录](validation/RELEASE-0.10.0.md)；实机明细见 [七段实机总报告](development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)。

**2026-10-30 接续计划（DEV-052 / N00 文档阶段已交付；本段为 N00 时点记录，N01—N13 已于 2026-10-31 随 0.10.0 交付）：** 用户确认的 0.9.0 最终账已固定为基线；Downloads/0.8.x 的**七份反馈已逐字节归档**并核 SHA256（7/7），缺件清单与逐章映射见 [0.8.x 归档 MAPPING](validation/feedback-0.8.x-2026-10-30/MAPPING.md)。该轮**只登记不实现**：新登记 [DEV-052](work-items/DEV-052.md)（本轮接续汇总）、[BUG-090](work-items/BUG-090.md)（Creo 10 SDK 兼容，待复现）、[BUG-091](work-items/BUG-091.md)（会话挂起/退出调查，待复现）、[FEAT-051](work-items/FEAT-051.md)（round/chamfer/draft 结果可观测性，待规划）。

**该顺序（DEV-051 侧）在 0.9.0 已收口到最终账**：板厚同步、释放回读校验与材料端 oracle、四壁对照设计与 `end_trim_mm` 贯通、弧方向判定与编辑/重载覆盖、组件身份同源、组件标签重载回归（生产零改动）、中心线计数、性能基准驱动与口径、孔型余项、BUG-085 离线证据调查——十个离线提交已随 **0.9.0 正式发布**（标签 `v0.9.0`），其中 T03 板厚与 T13 两段式回导取得本机实机证据，T05 第三道折边定因、T09D 出基准。三个未定因（BUG-085 根因、T05 第三壁/角部内部机理、T13 废弃 API 实际返回值）保持未定；T09D 未优化任何生产逻辑。逐项状态矩阵见 [DEV-051 工作卡](work-items/DEV-051.md#2026-10-30-离线批次十个提交与当前状态矩阵)。

**DEV-052 历史交接入口（N00 时点；当前后续入口见 DEV-053）：** [0.9.0 后续任务与分窗派发表](superpowers/plans/2026-10-30-post090-task-dispatch.md)（N00—N13 的依赖、文件、步骤、验收与固定 ID 映射）。此前 DEV-051 的 2026-10-30 完善计划与阶段卡**保留各自历史时点**，其未闭环子项沿用原 ID 继续有效；DEV-051 批次的实机结果以 [0.9.0 发布记录](validation/RELEASE-0.9.0.md) 为准。

本项目按可交付的 Creo MCP 工具维护，采用功能条目驱动、短分支和分批整理。日常开发从 [统一台账](BACKLOG.md) 选择条目；新增工作先登记，复杂条目复制 [模板](templates/WORK_ITEM.md)。开发准入对小修复同样适用，内容可精简为几行。

当前服务／源码版本以 [version.py](../version.py) 为准，为 **0.11.4 / 95 个公开工具**。0.11.1 第十二轮反馈批（R12）已随 0.11.4 交付；归档、逐章映射与登记 ID 见[本轮登记映射](validation/feedback-0.11.1-2026-11-02/MAPPING.md)，分批见 [R12 计划](superpowers/plans/2026-11-02-feedback0111-r12-plan.md)，发布见 [0.11.4 版本说明](RELEASE_NOTES_0.11.4.md)与[发布记录](validation/RELEASE-0.11.4.md)。开放项：[BUG-108](work-items/BUG-108.md) 平移定因与 Creo 10 复现、[BUG-107](work-items/BUG-107.md) Creo 10/9 实机构建、[BUG-106](work-items/BUG-106.md) 链路复测、BUG-104/BUG-105/FEAT-056 的实机验收、[DEV-063](work-items/DEV-063.md) 擦除回执/视角说明、Q08–Q10 三曲面链（[FEAT-055](work-items/FEAT-055.md)，探针路线不成立待重规划）、Q11 四带及后续分级（[FEAT-054](work-items/FEAT-054.md)）、WorkBuddy 黑盒（[提示词](validation/WORKBUDDY-0.11.1.md)）、BUG-091 根因。

**0.10.0 历史验收摘要（以下保留原环境与当时未测项，BUG-092/093 指定范围后来已在 0.10.1 收口）：** 当时服务／源码版本为 **0.10.0**（DEV-052 N13 集成批次：FEAT-051 round/chamfer/draft 逐操作体积差与方向/引用应用回报、FEAT-008 草图结果 `entity_ids`、FEAT-014 折边邻接折弯端 `adjacent_bend_ends` 拒绝语义，含 FEAT-035/T12 盲孔 tip 口径、FEAT-034/T02 编辑弧回显、FEAT-008/T09B 中心线计数修复与 BUG-049 端点诊断，MINOR 性质，公开工具仍 94）。本机 Creo 12.4.0.0 实机（2026-10-31 第二轮）：N04 七夹具、N06 邻接拒绝终验（RUN PASSED）、N08/N09/N10 六例、N11（含人工图像复核）通过；N07 创建 5/5+编辑 3/3 通过（`illegal_dir_zero` 反例待查）；N12 发布时 large 每类 n=2，发布后补轮每类 n=3（small 每类 n=3；两轮分开统计）。四壁不支持、Creo 9/10 未验。见 [0.10.0 版本说明](RELEASE_NOTES_0.10.0.md)、[发布记录](validation/RELEASE-0.10.0.md)；0.9.0 及更早范围见 [0.9.0 版本说明](RELEASE_NOTES_0.9.0.md)、[发布记录](validation/RELEASE-0.9.0.md)与 [0.8.5 版本说明](RELEASE_NOTES_0.8.5.md)、[发布记录](validation/RELEASE-0.8.5.md)。

**以下为 DEV-052 的历史接续范围，当前状态见上方入口及各工作卡。** 前一开发批次为 **DEV-052**（0.9.0 之后的反馈接续与分窗交付）：N00 文档阶段（七份 0.8.x 原件归档与映射、四个新固定 ID 入账）与 **N01—N13 分窗批次已随 0.10.0 交付**（各 ID 状态见上段，实机明细见[七段实机总报告](development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)）。**仍开放**：四壁/角部与 relief 材料几何、`end_trim_mm` 语义、T05/T06/T08C 缺件、BUG-049 原案与内核容差、BUG-088 I/O 根因、BUG-090 Creo 10 定向编译、BUG-091 根因、BUG-092（server.py 子进程残留）、BUG-093（illegal_dir_zero）与 N07 恢复编辑复跑；WorkBuddy 未执行、Creo 9/10 未验。前批 DEV-051 的 T00—T13 随 0.8.0—0.9.0 交付：T02/T06/T07/T08A 的指定实机子项随 0.8.3 补证，0.8.4 修复首壁阻断并补 T03 五组证据，0.8.5 交付折边方向和钣金 add 边界及 T08B/T09A/T09B/T12 证据，0.9.0 交付 T03 板厚实机、T13 两段式回导、T05 第三道定因与 T09D 基准。**四壁、relief 几何、T13 嵌套引用与 T05/T06 原件仍开放；WorkBuddy 未执行；Creo 9/10 未验**。前批 DEV-049 已随 0.7.2 交付并移入[完成档案](BACKLOG_COMPLETED.md)。

本机联调只使用指向 E 盘项目的 `MCP_CREO_MechDog_dev`。先按[根级规范](../AGENTS.md#本机开发联调补充2026-10-17用户要求)核对卡死调查与会话可操作条件，满足门槛后再安排 Toolkit 连接或故障注入；不得擅自结束 Creo 或清除 unknown 保护。文档分类和条目关闭不解除这些限制。

## 每次开发的顺序

台账按当前状态和下一步分类；观察项收到新证据后再转回调查，不列作当前发布阻断。执行经过写入工作卡或验证记录，主台账保留剩余工作和详情入口。

1. 明确条目 ID、问题或目标、包含与排除的范围、验收命令、预期结果、目标环境。报告中的问题先复现，区分现象与推测根因。
2. 检查工作区和现有条目；从可交付的 `main` 建立 `codex/<条目>-<主题>` 短分支。一个分支围绕一个条目或一组明确相关的条目。
3. 实现最小完整改动。格式清理、路径迁移、行为修改分开提交；每次目录迁移同时核对安装、后台入口、资源和运行数据的位置、源码打包。
4. 执行下述检查。校验或保护逻辑补回归用例；原生建模变更还需对应 Creo 实机测试。
5. 更新条目状态、验证证据和能力边界；提交说明注明 ID、具体行为及验证。PR 使用仓库模板；合入 `main` 前确定未发布的目标版本，同步版本元数据及版本说明，完成适用检查与发布准备。
6. 每次合入或直接提交到 `main`，均须在同一次交付流程按 [发布规则](development/RELEASING.md#合入-main-必须同步发布) 发布对应版本的 GitHub Release（包括文档和工程配置变更）。核对主干提交、版本标签、附件及 SHA256，并回填 Release 链接；Release 未发布或附件未齐则交付未完成。开发分支上的普通提交不要求发布。

## 配置开发环境

Windows x64、Python 3.12+。已有源码安装环境可直接安装开发依赖；只运行单元与语言检查时无需安装 Creo、SDK 或许可。正式建模安装可使用 Creo 9、10 或 12 及匹配 SDK；Creo 9 的编译与运行时状态见[兼容矩阵](COMPATIBILITY.md)。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools\dev_check.py
```

`requirements-dev.txt` 引用锁定的运行依赖、固定 Ruff 和 clang-format 版本，并通过 `-e .` 安装本地源码包。`pyproject.toml` 的构建后端版本也已锁定。正式建模安装继续使用 `setup.ps1`，详见 [安装说明](INSTALL.md)。检查入口以脚本位置定位仓库，工具在仓库目录执行。

`.gitattributes` 固定 Python/C++ 和新开发文档换行为 LF，避免 Windows 检出设置导致格式检查差异；已有历史文档沿用原换行，第三方与原生 PRT/ASM 等二进制禁止文本转换。

## 检查与现有问题基线

默认命令执行 Ruff 检查、Python/C++ 格式检查、历史基线比较和全部 Python 单元测试。输出 `build/development_check.json` 与 `build/unit_test_report.json`，失败返回非零退出码。Windows CI 执行同一入口，保存报告，不连接 Creo。

现有压缩代码暂记在 [风格基线](development/style-baseline.json)。它是未完成的整理工作，不是语言规范已全部通过的证明：

- Ruff 问题按文件、规则、消息、源代码行及次数匹配，行号移动不会误报；新增问题或同类问题次数增加会失败。
- 未格式化文件以规范化换行后的内容 SHA256 匹配；内容变化后必须通过格式检查。处理旧模块时先单独做格式整理，再改行为。
- 已清理问题可以消失，基线不会因此阻塞检查；随后在独立提交中删去对应基线项，防止旧问题被再次容许。
- 工具版本或配置改变、工具缺失、语法或配置错误、单测失败都会使检查失败。不能用自动更新基线规避检查。
- 基线变更必须关联工作条目并单独审查，审查新增容许项的具体原因；CI 从不生成或更新基线。

```powershell
# 仅检查语言，不构成单元或原生验收
.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit
# 忽略历史容许项；当前会明确暴露全部存量问题
.\.venv\Scripts\python.exe tools\dev_check.py --strict --skip-unit
# 仅在审查工具升级、配置修改或初始欠账后显式执行
.\.venv\Scripts\python.exe tools\dev_check.py --write-baseline --reason 'DEV-xxx: 已审查的具体原因'
```

单元阶段使用独立子进程预算，默认 **900 秒**，可用 `--unit-timeout-seconds` 覆盖；0、负数或非整数在参数解析阶段即以退出码 2 拒绝，`--skip-unit` 只跳过单元阶段、不取消预算校验。报告记录 `unit_test_timeout_seconds`，继续区分 `passed`/`failed`/`timed_out`，`timed_out` 永远不会被报告为 success。不要用拆开的 `tools/test_unit.py` 结论代替统一入口（[DEV-050](work-items/DEV-050.md)、[T02 记录](development/DEV049-T02-ACCEPTANCE.md)）。

```powershell
.\.venv\Scripts\python.exe tools\dev_check.py --unit-timeout-seconds 1200 --work-item DEV-050
```

安装脚本的外部 Python 调用统一走 `setup.ps1` 的 `Invoke-PipStep`：函数内局部把 `$ErrorActionPreference` 设为 `Continue` 并在 `finally` 恢复，调用前清空 `$LASTEXITCODE`，之后立即读取真实退出码。判定只看退出码——0 继续，启动失败/无退出码/非零按原语义失败并保留原始错误与码；stdout/stderr 不吞、不按 `[notice]` 文本猜测结果，也不全局降低错误偏好。新增安装步骤的外部进程调用应沿用该封装；回归见 `tests/unit/test_setup_native_stderr.py`（[BUG-086](work-items/BUG-086.md)、[T03 记录](development/DEV049-T03-ACCEPTANCE.md)）。

语言细则见 [编码规范](development/CODING_STANDARD.md)，迁移路线见 [架构计划](development/ARCHITECTURE.md)。

## DEV-049 批的离线与实机驱动

DEV-049 新增/收紧的三个驱动都**默认离线**：不给实机开关时不创建 MCP 客户端、不连接 Toolkit，只校验输入并写报告。实机必须同时给出 `--live` 与 `--confirm-session-usable`，且仍须人工核对 BUG-001 会话条件；单一开关或历史 `ready` 都不能替代核对。阶段记录见 [T04](development/DEV049-T04-ACCEPTANCE.md)、[T05](development/DEV049-T05-ACCEPTANCE.md)、[T06](development/DEV049-T06-ACCEPTANCE.md)。

| 驱动 | 用途 | 参数与门槛 | 离线结论不等于 |
| --- | --- | --- | --- |
| `tools/test_dev049_tilted_cut.py` | R20／54°／4×6 原斜槽六例（autodim/coordinates × positive/negative/symmetric），独立解析+数值积分 oracle | 默认离线；`--output` 指定新报告（默认 `build/dev049_t04/<run_id>/report.json`，启动时拒绝覆盖已存在报告）；单向 238.390260127791、双向 476.780520255582 mm³，绝对误差 ≤0.01，并核对实际帧与切口分布 | 六例实机通过；当前六例实机未执行 |
| `tools/test_dev049_profile_replay.py` | 多环输入查缺后的替代回放（2 圆对照、5/10 四弧环 cut），面积×厚度 oracle | 默认离线、双开关同上；报告声明 `original_case_replay=not_possible_missing_attachments`、`replacement_verification=true` | 原 `gear10.json` 案例回放；原输入缺失，替代用例实机未执行 |
| `tools/test_installation_loft.py` | 种子矩阵 15 正例 + 2 负例 | 保留 `--seed-library`；默认离线；实机需 `--live --confirm-session-usable`；新增可重复 `--case NAME`（未知或重复名称在连接前以退出码 2 拒绝）与 `--output PATH`（默认 `build/dev049_t06/<run_id>/report.json`，拒绝覆盖）；逐阶段持久化，不做自动重放/resume | 15+2 实机通过；不同 `source_fingerprint` 的报告不得合并，0.6.1 的 five_smooth 成功不移植 |

全部驱动的报告都写入唯一运行目录并带 provenance（提交、分支、dirty、源码指纹）；异常与失败报告同样保留，不覆盖历史文件。

## 验收级别

| 改动 | 本次必须取得的证据 |
| --- | --- |
| 文档、开发配置 | 文档引用与台账一致性、适用工具配置可加载；涉及检查或打包时运行其回归用例 |
| Python 校验、调度、登记、保护逻辑 | 统一检查、对应回归；外部进程/会话行为需要额外实机验证 |
| 长度、坐标、变换或体积接口 | 记录外部输入与实际测量的单位名、毫米换算、原始查询码及未知值；至少覆盖毫米、英寸、混合和单位未知场景。同层对象可共享单位证据，未执行的查询不能报成功 |
| C++ 或建模行为 | 上述检查、匹配 SDK 构建、对应 `tools/test_*.py`、原生几何及尺寸断言、保存擦除重载验证；失败路径涉及回滚时验证回滚 |
| 路径或布局迁移 | 单元检查、安装和客户端入口、后台任务、资源/数据根目录、源码包重新解压验证；涉及原生部分补实机验收 |
| 发布 | 发布回归清单、环境与源码标识、版本一致性、附件与校验和；明确本轮未测项 |

原生修改验收必须检查任务成功、原生特征有效、几何断言通过、`saved_file_reloaded_and_verified == true`。超时、`unknown_outcome`、拒绝非法输入以及仅能编译均不能计为建模成功。历史证据保留原日期和环境，只能在明确证明实现一致且说明复用范围时引用，不能改名冒充本次测试。

每份新证据记录条目 ID、版本、提交号、工作区是否有修改、实际受测源码指纹、测试时间、Windows/Python/Creo/SDK/编译器环境、命令、结果和未测范围。工作区有修改时，提交号不能单独代表受测内容。

## 功能与支持声明

当前开发与发布按本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 的实际改动范围验收。Creo 10 独立复测、双版本验收及正式基线不作为完成、合入或发布门槛；其他环境收到具体反馈后，登记或沿用 ID 跟进。Creo 9 与匹配 Toolkit 9 已纳入支持／要求范围，编译探测修复已实现，但本机无 Creo 9 SDK，实机编译和建模运行时均未验收。各环境历史结果及未测范围按[兼容矩阵](COMPATIBILITY.md)记录，不将本机成功外推为其他环境通过。运行接口范围以 `capabilities.py` 为基础，能力变更同时更新工具描述、README 和有关文档。台账管理未来工作，历史版本说明保存已发布范围。

`creo_capabilities.support_status` 应按当前实际启用工具与动作声明，compact/full 分页一致且各响应不超过 32 KiB。`release_status` 从本地 `version.py` 的版本后缀判断 stable、pre-release 或 unknown；`complete_creo_coverage` 独立说明范围，`update.is_prerelease` 只描述最新远端版本。新接口验收须分别验证本地版本与远端缓存未知、过期时的表述。

## WorkBuddy 测试约定

2026-10-13 用户明确要求：本项目所有“WorkBuddy 测试”均指直接使用已连接的 MCP 工具，对最终用户可见行为做黑盒验收，不查看源码。该约定已写入 [根级代理规范](../AGENTS.md)，后续任务和测试提示词均遵循，适用范围不限于 BUG-002。

WorkBuddy 测试提示词只包含 MCP 操作场景、输入、预期结果和报告要求，不要求阅读仓库、检查 Git、查看本机配置、修改源码或执行本地测试命令。环境、会话、可见工具与服务版本通过 MCP 公开接口确认；接口未提供的信息记为“无法确认”。版本号本身不足以证明具体修复已部署，部署身份可由测试发起者提供，不能据此要求 WorkBuddy 检查源码。

最终结果记录实际工具调用与输入、任务/模型 ID、终态、几何和参数、保存重载、revision、回滚及原始错误。并发场景须实际并行调用；不能并行时记为“并发未验证”。文件占用注入、重试预算/次数和临时文件清理等内部机制，若无法通过 MCP 观察，则不纳入 WorkBuddy 的通过结论。

开发者仍按前述要求执行源码单元、开发检查、压力和实机脚本。开发证据与 WorkBuddy 最终 MCP 验收分别记录；本约定不表示已经执行 WorkBuddy 测试。用户明确调整当次范围时遵循当次要求。
