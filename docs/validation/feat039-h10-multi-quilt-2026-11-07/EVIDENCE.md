# FEAT-039/H10 多 quilt 组整链实机证据（2026-11-07）

## 环境与命令

- Windows x64；Creo 12.4.0.0（作业回执 `creo_release_numeric=44`）；本机匹配 Toolkit SDK；单位 mm；
  单会话串行通道。Creo 由用户手工启动并确认可用，本轮未启动/关闭 Creo、未清 unknown 保护、未做故障注入。
- 源码：worktree `e:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-h05h12`，HEAD `3eb7c10` + 本轮改动。
- 构建：`.\.venv\Scripts\python.exe bridge.py build`（退出 0）。
- 驱动：`.\.venv\Scripts\python.exe tools\test_multi_quilt_group.py --live --confirm-session-usable`
- run：`20261108-011157-8a32d4`；46 项检查全部通过（`passed=true`、`native_multi_quilt_group="verified"`）。
- 报告：[live_multi_quilt_report.json](live_multi_quilt_report.json)，21 825 B，SHA256
  `95E23A7FDBD547DE6E7C9CC0809518266816DDE60368455336B900DD2D8238E9`。
- 模型：组 A `18820cd7e831457caa2865e8ff40252d`，组 B `aef3374fd71344dd9c30ea048d94ed9d`。
- 作业：`30696732…`（组 A 构建）、`b4808ce3…`（组级测量）、`c831e45a…`（0.3 mm 加厚）、
  `d0fdabe2…`（重载后组测量）、`a1601d62…`（开放单片实体化失败）、`96f36d7a…`（第二次加厚）、
  `588cc529…`（组 B 构建）、`e125502f…`（2 mm 加厚）；三次预受理拒绝未产生 job。

## 构造的组与逐片读数

两张互相垂直的 `surface_loft`（各 40×20 直纹面）加一张 40×40 的 `surface_fill`：

| 名称 | 构造 | quilt id | 面积 mm² | `closed` | 面数 | bbox mm |
| --- | --- | --- | --- | --- | --- | --- |
| `loft_a` | XY 两条 40 mm 直线，z=0/20 → 平面 y=0 | 61 | 800.0 | false | 1 | `[0,0,0]..[40,0,20]` |
| `loft_b` | XY 两条 40 mm 直线，x=40 → 平面 x=40 | 88 | 800.0 | false | 1 | `[40,0,0]..[40,40,20]` |
| `floor` | XY 40×40 矩形填充 | 136 | 1600.0 | false | 1 | `[0,0,0]..[40,40,0]` |

三片合计 **3200 mm²**，逐片 `ProQuiltVolumeEval` 均为开放面。构建作业 `30696732…` 报告
`saved_file_reloaded_and_verified=true`，随后 `creo_inspect_model` 读到的 id/面积与构建回执一致。

## 组级测量（`creo_measure_surface_group`）

测量 job `b4808ce3…`，参数 `tolerance_mm=0.01`、`gap_search_mm=1.0`，在已保存重载的模型上只读执行，
revision 1→1：

| 字段 | 实测 |
| --- | --- |
| `state` | **closed**（成员缝在容差内，不等于水密） |
| `boundary_edges` / `open_edges` / `joined_edges` | 12 / **6** / 6 |
| `gap_max_mm` | `2.465190328815662e-31`（数值 0） |
| `overlap` | `detected=false`、`overlap_area_mm2=0.0` |
| `boundary_closed` | **false**（开放片，非闭合壳体） |
| 单位 | `mm`，`length_scale_to_mm=1.0` |

四态判定为 `closed` 只说明三条成员缝（floor↔loft_a、floor↔loft_b、loft_a↔loft_b）在 0.01 mm 内接合；
外侧仍剩 6 条自由边，因此**不能**据此声称组是闭合实体。

## 加厚/实体化每条路径

### a. 直接对单片 `thicken`

| 厚度 | job | 加厚前/后体积 mm³ | 解析值 | 板厚读回 | 实体 | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.3 mm（组 A，`loft_a`） | `c831e45a…` | 0.0 → **239.99999999999994** | 800×0.3=240 | body bbox y 跨距 **0.3**（−0.15..0.15） | 1 体、6 面 | **true** |
| 2 mm（组 B，`loft_a`） | `e125502f…` | → **1599.9999999999995** | 800×2=1600 | body bbox y 跨距 **2.0**（−1..1） | 1 体、6 面 | **true** |

`surface_count=6` 表示加厚结果是闭合薄板（上下两面 + 四侧壁）；体积与“面积×厚度”一致（差 <1e-9）。
板厚读回来自 `creo_inspect_model` 的 `bodies[].bbox`（模型单位 mm），不是回显请求值。

**加厚不消耗 quilt**：0.3 mm 加厚后 `loft_a` 仍为 quilt 61、面积 800.0，但 `closed` 由 false 变为 true
（`ProQuiltVolumeEval` 此时可测）。`loft_b`/`floor` 仍为开放面。三片 id/面积在两次加厚后完全不变。

### b. 多片整体实体化 / 加厚：均在提交前或原生入口拒绝

| 尝试 | 入口 | 结果 |
| --- | --- | --- |
| `solidify.reference=[3 个 quilt]` | 公开 `creo_execute_plan` | `isError=true`、**无 job_id**；Pydantic `Input should be a valid dictionary … input_type=list` |
| `thicken.reference=[3 个 quilt]` | 公开 `creo_execute_plan` | `isError=true`、**无 job_id**；同上 |
| `quilt_merge` 两片 | 公开 `creo_execute_plan` | `isError=true`、**无 job_id**；`Not available in the 0.18.3 release; no native job was queued …` |
| 单片 `solidify`（开放 `loft_b`，job `a1601d62…`） | 原生 | 作业 `failed`，`solidify requires a closed quilt; the referenced quilt is open (ProQuiltVolumeEval=-18, quilt_is_open)`，`rollback_succeeded=true`，revision 2→2，quilt 未变 |

即：公开入口只接受**单片 quilt**；同计划多片引用在受理前被 schema 拒绝，merge 在受理前被能力门禁拒绝，
而单片成员本身是开放面，`solidify` 在原生入口也会被闭合判据拒绝并回滚。

### c. 产生的闭合实体与解析值

两条加厚路径都产生**闭合薄板实体**，但它们是各自一片的板，而不是整个组的一张闭合壳：

- 体积：0.3 mm → 240.000 mm³；2 mm → 1600.000 mm³（容差 ±0.5，实测差 <1e-12）。
- 闭合性：body `surface_count=6`，`bbox` 在法向跨距等于请求厚度（0.3 / 2.0 mm）。
- 组本身：`boundary_closed=false`、`open_edges=6`，开口边没有被任何一步封住。

## 保存-重载-再编辑

- 0.3 mm 加厚作业 `c831e45a…` 自身 `saved_file_reloaded_and_verified=true`；重载后 quilt 61/88/136 的
  id 与面积不变，`loft_a.closed` 变 true。
- 重载后对**仍是开放的**两片（`loft_b`+`floor`）再测组：job `d0fdabe2…`，revision 2，
  `state=closed`、`boundary_edges=8`、`open_edges=6`、`joined_edges=2`、`gap_max=0.0`，
  与移除已加厚成员后的拓扑一致。
- **限制（实测）**：把已加厚的 `loft_a` 重新放进组再测，工具直接拒绝：
  `surface_group_measure could not visit the group boundary: contour_edge_visit_failed`
  （`isError=true`、无 job_id）。组级测量只能覆盖尚未并入实体的开放 quilt。
- 同一模型再做一次 `thicken`（`loft_b` 2 mm，job `96f36d7a…`）成功并保存重载：体积
  **239.99999999999994 → 1836.9999999999982 mm³**。naive 相加 1840 mm³，差值 3 mm³ 恰为两块对称薄板
  在共享竖边处 1×0.15×20 mm 的体积重叠；最终 1 个 active body、`surface_count=10`、bbox
  `[0,−0.15,0]..[41,40,20]`。说明内核把两次加厚并成同一实体，重复体积只计一次。
- 最终三片 quilt 仍在模型中（id/面积不变），`loft_a`/`loft_b` 报 `closed=true`，`floor` 仍为开放面。

## 可行边界结论（merge 关闭时）

**可以做：**

1. 用现有 `surface_loft` + `surface_fill` 构造多片独立 quilt 组，逐片读面积/开放性与 quilt id；
2. 用 `creo_measure_surface_group` 得到组级 `open_edges`/`gap_max`/`overlap` 与四态，并区分
   “成员缝接合（closed）”和“外边界水密（boundary_closed）”；
3. 对**单片** quilt 做 0.3 mm / 2 mm 加厚，得到闭合薄板，体积等于面积×厚度，保存重载与后续再加厚均可用；
4. 多片分别加厚后，内核可把它们并成同一 body，重叠体积只计一次（本例 1837 mm³）。

**必须等 merge：**

1. 把多片变成**一张**结果 quilt（`quilt_merge` 仍 gated，`ProMerge` 树只产 4 个 `PRO_SURFACE`、0 quilt）；
2. 对整组做一次 `solidify`/`thicken`（公开入口只收单片；多片引用在受理前被拒）；
3. 对组做闭合性/水密判定与“整体开口面”收口——当前组级测量只能说成员缝状态，`boundary_closed=false`；
4. 已加厚成员不能再参与组级测量（`contour_edge_visit_failed`），因此“先加厚再整体补面”的链也走不通。

所以五爪类任务在 merge 关闭时可走到“多片独立建模、组级缝隙检查、逐片加厚成多块板并合并为一个 body”，
**不能**走到“整组一次实体化/一张闭合 quilt”。本轮不声称瓶底最终可实体化。

## 未覆盖

- Creo 9 / Creo 10；非 mm 单位；非平面或弯曲成员的三片组。
- 0.3 mm 壁厚整瓶（筒身+五爪+瓶底）全链；五爪阵列与瓶底收口仍依赖 merge 或新的原生路线。
- 已加厚成员重新进入组级测量的失败属于当前实现边界，未定位到可绕过的原生路线；未尝试修改产品代码。
- WorkBuddy 黑盒验收未执行（本轮为开发者实机证据）。
