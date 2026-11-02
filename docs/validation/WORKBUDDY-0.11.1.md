# 0.11.1 WorkBuddy 黑盒验收提示词（待执行）

按项目 WorkBuddy 约定执行：仅通过已连接的 MCP 工具对最终用户可见行为做黑盒验收，不查看/分析源码，不执行本地 Python 脚本、单元测试或开发检查，不读取本机配置、仓库状态或 Git。环境、会话、可见工具与服务版本用 MCP 公开接口确认；接口未提供的构建身份记"无法确认"。开发者侧实机证据见 [Q15 三轮实机记录](DEV-053-Q15-live-2026-11-01.md)，两者分别记录、互不替代。

前置条件（本提示词在下列条件全部满足后才开始执行）：MCP 服务已连接且指向待验收的 0.11.1 候选服务；Creo 会话可用（`creo_session_status` 的 `connected=true`、`toolkit_code=0`）；操作者已确认 Creo 界面可操作、无阻塞对话框；会话不可用时本轮全部记"未执行"，不要尝试启动或重启 Creo，也不要结束会话进程。文件占用注入、重试次数/预算、锁文件与临时文件处置等内部机制不纳入本轮结论。

---

## 提示词

你在做 MCP Creo 服务 0.11.1 候选版的黑盒验收。只调用已连接的 MCP 工具完成下列场景，逐项记录：工具名与完整输入、job_id/model_id、isError 与完整 message、终态 status 与 message、作业明细中的指定字段、操作前后 volume_mm3、revision、保存重载标志。

通用规则：所有修改提交后只轮询 `creo_get_job`（detail=compact）直到终态，不重复提交同一作业；返回 busy 按回执指引处理，不改写输入重投；出现 unknown_outcome 立即停止新写入并如实报告，不清保护、不重放。除场景 1 明确复用同名外，每个场景使用全新隔离模型名（建议 `wb0111_<场景>_<随机后缀>`），不复用历史 model_id，不触碰历史失败模型。

### 0. 环境与服务身份确认

1. `creo_session_status`：记录 connected、connection_state、toolkit_code、release。
2. `creo_capabilities`（detail=compact）：记录 name、version、server_version、tool_count（预期 95）、`scheduling.admission`、`scheduling.native_channels`、`scheduling.owner_fields`（预期含 blocking_job_id / blocking_model_id / blocking_operation）。
3. 列出可见工具并确认存在：`creo_execute_plan`、`creo_new_part`、`creo_inspect_model`、`creo_get_job`、`creo_list_jobs`、`creo_list_session_models`、`creo_capabilities`、`creo_recolor_assembly`。接口未提供的身份字段记"无法确认"。

### 1. 失败模型清理与同名重试（新建模作业失败后，终态带 failed_model_cleanup 回执）

用**一次** `creo_execute_plan`（省略 model_id，model_name=wb0111_cleanup_<随机后缀>）提交一个会在模型已建立后失败的计划。先造几何再触发去料为零的失败：

```json
[
  {"op": "sketch", "label": "plate_sk", "plane": "XY",
   "entities": [{"type": "rectangle", "name": "plate_r", "min": [-30, -20], "max": [30, 20]}]},
  {"op": "extrude", "label": "plate_ex", "sketch": "plate_sk", "depth": 10},
  {"op": "sketch", "label": "out_sk", "plane": "XY",
   "entities": [{"type": "circle", "name": "out_c", "center": [100, 100], "radius": 5}]},
  {"op": "extrude", "label": "out_ex", "sketch": "out_sk", "mode": "cut", "depth": 10}
]
```

1. 轮询该 job 到终态。预期：status=failed；message 指向"去料为零/未切除任何材料"一类原因（原文字面记录）；终态 result 内有 `failed_model_cleanup`，记录其**全部五个字段**：attempted、status、reason、erase_code、absence_verified。目标形态是 status=erased、reason=cleaned、erase_code=0、absence_verified=true；但清理出于安全理由保留对象时，status 会是 skipped 一类、reason 给出具体原因（如窗口已开、用户已改动、创建后已被保存、无法确认缺失），此时 absence_verified 预期为 false——按实际值如实记录，不要改写，也不要把"被安全跳过"当成已清理。同时记录 result.rollback_status（预期 not_attempted：新模型作业没有可回滚的保存检查点）。
2. 紧接着用**同一模型名**再提交一次 `creo_execute_plan`（省略 model_id，model_name 与上一步完全相同），operations 只含上面的 plate_sk 与 plate_ex 两步。预期：作业 succeeded、revision=1、`saved_file_reloaded_and_verified=true`、volume_mm3=24000（60×40×10 mm³）；不再出现"名称已存在"一类拒绝。此步成功即证明失败遗留对象未阻塞同名重建。
3. 记录两次作业的 job_id/model_id（同名重建应是新的 model_id）与终态。

### 2. 已保存模型的失败回滚与 rollback_status（区别于场景 1）

1. `creo_execute_plan`（省略 model_id，model_name=wb0111_saved_<随机后缀>）提交 XY 矩形 min=[-30,-20] max=[30,20] + extrude depth=10。预期 succeeded、revision=1、volume_mm3=24000、保存重载 true。记录 model_id。
2. 同模型再提交一次（带 model_id 与 expected_revision=1）一个必然失败的计划：XY 圆草图 center=[100,100] radius=5 + `extrude` mode=cut depth=10。预期：作业 failed；message 指向"去料为零"一类原因；result.rollback_succeeded=true；result.rollback_status=succeeded（保存检查点已恢复）；result.failed_model_cleanup 的 reason 预期 not_new_model_job（本次不是新模型作业）；失败前后 `creo_inspect_model` 的 volume_mm3 与 revision 均不变。
3. 随后对同一模型提交一次有效追加（带 model_id 与当前 revision）：XY 圆草图 center=[0,0] radius=5 + `extrude` mode=cut depth=10。预期 succeeded、revision=2、volume_mm3 减少 5²×π×10≈785.4 mm³（记录实测值）、保存重载 true。

### 3. 三点定面与斜面草图（datum_points + datum_plane through_points → 斜面 sketch → extrude）

先准备一个空零件：`creo_new_part`（model_name=wb0111_tilt_<随机后缀>），轮询其 job 到终态，再用 `creo_inspect_model` 读出该零件的 model_id 与当前 revision（预期 revision=1、status=ready）。随后在**同一个** `creo_execute_plan` 内提交下面这份计划（带 model_id 与刚读到的 expected_revision）：

```json
[
  {"op": "datum_points", "label": "dpa0", "points": [{"name": "pa", "position": [-95.191114, 40.0, -88.395141]}]},
  {"op": "datum_points", "label": "dpb0", "points": [{"name": "pb", "position": [95.191114, 40.0, 88.395141]}]},
  {"op": "datum_points", "label": "dpd0", "points": [{"name": "pd", "position": [94.701973, 50.416667, 89.27114]}]},
  {"op": "datum_plane", "label": "pl00a",
   "reference": {"kind": "through_points", "points": ["dpa0", "dpb0", "dpd0"]}},
  {"op": "sketch", "label": "smk", "dimensioning": "coordinates",
   "plane": {"type": "frame", "origin": [-95.191114, 40.0, -88.395141],
             "reference": {"kind": "datum_feature", "label": "pl00a"},
             "u_axis": [190.382228, 0.0, 0.0]},
   "entities": [{"type": "polyline", "name": "tri",
                 "points": [[0, 0], [190.382228, 22.394433], [189.893088, 32.838154]],
                 "closed": true}]},
  {"op": "extrude", "label": "smk_ex", "sketch": "smk",
   "depth": 9.87008714331235, "direction": "symmetric", "new_body": true}
]
```

1. 预期：作业 succeeded；保存重载 `saved_file_reloaded_and_verified=true`；revision 相对提交前 +1（即预期为 2）。
2. 体积：用 `creo_inspect_model` 读 volume_mm3，与解析值比较——草图三角形在该斜面局部 (u,v) 坐标下的面积为 999.6264427740043 mm²，深度 9.87008714331235 mm，故期望体积 **9866.400100938760 mm³**；相对偏差预期 ≤1e-6。记录实测值与相对偏差。
3. 记录斜面草图的定位证据：作业明细中标号为 smk 的记录里应有 origin、normal、u_axis、v_axis 与 section_location；记录这些字段的实际值。normal 的方向预期与三点定义的平面法向一致（符号不作要求）。
4. 负例一（近共线）：把三个 datum_points 的位置改为 (0,0,0)、(1,0,0)、(2,0,0)，其余不变重新提交。预期被拒绝，message 出现"接近共线/无法确定唯一平面"一类原因；不得建成模型。此负例在原生执行阶段才判定，计划本身可被受理，因此可能表现为"作业 failed"而非入口拒绝——两种形态都算被拒绝，只要原因可读且没有建成几何。
5. 负例二（重复点）：三个位置改为 (0,0,0)、(1,0,0)、(1,0,0)。预期被拒绝，message 出现"重复点"一类原因。
6. 负例三（错误引用形式）：把 datum_plane 的 reference 换成 `{"kind": "datum_point_feature", "label": "dpa0"}`。预期在受理前被拒绝，message 指出应改用 `{kind:"through_points", points:[...]}` 形式。

### 4. 草图显式容差 geometry_tolerance_mm

1. 在一个新零件上提交一次普通 XY 草图（矩形 min=[-30,-20] max=[30,20]），dimensioning=coordinates，并带 `geometry_tolerance_mm=0.05`。预期作业 succeeded；作业明细中标号为该草图的记录里应能看到容差相关字段（记录实际字段名与值，例如 geometry_deviation 的 warning_threshold_mm / max_deviation_mm / exceeds_warning / enforced / tolerance_source）。
2. 省略容差的默认行为：再提交两次同类草图——一次 dimensioning=coordinates、一次 dimensioning=autodim——都不带 geometry_tolerance_mm。预期前者生效阈值为 1e-05 mm（coordinates 模式下超出即失败），后者为 1e-03 mm（autodim 模式下只告警不失败）；两次的实际阈值与 enforced / tolerance_source 取值逐项记录。
3. 负例：分别在 `creo_execute_plan` 的草图操作上提交 `geometry_tolerance_mm=0`、`-1`、`"0.01"`（字符串）各一次。预期三次均在受理前被拒绝（isError=true），message 指出容差必须是有限正数；不产生 job、不产生模型。记录每次的完整 message 原文。
4. 负例边界：同一组非法值若改用独立草图工具提交，字符串形式可能被转换层接受——若出现这种情况，如实记录该入口的实际行为，并在结论中注明"拒绝只发生在计划入口"，不要把两个入口混为一谈。

### 5. Toolkit 忙时立即拒绝（busy 回执）

本节需要**真实并发**：必须让两个提交在时间上重叠，才能对 busy 回执下结论。只有一个客户端串行提交时，即使被拒绝也只说明"当时通道被占"，不能据此判定并发语义；无法制造重叠时本节记"未验证"。

1. 准备一个足以占用通道数秒的长作业（例如同一计划内连续 25 组"圆草图 + 拉伸"，各组圆心取不同位置）。提交它并立刻开始下一步。
2. 在长作业仍处于 running（`creo_get_job` 返回 status=running 或 stage=executing_feature_plan）时，从**另一个客户端或并行派发**提交第二个作业（不同模型名）。预期第二个调用立即返回错误：isError=true；JSON 与 structuredContent 一致；status="busy"、code="toolkit_busy"、accepted=false；blocking_job_id 指向第一个作业、blocking_model_id 与 blocking_operation 有值；含 retry_after_seconds 与 retry_guidance（提示轮询占位作业、重新读取 revision、不要重投已受理作业）。第二个请求不创建作业、不创建模型。
3. 背靠背：第一个提交的返回一到就立即再提交第二个（不同模型名）。预期同样是 busy 拒绝，不得出现两个都被接受后串行排队执行的情况。记录两次提交的时刻与两个回执原文。
4. 记录第一个作业最终终态（预期正常到 succeeded，revision 与保存重载正常）。若观察到"两个都被接受"，如实记录——这与对外声明的"忙时立即拒绝、不排队"不符。

### 6. 作业阶段上报与结果分页

1. 用场景 5 的长作业执行期间，多次 `creo_get_job`（detail=compact）轮询，记录每个观测到的 status 与 stage 值及其先后顺序。预期 stage 随执行推进而变化（例如出现 executing_feature_plan，随后 connect、sketch 类、save_and_reload、display_preview、result_delivery_complete，终态为 verified）；记录实际观测到的完整取值序列，不预设必须逐字命中某一序列。
2. 对特征数较多的模型读详情：`creo_get_job`（detail=full，section=operations_result）与 `creo_inspect_model`（detail=full，section=features）。预期分页字段 complete、next_cursor、total、returned_count 出现且自洽；翻页取回的操作记录条数与 total 一致、无重复无遗漏。记录每页的 total 与 returned_count。
3. 结果体量：若某个返回被折叠，观察 total/truncated/sample 一类的有界摘要字段并记录其数值；超大单条记录应表现为 oversize 标记而非被静默截断。客户端无法直接观测响应字节数时，"响应体 ≤32 KiB"记"无法确认"，不要用"返回看起来不大"代替。

### 7. 预览与上色不变项回归

1. 预览：执行场景 1/3 中任一成功建模作业后，读取终态里的 preview 相关字段（preview_status 与 preview 块）。预期建模成功时预览状态为 written 且 preview_file 指向一个存在的文件路径；记录状态与路径原文。预览失败不得改变作业成功判定与 revision——若观察到相反，如实记录。
2. 上色不变项：先建一个最小装配——(a) 新建两个零件模型并各做一个简单拉伸，记录它们的 model_id；(b) `creo_new_assembly`（model_name=wb0111_asm_<随机后缀>）建装配并轮询到终态；(c) 用 `creo_execute_plan`（model_id=装配、expected_revision=其当前 revision）提交 assemble_component 操作把其中一个零件装入装配（source_model_id 填该零件 model_id），轮询到终态并记录装配的 model_id 与 revision。然后对该装配调用 `creo_recolor_assembly`（dry_run=true，families 省略以自动按零件族分组；palette 的键填被装入零件的 source_model_id、值为一个 RGB 三元组如 [1.0, 0.0, 0.0]）。预期 dry_run 不创建作业、不推进 revision，返回分组、每族计数与 appearance 基线是否就绪；记录返回内容与调用前后的 revision。随后可用 dry_run=false 提交一次真实上色（palette 必须覆盖每个族恰好一次），预期作业 succeeded、revision 恰好 +1、每个组件的 appearance 读回与请求 RGB 偏差 ≤1e-6、源零件文件字节不变。若装配搭建或上色中途被拒绝，本条记"未验证"并记录被拒的完整 message 与所处步骤，不要凭 0.11.0 的历史结论判通过。
3. 工具清单：与场景 0 的 tool_count 对照，本版公开工具总数预期仍为 95（0.11.0 起未增减公开工具）；若有增减如实记录差异。

### 8. 报告要求

按场景逐条输出表格：场景 | 工具与完整输入摘要 | isError | job_id | model_id | 终态 status | message 摘要 | 指定字段实测值（failed_model_cleanup 五字段 / rollback_status / geometry_deviation / preview / capacity 等）| 前后 volume_mm3 | revision | 保存重载标志。

逐项给出结论：通过 / 未通过 / 无法确认，并在"原因"列写明依据（引用的具体字段与实测值）。要求：

- 与预期不符的结果原样记录，不重试掩盖、不改写输入后当作一次成功。
- 接口不可观察的项目（响应字节数、构建身份、源码指纹、内部调度细节）记"无法确认"，不推测。
- 并发结论只在本节真实制造出时间重叠的提交时才写"通过"；未制造出重叠则写"未验证"。
- 明确列出本轮未覆盖的项目（例如未做装配上色、未验证 Creo 9/10 环境），不据工具数量或既往版本结论判全通过。
