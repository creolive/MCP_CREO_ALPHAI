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

## 约束快照回放（DEV-047 T09 / FEAT-049）

`creo_inspect_session_assembly` 的快照 schema 3 为每个约束补充双侧引用身份
（`asm_reference`/`comp_reference` 的 `owner_scope`、`occurrence_label`、
`item_type`/`item_id`）、双侧方向（`asm_side`/`comp_side`）、偏移单位
（`offset_unit`、毫米口径 `offset_mm`）和 `replayable`/`reason`。schema 2 及更早
的快照没有这些证据，回放工具明确拒绝，不会静默升级。

只读规划工具：

```text
creo_plan_assembly_rebuild(snapshot_id, component_mapping, reference_mapping)
```

- `snapshot_id` 来自 `creo_inspect_session_assembly`，必须 schema 3、完整
  （`complete=true`、未截断/未限深）且在 600 秒内。十分钟只是规划证据窗口，
  不是长期写入授权；计划本身绑定源件 revision/摘要，提交时重新核验。
- `component_mapping`：每个 occurrence 一条
  `{occurrence: occurrence_label 或 occurrence_path, label: 新目标组件标签,
  source_model_id: 受管 part/sheetmetal}`；全部 occurrence 必须唯一覆盖，重复的
  occurrence label 用 `occurrence_path` 区分。
- `reference_mapping`：每个源引用一条
  `{source: {component: 同层组件 occurrence_label 或 null(装配根), item_type,
  item_id, side?}, target: execute_plan 引用对象, target_component?:
  装配侧目标组件标签, target_side?: yellow|red|none}`。引用身份必须显式给出，
  不凭 item_id 跨模型推断；同一源引用多条匹配视为歧义拒绝。
- 输出 `operations` 先插入全部组件（fixed/default 按快照真实语义单列；带约束
  组件先以 fixed 插入，再执行 `component_constraints`），随后按快照顺序设置
  `mate`/`align`/`mate_offset`/`align_offset`/`insert`/`csys`；偏移统一换算为
  毫米。装配侧同层兄弟引用通过约束内的 `assembly_component` 明确表达。
- 每个 `assemble_component` 带 `rebuild_binding`（源 model_id、revision、文件
  sha256）。`creo_execute_plan` 受理时在通道锁内重读 registry 与文件字节，原生
  执行器加载源件前再核对 revision。源件变化、过期/旧快照、缺映射、未知类型、
  嵌套引用和超过 200 操作的规划都明确拒绝，不拆成多个事务；执行失败仍由既有
  单作业事务整批回滚。
- 规划本身不加载、不收养、不修改原装配或源件，不创建作业/revision，不连接
  Toolkit，也不产生 `operation_results`；未覆盖 FEAT-050 公共比对、嵌套装配和
  新约束类型。

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

1. 一个作业内 `remove_component` 后重新 `assemble_component`：按源件**当前**
   revision 取新快照。重新 assemble 必须使用**新的唯一 label**——入口拒绝
   与目标既有别名重复的 assemble label，即使同一作业先 remove 了它（实机
   `assembly_pipeline_live_20261025T162553Z` step 9e 以原 label 复用同一计划
   被入口拒绝、未产生作业）；位姿沿用原快照位姿、同一 `source_model_id`，
   引用与约束需重新核对。若必须保留原 label，则拆成两个作业：先
   remove（revision+1），再 assemble（revision+1），各自独立提交，第二步
   失败不会撤销第一步；或
2. 新建装配整体重建。

实测要点：`creo_list_components` 返回的是**最近一次已验证检查**的缓存快照，
不能当作实时几何证明。要证明“源件编辑后装配仍是旧快照”，先对装配提交一次
`creo_execute_plan`（仅 `{"op":"regenerate"}`），按 revision+1 契约取得保存
重载后的新原生数据（`creo_inspect_model` 的体积/位姿）；此时体积仍等于编辑
前值即证明组件是旧快照。之后再 `remove_component` + 重新
`assemble_component`（**新的唯一 label**，见上），保存重载后体积/包围盒反映
新源件。

## 组件变更摘要

含组件操作的作业在 manifest 顶层增加有界 `component_changes`
（`creo_get_job` 的 compact 与 full 都包含；preview 仍在
`result.preview_file`）。状态按原生证据区分，不编造回滚：

- `committed`：作业成功，清单是作业前后**已验证状态的净变更**——前后集合
  只含**真实组件**：受管 label 仅在原生别名记录 `op="assemble_component"`
  或其 `feature_id` 属于已验证检查 `components` 的真实组件 id 时才计入；
  `datum_plane`/`sketch`/`extrude` 等通用别名绝不列入（混合作业新增 datum
  不会误报为组件变更）；无别名的原生组件以真实检查 `feature_id` 列入
  （`label` 为 `null`），绝不编造 id。组件按真实 `feature_id` 对比。仅作业后存在的 label 为 `added`（含结果别名里的
  新 `feature_id`、`source_model_id`/`source_revision`）；仅作业前存在的
  label 为 `removed`（用作业前别名的旧 `feature_id`）；两侧同 label 且同
  `feature_id` 才比较移动与约束（`moved` 含 `from`/`to` 查询矩阵，仅在
  查询到的变换确实不同时报告；约束比较剔除仅展示的 `type_name` 符号，
  与原生 `constraint_compare.h` 一致——旧数字-only 检查点不因新增可读
  符号误报 `constraints_changed`，数字/refs/offset 等真实字段仍全量对比）；两侧同 label 但 `feature_id` 不同视为重插，
  报旧 id `removed` + 新 id `added`，绝不从最终别名为已移除中间组件编造
  身份。同作业内先 add 再 move 最终只有 `added`；先 add 再 remove 无净组件
  变更；连续 move 只报一次从初态到终态的 `moved`。
- `rolled_back`：**仅当**原生结果确认 `rollback_succeeded=true`（保存检查点
  已恢复并验证）时才出现；只列请求意图，**不声称任何变更已生效**。
- `no_effect`：作业未产生任何变更——入口拒绝（通道 busy、worker 未启动）或
  原生预检拒绝（`model_unchanged=true`，副作用前失败）；不需要也未声称回滚。
- `unknown_outcome`：结果未确认，或作业在原生执行后失败但回滚未确证；清单
  为空并指向保留的保护。
- 摘要本身是辅助路径：只为摘要的别名/检查 sidecar 读取与计算**仅对含组件
  操作的请求**发生（普通零件作业完全不读这些 sidecar），其失败只把摘要降级
  为 `unavailable`（附错误），作业的已确认终态（上方 `status`）仍然权威，
  摘要异常不会改变终态；缺少已验证结果别名时同样降级为 `unavailable`，
  不猜测净变更。

入口当前拒绝在同一计划内复用既有 assemble label（即使先 remove），故经入口
提交的净重插状态只可能来自既有别名数据本身；无论何种来源，摘要按下述身份
规则报告：同一净状态下对同一 label 的旧 `remove_component` 与新
`assemble_component`，`removed` 记录的是**原** feature_id（来自作业前别名快照），`added` 记录的是
结果别名里的**新** feature_id，两者不会被混用。值全部来自原生操作结果、受管
别名与已验证检查；服务不在 Python 侧模拟几何。批量装配复用每个作业现有的
`preview.jpg`，不另设同义“批量装配工具”。

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
  （单作业多组件、预览/摘要/符号名、快照语义与再生成；全部动态请求经
  真实 `normalize_model_name`/`validate_operations` 离线校验，见
  `tests/unit/test_assembly_pipeline_requests.py`）。
- guard 实机入口（PowerShell 单行，可直接运行；参数是 `--run`，不是 `--`）：

  ```powershell
  .\.venv\Scripts\python.exe tools\guarded_live_run.py --guard-root E:\Projects\MCP_CREO_MechDog --run ".venv\Scripts\python.exe tools\test_assembly_matrix.py --session-health-verified" --run ".venv\Scripts\python.exe tools\test_assembly_pipeline.py --session-health-verified"
  ```

  先持主工作树**真实字节锁**再顺序运行 md050 子进程；锁忙即停止（exit 2）。
  子进程退出不等于作业终态：每个子进程结束后入口只轮询本轮受理作业
  （每轮重新发现晚到作业）到终态，并且只在三项独立证据齐全时才释放真实
  锁——全部受理作业终态 + 无 md050 原生 worker 存活（按
  `native_checkpoint.json` 的 `native_pid` 进程身份与
  `build\creo_worker.exe` 镜像路径只读扫描双重确认，空闲锁本身不算证据）
  + md050 通道字节锁探针空闲。受理作业出现 `unknown_outcome` 且 worker
  已停、通道空闲时：释放主锁但本入口返回失败（exit 3）、禁止后续子进程、
  md050 unknown 保护原样保留——unknown 不等于必须永远持锁。若作业仍
  pending 或通道/进程状态不可证实，`--settle-timeout` 只写报告报警，入口
  **继续存活并持有真实锁**直至可证实；操作员中断（Ctrl+C）是唯一的提前
  退出，进程退出即放锁，不做任何安全声明。本入口不结束 Creo、不杀
  worker、不清保护、不重连、不重提。
  不要把“子进程退出前作业必终态”当作已验证保证——这正是本入口要确认的。
- 每个驱动输出带时间戳的唯一报告目录。WorkBuddy 只通过公开 MCP 黑盒验收，
  场景见 [WORKBUDDY_FEAT008_PIPELINE.md](WORKBUDDY_FEAT008_PIPELINE.md)。

## 开发者实机验收状态（2026-10-26）

矩阵、批量收养与管线三驱动已于 2026-10-25/26 在本机 Creo 12.4 真实会话通过
开发者 MCP 实机验收（非 WorkBuddy）：矩阵 38 父作业（37 成功 + 1 故意普通
失败成功回滚）、4 次真实改变位姿 rev 36→40；收养两批 2+1 成功、3+2 拒绝、
0 unknown；最终管线 10 父作业全成功（快照刷新新唯一 label，12384→12984、
装配 rev 3→4）。raw 报告关键值与文件 SHA256 见
[development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md](development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md)。
WorkBuddy 黑盒经用户 2026-10-26 决定取消本批（未执行、不记通过）；上述配套随
0.6.0 交付，见[发布记录](validation/RELEASE-0.6.0.md)；并发、unknown 自然分支、
其他 Creo 版本未实机。
