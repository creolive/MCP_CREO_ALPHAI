# 第二批第三阶段：复审收口修复与离线再验证（2026-10-25）

范围：0.5.0 反馈第二批（FEAT-008/012/048、DEV-046）上游逐段读码复审确认的六项
缺陷的最小修复。实机/WorkBuddy 仍待统一安排，本轮不连接 Toolkit、不故障注入、
不改版本、不合并不推送。历史 `docs/validation/` 原件与 stage1/2 已发生的测试
事实未改写；本文件为独立新证据。

环境：Windows 11 x64 / Python 3.12.14 / 本机 Creo 12.4.0.0 匹配 Toolkit SDK
（仅离线编译）/ MSVC x64。工作树：`E:/Projects/md050`，分支
`codex/feat012-matrix-pipeline`，基准 HEAD `1c13654`（ahead 7 / behind 0，
干净起步）。

## 1. 旧装配约束记录不兼容（真实生产缺陷）

复现：`native/advanced.cpp` `inspect_constraints` 新增展示性 `type_name`
（`{"type":13,"type_name":"fix"}`），而 `native/generic.cpp` `verify_saved`
（约 2007 行）对 `constraints` 整段 JSON 严格比较；旧保存检查点只有
`{"type":13}`，旧装配任何后续编辑被误报 "Saved assembly constraints changed"。

修复：新生产 helper `native/constraint_compare.h`
（`mechdog_constraints::verification_view` / `match_for_verification`）只把
展示性 `type_name` 从兼容比较中投影掉；数字 `type`、offset、assembly/
component 引用、datum side、数量与顺序全部保留严格校验；不改写旧记录、不跳过
约束验证。`generic.cpp` 该比较点改走 helper。映射仍以 SDK 枚举为准（数字码保留，
`constraint_names.h` 不变）。

离线回归（生产 helper 真实编译运行，无 SDK、无 Creo）：
`tools/test_constraint_compare.py` → `tests/native/test_constraint_compare.cpp`：

- 复现断言：旧检查点 `!=` 新查询（严格比较误报），helper 判等价（双向）。
- 通过：旧→新、新→旧、`unknown`→具名符号、仅 type_name 差异。
- 拒绝：数字 type 变化、offset 改/删/变 null、引用 id/owner 变化、side 变化、
  新增字段、数量变化、顺序交换、unknown 码数字变化、畸形载荷（null）失败关闭。
- 结果：build exit 0、run exit 0，报告 `build/constraint_compare_test/report.json`。

## 2. 变更摘要不得编造回滚

复现：`src/creo_mechdog/component_changes.py` 对一切 `job_status != succeeded`
一律输出 `rolled_back`；`generic_bridge` 的 ToolkitBusy 拒绝、worker 未启动等
分支并无任何回滚证据，摘要编造回滚。且摘要异常会使已登记成功的作业在
`job.json` 停留在 `running`（异常发生在终态写盘之前）。

修复（`component_changes.py` + `generic_bridge.py` + `bridge.py`）：

- 状态按证据区分：`committed`（成功）；`rolled_back` **仅当**原生结果
  `rollback_succeeded=true`；`no_effect`（busy 拒绝/worker 未启动，或原生
  `model_unchanged=true` 预检拒绝）；`unknown_outcome`（结果未确认，或执行后
  失败但回滚未确证）；摘要构造异常输出 `unavailable`，作业已确认终态保持权威。
- `generic_bridge.run_generic_job` 传入原生 `result` 证据与 `worker_started`，
  摘要包 try/except，异常只标记 `unavailable` 后继续正常收尾（`finished_at` +
  持久化终态不再丢失）。
- 同 job 内 remove+reinsert 同 label：`removed` 用作业前别名旧 feature_id，
  `added` 用结果别名新 feature_id（新增回归锁定）。
- `bridge.compact_job` 白名单纳入有界 `component_changes`（compact/full 一致，
  可发现性明确）；`capabilities.py` assembly 说明同步。

回归：`tests/unit/test_component_changes.py` 16 项通过（新增 busy→no_effect、
model_unchanged→no_effect、执行后失败无回滚证据→unknown_outcome、
remove+reinsert 双身份、summary 异常→unavailable 且终态/指纹不变）。

## 3. guard-root 异常收尾（真实安全缺口）

复现：`tools/guarded_live_run.py` 仅在 `finally` 退出 main 锁，假定
“driver 退出=全部 accepted jobs 终态”；driver 断言/超时/协议异常提前退出时，
MCP runner 仍在后台，旧 main 服务随后可能与 md050 同时接 Creo。原说明把
“子进程退出前必终态”写成已验证保证，已修正。

修复（仍是测试入口局部桥接：不引入生产锁 API/队列/公平调度；busy 入口
exit 2 不运行任何子命令）：

- 启动前记录 md050 作业基线集与唯一报告目录。
- 每个子进程结束后、以及失败/异常后，在持 main guard 期间：只轮询本轮新增
  作业目录的 `job.json` 到终态（不提交/不重放/不新建 Toolkit 连接/不结束
  Creo/不清保护），并用非阻塞字节锁探针确认 md050 通道静止；全部终态且探针
  空闲才释放 guard。
- 发现 `unknown_outcome` 或预算内无法证明静止：停止后续子进程、不清理 guard
  owner 证据、md050 保护原样保留、exit 3 并明确报告“未证明可安全释放”，
  不声称安全。
- 修复过程中发现并纠正两个实现缺陷：(a) 持 guard 期间 `bridge.ROOT` 被绑定
  为 guard root，settle 必须显式传 md050 路径；(b) 轮询循环内作业状态需刷新。
- `--settle-timeout` 可调；`--help`/参数解析离线核对通过；按路径直接运行
  （`python tools/guarded_live_run.py ...`）补 sys.path 引导后可用。

回归：`tests/unit/test_guarded_live_run.py` 7 项通过，覆盖：子进程退出 0 但
作业仍 running（后台终态化后 guard 等待并释放）、unknown 保留 reservation
且后续 driver 未运行、失败子进程遗留作业仍先 settle 再释放、子进程结束后
md050 通道仍被占用时 exit 3 不声称安全。

## 4. 管线实机驱动修正（tools/test_assembly_pipeline.py）

复审缺陷与修正：

- 原把 MCP 刚创建的托管输出（`result.part_file`）直接送 `creo_adopt_file`，
  `adoption._origin_conflict` 会以 `managed_output` 拒绝，驱动不可能
  `all_adopted`。修正：本轮新建夹具——由 MCP 创建两个唯一命名零件（验证
  保存重载与 SHA256）后，把字节复制到独立、唯一命名、非托管输出目录
  `build/assembly_pipeline_external_<tag>/`（文件名含 timestamp+uuid；校验复制
  字节与受管输出 SHA256 一致；置只读；记录外部源 SHA）。此后源只读；原受管
  文件与登记不动；准备动作发生在任何收养受理之前，不算“源被修改”。
- 快照场景原编辑 `source_a`（装配实际引用的是收养副本）。修正：编辑
  **收养的 source_model_id**，并真实改变几何——凸台 [20,-5]-[30,5] 深 6，
  超出原体 -20..20 包络（旧版 [10,10] 深 2 完全在体内），体积 +600 mm³ 可核。
- “装配 revision 不自行推进 / 缓存≠实时几何”：源编辑后先确认装配缓存不变，
  再显式 `{"op":"regenerate"}` 作业按 revision+1 取得新的保存重载原生数据，
  证明体积仍是旧快照；随后 remove+reinsert 当前收养源（其当前 revision），
  保存重载后体积 = 旧值 + 600，新副本名/位姿/引用重查。
- 重建场景原为两个独立示例而非验证。修正：原夹具即含重复 occurrence 与非对称
  组合旋转（ROT_COMBINED，det +1）；用 `creo_inspect_session_assembly` 读出的
  归一化毫米 `transform_to_parent`（`transform_mm_known` 为假即停）逐 occurrence
  建立新装配，来源映射按快照副本名→label→source_model_id；最终组件数、逐
  occurrence 位姿（1e-6）、已知点映射、重复 occurrence 共享 source_model_id、
  整装配体积全部对上冻结快照；不用 raw 矩阵、不自动转置。
- 收养独立性反证：编辑收养模型后受管原件 revision/体积不变（若收养别名到
  受管原件此断言必失败）。
- 全部 fixture 名唯一（timestamp+uuid），失败重跑不撞旧驻留模型；报告目录唯一。

离线核对：驱动内全部计划操作通过 `creo_mechdog.schema.validate_operations`
真实校验；脚本语法/导入通过。

## 5. 矩阵实机驱动增强（tools/test_assembly_matrix.py）

- 真实回滚场景改为**单作业**：先合法 `component_placement` 移动既有组件，再
  `remove_component` 传无效原生组件 ID（424242，schema 合法、原生查找失败）。
  要求 failed、`result.rollback_succeeded=true`、revision 不变、
  `creo_list_components` 快照与作业前一致（已受理移动同样被回滚）、
  `component_changes.status=rolled_back`，随后一次合法修改成功。入口拒绝不计为
  回滚；不注入超时/进程故障/unknown。
- 独立几何断言：原生保存重载 inspection 的装配体积（Creo 质量属性）== 11 ×
  源件实测体积；再用仅 `{"op":"regenerate"}` + `assertions.volume_mm3` 的作业
  在原生侧复核。bbox：取源件原生 `bodies[].bbox` 8 角，经期望刚体变换得各组件
  期望边界（刚体不变体积核对）并与回读矩阵逐角映射交叉核对（1e-6），记录整体
  期望装配边界。保留既有 11 姿态、Euler 兼容、基向量/已知点、1e-6 检查与
  type_name/数字码断言。

## 6. 文档/示例/WorkBuddy 提示词与 CLI

- `examples/assembly_rebuild_pipeline.json`：step 4 capture 不再固定
  `revision=0`，改为捕获 `creo_new_assembly` 实际终态 revision；step 5
  `expected_revision` 引用 step 4 实际捕获值。
- `docs/ASSEMBLY_REBUILD.md`：guard 入口改为可直接运行的 PowerShell 单行
  （参数为 `--run`，原 `--` 写法不符合 parser）；组件变更摘要按四态重写并说明
  compact/full 均含；快照语义补“缓存 vs 刚实测原生数据”与 regenerate 取证
  方法；明确“子进程退出前必终态”不是已验证保证。
- `docs/WORKBUDDY_FEAT008_PIPELINE.md`：回滚场景改为先合法变更再普通原生失败；
  快照场景编辑实际 source_model_id 并区分缓存与实测；管线场景明确收养只接受
  托管输出之外的外部文件（managed_output 拒绝）；字段层级以实际返回为准
  （`component_changes` 在作业顶层、preview 在 `result.preview_file`，不虚构
  busy 字段）；矩阵场景补体积交叉核对。
- `capabilities.py` assembly 能力边界同步四态摘要；FEAT-008 首批其余范围
  （底板 holes 等）继续开放。

## 验证命令与结果（全部离线）

- `.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_changes
  tests.unit.test_guarded_live_run tests.unit.test_assembly_examples
  tests.unit.test_helper_layout tests.unit.test_file_adoption`：63 项通过。
- `.\.venv\Scripts\python.exe tools\test_constraint_compare.py`：build/run
  exit 0（旧→新等价、真实变化拒绝）；报告
  `build/constraint_compare_test/report.json`。
- `.\.venv\Scripts\python.exe tools\test_constraint_names.py`、
  `tools\test_adoption_source.py`：exit 0（不回退）。
- `.\.venv\Scripts\python.exe bridge.py build`：Creo 12.4 SDK 全量编译
  成功，worker `E:\Projects\md050\build\creo_worker.exe` SHA256
  `4d969376a0f00f973d157eb677db817dcae97d775d435cc2acb22e09820a4971`。
- `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-008`：
  exit 0，676 项单测 0 失败 0 错误；`build/development_check.json`
  success=true、`build/unit_test_report.json`、`build/feat008-stage3-devcheck.log`。
  未修改 style baseline；4 个变更文件按项目格式化（clang-format 23.1.3 /
  ruff 0.17.0），generic.cpp 格式化差异仅限本次修改区域。
- `.\.venv\Scripts\python.exe tools\guarded_live_run.py --help`：参数解析正常。

## 源码身份（最终，见提交记录）

实现提交基于 `1c13654`，提交后工作树干净。变更源指纹（SHA256，换行归一）：
`native/constraint_compare.h`
`566517d967a20647919fa7edccfff0cbd2ab2bada140ef2a6278ffd182233816`；
`native/generic.cpp`
`9c8a988b9592ea0562d01fe4ba633419f5ce871f9186c053373c9bc8853de2ec`；
`src/creo_mechdog/component_changes.py`
`2dd523b723805b1cae4874024dda5141ae4c7b77c0e8da1b815137b92a637ef7`；
`generic_bridge.py`
`b06571f1e24a72b04ada83d6a8de105c4fe123b64c36d6eac1090387d764f317`；
`bridge.py`
`6541612ed109142fce4a9762f4ef95baf385248c0f9a4a61234a539f99612398`；
`server.py`
`32c887c389e27f8f3c5bab58413e435af5dc6c837cec2c18291421666db0f3c0`；
`tools/guarded_live_run.py`
`edbaadf188dda47c5bdffb3baca493b429d339d7d8ce1c1aa1079b106e0398b5`；
`tools/test_assembly_pipeline.py`
`4a6ac4005dc4f5be85b98dc58bfb9d06746ae49fdfc37584719cb8966ce5ba09`；
`tools/test_assembly_matrix.py`
`709b5be8bd409b39c963d52d1864965cb32308821d32f900a2ddc689b78bd058`；
`tests/native/test_constraint_compare.cpp`
`047791411ac8717741807a0a6d1d2151e3b90e78e8c7942296aa48882c608c71`。
新增 `native/constraint_compare.h` 已进入 `server._SOURCE_NAMES` 与打包
白名单（`tools/package.py` 显式列入 `tests/native/test_constraint_compare.cpp`，
`native/*.h` 目录级覆盖）。

## 未测范围

- 实机 Creo 行为（管线/矩阵/收养驱动仅编写并离线校验，未连接 Toolkit）；
  保存重载/revision/放置的实机复核留待统一安排首次实机。
- WorkBuddy 黑盒（提示词已修正，未执行）。
- Creo 9/10 其他版本；BUG-001 会话约束继续生效（无新 Toolkit 连接）。
- unknown 保护、并发交错、嵌套装配、显式源件更新不属本轮。
