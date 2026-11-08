# DEV-078 Modeling Alternatives Offline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 实现曲面与钣金的下一批候选路线，取得离线契约/构建证据，并准备准确的后续实机交接。

**Architecture:** 沿用包内严格 schema、capabilities 统一门禁和原生 Toolkit dispatch。候选有独立操作名但不公开工具；只在当前已经 gated 的四边填充上替换被否决的构造。复杂实机引用与成功样件不在离线阶段伪造。

**Tech Stack:** Python 3.12 / Pydantic / unittest；C++17 / Creo 12.4 Toolkit。

**Spec:** `docs/work-items/DEV-078.md`（用户授权沿前次六条建议执行；离线边界为本卡所列）。

## Global Constraints

- 不连接、启动、结束或清理 Creo/Toolkit；不执行 live 驱动，不清 unknown，不绕过 busy。
- 公开工具保持 107；所有新原生候选均 unavailable，不能通过 plan 旁路。
- 几何在原生端计算；Python 仅校验与准备输入，离线通过不等于几何通过。
- 不改主工作区文件、历史 validation 原件、已发布版本/标签、version.py；不推送/合 main/发布。
- 不复制 constants.inc；从本机 SDK 重新生成；生成文件不提交。

## Review Focus

- bool/NaN/重复引用、非法拓扑必须拒绝，不能 coercion 变成有效候选。
- 新 flange profile 不能通过旧 flange 输入获得执行入口；原有 miter/相邻保护保持。
- 两方向曲线的顺序/反向和四角闭合需真正处理，ADD_CLOSED 不能再当填孔。
- 角部面类型/重复、quilt 与目标体归属及 API 错误需明确；回执不能把请求当观测。
- 所有候选要覆盖 schema→capability 准入拒绝；公开工具数量不变。

### Task 1: Four-boundary two-direction patch

**Files:** `src/creo_mechdog/surface_ops.py`、`native/surface_boundary_fill.cpp`、`tests/unit/test_surface_boundary_fill_contract.py`。
**Interfaces:** 继续 `surface_boundary_fill`；`boundary` 恰好四条有序曲线；`closed=true` 表示输入周界闭合，原生 ADD_CLOSED=false。两方向分别用对边，正确映射链方向；结果 route 描述更新。不改共享 capabilities（集成任务负责）。
- [x] 先写四边契约、三/五边拒绝、双方向及方向处理的有效回归；运行失败用例。
- [x] 修正 schema 与原生树及错误/诊断文案；保留测量、回滚和单位保护。
- [x] 定向回归通过，格式化自己的变更，给出报告；不构建、不提交共享文件。

### Task 2: Native independent relief and quilt form candidates

**Files:** 新 `src/creo_mechdog/sheetmetal_candidates.py`、`native/sheetmetal_candidates.cpp`、`tests/unit/test_sheetmetal_candidates.py`。
**Interfaces:** 导出 `SheetmetalCornerReliefOp`（op=sheetmetal_corner_relief；label；flat surface ref；bends恰好两个surface refs；width/depth正毫米；state formed/unbent；矩形释放）及 `SheetmetalQuiltFormOp`（op=sheetmetal_quilt_form；label；quilt ref；side face/offset；material_side inside/outside；keep_quilt默认true；trim_sides默认false）。原生函数 `generic_sheetmetal_corner_relief` / `generic_sheetmetal_quilt_form`；include 放在 advanced.cpp 之后（集成任务负责）。原生面类型与单位验证，定位唯一非空材料钣金体、读取体级板厚并显式写 body selection（不能复用默认体 body_options）；复用 create、remember。根据本机公开头文件构造，缺 SDK 头时明确不支持，不能破坏旧 SDK 编译。可选 body refs 仅在真实接线后接受，不接受静默忽略字段。
- [x] 补严格输入失败用例并记录 RED。
- [x] 实现模型与原生树，释放 Toolkit 资源；不推测实际去料/展开成功，不用布尔补体。
- [x] 定向测试 GREEN，报告包含缺失环境与文档/SDK依据；不修改共享 dispatch/schema/capabilities，不构建、不提交。

### Task 3: Multi-entity flange profile candidate

**Files:** 新 `src/creo_mechdog/flange_profile.py`、可选 `native/flange_profile.h`、修改 `native/advanced.cpp`、新 `tests/unit/test_flange_profile.py`。
**Interfaces:** 导出 `FlangeProfile`，接受2–32条line/arc组成的有序连续开放链；首端[0,0]、无零长/重复/闭环/自交，数字有限不接受bool；沿既有populate_profile语义。原生 `generic_sheetmetal_flange` 在 op=sheetmetal_flange_profile 时使用 `profile`（标准profile/dimensions/constraints结构），旧op保持单线。新schema由集成者从SheetmetalFlangeOp派生，height/angle禁止用户提供，内部需旧guard时使用从截面得出的明确extent，不能把extent当观测高度。保留miter/邻接守卫及错误回读。
- [x] 先为几何连续性、弧方向/单位、拒绝输入写有意义测试并记录RED。
- [x] 实现输入校验与native多实体截面；不读/分发PTC库存.sec，不假造hem已验。
- [x] 定向GREEN，格式化与报告；不修改共享schema/capabilities/dispatch、不构建、不提交。

### Task 4: Integration, recipes and offline validation

**Files:** `src/creo_mechdog/schema.py`、`capabilities.py`（包内）、`native/generic.cpp`、`job_projection.py`（确有需要才改）、`tools/generate_constants.py`（确有需要才改）、新包内`modeling_recipes.py`及`tools/test_modeling_alternatives.py`与对应单测、`docs/development/DEV-078-HANDOFF.md`、工作卡与BACKLOG。
- [x] 合并三任务接口，三新op全部登记/门禁；补完整准入拒绝及107工具回归，错误版本措辞准确。
- [x] 标准Offset：准备成功样件dump/UDF输入绑定与验收条件；缺.gph明确pending_reference，不能写猜测offset树。Punch/Die工具件同样准备参照件与UDF交接。N边patch、板中部jog保留明确后续范围。
- [x] 格栅：创建明确位于native_planar基体范围内的单孔/多孔对照计划；默认离线校验，不从旧失败推测根因。
- [x] 独立环境运行定向测试、统一dev_check与完整单测；用本机SDK重新生成constants并build，不连接Creo。记录日志/源码指纹/未测范围。
- [x] 独立审查每个任务与全分支，修复发现；仅提交本分支变更，状态清晰并交接。
