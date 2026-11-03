# 0.11.5 第十三轮反馈归档与逐章映射（R13）

- 归档日期：2026-11-03（Asia/Shanghai）
- 汇总条目：[DEV-065](../work-items/DEV-065.md)（归档、对账与交付编排）
- 基线：主干 `main@b3f6d43`、源码版本 0.11.5（已发布）、公开工具 95；分支 `codex/DEV-065-r13-feedback0115`
- 原件目录：[originals/](originals/)，清单与校验见 [manifest.json](manifest.json)（5/5 长度与 SHA256 与 `C:\Users\Administrator\Downloads\0.11.5` 源文件一致，另做整文件字节序列比对）
- **与既有归档的关系**：本目录是 0.11.5 批次的 5 份反馈原件；[feedback-0.10.0-2026-10-31](feedback-0.10.0-2026-10-31/MAPPING.md)、[feedback-0.10.0-2026-11-01](feedback-0.10.0-2026-11-01/MAPPING.md)、[feedback-0.11.0-2026-11-01](feedback-0.11.0-2026-11-01/MAPPING.md)、[feedback-0.11.1-2026-11-02](feedback-0.11.1-2026-11-02/MAPPING.md) 是前四批，五目录**互不覆盖、互不合并**。
- 本批性质：**归档 + A 组「稳定性与失败闭环」四项实施**。归档与登记不连接 Creo；四项改动先离线实现与单测，再按 BUG-001 会话纪律在本机 Creo 12.4.0.0 按改动点实机取证；Creo 9/10 与 WorkBuddy 一律记未验证。
- 报告方环境：F01 为 Windows 10 x64 / Python 3.13.14 / Creo 9.0.0.0 SDK；F02、F04 为 Windows x64 / Creo 10.0.0.0（`release_numeric=42`）；F03 为 Windows 10 / Creo 9.0.0.0（`release_numeric=41`）；F05 为 Creo 10.0.0.0（`release_numeric=42`，会话指纹 `6470267846245979272`）。全部 95 工具。

## 一、固定 ID 一览

| 固定 ID | 标题 | 状态 | 优先级 | 来源章节 |
| --- | --- | --- | --- | --- |
| [DEV-065](../work-items/DEV-065.md) | 0.11.5 第十三轮反馈归档、对账与交付编排 | 进行中（本批） | P1 | F01–F05 全篇 |
| [BUG-109](../work-items/BUG-109.md) | `verify_model` 阶段无子阶段归因，首建停滞只能等预算到点 | 本批实现 | P1 | F03 §二 |
| [BUG-110](../work-items/BUG-110.md) | 装配作业失败后四个恢复动作全不可用，只能手改登记文件 | 本批实现 | P1 | F02 核心问题 3 |
| [BUG-111](../work-items/BUG-111.md) | `geometry_transform` 第 5 个 `keep_original` 副本必失败，旋转越界无前置校验 | 本批实现 | P1 | F02 核心问题 4 |
| [BUG-108](../work-items/BUG-108.md) | 坐标求解整截面刚体平移被判"几何被改" | 本批修判据（原 R12 登记） | P1 | F02 核心问题 1 |
| [DEV-066](../work-items/DEV-066.md) | `tools/` 硬依赖 git、负例输出与真实失败同形 | 仅登记待规划 | P2 | F01 §一、§二 |

既有卡增量（不新开编号）：[FEAT-054](../work-items/FEAT-054.md)（P12 四带与刚性平移判据的关系）、[FEAT-055](../work-items/FEAT-055.md)（只记 0.11.5 曲面链逐字未变）、[BUG-082](../work-items/BUG-082.md)（Creo 9 官方套件 5/5，可归档外部复测子项）、[BUG-101](../work-items/BUG-101.md)（草图端点缝隙 `gap_detected` 建议）、[BUG-102](../work-items/BUG-102.md)（成功路径 `requested_flip` 仍未修）、[FEAT-007](../work-items/FEAT-007.md)（`wait_seconds` 第三次被提出）、[BUG-034](../work-items/BUG-034.md)/[BUG-017](../work-items/BUG-017.md)（Creo 9 第十轮仍失败）、[BUG-094](../work-items/BUG-094.md)/[BUG-095](../work-items/BUG-095.md)（D3–D5 未复测）。

## 二、逐章映射

### F01 `2026-11-02_CREO_0.11.5_离线证据工具硬依赖git且负例输出易误判.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 结论先行：0.11.5 安装、Creo 9 SDK 编译、种子安装与冒烟全过（95 工具），未发现产品缺陷 | 与 0.11.5 交付事实一致（DEV-002 第三批为纯包化） | 归档记录 |
| §1 现象：无 git 时 `tools/test_unit.py` 2196 项出现 38 errors、traceback 为 `FileNotFoundError: [WinError 2]` | **开放**：`tools/` 多个离线证据脚本以 `subprocess.run(["git", ...], check=True)` 取 `local_provenance()`，无 `which("git")`/异常兜底 | DEV-066（仅登记） |
| §1 影响面：37 个工具调用 git、32 处 `check=True`；受影响为源码 ZIP 安装与精简/离线机器 | 本仓未核对逐文件计数；按报告方 `grep` 结果登记为待核项，不在本批复算 | DEV-066（仅登记） |
| §1 建议 1–3：兜底降级、报错写明原因、README/INSTALL 前置 git | 采纳为待规划方向，本批不实现 | DEV-066、DEV-065 |
| §1 建议 4：仿 `vswhere` 探测常见 git 安装路径 | 仅登记为可选方案 | DEV-066 |
| §1 结论：MCP 服务本体不依赖 git | 与本仓实现一致（服务端无 git 调用） | 归档记录 |
| §二 负例测试 stdout 红字（`ERROR: Seed archive SHA256 ... differs ...`）与真实失败同形、摘要值每次不同 | **开放**：属测试可读性问题，非产品不稳定；本批不实现 | DEV-066（仅登记） |
| §三 升级验证表：Creo 9 SDK 一次通过、`creo_check_environment` 全绿、BUG-090 函数级探测（`ProSmtPartThicknessGet` 在 Creo 9 存在 → 宏为 1） | 外部环境证据；BUG-090 的 Creo 9 方向由报告方补上，Creo 9 实机建模仍为未验收 | BUG-090 增量（只记依据） |
| §三 升级注意：`session_activity.json` 仍被 git 跟踪、运行时追加，升级会覆盖 | **开放**：与 R12 `manifest.json` 记录的已知 dirty 同源；本批不实现，登记待规划 | DEV-066（仅登记） |
| §四 遗留：Creo 9 运行时建模未验收；BUG-034 未复测；`open_lock_file` 初始 `OPEN_EXISTING` 瞬时 WinError 5 建议仍未实装 | 与本仓台账一致；`lock_files.py` 仅覆盖 CREATE 阶段的事实保持，低优先级 | BUG-034、DEV-066 |

### F02 `2026-11-02CREO10.0.0.0-0.11.5-刚性平移仍被拒且G5四版未动.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| 〇 摘要：BUG-107 门控免补丁、`depth_basis` 三键、save origin 引导、斜面草图保持 | **已闭环**：BUG-107 随 0.11.4（`available_headers()`）、FEAT-035 `depth_basis` 随 0.11.2、BUG-106 文案随 0.11.4 | 归档记录 |
| 核心 1 现象：`maximum deviation mm=0.000016` 且回执已含刚性诊断（`rigid`、`translation_mm`）仍拒绝 | **开放**：`native/sketch_coordinates.cpp:368-376` 在 `rigid` 时仍 `throw`；`:724-742` CompleteFeature 阶段同判 | BUG-108（本批修判据） |
| 核心 1 数据：默认 `COORDINATES_DEFAULT_TOLERANCE_MM=1e-5`，求解器刚性平移噪声 1.6e-5 ~ 4e-3 mm | 与 `geometry_deviation.py:29`、`sketch_coordinates.cpp:717` 一致 | BUG-108 |
| 核心 1 对照：同几何 + `geometry_tolerance_mm=0.01` 成功（volume 19,659.70） | 显式容差路径现状正确，本批保留 | BUG-108 |
| 核心 1 建议 1：`rigid == true` 时放行并在回执报平移量 | **采纳（本批）**：`rigid` 且平移在 `RIGID_TRANSLATION_LIMIT_MM=1e-2` 内放行，`accepted_rigid=true`；超限拒绝并写明平移量与上限 | BUG-108 |
| 核心 1 建议 2：默认阈值提到 1e-3，或 coordinates 用形状偏差作判据 | **采纳后一半、拒绝前一半**：改判据为"形状偏差"，保留 1e-5 对形状的严格性；不放宽默认值（放宽会让真实变形过关）。本决策取代 R12 MAPPING §四「`geometry_tolerance_mm` 默认值调整不采纳」的同一结论 | BUG-108（决策） |
| 核心 1 建议 3：成功回执也带 rigid/translation | **采纳（本批）**：`geometry_deviation` 增 `shape_deviation_mm`/`rigid`/`translation_mm`/`residual_mm`/`accepted_rigid`，成功与失败都填；旧字段语义不动 | BUG-108 |
| 核心 1 附：job `fba3fc78…`（拒）、`cd475e22…`（容差放行） | 报告方现场编号，本仓不复用其状态作证据 | 归档记录 |
| 核心 2：G5 `surface_loft`/`project_curve`/`surface_trim` 四版未动，P12 仍 96 ops 切片堆 | **保持待规划**：0.11.5 的 `surface_solid` family scope 与 limits 与 0.11.1 逐字一致 | FEAT-055（只记事实） |
| 核心 3：装配失败后四动作全拒（`reconciliation.py:526`） | **本批实现**：四动作继续限零件/钣金（不触碰组件所有权），另加元数据动作 `ack_failure` 供装配恢复可提交状态 | BUG-110 |
| 核心 4 现象 1：同计划第 5 个 `keep_original` 复制必 `-1`（正角集与负角集同一位置） | **开放，本批复现并定位**：`native/placement.cpp` 复制路径 | BUG-111 |
| 核心 4 现象 2：单独 225° 也 `-1`，45/90/135/180 可过；schema 无范围约束 | **已定位代码事实**：`native/placement.cpp:221-222` 把负角 `+=360`，−135° 被写成 225°；`schema.py:446-497` 只挡 ±360 | BUG-111 |
| 核心 4 建议 2：`rotation` 加 ±180 schema 校验 + 文档，超范围前置拒绝 | **采纳（本批）**：角度归一改 (−180, 180]，schema 两侧加 ±180 前置拒绝并给等价值；属行为收紧 | BUG-111 |
| 核心 4 建议 3：暴露真正的 `body_pattern` | **不采纳（本批）**：属新工具，版本未定；先修第 5 副本与范围校验 | BUG-111（后续候选） |
| 附「能力边界」三条：`extrude mode=cut` 挖轮廓内部、`boolean_bodies` 只接受单 target、`feature_state delete` 需连带自动特征 | 事实正确；文档补充属 C 组，本批不做 | FEAT-033/DEV-066 待规划 |
| 附 P12 实测：单片体积 +3.41%、X 跨度 117.1 超 19、质心 x 符号相反；根因在配方侧（剪裁口径 `cosα`、Z 极性） | 报告方已自行定位为配方问题，非 MCP 缺陷；不回填为 BUG | FEAT-054（只记依据） |

### F03 `2026-11-03_CREO_0.11.5_new_part首建超时卡死verify_model与作者用例精度边界.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| §二 P0 时间线：`PHASE=verify_model` 后 10 分钟无输出；22:46:13 服务端预算到点 → `unknown_outcome`；Creo 转 hung | **开放**：`native/generic.cpp:6272` 一个 `verify_model` 包住再生/巡检/断言/备份保存/擦除/重载/再生/比对；`bridge.py:1364-1369` `generic_timeout_seconds` 默认 600，与 22:36→22:46 吻合 | BUG-109 |
| §二 要点 1：非确定性复现，重发同请求 30 秒成功；0.6.x–0.11.x 有同类记录 | 本仓无同源现场（报告方 native.log 未随包），按"不可区分"而非"必挂"定性 | BUG-109 |
| §二 要点 2：`unknown_outcome` 后恢复链路正确（pending 保护 → inspect → 会话变更拒绝 → 重取证据 → abandon_new） | **已交付能力**：BUG-096/097/098/100 与 0.11.x 恢复链，本批不改语义 | 归档记录 |
| §二 建议 1：`verify_model` 增加阶段级预算与中间日志 | **采纳（本批，改口径）**：做子阶段日志与停滞归因，**不做进程内子阶段强杀**；提前杀 worker 会把"慢但成功"的保存变成新的 unknown_outcome | BUG-109 |
| §二 建议 2：排查 Creo 9 首次执行慢/挂诱因（模板/字体/许可） | 本机无 Creo 9，**保持未定因**；不据此断言版本原因 | BUG-109（未验证） |
| §二 建议 3：并入 BUG-088/BUG-085 分析 | **不合并**：BUG-088 实为预览 raster 输出文件缺失、BUG-085 为断连调查，与本卡不是同一缺陷；只作对照材料引用 | BUG-109（澄清） |
| §三 BUG-082 Creo 9 复测：官方套件 5/5（`onaxis_sector_*` 五例）+ `EDITING_CLOSEOUT_SUCCESS=1` | **采纳**：补上本仓一直缺的外部 Creo 9 证据，可归档关闭该外部复测子项 | BUG-082 增量 |
| §三 手测失败判定：夹具 `round(cos(80°)*10, 6)` 与弧端点差 2.1e-7 mm，属调用方精度不足，非 MCP 缺陷 | 与本仓 `weldability`/簇内间隙诊断口径一致 | BUG-101（只记依据） |
| §三 建议 2：`update_sketch_geometry` 对 <1e-5 mm 缝隙返回 `gap_detected` 与位置 | **开放，本批不实现**（D 组未选）；登记为待规划 | BUG-101 增量 |
| §三 建议 3：文档写明"公共端点用同一全精度值" | 随 D 组一起待规划 | BUG-101、DEV-066 |
| §四.1 种子加载失败信息已按 BUG-034 语义化（sha256/api/stage/release/勿臆断版本） | 与 BUG-034 已交付诊断一致；Creo 9 种子 -16 本身仍失败 | BUG-034 增量 |
| §四.2 `session_health` 质量（damage_signals/next_steps/evidence、120 作业只读扫描） | 0.11.x 已交付能力，本批不改 | 归档记录 |
| §五 历史状态：种子 -16、筋失败、loft 需人工回调、`component_constraints` 写侧重解未排期（BUG-036）、`round` 别名已收口（BUG-019） | 与台账一致；BUG-036 仍不排期 | BUG-034、BUG-017、BUG-036、BUG-019 |
| §六 核心回归：在轴扇形 2094.3951、孔 85.5062、参数 type 52/53、关系 30 | 报告方环境结果，本仓不复用为成交依据 | 归档记录 |
| §七 建议 4：有可追溯来源地重建种子库或提供按目标版本重生成工具链 | 长期方向，本批登记不实现 | BUG-034 增量 |
| §七 建议 5：rib 失败信息区分"版本未验证"与"材料侧/轮廓问题" | 开放，待规划 | BUG-017 增量 |
| job_id：`db7afc8d…`（verify_model 超时）、`d12ea14b…`/`40109df7…`（两段恢复） | 报告方现场编号；其 `native.log` 保留在报告方工作区，未随包提供 | 归档记录（缺件） |

### F04 `2026-11-03CREO10.0.0.0-0.11.5曲面修剪仅低层可达与quilt引用断链.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| §1.1 `creo_capabilities` 分页（32 KiB、`next_cursor`、`snapshot_fingerprint`、600 s 快照） | **已交付**（0.11.1 分页与快照），本批不改 | 归档记录 |
| §1.2 `update_sketch_geometry` 支持 centerline（两次实测 `preserved_feature_id`、偏差 1e-15 量级） | **已交付**（BUG-079/082 链），本批不改 | 归档记录 |
| §1.3 `feature_state` delete 可用（`feature_tombstones`、before/after、`targets_complete`） | **已交付**（0.11.1），本批不改；依赖缺口一次只回一个属 D 组待规划 | FEAT-033/DEV-066 待规划 |
| §1.4 诊断信息密度（`execution_status`/`effect_status`、`material_delta_mm3`、`reference_application`、`profile`、`body_counts`、`preview` 分步码） | 已交付能力，本批只在其上补 `native_progress` | 归档记录、BUG-109 |
| §1.5 通道互斥带 `blocking_*` 与 `owner_snapshot` | 与 busy 契约一致，本批不改 | 归档记录 |
| §1.6 `native/constants.inc` TRIM 常量 53→81 | 本机常量表由 SDK 生成，不提交；属 DEV-055 探测头已备 | 归档记录 |
| §2.1 曲面修剪需手写 10 元素树、漏 `PRO_E_MATERIAL_SIDE` 即再生失败且无缺口提示 | **开放**：无高层封装 | FEAT-055（待规划） |
| §2.2 `inspect_model(section="surfaces")` 对纯曲面返回 `[]`；quilt 无 id；`quilt_feature` 对 trim 结果 `-4` | **开放**：走 `ProSolidBodySurfaceVisit`；`resolve()` 要求恰好 1 个 PRO_QUILT 项 | FEAT-055（待规划） |
| §2.3 缺 `loft{mode:"surface"}`、`boundary_blend`、`quilt_offset`、`quilt_merge`；`surface_solid` scope 与 limits 与 0.3.5 逐字一致 | **确认零推进**：0.11.5 与 0.11.1 capabilities 该家族文字相同 | FEAT-055（只记事实） |
| §3.1 `feature_state` 依赖缺口一次只回一个 | 开放，D 组待规划 | FEAT-033 增量 |
| §3.2 `creo_get_job` 无 `wait_seconds`（16 job 轮询约 50 次） | 开放，D 组待规划；第三次被提出 | FEAT-007 增量 |
| §3.3 纯曲面无面积/封闭性信息（`volume_mm3` 为 null） | 开放，随 FEAT-055 一起 | FEAT-055 |
| §4 MVR 七步（inspect quilts → surface_trim → quilt_merge → quilt_offset → boundary_blend → loft surface → 依赖缺口与 wait_seconds） | 全部登记；本轮不实现 | FEAT-055、FEAT-007、FEAT-033 |
| §5 job 证据：`7045d780…` 修剪成功（features 12→13、保存重载 true）、`97ce4522…` merge 失败 -4 | 报告方现场编号；本仓未复现 | 归档记录（未验证） |

### F05 `20261102_CREO_v0.11.5_失败信息重写与draft_failure落地_preview关闭_端点焊接本身仍未修.md`

| 章节 / 断言 | 当前判定 | 归属 |
| --- | --- | --- |
| §一 R3：空件 `preview_status="skipped_no_geometry"`、codes 全 null、`window:-1` | **已闭环**（0.11.4/0.11.5 交付），P3 关闭 | 归档记录 |
| §一 R1 `gear10.json` → add 10 仍 `-1`，失败信息重写（簇内间隙 8.21534267e-07 mm、指向 weldability、吸附建议） | **诊断已交付**（BUG-101 0.11.2）；端点焊接本身仍未实现 | BUG-101 增量 |
| §一 R2 `surface 67 + angle=10 + flip=true` 仍 `-1`，新增 `draft_failure` 诊断块 | **已交付**（BUG-102 0.11.2），本批不改 | BUG-102 增量 |
| §二 结论：诊断满分落地；`near_tolerance_pairs` 与吸附对照法继续可用 | 与本仓 `weldability.py` 契约一致 | BUG-101 |
| §二 未变：建议 sketch 提交时按 `max_endpoint_gap_mm` 阈值（1e-9 档）自动吸附或前置拒绝 | **开放，本批不实现**；与 F03 §三 的 `gap_detected` 同属 D 组 | BUG-101 增量 |
| §三 `draft_failure` 字段（`angle_deg`/`api`/`classification`/`element_errors`/`requested_flip`/`surface_count`/`note`） | 已交付 | BUG-102 |
| §三 仍待办：`flip=false` 成功时 `draft_geometry.flip` 仍回显 `true`；建议成功路径带 `requested_flip` 或改名 `effective_flip` | **开放（N2）**，D 组待规划 | BUG-102 增量 |
| §五 其他：新 family `job_reporting`（`enabled:null`）、`retry_after_seconds` 1→5、`failed_model_cleanup` 字段、compact `detail_truncated` | 与本仓 0.11.x 回执一致；`job_reporting` 占位未挂工具 | 归档记录 |
| §六 台账：P1 端点焊接未修、P3 已修、P5/P6/N1 已修、N2 未修、D3/D4/D5 未复测、N3 未修 | 与本地台账对应：BUG-101、BUG-102、BUG-094、BUG-095 | 各卡增量 |
| §七 下一轮判据：R1（`gear10` 体积 1849.80285 或吸附/拒绝并引用 weldability）、R2'、D3–D5、N3 | 登记为后续回归判据；本轮只做 A 组 | BUG-101、BUG-102、BUG-094、BUG-095 |

## 三、缺件与不复用

| 项 | 说明 |
| --- | --- |
| F03 的 `native.log` 原件与 `request.json` | 仅给时间线与 `PHASE` 行摘要，文件保留在报告方工作区（`F:\WorkBuddy CREO Space\...\jobs\`），未随包提供；本机无法比对同一现场的日志时序 |
| F03 官方套件报告 `build/editing-closeout/1bbca8ea…/report.json` | 未随包；BUG-082 归档按报告方摘要文字记录，不复制其构建产物 |
| F02/F04/F05 的 job 结果 JSON 与 P12 计划 | 只给 job_id 与摘要，未提供 `request.json`/`native_result.json`；本机只能构造同形态夹具 |
| P12 原始 TXT v1.2 与 580 项 blocked manifest | 仍未到；FEAT-054 的 3 项 unresolved 继续阻塞 |
| 报告方 worker 指纹与本地补丁构建产物 | 不进入本仓库证据链 |

## 四、本批不做

- 曲面链（`inspect_model(section="quilts")`、`surface_trim`、`quilt_merge`、`quilt_offset`、`boundary_blend`、`loft{mode:"surface"}`）——FEAT-055 保持待规划。
- `tools/` 的 git 兜底、负例输出静音、`session_activity.json` 移出跟踪、`lock_files.py` 初始 `OPEN_EXISTING` 兜底——DEV-066 仅登记。
- 端点缝隙 `gap_detected` 与公共端点全精度文档、`feature_state` 完整依赖缺口、`get_job wait_seconds`、draft 成功路径 `requested_flip`、`extrude cut`/`boolean_bodies` 边界文档——D 组与 C 组，待规划。
- 新工具 `body_pattern`、`creo_surface_trim` 等；不新增公开工具，工具数保持 95。
- 装配自动改组件类恢复；`adopt_session_copy`；自动擦除；队列与并发能力。
- WorkBuddy 黑盒、Creo 9/10 实机复测。

## 五、决策取代说明

R12 MAPPING §四 曾记录两条"本批不做"：`geometry_tolerance_mm` 默认值调整（含放宽 1e-5 闸门）与装配四恢复动作扩展。本轮据此**部分取代**：

1. `geometry_tolerance_mm` **默认值仍不调整**（结论不变），但改为在判据层区分"整体平移"与"形状变形"——形状仍按 1e-5 严格拒绝，只有可证刚体平移且平移量 ≤ 1e-2 mm 才放行。这是判据修正，不是阈值放宽。
2. 装配**四个既有恢复动作仍不扩展**（组件所有权不动），新增的是独立元数据动作 `ack_failure`，只把失败模型恢复到可提交状态，不改 revision、不改文件、不改组件。
