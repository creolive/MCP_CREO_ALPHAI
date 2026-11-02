# 0.10.0 第十轮反馈归档与逐章映射（R10）

- 归档日期：2026-11-02（Asia/Shanghai）
- 汇总条目：[DEV-060](../work-items/DEV-060.md)（归档、对账与计划落盘）
- 基线：主干 `main@64e28f1`、源码版本 0.11.1、公开工具 95；分支 `codex/DEV-060-r10-followup`
- 原件目录：[originals/](originals/)，清单与校验见 [manifest.json](manifest.json)（3/3 长度与 SHA256 与 `C:\Users\Administrator\Downloads\0.10.0` 源文件一致）
- **与既有归档的关系**：本目录是另一位报告人的 3 份 0.10.0 验收原件；[feedback-0.10.0-2026-11-01](feedback-0.10.0-2026-11-01/MAPPING.md) 是晚间包 10 件，二者**互不覆盖、互不合并**。
- 本批性质：**归档与对账**。本轮只读核对源码与台账，未连接 Creo、未运行产品测试、未合入 main、未发布。

## 一、固定 ID 一览

| 固定 ID | 标题 | 状态 | 优先级 | 来源章节 |
| --- | --- | --- | --- | --- |
| [DEV-060](../work-items/DEV-060.md) | 0.10.0 第十轮反馈归档、对账与计划落盘 | 已完成（本轮，未提交/未发布） | P2 | F01–F03 全篇 |
| [BUG-101](../work-items/BUG-101.md) | 近容差端点间隙导致拉伸 `-1` 且无准入判据/失败归因 | 待开发 | P1 | F02 §一 P1、§三 |
| [BUG-102](../work-items/BUG-102.md) | 倒角+圆角边界面 10° 拔模由成功变 `-1`；`flip` 入参与回显不一致 | 待复现 | P1 | F02 §五 N1 |
| [BUG-103](../work-items/BUG-103.md) | 水平底板 Z=0 长边不被登记为壁面轮廓（`-8`），四壁第 3 道受阻 | 待复现（部分诊断已交付） | P1 | F01 §二 R2/S3 |
| [DEV-061](../work-items/DEV-061.md) | 种子包摘要「仓库记录 vs 当场重建归档」仓库级闸门 | 待开发 | P2 | F03 §二 |

既有卡增量（不新开编号）：[FEAT-014](../work-items/FEAT-014.md)（壁面归属与四壁现状）、[FEAT-035](../work-items/FEAT-035.md)（`depth_basis` 契约）、[FEAT-051](../work-items/FEAT-051.md)（`requested/effective` flip 与失败分类）、[BUG-049](../work-items/BUG-049.md)（诊断已交付、准入与归因仍缺）、[BUG-090](../work-items/BUG-090.md)（Creo 10 外部编译证据）。

## 二、逐章映射

### F01 `2026-10-31_CREO_0.10.0_水平底板底边无法挂折边_R2仍未解决.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 一 表格 R1 首壁、S5 底板几何保持修复 | 已闭环，无动作 | 归档记录 |
| 一 N3 `preview` 写文件正常 | 已闭环（`src/creo_mechdog/preview.py`） | 归档记录 |
| 一 草图诊断增强（`closure_tolerance_mm`/`max_endpoint_gap_mm`/`near_tolerance_pairs`/`max_cluster_spread_mm`/`open_end_samples`） | 已交付（0.10.0 N03 / BUG-049 诊断子项），正面 | 归档记录 |
| 一/二 R2：YZ 配方 185×232×1 底板，边 104/105 成功、边 106 `ProSmtedgeContourGet=-8`，f_py 未执行、整批回滚 | **开放**。0.11.x 已交付 `wall_contour_status=eligible|ineligible|unknown` 与 `wall_contract.wall_face_ids`（`native/generic.cpp:419-431`、`src/creo_mechdog/sheetmetal.py:177-260`），可事前查询但**归属成因未定**；调用方仍会先撞 `-8` | BUG-103；FEAT-014 |
| 二 判读：Z=0 两长边未被登记为 green/white 壁面轮廓，疑与“第一壁折弯侧”判定有关 | 未定因，需人工 UI 对照 + 原生元素树对照 | BUG-103 |
| 二 建议 1：先在 Creo UI 人工复现；若 UI 亦失败则文档写明配方或直接拒绝该构造 | 未执行（需用户在 UI 侧确认；本轮不连 Creo） | BUG-103 |
| 二 建议 2：修报错文案（原提示让用户“用 depth=plate size, thickness=sheet thickness 重建底板”，而用户正是此写法） | **部分已改**：`native/advanced.cpp:1396-1412` 已重写为帧契约 + `wall_face_ids` + YZ 配方指引；但**该指引与 R2 实测矛盾**（推荐的正是失败配方），仍需核对 | BUG-103 |
| 二 建议 3：`edges` 给 `flange_available` | **已以不同名交付**：`wall_contour_status` 三态 + `wall_contour_query_code`（`sheetmetal.py:181-183` 明确不命名为 `flange_available`，`eligible` 不解除 `adjacent_bend_ends` 拒绝）；剩余仅文档可发现性 | FEAT-014（文档增量） |
| 二 建议 4：折弯释放参数/自动角部处理 | **保持开放**（`four_walls_complete=false`，corner relief/miter 未实现） | FEAT-014 |
| 三 S3 四壁第 3 道失败（与 R2 同源判定） | 与 BUG-103 同源；四壁能力仍不支持 | BUG-103、FEAT-014 |
| 四 历史遗留 S2（`flip` 无效）/ S6 / P3 / P5 / P11 | S2→BUG-047 已修（`PRO_E_SMT_FLANGE_SEC_FLIP`）；S6→BUG-060 待核实；P3（dict plane `offset≠0`）→BUG-061 待核实；P5（欧拉角反手）→BUG-045 已核对交付；P11（`native_bundle`）→FEAT-031 两段式实机通过 | 归档记录，不新开 |

### F02 `20261031_CREO_v0.10.0_端点焊接诊断已补齐但仍不可焊_draft方向取反静默失败.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 一 P1 近容差端点：诊断字段齐、拉伸 `-1` 仍在 | 诊断已交付；**准入判据与失败归因缺失**（`near_tolerance_pairs` 仅出现在 `src/creo_mechdog/operation_results.py` 投影，准入/原生侧无判据） | BUG-101；BUG-049 增量 |
| 一 P2/P6：round/chamfer/draft 已带 `material_delta_mm3` | 已闭环（FEAT-051，0.10.0 N04 实机） | 归档记录 |
| 一 P3：`creo_new_part` 空模型 preview 仍 `failed_step=output_file` | 已闭环（`PREVIEW_STATUSES` 含 `skipped_no_geometry`，Q01/P11 实机通过） | 归档记录 |
| 一 P5：`creo_capabilities.extrude_depths` 与 schema 不一致 | 已闭环（0.10.1 三键化；`tests/unit/test_t01_capability_contracts.py:179-186` 锁定） | 归档记录 |
| 三 P1 能力部分：应在草图提交即拒绝并引用 `near_tolerance_pairs`，或给 `weldable` 类判定 | 未实现 | BUG-101 |
| 三 判据：`gear10.json` → extrude add blind 10 期望 `volume=1849.80285` | 作为 BUG-101 回归判据 | BUG-101 |
| 五 N1：chamfer+round 面 10° 拔模 `-1`（0.9.0 同调用成功 +264.19） | **开放**；最可疑变量为 FEAT-051 新增元素树开关（`PRO_E_DRAFT_TWEAK_OR_INTERSECT`/`PRO_E_DRAFT_EXTEND`/`PRO_E_DRAFT_SPLIT`），`generic_draft` 无“加料即拒绝”守卫（`native/advanced.cpp:224-256`） | BUG-102 |
| 五 建议 1：失败信息区分“几何不可行”与“引用错误” | 未实现 | BUG-102 |
| 五 建议 2：`flip` 语义（入参 false、回显 true）；建议 `requested_flip`/`effective_flip` 或改名 `apply_flipped` | `requested_flip`/`effective_flip` 全库 0 命中；`draft_geometry.flip` 现为特征树实读值（`advanced.cpp:178-184`），与入参不区分 | BUG-102、FEAT-051 增量 |
| 五 建议 3：0.9.0→0.10.0 行为变化若属刻意收紧须写入 release note | 无该记录的收紧；按回归嫌疑处理，先证伪 | BUG-102 |
| 七 正面：`list_session_models`、失败回滚干净 | 归档记录 | — |
| 八 R1–R4 最短回归判据 | R1→BUG-101；R2→BUG-102；R3/R4 已满足 | BUG-101、BUG-102 |

### F03 `2026-10-31CREO10.0.0.0-0.10.0-BUG090获Creo10零补丁编译证据但种子摘要回填仍无闸门.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 0/1 BUG-090：Creo 10.0.0.0 首次零补丁编译通过，`MECHDOG_HAS_ProSmtPartThicknessGet=1`、无 `...ValueGet`，三级回退落到厚度尺寸 | 外部证据成立，**只回填，不改代码**；实机建模仍未验 | BUG-090 增量 |
| 1 建议：状态细化为“编译已在 Creo 10 通过；仅实机建模待验” | 采纳 | BUG-090 增量 |
| 2 种子摘要回填仍是无闸门手工步骤（`tools/package_seeds.py` 只 print、`RELEASING.md` 无该项、无 `install_seed_library(archive_file=...)` 用例） | **主体已闭环**：0.10.1 已加 `tools/package.py --seed-archive` 必填 + `validate_release_inputs`、`seeds.install_seed_library` 先校验、`RELEASING.md` 第 5 步已写入回填、`tests/unit/test_release_integrity.py` 有真实归档安装/篡改/错摘要三例。**残留**：测试 fixture 自己 `write_record()`，仓库真实 `docs/seed_package.json` 与“当场重建归档”的一致性无断言；`package_seeds.py` 仍只打印 | DEV-061 |
| 3 盲孔 tip 口径无机器可读标记（`depth_basis`/`tip_depth` 全库 0 命中） | 开放；`FEAT-035` 只交付了 tip 几何口径 | FEAT-035 增量 |
| 3 建议 README hole 行注明“0.10.0 起 custom 盲孔为钻尖口径” | 未做 | FEAT-035 增量 |
| 4 BUG-091/092/093 已建卡、README 版本段已更新、回调注册稳定、`.gitattributes` 未变 | 归档记录 | — |
| 6 未验证项（板厚三级回退实际读数、折边 `end_trim_mm`、四壁/corner relief、T09B 等） | 保持未验证，不由本机外推 | 各卡未测范围 |

## 三、已闭环、本轮不重复派工

| 项 | 依据 |
| --- | --- |
| round/chamfer/draft 体积回报与 `draft_geometry` | FEAT-051，0.10.0 N04 七夹具实机 |
| `extrude_depths` 枚举与 schema 不一致 | 0.10.1 三键化 + 单测锁定 |
| 空模型 preview `failed_step=output_file` | `skipped_no_geometry` 已实现，Q01/P11 实机通过 |
| 折边 `flip` 无效 | BUG-047 根因已定并修复 |
| `native_bundle` 打包导出 | FEAT-031 两段式实机通过 |
| 装配旋转欧拉角“反手” | BUG-045 已核对（XYZ Euler 旧语义保持） |
| 种子包安装/打包含摘要闸门 | BUG-089 / DEV-053 P04 已交付（残留见 DEV-061） |
| `edges` 的折边可用性标记 | 已以 `wall_contour_status` 三态交付 |

## 四、缺件与未验证

- F01 未附 job 原始日志与模型文件；边 104–107 为报告方观察值，本仓库不复用历史 edge id，只作复现输入。
- F02 未附 `gear10.json`/`gear10_snapped.json` 原文件（0.8.x 起即缺件，见 BUG-049 卡）；本批以报告给出的间隙量与体积判据构造替代夹具，不声称逐字回放。
- F03 的 Creo 10 编译证据来自报告方环境（VS2022 14.44 / Python 3.13），本仓库未复现；只登记为外部证据。
- 本机 Creo 12.4 实机、Creo 9/10 实机与 WorkBuddy 黑盒：本轮均**未执行**，全部记为未验证。
