# 0.12.0 反馈逐条映射（Q00）

建立：2026-11-06。归档目录：[feedback-0.12.0-2026-11-06](manifest.json)。原始字节见 `originals/`，四件均为逐字节复制，本文只做映射与纠偏，**不修改原件任何字节**。

- 归档时基线：`codex/FEAT-039-w02-w06-live`，HEAD `7002575`，`version.py` = 0.14.0，公开工具 100；工作区仅文档改动与 `.trae/`，均不入归档。
- 来源目录 `C:\Users\Administrator\Downloads\0.12.0` 混装两个报告版本：F01 标题写 0.11.7（报告方命名），内容与 `feedback-0.11.7-2026-11-04` 的四件**均不相同**，故归档在本批而非追加到旧批。四件均**未在既有任何归档目录出现过**。
- 派工依据：[0.12.0 反馈剩余工作与验收计划](../../superpowers/plans/2026-11-04-0.12.0-feedback-reconciliation-plan.md)；Qxx 是派工编号，不是新增台账 ID。并行的 [DEV-069](../../work-items/DEV-069.md) 批（0.13.0 反馈）已把 Q01—Q06 拆成 R01—R12，执行入口以那份计划为准。
- 台账归属：本批复用 [FEAT-055](../../work-items/FEAT-055.md)、[FEAT-039](../../work-items/FEAT-039.md)、[FEAT-058](../../work-items/FEAT-058.md)、[FEAT-008](../../work-items/FEAT-008.md)、[FEAT-012](../../work-items/FEAT-012.md)、[FEAT-023](../../work-items/FEAT-023.md)、[FEAT-045](../../work-items/FEAT-045.md)、[FEAT-031](../../work-items/FEAT-031.md)、[FEAT-052](../../work-items/FEAT-052.md)、[FEAT-054](../../work-items/FEAT-054.md)、[FEAT-001](../../work-items/FEAT-001.md)、[FEAT-062](../../work-items/FEAT-062.md)、[FEAT-014](../../work-items/FEAT-014.md)、[BUG-045](../../work-items/BUG-045.md)、[BUG-009](../../work-items/BUG-009.md)、[BUG-060](../../work-items/BUG-060.md)、[BUG-061](../../work-items/BUG-061.md)、[BUG-091](../../work-items/BUG-091.md)、[BUG-101](../../work-items/BUG-101.md)、[BUG-103](../../work-items/BUG-103.md)、[BUG-112](../../work-items/BUG-112.md)、[DEV-045](../../work-items/DEV-045.md)、[DEV-061](../../work-items/DEV-061.md)。未新增 ID。

**证据分级（全文统一）**：`已证实` = 本仓库当前源码或本轮离线检查可直接核对；`已闭环` = 已在后续版本交付并有发布/实机证据；`候选` = 需实机探针判定；`未验证` = 本轮未取得证据，不得写成通过。

---

## 一、F01（报告标题 0.11.7：Creo 10 底盘重建，70 实例）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| P-1 `rotation_matrix` 行/列约定未声明，整机转置不报错 | `capabilities.py` 装配段已写明 "row vectors local to parent"，与实测生效方向一致；`rotation_convention` 开关与读回 4×4 `transform` 回显仍未做 | BUG-045 / FEAT-012（Q02→R05） | 部分：文档已澄清；回显未实现 |
| P-2 非置换阵 `ProAsmcompAssemble` 返回 −2、`operations[31].error={}`、整批回滚 | `schema.py::_rotation_matrix` 已有正交 1e-6 与 det=+1 校验（报告方残差 3e-8 仍在阈值内）；2026-11-06 新增 `failed_operation`：回显 `input_matrix`（4×4 行向量）、`matrix_source`、`determinant`、`orthogonality_residual` 与 `pro_error`/`pro_error_source`，不自动修正，仍整批原子回滚 | BUG-045 / FEAT-012 / [FEAT-008](../../work-items/FEAT-008.md)（Q02→R05） | 已实现（离线单测 24 项）；实机 −2 未复现 |
| P-3 拉伸/切除失败只有 `Regeneration produced a failed...`，`failed_operation=null` | 2026-11-06 新增 `failed_operation`（14 键：index/operation/stage/feature_label/sketch_name/toolkit_call/pro_error/pro_error_source/message+截断标记/矩阵四键），原生在失败收尾发布、Python 对旧执行器按索引回填；`bridge.py` 与 `native/generic.cpp` 的 `failed_operation_index` 仍保留 | FEAT-008（Q02→R05） | 已实现（离线单测 24 项）；实机失败场景未跑 |
| P-4 `through_all` 仍要求并回显 `depth=1.0`；方向朝外时只说 Regeneration 失败 | 0.14.0 的 W05 已让 `depth` 可省略：blind 下 `requested_depth_mm=null`、`effective=blind/1.0 mm`、`defaulted_fields=["depth","depth_type"]`；`through_all` 下 `effective_depth_mm=null`（单测覆盖）。`depth_ignored` 显式声明与"方向未命中材料"提示仍未做 | FEAT-008（Q06→R04） | 部分 |
| P-5 `creo_get_job(detail="compact")` 仍内联完整 `geometry_deviation`；`list_jobs` compact 内联完整 result | `geometry_deviation` 自 0.11.x 起已按 `sample≤20 + total/truncated` 投影；2026-11-06 新增 `sections` 选择器（`compact_sections.py`）：只保留点名的结果块/操作块，响应给 `sections_applied` 与 `omitted_sections`，证据字段恒保留，投影先于 32 KiB 预算，未知块在读取 job 前拒绝 | FEAT-023 / FEAT-008（Q06→R04） | 已实现（离线单测 14 项，109 项回归通过）；实机与客户端未验 |
| P-6 装配检查无 `bbox`（零件有 `bodies[].bbox`） | `model_queries` 装配段无 `bbox`；`assembly_pose.h` 未接 `ProSolidOutlineGet` | FEAT-045（Q06） | 未实现 |
| P-7 `components[].model_name` 无 `source_model_id`，`model.json` 无组件绑定表 | `appearance` 绑定表已有 `source_model_id`（FEAT-052）；装配组件记录本身未回填 | FEAT-045 / FEAT-052（Q06） | 部分 |
| P-8 `session_status` 返回 `connected=true` 但 `session_health.status="unknown"`、`reason="session_identity_stale"` | `session_health.py:512` 仍返回该组合 | BUG-091 / FEAT-001（Q06→R06） | 未实现 |
| P-9 空闲时 `toolkit_busy`、`blocking_operation="session_status"` | 单通道语义与内部探测占通道未改 | BUG-009（Q06→R06） | 未实现（保留边界） |
| P-10 managed 模型无 delete/rename，返工只能换名 | `rename` 仍归 [FEAT-062](../../work-items/FEAT-062.md)，managed delete 仅登记 | FEAT-062（Q06） | 未实现 |
| P-11 `execute_plan` 提交响应回显全部 op（~25 KB） | 提交响应仍含入参回显 | FEAT-008（Q06→R04） | 未实现 |
| 基准面局部坐标（XZ 法向 −Y） | 已写入能力边界与语法参考 | FEAT-008 | 已证实（文档项） |

## 二、F02（安装/打包面：sidecar 连续第二次缺失）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| v0.12.0 Release 只有两个 ZIP、无 `.sha256` sidecar | `tools/package.py` 本地已生成 sidecar；0.12.0 发布只上传两件 | DEV-045（Q00/C01） | 已闭环：0.13.0 与 0.14.0 均四附件上传，并用 `tools/check_release_assets.py --tag <tag>` 远端核对 |
| 建议把 sidecar 上传并入脚本或写进 RELEASING 硬核对 | 现行 [RELEASING.md](../../development/RELEASING.md) 第 5 步与发布记录已要求逐个列名上传四件并远端核对 | DEV-045 | 已采纳并执行；自动闸门另见 [DEV-070](../../work-items/DEV-070.md) |
| 种子闸门顺序与五种前置失败 | 0.12.0 已交付，0.13.0/0.14.0 沿用 | DEV-061 | 已闭环 |
| 0.12.0 两包摘要与 Release body 一致 | 历史事实，保留 | DEV-045 | 只记依据 |
| 0.12.0 主体：新增两钣金工具、实机 67/67、Creo 10 零补丁编译 | 0.12.0 发布记录 | FEAT-058 | 已发布 |

## 三、F03（Creo 10 实机：板厚回读结构性缺失，G5 第七版）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| 板厚回读：SDK 未声明 `ProSmtBodyThicknessValueGet`，`thickness_loaded_mm`/`thickness_measured_mm` 恒 null | `native/planar_wall.cpp` 仍以 `#ifdef MECHDOG_HAS_ProSmtBodyThicknessValueGet` 编译开关跳过体测量，未知时发布 null | FEAT-058（Q01→R03） | 未实现 |
| resize 的"存档板厚不符"守卫在本机永不触发（静默降级） | 守卫依赖同一未声明的体测量通道 | FEAT-058（Q01→R03） | 未实现（守卫存在但无效） |
| 建议用 `volume/(length×width)` 反推板厚、`thickness_source="volume_derived"` | 未采用；报告方实测两例精确（19200/(120×80)、23400/(130×90)） | FEAT-058（Q01→R03） | 未实现（本轮计划要求以真实几何校验为优先，参数/体积不能单独自证） |
| 回执应区分"SDK 不支持"与"墙体异常" | 尚无 `thickness_readback` 可机读原因 | FEAT-058（Q01→R03） | 未实现 |
| G5 三 op（`surface_loft`/`project_curve`/`surface_trim`）第七版缺席 | 0.13.0 已交付 `creo_surface_trim`、`creo_project_curve`、`creo_surface_offset`；`surface_loft` 仍缺 | FEAT-039 / FEAT-009（Q03→R11） | 部分闭环：2/3 已公开，放样仍缺 |
| 钣金拒绝文案缺解锁指引（须 `creo_new_sheetmetal` + `template="native_planar"` 并等终态） | `generic_bridge.py:270` 仍只有 "Sheetmetal operations require an MCP sheetmetal model"，未带下一步 | FEAT-058（Q01） | 未实现 |
| 同作业 create→resize 的 `thickness_loaded_mm=null` 与结构性 null 无法区分 | 同板厚回读缺口 | FEAT-058（Q01→R03） | 未实现 |
| P12 已装机、体积 +3.83% 归因配方侧；G5 缺席下无新增助力 | 报告方自述，非本仓库验收 | FEAT-054（Q03） | 外部结果，不作精度基准 |
| recolor 80/80、12 族、换件后族归属正确 | 0.11.0 能力，实机回归 | FEAT-052 | 报告方正向前置证据，不重复开发 |

## 四、F04（第十一轮：单线首壁仅两端可挂折边）

| 原件条目 | 本轮核对 | 归属 | 状态 |
| --- | --- | --- | --- |
| R1/S5 首壁与底板保持（V=42 920、cog `[0,0,0.5]`） | 0.12.0 实机通过 | FEAT-058 | 已闭环 |
| N3 preview 正常（`written`、`file_check` 全绿） | 0.14.0 的 W06 只读预览实机 `preview_acceptance="passed"` | FEAT-008（Q06） | 已闭环 |
| 诊断增强（`wall_contract`/`weldability`/`geometry_deviation`/`verify_stages`/`datum_display`/`native_progress`） | 均在册，报告方肯定 | FEAT-058 / FEAT-008 | 保持项 |
| R2/S3 四壁第 3 道折边失败，根因为"单线首壁只有与草图线垂直的两端边可挂"（平行长边 `ProSmtedgeContourGet` 报 −8） | 报告方定因；本仓库未独立复现同一 `-8`，`wall_contract` 字段在册 | BUG-103 / FEAT-014（Q05→R09） | 已定因（报告方证据），未实现 |
| 建议支持闭合矩形/闭合多段首壁（TXT §4.1 原意），顺带支持异形底板 | `sheetmetal_wall` 仍只接受单线/开口轮廓 | FEAT-014（Q05→R09） | 未实现 |
| 建议 `edges` 给 `flange_available` 标记、补 bend relief | 未实现 | FEAT-014（Q05→R09） | 未实现 |
| 建议文档说明单线首壁仅端点可挂 | 未写入能力边界 | FEAT-014（Q05→R09） | 未实现 |
| `wall_contract.part_thickness_synced` 语义待说明 | 未写文档 | FEAT-058 | 未实现（文档项） |
| S2 `flip` 无效/折边方向不可控 | 0.8.5 已交付折边方向语义，报告方仍报无效 | FEAT-014（Q05→R09） | 部分（历史项，需定向复测） |
| S6 `unbend.fixed_surface` 不接受 datum_plane | 未实现 | BUG-060（Q05） | 未实现 |
| P3 dict plane `offset≠0` 被拒 | 未实现 | BUG-061（Q06） | 未实现 |
| P5 装配旋转欧拉角反手 | 同 P-1 的行/列约定问题；`failed_operation` 的 `input_matrix`/`matrix_source` 现可回显实际送入内核的矩阵，便于判定是调用方写错还是约定不符 | BUG-045（Q02→R05） | 部分（回显已实现，约定未改） |
| P11 无 `native_bundle` 打包导出 | 0.8.x 起已交付 `creo_export_model(format="native_bundle")`，两段式实机通过 | FEAT-031 | 已闭环（嵌套/外部引用仍开放） |

## 五、Q00—Q07 去向

| 派工 | 归属 | 本批动作 | 状态 |
| --- | --- | --- | --- |
| Q00 | FEAT-055 | 四件逐字节归档 + 逐条映射 + 台账回填 | 已完成（见本文与 `manifest.json`） |
| Q01 | FEAT-058 | 板厚几何校验与回执区分 | 未实现（执行入口 DEV-069 R03） |
| Q02 | FEAT-012/008 | 结构化失败诊断与矩阵精度 | 已实现（离线）；实机失败场景未验（R05） |
| Q03 | FEAT-039/009/054 | 曲面剩余分支 | 部分（R01/R11） |
| Q04 | BUG-101 | 端点焊接余项 | 未实现 |
| Q05 | BUG-103/FEAT-014 | 四壁与多道折边 | 定因，未实现（R09） |
| Q06 | FEAT-023/008/045 | 回执与补证余项 | 部分：`sections` 与失败上下文已实现（离线），装配 bbox/回指/会话健康仍缺（R04/R06/R12） |
| Q07 | DEV-067 | alphai 分支接续 | 未集成 |

## 六、对旧建议的纠正（不改原件）

1. **"板厚用 `volume/(length×width)` 反推即可"**：接受作为**辅助一致性检查**，不接受作为唯一证据。本项目规则要求几何校验优先，参数/体积不能单独自证；平面空件成立不等于任意壁或带孔壁成立。Creo 10 的真实几何兜底需满足 Q01 的适用前提。
2. **"提交期做旋转阵正交化/归一化自愈"**：不采纳自动修正。`schema.py` 已在 1e-6 拒绝非正交阵；对内核 −2 只做有界诊断（矩阵回显、行列式、正交残差、原始码），不静默改写调用方几何。
3. **"失败时 `continue_on_error` 续做"**：不采纳。装配仍整批原子回滚，避免部分装配产生不可回收的组件所有权；诊断改由失败项回执承担。
4. **"每次失败自动 `rotation_convention` 双解回放"**：不做。约定已固定为行向量并写入能力边界，双解尝试会把错误掩盖成"猜对"。
5. **"释放内嵌 `depth` 于 `through_all`"**：0.14.0 已让 `depth` 可省略（blind 默认），但 `through_all` 是否忽略 `depth` 仍需按 Q06 单独定契约，不凭报告一句话改公开语义。

## 七、旧 S/W 编号历史映射（不新增 ID）

Sxx/Wxx 只是 [FEAT-039](../../work-items/FEAT-039.md) 的派工编号，不是台账 ID。后续按行为名称派工，重新编号不改变归属：

| 旧编号 | 行为 | 归属 | 交付版本 |
| --- | --- | --- | --- |
| S01 | quilt 引用解析与共享测量底座 | FEAT-039 | 0.13.0 |
| S02 | 曲面修剪 `creo_surface_trim` | FEAT-039 | 0.13.0 |
| S03 | 合并 join（`creo_quilt_merge`） | FEAT-039 | 未交付（门禁） |
| S04 | 投影曲线 `creo_project_curve` | FEAT-039 | 0.13.0 |
| S05 | 曲面扫掠 / 多截面放样 | FEAT-039 / [FEAT-009](../../work-items/FEAT-009.md) | 扫掠 0.13.0；放样未交付 |
| S06 | 实体化判据 | FEAT-039 | 0.13.0 |
| S07 | 偏置 `creo_surface_offset` | FEAT-039 | 0.13.0（trim `offset_mm` 仍门禁） |
| S08 | 完整链路与示例 | FEAT-039 | 0.13.0 |
| S09 | 曲面模块化拆分 | FEAT-039 | 0.13.0 |
| S10 | 集成与发布 | FEAT-039 | 0.13.0 |
| W01 | 端点焊接本体（坐标规整路线） | [BUG-101](../../work-items/BUG-101.md) | 0.13.0（圆弧端点仍跳过） |
| W02 | 拔模双向与 `effective_flip` | [BUG-102](../../work-items/BUG-102.md) | 0.14.0 补证 |
| W03 | 基准面方向矩阵与两入口拒绝 | [BUG-094](../../work-items/BUG-094.md) | 0.14.0 补证 |
| W04 | 草图 origin 偏差矩阵 | [BUG-095](../../work-items/BUG-095.md) | 0.14.0 补证 |
| W05 | `extrude_depth` requested/effective 回执 | FEAT-039 | 0.14.0 |
| W06 | 只读预览与失败编辑回滚 | FEAT-039 | 0.14.0 |

## 八、缺件与未验证清单

- F01 的 31 零件 IR 与 70 实例源装配文本：**未归档**，本轮无法重放底盘重建；报告中的体积/质心/锚点数值只作对照来源，不是本仓库验收。
- F04 的模型 `acc120_sm` 与 TXT §4.1 原始配方：未归档；四壁根因只引用报告方证据，本仓库未独立复现 `ProSmtedgeContourGet -8`。
- `gear10.json`、P12 原始 TXT v1.2 与 N01 轮廓：仍缺（见 `feedback-0.11.7-2026-11-04` 同项）。
- 本机 Creo 会话：归档时未运行；本轮全部结论为源码核对，未连接 Creo、未跑单元测试。
- Creo 10 实机：本机无该环境，F01/F03 的 Creo 10 行为按报告方证据记录，未复测。
- Creo 9：本机无 SDK，未验收；WorkBuddy 黑盒：未执行。
