# RELEASE-0.18.3 发布记录

## 1. 版本与条目

| 项 | 值 |
| --- | --- |
| 版本 | 0.18.3（PATCH，用户指定编号的例外：含新增公开工具，按语义化版本本应 MINOR） |
| 条目 | [DEV-074](work-items/DEV-074.md)、[FEAT-058](work-items/FEAT-058.md)、[FEAT-009](work-items/FEAT-009.md)、[FEAT-039](work-items/FEAT-039.md)、[DEV-066](work-items/DEV-066.md)、[DEV-072](work-items/DEV-072.md) |
| 公开工具 | 102→104：新增 `creo_surface_loft`、`creo_measure_surface_group`；`creo_quilt_merge` 仍隐藏 |
| 性质 | 反馈批实机收口 + 两个增量公开工具；H03 反证不解除门禁 |

本版交付：H01（FEAT-058 非零 origin 大跨度 resize）、H02（FEAT-009 两截面直纹曲面放样）、H04（FEAT-039 曲面组四态测量）、H06（FEAT-039 保留侧真实几何）、H11（DEV-072/074 远端发布核对）、H13（DEV-066/074 证据工具无 Git 化）。H03 为反证交付（门禁保持）。H05/H07/H08/H09/H10/H12 未完成。

## 2. 提交、dirty 标志与受测源码指纹

| 项 | 值 |
| --- | --- |
| 门禁运行提交 | `7d18fca`（Merge origin/main into codex/DEV-074-feedback0174-offline） |
| 门禁时工作树 | dirty=true（本版版本号、种子清单、文档与打包记录改动未提交） |
| 受测源码指纹 | `2aeceda9d390ad60842dc4d2d3adfc25c4ea643b615dd1e20d28dd8269d09120`（`sha256-repo-lf-v1`，由 `tools/dev_check.py` 实测） |
| 发布准备提交 | 本记录所在的发布准备提交，标题 `DEV-074: prepare the 0.18.3 release`（哈希见 `git log -1`；因不能把提交自身哈希写入自身，未在文件内嵌） |
| 分支 | `codex/DEV-074-feedback0174-offline`，隔离工作树 `E:\Projects\MCP_CREO_MechDog-d074` |

源码包由发布准备提交的同一工作树生成；`version.py` 与种子清单已同步为 0.18.3。

## 3. 日期与环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07（Asia/Shanghai） |
| 系统 | Windows x64 |
| Python | 3.12.14（`.venv`） |
| Creo | 12.4.0.0（实机证据时点；本记录的门禁未启动/连接 Creo） |
| Toolkit SDK | 与本机 Creo 12.4.0.0 匹配的 SDK |
| 编译器 | MSVC x64 构建工具 |
| 工具链 | Ruff 0.17.0、clang-format 23.1.3（`dev_check` 报告） |

## 4. 命令及结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 原生编译 | `.\.venv\Scripts\python.exe bridge.py build` | 退出 0，生成 `build/creo_worker.exe`（13 905 408 B，SHA256 `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb`） |
| 全量门禁 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-074` | `success=true`；单测 **2916 项，0 失败 0 错误**；24 lint / 12 未格式化（存量基线，无新增） |
| 种子包（首次） | `python tools/package_seeds.py --output build/release-assets/MCP_CREO_MechDog-0.18.3-seed-library.zip` | exit 2：按设计拒绝未回填记录的摘要，保留归档并打印 `7325485f…` |
| 种子包（回填后） | 回填 `docs/seed_package.json` 后重建 | exit 0：24 个文件、9 个种子、摘要仍为 `7325485f26201c0242a315e7aa0291714a3de81e852eccbba6e60f6288831102` |
| 源码包 | `python tools/package.py --seed-archive build/release-assets/MCP_CREO_MechDog-0.18.3-seed-library.zip --output build/release-assets/MCP_CREO_MechDog-0.18.3-source.zip` | exit 0：1529 个文件，四附件闸门通过 |
| 源码包解压全量单测 | 解压到 `C:\i0183\MCP_CREO_MechDog`（无 `.git/`），自建 venv 安装 `requirements.txt` 与 `--no-deps -e .` 后运行 `python -m unittest discover -s tests` | **2916 项，0 失败 0 错误，3 项 SDK 跳过**（run `256.759s`） |
| 实机 | 见第 5 节 | 本记录未新连 Creo；引用 2026-11-07 已归档证据 |

## 5. 原生实机证据索引

| 条目 | 环境 | 结果 | 证据 |
| --- | --- | --- | --- |
| FEAT-058/H01 非零 origin 大跨度 resize | Creo 12.4.0.0，单会话串行 | 14/14 通过；6000/42920/41400/20000/27000/2400/1500 mm³ 等预期体积、bbox、feature id、origin、厚度、`saved_file_reloaded_and_verified=true`、revision 前进 | [SUMMARY](validation/FEAT-058-H01-2026-11-07/SUMMARY.md)、`artifacts/*.json` |
| FEAT-009/H02 两截面直纹曲面放样 | Creo 12.4.0.0 | 22/22 检查；quilt 800.0 mm²、开放、无实体、保存重载 id/面积不变；x=20 修剪两侧各 400.0 mm²；2 mm 加厚 1599.9999999999995 mm³ | [SUMMARY](validation/FEAT-009-H02-2026-11-07/SUMMARY.md)、`live_report.json` |
| FEAT-039/H04 曲面组四态测量 | Creo 12.4.0.0，mm | 42 项检查；closed/micro_gap/open/overlap 四态与 gap 0/0.005/0.5 mm、overlap 埋入边 2 | [EVIDENCE](validation/feat039-h04-surface-group-2026-11-07/EVIDENCE.md)、`live_group_report.json` |
| FEAT-039/H06 保留侧真实几何 | Creo 12.4.0.0，mm | 41 项检查；6 个 job；形心 +2.5/−17.5 mm、bbox、方向、保存重载、失败回滚 revision 1→1 | [EVIDENCE](validation/feat039-h06-kept-side-2026-11-07/EVIDENCE.md)、`live_trim_report.json` |
| FEAT-039/H03 quilt merge 反证 | Creo 12.4.0.0 | 两次尝试均 ACTIVE 但 0 quilt / 4 surface / quilt 访问 -4；门禁保持 | [EVIDENCE](validation/feat039-h03-quilt-merge-incomplete-2026-11-07/EVIDENCE.md)、`merge_probe_report.json` |

## 6. 未测模块、失败用例与兼容限制

- H05 钣金附着增料/百叶/格栅/凸台/铰链/耳与 corner relief；H07 独立 quilt offset；H08 曲面边圆角/曲率梳/斑马纹；H09 任意非平面填充；H10 五爪整链；H12 BUG-115 新诊断 MCP 实机复验与保存重载；H03 逐片缝合。
- H01 未做字面会话擦除后重载；`tools/test_adoption_planar_wall.py --live` 77 项因通道占用未跑完。
- H02 未验证 ≥3 截面、smooth/闭合、相切/曲率连续性、非平行/扭转/圆弧截面；先加厚再修剪返回 -1。
- H04/H06 未测 Creo 9/10、非 mm、多面/非平面成员、闭合壳体组；重叠面积为采样估计；`surface_trim` 标签下游引用 -4。
- H03 排查遗留 `unknown_outcome` 作业（模型 `35576f45…`），按用户决定由用户手动处理 Creo 会话，本版未清除保护。
- 本机无 Creo 9 SDK；Creo 10 未复测；WorkBuddy 公开 MCP 黑盒未执行。
- API asset-ID 回退的触发路径未做故障注入；v0.17.3 body 历史瑕疵按规则不改旧发布。

## 7. 源码包及种子包 SHA256

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.18.3-source.zip` | 8 650 655 | `042959b54dab8de15044b9991f7defc3abce476c0cee8228997f7f00979b45bb` |
| `MCP_CREO_MechDog-0.18.3-source.zip.sha256` | 101 | `de4e08b40a4127d483fb4f93d93d62d726c7a2d7f5d8644ebaee1af0678df657` |
| `MCP_CREO_MechDog-0.18.3-seed-library.zip` | 493 442 | `7325485f26201c0242a315e7aa0291714a3de81e852eccbba6e60f6288831102` |
| `MCP_CREO_MechDog-0.18.3-seed-library.zip.sha256` | 107 | `06b9ba48b97a240ce4d784e22ee69851f0305b8ac835642a8b77867de165ba6b` |

两个 sidecar 内容分别为 `<摘要>  MCP_CREO_MechDog-0.18.3-source.zip` 与 `<摘要>  MCP_CREO_MechDog-0.18.3-seed-library.zip`，与被摘要文件同名。

自引用说明：源码包内含本记录与版本说明，二者在归档生成时无法写入自身 ZIP 的摘要，包内副本因此保留「待解压验证/回填」占位；工作树与本文件记录的是打包后实测的最终值，发布体（Release body）以本表为准。

## 8. Release 附件清单（固定四个）

| 远端名称 | 存在性（准备态） |
| --- | --- |
| `MCP_CREO_MechDog-0.18.3-source.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.3-source.zip.sha256` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.3-seed-library.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.3-seed-library.zip.sha256` | 本地已生成，待主代理上传 |

## 9. 发布候选验收结论

- 全量门禁通过（0 失败 0 错误），原生执行器重新编译退出 0，两个打包脚本退出 0 且四附件闸门通过；本版新增工具与实机证据一致。
- 本记录为**准备发布**时点；tag、GitHub Release、远端附件核对由主代理完成，不得把本记录当作已发布事实。
- 未完成项与未测范围已在上文如实列出，不以历史证据替代本版结论。

## 10. 合入 main 的提交、版本标签及指向

待主代理合入与发布后回填：合入提交 `____`；标签 `v0.18.3` 指向 `____`；Release 链接 `____`。

## 11. GitHub Release 链接与发布状态

待主代理创建后回填（草稿/已发布、Pre-release 标记）。

## 12. 远端附件与 SHA256 核对结果

待主代理发布后执行 `python tools/check_release_assets.py --tag v0.18.3` 并回填：四个附件齐全、两个 sidecar 与对应 ZIP 摘要一致、Release body 含第 7 节 SHA256。

## 13. 逐 ID 状态核对（候选态）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [DEV-074](work-items/DEV-074.md) | 已交付 0.18.3 子项（H01/H02/H04/H06/H11/H13）；H03 反证仍 gated | 0.18.3 | H05/H07/H08/H09/H10/H12、Creo 9/10、WorkBuddy | 已交付 0.18.3 子项 | 已交付 0.18.3 子项 | 已列 | 0.18.3 入口 | 待发布 |
| [FEAT-058](work-items/FEAT-058.md) | H01 已修复（实机 14/14） | 0.18.3 | 坐标换参、扩展 frame、非矩形截面、Creo 9/10 | 已交付 0.18.3 子项 | 已交付 0.18.3 子项 | 已列 | 0.18.3 入口 | 待发布 |
| [FEAT-009](work-items/FEAT-009.md) | H02 两截面 `surface_loft` 已交付 | 0.18.3 | ≥3 截面、smooth/闭合/连续性、非平行/扭转/圆弧 | 已交付 0.18.3 子项 | 已交付 0.18.3 子项 | 已列 | 0.18.3 入口 | 待发布 |
| [FEAT-039](work-items/FEAT-039.md) | H04/H06 已交付；H03 反证 | 0.18.3 | 逐片缝合、quilt offset、非平面 fill、多截面/边界混合、trim 偏置 | 已交付 0.18.3 子项 | 已交付 0.18.3 子项 | 已列 | 0.18.3 入口 | 待发布 |

## 14. 相对上一正式包核对（上一版本：0.18.2）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节（含 `json.hpp`、第三方许可） | 未在本机保留 0.18.2 源码包 | 由 `git diff v0.18.2..HEAD -- native/third_party` 为空，字节未变 | 未变；无需迁移 |
| 回调指纹（`sha256-repo-lf-v1`） | 未在本机保留 0.18.2 构建产物 | `de87b1457d7ca677a17c583136b2696406c22b5a221f742907c57d7bca4eab03`（`build/blend_loader_build.json`） | 回调源码本批未改；上一版对应值未比对 |
| loader DLL SHA256 | 未在本机保留 | `ca74bfdb36ec4f0e06972b48da94894d9bad8bb7a52d3f333b7b277846581881`（`build/creo_blend_loader.dll`） | 本批未改 loader 源码；未比对 |
| callback DLL SHA256 | 未在本机保留 | `21b90435b416cd789b77b491c9abc472dee436980241f6e59700de9e28f02a2d`（`build/creo_blend_sync.dll`） | 本批未改 callback 源码；未比对 |
| worker SHA256 | 未在本机保留 | `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb`（`build/creo_worker.exe`） | 新增/修改原生特征后重建，哈希预期变化 |
| `protk.dat` / 注册表路径 | 未连接、未读取 | 未改动、未重新注册 | 本批未做注册变更 |
| 实际注册影响 | — | — | 需重新注册：否；需迁移：否；需重启：否（本批未连接 Creo；新执行器需在下次安装/启动时按现有流程生效） |
