# DEV-049 T00 验收记录（基线核对、0.6.1 反馈归档与工作项登记）

日期：2026-10-27（Asia/Shanghai）。任务：[DEV-049](../work-items/DEV-049.md) T00，按[派发表](0.6.1-FEEDBACK-TASKS-2026-10-27.md)与[总计划](0.6.1-FEEDBACK-PLAN-2026-10-27.md)执行，仅文档与只读核对。

## 范围与边界遵守

- 未实施 T01—T08 任何内容；未连接 Toolkit/SDK/Creo；未运行单元测试或 `tools/test_*.py`/`dev_check.py`；未改 `version.py`（仍为 0.7.1）；未合入 main、未推标签、未发布。
- 未触碰 `session_activity.json`、`session_erase/`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1` 等本机运行数据；未修改 `docs/validation/` 下任何历史原件。
- 提交按精确路径执行（`git add -- <paths>`），未使用 `git add .`。

## 依赖与实现提交

| 项目 | 值 |
| --- | --- |
| 基线（依赖提交） | `d2e37b0ed98aa01dec3d76f824703f0980ddb8c5`（本地与远端 main，0.7.1 发布后文档回填） |
| 已发布对照 | `v0.7.1` 附注标签 `0c7ee341…`，peeled → `ffa0a433736917812d1040dba7c6d7190b5f82f6`；`ffa0a43..main` 仅 `d2e37b0` 一笔，差异入 [T08 交付差异清单](../work-items/DEV-049.md#t08-delivery-gap) |
| 开发分支 | `codex/dev049-feedback061`（自 `d2e37b0` 建立） |
| 实现提交 1 | `354ceff0be7048dd0304872ee3e6dd781c93b5b4` `DEV-049 T00: archive 0.6.1 feedback, register work items and shared baseline`（两份计划、归档目录 4 文件、`.gitattributes`、四张新卡、主台账本批登记，共 12 文件） |
| 实现提交 2 | 本记录与 manifest 日期字段修正（`git log --oneline -- docs/development/DEV049-T00-ACCEPTANCE.md` 查询） |
| dirty 状态 | 记录时工作区 dirty=true，全部为本机运行数据（`session_activity.json` 已修改，`session_erase/`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1` 未跟踪）；不属于本任务，均未提交 |

## 受测指纹

| 项目 | SHA256 / 值 |
| --- | --- |
| `pyproject.toml` | `4b786c9741c35ba69a3e27a08b686fbf2989821d4ab8d1daf00fe9889e09d0aa` |
| `.clang-format` | `b084ba4a767e8fede2f3d47e7dfb3ae120528cb76fceb113ce27e3dd7e0a77a0` |
| `requirements-dev.txt` | `f325c41a3f7288bd4dfb08310276c9790b1ca5fcafc9bd68704559b64ec5decc` |
| `version.py` | `9a77bb5fa971118878bb327498dab3845f168fffe170657076e0ba51dc178e19`（内容 0.7.1，未修改） |
| 原件 1（11935 B） | `5d94503c86de300e4368321da9589ca4b2c2bb3cc367ca0b10a82893283ea298` |
| 原件 2（10598 B） | `5ea9400a4f8014b43b01c0e9151fbdbfd0636fceaa58f89eb6f751d7eb1671f9` |
| 归档环境 | Windows-11-10.0.26100-SP0、Python 3.12.14、git 2.50.1.windows.1；toolkit_connected=false、tests_run=false |

## 核对命令与原始结果

**1）计划 ID 占用（工作区 + docs 全文检索）**：`DEV-049|BUG-085|BUG-086|DEV-050` 在 `docs/` 仅命中两份计划文档自身的计划编号表述，`docs/work-items/` 无同名卡、主台账无对应行 → 未被并行工作占用，无同目标条目可复用，按计划新建四张卡。

**2）远端只读核对（未移动标签、未覆盖附件）**：

```
> git ls-remote origin main "refs/tags/v0.7.1*"
d2e37b0ed98aa01dec3d76f824703f0980ddb8c5        refs/heads/main
0c7ee341540910cebf782848dcf187a91dd63b01        refs/tags/v0.7.1
ffa0a433736917812d1040dba7c6d7190b5f82f6        refs/tags/v0.7.1^{}

> git rev-parse main                                  → d2e37b0ed98aa01dec3d76f824703f0980ddb8c5
> git rev-parse "v0.7.1^0"                            → ffa0a433736917812d1040dba7c6d7190b5f82f6
> git rev-parse "refs/tags/v0.7.1"                    → 0c7ee341540910cebf782848dcf187a91dd63b01
> git log --oneline ffa0a43..main
d2e37b0 DEV-048 T05: backfill 0.7.1 release evidence and ledger state
> git merge-base --is-ancestor ffa0a43 main           → exit 0
```

GitHub REST API（`GET /repos/wudahua/MCP_CREO_MechDog/releases/tags/v0.7.1`，只读）：`id=425556084`、`tag_name=v0.7.1`、`draft=false`、`prerelease=false`；4 个附件的 size/digest 为 `MCP_CREO_MechDog-0.7.1-source.zip` 5365479 B `sha256:b2237884fcba39011fdcf445ba601036c2caba55b9cccbaff295987769b55542`、`source.zip.sha256` 101 B `08a27c5a…`、`seed-library.zip` 493394 B `53b3d391…`、`seed-library.zip.sha256` 107 B `cdab6ba5…`，与 [RELEASE-0.7.1](../validation/RELEASE-0.7.1.md) 发布后核对表一致（本轮未重新下载附件，未重复哈希下载件）。**结论**：远端 main、v0.7.1 标签与 Release/附件状态均确认，与本地一致；main 领先标签一笔文档回填。

**3）原件哈希与字节（下载源，只读）**：`Get-FileHash SHA256 C:/Users/Administrator/Downloads/0.6.1/*.md` → `5D94503C86DE300E4368321DA9589CA4B2C2BB3CC367CA0B10A82893283EA298`（11935 B）、`5EA9400A4F8014B43B01C0E9151FBDBFD0636FCEAA58F89EB6F751D7EB1671F9`（10598 B），与派发表 T00「原件身份」表逐字一致。

**4）归档与入库逐字节核对**：以 `git show HEAD:<归档路径>` 取入库 blob 重算 SHA256，与下载源比较：

```
MATCH 11935 5d94503c86de300e4368321da9589ca4b2c2bb3cc367ca0b10a82893283ea298
MATCH 10598 5ea9400a4f8014b43b01c0e9151fbdbfd0636fceaa58f89eb6f751d7eb1671f9
```

`.gitattributes` 仅新增 `docs/validation/feedback-0.6.1-2026-10-27/2026*.md -text`（原件保护），映射/manifest 不加 `-text`，历史目录未动。

**5）章节映射与 manifest 校验**：`manifest.json` JSON 解析通过（UTF-8）；R1 15 个章节、R2 17 个章节（合计 32）与原件标题逐行比对 `headings match: True`；回复请求 5 条（R1-Q1—R1-Q5）在 MAPPING「回复请求逐条结论」逐条有结论。数值更正与事故口径更正只写入 [MAPPING](../validation/feedback-0.6.1-2026-10-27/MAPPING.md)，未改原件。

**6）相对链接、锚点与 ID 唯一性**：对本批新增/修改的 7 个 Markdown/JSON 文件抽取 264 条相对链接逐一核对目标文件与锚点，除 4 条指向本记录（`DEV049-T00-ACCEPTANCE.md`，随第二笔提交落地）外全部有效，提交后复核为 0 问题；主台账中 `DEV-049`/`BUG-085`/`BUG-086`/`DEV-050` 各 1 条任务行，无重复 ID；台账 ID 行合计 37 行（分类全量重算按约定归 T07，本批仅登记）。

## 结论（对照派发表 T00 验收）

| 验收项 | 结论 |
| --- | --- |
| 两原件与源目录逐字节一致 | 通过（下载源、工作区副本、入库 blob 三方 SHA256 一致） |
| 全部章节/请求均有结论 | 通过（32 章节 + 5 回复请求，事实/建议/推断/回复请求分列） |
| 后续窗口能从提交读取两份计划、共享基线和新卡 | 通过（提交 1 含两计划、DEV-049 接口基线与 T08 交付差异清单、四卡、台账登记） |
| 未实施代码或实机任务 | 通过（零代码变更、零 Creo/SDK/测试运行） |
| 断连事故口径 | 已更正：事故发生于作者本机 Creo 12.4.0.0 的 0.6.1 验收（FEAT-030），非外部 Creo 10 新复现；R1 为未连接 Toolkit 的静态报告 |
| 体积数值口径 | 已更正：原报告 ≈478 为双向近似；单向 238.390260127791、双向 476.780520255582 mm³（不改原件） |

## 未测项与偏离说明

未测项：未运行单元测试/开发检查（任务书禁止）；未连接 Toolkit、未核对 BUG-001 会话条件（本任务不需要）；未重新下载 Release 附件做下载件哈希复核（引用 0.7.1 发布记录的三方核对，本轮仅 API 只读核对 size/digest 字段）；外部 Creo 10 环境报告数据均属报告人环境，未独立复核；T01—T08 未实施。

偏离说明：

1. 命令执行使用 PowerShell（本环境 Bash 通道实为 cmd），原始输出按 PowerShell 记录，命令语义未变。
2. 远端 Release 核对改用 GitHub REST API（本机无 `gh` CLI），为只读操作。
3. 提交拆为两笔（产出、本记录/manifest 日期字段修正），均为 T00 产出，未混入其他文件。
4. 主台账除登记本批 4 行外同步更新了分类计数（开发中 5、待复现 22、新增「待开发」1、合计 124）以保持「行数=唯一 ID」陈述真实；全量分类重算仍归 T07。
5. `manifest.json` 的 `archived_at` 采用日期标记（未记录精确时刻），已在第二笔提交中由 `2026-10-27T00:00:00+08:00` 改为 `2026-10-27`，避免伪精确。
