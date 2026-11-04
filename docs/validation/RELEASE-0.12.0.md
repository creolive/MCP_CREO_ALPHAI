# 0.12.0 发布记录（2026-11-04）

- 版本：**0.12.0**（MINOR），`version.py` 唯一来源；公开工具 **95 → 97 个**，无破坏性接口变更。
- 条目：[FEAT-058](../work-items/FEAT-058.md)（原生矩形钣金首壁与就地改型）；契约说明：[FEAT058-PLANAR-WALL-CONTRACT](../development/FEAT058-PLANAR-WALL-CONTRACT.md)。
- 版本说明：[RELEASE_NOTES_0.12.0.md](../RELEASE_NOTES_0.12.0.md)（作为 Release 正文发布）。
- 标签：`v0.12.0`（注解标签 `4bbc55fc…`）→ 提交 `758e87e07ca6ac243125f24bf807656a99767615`（`main`，合并提交 `FEAT-058: native rectangular planar wall and in-place resize for 0.12.0`）。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.12.0>（`draft=false`、`prerelease=false`，发布 2026-11-04T04:36:58Z，`targetCommitish=main`）。

## 附件

| 附件 | 大小（字节） | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.12.0-source.zip` | 7 590 733 | `f18f543748a8e442d67c20e7002f9a1f2e3a09757f44d43ef437291b4b8288d5` |
| `MCP_CREO_MechDog-0.12.0-seed-library.zip` | 493 442 | `4385fa21bb49a42620479f89b8c51b94946c02d0f6e79281cab360807d339865` |

发布后用 `gh release download v0.12.0 --dir build\verify\0120 --clobber` 下载两份远端附件，`Get-FileHash -Algorithm SHA256` 与本地构建逐字节一致（源码包 `f18f5437…`、种子包 `4385fa21…`），与 Release body 记载一致。

种子包 24 个文件 / 9 个种子，摘要已回填 `docs/seed_package.json`（`compatible_server_version=0.12.0`），重建一次复现同一摘要。两份附件均由标签提交源码构建；发布后下载远端附件复核 SHA256 并回填本表。

## 构建与核验命令

```powershell
python bridge.py build
python tools\test_adoption_planar_wall.py --live --confirm-session-usable
python tools\dev_check.py
python tools\package_seeds.py --output build\dist\release\MCP_CREO_MechDog-0.12.0-seed-library.zip
python tools\package.py --seed-archive build\dist\release\MCP_CREO_MechDog-0.12.0-seed-library.zip `
    --output build\dist\release\MCP_CREO_MechDog-0.12.0-source.zip
git tag -a v0.12.0 -m "MCP_CREO_MechDog 0.12.0: native rectangular planar wall and in-place resize"
gh release create v0.12.0 <两个附件> --title "MCP_CREO_MechDog 0.12.0" --notes-file build\dist\release\RELEASE_BODY_0.12.0.md
gh release download v0.12.0 --dir build\verify\0120 --clobber; Get-FileHash build\verify\0120\*.zip -Algorithm SHA256
```

## 验收摘要

- 离线：全量 **2286 项单测** 0 失败/0 错误（`build/unit_test_report.json`，版本 0.12.0），含 FEAT-058 专项 18 项与三处复核反例回归；`tools/dev_check.py` `success=true`（`python_files_checked=328`、`cpp_files_checked=36`；存量 24 条 lint、13 个未格式化文件为既有基线，不宣称全库严格格式清零）；`bridge.py build` exit 0（执行器 13 403 136 B / SHA256 `9099e7f8825982d53de570d70cdcf04d276398f4bf6be66febc8b1f402a73a4f`，`build/source.sha256` = `ddf4717fea80a9c814e533c4bd63f630bf565271b15c36e3b5f77e4706451932`）。
- 平面壁驱动离线 20 项通过（`build/planar_wall/20261104T041850Z/adoption_offline.json`）。
- 本机 **Creo 12.4.0.0 实机**（用户本轮明确要求跑钣金发布回归；会话为已存在的本机会话），命令 `python tools\test_adoption_planar_wall.py --live --confirm-session-usable`，最终报告 `build/planar_wall/20261104T042412Z/adoption_live.json`，**67/67 检查通过**：
  - 创建 100×60×1：作业 `3014ae71…`，体积 6000 mm³，`feature_id=49`，`dimension_count=5`，包络 `u[0,100]/v[0,60]/n[0,1]`，`thickness_measured_mm=1.0`，`saved_file_reloaded_and_verified=true`；
  - 就地改型 120×80：作业 `295b5ea7…`，体积 9600 mm³，`feature_id_unchanged=true`，`thickness_loaded_mm=1.0`，保存重载 true；
  - `direction=negative`：作业 `b7ff19a7…`，6000 mm³，包络 `n[-1,0]`；
  - XZ：作业 `8186d511…`；YZ：作业 `f05fc68c…`；各 6000 mm³ 且 `verified=true`；
  - 方形 60×60 → 90×60：3600 mm³ → 5400 mm³，改型保持同一 feature id，`square` 由 true 变 false；
  - 下游依赖：原生壁挂折边（`edge_id=59`）后改型在建模前被拒；
  - 原生拒绝回滚：作业 `84ba8c40…` 在实体零件上失败（`ProMdlSubtypeGet=0`），revision 不变，随后旧 `sheetmetal_wall` 首壁成功 42920 mm³；
  - 旧首壁+折边链路：42920 → 47178.64 mm³，`flange_saved_reload=true`。
- **过程披露**：首轮实机（`build/planar_wall/20261104T041859Z/`）在三项检查上失败，根因是作业 `d580ff17…` 在 `connect_creo` 以 `-38` 连接失败（`failed_stage=connect`、`operations[0].effect_status=no_effect`，未执行任何建模操作），后续 YZ 与下游场景因此连带失败；会话仍响应（`parametric`/`xtop` 均 `Responding=True`）后重跑一次即 67/67 全过。该失败属会话连接问题，**不是本版建模回归**，但说明本机会话连接仍有偶发 `-38`，与本版无关，保持 BUG-001 既有结论。
- 环境：Windows x64 / PowerShell / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0 与匹配 Toolkit SDK / MSVC x64。

## 未验证范围

- 非矩形与多环截面首壁；四壁与第二折边（受 FEAT-014/corner relief 限制）。
- `plane` 传显式支撑面并覆写 origin。
- Creo 9 与 Creo 10 的本版构建与建模（本机无 Creo 9 SDK；Creo 10 不要求独立复测）。
- WorkBuddy 黑盒验收。
- 实机 `-38` 连接失败的根因（沿用 BUG-001 结论，未做新的故障注入）。

## 逐 ID 状态核对（发布后）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEAT-058 | 已发布：原生矩形首壁 + 就地改型，判定块随 job 结果发布；复核 6 项与复核记录 3 处已整改 | 0.12.0 | 非矩形/多环截面、四壁与第二折边、显式支撑面 origin、Creo 9/10 实机、WorkBuddy 黑盒 | [卡](../work-items/FEAT-058.md) | [台账](../BACKLOG.md)（FEAT-058 行） | [说明](../RELEASE_NOTES_0.12.0.md) | [入口](../DEVELOPMENT.md)（2026-11-04 发布条目） | [v0.12.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.12.0) |

公开工具 95→97（`creo_sheetmetal_planar_wall`、`creo_resize_sheetmetal_planar_wall`），`capabilities.py` 已随 FEAT-058 更新 sheetmetal 能力块。

## 相对上一正式包核对（上一版本：0.11.7，附件已从远端下载复核）

| 项目 | 上一版 0.11.7 | 本版 0.12.0 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | `json.hpp` 953 436 B / `aaf127c0…`；`LICENSE.nlohmann-json` 1 076 B / `46a65cff…` | 同左 | **逐字节一致**（`git diff origin/main` 无变更） |
| 回调源码（`blend_sync.cpp`、`blend_loader.cpp`、`callback_*.h`） | 未改动 | 未改动 | 源码本版无变更 |
| loader DLL SHA256 | `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9` | `098efef331d0a3c100b629f5e20fe50969fdd29205fa369342a53851dc2cf209` | **本机字节变化来自重新编译**（ABI/设置指纹变化触发重建），源码未变；本机未注册 loader，无注册影响 |
| callback DLL SHA256 | `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662` | `56c30894fc6521d26ee9eaca126f49ecccc577f37d77d9a10f56572cc23ff7c1` | 同上（重新编译，不是源码变更） |
| worker SHA256 | `7071b94780e08e77de7f626de964c43e0916d3f37445d1cedbd6e540ea250f3b` | `9099e7f8825982d53de570d70cdcf04d276398f4bf6be66febc8b1f402a73a4f` | **已变化**：新增 `native/planar_wall.{h,cpp}` 与 `native/generic.cpp` 分发；worker 是子进程执行器，升级后需重编 |
| `protk.dat` / 注册表路径 | 本机直接混合，无 `protk` 注册 | 同左 | 无注册影响 |
| 实际注册影响 | — | — | **未变**：未改 loader/callback 源码，本机不注册；如其他环境注册过 0.11.x 的 loader，重编后请重新注册 |

## 源码包内容核验

源码包 1301 个文件：含 `version.py`=`0.12.0`、`docs/RELEASE_NOTES_0.12.0.md`、`docs/validation/RELEASE-0.12.0.md`、两份 `seed_manifest.json`（`compatible_server_version=0.12.0`）、`native/planar_wall.{h,cpp}`、`src/creo_mechdog/native_planar_wall.py` 与 `native/third_party/{json.hpp,LICENSE.nlohmann-json}`；不含 `native/constants.inc`、`build/`、`jobs/`、`models/`、`.venv/`、`config.json`、`client-config.json`、`toolkit.lock`、`__pycache__`。

## 说明

本记录在标签发布后按项目惯例回填最终字段（标签指向、Release 链接、附件大小与 SHA256、逐 ID 的 Release 列），回填以单独提交进入 `main`；已发布的标签与附件不再改写。0.12.0 源码包与种子包成对发布，0.11.7 及更早的标签与附件保持原样。
