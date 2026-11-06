# MCP_CREO_MechDog 0.16.1

发布：2026-11-06 · 类型：PATCH · 公开工具：**100**（无新增、无删除、无参数语义破坏，仅新增回执字段）

本版合并 0.13.0 / 0.14.0 反馈的修复批（DEV-069）：把「看起来可测」的数值改成有来源、有边界的回执，并补齐之前只有离线契约的实机验收。

## 本版要点

**R01 / BUG-112 — 偏置距离适用性保护**
`creo_surface_offset` 不再把 `volume_after / source_area` 无条件当作偏置距离。新增 `offset_distance_status={available,source,query_code,reason}`，与 `source_area_status` 分离：只有单一平面源、偏置前体积≈0、结果体积为有限正值时才发布 `measured_offset_distance_mm`；已有实体（`pre_existing_volume`）、曲面/多平面源（`source_quilt_not_a_single_plane`）等一律 `null` 并给原因。面积可测时照常发布面积。

**R03 / FEAT-058 — 缺 API 的几何板厚验证与上下文修正**
新增 `geometry_normal_span` 来源：仅在编译期缺 `ProSmtBodyThicknessValueGet`、唯一材料 body、无子特征且 u/v/n 轴对齐时，用实测法向跨度核厚；API 存在但调用失败不走兜底。`thickness_verified` 由可信来源决定，缺 API 时不再因旧布尔为 null/false 而永远失败。新增 `wall_created_this_job`：同计划 create→resize 的 `thickness_loaded_validation.context` 为 `current_plan`，跨作业才是 `saved_loaded`。

**R05 / BUG-045 — 旋转矩阵准入判据集中与拒绝可读性**
Python 与原生（`native/assembly_pose.h`）共用同一 1e-6 行向量准入；拒绝信息带调用方矩阵的 `max |R*R^T-I|` 与 `det`，并说明输入原样回显、不修复。已准入但非严格正交的矩阵分类为 `near_orthonormal`（1e-9 仅分类，不是新阈值），`failed_operation` 增加 `precision_class`/`precision_advice`。**准入阈值未改。**

**R13 / BUG-114 — 失败清理的事务效果归因**
新增 `terminal_effect` / `component_changes` 归因：可信清理确认新模型已擦除且不存在后，`component_changes=no_effect` 只作用于模型/组件范围，`execution_status` 与旧 `rollback_status`、unknown 保护字段保留；已保存模型仍走检查点回滚，不因"新件可擦除"放宽。

**R04 / FEAT-023 — 查询投影与协议补证**
compact 白名单加入 `offset_distance_status`；新增查询协议回归（compact/full、sections、分页游标、列表预算），不改接口形态。

**R02 / BUG-113 — Backup/回滚定向复现**
新增默认离线的 `tools/test_surface_save_recovery.py` 与判定测试（`failure_verdict`、`baseline_invariants`）；本机 12 例中 3 例 `single_plan` + 独立平面组在 thicken 返回 `-4`、基线不变且保护未释放，另登记 BUG-115。外部 Creo 10 原件仍缺。

**R09 / FEAT-014 — miter 切角定标与 native_planar 路线补证**
新增 `tools/test_sheetmetal_planar_box.py`：native_planar 180×230×1 → resize 185×232×1（feature id 不变、保存重载）、四墙建成、按面 bbox 定标（自由墙顶面 run 232.0 = 附着边；miter 墙 185.0 vs 附着边 177.92，四角缺口 `[6,6]`）、gap/半径矩阵、unbend/bend_back/父壁 resize 拒绝/无效边折边回滚。

**R12 / FEAT-007 — 长轮询实机验收**
新增 `tools/test_job_wait_live.py`：`wait_seconds` 0/1/30、到期 `wait_expired=true`、终态提前返回、31 与 1.5 拒绝且作业不变、客户端取消不取消作业、第二 stdio 客户端读取同一持久化 job。等待不创建作业、不占 Toolkit 通道。

## 验证（2026-11-06，Creo 12.4.0.0 / 匹配 SDK）

- `bridge.py build` 退出 0，执行器重建。
- `tools/test_unit.py`：**2702** 项，0 失败、0 错误。
- `tools/dev_check.py --skip-unit`：通过（见发布记录）。
- 实机（均为本机 Creo 12.4.0.0，报告与摘要见 [RELEASE-0.16.1](validation/RELEASE-0.16.1.md)）：
  - R01 偏置 40×20 双侧 ±5 mm、已有实体、圆柱 quilt：27 项通过；
  - R03 板厚 77/77；
  - R13 清理四场景（新零件、同名复建、预存同名、新装配）全通过；
  - R12 长轮询六项全通过；
  - R09 native_planar/定标/矩阵/followup 全通过。

## 未验证

- Creo 9（本机无 SDK）与 Creo 10 实机；WorkBuddy 公开 MCP 黑盒。
- R12 断流/网络中断未单独注入；R02 外部 Creo 10 原件未取得。
- FEAT-014 relief 材料几何、更大厚度/半径范围；R10 首壁 origin、R11 曲面缺口路线。
- 历史版本、历史证据与已发布附件保持原状，不用本版结果回填。
