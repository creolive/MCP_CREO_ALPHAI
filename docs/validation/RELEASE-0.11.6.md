# 0.11.6 发布记录（2026-11-03）

- 版本：**0.11.6**（PATCH），`version.py` 唯一来源。
- 条目：[DEV-065](../work-items/DEV-065.md)（0.11.5 第十三轮反馈批 R13），关联 [BUG-108](../work-items/BUG-108.md)、[BUG-109](../work-items/BUG-109.md)、[BUG-110](../work-items/BUG-110.md)、[BUG-111](../work-items/BUG-111.md)。
- 版本说明：[RELEASE_NOTES_0.11.6.md](../RELEASE_NOTES_0.11.6.md)（已作为 Release 正文发布）。
- 标签：`v0.11.6` → 提交 `2d548dae042f6975b4dae8ebd43ecdec76a16c21`（`main`，合并提交 `DEV-065: R13 stability and failure closeout for 0.11.6`）。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.6>（`draft=false`、`prerelease=false`，发布 2026-11-03T06:07:38Z）。

## 附件

| 附件 | 大小（字节） | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.11.6-source.zip` | 7 399 315 | `e563f49a5ada4818cd192134aa30cd5f09692abd50bb276b9be1c5667dbf4257` |
| `MCP_CREO_MechDog-0.11.6-seed-library.zip` | 493 442 | `4f7019cf6d2a3fb31a8b184179a2c48e2cf6b5cc45b1d2667dd1baf14506edba` |

两份附件均由标签提交 `2d548da` 的源码构建；种子包摘要已回填 `docs/seed_package.json` 并在重建时复现一致（两次独立构建同为 `4f7019cf…`）。下载远端附件复核 SHA256 与本地构建逐字节一致。

## 构建与核验命令

```powershell
python tools/package_seeds.py --output build\dist\release\MCP_CREO_MechDog-0.11.6-seed-library.zip
python tools/package.py --seed-archive build\dist\release\MCP_CREO_MechDog-0.11.6-seed-library.zip `
    --output build\dist\release\MCP_CREO_MechDog-0.11.6-source.zip
git tag -a v0.11.6 -m "MCP_CREO_MechDog 0.11.6: R13 stability and failure closeout"
gh release create v0.11.6 <两个附件> --title "MCP_CREO_MechDog 0.11.6" --notes-file docs/RELEASE_NOTES_0.11.6.md
gh release download v0.11.6 --dir build\verify --clobber; Get-FileHash build\verify\*.zip -Algorithm SHA256
```

源码包内容核验：1263 个文件；不含 `native/constants.inc`、`jobs/`、`models/`、`build/`、`.venv/`、`toolkit.lock`、`session_activity.json`、`config.json`、`client-config.json`、`__pycache__`；含 `version.py`=`0.11.6`、`docs/RELEASE_NOTES_0.11.6.md`、`docs/validation/feedback-0.11.5-2026-11-03/MAPPING.md` 与 5 份原件。

## 验收摘要

- 离线：全量 **2241 项单测 0 失败/0 错误**、`tools/test_unit.py` `success=true`、`tools/dev_check.py --work-item 0.11.5-feedback-r13` 与 `--work-item DEV-065-release-0.11.6` 均 `success=true`、`bridge.py build` exit 0（执行器 13 323 776 B / SHA256 `0f5565049abfa9f16f742ca1e06c25f45e37670003b951a2093c8920905a64c1`，`build/source.sha256` = `cd22b5633159024d93907a20a3e62c3cd24cda930ef28025be64f290f3adf4c4`）。
- 本机 Creo 12.4.0.0 实机（`release_numeric=44`，用户当日授权启动会话）：四项夹具串行通过——阶段归因 3 作业各 13 个 `verify_stages` 且日志 13 行 `STAGE`；坐标草图 4 例 + 挤出成功（4 例 `rigid=false`）；装配失败作业 `failed` 后模型保持 `ready`，`ack_failure` 对 `ready` 被拒；225° 提交前拒绝并给 `-135`、单个 −135° 副本成功、5 op 与 7 op 批次均在 `operation_index=4` 失败（两轮复现）。详见各卡实机小节。

## 环境

Windows 11 x64 / PowerShell / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0 与匹配 Toolkit SDK / MSVC x64。

## 未验证范围

Creo 9 与 Creo 10 的本版构建与建模；WorkBuddy 黑盒验收；`ack_failure` 成功路径（实机只覆盖"对 `ready` 被拒"）；`accepted_rigid=true` 实机分支；真实 10 分钟停滞场景；第 5 个 `keep_original` 副本的根因（现象已在 12.4 复现，未定因）。

## 说明

本记录在标签之后补提交到 `main`（与以往版本一致）：标签指向 `2d548da`，记录本身不改变已发布附件。发布后未重建、未覆盖任何已发布资产。
