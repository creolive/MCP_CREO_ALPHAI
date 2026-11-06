# 0.14.0 发布记录（2026-11-06）

- 条目：[FEAT-039](../work-items/FEAT-039.md)（W05 `extrude_depth` 回执、W06 只读预览与失败编辑回滚、偏置 Thin 树复测），随附 [BUG-102](../work-items/BUG-102.md)、[BUG-094](../work-items/BUG-094.md)、[BUG-095](../work-items/BUG-095.md) 的发布后实机补证；PATCH 性质（公开工具仍 **100**，无新增工具）。
- 基线：上一已发布版本 **0.13.0**（`main` 合并提交 `d90d28e`，标签 `v0.13.0`，见 [RELEASE-0.13.0](RELEASE-0.13.0.md)）。
- 本分支：`codex/FEAT-039-w02-w06-live`，基线提交 `ceb25f8`，本轮提交 `04dcbd5`（W05/W06 为 `095b096`/`0744c07`）。
- 目标版本：`v0.14.0`、Release 与四份附件。按 0.13.0 的处理方式，最终发布 PR、合并提交、标签对象与附件远端核对结果记录在本次发布 PR 的交付说明中，不再向 `main` 追加提交。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 全量单元测试 `python tools/test_unit.py` | **2439 项通过**，0 失败 0 错误（`build/unit_test_report.json`） |
| 语言与格式 `python tools/dev_check.py` | `success: true`（24 条 lint 与 13 个未格式化文件均为 `style-baseline.json` 存量） |
| 原生编译 `python bridge.py build` | 退出 0，`build/creo_worker.exe` 重建 |
| W05 实机 `tools/test_t05_native.py --live --confirm-session-usable --section extrude-depth` | 2/2（省略深度 → 100 mm³；`depth=10` → 1000 mm³），`extrude_depth_receipt="passed"`，保存重载通过 |
| W06 预览实机 `tools/test_t07_preview.py --live --confirm-session-usable` | 三段全通过，run `20261106T004546_2a364d3b`，`preview_acceptance="passed"` |
| W06 回滚实机 `tools/test_failed_model_cleanup.py --live --confirm-session-usable` | 三场景全通过，run `20261106T004748_84fc913a`，已保存件失败编辑 revision 1→1 |
| 偏置 Thin 树探针（`build/_live_thin_trim_probe*.py`，不入库） | 厚度 5 → 700 mm²、10 → 600 mm²、x=2 → 760 mm²；`offset_side` 六种写法同结果；门禁保持 |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；两次确定性重建同为 SHA256 `eeb61ce748f583590902d365d9ee4ef82bfb4fddfe3584875a3c305716823101`；`docs/seed_package.json` 记录校验通过 |

源码身份：`version.py` = 0.14.0；`tools/dev_check.py` 受检源码指纹 `f13c35a5c00f9550553276befd37b37673ad39ac77ab90bd97dc2d9d6c5df37e`，基线提交 `04dcbd5`、工作区 `dirty=true`（版本元数据与版本说明尚未提交）；最终受测提交以合入 `main` 的提交为准。

## 交付清单

| 条目 | 完成度 | 依据 |
| --- | --- | --- |
| W05 `extrude_depth` 回执 | ✅ 实机 | `creo_extrude` 的 `depth`/`depth_type` 可省略，回执 7 键 frozen，`effective_*` 从特征树实读；14 项单测 |
| W06 只读预览入口 | ✅ 实机 | `creo_export_model(format="jpeg")` READ 作业，revision 不推进；三段预览通过 |
| W06 失败编辑回滚 | ✅ 实机 | 三个 cleanup 场景全通过；`unknown_outcome` 未做故障注入 |
| 偏置 Thin 树复测 | ✅ 复测完成，**门禁保持** | `offset_mm` 只对 quilt 工具生效且为"移除厚度带"，`offset_side` 无效；`capabilities.require_available` 继续拒绝两字段 |
| W02—W04 补证 | ✅ 实机 | BUG-102 双向拔模、BUG-094 基准面方向矩阵、BUG-095 草图 origin 矩阵 |

## 未验证范围

- W05 只执行 `--section extrude-depth`，未重跑完整 metric matrix；`through_all` 的 `effective_depth_mm=null` 仅单测覆盖。
- W06 预览图片内容需人工复核（`image_content_verification="human_review_pending"`）；`unknown_outcome` 按 BUG-001 恢复约定未注入。
- `surface_trim` 的 `offset_mm`/`offset_side` 仍门禁；是否按"移除厚度带"语义开放需单独决策（[G5 §2.7b](../development/G5-NATIVE-CONTRACT.md)）。
- S03 曲面合并仍门禁（四条原生路线建出 4 个 `PRO_SURFACE`、0 个 `PRO_QUILT`）；S05 多截面放样仍缺（Direct Blend 树抽取返回 -18）。
- 原始拔模 `-1` 反馈未复现；Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 独立复测按 2026-10-15 决定取消；WorkBuddy 黑盒未执行；BUG-001 既有边界继续适用。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.14.0-source.zip`、`MCP_CREO_MechDog-0.14.0-source.zip.sha256`、`MCP_CREO_MechDog-0.14.0-seed-library.zip`、`MCP_CREO_MechDog-0.14.0-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.14.0` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

当前状态：**准备发布**（本文随 0.14.0 提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布 PR。
