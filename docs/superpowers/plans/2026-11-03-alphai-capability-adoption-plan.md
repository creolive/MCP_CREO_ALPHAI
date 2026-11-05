# alphai 能力吸收与 Agent 派工 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 本次用户选择自己指派其他 Agent；本计划编写者不启动执行。单个被指派 Agent 默认使用 executing-plans；是否再委派由用户的任务指令决定。

**Goal:** 把比较清单中的 13 项拆成可独立指派、验证和集成的任务，优先交付真实质量、尺寸保护和标准螺纹孔。

**Architecture:** 逐项适配到 MechDog 现有 Python MCP、C++17 执行器和单一 Toolkit 通道。使用 4 个子计划覆盖不同业务域；公共接入、实机窗口及发布由集成人统一负责。骨架关联先有原生探针和多模型事务契约，再进入写入开发。

**Tech Stack:** Windows x64、Python 3.12+、unittest、C++17、Creo 12.4.0.0 / 匹配 Pro/TOOLKIT SDK。

**Spec:** [范围与设计依据](../specs/2026-11-03-alphai-capability-adoption-design.md)。协调固定 ID：[DEV-067](../../work-items/DEV-067.md)。

## Global Constraints

设计文档“全局约束”全部适用，执行前完整阅读。硬边界：毫米/度；单通道忙即拒绝、不排队/重试；工作区 `E:\Projects\MCP_CREO_MechDog`；开发服务 `MCP_CREO_MechDog_dev`；Python 3.12+ / C++17；公共回执 32 KiB；实机先满足 BUG-001 条件。不得改写历史验证原件、提交生成常量/配置/二进制；不得跳过检查点、revision 或 unknown 保护。

**2026-11-04 当前快照：A04已随0.12.0独立交付；P00首轮契约已冻结；A01/A02/A03与B01已有分支成果。** 下一步以[0.12.0后续集成计划](2026-11-04-alphai-post0120-integration-plan.md)和[核验记录](../../development/DEV067-POST0120-AUDIT-2026-11-04.md)为入口。未标姓名者只表示负责人待补，不能据此重复从零开发；本轮核验不构成新实机授权。

## Review Focus

1. 人工改动或同名重复实例后旧映射仍可命中：A02/C01/C02/B02 必须拒绝歧义和陈旧绑定，不能按名称或序号误写。
2. 未知单位、缺材料、骨架和重复组件影响质量：A01 必须保留完整性/原始码，不能返回伪造的 kg 值。
3. 部分保存成功后另一个模型失败：B01/B02/C04 必须保持全体身份与保护一致，未知不能写成回滚成功。
4. 草图/壁重新定义改变下游引用或方向：A04/C03 验证身份、有符号几何和重载，首版依赖不满足要拒绝。
5. 清理 token 后文件、引用或占用改变：D03 必须复核并保留，幂等回放不能第二次删除。

---

## 一 派工总表

任务号是本计划内编号，固定 ID 才是主台账身份。建议批次是先后关系，不是日程承诺。

| 任务 | 固定 ID | 交付 | 建议批次 / 前置 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- |
| P00 | DEV-067 | 核基线、公共接口与文件冲突协调 | 所有代码任务之前 | unassigned（集成人） | 首轮冻结已完成；R00需对齐0.12.0基线 |
| A01 | FEAT-057 | 真实质量属性 | 首批；P00 | unassigned | 分支已有实现f4be20e；数值/材料重心/契约待收口 |
| A02 | FEAT-004 | 尺寸旧值/归属保护 | 首批；P00 | unassigned | 分支离线实现2804d5a；实机未验证 |
| A03 | FEAT-035 | 标准螺纹孔 | 首批；P00 | unassigned | 分支已实现9520903；21例报告，深度/表来源待收口 |
| A04 | FEAT-058 | 原生平面壁创建与改型 | 0.12.0已交付；下一批仅影响回归 | unassigned | 已发布0.12.0；本次远端/原始报告核验通过 |
| B01 | FEAT-059 | 受管标准骨架 | 第二批研究；P00；先事务契约 | unassigned | 77bbb4e离线日志子项；原生骨架未验 |
| B02 | FEAT-060 | 骨架驱动钣金长宽 | 第三批；B01+A04，复用 A02 | unassigned | 未启动 |
| C01 | FEAT-061 | 组件抑制/恢复与切换 | 第二批；P00；沿用 FEAT-036 检查但不改其零件范围 | unassigned | 未启动 |
| C02 | FEAT-049 | 装配约束克隆/回放 | 第二批；P00；核已有 planner | unassigned | 未启动 |
| C03 | FEAT-010 | 对称/投影/边距草图 | 第二批；P00；先核既有坐标保真改动 | unassigned | 未启动 |
| C04 | FEAT-062 | 独立模型 rename/derive | 第三批；P00；先身份事务契约 | unassigned | 未启动 |
| D01 | FEAT-001 | 统一会话上下文 | 第二批；P00；仅聚合可先离线 | unassigned | 未启动 |
| D02 | FEAT-063 | 产品规则到只读计划 | 第三批；P00；首版无 Toolkit；引用已交付操作 | unassigned | 未启动 |
| D03 | FEAT-064 | 模型族历史版本清理 | 最后；P00；先检查点/引用保护清单 | unassigned | 未启动 |
| P99 | DEV-067 | 集成、串行实机、逐批发布 | 每批相应任务离线完成 | unassigned（集成人） | A04批已交付；R99继续下一批 |

以上为原任务拆分。**当前先指派R00集成人与R01/A02实机收口；A03/A01分别并行离线整改；B01接续已有日志并准备原生探针。A04退出完整开发派工。** 不重复实现已有分支，实际集成顺序仍按A02→A03→A01，未过准入者可单独延后。

## 二 子计划与文件所有权

| 子计划 | 任务 | 主要独占实现文件（拟新增） |
| --- | --- | --- |
| [A 基础能力](2026-11-03-alphai-a-foundation-plan.md) | A01—A04 | `mass_properties.py`、`dimension_guards.py`、`hole_standards.py`、`native_planar_wall.py` 及同职责原生模块/测试 |
| [B 骨架关联](2026-11-03-alphai-b-skeleton-plan.md) | B01—B02 | `skeleton_models.py`、`skeleton_links.py`、原生骨架/关联模块及各自测试 |
| [C 装配和草图改型](2026-11-03-alphai-c-editing-plan.md) | C01—C04 | `component_state.py`、既有 `assembly_replay.py`、`sketch_references.py`、`model_naming.py` 及各自原生/测试 |
| [D 会话规则和文件工具](2026-11-03-alphai-d-workflow-plan.md) | D01—D03 | `session_context.py`、`product_rules.py`、`model_version_reclaim.py` 和各自测试/脱敏模板 |

以上 Python 文件均位于 `src/creo_mechdog/`。具体新文件见各子计划，不创建空模块占位。

公共文件：`server.py`、`src/creo_mechdog/schema.py`、`capabilities.py`、`operation_results.py`、`references.py`、`model_queries.py`、`generic_bridge.py`、`bridge.py`、`native/generic.cpp`、`native/worker.cpp`、构建/身份清单、README、主台账、版本与发布文件。

每个任务在自己的隔离 checkout 提供完整可测分支，公共文件只做该任务所需最小修改，并列出冲突 hunk；禁止在共享工作区同时写公共文件。集成人顺序整合并重跑受影响检查。若用户安排同一 checkout，则这些写入和分支切换必须串行，不能靠“互不覆盖”口头假设并行。

工作卡由任务执行者维护自己的段落；主台账、开发入口、版本、集成契约、最终能力数量由集成人维护。产品业务不堆进 `server.py`，不新建第二个 Toolkit 锁。

## 三 P00：开始前的共同契约

**Files:** 修改本主计划、各子计划和本批工作卡；新建 `docs/development/ALPHAI-ADOPTION-CONTRACT.md`。按真实依赖决定是否调整构建/身份清单，不做架构迁移。

**Interfaces:** 输出各任务共同使用的模型定位、revision/错误回执、32 KiB 分页、模块接入和实机驱动约定。子计划列出的公开函数是首版提案；P00 冻结首批，B/C 的高风险接口在各自探针后追加冻结。没有冻结的接口只允许研究，不允许依赖方先实现猜测版本。

- [ ] 读取本设计、主台账和当前 AGENTS；核当前 HEAD/dirty、既有任务认领、最高 ID 和 0.11.7 之后变更。当前工作区已有 BUG-111 等修改，逐项保留，不 reset/stash/覆盖其他 Agent 内容。
- [ ] 确认用户指定的集成人、各任务负责人、隔离 checkout、公共文件集成次序；所有未认领者保持 unassigned。
- [ ] 核现有查询/作业接入方式和注册工具注解；冻结 A01 查询走同一锁的原生读取路径，A02/A03/A04 写入走既有 submit/execute_plan；不能用 Python 模拟几何。
- [ ] 为各新模块列实际构建依赖与源码身份接入位置；核 `bridge.py`、`native/worker.cpp` 和包内源码身份实现，避免新增模块漏编/漏指纹。
- [ ] 为 A01—A03 冻结 schema 与兼容示例；核本计划与当前实现没有重复。A04/B01 的探针只在用户安排的串行实机窗口执行。
- [ ] 以 `DEV-067: freeze adoption interfaces` 提交规划/契约变更到开发分支；不把现有代码脏改混入，不合 main。

## 四 每个任务的交付格式

每个执行者只完成被用户指派的任务，按对应子计划复现/写回归→实现→专项验证→自查→提交的顺序。交接必须包含：

```text
任务号 / 固定 ID / 负责人：
基线与提交范围 / dirty / 受测源码指纹：
修改文件，公共文件冲突点：
新增/变化的 schema、工具、op、返回字段及兼容示例：
专项 unittest 命令与结果：
dev_check / build 命令与结果（未执行则写明）：
默认离线驱动及实机用例清单：
实机：未执行 / 通过 / 失败 / 未验证，附 job_id/model_id：
保存重载、revision、回滚与源件不变性证据：
能力边界、缺证、未测环境、后续依赖：
工作卡与文档位置；是否可进入集成：
```

不得仅用“单测通过”宣布原生功能完成；探针不可行是研究结论，不能登记为公开能力可用。执行者提交完成只代表分支交付，不能自行合 main 或发布。

## 五 P99：集成与发布

**Files:** 公共文件、相关工作卡、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、能力/引用/兼容文档；每批新建验收摘要和版本说明。最终发布按 `docs/development/RELEASING.md`。

**Interfaces:** 消费各任务已冻结契约和提交清单；输出逐 ID 实际交付、仍开放范围、当前环境证据、Release 与附件核验。一个包不通过只阻断依赖它的包。

- [ ] 按 A02→A03→A01（或公共接口实际冲突决定的顺序）集成首批；A04 后续单独加入。每次整合核源分支差异，不整枝带回旧版本/历史证据。
- [ ] 运行 `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-067`，预期 `success=true`；修改原生后运行 `bridge.py build`，预期 exit 0，记录源码/二进制身份。不重建风格基线吸收错误。
- [ ] 会话负责人落实 BUG-001 条件后串行运行本批 `tools/test_adoption_*.py --live --confirm-session-usable`。没有当次条件就继续离线工作并保留实机未测；禁止多个 Agent 各开 stdio 服务争用同一会话。
- [ ] 验证新入口真实 MCP schema：省略/null/非法字段、busy 拒绝、accepted job 只轮询、结果分页及原始错误；真实并发没有做则不写通过。
- [ ] 核各任务指定的几何、源文件不变性、保存重载 true、revision 与适用失败回滚；D01/D02 只读/离线与 D03 文件回收不套用“保存重载=true”假指标。
- [ ] 如用户安排 WorkBuddy，只给公开 MCP 场景和输入/预期/报告要求，不给源码/本地测试步骤；内部文件占用/回收注入等只记开发者证据。
- [ ] 核新增工具实数、操作清单、compact/full、源码身份/安装/打包。更新每张交付卡的状态/范围，不关闭仍缺证的原 ID。
- [ ] 交付前选择尚未发布版本；新增能力默认 MINOR，不预占 `0.12.0`。获用户合入/发布指派后，在同一次交付完成 main、标签、正式 Release、由对应提交生成的源码/种子附件和完整 SHA256，远端核验后回填记录。

## 六 可复制给执行 Agent 的任务提示词

把下列 `{任务号}` 换成 A01 等；集成人用 P00/P99。一个提示词只指派明确任务，不默认领取整组。

> 在 E:\Projects\MCP_CREO_MechDog 完成 DEV-067 派工计划中的 **{任务号}**。先读 AGENTS.md、docs/DEVELOPMENT.md、docs/BACKLOG.md、docs/superpowers/specs/2026-11-03-alphai-capability-adoption-design.md、主计划 docs/superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md，再读任务所在子计划和固定 ID 工作卡。核当前实现与认领后，仅执行本任务；与集成人确认接口和 checkout，保留所有他人改动。以 E:\Projects\codex-creo-mcp-alphai 为只读参考，把业务接入我们既有通道/身份/回滚，不复制固定公司 ID 或增加第二通道。先完成离线实现、针对性回归、构建和默认离线驱动，按主计划格式交接提交与未测范围。Creo 实机由用户指定负责人统一串行安排，未满足 BUG-001 条件不得连接、重启、清 unknown 或注入故障。不自行合 main、改发布版本或发布；不额外派生 Agent，除非我明确安排。

## 七 本次规划记录

- [x] 静态核对 13 项与已有能力/台账，拆为 4 个子计划；明确首批 A01/A02/A03，A04 先探针。
- [x] 新登记 DEV-067、FEAT-057—064；复用 FEAT-001/004/010/035/049，不重复创建功能条目；补建缺失 FEAT-001/004 工作卡。
- [x] 规划自查：22 份本轮文档的本地链接/计划头/空白检查通过；台账178行/178唯一ID，新增9行，既有ID的优先级/状态/目标版本均保持。按当前行状态纠正BUG-101统计滞后后，分类为开发中3、待复现24、待核实10、验收中30、待规划52、观察中3、未收口56，合计178；历史统计原文保留。
- [x] `git diff --check` 无空白错误。本次未运行产品单测/dev_check/原生构建/实机；文档校验不作为产品测试证据。文件尚未提交，未合入或发布。
- [ ] 补齐执行者姓名与下一批会话窗口；已有分支实现按2026-11-04快照接续，不能把旧`unassigned`当作未实施。
- [x] P00 契约冻结：`docs/development/ALPHAI-ADOPTION-CONTRACT.md`（提交 `8a9a77a`），冻结 A01/A02/A03 接口、文件归属、集成次序 A02→A03→A01 与工作树环境；A01—A04 隔离工作树已建（`codex/FEAT-057-mass-properties`、`codex/FEAT-004-dimension-guards`、`codex/FEAT-035-standard-holes`、`codex/FEAT-058-planar-wall-probe`，均自 `8a9a77a`）。
- [ ] **2026-11-03 P00时点记录（已被后续进度取代）**：当时实现/实机/集成/发布未开始，授权不连Creo，A04仅离线。2026-11-04 A04已发布0.12.0，其余当前分支事实见顶部快照及新计划。

本文件与子计划是当前规划入口；台账才是状态唯一入口。新任务不覆盖 BUG-108/110 等既有稳定性工作及历史未测事实。
