# BUG-103 水平底板壁面归属：对照清单与收口口径

日期：2026-11-02。关联：[BUG-103](../work-items/BUG-103.md)、[FEAT-014](../work-items/FEAT-014.md)、[R10 归档映射](../validation/feedback-0.10.0-2026-10-31/MAPPING.md)、[角部调查交接](FEAT014-CORNER-INVESTIGATION-2026-10-31.md)。

## 1. 事实基线（只读核对，未连接 Creo）

| 事实 | 依据 |
| --- | --- |
| 报告配方：YZ 平面 offset 92.5、线 (−116,0.5)→(116,0.5)、`depth=185`、`thickness=1`、`direction=negative` | [F01 原件](../validation/feedback-0.10.0-2026-10-31/originals/2026-10-31_CREO_0.10.0_水平底板底边无法挂折边_R2仍未解决.md)、`examples/sheetmetal_base_yz.json` |
| 结果几何正确：V=42920、COG(0,0,0.5)、Z∈[0,1] | 同上；本机 0.8.4 五组实机曾复现体积 |
| 四条下边均 Z=0，但只有 X=±92.5 短边可挂；`f_ny` 报 `ProSmtedgeContourGet=-8` | F01；本仓库 T05/N05/N06 同族现象 |
| 本仓库已能**事前**查询每条边的资格：`wall_contour_status=eligible\|ineligible\|unknown` + `wall_contour_query_code`，按 revision 标注，每边一次查询、256 边预算 | `native/generic.cpp` `wall_contour_check`；`src/creo_mechdog/sheetmetal.py` 投影 |
| 壁面清单可回显：`wall_contract.wall_face_ids`；`thickness>=depth` 时附不阻断的 `parameter_hint` | `native/advanced.cpp` |
| 折边失败文案已重写（帧契约 + `wall_face_ids` + YZ 配方指引） | `native/advanced.cpp` 折边 create 失败分支 |
| **未定因**：为何该构造只有短边进入绿/白壁面轮廓；推荐配方与实测矛盾 | 本清单要解决的问题 |

## 2. 离线可完成的部分（已完成）

1. 读代码确认三态投影、`wall_face_ids` 与失败文案的实际字段名与作用域（见上表）。
2. 把“四条边都能挂”的隐含承诺从示例与文档中移除：`examples/sheetmetal_base_yz.json` 的描述现明确要求逐边读 `wall_contour_status`，并声明归属问题归 BUG-103；README 钣金行同步。
3. 把“若属原生限制则文档 + 准入拒绝”的收口口径写进本清单（第 4 节），避免后续把能力不足写成已修复。

## 3. 需要一次实机的只读巡检（待指派，不建几何）

前置：确认会话可用（无 unknown 保护、无已受理作业）、只连 `MCP_CREO_MechDog_dev`。

1. `creo_new_sheetmetal` 建毫米钣金件 → 等终态。
2. 按 `examples/sheetmetal_base_yz.json` 建底板（两操作计划）→ 记录 job/model/revision、V=42920、COG、`wall_contract.frame`、`wall_face_ids`。
3. `creo_inspect_model`（edges + `wall_contour_check`）→ 逐个记录四条下边的 `wall_contour_status` / `wall_contour_query_code` / `revision`。
4. 只读比对：`wall_face_ids` 里的面与四条下边所属的面是否一致；把“合格/不合格”与 face id 对应关系写成表。
5. 若需要，再单发一道 `f_ny`（`sheetmetal_flange`）确认失败码与文案；失败后核对 revision 不变、模型可用、无残留特征。

**通过判据**：三态结果可复核、与真实挂接结果一致（`eligible` 不误报成功）、失败文案不再推荐已验证失败的配方。

## 4. 人工 UI 对照清单（交操作者，不由 Agent 代做）

目的：区分“Creo 原生限制”与“本仓库元素树/固定侧差异”。

1. 在 Creo UI 新建钣金件，按同一参数建首壁（YZ 平面、offset 92.5、单线、depth 185、thickness 1、方向同）。
2. 开启面着色/绿白面显示，记录哪两个大面被标为驱动侧面（green/white）。
3. 尝试对 Z=0 的两条长边各建平整壁（Flange），记录 UI 是否允许选边、建出的几何与失败提示原文。
4. 再用另一条边界（例如把线改到 X-normal 平面构造）重复一次，记录差异。
5. 记录：Creo 版本与 build、是否同样只有短边可选、绿白面实际归属。

**判读**：
- UI 同样只有短边可选 ⇒ 原生限制，按第 5 节 A 分支收口。
- UI 四条边都可选而 MCP 不可 ⇒ 本仓库实现差异，按 B 分支修。
- 两者都不稳定或与构造顺序相关 ⇒ C 分支，保留证据并给替代路径。

## 5. 三种收口分支与动作

**A 原生限制（预期概率最高）**
- 文档：README 钣金行 + `examples/sheetmetal_base_yz.json` 写清“该配方只有哪些边可挂、四壁需换构造”。
- 准入：可选地在 `sheetmetal_flange` 创建前把已知不可挂的组合拒绝为 `wall_contour_status=ineligible` 的可读错误（不改变已有 `-8` 语义，仅提前给理由）。
- 能力声明：`four_walls_complete=false` 保持，不写“已修复”。

**B 实现差异**
- 最小修复 + 回归：新增/修正选边或固定侧属性；补一条“同构造四边挂接”实机用例。
- 仍需：体积、`wall_face_ids`、revision、保存重载、回滚齐全。

**C 未定因**
- 保留巡检表与 UI 记录；在 BUG-103 卡写明“证据不足、不承诺四壁”。
- 给替代路径（例如先做两侧壁 + 后续单边补齐，或改平面构造）。

## 6. 明确不做

- 不用历史 edge id 104–107 作为输入。
- 不修改 `end_trim_mm`（三轮实测 `trim_ignored`）。
- 不在无 UI 对照的情况下改元素树猜“墙面对”。
- 不把 `wall_contour_status=eligible` 当作折边必成的承诺。

## 7. 未验证

本机 Creo 12.4 只读巡检、UI 对照、失败文案在真机上的可读性均**未执行**；报告方环境为 Creo 10，跨版本结论不外推。
