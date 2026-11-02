# 0.11.0 第十一轮反馈归档与逐章映射（R11）

- 归档日期：2026-11-02（Asia/Shanghai）
- 汇总条目：[DEV-062](../work-items/DEV-062.md)（归档、对账与登记）
- 基线：主干 `main@c85aa8d`、源码版本 0.11.2（已发布）、公开工具 95；分支 `main`
- 原件目录：[originals/](originals/)，清单与校验见 [manifest.json](manifest.json)（3/3 长度与 SHA256 与 `C:\Users\Administrator\Downloads\0.11.0` 源文件一致）
- **与既有归档的关系**：本目录是 0.11.0 批次的 3 份验收原件；[feedback-0.10.0-2026-10-31](feedback-0.10.0-2026-10-31/MAPPING.md) 与 [feedback-0.10.0-2026-11-01](feedback-0.10.0-2026-11-01/MAPPING.md) 是 0.10.0 两批，三目录**互不覆盖、互不合并**。
- 本批性质：**归档、对账与离线实现**。归档与登记不连接 Creo、不运行产品测试、不合入 main、不发布；三处代码修复只做离线实现与单测，实机验收另指派。

## 一、固定 ID 一览

| 固定 ID | 标题 | 状态 | 优先级 | 来源章节 |
| --- | --- | --- | --- | --- |
| [DEV-062](../work-items/DEV-062.md) | 0.11.0 第十一轮反馈归档、对账与登记 | 已完成（本轮，本地） | P2 | F01–F03 全篇 |
| [BUG-104](../work-items/BUG-104.md) | 旧检查点无组件 `appearance` 基线，上色无自动迁移路径 | 已修复（随 0.11.3 发布，实机待验） | P1 | F01 核心问题 1 |
| [BUG-105](../work-items/BUG-105.md) | 零变更失败把装配置 `failed`，官方工具无恢复动作 | 已修复（随 0.11.3 发布，实机待验） | P1 | F01 核心问题 3 |
| [FEAT-056](../work-items/FEAT-056.md) | 色板支持零件名键与 `random:true` 一键随机上色 | 已交付（随 0.11.3 发布，实机待验） | P2 | F01 次要问题 1 |
| [BUG-106](../work-items/BUG-106.md) | 同名会话残留阻塞 save/erase，错误信息不含解锁链路 | 待规划（本批只登记） | P2 | F01 核心问题 2 |
| [DEV-063](../work-items/DEV-063.md) | 擦除 inspect 回执体量与 `view_matrix_matches` 说明 | 待规划（本批只登记） | P3 | F01 次要问题 2、3 |

既有卡增量（不新开编号）：[FEAT-052](../work-items/FEAT-052.md)（补基线与取色参数）、[BUG-101](../work-items/BUG-101.md)（R1 判据与风险标记语义）、[BUG-102](../work-items/BUG-102.md)（R2 方向失败归因与元素树 A/B）、[BUG-088](../work-items/BUG-088.md)（R3 空件预览）、[BUG-089](../work-items/BUG-089.md)（防复发状态行）、[DEV-061](../work-items/DEV-061.md)（首屏状态与台账对齐）。

## 二、逐章映射

### F01 `2026-11-01_CREO_0.11.0_受管装配上色解锁链路三处断裂与装配失败恢复死路.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 〇 上色本身成功：`painted=80/80`、12 族计数、写后读回与保存重载读回 1e-6、revision 4→5 | 正面结果，功能无缺陷 | 归档记录 |
| 核心 1：0.10.x 检查点组件快照无 `appearance`，execute 被拒（`missing_count:80`），无迁移 | **开放→已修（离线）**：0.11.2 及以前只有 `appearance.py:154-164` 的拒绝与 `CHECKPOINT_GUIDANCE`；本轮新增显式 `refresh_baseline`，在准入阶段以实读外观填基线，回执带 `baseline_source` | BUG-104、FEAT-052 增量 |
| 核心 1 建议 1：dry-run 回执给出“一键补基线”动作 | 采纳为 `next_action`（只读、不建作业、不推 revision） | BUG-104 |
| 核心 1 建议 2：文档声明“0.10.x 需先 save 一次” | 文档同步（README/工具描述），但不再作为唯一出路 | BUG-104、FEAT-052 增量 |
| 核心 1 建议 3：recolor 自动降级“先 save 再 recolor” | **不采纳**：隐式推进 revision 与“执行恰好一次保存”的既有契约冲突 | 归档记录（决策） |
| 核心 2：同名会话副本来自外部 origin，`creo_save_model` 报 origin 不匹配、`creo_erase_session_models` 报 `modified`，两处均无解锁引导 | **开放**：`native/generic.cpp:6182-6183`、`:5008-5011` 文案未变；`adopt_session_copy` 全库 0 命中 | BUG-106（本批只登记，不实现） |
| 核心 2 建议 3：`adopt_session_copy` 受管收养参数 | 未实现，需先定义“会话副本与检查点组件结构一致”的判定与责任边界 | BUG-106 |
| 核心 3：connect 阶段零变更失败的 save 把 `status` 置 `failed`；reconcile 四动作全拒；唯一出路手改 `model.json` | **开放→已修（离线）**：`generic_bridge.py:641-654` 原先只认 `callback_preflight`；本轮按“无变更证据”保持 `ready`，并提供显式 `ack_no_mutation` | BUG-105 |
| 核心 3 建议 1：区分失败性质（`failed_no_mutation`） | 采纳为“无变更证据即保持 `ready`”，不新增可长期停留的中间态，避免状态机扩散 | BUG-105 |
| 核心 3 建议 2：提供 `ack_failure` 类显式恢复动作 | 采纳为 `creo_reconcile_model(action="ack_no_mutation")`，注册表事务 + 审计块，装配可用 | BUG-105 |
| 核心 3 建议 3：文档写明“零变更失败可编辑 model.json” | **不采纳**：以官方动作替代手工改文件；文档改为指向 `ack_no_mutation` | BUG-105 |
| 核心 3 附带观察：`model.json` 的 `status` 可被外部直改且被接受 | 记录为已知边界：注册表不做完整性校验，官方动作是唯一受支持路径 | 归档记录（边界） |
| 次要 1：自动分族 palette 键为 `source_model_id` UUID，随机上色需三步 | **已交付（离线）**：自动分族下接受唯一零件名键；`random:true` 与 `palette` 互斥并回显解析结果 | FEAT-056 |
| 次要 2：`preview.view_matrix_matches:false` 无说明 | 开放（文档） | DEV-063 |
| 次要 3：单目标 erase inspect 的 `remaining_after` 仍列全部组件 | 开放（回执体量） | DEV-063 |
| 正向清单：dry-run 完全离线、双重读回、基线三态、erase 证据链、外观写装配层 | 保留设计，不在本批改动 | 归档记录 |

### F02 `2026-11-01CREO10.0.0.0-0.11.0-种子闸门完整落地并实测双向验证与FEAT052台账滞后.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 0 摘要：BUG-089 闸门完整落地；BUG-091/092 有交付；BUG-090 待复验；盲孔 `depth_basis` 未实现；FEAT-052 台账滞后；工具 95 | 三项已由后续版本闭环（见下），两项转本批 | 归档记录 |
| 1 种子闸门双向实测（官方包通过、篡改包拒绝） | **已闭环**：`tools/package.py --seed-archive` 必填、`seeds` 安装前校验、`docs/seed_package.json` 为受信记录；0.11.2 起另有仓库级断言（DEV-061） | BUG-089、DEV-061 |
| 1 建议：把 BUG-089 卡头改为“防复发已交付（0.10.1）” | 采纳，本轮修正 | BUG-089 增量 |
| 2 BUG-090：10-31 的 Creo 10 零补丁编译证据未被吸收 | **已闭环**：R10 批（DEV-060）已把外部编译证据回填 BUG-090，实机建模仍未验 | BUG-090 增量（无需再动） |
| 2 记录：10-31 报告未进 0.10.0 归档 | 归档队列已推进至 `feedback-0.10.0-2026-10-31`，本批归档为 0.11.0 批次；不追溯重排历史目录 | 归档记录 |
| 3 盲孔 `depth_basis`/`depth_scheme_query` 全库 0 命中 | **已闭环（0.11.2）**：`depth_basis`/`depth_scheme_code`/`depth_scheme_query` 三键随 0.11.2 交付，`tests/unit/test_hole_depth_basis.py` 锁定；实机回执未验 | FEAT-035 增量（已闭环，仅记未验证） |
| 4 FEAT-052 已发布而卡仍“开发中/未排期” | **已闭环**：`FEAT-052.md` 首屏已改“已交付（0.11.0；实机 28/28）” | 归档记录 |
| 4 建议：发布检查单“五处核对”纳入“新增能力对应 FEAT 卡状态” | 采纳，写入 `RELEASING.md` 第 8 步 | DEV-062（口径同步） |
| 5 其它：BUG-094 入队拒绝、BUG-092 有界退出、FEAT-008 三键化、recolor 契约细节、0.9.0 原件归档 | 均为历史交付，无新动作 | 归档记录 |
| 6 升级摘要：双包校验、覆盖 87 写、零补丁编译、注册五项不变、95 工具/9 种子 | 外部环境记录；本仓库不复用其哈希作发布依据 | 归档记录 |
| 7 未验证：FEAT-052 在 Creo 10 的实机行为、板厚三级回退、BUG-091 四现场 | 保持未验证，不由本机外推 | 各卡未测范围 |

### F03 `20261101_CREO_v0.11.0_N1已修复但flip方向依赖失败仍在_端点焊接连续三轮未修.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 一 R4：`extrude_depths` 与 schema 一致并标注 mode | **已闭环**（0.10.1 三键化，`tests/unit/test_t01_capability_contracts.py` 锁定） | 归档记录 |
| 一 R1：`gear10.json` 草图诊断齐、拉伸 `-1`，信息与 0.9.0/0.10.0 逐字相同 | **部分闭环**：0.11.2 交付 `profile.weldability` 风险标记与“簇内间隙”归因；**首版只报告不拒绝**，未做草图提交即拒绝，Creo 10 现场未复现 | BUG-101 增量 |
| 一 R2：`flip=false` 成功带 delta、`flip=true` 仍 `-1` 且无方向冲突归因 | **部分闭环**：`requested_flip`/`effective_flip` 与 `draft_failure` 已随 0.11.2 交付；**`pull_vector` 与冲突相邻面 id 归因、元素树 A/B 未做** | BUG-102 增量 |
| 一 R3：`creo_new_part` 空模型 `preview_status=failed`、`failed_step=output_file`、`-4`、FileNotFoundError | **开放**：`skipped_no_geometry` 已实现于 `native/preview.h` 与 `src/creo_mechdog/preview.py`，但 0.11.x 主干实测 empty_part 仍 failed（`DEV-053-Q01-handoff.md`），判定条件与实机路径未对齐 | BUG-088 增量 |
| 二 R4 已修：三键枚举与 `through_all` 仅用于 cut | 已闭环，正面 | 归档记录 |
| 三 R2：入参 `flip=false` 回显 `draft_geometry.flip:true` | 已闭环：回显拆为 `requested_flip`/`effective_flip`，`flip` 保留原值 | BUG-102 增量（已交付部分） |
| 三 R2 判据：surface 67 上 `angle=10, flip=true` 要么成功带 delta、要么指出方向冲突 | 作为 BUG-102 回归判据保留 | BUG-102 |
| 四 R1 建议 1：超过阈值在草图提交时拒绝并引用 `near_tolerance_pairs` | 未实现（首版只报告不拒绝，待实机证据决定门禁） | BUG-101 |
| 四 R1 建议 2：`native_section` 增 `weldable` 判定字段 | **部分实现**：以 `profile.weldability.weldable`（三态）+ `exceeding_pairs` 交付，位于草图结果而非 `native_section`；语义为风险标记 | BUG-101 |
| 四 R1 判据：`gear10.json` → extrude add blind 10 期望 `volume_mm3=1849.80285`；`gear10_snapped.json` 应继续通过 | 作为 BUG-101 回归判据；本机 12.4 未复现 `-1` | BUG-101 |
| 五 R3 建议：空模型返回 `skipped_no_geometry` | 采纳，但实现与实测路径未对齐，转 BUG-088 | BUG-088 |
| 六 正面清单：N1 回归修复、R4 拆分、95 工具、失败回滚干净、`near_tolerance_pairs` 稳定 | 归档记录 | — |
| 七 下一轮判据 R1–R3、R5（连续两次 draft 方向可从 `pull_vector` 预判） | R1→BUG-101；R2/R5→BUG-102；R3→BUG-088 | BUG-101、BUG-102、BUG-088 |

## 三、已闭环、本轮不重复派工

| 项 | 依据 |
| --- | --- |
| 种子包版本/摘要闸门与安装前校验 | BUG-089（0.8.2 / 0.10.1）、DEV-061（0.11.2 仓库级断言） |
| Creo 10 零补丁编译证据 | DEV-060 R10 Step 5 已回填 BUG-090（实机仍未验） |
| 盲孔 tip 口径的机器可读字段 | 0.11.2 交付 `depth_basis` 三键 + `tests/unit/test_hole_depth_basis.py` |
| FEAT-052 卡片状态滞后 | `FEAT-052.md` 首屏已改“已交付（0.11.0；实机 28/28）” |
| `extrude_depth_types`/`extrude_directions`/`extrude_through_all_modes` | 0.10.1 三键化并有契约测试 |
| draft `requested_flip`/`effective_flip` 与 `draft_failure` | 0.11.2 交付 + `tests/unit/test_draft_observation.py` |
| 近容差端点风险标记与拉伸失败簇内归因 | 0.11.2 交付 + `tests/unit/test_endpoint_weld_gate.py`（只报告不拒绝） |
| 失败作业回滚与 `rollback_status` | BUG-096 已随 0.11.1 交付 |

## 四、缺件与未验证

- F01 未附 `models/<id>/model.json` 与作业原始日志，仅有 job id 与组件计数；本仓库不复用其数值作为验收证据，只作复现输入。
- F02 未附 Creo 10 编译日志与注册表清单原件；其编译/注册结论记为外部证据，本仓库未复现。
- F03 仍未附 `gear10.json` / `gear10_snapped.json` 原文件（自 BUG-049 起即缺件），本批不构造替代夹具，也不声称逐字回放。
- 本机 Creo 12.4 实机、Creo 9/10 实机与 WorkBuddy 黑盒：本批均**未执行**，全部记为未验证。
- 本批代码改动只经离线单测与编译；原生“实读填基线”“全阶段 `model_unchanged`”的运行行为须由后续实机会话按 BUG-104/BUG-105 判据验收。
