# R13 后续定因与补证：本轮验收记录（实机轮）

日期：2026-11-03（同日接续离线轮）。分支：`codex/BUG-111-r13-followup`。计划：[R13 后续定因与实机补证](../superpowers/plans/2026-11-03-r13-followup-bug111-108-110.md)。运行目录：`build/r13_followup_20261103T161114/`。

## 结论摘要

用户当次授权实机测试，BUG-001 会话核对（GUI 可操作）通过后 T1—T4 实机全部执行：

| 目标 | 本轮结果 | 状态 |
| --- | --- | --- |
| BUG-111 第五副本定因 | **已定因**：4 个独立模型（C2/C3/C5/C6 批B）同型失败于 index 4；C4（-135 在首位）与 C0 推翻"位置/数量上限"与"纯角度"；C6 推翻拆批变通；全程单 body 推翻引用解析。T2 选集证据（`selected_surface_count=26` = 整个累积体）把根因定为 **"`keep_original` 复制整个当前体"的选集语义 + 追加副本与既有凸块重合/交叠时的再生失败**，无实现缺陷证据，不做行为修复 | 现象侧收口（诊断与边界交付）；Creo 10/9 分列未验证 |
| BUG-108 `accepted_rigid=true` | 9/9 候选全部 `detected=false`（体积 oracle 13585 mm³ 精确），目标分支未触发 | unverified，保留外部 Creo 10 补证 |
| BUG-110 `ack_failure` 成功路径 | 零件与装配控制场景均为零变更守卫成功（`outcome=failure_rollback_left_model_ready`），未能安全形成 `failed` 候选，`ack_success` 未实机发生 | `coverage=guard_only`（part/assembly 均），装配成功路径未覆盖 |

## 身份与环境

| 项 | 值 |
| --- | --- |
| 分支 / 实机取证时 HEAD | `codex/BUG-111-r13-followup` / `36b5b4c`（重放判据修正提交） |
| T1 执行器 | `0f556504…`（13 323 776 B，指纹 `cd22b563…`，离线轮产物） |
| T3/T4 中间执行器 | `df01aea3…`（13 328 384 B，指纹 `407d5fa9…`，诊断代码格式化前） |
| T2 最终执行器 | `7071b94780e08e77de7f626de964c43e0916d3f37445d1cedbd6e540ea250f3b`（13 328 384 B，指纹 `cc2aa38d…`，clang-format 后） |
| worker↔源码同一 | 格式化后 worker 哈希变化，按纪律以最终执行器 `7071b947…` 复跑 C2/C4（`--model-suffix t4`），行为与 T1 一致 |
| 环境 | Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）与匹配 SDK（本机） |
| 会话准入 | 用户当次授权 + GUI 可操作核对；单一 Toolkit 通道串行，无故障注入、无 unknown 保护清理 |

## T1/T2 事实（BUG-111）

逐例原始报告：`t1_reproduce.json`（C0—C6 全量）、`t2_rerun.json`（C2/C4 诊断增强后复跑）。假设权衡：`hypotheses.md`。

| 用例 | 底板 | 序列 | 结果 | reproduce 判定 |
| --- | --- | --- | --- | --- |
| C0 | r13c0 | [-135] + 225° 对照 | 225° 校验层拒绝（报错含 `-135`，未建作业）；[-135] 成功（vol 2×，features 8→9） | pass |
| C1 | r13c1 | [45,90,135,180] | 4 op 全部提交（vol 192000，bbox [-120,-120]..[120,120] 出现未请求方向） | fail（batch committed; reproduce only） |
| C2 | r13c2 | [45,90,135,180,-135] | **index 4 失败**，整批干净回滚，后续合法编辑成功 | pass |
| C3 | r13c3 | 7 op | **index 4 失败**，op5/6 未执行 | pass |
| C4 | r13c4 | [-135,45,90,135,180] | **5 op 全部成功**（features 8→13） | fail（batch committed; reproduce only） |
| C5 | r13c5 | 同 C2，显式 body id | **index 4 失败**，与 C2 同型 | pass |
| C6 | r13c6 | 批A 4 op + 批B 3 op | 批A 成功（vol 192000）；**批B 首个 op（累计第 5 副本）失败** | pass |

关键证据链：

1. **单 body**：全程 `counts.bodies=1`（id 52），副本是新 feature/凸块（+1/op），不是新 body——显式 id（C5）与隐式引用（C2）选中同一个体。
2. **选集随体增长**：C1 的 after bbox 与 T2 回执 `failed_transform.selection`（`requested_body_ids=[52]`、`selected_surface_count=26`，新底板仅 6 面；`model_counts_at_start` 执行器上下文不可用记 -1，不造数）共同证明每个 op 复制整个当前体。
3. **失败跟随"模型状态 × 角度"**：失败只在"体已含 {45,90,135,180} 副本 + 追加 -135"组合出现；C4、C0 反证位置/数量上限与纯角度缺陷；C6 反证拆批变通（"≤4/批建议"作废）。
4. **失败代价可控**：失败批整批回滚（after==before、revision 不变），后续合法编辑正常。

T2 处置：按计划走"完善诊断和边界"分支——`native/placement.cpp` 记录有界选集证据（行为零改动）、`native/generic.cpp` 失败回执并入 `selection`；未修行为。BUG-111 现象侧结论：**已定因（选集语义 + 几何重合），实现无缺陷证据**；"恰好重合 vs 部分交叠"的内核判据、Creo 10/9 行为、`body_pattern` 仍未验证/未实现。

## T3 事实（BUG-108）

`sketch_shift.json`：9 个独立候选（TRIANGLE，x 偏移 0/40/−260 各 3 例，省略 `geometry_tolerance_mm`）全部执行，9/9 `detected=false`（`note=no post-solve shift was measured`，点残差 ~1.4e-14 mm），作业全部成功、体积 oracle 逐例精确。**无一次触发刚性平移**，`accepted_rigid=true` 的数值与几何见证未取得。逐例判定均为 `unverified`，顶层 `verdict=unverified`。策略未改（未提高默认阈值、未取消原点约束、未人为搬动截面）；外部 Creo 10 补证保留。后续尺寸编辑步骤因无触发样本不适用。

## T4 事实（BUG-110）

`assembly_ack.json`：零件（PART-GUARD）与装配（ASM）控制场景均为 `failure_guard`——无效约束/失败建模后整批回滚，`outcome=failure_rollback_left_model_ready`，模型保持 `ready`。**未能用正常公开操作形成安全可达的 `failed` 候选**，`ack_failure` 成功路径（冻结快照 → apply ack → 不变性核对 → 同键重放 → 后续可用）未实机发生。顶层 `verdict=unverified`、`coverage={part: guard_only, assembly: guard_only}`。未注入进程故障、未手改注册表。重放判据修正（确认二次修改/结果变化判 fail、缺证据判 unverified）已由单测覆盖。

## 交付物

| 文件 | 变更 |
| --- | --- |
| `tools/test_geometry_transform_copies.py` | 判定口径修正（`features_added_per_copy` + `single_body_semantics` 取代 body 增量口径）；新增 `--cases` 子集过滤与 `--model-suffix` 重跑避让 |
| `tests/unit/test_geometry_transform_copies_driver.py` | `snapshot()` 增 `features` 参数；新增单 body 语义回归，共 7 项 |
| `tools/test_assembly_ack_failure.py` | 重放判据修正：`replay_single_transaction`/`replay_same_result` 从结果证据独立判定 |
| `tests/unit/test_assembly_ack_failure_driver.py` | 新增 3 项重放回归，共 10 项 |
| `native/placement.cpp` | `failed_transform` 前记录有界 `transform_selection`（请求 body id、被选面数、op 起始计数），只读诊断 |
| `native/generic.cpp` | `transform_failure_report()` 并入 `selection` 块 |
| `docs/work-items/BUG-111.md` | "定因轮实机结果"章节 + "≤4/批建议"口径作废 |
| `docs/work-items/BUG-108.md` | "补证轮实机结果（T3）"章节 |
| `docs/work-items/BUG-110.md` | "补证轮实机结果（T4）"章节 |
| `build/r13_followup_20261103T161114/`（不入库） | `baseline.json`、`t1_reproduce.json`、`t2_rerun.json`、`sketch_shift.json`、`assembly_ack.json`、`hypotheses.md` 及日志 |

## 检查命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_geometry_transform_copies_driver tests.unit.test_assembly_ack_failure_driver -v` | 17 项通过（7 + 10） |
| `python bridge.py build`（诊断改动后，含 clang-format 前后两轮） | exit 0；最终执行器 `7071b947…` |
| `python tools/test_geometry_transform_copies.py --confirmed-session-usable --phase reproduce --output build/r13_followup_20261103T161114/t1_reproduce.json`（及 `--cases`/`--model-suffix` 复跑） | C0—C6 全量成档；失败现象 4/4 独立复现 |
| `python tools/test_sketch_shift_batch.py --confirmed-session-usable --output .../sketch_shift.json` | 9/9 未触发，verdict=unverified |
| `python tools/test_assembly_ack_failure.py --confirmed-session-usable --output .../assembly_ack.json` | guard_only，verdict=unverified |
| `python tools/dev_check.py --work-item BUG-111-BUG-108-BUG-110-followup`（整批定稿后） | `success=true`；全量 **2 268 项 0 失败/0 错误**；无新增语言问题；风格基线未改 |

## 未执行与未测范围

1. **BUG-111**：Creo 10 / Creo 9 行为（无环境）；"恰好重合 vs 部分交叠"的内核判据（未做二分实验，不在本批范围）；`body_pattern` 未实现。报告方原 8 叶计划未随包提供。
2. **BUG-108**：`accepted_rigid=true` 分支未实机出现（不靠故障注入制造）；触发后的尺寸编辑/重载未执行（无样本）。
3. **BUG-110**：零件与装配 `ack_success` 均未实机发生；不变性、幂等、后续可用性在实机层无证据（判定逻辑由单测覆盖）。
4. **通用**：WorkBuddy 黑盒验收未执行；`docs/validation/` 历史原件逐字节未改；0.11.6 实机证据仍属那次批次，不外推为本轮结论；本批不合 main、不改版本、不发布。

## T5 口径与诊断计数修正（2026-11-03 续，发布后修正）

复审 0.11.7 交付时发现两处与 T1/T2 定因结论不符，本轮修正并复核。

| 目标 | 本轮结果 | 状态 |
| --- | --- | --- |
| 对外文案撤销"≤4/批"建议 | 工具描述、能力边界（placement 段）、[语法参考](../REFERENCE_SYNTAX.md) 均已改写为 C6 结论；兼容矩阵 0.11.6 历史段标注被 0.11.7 段取代 | 已修正（离线断言护栏） |
| 选集诊断计数取数 | 原读 `state["counts"]`（巡检从不发布）→ 一律 -1；改为读 `features`/`surfaces`/`bodies` 数组长度 + `body_counts.active`，缺失项记 `null` | 已修正 |
| 最终执行器复核 C2/C4 | C2 失败于 index 4、整批干净回滚、后续合法编辑成功；C4 五副本全部成功、保存重载 true；失败回执计数为实际值（12/26/1/1） | 实机通过（与前轮行为一致） |

- 身份：分支 `codex/BUG-111-doc-and-counts-fix`（基线 `main@8ab0641`，dirty）；三次重编（`c3ddf6de…` → `55af1174…` → `cb6f3345…`，第三次只改注释编号），以**最终执行器 `cb6f3345…`（13 329 920 B，源码指纹 `7d0bc254…`）**复跑为准；环境 Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 SDK；用户当次授权会话，单一 Toolkit 通道串行，无故障注入、无 unknown 保护清理。
- 复核命令与报告：`tools/test_geometry_transform_copies.py --confirmed-session-usable --phase reproduce --cases C2,C4 --model-suffix t7 --output build/r13_followup_20261103T1836/t5_rerun_final.json` → `verdict=pass`、`success=true`；C2 作业 `4aef9f4c…` 的 `native.log` 逐 op 记录 `TRANSFORM_SELECTION`（被选面 6→9→15→23→26、features 8→9→10→11→12），作业回执 `result.failed_transform.selection.model_counts_at_start` = `{features:12, surfaces:26, bodies:1, active_bodies:1}`（修正前为 -1/-1/-1）。
- 离线：全量 **2276 项**单测 0 失败/0 错误（起点 2268，新增 `tests/unit/test_transform_selection_diagnostics.py` 8 项）、`tools/dev_check.py --work-item BUG-111-doc-and-counts-fix` `success=true`（无新增语言问题，风格基线未改）。
- 未验证范围（不变）：Creo 9/10 行为；"恰好重合 vs 部分交叠"的内核判据；`body_pattern` 未实现；WorkBuddy 黑盒；**BUG-108 `accepted_rigid=true` 仍未触发（9/9）、BUG-110 `ack_success` 仍未实机发生**，两者保持开放）；本轮不合 main、不改版本号、不发布。
