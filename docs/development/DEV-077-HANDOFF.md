# DEV-077：0.18.2 反馈未完成清单（交另一个 AI）

分支：`offline/0.18.2-feedback-gapfill`；起点 `4bd6b7e` / 0.18.4；工作卡 [DEV-077](../work-items/DEV-077.md)、[逐项对照](../validation/feedback-0.18.2-2026-11-08/MAPPING.md)、[离线验收](../validation/feedback-0.18.2-2026-11-08/ACCEPTANCE.md)。

本批只做离线可验证部分：四份原件归档、RELEASING/POSTCHECK/BACKLOG 回填、台账计数门禁、质量属性拒绝诊断、阶段计时回退。**未连接 Creo/Toolkit、未做黑盒、未联网核对远端、未编译新的原生几何能力、未合 main、未发布。** 报告方 Creo 9/10 的正反证据都只是外部证据，不能当本轮实测。

## 已完成，勿重复派工

- `native/generic.cpp` 显式密度分支清残留 reason/hint；`preview.py` 假 path；装配质量属性加守卫；`surface_loft` / `surface_group` 测量 / 保留侧形心判据；`surface_solid.scope` 与 `surface_chain.limits` 文案；0.17.4 反馈归档；DEV-075 卡首页状态；BACKLOG 旧计数（以上来自 DEV-074/075/076）。
- 本批：四份 0.18.2 反馈归档 + MAPPING；RELEASING 第 8 步扩 DEV/BUG 与 DEV-075 行同步；POSTCHECK v0.18.2 四附件数据回填；`tools/check_backlog_counts.py` 自动计数；`normalize_mass_properties` 有界诊断；`stall_report` 回退 `result.verify_stages`（含 bridge 接线与两级单测）。

## 0.19.0 合并后刷新的未完成清单（R01—R08，2026-11-08）

合并提交 `006e357`；[对比与冲突取舍](../validation/feedback-0.18.2-2026-11-08/COMPARE-0.19.0.md)。**以本节为当前清单**；后面的 G01—G13 是 0.19.0 合并前基线，已被闭环或改判的项不再派工。0.19.0 已闭环、勿重复：`creo_quilt_merge` 解禁（两片 JOIN 目标 quilt 三级解析 + 2 mm thicken 实机）、`creo_surface_round` 与 `creo_measure_surface_curvature` 两个公开工具、H10 五爪整瓶整链 46 作业 63 项检查、非平面 fill / 独立 quilt 偏置 / 钣金成形类的实机不可用结论与门禁。

| R | 项目 | 0.19.0 后的当前事实 | 下一动作 / 验收判据 |
| --- | --- | --- | --- |
| R01（原 G01—G03） | 草图容差链、装配旋转矩阵、任意平面一等公民 | 0.19.1 已交付可选 `rotation_tolerance`（默认 1e-6，矩阵原值回显、不修复）；`closure_tolerance_mm` 仍内部常量、`coordinates` 超限仍直接失败、无偏差断言、无 `origin+normal+u_axis` 直接建面工具 | 先在 Creo 9 / 0.19.1 回归确认 F01 三步时间线；再落地可配草图容差/吸附回执/偏差断言，以及独立建面工具；判据见下方 G01—G03 行 |
| R02（原 G04/G05/G08/G10） | 契约与体验：mirror 特征子树、装配质量属性替代工具提示、`execute_plan` 最小示例/分页、`get_job` 长轮询、`known_limitations`、loft callback 退化 | 0.19.1 已交付装配质量属性 `use_tool: creo_inspect_model` 提示、6 个 `plan_examples`、`get_job.wait_seconds` 0–300、12 条结构化 `known_limitations`；mirror 特征子树与无 callback 的 `creo_loft` 仍未实现 | 实现受支持镜像子集与回执、无 callback 两截面直纹实现；继续保持 32 KiB 分页预算与严格默认语义 |
| R03（原 G06） | `session_health` 的 identity stale 与新鲜 connected 证据冲突 | `session_health.py` 仍 `unknown/session_identity_stale` | 先定安全策略（是否允许连接证据优先或 stale 降 warning），不得擅清 unknown 保护；三类样本状态与 caveats 需一致 |
| R04（原 G07/G09 收敛） | 曲面剩余：`INTERSECT`、三片以上单次 `quilt_merge`、被消耗工具 quilt 的内核残留、`PRO_ROUND_REF_EDGE` quilt 边 id、变半径/full/过渡、圆角后 thicken/solidify、真实凹谷瓣底、非 mm 单位、Creo 9/10 复验、格栅 cut 与 BUG-046 矛盾定因 | 0.19.0 只验了两片 JOIN（目标 quilt 原地增长）、恒定半径圆角、数值曲率与 Creo 12.4 整链；RELEASE_NOTES_0.19.0.md 第 36—42 节已逐条声明未测 | 按 release 分别补实机证据；门禁文案与 capabilities 契约同步；不把 Creo 12.4 结论外推到 9/10。判据：两片以外合并语义可复现且无静默 no-op、圆角后实体化可保存重载、45/72° 等几何按任务书逐项吻合 |
| R05 | 已判定不可用（**结论项，不再开工**） | 钣金成形类、独立 `quilt_offset`、任意非平面闭合边界 `surface_fill` 在 Creo 12.4 有实机反证，0.19.0 保持门禁 | 仅维护错误文案/门禁与证据链接；换 release/SDK 或出现新原生证据时才重开工作卡，禁止把不可用结论写成能力 |
| R06（原 G11 + 0.19.0 未测） | 实机与黑盒：Creo 9/10、WorkBuddy 公开 MCP、源码包解压全量单测、本分支新增改动的实机复验 | 0.19.1 已在 Creo 12.4 重编译并完成 H13 身份、H15 四态组、H16 连续 trim 实机；DEV-077 的质量属性诊断/stall 回退仍只有离线单测；Creo 9/10 与 WorkBuddy 未执行 | 补 Creo 9/10 与 WorkBuddy 公开 MCP；补源码包解压后全量单测；对 DEV-077 两项离线修复做适用实机复验。不得把编译/单测当实机通过 |
| R07（原 G12 升级） | 0.19.0 发布后核对与台账回填 | **v0.19.0 / v0.19.1 / v0.18.2 / v0.18.3 / v0.18.4 已联网 `--tag` 重下重算并写入统一 POSTCHECK**；v0.19.0 的 10—12 节占位由勘误收口；v0.19.1 的 10—12 节已回填 | 仅剩 Release body 逐字比对与历史原件不回写；新版本继续按同法执行 |
| R08（原 G13 + 新） | 本分支交付与登记 | **已合入 main 并发布 v0.19.1**（提交 `9dcf5ee`、标签 `v0.19.1`、四附件与两个 sidecar 已核对）；H13/H15/H16 登记在 DEV-076，R01/R02 部分登记在 DEV-077，未新增 ID | 后续新改动必须选未发布新版本；R01/R02 剩余、R03/R04/R06 见本表 |

0.19.1 发布前离线验证：全量 3071 项单测 OK、Ruff/`dev_check --skip-unit` 通过、`git diff --check` 通过、台账计数门禁 168 一致；Creo 12.4 实机完成 H13 身份、H15 四态组与 H16 连续 trim。源码包解压后全量单测与 Creo 9/10/WorkBuddy 仍属 R06。

## 历史清单 G01—G13（0.19.0 合并前的基线，状态见上方 R01—R08）

| 编号 | 项目与当前事实 | 下一动作 | 验收判据 |
| --- | --- | --- | --- |
| G01 / F01 A-1—A-3，P0 | 草图容差链：`closure_tolerance_mm=1e-4` 仍是内部常量；有受控 `weld` 吸附但无 `snap_endpoints` 与完整 entity A/B/gap 表；`coordinates` 偏差 1e-5 仍直接失败、不回退 `autodim`；`assertions` 无 `max_geometry_deviation_mm` / `require_exact_solve` / `preserve_input_geometry`；`auto` 的 entity_count 切换阈值未进 compact capabilities | 先在 Creo 9 / 0.18.4 上重跑 F01 的 P03 三步时间线确认是否仍复现；再按「可配容差 + 吸附回执 + 偏差超限时显式回退或按调用方声明拒绝」三选一落地，参数、拒绝文本与 receipt 同步 | 原 TXT 三位小数圆弧数据可直接提交；吸附点位移与 gap 表可核对；`coordinates` 超限不整作业失败或被显式拒绝；`autodim` 偏差可被断言阻断；compact 能预判 solver 选择；保存重载与回滚通过 |
| G02 / F01 B，P0 | `schema.py:47-70` 正交门槛硬编码 1e-6，25 个装配实例中 14 个被参数校验即时拒绝；无容差配置、无 `orthonormalize`、无建议合法矩阵 | 选一条路线：可配 `orthogonality_tolerance`（默认 1e-6）或 `orthonormalize=true` 且回执回报修正前后矩阵/最大修正量；报错附最近合法矩阵数值 | 4 位小数方向向量按文档原值可装配；默认严格语义不变；修正量可复现；25/25 实例 4×4 变换与 TXT 逐条吻合 |
| G03 / F01 §4，P0 | 字典式平面文档已改成可用的 surface/datum id 形式，但仍无「由 `origin+normal+u_axis` 直接建基准平面/草图平面」的一等公民工具 | 提供独立工具或扩展 `creo_create_sketch.plane`；先定义与既有 surface 解析的优先级与失败语义 | P04 耳板 / P01 凸台可按 `(d,n)` 斜面直接建草图；坐标系回执给出 origin/normal/u/v；无需调用方自行变换轮廓点 |
| G04 / F01 5.1—5.2，P1 | `creo_mirror` 仍拒绝特征子树；装配质量属性已按 parts-only 拒绝，但错误文本没有 `use_tool: creo_inspect_model` 提示 | 镜像按 feature label 提供受支持子集并在 receipt 标注实现路径；质量属性拒绝时补可用替代工具提示 | P02/P04 镜像特征可复现且体积不变；装配查询给出明确替代路径，不改 revision |
| G05 / F01 5.3、5.6，P2 | compact capabilities 只有操作名，`creo_execute_plan` 顶层 `operations` 仍靠试错；`creo_get_job.wait_seconds` 上限 30，长作业需多次轮询 | 提供 6—8 个常用 op 的最小示例或分页 `plan_examples`；提高长轮询上限或提供一次性等待 | 示例可直接提交成功；32 KiB 分页预算不破；P01/P04/总装单次等待可覆盖实测耗时 |
| G06 / F01 5.4，P2 | `session_health.py:559-565` 在 identity 记录过期时仍返回 `unknown/session_identity_stale`，即使 `connected=true`、`toolkit_code=0`、`verified_at` 很新 | **先定安全策略**：是否允许把新鲜连接证据作为 health 优先证据，或把 identity stale 降为 warning；不得擅自清 unknown 保护 | 决策写入工作卡；构造 connected 新鲜 / identity 过期 / 有损坏记录三类样本，状态与 caveats 一致；不因文案变更放宽故障注入或清锁权限 |
| G07 / F03 P0-1、P0-2，P0 | `quilt_merge` 仍全局门禁，文案已注明 Creo 10 外部正证据但不放行；8 片一次合并失败；两两合并后工具 quilt 残留、surface id 重复、`closed` 判定自相矛盾 | 先按 release 分别实机验收（Creo 10 两片共享边 → 面积叠加 → thicken 体积 → reload；Creo 12.4 反例保留），再决定 release-aware 门禁或 `allow_unverified_release`；实现 `consumed_quilt_ids` / `merged_surface_ids` / `result_quilt_id` / `boundary_loop_report`，并在 `inspect_model(quilts)` 过滤被消费 quilt | 门禁文案带 `creo_release_numeric` 与受测几何；8 片 → 1 个 quilt、`closed=true`、面积等于各片减重叠；无重复 surface id；thicken/solidify 一次成功并保存重载 |
| G08 / F01 5.7、F03 P2-2、F04 P1-2，P2 | 无 `known_limitations` 汇总段；`unavailable_operations` 的诚实做法尚未推广到有条件限制（A-2/A-3/B/装配 parts-only/tail 截断等）；0.18.2 之前的反馈登记已补，但 0.18.3/0.18.4 的契约变更未汇总 | 在 capabilities 新增结构化 `known_limitations`（条目、条件、release、证据来源、是否可配），并把已登记限制逐条迁入；各版本 MAPPING 与本批格式对齐 | compact/full 均可读到且分页预算不破；文案与回执逐字段一致；不把「实测不可用」写成「全平台不可用」 |
| G09 / F03 §5 表 1—11、F04 P1-2，P0/P1 | 已有两截面 `surface_loft`（Probbl.h 条件）、组级 gap/闭合测量与保留侧判据，但缺 `boundary_blend` / G1 桥接、`surface_fill` 3D 边界围成、独立 `quilt_offset`（0.3 壁厚）、`quilt_round`（R1/R2）、斑马纹/曲率梳质量分析、近切预检与方案 B 一步式 | 按 MVR 顺序 1（放样）→2（合并）→3（闭合/公差）→4（保留侧）先打通「放样爪面 → 有效修剪 → 全部缝合成闭合组 → 实体化」，再做品质收尾；每项必须原生几何证据 | 任务书 8 步逐条达成：50° 双截面放样、5 爪 72°、爪外侧修剪、G1 爪谷、中心开口沿边界补面、缝合成 1 个闭合 quilt、solidify 一次成功、任意截面壁厚 0.3；预览与曲率分析可核对 |
| G10 / F01 5.5，P2 | `creo_loft` 仍要求手工注册 Blend callback（`capabilities.py:668`） | 提供不依赖 callback 的两截面直纹退化实现，或自动检测 + 引导式注册 | 未注册 callback 时锥台/放样可用或给出可执行注册指引；P05 锥台体积偏差 ≤0.01 % |
| G11 / 全批，P0 | 本批及既有离线修复都没有 Creo 9/10 实机或 WorkBuddy 黑盒证据：显式密度 `material_assigned=true / mass_query_code=-1` 路径、装配守卫、stall 回退、`skipped_no_geometry`、`surface_loft`、保留侧判据、`preview.path` | 先按 BUG-001 恢复记录确认会话可操作并获授权；重编译并重启 `MCP_CREO_MechDog_dev`，只用公开 MCP 观察；WorkBuddy 不读取源码/配置、不跑本地脚本 | 记录版本、工具清单、job/model/revision、原始回执、保存重载与回滚；显式密度路径 `density_source=request` 且 reason=null；失败作业 compact 的 `native_progress` 含 connect/connected 计时且 `timing_source=verify_stages`；不把编译或单测当实机通过 |
| G12 / F02、DEV-076 余项，P1 | POSTCHECK 的 v0.18.3/0.18.4 段只有本地标签与外部资料转录；v0.18.2 的四附件数据来自报告方转录，本轮未重下重算 | 联网后按精确 tag 执行 `tools/check_release_assets.py --tag <tag> --version <版本>`，记录查询时间（UTC 与 +08:00）、tag 提交、Release 状态/body、四附件名/大小/API digest、下载后本地实算 SHA256、sidecar 与正文比对 | 每版四附件齐全、两个 sidecar 与对应 ZIP 摘要一致、exit 0；结果写入 POSTCHECK 并消除占位；不移动已发布 tag、不覆盖同名附件 |
| G13 / 交付流程，全局 | 本分支未合 main、未发布；`version.py` 仍 0.18.4 | 将来合入 main 时选未发布的新版本，同步版本入口/说明/逐 ID 表/种子记录，用 `tools/package_seeds.py` 与 `tools/package.py` 生成四附件，逐个列出文件名上传，发布后跑 `--tag` 核对并回填 POSTCHECK | 四附件齐全且两份 sidecar 与 ZIP 摘要一致；`tools/check_backlog_counts.py` exit 0；合规记录完整 |

## 接手约束

- 本机只启用 `MCP_CREO_MechDog_dev` 并指向 `E:\Projects\MCP_CREO_MechDog`；执行前核 BUG-001 恢复记录与会话可操作性，不擅自连接/结束 Creo、清 unknown 或做故障注入。
- 历史 `docs/validation/` 原件与已发布 `RELEASE-*.md` 保持字节不变；新证据用新记录与勘误链接，不回写旧 tag/附件。
- 报告中的 Creo 9（`release_numeric=41`）与 Creo 10（`42`）结论不能外推到作者 Creo 12.4 基线，也不能反向外推；F03 的「8 片一次合并失败根因」只是几何推断，原生回执只有 `feature_status=6`。
- 先 `git status/diff` 区分本批改动与用户原有的 DEV-054/DEV-066/`.trae/`/FEAT-014 计划未提交内容；测试证据注明实际组合源码与 dirty 状态。
