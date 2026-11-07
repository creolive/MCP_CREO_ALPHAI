# FEAT-057：A01离线数值守卫 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复A01纯Python回执归一化中NaN/Inf可被作为有效质量或重心返回的问题，形成独立可审查提交。

**Architecture:** 仅强化现有normalize_mass_properties入口的数值有限性和自洽计算检查；正常字段与返回形态保持。复用现有A01工作树和分支，与正在进行的曲面主线隔离。

**Tech Stack:** Python3.12+、math、unittest、Ruff；本任务无原生代码或Toolkit执行。

**Spec:** 本文“验收契约”是该子任务的完整约束；来源为DEV-067后续计划R03的非有限值子项及用户2026-11-04明确指派子Agent处理。其余A01材料重心/单位/异步回执范围继续开放。

## Global Constraints

- 工作树仅E:\Projects\codex-A01，分支codex/FEAT-057-mass-properties，基线f4be20e9cc1921ae031d453b61cf1b27c4317f4a。
- 只允许修改src/creo_mechdog/mass_properties.py、tests/unit/test_mass_properties.py、本计划、docs/work-items/FEAT-057.md和docs/development/ALPHAI-A01-ACCEPTANCE.md。工作卡/验收摘要仅追加本子项事实并纠正卡头状态，不改写历史原始证据。
- 不修改native、server.py、schema.py、generic_bridge.py、其他测试、主目录台账/开发入口、版本/发布文件或曲面计划；不切换其他工作树分支。
- 不连接或启动Creo，不调用MCP建模/状态探针，不编译执行器，不运行任何--live驱动；不合main、不推送、不发布。
- 保留字段名称、单位、density_source优先级、只读作业接入及现有公开签名；不以本子项完成宣称整个A01完成。
- 现有正常有限数、缺省/None及形状错误重心的行为保持；不扩大为一般正负数物理域校验或单位/材料逻辑重构。
- 测试使用本工作树包；可建立本地忽略的.venv/build临时环境与日志，不能改其他工作树环境或复制native/constants.inc。无有效环境时先解决导入归属，不能拿别的checkout测试结果作证据。

## Review Focus

- NaN在浮点比较中绕过一致性拒绝，必须先拒绝非有限输入。
- density_source=none也不能把显式非有限数吞成缺省None。
- 重心三维坐标中的非有限值不能发布；负坐标仍合法。
- 输入皆有限、体积乘密度发生溢出时不能因inf比较而误放行。
- 错误应是可定位字段的ValueError；合法未知值及旧回执结构继续兼容。

## 验收契约

1. volume_mm3、mass_g、density_g_cm3中已提供的数字如果为NaN、+Inf、-Inf，抛ValueError，消息包含实际字段名；对request/model_material/none都成立。bool继续按现有规则不作为数字接受。
2. 长度为3的重心list/tuple中，任一已提供数字为NaN或±Inf，抛ValueError并明确center_of_mass_mm及出错位置；合法负坐标、零坐标、有限整数坐标照常返回浮点列表。
3. 重心缺省/None/长度错误/非数字项的现有None行为保留，不增加静默修复或伪造坐标。
4. 数字转float不能表示、或质量自洽计算产生非有限中间值时，应明确ValueError，不泄漏OverflowError或返回有效读数。对正常数值维持既有一致性容差max(1e-9,abs(expected)*1e-9)。
5. 正常6000mm³、7.85g/cm³、47.1g和[5,10,15]读数、model_material读数、无密度时质量None、原始query_codes和hint等保持。
6. 本轮禁止修改真实材料重心的原生计算、同步/异步接口、工具数、主惯量、complete或单位契约；这些继续写入未测/未完成范围。

### Task 1: 修复有限性与自洽计算守卫

**Files:** Modify src/creo_mechdog/mass_properties.py、tests/unit/test_mass_properties.py；Append docs/work-items/FEAT-057.md、docs/development/ALPHAI-A01-ACCEPTANCE.md；更新本计划步骤。

**Interfaces:** 消费现有normalize_mass_properties(raw: dict[str,Any] | None) -> dict[str,Any]，公开签名/返回键不变；错误仍以ValueError提供字段上下文。不新增MCP、原生或全局测试接入。

- [x] **Step 1:** 在现有测试文件补有判据回归：三标量NaN/±Inf（含none来源）、三维重心各位置的非有限值、巨大整数float转换溢出、自洽乘法溢出，以及有限负重心/None/旧形状错误兼容。先运行python -m unittest tests.unit.test_mass_properties -v，保存修复前真实失败片段；不要写源码字符串断言或只测私有helper。
- [x] **Step 2:** 只修改独立模块，使用math.isfinite与有限性/溢出的字段级错误处理，在质量比较前完成数值验证。保持未知/无密度语义；不改变正常单位或新增可观察字段。
- [x] **Step 3:** 运行专项回归直至通过；对两个修改的Python文件执行Ruff check/format check。随后运行一次tools/dev_check.py --work-item FEAT-057-numeric-guards取得本工作树全量离线证据。工具/安装错误先修本地环境，不重建风格基线或改无关产品文件。
- [x] **Step 4:** 自查修改范围与包resource_root；在工作卡/验收摘要追加本次命令、实际通过数、源码身份、无Toolkit/无原生改动、既有材料重心/单位等仍未验事实。卡头仅改为“开发中（离线数值守卫子项完成；其余A01范围开放）”。
- [x] **Step 5:** 只暂存本任务允许文件并提交到现有A01开发分支，标题带FEAT-057；不混入他人文件。交接给控制者进行独立任务审查和最终范围审查；有意见则继续同范围修复并复审。

## 交接要求

记录基线/提交范围、dirty、实际包导入路径、红绿测试、专项/全量/风格结果、变更文件和未完成范围；报告写入本计划的SDD工作目录。只交付该独立子项，不自行派生其他Agent、不领取D02/B01或曲面任务。

## 2026-11-04 执行记录（限定子项）

- Task 1 RED：20 tests，48 failures / 12 errors；GREEN：20/20 通过。两目标 Python 文件的 Ruff check / format --check 均通过。
- 一次全量 dev_check 已执行但失败，unit_tests=not_run：四个与 BASE 无 diff 的存量测试文件格式问题阻断。未改无关文件或基线；另跑全量离线 test_unit 的结果见下方最终记录，不能替代 dev_check 成功。
- 本地解释器、包模块、SOURCE_PATHS.resource_root 均在 E:\Projects\codex-A01。自查 product/test diff 和 git diff --check 通过；无原生修改/构建、Toolkit/Creo/MCP/live 调用。
- 按用户范围保留本计划及本机 SDD 报告，独立审查交由控制者，不派生 Agent 或执行合并/推送/发布。其余 A01 范围开放。

- 最终独立全量离线 `tools/test_unit.py`：2288/2288 通过，0 failures / 0 errors，退出码 0；dev_check 失败状态不变。交付状态 DONE_WITH_CONCERNS，仅暂存五个许可文件提交 FEAT-057。
