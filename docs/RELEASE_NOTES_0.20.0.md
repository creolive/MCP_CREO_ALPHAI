# MCP_CREO_MechDog 0.20.0

日期：2026-11-10。类型：MINOR。公开工具：107（与 0.19.3 相同，新增能力是工具参数与回执字段，不是新工具）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.20.0 交付 [DEV-081](work-items/DEV-081.md) 的 B 批原生/实机四项（B1/F01、B2/F11、B3/F06、B4/F08），连同 C1 的 F08/F09/F10 契约冻结与 [BUG-001](work-items/BUG-001-FEAT-018-RECOVERY.md) 实机放行规则修订。四项全部在本机 Creo 12.4.0.0 + 匹配 Toolkit SDK 上实机验收，包含几何断言、保存重载与失败回滚。

B4 新增公开参数 `extrude(scope=...)`，属新增功能，按约定递增 MINOR。原有调用与省略 `scope` 的切除行为不变。

## 本版变化

### B4/F08 选择性切除作用域（新增公开参数）

- `extrude` 与计划操作新增可选 `scope={kind:"bodies", body_ids:[N]}`：多实体零件只切一个实体。实体 ID 取自 `creo_inspect_model` 的 `bodies[].id`。
- 省略 `scope` 时保持原全局切除（`PRO_BODY_USE_ALL`）。提交前拒绝：多个实体、`kind` 非 `bodies`、非 `cut`、`through_all`、`new_body=true`、`revolve` 带 scope；拒绝给出 `F08_SCOPE_*` 指引且不产生作业。
- 成功作业的操作结果带 `scope_applied`：`requested_body_ids`、`applied_body_ids`（从**创建后的特征树**回读，不回填请求值）、`source`、`query_code`、`non_target_bodies_unchanged`。回读值与请求不一致、特征未携带选择或无法读取时作业失败并回滚（`F08_SCOPE_RESOLVE_FAILED`），并把回执写进结果；非目标实体的面数或包围盒变化时失败并回滚（`F08_SCOPE_NON_TARGET_CHANGED`）。
- `non_target_bodies_unchanged` 是三态：`true`、`false`、`null`。查询不完整时给 `null`，不会填 `true`；非目标位置新增实体算变化。
- 能力边界写进 `creo_capabilities` 的 `known_limitations.cut_scope`，参数语义写进 [REFERENCE_SYNTAX](REFERENCE_SYNTAX.md) 与 [COMPATIBILITY](COMPATIBILITY.md)。

### B1/F01 无 callback 放样的 seed 兼容性预检

- 提交放样前先给出 seed 兼容性结论，避免连接后才发现不可行；不满足时在准入阶段拒绝并说明原因，不产生作业。

### B2/F11 零去料切除的结构化几何回执

- 切除未移除材料时，错误信息附草图原点、法向、方向符号与有效深度区间，并在结果里给出结构化 `cut_geometry_context`，便于复算，不再只给一句文本。

### B3/F06 阶段进度与日志体积

- `creo_get_job` 的 compact 视图按操作输出 `operation_index`/`operation_total`，长计划可读当前进度；同时暴露原生日志体积与 `truncated` 标记。

### C1 契约冻结与规则修订（不含实现）

- F08/F09/F10 的公开契约（字段、默认值、错误码、回执字段）在实现前冻结，分别由 `f08_contract`、`f09_contract`、`f10_contract` 承载；B5/F09 着色预览与 B6/F10 锥台尚未实现。
- 本机实机放行按用户 2026-11-09 决定改为「用户当次明确确认后即可用 Creo 实机测试」，安全底线与单通道/busy/revision/保存重载边界不变，见 [AGENTS.md](../AGENTS.md)。

## 验证

环境：Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可；`bridge.py status` → `connected=true`、`toolkit_code=0`。实机执行经用户当次明确确认，未结束或重启 Creo/nmsd、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型与历史证据。

- B1：`tools\test_installation_loft.py --live --confirm-session-usable --case matrix_two_straight --case invalid_seed_feature_id` → `success=true`。正例建件 job `6294f20c…`、revision 1、体积 7000 mm³、`saved_file_reloaded_and_verified=true`；改尺寸 job `3219ae25…`、revision 2、体积 8166.6667。负例在准入阶段被拒（无 `job_id`）。
- B2：`tools\test_cut_material.py` → `failures=[]`。T01 23371.6815 mm³（24000−200π）、T04 40.8753 vs 40.87528、T08a 94.2479（30π）；零去料回执含原点/法向/方向符号/深度且 `rollback_succeeded=true`；T03 重复切除 revision 不变。
- B3：`tools\test_job_progress_live.py` → `success=true`、`failures=[]`。20 op 计划 job `72a71fbc…` 的 compact 采样 `operation_index` 1→20 单调、`operation_total=20`、`log_bytes` 7806→387996、`truncated` false→true、终态 `stage=verified`、体积 22869.0263 vs 22869.0266；失败计划 job `ad67410a…` 的 `failed_operation_index=3`、`rollback_succeeded=true`、revision 未前进。
- B4：`tools\test_cut_scope_live.py --live --confirm-session-usable` → `success=true`、20 项 `checks` 全为 true、`failures=[]`。两实体零件（body 52 板 60×40×10、body 90 块 40×40×10，切除前各 6 面）只切 body 52：body 52 面数 6→8、body 90 面数与包围盒不变、总体积 39214.6018 mm³（40000 − 250π）、`saved_file_reloaded_and_verified=true`；`scope_applied` 的 `applied_body_ids=[52]` 由特征树回读、`source=feature_tree`、`query_code=0`、`non_target_bodies_unchanged=true`。负例：body id 100000 → `F08_SCOPE_RESOLVE_FAILED`、`rollback_succeeded=true`、revision 未前进；`mode=add` 带 scope 在准入阶段被拒绝，未创建作业。
- 全量单元测试：`Ran 3263 tests in 372.635s ... OK`（工作树）。
- `tools/dev_check.py --work-item DEV-081 --unit-timeout-seconds 1800`：EXIT=0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；受测源码指纹 `417a0477e95127c5567c65934f361110ce31f86dc9959cc5f20ec538b21488a5`（`source.dirty=true`，提交号仅作定位）。风格基线为存量 21 项 lint / 9 个未格式化文件，未新增诊断。
- `tools/check_backlog_counts.py`：`consistent=true`（172 / BUG 75 / FEAT 61 / DEV 36）。
- 种子包按确定性流程构建两次，SHA256 一致并回填 `docs/seed_package.json`；源码包与种子包各自生成 `.zip.sha256` sidecar。
- **源码包解压后全量单测为独立门禁**，其结论在 Release 正文与 [发布记录](validation/RELEASE-0.20.0.md) 中给出；源码包内的本文件保留发布前摘要。

## 未测范围与已知限制

- B5/F09 着色预览与 B6/F10 锥台拔模**未实现**；本版只冻结它们的公开契约。
- C 批 WorkBuddy 黑盒（C0—C5）未执行；开发者实机证据不替代黑盒验收。
- B4 未覆盖：回读不匹配与元素缺失的失败路径（仅有源码哨兵）、装配模型内切除、三个以上实体、非目标实体新增/消失、查询不完整导致 `non_target_bodies_unchanged=null` 的真实路径、compact 32 KiB 预算下 `scope_applied` 是否被裁。
- B1 的 callback 路线实机负例、种子矩阵其余 13 个夹具未验；B3 的 3—7.7 MB 日志与 1 MiB 阈值未真实触发。
- Creo 9 / Toolkit 9 与 Creo 10 未复测（编译探测修复已实现，本机无对应 SDK）；不把本机 Creo 12.4 结论外推到其它版本。
- BUG-001 卡死根因仍未确定；本版实机证据如实记录该事实，规则放宽不等于根因已解决，也不得擅自结束/重启 Creo 或清 `toolkit.lock`/unknown 保护。
- 单通道边界不变：通道忙碌立即拒绝（`status="busy"`），不排队、不自动重试；并发能力现状归 BUG-009。

## 安装与升级

安装、客户端注册与种子库步骤见 [docs/INSTALL.md](INSTALL.md) 与 [docs/SEED_LIBRARY.md](SEED_LIBRARY.md)。升级后请重启 MCP 客户端，使新的 `scope` 参数与回执字段生效。本版无需迁移模型或配置；本版原生执行器需要重新编译（`bridge.py build`）。已发布的 `v0.19.3` 标签与四附件保持原样。

## 附件

发布附件固定四个：源码包、种子包及各自 `.zip.sha256`。文件名与完整 SHA256 在 Release 正文与 [发布记录](validation/RELEASE-0.20.0.md) 中给出；源码包内的本文件保留发布前摘要，实际摘要以 Release 与 POSTCHECK 为准。
