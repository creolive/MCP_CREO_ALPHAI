# 0.11.7 反馈逐条映射（S00）

建立：2026-11-04。归档目录：[feedback-0.11.7-2026-11-04](manifest.json)。原始字节见 `originals/`，四件均为逐字节复制，本文只做映射与纠偏，**不修改原件任何字节**。

- 归档时基线：`codex/DEV-067-alphai-plan`，HEAD `376cdbd`，`version.py` = 0.11.7，`session_activity.json` 已修改（非本批内容）。
- 派工依据：[0.11.7 曲面链与反馈完善计划](../../superpowers/plans/2026-11-04-0.11.7-surface-chain-improvement-plan.md)。Sxx/Wxx/Cxx 是派工编号，不是新增台账 ID。
- 台账归属：本批复用 [FEAT-055](../../work-items/FEAT-055.md)、[FEAT-039](../../work-items/FEAT-039.md)、[FEAT-009](../../work-items/FEAT-009.md)、[BUG-101](../../work-items/BUG-101.md)、[BUG-102](../../work-items/BUG-102.md)、[BUG-094](../../work-items/BUG-094.md)、[BUG-095](../../work-items/BUG-095.md)、[FEAT-008](../../work-items/FEAT-008.md)、[BUG-088](../../work-items/BUG-088.md)、[BUG-108](../../work-items/BUG-108.md)、[BUG-109](../../work-items/BUG-109.md)、[BUG-110](../../work-items/BUG-110.md)、[BUG-111](../../work-items/BUG-111.md)、[FEAT-054](../../work-items/FEAT-054.md)、[DEV-045](../../work-items/DEV-045.md)。未新增 ID。

**证据分级（全文统一）**：`已证实` = 本仓库当前源码或本轮离线检查可直接核对；`候选` = 需实机探针判定，契约里只是待验证骨架；`路线失败` = 已有实机证据证明该路线不成立；`未验证` = 本轮未取得证据，不得写成通过。

---

## 一、F01（Creo 10 实机建模验收，刚性平移已修 / G5 六版未动）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| 刚性平移 0.01 mm 放行 + `sketch_shifted` 成功回执 | `native/sketch_coordinates.cpp` 存在 `RIGID_TRANSLATION_LIMIT_MM`/`accepted_rigid`；报告方 Creo 10 实测通过（job `856a5d4c…`） | BUG-108 | 已证实（报告方 Creo 10 证据）；本机 12.4 本轮未复跑 |
| rotation 越界（225°）前置拒绝并给等价角 | schema 层拒绝，报告方实测无 job 生成 | BUG-111 | 已证实 |
| 第 5 个 `keep_original` 副本必失败 | 0.11.7 已定因并写进能力边界；报告方接受"≤4/批 + 重引用 body"口径但建议 schema 前置拒绝 | BUG-111 | 路线已定因；报告方的"schemax 前置拒绝"建议**不采纳**——量不是有效约束（C0—C6 已推翻拆批），前置拒绝会把可用计划挡掉 |
| G5 曲面三 op 六版未动 | `capabilities.REGISTERED_OPERATIONS` 确无 `surface_loft`/`project_curve`/`surface_trim` | FEAT-055 / FEAT-039 | 已证实（能力缺口，非缺陷） |
| 建议先做 `project_curve`（COPYTRIM 族） | 旧 G5 契约 §2.2 已把 COPYTRIM 列为**候选**而非结论；本机未取得可重生成证据 | FEAT-039（S04） | 候选，待探针 |
| 装配失败恢复死路（`reconciliation.py:531`） | 源码核对：装配仍不进入恢复动作集合 | BUG-110 / BUG-108 | 已证实（仍未实现）；本批不修，见 §六 |
| P12 整机建成，体积 +3.83%、单片 +3.41% | 报告方自述两处偏差均在配方侧（剪裁口径 `Z = u·cosα(v)`、草图 Z 极性） | FEAT-054（S09） | 外部结果，非本仓库验收；不得作为精度基准 |

## 二、F02（安装/打包面：无新缺陷，附件缺 sidecar）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| v0.11.7 Release 只有两个 ZIP，缺 `.sha256` sidecar | `tools/package.py`、`tools/package_seeds.py` 已生成 `.zip.sha256`；0.11.7 发布记录只列两个 ZIP | DEV-045（C01） | 已证实：缺口在**上传与远端核对**，不是生成逻辑 |
| 建议把 sidecar 生成并进 `package.py` | 生成已存在，重复开发无收益 | DEV-045（C01） | 建议纠正：改为发布检查单与远端核对条目 |
| 回调注册连续第二十版稳定 | 与本仓库源码无关（安装环境事实） | — | 只记依据，不派工 |
| `MISSING_SDK_HEADER=Probbl.h` 门控正确记录 | 由 BUG-107 门控负责 | BUG-107 | 只记依据 |

## 三、F03（曲面链仍不可用、quilt 引用同码复现）——本批主线

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| `inspect_model` 无 `quilts` 分区，`sections_available` 20 项与 0.11.5 相同 | `model_queries.SECTIONS` 确无 `quilts` | FEAT-055（S01） | 已证实，本批实现 |
| 纯曲面模型 `counts.surfaces=0`、`edges=0` | 原生 `inspection()` 只经活动 body 枚举曲面 | FEAT-055（S01） | 已证实：保留旧字段语义，新增 `counts.quilts` 与 quilt 面/边计数 |
| merge 引用 trim 结果 `ProFeatureGeomitemVisit -4` 两版同码 | `resolve()` 的 `quilt_feature` 分支要求"恰好 1 个 PRO_QUILT 几何项" | FEAT-039（S01/S02/S03） | 已证实的是行为；"-4 的单一含义"**未证实**，不写死翻译 |
| 建议 A：加 `section="quilts"` | 采纳 | FEAT-055（S01） | 已实现（见 S01 交付） |
| 建议 B：放宽 `quilt_feature` 多候选 | 部分采纳：多个候选返回**有界候选清单**并拒绝自动选取，不引入 `require_single` 宽松模式 | FEAT-039（S01） | 已实现（见 S01 交付） |
| 建议"把 -4 翻译成可读原因" | 采纳为上下文诊断：错误信息包含"该特征不含可用 quilt 几何项"+ 原始码 + 候选数 | FEAT-039（S01） | 已实现 |
| 无高层 trim / merge / boundary_blend / quilt_offset | 确认缺失 | FEAT-039（S02/S03/S06/S07） | 见 §五进度 |
| 无 `get_job.wait_seconds` | `creo_get_job` 签名无该参数 | BUG-109（C04） | 未实现，本批不排 |
| `verify_model_start` 吃 60% 无子阶段 | 计时归属缺陷 | BUG-109（C04） | 未实现，本批不排 |
| connect 期间 `idle_seconds=null` | 无 stage 计时源 | BUG-109（C04） | 未实现，本批不排 |
| 终态与运行态进度字段名不统一 | 设计取舍 | BUG-109（C04） | 未实现，本批不排 |
| `loft` 无 `mode:"surface"` | 由 S05 `surface_loft` 承担，不改造既有 solid `loft` | FEAT-009（S05） | 见 §五进度 |

## 四、F04（第 13 轮：R3 保持、R1 焊接本体未动）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| R3 空模型 `preview_status=skipped_no_geometry` 保持 | 现有实现已含该路径 | FEAT-008 / BUG-088（W06） | 报告方正向前置证据；本轮只做回归保持，不重复开发 |
| R1 `gear10.json` add 10 仍 `-1`，失败文案与 0.11.5 逐字相同 | `gear10.json` 原件本轮**不在归档目录**，无法重放 | BUG-101（W01） | 报告方证据；本仓库未验证 |
| 端点焊接本体连续第 6 轮未实现 | 现有 `weldability` 只给风险标记，不焊接 | BUG-101（W01） | 已证实（缺口）；W01 不得以"仅拒绝/诊断"关闭 |
| 吸附对照组本轮未重跑，`1849.8028532376422 mm³` 只作对照 | 历史体积来源，不是本轮成功证据 | BUG-101（W01） | 未验证 |
| N2 flip 成功路径签名 | 源码已有 `requested_flip`/`effective_flip` | BUG-102（W02） | 未复测：既有实现补证，不新增同名字段 |
| D3/D4 angle+offset 拒绝与方向文档 | 源码已有 `angle + 非零 offset` 明确拒绝 | BUG-094（W03） | 未复测：优先补证 |
| D5 origin 偏差诊断 | 源码已有 `sketch_origin_diagnostics`（1e-6 mm 阈值） | BUG-095（W04） | 未复测：优先补证 |
| N3 省略参数不回显实际生效深度 | 现状：schema 默认 `depth_type="blind"`/`depth=1`，无实际值回执 | FEAT-008（W05） | 已证实（缺口） |
| `native_progress` / `verify_stages` 正面观察 | 运行态与终态进度字段已存在 | BUG-109（W06/C04） | 保持项；计时口径归 C04 |
| rollback 与 `failed_model_cleanup.reason="not_new_model_job"` 可靠 | 既有实现 | BUG-096 / BUG-088（W06） | 保持项，不登记为新修复 |

## 五、C01—C04 与 S00—S10、W01—W06 去向

| 派工 | 归属 | 本批动作 | 状态 |
| --- | --- | --- | --- |
| S00 | FEAT-055 | 归档 + 映射 + 台账 + 契约修订 + oracle 纠偏 | 已完成（见本文与 `G5-NATIVE-CONTRACT.md` §0.1/§4.1/§4.6/§5） |
| S01 | FEAT-039/055 | quilts 查询、共享测量、quilt 引用候选修复 | 已实现（离线可验证，实机未验证） |
| S02 | FEAT-039 | 高层 `surface_trim` | 见交付卡 |
| S03 | FEAT-039 | 高层 `quilt_merge` | 见交付卡 |
| S04 | FEAT-039/055 | `project_curve` | 未实现（依赖 COPYTRIM 探针） |
| S05 | FEAT-009/055 | `surface_loft` | 未实现（依赖边界混合探针） |
| S06 | FEAT-039/009 | `boundary_blend` 多方向/连续性 | 未实现 |
| S07 | FEAT-039 | `quilt_offset` | 未实现 |
| S08 | FEAT-039/055 | 曲面链与加厚/实体化集成 | 未实现 |
| S09 | FEAT-054 | P12 配方修正 | 未实现（缺原始 TXT/轮廓完整输入） |
| S10 | FEAT-055 | 验收汇总、能力文档与版本交付 | 部分完成（开发分支，不合 main、不发布） |
| C01 | DEV-045 | `.sha256` sidecar 上传与远端核对 | 未实现（生成逻辑已存在，不重复开发） |
| C02 | BUG-111 | 撤销"≤4/批"建议、修正选集诊断计数 | 未收取（分支 `codex/BUG-111-doc-and-counts-fix` 当前未合入 `codex/DEV-067-alphai-plan`；需求取未合部分时按 C02 处理） |
| C03 | BUG-108 / BUG-110 | 刚体平移与 ack 成功路径补证 | 未执行（需实机窗口） |
| C04 | BUG-109 / FEAT-007 | 计时归属、`wait_seconds`、终态进度兼容新增 | 未实现 |
| W01 | BUG-101 | P1 端点焊接本体 | 未实现（本轮只交付契约建议，不改几何） |
| W02 | BUG-102 | N2 成功路径复核 | 未执行（未复测） |
| W03 | BUG-094 | D3/D4 拒绝与方向文档 | 未执行（未复测） |
| W04 | BUG-095 | D5 诊断贯通复核 | 未执行（未复测） |
| W05 | FEAT-008 | N3 省略参数实际生效回执 | 未实现 |
| W06 | FEAT-008 / BUG-088 | R3 与进度/回滚保持回归 | 未执行 |

## 六、对旧建议的纠正（不改原件）

1. **"G5 曲面三 op 需要 10 ops 达到 P12 精度"**：只作对照价值，不承诺 op 数与精度；P12 偏差已由报告方归因到配方侧。
2. **"放宽 `quilt_feature` 到多候选自动选择"**：不采纳自动选取。多个候选必须返回有界清单并要求显式 ID，否则会把"猜错面"变成静默错误。
3. **"缝合公差 0.01 mm 内封闭"**：`closed` 只表达实测闭合性，不得由 `closed=false` 反推公差数值；公差是否生效必须由实测间隙支撑。
4. **"每批 ≤4 个 keep_original 副本"**：已由 BUG-111 推翻，不再作为建议；本批不新增数量约束，也不做 schema 前置拒绝。
5. **旧投影 oracle"高 20 mm 圆柱承载长 30 mm 源线"**：几何上不自洽（源线长于承载面高度），已改为 40×20 平面、z=10 的 30 mm 直线沿 −Z 投影到 z=0；圆柱用例另列并标注"有效域与多交点待定义"。
6. **跨模型比较 ID 数字证明两侧不同**：不再作为验收判据。O3 改为比较面积、位置与有符号偏移；同一模型内两次保留侧运行时才比较 `kept_quilt_id` 是否不同。

## 七、缺件与未验证清单

- `gear10.json`、`gear10_snapped.json` 与原始草图请求：本轮归档目录不含，W01 只能用合成夹具推进，原案保持未验证；不得把任意 10 环体积套用 `1849.8028532376422`。
- P12 原始 TXT v1.2、N01 轮廓与 α(v) 定义：本批未取得，S09 不得声称原案已复现。
- 本机 Creo 会话：归档时未运行（仅 `creoagent` 进程），本轮全部原生改动为**编译级验证**，建模/保存重载/回滚均未验证。
- Creo 10 / Creo 9：本轮无证据，历史结论按各自日期保留。
- WorkBuddy 黑盒：本批未执行。
