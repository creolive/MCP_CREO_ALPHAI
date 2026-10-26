# DEV-047 / T12 官方批处理、拔模及单位回归示例离线验收

日期：2026-10-26（Asia/Shanghai）。条目：FEAT-008、BUG-080，汇总 DEV-047 T12。基线 `e2a7714`（T00—T11 已纳入）；分支 `codex/dev047-t12-examples`。本次源码版本仍为 0.6.1，0.7.0 集成与发布由 T13 收口。

执行说明：本任务原应派发给实现子代理；其客户端后端自 T11 收尾起连续 spawn 即拒（详见 T11 记录），经一次重试仍拒绝且未产生任何变更后，由集成负责人按任务书直接实现，全程未连接 Toolkit。

## 交付物

- `examples/dev047_t12_batch_append.json`：对既有受管零件一次计划追加 6 个特征（顶面双凸台 + 通孔切除）的最小官方示例；说明 expected_revision、一次保存重载、整作业单次 revision 推进、失败整体回滚与 200 操作上限；凸台草图位于基体顶面（XY offset 10），全部增/减体积可解析核算（16000 + 2000 + 500 − 90π）。
- `examples/dev047_t12_draft_boss.json`：Ø6×3 凸台 11° 内拔模官方示例；draft 目标为巡检取得的圆柱侧面真实几何 ID（示例保留文档化占位符，不硬编码），中性面为基面 z=0；`r_top = 3 − 3·tan(11°) ≈ 2.416859`，圆台体积 `πh/3·(R²+R·r+r²) ≈ 69.403 mm³`（棱柱 84.823、去料 15.420）；expect 明确方向翻转时断言失败并以 `flip:true` 为记载的处置，不静默接受任一方向。
- `tools/test_t12_examples.py`：默认纯离线（OFFLINE ONLY，无 MCP 客户端）——加载两份示例、替换占位符后经真实 `validate_operations` 校验、复算解析常数；`--live --confirm-session-usable` 才创建客户端，模式与 `tools/test_t06_native.py` 一致（`auto_start_creo=false` 前置检查、180 秒只读启动观察、busy/unknown 即停、不自动重试、provenance 持久化）。live 侧覆盖：批量 6 操作 → 6 条零基 index 结果全部 `succeeded/committed`、revision 恰 +1、`saved_file_reloaded_and_verified=true`、体积 18217.2567；拔模 → 巡检按半径 3 与 Z 平行轴识别真实圆柱面后 draft，体积断言圆台公式值。
- `tests/unit/test_t12_examples.py`：6 项专项——两份示例经真实 schema 校验、占位符不落成真实 ID、事务/上限/回滚说明在文、批量与拔模解析常数自洽。
- README 迁移口径小节补固定单位矩阵验收模板说明（毫米/英寸/混合/未知四场景分别取证、未知为 null）与两份新示例入口。

## 已执行的离线检查

环境：Windows 11 x64；Python 3.12.14；Ruff（.venv）。无原生改动。

| 命令/检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t12_examples -q` | 6 项通过 |
| `python tools/test_t12_examples.py` | OFFLINE ONLY；两份示例通过真实 validate_operations，解析常数 r_top=2.4168590725868446、frustum=69.40338944342489、cylinder=84.82300164692441、removed=15.419612203499526 |
| `python tools/test_t12_examples.py --live`（缺确认标志） | 按设计拒绝，未连接 |
| ruff check + format --check（2 个新 Python 文件） | 全部通过，无基线豁免 |
| `python -m unittest discover -s tests -q` | 全量通过（964 项，210.041 秒，exit 0；`build/t12-unit.log`） |
| `python tools/dev_check.py --work-item FEAT-008` | exit 0、`success=true`、`unit_tests=passed`；证据 `build/development_check.json`、`build/t12-devcheck.log` |

dev_check 指纹：基线提交 `e2a7714683225371c18bdb52dce282c58f34bf88`、dirty=true（验证时含本次改动）、`checked_source_sha256=d3f6be046dab1a4c849d7ea305d3766e639563bdaa5e59ac13eeceaf72db7f75`。提交后仅追加本记录与台账文档。

工作区原有 `session_activity.json` 修改与未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/*` 保持原状，未提交。

## 未测与保留范围

- **实机未验收，live 驱动未运行**：批量一次 revision、T02 六条结果状态、保存重载、真实面引用拔模与圆台体积、方向/flip 约定均待 T13 在真实 Creo 会话取证。
- 既有装配矩阵/单位驱动（`tools/test_assembly_matrix.py`、`tools/test_assembly_units.py`）本轮只核对文档入口与契约描述，未重跑；多组件装配与矩阵示例在新结果契约下的实机回归归 T13。
- 外部 Creo 10 原拔模案例未复现；WorkBuddy 未执行。
- 本轮未连接 Toolkit、未创建 MCP 客户端、未启动/结束 Creo、无会话探测/故障注入、未清 unknown 保护。
