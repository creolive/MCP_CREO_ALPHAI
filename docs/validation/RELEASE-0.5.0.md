# RELEASE 0.5.0 发布核对（2026-10-22）

## 交付内容

0.4.6 反馈整合计划第二批（MINOR，新增公开工具，按现行 MINOR 规则不延用 0.4.6 的 PATCH 例外）：FEAT-045 装配只读检查 `creo_inspect_session_assembly`。见[版本说明](../RELEASE_NOTES_0.5.0.md)与[实施与验收记录](FEAT045-ASSEMBLY-INSPECT-2026-10-22.md)。

## 版本链

- 开发分支 `codex/feat045-assembly-inspect` 提交 `4d19437`（自 main `c28dc23`，0.4.8 已发布）。
- 合入 main：merge 提交 + 种子清单/expected digest 定版 `b09d612`。
- 标签 `v0.5.0` → `b09d612`（与该提交 `version.py` 一致）；远端 main 已推送至 `b09d612`。
- GitHub Release `420300519`（`MCP_CREO_MechDog 0.5.0`，Pre-release，非草稿）。

## 附件与 SHA256（Release body 直接列出，DEV-045 第 7 项）

- 源码包：`MCP_CREO_MechDog-0.5.0-source.zip`（751 文件）SHA256 `dd8b49bb743fbbe3492aa46444e218dbec9096eb69746d08c0265cbdf4d90626`。
- 种子包：`MCP_CREO_MechDog-0.5.0-seed-library.zip`（24 文件、9 种子）SHA256 `fb84a37d737621d371d06429048c43d7412ce1413029085203195a3a13445353`（与 `seeds.py` expected_digest 一致；种子内容较 0.4.8 未变，清单版本随版）。
- 各附同名 `.zip.sha256`。

## 远端核对

- 四附件已上传（source 4,340,265 字节、seeds 493,394 字节、两个 sha256 文本）。
- 远端附件逐项下载复核：source/seeds 哈希与本地及 body 记载完全一致（REMOTE_VERIFY: PASS）。
- 发布后补录：本记录与回填提交在 Release 发布后进入 main，不改变 `v0.5.0` 标签与附件。

## 验收与环境

- 单元 544 项（含 FEAT-045 新增 5 项与工具数契约 90→91）、`tools/dev_check.py`、SDK 构建通过；本机 Windows x64 / Creo Parametric 12.4.0.0 / E 盘 dev 服务（stdio 直连公开 MCP 工具）实机验收：托管链与外部装配（open_file 载入）检查、变换与放置平移逐位一致、约束快照、limit=1 三页分页、结构化拒绝、会话不变。
- 未测范围（随版披露，不外推）：嵌套子装配/重复实例/抑制/缺件四场景实机触发（本机构造手段受限：assemble_component 不支持嵌套插入、受管插入即复制快照、无抑制工具、缺件 fixture 被搜索路径解析；native 路径与单测覆盖）；外部 Win10/Creo 10 复核；WorkBuddy 黑盒（提示词 [WORKBUDDY-0.5.0-FEAT045](../development/WORKBUDDY-0.5.0-FEAT045-2026-10-22.md)）。
- 已知问题：BUG-078（恢复 accept 路径 `ProMdlnameBackup` 稳定 -1）待排期；BUG-077 原环境（track_p01b）迁移复测与 485 条旧登记批量迁移开放。
- 0.4.6 反馈整合计划两批全部随版交付；矩阵放置、重建编辑与装配整体收养为后续路线（登记于 FEAT-045 卡与台账）。
