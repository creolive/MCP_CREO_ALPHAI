# 0.13.0 发布记录（2026-11-05，开发分支验收；发布未执行）

- 条目：[FEAT-039](../work-items/FEAT-039.md)（曲面链 S02/S03/S04/S05/S06/S08/S09/S10）+ W01 策略层；MINOR（功能批），公开工具 **99**（运行时 `creo_capabilities` 的 `tool_count=99`、`enabled_tool_count=99`，2026-11-05 实测）。
- 基线：实际已发布版本是 **0.12.1**（`docs/development/RELEASING.md`；标签 `v0.12.1`）。`0.12.2` 只是从未发布、从未打标签的预置号，本批含新增能力，按 MINOR 提升为 **0.13.0**（`version.py` = 0.13.0，README 与两份种子清单同步）。
- 本分支：`codex/DEV-067-alphai-plan`，基线提交 `1acf5a1ecbb5c815e0405d50c641b7f85da1fbce`。
- 目标版本：标签 `v0.13.0`、Release 与四份附件**尚未创建**。按 S10 规则，本次只被指派开发，故**未合并 main、未打标签、未上传、未发布**；合入发布需另行指派并按 `docs/development/RELEASING.md` 执行。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 全量单元测试 `python tools/test_unit.py` | **2420 项通过** |
| 语言与格式 `python tools/dev_check.py --skip-unit` | `success: true`，无新增回归 |
| 原生编译 `python bridge.py build` | 通过，`build/creo_worker.exe` 重建 |
| 实机 `--case chain_open` | 13/13，run `20261105-054951-149100` |
| 实机 `--case chain_closed` | 11/11，run `20261105-055037-085600` |
| 实机 `--case join` | 13/13，runs `20261105-055327-176100`、`20261105-055415-518700`（连续三次复跑稳定） |
| 实机 `--case sweep_surface` | 11/11，run `20261105-073051-135500`（开放 2400.000 mm²、加盖 4000.000 mm² 且闭合、实体化 15999.999999999998 mm³） |
| 实机 `--example examples/p12_surface_blade.json` / `examples/surface_trim_merge.json` | 各三阶段通过（修剪 800 → 600.000 mm²、加厚 committed、保存重载通过） |
| 种子包 | 24 文件、9 种子；确定性重建两次同指纹 SHA256 `e5808ff18049f94a74436636c6633b1867aa487224567dc31738c644c8ad685b`；`docs/seed_package.json`、`docs/seed_manifest.json`、`seed_library/seed_manifest.json` 三方一致 |

源码身份（本次检查）：`version.py` = 0.13.0；`tools/dev_check.py` 受检源码指纹 `a05ab16a9c612a3715f690fb299e4ee6161fa507347a637cafca669f2f1dfd05`；基线提交 `1acf5a1e`，工作区 `dirty=true`（本版改动尚未提交）；最终受测提交以合并到主干后的提交为准。

## 交付清单（逐项区分完成度）

| 条目 | 完成度 | 依据 |
| --- | --- | --- |
| S02 曲面修剪 | ✅ 实机公开 | `creo_surface_trim`，保留侧语义由实机测定 |
| S03 join | 🟡 **需求可测量、算子仍门禁** | trim+加厚给出 1400 mm² / 2800 mm³；`creo_quilt_merge` 四条原生路线均建出 4 个 `PRO_SURFACE`、0 个 `PRO_QUILT` |
| S04 投影曲线 | ✅ 实机公开 | `creo_project_curve`，实测 40.000 mm 与 25.133 mm |
| S05 曲面生成 | 🟡 **曲面扫掠实机公开、多截面放样仍缺** | 2400/4000 mm²、16000 mm³；`ProSweep.h` 只支持常量截面，本机无 `ProBlend.h` |
| S06 实体化判据 | ✅ 实机公开 | 体积 6283.185307179587 mm³（2000π）、开放面拒绝回滚 |
| S07 偏置 | ⛔ 门禁 | 12 个候选树全拒，thin trim 实测不移动切口 |
| S08 完整链路 | ✅ 实机 | 四条用例 + 两个可运行示例 |
| S09 模块化 | ✅ | `surface_ops` / `schema_base` 拆分，根目录纯兼容导出 |
| S10 集成与发布交付 | 🟡 **本记录 + 黑盒提示词已备，发布未执行** | 未合并 main、未打标签、未上传 |
| W01 端点焊接本体 | 🟡 **仅策略层（诊断/拒绝），本体未完成** | 配对规则与回执交付；epsilon 实测非重合容差，`weld` 被明确拒绝 |
| W02—W06 | ⚪ **未在本批复核** | draft/angle+offset/origin/extrude 回执与回归保持沿用既有实现，未补证、未复现 |

## 未验证范围

- 多截面放样/边界混合、单一合并 quilt、偏置：缺参照树或文档树，保持门禁（契约 §2.7/§2.8/§2.8c）。
- W01 原生受控焊接、端点残差读回与原案 gear10 体积基准。
- Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测；BUG-001 既有边界继续适用。
- WorkBuddy 黑盒验收未执行：提示词见 [WORKBUDDY-0.13.0.md](WORKBUDDY-0.13.0.md)（待执行）。

## 附件与远端核对

发布应有四个文件：`MCP_CREO_MechDog-0.13.0-source.zip`、`MCP_CREO_MechDog-0.13.0-source.zip.sha256`、`MCP_CREO_MechDog-0.13.0-seed-library.zip`、`MCP_CREO_MechDog-0.13.0-seed-library.zip.sha256`。发布后需逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.13.0` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致，再回填本节。

当前状态：**四附件已在本地构建并核对通过**（`python tools/check_release_assets.py --tag v0.13.0 --version 0.13.0 --dir E:\Projects` → “four assets present; both sidecars match their ZIP digests”）；种子包确定性指纹见上表，源码包摘要以发布运行重算并再次核对为准（本记录不预写源码包摘要，避免自指）。**未创建标签、未上传附件、未核对远端**——合入发布需另行指派并按 `docs/development/RELEASING.md` 执行。
