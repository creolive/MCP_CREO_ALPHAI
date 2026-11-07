# 0.17.3 发布记录（2026-11-07）

- 条目：[DEV-071](../work-items/DEV-071.md) 反馈修复批（PATCH），同批附 [BUG-032](../work-items/BUG-032.md)、[FEAT-010](../work-items/FEAT-010.md)、[BUG-104](../work-items/BUG-104.md)、[BUG-105](../work-items/BUG-105.md)、[FEAT-056](../work-items/FEAT-056.md) 实机验证；公开工具仍 **100**。
- 基线：上一已发布版本 **0.17.2**（`main` 提交 `e3ad431`，标签 `v0.17.2`，见 [RELEASE-0.17.2](RELEASE-0.17.2.md)）；DEV-071 离线代码基于 `191c05f`（0.17.1），本批在独立工作树先合入 `e3ad431` 再发布。
- 开发分支：`codex/DEV-071-feedback016-offline`；合入 main 前的代码与文档提交 `322989f41e6763481bc618749c2867db893ea3b8`（本记录随其后的文档提交进入同一发布）。
- 目标版本：`v0.17.3`、Release 与四份附件；合并提交、标签对象与附件远端核对结果在 Release body 与交付说明中回填。

## 环境与身份

- 本机 Windows x64、Creo 12.4.0.0、匹配 Toolkit SDK 与许可；单 Toolkit 通道串行；用户 2026-11-07 明确授权直连 Creo。
- 会话由仓库 `creo_startup.launch_creo`（Explorer ShellExecute）启动，工作目录 `build/creo_session`（`config.pro` 含 `protkdat`）；`bridge.session_status` 返回 connected。
- 离线门禁在短路径副本 `C:\Temp\md0173`（源码与提交 `322989f` 一致，仅替换本地 editable 指向与清除共享依赖目录里的旧 0.12.1 finder）执行；工作树原路径会因 Win32 路径长度限制使 `test_dev040_blackbox_fixture` 在临时文件上失败，属环境限制而非产品回归。
- `tools/dev_check.py --skip-unit`：`source.commit=322989f…`、`dirty=false`、`checked_source_sha256=fc128f5bb77e37a45294f7d8e9cc96354ae65ecb1758024bb675ebbd6e187a30`、`success=true`（24 lint / 12 未格式化，均为存量基线）。

## 代码变更（相对 0.17.2）

| 主题 | 位置 | 行为 |
| --- | --- | --- |
| miter 回执公开投影 | `src/creo_mechdog/operation_results.py`、`bridge.py`、`compact_sections.py` | 任务结果、紧凑/分段详情、历史任务（经 `aliases_ref` 回填 label/feature_id）可见 miter 回执；缺失字段保持 `null` |
| 更新检查 force/预算 | `src/creo_mechdog/update_check.py` | `force=true` 跳过失败冷却；`MECHDOG_UPDATE_TIMEOUT_SECONDS`（1–30，默认 5）控制网络预算，单请求超时与总预算区分并在回执报告 |
| 草图求解上下文 | `native/sketch_solver.cpp`、`native/generic.cpp` | `requested`/`used`/`selection_reason`、`stages.{initial_solve,retry_without_inference,autodimension,section_regenerate}`、`completed`/`recovered`；成功与失败操作同构 |
| 再生失败特征状态 | `src/creo_mechdog/failure_context.py` | `failed_features` 有界投影 `id`/`name`/`type`/`status` 与总数/截断标记；已删除目标不猜测 |
| offset 文案 | `src/creo_mechdog/references.py`、文档 | 参数说明与错误文案统一；已交付功能不再重复登记 |

## 实机证据（本机 Creo 12.4.0.0）

| 条目 | 命令 | 结果 | 报告（SHA256） |
| --- | --- | --- | --- |
| BUG-032 | `tools/test_sheetmetal_contract.py --live --confirm-session-usable` | 5 例体积误差 0、板厚 232/1、三组 frame、reload `true` | `build/sheetmetal_contract/20261107T112023_c54bb010/report.json`（`04a3b33c…f3e4`） |
| FEAT-010 | `tools/test_sketch_geometry_deviation.py --live …` → `prepared_only`；改跑 `tools/test_dev048_plane_frame.py --live …` | ±Z 两例通过（800 mm³、COG `2,-10,5`/`2,10,-5`、reload `true`），平行 `u_axis` 拒绝；`native_acceptance=partial` | `build/dev048_t04_plane_frame.json`（`9f9b7360…5e48`） |
| BUG-104 + FEAT-056 | 临时探针 `build/live_appearance_0173.py`（不入库） | 剥离基线后预览建议刷新、未刷新被拒、`baseline_source=adopted_live`、revision +1；`random`/`family_label` 两种 `palette_source` 均通过；15/15 检查 | `build/live_appearance_0173.json`（`3dc0812f…d979`） |
| BUG-105 | 临时探针 `build/live_bug105_0173.py`（不入库） | 不存在的组件触发失败、`rollback_succeeded=true`、revision 不变、状态 `ready`；`ack_no_mutation.available=false`；随后 save/recolor 成功；7/7 检查 | `build/live_bug105_0173.json`（`a0e40511…844d`） |

## 离线门禁

| 项目 | 结果 |
| --- | --- |
| `tools/test_unit.py`（短路径副本） | **2741 项通过**，0 失败 0 错误，2 项缺本地 SDK 配置跳过 |
| `tools/dev_check.py --skip-unit` | `success=true`；24 lint / 12 未格式化均在基线；指纹 `fc128f5b…7a30` |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；两次构建同为 SHA256 `983843ae55e36c8f2ce53939dd24561149098891e49e312f0f7ef90c041132af`；已回填 `docs/seed_package.json` |
| 独立复核 | 通过（见 [DEV-071 离线记录](../development/DEV071-OFFLINE-2026-11-07.md) 与工作卡） |

## 未验证范围

- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试）。
- Creo 9（本机无 SDK）与 Creo 10 实机；本版实机均为 Creo 12.4.0.0。
- FEAT-010：仅右基准面 `u_axis=±Z`；其余方向、倾斜面、编辑/重载保真与外部 Creo 10 未验；`test_sketch_geometry_deviation` 驱动本身只生成 `prepared_only`。
- BUG-105：不做故障注入的前提下无法制造派发前（连接/回调阶段）零变更失败；`ack_no_mutation` 的 `failed→ready` 恢复路径未实机触发（单测 9 项覆盖）。
- DEV-071 原生诊断（草图阶段码、miter 投影）需重新编译执行器后在实机观察；本版未重新运行原生建模回归，53mm 形变根因未动。

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| 产品代码 / 原生 / 夹具 | 已变更（DEV-071） | `git diff e3ad431..322989f --stat` |
| 文档与版本元数据 | 已更新 | README、`docs/DEVELOPMENT.md`、`docs/development/RELEASING.md`、`docs/BACKLOG.md`、六张工作卡、DEV-048、`docs/development/PENDING-2026-11-07.md`、本章节 |
| 版本号 | `0.17.3` | `version.py` |
| 种子清单 | `compatible_server_version=0.17.3` | 两份 `seed_manifest.json`、`docs/seed_package.json` |

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.17.3-source.zip`、同名的 `.zip.sha256`、`MCP_CREO_MechDog-0.17.3-seed-library.zip` 与同名的 `.zip.sha256`。逐个列出文件名上传，并用 `python tools/check_release_assets.py --tag v0.17.3` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

当前状态：**准备发布**；合并提交、标签、Release 链接与附件核对结果在交付说明中回填。
