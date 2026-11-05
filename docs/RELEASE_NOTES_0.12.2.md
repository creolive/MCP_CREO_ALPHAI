# MCP_CREO_MechDog 0.12.2 版本说明

2026-11-04，MINOR；条目：[FEAT-039](work-items/FEAT-039.md)（曲面链 S02 修剪 / S04 投影曲线 / S06 实体化判据），随附 [DEV-045](work-items/DEV-045.md)（发布附件校验）与 [DEV-067](work-items/DEV-067.md)（规划与审计记录）。

新增两个公开算子：`creo_surface_trim`（曲面修剪 / use-quilt）与 `creo_project_curve`（曲线投影到 quilt），公开工具由 97 增至 **99**。两者均在 2026-11-04 本机 Creo 12.4.0.0 上完成实机验收后解除门禁。

- `keep_side` 语义已由实机测定：`one` 保留工具面法向正侧，`two` 保留负侧。40×20 平面填充（800 mm²）被 x=5 基准面修剪后分别为 700 mm²（外框 x∈[5,40]）与 100 mm²（x∈[0,5]）；圆柱曲面（1256.64 mm²）被 z=5 平面修剪后分别为 314.16 mm² 与 942.48 mm²；两次均 `saved_file_reloaded_and_verified=true`。
- 修复保留侧不生效：原实现只让 `PRO_E_PRIMARY_QLTSIDE` 跟随 `keep_side`，`PRO_E_MATERIAL_SIDE` 固定为 ONE，实机两侧得到同一区域；现在两个元素同时跟随 `keep_side`，不允许互相矛盾。
- 修复基准面引用被静默改写：`{kind:'datum_plane',label:...}` 的标签会被几何解析丢弃，默认轴过滤选中 TOP，修剪随后停在 `PRO_FEAT_UNREGENERATED`。Python 契约与原生解析现在都拒绝在几何类引用上携带标签，指引用 `{kind:'datum_feature',label:...}`。
- 修剪再生失败改为可诊断：返回 `regeneration`（失败阶段、特征 ID 与状态、目标 quilt、工具种类、两侧枚举值、结果特征 quilt 访问码与 ID 列表），失败消息带同一组数值；已测得的面积字段在失败记录中保留。
- `creo_surface_trim` 的修剪工具在 quilt 与基准面之外新增**曲线**（`{kind:'curve',id:...}`），走 `ProTrim.h` 文档化的 Use Curve 变体；实机矩阵确认 `PRO_E_MATERIAL_SIDE` 决定保留侧、保留侧相对曲线方向，`kept_side_basis` 因而不报 `tool_normal` 而报 `side_reference='curve_direction'` 与 `tool_curve_id`。已知边界：用曲线修剪它自己依赖的那张 quilt（例如刚投影到其上的曲线）会在保存阶段失败并回滚，见 [G5 契约 §2.3.2](development/G5-NATIVE-CONTRACT.md)。
- 新增公开算子 `creo_project_curve`：把一个曲线沿显式方向投影到一个 quilt，返回真实 `curve_id`、`curve_length_mm` 与两个 `endpoints_mm`。SDK 中两族投影元素（`PRO_E_COPYTRIM_*`、`PRO_E_PROJ_CRV_*`）只有 ID 而无树文档，实测 7 个候选树全部被内核拒绝，因此实现走文档化的两步路线：先由源草图沿方向生成扫掠辅助面，再用 `ProDtmCrv.h` 的 INTERSECT 求交——扫掠面由源曲线本身生成，交线逐点等于投影，不是用曲面求交冒充。实机：源直线 (5,10,10)→(35,10,10) 沿 −Z 投到 z=0 的 40×20 面得 30.000 mm、(5,10,0)/(35,10,0)；半径 8 圆弧得 25.133 mm、(12,10,0)/(28,10,0)；目标在请求背侧时按实测理由拒绝。辅助面作为真实父特征保留，其 ID 以 `helper_feature_id` 返回；方向必须与源草图平面法向平行，多分支或空投影一律失败而非挑选一条。
- `creo_solidify` 补齐判据并收紧输入：结果新增 `volume_before_mm3`、`volume_after_mm3` 与 `closure`（闭合性由 `ProQuiltVolumeEval` 实测，开放 quilt 返回 -18）；add 模式只接受一个 quilt 引用，body 引用在 schema 层被拒。实机：360° 旋转得到的闭合 quilt 实体化后体积 6283.185307179587 mm³（解析值 2000π），开放 quilt 在建特征前拒绝并回滚。
- 曲面偏置（S07）未公开：`surface_trim` 的 `offset_mm`/`offset_side` 字段保留在契约里，但请求在排队前被拒。本机 SDK 只有 `ProTrim.h` 的 thin trim 偏置树（无独立偏置 quilt 特征树），实测请求 5 mm 偏置时作业成功但切口不移动（保留面积仍 400/400 mm²），50 mm 的必不相交偏置也不被拒绝，因此距离无法兑现，见 [G5 契约 §2.7](development/G5-NATIVE-CONTRACT.md)。
- 曲面扫掠能力补齐实测证据：40×20 截面沿 20 mm 直线扫掠，开放曲面 2400.000 mm²、加盖曲面 4000.000 mm²（闭合）、实体化 15999.999999999998 mm³，统一驱动新增 `--case sweep_surface`（11 项实机通过，oracle 由几何参数推导）；多截面放样（边界混合）仍不可用，原因与实测见开发契约。
- 统一驱动新增两条完整曲面链用例（`--case chain_open`、`--case chain_closed`），实机分别 14 项与 12 项通过：开放链走填充→投影→曲线修剪→查询→对称加厚，闭合链走旋转闭合面→实体化→改写重生成→失败回滚；放样与缝合两步仍门禁并在用例里标注为 blocked。
- `creo_quilt_merge` 仍为门禁状态，未公开。版本入口、两份种子清单与受信摘要同步至 **0.12.2**；种子包确定性重建 SHA256 为 `044f1da0f78c52cf3fe11993486184063ceafac82615e77c28a02368f17ea2eb`（24 文件、9 种子），与两份清单一致，详见[发布记录](validation/RELEASE-0.12.2.md)。

验证命令为 `python tools/test_unit.py`（2384 项通过）、`python tools/dev_check.py --skip-unit`、`python bridge.py build`，外加实机 `build/_live_trim.py`、`python tools/test_surface_chain.py --case trim --live --confirm-session-usable`、`python tools/test_surface_chain.py --case project --live --confirm-session-usable`（run `20261104-134443-396700`，18 项检查全通过）与 `python tools/test_surface_chain.py --case solidify --live --confirm-session-usable`（run `20261104-145403-398500`，8 项检查全通过）。结果与受测源码身份见[发布记录](validation/RELEASE-0.12.2.md)。

本版实机验收覆盖修剪的再生、面积/位置、保存与重载，投影曲线的直线与圆弧用例、反向拒绝和保存重载，以及闭合曲面的体积判据与开放曲面的拒绝回滚；修剪结果在重载后被 `thicken` 消费、质心判据（本机无 quilt 质心查询，`signed_offset_mm` 保持 null）、失败回滚的实机表现、`use_curve` 投影—修剪串联、投影的多分支拒绝、圆柱/非平面目标与边界裁切，以及 `thicken` 与 cut 模式的体积字段均未验证。Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测；BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.12.2-source.zip` 与 `MCP_CREO_MechDog-0.12.2-seed-library.zip`，按安装说明更新环境并重启 MCP 服务。旧种子包会被版本闸门拒绝；本版新增一个公开工具，无回调注册变化、无参数迁移、无新增原生编译要求。
