# DEV-074/H08 数值曲率与 G1 分析离线证据（2026-11-08）

范围：本机 Windows x64、Creo 12.4.0.0 SDK、MSVC x64；分支 `codex/DEV-074-forming`，
worktree `e:\Projects\MCP_CREO_MechDog-d074`。**本轮未启动 Creo、未连接 Toolkit、未执行
`--live`**；以下都是离线编译、单元测试与源码级核对。

## 交付

- 只读计划操作 `surface_curvature`，公开工具 `creo_measure_surface_curvature`。
- 原生 `native/surface_curvature.cpp::generic_surface_curvature`。
- Python：`SurfaceCurvatureOp`（schema）、`generic_bridge.measure_surface_curvature`、
  `job_projection.SURFACE_CURVATURE_KEYS`、`operation_results.normalize_surface_curvature` /
  `annotate_surface_curvature`、`server.creo_measure_surface_curvature`、
  `capabilities` 注册与 `surface_curvature` 能力族。
- 测试：`tests/unit/test_surface_curvature_contract.py`（20 项）。

## 语义

- 输入：一个 quilt（`{kind:"quilt",id}` 或 `{kind:"quilt_feature",label}`）+ 1–2 个成员面
  （`{kind:"surface",id:N}` 或零基成员索引）+ `samples_per_direction` 5–50，默认 12。
- 原生：`ProQuiltSurfaceVisit` 校验成员归属；UV 范围来自 `ProSurfaceDataGet`
  （本机 SDK **不存在** `ProSurfaceParamRangeGet`）；单元中心栅格经 `ProSurfaceUvpntVerify`
  过滤后调用 `ProSurfacePrincipalCrvtEval`；每点返回 u/v、最大/最小主曲率（1/mm）、
  曲率半径（mm）、主方向。两共享边成员面沿 `ProEdgeXyzdataEval` 采样，两侧
  `ProSurfaceParamEval` + `ProSurfaceXyzdataEval` 取法向，返回 `g1_max_angle_deg` 与
  `g1_points[].angle_deg`；0.5° 只设置 `within_g1`。
- 单位：`1/mm = curvature_native / scale_to_mm`，`mm = radius_native * scale_to_mm`；
  单位未知时 1/mm 与 mm 值为 null + `unit_scale_unknown`。
- 失败不伪造 0：查询失败只增加 `failure_count`；整面无面内采样点时 `available=false` +
  `no_curvature_samples_inside_face` / `principal_curvature_eval_failed`。
- 只读：`readonly=True`，原生不 `ProSolidRegenerate`，revision 不变。
- **不提供斑马纹/曲率梳图像**：Toolkit 无可视化 API，数值分析是声明的等价交付。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，输出 `build\creo_worker.exe` |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_surface_curvature_contract -v` | 20 项全过 |
| `tests.unit.test_surface_group_measure` + `test_surface_round_contract` + `test_surface_boundary_fill_contract` | 78 项全过 |
| `tests.unit.test_t01_capability_contracts` + `test_reference_contract` + `test_callback_admission` + `test_update_check` | 52 项全过 |
| `.\.venv\Scripts\python.exe -c "import asyncio, server; print(len(asyncio.run(server.mcp.list_tools())))"` | `107`，含 `creo_measure_surface_curvature` |
| `ruff check` / `ruff format --check`（改动 Python 文件） | 通过 |
| `clang-format --style=file --fallback-style=none --dry-run --Werror native/surface_curvature.cpp` | 无差异 |

## 未验证 / 待实机确认

- 曲率数值是否正确（含平面零曲率、圆柱 1/R、球面主曲率相等）。
- `ProSurfaceDataGet` 返回的 UV 范围在裁剪面、平面与 B 样条面上的实际可用性；
  面内采样比例与 `outside_contour_count` 的真实分布。
- G1 法向夹角与 0.5° 阈值；相邻面绕向相反时读数可能接近 180°，需实机确认。
- 非 mm 单位、Creo 9/10、多个共享边、退化为尖边/缝合边的情形。
- 只读 revision 不变的实机核对（本机仅有代码路径证据）。
