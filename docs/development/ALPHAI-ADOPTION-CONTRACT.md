# DEV-067 P00：alphai 能力吸收共同契约（首轮冻结）

日期：2026-11-03。角色：P00 集成人契约冻结。基线：`main@8ab0641`（0.11.7 发布提交）。分支：`codex/DEV-067-alphai-plan`。状态：**离线冻结，未合 main、未连 Creo、未改产品行为**。

本文件只冻结首批 **A01 / A02 / A03** 的接口与文件归属。A04、B、C、D 的高风险接口按各自探针结果追加冻结；未冻结的接口只允许研究，不得由依赖方先实现猜测版本（主计划第三节）。

## 一 基线与并发边界

| 项 | 冻结值 |
| --- | --- |
| 集成人工作区 | `E:\Projects\MCP_CREO_MechDog`（唯一主干工作树） |
| 各任务工作区 | 独立 git worktree：`E:\Projects\codex-A01`、`codex-A02`、`codex-A03` |
| 任务分支 | `codex/FEAT-057-mass-properties`、`codex/FEAT-004-dimension-guards`、`codex/FEAT-035-standard-holes`，均自 `codex/DEV-067-alphai-plan` 分支 |
| 公共文件 | 只允许在任务分支做该任务必需的最小改动，并在交接里列出冲突 hunk；禁止两个 Agent 同时写同一公共文件 |
| 已有脏改动 | `session_activity.json` 属运行为产物；任何任务不得 reset/stash/覆盖他人未提交内容 |
| 合入与发布 | 任务分支不合 main、不改 `version.py`、不发布；由 P99 统一集成 |

已提交基线：`8798861`（`codex/BUG-111-doc-and-counts-fix`，BUG-111 文案与计数修正）、`33bb357`（`codex/DEV-067-alphai-plan`，规划/工作卡/台账登记）。

## 二 三个任务的接口冻结

### A01 `/ FEAT-057` 真实质量属性

**公开工具**：`creo_get_mass_properties(model_id: str) -> dict`，注解 `READ`。

**冻结形态**：与 `creo_refresh_model` 同构的**只读作业**——调用返回 `{job_id, model_id, status: "submitted", readonly: true, terminal_contract}`，数值在 `creo_get_job` 的终态回执 `result.mass_properties`。理由：活体模型查询必须占用唯一 Toolkit 通道并受 600 s 预算约束；同步探针（`session_status`/`callback_status`）只用于轻量状态，不用于模型查询。**否决**直接同步返回质量的写法，避免新增第二通道语义。

**回执块（字段冻结）**：

```json
{"mass_kg": 0.0471, "volume_mm3": 6000.0, "density_kg_per_mm3": 7.85e-06,
 "center_of_gravity_mm": [10.0, 15.0, 20.0],
 "principal_moments_kg_mm2": [12.5, 30.0, 36.0],
 "units": {"length": "mm", "mass": "kg"},
 "query_codes": {"mass": 0, "density": 0, "volume": 0},
 "complete": true, "failed_components": 0,
 "calculation_method": "ProSolidMassPropertyWithDensityGet",
 "components": {"returned": 2, "total": 2, "truncated": false, "items": []}}
```

- 不可测量的数值一律 `null` 且 `complete=false`；缺失材料**不得**回填密度 1 或质量 0。
- `components.items` 有界（≤20，`truncated` 显式标注），仅装配时出现。
- 错误/未知单位：`complete=false` + 原 `query_codes`，不猜单位。

**接入点（不新增 op 字符串、不进入 `creo_execute_plan`）**：

1. `server.py` 新增 `@mcp.tool(annotations=READ)` 函数，经 `invoke(general.submit, [], model_id, None, None, None, True)`。
2. `generic_bridge.py:194-197` 只读白名单加入 `mass_properties`（现有 `dump_tree`/`export`/`udf_inspect`）。
3. `generic_bridge.submit` 侧构造只读请求时带顶层键 `mass_properties: true`；`native/generic.cpp::run_generic` 按 `request.contains("mass_properties")` 分派（对齐 `session_models` 现有模式），**不进** `op` 名分发链。
4. 新增 `native/mass_properties.h` / `native/mass_properties.cpp`，由 `native/generic.cpp` 在 `inspection()` 定义之后 `#include`（`native/worker.cpp` 只编译一个 TU，未 `#include` 的 .cpp 不参与构建）。
5. 新增 `src/creo_mechdog/mass_properties.py`（`normalize_mass_properties(raw)` 只做已知单位换算与完整性投影）。
6. `server.py:71-146` `_SOURCE_NAMES` 登记新增 Python 与原生文件；`pyproject.toml` 无需改动（包内模块自动包含）。
7. `capabilities.families()` 新增族 `mass_properties`（只含 `enabled`/`tool`/`limits`/`scope`）。注意 `src/creo_mechdog/capability_summary.py::support_status()` 只映射既有的少数族键，`families()` 里多数族（如 `placement`、`drawing`）并不在其中；**默认不纳入 `support_status`**，若要纳入须同时改 `capability_summary.py` 与其契约测试 `tests/unit/test_t01_capability_contracts.py:21-40`。

### A02 `/ FEAT-004` 尺寸旧值/归属保护

**schema 冻结**：`DimensionValue` 保留 `id: int, value: float`，新增三个**可选**字段：

```python
expected_value: float | None = None  # 观测旧值
expected_symbol: str | None = None  # 观测符号名
expected_owner: str | int | None = None  # 观测归属（特征标签或 ID）
```

拒绝规则：`bool`、`NaN/Inf` 在 schema 层拒绝；旧 payload 不带新字段时行为不变。

**共享判定函数**：`src/creo_mechdog/dimension_guards.py::check_dimension_guard(current: dict, requested: dict) -> None`，违反时抛 `ValueError`，消息含 `dimension_id`、`expected_value`、`actual_value`、`expected_owner`、`actual_owner`、`query_code`。

**容差冻结**：`abs(expected - actual) <= max(1e-8, abs(expected) * 1e-8)`。

**语义冻结**：`revision` 准入先于 guard；一个 op 内**先读完全部目标**（值、符号、归属、relation 状态）再写第一个值；批内后项不符时按既有检查点整计划回滚，回执 `effect_status` 如实标注，不宣称“整计划未写”。

**查询字段冻结**：尺寸查询新增 `owner_feature_id`、`owner_feature_name`、`relation_driven`；查询失败或未知一律 `null`，**不得**回填 `false`。

**接入点**：`src/creo_mechdog/dimension_guards.py`（新）、`native/dimension_guards.h`（只放 helper 声明）、`schema.py::DimensionValue`、`native/generic.cpp::dimension_cb` 与 `set_dimensions`、`server.py` 描述、`_SOURCE_NAMES`。

### A03 `/ FEAT-035` 标准螺纹孔

**schema 冻结**：`HoleOp` 新增可选 `standard: StandardHoleSpec | None`：

```python
class StandardHoleSpec(StrictModel):
    series: str  # 表族，如 "ISO"；仅在已安装表中匹配
    size: str  # 规格，如 "M6"
    thread_depth: float  # > 0，且必须严格小于 tip 深度
```

- `standard` 与 `counterbore` / `countersink` **互斥**；
- `standard=None` 时 `diameter` 仍必填且行为不变；
- `standard` 提供 `diameter` 时必须与表值一致，否则拒绝；
- 拒绝 `..`、绝对路径、空型号、表中不存在规格、重复规格。

**查表函数**：`src/creo_mechdog/hole_standards.py::resolve_standard_hole(series: str, size: str) -> dict`，只读**配置确定的安装 `.hol` 目录**，不接受调用方路径；返回 `{series, size, table_id, table_sha256, tap_drill_diameter_mm, thread_depth_limit_mm}`。

**回执字段冻结**：新增 `thread_metadata{series, size, thread_depth_mm, table_id, table_sha256}` 与 `thread_metadata_verified: bool`；查询失败不得写 `true`。既有 `depth_basis`、去料量、引用与检查点语义不变。

**接入点**：`src/creo_mechdog/hole_standards.py`（新）、`native/standard_hole.h`/`.cpp`（新，`#include` 位置须在 `generic_hole` 之前）、`schema.py::HoleOp`、`native/generic.cpp` hole 路由、`server.py::creo_hole` 描述、`_SOURCE_NAMES`。

注意：`capabilities.families()` **没有 hole 族**（hole 只是 `REGISTERED_OPERATIONS` 里的 op），因此标准螺纹孔的边界写入 `creo_hole` 工具描述与 `docs/REFERENCE_SYNTAX.md`，**不新增族、不改 `REGISTERED_OPERATIONS`**；若确需新增族，按 A01 第 7 条同样处理 `support_status` 契约。

## 三 跨任务统一约定（三个任务都必须遵守）

| 主题 | 冻结规则 |
| --- | --- |
| 通道 | 唯一锁在 `bridge.py::toolkit_lock`；任务不得新增锁、队列或重试；忙即拒绝并带 `blocking_job_id/model_id/operation` |
| 回执预算 | 单次响应 ≤32 KiB；复用 `model_queries.RESPONSE_BUDGET`、`serialized_size`、`operation_results.enforce_compact_budget` |
| 列表边界 | 抽样上限 20，超出显式 `truncated`/`next_cursor`，不得静默截断 |
| 未知值 | 一律 `null` + 完整性标志；禁止用 0/1/false 代替未知 |
| 只读白名单 | 仅 A01 需要改 `generic_bridge.py:194-197`；A02/A03 是写路径，不改白名单 |
| 工具数 | 新增工具后 95 → 96/97/98，同步 4 处断言：`tests/unit/test_t01_capability_contracts.py:18`、`test_reference_contract.py:170`、`test_update_check.py:304`、`test_callback_admission.py:84` |
| 源码身份 | 新文件必须登记 `server.py:71-146` `_SOURCE_NAMES`；`pyproject.toml` 只对仓库根级垫片模块才需改 `py-modules` |
| 原生构建 | 单 TU：新 `.cpp` 必须被 `native/worker.cpp` → `native/generic.cpp` 链 `#include`；构建缓存按 `native/**.{cpp,h,hpp,inc}` 摘要自动失效 |
| 非原生查询登记 | A01 会触达 Creo，**不**加入 `server.py:623-629` `non_native_queries`（该表只放不连 Creo 的查询） |
| 版本与发布 | 本轮不改 `version.py`；目标版本由 P99 在集成完成、且用户指派发布后裁定 |
| 实机 | 本轮**不授权**连接 Creo。任何任务不得启动/重启 Creo、清 unknown 保护或注入故障；实机项如实记“未验证” |

## 四 文件所有权与集成次序

| 任务 | 独占新增 | 公共文件（最小改动） |
| --- | --- | --- |
| A01 | `src/creo_mechdog/mass_properties.py`、`native/mass_properties.{h,cpp}`、两个测试与一个离线驱动 | `server.py`、`native/generic.cpp`、`generic_bridge.py`、`capabilities.py`、`capability_summary.py`、`_SOURCE_NAMES` |
| A02 | `src/creo_mechdog/dimension_guards.py`、`native/dimension_guards.h`、测试与驱动 | `schema.py::DimensionValue`、`native/generic.cpp`（`dimension_cb`/`set_dimensions`）、`server.py` |
| A03 | `src/creo_mechdog/hole_standards.py`、`native/standard_hole.{h,cpp}`、测试与驱动 | `schema.py::HoleOp`、`native/generic.cpp`（hole 路由）、`server.py`、`capabilities.py` |

**集成次序**：A02 → A03 → A01。理由：A02 只动 `DimensionValue`，与另两者无交叉；A03 扩展 `HoleOp` 与 hole 路由；A01 动 `generic_bridge` 只读白名单与 `run_generic` 请求分派，最后合并冲突最少。每个任务提交前自行 `dev_check`，集成后由 P99 重跑全量。

**交接必填**（主计划第四节）：任务号/固定 ID、基线与 dirty、修改文件与公共文件冲突 hunk、schema/工具/回执变化与兼容示例、专项 unittest 结果、`dev_check` 与 build 结果、实机状态（本轮应为“未执行”）、能力边界与未测项、工作卡位置。

## 五 隔离 worktree 环境准备（每个任务照做一次）

```powershell
# 1) 建工作树与分支（以 A01 为例；P00 已执行，目录已存在时跳过）
git worktree add E:\Projects\codex-A01 -b codex/FEAT-057-mass-properties codex/DEV-067-alphai-plan

# 2) 复制本机配置（config.json 与 constants.inc 均为本机生成物，不提交）
Copy-Item E:\Projects\MCP_CREO_MechDog\config.json E:\Projects\codex-A01\config.json

# 3) 用主环境的解释器，但让导入解析到本工作树
$env:PYTHONPATH = "E:\Projects\codex-A01\src;E:\Projects\codex-A01"
cd E:\Projects\codex-A01
E:\Projects\MCP_CREO_MechDog\.venv\Scripts\python.exe -m unittest tests.unit.<本任务测试> -v

# 4) 原生构建（会在本工作树生成 native\constants.inc 与 build\）
E:\Projects\MCP_CREO_MechDog\.venv\Scripts\python.exe bridge.py build
```

注意：

- `native/constants.inc` 必须由本工作树重新生成，**不得**从主工作树或构建缓存复制。
- 若 `bridge.py build` 报找不到 SDK/编译器，先核 `config.json` 的 `creo_root`、`vcvars64` 与本机一致。
- 未设置 `PYTHONPATH` 时会导入主工作树的 editable 包，单元测试结果无效——交接里必须写明使用了哪条导入路径。

### 实测修订（2026-11-03，A02/A03 执行后）

只设 `PYTHONPATH` **不够**：`server.py:65-70` 有源码身份守卫，子进程测试（`unit.test_adoption` 等 22 项）按 `SOURCE_PATHS.resource_root` 判定“包属于另一个 checkout”而失败。可用做法是复制主环境（98 MB）并改指向：

```powershell
Copy-Item E:\Projects\MCP_CREO_MechDog\.venv <worktree>\.venv -Recurse -Force
# 复制后把 .venv\Lib\site-packages\__editable___mcp_creo_mechdog_0_11_5_finder.py 的 MAPPING
# 中 'E:\\Projects\\MCP_CREO_MechDog' 全部替换为本工作树路径（纯文本替换，勿用 pip 重装：环境内无 setuptools）
<worktree>\.venv\Scripts\python.exe tools\dev_check.py --work-item <ID>
```

改完后 `import creo_mechdog` 与 `SOURCE_PATHS.resource_root` 均指向本工作树，`dev_check` 全量单测可通过（A02、A03 已实测 `unit_tests=passed`、`success=true`）。

## 六 本次未冻结（只允许研究）

- **A04** 原生矩形平面壁：`sheetmetal_planar_wall` / `resize_sheetmetal_planar_wall` 的元素树与尺寸身份映射，需先完成离线 SDK 核验并按用户决定“仅离线”；探针结论记“未验证”，不开放工具。
- **B01/B02**：骨架模型身份与跨模型事务契约。
- **C01—C04**：组件状态、约束克隆、草图引用、rename/derive 的身份事务。
- **D01—D03**：会话上下文聚合、产品规则只读计划、版本回收保护清单。

## 七 P00 自查

- [x] 核对基线：`main@8ab0641`；本批两个开发分支已提交（`8798861`、`33bb357`）；工作树仅余运行为产物 `session_activity.json`。
- [x] 冻结 A01/A02/A03 的公开工具、schema 字段、回执字段、判定容差与错误形态。
- [x] 核实现有接入点：工具注册（`server.py:247+`）、只读作业链（`generic_bridge.submit` → `bridge._run_job_dispatch` → `run_generic`）、原生单 TU `#include` 链、源码身份 `_SOURCE_NAMES`、能力族与 `support_status` 双写、工具数 4 处断言。
- [x] 给出隔离 worktree 的环境准备与导入陷阱。
- [ ] 用户指派各任务负责人与执行顺序（负责人当前仍 `unassigned`）。
- [ ] A01/A02/A03 分支创建与首次推送（待用户指派后执行）。
