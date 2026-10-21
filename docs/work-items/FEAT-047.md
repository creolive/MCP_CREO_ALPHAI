# FEAT-047：只读注册表健康检查工具 creo_registry_health

类型：功能

优先级：P1

状态：验收中（2026-10-21 实现完成：单元 515 项与 dev_check 通过；实机调用与 WorkBuddy 开放）

目标版本：待定（新增公开工具，按项目规则使用 MINOR；版本归属由交付时确定）

来源与关联：[0.4.5/Creo 10 反馈](../validation/feedback-0.4.4-2026-10-21/report-registry-bloat.md) §5（P1："列出各条目 actual_bytes，预警接近 16 MiB 的条目——第二名 hull 3.4MB 已在路上"）；关联 BUG-077（拆分与迁移，共享迁移状态口径）。

## 问题或目标

注册表（`models/<id>/model.json` 及详情 sidecar）目前无任何整体可观察手段：条目接近 16 MiB 预算、已超限、损坏或仍为旧内联格式（未迁移）都只能在某个收养/恢复操作失败时逐个暴露。需要一个不连接 Toolkit 的只读工具，主动报告全量注册表健康状态。

## 范围

本次包含：

- 新增只读 MCP 工具 `creo_registry_health`（`server.py` 注册、`capabilities.py` 登记）：
  - 逐条目报告：model_id、model_name、status、revision、model.json 字节数与预算比、详情（aliases/inspection：引用/内联/缺失及字节数）、条目状态（ok / warning / over_budget / corrupt / legacy_inline）。
  - 汇总：条目总数、总字节数、预警清单（默认达到单文件预算 80%）、超限单列、损坏单列、迁移状态（需要迁移/已迁移）与迁移工具指引。
  - 单条目异常（读取失败、损坏、超限）不终止整份报告，该条目标记异常后继续。
  - 不连接 Toolkit、不修改任何文件。
- 能力说明文档与 README 同步。

不包含：任何修复/迁移动作（迁移工具属 BUG-077）；提高预算；读取详情 sidecar 全量内容（只报告身份与大小）。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | 单元测试（混合正常/预警/超限/损坏/旧内联条目） | 分类正确；单条损坏不中断整份报告；80% 阈值预警；超限单列 |
| Windows / Python | MCP 调用 `creo_registry_health`（无 Creo 会话） | 正常返回完整报告；不发起 Toolkit 连接 |
| 本机 Creo 12.4 | 常规注册表 | 与磁盘实际字节数一致 |

## 实现与证据

2026-10-21 实施于分支 `codex/bug077-registry-split`，与 [BUG-077](BUG-077.md) 同批（共用 `model_registry` 拆分语义与迁移口径）。

- `src/creo_mechdog/registry_ops.py::health`：逐条目 model_id/model_name/status/revision/model_json 字节数与预算比、详情三族形态（inline/reference/absent）、状态五分（ok / warning ≥80% / over_budget / corrupt / legacy_inline）；汇总计数 + 超限/预警/损坏单列；迁移段给出待迁移数量与 `creo_migrate_registry` 用法；单条目读取异常标记 corrupt 后继续；不写文件、不连接 Toolkit。
- `server.py` 注册 `creo_registry_health`（READ），`capabilities.py` 新增 `registry_maintenance` family（含 guarantees 与 limits）。
- 验证：`tests/unit/test_model_registry.py::Health`+`Pagination` 4 项（混合正常/预警/超限/损坏分类、单条损坏不中断整份报告、迁移后引用形态、分页遍历无重无漏）；516 项全量单测与 dev_check 通过，SDK 构建通过。
- **实机（MCP 黑盒，本机 dev 服务已重启加载本批代码）**：返回 526 条：ok 41 / legacy_inline 485 / 超限 0 / 损坏 0 / 预警 0，model.json 合计 12,705,876 B（最大 329,383 B，usage_ratio 0.0196），迁移段给出 485 条待迁移。首次实机调用暴露真实缺陷——无分页时响应 574,710 字节，远超项目 32 KiB 响应预算约定，随即加分页（limit 默认 20、上限 50；超限/预警/损坏清单各上限 50）并补单元回归。

未测：WorkBuddy 黑盒。
