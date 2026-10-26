# FEAT-012 实机驱动 CLI 直接入口修复（2026-10-25）

范围：仅修复三个开发者 CLI 实机驱动的文档化直接调用入口（从仓库根
`python tools/<driver>.py`），不触碰功能逻辑。不连接 Toolkit、不启动
Creo/worker、不故障注入、不改客户端配置、不清 unknown 保护、不合并不
推送、不改版本、不发布。主代理在 canonical `E:\Projects\MCP_CREO_MechDog`
的实机运行不受影响；本文件为独立新证据，不改写任何历史报告。

环境：Windows 11 x64 / Python 3.12.14 / 正常 editable 安装（无
PYTHONPATH）。工作树：`E:/Projects/md050`，分支
`codex/feat012-matrix-pipeline`，基准 HEAD `4161ffd`。

## 1. 缺陷与复现

文档登记的调用方式（`docs/ASSEMBLY_REBUILD.md`、`docs/FILE_ADOPTION.md`）
是从仓库根直接运行脚本，例如
`.venv\Scripts\python.exe tools\test_assembly_matrix.py --session-health-verified`。
canonical 实机守卫运行
`build\guarded_live_20261025T144852021328\report.json` / `child_0.log` 记录
了真实失败（任何 native 作业之前、新作业为 0）：

```
ModuleNotFoundError: No module named 'tools'
  File "...tools\test_assembly_matrix.py", line 21, in <module>
    from tools.dev_check import git_state, source_hash
```

按脚本路径执行时 `sys.path[0]` 是 `tools/` 而非仓库根，仓库根模块
（`tools` 包、`bridge`）不可导入。md050 本地在无 PYTHONPATH 下复现：

- `tools\test_assembly_matrix.py --help` → `ModuleNotFoundError: No module named 'tools'`（line 21）
- `tools\test_assembly_pipeline.py --help` → `ModuleNotFoundError: No module named 'bridge'`（line 55）
- `tools\test_file_adoption.py --help` → `ModuleNotFoundError: No module named 'bridge'`
  （经由已安装包 `creo_mechdog.file_adoption` 间接 import 根模块 `bridge`）

`-m tools.<driver>` 入口因 `sys.path[0]` 为仓库根本来可用，故此前未被
发现。

## 2. 修复

`tools/test_assembly_matrix.py`、`tools/test_assembly_pipeline.py`、
`tools/test_file_adoption.py` 三处均在第三方导入之后、仓库模块导入之前
加入既有仓库惯例（同 `tools/test_general.py` 等 20 余个驱动）：

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

不改任何业务逻辑、报告目录、请求构建或 MCP 调用序列。`tools/*.py` 已
在 `pyproject.toml` 对 E402 豁免，直接入口与 `-m` 入口共用同一代码。

## 3. 验证（无 Creo，仅 --help 与离线检查）

| 命令 | 结果 |
| --- | --- |
| `python tools\test_assembly_matrix.py --help`（PYTHONPATH 已清除） | 退出 0，usage 正常 |
| `python tools\test_assembly_pipeline.py --help`（同上） | 退出 0，usage 正常 |
| `python tools\test_file_adoption.py --help`（同上） | 退出 0，usage 正常 |
| `python -m tools.test_assembly_matrix --help` | 退出 0，usage 正常 |
| `python -m tools.test_assembly_pipeline --help` | 退出 0，usage 正常 |
| `python -m tools.test_file_adoption --help` | 退出 0，usage 正常 |
| `python -m unittest tests.unit.test_tool_driver_entries -v` | 2 项通过（每驱动直接入口与 `-m` 入口各一，子进程清 PYTHONPATH、限 60s） |
| `python tools\dev_check.py` | 退出 0，语言检查无新增诊断、全部 Windows 单测通过（`build/development_check.json` `success: true`，708+2 项） |

新增回归 `tests/unit/test_tool_driver_entries.py`：以子进程在仓库根、
清除 PYTHONPATH 的环境分别跑通三个驱动的 `python tools/<driver>.py
--help` 与 `python -m tools.<driver> --help`，断言退出 0 且输出
usage；只触碰 `--help`，不需要 Creo。

## 4. 源码身份

| 文件 | SHA256 |
| --- | --- |
| tools/test_assembly_matrix.py | 7028c52385f7f7b57c6c1cc6d242cbfe65794aef1938f778e3c239fdd4b92a2a |
| tools/test_assembly_pipeline.py | 57d97268fb288b8757d1afb9f47fec97735bb45c820a3bff77dab348287b1310 |
| tools/test_file_adoption.py | dd740faedde57bc05acfc08127e7338a1bc93511b9fd0ae3400e5a95948655b0 |
| tests/unit/test_tool_driver_entries.py | 74397bc23dfd6fb0403d06f22023add12c64d4846641a681d63b9c5e5929569a |

## 5. 未测范围

- 未连接 Creo、未运行任何 native 作业；三个驱动的实机建模行为本次未
  复测（由主代理按守卫流程负责）。
- 未测其他 Python 版本/其他机器；直接入口修复依赖仓库相对布局
  （`Path(__file__).resolve().parents[1]`），从仓库外路径调用脚本不在
  文档登记方式内。
- 守卫 `tools/guarded_live_run.py` 行为未改，未复测。
