# MCP_CREO_MechDog 0.18.4 版本说明

发布日期：2026-11-07。性质：PATCH。本版**不新增公开工具、无 schema/接口不兼容变更**，公开工具数量仍为 **104**；交付内容为 0.18.3 遗留的 DEV-074 H05/H07/H08/H09/H10/H12 实机收口，其中 H05（钣金附着增料）与 H07（独立 quilt 偏置）为**不可用结论**，门禁保持，不构成新增能力。

## 本版变更

- **FEAT-039 / H09：非平面填充的替代路线「旋转球面」。** 任意非平面闭合边界的 `surface_fill` 仍无原生通道（`FillOp` 只有 `sketch`；`boundary`/`edges`/`sections` 三种 3D 闭环写法在受理前被拒），本版不新增算子、不放宽 planar fill。中心 R8 场景改用已有曲面旋转交付：半圆子午弧绕中心线 360° 生成闭合球面 quilt，R8 面积 **804.247719319002 mm²**（4πR² 差 1.5e-11）、`closed=true`、无实体；基准面 x=4 修剪保留 **201.06192982974773 mm²**（球冠）与另一侧 **603.1857894892481 mm²**；球冠 2 mm 对称加厚 **404.21825476170756 mm³**；闭合球 `solidify` **2144.6605848506724 mm³**（与 4/3πR³ 相对差约 2e-14）。实机 22 项检查通过、5 个作业、均保存重载。证据：[EVIDENCE](validation/feat039-h09-surface-revolve-2026-11-07/EVIDENCE.md)。
- **FEAT-039 / H10：多 quilt 组整链。** 两片 `surface_loft` 加一片 `surface_fill` 共 **3200 mm²**（800+800+1600），`creo_measure_surface_group` 给出组级 `state=closed`、`open_edges=6`、`gap_max_mm≈0`（2.465e-31）且 `boundary_closed=false`，区分「成员缝接合」与「外边界水密」。逐片 0.3 mm 加厚 **239.99999999999994 mm³**、2 mm 加厚 **1599.9999999999995 mm³**，均保存重载；两次加厚被内核并成同一 body（1836.9999999999982 mm³，重叠体积只计一次）。整组一次实体化与 `quilt_merge` 仍在受理前被拒，单片开放 quilt 的 `solidify` 在原生入口被闭合判据拒绝并回滚。实机 **46/46** 通过。证据：[EVIDENCE](validation/feat039-h10-multi-quilt-2026-11-07/EVIDENCE.md)。
- **FEAT-014 / H05：钣金附着增料反证，门禁保持。** 直接 `extrude(add)` 返回 `ProFeatureWithoptionsCreate=-1`；`new_body=true` 成功但生成独立实体（6000→6500 mm³、2 体）；union 以钣金体为 target 仍为 −1；反向 union（新实体为 target）虽合并成功，却吞并钣金体——壁面候选边 8 eligible→0、24 条全部 `ProSmtedgeContourGet=-8`、`sheetmetal_unbend` 失败并回滚。同件实体-实体 union 成功，说明 −1 特定于钣金体。文案已写明「Creo 12.4 不支持、Creo 10 未测」。证据：[EVIDENCE](validation/feat014-h05-sheetmetal-solid-add-2026-11-07/EVIDENCE.md)。
- **FEAT-039 / H07：独立 quilt 偏置反证，门禁保持。** 公开 `surface_offset` 的 thin 树只生成厚度带（正/负侧各 800×5=4000 mm³、带宽 5.0 mm、方向可控、6 面闭合），没有新的 quilt；三条独立偏置树分别 −1/−2/−1。公开语义明确为「偏置壁，非独立偏置 quilt」，`surface_trim` 的 `offset_mm`/`offset_side` 门禁保持。证据：[EVIDENCE](validation/dev074-h07-h08-2026-11-08/EVIDENCE.md)。
- **FEAT-055 / H08：曲面边圆角原生可行但未注册工具。** `ProRound.h` 明确支持 quilt 引用（`PRO_E_STD_CURVE_COLLECTION_APPL` 条目写明结果附着回原 quilt）。实机对相邻面 (68,66) 施加 R3，quilt 由 4 面 1200.0 mm² 变为 **5 面 1187.1238898038469 mm²**（解析 1200−60+47.12388980384689）、`closed=false`、0 个实体面、保存重载 true；非相邻面对再生失败并回滚到 4 面 1200.0 mm²。仅登记最小契约（`surface_round` 默认保持 `UNAVAILABLE_OPERATIONS`），本版不开放工具；曲率梳/斑马纹无 SDK API，只有 `ProSurfacePrincipalCrvtEval` 数值读数。证据：同上。
- **BUG-115 / H12：失败回执与准入公开 MCP 复验。** 38 项检查 0 失败：失败 resize 的 `feature_id_unchanged=null`、5 个 loaded 字段显式 null；板厚 two-context 自洽且 full/compact 37 键全等；空预览带 `empty_geometry_basis={feature_visit_code:0, non_datum_feature_count:0}`；失配时 5 条结构化 `nearest_edges` 在 compact 中不截断；同计划 `fill→trim→thicken` 提交前被拒且模型 revision 1→1 无副作用；`fill→thicken` 放行（4800 mm³、保存重载 true）。过期启动快照顶层仍 `state=ready/connected=true`，已记录为兼容字段建议，本版未改语义。证据：[EVIDENCE](validation/dev074-h12-receipts-2026-11-07/EVIDENCE.md)。

## 验收摘要

- 离线全量门禁：`tools/dev_check.py --work-item DEV-074` → `success=true`，单测 **2943 项，0 失败 0 错误**；风格存量基线 24 条 lint / 12 个未格式化文件，无新增；源码指纹 `3574cd75d8923e26d3073f744135a8d5b56023a107e323d32b5e7cb2e101c9e6`（dirty 工作树，提交 `331bf88`）。
- 原生编译：`bridge.py build` → 退出 0。
- Creo 12.4.0.0 实机：H05/H07/H08/H09/H10/H12 均在本机单会话串行通道取得证据（H09 22 项、H10 46 项、H12 38 项，H05/H07/H08 见各自证据文件）；未启动/关闭 Creo、未清 unknown 保护、未做故障注入。
- 打包：种子包与源码包按固定顺序生成，四个附件（两个 ZIP 与两个 `.zip.sha256`）齐全；SHA256 见下节。
- 源码包解压全量单测：解压到短路径 `C:\i0184\MCP_CREO_MechDog`（无 `.git/`，自建 venv 安装 `requirements.txt` 后 `pip install --no-deps -e .`），`python -m unittest discover -s tests` → **2943 项，0 失败 0 错误，3 项 SDK 检查跳过**（258.008 秒）。

## 兼容性与升级

- 服务标识、MCP 工具名、既有计划 schema 与种子目录格式不变；公开工具仍 104，`creo_quilt_merge` 与 `surface_round` 仍由能力门禁隐藏；无需修改客户端配置。
- H05/H07 为不可用结论，门禁与错误文案保持；未新增 opt-in，也没有把反证写成能力。
- 种子包与源码包按同一版本成对发布，`seed_manifest.json` 的 `compatible_server_version` 为 `0.18.4`；种子文件本身未变，0.18.4 服务可读取旧 0.18.3 种子包，发布附件以新版为准。

## 环境

- Windows x64；Creo 12.4.0.0；匹配的 Creo Toolkit SDK；MSVC x64 构建工具；Python 3.12.14（`.venv`）。
- 实机证据为本机单会话串行通道，`auto_start_creo=false`；本记录的门禁未连接 Creo。

## 未测范围与未完成项

- **未完成**：百叶、成形、hem、jog、格栅孔、凸台/铰链/门板耳与 corner relief；任意非平面闭合边界 `surface_fill`；独立 quilt 偏置；公开曲面边圆角工具与曲率梳/斑马纹；五爪整瓶（筒身+五爪+瓶底）整链实体化；H03 逐片缝合。
- **H09**：未测 Creo 9/10、非 mm、90° 球带、显式外部基准轴与非 X 轴/倾斜轴；0.3 mm 壁厚整链与球冠边缘加厚自交边界未验。
- **H10**：未测 Creo 9/10、非 mm、非平面或弯曲成员；已加厚成员不能重新参与组级测量（`contour_edge_visit_failed`）。
- **H05**：Creo 10 从未尝试；其他凸台形状、板厚与更大重叠、多凸台同时 union 的失败顺序未验；反向 union 后能否恢复钣金身份未尝试。
- **H07/H08**：H07 只覆盖 3 个候选树与 mm 单位；H08 未取得 quilt 边 id（`PRO_ROUND_REF_EDGE` 未试），变半径/full/过渡、圆角后继续 thicken/solidify、G1 实测均未验。
- **H12**：busy/`unknown_outcome`、真实断流、Creo 已退出快照未验；BUG-115 原生 −4 根因仍开放。
- **Creo 9/10 与 WorkBuddy**：本机无 Creo 9 SDK，Creo 10 未复测；WorkBuddy 公开 MCP 黑盒未执行。

## 附件

四个附件（文件名与完整 SHA256）：

- `MCP_CREO_MechDog-0.18.4-source.zip`（8 752 689 字节）：`81ff64939c9b14ae94635bb49928664526d8fd4b64bda25836381320eb0f8f4f`
- `MCP_CREO_MechDog-0.18.4-source.zip.sha256`（101 字节）：`be337e203d0a0e9e2edfc9d7eeeaa0fa074df8be0eb1ed7f8fe1f3636704e0e5`
- `MCP_CREO_MechDog-0.18.4-seed-library.zip`（493 442 字节）：`1a030983c448d1f76cf5b74d878abce653e5d389ff939468b5cd314b43eb8647`
- `MCP_CREO_MechDog-0.18.4-seed-library.zip.sha256`（107 字节）：`168f7f4a277ad8b92d6b039839ed73626bb2af5ef66d85bcacbceeff27623aca`

发布核对与逐 ID 状态见 [RELEASE-0.18.4](validation/RELEASE-0.18.4.md)。
