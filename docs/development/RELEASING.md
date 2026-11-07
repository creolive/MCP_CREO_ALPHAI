# 分支、版本与源码发布

`main` 保持可交付，开发使用 `codex/<条目>-<主题>` 短分支。提交标题指明 ID 和具体改变，例如 `BUG-002: retry atomic registry replacement`；无需引入复杂的长期分支或强制 Conventional Commits。

## 合入 main 必须同步发布

自 2026-10-16 起，每次将变更合入或直接提交到 `main`，必须在同一次交付流程中生成并发布对应版本的 GitHub Release。功能、修复、文档和工程配置变更均适用；开发分支上的普通提交不要求发布。

1. 合入前确定尚未发布的目标版本，按下述版本约定同步 `version.py`、相关版本元数据和版本说明；已有版本已发布时必须递增版本号，不能复用旧版本承载新的主干变更。
2. 合入前完成下述适用发布门槛和附件准备；合入后，以本次变更对应的实际主干提交建立 `v<版本号>` 标签，版本号必须与该提交的 `version.py` 一致。最终附件必须由该提交源码生成。
3. 发布同名版本的 GitHub Release，附版本说明、验收摘要、实际环境、未测范围、源码包、种子包及各自 SHA256。Pre-release 按项目成熟度设置；草稿不算已发布。
4. 核对远端主干提交、标签指向、Release 版本及附件校验和，并在 PR 或交付记录中回填提交号、版本号、Release 链接和附件校验结果。

仅完成合并、推送或标签不能视为交付完成。Release 发布失败或附件缺失时，记录原因并继续补齐；完成报告必须明确尚未交付，不能将发布另列为可选后续工作。历史发布与验收记录保留原日期和实际范围。

## 版本约定

当前版本为 0.17.2（2026-11-07 实机验证批：BUG-115 准入实机复验、BUG-108/BUG-110/BUG-102 复跑、FEAT-004 rebase 后与 FEAT-058 R03 实机回归，PATCH 性质，无产品代码变更；公开工具仍 100；见 [0.17.2 版本说明](../RELEASE_NOTES_0.17.2.md)与[发布记录](../validation/RELEASE-0.17.2.md)）。前一版为 0.17.1（[BUG-115](../work-items/BUG-115.md) 同计划 fill→trim→thicken 准入与 [FEAT-005](../work-items/FEAT-005.md) 过期 revision 回执补齐，PATCH 性质；公开工具仍 100；见 [0.17.1 版本说明](../RELEASE_NOTES_0.17.1.md)与[发布记录](../validation/RELEASE-0.17.1.md)）。前一版为 0.17.0（[FEAT-058](../work-items/FEAT-058.md) 首壁 `origin` 定位与 [FEAT-014](../work-items/FEAT-014.md) `edge_geometry` 几何选边合并批，MINOR 性质；公开工具仍 100；见 [0.17.0 版本说明](../RELEASE_NOTES_0.17.0.md)与[发布记录](../validation/RELEASE-0.17.0.md)）。前一版为 0.16.1（[DEV-069](../work-items/DEV-069.md) 0.13.0/0.14.0 反馈修复批，PATCH；公开工具仍 100；见 [0.16.1 版本说明](../RELEASE_NOTES_0.16.1.md)与[发布记录](../validation/RELEASE-0.16.1.md)）。前一版为 0.16.0（[FEAT-014](../work-items/FEAT-014.md) 四壁 miter cuts 与 [FEAT-004](../work-items/FEAT-004.md) 尺寸守卫合并批，MINOR 性质；公开工具仍 100；见 [0.16.0 版本说明](../RELEASE_NOTES_0.16.0.md)与[发布记录](../validation/RELEASE-0.16.0.md)）。前一版为 0.15.1（[BUG-111](../work-items/BUG-111.md) 发布后修正，PATCH 性质；公开工具仍 100；撤销 `keep_original` "每批 ≤4 副本"旧建议、选集诊断计数改读巡检实际字段）；见 [0.15.1 版本说明](../RELEASE_NOTES_0.15.1.md)与[发布记录](../validation/RELEASE-0.15.1.md)。前一版为 0.15.0（DEV-069 0.13.0 反馈收口批，MINOR 性质；公开工具仍 100；见 [0.15.0 版本说明](../RELEASE_NOTES_0.15.0.md)与[发布记录](../validation/RELEASE-0.15.0.md)）。前一版为 0.14.0（FEAT-039 W05/W06 回执与预览补证批，PATCH；公开工具仍 100）；见 [0.14.0 版本说明](../RELEASE_NOTES_0.14.0.md)与[发布记录](../validation/RELEASE-0.14.0.md)。前一版为 0.13.0（FEAT-039 曲面链 MINOR 功能批：新增 `creo_surface_trim`、`creo_project_curve`、`creo_surface_offset`，公开工具 97→100）；见 [0.13.0 版本说明](../RELEASE_NOTES_0.13.0.md)与[发布记录](../validation/RELEASE-0.13.0.md)。前一版为 0.12.1（DEV-068 README 改版，PATCH；公开工具仍 97；文档与版本元数据，无原生变更）；见 [0.12.1 版本说明](../RELEASE_NOTES_0.12.1.md)与[发布记录](../validation/RELEASE-0.12.1.md)。前一版为 0.12.0（FEAT-058 原生矩形钣金首壁与就地改型，MINOR：新增公开工具 `creo_sheetmetal_planar_wall`、`creo_resize_sheetmetal_planar_wall` 与 `creo_new_sheetmetal(template="native_planar")`；job 结果发布 `planar_wall` 判定块（feature_id、四个矩形尺寸、有符号 frame 包络、体积＝长×宽×厚、板厚读回，改型另需存档厚度；缺失或非有限证据不再判通过）；公开工具 95→97；本机 Creo 12.4 实机 67/67）；见 [0.12.0 版本说明](../RELEASE_NOTES_0.12.0.md)与[发布记录](../validation/RELEASE-0.12.0.md)。前一版为 0.11.7（R13 后续定因与实机补证批，PATCH：BUG-111 第 5 个 `keep_original` 副本失败的定因与有界选集诊断（`failed_transform.selection`）、撤销"≤4/批"变通建议；BUG-110 重放判据修正；公开工具仍 95；本机 Creo 12.4 实机 C0—C6 对照定因）；见 [0.11.7 版本说明](../RELEASE_NOTES_0.11.7.md)与[发布记录](../validation/RELEASE-0.11.7.md)。前一版为 0.11.6（DEV-065 R13 反馈批，PATCH：`verify_model` 子阶段归因（BUG-109）、坐标求解按形状判定（BUG-108）、装配失败 `ack_failure` 元数据出路（BUG-110）、旋转范围前置拒绝与 `failed_transform`（BUG-111），公开工具仍 95；本机 Creo 12.4 实机四项通过）；见 [0.11.6 版本说明](../RELEASE_NOTES_0.11.6.md)与[发布记录](../validation/RELEASE-0.11.6.md)。前一版为 0.11.5（DEV-002 第三批，PATCH：种子与能力模块包化、兼容入口、安装声明和源码身份，公开工具仍 95；离线交付，T5 实机待验）；见 [0.11.5 版本说明](../RELEASE_NOTES_0.11.5.md)与[发布记录](../validation/RELEASE-0.11.5.md)。更前一版为 0.11.4（DEV-064 R12 反馈批，PATCH：`HEADERS` 存在性门控使 Creo 10 缺头不再中断构建（BUG-107）、草图顶层 `sketch_shifted` 与坐标原点试点（BUG-108）、save/erase 恢复链路文案（BUG-106）；公开工具仍 95）；见 [0.11.4 版本说明](../RELEASE_NOTES_0.11.4.md)与[发布记录](../validation/RELEASE-0.11.4.md)。前一版 `0.11.3`（DEV-062 R11 反馈批，PATCH：`refresh_baseline` 旧检查点补基线（BUG-104）、零变更失败保持 ready 与 `ack_no_mutation` 注册表事务（BUG-105）、色板唯一标签键与 `random:true`（FEAT-056）；公开工具仍 95）；见 [0.11.3 版本说明](../RELEASE_NOTES_0.11.3.md)与[发布记录](../validation/RELEASE-0.11.3.md)。前一版 `0.11.2`（DEV-060 R10 反馈批，PATCH：草图 `profile.weldability` 风险标记与拉伸失败簇内间隙归因（BUG-101）、draft `requested_flip`/`effective_flip` 与 `draft_failure`（BUG-102）、孔 `depth_basis` 三键（FEAT-035 增量）、种子摘要仓库级闸门（DEV-061）；公开工具仍 95）；见 [0.11.2 版本说明](../RELEASE_NOTES_0.11.2.md)与[发布记录](../validation/RELEASE-0.11.2.md)。前一版 `0.11.1`（DEV-053 0.10.0 晚间反馈批 Q00–Q15，PATCH（用户指定编号）：失败模型清理与同名复用（BUG-096）、斜面草图修复（BUG-097/098）、三点定面 `through_points`（FEAT-053）、草图显式容差 `geometry_tolerance_mm`（FEAT-010 增量）、作业 `stage` 上报（FEAT-033 增量）、结果有界回执与分页（FEAT-008 增量）、背靠背提交竞态修复（BUG-100）；公开工具仍 95）；见 [0.11.1 版本说明](../RELEASE_NOTES_0.11.1.md)与[发布记录](../validation/RELEASE-0.11.1.md)。前一版 `0.11.0`（FEAT-052 装配按零件族上色批次，MINOR：新增公开工具 `creo_recolor_assembly` 与计划操作 `recolor_assembly`、`creo_list_components` 三态 `appearance` 字段，公开工具 94→95；本机 Creo 12.4 实机 28/28 通过）；见 [0.11.0 版本说明](../RELEASE_NOTES_0.11.0.md)与[发布记录](../validation/RELEASE-0.11.0.md)。前一版 `0.10.1`（DEV-053 PATCH 批：基准面非法参数入队前拒绝、capabilities 深度/方向枚举三键化、stdio 有界退出、种子/源码打包受信摘要闸门；公开工具仍 94）；见 [0.10.1 版本说明](../RELEASE_NOTES_0.10.1.md)与[发布记录](../validation/RELEASE-0.10.1.md)。前一版 0.10.0（DEV-052 N13 集成批次：FEAT-051 round/chamfer/draft 逐操作体积差与方向/引用应用回报字段、FEAT-008 草图结果 `entity_ids` 发布、FEAT-014 折边邻接折弯端 `adjacent_bend_ends` 创建前拒绝语义，含 FEAT-035/T12 盲孔 `depth` 改 tip 口径、FEAT-034/T02 编辑弧回显修复、FEAT-008/T09B 中心线计数修复与 BUG-049 端点诊断，MINOR 性质；公开工具仍 94）；见 [0.10.0 版本说明](../RELEASE_NOTES_0.10.0.md)与[发布记录](../validation/RELEASE-0.10.0.md)。前一版 `0.9.0`（DEV-051 实机修复批次：首壁板厚改由 `SMT_THICKNESS` 参数驱动并实机通过、新增 `creo_sheetmetal_flange` 可选 `end_trim_mm`，MINOR 性质；公开工具仍 94）；见 [0.9.0 版本说明](../RELEASE_NOTES_0.9.0.md)与[发布记录](../validation/RELEASE-0.9.0.md)。前一版 `0.8.5`（DEV-051 折边方向语义变更与钣金 add 支持边界，MINOR 性质；按本次指定编号发布，公开工具仍 94）；见 [0.8.5 版本说明](../RELEASE_NOTES_0.8.5.md)与[发布记录](../validation/RELEASE-0.8.5.md)。0.8.4 修复首壁准入阻断，见 [0.8.4 版本说明](../RELEASE_NOTES_0.8.4.md)与[发布记录](../validation/RELEASE-0.8.4.md)。前版 `0.8.3` 补证 T02/T06/T07/T08A 指定夹具；`0.8.2` 修复种子清单版本；`0.8.1` 为文档归档补版。`0.8.0`（DEV-051，MINOR；公开工具数仍 94）新增弧方向、钣金壁与 relief、沉孔／沉头、装配 native_bundle 等接口；其首壁准入阻断在 0.8.4 修复，折边几何、四壁及部分实机仍开放。见 [0.8.0 版本说明](../RELEASE_NOTES_0.8.0.md)和[发布记录](../validation/RELEASE-0.8.0.md)。下段从 `0.7.1` 开始的长篇版本沿革为历史快照，当前版本以前述版本入口及 `version.py` 为准。

`version.py` 是服务与源码版本的唯一手工入口；运行依赖锁定版本、种子包清单、工具输出和对外文档按各自契约核对一致。历史版本快照从 `0.7.1` 开始（DEV-048 反馈修复，PATCH，工具数 94 不变：收养侧车完整性与回退、拒绝后的引用生命周期、工作卡与发布检查回填、Right 面 ±Z 实机证据；见 [版本说明](../RELEASE_NOTES_0.7.1.md)与[发布记录](../validation/RELEASE-0.7.1.md)）；前一版本 `0.7.0`（0.5.2 三份反馈完整交付，MINOR，新增 `creo_plan_assembly_rebuild` 与 `creo_reclaim_generations`，工具数 92→94：T02 每输入一条操作结果、T03/T04 平面引用与任意面坐标、T05 轴几何与毫米+英寸实机单位矩阵、T06 多环诊断、T07 预览投影、T08 特征生命周期、T09 约束回放、T10 会话健康证据、T11 显式世代回收、T12 官方示例与 T13 集成矩阵；实机另修复五处生产缺陷；WorkBuddy 按用户决定未执行，外部 Creo 9/10 未复测；见 [版本说明](../RELEASE_NOTES_0.7.0.md)与[发布记录](../validation/RELEASE-0.7.0.md)）；前一版本 `0.6.1`（BUG-082 编辑修复，PATCH，工具数 92 不变；修复批编辑专项 16/16，种子矩阵部分受阻，WorkBuddy/外部 Creo 9 未验收；见 [版本说明](../RELEASE_NOTES_0.6.1.md)与[发布记录](../validation/RELEASE-0.6.1.md)）；前一版本 `0.6.0`（已发布：0.5.0 反馈整合第二批可靠的装配重建管线，MINOR，新增 `creo_adopt_file`，工具数 92；开发者实机已通过，WorkBuddy 黑盒经用户 2026-10-26 决定取消、未执行；版本说明见 [RELEASE_NOTES_0.6.0.md](../RELEASE_NOTES_0.6.0.md)，发布核对见 [RELEASE-0.6.0.md](../validation/RELEASE-0.6.0.md)）；前一版本 `0.5.3`（已发布：0.5.0/0.5.1 外部 Creo 9 反馈整合阶段一+阶段三，PATCH，无新增公开工具，工具数 91 不变：BUG-081 迁移 owner 拒绝诊断与 inspect 预检（有界 `owner_block`，停止判定语义未改）、BUG-082 在轴剖面编辑失败特征级诊断（`failed_features`，autodim 改角失败本体随版披露）、BUG-083 revolve.axis 入口预检、FEAT-030/BUG-034 种子来源与兼容信息透明化、FEAT-045/BUG-058/FEAT-020/BUG-019 小修，交付见 [RELEASE_NOTES_0.5.3.md](../RELEASE_NOTES_0.5.3.md)）；前一版本 `0.5.2`（已发布：0.5.0 反馈整合第一批，PATCH，无新增公开工具，工具数 91 不变：BUG-080 装配变换单位契约（`creo_inspect_session_assembly` 单位显式化、`transform_to_parent` 毫米归一化并新增 `transform_to_parent_raw`）、FEAT-006 收养拒绝有界逐特征诊断、DEV-046 第一批收口，交付见 [RELEASE_NOTES_0.5.2.md](../RELEASE_NOTES_0.5.2.md)）；前一版本 `0.5.1`（已发布：编辑链路缺陷修复批次，PATCH，无新增工具，工具数 91：BUG-062 centerline 就地编辑、BUG-030 同几何守卫修正、BUG-029 reorder 槽位修正、BUG-079 就地改弧半径修复，WorkBuddy 黑盒复验通过，交付见 [RELEASE_NOTES_0.5.1.md](../RELEASE_NOTES_0.5.1.md)）；最近前一版本为 `0.5.0`（已发布：FEAT-045 装配只读检查（新增 `creo_inspect_session_assembly`，工具数 90→91），交付见 [RELEASE_NOTES_0.5.0.md](../RELEASE_NOTES_0.5.0.md) 与[发布核对](../validation/RELEASE-0.5.0.md)）；前一版本 `0.4.8`（已发布：0.4.6 反馈第一批世代盘点口径补齐+归档补录）；前一版本 `0.4.7`（已发布：BUG-077 注册表拆分/迁移与健康检查（新增 `creo_migrate_registry`、`creo_registry_health`，工具数 90）、FEAT-047、DEV-045 发布检查单，含图纸引用消费点修复；已知缺陷 BUG-078（恢复 accept 路径）随版披露，交付见 [RELEASE_NOTES_0.4.7.md](../RELEASE_NOTES_0.4.7.md) 与[发布核对](../validation/RELEASE-0.4.7.md)）；前一版本为 `0.4.6`（PATCH：用户 2026-10-21 明确指定两批统一按 PATCH 发布——0.4.3 反馈完善计划实施：BUG-076 收养资料分离精修、BUG-057 锁机制统一、新增公开工具 `creo_erase_session_models`、FEAT-043/044 会话可观察性与 DEV-027 世代盘点 dry-run、DEV-043 台账精简，按约定本应为 MINOR，遵用户指定作为本版例外，工具数 88，交付见 [RELEASE_NOTES_0.4.6.md](../RELEASE_NOTES_0.4.6.md)）；前一版本 `0.4.4`（PATCH：两份 Creo 10 构建侧反馈完善计划——DEV-027 构建指纹归一化/旧缓存兼容、DEV-030 vcvars64_env 放宽、FEAT-044/023 补验收，无新增公开工具，交付见 [RELEASE_NOTES_0.4.4.md](../RELEASE_NOTES_0.4.4.md)）；前一版本 `0.4.3`（PATCH：0.3.7 反馈修复合集，无新增公开工具，交付见 [RELEASE_NOTES_0.4.3.md](../RELEASE_NOTES_0.4.3.md)）；前一版本 `0.4.2`（PATCH：用户 2026-10-20 明确指定并弃用开发期 0.5.0 编号，包含新增公开工具 `creo_open_file` 与 capabilities 分页等新功能，按约定本应为 MINOR，遵用户指定作为本次例外，交付见 [RELEASE_NOTES_0.4.2.md](../RELEASE_NOTES_0.4.2.md)）；前一版本 0.4.1（PATCH：用户 2026-10-19 指定，含新增工具，同为例外，交付见 [RELEASE_NOTES_0.4.1.md](../RELEASE_NOTES_0.4.1.md)）；历史 0.4.0（MINOR：FEAT-042 接管工具等，交付见 [RELEASE_NOTES_0.4.0.md](../RELEASE_NOTES_0.4.0.md)）；历史 0.3.7（0.3.6 的 README 勘误版）见 [DEV-041](../work-items/DEV-041.md)；历史 0.3.5 见 [DEV-035](../work-items/DEV-035.md)；历史0.3.4见 [DEV-032](../work-items/DEV-032.md)；历史0.3.3见[DEV-029](../work-items/DEV-029.md)；已发布 0.3.2 见 [DEV-025](../work-items/DEV-025.md)，历史主干准备见 [DEV-015](../work-items/DEV-015.md)。0.3.0 由 [DEV-013](../work-items/DEV-013.md) 发布，历史发布及验收保持原日期；后续主干交付统一执行上述合入与 Release 要求。**发版清单必须包含 README 标题与版本段**（0.3.6 曾遗漏，以 0.3.7 勘误补救）。

后续统一 `MAJOR.MINOR.PATCH`，候选版采用 `0.y.z-rc.1` 等格式。0.x 仍处于 API 形成阶段，本项目约定：兼容修复、文档及不改变接口兼容性的工程配置变更递增 PATCH，新增功能或不兼容接口调整递增 MINOR；不兼容变化必须附迁移说明。0.2.6 按用户 2026-10-14 明确指定命名，包含新增自动启动能力，作为本次版本约定的例外。达到 1.0 后按标准的兼容性规则递增。开发条目可有目标版本；未承诺的工作写“未排期”，不能凭编号推断版本。

历史 `v0.22`、日期后缀标签及其附件保留原样。发布后标签所指源码和同名附件内容保持不变；任何变更通过新版本发布。[语义化版本规范](https://semver.org/lang/zh-CN/)

0.3.1为用户于2026-10-15明确确认的最小补丁版本，包含默认检查摘要的接口行为调整，需按[迁移说明](../RELEASE_NOTES_0.3.1.md)使用full和分页。该次明确确认是本版例外，后续不兼容调整继续遵循上面的MINOR规则。

2026-10-17 用户明确指定本次集成版本为0.3.4，作为新增恢复/回调公开工具仍递增PATCH的本版例外；不改变后续默认版本规则。用户要求关闭BUG-001并交付现有待合分支，本版不补实机/WorkBuddy，已知卡死与缺少验证须在Release显式披露，不能改写为通过。

## 发布门槛

1. 明确本版条目、验收范围及未完成项；完成条目链接本次证据。记录受测提交和源码指纹，工作区有修改时不得仅用提交号代表源码。
2. 运行 `tools/dev_check.py`，检查所有适用单元回归。存量风格基线需显式说明，不宣称全库严格格式通过。
3. 在本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 和编译器环境运行原生发布回归。根据改动影响选择当前和历史套件，逐项记录命令、几何断言、参数编辑、保存擦除重载与适用回滚结果。完整回归未执行时列出具体未测模块，不把旧版本通过数改标为本版通过数。
4. 核对工具列表与 `capabilities.py`、`creo_capabilities` compact/full 的支持摘要、32 KiB 分页预算、文档、版本、种子数、种子指纹及兼容矩阵。本地 `release_status` 应符合 `version.py` 的候选后缀，完整覆盖声明与远端 `update.is_prerelease` 分开核对。新增单位相关接口应列出毫米、英寸、混合和未知单位证据，保留实际单位名、换算、原始查询码；未知为 null，不把未执行查询填成成功。按用户 2026-10-15 要求，Creo 10 独立复测和双版本验收不作为发布门槛；其他环境收到具体反馈后再登记跟进。Creo 9 与匹配 Toolkit 9 已按 2026-10-16 决定纳入支持/要求范围，BUG-033 编译探测修复已实现；本机无 Creo 9 SDK，实机编译与运行时均未验收；发布说明须如实标注该状态。已有不同版本的测试事实分别保留，不跨环境外推通过。
5. 使用 `tools/package.py` 与 `tools/package_seeds.py` 制作源码和种子附件；检查分发白名单、第三方许可、配置模板、开发配置、种子及 SHA256。两个打包脚本各自在 ZIP 同目录生成 `<zip>.sha256`（内容为 `<完整 SHA256>  <文件名>` 一行），该文件是发布附件的一部分，不是本地临时产物。种子附件与源码包必须成对发布，顺序固定：先用 `tools/package_seeds.py --output <new-seed.zip>` 确定性构建种子包，把实测 SHA256 显式回填到 `docs/seed_package.json` 的 `seed_archive_sha256`（同时写 `compatible_server_version`），再重建一次确认哈希不变，最后用 `tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>` 制作源码包。**DEV-061 起 `tools/package_seeds.py` 构包后默认校验 `docs/seed_package.json`**：未回填或版本不符时保留归档、打印应回填的摘要并以非零退出（`--allow-record-mismatch` 只能用于准备回填，不得用于发布）；`tests/unit/test_seed_record_gate.py` 也在单元阶段守同一件事。`tools/package.py` 的 `--seed-archive` 是必填项：缺参、摘要不符、版本不符、两份种子清单不一致或 README 当前版本段滞后都在写出任何源码包或 stage 文件之前失败（exit 非零）。旧调用不静默猜选父目录 ZIP，须补该显式参数；从新目录解压并运行适用检查，随后在具备 SDK 的环境验收安装和建模。
6. 核对实际验收源码与本次变更对应的 `main` 提交一致，从该提交建立版本标签并发布 GitHub Release，附版本说明、验收摘要、环境与范围限制。核对附件及校验和，并回填 Release 链接。发布平台标记 Pre-release 与项目成熟度一致。
7. **Release body 必须直接列出源码包与种子包的文件名及完整 SHA256，Release 附件必须固定为四个文件**（DEV-045：0.4.1～0.4.3 的好做法在 0.4.4 漏写，升级者只能去主干 `docs/validation/RELEASE-*.md` 另找一步；DEV-045/C01：0.11.7 与 0.12.0 只上传两个 ZIP，漏传两个 `.zip.sha256` sidecar）。四个附件是 `MCP_CREO_MechDog-<版本>-source.zip`、同名的 `.zip.sha256`、`MCP_CREO_MechDog-<版本>-seed-library.zip` 与同名的 `.zip.sha256`；sidecar 由打包脚本生成，文件名必须是 `<zip 文件名>.sha256`。上传命令须逐个列出四个文件，例如 `gh release create v<版本> <source.zip> <source.zip.sha256> <seed-library.zip> <seed-library.zip.sha256> --title ... --notes-file ...`；不要用 `*.zip` 通配代替清单（通配会漏掉 sidecar）。发布后用 `gh release view <tag> --json assets` 或 `tools/check_release_assets.py --tag <tag>` 核对远端恰有这四个附件、两个 sidecar 的哈希与对应远端 ZIP 摘要一致，再报告交付完成；核对结果写入发布记录。已发布 Release 与附件保持原样，不回填旧版本。
8. 文档与状态一致性逐 ID 核对：`version.py`、当前版本说明的标题与正文、[docs/DEVELOPMENT.md 当前入口](../DEVELOPMENT.md)、主台账（含完成档案）、本版交付 ID 的工作卡首页及远端 GitHub Release（已发布／草稿／不存在）必须一致。**“本版交付 ID”同时包含功能/接口卡（FEAT）**：本版新增或扩展的能力，其 FEAT 卡首页状态与目标版本必须与 `capabilities.py`、README 和版本说明一致；能力已发布而卡仍写“开发中/未排期”视为本项未通过（DEV-062，对应 0.11.0 反馈 F02 §4）。合入前按候选状态核对一次，发布后按实际状态再核对一次；不允许旧版本遗留的"未发布"描述继续出现在当前入口、主台账或版本说明首部。核对时对本版交付的每个 ID 分别记录：技术状态、实际交付版本、仍开放范围，以及卡首页／主台账／版本说明／开发入口／实际 Release 五处链接。本项为手动清单核对，不为此编写新发布工具、不联网代替人工确认。
9. 相对上一正式包的身份核对：以最近一个已发布版本的正式源码包为基准，比较 `native/third_party/**` 原字节（至少含 `json.hpp` 与第三方许可）、回调指纹（沿用 `sha256-repo-lf-v1` 的 CRLF→LF 归一化算法，不因比较而改算法）、DLL 身份（loader／callback／worker 的 SHA256）与注册路径（`protk.dat`、实际注册表项及安装目录）。哈希相同只说明字节未变；内容确有变更时，按实际影响说明是否需要重新注册、迁移或重启，不以"所有哈希必须永远相同"阻止合理更新。本项同样为人工核对，不新增发布工具，不把外部报告中的字节数当作本机受测指纹。

本地构建或检查不等于已发布。GitHub 操作和附件示例见 [原发布说明](../PUBLISH_GITHUB.md)；其 0.2.5 文件名为历史示例，未来按实际新版本生成，不重新发布相同版本的修改内容。

### DEV-072：逐 ID 回填与发布后证据

第 8 步沿用人工清单，但必须逐行填值，不能仅写“文档已同步”。对本版涉及的每个 ID，读取主台账该行第 3 列（状态）、第 4 列（目标版本）及卡首页的状态/目标版本；在下表记录字面值与开放范围。已交付子项而整卡仍有余项时，主台账写“已交付 <版本> 子项；<具体余项> 未排期”。卡或台账仍把已发布实现写成“未实现/待规划”、已实机范围写成“未实机”，均不通过。候选态与发布后各核一次。

| ID | 主台账状态 / 目标版本 | 卡首页状态 / 目标版本 | 本版实际交付 | 仍开放范围 | 一致 / 待修正 |
| --- | --- | --- | --- | --- | --- |

第 7 步的发布后核对必须执行 `python tools/check_release_assets.py --tag v<版本>`；`gh` 不可用或失败时，工具使用 GitHub API 精确 tag 的下载备用路线。自动下载未成功时，人工下载四附件并用 `--dir` 检查，只能记“本地下载目录已校验”，远端发布元数据和 Release body 另行核对。

将发布后结果保存为新的交付记录（例如 `docs/development/RELEASE-<版本>-POSTCHECK-<日期>.md`）或 PR/Release body，逐件列出：实际查询时间（含时区）、tag 指向与 main 提交、Release 链接与状态、附件名/大小/API digest、下载后本地实算 SHA256、sidecar 与正文比对结论、命令与失败范围。API digest 与本地实算不得混称。`docs/validation/` 已成历史的发布前记录及原始反馈保持字节不变，新记录链接旧记录并明确“准备发布”为当时时点。

发布后标签与同名附件冻结；发现已上传内容不一致时保留原物和已知旧/新摘要、大小、取值方式与时间，并在新交付记录说明事实和未确认处。修复通过新版本发布；不能删除重传同名附件或移动旧 tag。缺少取值时间的历史 API 摘要，不得推断其必定对应某个替换前包。

### 打包调用迁移（DEV-053 P04 / BUG-089 防复发）

`tools/package.py` 新增必填 `--seed-archive`，源码包不再在缺少种子附件时生成：

| 旧调用 | 新调用 |
| --- | --- |
| `python tools/package.py --output <new-source.zip>` | `python tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>` |
| `python tools/package.py --output <new-source.zip> --stage <dir>` | `python tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip> --stage <dir>` |

`--seed-archive` 接受本地 ZIP 路径。校验不通过时命令 exit 非零，不创建源码 ZIP、不写 stage 目录，也不回退为警告继续；既有"拒绝覆盖既有输出"和"stage 目录必须为空且与工程分离"的保护保持不变。

## 发布回归记录模板

每个发布候选在 `docs/validation/` 保存可审查摘要，完整机器日志保留在忽略的 `build/`。

```text
版本与条目：
提交、dirty 标志、受测源码指纹：
日期与 Windows/Python/Creo/SDK/MSVC 环境：
命令及结果（单元 / 原生 / 安装 / 源码包）：
原生修改保存重载、参数编辑、回滚证据：
未测模块、失败用例、兼容限制：
源码包及种子包 SHA256（文件名与完整哈希，写入 Release body）：
Release 附件清单（四个：两个 ZIP 及各自的 `.zip.sha256`；逐个记录远端名称与存在性）：
发布候选验收结论：
合入 main 的提交、版本标签及指向：
GitHub Release 链接与发布状态：
远端附件与 SHA256 核对结果（四个附件逐项一致，含 sidecar 内容与对应 ZIP 摘要）：

逐 ID 状态核对（候选态 / 发布后各一次）：
| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

相对上一正式包核对（上一版本：____）：
| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| native/third_party 原字节（含 json.hpp、第三方许可） | | | |
| 回调指纹（sha256-repo-lf-v1） | | | |
| loader DLL SHA256 | | | |
| callback DLL SHA256 | | | |
| worker SHA256 | | | |
| protk.dat / 注册表路径 | | | |
| 实际注册影响（未变 / 需重新注册 / 需迁移 / 需重启） | — | — | |
```
