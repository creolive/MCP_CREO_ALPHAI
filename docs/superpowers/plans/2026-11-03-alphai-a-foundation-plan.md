# alphai A：质量、尺寸、螺纹孔与原生平面壁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 独立交付 A01—A04，首轮优先 A01/A02/A03；A04 先验证原生路线。

**Architecture:** Python 只负责参数、受管身份与回执；几何和材料属性来自既有 C++ Toolkit 通道。新原生文件按 P00 核实的现有构建方式接入，保持旧操作默认行为。

**Tech Stack:** Python 3.12+ / unittest、C++17、Windows x64、Creo 12.4 / 匹配 SDK。

**Spec:** [设计依据](../specs/2026-11-03-alphai-capability-adoption-design.md)；[派工主计划](2026-11-03-alphai-capability-adoption-plan.md)。

## Global Constraints

设计“全局约束”和主计划全部适用：毫米/度；32 KiB；单通道忙拒、不重试；保留 expected_revision/检查点/unknown；本机开发仅 E 盘 dev 服务；实机先满足 BUG-001 条件，由会话负责人串行执行。新字段是首版提案，P00 冻结后才实施公共接入。

## Review Focus

- A01：材料缺失、混合单位、重复 occurrence、骨架/无实体、汇总失败必须显式标不完整。
- A02：同 ID 不同归属、旧值漂移、关系查询失败和批中后项不符，不能先写前项再当作准入拒绝。
- A03：孔表路径逃逸、型号不存在、标准/自定义混用、旧 tip 深度退化都要拒绝或保持兼容。
- A04：矩形正方形锁定、有符号方向、feature 身份变化、下游引用和失败恢复分别取证。
- 原生正例必须有当前保存重载 true；不能用桩返回的几何值作为独立 oracle。

---

## A01 / FEAT-057：真实质量属性

**Files:**
- Create: `src/creo_mechdog/mass_properties.py`、`native/mass_properties.h`、`native/mass_properties.cpp`。
- Modify: `native/generic.cpp`/`native/worker.cpp` 的查询分发；`server.py`、包内 `capabilities.py` 和实际构建/源码身份清单；只按接入必需修改 `bridge.py`。
- Test: `tests/unit/test_material_mass_properties.py`、`tools/test_adoption_mass_properties.py`。
- Evidence/docs: `docs/work-items/FEAT-057.md`、`docs/development/ALPHAI-A01-ACCEPTANCE.md`。

**Interfaces:** 消费 model_id 与同通道原生查询；拟公开 `creo_get_mass_properties(model_id: str) -> dict`。包内 `normalize_mass_properties(raw: dict) -> dict` 仅做已知单位转换与完整性投影；原生 `nlohmann::json read_material_mass_properties(ProMdl model)` 查询实际材料。返回 `mass_kg`、`volume_mm3`、`density_kg_per_mm3`、`center_of_gravity_mm`、`principal_moments_kg_mm2`、`units`、`query_codes`、`complete`、`failed_components`、`calculation_method`；不可测数值 null。源件与 revision 不变。不得从当前 density=1 的几何查询推导“真实质量”。

- [ ] **1. 写有判据的失败回归**：`test_mm_kg_normalization` 断言 6000 mm³ × 7.85e-6 kg/mm³ = 0.0471 kg；`test_unknown_mass_unit_is_incomplete` 断言质量 null/complete=false；`test_missing_material_does_not_use_one`、`test_repeated_occurrences_count_twice`、`test_component_failure_not_partial_success` 覆盖来源/完整性，不以 Python 求和替代 Creo 取值。
- [ ] **2. 运行专项回归确认旧能力缺口**：`.\.venv\Scripts\python.exe -m unittest tests.unit.test_material_mass_properties -v`；新增契约项应先失败，保存失败依据，不因缺模块修改风格基线。
- [ ] **3. 实现查询**：核本机 SDK 真实材料密度/质量单位 API；模型/组件/材料查询失败保留原码，未知单位不猜；按 occurrence 统计且用 API 识别骨架，汇总变换/重心/惯量采用一致根坐标。组件 fallback 若不能证明单位与状态完整，返回未完成，不输出成功总质量。不得保存/激活/修改用户模型。
- [ ] **4. 专项通过并准备实机**：运行上述 unittest、`tools/test_adoption_mass_properties.py` 默认离线（仅检查输入/oracle/判定），以及 `bridge.py build`。实机用已知钢材 10×20×30 mm 方块、两个平移实例、混合长度/质量单位、缺材料/缺件；体积 6000、质量 0.0471、重心与解析相符，两个实例质量 0.0942，误差上限 `max(1e-9 kg, expected*1e-6)`，位置 ≤1e-5 mm；记录材料来源、查询前后源件 SHA256/revision/当前窗口不变。查询不制造“已保存重载”标记；夹具建模链另证保存重载。
- [ ] **5. 自查并提交**：核所有列表有界、未知值与单位；`FEAT-057: add material mass properties` 提交自己的明确文件，附本次证据/未测范围给集成人。

## A02 / FEAT-004：尺寸保护增量

**Files:**
- Create: `src/creo_mechdog/dimension_guards.py`、`native/dimension_guards.h`（只放本职责 helper）。
- Modify: `src/creo_mechdog/schema.py::DimensionValue`、`native/generic.cpp::dimension_cb` 和 set_dimensions；包内能力/结果投影、`server.py` 描述。
- Test: `tests/unit/test_dimension_guards.py`、`tools/test_adoption_dimension_guards.py`。
- Docs: 补建的 `docs/work-items/FEAT-004.md` 与 `docs/development/ALPHAI-A02-ACCEPTANCE.md`。

**Interfaces:** `DimensionValue` 保留 `id:int,value:float`，增加可选 `expected_value:float|None`、`expected_symbol:str|None`、`expected_owner:str|int|None`。`check_dimension_guard(current: dict, requested: dict) -> None` 负责共享判定，原生在写前实读并执行同契约。拒绝回显尺寸 id、预期/实际与原始查询码，不改变旧 revision 冲突语义。尺寸查询补 `owner_feature_id/name`、`relation_driven` 的真实来源与可编辑状态；未知状态不能回填 false。

- [ ] **1. 写失败回归**：`test_legacy_id_value_unchanged` 保持旧 payload；`test_guard_fields_reject_bool_nonfinite`；`test_stale_value_or_wrong_owner_refused`；`test_relation_query_failure_refused`；`test_all_dimensions_checked_before_first_write`。旧值 10→请求 12 时 current=10 通过，current=10.01 拒绝；尺寸旧值公差为 `max(1e-8, abs(expected)*1e-8)`。
- [ ] **2. 运行** `.\.venv\Scripts\python.exe -m unittest tests.unit.test_dimension_guards -v`，确认针对新字段/错误来源的回归先失败。
- [ ] **3. 实现**：revision 准入继续先行；每个 set_dimensions 操作先解析并读完全部目标、归属和关系，再设置任何值。同一个计划前面已做其他操作、后项 guard 不符时沿用整计划回滚，不谎报“整计划未写”。只新增可选保护，不强迫旧调用补字段。
- [ ] **4. 验证**：专项通过、默认离线驱动与 build；实机覆盖自由尺寸、关系驱动、符号/归属不符、批量第二项旧值错、旧接口和过期 revision。成功尺寸读回正确、revision +1、保存重载 true；入口拒绝无 job；已受理后原生守卫失败要核实际回滚、几何/revision 不变及后续合法编辑成功。
- [ ] **5. 提交** `FEAT-004: guard dimension writes by observed identity`；只回填本子项，不把 FEAT-004 其他尺寸分类缺证一并关闭。

## A03 / FEAT-035：标准螺纹孔

**Files:**
- Create: `src/creo_mechdog/hole_standards.py`、`native/standard_hole.h`、`native/standard_hole.cpp`。
- Modify: 包内 `schema.py::HoleOp`、`native/generic.cpp` hole 路由、`server.py::creo_hole`、能力/引用/结果文档与实际构建身份清单。
- Test: `tests/unit/test_standard_holes.py`、`tools/test_adoption_standard_holes.py`；回归既有 `tests/unit/test_hole_depth_basis.py`。
- Docs: `docs/work-items/FEAT-035.md` 追加本子项，`docs/development/ALPHAI-A03-ACCEPTANCE.md`。

**Interfaces:** 新增 `StandardHoleSpec(series: str, size: str, thread_depth: Positive)` 及 `HoleOp.standard`。standard 与 counterbore/countersink 互斥，`diameter` 在 standard=None 时仍必填；standard 提供 diameter 时必须与表值一致，否则拒绝。包内 `resolve_standard_hole(series: str, size: str) -> dict` 只读配置确定的安装 `.hol`，不接受任意路径。结果包含实际表标识/哈希、底孔直径、螺纹系列/规格/深度及 `thread_metadata_verified`、既有 depth_basis/去料量。

- [ ] **1. 写失败回归**：标准分支省略 diameter、旧分支缺 diameter、互斥组合、`../`/绝对路径/空型号、不存在表、重复规格、bool/非有限值；`test_thread_depth_strictly_inside_tip_depth`；保留旧三种 depth_basis。脱敏 `.hol` 片段仅做解析夹具，不复制 PTC SDK 文件。
- [ ] **2. 运行** `.\.venv\Scripts\python.exe -m unittest tests.unit.test_standard_holes tests.unit.test_hole_depth_basis -v`，先看到新增契约不满足。
- [ ] **3. 实现**：对照本机 SDK/表格式冻结原生元素树，不能硬编码对方数值常量；创建一枚原生标准孔，读回系列、规格与螺纹属性，查询失败不能写 true。保留 tip 深度、引用、方向、去料和检查点语义；无匹配表时明确不可用，不退成普通直孔冒充螺纹。
- [ ] **4. 验证**：专项/默认离线驱动/build；实机至少本机表中两个已枚举规格、翻向、旧直孔/沉孔/沉头回归、非法型号和过深螺纹。孔数 +1、真实元数据匹配、底孔去料对表值解析、revision、保存重载 true、故意失败计划回滚通过。规格可用性以实际安装为准，不预写“所有 ISO 均支持”。
- [ ] **5. 提交** `FEAT-035: add guarded standard threaded holes`；卡中通孔、出口沉头、双端沉孔、其他版本未测仍保留。

## A04 / FEAT-058：原生矩形平面壁

**Files:**
- Create: `src/creo_mechdog/native_planar_wall.py`、`native/planar_wall.h`、`native/planar_wall.cpp`。
- Modify: 包内 schema/能力/结果/引用、`native/generic.cpp`、`server.py` 和构建身份清单；复用 `sheetmetal.py` 的受管与子类型检查。
- Test: `tests/unit/test_native_planar_wall.py`、`tools/test_adoption_planar_wall.py`；影响回归 `tools/test_sheetmetal_contract.py`。
- Docs: `docs/work-items/FEAT-058.md`、`docs/development/ALPHAI-A04-NATIVE-CONTRACT.md` 与验收摘要。

**Interfaces:** 拟新增 `sheetmetal_planar_wall{label,plane,length,width,thickness,direction}` 与 `resize_sheetmetal_planar_wall{feature,length,width}`；公开包装 `creo_sheetmetal_planar_wall`/`creo_resize_sheetmetal_planar_wall` 均消费 model_id/expected_revision。首版空受管钣金建矩形首壁；改型拒绝下游依赖/不支持截面，不自动删除约束或放宽守卫。长度沿真实草图 U、宽度沿 V、厚度方向显式，不能用排序后 bbox 代替有符号坐标证明。B02 复用此特征的真实尺寸/截面身份。

- [ ] **1. 先冻结可行路线**：离线读匹配 SDK 与对方实现，准备最小创建/重定义探针；获会话窗口后验证原生子类型、特征形式、元素树抽取/重载。给出可行/不可行/未验证及 API 原码；未通过不开放工具。契约需列 B02 所需真实尺寸身份和持久化方法。
- [ ] **2. 写并运行失败回归**：`test_requires_empty_sheetmetal`、`test_resize_preserves_feature_identity`、`test_downstream_dependency_refused`、`test_square_not_silently_unconstrained`、`test_signed_envelope`、失败恢复状态；运行 `python -m unittest tests.unit.test_native_planar_wall -v`。
- [ ] **3. 实现**：建立标准首壁、读回厚度/特征；就地改矩形保留未授权约束，只有探针证明且契约允许的等长推断可受控移除并回报。恢复原元素树要检查返回码及几何，恢复未知继续保护。旧 `sheetmetal_wall` 行为不变。
- [ ] **4. 验证**：专项、默认离线驱动/build 后，串行实机 100×60×1（6000 mm³）→120×80×1（9600 mm³），反向厚度、正方形→长方形、非法厚度/依赖拒绝。feature_id/厚度保持，U/V 长宽与有符号 AABB 正确，保存重载 true，失败回滚与再次编辑通过；旧首壁/折边做影响回归。此项通过不关闭四壁/relief。
- [ ] **5. 提交** `FEAT-058: create and resize native planar walls`，将冻结尺寸映射交给 B02。

所有 live 驱动统一默认离线；`--live --confirm-session-usable` 仅由获安排的会话负责人运行。上述 `python` 命令执行时统一使用项目 `.venv\Scripts\python.exe`。
