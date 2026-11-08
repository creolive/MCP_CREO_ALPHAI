# DEV-074 / H12：0.17.4 回执字段公开 MCP 实机复验（2026-11-07）

条目：[DEV-074](../../work-items/DEV-074.md)（H12）、[BUG-115](../../work-items/BUG-115.md)、[BUG-109](../../work-items/BUG-109.md)。
本目录为新增证据，未修改 `docs/validation/` 下任何既有原件字节。

## 1. 环境与受测源码

| 项 | 值 |
| --- | --- |
| 环境 | Windows x64；Creo 12.4.0.0（用户已手工启动并确认可用，单会话串行）；匹配 Toolkit SDK；MSVC x64 |
| 工作树 | `E:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-h05h12` |
| HEAD | `f60811bf916596020ebd3ba6a9bef8c268ee641d` + 本轮新增驱动与证据（提交时 dirty） |
| 服务版本 | `creo_session_status.server_version=0.18.3`，`mode=explicit_live`，`connected=true` |
| 执行器 | `build/creo_worker.exe` SHA256 `3AC423DD831674A668AD3DF081839189AEDFD6D009A3DBEC843C02B5B584E2CB`（`bridge.py build` exit 0） |
| 驱动 | `tools/test_feedback0174_receipts.py` SHA256 `6F12AF6D0D713464A520FBA3F20E76CE6CD4A155AFBEC338A04983675AE187DE` |
| 受测投影源码 | `src/creo_mechdog/native_planar_wall.py` `FC56C6AA…AEA383`；`src/creo_mechdog/preview.py` `D3385FAB…27386B`；`creo_startup.py` `46B63333…56F0C`；`native/advanced.cpp` `09CA464B…A29EBB` |
| 命令 | `.\.venv\Scripts\python.exe tools\test_feedback0174_receipts.py --live --confirm-session-usable` |
| 原始报告 | [live_receipts_report.json](live_receipts_report.json)：驱动写出的工作树副本 91195 bytes，SHA256 `65EA57BAB677F9BB940076DC5001FE2634E8F368F5F111314619FFE29F714FDC`；提交进 Git 后按 LF 归一化为 88297 bytes，blob SHA256 `78FB0A303BCDF2EE892F5CDA60E5B34A2023610CA8FB8F397180EA9228AFD236`（内容相同），run `20261108T002653_283` |
| 只读补核 | [followup_full_compare.json](followup_full_compare.json)：同一批 job 的 `detail=full` 与 compact 回执比对，以及空模型 job 的保存结论（不提交、不改模型） |

纪律：单连接、每个用例只提交一次、失败不重提；未启动/关闭 Creo、未清 unknown 保护、未做故障注入、未并发提交。
全部模型为本轮新建（`h12_*`），未触碰既有模型。运行结果：**38 项检查，0 失败**。

## 2. 结论总表

| # | 复验项 | 判定 | 关键证据 |
| --- | --- | --- | --- |
| 1 | 失败回执 `feature_id`/`feature_id_unchanged`/loaded 字段（反馈 §3.2） | **一致**（离线修复已由实机确认） | 失败 resize `64149031…`：`feature_id=null`、`feature_id_unchanged=null`、`thickness_loaded_validation/api_scope/api_reason/fallback_source/verified_effective` 全部显式 `null`，`verified=false` |
| 2 | 板厚权威判据 `thickness_validation` 与 loaded 上下文（§3.1） | **一致** | 建壁 `db391407…`：`current_plan/verified/api/1.0`；改型 `149d8ae7…`：`current_plan/verified/api/1.0` + `saved_loaded/verified/api/1.0`，两个 `*_verified_effective=true`，保存重载 true |
| 3 | 空装配/空零件预览的 `skipped_no_geometry` 依据（§3.4） | **一致** | 空零件 `a2a8a1a1…`、空装配 `32efcfd5…`：`empty_geometry_basis={feature_visit_code:0, non_datum_feature_count:0}`、`bytes=null`、`failed_step=null`、全部 raster code 为 null |
| 4 | 结构化最近候选边在精简回执中不被截断（§3.3） | **一致** | 失配 `712c6ffb…`：`nearest_edges` 5 条（id/endpoints_mm/endpoint_errors_mm）、`tolerance_mm=1e-6`、`candidate_limit=5`、`straight_edge_count=12`；compact 与 full **逐字段相同** |
| 5 | 过期 startup 快照是否仍宣称 ready/connected（§3.5） | **部分一致（兼容语义按设计保留，不改）** | 32 s 后 `stale=true`、`state=ready`、`connected=true`，但 `connection_verification="unverified_stale_snapshot"`、`current_connected=null`，message 明示"state/connected 只是上次验证" |
| 6 | BUG-115 同计划 `fill→trim→thicken` 准入 | **一致** | 提交前拒绝（`isError=true`、无 `job_id`、消息含 BUG-115 与两种替代），模型 revision 1→1；`fill→thicken` 允许并通过（4800 mm³、保存重载 true） |

## 3. 逐项实测

### 3.1 过期 startup 快照（§3.5）

`creo_startup_status` 两次只读调用，中间等待 32 s（`READY_FRESHNESS_SECONDS=30`），未触发 retry：

| 字段 | 首次 | 32 s 后 |
| --- | --- | --- |
| `state` / `connected` | `ready` / `true` | `ready` / `true` |
| `verified_at` | `2026-11-07T16:27:04.398904+00:00` | 同值 |
| `verification_age_seconds` | 0.006 | 32.020 |
| `stale` | false | **true** |
| `connection_verification` | `recent_snapshot` | **`unverified_stale_snapshot`** |
| `current_connected` | `true` | **`null`** |
| `message` | `Toolkit connection verified` | `Startup snapshot expired; current connection is unverified. state/connected describe the last verification only. Use creo_session_status for an explicit current check.` |

判定：反馈要求的"不要把过期快照当成实时连接"已经被三个字段（`stale`、`connection_verification`、`current_connected`）与文案覆盖；
但顶层 `state=ready` / `connected=true` 仍然逐字保留。这属于**门禁兼容语义**（`require_ready()` 与所有轮询客户端都以这两个字段判断可提交性），
把过期快照改成 `unknown` 会让空闲 30 s 后的会话立即拒绝所有提交，因此本轮**不改语义**，只记录建议：下游应改读 `current_connected`/`connection_verification`；
若确实需要更强约束，应另立条目设计"快照过期即需显式 recheck"的门禁，而不是只改字段。

### 3.2 空零件 / 空装配预览（§3.4）

| 用例 | job_id | model_id | 回执 |
| --- | --- | --- | --- |
| 空零件（`creo_new_part`） | `a2a8a1a185d945f2b2545bd100802b35` | `0f2c7e6ce46145ebb54a73d2d6dc7b45` | `preview.status=skipped_no_geometry`、`empty_geometry_basis={feature_visit_code:0, non_datum_feature_count:0}`、`path=null`、`bytes=null`、`file_verified=false`、`failed_step=null`、`failed_code=null`、12 个 raster code 全 `null` |
| 空装配（`creo_new_assembly`） | `32efcfd555dc4ca7bad2a2cfcefb68ba` | `f7f0c21bc95646388452c63c9af64c8e` | 同上 |

`datum_display` 在跳过路径上为 `model_type="unknown"/type_query_code=0/applicable=false/attempted=false`：捕获未开始，datum 隐藏/恢复确实没有执行，
这是"未尝试"而不是"查询失败"；`empty_geometry_basis.feature_visit_code=0` 证明 `ProSolidFeatVisit` 确实跑过并确认 `non_datum_feature_count=0`。
两份 job 都 `succeeded`、rev 1，且 `saved_file_reloaded_and_verified=true`（复核值见 [followup_full_compare.json](followup_full_compare.json)），预览跳过没有影响保存结论。

### 3.3 板厚两种上下文（§3.1）

钣金件 `9903555ab21c403893ee516b2bcda0cf`（`creo_new_sheetmetal template=native_planar`）：

| 用例 | job_id | feature_id | 体积 mm³ | `thickness_validation` | `thickness_loaded_validation` | 生效判据 | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 建壁 100×60×1 | `db391407c7674053bb1280ba7a8a0a3d`（rev 2） | 49 | 6000.0 | `verified` / `api` / `1.0` / `current_plan` | 不适用（非改型） | `thickness_verified_effective=true` | true |
| 改型 120×80 | `149d8ae7cdc84dc080c987dcb94dfb01`（rev 3） | 49（`feature_id_before=49`，`feature_id_unchanged=true`） | 9600.0 | `verified` / `api` / `1.0` / `current_plan` | `verified` / `api` / `1.0` / **`saved_loaded`** | 两个 `*_verified_effective` 均 true | true |

改型回执另有 `thickness_api_scope=body_api_readback_only`、`thickness_loaded_api_scope=body_api_readback_only`，`problems=[]`、`verified=true`。
`creo_get_job(detail=full)` 的 `result.planar_wall` 与 compact 的 `planar_wall` **37 个键、取值逐一相等**（[followup_full_compare.json](followup_full_compare.json) 的 `equal_to_compact=true`），未发生截断。
即：`thickness_verified`/`thickness_measured_mm` 仍只是 body API 回读，权威判据是 `thickness_validation`/`thickness_loaded_validation`，两者在同一回执里不再互相矛盾。

### 3.4 失败回执的身份与 loaded 字段（§3.2）

失败样本为真实几何失败（非故障注入）：改型到 `0.001 × 20 mm` 时，Creo 再生返回
`Regeneration produced a failed, suppressed or incomplete feature`，job `641490319ba1495c98e9d9cb89d55685`：

| 字段 | 值 |
| --- | --- |
| 终态 / 回滚 | `failed`；`rollback_succeeded=true`、`rollback_status="succeeded"` |
| `feature` / `feature_id` / `feature_id_before` | `null` / `null` / `null` |
| `feature_id_unchanged` | **`null`**（不再是 `true`） |
| `thickness_loaded_mm` / `thickness_loaded_validation` | `null` / `null` |
| `thickness_loaded_api_scope` / `_api_reason` / `_fallback_source` / `_verified_effective` | 全部 `null`（键存在，schema 稳定） |
| `thickness_validation` | **键不存在**（原生未读到任何 gauge，投影不伪造读数） |
| `verified` / `problems` | `false` / 5 条（无 feature id、尺寸不足、无方向、非钣金体、无可用长宽厚） |

判定：反馈 §3.2 指出的"无证据却声称未改变"已消失；成功语义不再出现在失败回执。模型 revision 在失败前后保持 3（`creo_list_models` 读回），
回滚有效。残留说明：`thickness_validation`（当前计划）在"根本没读 gauge"的失败里保持缺省，而不是显式 `null`——这与 `native_planar_wall.result_projection`
"缺失的回执属于旧执行器，不生成合成读数"的既有规则一致，且 `verified=false` + `problems` 已足以判定，故本轮不改；
若要求失败回执 schema 完全稳定，应由原生侧显式发一个 `unavailable` 回执，而不是 Python 端补造。

### 3.5 几何选边失配的结构化候选（§3.3）

`creo_sheetmetal_flange`，`edge_geometry` 端点 `[[1000,1000,1000],[1001,1001,1001]]`、`tolerance_mm=1e-6`，job `712c6ffbc4204957950341c2248e4f66`：

- 终态 `failed`，`failed_stage="execute_sheetmetal_flange"`，`failed_operation_index=0`；模型 revision 3→3，`rollback_succeeded=true`。
- `edge_geometry_diagnostic`：`straight_edge_count=12`、`tolerance_mm=1e-6`、`candidate_limit=5`、`nearest_edges` 5 条，每条含 `id`、`endpoints_mm`、`endpoint_errors_mm`：
  `id=96 [120,80,0]–[120,80,1]`（误差 1618.8885/1620.0006）、`id=87`、`id=60`、`id=93`、`id=89`。
- 同一 job 的 compact 与 full 的 `edge_geometry_diagnostic` **完全相等**（4 个键，`followup_full_compare.json` 的 `equal_to_compact=true`），失败 `message` 同时保留文本候选与修正指引。

### 3.6 BUG-115 准入（同计划 fill → trim → thicken）

在零件 `0f2c7e6ce46145ebb54a73d2d6dc7b45`（rev 1）上提交 5 个操作的同计划链，`creo_execute_plan` 在创建 job 前返回：

```
Error executing tool creo_execute_plan: operations[4].reference: thicken names quilt_feature
'h12_chain_trim' from operations[3], whose own target quilt 'h12_chain_base' is created in
operations[1] of the same plan; Creo returns ProFeatureGeomitemVisit(PRO_QUILT) -4 before the
fresh trim chain regenerates (BUG-115). Submit fill/trim first, then submit thicken in a second
plan referencing the existing quilt feature, or pass an explicit {kind:'quilt',id:N} read back
from creo_inspect_model.
```

`isError=true`、无 `job_id`、`creo_list_models` 的 revision 与 `part_sha256` 前后一致（1→1），无模型副作用。
随后提交被允许的 `sketch → surface_fill → thicken(quilt_feature=fill)` 同计划组合：job `e4d3a39f8ba244c38bd28e7e281ce686`
`status=succeeded`、revision 2、`volume_mm3=4800.0`（60×40×2）、`saved_file_reloaded_and_verified=true`，未被准入误伤。

## 4. 发现的缺陷与修复

- **产品缺陷：无**。6 项中 5 项完全一致；第 5 项（过期快照仍保留顶层 `ready/connected`）是已文档化的门禁兼容语义，不属于可安全收紧的回执缺陷，本轮只记建议。
- **驱动缺陷（已修）**：首轮 run `20261108T002341_239` 的 `bug115:allowed_volume` 失败，原因是驱动从 `result.volume_mm3` 取体积，
  而通用计划的体积在 `result.inspection.volume_mm3`（顶层字段为空）。修正读取路径后重跑得到 run `20261108T002653_283`（38/38 通过）；
  首轮报告保留在 `build/`（未纳入证据目录），不影响产品结论。
- 建议（未改代码）：① 下游用 `current_connected`/`connection_verification` 判断实时连接；② 失败 resize 若要完全稳定的 schema，
  由原生发 `unavailable` gauge 回执；③ 失败块的 `origin=[0,0]` 是缺失字段的既有默认（`_origin` 对 R10 之前执行器的兼容），在 `verified=false` 下不构成位置断言。

## 5. 构建与测试

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，`build/creo_worker.exe` SHA256 `3AC423DD…84E2CB` |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_feedback0174_status tests.unit.test_native_planar_wall tests.unit.test_edge_geometry_diagnostic tests.unit.test_surface_trim_schema -v` | 84 项，0 失败、0 错误 |
| `python -m ruff check tools/test_feedback0174_receipts.py` | All checks passed |
| `python -m ruff format --check tools/test_feedback0174_receipts.py` | 1 file already formatted |

本轮没有改动产品源码，因此没有新增产品单测；新增的只有离线可审阅的实机驱动。

## 6. 未验证范围

- 通道 busy、`unknown_outcome`、真实断流与保存失败未出现/未注入，不作为通过项。
- 过期快照只用"等待 32 s"制造（真实时间窗），未构造 Creo 已退出的极端现场；`retry` 分支未触发。
- 失败 resize 的触发方式是极小尺寸导致再生失败，不是 0.17.4 的 origin 跨轴体积守卫；后者的修复证据见 [FEAT-058-H01](../FEAT-058-H01-2026-11-07/SUMMARY.md)。
- BUG-115 的原生 -4 根因仍未确认；本轮只证明准入在真实 MCP 路径生效且替代组合可用。
- Creo 9/10、非 mm 单位、装配环境、WorkBuddy 黑盒未测；未验证其它同计划组合（join→thicken、trim→offset 等）。
