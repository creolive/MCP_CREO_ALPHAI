# 0.10.0 晚间反馈后续完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施。步骤使用复选框跟踪；用户负责向其他 agent 派工，本轮不启动实施。

**Goal:** 基于当前 0.11.0 对本反馈包去重，优先修复正确性与事务问题，再推进斜面草图、曲面链路和 P12 验收；上色已交付，不重复派工。

**Architecture:** 保留 MCP → bridge → generic_bridge → C++ Toolkit 单通道。离线模块可并行开发；原生实验、构建、实机与最终集成由一名负责人串行安排。先调查可行性，再承诺公开能力。

**Tech Stack:** Windows x64、PowerShell、Python 3.12+、unittest、Pydantic、C++17、Creo 12.4.0.0、匹配 Toolkit SDK、MSVC。

**Spec:** [后续完善范围与决策](../specs/2026-11-01-feedback0100-followup-design.md)。执行人必须同时读取。编制及对账日期 2026-11-01（Asia/Shanghai）；初版基线 `main@89ee542` / 0.10.1，当前基线 **`main@2f6aab7` / 0.11.0 / 95 工具**。下文 Q 编号是派工号，不是固定 ID。**Q12 已随 0.11.0 交付；其他任务按下表状态继续**。本次仅整理文档与本地冗余，见 [DEV-054](../../work-items/DEV-054.md)，未实施其余产品任务。

## Global Constraints

- 新业务进 `src/creo_mechdog/`；根包装共享类型，服务 stdout 只承载 MCP。
- 长度 mm、角度度；标签小写字母开头、只含小写/数字/下划线、最多 28 字符。
- 工程 ID、目标、范围、验收与环境须在实现前登记；已完成 ID 不自动重开。
- 本机只用 E 盘 `MCP_CREO_MechDog_dev`；先核 BUG-001/BUG-091 会话准入，不擅自连接、重启/结束 Creo 或清 unknown 保护。
- 忙立即返回 isError=true/status=busy 和 blocking 信息，不排队、不自动重试；受理后只轮询 creo_get_job。
- 新单测在 tests/unit/，用 unittest；校验/保护必须补回归；原生必须构建、实测几何、保存擦除重载与适用回滚。
- 本机 Creo 12.4.0.0 按范围验收；Creo 9/10 未验继续明示，不恢复双版本门槛。
- WorkBuddy 只用 MCP 黑盒，不读源码、不跑本地脚本，与开发者验证分开。
- 保护 dirty 与其他工作树；历史 docs/validation 原件逐字节不变；生成物不进入源码包。
- 合入 main 必须同批正式 Release、未占用新版本、主干标签、两包和哈希远端核验；开发提交无须逐个发布。

## Review Focus

1. 输入闭合但求解后漂移、编辑后才漂移或测量失败：Q02 必须给真实偏差或 unavailable，不能把闭合 gap 当几何保真。
2. 同名预存对象、用户修改、外部引用或结果未知：Q03 必须保留，不能因本 job 失败误擦除。
3. 合法 identity、平移 XY、反向 U、斜面 normal 与近共线三点：Q05/Q06 须以真实帧和几何验证，不按矩阵表象猜测。
4. 反向投影、多片 quilt、多环 trim、旧 revision 或失效引用：Q07/Q09/Q10 须明确选择语义和拒绝，不用第一个匹配项冒充目标。
5. 大结果截断、颜色/曲面回执查询失败或重载后引用变化：Q12/Q13/Q15 保留总数、unavailable 和真实重载证据，不用截断样本证明全量成功。

## 一 先看这个派工表

第一轮建议同时派 **Q00、Q02、Q03、Q04**。Q00 完成登记后，Q02–Q04 才可写产品代码。第二轮派 **Q01、Q05、Q06、Q07**；同一原生文件由集成人顺序收取提交。Q11 的离线配方核对可以提前做，完整建模需等待前置能力。Q12 已交付，退出开发派工；若用户安排 WorkBuddy 黑盒，只补尚未验证的用户行为，不重做上色实现。

| 派工号 | 当前状态 | 优先级 | 独立交付 / 固定 ID | 下一步与前置 |
| --- | --- | --- | --- | --- |
| Q00 | **已完成：晚间包已逐字节归档（10/10）；FEAT-009/010 卡与新 ID 已登记** | P1 | DEV-053 接续；本次维护 DEV-054 | 归档映射见 [feedback-0.10.0-2026-11-01/MAPPING.md](../../validation/feedback-0.10.0-2026-11-01/MAPPING.md)；新登记 BUG-096/BUG-097/FEAT-053 |
| Q01 | 离线开发完成；实机未执行（BUG-098） | P2 | P07/P08/P11；BUG-095/032/088、FEAT-014 | 保留 dev053 分支，选择性集成；下一 MINOR 重新核号 |
| Q02 | 离线开发完成；实机未执行（BUG-098） | P1 | A/D 求解保真；FEAT-010 / BUG-049（**写程序高手**） | Q00 已完成登记；统一创建/编辑的实际偏差 |
| Q03 | 离线开发完成；实机未执行（BUG-098） | P1 | E 失败新对象清理；**BUG-096**（本次新登记），交叉关联历史 BUG-012/FEAT-018（**代码编写者**） | Q00 已完成登记；不重开完成档案旧 ID |
| Q04 | 离线开发完成；实机未执行（BUG-098） | P2 | N1/N2；FEAT-033，必要时独立 BUG（**codex代码**） | Q00 已完成登记；bridge.py 与 server.py 两处都核 |
| Q05 | 离线开发完成；实机未执行（BUG-098） | P2 | 三点定面；**FEAT-053**，关联 FEAT-008 | `main_plane` 首例在特征树校验处卡死（BUG-098）；恢复会话后先重跑该驱动 |
| Q06 | 离线开发完成；L1/L2 实机未取证（BUG-098） | P1 | 斜面草图 L1/L2；**BUG-097**（本次新登记），关联 FEAT-010/BUG-087/095 | 新增 `tools/test_tilted_sketch_3pt.py` 离线通过；live 被 BUG-098 阻断，L1/L2 未取证 |
| Q07 | **契约冻结；P1–P3 探针未执行** | P2 | G5 契约；FEAT-009 / FEAT-039（卡已补建） | 探针执行器未实现且实机被 BUG-098 阻断；P1–P3 未执行，Q08–Q10 不开工 |
| Q08 | **未开工**：Q07 P1 未判定 | P2 | surface_loft；FEAT-009 | Q07；斜面用例需 Q06 |
| Q09 | **未开工**：Q07 P2 未判定 | P2 | project_curve；FEAT-039 | Q07；现有曲面可先验 |
| Q10 | **未开工**：Q07 P3 未判定 | P2 | surface_trim / 测量；FEAT-039 | Q07/Q09；完整链需 Q08 |
| Q11 | 离线开发完成；实机未执行（BUG-098） | P3 | 扭叶片 P12；DEV-053 场景，必要时新 FEAT | 离线映射已就绪；分站 Q02/Q05/Q06；正规 Q08–Q10 |
| Q12 | **已交付：0.11.0，本机 28/28；不再派开发** | — | FEAT-052 装配按族上色 | 仅保留明确未测范围，见完成记录 |
| Q13 | 离线开发完成；实机未执行（BUG-098） | P2 | F 大回包 / H 预览；FEAT-008 / BUG-088 | Q00 已完成登记；Q01 先对齐，不把上色分页扩推全局 |
| Q14 | 离线开发完成；实机未执行（BUG-098） | P3 | 按 Q00 映射（C→FEAT-010）；分项登记原或新 ID | Q00 已完成登记；分项调查，不直接承诺修复 |
| Q15 | 离线集成完成；**0.11.1 未发布（实机被 BUG-098 阻断）** | P1 | 集成/发布/黑盒交接；DEV-053 / 本批 ID | 其余任务逐批验收；不把 FEAT-052 发布当整计划完成 |

**不要混淆两个 P12：** DEV-053 旧计划的 P12 是 Creo 10 构建补证；本包 P12 是扭叶片零件。下文统一称“扭叶片 P12”。

**负责人字段（2026-11-01 Q00 登记）：** Q02→写程序高手、Q03→代码编写者、Q04→codex代码（已指派）；其余 Q 任务一律 `unassigned`，不虚构认领。逐章归属、缺件表与新 ID 卡片见[归档映射](../../validation/feedback-0.10.0-2026-11-01/MAPPING.md)；其他 agent 直接读 `docs/BACKLOG.md` 取固定 ID。

## 二 当前版本去重与缺件

| 项目 | 本次核查结果 | 执行决策 |
| --- | --- | --- |
| BUG-092 / BUG-093 | 0.10.1 已有退出和反例取证收口 | 不再派完整重修；只按影响回归，修订过期摘要 |
| 仓库 BUG-094 | angle/offset 契约及本机指定用例已验收 | 保留结论，不承载本包 L1/L2 新问题 |
| P07/P08/P11 | dev053 分支有离线实现，尚未进 main；对应提交 50b34a1 / 28b1447 / 53ed968 | Q01 复核差异后接续，不把整个旧分支直接合入 |
| 旧主计划与设计 | 2026-10-31 未跟踪文件，内容保留旧 0.10.0 时点 | 不覆盖；本计划作为新快照 |
| 上色 | FEAT-052 已登记并随 0.11.0 发布；262ef20 为发布提交、2f6aab7 为核验回填；原工作树含未跟踪模型 | Q12 完成，不再开发；保留测试数据与正式附件，见 [发布记录](../../validation/RELEASE-0.11.0.md) |
| FEAT-009 / FEAT-010 | BACKLOG 有条目，单独工作卡当前缺失 | **2026-11-01 已补卡**（沿用既有 ID，不另登新编号）；工作卡内容按晚间包补充，不能被当作新能力编号 |
| L1/L2 原始 job 日志、smoke_3pt_b–f、p12_v12_ops_a1.json、完整 v1.2 TXT/判据 | 报告提到，当前包未附；只有 smoke_3pt_min_repro 等四个 JSON | 缺件逐项登记于 [归档 MAPPING 缺件表](../../validation/feedback-0.10.0-2026-11-01/MAPPING.md#缺件清单)；可做替代实验，不冒充原 job 回放 |
| 原 6 图元 A/D 完整输入、B/C/G 原案 | 01 报告无完整输入；是否能在旧归档取得须 Q00 查明 | **2026-11-01 已查：同目录上游运输 zip 与目录内容完全一致（同样 10 件），仓库历史与既有归档中亦无**，缺件状态成立；有明确数值的替代夹具可先推进，原案结论保持未验证 |

## 三 任务卡

### Q00：归档、登记与当前状态对账

**文件：** 新建 `docs/validation/feedback-0.10.0-2026-11-01/manifest.json`、`MAPPING.md` 与原件子目录；修改 `docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、`docs/work-items/DEV-053.md` 及相关工作卡。只追加新归档，不改旧 validation 原件。

**接口：** 产出十文件的 path/size/sha256 清单、来源章节→Q任务→固定ID→负责人表、缺件表和基线提交；后续 agent 均引用该表。尚未被用户指派的负责人填 `unassigned`，不虚构认领。新 BUG/FEAT 先检查主干、其他工作树与认领，再核号，不预占 BUG-094 或 FEAT-052。

- [x] DEV-054 已检查 HEAD、版本、dirty、分支/工作树及已有条目；“主干已交付”“开发分支已实现”“外部观察”“未复测”已分开，后续执行前复核新变化。
- [x] 十文件逐字节复制；ZIP 原包不改，内置文本列来源即可，不执行附件程序。逐件比较长度、SHA256 与字节，归档 manifest 不写本机生成文件。**2026-11-01 完成：10/10 长度、SHA256 与字节一致**，见 [manifest](../../validation/feedback-0.10.0-2026-11-01/manifest.json) 与 [originals](../../validation/feedback-0.10.0-2026-11-01/originals/)。
- [x] 创建缺失的 FEAT-009/010 工作卡；为 E 与 L1/L2 登记新问题，为三点平面登记新增能力；既有完成档案 BUG-012 仅交叉关联。**2026-11-01 完成：BUG-096（E，关联 BUG-012/FEAT-018）、BUG-097（L1/L2，关联 FEAT-010/BUG-087/BUG-095）、FEAT-053（三点定面，关联 FEAT-008）**。
- [x] DEV-054 已对齐当前入口 **0.11.0 / 95 工具** 与指定已交付范围、工作卡首页和分类计数；后续只补新变化、缺件与新ID，原始反馈归档仍待。**2026-11-01 晚间包归档已完成**，映射与缺件表见 [MAPPING](../../validation/feedback-0.10.0-2026-11-01/MAPPING.md#缺件清单)。
- [x] 检查新增链接、ID 唯一性、所有 Q 任务有范围/验收/环境/负责人字段（可为 unassigned）；独立文档提交，不合 main、不发布。**2026-11-01 完成：台账 140 行/140 唯一 ID（新增 BUG-096、BUG-097、FEAT-053），负责人仅 Q02/Q03/Q04 已指派、其余 unassigned。**

**通过条件：** 10/10 字节及哈希一致、所有章节有归属；不把缺件当附件或已有分支当已发布。

### Q01：接续已有 MINOR 批次

**文件：** 以 `git diff main...codex/dev053-post0100` 实际结果为准，重点 `native/generic.cpp`、`src/creo_mechdog/operation_results.py`、对应原点/钣金帧/空件预览的测试及文档。读取旧分支测试清单后复用，不另写同类实现。

**接口：** 保留 P07 原点实测距离/方程/1e-6 mm 阈值、P08 方向和候选边证据、P11 空件预览状态的原契约。输出“待集成提交及冲突决策”清单给 Q15；不能带回旧版本元数据覆盖当前 0.11.0。

- [ ] 核三个提交及已进 main 的同源改动；选择迁移变更，不整枝合并包含重复 PATCH 的旧分支。
- [ ] 运行原任务专项 unittest 和默认离线驱动，旧结论保留原日期；新集成源码产生新指纹。
- [ ] 把 Q06 原点/坐标诊断、Q13 预览的字段所有权写入交接，避免两个 agent 改同一返回字段。
- [ ] 在统一实机窗口补本次构建、几何、候选边 unknown、空件状态、保存重载证据；未测部分不得写已交付。

**通过条件：** 三个子任务分别可验；未通过者不阻挡其他已验任务单独发布。

### Q02：A/D 草图求解后的几何保真

**文件：** `native/sketch_coordinates.cpp`、`native/sketch_solver.cpp`、`native/sketch_edit.cpp`、`native/generic.cpp`；`src/creo_mechdog/schema.py`、`operation_results.py`；根 `server.py` 仅同步工具签名、`capabilities.py` 同步描述；新建 `tests/unit/test_sketch_geometry_deviation.py`、`tools/test_sketch_geometry_deviation.py`，复用现有弧/倾斜草图夹具。

**接口：** sketch 创建与编辑统一输出 `geometry_deviation`，至少包含 `available`、`max_deviation_mm`、`warning_threshold_mm`、`exceeds_warning`、`measurement_scope`、`total`、`sample`、`truncated`；样本上限 20。无法比较的值为 null 并说明原因。新增 `geometry_tolerance_mm: float | None = None`；独立工具与 plan 同源。兼容保留已有 solver.coordinate_geometry / coordinate_geometry_after_creation；按两阶段都核验，不能只测 SectionRegenerate 后、漏掉 CompleteFeature 后的变化。

- [ ] 先建立有独立解析面积/半径/体积的弧线混合轮廓，检查是否取得原 6 图元；同时覆盖 coordinates/autodim/auto、创建/编辑和非主平面。把原案与替代用例分开。
- [ ] 补失败回归：输入闭合并不保证求解保真；radius 漂移、中心漂移、端点漂移、反向弧/中心线、查询失败不能返回全 0；比对输入规范化后实体与求解后实体的同一身份。
- [ ] 扩展求解前快照到各模式，核共享顶点/弧端点约束而非预设“重复约束”为根因；修复有证据的约束问题。中心线按无限线方向/偏移，不能按可滑动端点误判。
- [ ] 接入诊断和显式容差：默认 coordinates 保留当前源码的 **1e-5 mm**，不是反馈所称 1e-4；沿用当前偏差量纲/度量并写明，不悄悄换范数扩大或收紧默认闸门。autodim 超 1e-3 告警；提供 tolerance 时按请求强制上限。拒绝 bool/NaN/Inf/0/负数；显式严格策略遇不可测图元明确拒绝。不添加 coordinates_lenient 模式。
- [ ] 运行 `python -m unittest tests.unit.test_sketch_geometry_deviation -v`；再由实机负责人运行新驱动，验证默认/显式容差阈值两侧、原半径面积、编辑后下游体积、revision、回滚及保存重载。

**通过条件：** autodim 不再静默失真；coordinates 的放行有明示请求和实测依据。独立 oracle 不能直接抄“正确面积 136486.4”的近似参考值。

### Q03：E 失败新模型的安全清理

**文件：** `native/generic.cpp` 新件创建/异常收尾；`bridge.py` 终态登记；必要的新策略进 `src/creo_mechdog/failed_model_cleanup.py`；新建 `tests/unit/test_failed_model_cleanup.py`、`tools/test_failed_model_cleanup.py`。

**接口：** 原生报告 `failed_model_cleanup={attempted,status,reason,erase_code,absence_verified}`；status 区分 erased/skipped/failed/unknown，查询没执行时不填成功。已有 rollback 字段保留旧语义，清理不是恢复保存检查点。

- [ ] 先复现“新建→sketch失败→无保存→同名再次新建冲突”，记录对象身份、会话引用及是否有窗口；与预存名称冲突单列。
- [ ] 回归覆盖预存同名、用户修改/打开窗口、装配引用、擦除失败、absence 查询失败、unknown_outcome；这些对象不得被通用清理误删。单测用隔离桩，实机不对用户对象注入故障。
- [ ] 在原锁内、身份和依赖再核对后清理本 job 新建的孤儿；无证明就保留并回报。不得借助 erase_all、清 unknown、接管任意未保存对象或无条件重试。
- [ ] 专项 unittest 通过后实机验证隔离夹具：失败对象确认消失、同名可再次新建、原模型及已有文件不受影响；已保存模型失败仍正常回滚、revision 不变。

**通过条件：** 同名复用不再依赖改名绕过；失败/未知清理能明确报告并保留保护。新增结构归 MINOR。

### Q04：N1 阶段真实性与 N2 busy 建议间隔

**文件：** `bridge.py` 的 toolkit_lock/run_job/get_job/compact_job、`server.py` 现有 busy 回包（只改协议映射，业务留包内）、`generic_bridge.py` 的原生终态处理（仅确有必要时改）、`capabilities.py` 相关文案；新建 `tests/unit/test_job_stage_reporting.py`，扩展 `tests/unit/test_toolkit_channel.py`。锁所有权仍在 bridge.py，不新建第二套锁实现。

**接口：** 终态 stage 优先真实 failed_stage；没有来源时保持最后已知阶段。保留原 blocking_*，busy retry_after_seconds 首版为 5，文案明确为建议间隔；不引入 stage_history 或耗时预测 API。

- [ ] 用隔离 job/log 构造“connect失败但 runner已标后续阶段”“成功后disconnect”“失败后rollback”三例，先令错误阶段回归失败。
- [ ] 修改终态发布与读取，使 compact/full 一致；缺/截断日志和旧 job 兼容，不能将 disconnect/rollback 当主要失败阶段。
- [ ] 为 busy 添加 owner已知/未知、session_status 与建模占用、释放边界的回归；确认立即拒绝、不创建被拒作业、不触发后台重试。
- [ ] 运行 `python -m unittest tests.unit.test_job_stage_reporting tests.unit.test_toolkit_channel -v`；受控 MCP 验证只能由实机负责人安排，不能靠串行调用宣称真实并发通过。

**通过条件：** 进度不显示未到达阶段；busy 指引不被描述为完成 ETA。若终态语义或字段有扩展，由 Q15 按发布规则归 MINOR。

### Q05：三点定面

**文件：** `src/creo_mechdog/references.py`、`schema.py`、`native/generic.cpp` 的 datum_plane/resolve、工具签名/能力说明；新建 `tests/unit/test_datum_plane_through_points.py`、`tools/test_datum_plane_through_points.py`。

**接口：** `datum_plane.reference={kind:'through_points',points:[label_a,label_b,label_c]}`；三个已有 datum_points 特征各自唯一 PRO_POINT。angle/axis/非零 offset 与此形式互斥；旧有缺 kind 拒绝、angle+offset 拒绝保持。

- [ ] 先补 schema 正反例：2/4 点、重复标签、空值/bool、未来引用、错误特征类型、多点特征、角度/偏移混用。原包无 kind 写法应经明确转换，不能原样放行。
- [ ] 原生回读点坐标、单位与唯一性，拒绝共线/重复/无法判定的三点；近共线条件的容差与尺度说明记录入工作卡，不以固定世界坐标大小猜测。
- [ ] 原生创建后验证三点到平面距离、法向与叉积方向等价性、特征引用；失败前后的 revision/特征集合不变。
- [ ] 运行专项 unittest；实机覆盖主平面、斜面、大/小尺度、点序颠倒、错误引用以及保存擦除重载。原报告 normal/origin 仅作旁证。

**通过条件：** 独立入口/plan 同契约；Q06 可引用真实三点平面，不代表草图已可创建。

### Q06：任意斜面草图 L1/L2

**文件：** `native/generic.cpp` 的 sketch/project/redefine/frame/anchor，`native/geometry.cpp` 的错误收集；`src/creo_mechdog/operation_results.py`；扩展 `tools/test_tilted_sketch_lifecycle.py`、`tools/test_dev048_plane_frame.py` 和对应 tests/unit；新增原案夹具，避免另造相同驱动。

**接口：** CompleteFeature 失败应保留 API、code、element/type/error、失败阶段及原始 section 错误；有界样本上限 20，缺失明确 unavailable。新诊断与 Q01 字段兼容。Q02 的偏差比较必须使用同一真实帧。

- [ ] 先用现有旋转/偏移平面复现非三点斜面，再用 Q05 转换后的 smoke 原案；区分 frame 校验、UV 写入、SectionRegenerate、CompleteFeature 四阶段。
- [ ] 检查现有 `geometry.cpp::errors()` 已有遍历与 `last_feature_errors`；找 CompleteFeature 的实际丢失点，补透传而非重新声称“此前没有 ProErrorlist”。
- [ ] 验证 identity 合法 XY、平移 XY、主平面 YZ/XZ、±54°、三点斜面、反向 U、编辑/重载；用世界↔section 往返点、法向、实际曲线位置验证映射。不要直接粘贴外部 identity-only fallback。
- [ ] 对 L2 依据真实 element 错误定位 anchor/参照序列/再生等条件；保留 BUG-087 的非平行参照修复。未复现时交付跨环境条件和缺证，不能改旋转符号猜根因。
- [ ] 专项单测与旧倾斜工作流通过后，实机验证三角草图成功、9.87 mm 对称拉伸体积、朝向/位置、就地编辑、失败恢复和保存重载。

**通过条件：** L1 坐标正确与 L2 特征完成分别有证据；只有日志 UV 正确不算修复完成。若 L2 仍未定因，Q11 实机保持受阻。

### Q07：G5 可行性与接口冻结

**文件：** `docs/work-items/FEAT-009.md`、`FEAT-039.md`，新建 `docs/development/G5-NATIVE-CONTRACT.md`；核 `native/surfaces.cpp`、`blend_create.cpp`、`tools/generate_constants.py` 与本机匹配 SDK。实验驱动新建 `tools/test_g5_native_probe.py`，默认离线。

**接口：** 交付 Q08–Q10 共用契约：sections 顺序、quilt/curve 引用唯一性、方向坐标系/单位、keep_side、真实测量、引用重载稳定性及错误/回滚；逐字段写清 schema 和实际原生树。此文档冻结后才能实现公开 op。

- [ ] 对照正式 SDK 声明/本机头与示例核每个 element/feature form/API；不硬编码反馈里的数值 ID，不复制 constants.inc。
- [ ] 在获准的串行实机窗口做三个独立最小原生探针；比较实际创建树/抽取树、再生与重载，分别记录“可行/路线不成立/未验证”。不能只编译通过。
- [ ] 冻结第一版能力：surface_loft 先两条截面、straight；smooth、closed、连续性未测则不公开。project_curve 先一个目标 quilt 与显式投影方向；surface_trim 明确工具和保留区域，不按 GUI 猜正负侧。
- [ ] 冻结返回字段：loft `surface_area_mm2`；project `curve_length_mm` 与 `endpoints_mm`；trim `area_before_mm2/area_after_mm2/kept_side`；单位查询失败为 null+原因。共享测量/引用 helper 由此任务指定唯一所属文件与维护人。
- [ ] 评审契约和最小几何 oracle，列出 Q08–Q10 的确切函数/模型名称后交接；有一项不可行时只阻断依赖它的任务，不用 body 布尔替代 quilt 语义。

**通过条件：** 每项有 SDK 与真实原生证据；开发者可按契约写出唯一合理实现。正式公开 API 的具体模型/函数名由该调查结论确定，而非照抄未经证明的外部树。

### Q08：曲面放样 surface_loft

**文件：** `src/creo_mechdog/schema.py`、`references.py`、`native/surfaces.cpp`，必要时新增 `native/surface_loft.cpp`；仅在 `generic.cpp` 接入分派；能力/结果投影同步。新建 `tests/unit/test_surface_loft.py`、`tools/test_surface_loft.py`。

**接口：** 消费 Q07 冻结契约；产出 `surface_loft` op、可重载的 quilt 引用和真实面积。不改 `creo_loft` 现有实体路径。

- [ ] 先写非空两截面、截面类型/引用、顺序、非法枚举、来源不可用的 schema 与投影回归；未支持 smooth/closed 明确拒绝。
- [ ] 实现已证明的原生树、资源释放、特征标签与统一事务结果；不要求任意非平行截面都成功。
- [ ] 以两条平行直线生成矩形曲面核解析面积，以扭转截面核独立几何/面积对照；显式声明有效截面范围。
- [ ] 运行专项单测、原生构建与实机驱动；核曲面类型、无意外实体体积、编辑或下游引用、失败回滚和保存重载；回归原 solid loft。

**通过条件：** 已支持输入创建真实曲面并可供后续引用；不能以曲面拉伸代替任意放样。

### Q09：投影曲线 project_curve

**文件：** `src/creo_mechdog/schema.py`、`references.py`、`native/surfaces.cpp`，必要时新建 `native/project_curve.cpp`；结果投影与能力；新建 `tests/unit/test_project_curve.py`、`tools/test_project_curve.py`。

**接口：** 消费 Q07 的 quilt/source/direction_ref 与正负侧契约；产出稳定曲线引用、长度、端点；不得仅返回输入曲线信息冒充投影测量。

- [ ] 覆盖目标非 quilt、多个候选 quilt、空/错类型来源、方向不合法/零向量、反向、未相交、失效引用和单位未知的回归。
- [ ] 先用现有曲面 extrude 建平面/圆柱对照，独立验证曲线确实落在目标面、长度和端点，再接 Q08 曲面。
- [ ] 实现实际已验证的选择与元素树；查询失败保留原码，不选择第一片 quilt 猜结果。
- [ ] 专项单测和实机通过后，核保存重载后的引用、下游 trim、失败回滚与 revision。

**通过条件：** 方向、目标、曲线真实性均有证据，Q10 不依赖不稳定的临时 ID。

### Q10：曲面剪裁与加厚测量

**文件：** `native/surfaces.cpp`（必要时新建 `native/surface_trim.cpp`）、schema/references/operation_results/capabilities；新建 `tests/unit/test_surface_trim.py`、`tools/test_surface_trim.py`，复用 `tools/test_surface_features.py` 回归已有 thicken/solidify。

**接口：** 消费 Q07/Q09 契约；产出保留侧、真实面积前后值和可供已有 thicken 的 quilt。thicken 如补体积差，字段统一为 `volume_before_mm3/volume_after_mm3/volume_delta_mm3`，不改已有对称加厚语义。

- [ ] 先覆盖 keep_side 互换、非相交/切线、错误工具、多个区域/孔环、失效引用与面积测量失败；未支持多区域要明确拒绝。
- [ ] 矩形曲面用直线二分，正反保留侧面积之和等于原面积；再做闭合工具保留内/外区域对照，不允许两侧产物相同却回报成功。
- [ ] 接 Q08/Q09 执行真实曲面链，确认重载后可加厚；平面夹具核体积=面积×厚度，曲面场景用独立测量而非一律套该公式。
- [ ] 运行专项单测、已有曲面回归及本次实机，验证保存重载、回滚、引用稳定和 revision。

**通过条件：** 面积与保留区域符合定义，加厚成功是实际实体；不能只凭 op success 或输入回显验收。

### Q11：扭叶片 P12 配方规范化与分级验收

**文件：** 新建 `tools/convert_p12_feedback.py`、`tests/unit/test_p12_recipe_conversion.py`、`tools/test_p12_blade.py`、`docs/development/P12-BLADE-ACCEPTANCE.md`；可执行示例进 `examples/`，保持原反馈 JSON 不变。

**接口：** 离线转换器 `convert_recipe(tree: dict, *, route: str) -> dict` 返回 manifest：`status`（ready/blocked）、`source_sha256`、`source_seq_map`、`operation_count`、`batches`、`unresolved` 和近似声明。每个 batch 含 `batch_id`、`depends_on`、`operations`（≤200）。格式非法抛 ValueError；未解析字段/未知 op 列入 unresolved 并置 blocked，不静默丢弃，blocked 产物不得提交。route 的支持值先在工作卡冻结；转换器只做离线转换，驱动逐批提交且等待终态，不把整份 manifest 交给 execute_plan。

- [ ] 逐项核 391 条与 recipe=196 的口径差异。原树有 96 个含3点的 datum_points，其后的 thru_points 引用的是 p_a/p_b/p_c 点名，不是特征标签：须拆成3个单点特征，以 `(来源特征label,点名)` 为映射键生成全局唯一且≤28字符的新标签，并在所属组范围改写三点平面和后续依赖。只拆点时应为 **583 操作**；转换其他占位后再次统计。回归断言不同带的重复点名不会串引用。
- [ ] 展开 triangle_uv/plane label 等占位；merge_all_bodies 无现有等价时列入 unresolved，不编造受支持 op。family_table 80项的索引映射需来源证明，不能按遍历序猜。保留树中厚度 `9.87008714331235` 的来源精度，不一律替换为 smoke 的 9.87。
- [ ] 核最长标签与载荷体积；当前 `schema.py::validate_operations` **每计划最多 200 操作**，391条及展开后操作必须按真实依赖分批。等待每批终态后用最新 revision 续编；部分完成/失败不自动重提整批，也不为此放大既有上限。
- [ ] 先独立计算每条三角棱柱的面积与厚度体积，明确 48带/96三角的具体数量；存在交叠时不能直接相加成最终并集体积。
- [ ] 一条带→四条带→全叶片逐级实机；每级核实际扭转、厚度、bbox、体积、特征数、保存重载与失败恢复，再接轮毂/阵列/装配。
- [ ] 正规链另用 Q08–Q10→thicken 验收；138629.77、62231.97、614234.967 等外部锚值只有在完整 v1.2 来源/单位/几何口径一致后才设硬断言。原始 TXT 缺失时明确“按现有包重建”，不声称原任务完整符合。

**通过条件：** 配方可以真实执行且近似误差可解释；逐带路线与正规曲面路线分别报告，不以外形相似认定等价。

### Q12：装配按族上色已交付，不再派开发

**状态与证据：** [FEAT-052 工作卡](../../work-items/FEAT-052.md)、[0.11.0 版本说明](../../RELEASE_NOTES_0.11.0.md)、[发布记录](../../validation/RELEASE-0.11.0.md)。发布提交 `262ef20`，远端核验回填 `2f6aab7`；当前 95 个公开工具。原 [上色计划](2026-10-31-assembly-recolor-plan.md) 保留接口与历史方案，已由实际实现/验收取代其旧“等待实施”状态。

- [x] 主干已含 `creo_recolor_assembly`、`recolor_assembly` op、组件三态 appearance 与完整注册；只支持 MCP 受管单层装配。
- [x] 本机 Creo 12.4.0.0 / 匹配 SDK 实机 run `assembly_appearance_live_20261101T060336Z558b3546`：80组件/12族、28/28检查通过；自动/显式分族、复涂、身份/姿态/约束、源件哈希不变、保存重载与两种外观基线回滚均有证据，另有发布记录所载 pipeline/T07 指定回归；T07 总判定不代表 P11 的 skipped_no_geometry 状态已交付，原报告 empty_part 预览仍失败，差异见 DEV-054。
- [x] 0.11.0 正式 Release、标签与四附件远端逐件核验已在仓库记录；本次只读引用，未重新联网核验或改发布附件。

**尚未验证：** WorkBuddy 纯 MCP 黑盒、真实 busy/并发交错、Creo 9/10；dry_run 分页/游标、非法输入与读回错误注入是离线证据。独立零件、面级、嵌套及外部装配不在已交付范围。此处留作验收/能力边界，不把未测项升级成已通过，也不自动新增扩展开发任务。

### Q13：F 大回包与 H 装配预览

**文件：** `src/creo_mechdog/operation_results.py`、`src/creo_mechdog/preview.py`、`bridge.py` 的 compact/full 投影、`native/preview.h`、相关工具描述；新建 `tests/unit/test_large_plan_result_budget.py`，扩展 `tests/unit/test_t07_preview.py` 与 `tools/test_t07_preview.py`。

**接口：** compact/full 的既有 detail/分页语义保持；新增操作必须经同一有界投影。以 UTF-8 序列化结果≤32 KiB 为 compact 设计目标，保留总数与截断标记；full 采用项目已支持的分页/引用机制，不无上限回显输入。

- [ ] 从当前真实 MCP 载荷构造 40+操作、81点轮廓、80组件与多错误结果，测实际字节而非字符数；本轮 F 未复测，先确认是否仍超限。
- [ ] 给 operation_results 的新诊断/颜色/曲面结果设有界摘要；不能截断总数、失败原因、revision、回滚或保存重载证据。full 缺页应可继续获取。
- [ ] H 与 Q01 的“空件预览状态”分开：在模型正确、非空装配上验证 datums 遮挡，若提供隐藏基准预览须临时应用并恢复原显示状态，失败也恢复，不默改用户全局 config。
- [ ] 单测核预算、分页一致与错误保留；实机核目标窗口、显示效果、恢复状态及已有预览回归。

**通过条件：** 大回包可控且信息可检索；空件 skip 状态不能冒充解决“基准遮挡”。

### Q14：B/C/G 未复测项先调查

**文件：** Q00 归档映射、相应工作卡，现有 `native/sketch_coordinates.cpp`、`native/generic.cpp` round/frame、`src/creo_mechdog/schema.py`；先做最小夹具与调查文档，禁止一次顺带大改三个子系统。

**接口：** 每项独立输出“现行契约/原始输入是否齐备/复现条件/真实结果/是否需要下一实施任务”。只在有具体证据时拆出独立修复提交。

- [ ] B：核凹圆棱 round 的 face/edge 选择、半径与几何条件，用明确目标棱构造最小正反例；无原案就记替代验证。
- [ ] C：coordinates 当前明确不支持 spline，这是能力扩展；评估控制点/插值点、驱动约束及求解后保真，不能靠去掉 schema 限制或悄悄 autodim 宣称支持。
- [ ] G：定位所报正交性闸究竟是 rotation_matrix 还是 frame 方向。当前 rotation_matrix 校验的是单位正交矩阵；不能为放行“方向向量”而统一归一化所有矩阵，吞掉缩放/剪切/反射。用单位/等比例方向、近零、非正交与 det=-1 分类验证。
- [ ] 将有证据的问题/能力缺口登记原或新 ID，分别给出下一小任务的输入、输出、测试与文件；无证据不写“修复完成”。

**通过条件：** B/C/G 各有可执行的结论，不再把上一轮建议直接当本轮已证缺陷。

### Q15：集成、发布与黑盒交接

**文件：** 本批工作卡/能力说明/版本说明/发布证据，`version.py`、双种子清单与 `docs/seed_package.json` 等按 RELEASING 更新；不在功能 agent 分支分别改版本。

**接口：** 每个功能 agent 交付固定ID、提交、dirty/指纹、输入、预期、真实结果、专项命令、未测范围及候选集成顺序。集成人是共享 schema、capabilities、server 注册与 native/generic.cpp 冲突的唯一裁决人。

- [ ] 按实际交付小批集成；首选已有 MINOR 收口与 P1 正确性，不等待整个 G5/P12。0.11.0 已发布，不得复用。新 MINOR 可暂按 0.12.0 讨论、独立 PATCH 可暂按 0.11.1 讨论，均须发布前核号；不回到旧 0.10.x 开新主干版本。
- [ ] 离线先跑各专项，然后在仓库根运行 `.\.venv\Scripts\python.exe tools\dev_check.py`；不自动重建 style baseline。检查失败需修复或明确受阻，不能沿用历史总数。
- [ ] 冻结源码后用 `.\.venv\Scripts\python.exe bridge.py build`；同一实机负责人按已确认会话条件串行跑受影响驱动。驱动默认离线，live 必须显式 `--live --confirm-session-usable` 并具备实际准入证据。
- [ ] 先最小夹具再原案；unknown/通信异常立即停止新提交。保存重载、真实几何、revision/回滚任何一项缺失均不能计成功。原始 job/log、worker hash、源码指纹、环境写入新运行目录。
- [ ] 为已完成能力单独写 WorkBuddy 提示词：只给 MCP 输入/场景/预期/报告要求，不要求看源码/Git/配置或跑本地测试；版本/环境只能从公开接口确认，不可见项记无法确认。是否执行由用户安排，不设额外发布门槛。
- [ ] 按 `docs/development/RELEASING.md` 同批合 main、正式 Release、主干标签、种子与源码两包及 sidecar；用正式附件核验哈希并回填链接。失败继续补齐，不以“已合 main”结束。

**通过条件：** 能力、台账、版本与实际发布一致；已交付/待实机/原案缺件/路线不可行/外部未验分别列出。

## 四 并行边界与可复制派工提示词

- 不同 agent 不在同一 checkout 修改同一文件；优先复用已认领且合适的 worktree，新 worktree 按宿主工具创建。FEAT-052 工作树含测试数据，不能当空目录重建/接管；本地清理结果见 DEV-054。
- `schema.py/references.py/capabilities.py/server.py/operation_results.py/native/generic.cpp` 是冲突热点。功能 agent 在隔离分支交付小差异；共享 helper 在 Q07 冻结归属后复用。由集成人顺序集成，不能多人同时在主工作区改。
- 实机不是多个 agent 的并行任务；包括 session_status 等会占用通道的探测也由同一人安排。不要后台重建正在运行的 worker。
- 预计复杂度：Q00/Q04 为小到中；Q01/Q02/Q03/Q05/Q06/Q13 为中到大，Q12 已交付不再估开发工作量；Q07–Q11 为研究驱动，先用证据决定下一步，不沿用外部“0.5天无风险”的估计。

将下面内容的 Qxx 换成表中任务号即可派发：

```text
请处理 E:\Projects\MCP_CREO_MechDog\docs\superpowers\plans\2026-11-01-feedback0100-agent-dispatch.md 中的 Qxx。
先读该计划、关联 Spec、仓库 AGENTS.md/DEVELOPMENT.md/BACKLOG 和该任务的来源材料。
仅做 Qxx 的范围；先核当前版本、既有提交、工作树、认领和固定 ID，Q00 登记前不写产品代码。
保护其他 agent 的改动，不修改已发布标签/附件，不自行合 main、改版本或发布。
可自主完成离线复现、实现、专项回归与文档；原生实验/构建/实机须交给统一负责人安排，先核 BUG-001/BUG-091 条件。
不连接/重启/结束 Creo，不清 unknown；不自动重试已受理请求。若你被单独指定为实机负责人，仍须先满足仓库准入。
反馈里的补丁/数值只作来源，按当前源码与真实返回验证；原案缺件、不可行和未测如实报告。
交付：固定ID、修改文件、提交、受测源码指纹/dirty、专项命令及结果、原始证据路径、剩余范围、交给下一任务的接口。
```

## 五 本轮计划自检

- [x] 来源覆盖：00总览、01 A–H/N1–N3/正面观察、02 G5、03/04 L1/L2及补丁、05 ZIP、06四个JSON均有任务归属。
- [x] 版本去重：当前 0.11.0 / 95 工具与旧 0.10.1 范围分开；Q12 已交付，P07/P08/P11 仍是开发态；旧 BUG-094 与新 L1/L2、两个 P12 各自分开。
- [x] 接口一致：Q07 冻结后 Q08–Q10 消费；Q11 不提前承诺未经证明的树；Q12 以实际工作卡/发布证据为准，不再派开发。
- [x] 审查风险：偏差/误擦除/帧/引用与保留侧/大回包分别有负责任务与反例。
- [x] 执行边界：初版只编计划；本次 DEV-054 只做文档对账和本地冗余清理，未实施其余产品任务、未运行产品测试、未连接 Creo、未提交或发布。Q12 的测试/发布是此前独立任务的证据。
