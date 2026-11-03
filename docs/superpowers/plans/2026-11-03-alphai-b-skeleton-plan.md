# alphai B：受管骨架与关联设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先证明标准骨架可创建并受管，再用骨架长宽真正驱动原生钣金壁。

**Architecture:** 复用唯一通道和受管模型登记；新增显式父子依赖与多模型修改日志。多文件保存不声称文件系统原子事务，只有所有验证完成才能发布成功登记；无法证明恢复时保护整个受影响集合。

**Tech Stack:** Python 3.12+ / unittest、C++17、Creo 12.4 / 匹配 SDK、现有持久化注册与检查点。

**Spec:** [设计依据](../specs/2026-11-03-alphai-capability-adoption-design.md)；[主计划](2026-11-03-alphai-capability-adoption-plan.md)。

## Global Constraints

继承设计/主计划全部约束；模型不得靠名字猜身份；不接管外部装配，不自动放宽收养的外部依赖拒绝。新原生调用先对 SDK 与实际元素树，实机统一串行。B02 必须等待 B01 与 A04 的契约和可用能力，不依赖对方产品专属映射。

## Review Focus

- 创建骨架失败后的父装配/子模型/文件/登记是否一致，不残留“成功一半”。
- 同名源、重复骨架、非骨架零件与错误父装配不得误认。
- 日志写入中断、部分保存、登记发布失败都要保留可恢复事实与 unknown。
- 长宽映射对调、关系冲突、引用缺失、依赖循环必须在修改前拒绝。
- 源件改变后的真实联动、保存重载与关系留存必须分别证明。

---

## B01 / FEAT-059：标准骨架及受管身份

**Files:**
- Create: `src/creo_mechdog/skeleton_models.py`、`src/creo_mechdog/model_transaction.py`、`native/skeleton_models.h`、`native/skeleton_models.cpp`。
- Modify: `generic_bridge.py` 的受管登记/提交适配、`native/generic.cpp`、公共 schema/能力/结果及 `server.py` 最小注册；实际构建/源码身份清单。
- Test: `tests/unit/test_skeleton_models.py`、`tests/unit/test_model_transaction.py`、`tools/test_adoption_skeleton.py`。
- Docs: `docs/development/ALPHAI-B01-SKELETON-CONTRACT.md`、`docs/work-items/FEAT-059.md` 及验收摘要。

**Interfaces:** 首版提案 `creo_create_skeleton(assembly_model_id: str, skeleton_name: str, expected_revision: int) -> dict` 返回既有作业回执；成功结果列父装配和新骨架 model_id/revision。骨架受管类型单独记录，不能自动开放普通零件全部操作。`inspect_skeleton_binding(assembly_model_id: str) -> dict` 输出 API 骨架身份和显式绑定。

本任务唯一拥有共享包 `model_transaction.py`；先冻结 `prepare_model_transaction(model_ids: list[str], expected_revisions: dict[str,int]) -> dict`、`finish_model_transaction(transaction_id: str, native_result: dict) -> dict`。日志至少有 transaction_id、模型集、旧 revision/检查点、预期新文件身份、实际保存/恢复结果；阶段为 prepared/native_saved/registry_committed/recovery_required。这些是项目日志阶段，不新增任务排队状态。恢复与登记失败语义需和集成人评审后才允许 B02/C04 依赖。

- [ ] **1. 核 SDK 与最小探针**：确认创建/获取/辨别骨架 API、许可、模板来源和子类型；准备隔离空受管装配夹具。会话负责人执行创建、抽取、保存重载、父装配回读。交付真实树/身份/失败码；探针未过只提交研究结论。
- [ ] **2. 冻结并测试事务契约**：新增 `test_parent_child_identity_commit_together`、`test_second_save_failure_protects_all_models`、`test_registry_publish_failure_has_recovery_record`、`test_old_checkpoint_not_replaced_before_success`、`test_unknown_never_reported_rolled_back`、`test_repeated_request_not_duplicate_child`。通过隔离目录/替身验证持久化协议，不向用户 Creo 注入故障。运行 `python -m unittest tests.unit.test_model_transaction tests.unit.test_skeleton_models -v`，新协议先失败。
- [ ] **3. 实现受管路径**：同一锁下核父装配 revision 与无既有骨架，再创建 API 认定的标准骨架，登记父子关系与共同日志，沿用既有作业终态时序。成功父装配 revision +1、新骨架 revision=1；修改失败按检查点恢复并逐模型核验，无法证实则均保留保护，既有 reconcile 未支持时明确拒绝恢复动作而不清日志。
- [ ] **4. 验证**：专项通过、默认离线驱动/build；串行实机标准创建/重载、重复/同名/错父类型拒绝、失败计划恢复。确认装配关联指向同一真实骨架、源件不变；成功保存重载 true，恢复后旧 revision/组件集不变，重复提交遵循既有保护。未知中断路径只拿离线证据，写清未实机注入。
- [ ] **5. 提交与交接**：`FEAT-059: manage native assembly skeletons`；把共享事务契约、文件保护集、受管骨架允许操作清单交给 B02、A01 和 D03。未通过原生/事务任一关，不开放公开写入口。

## B02 / FEAT-060：骨架长宽关联驱动

**Files:**
- Create: `src/creo_mechdog/skeleton_links.py`、`native/skeleton_links.h`、`native/skeleton_links.cpp`。
- Modify: B01 的绑定查询接入、公共 schema/能力/结果与 `generic_bridge.py` 的依赖校验；公共分发最小接入，不能直接放开 `RelationsOp` 任意语法。
- Test: `tests/unit/test_skeleton_links.py`、`tools/test_adoption_skeleton_links.py`。
- Docs: `docs/development/ALPHAI-B02-LINK-CONTRACT.md`、`docs/work-items/FEAT-060.md` 及验收摘要。

**Interfaces:** 消费 B01 受管父装配/骨架绑定与共享事务；A04 平面壁真实尺寸身份；A02 可选旧值守卫。拟接口 `creo_link_skeleton_dimensions(assembly_model_id, skeleton_model_id, target_model_id, dimension_mapping, expected_revisions) -> dict`，dimension_mapping 首版必须显式 length/width 的源和目标真实引用；所有 ID 必须属于该受管依赖集合。结果列关系的规范化表达、身份/方向/单位、前后读数、各模型提交/恢复结果。

- [ ] **1. 检查前置并冻结原生关系**：B01/A04 尚未通过时只做离线调查。对照实际 SDK/抽取的组件 Session ID 与持久化关系行为，验证重载后不会把临时 ID 误指另一组件；冻结引用重新解析方式。禁止拼对方固定 `d3/d2` 或公司模型名。
- [ ] **2. 写失败回归并运行**：`test_dimension_mapping_is_explicit`、`test_ambiguous_component_refused`、`test_conflicting_relation_preserved_and_refused`、`test_cross_model_cycle_refused`、`test_unknown_units_refused`、`test_partial_save_uses_shared_recovery`；运行 `python -m unittest tests.unit.test_skeleton_links tests.unit.test_model_transaction -v`。关系新增前必须读取保留所有无关旧关系；未知外部依赖拒绝。
- [ ] **3. 实现受控关联与更新**：仅允许本批骨架和原生平面壁矩形长宽；保存前回读关联。对关联模型后续尺寸修改，先在同一事务收集完整依赖集，检查所涉及全部 revision，再改变源尺寸、再生并验证目标；普通 `creo_regenerate` 不得暗中写其他未声明对象。循环/缺依赖不能自动跳过。
- [ ] **4. 证明真实随动**：先绑定 100×60×1 壁，再把骨架改为 120×80，目标体积必须 6000→9600 mm³，长宽/包络正确；重载后再改为 110×70，目标体积 7700。绑定、两次变化和故意失败恢复都分别记录 revision/关系/文件与保存重载；未知引用/旧 revision 拒绝后所有对象不变。临时变尺寸验证只在隔离夹具中执行，不能擅改用户设计再“还原”。
- [ ] **5. 提交** `FEAT-060: drive planar walls from managed skeletons`；写清这一显式关联不等于所有旧 source_snapshot 变为实时联动，也不关闭 FEAT-012/031 的嵌套装配未测范围。

以上命令执行使用 `.\.venv\Scripts\python.exe`。live 驱动默认离线，需用户安排的 `--live --confirm-session-usable` 窗口。
