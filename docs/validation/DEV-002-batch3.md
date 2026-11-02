# DEV-002 第三批：种子与能力模块迁移验收

日期：2026-11-02（Asia/Shanghai）。状态：**实现及离线验收完成；最终统一检查 success=true、2196 项零失败/错误；条件性 T5 实机待验。** 整个 DEV-002 仍为开发中。

## 身份与范围

- 分支：`codex/DEV-002-batch3-package`；起点：`0f6c085324c0df016e73fe1a088d5e731147ad12`。
- 服务／源码版本保持 `0.11.4`；本批未合 main、未推送、未创建标签或 Release，不是已发布 0.11.4 附件的一部分。
- 核心迁移提交：`27e62c1`（capabilities）、`efbb139`（seeds/CLI）、`0e92ab7`（消费者、安装、指纹）、`3ffdd02`（仅配置哈希审查）；独立测试夹具修复：`24e4e37`。规划登记 `9f03623`，受影响旧工具格式整理 `76f7c9b`。
- 受测工作区 dirty=true：保留原有 `session_activity.json` 和客户端目录；最终轮还包含本批文档回填。提交号不单独代表全部受测源码，精确身份以本轮源码指纹和归档 SHA256 为准。
- 原始过程目录：`build/dev002_batch3_20261102T141301Z/`；过程中的失败日志、首个归档及第二版归档全部保留，未覆盖旧证据。
- 环境：本机 Windows x64 / Python 3.12.14；Ruff 0.17.0 / clang-format 23.1.3；独立环境按锁文件安装依赖。无原生源码变更，未连接 Creo、未构建或调用 Toolkit。

本次最终统一检查的 `checked_source_sha256`：`b87c277ee99e347497a3cc37e3030fd9c47a735c67f1d1ef6b764080eb0de8af`；服务运行源码指纹清单（排序 JSON）的 SHA256：`ffc80d0a7357bdb066277c2d0dbe35f2f8ea038a093288757908596d82035787`。完整逐文件指纹见本轮 `source_fingerprints_final.json`，摘要见 `validation_summary.json`。实际系统为 Windows 11 x64 / 10.0.26100。

## 交付行为

`src/creo_mechdog/seeds.py` 和 `capabilities.py` 保存唯一实现。根同名模块采用既有辅助模块的薄导出模式；新旧导入共享对象，旧私有 seed helper 的 getattr 访问仍兼容。根 seeds CLI 交给包内 `main(argv)`，保留默认列举、--install、--directory、--archive-file、单个 JSON 成功输出和非零错误退出。

生产消费者与当前工具脚本改用包内入口；受影响测试 mock 改到包内定义位置，原断言未删除。服务源码身份同时覆盖两个根包装和两个新实现。标准 editable 安装额外声明 bridge/seeds/capabilities，使仓库外导入不依赖当前目录；bridge 实现、ROOT 和 JSON I/O 仍在根目录，资源和运行数据位置保持原样。

未修改工具参数、能力/错误语义、任务调度、模型登记、revision、恢复逻辑、种子字节/受信摘要、原生实现或版本号。AGENTS 与架构文档按实际职责纠偏，后续服务、启动和桥接继续分批迁移，C++ 整理继续归 DEV-003/DEV-004。

## 当前证据

| 阶段 | 命令／方法 | 实际结果 |
| --- | --- | --- |
| T0 基线 | 不进入 lifespan，直接读取 MCP 注册 schema，mock 掉启动和 Toolkit 入口；相关 unittest | 95 工具；79 测试通过；`contract_before.json`、`source_before.json`、`baseline_tests.log` |
| T1/T2 RED→GREEN | 新增 capability/seed 兼容与 CLI 回归，再迁移实现 | RED：7 项中的 4 项因缺新模块报错；GREEN：123 项模块/保护/种子回归通过；`migration_red.log`、`modules_green.log` |
| T3 RED→GREEN | 仓库外隔离子进程导入、两种导入顺序、纯导入审计、服务身份、源码变化检测 | RED：5 个断言失败，揭示安装缺失和服务仍使用根模块；GREEN：23 项通过；`integration_green.log` |
| 契约比较 | 规范化 JSON 比较冻结的工具 schema、全部 operations/unavailable/families 与种子输出 | 迁移前后完全相同；`contract_before.json`、`contract_after.json` |
| 第一轮统一检查 | `.venv/Scripts/python.exe tools/dev_check.py --work-item DEV-002-batch3` | success=true；2196 单测，0 failures / 0 errors；`development_check_first.json`、`unit_test_report_first.json`、`dev_check.log` |
| 分发重建 | package_seeds.py --output 新路径；package.py --seed-archive 种子包 --output 新源码包 | 正常通过受信摘要闸门；未使用 --allow-record-mismatch |
| 首个独立副本 | 新解压目录＋新 venv，安装 requirements-dev.txt，外部 cwd 导入与 CLI | 导入/路径/9 种子/CLI 通过；64 回归中 1 error：旧测试缺 .tmp 父目录。失败日志与源码包保留 |
| 修复后的独立副本 | 第二版源码包、新解压目录＋新 venv、清理 PYTHONPATH/PYTHONHOME 和用户站点干扰 | 64 测试全过；所有模块、bridge.ROOT、资源/数据根均属于解压副本；没有 config.json/client-config.json；CLI 只在副本写注册表。`fresh_identity_v2.json`、`fresh_regressions_v2.log` |
| 最终统一检查 | 修复测试夹具后重新运行同一 dev_check 命令 | success=true、unit_tests=passed；2196 项 0 failures / 0 errors；`development_check_final.json`、`unit_test_report_final.json`、`dev_check_final.log` |
| 独立审查 | 新上下文 reviewer 审查 0f6c085..3ffdd02 五项重点 | 无 Critical/Important/Minor 发现；并确认能力 AST 与种子原业务 AST 一致。随后仅增加测试夹具的 mkdir，以独立副本失败→成功验证 |

原生建模未执行，不能将上述文件/协议注册检查写成真实 stdio 握手或保存重载成功。

## 归档身份

这些是开发验收归档，生成于文档最终回填前，不是正式 Release 附件：

| 归档 | SHA256 | 用途 |
| --- | --- | --- |
| seed-library.zip | `666f9c806572717e93f8f6aeda64c471290806997bd0b73093884c14820a3233` | 9 种子，匹配当前受信记录；种子本体不变 |
| source.zip | `225be7dd9d486a034ad6092aaf2a15dc046d27286e42964f9d1fc57aaf901113` | 首轮独立安装；保留包含测试 .tmp 前提错误的原归档 |
| source-v2.zip | `6c78d3a550c819018194764cd4796905e363a0c83bf9f1f42c3f4226dd4d358d` | 24e4e37 源码，独立安装与 64 回归通过 |

源码收集检查覆盖新实现、包装与嵌套测试；归档排除本机配置、seed_registry.json、常量表、SDK、二进制和运行目录。独立环境没有切换 E 盘共享虚拟环境的源码归属，也没有修改 C 盘旧部署。

## 过程决策与限制

- 复用用户指定的当前 checkout，在新 codex 分支执行，保留原有改动；不新建会改变共享 editable 归属的工作树。代价：不能把目录隔离视为 Creo 会话隔离，因此本轮完全不访问 Toolkit。
- executing-plans 引用的 TDD/review/finish 配套技能未安装，使用原生命令记录 RED→GREEN、逐任务提交和最终独立审查；没有把缺少配套脚本当成测试已执行。代价：任务记账由人工维护，可通过提交和原始日志复核。
- 普通 editable 安装已成功；最初尝试 --no-build-isolation 因当前 venv 缺 setuptools 后端失败，改用仓库规定的标准隔离安装。没有更改依赖锁或升级运行依赖来绕过失败。
- 仅审查更新 style-baseline 的 pyproject 配置 SHA256：`15dec4018951449070a4e5ceb5db782aaa3e0fb8c583c816f1edcf10745bfa2b`；未重建基线、未新增 lint/format 容许项。

## T5 后置范围

根 AGENTS 的 BUG-001 限制与[恢复现场记录](BUG-001-recovery-2026-10-17.md)仍要求先核对根因和会话可操作状态。该记录最后附注仍有卡死、退出及会话身份过期事实，本轮没有当前可操作确认，因此未启动 MCP 传输、未连接 Toolkit、未创建/编辑真实模型、未结束 Creo、未清 unknown。

真实 MCP 清单/schema/capabilities 分页及自动选种建模＋一次编辑、原生几何、revision、saved_file_reloaded_and_verified 与源种子字节核验仍待本批实机。WorkBuddy、Creo 9/10、并发/恢复实机未执行。历史其他批次成功不算本批通过，也不要求 Creo 9/10 独立复测作为本次迁移的新增门槛。

T0—T4/T6 以本次最终结果收口，T5 保留待验；第三批不标为全范围验收完成，整个 DEV-002 不关闭。
