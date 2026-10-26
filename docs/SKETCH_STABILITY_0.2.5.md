# 大坐标和复杂草图尺寸策略

`creo_create_sketch`、计划中的 `sketch` 和 `creo_update_sketch_geometry` 接受 `dimensioning`：

| 值 | 行为 |
| --- | --- |
| `auto`（默认） | 主平面上没有显式尺寸/约束、只含支持实体时，展开后至少十个实体或任意坐标/半径超过 1000 mm，使用坐标尺寸；其他轮廓使用原生自动标注。 |
| `coordinates` | 明确使用坐标尺寸；限 XY/XZ/YZ 的直线、中心线、矩形、多段线、圆和圆弧，不与显式尺寸/约束混用。 |
| `autodim` | 使用 Creo 原有自动尺寸流程，可与调用者指定尺寸和约束组合。 |

坐标模式为直线端点和圆弧/圆的中心、半径提供原生尺寸；轴对齐直线共用重复坐标。圆弧极角用度。求解已完成时不再自动标注；需要处理剩余自由度时仍使用 Creo 求解器。首次求解冲突时仅排除与完整尺寸重复的推断相切/共线关系，再求解；没有调用刚性求解，没有改变零件单位，也没有缩放输入后再放大。

在写入特征前和写入后各读取实际截面实体，核对端点、圆心、半径及圆弧端点角度。位置差异超过 **0.00001 mm** 时任务失败并进入受管模型的回滚流程。该阈值用于创建/整体几何替换；随后用户主动改尺寸会改变轮廓，另通过再生、检查和保存重载验证。

生成的尺寸名称形如 `coord_edge_start_x`、`coord_edge_end_y`、`coord_arc_radius`、`coord_arc_start_angle`。它们是原生非负距离或角度，符号、起止方向及原生截面轴由 Creo 表达；修改前从 `creo_inspect_model` 的 `aliases.dimension_ids` 与特征尺寸表取得实际 ID/值，不把原始有符号坐标直接当作距离尺寸值。轴对齐直线可能没有重复的终点坐标尺寸。

整体替换草图会保持草图特征和命名实体 ID，清除原有尺寸/约束并重新生成所选模式的尺寸。替换后重新查询尺寸 ID；它们不保证与替换前相同。下游拉伸/混合通过再生保留原生特征。

验收包括原报告的 19 段闭合轮廓、R40000 的 12 边形、30000×10000 的半圆端槽形、旋转并平移到 XZ 的同类轮廓、YZ 的大圆及显式坐标模式矩形。验收条件为原生草图/实体特征 ID 保留、尺寸修改、实体 STL 边界核对和保存擦除重载；大多段线及轴对齐圆弧另外验证整体几何修改、故意错误断言回滚及恢复模型的实查。最终结果见 [本轮证据](validation_increment_025.json)。

实体边界的 STL 核对容差为 0.15 mm，包含导出离散/文本精度；不能用它代替截面实体的 0.00001 mm 写入核对。大圆弧体积断言采用 1e-8 相对容差，直线轮廓至少允许 1 mm³ 的浮点计算差异。

曲面任意方向草图、样条和椭圆仍使用原有自动尺寸流程。坐标模式不承诺每种相切、多环、相交或极端比例都可求解；提交不可闭合轮廓作为实体 Blend 截面会提前拒绝。开放曲线可以用于扫掠轨迹或曲面，不强制当作实体截面。

复现六类公开 MCP 验收：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_sketch_stability.py
```

这会创建独立测试模型并修改原生参数，结果与任务日志写入 `build/sketch_stability_integration.json`。需要续查已提交任务时加 `--resume`；新测试用不同 `--output`。超时或未知结果先检查原任务，不重复提交。19 段的输入实体保存在 `examples/sketch_stability_large_profile.json`，它是此测试读取的实体列表，不能直接作为建模计划参数。

## 2026-10-18 增补（BUG-050 / BUG-068 修复后的坐标模式与约束行为）

- **相邻段共享顶点只标注一次**：多段线/矩形展开后，同一物理顶点（容差 1e-9，与截面 epsilon 一致）的首个命名尺寸保留，后续相邻段的重复端点尺寸跳过（日志 `COORDINATE_SHARED_VERTEX_SKIPPED`）。此前同顶点会被两段各标一次，形成冗余约束。
- **构造中心线按无限轴处理**：坐标模式不再给轴平行构造中心线的端点打坐标尺寸——Creo 求解器会沿轴滑动其端点且不理会这类尺寸。非零偏置时改与投影基准线打一根位置尺寸（命名 `coord_<name>_offset`，`PRO_TK_DIM_LINE_LINE`）；偏置≈0（在基准轴上）不生成尺寸。斜中心线暂不在此范围。
- **截面回读对中心线只核对垂直位置轴**：沿轴端点坐标不参与 0.00001 mm 偏差判定（无限轴语义）；成形实体、圆/弧、半径与角度的核对和阈值不变。新增逐实体偏差日志 `COORDINATE_DEVIATION` 便于定位漂移来源。
- **约束引用改为实体上的真实参考点**（BUG-068）：`coincident` 等约束的 whole/start/end/center 引用按实体几何计算参考点（线端点/中点、圆与弧的圆心或圆上点），不再使用固定原点——弧圆心与截面原点重合时旧实现会因方位角退化返回 -2。
- 公开回归扩至 8 用例：新增 `bug068_coincident`（弧圆心在原点 + coincident + 拉伸体积断言）与 `bug050_centerline_coordinates`（31 点折线 + 构造中心线 + 坐标模式）。证据见 [BUG-068/BUG-050 记录](validation/BUG-068-BUG-050-repro-2026-10-18.md)。

## 2026-10-26 增补（BUG-082：就地编辑的 autodim 升级路由）

- **`creo_update_sketch_geometry` 的 `auto` 与 `autodim` 在主平面同样升级坐标尺寸**：此前仅 `auto` 编辑在主平面、实体类型受支持且截面含坐标系时改用完全约束的坐标尺寸（BUG-079）。BUG-082 根因实证后（见 [根因记录](development/BUG082-AUTODIM-ROOT-CAUSE.md)），原生 `ProSectionAutodim` 在重建截面上仅生成 0–1 个尺寸，截面级再生容忍该欠约束方案，但 `ProFeatureWithoptionsRedefine` 后的特征级再生从尺寸方案重解失败（`REV_SK` 与下游回转均 `PRO_FEAT_UNREGENERATED`，特征尺寸值被清零）；创建路径不受影响，因为新特征初次构建直接采用截面实体几何。显式 `autodim` 编辑现与 `auto` 走同一升级路由。
- **非静默**：升级记录在响应的 `solver` 信息中（`requested="autodim"`、`used="coordinates"`），模型 aliases 的 `last_dimensioning` 仍保留请求值；不升级时（非主平面或实体类型不受支持）保持 autodim，编辑失败按既有保护回滚。
- **`coordinates` 语义不变**；显式 `coordinates` 在非主平面依旧被拒绝。创建路径（`creo_create_sketch`、计划 `sketch`）的 dimensioning 选择不变。
- 公开回归：编辑专项新增/改造用例 `onaxis_sector_auto_to_autodim_edit`（外部报告组合，修复后成功）、`onaxis_sector_autodim_edit`（autodim 创建→四次 autodim 编辑）、`onaxis_sector_auto_edit`（auto 组合）与 `onaxis_sector_open_profile_failure`（开环剖面非法几何：失败、回滚与 `failed_features` 诊断，不再依赖保留本缺陷制造失败）。
