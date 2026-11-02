# MCP_CREO_MechDog 0.11.3 版本说明

- 类型：PATCH（公开工具仍 **95 个**，无新增工具、无破坏性接口变更）。
- 批次：2026-11-02 第十一轮反馈（R11），[DEV-062](work-items/DEV-062.md)；来源为 `C:\Users\Administrator\Downloads\0.11.0` 三份 v0.11.0 验收原件。
- 服务与源码版本以 [version.py](../version.py) 为准；本版种子包为 `MCP_CREO_MechDog-0.11.3-seed-library.zip`。

## 本版内容

### 1. 0.11.0 反馈归档与逐章对账（DEV-062）

三份原件逐字节归档到 `docs/validation/feedback-0.11.0-2026-11-01/`（3/3 长度、SHA256 与源文件一致），附 `manifest.json` 与 [逐章映射](validation/feedback-0.11.0-2026-11-01/MAPPING.md)：每章对应固定 ID、已闭环依据与缺件。新登记 [BUG-104](work-items/BUG-104.md)、[BUG-105](work-items/BUG-105.md)、[BUG-106](work-items/BUG-106.md)、[FEAT-056](work-items/FEAT-056.md)、[DEV-063](work-items/DEV-063.md)，并补 FEAT-052/BUG-101/BUG-102/BUG-088/BUG-089/DEV-061 增量。已闭环项（BUG-089 主闸门、DEV-061 仓库级断言、BUG-090 编译证据、FEAT-035 `depth_basis`、0.10.1 三键枚举、draft 双 flip、`weldability` 风险标记、BUG-096 回滚字段）只记依据、不重复派工。

### 2. 旧检查点补基线（BUG-104）

0.10.x 建的受管装配检查点没有组件 `appearance` 字段，此前只能先 `creo_save_model` 再上色。`creo_recolor_assembly` 新增显式参数 `refresh_baseline`（默认 `false`）：

- `false`：与旧版一致，缺 `appearance` 的检查点拒绝写入，拒绝信息同时给出两条路径（先 save，或带 `refresh_baseline=true` 重提）。
- `true`：原生在装配加载准入阶段发现检查点组件缺少外观时，以**当次作业前的实读外观**填充回滚基线，随后仍是“上色 → 保存 → 双次读回”一条作业、一次 revision 递增；回执新增 `baseline_source`（`checkpoint` / `adopted_live`）。
- 只放宽“缺 `appearance`”这一项：缺 `feature_id`、绑定冲突、源 ID 不一致等身份缺口仍拒绝。
- `dry_run` 仍只读注册表，缺基线时回执直接返回 `next_action`（含可直接照抄的调用参数）。

`execute_plan` 的 `recolor_assembly` 操作同样接受该字段，与工具共用一条准入校验。

### 3. 零变更失败不再进入不可恢复状态（BUG-105）

- 原生执行器在**没有任何操作被派发**的失败（连接、加载、查表等阶段）上统一发布 `model_unchanged=true`，不再限定 `callback_preflight`；Python 侧只据此保持模型 `ready`，有派发证据或回滚失败仍置 `failed`。
- `creo_reconcile_model` 新增动作 `ack_no_mutation`，用于处理旧作业或证据不足、模型已被置为 `failed` 的现场：必须传 `confirm_zero_mutation=true`，并沿用既有 `evidence_token`、`expected_revision`、`idempotency_key`。它只满足以下全部条件时可用：`status=failed`、无 `pending_job`/`recovery_pending`、检查点身份仍与记录一致、失败作业的回滚未失败。
- 该动作是**纯注册表事务**：不启动 worker、不连接 Toolkit、不写模型文件、revision 不变，写入 `reconciliation` 审计块（`prior_status`、`original_job_id`、`checkpoint_identity`、`acknowledged_at`）并清除恢复保护，替代手工编辑 `model.json`。
- 装配与工程图也可使用（原生四动作仍只支持零件/钣金），因为该动作不触碰组件归属。

### 4. 上色取色更直接（FEAT-056）

- 自动分族时，`palette` 的键除 32 位 `source_model_id` 外，还可直接写**唯一的组件标签**；标签只对应一个源族时自动解析，跨族或歧义则拒绝并列出冲突族，不猜测。
- 同一族被标签键与源 ID 键重复覆盖时拒绝，不会静默覆盖其中一种颜色。
- 新增 `random`：按族名排序 + 黄金比例色相生成一套确定性颜色，与 `palette` 互斥；`dry_run` 与执行都回显 `palette_source`（`explicit` / `family_label` / `random`）与解析后的 `palette`。
- 作业里记录的始终是**显式调色板**，重放不依赖随机生成器；`execute_plan` 的 `recolor_assembly` 仍只接受显式调色板。
- 显式族表模式语义不变：键必须是族名。

### 5. 台账与发布口径

- `RELEASING.md` 第 8 步把“本版新增能力对应的 FEAT 卡首页状态”列为逐 ID 核对项，避免能力已发布而工作卡仍写开发中。
- 修正 0.11.2 回填遗留的 `BUG-102`/`DEV-061` 首屏状态与台账行不一致、`BUG-089` 卡头滞后，以及 `docs/DEVELOPMENT.md` 曾停留在 0.11.1 的版本行；分类统计按实际行状态重算（155→161 行）。
- [BUG-101](work-items/BUG-101.md)/[BUG-102](work-items/BUG-102.md)/[BUG-088](work-items/BUG-088.md) 补记 0.11.0 回归现场与剩余判据，不宣称通过。

## 升级注意

- 本版种子包为 0.11.3（`docs/seed_manifest.json` 的 `compatible_server_version` 同步为 `0.11.3`）；旧种子包安装到本版会被版本闸门拒绝，请改用下方附件。
- `refresh_baseline` 默认关闭，行为与 0.11.2 一致；只在确认“检查点缺外观基线”时才开启，开启后本次作业的回滚基线是作业前的实读外观。
- `ack_no_mutation` 只处理“失败但没有改动模型”的现场；有派发或回滚失败的作业仍须走 `restore_baseline`/`accept_saved`/`accept_live`/`abandon_new`。
- `random` 生成的调色板会写入作业请求，可原样重放；如需固定配色，请先 `dry_run` 取回 `palette` 再显式提交。

## 验收与未验证范围

- 本机（Windows x64 / Python 3.12）：全量单元测试 **2158 项 0 失败**（本批新增 27 项），`tools/dev_check.py --work-item 0.11.0-feedback-r11` `success=true`，`bridge.py build` exit 0（Creo 12.4.0.0 匹配 SDK），样式无回归。
- **未执行实机验收**：`refresh_baseline` 的实读填基线与 `baseline_source=adopted_live` 回执、随机上色的写后读回与保存重载、connect 阶段零变更失败后 `ack_no_mutation` 恢复，均只完成离线实现与单元测试；Creo 9/10 实机与 WorkBuddy 黑盒同样未执行，不因本机检查通过外推为其他环境通过。
- 反馈方 Creo 10 的 `-1` 拉伸、draft `flip=true` 方向失败与元素树 A/B、空件预览现场，本机 Creo 12.4 不可复现或不可判定，本版只登记判据，结论不变。

详细验收摘要、环境与附件校验见[发布记录](validation/RELEASE-0.11.3.md)。
