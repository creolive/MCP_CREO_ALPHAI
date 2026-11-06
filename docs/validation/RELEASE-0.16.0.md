# 0.16.0 发布记录（2026-11-06）

- 条目：[FEAT-014](../work-items/FEAT-014.md)（四壁盒子经 `miter_cuts` 建成、`adjacent_bend_ends` 改为显式放行）、[FEAT-004](../work-items/FEAT-004.md)（尺寸旧值/符号/归属守卫与 `set_dimensions` 两遍式），MINOR 性质；公开工具仍 **100**，无新增工具。
- 基线：上一已发布版本 **0.15.1**（`main` 提交 `2b57dd5`，标签 `v0.15.1`，见 [RELEASE-0.15.1](RELEASE-0.15.1.md)）。
- 开发分支：`codex/FEAT-014-miter-cuts`（合并提交前单个提交 `e3f7b66`，基于 `2b57dd5`）与 `codex/FEAT-004-dimension-guards`（`2c1276b` 守卫实现、`3d0c31c` live driver 与验收记录、`90d2c3e` rebase 记录，同样基于 `2b57dd5`）。两分支在 `v0.15.1` 之上合并，无垂直冲突；`docs/BACKLOG.md` 与工作卡状态行为并发修改，按主干最新口径并入 A02 实现说明。
- 目标版本：`v0.16.0`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在本次发布的 Release body 与交付说明中。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 原生编译 `python bridge.py build` | 退出 0，`build/creo_worker.exe` 重建（`native/advanced.cpp` miter 树与 `native/generic.cpp` 尺寸两遍式均生效） |
| 全量单元测试 `python tools/test_unit.py` | **2646 项通过**，0 失败 0 错误（0.15.1 起点 2624，本版新增 22 项：FEAT-014 schema/契约/守卫释放与 FEAT-004 17 项守卫回归）；`build/unit_test_report.json` |
| 语言与格式 `python tools/dev_check.py --skip-unit` | `success: true`（24 条 lint、12 个未格式化文件，均未高于 `style-baseline.json`） |
| 种子包 `python tools/package_seeds.py` | 24 文件、9 种子；两次确定性构建同为 SHA256 `472ea06440d35ff9e6c77f3e3ce9cba8263c255ffbe25563593e26d59e364c53`；`docs/seed_package.json` 回填后二次构建校验一致 |
| 源码包 `python tools/package.py --seed-archive …` | 见下方交付清单（摘要与 Release body 一致） |

源码身份：`version.py` = 0.16.0；`tools/dev_check.py` 受检源码指纹 `e60baa6396ab0696270a5eaeb0ae4c883fffb0f9f06bc59fb3b9daac501cbec8`，提交 `051a65a`（FEAT-004 合并提交）、工作区 `dirty=true`（版本元数据与版本说明尚未提交）。**最终受测提交以合入 `main` 的 0.16.0 提交为准**，附件由该提交源码生成。

## 实机证据（FEAT-014）

- 环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 与许可。
- 驱动：`tools/test_sheetmetal_box_live.py --live --confirm-session-usable`（单 Toolkit 通道、一墙一 job、不重试不排队）。
- 结果：底板 `N05_MITER_BOX_D274A9` 42 920 mm³（rev 1）→ 四道折边全部成功，revision 1→5，终态体积 106 499.16 mm³；四墙 `saved_file_reloaded_and_verified=true`；`four_walls_complete=true`、整体 `passed=true`。
- 报告：`build/post090_n05/20261106T163234_c086ae9d/report.json`（SHA256 `a83f6eea…`），同结果另有 `build/post090_n05/20261106T161949_61da6c2a/report.json`。
- 失败留档：GAP 型宽度/偏移被 Creo 重置为 `PARAM` 且值清零导致回滚的报告 `build/post090_n05/20261106T161433_254305b2/report.json`；改用 BLIND 后通过。

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| `miter_cuts` 入参与 schema | ✅ 已合入 | `FlangeMiterCuts`（width>0、offset≥0、拒绝 bool、默认 offset=width）；server 参数与 operation 透传；capabilities 与语法参考文案 |
| 原生 miter 元素树与回显 | ✅ 已合入（需重编） | `native/advanced.cpp` 写 `PRO_E_SMT_MTR_CUTS`（BLIND 数值）、回显核对、`extra["miter_cuts"]` |
| `adjacent_bend_ends` 放行语义 | ✅ 已合入 | 仅显式 `miter_cuts` 放行，默认拒绝不变；`adjacent_bend_ends_allowed=true` 与 `FLANGE_ADJACENT_BEND_ALLOWED` 日志 |
| 尺寸旧值/符号/归属守卫 | ✅ 已合入（需重编） | `dimension_guards.py`、schema 三字段、`native/generic.cpp` 两遍式、巡检归属与 `editable` |
| compact 投影白名单 | ✅ 已更新 | `job_projection._OPERATION_CRITERIA["sheetmetal_flange"]` 增 `miter_cuts`/`adjacent_bend_ends_allowed` |

## 未验证范围

- miter `width`/`offset` 与实际切除量的定量关系、角部间隙尺寸、不同板厚/折弯半径行为、删除或修改折边后的回滚。
- 自由端（无相邻折弯）带/不带 `miter_cuts` 体积差为 0，属空操作对照，不作为切角量证据。
- FEAT-004 rebase 后未重跑 `tools/test_adoption_dimension_guards.py --live`；2026-11-03 的 19 例属 rebase 前源码。
- Creo 10/9 未复测；WorkBuddy 黑盒未执行；BUG-001 会话边界继续适用。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.16.0-source.zip`、`MCP_CREO_MechDog-0.16.0-source.zip.sha256`、`MCP_CREO_MechDog-0.16.0-seed-library.zip`、`MCP_CREO_MechDog-0.16.0-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.16.0` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

种子包 SHA256：`472ea06440d35ff9e6c77f3e3ce9cba8263c255ffbe25563593e26d59e364c53`（24 文件、9 种子，内容除清单版本字段外未变）。源码包 SHA256 由最终提交源码生成，写入 Release body 与 `MCP_CREO_MechDog-0.16.0-source.zip.sha256`。

当前状态：**准备发布**（本文随 0.16.0 提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布交付说明。
