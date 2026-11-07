# MCP_CREO_MechDog 0.17.3 版本说明

2026-11-07，PATCH：**反馈修复批**。本轮把 [DEV-071](work-items/DEV-071.md) 的离线代码（源码提交 `22a3c62`、`d2f9601`、`f1826a2`、`c12f83d`，基于 0.17.1）合入主干，并附 BUG-032、FEAT-010、BUG-104、BUG-105、FEAT-056 五项本机实机验证证据。公开工具仍为 **100**，无新增/删除工具；变更集中在既有回执字段、更新检查语义与诊断文案。

## 本版内容

| 条目 | 本版结果 | 证据 |
| --- | --- | --- |
| [DEV-071](work-items/DEV-071.md) miter 回执公开投影 | `creo_get_job` 结果、紧凑/分段详情与历史任务（经 `aliases_ref` 回填 label/feature_id）都能看到 miter 回执；缺失字段保持 `null`，不臆造 | `src/creo_mechdog/operation_results.py`、`bridge.py` |
| [DEV-071](work-items/DEV-071.md) 更新检查 force/缓存语义 | `force=true` 跳过失败冷却立即重试；网络预算可配置（`MECHDOG_UPDATE_TIMEOUT_SECONDS`，1–30 秒，默认 5），单请求超时与总预算区分；回执报告 `network_timeout_seconds` 与可重试指引 | `src/creo_mechdog/update_check.py` |
| [DEV-071](work-items/DEV-071.md) 草图求解上下文 | 草图回执新增 `requested`/`used`/`selection_reason` 与 `stages.{initial_solve,retry_without_inference,autodimension,section_regenerate}`、`completed`、`recovered`；成功与失败操作都带同一结构，初始 `Solve=-1` 可重试时标记 `recovered` | `native/sketch_solver.cpp`、`native/generic.cpp` |
| [DEV-071](work-items/DEV-071.md) 再生失败特征状态 | 失败操作的 `failed_features` 投影包含有界的 `id`/`name`/`type`/`status` 样本及总数、截断标记；已删除目标不再被猜测 | `src/creo_mechdog/failure_context.py` |
| [DEV-071](work-items/DEV-071.md) offset 文案统一 | `offset` 参数说明与错误文案统一为同一表述；已交付功能不再重复登记 | `src/creo_mechdog/references.py`、文档 |
| [BUG-032](work-items/BUG-032.md) 钣金契约 | 实机 5 例体积误差 0；板厚回填 232/1；三组 frame；保存重载 `true` | `build/sheetmetal_contract/20261107T112023_c54bb010/report.json` |
| [FEAT-010](work-items/FEAT-010.md) 任意平面坐标草图 | `test_sketch_geometry_deviation --live` 仅 `prepared_only`；改用 DEV-048 矩阵实机：±Z 两例通过（800 mm³、COG 2,-10,5 / 2,10,-5、reload `true`），平行 `u_axis` 拒绝验证；`native_acceptance=partial` | `build/dev048_t04_plane_frame.json` |
| [BUG-104](work-items/BUG-104.md) 外观基线 | 剥离持久化 `appearance` 后预览 `present=false` 并建议 `refresh_baseline=true`；未刷新执行被拒；刷新后 `baseline_source=adopted_live`，revision +1 | `build/live_appearance_0173.json` |
| [FEAT-056](work-items/FEAT-056.md) 随机与标签键调色 | `random:true` 预览 `palette_source=random`、3 色互异，执行 revision +1，全部组件 `appearance=present`；组件标签键预览/执行均为 `family_label` | `build/live_appearance_0173.json` |
| [BUG-105](work-items/BUG-105.md) 零变更失败 | 组件放置失败（目标不存在）后回滚成功、revision 不变、状态保持 `ready`；`ack_no_mutation` 因无失败不可用；随后保存与调色均成功 | `build/live_bug105_0173.json` |

## 兼容性与接口

- 无新增/删除工具，无参数重命名；新增字段均为附加回执，旧客户端忽略即可。
- 新增环境变量 `MECHDOG_UPDATE_TIMEOUT_SECONDS`，缺省行为（5 秒）与旧版一致；非法值按缺省处理并保留在回执中。
- 原生执行器源码有变更（草图求解回执、miter 投影），升级需按 `bridge.py build` 重新编译。

## 门禁

- 短路径副本（`C:\Temp\md0173`，源码与本次提交一致）全量单测 **2741 项，0 失败、0 错误、2 跳过**。
- `tools/dev_check.py` 语言检查通过；独立复核通过。
- 种子包确定性构建两次同为 `983843ae55e36c8f2ce53939dd24561149098891e49e312f0f7ef90c041132af`，已回填 `docs/seed_package.json`。

## 未验证范围

- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试，本轮不执行）。
- Creo 9（本机无 SDK）与 Creo 10 实机；本版实机证据均来自本机 Creo 12.4.0.0。
- FEAT-010：仅验证右基准面 `u_axis=±Z`，其余基准方向与外部 Creo 10 未复现；驱动本身只生成 `prepared_only`。
- BUG-105：本机无法在不做故障注入的前提下制造派发前（连接/回调阶段）零变更失败；已用「派发后回滚成功」等价证据替代，`ack_no_mutation` 的失败态恢复路径仍未实机触发。
- 原生草图求解阶段码与 miter 投影需重新编译后在实机观察；本版只完成离线门禁与既有条目实机验证。

## 升级

1. 拉取本版本源码并执行 `python -m pip install --no-deps -e .`。
2. 执行 `python bridge.py build` 重新编译执行器（原生源码有变更）。
3. 重启 MCP 服务；如需调整更新检查网络预算，设置 `MECHDOG_UPDATE_TIMEOUT_SECONDS`（1–30，默认 5）。
