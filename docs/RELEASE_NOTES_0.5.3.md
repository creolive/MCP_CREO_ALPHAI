# MCP_CREO_MechDog 0.5.3 版本说明

日期：2026-10-25。本次为 0.5.0/0.5.1 外部 Creo 9 反馈整合（阶段一登记 + 阶段三兼容修复与说明，PATCH，无新增公开工具，工具数 91 不变）。基于 0.5.2。

## 变更

- **BUG-081 迁移 owner 拒绝诊断与 inspect 预检**（P1）：`creo_migrate_registry` 的 inspect 预检对每个待迁移条目做只读 owner 观察，会被 owner 守卫阻塞的条目挂有界 `owner_block`（`job_id`/`model_id`、`reason_code`、`job_status`、runner/worker 的 `recorded`/`observed` 投影与 Windows 错误码），顶层报告 `blocked_entries`；apply 拒绝负载携带同一 `owner_block` 结构与 `next_steps` 固定指引，不再只返回笼统 busy。幂等重放不重新审计 owner。停止判定语义与 BUG-074 时间证据适用面**未改**：无法证明 owner 已停止时继续拒绝并解释。
- **BUG-082 在轴剖面编辑失败特征级诊断**（P1）：再生失败响应新增结构化 `failed_features`（逐特征 `id`/`name`/`type`/`type_name`/`status`/`incomplete`/`geometry_items`），实机验证 autodim 改角失败可透出 REV_SK/REV1 的 `status=6` 诊断且回滚干净、体积复原。**autodim 改角再生失败本体仍在（随版披露）**；coordinates 改角、两种标注的改半径与回程在本机 Creo 12.4 成功路径 7/7，体积与 `V=(2πR³/3)·sinθ_max` 逐位一致（本批同时修正了任务材料中的错误期望体积公式）。
- **BUG-083 revolve.axis 入口预检**（P2）：非法轴结构（缺 `kind`、错误类型、不适用引用、空对象）在 Python 计划校验与原生边界统一拒绝，返回字段路径与可操作示例，不再透出 nlohmann 裸 JSON 异常；省略 `axis` 与 `null` 等价（使用截面构造中心线）。新增显式外部轴示例 `examples/revolve_external_axis.json` 与 [REFERENCE_SYNTAX.md](REFERENCE_SYNTAX.md) 用法说明；`server.py` 工具描述同步。
- **FEAT-030 / BUG-034 种子来源与兼容信息透明化**：种子加载失败诊断保留原始 API、错误码、实际阶段、种子标识/SHA256 与可取得的运行版本，原因无证据时为 `undetermined_by_error_alone`，不硬写「由 Creo 12.4 构建」；`seed_build_version` 仅接受绑定该种子 SHA256 的可追溯生成记录或可靠原生证据，否则保持 null（UGC 头仅作 `unverified_clue`）；`available` 口径明确为文件与哈希有效、不代表当前会话可加载；按种子 SHA256/原生 release/会话绑定的历史加载记录落地；capabilities 与[兼容矩阵](COMPATIBILITY.md)如实标注「外部 Creo 9 已报告受测种子 -16；本机 12.4 与历史 Creo 10 成功均不外推」。
- **四项既有条目小修**：FEAT-045 `support_status.assembly_checks` 与已发布的 `creo_inspect_session_assembly` 只读检查对齐；BUG-058 挂起 guidance 区分挂起窗口（hidden/visible）与活动 Dashboard/模态框，结束进程仅作为操作者明确选择的恢复项；FEAT-020 更新检查网络失败明确「未取得最新版本信息」（保留 `latest_version=null` 与实际错误，不阻断建模）；BUG-019 补独立 `round.radius`/`chamfer.distance` 与 `execute_plan` 别名/size 的对照示例与部署核对方法。
- **阶段一登记随版**：两份外部报告逐字节归档（SHA256 复核一致），BUG-081～083 建卡，十组既有卡按子项补录外部证据并保留未测范围。

## 兼容与迁移

- 无新增/停用公开工具；除下述行为修正外均为响应字段新增、诊断增强或文案修正，客户端无需修改。
- **BUG-083 行为变化**：0.5.2 及之前 `revolve.axis` 非法结构以 nlohmann 裸异常文本透出（`key 'kind' not found`），本版起为带字段路径与示例的明确拒绝负载，属缺陷修复；合法显式轴与内部构造中心线语义不变。
- `owner_block`、`failed_features`、`blocked_entries`、种子诊断字段均为新增结构，旧客户端可忽略。

## 验证与未测

- 开发侧（本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK 与 MSVC，集成尖 `e2bba08`，收口证据见 [PHASE3-CLOSEOUT-2026-10-25.md](validation/PHASE3-CLOSEOUT-2026-10-25.md)）：612 项单元测试、`tools/test_unit.py`、`tools/dev_check.py`、`bridge.py build` 复编全部通过（lint 31 / 未格式化 19 为既有风格基线，非本批引入）。
- 实机收口（本机 Creo 12.4）：编辑收口矩阵 13/13（含 BUG-079 离轴回归 R5→R6→R5、重排 no-op rev+1、legacy 夹具哈希还原）；BUG-082 在轴扇形成功路径 7/7 与体积逐位一致、autodim 失败带 `failed_features` 诊断且回滚干净；BUG-083 省略轴 `revolve_modes` 3/3 与显式外部轴隔离新件成功（体积 1000π、保存重载通过）；FEAT-030 两种子（two_straight/two_smooth）加载、证据持久化与保存重载成功。
- 未测范围（如实披露）：Creo 9 全部未复验（本机无 Creo 9 SDK，按既有决定不新增双版本发布门槛）；BUG-082 autodim 改角再生失败本体未修复，外部「coordinates/改半径也失败」未在本机复现、保留外部待核对，球体/半圆贴轴基线失败另立条目；编辑矩阵失败作业 revision 字段未取得（报告格式不含）；种子重生成（环境受阻）与 9 种子安装库回归未执行；BUG-081 实机 MCP 拒绝时序未复现（无同型残留 worker 现场，单测直接断言 payload）；WorkBuddy 黑盒本轮未执行（全部为开发者离线 + 实机脚本证据）。

## 已知问题（随版披露）

- [BUG-082](work-items/BUG-082.md)（P1）：在轴扇形 autodim 改角 90°→80° 再生失败本体仍在（REV_SK/REV1 `status=6`，`ProSectionSolve=-1`），已带特征级诊断、回滚干净；coordinates 路径成功。
- [BUG-078](work-items/BUG-078.md)（P1）：恢复 accept 路径 `ProMdlnameBackup` 稳定 -1。根因已定位为损坏会话级（建模/恢复代码零改动），三个历史 dirty 现场仅 `restore_baseline` 可用。
- [BUG-058](work-items/BUG-058.md)（P1）：外部无主窗口 -11 待复现；本机同码 -4 已定位客户端侧 RPC 端点自举端口错位。
- [BUG-063](work-items/BUG-063.md)/[BUG-064](work-items/BUG-064.md)（P1）：非原点轴阵列、surface 平面引用两条拒绝路径待复现。
