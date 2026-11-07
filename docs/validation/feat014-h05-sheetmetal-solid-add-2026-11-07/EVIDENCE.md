# FEAT-014/H05 钣金附着增料反证（2026-11-07）

## 结论

**不可用（保持门禁）。** Creo 12.4.0.0 上「`new_body=true` 建独立实体 + `boolean_bodies(union)` 并回钣金体」不构成附着增料路线：

- union 以钣金体为 target：`ProFeatureWithoptionsCreate=-1`，作业失败并回滚，几何不变。
- 反向 union 以新实体为 target：特征建成并保存重载，但钣金体被吞并；同一次保存后壁面候选边从 8 条 eligible 变为 0 条，全部 `ProSmtedgeContourGet=-8`，`sheetmetal_unbend` 失败并回滚。
- 直接 `extrude(add)`：`ProFeatureWithoptionsCreate=-1`，元素错误列表为空，回滚成功。
- 同件「实体-实体」union 成功，证明布尔特征本身在该钣金件可用，`-1` 特定于钣金体。

Creo 10 从未实际尝试；本证据只覆盖本机 Creo 12.4.0.0、mm、下述单一几何。

## 环境与源码身份

- Windows x64；Creo 12.4.0.0；本机匹配 Toolkit SDK；单位 mm；单会话、串行、单通道。
- worktree `e:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-h05h12`，HEAD `3a29c0d`；探针时工作树干净（`git status --short` 无输出）。
- 构建：`.\.venv\Scripts\python.exe bridge.py build` → 退出 0；执行器 `build/creo_worker.exe` SHA256 `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb`。
- `config.json`：`auto_start_creo=false`；Creo 12.4 由用户手工启动并确认会话可用。本轮未启动、关闭或重启 Creo，未清 unknown 保护，未做故障注入；未重提已受理 job。

## 几何夹具

- 主体：`creo_new_sheetmetal(template="native_planar")` → `sheetmetal_planar_wall`，XY 平面，100×60×1 mm，`origin=[0,0]`，`direction=positive`；实测 bbox `[0,0,0]..[100,60,1]`，体积 6000 mm³。
- 凸台：XY 草图 `[20,20]..[30,30]`，`extrude(depth=5, mode=add, direction=positive, new_body=true)`；bbox `[20,20,0]..[30,30,5]`，体积 +500 mm³。
- 两者重叠带 `10×10×1=100 mm³`，因此合并后的解析体积应为 6400 mm³；未合并时应为 6500 mm³。

## 路径与原始返回

### A. 直接 `extrude(add)`（探针内仅绕过 Python 准入纯函数）

模型 `8a4bef3d81d840e392c8ef2919e1d3c4`（`h05_add_*`），壁 job `6fec269564d644fa956e1fedbc7db43c`，raw add job `db9eecbd3a6e4e7caff0aec7e560972f`。

| 字段 | 值 |
| --- | --- |
| 终态 | `failed` |
| `failed_stage` | `execute_extrude` |
| `failed_toolkit_call` | `ProFeatureWithoptionsCreate` |
| `toolkit_code` | `-1` |
| 元素错误 | 空（job 目录无 `Element errors:` / `feature_error element=`） |
| `rollback_succeeded` | `true` |
| 结果体积 / 实体体 | 6000 mm³ / 1 个实体体 |
| revision | 2 → 2 |
| `saved_file_reloaded_and_verified` | `false`（失败回滚，未进入保存验收） |

原生日志含 `BUILD_FAILED=Extrude feature creation failed (ProFeatureWithoptionsCreate=-1)`；作业消息同时给出截面诊断（1 个闭合轮廓、4 条实体、0 开放端），并明确声明该计数不能定因。

> 仅为取证：探针进程内临时把 `creo_mechdog.sheetmetal.solid_add_on_sheetmetal_problem` 置空后调用 `generic_bridge.submit`；生产门禁与 MCP 服务未改动，探针结束即恢复。未经由此绕过做任何产品变更。

### B. `new_body=true` 独立实体

模型 `87f6ec8b82b44b95a98b2e8f1b1f8eee`（`h05_clean_8ada34`），壁 job `fed780e0071b4d9ca4171bdc9d9d5a94`，凸台 job `29f11db4290342af8aa435ec69ca6865`。

| 字段 | 值 |
| --- | --- |
| 终态 | `succeeded`，`toolkit_code=0` |
| revision | 2 → 3 |
| 体积 | 6000 → 6500 mm³（+500，未合并） |
| 实体体 | 2 个 active/material：id 52（bbox `[0,0,0]..[100,60,1]`）与 id 116（bbox `[20,20,0]..[30,30,5]`） |
| 壁面候选边 | 12 查 8 eligible（凸台加入后 24 查 8 eligible） |
| `saved_file_reloaded_and_verified` | `true` |

### C1. union 以钣金体为 target（52 ← 116）

模型 `6d755207dd534263803100d6b340a30e`（`h05_wall_c6c8d2`），job `caf37e4944c641bd8c1a4a6a9f9fba46`。

| 字段 | 值 |
| --- | --- |
| 终态 | `failed` |
| `failed_stage` | `execute_boolean_bodies` |
| `failed_toolkit_call` | `ProFeatureWithoptionsCreate` |
| `toolkit_code` | `-1` |
| `rollback_succeeded` | `true` |
| 结果体积 / 实体体 | 6500 mm³ / 2 个 |
| revision | 3 → 3 |

### C2. 反向 union 以新实体为 target（116 ← 52）

同一干净序列模型 `87f6ec8b82b44b95a98b2e8f1b1f8eee`，job `0099c06293d84a71b5b09f2e0a5d6b86`（另一模型 `6d755207…` 的 job `6c35874d77c8456c9f374ae5c57ff53b` 结果相同）。

| 字段 | 值 |
| --- | --- |
| 终态 | `succeeded`，`toolkit_code=0` |
| revision | 3 → 4 |
| 体积 | 6500 → 6400 mm³（合并去重 100 mm³ 重叠） |
| 实体体 | 1 个 active/material：id 116，bbox `[0,0,0]..[100,60,5]` |
| `saved_file_reloaded_and_verified` | `true` |
| 壁面候选边 | 合并前 8 eligible → 合并后 **24 查 0 eligible、24 全 -8** |
| `sheetmetal_unbend`（job `f3c83cbf19ee432cb1f5d463111cf94c`） | `failed`，`toolkit_code=-1`，`failed_stage=execute_sheetmetal_unbend`，`rollback_succeeded=true`，revision 4 → 4、体积 6400 不变 |

即几何上「成功」，但结果不再具备可用钣金身份：没有可挂折边的壁面轮廓，展开失败。另一模型在反向 union 后追加 `new_body` 凸台并以合并体为 target 再做实体-实体 union 也成功（job `32eae0e83d7d4f6eaacc65ca0782c163`，6800 mm³、1 体、保存重载 true），反证 id 116 此时已不是钣金体（否则会像 C1 一样 `-1`）。

### D. 同件「实体-实体」union 对照

模型 `6d755207dd534263803100d6b340a30e`：第二个 `new_body` 凸台 10×10×5（job `abfb4e0e4c244682ba38275749317eac`，6900 mm³、2 体），再 union 116 ← 188（job `32eae0e83d7d4f6eaacc65ca0782c163`）→ `succeeded`、6800 mm³、1 体、`saved_file_reloaded_and_verified=true`。说明布尔特征本身在该钣金件可创建；C1 的 `-1` 特定于钣金体作为 target。

### E. 最小替代（仅记录可行性，未实现）

独立实体件 + 装配放置可行：零件 job `7fa88204f92a4c8c98740ed472e08920`（模型 `929ebf222bb4486d8f3165895bbda94d`，10×10×5，500 mm³），新建装配 job `46c729279ce546808e81cb70f78e67eb`（模型 `cb5440cf1d904978bf8d1d243a28cded`），`assemble_component(fixed, translation=[0,0,0])` job `f70d238a64bf44f2815c4f124b0ec090` → `succeeded`，装配 revision 1 → 2，保存重载 true。这是两个独立组件，不是一体成形，不构成钣金增料能力。

## 仍未交付的子项（本轮只记录，不实现）

- 连续多边折边：`miter_cuts` 只覆盖四壁直角盒的角部重叠；非矩形连续边链、切角量与角部间隙未定标。
- corner relief：无原生路线；现有 `relief` 仅为弯端释放（`PRO_E_SMT_BEND_RELIEF`），不是 corner relief。
- 百叶（louver）、成形（forms）、hem、jog：无公开工具。
- 格栅孔：只能用 cut 去除材料，不是钣金成形特征。
- 凸台 / 铰链 / 门板耳：附着增料无通道；`new_body` 只能给独立实体，装配放置只能做独立组件。
- Creo 9/10 实机、非 mm 单位、其他板厚/几何、WorkBuddy 黑盒验收均未验证。

## 未验证

- Creo 10（及 Creo 9）从未尝试附着增料或 union。
- 其他凸台形状、板厚、位置与更大重叠；多凸台同时 union 的失败顺序。
- 反向 union 后是否还能通过其他原生 API 恢复钣金身份（未尝试；本轮不开放任何 opt-in）。
- 字面会话擦除后重载、WorkBuddy、并发/通道压力。
