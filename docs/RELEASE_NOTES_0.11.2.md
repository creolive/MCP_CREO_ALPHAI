# MCP_CREO_MechDog 0.11.2 版本说明

发布日期：2026-11-02。类型：PATCH（兼容修复、诊断补充、工程闸门；公开工具仍 **95 个**，无新增/删除工具，无破坏性接口变更）。关联条目：[DEV-060](work-items/DEV-060.md)（R10 归档与登记）、[BUG-101](work-items/BUG-101.md)、[BUG-102](work-items/BUG-102.md)、[BUG-103](work-items/BUG-103.md)、[DEV-061](work-items/DEV-061.md)、[FEAT-035](work-items/FEAT-035.md) 增量。

## 本版内容

### 1. 草图端点可焊性风险标记（BUG-101）

- `creo_create_sketch` 结果 `profile` 新增 `weldability{available, weldable, max_endpoint_gap_mm, weld_tolerance_mm, tolerance_source, guarantee_scope, exceeding_pairs{total, truncated, sample≤20}, note}`。
- `weld_tolerance_mm` 取仓库既有 `EXACT_TOLERANCE_MM = 1e-9` mm（坐标尺寸求解 epsilon），**不是新标定值**；`tolerance_source` 区分 `measured_constant` 与调用方显式请求。
- **语义**：`weldable` 是风险标记。`true` 表示端点落在已测安全界内；`false` 只表示“超出已测安全界、未被证明可焊”，**不代表拉伸会失败**（本机 Creo 12.4 实测 8.215e-7 mm 间隙拉伸成功）。不可判定（分析不可用、partial、无间隙、非有限值）时为 `null`；开轮廓直接 `false`。
- 默认**只报告不拒绝**：草图闭合放行仍是 1e-4 mm 聚类容差，既有通过路径不变。
- 原生拉伸失败信息：`open_ends==0` 但端点簇内仍有间隙（`max_cluster_spread_mm>0`）时，点名“端点只在诊断聚类容差内相连、内核不保证焊接”并给出下一步动作，替换原“原因未定”；原句仅作最后兜底。

### 2. 拔模回执分列请求与实际方向（BUG-102）

- `draft_geometry` 新增 `requested_flip`（入参原样回显）与 `effective_flip`（创建后特征树实读，读不到为 `null`）；既有 `flip` 语义保持不动（仍为树值）。
- 创建被拒时追加 `draft_failure{api, requested_flip, angle_deg, surface_count, element_errors{total,truncated,sample≤20}, classification, note}`；`classification` 只在 `kernel_element_error` 与 `no_element_evidence` 之间二分，**不推断几何可行性**，`note` 给出下一步（减小角度 / 先删相邻圆角倒角 / `creo_inspect_model` 重读面 ID）。

### 3. 孔深度口径可读（FEAT-035 增量）

- 孔结果新增 `depth_basis`（`tip` / `not_tip` / `null`）、`depth_scheme_code`、`depth_scheme_query`（`PRO_E_HLE_DEPTH_DIM_TYPE`），由创建后特征树实读。
- `tip` 仅在读到 `PRO_HLE_DEP_TIP_DIM_SCHEME` 时给出；普通直孔走另一元素树，保持 `null`，**不猜** `"shoulder"`。
- 用途：0.10.0 起 custom 盲孔 `depth` 为钻尖口径，跨版本重放不会再静默变浅。

### 4. 种子包摘要仓库级闸门（DEV-061）

- 新增 `release_integrity.assert_repo_record_matches()`：比对实测归档摘要与本仓库 `docs/seed_package.json` 的 `seed_archive_sha256`、以及 `compatible_server_version` 与 `version.py` 是否一致，失配消息直接给出回填指引。
- `tools/package_seeds.py` 构包后**默认**校验；失配时保留刚构建的归档供回填、打印摘要并返回非零；`--allow-record-mismatch` 仅用于准备回填。
- `tests/unit/test_seed_record_gate.py` 与 `docs/development/RELEASING.md` 第 5 步同步，把“记得回填”变成可失败断言。

### 5. 台账与文档口径

- 三份 v0.10.0 第十轮反馈原件逐字节归档（[归档映射](validation/feedback-0.10.0-2026-10-31/MAPPING.md)，含章节→任务→固定 ID→已闭环依据）；新增 BUG-101/102/103、DEV-060/DEV-061，补 FEAT-014/035/051、BUG-049/090 增量。台账 150→155 行，155 个唯一 ID。
- `examples/sheetmetal_base_yz.json` 与 README：不再暗示“四条下边都能挂折边”，改为逐边读 `wall_contour_status`（eligible/ineligible/unknown）后再承诺。

## 实机验收（本机 Creo 12.4.0.0）

- draft 10°、`flip=false`、素面侧边 → `succeeded`，`requested_flip=false`、`effective_flip=true`、`material_delta_mm3=+264.490471`（与外部 0.9.0 报告的 +264.19 同向）。
- YZ 底板 185×232×1 → 体积 42920.0；四条下边 104–107 全部 `eligible`（`wall_contour_query_code=0`），另有 122/123/125/127 `ineligible`；对报告方失败的边 106 挂 `creo_sheetmetal_flange(height=80, radius=2.54, y_factor=0.5)` → 成功，体积 57293.615854821175，无回滚。
- 8.21534262415399e-7 mm 间隙草图拉伸 → 成功；吸附对照（7.83e-13）体积 500.0。
- 离线与静态：`tools/dev_check.py --work-item R10` `success=true`、全部单元测试通过、样式无回归；`bridge.py build` exit 0。

## 未测与已知限制

- 报告方环境为 Creo 10：8.2e-7 间隙 `-1`、四边中仅短边可挂两项在本机 Creo 12.4 **不可复现**，跨版本差异未定因；`gear10` 原件仍缺。
- 带 chamfer+R3 的 10° 拔模失败与 `PRO_E_DRAFT_*` 元素树 A/B 未执行（需按 `tools/test_draft_regression.py` 的变体重建执行器）。
- 盲孔 `depth_basis` 的实机回执（custom 盲孔读到 `tip`）未单独实机验证；普通直孔为 null 的行为由代码路径决定。
- 原生“簇内间隙”失败文案未在实机命中（本机无法复现该失败）。
- Creo 9 / Creo 10 实机、WorkBuddy 黑盒均未执行；不由本机通过外推。
- 四壁与角部 relief 仍不支持（`four_walls_complete=false`）。

## 升级说明

- 结果只增字段，旧字段语义不变；旧作业记录缺新字段时保持缺省，不推导、不补造。
- 若脚本以 `weldable=false` 作为“不允许拉伸”的硬门槛，请改为按自身容差判断：该字段是风险标记。
- 种子包与源码包必须成对使用：0.11.2 种子包对应本版源码；`docs/seed_package.json` 记录本版归档摘要。
