# 0.11.1 第十二轮反馈归档与逐章映射（R12）

- 归档日期：2026-11-02（Asia/Shanghai）
- 汇总条目：[DEV-064](../work-items/DEV-064.md)（归档、对账与交付编排）
- 基线：主干 `main@2ba1e2d`、源码版本 0.11.3（已发布）、公开工具 95；分支 `codex/DEV-064-r12-feedback0111`
- 原件目录：[originals/](originals/)，清单与校验见 [manifest.json](manifest.json)（2/2 长度与 SHA256 与 `C:\Users\Administrator\Downloads\0.11.1` 源文件一致，另做整文件字节序列比对）
- **与既有归档的关系**：本目录是 0.11.1 批次的 2 份反馈原件；[feedback-0.10.0-2026-10-31](feedback-0.10.0-2026-10-31/MAPPING.md)、[feedback-0.10.0-2026-11-01](feedback-0.10.0-2026-11-01/MAPPING.md)、[feedback-0.11.0-2026-11-01](feedback-0.11.0-2026-11-01/MAPPING.md) 是前三批，四目录**互不覆盖、互不合并**。
- 本批性质：**归档 + P1 修复**。归档与登记不连接 Creo；两处命令级修复先离线实现与单测，微移可观测与原点试点另做本机 Creo 12.4 实机取证；Creo 10 与 WorkBuddy 一律记未验证。
- 报告方环境：Windows x64 / Creo Parametric 10.0.0.0（`release_numeric=42`）/ Toolkit SDK 10.0.0.0 / VS2022 BuildTools 14.44.35207 / Python 3.13 / 95 工具。

## 一、固定 ID 一览

| 固定 ID | 标题 | 状态 | 优先级 | 来源章节 |
| --- | --- | --- | --- | --- |
| [DEV-064](../work-items/DEV-064.md) | 0.11.1 第十二轮反馈归档、对账与交付 | 进行中（本批） | P1 | F01–F02 全篇 |
| [BUG-107](../work-items/BUG-107.md) | `HEADERS` 清单缺存在性过滤，Creo 10 首次构建硬崩溃 | 本批实现 | P1 | F02 §1 |
| [BUG-108](../work-items/BUG-108.md) | 坐标标注求解刚体平移阻断批量构建且不可观测 | 本批实现 | P1 | F01 核心问题 1 |
| [BUG-106](../work-items/BUG-106.md) | 同名会话残留阻塞 save/erase，两处错误不给解锁链路 | 本批实现（文案，原 0.11.0 批登记） | P2 | F01 核心问题 2、3 |

既有卡增量（不新开编号）：[FEAT-054](../work-items/FEAT-054.md)（P12 续推与同族偏差回填）、[FEAT-055](../work-items/FEAT-055.md) 与 [FEAT-039](../work-items/FEAT-039.md)（G5 三算子保持待规划）、[BUG-090](../work-items/BUG-090.md)（外部构建证据格式补录）、[FEAT-035](../work-items/FEAT-035.md)（`depth_basis` 已闭环，仅记依据）、[BUG-105](../work-items/BUG-105.md)（零变更失败已闭环口径）、[DEV-063](../work-items/DEV-063.md)（擦除回执体量，未纳入本批）。

## 二、逐章映射

### F01 `2026-11-02CREO10.0.0.0-0.11.1-坐标求解微移仍拒绝批量构建P12闸门已开但卡0.004mm.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 〇 摘要：BUG-094 已修复、三点定面正式化，P12 唯一历史闸门已开 | **已闭环**：BUG-094 随 0.11.1 交付（斜面草图 dev 8e-38 mm） | 归档记录 |
| 〇 摘要：24 条带在第 2 条带被 0.004 mm 微移拒绝；容差可放行但无顶层告警 | **开放**：`native/sketch_coordinates.cpp:196-272` 仍以 1e-5 拒绝，位移只在 `geometry_deviation.sample[]` 内可见 | BUG-108 |
| 核心 1 现象：`maximum deviation mm=0.004004`、`COORDINATE_ORIGIN=-0.004003728342,0`、3 图元同量平移、`SKETCH_SOLVE_WITHOUT_INFERENCE=-1`、`AutodimensionSketch=0` | 与既有日志实现一致：`COORDINATE_ORIGIN`/`COORDINATE_DEVIATION` 由 `verify_coordinate_plan()` 输出；刚体平移无判定、无顶层字段 | BUG-108 |
| 核心 1 特征：输入自洽、零 gap、非自交，求解器做刚体平移而非变形 | 需要共模判定才能区分"平移"与"变形" | BUG-108 |
| 核心 1 建议 1：定位原点重安置来源；对"原点 + 首点重合"形态跳过原点重求解 | **试点**：以投影基准线给坐标原点补零值点-线尺寸；不可用/无效时输出 `SKETCH_ORIGIN_PIN_UNAVAILABLE` 并保持原行为，不放宽 1e-5 | BUG-108 |
| 核心 1 建议 2：把"发生位移"提升为回执顶层字段（如 `sketch_shifted`） | **采纳**：新增顶层 `sketch_shifted`（`detected`/`rigid`/`translation_mm`/`max_point_mm`/`point_count`/`sample`/`tolerance_source`/`accepted_by_request`/`note`）；`geometry_deviation` 只增 `shift_detected`、`accepted_by_request` | BUG-108 |
| 核心 1 建议 2 附注：`tolerance_source:"request"` 时 `exceeds_warning:false` 看起来像"完全精确" | **采纳**：`exceeds_warning` 语义不变（是否超阈值），另加 `accepted_by_request` 与 `note` 明确"放行不等于精确求解" | BUG-108 |
| 核心 1 建议 3：文档写明 `geometry_tolerance_mm` 是"验收放行阈值"而非"求解精度" | **采纳**：`server.py` 工具描述、`README.md`、`geometry_deviation.py` 文档串同步 | BUG-108 |
| 核心 1 同类历史：0.10.0 报过同族（本仓 2.91e-4 mm，报告方 0.004 mm） | 同族合并观察，不新开第二张卡 | FEAT-054 增量 |
| 核心 2：装配失败恢复死路（`reconciliation.py:520` 仅 part/sheetmetal，四动作全拒） | **已回应（0.11.3）**：BUG-105 新增 `creo_reconcile_model(action="ack_no_mutation", confirm_zero_mutation=true)`，纯注册表事务、装配可用；四动作仍限零件/钣金，本批不扩展 | BUG-105 已闭环口径 |
| 核心 3：save 的 origin 不匹配仍不引导 erase（`native/generic.cpp` 裸错误） | **开放**：`:6182-6183` 原文未变 | BUG-106 |
| 核心 4：G5 三 op（`surface_loft`/`project_curve`/`surface_trim`）仍未实现，P12 只能 194 ops 替代 | **保持待规划**：Q08–Q10 探针"路线不成立"需重拟技术路线；三维曲面链本批不做 | FEAT-055、FEAT-039 |
| 核心 4 后果：194 ops 紧贴 200 ops 上限、单计划内必须完成、一次拒绝整批回滚 | 依赖 BUG-108 的可观测与试点结论，不改变计划上限 | BUG-108、FEAT-054 |
| 正向 1：BUG-094 闭环（normal 与解析一致、dev 8e-38 mm、vol 9866.313 精确闭合、保存重载通过） | 报告方环境结果，本仓 0.11.1 已交付同项修复 | 归档记录 |
| 正向 2：失败模型清理 `failed_model_cleanup:{status:"erased", absence_verified:true}` | 已交付（BUG-096，0.11.1） | 归档记录 |
| 正向 3：`geometry_tolerance_mm` 机制本身（`tolerance_source`/`warning_threshold_mm` 回显、边界校验） | 保留机制，本批只补语义说明与顶层位移告警 | BUG-108 |
| 正向 4：recolor 回归 80/80、12 族、基线 present | 0.11.3 已扩展（BUG-104 `refresh_baseline`、FEAT-056 取色），不复用其回归结论 | 归档记录 |
| 正向 5：两点成面后实建 2 条带，bbox X = [-99.87, 98.88]（理论 ±98.55） | 报告方环境结果，本仓未复现 | 归档记录（未验证） |
| 附 P12 数据：投影剪裁母面 61 040.63 vs 62 231.97 mm²（−1.91%）、标定厚度 10.063 vs 9.87 mm | 报告方要求回执声明 dV；本仓仍缺该声明字段 | FEAT-054 增量 |
| 附 P12 数据：81 点样条多边形弦近似与直纹面差异属 A01 允许近似 | 需在回执声明，不新增数值口径 | FEAT-054 增量 |
| 附 job_id：`5f1dba8b…`（成功）、`725531e2…`（第 26 op 拒绝）、`ad638fd8…`（容差放行含位移） | 报告方现场编号；本仓不复用其状态作证据 | 归档记录 |

### F02 `2026-11-02CREO10.0.0.0-0.11.1-门控未延伸到头文件清单Probblh硬崩溃与盲孔口径标记第三次未加.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| §1 现象：`FileNotFoundError: ...\protokit\includes\Probbl.h` → `SDK constant generation failed`，`bridge.py build` 中止 | **开放**：`tools/generate_constants.py:7-41` 的 `HEADERS` 无存在性过滤，`read_text()` 直接抛错 | BUG-107 |
| §1 根因：Q07 为 G5 探测新增 5 个头，注释写明"declared outside the original feature-header list" | 与源码一致（`:35-41` 注释与条目） | BUG-107 |
| §1 本机 SDK 存在性：`Probbl.h` 缺失；`ProTrim.h`/`ProStdSection.h`/`ProMerge.h`/`ProAsmcomp.h` 存在 | 本仓无法核对 Creo 10 SDK；以"参考 SDK 存在或显式跳过"契约覆盖 | BUG-107（Creo 10 记未验证） |
| §1 同族判断：与 BUG-090 同一族，函数有 `MECHDOG_HAS_*` 门控、头文件清单没有 | **采纳**：门控延伸到 `HEADERS`，按 `GATED_SDK_CALLS` 模式新增 `GATED_HEADERS` 契约 | BUG-107 |
| §1 影响面：native 全源码无 `Probbl.h` 独有符号引用（P08 用 `ProSmtedgeContourGet`） | 本仓核对一致：无 bbl 类符号引用 | BUG-107 |
| §1 建议：缺失头跳过读取且不生成 `#include` 行 | **采纳**：同一"可用头"集合驱动枚举扫描与 include 段 | BUG-107 |
| §1 建议：补 `GATED_HEADERS` 契约测试 | **采纳**：`tests/unit/test_gated_headers.py`，清单每个头要么在参考 SDK 存在、要么有跳过用例 | BUG-107 |
| §1 备选：`#if __has_include(<Probbl.h>)` | **不采纳**：`constants.inc` 在库外生成，编译期与生成期双闸门会出现"头存在但枚举未读"或"枚举已读但 include 被跳过"的偏差 | BUG-107（决策） |
| §2 盲孔 `depth_basis` 第三次未加 | **已闭环（0.11.2）**：`depth_basis`/`depth_scheme_code`/`depth_scheme_query` 三键 + `tests/unit/test_hole_depth_basis.py` | FEAT-035 已闭环 |
| §3 好消息：BUG-090 P12 证据格式（环境/上游提交/dirty 与补丁/源码指纹/constants.inc/结果） | **采纳**为归档基线字段，见 `manifest.json` 的 `source_baseline` | DEV-064 |
| §3 FEAT-052 台账滞后已闭环 | 已闭环（0.11.3 卡头为"已交付（0.11.0；实机 28/28）"） | 归档记录 |
| §3 种子闸门第二版稳定运行（`seed_package.json` 与附件、Release 三方一致，种子 9/9） | **已闭环**：0.11.3 种子包 `926c5a4f…`，两版未再现 0.9.0 脱节 | 归档记录 |
| §3 Q 批修复质量（失败清理、三点定面、显式容差、stage、分页、背靠背竞态、BUG-100） | 0.11.1 已交付，本批不重复派工 | 归档记录 |
| §4 升级摘要：首次编译失败、本地补丁 +11 行、worker 9 820 160 B、指纹 `314cb07c…`、constants.inc 6 222 常量 | 外部环境记录；本仓不复用其哈希或字节数作为成交依据 | BUG-107（参考） |
| §4 本地补丁每次升级需重打（该文件每次被上游覆盖） | 本批上游化后不再需要本地补丁 | BUG-107 |
| §5 两次外部 Creo 10 构建证据（0.10.0 零补丁 / 0.11.1 含本地补丁） | 归档为外部证据，格式与 BUG-090 P12 要求对齐 | DEV-064、BUG-090 增量 |
| §6 未验证：P08 候选边、Q07 G5 探测、斜面草图、三点定面、失败清理、stage、分页、竞态、BUG-100 | 保持未验证，不由本机外推 | 各卡未测范围 |

## 三、缺件与不复用

| 项 | 说明 |
| --- | --- |
| Creo 10 首次构建的完整日志 | 报告方只给摘要行与"日志含完整 traceback"的说明，`build/generate_constants.log` 原件未随包提供 |
| P12 原始 TXT v1.2 与 580 项 blocked manifest | 仍未到；FEAT-054 的 3 项 unresolved（seq387/388/389 与 family_table 来源）继续阻塞 |
| 24 条带 194 ops 计划 JSON | 未提供，本机无法重放同一输入；只能构造同形态细长三角条夹具 |
| 报告方 worker 指纹 `314cb07c…` / 9 820 160 B | 含本地补丁的构建产物，不进入本仓库证据链 |
| Creo 10 实机、WorkBuddy 黑盒 | 本机无 Creo 10 SDK/许可，一律记未验证 |

## 四、本批不做

- G5 曲面三算子与 P12 正规链路（FEAT-055、FEAT-039 保持待规划）。
- 装配四恢复动作扩展（`restore_baseline`/`accept_saved`/`accept_live`/`abandon_new`）。
- `adopt_session_copy`、自动擦除、自动接管会话副本。
- `geometry_tolerance_mm` 默认值调整、1e-5 闸门放宽、autodim 1e-3 告警阈值变更。
- WorkBuddy 黑盒验收、Creo 9/10 实机复测、并发/队列能力。
