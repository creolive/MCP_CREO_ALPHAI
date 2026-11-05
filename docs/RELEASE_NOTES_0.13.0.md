# MCP_CREO_MechDog 0.13.0 版本说明

2026-11-05，MINOR；条目：[FEAT-039](work-items/FEAT-039.md)（曲面链 S02 修剪 / S03 join 取证 / S04 投影曲线 / S05 曲面扫掠 / S06 实体化判据 / S08 完整链路与示例），随附 [DEV-045](work-items/DEV-045.md)（发布附件校验）与 [DEV-067](work-items/DEV-067.md)（规划与审计记录）。

新增两个公开算子：`creo_surface_trim`（曲面修剪 / use-quilt）与 `creo_project_curve`（曲线投影到 quilt），公开工具由 97 增至 **99**。两者均在 2026-11-04 本机 Creo 12.4.0.0 上完成实机验收后解除门禁。

- `keep_side` 语义已由实机测定：`one` 保留工具面法向正侧，`two` 保留负侧。40×20 平面填充（800 mm²）被 x=5 基准面修剪后分别为 700 mm²（外框 x∈[5,40]）与 100 mm²（x∈[0,5]）；圆柱曲面（1256.64 mm²）被 z=5 平面修剪后分别为 314.16 mm² 与 942.48 mm²；两次均 `saved_file_reloaded_and_verified=true`。
- 修复保留侧不生效：原实现只让 `PRO_E_PRIMARY_QLTSIDE` 跟随 `keep_side`，`PRO_E_MATERIAL_SIDE` 固定为 ONE，实机两侧得到同一区域；现在两个元素同时跟随 `keep_side`，不允许互相矛盾。
- 修复基准面引用被静默改写：`{kind:'datum_plane',label:...}` 的标签会被几何解析丢弃，默认轴过滤选中 TOP，修剪随后停在 `PRO_FEAT_UNREGENERATED`。Python 契约与原生解析现在都拒绝在几何类引用上携带标签，指引用 `{kind:'datum_feature',label:...}`。
- 修剪再生失败改为可诊断：返回 `regeneration`（失败阶段、特征 ID 与状态、目标 quilt、工具种类、两侧枚举值、结果特征 quilt 访问码与 ID 列表），失败消息带同一组数值；已测得的面积字段在失败记录中保留。
- `creo_surface_trim` 的修剪工具在 quilt 与基准面之外新增**曲线**（`{kind:'curve',id:...}`），走 `ProTrim.h` 文档化的 Use Curve 变体；实机矩阵确认 `PRO_E_MATERIAL_SIDE` 决定保留侧、保留侧相对曲线方向，`kept_side_basis` 因而不报 `tool_normal` 而报 `side_reference='curve_direction'` 与 `tool_curve_id`。已知边界：用曲线修剪它自己依赖的那张 quilt（例如刚投影到其上的曲线）会在保存阶段失败并回滚，见 [G5 契约 §2.3.2](development/G5-NATIVE-CONTRACT.md)。
- 新增公开算子 `creo_project_curve`：把一个曲线沿显式方向投影到一个 quilt，返回真实 `curve_id`、`curve_length_mm` 与两个 `endpoints_mm`。SDK 中两族投影元素（`PRO_E_COPYTRIM_*`、`PRO_E_PROJ_CRV_*`）只有 ID 而无树文档，实测 7 个候选树全部被内核拒绝，因此实现走文档化的两步路线：先由源草图沿方向生成扫掠辅助面，再用 `ProDtmCrv.h` 的 INTERSECT 求交——扫掠面由源曲线本身生成，交线逐点等于投影，不是用曲面求交冒充。实机：源直线 (5,10,10)→(35,10,10) 沿 −Z 投到 z=0 的 40×20 面得 30.000 mm、(5,10,0)/(35,10,0)；半径 8 圆弧得 25.133 mm、(12,10,0)/(28,10,0)；目标在请求背侧时按实测理由拒绝。辅助面作为真实父特征保留，其 ID 以 `helper_feature_id` 返回；方向必须与源草图平面法向平行，多分支或空投影一律失败而非挑选一条。
- `creo_solidify` 补齐判据并收紧输入：结果新增 `volume_before_mm3`、`volume_after_mm3` 与 `closure`（闭合性由 `ProQuiltVolumeEval` 实测，开放 quilt 返回 -18）；add 模式只接受一个 quilt 引用，body 引用在 schema 层被拒。实机：360° 旋转得到的闭合 quilt 实体化后体积 6283.185307179587 mm³（解析值 2000π），开放 quilt 在建特征前拒绝并回滚。
- 曲面偏置（S07）已公开 `creo_surface_offset`：按 `ProThicken.h` 的文档化规格（`PRO_USE_SURFS` 薄壁形式 + quilt 引用 + `PRO_E_THICKNESS` + 法向偏移方法 `PRO_OFFS_METH_NORMTOSURF` + 显式方向 `PRO_E_STD_USEQLT_SIDE`）沿法向偏置一张 quilt；回执的 `measured_offset_distance_mm` 由"建特征后体积 ÷ 源面积"实测，不是回显——40×20 偏置 5 mm 双侧实测：体积 **3999.9999999999995 mm³**、实测距离 **4.999999999999999 mm**、保存重载通过；此前 12 个候选树被拒的根因是挂错了父节点（偏置元素属于加厚/凸台树，见[G5 契约 §2.8f/§2.8g](development/G5-NATIVE-CONTRACT.md)）。`surface_trim` 的 `offset_mm`/`offset_side` 仍拒（本机只有 `ProTrim.h` 的 thin trim，实测不移动切口）。
- 曲面扫掠能力补齐实测证据：40×20 截面沿 20 mm 直线扫掠，开放曲面 2400.000 mm²、加盖曲面 4000.000 mm²（闭合）、实体化 15999.999999999998 mm³，统一驱动新增 `--case sweep_surface`（11 项实机通过，oracle 由几何参数推导）；多截面放样（边界混合）仍不可用，原因与实测见开发契约。
- 统一驱动新增两条完整曲面链用例（`--case chain_open`、`--case chain_closed`），实机分别 14 项与 12 项通过：开放链走填充→投影→曲线修剪→查询→对称加厚，闭合链走旋转闭合面→实体化→改写重生成→失败回滚；放样与缝合两步仍门禁并在用例里标注为 blocked。
- 端点焊接（W01）**本体已交付**：内核没有位移上限 API，显式点重合约束做不到受控，因此改为坐标规整——策略层给出焊接对，原生侧在写入实体前把每对端点各移动 gap/2（超上限则拒绝应用），求解后回读残差。实机：5e-5 mm 间隙 → 移动 2.4999999999941735e-05 mm（≤ 请求上限 1e-4）→ `max_residual_mm=0.0`；同一轮廓默认路径 `applied=false`。
- join 需求已可测量（算子仍门禁）：两张 40×20 填充面重叠 200 mm²，用共享边所在基准面（x=40）修剪出外侧 600 mm² → 并集面积 **1400 mm²**；两片各加厚 2 mm 合入同一 body → 体积 **2799.9999999999995 mm³**（简单相加是 3200 mm³，重叠只算一次），模型只有一个 body 且保存重载通过；统一驱动新增 `--case join`（13 项检查，连续三次复跑稳定）。`creo_quilt_merge` 本身仍为门禁状态：四条原生路线实测都建出 ACTIVE 特征（持有 4 个 `PRO_SURFACE`、0 个 `PRO_QUILT`），产出单一合并 quilt 仍需参照树。
- 新增两个可运行的曲面链示例 `examples/p12_surface_blade.json` 与 `examples/surface_trim_merge.json`：分阶段计划，id 用占位符声明（`$curve:<特征名>` 等，运行前按检查结果解析），统一驱动新增 `--example <file>`；离线条过 schema 且不碰门禁算子，实机逐阶段要求 `succeeded` 与 `saved_file_reloaded_and_verified=true`，两例实机三阶段全通过（修剪面积 800 → 600.000 mm²）。
- 端点焊接（W01）**仅策略层**交付：创建与更新算子共用 `endpoint_policy`（report/reject/weld）与 `max_endpoint_move_mm`，回执发布配对证据且不改几何；`weld` 策略被明确拒绝——实测草图 epsilon 不是端点重合容差（提到 2e-3 mm 后 5e-4 mm 间隙仍张开，而默认路径自己会合上 8.2e-7 mm），原生受控焊接未完成。
版本入口、两份种子清单与受信摘要同步至 **0.13.0**；种子包确定性重建 SHA256 为 `e5808ff18049f94a74436636c6633b1867aa487224567dc31738c644c8ad685b`（24 文件、9 种子），与两份清单一致，详见[发布记录](validation/RELEASE-0.13.0.md)。

验证命令为 `python tools/test_unit.py`（2384 项通过）、`python tools/dev_check.py --skip-unit`、`python bridge.py build`，外加实机 `build/_live_trim.py`、`python tools/test_surface_chain.py --case trim --live --confirm-session-usable`、`python tools/test_surface_chain.py --case project --live --confirm-session-usable`（run `20261104-134443-396700`，18 项检查全通过）与 `python tools/test_surface_chain.py --case solidify --live --confirm-session-usable`（run `20261104-145403-398500`，8 项检查全通过）。结果与受测源码身份见[发布记录](validation/RELEASE-0.13.0.md)。

本版实机验收覆盖修剪的再生、面积/位置、保存与重载，投影曲线的直线与圆弧用例、反向拒绝和保存重载，以及闭合曲面的体积判据与开放曲面的拒绝回滚；修剪结果在重载后被 `thicken` 消费、质心判据（本机无 quilt 质心查询，`signed_offset_mm` 保持 null）、失败回滚的实机表现、`use_curve` 投影—修剪串联、投影的多分支拒绝、圆柱/非平面目标与边界裁切，以及 `thicken` 与 cut 模式的体积字段均未验证。Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测；BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.13.0-source.zip` 与 `MCP_CREO_MechDog-0.13.0-seed-library.zip`，按安装说明更新环境并重启 MCP 服务。旧种子包会被版本闸门拒绝；本版新增一个公开工具，无回调注册变化、无参数迁移、无新增原生编译要求。
