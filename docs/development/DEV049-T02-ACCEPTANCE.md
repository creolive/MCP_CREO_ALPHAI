# DEV-049 / T02 dev_check 单元阶段超时预算验收（DEV-050）

日期：2026-10-27（Asia/Shanghai）。范围：给 `tools/dev_check.py` 的单元阶段增加可配置超时预算（`--unit-timeout-seconds`，默认 900 秒）及离线回归，并如实报告真实结果。不含风格工具预算、style-baseline 重建、Windows 检查绕过、其他阶段逻辑改动；完整单元套件与统一入口全量运行按派发表留给 T08。

## 交付与来源身份

- 依赖基准：`4afd19d`（集成分支 `codex/dev049-feedback061` 顶端，T00/T01 已并入）。
- 本任务分支：`codex/dev049-t02-check-timeout`，从 `4afd19d` 建立。
- 实现提交：`2848d59`（`tools/dev_check.py` + `tests/unit/test_dev_check_timeout.py`）；卡与本验收记录为随后的文档提交。
- dirty 状态：验证时 `git status` dirty=true，脏项为 `session_activity.json` 的既有运行数据修改，以及未跟踪的 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/`。运行数据全部保留，未提交、未 stash、未 checkout。
- 受测源码指纹：`checked_source_sha256=edcda2a338e7a7662736b28fd8b8a0ec4164ff33ce46605372d3d8a128edae19`（`build/development_check.json`，覆盖 216 个 Python 与 33 个 C/C++ 源文件；脏运行数据不计入）。
- 环境：Windows 11 x64、Python 3.12.14、ruff 0.17.0、clang-format 23.1.3，工作区 `E:ProjectsMCP_CREO_MechDog`。
- 未连接 Creo/Toolkit/SDK；未改 `version.py`（0.7.1）；未合入 main、未推标签、未发布；未动 `session_*` 运行数据。

## 新增 CLI 用法

- `--unit-timeout-seconds N`：单元阶段子进程预算，正整数秒，默认 900。
- 0、负数、非整数在参数解析阶段拒绝：非零退出码 2，报错 `error: argument --unit-timeout-seconds: ...`。
- `--skip-unit` 仍不运行单元测试（报告 `unit_tests=not_run`），且不移除预算校验：与 `--skip-unit` 同用非法预算同样在参数阶段被拒。
- development_check 报告新增 `unit_test_timeout_seconds`；`passed`/`failed`/`timed_out` 三态区分、`timed_out` 永不被报告为 success、非零退出码语义均保持。

## 矛盾复现（替身，不真等 347 秒）

`tests/unit/test_dev_check_timeout.py` 的替身套件把单元阶段模拟为耗时 347 秒（预算低于 347 即抛 `subprocess.TimeoutExpired`），复现 0.7.1 实录矛盾（`docs/validation/RELEASE-0.7.1.md`）：

| 预算 | 结果 |
| --- | --- |
| `--unit-timeout-seconds 300`（修复前硬编码） | `unit_tests=timed_out`、`success=false`、exit 1 |
| 默认 900 | `unit_tests=passed`、`success=true`、exit 0 |

## 命令与结果（2026-10-27，Windows / Python 3.12.14，HEAD `2848d59`）

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_dev_check_timeout -v` | exit 0，`Ran 8 tests in 0.196s`、`OK`。8 项覆盖：默认预算 900、显式预算 1200/600/45、非法参数（0、-3、abc、12.5、空串）、`--skip-unit`（不跑测试且非法预算仍被拒）、子进程非零退出（failed）、`TimeoutExpired`（timed_out）、正常完成（passed）、300/347 矛盾复现；断言 `timed_out` 永远不会被报告为 success |
| `.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-050` | exit 0，`success=true`、`unit_tests=not_run`、`unit_test_timeout_seconds=900`、`native_validation=not_run`；`style_summary` lint 30 / 未格式化 16 均为既有基线，无新增语言问题，未重建基线；报告 `build/development_check.json`（本机生成物，不入库） |
| `.venv\Scripts\python.exe tools\dev_check.py --unit-timeout-seconds 0` | exit 2，`error: argument --unit-timeout-seconds: must be a positive number of seconds: 0` |
| `.venv\Scripts\python.exe tools\dev_check.py --unit-timeout-seconds -5` | exit 2，`error: argument --unit-timeout-seconds: must be a positive number of seconds: -5` |
| `.venv\Scripts\python.exe tools\dev_check.py --unit-timeout-seconds abc` | exit 2，`error: argument --unit-timeout-seconds: must be a positive integer number of seconds: 'abc'` |
| `.venv\Scripts\python.exe tools\dev_check.py --unit-timeout-seconds 1.5` | exit 2，`error: argument --unit-timeout-seconds: must be a positive integer number of seconds: '1.5'` |

CLI 参数行为小结：默认 900 秒，可被显式正整数覆盖（1200 用例断言子进程收到 `timeout=1200` 并写入报告）；0/负数报“必须是正数秒”，非整数报“必须是正整数秒”；非法值在参数解析阶段即拒绝，未进入任何检查阶段。

## 未测项

- 完整单元套件（约 1017 项 / 347 秒）与统一入口全量运行 `toolsdev_check.py --work-item DEV-049`（默认 900 秒）按派发表留给 T08；本任务按要求未运行完整套件。
- 未做实机/Toolkit/Creo 范围验证（纯 Python 工程改动，不适用）；按 2026-10-15 用户决定不要求 Creo 9/10 独立复测。
- `--write-baseline` 与 `--strict` 路径仅保持既有行为，未新增验证；单元阶段的非 Windows 平台行为未验证（该阶段本身要求 Windows）。
