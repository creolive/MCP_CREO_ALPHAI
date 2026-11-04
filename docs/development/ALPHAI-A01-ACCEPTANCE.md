# A01 / FEAT-057 真实质量属性：验收摘要（零件路径）

日期：2026-11-04。分支 `codex/FEAT-057-mass-properties`，实机环境本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK，单会话串行。

驱动：`tools/test_adoption_mass_properties.py`（离线 11 例 + 实机 4 例，全部通过；证据 `build/acceptance_mass_properties.json`）。探针：`tools/probe_mass_properties.py`。

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

离线覆盖：回执归一化的四类自相矛盾组合（有质量无来源、质量与体积×密度不符、体积缺失、未知来源）、未知质量单位保留原始值、schema 对 `density_g_cm3` 的边界（0 与 40 拒绝，7.85 与省略接受）。

## 三 实现位置

- `native/mass_properties.h`：质量单位读取与克因子表（只对 `g/kg/tonne` 生效）。
- `native/generic.cpp` 的 `mass_properties_json(op)`：体积用单位密度计算；质量优先材料密度，其次显式密度；程序集明确拒绝。
- 只读 op `mass_properties`：schema `MassPropertiesOp`、`generic_bridge` 只读白名单、`REGISTERED_OPERATIONS` 与 `families()` 登记。
- 工具 `creo_get_mass_properties(model_id, density_g_cm3=None)`：同步等待只读作业并返回归一化回执；工具数 95→96（四处契约测试同步更新）。
- `src/creo_mechdog/mass_properties.py`：回执归一化与自洽校验；`tests/unit/test_mass_properties.py` 9 例。

## 四 偏差

- P00 写的 `native/mass_properties.cpp` 实际以 `mass_properties.h` + `generic.cpp` 落点：该文件的孔/查询路由与元素树辅助集中在 `generic.cpp`，独立 .cpp 会重复 `log`/`CK`/`get_optional` 走线。功能与契约不受影响。
- 契约新增可选参数 `density_g_cm3`（用户已确认），回执多 `density_source`/`hint`/`query_codes` 三个说明性字段。

## 五 未验证范围（A01 尚未整体验收）

- **装配体**：原生已改为走 `ProAssemblySolidMassPropertyGet(solid, csys_sel=nullptr, &mp)` 并回报 `volume_query_code`，但**实机未验**：本次尝试用 10×20×30 零件做两实例平移装配时，`assemble_component` 的 `placement` 只接受 `fixed/default/constraints`（`identity` 被 schema 拒绝），改用 `default` 仍未通过校验，`AssemblyPose` 的平移字段口径未确认。因此 P00 的"两实例装配、总质量 94.2 g"**没有通过证据**，装配路径视为未验证，不得据此外推。
- **混合单位**：模型单位来自模板，工具集无法改单位系统；英寸件只能用离线归一化用例覆盖，未做实机。
- Creo 9 / Creo 10 实机。
- WorkBuddy 黑盒验收。
