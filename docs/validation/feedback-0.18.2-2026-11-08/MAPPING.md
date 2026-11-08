# 0.18.2 四份报告与当前源码对照（DEV-077）

日期：2026-11-08；分支 `offline/0.18.2-feedback-gapfill`；起点 `4bd6b7e` / 0.18.4（DEV-076）。四份原件长度与 SHA256 见 [manifest.json](manifest.json)，复制后逐字节一致；报告方 2026-11-07 的 Creo 9/10 实测与本次离线环境严格分开。

代号：F01 [草图容差链与装配矩阵精度阻断](originals/2026-11-07_CREO_v0.18.2_草图容差链与装配矩阵精度阻断.md)（实跑 0.18.1 / Creo 9）、F02 [本版交付卡与台账计数及 POSTCHECK](originals/2026-11-07CREO10.0.0.0-0.18.2-本版交付卡DEV075仍开发中与台账计数166实为165及POSTCHECK本版段未回填.md)（离线安装侧）、F03 [quilt_merge 门禁与曲面放样闭合](originals/2026-11-07CREO10.0.0.0-0.18.2quilt_merge门禁与Creo10实测相反及曲面放样闭合仍缺.md)（Creo 10 黑盒）、F04 [显式密度质量属性与曲面反馈未登记](originals/2026-11-07CREO10.0.0.0-0.18.2显式密度质量属性被归一化守卫拒绝与全程曲面反馈跨版未登记.md)（Creo 10 黑盒）。

## 对比结论

当前仓库已由 DEV-074/075/076 集成 0.18.3/0.18.4 修复，四份报告的多数「未修」描述已过时。本批按「现状核对 → 只补真实缺口」处理，不重复认领既有成果，也不把 0.18.1/0.18.2 报告结论标成本轮实测。

| 批次 | 报告中本项目已完成（无需重复） | 本批离线完成 | 仍需接手 |
| --- | --- | --- | --- |
| F01 | `endpoint_policy=weld` + `max_endpoint_move_mm` 受控吸附；`geometry_deviation` / `weldability` / `arc_geometry` 可观测字段；字典式平面的文档已改为可用 surface/datum id 形式 | 归档登记；其余无（见 G01—G06） | 草图容差链、旋转矩阵门槛、任意平面一等公民、mirror、契约示例、health、轮询 |
| F02 | DEV-075 卡首页已改「已交付0.18.2子项」；BACKLOG 计数已由 DEV-076 实算为 167（报告中的 166/165 是旧时点）；POSTCHECK 已有 v0.18.2 标签/时间与两个 ZIP 索引 | RELEASING 第 8 步扩到 DEV/BUG、逐 ID 表 DEV-075 行同步；POSTCHECK v0.18.2 四附件 digest/字节/exit 0 回填；计数自动门禁；新增 DEV-077 并同步计数 168 | v0.18.3/0.18.4 远端四附件与真实核对时间联网补证 |
| F03 | `creo_surface_loft`（两截面、Probbl.h 条件）、`creo_measure_surface_group` 闭合/gap 测量、`native/surface_trim.cpp` 保留侧形心/法向判据、`surface_solid.scope` / `surface_chain.limits` 文案、0.17.4 反馈归档 | 四份 0.18.2 反馈归档与 MAPPING 登记；`stall_report` 在 tail 截断时回退 `result.verify_stages` | quilt_merge 放行与合并语义、G1 桥接、边界 fill、独立 offset、quilt round、曲率分析、近切预检 |
| F04 | `native/generic.cpp` 显式密度成功分支已清 `mass_unavailable_reason` / `hint`；`preview.py` 的 `skipped_no_geometry` 已把 path 置 null；装配质量属性已加守卫，与 `parts_only` 契约一致 | 归一化守卫错误信息携带可定位字段 + 回归；stall 回退（与 F03 同项）；本批反馈登记 | 显式密度路径 Creo 10 实机复验、装配契约黑盒验收、原生侧针对性回归 |

## F01 逐项

| 报告项 | 当前事实（证据） | 判定 / 归属 |
| --- | --- | --- |
| A-1 闭合容差 1e-4 与三位小数数据冲突、缺端点吸附与 gap 表 | `src/creo_mechdog/profile_diagnostics.py:20` 仍是内部常量；已提供 `endpoint_policy=weld` + `max_endpoint_move_mm`（`src/creo_mechdog/capabilities.py:131-147`、`endpoint_welding.py`）；`native/generic.cpp:1854` 只给 `nearest_gap_mm`，没有 entity A/B/gap 完整表 | 部分完成；可配 `closure_tolerance_mm` / `snap_endpoints` 与完整 gap 表见 G01 |
| A-2 `coordinates` 偏差超限自动回退 `autodim` | `native/sketch_coordinates.cpp:393` 仍直接失败；无 fallback | 未完成 G01 |
| A-3 `autodim` 静默改动几何的主动拒绝 | `assertions` 无 `max_geometry_deviation_mm` / `require_exact_solve` / `preserve_input_geometry`；`geometry_deviation` 仍可事后发现 | 未完成 G01 |
| B 旋转矩阵 1e-6 硬门槛 | `src/creo_mechdog/schema.py:47-70` 硬编码 1e-6，docstring 仍「never repaired」；无 `orthogonality_tolerance` / `orthonormalize` / 建议矩阵 | 未完成 G02 |
| §4 任意平面草图写法不可用 | `server.py:726`、`references.py:541-549` 已把文档改为可用 `surface/datum id` + `origin/u_axis`；`native/generic.cpp:1143-1200` 仍按既有几何匹配 axis/offset | 文档已收口，一等公民工具未实现 G03 |
| 5.1 特征子树镜像 / 5.2 装配质量属性 / 5.3 `operations` 最小示例 / 5.4 `session_health` / 5.5 loft callback / 5.6 长轮询 / 5.7 known_limitations | 镜像仍拒绝（`capabilities.py:615`）；装配已加守卫（`generic_bridge.py:80-83`）但错误信息无 `use_tool` 提示；compact 只有操作名（`server.py:711-712`）；`session_health.py:559-565` 仍 `session_identity_stale`；`capabilities.py:668` 仍要求 callback；`server.py:412` 上限 30；全仓无 `known_limitations` | 均未完成 G04—G06、G08；health 涉及 unknown 保护语义，需先定策略 |

> F01 自身声明「问题全部在 0.18.1 上复现、未在 0.18.2 验证」。本批没有 Creo 9 实机，无法把上述项标成回归通过；接手时先做一次 0.18.4 回归确认，再决定是否按报告建议改代码。

## F02 逐项

| 报告项 | 本批处理 | 证据 |
| --- | --- | --- |
| P1-1 DEV-075 卡首页「开发中」与 RELEASING 逐 ID 表自相矛盾 | 卡首页已由 DEV-076 改为「已交付0.18.2子项」；本批把 `docs/development/RELEASING.md:50` 两列状态同步，并把第 8 步「本版交付 ID」从 FEAT 扩到 DEV/BUG | `DEV-075.md:3`、`RELEASING.md:39,50,109` |
| P2-1 计数 166/DEV 30 实为 165/DEV 29 | 属旧时点；DEV-076 已实算 167/DEV 31。本批新增 DEV-077 后改为 168/DEV 32，并新增 `tools/check_backlog_counts.py` 由表行自动生成计数，防止移档 off-by-one | `docs/BACKLOG.md`、`src/creo_mechdog/backlog_counts.py`、`tests/unit/test_backlog_counts.py` |
| P2-2 POSTCHECK v0.18.2 段仍占位 | 用 F02 §七可直接回填的数据补齐：标签对象 `4c659f5e…` → 提交 `43862f00…`、`2026-11-07T10:18:16Z`、`--tag v0.18.2 --version 0.18.2` exit 0、四附件 SHA256/字节、报告方取值时间 `2026-11-07 18:22 +08:00`。明确这些是外部报告转录，本轮未联网重跑；`docs/validation/RELEASE-0.18.2.md` 作为历史发布前原件不改字节 | `docs/development/RELEASE-POSTCHECK-2026-11-07.md` 的 `## v0.18.2` |
| P3 feedback-* 空目录 | 报告已声明非缺陷；本批补齐 0.18.2 批次归档，0.18.0 原件仍寄在 `feedback-0.18.1-2026-11-07/originals/`，不制造占位 | 本目录 manifest |

## F03 / F04 逐项

| 报告项 | 当前事实 | 判定 / 归属 |
| --- | --- | --- |
| F03 P0-1 / F04 P1-2 quilt_merge 全局门禁与 Creo 10 实测相反 | `capabilities.py:102-114` 仍只有 `quilt_merge` 一条门禁，文案已注明 Creo 10 外部正证据不能解禁；`server.py:2827` 提交前拒绝；无 release-aware / `allow_unverified_release` | 未完成 G07（需 Creo 10/12 分别实机验收后才可放行） |
| F03 P0-2 多片合并失败、工具 quilt 残留、surface id 重复 | 无 `consumed_quilt_ids` / `result_quilt_id` / `boundary_loop_report`；`inspect_model(quilts)` 未过滤被消费 quilt | 未完成 G07 |
| F03 P1-1 / F04 P1-2 缺多截面曲面放样 | `creo_surface_loft` 已注册（`server.py:2787`）但受 Probbl.h 缺头门控；`creo_boundary_blend` / G1 桥接仍缺 | 部分完成；实机几何与 8 片缝合未完成 G09 |
| F03 P1-2 / F04 P1-2 修剪保留侧判据 | `native/surface_trim.cpp:295-324` 已给 `tool_normal`、目标/保留形心与 `centroid_status`；`capabilities.py:571-576` 的 `native_test` 措辞已有实测支撑 | 代码已完成；Creo 10 黑盒复验未完成 G09 |
| F03 P1-3 `surface_fill` 只接受平面草图 | `src/creo_mechdog/schema.py:1857-1860` 只有 `sketch`，无 `boundary/edges/curves` | 未完成 G09 |
| F03 P2-1 / F04 P1-1 `connect` 计时被 8192 B tail 截断 | 本批 `stall_report` 在 `truncated=true` 且无子阶段时回退同一作业 `result.verify_stages`，并标 `timing_source`；head 扫描与 `ts`/`idle_seconds` 不伪造 | **本批离线完成**，实机样本复验见 G11 |
| F03 P2-2 / F04 P1-2 能力契约滞后、0.17.4/0.18.2 反馈未登记 | `surface_solid.scope` / `surface_chain.limits` 已由 DEV-076 更新；本批补齐四份 0.18.2 原件归档与对照；`known_limitations` 段仍缺 | 登记本批完成；能力契约汇总段未完成 G08 |
| F04 P0-1 显式密度回执被归一化守卫拒绝 | `native/generic.cpp:804-808` 已清残留 reason/hint；本批把 `normalize_mass_properties()` 的拒绝文本补上有界原始字段，避免「作业成功但工具无诊断」 | 源码修复完成；Creo 10 上 `material_assigned=true / mass_query_code=-1` 的实机复验未完成 G11 |
| F04 P1-3 装配质量属性三态不一致 | `generic_bridge.py:80-83,364-368` 已加装配守卫，docstring 与 `parts_only=true` 一致；装配路径不再产生缺字段回执 | 按「二选一」的拒绝路线已闭环；WorkBuddy 黑盒验收 G11 |
| F04 P2-1 `skipped_no_geometry` 假 path | `preview.py:135-137` 已把 path/bytes 置 null | 已完成（DEV-076），本批只登记；本版实机样本仍无 G11 |

本批离线验证、未测范围与接手顺序见 [验收记录](ACCEPTANCE.md) 与 [DEV-077 接手清单](../../development/DEV-077-HANDOFF.md)。2026-11-08 合并已发布的 v0.19.0 后，本表 G01—G13 的覆盖变化、冲突取舍与刷新后的 R01—R08 清单见 [COMPARE-0.19.0.md](COMPARE-0.19.0.md)；本表记录的是 0.18.2 反馈当时的事实，不因合并改写历史结论。
