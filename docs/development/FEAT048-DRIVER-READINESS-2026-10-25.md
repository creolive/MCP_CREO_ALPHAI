# FEAT-048 实机收养驱动补 readiness 前置（2026-10-25）

范围：仅修复 `tools/test_file_adoption.py` 实机驱动缺少公开启动状态观测的
问题，复用既有 `tools/mcp_readiness.py:wait_for_startup`，并新增离线回归
`tests/unit/test_file_adoption_driver.py` 与本证据文件。不触碰生产逻辑
（`server.py`/`bridge.py`/包内实现/native 均未改）、不改 canonical、不改配
置、不连接 Toolkit/MCP/Creo、不启动真实 server、不故障注入、不合并不推
送、不改版本、不发布。主代理在 canonical `E:\Projects\MCP_CREO_MechDog`
的实机运行不受影响；报告路径改为每次独立目录，不覆盖旧报告。

环境：Windows 11 x64 / Python 3.12.14。工作树：`E:/Projects/md050`，分支
`codex/feat012-matrix-pipeline`，基准 HEAD `78c4bfe`。

## 1. 缺陷与复现

`tools/test_assembly_matrix.py`（line 178）与
`tools/test_assembly_pipeline.py` 在任何 inventory/adoption 之前调用
`wait_for_startup`，而 `tools/test_file_adoption.py` 的 `scenario()` 在
stdio `Client` 建立后立即 `creo_list_session_models`（旧 line 69
`before = await current()`）。`server.py` lifespan 只后台异步
`startup.start()` 构建/连接执行器，首次 session inventory 与
`startup_build` 竞争通道：Toolkit 忙碌时按约定返回
`status="busy"`（`isError=true`），驱动的 `call()` 将其升为
RuntimeError 立即停止，脚本在从未观测公开启动状态的情况下失败。

离线复现（假 stdio 客户端，第一个 `creo_list_session_models` 返回 busy）：

- 修复前新增回归 4 项全错：首个工具调用是 `creo_list_session_models`，
  无任何 `creo_startup_status`；`scenario()` 无输出路径参数；
  `main()` 无独立报告目录。
- 修复后：首个调用为 `creo_startup_status`；busy inventory 停止且不重试、
  不进入 `creo_adopt_file`。

## 2. 修复

`tools/test_file_adoption.py`：

- `scenario(paths, report, output)` 在进入 client 后、任何
  inventory/adoption 之前 `await wait_for_startup(client, report, output)`；
  保持 busy 不重试、accepted job 只轮询、unknown 停止等既有约定，
  `wait_for_startup` 自身负责非 ready 终态与观测超时停止。
- 新增 `report_destination()`：报告目录
  `build/file_adoption_integration_<UTC秒级时间戳>_<uuid8>/report.json`，
  每次调用独立，不覆盖旧报告（旧格式同秒重跑会覆盖同名目录）。
- `main(argv=None)` 在 `try` 前确定 destination 并传入 scenario；
  `finally` 仍把失败/部分记录写入同一独立目录，语义不变。
- 直接脚本与 `-m tools.test_file_adoption` 共用同一代码，入口均保持可用。

不改 `tools/mcp_readiness.py` 契约，不改其他驱动。

## 3. 验证（无 Creo，仅离线假客户端与 --help）

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_file_adoption_driver -v`（修复前） | 4 项全错（复现缺 readiness 前置） |
| `python -m unittest tests.unit.test_file_adoption_driver tests.unit.test_mcp_readiness tests.unit.test_file_adoption -v`（修复后） | 39 项通过 |
| `python tools\test_file_adoption.py --help` | 退出 0，usage 正常 |
| `python -m tools.test_file_adoption --help` | 退出 0，usage 正常 |
| `python -m ruff check tools/test_file_adoption.py tests/unit/test_file_adoption_driver.py` | All checks passed |
| `python -m ruff format --check tools/test_file_adoption.py tests/unit/test_file_adoption_driver.py` | 2 files already formatted |

按要求未跑全量 `tools/dev_check.py`（避免与主代理实机测试时序干扰），
未跑任何实机/native 测试。

## 4. 源码身份

| 文件 | SHA256 |
| --- | --- |
| tools/test_file_adoption.py | （见本次提交） |
| tests/unit/test_file_adoption_driver.py | （见本次提交） |

## 5. 未测范围

- 未连接 Creo/Toolkit/MCP，未运行真实 server，`creo_adopt_file` 全链路
  实机行为未复测（由主代理按守卫流程负责）。
- 未跑全量 dev_check 与全量单测（仅针对性离线套件 39 项）。
- 其他 Python 版本/机器未测。
