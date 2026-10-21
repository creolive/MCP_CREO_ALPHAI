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

2026-10-21 已收到[WorkBuddy公开黑盒结果](validation/WORKBUDDY-0.4.7-2026-10-21.md)：正常新模型编辑、装配、保存重载、分页、空迁移幂等与拒绝保护通过。真实旧格式/超限迁移、恢复apply/回滚及黑盒32KiB字节实测仍未完成；不以空迁移替代。create_plate不返回受管model_id属于既有FEAT-028一次性产物边界。本版仍未合入或发布。
