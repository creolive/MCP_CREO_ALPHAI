# 第二批第五阶段：committed 摘要组件筛选修正（2026-10-25）

范围：用户从 stage-4 最终源码确认的一项残余缺陷的最小修复。仍不连接
Toolkit、不故障注入、不改客户端配置、不结束 Creo/worker、不清 unknown
保护、不合并不推送、不改版本、不发布。stage-1/2/3/4 已发生的测试事实与
历史 `docs/validation/` 原件未改写；本文件为独立新证据。

环境：Windows 11 x64 / Python 3.12.14 / 本机 Creo 12.4.0.0 匹配 Toolkit SDK
（仅离线编译）/ MSVC x64。工作树：`E:/Projects/md050`，分支
`codex/feat012-matrix-pipeline`，基准 HEAD `73a8ea2`（stage-4 收口证据提交）。

## 复现

`component_changes._committed_changes` 的净摘要循环此前遍历
`sorted(set(prior_aliases) | set(result_aliases))`，把别名表里的**任何**
别名都当作组件。generic 别名与组件共用同一别名表（原生 `remember` 为
datum_plane/sketch/extrude 等同样写 `aliases[label]`），因此同一 assembly
作业既有 component 操作又新增 datum 时，datum 别名被误报为
`component_changes` 的 `added`（`source_model_id=None`），源码可证。

## 修复（`src/creo_mechdog/component_changes.py`，仅此一文件 + 测试 + 文档澄清）

- 新增 `_component_labels`：受管 label 仅在原生别名记录
  `op="assemble_component"`（原生 `remember` 必盖 op 章）或其
  `feature_id` 属于已验证检查 `inspection.components` 的真实组件 id
  时才计入前后集合；通用别名（datum_plane/sketch/extrude 等）一律排除。
- 无别名原生组件：以真实检查 `feature_id` 进入（`label=null`），身份
  只来自 inspection，绝不编造 id。
- 现有语义保留：真实 feature_id 净 added/removed/moved/
  constraints_changed；同 label 双身份（重插旧 removed + 新 added）；
  add+move 收敛为 added；add+remove 无净变更；连续 move 单次净移动；
  缺已验证结果别名仍降级 unavailable。
- 附带（同源缺陷面）：约束比较新增 `_constraints_view`，剔除仅展示的
  `type_name` 符号（与原生 `constraint_compare.h` 一致）——旧数字-only
  检查点不因新增可读符号误报 `constraints_changed`；数字 type、offset、
  refs、sides 与数量/顺序仍全量对比。未重构管线或 guard。

## 回归（`tests/unit/test_component_changes.py`，32 项，新增 7 项）

- 混合作业：assemble_component + 新 datum_plane 别名 → 只报组件 added，
  datum 不出现；move + 新 datum → 只报净 moved。
- 仅 datum 作业（无组件操作）→ summarize 返回 None（原有语义）。
- 作业前已存在且存活到作业后的 datum 别名不被 diff 成组件。
- 无别名原生组件以真实 feature_id 列入（label null，不造 ID）。
- 约束：旧数字-only + 新 type_name → 无 constraints_changed；真实 offset
  变更 → 仍报 constraints_changed。
- 两项既有用例按原生真实形状补齐组件身份（prior_inspection 含该组件）。

## 验证命令与结果（全部离线）

- 定向回归：`.\.venv\Scripts\python.exe -m unittest
  tests.unit.test_component_changes`：32 项 OK。
- `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-008`：
  exit 0，success=true，unit_tests=passed；全量 708 项，0 失败 0 错误
  （stage-4 为 701 项，新增 7 项），186.5 s；未修改 style baseline
  （lint_findings 31、unformatted 19 均为存量，2 个变更文件已按项目格式化）。
  报告 `build/development_check.json`（唯一最新）；日志
  `build/feat008-stage5-devcheck.log`。
- 无 C++ 变更：worker `E:\Projects\md050\build\creo_worker.exe` SHA256
  `4d969376a0f00f973d157eb677db817dcae97d775d435cc2acb22e09820a4971`
  与 stage-4 逐字节一致，未重复 SDK 重编与 4 helper。

## 源码身份（最终，见提交记录）

变更源指纹（SHA256，工作树最终态）：
`src/creo_mechdog/component_changes.py`
`79ee4f5043dc737496e37615f27ebf07ebccb6f7dabb4a2d410160e97d47627e`；
`tests/unit/test_component_changes.py`
`aff408ed5588ef09da2d133d8d568101630a2f86e04855dad68d776f093c2d94`；
`docs/ASSEMBLY_REBUILD.md`
`beb9595a5a59f8f1d8f0b0786aee561e7156e2ee03f1cd2bb10f38c5dcd99fc5`。

## 未测范围

- 实机 Creo 行为：未连接 Toolkit（遵守 BUG-001 会话约束）；本修正的
  混合作业实机表现留待统一安排。
- WorkBuddy 黑盒：未执行。
- 并发交错、unknown 恢复不在本轮。
- 这些修复完成不等于交付：合入 main/版本/Release 未发生。
