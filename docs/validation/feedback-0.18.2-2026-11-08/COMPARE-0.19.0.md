# v0.19.0 与 DEV-077 对比及合并记录

日期：2026-11-08；分支 `offline/0.18.2-feedback-gapfill`；合并提交 `006e357`。相关：[工作卡](../../work-items/DEV-077.md)、[逐项对照](MAPPING.md)、[刷新后的未完成清单](../../development/DEV-077-HANDOFF.md)、[离线验收](ACCEPTANCE.md)。

## 版本身份

- `v0.19.0` = 本地标签 `86020e7` = `origin/main`，共同祖先 `04927a9`（v0.18.4），相对本分支原 HEAD `4bd6b7e` 有 12 个 DEV-074 提交；`version.py` 合并后为 0.19.0。
- 0.19.0 版本说明（[RELEASE_NOTES_0.19.0.md](../../RELEASE_NOTES_0.19.0.md)）声明：新增 `creo_surface_round`、`creo_measure_surface_curvature`，解除门禁重新公开 `creo_quilt_merge`，公开工具 104→107；H10 五爪整瓶整链 46 作业 63 项检查 0 失败；钣金成形类、独立 quilt 偏置与任意非平面边界填充为**不可用结论**，门禁保持。
- 但发布记录 [RELEASE-0.19.0.md](../RELEASE-0.19.0.md) 第 10—12 节仍是「待主代理回填」占位（合入提交、Release 链接、远端附件核对），统一 POSTCHECK 也没有 v0.19.0 段。也就是说仓库本地有已发布 tag 与四附件摘要，**发布后核对尚未在台账回填**；见清单 R07。

## 合并操作

1. 先确认工作树含有另一 AI 的未提交改动（`bridge.py`、`generic_bridge.py`、`native/*.cpp`、`server.py`、`capabilities.py`、两个 `seed_manifest.json`、原生夹具与新 H13 测试），并核对它们与 0.19.0 官方文件并非简单复制：只有两个 `seed_manifest.json` 与 v0.19.0 逐字节相同，其余均为独立改动。
2. 备份：未提交状态/HEAD 记录、16 个未跟踪文件副本放在 `build/merge-0.19.0-20261108/untracked-cache/`；已跟踪改动用 `git stash push` 保存（引用保留，未 drop）。
3. `git merge --no-ff --no-commit v0.19.0`，3 个冲突：`docs/BACKLOG.md`、`docs/COMPATIBILITY.md`、`src/creo_mechdog/capabilities.py`；解决后提交 `006e357`。
4. `git stash pop` 恢复两方工作树改动，2 个冲突：`docs/BACKLOG.md`、`src/creo_mechdog/capabilities.py`；解决后 `git reset` 回到未暂存状态。所有原有未提交内容仍是未提交内容。

冲突取舍：

| 文件 | 取舍 |
| --- | --- |
| `capabilities.py` / `UNAVAILABLE_OPERATIONS` | 移除 DEV-076 的 `quilt_merge` 全局门禁（0.19.0 H03 已定位到目标 quilt 原地增长并实机通过），保留 0.19.0 恢复的 `surface_boundary_fill` 门禁 |
| `capabilities.py` / `surface_chain.limits` | 串联两方文案：DEV-076 的 overlap 采样预算回执（`overlap_area_mm2=null` 时给预算/覆盖率/包含错误） + 0.19.0 的 `surface_round` 恒定半径与 `creo_measure_surface_curvature` 数值分析限制 |
| `docs/BACKLOG.md` | 保留 0.19.0 发布入口与历史时点，叠加 DEV-077 登记；计数 168（BUG 75 / FEAT 61 / DEV 32） |
| `docs/COMPATIBILITY.md` | 当前已发布版本改为 0.19.0、0.18.4 标为「当时」，保留 DEV-076 的 Probbl.h 头门控补步说明 |

## 三方内容对比

| 内容 | DEV-077（本批） | 另一 AI（工作树） | 0.19.0 | 合并后 |
| --- | --- | --- | --- | --- |
| 四份 0.18.2 反馈原件/MAPPING/工作卡/验收/接手清单 | 有 | 无 | 无 | 保留 |
| RELEASING 第 8 步扩 DEV/BUG、DEV-075 逐 ID 行同步 | 有 | 无 | 未改（仍只写 FEAT） | 保留 |
| POSTCHECK v0.18.2 四附件回填 | 有 | 无 | 无 | 保留 |
| `tools/check_backlog_counts.py` + 业务模块 + 6+1 单测 | 有 | 无 | 无 | 保留 |
| `mass_properties.py` 冲突回执有界诊断 + 单测 | 有 | 无 | 无 | 保留 |
| `native_stage.py` / `bridge.py` 回退 `result.verify_stages` | 有 | 无 | 仍 `stall_report(directory)` | 保留 |
| H13 worker 条件可用性（`WORKER_CONDITIONAL_OPERATIONS` / `project_worker_availability` / `worker_build_identity`） | 无 | 有 | 无 | 保留（自动合并 + 一处手工） |
| overlap 采样预算回执（原生 C++ 与夹具） | 无 | 有 | 无 | 保留 |
| `seed_manifest.json` 的 `compatible_server_version=0.19.0` | 无 | 有 | 有（逐字节相同） | 无差异 |
| `creo_quilt_merge` 解禁与三级 quilt 归属解析 | 无 | 无 | 有 | 采用 0.19.0 |
| `creo_surface_round` / `creo_measure_surface_curvature` | 无 | 无 | 有 | 采用 0.19.0 |
| H10 五爪整瓶整链实机证据、非平面 fill/offset/钣金不可用结论 | 无 | 无 | 有 | 采用 0.19.0 |

DEV-077 的离线成果与 0.19.0 **没有重复实现**，全部保留；0.19.0 的新能力和证据全部引入；另一 AI 的独立改动也全部保留。

## 对原未完成清单 G01—G13 的覆盖

| 编号 | 0.19.0 后的状态 |
| --- | --- |
| G01/G02/G03 草图容差链、旋转矩阵、任意平面 | 0.19.0 未涉及，仍待办（R01） |
| G04/G05/G08/G10 mirror、契约示例/轮询、known_limitations、loft callback | 0.19.0 未涉及，仍待办（R02） |
| G06 session_health 语义 | 0.19.0 未涉及，仍需先定安全策略（R03） |
| G07 quilt_merge 门禁与合并语义 | **大部分闭环**：门禁解除、两片 JOIN 目标 quilt 解析、2 mm thicken 与保存重载实机；剩余 INTERSECT、三片以上单次合并、被消耗工具 quilt 内核残留、Creo 9/10（R04） |
| G09 曲面工具链 | **部分闭环 + 部分改判**：新增 round / 数值曲率、H10 整链闭合壳与 0.3/2 mm 加厚；非平面边界 fill、独立 quilt 偏置、钣金成形类已由 0.19.0 实机判为不可用并保持门禁，不再作为实现目标（R04/R05） |
| G11 实机/黑盒 | 0.19.0 在 Creo 12.4 做了大量实机，但 Creo 9/10、WorkBuddy 黑盒、源码包解压单测以及本分支新增的 H13/overlap/DEV-077 修复仍未验（R06） |
| G12 远端核对 | 新增 v0.19.0 缺口：POSTCHECK 无 v0.19.0 段、`RELEASE-0.19.0.md` 第 10—12 节仍占位（R07） |
| G13 本分支发布流程 | 不变：本分支仍未合 main、未发布（R08） |

刷新后的清单以 [DEV-077-HANDOFF.md 的 R01—R08](../../development/DEV-077-HANDOFF.md) 为准。

## 合并后验证

- `python -m unittest discover -s tests`：**3065 项 OK**（496.992 s，exit 0；日志中的 v9.9.9 附件不全、`--reps must be at least 1`、Creo startup、live runs、asyncio 慢回调均为既有测试夹具/负例输出）。
- `python -m ruff check <14 个合并涉及的 Python 文件>`：`All checks passed!`；`git diff --check` exit 0。
- `python tools/check_backlog_counts.py` exit 0：168（75/61/32）、分类 168、无重复。
- 双方关键字均可在合并后源码检索到：`verify_stages` / `timing_source`、`density_source={source}`、`WORKER_CONDITIONAL_OPERATIONS` / `project_worker_availability` / `worker_build_identity`、`surface_boundary_fill` / `surface_round` / `measure_surface_curvature` / `quilt_merge`。

未测：本轮未连接 Creo、未重新编译原生执行器（合并后 C++ 同时含双方改动，需 MSVC + Creo SDK 重建）、未跑 WorkBuddy 黑盒、未联网核对远端 Release、未跑源码包解压后的全量分发回归。
