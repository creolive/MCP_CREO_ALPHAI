# WorkBuddy 0.4.7：小型真实旧内联迁移与编辑闭环

日期：2026-10-21；报告来自用户提供的 WorkBuddy 公开 MCP 黑盒结果。仅补录本次实际范围，不替代超限迁移、恢复apply或回滚验收。本次接收没有新增 Toolkit 连接或重复建模调用。

## 原件与身份

- [报告原件](workbuddy-0.4.7-nonempty-2026-10-21/report.md)逐字节归档，7658 B，SHA256：`bad2923da5ffd4cf06a43818db58c2abe6d66328bbc3cba2234f9da5ecfbd313`；[manifest](workbuddy-0.4.7-nonempty-2026-10-21/manifest.json)记录来源与证据边界。用户随后在对话粘贴的同轮内容与此结论一致，原附件保留不改。
- 公开服务0.4.7、90个启用工具、E盘dev，Creo12.4.0.0（release_numeric44）。操作者确认界面正常；启动状态缓存较旧，随后session_status返回connected=true、fresh，Toolkit代码0；任务内session_fingerprint=`12830465268385011701`。
- 受测源码提交及构建号公开不可见，保持“无法确认”。开发侧接收时仓库HEAD为 `0d0462681672d487e8c1da301394c561a6f73a79`，受管源码clean；这不是公开进程的构建证明。
- 完整model_id：`7efb4e2646464e44a5fc8a86b89c0ee9`；模型名 `wb047_legacy_prep_1021a`；创建job_id：`9065e89d354448adb765f69bedaf5e6b`。夹具如何由开发侧还原旧内联，见[准备证据](BUG077-LEGACY-FIXTURE-PREP-2026-10-21.md)。

## 本轮公开黑盒结果

按[单目标提示词](../development/WORKBUDDY-0.4.7-NONEMPTY-MIGRATION-2026-10-21.md)的8步完成。无首次错误、重试、重复提交、擦除、清保护或回滚。

| 阶段 | 实际结果 |
| --- | --- |
| 初始模型 | ready、revision1、pending_job=null；直径16、体积2010.6192982974674 mm³；PRT SHA256 `759295a5b0f5868cfcd2bf9d959e89413cfb6e6bfc9917697c0ffe5bfcdc52db` |
| 非空inspect | targets仅该完整ID；entries_needing_migration=1，model_json_bytes12996；inline_details为aliases/inspection，作业链仅创建job；无后续页 |
| 首次apply | 同一单目标，key=`wb047_real_mig_7efb4e26_01`；migrated=1、job_files_split=1、refused=0、replayed=false；completed_at=`2026-10-21T14:04:02.009319+00:00` |
| 编辑前同键回放 | replayed=true；计数、completed_at及两项备份/控制摘要相同，fingerprint=`1d27d06387b7c8d5` |
| 迁移后未编辑 | 待迁移数0；ready、revision仍1，身份、体积、PRT摘要及尺寸别名保持；updated_at未变 |
| 按别名编辑 | sketch=disk_profile，diameter=20，expected_revision=1；一次受理，job_id=`bc100ebc75aa4c1bbebaf1ced97c2d6b`，仅轮询该作业 |
| 编辑终态 | succeeded/verified、revision2、saved_file_reloaded_and_verified=true；finished_at=`2026-10-21T14:32:35.818632+00:00` |
| 最终核对 | ready、pending_job=null，体积3141.5926535897925 mm³（容差0.01内）；实际尺寸20.0，disk_profile/disk_solid及diameter别名可见 |

迁移动作备份摘要：model.json=`dd40b15c9d4d7ed3c75b7587a5b816c33950d528a632a7471cfa703b23fdc858`，job.json=`b4fd5b744d4f97c84ea9dbc89ded8c299e5a3b0129e6e965de55c4136ace9099`。首次迁移控制摘要 `bf0045390b8f7a1e77d2e7675bb98fccd584a98cec54d3f0730ed8327fca1c03` 为编辑前结果，后续编辑可改变控制记录。

编辑后PRT为 `.prt.3`，SHA256：`eac91ead42ae087e8a885f9403108b40566d20fbb2d07f6ff713fc61d94cb875`。原 `.prt.2`保留。别名feature_id40/47、disk entity_id5、diameter dimension_id2不变。别名geometry.radius仍为8，不能用该创建时几何记录代替当前尺寸；本轮实际尺寸20与保存重载体积提供编辑正向证据。没有据此评审或更改别名几何字段的接口承诺。

## 独立开发侧只读补核

命令：`.\.venv\Scripts\python.exe build\bug077-fixture\receive_nonempty.py`。只读取已有文件并归档文档，不调用MCP或Toolkit；结果见[developer-check.json](workbuddy-0.4.7-nonempty-2026-10-21/developer-check.json)。

- 两份 `.pre-split-bak` 与准备阶段记录的旧内联SHA256一致；从保存的拆分原件及核验后的sidecar按原算法重建旧内联字节，与迁移备份逐字节相等。这是开发者补核，不能写成WorkBuddy黑盒读取了备份。
- 持久化幂等记录的计数、目标指纹和completed_at吻合；迁移日志中存在该目标的migrate记录。未从单个日志条目或最终文件状态推断调用重放过程，回放结论来自用户报告。
- 最终模型控制记录1624 B，无内联详情；revision2、ready，PRT实文件摘要、详情引用完整性、体积及编辑作业的保存重载字段吻合。
- 与准备阶段快照相比，其余529个模型登记、其他job.json和所有原有request.json共3862份元数据字节摘要不变；目标原有12份原生证据/详情/文件不变。新增编辑作业及新保存文件不包含在“原有文件”集合中。
- 本次没有修改业务源码，不重复运行已通过的530项单测、dev_check或SDK构建；历史代码回归证据独立保留。

## 状态与下一步

BUG-077的小型真实旧内联模型“非空迁移→同键回放→按别名编辑→保存重载”子项通过。BUG-077仍为验收中：本轮没有>16MiB实机迁移及其收养/编辑、恢复apply/回滚、其他原生消费点或真实并发；不外推到485条历史批量迁移或外部Creo10。外部环境未测事实保留，不新增Creo10全项目复测发布门槛。

测试模型保留，485条历史旧登记不变。下一项是独立专用超限夹具的迁移及后续消费验证，须单独准备、限定目标并遵守现有会话/故障注入边界；本次未做该准备。版本仍0.4.7，未合入main、未创建发布标签或Release，DEV-044整体仍未完成。
