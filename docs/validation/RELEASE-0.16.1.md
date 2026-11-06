# 0.16.1 发布记录（2026-11-06）

- 条目：[DEV-069](../work-items/DEV-069.md)（0.13.0/0.14.0 反馈修复批）——R01/BUG-112 偏置距离闸门、R03/FEAT-058 板厚几何兜底与上下文修正、R05/BUG-045 旋转矩阵准入诊断、R13/BUG-114 失败清理事务归因、R04/FEAT-023 查询协议补证、R02/BUG-113 定向复现驱动、R09/FEAT-014 切角定标与 native_planar、R12/FEAT-007 长轮询实机；PATCH 性质，公开工具仍 **100**，无新增/删除工具。
- 基线：上一已发布版本 **0.16.0**（`main` 提交 `4517e36`，标签 `v0.16.0`，见 [RELEASE-0.16.0](RELEASE-0.16.0.md)）。
- 开发分支：`codex/DEV-069-feedback-repair`（`a88900c` 源码与单测、`95b9114` R01/R03 实机驱动与证据、后续提交补齐 R09/R12/R13 驱动与文档）；在 `4517e36` 之上 `--no-ff` 合入 `main`（合并提交 `54e064e`）。
- 目标版本：`v0.16.1`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在 Release body 与交付说明。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 原生编译 `bridge.py build` | 退出 0，`build/creo_worker.exe` 重建（`native/surfaces.cpp` 偏置闸门、`native/planar_wall.cpp` 几何兜底、`native/assembly_pose.h` 旋转准入生效） |
| 全量单元测试 `tools/test_unit.py` | **2702 项通过**，0 失败 0 错误（0.16.0 起点 2646，本版新增 56 项）；`build/unit_test_report.json` |
| 语言与格式 `tools/dev_check.py --skip-unit` | `success: true`（24 条 lint、12 个未格式化文件，均未高于 `style-baseline.json`；受检源码指纹 `49856b6b5ccab6700eee45440632729c79a423b4ea857f6db4c0472f32dee5f9`） |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；SHA256 `54ff5dfd58177d58b5748129e562872add6dfa0da25fda85d613e91d274d5a84`；`docs/seed_package.json` 回填后二次构建一致并按记录校验通过 |
| 源码包 `tools/package.py --seed-archive …` | 1413 文件；四个附件闸门通过（两个 sidecar 与 ZIP 摘要一致） |

源码身份：`version.py` = 0.16.1；受测源码为合并提交 `54e064e` 加版本元数据/文档改动（`dirty=true`，仅版本与发布文档，未改产品代码）。**最终受测提交以合入 `main` 的 0.16.1 发布提交为准**，附件由该提交源码生成。

## 实机证据（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 与许可，单 Toolkit 通道串行）

| 项 | 结果 | 报告 |
| --- | --- | --- |
| R01 偏置距离 | 空件 40×20 双侧 ±5 mm 发布 `measured_offset_distance_mm≈5`、`source=volume_over_source_area`；已有实体 `pre_existing_volume`、圆柱 quilt `source_quilt_not_a_single_plane` 且距离 null；27 项通过 | `build/surface_chain/20261106-121417-172300/report.json`，SHA256 `bde1c1c798521c9c892e72b90e75d9749710cb2c2ff18431c6535bf7716528b9` |
| R03 板厚 | 77/77 通过；100×60×1 体积 6000、API 读数 1.0、`wall_created_this_job=true`；185×232×1、同计划 `current_plan`、保存重载 true | `build/planar_wall/20261106T115256Z/adoption_live.json`，SHA256 `7a981a00d11e9698f0dde8c70a622f6d44a0bf8eeb13f02d5e6f2675def39838` |
| R09 六组复跑 | 六组全过、四墙保存重载 true、报告身份块完整 | `build/post090_n05/20261106T203424_b183d2c8/report.json`，SHA256 `bceb73dd7e2ce011bd4246ebd53d71ef1203046da74ffbc7e4f99850f35c9fe4` |
| R09 剩余三项 | native_planar 180×230×1→185×232×1（feature id 不变、保存重载）；四墙 `f_px/f_nx/f_ny/f_py` 建成（终 bbox 185×232.1×80、体积 106499.15656）；自由墙顶面 run 232.0 = 附着边、miter 墙 185.0 vs 177.92、四角缺口 `[6,6]`；矩阵 gap 2.0@R2.54 Δ−424.537 / gap 1.0@R1.5 Δ+542.086；unbend/bend_back/父壁 resize 拒绝/无效边折边回滚全通过 | `build/sheetmetal_planar_box/20261106T212525_1018e92f/report.json`，SHA256 `3fffaf07b9686227cee4e6ef8cd8a1567c084ee57d1f856aed634073a043e607` |
| R13 清理 | 新零件擦除+同名复建、预存同名 victim 不变、已保存件 `not_new_model_job` 回滚、新装配（`set_dimensions{id=999999}` 原生 -23）`erased/absence_verified/cleaned`；四场景 `live_acceptance=true` | `build/bug096_failed_model_cleanup/20261106T213848_df2d8987/report.json`，SHA256 `44ebfebb8280003aeb1018167c0ec780a008c86c6f3c32c2f458c94102a1f31b` |
| R12 长轮询 | `wait_seconds` 0/1/30、到期 `wait_expired=true`、终态提前 6.015 s 返回、31 与 1.5 拒绝且作业不变、客户端取消后同一 job 达终态、第二 stdio 客户端读取同一 job；六项全通过 | `build/job_wait/20261106T214456_b6be82db/report.json`，SHA256 `29df2f631fd2139539864071ca37a41be733be1a6e2c82e703bf26277cba32bd` |
| R02 定向复现 | 12 例全执行、无自动重交；9 例 ready 且三项基线不变；3 例同计划 trim→thicken 报 `-4`（基线不变、保护未释放）→ 登记 BUG-115 | `build/surface_save_recovery/20261106-120635-343700/report.json`，SHA256 `4a4a264ab33bac590aa0fa317f5ebadc726f4f03049cc2433c984a95b18f1d05` |

## 交付清单

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| `offset_distance_status` 三态与 compact 白名单 | ✅ 已合入（需重编） | `native/surfaces.cpp`、`operation_results.py`、`job_projection.py`、单测 |
| `geometry_normal_span` 与 `wall_created_this_job` | ✅ 已合入（需重编） | `native/planar_wall.cpp`、`native_planar_wall.py`、`tests/unit/test_native_planar_wall.py` |
| 旋转准入共享判据与 `precision_class` | ✅ 已合入（需重编） | `rotation_admission.py`、`native/assembly_pose.h`、schema/失败回执 |
| `terminal_effect`/`component_changes` | ✅ 已合入 | `terminal_effect.py`、`component_changes.py`、`generic_bridge.py` |
| R09/R12/R13/R01 live 驱动 | ✅ 已合入 | `tools/test_sheetmetal_planar_box.py`、`tools/test_job_wait_live.py`、`tools/test_failed_model_cleanup.py`、`tools/surface_chain_offset.py` |

## 未验证范围

- Creo 9（本机无 SDK）与 Creo 10 实机；WorkBuddy 公开 MCP 黑盒。
- R12 断流/网络中断未单独注入；R02 外部 Creo 10 原件未取得。
- FEAT-014 relief 材料几何、更大厚度/半径范围、折边高度编辑/删除折边（产品无该操作）；R10 首壁 origin、R11 曲面缺口路线。
- 历史版本、历史证据与已发布附件保持原状，不用本版结果回填。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.16.1-source.zip`、`MCP_CREO_MechDog-0.16.1-source.zip.sha256`、`MCP_CREO_MechDog-0.16.1-seed-library.zip`、`MCP_CREO_MechDog-0.16.1-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.16.1` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

种子包 SHA256：`54ff5dfd58177d58b5748129e562872add6dfa0da25fda85d613e91d274d5a84`。源码包 SHA256：`81745242cc70ecb7e0d7ec561c822be223dbf8f6849f8c50276d83354b372629`。

当前状态：**准备发布**（本文随 0.16.1 发布提交进入 `main`）；标签、Release 链接与附件核对结果记录在发布交付说明。
