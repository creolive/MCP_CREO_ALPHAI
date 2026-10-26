# DEV-047 / T07 预览实体失真离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[BUG-066](../work-items/BUG-066.md)。任务分支：`codex/dev047-t07-preview-fix`，基线 `5217601`（集成分支 `codex/dev047-feedback052`，含 T00—T06）。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。**本轮结论：离线实现完成，实机未验收；空白/长条/缺面的复现与目视证据归 T13。**

## 范围与素材边界

本任务只做离线工作：**未创建 MCP 客户端、未连接 Toolkit、未启动/结束 Creo、未做会话探测或故障注入、未清理 unknown 保护**。`tools/test_t07_preview.py` 仅以离线模式运行并输出 `OFFLINE ONLY`；实机驱动已编写但**未运行**。BUG-066 的原始现象（Part1 星形架 7~8 根长条、Part2 V3898.30 近空白）来自外部报告，本轮没有复放原案例，也没有据此推断根因。视角选择等 FEAT-041 其他范围保持原卡，不在本次范围。

## 两条截图路径的现状与统一

| 路径 | 改前 | 改后 |
| --- | --- | --- |
| 作业自动 `preview.jpg`（generic 计划） | `ProMdlDisplay`→`ProMdlWindowGet`→`ProWindowCurrentSet`→`ProViewMatrixSet`→`ProWindowRefit`→`ProWindowRepaint`→`ProWindowActivate`→`ProRasterFileWrite`，全部 `CK()`（截图失败会把作业标失败） | 同一序列集中在 `native/preview.h` 的 `capture_preview`，逐个记录原始返回码，不抛异常、不改变作业终态 |
| 显式 JPEG 导出（generic `export(format="jpeg")`） | 仅 `ProMdlDisplay`→`ProWindowRefit`→`ProWindowRepaint`→`ProRasterFileWrite`，缺当前窗口核对与视图矩阵，`CK()` 抛错 | 同一 `capture_preview`；因图像是该输入请求的结果，失败时按 T02 规则为该输入记一条 `failed` 结果 |
| 板件作业 `preview.jpg`（worker `create`） | 复用 `create_plate` 的显示状态后直接 `ProRasterFileWrite` | 同一 `capture_preview`；同时把板件显示用的固定视图矩阵改为共享常量 `preview_isometric_view` |
| 图纸 JPEG 导出 | `ProWindowRefit`→`ProWindowRepaint`→`ProRasterFileWrite`（12×8，无视图矩阵） | 同一 `capture_preview`（`apply_view_matrix=false`，12×8）；因为图纸视图由图纸视图自身拥有 |

共用步骤（`native/preview.h`）：

1. **目标窗口选择**：`ProMdlDisplay` 取得窗口，`ProMdlWindowGet` 读窗口号；`ProWindowMdlGet` 校验该窗口确实属于本次模型（句柄不同时再按模型名复核），避免截取到上一个作业遗留窗口。
2. **当前窗口核对**：`ProWindowCurrentSet` 后立即 `ProWindowCurrentGet` 回读，记录 `current_window_matches`。
3. **视图矩阵**：使用共享常量 `preview_isometric_view`（每行单位长度且正交，符合 SDK 对 `ProViewMatrixSet` 的归一化要求），随后 `ProViewMatrixGet` 回读并按 1e-3 比较旋转部分，记录 `view_matrix_matches`。
4. **refit/repaint 时机**：固定顺序 `Refit`→`Refresh`→`Repaint`→`ProRasterFileWrite`；`ProWindowActivate` 只记录返回码（SDK 明确其效果要等控制权回到 Creo），不当作可失败步骤。
5. **截图调用**：只有走到最后一步才调用 `ProRasterFileWrite`，成功后用文件大小复核（`< 1` 字节记为 `output_file` 失败）。

已按本机 Creo 12.4 Toolkit 头文件核对使用到的单个 API：`ProMdlDisplay`、`ProMdlWindowGet`、`ProWindowMdlGet`、`ProWindowCurrentGet/Set`、`ProWindowActivate`、`ProViewMatrixSet/Get`、`ProWindowRefit`、`ProWindowRefresh`、`ProWindowRepaint`、`ProRasterFileWrite`。**「显示模式」在本 SDK 中没有窗口着色的读取接口**：`ProWindows.h` 只提供窗口、视图矩阵与重绘类函数，`ProDisplaymode*` 描述的是尺寸显示（符号/数值），`ProDisplayStyle` 只作用于图纸视图。因此共用步骤核对的是「目标窗口 ↔ 模型」和「当前窗口」，无法读取或断言模型窗口的着色/线框模式；这一点在 BUG-066 的 T13 核对项中保留，不用推测替代。

## 失败路径结构化

- 自动预览失败**不影响**作业终态：`capture_preview` 不抛异常，作业仍按保存与重载结果判定 `success`；`result.preview_status` 为 `failed`，`preview_file` 为 `null`，原始码留在 `result.preview`。
- 保存失败也不会被预览掩盖：预览在保存与重载校验之后执行，失败作业根本不会走到截图；即使之前存在旧图，`bridge/generic_bridge` 的投影也不会把失败作业的图标为可用。
- 新增字段（snake_case，进入既有结果结构，不新增记录）：

| 字段 | 位置 | 含义 |
| --- | --- | --- |
| `preview` | 作业结果；显式导出的**同一条**操作结果 | `status`（written/failed）、`path`、`bytes`、`file_verified`、`window`、`window_matches_model`、`current_window_matches`、`view_matrix_matches`、`codes`、`failed_step`、`failed_code`、`source` |
| `preview_status` | 作业结果 | 由 `preview.status` 复制，便于 compact 读取 |
| `preview_code` | 作业结果（保留原字段）与导出操作结果（新增） | `codes.raster` 原始返回码 |
| `preview_file` | 作业结果（保留原字段） | 仅 `written` 时为路径，否则 `null` |

`codes` 固定包含 `display`、`window_get`、`window_model_get`、`current_set`、`current_get`、`activate`、`view_matrix_set`、`view_matrix_get`、`refit`、`refresh`、`repaint`、`raster`。未知步骤为 `null`，不会被补成 0。导出失败时仍只有一条 input 对应的终态记录（`execution_status=failed`），诊断随该记录返回，不追加第二条。

`src/creo_mechdog/preview.py` 是 Python 侧唯一投影：`normalize_preview`/`apply_preview_projection` 只在原生证据存在时投影，**从不把 failed 升级为 written**；声明 `written` 但文件缺失或为 0 字节时降级为 `failed`（`failed_step=output_file_verification`）；旧结果的 `preview_code=-1` 且作业失败记为 `not_attempted`。`bridge.py`（板件）与 `generic_bridge.py`（通用计划）调用同一函数，compact 投影保留 `preview`/`preview_status`/`preview_code` 与操作内的 `preview`。

## 实机驱动（未运行）

`tools/test_t07_preview.py`：

- 默认严格离线，只打印 `OFFLINE ONLY` 与夹具解析体积，不导入 MCP 客户端。
- `--live` 必须同时给 `--confirm-session-usable`；运行前还要求 `config.json` 的 `auto_start_creo=false`（只读取，不修改）。
- 实机阶段只用 180 秒预算观察 `creo_startup_status`，`busy`/`unknown_outcome`/其它非等待状态立即停止；不自动重试、不重新提交；只轮询 `creo_get_job`。
- 夹具：`disk`（Ø80×12 圆盘拉伸）→ `disk_cut`（先建两平面交线轴 `zaxis`，再 Ø20 贯通切除）→ `disk_cut_pattern`（绕 `zaxis` 四实例 90° 角度阵列）→ 显式 `creo_export_model(format="jpeg")`。
- 每个作业断言：`preview.status=written`、`codes.raster/display/refit/repaint` 均为 0、`file_verified=true`、图像文件存在且非空；同时复制到 `build/t07-preview/<case>.jpg` 并记录字节数与 SHA256 供 T13 目视复核，标注 `content_verification=human_review_pending`。
- 体积只作为**事实记录**（`volume_mm3` 与解析期望值并列写入报告），不在驱动中断言；图像内容是否正确、失真是否消失仍由 T13 目视与原生几何断言判定。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format；本机匹配的 Creo 12.4.0.0 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t07_preview` | 19 项通过 |
| `python -m unittest discover -s tests -q` | 856 项通过，耗时 220.689 秒；既有套件无回归 |
| `python tools/test_t07_preview.py` | 输出 `OFFLINE ONLY`，未创建 MCP 客户端；期望体积 disk=60318.579、after_cut=56548.668、after_pattern=45238.934 mm³ |
| `python tools/test_t07_preview.py --live`（缺确认标志） | 按设计拒绝并退出，未连接 |
| 变更 Python 的 Ruff check / format --check | `src/creo_mechdog/preview.py`、`bridge.py`、`generic_bridge.py`、`tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py` 全部通过，未新增风格基线豁免 |
| 项目 clang-format 23.1.3 对 `native/preview.h`、`native/worker.cpp`、`native/generic.cpp`、`native/drawing.cpp` | `--style=file --fallback-style=none --dry-run --Werror` 通过；格式化差异只落在本次新增/修改区域，无存量格式清理 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `0BC7F894EF18828F121741E16735FC5AC72CA86516717B2A5314CC1349D8A3E8`，该生成物不入库 |
| `python tools/dev_check.py --work-item BUG-066` | exit 0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；`style_summary` 为既有基线（lint 30、未格式化 16），无新增违规；证据 `build/development_check.json`、`build/t07-devcheck.log` |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `5217601a21111dea55b46ce8361b6e012677e332`（dirty=true，仅既有 `session_activity.json` 本地改写与未跟踪运行文件），受测源码 `checked_source_sha256=708a8b30a19c7be4df5051d5d2fc4cabfd2df77b9578bc2d5498c267867d4c67`，生成时间 `2026-10-26T16:41:16Z`。

### 新增单测覆盖

`tests/unit/test_t07_preview.py`：

- 结构守卫：`ProRasterFileWrite` 只出现在 `native/preview.h`；`worker.cpp`/`generic.cpp`/`drawing.cpp` 不再直接调用；三个截图调用点都走 `capture_preview`；自动预览区不含 `CK(`/`throw`；导出分支只委派共用步骤；共用步骤包含窗口身份、当前窗口、视图矩阵回读与文件大小核对。
- 投影：written 保留路径与码；failed 即使文件存在也不升级；声明 written 但文件缺失/空降级；旧字段回退；`not_attempted`；无证据不投影；投影不改 `success`/`saved_file_reloaded_and_verified`/`sha256`/`revision`；导出仍是单条操作结果且 compact 保留 `preview`。
- 作业级解耦（fake worker）：预览失败 + 保存成功 → `succeeded`、revision 推进、`preview_status=failed`、`preview_file=null`；预览成功 → `preview_file` 有值；保存失败 → 作业 `failed`，预览的旧图不掩盖失败。

## 未测范围与 T13 实机矩阵（本次未执行）

1. 盘体、切除、阵列三步各自的 `preview.jpg` 与显式 JPEG 导出：核对 `preview.codes` 全为 0、文件非空，并人工比对图像与体积/特征树（原卡要求的「轮廓完整、对象和视图正确」）。截图成功或像素非空不作为内容正确的证明。
2. 报告场景（星形架斜槽种子切除、Part2 近空白）未复放；缺失原案例输入，本轮只提供步进夹具。若 T13 复现失真，需要保存当次 `preview` 码、`native.log` 的 `PREVIEW=` 行与前后图，再判定是窗口/视图时机、显示集还是网格原因，不用返回码推测根因。
3. 模型窗口的着色/线框显示模式无法经 Toolkit 读取（见上），T13 只能由操作者目视记录 Creo 中的实际显示样式；不把 `view_matrix_matches` 当作画面正确。
4. 图纸 JPEG 导出改为共用步骤后未实机运行；`ProMdlDisplay` 对图纸窗口、12×8 尺寸与 refit 行为需在 T13 回归。
5. 板件作业仍保留 `create_plate` 自己的显示序列（重载校验用，不截图），只共享固定视图矩阵与截图步骤；两者是否需要在实机后进一步合并由 T13 决定。

本次验收结论：**T07 离线实现完成，实机未验收**。两条截图路径已统一到一个共用步骤，预览失败与模型保存分开表达、原始返回码进入既有结果结构，驱动与图像留存已就绪；BUG-066 的失真复现、修复有效性、图像目视复核与几何回归全部待 T13。`docs/validation/` 历史原件、`session_activity.json` 本地修改及未跟踪运行文件保持原状。
