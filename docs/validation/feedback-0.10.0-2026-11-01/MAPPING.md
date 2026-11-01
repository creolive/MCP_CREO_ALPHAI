# 0.10.0 晚间反馈逐章映射（Q00 归档与登记）

日期：2026-11-01（Asia/Shanghai）。基线提交 **`eb913de`**（0.11.0 / 95 个公开工具，上游 `main@2f6aab7`），归档分支 `codex/q00-feedback-archive`。

本轮只做归档、登记与入口对账：未连接 Creo/MCP，未跑产品测试，未改产品代码，未改版本或发布。十件原件逐字节复制，逐件长度、SHA256 与全字节比对 **10/10 一致**；完整路径、字节数与 SHA256 见 [manifest](manifest.json)。

**05 的 recolor_assembly zip 只整体归档**：未解包、未执行、未并入代码。其内置文本仅作来源引用，条目清单见下方 F06 行。

本表是 Q02—Q15 的唯一归属依据（来源章节 → Q 任务 → 固定 ID → 负责人）。各 Q 任务的范围、验收与环境以对应工作卡为准；本表只给归属。

## 逐件清单

| ID | 原件 | 归档相对路径 | 字节 | SHA256（前 12 位） |
| --- | --- | --- | --- | --- |
| F01 | 反馈包说明 | `originals/00_README_反馈包.md` | 2819 | `a944edb0cf6a` |
| F02 | 0.10.0 验收报告 | `originals/01_验收报告_0.10.0.md` | 11656 | `cc832dc43374` |
| F03 | G5 曲面能力方案 | `originals/02_G5曲面能力方案.md` | 9373 | `dbf16b25ae02` |
| F04 | BUG-094 报告（L1/L2） | `originals/03_BUG094报告.md` | 6510 | `fcc63d18454b` |
| F05 | generic.cpp 补丁提取 | `originals/04_generic_cpp_patches.md` | 4918 | `8c43f5b7f6be` |
| F06 | 上色建议包（zip 原包） | `originals/05_上色能力建议包_recolor_assembly.zip` | 11451 | `f3990bc86fa8` |
| F07 | P12 族表 | `originals/06_P12_v12_配方/family_table.json` | 253 | `21b054daf2a3` |
| F08 | P12 逐站棱柱配方 | `originals/06_P12_v12_配方/p12_v12_native_recipe.json` | 466 | `d93951d3843d` |
| F09 | P12 391 项特征树 | `originals/06_P12_v12_配方/p12_v12_native_tree.json` | 101487 | `891ac8369877` |
| F10 | 三点定面最小复现 | `originals/06_P12_v12_配方/smoke_3pt_min_repro.json` | 833 | `3a3f90ee8492` |

F06 内置条目（只列来源，未提取到磁盘）：`README.md` 7864 B、`RESULT.md` 1013 B、`recolor_worker.cpp` 8026 B、`verify_color.cpp` 2925 B、`build_recolor.cmd` 1663 B、`build_verify.cmd` 1592 B、`family_table.json` 253 B、`comp_family.json` 1203 B。其中 zip 内 `family_table.json` 与 F07 **SHA256 完全相同**（`21b054daf2a3…`），可作交叉核对。

## 来源章节 → Q 任务 → 固定 ID → 负责人

| 来源章节 | 内容要点 | Q 任务 | 固定 ID | 负责人 |
| --- | --- | --- | --- | --- |
| F01 §包内清单与三份材料关系 | 四份报告 + 两份补丁 + 配方工件的关系说明 | Q00 | [DEV-054](../../work-items/DEV-054.md)（本次维护） | unassigned |
| F01 §一页速览 1（A + D 一起修） | coordinates 位移拒绝与 autodim 静默失真是同一处比对逻辑两面 | Q02 | [FEAT-010](../../work-items/FEAT-010.md) / [BUG-049](../../work-items/BUG-049.md) | 写程序高手 |
| F01 §一页速览 2（E） | 失败事务里擦除孤儿会话对象 | Q03 | [BUG-096](../../work-items/BUG-096.md)（本次新登记） | 代码编写者 |
| F01 §一页速览 3（BUG-094） | `errors(es)` 带回 `ProErrorlist`；L1 补丁可直接并入 | Q06 | [BUG-097](../../work-items/BUG-097.md)（本次新登记） | unassigned |
| F01 §一页速览 4（N1/N2） | stage 冻结在真实失败阶段；busy 建议间隔 | Q04 | [FEAT-033](../../work-items/FEAT-033.md) | codex代码 |
| F01 §一页速览 5（N3 上色） | `recolor_assembly` 建议 | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（已随 0.11.0 交付） | unassigned |
| F01 §一页速览 6（G5 三 op + `thru_points`） | 曲面三 op 元素树路线与三点定面 | Q05 / Q07—Q10 | [FEAT-053](../../work-items/FEAT-053.md)（本次新登记）/ [FEAT-009](../../work-items/FEAT-009.md) / [FEAT-039](../../work-items/FEAT-039.md) | unassigned |
| F01 §复现环境 | 外部环境为 Windows 11 x64 / Creo 10.0.0.0 / 0.10.0 / MSVC 14.44 | Q00 | 外部环境归属，见下方缺件表 | unassigned |
| F02 §复测结论速览表 | 上轮 A—H 逐条在 0.10.0 的状态 | Q14 | 见下方 A—H 各行 | unassigned |
| F02 §A | coordinates 对 0.0017 mm 求解位移仍整轮廓拒绝，偏差逐位相同 | Q02 | [FEAT-010](../../work-items/FEAT-010.md) / [BUG-049](../../work-items/BUG-049.md) | 写程序高手 |
| F02 §D | autodim 静默改几何，成形面积 −0.90 %，仍无 deviation 告警 | Q02 | [FEAT-010](../../work-items/FEAT-010.md) | 写程序高手 |
| F02 §E | 失败作业仍占用模型名，无释放路径，只能改名绕过 | Q03 | [BUG-096](../../work-items/BUG-096.md)（本次新登记；交叉关联 BUG-012（[台账](../../BACKLOG.md#输入或规则待核实)行，无独立工作卡）/ [FEAT-018](../../work-items/FEAT-018.md)，只关联不重开旧档） | 代码编写者 |
| F02 §B | round 面组对凹圆棱失败（本轮未复测） | Q14 | [FEAT-051](../../work-items/FEAT-051.md) / [FEAT-008](../../work-items/FEAT-008.md)（面配对选棱用法）；有证据后再登记原 ID 或新 ID | unassigned |
| F02 §C | coordinates 不支持 spline（本轮未复测） | Q14 | [FEAT-010](../../work-items/FEAT-010.md) | unassigned |
| F02 §F | 大计划回显无节制（本轮未复测） | Q13 | [FEAT-008](../../work-items/FEAT-008.md) / [BUG-088](../../work-items/BUG-088.md) | unassigned |
| F02 §G | 正交性闸 1e-6 无归一化（本轮未复测） | Q14 | [FEAT-012](../../work-items/FEAT-012.md) / [BUG-045](../../work-items/BUG-045.md) | unassigned |
| F02 §H | 装配预览被基准淹没（本轮未复测） | Q13 | [FEAT-008](../../work-items/FEAT-008.md) / [BUG-088](../../work-items/BUG-088.md) | unassigned |
| F02 §N1 | `stage` 在必败作业上仍推进到 `executing_feature_plan` | Q04 | [FEAT-033](../../work-items/FEAT-033.md) | codex代码 |
| F02 §N2 | `retry_after_seconds: 1` 与 `session_status` 实际 2—4 s 占用不匹配 | Q04 | [FEAT-033](../../work-items/FEAT-033.md) | codex代码 |
| F02 §N3 | 0.10.0 无 appearance/color API，80 组件按族上色不可表达 | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（已交付，不重复开发） | unassigned |
| F02 §0.10.0 确实变好的 1（端点诊断） | `max_endpoint_gap_mm` 等已落地 | Q15 | [BUG-049](../../work-items/BUG-049.md)（已交付观察项，不重新登记） | unassigned |
| F02 §0.10.0 确实变好的 2（弧回显） | `arc_geometry[]` 补 `center_uv`/`radius_mm` | Q15 | [FEAT-034](../../work-items/FEAT-034.md)（同上） | unassigned |
| F02 §0.10.0 确实变好的 3（切除体积回执） | `cut_bore` 回包带 `material_removed_mm3` | Q15 | [FEAT-035](../../work-items/FEAT-035.md)（同上） | unassigned |
| F02 §0.10.0 确实变好的 4（空场景预览） | preview 正常写出，`window_matches_model: true` | Q15 | [BUG-088](../../work-items/BUG-088.md)（同上；空件必失败仍在开放范围） | unassigned |
| F02 §0.10.0 确实变好的 5（作业吞吐） | 8 操作 68 s，与 0.9.0 同规模相当 | Q15 | [FEAT-033](../../work-items/FEAT-033.md)（同上） | unassigned |
| F02 §对"风扇叶片 L2 方案"的影响评估 | 放样→投影→剪裁→加厚链仍无法表达；81 点折线叶片体积 6 450 293 mm³ 偏差主因是叶片曲面缺失 | Q11 / Q07—Q10 | DEV-053 场景；[FEAT-039](../../work-items/FEAT-039.md) / [FEAT-009](../../work-items/FEAT-009.md) | unassigned |
| F02 §给作者的处理优先级建议 | A+D 一起修 → E → N1/N2/N3 → B/C/F/G/H 维持 | Q00 | 无独立 ID，作为本表排序依据 | unassigned |
| F02 §复现索引 | 4 个 job 目录编号（`817537af…`、`27008cce…`、`8d010499…`、`7f70073c…`） | Q00 | 缺件项，见下方缺件表 | unassigned |
| F03 §0 结论摘要表 | 曲面放样/投影/剪裁三个缺口；任意平面草图受限；对称加厚已具备 | Q07—Q10 | [FEAT-009](../../work-items/FEAT-009.md) / [FEAT-039](../../work-items/FEAT-039.md) / [FEAT-053](../../work-items/FEAT-053.md) | unassigned |
| F03 §1 现状核实 | `creo_loft` 仅 `mode=add` 且强制 MCP 自有 XY 草图；`extrude` 已有 surface 模式；`thicken` 已有 | Q07 | [FEAT-009](../../work-items/FEAT-009.md) / [FEAT-039](../../work-items/FEAT-039.md) | unassigned |
| F03 §2 `surface_loft` 元素树 | `PRO_E_BLEND_SECTIONS` + `PRO_E_BLEND_ATTRIBUTES`；回执 `surface_area_mm2` | Q08 | [FEAT-009](../../work-items/FEAT-009.md) | unassigned |
| F03 §3 `project_curve` + `surface_trim` | `PRO_E_COPYTRIM_*` 元素族 1630—1634；`curve_length_mm`、端点、`kept_side` | Q09 / Q10 | [FEAT-039](../../work-items/FEAT-039.md) | unassigned |
| F03 §4 `datum_plane` 三点定面 | `PRO_DTMPLN_THRU` 可接受 `PRO_POINT`；一行级补丁解锁逐站棱柱路线 | Q05 | [FEAT-053](../../work-items/FEAT-053.md)（本次新登记，关联 [FEAT-008](../../work-items/FEAT-008.md)） | unassigned |
| F03 §5 回执与验收钩子 | v1.2 五条判别性验收所需读数 | Q07—Q10 / Q11 | [FEAT-009](../../work-items/FEAT-009.md) / [FEAT-039](../../work-items/FEAT-039.md) | unassigned |
| F03 §6 优先级与工作量 | 四步顺序与"0.5 天无风险"估计 | Q07 | 不作排期承诺，见 Q07 卡片 | unassigned |
| F03 §7 验证材料 | `p12_v12_native_tree.json` 391 项；`p12_v12_ops_a1.json` 未附 | Q11 | DEV-053 场景 | unassigned |
| F04 §一 摘要（L1/L2 两层） | L1：`ProSectionLocationGet` 在斜面 incomplete 阶段返回单位阵 → 世界 XY 被当 UV 写入；L2：UV 正确后 `ProFeatureWithoptionsRedefine` 仍 −1 | Q06 | [BUG-097](../../work-items/BUG-097.md)（本次新登记，关联 [FEAT-010](../../work-items/FEAT-010.md) / [BUG-087](../../work-items/BUG-087.md) / [BUG-095](../../work-items/BUG-095.md)） | unassigned |
| F04 §二 复现最小用例 | 3 个 `datum_points` + 三点 `datum_plane` + 斜面 `sketch` + 对称拉伸；三次独立运行一致 | Q05 / Q06 | [FEAT-053](../../work-items/FEAT-053.md) / [BUG-097](../../work-items/BUG-097.md) | unassigned |
| F04 §三 L1 细节与已验证修复 | 单位阵判定后改用 frame.u/v 基点积，`LINE_tri_0` 由错值修正为 `(0,0)→(190.38,22.39)` | Q06 | [BUG-097](../../work-items/BUG-097.md)（外部直改结果不算主干修复，须本仓库取证） | unassigned |
| F04 §四 L2 剩余层 | 已排除截面质量/坐标锚/再生时机；建议在 `errors(es)` 处带回 `ProErrorlist` | Q06 | [BUG-097](../../work-items/BUG-097.md) | unassigned |
| F04 §五 对 P12/下游影响与替代路径 | L1 是普适收益；L2 未修前两条路线同卡一处；主平面工作流不受影响 | Q11 | DEV-053 场景 | unassigned |
| F04 §六 建议 | 并入 L1、并入 `thru_points`、透传 `ProErrorlist`、中期补三 op | Q05 / Q06 / Q07 | [FEAT-053](../../work-items/FEAT-053.md) / [BUG-097](../../work-items/BUG-097.md) / [FEAT-009](../../work-items/FEAT-009.md) | unassigned |
| F04 §七 本包工件 | `smoke_3pt.json` / `smoke_3pt_b~f` 运行记录、`native.log` 关键行 | Q00 | 缺件项，见下方缺件表 | unassigned |
| F05 §补丁 1（`datum_plane` 三点定面） | 三个 `PRO_DTMPLN_THRU` 约束，逐个 `datum_point_feature` 解析 | Q05 | [FEAT-053](../../work-items/FEAT-053.md)（补丁来源，不直接并入） | unassigned |
| F05 §补丁 2（`sketch frame` UV 基回退） | `loc_is_identity` 时改用 frame 基投影 | Q06 | [BUG-097](../../work-items/BUG-097.md)（补丁来源，不直接并入） | unassigned |
| F05 §实测证据 | 三点定面几何与解析一致；UV 回退后一致；正确 UV 后 redefine 仍 −1 | Q05 / Q06 | [FEAT-053](../../work-items/FEAT-053.md) / [BUG-097](../../work-items/BUG-097.md)（外部环境旁证） | unassigned |
| F06 内置 README §一 需求 | 80 组件 / 12 族按族上色；对照 SolidWorks 侧 `recolor_assembly` | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（已交付） | unassigned |
| F06 内置 README §二 关键接口 | `ProMdlVisibleSideAppearancepropsSet/Get`、`ProAsmcompAsmitemInit`、`ProSolidFeatVisit` | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（已交付） | unassigned |
| F06 内置 README §三 两个坑 | `item_type` 必须传组件模型类型；组件→族映射不应依赖插入序 | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（已交付；外部实现与主干实现分别归属） | unassigned |
| F06 内置 README §四 / RESULT.md 实测 | 外部 80/80 上色、读回 12 族逐项一致、`.asm` 版本号递增 | Q12 | [FEAT-052](../../work-items/FEAT-052.md)（主干实机 28/28，非本包证据） | unassigned |
| F06 内置 `recolor_worker.cpp` / `verify_color.cpp` / `build_*.cmd` | 外部上色源码与构建脚本 | Q12 | 不并入代码；仅作来源对照 | unassigned |
| F06 内置 `comp_family.json` / `family_table.json` | 80 项组件→族映射与族计数 | Q12 / Q11 | [FEAT-052](../../work-items/FEAT-052.md) / DEV-053 场景 | unassigned |
| F07 P12 族表 | 80 项族计数数组（和 481） | Q11 | DEV-053 场景；索引映射须有来源证明 | unassigned |
| F08 P12 逐站棱柱配方 | 48 带 × 4 特征 = 196；声明 `thru_points` 补丁需求与"当前 MCP 不可行"原因 | Q11 | DEV-053 场景；与 F09 的 391 口径不同，见下方核对 | unassigned |
| F09 P12 391 项特征树 | 实为 48 带 × 8 特征 + 7 项轮毂/阵列/倒角/镗孔；96 个含 3 点的 `datum_points`；96 个 `datum_plane` 的 `thru_points` 引用点名 `p_a/p_b/p_c` 而非特征标签 | Q11 | DEV-053 场景；拆分与占位转换口径见 Q11 卡片 | unassigned |
| F10 三点定面最小复现 | `datum_points`×3 + 三点 `datum_plane` + 斜面 `sketch` + 对称拉伸 9.87008714331235 | Q05 / Q06 | [FEAT-053](../../work-items/FEAT-053.md) / [BUG-097](../../work-items/BUG-097.md) | unassigned |

## 本轮独立核对结果

| 核对项 | 结果 |
| --- | --- |
| F09 与 F08 口径 | F08 称"48 带 × 4 特征 = 196"；F09 实测为 48 带 × 8 特征（每带 2 组 `datum_points`/`datum_plane`/`sketch`/`extrude`）+ 7 项非带特征（`hubsk`/`ex_hub`/`blades8`/`merge_all_bodies`/`rim_r20`/`boresk`/`cut_bore`）= 391。两个数字口径不同，**不是同一计数单位**，不可互换 |
| F09 点名引用 | 96 个 `datum_points` 各含 3 点，点名 `p_a`/`p_b`/`p_c` 在 48 带中**逐带重复**；96 个 `datum_plane` 的 `thru_points` 引用的是点名而非特征标签。仅拆点即由 391 增至 **583** 操作 |
| F09 厚度精度 | 带特征拉伸厚度 `9.87008714331235`（96 处）；F10 最小复现同为 `9.87008714331235`。来源精度应保留，不得一律替换为 smoke 的 9.87 |
| F09 占位结构 | `sketch.entities` 为 `{"triangle_uv": …}` 占位（96 处）、`sketch.plane` 为 `{"datum_plane_label": …}` 占位（96 处）、`merge_all_bodies` 为无参占位（1 处） |
| F09 标签 | 390 个标签互异，最长 8 字符，均满足小写字母开头、≤28 字符 |
| F10 与 F03 | F10 用 `reference={"thru_points":[…]}`，F03/F05 用 `thru_points` 直挂或 `{"kind":"datum_point_feature"}` 解析；**三种写法不等价**，须经明确转换 |

## 缺件清单

以下原件或证据**缺**，报告与说明里提到的名称和路径不等于本次已取得附件。已核对：同目录的上游运输 zip（`2026-10-31_CREO_MechDog_反馈材料包_验收_G5方案_BUG094补丁.zip`）与目录**内容完全一致**（同样 10 件），仓库历史与既有归档中也无下列文件，故缺件状态成立。

| 缺件 | 报告中的出处 | 用途 / 影响 | 归属任务 |
| --- | --- | --- | --- |
| L1/L2 原始 job 日志与 `native.log` 关键行（`SKETCH_ANCHOR_PLANE=2`、`SECTION_LOCATION_IDENTITY=1 using_frame_basis`、`LINE_tri_0=…`、`CompleteFeature=-1`，job 目录 `8b3c5c2e…`） | F03 §三、§四、§七 | 定位 L2 内核报错原文；**不得冒充原 job 回放**，可做替代实验 | Q06 |
| `smoke_3pt.json` 与 `smoke_3pt_b~f` 运行记录 | F03 §七 | 六组三点定面复现的完整矩阵；本包只有 `smoke_3pt_min_repro.json` 一组最小载荷 | Q06 |
| `p12_v12_ops_a1.json`（轮毂 + 前 4 带的 execute_plan 载荷） | F03 §7 | 补丁后第一批可执行序列 | Q11 |
| 完整 v1.2 TXT 与五条判别性验收判据原文（138 629.77 / 62 231.97 / 614 234.967 等锚值来源；逐半径桨距表；判据 1 的 X 半跨 49.53→99.06） | F03 §5、§7；F02 §"风扇叶片 L2 方案" | 锚值硬断言前提；缺失时只能"按现有包重建"，不得声称原任务完整符合 | Q11 |
| 原 6 图元 A/D 完整输入（3 段 R25 圆弧 + 3 条直线，端点共用到 1e-9） | F02 §A、§D | A/D 原案复现；01 报告只有文字描述与偏差数字，无载荷。仓库与既有归档中亦无 | Q02 |
| B/C/G 原案输入（凹圆棱 `round` 面组对、`coordinates` spline 用例、正交性闸 1e-6 用例） | F02 §复测结论速览表 | 本轮均"未复测"，无完整输入；Q14 只能用替代夹具并记为替代验证 | Q14 |
| 上色包外部 80 组件装配源件与生成数据 | F06 内置 README §四 | 外部 80/80 结果不可移植为主干证据；主干已有 FEAT-052 实机 28/28 | Q12 |
| 0.10.0 轮次另三份反馈原件（`Downloads\0.10.0\` 下 BUG090 / 水平底板 / 端点焊接） | — | 与本包十个文件**不是同一批**，本轮未归档、未登记；后续处理须单独立项并重新核号 | 后续批次 |

另记一条口径提醒：F02 报告所称"BUG-094"与仓库 [BUG-094](../../work-items/BUG-094.md) **不是同一范围**。仓库条目是 angle/offset/引用契约，其指定部分已随 0.10.1 验收；本包 L1/L2 另登记 [BUG-097](../../work-items/BUG-097.md)，交叉关联而不覆盖旧结论。

## 登记与编号

本次新登记固定 ID（编号顺延自 `eb913de` 的最大 BUG-095 / FEAT-052，未占用 BUG-094、FEAT-052 或任何既有 ID；已核主干、Q02/Q03/Q04 三个工作树与 FEAT-052 工作树均无认领冲突）：

| 新 ID | 标题 | 分类 | 关联 | 负责 Q 任务 |
| --- | --- | --- | --- | --- |
| [BUG-096](../../work-items/BUG-096.md) | 失败作业遗留未保存会话对象占用模型名 | 待复现 | 交叉关联 BUG-012 / FEAT-018（只关联，不重开旧档） | Q03 |
| [BUG-097](../../work-items/BUG-097.md) | 斜面草图 UV 映射与特征完成失败（L1/L2） | 待复现 | FEAT-010 / BUG-087 / BUG-095 | Q06 |
| [FEAT-053](../../work-items/FEAT-053.md) | `datum_plane` 三点定面（`thru_points`） | 待规划 | FEAT-008 | Q05 |

另补建缺失的工作卡（沿用既有 ID 与描述，不另登新编号）：[FEAT-009](../../work-items/FEAT-009.md)、[FEAT-010](../../work-items/FEAT-010.md)。

Q 任务负责人字段：**Q02→写程序高手、Q03→代码编写者、Q04→codex代码**（已指派）；其余 Q 任务一律 `unassigned`，不虚构认领。

## 本轮未测范围

未连接 Creo/MCP，未建模，未运行产品单元与 `dev_check`，未做原生构建或实机验收；本轮无产品实现变更。F01—F10 全部为外部来源，报告中的实测结论保留其原环境（Windows 11 x64 / Creo 10.0.0.0 / 0.10.0 或外部直改源码），**不作为本仓库已验收结论**。
