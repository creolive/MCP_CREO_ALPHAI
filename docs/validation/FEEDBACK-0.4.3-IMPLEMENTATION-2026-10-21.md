# 0.4.3 反馈完善计划实施记录（开发分支）

日期：2026-10-21。实施分支：`codex/dev-043-ledger-simplification`（自 main `e3848f0`，叠加 DEV-043 文档整理工作区）。实施依据：[0.4.3 反馈完善计划](../development/0.4.3-feedback-improvement-plan-2026-10-21.md)。版本保持 0.4.5（开发分支不发布；用户 2026-10-21 指定两批统一随 0.4.6 PATCH 发布——含新增公开工具 `creo_erase_session_models`，按约定本应为 MINOR，遵用户指定作为本版例外）。

计划中 DEV-027/030 构建改进已随 0.4.4 交付、BUG-076 定位诊断已随 0.4.5 交付，本轮不重复实施。

## 第一批：BUG-076 资料分离精修 + BUG-057 锁方案统一

### BUG-076：控制元数据与完整检查资料分离

变更：

- 新增 `src/creo_mechdog/inspection_refs.py`：受控引用（路径/SHA256/字节数，内容寻址文件名）的创建、校验加载、摘要和请求字段生成；引用指向服务目录之外的路径、被篡改、截断或缺失时拒绝。
- `native/generic.cpp`：`write_inspection_ref`/`read_inspection_ref`/`choice_inspection`/`split_report_inspections`；交付前把 `live.inspection` 与 `inspection` 完整资料移入 job 目录内容寻址 sidecar，native_result.json 只留引用；请求端 `live_inspection`/`source_inspection`/model.inspection 支持 `*_ref` 形式并兼容旧内联。
- `src/creo_mechdog/adoption.py`：`_native`/`inspect`/`_run_locked` 双层拆分（真实执行器与替换边界一致）；evidence 令牌、request、model.json 登记、intent journal 与 job manifest 只保存摘要+引用；apply/confirm 请求发 `live_inspection_ref`/`source_inspection_ref`；旧内联记录读取路径全部兼容。
- `src/creo_mechdog/reconciliation.py`：candidate/model/live 的 inspection 兼容 ref 与内联；恢复请求改发引用；成功登记只写摘要+引用。
- `bridge.py` compact：透传 `inspection_ref`/`inspection_summary`/拆分后的 `live`。
- worker 链接补 `bcrypt.lib`（sidecar SHA256 复用 `callback_identity.h` 的实现）。

验证：`tests/unit/test_adoption_split.py` 7 项（内容寻址幂等、内联拆分、ref-only no-op、篡改/截断/缺失/外部路径拒绝、>16 MiB 完整资料贯通 inspect 无预算触发且 evidence/登记 <64 KiB、请求引用与旧内联回退）；`test_adoption.py`/`test_adoption_budget.py`/`test_reconciliation*.py` 既有 80 项随接口调整更新后全过。实机链路（打开→收养→编辑→保存重载，复杂零件详情分页取全）待会话可操作核对后执行。

### BUG-057：统一 Windows 锁文件打开机制

变更：

- 新增 `src/creo_mechdog/lock_files.py`：`OPEN_EXISTING` → `CREATE_NEW` → 首建碰撞（ERROR_FILE_EXISTS=80）/首建阶段拒绝访问（ERROR_ACCESS_DENIED=5）时仅一次共享打开回退；其他错误保留原始错误码；常驻文件、不共享删除、非阻塞字节锁语义不变。
- `bridge.py` `_open_toolkit_lock` 与 `creo_startup.py` `coordination_lock` 统一改用该机制（两种锁路径独立）。
- `creo_startup.py` 新增 `CoordinatorLockError`（kind=lock_access_error，含 phase/winerror/errno/filename）：锁访问失败发布 `lock_error` 状态并附结构化 `coordination_error`，不再落入 `configuration_error` 分支；字节锁竞争仍为 `CoordinatorBusy`。
- `tools/reproduce_toolkit_lock.py` 双路径：CRT `open("a+b")` 对照与生产 `open_lock_file` 并列统计。

验证：`tests/unit/test_lock_files.py` 9 项（首建 CREATE_NEW、既有文件不重建、碰撞回退一次、回退失败保留原始码、既有文件 ACL 错误不回退、非碰撞错误直抛、共享读写无删除、CoordinatorLockError/CoordinatorBusy 分类）；诊断脚本本机 60 轮×三状态×双路径全部 `acquired+lock_busy`（恰好一方获准一方 busy），生产路径共享冲突保留 winerror=32、delete-pending 保留 winerror=5。外部 Windows 10 19045/Python 3.13.14 复验继续开放。

## 第二批：会话管理与可观察性

### FEAT-046：creo_erase_session_models（新工具，随 0.4.6 交付）

- `native/generic.cpp` `session_erase_native`：inspect 完整清单+资格（有盘/未修改/非受管）+全会话依赖图（清单外引用、依赖环拒绝）+装配先于组件的拓扑序+预期剩余对象；apply 逐项复核（存在性/修改状态/origin/受管）→ ProMdlErase → 两次独立查询确认消失，中途失败停止并报告 erased/unconfirmed/remaining。
- `src/creo_mechdog/session_erase.py`：inspect 同步探查+600 秒令牌（仅 available 清单签发）；apply 令牌校验（缺失/过期/跨键拒绝）+幂等 journal+后台 job（`bridge.run_job` 分发 kind=session_erase），全作业单一通道锁。
- `server.py` 注册 `creo_erase_session_models`（工具数 87→88，三处数量断言同步）；`capabilities.py` families 增加 `session_erase`。

验证：`tests/unit/test_session_erase.py` 5 项（available/blocked 令牌签发、非法 targets 拒绝且不建 job、令牌缺失/过期拒绝、幂等重放与跨键拒绝、apply 成功记录会话变化）。实机装配+组件清单 inspect→apply、擦除后再次 `creo_open_file` 待执行。

### FEAT-043：快照年龄与会话变化记录

- `session_models.py`：响应增加 `snapshot_age_seconds`、`refresh_guidance`、`service_session_changes`（有界，自快照创建起）与说明；新增 `record_session_change`（跨进程、有界 50 条、通道锁内写入）。
- 接入点：`creo_open_file` 成功、收养 apply/confirm 成功、恢复 accept_live/restore_baseline/accept_saved/abandon_new 成功、擦除成功。

### FEAT-044：loaded_session_models 摘要

- `native/generic.cpp` open_file 成功尾部：一次全量枚举输出 `open_file.loaded_session_models`（会话模型数、组件实例数及统计口径、有界 20 条页、has_more、详情入口）；`SESSION_NAME_CONFLICT` 消息补充装配依赖加载来源提示。

### DEV-027：世代盘点 dry-run

- `blend_callback.py` `generation_inventory`：当前世代（build stamp）、注册世代（setup 元数据/registry exec_file）与其余世代目录的 sha256/字节数盘点，`reclaim_candidates` 仅列出、`dry_run=true` 不删除；挂载于 `creo_callback_status` 结果 `generation_inventory`。本机当前世代 `695fdd07…`、4 个回收候选。

## 总体验证

- `python -m unittest discover -s tests`：502 项全部通过（新增 21 项：lock 9、split 7、erase 5；随接口调整更新若干）。
- `tools/dev_check.py`：通过（success=true），无新增语言问题；新文件已按 ruff/clang-format 格式化。
- `bridge.py build`：SDK 构建通过（含 bcrypt.lib 链接变更与 clang-format 后重编译）。
- 环境本机 Windows x64 / Python 3.12 / Creo 12.4 SDK；工具数 88。

## 未测与开放范围

- 实机验收（需先满足会话可操作核对）：收养真实零件全链路与 >16 MiB 实机夹具、擦除装配清单、loaded_session_models 实机观察、锁跨进程双 200 轮（BUG-076/046/044/057 各卡）。
- 外部原环境：BUG-076 超 16 MiB 阻断复测（Creo 10）、BUG-057 Windows 10 19045/Python 3.13.14 复跑。
- WorkBuddy 黑盒复核（发布后）；三份反馈原件的归档核对在交付流程完成。
- 台账：BUG-076/BUG-057/FEAT-046 转"验收中"，剩余动作见各卡。
