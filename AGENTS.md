# Repository Guidelines

## 项目结构与模块划分

- `src/creo_mechdog/` 保存已迁移的 Python 实现与显式路径入口；新的业务模块放在包内，通过标准 editable 安装导入。
- 根目录暂保留 stdio MCP 服务（`server.py`）、任务与构建桥接（`bridge.py`、`generic_bridge.py`）、版本入口（`version.py`）和尚待迁移的校验/建模模块。DEV-002 按批次迁移，保留既有入口和运行数据位置。
- `native/` 保存 C++17 Creo Toolkit 执行器和各类特征实现；`native/third_party/` 保存第三方 JSON 代码及许可证。
- `tests/unit/` 保存新增及已迁移的 Python 单元测试，根 `tests/test_*.py` 为待迁移测试；`tools/` 暂保存实机 Creo 集成测试、打包脚本及验证证据汇总工具。
- `examples/` 保存 JSON 建模方案；`seed_library/` 保存原生 PRT 种子模板及清单；`docs/` 保存安装说明、功能边界和验证记录。
- `.venv/`、`build/`、`jobs/`、`models/` 是本机运行生成的目录。

当前布局与迁移目标分别记录在 `docs/development/ARCHITECTURE.md`。首批只建立规范；Python 包化、C++ 上下文提取及独立编译由 DEV-002～DEV-004 分批推进，每批同时核对入口、路径、安装和打包。

根模块职责（迁移期间按此理解入口，不要在未登记条目时改写）：

- `server.py`：MCP stdio 入口与工具注册；业务逻辑不写在该文件。
- `bridge.py`：Toolkit 调度与执行器子进程生命周期；Toolkit 通道锁的唯一持有者。
- `generic_bridge.py`：执行器子进程的 stdin/stdout 桥接；不解析业务语义。
- `creo_startup.py`：受限的后台 Creo 启动与跨本地 MCP 进程协调（根目录 `toolkit.lock`）；实现模块，非转发包装。
- `capabilities.py`：工具清单及启用/禁用来源；新增或停用工具必须在此登记。
- `schema.py`、`profile_checks.py`、`airfoil.py`、`seeds.py`：根目录兼容模块，只转发导出；新逻辑进 `src/creo_mechdog/`。
- `version.py`：服务与源码版本的唯一来源，合入 `main` 时同步更新。

## 请求流与运行时架构

一次建模请求的实际路径：MCP 客户端（stdio）→ `server.py`（工具数以 capabilities 为准，本开发分支93个）→ `bridge.py`（revision 校验、保护策略、子进程与终态登记）→ `generic_bridge.py` → 由 `native/*.cpp` 编译出的 Creo Toolkit 执行器（单一通道串行）→ Creo Parametric 进程。客户端只看到任务 `job_id` 与 `model_id`；几何计算全部在原生执行器内完成，Python 侧不模拟 Creo 行为。

两条并存的 Python 轨道：`src/creo_mechdog/` 是标准可编辑包（安装声明见 `pyproject.toml`），新业务模块放包内；根目录同名的 `schema.py`、`airfoil.py`、`profile_checks.py` 及 `server.py`、`bridge.py`、`version.py` 保留兼容包装。包内实现与根包装同时进入源码身份清单，二者对同一类型必须共享定义，不能出现两套模型。

只读分发资源（`seed_library/`、`examples/`、`docs/`、`native/`）与本机生成内容（`.venv/`、`build/`、`jobs/`、`models/`、`native/constants.inc`、`config.json`、`client-config.json`、根目录 `seed_registry.json` 与 `toolkit.lock`）严格分开；生成物不得进入源码包或发布附件。

关键边界：服务标准输出只承载 MCP 协议消息；Toolkit 通道忙碌时立即拒绝新提交（`isError=true` 且 `status="busy"`，携带 `blocking_*` 与重试指引），不排队、不自动重试；任务在锁内收尾，释放通道后才发布持久化终态，因此其他客户端可能在旧任务返回后取得通道。并发能力现状归 BUG-009，未新增队列时不要假设 FIFO 或容量保证。

## 开发准入与台账

- 以 `docs/DEVELOPMENT.md` 为开发入口、`docs/BACKLOG.md` 为唯一工作台账；每项功能、缺陷或工程整理在实现前登记固定 ID、目标、范围、验收方式和环境。小修复可精简，复杂条目使用 `docs/templates/WORK_ITEM.md`。
- 先复现已报告缺陷，分别记录现象与推测根因。优先处理 P1 稳定性问题，再扩展建模能力。
- 条目验收后同步状态、能力边界和本次证据。旧版本说明、测试日志和待办快照保留其历史日期，不作为当前台账。

## 构建、测试与开发命令

在仓库根目录使用 PowerShell 执行以下命令。安装需要 Windows x64、Python 3.12+、Creo 9、10 或 12、匹配的 Toolkit SDK、可用许可及 MSVC x64 构建工具。Creo 9 与 Toolkit 9 已纳入支持/要求范围（支持范围见 `docs/COMPATIBILITY.md`）：[BUG-033](docs/work-items/BUG-033.md) 编译探测修复已实现；本机无 Creo 9 SDK，Creo 9 实机编译与建模运行时均未验收，其他环境按反馈补录。

- `.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'`：创建虚拟环境、安装锁定版本的依赖、生成配置和常量表，并编译执行器。请替换为实际安装路径。
- `.\.venv\Scripts\python.exe bridge.py build`：编译变更后的原生源码，或复用已有执行器。
- `.\.venv\Scripts\python.exe server.py`：启动本地 stdio MCP 服务。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：运行单元测试。
- `.\.venv\Scripts\python.exe tools\test_unit.py`：运行单元测试并生成 `build/unit_test_report.json`。
- `.\.venv\Scripts\python.exe tools\test_general.py`：连接已打开的 Creo 会话，执行原生建模集成测试。
- `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`：安装锁定的运行与开发依赖；纯单元/语言检查无需 Creo SDK。
- `.\.venv\Scripts\python.exe tools\dev_check.py`：检查新增语言问题并运行全部 Windows 单元测试，生成 `build/development_check.json`。
- `.\.venv\Scripts\python.exe tools\dev_check.py --strict --skip-unit`：暴露全部存量语言问题；不是原生建模验收。
- `.\.venv\Scripts\python.exe -m pip install --no-deps -e .`：拉取源码更新后同步包内模块；`setup.ps1` 已包含该步骤，开发环境手动执行一次即可。

服务名称与客户端注册键统一为 `MCP_CREO_MechDog`；`client-config.json` 是该配置的 `mcpServers` 格式样例，其 command/args 必须与安装实际路径一致。

## 代码风格与命名约定

Python 使用四个空格缩进，函数和模块采用 `snake_case`，类采用 `PascalCase`；Ruff 配置位于 `pyproject.toml`。C++ 保持 C++17 和 Toolkit 命名，格式配置位于 `.clang-format`，保留 include 顺序。具体错误处理、类型标注、资源管理规范见 `docs/development/CODING_STANDARD.md`。格式清理按模块独立提交，排除第三方、SDK 和生成文件。

历史问题记录在 `docs/development/style-baseline.json`，默认检查拒绝新增诊断和变更后仍未格式化的文件。工具/配置错误与单测失败不能加入基线；基线新增容许项必须关联条目、说明原因并单独审查，禁止在正常开发或 CI 中自动重建。`docs/validation/` 下的历史反馈原件必须逐字节保持一致，该目录已在 `pyproject.toml` 的 Ruff 配置中排除；不要对其重排或格式化。

长度使用毫米，角度使用度。特征标签以小写字母开头，仅包含小写字母、数字和下划线，最多 28 个字符。服务标准输出仅用于 MCP 协议消息。

Toolkit 调用共用单一通道：提交时通道忙碌立即返回 `status="busy"`（`isError=true` 并给出 `blocking_job_id`/`blocking_model_id`/`blocking_operation`），不重试、不排队。新增并发或调度原语前先核对 BUG-009 记录的边界，不要假设已存在队列或公平调度；已接受的任务只轮询 `creo_get_job`，不重新提交。

## 测试要求

### WorkBuddy 测试约定（项目全局）

- 用户提到“WorkBuddy 测试”“用 WorkBuddy 测试”或要求给 WorkBuddy 测试提示词时，均指通过 WorkBuddy 直接调用已连接的 MCP 工具，对最终用户可见行为做黑盒验收。此约定适用于整个项目，不限于 BUG-002。
- WorkBuddy 不查看、分析或修改源码，不执行本地 Python 测试脚本、单元测试、开发检查或源码压力探针；测试提示词只提供 MCP 操作场景、输入、预期结果和报告要求。
- 环境、会话、可见工具与服务版本通过 MCP 公开接口确认。接口未提供的构建身份或实现细节记为“无法确认”，不要求读取仓库、Git 状态或本机配置来补齐。
- 验收以工具实际返回及 Creo 中的实际结果为准，记录工具调用、输入、job_id/model_id、终态、几何/参数、保存重载、revision、回滚和原始错误；只有真实实施了并发调用，才能报告并发测试通过。
- 只能靠源码或本地脚本验证的内部机制（例如文件占用注入、重试次数/预算、临时文件清理）不纳入 WorkBuddy 结论。无法由 MCP 观察的项目明确记为“未验证”，不得推测通过。
- 下面的开发者测试要求继续用于实现与回归阶段；本地测试证据和 WorkBuddy 最终 MCP 验收分别记录，不互相替代。用户明确要求改变 WorkBuddy 范围时，以当次要求为准。
- 运行在 WorkBuddy 或其他客户端会话内的 Agent 不得用本文件的开发者要求替代该约定：不执行 `tools/test_*.py`、`tools/dev_check.py`、单元测试或源码探针，也不读取本机配置与仓库状态来补齐报告。该限制只约束 WorkBuddy 黑盒验收，实现与回归阶段仍按下一段执行。

单元测试使用 `unittest`，新增文件命名为 `tests/unit/test_*.py`，测试方法命名为 `test_*`；现有 `discover -s tests` 递归发现入口继续覆盖两种布局。修改输入校验或保护逻辑时补充回归用例。项目未设置数值化覆盖率门槛。修改原生建模代码后，运行对应的 `tools/test_*.py`，检查任务成功、几何断言通过，以及 `saved_file_reloaded_and_verified` 为 `true`。明确记录本次验证范围，不能用历史证据代替当前验证。

Windows CI 仅承担语言与单元检查；当前开发与发布的原生验收使用本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 和许可，按实际改动范围取得证据。2026-10-15 用户取消全项目 Creo 10 独立复测、双版本验收及正式基线门槛，不因缺少 Creo 10 结果阻塞完成、合入或发布。朋友反馈具体问题后再登记或沿用条目跟进；历史版本、环境和未测事实保留，不把本机通过外推为其他环境通过。Creo 9 与 Toolkit 9 的编译探测修复已实现，本机无 Creo 9 SDK，实机编译及建模运行时均未验收，范围见 `docs/COMPATIBILITY.md`。新证据记录条目、源码提交与 dirty 状态、受测源码指纹、命令、环境和未测范围。

## 提交与合并请求要求

历史提交保留原样。新提交标题简短指出条目 ID 和具体变更。`main` 保持可交付，开发使用 `codex/<条目>-<主题>` 短分支。合并请求使用 `.github/pull_request_template.md`，说明影响范围、关联条目、列出验证命令及结果、注明 Creo 环境，并提供适用的建模证据。支持能力发生变化时，同步更新能力说明文档。

`version.py` 是服务/源码版本入口。开发分支上的普通提交不要求发布；合入 `main` 时必须按下述全局要求及 `docs/development/RELEASING.md` 完成对应版本发布。已发布标签和同名附件不得覆盖。

### 合入 main 与 Release（项目全局）

- 每次将变更合入或直接提交到 `main`，必须在同一次交付流程中生成并发布对应版本的 GitHub Release，适用于功能、修复、文档和工程配置变更。仅合并、推送、创建标签或保存 Release 草稿均不算交付完成。
- 合入前确定未发布的目标版本，按版本规则同步 `version.py`、相关版本元数据及版本说明；Release 标签统一为 `v<version.py 中的版本号>`。新的主干变更不得复用已发布版本号。
- 按发布规则完成适用验收和打包；Release 标签必须指向本次变更合入 `main` 后对应的主干提交，附件必须由该提交源码生成，并附版本说明、验收摘要、环境、未测范围及 SHA256。
- 合入后核对远端提交、标签、Release 和附件，交付记录提供提交号、版本号、Release 链接及附件校验结果。发布失败或附件缺失时仍属未完成，须明确记录原因并继续补齐，不得只报告“已合入 main”即结束。

## 配置与许可

本机路径写入已被 Git 忽略的 `config.json` 和 `client-config.json`。不要提交生成的常量表、二进制文件、日志或测试模型。保留第三方许可声明，不要提交 PTC SDK 文件或许可数据。

`native/constants.inc` 由 `tools/generate_constants.py` 依据本机 Creo SDK 生成，属于本机生成物：不提交、不从其他机器或构建缓存复制、不进入发布附件；更换 Creo 或 SDK 版本后必须重新生成。

## 本机开发联调补充（2026-10-17用户要求）

本机所有Creo MCP联调只启用 `MCP_CREO_MechDog_dev` 并指向 `E:\Projects\MCP_CREO_MechDog`；旧C盘副本和test项禁用。发布默认服务标识仍为MCP_CREO_MechDog，本条是本机开发客户端约定。BUG-001于2026-10-17按用户决定关闭，但此前实机回归Creo卡死根因未定，继续停止新的Toolkit连接/故障注入；先完成根因核对并确认会话可操作，不能擅自继续、结束Creo或清unknown保护。详见docs/validation/BUG-001-recovery-2026-10-17.md。
