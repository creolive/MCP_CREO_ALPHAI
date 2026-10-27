# DEV-049 / T03 PowerShell 5.1 pip stderr 误报验收（BUG-086）

日期：2026-10-27（Asia/Shanghai）。范围：在 Windows PowerShell 5.1 隔离夹具中复现「pip 退出码 0、stderr 输出 `[notice]`，却被 Stop 偏好与 stderr 重定向当作失败」，在 `setup.ps1` 内集中封装两个 pip 步骤的外部 Python 调用，并补齐离线回归。不含真实新目录 setup 安装（T08）、不改服务注册标识、不改 `version.py`、不连接 Creo/Toolkit、不联网安装。

## 交付与来源身份

- 依赖基准：`bc39c95`（集成分支 `codex/dev049-feedback061` 顶端，T00/T01/T02 已并入）。
- 本任务分支：`codex/dev049-t03-installer`，从 `bc39c95` 建立。
- 变更文件：`setup.ps1`；新增 `tests/unit/test_setup_native_stderr.py`；扩展 `tests/unit/test_install_config.py`、`tests/test_installation_validation.py`；本记录与 [BUG-086](../work-items/BUG-086.md) 卡。
- dirty 状态：验证时 `git status` dirty=true；脏项为本任务尚未提交的上述代码/文档，以及既有运行数据 `session_activity.json` 的修改与未跟踪的 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/`。运行数据全部保留，未提交、未 stash、未 checkout。
- 受测源码指纹：`checked_source_sha256=d1334f3572a92b877e56ab3f866873ede0b8566b490ebbd23bde8794891039ea`（`build/development_check.json`，217 个 Python 与 33 个 C/C++ 源文件；脏运行数据不计入）。
- 变更文件 SHA256（验证时）：`setup.ps1` `24aff3ad521ba49789aae0016f4bb65a108c28a45b7553b8d0ea6f601bd67793`；`tests/unit/test_setup_native_stderr.py` `1c5cf7c49790c78737e34909b3e1fa4f8050cec53fd0401fdf5f8baca8902585`。
- 环境：Windows 11 Enterprise x64、**Windows PowerShell 5.1.26100.9711**（`$PSVersionTable.PSVersion`，`powershell.exe` 10.0.26100.9549）、Python 3.12.14、ruff 0.17.0、clang-format 23.1.3，工作区 `E:\Projects\MCP_CREO_MechDog`。

## 复现（隔离夹具，不访问 PyPI、不连 Creo）

触发条件经实测确认：**脚本内 `$ErrorActionPreference='Stop'` + 原生命令的 stderr 被重定向**（`2> file`，即 0.7.1 安装实录的写法）。此时 PowerShell 5.1 把 pip 的 stderr 行转成 `ErrorRecord`（`RemoteException`/`NativeCommandError`），`Stop` 偏好使其成为终止错误；pip 本身 **exit 0**。直接执行与调用方 `2>&1`（错误流并入输出流）不会触发同一条终止路径。

### 最小夹具（`%TEMP%` 下临时脚本，非仓库文件）

`fake-pip.cmd` 向 stderr 打印 `[notice] A new release of pip is available: 24.0 -> 25.2` 与 `Successfully installed ...`，然后 `exit /b 0`；`repro.ps1` 设 `$ErrorActionPreference='Stop'` 后执行 `& fake-pip.cmd -m pip install -r requirements.txt`。

| 调用方式（修复前） | 实际输出 | 结论 |
| --- | --- | --- |
| 直接执行 `powershell -File repro.ps1` | `[notice] ...` 后 `RESULT stage-completed exit=0` | 正常 |
| 调用方 `& 'repro.ps1' 2> err.txt` | `CAUGHT type=RemoteException`、`CAUGHT message=Successfully installed fixture-package-1.0`、`INSTALL_INCOMPLETE: failed at Python dependencies` | **误报复现**（pip exit 0 被判失败） |
| 调用方 `2>&1` | 记录并入输出流，`RESULT stage-completed exit=0` | 正常 |

### 真实 `setup.ps1` + 完整安装夹具（修复前 / 修复后对照）

夹具为 `tests/unit/test_setup_native_stderr.py` 的临时安装树：假 SDK 文件、空 `requirements.lock.txt`、`python.cmd` 桩（应答 `-c` 版本探测、venv 步骤空转）、`fake_site/pip/__main__.py` 假 pip（经 `PYTHONPATH` 命中，`--editable` 判定步骤）。两列都止于 `SDK constants and native worker`，因为夹具没有 MSVC，属预期终态。

| 调用方式 | 修复前（`bc39c95:setup.ps1`） | 修复后 |
| --- | --- | --- |
| 直接执行 `-File` | 停在 `SDK constants and native worker`，两个 pip 阶段完成 | 同左 |
| 调用方 `2> native-stderr.txt` | 停在 **`Python dependencies`**，`Completed: local configuration, Python virtual environment, client configuration` | 停在 `SDK constants and native worker`，两个 pip 阶段完成 |
| 调用方 `2>&1` | 停在 `SDK constants and native worker`，两个 pip 阶段完成 | 同左 |

修复前同一夹具的失败断言原文（`test_notice_on_stderr_keeps_both_pip_stages`，form=`stderr_redirect`）：

```
AssertionError: 'Python dependencies' not found in 'local configuration, Python virtual environment, client configuration'
  : Prerequisites found: Python 3.12.0, Creo SDK and MSVC x64.
INSTALL_INCOMPLETE: failed at Python dependencies. ...
```

## 修复方式（`setup.ps1`）

新增单点封装 `Invoke-PipStep`（`setup.ps1:12-50`），两个 pip 步骤改为调用它，其余阶段逻辑与顺序未动：

- 局部容忍：函数内保存 `$previousPreference = $ErrorActionPreference`，`try` 内设 `Continue`，`finally` 恢复；脚本顶层仍只有一处 `$ErrorActionPreference = 'Stop'`，**未全局降低偏好**。
- 立即取真值：调用前 `$global:LASTEXITCODE = $null` 清除旧值，`& $Executable @Arguments` 之后第一条语句即 `$exitCode = $global:LASTEXITCODE`（实测函数内直接赋值 `$LASTEXITCODE` 会遮蔽，读不到真实码，故用 `global:`）。
- 三种失败语义：捕获到启动异常 → `<原失败消息> Could not start <exe>: <原始错误>`；无退出码 → `reported no exit code`；退出码非零 → `<原失败消息> <exe> exited with code N`，保留 pip 的真实码。
- 不吞 stderr：函数不做任何重定向、不匹配 `[notice]`、不关闭 pip 版本提示；stderr 文本在三种调用下仍可见或可取证。
- 判定只用退出码：`exit 0` 一律继续，失败消息仍为原有 `Dependency installation failed. ...` / `Source package installation failed. ...` 语义。

## 回归矩阵（3 种调用 × 4 种退出情形）

`tests/unit/test_setup_native_stderr.py`，5 个测试方法，逐调用方式 `subTest` 展开：

| 用例 | direct | stderr_redirect | merge | 断言要点 |
| --- | --- | --- | --- | --- |
| exit 0 + stderr notice | 通过 | 通过 | 通过 | `Completed:` 含 `Python dependencies`、`Python source package`；`[notice]` 仍可见 |
| requirements 阶段非零 | 通过 | 通过 | 通过 | 停在 `Python dependencies`；`exited with code 3`；原始 `ERROR: Could not find ...` 保留 |
| editable 阶段非零 | 通过 | 通过 | 通过 | 停在 `Python source package`；`Python dependencies` 已完成；`exited with code 3`；原始错误保留 |
| 可执行文件启动失败 | 通过 | 通过 | 通过 | 停在 `Python dependencies`；`Could not start`；不得出现 `exited with code`（无码不冒充失败码） |
| 静态约束 | 通过 | — | — | 顶层 `'Stop'` 唯一、`'Continue'` 唯一且在 helper 内、恢复语句在 helper 内、位于首个安装阶段之前 |

既有回归的扩展：`tests/unit/test_install_config.py` 的 `-CheckOnly` 用例新增断言（不生成 `client-config.json`、不生成 `.venv`，即不产生安装写入）；`tests/test_installation_validation.py` 的原生失败用例新增断言（真实 pip 路径下 `Python dependencies, Python source package, native Blend seed library` 全部完成，证明修复未破坏正常路径）。

## 命令与结果（2026-10-27，Windows 11 / PowerShell 5.1.26100.9711 / Python 3.12.14）

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_setup_native_stderr tests.unit.test_install_config tests.test_installation_validation -v` | exit 0，`Ran 24 tests in 37.487s`、`OK`（5 新增 + 8 安装配置 + 11 安装校验） |
| `.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item BUG-086` | exit 0，`success=true`、`unit_tests=not_run`、`native_validation=not_run`；`style_summary` lint 30 / 未格式化 16 / cpp 33 / py 217，均为既有基线，无新增语言问题，未重建基线；报告 `build/development_check.json`（本机生成物，不入库） |
| `.venv\Scripts\python.exe -m ruff format tests/test_installation_validation.py tests/unit/test_setup_native_stderr.py` | `2 files reformatted`（首个 `dev_check` 曾报 2 处 `must pass its formatter`；格式化后复跑为 `success=true`） |

## 未测项

- 真实新目录解包执行 `setup.ps1`（含真实 `.venv` 创建、真实 pip 走网络、可编辑包导入、九种子与原生构建）归 T08，本任务未执行。
- 夹具用 `python.cmd` 桩与 `PYTHONPATH` 假 `pip`，只验证判定语义；**不证明真实 pip 的 stderr 行为、安装结果或网络/许可状况**。
- Windows PowerShell 7（`pwsh`）与 PowerShell 5.0 未测；其他系统区域设置下的 PS 本地化错误消息未断言（夹具只匹配自带 ASCII 标记 `Could not start` / `exited with code`）。
- `setup.ps1` 其余外部调用（`-c` 版本探测、`-m venv`、`seeds.py`、`bridge.py build`）按派发表未纳入封装，保持原语义，未新增针对它们 stderr 的回归。
- 未连接 Creo/Toolkit/SDK 实机；按 2026-10-15 决定不要求 Creo 9/10 独立复测。

