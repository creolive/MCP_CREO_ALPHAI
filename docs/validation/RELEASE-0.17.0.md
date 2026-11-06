# 0.17.0 发布记录（2026-11-07）

- 条目：[FEAT-058](../work-items/FEAT-058.md)（原生矩形首壁可选 `origin` 草图定位与保持原点的改型）、[FEAT-014](../work-items/FEAT-014.md)（`sheetmetal_flange.edge` 的计划内几何选边 `edge_geometry`），MINOR 性质；公开工具仍 **100**，无新增工具，两处均为可选入参。
- 基线：上一已发布版本 **0.16.1**（`main` 提交 `34dbcb1`，标签 `v0.16.1`，见 [RELEASE-0.16.1](RELEASE-0.16.1.md)）。
- 开发分支：`codex/R10-first-wall-origin`（`be2f473` FEAT-058 首壁 origin、`bcc7f91` FEAT-014 `edge_geometry`），基于 `34dbcb1`。
- 目标版本：`v0.17.0`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在本次发布的 Release body 与交付说明中。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 原生编译 `bridge.py build` | 退出 0，`build/creo_worker.exe` 重建（`native/planar_wall.cpp` origin 矩形与截面轴映射、`native/advanced.cpp` 边几何匹配生效） |
| 全量单元测试 `tools/dev_check.py` | **2723 项通过**，0 失败 0 错误（0.16.1 起点 2702，本版新增 21 项）；`success=true` |
| 语言与格式 | 24 条 lint、12 个未格式化文件，均未高于 `style-baseline.json`；受检源码指纹 `71a6359e291b64e69ac2ff3bd6c780aeec9eea44e81bbc9f52fce03d63c92e98` |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；两次确定性构建同为 SHA256 `2f75aba0599b86f5c657cb48f27c95dac5d807b3c684807a25cd3b5ec09a3382`；`docs/seed_package.json` 回填后二次构建校验通过 |
| 源码包 `tools/package.py --seed-archive …` | 见下方交付清单（摘要与 Release body 一致） |

源码身份：`version.py` = 0.17.0；受测源码为提交 `bcc7f914ee080b5706d31fd24afeb84f0bd4be13`（HEAD `bcc7f91`）加版本元数据/文档改动（`dirty=true`，仅版本与发布文档，未改产品代码）；`tools/dev_check.py` 记录 `checked_source_sha256=71a6359e…`。**最终受测提交以合入 `main` 的 0.17.0 发布提交为准**，附件由该提交源码生成。

## 实机证据（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 与许可，单 Toolkit 通道串行）

| 项 | 结果 | 报告 |
| --- | --- | --- |
| FEAT-058 首壁 `origin` | `tools/test_first_wall_origin.py --live --confirm-session-usable` **112/112**；185×232×1、`origin=[-92.5,-116]` 的 bbox `[-92.5,-116,0]..[92.5,116,1]`、质心 `[0,0,0.5]`、体积 42 920 mm³；省略 origin 与 0.16.0 一致；XZ/YZ、负方向、同计划与跨计划 resize 200×250、第二面墙拒绝后继续 resize；保存重载全 true | `build/first_wall_origin/20261106T152859Z/origin_live.json`（同结果另有 `20261106T151338Z`） |
| FEAT-014 `edge_geometry` | `tools/test_flange_edge_geometry.py --live --confirm-session-usable` **17/17**；185×232×1 首壁（模型 `cbbcd27acf374b9c82534c3764b3aa51`），`+x`/`-x` 两道折边用创建前采集端点提交，顶面 232 mm 与贴边 `matches`，保存重载 true；`-y` 顶边由 185 缩短到 177.92 mm、id 85→267 后按几何端点加 `miter_cuts{1,1}` 重建成功；不存在几何被拒（扫描 86 条直线边、匹配 0 条），revision/体积不变、回滚 `succeeded` | `build/flange_edge_geometry/20261106T235931_f44fd733/report.json`，SHA256 `b84b3e0f5908f6af8932babf70803bbb81982f7ef2bbadf90341db917f13f4ea` |

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| `origin` 入参与 schema | ✅ 已合入 | `SheetmetalPlanarWallOp.origin`（默认 `[0,0]`、有限且 `|值|≤1e6`、非零值与显式平面字典互斥）；server 参数与 operation 透传；记录与结果回显 `origin` |
| 首壁创建按 origin 移动矩形 | ✅ 已合入（需重编） | `native/planar_wall.cpp` 矩形由 `0..L/0..W` 改为 `u0..u0+L / v0..v0+W`，命名帧与板厚生长侧不变，包络按移动后矩形校验 |
| 改型保持原点 | ✅ 已合入（需重编） | 读取草图截面定位矩阵，把记录 frame 映射到截面轴，按 `wall_0..wall_3` 角点表还原尺寸并核对旧值；旧记录缺 origin 按 `[0,0]` |
| `edge_geometry` 形态与 schema | ✅ 已合入 | `endpoints_mm` + `tolerance_mm`（默认 1e-6，范围 1e-9..1000），只接受两键；与 `{"kind":"edge","id":N}` 并存 |
| 原生几何选边 | ✅ 已合入（需重编） | `native/advanced.cpp` 每 op 前重扫 body→surface→contour→edge，无向端点对比较；0 条/多条/未知长度单位创建前拒绝并给诊断 |
| 单测与 live 驱动 | ✅ 已合入 | `tests/unit/test_native_planar_wall.py`（origin 相关 9 项）、`tools/test_first_wall_origin.py`、`tools/test_flange_edge_geometry.py` |

## 未验证范围

- Creo 9（本机无 SDK）与 Creo 10 实机；WorkBuddy 公开 MCP 黑盒。
- 显式平面字典与非零 `origin` 的组合（schema 明确拒绝，未实机执行）；斜置/非轴对齐 frame 的 resize（原生以"截面轴与记录 frame 不对齐"拒绝，未取实机证据）。
- `edge_geometry` 的多候选歧义与未知长度单位的实机拒绝（仅单测）、非轴对齐/斜置边的端点匹配、跨计划重放与真实重启后的 id 重排。
- 历史版本、历史证据与已发布附件保持原状，不用本版结果回填。

## 相对上一正式包核对（上一版本：0.16.1）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party/**` 原字节（含 `json.hpp`、第三方许可） | — | 未改 | `git diff 34dbcb1..HEAD -- native/third_party` 为空；无需迁移 |
| 回调指纹（`sha256-repo-lf-v1`） | — | 未改 | 本版未触碰回调注册代码；沿用 0.16.1 |
| loader DLL / callback DLL | — | 未改 | 本版只重编 `creo_worker.exe`；loader 与 callback 二进制由本机既有产物继续使用 |
| worker SHA256 | — | 重编 | 因 `native/planar_wall.cpp`、`native/advanced.cpp` 变更重编；替换执行器后重启 MCP 服务 |
| `protk.dat` / 注册表路径 | — | 未改 | 不需要重新注册；重启服务即可 |

## 逐 ID 状态核对（候选态）

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEAT-058 | `origin` 创建/改型已实机 112/112；默认路线不变 | 0.12.0 首壁、0.17.0 origin | 非矩形/多环截面、显式平面字典 + 非零 origin、斜置 frame resize、Creo 9/10、WorkBuddy | 已更新 | 已更新 | 已记录 | 已记录 | 发布后核对 |
| FEAT-014 | `edge_geometry` 已实机 17/17；`adjacent_bend_ends` 与 miter 门槛不变 | 0.16.0 miter、0.17.0 edge_geometry | 多候选/未知单位实机拒绝、非轴对齐边、跨计划重放与重启 id 重排、Creo 9/10、WorkBuddy | 已更新 | 已更新 | 已记录 | 已记录 | 发布后核对 |

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.17.0-source.zip`、`MCP_CREO_MechDog-0.17.0-source.zip.sha256`、`MCP_CREO_MechDog-0.17.0-seed-library.zip`、`MCP_CREO_MechDog-0.17.0-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.17.0` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

种子包 SHA256：`2f75aba0599b86f5c657cb48f27c95dac5d807b3c684807a25cd3b5ec09a3382`（24 文件、9 种子，内容除清单版本字段外未变）。源码包 SHA256 由最终提交源码生成，写入 Release body 与 `MCP_CREO_MechDog-0.17.0-source.zip.sha256`。

当前状态：**准备发布**（本文随 0.17.0 发布提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布交付说明。
