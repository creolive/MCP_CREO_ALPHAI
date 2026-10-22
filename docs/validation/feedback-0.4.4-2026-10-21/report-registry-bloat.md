# MCP_CREO_MechDog v0.4.5 验收报告

> **文档命名**：2026-10-21 / CREO 10 / v0.4.5 / 核心问题：**BUG-076 结构化诊断生效并定位根因——单个历史模型的 model.json 膨胀至 21.4MB 阻断全部收养；且该文件同样阻断 reconcile 恢复通道，形成死锁**
> **验收日期**：2026-10-21
> **验收对象**：MCP_CREO_MechDog v0.4.5（首个正式版；历史轮次 v0.4.0→v0.4.4 五轮反馈）
> **文档目的**：验收 0.4.5 交付项；提交 BUG-076 根因定位证据（作者 recovery 指引要求的全部字段）；反馈新发现的死锁问题

---

## 1. 验收结论（TL;DR）

| 项目 | 结论 |
|---|---|
| **BUG-076 结构化诊断** | ✅ **按规格交付**——`ADOPTION_METADATA_BUDGET_EXCEEDED` + metadata_kind/actual_bytes/budget_bytes/failed_stage/recovery 全字段齐备（§3.1） |
| **根因定位（本报告核心价值）** | ⭐ 超限文件是 **MCP 自身模型注册表条目**：`models\c437cace…\model.json`（`track_p01b`，21,472,751 B）——**与被收养零件无关**，三轮"复杂度无关"之谜就此解开（§3.2/3.3） |
| **新发现 P0：死锁** | ❌ 同一文件也阻断 `creo_reconcile_model`（`Recovery metadata exceeds the 16 MiB read budget`）——诊断给了 recovery 指引，但 recovery 通道本身被同一文件堵死（§4.1） |
| FEAT-043/044（opened_session_model） | ❌ 未在本环境观察到（§4.2，疑似仅 file-source 路径） |
| 会话擦除工具 | ➖ 0.4.5 明确"另期"，维持 P1 |

---

## 2. 测试环境

| 项目 | 值 |
|---|---|
| MCP 版本 | **0.4.5**（`server_version` 确认；capabilities.update: up_to_date） |
| Creo | Creo Parametric **10.0.0.0**（release_numeric 42）——BUG-076 作者标注的原环境 |
| 会话 | 延续多轮验收：ASM_MX + 依赖组件 + P02_HUOSAI_GAN（当前窗口，186KB 活塞杆） |
| 注册表 | `E:\WorkBuddy Space\MCP MCP_CREO_MechDog\models\`：**212 个模型目录，共 357MB** |

---

## 3. BUG-076 复现与根因定位（作者 recovery 指引要求的诊断数据）

### 3.1 结构化诊断实测（0.4.5 交付验证 ✅）

`creo_adopt_current_model(inspect)` 在 P02_HUOSAI_GAN 为当前窗口时返回：

```json
{
  "reason_code": "ADOPTION_METADATA_BUDGET_EXCEEDED",
  "metadata_kind": "model_registry",
  "path": "models\\c437cace0625425496fec62d8c14743a\\model.json",
  "actual_bytes": 21472751,
  "budget_bytes": 16777216,
  "failed_stage": "origin_conflict_scan",
  "job_id": null, "model_id": null,
  "recovery": "Keep the oversized file unchanged for diagnosis; report metadata_kind, actual_bytes, path, job_id and the deployment identity ... Do not delete the file, rerun native execution, or raise the budget to hide the error"
}
```

与 0.4.5 release notes 承诺的字段**逐项吻合**。注意 `metadata_kind: model_registry`——超限的**不是**被收养模型的元数据，而是 MCP 自己的注册表。

### 3.2 根因（本环境只读诊断，未删改任何文件）

- 超限文件：`models\c437cace0625425496fec62d8c14743a\model.json`，**21,472,751 B**（预算 16,777,216 B）
- 身份：`model_name: "track_p01b"`，revision 16，created 2026-10-16——**10月16日 loft/几何变换验收时创建的测试模型**
- 内容特征：aliases 中 `band_p01` 的 entity_ids/geometry 映射规模巨大（sec_0…sec_19+ 逐实体映射），推断为多次 axis_pattern/geometry_transform 追加后**别名与几何映射无界累积**
- 同目录还有 `model.json.operator-reconcile-bak`（8,381,628 B，10-16 19:22）——**该模型此前已发生过一次超限并做过 reconcile 备份**，之后 revision 继续增长再次突破预算
- 注册表全貌：212 个模型共 357MB；第二名 `hull`（e81e1244，39MB 目录）model.json 3.4MB——距预算仅一步之遥，**下一个被堵的就是它**

### 3.3 机制解释（回答三轮之谜）

`origin_conflict_scan`（收养预检的来源冲突扫描）需读取**注册表条目**做冲突比对 → 读取是全量 JSON 载入 → 任何超过 16 MiB 的历史条目都会让**所有零件**的收养在同一阶段失败。这完美解释了 v0.4.2→0.4.4 三轮"与被收养零件复杂度无关"的复现（1MB 键帽/477KB 前盖/186KB 活塞杆全部阻断）。**BUG 的本质是注册表条目无界增长 + 预检全量读取的组合，与"收养元数据收集"无关**——0.4.5 "不提高限额、不重构存储"的决策正确，但还需要条目膨胀的治理手段（见 §5）。

---

## 4. 本轮新发现问题

### 4.1 【P0】死锁：同一文件阻断 reconcile 恢复通道

- 实测：`creo_reconcile_model(inspect, model_id=c437cace…)` →
  `Error executing tool: Recovery metadata exceeds the 16 MiB read budget`（裸 isError，无结构化字段）
- 语义死锁链：adopt 诊断的 recovery 指引说"保留文件、走诊断流程"→ 但唯一能归档/治理该模型的官方通道 `creo_reconcile_model` 自身也要全量读取同一 model.json → **两条路都走不通**，用户只能手改/手删注册表文件（恰恰是 recovery 指引禁止的动作）。
- 且 reconcile 的错误**未升级为结构化诊断**（无 reason_code/actual_bytes），与 adopt 同一预算机制却两套报文。
- **建议**：reconcile 复用 adopt 的结构化诊断；并为超大条目提供**不载入全量 JSON 的归档动作**（如 `abandon_new` 流程改为流式处理或仅按 manifest 头操作）。

### 4.2 【P2】`opened_session_model` 字段未在本环境观察到

- FEAT-043/044 宣称 open_file 成功结果新增该字段；本轮 `creo_open_file(p02_huosai_gan.prt)` 成功结果中**没有**该字段。
- 可能原因：该字段仅限 file-source 直接打开路径，而本会话 P02 已在会话中（上一轮打开）→ 未触发新检索；或 Creo 10 与 Creo 12.4 行为差异。无法定论，仅报告现象供作者核对（作者实机验证环境为 Creo 12.4）。

### 4.3 【P1 维持】会话擦除工具"另期"

- 0.4.5 release notes 明确"会话擦除、FEAT-045、装配接管/reconcile、旧 DLL 目录回收另期"。本会话现驻留 ASM_MX + 8 依赖 + 2 个零件，后续装配打开仍需手动 GUI 清理。

---

## 5. 建议优先级

| 优先级 | 事项 |
|---|---|
| **P0** | 打破死锁：`creo_reconcile_model` 对超限条目支持免全量载入的 `abandon_new`/归档（流式或 manifest 级）；错误报文对齐 adopt 的结构化诊断（§4.1） |
| **P0** | 条目膨胀治理：model.json 的 aliases/geometry 映射随 revision 无界增长（track_p01b：8.4MB→21.4MB 仅隔数小时使用）；建议映射分片（按 revision/feature 分文件）或快照压缩 |
| P1 | 全量注册表健康检查工具（列出各条目 actual_bytes，预警接近 16 MiB 的条目——第二名 hull 3.4MB 已在路上） |
| P2 | 核对 opened_session_model 在 Creo 10 的行为（§4.2） |
| P1 维持 | 会话擦除工具排期提醒 |

---

## 6. 复测方法

1. `creo_session_status` → 确认 0.4.5。
2. 当前窗口任意零件 → `creo_adopt_current_model(inspect)` → 复现结构化诊断（P02_HUOSAI_GAN 实测即触发）。
3. `creo_reconcile_model(inspect, model_id=c437cace0625425496fec62d8c14743a)` → 复现裸 16 MiB 错误（死锁证据）。
4. 文件系统只读核查：`models\c437cace…\model.json` 应为 21,472,751 B（未动）。

---

## 7. 亮点

- **结构化诊断一次到位**：本报告的根因定位（§3.2/3.3）完全是 0.4.5 诊断字段的直接产物——`metadata_kind: model_registry` + `path` + `failed_stage` 三个字段就把三轮悬案解开了。这个设计的投资回报已经兑现。
- recovery 指引的"不要删文件、不要提限额掩盖错误"纪律，引导验收方做了正确的只读诊断而不是绕过问题。
- release notes 与实机行为逐项对得上（本次唯一对不上的是 §4.2 的可选字段，已如实报告）。

*本文档由 AI 助手基于 2026-10-21 对 v0.4.5 的实测调用与注册表只读诊断整理。超限文件 `models\c437cace0625425496fec62d8c14743a\model.json` 依 recovery 指引原样保留，未做任何修改。*
