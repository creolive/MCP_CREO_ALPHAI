# MCP_CREO_MechDog 0.19.0 版本说明

发布日期：2026-11-08。性质：MINOR。本版新增两个公开工具（`creo_surface_round`、`creo_measure_surface_curvature`），并解除门禁重新公开 `creo_quilt_merge`，公开工具 **104→107**；既有工具名称与计划 schema 无不兼容变更。钣金成形类、独立 quilt 偏置与任意非平面边界填充仍为**不可用结论**，门禁保持，不构成本版能力。

## 本版变更

- **FEAT-055 / H08：曲面边圆角，新增公开工具 `creo_surface_round`。** 对同一 quilt 内两个相邻成员面施加恒定半径圆角，由内核判定两面是否共享边。Creo 12.4.0.0 实机：4 面 1200.0 mm² 拉伸曲面 quilt 对相邻面 (62,64) 施加 R3 → **5 面 1187.1238898038469 mm²**（解析 1200−2×3×10+(π/2×3)×10，逐位一致）、开放（`closed=false`）、`has_solid=false`、`solid_surface_count=0`、`saved_file_reloaded_and_verified=true`，重载后面积与面数不变；非相邻面 (62,66) 再生失败（`feature_status=6`）并整体回滚，revision 2→2、面积不变。证据：[EVIDENCE](validation/dev074-h08-h09-live-2026-11-08/EVIDENCE.md)。
- **FEAT-055 / H08：数值曲率与 G1 分析，新增只读公开工具 `creo_measure_surface_curvature`。** 平面 **0.0 /mm**（144/144 采样，`min_curvature_radius_mm=null`、`zero_curvature`）；R8 球面 **0.12500000000000003 /mm**、半径 **7.999999999999998 mm**；相邻垂直平面墙共享边 **G1=90.0°**（阈值 0.5°，`within_g1=false`）。三次只读作业 revision 均为 1（提交前后相同）。Creo Toolkit 没有斑马纹或曲率梳 API，数值分析为等价交付。证据：同上。
- **FEAT-039 / H03：`creo_quilt_merge` 解除门禁并公开（重新启用）。** 根因不是元素树被拒，而是结果 quilt 归属判据：merge 特征 `ProFeatureGeomitemVisit(PRO_QUILT)` 返回 −4，但内核把第二片 join 进**目标 quilt 原地**。改为三级解析（特征 quilt → 成员面所属 quilt → 面积严格增长的目标 quilt），静默 no-op 仍判失败并回滚。实机两片各 400 mm² 共面填充 → 目标 quilt **800.0 mm²**、开放、`saved_file_reloaded_and_verified=true`，同模型 2 mm `thicken` 成功（body 法向跨距 2.0 mm、6 面）；2 mm 不相邻负例 `ProFeatureWithoptionsCreate=-1` 并回滚（两片仍各 400 mm²、revision 1→1）。公开工具 106→107。证据：[EVIDENCE](validation/dev074-h03h07-2026-11-08/EVIDENCE.md)。
- **FEAT-039 / H10：五爪整瓶整链实机通过。** 46 个作业、63 项检查 0 失败：R20×40 筒身 **5026.5482 mm²**、五个 72° 直纹锥扇面各 **274.81017765 mm²**、R8 瓶底 **201.0619 mm²**、R20 瓶盖，经 7 次两片 `quilt_merge` 合成闭合壳 **7858.298125230911 mm²**，组级 `open_edges=0`、`boundary_closed=true`；0.3 mm 加厚 **2357.526186516854 mm³**、2 mm 加厚 **15727.484826184516 mm³**，保存重载 true；未加厚闭合 quilt `solidify` **56799.99517675038 mm³**；加厚体顶缘 R0.1/R0.5 圆角与保存重载成功。证据：[EVIDENCE](validation/dev074-h10-five-claw-2026-11-08/EVIDENCE.md)。
- **FEAT-014：钣金成形类不可用，门禁保持（本轮实机反证）。** corner relief 三变体（矩形 3×3、矩形 1×1、`PARAM`）写在折边特征内时均 create 后再生失败并回滚（revision 2→2、体积不变），同边 `miter_cuts{1,1}` 对照成功；`PRO_FEAT_SMT_SKETCH_FORM` 三种元素树均 `ProFeatureWithoptionsCreate=-1`；本机 Creo 12.4 SDK 无 Hem/Jog 头与特征常量；格栅 cut 与 BUG-046 正证据矛盾，记为未取证；凸台/铰链/门板耳沿用 H05 反证。公开面零变化。证据：[EVIDENCE](validation/dev074-forming-2026-11-08/EVIDENCE.md)。
- **FEAT-039 / H07：独立 quilt 偏置不可用，门禁保持。** `ProFlexOffset.h` 的 `PRO_FEAT_FLX_OGF` 完整树 create=−1；`PRO_FEAT_CR_INCOMPLETE_FEAT` 骨架 create=0/extract=0（36 元素）但 redefine=−1；公开 `creo_geometry_transform` 复制+平移得到的是**平移副本**（沿面内方向距离 0），仅对平面源等价于等距偏置。不新增 `quilt_offset`，`surface_trim` 的 `offset_mm`/`offset_side` 门禁不动。证据：[EVIDENCE](validation/dev074-h03h07-2026-11-08/EVIDENCE.md)。
- **FEAT-039 / H09：任意非平面边界填充恢复门禁。** 平面 4 曲线闭合环（端点间隙 1.88e-31 mm）两次提交均 create=0/extract=0，但实测 `feature_status=6`、quilt 访问 −4、`quilt_count=0`、元素错误 total=0，整体回滚；`surface_boundary_fill` 已移出公开面（公开工具 107→106，随后 H03 解除门禁回到 107），planar fill 未改。证据：[EVIDENCE](validation/dev074-h08-h09-live-2026-11-08/EVIDENCE.md)。

## 兼容性与接口

- 新增 `creo_surface_round`、`creo_measure_surface_curvature` 两个公开工具，并重新公开 `creo_quilt_merge`，公开工具 104→107；能力族 `surface_chain` 的工具清单同步为 8 项。
- `creo_quilt_merge` 只接受 JOIN、恰好两片真实接触或相交的 quilt，结果是被增长的目标 quilt（`result_quilt_source=retrimmed_target_quilt`）；单次三片以上合并、`INTERSECT`、闭合壳体的直接合并未验收（五爪整瓶为 7 次两片调用的链式组合）。
- `creo_surface_round` 只支持恒定半径与两个相邻成员面；无 edge-chain（尚无 quilt 边 id 通道）、变半径、full 或过渡。
- `creo_measure_surface_curvature` 只读，不推进 revision；不提供斑马纹/曲率梳图像。
- 钣金成形类、独立 quilt 偏置与任意非平面边界填充仍不可用，门禁、错误文案与准入拒绝保持；未把反证写成能力。
- 种子目录格式与既有计划 schema 不变；`seed_manifest.json` 的 `compatible_server_version` 为 `0.19.0`，种子文件本身未变。

## 验收摘要

- 离线全量门禁：`tools/dev_check.py --work-item DEV-074` → `success=true`，单测 **3005 项，0 失败 0 错误**；风格存量基线 24 条 lint / 12 个未格式化文件，无新增；源码指纹 `a6d4dc23147a36ce988da0b79c0313be9b3770328cc6edbb3d79373a0455d01b`（dirty 工作树，提交 `2266ea8`）。
- 原生编译：`bridge.py build` → 退出 0。
- Creo 12.4.0.0 实机：H03/H07/H08/H09/H10 与钣金成形类探针均在本机单会话串行通道取得证据；未启动/关闭 Creo、未清 unknown 保护、未做故障注入、未重提已接受作业。
- 打包：种子包与源码包按固定顺序生成，四个附件（两个 ZIP 与两个 `.zip.sha256`）齐全；SHA256 见下节。

## 环境

- Windows x64；Creo 12.4.0.0（release numeric 44）；匹配的 Creo Toolkit SDK；MSVC x64 构建工具；Python 3.12（`.venv`）。
- 实机证据为本机单会话串行通道，`auto_start_creo=false`；本节门禁未连接 Creo。

## 未测范围与未完成项

- **不可用（门禁保持）**：钣金成形类（corner relief、百叶/成形、hem/jog、格栅孔、凸台/铰链/门板耳）、独立 quilt 偏置、任意非平面闭合边界 `surface_fill`。
- **H03**：`INTERSECT`、三片以上单次合并、非 mm、Creo 9/10；被消耗的工具 quilt 在内核里留下不可测记录（属内核行为）。
- **H08**：quilt 边 id 通道（`PRO_ROUND_REF_EDGE`）、变半径/full/过渡、圆角后 thicken/solidify、弯曲 quilt、非 mm、Creo 9/10。
- **H10**：真实凹谷瓣底、非 mm、Creo 9/10；格栅 cut 与 BUG-046 的矛盾未定因。
- **本批未执行**：源码包解压后的全量单测、WorkBuddy 公开 MCP 黑盒验收、Creo 9/10 实机（本机无 Creo 9 SDK，Creo 10 未复测）。

## 附件

四个附件（文件名与完整 SHA256）：

- `MCP_CREO_MechDog-0.19.0-source.zip`（8 908 094 字节）：`9caa479041c2303e5e923faf48d0e5406de516e39050d71495ea3ec8c00a9878`
- `MCP_CREO_MechDog-0.19.0-source.zip.sha256`（101 字节）：`0eb2615c836a8b96655e12c3fc6f5d443e2e9b5d8e209040d79be9cb3c9a2d9e`
- `MCP_CREO_MechDog-0.19.0-seed-library.zip`（493442 字节）：`05859ac1ae89d0c0455f6b4aa8a02a34b232588c4d1b4da74d6842f21041a072`
- `MCP_CREO_MechDog-0.19.0-seed-library.zip.sha256`（107 字节）：`9cce3894e4ebd5ae2f3cfe650334becf83e0f398a62bb5234e179c0ffc7d506b`

源码包内含本说明与发布记录；生成归档时无法写入自身 ZIP 的摘要，包内副本保留回填前占位，工作树与 Release body 以上述最终值为准。

发布核对与逐 ID 状态见 [RELEASE-0.19.0](validation/RELEASE-0.19.0.md)。
