# DEV-048 T03 验收记录：工作卡、台账与发布检查回填

日期：2026-10-27（Asia/Shanghai）。任务：[DEV-048](../work-items/DEV-048.md) T03。分支 `codex/dev048-t03-release-docs`，基于 T02 验收提交 `3aaf255`。范围：仅 `docs/` 下的工作卡、主台账、完成档案、发布规范与本记录；不改业务代码、版本、归档原件或 0.7.0 的标签／Release／附件。

## 1. 依赖与基线

| 项目 | 实际值 |
| --- | --- |
| T00 文档基线 | `c0a3e55b2124c2ae08cbf577cdbd4a3bd65b52b7` |
| T01 实现 | `23ddcb7371288008f0b599cf8ee1c83c5d561c2a` |
| T02 实现与收口 | `b65b14d8621e4347ca346f84d655ce5621975d09`、`07cc8e4ead08b86ce79a278f69d2718555a827c9`、`eef464ddadca09931d7d1dbe94d0c82bac3a06cb` |
| T02 验收提交（本分支起点） | `3aaf255b64cf04869aa5750f9431a38d8eb27e82` |
| main / `v0.7.0^{}` | 均为 `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d` |
| `version.py` | 0.7.0 |

核验命令与输出（本机，提交前）：

```text
$ git rev-parse --abbrev-ref HEAD
codex/dev048-t02-ref-lifecycle
$ git rev-parse HEAD
3aaf255b64cf04869aa5750f9431a38d8eb27e82
$ git rev-parse main
2a7835808e1ea2981df411c7e2a4e94d1fd4d92d
$ git rev-parse 'v0.7.0^{}'
2a7835808e1ea2981df411c7e2a4e94d1fd4d92d
```

工作区非干净，但与本次文档无关：`session_activity.json` 为保留的本机运行修改，另有 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/` 未跟踪文件。以上均未暂存、未提交、未删除。

## 2. 交付事实来源

只读核对本地标签与 GitHub Release API（2026-10-27），不以卡内旧“待发布”措辞反推：

| 版本 | 标签 / peeled 提交 | Release | 状态 | 附件 |
| --- | --- | --- | --- | --- |
| 0.5.1 | `v0.5.1`（轻量）→ `0d9715ded6322d2341e587b5575f9dfe0ce071b7` | [421562562](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.5.1) | `draft=false`、`prerelease=true`、2026-10-23T07:35:56Z | 4 |
| 0.5.3 | `v0.5.3`（轻量）→ `60c1895d47eb6645ebe850f33f67de9b34c645bf` | [423245388](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.5.3) | `draft=false`、`prerelease=false`、2026-10-25T08:16:46Z | 4 |
| 0.6.1 | `v0.6.1`（附注）→ `2af3853531ebba29fe2fa458f5a432224323ce76` | [423906789](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.6.1) | `draft=false`、`prerelease=false`、2026-10-26T06:07:51Z | 4 |
| 0.7.0 | `v0.7.0`（附注）→ `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d` | [424956318](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0) | `draft=false`、`prerelease=false`、2026-10-27T01:57:05Z | 4 |

0.7.0 四附件与正文一致：源码包 `39a8059ca1ef6b3c940731f046d97f6e98bdf0bb8dcc8e2e676ae2d5375191c8`、种子包 `515ef9d356a6d5582879fc736c43d0a7408fc15915605f04ded2bb5f991fd114`、两个 `.sha256` 为 `ea0071fef9d56d9a11796d8c0e49ec54d36ab7d0a73b7a84d9d9545d0b0e19b8`／`62279ee19f1cd68e5676f571cd49098a739e499675154c87e6a6b68a826d3417`。Release 正文另记录 main 提交 `2a78358`、966 项单元测试与安装冒烟；本地 [0.7.0 发布记录](../validation/RELEASE-0.7.0.md)未内嵌提交号，故以本机标签 peel 与 Release 正文互证。

冲突点与采信：

- 主台账原写“共 120 项”，实际表格为 121 行；BUG-080 未归入原分类表任何一行，其余 120 行可逐行归类。采信实测行数，移动 DEV-047 后按 120 行重算，并把 BUG-080 计入“验收中”。
- [DEV-047](../work-items/DEV-047.md) 首页原写“剩余安装冒烟与 0.7.0 发布”，与已发布的 Release、标签及 main 冲突。采信 Release 与标签，回填为已完成并移档。
- [BUG-079](../work-items/BUG-079.md) 原写“待发布／下一 PATCH”，与 0.5.1 已发布冲突。采信 0.5.1 发布记录与 Release。
- [BUG-081](../work-items/BUG-081.md)、[BUG-082](../work-items/BUG-082.md) 原已写对交付版本，本次只补 Release 链接、技术状态与剩余范围，不改变其“验收中”结论。
- 0.5.1 的 GitHub 标记为 Pre-release，0.5.3／0.6.1／0.7.0 为非 prerelease；按各自实际值记录，不统一改写。

## 3. 逐 ID 回填前后对照

| ID | 回填前首页 | 回填后技术状态 | 已交付版本 | 仍开放范围 |
| --- | --- | --- | --- | --- |
| [DEV-047](../work-items/DEV-047.md) | 进行中；T00—T13 已完成但“剩余安装冒烟与 0.7.0 发布”；主台账状态“验收中” | 已完成（安装冒烟、标签、Release、四附件与远端核对完成） | 0.7.0（main `2a78358`／`v0.7.0`） | WorkBuddy 未执行、外部 Creo 9/10 未复测、unknown 单位仅离线覆盖、BUG-078 三现场未 apply、BUG-066 原始失真未复现、FEAT-050／嵌套回放／新约束类型／世代二进制可复现性等父卡范围 |
| [BUG-079](../work-items/BUG-079.md) | 已修复，WorkBuddy 复验通过（待发布）；目标“下一未发布 PATCH” | 已修复（0.5.1 交付），外部范围验收中 | 0.5.1（`0d9715d`） | 外部 Creo 9/10 完整编辑矩阵未复测；非主平面、ellipse/spline、显式 `autodim` 既有边界；并发与构建指纹未验证 |
| [BUG-081](../work-items/BUG-081.md) | 验收中；已写“诊断已随 0.5.3 交付”，无 Release 链接 | 验收中（诊断已交付，停止判定未改） | 0.5.3（`60c1895`，诊断） | 实机 MCP 拒绝时序未复现、外部 Creo 9 未复测；迁移链路其余验收归 BUG-077 |
| [BUG-082](../work-items/BUG-082.md) | 已修复（验收中）；已写“交付版本 0.6.1”，无 Release 链接 | 已修复（验收中，本机修复范围） | 0.6.1（`2af3853`） | 外部 Creo 9 未复测；外部 coordinates/改半径失败未复现；非主平面／不支持实体边界；半圆/球体贴轴基线、失败作业 revision 未取得 |
| [DEV-048](../work-items/DEV-048.md) | 开发中（仅 T00 完成）；T03 未开始 | 开发中（T00—T03 已完成） | 本批未发布（目标暂定下一 PATCH） | T04 Right 面 ±Z、T05 集成与最终交付 |

父卡处理：只完成本批子项，未批量关闭任何父卡；BUG-081／BUG-082 保持验收中，外部与实机未测项未改为通过。DEV-047 的完成仅指其自身交付目标，不改变上述父卡范围。

## 4. 台账与唯一 ID 统计

统计脚本只解析 Markdown 表格行（`|` 开头且首列含固定 ID），不把正文提及计入行数。

| 项目 | 回填前 | 回填后 |
| --- | --- | --- |
| `docs/BACKLOG.md` 行数 | 121 | 120 |
| 唯一 ID | 121 | 120 |
| 重复 ID | 0 | 0 |
| 声明总数 | 120（与行数不一致） | 120（与行数一致） |

分类按行状态显式归类，合计 120＝118 项未完成工作＋2 项历史观察：

| 分类 | 数量 |
| --- | --- |
| 开发中 | 4 |
| 待复现 | 20 |
| 待核实 | 12 |
| 验收中 | 30 |
| 待规划 | 44 |
| 观察中 | 2 |
| 已交付/已修复/已验收（未收口） | 8 |

`docs/BACKLOG_COMPLETED.md`：55 行／55 个唯一 ID → 56 行／56 个唯一 ID（新增 DEV-047），与主台账交叉重复 0；两表合计 176 个唯一 ID。

工作卡文件：`docs/work-items/` 共 140 个 Markdown，其中规范 ID 卡 138 个，另有 `BUG-001-FEAT-018-RECOVERY.md`、`P1-MODELING-REPAIR.md` 两个联合/专题卡。39 个台账 ID 没有独立工作卡（历史条目直接记录在台账，属既有结构，本次不补卡）；`DEV-042` 是 BUG-019 的执行卡，不作为主台账行。台账行数与唯一 ID 一致（120＝120），与工作卡文件数不相等是上述既有结构所致，不是重复或漏计。

## 5. 发布检查扩展

[docs/development/RELEASING.md](RELEASING.md) 的第 8 项改为逐 ID 核对：本版交付的每个 ID 分别记录技术状态、交付版本、剩余范围，以及卡首页／主台账／版本说明／开发入口／实际 Release 五处链接，候选态与发布后各核对一次；不新建索引或自动工具。

新增第 9 项“相对上一正式包”的身份核对：`native/third_party/**` 原字节（含 `json.hpp` 与第三方许可）、回调指纹（继续使用 `sha256-repo-lf-v1` 的 CRLF→LF 归一化，不改算法）、loader／callback／worker 的 DLL SHA256、`protk.dat` 与实际注册表／安装路径。内容真实变更时按影响说明是否需要重新注册、迁移或重启；不要求所有哈希永远相同。

发布回归模板新增两张表：逐 ID 五处状态核对表，以及上一版/本版的身份对比表（含“实际注册影响：未变／需重新注册／需迁移／需重启”）。

## 6. 链接与 ID 核对结果

命令（本机仓库根，脚本在忽略的 `build/`，不入库）：

```powershell
.\.venv\Scripts\python.exe build/t03_links.py <本次改动的 9 个文档>
.\.venv\Scripts\python.exe build/t03_ids2.py
git diff --check
```

链接检查覆盖本次改动与新增的 9 个文档，解析 Markdown 相对链接、页内锚点、显式 `<a id>` 与标题 slug（外部 URL 不计入本地链接数）：

```text
FILES 9
LINKS 564 LOCAL_OR_ANCHOR 564 ANCHORS_CHECKED 18
MISSING_FILES 0
MISSING_ANCHORS 0
```

564 条均为可解析的本地链接或页内锚点；18 条跨文件片段锚点全部命中显式 id 或标题 slug。

ID 统计见第 4 节；`git diff --check` 无输出（exit 0），未发现行尾空白、空白行尾或混合缩进问题。

## 7. 未测与阻断

- 未运行任何单元测试、`dev_check`、原生构建或 SDK 编译；本任务仅为文档事实回填与人工清单扩展。
- 未启动 Creo、未连接 Toolkit、未做会话探测或故障注入、未运行建模回归。
- 未合入 main、未创建标签、未发布任何版本；本批仍为开发中，未宣称 0.7.1 已发布。
- 未修改 0.7.0 及历史版本的标签、Release、附件和既有发布记录正文；未改归档原件、业务代码或 `version.py`。
- T04、T05 未启动。最终发布前的逐 ID 候选核对与发布后核对仍由 T05 执行；本记录只证明 T03 文档与链接范围。

## 8. 本任务提交

- 起点：`3aaf255`（T02 验收提交）。
- 文档提交：`fa284fce7424d945f0ab7e0bd15463e15ade146e`（`DEV-048 T03: backfill delivered status and release checks`）。
- 记录提交：本文件所在提交（仅回填提交号，不改变结论）。
- 提交范围：`docs/BACKLOG.md`、`docs/BACKLOG_COMPLETED.md`、`docs/work-items/DEV-047.md`、`docs/work-items/DEV-048.md`、`docs/work-items/BUG-079.md`、`docs/work-items/BUG-081.md`、`docs/work-items/BUG-082.md`、`docs/development/RELEASING.md`、`docs/development/DEV048-T03-ACCEPTANCE.md`。
