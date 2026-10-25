# 装配重建官方管线（0.5.0 反馈第二批）

适用范围：单层装配，健康、毫米单位、无外部依赖的独立零件/钣金源件。嵌套
子装配与显式源件更新未开放（见 [FEAT-012](work-items/FEAT-012.md)）。

完整可调用示例：[examples/assembly_rebuild_pipeline.json](../examples/assembly_rebuild_pipeline.json)
（逐步工具调用）与 [examples/assembly_multicomponent_plan.json](../examples/assembly_multicomponent_plan.json)
（单作业批量插入）。示例参数与真实 MCP schema 一致并由单元测试锁定
（`tests/unit/test_assembly_examples.py`）。

## 管线步骤

1. **检查原装配**：`creo_inspect_session_assembly(name=...)` 只读快照，返回树序
   occurrence、归一化毫米行向量 4×4 变换（`transform_to_parent` /
   `transform_to_root`，平移在末行）、原始矩阵（`*_raw`，源单位）、逐节点单位与
   约束快照。失败分支：装配不在会话或快照不完整时不产生任何写入，修好会话后重查。
2. **按路径收养源件（inspect）**：`creo_adopt_file(file_path=[...], mode="inspect")`
   逐件选择、哈希与原生健康/单位/依赖准入；不改变当前窗口，源文件只读。
   每件独立结果，普通拒绝不影响其余件。见 [FILE_ADOPTION.md](FILE_ADOPTION.md)。
3. **按路径收养源件（apply）**：同一文件列表 + `evidence_token` +
   `idempotency_key` 提交一个父作业，单通道内顺序独立提交；普通失败继续，
   unknown 停止剩余并保留保护；同键回放只读返回同一父作业。
4. **新建托管装配**：`creo_new_assembly(model_name=...)`。
5. **单作业插入多个组件**：`creo_execute_plan` 在一个作业内顺序执行多个
   `assemble_component`（也可含 `component_placement` / `remove_component`），
   末尾统一保存、擦除、重载并验证。重复 occurrence 复用同一收养的
   `source_model_id`，但每个组件 label 必须独立。通道忙立即拒绝，不排队。
6. **回读验证**：轮询 `creo_get_job` 到终态（只轮询、不重新提交），确认
   `status=succeeded`、`saved_file_reloaded_and_verified=true`、`revision+1`；
   再用 `creo_list_components` 核对组件集、位姿与约束。

## 位姿与矩阵约定

- `translation` 为 XYZ 毫米；`rotation` 为 XYZ Euler 度（先 X 后 Y 再 Z）；
  或互斥的嵌套 3×3 `rotation_matrix`：行向量、局部到父级，
  `p_parent_mm = p_local_mm * rotation_matrix + translation_mm`。
- 矩阵只接受有限实数，行向量正交性与行列式 +1 容差 `1e-6`；拒绝反射、缩放与
  超容差输入，容差内按原值使用，**不自动转置、不修正**。与显式 `rotation`
  （含 `[0,0,0]`）互斥。
- 从 `creo_inspect_session_assembly` 回放位姿时，使用归一化毫米结果
  （3×3 取 `transform_to_parent` 的左上块，`translation` 取末行前三项）。
  **不要**把 `*_raw` 矩阵、单位未知或带单位缩放的矩阵喂回；原变换未知或
  不支持时停下重新检查，不要假装完整重建。

## source_snapshot 语义

插入的组件是源件在该源 revision 的**快照**（原生按作业复制为
`c_<job>_<index>`）。编辑源件**不会**自动更新已插入组件；`component_placement`、
`regenerate`、`save` 都不是源件更新手段。当前支持的重新生成方式：

1. `remove_component` 后重新 `assemble_component`：按源件**当前** revision 取新
   快照，label 与位姿需重新指定，引用与约束需重新核对；或
2. 新建装配整体重建。

## 组件变更摘要

含组件操作的作业在 manifest 上增加有界 `component_changes`：

- `committed`：作业成功，清单给出真实 `feature_id`（`added` 另含
  `source_model_id`/`source_revision`；`moved` 含 `from`/`to` 查询矩阵）。
- `rolled_back`：作业失败回滚，只列请求意图，**不声称任何变更已生效**。
- `unknown_outcome`：结果未确认，清单为空并指向保留的保护。

值全部来自原生操作结果、受管别名与已验证检查；服务不在 Python 侧模拟几何。
批量装配复用每个作业现有的 `preview.jpg`，不另设同义“批量装配工具”。

## list_components 约束符号名

`creo_list_components` 的 `constraints[]` 保留数字 `type`（本机 SDK
`ProAsmcompConstrType` 查询码），新增 `type_name` 可读符号（如数字 `13` →
`"fix"`），符号与 `creo_inspect_session_assembly` 共用同一映射；未识别的码
保留数字并将 `type_name` 标为 `"unknown"`，不猜测含义。

## 开发者入口与实机验收

- 矩阵实机驱动：`tools/test_assembly_matrix.py --session-health-verified`
  （实际放置+查询、三基向量与已知点、Euler 兼容、revision、非法拒绝、真实
  普通失败后回滚、保存重载）。
- 批量收养实机驱动：`tools/test_file_adoption.py <sources...>`（窗口/源字节
  不变、来源 provenance、健康/单位/依赖拒绝、重复/失败继续、幂等回放、
  revision/保存重载）。
- 管线实机驱动：`tools/test_assembly_pipeline.py --session-health-verified`
  （单作业多组件、预览/摘要/符号名、快照语义与再生成）。
- guard 实机入口：`tools/guarded_live_run.py --guard-root E:\Projects\MCP_CREO_MechDog -- <command...>`
  先持主工作树通道锁再顺序运行 md050 子进程；锁忙即停止。
- 每个驱动输出带时间戳的唯一报告目录。WorkBuddy 只通过公开 MCP 黑盒验收，
  场景见 [WORKBUDDY_FEAT008_PIPELINE.md](WORKBUDDY_FEAT008_PIPELINE.md)。
