# BUG-077：真实小型旧内联夹具准备（0.4.7）

日期：2026-10-21。分支：`codex/bug077-registry-split`；准备时 HEAD：`29e6aab`，受管源码 clean（另有无关未跟踪文件）。本次只改本机生成元数据及新增文档，没有修改业务源码、构建或版本。开发验证与 WorkBuddy 黑盒结果分别记录。

## WorkBuddy 交回的新模型

用户提供公开 MCP 报告：`MCP_CREO_MechDog_dev` 连接到 E 盘项目，服务 0.4.7、90 个启用工具；操作者确认界面可操作，`creo_session_status` connected=true、toolkit_code=0、release_numeric=44（Creo 12.4），session_fingerprint=`12830465268385011701`。源码提交及构建号无法从公开接口确认，不把开发侧 HEAD 等同于公开运行进程身份。

| 字段 | 用户报告及开发侧核对 |
| --- | --- |
| 模型名 | `wb047_legacy_prep_1021a` |
| model_id | `7efb4e2646464e44a5fc8a86b89c0ee9` |
| 创建 job_id | `9065e89d354448adb765f69bedaf5e6b` |
| 状态 / revision | succeeded（job）、ready（模型）/ 1，无 pending_job 或 recovery_pending |
| 几何 | XY 圆草绘直径16，拉伸深10；体积2010.6192982974674 mm³ |
| 别名 | disk_profile feature_id=40，disk entity_id=5，diameter dimension_id=2；disk_solid feature_id=47 |
| 保存重载 | saved_file_reloaded_and_verified=true |
| 原生 PRT SHA256 | `759295a5b0f5868cfcd2bf9d959e89413cfb6e6bfc9917697c0ffe5bfcdc52db` |

WorkBuddy 到创建并检查别名后停止，没有改尺寸或执行迁移。此前开发侧启动超时的尝试没有创建模型；本次直接使用上述用户明确指定的新模型，没有重新连接 Toolkit。

## 开发侧准备

运行命令：`.\.venv\Scripts\python.exe build\bug077-fixture\restore_inline.py`。脚本与完整前后哈希快照在忽略目录 `build/bug077-fixture/`，报告为 `restore-inline.json`；准备完成时间 `2026-10-21T13:44:48.693391+00:00`。

脚本 SHA256：`ed36c4a4e257178c20c8e53c07454b242a22b172e1405077a7e97438d8528afd`；完整报告 SHA256：`2c4596272eb82ac95e53625b86c522f114abf0a3312ecbbe87a630dbe674dcdd`。

持有 `bridge.toolkit_lock(operation="prepare_registry_fixture", model_id=...)`，取得锁后核对模型身份、revision、终态、关联请求和 PRT。进程身份实查：runner PID24120、worker PID1836 均已退出，记录的创建时间身份匹配检查返回 stopped=true。未根据 job 中历史 alive=true 推断当前仍活动，也未清除任何保护。

仅对指定模型的 model.json 和其创建作业 job.json.result，把经过路径、字节数、SHA256 校验的 aliases_ref / inspection_ref 解析成原内容并内联；移除对应引用及派生摘要，控制字段和详情内容保持等义。先备份拆分格式的原始字节，再原子持久化两份元数据。未删除 sidecar，未修改 request.json、native_result.json、native_checkpoint.json、PRT 或其他已有登记。没有构造大字段或故障状态。

| 文件（相对项目根） | 原字节数 | 旧内联字节数 | 旧内联 SHA256 |
| --- | ---: | ---: | --- |
| models/7efb4e2646464e44a5fc8a86b89c0ee9/model.json | 1624 | 12996 | `dd40b15c9d4d7ed3c75b7587a5b816c33950d528a632a7471cfa703b23fdc858` |
| jobs/9065e89d354448adb765f69bedaf5e6b/job.json | 3934 | 16538 | `b4fd5b744d4f97c84ea9dbc89ded8c299e5a3b0129e6e965de55c4136ace9099` |

原始拆分字节备份分别在同目录的 `model.json.before-legacy-fixture` 和 `job.json.before-legacy-fixture`，SHA256 为：

- model：`76ed2718f7d72f8e6a5efc7b5e58c44b4d94c93410323629b9e878d05657b74c`。
- job：`86fbfbed49979110908e001903e11914d7eb9f8db76b980bbeb50d9b22b68d00`。

这两份是开发准备备份；迁移工具尚未生成自己的 `.pre-split-bak`，不能混为一次迁移成功。

## 核验结果与边界

- model 与 job.result 的 `semantic_view` 转换前后完全相等；model revision仍为1，PRT SHA256保持原值。
- 其余529份 model.json，以及其他 job.json 和所有 request.json 共3862份元数据前后 SHA256 相同；目标目录中12份已有不可变文件前后相同。
- 开发侧直接调用只读 `registry_ops.migrate(mode="inspect", targets=["7efb4e2646464e44a5fc8a86b89c0ee9"], limit=20)`，返回 `entries_needing_migration=1`，inline_details=`["aliases", "inspection"]`，job_chain仅上述创建作业，has_more=false。
- 元数据 inspect compact 与 full/aliases 可读；这是开发侧检查，不冒充 WorkBuddy 公开 MCP 验收。
- 没有执行任何迁移 apply 或新原生操作，没有批量迁移485条历史旧登记。未改业务代码，不重复运行已通过的530项单测、dev_check或SDK构建。

结论：真实小型非空迁移夹具已就绪。下一步使用[WorkBuddy 单目标非空迁移提示词](../development/WORKBUDDY-0.4.7-NONEMPTY-MIGRATION-2026-10-21.md)执行迁移、幂等回放和实际改尺寸闭环。当前不能报告非空迁移、超限迁移、恢复apply或回滚通过；BUG-077继续验收中。
