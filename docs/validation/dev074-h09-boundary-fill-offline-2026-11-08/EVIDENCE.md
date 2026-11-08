# DEV-074 H09 `surface_boundary_fill` 离线实现证据（2026-11-08）

本文件只记录**离线**工作：schema/校验、原生树接线、编译与单元测试。**本轮没有启动或连接 Creo，
没有提交实机作业，也没有做任何 `--live` 运行**；H09 早前的 R8 球面旋转读数属于
[`feat039-h09-surface-revolve-2026-11-07`](../feat039-h09-surface-revolve-2026-11-07/EVIDENCE.md)，
不是本实现的实机验收。

工作目录：`e:\Projects\MCP_CREO_MechDog-d074`（worktree，分支 `codex/DEV-074-forming`，
起点 `4155a3a`）。

## 交付范围

- 新公开计划操作 `surface_boundary_fill` / MCP 工具 `creo_surface_boundary_fill`
  （公开工具 105→106）。
- 输入：一条闭合链 `boundary`，3–200 条有序曲线，每条 `{kind:"curve",id:N}`；
  `closed` 只接受默认 `true`。
- 原生：`native/surface_boundary_fill.cpp` 的 `generic_surface_boundary_fill`。沿用
  `surface_loft` 的 `Probbl.h` 裸骨架（`PRO_FEAT_DATUM_SURF` + `PRO_USE_SURFS` +
  `PRO_E_DTM_SRF_TYPE_BND_BLEND`）与 `PRO_FEAT_CR_INCOMPLETE_FEAT` → extract → redefine 流程；
  每条曲线一个 `PRO_E_STD_CHAIN_HOLDER`，在 `PRO_E_BNBLN_1DIR` 写
  `PRO_E_BBL_ADD_CLOSED = PRO_B_TRUE`。
- 原生校验（创建前）：`ProCurveXyzdataEval` 取每条曲线的真实端点，检查相邻曲线与首尾闭合
  （0.01 mm）；重复 id、非曲线 id、开放链、乱序链、未知长度单位直接失败，错误消息给出
  `surface_loft` / `project_curve` 可执行替代。
- 回执：`boundary`/`boundary_curve_ids`/`boundary_edges`/`boundary_closed`/
  `chain_gap_max_mm`、`quilt_id`/`quilt_ids`/`quilt_count`、`face_count` 及其 status、
  `surface_area_mm2` 及其 status、`quilt_closed_native`/`closure`、`surface_group`、
  `has_solid`/`solid_surface_count`、create/extract 代码与元素错误样本。
  测量值全部来自原生 quilt 查询，不用请求值回填。
- 回滚：不新增机制，失败由 job 级既有检查点恢复处理。
- 投影：`job_projection.SURFACE_BOUNDARY_FILL_KEYS`；`operation_results.annotate_surface_group`
  同步规范化本算子的 `surface_group`。
- 文档：`G5-NATIVE-CONTRACT.md` §2.12、`FEAT-039.md` 文末 H09 新增段、`DEV-074-HANDOFF.md`
  H09 行。
- planar `surface_fill` 未改：`FillOp` 仍只有 `sketch`，`generic_fill` 仍写 `PRO_FLAT` +
  `PRO_E_SEC_USE_SKETCH`；把 `boundary` 传给 `surface_fill` 会在受理前被 strict schema 拒绝。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，产出 `build\creo_worker.exe`（格式化前后各一次） |
| `.\.venv\Scripts\python.exe -c "import asyncio, server; print(len(asyncio.run(server.mcp.list_tools())))"` | `106`，且包含 `creo_surface_boundary_fill` |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_surface_boundary_fill_contract -v` | **22 项通过，0 失败 0 错误** |
| 定向单测（`test_surface_round_contract`、`test_t01_capability_contracts`、`test_reference_contract`、`test_callback_admission`、`test_update_check`） | **69 项通过，0 失败 0 错误** |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests` | **2983 项通过，0 失败 0 错误**（332.4 s） |
| `ruff check`（本次改动文件） | All checks passed |
| `ruff format --check`（本次改动文件） | 全部已格式化（新测试首次检查后格式化一次） |
| `clang-format --style=file --fallback-style=none --dry-run --Werror native\surface_boundary_fill.cpp` | 无差异 |

## 契约边界（离线）

- 允许：一条闭合链、3–200 条不同曲线、已知长度单位、一条时间线内的有序几何。
- schema 拒绝（无 job_id）：空/1–2 条、重复边、嵌套列表/多环/孔、非曲线 kind（quilt/face/
  edge/body/标签）、曲线带 `label`/`reverse`/额外键、非整数/负数/布尔 id、`closed=false`。
- 原生拒绝（无 job_id 或整体回滚）：曲线 id 不可解析为非曲线、链未按提交顺序相接、首尾不闭合、
  未知长度单位、创建/抽取/redefine 失败、结果不是 ACTIVE datum surface、非 1 个 quilt、
  面积不可测、产生实体、结果 quilt 不是开放面、面不可读。
- 单位未知：直接拒绝，因为 0.01 mm 容差与 mm² 面积都无法判定；不使用模型内部单位猜测。

## 未验证（继续开放）

- **实机未验证**：内核是否接受“单向 + N 个 `PRO_E_STD_CHAIN_HOLDER` + `PRO_E_BBL_ADD_CLOSED`”
  并生成一张闭合填充面；`DIR_CURVES` 的顺序与曲线方向是否按提交顺序消费；结果 quilt 数、
  面数、面积、闭合与边界边数是否与输入环一致；保存重载与失败回滚路径。
- 未测：非 mm 单位（当前拒绝）、曲线方向反转的边界、复合曲线、孔/多环、Creo 9/10、
  真实并发/通道占用、WorkBuddy 黑盒验收。
- 实机确认前不解除“任意非平面 fill 不可用”的对外结论；本实现只进入离线实现状态。
