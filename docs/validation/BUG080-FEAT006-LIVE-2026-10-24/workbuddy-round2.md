# WB080 黑盒验收报告（BUG-080 / FEAT-006）

- 验收时间：2026-10-24 10:49（GMT+8）
- 服务标识：MCP_CREO_MechDog_dev（自报 name=MCP_CREO_MechDog，version=0.5.1，tool_count=91，unit=mm，angle=degrees）
- 方式：仅调用已连接 MCP 工具，只读；未做任何建模、保存、擦除或收养 apply；未读取源码/本地配置/仓库状态。
- 连接工具：creo_capabilities、creo_list_session_models、creo_inspect_session_assembly、creo_adopt_current_model（本次均为同步只读返回，未产生 job_id / model_id）。

## 前置核对（成立）

- 会话含装配 WB080_INCH_WB104102（assembly，session_model_id=524288，非当前窗口）。
- 会话含毫米零件组件 WB080_UNHEALTHY_101652（part，session_model_id=1572869）。
- 当前窗口模型为 DB_8BDD03C9DA（part，is_current=true，session_model_id=524294）。
- 前置成立，继续测试。

## 步骤 1｜环境与会话自报（通过）

- creo_capabilities：name="MCP_CREO_MechDog"，version=server_version=0.5.1（update.status=up_to_date，is_prerelease=true），tool_count=91 / enabled_tool_count=91，unavailable_tools=[]，unit="mm"，angle_unit="degrees"。
- creo_list_session_models（第一次）：total=8，complete=true，truncated=false，type_errors=[]。
- 会话清单（名称/类型/当前窗口/modified）：MMNS_PART_SOLID_ABS(part)、WB080_UNHEALTHY_100748(part)、WB080_UNHEALTHY_100943(part)、WB080_UNHEALTHY_101136(part)、WB080_UNHEALTHY_101316(part)、WB080_UNHEALTHY_101652(part)、DB_8BDD03C9DA(part, is_current=true)、WB080_INCH_WB104102(assembly)；全部 modified=false、model_id=null。
- session_fingerprint="2572692221204510968"，service_session_changes=[]。

## 步骤 2｜BUG-080 装配变换单位契约（不通过）

调用：creo_inspect_session_assembly，输入 name="WB080_INCH_WB104102", limit=20；isError 未置位（正常返回）。

### assembly.length_unit

- 预期：name="in"、scale_to_mm=25.4（记录全部查询码）。
- 实测：assembly 对象（name/model_type/origin/query_codes{ id:0, modified:0, name:0, origin:0 }/session_model_id=524288）中**不存在 length_unit 字段**，无任何单位查询码可记录。
- 结论：**不通过**。

### 组件 WB080_UNHEALTHY_101652 节点 units

- 预期：units.component name="mm"、scale_to_mm=1.0；units.parent name="in"、scale_to_mm=25.4。
- 实测：组件节点（component_id=40, occurrence_path=[40], resolved=true, suppressed=false, packaged=true, depth=0, feature_status=0, constraints=[], query_codes{constraint_comppath:0, constraints:0, feature_status:0, model:0, model_type:0, packaged:0, transform:0}）中**不存在 units 字段**（无 component/parent 单位，也无对应查询码）。
- 结论：**不通过**。

### transform_to_parent

- 预期：旋转为 3×3 单位阵；平移行（第 4 行前三个数）≈ [25.4, 50.8, 76.2]（毫米归一化）。
- 实测原始矩阵：

```
[ [0.03937007874015748, 0, 0, 0],
  [0, 0.03937007874015748, 0, 0],
  [0, 0, 0.03937007874015748, 0],
  [1.0, 2.0, 3.0, 1.0] ]
```

- 实测平移行 = [1.0, 2.0, 3.0]（≠ [25.4, 50.8, 76.2]）；旋转对角 = 0.03937007874015748 ≈ 1/25.4（≠ 单位阵）。
- 结论：**不通过**（返回的 transform_to_parent 恰为「原始英寸矩阵」的形态：对角 1/25.4、平移 1/2/3 英寸）。

### transform_to_parent_raw

- 预期：平移行 ≈ [1.0, 2.0, 3.0]（原始矩阵）。
- 实测：**不存在 transform_to_parent_raw 字段**；原始矩阵语义疑似被并入 transform_to_parent（见上，实测平移恰为 [1.0,2.0,3.0]）。
- 结论：**不通过**。

### complete 与缺件标志

- complete=true、truncated=false、incomplete=false、total=1、next_cursor=null；**不存在 transform_unknown_reason / depth_limited / 缺件标志字段**。
- 返回自述 transform_convention："row-vector 4x4 ... translation occupies the last row; units follow the assembly (mm)"。
- 「complete=true」一项：**通过**；「无 transform_unknown_reason/depth_limited 标志」记为字段未实现，**不通过**。

## 步骤 3｜FEAT-006 收养拒绝逐特征诊断（通过）

调用：creo_adopt_current_model，输入 mode="inspect"；isError 未置位；返回 model_id=null、evidence_token=null（未进入 prepare/apply）。

- available：实测 false（预期 false）——通过。
- reason_code：实测 "unhealthy_features"（预期 unhealthy_features）——通过。
- reason 完整文本：实测 "The model has failed, suppressed or incomplete features"。
- refusal_details.unhealthy_features：unhealthy_total=1、returned=1、truncated=false（全部命中预期）——通过。
- items 逐字段：id=82（预期 82）、name="BLEND"（预期 "BLEND"）、type_name="protrusion"（预期 "protrusion"）、status_code=5 整数（预期整数 5）、status="suppressed"（预期 "suppressed"）、incomplete=false（预期 false）——全部通过。
- refusal_details.health_breakdown 原文："per-feature diagnosis from the native health scan: 1 unhealthy feature(s), 1 listed"（符合 per-feature diagnosis 口径）——通过。
- 辅助观察（不计入条目）：current_model.display_name="DB_8BDD03C9DA" 与当前窗口一致；healthy=false、millimeter_units=true、feature_count=16；inspection_ref sha256=eed904dd84fbc71a44b052ea00c09c9a45a35303fa07c9ac2bac2c7cfa9093eb；available_modes=[]。

## 步骤 4｜只读核验（通过）

- 第二次 creo_list_session_models：total=8，模型清单（名称、类型、origin、is_current、modified、session_model_id）与步骤 1 完全一致。
- session_fingerprint="2572692221204510968"，与步骤 1 相同。
- service_session_changes=[]（空）——通过。

## 总结

| 条目 | 结论 | 依据 |
|---|---|---|
| 前置核对 | 通过 | 装配、组件、当前窗口均在会话中 |
| 步骤 1 环境自报 | 通过 | name/version/tool_count 与清单记录如上 |
| BUG-080 length_unit | 不通过 | 字段不存在 |
| BUG-080 units.component/parent | 不通过 | 字段不存在 |
| BUG-080 transform_to_parent | 不通过 | 平移实测 [1.0,2.0,3.0]≠[25.4,50.8,76.2]；旋转对角 0.03937≠单位阵 |
| BUG-080 transform_to_parent_raw | 不通过 | 字段不存在 |
| BUG-080 complete | 通过 | complete=true |
| FEAT-006 拒绝诊断 | 通过 | 全部字段命中预期 |
| 步骤 4 只读核验 | 通过 | 清单/fingerprint 一致，service_session_changes 为空 |

**总评：BUG-080 装配变换单位契约未实现预期返回结构（单位字段与 raw 矩阵缺失，且 transform_to_parent 语义与预期相反）；FEAT-006 拒绝逐特征诊断完全符合预期；全程只读无副作用。**

未验证项：构建身份、Creo 版本、许可、内部实现机制等无法由 MCP 观察的项目一律记「未验证」。
