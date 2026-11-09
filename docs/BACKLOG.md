# 统一开发台账

2026-11-08：[DEV-076](work-items/DEV-076.md)在当前分支合入本地v0.18.4并修三件反馈。标签导入时实际表行为166（原文167偏大1）；新增本卡后实际为167，不是沿用错误数字。该句为DEV-076时点，尚未合main或发布。

2026-11-08：本分支合并已发布的 [v0.19.0](validation/RELEASE-0.19.0.md)（DEV-074 曲面与整链批），保留 DEV-076/DEV-077 与另一 AI 的工作树改动；本分支自身仍未合 main、未发布。

2026-11-08：[DEV-077](work-items/DEV-077.md)对比下载目录0.18.2的四份反馈，归档原件、回填RELEASING逐ID表与POSTCHECK v0.18.2四附件数据、补台账计数门禁及两项离线诊断修复；新增本卡后当前表行为168。未完成项见[接手清单](development/DEV-077-HANDOFF.md)。同样未合main或发布。

2026-11-08：DEV-076/DEV-077 的 0.19.1 子项已合入 main 并发布 [v0.19.1](validation/RELEASE-0.19.1.md)：worker 构建身份/`surface_loft` 动态准入、overlap 预算/覆盖诊断、trim 结果句柄与连续 trim、`rotation_tolerance`、`get_job` 300 s、`known_limitations`/`plan_examples`；公开工具仍 107。R01—R08 剩余项与未测范围见[DEV-077-HANDOFF](development/DEV-077-HANDOFF.md)。

2026-11-08：[DEV-079](work-items/DEV-079.md)归档下载目录0.19.0的三份Creo 10反馈并完成离线补漏：quilt_merge公开描述、曲率默认摘要/`include_samples`、surface_group结构化失败回执、`profile.method`与POSTCHECK旧句；新增本卡后当前表行为170。随 0.19.2 发布（提交`df8e178`，[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.2)），四附件核对 exit 0；Creo 10原生能力与钣金余项见[对照表](validation/feedback-0.19.0-2026-11-08/MAPPING.md)。

2026-11-08：[DEV-080](work-items/DEV-080.md)接手上述三份报告复核后仍未闭环的H01—H09及未编号缺口；首批离线收口为手写TU头门控契约测试、COMPATIBILITY缺头降级说明、台账计数自检进CI；新增本卡后当前表行为171。开发分支`codex/DEV-080-feedback-0190-followup`，未合main、未发布；原生/实机项按依赖留卡。

2026-11-09：按用户决定修订本机实机测试放行条件，[BUG-001/FEAT-018 工作卡](work-items/BUG-001-FEAT-018-RECOVERY.md)追加「用户明确确认后即可用 Creo 进行实机测试」，不再以卡死根因核对/事前会话可操作判定为阻断前置；根因未定、历史失败与恢复原件仍逐字节保留，安全底线（不擅自结束Creo/清锁或unknown保护、故障注入需单独授权）不变，确认按次生效。当前规则见 [AGENTS.md](../AGENTS.md) 与 [DEVELOPMENT.md](DEVELOPMENT.md)。本条为规则修订，不新增ID、不改计数（仍172），未合main、未发布；本轮未据此执行任何 Creo 实机测试。

2026-11-09：[DEV-081](work-items/DEV-081.md)归档第四份0.19.0反馈（护卫舰重建，报告P1—P11映射F01—F11），建立[MAPPING](validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md)与[离线批次实施计划](superpowers/plans/2026-11-09-feedback0190-frigate-offline.md)；A批离线六项（F02/F03/F07/F04回执/F11文档契约/F05限制说明）已交付并逐任务独立审查，统一dev_check通过。同日补[B/C批子计划](superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md)与 WorkBuddy 黑盒提示词，实机/黑盒仍未执行；[DEV-080](work-items/DEV-080.md)首批离线收口与台账一并提交。新增本卡后当前表行为172；本批不改公开工具签名、未连Creo、未编译原生、未合main、未发布。

建立：2026-10-13；最近复核：2026-11-08（[DEV-074](work-items/DEV-074.md) 0.19.0 发布准备；本分支叠加 DEV-076/DEV-077）。本文件是唯一当前台账，按“开发入口 → 本表 ID → 工作卡当前摘要 → 相关源码”读取，历史证据按需打开。当前源码版本以 [version.py](../version.py) 为准；逐版交付记录见 [版本说明目录](../README.md) 与 `docs/validation/RELEASE-*.md`，不在本表重复回填。

DEV-073 以 `1cf9d3f` 为基点整理台账，随后并入 0.18.0 发布提交（[RELEASE-0.18.0](validation/RELEASE-0.18.0.md)）。0.18.0 已发布的结论以该发布记录与远端 Release 核对为准。DEV-074 的 0.18.3 子项交付以 [0.18.3 发布记录](validation/RELEASE-0.18.3.md)为准，0.18.4 子项以 [0.18.4 发布记录](validation/RELEASE-0.18.4.md)为准，0.19.0 子项以 [0.19.0 发布记录](validation/RELEASE-0.19.0.md)为准；两版发布状态来源和空白字段勘误以[统一POSTCHECK](development/RELEASE-POSTCHECK-2026-11-07.md)及其所链新勘误为准。

## 使用与计数

每个 ID 仅一行，保留优先级、当前状态、剩余工作和工作卡入口。目标版本统一表示剩余范围的安排，已交付子项版本/日期保留在工作卡；未分配的新工作不继承旧已发布目标。无独立卡的存量 ID 链接至完成档案的原登记，本轮不批量补卡。

诊断交付不等于根因修复；部分交付不关整卡；缺其他版本证据不自动判未修。观察项等自然新现场，不制造故障。已完成且无保留范围的行移入 [完成档案](BACKLOG_COMPLETED.md#2026-11-07dev-073-归档与历史进展)。原进展/证据保留日期，不再回填第二份待办。小修复沿用卡与证据，复杂跨模块任务才另建完整计划。

当前唯一 ID **172**（BUG **75**、FEAT **61**、DEV **36**）；2026-11-07整理时移入完成档案23项（含DEV-073、DEV-075），该句为历史时点，归档项不计入当前行数。DEV-077起运行 `python tools/check_backlog_counts.py` 自检声明行、表行与分类表三方计数，不一致exit 1；该脚本只校验计数，不替代逐ID人工核对。

| 当前分类 | 唯一 ID 数 |
| --- | --- |
| 仍需修复 | 4 |
| 待复现/待核实 | 31 |
| 已有修复但待验收 | 27 |
| 观察中 | 3 |
| 其它 agent 处理范围 | 20 |
| 开发中 | 6 |
| 部分交付，剩余待验收 | 37 |
| 部分交付，剩余待规划 | 2 |
| 待规划 | 42 |

BUG 分类是互斥主分类；“其它 agent”行仍写明已完成子项与真实缺口，勿重复派工。

## 仍需修复

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-017](work-items/BUG-017.md) | P1 | 仍需修复 | 未排期 | 取得外部最小输入及 Creo 9 原生失败码，定位并修复或明确支持边界；现有修复仅覆盖子项，原案/规则未闭环。 |
| [BUG-020](BACKLOG_COMPLETED.md#legacy-bug-020) | P2 | 仍需修复 | 未排期 | 列明产物/诊断附件，仅清理本作业 *_out.log.N，验证用户文件不受影响；依赖：离线可先取导出路径与作业文件归属；最终需真实 STEP 导出。 |
| [BUG-034](work-items/BUG-034.md) | P1 | 仍需修复 | 未排期 | 定位种子生产版本及原生加载失败，决定可追溯重生方案；依赖：需 Creo 9 SDK/许可与种子来源。 |
| [BUG-036](work-items/BUG-036.md) | P1 | 仍需修复 | 未排期 | 核对实际约束、求解调用与 transform，修正写侧或给出明确拒绝；现有修复仅覆盖子项，原案/规则未闭环。 |

<a id="输入或规则待核实"></a>

## 待复现/待核实

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-004](BACKLOG_COMPLETED.md#legacy-bug-004) | P1 | 待复现/待核实 | 未排期 | 核对对象句柄、种子身份、直线/平滑/三截面编辑和重载；依赖：需可用 Creo 12 会话与原始失败输入。 |
| [BUG-011](BACKLOG_COMPLETED.md#legacy-bug-011) | P1 | 待复现/待核实 | 未排期 | 取得状态查询与提交时间线，标明快照时间及实时性；依赖：需真实异常通道现场；禁止主动制造。 |
| [BUG-012](BACKLOG_COMPLETED.md#legacy-bug-012) | P1 | 待复现/待核实 | 未排期 | 区分未尝试/成功/失败/未知；核对新件无检查点和旧字段兼容；依赖：需失败样例与当前回执对照。 |
| [BUG-014](work-items/BUG-014.md) | P1 | 待复现/待核实 | 未排期 | counts=null 与后续查询有值的时点/来源差异及恢复失败路径仍待核对。 |
| [BUG-015](BACKLOG_COMPLETED.md#legacy-bug-015) | P2 | 待复现/待核实 | 未排期 | 以真实 body ID 做干净件/组合件保存重载对照，定位保存阶段；依赖：t30_probe 模型、原生返回与 Creo 会话。 |
| [BUG-016](BACKLOG_COMPLETED.md#legacy-bug-016) | P2 | 待复现/待核实 | 未排期 | 核对 side、工具面与切除语义，做双侧几何、体积及重载对照；依赖：原报告操作输入及 Creo 可用会话。 |
| [BUG-018](BACKLOG_COMPLETED.md#legacy-bug-018) | P2 | 待复现/待核实 | 未排期 | 逐输入结果契约已实施；历史 effect/status 矛盾需按当前返回核对，关联 T02/T13。 |
| [BUG-031](work-items/BUG-031.md) | P1 | 待复现/待核实 | 未排期 | 先建并查询唯一 x=45 平面，再与显式 ID/标签对照；依赖：需 Creo 几何对照。 |
| [BUG-035](work-items/BUG-035.md) | P1 | 待复现/待核实 | 未排期 | 补 shell+孔夹具，对照轴阵列与树依赖、材料体积；依赖：缺完整原模型/leader 历史与 Creo 实机。 |
| [BUG-037](work-items/BUG-037.md) | P1 | 待复现/待核实 | 未排期 | 测尺寸类型×引用数量及端点矩阵；依赖：缺完整草图请求与 Creo 9/12 对照。 |
| [BUG-039](work-items/BUG-039.md) | P2 | 待复现/待核实 | 未排期 | 与 extrude 对照原生 body ID、材料、体积、重载；依赖：曲面来源、厚度、侧及原 job/model。 |
| [BUG-041](work-items/BUG-041.md) | P2 | 待复现/待核实 | 未排期 | 先定普通约束非零 offset 契约，再加准入拒绝或显式转换，验证面距及保存值；依赖：原始约束输入/回读，或构造最小对照的 Creo 会话。 |
| [BUG-048](work-items/BUG-048.md) | P2 | 待复现/待核实 | 未排期 | 补等价特征序列并隔离镜像、顺序、变换和壳引用，取得原生诊断；依赖：原模型、引用、job；可用 Creo 会话。 |
| [BUG-049](work-items/BUG-049.md) | P1 | 待复现/待核实 | 未排期 | 原件取得后同件 gap/snapped 对照，确认多环支持边界；依赖：缺 gear10.json/sketch_entities.json。 |
| [BUG-052](work-items/BUG-052.md) | P2 | 待复现/待核实 | 未排期 | 以已知几何查询 Toolkit 返回语义，再设计兼容的 geometry_type 字段；依赖：平面/圆柱等原生夹具与 Creo 查询。 |
| [BUG-053](work-items/BUG-053.md) | P1 | 待复现/待核实 | 未排期 | 同一快照分段计时及调用计数后再选优化；依赖：缺大模型样本与阶段日志。 |
| [BUG-058](work-items/BUG-058.md) | P1 | 待复现/待核实 | 未排期 | 只在自然现场采集进程、窗口和通道时间线；依赖：需外部 Creo 9 无主窗口现场。 |
| [BUG-060](work-items/BUG-060.md) | P2 | 待复现/待核实 | 未排期 | 核对 schema/resolve 接受的引用类型，明确报错或扩展支持，验证重载；依赖：原始 S6 输入、固定面选择规则与 Creo 会话。 |
| [BUG-061](work-items/BUG-061.md) | P2 | 待复现/待核实 | 未排期 | 与 BUG-031 联查解析路径；明确接受或拒绝并给出 datum_plane 替代；依赖：用户契约决定与 Creo 几何对照。 |
| [BUG-063](work-items/BUG-063.md) | P1 | 待复现/待核实 | 未排期 | 取得外部轴引用形式/原模型并对照修复后 BUG-084；依赖：缺外部 Creo 10 原案。 |
| [BUG-065](work-items/BUG-065.md) | P2 | 待复现/待核实 | 未排期 | 保留 Creo 10 原案待复现；斜交与单平面回归依关联矩阵；依赖：外部原始模型与 Creo 10 环境。 |
| [BUG-066](work-items/BUG-066.md) | P2 | 待复现/待核实 | 未排期 | 取原 Part1/Part2、同作业请求及图像；实机逐图复核失真路径；依赖：原模型、preview.jpg、同作业 JSON。 |
| [BUG-075](work-items/BUG-075.md) | P2 | 待复现/待核实 | 未排期 | 下次自然出现时收集 worker 日志和时序，辨别探针异常/连接竞争；依赖：自然复发时原始探针日志。 |
| [BUG-078](work-items/BUG-078.md) | P1 | 待复现/待核实 | 未排期 | 偶发编辑 -1 未复现；三旧现场待选择 restore_baseline；依赖：现场日志/操作者。 |
| [BUG-081](work-items/BUG-081.md) | P1 | 待复现/待核实 | 未排期 | 自然现场验证 MCP 拒绝时序后决定 alive=None 规则；依赖：缺同型残留 worker/外部 Creo 9 现场。 |
| [BUG-085](work-items/BUG-085.md) | P1 | 待复现/待核实 | 未排期 | 自然事故时采集 nmsd 身份、worker 与源码指纹；依赖：缺原始时序和受控现场。 |
| [BUG-091](work-items/BUG-091.md) | P1 | 待复现/待核实 | 未排期 | 自然现场核对分层事实与外部时间线；依赖：缺真实断连/挂起现场。 |
| [BUG-102](work-items/BUG-102.md) | P1 | 待复现/待核实 | 未排期 | 取得报告方原 surface 69/中性面引用并做单变量对照；依赖：缺外部 Creo 10 原夹具/错误树。 |
| [BUG-106](work-items/BUG-106.md) | P2 | 待复现/待核实 | 未排期 | 文案已修；adopt_session_copy 只是候选，先裁定是否纳入本卡，再补同名模型实际链路。 |
| [BUG-108](work-items/BUG-108.md) | P1 | 待复现/待核实 | 未排期 | 在原 Creo 10 现场取得可复现平移及 accepted_rigid 实例，判断原点固定是否消除位移；现有修复仅覆盖子项，原案/规则未闭环。 |
| [BUG-109](work-items/BUG-109.md) | P1 | 待复现/待核实 | 未排期 | 自然现场取得子阶段时间线以定位阻塞；依赖：缺 Creo 9 真实停滞的 native.log/request.json。 |

## 已有修复但待验收

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [DEV-078](work-items/DEV-078.md) | P2 | 离线实现/检查完成；实机待验 | 未排期 | 四边双方向填充、独立角释放/quilt成形、多段flange全部门禁；Offset/PunchDie待真实样件，格栅待实测。3031单测与SDK12.4编译通过，见交接清单。 |
| [DEV-076](work-items/DEV-076.md) | P1 | 已有修复但待验收 | 未排期 | H13 worker构建身份/动态准入、H15 overlap预算/覆盖诊断、H16 trim结果句柄与连续trim已在Creo12.4实机通过；H14交线诊断、H17 Creo10直创原件、H18 Creo10同载荷、H19旧原件仍缺；Creo9/10与远端余项见接手H10—H19。 |
| [BUG-010](BACKLOG_COMPLETED.md#legacy-bug-010) | P1 | 已有修复但待验收 | 未排期 | 视图 scale=2 已有成功证据；位置更新、图纸保存重载/revision 仍未验。 |
| [BUG-013](work-items/BUG-013.md) | P1 | 已有修复但待验收 | 未排期 | 摘要/分页已有；模型查询精确32KiB及单项超限未验，不能复用 capabilities 结论。 |
| [BUG-019](work-items/BUG-019.md) | P2 | 已有修复但待验收 | 未排期 | 引用语法主线已验；计划/三入口公开终验仍缺，先核真实请求和部署。 |
| [BUG-028](work-items/BUG-028.md) | P2 | 已有修复但待验收 | 未排期 | 计划入口整数/字符串/混合草图引用的建模/重载待验，校验通过不等于成功。 |
| [BUG-029](work-items/BUG-029.md) | P1 | 已有修复但待验收 | 未排期 | 重排主矩阵及 no-op 已验；原模型重建/复杂多特征树仍待验证。 |
| [BUG-030](work-items/BUG-030.md) | P1 | 已有修复但待验收 | 未排期 | 尺寸编辑主线已验；原报告失败例与受影响回归仍需原件/实机。 |
| [BUG-040](work-items/BUG-040.md) | P2 | 已有修复但待验收 | 未排期 | 补扫掠后状态变化、compact/full、异常查询；保留非活动记录；依赖：原始 sweep job/native JSON；受控 Creo 会话。 |
| [BUG-047](work-items/BUG-047.md) | P1 | 已有修复但待验收 | 未排期 | 两方向折边已验；其它边/串连 flip 及回滚后合法折边还需矩阵。 |
| [BUG-057](work-items/BUG-057.md) | P1 | 已有修复但待验收 | 未排期 | 统一锁及本机三状态60轮已过；双进程200轮与 Win10/Python3.13 原环境待验。 |
| [BUG-062](work-items/BUG-062.md) | P1 | 已有修复但待验收 | 未排期 | centerline 核心两入口已验；保存重载全矩阵及其它构型按原卡保留。 |
| [BUG-072](work-items/BUG-072.md) | P2 | 已有修复但待验收 | 未排期 | 非毫米保护本机已验；公开复核待补，继续毫米准入与原件字节保护。 |
| [BUG-074](work-items/BUG-074.md) | P1 | 已有修复但待验收 | 未排期 | 历史身份停止证明已修；Windows 跨启动四动作与公开验收未齐，同次启动/未知仍拒绝。 |
| [BUG-076](work-items/BUG-076.md) | P1 | 已有修复但待验收 | 未排期 | 膨胀诊断/详情引用已修，阻断修复归 BUG-077；本卡真实零件全链路/公开复核仍待。 |
| [BUG-079](work-items/BUG-079.md) | P1 | 已有修复但待验收 | 未排期 | 就地改弧半径已修；非主平面/外部完整编辑矩阵仍未验。 |
| [BUG-080](work-items/BUG-080.md) | P1 | 已有修复但待验收 | 未排期 | 单位/变换本机实机及 A/B 已过；公开 WorkBuddy 第三轮仍缺，不代外部环境。 |
| [BUG-082](work-items/BUG-082.md) | P1 | 已有修复但待验收 | 未排期 | 主修复/外部 Creo 9 编辑已过；非主平面 autodim、贴轴基线及失败 revision 未齐。 |
| [BUG-083](work-items/BUG-083.md) | P2 | 已有修复但待验收 | 未排期 | Python 非法轴准入已修；原生 validate_revolve_axis 分支与外部原环境未验。 |
| [BUG-090](work-items/BUG-090.md) | P1 | 已有修复但待验收 | 未排期 | 厚度函数门控/实读回退已修；Creo 10 定向编译与运行待原环境，保持开放。 |
| [BUG-094](work-items/BUG-094.md) | P1 | 已有修复但待验收 | 未排期 | 本机已验，待原负责人交付裁定；−Z 扩展及外部原请求未验证；依赖：交付裁定；外部原请求/环境仅用于原案核对，不作全项目发布门槛。 |
| [BUG-098](work-items/BUG-098.md) | P1 | 已有修复但待验收 | 未排期 | 三点面阻塞已修并实机8/8；约束引用逐条核对仍未验证，保留数量校验安全边界。 |
| [BUG-101](work-items/BUG-101.md) | P1 | 已有修复但待验收 | 未排期 | 补圆弧端点支持并用 gear10 原案验证；依赖：缺 gear10.json 和外部 Creo 10 对照。 |
| [BUG-105](work-items/BUG-105.md) | P1 | 已有修复但待验收 | 未排期 | 回滚成功保持 ready 已验；派发前零变更及 ack_no_mutation 恢复失败态仍未实机。 |
| [BUG-107](work-items/BUG-107.md) | P1 | 已有修复但待验收 | 未排期 | 生成器门控已发布；本批DEV-076补手写surface_loft的Probbl.h门控与缺头实际编译回归。Creo9/10完整SDK/运行时未验，禁止用编译代替几何通过。 |
| [BUG-110](work-items/BUG-110.md) | P1 | 已有修复但待验收 | 未排期 | ack_failure 已实现；11/07 仍 guard_only，零件/装配成功确认分支未触发，待健康失败态夹具。 |
| [BUG-114](work-items/BUG-114.md) | P1 | 已有修复但待验收 | 未排期 | 新件清理/重建已验；新装配失败清理与终态作用域仍需实机，不放宽组件保护。 |

## 观察中

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-005](work-items/BUG-005.md) | P1 | 观察中 | 未排期 | 新现场再查；依赖：新现场。 |
| [BUG-021](work-items/BUG-021.md) | P1 | 观察中 | 未排期 | 朋友新反馈再查；依赖：新现场。 |
| [BUG-088](work-items/BUG-088.md) | P2 | 观察中 | 未排期 | Creo 10 原案再查；依赖：原始日志。 |

## 其它 agent 处理范围

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-003](BACKLOG_COMPLETED.md#legacy-bug-003) | P1 | 其它 agent 处理范围 | 未排期 | 与 FEAT-010 及反馈批对账；依赖：实机/原件。 |
| [BUG-032](work-items/BUG-032.md) | P1 | 其它 agent 处理范围 | 未排期 | green/white 面距、外部差异；依赖：外部环境。 |
| [BUG-045](work-items/BUG-045.md) | P2 | 其它 agent 处理范围 | 未排期 | 内核阈值扫描、外部 -2；依赖：健康会话/原报文。 |
| [BUG-046](work-items/BUG-046.md) | P1 | 其它 agent 处理范围 | 未排期 | revolve 与一体增料路线；依赖：原生方案。 |
| [BUG-050](work-items/BUG-050.md) | P1 | 其它 agent 处理范围 | 未排期 | 原切线闭环/53 mm 混合轮廓；依赖：原输入。 |
| [BUG-051](work-items/BUG-051.md) | P1 | 其它 agent 处理范围 | 未排期 | 完整原案与 coordinates 对照；依赖：原输入/日志。 |
| [BUG-064](work-items/BUG-064.md) | P1 | 其它 agent 处理范围 | 未排期 | surface 引用、无第二参照、外部原案；依赖：原件/实机。 |
| [BUG-084](work-items/BUG-084.md) | P1 | 其它 agent 处理范围 | 未排期 | 三引用等价与外部原案；依赖：原件/实机。 |
| [BUG-095](work-items/BUG-095.md) | P2 | 其它 agent 处理范围 | 未排期 | 本机已验，待原负责人交付裁定；报告方同面/同模型仍缺 request.json；依赖：request.json。 |
| [BUG-103](work-items/BUG-103.md) | P1 | 其它 agent 处理范围 | 未排期 | 四壁矩阵、UI 对照、外部差异；依赖：Creo 10 环境。 |
| [BUG-113](work-items/BUG-113.md) | P1 | 其它 agent 处理范围 | 未排期 | 外部 Backup/回滚原案；依赖：MCP/job/native/检查点。 |
| [BUG-115](work-items/BUG-115.md) | P2 | 其它 agent 处理范围（已交付 0.18.4 H12 回执复验子项） | 0.18.4（H12 子项已交付）；剩余未排期 | 原生 -4 根因、其它组合；依赖：原生机制。 |
| [DEV-054](work-items/DEV-054.md) | P2 | 其它 agent 处理范围 | 未排期 | 原负责人仍有本地维护记录未提交；分支/归档与发布状态核对由其继续，本批只对账。 |
| [DEV-067](work-items/DEV-067.md) | P2 | 其它 agent 处理范围 | 未排期 | A01/A03/B01/D02 已进入本地集成，A02 已交付；协调原负责人验收/发布，其它组未全实现。 |
| [DEV-069](work-items/DEV-069.md) | P1 | 其它 agent 处理范围 | 未排期 | chatgpt/0.17.1 反馈归原批负责人；保真、钣金增料/角部、原现场与发布后核对未闭环。 |
| [DEV-072](work-items/DEV-072.md) | P1 | 其它 agent 处理范围 | 未排期 | 代码及组合编译已有；原生诊断实机/保存重载、真实附件下载与 0.17.4 发布核对归原负责人。 |
| [FEAT-035](work-items/FEAT-035.md) | P2 | 其它 agent 处理范围 | 未排期 | 标准孔实现已进入本地集成；孔表/深度和扩展原生矩阵由原负责人收口。 |
| [FEAT-057](work-items/FEAT-057.md) | P2 | 其它 agent 处理范围（0.18.1 已交付密度/单位/缺失原因契约，离线） | 0.18.1（已发布）；剩余未排期 | 质量属性已随 0.18.0 集成；0.18.1 补 `mass_unavailable_reason` 回执契约与单位口径（离线，24 项回归）。主惯量、装配 occurrence 汇总、真实材料密度与保存重载仍由原负责人收口。 |
| [FEAT-059](work-items/FEAT-059.md) | P2 | 其它 agent 处理范围（已交付 0.18.0 事务日志底座子项） | 未排期（剩余范围） | 事务日志底座随 0.18.0 集成；原生骨架创建、受管身份/依赖、完整多模型事务未实现，未排期。 |
| [FEAT-063](work-items/FEAT-063.md) | P2 | 其它 agent 处理范围 | 未排期 | 只读 box_frame 规划器软件完成并进入本地集成；模板原生/保存重载仍未验。 |

## 开发中

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [DEV-002](work-items/DEV-002.md) | P2 | 开发中 | 未排期 | 第三批包化离线已交付，T5 实机待验；服务/启动/桥接后续分批，不关整项。 |
| [DEV-030](work-items/DEV-030.md) | P1 | 开发中 | 未排期 | 推进 G2 底板/编辑、G3 履带/性能、G4 阵列；已放宽三键不重复调查。 |
| [FEAT-010](work-items/FEAT-010.md) | P2 | 开发中 | 未排期 | Right ±Z 已验；倾斜 frame、保真/原53mm输入、编辑重载和投影驱动仍开放。 |
| [DEV-077](work-items/DEV-077.md) | P1 | R01—R04 已随 0.19.2 交付；实机/黑盒/远端余项待接手 | 0.19.2 | 0.18.2四份反馈对比归档、RELEASING/POSTCHECK回填、台账计数门禁、质量属性诊断与阶段计时回退；R01可配rotation_tolerance、R02质量属性提示/get_job 300s/known_limitations/plan_examples已在0.19.1交付；0.19.2新增草图closure_tolerance/snap_endpoints/偏差断言、mirror feature引用与回执、session_health降级策略、quilt_merge消耗回执；余项见DEV-077-HANDOFF R01—R08。 |
| [DEV-079](work-items/DEV-079.md) | P1 | 离线子项已随 0.19.2 交付；Creo 10/钣金/黑盒待接手 | 0.19.2 | 0.19.0三份Creo 10反馈归档与对照；quilt_merge描述同步、曲率默认摘要/`include_samples`、surface_group结构化失败回执、`profile.method`、POSTCHECK旧句已修；`state_reason`与裸名导入等0.19.1已修项不重复；H01—H09（Probbl.h替代、开放弧trim、残留quilt、原生截面面积、大作业compact、连续顶边选边、entities_file、native_bundle、负origin resize）待实机。 |
| [DEV-080](work-items/DEV-080.md) | P1 | 开发中；首批离线收口已提交，未合main、未发布 | 未排期 | 接手0.19.0三份报告复核后仍未闭环的H01—H09及未编号缺口；首批交付手写TU头门控契约测试、COMPATIBILITY缺头降级说明、计数自检进CI；原生解耦/等价元素树、开放弧trim、残留quilt、原生截面面积、大作业compact、连续顶边选边、entities_file、native_bundle、负origin resize待Creo10 SDK或实机；解压单测发布前阻断与verify_stages优先留后续。 |

## 部分交付，剩余待验收

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [DEV-027](work-items/DEV-027.md) | P2 | 部分交付，剩余待验收 | 未排期 | 真实世代回收、二进制可复现性及副本外部改动/登记不一致分支待验。 |
| [DEV-044](work-items/DEV-044.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.4.7 五组已有后续证据；保留 DEV-027 等整计划关联余项，避免按旧末段重复安排迁移。 |
| [DEV-046](work-items/DEV-046.md) | P1 | 部分交付，剩余待验收 | 未排期 | 第二批矩阵实机已验；第三批约束/结果比对、源件更新/嵌套及 DEV-027 余项保留。 |
| [DEV-051](work-items/DEV-051.md) | P1 | 部分交付，剩余待验收 | 未排期 | 历史离线批已交付；四壁后续、嵌套回导、原件缺项及公开预算契约按子卡对账。 |
| [DEV-052](work-items/DEV-052.md) | P1 | 部分交付，剩余待验收 | 未排期 | N 批已交付；曲面/角部、缺原件及会话调查按子卡接续；092/093 已补证，不再列未修。 |
| [DEV-053](work-items/DEV-053.md) | P1 | 部分交付，剩余待验收 | 未排期 | 反馈批部分交付；P07/P08/P11、P13/P16 及缺原件范围按卡保留，沿原 ID 接续。 |
| [DEV-065](work-items/DEV-065.md) | P1 | 部分交付，剩余待验收 | 未排期 | 诊断批已交付；真实停滞、刚体平移放行与 ack_failure 目标分支仍开放；BUG-111 已定因。 |
| [DEV-070](work-items/DEV-070.md) | P2 | 部分交付，剩余待验收 | 未排期 | 四附件校验及 API 回退已写；真实远端回退和旧附件/摘要冲突外置核对待原负责人完成。 |
| [DEV-071](work-items/DEV-071.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.17.3 离线修复已合主干；原生阶段码/miter 回执实机观察待补，53mm 根因归 BUG-050/051。 |
| [DEV-074](work-items/DEV-074.md) | P1 | 已交付 0.18.3/0.18.4/0.19.0 子项；Creo 9/10 未排期 | 0.19.0（子项已交付） | 0.19.0 交付 H03 `creo_quilt_merge` 公开（两片 400→800 mm²）、H08 `creo_surface_round` 与 `creo_measure_surface_curvature` 实机、H10 五爪整瓶整链 63 项检查；H05 钣金附着增料、H07 独立 quilt 偏置、钣金成形类与任意非平面 fill 为不可用或未取证，门禁保持；仍开放：百叶/格栅/凸台/铰链/耳、格栅 cut 定因、Creo 9/10 与 WorkBuddy。 |
| [FEAT-004](work-items/FEAT-004.md) | P2 | 部分交付，剩余待验收 | 未排期 | rebase 后 18/18 实机已补；装配/骨架/族表尺寸、分类和同计划先后语义仍未验。 |
| [FEAT-005](BACKLOG_COMPLETED.md#legacy-feat-005) | P2 | 部分交付，剩余待验收 | 未排期 | 过期 revision 错误上下文已实现；公开 stdio 验收未记录，继续保持入队前拒绝。 |
| [FEAT-006](work-items/FEAT-006.md) | P2 | 部分交付，剩余待验收 | 未排期 | 接管/收养主线已验；卡内既有剩余范围继续保留，异常所有权不以健康夹具替代。 |
| [FEAT-007](work-items/FEAT-007.md) | P2 | 部分交付，剩余待验收 | 未排期 | 长轮询已实现且实机六项通过；真实长任务/stdin 取消与公开进度细分仍开放。 |
| [FEAT-008](work-items/FEAT-008.md) | P2 | 部分交付，剩余待验收 | 未排期 | entity_ids/中心线计数及重建配套已验；其余首批范围与真多中心线原件仍缺。 |
| [FEAT-012](work-items/FEAT-012.md) | P2 | 部分交付，剩余待验收 | 未排期 | 矩阵放置已验；显式源件更新/嵌套及内核精度扫描待补，阈值不改。 |
| [FEAT-014](work-items/FEAT-014.md) | P2 | 已交付 0.18.4/0.19.0 反证子项（附着增料与成形类均不可用，门禁保持）；其余未排期 | 0.19.0（反证子项已交付） | 四壁基础/origin/选边已有；附着增料经 Creo 12.4 反证不可用（直接 add −1、union 吞并钣金体）；成形类 corner relief/草图成形 create 失败或再生失败，hem/jog 无 API，格栅 cut 未取证；连续多边折边、格栅孔、凸台/铰链/耳未排期。 |
| [FEAT-018](work-items/FEAT-018.md) | P1 | 部分交付，剩余待验收 | 未排期 | 补四动作的 revision、凭证/过期、幂等、owner、再次中断与后续编辑矩阵。 |
| [FEAT-020](work-items/FEAT-020.md) | P2 | 部分交付，剩余待验收 | 未排期 | 更新预算/force 已实现；真实断网/限流及失败期间继续建模待验。 |
| [FEAT-022](work-items/FEAT-022.md) | P2 | 部分交付，剩余待验收 | 未排期 | 真实连接器升级前后核对路径、启动身份和工具版本；本地部署指纹已实现。 |
| [FEAT-023](work-items/FEAT-023.md) | P2 | 部分交付，剩余待验收 | 未排期 | 剩余 jobs 日志、复杂请求/union 错误体量及规范化回执实机；capabilities 分页已闭环。 |
| [FEAT-029](work-items/FEAT-029.md) | P1 | 部分交付，剩余待验收 | 未排期 | 剩余跨代兼容升级/回退、多目录与公开验收，自动注册/签名另评估。 |
| [FEAT-030](work-items/FEAT-030.md) | P2 | 部分交付，剩余待验收 | 未排期 | 15+2 种子本机矩阵已验；生产版本可追溯与 Creo 9 加载/重生仍缺环境和来源。 |
| [FEAT-031](work-items/FEAT-031.md) | P2 | 部分交付，剩余待验收 | 未排期 | 两件装配导出/隔离回导已验；嵌套、外部引用与跨机重建边界仍开放。 |
| [FEAT-036](work-items/FEAT-036.md) | P2 | 部分交付，剩余待验收 | 未排期 | delete/suppress/resume 主线已验；组/阵列头随动仍未闭环。 |
| [FEAT-039](work-items/FEAT-039.md) | P1 | 已交付 0.13.0/0.14.0/0.15.0/0.18.3/0.18.4/0.19.0 子项；H15/H16 已补；多截面/offset/fill/交线未排期 | 0.19.0（子项已交付） | 0.19.0 交付 H03 quilt merge 公开（两片 400→800 mm²、可继续加厚）、H10 五爪整瓶整链（闭合壳 7858.298125 mm²、加厚与 solidify）；H15 overlap预算/覆盖诊断与H16 trim结果句柄/连续trim已在Creo12.4实机通过，H14真实交线诊断、H17 Creo10直创原件、H18 Creo10同载荷仍缺；H07 独立偏置与任意非平面 fill 仍不可用（门禁保持）；多截面/边界混合与 trim 偏置语义未排期。 |
| [FEAT-042](work-items/FEAT-042.md) | P1 | 部分交付，剩余待验收 | 未排期 | 接管、同模型并发编辑、真实再生失败及钣金语义仍需证据；通道 busy 不代替。 |
| [FEAT-043](work-items/FEAT-043.md) | P2 | 部分交付，剩余待验收 | 未排期 | 会话枚举主线已验；unknown、其它类型及真实并发枚举待补。 |
| [FEAT-044](work-items/FEAT-044.md) | P1 | 部分交付，剩余待验收 | 未排期 | 原 asm_mx.asm.16、显示失败、unknown 和真实并发的打开链路仍需现场。 |
| [FEAT-045](work-items/FEAT-045.md) | P2 | 部分交付，剩余待验收 | 未排期 | 只读装配检查主线已验；受限场景/外部原环境与公开黑盒保留。 |
| [FEAT-046](work-items/FEAT-046.md) | P1 | 部分交付，剩余待验收 | 未排期 | erase 主线已有外部证据；本机矩阵、阻断分支与公开黑盒仍未齐。 |
| [FEAT-047](work-items/FEAT-047.md) | P1 | 部分交付，剩余待验收 | 未排期 | health 正常/异常分页主线已验；外部异常数据还原及原始响应字节核对按卡保留。 |
| [FEAT-048](work-items/FEAT-048.md) | P1 | 部分交付，剩余待验收 | 未排期 | 按路径/批量收养已有实机；准入分支泛化及卡内保留项待补，不重做首批。 |
| [FEAT-051](work-items/FEAT-051.md) | P2 | 部分交付，剩余待验收 | 未排期 | requested/effective_flip 与 draft_failure 当前代码已有；外部 -1 定因、单位实机矩阵及回执补证仍开放。 |
| [FEAT-052](work-items/FEAT-052.md) | P2 | 部分交付，剩余待验收 | 未排期 | 分族上色主线已实机通过；真实 busy 并发与其余卡内矩阵未验，random/标签键归 FEAT-056。 |
| [FEAT-053](work-items/FEAT-053.md) | P2 | 部分交付，剩余待验收 | 未排期 | 三点定面与斜面草图已验；约束引用逐条核对未验证，关联 BUG-098 保留。 |
| [FEAT-058](work-items/FEAT-058.md) | P2 | 已交付 0.12.0/0.15.0/0.16.1/0.17.0/0.18.3 子项；坐标换参/扩展 frame 未排期 | 0.18.3（子项已交付） | H01 非零 `origin` 大跨度 resize 已修复（Creo 12.4 实机 14/14）；坐标换参、板厚回执新诊断、扩展 frame 与非矩形截面留原批未排期。 |

## 部分交付，剩余待规划

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [FEAT-027](BACKLOG_COMPLETED.md#legacy-feat-027) | P3 | 部分交付，剩余待规划 | 未排期 | 墓碑与旧别名拒绝已交付；显式释放/重绑定接口和跨版本历史核对待规划。 |
| [DEV-066](work-items/DEV-066.md) | P2 | 部分交付，剩余待规划 | 未排期 | 0.18.2已交付来源降级子项；当前分支8def1e4已补齐其余Git读取、报告字段、负例捕获和runtime日志取消跟踪，未发布增量及H08—H09见DEV-075-HANDOFF。 |

<a id="未来能力候选"></a>
<a id="当前优先功能"></a>

## 待规划

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [DEV-003](BACKLOG_COMPLETED.md#legacy-dev-003) | P2 | 待规划 | 未排期 | 整理 C++ 的执行上下文、模块接口和资源由谁创建、释放，再用受影响的 SDK 构建并运行原生测试。 |
| [DEV-004](BACKLOG_COMPLETED.md#legacy-dev-004) | P2 | 待规划 | 未排期 | 在 DEV-003 完成后，让各模块可以独立编译，并整理原生测试目录。检查构建缓存、安装、保存重载和失败回滚。 |
| [DEV-005](BACKLOG_COMPLETED.md#legacy-dev-005) | P2 | 待规划 | 未排期 | 按工具和参数用法记录本机哪些测过、哪些没测，并注明真实环境，同步安装和能力说明。其他环境收到具体反馈再补；不要求双版本验收，也不能拿“82 工具测过”的汇总代替每种用法的兼容性测试。 |
| [DEV-006](BACKLOG_COMPLETED.md#legacy-dev-006) | P2 | 待规划 | 未排期 | 按工具分支补成功/非法输入、真并发与保存重载；需对应 SDK/种子/UDF 环境，黑盒单列。 |
| [DEV-007](BACKLOG_COMPLETED.md#legacy-dev-007) | P2 | 待规划 | 未排期 | 复用 DEV-006 的发布回归清单，按环境记录；模拟/本地直调不代替公开 MCP。 |
| [DEV-008](BACKLOG_COMPLETED.md#legacy-dev-008) | P3 | 待规划 | 未排期 | 查清旧清单第 5/6/7/9 项分别来自哪里、现在归哪个任务，补上对照关系。来源是 NEXT_STEPS_025 的“完善建议 5”。 |
| [DEV-009](BACKLOG_COMPLETED.md#legacy-dev-009) | P2 | 待规划 | 未排期 | 按模块分别整理代码格式，每批完成后做回归检查，不自动增加历史问题的豁免项。2026-10-14 的历史统计为 67 条 Ruff 问题、36 个 Python 和 14 个 C++ 文件，见历史记录。 |
| [DEV-031](work-items/DEV-031.md) | P2 | 待规划 | 未排期 | 先澄清履带TXT的相位、闭合、近似与容差，再分步安排63站/90凸台、性能和恢复；报告−1.46%偏差仍未满足±1%，本条不直接建模。 |
| [DEV-056](work-items/DEV-056.md) | P2 | 待规划 | 未排期 | job/驱动统一记录 worker SHA256 与 build stamp；已有 service/loader 指纹不重复开发。 |
| [DEV-057](work-items/DEV-057.md) | P3 | 待规划 | 未排期 | 原 BCG 输入仍缺；凹圆棱替代例已验，补原案及超薄几何规则裁定。 |
| [DEV-058](work-items/DEV-058.md) | P3 | 待规划 | 未排期 | WorkBuddy 提示词需按当前契约更新，公开 MCP 黑盒尚未执行；不以开发者证据替代。 |
| [DEV-059](work-items/DEV-059.md) | P3 | 待规划 | 未排期 | 核实旧 22 项环境 errors 是否仍存在；余下统计校验与计划状态规范，历史清理已完成。 |
| [DEV-063](work-items/DEV-063.md) | P3 | 待规划 | 未排期 | compact erase 摘要和预览矩阵 false 的说明待补；full 字段不裁剪。 |
| [DEV-081](work-items/DEV-081.md) | P1 | A批离线六项已交付并逐任务独立审查；B/C批规划已建立，实机/黑盒未执行 | 未排期 | 第四份0.19.0反馈（护卫舰）F01—F11；A批F02圆弧闭合误拒/F03半径上限/F07更新提示/F04 connect −4回执/F11平面语义文档/F05限制说明已离线交付，六个提交与统一dev_check证据见[MAPPING第五节](validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md)；A批仅「离线已交付、实机未验」，计划见[离线批次计划](superpowers/plans/2026-11-09-feedback0190-frigate-offline.md)；B1—B6原生/实机与C0—C5黑盒拆项、前置条件见[B/C批子计划](superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md)，[WorkBuddy提示词](validation/feedback-0.19.0-frigate-2026-11-08/workbuddy-blackbox-prompt.md)仅阶段0/1可试、建模与并发留卡，未连Creo未做黑盒。 |
| [FEAT-001](work-items/FEAT-001.md) | P1 | 待规划 | 未排期 | 启动/重连/多会话状态检测及普通 retry、损坏通道恢复完整验收仍开放。 |
| [FEAT-002](BACKLOG_COMPLETED.md#legacy-feat-002) | P2 | 待规划 | 未排期 | 遇到 DLL 提示等需要人工处理的情况时，说明正在等什么。测试等待超时后，任务上下文是否保留、相关模块能否清理。 |
| [FEAT-003](BACKLOG_COMPLETED.md#legacy-feat-003) | P2 | 待规划 | 未排期 | 支持并测试带单位的关系式，例如 `8[mm]`。确认它能真实驱动尺寸、带动相关参数变化，并保留用户对单位的检查设置。 |
| [FEAT-009](work-items/FEAT-009.md) | P2 | 已交付 0.18.3 子项；动态准入已补；多截面/连续性/非平面未排期 | 0.18.3（子项已交付） | 两截面直纹曲面放样 `creo_surface_loft` 在Creo12.4已实机验收（quilt 800 mm²、trim 两侧各 400、2 mm 加厚 1600 mm³）；H13 worker构建身份/动态准入与提交前拒绝已实现并在Creo12.4核验，Creo10缺Probbl.h实机与完整放样路线仍未验；≥3 截面、smooth/闭合、非平行/扭转/圆弧截面仍不公开。 |
| [FEAT-011](BACKLOG_COMPLETED.md#legacy-feat-011) | P2 | 待规划 | 未排期 | 增加复合轨迹、可变截面和螺旋扫掠，分别明确范围并测试。 |
| [FEAT-013](BACKLOG_COMPLETED.md#legacy-feat-013) | P2 | 待规划 | 未排期 | 增加剖视、局部放大、装配图和 BOM（物料清单），逐项检查模型变化后图纸能否同步更新。 |
| [FEAT-015](BACKLOG_COMPLETED.md#legacy-feat-015) | P3 | 待规划 | 未排期 | 评估模具、NC 加工和仿真能力，先选一个最小场景做完整流程，暂不承诺支持全部模块。 |
| [FEAT-016](BACKLOG_COMPLETED.md#legacy-feat-016) | P2 | 待规划 | 未排期 | 增加翼型凸度和 NACA 四位数系列，检查能否通过原生参数编辑，并验证实际几何。 |
| [FEAT-017](BACKLOG_COMPLETED.md#legacy-feat-017) | P2 | 待规划 | 未排期 | 分别复现并测试布尔、曲面和拔模中尚未测过的用法，再决定扩大哪些支持范围。 |
| [FEAT-021](BACKLOG_COMPLETED.md#legacy-feat-021) | P1 | 待规划 | 未排期 | 设计受控取消任务，先说明 queued、running、unknown_outcome 各能否取消，再检查执行器和模型状态。不能安全中断时说明原因。取消后要检查最终状态、保存点、revision、锁和下一次任务是否正常；不能把杀 worker 或清 pending_job 当作取消成功。与未知结果恢复分别验收，任务状态名称不表示当前已有排队能力。 |
| [FEAT-024](BACKLOG_COMPLETED.md#legacy-feat-024) | P3 | 待规划 | 未排期 | lookup_constants 没找到结果时，说明没有匹配，并提示可用前缀。测试不存在的前缀、空条件、合法前缀及旧返回规则；保留正常命中的行为。当前按体验改进处理，不直接把空字典认定为缺陷。 |
| [FEAT-025](BACKLOG_COMPLETED.md#legacy-feat-025) | P2 | 待规划 | 未排期 | 评估 creo_loft 在回调未就绪时，能否用 2～6 截面种子完成部分操作。先说明支持哪些截面和模式、怎样保留模型身份，再检查已有特征、编辑、revision、保存重载和失败恢复。种子能新建零件，不代表能追加到已有零件；不自动加载 DLL 或改变策略，也不预先承诺实现成本低。 |
| [FEAT-026](BACKLOG_COMPLETED.md#legacy-feat-026) | P3 | 待规划 | 未排期 | 提供 create_feature_tree 能运行的最小 dict 示例，说明 dump XML 能否转换或导入。先让示例建模、参数、几何和重载通过，非法树能指出问题元素，再评估导出后重新导入。无效示例失败不能证明工具不可用。 |
| [FEAT-028](BACKLOG_COMPLETED.md#legacy-feat-028) | P3 | 待规划 | 未排期 | 评估一次性 create_plate 的注册/后续编辑范围；不能把无 model_id 产物当受管源件。 |
| [FEAT-032](work-items/FEAT-032.md) | P2 | 待规划 | 未排期 | 评估原生沿曲线阵列：先简单平面，再闭环弧长、相位、切向、种子计数和跳站，最后履带63站与多特征；多次切除不算原生阵列验收。 |
| [FEAT-033](work-items/FEAT-033.md) | P1 | 待规划 | 未排期 | small/large 基准已有；预算与阶段公开契约未实现，不以取消保存重载缩时。 |
| [FEAT-037](work-items/FEAT-037.md) | P3 | 待规划 | 未排期 | 先补参数误写的最小输入，再明确模型/特征参数目标与同名规则，评估少量建议；不自动猜改，验证关系、revision及重载。 |
| [FEAT-038](BACKLOG_COMPLETED.md#legacy-feat-038) | P2 | 待规划 | 未排期 | 提供不建立 Toolkit 连接的安装自检路径：校验部署产物与配置一致性（常量表、执行器与源码指纹、种子哈希与清单、protk/loader 注册文件），让按约束停止 Toolkit 连接的受限环境也能确认安装正确性，不必冒卡死风险连 Creo。先确定自检覆盖哪些项、怎样判定"一致"，以及自检通过与实机就绪的关系（自检通过不等于通道可用）。来源见Creo 10 反馈，关联 FEAT-022。 |
| [FEAT-040](work-items/FEAT-040.md) | P2 | 待规划 | 未排期 | 核对SDK后评估变半径表与收尾控制，补真实冲突边/可行半径诊断；恒定半径行为及回滚保持，与 FEAT-039 联动。 |
| [FEAT-041](work-items/FEAT-041.md) | P3 | 待规划 | 未排期 | 评估可选输出目录与预览/导出视角、正交投影；保持默认行为，输出目录不开放任意写路径。 |
| [FEAT-049](work-items/FEAT-049.md) | P1 | 待规划 | 未排期 | 显式目标参考约束克隆；核现有六类回放，不重复实现；完整快照/映射尚未交付。 |
| [FEAT-050](work-items/FEAT-050.md) | P2 | 待规划 | 未排期 | 冻结基准和显式映射后比对组件集、位姿、约束、包络/体积，缺数据标未验证。 |
| [FEAT-054](work-items/FEAT-054.md) | P2 | 待规划 | 未排期 | 待裁定四带几何偏差与求解路线，再推进全叶片/轮毂阵列；缺原始四带输入。 |
| [FEAT-055](work-items/FEAT-055.md) | P2 | 已交付 0.18.4/0.19.0 子项（H08 曲面边圆角与数值曲率/G1 已公开并实机）；其余未排期 | 0.19.0（H08 子项已交付）；剩余未排期 | `creo_surface_round` 与 `creo_measure_surface_curvature` 已公开，公开工具 107；edge-chain、变半径/过渡、斑马/曲率梳图像无 API；重拟曲面操作链、merge/放样及原生查询补证未排期。 |
| [FEAT-060](work-items/FEAT-060.md) | P2 | 待规划 | 未排期 | 骨架驱动首壁参数；依赖 FEAT-059 真实骨架，先冻结日志/依赖闭包与 revision 契约。 |
| [FEAT-061](work-items/FEAT-061.md) | P2 | 待规划 | 未排期 | 单层受管装配配置切换/抑制恢复；保留身份、约束和位姿，尚未实施。 |
| [FEAT-062](work-items/FEAT-062.md) | P2 | 待规划 | 未排期 | 独立零件 rename/derive；统一名称冲突、身份与检查点恢复，尚未实施。 |
| [FEAT-064](work-items/FEAT-064.md) | P3 | 待规划 | 未排期 | 受管世代清理 inspect/apply；冻结证据/幂等与引用保护后实施，不自动删除。 |

## 历史资料

<a id="workbuddy-030-全量实测问题映射"></a>

[完成档案与来源索引](BACKLOG_COMPLETED.md)、[开发规则](DEVELOPMENT.md)。历史版本说明和 docs/validation 原件保持路径；日期交接快照不承担当前待办维护。
