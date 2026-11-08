# 0.19.0 / 0.19.1 反馈对照（2026-11-08）

工作卡：[DEV-079](../../work-items/DEV-079.md)。来源目录 `C:\Users\Administrator\Downloads\0.19.0`，三份原件逐字节归档在 [originals](originals/)，身份见 [manifest.json](manifest.json)。归档副本与来源的大小、SHA256 已逐项比对一致。

- 前两份报告的实机版本是 **0.19.0**（Creo Parametric 10.0.0.0，`creo_release_numeric=42`，`tool_count=107`）。
- 第三份报告文件名取 0.19.1，但正文说明**本机只安装并实测 0.19.0，0.19.1 仅按 release notes 评估**。
- 本轮核对基线与累计实现为本地 `main`（含 DEV-079 工作树改动），源码版本 0.19.1。报告方在 Creo 10 的结果不被当成本轮实测；本轮未连接 Creo、未编译原生执行器、未联网。

## 一、报告一：0.19.0 曲面闭环与四个新能力

| 报告项 | 报告结论 | 当前核对 | 处置 |
| --- | --- | --- | --- |
| §3.1 `creo_quilt_merge` | Creo 10 两片 400 mm² 合并为 800 mm²，`retrimmed_target_quilt`，保存重载通过 | 0.19.0 已公开；本轮补 `consumed_quilt_ids` / `merged_surface_ids`（DEV-077 R04） | 无需改代码；Creo 10 证据采纳为报告方实测 |
| §3.2 `creo_surface_round` | 正例面积与解析值逐位一致，负例回滚 | 未改变该路径 | 无动作 |
| §3.3 `creo_measure_surface_curvature` | 数值通过，但默认 144 点回执不可消费 | 见 §6.2 | 本轮修复 |
| §4 纯曲面闭环 | Creo 10 首次打通 merge/closed/thicken | 报告方证据，本轮不重跑 | 记录，不外推 |
| §6.1 `surface_loft` 被 `Probbl.h` 编译屏蔽（P0） | Creo 10 无该头文件，工具 100% 失败 | 0.19.1 已有 worker 构建身份动态准入：worker 自报缺失时 Python 在作业前拒绝（`WORKER_CONDITIONAL_OPERATIONS`）；Creo 10 的可用实现仍不存在 | 保留开放（H01），需 Creo 10 SDK / 等价元素树 |
| §6.2 曲率默认输出超预算（P1） | 97,987 字符，144 点/面 | 默认移除 `faces[].points`，保留 `summary`/`g1_*`/每面统计；新增 `include_samples`（默认 false），响应带 `samples_included`、`omitted_sample_count`、`samples_note` | 本轮修复 |
| §6.3 失败作业 connect 计时被 8192 B tail 截断（P1） | `stages_seen=0`，`result.verify_stages` 里有 connect/connected | DEV-077 已交付 `stall_report` 的 `verify_stages` 回退，`timing_source=verify_stages` | 0.19.1 已修，无需重复 |
| §6.4 合并后残留 quilt 干扰闭合检测（P1） | 被消耗 quilt 仍 `closed=true`、面积不可测 | 回执已有 `consumed_quilt_ids`；`inspect_model` 仍未对残留片标注 `consumed_by_merge` | 部分修复；标记残留与三片以上 merge 保留开放（H03） |
| §6.5 `creo_measure_surface_group` 工具级异常（P1/P2） | `contour_edge_visit_failed` 只有一句错误，无 job_id | 失败改为结构化 payload：`job_id`/`model_id`/`revision`/`status`/`group.state_reason`/`hint`，经 `server.invoke` 以 isError 回执发布 | 本轮修复回执；触发条件与根因仍开放（随 H03） |
| §6.6 `creo_quilt_merge` docstring 相反（P1） | 仍是「gated: submissions are refused」 | 已重写为两片 JOIN：消耗规则、`result_quilt_source`、`input_area_mm2` 与 `area_mm2` 语义、失败回滚 | 本轮修复 |
| §6.7 `state_reason` 与 `boundary_edges` 矛盾（P2） | open 组给 `boundary_edges_unavailable` 但有 15 条边 | 0.19.1 的 `group_state_decide` 只在边真的不可用时给该 reason，其余开放组给 `open_edges_present`；原生状态用例覆盖 | 0.19.1 已修 |
| §7 `surface_trim` 开放弧交线诊断（P0） | 开放带面/开放弧交线未诊断 | 未改变 | 保留开放（H02），需实机交线夹具 |
| §7 `surface_boundary_fill` | 仍在 `unavailable_tools` | DEV-078 四边路线仍离线，未公开 | 门禁保持 |

## 二、报告二：0.19.0 安装、编译与发布核验

| 报告项 | 报告结论 | 当前核对 | 处置 |
| --- | --- | --- | --- |
| P1-1 Creo 10 编译阻断 | `native/surface_loft.cpp` 裸 `#include <Probbl.h>`；0.19.0 的 `surface_boundary_fill.cpp` 复用 `SURFACE_LOFT_TREE_SAMPLE_LIMIT`、`loft_element_json`、`PRO_E_DTM_SRF_TYPE_BND_BLEND`，旧补丁失效 | 与 §6.1 同一缺口；本轮未改原生，避免在没有 Creo 10 SDK 的情况下交付未编译的 `#if` 分支 | 保留开放（H01）；验收需 Creo 10 SDK 编译 + 实机几何 |
| P1-2 `RELEASE-0.19.0.md` 仍准备态、正文自相矛盾 | 快照声明缺失，正文两处口径冲突 | 0.19.0 发布记录是历史原件，按项目规则保持字节不变；统一 POSTCHECK 与 [RELEASE-ERRATA](RELEASE-ERRATA-2026-11-08.md) 已记录勘误 | 不回写原件；以勘误为当前口径 |
| P1-3 源码包解压全量单测口径冲突 | 0.19.0 记录前后矛盾 | 0.19.1 记录统一写明源码包全量单测未执行，不再声称通过 | 0.19.1 已澄清；不把解压单测当发布门槛 |
| P2-4 三处裸名导入 | `test_tilted_sketch_lifecycle.py`、`test_guards.py`、`summarize_multisection.py` | 当前三处均已改为 `tools.*` 包路径导入；`tests/unit/test_t07_provenance.py` 可导入 | 0.19.1 已修，无需重复 |
| P2-5 台账计数 | 0.19.0 写 167/DEV 31，实际 166/DEV 30 | `tools/check_backlog_counts.py` 三方计数自检；本批登记后为 170（BUG 75 / FEAT 61 / DEV 34） | 本轮更新 |
| P2-6 DEV-075 卡首页 | 仍「开发中 / 目标 0.18.2」 | 卡首页已写「已交付 0.18.2 子项」 | 0.19.1 已修 |
| P2-7 POSTCHECK 缺失段落 | require 段落缺失、v0.18.x 仍「待补」与已回填段落矛盾 | v0.18.2/0.18.3/0.18.4/0.19.0/0.19.1 段均已回填；本轮删除 v0.19.0 段末「仍待补」的旧句 | 本轮修复 |
| §6 附件 digest 回填 | 给出 v0.19.0/v0.18.4 可直接回填的数据 | POSTCHECK 已含四附件字节/SHA256，与报告数据一致 | 已回填 |

## 三、报告三：0.19.1 曲面链 Creo 10 通过、钣金与多轮廓切除

| 报告项 | 报告结论 | 当前核对 | 处置 |
| --- | --- | --- | --- |
| P-A 多轮廓含圆弧切除面积差 | 28/32 孔与百叶开口的 `material_removed_mm3` 比 `material_area_mm2` 少约 1.8%–2.1%；整圆无差；几何本身正确 | `profile.material_area_mm2` 是 Python 解析输入草图的面积，原生 `material_removed_mm3` 是内核测量；回执未标面积口径 | 本轮加 `profile.method=analytic-input` 并在 extrude 描述写明差异；native `section_area_mm2` 保留开放（H04），需在原生执行器取截面 |
| P-B 曲率默认输出超预算 | 99,512 字符；成员面 retrim 后 `faces:[0,1]` 报越界 | 见 §6.2；成员数错误信息本身已是可读文本 | 本轮修复默认摘要；描述补充 `face_count` 前置提示 |
| P-C 大草图作业默认轮询超预算 | 105–120 实体时 `detail=full` 报单项超限，必须 `detail=compact, sections=[]` | 0.19.1 已放宽 `wait_seconds` 到 300；`get_job` 全量视图对单项超限只标记不裁剪 | 仍开放（H05）：终端作业默认 compact / `omit_operations_input` |
| P-D 钣金成形全缺位 | 0.19.0/0.19.1 均未解锁 | `UNAVAILABLE_OPERATIONS` 仍门禁 flange_profile/corner_relief/quilt_form；FEAT-014/DEV-078 离线候选未实机 | 门禁保持，不因本批改动放宽 |
| P-E ±X 顶边碎片化 | 四壁盒 ±X 顶边最长 70.586 mm，折边无法挂完整 232 mm | 未改选边/合并逻辑 | 保留开放（H06），需连续共线边合并或按 wall 顶边生成 |
| P-F 钣金体无法与实体合并 | `SHEETMETAL_SOLID_ADD_UNSUPPORTED`、负 body id 被拒、`union` 正反均 -1 | 未改；FEAT-014 已记录反证 | 保留开放（FEAT-014） |
| P-G 草图无文件/参数化入口 | `creo_run_plan` 不可用，只能内联 `entities` | `creo_execute_plan` 仍内联；本批未加 `entities_file` | 保留开放（H07） |
| P-H 装配交付需手工复制组件 | `.asm` 引用 `models/<id>/output/` 副本，`native_bundle` 未验证 | `native_bundle` 存在但本轮无实机 | 保留开放（H08），需导出后另一目录打开验证 |
| P-I `origin≠[0,0]` 大跨度 resize 体积错误 | 0.17.4 起连续多版未修，本轮未复测 | 未改 | 沿用原卡（H09） |
| P-J 建议 Creo 10 进发布前回归 | 报告方建议至少覆盖曲面链、钣金增料、多轮廓 cut | 2026-10-15 用户已取消 Creo 10 独立复测与双版本发布门槛 | 不改变发布门槛；保留为建议，按朋友新反馈再排 |

## 四、剩余项编号（DEV-079 接手 H 列表）

| 编号 | 剩余工作 | 依赖 |
| --- | --- | --- |
| H01 | Creo 10 不依赖 `Probbl.h` 的 `surface_loft`/`surface_boundary_fill` 等价元素树，或按 SDK 代际明确不可用 | Creo 10 SDK 编译 + 实机几何 |
| H02 | `surface_trim` 开放带面/开放弧交线的诊断与分割 | 实机原夹具 |
| H03 | `inspect_model(quilts)` 标注被 merge 消耗的残留片；三片以上/过滤内核残留；group 边界访问失败根因 | Creo 实机 |
| H04 | 原生 `section_area_mm2` 与 `material_removed_mm3` 对账及超差告警 | 原生截面查询 + 实机 |
| H05 | 终端大作业默认 compact 摘要 / `operations_input` 分页或省略开关 | 离线可先设计，公开预算需验收 |
| H06 | 连续共线顶边合并选边或按整条 wall 顶边生成折边 | 实机四壁盒 |
| H07 | 草图 `entities_file` 或极坐标/环扇模板 | 设计 + 实机 |
| H08 | `native_bundle` 装配快照自动打包验证 | 实机导出后异目录打开 |
| H09 | `origin≠[0,0]` 大跨度 `resize_sheetmetal_planar_wall` 体积错误 | 原卡现场 |
