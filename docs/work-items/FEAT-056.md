# FEAT-056：色板支持零件名键与 `random:true` 一键随机上色

日期：2026-11-02。类型：功能。优先级：P2。状态：已交付（随 0.11.3 发布，实机待验）。目标版本：0.11.3（已发布，公开工具仍 95）。关联 [FEAT-052](FEAT-052.md)（装配按零件族上色）、[BUG-104](BUG-104.md)（补基线）、[DEV-062](DEV-062.md)。

## 来源

- 原件：[0.11.0 反馈 F01 次要问题 1](../validation/feedback-0.11.0-2026-11-01/originals/2026-11-01_CREO_0.11.0_受管装配上色解锁链路三处断裂与装配失败恢复死路.md)。
- 现状：自动分族时族名即 `source_model_id`（32 位十六进制 UUID），随机上色需“dry_run 取 UUID → 本地生成调色板 → 执行”三步。

## 目标

让“按族随机上色”一次调用完成，同时不破坏既有的 UUID 键语义与可重放性。

## 范围

包含：

1. **零件名键**：自动分族模式下，`palette` 的键除 32 位小写十六进制 `source_model_id` 外，接受唯一零件名（`label`）。
   - 解析为对应族的唯一 `source_model_id`；同名多组件、`source_model_id` 冲突或标签命中多个族 → 拒绝并列出候选 `feature_id`/族名，不猜测。
   - 显式 `families` 模式语义不变（键仍必须是族名）。
2. **`random:true`**：
   - 与显式 `palette` 互斥；只与自动分族或显式族表组合使用。
   - 按族名稳定排序 + 黄金比例色相步进生成固定饱和度/明度颜色，同一输入重复调用得到同一调色板。
   - dry-run 与执行都回显 `palette_source: "explicit" | "family_label" | "random"` 与解析后的完整 `palette`，便于重放。
3. 计划操作 `recolor_assembly` 仍只接受显式 `palette`；`random` 只在公开工具提交前解析，避免计划重放不确定。
4. 工具描述、`README.md`、`capabilities.py` 同步。

不包含：

- 不新增公开工具；不做逐组件上色；不做色板持久化或主题库；不改 `families` 的成员引用语义（标签/ID 二选一规则不变）。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `tests/unit/test_recolor_palette_resolution.py` | 唯一标签键解析成功；同名多组件/源冲突报歧义并给候选；32 位十六进制键语义不变 |
| Windows / Python | 同上（random） | `random` 与 `palette` 同传 → 拒绝；同一族集合两次生成完全一致；族数/键集合完整覆盖；`palette_source` 正确 |
| Windows / Python | `tests/unit/test_assembly_appearance.py` | dry-run 与执行回显解析后的 palette；计划操作拒绝 `random` |
| Windows / Python | `tools/dev_check.py` | 无新增语言问题，全量单测通过 |
| 本机 Creo 12.4 / 匹配 SDK | 自动分族 + `random:true` 执行 | 各族颜色不同、写后读回与保存重载读回通过；**本轮未执行** |

## 实现与证据（2026-11-02，本地工作树，未提交）

| 项 | 内容 |
| --- | --- |
| 修改文件 | `src/creo_mechdog/appearance.py`（`checked_random`、`random_family_palette`、`_hsv_to_rgb`、`resolve_auto_palette`、`resolve_grouping(random=...)` 与 `palette_source`、preview 回显、submit 预解析并回显 manifest）、`src/creo_mechdog/schema.py`（自动分族键接受源 ID 或组件标签）、`server.py`（`random` 参数与描述）、`capabilities.py`、`README.md`、`tests/unit/test_recolor_palette_resolution.py` |
| 语义 | 自动分族下标签键解析为唯一 `source_model_id`；歧义（同一标签跨多个源族）拒绝并列出族；标签与源 ID 指向同一族重复拒绝；显式族表仍只接受族名键；`random` 与 `palette` 互斥；随机色按族名排序 + 黄金比例色相（固定饱和度/明度），同族集合结果稳定；作业里记录显式调色板，计划操作仍拒绝 `random` |
| 命令与结果 | 先红灯（10 项）→ 实现 → 绿灯；`unittest tests.unit.test_recolor_palette_resolution tests.unit.test_assembly_appearance` 49 项 OK；全量 2158 项 OK；`dev_check` `success=true` |
| 构建 | 同 [BUG-104](BUG-104.md)（执行器 `a61fad90…`，随 0.11.3 发布） |
| 未验证 | 随机上色在实机的写后读回与保存重载、80 组件夹具的族色区分；Creo 9/10、WorkBuddy 黑盒 |
