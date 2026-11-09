# 开发入口

2026-11-08 [DEV-076](work-items/DEV-076.md)：本地v0.18.4合入当前开发分支，保留DEV-066/075后续离线修复。新增缺头编译与独立包导入回归，发布资料勘误见[统一核对台账](development/RELEASE-POSTCHECK-2026-11-07.md)。本批未连接Creo、未合main、未发布。

从 [统一台账](BACKLOG.md) 定位 ID，读取工作卡的当前摘要，再查相关源码；历史证据按需打开。根级 [AGENTS.md](../AGENTS.md) 是仓库约束，架构与入口分工见 [ARCHITECTURE](development/ARCHITECTURE.md)，编码规则见 [CODING_STANDARD](development/CODING_STANDARD.md)。当前版本以 [version.py](../version.py) 为准，本节不再重复逐版记录。

## 准入与日常维护

1. 开始前核对分支、工作树、未提交改动、合并现场和已有 ID，避免覆盖其他任务。默认从可交付 main 创建 `codex/<条目>-<主题>`；关联集成批以指定提交为基点时，在工作卡记录原因与源码身份。
2. BACKLOG 是唯一当前台账。新增工作先登记未占用 ID、目标、范围、验收及环境。小修复沿用工作卡和证据链接，几行即可；复杂跨模块任务才使用[工作卡模板](templates/WORK_ITEM.md)和完整计划，不另建总台账或第二份待办。
3. 已报告缺陷先复现，分别记录现象和推测根因。诊断交付与根因修复、部分子项交付与整卡完成分别记录；缺其他版本测试不等于代码未修。观察项仅在收到同类新证据后重开调查。
4. BACKLOG 每个 ID 只有一行：优先级、当前状态、目标版本、简短剩余工作、工作卡链接。工作卡首页维护当前结论、剩余范围、依赖和最新证据，旧过程保留日期。无保留范围的完成项移至[完成档案](BACKLOG_COMPLETED.md)，部分完成不关整卡。
5. 实现最小完整改动；格式整理、路径迁移与行为修改分开提交。能力变化同步工具描述、README 和能力边界。PR 使用仓库模板；开发分支提交本身不要求发布。

逐版过程留在对应版本说明和发布记录，不在入口重复回填：[0.19.3 版本说明](RELEASE_NOTES_0.19.3.md)、[0.19.3 发布记录](validation/RELEASE-0.19.3.md)、[0.19.2 版本说明](RELEASE_NOTES_0.19.2.md)、[0.19.2 发布记录](validation/RELEASE-0.19.2.md)、[0.19.1 版本说明](RELEASE_NOTES_0.19.1.md)、[0.19.1 发布记录](validation/RELEASE-0.19.1.md)、[0.19.0 版本说明](RELEASE_NOTES_0.19.0.md)、[0.19.0 发布记录](validation/RELEASE-0.19.0.md)、[0.18.4 版本说明](RELEASE_NOTES_0.18.4.md)、[0.18.4 发布记录](validation/RELEASE-0.18.4.md)、[0.18.3 版本说明](RELEASE_NOTES_0.18.3.md)、[0.18.3 发布记录](validation/RELEASE-0.18.3.md)、[0.18.2 版本说明](RELEASE_NOTES_0.18.2.md)、[0.18.2 发布记录](validation/RELEASE-0.18.2.md)、[0.18.1 发布记录](validation/RELEASE-0.18.1.md)、[版本说明目录入口](../README.md)。源码版本只认 [version.py](../version.py)，启用工具只认 [包内 capabilities](../src/creo_mechdog/capabilities.py)；本地版本号、标签存在与正式 Release 交付不是同一事实，发布核对归原集成负责人。

## 架构与环境

MCP stdio → `server.py` 工具注册 → `bridge.py` 单通道调度/保护 → `generic_bridge.py` 计划校验/登记 → 原生 Toolkit 执行器 → Creo。几何在原生端计算，Python 不模拟 Creo。新业务实现进入 `src/creo_mechdog/`，根级兼容包装与包内必须共享类型；根级实现入口及资源/生成物边界见 AGENTS 与 ARCHITECTURE。

服务 stdout 只承载 MCP。通道忙碌立即拒绝（`isError=true`、`status=busy`、`blocking_*`），不排队、不自动重试；已接受任务只轮询 `creo_get_job`，不能重复提交。现有并发边界见 [BUG-009](work-items/BUG-009.md)。长度为 mm、角度为度；特征 label 小写字母起始，仅小写字母、数字、下划线，最多 28 字符。

开发环境为 Windows x64 / Python 3.12+。语言与单元检查不需要 Creo SDK。建模需 Creo 9/10/12、匹配 SDK、许可和 MSVC x64；当前本机原生验收环境为 Creo 12.4.0.0。Creo 9 编译探测已有修复，本机无 SDK，实机编译/运行未验；其他环境范围见[兼容矩阵](COMPATIBILITY.md)。不要求全项目 Creo 10 独立复测或双版本发布门槛，也不把本机成功外推至其他环境。

本机联调只启用指向 E 盘项目的 `MCP_CREO_MechDog_dev`。BUG-001 关闭不代表事故会话根因已解决，历史失败与 [2026-10-17 恢复记录](validation/BUG-001-recovery-2026-10-17.md) 按原件保留；按 2026-11-09 用户决定，**用户明确确认后即可用 Creo 进行实机测试**（含新建 Toolkit 连接与建模），不再以根因核对或事前会话可操作判定作为阻断前置，确认按次生效。未获确认时默认不主动连接 Toolkit、不启动 Creo；任何情况下不擅自结束 Creo/nmsd、清锁或 unknown 保护，故障注入与进程/保护状态清理需单独明确授权。单通道、busy 立即拒绝、保存重载与证据边界不变，完整规则见 [AGENTS.md](../AGENTS.md)。

## 命令与检查

在仓库根目录 PowerShell 执行；正式安装步骤见 [INSTALL](INSTALL.md)。`requirements-dev.txt` 包含锁定依赖及 editable 安装，变更包布局后同步安装入口、资源路径和分发。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe tools\dev_check.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\test_unit.py
.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit
.\.venv\Scripts\python.exe tools\dev_check.py --strict --skip-unit
```

统一检查覆盖 Ruff、Python/C++ 格式、存量基线比较及全部单元，报告为 `build/development_check.json`、`build/unit_test_report.json`。`--skip-unit` 只提供语言证据，`--strict` 暴露全部欠账。[风格基线](development/style-baseline.json) 按诊断及内容身份容许存量，不能掩盖工具/配置错误、单测失败或新增问题；正常开发与 CI 不重建基线，不新增豁免。

单元阶段默认 900 秒，可用 `--unit-timeout-seconds 1200 --work-item <ID>` 调整；报告区分 passed/failed/timed_out，超时不算通过。单测必须 mock 外部通道和进程，真实 busy 时修夹具，不绕过产品保护。新增用例放 `tests/unit/test_*.py`，使用 unittest；校验或保护变化补回归。冻结源码后执行最终全量，不能用分拆测试代替统一检查。

以下仅为获准原生任务的操作入口，本次文档整理不执行：

```powershell
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
.\.venv\Scripts\python.exe bridge.py build
.\.venv\Scripts\python.exe server.py
.\.venv\Scripts\python.exe tools\test_general.py
```

`native/constants.inc` 必须由本机 SDK 生成，不复制、不提交、不分发。DEV-049 的默认离线驱动与双开关门槛见 [T04](development/DEV049-T04-ACCEPTANCE.md)、[T05](development/DEV049-T05-ACCEPTANCE.md)、[T06](development/DEV049-T06-ACCEPTANCE.md)，历史结果不等于新源码已测。

## 验收与交付

| 改动 | 必要证据 |
| --- | --- |
| 文档 | 链接、ID 唯一性、状态/工作卡、历史原件字节、冲突标记和打包引用；涉及工具或配置时加对应回归 |
| Python 校验/调度/保护 | 统一检查及专项回归；外部进程/会话行为另取实机证据 |
| C++/建模/单位 | 匹配 SDK 构建、对应驱动、实际几何/尺寸/单位、保存重载及适用失败回滚；mm/英寸/混合/未知单位分别声明 |
| 路径/布局迁移 | 安装/客户端/后台入口、资源和数据根、解压源码包验证；原生变化补实机 |
| 合入 main | 未发布新版本、版本元数据、适用验收和打包、标签/Release/附件及 SHA256 远端核对 |

原生成功须任务成功、特征有效、几何断言通过且 `saved_file_reloaded_and_verified=true`。拒绝、超时、unknown、编译通过均不能代替建模成功。证据记录日期、条目、版本、提交、dirty、受测指纹、命令、环境与未测范围；历史证据保留原日期，引用时说明复用边界。

每次合入或直接提交 main（包括文档）都须同次完成对应 GitHub Release；仅合并、推送、标签或草稿不算交付。`version.py` 递增至未发布版本，标签指向合入后的主干提交，附件由该提交生成；旧标签与同名附件不可覆盖，细则见 [RELEASING](development/RELEASING.md)。独立开发分支可以按用户要求只交付本地提交。

<a id="workbuddy-测试约定"></a>

WorkBuddy 一律指公开 MCP 黑盒验收：仅给操作场景、输入、预期和报告要求，不读取源码/配置/Git、不跑本地测试。环境和版本由 MCP 公开接口确认，未提供则“无法确认”；只有实际并发才能报并发通过。内部文件占用/重试预算不纳入黑盒结论。开发者证据与 WorkBuddy 分别记录，完整约定见 AGENTS。

`docs/validation/` 历史原件逐字节保留。稳定契约、安装说明、兼容矩阵和第三方许可继续沿用；`tools/package.py` 递归收集 docs 的 Markdown/JSON，归档不会缩小分发范围，本批不改打包协议。
