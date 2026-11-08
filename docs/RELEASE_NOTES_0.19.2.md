# MCP_CREO_MechDog 0.19.2

日期：2026-11-08。类型：PATCH。公开工具：107（与 0.19.1 相同）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.19.2 集成两批离线工作：

1. DEV-077 的 R01—R04 离线实现：草图容差链与端点吸附、几何保真断言、mirror 特征引用、session_health stale 身份降级、quilt_merge 消耗片回执。
2. DEV-079 对 2026-11-08 下载目录 `0.19.0` 三份 Creo 10 反馈的离线处理：曲率默认摘要、surface_group 结构化失败、quilt_merge 描述同步、切除面积口径与台账/POSTCHECK 收口。

本版不新增公开工具，不改变已有接口的必填参数或默认行为；新增字段均为可选或有默认值的回执扩展，按 PATCH 发布。

## 本版变化

### 草图（DEV-077 R01）

- `creo_sketch` / `creo_update_sketch_geometry` 新增可选 `closure_tolerance_mm`（有限正数）。省略时仍是已发布的 1e-4 mm；该值只影响 Python 解析预检、近容差与开放端判定及 `profile` 回执，不改变原生 solver 精度。
- 新增 `snap_endpoints`（默认 false）。为 true 时按已接受配对重写直线端点：直线-直线取中点，直线-圆弧以圆弧端点为锚、圆弧不移动；矩形/多段线与双圆弧配对显式拒绝。回执 `snap.{requested,applied,rule,max_shift_mm,residual_max_mm,pairs}`，`applied_by=python_request_rewrite`，每条配对带两侧实体、端点、间隙与位移。
- `assertions` 新增 `max_geometry_deviation_mm`、`require_exact_solve`、`preserve_input_geometry`。原生在校验阶段扫描各草图已测 `geometry_deviation`：超限、非零或发生位移时按断言失败回滚；未测得偏差时显式失败，而不是默认通过。

### mirror（DEV-077 R02）

- `creo_mirror.references` 允许 `{kind:'feature', label|id}`，按原生 PRO_FEATURE mirror item 解析且不展开子树。
- 回执新增 `implementation`（`part_mirror` 或 `reference_mirror`）、`reference_kinds`、`feature_reference_count`；capabilities 同步说明受支持子集与“不合成几何”。

### session_health（DEV-077 R03）

- 新鲜的 connected 证据可把 stale identity 降为 warning（`session.identity_stale_downgraded` + `warnings` + caveat），状态仍按现有证据判定。
- 不清任何 unknown/damage 保护；当前会话内已过新鲜期的 unknown/damage 记录改列入 `historic_damage_signals` 并标注 `current_session`。

### quilt_merge（DEV-077 R04 / DEV-079）

- 回执新增 `consumed_quilt_ids`（JOIN 必消耗 tool；未原地增长时也含 target）与 `merged_surface_ids`。
- 公开描述从门禁时代文案改为两片 JOIN 的实际语义：消耗规则、`result_quilt_source`、`input_area_mm2`（两输入之和）与 `area_mm2`（结果面积）的区别、失败回滚。
- `inspect_model(quilts)` 过滤内核残留、三片以上 merge、变半径/过渡、圆角后实体化仍未完成。

### 曲率与曲面组（DEV-079）

- `creo_measure_surface_curvature` 新增 `include_samples`（默认 false）。默认响应移除 `faces[].points`，保留 `summary`、G1 块与每面统计，并返回 `samples_included=false`、`omitted_sample_count`、`samples_note`；显式 true 才返回逐点。作业记录始终保留完整采样。这使默认 12×12 两面的回执不再超过 MCP 结果预算。
- `creo_measure_surface_group` 失败改为结构化 isError：`job_id`、`model_id`、`revision`、`readonly`、`status`、`group.state=null`、`group.state_reason`（`contour_edge_visit_failed` 或 `measurement_failed`）、`error` 与重读 quilt 的 `hint`。
- `profile` 块新增 `method`（`analytic-input`），并在 `creo_extrude` 描述中写明 `material_area_mm2` 是输入草图解析面积，不是内核去除截面；多轮廓部分圆弧切除可与 `material_removed_mm3` 相差约 2%。

### 台账与发布记录（DEV-079）

- 三份 2026-11-08 Creo 10 反馈逐字节归档到 `docs/validation/feedback-0.19.0-2026-11-08/`，附 manifest 与逐项 MAPPING。
- BACKLOG 当前表行 170（BUG 75 / FEAT 61 / DEV 34）；`tools/check_backlog_counts.py` 三方一致。
- POSTCHECK 删除 v0.19.0 段末与已回填事实矛盾的“仍待补”旧句。

## 验证

- 全量 Windows 单元测试：`Ran 3118 tests ... OK`（394.649 s，工作树）。
- `tools/dev_check.py --skip-unit --work-item DEV-079`：成功，仅存量风格基线。
- `git diff --check` 通过；`tools/check_backlog_counts.py` 170 一致。
- 原生执行器已用本机 Creo 12.4 SDK 通过 `bridge.py build`；本批未连接 Creo 会话，未做几何、保存重载或回滚实机复验。
- 本批未执行 WorkBuddy 黑盒、源码包解压后全量单测、Creo 9/10 实机。

## 未测范围与已知限制

- **Creo 10**：`surface_loft` / `surface_boundary_fill` 仍依赖 `Probbl.h`；0.19.1 起 worker 构建身份会让缺该头的执行器在作业前拒绝该工具，但 Creo 10 的可用实现仍不存在（DEV-079/H01）。
- `surface_trim` 开放带面/开放弧交线诊断、合并残留 quilt 标记、group 边界访问失败根因未解决（H02/H03）。
- 钣金成形类（`sheetmetal_flange_profile`、`sheetmetal_corner_relief`、`sheetmetal_quilt_form`）与 `surface_boundary_fill` 门禁保持不变；DEV-078 路线仍为离线候选。
- 多轮廓切除的原生 `section_area_mm2`、大作业默认 compact、连续共线顶边选边、`entities_file`、`native_bundle` 装配打包、负 `origin` resize 体积仍开放（H04—H09）。
- Creo 9 与 Toolkit 9 的编译探测修复已实现，本机无 Creo 9 SDK，实机编译与建模未验收。
- 本版不把 Creo 12.4 或外部 Creo 10 的历史结果外推为本批通过。

## 安装与升级

安装、客户端注册与种子库步骤见 [docs/INSTALL.md](INSTALL.md) 与 [docs/SEED_LIBRARY.md](SEED_LIBRARY.md)。升级后请重启 MCP 客户端，使新的工具描述与 `include_samples` 参数生效。本版无需迁移模型或配置。

## 附件

发布附件固定四个：源码包、种子包及各自 `.zip.sha256`。文件名与完整 SHA256 在 Release 正文与 [发布记录](validation/RELEASE-0.19.2.md)中给出；源码包内的本文件保留发布前占位，实际摘要以 Release 与 POSTCHECK 为准。
