# 2026-11-09 第四份 0.19.0 反馈 B/C 批子计划（规划，不实施）

关联：[DEV-081](../../work-items/DEV-081.md) · [MAPPING](../../validation/feedback-0.19.0-frigate-2026-11-08/MAPPING.md) · [A 批离线计划](2026-11-09-feedback0190-frigate-offline.md) · [WorkBuddy 黑盒提示词](../../validation/feedback-0.19.0-frigate-2026-11-08/workbuddy-blackbox-prompt.md)

日期：2026-11-09。分支：`codex/DEV-080-feedback-0190-followup`。基线：已发布 `v0.19.2`，A 批 9 个提交，另有 [DEV-080](../../work-items/DEV-080.md) 首批离线收口提交 `c983022`。

## 0. 本文件的性质与边界

**这是一份留卡子计划，不是实施记录。** 本轮只交付 B/C 批的任务拆分、前置条件、验收口径与黑盒提示词；**不改任何 `native/*.cpp`、公开 MCP 签名、`capabilities.py` 门禁、`version.py`，不连接 Creo、不编译执行器、不做故障注入、不启动/结束会话、不清 unknown 保护、不联网、不发布**。

- 编号沿用 MAPPING 的 F01—F11，工作卡沿用 DEV-081，**不新增台账 ID、不改变 `docs/BACKLOG.md` 的 172 / BUG 75 / FEAT 61 / DEV 36 计数**；B/C 批是 DEV-081 内部的子批次，不是新工作项。
- 源码位置来自 2026-11-09 对 0.19.2 的静态核对（见 MAPPING 第一节）。A 批改过 `schema.py` / `server.py` 的文本层，**行号仅作定位参考，每个任务实施前必须重新定位**。
- B 批每个任务实施时按项目规则登记验收方式与环境，仍采用用户选定的 Subagent-driven 流程：逐任务实现、另一个只读代理审查通过后才进入下一个。
- 报告方的 Creo 10 / 0.19.0 结论只作为报告方证据；不外推为本机实机验收。`update.status=failed` 使其无法确认版本是否最新，版本差不当作修复证据。
- 明确不纳入：把 Creo 10 独立复测或双版本验收列为发布门槛（2026-10-15 用户已取消）；F05「曲面能力整体不可用」、F10「draft 需逐面引用」这两项报告方自己声明未实测的推断；把 F04 的 connect `-4` 归因于 seed loft。

## 1. 全局前置条件（任一不满足则不启动 B 批）

| 前置 | 判定方式 | 缺失时 |
| --- | --- | --- |
| BUG-001 实机回归卡死根因已核对，且确认会话可操作 | 按 `docs/validation/BUG-001-recovery-2026-10-17.md` 与现场确认；不由本计划代判 | **停止**，不建立新的 Toolkit 连接、不做故障注入、不启动/结束 Creo、不清 unknown 保护 |
| 本机 Creo 12.4.0.0 + 匹配 Toolkit SDK + 可用许可 + MSVC x64 | `.\setup.ps1 -CreoRoot <实际路径>` 与 `bridge.py build` | 停止；不交付未编译的原生分支 |
| `native/constants.inc` 按本机 SDK 重新生成 | `tools/generate_constants.py` | 停止；该生成物不提交、不从别处复制、不进发布附件 |
| 本机联调只启用 `MCP_CREO_MechDog_dev` 并指向 `E:\Projects\MCP_CREO_MechDog` | 客户端配置（本机约定） | 停止；旧 C 盘副本与 test 项保持禁用 |
| WorkBuddy 会话可用且已连接上述服务 | 由 MCP 公开接口确认，不读本机配置 | C 批只交付提示词，不报黑盒通过 |

任何建模任务只在**确认会话可操作之后**提交；已接受的任务只轮询 `creo_get_job`，通道忙时立即接受 `status="busy"` 拒绝，不重试、不排队、不假设 FIFO（BUG-009 边界）。

## 2. B 批（原生 / 实机）任务拆分

每个任务的验收都必须记录：提交号、工作树 dirty 状态、受测源码指纹、命令、Creo/SDK/许可环境、`saved_file_reloaded_and_verified`（适用时）、几何/尺寸/单位、revision、适用失败回滚、原始错误与未测范围。**开发者单测不替代原生或实机验收**。

### B1 — F01 无 callback 原生放样与 seed 兼容性前置预检（P1，阻断）

- 现状：`src/creo_mechdog/blend_callback.py` 的 `prepare_callback` / `callback_setup_status` 要求 `readiness=ready`；`native/blend_create.cpp` 抛 `BLEND_CALLBACK_SETUP_REQUIRED`；`generic_bridge.py` 的 seed 路线已有 2–20 截面、递增 Z、闭合轮廓预检与按截面数选 seed。失败发生在 connect 阶段 `code -4`，此时两 sketch 均未执行、`model_unchanged=true`。
- 目标：让不人工注册并启动 DLL callback 的客户端至少走通一条**可查询状态**的放样路径；在提交作业前给出 seed 兼容性预检结论，避免连接后才发现不可行。
- 候选设计（实机裁定，不在本计划定论）：① 把 seed 路线的 callback 准备改成一次性、可查询状态机；② 增加不依赖 callback 的轻量双截面/多截面路线，沿用 [FEAT-009](../../work-items/FEAT-009.md) 与 FEAT-025 的边界；③ 只补预检与明确失败回执，暂不改几何能力。
- 关联：DEV-079 H01 的 `Probbl.h` 缺头编译缺口、[FEAT-025](../../BACKLOG_COMPLETED.md#legacy-feat-025)。缺头 SDK 下不得声称放样可用。
- 实机验收：编译执行器后跑对应 `tools/test_*.py`；至少一条成功路线给出 PRT 保存重载与体积/尺寸断言，一条不可行路线给出预检回执与 `model_unchanged` 证据；记录 connect `-4` 时的原始返回，不把 Creo 退出归因于放样。
- 不做：不放宽 `surface_boundary_fill` 门禁；不把「曲面链整体不可用」当结论；不写第二份 `surface_loft` 限制描述（A 批已确立单一真源）。

### B2 — F11 原生错误上下文（P2，导致整批回滚）

- 现状：`native/generic.cpp` 的 `sketch_frame` 已算出 origin/normal（XY `+Z`、XZ `-Y`、YZ `+X`），但 `Extrude cut removes no material; check the sketch position, direction and depth against existing geometry` 不含实际坐标与有效深度。
- 目标：失败回执里附实际原点、法向与有效深度区间；优先结构化字段，避免只加长文本；不改公开工具签名。
- 实机验收：构造一组已知失败与一组已知成功的 plan，断言失败字段含可复算的坐标/法向/深度，成功路径不受影响；`creo_get_job` 终态与 revision 一致；A 批写入的 `SketchOp.offset` / docstring / [REFERENCE_SYNTAX](../../REFERENCE_SYNTAX.md) 三平面表述仍与原生行为一致。
- 不做：不改 `direction` 相对法向的既有语义，不改 XZ 的负 Y 法向。

### B3 — F06 阶段进度与原生日志体积（P2，不阻断）

- 现状：`src/creo_mechdog/native_stage.py` 的 `TAIL_BYTES=8192` / `HEAD_BYTES=4096` 与 `stall_report` 的 `log_bytes` / `truncated` / `stages_seen`；DEV-077 已交付 `verify_stages` 回退（DEV-079 MAPPING §6.3 标为已修，**不重复认领 tail 截断**）；当前仍无 index/total 紧凑阶段输出。
- 目标：单特征 15–20 秒、20 op 计划 5–8 分钟时，`creo_get_job` 能读到可读的阶段进度；3–7.7 MB 原生日志的体积治理与截断标记；批量事务合并先做可行性评估，不直接改。
- 实机验收：20 op 计划的阶段回执含 index/total 与耗时；日志体积上限与 `truncated` 一致；不破坏 compact 预算与 DEV-079 H05 的大作业 compact 路线。
- 不做：不以缩短日志为由丢失终态错误；不把「阶段可见」等同于「性能已优化」。

### B4 — F08 选择性布尔 / 切除作用域（P2，依赖 C 批设计先行）

- 现状：`ExtrudeOp` 与 `creo_extrude` 均无 `targets` / `scope`；`BooleanOp.targets` 是另一条路径。关联 [BUG-102](../../work-items/BUG-102.md) / [FEAT-051](../../work-items/FEAT-051.md)。
- 目标：先由 C1 定公开 schema（字段、默认值、向后兼容、错误回执），再由本任务实现原生作用域选择并实机验收。
- 实机验收：多实体模型中限定目标切除，断言非目标实体几何不变、保存重载后仍成立；非法 target 给出结构化拒绝且不改模型；revision 与回滚可用。
- 不做：设计未定稿前不改公开签名；不把 `BooleanOp.targets` 直接当 `ExtrudeOp` 语义复用。

### B5 — F09 着色预览（P3）

- 现状：`native/preview.h` 固定等轴测矩阵 + `ProRasterFileWrite`；`src/creo_mechdog/preview.py` 只投影 `preview_file` / `preview_status` / `preview_code`；全仓无 `preview_mode` / `view` / `fit_all` 参数。关联 [FEAT-041](../../work-items/FEAT-041.md)。
- 目标：给出可判读外观的着色预览与视角/适配参数，线框与全叠加基准不再唯一。
- 实机验收：同一模型分别产出线框与着色图，记录文件、体积、耗时与截图对比；失败时 `preview_status` / `preview_code` 可读；公开参数需 C1 一并设计。
- 不做：不把「生成了预览文件」当作「外观可判读」；不改 A 批已交付的 compact/full 分页预算之外的契约。

### B6 — F10 锥台 / 拔模参数入口（P2，先证伪推断）

- 现状：`ExtrudeOp` 无 `draft_angle` / `top_scale`；`creo_draft` 是独立工具（`surfaces` / `neutral_plane` / `angle` / `pull_direction`），报告**未提交也未查其 schema**。
- 第一步（必须先做）：查 `creo_draft` 的实际 schema 与实机可用范围，验证报告方「draft 需逐面引用」的推断是否成立；未验证前不写「能力缺失」结论。
- 第二步：按结果选择「复用 `creo_draft` 并补文档/示例」或「在 F01 轻量双截面路线里支持锥台」；参数设计归 C1。
- 实机验收：锥台/拔模模型的上下尺寸、体积、保存重载与 revision；非法角度/比例的结构化拒绝与回滚。
- 不做：不把报告方推断当事实；不改 `creo_draft` 的既有语义。

## 3. C 批（公开契约 / WorkBuddy 黑盒）任务拆分

执行载体是 [workbuddy-blackbox-prompt.md](../../validation/feedback-0.19.0-frigate-2026-11-08/workbuddy-blackbox-prompt.md)。**WorkBuddy 不读源码、不分析或修改源码、不执行本地 Python 测试脚本/单测/`dev_check`/源码压力探针**；提示词只给 MCP 操作场景、输入、预期结果与报告要求。环境、会话、可见工具与服务版本只通过 MCP 公开接口确认，接口未提供的构建身份或实现细节记「无法确认」。

| 任务 | 内容 | 前置 | 通过判据 |
| --- | --- | --- | --- |
| C0 只读基线 | 通过公开接口确认服务版本、启用工具数、会话健康与 `creo_capabilities` compact/full 行为 | 会话已连接；**不建立新的 Toolkit 建模连接** | 逐项记录实际返回；不读仓库/Git/本机配置补齐 |
| C1 契约设计 | F08 `targets`/`scope`、F09 `preview_mode`/`view`/`fit_all`、F10 `draft_angle`/`top_scale` 的字段、默认值、向后兼容、错误回执，以及 `known_limitations` / compact 预算同步 | B4/B5/B6 的实现方案草拟后 | 公开工具数与能力说明一致；compact/full 不丢关键限制 |
| C2 限制标注 | 黑盒确认 A 批 F05 的 compact `families.surface_loft.limits_note` 可被客户端消费，full 仍是完整 `limits`，`surface_boundary_fill` 仍不可用 | C0 通过 | 以 `creo_capabilities` 实际返回为准，不以单测断言代替 |
| C3 版本可确认性 | 黑盒确认 F07 失败文案给出 `MECHDOG_UPDATE_TIMEOUT_SECONDS` 与 `creo_check_update(force=true)`，且 `update.status=failed` 不被表述为「已是最新」 | C0 通过 | 记录原始返回；无法由 MCP 观察的内部重试/预算记「未验证」 |
| C4 A 批补证 | F02 精确圆弧闭合轮廓、F03 `R<=1e6` mm、F04 connect `-4` 回执、F11 三平面 offset/direction 的公开可见效果 | **BUG-001 根因核对完成且会话确认可操作** | 记录工具调用、输入、`job_id`/`model_id`、终态、几何/参数、保存重载、revision、回滚与原始错误 |
| C5 并发 | 仅当真实实施并发调用时才报告通过 | 会话可操作 + 明确的两客户端场景 | 未真实并发则写「未验证」，不推测 FIFO 或容量 |

报告要求：只有真实调用了并发才能写并发通过；文件占用注入、重试次数/预算、临时文件清理等只能靠源码或本地脚本观察的机制一律记「未验证」；开发者证据与 WorkBuddy 黑盒结论分别记录，不互相替代。

## 4. 实施顺序与收口

1. 先完成「全局前置条件」判定；不满足则本计划保持留卡，不启动 B/C 代码。
2. C0 只读基线与提示词阶段 0/1 可在会话已连接时先行（不新建 Toolkit 建模连接）。
3. C1 的 schema 设计先行于 B4/B5/B6 的原生实现；B1（阻断项）优先于其余 B 项。
4. 每个 B 任务按实机验收矩阵取证；每个 C 任务按黑盒提示词取证；两者都不以 A 批的离线单测代替。
5. 能力说明、[COMPATIBILITY](../../COMPATIBILITY.md)、[BACKLOG](../../BACKLOG.md) 与 DEV-081 工作卡在**真实能力发生变化时**才同步，规划阶段不改能力边界文档。
6. 合入 `main` 时按项目规则同流程发布对应版本 Release（四个附件 + 两个 `.sha256` sidecar，逐个列出文件名，发布后运行 `tools\check_release_assets.py --tag v<版本>`）；已发布 `v0.19.2` 的标签与附件不得覆盖。本轮无任何合入或发布动作。

## 5. 自审

- **Spec 覆盖**：MAPPING 第三节 B 批的 F01/F09/F06/F08/F10/F11 原生部分分别落到 B1—B6，C 批的公开契约/黑盒落到 C0—C5；A 批六项不重复认领；F05/F10 的未实测推断与 BUG-001 约束作为边界保留。
- **证据强度**：本文件是规划，不含任何实机/黑盒结论；所有通过判据都要求真实返回或实机几何，`native_validation` 在本轮仍为 `not_run`。
- **计数与范围**：不新增台账 ID、不改计数；不改 `native/`、公开签名、`version.py`、能力说明、生成物与已发布附件。
- **可追溯**：F 编号、工作卡、A 批提交与 WorkBuddy 提示词均给出链接；实施时需另建逐任务 brief/report/review package 并按 Subagent-driven 审查 gate 推进。
