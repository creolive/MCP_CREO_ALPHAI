# RELEASE-0.18.4 发布记录

## 1. 版本与条目

| 项 | 值 |
| --- | --- |
| 版本 | 0.18.4（PATCH：无新增公开工具、无 schema/接口不兼容变更） |
| 条目 | [DEV-074](work-items/DEV-074.md)、[FEAT-039](work-items/FEAT-039.md)、[FEAT-055](work-items/FEAT-055.md)、[FEAT-014](work-items/FEAT-014.md)、[BUG-115](work-items/BUG-115.md)；关联 [DEV-066](work-items/DEV-066.md)（本版无新交付） |
| 公开工具 | 104（不变）；`creo_quilt_merge`、`surface_round` 仍由能力门禁隐藏 |
| 性质 | 0.18.3 遗留实机收口：H09/H10 替代路线交付，H05/H07 反证不可用（门禁保持），H08 契约登记（未开放），H12 回执复验 |

## 2. 提交、dirty 标志与受测源码指纹

| 项 | 值 |
| --- | --- |
| 分支 / 工作树 | `codex/DEV-074-h05h12`，隔离工作树 `e:\Projects\MCP_CREO_MechDog-d074` |
| 基线 | `331bf88`（0.18.3 已发布）；本记录由发布准备提交生成 |
| 门禁运行提交 | `331bf88`（`331bf88700fd93771e30e07eb1f6ee58dd9e25e6`） |
| 门禁时工作树 | dirty=true（本版版本号、种子清单、文档与打包记录改动未提交） |
| 受测源码指纹 | `3574cd75d8923e26d3073f744135a8d5b56023a107e323d32b5e7cb2e101c9e6`（`sha256-repo-lf-v1`，由 `tools/dev_check.py` 实测） |
| 发布准备提交 | 本记录所在的发布准备提交，标题 `DEV-074: prepare the 0.18.4 release`（因不能把提交自身哈希写入自身，未在文件内嵌；哈希见交付报告） |

源码包由同一工作树生成；`version.py`、`docs/seed_manifest.json`、`seed_library/seed_manifest.json` 与 `docs/seed_package.json` 已同步为 0.18.4。

## 3. 日期与环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07（Asia/Shanghai；H07/H08 证据文件日期为 2026-11-08，系实机跨零点） |
| 系统 | Windows x64 |
| Python | 3.12.14（`.venv`） |
| Creo | 12.4.0.0（实机证据时点；本记录的门禁未启动/连接 Creo） |
| Toolkit SDK | 与本机 Creo 12.4.0.0 匹配的 SDK |
| 编译器 | MSVC x64 构建工具 |
| 工具链 | Ruff 与 clang-format 版本见 `build/development_check.json` |

## 4. 命令及结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 原生编译 | `.\.venv\Scripts\python.exe bridge.py build` | 退出 0，生成 `build/creo_worker.exe`（13 905 408 B，SHA256 `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb`） |
| 全量门禁 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-074` | `success=true`；单测 **2943 项，0 失败 0 错误**（2026-11-07T17:24:15Z 起）；24 lint / 12 未格式化（存量基线，无新增）；指纹 `3574cd75…e101c9e6` |
| 种子包（首次） | `python tools/package_seeds.py --output build/release-assets/MCP_CREO_MechDog-0.18.4-seed-library.zip` | exit 2：按设计拒绝未回填记录（版本 0.18.3），保留归档并打印 `1a030983…eb8647`；24 个文件、9 个种子 |
| 种子包（回填后） | 回填 `docs/seed_package.json` 后重建 | exit 0：24 个文件、9 个种子、摘要仍为 `1a030983c448d1f76cf5b74d878abce653e5d389ff939468b5cd314b43eb8647` |
| 源码包 | `python tools/package.py --seed-archive build/release-assets/MCP_CREO_MechDog-0.18.4-seed-library.zip --output build/release-assets/MCP_CREO_MechDog-0.18.4-source.zip` | exit 0：1549 个文件，四附件闸门通过 |
| 源码包解压全量单测 | 解压到 `C:\i0184\MCP_CREO_MechDog`（无 `.git/`），自建 venv 安装 `requirements.txt` 与 `--no-deps -e .` 后运行 `python -m unittest discover -s tests` | **2943 项，0 失败 0 错误，3 项 SDK 跳过**（`Ran 2943 tests in 258.008s`，exit 0） |
| 实机 | 见第 5 节 | 本记录未新连 Creo；引用已归档的 2026-11-07/08 证据 |

## 5. 原生实机证据索引

| 条目 | 环境 | 结果 | 证据 |
| --- | --- | --- | --- |
| FEAT-039/H09 旋转球面替代 | Creo 12.4.0.0，mm，单会话串行 | 22 项检查通过；R8 球面 804.247719319002 mm²、闭合、无实体；x=4 修剪 201.06192982974773 / 603.1857894892481 mm²；2 mm 加厚 404.21825476170756 mm³；solidify 2144.6605848506724 mm³；均保存重载 | [EVIDENCE](validation/feat039-h09-surface-revolve-2026-11-07/EVIDENCE.md)、`live_surface_revolve_report.json` |
| FEAT-039/H10 多 quilt 组整链 | Creo 12.4.0.0，mm | 46/46；三片共 3200 mm²；组级 `state=closed`、`open_edges=6`、gap≈0、`boundary_closed=false`；0.3 mm/2 mm 逐片加厚 240.0/1600.0 mm³ 并保存重载；整组实体化与 `quilt_merge` 受理前被拒 | [EVIDENCE](validation/feat039-h10-multi-quilt-2026-11-07/EVIDENCE.md)、`live_multi_quilt_report.json` |
| FEAT-014/H05 钣金附着增料反证 | Creo 12.4.0.0，mm | 直接 add −1；`new_body` 成独立体；以钣金体为 target 的 union −1；反向 union 吞并钣金体（壁面候选 8→0、unbend 失败）；门禁保持 | [EVIDENCE](validation/feat014-h05-sheetmetal-solid-add-2026-11-07/EVIDENCE.md)、`evidence.json` |
| FEAT-039/H07 独立 quilt 偏置反证 | Creo 12.4.0.0，mm | thin 树只出厚度带（各 4000 mm³、带宽 5.0 mm）；三条独立偏置树 −1/−2/−1；门禁保持 | [EVIDENCE](validation/dev074-h07-h08-2026-11-08/EVIDENCE.md)、`h07_quilt_offset_probe.json` |
| FEAT-055/H08 曲面边圆角 | Creo 12.4.0.0，mm | 可行但未注册工具；R3 后 quilt 5 面 1187.1238898038469 mm²、开放、0 实体面、重载 true；非相邻面再生失败回滚 | [EVIDENCE](validation/dev074-h07-h08-2026-11-08/EVIDENCE.md)、`h08_surface_round_probe.json` |
| BUG-115/H12 回执与准入复验 | Creo 12.4.0.0，公开 MCP | 38 项检查 0 失败；失败回执显式 null、板厚上下文自洽、空预览依据、`nearest_edges` 不截断、同计划整链拒绝、`fill→thicken` 放行 | [EVIDENCE](validation/dev074-h12-receipts-2026-11-07/EVIDENCE.md)、`live_receipts_report.json` |

## 6. 未测模块、失败用例与兼容限制

- 任意非平面闭合边界 `surface_fill`；独立 quilt 偏置；公开曲面边圆角工具与曲率梳/斑马纹；百叶/成形/hem/jog、格栅孔、凸台/铰链/门板耳、corner relief；五爪整瓶整链实体化；H03 逐片缝合。
- H09：Creo 9/10、非 mm、90° 球带、显式外部基准轴、非 X 轴/倾斜轴未验；0.3 mm 整链与球冠边缘加厚自交边界未验。
- H10：Creo 9/10、非 mm、非平面/弯曲成员未验；已加厚成员不能再参与组级测量（`contour_edge_visit_failed`）。
- H05：Creo 10 从未尝试；其他凸台形状/板厚/重叠与多凸台 union 顺序未验；反向 union 后恢复钣金身份的路线未尝试。
- H07/H08：H07 仅 3 个候选树；H08 未取得 quilt 边 id，变半径/full/过渡、圆角后 thicken/solidify 与 G1 实测未验。
- H12：busy/`unknown_outcome`、真实断流、Creo 已退出快照未验；BUG-115 原生 −4 根因仍开放。
- 本机无 Creo 9 SDK；Creo 10 未复测；WorkBuddy 公开 MCP 黑盒未执行。

## 7. 源码包及种子包 SHA256

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.18.4-source.zip` | 8 752 689 | `81ff64939c9b14ae94635bb49928664526d8fd4b64bda25836381320eb0f8f4f` |
| `MCP_CREO_MechDog-0.18.4-source.zip.sha256` | 101 | `be337e203d0a0e9e2edfc9d7eeeaa0fa074df8be0eb1ed7f8fe1f3636704e0e5` |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip` | 493 442 | `1a030983c448d1f76cf5b74d878abce653e5d389ff939468b5cd314b43eb8647` |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip.sha256` | 107 | `168f7f4a277ad8b92d6b039839ed73626bb2af5ef66d85bcacbceeff27623aca` |

两个 sidecar 内容分别为 `<摘要>  MCP_CREO_MechDog-0.18.4-source.zip` 与 `<摘要>  MCP_CREO_MechDog-0.18.4-seed-library.zip`，与被摘要文件同名。

自引用说明：源码包内含本记录与版本说明，归档生成时无法写入自身 ZIP 的摘要，包内副本保留回填前占位；工作树与本文件记录的是打包后实测最终值，Release body 以本表为准。

## 8. Release 附件清单（固定四个）

| 远端名称 | 存在性（准备态） |
| --- | --- |
| `MCP_CREO_MechDog-0.18.4-source.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.4-source.zip.sha256` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip.sha256` | 本地已生成，待主代理上传 |

## 9. 发布候选验收结论

- 全量门禁、原生编译与两个打包脚本按第 4 节执行；H05/H07 为不可用结论，不以「检查通过」表述为能力开放。
- 本记录为**准备发布**时点；tag、GitHub Release 与远端附件核对由主代理完成，不得把本记录当作已发布事实。
- 未完成项与未测范围已在上文如实列出，不以历史证据替代本版结论。

## 10. 合入 main 的提交、版本标签及指向

待主代理合入与发布后回填：合入提交 `____`；标签 `v0.18.4` 指向 `____`；Release 链接 `____`。

## 11. GitHub Release 链接与发布状态

待主代理创建后回填（草稿/已发布、Pre-release 标记）。

## 12. 远端附件与 SHA256 核对结果

待主代理发布后执行 `python tools/check_release_assets.py --tag v0.18.4` 并回填：四个附件齐全、两个 sidecar 与对应 ZIP 摘要一致、Release body 含第 7 节 SHA256。

## 13. 逐 ID 状态核对（候选态）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [DEV-074](work-items/DEV-074.md) | 已交付 0.18.3/0.18.4 子项；H05/H07 反证不可用、H08 仅契约 | 0.18.4 | 百叶/格栅/凸台/铰链/耳、corner relief、任意非平面 fill、公开曲面圆角、五爪整瓶实体化、H03 逐片缝合、Creo 9/10、WorkBuddy | 已交付 0.18.3 与 0.18.4 子项 / 0.18.4 | 已交付 0.18.3/0.18.4 子项 / 0.18.4 | 已列 | 0.18.4 入口 | 待发布 |
| [FEAT-039](work-items/FEAT-039.md) | H09 替代路线、H10 组链已交付；H07 反证不可用 | 0.18.4 | 任意非平面 fill、独立 quilt offset、多截面/边界混合、trim 偏置、H03 缝合 | 已交付 0.18.3/0.18.4 子项 / 0.18.4 | 已交付 …/0.18.4 子项 / 0.18.4 | 已列 | 0.18.4 入口 | 待发布 |
| [FEAT-055](work-items/FEAT-055.md) | H08 契约登记，未开放工具 | 0.18.4 | 公开 `surface_round`、曲率梳/斑马纹、Q08 边界混合及 Q01—Q07 | 已交付 0.18.4 子项 / 0.18.4 | 已交付 0.18.4 子项 / 0.18.4 | 已列 | 0.18.4 入口 | 待发布 |
| [FEAT-014](work-items/FEAT-014.md) | H05 反证：附着增料不可用，门禁保持 | 0.18.4 | 连续多边折边、corner relief、百叶/成形/hem/jog、格栅孔、凸台/铰链/耳 | 已交付 0.18.4 子项 / 0.18.4 | 已交付 0.18.4 子项 / 0.18.4 | 已列 | 0.18.4 入口 | 待发布 |
| [BUG-115](work-items/BUG-115.md) | H12 回执与准入复验已交付；原生根因开放 | 0.18.4（H12 子项） | 原生 −4 根因、其它组合 | 已交付 0.18.4 H12 子项 / 0.18.4 | 已交付 0.18.4 H12 子项 / 0.18.4 | 已列 | 0.18.4 入口 | 待发布 |
| [DEV-066](work-items/DEV-066.md) | 本版未交付新子项，状态不变（t07 随 0.18.2 交付） | —（0.18.2 子项） | 其余 `tools/` 离线驱动的 git 依赖、负例输出与前置说明 | 部分交付 / 未排期 | 部分交付，剩余待规划 / 未排期 | 已列（历史） | 0.18.4 入口 | 待发布 |

## 14. 相对上一正式包核对（上一版本：0.18.3）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节（含 `json.hpp`、第三方许可） | 0.18.3 源码包 | 本批未改 `native/third_party/`（以 `git diff v0.18.3..HEAD -- native/third_party` 为空核对） | 未变；无需迁移 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.18.3 记录 `de87b145…a4eab03` | 本批未改回调源码，沿用同值 | 未变；无需重新注册 |
| loader DLL SHA256 | 0.18.3 记录 `ca74bfdb…6581881` | 本批未改 loader 源码 | 未变；无需迁移 |
| callback DLL SHA256 | 0.18.3 记录 `21b90435…f02a2d` | 本批未改 callback 源码 | 未变；无需迁移 |
| worker SHA256 | 0.18.3 记录 `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb` | `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb`（13 905 408 B，本批重建） | 原生源码本批未改，哈希未变 |
| `protk.dat` / 注册表路径 | 未改动 | 未改动、未重新注册 | 无需迁移 |
| 实际注册影响（未变 / 需重新注册 / 需迁移 / 需重启） | — | — | 需重新注册：否；需迁移：否；需重启：否（本批未连接 Creo） |
