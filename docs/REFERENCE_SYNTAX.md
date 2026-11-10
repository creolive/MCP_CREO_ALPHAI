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

## 平面 axis/normal 筛选器（匹配已有面，P05）

不带 ID 的平面引用是**已有面筛选器**，合法形状例如：

```json
{"kind": "plane", "axis": "z"}
{"kind": "plane", "normal": [0, 0, 1], "offset": 10}
```

语义是在**当前模型中**按法向（`axis` 是 `x/y/z` 的简写，`normal` 是任意非零 3D 向量）和偏置匹配一张已有的平面支撑面；候选不唯一或不存在时明确失败。它**不是**"按法向创建新基准面"的输入，服务也没有按法向建面的入口；需要新基准面时用 `creo_datum_plane`（其 `reference` 内部的筛选 offset 与操作自身的 offset 是分开的两个值）。缺 `kind` 的引用、未知标签在入口即拒绝，不透出 JSON 缺键异常。字典 offset 旧摘要（0.9.0 反馈 F4 S6）指的就是该筛选器的 `offset` 字段：它是匹配条件，不是新建偏移距离。

## 钣金展开固定面（fixed_surface，P05）

`sheetmetal_unbend`/`sheetmetal_flat_pattern`/`sheetmetal_bend_back` 的 `fixed_surface` 是一个**裸面引用**（与其他引用同一解析语义），如：

```json
{"kind": "surface", "id": 11}
```

它指定展开/折回过程中保持固定的几何；`references` 省略时作用于全部折弯。选中的几何能否真正固定由原生执行器判定，Python 侧不预判。

## 任意平面 coordinates 标注（FEAT-010 / T04）

`dimensioning="coordinates"` 与 auto 路由的坐标标注不再限于主平面字符串：字典平面（任意有效支撑面）同样创建完整坐标尺寸，编辑路径（`creo_update_sketch_geometry`）不再因非主平面法向拒绝或强制退回 autodim。坐标尺寸在**原生 section 局部坐标**中创建并回读核验；草图 U 轴与 section 轴成任意角度时，输入 u/v 分量按主导 section 轴命名（日志 `COORDINATE_AXES`），不再报 "requires principal section axes"。

- 创建、就地编辑与同几何快捷路径共用同一坐标变换（T03 实际帧 `origin/u_axis/v_axis`）与 1e-5 mm 回读门槛；不放宽阈值、不改输入坐标、不静默降级，核验失败如实报错并回滚。
- 中心线按**直线身份核验**：比较方向与两端点到目标无限线的偏移（日志 `COORDINATE_CENTERLINE_IDENTITY`），不依赖可能被求解器滑动的端点。轴平行中心线仍用基准投影线偏移尺寸固定；斜中心线不生成已知不稳定的端点尺寸（日志 `COORDINATE_CENTERLINE_SKEW`），仅靠核验兜底。
- 图元集合与互斥边界不变：line/centerline/rectangle/polyline/circle/arc；显式 dimensions/constraints 与 coordinates 仍互斥；ellipse/spline 仍走 autodim，本项不扩展。

## 坐标容差与旋转范围（BUG-108 / BUG-111，R13）

**`geometry_tolerance_mm` 的含义**：它是**验收放行阈值**（判定求解结果是否可接受），不是求解精度设置，也不会让内核"解得更好"。缺省时 `coordinates` 按 1e-5 mm 判定形状、autodim 按 1e-3 mm 只告警不拒绝。

**形状与平移分开判**：坐标求解会整体挪动整个截面（外部实测 1.6e-5 ~ 4e-3 mm），这不是形状改变。现在两处闸门（`SectionRegenerate` 的 `verify_coordinate_plan` 与 `CompleteFeature` 的 `enforce_geometry_deviation`）都按"去掉共模平移后的逐点残差"判定：

```json
{"geometry_deviation": {"max_deviation_mm": 0.000016, "shape_deviation_mm": 0.0,
                        "residual_mm": 0.0, "rigid": true,
                        "translation_mm": {"u": 0.000016, "v": 0.0},
                        "accepted_rigid": true},
 "sketch_shifted": {"detected": true, "rigid": true, "accepted_rigid": true,
                    "translation_mm": {"u": 0.000016, "v": 0.0}, "residual_mm": 0.0}}
```

- 可证刚体平移且平移量 ≤ **1e-2 mm** → 放行，`accepted_rigid=true`，日志 `GEOMETRY_DEVIATION_RIGID_ACCEPTED`；
- 刚体平移超过 1e-2 mm → 拒绝，错误里同时给平移量与该上限；
- **真实变形（残差 > 1e-5 mm）仍拒绝**，默认阈值没有放宽；显式 `geometry_tolerance_mm` 仍是收紧/放宽验收的唯一手段。

**`rotation` 范围**：`geometry_transform` 与 `set_geometry_transform` 的每个 `rotation` 分量必须落在 **-180..180 度**。超范围在提交前拒绝并给等价值，例如：

```json
{"error": "rotation[2]=225 deg is outside the supported range of -180..180 deg; use the equivalent -135 deg"}
```

两种原生后端统一归一为 `(-180, 180]`，因此 `-135` 与 `225` 指向同一旋转（旧实现把负角 `+360`，两者走了不同路径）。失败回执带 `failed_transform`（`backend`、`rotation_deg`、`rotation_normalized_deg`、`translation_mm`、`keep_original`、`reference_count`、`reference_kinds`）。

**`keep_original` 批量复制（BUG-111，0.11.7 定因口径）**：`keep_original` 复制的是**整个当前体**，副本累积在**同一个 body** 内（特征数 +1/副本，不新增 body）。追加副本能否成功取决于"既有副本集合 × 该角度"，**不是副本数量上限**：本机 Creo 12.4 四个独立模型（C2/C3/C5 与 C6 批 B）同型失败于 `operation_index=4`（`failed_stage=execute_geometry_transform`，消息 `Regeneration produced a failed, suppressed or incomplete feature`，前序 op `effect_status=rolled_back`），而把 −135 放在首位的 C4 五个副本**全部成功**、拆成 4+3 两批的 C6 仍在批 B 首个 op 失败。**"单批 ≤4 个副本、下一批重新引用当前 body"的变通建议已作废**（拆批实测无效）：把副本集放在同一计划里提交即可；需要"固定原件"的副本时应另建模型。失败回执的 `failed_transform` 给出 `backend`、`rotation_deg`/`rotation_normalized_deg`、`keep_original`、`reference_count`，并附有界 `selection` 块（`requested_body_ids`、`selected_surface_count`、`model_counts_at_start`：`features`/`surfaces`/`bodies`/`active_bodies`，取自 op 开始时的巡检，巡检未提供的项记 `null`）；`failed_operation_index` 与 `failed_transform.label` 指明是哪一步失败。Creo 10 报告方在 `ProFeatureWithoptionsCreate` 上拿到裸 `-1`，位置相同，**Creo 10/9 行为仍未验证**。

## 回转轴（revolve.axis，BUG-083）

`creo_revolve.axis` 与 execute_plan 的 `revolve` 操作 `axis` 字段接受以下两种裸对象，不增加 `reference`/`entity`/`edge` 包装：

```json
{"kind": "datum_axis_feature", "label": "axis_label"}
{"kind": "axis", "id": 83}
```

第一种引用同一模型中**先创建**的基准轴特征（例如先用 `datum_axis` 操作或 `creo_datum_axis` 创建，再回转引用其标签），推荐使用；第二种是模型巡检取得的几何轴 ID。axis_pattern 专用的 `datum_feature` 兼容别名不适用于回转。

**省略 axis 或显式传 null**：回转轴取草图自身的构造中心线，此时草图必须恰含一条 centerline（示例 [examples/turned_part.json](../examples/turned_part.json)）。**空对象 `{}`、缺 `kind` 的结构（如 `{"entity":"ax"}`）、非轴 kind、缺失 id/label 会在入口被拒绝**：错误信息含字段路径与上述可用示例，且不派发原生作业；`{"entity":"ax"}` 不会被静默猜测为外部轴。原生执行器对同类非法结构保留第二道边界防御，作业以结构化错误结束（含失败阶段与操作序号），不再透出 nlohmann JSON 异常文本。高层工具与 execute_plan 使用同一规范化逻辑，revision 防护保持有效；显式外部轴示例见 [examples/revolve_external_axis.json](../examples/revolve_external_axis.json)。

## 曲面链引用（surface trim / project curve / surface offset，FEAT-039 / DEV-069）

三个已发布曲面工具都只接受**裸引用对象**，不增加 `reference`/`entity` 包装。几何对象用几何 ID，特征标签用 `quilt_feature`；`quilt`、`curve` 等几何 kind 不接受 `label`。下面的 ID 仅为类型示例，实际值须从目标模型本次巡检取得。

```json
// creo_surface_trim：target 是 quilt；tool 是 quilt、基准面标签或曲线几何 ID
{"target": {"kind": "quilt", "id": 21},
 "tool": {"kind": "quilt_feature", "label": "trim_fill"},
 "keep_side": "one"}

// tool 也可以是基准面标签或曲线 ID（曲线修剪走 use-curve 变体）
{"target": {"kind": "quilt_feature", "label": "blade_quilt"},
 "tool": {"kind": "datum_plane", "label": "FRONT"},
 "keep_side": "two"}
{"target": {"kind": "quilt", "id": 21}, "tool": {"kind": "curve", "id": 41}, "keep_side": "one"}
```

`keep_side` 只有 `one`/`two`，表示保留哪一侧，不是 GUI 视图名。终态 `kept_side_basis` 报告实际依据：quilt 或基准面工具为 `side_reference="tool_plane_normal"`，曲线工具为 `"curve_direction"`（反向曲线会交换保留区域）；`tool_normal` 只在基准面工具上是真实向量。`target` 与 `tool` 必须不同，且只接受一个 tool。

```json
// creo_project_curve：一张 quilt、一条曲线几何 ID、一个能读出真实方向的方向引用
{"target": {"kind": "quilt", "id": 21},
 "source": {"kind": "curve", "id": 7},
 "direction_ref": {"kind": "datum_feature", "label": "TOP"},
 "side": "positive"}
```

`direction_ref` 接受 `datum_feature`/`datum_axis_feature` 标签，或直的 `{"kind":"curve","id":N}`。`side` 只翻转该方向，只有 `positive`/`negative`。投影按“源草图沿方向扫掠 + 官方相交曲线”构造，模型会多一个辅助曲面特征，其 ID 由 `helper_feature_id` 返回；方向须平行于源草图平面法向，目标须在请求一侧，源曲线须属于曲线特征。`source` 只接受 `curve` 几何 ID，**不接受** `edge` 或 `axis`；`direction_ref` **不接受** `{"kind":"datum_plane","label":...}`（该解析器会丢掉标签并取默认平面）或裸向量。

```json
// creo_surface_offset：源 quilt，沿曲面法向偏移
{"reference": {"kind": "quilt_feature", "label": "fill_label"},
 "distance": 5.0,
 "side": "positive"}
```

`creo_surface_offset` 的结果是会增加实体体积的**偏置壁**，不是独立偏置 quilt。`target_quilt_id` 指向源 quilt，不代表新产生、可供下游修剪或合并的 quilt。只有单一平面源、偏置前体积近零等计量条件满足时才以体积÷面积发布实测距离；其他情况实测距离为 null，原因见 `offset_distance_status`。`creo_thicken`/`creo_solidify` 保留各自从 quilt 生成实体的独立契约。`side` 只回显请求侧，几何 z 符号不回读。该工具用 `distance`，不吃 `offset_mm`；`surface_trim` 的 `offset_mm` 是另一条被门禁的薄修剪路线，当前拒绝文案为：

> surface_trim offset_mm is not published: the documented Thin tree (PRO_SURF_TRIM_THIN with PRO_E_THICKNESS/PRO_E_SRF_OFFS_METHOD) only removes a band of that thickness when the tool is a quilt, keeps both sides instead of the requested keep_side, and offset_side has no observable effect (2026-11-06 six direction variants all produced the same band; negative thickness fails regeneration)

**loft 的表面模式仍不可用**：`creo_loft` 只接受 `mode="add"`；`mode="surface"`、`cut` 与 `new_body=true` 都在入队前拒绝。没有 `creo_surface_loft` 工具，也没有 `surface_loft` 已注册操作；多截面放样/边界混合曲面仍未发布。

`extrude(mode="surface")`、`revolve(mode="surface")`（含局部角度）以及曲面特征上的 `axis_pattern` 已有 Creo 10 报告方实机正证据；它们不替代多截面放样或 quilt 合并。`creo_quilt_merge` 虽有公开工具签名，仍在提交前门禁，文档中的结果字段仅是待验契约。修剪结果 quilt 通过特征标签再次引用、弯曲 quilt 的偏置距离读回与保留侧的几何判据仍未闭环；需要从当前模型的 `inspect_model(section="quilts")` 获取实际几何 ID，不能把请求值当成实测值。

## 各工具的外层形状

| 工具 / 参数 | 完整形状或规则 |
| --- | --- |
| datum_plane.reference | 裸平面/面引用，如 `{"kind":"datum_plane","id":163}`、`{"kind":"datum_plane","axis":"z"}` 或 `{"kind":"datum_feature","label":"plane_label"}`；操作自身的 offset 与引用内部的筛选 offset 分开 |
| revolve.axis | 裸轴引用（`datum_axis_feature`+label 或 `axis`+id）；省略或 null 用草图构造中心线，空对象/缺 kind 在入口拒绝 |
| datum_axis.references | 裸引用数组，如两张基准平面；圆柱面、直边或现有轴需满足实际几何要求 |
| datum_csys / datum_points.reference | 裸坐标系引用，如 `{"kind":"default_csys"}`、几何 csys ID 或 datum_csys_feature 标签 |
| hole.placement/reference1/reference2 | 各自直接传入裸引用，placement 为放置面，reference1/2 为定位参考；平面定位参考可用 `datum_plane.id` 几何 ID |
| hole.standard | `{"series":"ISO","size":"M6","thread_depth":8}`：按安装孔表建螺纹孔。此时 `diameter` 可省略（给了必须等于表内名义直径），`depth` 必填，`thread_depth` 必须严格小于钻尖深度且不超表内上限；回执给 `thread_metadata` 与 `thread_metadata_verified`（只有创建后特征树回读一致才为 true），非标准孔回执不变 |
| draft.surfaces/neutral_plane/pull_direction | surfaces 是裸面引用数组；neutral_plane 和 pull_direction 分别是裸单引用，neutral_plane 可用 `datum_plane.id` 几何 ID |
| boolean_bodies.targets/tools | 裸 body 引用数组，须明确不同 body ID；不能传特征 ID。巡检可能返回负 body ID，但当前布尔入口不支持把负 ID 作为目标或工具；这不表示巡检记录无效。正 ID 也不保证能把独立实体并入钣金主体：报告方在 Creo 10 对钣金体与实体做双向 union 均遇到原生 `-1` 并回滚，当前未提供钣金体融合能力 |
| 钣金模型的 extrude/revolve add | 普通 `extrude(mode="add", thin=null, new_body=false)` 在建模前以 `SHEETMETAL_SOLID_ADD_UNSUPPORTED` 拒绝；`new_body=true` 创建的是独立实体，不保证能与钣金主体融合。`thin` 增料与 `revolve` 增料未被该准入规则阻断，但目标 body 与合并结果尚无可靠契约，不能据此视为钣金主体增料 |
| solidify.reference | 裸平面/曲面参考，可用已验证平面的 `plane.id` 几何 ID；平面裁剪示例使用 mode=cut，quilt 分支按既有能力限制验收 |
| surface_fill.sketch | 草图特征标签或特征 ID（字符串或整数），无需 `{kind:...}` 对象 |
| thicken.reference | 裸 quilt 或 quilt_feature 引用 |
| surface_trim.target/tool | target 一个 quilt；tool 一个 quilt、基准面标签或曲线几何 ID；`keep_side` 只用 `one`/`two`，实际依据见 `kept_side_basis`；`offset_mm` 仍拒绝 |
| project_curve.target/source/direction_ref | target 一个 quilt；source 只接受 `{"kind":"curve","id":N}`（不接受 edge/axis 或曲线标签）；direction_ref 接受 `datum_feature`/`datum_axis_feature` 标签或曲线 ID，不接受 `datum_plane` 标签或裸向量 |
| surface_offset.reference | 裸 quilt 或 quilt_feature 引用；距离字段是 `distance`，结果为会增加实体体积的偏置壁；源 quilt id 不是新结果 quilt，实测距离可用性见 offset_distance_status |
| sheetmetal_flange.edge | 裸引用（计划路径 `operations[i].edge`），两种形态：`{"kind":"edge","id":N}`，`id` 取当前 `creo_inspect_model` 的边 ID；或 `{"kind":"edge_geometry","endpoints_mm":[[x,y,z],[x,y,z]],"tolerance_mm":1e-6}`，用当前模型坐标毫米的两端点点名一条直线边，原生在执行每个 op 时重查当前几何、要求无向唯一匹配，因此计划可跨边 ID 重排。`tolerance_mm` 可省略（默认 1e-6，范围 1e-9..1000），不接受单位字段；0/多候选、非有限坐标、退化边或无法换算模型长度单位时明确拒绝。两种形态都不得再加 edge/reference 包装。首壁来源为 `native_planar` 时，报错只指向 `creo_sheetmetal_planar_wall` 的 frame/envelope；只有 `sheetmetal_wall` 转换首壁才引用 `wall_contract`；来源未知不给旧首壁配方 |
| sheetmetal_unbend/flat_pattern/bend_back.fixed_surface | 裸面引用，如 `{"kind":"surface","id":N}`，取自当前巡检；`references` 省略时作用全部折弯，能否固定由原生执行判定 |
| sheetmetal_flange.relief | 可选对象 `{type:"none"\|"rectangular", ends:"both"\|"side1"\|"side2", width:>0, depth:>=0}`；省略等于 `none`（两端保持 `PRO_BEND_RLF_NONE`）。宽深是**绝对模型单位**、不按板厚缩放；`rip`/`stretch`/`obround`/`param`、角部释放与边撕裂不支持。这是 **bend-end relief**，不是 corner relief 或斜接，当前未证明能解决角部重叠；传入它也不会跳过 `adjacent_bend_ends` 创建前拒绝。释放是创建期属性，改它要删除/抑制折边后重建，没有就地改释放的入口 |
| sheetmetal_flange.end_trim_mm | 可选正数（`>0`，上限 100000，布尔拒绝），模型单位；省略时元素树与旧行为逐字一致。**Creo 把它读作「距链端各内缩 setback」还是「自截面起算的壁长」尚未实机确认**，属诊断参数：先在自由壁上用实测体积分类再依赖修剪几何（开发分支未发布） |
| sheetmetal_flange.miter_cuts | 可选对象 `{width:>0, offset:>=0}`（模型单位，布尔拒绝；`offset` 省略时等于 `width`）。写入折边自身 `PRO_E_SMT_MTR_CUTS` 的 **BLIND（`PRO_DIM_ENTER`）数值**宽度/偏移，创建时由 Creo 切掉墙端与相邻折弯的重叠。**这是 `adjacent_bend_ends` 创建前拒绝的唯一放行方式**：不传 `miter_cuts` 的请求照旧被拒；传入后放行并回显 `miter_cuts` 与放行证据 `adjacent_bend_ends_allowed`。实测（2026-11-06）：GAP 型会被 Creo 重置为 PARAM 且值清 0，故改用 BLIND；四壁盒子四墙均建成并保存重载，但 1 mm 宽度/偏移在自由首壁探针上无可测体积变化，切角量尚未定标 |
| feature_state.action / targets | `action` ∈ `delete`/`suppress`/`resume`；`targets` 是特征标签或非负特征 ID 的数组，同一批目标必须互不相同。仅用于零件/钣金模型；装配组件走 `creo_remove_component` |
| component_placement.component / component_constraints 引用 | 组件**业务标签**（如 `part_alpha`）；标签是业务名不是身份，身份是模型身份 + feature_id，删除重插后旧标签不误指新组件 |
| round/chamfer.references | **集合对象数组**：`[{"edge":{"kind":"edge","id":N}}]`，或 `[{"surfaces":[{"kind":"surface","id":A},{"kind":"surface","id":B}]}]`；裸边数组不等于集合数组 |
| round/chamfer 尺寸字段 | 独立工具 `creo_round.radius`、`creo_chamfer.distance` 与计划操作 `size` 是同一数值（mm）：round 计划也接受 `radius`、chamfer 计划也接受 `distance` 作为 `size` 别名；别名与 `size` 同现或用于另一种操作时明确拒绝。任务提交回显 `operations[].size`，终态 `result.operations[].size` 回显原生应用值（compact 返回同样保留） |
| create_sketch.plane | 主平面字符串 `XY/XZ/YZ`；字典形式为 `{"reference":{"kind":"datum_plane","id":N},"origin":[x,y,z],"u_axis":[x,y,z]}`，reference 也可取已验证平面 `plane`/`surface` 几何 ID 或 `datum_feature` 标签；origin/u_axis 可省略，reference 容器必需 |

### 主平面 offset 与切除方向（DEV-081/F11）

`offset` 是 `plane_coordinate`：主平面在自身轴上的**全局坐标值，不是沿法向的位移**；`direction`（extrude/revolve）才是相对该法向的 `positive`/`negative`。

| plane | origin | normal | offset 所在的全局轴 |
| --- | --- | --- | --- |
| XY | `[0, 0, offset]` | `[0, 0, 1]` | Z |
| YZ | `[offset, 0, 0]` | `[1, 0, 0]` | X |
| XZ | `[0, offset, 0]` | `[0, -1, 0]` | Y（negative Y） |

XZ 的法向是 negative Y，因此 `direction="positive"` 会让实体向更小的 Y 增长；切料方向与草图全局位置必须同时核对。字典引用内部的 `offset`（平面筛选条件，见上文）与本表的 `plane_coordinate` 不是同一个字段。

这些集合和坐标包装承载不同的参数含义，不能简单地给所有裸引用增加同一层包装。此修复兼容报告中的轴标签、补齐引用契约，不更改原生执行器或创建额外几何。

实现与当前验收范围见 [BUG-006](work-items/BUG-006.md) 和 [本次证据](validation/BUG-006.md)。

## 选择性切除作用域（DEV-081/F08）

多实体零件的 `extrude` 切除可以只作用于一个实体：

| 字段 | 取值 |
| --- | --- |
| `scope.kind` | 只接受 `"bodies"` |
| `scope.body_ids` | 一个正整数实体 ID，取自 `creo_inspect_model` 的 `bodies[].id` |

省略 `scope` 时行为不变，切除对全部实体生效。以下组合在提交前拒绝，不产生作业：多个实体 ID、`kind` 不是 `bodies`、非 `cut` 模式、`depth_type="through_all"`、`new_body=true`、`revolve` 带 scope。

成功作业的该操作结果带 `scope_applied`：`requested_body_ids`、`applied_body_ids`（从创建后的特征树回读）、`source`、`query_code`、`non_target_bodies_unchanged`。`non_target_bodies_unchanged` 比较其余实体的面数与包围盒；任一侧查询无法完成时为 `null`，不会填 `true`。回读到的实体与请求不一致或特征中没有该选择时作业失败并回滚，错误码 `F08_SCOPE_RESOLVE_FAILED`；非目标实体发生变化时为 `F08_SCOPE_NON_TARGET_CHANGED`。

本机实机验收（Creo 12.4.0.0）：两实体零件只切 body 52，body 90 的面数与包围盒不变，总体积 39214.6018 mm³（40000 − 250π），保存重载通过。装配内切除、三个以上实体与回读不匹配路径尚未实机验证，见 [DEV-081](work-items/DEV-081.md)。

## 回转轴回显（revolve_axis）

`revolve` 操作结果带 `revolve_axis` 块（只增不改；旧作业与失败作业没有该块，不补）。字段与语义：

| 字段 | 含义 |
| --- | --- |
| `source` | `explicit`（请求显式轴）/ `internal_centerline`（省略或 null 轴）/ `unknown` |
| `kind` | `datum_axis`（无归属面的基准轴）/ `surface`（轴由几何面解析）/ `section_centerline`（草图内部中心线）/ `unknown`；按实测分类，不按请求文本 |
| `id` | 实际解析 id：基准轴/面轴为模型轴几何项 id（可用于 `{"kind":"axis","id":N}`），内部中心线为草图 section 实体 id；无法判定为 `null` |
| `origin` / `direction` | 只来自实际轴或 section 中心线查询；`frame="model"` 为模型坐标 3 元，`frame="sketch_local"` 为草图 (u,v) 2 元；未知为 `null`，**不回填请求值** |
| `frame` | `model` / `sketch_local` / `null`；实测优先 `model`（能取回转特征自身轴时），`sketch_local` 只是回退 |
| `length_unit` | 与基准轴同形的真实单位查询块（`name`/`query_code`/`scale_to_mm`…），失败为 `null` + 原码 |
| `geometry_known` | 严格布尔；仅当 frame 合法且 origin/direction 都是实测有效向量时为 `true` |
| `query_code` / `resolution` | 产出几何值的查询码与辅助证据（`feature_axis_query_code`、`axis_item_query_code`、`axis_surface_query_code`、`section_centerline_count`、`section_query_code`） |
| `section_centerline_count` | 实测**用户中心线**根数。2026-10-30 修正计数口径：草图构建器必写的两条系统投影参考不再计入（此前一条用户线被计成 3），修复后一条用户线计 1 并给出 id；真实多中心线仍保留 `id=null`，不武断选第一条 |

开发分支的该修正**尚未实机验收**；服务准入仍限一条草图中心线，因此「真实多用户中心线」夹具无法经本服务构造，需外部手工草绘模型。详见 [T09B 验收卡](development/DEV051-T09B-ACCEPTANCE.md)。

## 组件身份查询（list_components）

`creo_list_components` 与 `creo_inspect_model` 的 components 节在组件记录上投影业务身份：每条带 `identity`（模型身份 + feature_id，即关联键本身）、`labels`、`label`（恰好一个绑定时为该值，否则 `null`）、`label_state`（`single`/`multi`/`unlabeled`）、`source_model_id`/`source_revision`（多标签或无绑定时为 `null`，不任选一个冒充）、`bindings`（每个绑定一条）。顶层另返回 `deleted_identities`（旧 feature_id 不在当前组件集时单独列出，绝不并入当前记录）与 `identity_key`。

label 永远不是身份：同名 label 可以存在于不同模型，删除重插后 label 不变但 feature_id 换新，因此求交只在同一模型身份内按 feature_id 进行。物理副本名 `c_<job>_<n>` 是原生身份，不做改写。保存重载后关联与删除重插不误指的开发分支回归**尚未实机复验**。

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


## 产品规则只读规划（FEAT-063，开发分支未发布）

`creo_plan_product_variant(template_id="box_frame", parameters={})` 使用 READ 注解。
参数仅 length_mm/width_mm/height_mm/wall_mm，默认 100/60/40/2 mm；前三项范围
[10,1000]，壁厚 [0.5,20]，内腔每向至少 1 mm。拒绝 bool、字符串、非有限数、
未知字段和模板路径。服务从当前启用操作构造快照，不接受调用方能力声明。
返回 plan.operations、解析 expected_geometry 和 blocking_items；缺 sketch/extrude 时
executable=false、plan=null。完整 JSON 上限 32768 UTF-8 字节，超限拒绝而不截断。
executable 仅表示静态能力/schema 准入；native/saved_reload 恒为 not_run。
无连接、提交、job_id/model_id/revision；原生模板未验。详见 [产品规则](PRODUCT_RULES.md)。

## 2026-11-07 DEV-074 离线回执增量（开发分支）

- 平面钣金壁 `thickness_verified_effective` 与 resize 的 `thickness_loaded_verified_effective` 来自有来源、上下文正确且与请求厚度一致的验证块；缺块/缺请求尺寸为 null。旧 `thickness_verified` 等字段保留原生 API 读数语义。
- resize 缺少前后任一 feature ID 时，`feature_id_unchanged=null`；失败且未取得 ID 的 loaded 验证/来源字段显式 null。
- 几何选边零匹配的失败操作携带 `edge_geometry_diagnostic`，包含 `nearest_edges`（最多5项：`id`、`endpoints_mm`、`endpoint_errors_mm`）、`tolerance_mm`、`candidate_limit` 与 `straight_edge_count`。这些是诊断候选，不会自动吸附或放宽严格匹配；compact 保留该结构。
- `preview.status=skipped_no_geometry` 时 `path/bytes=null`，`empty_geometry_basis` 透传 `feature_visit_code` 与 `non_datum_feature_count`；未测或查询失败的计数为 null。
- startup `state/connected` 保持上次观测语义；`connection_verification=unverified_stale_snapshot` 与 `current_connected=null` 表示快照已过期，message 明确提示未验证。状态读取不会探测 Toolkit。
- 更新快照 `in_flight` 明示正在检查；`last_completed_status` 保留上次完成状态（未检查为null），与 `from_cache/stale` 分别解读。
- `native_progress.connect_timing` 保存日志头部连接阶段证据；尾部当前阶段没有时间则不填 `idle_seconds`，不能把早期连接时间归给回滚或其它阶段。

这些增量已作离线回归与原生编译；新原生字段的真实MCP/Creo/保存重载验证仍见[接手清单](development/DEV-074-HANDOFF.md)。
