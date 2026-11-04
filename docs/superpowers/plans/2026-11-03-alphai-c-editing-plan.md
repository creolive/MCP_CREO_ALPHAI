# alphai C：装配、草图和模型派生 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付组件状态切换、约束复用、草图设计意图和受控名称/副本派生四个独立包。

**Architecture:** 全部写入沿用 execute_plan/受管 submit 与检查点；C02 扩展既有 planner，C03 不控制用户活动草图 UI，C04 首版只处理独立零件。新模型身份事务按实际需求复用 B01 契约，不能修改源件引用绕过限制。

**Tech Stack:** Python 3.12+ / unittest、C++17、Creo 12.4 / 匹配 SDK。

**Spec:** [设计依据](../specs/2026-11-03-alphai-capability-adoption-design.md)；[主计划](2026-11-03-alphai-capability-adoption-plan.md)。

## Global Constraints

继承设计/主计划全部约束；组件以 occurrence 定位，真实并发和未知结果按现有契约。公共文件在隔离 checkout 修改后由集成人串行整合。实机先满足 BUG-001 条件；只用当前 E 盘 dev 服务。保留 FEAT-036 零件生命周期边界和 FEAT-010 coordinates 互斥限制。

## Review Focus

- C01：重复模型的不同 occurrence、已抑制组件和恢复失败不能误指或留下半切换。
- C02：snapshot/源 revision 过期、参考面歧义、方向丢失不能退成 fixed 成功。
- C03：投影边失效、名称碰撞、对称约束引用数量和求解漂移不能静默修复。
- C04：名称冲突、同名源来源、后续登记/保存失败不能破坏 model_id 或原始文件。
- 断言实际随动和身份保持，不能只断言某接口返回 succeeded。

---

## C01 / FEAT-061：组件抑制/恢复

**Files:** Create `src/creo_mechdog/component_state.py`、`native/component_state.h`、`native/component_state.cpp`；Modify 公共 schema/分发、`native/placement.cpp` 的组件查询接入、结果/能力/`server.py`；Test `tests/unit/test_component_state.py`、`tools/test_adoption_component_state.py`；Docs FEAT-061 卡及 `docs/development/ALPHAI-C01-ACCEPTANCE.md`。

**Interfaces:** 新 op `component_state{action:'suppress'|'resume',components:[label|feature_id]}`；原子成对切换由同一 execute_plan 的两个 op 表达。拟包装 `creo_set_component_state(model_id, expected_revision, action, components) -> dict`。只支持受管单层装配；组件抑制后保留 label、source binding 和原 occurrence，恢复不新建实例。list_components 状态和 `component_changes` 有界回执如实回报。

- [ ] **1. 写回归** `test_occurrence_not_model_name`、`test_suppressed_label_still_resolvable`、`test_resume_keeps_same_feature_id`、`test_pair_failure_rolls_back_both`、`test_nested_and_unknown_refused`；运行 `python -m unittest tests.unit.test_component_state -v`，确认新 op 契约先失败。
- [ ] **2. 实现**：先核整组目标的类型/状态/依赖，使用原生组件状态 API，逐项读回；第二 op 失败走现有整计划检查点。保留源件/位姿/约束/appearance，不能以 remove+assemble 模拟恢复；不能按模型名选择首个实例。
- [ ] **3. 验证**：专项、默认离线驱动/build；实机含同一零件两个 occurrence，抑制其一、恢复、A/B 切换、第二 op 故意失败、旧 revision/嵌套拒绝。feature_id/标签/约束保持、revision 与源件 hash 正确、保存重载 true、回滚后后续合法操作成功。
- [ ] **4. 提交** `FEAT-061: manage assembly component state`；FEAT-036 卡仅交叉关联，不把零件范围改为装配已全支持。

## C02 / FEAT-049：约束克隆增量

**Files:** Modify `src/creo_mechdog/assembly_replay.py`、`references.py`、`native/placement.cpp` 和实际需要的约束方向/身份投影；首版复用 `creo_plan_assembly_rebuild`，不另建重复 planner；Test 扩展 `tests/unit/test_t09_assembly_replay.py`、新增 `tests/unit/test_constraint_clone.py`、`tools/test_adoption_constraint_clone.py`；Docs FEAT-049 卡及 `docs/development/ALPHAI-C02-CONSTRAINT-CONTRACT.md`。

**Interfaces:** 先核既有 FEAT-049 已实现的 snapshot schema 3/绑定/顺序插入约束逻辑。拟包内 `plan_constraint_clone(snapshot_id: str, source_occurrence: dict, targets: list[dict], reference_mapping: list[dict]) -> dict`，返回现有 execute_plan 操作和 source bindings，不提交。公开 planner 可选 `clone_request` 由 P00 冻结；只接受显式 occurrence/双方参考/方向，现有过期和源摘要保护继续生效。

- [ ] **1. 核重复与写回归**：列出已有 planner 能完成和缺失的字段，不重做。`test_clone_preserves_both_datum_sides`、`test_insert_target_surface_mapping_explicit`、`test_source_revision_rechecked_on_submit`、`test_unmapped_never_becomes_fixed`、`test_oversized_plan_refused`；运行 `python -m unittest tests.unit.test_constraint_clone tests.unit.test_t09_assembly_replay -v`。
- [ ] **2. 实现最小子集**：单层装配，一组 ALIGN+INSERT，从一个已冻结 occurrence 生成两个目标实例；完整保留双侧参考、方向、偏移和重复实例身份。现有其他六类支持范围不因本子集而缩减，也不宣称均完成本次验证；不能靠固定坐标代替约束。
- [ ] **3. 验证**：默认离线驱动/build；实机在隔离受管装配插入并克隆到两个明确圆柱目标，读取约束/方向/欠约束状态。改变宿主驱动尺寸后实例必须随目标移动，重载后再次变化仍随动；缺映射/方向不明/过期 snapshot 入口拒绝，已受理失败核整计划回滚。比对测试不扩成 FEAT-050 通用比较工具。
- [ ] **4. 提交** `FEAT-049: clone mapped assembly constraints`；原卡其他约束类型/嵌套范围继续按证据开放。

## C03 / FEAT-010：草图投影/对称/边距

**Files:** Create `src/creo_mechdog/sketch_references.py`、`native/sketch_references.h`、`native/sketch_references.cpp`；Modify schema 的 SketchConstraint/SketchOp/编辑模型、`native/sketch_edit.cpp` 与 `native/generic.cpp` 最小接入；Test `tests/unit/test_sketch_design_intent.py`、`tools/test_adoption_sketch_design_intent.py`；Docs FEAT-010 卡与 `docs/development/ALPHAI-C03-SKETCH-CONTRACT.md`。

**Interfaces:** 拟 `SketchConstraint.type='symmetry'`，只对该类型允许 3 个引用（两实体+中心线），旧类型仍按旧数量规则；`projections=[{name,edge,construction:true}]` 为命名模型边投影，引用必须唯一且与输入实体无重名。给已保存矩形增约束的 op/包装暂定 `set_sketch_constraints` / `creo_set_sketch_constraints(model_id,expected_revision,sketch,projections,constraints,dimensions)`；先冻结与现有 update_sketch_geometry 的兼容，不能创建两个竞争更新入口。coordinates 仍不能混自定义约束。

- [ ] **1. 写回归** `test_only_symmetry_accepts_three_refs`、`test_projection_names_unique`、`test_four_edges_must_map_uniquely`、`test_coordinate_mode_stays_exclusive`、`test_lost_projected_edge_not_guessed`；复用现有偏差字段，运行 `python -m unittest tests.unit.test_sketch_design_intent tests.unit.test_sketch_geometry_deviation -v`。
- [ ] **2. 实现**：首版矩形、两条明确中心线或四条明确直边；不依赖界面正在编辑状态。对旧元素树和投影所有权建快照，保留未经请求的约束；过约束明确拒绝，求解后核同身份几何偏差，不静默切 autodim/放宽公差。
- [ ] **3. 验证**：默认离线驱动/build；实机矩形关于原点两轴对称，独立改变长宽后中心不漂；100×60 外框四边内缩5，内框90×50，改变外框后内框边距仍5。读回约束类型、真实投影关联、feature/section/entity 对应，保存重载后继续编辑；删边/冲突约束/失败计划回滚，源几何/revision 保持。
- [ ] **4. 提交** `FEAT-010: preserve sketch symmetry and projected margins`；仅回填本子项，不关闭原案求解漂移、spline 和其他任意约束组合的未测范围。

## C04 / FEAT-062：模型 rename/derive

**Files:** Create `src/creo_mechdog/model_naming.py`、`native/model_naming.h`、`native/model_naming.cpp`；Modify 既有受管提交/文件来源/检查点最小接入、schema/分发/能力；Test `tests/unit/test_model_naming.py`、`tools/test_adoption_model_naming.py`；Docs FEAT-062 卡与 `docs/development/ALPHAI-C04-IDENTITY-CONTRACT.md`。

**Interfaces:** 拟 `creo_rename_model(model_id,target_name,expected_revision)` 保留 model_id、revision+1；`creo_derive_model(model_id,target_name,expected_revision,operations=[])` 创建新 model_id/revision=1，源件不变。只允许独立无依赖受管 part/sheetmetal，先复用现有独立新件/检查点流程；如需多对象登记，消费 B01 已冻结 `model_transaction`，未交付则相应路径只做契约研究，不另造事务体系。新名称不覆盖任何 session/disk/registry 冲突。

- [ ] **1. 冻结身份与恢复契约并写回归**：`test_rename_keeps_model_id`、`test_derive_gets_new_identity_and_source_unchanged`、`test_case_insensitive_session_disk_collision`、`test_dependency_refused`、`test_save_then_registry_failure_retains_recovery`、`test_derive_failed_edit_does_not_publish_model`；运行 `python -m unittest tests.unit.test_model_naming -v`。
- [ ] **2. 实现**：重命名后同步受管名称、来源、检查点和旧证据引用，不删除历史文件冒充完整迁移；derive 从验证副本编辑，拒绝超出首版的装配和外部引用。原名恢复也必须读回，无法证实保持保护，不能仅调用一次 Rename 就报 rollback=true。
- [ ] **3. 验证**：默认离线驱动/build；实机独立零件 rename 后继续编辑/重载，derive 改尺寸后新体积正确、原文件 hash/原 revision 不变；同名、装配引用、非法名称拒绝，派生中途失败无成功登记，原模型仍可继续使用。操作返回完整 old/new identity 和保存文件，不把目标名称当 model_id。
- [ ] **4. 提交** `FEAT-062: rename and derive independent managed models`；气弹簧总成联合改名/运动限位仍记未实现。

上述 `python` 使用项目 `.venv\Scripts\python.exe`；live 驱动默认离线，只有指定会话负责人在获安排的窗口使用 `--live --confirm-session-usable`。
