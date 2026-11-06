# MCP_CREO_MechDog 0.15.1 版本说明

2026-11-06，PATCH 性质的发布后修正批；条目：[BUG-111](work-items/BUG-111.md)（`geometry_transform` 的 `keep_original` 副本诊断与能力文案）。公开工具仍为 **100** 个，无新增工具、无参数迁移、无回调注册变化。

本版只把 0.11.7 遗留的两处与定因结论不符之处修正后合入主干，**不改变建模行为**：`keep_original` 的选集语义、再生时机、旋转归一与整批回滚均保持原样，第 5 个副本在该角度集上仍会失败。

- 对外文案撤销旧变通建议：工具描述（`server.py`）、能力边界（`src/creo_mechdog/capabilities.py` 的 placement 段）与[语法参考](REFERENCE_SYNTAX.md) 删除"每批 ≤4 个副本并重新引用当前 body"，改为 0.11.7 定因（C0—C6 实机）后的口径——`keep_original` 复制的是**整个当前体**、副本累积在同一 body 内，追加副本是否会失败取决于既有副本集合与角度，**不是副本数量上限**，拆批（C6 的 4+3）对该角度集无效；需要固定原件的副本时另建模型。兼容矩阵的 0.11.6 历史段已标注被 0.11.7 段取代，并注明本修正随 0.15.1 发布。
- 选集诊断计数改取真实字段（原生改动，本版重编执行器）：`native/placement.cpp` 原从 `state["counts"]` 读取模型计数，而巡检从不发布该对象，`failed_transform.selection.model_counts_at_start` 的 `features`/`surfaces`/`bodies` 因此一律退化为 `-1`，把已有数据写成未知。现改从巡检实际发布的数组长度（`features`/`surfaces`/`bodies`）与 `body_counts.active` 取数；巡检确实没有的字段在回执里记 `null`（明确未知），原生日志 `TRANSFORM_SELECTION` 同时输出 `model_active_bodies`。失败回执结构、字段名与整批回滚语义未变。

证据沿用 2026-11-03 的定因轮实机记录（见 [BUG-111](work-items/BUG-111.md)）：本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK，分支 `codex/BUG-111-doc-and-counts-fix`，执行器 `cb6f3345…`、源码指纹 `7d0bc254…`；C2 仍失败于 `operation_index=4` 且整批干净回滚（revision 3→3、体积 28 800 mm³ 不变、后续合法编辑成功），C4 五副本全部成功（features 8→13、`saved_file_reloaded_and_verified=true`）。失败回执修正后为 `requested_body_ids=[52]`、`selected_surface_count=26`、`model_counts_at_start={features:12, surfaces:26, bodies:1, active_bodies:1}`（修正前为 -1/-1/-1）。

本版验证门禁：`tools/test_unit.py` 全量 **2624 项通过**（0 失败 0 错误，起点 2616，新增 8 项文案与取数护栏）、`tools/dev_check.py --skip-unit` `success=true`（24 条 lint 与 12 个未格式化文件均为 `style-baseline.json` 存量，未新增）、`bridge.py build` 退出 0（原生改动已重编 `build/creo_worker.exe`）。种子内容未变，仅清单版本字段同步：种子包 24 文件、9 种子，重建摘要 `a1a44ab3c7ad88e79829ef3248e678feb5760f4f57f49bc9da63616adcdc60b0`，已回填 `docs/seed_package.json` 并二次重建确认稳定。受测源码身份见[发布记录](validation/RELEASE-0.15.1.md)。

未验证范围：Creo 10/9 的副本行为与本修正的原生构建；"恰好重合 vs 部分交叠"的内核判据；`body_pattern`（仍未实现）；本轮未重跑 `tools/test_geometry_transform_copies.py` 实机（沿用 2026-11-03 同一源码的实机记录，本版只增删文案与取数字段）；WorkBuddy 黑盒未执行；BUG-108（`accepted_rigid=true` 9/9 未触发）与 BUG-110（`ack_success` 未实机发生）保持开放；BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.15.1-source.zip` 与 `MCP_CREO_MechDog-0.15.1-seed-library.zip`，按安装说明更新环境、重编执行器并重启 MCP 服务。旧种子包会被版本闸门拒绝。
