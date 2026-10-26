# 第二批第四阶段：复审收口残余缺陷修复与离线再验证（2026-10-25）

范围：用户从 stage-3 最终源码确认的四项残余缺陷的最小修复。仍不连接
Toolkit、不故障注入、不改客户端配置、不结束 Creo/worker、不清 unknown
保护、不合并不推送、不改版本、不发布。stage-1/2/3 已发生的测试事实与
历史 `docs/validation/` 原件未改写；本文件为独立新证据。

环境：Windows 11 x64 / Python 3.12.14 / 本机 Creo 12.4.0.0 匹配 Toolkit SDK
（仅离线编译）/ MSVC x64。工作树：`E:/Projects/md050`，分支
`codex/feat012-matrix-pipeline`，基准 HEAD `08754cb`（stage-3 收口证据提交）。

## 1. guard-root 真实锁释放语义修正（安全）

复现：stage-3 实现中 unknown、settle 超时、异常分支 `return 3` 直接跳
过 `_exit_guard`；但 Python 生成器回收/进程退出会释放真实 OS 字节锁，
owner 文件不是隔离，报告却写 `retained_unproven`——声称保留实则已放。

修复（`tools/guarded_live_run.py`）：

- 释放真实 main 锁的唯一条件是**三项独立证据齐全**：本轮全部受理作业
  终态 + 无 md050 原生 worker 存活 + md050 字节锁探针空闲。worker 存活
  证据不可由空闲锁推断：按本轮作业 `native_checkpoint.json` 的
  `native_pid` 对照存活进程身份（进程创建时间区分复用 PID），并对
  `build\creo_worker.exe` 镜像路径做只读进程扫描（捕捉更早崩溃遗留的
  孤儿）；扫描不可读同样视为不可证实。
- `unknown_outcome` 终态：worker 已停且锁闲时可安全释放 main 锁，但
  返回失败（exit 3）、禁止后续 child、md050 模型/作业 unknown 保护原样
  保留；unknown ≠ 必须永远持锁。
- 仍 pending 或通道/进程状态不可证实：`--settle-timeout` 只写报告/报警
  （`waiting_for_proof`），入口**继续存活持真锁**直至可证实；操作员
  Ctrl+C 是唯一提前退出（进程退出放锁，不做安全声明）。
- `_snapshot_jobs`/`_new_jobs` 仅 `FileNotFoundError` 按真正初始不存在
  处理，其他 I/O 错误不当空：基线期出错在持锁前中止；settle 期出错该
  轮不可证实并继续持锁。每轮重新发现新增作业并累计，晚到批子项不漏。
- 全程不结束 Creo/worker、不清保护、不重连、不重提、不恢复。

回归（`tests/unit/test_guarded_live_run.py`，11 项）：全部改用独立进程
真实抢 main 字节锁断言，不再只看报告字符串——超过短 settle 阈值仍真
busy（子进程入口）、延迟 job 完成后可释放、轮询期间晚到 job 累计等待、
发现期 I/O 错误（目录被替换为文件）持续持锁、终态但 checkpoint
`native_pid` 仍存活时持续持锁至其退出后释放、unknown 安静后释放但
exit 3 且保护未动、基线 I/O 错误在持锁前中止。

## 2. 管线驱动命名长度与 replace 操作缺陷

复现：24 字符 tag 使 `pipe_src_a_<tag>`=35、`pipe_rebuilt_asm_<tag>`=41，
真实 `bridge.normalize_model_name` 拒绝；末尾 replace 操作把
`plate_a_pose` 的 `op` 字段剥掉，而 `execute_plan` 操作必须有 `op`。

修复（`tools/test_assembly_pipeline.py`）：长 tag 只用于报告/外部目录；
原生模型名与外部源 basename 改用 tag 的 SHA256[:8] 确定性短后缀
（≤31、每轮唯一、跨轮可重复）。全部动态请求提取为 builder
（`request_plan`/`validate_plan`/`replace_operations` 等），replace 保留
`dict(plate_a_pose)`。

离线回归（新增 `tests/unit/test_assembly_pipeline_requests.py`，8 项）：
用真实 `normalize_model_name`/`validate_operations` 校验全部分支（夹具
零件、原装配、按 inspect 变换重建、末尾 replace、凸台编辑），并锁定旧
长命名被真实校验拒绝。

## 3. 矩阵驱动假 AABB 不变量

复现：对每个 pose 断言旋转后 AABB 体积 == 源 AABB 体积，在
`[30,90,60]` 非轴对齐姿态数学上不成立（AABB 变大）。

修复（`tools/test_assembly_matrix.py`）：体积不变量仅对有符号置换
（轴对齐）旋转断言，其余姿态断言 AABB 严格增大；保留 11 组姿态、原生
查询矩阵/基向量/已知点、原生保存重载体积与真实复合回滚场景。报告措辞
如实化：记录的整体 bbox 是**预期派生值**（源 bbox 与返回矩阵交叉运算），
不是 Creo 实测装配 bbox，也不单独构成独立物理位姿验证；独立物理锚点
仍是 Creo 质量属性体积 + 原生矩阵。未新增生产 bbox 工具/行为。

离线回归（新增 `tests/unit/test_assembly_matrix_poses.py`，4 项）：逐 pose
核算 AABB 体积，证明不变量仅对置换旋转成立、`[30,90,60]` 严格增大。

## 4. 摘要辅助读取阻断主任务 + 净变更摘要

复现：(a) `generic_bridge.run_generic_job` 在辅助 try 之前无条件
`aliases_of(prior)`/`inspection_of(prior)`，sidecar 读取失败/预算错误使
无组件作业与组件作业都在 worker 运行前异常退出，已受理作业卡死。
(b) committed 摘要按请求操作列表重复输出：add 后 move 出现
feature_id=None，连续 move 重复声称同一 from/to，add 后 remove 仍声称
added，remove/reinsert 后 move 用旧 ID。

修复（`generic_bridge.py` + `src/creo_mechdog/component_changes.py`）：

- 作业前已验证状态快照只在请求**含组件操作**时读取（普通零件作业完全不
  读 sidecar）；读取失败记录为辅助错误，仅当摘要状态真正使用前态
  （committed 净 diff、rolled_back label 解析）时降级
  `component_changes.status=unavailable`；busy 拒绝/no_effect/unknown 等
  原有错误语义不变。终态与原生结果持久化不受摘要任何影响。
- committed 摘要改为作业前后已验证状态的**净变更**：按真实 feature_id
  对比；新增/移除各一次；同 ID 才比较移动与约束；重插同 label 旧 ID
  removed + 新 ID added；先 add 再 move 最终只 added；先 add 再 remove
  无净组件变更；缺少已验证结果别名时降级 unavailable，不编造身份。
  顶层 `component_changes`/compact 接口不变，全部值取自原生
  inspection/aliases，Python 不模拟几何。

回归（`tests/unit/test_component_changes.py`，25 项）：新增 add+move 净
added、add+remove 无净变更、连续 move 单次净移动、remove/reinsert/move
双身份、缺结果别名→unavailable、sidecar 读取失败→unavailable 且终态不
变、普通作业不读 sidecar、busy 拒绝遇坏 sidecar 仍 no_effect。

## 附带修正

`tools/test_file_adoption.py` 工作树已有一行未提交修正
（provenance `fresh` → `fresh_retrieval`），与原生
`native/generic.cpp` 实际发送值一致（`tests/native/test_adoption_source.cpp`
同值），随本轮一并提交。

## 验证命令与结果（全部离线）

- 定向回归：component_changes + guarded_live_run +
  assembly_pipeline_requests + assembly_matrix_poses + model_registry +
  seed_listing + assembly_examples 共 86 项通过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：701 项，
  0 失败 0 错误，182.5 s；日志 `build/feat008-stage4-units.log`。
- `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-008`：
  exit 0，success=true，unit_tests=passed；未修改 style baseline
  （lint_findings 31、unformatted 19 均为存量，4 个变更文件按项目格式化）。
  报告 `build/development_check.json`（唯一最新），历史记录已另存
  `build/batch2-stage3-development_check.json`、
  `build/batch2-stage3-unit-test-report.json`、
  `build/batch2-stage4-development_check.json`；日志
  `build/feat008-stage4-devcheck.log`。
- 四个 C++ helper harness（生产 helper 真实编译运行，无 Toolkit）：
  `tools\test_assembly_pose.py`、`tools\test_constraint_compare.py`、
  `tools\test_constraint_names.py`、`tools\test_adoption_source.py`
  全部 build/run exit 0。
- `.\.venv\Scripts\python.exe bridge.py build`：Creo 12.4 SDK 编译成功，
  worker `E:\Projects\md050\build\creo_worker.exe` SHA256
  `4d969376a0f00f973d157eb677db817dcae97d775d435cc2acb22e09820a4971`
  （与 stage-3 相同，本轮无 C++ 变更）。

## 源码身份（最终，见提交记录）

变更源指纹（SHA256，换行归一）：
`tools/guarded_live_run.py`
`5e5b09d04318ee4ab216ed94d480a316b3a8e83d7b00ba3d26f88d9982f520b2`；
`tools/test_assembly_pipeline.py`
`84ed5f15043be217b47d1813707c3f8f17d81abfb0532c89166686457ab439ed`；
`tools/test_assembly_matrix.py`
`680c9230192fab5fdcb8d7b407d50df8e4055bfe0385080fd2042286166eefc7`；
`tools/test_file_adoption.py`
`abe3d37bf98a9da3edd0261ce4e1f4f0f6847040efe06083787bf272885a7450`；
`generic_bridge.py`
`3f76263415e8ff6fa6d6e576c71cdfa2e0459820cf229ea9bab5a6838ad91a78`；
`src/creo_mechdog/component_changes.py`
`4fa0db12a861e8d8bb6da4335b03bbbbf054759982da2d2cb7c1084d584ab84b`；
`tests/unit/test_guarded_live_run.py`
`54bb091def1534dd0725806b9fdc98be7a302bae0d4450f08ba131dddf7e8a53`；
`tests/unit/test_component_changes.py`
`108941ee71184a7778e249a541f16032b724d46b378edb5be2a2074765f2b422`；
`tests/unit/test_assembly_pipeline_requests.py`
`098fb0a4016bc891ac08f54e89532a2b854b45c53f9a40cf3150fda89496ef37`；
`tests/unit/test_assembly_matrix_poses.py`
`772198deced1c3050dd29487a089298d7992f2b4601ab9ebfcc92d5a166fb12c`；
`docs/ASSEMBLY_REBUILD.md`
`22db11b29f5e8b39bdb48a1faa3303e6e9c2392f39a95d553a9d36ca98078e57`。

## 未测范围

- 实机 Creo 行为：管线/矩阵/收养驱动仅离线校验，未连接 Toolkit；
  guard 新释放语义的真实会话验证留待统一安排（本机继续遵守
  BUG-001 会话约束，无新 Toolkit 连接/故障注入）。
- WorkBuddy 黑盒：未执行。
- 并发交错、unknown 恢复、嵌套装配、显式源件更新不在本轮。
- 这些修复完成不等于交付：合入 main/版本/Release 未发生。
