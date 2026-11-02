# FEAT-051：round / chamfer / draft 的结果可观测性（体积差、方向与引用应用证据）

日期：2026-10-30（Asia/Shanghai）。类型：功能。优先级：P2。状态：已交付（0.10.0；契约冻结 + 离线实现 + 2026-10-31 run2 七夹具实机通过）。目标版本：0.10.0。

来源与关联：外部反馈 [0.8.5 细节特征报告](../validation/feedback-0.8.x-2026-10-30/20261030_CREO_v0.8.5_细节特征无体积回报_拔模方向只能靠体积反查.md) 全篇。关联 [DEV-052](DEV-052.md) 的 N04 任务；与 [FEAT-035](FEAT-035.md)（沉孔/沉头参数与几何）、[FEAT-034](FEAT-034.md)（T02 严格判定口径）、[BACKLOG](../BACKLOG.md) 的 BUG-018 行（逐操作结果契约）、[FEAT-014](FEAT-014.md)（钣金方向语义）相关但不同条目。

分类依据：新结果契约的范围与字段尚未冻结；按模板「输入、规则或预期仍不清楚」填「待规划」。**不填「已实现」或「已修复」**——外部报告只观察到「没有回报」，本仓库未复现，也未定义契约。

## 问题或目标

**外部观察（2026-10-30，反馈环境 Creo Parametric 10.0.0.0 / release_numeric 42 / mmns 模板 / MCP 0.8.5）**：

`creo_extrude` 的 cut 会回报 `material_removed_mm3`，可以逐刀对账；但 `round` / `chamfer` / `draft` 三个操作成功时**只回报 `succeeded: true`，不带任何体积增减量**。

报告方给出一个可复跑的三步例子（模型 `part2_rocker`，圆凸台柱面 `surface id=633`，中性面 `surface id=627`，TXT 要求 11° 内拔模，正确应去除约 15.42 mm³）：

| 步骤 | 入参 | 操作回报 | 实测体积变化 |
| --- | --- | --- | --- |
| 1 | `flip: false` | `succeeded: true`，无任何体积字段 | 3895.580255 → 3913.143937，**+17.564（加料，错）** |
| 2 | `feature_state delete d11_boss` | `applied: 1, tombstone_count: 1` | 回到 3895.580255 |
| 3 | `flip: true` | `succeeded: true`，无任何体积字段 | 3895.580255 → 3880.174229，−15.406（正确，解析 −15.416） |

两次调用**都返回 succeeded**，差别只有体积符号。若不做前后体积比对，第 1 步会被当成成功写入并保存——**拔模方向取反会静默加料并照样报成功**。

**建议（报告方提出，尚未定案）**

1. 给 `round` / `chamfer` / `draft` 也回报体积增减量，与 extrude 对齐，例如 `material_delta_mm3`（带符号）或 `material_removed_mm3` / `material_added_mm3`。这是唯一能让调用方自证「这一刀方向对不对」的证据。
2. `draft` 的方向语义需要显式化：当前 `neutral_plane` + `flip` + 可选 `pull_direction` 三者共同决定锥度方向，`pull_direction` 允许为 `null`，调用前无法预知符号。建议在返回结果里带上实际解析出的 pull 方向向量与锥度符号（外扩/内收），或在 `flip` 省略且 `pull_direction` 为 null 时把「方向未确定」作为 caveat 明确写出。
3. `chamfer` / `round` 建议回报命中的边/面数。报告方一次提交 3 组 face-pair 只回 `succeeded: true`，无法确认 3 组是否都命中（事后靠 `edges` 计数 159→169 反推）。

**本仓库现状（2026-10-30 静态核对）**：`material_removed_mm3` 目前只出现在 `native/generic.cpp` 的拉伸/旋转路径（`generic.cpp:2066`、`generic.cpp:2277`），round / chamfer / draft 路径确实没有等价字段；`creo_round`（`server.py:1171`）、`creo_chamfer`（`server.py:1199`）、`creo_draft`（`server.py:1442`）均为**独立公开工具**（`references` 为集合列表，入参 `radius`/`distance` 单位 mm）。因此外部观察在当前源码上**方向上成立**，但本轮**未实机复现**，也未测量过 `flip` 取反的实际体积符号。

**目标**：让调用方能区分**实测材料变化**、**实际方向/引用证据**和**未知结果**——成功不被误读成符合所有设计意图，回滚不被报告为已提交。

## 范围

**包含**

- 建议的结果契约（**实施前须与既有投影核对后冻结**）：原生在相应 `result.operations[]` 增加 `volume_before_mm3`、`volume_after_mm3`、`material_delta_mm3 = after - before`；`material_measurement{status, before_query_code, after_query_code}`，`status` 取 `measured` / `unknown` / `not_applicable`，未知值为 `null`。
- `draft_geometry`：记录实际引用 / flip / 角度 / 方向及 source / query_code，不能回读的字段为 `null`；多面拔模**不强塞**一个无法成立的全局「内收/外扩」。
- `reference_application`：分开 `requested_set_count` 与可由原生树证实的 `applied_set_count` / source / query_code。
- 真实原生块透传、缺查询保持 `null`、每操作一条结果、后续失败时先前变化标 `rolled_back`、`not_executed` 无伪造读数；compact/full 透传一致，公共响应保持 32 KiB 与有界投影规则。

**不包含**

- 输入不变、默认材料方向不变；旧 `material_removed_mm3` 字段不改义。
- 不在原生操作边界每操作额外做两次全模型 inspection；优先复用已有检查。
- 全模型边数差**不能冒充**命中数；输入数量不等于应用数量；无法取得应用数时明确未知。
- 若提出 `expected_material_effect` 等新输入，另交方案，不夹带实施。
- 本卡为 N04 的离线实现 + SDK 构建 + 定向证据；实机阶段另需用户点名并确认当前会话条件。

## 契约冻结（2026-10-30 N04，实现前冻结）

**字段名核对：**与 `src/creo_mechdog/operation_results.py` 既有投影、`bridge.compact_job`
操作键白名单及 N03（a6d4a3d）的 `profile` 诊断字段逐一核对，下列新键与任何既有
`operations[]` 键（含 `material_removed_mm3`、`revolve_axis`、`native_section`、
`feature_state`、N03 的 `near_tolerance_pairs` 等）无冲突；旧 `material_removed_mm3`
（拉伸/旋转切除路径）不改义、不改名，round/chamfer/draft **不**新增该字段。

**适用记录：**每个**已执行**的 `result.operations[]`（op ∈ round / chamfer / draft），
成功与失败记录都带材料块；`not_executed` 与旧版遗留记录**不带任何**读数块（不伪造）。
读回块（draft_geometry / reference_application）只在原生特征创建成功后出现；创建失败
记录省略读回块（缺失即缺失）。每输入一条记录，字段随既有 `index` / `execution_status` /
`effect_status` 契约（T02）透传。

**1. 材料测量（round / chamfer / draft）**

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `volume_before_mm3` | number \| null | 操作前模型体积（mm³）；该侧查询成功且模型长度单位→mm 比例已知（原生×比例³换算）时非 null，否则 null |
| `volume_after_mm3` | number \| null | 同上，操作后（重建后）体积 |
| `material_delta_mm3` | number \| null | = after − before；两端均非 null 才非 null。**零是合法报告值**，不新增无依据拒绝 |
| `material_measurement` | object | `{status, before_query_code, after_query_code}` |
| `material_measurement.status` | `"measured"` \| `"unknown"` \| `"not_applicable"` | `measured`：前后体积对均在 mm³ 建立；`not_applicable`：模型无可测实体（has_solid=false）；其余（查询失败、非有限、单位比例未知、后侧未执行）为 `unknown` |
| `material_measurement.before_query_code` / `after_query_code` | int \| null | 该侧质量属性查询的原始 ProError；仅当该侧查询从未执行时为 null（失败也保留原码） |

逐值 null 规则：任一未建立的**值**为 null（例如后侧查询失败时 `volume_before_mm3`
仍可报告实测值，`volume_after_mm3` 与 `material_delta_mm3` 为 null）。
单位未知（长度单位→mm 比例不可知）时三个体积值均为 null、status=`unknown`，
查询码保留真实值。毫米/英寸/其他单位系统按比例³换算为 mm³ 报告。

**2. `draft_geometry`（仅 draft；原生特征树读回，不能回读的字段为 null）**

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `source` | `"feature_tree"` \| `"unknown"` | 读回来源；树提取失败为 `unknown` |
| `query_code` | int \| null | ProFeatureElemtreeExtract 原始码；未尝试为 null |
| `neutral_plane` | `{type, id, query_code}` \| null | 树内 PRO_E_DRAFT_NEUTRAL_PLANE_1 的实际引用（ProType 原始值 + 几何 ID） |
| `pull_direction` | `{type, id, query_code}` \| null | 树内 PRO_E_DIRECTION_REFERENCE 的实际引用（缺省 pull 时即中性面引用，读回如实呈现，不回显请求） |
| `flip` | bool \| null | 树内 PRO_E_DIRECTION_FLIP 的实际值 |
| `angle_deg` | number \| null | 树内 PRO_E_DRAFT_ANGLE_1 的实际值（度） |
| `pull_vector` | object | `{frame:"model", vector:[x,y,z]\|null, source:"plane_normal"\|"axis_direction"\|"unknown", query_code:int\|null}`；只含引用几何自身可证向量（平面法向/轴方向），不做 flip 合成推导；引用非平面/轴时 vector=null、source=`unknown` |

**不设全局「内收/外扩」锥度字段**：多面拔模无法成立单一锥度结论；材料方向证据是
带符号的 `material_delta_mm3`（实测）与上述原始引用/flip/角度/向量。
`neutral_plane` / `pull_direction` 的 null 只表示树提取失败；树提取成功而单个引用
读取失败时保留 `{type: null, id: null, query_code: 原码}`，不丢查询码。`pull_vector`
是引用几何自身方向（平面 e3 法向 / 轴向单位向量），不做 flip 合成推导。

**3. `reference_application`（round / chamfer / draft）**

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `requested_set_count` | int | 输入集合数（round/chamfer=references 长度；draft=surfaces 长度）。请求侧事实，显式命名，不冒充证据 |
| `applied_set_count` | int \| null | 仅由创建后特征树证实：round/chamfer 数 PRO_E_RNDCH_SET 节点；draft 数表面集合指令。不能证实时 null |
| `source` | `"feature_tree"` \| `"unknown"` | 应用数来源 |
| `query_code` | int \| null | 树读回原始码；未尝试为 null |

**输入数量、全模型边数差不得冒充命中数。**无法取得应用数时明确未知（null + source=unknown）。

**4. 透传与预算**

- Python 只透传不推导：`annotate_native_result` 不新增、不填充、不升级任何上述块；
  缺块保持缺失，缺值保持 null。块内容以原生执行器为唯一来源。
- compact/full 一致：`bridge.compact_job` 操作键白名单加入上述六个键，两个视图携带
  相同字段；块有界（每操作固定大小、无无界列表，实测六块合计约 1 KiB 量级）。32 KiB
  硬预算分页保证的是 capabilities / 模型查询等列表响应（不含 operations[]，本次不
  受影响）；作业结果沿用既有有界投影口径（compact 键白名单），不为本次新增分页或
  截断——`creo_execute_plan` 上限 200 操作的极端满载 compact 响应与既有 profile 样本
  字段同口径线性增长，非新增回归。
- 批中途失败：先前操作的实测块保留历史值，`effect_status` 由 T02 既有规则标
  `rolled_back`（有回滚证据时）；失败操作带材料块（后侧码 null）；`not_executed`
  记录无任何读数。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `python -m unittest tests.unit.test_detail_feature_observation tests.unit.test_t02_operation_results -v` | 真实原生块透传；缺查询保持 `null`；每操作一条结果；批中途失败时先前变化标 `rolled_back`、`not_executed` 无读数；公共响应预算保持 |
| Windows / 匹配 SDK | `python bridge.py build` | 编译 exit 0；执行器重建 |
| 本机 Creo 12.4 / 匹配 SDK | `python tools\test_detail_feature_observation.py --live --confirm-session-usable` | 凸/凹圆角、三组 face-pair 倒角、draft flip 双向、缺省/显式 pull、批中途失败的夹具逐例通过；单位覆盖 mm/in/混合与未知；差值与独立几何预期一致；零差值如合法就报告零，不新增无依据拒绝 |

按当前项目规则，不要求 Creo 10 独立复测或双版本验收作为完成门槛；其他环境收到具体反馈后再跟进，证据始终标明实际环境。禁止只写「能运行」或引用历史成功数代替本次验收。

## 实现与证据

**2026-10-30（登记，仅静态核对，未实现）**

本轮为 N00 文档阶段：依据外部 0.8.5 报告登记本卡，并只读核对当前源码——`material_removed_mm3` 仅存在于拉伸/旋转路径；`creo_round` / `creo_chamfer` / `creo_draft` 已是独立公开工具（报告方在同一份报告的「附带更正」中亦更正了早前一轮「只在 plan 通道」的说法，与本仓库一致）。未编译、未运行单元测试、未连接 Creo、未改任何生产代码。

未验证范围：外部报告的「只回 succeeded、无体积字段」**未在本机实机复现**；`flip` 取反导致的 +17.564 mm³ 加料**未实测**；11° 拔模的解析值 −15.416 mm³ 为报告方计算，本机未独立复算。契约字段名与状态取值**尚未冻结**。证据：见 [归档 MAPPING](../validation/feedback-0.8.x-2026-10-30/MAPPING.md) 与 [manifest](../validation/feedback-0.8.x-2026-10-30/manifest.json)。

下一步：按 N04 指派执行离线实现与 SDK 构建；契约字段先与既有投影核对再冻结，实机阶段另需用户点名。

**2026-10-30（N04 离线实现与 SDK 构建，已冻结契约，未实机）**

分支 `codex/dev051-feedback070`（基线 a6d4a3d 之上；执行期间同分支另一窗口合入
142e7d8 N07—N12 离线预检，未改其内容）。实现范围：

- **原生（`native/generic.cpp`）**：round/chamfer/draft 操作边界复用既有轻量质量属性
  查询（与切除路径同款 ProSolidMassPropertyWithDensityGet，每操作前后各一次，不加
  两次全模型 inspection）；按冻结契约产出 `volume_before_mm3` / `volume_after_mm3` /
  `material_delta_mm3` / `material_measurement`（mm³ 按长度单位比例³换算；逐值
  null；查询失败保原码；has_solid=false → not_applicable；零差值如实报0）。失败
  记录带真实 before 侧、after 侧码 null。round/chamfer 从创建后特征树数
  PRO_E_RNDCH_SET 得 `reference_application`（零计数对非空请求视为不可证 → unknown）。
- **原生（`native/advanced.cpp`，仅 generic_draft 范围）**：generic_draft 返回
  `draft_geometry`（特征树读回中性面/拉伸引用/flip/角度 + 平面法向或轴向可证向量，
  失败逐项 null+原码）与 `reference_application`（表面集合指令计数）。
- **投影（`bridge.compact_job`）**：compact 键白名单加六键，compact/full 一致透传；
  `src/creo_mechdog/operation_results.py` 零改动（纯透传，源码测试锁定不推导）。
- **驱动**：`tools/test_detail_feature_observation.py`（默认离线；`--live` 需同时
  `--confirm-session-usable`；输出唯一不覆盖，默认 `build/post090_n04_<run_id>/report.json`）。
  夹具矩阵：凸圆角（盒体立边，解析 −20·9·(1−π/4)）、凹圆角（L 棱柱内角，同幅正号）、
  三组 face-pair 倒角（3×20·2²/2 = 120 mm³）、draft flip 双向（Ø6×3 圆柱 11°，
  解析内收 −15.416 / 外扩 +17.555，与外部 0.8.5 报告解析值同式；flip→方向映射依
  赖中性面朝向，按「幅度精确、符号相反、实测符号记录」判定，不强设）、缺省/显式
  pull（读回引用证据）、批中途失败（好圆角→无效边失败→尾随倒角：rolled_back /
  部分读数 / not_executed 无读数）、零差值投影行；单位矩阵 mm/in/混合/未知走
  合成记录+比例³换算判定（公开建模工具仅产 mmns 件，且禁止故障注入，英寸/混合/
  未知单位只在离线覆盖）。解析式经数值积分独立复核（numeric_oracles_agree）。
- **回归**：`tests/unit/test_detail_feature_observation.py` 41 例（契约透传、缺值
  null、not_executed 无读数、rolled_back 保留读数、compact 透传、有界投影、原生
  源码契约、夹具与判定函数）；复用 `tests/unit/test_t02_operation_results.py` 全绿。

命令与退出码（2026-10-30，Windows x64 / Python 3.12 venv / MSVC x64 / Creo 12.4.0.0
匹配 SDK；工作区 dirty=是，受测指纹见报告 provenance）：

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_detail_feature_observation tests.unit.test_t02_operation_results -v` | 0 | 59/59 通过 |
| `.\.venv\Scripts\python.exe tools\test_detail_feature_observation.py --output build/post090_n04_20261030T214903_5a4173ca/report.json` | 0 | 离线 9 夹具 + 4 单位行 + 数值复核通过，LIVE NOT RUN |
| `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-051` | 1 | 本任务回归 0；**唯一剩余回归为 142e7d8 引入的** `docs/development/DEV051-T09D-ACCEPTANCE.md` **格式项**（ruff format 格式化 markdown 代码块；非本任务路径，未改动）。样式阶段阻断其 unit 阶段 |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests` | 0 | 1626/1626 通过（dev_check unit 阶段被上述外部回归阻断，另行全量补证） |
| `.\.venv\Scripts\python.exe bridge.py build` | 0 | `build/creo_worker.exe` 重建 |

**未测范围（实机）**：measured 体积差与解析预期的一致性、draft_geometry 读回真值、
reference_application 应用数、批回滚语义、保存重载、额外查询成本对比——全部待实机；
flip→方向映射只离线定义判定规则，未观测。实机命令（本任务未执行）：

```
.\.venv\Scripts\python.exe tools\test_detail_feature_observation.py --live --confirm-session-usable --output build/post090_n04_<新runid>/report.json
```

## 2026-10-30～31 N04 实机复测追加

分支 codex/dev051-feedback070，基线 7288f2f，runid 20261030T234952。首例创建后驱动读取 result.revision 抛 KeyError；材料变化、draft_geometry、应用集数、回滚与重载矩阵均未验。 完整 job_id/model_id/revision、原始错误、命令、报告路径与 SHA256 见 [七段实机总报告](../development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)；原始 JSON 留在 build/post090_live_20261030T234952/，未入库。未重放已受理作业，会话保持运行。

## 2026-10-31 N04 live runner 缺陷修复（离线，未实机）

分支 `codex/dev051-feedback070`，基线 a94139e（5018f02 七段记录之上）。本轮只修
live runner 的终态读取缺陷并补单元锁定，**矩阵九夹具与判定口径不变**、未连接
Creo、未构建、未实机。

- **根因（核对真实 plan 结果结构后定）**：`run_case` 在首个 `creo_execute_plan`
  后读 `created_terminal["result"]["revision"]`。实际结构里模型 revision 是
  **job manifest 顶层字段**，不在 `result` 内——`generic_bridge.run_generic_job`
  成功收尾时 `manifest.update(..., revision=model["revision"])`（原 :610），
  `bridge.compact_job` 顶层键白名单亦列 `"revision"`；`tools/test_sheetmetal_contract.py:453`
  的正确读法即 `terminal.get("revision")`。N01 contract 同会话 5/5 通过、其
  revision 逐例记录在案，反证结构本身正常；N04 只是读错了层，于是
  `KeyError: 'revision'`。
- **修复**：新增纯函数 `terminal_model_revision(terminal, context)`（缺顶层 int
  revision 时抛带上下文的 `RuntimeError`，消息指明 revision 在 manifest 顶层，
  绝不 KeyError；bool/float/str 型 revision 一律拒绝），`run_case` 改经它取
  `expected_revision`。
- **单元锁定**：`tests/unit/test_detail_feature_observation.py` 新增
  `DriverTerminalRevisionTests` 6 例（顶层 int 读取；result 内嵌 revision 不作
  来源；缺失时清晰报错而非 KeyError；非整型拒绝；非 dict 终态带上下文拒绝；
  源码守卫断言驱动不再出现 `["result"]["revision"]`）。
- **命令与退出码（2026-10-31，Windows x64 / Python 3.12 venv；dirty=是，同分支
  另一窗口 N05 提交后的工作区）**：
  `.\.venv\Scripts\python.exe -m unittest tests.unit.test_detail_feature_observation tests.unit.test_sheetmetal_relief tests.unit.test_sheetmetal_contract -v` → exit 0，142/142 通过；
  `.\.venv\Scripts\python.exe tools\test_detail_feature_observation.py --output build\post090_n04_f1a_offline\report.json` → exit 0，离线 9 夹具 + 4 单位行 + 数值复核通过，LIVE NOT RUN；
  `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-051` → exit 0（style 无回归，单元全量通过）。
- **未测范围（实机）**：全部 live 矩阵仍待重跑——凸/凹圆角、三组倒角、draft
  flip 双向、缺省/显式 pull、批回滚、保存重载与应用集数均无本机实测结论。实机
  命令（本任务未执行）：
  `.\.venv\Scripts\python.exe tools\test_detail_feature_observation.py --live --confirm-session-usable --output build\post090_n04_<新runid>\report.json`；
  预期：九夹具逐例有判定行，不再出现 KeyError；结果缺顶层 revision 时报告为
  清晰驱动错误而不是崩溃。

## 2026-10-31：N04 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n04/run2/report.json`（SHA256 `714db02d…9fc2`，`run_id=20261031T133944_03b62f94`，`mode=live`，`native_acceptance=recorded`，`live_run=true`，`volume_tolerance_mm3=0.01`，`flip_pair_opposite_signs=true`，`provenance.source_fingerprint=ae5ec35b…1a4eb`）。本节只追加，不改写 2026-10-30～31 首轮记录。

### run1 的夹具失败与修复（过程如实记录）

首轮 `build/post090_live2_20261031T115830/n04/run1/report.json`（SHA256 `eb7622d0…79abc`）在 `draft_explicit_pull` 的底件创建阶段失败：`RuntimeError: base creation failed for draft_explicit_pull: … Toolkit call ProModelitemInit(board, id, t, &mi) failed with code -23 during execute_datum_axis`（job `a044dfcfe5fe4b8986953e8872773f99`）。根因是**夹具把 datum_axis 的引用硬编码成 `{"kind":"surface","id":1}`**，而实机不存在 surface id 1；`-23` 即 `PRO_TK_NOT_EXIST`。修复提交 `b5dce10` 改用默认基准面 2（X 法向）与 4（Y 法向）相交构造 Z 轴（与圆柱轴同轴），run2 全部通过。该修复只动夹具，不动原生语义。

### run2 九夹具结果

| 夹具 | model / 作业 | 实测材料变化 (mm³) | 树证 | 判定 |
| --- | --- | --- | --- | --- |
| `round_convex` | `6fccaa4d677e44acb10430af5d9d2d76` / `97f1a3614de8456c92c0c8b4ce8baea3` | **−38.62833848818991**（对上 −38.628330588459306，误差 7.9e-06） | applied=requested=1 | pass |
| `round_concave` | `a8fec19200f14c6495d0b639607b0ba2` / `d2edc6f4485c40b982618e0aec763df9` | **+38.628301733198896**（对上 +38.628330588459306，误差 2.9e-05） | applied=requested=1 | pass |
| `chamfer_three_face_pairs` | `9c22f813336946999ee65e1b17ce0e05` / `8a8e2b6c1e0c435cb00f78641e3c9a46` | **−120.00000000000364**（对上 −120.0，误差 3.6e-12） | applied=requested=3 | pass |
| `draft_flip_false` | `579bc2acfa5840a1b6e29f163a120713` / `04a937bb6e484c9f9d44ee97f8f31a9e` | **+17.556230361033258**（对上 +17.556230360737217，误差 3.0e-10） | applied=requested=1 | pass |
| `draft_flip_true` | `1deee2ff096a44b8bdb56653b637c8c5` / `e6d56733887246a29e8788377fd2e707` | **−15.41961220323752**（对上 −15.419612203499526，误差 2.6e-10） | applied=requested=1 | pass |
| `draft_default_pull` | `a0b2b2a9163d46a0b8696c88b3dee2a1` / `ff0d3b51ab42473eb69b458e701c76d1` | **−15.41961220323752** | applied=requested=1 | pass（`pull_verdict=pass`） |
| `draft_explicit_pull` | `2dbed55b07554e359663dcd8b7aa4c68` / `218a026bb8a744e2987e73eb08f2d65e` | **−15.41961220323752** | applied=requested=1 | pass（`pull_verdict=pass`） |
| `batch_mid_failure` | `45397c2a2e4b4bb5977efc679c4ffd4c` / `2d81e427398e434dafa16a9378084ba4` | 首操作有读数 −38.62833848818991（`effect_status=rolled_back`） | — | `batch_verdict.status=pass` |
| `zero_delta` | — | — | — | `not_applicable_live`（离线专属） |

要点：

- **拔模方向成对**：flip=false 为 **+17.556230361033258**、flip=true 为 **−15.41961220323752**，符号相反、幅度精确对上解析值（−15.419612203499526 / +17.556230360737217），`flip_pair_opposite_signs=true` 成立。flip 方向映射仍由"中性面朝向 + 实测符号"自证，未强设（外部 0.8.5 报告的 +17.564 / −15.406 为外部值，本机独立解析值以本表为准）。
- **pull 方向回读**：缺省 pull 时 `neutral_plane` 与 `pull_direction` 同为 id 54（type 5，面）、`pull_vector.source=plane_normal`、向量 `[0,0,1]`；显式 pull 时 `pull_direction` 为 id 72（type 21，轴）、`pull_vector.source=axis_direction`、向量同为 `[0,0,1]`。两例 `pull_verdict=pass`。
- **批中途失败按设计验证**：作业终态 failed、`rollback_succeeded=true`；第一操作（好圆角）**保留读数** −38.62833848818991 且 `effect_status=rolled_back`，第二操作（失败圆角）`material_measurement.status=unknown`、after 侧读数为 null，第三操作（尾随倒角）`execution_status=not_executed`、`effect_status=no_effect`——"首操作有读数、失败回滚、后续 not_executed"三条判读信号齐备。
- **重载**：七例 `saved_file_reloaded_and_verified=true`（`batch_mid_failure` 为 false，因整作业失败，属预期）；`material_measurement` 全部 `status=measured`，查询码 before/after 均 0。

### 未测范围

`zero_delta`（合法零差值投影）为**离线专属**，实机不适用；单位矩阵 mm/in/混合/未知仍只由离线合成记录覆盖。外部 SDK 与其它 Creo 版本未测。本卡本节不改写 2026-10-30 的离线交付记录。

## 2026-11-02 增量：`flip` 需区分请求与生效，失败需分类（外部反馈，未实现）

来源：[0.10.0 第十轮反馈 F02 §五](../validation/feedback-0.10.0-2026-10-31/MAPPING.md)（N1，另见 [BUG-102](BUG-102.md)）。

- **已交付部分**：`material_delta_mm3` 带符号可识别加料/去料，`draft_geometry` 读特征树实际值（`native/advanced.cpp:160-193`），N04 第二轮实机 flip=false `+17.556230`、flip=true `−15.419612` 成对成立。
- **缺口 1（签名歧义）**：入参 `flip=false` 而回显 `draft_geometry.flip=true` 时，调用方无法判断该值是“请求被翻转后应用”还是“实际生效值”。`requested_flip`/`effective_flip` 全库 0 命中。计划：`draft_geometry` 增两个字段（保留现有 `flip` 不动以免破坏既有契约），工具描述说明差异；缺读回时 null 不补造。
- **缺口 2（失败不可解释）**：`ProFeatureWithoptionsCreate=-1` 只有裸码，未区分“与圆角/倒角几何冲突”“引用错误”“参数越界”。计划：按 BUG-102 的 A/B 定因结论给分类诊断与下一步动作，避免只回 -1。
- **边界**：多面拔模仍不强塞全局“内收/外扩”结论；`material_measurement` 与既有 `material_delta_mm3` 语义不改。
