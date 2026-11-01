# 0.11.0 发布验证记录

日期：2026-11-01。版本入口 [version.py](../../version.py)（`VERSION = "0.11.0"`）、[版本说明](../RELEASE_NOTES_0.11.0.md)、[开发入口](../DEVELOPMENT.md) 与[主台账](../BACKLOG.md)（FEAT-052 行）随版一致。本版为 **MINOR**：FEAT-052 装配按零件族上色，公开工具 94→95。发布后补记：以下各节为已核对的终值（2026-11-01 发布当日回填）。

## 交付提交与标签

- 开发分支 `codex/FEAT-052-assembly-recolor`（基于 main `89ee542`）：`7f944ad`(台账文档)→`b3db096`(Python 侧)→`1d37aff`(原生侧)→`c68beb2`(离线证据回填)→`3c4fa9d`(原生迭代器下标修复)→`e9ddc6d`(结果投影透传回滚核验)→`b21dbb6`(驱动夹具修正)→实机证据提交→0.11.0 版本准备提交。
- 主干提交：`262ef204b235fbee7c261256d6f7f664300e25db`（`main`，快进合入自 `codex/FEAT-052-assembly-recolor`，远端 `89ee542..262ef20` 已核对一致）。
- 附注标签：`v0.11.0`（标签对象 `09114c7d91386fac34d88e4d3074d817c8aecdf2`，经 API 剥离后指向 `262ef20`，远端已核对）。

## 本机实机验收（FEAT-052）

环境：Windows x64、Creo Parametric 12.4.0.0（parametric 9140 / xtop 7072 / nmsd 9792 / pro_comm_msg 19684，2026-11-01 12:57:53–12:58:00 本地创建）、匹配 Toolkit SDK 与许可、MSVC。会话准入按 BUG-001/BUG-091 四门槛逐项核对：本轮用户指派后经 `creo_startup.py` 受限 Explorer/PSF 路径**仅请求一次**启动；GUI 核验（xtop 唯一可见顶层窗口 "Creo Parametric 12"、`IsHungAppWindow=false`、无模态/警告弹窗、四进程 `Responding=True`）；唯一 E 盘 dev 客户端（C 盘旧项 disabled）、无并行构建/活动 worker/未终态作业，工作树 `jobs/`/`models/` 空；历史 unknown 保护原样保留未触碰；驱动 `wait_for_startup` 实测 `startup=ready/connected=true` 后才提交。

构建身份：分支工作树 `c68beb2`+三项修复（`3c4fa9d`/`e9ddc6d`/`b21dbb6`，内容与受测时一致）；native `build/source.sha256=f7affbcb…8e36ecbc`（R3/R4 轮）、worker SHA256 `00730F45…`（R1/R2）/`1FD68071…`（R3/R4）。

| 轮次 | 报告（build/ 本机生成物） | 结果 |
| --- | --- | --- |
| R1 `20261101T050234Z74ca4441` | 14 作业全成功、3 检查过 | 驱动"失败计划 1"三成员显式族表被生产端**正确拒绝**（is_error、未建作业、revision 不变）——"族表必须完整覆盖"契约的活体证据；驱动修正（`b21dbb6` 之一） |
| R2 `20261101T051854Z4ebece26` | 失败计划 1 全过（9 检查） | round A 作业 `f4d0d50c` 在 `save_and_reload` 阶段 `[json.exception.invalid_iterator.208]`——`native/appearance.h` 两处对 `find()` 迭代器误用下标，修复 `3c4fa9d` |
| R3 `20261101T053544Z61515f3a` | 23 检查、1 项失败 | 失败计划 2 原生侧回滚核验 80/80 通过但顶层 `result.recolor` 投影丢弃 `rollback_appearance_verified`（修复 `e9ddc6d`，+2 单测）；驱动 `component_placement` 多带 `placement` 字段被 schema 拒绝（修复 `b21dbb6`） |
| R4 `20261101T060336Z558b3546` | **28/28 检查通过、退出码 0** | 见下 |

R4 清单：12 源件创建+保存重载 true；80 组件装配；初始全 absent；失败计划 1（全量自动分族上色→双 remove 原生失败→回滚恢复"无组件外观"，80 条 absent 基线、身份/组件数恢复）；round A 自动分族 80 painted 无 unmatched、12 族计数与建议包一致、保存擦除重载前后读回 ≤1e-6、revision+1；round B 显式族表+合族、round C 第三色板；失败计划 2 回滚到 round A 颜色（`rollback_appearance_verified=true`）；`component_placement` 移动 c01 后保存、全员保色、仅 c01 位姿变化、体积不变、保存重载 true；12 源零件 SHA256 各阶段不变。目视确认：`visual_check.png`（截屏存档）+ 视觉核验约 8–12 种可辨实色族、网格规整、无弹窗。

针对性回归：`tools/test_assembly_pipeline.py --session-health-verified`（两跑均 success=true；13 断言、10 作业全 succeeded；报告 `build/assembly_pipeline_live_20261101T061539Z75cf1bfe/report.json`）；`tools/test_t07_preview.py --live --confirm-session-usable`（`preview_acceptance=passed`，7 例、`empty_part` 预览按预期 `skipped_no_geometry`；报告 `build/t07_preview_feat052_regress_20261101.json`）。

离线检查：`tools/dev_check.py` success=true（单元 **1814/1814** OK=基线 1812+2 新增投影锁定；0 新增语言/格式回归）；`clang-format 23.1.3 --dry-run --Werror native/appearance.h` 通过。

## 未测范围（保持开放）

WorkBuddy 纯 MCP 黑盒未执行；busy/并发通道交错未做实机；`dry_run` 分页/游标失效、非法输入拒绝、读回故障注入属离线范围；Creo 9 本机无 SDK、实机编译与建模运行时未验收；Creo 10 独立复测不作为门槛；本机通过不外推其他环境；BUG-091 根因未定，实机准入纪律持续有效。

## 附件与远端核验

正式 Release（`draft=false`、`prerelease=false`）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.0 （Release id 430412112；正文直接列两 ZIP 文件名与完整 SHA256）。种子包确定性三建同哈希（工作树双建 + 主干重建）；源码包以 `--seed-archive` 成对生成（1126 文件）。四附件均从远端逐件下载核对：

| 附件 | 远端字节数 | 下载后 SHA256 | 核验 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.11.0-source.zip` | 6 734 245 | `d657c845d6164b99ad20d960cc9659ac6f44c91f6490ab82f57e2f6a2b76477a` | 通过（与本地构建同哈希） |
| `MCP_CREO_MechDog-0.11.0-source.zip.sha256` | 101 | 内容为 `d657c845…477a  MCP_CREO_MechDog-0.11.0-source.zip` | 通过（指向源码包哈希） |
| `MCP_CREO_MechDog-0.11.0-seed-library.zip` | 493 442 | `3d922e0ec6185a624f3e85155651d0b62c94c66ac89e9bc40da9949423b213cf` | 通过（确定性三建同哈希，24 文件 9 种子） |
| `MCP_CREO_MechDog-0.11.0-seed-library.zip.sha256` | 107 | 内容为 `3d922e0e…13cf  MCP_CREO_MechDog-0.11.0-seed-library.zip` | 通过（指向种子包哈希） |

远端核对还包括：`refs/heads/main` = `262ef20`、`refs/tags/v0.11.0` 标签对象剥离后指向同一提交、Release 正文包含两完整 SHA256、四附件 `state=uploaded`。本机生成物原件（报告/截屏/校验文件）在 `build/assembly_appearance_live_20261101T060336Z558b3546/` 与 `E:\Projects\MCP_CREO_MechDog-release-0.11.0\`（仓库外），不入库。
