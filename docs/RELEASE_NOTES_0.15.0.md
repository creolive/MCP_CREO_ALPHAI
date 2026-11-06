# MCP_CREO_MechDog 0.15.0 版本说明

2026-11-06，MINOR 性质的 0.13.0 外部反馈收口批；条目：[DEV-069](work-items/DEV-069.md)。新增只读长轮询参数 `creo_get_job(wait_seconds=...)`，公开工具仍为 **100** 个，无新增工具、无参数迁移、无回调注册变化、无新增原生编译要求。

来源：[核对与修复设计](superpowers/specs/2026-11-06-0.13.0-feedback-repair-design.md)、[实施计划](superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)、[逐项映射](validation/feedback-0.13.0-2026-11-06/MAPPING.md)。本版先修稳定性与证据可信度，再补回执、契约和新能力；C 批（四壁/首壁 origin/曲面缺口）路线未成立的部分保持 gated。

## 稳定性与证据

- 偏置源面积返回码（[BUG-112](work-items/BUG-112.md)）：`creo_surface_offset` 只在初始化返回成功且句柄有效时才调用面积测量，结果新增 `source_area_status={available,init_code,query_code,reason}`；初始化失败、句柄无效或测量失败时数值为 null，不再由 `volume_after/source_area` 产生有限距离。自有原生代码编译增加 `/we4552` 失败规则。
- 保存失败与回滚差异分别定因（[BUG-113](work-items/BUG-113.md)）：结果新增 `save_failure`（call/code/stage/destination/source_checkpoint/candidate_files）与 `rollback_difference`（feature/body before-after、缺失/新增、状态、体积/单位、可用性），候选与差异清单 ≤20 并带 total/truncated；明确“体积相同”不等于回滚成功，仅身份/状态/几何与基线全部相符才可按既有规则恢复 ready。恢复指引先建议 `creo_reconcile_model(mode="inspect",live=false)`，有失败回滚时不建议 ack 绕过。
- 四附件发布闸门（[DEV-070](work-items/DEV-070.md)）：打包与核对要求源码包、种子包、两份 SHA256 sidecar 同时存在且使用 LF 行尾，缺一不通过。

## 回执与契约

- 板厚双上下文回执（[FEAT-058](work-items/FEAT-058.md)）：`thickness_validation` / `thickness_loaded_validation` 逐 op 发布 `status/source/value/reason/context`，区分当前计划与保存读回；API 存在但失败或几何冲突时拒绝改型，缺 API 的几何兜底仅对已核对的纯矩形/唯一材料 body 开放，参数与 `V/(L×W)` 不能自证。
- 精简轮询与列表预算（[FEAT-023](work-items/FEAT-023.md)）：compact 只投影原生已存在的判据字段（trim 面积/侧别、offset 实测距离/源面积、project 长度/端点/curve、solidify closure），null 与 reason 原样保留；列表 ≤50 项、序列化 ≤32768 B，`get_job` compact 新增 `full_detail_hint` 指向 `detail=full&section=operations_result`。
- 矩阵约定与失败上下文（[BUG-045](work-items/BUG-045.md)、[FEAT-012](work-items/FEAT-012.md)、[FEAT-008](work-items/FEAT-008.md)）：schema 直接透出行向量公式 `p_parent = p_local * rotation_matrix + translation`，结果新增 `rotation_convention="row_vectors_local_to_parent"` 与 `assembly_pose_receipt` 实读 transform/source/unit；失败对象 `failed_operation` 带 index/op/label/sketch/stage/call/code，矩阵失败另带正交残差/det，未知成因保持 null。
- 会话可解释性（[FEAT-001](work-items/FEAT-001.md)、[BUG-091](work-items/BUG-091.md)）：启动重试回执区分身份/阶段/预算，health 事实分层，Toolkit 通道忙碌继续立即返回 `status="busy"` 与 blocking 上下文，不排队、不自动重试。
- 曲面引用契约（[FEAT-039](work-items/FEAT-039.md)）：trim/project/offset/loft 的 edge/surface 引用要求来自当前 revision 并逐 op 重解析，旧 id、回显或 eligible 不作为可用证明；工具说明与工作卡口径对齐。

## 长轮询与阶段计时

- `creo_get_job(wait_seconds=...)`（[FEAT-007](work-items/FEAT-007.md)）：在限定时间内只读等待任务记录，终态即返回、超时返回当前状态；不占用 Toolkit 通道、不创建任务、不重试，取消等待不影响已接受任务。
- connect 阶段计时（[BUG-109](work-items/BUG-109.md)）：原生工作进程在 `connect_creo` 前后各发一条带 `ts`/`elapsed_ms` 的 `STAGE`，`native_stage.stall_report` 可把会话附着耗时与首个操作阶段分开。

## 四壁口径与实机

[FEAT-014](work-items/FEAT-014.md) 只改诊断文案与能力口径，不新增几何、不放宽拒绝条件：`adjacent_bend_ends` 是创建前拒绝规则，`relief` 是 bend-end relief，不是 corner relief/miter。2026-11-06 用 `tools/test_sheetmetal_box_live.py --live --confirm-session-usable` 跑 R09 第 3 项（本机 Creo 12.4.0.0，报告 `build/post090_n05_live_20261106T1505/report.json`，SHA256 `046702f2…1cf7`，`passed=true`）：自由首壁建成并保存重载；第三壁在 1 角（span 181.46/185）和 2 角（span 177.92/185）上下文都被创建前拒绝，回滚成功、revision/体积不变；`end_trim_mm` 实测仍被忽略。四壁仍不支持，第 4—6 项继续 blocked。

## 验证

- `python tools/test_unit.py`：**2616** 项通过，0 失败、0 错误。
- `python tools/dev_check.py --skip-unit`：`success=true`（24 lint、12 未格式化，未高于 style-baseline）。
- `python bridge.py build`：退出 0。
- 实机：R09 第 3 项对比（上节）；其余实机项见[发布记录](validation/RELEASE-0.15.0.md)。

## 未验证与仍开放

R01 的 40×20/±5 mm 实机基准与量纲/已有实体保护；R02 的 Creo 10 外部现场与真实回滚失败；R03 缺 API 的原生几何兜底实机；R04 真实 stdio 字节核对；R05 原生装配回读；R06 真实断连/`-4`/挂起；R09 第 4—6 项；R10 首壁 origin 与计划内几何选边；R11 真实 quilt merge 与多截面放样；R12 的 through_all 实机矩阵、装配 bbox、erase 耗时、rename、managed delete；WorkBuddy 黑盒；Creo 9 无本机 SDK，Creo 10 独立复测按 2026-10-15 决定取消；BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.15.0-source.zip` 与 `MCP_CREO_MechDog-0.15.0-seed-library.zip`，按安装说明更新环境并重启 MCP 服务。旧种子包会被版本闸门拒绝。
