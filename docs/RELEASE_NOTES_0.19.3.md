# MCP_CREO_MechDog 0.19.3

日期：2026-11-09。类型：PATCH。公开工具：107（与 0.19.2 相同）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.19.3 集成第四份 0.19.0「简易护卫舰」反馈的 [DEV-081](work-items/DEV-081.md) A 批离线处理、[DEV-080](work-items/DEV-080.md) 首批离线收口，以及 B/C 批子计划与 [BUG-001](work-items/BUG-001-FEAT-018-RECOVERY.md) 实机放行规则修订。全部改动集中在 Python 输入校验、回执文案、能力说明、工程配置与文档；未改 `native/*.cpp`、未改公开工具签名、未改能力门禁，按 PATCH 发布。

## 本版变化

### 输入校验（DEV-081 F02 / F03）

- F02：两段精确圆弧在轴上相接不再因浮点残差被 `near_tolerance` 误判为开放轮廓。`validate_solid_profile` 以 `RESIDUAL_RATIO=1e-3` 放行残差级闭合，`5e-7` mm 及以上的既有保护不变；所有拒绝都附带可复制的补救建议（`closure_tolerance_mm`、`snap_endpoints`、`endpoint_policy=weld`、折线合并）。
- F03：半径/尺寸类字段改用独立的 `schema_base.Dimension`（上限 \(10^6\) mm、拒绝 bool），错误信息说明这是服务 API 上限而非 Creo 内核限制；平移等其它 `Positive` 字段不变。

### 回执、文案与限制可见性（DEV-081 F04 / F07 / F05 / F11）

- F04：`creo_session_status` 在 `toolkit_code=-4` 且未连接时给出显式 `creo_startup_status(retry=true)` 步骤；不改恢复策略、不自动重启、不清 unknown 保护。
- F07：更新检查失败的文案给出 `MECHDOG_UPDATE_TIMEOUT_SECONDS` 与 `creo_check_update(force=true)`，并明确 `update.status=failed` 不等于「已是最新」；默认 5 秒预算不变。
- F05：`creo_capabilities` compact 视图的 `families.surface_loft` 增加 `limits_note`（≤160 字符、单一真源）；full 仍是完整 `limits`，`surface_boundary_fill` 门禁不变。
- F11：`SketchOp.offset` 描述、`creo_execute_plan` docstring 与 `REFERENCE_SYNTAX` 写清三平面 `offset` 的全局坐标语义与 `direction` 相对法向（XZ 为 −Y）。原生错误信息里附实际原点/法向/有效深度仍留 B 批。

### 工程整理（DEV-080 首批离线收口）

- 新增手写 TU 头门控契约测试，锁定 Creo 10 缺头 SDK 下的降级行为；[COMPATIBILITY](COMPATIBILITY.md) 补齐缺头降级说明。
- `tools/check_backlog_counts.py` 的台账计数自检进入 Windows CI 的独立步骤；`docs/BACKLOG.md` 与 DEV-080/DEV-081 工作卡同步至 172 / BUG 75 / FEAT 61 / DEV 36。

### 规划与规则（不产生新的建模能力）

- 建立 [B/C 批子计划](superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md)与 [WorkBuddy 黑盒提示词](validation/feedback-0.19.0-frigate-2026-11-08/workbuddy-blackbox-prompt.md)：把需原生/实机的 F01/F06/F08/F09/F10/F11 拆为 B1—B6，公开契约/黑盒拆为 C0—C5。本版只交付规划，不含原生实现。
- 按用户 2026-11-09 决定修订本机实机放行条件：用户当次明确确认后即可使用 Creo 实机测试，不再以卡死根因核对或事前会话可操作判定作为阻断前置；确认按次生效，安全底线与单通道/busy/revision/保存重载边界不变，历史失败与恢复原件逐字节保留。见 [AGENTS.md](../AGENTS.md)。

## 验证

- 全量 Windows 单元测试：`Ran 3150 tests in 409.732s ... OK`（工作树，Python 3.12.14）。
- `tools/dev_check.py --work-item DEV-081 --unit-timeout-seconds 1800`：EXIT=0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；受测源码指纹 `7ebb77e7a1e89f92871a03a175bd262cbd634904b65a11af4e647f7621699d56`（`source.dirty=true`，提交号仅作定位）。风格基线为存量 21 项 lint / 10 个未格式化文件，未新增诊断。
- `tools/check_backlog_counts.py`：`consistent=true`（172 / BUG 75 / FEAT 61 / DEV 36）；`git diff --check` 通过；改动文档 `read_lints` 0 诊断；相对链接全部可达。
- 种子包按确定性流程构建两次，SHA256 一致并回填 `docs/seed_package.json`；源码包与种子包各自生成 `.zip.sha256` sidecar。
- **源码包解压后全量单测为独立门禁**，其结论见 Release 正文与 [发布记录](validation/RELEASE-0.19.3.md)；源码包内的本文件保留发布前占位。
- 本批未连接 Creo、未启动会话、未编译原生执行器、未做几何/保存重载/回滚实机验收，未执行 WorkBuddy 黑盒。

## 未测范围与已知限制

- A 批六项均为「离线已交付、实机未验」：精确圆弧闭合轮廓能否在 Creo 中成功建模、大半径输入的实际几何效果等尚未实机确认。
- B1—B6（无 callback 放样与 seed 预检、原生错误上下文、阶段进度与日志、选择性布尔、着色预览、锥台/拔模）与 C0—C5 黑盒仍未执行；按用户 2026-11-09 决定，本次会话不执行 WorkBuddy 黑盒。
- Creo 10 的 `Probbl.h` 缺头限制与 `surface_boundary_fill` 门禁不变；Creo 9 / Toolkit 9 的编译探测修复已实现，本机无 Creo 9 SDK，实机编译与建模运行时未验收。
- BUG-001 卡死根因仍未确定，实机证据须如实记录；规则放宽不等于根因已解决，也不得擅自结束/重启 Creo 或清 `toolkit.lock`/unknown 保护。
- 不把本机单测、历史版本或其它环境的通过结论外推为实机验收。

## 安装与升级

安装、客户端注册与种子库步骤见 [docs/INSTALL.md](INSTALL.md) 与 [docs/SEED_LIBRARY.md](SEED_LIBRARY.md)。升级后请重启 MCP 客户端，使新的准入与工具文案生效。本版无需迁移模型或配置；已发布的 `v0.19.2` 标签与四附件保持原样。

## 附件

发布附件固定四个：源码包、种子包及各自 `.zip.sha256`。文件名与完整 SHA256 在 Release 正文与 [发布记录](validation/RELEASE-0.19.3.md) 中给出；源码包内的本文件保留发布前占位，实际摘要以 Release 与 POSTCHECK 为准。
