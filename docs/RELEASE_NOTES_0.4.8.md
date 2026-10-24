# MCP_CREO_MechDog 0.4.8 版本说明

发布状态：已发布。2026-10-22 合入 main 并发布 GitHub Release（Release 420244170，Pre-release，非草稿），交付核对见 [RELEASE-0.4.8](validation/RELEASE-0.4.8.md)。本说明撰写于 2026-10-22 发布前，当时状态为开发分支未发布，以下历史日期与陈述保持原样。

日期：2026-10-22。本次为 0.4.6 反馈整合计划第一批（PATCH，无新增公开工具，工具数保持 90）。基于 0.4.7。

## 变更

- DEV-027 世代盘点口径补齐：`creo_callback_status` 的 `generation_inventory` 重写为 loader/payload 双维度盘点。引用按三态分类——本地注册引用（setup 与 registry 两来源分别记录）、运行证据（DLL 文件锁、新鲜 `callback_result.json`、probe ready 标记运行世代）、未知状态（`needs_review` 逐条原因）。`records_status`（build_stamp/setup/registry 各 ok/missing/corrupt）、`record_conflict` 与 `conflict_generations` 显式化。
- 回收候选判定收紧为"每个引用维度均可证明无引用"：本地记录缺失、损坏或冲突时保留相关世代并进入待复核清单，不再仅凭"非当前且未注册"判候选（回应外部反馈"已注册但记录丢失 → 误列回收"场景）。保持 `dry_run=true` 零删除；实际回收仍为另批实施的显式操作。
- payload 维度：`blend_callback/<sha>` 目录全量盘点，loader 世代经 `deployment.json` 关联 payload；登记缺失、损坏或哈希不符者判待复核，未被任何存活 loader 引用且记录确定时才判候选。
- 0.4.6 三份外部反馈原件逐字节归档（[feedback-0.4.6-2026-10-21](validation/feedback-0.4.6-2026-10-21/manifest.json)，SHA256 与章节条目映射）：FEAT-046 擦除外部实机主链路子项关闭、FEAT-043/044 `opened_session_model` 原环境观察子项关闭（`session_model_id` 524288+ 大数段保留观察）、DEV-027 dry-run 外部静态确认、DEV-045 附件命名 0.4.7 起按定名执行核对通过（0.4.6 第四种变体为历史，不回填）、BUG-077 原环境 0.4.6 时点死锁证据与复测脚本单列。

## 用法与兼容

`generation_inventory` 旧字段名（`current/registered/bytes/reclaim_candidates` 等）保持兼容，新增 `registered_by/runtime_evidence/referenced/needs_review/review_reasons/records_status/payload_generations/reclaim_candidates_payload/needs_review_payload/runtime_probe`。候选集比 0.4.7 更保守属预期行为：记录不健康或存在无法排除的引用时，候选可能为空并转入待复核。

## 验证与未测

见 [DEV-027 盘点验证记录](validation/DEV027-INVENTORY-2026-10-22.md)：单测 9 项、全量 539 项、`tools/dev_check.py` 通过；本机 Creo 12.4 实机盘点 5 个 loader 世代与 11 个 payload 世代输出符合设计。`file_locked` 运行证据分支未在实机出现（查询时回调 not_loaded 属预期），待真实 blend 会话复核。外部 Win10/Creo 10 环境的盘点复核、BUG-077 原环境迁移复测、BUG-078（恢复 accept 路径 `ProMdlnameBackup` 稳定 -1，登记待修）、485 条真实旧登记批量迁移继续开放，不随本版关闭。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1，待排期）不变：`accept_saved`/`accept_live` 实机不可用，三个 dirty 现场模型保护挂起待修复收尾。
- FEAT-045（装配只读检查）为下一批次，按 MINOR 规则独立交付，不在本版。
