# 普通放样：原生混合种子复用

**v0.2.5 当前流程**：源码附带九个 MIT 种子（2/3/4/6 直线和平滑，5 平滑）；安装器自动注册，调用 `creo_new_loft_part` 可省略 `seed_file` 和 `seed_feature_id`，按数量/模式匹配。以下显式路径流程仍兼容，手工新建种子用于其他数量；当前能力见 [RELEASE_NOTES_0.2.5.md](RELEASE_NOTES_0.2.5.md)。

`creo_new_loft_part` 复制保存的专用 PRT 种子，创建独立的新零件，保留可编辑的原生 **Blend / 混合**。从 **0.2.4** 起接收 **2～20 张** Z 偏移严格递增的 XY 草图，数量和 `straight` / `smooth` 模式必须与种子匹配。多截面步骤及验证见 [MULTISECTION_BLEND.md](MULTISECTION_BLEND.md)。

执行器创建全新的参数草图，将复制出的混合参照改接到新草图，并删除旧截面草图；支持草图整体及完整复合曲线参照。源文件不修改，会话中未保存内容不参与复制。必须使用毫米制、单实体、独立外部草图的专用简单种子，端点设置、参数、关系和基准可能继承。

2026-10-10 修复：按指定 `.prt.N` 的快照字节生成唯一临时模型，读取参照和模式前显示并真正激活目标模型，复用当前或基础窗口；保存重载后也执行相同检查。单独调用 `ProWindowCurrentSet` 不会切换活动模型；此行为见 [PTC 窗口接口说明](https://support.ptc.com/help/creo_toolkit/protoolkit_plus/korean/creo_toolkit/api/dita/6316.html)。无需手动打开种子，启动 Creo 后应先结束草图编辑、特征编辑等模态命令。

`dimensions` 是可选列表。矩形与种子实体边重合时，旧实现的自动求解可能让新草图反向引用种子混合，进而在 `ReorderSeedBlend` 失败。修复版在创建截面期间暂时抑制**新副本中的种子混合**，完成后恢复，并检查新截面没有依赖旧混合或旧截面；源种子不受影响。希望用 `width`、`height` 等名字修改参数时，仍建议提供命名尺寸；省略时可通过检查结果取得 Creo 自动尺寸的原生 ID，或修改截面平面的偏移尺寸。

## 来源与兼容性口径（2026-10-25，FEAT-030 / BUG-034）

**兼容口径（逐字引用）**：外部 Creo 9 已报告受测种子 -16；另有 Creo 10 三截面成功历史；当前会话/其他种子未验证。

- 本文其余章节与 [SEED_LIBRARY.md](SEED_LIBRARY.md) 的历史验收段落保留其原环境与日期，不作为当前兼容结论。
- 种子清单中的 `available` 只表示文件字节与 SHA256 有效；`creo_list_seeds` / `creo_validate_seed` 不建立 Toolkit 连接、不隐式试载，不代表当前 Creo 会话能加载该种子。
- `seed_build_version` 只来自与该种子实际 SHA256 绑定的可追溯生成记录或可靠原生证据；否则保持 null。UGC 头中的版本数值只是诊断线索，不映射为产品版本。
- 放样或翼型加载失败时，诊断保留原始 API（`ProMdlFiletypeLoad`）、错误码、实际阶段、种子标识与 SHA256、可取得的运行版本，并提示核对兼容性与来源。只有存在绑定该 SHA256 的来源记录且其 release 高于当前会话 release 时才给出有界的版本提示，否则原因记为 `undetermined_by_error_alone`，不硬写“由 Creo 12.4 构建，当前版本无法加载”。加载成功与后续建模成功分别记录（`seed_load_succeeded` / `modeling_succeeded`）。

## 两截面种子与调用

可以直接下载独立发布的 [种子库](SEED_LIBRARY.md)，选用 `two_straight` 或 `two_smooth`。种子原文件可以在不同电脑复制，调用时改为本机绝对路径，清单中的内部 ID 适用于同一份原文件。

先创建 Z=0 的 20×20 正方形，再创建 Z=30 的 10×10 正方形；创建实体“混合”，使用“选定截面”，按顺序选取完整闭合曲线链。在“选项”设置直线或平滑，确认保存并查询原生特征 ID。源码内附九个项目原创 MIT 种子 PRT，不含 PTC 模型或 SDK。

将 [loft_seed.json](../examples/loft_seed.json) 或 [loft_smooth_seed.json](../examples/loft_smooth_seed.json) 作为工具参数，替换种子绝对路径与 ID。示例方台体积 7000 mm³。种子库两份原始两截面种子的内部 ID 为 60；自行新建或改造的模型须重新查询，不能套用该值。

任务成功后确认 `result.saved_file_reloaded_and_verified == true`，检查 `result.loft_checks.before_save.blend` 与 `after_reload.blend` 的模式和截面数。自定义标签时键名跟随标签。模式通过 Creo 官方 `PRO_FEAT_INFO` 核对，修改、重载和回滚后再次检查；两截面自由端点的直线和平滑可能产生相同几何。

上截面可调用 `creo_set_sketch_dimensions`：最新模型 ID、revision、`sketch: "top"`、`values: {"width": 12, "height": 12}`。体积变为 7840 mm³，后续仍能通过通用工具追加拉伸切除等特征。

## 两截面回归案例

| 案例 | 参数 | 体积 mm³ |
| --- | --- | ---: |
| 方台 | 正方形 20→10，间距 30 | 7000 |
| 圆台 | 半径 10→5，间距 30 | 5497.787143782138 |
| 三角台 | 直角等腰三角形边长 20→10，间距 30 | 3500 |
| 修改方台 | 上截面 10→12 | 7840 |
| 后续切除 | 修改后的方台扣除 Ø2、高 30 的圆柱 | 7745.752220392307 |

直线和平滑分别运行上述案例；另检查故意错误断言的回滚、无效 ID 及模式不匹配。公开摘要为 [validation_loft_seed.json](validation_loft_seed.json)、[validation_loft_smooth.json](validation_loft_smooth.json)，其他模块保留历史证据，不推定完整 Creo 覆盖。

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\blend_seed.prt.1' --feature-id 60 --interpolation straight
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\smooth_seed.prt.1' --feature-id 60 --interpolation smooth
```

路径和 ID 必须替换。超时或未知结果先检查原任务，不重复提交。种子复用不增加或删除截面；数量与模式必须匹配。`creo_loft` 与计划操作 `loft` 已支持直接创建和已有受管零件追加，限 XY 截面按实际 Z 递增、默认实体增材，见 [直接混合](DIRECT_BLEND_0.2.5.md)。非平行、切除/曲面以及相切/曲率控制仍未开放。
