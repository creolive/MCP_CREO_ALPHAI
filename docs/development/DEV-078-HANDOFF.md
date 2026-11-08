# DEV-078 离线实现与后续实机交接

日期：2026-11-08。分支 `codex/DEV-078-modeling-offline`；基点 `v0.19.0` / `86020e7`。离线开发与验收目录 `E:\Projects\MCP_CREO_MechDog-d074`。主工作区的 DEV-076/077、DEV-054、`.trae/` 等改动未带入本分支。

本轮仅离线开发。新操作没有独立 MCP 工具；所有候选仍由 `require_available` 在取得通道前拒绝，公开工具保持 107。单测、源码拓扑算法和 SDK 编译均不能证明真实几何可用。

## 交付对应关系

| 前次建议 | 本轮实际内容 | 下一步所缺 |
| --- | --- | --- |
| 非平面 fill | `surface_boundary_fill` 改为恰好四边、两方向对边 `[0,2]` / `[3,1]`、`ADD_CLOSED=false`；真实端点闭合/方向校验 | 内核再生、真实 quilt/面积/边界、后续加厚、保存重载及失败回滚 |
| 标准 quilt Offset | `reference_route("standard_quilt_offset")` 与 `udf_placement_recipe`；成功参照件 dump/UDF 准备和曲面距离验收条件 | 真实标准 Offset 成功件、其元素树或 `.gph`；本轮没有新建标准 Offset 原生树 |
| Hem / 边缘 joggle | `sheetmetal_flange_profile`：2–32 个 line/arc 的严格开放截面；复用原 flange 树/guard；只支持实际 mm 模型 | 原生 hem/joggle 成形、板厚、展开、编辑与重载；板中部 jog 不在该截面路线内 |
| Corner relief | `sheetmetal_corner_relief`：独立三面引用矩形角部释放，formed/unbent | 真实 rip 和相交折弯前提、去料与展开几何；不保证救活原第三壁 |
| 百叶 / 冲压凸包 | `sheetmetal_quilt_form`：quilt punch 特征；另准备 Punch/Die 工具件的 UDF 路线 | quilt form 与工具件各自的真实成形、钣金身份/厚度与 flatten/unflatten；没有离线生成冲头/凹模或假 UDF |
| 格栅孔 | `grille_cut_recipe()` 与 3×3 变体：native_planar 100×60×1，XY z=0.5 的 6×4 矩形、对称 through_all cut | 同条件复现 −24 / −216 mm³、真实孔、板体/厚度与重载；旧失败根因仍未定 |

## 候选输入

以下仅供开发者准备未来实机夹具，当前公开 MCP 会拒绝前三项及 fill，不提供运行开关。

```json
[
  {"op":"sheetmetal_corner_relief","label":"corner_probe","flat":{"kind":"surface","id":12},"bends":[{"kind":"surface","id":20},{"kind":"surface","id":21}],"width":1,"depth":1,"state":"formed"},
  {"op":"sheetmetal_quilt_form","label":"form_probe","quilt":{"kind":"quilt","id":82},"side":"face","material_side":"outside","keep_quilt":true,"trim_sides":false},
  {"op":"sheetmetal_flange_profile","label":"profile_probe","edge":{"kind":"edge","id":31},"profile":{"entities":[{"type":"line","name":"leg1","start":[0,0],"end":[10,0]},{"type":"line","name":"leg2","start":[10,0],"end":[10,5]}]},"radius":1}
]
```

ID 必须替换为真实模型查询结果。角部三面须互异；平面和圆柱面类型、当前模型及唯一真实材料钣金体由原生检查，不能用声明 `rip=true` 代替几何前提。native_planar 的空模板体不作为目标；存在多个材料钣金体时拒绝歧义，读取实际目标体的板厚并显式选中该体，不使用零件级厚度或空默认体。角释放尺寸按查询到的模型单位转换；未知单位拒绝。非 mm 运行没有验收。

多段截面不接受 height/angle；旧 `sheetmetal_flange` 不接受 profile。内部 `request_derived_guard_extent_mm` 仅用于原有守卫，不能解释为实际壁高。截面解析相交而非离散采样；同圆圆弧对暂全部拒绝，连续性容差为 1e-8 mm，坐标有限且不接受 bool。

四边 fill 按周界邻接顺序提交，但曲线原生参数方向必须已对齐两组对边。例：四条线端点分别为 A→B、B→C、D→C、A→D，提交顺序仍为第一、第二、第三、第四条；A/B/C/D 可以非共面。原生枚举 16 种端点方向判断闭合和配对，需要参数反转时在建树前明确拒绝，未猜造 SDK 反向指令。复合链、N 边、孔、多环及 G1/G2 仍不支持；该端点算法不证明整条曲线无自交。

## 离线使用与标准 Offset / 工具件准备

```powershell
.\.venv\Scripts\python.exe tools/test_modeling_alternatives.py
```

仅写 `build/dev078_offline_recipes.json`，没有 `--live`，不会调用 MCP 或 Toolkit。单孔/九孔是待执行计划；解析体积在 `oracle`，明确为期望值而非测量值。必须先完成输出中 `creo_new_sheetmetal(template="native_planar")`，再向返回的 model_id 追加对应计划。

标准 Offset 与 Punch/Die 没有实物参照时返回 `pending_reference` 和空 operations。取得合法真实 `.gph` 后，可用包内 `udf_placement_recipe` 准备现有 `udf_create`，但必须先通过 `creo_inspect_udf` 获取精确提示名、引用类型和可变尺寸；此函数不检查文件存在或可加载，不声称 UDF 放置成功。工具件来源、放置坐标系和外部引用仍需独立取证。

标准 Offset 优先测试曲面，例如向外 R8 球面偏置 2 mm 后 R10；源 quilt 保持、结果独立、沿源法向距离 2 mm 且无实体。Automatic/Controlled Fit、复制平移和偏置壁不能冒充这个验收。

成形与可展折弯分别验收。普通 unbend 不保证消除冲压特征；需验证原生 form flatten/unflatten 行为。实心增厚凸台或焊接铰链仍不是本卡已实现的附着增料能力；同板耳片可在另一个具体几何夹具上走坯料/切口/折弯，不凭本次代码宣称交付。

## 后续运行边界

后续实机工作须另行确认可操作会话并遵守 BUG-001 恢复记录；本轮未获取新的实机授权或连接。取证要记录 job/model、源码身份、dirty、原始错误、实际几何、保存重载及回滚。已有 0.19.0 的负证据保留原样；新的候选不能覆盖旧证据或把单测通过写成几何通过。Creo 9/10、非 mm、WorkBuddy 仍未验证。

最终冻结源码：3031 项单测、0 失败、0 错误；增量语言检查与 SDK12.4 编译通过。详见 [离线验收记录](../validation/dev078-offline-2026-11-08/EVIDENCE.md) 与 [工作卡](../work-items/DEV-078.md)。
