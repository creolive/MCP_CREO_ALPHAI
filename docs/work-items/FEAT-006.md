# FEAT-006：失败阶段、原生诊断与操作结果的可定位契约

日期：2026-10-16 补全。类型：功能。优先级：P2。状态：实现完成，实机取证通过（收养拒绝逐特征诊断子项，[2026-10-24 实机记录](../validation/BUG080-FEAT006-LIVE-2026-10-24.md)；WorkBuddy 黑盒待执行；C++ 纯逻辑夹具待 `tests/native` 范式顺手补）。目标版本：0.5.2。

## 2026-10-23：收养拒绝的有界逐特征诊断（0.5.0 反馈计划第一批 P1-5）实施

[0.5.0 反馈计划](../development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)第一批"补收养拒绝的有界逐特征诊断"已在开发分支 `codex/feat006-adoption-health-details`（自 main d508444 切出）实施，未合入 main：

- 原生侧（`native/generic.cpp`）：`adopt_native` 的 live 摘要新增内联 `health_details`——对每个失败/抑制/不完整特征输出 `id`、`name`、`type_name`、`status_code`（`ProFeatureStatusGet` 原始整码，SDK 头文件 `ProFeature.h` 枚举核对为 -1～6）、可读 `status` 标签与 `incomplete` 标记；只列前 20 条，附 `unhealthy_total` 真实总数、`returned`、`truncated`。apply/prepare 防线拒绝消息同步携带总数与已列条数（前缀 `unhealthy_features:` 不变）。健康准入规则本身未改。
- Python 侧（`src/creo_mechdog/adoption.py`）：`_refusal_details` 校验并把 `health_details` 暴露为 `refusal_details.unhealthy_features`，`health_breakdown` 改为逐特征口径；数据缺失或畸形（旧执行器）回退原合并口径文本，另设 50 条防御性截断上限。`ADOPTION.md` 契约段已同步。
- 测试（`tests/unit/test_adoption.py`）：新增 4 例——有界明细透传、无明细回退 unknown、畸形数据回退、超长清单防御性截断。全套 558 例单元测试通过；`bridge.py build` 编译通过产出新执行器；`tools/dev_check.py` success=true（无新增诊断、格式合规）。

未验收范围：按 BUG-001 约束未做实机 Creo 验收与 WorkBuddy 黑盒复验（需真实不健康零件触发 `unhealthy_features` 拒绝并核对返回明细）；C++ 侧有界提取的纯逻辑测试待 dev046 分支的原生测试设施（`tests/native` 范式）合入后补。未合入 main，未发布版本。

### 2026-10-24 回收核对（task/2 工作树，HEAD 62bc4dc）

独立复核确认 2026-10-23 实施真实落地，非仅"已启动"：`native/generic.cpp` 的 `health_details()` 以采集侧真实 `status`/`incomplete` 键（generic.cpp 采集段）为源，20 条上限、`unhealthy_total`/`returned`/`truncated` 与逐特征 `id`/`name`/`type_name`/`status_code`/可读 `status`/`incomplete` 齐备，健康判定与明细读取同键同源；拒绝消息携带总数与已列条数；`src/creo_mechdog/adoption.py` `unhealthy_features` 校验透传、畸形/缺失回退与 50 条防御截断在案；`ADOPTION.md` 契约段同步；4 个新测试方法在本提交内。

- 单元复跑：主仓工作树（同一提交 62bc4dc；dirty 仅 `session_activity.json` 运行改写与未跟踪 WorkBuddy 运行产物）全量 558 例 `python -m unittest discover -s tests` OK（182.5s）。task/2 worktree 内复跑 dev_check 单元段失败，系 `server.py:55` 源码身份守卫拒绝跨检出导入（editable 属主仓，按 AGENTS 需各检出自装 `pip install --no-deps -e .`），非本提交回归；该次风格门通过（31 lint/19 未格式化，与既有基线一致，无新增）。
- 编译核对：主仓 `build/creo_worker.exe` 时间戳 2026-10-23 22:53（本提交前 9 分钟），为含 `health_details` 的重建产物。
- 合并面核对：与 `codex/dev046-feedback050`（b09ffc3，DEV-046 文档收口+BUG-080）`git merge-tree` 无文本冲突；合并后 dev046 的 `tests/native` 范式可用于补 C++ 有界提取夹具，其 BACKLOG 头部"FEAT-006 待下一 PATCH 实施"注记需按本分支现状校正；`version.py` 当前 0.5.1，下一 PATCH（0.5.2）未占用。
- 验收缺口不变：实机真实不健康零件触发 `unhealthy_features` 拒绝并核对明细、WorkBuddy 黑盒仍受 BUG-001 会话核对条件约束，未执行。

### 2026-10-24 会话核对（0.5.2 实机验收前置，通过）

- Creo 会话：`xtop.exe` PID 22456 于 2026-10-24 08:22:48 启动，Responding=True；无 `creo_worker` 进程在运行，Toolkit 通道空闲。
- 连接 -4：0.5.0 计划（10-22）"最新连接 -4 尚未解除"已过时——[BUG030 收口记录](../validation/BUG030-CACHE-CLOSEOUT-2026-10-22.md) 2026-10-22/23 节完成排查（本机 SDK 枚举为 `PRO_TK_E_NOT_FOUND`）、用户授权恢复，[BATCH2 §8](../validation/BATCH2-EDITING-2026-10-22.md) 记录 2026-10-23 本机实机验收完成（专项 9/9、general_core 7/7、同会话空闲约 12.5 分钟复连通过）；最新 Toolkit 作业 2026-10-23 13:50–13:52 均为终态。
- 模型登记：822 项登记无 `recovery_pending`/`pending_job`；含 unknown 字样的 8 项均为终态（ready/abandoned/failed），BUG-078 三个旧现场已于 10-22/23 经 accept 动作收口。
- 结论：会话核对条件满足，BUG-001 下暂停的 Toolkit 实机验收可恢复；本子项实机触发与 WorkBuddy 黑盒随 0.5.2 验收会话顺带取证。

## 当前进度（2026-10-21）

接管空窗口NO_CURRENT_MODEL的Python结构化转换与预检全阶段诊断已随0.4.5交付，实机空窗口保留ProMdlCurrentGet调用及-8原码；native结果/来源核验/冲突扫描/令牌发布失败记录failed_stage，超限收尾不覆盖原始诊断。见[本次实施证据](../validation/BUG076-FEEDBACK042-2026-10-21.md)，预算阻断本身仍由BUG-076继续定位。

其余诊断仍需规划：union长错误、body/plane/fixed_surface候选与查询指引，轮廓/约束及创建返回0但再生status6的原生详情、过期surface的-23提示。自交轮廓预检仅为待评估建议；原生失败特征名/ID、ProFeatureError与冲突面边、min_wall等只在SDK可可靠取得时返回，不能从-1或日志中成功调用回显猜根因。失败操作结果与模型清理/恢复尚需各自验收。

历史定位样例见[曲面反馈原件](../validation/feedback-0.3.5-surface-2026-10-18/report.md)：shell两次失败时native_log_tail只有成功调用回显，报告后续定位到0.357mm刀口尺寸链；这支持补最小壁厚/冲突面提示的需求，不作为任意shell失败的通用根因。自交轮廓O(n²)预检同样只保留为方案建议。

来源：既有统一错误与诊断项；新增[履带反馈](../validation/TRACK-FEEDBACK-2026-10-16.md)第一、七、十、十二和十八节。关联 BUG-018、BUG-030、BUG-031、BUG-049～051、FEAT-007、FEAT-023。

## 目标与范围

让失败能定位到操作、特征/草图和可取得的原生原因，区分创建失败、创建后再生不健康、回滚失败与结果未知。`ProFeatureWithoptionsCreate=0` 不能替代特征健康和保存重载；status 6 不直接证明共面、自交或内核限制。

首批围绕履带切除/约束，保留统一错误码、失败调用、Toolkit 返回、操作索引/标签、特征 ID/status、可取得的剖面/再生诊断及有界上下文。候选环或面只有可靠定位时返回；SDK 没有详情时明示“无法取得”，不补造根因。错误索引规则、完整性/截断标志和详情入口须明确。

对重合约束失败，评估返回实际实体/端点引用、坐标与距离；自动吸附会改变几何，须另有显式契约，不能静默启用。对修正既有尺寸，给出“查询当前可编辑驱动尺寸 → set_dimensions”的指引，不能硬编码报告 ID=2788，也不把它当作任意失败的通用修复。

## 验收标准

| 场景 | 可判断的预期结果 |
| --- | --- |
| 创建直接失败 / 创建后再生失败 | 阶段明确，准确区分调用返回 0 和最终不健康；只列真实可取得的失败特征与诊断 |
| 约束/引用错误 | 指明可确认的实体、端点或候选面，距离有单位；未知原因不写确定诊断；信息有界且保留详情入口 |
| 操作历史与回滚 | 区分执行后回滚、执行失败、未执行和不确定，失败索引/顺序一致；不把 completed_operations 当已持久化成果 |
| 兼容与大小 | 保留已有字段兼容，compact 不输出完整 union dump 或全量日志；UTF-8 大小/截断与详情标志按 FEAT-023 验证 |
| 后续修正 | 查询得到的自由驱动尺寸可合法修改并保存重载；关系控制/只读尺寸准确拒绝，原文件/revision 与回滚保持一致 |

开发环境 Windows x64 / Creo 12.4 / 匹配 SDK；统一检查、受影响构建和切除/草绘/约束失败恢复回归。WorkBuddy 验证 MCP 原始错误、job/model、revision 与后续编辑，不读取原生日志来补产品缺失字段。

## 实现与证据

本次只补卡与去重来源，未增加错误字段、吸附功能或改再生路径。外部 status 6、共面侧壁等观察和解释分开保留；与 BUG-048 含镜像抽壳的特定复现不互相代替。

## 2026-10-17：0.3.4 特征引用错误的可行动提示

[报告第四节](../validation/FEEDBACK-0.3.4-2026-10-17.md)称 dump_feature_tree 用原生名 H34 报 Unknown feature label，创建别名 h34 成功。沿用本项与 FEAT-008：明确 label/id/原生名、大小写及支持范围，评估有界可用别名/当前引用查询指引，避免全量 aliases 膨胀或泄露无关模型。未承诺原生名输入时不据此登记导出缺陷，不能在歧义时猜选对象。本次只补需求。

## 2026-10-20：0.4.1 接管空窗口的语义化错误

[v0.4.1 反馈](../validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md) P3-1：会话无模型时 `creo_adopt_current_model(mode=inspect)` 返回裸 `ProMdlCurrentGet(&current) failed with code -8 during adoption_inspect`，agent 无法区分"窗口无模型"与连接故障。本轮在 native 接管入口对该调用返回"无当前模型"原码时改抛 `NO_CURRENT_MODEL` 前缀错误，保留失败调用名与 Toolkit 原码，并提示先经 `creo_list_session_models` 查看会话清单。仅改错误可读性，不改接管准入、证据与保护路径；其余裸 Toolkit 错误码的可读化仍按本卡整体范围分批推进。

实现当日完成（-8 经 SDK 头文件核对为 PRO_TK_BAD_CONTEXT）；实机以装配窗口的 `unsupported_model_type` 前缀路径旁证稳定原因码改造，无窗口 `NO_CURRENT_MODEL` 分支留 WorkBuddy 黑盒复验，见[验证记录](../validation/FEAT-044-live-2026-10-20.md)第四节。

### 2026-10-24 实机触发取证（通过）

task/2 整合树实机（Creo 12.4）：未受管种子副本（毫米、无依赖）经夹具真实抑制 BLEND 特征（id 82）后，`creo_adopt_current_model(mode=inspect)` 返回 `reason_code="unhealthy_features"`（结构化正常响应 `available=false`），`refusal_details.unhealthy_features` 为 `unhealthy_total=1/returned=1/truncated=false/items=[{id:82,name:"BLEND",type_name:"protrusion",status_code:5,status:"suppressed",incomplete:false}]`（`ProFeatureStatusGet` 原始整码 5=PRO_FEAT_SUPPRESSED），`health_breakdown` 逐特征口径。受管路径旁证：`managed_output` 拒绝同样携带完整明细（PAD2 id 87 抑制案例）。截断与旧执行器回退路径未实机触发（单测覆盖）。详见[实机取证记录](../validation/BUG080-FEAT006-LIVE-2026-10-24.md)。
