# 0.17.2 发布记录（2026-11-07）

- 条目：实机验证批，**无产品代码变更**。覆盖 [BUG-115](../work-items/BUG-115.md)、[BUG-108](../work-items/BUG-108.md)、[BUG-110](../work-items/BUG-110.md)、[BUG-102](../work-items/BUG-102.md)、[FEAT-004](../work-items/FEAT-004.md)、[FEAT-058](../work-items/FEAT-058.md) 的实机复跑与证据回填；公开工具仍 **100**。
- 基线：上一已发布版本 **0.17.1**（`main` 提交 `191c05f`，标签 `v0.17.1`，见 [RELEASE-0.17.1](RELEASE-0.17.1.md)）。
- 开发分支：`codex/0.17.2-live-verification`，基于 `191c05f`。
- 目标版本：`v0.17.2`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在 Release body 与本文件交付说明。

## 环境与身份

- 本机 Windows x64、Creo 12.4.0.0、匹配 Toolkit SDK 与许可；单 Toolkit 通道串行；用户 2026-11-07 明确授权直连 Creo。
- 会话由仓库 `creo_startup.launch_creo`（Explorer ShellExecute，规避 stdio 宿主的 KILL_ON_JOB_CLOSE 树）启动；`bridge.session_status` 返回 connected、toolkit 连接成功。
- 源码为 `191c05f` 加本轮文档/版本元数据改动（`dirty=true`），未改产品代码、原生源码与测试夹具。

## 实机证据

| 条目 | 命令 | 结果 | 报告（SHA256） |
| --- | --- | --- | --- |
| BUG-115 拒绝组 | `tools/test_surface_save_recovery.py --live --confirm-session-usable --case single_plan:independent_plane` | 3/3 `refused_expected`，16 项检查 0 失败 | `build/surface_save_recovery/20261107-021631-361600/report.json`（`dcd497ed…4ee9`） |
| BUG-115 拆分路线 | 同上 `--case incremental:independent_plane` | 3/3 `ready`，13 项 0 失败 | `…/20261107-021652-068900/report.json`（`e29571ab…239a`） |
| BUG-115 投影依赖组 | 同上 `--case single_plan:projected_dependency` | 3/3 `ready`，13 项 0 失败 | `…/20261107-021908-247700/report.json`（`57e32a1c…c732`） |
| BUG-108 | `tools/test_sketch_shift_batch.py --confirmed-session-usable` | 9/9 建成、重载 9/9；`detected=false`、`accepted_rigid=false`；`success=false`/`unverified` | `build/sketch_shift_batch.json`（`985f409d…5b0b`） |
| BUG-110 | `tools/test_assembly_ack_failure.py --confirmed-session-usable` | 零件/装配 `guard_only`、`unverified`；首轮证据竞态后重跑通过 | `build/assembly_ack_failure_report.json`（`b4c7919a…3e66`） |
| BUG-102 | `tools/test_draft_regression.py --live --confirm-session-usable` | 两变体成功；+352.044362 / −353.263560 mm³；`-1` 未复现 | `build/bug102_draft/20261107T102821_d3493613/report.json`（`d9fc2fb0…1224`） |
| FEAT-004 | `tools/test_adoption_dimension_guards.py --live --confirm-session-usable` | 18/18、`success=true` | `build/acceptance_dimension_guards.json`（`34e1752a…491a`） |
| FEAT-058 R03 | `tools/test_adoption_planar_wall.py --live --confirm-session-usable` | 77 项检查 0 失败、`passed=true` | `build/planar_wall/20261107T023240Z/adoption_live.json`（`cfcadd73…010b`） |

## 离线门禁

| 项目 | 结果 |
| --- | --- |
| `tools/test_unit.py` | **2726 项通过**，0 失败 0 错误；`build/unit_test_report.json` `success=true` |
| `tools/dev_check.py --skip-unit` | `success=true`；24 条 lint、12 个未格式化文件，与 `style-baseline.json` 存量相同；受检源码指纹 `594bf93d…8f57`（提交 `191c05f`、`dirty=true`，仅版本与文档） |
| `bridge.py build` | 退出 0，`build/creo_worker.exe` 复用/重建成功 |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；两次确定性构建同为 SHA256 `4ff0defb21fbeb019e6e1bca821eb96d38eafe385802f73ece8ecb2eca1384a7`；已回填 `docs/seed_package.json`，二次构建校验通过 |

## 未验证范围

- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试）。
- Creo 9（本机无 SDK）与 Creo 10 实机。
- BUG-108 `accepted_rigid=true`；BUG-110 `ack_failure` 成功路径；BUG-102 `ProFeatureWithoptionsCreate=-1`；BUG-115 原生 `-4` 根因。
- 其余需外部原件或设计前置的条目保持原状态，不据推测改代码。

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| 产品代码 / 原生 / 夹具 | 未改 | `git diff 191c05f..HEAD -- src native server.py bridge.py generic_bridge.py tools` 为空 |
| 文档与版本元数据 | 已更新 | 六张工作卡、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、`docs/development/RELEASING.md`、README、两份种子清单与 `docs/seed_package.json` |
| 版本号 | `0.17.2` | `version.py` |

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.17.2-source.zip`、同名的 `.zip.sha256`、`MCP_CREO_MechDog-0.17.2-seed-library.zip` 与同名的 `.zip.sha256`。逐个列出文件名上传，并用 `python tools/check_release_assets.py --tag v0.17.2` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

当前状态：**准备发布**（本文随 0.17.2 发布提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果在交付说明中回填。
