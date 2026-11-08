# DEV-077 离线验收记录（2026-11-08）

范围：四份 0.18.2 反馈对比后的离线补漏。工作卡 [DEV-077](../../work-items/DEV-077.md)、[逐项对照](MAPPING.md)、[接手清单](../../development/DEV-077-HANDOFF.md)、[原件身份](manifest.json)。

## 环境与源码身份

- Windows x64；`.venv` Python `3.12.14`；仓库 `E:\Projects\MCP_CREO_MechDog`。
- 分支 `offline/0.18.2-feedback-gapfill`，起点 `4bd6b7e`（DEV-076 / `version.py = 0.18.4`）；**dirty = true**。除本批改动外，开始时已有的 `docs/work-items/DEV-054.md`、`DEV-066.md`、`.trae/`、`docs/superpowers/plans/2026-11-06-feat-014-miter-cuts-route.md` 未提交内容保留，不纳入本批。
- 没有连接 Creo/Toolkit、没有启动或结束 Creo 会话、没有故障注入、没有清 unknown 保护、没有联网核对远端、没有改 `version.py`、没有合 main 或发布。本批没有 C++ 改动，因此未重新编译原生执行器。

## 原件归档

四份 md 从 `C:\Users\Administrator\Downloads\0.18.2` 复制到 `docs/validation/feedback-0.18.2-2026-11-08/originals/`，逐份 `Get-FileHash -Algorithm SHA256` 比对结果 **4/4 identical=True**；字节数与摘要写入 `manifest.json`。`tools/package.py::source_files()` 的目录扫描包含 `docs/**/*.md`、`src/creo_mechdog/*.py`、`tools/*.py`、`tests/*.py`，实测新增的 4 份原件、manifest/MAPPING、`backlog_counts.py`、两个测试与 CLI 均在源码包白名单内。

## 先红后绿（每条代码修复都有针对性用例）

| 用例 | 红（原因） | 绿 |
| --- | --- | --- |
| `test_mass_properties.py::test_conflicting_receipt_error_names_the_bounded_raw_fields` | FAIL：拒绝文本没有 `density_source` / `mass_unavailable_reason` / `mass_g` | 30 tests OK |
| `test_native_stage.py` 三条 `verify_stages` 用例 | 3 errors：`stall_report()` 不接受 `verify_stages` | 21 tests OK |
| `test_job_stage_reporting.py::test_failed_job_uses_verify_stages_when_log_is_truncated` | FAIL：`reason == "no_stage_timing"`（bridge 未传回执） | 10 tests OK |
| `test_backlog_counts.py` 六条 | ImportError：`creo_mechdog.backlog_counts` 不存在 | 6 tests OK |
| `test_backlog_counts_cli.py::test_isolated_copy_without_site_packages_still_exits_zero` | FAIL：`python -I -S` 隔离副本报 `ModuleNotFoundError: creo_mechdog` | 1 test OK |

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest discover -s tests` | **Ran 2990 tests in 400.996s / OK**，exit 0；无失败、无错误 |
| `.venv\Scripts\python.exe -m ruff check <本批 9 个改动文件>` | `All checks passed!`，exit 0 |
| `.venv\Scripts\python.exe tools\check_backlog_counts.py` | exit 0；`declared/actual = 168（BUG 75、FEAT 61、DEV 32）`、`category_total=168`、`duplicates=[]`、`problems=[]` |
| 四份原件 SHA256 比对 | 4/4 逐字节一致 |
| 新增文档相对链接检查 | MAPPING / DEV-077 / HANDOFF 的相对链接目标全部存在（ACCEPTANCE 自身为最后补入） |

全量单测输出中的 `WARNING:creo_startup:Creo startup failed (ValueError)`、`live runs require --confirm-session-usable`、`Refusing to overwrite an existing report` 与 `asyncio` 慢回调警告均为既有测试夹具/守卫的预期日志，不是本批失败项；`docs/seed_package.json matches this rebuild` 属打包回归用例输出。

## 文档回填的证据边界

- `docs/development/RELEASING.md` 第 8 步与 DEV-075 逐 ID 表按 [DEV-075 卡首页](../../work-items/DEV-075.md) 同步；`docs/BACKLOG.md` 登记 DEV-077 后计数为 168，三方自检一致。
- `docs/development/RELEASE-POSTCHECK-2026-11-07.md` 的 v0.18.2 段四附件 SHA256/字节、标签提交、发布时间与 `--tag` exit 0 **全部来自本批归档原件的报告方实测**（取值时间 2026-11-07 18:22 +08:00），本轮未联网重跑、未重新下载重算；精确 tag 的当轮远端核对仍是 [G12](../../development/DEV-077-HANDOFF.md)。
- `docs/validation/RELEASE-0.18.2.md` 等历史发布前原件保持字节不变，不回写旧 tag 或附件。

## 未测范围

Creo 9/10 实机建模与黑盒验收、WorkBuddy 公开 MCP 回归、原生几何能力（quilt_merge / 曲面放样 / 边界 fill / offset / round / 曲率分析）、草图容差链与旋转矩阵参数、Creo 9/10 SDK 编译、GitHub Release 远端四附件与 body 核对、源码包解压后的全量分发回归（本批只做白名单静态核对与 CLI 隔离副本用例）。全部余项见 [DEV-077 接手清单 G01—G13](../../development/DEV-077-HANDOFF.md)。

## 合并 v0.19.0 后的复验（2026-11-08）

用户随后要求把已发布的 v0.19.0 合并进本分支。详细对比与冲突取舍见 [COMPARE-0.19.0.md](COMPARE-0.19.0.md)。

- 合并前：备份 16 个未跟踪文件到 `build/merge-0.19.0-20261108/untracked-cache/`，记录 `pre-merge-status.txt` / `pre-merge-head.txt`，已跟踪改动放入 `git stash`（引用保留）。
- `git merge --no-ff --no-commit v0.19.0`：3 个冲突（BACKLOG / COMPATIBILITY / capabilities）；手工收敛后提交 `006e357`。`git stash pop`：2 个冲突（BACKLOG / capabilities）；手工收敛后 `git reset` 恢复未暂存状态。
- 双方关键字检索均存在；`version.py` 为 0.19.0；`docs/BACKLOG.md` 计数 168、DEV-077 行与 0.19.0 发布入口并存。
- 复验命令：`python -m unittest discover -s tests` → **Ran 3065 tests in 496.992s / OK**，exit 0；`python -m ruff check <14 个合并相关 Python 文件>` → `All checks passed!`；`git diff --check` exit 0；`python tools/check_backlog_counts.py` exit 0（168 / 75 / 61 / 32）。
- 日志中的 `v9.9.9: release assets are incomplete`、`--reps must be at least 1`、`Creo startup failed (ValueError)`、`live runs require --confirm-session-usable`、`Refusing to overwrite an existing report`、asyncio 慢回调均为既有负例/夹具输出，不是合并引入的失败。
- 本轮未连接 Creo、未重新编译原生执行器（合并后 C++ 同时含 0.19.0 与另一 AI 的改动）、未跑 WorkBuddy 黑盒、未联网核对远端、未跑源码包解压后的分发回归、未合 main、未发布。

结论：本批离线项完成，合并 0.19.0 后有 3065 项单测与定向门禁支撑；**未合 main、未发布**。将来合入 main 需选未发布新版本（不得复用已发布的 0.19.0），按 `RELEASING.md` 同次完成 Release 与四附件（两个 ZIP 及各自 `.zip.sha256`），发布后运行 `tools/check_release_assets.py --tag v<版本>` 并回填 POSTCHECK。当前未完成项见 [R01—R08](../../development/DEV-077-HANDOFF.md)。
