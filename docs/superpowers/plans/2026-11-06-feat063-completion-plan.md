# FEAT-063 只读产品规划器接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 D02 已有设计，把已交付离线内核接成可独立验收的只读 MCP 规划器，并完成开发分支收尾。

**Architecture:** 沿用固定 box_frame JSON 和 build_product_plan。server 只做只读注册、从本版本 REGISTERED_OPERATIONS 减 UNAVAILABLE_OPERATIONS 构造快照和 invoke 映射；不查询 Creo。保留现有 execute_plan 的显式提交边界。

**Tech Stack:** 本工作树 Python 3.12+/.venv、MCP、unittest、现有 schema；无新增依赖。

**Spec:** ../specs/2026-11-03-alphai-capability-adoption-design.md 第 12 项及 2026-11-03-alphai-d-workflow-plan.md 的 D02。2026-11-04 离线阶段已完成；本次用户要求解决此分支并不得影响 DEV-069，授权接续原 D02 剩余软件接入。

## Global Constraints

- 仅在 codex/FEAT-063-offline-product-rules 的既有独立工作树工作；main@4517e365 已合入此分支，起点 b3a9efc。不得修改 E:/Projects/MCP_CREO_MechDog、它的虚拟环境、连接器配置、Toolkit 通道或其他分支。
- 不连接、启动或重启 Creo，不运行 live、不编译执行器、不复制配置/SDK/常量，不启动 server lifespan。单元中的离线 MCP fixture 可用。
- 长度毫米、角度度；白名单模板不接受路径/表达式；拒绝 bool/非有限数/越界和退化尺寸。新业务进入包内，server 只注册和映射。
- 返回完整 JSON ≤32768 UTF-8 字节；超限明确拒绝，不截断 operations。缺能力时 executable=false、plan=null。
- executable 只表示本版本静态能力与 schema 准入；native/saved_reload 始终 not_run。不能宣称模板已完成 Creo 建模验收。
- 不合入 main、不推送或发布；开发分支可以提交。版本保持主干版本，公开工具数量的开发断言同步到实际值；旧发布记录不改写。
- 不改语言基线或历史反馈原件。生成证据仅写本树 build；保留旧证据原件并新增本次日期段。

## Review Focus

- MCP schema 不得在内核收到前把 bool/字符串尺寸转换为合法数字。
- 能力快照必须来自当前服务的启用操作，不能让调用方自报或调用完整 capabilities 引入运行时查询。
- 只读接口不得触发 jobs/models/config 写入、通道锁、子进程、网络或 Toolkit；非法输入返回既有 MCP 错误。
- 产品模板和实现必须进入源码身份与源码分发；解压后的安装不得依赖原工作树。
- 验收 driver 不得覆盖同名报告；文档/台账应区分软件完成、未发布与实机未验。

### Task 1: 只读工具、分发和开发验收

**Files:** 修改 server.py、src/creo_mechdog/capabilities.py、必要时 product_rules.py 与 tools/test_adoption_product_rules.py；新增 tests/unit/test_product_rules_mcp.py 与 driver 行为测试，保留现有 test_product_rules.py；同步实际工具数的既有测试（test_reference_contract.py、test_t01_capability_contracts.py、test_update_check.py）；文档 docs/PRODUCT_RULES.md、docs/work-items/FEAT-063.md、docs/BACKLOG.md、docs/DEVELOPMENT.md、docs/REFERENCE_SYNTAX.md、README.md、docs/development/ALPHAI-D02-ACCEPTANCE.md。tools/package.py 现有递归白名单已包含资源，优先测试证明，不无故修改。

**Interfaces:** 新增 creo_plan_product_variant(template_id: str, parameters: dict[str, Any]) -> dict[str, Any]，READ annotations，经 invoke(build_product_plan, template_id, parameters, 静态启用操作快照)。保持 build_product_plan 的既有接口与结果；操作数不变，工具总数由 100→101。families 增加 product_rules 只读能力，说明模板、单位、参数、无连接/提交、解析预期、原生未验。_SOURCE_NAMES 加实现与固定 JSON 资源。

- [x] Step 1: 新增并运行回归取得 RED：通过 MCPServer.call_tool 验证工具枚举/READ、默认与第二尺寸体积 35712/83508、缺 extrude 时阻断、非法 bool/字符串/模板路径返回 isError、无写盘/锁/作业/连接、完整响应预算、实现/资源指纹与分发可用。通过已有离线测试模式，不启动服务生命周期。
- [x] Step 2: 最小实现注册/能力/身份；保持业务在包内。不添加通用表达式解释器、自动执行、额外模板、实机开关或参数猜测。
- [x] Step 3: driver 添加拒绝已有 report.json 的回归，使用独占创建以免覆盖；报告补充本次时间、版本、平台、提交/dirty 与受测源码指纹（纯 run_checks 不调用外部进程，CLI 可只读 git 记录身份）。保持默认离线、无 --live。
- [ ] Step 4: 运行本树 .venv 的专项 tests.unit.test_product_rules/tests.unit.test_product_rules_mcp 和 driver 测试、能力/身份/打包相关回归；Ruff check/format check 改动 Python。运行 driver 与拒绝 --live；执行一次 tools/dev_check.py --work-item FEAT-063-completion，长输出留本树 build/feat063_completion_20261106。不得用 SDK 或其他工作树配置补全离线测试。
- [x] Step 5: 更新文档/工作卡/台账为“只读规划器软件已完成，开发分支未发布，原生模板未验”，保留原日期证据；记录 HEAD/dirty、源码指纹、环境、命令和结果。用户明确要求不影响 DEV-069，不能为实机验收替换它的服务。
- [x] Step 6: 自查范围后提交 FEAT-063 开发分支，写实现报告到控制者指定的独立 scratch 路径；控制者随后做任务审查和全分支审查。不得自行派生 agent。

## 预检与决定

沿用已存在的 D02 设计与内核，不重新设计产品。11-04 八文件白名单只约束该离线阶段，本次按原始 D02 接口范围补齐公共接入；代价是未来集成仍需处理其他分支对公共文件的并发修改。本次不修改其他工作树。

纯规划器可无 SDK 独立验收；原始 D02 规定没有实机证据时只交付规划器。实际模板建模、保存重载、WorkBuddy 与发布不是本次完成声明。
