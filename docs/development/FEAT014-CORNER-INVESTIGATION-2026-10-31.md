# FEAT-014 四壁/端部 trim/材料端 relief 离线证据核对（P09 第一阶段）

日期：2026-10-31（Asia/Shanghai）。范围：总计划 [P09 第 1 条](../superpowers/plans/2026-10-31-post0100-master-plan.md)（仅离线证据核对与候选设计；原生对照试验即第 2 条起需实机与受限诊断设计审阅，本轮不做）。分支 `codex/dev053-post0100`，基线提交 `50b34a1`（P07）；本轮**未改任何源码、未跑 build、未连接 Creo、未提交 Toolkit 作业**。不修改 FEAT-014.md、BUG-032.md（P08 窗口正拥有）与 docs/validation/ 历史原件；RELEASE-0.8.5.md 与 session_activity.json 不纳入提交。

输入：FEAT-014 卡（只读）、[T05 验收卡](DEV051-T05-ACCEPTANCE.md)、[T11 验收卡](DEV051-T11-ACCEPTANCE.md)、[N05 实机记录](DEV052-N05-LIVE-2026-10-30.md)、[七段实机总报告](POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)、[RELEASE-0.10.0.md](../validation/RELEASE-0.10.0.md)、[MAPPING.md F4 §4-2/3、F5 §5/6 行](../validation/feedback-0.9.0-2026-10-31/MAPPING.md)（"换底板后四壁希望大"属假说；0.10.0 已证实 `adjacent_bend_ends` 边界）、`build/` 下原始报告（本机生成物，未入库，路径逐一经 `Test-Path` 核实存在）。

按 MAPPING 口径，四个现象分别对应：F4/F5 的四壁路线（现象 2）、`end_trim_mm` 行为（现象 1）、relief 元素与几何（现象 3/4）。以下逐现象给出可复现证据；缺失的证据明确标"缺证"，不用假说补。

## 一、四个现象的证据核对

### 现象 1：`trim_ignored`（`end_trim_mm` 无可观测几何效果）

**状态：已证实（三轮独立实机一致）。**

| # | 时间 | 报告（均已核实存在） | 观测 |
| --- | --- | --- | --- |
| 1 | 2026-10-30 N05 首跑 | `build/post090_n05_live_20261030T233639/report.json`（run `20261030T233639_cb833e2b`） | 同一 +x 自由首壁，无 trim 与 `end_trim_mm=20`（各一 fresh 模型）增量同为 18025.291234051932 mm³，分类 `trim_ignored` |
| 2 | 2026-10-31 N05 重启后重跑 | `build/post090_n05_live_20261031T114634_restart/report.json`（run `20261031T114635_d85e4c3e`，SHA256 `F39DBCC1…7346F`） | 复测同判 `trim_ignored`，两组均 succeeded、重载 true |
| 3 | 2026-10-31 N06 终验 | `build/post090_n06_live_20261031T142644/report.json`（SHA256 `5fd12b29…fe768`） | `trim_probe` 仍 `trim_ignored`；`setback_confirmed=false`（实测 `four_walls_complete=false`、`setback_confirmed=false` 已在本轮直接抽取核对）；候选分类 `setback_from_ends`=14917.48、`length_from_section`=1553.90、`length_both_sides`=3107.81 均不匹配实测增量 |

结论：trim 写入路径已接通（`advanced.cpp` DEPTH `TO_END`→`BLIND`+offset，缺省树逐字节不变的静态守卫在），但 Creo 对该偏移**无任何几何响应**。语义四候选（setback_from_ends / length_from_section / length_both_sides / trim_ignored）三轮实测均落 `trim_ignored`。**缺证**：创建特征树内 `PRO_E_SMT_FLANGE_DEPTH_OFFSET` 的实际保留值从未被回读（现有回读只覆盖 relief 段，见现象 3），因此"Creo 丢弃该元素"与"元素保留但被深度类型压制"不可区分。

### 现象 2：邻接端（`adjacent_bend_ends`）拒绝

**状态：已证实且实机生效（N06 终验 RUN PASSED）。**

- 触发条件复现链（创建后未再生形态，预检之前的历史证据）：第六轮 `f_ny`（job `1a2b487ce90b486fb358494ba6afcc22`，rev 3→3 回滚）→ N05 重启后重跑两例真实板顶边（`build/post090_n05_live_20261031T114634_restart/report.json`：`px_then_ny` 的 `f_ny` job `36defb2ad3ca400abd7b65f5ef839cc7`、`px_nx_then_ny` 的 `f_ny` job `1e8f8ed96f6e4719874393a9f56f82d0`，均 `trigger_reproduced`、`FLANGE_FAILURE_EVIDENCE stage=after_regenerate feature_status=6 geometry_item_count=0`）。
- 创建前拒绝实机生效（N06 终验，同报告 SHA256 `5fd12b29…fe768`）：`px_then_ny` 的 `f_ny` job `f706af6a78f1483c9a6ce20586605c15` fast-fail `adjacent_bend_ends_rejected`，`stage="before_create"`，附着边 197（181.46 mm，end1 命中：邻接弧边 201、R2.54、折弯面 [193]、界限 7.081 mm）；`px_nx_then_ny` 的 `f_ny` job `94ea4ea25c5b42e3887aafe9688e41aa` 两端均命中（298/[292]、201/[193]）。两次 revision 均不变（2→2、3→3）、回滚成功。自由壁负对照 `ny_first`（job `40aae64263a24e65b9e3d360bf435360`，42920.0→57293.61585482106 mm³、重载 true）证明拒绝不误伤自由边。
- 迭代史：预检两轮修复（`ProEdgeNeighborsGet` 轮廓邻边不分端 → `ProEdgeVertexdataGet` 按端扇区 `582c1a3`；summary 空值崩溃 → 判空 `b5dce10`），此前 `…T134730`、`…T142121` 两轮（报告存在，已核实）仍 `trigger_reproduced`，`142644` 才首次拿到 `adjacent_bend_ends_rejected`。
- **未定部分**：触发机理的内部二分（截面越界 vs 相邻料重叠）仍不可区分——这正是 P09 第 2 条原生对照试验要回答的问题；当前证据只支持"端部邻接折弯 ⇒ 再生失败"，不支持任何具体角部机理结论。

### 现象 3：释放（relief）元素保留

**状态：自由端已证实（元素树回读一致）；材料端缺证。**

- 元素树回读机制（2026-10-30 离线交付）：创建+再生成功后 `ProFeatureElemtreeExtract` 回读创建特征树的 `TYPE/WIDTH/DEPTH_TYPE/DEPTH`，与请求逐项核对，不一致即失败回滚；`LENGTH_TYPE/LENGTH/ANGLE` 只记录不断言。
- 实机证实（N01 relief 第二轮，`build/post090_live2_20261031T115830/n01relief/run1/report.json`，SHA256 `cefce8ed…643a`，run `20261031T133009_e33744d9`）：`free_rect_both_4x4`（model `b6845c6048cf49ce9aeb7e27554d294e`，`f_px` job `71ef2f4526324dbfbcb86bf31f3e2361`）succeeded、rev 1→2、+18025.291234051932 mm³、重载 true，`relief_echo` 与 `relief_element_echo` 齐全（side1/side2 宽深各 4.0 mm、blind、`length_type=-31`、`type=3`）。这证明**写入值留在创建出的特征里**（对照第六轮之前"只看请求回显"的空过形态，判读纪律见第六节）。
- 自由端差分 0 属预期：`profile_comparison` 中 `f_px`/`f_nx` 的 `measured_delta_mm3=0.0`、`notch_faces_with_relief=0`，自由板角不切缺口。诊断性 4×4 探针 job `6ddadf6487644504a1ebdfd6ef8bd7f4`（`build/relief_probe/w4_d4/20261029T223039_44c271f2/report.json`，已核实存在）同样差 0，排除"1×1 太小被忽略"。
- **缺证**：材料端（含单端 `side1`/`side2` 映射）的元素保留从未取得——`mat_baseline` 与 `mat_rect_both_1x1/both_4x4/side1_1x1/side2_1x1` 五案目标 `f_ny` 全部被 T05 边界挡住（`known_t05_boundary`），`measured_delta_vs_baseline_mm3=null`。`LENGTH_TYPE/LENGTH/ANGLE` 的生效默认值同样只有自由端读数（`length_type=-31`），无材料端对照。

### 现象 4：真实去料几何（trim 或 relief 的实际材料切除）

**状态：缺证。**

- trim 侧：`trim_ignored` 意味着连去料都没有，无几何可核。
- relief 侧：材料端缺口的位置、尺寸（宽×深×板厚）、缺口面数、体积差（−1/−16 mm³ 期望）在所有实机轮次中均不可观测——需要材料端的合法建壁场景，而该场景被现象 2 的边界挡住（有/无释放失败方式相同：第六轮 job `2bc5bf3184d94d08b472a0cd179c242e` 与 none 档同失败）。
- 关联缺陷背景：`relief` 回显里的 `part_thickness_mm=3.71`（1 mm 板读到零件级默认板厚）已登记 BUG-032；N01 第二轮材料矩阵五案 `wall_contract.part_thickness_mm=1.0`（`part_thickness_synced=true`）后该口径已恢复可信，但任何"宽 ≥ 板厚"规则仍须在当前读数下重验。

## 二、证据完备度表

| 现象 | 复现证据 | 反例/负对照 | 定量 oracle | 机理区分 | 完备度 |
| --- | --- | --- | --- | --- | --- |
| 1 trim_ignored | 3 轮独立实机（10/30、10/31×2） | 无 trim 基线各轮齐备 | 实测增量 vs 四候选分类齐备 | 缺：创建树内 depth offset 回读 | 高（现象层面）/ 缺输入（语义层面） |
| 2 邻接端拒绝 | 触发复现 2 例 + 创建前拒绝 2 例（同轮） | 自由壁 `ny_first` 负对照 | 边长/端点/邻接弧/半径/界限/折弯面全录 | 缺：截面越界 vs 料重叠二分（属第 2 条试验） | 高（边界层面） |
| 3 relief 元素保留 | 自由端 4×4 一例（元素树回读一致） | 无释放对照齐备 | `relief_element_echo` 逐项一致 | 材料端五案全缺证 | 自由端高 / 材料端缺证 |
| 4 真实去料几何 | 无（材料端场景全部被边界挡住） | — | −1/−16 mm³ 期望从未实测 | 无 | **缺证** |

## 三、候选设计：最小 native 对照矩阵草案（不承诺四壁成功）

沿用 P09 卡给定的因子：自由端 vs 材料端、relief none/1×1/4×4/单端、full_length/trimmed_20、NY first/second；固定 185×232×1 底板（`plane="XZ"`、`sheetmetal_wall(depth=232, thickness=1)`）、h80/R2.54/Y0.5、每 fresh 模型逐道一 job、每道从最新 inspect 按几何选边（显式 `face`、排除 rim 边、允许缩短边有界），每次只改一个因素。

**层级划分（关键）：矩阵必须按"是否触及当前保护拒绝的形状"分两层，先跑 A 层再谈 B 层。**

### A 层：不触及 `adjacent_bend_ends` 保护的试验（当前实现即可跑）

| 组 | 顺序 | relief | trim | 回答什么 |
| --- | --- | --- | --- | --- |
| A1 `ny_first` | f_ny → f_px | none | full_length | 自由边基线（N06 已过，作回归锚） |
| A2 `order_ny_second` | f_px → f_ny | none | full_length | 单材料端：被保护拒绝（复现确认，非目标） |
| A3 trim 读数组 | f_px（自由）×{无, 5, 20, 40} | none | 各档 | trim 剂量响应：全零则确认 ignore 与剂量无关 |
| A4 relief 自由端扩展 | f_px ×{1×1, 4×4, side1, side2} | 各档 | full_length | 单端映射与 LENGTH 三元素读数（自由端安全场景） |

A 层缺口：A3/A4 均为自由端，不能回答材料端去料——这由 B 层回答。

### B 层：触及被保护形状（须先审阅受限诊断设计，本轮不执行）

目标场景：`f_px → f_ny`（第二道、1 个材料端）在**预检豁免或按例放行**下提交，观测 relief 材料端去料与失败/成功形态。候选放行方式（设计决策，非实施）：

1. **受限诊断开关**（建议形态）：原生加一个仅由配置/请求显式开启的 `allow_adjacent_bend_ends_probe` 诊断通道，默认关闭、只影响该开关命中的请求、失败路径取证全开（现有 `flange_failure_evidence` 复用）；**不改动默认拒绝语义**，不开全局旁路。
2. **按提交逐例放行**：请求带显式 `diagnostic_override` 字段，schema 校验 + 单元锁定默认拒绝不变。

B 层必须等：① 受限诊断设计（含开关字段落点、兼容影响、回滚）单独审阅登记；② 会话满足 BUG-001/BUG-091 准入。**不得全局移除邻接保护后盲跑长队列，不靠反复失败寻参。**

### oracle 必须核对什么

- **trim 端点实际后退距离**：不能凭参数回显或"无 trim 增量差为 0"判通过。若 B 层或 trim 读数组出现非零差，须核对：实测增量 vs 退距模型（两端各 `end_trim_mm` 的 span×h×t 修正）、修剪壁 bbox/附着边端点、以及**创建树回读的 `DEPTH_TYPE`/`DEPTH_OFFSET` 实际保留值**（需为 trim 段补回读，复用 relief 回读机制）。
- **材料端释放实体切除位置/体积**：缺口位置在材料链端（`f_ny` +x 端与 `f_px` 折弯相接处）、尺寸 = 宽×深×实测板厚（1.0，非 3.71）、体积差对 none 基线 = −w×d×t（1×1→−1、4×4→−16，±0.2）；**期望差值在用之前须按几何独立重推导并双向验证**（沿用 18025.291233 体积模型锚定实测 18025.291234 的做法），不得直接抄卡面算术。单端对：`side1`/`side2` 恰好一端去料、另一端 0，由此锁定映射。
- **不穿透邻壁**：缺口不得切进 `f_px` 折弯区/邻壁——用 bbox、COG、缺口面三向包围盒（≤1.5 mm 口径沿用第六轮）与体积模型（含角部重叠项）共同判定；仅体积差 0/非 0 不构成判据。
- **判读纪律（防"空过"）**：请求回显/`relief_echo` 齐全不构成释放证据（第六轮形态）；材料端差 0 = 未生效（失败），自由端差 0 = 预期对照，两者不得混用；任何量测缺失记 unknown，不判通过。
- **通过门槛**：某种策略只有在"建成 + 几何 oracle 过 + 可编辑 + 展开/折回 + 保存重载 + 失败回滚"闭环后才谈支持；`four_walls_complete` 在一切分支保持 false，直到第三、四壁真实建成并全链路通过。

### 停止规则与会话条件

- 会话：`auto_start_creo=false`、唯一 dev 服务 `MCP_CREO_MechDog_dev`、先按 BUG-001/BUG-091 确认 GUI 可操作、无 unknown 保护残留；不启动/结束/重启 Creo，不重提已受理 job。
- 停止：180 s 未终态、首个 busy/unknown、通道死亡即停止该轮新提交并保留现场（`LiveStop` 约定沿用）；失败墙保留 job 与原始码，不重提、不续跑后续道。
- 矩阵复盘：每完成一个独立试验矩阵即复盘是否继续；失败/异常停止，不把调查扩展为全项目阻断。

## 四、四选一定性（每现象一票）

| 现象 | 结论 | 理由 |
| --- | --- | --- |
| 1 trim_ignored | **缺输入** | 现象已三轮证实且稳定（不能用于角部让位）；但语义未定缺一份输入：创建树内 depth offset 回读。若回读显示元素被丢弃/被压制，则转"需设计"（换深度表达或放弃 trim 路线）；在此之前 trim 路线冻结 |
| 2 邻接端拒绝 | **可继续** | 边界已实机生效、证据闭环（触发复现 + 创建前拒绝 + 自由壁负对照）；继续方向是 B 层受限诊断试验回答机理二分，属设计决策而非能力缺陷 |
| 3 relief 元素保留 | **可继续** | 自由端元素树回读一致已实机证实（`relief_element_echo` 机制有效）；单端映射与 LENGTH 默认值可先在 A 层自由端补齐 |
| 4 真实去料几何 | **缺输入** | 材料端场景被现象 2 边界挡住，从未取得可观测几何；必须等 B 层受限诊断设计审阅 + 实机窗口。若 B 层试验后仍不可行或不可观测，则本现象落"保持不支持" |
| （边界项）四壁整体 / corner relief / miter | **保持不支持** | 3/4 是上限且第 3 墙被明确拒绝；角部释放/斜接未实现；只有第三/四壁真实建成并全链路通过才改口 |

必须等实机的：现象 1 的语义回读、现象 4 的材料端去料观测、B 层全部组。属设计决策的：B 层受限诊断开关的形态与字段落点、trim 路线是否放弃、A 层补充组（A3/A4）的取舍。

## 五、给 P08 与 P14 的交接要点

**给 P08（钣金帧/选边窗口，正拥有 FEAT-014.md/BUG-032.md/native/advanced.cpp、generic.cpp、sheetmetal.py、server.py 钣金描述）：**

1. 候选边发现契约（`wall_contour_status=eligible|ineligible|unknown`）应把"邻接端"表达为独立的 ineligible 原因（可引用 `failure_reason=adjacent_bend_ends` 与 `flange_failure_evidence` 的边/端点/弧证据字段），不要与"查询失败 unknown"或"最终不可创建"混并；候选边通过**不解除** `adjacent_bend_ends` 创建前拒绝。
2. 选边实现可直接复用 N05 修复约定：相对基线板 bbox（非折边后整件 bbox）分类 top/bottom、排除 span ≤ 2×板厚的 rim 边、`allow_shortened` 下限 2×(R+t)——1 mm rim 边误判为缩短边的驱动缺陷已定因，勿回退。
3. `end_trim_mm` 三轮实测 `trim_ignored`：P08 的工具描述/能力文档不得把 trim 写成可用参数或角部让位手段；若 P08 改工具描述，保持"语义未定、不可依赖"口径。
4. relief 回读机制（`relief_element_echo`）已实机有效，P08 的 inspection/候选边结构如需引用释放状态，引用该字段而非请求回显。

**给 P14（集成与回归）：**

1. 钣金段回归范围按现状：标准底板契约（XZ/232/1）、自由端折边（bbox Z 增长 ≥72 mm 判折弯，体积相同不算）、`ny_first` 回归、已知邻接拒绝（`adjacent_bend_ends_rejected` 判 passed 且 `failed_walls` 如实列出、`four_walls_complete=false`）；`trim_probe` 仅在 trim 实现变化后重跑，否则沿用 `trim_ignored` 现状不重测。
2. 报告落唯一 `build/post0100_<runid>/` 新路径，保留 job/model/revision/几何/重载/回滚与原始错误；本轮核对过的 `build/` 报告均为本机生成物不入库，引用时以路径 + 报告内 SHA256 字段为准。
3. 若 P09 第 2 条 B 层试验在 P14 之前获得编排排期：P14 须先核受限诊断设计已单独审阅登记、会话满足 BUG-001/091 准入、执行器 `build/source.sha256` 与受测提交一致，再把矩阵结果纳入汇总；未满足则钣金段仍按现状边界收口，不冒进。
4. 本文档结论仅在源码身份 `50b34a1`（`codex/dev053-post0100`）下有效；后续 native 变更不影响已录历史证据，但会重置"当前实现"口径，引用时注明时点。

## 六、本轮实际修改与验证范围

新增仅本文档 `docs/development/FEAT014-CORNER-INVESTIGATION-2026-10-31.md`。未修改：FEAT-014.md、BUG-032.md、任何源码/测试、docs/validation/ 原件；未跑 build、未运行单元测试（无代码改动）、未连接 Creo。证据核对方式：读取上述验收卡与发布记录、对列出的 8 个 build 报告路径逐一 `Test-Path` 核实存在、对 N06 报告直接抽取 `four_walls_complete=false`/`setback_confirmed=false` 字段复核；未重新解析全部原始 JSON 的逐字段内容，字段值以各验收卡记录为准。
