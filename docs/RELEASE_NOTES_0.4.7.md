# MCP_CREO_MechDog 0.4.7 版本说明（开发分支，未发布）

日期：2026-10-21。用户明确指定本次为 0.4.7 PATCH；新增两个公开工具按项目规则本应递增 MINOR，本次作为用户指定的版本例外，不改变后续规则。基于 0.4.6，工具数 88→90。

## 变更

- BUG-077：模型登记控制信息与 aliases／inspection 详情分离；详情使用内容寻址 sidecar，旧内联记录继续兼容。新增 `creo_migrate_registry`，显式 inspect/apply，先备份原字节，再发布详情和原子控制记录；reconcile 预算拒绝增加结构化诊断。
- 迁移 apply 全程持有现有 Toolkit 通道锁，不发起 Toolkit 连接；忙即拒绝，不排队或自动重试。待运行作业、活动或无法证明停止的 owner 拒绝改写；停止已证明的保护记录只迁移存储形态，pending／unknown 状态保持。
- 迁移目标必须为合法的 32 位十六进制 model_id、直属模型目录，拒绝越界、绝对路径、符号链接及模型／作业身份错配。
- FEAT-047：新增只读 `creo_registry_health`，提供大小、预算占比、详情形态、迁移状态与 80% 预警。单条异常单列，不中断整份报告。
- health、迁移 inspect、apply 和幂等回放按实际序列化字节分页，整个响应不超过 32 KiB；默认 limit=20，上限 50。问题预览缩短时仍保留完整计数，完整条目通过 next_cursor 遍历。
- DEV-044／045：两份原报告证据补录；发布清单固定要求 Release body 写入两包文件名和完整 SHA256。

## 用法与兼容

`creo_migrate_registry(mode="inspect", targets=[model_id], limit=20)` 查看范围。apply 使用相同 targets 与一个新 idempotency_key；省略 targets 表示全注册表，因此应先确认范围。后续结果页沿用相同 mode／targets／key，并传上页 next_cursor；apply 游标只读取既有幂等结果，不重新迁移。inspect／health 游标绑定当时报告，登记变化后需省略 cursor 重新查询。

迁移不提高 16 MiB 控制记录预算，不删文件，不清保护，不将已保存模型套用 `abandon_new`。详情仍参与完整几何核验、后续编辑与保存重载。

## 验证与未测

本次验证与源码身份见 [BUG-077 审查补修记录](validation/BUG077-REGISTRY-SAFETY-0.4.7-2026-10-21.md)。本机 485 条真实旧记录不批量迁移；大条目和分页回归使用临时目录隔离夹具。原生主链路仍须满足 BUG-001 会话核对要求，未测部分如实保留。

当前仅更新开发分支源码版本，未合入 main、创建标签或发布 Release。DEV-027 二进制可复现性及目录安全回收继续开放，不将盘点 dry-run 当作回收实现完成。

2026-10-21 [WorkBuddy公开黑盒](validation/WORKBUDDY-0.4.7-2026-10-21.md)已覆盖正常新模型编辑、装配、保存重载、分页、空迁移幂等与拒绝保护；[后续单目标验收](validation/WORKBUDDY-0.4.7-NONEMPTY-2026-10-21.md)另覆盖真实小型旧内联迁移1条、创建job详情拆分1份、同键回放及迁移后直径16→20、revision1→2和保存重载。开发侧独立核对迁移备份与准备字节一致，其他529个模型登记不变。create_plate不返回受管model_id属于既有FEAT-028一次性产物边界。

2026-10-22 开发侧实机补齐并随版交付：

- [>16 MiB超限迁移实机链路](validation/BUG077-OVERSIZE-MIGRATION-2026-10-21.md)：17,393,662 B旧内联条目迁移（备份逐字节一致、控制记录1,634 B、31.6 MB sidecar哈希核验、语义与PRT不变、全表字节守恒）→迁移后不相关零件收养inspect/apply通过→该模型直径16→20编辑revision 1→2保存重载verified，请求以31,668,816 B的`aliases_ref`引用传递。
- [恢复链路](validation/BUG077-RECOVERY-2026-10-22.md)：四恢复动作×五种现场的可用性矩阵全实测；`restore_baseline`两种现场（现场=基线、live缺失）正向通过并验证dirty现场正确拒绝边界；`abandon_new`通过；悬挂场景构造方法沉淀（只杀Python runner，native执行器自然收尾，非Toolkit故障注入）。
- 图纸消费点：发现并修复拆分遗漏两处——`run_drawing`（native/drawing.cpp）的组件与模型详情引用内联化（创建/编辑/校验/回滚四路径）及`owned_file`的图纸`.drw`扩展名（reconciliation.py）。修复后图纸全链路实机通过：对拆分模型`creo_new_drawing`（源以引用消费）、编辑已有图纸（视图/投影/标注，revision 2→4，每步保存重载verified，`aliases_ref`随内容增长）、导出PDF。
- [health异常场景](validation/BUG077-HEALTH-2026-10-22.md)：预警（0.86倍预算条目正确归类并还原）、损坏条目（单条损坏不中断扫描、545条全量分页完整、结构化error）、32 KiB响应预算逐页实测（最大页19,895 B）、其他543条登记字节不变；超限场景见超限迁移记录。
- 发布回归：530项单测、`tools/dev_check.py`、SDK构建与`tools/test_general.py`原生套件（7/7）通过；test_general适配0.4.7作业结果摘要化结构（体积等断言改读`inspection_summary`与模型快照分节，`creo_create_plate`独立工具保持内联断言）。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1，待排期）：恢复accept路径`ProMdlnameBackup`稳定-1，`accept_saved`/`accept_live`实机不可用（实机0/4，该路径历史从未实机通过；场景与证据链齐全，保护语义正确保留）。同日普通编辑路径另有3次偶发`ProMdlnameBackup -1`，与成功样本操作同构，未定位根因。受影响恢复入口：dirty现场模型以`restore_baseline`不适用（现场≠基线）时保持保护挂起，待修复后收尾。
- 三个dirty现场测试模型（`de6f0bb5`/`bebe7e2b`/`57294ff8`）保护挂起，随BUG-078登记；485条真实历史旧登记未批量迁移。
- 原环境（外部Creo 10 / track_p01b 21.4MB条目）复测、Creo 9实机、DEV-027二进制可复现性与目录安全回收继续开放。
