# DEV-053 Q01 离线交接（2026-11-01）

固定 ID：BUG-095（P07）、BUG-032 / FEAT-014（P08）、BUG-088（P11）、DEV-053。基线 `50636bf`，开发树 `codex/q01-post0100-batch`；版本元数据仍为 0.11.0。这里只记录离线迁移，原生构建和 Creo 实机由统一窗口验收。

## 待集成提交及冲突决策

| 旧提交 | 本树提交 | 冲突与决策 |
| --- | --- | --- |
| `53ed968` P11 | `4758763`，后续测试适配 `30d7fd1` | `native/preview.h` 与 main 的 FEAT-052 窗口绑定/重绘重叠；保留主干绑定与重绘，在 capture 入口加空几何探测。测试只在 capture 函数内断言探测顺序。其余 preview 投影和驱动复用旧提交。|
| `50b34a1` P07 | `e92ef0d` | main 的 `native/generic.cpp` 已有其他同源 PATCH，三方合并只收原点实测诊断；`operation_results.py` 投影保留原生数值、不从请求补证。|
| `28b1447` P08 | `9e76309` | `docs/COMPATIBILITY.md` 保留 main 的 0.11.0 FEAT-052 段，并加入 P08 离线段；`native/generic.cpp` 与 P07 同文件按顺序集成。其余方向、候选边和旧测试直接复用。|

建议 Q15 依 P11→P07→P08 顺序收取，再收 Q02、Q03、Q04；Q02 与本树共改 `native/generic.cpp`、`server.py`、`operation_results.py`，Q03 共改 `native/generic.cpp`，Q04 共改 `server.py`。Q02 的 geometry_deviation 属求解几何证据，P07 的 sketch_origin_diagnostics 属原点拒绝证据，两者独立保留；Q03 清理失败对象不得清掉 P07 阶段结果；Q04 只合并 busy/stage 逻辑，不覆盖 P08 的工具响应字段。共同修改的计划与台账文档由 Q15 按最新主干状态重写，不采纳旧分支的版本号或历史状态覆盖。

## 字段所有权

- Q01/P07 拥有失败 sketch 操作中的 `sketch_origin_diagnostics`：`status`、`distance_to_plane_mm`、`signed_distance_to_plane_mm`、`origin_tolerance_mm=1e-6`、`support_plane.normal/constant_mm`、`requested_origin`、`suggested_origin`。Q06 可新增斜面 UV/section/CompleteFeature 诊断，但不得以 identity 猜测真帧、不得重算或覆盖该原点字段；两者在同一操作记录并列。
- Q01/P08 拥有 `wall_contract.frame`、`wall_face_ids`、`parameter_hint` 和巡检 `wall_contour_check`（eligible/ineligible/unknown、真实查询代码与 bounded 记录）。候选边 unknown 不冒充可用边。
- Q01/P11 拥有 `result.preview.status` / 顶层 `preview_status` 的 `skipped_no_geometry`、`written`、`failed`、`not_attempted` 投影及原始 codes/file_check。Q13 可增加非空模型的基准遮挡与大回包证据，但应保留这些现有状态及字段，不把上色专用分页直接推广；遮挡诊断用另名字段。

## P11 证据对账与验收边界

只读核对 `E:\Projects\MCP_CREO_MechDog_feat052\build\t07_preview_feat052_regress_20261101.json`：总 `preview_acceptance=passed`，但 `empty_part` 模型作业 `succeeded`、预览 `failed` / `failed_step=output_file` / `failed_code=-4`，输出文件不存在；报告还明确 `empty_part_expectation=capture_may_fail_recorded_not_asserted`。`docs/validation/RELEASE-0.11.0.md` 所称 `skipped_no_geometry` 与该实测和当时主干源码不符。本树已迁入 P11 离线代码与测试，**P11 尚未实机交付**；该历史总判定不可充当 P11 验收。

## 本次验证

工作树内 `PYTHONPATH=E:\Projects\MCP_CREO_MechDog_q01;E:\Projects\MCP_CREO_MechDog_q01\src`，解释器 `E:\Projects\MCP_CREO_MechDog\.venv\Scripts\python.exe`。六个专项模块合计 125 tests，OK；默认离线驱动 `tools/test_sketch_origin_diagnostics.py`、`tools/test_sheetmetal_contract.py`、`tools/test_flange_direction.py`、`tools/test_t07_preview.py` 均 exit 0。前两份报告的源码指纹均为 `1389a855fd42e3cf9d80173daa21da94057d24815cd5d0ca47a79c0d22916a38`，dirty=false；运行记录在忽略的 `build/` 下。旧分支结论保留其原日期，不作为本轮实机结果。

统一实机窗口仍需：原生构建、P07 原点与任意平面几何、P08 方向/候选边 unknown、P11 空件状态、保存擦除重载及适用回滚。Creo 9/10 未验；本轮没有连接或占用 Toolkit 通道。
