# Release 0.7.1 发布验收记录

版本与条目：`0.7.1`（PATCH），DEV-048 反馈修复批次（T00 文档基线、T01 收养侧车完整性与回退、T02 拒绝后引用生命周期、T03 工作卡与发布检查回填、T04 Right 面 ±Z 定向证据、T05 集成与交付）。公开工具数 94，与 0.7.0 相同，不新增工具。

日期与环境：2026-10-27（Asia/Shanghai）；Windows 11 Enterprise x64、Python 3.12.14、Creo Parametric 12.4.0.0（`release_numeric=44`）、匹配 Toolkit SDK、MSVC x64、ruff 0.17.0、clang-format 23.1.3。

## 受测源码

| 项目 | 值 |
| --- | --- |
| 版本定稿提交 | `7e5b7d135df15cc2c4b93a4c83128962b9fc15c9`（`DEV-048 T05: set version 0.7.1 and release metadata`） |
| 记录时工作区 | dirty=true（本记录尚未提交；其余为 `.gitignore` 内的本机运行数据 `session_activity.json`、`session_erase/`、`.codebuddy/`、`.workbuddy/`、`.zcode/`） |
| `checked_source_sha256` | `8e5b2e978cc8f18dab026ff53d345a385d5cf3701e804751c4a8dd30213bac8e` |
| 配置指纹 | `pyproject.toml` `4b786c97…`、`.clang-format` `b084ba4a…`、`requirements-dev.txt` `f325c41a…` |

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe tools\test_unit.py` | `Ran 1017 tests in 347.181s`，`OK`（exit 0；日志 `build/unit_full.log`） |
| `.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-048` | `success=true`；`lint_findings=30`、`unformatted_files=16`、`cpp=33`、`py=215`（均为既有基线，无新增回归） |
| `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-048` | **超时未完成**：`tools/dev_check.py:233` 写死 `timeout=300`，全量套件实测 347 秒，被判 `unit_tests=timed_out`。这是工具定时器不足，不是测试失败；全量结果以直接运行 `tools/test_unit.py` 的上述记录为准，未修改该工具 |
| `.\.venv\Scripts\python.exe tools\test_dev048_plane_frame.py --live --confirm-session-usable` | `plane_frame_matrix=passed`、`native_acceptance=partial`，三例见下 |
| `setup.ps1`（解包候选目录） | exit 0，见"解包安装" |
| `tools\package.py` / `tools\package_seeds.py` | 见"附件" |

## T04 实机（Creo 12.4.0.0）

| 用例 | 实际帧 | 体积 mm³ | AABB | 重心 | 保存重载 | revision |
| --- | --- | --- | --- | --- | --- | --- |
| `u_axis=[0,0,1]` | `u=[0,0,1]`、`v=[0,-1,0]`、`n=[1,0,0]` | 799.9999999999998 | `[[0,-20,0],[4,0,10]]` | `[2,-10,5]` | true | 2 |
| `u_axis=[0,0,-1]` | `u=[0,0,-1]`、`v=[0,1,0]`、`n=[1,0,0]` | 799.9999999999998 | `[[0,0,-10],[4,20,0]]` | `[2,10,-5]` | true | 2 |
| `u_axis=[1,0,0]`（平行法向） | 空零件无几何 | null | — | — | — | 1 → 1 |

Right 面几何 ID 由巡检选出（过原点且法向平行 X 的唯一平面），本次会话实际为 `id=2`。平行法向一例入口未拒绝、由原生边界拒绝且 `rollback_succeeded=true`、别名不变。`native_acceptance=partial` 表示只做 Right 面定向补证，未重跑 DEV-047 完整历史矩阵。

## 解包安装

从候选公开源码包（940 文件）解压到 `E:/Projects/md071-install-20261027/MCP_CREO_MechDog`，运行 `setup.ps1 -Python <主仓 .venv> -CreoRoot "C:\Program Files\PTC\Creo 12.4.0.0" -VcVars64 <本机脚本>`，**exit 0**，末行为 `Ready.`。解包目录自有 `.venv` 验证：`version.VERSION=0.7.1`，`creo_mechdog.__file__` 位于解包目录；原生侧 `build/creo_worker.exe`（12,814,336 字节）由该目录 SDK 重新编译成功。未复制主仓常量或二进制，未注册第二个 MCP 客户端，未执行 Toolkit 探活或建模。

安装期发现一处工具缺陷（不影响本版产物）：`setup.ps1:8` 设 `$ErrorActionPreference='Stop'`，而 PowerShell 5.1 在重定向 stderr 时会把 pip 的 `[notice]` 输出转成终止错误，导致"依赖已装好但脚本报 `INSTALL_INCOMPLETE: failed at Python dependencies`"。pip 实际 exit 0；仅重定向 stdout 后同一命令 exit 0。后续版本宜让依赖步骤不因 stderr 通知而中断。

## 附件

| 附件 | 大小/内容 | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.7.1-seed-library.zip` | 24 文件 / 9 种子（确定性，两次构建一致） | `53b3d39176a1107d6a5da57257a9566500a084b7a5a3cf415fec75f657e46994` |
| `MCP_CREO_MechDog-0.7.1-source.zip` | 940 文件，由本版标签提交源码生成 | 见 GitHub Release body（该附件生成于记录提交之后，无法在本文件内自指） |

`seeds.py` 的 `expected_digest` 已更新为上述种子包 SHA256；两份种子清单（`seed_library/seed_manifest.json`、`docs/seed_manifest.json`）版本同为 0.7.1、均 9 条目。

## 相对上一正式包（0.7.0）的身份核对

| 项目 | 0.7.0 | 0.7.1 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节 | — | `git diff v0.7.0..HEAD -- native/third_party` 为空 | 字节未变，第三方许可与 `json.hpp` 无需处理 |
| 回调指纹算法 | `sha256-repo-lf-v1` | 同 | 算法未改，仅比较；未为比较调整归一化 |
| 原生源码 | — | `native/generic.cpp` 缩减 55 行、新增 `native/inspection_sidecar.h` 235 行 | 侧车 helper 提取与 `MoveFileExW` 发布语义 |
| worker | 见 [0.7.0 记录](RELEASE-0.7.0.md) | `creo_worker.exe` SHA256 `bc36eff83ce61d371e0aee1c1372053e867d2515754a5dd51fc71e303aac06e9` | 二进制已变，需替换并重启 MCP 服务 |
| loader DLL | 见 0.7.0 记录 | `creo_blend_loader.dll` `eea159f9b8fd8bd7c65946d4d4817d721fda6ea641eaf8c98262daf5f72ff637` | 安装时因归一化指纹变化自动重编 |
| callback DLL | 见 0.7.0 记录 | `creo_blend_sync.dll` `acdda5623b8549fc74a7dbb8f7f33f8cc63c856d244e05f7a1b188cb8502be93` | 同上 |
| `protk.dat` / 注册表 / 安装路径 | 未变更 | 未变更 | 无需重新注册 Toolkit 应用；升级后重启 MCP 服务即可 |

本机未保留 0.7.0 的构建产物，上一版 DLL 身份以 0.7.0 发布记录为准，不以本次重建值冒充旧值。

## 逐 ID 状态核对（候选态）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-048 | 本批代码与实机证据完成 | 0.7.1 | T05 交付本身；外部 Creo 9/10、WorkBuddy、完整历史矩阵未做 | [DEV-048](../work-items/DEV-048.md) | [BACKLOG](../BACKLOG.md) | [0.7.1 说明](../RELEASE_NOTES_0.7.1.md) | [DEVELOPMENT](../DEVELOPMENT.md) | 待发布（本节为候选态核对） |

## 未测与限制

- WorkBuddy 黑盒按用户 2026-10-26 决定取消，本版未执行。
- 外部 Creo 9（本机无 SDK）与 Creo 10 未复测；CREO 9 仅保留支持声明。
- T04 只覆盖 Right 面 ±Z，未重跑 DEV-047 完整历史矩阵。
- 未做真实 worker 超时/断连注入、真实文件锁下的清理失败注入、未知单位实机诱导。
- `dev_check` 全量模式因 300 秒上限未跑通，已改用等价的全量命令并如实记录。