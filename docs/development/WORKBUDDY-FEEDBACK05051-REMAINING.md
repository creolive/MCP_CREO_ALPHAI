# WorkBuddy 黑盒验收提示词：0.5.0/0.5.1 反馈剩余项（2026-10-26）

按 [反馈计划](0.5.0-0.5.1-FEEDBACK-PLAN-2026-10-23.md) Task 4 准备。本文件只包含公开 MCP 操作、输入、预期与报告要求；WorkBuddy 不阅读源码、配置、Git 状态、native.log 或本地引用文件，不执行本地 Python 脚本、单元测试或开发检查。环境、会话、可见工具与服务版本经 MCP 公开接口确认；接口未提供的构建身份记"无法确认"。每个场景记录：工具调用、输入、job_id/model_id、终态、几何/参数、revision、保存重载与原始错误；结论分"通过 / 失败 / 未验证 / 无法确认"。只有真实实施了并发调用才能报告并发通过；无适用现场的项目保持未验证，不杀进程或改配置制造条件。

## 场景 1：BUG-082 修复目标（在轴扇形 autodim 编辑）

1. `creo_execute_plan`：`model_name=wb082_<随机>`，operations：XZ 面 sketch（label `rev_sk`，entities：centerline `axis` (0,0)→(0,20)；line `l1` (0,0)→(10,0)；arc `prof_arc` 圆心 (0,0)、半径 10、0°→90°；line `l2` (10·cos90°,10·sin90°)=(0,10)→(0,0)，dimensioning `autodim`）+ revolve（label `rev1`、sketch `rev_sk`、angle 360）。
2. 记录 job_id/model_id/revision/体积（预期成功，体积 ≈ 2094.3951 mm³ = (2π·10³/3)·sin90°，容差 0.01）。
3. `creo_update_sketch_geometry`：同一 model_id、`expected_revision` 为当前 revision、sketch `rev_sk`、同上实体但弧 0°→80°（l2 起点改 (10·cos80°, 10·sin80°)），`dimensioning="autodim"`。
   - 预期：成功；revision +1；体积 ≈ 2062.5765 = (2π·10³/3)·sin80°；响应 solver 信息 `requested="autodim"`、`used="coordinates"`；`saved_file_reloaded_and_verified=true`。
4. 回程 80°→90°、改半径 10→12（弧与 l1/l2 端点同步，l1 终点 (12,0)）、再回程 12→10：每次携带最新 `expected_revision`，均预期成功，体积分别 ≈ 2094.3951 / 3619.1147 / 2094.3951。
5. `creo_inspect_model`（detail=compact）核对 rev_sk/rev1 特征 ID 全程不变。
6. 失败对照（独立新模型，同步骤 1 创建后）：编辑为**开环剖面**（`l2` 改 (0,10)→(0,5)，其余不变）。预期：作业 failed、`rollback_succeeded=true`、`failed_features` 含 REV1 且 status≠0、模型体积/revision 复原。

## 场景 2：BUG-083 非法轴结构化拒绝

对 `creo_revolve` 与 `creo_execute_plan`（revolve op）分别提交 `axis={"entity":"ax"}`、`axis={}`、`axis="axis_label"`、`axis={"kind":"datum_axis_feature"}`（缺 label）、`axis={"kind":"axis"}`（缺 id）。预期：两入口均结构化拒绝（isError），错误指出 axis 路径与正确形式（`{"kind":"datum_axis_feature","label":…}` 或 `{"kind":"axis","id":N}`）；无 job_id 生成即不算已接受作业。省略 axis 与 `axis=null` 等价（用草图中心线），空对象按缺 kind 拒绝。

## 场景 3：BUG-083 合法轴双路径

1. 省略 axis：execute_plan 用含恰一条构造中心线的回转草图（可用场景 1 同款剖面）+ revolve 360，预期成功、几何正确、保存重载 true。
2. `axis=null`：同一计划再次执行（新模型），预期与省略等价。
3. 显式轴：同一计划先 `datum_axis`（label `turn_axis`，references 两个基准平面）再 revolve `axis={"kind":"datum_axis_feature","label":"turn_axis"}`，预期成功、体积正确、保存重载 true（参照 `examples/revolve_external_axis.json`）。

## 场景 4：FEAT-030 元数据与创建

1. `creo_list_seeds`：记录九个种子的 name/section_count/interpolation/sha256 与 `seed_build_version`（无生产来源记录时保持 null）。
2. `creo_validate_seed`（任选两个）：`available=true` 只代表文件/哈希一致；`native_compatibility.status` 预期 `not_verified_for_current_session`；observations 为其他会话的历史加载，不证明本会话可加载。
3. `creo_new_loft_part`：用所选种子的 `seed_file`/`seed_feature_id` 与匹配的 sections/interpolation 显式创建模型，预期成功并记录 `seed_load_evidence`。
4. 再次 `creo_validate_seed`：`available` 语义不变；不要期望普通查询隐式试载种子。

## 场景 5：BUG-081 自然阻塞现场（仅有适用现场时执行）

仅当会话中真实存在"终态作业的仍存活 owner 拒绝"现场时执行：对同一批条目先 `creo_migrate_registry`（mode=inspect），记录 `owner_block`/`blocked_entries` 与原始拒绝；现场允许且属于原授权迁移范围时再 apply。inspect 不授权 apply。无现场只记"未验证"，不制造进程或注册现场。

## 场景 6：busy / unknown（仅记录真实发生）

仅当真实并发交错发生时记录：busy 立即拒绝（isError、blocking_job_id 等，不排队不重试）；已接受作业只轮询 `creo_get_job`；unknown 保持保护、不清场不重提。未真正并行调用不得报告并发通过。

## 报告要求

每场景单独成节：操作序列、输入 JSON 摘要、job_id/model_id、终态与原始错误、几何/体积/revision/特征 ID、保存重载结果；结尾给出四态结论表（通过/失败/未验证/无法确认）与无法由 MCP 观察的项目清单。
