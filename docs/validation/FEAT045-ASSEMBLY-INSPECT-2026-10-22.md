# FEAT-045 装配只读检查实施与验收（2026-10-22）

按 [0.4.6 反馈整合计划](../development/0.4.6-FEEDBACK-PLAN-2026-10-21.md) 第二批实施。分支 `codex/feat045-assembly-inspect`（自 main `c28dc23`）。目标版本 0.5.0（MINOR，新增公开工具，不延用 0.4.6 PATCH 例外），工具数 90→91。

## 实现

- `native/generic.cpp` `session_assembly_native`：按名称选定驻留装配（`ProMdlInit`+类型校验，找不到返回 `SESSION_ASSEMBLY_NOT_FOUND` 结构化错误）；`ProSolidFeatVisit` 树序递归（深度上限 32、总数上限 4096、子装配遍历失败标记该节点 `subassembly_visit_code` 并置 `incomplete` 不毁整份报告）。
- 每组件记录：occurrence/parent 路径（组件特征 id 序列）、depth、`ProFeatureStatusGet` 抑制判定（含族表/简化表示/程序抑制）、`ProAsmcompIsPackaged`、`ProAsmcompMdlGet`（失败标记 `resolved=false` 保留节点）、`observe_session_model` 同构字段（name/type/origin/has_saved_origin/modified/session_model_id/is_current，未知为 null+query_codes）、约束快照（`ProAsmcompConstraintsWithComppathGet`+type/offset/朝向/asm/comp 引用，引用经 `ProSelectionAsmcomppathGet`/`ProSelectionModelitemGet` 尽力解析，原始码保留）、`component_to_assembly_transform`（解算值）4×4 到父级 + 行向量累积到根（`p' = p × M`，平移末行，毫米）。
- `src/creo_mechdog/session_assembly.py`：首采持 Toolkit 通道锁（忙即拒绝）、快照存 job 目录、10 分钟冻结分页（32 KiB 预算、fingerprint/selection/name/offset 防篡改、过期拒绝）；注册 `creo_inspect_session_assembly`（READ）并登记 `capabilities.py` `session_assembly` 家族。
- 实施中修复的崩溃根因：`ProMdlMdlnameGet` 输出缓冲必须为 `ProMdlName`（80 宽字符），误用 `ProName`（32）造成栈溢出（0xC0000409）——`ProSelectionAsmcomppathGet` 结果解析处；`ProAsmcompConstraintsWithComppathGet` 传 NULL comppath 在 Creo 12 实机崩溃，改为始终构造 owner comppath。

## 验证

- 单元：`tests/unit/test_session_assembly.py` 5 项（树序/occurrence/重复实例分别记录、名称与 limit 校验、cursor 冻结与五类非法拒绝、32 KiB 分页切分、busy 与 native 失败不建 job）；工具数契约断言 90→91；全量 544 项与 `tools/dev_check.py` 通过（native 格式化后零回归）。
- 本机 Windows / Creo 12.4.0.0 / E 盘 dev 服务（stdio 直连，全程公开 MCP 工具）：
  - **托管链**：新建 f45b_p1（40×30×5 板）/f45b_p2（φ12 圆柱）/f45b_top（p1 原位 fixed + p1 平移 [50,0,0] + p2 平移 [10,10,5]）并保存；
  - **外部装配主线**：结束挂起会话（xtop 无窗口且 Toolkit -11，核对全部模型已保存、无活动作业/锁后按 0.3.7/0.4.7 先例重启）→ `creo_open_file` 打开 `f45b_top.asm.3`（8 模型载入、`opened_and_displayed`）→ `creo_inspect_session_assembly("f45b_top")` 返回 3 组件 complete=true：约束快照各 1 条 `fix`（offset 0、orientation none、asm 引用 comppath code 0/item -2、comp 引用 -4 如实标记），`transform_to_parent` 末行与放置平移**逐位一致**（[0,0,0]/[50,0,0]/[10,10,5]），`to_root=to_parent`（顶层）；根信息含 origin/loaded 状态，`session_model_id` 出现大数段（与外部观察一致，仅瞬态提示）。
  - **分页**：limit=1 三页 [40][43][46] 无重无漏、末页 `next_cursor=null`；跨页只读同一快照。
  - **拒绝**：不存在名称 → `SESSION_ASSEMBLY_NOT_FOUND`（提示经 `creo_list_session_models` 选择）；空装配 total=0 正常返回。
  - **只读核对**：多次 inspect 后会话枚举不变、无受管 revision 创建（job `model_id=null`）。
- 原始输出：`build/feat045_full.json`（完整快照）、`build/feat045_missing_real.json`、运行日志 `build/feat045_run*.log`（本机生成物，不入库）。

## 未验证（如实保留）

- **嵌套子装配**（depth≥1 递归与 to_root 累积）：本机无构造手段——`assemble_component` 不支持嵌套装配插入（既有边界），本机亦无嵌套样本文件；递归与累积逻辑由单测合成数据覆盖，外部环境（如 ASM_MX 含子装配）复测后定论。
- **重复实例**（同一模型两个 occurrence）：受管装配插入即复制快照（c_<sha>_<n>），不产生同名实例；本机无外部重复实例样本。native 对重复 visit 天然分别记录，单测合成数据覆盖（同 component_id 两条目）。
- **抑制组件**（suppressed=true 实机触发）：无 MCP 抑制工具，GUI 手段不可用；`ProFeatureStatusGet` 判定逻辑由代码路径保证。
- **缺件**（resolved=false 实机触发）：两个历史 fixture（asm_missing/asm2_missing）组件经 Creo 搜索路径解析成功未触发；需受控隔离目录的外部 fixture。native 路径（`ProAsmcompMdlGet` 失败保留节点）与单测覆盖。
- 外部 Win10/Creo 10 环境复核随 WorkBuddy/外部反馈闭环。

## 后续路线（单列，不随本轮实施）

矩阵放置承接（assemble_component 按提取 transform 摆放，含 4×4→XYZ mm+Euler 度换算口径与精度实测）、受限重建（组件选择/收养流程）、装配整体收养（依赖物化+引用重映射+装配 reconcile，前置注册表治理已完成）；"托管副本回存原盘"显式动作与嵌套子装配装配、mate/insert/csys 全谱系为更后批次。
