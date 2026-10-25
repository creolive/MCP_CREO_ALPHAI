# 0.5.0 反馈第二批第一阶段：保全、整合与复审离线证据

日期：2026-10-25。条目：DEV-046 第二批、FEAT-048、FEAT-012/BUG-045。阶段范围：保全
已有暂存、整合 main、复审修复、离线证据；不含 FEAT-008 配套、实机/WorkBuddy 与
发布。本文件为新增证据，历史 docs/validation 原件逐字节未改写。

## 源码与版本身份

- 工作区：`E:/Projects/md050`（唯一工作树；未触碰 `E:/Projects/MCP_CREO_MechDog`）。
- 分支：`codex/feat012-matrix-pipeline`；源码版本 0.5.3（随 main 整合）。
- 保全提交：`d563958`，标题 “FEAT-048 preserve path and batch adoption implementation”，
  tree `08ba93a34409f539145686ea91541ce34fb34102`，与保全备份
  `E:/Projects/md050-preservation/20261025-165659` 的 index tree 一致；21 文件、
  1614+/21-，提交后工作树干净。备份（git bundle verify 通过、manifest、
  preflight、review-findings）未删改。
- 整合提交：`85d5178`，`git merge origin/main`（b5ad5d5，0.5.3）。唯一冲突
  `docs/BACKLOG.md` 两处：页头版本事实与状态计数表。两处均取 main 侧——0.5.3
  定版事实与计数（验收中 28、待开发 2、共 118）为最新台账口径，与自动合入的
  总数行一致；第二批逻辑由 DEV-046 行与 FEAT-048 卡承载。未 amend/rebase/
  reset --hard/clean/stash；未在 main 提交/推送/发版。
- 修复提交：`01a4cd8` “FEAT-048 reject busy inspect without job artifacts”
  （src/creo_mechdog/file_adoption.py、tests/unit/test_file_adoption.py、
  docs/work-items/FEAT-048.md）。
- 本证据提交：随 FEAT-012.md 复审记录一并提交（docs-only）。
- dev_check 受测身份：commit `01a4cd83f6e8dd57b02ab8a7ae52558c864cce27`，
  dirty=true（仅 docs：FEAT-012.md 复审记录与本证据文件，不影响受测代码），
  checked_source_sha256 `a35615674789dc5420e0db017f25458cb2f520cc203fdeb675d526a9a8b4d78f`。

关键受测文件指纹（LF 归一化 SHA256）：

| 文件 | SHA256 |
| --- | --- |
| src/creo_mechdog/file_adoption.py | 83a58af40f640b6d2a407a264165d46c81baa89f4a8f3884bbe9fa2f40479f61 |
| src/creo_mechdog/schema.py | aafd10d9f923f638e4cfac652adaafe258b1cb2e27cad81d7d04acae67bbf7ab |
| native/assembly_pose.h | 73ce38218dd29afd88e2f57e686a2b361086912554421b89b781bccd9f6ba5de |
| native/adoption_source.h | 6e939a152ee1489b8c366fdec57268456adcec4352e0a54240db5570c11d6ff2 |
| native/generic.cpp | 7a26194c20481c1b0e8b009f6a9096462fd8373c4712fc8a035da99c91793d00 |
| server.py | 5acaa50152669dcc692472ec0f907638cc09be7ed5bdc5cf7ef3ebc8e9370be4 |
| bridge.py | f1747c5f4d8b5e99d872e69df8120882bc9ee9d4dc312e4a1f5e05802e640180 |
| tests/unit/test_file_adoption.py | 38405571bcb93e3f9c4af73a29e6205d40a4ac6664698b85c36b83ef41e38bb4 |

## 复审发现与处理

1. FEAT-048（上游 review-findings.json 已确认，本地在合并树复现一致）：
   `inspect` 在 `toolkit_lock` 获取前创建 parent 作业目录并发布 running 清单；
   通道忙碌时 `ToolkitBusy` 拒绝受理却遗留 1 个 `adoption_file_inspect`/`running`
   孤儿目录（native_calls=0），违反“忙碌拒绝不接受作业”契约。修复：parent 目录
   创建与首次清单发布移入锁内；修复后复现脚本确认 new_job_dirs=0、
   evidence=0、intents=0、models=0、native_calls=0。回归：新增
   `test_busy_inspect_rejects_without_any_job_artifact`，并强化
   `test_busy_submission_rejects_without_acceptance` 补目录/evidence/intent/model
   计数断言（apply 路径复查确认目录创建于锁内，无泄漏，回归锁定）。
2. FEAT-012/BUG-045：独立复核创建/更新组件与 execute_plan 矩阵管线。Python
   `_rotation_matrix` 与原生 `assembly_pose.h` 双侧的形状、有限实数（拒
   bool/字符串/NaN/Inf）、1e-6 正交与行列式 +1、Euler 互斥与省略兼容、行向量
   局部到父级 p_parent=p_local*R+t 均一致；校验先于提交锁与副作用；根
   `schema.py` 与包内共享同一类型。未发现需修复缺陷。
3. FEAT-048 其余重点复查（令牌时效/路径内容顺序与源会话绑定、幂等回放、重复
   来源、既有保护、逐项 durable commit、普通失败继续、unknown 停止保留保护、
   metadata-only 恢复不重跑原生、终态锁外发布、生命周期预算、native 驻留源
   选择与窗口/源只读守卫）与既有单测覆盖一致，未发现新缺陷。

## 命令与结果（环境：Windows 11 x64 / Python 3.12.14 / Creo 12.4 匹配 SDK / MSVC x64）

| 命令 | 结果 |
| --- | --- |
| `git commit`（21 暂存文件） | d563958；tree=08ba93a3… 与备份一致 |
| `git merge origin/main` | 85d5178；BACKLOG.md 两处冲突按 main 侧解决 |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_file_adoption tests.unit.test_assembly_pose -q` | 通过（35 项；file_adoption 29 含新增 busy 回归，assembly_pose 6） |
| `.\.venv\Scripts\python.exe tools\test_assembly_pose.py` | 通过：11 组 Euler/矩阵姿态、基向量/已知点/逆映射、容差保留与非法输入 |
| `.\.venv\Scripts\python.exe tools\test_adoption_source.py` | 通过：12 项 source-state 收养检查 |
| `.\.venv\Scripts\python.exe bridge.py build` | 成功，exit 0；worker SHA256 `890bfa018bbd657023822da2fe5259f781e22dd86bbbef78718dcce924f5bd35`（既有 C4819 代码页警告，无错误） |
| `.\.venv\Scripts\python.exe tools\dev_check.py` | success=true；647 项单测 0 失败 0 错误；lint/unformatted 均在既有基线内，未重建基线；日志 `build/batch2-stage1-devcheck.log`、`build/development_check.json`、`build/unit_test_report.json` |

## 未测范围

无 Toolkit 连接、无 Creo 实机建模、无 WorkBuddy 黑盒（按本阶段安全限制）；
FEAT-048 实际窗口/源字节保留、原生健康/单位/依赖守卫、保存重载/revision、
fresh/resident 选择，FEAT-012 实际放置/查询/revision/保存重载均未验证；Creo 9/10
环境未测；`tools/test_file_adoption.py`、`tools/test_assembly_matrix.py` 为后续许可
场景脚本，非本次证据。第二批 FEAT-008 官方流程、source_snapshot 说明、组件摘要与
约束符号名，以及实机/WorkBuddy/Release 安排为后续阶段。
