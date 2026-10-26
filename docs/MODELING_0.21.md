# 0.21 新增建模操作

先查看 [COVERAGE_0.21.md](COVERAGE_0.21.md) 和 `creo_capabilities`。以下工作流使用启用的功能；放样保留接口当前不可用。

## 镜像、扫掠、拔模、钣金首壁

将 `examples/mirror.json`、`sweep.json`、`draft.json` 或 `sheetmetal_wall.json` 的 JSON 对象传给 `creo_execute_plan`。只提交一次，轮询返回的 `job_id`。

镜像示例保留两个 10 × 10 × 5 mm 实体，体积总计 1000 mm³。扫掠示例使用 40 mm 直线轨迹和 Ø4 mm 截面；截面坐标为轨迹起点的局部坐标。改变截面直径时调用：

```json
{
  "model_id":"用成功结果中的 model_id 替换",
  "expected_revision":1,
  "sketch":"pipe",
  "values":{"diameter":6}
}
```

上述对象传给 `creo_set_sketch_dimensions`。`expected_revision` 必须换成该模型实际最新版本，不能固定复用示例中的 `1`。Ø6 × 40 mm 的扫掠体积约为 1130.973355 mm³。

钣金首壁示例的草图在 XY 面，为沿 X 的 40 mm 直线，沿 +Z 延伸 30 mm，厚度 1 mm 位于 Y 方向。树保留独立驱动草图、薄壁拉伸和原生钣金转换。`creo_new_sheetmetal` 初始创建用于钣金建模的毫米零件，实际模型类型在首壁转换后才成为原生钣金。不要对旧版使用空钣金模板创建的测试模型继续附着法兰。

## 钣金法兰与展开

1. 执行 `examples/sheetmetal_wall.json`，等待保存重载成功。读取 `inspection.edges` 和 `inspection.surfaces`；选择首壁绿色面（`sheetmetal_type:2`）与侧面的公共直边。实测案例选择 Z=0、沿 X 的 40 mm 边。
2. 调用 `creo_sheetmetal_flange`，传最新版本、`label:"flange"`、`edge:{"kind":"edge","id":实际边ID}`、`height:15`、`angle:90`、`radius:2`、`y_factor:0.5`。返回的弯曲面半径为 2 和 3 mm。高度指局部截面线长，由 Creo 弯曲规则确定最终外包尺寸。
3. 用 `creo_set_sketch_dimensions`，`sketch:"flange", values:{"height":20}` 编辑高度。40 mm 宽、1 mm 厚的案例增加体积 200 mm³。
4. 再查询首壁绿色平面面 ID，作为 `fixed_surface:{"kind":"surface","id":实际面ID}` 调用 `creo_sheetmetal_unbend`；不传 `references` 时展开全部弯曲。
5. 在展开模型上调用 `creo_sheetmetal_bend_back`，同样使用固定面和最新版本。恢复后可调用 `creo_sheetmetal_flat_pattern` 创建平展特征。每步完成后检查原生保存重载结果，并重新查询拓扑引用。

展开长度由 Y 因子决定，展开体积与弯曲实体体积可以不同。当前实测为单个 90° 法兰及全部弯曲展开/恢复；选择部分弯曲、多法兰、其他角度与方向组合仍需验证。

## 装配组件快照

1. 用 `creo_execute_plan` 创建并保存一个源零件，记录其 `model_id`。源模型须为 `ready`，没有待完成任务。
2. 调用 `creo_new_assembly`，轮询完成，记录装配 `model_id` 和 `revision`。
3. 调用 `creo_assemble_component`，传入装配的 `model_id`、最新 `expected_revision`、标签如 `first`、源零件的 `source_model_id`。默认在原点固定放置。
4. 插入第二个组件时，可传 `translation:[25,0,0]`、`rotation:[0,0,90]`。顺序为先绕 X、Y、Z，再应用平移。

创建与 `creo_component_placement` 更新放置（也适用于 `creo_execute_plan` 对应
operation）可改用唯一嵌套 3×3 `rotation_matrix`，例如：

```json
{"rotation_matrix": [[0,0,-1],[0,1,0],[1,0,0]], "translation": [25,0,0]}
```

这是右手主动旋转的行向量、局部到父级映射：
`p_parent_mm = p_local_mm * rotation_matrix + translation_mm`。例如上面的矩阵
使局部 +X 映到父级 −Z，+Y 映到 +Y，+Z 映到 +X；它与旧 Euler `[0,90,0]`
相同。旧 Euler 保持先绕固定 X、Y、Z 的语义，查询矩阵按行向量存储，不翻转角度。
4×4 查询矩阵的姿态是左上 3×3、平移是末行前三项；重用时读取 BUG-080 的
已知毫米正规化结果，勿直接使用单位未知或带单位缩放的 raw 矩阵。

矩阵与显式 `rotation` 互斥（即使 Euler 是 `[0,0,0]`）；公开工具省略或传
`rotation: null` 均视为未提供。只接受嵌套 3×3，拒绝平铺九元素、布尔和字符串。
每个数必须有限，行向量内积与单位阵元素之差、行列式与 +1 之差均不能超过
`1e-6`；反射、缩放及超容差输入拒绝，容差内按原值使用，不转置、不修正。
平移独立为 XYZ 毫米。组件创建仍是源件 revision 的快照，源件修改不会自动更新，
嵌套插入仍不支持。此新增矩阵管线已做离线校验；实际 Creo 放置、revision 和
保存重载及 WorkBuddy 结果本次未验证，见 [FEAT-012](work-items/FEAT-012.md)。
5. 用 `creo_list_components` 查看最近已验证的装配快照；人工改动后用 `creo_refresh_model` 查看实况。
6. 用 `creo_component_placement` 和 `component:"second"` 改变位置。此操作会替换原约束为固定定位。用 `creo_remove_component` 删除这个装配副本。

插入使用源模型的版本副本。`aliases` 中记录 `source_model_id`、`source_revision` 和 `source_snapshot:true`。源零件后续改变不会更新已插入的副本，源零件也不会被装配备份移到另一加载路径。子装配来源当前被拒绝。

## 原生装配约束

`placement:"constraints"` 时必须提供 `constraints`。以下约束将组件的三个主基准面和装配的相应主基准面对齐：

```json
[
  {"type":"align","assembly_reference":{"kind":"datum_plane","axis":"x"},"component_reference":{"kind":"datum_plane","axis":"x"}},
  {"type":"align","assembly_reference":{"kind":"datum_plane","axis":"y"},"component_reference":{"kind":"datum_plane","axis":"y"}},
  {"type":"align","assembly_reference":{"kind":"datum_plane","axis":"z"},"component_reference":{"kind":"datum_plane","axis":"z"}}
]
```

将第一项改为 `type:"align_offset", offset:20` 可产生 20 mm 的原生约束偏置。实际正负方向由选中基准面的方向及 `assembly_side`、`component_side` 决定，应查询返回的变换矩阵。

`component_reference` 可使用源组件快照内的数值几何 ID，或 `{"kind":"datum_feature","label":"源零件的基准标签"}`。组件引用使用组件自身标签表，装配引用使用装配标签表。

已验证三平面对齐和对齐偏置。`mate`、`mate_offset`、`insert`、`csys` 的参数分支尚需进一步实机验证；涉及圆柱轴和坐标系时先查询实际引用 ID。

## 失败与版本

创建或修改成功必须同时满足 `status:"succeeded"` 和 `saved_file_reloaded_and_verified:true`。实时查询不保存模型，也不会将人工修改接受为新的保存基线。

原生任务失败后的 `rollback_succeeded:true` 表示已从修改前的文件恢复、再生并核对基线。无法确认执行结果时保留 `unknown_outcome`，不可盲目重复提交。禁用功能会在任务入队前返回错误，既不会产生新任务，也不会修改 Creo 模型。
