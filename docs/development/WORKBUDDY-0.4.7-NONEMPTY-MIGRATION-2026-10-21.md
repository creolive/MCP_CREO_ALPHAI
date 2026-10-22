# WorkBuddy：0.4.7 单目标非空迁移及后续编辑验收

开发侧已把你先前新建的专用模型及其创建作业详情无损还原为旧内联格式，并核对原生文件与revision不变。你现在只通过已连接的 `MCP_CREO_MechDog_dev` 公开工具完成以下实际操作；不读源码、配置、磁盘文件、Git或日志，不运行终端、脚本、单测或开发检查，不调用其他服务代替。

固定测试目标：

```text
model_id = 7efb4e2646464e44a5fc8a86b89c0ee9
model_name = wb047_legacy_prep_1021a
creation_job_id = 9065e89d354448adb765f69bedaf5e6b
initial_revision = 1
initial_volume_mm3 = 2010.6192982974674
initial_part_sha256 = 759295a5b0f5868cfcd2bf9d959e89413cfb6e6bfc9917697c0ffe5bfcdc52db
idempotency_key = wb047_real_mig_7efb4e26_01
```

不要新建替代模型，不迁移任何其他模型，不省略targets，不删模型或清保护。步骤遇到不符、busy、连接超时、unknown_outcome或界面异常即停止并保留原始结果；不自动重试或重复提交。已受理原生任务只轮询原job_id，不能重新提交。

1. 调用 `creo_capabilities(detail="compact")` 确认0.4.7及E盘dev部署。公开接口不能确认的源码提交、构建号记为“无法确认”。版本不符立即停止。
2. 调用 `creo_inspect_model(model_id=固定ID, detail="compact")`，并以 full/aliases 检查disk_profile、disk_solid和diameter。必须ready、revision=1、pending_job为空、体积与初始值在0.01 mm³内；通过公开结果核对可获取的完整SHA256。公开字段缺失写“无法确认”，不读磁盘补齐。
3. **先确认非空**，调用：

```json
{"mode":"inspect","targets":["7efb4e2646464e44a5fc8a86b89c0ee9"],"limit":20}
```

工具为 `creo_migrate_registry`。预期entries_needing_migration=1，唯一条目ID一致，inline_details包含aliases和inspection，job_chain包含上述完整创建job_id。若0条或目标不符，停止报告，不做空迁移。

4. 调用一次 `creo_migrate_registry`：

```json
{"mode":"apply","targets":["7efb4e2646464e44a5fc8a86b89c0ee9"],"idempotency_key":"wb047_real_mig_7efb4e26_01","limit":20}
```

预期migrated=1、refused=0、replayed=false，且创建作业详情得到拆分（job_files_split至少1，记录实际动作）。这是同步维护调用，不要求生成建模job_id。记录全部actions、backup_sha256、completed_at；若有has_more，用同键、同targets和next_cursor读取完整动作，不换键重做。

5. 在任何几何编辑之前，以完全相同的apply输入立即重放。必须replayed=true、completed_at及迁移计数与首次结果相同。再用单目标inspect确认entries_needing_migration=0，并用模型inspect确认ready、revision仍1、体积及可公开取得的PRT SHA256不变，别名和尺寸可见。仅凭公开返回的backup_sha256不能声称“备份原始字节已逐字节核验”。
6. 实际改尺寸之前，取得操作者确认当前Creo界面正常响应、无阻塞对话框、无运行任务。调用 `creo_startup_status(retry=false)`，ready后调用 `creo_session_status`，必须connected=true。building/checking只轮询本次状态，最多60秒；其余异常停止，不retry=true、不结束/重启Creo。确认Creo版本，记录会话指纹；若界面可操作已无法确认，不执行后续原生编辑。
7. 再读模型最新revision，正常应为1；若不是1，停止避免改写已变化对象。调用 `creo_set_sketch_dimensions`：

```json
{"model_id":"7efb4e2646464e44a5fc8a86b89c0ee9","expected_revision":1,"sketch":"disk_profile","values":{"diameter":20}}
```

只提交一次，受理后用 `creo_get_job(job_id=实际返回ID, detail="compact")` 轮询至终态。预期succeeded、revision从1变2、saved_file_reloaded_and_verified=true、体积3141.592653589793 mm³（容差0.01），说明迁移后的真实模型可按原尺寸别名编辑并保存重载。用 full job / inspection公开字段补齐证据即可，不读本地文件。
8. 用模型inspect compact及full/aliases核对ready、revision=2、pending_job为空、体积符合、disk_profile/disk_solid/diameter继续可见。编辑后PRT SHA256可改变，记录实际值。至此停止，保留测试模型，不做恢复apply、回滚、擦除或额外修改。

报告要求：逐项给出实际工具名和输入、完整model_id/job_id、服务和Creo版本、revision前后、终态、保存重载字段、体积、公开SHA256、迁移首次与回放计数/completed_at、动作及原始错误。将未测/接口不可见项明确列出。最终结论限定为“小型真实旧内联模型的非空迁移→幂等回放→按别名编辑/保存重载”。不得外推到>16MiB迁移、485条历史批量迁移、恢复动作/回滚、Creo10原环境或未实际执行的并发。
