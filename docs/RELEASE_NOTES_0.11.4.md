# MCP_CREO_MechDog 0.11.4 版本说明

- 类型：PATCH（公开工具仍 **95 个**，无新增工具、无破坏性接口变更）。
- 批次：2026-11-02 第十二轮反馈（R12），[DEV-064](work-items/DEV-064.md)；来源为 `C:\Users\Administrator\Downloads\0.11.1` 两份 Creo 10 × 0.11.1 验收原件。
- 服务与源码版本以 [version.py](../version.py) 为准；本版种子包为 `MCP_CREO_MechDog-0.11.4-seed-library.zip`。

## 本版内容

### 1. 0.11.1 反馈归档与逐章对账（DEV-064）

两份原件逐字节归档到 `docs/validation/feedback-0.11.1-2026-11-02/`（2/2 长度、SHA256 与源文件一致，另做整文件字节比对），附 `manifest.json`（含提交/dirty/源码指纹三元组）与[逐章映射](validation/feedback-0.11.1-2026-11-02/MAPPING.md)。新登记 [BUG-107](work-items/BUG-107.md)、[BUG-108](work-items/BUG-108.md)，补建 [FEAT-054](work-items/FEAT-054.md)、[FEAT-055](work-items/FEAT-055.md) 工作卡（沿用既有 ID），并把 [BUG-106](work-items/BUG-106.md) 转为本批实现。已闭环项只记依据不重复派工：孔 `depth_basis` 三键（[FEAT-035](work-items/FEAT-035.md)，0.11.2）、零变更失败可用 `ack_no_mutation` 复位（[BUG-105](work-items/BUG-105.md)，0.11.3）、BUG-090 P12 外部构建证据格式、0.11.3 种子闸门。

### 2. Creo 10 首次构建不再硬失败（BUG-107）

`tools/generate_constants.py` 的 `HEADERS` 无条件读取全部头文件，而 Q07 G5 探测新增的 `Probbl.h` 在 Creo 10 SDK 中不存在，导致 0.11.1 在该版本首次 `bridge.py build` 以 `FileNotFoundError` → `SDK constant generation failed` 整体中止（与 BUG-090 同族：函数有门控、头文件清单没有）。

- 新增 `available_headers(inc_dir)`：读取前把 `HEADERS` 分成"本代 SDK 存在"与"缺失"两半，**只用存在的头**驱动枚举扫描与 `#include` 段，保证枚举集合与 include 集合永远同源。
- 缺失头逐条打印 `MISSING_SDK_HEADER=<name>`，经 `bridge.py` 的 stdout 捕获写入 `build/generate_constants.log`；不再中断构建。
- 未采用 `#if __has_include`：`native/constants.inc` 在库外生成，编译期与生成期双闸门会出现"头存在但枚举未读"或"枚举已读但 include 被跳过"的偏差。
- 契约测试 `tests/unit/test_gated_headers.py` 对清单里的**每个头**做"从 SDK 抽掉即跳过"的断言（31 子用例），并核对本机实际 `constants.inc` 的 include 集合等于存在集合。

### 3. 草图位移可观测与原点试点（BUG-108）

报告方 Creo 10 在第 2 条带被 `Coordinate dimensioning changed the supplied geometry; maximum deviation mm=0.004004` 拒绝，日志显示 `COORDINATE_ORIGIN=-0.004003728342,0` 且三个图元同量平移——是整截面刚体平移而非变形；加 `geometry_tolerance_mm` 放行后，回执没有任何"草图被移动"的信号。

- 创建与编辑草图的结果新增顶层 `sketch_shifted`：`detected`、`rigid`、`translation_mm{u,v}`、`max_point_mm`、`point_count`、有界 `sample`（≤20）、`truncated`、`tolerance_source`、`accepted_by_request`、`measurement_scope`、`note`。刚体判据为"所有被检点相对共模向量残差 ≤ 1e-9"。
- `geometry_deviation` 只增 `shift_detected` 与 `accepted_by_request`，`exceeds_warning` 语义（是否超阈值）未变。
- `accepted_by_request=true` 明确表示"该草图仅在显式 `geometry_tolerance_mm` 下被放行、并非精确求解"；`note` 同步写明。文档与工具描述强调 `geometry_tolerance_mm` 是**验收放行阈值**，不是求解精度。
- 拒绝报文保留原前缀，并在整截面平移时追加实测 `u/v` 与"未被重求解"的说明；1e-5 mm 默认阈值与 autodim 1e-3 mm 告警阈值均未改。
- 坐标模式试点：`coordinate_anchors` 能覆盖两个轴向时，为坐标原点补零值点-基准线尺寸把它钉住；参考不足输出 `SKETCH_ORIGIN_PIN_UNAVAILABLE`，创建或赋值失败输出 `SKETCH_ORIGIN_PIN_FAILED` 并继续原流程，不让原本可建的草图因试点而失败。
- Python 侧 `normalize_sketch_shifted()` 只回显实测值：缺字段保持缺省、非法或自相矛盾的记录降级为显式不可用、`accepted_by_request` 绝不由投影推断；`bridge.py` 的 compact 白名单加入该块。

### 4. save/erase 两处拒绝给出可执行下一步（BUG-106）

- `creo_save_model` 的 origin 不匹配：保留原句，追加"会话内有同名模型"的成因、`creo_erase_session_models(action='inspect')` 读取目标、`creo_erase_session_models(targets=[{name: ..., model_type: ...}])` 的调用形态与 `retry creo_save_model`，并声明会话副本不会被自动擦除。
- `creo_erase_session_models` 的 `modified` 拒绝：追加"在 Creo 用 File > Save 保存或丢弃修改 → 重新 `inspect` → apply 同一批目标"，并声明擦除不会替调用方保存或丢弃。
- 拒绝条件、回执结构与 `adopt_session_copy`（仍不实现）均未改动。

### 5. 台账与工程整理

- 工作区 42 项脏/未跟踪内容逐项定性并记入 [DEV-064](work-items/DEV-064.md)：`session_erase/` 的 34 份擦除回执、`trail.txt.*`、`std.err`/`std.out`、`examples/*.prt.*` 为本机运行物，新增根锚定忽略规则（不删除现场文件、不入包）；工具目录与 `session_activity.json` 只记录、不改变。
- 台账 161→164 行（新增 BUG-107、BUG-108、DEV-064），分类按实际行状态重算（开发中 4、待复现 24、待核实 10、待开发 0、验收中 30、待规划 42、观察中 3、未收口 51）。

## 验证摘要（2026-11-02，本机）

| 项 | 结果 |
| --- | --- |
| 全量单元 | `python -m unittest discover -s tests` **2 185 项 0 失败**（0.11.3 起点 2 158，新增 27） |
| 单测报告 | `tools/test_unit.py` → `build/unit_test_report.json`（`tests_run=2185`、`success=true`） |
| 开发检查 | `tools/dev_check.py --work-item 0.11.1-feedback-r12` `success=true`，样式无新增回归 |
| 原生构建 | `bridge.py build` exit 0，执行器 13 276 672 B / `8ab6978e…` |
| 常量生成 | `build/generate_constants.log` 无 `MISSING_SDK_HEADER`（本机 SDK 31 头全在），常量 6 563 |
| 种子包 | 重建三次同哈希 `666f9c80…`，`docs/seed_package.json` 受信摘要一致（24 files / 9 seeds） |
| 实机（Creo 12.4.0.0） | `tools/test_sketch_shift_batch.py`：4 个细长钝角三角条草图（260×20.9，坐标标注；3 个默认容差 + 1 个请求容差 0.01）+ 实体挤出全部 `succeeded`，`saved_file_reloaded_and_verified=true`；`sketch_shifted.detected=false`（max 1.4e-14 ~ 1.9e-33），`SKETCH_ORIGIN_PIN axis=0/1` 均生效 |

## 未验证范围

- **Creo 10 / Creo 9 实机**：本机无对应 SDK 与许可；缺头跳过路径只由离线夹具与契约测试证明，"报告方构建成功"未在本机复现。
- **报告方 0.004 mm 平移未复现**（本机 12.4 四个细长三角条偏差 ≤1.4e-14），因此"原点钉住是否消除该平移"仍**未定因**；`accepted_by_request=true` 的真实触发样本未取得，该分支仅由单测覆盖。
- 报告方 24 条带 194 ops 计划 JSON 未提供，无法重放同一输入；P12 续推仍归 [FEAT-054](work-items/FEAT-054.md)。
- G5 三算子（`surface_loft`/`project_curve`/`surface_trim`）仍待规划（[FEAT-055](work-items/FEAT-055.md)）。
- 同名外部模型的 save/erase 两步链路未构造复测；WorkBuddy 黑盒未执行。

## 升级注意

- 升级到 0.11.4 后请使用配套种子包 `MCP_CREO_MechDog-0.11.4-seed-library.zip`；`docs/seed_manifest.json` 与 `seed_library/seed_manifest.json` 的 `compatible_server_version` 已同步为 0.11.4，旧种子包会被版本闸门拒绝。
- 若调用方按 `geometry_deviation.max_deviation_mm` 判断"是否精确"，请改为同时检查 `sketch_shifted.detected` 与 `accepted_by_request`：前者是位移事实，后者是放行来源。
- 公开工具数与参数签名未变；如需长期放宽某个草图的阈值，仍建议在计划里显式写 `geometry_tolerance_mm`，并在回执中保留 `accepted_by_request` 记录。
