# FEAT-008/012/048 第二批：WorkBuddy MCP 黑盒验收提示词

请只通过已连接的 MCP 工具验收；不读取、分析或修改源码，不运行本地脚本/单元/开发检查，不检查本机配置或 Git。无法从公开接口确认的身份信息写“无法确认”。本文件是待执行场景，不是通过记录。

测试发起者先确认会话可操作，并确认连接器指向本批受测服务、工具清单含
`creo_adopt_file`（能力边界里 maximum_paths=20）。只在独立夹具上操作：自建
零件/装配或操作者明确提供的只读源件；不要触碰历史受保护模型。单一
Toolkit 通道 busy 立即拒绝、不排队；已受理作业只轮询，不重新提交。

1. 用公开环境/会话/能力接口记录运行身份、服务版本、工具数与
   `source_changed_since_startup=false`。矩阵放置与收养能力声明以
   `creo_capabilities` 为准；未部署或仍为旧连接器则报告阻断，不猜测源码已生效。

2. **矩阵放置与回读（FEAT-012/BUG-045）**：`creo_execute_plan` 自建毫米长方体
   源件（如 40×30×6），记录 model_id/revision。新建装配后交替使用
   `creo_assemble_component` 与 execute_plan 的 `assemble_component` 插入同一
   源件，分别用 `rotation` Euler 与互斥的嵌套 3×3 `rotation_matrix`（含组合
   旋转，如 `[[0,1,0],[-1,0,0],[0,0,1]]` 与 `[[1,0,0],[0,-1,0],[0,0,-1]]`），
   平移独立毫米。每次只轮询作业到终态，预期 succeeded、
   `saved_file_reloaded_and_verified=true`、revision+1。用
   `creo_list_components` 回读每个组件 4×4 矩阵：左上 3×3 与请求矩阵逐元素
   一致（1e-6 内），末行前三项等于平移；用实际回读矩阵验证三个基向量方向与
   一个已知点映射（局部点 p 映到 p·R+t）。非法输入（矩阵与 Euler 同传、平铺
   九元素、含字符串/布尔、NaN、反射或缩放矩阵、超 1e-6 非正交）预期在入口拒绝、
   不产生作业或模型变化。之后用 `creo_component_placement` 更新位姿并回读，
   Euler 与矩阵两种写法结果一致。

3. **一次真实普通失败后的回滚**：在装配提交一个引用不存在组件的作业（如
   `remove_component` 传未知标签），预期作业 failed、`rollback_succeeded=true`，
   装配 revision 与 `creo_list_components` 快照不变；作业 manifest 的
   `component_changes.status` 为 `rolled_back`，其中只列请求意图，不得有任何
   变更被报为已生效。unknown 保护不注入、不测；遇到自然 unknown 即停并报告。

4. **批量收养（FEAT-048）**：操作者提供 1–19 个独立外部零件路径（可含不健康/
   非毫米/带依赖源件各一，须事先明确）。先记录当前窗口模型（`creo_list_session_models`
   中 `is_current`）。`creo_adopt_file(mode="inspect")`：每件独立结果，重复来源报
   `duplicate_source`，源件选择身份（路径+哈希）逐件记录；当前窗口不变。再
   `mode="apply"`（同一有序路径+evidence_token+幂等键），轮询父作业到终态：
   预期普通拒绝件不撤销成功件（`partial_result`），成功件 revision=1、
   `saved_file_reloaded_and_verified=true`、结果含 `source_unchanged=true` 与
   `window_unchanged=true`；成功后当前窗口仍不变，源文件字节如公开接口无独立
   证据则记未验证。同键回放返回同一父作业与相同 items。通道忙时可由真实并发
   观察 busy 拒绝（含 blocking_* 与 accepted=false）；做不到真实并发则写并发未验证。

5. **官方重建管线（FEAT-008）**：对一个本会话装配（自建或操作者提供的只读
   原装配）执行 `creo_inspect_session_assembly` 只读快照，记录 occurrence 路径、
   归一化毫米 4×4 变换与约束快照；再按路径收养其源件、新建托管装配、用
   **一个** `creo_execute_plan` 作业插入多个组件（重复 occurrence 复用同一
   `source_model_id`、不同 label）。作业预期 succeeded、revision 只 +1、
   `component_changes.status=committed` 且每个操作一条 `added`（含真实
   feature_id、source_model_id、source_revision），`preview_file` 存在；重复
   occurrence 的位姿按各自 label 独立回读正确。`creo_list_components` 的
   固定约束同时给出数字 `type` 与 `type_name="fix"`（数字以本机返回为准，
   不预设枚举含义）；两个重复 occurrence 各自独立条目。

6. **source_snapshot 语义**：编辑源件（如对源件追加一个特征作业）使其
   revision+1 后，重建装配的 `creo_list_components` 应保持不变（组件数、位姿、
   组件副本名均不变；装配 revision 不变），证明已插入组件是旧快照。然后
   `remove_component`+重新 `assemble_component`（原 label、原位姿）：预期作业
   succeeded，`component_changes` 各列一条 `removed` 与 `added`；重新插入的
   组件反映源件当前 revision（副本名变化、source_revision 为新值）。约束与
   引用需重新核对；`component_placement`/`regenerate`/`save` 不是源件更新手段，
   不得据此声称源件已更新。嵌套装配（以装配为源）预期被拒绝。

报告逐项记录工具、完整输入、job_id/model_id、终态、revision、几何/矩阵数值、
保存重载、回滚与原始错误。区分通过、失败、阻断、未验证；只有真实实施了并发
调用才能报告并发通过。内部文件占用、哈希实现、临时文件清理、锁文件处置不
纳入黑盒结论；本机 Creo 12.4 结果不外推其他版本。
