# DEV-049 T05 验收记录：多环原输入与预览的查缺补验（2026-10-28）

> **仅离线阶段。** 本记录覆盖 DEV-049 T05 的输入查缺、覆盖差项表与替代回放夹具的离线交付。
> 未连接 Creo/Toolkit、未启动 MCP 客户端、未执行任何建模作业，因此**没有任何多环实机结果或预览图像**，
> 也没有对 BUG-049 / BUG-066 作出修复结论。

## 一、交付身份与环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-10-28（Asia/Shanghai） |
| 分支 | `codex/dev049-t05-input-gaps` |
| 依赖提交（基线） | `fbc899f59dbb55ac86198c4af7ade6ba943a9531`（DEV-049: integrate T04 offline tilted-cut prep） |
| 任务提交 | 见 `git log` 本次提交 |
| dirty | `true` |
| 版本入口 | `version.py = 0.7.1`（本任务未改） |
| 环境 | Windows x64、Python 3.12.14 |
| 受测源码指纹 | `cdcb27e65431f3d8463ee0dc4fb0b73276e002a17971e7d4a5f10446cae38436`（离线报告 `provenance.source_fingerprint`） |
| dev_check 受测源码 | `73faee4f206769836bb06aaeef99584821e142849bee5d3e270d447a2122a66f`（`build/development_check.json`） |

dirty 来源：`session_activity.json`（运行数据，未提交、未 stash、未 checkout）、`session_erase/`、
客户端目录与既有未跟踪模型，以及本次新增的两个源码/测试文件。运行数据与源码分开登记。

**未改动项：**`version.py`、`native/**`、生产几何实现、94 个 MCP 工具清单均未改动；未实施 T06—T08。

## 二、原输入查缺（搜索范围与结果）

### 2.1 搜索范围（严格限定）

| 范围 | 方式 |
| --- | --- |
| 本项目工作区 | 全树文件名匹配 `gear10*`、`sketch_entities*`、`*gear*`、`*part2*`、`*Part2*`、`*.prt`、`*.jpg/*.png` |
| 本项目 Git 历史 | `git log --all -- '*gear10*' '*sketch_entities*'`；`git log --all -Sgear10`；`git log --all --diff-filter=D -- '*gear*'` |
| 发布/预检压缩包 | `build/*.zip` 共 29 个，逐包列出含 `gear10`/`sketch_entities` 的条目 |
| 用户指定下载目录 | `C:\Users\Administrator\Downloads` 递归（含 `0.5.0`、`0.5.1`、`0.5.2`、`0.6.0`、`0.6.1`、`0.7.0` 反馈目录） |

未扩大到其他私人目录（桌面、文档、其他盘符等），未使用网络检索。

### 2.2 找到的文件身份

| 文件 | 位置 | 字节 | SHA256 | 结论 |
| --- | --- | --- | --- | --- |
| `2026-10-26CREO10.0.0.0-0.6.1会话断连同族故障复现但BUG056仍标已关闭.md` | `Downloads\0.6.1` | 11935 | `5d94503c86de300e4368321da9589ca4b2c2bb3cc367ca0b10a82893283ea298` | 与归档 `manifest.json` 哈希一致（同一原件） |
| `20261026_CREO_v0.6.1_三项阻断仍未修复_非主面拉伸方向已获干净定量证据.md` | `Downloads\0.6.1` | 10598 | `5ea9400a4f8014b43b01c0e9151fbdbfd0636fceaa58f89eb6f751d7eb1671f9` | 同上（T05 的事实来源） |

`Downloads\0.6.1` 目录下只有这两份 Markdown，没有其它附件。

### 2.3 缺失项

| 缺失输入 | 证据 | 影响 |
| --- | --- | --- |
| `gear10.json`（10 环 40 弧 payload，前 20 条即 5 环） | 项目树、全部 Git 历史、29 个压缩包、Downloads 递归均无命中；`gear10` 只作为文档/夹具注释里的文字出现（7 个提交，全部是 `.md`/`t06_fixtures.py`） | **原案例不可逐字回放** |
| `sketch_entities.json` | 同上，零命中 | 无法重建原始坐标 |
| 原 Part2 模型（`.prt`） | 全树 `.prt` 均为本机生成件（`models/`、`build/`），无 `part2*`/`probe_npp*` 命名文件 | 无法复现预览失真的原始构型 |
| 原 Part2/Part1 预览图像 | 全树 `*.jpg/*.png` 仅有 `build/t07-preview/` 五图（本机 T13 产出） | 无法目视对照原始失真形态 |
| T04 同作业图像 | `build/dev049_t04/**` 仅 11 个 `.json`，**0 张图像**（T04 实机未跑） | 本阶段无同构图像可用 |

**结论：原案例不可逐字回放，所有结果只能作为替代验证（replacement verification）记录。**

## 三、覆盖差项表（原输入 / 已有夹具 / 差异 / 本次所需）

已有实机证据（均为既有记录，本次未重跑）：

- **9/9 合法多环**：`build/t06-native-live.json`，`native_acceptance=passed`、`geometry_matrix=passed`，
  源码 `402821e`（分支 `codex/dev047-feedback052`、版本 0.6.1、`dirty=true`）。
  九例：`add` ×2 圆 / 5 圆 / 10 圆 / 5 四弧环 / 10 四弧环 / 2 圆+5 四弧环 / 嵌套，
  `cut` ×2 圆 / 2 圆+5 四弧环；全部单原生特征（`feature_delta` 只 +1）且 `saved_file_reloaded_and_verified=true`。
- **五图目视**：`build/t07-preview/{disk,disk_cut,disk_cut_pattern,explicit_jpeg_export,export_job_preview}.jpg`，
  2026-10-27 T13 复核“轮廓完整、4 孔阵列与解析体积互证、显式导出与作业预览逐字节一致”。
- T06 证据自身已记 `external_case_replay = not_applicable_missing_attachments`。

| # | 项目 | 原输入 | 已有夹具/证据 | 差异 | 本次所需 |
| --- | --- | --- | --- | --- | --- |
| 1 | 2 个独立圆 | 缺失 | T06 实机 `add/2_circles`、`cut/2_circles`（R3、±6、深 8） | 尺寸不同（报告为 R2、±8、板厚 5），轮廓数量与类型相同 | **只引用证据**；另加同板数值对照 |
| 2 | 5 个四弧闭环 | 缺失（原坐标未知） | T06 实机 `add/5_arc_rings`；`cut/two_circles_five_arc_rings`（7 轮廓 cut 通过） | 缺“5 环单独进入 cut 计划”；原坐标未知 | 替代夹具 `five_arc_rings_cut` |
| 3 | 10 个四弧闭环 | 缺失 | T06 实机 `add/10_arc_rings` | **cut 计划从未提交过 10 环** | 替代夹具 `ten_arc_rings_cut` |
| 4 | 原始齿轮剖面（40 弧） | `gear10.json` 缺失 | 无 | 几何不可知 | **阻塞**，等待附件 |
| 5 | 预览空白/长条失真 | 无模型、无原始图像 | T07 五图（无失真） | 原构型从未留存 | **无法复现**，BUG-066 维持待复现 |

补充判断（离线可独立确认，不含实机结论）：

- 报告“多轮廓只支持 2 个”的表述在本仓既有证据前不能成立：0.6.1 版源码上的 T06 实机已用 **7 个轮廓**
  的 cut 计划成功（`two_circles_five_arc_rings`，去料 1979.203372 mm³ = 7π·3²·10）。
- 因此本任务**不输出 `supported=2`，也不给出任何多环上限**；报告中的数量边界保持未证实。
- 但既有 7 轮廓用例是同一次 sketch 内 2 圆 + 5 环，仍不能替代“纯 5/10 四弧环 cut”和原始齿轮坐标。

## 四、本次新增（仅对确有未覆盖且可执行的差项）

| 文件 | 职责 |
| --- | --- |
| `tools/test_dev049_profile_replay.py` | 默认离线双门槛驱动；三个替代用例、独立面积极分与面积×厚度 oracle、内嵌原输入缺失声明 |
| `tests/unit/test_dev049_profile_replay.py` | 29 项离线回归 |

未重写现有多环/预览实现，未新增 MCP 工具，未改原生代码。

### 替代夹具（显式声明为替代）

板件与报告一致：XY 上 R20 圆、正向拉伸 5，`z=0..5`，体积 π·400·5 = **6283.185307179586 mm³**；
`dimensioning=coordinates`；cut 为 `through_all`。

| # | 用例 | 角色 | 期望来源 | 轮廓/图元 | 解析面积 mm² | 期望去料 mm³ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `control_two_circles_r2` | 对照（引用 T06 覆盖） | 报告数值 | 2 / 2 | 25.132741229 | **125.663706144** |
| 2 | `five_arc_rings_cut` | 未覆盖差项 | 替代（r=3、间距 12） | 5 / 20 | 141.371669412 | 706.858347058 |
| 3 | `ten_arc_rings_cut` | 未覆盖差项 | 替代（同上） | 10 / 40 | 282.743338823 | 1413.716694115 |

**方向说明（重要）：** 报告 §3 写作 `cut + through_all + negative`，但未给出该草图的支撑平面；
在 `z=0..5` 的板上从 XY 作负向扫掠不会去料（§2 已实测为 0）。因此驱动把
`plane=XY / direction=positive` 记为**驱动显式选择**而非“回放”，并写入报告 `geometry_basis.direction_note`；
实机阶段若实测去料为 0，按失败记录，不改写为通过。

### 离线实测（本次）

| 量 | 结果 |
| --- | --- |
| 2 圆对照复算 | 2π·2²·5 = 125.66370614359172；报告值 125.663706；互差 **1.4359e-7 mm³**，6 位小数一致 |
| 闭合检查 | 各环端点最大缝隙 ≤ 7.35e-16 mm |
| 环间最小间隙 | 2 圆对照 12.0 mm；四弧环 6.0 mm（均 > 0，不重叠） |
| 面积数值核对 | 内接多边形 Richardson 外推（256/512 采样）与闭式面积最大互差 **1.9e-8 mm²**（容差 1e-6/环） |
| 单靠内接多边形 | 256 采样误差 ~1.3e-3 mm²，**不达容差**——因此必须外推，不能把“数值接近”当成独立验证 |
| oracle 拒绝项 | 0、2 倍、按 T06 深度 8 计算、直径当半径（×4）、非数值、NaN 全部被拒 |

### 离线报告

`build/dev049_t05/20261028T003658_d6d2da69/report.json`，字段：
`mode=offline`、`live_run=false`、`native_acceptance=not_run`、
`original_inputs.original_case_replay=not_possible_missing_attachments`、
`replacement_verification=true`、`contour_limit_claim=not_asserted`、
`coverage`（五条差项表）、`geometry_basis`、`oracle`、三例 `cases`、`provenance`。

## 五、BUG-066 预览结论

- 本阶段**没有**原失真构型、没有原始图像、也没有 T04 同作业图像（T04 未实机，`build/dev049_t04` 内 0 张图）。
- 既有五图只是本机 T13 正常渲染证据，不能反推原始“近空白/分离长条”形态。
- 现有夹具（T07 的盘体→切除→阵列）与报告构型（Part1 斜槽切除、Part2 全特征齐备）不同构。
- **结论：BUG-066 保持“待复现”。** 未新增任何“预览正确”的证据，也未把非空文件、`written` 或体积正确
  当作图像正确。

## 六、命令与结果

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_dev049_profile_replay -v
# Ran 29 tests in 1.912s — OK

.\.venv\Scripts\python.exe tools\test_dev049_profile_replay.py
# OFFLINE ONLY (no live flags given): no MCP client, no Toolkit call, no Creo connection.
# offline_cases=3 validated
# original_case_replay=not_possible (gear10.json, sketch_entities.json missing)
# replacement_verification=true
# reported_control_agrees=True
# report=build/dev049_t05/20261028T003658_d6d2da69/report.json
# LIVE NOT RUN: no native geometry result was produced or claimed.

.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item DEV-049
# "success": true, "unit_tests": "not_run", "native_validation": "not_run"
```

格式：`.venv\Scripts\python.exe -m ruff format tools/test_dev049_profile_replay.py tests/unit/test_dev049_profile_replay.py`
（2 files reformatted）；`ruff check` 两文件 **All checks passed**。

> PowerShell 5.1 会把子进程 stderr 显示成 `NativeCommandError`；上表退出码以
> `2>$null` 后的 `$LASTEXITCODE`/重定向日志为准（单测 0、驱动 0、dev_check 0）。

## 七、未测范围（明确）

- **三个替代用例均未在 Creo 中执行**：未连接 Toolkit、未启动 MCP 客户端、未建模、未保存/重载。
  实机去料、`native_section` 闭环数、单原生特征、revision、重载校验全部**未验证**。
- 原始 `gear10.json` / `sketch_entities.json` 案例**不可回放**；未做、也无法做逐字回放。
- 未复现报告中的 5/10 环 `ProFeatureWithoptionsCreate=-1`，未定位根因；BUG-049 状态不变。
- 未复现预览失真；BUG-066 状态不变。
- 未实施 T06—T08；未改原生实现；外部 Creo 10 环境继续未测。

## 八、后续触发条件

| 条件 | 后续动作 |
| --- | --- |
| 用户提供 `gear10.json` / `sketch_entities.json` | 先离线核对闭合、面积、图元与两两交点，再在独立干净基体、同版本同尺寸策略下实机回放 |
| 用户指派 T05 实机阶段 | 必须同时 `--live --confirm-session-usable`，并按 BUG-001 纪律人工确认会话可操作；串行三例，新报告目录，异常即停止新提交 |
| T04 实机执行完成 | 取同作业图像补预览对照；无失真仍不改 BUG-066 状态 |
| 观察到原始失真构型 | 保留模型/图像/作业 ID 与体积，按 BUG-066 待核对项逐条定位 |

## 九、关联条目

- **BUG-049**：仅登记“T05 输入查缺与替代夹具离线完成”阶段记录；父卡“待复现”与数量边界判断保持开放。
- **BUG-066**：仅登记“无原模型/图像，未复现”阶段记录；保持待复现。
- **DEV-047 T06 / T07**：既有 9/9 与五图证据只引用，未重跑、未改写。
