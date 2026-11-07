# FEAT-039 / H06 保留侧真实几何测量（2026-11-07）

条目：[FEAT-039](../../work-items/FEAT-039.md)（H06，见 [DEV-074 接手清单](../../development/DEV-074-HANDOFF.md)）。
契约：[G5-NATIVE-CONTRACT §4.5](../../development/G5-NATIVE-CONTRACT.md)。
本目录为新增证据，未修改 `docs/validation/` 下任何既有原件。

## 1. 环境与受测源码

| 项 | 值 |
| --- | --- |
| 环境 | Windows x64；Creo 12.4.0.0（用户已手工启动，单会话串行）；匹配 Toolkit SDK；MSVC x64 |
| 工作树 | `E:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-feedback0174-offline` |
| HEAD | `e8e8b42f507ea09228134a97182b632e49864726` + 本轮未提交改动（dirty） |
| 执行器 | `build/creo_worker.exe` SHA256 `8087F4D348050239C65A86C515F72377589199245A2407C9186946C1F7128704`（`bridge.py build` exit 0） |
| 源码指纹 | `native/surface_measure.h` `A55612E1…F287273`；`native/surface_trim.cpp` `A06D0954…D086D7E`；`src/creo_mechdog/operation_results.py` `E87CC982…FD99D8F`；`tools/test_surface_chain.py` `1BFBCF3A…71BE819`；`tests/unit/test_surface_trim_kept_side_evidence.py` `8D6A79C8…C83E667C` |
| 驱动 | `.\.venv\Scripts\python.exe tools\test_surface_chain.py --case trim --live --confirm-session-usable` |
| 原始报告 | [live_trim_report.json](live_trim_report.json)（19943 bytes，SHA256 `4911D20D9F8F39FB818A050808B7DC1D8B589746C010CE7457CC31B810936C6A`，run `20261107-121303-781400`） |

## 2. 可用查询与实测行为

Creo 12.4 SDK 中 `ProQuilt.h` 只有 `Init / IdGet / SurfaceVisit / VolumeEval / IsBackupgeometry / IsInternal`，
**没有**质心或包围盒查询；`ProSurface.h` 也没有 `ProSurfaceEval`/`ProMeasurable`。可用的真实几何面是：

| 查询 | 声明位置 | 实测用途 |
| --- | --- | --- |
| `ProQuiltSurfaceVisit` | `ProQuilt.h:105` | 枚举 quilt 的成员面 |
| `ProSurfaceTessellationGet` + `ProSurfacetessellationinputAlloc/ChordheightSet/inputFree` | `ProSurface.h:612–724` | 取**修剪后面**的三角网格（默认显示弦高），返回 `PRO_TK_NO_ERROR` |
| `ProTessellationVerticesGet` / `ProTessellationFacetsGet` / `ProTessellationFree` | `ProSurface.h:726–811` | 顶点 `Pro3dPnt`（=double[3]）与面片 `ProTriangle`（=int[3]，`ProPart.h:10`） |
| `ProSurfaceXyzdataEval` / `ProSurfaceParamEval` / `ProSurfaceAreaEval` / `ProSurfaceExtremesEval` | `ProSurface.h:219–357` | 已核对存在；本次未采用（`ExtremesEval` 只是按方向投影的极值，精度受边三角化限制，且不给面积加权形心） |
| `ProContourAreaEval` / `ProSurfaceContourVisit` | `ProContour.h:140`、`ProSurface.h:442` | 既有面积口径（未改变） |

最小可复现探测（同一实机窗口，40×20 平面填充）：直接对该 quilt 采样，得到
`triangle_count=2`、`face_count=1`、质心 `(20,10,0)`、bbox `[0,0,0]–[40,20,0]`、法向 `(0,0,-1)`、
`max_normal_deviation_deg=0`。数值与解析值完全一致，说明：

- 三角面片覆盖的是**修剪后**的面，不是未修剪基面；
- 面积加权形心 = 三角形面积加权质心（不是外框中心）；
- 轴对齐 bbox 直接取顶点极值；
- 平面法向取面积加权、绕向对齐后的平均法向；非平面区域用 `max_normal_deviation_deg > 0.5°`
  判为不可用，返回 `null` + `reason="region_not_planar"`，不把平均向量冒充某点法向。

## 3. 实机矩阵（逐项）

命令见上。6 个 job，全部串行提交，无并发、无重提。

### 3.1 `keep_side=one/two` × 平面工具（x=5 基准面，法向 +X）

工具平面法向由 `ProPlanedata.e3` 读入并归一化；`target` 为 40×20 填充（800 mm²）。

| keep_side | job_id | 终态 | area_after_mm2 | target_centroid | kept_centroid | delta_mm | kept bbox min–max | kept_direction | signed_offset_mm | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one | `557ad826ccf84e8c8e009e5689361335` | succeeded (rev 1) | **700.0** | (20,10,0) | **(22.5,10,0)** | **(+2.5,0,0)** | (5,0,0)–(40,20,0) | (0,0,−1) planar 0° | **+2.5** | true |
| two | `b431322541e74549a82103354b7093c1` | succeeded (rev 1) | **100.0** | (20,10,0) | **(2.5,10,0)** | **(−17.5,0,0)** | (0,0,0)–(5,20,0) | (0,0,−1) planar 0° | **−17.5** | true |

两个保留侧的形心分别在工具平面 x=5 的两侧：`22.5−5=+17.5` 与 `2.5−5=−2.5`，符号相反且面积不是判据。

### 3.2 `keep_side=one/two` × quilt 工具（x=5 的 YZ 60×60 填充）

| keep_side | job_id | 终态 | area_after_mm2 | target_centroid | kept_centroid | delta_mm | kept bbox min–max | kept_direction | tool_normal（source） | signed_offset_mm | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one | `549773db06184377814f7ec71199bc65` | succeeded (rev 1) | **700.0** | (20,10,0) | **(22.5,10,0)** | **(+2.5,0,0)** | (5,0,0)–(40,20,0) | (0,0,−1) planar 0° | (−1,0,0) `tool_quilt_face_normal` | null（reason `tool_normal_unavailable`） | true |
| two | `2316d27699e242d289915fae14e565c8` | succeeded (rev 1) | **100.0** | (20,10,0) | **(2.5,10,0)** | **(−17.5,0,0)** | (0,0,0)–(5,20,0)（y 下界含 1.9e-31 网格噪声） | (0,0,−1) planar 0° | (−1,0,0) `tool_quilt_face_normal` | null（reason `tool_normal_unavailable`） | true |

quilt 工具的实测面法向是 `(−1,0,0)`，与草图支撑面法向 `(+1,0,0)` 相反——这正是**不能**把 quilt 工具法向用于
`keep_side` 符号判定的实测原因。两侧仍由形心坐标与差值证明落在 x=5 两侧（+17.5 / −2.5）。

### 3.3 失败用例与干净回滚

先建 40×20 填充 + x=100 的基准面（job `a9e58c89b091468bb9dc8824f78bea0e`，succeeded/rev 1、保存重载 true），
再在同一模型提交 `surface_trim`（工具不相交）。

| 项 | 实测 |
| --- | --- |
| job_id | `1fde1a0c702b4713bfd04d3c5291b1ef` |
| 终态 | **failed** |
| 原始消息 | `Surface trim regeneration failed (feature_status=6, feature_id=87, target_quilt_id=82, tool=datum_plane, keep_side=one); check that the tool actually intersects the target quilt` |
| 回滚 | `rollback_succeeded=true` |
| 模型几何 | 仍只有 800.0 mm² 的未修剪填充 |
| revision | 1 → **1**（未推进） |

## 4. 实现与契约

- `native/surface_measure.h`：新增 `RegionGeometry` 与 `quilt_region_geometry()`（面片面积加权质心/bbox/法向）、
  `region_centroid_json` / `region_bbox_json` / `region_direction_json` / `region_status_json` /
  `region_direction_status_json`。失败一律 `available=false` + `reason` + 原始 `query_code`；单位比例未知时
  毫米值保持 `null`（`scale_to_mm_known=false`），不填 0、不按“看起来是 mm”采用。
- `native/surface_trim.cpp`：`target_centroid` / `kept_centroid` 换成真实值；新增 `target_bbox_mm` /
  `kept_bbox_mm` / `target_direction` / `kept_direction` / `centroid_delta_mm` 与各自的 `*_status`；
  `tool_normal` 对平面工具保持基准面轴（已归一化），对平面 quilt 工具给出实测面法向并标注
  `tool_normal_source`；`signed_offset_mm` 只在法向符号可锚定（基准面）时给出。
  契约 §4.5 的“矛盾即失败”已按实测质心落实：基准面工具下 `one` 要求投影 >0、`two` 要求 <0，否则 op 失败并回滚。
- `src/creo_mechdog/operation_results.py`：新增 `normalize_kept_side_basis` / `annotate_kept_side_basis`，
  只做“值不得脱离状态”的投影：状态不可用则值为 null；点/bbox 无已知单位则保持 null；非平面区域无方向；
  无状态支撑的 `signed_offset_mm` 归零为 null；历史 job 缺字段不补造。
- 单测：`tests/unit/test_surface_trim_kept_side_evidence.py`（16 项，覆盖 null 语义、单位未知、
  `available=false` 带 reason、非有限值、历史记录不扩张）。
- 驱动：`tools/test_surface_chain.py --case trim` 同时校验平面/quilt 计划与失败计划可过 schema；
  live 用例扩展为上述 4 个成功组合 + 回滚用例，并断言形心、bbox、方向与“两侧落在相反侧”。

## 5. 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，输出 `build/creo_worker.exe` |
| `tools\test_surface_chain.py --case trim`（离线） | `passed=true` |
| 定向单测 9 个模块（含新增 16 项） | 138 项 OK |
| `ruff check` + `ruff format --check`（3 个 Python 文件） | All checks passed / already formatted |
| `clang-format --style=file` （2 个 native 文件） | clean |
| `tools\test_surface_chain.py --case trim --live --confirm-session-usable` | `passed=true`，43 项检查全通过 |

## 6. 未覆盖 / 风险

- 未测非平面（圆柱/球）保留区域的方向字段：实现按 `region_not_planar` 返回 null，但没有实机负例证据。
- 未测英寸/非 mm 模型：单位比例未知时 null 语义只有单测覆盖，没有实机读数。
- 未测多面 quilt（多张曲面组成的保留区域）的质心/bbox；本次目标与保留区都是单面。
- 未测 quilt 工具法向方向在**同一模型多次重建**后的稳定性；本次 one/two 是两个独立模型，均测得 `(−1,0,0)`。
- 未测 Creo 9 / Creo 10：本机只有 12.4 SDK 与运行时会话。
- 三角网格精度沿用 Creo 默认显示弦高（平面用例为精确值）；曲面区域的质心/bbox 精度未量化。
- 未做故障注入；`rollback_kept_the_revision` 只比较作业前后 inspect 的 revision，不覆盖 unknown_outcome。
