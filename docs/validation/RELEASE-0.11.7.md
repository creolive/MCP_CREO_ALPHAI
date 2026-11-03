# 0.11.7 发布记录（2026-11-03）

- 版本：**0.11.7**（PATCH），`version.py` 唯一来源；公开工具仍 **95 个**，无接口与参数语义变化。
- 条目：[BUG-111](../work-items/BUG-111.md)（第 5 个 `keep_original` 副本失败的定因与有界选集诊断）、[BUG-110](../work-items/BUG-110.md)（重放判据修正；成功路径仍开放）、[BUG-108](../work-items/BUG-108.md)（实机补证轮，未触发，仍开放）。实施计划：[R13 后续定因与实机补证](../superpowers/plans/2026-11-03-r13-followup-bug111-108-110.md)；验收摘要：[R13-FOLLOWUP-ACCEPTANCE-2026-11-03](../development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。
- 版本说明：[RELEASE_NOTES_0.11.7.md](../RELEASE_NOTES_0.11.7.md)（已作为 Release 正文发布）。
- 标签：`v0.11.7` → 提交 `c327dbe8b6aa0713fba05932e5ac493f672299ce`（`main`，合并提交 `BUG-111/108/110: R13 follow-up root cause round for 0.11.7`）。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.7>（`draft=false`、`prerelease=false`，发布 2026-11-03T10:19:16Z，`targetCommitish=c327dbe8…`）。

## 附件

| 附件 | 大小（字节） | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.11.7-source.zip` | 7 468 537 | `bbe50e8901b82a68032efc974d1877342a8a98c710be4403b436c538933cb8b7` |
| `MCP_CREO_MechDog-0.11.7-seed-library.zip` | 493 442 | `b9b0d6c27dc1c17ac6100904a684d7e8441aab2cc4c91f10b03a9d9d9958188e` |

两份附件均由标签提交 `c327dbe` 的源码构建；种子包摘要已回填 `docs/seed_package.json`（`compatible_server_version=0.11.7`）并在重建时复现一致（两次独立构建同为 `b9b0d6c2…`）。发布后下载远端附件复核 SHA256 与本地构建逐字节一致。

## 构建与核验命令

```powershell
python tools\package_seeds.py --output build\dist\release\MCP_CREO_MechDog-0.11.7-seed-library.zip
python tools\package.py --seed-archive build\dist\release\MCP_CREO_MechDog-0.11.7-seed-library.zip `
    --output build\dist\release\MCP_CREO_MechDog-0.11.7-source.zip
git tag -a v0.11.7 -m "MCP_CREO_MechDog 0.11.7: BUG-111 root cause and bounded selection diagnostics"
gh release create v0.11.7 <两个附件> --title "MCP_CREO_MechDog 0.11.7" --notes-file build\dist\release\RELEASE_BODY_0.11.7.md
gh release download v0.11.7 --dir build\verify\0117 --clobber; Get-FileHash build\verify\0117\*.zip -Algorithm SHA256
```

源码包内容核验：1274 个文件；不含 `native/constants.inc`、`jobs/`、`models/`、`build/`、`.venv/`、`toolkit.lock`、`session_activity.json`、`config.json`、`client-config.json`、`__pycache__`；含 `version.py`=`0.11.7`、`docs/RELEASE_NOTES_0.11.7.md`、两份 `seed_manifest.json` 与 `native/third_party/{json.hpp,LICENSE.nlohmann-json}`。

## 验收摘要

- 离线：全量 **2268 项单测 0 失败/0 错误**（起点 2264）、`tools/dev_check.py --work-item BUG-111-BUG-108-BUG-110-followup` `success=true`（风格基线未改；存量 lint/格式基线照旧，不宣称全库严格格式清零）、`bridge.py build` exit 0（执行器 13 328 384 B / SHA256 `7071b94780e08e77de7f626de964c43e0916d3f37445d1cedbd6e540ea250f3b`，`build/source.sha256` = `cc2aa38dcda16008e888f98196a0eace571b74e2bd338cd4341136da29f7dbe7`）。
  - 版本号提升后首次 `dev_check` 因 `docs/seed_package.json` 尚未回填而失败 10 项（种子闸门按设计拒绝），回填后复跑全绿——该失败是发布流程的中间状态，不是产品回归。
- 本机 Creo 12.4.0.0 实机（`release_numeric=44`，用户当日授权会话），发布轮复跑 `release_0117_reproduce.json`（C0/C2/C4/C6，最终执行器 `7071b947…`，源码指纹 `cc2aa38d…`）：
  - C0：225° 提交前拒绝（不建作业），单个 −135° 副本成功；
  - C2：index 4 失败，失败回执 `failed_transform.selection` = `requested_body_ids=[52]`、`selected_surface_count=26`（复制的是整个累积体），整批干净回滚、后续合法编辑成功；
  - C4：−135 在首位时 5 个副本全部成功；
  - C6：批 A 成功、批 B 首个 op（累计第 5 副本）失败——拆批不是变通。
  - 定因轮完整对照见 `build/r13_followup_20261103T161114/t1_reproduce.json` 与 `hypotheses.md`。
- 环境：Windows 11 x64 / PowerShell / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0 与匹配 Toolkit SDK / MSVC x64。

## 未验证范围

- Creo 9 与 Creo 10 的本版构建与建模（本机无 Creo 9 SDK，Creo 10 不要求独立复测）。
- WorkBuddy 黑盒验收。
- `accepted_rigid=true` 实机分支（本轮 9/9 候选未触发，保留外部补证）。
- `ack_failure` 成功路径的实机证据（本轮零件与装配均为零变更守卫，`coverage=guard_only`；重放判据修正仅由单测覆盖）。
- `keep_original` 复制**固定原件**的副本语义（现有实现复制整个当前体）；"恰好重合 vs 部分交叠"的内核判据。
- 第 5 副本问题的**行为修复**：本版只交付诊断与能力边界，未改建模行为。

## 逐 ID 状态核对（发布后）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-111 | 已定因（选集语义 + 重合/交叠再生失败），诊断已交付，未做行为修复 | 0.11.7 | Creo 10/9、内核判据、`body_pattern` 未实现 | [卡](../work-items/BUG-111.md) | [台账](../BACKLOG.md)（0.11.7 发布条目） | [说明](../RELEASE_NOTES_0.11.7.md) | [入口](../DEVELOPMENT.md) | [v0.11.7](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.7) |
| BUG-110 | 重放判据修正已交付；`ack_success` 实机未发生 | 0.11.7 | 零件与装配成功路径、幂等与不变性实机证据 | [卡](../work-items/BUG-110.md) | 同上 | 同上 | 同上 | 同上 |
| BUG-108 | 实机补证 9/9 未触发，`accepted_rigid=true` 无见证 | 0.11.7（补证轮，结论为"未验证"） | 默认阈值下真实刚性平移见证、Creo 10 复现 | [卡](../work-items/BUG-108.md) | 同上 | 同上 | 同上 | 同上 |

本版无新增公开能力，公开工具数 95 不变，**无 FEAT 卡需要同步状态**；`capabilities.py` 未改动。

## 相对上一正式包核对（上一版本：0.11.6，附件已从远端下载复核）

| 项目 | 上一版 0.11.6 | 本版 0.11.7 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | 2 个文件 | 2 个文件 | **逐字节一致**（CRLF→LF 归一化 SHA256 相同） |
| 回调指纹 / loader、callback 源码 | 未改动 | 未改动 | loader/callback 源码本版无变更，无需重新注册或迁移 |
| loader DLL SHA256 | `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9` | `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9` | 一致（本机 `build/creo_blend_loader.dll`） |
| callback DLL SHA256 | `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662` | `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662` | 一致（本机 `build/creo_blend_sync.dll`） |
| worker SHA256 | `0f5565049abfa9f16f742ca1e06c25f45e37670003b951a2093c8920905a64c1` | `7071b94780e08e77de7f626de964c43e0916d3f37445d1cedbd6e540ea250f3b` | **已变化**：`native/placement.cpp`、`native/generic.cpp` 增加只读诊断，升级后需重编执行器（worker 为子进程执行器，不涉及注册） |
| `protk.dat` / 注册表路径 | 本机未注册直接混合（`HKCU\Software\PTC` 下无 `protk`/`proto_k` 项） | 同左 | 无注册影响 |
| 实际注册影响 | — | — | **未变**（未改 loader/callback，无需重新注册、迁移或重启） |

## 说明

本记录在标签之后补提交到 `main`（与以往版本一致）：标签指向 `c327dbe`，记录本身不改变已发布附件。发布后未重建、未覆盖任何已发布资产；0.11.6 及更早的标签与附件保持原样。
