# MCP_CREO_MechDog 0.4.6 版本说明

日期：2026-10-21。版本类型：**PATCH**（用户 2026-10-21 明确指定两批统一按 PATCH 发布；包含新增公开工具 `creo_erase_session_models`，按版本约定本应为 MINOR，遵用户指定作为本版例外，同 0.4.1/0.4.2 先例；工具数 87→88）。实施计划：[0.4.3 反馈完善计划](development/0.4.3-feedback-improvement-plan-2026-10-21.md)；实施记录见 [FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21](validation/FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)。

## 修复与功能

- **BUG-076（收养链路 16 MiB 元数据预算阻断，资料分离精修）**：在 0.4.5 定位诊断基础上分离控制元数据与完整检查资料——结果、令牌、请求和登记只保存摘要（`inspection_summary`）及受控文件引用（`inspection_ref`：路径/SHA256/字节数），完整几何资料移入 job/模型输出目录的内容寻址 sidecar 文件（同内容幂等、不同内容不覆盖旧引用）；覆盖 inspect/apply/prepare/confirm、快照续签与登记读取（含 reconciliation 路径），apply/confirm 请求发送 `live_inspection_ref`/`source_inspection_ref` 并兼容旧内联记录；引用被篡改、截断、缺失或指向服务目录之外时明确拒绝，无半登记。超过 16 MiB 的完整资料贯通各模式不再触发预算错误（>16 MiB 夹具单测验证 evidence/登记 <64 KiB）；源模型、复制后、保存重载的带容差比较不变；**不提高限额、不删几何核验**。普通建模作业的登记与查询快照契约保持内联原状。
- **BUG-057（toolkit_lock 并发准入 PermissionError，锁方案统一）**：新增包内统一 Windows 锁文件打开机制（`creo_mechdog/lock_files.py`）：优先 `OPEN_EXISTING`，不存在时 `CREATE_NEW`，首建碰撞（ERROR_FILE_EXISTS）或首建阶段拒绝访问时仅一次共享打开回退；其他错误保留原始错误码。`toolkit.lock` 与 `startup.lock` 统一使用（路径独立）；启动协调新增 `lock_error` 状态与结构化 `CoordinatorLockError`（lock_access_error，含 phase/winerror），不再把锁访问失败误报为 `configuration_error`；字节锁竞争保持 `ToolkitBusy`，忙即拒绝、无排队/重试语义不变。离线诊断脚本保留 CRT 对照与生产打开路径双统计。
- **FEAT-046（新增 `creo_erase_session_models`）**：显式擦除选定的会话模型清单。`inspect(targets=[{name, model_type}])` 返回每项目标身份、阻断原因（未保存/已修改/受管/清单外引用/依赖环）、装配先于组件的擦除顺序、预期剩余对象和 600 秒令牌；`apply(evidence_token, idempotency_key)` 仅执行令牌中的清单（不可扩大），返回 `job_id` 轮询，全作业单一 Toolkit 通道锁。逐项复核身份/修改状态/来源后 `ProMdlErase`，并经两次独立查询确认消失；中途失败停止剩余项并明确报告已完成/未确认清单。不保存模型、不删除磁盘文件；受管模型仍归 `creo_reconcile_model`。
- **FEAT-043（会话可观察性）**：`creo_list_session_models` 响应新增 `snapshot_age_seconds`、`refresh_guidance` 与 `service_session_changes`（本服务自快照以来引起的会话内容变化，跨进程有界记录，GUI 手工变化标注未实时复核）；`creo_open_file`/收养/恢复/擦除成功后写入变化记录。省略 cursor 实时重采、携 cursor 冻结快照语义不变。
- **FEAT-044（打开后的会话摘要）**：`creo_open_file` 成功结果新增有界 `open_file.loaded_session_models`（区分会话模型数与本次装配打开的组件实例数、有界 20 条页、详情入口）；`SESSION_NAME_CONFLICT` 冲突提示补充装配依赖加载来源。
- **DEV-027（世代盘点 dry-run）**：`creo_callback_status` 结果新增 `generation_inventory`：当前世代、注册世代与各世代目录 SHA256 盘点，非当前且未注册者列为 `reclaim_candidates`；`dry_run=true` 不删除任何目录，实际回收另按安全规则执行。
- **DEV-043（台账精简，随版交付的文档整理）**：主台账只展示未完成工作与两项历史观察，已完成 BUG 移入完成档案；开发入口/README/架构说明去掉旧轮次当前状态，旧计划标注执行结果。详见 [DEV-043](work-items/DEV-043.md)。

## 验收摘要

- 502 项单元测试（新增 `test_lock_files.py` 9 项、`test_adoption_split.py` 7 项、`test_session_erase.py` 5 项；随接口与工具数调整更新若干）+ `tools/dev_check.py` 通过；SDK 构建通过（worker 链接新增 `bcrypt.lib`，复用 `callback_identity.h` 的 SHA256）。
- 实机（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK，stdio 直连工作区新 server 实例）：`tools/test_general.py` 原生建模集成全过（`GENERAL_CORE_SUCCESS=1`，几何断言 BRACKET_VOLUME=10600.0）；本轮改动点冒烟全过——`creo_open_file` 成功含 `loaded_session_models`（12 条会话模型、`opened_session_model.is_current=true`）；收养种子零件 inspect（`inspection_summary`+`inspection_ref` 齐全）→ apply（revision=1）→ `creo_list_models`/`creo_inspect_model` 查询正常（`snapshot.source=saved_verified`）；擦除：含受管副本的清单整体拒绝（`managed` 阻断）、纯种子清单 available → apply 擦除成功并确认消失 → 擦除后同一文件可再次 `creo_open_file`；快照年龄字段正常。锁诊断双路径三状态×60 轮均恰好一方获准一方 busy。
- 实施过程发现并修复：native 结果拆分最初影响普通建模登记（`KeyError: inspection`），已收窄到收养/恢复请求并使查询系统兼容引用形态；`creo_get_job` compact 透传 `session_erase`；`session_erase` 摘要因 JSON 值语义脱离报告的缺陷已改为引用绑定。

## 环境与未测范围

- 本机 Windows x64 / Python 3.12 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC。未测：**BUG-076 原环境（Creo 10）超限文件类别、实际字节数与部署身份未取得，本机通过不外推为 Creo 10 已通过**；BUG-057 外部 Windows 10 19045/Python 3.13.14 原环境重跑（含双进程各 200 轮）；擦除的装配+组件多级清单实机矩阵与幂等重放；`loaded_session_models` 装配打开实机观察；WorkBuddy 公开黑盒验收（建议作为发布后复核）。
- 升级后请重启目标 MCP 连接器使新逻辑生效；既有作业、模型登记、令牌与保护语义不变，旧内联记录继续兼容读取。

历史版本：[0.4.5](RELEASE_NOTES_0.4.5.md)、[0.4.4](RELEASE_NOTES_0.4.4.md)、[0.4.3](RELEASE_NOTES_0.4.3.md)、[0.4.2](RELEASE_NOTES_0.4.2.md)、[0.4.1](RELEASE_NOTES_0.4.1.md)、[0.4.0](RELEASE_NOTES_0.4.0.md)。
