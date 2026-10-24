# MCP_CREO_MechDog 0.5.2 版本说明

日期：2026-10-24。本次为 0.5.0 反馈整合第一批（PATCH，无新增公开工具，工具数 91 不变）。基于 0.5.1。

## 变更

- **BUG-080 装配变换单位契约**（P1）：`creo_inspect_session_assembly` 不再把装配单位硬编码为毫米。
  - 新增 `assembly.length_unit`：装配自身长度单位的名称、毫米换算系数 `scale_to_mm` 与单位查询返回码；`transform_convention` 的口径声明与实际数值一致。
  - 每个组件节点新增 `units.component` 与 `units.parent`（各自单位名称与毫米换算系数），英寸装配含毫米组件等混合单位装配可直接判定数值口径。
  - `transform_to_parent` 统一为毫米归一化的全坐标映射（旋转与平移按组件/父装配单位换算；行向量约定 p'=p*M、平移在末行不变）；新增 `transform_to_parent_raw` 保留源/目标单位的原始矩阵。
  - 单位或父级变换无法确认时规范化结果标为未知并传播不完整状态；缺件、父变换失败、子装配遍历失败的完整性标志逐项核对。
- **FEAT-006 收养拒绝有界逐特征诊断**（0.5.0 反馈第一批 P1-5）：`creo_adopt_current_model` 以 `reason_code=unhealthy_features` 拒绝时，`refusal_details.unhealthy_features` 逐特征列出 `id`、`name`、`type_name`、`status_code`（Toolkit 原始整码）、可读 `status` 与 `incomplete` 标记；原生侧 20 条上限附真实总数（`unhealthy_total`/`returned`/`truncated`），Python 侧另设 50 条防御性截断，明细缺失或畸形（旧执行器）回退原合并口径文本。apply/prepare 防线拒绝消息同步携带总数与已列条数。健康准入规则本身未改。
- **DEV-046 第一批收口**：0.5.0 反馈整合登记与原件归档（0.5.0 随版文档），第一批证据、状态与正确性项（BUG-080、FEAT-006）随本版交付；后续批次见[0.5.0/0.5.1 反馈计划](development/0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md)。

## 兼容与迁移

- 无新增/停用公开工具；除下述一处数值口径修正外均为响应字段兼容性新增，客户端无需修改。
- **`transform_to_parent` 数值口径变化**：0.5.1 及之前返回装配原单位的原始矩阵（英寸装配即英寸值）却声明毫米；本版起为毫米归一化映射。需要原始单位数值的客户端改用 `transform_to_parent_raw`，并以 `assembly.length_unit` 与 `units.*` 判定口径。此前把旧值当毫米使用的管线（BUG-080 反馈场景）本版起得到正确毫米值。
- `refusal_details.unhealthy_features` 为新增结构；`health_breakdown` 文本由合并计数口径改为逐特征口径。

## 验证与未测

- 开发侧（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC，task/2 整合树）：BUG-080 离线原生夹具 27 个单位/变换 case + 12 个遍历状态 case 全部通过（`tools/test_assembly_units.py`，SDK 查询替换、无 Toolkit 连接），Python 单测含 `tests/unit/test_session_assembly.py` 8 例与收养明细 4 例；整合树全量单元测试与 `tools/dev_check.py` 结果见[发布核对](validation/RELEASE-0.5.2.md)。
- 2026-10-24 实机取证（[记录](validation/BUG080-FEAT006-LIVE-2026-10-24.md)，公开 MCP 工具 + 最小 Toolkit 夹具）：英寸模板装配放入毫米组件于 (1,2,3) inch——`length_unit`=inch/25.4、`units.component`=mm(1.0)、`units.parent`=inch(25.4)、`transform_to_parent` 平移 [25.4, 50.8, 76.2] 且旋转为单位阵、`transform_to_parent_raw` 平移 [1,2,3]、`complete=true`；抑制特征的种子零件触发 `unhealthy_features` 拒绝，逐特征明细（id/名称/类型/状态码/状态）齐备。inspect 前后会话清单一致（只读五不）。过程含一次连接 -4 复发，按 BUG-001 纪律经用户授权恢复后完成取证（记录在案）。
- WorkBuddy 黑盒（[第二轮报告](validation/wb080-blackbox-acceptance-2026-10-24.md)）：FEAT-006 全部断言通过（含 NO_CURRENT_MODEL 分支复验）；BUG-080 该轮经修复前主仓服务运行，缺字段与原始英寸矩阵恰好黑盒确证缺陷本体；同对象 A/B 经整合树服务返回正确毫米归一化与 raw 值。第三轮（BUG-080，整合树服务 0.5.2，[报告](validation/wb080-blackbox-round3-2026-10-24.md)）**全部通过**：环境确认 0.5.2、前置两件套在会话、核验 a–e 逐项达标（`length_unit` in/25.4、组件 mm(1.0)/in(25.4)、`transform_to_parent` 单位阵+平移 [25.4,50.8,76.2]、`transform_to_parent_raw` 平移 [1,2,3]、`complete=true`）、两次 inspect 逐项一致、会话 fingerprint 前后不变；同装配两组件实例均核验合规。
- 未测范围（如实披露）：Creo 9 / Creo 10 实机未测（按 2026-10-15 用户决定不作为发布门槛）；并发能力维持 [BUG-009](work-items/BUG-009.md) 记录边界（单通道忙拒，无队列）；BUG-080 多级嵌套装配与缺件/父变换失败/子装配遍历失败路径以离线夹具覆盖，实机单层混合单位已测，三个生产失败分支的实机触发仍保留未验证；BUG-058 外部 -11 待复现；WorkBuddy 未实施并发调用。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1）：恢复 accept 路径 `ProMdlnameBackup` 稳定 -1。根因已定位为损坏会话级（建模/恢复代码零改动，健康会话实机闭环通过），三个历史 dirty 现场仅 `restore_baseline` 可用，收尾动作待操作者选择。
- [BUG-058](work-items/BUG-058.md)（P1）：外部无主窗口 -11 待复现；本机同码 -4 已定位客户端侧 RPC 端点自举端口错位。
- [BUG-063](work-items/BUG-063.md)/[BUG-064](work-items/BUG-064.md)（P1）：非原点轴阵列、surface 平面引用与纯 Z 向 u_axis 两条拒绝路径待复现。
