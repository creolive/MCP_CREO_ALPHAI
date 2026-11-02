# MCP_CREO_MechDog 0.11.1

0.11.1 交付 0.10.0 晚间反馈包（Q00–Q15 批次）的修复与增量（PATCH，用户指定编号）：失败模型清理与同名复用、斜面草图修复、三点定面基准面、草图显式容差、作业阶段上报、结果有界回执与分页，以及 Toolkit 通道背靠背提交竞态修复。公开工具保持 **95 个**不变；0.11.0 及更早的提交、标签、Release 和附件均保持原样。反馈原件十件已逐字节归档（[manifest](validation/feedback-0.10.0-2026-11-01/manifest.json)、[逐章映射](validation/feedback-0.10.0-2026-11-01/MAPPING.md)）。

## 修复与增量

- **失败模型清理与同名复用（[BUG-096](work-items/BUG-096.md)）**：新建模型作业失败后，终态携带 `failed_model_cleanup` 回执（erased/cleaned、`absence_verified` 等 17 种形态按实际路径如实报告）；只清理能证明由本次失败作业新建、未被使用、无引用的对象，预存同名对象原样保留。终态新增显式 `rollback_status ∈ {notattempted, succeeded, failed, unconfirmed}`（`rollback_succeeded` 语义不变）。失败后**同名再次新建不再被迫改名**（本机 Creo 12.4 实机 S1/S2/S3 三场景通过）。
- **斜面草图修复（[BUG-097](work-items/BUG-097.md)）**：三点定面的斜面上没有精确垂直基准面时，`sketch`（frame 形式）自动创建 4 个基准点与两块互相垂直的辅助基准面（法向 frame.u/frame.v）作 orientation 与投影锚点；此前未完成草图停在世界 XY 导致 `CompleteFeature=-1`。实机体积相对偏差 1.45e-8、保存重载通过；三点定面读取修复（[BUG-098](work-items/BUG-098.md)）一并交付。
- **三点定面（[FEAT-053](work-items/FEAT-053.md)）**：`datum_plane` 的 `reference` 新增 `{kind:"through_points", points:[标签×3]}` 形态（引用同计划内 `datum_points` 特征标签）；重复点、近共线在准入层拒绝。实机 5 正例 + 3 负例通过。
- **草图显式容差（[FEAT-010](work-items/FEAT-010.md) 增量）**：草图创建/编辑可选 `geometry_tolerance_mm`（有限正数上限），省略时保持默认——coordinates 写入核对超过 1e-5 mm 失败并回滚、autodim 超过 1e-3 mm 报告告警；非法值（0、负数、非数值）准入拒绝。作业回执报告实际几何偏差。
- **作业阶段上报与通道预约（[FEAT-033](work-items/FEAT-033.md) 增量、[BUG-100](work-items/BUG-100.md)）**：`creo_get_job` 全程携带 `stage` 阶段流转；Toolkit 通道新增"接受→runner 收尾"的预约（`toolkit-channel.json`），背靠背提交在 runner 取得通道前的空窗内现在按契约**立即 busy 拒绝**（此前会被接受并排队）；同模型 `pending_job` 语义不变，预约在终态后释放、不可判定时保守占用。实机背靠背（11.9 ms 间隔）与真实并发复验均符合 `reject_busy_without_creating_a_job`。
- **结果有界回执与分页（[FEAT-008](work-items/FEAT-008.md) 增量）**：大结果按 `{total, truncated, sample≤20}` 有界回报，unavailable 携带原因、绝不返回全 0；`creo_get_job` compact ≤32 KiB、detail=full 游标分页翻页不重不漏；预览与装配快照同口径。
- **[BUG-099](work-items/BUG-099.md) 定因披露（无代码变更）**：轮1实机 `axis_pattern` 后 Backup/Save 均 -1 的失败经取证判定为**实验性 worker 与提交源码不一致**所致（终态消息含仓库不存在的 `ProMdlSave`、回执形态无法由已提交分支产生）；干净源码下 Q13 驱动连续三次全通过（`disk_cut_pattern` 保存重载 true、体积解析一致）。随版披露，不改产品代码。
- **工程与文档**：G5 原生契约冻结（[G5-NATIVE-CONTRACT](development/G5-NATIVE-CONTRACT.md)）、P12 扭叶片配方离线转换与分级验收（一带通过、四带受坐标标注默认阈值约束，见 [P12-BLADE-ACCEPTANCE](development/P12-BLADE-ACCEPTANCE.md)）、DEV-055 曲面探测头登记、`docs/superpowers` 行尾规范化。

## 实机验收摘要（本机 Creo 12.4.0.0 / 匹配 SDK / MSVC）

四轮实机（2026-11-01～02，[记录](validation/DEV-053-Q15-live-2026-11-01.md)）：Q05 三点定面 8/8；Q06 斜面草图 L1/L2；Q03 失败清理 S1/S2/S3；Q13 预览/分页全套（含 `disk_cut_pattern`）；Q02 草图容差 15/15（4 例显式容差被强制拒绝按契约判定）；Q04 真实并发 busy 回执完整并发现/修复 BUG-100；Q01 P07 原点 3+3、P08 钣金 9/9 与法兰 2/2、P11 预览跳过态覆盖；Q11 P12 一带通过；BUG-100 背靠背/并发/预约释放三项复验通过。离线：全量单元 **2096 项 0 failures**、`tools/dev_check.py` success=true（本批变更文件全部过 ruff/clang-format）。

## 未测范围（保持开放）

WorkBuddy 纯 MCP 黑盒未执行（[提示词已备](validation/WORKBUDDY-0.11.1.md)）；同模型空窗陈旧 revision 竞态、>2 并发未做实机；Q08–Q10 三曲面链（探针路线不成立，待重规划）；Q11 四带/全叶片/轮毂阵列；Creo 9 本机无 SDK（实机编译与建模运行时未验收）、Creo 10 独立复测不作为门槛；本机 Creo 12.4 通过不外推其他环境。BUG-091 根因未定，实机准入纪律持续有效。

## 附件

| 附件 | SHA256 |
| --- | --- |
| `MCP_CREO_MechDog-0.11.1-seed-library.zip` | `f1794794d3abed1f8c8ec4de0f3ff2a8338f5d8d9118c5323ec5fef4b075820f` |
| `MCP_CREO_MechDog-0.11.1-source.zip` | 见[发布记录](validation/RELEASE-0.11.1.md)与 Release 正文（源码包由标签提交生成，哈希不预先写入本文件所在提交） |

发布状态见 [发布记录](validation/RELEASE-0.11.1.md)。
