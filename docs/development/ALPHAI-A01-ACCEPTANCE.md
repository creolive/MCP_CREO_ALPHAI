# A01 / FEAT-057 真实质量属性：验收摘要（零件路径）

日期：2026-11-04。分支 `codex/FEAT-057-mass-properties`，实机环境本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK，单会话串行。

驱动：`tools/test_adoption_mass_properties.py`（离线 11 例 + 实机 8 例，19 例全部通过；证据 `build/acceptance_mass_properties.json`，SHA256 `e47d4412b79a8d852a73135fff13860a7325eeed91aa1095320a2189e4b71f9b`，最终格式化源码重建后重跑）。探针：`tools/probe_mass_properties.py`。

## 一 密度口径（用户 2026-11-04 决定）

本机新零件的材料记录存在但**没有密度**：`ProMaterialCurrentGet` 成功，`PRO_MP_DENS_DEFAULT` 返回 `-1`。因此按"可选密度参数"实现：

1. 模型材料有可用密度 → `density_source="model_material"`（唯一描述零件的密度）；
2. 否则调用方给 `density_g_cm3` → `density_source="request"`（显式 what-if，不冒充材料）；
3. 两者都没有 → `mass_g=null`、`density_g_cm3=null`、`density_source="none"` 并带 `hint`，绝不用假定密度补数。

## 二 实机逐例（10×20×30 方块，6000 mm³）

| 用例 | 期望 | 实测 |
| --- | --- | --- |
| `part_without_density` | 只给体积/质心，质量为空并给指引 | `volume_mm3=6000.0`、质心 `[5,10,15]`、`mass_g=null`、`density_source="none"`、hint 存在 |
| `part_with_requested_steel` | 7.85 g/cm³ → 47.1 g | `mass_g=47.1`、`density_g_cm3=7.85`、`density_source="request"`、回执带 `job_id`/`model_id` |
| `read_only_revision` | 查询不改模型 | 查询前后 revision 相同 |
| `fixture_block` | 底板建模成功 | succeeded |
| `assembly_two_instances` | 两实例平移装配，总量翻倍、质心随平移移动 | `volume_mm3=12000.0`、`mass_g=94.2`、质心 `[30,10,15]`、`density_source="request"`、查询前后 revision 相同 |

装配夹具（`fixture_assembly` / `fixture_second_instance` / `fixture_instance_translation`）：同一个 10×20×30 零件装两次，第二实例用 `component_placement` 平移 `[50,0,0]`，质心由 `[5,10,15]` 移到 `[30,10,15]`——与 `(5+55)/2=30` 一致，说明位置真的进了计算，不是两台叠在原点。

离线覆盖：回执归一化的四类自相矛盾组合（有质量无来源、质量与体积×密度不符、体积缺失、未知来源）、未知质量单位保留原始值、schema 对 `density_g_cm3` 的边界（0 与 40 拒绝，7.85 与省略接受）。

## 三 实现位置

- `native/mass_properties.h`：质量单位读取与克因子表（只对 `g/kg/tonne` 生效）。
- `native/generic.cpp` 的 `mass_properties_json(op)`：体积用单位密度计算；质量优先材料密度，其次显式密度；程序集明确拒绝。
- 只读 op `mass_properties`：schema `MassPropertiesOp`、`generic_bridge` 只读白名单、`REGISTERED_OPERATIONS` 与 `families()` 登记。
- 工具 `creo_get_mass_properties(model_id, density_g_cm3=None)`：同步等待只读作业并返回归一化回执；工具数 95→96（四处契约测试同步更新）。
- `src/creo_mechdog/mass_properties.py`：回执归一化与自洽校验；`tests/unit/test_mass_properties.py` 9 例。

## 三之二 本轮确认的两条原生事实

1. **装配体查询要回退**：`ProAssemblySolidMassPropertyGet(solid, nullptr, &mp)` 在本机返回 `-1`（它要求真实的 csys selection），回退 `ProSolidMassPropertyWithDensityGet(..., PRO_MP_DENS_USE_ALWAYS, 1.0, ...)` 返回 `0` 并给出正确体积。回执保留 `assembly_query_code` 与 `source`，能看清走了哪条路径。
2. **装配位姿不生效，位移要用 `component_placement`**：`assemble_component` 的 `placement="default"` 加 `translation` 不会移动实例（先验时质心仍是 `[5,10,15]`），改用 `component_placement` 后质心才到 `[30,10,15]`。夹具按后者写。

## 四 偏差

- P00 写的 `native/mass_properties.cpp` 实际以 `mass_properties.h` + `generic.cpp` 落点：该文件的孔/查询路由与元素树辅助集中在 `generic.cpp`，独立 .cpp 会重复 `log`/`CK`/`get_optional` 走线。功能与契约不受影响。
- 契约新增可选参数 `density_g_cm3`（用户已确认），回执多 `density_source`/`hint`/`query_codes` 三个说明性字段。

## 五 未验证范围

- **混合单位**：模型单位来自模板，工具集没有改单位系统的操作；英寸件只能用离线归一化用例（`unknown_mass_unit_keeps_model_values`）覆盖，**未做实机**。质量换算表目前只认 `g/kg/tonne`，其他质量单位报原始值。
- 带真实材料密度的路径（`density_source="model_material"`）**未实机触发**：本机新零件的材料没有密度，只能靠显式密度走通；该分支只有离线用例。
- Creo 9 / Creo 10 实机。
- WorkBuddy 黑盒验收。

## 六 2026-11-04 离线数值守卫补充（仅本子项）

本轮仅在 `E:\Projects\codex-A01` / `codex/FEAT-057-mass-properties` 强化 Python 回执归一化，不重跑或改写上述历史实机证据。正常 6000 mm³、7.85 g/cm³、47.1 g、重心 [5,10,15]、model_material/none 语义和原始 query_codes/hint 均保留。三标量与合法三维重心中的非有限数字、float 转换溢出及自洽乘法/差值溢出现在拒绝为含字段上下文的 ValueError；有限负重心仍可返回浮点列表。

环境 Windows x64 / Python 3.12.14，实际解释器、模块和 SOURCE_PATHS.resource_root 均确认来自本工作树。测试基线 `f4be20e9cc1921ae031d453b61cf1b27c4317f4a`、dirty=true；源码指纹 `e99c50c61fedb59dc7372aadfa5a346f168b3875f48ca45607af4b3d59a0e428`。

- 专项命令 `.\.venv\Scripts\python.exe -m unittest tests.unit.test_mass_properties -v`：RED 为 20 例 / 48 failures / 12 errors；GREEN 为 20/20 通过。
- 两个改动 Python 文件的 `ruff check` 与 `ruff format --check` 均通过（Ruff 0.17.0）。
- 一次 `.\.venv\Scripts\python.exe tools/dev_check.py --work-item FEAT-057-numeric-guards` 明确失败：四个本次未改文件的格式回归阻断，unit_tests=not_run、native_validation=not_run。对应文件与基线无 diff 且 LF 规范化哈希相同，未修改基线；详见本机交接报告及 `build/development_check.json`。

本轮没有原生修改/构建、Toolkit/Creo/MCP 连接或 live 驱动。真实材料密度与材料重心、混合/未知单位、同步/异步接口、工具数、主惯量、complete 契约和其余 A01 范围未在本子项验证/完成；Creo 9/10、WorkBuddy 仍未测。不以离线数值防护通过宣称整个 A01 完成。

独立全量离线单测 `.\.venv\Scripts\python.exe tools/test_unit.py`：2288/2288 通过、0 failures / 0 errors，退出码 0（`build/unit_test_report.json`）。此结果与失败的 dev_check 分别记录。
