# 模型引用格式（BUG-006）

模型引用首先区分**几何对象**和**特征标签**，再区分单条引用与参数外层容器。`creo_capabilities.references` 保留原有示例键，新增 `syntax` 与 `by_tool`，应按具体工具和参数选用示例。工具列表中的 schema 和描述也给出轴、边、倒圆集合和草图支撑面的格式。

示例中的 ID 只说明 JSON 类型，实际值必须从当前模型巡检取得；几何 ID 和特征 ID 不能互换。标签必须是该模型已有的 MCP 别名。原生几何是否符合要求仍需实际解析、再生和保存重载验证。

## 轴阵列

`creo_axis_pattern.axis` 接受以下三种裸对象，不增加 `reference` 或 `edge` 包装：

```json
{"kind": "axis", "id": 83}
{"kind": "datum_axis_feature", "label": "t82_da1"}
{"kind": "datum_feature", "label": "t82_da1"}
```

第一种是几何轴 ID；第二种是明确的轴特征标签，推荐使用。第三种是为报告 §7-N1 增加的兼容写法：**仅在 axis_pattern.axis 中**按轴参数上下文转换为 datum_axis_feature。它不会把一个实际基准平面变成轴；标签指向的特征仍必须包含一根可解析的轴。

其它参数中的 datum_feature 继续代表基准平面。`{"kind":"datum_plane","axis":"z"}` 的 axis 表示平面法向，不能用作旋转轴。阵列轴必须先于 leader；必要时创建独立基准轴，再用 creo_reorder_features 调整顺序。高层工具和 execute_plan 使用同一规范化逻辑，非法轴类型、缺少 ID/标签会在入队前返回可操作示例，revision 防护保持有效。

## 显式平面几何 ID（BUG-084 / T03）

`datum_plane.id` 使用当前模型 `creo_inspect_model(section="datum_planes")` 返回的**基准平面几何 ID**；`plane.id` 使用当前模型中经验证为平面的几何 ID；`surface.id` 沿用面几何 ID，草图支撑面仍须确实平面。特征标签使用 `datum_feature`。特征 ID 与几何 ID 不互换，同一个数字也不能靠类型猜测重解释。

```json
{"kind":"datum_plane","id":163}
{"kind":"plane","id":163}
{"kind":"surface","id":163}
{"kind":"datum_feature","label":"right_plane"}
```

前三个 ID 只是格式示例，调用前须从**目标模型本次巡检**选取。显式 `plane`/`datum_plane` ID 与同一引用对象的 `axis`、`normal`、`offset` 互斥，连默认 `axis:"z"` 或 `offset:0` 同现也拒绝；不带 ID 时保留几何筛选模式。`creo_create_sketch.plane` 的字典把上述一个裸引用放在 `reference` 内，可另给 `origin`、`u_axis` 帧字段。支撑面缺失、非平面或不唯一时明确失败，不能回退默认 XY。结果 `operations[]` 的 `surface_id`、`origin`、`normal`、`u_axis`、`v_axis` 来自原生解析；`u_axis` 必须非零且在真实支撑面内有非零投影。无新 Toolkit 连接的离线验证不能替代这些几何数值的实机核验。

## 回转轴（revolve.axis，BUG-083）

`creo_revolve.axis` 与 execute_plan 的 `revolve` 操作 `axis` 字段接受以下两种裸对象，不增加 `reference`/`entity`/`edge` 包装：

```json
{"kind": "datum_axis_feature", "label": "axis_label"}
{"kind": "axis", "id": 83}
```

第一种引用同一模型中**先创建**的基准轴特征（例如先用 `datum_axis` 操作或 `creo_datum_axis` 创建，再回转引用其标签），推荐使用；第二种是模型巡检取得的几何轴 ID。axis_pattern 专用的 `datum_feature` 兼容别名不适用于回转。

**省略 axis 或显式传 null**：回转轴取草图自身的构造中心线，此时草图必须恰含一条 centerline（示例 [examples/turned_part.json](../examples/turned_part.json)）。**空对象 `{}`、缺 `kind` 的结构（如 `{"entity":"ax"}`）、非轴 kind、缺失 id/label 会在入口被拒绝**：错误信息含字段路径与上述可用示例，且不派发原生作业；`{"entity":"ax"}` 不会被静默猜测为外部轴。原生执行器对同类非法结构保留第二道边界防御，作业以结构化错误结束（含失败阶段与操作序号），不再透出 nlohmann JSON 异常文本。高层工具与 execute_plan 使用同一规范化逻辑，revision 防护保持有效；显式外部轴示例见 [examples/revolve_external_axis.json](../examples/revolve_external_axis.json)。

## 各工具的外层形状

| 工具 / 参数 | 完整形状或规则 |
| --- | --- |
| datum_plane.reference | 裸平面/面引用，如 `{"kind":"datum_plane","id":163}`、`{"kind":"datum_plane","axis":"z"}` 或 `{"kind":"datum_feature","label":"plane_label"}`；操作自身的 offset 与引用内部的筛选 offset 分开 |
| revolve.axis | 裸轴引用（`datum_axis_feature`+label 或 `axis`+id）；省略或 null 用草图构造中心线，空对象/缺 kind 在入口拒绝 |
| datum_axis.references | 裸引用数组，如两张基准平面；圆柱面、直边或现有轴需满足实际几何要求 |
| datum_csys / datum_points.reference | 裸坐标系引用，如 `{"kind":"default_csys"}`、几何 csys ID 或 datum_csys_feature 标签 |
| hole.placement/reference1/reference2 | 各自直接传入裸引用，placement 为放置面，reference1/2 为定位参考；平面定位参考可用 `datum_plane.id` 几何 ID |
| draft.surfaces/neutral_plane/pull_direction | surfaces 是裸面引用数组；neutral_plane 和 pull_direction 分别是裸单引用，neutral_plane 可用 `datum_plane.id` 几何 ID |
| boolean_bodies.targets/tools | 裸 body 引用数组，须明确不同 body ID；不能传特征 ID |
| solidify.reference | 裸平面/曲面参考，可用已验证平面的 `plane.id` 几何 ID；平面裁剪示例使用 mode=cut，quilt 分支按既有能力限制验收 |
| surface_fill.sketch | 草图特征标签或特征 ID（字符串或整数），无需 `{kind:...}` 对象 |
| thicken.reference | 裸 quilt 或 quilt_feature 引用 |
| sheetmetal_flange.edge | 裸 `{"kind":"edge","id":N}`；参数内部不再加 edge/reference 包装 |
| round/chamfer.references | **集合对象数组**：`[{"edge":{"kind":"edge","id":N}}]`，或 `[{"surfaces":[{"kind":"surface","id":A},{"kind":"surface","id":B}]}]`；裸边数组不等于集合数组 |
| round/chamfer 尺寸字段 | 独立工具 `creo_round.radius`、`creo_chamfer.distance` 与计划操作 `size` 是同一数值（mm）：round 计划也接受 `radius`、chamfer 计划也接受 `distance` 作为 `size` 别名；别名与 `size` 同现或用于另一种操作时明确拒绝。任务提交回显 `operations[].size`，终态 `result.operations[].size` 回显原生应用值（compact 返回同样保留） |
| create_sketch.plane | 主平面字符串 `XY/XZ/YZ`；字典形式为 `{"reference":{"kind":"datum_plane","id":N},"origin":[x,y,z],"u_axis":[x,y,z]}`，reference 也可取已验证平面 `plane`/`surface` 几何 ID 或 `datum_feature` 标签；origin/u_axis 可省略，reference 容器必需 |

这些集合和坐标包装承载不同的参数含义，不能简单地给所有裸引用增加同一层包装。此修复兼容报告中的轴标签、补齐引用契约，不更改原生执行器或创建额外几何。

实现与当前验收范围见 [BUG-006](work-items/BUG-006.md) 和 [本次证据](validation/BUG-006.md)。

## 圆角/倒角尺寸字段对照与部署核对（BUG-019）

三个入口的尺寸数值是同一个值（mm），只是入口字段名不同：独立工具 `creo_round.radius`、`creo_chamfer.distance` 在提交时转换为计划操作的 `size`；`creo_execute_plan` 的 round/chamfer 操作以 `size` 为主字段，并分别接受 `radius`/`distance` 作为 `size` 的别名（别名与 `size` 同现、或用于另一种操作时明确拒绝，不做静默优先）。别名自 0.3.7（DEV-042）起可用。

三个入口的等价请求示例（同一 3 mm 圆角）：

```json
// 独立工具 creo_round（参数名 radius）
{"model_id":"<id>","expected_revision":7,"label":"fillet","radius":3.0,
 "references":[{"edge":{"kind":"edge","id":9}}]}

// execute_plan 旧式（主字段 size）
{"model_id":"<id>","expected_revision":7,
 "operations":[{"op":"round","label":"fillet","size":3.0,
               "references":[{"edge":{"kind":"edge","id":9}}]}]}

// execute_plan 别名（round 的 radius，与上一条等价；chamfer 对应别名是 distance）
{"model_id":"<id>","expected_revision":7,
 "operations":[{"op":"round","label":"fillet","radius":3.0,
               "references":[{"edge":{"kind":"edge","id":9}}]}]}
```

无论入口如何，任务提交回显 `operations[].size`，终态 `result.operations[].size` 回显原生特征实际应用的值（compact 返回同样保留），可与调用输入直接对照。

部署核对方法（仅用公开 MCP 接口，不读源码）：

1. 用 `creo_capabilities`（或 `creo_check_update`）读当前部署的 `version`/`current_version`：低于 0.3.7 的部署没有计划别名，独立工具的 `radius`/`distance` 参数一直可用。
2. 在客户端 `tools/list` 或 `creo_capabilities` 的 tools 分节核对 schema：`creo_round` 输入为 `radius`（无 `size`），`creo_chamfer` 输入为 `distance`，`creo_execute_plan` 的 round/chamfer 操作含 `size` 与别名字段。
3. 实测一条最小请求：任一入口提交成功后，提交返回与终态均出现 `operations[].size` 且数值等于输入；给 round 同时传 `size` 与 `radius`（或给 round 传 `distance`）应被明确拒绝。

外部 0.3.1/0.3.4/0.3.5 的参数名差异反馈来自别名引入前的部署；在核对真实请求与受测部署身份之前，不把这些旧反馈计为当前实现的回归。

## 待核对的补充契约

[FEAT-008 首批任务](work-items/FEAT-008.md)跟进专用底板holes的客户端传输形状、对称拉伸depth口径与“查当前可编辑尺寸再修改”的闭环；[BUG-031](work-items/BUG-031.md)核对共面多候选/默认基准选择，结合字符串plane+offset产生构造特征的可见性说明。[履带反馈补录](validation/TRACK-FEEDBACK-2026-10-16.md)仅提供外部来源。上述是待核对工作，不是已新增字段或已变更接口；仍须按当前工具schema和真实返回使用，不把报告中的建议引用/参数当作已支持形式。
