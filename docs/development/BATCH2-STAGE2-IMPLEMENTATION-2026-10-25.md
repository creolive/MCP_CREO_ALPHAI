# 0.5.0 反馈第二批第二阶段：配套实现与离线验收证据

日期：2026-10-25。条目：DEV-046 第二批、FEAT-008（0.5.0 反馈第二批配套）、
FEAT-012/BUG-045 配套、FEAT-048 锁顺序修复。阶段范围：官方装配重建管线
示例与说明、source_snapshot 语义、组件变更摘要、list_components 约束符号名、
FEAT-048 昂贵选择前取锁、实机驱动与 WorkBuddy 场景文档、guard-root 开发者
实机入口（仅准备）；不含实机/WorkBuddy/发布，不连接 Toolkit、不故障注入、
不结束或重启 Creo、不清保护或旧作业、不改客户端配置与 main 工作树。本文件
为新增证据，历史 docs/validation 原件逐字节未改写。

## 源码与版本身份

- 工作区：`E:/Projects/md050`；分支 `codex/feat012-matrix-pipeline`；
  源码版本 0.5.3（未变更、未发版）。
- 行为提交：`def2cf1` “FEAT-008/012/048 batch-2 stage-2: pipeline examples,
  change summary, constraint names, lock-order fix, drivers, guard entry”，
  29 文件、+1969/-37。提交后工作树干净。
- 最终 dev_check 受测身份：commit `def2cf1c42903287afd94fa77d83371bfdc8b362`，
  dirty=false，checked_source_sha256
  `5f922c61c5b5405ee003b0b4372693241a1572c7be1f097915880c5b72f646df`。
- 未 amend/rebase/reset --hard/clean/stash；未 push、未合 main、未发版；
  `E:/Projects/MCP_CREO_MechDog` 未触碰。

关键受测文件指纹（LF 归一化 SHA256，提交 def2cf1）：

| 文件 | SHA256 |
| --- | --- |
| src/creo_mechdog/file_adoption.py | b7a23f9b36b326c0a5ff7544d838e5c4a3a8183e3a8e32fc1287a253ea4e08f7 |
| src/creo_mechdog/component_changes.py | 543fc87774ca975d3ef6939f673e476653dbb56b2958c9a3fc4f0c4fe99fd89b |
| generic_bridge.py | cd98e8a91b14ecca9089451a7ef54aba0478a5df9aa00e219d267ef96a4ef4f0 |
| native/constraint_names.h | af97b99c431029fecc90b2df6c76107093e293160d14b1708fe610f296bac652 |
| native/advanced.cpp | 7beb07d61b2fd27cc90482694ac3918e95b53a5fa1ea938156e762f489cebfd9 |
| native/generic.cpp | c2d1f48b956bda80a46bb8e88595ec9fc99e147339e6e913cf2af434bf1d4ec3 |
| server.py | 80e95eff74cbb61fca20fd6577428d13d73d1ab122f2a0ac5c97d3b2d43b0889 |
| src/creo_mechdog/schema.py | aafd10d9f923f638e4cfac652adaafe258b1cb2e27cad81d7d04acae67bbf7ab |
| tools/guarded_live_run.py | 18f33ec75c88faa65a0439d9ce18687ce6ae7252acc7cb40c7e4e59422865dd8 |
| tools/test_assembly_pipeline.py | a74b4f33ec3f30e47b963f7f72011fdc0385a1656110f38e3ef4ee2504c86668 |
| tests/unit/test_file_adoption.py | e5d623b99cf18f0a62777147aab8df7893c3814824c4e7f8e4efac36c0996d8a |
| tests/unit/test_component_changes.py | f7a0874d0ff808363ebca4c29382e1433d594e40ccadb2caa56c8e867841a596 |
| tests/unit/test_guarded_live_run.py | 50080bba2803aace81e437783117b65e71409de5b2a91d0196a4a7402a5cc60a |
| tests/unit/test_assembly_examples.py | 5684c02fb5bc0ad580cbd58c2aa8188b0bb1539dae8fb637f2eacb14f374aa9d |
| tests/native/test_constraint_names.cpp | 0d2391b3112391ee50c765643703481b3f828d9b19fb9a6c51d2a824e59961b9 |

## 实现内容

1. **FEAT-048 锁顺序（上游复审追加）**：新 `inspect`/`apply` 在昂贵逐文件
   选择/哈希（`_select`，每件可能数秒）之前取得非阻塞通道锁；廉价 schema
   校验（键、token 格式）仍在锁前；已知幂等回放保持忙时只读返回并维持既有
   路径/identity/token 绑定契约（回放仍执行 `_select` 绑定身份）。无排队/
   重试，幂等语义不变。
2. **组件变更摘要**：含组件操作的 generic 作业 manifest 增加有界
   `component_changes`：committed（真实原生 feature_id；added 含
   source_model_id/source_revision；moved 含受管检查查询矩阵 from/to；
   removed/constraints_changed 按既有别名解析 label）/ rolled_back（仅请求
   意图，明确未生效）/ unknown_outcome（空清单 + 保护指引）。值取自原生
   操作结果、受管别名与已验证检查；Python 不模拟几何；现有结果字段兼容；
   复用现有 preview.jpg，无同义批量装配工具。`src/creo_mechdog/component_changes.py`。
3. **list_components 约束符号名**：`native/constraint_names.h` 统一
   FEAT-045 会话装配（generic.cpp `constraint_json`）与受管组件清单
   （advanced.cpp `inspect_constraints`）映射；数字 `type` 保留，新增
   `type_name`（本机 SDK 枚举 static_assert 钉住数值，如 13→"fix"）；未知码
   保留数字并输出 `"unknown"`，不猜测含义。
4. **FEAT-008 官方管线**：`examples/assembly_rebuild_pipeline.json`（八步：
   检查原装配→按路径收养→新建托管装配→单 execute_plan 多组件→统一保存
   重载→回读验证→快照再生成）、`examples/assembly_multicomponent_plan.json`；
   `docs/ASSEMBLY_REBUILD.md` 说明（毫米行向量约定、不重用 raw 矩阵、
   source_snapshot 语义与再生成方式、摘要/type_name 用法、开发者入口）；
   `docs/WORKBUDDY_FEAT008_PIPELINE.md` 纯 MCP 场景。
5. **实机驱动**：`tools/test_assembly_matrix.py`（补真实普通失败回滚、
   type_name 断言、唯一报告目录）、`tools/test_file_adoption.py`（provenance
   与拒绝原因断言、唯一报告目录）、新增 `tools/test_assembly_pipeline.py`
   （单作业多组件、预览/摘要/符号名、快照语义与再生成）。本轮新建隔离
   夹具，不动历史保护模型；仅编写待用，未运行。
6. **guard-root 开发者实机入口**：`tools/guarded_live_run.py`——最外层以
   `bridge.toolkit_lock` 局部绑定 ROOT 持 `E:\Projects\MCP_CREO_MechDog` 的
   真实通道锁，再顺序运行 md050 MCP/native 测试子进程；内部 md050 继续持
   自有锁；锁忙即停（exit 2，报告含 guard 根 owner 快照），不排队/重试/
   清旧 owner；guard 覆盖子进程完整生命周期（子驱动轮询到终态后才退出）；
   报告含父/子源码身份。不引入生产配置 API，不改生产锁机制。

## 命令与结果（环境：Windows 11 x64 / Python 3.12.14 / Creo 12.4 匹配 SDK / MSVC x64）

| 命令 | 结果 |
| --- | --- |
| `git commit`（行为批） | `def2cf1`，29 文件 +1969/-37；树干净 |
| `.\.venv\Scripts\python.exe bridge.py build`（提交后源码） | exit 0；worker SHA256 `7c653a1d9df1b0421a0d69e181683fc9e10e787948c7e4a869fe3cac61571402`（既有 C4819 代码页警告，无错误） |
| `.\.venv\Scripts\python.exe tools\test_constraint_names.py` | success=true；13 组符号 + 未知码nullptr + fallback 枚举 static_assert；`build/constraint_names_test/report.json` |
| `.\.venv\Scripts\python.exe tools\test_assembly_pose.py` | success=true（11 组姿态/基向量/已知点不回退） |
| `.\.venv\Scripts\python.exe tools\test_adoption_source.py` | success=true（12 项 source-state 检查不回退） |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_file_adoption -q` | 32 项通过（29 既有 + 3 新增 busy 锁序回归） |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_changes -q` | 10 项通过（纯契约 6 + run_generic_job 挂载 4） |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_guarded_live_run -q` | 3 项通过（持锁期间子进程实测 busy、busy 停、失败子停止但释放） |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_assembly_examples -q` | 3 项通过（示例参数经真实 schema 校验） |
| `.\.venv\Scripts\python.exe tools\dev_check.py`（提交后干净树） | success=true；666 项单测 0 失败 0 错误；lint/unformatted 在既有基线内（31/19，未重建基线）；`build/development_check.json`、`build/unit_test_report.json` |

新增公开字段：`component_changes`（作业 manifest 层）；组件约束
`constraints[].type_name`（list_components）。现有字段不变。

## 未测范围

无 Toolkit 连接、无实机建模、无 WorkBuddy 黑盒（按本阶段限制）；矩阵实际
放置/查询、批量收养窗口/源字节、管线快照语义均待实机；unknown/并发 busy
只保留离线/文档契约，未注入；Creo 9/10 未测；实机入口 guard 方式未在真实
主工作树演练（仅临时目录离线回归）。第三阶段（约束回放 FEAT-049、比对
FEAT-050、世代回收 DEV-027）与 FEAT-012 显式源件更新/嵌套装配未实施。
