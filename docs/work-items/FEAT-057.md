# FEAT-057：真实材料质量属性

类型：功能。优先级：P2。状态：部分交付（0.18.1 发布密度/单位/缺失原因回执契约，离线验证；主惯量、装配汇总与 Creo 实机待收口）。目标版本：0.18.1（已发布）；剩余范围未排期。

来源：2026-11-03 用户要求比较 alphai 项目并建立由用户自行派工的计划；静态参考源码不构成当前实机证据。

关联：FEAT-045、BUG-080；骨架身份与后续 B01 对接。

## 目标与范围

新增受管 part/sheetmetal/assembly 的只读质量接口；查询实际材料密度与单位，输出 kg、mm 重心、主惯量及完整性；按 occurrence 计重复实例，缺材料/未知单位/失败组件不返回伪造总质量。

明确边界及拟接口见[设计依据](../superpowers/specs/2026-11-03-alphai-capability-adoption-design.md)。本卡固定身份不能被历史反馈中的同号误写引用替代。

## 派工与验收

- 任务号：A01；负责人：unassigned；[子计划](../superpowers/plans/2026-11-03-alphai-a-foundation-plan.md)；[主计划](../superpowers/plans/2026-11-03-alphai-capability-adoption-plan.md)。
- 判据：已知 6000 mm³ 钢材夹具质量 0.0471 kg；两个实例 0.0942 kg；混合单位、缺材料、组件失败、源文件/revision/窗口不变；当前原生查询证据和独立单位/完整性回归。
- 开发环境：Windows x64 / Python 3.12+；原生适用时 Creo 12.4.0.0 / 匹配 SDK/许可，先满足 BUG-001 条件并由会话负责人串行安排。Creo 9/10 未测不能外推。
- 对应专项 unittest、默认离线驱动、构建、实机命令与错误/恢复矩阵见子计划；所有 live 驱动默认离线。WorkBuddy 如安排则只做公开 MCP 黑盒，不替代内部验证。

## 实现与证据

2026-11-03 仅登记和规划；未修改产品代码，未运行产品测试、未连接 Creo、未提交/合入 main/发布。执行者按主计划交接实际提交、dirty、受测源码指纹、命令、环境、结果和未测范围；完成后由集成人同步主台账、能力边界与发布记录。

## 2026-11-04 跨工作树核验与后续动作

已有实现及显式密度的用户决定按A01验收摘要保留。本次纯函数复现NaN质量/Inf重心未被拒绝；材料实际重心、P00回执差异、卡头/工具文案需收口。此状态不代表main已包含该工具；接续R03，不从零重做。

详见[核验记录](../development/DEV067-POST0120-AUDIT-2026-11-04.md)和[后续计划](../superpowers/plans/2026-11-04-alphai-post0120-integration-plan.md)。本次只改记录/计划，未修改该任务产品代码或进行新实机。

## 2026-11-04 离线数值守卫子项

本次只修改回执归一化模块和专项测试：拒绝三标量/三维重心中的 NaN、±Inf，把巨大整数转 float 的溢出统一为含字段/坐标位置的 ValueError，在自洽比较前拒绝乘法和差值的非有限中间值。保留缺省/None、非数字/形状错误重心的旧行为、有限负重心、正常 6000 mm³ / 7.85 g/cm³ / 47.1 g 和回执元数据；未改公共签名、字段、单位或密度优先级。

环境为 Windows x64 / Python 3.12.14，解释器 `.venv/Scripts/python.exe`、实际包路径 `src/creo_mechdog/mass_properties.py` 与 `SOURCE_PATHS.resource_root` 均核对属于 `E:\Projects\codex-A01`。受测基线 `f4be20e9cc1921ae031d453b61cf1b27c4317f4a`，测试时 dirty=true；开发检查受测源码指纹 `e99c50c61fedb59dc7372aadfa5a346f168b3875f48ca45607af4b3d59a0e428`。

- `.\.venv\Scripts\python.exe -m unittest tests.unit.test_mass_properties -v`：修复前 20 例，48 failures / 12 errors；修复及格式化后 20/20 通过。
- `.\.venv\Scripts\python.exe -m ruff check src/creo_mechdog/mass_properties.py tests/unit/test_mass_properties.py` 及相同文件的 `ruff format --check`：通过。
- `.\.venv\Scripts\python.exe tools/dev_check.py --work-item FEAT-057-numeric-guards`：失败，四个未修改测试文件的既有格式问题阻断（test_callback_admission、test_reference_contract、test_t01_capability_contracts、test_update_check），unit_tests=not_run；未改其他文件或重建基线。不得将单独单测结果等同于该检查通过。

本次无原生改动/构建、无 Toolkit/Creo/MCP 连接、无 live 驱动。真实材料重心、混合单位/未知单位、同步/异步接口、主惯量与 complete 契约等其余 A01 范围仍开放，历史实机记录不构成本次证据。原始日志和详细交接保存在本机 `build/feat057_numeric_guards_20261104/task-1-report.md`，交控制者独立审查。

独立全量离线单测 `.\.venv\Scripts\python.exe tools/test_unit.py`：2288/2288 通过、0 failures / 0 errors，退出码 0（稳定日志 `build/feat057_numeric_guards_20261104/unit-full.log`）。此结果与失败的 dev_check 分别记录。

本子项稳定本机证据目录为 `build/feat057_numeric_guards_20261104/`（Git 忽略）：`task-1-report.md` 为交接报告，`red.log` / `green.log` 为专项红绿回归，`dev-check.log` 为失败的完整开发检查，`unit-full.log` 为独立全量离线单测，`unchanged-style-files.json` 为四个格式阻断文件相对基线未变的哈希证据。该目录保留证据以供计划临时目录清理后追溯。

## 2026-11-07 密度/单位/缺失原因契约补步

分支 `codex/FEAT-057-density-contract`（基线 `58dd76b`，0.18.0 发布提交）。本次只补回执契约，不做实机：

- 单位口径固定：`mass_g` 恒为克，`density_g_cm3` 恒为 g/cm³；`mass_unit` 是模型自身质量单位名，只有 `g`/`kg`/`tonne`(t) 会被换算，其余单位不猜换算因子。
- 原生 `mass_properties` 新增 `mass_unavailable_reason`：材料存在但查询失败 `material_query_failed`、单位不可换算 `unsupported_mass_unit`、材料无可用密度 `material_density_unavailable`、仅给请求密度但体积未知 `volume_unavailable`、既无材料也无请求密度 `no_density`；对应 hint 不再一律提示“先赋材料”。
- Python 归一化新增原因枚举校验：未知原因拒绝；`density_source` 非 `none` 时携带原因拒绝；旧原生回执无该字段时保留 `null`（版本错配不误判）。
- 工具说明同步单位与原因，`material_assigned`/`mass_unit`/`density_source` 语义不变。

验收：`tests/unit/test_mass_properties.py` 24/24 通过；`bridge.py build` 组合编译通过（Windows x64 / Creo 12.4.0.0 匹配 SDK）。**未连接 Creo/Toolkit**：原生原因分支、真实材料密度、英寸/磅单位模型、保存重载均无实机证据；主惯量、装配 occurrence 汇总与 `complete` 契约仍开放。已随 0.18.1 发布（离线），发布记录见 [RELEASE-0.18.1](../validation/RELEASE-0.18.1.md)。
