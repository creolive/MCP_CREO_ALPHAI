# FEAT-048：按路径及批量收养

类型：功能

优先级：P1

状态：验收中（Task 5 离线实现；实机 / WorkBuddy 待验收）

目标版本：下一 MINOR（0.5.0 反馈第二批）

来源与关联：[装配编辑流程改进建议 P1-1](../validation/feedback-0.5.0-2026-10-22/2026-10-22_CREO10_v0.5.0_装配编辑流程改进建议.md)（外部 Creo 10 / 0.5.0 实操 asm_mx → asm_edit_demo；P1-2 多组件单作业归 FEAT-008 现有 `creo_execute_plan` 示例与验收，不在本卡）；[0.5.0 反馈整合计划](../development/0.5.0-FEEDBACK-PLAN-2026-10-22.md) 第二批；关联 [FEAT-008](FEAT-008.md)、[DEV-046](DEV-046.md)。

## 问题或目标

`creo_adopt_current_model` 只能收养"当前窗口模型"：收养一个组件必须 open_file → adopt inspect → apply → 轮询四步串行，8 组件实测约 5.5 分钟纯串行，100 组件装配约 1 小时以上，路线 A 在真实装配上基本不可用。反馈方建议按路径收养（不要求也不改变当前窗口）与批量收养；多组件单作业装配（P1-2）已由现有 `creo_execute_plan` 支持，归 FEAT-008 官方示例与验收，非本卡新增工具。报告中预计收益（100 件从 ~1h 降到分钟级）仅为建议，不作承诺。

## 范围

包含（按 0.5.0 反馈计划第二批设计）：

- 新增统一收养入口（如 `creo_adopt_file(file_path, mode="inspect", evidence_token=None, idempotency_key=None)`），支持单路径与路径列表，采用 inspect/apply、证据令牌与幂等键；不要求也不改变当前窗口，源文件只读，内部完成 retrieve + 预检 + 复制。
- 首期仅支持健康、毫米、无外部依赖的零件/钣金件；批量收养在单通道内顺序执行，每件独立提交并返回独立结果。
- 普通单件拒绝不撤销此前成功项；通道结果未知时停止剩余项并保留保护，不自动重试（保持单通道忙拒边界，无排队）。

不包含：多组件单作业批量装配（现有 `creo_execute_plan` 已支持，归 FEAT-008 官方示例与验收，第二批）；不健康零件收养（先补 FEAT-006 逐特征诊断；只读装配源降级为后续候选）；装配整体收养（后续路线，须同时完成依赖复制、引用重映射与装配 reconcile）；多 job 并行或队列。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | 批量链路单测 | 重复实例、逐项失败、幂等回放、revision、保存重载覆盖；一项失败不撤销其余已成功项，通道未知停止剩余并保留保护 |
| 本机 Creo 12.4 / E 盘 dev 服务 | 多组件装配按路径及批量收养实机（须先满足会话核对条件） | 每件独立结果、保存重载 `saved_file_reloaded_and_verified=true`；收养动作不改变当前窗口、源文件只读 |

## 实现与证据

2026-10-23 预登记，未实施。

### 2026-10-24 Task 5 implementation scope (registered before behavior edits)

Status at registration: implementation in progress; live Creo / WorkBuddy acceptance pending.

Approved API: `creo_adopt_file(file_path: str | list[str], mode="inspect", evidence_token=None, idempotency_key=None)`, 1-20 ordered paths, internal unique names, 600-second tokens. Exact numeric/latest version selection; source files are read-only; native retrieve/copy never displays. Only healthy millimeter dependency-free parts/sheetmetal are admitted. Duplicate origins produce `duplicate_source` / `duplicate_of`.

One parent holds the channel across independent durable item journals and revision=1 save/reload commits. Known refusals continue; unknown execution or commit stops remaining dispatch and preserves protection. Replay/poll only materializes known durable decisions. Parent lifetime covers bounded sequential execution; no general budget API.

Controller clarification: an existing unmodified exact-origin resident is allowed with explicit `existing_resident` provenance, session/id/versionstamp/live inspection plus stable disk SHA. Pre-inspection disk/resident content equality is unknown (a file might have been externally replaced before inspection). Fresh disk semantics require the name to be absent through prior manual session management. No automatic erase or rename.

Verification: offline temporary-root regressions (identities, expiration, replay, duplicates, partial success, unknown stop, metadata interruption), Windows / Creo 12.4 SDK compile and production helper harness, final unified dev check. No Toolkit connection, Creo process/session actions, recovery/unknown clearing, original service data/config changes, version bump or publication. Actual window preservation, source bytes, save/reload/revision and WorkBuddy remain unverified until session clearance.


### 2026-10-25 offline implementation and evidence

Implemented the [path-adoption contract](../FILE_ADOPTION.md), public tool/capabilities, native no-display selector with explicit resident provenance, independent durable per-item commits and unknown stop, bounded parent polling and metadata-only idempotent replay. Current development registry has 92 public tools; historical 0.5.2 release records retain 91.

Validation environment: Windows 11 x64 / Python 3.12.14 / local Creo 12.4 Toolkit SDK / MSVC x64, private editable worktree `E:/Projects/md050`. Tested source: base `c50fd653e7974a64706abfd46071941a62de61fc`, dirty=true, final checked source SHA256 `c68dee7becfd45409621e6879315c9ca9752c0ec0f846b76eac4a03c6389cff6`.

- `.venv/Scripts/python.exe -m unittest tests.unit.test_file_adoption -q`: final focused 28 passed (7.143s); includes deterministic stale-parent polling regression. Existing adoption/open-file focused suite: 71 passed; reconciliation suite: 66 passed before the last two path cases.
- `.venv/Scripts/python.exe tools/test_adoption_source.py`: SDK-independent production source-state helper compiled and passed 12 checks; report `build/adoption_source_test/report.json`.
- `.venv/Scripts/python.exe bridge.py build`: full SDK compilation succeeded on 2026-10-24; final 2026-10-25 build validated/reused the same matching binary. Worker SHA256 `95fbe6d7be50fad58bf7a0b2b62ff3e2d4e14e13559533381d5e0ee6e3b47667`. Existing C4819 code-page warnings remain; no error.
- `.venv/Scripts/python.exe tools/dev_check.py --work-item FEAT-048`: final stable-source run passed, 595 tests / 0 failures / 0 errors, 152.796s; `build/feat048-dev-check-final.log`, `build/development_check.json`, `build/unit_test_report.json`. No baseline modifications. Interim run retained separately: three old tool-count assertions and three in-flight source-change detections; all corrected before final run.

No Toolkit/live integration or WorkBuddy execution. Actual window/source preservation, fresh/resident selection behavior, native health/units/dependencies, save/reload/revision, modified/wrong-origin cases and other Creo versions remain unverified. The added `tools/test_file_adoption.py` is a future permitted integration scenario, not current native evidence. Independent review remains required before the controller advances the plan.

### 2026-10-25 复审登记（main 0.5.3 整合后，行为修改前）

背景：复审前已把 origin/main（b5ad5d5，0.5.3）merge 进本分支（合并提交 85d5178），
21 个暂存文件的保全提交 d563958 的 tree 与保全备份 index tree
08ba93a3… 一致；历史 docs/validation 原件未改写。

上游复审确认缺陷（review-findings.json，本地复现一致）：`inspect` 在获取
`bridge.toolkit_lock` 之前创建 parent 作业目录并发布 running 清单；通道忙碌时
`ToolkitBusy` 拒绝受理，但遗留一个 `adoption_file_inspect`/`running` 孤儿目录
（native_calls=0），违反“忙碌拒绝不接受作业、不留接受态”契约。

本轮范围（最小修复，不扩功能）：`inspect` 的 parent 目录创建与首次清单发布移到
`toolkit_lock` 获取之后；忙碌拒绝不得遗留 job/runner/model/intent/证据或任何
接受状态。`apply` 路径复查确认目录创建于锁内（无泄漏），补回归锁定该行为。
验收：inspect 与 apply 在持有通道锁时拒绝且零新增作业目录、零 evidence/intent、
零 model、零 native 调用；既有全部 FEAT-048 单测不回退。离线 mock 夹具，不连接
Toolkit，不改版本或发布。

修复结果（2026-10-25，提交 01a4cd8）：`inspect` 的 parent 目录创建与首次清单
发布已移入 `toolkit_lock` 之后；复现脚本确认忙碌拒绝零遗留；新增
`test_busy_inspect_rejects_without_any_job_artifact` 并强化 apply 忙碌回归；
合并树上 35 项重点单测、原生 helper（11+12 项）、SDK 编译与全量 dev_check
（647 项）通过。完整证据见
[BATCH2-STAGE1-REVIEW-2026-10-25.md](../development/BATCH2-STAGE1-REVIEW-2026-10-25.md)。

### 2026-10-25 第二批第二阶段：锁顺序修复结果

上游复审追加修复（本阶段实现，提交见批次证据）：新 `inspect`/`apply` 改为在
昂贵逐文件选择/哈希（`_select`）之前取得非阻塞通道锁；廉价 schema 校验
（键、token 格式）仍在锁前；已知幂等回放保持忙时只读返回并维持既有
路径/identity/token 绑定契约（回放仍执行 `_select` 绑定身份）。不增加排队/
重试，不改幂等语义。

回归（`tests/unit/test_file_adoption.py` +3，共 32 项）：持锁时新 inspect/
新 apply 未进入 `_select`（side_effect 断言）、identity、native，且零作业/
intent/evidence/model 接受状态；忙时回放仍绑定身份并返回同一父作业。既有
全部 FEAT-048 单测不回退；全量 dev_check 666 项通过（证据见
[BATCH2-STAGE2-IMPLEMENTATION-2026-10-25.md](../development/BATCH2-STAGE2-IMPLEMENTATION-2026-10-25.md)）。

配套：批量收养实机驱动补 provenance（fresh/existing_resident）与拒绝原因
断言、唯一报告目录；guard-root 开发者实机入口
`tools/guarded_live_run.py`（最外层持主工作树真实通道锁再顺序运行 md050
子进程，锁忙即停，离线回归 3 项）。实机仍未连接。

### 2026-10-25 第二批第二阶段登记（行为修改前）

上游复审追加：01a4cd8 后 `inspect` 仍先 `_select(paths)`（逐文件哈希，可能
每件数秒）再取通道锁；`apply` 新提交同样先 `_select` 再检查锁。项目契约
要求通道忙立即拒绝，新提交不得先做整批耗时文件选择/哈希。本轮最小修复：
新 `inspect`/`apply` 在昂贵选择前取得非阻塞通道锁；廉价 schema 校验
（键格式、token/key 形态）仍在锁前；已知幂等回放保持忙时只读返回并维持
既有路径/identity/token 绑定契约。不增加排队/重试，不改幂等语义。

范围还包括第二阶段配套（登记于 FEAT-008/DEV-046）：批量收养实机驱动补
fresh/existing_resident 来源、健康/单位/依赖拒绝与幂等回放断言；开发者
guard-root 实机执行入口（只准备不连接）。

验收：离线 mock 回归——持锁时新提交未进入 `_select`/identity/native、无
作业/模型/intent/证据接受状态；回放路径不变；既有 FEAT-048 单测不回退。
环境：Windows 11 x64 / Python 3.12.14 / 本机 Creo 12.4 SDK（仅离线编译），
不连接 Toolkit。

### 2026-10-25 第二批第三阶段登记（复审收口）

guard-root 异常路径收尾修复（启动前基线、终态确认与通道静止后才释放、
unknown 保留）与管线驱动外部夹具制备修正，范围与验收见
[FEAT-008](FEAT-008.md) 第三阶段登记；收养行为本体未改，实机仍待统一安排。

### 2026-10-25 第二批第四阶段登记（复审收口续）

guard 释放语义进一步强化：真实 main 锁只在"本轮受理作业全终态 + 无
md050 原生 worker 存活（checkpoint `native_pid` 身份与 `creo_worker.exe`
镜像扫描双证据）+ md050 字节锁空闲"时释放；不可证实时入口持续存活持锁，
`--settle-timeout` 仅写报警；unknown 安静后可释放但返回失败并保留保护。
收养驱动 provenance 断言随原生实际值修正为 `fresh_retrieval`（工作树
既有未提交修正，本轮一并提交）；收养行为本体未改。范围与验收见
[FEAT-008](FEAT-008.md) 第四阶段登记与
[BATCH2-STAGE4-REVIEW-CLOSEOUT-2026-10-25.md](../development/BATCH2-STAGE4-REVIEW-CLOSEOUT-2026-10-25.md)。
实机仍待统一安排。
