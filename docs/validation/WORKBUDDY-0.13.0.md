# 0.13.0 WorkBuddy 黑盒验收提示词（待执行）

按项目 WorkBuddy 约定执行：仅通过已连接的 MCP 工具对最终用户可见行为做黑盒验收，不查看/分析源码，不执行本地 Python 脚本、单元测试或开发检查，不读取本机配置、仓库状态或 Git。环境、会话、可见工具与服务版本用 MCP 公开接口确认；接口未提供的构建身份记"无法确认"。开发者侧实机证据见 [发布记录 0.13.0](RELEASE-0.13.0.md)，两者分别记录、互不替代。

前置条件（本提示词在下列条件全部满足后才开始执行）：MCP 服务已连接且指向待验收的 0.13.0 候选服务；Creo 会话可用（`creo_session_status` 的 `connected=true`、`toolkit_code=0`）；操作者已确认 Creo 界面可操作、无阻塞对话框。会话不可用时本轮全部记"未执行"，不要尝试启动或重启 Creo，也不要结束会话进程。

---

## 提示词

你在做 MCP Creo 服务 0.13.0 候选版的黑盒验收。只调用已连接的 MCP 工具完成下列场景，逐项记录：工具名与完整输入、job_id/model_id、isError 与完整 message、终态 status 与 message、作业明细中的指定字段、操作前后 volume_mm3/area_mm2、revision、保存重载标志。

通用规则：所有修改提交后只轮询 `creo_get_job`（detail=compact）直到终态，不重复提交同一作业；返回 busy 按回执指引处理，不改写输入重投；出现 unknown_outcome 立即停止新写入并如实报告。每个场景使用全新隔离模型名（建议 `wb0130_<场景>_<随机后缀>`），不复用历史 model_id。

### 0. 环境与服务身份确认

1. `creo_session_status`：记录 connected、connection_state、toolkit_code、release。
2. `creo_capabilities`（detail=compact）：记录 name、version、server_version、**tool_count（预期 99）**、`scheduling.admission`、`scheduling.native_channels`。
3. 确认存在这些公开工具：`creo_execute_plan`、`creo_inspect_model`、`creo_get_job`、`creo_capabilities`、`creo_session_status`。接口未提供的身份字段记"无法确认"。

### 1. 曲面扫掠：开放面、加盖面与实体化

一次 `creo_execute_plan`（省略 model_id）：

```json
[
  {"op": "sketch", "label": "wb_path", "plane": "XZ",
   "entities": [{"type": "line", "name": "p", "start": [0, 0], "end": [20, 0]}]},
  {"op": "sweep", "label": "wb_sweep", "trajectory": "wb_path",
   "profile": [{"type": "rectangle", "name": "r", "min": [0, 0], "max": [40, 20]}],
   "mode": "surface", "capped": false}
]
```

预期：作业 `status=succeeded`；`creo_inspect_model`（section=quilts）给出**恰好一个** quilt，`area_mm2` = **2400.0**（±0.5，等于 2×(40+20)×20），`closed=false`；作业明细里 `saved_file_reloaded_and_verified=true`。

### 2. 加盖曲面扫掠后实体化

同上计划，改 `capped: true`。预期：quilt `area_mm2` = **4000.0**（±0.5，侧壁 2400 + 两个 40×20 端盖），`closed=true`；再提交

```json
[{"op": "solidify", "label": "wb_solid",
  "reference": {"kind": "quilt", "id": "<上一步的 quilt_id>"}, "side": "positive"}]
```

预期：作业 `status=succeeded`，作业明细 `volume_after_mm3` = **16000.0**（±1.0，等于 40×20×20），`saved_file_reloaded_and_verified=true`。

### 3. 曲面修剪与加厚

一次作业：填充 40×20 平面（XY 草图矩形 [0,0]-[40,20]）→ 用 x=5 的基准面修剪 → 对保留面加厚 2 mm。预期：修剪作业明细 `area_after_mm2` 为 **700.0** 或 **100.0**（两侧其一，记录实际值与 `kept_side_basis`），加厚作业明细 `volume_after_mm3` = `area_after_mm2 × 2`（±1.0）。

### 4. join 的可测量并集

一次作业：两张 40×20 填充面（A: x∈[0,40]，B: x∈[30,70]）→ 用 x=40 的基准面修剪 B → 两片各加厚 2 mm。预期：修剪后 B 的保留面积 = **600.0**（±0.5）；两片加厚后模型实体总体积 = **2800.0**（±1.0，等于 (800+600)×2；简单相加是 3200，重叠只算一次）；作业明细 `saved_file_reloaded_and_verified=true`。

### 5. 曲线投影

一次作业：40×20 填充面 → 沿 −Z 投影一条直线 → 记录 `curve_length_mm` 与 `endpoints_mm`。预期：`curve_length_mm` = **40.0**（投影被目标面裁剪，不是源线全长），端点落在面内。

### 6. 门禁与拒绝（记录 message，不绕过）

依次提交并记录拒绝理由：

- `{"op": "loft", "label": "x", "sections": ["a"], "mode": "surface"}` → 预期在排队前被拒（Direct Blend 只支持实体 add）。
- `{"op": "quilt_merge", "label": "x", "sources": [...]}` → 预期被拒（曲面合并未公开）。
- `{"op": "sketch", "label": "x", "entities": [...], "endpoint_policy": "weld", "max_endpoint_move_mm": 0.001}` → 预期被拒（原生受控焊接不存在）。
- 对同一模型用**陈旧 revision** 提交修改 → 预期被拒且 message 含当前 revision。

### 7. 失败回滚

一次作业：先建一个几何，再提交一个引用不存在 quilt 的修剪。预期：作业 `status=failed`；回滚后模型几何与提交前一致（面积/体积不变）。

### 8. 报告要求

逐场景给出：场景号、工具与完整输入、job_id、model_id、isError、终态 status 与完整 message、上述各测量字段的实际值与期望值、是否一致、revision、保存重载标志。未执行或无法确认的项写"未执行/无法确认"并说明原因，不要推测数值。
