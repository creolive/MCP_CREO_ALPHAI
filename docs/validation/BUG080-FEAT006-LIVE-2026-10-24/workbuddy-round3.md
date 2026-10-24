# WorkBuddy 第三轮黑盒验收报告：BUG-080（整合树服务复验）

- 日期：2026-10-24（覆盖旧版同名报告；21:16 前置就绪后完成全部步骤）
- 范围：仅 BUG-080，整合树服务复验
- 执行约束：仅使用 MCP 公开工具；不读源码、不读本地文件、不运行本地脚本
- 结论：**全部通过** ✅（环境确认、前置确认、BUG-080 核验 a–e、重复性、无副作用）

## 1. 环境确认 — 通过

| 项目 | 输入 | 关键输出 | 预期 | 结果 |
|---|---|---|---|---|
| 服务端身份与版本 | `creo_capabilities({"detail":"compact"})` | `name = "MCP_CREO_MechDog"`；`version = "0.5.2"`；`server_version = "0.5.2"`；`update.status = "up_to_date"`；`tool_count = 91` | `server_version = 0.5.2` | **通过** |

说明：`latest_version = "0.5.1"`、`is_prerelease = true`，服务提示"当前版本高于最高公开版本，无需降级"，0.5.2 为在制版本，符合预期。

## 2. 前置确认 — 通过

| 项目 | 输入 | 关键输出 | 结果 |
|---|---|---|---|
| 会话清单（调用前，实时采集） | `creo_list_session_models({"limit":50})`（21:16:38） | `total = 2`：① `WB080_UNHEALTHY_121839`（part，model_id=`676bf721eca941a2ac9e6447b5dbf51b`，is_current=false，modified=false）；② `WB080_INCH_121839`（**assembly**，is_current=true，modified=false）；`session_fingerprint = "12127474059698656065"` | **通过** |

- `WB080_INCH_121839` 装配存在：**通过**
- 毫米组件 `WB080_UNHEALTHY_121839` 在会话中：**通过**（组件平移是否 (1,2,3) 英寸由第 3 步 d 项核验）

## 3. BUG-080 核验 — 全部通过

- 工具：`creo_inspect_session_assembly({"name":"WB080_INCH_121839","limit":50})`（第一次 21:16:51）
- 顶层返回：`total = 2`（同一组件的两个实例 component_id 40 与 41，均单独列出）、`complete = true`、`truncated = false`、`incomplete = false`、`depth_limited = false`、`root_visit_code = 0`

| 核验项 | 判定 | 原始数值证据 |
|---|---|---|
| a. `assembly.length_unit` 含 `name` 与 `scale_to_mm`，顶层为英寸、`scale_to_mm≈25.4` | **通过** | `name = "in"`，`scale_to_mm = 25.4`，`scale_to_mm_known = true`，`query_code = 0`，scale 各子查询码均为 0 |
| b. 组件节点含 `units.component`（mm，≈1.0）与 `units.parent`（inch，≈25.4） | **通过** | 两个实例一致：`units.component = {"name":"mm","scale_to_mm":1.0,"scale_to_mm_known":true}`；`units.parent = {"name":"in","scale_to_mm":25.4,"scale_to_mm_known":true}`，query_code 均 0 |
| c. `transform_to_parent` 为毫米归一化映射：旋转单位阵、平移≈[25.4, 50.8, 76.2] | **通过** | 3×3 旋转对角均为 `0.9999999999999999`（浮点单位阵），末行 `[25.4, 50.8, 76.19999999999999, 1.0]`；`transform_mm_known = true` |
| d. `transform_to_parent_raw` 存在且平移≈[1, 2, 3] | **通过** | 存在；3×3 对角 `0.03937007874015748`（=1/25.4，raw 保持源/目标模型长度单位），末行 `[1.0, 2.0, 3.0, 1.0]`（英寸） |
| e. 完整性标志为 true 且各节点一致 | **通过** | 顶层 `complete=true`、`incomplete=false`、`depth_limited=false`、`root_visit_code=0`；两组件实例均 `resolved=true`、`suppressed=false`、`packaged=true`、`transform_known=true`、`transform_mm_known=true`、`transform_root_known=true`，全部 `query_codes` 为 0；`constraints=[]` |

补充观察（非否决项）：`transform_to_root` 与 `transform_to_root_raw` 同 `transform_to_parent(_raw)` 完全一致（单层装配，符合预期）；`modified = false`（查验未改动模型）。

## 4. 重复性 — 通过

- 第二次调用 `creo_inspect_session_assembly({"name":"WB080_INCH_121839","limit":50})`（21:17:05）
- 两次输出逐项比对：assembly.length_unit、两组件实例的 units、transform_to_parent、transform_to_parent_raw、transform_to_root(_raw)、complete/incomplete/depth_limited/root_visit_code、各 query_codes **完全一致**（仅 `checked_at` 与 `snapshot_id` 不同）。
- 判定：**通过**

## 5. 无副作用 — 通过

| 检查项 | 实际调用 | 结果 |
|---|---|---|
| 调用前 `creo_list_session_models` | 已调用（21:16:38，total=2） | 通过 |
| 调用后 `creo_list_session_models` | 已调用（21:17:17，total=2） | 通过 |
| 调用前后会话清单是否一致 | 两次清单模型集合、顺序、字段（name/type/is_current/modified/origin/model_id）完全一致，`session_fingerprint = "12127474059698656065"` 不变，`service_session_changes = []` | **通过** |
| 是否保存模型 | 未调用保存类工具 | **通过** |
| 是否重建模型 | 未调用创建/重建类工具 | **通过** |
| 是否修改组件 | 未调用组件编辑类工具 | **通过** |

本轮全部调用（capabilities ×1、list_session_models ×2、inspect_session_assembly ×2）均为只读。

## 6. 总结

BUG-080 第三轮黑盒复验**全部通过**：服务版本 0.5.2 生效后，`creo_inspect_session_assembly` 的整合树输出完整实现了单位契约——顶层 `length_unit`（in / 25.4）、组件级 `units.component/units.parent`（mm 1.0 / in 25.4）、毫米归一化 `transform_to_parent`（单位阵 + [25.4, 50.8, 76.2]）与 raw 英寸矩阵（平移 [1,2,3]）并存，完整性标志全 true 且重复调用数值稳定，全程无副作用。与 2026-10-24 早前版本（0.5.1 时期 transform 平移为 [1,2,3]、无 units 字段）相比，本轮行为符合 BUG-080 修复预期。
