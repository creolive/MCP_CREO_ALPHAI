# RELEASE-0.19.0 发布记录

## 1. 版本与条目

| 项 | 值 |
| --- | --- |
| 版本 | 0.19.0（MINOR：新增 2 个公开工具并重新公开 1 个，104→107；无既有接口不兼容变更） |
| 条目 | [DEV-074](work-items/DEV-074.md)、[FEAT-039](work-items/FEAT-039.md)、[FEAT-055](work-items/FEAT-055.md)、[FEAT-014](work-items/FEAT-014.md) |
| 公开工具 | 107（`creo_surface_round`、`creo_measure_surface_curvature` 新增；`creo_quilt_merge` 解除门禁）；`creo_surface_boundary_fill` 仍门禁隐藏 |
| 性质 | 曲面边圆角与数值曲率/G1 公开、quilt merge 公开、五爪整瓶整链实机；钣金成形类、独立 quilt 偏置、任意非平面填充分别为不可用/未取证，门禁保持 |

## 2. 提交、dirty 标志与受测源码指纹

| 项 | 值 |
| --- | --- |
| 分支 / 工作树 | `codex/DEV-074-forming`，隔离工作树 `e:\Projects\MCP_CREO_MechDog-d074` |
| 基线 | `2266ea8`（基于已发布 0.18.4） |
| 门禁运行提交 | `2266ea8` |
| 门禁时工作树 | dirty=true（本版版本号、种子清单、文档与发布记录改动未提交） |
| 受测源码指纹 | `a6d4dc23147a36ce988da0b79c0313be9b3770328cc6edbb3d79373a0455d01b`（`sha256-repo-lf-v1`，由 `tools/dev_check.py` 实测） |
| 发布准备提交 | 本记录所在的发布准备提交，标题 `DEV-074: prepare the 0.19.0 release`（不能把提交自身哈希写入自身，哈希见交付报告） |

源码包由同一工作树生成；`version.py`、`docs/seed_manifest.json`、`seed_library/seed_manifest.json` 与 `docs/seed_package.json` 已同步为 0.19.0。

## 3. 日期与环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-08（Asia/Shanghai） |
| 系统 | Windows x64 |
| Python | 3.12（`.venv`） |
| Creo | 12.4.0.0（release numeric 44，实机证据时点；本记录的门禁未启动/连接 Creo） |
| Toolkit SDK | 与本机 Creo 12.4.0.0 匹配的 SDK |
| 编译器 | MSVC x64 构建工具 |

## 4. 命令及结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 全量门禁 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item DEV-074` | `success=true`；单测 **3005 项，0 失败 0 错误**（打包后复跑：2026-11-08T06:17:13Z 起，14:22:44 完成，与前次一致）；24 lint / 12 未格式化（存量基线，无新增）；指纹 `a6d4dc23…0455d01b` |
| 原生编译 | `.\.venv\Scripts\python.exe bridge.py build` | 退出 0，生成 `build/creo_worker.exe`（14 027 264 B，SHA256 `1bba0deeaf0e98e8bf66e95ddf96eea88c5a361a7913a4ce442d0af760a1328e`） |
| 种子包（首次） | `python tools/package_seeds.py --output build/release-assets/MCP_CREO_MechDog-0.19.0-seed-library.zip` | exit 2：按设计拒绝未回填记录（旧摘要），保留归档并打印 `05859ac1…41a072`；24 个文件、9 个种子 |
| 种子包（回填后） | 回填 `docs/seed_package.json` 后删除首轮归档并重建 | exit 0：24 个文件、9 个种子、摘要仍为 `05859ac1ae89d0c0455f6b4aa8a02a34b232588c4d1b4da74d6842f21041a072` |
| 源码包 | `python tools/package.py --seed-archive build/release-assets/MCP_CREO_MechDog-0.19.0-seed-library.zip --output build/release-assets/MCP_CREO_MechDog-0.19.0-source.zip` | exit 0：1579 个文件，四附件闸门通过（两个 sidecar 与 ZIP 摘要一致） |
| 源码包解压全量单测 | 本批未执行 | 未验证（见第 6 节） |
| 实机 | 见第 5 节 | 本记录未新连 Creo；引用已归档的 2026-11-08 证据 |

## 5. 原生实机证据索引

| 条目 | 环境 | 结果 | 证据 |
| --- | --- | --- | --- |
| FEAT-055/H08 曲面边圆角 | Creo 12.4.0.0，mm，单会话串行 | R3 后 quilt 4→5 面、1187.1238898038469 mm²（oracle 逐位一致）、开放、无实体、保存重载 true；非相邻面 `feature_status=6` 失败并回滚（rev 2→2） | [EVIDENCE](validation/dev074-h08-h09-live-2026-11-08/EVIDENCE.md)、`A_surface_round.json` |
| FEAT-055/H08 数值曲率/G1 | Creo 12.4.0.0，mm | 平面 0.0 /mm、半径 null；R8 球面 0.12500000000000003 /mm、7.999999999999998 mm；G1 90.0°、`within_g1=false`；三次只读 revision 不变 | 同上、`C_surface_curvature.json` |
| FEAT-039/H03 quilt merge 公开 | Creo 12.4.0.0，mm | 两片 400 mm² → 目标 quilt 800.0 mm²、开放、保存重载 true，2 mm 加厚成功；不相邻负例 −1 回滚 | [EVIDENCE](validation/dev074-h03h07-2026-11-08/EVIDENCE.md)、`h03_merge_live.json` |
| FEAT-039/H10 五爪整瓶整链 | Creo 12.4.0.0，mm | 46 作业、63 项 0 失败；闭合壳 7858.298125230911 mm²、`open_edges=0`；加厚 2357.526/15727.485 mm³；solidify 56799.99517675038 mm³；圆角与重载成功 | [EVIDENCE](validation/dev074-h10-five-claw-2026-11-08/EVIDENCE.md)、`report.json` |
| FEAT-014 钣金成形类 | Creo 12.4.0.0，mm | corner relief 三变体再生失败回滚（miter 对照成功）；草图成形三变体 create=−1；无 Hem/Jog API；格栅未取证；门禁保持 | [EVIDENCE](validation/dev074-forming-2026-11-08/EVIDENCE.md)、`evidence.json` |
| FEAT-039/H07 独立 quilt 偏置 | Creo 12.4.0.0，mm | `PRO_FEAT_FLX_OGF` 完整树 −1；INCOMPLETE 骨架 redefine −1；复制+平移为平移副本（面内距离 0）；门禁保持 | [EVIDENCE](validation/dev074-h03h07-2026-11-08/EVIDENCE.md)、`h07_ogf_*.json` |
| FEAT-039/H09 任意非平面填充 | Creo 12.4.0.0，mm | 平面闭合环 `feature_status=6`、quilt 访问 −4、0 quilt、整体回滚；工具移出公开面 | [EVIDENCE](validation/dev074-h08-h09-live-2026-11-08/EVIDENCE.md)、`B_planar_fill_failure_job*.json` |

## 6. 未测模块、失败用例与兼容限制

- **不可用（门禁保持）**：钣金成形类（corner relief、百叶/成形、hem/jog、格栅孔、凸台/铰链/门板耳）、独立 quilt 偏置、任意非平面闭合边界 `surface_fill`。
- **H03**：`INTERSECT`、三片以上单次合并、闭合壳体直接合并、非 mm、Creo 9/10 未验；工具 quilt 合并后不可测属内核行为。
- **H08**：quilt 边 id 通道（`PRO_ROUND_REF_EDGE`）、变半径/full/过渡、圆角后 thicken/solidify、弯曲 quilt、非 mm、Creo 9/10 未验。
- **H10**：真实凹谷瓣底、非 mm、Creo 9/10 未验；格栅 cut 与 BUG-046 矛盾未定因。
- **本批未执行**：源码包解压后的全量单测、WorkBuddy 公开 MCP 黑盒验收、Creo 9/10 实机（本机无 Creo 9 SDK，Creo 10 未复测）。

## 7. 源码包及种子包 SHA256

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.0-source.zip` | 8 908 094 | `9caa479041c2303e5e923faf48d0e5406de516e39050d71495ea3ec8c00a9878` |
| `MCP_CREO_MechDog-0.19.0-source.zip.sha256` | 101 | `0eb2615c836a8b96655e12c3fc6f5d443e2e9b5d8e209040d79be9cb3c9a2d9e` |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip` | 493 442 | `05859ac1ae89d0c0455f6b4aa8a02a34b232588c4d1b4da74d6842f21041a072` |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip.sha256` | 107 | `9cce3894e4ebd5ae2f3cfe650334becf83e0f398a62bb5234e179c0ffc7d506b` |

两个 sidecar 内容分别为 `<摘要>  MCP_CREO_MechDog-0.19.0-source.zip` 与 `<摘要>  MCP_CREO_MechDog-0.19.0-seed-library.zip`，与被摘要文件同名。

自引用说明：源码包内含本记录与版本说明，归档生成时无法写入自身 ZIP 的摘要，包内副本保留回填前占位；工作树与本文件记录的是打包后实测最终值，Release body 以本表为准。

## 8. Release 附件清单（固定四个）

| 远端名称 | 存在性（准备态） |
| --- | --- |
| `MCP_CREO_MechDog-0.19.0-source.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.19.0-source.zip.sha256` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip` | 本地已生成，待主代理上传 |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip.sha256` | 本地已生成，待主代理上传 |

## 9. 发布候选验收结论

- 全量门禁与原生编译按第 4 节执行；H05/H07/成形类与任意非平面填充为不可用或未取证结论，不以「检查通过」表述为能力开放。
- 本记录为**准备发布**时点；tag、GitHub Release 与远端附件核对由主代理完成，不得把本记录当作已发布事实。
- 未完成项与未测范围已在第 6 节如实列出，不以历史证据替代本版结论。

## 10. 合入 main 的提交、版本标签及指向

待主代理合入与发布后回填：合入提交 `____`；标签 `v0.19.0` 指向 `____`；Release 链接 `____`。

## 11. GitHub Release 链接与发布状态

待主代理创建后回填（草稿/已发布、Pre-release 标记）。

## 12. 远端附件与 SHA256 核对结果

待主代理发布后执行 `python tools/check_release_assets.py --tag v0.19.0` 并回填：四个附件齐全、两个 sidecar 与对应 ZIP 摘要一致、Release body 含第 7 节 SHA256。

## 13. 逐 ID 状态核对（候选态）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [DEV-074](work-items/DEV-074.md) | 已交付 0.18.3/0.18.4/0.19.0 子项；H03/H08/H10 交付，H05/H07/成形类/非平面 fill 不可用 | 0.19.0 | 成形类、格栅、独立 quilt 偏置、任意非平面 fill、Creo 9/10、WorkBuddy | 已交付 0.18.3—0.19.0 子项 / 0.19.0 | 已交付 0.18.3—0.19.0 子项 / 0.19.0 | 已列 | 0.19.0 入口 | 待发布 |
| [FEAT-039](work-items/FEAT-039.md) | H03 merge 公开、H10 整链实机；H07 与任意非平面 fill 仍不可用（门禁保持） | 0.19.0 | 独立 quilt offset、任意非平面 fill、多截面/边界混合、trim 偏置语义、H03 其它模式 | 已交付 0.13.0—0.19.0 子项 / 0.19.0 | 已交付 0.13.0—0.19.0 子项 / 0.19.0 | 已列 | 0.19.0 入口 | 待发布 |
| [FEAT-055](work-items/FEAT-055.md) | H08 曲面边圆角与数值曲率/G1 公开并实机验收 | 0.19.0 | edge-chain、变半径/过渡、圆角后 thicken/solidify、Q08 边界混合及 Q01—Q07 | 已交付 0.18.4/0.19.0 子项 / 0.19.0 | 已交付 0.19.0 子项 / 0.19.0 | 已列 | 0.19.0 入口 | 待发布 |
| [FEAT-014](work-items/FEAT-014.md) | H05 附着增料与成形类均为反证，不可用，门禁保持 | 0.19.0（成形类反证） | 连续多边折边、corner relief、百叶/成形/hem/jog、格栅孔、凸台/铰链/耳 | 已交付 0.18.4/0.19.0 反证子项 / 0.19.0 | 已交付 0.19.0 反证子项 / 0.19.0 | 已列 | 0.19.0 入口 | 待发布 |

## 14. 相对上一正式包核对（上一版本：0.18.4）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节（含 `json.hpp`、第三方许可） | 0.18.4 源码包 | 本批未改（以 `git diff v0.18.4..HEAD -- native/third_party` 为空核对） | 未变；无需迁移 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.18.4 记录未变（沿用 0.18.3 值） | 本批未改回调源码，沿用同值 | 未变；无需重新注册 |
| loader DLL SHA256 | 0.18.4 未变 | 本批未改 loader 源码 | 未变；无需迁移 |
| callback DLL SHA256 | 0.18.4 未变 | 本批未改 callback 源码 | 未变；无需迁移 |
| worker SHA256 | `3ac423dd831674a668ad3df081839189aedfd6d009a3dbec843c02b5b584e2cb` | `1bba0deeaf0e98e8bf66e95ddf96eea88c5a361a7913a4ce442d0af760a1328e`（14 027 264 B，本批重建） | 原生源码有变更（`quilt_merge.cpp`、`quilt_query.h` 及曲面实现），哈希随构建更新 |
| `protk.dat` / 注册表路径 | 未改动 | 未改动、未重新注册 | 无需迁移 |
| 实际注册影响（未变 / 需重新注册 / 需迁移 / 需重启） | — | — | 需重新注册：否；需迁移：否；需重启：服务与客户端需重启以加载新执行器 |
