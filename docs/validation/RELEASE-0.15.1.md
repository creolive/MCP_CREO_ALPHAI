# 0.15.1 发布记录（2026-11-06）

- 条目：[BUG-111](../work-items/BUG-111.md)（`keep_original` 副本能力文案撤销旧建议、`failed_transform.selection` 模型计数改读巡检实际字段），PATCH 性质；公开工具仍 **100**，无新增工具、无参数语义变化。
- 基线：上一已发布版本 **0.15.0**（`main` 合并提交 `ce145fd`，标签 `v0.15.0`，见 [RELEASE-0.15.0](RELEASE-0.15.0.md)）。
- 本分支：`main`；合并提交 `670c54b`（将 `codex/BUG-111-doc-and-counts-fix` 的单个提交 `8798861` 合入 0.15.0 之后的主干）。该分支另有 README 段落改动与 0.15.0 改版后的 README 冲突，合并时按主干结构保留新版 README（旧版本段落已在 0.15.0 改版中移除），不改写其它文件。
- 目标版本：`v0.15.1`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在本次发布的 Release body 与交付说明中。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 原生编译 `python bridge.py build` | 退出 0，`build/creo_worker.exe` 重建（`native/placement.cpp` 取数改动生效） |
| 全量单元测试 `python tools/test_unit.py` | **2624 项通过**，0 失败 0 错误（起点 2616，新增 8 项）；`build/unit_test_report.json` |
| 语言与格式 `python tools/dev_check.py --skip-unit` | `success: true`（24 条 lint、12 个未格式化文件，均未高于 `style-baseline.json`） |
| 种子包 `python tools/package_seeds.py` | 24 文件、9 种子；两次确定性重建同为 SHA256 `a1a44ab3c7ad88e79829ef3248e678feb5760f4f57f49bc9da63616adcdc60b0`；`docs/seed_package.json` 回填后二次重建校验一致 |
| 源码包 `python tools/package.py --seed-archive …` | 见下方交付清单（摘要与 Release body 一致） |

源码身份：`version.py` = 0.15.1；`tools/dev_check.py` 受检源码指纹 `d483f10884a2693e202c50d9cd466eb6060ec2cda4ba945f00c23cb005ef31a1`，提交 `670c54b`、工作区 `dirty=true`（版本元数据与版本说明尚未提交）。**最终受测提交以合入 `main` 的 0.15.1 提交为准**，附件由该提交源码生成。

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| 对外文案撤销"≤4/批"建议 | ✅ 已合入 | 工具描述、`capabilities.py` placement 段、`REFERENCE_SYNTAX.md` 改为 0.11.7 定因口径；`tests/unit/test_transform_selection_diagnostics.py` 4 项文案护栏 |
| 选集诊断计数改读真实字段 | ✅ 已合入（需重编） | `native/placement.cpp` 改取 `features`/`surfaces`/`bodies` 数组长度与 `body_counts.active`，缺失记 `null`；4 项原生取数源码护栏 |
| 能力边界与兼容矩阵口径 | ✅ 已更新 | `docs/COMPATIBILITY.md` 0.11.7 段与本修正段标明随 0.15.1 发布，0.11.6 历史段标注被取代 |

## 未验证范围

- 本版未重跑 `tools/test_geometry_transform_copies.py` 实机；沿用的是 2026-11-03 同一原生逻辑的 C2/C4 实机记录（执行器 `cb6f3345…`、源码指纹 `7d0bc254…`），本版相对该分支只增删文案与取数字段。
- Creo 10/9 的副本行为与本修正的原生构建；"恰好重合 vs 部分交叠"的内核判据；`body_pattern` 未实现。
- WorkBuddy 黑盒未执行；BUG-108（`accepted_rigid=true` 9/9 未触发）与 BUG-110（`ack_success` 未实机发生）保持开放；BUG-001 的既有边界继续适用。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.15.1-source.zip`、`MCP_CREO_MechDog-0.15.1-source.zip.sha256`、`MCP_CREO_MechDog-0.15.1-seed-library.zip`、`MCP_CREO_MechDog-0.15.1-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.15.1` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

种子包 SHA256：`a1a44ab3c7ad88e79829ef3248e678feb5760f4f57f49bc9da63616adcdc60b0`（493 442 B 级别的同构种子包，内容除清单版本字段外未变）。源码包 SHA256 由最终提交源码生成，写入 Release body 与 `MCP_CREO_MechDog-0.15.1-source.zip.sha256`。

当前状态：**准备发布**（本文随 0.15.1 提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布交付说明。
