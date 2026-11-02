# DEV-002 第三批：种子与能力模块包化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将根目录 seeds/capabilities 的唯一业务实现迁入 Python 包，保留旧导入和种子 CLI，并证明安装、路径、源码身份和 MCP 行为兼容。

**Architecture:** 包内保存唯一实现；根目录保留与 schema/profile_checks/airfoil 相同模式的薄导出包装，seeds 的脚本入口只调用包内 main。保留种子模块对既有 bridge 路径和 JSON I/O 的依赖，本批通过显式安装声明解决仓库外导入，不提前重写桥接基础设施。

**Tech Stack:** Windows x64、Python 3.12+、setuptools editable 安装、unittest、现有 MCP 服务；条件性原生验收使用本机 Creo 12.4.0.0 / 匹配 SDK。

**Spec:** [DEV-002 第三批设计与边界](../../work-items/DEV-002.md#第三批任务卡种子与能力模块迁移)；[总体架构](../../development/ARCHITECTURE.md)。

登记：2026-11-02。状态：用户后续要求本会话直接执行；实现及独立分发验证完成，最终统一检查通过（2196 项、0 失败/错误），T5 实机待验。沿用固定 ID **DEV-002**，不增加台账任务行。计划调查基点为 `0f6c085324c0df016e73fe1a088d5e731147ad12`，执行时重新记录 HEAD 与 dirty，不能把该提交当成未来受测源码。

执行方法更新：用户随后要求本会话直接完成，按 executing-plans 串行实施并进行一次独立审查；以下派工提示词保留作原始计划参考。一个 agent 可以按 T0→T6 串行完成；分给多名 agent 时，按下表分工。

## Global Constraints

- 新业务实现进入 `src/creo_mechdog/`，通过标准 editable 安装导入；不得新增业务模块的 `sys.path` 补丁。
- 服务名称与客户端注册键为 `MCP_CREO_MechDog`；本机联调只用 `MCP_CREO_MechDog_dev` 指向 `E:\Projects\MCP_CREO_MechDog`。
- 本批保持公开工具集合、参数 schema、能力声明、错误语义、seed SHA256、任务/revision/恢复行为；工具数以执行起点清单为准，规划时为 95。
- 资源与运行数据仍在原安装根目录；不在 `src/creo_mechdog/` 下创建 `jobs/`、`models/`、`build/`、配置或种子注册表。
- 长度使用毫米，角度使用度。服务标准输出仅用于 MCP 协议消息。
- Toolkit 忙时立即拒绝、不排队、不自动重试；已接受作业只轮询。锁仍由 bridge 的既有入口管理。
- BUG-001 现场约束继续适用：未经根因核对与会话可操作确认，不新增 Toolkit 连接或故障注入，不结束 Creo，不清 unknown 保护。普通 stdio 启动也可能触发后台启动，不视为离线。
- 不修改原生实现、服务/启动/桥接业务、版本号、种子字节或受信摘要；不执行 C 盘旧部署更新。
- `docs/validation/` 历史证据逐字节保留；不得重建/扩充风格债务容许项。仅允许单独审查更新本批 pyproject 配置哈希。
- 当前授权是规划与后续开发交接；本计划不自动合入 main、不推送、不发布。若后续获授权交付 main，必须使用未发布版本并在同次流程完成正式 Release 及附件核对。

## Review Focus

1. 仓库外首次导入 seeds 时也能找到 bridge；安装可见性不能依赖当前目录或残留 PYTHONPATH。测试归 T3/T4。
2. `setup.ps1` 调用的 `python seeds.py --install` 继续工作，成功输出为单个 JSON；失败仍非零退出。测试归 T2。
3. 根包装转发的函数使用包内全局变量；旧测试 patch 根模块的 manifest 后可能失效，必须调整 mock 目标并保持断言。测试归 T1/T2。
4. 只改包内 seeds/capabilities 时，服务仍识别源码已改变；指纹不能只覆盖根包装。测试归 T3。
5. 从新 ZIP 解压并独立安装后，资源、配置和数据定位仍属于解压副本；不能误导入原 E 盘 checkout。测试归 T4。

## 派工与文件归属

| 任务 | 建议负责人 | 主要文件 | 前置与交付 |
| --- | --- | --- | --- |
| T0 基线记录 | 集成 agent C | 新运行目录中的基线/契约快照 | 所有实现前；把基点与快照交给 A/B |
| T1 能力模块 | agent B | capabilities.py、src/creo_mechdog/capabilities.py、tests/unit/test_capabilities_layout.py、受影响能力测试 | T0 后；可与 T2 并行 |
| T2 种子模块 | agent A | seeds.py、src/creo_mechdog/seeds.py、tests/unit/test_seeds_layout.py、受影响种子测试 | T0 后；可与 T1 并行 |
| T3 入口与安装集成 | agent C | server.py、bridge.py、generic_bridge.py、pyproject.toml、共享布局测试、相关 tools 导入 | T1/T2 后串行集成 |
| T4 离线验收与分发 | agent C | tests/unit/test_package_migration.py、安装夹具、本次证据 | T3 后 |
| T5 条件性实机 | 单一实机负责人 | 本次独立运行目录与验收记录 | T4 后，且会话条件与现有授权均满足 |
| T6 文档与交接 | agent C | DEV-002 工作卡、主台账、ARCHITECTURE、AGENTS、本次证据 | 依据真实阶段结果回填 |

A/B 不修改共享的 server.py、bridge.py、generic_bridge.py、pyproject.toml、test_helper_layout.py 或主台账；需要的接线改动写入交接说明，由 C 集成。没有相互隔离的 checkout 时按串行执行，避免共同编辑同一工作区。新 checkout 按项目工具创建并独立安装，不能重装当前共享虚拟环境来指向另一个 checkout。

## T0：冻结实际基线

**Files:** 只读现有源码；新建 `build/dev002_batch3_<run_id>/` 存放本轮过程证据。

**Interfaces:** 向 T1/T2 提供起点提交、dirty、工具契约及能力数据；不调用服务 lifespan 或 Toolkit。

- [x] 记录分支、HEAD、dirty 和受测源码指纹，标记已有 session_activity.json、客户端目录及其他用户改动，禁止覆盖或清理。
- [x] 审查本次选中的单元用例不会访问真实会话，运行当前种子/能力/路径对应回归，记录既有失败及原始错误。
- [x] 在 mock 启动器、更新线程、原生提交的条件下，读取服务注册的工具名及输入 schema；对比时不依赖工具顺序。
- [x] 保存当前 REGISTERED_OPERATIONS、UNAVAILABLE_OPERATIONS、families() 与种子公开输出的契约快照。时间、绝对根路径等环境字段单列；业务字段逐字段比较。
- [x] 记录 `setup.ps1` 的 seeds.py --install 调用、两处 generic_bridge 动态 import seeds、源码身份清单、安装元数据及测试 mock 路径。

验收：有可复核基线，且没有启动 MCP 传输、后台 Creo 或 Toolkit。既有失败不能在后续报告中被省略或称为通过。

## T1：迁移 capabilities 的唯一实现

**Files:** 新建 `src/creo_mechdog/capabilities.py`、`tests/unit/test_capabilities_layout.py`；修改根 capabilities.py。调整确有 mock/导入依赖的 `tests/unit/test_t01_capability_contracts.py`、`test_t04_arbitrary_plane_coordinates.py`、`test_t08_feature_state.py`、`test_support_status.py`、`tests/test_v021_validation.py`。

**Interfaces:** 保持 `REGISTERED_OPERATIONS`、`UNAVAILABLE_OPERATIONS`、`require_available(operations: list[dict]) -> None`、`families() -> dict`。根/包对象身份相同；函数以包内实现为唯一来源。

- [x] 先新增失败回归：`test_legacy_exports_share_objects` 逐一用 assertIs 核对上述常量/函数；冻结的 `contract_before.json` / `contract_after.json` 核对全部操作与 families 数据；`test_unavailable_operation_still_rejected_before_submission` 核对拒绝发生在锁和目录创建之前。
- [x] 运行 `python -m unittest discover -s tests/unit -p test_capabilities_layout.py -v`，确认失败源于包内模块尚未迁移。
- [x] 将现有实现迁入包内；根文件按 schema.py 的 __getattr__/__dir__/__all__ 模式薄导出。保留私有属性的既有 getattr 可访问性，不另写一套常量。
- [x] 消费者测试从包内导入；patch 包内定义位置，`patch.dict` 与共享字典身份语义保留。不得削弱原有拒绝断言。
- [x] 重跑新增回归及现有能力、分页、支持状态和 v021 校验回归，全部通过后提交 `DEV-002: migrate capabilities implementation into package`。

## T2：迁移 seeds 并保留命令行入口

**Files:** 新建 `src/creo_mechdog/seeds.py`、`tests/unit/test_seeds_layout.py`；修改根 seeds.py，以及 `tests/unit/test_seed_listing.py`、`test_seed_distribution.py`、`test_release_integrity.py`、`tests/test_portable_modeling.py` 中受影响导入/mock。

**Interfaces:** 保持原 seeds 函数签名与返回结构：expected_archive_sha256、manifest、library_directories、manifest_entry_by_digest、list_seeds、select_seed、validate_seed、install_seed_library；私有 _checked_seed/_validate_library 仍可由旧模块访问。新增包内 `main(argv: list[str] | None = None) -> int`。

- [x] 先新增失败回归：`test_legacy_exports_share_objects` 核对函数身份；`test_cli_listing_emits_one_json_object`、`test_cli_install_directory_uses_fixture_root`、`test_cli_rejects_directory_and_archive_together` 核对现有 CLI 行为，所有安装写入使用隔离夹具，不能写本仓库 seed_registry.json。
- [x] 运行 `python -m unittest discover -s tests/unit -p test_seeds_layout.py -v`，确认新包入口尚不存在导致失败。
- [x] 迁入唯一实现；现有 argparse 和 JSON 输出放入包内 main，成功返回 0，参数错误/业务异常保持非零退出和原错误，不新增吞异常逻辑。
- [x] 根文件只保留薄导出和 `if __name__ == '__main__': raise SystemExit(_implementation.main())`；保留 --install、--archive-file、--directory 和默认列举行为。
- [x] 保留调用时使用 bridge.ROOT/read_json/write_json 的现有行为，避免新加导入时配置读取、建目录或 Creo 调用；本批不复制桥接 I/O，也不改持久化语义。
- [x] 将 patch.object(seeds, 'manifest', ...) 等测试的 seeds 指向包内实现；为根旧入口单独保留身份和 CLI 回归，不能靠删除原测试解决 mock 失效。
- [x] 重跑 `python -m unittest discover -s tests/unit -p 'test_seed*.py' -v`、release_integrity 和根 tests/test_portable_modeling.py 对应回归；覆盖篡改 ZIP、目录逃逸、许可差异、哈希失配、来源未知、缺文件和不连接 Toolkit。通过后提交 `DEV-002: migrate seeds and preserve legacy CLI`。

## T3：接线、安装声明与源码身份

**Files:** 修改 server.py、bridge.py、generic_bridge.py、pyproject.toml、tools/summarize_evidence.py、tools/summarize_development.py、tools/summarize_portable_modeling.py、tools/test_mcp.py、tests/unit/test_helper_layout.py、test_paths.py；新增 tests/unit/test_package_migration.py。仅按实际需要修改 tools/package.py。

**Interfaces:** 新代码使用 `creo_mechdog.seeds` / `creo_mechdog.capabilities`；兼容旧入口。安装声明保留原 version/schema/airfoil/profile_checks，并加入 seeds、capabilities 和现存依赖 bridge；不移动 bridge 实现。

- [x] 新增 `test_external_cwd_imports_resolve_same_checkout`，在全新独立环境和仓库外 cwd 验证包、根包装及 bridge 全部来自同一 checkout；先确认遗漏安装声明时失败。
- [x] 新增 `test_legacy_first_and_package_first_imports`，在新子进程覆盖两个导入顺序；禁止依赖 PYTHONPATH 或手动 sys.path。单独覆盖配置不存在时纯导入成功且不创建运行目录。
- [x] 调整三个根消费者及当前工具脚本导入；覆盖 generic_bridge 两处动态导入，不修改其业务流程。历史归档脚本保持不变，仍通过包装兼容。
- [x] `pyproject.toml` 的 py-modules 加入 bridge/seeds/capabilities。bridge 当前导入依赖已在包内或 capabilities，运行 CLI 时的数据位置继续由根 bridge.py 决定；这只是安装可见性补齐，不代表桥接已完成包化。
- [x] server._SOURCE_NAMES 同时保留两个根包装，并加入 src/creo_mechdog/seeds.py、src/creo_mechdog/capabilities.py；当前汇总工具的 code_paths 同步覆盖两份实现，不把历史报告当成本批证据。
- [x] 扩展迁移测试：`test_runtime_detects_each_new_implementation_change` 在临时源码副本逐一修改两个实现，重置 capabilities 快照，断言 source_changed_since_startup=true；根包装也在指纹集合中。
- [x] 更新 `docs/development/style-baseline.json` 时仅单独审查 pyproject 配置哈希；不得增加 lint/format 容许项，不运行 --write-baseline。被迁入的新路径必须符合格式要求，不能继承旧路径债务。
- [x] 运行 helper_layout、paths、package_migration 和现有能力/种子回归，核对 T0 工具集合、输入 schema 与业务输出一致。通过后提交 `DEV-002: wire package imports and installation identity`。

## T4：离线完整验收与新 ZIP 安装

**Files:** T3 新测试；按需要更新 `tests/test_installation_validation.py`、`tests/unit/test_setup_native_stderr.py` 中源码复制夹具；新建本批验收文档 `docs/validation/DEV-002-batch3.md`，本次原始报告进入独立运行目录。

**Interfaces:** 输出源码包 SHA256、独立安装记录、纯离线检查结果及全部未验范围。

- [x] 确认安装夹具复制了新包实现和根包装；禁止仅因工作区 editable 安装残留而通过。
- [x] 验证 package.source_files() 包含两个实现、两个包装和新增测试，排除 config.json/client-config.json、seed_registry.json、native/constants.inc、SDK、二进制和运行目录。
- [x] 审查全量用例的会话副作用后，运行 `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-002-batch3`；要求 success=true、unit_tests=passed、无新增语言问题。若环境错误/超时/失败，保留原始输出并处置，不能写入风格基线或改称“通过”。
- [x] 选取唯一新运行目录，先运行 `tools/package_seeds.py --output <run_dir>/seed-library.zip`，再运行 `tools/package.py --seed-archive <run_dir>/seed-library.zip --output <run_dir>/source.zip`；均以开发副本 Python 执行，不覆盖既有附件，不使用 --allow-record-mismatch 绕过闸门。
- [x] 解压到独立临时目录，在该副本新建虚拟环境并安装其 requirements-dev.txt；清除测试子进程 PYTHONPATH/用户站点干扰，从解压目录之外导入根 seeds/capabilities/bridge 和包内模块，核对路径全部属于副本。
- [x] 在副本使用模拟种子/配置验证目录注册和 CLI，输出文件只进入副本；运行对应迁移回归，核对 resource_root/data_root、源码指纹和版本入口，不启动 server.py 传输。
- [x] 将环境、命令、提交/dirty/源码指纹、输出 ZIP 哈希、测试数量/失败项及未验范围写入本批记录。此时可记“离线开发验收通过”，不能记“实机/整个 DEV-002 完成”。

`test_package_migration.py` 对应可执行命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p test_package_migration.py -v
```

本批没有 C++ 改动，离线阶段不要求原生重编。若受信种子包闸门已因其他并行任务失配，记录为真实阻塞并协调归属，不擅自更新版本或摘要。

## T5：有条件后置的协议与建模验收

**Files:** 复用现有实机驱动及其公开操作；本批证据单列。全过程只有一个负责人占用 Toolkit 通道。

**Interfaces:** T4 的准确源码与安装身份；输出真实 job_id/model_id、终态、几何、保存重载及 revision。

- [x] 先核对当前用户授权、BUG-001 恢复记录及会话可操作状态；条件不足就写“待实机验收”，不启动服务或工具。WorkBuddy 未执行时单列未验证，不推测通过。
- [ ] 满足条件后验证真实 MCP 工具清单、schema、capabilities compact/full 分页、种子列举和校验。现有 `tools/test_mcp.py` 即使不加 --create 也调用 creo_session_status，且启动 lifespan，因此只在本阶段使用；其固定报告名应先在本批驱动副本改为唯一输出，不能覆盖历史文件。
- [ ] 使用执行时真实清单中的可用两截面种子，完成自动选种建模和一次参数编辑；记录所用 seed_file/feature_id/SHA256，检查原生几何与体积、revision、saved_file_reloaded_and_verified=true，并确认原种子字节不变。操作沿用 tools/test_portable_modeling.py 的已存在场景，输出到新的 --output-dir，按脚本实际支持的阶段执行，不臆造 CLI 参数。
- [ ] 保存本轮协议和建模原始回执；失败或 unknown_outcome 时停下保留现场，不重提、不杀 Creo、不清保护。回滚仅在真实执行了相应失败场景时报告结果。

本批不要求 Creo 9/10 独立复测。实机条件尚未满足，不妨碍交付可审查的离线分支，但不得提前关闭本批的后置验收。

## T6：文档、状态与交接

**Files:** docs/work-items/DEV-002.md、docs/BACKLOG.md、docs/development/ARCHITECTURE.md、AGENTS.md、docs/validation/DEV-002-batch3.md。

- [x] 按实际完成范围把第三批从“已规划”推进到“开发中/离线验收通过/后置验收完成”，整个 DEV-002 仍按剩余迁移范围保留开发中。
- [x] 同步 AGENTS 根模块职责：seeds/capabilities 迁移实际完成后才写成薄导出；server/bridge/creo_startup 仍是实现入口；generic_bridge 仍承担计划校验、登记、revision 与结果处理，不能写成单纯 stdin/stdout 转发。
- [x] 更新架构当前批次与唯一台账行，不改写前两批历史验收日期；不新增 DEV-002 重复条目，不顺带重算无关统计。
- [x] 最终交接列出变更文件、提交、环境/源码身份、逐项结果、未验范围、剩余根模块职责和风险；提交仅在开发分支，逐提交带 DEV-002。是否 main/Release 由后续交付授权决定，不在本计划预定版本号。

## 可复制派工提示词

给单个执行 agent：

> 请在 E:\Projects\MCP_CREO_MechDog 按 docs/superpowers/plans/2026-11-02-dev002-batch3-package-migration.md 和 docs/work-items/DEV-002.md 执行 DEV-002 第三批，先读 AGENTS.md 与开发入口。从 T0 开始，在 codex/DEV-002-batch3-package 开发分支按任务提交，完成 seeds/capabilities 包化、旧导入/CLI 兼容、源码指纹、安装打包与离线验收。保留用户现有改动，不扩展到服务/桥接/C++ 重构。T5 是条件性后置实机阶段，条件不足只记录未验；不擅自连接 Toolkit、结束 Creo 或清 unknown。不合 main、不推送、不发 Release。完成后交付可审查分支、证据、未验范围并同步 DEV-002 台账。

分给多个 agent 时，将上述提示词中的任务范围分别替换为：

- A：仅 T2，分支 `codex/DEV-002-batch3-seeds`，交接接口/测试结果，不修改集成共享文件。
- B：仅 T1，分支 `codex/DEV-002-batch3-capabilities`，交接接口/测试结果，不修改集成共享文件。
- C：负责 T0、集成 A/B 后的 T3/T4/T6；T5 条件满足时由单一负责人串行执行。先把 T0 基线交给 A/B，再接受其提交。

## 后续批次入口

第三批完成后，另行规划服务工具注册与能力 payload 的职责提取，再处理启动协调、桥接中的构建/作业结果职责；每批分别核对包与根依赖。C++ 上下文与独立编译继续归 DEV-003/DEV-004。本计划不提前规定这些后续批次的新接口或完成状态。

## 本次执行说明

- T0—T4/T6 已按本批证据推进，最终统一检查通过（2196 项、0 失败/错误）。T5 入场条件核对后保留实机待验，后续三项不勾选。
- 原两个业务模块已格式合规，无需单独格式提交；受影响的三个旧独立工具先单独格式提交，再接线。
- 外部 cwd 回归验证了 py-modules 缺失的失败→成功；首次全新解压暴露旧测试缺 .tmp 父目录，已修复并在第二个新环境 64 项通过。
- [本批验收记录](../../validation/DEV-002-batch3.md)记录实际结果；不因勾选实现步骤而宣称实机或整个 DEV-002 完成。

## 用户追加的交付授权（2026-11-02）

用户在离线验收完成后明确要求“直接合并到 main 里面发布”。该授权取代本计划原先不合 main/不推送/不发布的阶段边界；本批以兼容工程整理 PATCH 0.11.5 发布，T5 实机仍未执行，整个 DEV-002 不关闭。发布输入和远端核对见 [RELEASE-0.11.5](../../validation/RELEASE-0.11.5.md)，此前开发证据保持原样。
