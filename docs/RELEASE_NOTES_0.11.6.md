# MCP_CREO_MechDog 0.11.6 版本说明

- 类型：PATCH，行为修正与可观测性；公开工具仍 **95 个**，无新增工具。
- 条目：[DEV-065](work-items/DEV-065.md)（0.11.5 第十三轮反馈批 R13），关联 [BUG-108](work-items/BUG-108.md)、[BUG-109](work-items/BUG-109.md)、[BUG-110](work-items/BUG-110.md)、[BUG-111](work-items/BUG-111.md)。
- 版本入口：[version.py](../version.py)；配套种子包 `MCP_CREO_MechDog-0.11.6-seed-library.zip`。
- 反馈归档：[5 份原件逐字节归档](validation/feedback-0.11.5-2026-11-03/manifest.json)与[逐章映射](validation/feedback-0.11.5-2026-11-03/MAPPING.md)。

## 本版内容

本版只处理"作业失败后无定位、无解释、无出路"的 A 组四项；曲面链、`tools/` 的 git 兜底与负例输出、端点缝隙、draft 成功路径回显、`get_job` 长轮询均只登记待规划，**未实现**。

- **`verify_model` 阶段可定位（BUG-109）**：原生把 `verify_model` 拆成 `verify_model_start/regenerate/inspect/assertions/before_save/save/erase/reload/reload_regenerate/reload_inspect/compare/after_reload/preview` 13 个子阶段，每段写 `STAGE name= elapsed_ms= since_start_ms= ts=`；成功与失败回执都带 `verify_stages`（≤32 条）。`creo_get_job` 在 `queued`/`running`/`failed`/`unknown_outcome` 时追加只读 `native_progress`（stage/sub_stage/elapsed_ms/since_start_ms/idle_seconds/log_bytes/stages_seen/reason，只 seek 日志末尾 8 KiB）；超时文案点名最后子阶段与停滞秒数。总预算 600 s、`unknown_outcome` 语义、无自动重试均未改变，未做子阶段强杀。
- **坐标求解按"形状"而非"点位移"判定（BUG-108）**：`verify_coordinate_plan` 与 `enforce_geometry_deviation` 都改为看"去掉共模平移后的逐点残差"——可证刚体平移且平移 ≤1e-2 mm 时放行并标 `accepted_rigid=true`（日志 `GEOMETRY_DEVIATION_RIGID_ACCEPTED`），平移超限则拒绝并写明平移量与上限；**形状闸门仍为 1e-5 mm，默认阈值未放宽**。`geometry_deviation` 与 `sketch_shifted` 在成功与失败时都带 `shape_deviation_mm`/`residual_mm`/`rigid`/`translation_mm`/`translation_magnitude_mm`/`accepted_rigid`，旧字段与 `exceeds_warning` 语义不变。
- **装配失败有元数据出路（BUG-110）**：`creo_reconcile_model` 新增 `action="ack_failure"`（需 `confirm_failure_ack=true`），把终态失败/`unknown_outcome` 的模型以**纯注册表事务**退回 `ready`：不启 worker、不连 Toolkit、不改 revision、不改模型文件、不改组件绑定；审计块记 `prior_status`/`prior_job_status`/`outcome_uncertain`/`disk_state_verified=false`/`component_ownership_preserved=true`。四个触碰组件所有权的动作仍只对零件/钣金可用。
- **旋转范围与失败归因（BUG-111，行为收紧）**：`geometry_transform`/`set_geometry_transform` 的 `rotation` 分量前置限制在 **-180..180 度**，超范围在提交前拒绝并给出等价值（如 225 → -135，**此前会提交后吃内核裸 -1**）；两条原生后端统一归一为 `(-180, 180]`（旧实现把负角 `+360`，使 −135 与 225 走不同路径）。transform 失败回执新增 `failed_transform`（backend、请求与归一角度、平移、`keep_original`、引用数与类型），并保留 `failed_operation_index`。

## 验证与边界

- 离线：全量 **2241 项单测 0 失败/0 错误**（起点 2196，新增 45 项）、`tools/test_unit.py` `success=true`、`tools/dev_check.py --work-item 0.11.5-feedback-r13` `success=true`、`bridge.py build` exit 0（执行器 13 323 776 B / SHA256 `0f556504…`，源码指纹 `cd22b563…`）。
- 本机 **Creo 12.4.0.0 实机（2026-11-03，用户授权启动会话）**：阶段归因 3 个作业各 13 个 `verify_stages` 且 `jobs/<id>/native.log` 对应 13 行 `STAGE`，终态不带 `native_progress`；坐标草图 4 例 + 挤出全部成功、新字段齐备（4 例 `rigid=false`，整体平移仍未复现）；装配失败作业 `failed` 后模型仍 `ready`（无死路），对 `ready` 硬发 `ack_failure` 被拒；225° 提交前拒绝并给 `-135`、单个 −135° 副本成功、**5 op 与 7 op 批次均在 `operation_index=4` 失败**（第 5 个 `keep_original` 副本现象在 12.4 复现两轮，根因未定）。
- **未验证**：Creo 9/10 构建与建模；WorkBuddy 黑盒；`ack_failure` 成功路径（本机无法在不冒组件所有权风险的前提下造出 `failed` 装配，只由单测与 MCP 层测试覆盖）；`accepted_rigid=true` 实机分支；真实 10 分钟停滞场景；报告方 `native.log`/`request.json`/P12 计划原件（未随包）。
- 环境：Windows 11 x64 / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK；检查无新增风格回归，不代表全库存量严格格式清零。
- 本版含原生改动（`native/generic.cpp`、`native/sketch_coordinates.cpp`、`native/placement.cpp`），需重新编译执行器；第三方文件未修改。

## 升级

1. 使用成对的 0.11.6 源码包与种子包；种子 PRT 字节不变，两份清单的 `compatible_server_version` 已更新，旧种子包会被版本闸门拒绝。
2. 重新运行 `setup.ps1`，或在安装虚拟环境执行 `python -m pip install --no-deps -e .` 后重启 MCP 服务加载新模块。原生代码有变更，首次启动会重建/校验 `build/creo_worker.exe`。
3. 调用方需要复核的语义变化：`rotation` 分量超出 ±180° 现在**提交前拒绝**（此前提交后由内核失败）；`geometry_deviation`/`sketch_shifted` 新增字段只增不改，旧回执缺字段保持缺省、不推导；`creo_reconcile_model` 的 `action` 枚举新增 `ack_failure`，不传 `confirm_failure_ack=true` 不会执行。
