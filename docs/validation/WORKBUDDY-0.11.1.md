# 0.11.1 WorkBuddy 黑盒验收提示词（待执行）

按项目 WorkBuddy 约定执行：仅通过已连接的 MCP 工具对最终用户可见行为做黑盒验收，不查看/分析源码，不执行本地 Python 脚本、单元测试或开发检查，不读取本机配置或仓库状态。环境、会话、可见工具与服务版本用 MCP 公开接口确认；接口未提供的构建身份记"无法确认"。开发者侧实机证据见 [Q15 三轮实机记录](DEV-053-Q15-live-2026-11-01.md)，两者分别记录、互不替代。

前置条件：MCP 服务已连接且 Creo 会话可用（`creo_session_status` connected=true、toolkit_code=0），操作者已确认 Creo 界面可操作；会话不可用时本轮全部记"未执行"，不要尝试启动或重启 Creo。

---

## 提示词

你在做 MCP Creo 服务 0.11.1 的黑盒验收。只调用已连接的 MCP 工具完成下列场景，逐项记录：工具名与完整输入、job_id/model_id、终态 status 与 message、作业/模型明细中的指定字段、操作前后 volume_mm3、revision、保存重载标志。所有修改提交后只轮询 `creo_get_job`（detail=compact）直到终态，不重复提交；返回 busy 按回执指引处理；出现 unknown_outcome 停止新写入并报告。除场景 1 复用同名外，每个场景使用全新隔离模型，不复用历史 model_id。

### 0. 环境确认

1. `creo_session_status`：记录 connected、toolkit_code、release。
2. 列出可见工具并计数（预期 95 个）；确认 `creo_execute_plan`、`creo_new_part`、`creo_inspect_model`、`creo_get_job` 存在；记录服务版本（接口未提供则记"无法确认"）。

### 1. 失败模型清理与同名重试（新模型，未保存路径）

1. `creo_new_part`（模型名如 wb0111_cleanup），随后单次 `creo_execute_plan` 提交：XY 矩形草图 min=[-30,-20] max=[30,20] + `extrude` add depth=10 + 圆草图 center=[100,100] radius=5 的 `extrude` cut（板外，确定失败）。预期：作业 failed，message 含 "removes no material"；终态含 `failed_model_cleanup`（记录其全部字段，预期 status=erased/cleaned、absence_verified=true 一类可判定值）与 `rollback_status`（新模型预期 not_attempted）。
2. 随后再次 `creo_new_part` 使用**同一模型名**。预期：成功，不出现 "name already exists in the Creo session" 类错误。

### 2. 已保存模型的失败回滚与 rollback_status

1. `creo_new_part` + `creo_execute_plan`：场景 1 的矩形+extrude（无失败项）。预期 succeeded，revision 1。
2. 同模型再提交板外圆 cut（expected 失败）。预期：作业 failed；`rollback_status=succeeded`；`creo_inspect_model` 体积与 revision 与提交前一致；模型仍可继续编辑（再提交一个有效小特征应成功）。

### 3. 三点定面与斜面草图

1. `creo_new_part` + 单次 `creo_execute_plan`：三个 `datum_points`（A=(0,0,0)、B=(40,0,30)、C=(0,30,-20)）→ `datum_plane` reference 为 {kind:"through_points", 上述三点标签} → 在该平面上的三角形草图（frame 的 u 轴沿 A→B，闭合三角形 A、B、C）→ `extrude` 厚度 5。预期：succeeded；volume_mm3 ≈ 4250（三角形面积 850 mm² × 5）；revision 1；保存重载 true。
2. 负例一：三点共线（如 (0,0,0)、(10,0,0)、(20,0,0)）的 through_points 计划。预期：被拒绝（准入或执行失败均可，记录 message 原文），不产生半成品模型。
3. 负例二：三点中两点相同。预期：被拒绝并给出可读原因。

### 4. 草图显式容差 geometry_tolerance_mm

1. 在场景 3 类似的常规草图中带 `geometry_tolerance_mm=0.05` 提交。预期：正常 succeeded，容差字段随回执可见（记录实际字段名与值）。
2. 非法值负例：分别提交 `geometry_tolerance_mm=0`、`-1`、`"0.01"`（字符串）各一次。预期：三次均在准入层被拒绝且 message 可读；无 job 创建时记录 job_id 为空。

### 5. busy 立即拒绝（真实并发 + 背靠背）

1. 真实并发：提交一个多操作长计划（如 30+ 特征的阵列/多草图计划），在其执行期间（stage=executing_feature_plan 或轮询仍 running）立即提交第二个计划。预期：第二个立即返回错误，isError=true、status="busy"、accepted=false、blocking_job_id=第一个 job、含 blocking_model_id/blocking_operation 与重试指引；不新建第二个 job。第一个作业正常到终态。
2. 背靠背：第一个提交的返回一到达就毫秒级紧跟第二个提交。预期同样为 busy 拒绝（不得出现两个都被接受排队后串行执行的情况）；如实记录两次的时间与回执。
3. 仅当真实实施了同时/紧邻提交才可记录并发结论；串行先后提交不算本场景。

### 6. 作业 stage 流转与结果分页

1. 场景 5 的长计划执行期间多次轮询 `creo_get_job`（detail=compact）。预期：status/stage 依序推进（记录观察到的每个 stage 值与时间）；compact 终态可完整返回。
2. 对特征数较多的模型调用详情/预览类工具：若结果被截断，回执应含 total/truncated/sample 一类的有界字段（记录实际字段与数值）；detail=full 的 cursor 分页翻页不重不漏（记录两页样本比对）。
3. 字节预算（≤32 KiB）客户端不可观察，记"未验证"。

### 7. 报告要求

输出表格式记录（场景 | 输入摘要 | job_id | model_id | 终态 | message 摘要 | 指定字段实测值 | 前后体积 | revision | 保存重载）。任何与预期不符的结果原样记录，不重试掩盖；接口不可观察的项目记"未验证/无法确认"；不推测内部机制（文件占用、重试预算、内部日志等）。不要求测试未列出的工具或分支。
