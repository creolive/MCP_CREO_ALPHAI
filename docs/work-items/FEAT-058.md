# FEAT-058：原生矩形钣金平面壁及就地改型

类型：功能。优先级：P2。状态：已实现并实机验收，复核 6 项与复核记录 3 处已整改（2026-11-04）；待集成人同步台账与发布。目标版本：未排期。

来源：2026-11-03 用户要求比较 alphai 项目并建立由用户自行派工的计划；静态参考源码不构成当前实机证据。

关联：BUG-032、FEAT-014；本项不关闭四壁/corner relief；产物供 FEAT-060 使用。

## 目标与范围

先核 SDK/做独立原生探针，再新增显式矩形首壁创建/改型；保留 feature 身份，核厚度、有符号包络、体积与恢复；首版拒绝下游依赖；旧 sheetmetal_wall 默认路线保持。

明确边界及拟接口见[设计依据](../superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)。本卡固定身份不能被历史反馈中的同号误写引用替代。

## 派工与验收

- 任务号：A04；负责人：unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-a-foundation-plan.md)；[主计划](../superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)。
- 判据：100×60×1→120×80×1 的体积 6000→9600 mm³、feature_id/厚度保持、方向与长宽真实读回、保存重载 true、拒绝和回滚后继续编辑；不可行探针不得开放写工具。
- 开发环境：Windows x64 / Python 3.12+；原生适用时 Creo 12.4.0.0 / 匹配 SDK/许可，先满足 BUG-001 条件并由会话负责人串行安排。Creo 9/10 未测不能外推。
- 对应专项 unittest、默认离线驱动、构建、实机命令与错误/恢复矩阵见子计划；所有 live 驱动默认离线。WorkBuddy 如安排则只做公开 MCP 黑盒，不替代内部验证。

## 实现与证据

2026-11-03 仅登记和规划；未修改产品代码，未运行产品测试、未连接 Creo、未提交/合入 main/发布。执行者按主计划交接实际提交、dirty、受测源码指纹、命令、环境、结果和未测范围；完成后由集成人同步主台账、能力边界与发布记录。

### 2026-11-04 原生首壁探针（未提交）

分支 `codex/FEAT-058-planar-wall-probe`，基线提交 `88a02dc1`（工作区 dirty：`generic_bridge.py`、`native/advanced.cpp`、`native/generic.cpp`、`src/creo_mechdog/schema.py`、`src/creo_mechdog/capabilities.py`，新增 `tools/probe_planar_wall.py`）。探针算子 `sheetmetal_wall_probe` 仅用于实机判定，不改变 `sheetmetal_wall` 的既有默认路线。

原生依据（本机 SDK 离线文档）：`protoolkit/online_help/creo_toolkit/user_guide/Unattached_Planar_Wall_based_on_the_Fill_Tool.html` 与 `includes/ProFlatSrf.h` 表 4——首壁不是 `PRO_FEAT_WALL`，而是 Fill 特征（`PRO_FEAT_DATUM_SURF` + `PRO_FLAT`）加钣金分支：`PRO_E_IS_UNATTACHED_WALL=PRO_B_TRUE`、`PRO_E_STD_DIRECTION`、`PRO_E_STD_SMT_THICKNESS`（零件已有厚度参数时不可写）、`PRO_E_STD_SMT_SWAP_DRV_SIDE`、`PRO_E_BODY{PRO_E_BODY_USE=PRO_BODY_USE_NEW}`、`PRO_E_SMT_NEW_BODY_LINKED`。

实机结果（Creo 12.4.0.0 / 匹配 SDK，Windows x64，命令 `.\.venv\Scripts\python.exe tools\probe_planar_wall.py --confirm-session-usable [--template solid]`）：

| 用例 | 树 | 零件模板 | job | 结果 |
| --- | --- | --- | --- | --- |
| 首轮失败 | `PRO_FEAT_WALL`+`PRO_SMT_WALL_TYPE_FLAT` | 实体 | `18d7eac1…` | `ProFeatureWithoptionsCreate=-1`，元素错误 0 条 |
| 诊断 | Fill 首壁树 | 实体 | `6f523673…` | 创建返回 0，重生成失败（`model_type=part`，`sheetmetal` body 0 个） |
| 通过 | Fill 首壁树 | `mmns_part_sheetmetal_abs.prt` | `8fdfd659…` | 成功，`model_type=sheetmetal`，feature_id 49，体积 6000 mm³（100×60×1，误差 0），两个 body 均为 sheetmetal，`saved_file_reloaded_and_verified=true` |

结论：`-1` 出在特征树（首壁必须走 Fill+钣金分支），零件子类型仍必须是钣金（同一棵树在实体零件上创建成功但重生成失败），因此原生首壁要求钣金模板起步。

已知限制与未测范围：`ProSmtPartThicknessValueGet` 在该模板状态下创建前后均返回 0，厚度目前只由体积（6000 mm³）间接证明，正式实现需要另找厚度读回/校验路径；`PRO_E_SMT_NEW_BODY_LINKED` 按帮助文档以 INT 写入成功（`ProExtrude.h` 标注为 OPTION 类型）。未验证：120×80 改型（`feature_id`/厚度保持）、指向该壁的下游特征、`sheetmetal_flange` 在原生首壁意义上的可附着性、Creo 9/10 实机，以及 WorkBuddy 黑盒验收。全量单元测试在本机因虚拟环境 editable 安装指向另一 checkout 而出现 35 项导入错误与 4 项失败（`server.py` 源检出保护、seed 包摘要），与本次改动无关；`test_*sheetmetal*.py` 241 项通过。

### 2026-11-04 正式实现与实机验收

探针完成后按同一实测树落地正式算子，探针算子 `sheetmetal_wall_probe` 与 `tools/probe_planar_wall.py` 已退役（结论留在上表），产品面只保留两个公开算子/工具。

实现（本分支工作区，基线 `88a02dc1`）：

- 契约：`src/creo_mechdog/schema.py` 新增 `SheetmetalPlanarWallOp`（label ≤25 字符以便驱动草图 `<label>_sk`、`plane` 仅 XY/XZ/YZ、`length/width/thickness>0`、`direction`）与 `SheetmetalPlanarWallResizeOp`（`feature/length/width`）；`capabilities.py` 登记两个算子并把 sheetmetal 能力块改为原生首壁的实际边界。
- 准入与判定：新增 `src/creo_mechdog/native_planar_wall.py`（空钣金零件、面型校验、改型只接受本算子创建的壁、下游依赖拒绝、尺寸数下限、有符号 frame 包络判定、结果投影），由 `generic_bridge.submit` 在建模前校验、由 job 结果发布 `planar_wall` 判定块。
- 原生：新增 `native/planar_wall.h`、`native/planar_wall.cpp`，`native/generic.cpp` 分发 `sheetmetal_planar_wall`/`resize_sheetmetal_planar_wall`。创建＝坐标全约束矩形草图 + Fill 首壁树（厚度先写零件 `SMT_THICKNESS` 参数，参数不存在时才写元素）；改型＝按当前尺寸比例驱动该草图的点坐标尺寸后重定义草图，壁 feature id/厚度不变；两道都要求重生成后体积＝长×宽×厚、body 报钣金、草图点尺寸 ≥4。
- 工具：`creo_new_sheetmetal` 增加 `template="conversion"|"native_planar"`（默认不变），新增 `creo_sheetmetal_planar_wall`、`creo_resize_sheetmetal_planar_wall`；服务工具数 95→97。
- 驱动：新增 `tools/test_adoption_planar_wall.py`（默认离线 20 项判定；`--live --confirm-session-usable` 走实机全流程）。

实机结果（Creo 12.4.0.0 / 匹配 SDK，Windows x64，`PYTHONPATH=E:\Projects\codex-A04\src`，命令 `.\.venv\Scripts\python.exe tools\test_adoption_planar_wall.py --live --confirm-session-usable`，报告 `build/planar_wall/adoption_live.json`，37 项全部通过）：

| 步骤 | job | 结果 |
| --- | --- | --- |
| 原生模板空模型 | — | `model_type=sheetmetal`，`has_solid=false` |
| 创建 100×60×1 | `8bf77691…` | 体积 6000 mm³（期望 6000，误差 0），feature_id 49，草图 `wall_sk` 5 个点尺寸，包络 u[0,100]/v[0,60]/n[0,1]，`saved_file_reloaded_and_verified=true` |
| 就地改型 120×80 | `7f180b19…` | 体积 9600 mm³（期望 9600），feature_id 仍为 49（`feature_id_unchanged=true`），比例 1.2/1.3333，包络 u[0,120]/v[0,80]/n[0,1]，厚度 9600/(120×80)=1 mm，保存重载 true |
| 方形 60×60×1 | `b18a0e0a…` | 体积 3600 mm³，`square=true`，5 个点尺寸，不因等边降维 |
| 旧契约回归（`examples/sheetmetal_base_yz.json`） | `6ee62f8f…` | 42920 mm³，与示例断言一致，`sheetmetal_wall` 默认路线未变 |
| 拒绝矩阵 | — | 非空钣金零件再建壁、未知标签改型、改型由 `sketch` 创建的标签，均在建 job 前被拒绝并给出可整改文案 |

另以服务工具路径（`creo_new_sheetmetal(template="native_planar")` → `creo_sheetmetal_planar_wall`）复核一次：job `99fbbf33…` 成功、体积 6000 mm³，轮询结果携带 `planar_wall.verified=true`。此路径同时暴露并修复了初版判定块只挂在提交返回上的缺陷。

### 2026-11-04 复核整改（第二笔，关闭复核 6 项）

复核指出 6 项问题，逐条整改如下：

| # | 复核问题 | 整改 | 证据 |
| --- | --- | --- | --- |
| 1 | 内部草图名 `<label>_sk` 未纳入重名/墓碑保护，可覆盖受管别名 | `native_planar_wall.internal_labels/declared_names/name_conflict`；`generic_bridge.submit` 把内部名一并纳入既有别名、墓碑与计划内重复检查；原生在建草图前再查 `alias_entry(label \|\| sketch_name)` | 单测 `NameProtectionTest`；实机拒绝矩阵未受影响 |
| 2 | 判定只比跨度，正方向请求 `n=[-1,0]`、整体偏移、缺体积/尺寸仍得 `verified=true` | 包络改为**有符号区间**（u[0,L]、v[0,W]、n[0,t] / n[-t,0]），原生 `planar_wall_require_envelope` 与 Python `envelope_problem` 双向强制；判定新增体积、方向、厚度读回、钣金 body、feature_id 必需项 | 单测 `EvidenceTest`（10 个反例）；实机 XZ 首跑即因方向不符失败并暴露第 4 行的方向语义缺陷 |
| 3 | 厚度来自请求或记录，未独立读回 | 新增 `ProSmtBodyThicknessValueGet`/`ProSmtBodyIsLinkedToPart` 读回（`MECHDOG_HAS_*` 门控并加入 `FUNCTION_PROBES`）；创建后按承载几何的钣金 body 比对；改型开始前从已保存文件重读并与记录比对 | 实机 `PLANAR_WALL_BODIES … thickness_mm=1.0 thickness_known=1 linked=1`；改型 `thickness_loaded_mm=1.0` |
| 4 | 公开接口未接完整：轮询看不到 `planar_wall`；同计划"创建→改型"被提前拒绝 | `bridge.compact_job` 结果白名单加入 `planar_wall`（full 本就按 page 输出）；`validate_plan` 按顺序模拟计划内别名，同计划创建→改型放行 | `test_job_result_publishes_the_verdict`、`PlanOrderTest`；实机 compact 轮询可见 |
| 5 | 关键实机场景缺失 | 驱动扩到 8 个实机场景（正/负方向、XZ、YZ、方形→长方形改型、下游依赖、原生拒绝回滚后合法编辑、旧首壁+折边链路） | 见下表 |
| 6 | 源码身份与交接记录未收尾 | 三份新实现文件进入 `reconciliation._deployment` 部署指纹；驱动报告改为按运行时间戳分目录并写入 commit/分支/dirty/逐文件 SHA256/worker 摘要；新增本契约文档 | `docs/development/FEAT058-PLANAR-WALL-CONTRACT.md`、`build/planar_wall/20261104T032633Z/adoption_live.json` |

另修正一处方向语义缺陷：`PRO_E_STD_DIRECTION=+1` 实际沿**支撑面法向**增长，而具名平面的草图 frame normal 是"请求轴"，XZ 支撑面法向为 +Y 时直接用 `+1` 会得到 `n[-1,0]`（实机 job `c4753cb6…` 失败）。现按 `tree_direction = (support_flipped == negative) ? +1 : -1` 修正并在 `PLANAR_WALL_DIRECTION` 记录两个法向。

实机结果（Creo 12.4.0.0，命令同上，报告 `build/planar_wall/20261104T032633Z/adoption_live.json`，67 项全部通过）：

| 场景 | 结果 |
| --- | --- |
| 创建 100×60×1 / 改型 120×80 | 6000 → 9600 mm³，`feature_id` 49 不变，`thickness_measured_mm=1.0`，保存重载 true |
| `direction=negative` | 6000 mm³，包络 `n[-1,0]`，`direction=negative` |
| XZ / YZ 支撑面 | 各 6000 mm³，包络 `n[0,1]`，`verified=true` |
| 方形 60×60×1 → 90×60 | 3600 → 5400 mm³，同一 `feature_id`，`square` 由 true 变 false |
| 下游依赖 | 原生壁挂 `sheetmetal_flange` 成功（子特征 104），改型在建模前被拒：`downstream dependencies ([104])` |
| 原生拒绝后回滚 | 转换模板模型上原生首壁 `failed`（要求钣金子类型），revision 保持 1，随后旧 `sheetmetal_wall` 成功 42920 mm³ |
| 旧首壁 + 折边链路 | 42920 → 47178.64 mm³，`saved_file_reloaded_and_verified=true` |

测试：`tests/unit/test_native_planar_wall.py` 14 项、`test_sheetmetal_contract` 37 项、`test_t01_capability_contracts` 11 项、服务/更新/引用 4 个模块合计 98 项通过；`dev_check --skip-unit` 无风格回归。

未验证/边界：非矩形或多环截面；`plane` 传显式支撑面并覆写 origin；原生壁上的第二个折边与四壁（受 FEAT-014/corner relief 限制）；Creo 9/10 实机；WorkBuddy 黑盒。厚度由壁体 `ProSmtBodyThicknessValueGet` 读回，零件级 `ProSmtPartThicknessValueGet` 在新鲜钣金模板读到 0，故不再作为证据来源。

交付记录：提交 `464a27e`（分支 `codex/FEAT-058-native-planar-wall`，父提交 `88a02dc`，提交时工作区干净）。受测源码指纹（SHA256 前 16 位）：`native/planar_wall.cpp ef3d0110295714b6`、`native/planar_wall.h e1956e8522579d7f`、`native/generic.cpp 3294e2848f69ec55`、`native/advanced.cpp be9056b6d9a77d28`、`src/creo_mechdog/native_planar_wall.py fe5ac85f8c9b8620`、`src/creo_mechdog/schema.py dbd66fccf6b648b6`、`src/creo_mechdog/capabilities.py c1caf4351f3871f2`、`generic_bridge.py 7da439dc26a3c5b6`、`server.py 623791f4f1967c09`、`tools/test_adoption_planar_wall.py 75f436a61d99a42b`。未跑 `tools/dev_check.py` 的单元部分（其环境与本机虚拟环境安装路径冲突），语言检查 `--skip-unit` 无回归。

复核整改交付记录：提交 `0dfb92f`（同一分支，父提交 `5ed8e3e`，15 个文件）。受测源码指纹（SHA256 前 16 位，CRLF→LF 归一）：`native/planar_wall.cpp 3c7c6a7674fdfb0e`、`native/planar_wall.h da6159fa0f9c622e`、`src/creo_mechdog/native_planar_wall.py 237a4777fae2303d`、`generic_bridge.py d6a17e8975bdc0db`、`bridge.py be8b91c50fb42da5`、`server.py 0073a75e5b9c1e65`、`src/creo_mechdog/reconciliation.py e305a6535b16bca5`、`tools/test_adoption_planar_wall.py c7752895221d8c22`。实机证据 `build/planar_wall/20261104T032633Z/adoption_live.json` 由该源码构建的 worker 生成（报告内含 commit/dirty/逐文件摘要/worker 摘要）。全量 `discover -s tests`（`PYTHONPATH=src`）2282 项：3 项失败 + 22 项错误，全部为本机虚拟环境 editable 安装指向 `codex-A03` 导致的 `server.py` 源检出保护与安装布局断言，与本改动无关；`dev_check --skip-unit` 无风格回归。剩余待办：非矩形截面、显式支撑面 origin、第二折边/四壁、Creo 9/10 实机、WorkBuddy 黑盒。

### 2026-11-04 复核整改（第三笔，关闭复核记录三处）

复核记录 `build/feat058_review_20261104T035042429265Z/review_findings.json`（基线提交 `d333f83`）给出 5 个 `expected_verified=false / actual_verified=true / problems=[]` 反例与 3 项 `runtime_fingerprint_omissions`。按用户要求只收口这三类、补对应反例回归，不扩展功能范围。

| # | 复核问题 | 复现反例 | 整改 |
| --- | --- | --- | --- |
| 1 | 尺寸缺失时体积、厚度、包络裁决整体被跳过，仅靠 `dimension_count` 兜底；改型不校验存档读回的厚度 | `missing_length`、`missing_all_sizes_and_shape`、`missing_loaded_thickness` | `result_projection` 把缺失尺寸本身记为 problem（`... reports no usable length/width/thickness ...`），不再进入静默分支；resize 的 `thickness_loaded_mm` 缺失或非有限也记为 problem（`... no gauge read back from the saved wall ...`） |
| 2 | NaN 使所有阈值比较为 False，等价于一致 | `nan_volume`、`nan_measured_thickness` | `_number()` 只返回有限数，NaN/Inf 视为无值并落入缺失分支；`volume_mm3`、`thickness_measured_mm`、`thickness_loaded_mm` 在投影中发布为 `null`；同类漏洞补到包络 min/max（`... extent is not finite ...`）与坐标系轴（`... is not a finite vector ...`） |
| 3 | 平面壁实现未进入运行时源码身份 | 三项 `runtime_fingerprint_omissions` | `server._SOURCE_NAMES` 补 `native/planar_wall.cpp`、`native/planar_wall.h`、`src/creo_mechdog/native_planar_wall.py`（`reconciliation._deployment` 第二笔已含，未重复改动） |

行为变化：改型结果只有带回读自存档的 `thickness_loaded_mm` 才算 `verified`（原生在 `MECHDOG_HAS_ProSmtBodyThicknessValueGet` 分支本就抛错，未定义该探针时输出 `null`，此前会被当成通过）；异常输入下投影不再泄漏 NaN。正向用例 `ResizeProjectionTest` 相应补 `thickness_loaded_mm=1.0`，与原生实际输出一致。

证据：`tests/unit/test_native_planar_wall.py` 新增 `CounterexampleTest`（缺尺寸 4 例、缺存档厚度 1 例、非有限 5 例，均断言 `verified is False` 且命中对应 problem）与 `RuntimeIdentityTest`（三项在 `_SOURCE_NAMES` 且可算出 64 位指纹），模块 18 项通过；`tools/test_unit.py` 全量 2286 项 OK（277s）；`tools/dev_check.py --skip-unit` `success=true`（24 条 lint、13 个未格式化文件均为既有基线）；三个改动文件 `ruff check` 与 `ruff format --check` 通过。

未验证/边界：原生 C++ 未改动，本次无实机运行，几何与实机证据沿用 `build/planar_wall/20261104T032633Z/adoption_live.json`；默认模板路线保留；非矩形、四壁、显式支撑面 origin 仍属后续范围；`annotate_result` 只裁决首个匹配算子（多壁结果）也未在本次扩展。

