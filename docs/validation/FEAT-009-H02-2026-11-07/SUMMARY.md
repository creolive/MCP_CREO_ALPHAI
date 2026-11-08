# FEAT-009/H02 两截面直纹曲面放样：Creo 12.4 实机证据

日期：2026-11-07（Asia/Shanghai）。条目：[FEAT-009](../work-items/FEAT-009.md) / [DEV-074](../work-items/DEV-074.md) H02。分支：`codex/DEV-074-feedback0174-offline`，取证时 HEAD `c4948d3`（本轮改动未提交）。环境：Windows x64、Creo 12.4.0.0、匹配 Toolkit SDK、`auto_start_creo=false`、用户已手工启动并授权会话。构建：`bridge.py build` 退出 0。

## 结论

路线 A（文档树直接创建）**成立**。`Probbl.h` 的边界混合树在 **INCOMPLETE 创建 → `ProFeatureElemtreeExtract` → `ProFeatureWithoptionsRedefine`** 流程下可再生成，产出 1 个开放 datum-surface quilt，面积与闭式解一致。未使用路线 B（面板宏曲面开关），也未放宽任何既有门禁。

## 为什么 2026-11-01 的 P1 失败

旧探针在创建前把 `PRO_E_EXT_SURF_CUT_SOLID_TYPE`、`PRO_E_BNBLN_TAN_COND_TYPE`、`PRO_E_BNBLN_TAN_FLD_TYPE` 写进树（契约 §2.1 明确禁止"猜"这些值），得到 `create=0` 但 `status=6 (PRO_FEAT_UNREGENERATED)`、无 geometry item。

本轮按 §2.1 只建裸骨架（FEATURE_TYPE/FORM/DTM_SRF_TYPE/NAME + BNBLN_CURVES→1DIR→DIR_CURVES→CHAIN_HOLDER→CURVE_COLLECTION_APPL），用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 创建后抽取树，内核自行补齐了切线条件与表面类型，再 redefine 即 ACTIVE。首跑收据（[first_run_loft_receipt.json](first_run_loft_receipt.json)）记录的 103 个元素中可见：

| 元素（符号） | 抽取值 |
| --- | --- |
| `PRO_E_FEATURE_TYPE` | 942（`PRO_FEAT_DATUM_SURF`） |
| `PRO_E_FEATURE_FORM` | 512（`PRO_USE_SURFS`） |
| `PRO_E_DTM_SRF_TYPE` | 11（`PRO_E_DTM_SRF_TYPE_BND_BLEND`） |
| `PRO_E_EXT_SURF_CUT_SOLID_TYPE` | 942（内核补齐） |
| `PRO_E_BNBLN_CURVES/1DIR/DIR_CURVES` | 661 / 651 / 657，2 个 `PRO_E_STD_CHAIN_HOLDER`（3058） |
| `PRO_E_BNBLN_TAN_COND` | 459 → 4 个 `PRO_E_BNBLN_TNC_BNDRY`，`TAN_COND_TYPE`=1,1,0,0，`TAN_FLD_TYPE`=-1,-1,0,0（内核补齐） |
| `PRO_E_STD_FEATURE_NAME` | `LOFT_SURFACE` |

即：不写切线条件也能再生；旧路线的失败点是**创建前写入的切线/表面类型值与内核默认不一致**，不是元素被拒。

## 实机验收（最终一轮 [live_report.json](live_report.json)）

驱动：`tools/test_surface_loft.py --live --confirm-session-usable`，公开 MCP 工具串行提交；22/22 检查通过。

| 项 | job_id / model_id | 读数 |
| --- | --- | --- |
| 两截面放样（40 mm 直线，相距 20 mm，z=0/20） | `7a29b97ddb564a0e820c90f02b56921f` / `a03f9fbe7b2347f6b1de315947ec9ed8` | `create_code=0`、`extract_code=0`、`feature_type=942`、`feature_status=0`、`quilt_count=1`、`quilt_id=61`、`surface_area_mm2=800.0`、`quilt_closed_native=open`（`ProQuiltVolumeEval=-18`）、`has_solid=false`、`saved_file_reloaded_and_verified=true`（revision 1） |
| 保存重载后查询 | 同上（作业后 `creo_inspect_model`） | 模型恰好 1 个 quilt，`quilt_id=61`、`area_mm2=800.0`，id 与面积均不变 |
| `surface_trim` 基准面 x=20，`keep_side=one` | `caf35a74f1b940b4b7775f21d242bba1`（revision 2） | `area_before_mm2=800.0`、`area_after_mm2=400.0`、`kept_quilt_id=61`、`kept_quilt_source=retrimmed_target_quilt_visit_failed`（沿用既有 -4 回退，非本卡范围） |
| `thicken` 2 mm（新模型先放样，再同模型加厚） | `08aa638831714906a0ca890bde085f20` / `8815013ed0ff43ff91d6dfb7397648de`；`286b88cba21b482d9db76e051a59ec09` | `volume_after_mm3=1599.9999999999995`（800 × 2，差 <1e-9），保存重载 true |
| `surface_trim` 基准面 x=20，`keep_side=two`（独立模型） | `7ad3e82019de4a9e804e444bc2ac1ab4` / `1246edda397e40f78f396955ef305be5` | `area_after_mm2=400.0`；与 one 侧合计 800.0（±1.0） |

## 实测到的顺序约束

在已加厚（有实体）的同一模型上再对该 quilt 执行 `surface_trim`，`ProFeatureWithoptionsCreate` 返回 **-1**（job `ddf1f332f8de4c33ac7a4a1c82057830`，`execute_surface_trim`）。加厚先消费/实体化该 quilt，后续修剪失败。最终验收因此把 trim 放在 thicken 之前，并用独立模型分别验证两侧。本轮未继续排查该顺序问题，未把它归因于 `surface_loft`，也未据此改动既有 trim/thicken 逻辑。

## 覆盖范围与未验证

- 只验证：2 条单曲线草图截面、平行平面、straight、开放 quilt、无实体、保存重载、x=20 两侧修剪、2 mm 加厚。
- 未验证：≥3 截面、smooth、闭合、相切/曲率连续性、非平行/扭转截面、曲面截面（圆弧）放样、Creo 9/10 实机、字面 erase 后重载、同一模型内先加厚再修剪。
- 本轮在会话中留下了若干未删除的测试模型（既有驱动约定交由会话清理策略处理），未执行 erase/清 unknown。

## 改动文件

`native/surface_loft.cpp`（新增）、`native/generic.cpp`（include + 分派）、`src/creo_mechdog/surface_ops.py`、`src/creo_mechdog/schema.py`、`src/creo_mechdog/capabilities.py`、`src/creo_mechdog/job_projection.py`、`server.py`、`tools/test_surface_loft.py`、`tests/unit/test_surface_loft_schema.py`，以及本目录与 FEAT-009 / G5 契约 / DEV-074 交接文档。
