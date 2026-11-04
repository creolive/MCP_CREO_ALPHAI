# 0.12.2 发布记录（2026-11-04，预置）

- 条目：[FEAT-039](../work-items/FEAT-039.md)；MINOR，公开曲面修剪算子 `creo_surface_trim`，公开工具 97→**98**。
- 基线：本分支已合并 `codex/DEV-068-readme-release`（0.12.1），合并提交 `2afff21`；本版改动在其上。
- 目标版本：`version.py` = `0.12.2`。标签 `v0.12.2`、Release 与四份附件**尚未创建**，本条记录随之回填实际主干提交与远端核对结果；已发布标签与附件不覆盖。
- 状态说明：本记录是**发布预置**，不是"已发布"结论。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 全量单元测试 `python tools/test_unit.py` | 2353 项通过（291 s） |
| 语言与格式 `python tools/dev_check.py --skip-unit` | `success: true`；24 条基线 lint、13 个基线未格式化文件，无新增 |
| 原生编译 `python bridge.py build` | 通过，`build/creo_worker.exe` 重建 |
| 实机 P3 修剪（`build/_live_trim.py`） | Creo 12.4.0.0；`one` 700 mm²（外框 x∈[5,40]）、`two` 100 mm²（x∈[0,5]），面积与期望值一致，`saved_file_reloaded_and_verified=true` |
| 实机驱动（`tools/test_surface_chain.py --case trim --live --confirm-session-usable`） | `native_surface_trim="verified"`，jobs `247f76de…`、`7ae993e6…` |
| 种子包 | 24 文件、9 种子，确定性重建 SHA256 `044f1da0f78c52cf3fe11993486184063ceafac82615e77c28a02368f17ea2eb`；`--allow-record-mismatch` 回填后再构建摘要一致，`docs/seed_package.json` 与 `docs/seed_manifest.json`、`seed_library/seed_manifest.json` 三方一致 |

源码身份（本次检查）：`version.py` = 0.12.2；`tools/dev_check.py` 记录的受检源码指纹 `6ba60640bc56bced43ee22d8b19cdb918b16ef75a59c8dd773f6b8782ff1c149（2026-11-04 S04 消费者 / S06 实体化 / S07 偏置取证 / S09 模块化之后重算；发布运行仍会再算一次，以发布那次的值为准）65a1a9732`（基线提交 `30b7c36`，工作区 dirty=true，因本版改动尚未提交）；README 检出字节 SHA256 `7de83ed4924deb76814bc9d1cb176f095141b9a7eee478f2a9ed8a6a8146aab3`。最终受测提交以合并到主干后的提交为准。

## 未验证范围

- 修剪结果在保存重载后被 `thicken` 消费；质心判据（本机无 quilt 质心查询，`signed_offset_mm` 保持 null）；失败回滚的实机表现；`use_curve` 投影—修剪串联。
- `creo_quilt_merge` 仍为门禁状态（S03 实机 join 未做）；S04—S09 未开工。
- Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测；BUG-001 既有边界继续适用。
- WorkBuddy 黑盒验收未执行。

## 附件与远端核对

发布应有四个文件：`MCP_CREO_MechDog-0.12.2-source.zip`、`MCP_CREO_MechDog-0.12.2-source.zip.sha256`、`MCP_CREO_MechDog-0.12.2-seed-library.zip`、`MCP_CREO_MechDog-0.12.2-seed-library.zip.sha256`。发布后需逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.12.2` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致，再回填本节。

当前状态：未打包源码 ZIP、未创建标签、未上传附件、未核对远端。
