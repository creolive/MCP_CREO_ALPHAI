# B01 契约：共享多模型事务与骨架受管身份（P00 后续冻结）

日期：2026-11-03。分支：`codex/FEAT-059-skeleton-transaction`，基线 `376cdbd`。**本轮不连 Creo**，按用户授权只交付离线可判定部分。

## 一 已冻结：共享多模型事务（`src/creo_mechdog/model_transaction.py`）

B01 唯一拥有该模块，B02、C04 依赖它，因此先冻结并使用：

```python
prepare_model_transaction(model_ids: list[str], expected_revisions: dict[str, int], *, root: Path | None = None) -> dict
finish_model_transaction(transaction_id: str, native_result: dict, *, root: Path | None = None) -> dict
load_transaction(transaction_id: str, *, root: Path | None = None) -> dict
```

- **日志位置**：`<data_root>/transactions/<transaction_id>.json`，原子写（临时文件 + `os.replace`）。它是项目日志，**不是**文件系统事务，也不新增任务排队状态。
- **阶段**：`prepared` → `native_saved` → `registry_committed` | `recovered` | `recovery_required`。
  `recovered` 为本轮对主计划四阶段表的**补充**：失败但每个模型的恢复都被原生证实；`recovery_required` 表示至少一个模型状态未被证实（继续保护、日志保留）。
- **`native_result` 形状（冻结）**：
  ```python
  {"models": {model_id: {"saved": bool, "verified": bool, "revision": int | None, "checkpoint": str | None}},
   "rollback": {"verified_models": [model_id...], "unproven_models": [model_id...]},
   "registry": {"published": bool, "error": str | None}}
  ```
- **不可让步的两条**：
  1. 检查点只在整笔事务成功后才推进；失败时保留旧检查点，新的只作证据记录，`published` 恒为 false。
  2. 未证实的模型记 `rollback="not_attempted"`/`"unproven"`，**永不**出现 `rolled_back`；未证实的模型全部进入 `protected_models`。
- **幂等**：终态事务重复 `finish` 返回同一记录并带 `idempotent=true`，不重复提交子模型。
- **拒绝前置**：空模型集、重复 id、缺/多 `expected_revisions`、布尔或负 revision、非法 transaction id 一律在写盘前抛 `TransactionError`（测试断言磁盘上无残留）。

离线证据：`tests/unit/test_model_transaction.py` 9 项，含主计划点名的 6 项（`test_parent_child_identity_commit_together`、`test_second_save_failure_protects_all_models`、`test_registry_publish_failure_has_recovery_record`、`test_old_checkpoint_not_replaced_before_success`、`test_unknown_never_reported_rolled_back`、`test_repeated_request_not_duplicate_child`）；`tools/dev_check.py --work-item FEAT-059-skeleton-transaction` → `success=true`、`unit_tests=passed`。

## 二 未交付：标准骨架创建与受管身份

B01 步骤 1 要求**会话负责人**在隔离空受管装配里完成创建、抽取、保存重载与父装配回读，交付真实元素树、身份与失败码；本轮无会话窗口，故：

- `creo_create_skeleton` / `inspect_skeleton_binding` 两个入口**未注册**（不开放未经验证的公开写入口）。
- `native/skeleton_models.{h,cpp}` 与 `skeleton_models.py` **未创建**：骨架类型判定（`ProMdl` 子类型/API 骨架标志）、模板来源、父子绑定持久化方式都依赖该探针结论，先猜会做出“按名字认骨架”的错误实现（设计文档明确禁止）。
- 待办顺序：① 离线核 SDK 中骨架相关 API 与许可 → ② 隔离装配探针（创建/抽取/重载/父装配回读）→ ③ 冻结元素树与身份 → ④ 再实现受管创建与查询。

## 三 未启动：B02 骨架长宽关联

B02 依赖 **B01 受管绑定** 与 **A04 平面壁真实尺寸身份**，两者都未通过，按 Global Constraints 只允许离线调查。本轮未写 `skeleton_links.py`、未改 `RelationsOp` 分发、未新增 `creo_link_skeleton_dimensions`。

## 四 与主计划 P00 契约的衔接

- 事务契约是 `ALPHAI-ADOPTION-CONTRACT.md` 中“B01/B02 未冻结”一项的落地；A01、D03 可复用本事务日志（A01 单模型也应走同一记录，避免两套收尾语义）。
- 集成次序不变：A02 → A03 → A01 → B01 → B02；B01 的写入口必须等实机探针通过后才注册。
