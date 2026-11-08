# FEAT-039/H04 曲面组级测量实机证据（2026-11-07）

## 环境与命令

- Windows x64；Creo 12.4.0.0；本机匹配 Toolkit SDK；单位 mm；单会话串行通道。
- 构建：`.\.venv\Scripts\python.exe bridge.py build`（退出 0）。
- 驱动：`.\.venv\Scripts\python.exe tools\test_surface_chain.py --case group --live --confirm-session-usable`
- run：`20261107-132056-710000`；42 项检查全部通过（`passed=true`）。
- 报告：[live_group_report.json](live_group_report.json)，15645 B，SHA256
  `D530B999A0C1A97F5770EC67E5415A5ACA4B91C4B60448C88B7C177C2D5C9970`（LF 行尾）。

每例的构造：两张 40×20 平面填充（`surface_fill`），第二张沿 X 平移 offset；两张草图都用
`dimensioning="coordinates"`。每例先用一个可写作业建模并保存重载，再用只读工具
`creo_measure_surface_group` 在**重载后的模型**上测量（revision 不变）。

## 四态实测

| 用例 | offset mm | 建模 job | 测量 job | state | open_edges | gap_max_mm | overlap | 保存重载 | revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 共边拼接 | 40.000 | `4bc91199e98c46aaa7f178085130b3f4` | `a1c0f387cc774278bdee35b8070283f8` | `closed` | 6 | 0.0 | — | true（建模作业） | 1 → 1 |
| 0.005 mm 微缝 | 40.005 | `e85cc62dd93a46db91a6ad15369f17c5` | `d65470b3d5bf4af88ec0012256e10e57` | `micro_gap` | 6 | 0.005000000000009663 | — | true（建模作业） | 1 → 1 |
| 0.5 mm 缝隙 | 40.500 | `7bb6e6030a544c6391b34534301e14d5` | `f4cbc4901ac546e8b1f3a91ce59e96b6` | `open` | 8 | 0.5 | — | true（建模作业） | 1 → 1 |
| 0.5 mm 重叠 | 39.500 | `b223d959b34948aca928712d268a6db9` | `248936751b9742ccba5485ada60a2509` | `overlap` | 8 | 0.5 | `detected=true`、`buried_boundary_edges=2`、`overlap_area_mm2=0.0`（`area_below_sample_resolution=true`） | true（建模作业） | 1 → 1 |

所有例的 `boundary_closed=false`（两张平面拼接仍是开放片）、`unit_name="mm"`、
`length_scale_to_mm=1.0`、`tolerance_mm=0.01`、`gap_search_mm=1.0`。

说明：

- **共边/微缝**：缝对在容差内 joined；0.005 mm 的 joined 缝距离 > 1e-6 mm 的"完全重合"阈值，
  因此判 `micro_gap` 而不是 `closed`。
- **0.5 mm 缝**：缝对超出容差但在搜索窗口内，`gap_max=0.5`、`within_tolerance=false`，判 `open`。
- **0.5 mm 重叠**（重叠带 0.5×20=10 mm²）：边界边埋入另一面内部 0.5 mm，`buried_boundary_edges=2`；
  面积采样分辨率为 7.27 mm²/点，10 mm² 重叠带不足一个采样点，故面积估计为 0 并标注
  `area_below_sample_resolution=true`；`state` 仍由埋入边界判为 `overlap`。

## SDK 依据

- 成员面：`ProQuiltSurfaceVisit`。
- 边界：`ProSurfaceContourVisit` → `ProContourEdgeVisit`（`ProEdge`）、`ProEdgeLengthEval`。
- 边采样：`ProEdgeTessellationGet`（点数 ≥5 时使用），否则 `ProEdgeXyzdataEval` 参数采样
  （直线边默认只镶嵌两端点，端点恰在邻面拐角/边界上，会漏判）。
- 重叠：`ProSurfaceTessellationGet`（面网格）+ `ProSurfaceParamEval` + `ProSurfaceXyzdataEval` +
  `ProSurfaceUvpntVerify`。
- 未使用面积/体积推断，也未调用 `ProQuiltVolumeEval` 作为组级判据。

## 本轮发现的构造限制

- `dimensioning="auto"`（autodim）在本机会把草图轮廓量化到 0.01 mm：请求 40.005 的填充实测
  外框为 40.01（`GEOMETRY_STAGE_SHAPE … translation=0.005 … rigid=1`），0.005 mm 缝被挪到
  容差边界。改用 `dimensioning="coordinates"` 后坐标保持 40.005，微缝用例成立。
- 两片完全共面的填充无法用 `quilt_merge` 缝合（该算子仍 gated），因此组级测量只能对**独立
  quilt 集合**取证，不代表合并特征的内部拓扑。

## 未覆盖

- Creo 9 / Creo 10；非 mm 单位；多面/曲面（非平面）成员；闭合壳体组（`open_edges=0`）。
- 重叠面积估计精度（采样分辨率限制）、`gap_search_mm` 之外的间距量化、跨 cowork 的缝方向。
- 只读测量作业本身不做保存重载（`saved_file_reloaded_and_verified` 只在建模作业上为 true）。
