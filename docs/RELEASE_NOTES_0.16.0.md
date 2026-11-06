# MCP_CREO_MechDog 0.16.0 版本说明

2026-11-06，MINOR 功能批；条目：[FEAT-014](work-items/FEAT-014.md)（钣金四壁盒子的 miter cuts 路线）与 [FEAT-004](work-items/FEAT-004.md)（尺寸归属与修改旧值守卫）。公开工具仍为 **100** 个，无新增工具、无参数迁移、无回调注册变化。

两条开发分支都基于已发布的 `v0.15.1`（`2b57dd5`）开发，本次合并后一并合入 `main` 并发布；合并无垂直冲突（`docs/BACKLOG.md` 与工作卡的状态行为并发修改，按主干最新口径并入）。

## FEAT-014：四壁盒子经 `miter_cuts` 建成

`creo_sheetmetal_flange` 新增可选 `miter_cuts {width, offset}`：

- **原生实现**：在折边特征树里写入 `PRO_E_SMT_MTR_CUTS`（`ADD=TRUE`，宽度与偏移各带类型与数值）。宽度/偏移类型使用 `PRO_MITER_CUT_WIDTH_TYPE_BLIND` / `PRO_MITER_CUT_OFFSET_TYPE_BLIND`（即 `PRO_DIM_ENTER`）；**不使用 GAP 型**——实机证明 `GAP`（`PRO_DIM_SMT_GAP`）提交后会被 Creo 重置为 `PARAM` 且数值清零，任务因此回滚。默认 `offset` 等于 `width`。
- **保护语义变化**：`adjacent_bend_ends` 从"无条件创建前拒绝"改为"仅当请求显式携带 `miter_cuts` 时放行"。**不传 `miter_cuts` 时行为与旧版一致**（仍然拒绝），错误文案保留原有关键词并提示可用 `miter_cuts`。放行时结果里记录 `adjacent_bend_ends_allowed=true`，并原样回显 `miter_cuts`（`add`、两个类型与两个数值，容差 1e-6 核对，不符合即回滚）。
- **实机结果**（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK）：1 mm 底板 42 920 mm³ 起，四道折边 `f_px`、`f_nx`、`f_ny`、`f_py` 全部 `succeeded`，每道 `saved_file_reloaded_and_verified=true`，revision 1→5，终态体积 106 499.16 mm³，报告 `four_walls_complete=true`、整体 `passed=true`。
- **仍未量化**：`width`/`offset` 与实际切除量、角部间隙的定量关系；不同板厚与折弯半径下的行为；删除/修改折边后的回滚。自由端（无相邻折弯）带与不带 `miter_cuts` 的体积差为 0，属预期的空操作对照，不能作为切角量证据。

## FEAT-004：尺寸编辑的旧值、符号与归属守卫

- 新增 `dimension_guards.check_dimension_guard` 与 `DimensionValue.expected_value` / `expected_symbol` / `expected_owner`；调用方可在一次批写里声明期望的旧值、符号名与所属特征，任一不符即整体拒绝，旧 `id`/`value` 调用方式保持兼容。
- 原生 `set_dimensions` 改为两遍式：先读取值/符号/关系/归属，统一判定，最后才写入，避免"前半批已改、后半批被拒"的中间态；巡检补 `owner_feature_id`、`owner_feature_name` 与 `editable`。
- 新增离线回归 17 项（`tests/unit/test_dimension_guards.py`）与实机驱动 `tools/test_adoption_dimension_guards.py`（默认离线，`--live --confirm-session-usable` 才连接）。
- 2026-11-03 的 19 例实机记录属 **rebase 前**源码；本版未重跑该实机回归，结论不外推。

## 本版验证门禁

`bridge.py build` 退出 0（重编 `build/creo_worker.exe`）；`tools/test_unit.py` 全量 **2646 项通过**，0 失败 0 错误；`tools/dev_check.py --skip-unit` `success=true`（24 条 lint、12 个未格式化文件均为 `style-baseline.json` 存量，未新增）。种子内容未变，仅清单版本字段同步：种子包 24 文件、9 种子，两次构建同摘要 `472ea06440d35ff9e6c77f3e3ce9cba8263c255ffbe25563593e26d59e364c53`，已回填 `docs/seed_package.json` 并二次构建确认稳定。受测源码身份见[发布记录](validation/RELEASE-0.16.0.md)。

未验证范围：miter 切角量与角部间隙未量化、不同板厚/半径未测；FEAT-004 rebase 后实机回归未跑；Creo 9/10 未复测；WorkBuddy 黑盒未执行；BUG-001 的会话边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.16.0-source.zip` 与 `MCP_CREO_MechDog-0.16.0-seed-library.zip`，按安装说明更新环境、重编执行器并重启 MCP 服务。旧种子包会被版本闸门拒绝。
