# MCP_CREO_MechDog 0.4.7 公开 MCP 黑盒验收报告

执行方式：仅调用已连接的 `MCP_CREO_MechDog_dev` 公开工具，全部为实际执行（非建议）。未读取源码、仓库、Git、配置、日志或本机目录，未执行任何本地命令/脚本。操作者已确认“界面正常响应、无阻塞对话框、无正在执行的任务”后才开始原生调用。

## 1. 环境与前置条件

| 项 | 实测值 |
|---|---|
| 服务名/版本 | `MCP_CREO_MechDog` / `server_version=0.4.7`（`creo_session_status` 与 capabilities 一致） |
| 工具数 | `tool_count=90`，`enabled_tool_count=90`，`unavailable_tools=[]` |
| 发布状态 | `release_status=pre-release candidate` |
| 更新检查 | `up_to_date`：当前 0.4.7 高于最高公开版 0.4.6（`is_prerelease=true`） |
| Creo | 12.4.0.0（`release_numeric=44`）；`ready_to_build=true`；`transport=stdio` |
| 部署身份 | `code_root=E:\Projects\MCP_CREO_MechDog`，`server_entry=server.py`，`.venv` 解释器；`source_changed_since_startup=false`，50 个源码指纹随启动快照公开 |
| 源码提交/构建号 | **无法确认**（公开接口未提供） |
| 会话 | `connected=true`，`toolkit_code=0`，`current_model=MECHDOG_MULTI5_REFERENCE`，`session_fingerprint=12830465268385011701` |
| 进程快照 | `xtop.exe`(21144) 可见窗口正常；`parametric.exe`(16296) 仅隐藏窗口且 `hung_window_observed=true`（观察记录，非本服务判定） |
| 参数核对 | `creo_registry_health` 公开 limit(1-50)/cursor；`creo_migrate_registry` 公开 mode/targets/idempotency_key/limit/cursor，与要求一致 |

## 2. 用例表

| # | 用例 | 结果 | 关键证据 | 限制 |
|---|---|---|---|---|
| 1 | 版本 0.4.7 / 90 工具 | 通过 | capabilities 两字段一致 | — |
| 2 | 两个注册表工具在新清单中 | 通过 | tools 清单 #12/#13，schema 含新参数 | — |
| 3 | 会话状态 | 通过 | connected=true，9s 探针 0 错误 | 未执行 retry |
| 4 | 健康检查全量分页 | 通过 | 11 页 526 条，无重复无遗漏，无页错误 | — |
| 5 | 迁移预检全量分页 | 通过 | 10 页 485 条，计数恒为 485 | 全局范围禁止 apply，未做 |
| 6 | 三个非法 targets | 通过（均拒绝） | 三条均 `Invalid model_id` | — |
| 7 | 32 KiB 响应预算实测 | **未验证** | 仅见 `response_budget_bytes=32768` 声明 | 客户端不提供原始字节数，未用脚本测算 |
| 8 | 模型A 圆盘 Ø16×10 | 通过 | 2010.6192982974674 mm³，Δ=3e-7 | — |
| 9 | 别名改 Ø20 | 通过 | 3141.5926535897925 mm³，rev1→2 | — |
| 10 | inspect compact/aliases | 通过 | 2 条别名，单页 complete | — |
| 11 | 限定目标迁移 inspect | 通过（0 条） | `entries_needing_migration=0` | 新模型已拆分存储 |
| 12 | apply + 同 key 回放 | 通过（空迁移） | `migrated=0`；回放 `replayed=true`，`completed_at` 不变 | 不等于旧格式迁移通过 |
| 13 | 迁移后 A 不变 | 通过 | rev2/ready/3141.5926535897925/sha 不变 | — |
| 14 | 直径改 18 | 通过 | 2544.690049407732 mm³，rev3 | — |
| 15 | 模型B 10×10×10 | 部分失败→改道通过 | `creo_create_plate` 成功但**无 model_id**；改用 new_part+plan 得 999.9999999999999 mm³ | 见第5节首次异常 |
| 16 | 装配 C + 两固定组件 | 通过 | rev3，3544.6900494077317 mm³，2 组件，transform [0,0,0]/[50,0,0] | 约束类型仅返回数字 13 |
| 17 | 过期 revision 拒绝 | 通过 | `Stale revision: current model revision is 3`，未产生作业，A 不变 | — |
| 18 | reconcile inspect | 通过（未 apply） | restore_baseline 资格=true，其余三项 false | live=false，故 live 证据类动作不可用 |
| 19 | 复用 key 换目标集 | 通过（拒绝） | `This idempotency_key was used for a different target set; use a new key`，B 不变 | — |
| 20 | 真实并发争用 | 通过（准入拒绝） | apply 返回 `toolkit_busy`/`accepted=false`，同批 regenerate 被受理 | `owner_determined=false`，阻塞者未定 |

## 3. 调用序列（关键字段）

1. `creo_session_status{}` → connected，Creo 12.4.0.0。
2. `creo_execute_plan{model_name:"wb047_disk_a1", operations:[sketch disk_profile(XY, circle disk c=[0,0] r=8, dimension diameter refs[disk] value16 pos[12,0]), extrude disk_solid sketch=disk_profile depth=10], assertions{require_solid:true}}` → `job 250f314808f7496bb869f0d280cee613`，model `2d60e6bff35b4383971ddbd7bc22ee51`；succeeded，rev 1，`volume_mm3=2010.6192982974674`，`saved_file_reloaded_and_verified=true`，sha `20e6cb8d…`。
3. `creo_set_sketch_dimensions{model_id:A, expected_revision:1, sketch:"disk_profile", values:{diameter:20}}` → `job 0a29a21ab85a4a5c99a4872696adbd71`；succeeded rev 2，`3141.5926535897925`，verified=true。
4. `creo_inspect_model{detail:compact}` → ready/rev2/`3141.5926535897925`；`{detail:full, section:"aliases"}` → `disk_profile`(feature_id 40, `dimension_ids.diameter=2`, `entity_ids.disk=5`) + `disk_solid`(feature_id 47)，`returned_count=2, complete=true, next_cursor=null`。
5. `creo_migrate_registry{mode:"inspect", targets:[A], limit:20}` → `entries_needing_migration=0, entries=[], has_more=false`。
6. `…{mode:"apply", targets:[A], idempotency_key:"wb047a1mig1", limit:20}` → `migrated=0, job_files_split=0, already_migrated=0, refused=0, actions=[], replayed=false, completed_at=2026-10-21T13:07:29.480192+00:00`，**无 job_id**（未虚构作业）。
7. 同 key、同 targets 重放 → `replayed=true, fingerprint=0183fb03c9638f68`，`completed_at` 与首次完全相同，`migrated=0`。
8. `creo_set_sketch_dimensions{expected_revision:2, values:{diameter:18}}` → `job 36dde2487d6545659a5af002f58fb7c4`；rev 3，`2544.690049407732`，verified=true。
9. `creo_create_plate{10,10,10, model_name:"wb047_box_b1"}` → `job 26f19ef9a2cf49f795ded51660e132ff` succeeded，`volume_mm3=1000`，verified=true，**返回体无 model_id**；`creo_list_models{limit:50}` 首页以 A 开头（按 updated_at 降序）未含该模型。
10. `creo_new_part{model_name:"wb047_box_b1m"}` → `job 77b10d8e…`，model `be5d97aaf0964239acd99ca35b9cc14b`，rev 1 无实体。
11. `creo_execute_plan{model_id:B, expected_revision:1, operations:[sketch box_profile 4 条首尾相连直线(±5), extrude box_solid depth10]}` → `job 277bf7f465124759a58de00fd6a77000`，rev 2，`999.9999999999999`，verified=true。
12. `creo_new_assembly{model_name:"wb047_asm_c1"}` → `job 8a412d0e…`，model `13dd8f4b3b18446f8ef62e9d62df97b7`，rev 1。
13. `creo_assemble_component{C, expected_revision:1, label:"comp_a", source:A, placement:"fixed", translation:[0,0,0]}` → `job 8641e3fff51849e69372617dbfc22bc9`，rev 2，1 组件，`2544.6900494077317`。
14. `…{expected_revision:2, label:"comp_b", source:B, translation:[50,0,0]}` → `job 1379f73f65b1425797d57d2b0b8406cd`，rev 3，2 组件，`3544.6900494077317`，verified=true。
15. `creo_inspect_model{C, section:"components"}` → feature_id 40/43，transform 平移 0 与 50，`underconstrained=false`，`constraints:[{type:13}]`，内部名 `▩C_8641E3FFF51849E60001`/`▩C_1379F73F65B142570001`；`section:"aliases"` → comp_a(source A, source_revision 3, fixed)、comp_b(source B, source_revision 2, fixed)，`source_snapshot=true`。
16. `creo_execute_plan{model_id:A, expected_revision:2, operations:[{op:"regenerate"}]}` → 拒绝：`Stale revision: current model revision is 3`；随后 inspect 确认 A 仍 rev3/`2544.690049407732`。
17. `creo_reconcile_model{A, mode:"inspect", live:false}` → `recovery_pending=null`，baseline `verified=true` 且与 candidate sha 一致，owners `stopped=true`；`restore_baseline.available=true`("Explicit apply with matching evidence and idempotency key required")，`accept_saved/accept_live/abandon_new=false`("Required baseline/candidate/owned healthy live evidence is unavailable")，`evidence_token` 600s，`automatic_replay_allowed=false`。未执行任何 apply。
18. `creo_migrate_registry{mode:"apply", targets:[B], idempotency_key:"wb047a1mig1"}` → 拒绝：`This idempotency_key was used for a different target set; use a new key`；B 仍 rev2/1000。
19. 并发（同一批发出）：`execute_plan{A, expected_revision:3, [regenerate]}` 于 `13:10:32.076415` 受理 `job 37210eda1ec64384b2d0b639596b42da` → 13:10:39.32 succeeded rev 4，体积仍 `2544.690049407732`；同批 `migrate apply{targets:[B], idempotency_key:"wb047conc1"}` 返回 busy（未重提）。

## 4. 原始返回摘录

- 健康分页：11 页（50×10+26），`entry_offset` 0→500，前 10 页 `has_more=true`，末页 `next_cursor=null`；`entry_count=526`，唯一 model_id 526，无重复无遗漏；`summary{ok:41, warning:0, legacy_inline:485, over_budget:0, corrupt:0}`，`total_model_json_bytes=12705876 / 16777216`，三个预览块 `count=0, complete=true`；11 次调用 `generated_at` 12:52:01→12:52:59、cursor 内 snapshot 哈希恒定（期间登记未变）。
- 迁移预检：10 页（50×9+35）=485，`entries_needing_migration=485` 每页恒定，唯一 485 无重复；条目字段 `model_id/model_json_bytes/inline_details/job_chain`，`job_chain` 为平坦 32 位十六进制字符串数组（长度 1–16）；顶层无 `job_id`；末页 `has_more=false`。
- 非法目标（原文）：`../`、`C:\`、`not_a_model_id` 三次均 `Error executing tool creo_migrate_registry: Invalid model_id`。
- 迁移回放：首次 `{"migrated":0,…,"replayed":false,"completed_at":"2026-10-21T13:07:29.480192+00:00"}`；回放 `{"migrated":0,…,"fingerprint":"0183fb03c9638f68","replayed":true,"completed_at":"同值"}`。
- busy（原文）：`{"status":"busy","code":"toolkit_busy","accepted":false,"blocking_job_id":null,"blocking_model_id":null,"blocking_operation":null,"owner_snapshot":null,"owner_determined":false,"retry_after_seconds":1,"retry_guidance":"No occupying job could be determined; the owner may be a session probe, build or another client. This request was not accepted. Retry this request after 1 second only when the occupying operation has finished; re-read the model revision before writing. Do not resubmit an already accepted job.","message":"Creo Toolkit is busy with another operation"}`。未按指引重试。

## 5. 首次异常与停止位置

- 唯一异常：`creo_create_plate` 在第 9 步成功建模（1000 mm³、保存重载验证通过），但**提交与结果均不含 model_id**，且 `creo_list_models` 首页（按 updated_at 降序、首位为本轮 A）未见它，PRT 落在 `jobs/<job_id>/output/`。因此它不能作为装配源（`source_model_id` 需 32 位 id）也不能作为迁移 targets——此为公开接口可用性问题，建议登记。处理方式：B 改用 `creo_new_part` + `creo_execute_plan` 重新达成 10×10×10（1000 mm³），未修改、未删除已生成的 `wb047_box_b1` 文件。
- 除上述一处，无失败用例；无 unknown_outcome、无连接超时、未触发保护清理或 Creo 重启。

## 6. 本轮创建对象（全部保留，未清理）

| 类型 | 名称 | model_id | 终态 |
|---|---|---|---|
| 圆盘 A | wb047_disk_a1 | 2d60e6bff35b4383971ddbd7bc22ee51 | ready, rev 4, 2544.690049407732 mm³ |
| 方块 B | wb047_box_b1m | be5d97aaf0964239acd99ca35b9cc14b | ready, rev 2, 999.9999999999999 mm³ |
| 装配 C | wb047_asm_c1 | 13dd8f4b3b18446f8ef62e9d62df97b7 | ready, rev 3, 2 组件, 3544.6900494077317 mm³ |
| 未托管 PRT | wb047_box_b1 | 无（仅文件） | `jobs/26f19ef9…/output/wb047_box_b1.prt.2` |

作业：`250f3148…`、`0a29a21a…`、`36dde248…`、`26f19ef9…`、`77b10d8e…`、`277bf7f4…`、`8a412d0e…`、`8641e3ff…`、`1379f73f…`、`37210eda…`（完整 ID 见第 3 节）。

## 7. 结论边界（必须分开读）

- **正常新模型链路通过**：建模、别名草稿修改、保存重载验证、装配、过期 revision 拒绝、reconcile inspect、幂等 key 冲突拒绝、busy 准入拒绝。
- **空迁移通过**：只有“限定目标调用 + 空迁移幂等回放”成立；`entries_needing_migration=0` 属新模型拆分存储的合理结果。
- **真实旧格式/超限迁移未验证**：485 条历史 legacy_inline 未迁移（按指令不处理，且全局 apply 禁止）；备份字节一致性、>16 MiB 登记、掉电/中断续作、内部文件锁机制均未验证。本次未制造 unknown，因此四种恢复 apply 与真实回滚链路不能宣称通过。32 KiB 预算因无法取得原始响应字节数记为未验证。