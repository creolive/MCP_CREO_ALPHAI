# Release 0.7.2 发布验收记录

版本与条目：`0.7.2`（PATCH），[DEV-049](../work-items/DEV-049.md) 0.6.1 两份反馈后续批次（T00 基线与原件归档、T01 断连离线核对（BUG-085，结论证据不足、根因未定）、T02 `dev_check` 超时修复（DEV-050）、T03/T08 安装误报修复（BUG-086，含 T08 批内补充）、T04 原斜槽六例（BUG-087）与 Right 面回归、T05 多环/预览查缺、T06 种子 15+2（FEAT-030）、T07 文档收口、T08 集成与交付）。本版同时覆盖 0.7.1 发布后的主干回填提交 `d2e37b0`（DEV-049 T08 交付差异清单 GAP-1/GAP-2）。公开工具数 94，与 0.7.1 相同，不新增工具。

日期与环境：2026-10-28（Asia/Shanghai）；Windows 11 Enterprise x64、Python 3.12.14、Creo Parametric 12.4.0.0（`release_numeric=44`）、匹配 Toolkit SDK、MSVC x64、Windows PowerShell 5.1.26100.9711、ruff 0.17.0、clang-format 23.1.3。

## 受测源码

| 项目 | 值 |
| --- | --- |
| 版本定稿提交 | 本记录随定稿提交一同入库；合入 main 的提交、附注标签 `v0.7.2` 对象与 Release 以 GitHub 为准（记录内自指提交号不可行，同 0.7.1 先例）。T08 代码修复提交 `7e96c14fe9e1e2c99011f745661f5a295c544802`（BUG-086 批内补充修复） |
| 记录时工作区 | dirty=true（本记录与版本/文档定稿尚未提交；其余为 `.gitignore` 内的本机运行数据 `session_activity.json`、`session_erase/`、`.codebuddy/`、`.workbuddy/`、`.zcode/`） |
| `checked_source_sha256` | `6b9aaadd21fefaa35f32c6b511d78e198eb62bd0270073c9f9000a59cddf2b39`（全量 `dev_check` 运行时点：commit `7e96c14`、dirty=true，其后仅版本/文档定稿） |
| 配置指纹 | `pyproject.toml` `4b786c97…`、`.clang-format` `b084ba4a…`、`requirements-dev.txt` `f325c41a…` |

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-049` | `success=true`、`unit_tests=passed`：`Ran 1128 tests in 246.699s`，`OK`，无 `timed_out`（`unit_test_timeout_seconds=900`）；`lint_findings=30`、`unformatted_files=16`（均为既有基线），python 221 / cpp 33；报告 `build/development_check.json` 已被本次覆盖（`work_item=DEV-049`） |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_setup_native_stderr tests.unit.test_install_config tests.test_installation_validation -v` | `Ran 28 tests … OK`（BUG-086 批内补充修复后扩展回归：Python 探测/venv 阶段 stderr notice 与非零退出 × 三种调用形式，及 8 处调用点统一封装断言） |
| `.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item BUG-086` | `success=true`（lint 30 / 未格式化 16 基线，无新增回归） |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，输出 `build\creo_worker.exe`（原生执行器可复用） |
| `.\.venv\Scripts\python.exe tools\package_seeds.py --output …` | 24 文件 / 9 种子；两次构建 SHA256 一致（确定性） |
| `setup.ps1`（新目录安装验证） | exit 0，见「安装验证」 |

## T04/T06 实机摘要（Creo 12.4.0.0，2026-10-28）

- **T04 原斜槽六例 6/6**（BUG-087 修复后）：R20、z∈[0,5] 圆柱、54° 面、u∈[-4,0]、v∈[-3,3]，autodim×3（run `20261028T102858_b2d5e5c9`）与 coordinates×3（run `20261028T104324_57f20a2d`）全部通过：去料体积对单向 238.390260127791 / 双向 476.780520255582 mm³ 基准（≤0.01 mm³）、实际帧 v=n×u、参考线 2 条、`revision=3`、保存重载 true；Right 面 ±Z 回归无退化（[T04 记录第十节](../development/DEV049-T04-ACCEPTANCE.md)）。
- **T06 种子 15+2 全部通过**：FEAT-030 九种子矩阵 15 正例 + 2 负例实机通过（单一受测源码、逐阶段持久化、跨指纹不合并），九种子 SHA256 与 `docs/seed_manifest.json` 一致（[T06 记录](../development/DEV049-T06-ACCEPTANCE.md)）。
- 实机驱动均为 `--live --confirm-session-usable` 双门槛并记录本次人工会话核对；未启动/结束 Creo、未清 unknown 保护、未注册第二套客户端。

## BUG-086 批内补充修复与安装验证

- **修复**：T03 只封装了两个 pip 步骤；T08 新目录安装验证发现非 pip 外部调用（vswhere 工具链探测、Python 版本探测、`python -m venv`、editable 导入检查、`seeds.py --install`、`bridge.py build`）在调用方 stderr 重定向下同样误报 `INSTALL_INCOMPLETE`。经用户批准按 T03 同模式最小修复：`setup.ps1` 的全部 8 处外部调用统一经 `Invoke-ExternalStep`（原 `Invoke-PipStep` 泛化）按真实退出码判定——局部容错 stderr ErrorRecord、调用前清 `$global:LASTEXITCODE`、启动失败/无退出码/非零一律失败、finally 恢复错误偏好；不吞 stderr、不匹配特定文本。语义差异一处：vswhere 非零不再静默回退，而是按同一 MSVC 缺失文案失败并附真实退出码。
- **安装验证（修复后）**：`git archive` 导出集成分支源码到全新目录 `E:\Projects\MCP_CREO_MechDog_T08_install_dev049t08`（保留为证据，不在仓库内），Windows PowerShell 5.1 运行 `setup.ps1 -CreoRoot "C:\Program Files\PTC\Creo 12.4.0.0"`，调用方以 `1> setup_out.log 2> setup_err.log` 重定向：**exit 0**，pip 与非 pip 阶段均无误报，`INSTALL_INCOMPLETE` 未出现，`Ready.` 收尾；`setup_err.log` 仅含 pip `[notice]` 等通知文本且保留可见。可编辑包指向导出源码（`source\src\creo_mechdog`，`MCP_CREO_MechDog 0.7.1` 与导出源码 `version.py` 一致，随本版定稿升 0.7.2）；九种子 SHA256 与 manifest 逐项一致（9/9）；原生执行器由导出目录 SDK 重新编译成功（`build/creo_worker.exe` 12 814 848 字节）。未复制主仓 config/常量/二进制，未连接 Toolkit/Creo，未注册第二套客户端。
- **对照（修复前）**：同一 `2> err.log` 重定向形式下，非 pip 阶段外部调用被 Stop/重定向误判而假报 `INSTALL_INCOMPLETE`（T08 安装验证实测、用户批准本批内补充修复的动因）；修复后同形式全阶段通过。

## 种子与打包

- 两份种子清单（`seed_library/seed_manifest.json`、`docs/seed_manifest.json`）`compatible_server_version` 同步 0.7.2、字节级一致、均 9 条目；9 个种子 PRT **原字节不变**。
- 种子包按 0.7.2 确定性重建（两次构建 SHA256 一致）；`seeds.py` 的 `expected_digest` 已更新为该包 SHA256（算法与校验逻辑不变）。

## 附件

| 附件 | 大小/内容 | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.7.2-seed-library.zip` | 24 文件 / 9 种子（确定性，两次构建一致） | `0ab4918b836d8d7edc384581cdffd346b0bfdd379e8fbb39947f8a739be86554` |
| `MCP_CREO_MechDog-0.7.2-seed-library.zip.sha256` | 记载上行哈希 | `94debebb245f9c127670613033e2d56ceea08512608b1018e3e9bf4c4605514c` |
| `MCP_CREO_MechDog-0.7.2-source.zip` | 由 `v0.7.2` 标签提交源码生成（`tools/package.py` 允许清单） | 见 GitHub Release body（附件生成于记录提交之后，无法在本文件内自指，同 0.7.1 先例） |
| `MCP_CREO_MechDog-0.7.2-source.zip.sha256` | 记载上行哈希 | 见 GitHub Release body（同上） |

逐件下载核对结果回填于 GitHub Release 正文；按用户 2026-10-28 要求，发布后不再产生新的 main 提交。

## 相对上一正式包（0.7.1）的身份核对

| 项目 | 0.7.1 | 0.7.2 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节 | — | `git diff v0.7.1..HEAD -- native/third_party` 为空 | 字节未变，第三方许可与 `json.hpp` 无需处理 |
| 回调指纹算法 | `sha256-repo-lf-v1` | 同 | 算法未改 |
| 原生源码 | — | 仅 `native/generic.cpp` +26/−14（草图第二参照选择，BUG-087） | 建模行为修复，其余原生文件未动 |
| worker | `bc36eff83ce6…` | `creo_worker.exe` SHA256 `93f808b34c987423e62065a03511b1a3c7c61a1971fb2fc21a5195424ec9776b` | 二进制已变，需替换并重启 MCP 服务 |
| loader DLL | `eea159f9b8fd…` | `creo_blend_loader.dll` `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9` | 随批重建 |
| callback DLL | `acdda5623b85…` | `creo_blend_sync.dll` `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662` | 随批重建 |
| `protk.dat` / 注册表 / 安装路径 | 未变更 | 未变更 | 无需重新注册 Toolkit 应用；升级后重编（`bridge.py build`）并重启 MCP 服务即可 |

## 逐 ID 状态核对

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 |
| --- | --- | --- | --- | --- |
| DEV-049 | 已完成（T00—T08，随本版交付并移入完成档案） | 0.7.2 | WorkBuddy、外部 Creo 9/10 未做；T05 差项实机未跑 | [DEV-049](../work-items/DEV-049.md) |
| BUG-086 | 已修复（含 T08 批内补充；新目录安装验证通过） | 0.7.2 | `pwsh` 7 / PowerShell 5.0 未测 | [BUG-086](../work-items/BUG-086.md) |
| BUG-087 | 已修复（六例 6/6 + Right 面回归） | 0.7.2 | 外部环境未复测；BUG-064/084 原构型范围保留 | [BUG-087](../work-items/BUG-087.md) |
| DEV-050 | 已完成（`--unit-timeout-seconds` 默认 900 秒，全量 1128 项通过） | 0.7.2 | 无 | [DEV-050](../work-items/DEV-050.md) |
| FEAT-030 | 已验收（未收口；15+2 实机全过） | 0.7.2 | 生产版本可追溯记录、其他环境加载证据 | [FEAT-030](../work-items/FEAT-030.md) |
| BUG-085 | 待复现（根因未定） | 未排期 | 13 正例 + 2 负例编辑闭环缺口、关键证据缺失 | [BUG-085](../work-items/BUG-085.md) |

## 未测与限制

- WorkBuddy 黑盒按用户 2026-10-26 决定取消，本版未执行。
- 外部 Creo 9（本机无 SDK）与 Creo 10 未复测；Creo 9 仅保留支持声明，实机编译与建模运行时未验收。
- BUG-085 断连事故根因未定（T01 结论：证据不足）；未做新的 Toolkit 连接或故障注入，BUG-001 恢复条件与 unknown 保护保持。
- BUG-066 预览失真待复现（无原模型/原始图像）；T05 多环/预览差项实机未执行（原输入缺失）。
- 安装验证未连接 Toolkit/Creo、未启动 Creo、未注册第二套客户端；`pwsh` 7 与 PowerShell 5.0 下的 setup 未测。
- 未重跑 DEV-047 完整历史矩阵；`d2e37b0` 主干回填不属于 0.7.1 附件（GAP-1/GAP-2 由本版覆盖）。
