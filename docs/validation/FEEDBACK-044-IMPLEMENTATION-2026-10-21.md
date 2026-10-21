# 0.4.4/0.4.5 反馈整合实施记录（开发分支）

日期：2026-10-21。实施分支：`codex/bug077-registry-split`（自 main `e3a7480`）。实施依据：[0.4.4 反馈整合计划](../development/0.4.4-FEEDBACK-PLAN-2026-10-21.md)（覆盖 v0.4.4 构建验收与 v0.4.5 运行反馈两份原件，[归档](../validation/feedback-0.4.4-2026-10-21/manifest.json) 含 SHA256）。

版本保持 0.4.6（开发分支不发布；本批含两个新增公开工具，按项目规则应为 MINOR，版本归属待用户决定）。

## 证据补录（DEV-044 第二节）

- DEV-027：外部 Win10/Creo 10 通过证据补录（json.hpp 换行翻转场景下 `protk.dat`、loader/payload DLL 字节与世代目录数全部稳定，旧格式缓存 `generation_key` 保留），指纹稳定化与旧缓存迁移子项关闭；二进制可复现性与目录安全回收继续开放。
- DEV-030：外部七键 `vcvars64_env` 复测通过（`RC=0`，多余键忽略提示只列键名），子项闭环。
- BUG-076：原环境根因证据取得（`metadata_kind=model_registry`、`models/c437cace…/model.json` 21,472,751 B、`failed_stage=origin_conflict_scan`）——"尚未取得文件类别和字节数"的开放项闭环，阻断修复移交 BUG-077。

## 第一阶段：BUG-077 注册表膨胀治理与 reconcile 死锁解除

### 膨胀来源核对（本机 526 条登记）

迁移前实测分布：最大条目 329,383 B（`inspection` 128,704 + `aliases` 34,754，单别名 `sk_big` 含数千 `entity_ids` 映射）；第 2/3 名 197KB/172KB 为 `inspection` 与 `last_live_inspection` 各约 37KB。确认报告推断成立：成功编辑路径把完整 aliases/inspection 内联写入 model.json。报告提到的"同名模型 revision 16、8.4MB→21.4MB"与 `hull` 3.4MB 属原环境观察，本机最大条目仅 0.33MB，未复现超限规模（超限需长时间多轮阵列/变换累积）。

### 实现

- `src/creo_mechdog/model_registry.py`（新）：统一注册表持久化。`write_model` 详情先写入 `models/<id>/details/` 内容寻址 sidecar、控制记录后原子发布；`read_control` 预算+链接+类型校验，超限抛结构化 `RegistryBudgetExceeded`；`aliases_of`/`inspection_of` 按需解析且兼容旧内联；`detail_digests`/`semantic_view` 提供与形态无关的语义比较（内部 payload 按 sidecar 序列化方式计算摘要，因此 inline 与 ref 内容同摘要）。
- `src/creo_mechdog/registry_ops.py`（新）：`health`（只读五态报告 + 分页）与 `migrate`（inspect/apply + 幂等键 + 目标集指纹；逐条目先备份原始字节 → 详情先持久化 → 控制记录原子发布；job 证据链的 `job.json` 结果与 `request.json` 模型/组件详情同法拆分；`models/registry-migration.jsonl` 追加日志；apply 结果按键持久化可重放）。
- `reconciliation.py`：`RecoveryMetadataBudgetExceeded`（RECOVERY_METADATA_BUDGET_EXCEEDED + metadata_kind/路径/字节/预算/阶段/job/model/recovery）；native 原文件超限时由拆分后的 job result 供给 candidate（原始 native 文件保持原样不覆盖）；candidate 携带 `aliases_ref`；`_check_execution` 改语义比较；`_native_request` 与 accept_saved 引用优先。
- `adoption.py`：冲突扫描控制记录化——超限抛既有 ADOPTION_METADATA_BUDGET_EXCEEDED，损坏抛 `registry_entry_unreadable` 拒绝（不静默跳过）；六个登记写入点经 `write_model`。
- `generic_bridge.py`：`model_info` 经 `read_control`；`list_models` 单条异常占位继续；别名检查用 `aliases_of`；请求视图引用优先且 legacy 内联保持（`aliases` 始终以对象到达 native）；成功收尾以结果引用替换详情键并清陈旧内联；`split_job_result` 防 job.json 反复内联。
- `model_queries.py`/`server.py`/`bridge.py`：aliases 章节与组件列表按需解析；compact 透传 `aliases_ref`。
- native `generic.cpp`：`aliases_ref`/`inspection_ref` 解析 5 处（模型加载、组件源内联化、主模型 verify_saved、回滚路径），旧内联请求兼容；前置声明解决 unity build 顺序。

### 验证

- 单元：516 项通过（新增 `tests/unit/test_model_registry.py` 14 项：控制记录 <64 KiB、内容寻址幂等、语义视图形态无关、篡改引用拒绝、超限条目结构化六要素、冲突扫描损坏拒绝与拆分后仍检出冲突、inspect 无副作用、apply 拆分+备份+日志、幂等与键冲突、损坏条目拒绝、健康五态分类、单条异常不中断、分页遍历无重无漏）。
- `tools/dev_check.py`：success=true，无新增语言问题。
- `bridge.py build`：SDK 编译通过。
- **实机（MCP 黑盒，E 盘 dev 服务，已重启加载本批代码）**：`creo_registry_health` 返回本机 526 条：ok 41 / legacy_inline 485 / 超限 0 / 损坏 0，总 12,705,876 B；迁移段给出 485 条待迁移。**首次实机调用暴露真实缺陷**：无分页时响应 574,710 字节（远超项目 32 KiB 响应预算约定），随即加分页（limit 默认 20 / next_cursor；超限·预警·损坏清单各上限 50）并补单元回归。
- 迁移 apply 未在本机真实注册表执行（会改写 485 条历史记录，属用户数据变更），保持人工确认后执行。

## 第二阶段：会话与公开行为

- FEAT-043/044 `opened_session_model` 核对（源码三场景）：显示成功后必生成；同名已驻留在预检以 `SESSION_NAME_CONFLICT` 拒绝（反馈方延续多轮验收的会话最可能命中该路径）；显示失败只返回 `displayed=false`+`display_message`。**字段缺失不等于实现缺陷**，未发现成功打开却缺字段的路径，不改代码；原环境按三类结果分别复测。
- FEAT-047 `creo_registry_health` 已实现（工具数 88→90，三处数量断言同步）；FEAT-046 擦除工具已随 0.4.6 交付，实机矩阵按卡开放。

## 第三阶段：DEV-045 与 DEV-027 余项

- DEV-045：RELEASING 发布门槛新增第 7 项（Release body 必列两包文件名+完整 SHA256 并核对远端附件），记录模板同步；旧 Release 不回填。
- DEV-027：二进制可复现性与世代目录安全回收未实施（本轮无变化，盘点 dry-run 仍为唯一观测手段）。

## 未测与开放

- 实机 >16 MiB 历史夹具的完整链路（本机无超限条目，需构造）：迁移 → 不相关零件收养 inspect → 该模型编辑 → revision 推进与保存重载。
- 本机 485 条 legacy_inline 的迁移 apply 执行（需用户确认后进行）。
- 原环境（Creo 10 track_p01b 21.4MB）与 WorkBuddy 黑盒复核。
- 建模主链路回归（普通编辑、装配、图纸、恢复动作）待会话可操作核对后执行——本轮全部改动集中在注册表存储层，native 引用化涉及 5 处消费点，需要一次真实建模回归确认。

## 环境与命令

本机 Windows x64 / Python 3.12 / Creo 12.4 SDK / MSVC；工具数 90；`.venv\Scripts\python.exe -m unittest discover -s tests`、`tools\dev_check.py`、`bridge.py build` 均过；源码指纹与 dirty 状态见 `build/development_check.json`。