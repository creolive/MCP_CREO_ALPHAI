# 0.15.0 发布记录（2026-11-06）

- 条目：[DEV-069](../work-items/DEV-069.md)（0.13.0 四件外部反馈收口批），覆盖 R01—R12 的离线交付与 R09 第 3 项实机；MINOR 性质（新增 `creo_get_job(wait_seconds=...)` 只读长轮询，公开工具仍 **100**，无新增工具）。
- 基线：上一已发布版本 **0.14.0**（`main` 合并提交 `c774fa2`，标签 `v0.14.0`，见 [RELEASE-0.14.0](RELEASE-0.14.0.md)）。
- 本分支：`codex/FEAT-039-w02-w06-live`，基线提交 `7002575`，本批实现提交 `942e3f2`…`0f3e782`，发布提交见合入 `main` 的提交。
- 目标版本：`v0.15.0`、Release 与四份附件。按 0.13.0/0.14.0 的处理方式，最终发布 PR、合并提交、标签对象与附件远端核对结果记录在本次发布 PR 的交付说明中，不再向 `main` 追加提交。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 全量单元测试 `python tools/test_unit.py` | **2616 项通过**，0 失败 0 错误（`build/unit_test_report.json`） |
| 语言与格式 `python tools/dev_check.py` | `success: true`（24 条 lint 与 12 个未格式化文件均为 `style-baseline.json` 存量） |
| 原生编译 `python bridge.py build` | 退出 0，执行器重建 |
| R09 第 3 项实机 `python tools/test_sheetmetal_box_live.py --live --confirm-session-usable` | `passed=true`，run `20261106T145942_62f3136c`，报告 SHA256 `046702f2d2642697ec82e2d674de293821c02700b07a87e63e808072f18e1cf7`；自由首壁建成，第三壁 1 角/2 角均创建前拒绝，`trim_ignored` 复现 |
| 种子包 `python tools/package_seeds.py` | 24 文件、9 种子；两次确定性重建同为 SHA256 `0954faaad03e7373852320fca05206bcdb5610a26466ba02917c07446de4cabb`；`docs/seed_package.json` 记录校验通过 |

源码身份：`version.py` = 0.15.0；`tools/dev_check.py` 受检源码指纹 `ece9002cbe1faa5e5fd9178a6cfd853f739df5b3ea4fdfb8025bba18e4ec4618`，基线提交 `0f3e782`、工作区 `dirty=true`（版本元数据与版本说明尚未提交）；最终受测提交以合入 `main` 的提交为准。

## 交付清单

| 条目 | 完成度 | 依据 |
| --- | --- | --- |
| R01 [BUG-112](../work-items/BUG-112.md) 偏置初始化返回码 | ✅ 离线 | 初始化成功且句柄有效才测量，`source_area_status` 回执，失败数值 null；`/we4552` 编译门禁 |
| R02 [BUG-113](../work-items/BUG-113.md) 保存/回滚差异 | ✅ 诊断离线，根因开放 | `save_failure`/`rollback_difference`、终态矩阵与恢复指引；本机 12.4 未复现 |
| R03 [FEAT-058](../work-items/FEAT-058.md) 板厚双上下文 | ✅ 回执离线，实机未跑 | `thickness_validation`/`thickness_loaded_validation`；缺 API 几何兜底仅离线门控 |
| R04 [FEAT-023](../work-items/FEAT-023.md) compact | ✅ 离线 | 判据白名单、null 原样、列表 ≤50/≤32768 B、`full_detail_hint` |
| R05 [BUG-045](../work-items/BUG-045.md)/[FEAT-012](../work-items/FEAT-012.md)/[FEAT-008](../work-items/FEAT-008.md) | ✅ 契约离线 | schema 行向量公式、`rotation_convention`、`assembly_pose_receipt`、`failed_operation` |
| R06 [FEAT-001](../work-items/FEAT-001.md)/[BUG-091](../work-items/BUG-091.md) | ✅ 部分离线 | 启动重试身份/阶段/预算、health 分层、busy 立即返回；真实断连未验 |
| R07 曲面引用契约 | ✅ 离线 | 引用须来自当前 revision 并逐 op 重解析，旧 id/回显不作证明 |
| R08 [DEV-070](../work-items/DEV-070.md) 四附件闸门 | ✅ 离线 + 本记录使用 | 附件齐全、LF sidecar、SHA256 一致 |
| R09 [FEAT-014](../work-items/FEAT-014.md) 口径与实机第 3 项 | ✅ 实机第 3 项，**四壁仍 gated** | 第三壁 `adjacent_bend_ends` 创建前拒绝；`trim_ignored`；第 4—6 项 blocked |
| R12 [FEAT-007](../work-items/FEAT-007.md)/[BUG-109](../work-items/BUG-109.md) | ✅ 离线 | `wait_seconds` 只读长轮询；connect 前后 `STAGE` 计时 |
| R10/R11 | ⛔ blocked | origin 负坐标尺寸语义未解决；无新的 quilt merge/多截面放样路线证据 |

## 未验证范围

- R01 的 40×20/±5 mm 实机基准、量纲与已有实体保护；R02 的 Creo 10 外部现场与真实回滚失败。
- R03 缺 API 的原生几何兜底实机；R04 真实 stdio 字节核对；R05 原生装配回读；R06 真实断连/`-4`/挂起。
- R09 第 4—6 项；R10 首壁 origin 与计划内几何选边；R11 真实 quilt merge 与多截面放样。
- R12 的 through_all 实机矩阵、装配 bbox、erase 耗时、rename、managed delete。
- WorkBuddy 黑盒未执行；Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 独立复测按 2026-10-15 决定取消；BUG-001 既有边界继续适用。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.15.0-source.zip`、`MCP_CREO_MechDog-0.15.0-source.zip.sha256`、`MCP_CREO_MechDog-0.15.0-seed-library.zip`、`MCP_CREO_MechDog-0.15.0-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.15.0` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

当前状态：**准备发布**（本文随 0.15.0 提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布 PR。
