# FEAT-035：原生沉孔与沉头孔参数化

日期：2026-10-17。类型：功能。优先级：P2。状态：已交付（0.10.0，T12 tip 口径；沉孔/沉头与盲孔/方向/尺寸编辑六例实机通过；通孔、出口沉头、螺纹孔等余项开放）。目标版本：0.10.0。

来源：[0.3.3 反馈补录](../validation/FEEDBACK-0.3.3-2026-10-17.md)报告 B 第 9 节；关联 FEAT-008、BUG-022、BUG-033。

## 目标与范围

齿轮泵报告需要沉孔，目前以圆草图加拉伸切除替代，缺少单个原生孔特征的参数和注释语义。本项作为新增能力，不把现有直孔范围记成缺陷。

评估在原生 hole 路径支持平底沉孔 `counterbore`（直径、深度）和锥形沉头孔 `countersink`（口部直径、夹角），明确基本孔径、通孔/盲孔深度、放置方向、互斥/组合与合法尺寸关系。字段与 SDK 元素树映射须先核对，报告建议不作为已定实现；不承诺螺纹、标准孔系列或锥管孔。

普通直孔旧请求保持兼容，接口/计划/回显/能力说明一致。Creo 9 常量条件编译修复不证明支持新的孔类型，各 SDK 缺项须给准确能力边界，不能用缺常量静默退成直孔。

## 验收标准

| 环境 / 用例 | 可判断的预期结果 |
| --- | --- |
| Windows / schema 与回归 | 省略新字段保持旧直孔行为；负值、沉孔小于基本孔、非法角度/深度和不支持组合准确拒绝；统一开发检查通过 |
| 本机 Creo 12.4 / 匹配 SDK | 通孔/盲孔分别覆盖沉孔与沉头孔；单个原生孔特征可回读尺寸、类型、实际轴向及深度，去料体积与独立圆柱/圆台计算相符 |
| 编辑与保存 | 尺寸可按确认契约编辑；几何、revision、保存重载 true；无交集和失败分支保持材料守卫及检查点 |
| 外部环境与 WorkBuddy | 外部 SDK 按实际取得的编译/建模证据记录；WorkBuddy 仅 MCP 黑盒，不以普通孔通过推定新孔类型通过 |

## 实现与证据

本次只建卡，目标版本未排期，未新增字段、SDK 节点或模型。来源为 0.3.3 外部需求，当前 0.3.4 尚未实施或验收。

## DEV-051 T12 离线阶段（2026-10-29）

已在独立工具和计划的共享 `HoleOp` 中加入互斥的 `counterbore{diameter,depth}` 与 `countersink{diameter,angle}`。Creo 12.4 匹配 SDK 的 `ProHole.h` 将这些元素列于 custom hole；原生路径只创建一个 `PRO_FEAT_HOLE`，省略新字段时仍走旧 straight hole 树。离线构建、契约测试、解析几何算式已完成；元素树实际创建、原生尺寸编辑、几何、保存重载、回滚尚未连接 Creo 验收。详见 [T12 验收卡](../development/DEV051-T12-ACCEPTANCE.md)。本条保持开放，状态为实现待原生验收。

## 2026-10-29 实机：沉孔平座与 90° 沉头（CREO 12.4.0.0）

`tools/test_native_countersink.py --live --confirm-session-usable` 3/3 通过，报告 `build/native_countersink/20261029T231402_6e57e45d/report.json`（SHA256 `f58cd6af…8477c`）：

- 沉孔 Ø10×2 平座（Ø6 通孔，50×50×10 板）：去料 **383.274 303 737 951 mm³**，独立 oracle 383.274 303 737 955，误差 3.6e−12；`hole +1`、`feature_id=78`、结果回显 `material_removed_mm3` 与孔轴 `(25,25,0)→(25,25,10)`，rev 2。
- 沉头 Ø10 @90°：去料 **328.820 031 075 731 mm³**，oracle 328.820 031 075 732，误差 7.3e−12；同样 `hole +1` 并回显轴，rev 2。
- 180° 沉头：入口拒绝 `operations.0.hole.countersink.angle Input should be less than 180`，无 job（契约要求 `<180`，因此 180° 一侧以平座沉孔作几何对照）。

两个孔型的去料量与独立解析式一致，说明 custom hole 元素树真正生效而非只建特征。未测：盲孔+沉台深度约束、沉孔尺寸 ID 编辑、保存重载、螺纹/标准孔、出口沉头与双端沉孔、Creo 9/10。本条仍开放（编辑与保存重载未验）。

## 2026-10-30 离线余项：盲孔/方向/编辑/失败回滚/保存重载（DEV-051 T12）

在既定孔型契约内补齐余项的离线实现与待验驱动：`depth` 盲孔（overall 语义）、方向沿放置面法向（含侧面法向孔与 `flip` 向外钻的守卫失败+回滚+恢复）、真实 dimension ID 的尺寸值编辑（径/沉孔深）、逐例保存重载与参数/几何一致性。每例带独立 oracle（平底去料解析式、面数增量、尺寸回读、圆柱面轴与 bbox），并以 `matched_variant` 区分 118° 钻尖/座面起量备选算式（命中备选不通过）。入口拒绝边界（互斥/尺寸关系/角度）保持不变。修改 `tests/unit/test_native_countersink.py`（9 用例）与 `tools/test_native_countersink.py`（默认 live 跑 6 例余项，三例已通过项仅 `--include-passed-cases` 重跑）；未改 schema、native 与 capabilities。离线：单测 1490 OK、`bridge.py build` 通过、报告 `build/native_countersink/20261030T102226_76e75830/report.json`（SHA256 `ae785e69…fda5500`）。6 例全部未实机；详见 [T12 验收卡](../development/DEV051-T12-ACCEPTANCE.md)「2026-10-30 离线余项」。本条保持开放（实机待验）。

## 2026-10-31：N10 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n10/run1/report.json`（SHA256 `6056a097…76119`，`run_id=20261031T134447_69136d19`，`mode=live`，`passed=true`）。本节只追加，不改写上方 2026-10-29/30 的记录。

**六例全部首次执行并通过**：

| 用例 | 底板 / 孔作业 | rev | 去料实测 / 口径 | 口径变体 |
| --- | --- | --- | --- | --- |
| `blind_straight` | `d67dc571359242618f1d54c8518b49af` / `4a2733102e234ca083a380bc694e1fdb` | 2 | 197.92033717615413 | `contract_flat_overall`（`overall_flat`） |
| `blind_counterbore` | `b9225dea1ced40cd98f7be119feecbff` / `37aae7ae58ae4a5f9557266fab2eeeec` | 2 | 292.7477684551013 | `contract_tip_overall`（`overall_tip`） |
| `blind_countersink` | `468d5a79b60f4b47abb154d01d648864` / `64de562c50174e25990e688076c78687` | 2 | 238.293495792881 | `contract_tip_overall`（`overall_tip`） |
| `direction_side_normal` | `7570b713bac347d69a75917452772fa4` / `076503e1e58c4f0cac52b9f11161c534` | 2 | 197.92033717615777 | `contract_flat_overall`（`overall_flat`） |
| `direction_flip_guard` | `29616cb6534e4d34967856ab1bb5084f` / `c9e9ff90226a41c8baab8cdca24bedf1` | — | 翻向作业 failed（守卫按设计拒绝） | 见下 |
| `edit_dimension_values` | `f23ff0e51dc641db9fa167e1428bb87d` / `1d755a950cb343df95dee70d8b40c719` → 编辑 `fc2ecd45c1884a958699ab2c53b799bc` | 2→3 | 292.7477684551013 → 374.0864038721993 | `contract_tip_overall`（`overall_tip`） |

要点：

- **T12 tip 口径生产修复（`0f1844a`）实机验证成立**：沉孔与沉头两例均命中 `contract_tip_overall` 且 `depth_semantics=overall_tip`，不再落到 `defect_till_shoulder_below_tip`（343.7145697324541 / 289.260297070231）或 `defect_seat_measured_drilldepth`（383.27430373795477）等备选形态；`depth_evidence` 中 `cone_depth_max` 与 `total_depth` 均为 8.0，钻孔段止于锥底（`bore_depth_max=6.19741814291732`），与该口径自洽。
- **方向例**：侧面法向孔 `direction_side_normal` 去料 197.92033717615777（与直孔 oracle 197.92033717615698 相符，误差 8.0e-13），孔轴从 `(25,25,5)` 指向 `(25,25,3)`，即沿放置面法向而非默认 Z。
- **翻向守卫**：`direction_flip_guard` 的翻向作业按设计失败（`toolkit_code=-1`、`failed_stage=execute_hole`、`rollback_succeeded=true`、原生消息 "Hole removes no material; check reference offsets, placement, flip and overlap with existing holes"），失败后模型体积与面数回到 `24999.999999999993` / 6 面；随后恢复作业 `4762ea0f692e420a8a19d831b5a29fe9` succeeded，去料 197.92033717615413、`contract_flat_overall`、`saved_file_reloaded_and_verified=true`。
- **尺寸编辑**：编辑作业用真实 dimension ID（`diameter=14`、`counterbore_depth=13`），编辑后 rev 3、去料 374.0864038721993（对上 oracle 374.0864038721959，误差 3.4e-12），尺寸回读 `[3.0, 7.0, 118.0, 10.0, 8.0, 25.0, 25.0]`，保存重载 true。
- 全部成功例 `saved_file_reloaded_and_verified=true`、`missing_dimensions=[]`，面数增量与 oracle 一致（直孔 +3、沉孔 +7、沉头 +6）。

未测范围不变：通孔口径、出口沉头与双端沉孔、螺纹/标准孔、Creo 9/10、WorkBuddy 黑盒。本条在"沉孔/沉头孔参数化 + 盲孔/方向/尺寸编辑"范围内实机已通过，仍不据此关闭本卡整项（通孔与其它孔型未验）。

## 2026-11-02 增量：tip 口径需机器可读标记（外部反馈，未实现）

来源：[0.10.0 第十轮反馈 F03 §3](../validation/feedback-0.10.0-2026-10-31/MAPPING.md)（[原件](../validation/feedback-0.10.0-2026-10-31/originals/2026-10-31CREO10.0.0.0-0.10.0-BUG090获Creo10零补丁编译证据但种子摘要回填仍无闸门.md)）。

- **现象**：0.10.0 起 custom 盲孔 `depth` 为钻尖口径（`PRO_HLE_DEP_TIP_DIM_SCHEME`，对齐冻结契约 overall），但该口径**只出现在版本说明**：全库检索 `depth_basis`/`tip_depth` 为 0 命中，响应里没有任何字段说明“本次用了哪种口径”。按存储 JSON 计划重放的自动化客户端在 0.9.0/0.10.0 上提交同一 hole 请求会得到不同深度/体积，且**无法自证**。
- **与既有验收的关系**：本卡 2026-10-31 N10 六例已用 `contract_tip_overall`/`depth_evidence` 记录口径（`depth_evidence.cone_depth_max`、`total_depth`、`bore_depth_max`），但那是**验收驱动**的判据字段，不是稳定公开回执；`matched_variant` 属离线驱动判定，不是工具返回契约。
- **计划增量（2026-11-02 已离线交付）**：`native/generic.cpp` 新增 `hole_depth_basis_json()`，从**创建后特征树**实读 `PRO_E_HLE_COM/PRO_E_HLE_DEPTH_DIM_TYPE`，孔结果输出 `depth_basis`（`tip`/`not_tip`/null）、`depth_scheme_code`、`depth_scheme_query="PRO_E_HLE_DEPTH_DIM_TYPE"`；`bridge.compact_job` 白名单同步。`tip` 仅在读到 `PRO_HLE_DEP_TIP_DIM_SCHEME` 时给出，普通直孔走另一元素树故为 null，**不猜 `"shoulder"`**。README 接口表 hole 行已注明“0.10.0 起 custom 盲孔为钻尖口径”。单元 `tests/unit/test_hole_depth_basis.py` 6 项通过（含 compact 保留与不默认）。
- **边界**：只加字段，不改既有 `depth` 数值语义；不重新解释历史作业记录（缺字段保持缺省）。通孔口径与其它孔型仍不在本卡已验范围。**实机未验**：普通直孔是否也返回非 null 取决于 Creo 是否把该元素写进树，未连会话确认。

## 2026-11-03 alphai 能力吸收：A03 标准螺纹孔（仅规划）

沿用本 ID 的“螺纹/标准孔”余项，不重做已交付沉孔/沉头/tip 口径。拟增加受安装孔表约束的 `standard={series,size,thread_depth}`，原生核验系列/规格/底孔与保存的螺纹元数据；不是实体螺旋牙型。旧 `diameter` 仅在新标准分支可省略，其余行为兼容。

负责人 unassigned；接口、文件、针对性回归、实机矩阵见 [A03 子计划](../superpowers/plans/2026-11-03-alphai-a-foundation-plan.md)，协调 [DEV-067](DEV-067.md)。本次未实现、未测试/连 Creo；本卡原状态、已交付版本和其他开放范围保持，后续仅按新证据回填本子项。
