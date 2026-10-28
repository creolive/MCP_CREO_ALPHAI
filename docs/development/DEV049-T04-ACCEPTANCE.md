# DEV-049 T04 验收记录：R20／54°／4×6 原斜槽定向回放（2026-10-28）

> **离线阶段完成、实机未执行。** 本记录只覆盖 DEV-049 T04 的离线交付（六例输入、独立积分
> oracle、默认离线双门槛驱动）。**六例未在 Creo 中执行，不得据此宣称六例通过。**

## 一、交付身份与环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-10-28（Asia/Shanghai） |
| 分支 | `codex/dev049-t04-tilted-cut` |
| 依赖提交（基线） | `1a82185360f94baee0c2723bdbb80f4d782a34ea`（DEV-049: integrate T03 installer stderr fix） |
| 任务提交 | 见 `git log` 本次提交 |
| dirty | `true` |
| 版本入口 | `version.py = 0.7.1`（本任务未改） |
| 环境 | Windows x64、Python 3.12.14 |
| 受测源码指纹 | `cdf8972fa5e4e9ec7441406b3c84d510ce07b02a09953bcbbb4d30b75b915cc9`（见离线报告 `provenance.source_fingerprint`） |
| dev_check 受测源码 | `3fece0810be92e55fd4b17e4e754b1eda4aa2d8f144dc526af7f1ec8c2cdf5b3`（`build/development_check.json`） |

dirty 来源：`session_activity.json` 为运行数据（未提交、未 stash、未 checkout），以及本次新增的
两个源码/测试文件。运行数据与源码分开登记。

**未改动项：**`version.py`、`native/**`、生产几何实现、94 个 MCP 工具清单均未改动。

## 二、本阶段交付物

| 文件 | 职责 |
| --- | --- |
| `tools/test_dev049_tilted_cut.py` | 默认离线双门槛驱动；六例输入、独立积分 oracle、内嵌方向/法向语义与 `v = n×u` 检查 |
| `tests/unit/test_dev049_tilted_cut.py` | 35 项离线回归 |
| `docs/development/DEV049-T04-ACCEPTANCE.md` | 本记录 |

## 三、几何基准（以派发表与总计划为准）

- 基体：XY 面 R20 圆正向拉伸 5，`z = 0..5`。
- 面法向 `n = (cos54°, sin54°, 0)`；`u = (sin54°, -cos54°, 0)`；`v = n×u = -Z`。
- 矩形 `u ∈ [-4, 0]`、`v ∈ [-3, 3]`；圆盘内有效高度 **3**。
- 单向期望 `3 × ∫[-4,0] sqrt(400-u²) du = 238.390260127791 mm³`。
- symmetric 双向 **476.780520255582 mm³**；绝对误差 ≤ **0.01 mm³**。
- 原报告约 478 是**双向**近似值；旧版 **120/0** 保留为异常线索。
- 草图显式 `origin = [0,0,0]`；U 输入保留原报告 `[0.809017, -0.587785, 0]`，记录原始值与实际归一化帧。
- 平面 ID 由巡检取得（`select_tilted_plane`），**不写死 74 或 2**。

### oracle 双算对照（本次实测）

| 量 | 值 |
| --- | --- |
| 解析积分（闭式） | `238.390260127791` mm³ |
| 数值积分（Simpson，2000 面板） | `238.39026012779075` mm³ |
| 绝对互差 | `2.558e-13` mm³ |
| 互差上界 | `1e-6` mm³ → **agrees = true** |
| symmetric（解析） | `476.780520255582` mm³ |

### oracle 拒绝项（本次实测）

| 方向 | 120 拒绝 | 0 拒绝 | 478 当单向拒绝 | 双向值当单向拒绝 |
| --- | --- | --- | --- | --- |
| positive | 是 | 是 | 是 | 是 |
| negative | 是 | 是 | 是 | 是 |
| symmetric | 是 | 是 | 是 | 不适用（该方向双向值即正确期望） |

> 关键约束：oracle **不接受**「不再等于 120」作为通过判据，也**不接受**把 478 当单向期望。

## 四、六例输入清单

每例独立干净基体、模型名唯一后缀（`<run_tag>` 为本次运行短哈希 `6655a995`）：

| # | 用例 | 尺寸策略 | 方向 | 模型名 | 期望去料 mm³ |
| --- | --- | --- | --- | --- | --- |
| 1 | autodim_positive | autodim | positive | `dev049t04_ad_pos_6655a995` | 238.390260127791 |
| 2 | autodim_negative | autodim | negative | `dev049t04_ad_neg_6655a995` | 238.390260127791 |
| 3 | autodim_symmetric | autodim | symmetric | `dev049t04_ad_sym_6655a995` | 476.780520255582 |
| 4 | coordinates_positive | coordinates | positive | `dev049t04_co_pos_6655a995` | 238.390260127791 |
| 5 | coordinates_negative | coordinates | negative | `dev049t04_co_neg_6655a995` | 238.390260127791 |
| 6 | coordinates_symmetric | coordinates | symmetric | `dev049t04_co_sym_6655a995` | 476.780520255582 |

模型名长度 ≤ 31、仅小写字母/数字/下划线、首字符为字母或数字；六例互不重复，跨运行后缀唯一。

每例实机流程（驱动内嵌，供实机阶段直接使用）：独立 `creo_new_part` → R20 圆拉伸 +5 →
主 X/Y 交线建 Z 轴 → 主 X 面 + 该轴建 54° 平面 → **巡检取平面 ID** →
`origin=[0,0,0]` + `u_axis=[0.809017,-0.587785,0]` 建 4×6 矩形（`dimensioning` 分别为
autodim / coordinates）→ `cut + through_all + <direction>`。

## 五、命令与结果

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_dev049_tilted_cut -v
# Ran 35 tests in 1.772s — OK

.\.venv\Scripts\python.exe tools\test_dev049_tilted_cut.py
# OFFLINE ONLY (no live flags given): no MCP client, no Toolkit call, no Creo connection.
# offline_cases=6 validated
# oracle_analytic=238.390260127791
# oracle_numeric=238.390260127791
# oracle_abs_difference=2.558e-13
# report=build/dev049_t04/20261028T002441_6d1e6443/report.json
# LIVE NOT RUN: no native geometry result was produced or claimed.

.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-049
# "success": true, "unit_tests": "not_run", "native_validation": "not_run"
```

### 默认离线运行生成的报告

`build/dev049_t04/20261028T002441_6d1e6443/report.json`

报告字段：`mode=offline`、`live_run=false`、`native_acceptance=not_run`、
`geometry_basis`（方向/法向语义与解析量）、`oracle`、`direction_verdicts`、`oracle_rejections`、
`frame_semantics`、六例 `cases`、`provenance`。报告路径按 `build/dev049_t04/<run_id>/report.json`
生成，启动时拒绝覆盖已存在的旧报告。

### 专项测试覆盖（35 项）

- 六例输入合法性（`validate_operations` 通过、`origin=[0,0,0]`、U 原始值、矩形 `[-4,-3]..[0,3]`、`through_all`）
- 无重复模型名 + 长度/字符集合法性 + 跨运行后缀唯一
- 默认不实例化 MCP 客户端（`mcp.Client` 不被构造）
- 单一 `--live` 或单一 `--confirm-session-usable` 均不能连接
- 非法参数在连接前拒绝（已存在报告路径拒绝覆盖，返回码 2，不触碰客户端）
- oracle 拒绝 120/0 与「478 当单向期望」
- 预算耗尽 / 未知结果**不会自动重提**（`wait_job` 只轮询 `creo_get_job`，`submit_once` 拒绝重复提交）
- 帧检查 `v = n×u`、非正交/错误 U/N/V 被拒；平面 ID 由巡检选取
- 解析与数值积分互差有界

## 六、未测范围（明确）

- **六例实机定向回放未执行**：未连接 Toolkit、未启动 MCP 客户端、未启动或结束 Creo、
  未发起任何建模作业。六例的实机去料、切口位置/分布、真实帧、revision、保存重载**全部未验证**。
- 未实施 T05—T08。
- 外部 Creo 10 环境继续未测。
- BUG-064（自定义基准面草图两处硬失败）与 BUG-084（平面显式 id 被忽略）的实机范围未收口；
  本阶段只完成 T04 离线准备，**不关闭任何范围**。
- 未复现原报告的 120/0 异常，也未在本阶段判定其当前状态；仅确认 oracle 会拒绝把它判为通过。
- 预览/同作业图像（T05）未做。

## 七、交接（给 T04 实机阶段）

- **前置**：按 BUG-001 纪律由人工确认 GUI 可操作、无初始化告警、无残留模态框；
  不得用 `--confirm-session-usable`、`session_health`、`ready` 或历史记录替代。
  T01 已注明 2026-10-26 会话已于 `2026-10-26T05:48:13Z` 退出，必须在**新会话**上执行。
- **命令**：`.\.venv\Scripts\python.exe tools\test_dev049_tilted_cut.py --live --confirm-session-usable`
  （两个开关必须同时给出，缺一即回落离线）。
- **停止点**：出现 `building_worker` 长时间无终态、`not_found_or_unreadable`、busy、失联、unknown
  或 GUI 不可操作，立即停止新提交；已受理作业只轮询 `creo_get_job`，不重提、不重连、不清保护。
- **判定**：每例须同时满足真实帧（`v = n×u`、U/V 与输入一致、面法线与期望法线平行）、
  去料体积（单向 238.390260127791 / 双向 476.780520255582，≤0.01）、切口分布符合单/双向、
  以及 `saved_file_reloaded_and_verified = true`。**不能只比体积**。
- autodim 失败不得用 coordinates 通过冲抵；两种策略分开记录。

## 八、关联条目

- **BUG-064**：仅登记「T04 离线准备完成」阶段记录；实机范围保持开放。
- **BUG-084**：仅登记「T04 离线准备完成」阶段记录；实机范围保持开放。
- **BUG-049 / BUG-066**：未在本阶段复现，保持原状态。

## 九、2026-10-28 实机阶段：六例全部失败于草图求解，缺陷定位（复现记录）

**会话核对（本次人工）**：2026-10-28 上午用户亲眼确认 GUI 可操作、无初始化告警、无残留模态框后才执行 `--live --confirm-session-usable`；未以 ready/`session_health`/历史授权替代。会话为 2026-10-27 21:21（本地）启动的新会话（事故会话已于 2026-10-26 13:48 退出）。附带观测：`nmsd.exe`（PID 20872，2026-10-26 20:26 启动）跨会话存留，已记录供 [BUG-085](../work-items/BUG-085.md) 参考，未处置。

**第 1 轮**（run_id `20261028T090725_e4f7ece5`，报告 SHA256 `0e76e17899663576750aead31517f5b7a4acb4606e1aa0a2b4438f89b767657e`）：案例 `autodim_positive`（job `c6d14112c6974d8b8dd55ccc6a399b52`，模型 `dev049t04_ad_pos_6655a995`）。基体 R20×5 圆柱正常（体积 6283.185307 mm³），54° 面由巡检取得（datum id=74，法向 0.588/0.809/0）；草图阶段 `SKETCH_SOLVE=-1`（mode=autodim）→ `AutodimensionSketch=-1` → `BUILD_FAILED=-1`，作业终态 `failed`（stage=`execute_sketch`，toolkit_code=-1）；`rollback_succeeded=true`、断开码 0、会话保持健康。驱动随后在自身断言处中止且未把该案例写入报告（cases 为空）——驱动证据持久化缺口，本轮失败证据保留于作业目录 `jobs/c6d14112…/`（含 native.log、inspection-verified、request）。

**驱动最小修复（随本次实机提交）**：斜槽作业终态 `failed` 时记录为 `passed=false`（含 message/failed_stage/failed_toolkit_call/toolkit_code/rollback 字段）并继续下一例；会话级异常（busy、失联、unknown、超时、未知终态）仍立即中止；新增可重复 `--case` 筛选，未知用例名在连接前拒绝。`tests.unit.test_dev049_tilted_cut` 扩至 **38 项全部通过**。

**第 2 轮**（run_id `20261028T094203_f120a54e`，报告 SHA256 `e41deae8ed4f79337cca53073dd8f2e579d8985f4c227068d633f1013f8448c1`，commit `5c03b10`、dirty=true）：经 `--case` 补跑其余五例，**全部同样失败**于 `execute_sketch`／`AutodimensionSketch=-1`：

| 案例 | job | 模型 | 终态 |
| --- | --- | --- | --- |
| autodim_negative | `edd302ca6bfc4b61890fd3104581c6c9` | `dev049t04_ad_neg_9382f3c5` | failed（同上） |
| autodim_symmetric | `ae349be8ade244aeb54fac79be26ba59` | `dev049t04_ad_sym_9382f3c5` | failed（同上） |
| coordinates_positive | `398e461f0cba4eaa9b19726e4e6387b3` | `dev049t04_co_pos_9382f3c5` | failed（见下） |
| coordinates_negative | `915bf14493574d54b3280710d2fc7877` | `dev049t04_co_neg_9382f3c5` | failed（见下） |
| coordinates_symmetric | `5acbdffc0ad344b392c892c546447b7b` | `dev049t04_co_sym_9382f3c5` | failed（见下） |

coordinates 三例的原生日志（例：job `398e461f…/native.log`）显示模式确为 coordinates（epsilon 1e-9）：`SKETCH_SOLVE=-1 mode=coordinates` → `SKETCH_SOLVE_WITHOUT_INFERENCE=-1` → `AutodimensionSketch=-1`，三阶段 **SECTION_ERRORS 均为 0**。六例 `rollback_succeeded` 全部为 true，无 busy/断连/-4/unknown，通道正常释放。

**结论与最小修复范围**：0/6 通过；体积、实际帧、切口分布、revision、保存重载均未到达。0.6.1 反馈的「非主面拉伸阻断」在 0.7.1 上对**原构型路径仍然存在**。对照控制组：0.7.0 通过 18/18 的通用倾斜面矩阵（`tools/test_t05_native.py:386`）使用 `datum_feature` 按标签引用 + `u_axis=[0,0,1]`；本任务按原报告构型使用 `datum_plane` 按巡检 ID + 平面内 `u_axis=[0.809017,-0.587785,0]`——两者走不同原生分支，后者 `ProSectionSolve` 获得错误放置（原生 trace 中实体线坐标为 u∈[0,4]，而提交矩形为 u∈[-4,0]，变换偏差候选）。**最小修复范围：按 `datum_plane` ID 引用且带自定义面内 u_axis 时的草图截面变换**。按派发表规则，本任务不改生产/native；修复待用户另行指派。

**边界**：未改生产/原生实现；未自动重连、未重启/结束 Creo、未清保护；失败后由用户决定继续补跑；运行数据未动。BUG-064/084 保持开放（见当日阶段记录）。

## 十、2026-10-28 BUG-087 修复验证：六例全部通过

**会话核对**：第九节失败后由用户于 2026-10-28 当场确认 Creo 会话仍可操作，并明确允许新开一次 MCP 连接补跑；本轮未自动重连、未重启或结束 Creo、未清任何保护。轮 A 的中断原因是驱动进程被工具环境杀死（非 Creo 故障），用户确认会话可用后才继续。

**修复（[BUG-087](../work-items/BUG-087.md)）**：补第二条截面定位参照时，候选基准面除与支撑面非平行外，还必须与 orient 参照面法向不平行，否则记 `SKETCH_ANCHOR_SKIPPED` 并继续，最终回落基准轴参照并记 `SKETCH_ANCHOR_AXIS`（`native/generic.cpp:1233-1287`）。截面矩阵未改。第九节 trace 中的 `u∈[0,4]` 属截面表达坐标，不是放置错误，本批不修。

**受测身份**（两轮一致）：commit `426d6b180e551a409ea1e96a9bdb3f7933cfe56a`、分支 `codex/bug087-sketch-frame`、`dirty=true`、`native/generic.cpp` SHA256 `a3665a9150c94da02762110f56e899c9c13d4abf960271e32379fbac1fdfbceb`、服务版本 0.7.1、本机 Creo 12.4.0.0。

| 轮 | run_id | 报告 | 报告 SHA256 |
| --- | --- | --- | --- |
| A：autodim×3 | `20261028T102858_b2d5e5c9` | `build/dev049_t04/20261028T102858_b2d5e5c9/report.json` | `5293df5224bfaab417f8322ee17731faa8a1f47dc1a2d0509d904dd5e973deb0` |
| B：coordinates×3 | `20261028T104324_57f20a2d` | `build/dev049_t04/20261028T104324_57f20a2d/report.json` | `0549fa7a44afddfe9e24f94f49e2ea2ecbb2183a41de4b09a00bb630d2a8e65f` |

轮 A 驱动被工具环境杀死（非 Creo 故障），报告未写终态 `native_acceptance`，三例结果已逐例落盘；轮 B `native_acceptance=all_passed`。

| 案例 | job | 模型 | 去料 mm³ | 期望 | rev | 参考线 | 重载 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| autodim_positive | `531d86e741844b5a9fa12079aaf2d4c8` | `dev049t04_ad_pos_9f7b1c2c` | 238.3902600354577 | 238.390260127791 | 3 | 2 | true |
| autodim_negative | `ee4fbfc02f734808b7e569a9167daf8d` | `dev049t04_ad_neg_9f7b1c2c` | 238.39026006478252 | 238.390260127791 | 3 | 2 | true |
| autodim_symmetric | `e44d31371e894df4abce53ba47598e1f` | `dev049t04_ad_sym_9f7b1c2c` | 476.78052009902603 | 476.780520255582 | 3 | 2 | true |
| coordinates_positive | `69cf8cac012543f1bcfe59791faa7be3` | `dev049t04_co_pos_11f854dc` | 238.3902600354577 | 238.390260127791 | 3 | 2 | true |
| coordinates_negative | `c9d0a15172c6439e9a5d693c97b5046a` | `dev049t04_co_neg_11f854dc` | 238.39026006478252 | 238.390260127791 | 3 | 2 | true |
| coordinates_symmetric | `fd105a986897481da1c6779b391130fe` | `dev049t04_co_sym_11f854dc` | 476.78052009902603 | 476.780520255582 | 3 | 2 | true |

六例 `passed=true`；实际帧 `u=(0.809016994,-0.587785252,0)`、`v=(0,0,-1)=n×u`、`n=(0.587785252,0.809016994,0)`；矩形 `min=[-4,-3]`、`max=[0,3]`；最大绝对误差 1.57e-7 mm³（容差 0.01）。全程无 busy／断连／`-4`／unknown／`building_worker` 悬挂。

**原生日志**（六例 `native.log` 一致）：`SKETCH_ANCHOR_SKIPPED=42 parallel_to_orientation=1.000000000`、`SKETCH_ANCHOR_SKIPPED=49 parallel_to_orientation=1.000000000`、`PROJECT_REFERENCE_AXIS=72 code=0 entity=1`、`SKETCH_ANCHOR_AXIS=72`；coordinates 三例 `SKETCH_SOLVE=0 mode=coordinates`，autodim 三例 `SKETCH_SOLVE=-1` 后 `AutodimensionSketch=0`／`RegenerateSolvedSketch=0`／`CompleteFeature=0` 完成特征。第九节中 42 被选中并 break 的路径不再出现。

**Right 面回归**：`tools/test_dev048_plane_frame.py --live --confirm-session-usable --output build/dev048_t04_plane_frame_bug087.json`（新路径，保留 0.7.1 原报告），报告 SHA256 `12e7532a2ba7385d217d797f7864940d1cb548813bc85baa06fbc58d355e7f7f`。`u_positive_z`／`u_negative_z` 均 799.9999999999998 mm³、八点 AABB 与重心符合、`revision=2`、保存重载 true、U/V=N×U；`parallel_u_axis_refusal` 仍为 `native_refusal`、`revision` 1→1、`aliases_unchanged=true`。与 0.7.1 同驱动记录（commit `8be9bcb`）逐项一致，轴对齐分支无退化；`native.log` 出现 `SKETCH_ANCHOR_PLANE=6`。

**离线验证**：`unittest tests.unit.test_dev049_tilted_cut tests.unit.test_t05_geometry` **57 项 OK**（新增 3 项 `SectionFrameTests`）；`tools/dev_check.py --skip-unit --work-item BUG-087` `success=true`，样式基线与既有一致，未重建。

**未测范围**：Creo 10／9 未独立复测；外部 Creo 10 原报文未复现；未做并发（BUG-009 边界）；未合 main、未推标签、未发布，`version.py` 未动（0.7.2 归 T08）；工具清单保持 94。运行数据与 `docs/validation/` 原件未动。
