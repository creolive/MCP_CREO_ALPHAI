我会按照你规定的顺序，只通过已连接的 `MCP_CREO_MechDog_dev` 公开工具逐步执行，并在每一步与预期值核对；任何不符立即停止。

先加载需要调用的工具定义。
第 1 步：确认服务版本与部署。
0.4.7 已确认，部署根目录与注册文件均在 E 盘 dev 仓库。继续第 2 步读取模型快照。
快照一致。现在用 full 详读 aliases 与尺寸部分，核对别名与直径。
第 3 步：迁移前非空确认（只读 inspect）。
条目与预期完全一致（非空、单条、内联 aliases+inspection、作业链含创建作业）。第 4 步：执行一次 apply。
第 5 步：几何编辑前用完全相同的输入立即重放。
重放确认幂等。现在复查迁移后状态（单目标 inspect + 模型 inspect）。
迁移链路已完成且模型未被触碰（ready / revision=1 / 体积与 PRT SHA256 均未变 / 条目待迁移数归零）。在进入原生编辑前，需要你作为操作者确认现场界面状态。
已获得确认。第 6 步：检查启动状态与会话连接。
会话已连通，Creo 12.4.0.0。编辑前再读一次最新 revision。
revision 仍为 1，pending_job 为空。提交唯一一次尺寸修改。
任务已受理（job `bc100ebc75aa4c1bbebaf1ced97c2d6b`）。轮询该任务至终态。
任务成功，revision 2，保存重载校验通过。第 8 步：复核模型快照与别名。
补齐 job full 证据字段。
全部 8 步按序执行完成，无停止条件被触发，无重试、无重复提交、未删除模型、未清保护、未回滚。

## 1. 环境与服务版本

| 项目 | 实际值 |
|---|---|
| 工具 | `creo_capabilities(detail="compact")` |
| 服务版本 | `version` / `server_version` = **0.4.7**（符合），tool_count 90 / enabled 90，unavailable_tools 空 |
| 部署位置 | `resource_root`、`registry_file` = `E:\Projects\MCP_CREO_MechDog\...` → **E 盘 dev 部署符合** |
| 更新检查 | up_to_date（latest 公开版 0.4.6，当前为预发布） |
| 源码提交 / 构建号 | **无法确认**（公开接口未提供） |

## 2. 迁移前基线（`creo_inspect_model` compact + full/aliases + full/sketch_dimensions）

- model_id `7efb4e2646464e44a5fc8a86b89c0ee9`，`wb047_legacy_prep_1021a`，part
- status **ready**，revision **1**，pending_job **null**，last_job `9065e89d354448adb765f69bedaf5e6b`
- volume **2010.6192982974674 mm³**（与初始值 0 偏差），units mm，healthy/has_solid=true，counts 8/4/6/1
- part_sha256 **759295a5b0f5868cfcd2bf9d959e89413cfb6e6bfc9917697c0ffe5bfcdc52db**（公开字段提供，与初始值一致）
- 别名可见：`disk_profile`（dimension_ids.diameter=2、entity_ids.disk=5、feature_id 40）、`disk_solid`（feature_id 47）；sketch_dimensions：id=2 value **16.0**

## 3. 非空确认（`creo_migrate_registry` mode=inspect）

输入 `targets=["7efb4e2646464e44a5fc8a86b89c0ee9"]`, limit=20 → **entries_needing_migration=1**，唯一 entry 即目标 ID，`inline_details=["aliases","inspection"]`，`job_chain=["9065e89d354448adb765f69bedaf5e6b"]`，model_json_bytes 12996，has_more=false。符合预期，未做空迁移。

## 4+5. 首次 apply 与同键重放

**首次**（`mode=apply`, 同 targets, `idempotency_key=wb047_real_mig_7efb4e26_01`, limit=20）：

- migrated **1** / job_files_split **1** / refused **0** / replayed **false**
- completed_at **2026-10-21T14:04:02.009319+00:00**，has_more=false
- 动作：
  1. `9065e89d…5e6b` → `job_file_split`，`job.json` → `job.json.pre-split-bak`，backup_sha256 `b4fd5b744d4f97c84ea9dbc89ded8c299e5a3b0129e6e965de55c4136ace9099`
  2. `7efb4e26…0ee9` → `migrated`，`model.json.pre-split-bak`，backup_sha256 `dd40b15c9d4d7ed3c75b7587a5b816c33950d528a632a7471cfa703b23fdc858`，control_sha256 `bf0045390b8f7a1e77d2e7675bb98fccd584a98cec54d3f0730ed8327fca1c03`

**重放**（完全相同的 apply 输入，几何编辑之前）：**replayed=true**，migrated=1 / job_files_split=1 / refused=0，completed_at 与两条 backup/control SHA256 **完全相同**，另返回 fingerprint `1d27d06387b7c8d5`。

迁移后复查：inspect `entries_needing_migration=0`；模型 **ready / revision 1 / pending_job null / 2010.6192982974674 mm³ / part_sha256 759295a5…52db 未变**，updated_at 保持 13:38:23.977611，别名与 diameter=16 仍可见。

> 说明：`backup_sha256` 仅为公开返回值，**不能据此声称备份原始字节已逐字节核验**。

## 6. 会话前置

操作者已确认 Creo 界面正常响应、无阻塞对话框、无运行任务。

- `creo_startup_status(retry=false)`：state=ready、connected=true（snapshot stale=true，verification_age 1721.7 s，updated_at 14:03:27.9）
- `creo_session_status`：**connected=true**，toolkit_code 0，fresh（age 0 s，stale=false）；当前模型 WB047_LEGACY_PREP_1021A
- Creo 版本 **12.4.0.0**（release_numeric 44，`C:\Program Files\PTC\Creo 12.4.0.0\Parametric\bin\parametric.exe`）
- 会话指纹：`parametric.exe` pid **16296**（2026-10-21T03:31:29.943896+00:00，窗口 hidden_only、hung_window_observed=true、visible_hung=false）+ `xtop.exe` pid **21144**（03:31:30.691916，可见窗口 1 个、无 hung）；任务内 `session_fingerprint=12830465268385011701`

## 7. 按别名编辑（唯一一次提交）

再读 revision = **1**、pending_job 空 → 提交
`creo_set_sketch_dimensions{model_id:"7efb4e26…0ee9", expected_revision:1, sketch:"disk_profile", values:{diameter:20}}`

- job_id **bc100ebc75aa4c1bbebaf1ced97c2d6b**，queued → running(connect → save_and_reload) → **succeeded / stage=verified**
- revision **1 → 2**，finished_at 2026-10-21T14:32:35.818632+00:00
- **saved_file_reloaded_and_verified=true**，success=true，toolkit_code 0，creo_release_numeric 44，rollback_succeeded=false（未触发回滚）
- volume **3141.5926535897925 mm³**（目标 3141.592653589793，偏差 5e-13，远小于 0.01）
- part_file `…\output\wb047_legacy_prep_1021a.prt.3`，sha256 **eac91ead42ae087e8a885f9403108b40566d20fbb2d07f6ff713fc61d94cb875**
- inspection_summary：healthy/has_solid=true，units mm，features 8 / surfaces 4 / edges 6 / bodies 1

## 8. 编辑后复核

- compact：**ready**，revision **2**，pending_job **null**，last_job = 上述编辑 job，volume 3141.5926535897925，part_sha256 **eac91ead…b875**（已改变，符合预期）
- full/aliases：`disk_profile`、`disk_solid` 仍可见，dimension_ids.diameter=2、entity_ids.disk=5、feature_id 40/47 未变
- full/sketch_dimensions：id=2 value **20.0**

## 未测 / 不可见项

- 源码提交号、构建号：**无法确认**
- 备份原始字节的逐字节核验、迁移日志内容：**未验证**（仅取公开 `backup_sha256`，未读 `models/registry-migration.jsonl`）
- >16 MiB 单模型迁移、485 条历史批量迁移、恢复 apply / 回滚、Creo 10 原环境、真实并发争用：**未测试**
- 别名 `geometry.radius` 在迁移后仍显示创建时的 8.0（别名记录内原始几何，未被尺寸编辑重写）；实际尺寸以 sketch_dimensions 的 20.0 与体积 3141.59 为准

## 结论

**小型真实旧内联模型的非空迁移 → 幂等回放 → 按别名编辑/保存重载**：迁移首次 migrated=1（job 详情拆分 1 个文件）、同键重放 replayed=true 且 completed_at 与计数一致、迁移后待迁移条目归零且模型身份/体积/SHA256 未变；随后 `disk_profile.diameter` 由 16 改为 20 一次受理成功，revision 1→2，体积 3141.5926535898 mm³，保存并重载验证通过，别名字段继续可用。测试模型已保留，未做恢复、回滚或擦除。