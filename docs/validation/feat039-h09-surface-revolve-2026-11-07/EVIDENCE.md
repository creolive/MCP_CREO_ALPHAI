# FEAT-039/H09 旋转球面替代路线实机证据（2026-11-07）

## 结论

任意非平面闭合边界的 `surface_fill` 仍无原生路线（`FillOp` 只有 `sketch`，原生只有
`PRO_FEAT_DATUM_SURF` + `PRO_FLAT` + `PRO_E_SEC_USE_SKETCH`，没有任何 3D 闭环输入通道），本轮
**不放宽** planar fill 门禁，也没有新增算子。中心 R8 场景改用**已有的曲面旋转**交付：一条
半圆子午弧 + 一条构造中心线，`revolve{mode:"surface", angle:360}` 生成闭合球面 quilt，再用
`surface_trim` 切出球冠、`thicken` 加厚、`solidify` 实体化，全部经公开 MCP 工具实测并保存重载。

## 环境与命令

- Windows x64；Creo 12.4.0.0（用户手工启动的会话）；本机匹配 Toolkit SDK；单位 mm；单会话串行。
- 构建：`.\.venv\Scripts\python.exe bridge.py build`（退出 0；本轮无原生源码改动）。
- 离线条：`.\.venv\Scripts\python.exe tools\test_surface_revolve.py`（`passed=true`，12 项）。
- 实机：`.\.venv\Scripts\python.exe tools\test_surface_revolve.py --live --confirm-session-usable`
- run：`20261107-235346-03398b`；**22 项检查全部通过**（`passed=true`、`native_surface_revolve="verified"`），5 个作业。
- 报告：[live_surface_revolve_report.json](live_surface_revolve_report.json)，6864 B（LF 行尾），SHA256
  `1AA72913ACC957DA5AF8C30EC1695363801CBC32E15F3C18F4F6D16140BDCBD7`。

说明：首次实机运行（run `20261107-235241-dbd533`）所有几何读数与本报告一致，唯一失败项是驱动
自身的 `no_solid_created` 断言把 `state=3/no_geometry` 的空 body 当成实体；修正该断言（判据改为
`material`/`has_geometry`）后原样复跑，未改任何门禁、schema 或原生代码。

## 几何与读数

解析 oracle（代码内先定，运行后比较）：球面 4πR² = 804.247719318987 mm²；x=4 球冠
2πR(R−4) = 201.06192982974676 mm²；其余 603.1857894892403 mm²；球体积 4/3πR³ =
2144.660584850632 mm³；2 mm 对称加厚的精确球壳体积 406.31264986427993 mm³。面积容差
±0.5 mm²，体积容差 ±2%（相对）。

| 步骤 | job_id | 实测 |
| --- | --- | --- |
| 半圆绕 X 中心线 360° 旋转成曲面 | `a2f0728c9fe64fee85184092aebae918` | 作业成功、`saved_file_reloaded_and_verified=true`、rev 1；特征 49 `type=942`（datum surface）`status=0`（ACTIVE）；quilt **74**、2 个成员面、bbox `[-8,-8,-8]..[8,8,8]`、`closed=true`、面积 **804.247719319002 mm²**（与 oracle 差 1.5e-11 mm²）；body `material=false`，未产生实体 |
| 基准面 x=4 修剪，`keep_side="one"` | `98d2c06424274ee499c95347cff1c10b` | 作业成功、保存重载 true、rev 2；保留面积 **201.06192982974773 mm²**（球冠，与 oracle 差 9.7e-13 mm²）；保留 quilt 可在模型 quilt 列表按面积查回（`quilt_id=74`，同目标 quilt 被就地修剪） |
| 球冠 2 mm 对称加厚 | `6a1319b229f44ecf98c1ec11e51dabf5` | 作业成功、保存重载 true、rev 3；体积 **404.21825476170756 mm³** = 精确球壳 −0.52%，`面积×厚度` 402.12385965949545 mm³ +0.52%，落在两个 oracle 之间 |
| 同一刀另一侧，`keep_side="two"`（独立模型） | `2615afb025964e9bb1a71ddfd6e09615` | 作业成功、rev 1；保留面积 **603.1857894892481 mm²**；两侧之和 804.2477193190 mm² |
| 闭合球面 `solidify`（独立模型） | `4703a3909b1c4d0bb1ed445628cb38ad` | 作业成功、rev 1；体积 **2144.6605848506724 mm³**（与 4/3πR³ 相对差 ~2e-14），独立证明该 quilt 闭合 |

加厚的两个 oracle 都列出：对称加厚在曲面上并不等于两个同心球面的严格差分，实测值同时偏离
理论球壳与 `面积×厚度` 约 0.52%；驱动在运行前固定 2% 相对容差，不按结果回头放宽。

## 非平面闭合边界 fill 的拒绝证据

实机先提交一条带 3D 边界的计划（未建任何几何）：`creo_execute_plan` 返回 `isError=true`、无
`job_id`，原文为 `operations.0.surface_fill.sketch Field required` 与
`operations.0.surface_fill.boundary Extra inputs are not permitted`。离线同一拒绝：
`boundary`/`edges`/`sections` 三种 3D 闭环写法全部在 `validate_operations` 阶段失败，
`FillOp.model_fields == {op, label, sketch}`。因此 planar fill 的行为与门禁保持不变。

## 路线依据

- 现有 `native/generic.cpp::extrude_or_revolve` 在 `mode="surface"` 时写
  `PRO_E_FEATURE_TYPE=PRO_FEAT_DATUM_SURF`、`PRO_E_FEATURE_FORM=PRO_REVOLVE`、
  `PRO_E_EXT_SURF_CUT_SOLID_TYPE=PRO_EXT_FEAT_TYPE_SURFACE`；缺省 `axis` 时用草图内唯一中心线
  （`PRO_REV_AXIS_INT_REF`），显式轴走 `PRO_E_REVOLVE_AXIS_OPT=PRO_REV_AXIS_EXT_REF` 并回报实测轴 id。
- `mode="surface"` 不进入实体轮廓闭合校验（`schema.py` 只对非 surface / 非 thin 的
  extrude/revolve 调 `validate_solid_profile`），所以开放子午弧可用于球面；实体旋转仍要求闭合轮廓。
- `surface_trim` / `thicken` / `solidify` / `inspect_model` 的 quilt 与面积/闭合读数全部复用既有实现。

## 未覆盖

- Creo 9 / Creo 10；非 mm 单位；部分角度（90° 球带）实机；显式外部基准轴旋转；非 X 轴/倾斜轴。
- 任意非平面闭合边界 fill：仍不可用，未做新原生路线、未放宽 planar fill。
- 0.3 mm 壁厚整链、球冠边缘的加厚失败/自交边界、多 quilt 组合（H10 范围）。
- 只读 `creo_capabilities` / 拒绝路径不产生作业，因此没有对应 job_id。
