# 第二批可靠装配重建管线：开发者实机验收综合证据（2026-10-26）

范围：FEAT-012/BUG-045 矩阵子项、FEAT-048 按路径/批量收养、FEAT-008 官方装配重建管线
（DEV-046 第二批）。本文汇总实际执行的开发者验收与证据复核，未改生产代码/版本，
未结束 Creo、清 unknown 或故障注入；未合入 main/推送/发版。

受测分支 `codex/feat012-matrix-pipeline` 的源码提交为
`b86fa4a7c1184767c50b1ecc12352114c070d386`；该次开发检查时工作树干净
（`git status --porcelain` 空），后续证据提交只改文档；`c50fd65` 与 main `b5ad5d5` 均为祖先；
21 个暂存文件由 d563958 保全（tree `08ba93a34409f539145686ea91541ce34fb34102`，
备份 `E:\Projects\md050-preservation\20261025-165659`）。canonical
`E:\Projects\MCP_CREO_MechDog` 为 detached 同一 b86 候选（本机 dev 服务规范），
main ref 仍 b5、版本仍 0.5.3；canonical 仅多 tracked 运行账本 session_activity.json
自然变化与既有 untracked，保留不还原/不提交。

**以下全部为真实开发者 MCP 实机证据，不是 WorkBuddy 黑盒。** 第 2～6 节运行于
2026-10-25 23:07（Asia/Shanghai）那次重启之后、10-26 06:58 再次重启之前。环境：Windows 11
x64 / Python 3.12.14 / Creo 12.4.0.0 匹配 SDK+MSVC；重启后 parametric 进程 4516 /
xtop 17932，session fingerprint `1841692455511503772`。canonical native worker
SHA256 `9b25859862fffecbb79bfc655795bbb35cabba0d5f6e5dd41a60955966ad35ad`，
native 生产源码本轮未再变。所有 raw 报告关键值已经人工核对。

## 1. 独立全量开发检查（md050，串行 solo）

- `build/batch2_solo_check_b86fa4a_20261025T165605Z/`：748 项单测 0 失败 0 错误，
  dev_check `success=true`，source clean b86、`checked_source_sha256=
  c0b92b7fd31d570d72ecc591c929394d53e66c8f8a5dd21127c9b1b7fd7dfafb`。
  style 存量基线 31 lint / 19 unformatted（非严格全库零问题，未放宽基线）。
- 文件 SHA256：
  - `result.json` `fee140cf6cd4a35db2fe40675bb77f3908a0f2dd0189423975933fc7e0b69e29`
  - `development_check.json` `912702fa7face154bc885c7d543ecd61add2795c2c2e51aee2ef3aa42fedbee5`
  - `unit_test_report.json` `c03cccb94ba211a07daa1c4d28877d808ae2f0727dc1bb93c41cc2878450128d`
  - `dev_check.log` `5c9b6ee7660e3590bbbdc718577eb387bf74208212eb752525afd70041380d34`
- 历史失误不计通过：上次 c6 并行测试 full 726 报 ToolkitBusy（1 error），原件
  `build/batch2_parallel_check_failure_20261025T154845Z/development_check.json`
  （SHA256 `0c8b5a28166a6cf016c1eb6a49295cffb1637a197e4ff292021dc225d0b156ea`）
  另存保留；随后 fc86231 solo 745 项与本次 b86 solo 748 项均通过。

## 2. 矩阵实机（canonical，源码 fc86231）

- `build/assembly_matrix_live_20261025T162021Z/report.json`
  （SHA256 `fb44e398d27aed3d60734eeead16c74a351f7dce7a9365ac88303d8a00c16a3a`）：
  `success=true`；38 个父作业 = 37 成功 + 1 故意普通失败（无效组件引用 id 424242，
  job `b0292449d74345f582858540bc30ea81`，`toolkit_code=-23`，
  `rollback_succeeded=true`，`component_changes.status=rolled_back`，装配 revision
  与位姿恢复后后续作业继续成功）。覆盖 11 组姿态、实际查询矩阵基向量/已知点、
  Euler/矩阵互斥输入拒绝、revision 递进、native 保存重载、约束数字码 13
  + `type_name="fix"` 并存、装配体积 330（11×30）独立几何断言（原生质量属性，
  保存重载后复检）；记录 bbox 为源盒×回读矩阵的**预期派生值**，不是 Creo 实测
  装配 bbox。
  该驱动没有逐项调用形状、字符串、布尔、非有限数、反射、缩放及非正交负例；
  不能由这份实机报告判为 MCP 入口全部已测；标准 JSON 可表达的 8 类负例随后由
  第 6 节另行实测，数值 NaN/Infinity 仍只离线覆盖。
- 配套 guard `build/guarded_live_20261025T162020624286/report.json`
  （SHA256 `ec9eaf6a88f484715a12b3954a56a47d9bd6266133e7e7065532ed618b7cf45`）：
  **总体 `success=false`（不写通过）**——旧管线驱动 step 9e 以原 label 复用
  remove+re-assemble 被入口拒绝（`Feature labels already exist: ['plate_a']`），
  pipeline 子进程 exit 1；**matrix 子进程 exit 0**（唯一失败为上述故意回滚作业）。
  guard settle quiet/released 成立（本轮 53 个新发现作业：52 succeeded + 1 故意
  failed）。

## 3. 补充真实改变位姿 4 步（md050）

- `build/matrix_changed_pose_20261025T1636/report.json`
  （SHA256 `6b40a9e22232283ad26f21854a180c51d50fe76ac0a96f0a1832d0601d13be94`）：
  model `fc8b1c60f0b947debba6ca84726fcc90`，revision 36→40，四步依次为
  独立工具矩阵（job `fb4d8de1494d4fa19141a8ed1c36bff4`，rev 37）→
  execute_plan 矩阵（`a0ea652d956a4f7f8155b6840f43d4fc`，rev 38）→
  Euler 兼容（`c8f05de9429b45b290c584f8b8835ac9`，rev 39）→
  恢复原位姿（`7d4a0489b7ec4fafaa52a1e45eff8128`，rev 40）；逐步真实查询回读
  与 knownpoint/摘要 moved/保存重载一致，worker SHA 同上。

## 4. FEAT-048 批量收养实机（canonical，源码 aac3c84，与最终 production 相同）

- 批次一 `build/file_adoption_integration_20261025T153627Z_4dd8fca3/report.json`
  （SHA256 `7ca681f0a92e90740534622f8b3575b74838c7e4f9426c5b66d49df8cf022bb8`）：
  父作业 `536d15c0312f460780637a743fbfa03c` succeeded；5 件 = 2 成功 + 3 拒绝 +
  0 unknown——item0 现驻留健康 `existing_resident` 成功（model
  `76c54f8a6f06441d843409fecb728b95`）、item1 `unhealthy_features` 拒绝、item2
  `non_millimeter_units` 拒绝、item3 fresh 健康 `fresh_retrieval` 成功
  （`fd97bb56e2a548f69765588690a5140c`）、item4 `duplicate_source` 拒绝。两件成功
  各自 revision=1（durable item 作业 `83f47d16…`/`a7a10541…`）、
  `saved_file_reloaded_and_verified=true`、source SHA 不变、窗口不变、same-key
  回放返回同一父作业。guard `guarded_live_20261025T153625988611` released/quiet
  （报告 SHA256 `62e64327adb955083c1d74bbd1050f3921cc6abca7cbab0e7fcb0744f83918c7`）。
- 批次二（真实外部依赖源件）`build/file_adoption_integration_20261025T160223Z_21b9c215/report.json`
  （SHA256 `2b6f6fae7e6a5cd6697f4f0a372e1ae3d3de2c71d97201975f3733a0ffb6c1cf`）：
  父作业 `0df319186d284a168b3359f9291e42b2` succeeded；3 件 = 1 成功 + 2 拒绝——
  item0 `wb_reject_dep.prt.1`（existing_resident）`external_dependencies` 拒绝，
  item1 `b2dep_ok_062d403a.prt.1` `fresh_retrieval` 成功（model
  `f86154053a7a4f67aad18b4d60b07689`，rev 1），item2 `duplicate_source` 拒绝；
  same-key 回放/source 不变/窗口不变/保存重载均成立。guard
  `guarded_live_20261025T160222706597` released/quiet（报告 SHA256
  `938dac7eb61eaf6cf50f64df87ecbbdaa0afe2a34e20c3cafc04bd0c092b8b7f`）。
- 真实夹具：`build/batch2_existing_dependency_20261025T155102Z_21d0fb/manifest.json`
  （SHA256 `d1e3a59b8dd544b39468e270ea5af30c62692a1b0fb863b68a4fde8ae9e770ce`）记录
  原件（`E:\CreoAcceptance\2026-10-19\`，证据 docs/validation/ADOPTION-WorkBuddy-
  2026-10-19.md 同日段）与只读副本 SHA（`c2eaa0cc…`/`8d4429d7…`/`fff48c00…`），
  原件与副本独立重 hash 均不变。附加单 inspect 作业
  `9e48e7ec31294564936f721cad4c095d`（kind `adoption_file_probe`，status=failed
  即探到依赖）：units=mm、healthy=true、`dependency_free=false`（显示名
  WB_REJECT_DEP），证明“健康毫米但非 dependency_free”的准入分支。
- 此前两种私有 SDK 造依赖夹具均普通失败，原报告保留，不宣称成功、不推测许可
  根因；本批已用真实历史依赖夹具解决。modified / wrong-origin / token 超时等
  准入分支本轮仍只离线覆盖，未实机泛化。

## 5. 最终管线实机（canonical，源码 b86）

- `build/assembly_pipeline_live_20261025T170907Zf5978fb3/report.json`
  （SHA256 `d193f80a4da87951fe03caf7ee9155a9d3ce0d6f392e65c98b034ec8cdc4c261`）：
  `success=true`，10 个父作业全部成功。original model `806a0a70687b472981db4690d4551628`、
  rebuilt `e43c98380fa54c1faf9310b86c86c2e8`、source A `f0d3e46e07c14866ad69793af7e7bcca`。
  源 A 7200→7800（外伸凸台 tab 体积 600）；新旧装配快照总体积均 12384；源编辑后
  原生 regenerate+保存重载仍 12384（list_components 缓存不变，仅缓存非实时证明）；
  单作业 remove `plate_a` + 新唯一 label `plate_a_refreshed` 重插后 12984，
  装配 rev 3→4，`component_changes` committed（removed 旧 feature_id 40 / added 新
  feature_id 49、source_revision=2），组件回读另确认新 copy name；三 occurrence（含 B 重复 +
  非对称组合旋转 R）按实际 occurrence_path 与 mm transform 重建并回读匹配冻结
  快照；源只读 hash 不变、原装配只读检查不改动。保留原 label 需两个独立作业，
  第二失败不回滚首个删除；生产 alias 预检规则未改。
- guard `build/guarded_live_20261025T170905774374/report.json`
  （SHA256 `962d243085bd51423ebab419a5efc1d279c6957d953f00fa950adc8cc5bdce5b`）：
  `success=true`、子进程 exit 0、settle quiet/released，本轮 16 个新发现作业全部
  succeeded；释放时无 md050 native worker 存活且通道锁空闲。旧 24 个历史
  pending/running 登记不属本轮，不核销、不清保护。

## 6. 四条真实 MCP 路径的 32 个矩阵拒绝输入（canonical，源码 b86）

- `md050/build/matrix_entry_reject_20261025T173627Z/report.json`
  （SHA256 `d2fb3fc87d2d1494f339b7d7d2e720dd49be4f594e3a3f18381a4fac9d36fdc7`）：
  8 类输入分别调用独立 `creo_assemble_component`、独立
  `creo_component_placement`、plan assemble、plan placement，共 32 次真实调用。
  输入包括 Euler 与矩阵并传、平铺 9 元素、缺列、字符串元素、布尔元素、反射、
  缩放和剪切（非正交量 `0.000002`）。全部为服务入口校验拒绝，原始错误命中对应
  矩阵原因，未因 busy、revision、模型或标签错误掩盖；`accepted_job_count=0`。
  model `fc8b1c60f0b947debba6ca84726fcc90` 的完整 components/aliases 前后相等，
  仍为 11 个组件、revision 40。NaN/Infinity 没有以非标准 JSON 发送，不判其 MCP
  数值输入已实测。
- 临时驱动仅保存在忽略目录，未改生产测试：`matrix_entry_reject.py` SHA256
  `e298faaeee525bc05b97ec770e8e7d9a252f6bce87106b40c677fc5bc55d3fcd`。
  canonical 工作树只有既有运行账本变化和 untracked；md050 当时有本文等 4 份文档
  修订，生产源码与 b86 相同。
- 成功 guard `canonical/build/guarded_live_20261025T173855736205/report.json`
  （SHA256 `dd7c4e50a9e35a5da97bb4bcaeabee4b846356c617fcd27058bc5721bc4fd646`）：
  `success=true`、子进程 exit 0、quiet/released，未发现新增作业、无 native worker
  存活。前次临时驱动的局部变量错误在发送负例前退出，guard
  `guarded_live_20261025T173751464498` 为 `success=false`、exit 1、quiet/released，
  未新增作业；失败原件保留，不计通过。

## 7. 第二次停电重启后的恢复核对（2026-10-26）

Windows boot 06:58:15（Asia/Shanghai）；当前 parametric PID 20180、xtop PID 20164
于 08:07 启动。只读画面是正常 Creo 起始页，无模型或阻塞对话框；00:19:21 UTC
公开 `creo_session_status` 返回 `connected=true`、connect/disconnect code 0，
visible Creo 窗口无挂起，当前模型为空。该次启动历史显示
`launched_by_coordinator=true`，不是沿用前次进程。这里仅证明新会话连接正常，
不替代前六节几何验收，也不重写其会话指纹。

恢复复核：原 21 文件 tree 不变，856 份旧 model 控制文件 SHA256 不变；main
`b5ad5d5` 的 338 个 `docs/validation/` 文件与当前逐字节一致。未清历史 pending、
unknown 或其他保护。新会话的 WorkBuddy 场景需重新读取驻留状态并打开只读原装配。

随后由“写程序高手”完成开发者只读夹具准备，报告
`md050/build/fixture_prep_reopen_20261026T002632/report.json`（SHA256
`4337e4ea936a1af008893cf54d2d70d67a1dc602e156b91a8b1989140dcfb470`），
仍不是 WorkBuddy 验收。三个公开 `creo_open_file` 作业分别为原装配
`aaeae77143f44d79a861960c66241c69`、依赖参考件副本
`85efd21e9e8a470bbff43ffe0d13d49c`、专属健康 A
`8ba211df64274c02ab64cd9cd27186a8`，均 succeeded、`adopted=false`、
`model_id=null`、`source_file_changed_during_open=false`。原装配已驻留，
没有重新收养或推进原装配 revision。

原装配公开只读检查 complete/resolved，occurrence_path 为 [40]/[43]/[46]；
冻结原始结果 `frozen_assembly.json` SHA256
`1a6197493593a708e0a9c70fa04a8b2a235ca2c87353246177aa262c1ddece83`。
最终驻留 6 个对象且全部 modified=false；健康 A 精确来自专属只读夹具路径，
未收养且为当前模型，B/bad/inch/依赖源件均未加载。session fingerprint 为
`8109163335419786528`。原装配输出目录、原 model.json 与三个打开输入的 9 个
唯一文件前后 hash/只读属性相等，root 复核当前字节仍一致；原登记保持
ready/revision 2/pending=null。准备步骤允许显示不同夹具；后续收养“窗口不变”
须由 WorkBuddy 以它自己读取的当前窗口为基线判断。

准备驱动共留下 6 份独立 guard 报告：前 5 份 exit 2（驱动 API/字段/轮询检查
错误或新 MCP 启动尚在 building_worker），不计通过；其中实际打开成功的对象
留在会话，未重提打开作业，没有清理会话。最终只读核对 guard
`canonical/build/guarded_live_20261026T003815225709/report.json`（SHA256
`94e45500b911161a5a68643fbcb27634f90a001c92dd0b7ac25fc6cd5fe0bfde`）
exit 0 / success / quiet / released。六轮共发现 10 个作业，全部 succeeded；
三个打开作业各只执行一次，其余为公开只读检查。没有 unknown 或原生失败。
root 最后只读画面确认健康 A 正常显示，无阻塞对话框。

## 2026-10-26 最新用户决定（追加）

用户当日明确决定：取消本批 WorkBuddy 黑盒测试（**未执行**，已备提示词
`build/workbuddy_batch2_20261026/PROMPT-UTF8.txt` 不产生黑盒结果），不再请求
UI 共享；并授权在符合条件后直接合入 main 与发布 Release。上述第 1～7 节验收
事实与发生时状态保持原样，WorkBuddy 取消不改变其结论，也不把任何开发者 MCP
证据改称为 WorkBuddy 通过。0.6.0 发布候选的只读收口（版本元数据、种子包
digest、当前文档）在业务实现不变的前提下另行提交；合入、标签、Release 与
附件核对由控制者执行。

## 取消前的 WorkBuddy 状态与未测范围（保留当时事实）

以下共享阻塞是用户取消测试前的记录；当前决定以上一节为准，不再要求 WorkBuddy。

- WorkBuddy 黑盒**仍未运行**：最新重启后工具看到整个屏幕为 read，WorkBuddy
  已恢复显示，但没有单独 control 共享；须由用户在 Codeg 的 Computer use
  改为读取和操作（不是 WorkBuddy 自身设置）。
  已备独立纯 MCP 提示词 `build/workbuddy_batch2_20261026/PROMPT-UTF8.txt`，但无黑盒结果。
  **当前不能判整批交付或发布。**
- 未实机：并发/通道忙交错、unknown 自然分支与断连故障注入、其他 Creo 版本
  （9/10 未复验）、modified/wrong-origin/token 超时等收养准入分支（仅离线）、
  嵌套子装配、FEAT-012 显式源件更新、第三批 FEAT-049/050、DEV-027 世代回收。
  unknown 保护只有离线覆盖。派生 AABB 非独立几何实测。
- 第一批与第三批范围、FEAT-008/FEAT-012 整卡其余范围保持开放，不按本轮证据
  关闭。
