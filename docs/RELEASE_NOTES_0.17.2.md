# MCP_CREO_MechDog 0.17.2 版本说明

2026-11-07，PATCH：**实机验证批，无产品代码变更**。本轮在本机 Creo 12.4.0.0（匹配 SDK、Windows x64、单 Toolkit 通道串行）复跑六组既有条目的实机夹具，把证据回填到工作卡与台账；`version.py`、README、种子清单与版本说明同步递增。公开工具仍为 **100**，无新增/删除工具，无参数与行为变化。

## 本版内容

| 条目 | 本版结果 | 证据 |
| --- | --- | --- |
| [BUG-115](work-items/BUG-115.md) 同计划 fill→trim→thicken 准入 | 拒绝组 3/3 `refused_expected`（16 项检查 0 失败）；拆分路线 3/3 `ready`（13/13）；投影依赖组 3/3 `ready`（13/13） | `build/surface_save_recovery/20261107-021631-361600/`、`…-021652-068900/`、`…-021908-247700/` |
| [BUG-108](work-items/BUG-108.md) 刚体平移 `accepted_rigid` | 9/9 独立候选建成、保存重载 9/9；`detected=false`、`accepted_rigid=false`，目标分支仍未触发，卡保持开放 | `build/sketch_shift_batch.json` |
| [BUG-110](work-items/BUG-110.md) 装配失败 `ack_failure` | 零件/装配仍为零变更回滚（`part=guard_only`、`assembly=guard_only`），成功路径未发生；另记录一次 preflight 证据竞态（重跑通过） | `build/assembly_ack_failure_report.json` |
| [BUG-102](work-items/BUG-102.md) draft 失败复现 | 报告方夹具（chamfer 2 + round R3）两变体均成功：`flip=false` +352.044362 mm³、`flip=true` −353.263560 mm³，`-1` 仍未复现 | `build/bug102_draft/20261107T102821_d3493613/report.json` |
| [FEAT-004](work-items/FEAT-004.md) 尺寸守卫 | rebase 后实机 18/18 通过 | `build/acceptance_dimension_guards.json` |
| [FEAT-058](work-items/FEAT-058.md) R03 原壁矩阵 | 77 项检查 0 失败（100×60×1、185×232×1、同计划 `current_plan`、保存重载） | `build/planar_wall/20261107T023240Z/adoption_live.json` |

## 未验证范围

- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试，本轮不执行）。
- Creo 9（本机无 SDK）与 Creo 10 实机。
- BUG-108 `accepted_rigid=true` 分支（本机 12.4 求解器不产生平移）；BUG-110 `ack_failure` 成功路径（本机失败路径全部零变更回滚）；BUG-102 报告方 `ProFeatureWithoptionsCreate=-1`；BUG-115 原生 `-4` 根因。
- 其余需外部原件或设计前置的条目保持原状态，见[台账](BACKLOG.md)。

## 升级

本版不改动执行器、回调与注册配置，沿用当前安装即可；版本号用于标识证据基线。配套附件仍为源码包与种子包（种子内容未变，仅清单 `compatible_server_version` 同步为 0.17.2）。
