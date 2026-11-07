# DEV-074 H07 / H08 曲面探针证据（2026-11-08）

环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK；Creo 会话由用户手工启动并验证可用，
`config.json` 的 `auto_start_creo=false`。未启动或关闭 Creo、未清 unknown 保护、未做故障注入、
未修改主工作区。源码起点 `e6e9da5`（分支 `codex/DEV-074-h05h12`，0.18.3）；本轮驱动的两个探针只
经由公开 MCP 工具（`creo_execute_plan` / `creo_create_feature_tree` / `creo_round` /
`creo_inspect_model` / `creo_get_job`）提交，未直连 Toolkit。

驱动（`build/` 本机生成物，不提交）：

- `build/_live_h07.py`：H07 路线 A（公开 `surface_offset` 单侧）与 B1—B3（独立偏置候选树）；
- `build/_live_h08.py`：H08 实体圆角对照 C0 与曲面边圆角 C1/C2/C5。

## H07 / FEAT-039：独立 quilt 偏置

源 quilt 由公开 `surface_loft` 产生：两条 40 mm 直线截面相距 20 mm，quilt 61、1 个面、
面积 800.0 mm²、开放、外框 `[[0,0,0],[40,0,20]]`（法向为 ±Y）。

### 路线 A：`ProThicken.h` 文档化单侧偏置（当前公开 `surface_offset`）

| 侧 | 作业 | 体积 mm³ | 实测距离 mm | 结果 quilt | 结果外框 |
| --- | --- | --- | --- | --- | --- |
| positive | `cfeb9eeba3e849ba9118f396997a6dd9` | 0 → 3999.9999999999995 | 4.999999999999999 | quilt 61：**6 面**、2200 mm²、`closed=true` | `[[0,0,0],[40,5,20]]` |
| negative | `4bfcf866dede4d7b98e992b27a1bd8c9` | 0 → 3999.9999999999995 | 4.999999999999999 | quilt 61：**6 面**、2200 mm²、`closed=true` | `[[0,−5,0],[40,0,20]]` |

两次均 `saved_file_reloaded_and_verified=true`，`target_quilt_id=61`，`source_area_mm2=800.0`，
`offset_distance_status.source="volume_over_source_area"`。

判读：

- 结果是**厚度带**（闭合 6 面实体带的边界：800 + 800 + 4×(5×边长) = 2200 mm²），不是一张独立的
  偏置曲面；没有任何新的 quilt 出现，quilt 61 被实体边界取代。
- 带宽恰好等于请求值：正侧占 y∈[0,5]，负侧占 y∈[−5,0]，两侧外框厚度均为 **5.0 mm**，方向可控。
- 这与公开回执的语义一致：`surface_offset` 是“偏置壁”，`target_quilt_id` 指向源 quilt，
  不是下游偏置 quilt。

### 路线 B：独立偏置特征树（三条候选，全部失败，按 3 次上限停止）

| 路线 | 树（元素名） | 作业 | `ProFeatureWithoptionsCreate` | 结果 |
| --- | --- | --- | --- | --- |
| B1 | `PRO_FEAT_OFFSET` + `PRO_E_SRF_OFFS_REFQUILT` + `PRO_E_SRF_OFFS_OFFSET` + `PRO_E_SRF_OFFS_METHOD=1` | `8c032aae04f54fc483c1df5282c0d0e4` | **−1** | 回滚，quilt 仍 1 面 / 800 mm² |
| B2 | `PRO_FEAT_DATUM_SURF` + `PRO_E_FEATURE_FORM=PRO_COPY` + `PRO_E_SRF_COPY_SRFS` + `PRO_E_SRF_OFFS_OFFSET` | `7291710910eb4c8e93fffc2088c5fac2` | **−2** | 元素加不进树，回滚 |
| B3 | `PRO_FEAT_DATUM_SURF` + `PRO_E_SRF_OFFS_SRF` + `PRO_E_SRF_OFFS_OFFSET` + `PRO_E_SRF_OFFS_METHOD` + `PRO_E_SRF_OFFS_TYPE` | `e6bca3ecdbbe47ddabf7b70caff1ba50` | **−1** | 回滚，quilt 仍 1 面 / 800 mm² |

每个候选都在独立的新模型里重建同样的 800 mm² loft quilt（构建作业 `34c0365b…`、
`aa384bb0…`、`74bec559…`，全部 succeeded），因此失败来自树本身，不是引用或源几何。

结论：**独立 quilt 偏置仍不可用**。`PRO_E_SRF_OFFS_*` 族只在 thicken（本文件的路线 A）与
thin trim 树里作为子元素成立；`ProQuilt.h`、`ProSurface.h`、`ProCopyGeom.h`、`ProSrfcopyOpts.h`
都没有独立的偏置面创建 API（`ProSrfcopyOpts.h` 的五个 copy 类型不含 offset）。公开语义继续是
“偏置壁”，`surface_trim` 的 `offset_mm`/`offset_side` 保持门禁。

## H08 / FEAT-055：曲面边圆角与分析

### SDK 声明依据（本机 Creo 12.4.0.0 头文件实读）

- `ProRound.h`：`PRO_FEAT_ROUND`（`ProFeatType.h:11` = 913）的元素树
  `PRO_E_RNDCH_SETS → PRO_E_RNDCH_SET → PRO_E_RNDCH_REFERENCES`；
  `ProRoundReferenceType` = `PRO_ROUND_REF_EDGE(1)`、`PRO_ROUND_REF_SURF_SURF(2)`、
  `PRO_ROUND_REF_EDGE_SURF(3)`、`PRO_ROUND_REF_EDGE_EDGE(4)`；
  `PRO_E_RNDCH_ATTACH_TYPE` = `PRO_ROUND_ATTACHED(0)` / `PRO_ROUND_UNATTACHED(9)` /
  `PRO_ROUND_CAPPED_ENDS(15)`。
- 同一头文件在 `PRO_E_STD_CURVE_COLLECTION_APPL` 条目下明确写出：
  “Mixed selection from different solid bodies and/or quilts is supported. Resulting geometry
  will be attached back to the same solid body or quilt where the referenced edges came from.”
  即 quilt 上的圆角是文档化支持的，不是本项目自造。
- 分析：**没有** `ProCurvature*`、斑马纹或曲率梳 API。全 SDK 只有
  `ProSurface.h:586 ProSurfacePrincipalCrvtEval`（给定 UV 点返回最大/最小主曲率与主方向）与
  `ProMechGeometry.h:1807 ProMechsurfacePrincipalCrvtEval`（Simulate 侧同名量）。
  `ProAnalysis.h` 只有 `PRO_ANALYSIS_CLASS_EXTERNAL(8)` 的外部自定义分析类注册机制，没有内置
  曲率/斑马/梳图类型。

### 实机读数（公开 MCP）

| 用例 | 选择 | 作业 | 结果 | 保存重载 |
| --- | --- | --- | --- | --- |
| C0 实体对照 | 40×20×10 方块、边 54（相邻面 53/63）、R3 | `621d9573d5e64540a43138f04e308733` | 体积 7999.999999999999 → **7922.7433330068 mm³**（Δ −77.25666699319936），7 面，仍是实体 | true |
| C1 曲面边 | 曲面拉伸 quilt 70（4 面、1200 mm²）、面对 (68,66)、R3 | `d567f5d8933b4fb8a716f952773b94a9` | quilt 70 → **5 面、1187.1238898038469 mm²**、`closed=false`、0 个实体面、`material_measurement=not_applicable` | true |
| C2 重复 | 同一构造、面对 (66,64)、R3 | `03cfba97ec4a4e099e7fcfb1871d079d` | 同上 5 面、1187.1238898038469 mm² | true |
| C5 负例 | 同一 quilt、非相邻面对 (68,64)、R3 | `495d56bdf364490bba9443065ea2d52e` | 失败：“Regeneration produced a failed, suppressed or incomplete feature”；回滚到 4 面 / 1200.0 mm² | false（回滚） |

解析 oracle（C1/C2 精确命中）：1200 − 2×3×10 + (π/2×3)×10 = 1200 − 60 + 47.12388980384689 =
**1187.1238898038469 mm²**。`reference_application.applied_set_count=1`、`query_code=0`。

判读：曲面边圆角**可行且结果留在 quilt 上**（开放面、无实体、无体积读数），不是实体圆角；
非相邻面对在再生阶段失败并整体回滚，说明“只接受共享一条边的两个面”这一限制可以被内核兑现。

### 最小契约（只登记，不实现）

- 入口：`surface_round`（MCP 工具 `creo_surface_round`），默认保持 `UNAVAILABLE_OPERATIONS`。
- 输入：`reference`（一个 quilt：`{kind:"quilt",id}` 或 `{kind:"quilt_feature",label}`）+
  `faces`（恰好两个 `{kind:"surface",id}`，必须是该 quilt 的成员且共享一条边）+ `radius > 0`。
- 只做单组、常量半径、`PRO_ROUND_REF_SURF_SURF`；`PRO_E_RNDCH_ATTACH_TYPE=PRO_ROUND_ATTACHED`。
- 拒绝：多组、非相邻/跨 quilt 面对、变半径、full/chordal/through-curve、带过渡（transitions）
  的写法；`PRO_ROUND_REF_EDGE` 暂不开放——公开查询没有 quilt 边 id 通道
  （`creo_inspect_model` 的 edges 只枚举实体面边，曲面 quilt 模型为 0 条）。
- 回执：`quilt_id`、`face_count`/`area_mm2` 前后值及 `*_status`、`radius`、
  `reference_application`、`material_measurement`（曲面结果必须是 `not_applicable`）、保存重载标记。
- 分析侧：短周期内只能给出数值读数（主曲率 max/min、方向），没有斑马纹/曲率梳 API；
  跨边 G1 判定建议的实现路径是：共享边按参数采样 → 两侧面各取法向（`ProSurfaceParamEval` +
  `ProSurfaceXyzdataEval`/`ProSurfaceTessellationGet` 的法向）→ 夹角 ≤0.5°。该测量尚未实现，
  本轮不声称任何 G1 数值。

## 未覆盖

- H07：非 mm 单位、弯曲源 quilt 的带厚读数、`offset_mm` 变体的实机重放；B 路线只覆盖 3 个候选树。
- H08：edge-chain（`PRO_ROUND_REF_EDGE`）未取得 quilt 边 id，未试；变半径/full/过渡未试；
  圆角后继续 thicken/solidify 的链未验证；G1 与曲率读数只有 API 依据，没有实机数值；Creo 9/10 未测。

## 文件校验

| 文件 | SHA256（仓库内 LF 文本字节） |
| --- | --- |
| `h07_quilt_offset_probe.json` | `D3FD6F5704002AB9054A062E8FF37D539C77530D5C508859FD2693F33F2EF1E5` |
| `h08_surface_round_probe.json` | `D74FF0619EA07F1B867F403C5FA30DF9DA5B81F4EE20A04C679D5E5EFB6E64D5` |
