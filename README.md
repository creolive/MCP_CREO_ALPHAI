# MCP_CREO_MechDog 0.11.7

开发维护从 [开发入口](docs/DEVELOPMENT.md) 和 [统一功能台账](docs/BACKLOG.md) 开始。每项工作先定义验收；语言与单元检查、Creo 实机验收分别记录。项目采用渐进布局整理，当前支持环境见 [兼容矩阵](docs/COMPATIBILITY.md)。

本地 Windows MCP 服务，按需启动或连接 Creo Parametric 9 / 10 / 12，通过官方 C/C++ Toolkit 创建、查询和修改**原生参数化特征**。当前开发与发布按本机 Creo 12.4.0.0 的改动范围验收；Creo 10 不再要求独立复测。Creo 9 与 Toolkit 9 已纳入支持／要求范围，编译探测修复已实现，但本机无 Creo 9 SDK，实机编译与建模运行时均未验收。各环境已测和未测范围见[兼容矩阵](docs/COMPATIBILITY.md)。典型建模流程为：新建零件 → 草图 → 拉伸／旋转 → 切除／孔 → 后续特征；底板接口保留为快捷工具。

公开工具 **95 个**（0.11.0 新增 `creo_recolor_assembly` 装配按零件族上色），实际可见清单以 `creo_capabilities` 为准。接口覆盖常见实体特征、磁盘模型打开、受管副本接管、会话枚举、**装配只读检查与回放规划**、**装配按零件族上色**、受控恢复、**显式世代回收**及直接混合，**尚未完成所有 Creo 操作和参数组合的覆盖**。禁用操作从工具列表隐藏，并在提交前拒绝。服务使用官方 Python MCP SDK 2.3.0、stdio 传输，采用 [MIT 许可证](LICENSE)。使用者在自己的 Windows 电脑上安装依赖并编译 Toolkit 执行器，由本地 AI 客户端调用。

当前正式版 **0.11.7**（PATCH，R13 后续定因与实机补证批，分支 `codex/BUG-111-r13-followup`）把"第 5 个 `keep_original` 副本失败"从**未定因**推进到**已定因**，公开工具仍 **95 个**，接口与参数语义不变：`geometry_transform` 失败回执新增有界 `failed_transform.selection`（请求 body id、被选面数、op 起始计数），可直接看出失败操作复制的是**整个当前体**（[BUG-111](docs/work-items/BUG-111.md)）；本机 **Creo 12.4.0.0 实机对照**（C0—C6 七个独立底板）证明 4 个独立模型同型失败于 index 4，而 -135 置于首位时 5 个副本全部成功、拆成 4+3 批仍失败——**不是副本数量上限、不是角度缺陷、也不是引用解析问题**，而是 `keep_original` 复制整个当前体后新增副本与既有凸块重合／交叠导致的再生失败；据此**撤销**此前"单批 ≤4 个副本、下一批重新引用当前 body"的变通建议（拆批实测无效），本版只交付诊断与能力边界，不改变建模行为。开发者夹具同步按特征增量与单 body 语义判定，并支持按用例过滤与重跑避让。**未验证**：Creo 9/10 实机、WorkBuddy 黑盒、`accepted_rigid=true` 实机分支、`ack_failure` 成功路径（实机只覆盖零变更守卫）。离线全量 2268 项单测 0 失败、`dev_check` `success=true`。详见[版本说明](docs/RELEASE_NOTES_0.11.7.md)、[兼容矩阵](docs/COMPATIBILITY.md)与[语法参考](docs/REFERENCE_SYNTAX.md)。

上一版 **0.11.6**（PATCH，0.11.5 第十三轮反馈批 R13，[DEV-065](docs/work-items/DEV-065.md)，[归档映射](docs/validation/feedback-0.11.5-2026-11-03/MAPPING.md)）关闭四类"失败无出路"的问题，公开工具仍 **95 个**：`verify_model` 拆子阶段并逐段计时，`creo_get_job` 新增只读 `native_progress`（阶段、子阶段、停滞秒数），超时文案点名最后子阶段（[BUG-109](docs/work-items/BUG-109.md)）；坐标求解的整体刚体平移（≤1e-2 mm、形状残差 ≤1e-9 mm）不再判失败，形状闸门仍为 1e-5 mm 并新增 `shape_deviation_mm`/`accepted_rigid`（[BUG-108](docs/work-items/BUG-108.md)）；`creo_reconcile_model` 新增 `action="ack_failure"`（`confirm_failure_ack=true`），让终态失败的装配以元数据事务退回 `ready`，不动 revision、文件与组件（[BUG-110](docs/work-items/BUG-110.md)）；`geometry_transform` 旋转限定 -180..180 度、超范围给等价值，失败回执带 `failed_transform`（[BUG-111](docs/work-items/BUG-111.md)）。离线全量 2241 项单测通过、`dev_check` `success=true`；本机 **Creo 12.4.0.0 实机四项通过**（阶段归因 3 作业各 13 个 `verify_stages`、坐标草图 4 例 + 挤出成功、装配失败后模型保持 `ready`、225° 前置拒绝且第 5 副本失败在 `operation_index=4` 复现），Creo 9/10 与 WorkBuddy 未测。详见[版本说明](docs/RELEASE_NOTES_0.11.6.md)、[兼容矩阵](docs/COMPATIBILITY.md)与[语法参考](docs/REFERENCE_SYNTAX.md)。

上一版 **0.11.5**（PATCH，[DEV-002 第三批](docs/work-items/DEV-002.md)）：DEV-002 第三批种子与能力模块包化：seeds/capabilities 的唯一实现进入 src/creo_mechdog，根导入与 seeds CLI 保持兼容；补齐 bridge/seeds/capabilities 标准安装声明、运行源码指纹与独立分发验收。公开工具仍 95，参数和建模语义不变。离线实现全量 2196 项单测零失败、全新解压安装环境 64 项回归通过；本次发布版检查见[发布记录](docs/validation/RELEASE-0.11.5.md)。**本批实机与真实 stdio 验收未执行**，T5 和后续服务/启动/桥接迁移继续保留，整个 DEV-002 未关闭。升级请重新运行 setup.ps1 或在本安装虚拟环境执行 `python -m pip install --no-deps -e .`，重启 MCP 服务加载新模块；请配套使用 0.11.5 种子包（种子本体字节不变，清单版本已更新）。见[版本说明](docs/RELEASE_NOTES_0.11.5.md)。

上一版 **0.11.4**（PATCH，0.11.1 第十二轮反馈批 R12，[DEV-064](docs/work-items/DEV-064.md)）：两份 Creo 10 反馈原件逐字节归档并逐章对账（[归档映射](docs/validation/feedback-0.11.1-2026-11-02/MAPPING.md)）；SDK 常量生成按"缺失头跳过读取、不生成 include"门控，Creo 10 缺 `Probbl.h` 不再中断构建（[BUG-107](docs/work-items/BUG-107.md)）；草图结果新增顶层 `sketch_shifted` 与 `geometry_deviation.shift_detected`/`accepted_by_request`，坐标模式试点用投影基准线钉住原点（[BUG-108](docs/work-items/BUG-108.md)）；`save` 的 origin 不匹配与 `erase` 的 `modified` 拒绝给出可照抄链路（[BUG-106](docs/work-items/BUG-106.md)）；台账补建 [FEAT-054](docs/work-items/FEAT-054.md)/[FEAT-055](docs/work-items/FEAT-055.md) 卡。公开工具仍 **95 个**。本版含本机 Creo 12.4 实机：细长三角条 4 个坐标草图 + 实体挤出全部成功、`saved_file_reloaded_and_verified=true`、未复现 0.004 mm 整体平移（见[发布记录](docs/validation/RELEASE-0.11.4.md)）；Creo 9/10 实机与 WorkBuddy 未测。升级请使用 0.11.4 种子包（旧种子包会被版本闸门拒绝）。

上一版 **0.11.3**（PATCH，0.11.0 第十一轮反馈批 R11，[DEV-062](docs/work-items/DEV-062.md)）：三份反馈原件逐字节归档并逐章对账（[归档映射](docs/validation/feedback-0.11.0-2026-11-01/MAPPING.md)）；`creo_recolor_assembly` 新增显式 `refresh_baseline`——0.10.x 检查点缺组件外观基线时以作业前实读外观建立回滚基线（回执 `baseline_source`，`dry_run` 给出可直接照抄的 `next_action`），且只放宽这一项身份缺口（[BUG-104](docs/work-items/BUG-104.md)）；零变更失败不再进入不可恢复状态——原生无派发即发布 `model_unchanged`，并新增纯注册表事务 `creo_reconcile_model(action="ack_no_mutation", confirm_zero_mutation=true)`，把 `failed` 模型复位为 `ready` 并写审计块，不启动 worker、不连 Toolkit、不改 revision（[BUG-105](docs/work-items/BUG-105.md)）；上色取色支持唯一组件标签键与 `random:true`（与 `palette` 互斥、确定性、回显解析后的调色板，作业记录显式颜色便于重放，[FEAT-056](docs/work-items/FEAT-056.md)）；`RELEASING.md` 第 8 步纳入 “新增能力对应 FEAT 卡状态”核对，修正 BUG-089/BUG-102/DEV-061 卡头滞后与台账分类（155→161 行）。公开工具仍 **95 个**。本版为离线交付：全量 2158 项单测 0 失败、`dev_check` `success=true`、`bridge.py build` exit 0，**实机未执行**（见[发布记录](docs/validation/RELEASE-0.11.3.md)）；Creo 9/10 实机与 WorkBuddy 未测。升级请使用 0.11.3 种子包（旧种子包会被版本闸门拒绝），并阅读[0.11.3 版本说明](docs/RELEASE_NOTES_0.11.3.md)。上一版 **0.11.2**（PATCH，0.10.0 第十轮反馈批 R10，[DEV-060](docs/work-items/DEV-060.md)）：三份反馈原件逐字节归档并逐章对账（[归档映射](docs/validation/feedback-0.10.0-2026-10-31/MAPPING.md)）；草图结果新增 `profile.weldability` **风险标记**——阈值取既有 1e-9 mm 已测安全界，`weldable=false` 只表示“未被证明可焊”而非“会失败”（本机 Creo 12.4 实测 8.215e-7 mm 间隙拉伸成功，[BUG-101](docs/work-items/BUG-101.md)），并给出有界 `exceeding_pairs`；拉伸失败在 `open_ends==0` 但端点簇内仍有间隙时点名该证据、替换“原因未定”；`draft_geometry` 分列 `requested_flip`（入参原样）与 `effective_flip`（特征树实读），创建被拒时追加 `draft_failure{classification, element_errors≤20, note}`（[BUG-102](docs/work-items/BUG-102.md)）；孔结果新增 `depth_basis`/`depth_scheme_code`/`depth_scheme_query` 由创建后特征树实读，普通直孔保持 null 不猜（[FEAT-035](docs/work-items/FEAT-035.md) 增量）；种子包摘要新增**仓库级闸门**——`tools/package_seeds.py` 构包后校验 `docs/seed_package.json`，失配保留归档并非零退出，`release_integrity.assert_repo_record_matches()` 与 `tests/unit/test_seed_record_gate.py` 双守（[DEV-061](docs/work-items/DEV-061.md)）。壁面归属：YZ 底板在本机四条下边均 `eligible`、报告方失败的长边 106 折边成功，Creo 10 的 `-8` 不可复现，示例/README 改为“逐边读 `wall_contour_status`、不得假设四道折边”（[BUG-103](docs/work-items/BUG-103.md)）。公开工具仍 **95 个**。本机 Creo 12.4.0.0 实机（见[发布记录](docs/validation/RELEASE-0.11.2.md)）：draft 10°/flip=false → `effective_flip=true`、+264.49 mm³；YZ 底板 42920 mm³ 与四边三态、106 折边 57293.62 mm³；8.215e-7 间隙拉伸成功；全量 2131 项单测与 `dev_check` 通过；Creo 9/10 实机与 WorkBuddy 未测。升级请使用 0.11.2 种子包，并阅读[0.11.2 版本说明](docs/RELEASE_NOTES_0.11.2.md)。上一版 **0.11.1**（PATCH，0.10.0 晚间反馈批 Q00–Q15，[DEV-053](docs/work-items/DEV-053.md)）：失败模型清理与同名复用——失败终态携带 `failed_model_cleanup` 回执（只清理能证明由本次失败作业新建、未被使用、无引用的对象），新增显式 `rollback_status` 字段，失败后同名再次新建不再被迫改名（[BUG-096](docs/work-items/BUG-096.md)）；斜面草图修复——三点定面斜面上无精确垂直基准面时自动创建辅助基准面（[BUG-097](docs/work-items/BUG-097.md)/[BUG-098](docs/work-items/BUG-098.md)）；`datum_plane` 新增 `{kind:"through_points"}` 三点定面（[FEAT-053](docs/work-items/FEAT-053.md)，重复点/近共线准入拒绝）；草图可选显式容差 `geometry_tolerance_mm`（省略时 coordinates 1e-5 mm 失败阈值、autodim 1e-3 mm 告警不变，[FEAT-010](docs/work-items/FEAT-010.md) 增量）；作业全程 `stage` 阶段上报；大结果有界回执 `{total, truncated, sample≤20}`、`creo_get_job` compact ≤32 KiB 与 full 游标分页（[FEAT-008](docs/work-items/FEAT-008.md) 增量）；Toolkit 通道背靠背提交竞态修复——预约贯穿接受到 runner 收尾，空窗内立即 busy 拒绝不排队（[BUG-100](docs/work-items/BUG-100.md)）。公开工具仍 **95 个**。本机 Creo 12.4.0.0 四轮实机（[记录](docs/validation/DEV-053-Q15-live-2026-11-01.md)：Q05 8/8、Q06 L1/L2、Q03 S1/S2/S3、Q13 全套、Q02 15/15、Q04 真并发与背靠背、Q01 P07/P08/P11、Q11 P12 一带、BUG-100 三项复验）与全量 2096 项单测通过；WorkBuddy 黑盒与 Creo 9/10 未测。升级请使用 0.11.1 种子包，并阅读[0.11.1 版本说明](docs/RELEASE_NOTES_0.11.1.md)。上一版 **0.11.0**（MINOR，[FEAT-052](docs/work-items/FEAT-052.md) 装配按零件族上色）：新增公开工具 `creo_recolor_assembly` 与计划操作 `recolor_assembly`——默认按组件绑定中唯一 `source_model_id` 自动分族，也支持显式族表（须无重复且完整覆盖全部组件）加色板（每族三个 0..1 有限数值）；`dry_run` 只读预览分组（不连接 Toolkit、不建作业、不推进 revision，分页 ≤32 KiB）；执行走既有作业通道并始终保存，颜色写在装配组件层（源零件文件字节不变），`creo_list_components` 每组件新增三态 `appearance` 字段（present/absent/query_failed），保存擦除重载前后逐组件读回误差 ≤1e-6，任一步失败沿用检查点回滚并核验外观点恢复（无法证明恢复保留 unknown 保护），旧检查点缺外观基线时拒绝写入并指引 `creo_save_model`。本机 Creo 12.4.0.0 实机（run `assembly_appearance_live_20261101T060336Z558b3546`）：80 组件/12 族夹具 28/28 检查通过（自动分族与显式合族两轮上色、第三套色板复涂、放置变更后保色、两个故意失败计划分别回滚至"无组件外观"与既有颜色、源零件 SHA256 全程不变、保存重载核验全 true），另过装配 pipeline 与 T07 预览针对性回归；WorkBuddy 黑盒与 Creo 9/10 未测。升级请使用 0.11.0 种子包，并阅读[0.11.0 版本说明](docs/RELEASE_NOTES_0.11.0.md)。上一版 **0.10.1**（PATCH，[DEV-053](docs/work-items/DEV-053.md) 0.9.0 反馈对账批）：基准面非法参数不再静默丢参——`angle` 携带非零 `offset`、缺 `kind`、非法 angle 轴类型均在入队前明确拒绝（原生兜底），`angle=0` 属显式角度模式；`creo_capabilities` 概览的深度/方向枚举拆分为 `extrude_depth_types`/`extrude_directions`/`extrude_through_all_modes` 三键并移除旧 `extrude_depths` 键（旧键内容与 `depth_type` 契约不符）；stdio 服务在客户端消失后有界退出（宽限 1.5 s、兜底 2 s），不杀已受理任务；种子安装与源码打包新增受信摘要双重闸门（`tools/package.py` 必填 `--seed-archive`）。本机 Creo 12.4.0.0 实机（run `post0100_20261031T234309_rel0101`）：五非法编辑反例（4 例 schema 拒绝无作业、1 例原生失败回滚，拒绝后同源体积与 revision 逐位不变）、恢复编辑、基准面 ±54°/偏移/独立工具与 plan 双入口正反例、圆角/倒角/拔模九例（含批中途失败回滚）、装配回放与 T12 官方示例回归全部通过；公开工具仍为 **94 个**。升级请使用 0.10.1 种子包，并阅读[0.10.1 版本说明](docs/RELEASE_NOTES_0.10.1.md)。上一版 **0.10.0**：`creo_round` / `creo_chamfer` / `creo_draft` 结果新增逐操作体积差（`volume_before_mm3`/`volume_after_mm3`/`material_delta_mm3`/`material_measurement`）与 `draft_geometry`/`reference_application` 回报；草图结果发布 `entity_ids`，`revolve_axis` 回显可与所画中心线对账；折边附着边端部邻接既有折弯时创建前拒绝（`failure_reason=adjacent_bend_ends`，四壁仍不支持）；盲孔 `depth` 改为钻尖（tip）口径——旧版同输入建出的 custom 盲孔更深（到肩 + 钻尖超出），升级后重放同请求结果不再相同，详见[版本说明](docs/RELEASE_NOTES_0.10.0.md)。公开工具仍为 **94 个**。本机 Creo 12.4.0.0 实机：圆角/倒角/拔模七夹具、沉孔/沉头与盲孔六例、组件身份、中心线计数、邻接拒绝边界与预览图像复核均通过；Creo 9/10 未验，WorkBuddy 未执行。升级请使用 0.10.0 种子包，并阅读[0.10.0 版本说明](docs/RELEASE_NOTES_0.10.0.md)及[发布记录](docs/validation/RELEASE-0.10.0.md)。0.8.5 及更早的折边方向、钣金 add 边界与历史证据见 [0.8.5 版本说明](docs/RELEASE_NOTES_0.8.5.md)及[发布记录](docs/validation/RELEASE-0.8.5.md)。

服务后台检测已有会话、协调启动并检查建模就绪；成功建模及保存重载才证明相应操作在该环境可用。启动配置和排错见[安装说明](docs/INSTALL.md)。

普通混合可直接创建或追加，范围见 [直接混合](docs/DIRECT_BLEND_0.2.5.md)；种子复用见 [调用说明](docs/LOFT_SEED.md)、[多截面](docs/MULTISECTION_BLEND.md)。草图支持 `dimensioning="auto" / "autodim" / "coordinates"`，坐标模式的范围与尺寸编辑规则见 [草图说明](docs/SKETCH_STABILITY_0.2.5.md)。迁移步骤见 [种子库](docs/SEED_LIBRARY.md) 和 [换电脑、换 Agent](docs/MIGRATION.md)。

直接混合使用固定注册入口与升级预检：按下文一次性设置及[生命周期说明](docs/CALLBACK_LIFECYCLE.md)完成正式注册、持久配置与手动启动，再查 `creo_callback_status`；只有实时 `ready` 才提交直接混合。查询和建模不加载 DLL、不修改安全策略。升级、回退及多目录并存等剩余验收见[统一台账](docs/BACKLOG.md)。新建种子放样不需要此回调。

工程图、曲面、布尔、筋、UDF、钣金和装配各有验收范围，见[兼容矩阵](docs/COMPATIBILITY.md)；旧版测试与来源见[历史资料](docs/BACKLOG_COMPLETED.md)。新版本不会改写已发布的 GitHub 源码或附件。

[版本检查与提醒](docs/UPDATE_CHECK.md)的断网期间建模、高版本提示及客户端展示等剩余验收仍按台账跟进。0.2.6 旧发布需先手动升级一次才可收到后续更新提醒。

Python 包迁移前两批已完成，更新检查、输入模型及轮廓／翼型辅助实现位于 `src/creo_mechdog/`，整体迁移仍继续。现有开发环境更新源码后执行 `python -m pip install --no-deps -e .`；正常安装由 `setup.ps1` 完成。根入口和数据位置保留，见[迁移任务卡](docs/work-items/DEV-002.md)。

模型引用须按具体工具的参数形状选择，见[引用格式](docs/REFERENCE_SYNTAX.md)。

### 0.5.2 反馈的矩阵与结果迁移口径

`creo_inspect_session_assembly` 的 `transform_to_parent` / `transform_to_root` 是**毫米归一化**的行向量 4×4 矩阵：局部毫米坐标乘矩阵得到父级／根级毫米坐标，平移在末行。`*_raw` 保留 Creo 查询所得原始矩阵及其源／目标模型单位，不可直接作为毫米放置参数。每个节点的 `units.component` / `units.parent` 和装配的 `assembly.length_unit` 提供实际单位名、毫米换算和查询码；缺失或未确认时相应值为 `null`，不能把未知当作毫米。

例如组件为英寸、父装配为毫米时，先确认双方单位及查询结果，再使用完整的 `transform_to_parent` 映射毫米点。若把 raw 定义为 `p_parent_raw = p_local_raw × R_raw + t_raw`，且组件、父级每原始单位分别为 `s_local`、`s_parent` 毫米，则 `p_parent_mm = p_local_mm × (s_parent/s_local × R_raw) + s_parent × t_raw`。混合单位影响 3×3 块与平移，不能只缩放平移。回放位姿时只从**有效的** `transform_to_parent` 取左上 3×3 和末行前三项，并满足 `rotation_matrix` 的正交／行列式校验；单位未知或矩阵不能表达刚体位姿时停止，重新取得证据，不猜测坐标。详见[装配重建管线](docs/ASSEMBLY_REBUILD.md#位姿与矩阵约定)。

`unchanged=true` 只说明对应操作走了**原生几何核验过的同几何快捷路径**；不能据此假定所有写操作都无效果，也不能把同值 `creo_set_dimensions` 自动视为 `unchanged`。成功作业仍按接口保存、重载并推进约定的 revision。批量结果的执行与最终提交／回滚语义以[DEV-047 共享基线](docs/work-items/DEV-047.md#interface-baseline)为准。

## 安装

升级后先重启目标 MCP 连接器，再核对实际路径、启动指纹和工具清单；现有模型接管流程与未测边界见[接管说明](docs/ADOPTION.md)。

准备 Windows x64、Python 3.12+ x64、Creo Parametric 9、10 或 12 及匹配的 Toolkit SDK、MSVC x64 C++ 构建工具和可用的 PTC 许可。Creo 9 与 Toolkit 9 的编译探测修复已实现，实机编译与建模运行时未在本机验收。Creo 软件、SDK、模板和许可需要自行取得；MIT 适用于本项目代码、文档及种子库的原创内容，不提供 PTC 软件授权。第三方依赖和 PTC 前置条件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

1. 下载源码，解压到较短的可写目录，例如 `C:\MCP_CREO_MechDog`；下列命令在该目录执行。
2. 运行安装脚本，填写自己的 Creo 安装根目录：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
   ```

   Creo 12.4 的安装示例：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 12.4.0.0'
   ```

   按自己的安装位置替换路径，使用对应版本的 Toolkit SDK 在目标机重新构建。

   如果 Python 没有加入 PATH，可加 `-Python 'C:\Path\To\python.exe'`。如果编译器没有自动找到，可加 `-VcVars64 'C:\Path\To\vcvars64.bat'`。这两个示例路径需要替换。
3. 安装成功后，脚本生成本机 `config.json`、`.venv/`、`build/` 和 `client-config.json`。将 `client-config.json` 中的服务配置加入支持本地 stdio MCP 的 AI 客户端。
4. 启动客户端中的 MCP 服务，服务自动复用已有 Creo 或按配置启动。让 AI 调用 `creo_startup_status` 等待 `state == "ready"`，再用 `creo_session_status` 确认连接后提交建模计划。若 Creo 显示启动对话框，由使用者处理。成功建模及保存重载验证才证明相应操作在该环境可用。

脚本不修改全局客户端配置。完整安装与排错说明见 [docs/INSTALL.md](docs/INSTALL.md)；GitHub 源码发布步骤见 [docs/PUBLISH_GITHUB.md](docs/PUBLISH_GITHUB.md)。GitHub 仓库用于分发源码，服务在使用者的电脑运行。

### 直接混合（Blend）的一次性回调设置

`creo_loft` / 计划内 `loft`（直接混合）依赖一个常驻回调 DLL，须由使用者完成一次正式注册；未就绪时建模前会被明确拒绝（`BLEND_CALLBACK_SETUP_REQUIRED`）。**新建种子放样（`creo_new_loft_part`、`creo_new_airfoil_blade`）不需要此回调**。一次性步骤：

1. 构建后在 `build\blend_callback_setup.json` 或 `creo_callback_status` 返回中确认 `registry_file`（固定入口 `<安装目录>\build\blend_callback_protk.dat`）。
2. 在 Creo 的「辅助应用程序」（Auxiliary Applications）对话框注册该 `registry_file` 一次，手动启动它并亲自确认 DLL 安全提示；不要直接注册 `module_file`。
3. 跨 Creo 重启保持条目：把 `build\blend_callback.config.pro` 中的 `protkdat <注册文件绝对路径>` 一行合入实际加载的 config.pro（生成片段不会被自动读取）。
4. 正常重启 Creo 后条目应自动出现（`delay_start true` 仍需手动 Start）。
5. 查询 `creo_callback_status`：`readiness=ready` 才提交直接混合；`not_loaded`（可确定未加载，含首次）的 `instruction` 首行即注册入口，`unknown` 表示无法确认，保守处理。

MCP 不会代为注册、加载 DLL 或修改 Creo 安全策略。完整流程、升级/回退与限制见 [生命周期说明](docs/CALLBACK_LIFECYCLE.md)。

## 建模能力

| 类别 | 工具及能力 |
| --- | --- |
| 零件与建模计划 | `creo_new_part`、`creo_execute_plan`：新建毫米零件，或对已有 MCP 零件逐步追加特征 |
| 草图 | `creo_create_sketch`：直线、中心线、圆、圆弧、矩形、多段线、样条、椭圆；显式尺寸和约束；auto/autodim/coordinates 尺寸策略。结果 `profile` 另带 `weldability{available, weldable, max_endpoint_gap_mm, weld_tolerance_mm, tolerance_source, guarantee_scope, exceeding_pairs≤20, note}`：`weldable` 是**风险标记**而非判决——`true` 表示端点落在已测安全界内（既有 1e-9 mm epsilon），`false` 只表示“超出已测安全界、未被证明可焊”，**不代表拉伸会失败**；2026-11-02 本机 Creo 12.4 实测 8.215e-7 mm 间隙拉伸成功。不可判定时为 null。默认只报告不拒绝，闭合放行仍是 1e-4 mm |
| 拉伸 | `creo_extrude`：实体增材、切除、贯穿切除、曲面、薄壁、正/反向、对称深度、新实体；切除未去料（板外草图、方向/深度错误或已去除区域）时失败回滚，成功操作详情返回material_removed_mm3 |
| 旋转 | `creo_revolve`：实体旋转、旋转切除、指定角度，使用草图中心线或外部轴；提供曲面、薄壁和对称角度分支；切除零去料同样失败回滚并返回material_removed_mm3 |
| 孔 | `creo_hole`：原生直孔及可选沉孔／沉头，平面定位，两条独立平面参考或共面直边及有符号偏置；通孔或盲孔，flip 反转切削侧。沉孔/沉头 T12 指定 3/3 实机通过（180° 按契约拒绝）；其余尺寸编辑仍待验。**口径可读**：结果带 `depth_basis`（`tip`/`not_tip`/null）、`depth_scheme_code` 与 `depth_scheme_query`，由创建后特征树实读 `PRO_E_HLE_DEPTH_DIM_TYPE`；0.10.0 起 custom 盲孔为**钻尖口径**（`depth` 量到钻尖），普通直孔走另一元素树故该项为 null，不猜测 |
| 修饰特征 | `creo_round`、`creo_chamfer`、`creo_shell`：恒定半径圆角、等距倒角、恒定厚度抽壳；用查询得到的边/面 ID 选引用。round/chamfer 支持边集合或**面配对** `{"surfaces":[面A,面B]}`：A/B 是当前模型中共享待倒圆（角）边的两张已有面，例如 `[{"surfaces":[{"kind":"surface","id":11},{"kind":"surface","id":13}]}]` |
| 基准与重复 | `creo_datum_plane`、`creo_datum_axis`、`creo_dimension_pattern`：偏移/角度基准面、基准轴、一方向尺寸阵列 |
| 镜像、扫掠、拔模 | `creo_mirror`：整体/几何镜像；`creo_sweep`：恒定截面及命名截面尺寸；`creo_draft`：恒角、不分割拔模。`draft_geometry` 同时给出 `requested_flip`（入参原样）与 `effective_flip`（特征树实读，读不到为 null），既有 `flip` 保留；创建被拒时追加 `draft_failure{requested_flip, angle_deg, surface_count, element_errors{total,truncated,sample≤20}, classification, note}`，`classification` 只在 `kernel_element_error` 与 `no_element_evidence` 之间二分，不推断几何可行性 |
| 钣金 | `creo_new_sheetmetal`、`creo_sheetmetal_wall`、`creo_sheetmetal_flange`、`creo_sheetmetal_unbend`、`creo_sheetmetal_bend_back`、`creo_sheetmetal_flat_pattern`：首壁参数建模前校验、可选 `relief`（默认 `none`）、折边、展开、折弯回去和平展；钣金建模先用 `creo_new_sheetmetal` 并等其终态，`creo_execute_plan` 无 `model_id` 默认新建普通 part、不隐式转换钣金；unbend/bend_back/flat_pattern 的 `fixed_surface` 是裸面引用（如 `{"kind":"surface","id":N}`，取自巡检），能否固定由原生执行判定；首壁五组已在 0.8.4 实机通过；0.8.5 两道折边几何与方向通过；0.10.0 起附着边端部邻接既有折弯时创建前拒绝（`failure_reason=adjacent_bend_ends`，revision 不变）；四壁仍不支持、relief 去料未证实；钣金体并入式实体 add 明确拒绝。**0.9.0 起新增** `creo_sheetmetal_flange` 的可选 `end_trim_mm`：模型单位的正数（`>0`，上限 100000，布尔值拒绝），把两侧链端各缩短该长度，缺省时元素树与旧行为完全一致；**三轮实机实测均为 `trim_ignored`（修剪未生效），链端 setback／截面起算两种读法都未成立，语义未定，属诊断用途**，先用自由壁探针实测再依赖修剪几何；**首壁帧契约（DEV-053 P08）**：`depth` 沿有符号草图法向单侧生长（`direction=positive`→+法向、`negative`→−法向），`thickness` 是以草图线为中心、面内垂直于线的板厚；标准水平底板配方见 `examples/sheetmetal_base_yz.json`（YZ+offset92.5、线 (−116,0.5)→(116,0.5)、depth=185、thickness=1、`direction=negative`，得 X±92.5/Y±116/Z[0,1]、V=42920、COG(0,0,0.5)）；`wall_contract` 回显实测帧（`frame.sketch_normal`/`depth_direction`/`thickness_direction`/`material_side`）、`wall_face_ids`（绿/白壁面，即折边可挂接的面）与零件级板厚——只看体积（如 V=42920）无法发现 depth/thickness 写反或壁面朝向错（0.9.0 反馈的旧写法 185×232×1 板体积/质心看似全对，但绿/白壁面是 185×1 窄条，折边挂接报 `PRO_TK_BAD_CONTEXT -8`，该报错现附带含草图平面/方向的修正提示与官方例子）；`thickness≥depth` 只给不阻断的 `parameter_hint` 警告，不按 5mm 或 t>depth 拒绝合法厚板；钣金件巡检附带 `wall_contour_check` 有界查询（每边一次 `ProSmtedgeContourGet`，保留真实 query_code，`wall_contour_status=eligible|ineligible|unknown` 由 `creo_mechdog.sheetmetal` 投影并带当前 revision；`eligible` 仅代表该边在绿/白壁面轮廓上，**不代表折边必成**——`adjacent_bend_ends` 创建前拒绝不因此解除，选边始终按当前巡检几何而非历史 edge id）。**壁面归属未定因**：2026-10-31 反馈的 YZ 底板只有 X=±92.5 短边进入壁面轮廓、Z=0 两条长边报 `-8`，本仓库已能事前查询三态但不解释“为何只有短边合格”，配方与准入口径按 [BUG-103](docs/work-items/BUG-103.md) 跟踪，未定因前不宣称四壁可用 |
| 装配 | `creo_new_assembly`、`creo_assemble_component`、`creo_component_placement`、`creo_component_constraints`、`creo_remove_component`、`creo_list_components`：组件版本快照、定位（XYZ Euler 按 X→Y→Z 逐次应用，或互斥的嵌套 3×3 `rotation_matrix`；行向量与毫米平移约定见 [ASSEMBLY_REBUILD.md](docs/ASSEMBLY_REBUILD.md)）、约束、删除和查询；含组件操作的作业附 `component_changes` 有界变更摘要（committed/rolled_back/unknown_outcome），`list_components` 约束保留数字 `type` 并附 `type_name` 符号；单作业插入多个组件与官方重建管线见 [ASSEMBLY_REBUILD.md](docs/ASSEMBLY_REBUILD.md)；矩阵放置子项已在本机 Creo 12.4 实机通过（0.6.0 交付，38 父作业含故意失败回滚），显式源件更新与嵌套装配仍开放，见 [FEAT-012](docs/work-items/FEAT-012.md)。`creo_list_components` 的每条组件记录另带业务身份字段 `identity`/`labels`/`label`/`label_state`/`source_model_id`/`source_revision`/`bindings`，顶层带 `deleted_identities` 与 `identity_key`；关联键是**模型身份 + feature_id**，label 只是业务名，删除重插后旧标签不误指新组件 |
| 装配上色 | `creo_recolor_assembly`：给 **MCP 受管的单层装配**按零件族上色。省略 `families` 时按组件绑定中唯一的 `source_model_id` 自动分族，也支持显式族表 `families={族名:[组件标签或特征ID]}`；`palette` 给出各族 RGB（三个 `0..1` 有限数值，拒绝布尔值），写入时须完整匹配所有族；自动分族时键也可写成唯一的组件标签，或直接 `random=true` 由服务端按族名稳定生成一套颜色（与 `palette` 互斥，`dry_run` 与执行都会回显解析后的 `palette` 与 `palette_source`，作业里记录的是显式颜色，重放不重跑随机）。旧检查点若没有组件外观基线会默认拒绝，可显式 `refresh_baseline=true`，以当次作业前的实读外观作为回滚基线（回执 `baseline_source=adopted_live`，默认 `checkpoint`）；`dry_run` 会在缺基线时返回可直接照抄的 `next_action`。`dry_run=true` 为分组预览：不连接 Toolkit、不创建作业、不推进 revision，分页返回分组、计数与未匹配项且单页不超过 32 KiB；执行走现有作业通道（`creo_get_job` 轮询），始终保存，成功后 revision 加一。颜色写在**装配组件层**，源零件文件字节不变。同步提供 `recolor_assembly` 计划操作供 `creo_execute_plan` 使用（只选择操作前已存在的组件，不接受预览参数）。**边界**：仅 MCP 受管单层装配；独立零件、面级、嵌套装配与外部装配不在此版；随 0.11.0 交付，本机 Creo 12.4.0.0 实机验收通过（80 组件/12 族 28/28 检查），WorkBuddy 黑盒与其他 Creo 版本未测，见 [FEAT-052](docs/work-items/FEAT-052.md) |
| 新增曲面与实体 | `creo_surface_fill`、`creo_thicken`、`creo_solidify`、`creo_boolean_bodies`、`creo_rib` |
| 新增基准 | `creo_datum_csys`、`creo_datum_points` |
| 原生工程图 | `creo_new_drawing`；图纸、一般/投影视图、尺寸显示、注释、表格及编辑/删除；原生 DRW 与 PDF 输出 |
| UDF 特征库 | `creo_inspect_udf`、`creo_create_udf`：查询并复用用户的 .gph，保留组内原生参数特征 |
| 普通混合种子复用 | `creo_new_loft_part`：按新 XY 截面和模式自动选择随包种子；自动匹配 2/3/4/6 的直线和平滑及 5 的平滑，其他数量需显式兼容种子或使用直接混合；`creo_list_seeds`、`creo_validate_seed`、`creo_install_seed_library` |
| 翼型与几何编辑 | `creo_create_airfoil_section`、`creo_new_airfoil_blade`、`creo_set_airfoil_parameters`、`creo_update_sketch_geometry`；原生草图和 Blend，弦长/厚度/扭转/原点参数 |
| 定位及特征组织 | `creo_transform_geometry`、`creo_set_geometry_transform`、`creo_group_features`、`creo_reorder_features`、`creo_axis_pattern`、`creo_feature_state`；完整实体/quilt 原生定位、原生局部组和轴阵列；`creo_feature_state` 按 `delete`/`suppress`/`resume` 操作已有零件或钣金模型的特征（目标用特征标签或特征 ID，带依赖闭包准入、墓碑与抑制登记，失败真实回滚） |
| 直接混合及追加 | `creo_loft`：独立 XY 草图按 Z 递增，直线/平滑原生实体混合；支持受管零件的默认实体增材 |
| 参数化修改 | `creo_set_dimensions`、`creo_set_sketch_dimensions`、`creo_set_parameters`、`creo_set_relations`：编辑特征尺寸/草图尺寸、零件参数、简单算术关系式，重新生成依赖特征 |
| 特征树与拓扑查询 | `creo_inspect_model`、`creo_refresh_model`、`creo_list_models`：特征 ID、名称、类型、状态、尺寸、草图尺寸、几何引用 ID、面/边/实体、体积、包围盒、参数和版本 |
| 高级原生特征接口 | `creo_create_feature_tree`、`creo_lookup_constants`、`creo_dump_feature_tree`：按照本机 SDK 的 Element Tree 结构创建特征，查询常量、导出特征 XML |
| 保存与导出 | `creo_regenerate`、`creo_save_model`、`creo_export_model`：保存原生 PRT/ASM，导出 STEP、IGES、STL、JPEG；已登记装配可显式选择 `native_bundle`，结果含 manifest 与 `complete`，新目录可打开性待实机；两件导出与隔离回导已实机通过，嵌套装配与缺件场景仍开放，见 [FEAT-031](docs/work-items/FEAT-031.md) |
| 环境与任务 | `creo_check_environment`、`creo_session_status`、`creo_capabilities`、`creo_get_job`、`creo_list_jobs`：环境、实际 Toolkit 连接、能力和任务进度 |
| 磁盘模型打开 | `creo_open_file`：只读检索并显示磁盘既有 `.prt`/`.asm`（显式 `.N` 版本或目录内最高数字版本）；同名同类型会话模型与非空会话装配拒绝，冲突提示含装配依赖加载来源；缺件装配报残留对象、缺件清单标记未知；不保存、不擦除、不接管，成功返回 `model_id=null`，并附有界 `loaded_session_models` 摘要（区分会话模型数与组件实例数） |
| 注册表维护 | `creo_registry_health`：只读报告每个模型登记的字节数、16 MiB 读取预算占比、详情（别名/检查资料）形态与状态（正常/接近预算/超限/损坏/旧内联格式），单条异常不终止整份报告，不连接 Toolkit。`creo_migrate_registry`：`inspect` 列出仍内联详情的条目（含超限项）及其作业证据链；`apply(idempotency_key)` 先备份原始字节为 `*.pre-split-bak`，把详情写入内容寻址 sidecar 后原子发布控制记录，并把每个动作追加到 `models/registry-migration.jsonl`。重复执行幂等、中断可续作；不提高预算、不删除文件，原始原生结果保持原样 ；apply 持有共用非阻塞通道锁并核验 owner，targets 仅接受合法 model_id。health、迁移 inspect/apply/幂等回放均受完整 32 KiB 响应预算约束，使用 limit/cursor 逐页读取；登记变化后 inspect/health 游标需重采 |
| 会话模型擦除 | `creo_erase_session_models`：显式擦除选定的会话模型清单。`inspect(targets)` 返回每项目标身份、阻断原因、装配先于组件的擦除顺序、预期剩余对象和 600 秒令牌；`apply(evidence_token, idempotency_key)` 只执行令牌中的清单并返回 `job_id`。仅限有盘、未修改、非受管、无清单外引用与依赖环的对象；逐项复核后经两次独立查询确认消失；中途失败停止并明确报告已完成/未确认清单。不保存模型、不删除磁盘文件 |
| 世代回收 | `creo_reclaim_generations`：显式回收本项目自有的 loader/payload 世代目录。`inspect` 只列 `creo_callback_status.generation_inventory` 中可证明未被引用的世代并签发 600 秒证据令牌，`apply` 只删除令牌清单内目标且幂等键回放不重复删除；当前、已注册、运行中、回退保留与记录缺失/损坏/冲突的世代一律保留，不连接 Toolkit、不加载 DLL、不在启动或升级时自动清理 |
| 快捷底板 | `creo_create_plate`：兼容此前矩形底板、角圆角、独立通孔接口 |

特征保存为 Creo 可编辑的草图、拉伸、旋转、孔、圆角等，保留尺寸及依赖。多段线和矩形会展开为原生直线，不能将 `polyline` 名字当作单个尺寸引用；例如 `box_0` 是矩形第一条边。

0.8.0 接口增量：圆弧 `dir` 只接受严格整数，零扫角和整圆输入拒绝；弧结果回显原生几何而非按输入推算。钣金首壁不再静默改写不一致参数，而是在建模前拒绝；`relief` 省略时为 `none`。0.8.4 修复首壁准入将草图坐标系误计为几何的阻断，本机 T03 五组已通过。0.8.5 折边默认方向改为从选中面向外，并明确拒绝钣金体并入式实体 add，升级须检查 `flip` 和拒绝码。装配组件可使用业务标签定位，回转特征返回实际原生轴查询结果；未知几何明确保持未知。多操作请求、`feature_state`、独立 `draft` 及失败后 `rolled_back` 的前置重建边界以各工具实际返回为准。其余原生行为按各项实机证据与未测范围判断。

**0.11.4 接口增量：**SDK 常量生成对缺失头文件按"跳过读取、不生成 include"处理，Creo 10 缺 `Probbl.h` 时不再中断构建；草图创建/编辑结果新增顶层 `sketch_shifted`（`detected`/`rigid`/`translation_mm`/`max_point_mm`/有界 `sample`），`accepted_by_request=true` 表示该草图仅在显式 `geometry_tolerance_mm` 下被放行、并非精确求解；`geometry_deviation` 只增 `shift_detected`/`accepted_by_request`；坐标模式试点用投影基准线钉住草图坐标原点。`creo_save_model` 的 origin 不匹配与 `creo_erase_session_models` 的 `modified` 拒绝现在直接给出可照抄的下一步调用。公开工具数不变（95）。

**0.11.1 接口增量：**`datum_plane` reference 新增 `through_points` 形态；草图创建/编辑可选 `geometry_tolerance_mm`；作业终态新增 `failed_model_cleanup` 回执与 `rollback_status` 字段、全程 `stage` 上报；`creo_get_job`/检查类结果采用有界回执（`total`/`truncated`/`sample≤20`）与 compact 32 KiB、full 游标分页；Toolkit 通道对背靠背提交立即 busy（不排队）。公开工具数不变（95）。逐项状态见 [0.11.1 版本说明](docs/RELEASE_NOTES_0.11.1.md)与[统一台账](docs/BACKLOG.md)。

**0.11.0 接口增量：**新增公开工具 `creo_recolor_assembly`（自动分族/显式族表/dry_run 预览）与计划操作 `recolor_assembly`；`creo_list_components` 每组件新增三态 `appearance` 字段；作业结果新增 `recolor` 证据块（含读回与回滚核验）。首版仅覆盖 MCP 受管单层装配；族表必须无重复且完整覆盖全部组件。逐项状态见 [0.11.0 版本说明](docs/RELEASE_NOTES_0.11.0.md)与[统一台账](docs/BACKLOG.md)。

**0.10.1 接口变化：**`creo_capabilities` 概览深度/方向枚举三键化（`extrude_depths` 键移除）；基准面 `angle`+非零 `offset`、缺 `kind`、非法 angle 轴类型入队前拒绝（0.9.0 前同类输入会静默丢 `offset` 后“成功”）。逐项状态见 [0.10.1 版本说明](docs/RELEASE_NOTES_0.10.1.md)与[统一台账](docs/BACKLOG.md)。

**0.9.0—0.10.0 接口增量：**`creo_sheetmetal_flange` 可选 `end_trim_mm`（正数、两侧链端缩短，诊断参数，两轮实机实测 `trim_ignored`、语义未定）；`revolve_axis` 的 `section_centerline_count` 改为只计用户中心线并发布草图 `entity_ids`（0.10.0 实机验证）；`creo_list_components` 的组件身份投影补保存重载与删除重插回归锁定（0.10.0 实机验证）；`round`/`chamfer`/`draft` 结果新增体积差与 `draft_geometry`/`reference_application` 回报（0.10.0）；折边邻接折弯端 `adjacent_bend_ends` 创建前拒绝（0.10.0）。逐项状态见 [0.10.0 版本说明](docs/RELEASE_NOTES_0.10.0.md)与[统一台账](docs/BACKLOG.md)。

提供接口不等于所有参数组合都已验证。[直线混合摘要](docs/validation_loft_seed.json) 与 [平滑混合摘要](docs/validation_loft_smooth.json) 保留两截面的历史测试；[其他开发功能摘要](docs/validation_development.json) 和 `build/capability_evidence.json` 是此前测试的历史证据，本轮未重跑其完整套件。已测试非矩形支架、带内孔和沟槽的轴类件、多实体圆弧/椭圆实体、样条拉伸曲面、薄壁对称拉伸、抽壳、边圆角和倒角、尺寸阵列及参数关系驱动。高级树接口需要符合 SDK 的具体特征定义，不能自动补齐任意缺失的草图或集合。

## 接入与调用

把以下本地 stdio 服务配置加入支持 MCP 的客户端：

```json
{
  "command": "C:\\MCP_CREO_MechDog\\.venv\\Scripts\\python.exe",
  "args": ["C:\\MCP_CREO_MechDog\\server.py"]
}
```

上述路径仅为示例，以安装生成的实际路径为准。服务名称及客户端注册键为 `MCP_CREO_MechDog`。`client-config.json` 是同一配置的 `mcpServers` 格式；不同客户端的配置格式可能需要转换，必须保留相同的 command/args。服务启动后客户端可发现工具的完整 JSON Schema。服务从自然语言规划器接收结构化建模操作；自然语言理解由调用它的 AI 客户端完成。

典型流程：

1. 调用 `creo_check_environment`、`creo_session_status` 检查本机环境并实际连接。
2. 使用 `creo_execute_plan` 一次创建完整零件，或用 `creo_new_part` 后分步调用草图及特征工具。
3. 建模工具立即返回 `job_id`；轮询 `creo_get_job(job_id, detail="compact")`，等待 `status == "succeeded"`，并检查 `result.saved_file_reloaded_and_verified == true`。需要完整几何和尺寸时使用 `detail="full"`；该值仍是单任务查询的默认值。`creo_list_jobs` 默认返回精简结果。
4. 保留 `model_id` 和最新 `revision`。修改已有零件时提供 `expected_revision`；版本不一致会拒绝旧请求。新建模型的受理返回携带登记时的 `revision: 0`，成功终态把它推进到 1；后续编辑先等 `creo_get_job` 返回终态，再以最新 revision（或重新 inspect）作为 `expected_revision`，不要把终态前的受理值或中间快照当成权威（2026-10-31 对 4035 份本机作业记录的离线核对：1286 个新建作业终态 revision 均推进、100 个失败作业保持 0、无终态与登记不一致，唯一例外是已知的 `unknown_outcome` 保护现场）。
5. 查询实际面/边/尺寸 ID 后追加特征。引用发生变化时重新查询，不复用猜测的拓扑 ID。

Toolkit 操作共用一个通道，提交时忙碌会立即拒绝；响应保持 MCP `isError=true`，JSON 文本与 `structuredContent` 同时给出 `status="busy"`、`accepted=false`、`blocking_job_id`、`blocking_model_id`、`blocking_operation`、`retry_after_seconds` 和 `retry_guidance`。未创建新任务。占用者可能是任务、提交登记、连接探针或构建；无法确定时 ID 为 null，不能猜测最近的任务就是占用者。1 秒是建议重查间隔，不是完成时间承诺。已接受的任务只轮询，不重新提交；未知结果先检查模型。

任务模型登记（revision、pending_job、保存结果）在锁内收尾，释放通道后才发布持久化终态。观察到旧任务 succeeded 后，其他客户端仍可能取得通道，此时按新响应的占用者处理。`creo_get_job`、`creo_list_jobs`、`creo_inspect_model`、`creo_list_models` 读取持久化快照，不等待 Toolkit；`creo_refresh_model`、导出和实际连接检查仍需要通道。已接受后台 runner 最多等锁 120 秒；没有公开 FIFO、容量或排队顺序保证，本次没有增加队列能力。开发与 WorkBuddy 验收范围见 [BUG-009](docs/work-items/BUG-009.md)。

例如创建有原生特征树的圆柱：

```json
{
  "operations": [
    {"op":"sketch","label":"profile","plane":"XY",
     "entities":[{"type":"circle","name":"circle","center":[0,0],"radius":10}],
     "dimensions":[{"name":"diameter","type":"diameter","refs":[{"entity":"circle"}],"value":20,"position":[15,0]}]},
    {"op":"extrude","label":"solid","sketch":"profile","depth":30}
  ],
  "assertions":{"require_solid":true,"volume_mm3":9424.77796076938}
}
```

随后 `creo_set_sketch_dimensions` 使用 `sketch:"profile", values:{"diameter":24}` 修改直径；拉伸实体随之更新。`creo_set_dimensions` 接收查询结果中的模型尺寸 ID，例如 `values:[{"id":18,"value":40}]`；实际 ID 由 Creo 生成。

完整案例在 `examples/`；0.21 新增镜像、扫掠、拔模和钣金首壁计划；装配重建管线与单作业多组件示例见 `examples/assembly_rebuild_pipeline.json` 与 `examples/assembly_multicomponent_plan.json`（说明见 [docs/ASSEMBLY_REBUILD.md](docs/ASSEMBLY_REBUILD.md)）；装配按零件族上色的显式族表与色板示例见 `examples/assembly_recolor_families.json`（说明见 [FEAT-052](docs/work-items/FEAT-052.md)）。装配调用步骤见 [docs/MODELING_0.21.md](docs/MODELING_0.21.md)。尺寸阵列先建立引导孔，再查询其定位尺寸 ID，调用 `creo_dimension_pattern`，指定包含引导成员的总数量和每次增量。

### 能力发现示例

以下四个最小请求覆盖最常被问到的入口。全部经当前 schema 的 `validate_operations` 校验通过（2026-10-30 离线核对），**示例本身不是新的实机证据**；各能力的已验范围以台账与各验收卡为准。

**一次 `creo_execute_plan` 提交多个操作**（草图 → 拉伸 → 孔，同一作业一次 revision、一次保存重载）：

```json
{
  "operations": [
    {"op":"sketch","label":"profile","plane":"XY",
     "entities":[{"type":"rectangle","name":"r","min":[0,0],"max":[60,40]}]},
    {"op":"extrude","label":"solid","sketch":"profile","depth":12},
    {"op":"hole","label":"main_bore",
     "placement":{"kind":"plane","axis":"z","offset":12},
     "reference1":{"kind":"datum_plane","axis":"x","offset":30},
     "reference2":{"kind":"datum_plane","axis":"y","offset":20},
     "diameter":10,"depth":12}
  ],
  "assertions":{"require_solid":true}
}
```

**`creo_feature_state` 删除／抑制／恢复特征**（目标是特征标签或特征 ID；同一批目标必须互不相同）：

```json
{"operations":[{"op":"feature_state","action":"suppress","targets":["main_bore"]}]}
```

```json
{"operations":[{"op":"feature_state","action":"resume","targets":["main_bore"]}]}
```

```json
{"operations":[{"op":"feature_state","action":"delete","targets":[18]}]}
```

**独立拔模 `creo_draft`**（恒角、不分割；`surfaces` 是裸面引用数组，`neutral_plane` 与 `pull_direction` 是裸单引用）：

```json
{
  "operations": [
    {"op":"sketch","label":"base","plane":"XY",
     "entities":[{"type":"rectangle","name":"r","min":[0,0],"max":[20,20]}]},
    {"op":"extrude","label":"solid","sketch":"base","depth":20},
    {"op":"draft","label":"taper",
     "surfaces":[{"kind":"plane","axis":"x","offset":20}],
     "neutral_plane":{"kind":"datum_plane","axis":"z"},
     "angle":3}
  ]
}
```

**组件标签查询**（标签是业务名，身份是模型身份 + feature_id；删除重插后旧标签不误指新组件）：

```json
{"model_id": "<装配 model_id>", "tool": "creo_list_components"}
```

返回的每条组件记录带 `identity`、`labels`、`label`、`label_state`（`single`/`multi`/`unlabeled`）、`source_model_id`、`source_revision`、`bindings`；顶层另返回 `deleted_identities`（旧 feature_id 不再出现在当前组件集时单独列出）与 `identity_key`。放置与约束按 label 引用组件，例如 `{"op":"component_placement","component":"part_alpha","translation":[0,0,25]}`。

**钣金折边两端缩短（0.9.0 起；诊断参数，语义未定）**：

```json
{
  "model_id": "<钣金 model_id>",
  "expected_revision": 1,
  "label": "trimmed_wall",
  "edge": {"kind":"edge","id": 12},
  "height": 20,
  "angle": 90,
  "radius": 1,
  "flip": false,
  "y_factor": 0.5,
  "end_trim_mm": 20
}
```

`end_trim_mm` 是模型单位的正数，缺省时元素树与旧行为完全一致。**Creo 究竟把它读作「距链端各内缩 setback」还是「自截面起算的壁长」两轮实机均未成立（实测 `trim_ignored`、修剪未生效），语义未定**，因此它是诊断参数：先在一道两端均为自由角的自由壁上探测并用实测体积分类，再决定是否用于修剪对照；不要仅凭回显就认为修剪已生效。

## 坐标、引用与参数

长度使用毫米，角度使用度。草图输入是平面内的 `(u,v)`：

| 平面 | u | v | 正向法线 | offset |
| --- | --- | --- | --- | --- |
| XY | +X | +Y | +Z | 世界 Z 坐标 |
| XZ | +X | +Z | −Y | 世界 Y 坐标 |
| YZ | +Y | +Z | +X | 世界 X 坐标 |

`direction:"positive"` 沿表中正向法线，`negative` 反向。对称拉伸的 `depth` 是总深度。圆弧起止角以输入平面 u 轴为零度，沿 u→v 逆时针。

平面也可传入 `{"reference":{"kind":"surface","id":实际ID},"origin":[x,y,z],"u_axis":[x,y,z]}`，用于已有平面面或基准面。默认原点是世界原点到该平面的垂足；指定原点必须在平面内。基准面的方向和生成几何由 Toolkit 决定，应按查询结果使用。

`creo_datum_axis` 的操作详情包含 `datum_axes` 与 `axes_query_code`；`creo_inspect_model(detail="full", section="datum_axes")` 分页返回已保存快照中的原生轴几何。`origin` 是原生轴线上的一个点（不保证是离原点最近点），`direction` 是原生两端点差的单位向量。坐标使用实际模型长度单位；同层 `length_unit` 提供单位名、到毫米的比例及原始查询码。查询失败/未执行或几何退化时使用 null/`geometry_known:false`，不得把输入引用猜成几何。巡检 `center_of_gravity` 同样使用原生长度单位，查询结果由 `volume_query_code` 记录；尚无实体或质量查询失败时为 null。上述接口已随 0.7.0 交付。倾斜面与主平面的正/反/对称盲深拉伸（800 mm³、完整 AABB 与重心）及贯穿去料（48/48/96），以及偏心 `(4,-3)` 两平面交线轴、基体柱面轴的正余弦阵列，已在本机 Creo 12.4 实机通过 18/18 并逐个保存重载（[T05 Live03](docs/development/DEV047-T05-ACCEPTANCE-2026-10-26.md)）。仍未覆盖：外部 Creo 9/10、非毫米与单位未知场景，以及无基准轴模型上的倾斜面草图（日志 `SKETCH_REFERENCE_INCOMPLETE`）。

常用引用：

```json
{"kind":"datum_plane","axis":"x","offset":0}
{"kind":"plane","axis":"z","offset":30}
{"kind":"surface","id":123}
{"kind":"edge","id":456}
{"kind":"axis","id":78}
{"kind":"datum_feature","label":"offset_plane"}
{"kind":"datum_axis_feature","label":"axis"}
```

`plane` 选择实际实体平面面，必须唯一；有多个匹配面时使用查询得到的 `surface` ID。`datum_plane` 的零偏移主平面选择模板中最早的对应基准，避免与 Creo 自动生成的内部基准混淆。非零偏移仍要求唯一。草图/拉伸等特征间用 `label` 引用；标签须匹配 `^[a-z][a-z0-9_]{0,27}$`，即以小写字母开头，其余仅用小写字母、数字或下划线，总长最多 28 字符，例如 `i001_part1`。服务不会自动改名。

显式尺寸支持长度、半径、直径、点间距离/水平距离/垂直距离、线间距离、夹角、圆弧角度和椭圆半轴。约束接口包含水平、垂直、重合、点在线上、相切、垂直、等半径、平行、等长、共线；实测包括水平/垂直约束及驱动直径尺寸，其余组合由原生求解器验证。

关系式当前接受简单算术赋值，例如 `d18 = LENGTH / 2`；替换零件当前关系式集合。参数支持数字、布尔值和字符串。

## 验证、恢复与当前边界

每次修改成功后，执行器检查单位、所有原生特征的活动/完整状态及实体状态；保存 `.prt.N` 或 `.asm.N`，擦除该 MCP 零件的内存模型，从实际保存文件重载、重新生成，再对比特征 ID/类型/名称、尺寸值、实体数量、体积和参数。可额外提供 `require_solid`、`volume_mm3`、`volume_tolerance` 断言。体积计算临时使用密度 1，不修改材料。

**默认摘要与分页接口一览。** 以下三个查询接口默认返回 compact 摘要（小体积、可直接整读），需要全量内容时显式请求并按页遍历；依赖旧全量返回的调用方会静默拿到摘要，不会报错：

| 接口 | 默认 | 取全量 |
| --- | --- | --- |
| `creo_list_models` | compact 模型清单摘要 | `detail="full"`，必要时沿 `next_cursor` 分页 |
| `creo_inspect_model` | compact 快照摘要（身份/revision/体积/计数） | `detail="full"` + `section="dimensions"`/`"surfaces"`/`"edges"`/`"features"` 等，沿 `next_cursor` 分页 |
| `creo_capabilities` | compact 能力摘要页 | `detail="full"` + `section="tools"`/`"families"`/`"references"` 等，沿 `next_cursor` 分页 |

通用规则：单页响应预算 32 KiB，超预算会分页或对单条超限项显式标记；出现 `next_cursor` 时保持相同 `detail`/`section` 继续翻页，翻完即 `complete=true`。`creo_inspect_model` 的分页绑定已保存快照，模型改变后游标失效，应重新查询；`creo_capabilities` 的分页绑定进程内约 600 秒冻结快照，过期 cursor 被拒绝并提示重新首查。

`creo_list_session_models` 的 cursor 语义另有两态：不带 `cursor` 调用时实时重新采集会话清单；携带上次返回的 `cursor` 时读取约 10 分钟的冻结快照分页，不反映快照创建后的会话变化。因此"打开/擦除模型后要确认会话现状"时应省略 `cursor` 重新查询；需要稳定遍历时沿用 `cursor`。结果中的 `snapshot_age_seconds`/`expires_in_seconds`/`refresh_guidance` 说明快照年龄与刷新方式；`service_session_changes` 列出本服务自快照以来记录的会话内容变化（跨进程、有界），GUI 手工变化不在其中、未实时复核。`creo_open_file` 成功结果的 `open_file.opened_session_model` 直接提供刚打开模型的单条会话观察（字段与会话枚举条目一致，另含 `observed_at`）；`open_file.loaded_session_models` 提供打开后的有界会话摘要（会话模型数、组件实例数与详情入口），不必立即发起全量枚举。

`creo_list_models` 与 `creo_inspect_model` 默认返回 compact 摘要，保留身份、revision、状态、体积、真实计数和快照时间。需要几何时显式使用 `detail="full"`，可指定 `section="dimensions"`、`"surfaces"`、`"edges"`、`"features"` 等。详情默认每页50条、最多200条，响应预算32 KiB；出现 `next_cursor` 时保持 detail/section 继续分页，模型改变后重新查询。大快照的 `data` 按 section 返回；特征内的尺寸、几何项和草图尺寸分别分页，未知计数为 null，不能当作0。小快照的 full 保留原 inspection/aliases 布局。Python调用方可用 `creo_mechdog.query_client.read_full_model` 收集全部页并重建快照。

`creo_inspect_model` 返回最近已验证的保存快照，snapshot明确不代表实时状态；人工在 Creo 修改后，用 `creo_refresh_model` 获取实况。实时查询不会替换已保存模型的基线，也不会保存或接受人工修改。已有模型修改前会检测模型与记录是否一致；因任务失败或人工修改而不一致时，不应盲目重复提交。失败作业的 inspection 仅在恢复并验证成功时代表恢复模型；失败中间状态另列 failure_inspection，无法取得真实状态时为 null。

恢复失败按实际阶段返回原因：执行器派发前的证据校验拒绝返回 `failed` / `before_native`，在锁内仅释放本次恢复占位；原生执行器可能已开始时仍为 `unknown_outcome` 并保留保护。原生会话指纹拒绝发生在连接之后，不能因消息含 refused 就自动重试。见[恢复契约](docs/MODEL_RECOVERY.md)。[隔离 MCP 契约验收](docs/validation/DEV-040-isolated-contract-2026-10-18.md)已通过，不代表真实 Creo 会话切换、中断、几何或并发恢复已全部验收；剩余范围按台账跟进。

`creo_loft.sections` 和计划中 `op="loft"` 支持草图标签、整数feature_id，以及为客户端兼容接受的纯十进制数字字符串；例如 `[40,"49"]` 归一化为整数ID。归一化后的重复引用被拒绝，不影响其他参数的字符串语义。原生几何与公开客户端验收范围仍分别记录。

现有 MCP 零件任务失败，会尝试从任务开始前的保存文件恢复；只有 `rollback_succeeded` 确认成功才能继续。版本号不随失败增加。辅助进程崩溃、超时或结果不能确认时标记 `unknown_outcome`，保留现场供检查。新零件失败可能留下本任务的部分模型。

未知作业保留 `pending_job`，`creo_get_job` 的 `recovery` 提供执行器身份、断开前检查点及已保存基线；检查点不等于成功，也不自动提交 revision。原生断开有 20 秒 helper 看门狗，只退出自有 helper，不关闭 Creo。`creo_startup_status(retry=true)` 只重新核实通道及安全启动条件，不能解锁或重放未知作业。启动等待区分 `waiting_for_channel` 与 `building_worker`，preparation 为 180 秒，总预算为 180 秒加配置的启动预算；到期仍在执行时说明 in-flight，继续保留保护。状态快照带 `verified_at`、`verification_age_seconds`、`stale`；`creo_session_status` 的独立探针预算为 9 秒，超时返回 `probe_timeout` 和处理指引。

共享启动历史损坏时，仅在核实记录早于本次 Windows 启动、双锁已取得且没有现有 Creo 后，备份原字节并重建启动状态，再由协调器启动 Creo；`startup_recovery` 提供归档与重启依据。同次开机损坏、时钟／会话不确定或备份失败仍返回 `startup_state_unreadable` 和处理说明，已有会话可只读重连。未知任务和模型保护不随启动历史重建而清除，验证范围见[重启恢复记录](docs/validation/BUG-008-reboot-recovery.md)。

目前高层工具覆盖上述常见实体特征，仍有明确范围：

- 持续修改支持本服务创建、登记的零件、钣金模型和装配；用户已在 Creo 打开的未登记模型可通过 `creo_adopt_current_model` 显式接管为受管副本（原件与原会话对象不动，首批独立 part/钣金、mm 单位、无外部依赖；身份按 origin 路径 + 文件哈希 + live 快照证明，不信任显示名）。
- Development branch: `creo_adopt_file` accepts 1-20 ordered source paths with inspect/apply, independent per-item commits and no display/window activation. Existing unmodified exact-origin residents are copied as explicitly inspected session state; their pre-inspection disk/content equality is unknown. Duplicate sources are refused with reuse guidance; unknown outcomes stop remaining items and retain protection. See the [path-adoption contract and its live evidence range](docs/FILE_ADOPTION.md).
- 各类尺寸/约束的复杂组合、极端几何及外部人工修改的自动接管仍需后续扩展。
- 孔支持直孔及可选原生沉孔／沉头；螺纹与标准孔系列未封装。倒角为等距，阵列支持一方向尺寸阵列和原生轴阵列。
- 普通混合支持平行 XY 截面的种子复用及直接创建/追加。随包九个种子覆盖 2/3/4/6 截面的直线和平滑，以及 5 截面平滑；其他数量需显式兼容种子或直接创建并本机验证。直接混合仅支持受管草图、Z 严格递增和默认实体增材。不支持自动增减种子截面、转换连接模式、非平行截面或端点相切/曲率控制。数量上限不代表每种数量都已实测。新零件整体可用原生定位特征移动或旋转。
- 钣金首壁 T03 五组已在本机验证；0.8.5 在真正的 1 mm 板上，两道折边为真实 90° 折弯（各 +18 025.29 mm³、Z 增长 79 mm、保存重载通过，`flip=false` 默认从选中面向外），但**四壁仍只完成 2/4**：第三道 `f_ny` 创建后回滚、第四道未执行，`relief` 目前只确认「请求被接受并回显」，尚无可观测几何去料。板厚同步、释放有效场景与第三壁对照已在开发分支离线交付但**未实机验收**。其他钣金能力及历史验证范围见版本说明和能力文档。镜像、扫掠、拔模、装配、筋和工程图各自具有明确范围；复杂自由曲面及专业模块仍未完整封装。
- 装配插入源模型的版本快照，源模型后续修改不更新组件；子装配复制尚未开放。
- 装配按零件族上色（`creo_recolor_assembly`）首版仅覆盖 **MCP 受管的单层装配**：独立零件、面级、嵌套装配与外部装配不在此版；颜色写在装配组件层，源零件文件字节不变；该能力随 0.11.0 交付，本机 Creo 12.4.0.0 实机验收通过（80 组件/12 族 28/28 检查，含保存擦除重载读回与两种回滚）；WorkBuddy 黑盒与其他 Creo 版本未测，见 [FEAT-052](docs/work-items/FEAT-052.md)。`refresh_baseline`（旧检查点补基线）与色板族名键/`random` 是 0.11.0 反馈后的增量，离线实现与单测已完成、实机未验，见 [BUG-104](docs/work-items/BUG-104.md) 与 [FEAT-056](docs/work-items/FEAT-056.md)。
- `creo_create_feature_tree` 可扩展符合本机 SDK 的特征结构，但无法保证所有 PTC 特征类型和选项均可创建。
- 不承诺任意文字描述都自动成功。AI 需要规划有效的轮廓、基准、尺寸和特征顺序；无效几何由 Creo 返回错误。

服务串行执行 Toolkit 操作，后台检测并复用已有会话，无会话时按配置启动；连接确认前拒绝建模提交，不自动关闭 Creo。输出保存在项目运行数据目录内：`models/`（受管模型登记与输出）、`jobs/`（作业请求/结果/日志）、`open_file/`（磁盘打开的幂等意图登记）、`session_erase/`（会话擦除的令牌与意图登记）和 `session_activity.json`（本服务引起的会话内容变化记录）；升级到新版本时保留这些目录，不要手工删除或合并它们。不提供任意命令／代码执行工具，不输出许可服务器内容或修改安装目录。正在交互建模或有模态对话框时，应先处理该会话状态。

## 开发与测试

安装脚本创建虚拟环境、安装锁定依赖、验证/注册随包种子库、读取本机 SDK 生成常量表、编译执行器并生成客户端配置。首次运行或原生源码改变时也会自动重新编译。`native/constants.inc` 由本机 SDK 生成；不随源码分发。源码包含九个项目原创 MIT 种子 PRT，不含 Creo SDK 库、许可内容、虚拟环境、编译二进制或其他本机测试模型。第三方 JSON 头文件附带其原始 MIT 许可。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\test_mcp.py --classic
.\.venv\Scripts\python.exe tools\test_general.py
.\.venv\Scripts\python.exe tools\test_extended.py
.\.venv\Scripts\python.exe tools\test_guards.py
.\.venv\Scripts\python.exe tools\test_v021.py
.\.venv\Scripts\python.exe tools\test_unit.py
```

除输入验证外，上述集成测试会实际连接 Creo 并创建或修改独立测试模型。`test_v021.py` 默认验证启用功能和禁用接口的拒绝行为；禁用接口的拒绝测试不是建模成功证明。日志位于任务 `native.log`/`runner.log`/`job.json` 和 `build/build.log`；证据在 `build/*integration_test.json`。保存目录较长时应缩短项目路径。

Windows 登记文件读取允许共享删除，写入使用单步原子替换；短暂占用最多重试 1 秒，持续失败保留旧登记并报错，不会自动重复原生操作。登记读写压力与并发实机轮询可分别运行 `tools/test_registry_io.py` 和 `tools/test_registry_native.py --readers 3`。Creo 12.4 结果及历史交接记录见 [BUG-002 验证与交接](docs/validation/BUG-002.md)。

实现依据：[PTC 草图特征 Element Tree 文档](https://support.ptc.com/help/creo_toolkit/protoolkit_plus/usascii/creo_toolkit/user_guide/Element_Tree_for_Sketched_Features.html)、本机 Creo 10 Toolkit 头文件与示例、[官方 MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。实际本机建模成功、保存重载成功的记录才证明该路径可用，SDK/许可环境文件存在本身不能证明许可可用。

完成普通放样实机测试后，可生成它的独立摘要；打包会重新生成本地同版本压缩包：

```powershell
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py --interpolation smooth
.\.venv\Scripts\python.exe tools\package.py
```

摘要命令需要已经完成相应的实机测试；打包命令只选择公开源码及文档。`config.json`、`client-config.json`、虚拟环境、构建结果、任务和模型目录已在 `.gitignore` 中排除。

毫米、英寸与混合装配的单位对照场景由固定矩阵驱动覆盖：`tools/test_assembly_matrix.py`（毫米／英寸组件的 normalized 与 raw 矩阵、已知点对照）和 `tools/test_assembly_units.py`（毫米／英寸／混合与单位查询失败的 null 表达）。这组矩阵是后续新增数值接口（坐标、变换、体积等）的验收模板：新接口必须在毫米、英寸、混合与未知单位四种场景下分别取得证据，未知或查询失败如实为 `null`，不得默认毫米。批处理与拔模官方示例见 `examples/dev047_t12_batch_append.json`（一次计划多特征、单次 revision 与整体回滚）和 `examples/dev047_t12_draft_boss.json`（Ø6×3 凸台 11° 内拔模，`r_top = 3 − 3·tan(11°)` 圆台体积断言）。
