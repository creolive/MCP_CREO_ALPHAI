# WorkBuddy 黑盒验收报告（第一轮，前置缺失被阻塞）

来源：用户于 WorkBuddy 客户端执行 2026-10-24（提示词见 [取证记录](../BUG080-FEAT006-LIVE-2026-10-24.md) WorkBuddy 节）。逐字归档，未修改。

---

# WorkBuddy 黑盒验收报告（BUG-080 / FEAT-006）
**测试方式**：仅调用 MCP 工具，未读取源码/本地配置。所有字段引用原始返回。
---
## 环境自报（creo_capabilities, detail=compact）
- `name`: `MCP_CREO_MechDog`，`version` / `server_version`: **0.5.1**（`update.status`: `up_to_date`，`is_prerelease`: true）
- `unit`: `mm`，`angle_unit`: `degrees`；`tool_count` = `enabled_tool_count` = **91**，`unavailable_tools`: `[]`
- 调度：`native_channels: 1`，`admission: reject_busy_without_creating_a_job`
- 注意：`support_status.assembly_checks.status: "planned"`（tracking: FEAT-045），但 `families.session_assembly.enabled: true`（工具 `creo_inspect_session_assembly`）
## BUG-080：会话装配检查 — ⛔ 前置不满足，阻塞
**creo_list_session_models**（首次，实时采集，`snapshot_age_seconds: 0`）：
- `total: 6`，`complete: true`，`truncated: false`，`type_errors: []`，`next_cursor: null`
- 会话仅含 **6 个 part，无任何 assembly**：
  1. `MMNS_PART_SOLID_ABS`（part，origin 为 Creo 12.4.0.0 模板 `mmns_part_solid_abs.prt`，`session_model_id: 0`）
  2. `WB080_UNHEALTHY_100748`（part，`session_model_id: 1048577`，`modified: false`）
  3. `WB080_UNHEALTHY_100943`（part，`1572866`）
  4. `WB080_UNHEALTHY_101136`（part，`1572867`）
  5. `WB080_UNHEALTHY_101316`（part，`1572868`）
  6. `WB080_UNHEALTHY_101652`（part，`1572869`）
- 所有条目 `model_id: null`、`adopted_copy_model_id: null`、`has_saved_origin: true`、`is_current: null`
- 5 个 WB080 零件 origin 均指向 `E:\Projects\MCP_CREO_MechDog-task-2\models\<hash>\output\...prt.2`（疑似先前测试遗留，非本次预置的英寸装配）
**结论**：预置"英寸装配"在会话中不存在，`creo_inspect_session_assembly` 无合法 `name` 可调用，未执行。assembly.length_unit / units / transform_to_parent（预期 ≈25.4/50.8/76.2 mm）等字段**全部未验证**。预置状态与开发者描述不一致，需在 Creo 中重新加载装配后重测。
## FEAT-006：受抑制特征零件的 inspect 拒绝 — 实际返回非预期码
**creo_adopt_current_model(mode="inspect")** 原始返回：
- `available: false`
- `reason`: `NO_CURRENT_MODEL: the Creo window has no current model (ProMdlCurrentGet(&current) returned -8 PRO_TK_BAD_CONTEXT during adoption_inspect); switch to a model in Creo first`
- `reason_code`: **`NO_CURRENT_MODEL`**（预期 `unhealthy_features`，**未出现**）
- `available_modes: []`，`conflict: null`，`current_model: null`
- `refusal_details`:
  - `actual_units: null`，`actual_units_known: false`，`units_query_code: null`
  - `dependency_inventory: "unknown"`，`dependency_inventory_note`: "the native executor refused before a live summary was available; units/dependency/health values were not queried"
  - `health_breakdown`: `"unavailable for the same reason"`
  - **`refusal_details.unhealthy_features` 字段不存在**（因先于健康检查被拒绝，未生成 unhealthy_total/returned/truncated/items）
- `file: null`，`source_kind: "unknown"`，`model_id: null`，`evidence_token: null`
- 返回负载中未见独立 `isError` 字段（协议层未报错，属业务拒绝，可明确判定为拒绝路径）
**结论**：预期"当前模型含抑制特征 → `unhealthy_features` 拒绝"未触发——窗口当前无模型（返回码 -8 `PRO_TK_BAD_CONTEXT`）。健康明细（unhealthy_total/items/status_code 等）与 health_breakdown 原文**未验证**。
## 会话复査（creo_list_session_models 第二次）
- `total: 6`、`complete: true`、`truncated: false`，6 个模型名称/类型/顺序与首次完全一致
- `session_fingerprint: 2572692221204510962`（两次相同，连接/进程会话未变）
- `service_session_changes: []` —— 本轮 MCP 调用未引起任何会话变更（两次 inspect/list 均为只读路径，符合预期）
## 总结
| 条目 | 结果 | 说明 |
|---|---|---|
| BUG-080 | ⛔ 阻塞 | 会话无装配，预置①未落实；单位换算/变换矩阵未验证 |
| FEAT-006 | ⛔ 阻塞 | 窗口无当前模型（`NO_CURRENT_MODEL`），非预期 `unhealthy_features`；健康明细未验证 |
| 会话不变性 | ✅ 通过 | 两次 list 完全一致，fingerprint 相同，无服务侧变更 |
**建议**：请在 Creo 中①重新加载/激活英寸装配、②将带抑制特征的零件置为当前窗口模型后，再发起同一组验收。我未做任何重试或会话补救操作。
