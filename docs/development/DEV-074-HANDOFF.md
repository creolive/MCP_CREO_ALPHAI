# DEV-074：0.17.4 反馈离线结果与接手清单

日期：2026-11-07。工作分支：`codex/DEV-074-feedback0174-offline`，起点 `8d71e6c` / 0.18.0。用户要求先对照现有实现、先离线完成、把余项交另一个 AI。工作卡：[DEV-074](../work-items/DEV-074.md)；四份原件与完整逐章对照：[MAPPING](../validation/feedback-0.17.4-2026-11-07/MAPPING.md)。

## 已有内容与本次增量

开始前已存在 DEV-071/072 的 miter 公开投影、更新 force/预算、板厚来源、最近五条边文本诊断、空模型预览 skip、API 精确 tag 下载备用路线及台账修正；四份报告补有 Creo 10 的外部正证据，本轮未重复实现。

本轮离线补齐：无 Git 来源降级、日志头尾阶段归因、失败 ID 与 loaded 回执、有效板厚判据、空预览路径/字节/判定依据、过期 startup 提示、更新检查在途字段、曲面能力与门禁文案、附件 API 二级备用路线、发布勘误与统计口径。原生 resize 仅补诊断，**功能缺陷仍开放**。

## 验证结果

仓库内 `tools/dev_check.py --work-item DEV-074` 已通过：2850项单测、0失败、0错误，风格24条lint/12个未格式化文件为既有基线，没有新增基线问题；`bridge.py build`退出0。最终源码在无`.git`、PATH无Git的独立分发目录全量2850项、0失败/0错误、2项SDK检查跳过；464个源码文件与工作树一致。完整来源、命令与审查限制见[验收记录](DEV-074-ACCEPTANCE.md)。上述轮次没有连接 Creo；所有新原生字段、非零原点 resize、真实附件下载、WorkBuddy、Creo 9/10/12 新实机结果均不能记为通过。

后续增量（2026-11-07，H01 实机）：非零原点跨轴 resize 已在 Creo 12.4.0.0 实机定性并修复（14 例矩阵通过，驱动 `tools/test_planar_wall_origin_resize.py`），证据 [FEAT-058-H01-2026-11-07](../validation/FEAT-058-H01-2026-11-07/SUMMARY.md)；本页其余离线结论不受影响。

## 未完成清单（接手顺序）

| 编号 / 条目 | 未完成内容与当前文件 | 下一动作与验收 |
| --- | --- | --- |
| H01 / FEAT-058，P1 | **已修复（Creo 12.4.0.0 实机 14 例通过）**。根因实测：5 个坐标尺寸是到截面轴的距离，方向属于尺寸本身；`coord_wall_1_end_y` 的目标角点必须跨到截面轴另一侧，`fabs()` 写法只能留在原侧，解出 v 跨距 172、体积 17200 被回滚。`native/planar_wall.cpp` 现在用 `ProSecdimReferencesGet` 实测每个尺寸方向后写有符号值（负值即翻侧），读回比较绝对值，并新增定位矩阵/角点/尺寸引用/包络诊断；守卫、feature ID、origin、厚度与 `origin=[0,0]` 路径不变。矩阵覆盖零/正/负/混合 origin、跨/不跨轴、恒等/缩小/放大/连续改型、XY/XZ/YZ、正负厚度方向、同计划、跨计划与 save/reload 后 resize，均 6000/42920 等预期值且保存重载 true。证据：[SUMMARY](../validation/FEAT-058-H01-2026-11-07/SUMMARY.md)。未验证：字面会话擦除后重载（工具约束）、Creo 9/10 实机、`test_adoption_planar_wall.py --live` 77 项因其它客户端占用通道未跑完。 | 后续：有健康会话时补 Creo 10/9 实机与完整 77 项回归；若需要字面 erase/reload，先扩展受管模型的擦除路线，不要删除现有体积/包络/子特征守卫。 |
| H02 / FEAT-009，主线阻塞 | **已交付（Creo 12.4.0.0 实机 2026-11-07）**。路线 A 成立：按契约 §2.1 的 `Probbl.h` 裸树用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 创建 → `ProFeatureElemtreeExtract` → `ProFeatureWithoptionsRedefine`；内核自行补齐 `PRO_E_EXT_SURF_CUT_SOLID_TYPE` 与 `PRO_E_BNBLN_TAN_COND` 默认值，说明旧 P1 失败源于创建前手写这些值（status 6），不是元素被拒。新增 `surface_loft` / `creo_surface_loft`：恰好 2 条单曲线草图截面、straight、开放 datum-surface quilt、不产实体；`creo_loft` 仍只建实体。实机：quilt_id 61、面积 800.0 mm²、`quilt_closed_native=open`、`has_solid=false`、保存重载 id/面积不变；x=20 trim 两侧各 400.0 mm²；2 mm thicken 1599.9999999999995 mm³。证据 [FEAT-009-H02-2026-11-07](../validation/FEAT-009-H02-2026-11-07/SUMMARY.md)，契约 §2.1/§2.8/§3.1/§9.4 已回填。未验证：≥3 截面、smooth、闭合、连续性、非平行/扭转/圆弧截面、Creo 9/10；先 thicken 后 trim 同模型返回 -1，验收顺序已改为 trim 在前或用独立模型。 | 后续：多截面/G1 由 FEAT-039/055 另外立最小契约；不要在创建前写切线条件或放宽门禁；Creo 10 实机按用户规则非阻塞。
| H03 / FEAT-039，主线阻塞 | `quilt_merge` 保持门禁，既有树无可用结果 quilt，不能逐片缝合封闭。 | 原生 join/intersect 两片→链式，测 result_quilt_id、面积、闭合、失败回滚；修复前不解除 unavailable，不声称最终瓶底可实体化。 |
| H04 / FEAT-039/055 | **已交付（Creo 12.4.0.0 实机 2026-11-07）**。新增 `native/surface_group.cpp` 与只读 `surface_group_measure` / `creo_measure_surface_group`：`open_edges`、`gap_max_mm`（`tolerance_mm` 默认 0.01、`gap_search_mm` 默认 1）、`overlap_area_mm2` 与四态 `state`（closed/open/micro_gap/overlap），每值带 `*_status`；依据 `ProContourEdgeVisit`/`ProEdgeTessellationGet`/`ProEdgeLengthEval` 与面网格 + `ProSurfaceParamEval`/`ProSurfaceXyzdataEval`/`ProSurfaceUvpntVerify`，不用面积或体积反推。`surface_loft` 回执同时携带 `surface_group`。实机四例（run `20261107-132056-710000`，42 检查通过）：共边 `closed`/gap 0、0.005 mm `micro_gap`/gap 0.005、0.5 mm `open`/gap 0.5、0.5 mm 重叠 `overlap`（`buried_boundary_edges=2`，面积 0 标 `area_below_sample_resolution`）。证据 [EVIDENCE](../validation/feat039-h04-surface-group-2026-11-07/EVIDENCE.md)。 | 后续：补 Creo 9/10、非 mm、多面/曲面成员与真正闭合壳体组（`open_edges=0`）；重叠面积是采样估计，需要精确交集时另立布尔/求交路线；`quilt_merge`（H03）仍 gated，组级测量只对独立 quilt 集合取证；autodim 会把草图量化到 0.01 mm，微小缝隙用例须用 `dimensioning="coordinates"`。 |
| H05 / FEAT-014 | 钣金附着增料、百叶/格栅/凸台/铰链/耳、连续多边与 corner relief 尚缺原生能力/验收。`src/creo_mechdog/sheetmetal.py`、`native/advanced.cpp`。 | 先核查已有 FEAT-014 计划和用户未提交计划，避免重写。Creo 10 增料未实际尝试，12.4已有失败；不得直接开放 opt-in 或宣称 new_body+union 可用。分项定义树、材料连续性、板厚、角部实际去料量、展开回折与重载矩阵。 |
| H06 / FEAT-039 | trim 特征标签下游引用 visit -4 **未修**；保留侧 centroid/bbox/世界方向已于 2026-11-07 实机补齐。 | 已交付：`surface_measure.h::quilt_region_geometry`（面片面积加权质心/bbox/法向）+ `surface_trim` 新字段与 `*_status`；基准面/quilt 工具 × one/two 四组形心分居工具两侧（±17.5/−2.5 mm）、保存重载 true、失败用例回滚且 revision 1→1。证据见 [EVIDENCE](../validation/feat039-h06-kept-side-2026-11-07/EVIDENCE.md)。仍待：trim 特征标签下游引用 `-4` 修复、跨计划标签复用、非平面/非 mm/多面 quilt 实机矩阵、Creo 9/10。 |
| H07 / FEAT-039 | 独立 quilt offset、弯曲源实测偏置距离/0.3壁厚未实现。现有 surface_offset 是偏置壁。 | 分开设计 offset wall 与 quilt offset；测真实结果quilt及曲面距离，mm/in/混合/未知单位矩阵；未知保持null，不能用体积/面积估算冒充局部厚度。 |
| H08 / FEAT-055 | 曲面边圆角、曲率梳/斑马纹、跨边G1偏差尚无接口。 | 各自登记最小契约，取得曲面边选择/几何结果或分析图、方向/曲率数值及保存重载证据。实体 round 不等于曲面 fillet。 |
| H09 / FEAT-039 | 任意非平面 fill 未支持。 | 先交付明确替代：旋转球面用于中心R8场景；任意闭合边界的非平面填充需新原生路线，单独验收，不放宽现有 planar fill。 |
| H10 / FEAT-039 | 多quilt实体化/加厚、开口面与0.3壁厚整链验收未完成。 | H02/H03/H04完成后再跑完整五爪任务；验证闭合、无缝/重叠、质量/厚度、开口面、保存重载与后续编辑。 |
| H11 / DEV-072/074 | 0.17.4与当前版本的真实远端 tag/main/Release/四附件/body 后核对尚未独立实施；新 API asset-ID 路线仅离线mock。 | 有网络时执行 `tools/check_release_assets.py --tag v0.17.4 --version 0.17.4`，记录Asia/Shanghai查询时间、提交、大小、API digest、本地SHA256与sidecar/body；写新POSTCHECK文件，保留旧validation/tag/附件字节。本轮[勘误](DEV-074-RELEASE-ERRATA.md)区分报告方实测与本机未查。 |
| H12 / BUG-115、BUG-109、DEV-074 | BUG-115原生根因和Creo10精确失败形态未知；新诊断/回执/预览依据尚无本轮MCP实机、保存重载与新WorkBuddy证据。 | 先确认健康会话，重编译后用MCP复验新字段及原始失败样本；默认保护保持。若按release收窄或新增opt-out，先补原生证据及独立设计。真实断流/原生并发/保存失败不得以单元mock记通过。 |
| H13 / DEV-066及历史反馈 | 2026-11-07 第二轮已把剩余 17 个仍自行调用 `git rev-parse/ls-files/status` 的证据/驱动函数迁到 `source_provenance.local_provenance`：`test_update_check.provenance`、`test_toolkit_recovery.provenance`、`test_toolkit_channel.provenance`、`test_startup_retry.provenance`、`test_sketch_shift_batch._environment`、`test_geometry_transform_copies._identity`、`test_sketch_geometry_deviation.provenance`、`test_native_countersink.provenance`、`test_sheetmetal_box_live.local_provenance`、`test_g5_native_probe.local_provenance`、`test_first_wall_origin.source_identity`、`test_failed_model_cleanup.local_provenance`、`test_assembly_bundle.provenance`、`test_assembly_ack_failure._identity`、`test_adoption_product_rules.git_identity`、`test_adoption_planar_wall.source_identity`、`dev_check.git_state`（连带 `guarded_live_run`、`test_editing_closeout`）。所有报告保留原字段，仅新增 `git_status`；缺 Git/非仓库时 commit/branch/dirty 为 null。`docs/validation/bug-001-repro-2026-10-16/g0_driver.py` 是不可改历史原件，不迁移。负例日志降噪仅处理已登记的种子摘要负例：`tests/unit/test_seed_record_gate.py` 的 CLI 负例改用 `redirect_stdout` 捕获并断言错误文本仍存在，不再向全量测试打印红字；未改无关日志。缺失的旧反馈原稿与原始失败现场仍开放。 | 本轮已完成上述 17 处并新增 `tests/unit/test_source_provenance_drivers.py`（Git 缺失/非仓库/正常仓库三态 + 全部迁移入口降级）；全量单测与 ruff 结果见 DEV-074 证据节。逐脚本迁移仍不等于 37 个历史工具全部完成；剩余只有不可改历史原件。旧反馈原稿需向原报告方取得后校验归档，不能凭空补造。 |

结构化最近候选边已完成原生失败结果、compact白名单与保护证据链路；仅离线测试/编译，实机失配场景仍由H12接手，不从错误message正则提取“测量值”代替原生结构化证据。

## 接手约束

本机只使用 `MCP_CREO_MechDog_dev`，不擅自连接、结束Creo、清unknown或故障注入。当前服务版本保持0.18.0，本次不合main、不发Release；后续用户授权合main时必须遵守项目同次Release交付规则。开始时用户已有 `docs/work-items/DEV-054.md`、`.trae/`、`docs/superpowers/plans/2026-11-06-feat-014-miter-cuts-route.md` 未提交内容，不属于本批提交。
