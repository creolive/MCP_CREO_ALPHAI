# DEV-027 世代盘点口径补齐验证（2026-10-22）

按 [0.4.6 反馈整合计划](../development/0.4.6-FEEDBACK-PLAN-2026-10-21.md)并行事项实施。分支 `codex/dev044-feedback046`（自 main `62e6654`，0.4.7 已发布）。

## 改动

- `src/creo_mechdog/blend_callback.py` `generation_inventory(build, *, probe_readiness=None)` 重写：
  - **loader/payload 双维度**：`blend_loader/<指纹>/` 与 `blend_callback/<sha>/` 全量盘点，loader 世代经 `deployment.json` 关联 payload（登记缺失/损坏/指向不存在或哈希不符的 payload 均判待复核）。
  - **引用三态分类**：本地注册引用（setup `loader_file` 与 registry `exec_file` 两来源分别记录 `registered_by`）、运行证据（`file_locked`=DLL 镜像被进程加载锁定；`recent_ready_file`=`callback_result.json` 新鲜（30 天内）；`probe_ready`=native probe ready 时 setup 记录世代）、未知状态（记录缺失/损坏/冲突涉及者进 `needs_review`，逐条列 `review_reasons`）。
  - **记录状态显式化**：`records_status`（build_stamp/setup/registry 各 ok/missing/corrupt）、`record_conflict`+`conflict_generations`（两来源指向不同世代）、`records_definitive`（三记录 ok 且无冲突）。任一记录非 ok → 全部世代进待复核，不判候选；payload 仅在 records_definitive 且无引用时才判候选。
  - 回应外部 §5.2（"已注册但记录丢失 → 误列回收"）：reclaim_candidates 判定收紧为"每个引用维度均可证明无引用"；无法证明者进 `needs_review`。保持 `dry_run=true` 零删除，旧字段名（`current/registered/bytes/reclaim_candidates` 等）保持兼容。
- `server.py` `creo_callback_status`：组装时传入 probe `readiness`（ready 时标记运行世代；unknown/not_loaded 如实记录，不据此单独清候选——文件级证据独立判定）。

## 验证

- 单元：`tests/unit/test_blend_callback_inventory.py` 9 项（健康候选/记录缺失/记录损坏/记录冲突保留涉及世代/deployment 缺失/新鲜 ready 文件为运行证据/probe ready 标记/payload 哈希不符/无引用 payload 候选），全过；全量 539 项与 `tools/dev_check.py` 通过（格式化后零回归）。
- 实机（本机 Windows / Creo 12.4.0.0 / E 盘 dev 服务 stdio 直连）：`creo_callback_status` 盘点 5 个 loader 世代、11 个 payload 世代——当前世代 `695fdd07…` current+双源注册+`recent_ready_file` 证据保留；4 个老世代（含派生键 `de87b145…-ef48706…`）判候选、`needs_review=[]`；payload 3 个候选、3 个缺 `callback_bootstrap.json` 判待复核（`bootstrap_missing`，不误入候选）、其余按 deployment 关联保留。`runtime_probe.readiness=not_loaded` 如实记录。会话状态 ready/connected=true 后查询，无模型/作业/保护触碰。
- 探测脚本 `build/dev027_inventory_probe.py`（本地生成物，不入库）。

## 未验证与边界

- `file_locked` 证据分支未在实机出现（查询时回调未加载属预期 not_loaded）；DLL 加载锁定语义依赖 Windows 行为，由单测外的代码路径保证，待真实 blend 会话时复核。
- 实际回收（删除）仍按卡另批实施；同源码二进制可复现性不变（另期）。
- 外部 Win10/Creo 10 环境的盘点输出复核随下次外部反馈闭环。
