# BUG-077 超限（>16 MiB）注册表条目实机迁移验收记录

日期：2026-10-21。开发者侧实机验收，对应[工作卡](../work-items/BUG-077.md)验收标准"构造 >16 MiB 历史条目（内联 aliases）后：迁移 → 收养 → 该模型编辑"一行。

## 环境

- Windows x64 / Creo 12.4.0.0（release_numeric 44）/ Toolkit 会话指纹 `12830465268385011701`
- E 盘 dev 服务 `MCP_CREO_MechDog_dev`，公开版本 0.4.7（startup_status `update.current_version=0.4.7`）
- 分支 `codex/bug077-registry-split`（31e16ff 之上）；建模经 stdio 直连 server.py（ZCode 连接器 `creo_execute_plan` schema 缓存拒绝合法 plan，为已知连接器问题），其余全部经 MCP 公开工具
- 会话核对：startup ready/connected；上一轮 WorkBuddy 已确认会话可操作；本轮全部操作通过 MCP/stdio 完成

## 专用夹具

- 模型 A `e3abec8f44b84227b9acf28bf3e1d249`（`wb047_oversize_1021a`）：圆盘 d16×深10，创建作业 `db5868a31eae4468b73251e045f60260` succeeded、revision 1、`saved_file_reloaded_and_verified=true`、体积 2010.6192982974674 mm³、PRT `.prt.2` SHA256 `a7105c87d41ed77536993518641ad802369d2286304fdde64967a67fc2184bd7`
- 膨胀脚本（持共用通道锁，仅元数据）：将 A 及其创建作业还原为旧内联形态后，向 aliases 追加 42,000 条惰性填充条目（克隆 disk_profile 结构、独立标签、feature_id 自 100000 递增），紧凑序列化 17,393,662 B > 16,777,216 预算。原始拆分字节备份为 `*.before-oversize-fixture`；膨胀字节 SHA256 `5460a3a31cd950fff6a03e46514d69d18605c5d9b6d9c125a0dbf216a655c0c2`
- 膨胀时刻核对：其余 530 个模型登记与 3,867 份其他元数据字节不变；PRT 与 14 份原生证据不变。脚本与报告在忽略目录 `build/bug077-oversize/`

## 验收证据（全部 MCP 公开接口）

### 1. 超限条目的可见与阻断

- `creo_registry_health`：A 归类 `over_budget`（usage_ratio 1.0367，aliases inline 19,488,510 B）；summary `ok=45 / legacy_inline=485 / over_budget=1 / corrupt=0`，响应分页（32 KiB 预算、has_more/next_cursor）正常。膨胀时全表 model.json 总计 30,105,979 B
- 不相关零件 B `WB047_BOX_B1`（有盘、未修改、无登记关联；经 `creo_erase_session_models` inspect/apply 擦除后 `creo_open_file` 取回并显示，job `eb5bc12cfbb34f56bd455ba8208087c5`）收养 inspect被结构化拒绝：`ADOPTION_METADATA_BUDGET_EXCEEDED`、`failed_stage=origin_conflict_scan`、path 指向 A 的 model.json、`actual_bytes=17393662 / budget_bytes=16777216`——不再静默跳过或死锁
- 开发侧同口径：`read_control` 抛 `REGISTRY_METADATA_BUDGET_EXCEEDED` 六要素齐全并带迁移指引

### 2. 迁移与幂等回放

- 单目标 inspect：`entries_needing_migration=1`，`model_json_bytes=17393662`，`inline_details=[aliases, inspection]`，`job_chain=[db5868a31eae4468b73251e045f60260]`
- apply（键 `wb047_osz_mig_e3abec8f_01`）：`migrated=1 / job_files_split=1 / refused=0 / replayed=false`；model 备份 SHA256 与膨胀字节一致（`5460a3a3…`），控制记录新 SHA256 `87aac5b66517211ae184fae0b5c3d479ac25d6c47d78d312bbcfe55383e5fb00`
- 编辑前同键回放：`replayed=true`、completed_at `2026-10-21T15:07:27.941209+00:00` 及全部计数/摘要一致，目标集指纹 `2efef65d6f772290`
- 迁移后单目标 inspect：0 条待迁移

### 3. 迁移后开发侧核对（`build/bug077-oversize/verify_migration.py`，报告 `verify-migration.json`）

- 控制记录 1,634 B（<64 KiB）且无内联详情；aliases sidecar 31,668,816 B（>16 MiB）SHA256 `05c025ba21fa2fe419c0cd274ffb2c40de4f262569cd16aa1ba1512b5754618d` 核验通过，按需解析 42,002 条别名（2 条真实 + 42,000 填充），`disk_profile.diameter` 仍为 dimension 2
- `semantic_view` 备份内联形态与拆分后完全一致；PRT SHA256 不变；两份 `.pre-split-bak` 完好
- 全表字节守恒：30,105,979 − 17,393,662 + 1,634 = 12,713,951 = 迁移后 health `total_model_json_bytes`（其余登记总字节不变）；summary `ok=46 / over_budget=0 / legacy_inline=485`

### 4. 迁移后不相关零件可继续收养

- B 的文件源收养 inspect：`available=true`、`conflict=null`、live 检查完整（6 特征、1000 mm³），evidence_token 正常下发——与迁移前同路径的结构化拒绝形成直接对照
- apply（job `75b5b0ebd68343c6b73de5b3c8fb4851`）succeeded：受管副本 `d9d25bc43816465cb9d12196d6bc3dfe`（`wb047_osz_adopt_probe`）revision 1、`saved_file_reloaded_and_verified=true`、源文件未修改

### 5. 迁移后该模型编辑（引用形态请求）

- `creo_set_sketch_dimensions`（sketch `disk_profile`，diameter 16→20，expected_revision 1）：作业 `d9ef41109f3847a2b6b5e1756351b73b` succeeded、revision 1→2、`saved_file_reloaded_and_verified=true`、体积 3141.5926535897925 mm³（=π·10²·10，直径 20 精确生效）
- 作业结果直接可见 `aliases_ref`：请求详情以 31,668,816 B sidecar 引用传递（SHA256 与迁移产物一致）——超限模型的编辑请求不再受 16 MiB 读取预算约束，由 native 无预算解析引用并按别名修改
- 终态：ready、revision 2、`pending_job=null`、PRT `.prt.3` SHA256 `01a373bb08b5e85147924ae09c1cc3d329c690162fd683ed71ada809656a5d98`；编辑后 aliases sidecar 内容寻址未变（映射本身未变，与上轮小型迁移行为一致），inspection sidecar 更新为 saved_reloaded 快照（9,599 B）

### 6. 顺带取得的真实恢复动作证据（第 2 组部分）

- B 首次收养误用 never-saved 的 prepare 模式，产生 `adopt_pending`（revision 0）模型 `bc1a58f3a5abcbcf2f2aaeaa635fba40`，作业 `19b42e6d6a2a4e878ae9f06f38d22769` unknown_outcome（`native_worker_started`），保护保留
- live inspect：owners stopped（runner 25424 / worker 23412 均确认退出）；四个动作中仅 `abandon_new` available（restore_baseline/accept_saved/accept_live 因无 baseline/candidate/owned live 证据不可用）——revision 0 无保存文件的适用边界真实观测
- apply `abandon_new`（恢复作业 `850873fa630b4627b8daabbd37ddf9d8`）succeeded `reconciliation_committed`：revision 0、原始作业历史保留、文件未删

## 边界与未测

- pending/活动 owner 的迁移拒绝未做实机自然构造（超限时编辑提交本身被预算拒绝，无法为超限条目制造 pending 作业）；该路径由 530 项单测中的"待运行/活动/未知 owner"回归覆盖
- 膨胀 aliases 为人工填充条目，不是自然膨胀的 21.4MB 真实条目；原环境（外部 Creo 10 / track_p01b）复测仍开放，本机通过不外推
- 恢复 apply 四动作仅 `abandon_new` 取得真实证据；restore_baseline/accept_saved/accept_live 及适用回滚、图纸等其他原生消费点、32 KiB 预算的损坏条目场景仍开放（第 2～4 组）
- 485 条真实历史旧登记未批量迁移；未合入 main、未发布
