# DEV-067：0.12.0 后续收口与集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用户仍自行指派其他Agent。本计划编写者只核验和更新计划，不启动执行者或实机。

**Goal:** 以已发布0.12.0为基线，收口并集成已有A02→A03→A01分支，推进B01探针；A04从开发派工退出。

**Architecture:** 既有单通道、受管身份、revision、检查点与unknown保护保持；集成分支必须包含main@90dbd6c。公共文件逐项整合，先解决接口差异再做统一实机；不能把多个旧0.11.7分支直接覆盖到0.12.0源码。

**Tech Stack:** Windows x64 / Python3.12+ / C++17 / Creo12.4.0.0匹配SDK；unittest、现有MCP stdio与GitHub发布流程。

**Spec:** [原范围设计](../specs/2026-11-03-alphai-capability-adoption-design.md)、[本轮核验记录](../../development/DEV067-POST0120-AUDIT-2026-11-04.md)、[原P00契约](../../development/ALPHAI-ADOPTION-CONTRACT.md)。当前事实覆盖旧计划中“A04未启动/仅离线”表述，不改写旧时点历史记录。

## Global Constraints

根AGENTS和原设计全局约束继续适用：毫米/度、32KiB、唯一Toolkit锁、忙即拒绝、不自动重试、已接受只轮询；MCP联调只使用指向E盘主目录的MCP_CREO_MechDog_dev。先保留现有他人修改，不自动stash/reset、结束Creo或清unknown。实机须先满足BUG-001条件并统一串行；本次检查不构成新实机授权。已发布v0.12.0及同名附件不改写；任何main交付仍须同批新版本Release。

## Review Focus

- 发布源码97工具与本对话工具目录95不一致，运行前必须证明实际服务源码/工具版本。
- A03肩深度/tip深度不能互相替代，固定表摘要不能冒充安装孔表摘要。
- A01 NaN/Inf、异材料真实重心、未知单位/材料与部分装配不能返回虚假完整结果。
- 旧分支合并不得带回已撤销的“最多4副本/拆批”文案、旧工具数/版本或覆盖A04。
- 集成后的实测源码与新附件必须同源；旧分支成功日志不能直接改名为新集成版本验收。

---

## 一 当前派工与依赖

| 顺序 | 任务/固定ID | 交付 | 当前状态 |
| --- | --- | --- | --- |
| R00 | DEV-067/P00、P99 | 环境/基线与主计划同步 | 本轮已核验；实际服务切换与新集成分支尚未做 |
| R01 | FEAT-004/A02 | 在0.12.0基线上完成守卫实机验收 | 已有2804d5a，不重做离线实现 |
| R02 | FEAT-035/A03 | 深度/表来源契约整改、复审与集成 | 已有9520903及21例报告；契约关口未过 |
| R03 | FEAT-057/A01 | 数值/材料重心/回执契约收口、验证 | 已有f4be20e及19例报告；不将原材料质量目标整体关闭 |
| R04 | FEAT-059/B01 | 日志子项审查、原生骨架探针 | 已有77bbb4e日志；骨架入口未实现 |
| R05 | FEAT-001/D01增量 | 记录-38连接阶段现象与诊断契约 | 根因未定；本次不做故障注入或自动重试 |
| R99 | DEV-067/P99 | 集成回归、逐批发布/交接 | 依赖拟交付包通过；具体版本发版前确定 |

A04/FEAT-058：0.12.0已交付，不再派完整开发；只对后续公共改动运行影响回归。B02仍等B01真实骨架绑定，C/D其他包维持原计划。R02/R03可并行离线修复，实机统一排他；R04离线审查可并行。

## 二 R00：基线和环境对齐（集成人先做）

**Files:** 原派工主计划、DEV-067卡、BACKLOG、ALPHAI-ADOPTION-CONTRACT；新的集成交接记录。现有曲面计划/G5/feedback不属于本任务。

**Interfaces:** 输出“集成checkout/分支/HEAD/dirty/包resource_root/连接器工具目录”的单一清单；明确每个任务源提交范围。当前可核对：发布工作树E:\Projects\codex-A04的main@90dbd6c；规划工作树E:\Projects\MCP_CREO_MechDog的376cdbd，不可混认。

- [ ] 核当前工作树/任务认领，协调保存E盘主目录里的其他任务现场；保留其未提交内容，不为升级覆盖或自动归档它们。
- [ ] 由集成人选择隔离集成checkout，基于最新main建立`codex/DEV-067-post0120-integration`，保留已发布main与现有任务工作树；不要在其他Agent工作树切分支或强推其分支。
- [ ] 对接E盘唯一开发入口，明确如何在保留现场后加载集成源码；在真正获准实机前，通过公开MCP版本/工具枚举与源码身份确认受测对象，不能凭工作树version.py推断连接器已升级。
- [ ] 更新P00契约：A01用户已决定的density_g_cm3来源保留；同步/异步、单位、op、完整性/惯量范围另列差异并冻结。A03深度/孔表来源重新冻结。原冻结文档保留日期，在新段说明当前有效契约。
- [ ] 交付未发布集成分支与环境清单给R01—R04；本步骤不合main/发布。

## 三 R01：A02集成与最小实机（FEAT-004）

**Files:** 消费`7b3d90e`、`2804d5a`；重点`dimension_guards.py`、schema DimensionValue、native/generic.cpp尺寸读写、server源码清单；复用`tests/unit/test_dimension_guards.py`和`tools/test_adoption_dimension_guards.py`。

**Interfaces:** 仍是旧id/value加三个可选guard；容差与两遍读写沿用已冻结契约，不增加新工具。

- [ ] 在集成分支选择性接入任务提交，解决公共文件冲突；对照main保留A04新工具、97工具断言及BUG-111实际选集文案，不带回旧版本元数据。
- [ ] 用本checkout虚拟环境运行`python -m unittest tests.unit.test_dimension_guards -v`，确认包resource_root指向集成checkout；构建成功后交会话负责人。
- [ ] 串行实机验证自由尺寸成功、旧值/符号/归属不符、关系驱动拒绝、两项中第二项不符、计划前项已修改后后项失败、过期revision与后续合法编辑；分清入口无job和原生已受理回滚。
- [ ] 成功保存重载true、失败前后几何/revision/源字节正确；生成新源码指纹绑定报告，更新卡为本子项已验，不连带关闭其他尺寸分类余项。

## 四 R02：A03深度/孔表收口（FEAT-035）

**Files:** `hole_standards.py`、schema HoleOp、native/generic.cpp的standard_hole_elements/hole_thread_json、server工具文案、ALPHAI-A03-ACCEPTANCE、相关标准孔与depth_basis测试/驱动。

**Interfaces:** standard分支的depth语义必须明确且与回执一致；推荐保持P00的tip输入：native若必须写肩深度，则在原生按实际底孔/钻尖角换算，并以真实树回读核验，不允许输入depth后再额外钻深。若采用显式basis，需独立契约和兼容说明，不能暗改默认。

- [ ] 写失败回归：以表中Ø5底孔、118°钻尖、请求tip深度10为例，肩深应为`10-(2.5/tan59°)`，内部完整盲孔去料按圆柱+圆锥独立计算；schema的thread_depth必须严格受冻结tip边界约束。分别测等于/越过边界和深度不足以容纳钻尖。
- [ ] 明确table_id/table_sha256属于冻结表还是实际安装表；若暂不实现安装表解析，能力边界必须说明固定ISO行及本机读回范围，并对实际表不同/缺行给明确失败，不能用冻结值冒充安装表真值。
- [ ] 最小修复、专项单测、原生构建；在0.12.0集成分支运行标准孔矩阵与旧直孔/沉孔/沉头/tip回归，核元数据、实际钻尖位置、去料与保存重载。
- [ ] 新报告写完整HEAD/dirty/源码指纹/worker、用例实数（现文件21条，不沿用20）；无契约关口通过则不进入R99，但不阻断已验A02单独交付。

## 五 R03：A01数值与真实质量范围（FEAT-057）

**Files:** `mass_properties.py`、generic_bridge.get_mass_properties、native/generic.cpp::mass_properties_json、mass_properties.h、server/能力/卡头、现有test_mass_properties和驱动。

**Interfaces:** 用户已确认显式density_g_cm3的what-if来源可保留；真实材料质量、what-if与无密度结果要明确。对P00异步job、kg字段、惯量/complete的偏差先形成有效契约；默认建议继续返回可轮询job，不能因同步封装超时而丢掉已受理job_id。

- [ ] 补`NaN/Inf`的质量、体积、密度、三维重心回归，确认现实现反例失败；修复为不能输出非有限“有效读数”，未知需有原因/完整性，bool不能当数值。
- [ ] 修复/证明真实重心来源：材料路径用材料质量对应的重心与单位转换；what-if路径可使用均匀密度几何重心但须标来源。用两个6000mm³块、中心x=5/55、密度7.85/2.70的夹具，材料质量应为47.1g/16.2g、总63.3g，重心x应`(47.1*5+16.2*55)/63.3`，不能返回30。缺件/缺材料不能冒充完整装配总质量。
- [ ] 根据实际完成范围补齐惯量/complete等原目标或明确拆成后续子项；修正卡头“待规划”、描述“装配拒绝”和已有装配代码/报告的冲突。用户确认的新增参数不是其他全部契约变更已确认的证据。
- [ ] 在集成分支专项/构建后，串行补真实材料密度路径和单位/只读不变性；已有19例仅作旧分支事实，新集成报告重新取证。A01新增一个工具，若本批仅增加A01工具，97→98，按实际枚举同步断言。

## 六 R04/R05与R99

**R04 / B01 Files:** 现有model_transaction.py、test_model_transaction、骨架契约卡。**交付**：先审事务日志是否真正接入现有持锁/登记/恢复流程（当前仅离线helper）；不因9项桩测试认定真实多模型原子提交。用户安排窗口后做骨架创建/抽取/保存重载/父装配读回探针，过关再开放受管入口；B02继续等待该证据。

**R05 / FEAT-001 Files:** 会话工作卡、诊断契约与本轮记录。**交付**：保留-38 job阶段、错误、进程身份、发生时间、源码/worker；将“与版本无关”改为未定因表述并列所缺证据，不为复现自动重连/重启/故障注入。开发者证据和WorkBuddy公开可观察项分开。

**R99 / DEV-067 Files:** 公共接入、能力/引用/版本说明、工作卡、主台账、RELEASING和新发布记录。

- [ ] 按实际已验包集成，运行本checkout `tools/dev_check.py --work-item DEV-067-post0120` 与`bridge.py build`，生成新源码/worker身份，不引用旧2286数作为本轮全量结果。
- [ ] 统一串行实机：新包矩阵及A04平面壁影响回归（含6000→9600、负方向、XZ/YZ、方形、下游拒绝、旧首壁/折边）。0.12.0当前67/67是历史事实，不改标新版本。
- [ ] 做真实stdio MCP调用契约/忙拒/分页/作业回执验收；WorkBuddy若由用户安排，只使用公开MCP，不读取源码/运行本地脚本。未做真实并发不得写并发通过。
- [ ] 只把已验包列入本版。新增A01能力默认MINOR；具体未发布版本发版时核定，不能复用0.12.0。合main与Release、由对应提交生成的成对源码/种子附件、完整SHA256远端核验在同次交付完成。

## 七 可直接派工的下一句话

> 继续DEV-067的0.12.0后续集成计划，先执行R00，再接续R01（A02）。基线使用最新main@90dbd6c，保留其他工作树和未提交曲面现场；复用现有A02提交，按本计划交付独立分支、专项验证与待安排的串行实机清单。A03并行收口深度/孔表契约，A01并行修NaN/Inf与材料重心/回执契约。暂不重做A04、不合main或发布；实机仍由用户指定会话负责人统一安排。

## 本次已完成

- [x] 0.12.0远端发布/附件/源码身份/原始验收报告核验。
- [x] 盘点现有A01—A04/B01分支，复现A01非有限数值投影缺口。
- [x] 写本计划和核验记录，更新规划分支任务状态与台账入口。
- [ ] 用户指派R00—R99角色和会话窗口；所有产品修复/集成/新实机/新发布尚未由本次检查执行。
