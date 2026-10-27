# DEV-049 T07 验收记录：当前文档与台账一致性收口（2026-10-28）

任务：[DEV-049](../work-items/DEV-049.md) T07，按[派发表](0.6.1-FEEDBACK-TASKS-2026-10-27.md#t07当前文档与台账一致性)执行。范围：只改当前摘要、台账与卡首页，历史日期段与 `docs/validation/` 原件不动。**未改业务代码、未连接 Creo/Toolkit、未改 `version.py`、未合 main、未推标签、未发布、未实施 T08。**

## 一、交付身份

| 项 | 值 |
| --- | --- |
| 日期 | 2026-10-28（Asia/Shanghai） |
| 任务分支 | `codex/dev049-t07-docs`，自集成分支 `codex/dev049-feedback061` 顶端 `97120a7` 建立 |
| 依赖提交 | `97120a7`（DEV-049: integrate T06 offline seed-matrix driver） |
| 上游阶段记录 | [T00](DEV049-T00-ACCEPTANCE.md)—[T06](DEV049-T06-ACCEPTANCE.md) |
| 版本入口 | `version.py = 0.7.1`（本任务未改） |
| 引用版本 | `main = d2e37b0ed98aa01dec3d76f824703f0980ddb8c5`；`v0.7.1` 附注标签对象 `0c7ee341540910cebf782848dcf187a91dd63b01`，peeled → `ffa0a433736917812d1040dba7c6d7190b5f82f6` |
| 工具面 | `server.py` 中 `creo_*` 定义 94 个（未改） |
| 环境 | Windows 11 Enterprise x64、git 2.50.1.windows.1；未启动 Python 分析、未连接 Creo |
| dirty | 开工时 `M session_activity.json` 与未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/*`（共 33 条）；全部为本机运行数据，未提交、未 stash、未 checkout |

## 二、核对依据（能力现状按已发布证据判定）

核对不以“待规划/待实施”旧文案为准，逐项以发布证据确认能力是否存在：

| 依据 | 用途 |
| --- | --- |
| [RELEASE_NOTES_0.7.0.md](../RELEASE_NOTES_0.7.0.md)、[RELEASE-0.7.0.md](../validation/RELEASE-0.7.0.md)、[T13 记录](DEV047-T13-ACCEPTANCE-2026-10-26.md) | 0.7.0 交付：T05 毫米矩阵 18/18、T08/T13 特征状态实机、T11 `creo_reclaim_generations` |
| [DEV047-T05 记录](DEV047-T05-ACCEPTANCE-2026-10-26.md) | 倾斜面/主平面拉伸 9 例与偏心两平面交线轴、柱面轴阵列 9 例的实机通过范围 |
| [DEV048-T04 记录](DEV048-T04-ACCEPTANCE.md)、[RELEASE_NOTES_0.7.1.md](../RELEASE_NOTES_0.7.1.md)、[RELEASE-0.7.1.md](../validation/RELEASE-0.7.1.md) | Right 面 `u_axis=±Z` 实机、实际帧、平行法向回滚；0.7.1 未测范围 |
| [T01](DEV049-T01-ACCEPTANCE.md)—[T06](DEV049-T06-ACCEPTANCE.md) | 本轮真实结论：根因未定、CLI 契约、六例/替代用例/15+2 的离线与实机边界 |
| `capabilities.py`（`generation_reclaim.enabled=true`、`tool=creo_reclaim_generations`） | 确认显式世代回收已实现，未据“未排期”旧文案判为缺失 |

## 三、修改文件

| 文件 | 改动要点 |
| --- | --- |
| `README.md` | 装配行改为矩阵放置子项已实机（0.6.0，38 父作业含故意失败回滚），显式源件更新/嵌套仍开放；倾斜拉伸、两平面交线轴、偏心阵列改记 0.7.0 T05 Live03 18/18 并列出未覆盖面；`creo_adopt_file` 的 “pending native acceptance” 改为契约与实机范围；补 `creo_reclaim_generations` 能力行（正文此前已声明该能力，表中缺工具） |
| `docs/BACKLOG.md` | 首段改为 0.7.1 标签/主干分离事实与 DEV-048 已交付；当前安排更新 0.6.1、0.6.0、0.5.2、0.5.0/0.5.1 四条；删除 DEV-048 行并更新 DEV-049 行；BUG-085/086/084/064/049/066、DEV-027、FEAT-030、FEAT-036、FEAT-027、DEV-050 行改写当前摘要；分类表与总项数重算 |
| `docs/BACKLOG_COMPLETED.md` | 头部登记追加；已完成表首新增 DEV-048（0.7.1、四附件、T01—T05、未测范围）；“当前源码已到 0.3.5”改为 0.7.1 |
| `docs/DEVELOPMENT.md` | 标注当前批次 DEV-049 与已交付 0.7.1 的区别；补 `--unit-timeout-seconds` 语义与示例、`Invoke-PipStep` 安装判定语义；新增「DEV-049 批的离线与实机驱动」表（三个驱动的参数、双门槛与“离线结论不等于实机通过”） |
| `docs/INSTALL.md` | 头部当前版本 0.3.5 → 0.7.1（含 BUG-085 根因未定提示）；新增「升级与部署核对」四项（版本/路径/启动身份/工具清单）；0.3.0 节的历史 `version == "0.3.0"` 步骤改为与该 Release 一致并指向新节；AI 客户端第 1 步改为核对版本与工具清单（0.7.1 = 94） |
| `docs/work-items/DEV-048.md` | 目标版本改为 0.7.1（已发布） |
| `docs/work-items/DEV-049.md` | 状态行与阶段表 T01—T07 状态改为实际（T04/T05/T06 明确“仅离线”） |
| `docs/work-items/BUG-064.md` | 新增 0.7.1 段：Right 面 ±Z 与平行法向子项实机通过、实际帧/800 mm³/重载，保留外部原报文、无基准轴倾斜草图与 T04 六例未执行 |
| `docs/work-items/BUG-084.md` | 同上，并写明“三种引用等价性未做对照”、T04 只覆盖 `datum_plane.id` 一种 |
| `docs/work-items/FEAT-036.md` | 状态改为已交付（0.7.0，本机实机通过），剩余组/阵列头随动、外部环境与 WorkBuddy |
| `docs/work-items/DEV-027.md` | 当前范围补 0.7.0 显式世代回收（inspect/apply、令牌、幂等、保留集合），明确真实世代删除未执行 |
| `docs/development/DEV049-T07-ACCEPTANCE.md` | 本记录（新建） |

`docs/validation/` 下任何文件、T00—T06 记录、两份反馈计划与原件均未修改。

## 四、一致性核对结果（逐项）

| 核对项 | 结论 |
| --- | --- |
| BACKLOG 首段不再称 DEV-048 开发中 | 通过：改为 0.7.1 已交付并移档，下一 PATCH 归 DEV-049 |
| DEV-048 目标版本与实际交付一致 | 通过：卡与台账均为 0.7.1，记录移入完成档案并保留未测范围（WorkBuddy、外部 9/10、`native_acceptance=partial`、历史现象不在范围） |
| BACKLOG 当前安排不再称 T04/T05 未实施 | 通过：0.6.0 批次改为 T04 实机通过、T05 已随 0.7.1 发布 |
| README 倾斜面/两平面轴/偏心阵列 | 通过：改为 0.7.0 T05 Live03 18/18 已通过，未覆盖面单列（外部 9/10、非毫米/unknown、无基准轴倾斜草图） |
| README 矩阵装配子项 | 通过：改为 0.6.0 实机通过（38 父作业），显式源件更新/嵌套仍开放 |
| BUG-064/084 当前摘要 | 通过：补 Right±Z 实际帧证据与 0.7.1 交付；外部原报文、原构型、T04 六例未执行如实保留，两卡均未关闭 |
| DEV-027 显式回收 | 通过：确认工具已随 0.7.0 交付（`capabilities.py:238` `enabled=true`）；真实世代删除仍只到只读盘点 |
| FEAT-036 / FEAT-027 | 通过：0.7.0 交付并 T13 实机验证（抑制/恢复/删除/墓碑/旧标签重建被拒）；剩余范围保留，ID 未拆分 |
| FEAT-030 种子矩阵 | 通过：15+2 驱动与清单离线就绪，实机未执行；0.6.1 的 five_smooth 不移植；卡保持验收中 |
| BUG-079 / BUG-081 / BUG-082 | 核对一致，未改写：0.5.1 / 0.5.3 / 0.6.1 交付事实与未测子项与卡相符 |
| BUG-085 / BUG-086 / DEV-050 | 通过：BUG-085 保持根因未定；BUG-086、DEV-050 卡已为“本阶段完成”，台账改为一致表述且未写成整卡关闭 |
| INSTALL 当前升级步骤 | 通过：不再要求固定版本号，改为核对 Release 版本、路径、启动身份与工具清单 |
| T01—T06 结论与 CLI 纳入 | 通过：DEVELOPMENT 记录 `--unit-timeout-seconds`、`Invoke-PipStep`、三个驱动与双门槛；台账逐条引用阶段记录 |
| 阶段完成 vs 全卡关闭 | 通过：T04/T05/T06 在台账、卡与 README 中均写“离线完成、实机未执行”，未关闭 BUG-049/064/066/084 或 FEAT-030 |
| 唯一 ID | 通过：BACKLOG 123 行对应 123 个唯一 ID，无重复；DEV-048 仅存在于完成档案 |

## 五、分类计数与唯一 ID（逐行重算）

按行状态归类（`docs/BACKLOG.md` 表格逐行解析，共 123 行）：

| 分类 | 数量 | 构成 |
| --- | --- | --- |
| 开发中 | 4 | DEV-049、DEV-046、DEV-002、DEV-030 |
| 待复现 | 21 | 22 行减 BUG-086（转入已修复） |
| 待核实 | 12 | 11 行 + BUG-045 |
| 待开发 | 0 | DEV-050 已由 T02 实施，转入下行 |
| 验收中 | 30 | 27 行 + BUG-081、FEAT-048、BUG-080 |
| 待规划 | 42 | 41 行减 FEAT-036/FEAT-027，含 FEAT-008、FEAT-010、FEAT-012 |
| 观察中 | 2 | BUG-021、BUG-005 |
| 已交付/已修复/已完成/已验收（未收口） | 12 | 原 8 项 + FEAT-036、FEAT-027、BUG-086、DEV-050 |

合计 4+21+12+0+30+42+2+12 = **123**，与总项数一致；未完成工作 121 项、历史观察 2 项。上一版为 124 行（DEV-048 移档后减 1）。

## 六、链接检查

对本任务修改与新建的 12 个 Markdown 抽取全部相对链接并解析到仓库根：共 697 处引用、**336 个唯一目标、0 缺失**。新增链接均为已存在的阶段记录（`DEV049-T00`—`T06`）、发布记录（`RELEASE-0.7.0`／`0.7.1`、`RELEASE_NOTES_0.7.1`）、工作卡或 `version.py`；本记录对派发表使用 `#t07当前文档与台账一致性`，与 `### T07：当前文档与台账一致性` 的锚点一致。

## 七、未测项与边界

- 纯文档任务：未运行单元测试、`tools/dev_check.py` 或任何 `tools/test_*.py`；未构建 SDK。
- 未连接 Creo/Toolkit、未启动或结束 Creo、未探测、未清 unknown/保护、未对 BUG-078 旧现场 apply。
- 未改 `version.py`、业务代码、原生代码、`server.py`、工具清单；未合 main、未推标签、未发布。
- 未动 `session_activity.json`、`session_erase/`、客户端目录与 `docs/validation/` 原件。

## 八、未回填项（等待 T08 或后续指派）

1. **版本与发布**：`version.py`、README 首页版本、Release 说明仍为 0.7.1；0.7.2 的版本号、说明、main/标签/Release/四附件与哈希核对由 T08 执行。
2. **实机未执行**：T04 六例（单向 238.390260127791／双向 476.780520255582 mm³）、T05 三个替代用例、T06 15+2。台账已按此表述，未解除 FEAT-030 验收中，未关闭 BUG-049/064/066/084。
3. **BUG-085**：根因未定，保持待复现；未重开 BUG-056、未清保护，断连后稳定性未复测。
4. **BUG-086 / DEV-050**：真实新目录 `setup.ps1` 安装（PS5.1、notice 不误报、可编辑包版本、九种子哈希、原生构建）与统一入口全量 `dev_check` 未执行。
5. **环境**：外部 Creo 9/10 未复测、本机无 Creo 9 SDK；WorkBuddy 黑盒按用户 2026-10-26 决定未执行。
6. **范围外发现（本次未改）**：`docs/MIGRATION.md` 第 3、25、34、38 行仍是 0.3.0 时代表述，其中第 34 行 `version == "0.3.0"` 与本任务修正的 INSTALL 同类问题；该文件不在本次指定文件清单内，按“只改当前摘要、不把历史版本说明改写成当前版本”的边界留给后续条目或 T08 决定。

## 九、偏离说明

1. 命令执行使用 PowerShell（本环境 Bash 通道实为 cmd），命令语义未变。
2. 分类计数由脚本按 `docs/BACKLOG.md` 行状态逐行解析得出，口径与表中“归类口径”一致；`待开发` 归零后保留该行并说明原因，不删行凑数。
3. README 增补 `creo_reclaim_generations` 行属能力面补全（正文第 7 行此前已声明“显式世代回收”，表中无对应工具），未新增或改动任何工具。
4. 台账 BUG-086 行由“待复现”改为“已修复（本阶段完成；真实安装待 T08）”，与卡状态一致；未把阶段完成写成整卡关闭。
