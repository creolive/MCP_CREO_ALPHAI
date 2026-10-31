# Release 0.8.5 发布验收记录

日期：2026-10-29（Asia/Shanghai）。版本与条目：0.8.5，[DEV-051](../work-items/DEV-051.md) 及关联 BUG-047、BUG-046、FEAT-014、BUG-040、FEAT-023、FEAT-008、FEAT-035、FEAT-031。折边方向语义变更与新增拒绝码属于 MINOR 性质；依本次指定编号发布为 0.8.5。公开工具仍 94 个。本文件随候选源码打包，源码包 SHA256 与发布后远端对象的完整值以 Release body 和最终交付报告为准，避免源码包自指。

## 源码与环境

开发分支 `codex/dev051-feedback070`，候选起点 `29a3df8`；实机证据由此前各提交及当轮工作区产生，不能用最终发布提交冒充实机受测指纹。各轮真实提交、dirty 状态、job/model、报告及环境见 [T03](../development/DEV051-T03-ACCEPTANCE.md)、[T04](../development/DEV051-T04-ACCEPTANCE.md)、[T05](../development/DEV051-T05-ACCEPTANCE.md)、[T06](../development/DEV051-T06-ACCEPTANCE.md)、[T07](../development/DEV051-T07-ACCEPTANCE.md)、[T08A](../development/DEV051-T08A-ACCEPTANCE.md)、[T08B](../development/DEV051-T08B-ACCEPTANCE.md)、[T09A](../development/DEV051-T09A-ACCEPTANCE.md)、[T09B](../development/DEV051-T09B-ACCEPTANCE.md)、[T11](../development/DEV051-T11-ACCEPTANCE.md)、[T12](../development/DEV051-T12-ACCEPTANCE.md)、[T13](../development/DEV051-T13-ACCEPTANCE.md)。

已取得的实机环境为本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK。本次发布不新连 Creo、不使用 WorkBuddy；Creo 9 本机无 SDK，Creo 9 编译与运行时未验，Creo 10 未独立复测。

## 实机结论与边界

- T03 首壁五组在 0.8.4 修复后通过，体积 42 920 / 42 920 / 185 / 370 / 92.5 mm³，保存重载通过。T02 4/4、T06 9/9、T07 3/3、T08A 4/4 为 0.8.3 指定证据；本版没有重跑。
- 折边方向改由 `PRO_E_SMT_FLANGE_SEC_FLIP` 控制：`flip=false` 默认从选中面向外，`flip=true` 反向。两例均 +18 025.29 mm³、Z 增长 79 mm，保存重载核验。升级调用方须复核选面和方向。
- 四壁 2/4；第三道 `f_ny` 返回 `-1`、regen failed、`effect_status=rolled_back`。`relief` 仅接受并回显，已成功两道与无释放逐位相同，无可观测去料。
- T04 钣金体并入式 add 重叠与非重叠均 `-1`、元素错误为空；`new_body=true` 独立实体 +500 mm³。新增建模前拒绝码 `SHEETMETAL_SOLID_ADD_UNSUPPORTED`，拒绝后驱动 5/5；普通件 add +400、钣金 cut −100。支持边界见 [兼容说明](../COMPATIBILITY.md)。
- T08B 5/5、T09A 4/4、T09B 3/3、T12 3/3；T09B 单条用户中心线时 `section_centerline_count=3` 为新缺陷，T12 的 180° 按契约拒绝。
- T13 **不通过**：导出 `complete=false`、`files=1`、`missing=2`，巡检名 `▩C_...0001` 与磁盘名 `c_..._0.prt.1` 不同源；回导 `SESSION_NAME_CONFLICT`。不得视为 bundle 验收通过。

四壁 4/4、relief 几何、T13 bundle、T05/T06 原件及其他各卡列明的未测分支保持开放。

## 离线检查与分发

种子清单两份均为 0.8.5。`tools/package_seeds.py` 连续两次及回填 `seeds.py expected_digest` 后第三次均为 24 文件、9 种子、SHA256 `4178f8aaa0509653915a8238374696358739c140c3a6d7a442dc0491daec53a8`。

`.venv\Scripts\python.exe tools\dev_check.py`：exit 0，`success=true`、`unit_tests=passed`，0 失败、0 错误；`source.commit=29a3df88aa47be9c819baa75a34a0507ba64a9d3`、`dirty=true`、`checked_source_sha256=f22e6c2da4d788a3434a867e9e1590d4fc0b632babb87c883c3e3e1e8bd5a0ff`、`native_validation=not_run`。存量风格摘要为 30 lint、16 个未格式化文件，不能宣称严格全库格式通过。

`.venv\Scripts\python.exe tools\package.py` 在同一候选树上重复构建，两次 1048 文件、SHA256 一致；源码 ZIP 解压到新目录后 1048 文件、ZIP 完整性通过，禁入路径 0，许可证及配置模板俱全。正式附件在本卡定稿后从同一树重建，完整哈希列入 Release body，避免本卡自指。

相对 0.8.4 正式源码包，`native/third_party` 两个文件原字节一致：`json.hpp` SHA256 `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`，第三方许可 SHA256 `b9715282b2f1db1359a919bb3a542dd4362fd9e38ae72d421367eb11abe62eec`。按 `sha256-repo-lf-v1` 的 CRLF→LF 口径，回调及 loader 的五份依赖源码逐项一致（`blend_sync.cpp`、`blend_loader.cpp`、`callback_identity.h`、`callback_api.h`、`json.hpp`）。完整回调指纹还依赖本机 ABI 和配置，本次未重算；DLL 二进制与实际 `protk.dat` 注册路径不在正式源码包内，本轮未核对，也不能据源码一致推断运行中注册状态。本次不连接 Creo。正式源码包及种子包完整 SHA256 列于 Release body；发布后逐件下载和远端 main、标签、Release 核验记录留在本机交付副本与最终报告，不在发布后新增 main 提交。

## 候选状态与逐 ID 核对

发布前候选状态：待核对主干提交、附注标签、正式 Release 与四附件；DEV-051 整体仍验收中，BUG-046 的钣金 add 边界已定案，BUG-047 的方向子项已验，FEAT-014 四壁和 relief 仍开放，FEAT-031/T13 失败仍开放。状态入口为 [工作卡](../work-items/DEV-051.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.5.md)和[开发入口](../DEVELOPMENT.md)。实际发布结果见下节。

## 发布后远端核验（本机交付副本；不追加 main 提交）

2026-10-29 从 REST API 核对：远端 `main=4ffdd5d9907afe719c174c234df765664dc04f7f`；附注标签 `v0.8.5` 对象为 `74917557028a028ed69e78589cc0e5e39a0ab4a9`，剥离后指向同一提交。正式 Release（`draft=false`、`prerelease=false`）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.8.5 。四附件均逐件从远端下载，字节数、SHA256 与 Release body 一致；两个 `.sha256` 文件内容也与相应 ZIP 一致。

| 附件 | 远端字节数 | 下载后 SHA256 | 核验 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.8.5-source.zip` | 6 030 339 | `4d8a0b6beeec7ce02c0120bf96a60e0399efc84e9ec9b52f6e90be49b987a45d` | 通过 |
| `MCP_CREO_MechDog-0.8.5-source.zip.sha256` | 101 | `7956d475fab16bd9caf932338dd425294bdc318ef9fb2dc33df6256b277cfc4b` | 通过 |
| `MCP_CREO_MechDog-0.8.5-seed-library.zip` | 493 394 | `4178f8aaa0509653915a8238374696358739c140c3a6d7a442dc0491daec53a8` | 通过 |
| `MCP_CREO_MechDog-0.8.5-seed-library.zip.sha256` | 107 | `db59ac215ae4766cbd0bedafae7fde4da5c7cb9747a717ddfc5bfcd0fa1cdce7` | 通过 |

发布后逐 ID 核对：DEV-051 仍验收中、0.8.5 已交付本轮子项；BUG-046 支持边界已明确；BUG-047 折边方向子项已验；FEAT-014 四壁和 relief 继续开放；FEAT-031/T13 继续不通过。卡首页、主台账、版本说明、开发入口与实际 Release 的当前版本入口一致。此段是发布后本地核验记录，**未进入已发布源码包，也未在 main 增加提交**；正式附件的哈希以 Release body 为准。
