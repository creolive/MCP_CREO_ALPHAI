# 0.19.0「简易护卫舰」反馈对照（报告 2026-11-08 / 接手 2026-11-09）

工作卡：[DEV-081](../../work-items/DEV-081.md)。原件逐字节归档于 [originals](originals/)，身份见 [manifest.json](manifest.json)。本报告是**第四份** 0.19.0 反馈，与 [DEV-079 三份报告](../feedback-0.19.0-2026-11-08/MAPPING.md)不是同一批，编号体系也不同：本卡把报告的 P1—P11 映射为 **F01—F11**，避免与 DEV-079 的 P1-1 / P-A / H01—H09 混淆。

- 报告方环境：Windows / Creo Parametric 10.0.0.0（`release_numeric=42`）/ MCP_CREO_MechDog 0.19.0 / 107 个启用工具；任务为仅凭一份 1571 行自然语言 TXT 重建简易护卫舰，全程只用 MCP，未导入外部模型。`creo_capabilities.update.status=failed`（5 秒网络预算），因此报告方**无法确认 0.19.0 是否最新**。
- 本轮基线：本地 `v0.19.2`（`f1c0a94`），分支 `codex/DEV-080-feedback-0190-followup`，工作树含 DEV-080 未提交改动。**接手核对阶段只做只读核对、归档与计划；随后 A 批离线交付 6 个 Python 模块、6 个新单测模块与文档（见第五节）。两批均未连接 Creo、未编译原生执行器、未联网、未发布。**
- 证据强度：报告方的 Creo 10 实测结论只作为报告方证据，不外推为本轮实机验收；本卡的「当前核对」均为本地源码静态核对。

## 一、逐项对照

| 编号 | 报告结论（严重度） | 当前 0.19.2 源码核对 | 处置 / 依赖 |
| --- | --- | --- | --- |
| F01（报告 P1） | 原生实体 Blend 必须人工注册并启动 DLL callback，`creo_loft` 直接拒绝；`creo_new_loft_part` 在 connect 阶段 `code -4` 失败（高，阻断） | `src/creo_mechdog/blend_callback.py` 的 `prepare_callback`/`callback_setup_status` 仍要求 `readiness=ready`；`native/blend_create.cpp` 抛 `BLEND_CALLBACK_SETUP_REQUIRED`；`generic_bridge.py:316-394` 的 seed 路线已有 2–20 截面、递增 Z、闭合轮廓预检与按截面数选 seed，但失败发生在 connect 阶段 | 需设计 + 实机：无 callback 的原生放样路径或可查询的一次性注册状态机；seed 兼容性前置预检另立。与 [FEAT-025](../../BACKLOG_COMPLETED.md#legacy-feat-025) / [FEAT-009](../../work-items/FEAT-009.md) 的多截面限制、DEV-079 H01 的缺头编译缺口相关，**不并入离线批次** |
| F02（P2） | 两段精确圆弧在轴上相接被 `near_tolerance` 预检误判；`endpoint_policy=weld` 不生效（高，阻断） | `src/creo_mechdog/schema.py:2420-2427` 的 `validate_operations` 调用 `validate_solid_profile`；`profile_diagnostics.py:703-706` 在 `dimensioning=="coordinates"` 时把 `near_tolerance` 列为 fatal；`endpoint_welding.prepare_operations` 在 `generic_bridge.py:625` 才执行，**晚于 schema 校验**，故 weld 无法救回 | **离线可交付**：对已解析为 1 个闭合环、0 个开放环的轮廓不再因浮点残差拒绝；保留开放轮廓保护；错误信息给可复制补救建议。见实施计划 Task 1 |
| F03（P3） | `arc.radius` 上限 100000 mm，R=105 m 无法表达（中，阻断） | `src/creo_mechdog/schema_base.py:47` 的 `Positive = Annotated[float, Field(gt=0, le=100000)]` 是唯一真源，被 `Circle.radius`（含 `Arc` 继承）、`Ellipse.x_radius/y_radius`、`SketchDimension.value` 共用；无逐字段上限，也没有专门锁定该上界的单测 | **离线可交付**：为半径/尺寸类字段引入独立上限并在错误中说明是 API 上限而非 Creo 内核限制；平移等其它 `Positive` 字段不动。见 Task 2 |
| F04（P4） | 会话中途 Creo 消失、connect `-4`，需显式 retry 才恢复（中，中断一次） | `creo_startup.py:61` 的 `_retry_explanation` 与 `creo_startup.py:642` 的 `start(retry)` 已支持显式重试；`src/creo_mechdog/session_health.py:413` 的 `_next_steps` 只给 preserve/operator 等步骤，未给 `creo_startup_status(retry=true)` 工具名；`window_observations.py:81` 的 `connection_guidance` 是窗口观察提示 | **离线可交付（仅回执）**：`toolkit_code=-4` 且未连接时给出显式 retry 步骤；不改恢复策略、不自动重启、不清 unknown 保护。见 Task 5。报告已声明失败在 connect 阶段、几何未创建，**不能据此断言 seed loft 导致 Creo 退出** |
| F05（P5） | 曲面替代链未打通（中，但报告明确非缺陷结论） | `creo_surface_loft` 限两截面、每截面一条非复合曲线、仅 straight；`surface_boundary_fill` 自报不可用（缺 `Probbl.h`，见 DEV-079 H01）。报告方**本次 0 次曲面/扫掠/加厚调用**，`creo_sweep`/`thicken`/`solidify`/`quilt_merge`/`draft` 完全未尝试 | **不作为缺陷认领**。`capabilities.py:1003-1009` 已有完整 `limits`，`KNOWN_LIMITATIONS` 也有 `surface_loft_sdk_header`；但 `capability_pages.py:97-105` 的 compact 摘要只保留 `enabled`/`tool`，而报告方查的正是 `detail=compact`，真实缺口是**限制在该视图不可见**。A 批只补 compact 的 `limits_note`，不写第二份描述、不放宽门禁。多段闭合轮廓 loft 归入 F01 设计批次，与 [FEAT-009](../../work-items/FEAT-009.md)、DEV-079 H01 关联 |
| F06（P6） | 单特征 15–20 秒、20 op 的 plan 5–8 分钟、原生日志 3–7.7 MB，阶段进度不可读（中，不阻断） | `src/creo_mechdog/native_stage.py` 的 `TAIL_BYTES=8192`/`HEAD_BYTES=4096`、`stall_report` 的 `log_bytes`/`truncated`/`stages_seen`；DEV-077 已交付 `verify_stages` 回退（DEV-079 MAPPING §6.3 标为已修）。当前仍无 index/total 紧凑阶段输出 | 需原生 + 实机：紧凑阶段进度、日志体积治理、批量事务合并。**不并入离线批次**；与 DEV-079 H05（大作业 compact）分别记录，不重复认领 tail 截断 |
| F07（P7） | 更新检查 5 秒预算导致版本探测长期失败（低，不阻断） | `src/creo_mechdog/update_check.py:25` `NETWORK_SECONDS=5`、`:154-160` 已有环境变量 `MECHDOG_UPDATE_TIMEOUT_SECONDS`（1..30）、`:265-296` 超时文案与缓存说明；`snapshot()` 已输出 `network_timeout_seconds` | **离线可交付**：保持默认 5 秒（MCP 启动预算），在失败文案与能力说明里给出可执行下一步（调预算 / `creo_check_update(force=true)`），并明确失败不等于最新。见 Task 3 |
| F08（P8） | `extrude(mode="cut")` 只能全局切除，无法按特征/实体限定作用域（中，不阻断） | `schema.py:649-664` 的 `ExtrudeOp` 与 `server.py:1204-1215` 的 `creo_extrude` 均无 `targets`/`scope`；`BooleanOp.targets` 是另一条路径 | 需公开契约设计 + 实机验收；与 [BUG-102](../../work-items/BUG-102.md) / [FEAT-051](../../work-items/FEAT-051.md) 相关。**不并入离线批次** |
| F09（P9） | 预览图为线框 + 全部草图/基准叠加，无法判读外观（低，不阻断） | `native/preview.h` 固定等轴测矩阵 + `ProRasterFileWrite`；`src/creo_mechdog/preview.py` 只投影 `preview_file`/`preview_status`/`preview_code`。全仓无 `preview_mode`/`view`/`fit_all` 参数 | 需原生改动 + 实机截图验收；与 [FEAT-041](../../work-items/FEAT-041.md) 的预览视角候选相关。**不并入离线批次** |
| F10（P10） | 缺锥台/拔模拉伸的参数入口，只能用台阶近似（中，不阻断） | `ExtrudeOp` 无 `draft_angle`/`top_scale`；`creo_draft` 是独立工具（`surfaces`/`neutral_plane`/`angle`/`pull_direction`），报告**未提交也未查其 schema** | 报告已声明「draft 需要逐面引用」只是未验证推断，**不作能力缺失结论**；锥台需求归入 F01 的轻量双截面路线设计。需实机，不并入离线批次 |
| F11（P11） | 主草图 `offset` 是全局坐标、`direction` 相对法向（XZ 为 −Y），文档未说明；失败信息缺实际坐标（中，导致整批回滚） | `schema.py:328-329` 的 `SketchOp.plane/offset`、`native/generic.cpp:1306-1327` 的 `sketch_frame`（`name=="XZ"` 时法向 −Y）、`native/generic.cpp:2845-2849` 的 `"Extrude cut removes no material; check the sketch position, direction and depth against existing geometry"` | **离线可交付（文档/描述契约）**：写清三平面 offset 与 direction 对照、在工具描述标注 offset 是平面全局坐标；错误里附原点/法向/有效深度区间属原生改动，另立实机批次。见 Task 4 |

## 二、证据边界（按报告原文保留）

1. F05：全程 122 次 deferred 调用中曲面/扫掠/加厚类为 0 次，`creo_loft` 是实测 `not_loaded`，`surface_loft` 结论只来自静态 schema，`boundary_fill` 只来自 capabilities 自报；「曲面路径不可用」只是**本次会话未打通**，不是 MCP 曲面能力整体不可用，作者不必据此改曲面实现。
2. F10：`creo_draft` 未提交、未查 schema；「需要逐面引用」是推断。
3. F04：connect `-4` 发生在几何创建之前，`model_unchanged=true`、两 sketch 均未执行；不能把 Creo 退出归因于 seed loft。
4. F03：100000 是 Python API 的硬上限，报告建议至少说明这一点；不是已证实的 Creo 内核限制。
5. 报告方因 `update.status=failed` 无法确认 0.19.0 为最新，本轮用本地 `version.py` 的 0.19.2 对照，不把版本差当作修复证据。

## 三、处置分层与优先级

| 批次 | 项 | 依赖 / 环境 |
| --- | --- | --- |
| A 离线可交付（本轮计划，**2026-11-09 已交付**，见第五节） | F02、F03、F07、F04 回执、F11 文档契约、F05 的 compact `limits_note` | 仅 Python 单测与文档，不连 Creo、不编译原生、不改公开工具签名；六项均为「离线已交付、实机未验」 |
| B 原生 / 实机（**2026-11-09 子计划已建立，实机未执行**） | F01 无 callback 放样与 seed 预检、F09 着色预览、F06 阶段进度与日志、F08 选择性布尔、F10 锥台/拔模、F11 原生错误上下文 | 匹配 Creo SDK 编译 + 实机几何/保存重载 + 适用失败回滚；本机 Creo 12.4.0.0；拆为 B1—B6，见[子计划](../../superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md) |
| C 公开契约 / 黑盒（**2026-11-09 提示词已建立，黑盒未执行**） | F08/F09/F10 的参数设计、`creo_capabilities` 限制标注、`update` 版本可确认性 | 公开契约变更需 WorkBuddy 黑盒预算验收，开发者证据不替代；拆为 C0—C5，见[黑盒提示词](workbuddy-blackbox-prompt.md) |
| 明确不纳入 | 把 Creo 10 独立复测或双版本验收列为发布门槛（2026-10-15 用户已取消）；F05/F10 的「能力整体不可用」结论；未经用户明确确认擅自连接 Creo 做实机测试，以及任何情况下擅自重启/结束 Creo 或清 unknown 保护 | 项目规则（实机放行条件已于 2026-11-09 改为用户确认制） |

报告建议优先级：F02 → F01/F05 → F03 → F11 → F08/F10 → F04/F06 → F09 → F07。本轮按「先离线低风险、不触碰需要实机的公开契约」调整，A 批先做并于 2026-11-09 交付；B/C 批已于同日另出[B/C 批子计划](../../superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md)与[WorkBuddy 黑盒提示词](workbuddy-blackbox-prompt.md)，**实机与黑盒验收仍留卡、未执行**。

## 四、验收口径

- A 批：Windows / Python 3.12+；新增用例放 `tests/unit/test_*.py`、`unittest`、`test_*`；`.venv\Scripts\python.exe tools\dev_check.py`、全量 `tools\test_unit.py`、`tools\check_backlog_counts.py` 与 `git diff --check`；不要求 Creo 10 独立复测或双版本验收。
- B 批：匹配 SDK 构建、对应驱动、几何/尺寸/单位、`saved_file_reloaded_and_verified=true`、适用失败回滚；证据记录提交、dirty、源码指纹、命令、环境和未测范围。
- C 批：WorkBuddy 只通过公开 MCP 黑盒验收，不读源码、不跑本地脚本；无法由 MCP 观察的项目记为「未验证」。
- 已发布 `v0.19.2` 的标签与四附件不得覆盖；A 批不改动时也不单独发布，合入 `main` 时按同流程交付对应版本 Release。

## 五、A 批离线交付记录（2026-11-09）

| 编号 | 任务 / 提交 | 交付内容 | 验证 |
| --- | --- | --- | --- |
| F02 | Task 1 / `2cc932e` | `validate_solid_profile` 以 `RESIDUAL_RATIO=1e-3` 放行浮点残差闭合轮廓，保留 `5e-7` mm 以上的既有保护；所有拒绝追加补救建议 | 7 个新测试 + 5 个回归模块共 66 测试 OK；独立审查规格/质量双 ✅ |
| F03 | Task 2 / `04d36b0` | `schema_base.Dimension`（上限 `1e6` mm、拒绝 bool、错误说明是服务 API 上限）用于 4 个半径/尺寸字段，`Positive` 不变 | 67 测试 OK；独立审查双 ✅ |
| F07 | Task 3 / `a25c969` | 更新检查失败文案给出 `MECHDOG_UPDATE_TIMEOUT_SECONDS` 与 `creo_check_update(force=true)`，默认 5 秒预算不变 | 43 测试稳定复跑 OK（一次未归因的偶发 `errors=1` 记为 concern，Task 7 全量单测已复跑通过）；独立审查双 ✅ |
| F11 | Task 4 / `3f1cdc9` | `SketchOp.offset` 描述、`creo_execute_plan` docstring、REFERENCE_SYNTAX 三平面对照；原生错误里附坐标仍留 B 批 | 54 测试 OK；独立审查双 ✅ |
| F04 | Task 5 / `68436b5` | `creo_session_status` 只读回执在 connect `-4` 时给显式 retry 步骤，不自动重启、不清 unknown 保护 | 72 测试 OK；独立审查双 ✅ |
| F05 | Task 6 / `b3bfcdf` | compact `families.surface_loft.limits_note`（≤160 字符、单一真源），全量 `limits` 与 `surface_boundary_fill` 门禁不变 | 55 测试 OK；独立审查双 ✅ |

统一证据：`tools\dev_check.py --work-item DEV-081 --unit-timeout-seconds 1200` → `success=true`、`unit_tests=passed`（全量）、`native_validation=not_run`；`tools\check_backlog_counts.py` → `consistent=true`；`git diff --check` → 0。六个任务均为「离线已交付、实机未验」，B/C 批仍按第三节留卡。
