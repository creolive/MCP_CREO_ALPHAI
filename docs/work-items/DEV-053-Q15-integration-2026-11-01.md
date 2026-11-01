# DEV-053 Q15 离线集成报告（2026-11-01）

状态：**离线开发完成；首次实机尝试被 BUG-098 阻断，未验收、未发布**。工作树 `codex/q15-integration`，基点 `50636bf`；离线阶段未连接 Creo、未原生构建、未合 main、未改版本或发布。2026-11-01 晚间在 task/11 合并后完成原生构建并开始首轮实机，详见下文“首次实机窗口”。

## 合并顺序与冲突裁决

| 顺序 | 来源提交 | 合并提交 | 裁决 |
| --- | --- | --- | --- |
| Q01 | `70ee4f5` | `97513cc` | 自动合并，P11/P07/P08 先入。 |
| Q02 | `747239d` | `7df7462` | `operation_results.py` 保留 Q01 原点诊断和 Q02 偏差诊断两套投影。 |
| Q03 | `b009b25` | `9806189` | 自动合并。 |
| Q04 | `fc19485` | `2ac2fd7` | 自动合并，保留终态阶段与 busy 5 秒文案。 |
| Q05 | `5a9be6c` | `d6d0c74` | 自动合并。 |
| Q06 | `102b9ef` | `ae78d79` | `native/generic.cpp` 同时保留 Q02 求解偏差及 Q06 `section_location`。 |
| Q07 | `1e4f7e3` | `495f887` | 自动合并。 |
| Q11 | `48216ee` | `7036666` | 自动合并。 |
| Q13 | `db28c10` | `ff51e32` | `bridge.py` 保留 Q03 cleanup、Q04 阶段，接 Q13 分页；结果投影保留 Q06 feature errors；`preview.h` 保留 P11 空几何跳过与 Q13 datum 遮挡，探测在 guard 前。后续修正 `0fabc32`。 |
| Q14 | `1265730` | `8ce0614` | 自动合并。 |

集成后补修：Q05 已登记三点契约，Q06 的旧 schema gate 改为验证先创建三个点；T07 测试定位新共享步骤；旧 registry 测试按 Q03 契约检查 cleanup unknown。Q06 合并造成的两处非 UTF-8 注释字节已修正。补修提交 `3c12f8d`。

## 离线检查

在 Q15 工作树运行，使用主 checkout 的 Python 可执行文件及 Q15 `PYTHONPATH`；日志保留为本机 `q15-*.log`，不入库。

- 指定专项及 Q01 迁移专项复跑：**387 项通过**。合并初跑 384 项有 2 失败、23 错误；修正编码及契约断言后复跑通过。
- 全量 `unittest discover`：2070 项，22 错误、2 失败，279.637 秒。21 个错误是 stdio 子进程从主 checkout editable 路径加载旧 `creo_mechdog.sheetmetal`，缺 `project_wall_contour`；其余 1 错误与 2 失败已修正并针对性复测。**未重跑修正后的全量，也未在 50636bf 独立复跑核对预存清单**；不能声称全量或基线对比通过。
- `tools/dev_check.py`：`success=false`，32 条 style regression；未重建 style baseline。这些问题仍须清理。
- 五个默认离线驱动 `test_g5_native_probe.py`、`convert_p12_feedback.py`、`test_t07_preview.py`、`test_datum_plane_through_points.py`、`test_failed_model_cleanup.py` 均 exit 0；不含原生验收。

## 统一实机负责人串行清单

1. 先按 BUG-001/091 记录核对根因及 Creo 会话可操作性；不擅自结束 Creo 或清 unknown。仅使用指向本工作树的 `MCP_CREO_MechDog_dev`。
2. 实机窗口生成本机 SDK 常量、执行 `bridge.py build`，记录环境、提交、dirty、源码指纹、命令及结果。
3. 串行执行 Q01 原点/折边/空件预览、Q02 偏差、Q03 cleanup、Q04 stage/busy、Q05 三点定面、Q06 斜面 L1/L2、Q07 G5 探针、Q11 P12、Q13 分页/预览、Q14 B/C/G 替代夹具的 live 驱动；逐项遵守各工作卡准入。
4. 记录每次调用、job_id/model_id、终态、几何/参数、保存重载 `saved_file_reloaded_and_verified=true`、revision、回滚、原始错误及未测范围。只有实际并发调用才报告并发通过。
5. 实机结束后讨论候选集成版本 `0.12.0` 或 `0.11.x`；本轮不定版、不发布。

剩余：style 修复、全量与基线复测、实机、WorkBuddy 黑盒、main 合入和 Release。Q08–Q10 仍待 Q07 探针与实现；Q12 的 0.11.0 已交付状态不变。

## 首次实机窗口（2026-11-01 晚间，本机 Creo 12.4.0.0）

- 环境：Windows 11 x64、Creo 12.4.0.0（`release_numeric=44`）、匹配 SDK、MSVC x64；新开本机 Creo 会话，`bridge.py status` 首测 `connected=true`、`toolkit_code=0`、`disconnect_code=0`。
- 集成修复：`native/preview.h` 有两处 Q15 合并截断——`bind_model_window()` 函数头丢失、返回块后残留重复的 `datum_display` 片段。修复后 `.venv\\Scripts\\python.exe bridge.py build` 通过（首次 build 报 C2143/C2059/C3861，修复后无错误）。
- 执行：`tools/test_datum_plane_through_points.py --live --confirm-session-usable` 第一个用例 `main_plane`。
- 结果：三个 `datum_points` 与 `datum_plane`（id=47，normal 0,0,1）创建完成；`native.log` 停在 `ProFeatureElemtreeExtract` / `ProElemtreeElementGet`，作业 `b620c5a6c9d54d28a2815cb5083bfa6e` 持续 `running` 6 分钟，驱动按 360 s 预算停止轮询且未重提。worker CPU 冻结，`parametric` hidden+hung、`xtop` 正常。
- 处置：按 BUG-001/BUG-091 规则停止新提交，保留现场（未结束 Creo、未清 unknown、未重提作业），登记 [BUG-098](../../work-items/BUG-098.md)。0.11.1 未发布；Q06 L2、Q07 P1–P3、Q02/Q03/Q13 实机均未执行。
- 新增离线驱动：`tools/test_tilted_sketch_3pt.py`（smoke_3pt 原案经 FEAT-053 契约转换）与 `tests/unit/test_tilted_sketch_3pt.py`，离线 4 项单测通过；后续已执行 live，见下。

### 第二轮实机（BUG-098 修复后）

BUG-098 定位到三点定面创建后的逐约束特征树读取会阻塞 Toolkit；将校验改为 `ProElementArrayCount` 只读数组计数（`references_status.available=false` 明示）后：

- **Q05 通过 8/8**：5 个有效例 + 3 个拒绝例；`build/live-0.11.1/q05_through_points_r2.json`。
- **Q06 L1 通过、L2 未过**：`using_frame_basis` 生效；`CompleteFeature=-1` 且 element/section 错误为空，L2 根因仍未定；`build/live-0.11.1/q06_l2_smoke3pt.json`。
- **Q07 P1/P2/P3 均“路线不成立”**：P1/P3 特征停在 `PRO_FEAT_UNREGENERATED`，P2 创建失败；Q08–Q10 不开工；见契约 §9。
- **Q03 未通过**：S1 `saved_since_creation` 跳过、同名不可复用；S3 `rollback_succeeded` 缺失。
- **Q13 未通过**：`disk_cut_pattern` 的 `save_and_reload` 报 `ProMdlnameBackup` -1。

因此 0.11.1 的实机验收门槛未全部满足，未进行版本裁定或发布。
