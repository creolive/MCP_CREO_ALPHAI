# 0.6.0 发布验收记录（2026-10-26）

第二批可靠装配重建管线：FEAT-012/BUG-045 矩阵子项、FEAT-048 按路径及批量收养、
FEAT-008 官方流程、组件变更摘要与约束符号名，关联 DEV-046。
本批 WorkBuddy 黑盒经用户明确取消，未执行、不记通过；用户随后因子代理额度耗尽
授权 root 直接完成验证、合入和发布。第三批及显式源件更新/嵌套不在本次范围。

## 源码与环境

最终业务源码候选 `a2a391368fd0147bcf2501fb5b0779208f63351f`；相对已验收 b86，
语言源码仅版本常量和种子包摘要常量改变，无业务/原生实现变化。后续提交仅收口文档。
Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 SDK、MSVC；本地 MCP 仅
canonical `E:\Projects\MCP_CREO_MechDog`，受测时 detached a2a3913，dirty 是保留的
`session_activity.json` 和既有 untracked，未提交或还原运行账本。
会话 fingerprint `8109163335419786528`；未结束/重启 Creo、清保护或故障注入。

原 21 暂存文件保全提交 d563958 的 tree 为
`08ba93a34409f539145686ea91541ce34fb34102`；原 c50fd65 与整合的 main b5ad5d5
保留为祖先。备份见 `E:\Projects\md050-preservation\20261025-165659`。

## 开发与安装

- `tools/dev_check.py`：748 项，0 失败 0 错误，success=true；受测 BASE beb8408、
  dirty=true，语言源码 SHA256
  `f4dd3524c864ce6679bf02703bece60f4657c393781af0e555c83f122223e9e5`。
  默认增量风格检查通过，存量 31 lint/19 未格式化，未改基线。
- 原件目录 `md050/build/release_candidate_0.6.0_20261026T005954Z/`：
  development_check.json SHA256
  `63f6f1fd361dc63dc01e25fedb9528ed1bfda2631d2e5e95ca91d7d54309c3a0`；
  unit_test_report.json `f778ab89b8e17fa73af1e0d28265f8172c0b3c45f3bfd585295290ccf519854f`；
  完整 dev_check.log `912dd70dd1a1fd21cf38d9a2c5d46c1c096ad09d620c58de905e03772b03d0d4`。
- `bridge.py build` 成功；native source 指纹
  `3dcedc0e66e40c2fc10105577d7d813a6a466bb9356348744a3e073e13f76e56`，
  实机 canonical worker SHA256
  `9b25859862fffecbb79bfc655795bbb35cabba0d5f6e5dd41a60955966ad35ad`。
- 从干净 a2a3913 checkout 预打包并解压 854 个公开文件，确认本机配置/常量/二进制/
  build/jobs/models/.venv/运行账本不入包，新模块/helper/示例/许可齐全，9 个 PRT
  原哈希不变。新目录完整执行 `setup.ps1`，依赖、editable 安装、种子校验、常量
  重新生成与 SDK 复编全部成功；包元数据、version.py 均 0.6.0，模块实际从解包目录导入。
  该目录未注册为 MCP 客户端，实机仍仅用 canonical。记录
  `md050/build/release_preflight_060_a2a3913/installation_verified.json`；安装日志 SHA256
  `15fef8c5599c19575ba4b2fdebc0466d1efbd9417b91256286203175165fef61`。
  首次日志捕获在依赖阶段中断，原 `installation.log` 保留；改变日志捕获方式后重用
  同目录安装成功，未改安装脚本，初次中断根因未独立隔离。

## 最终候选公开 MCP 实机

- 六项收养父作业 `31e099b10f2a41bfa7647ded16e60787`：2 succeeded、4 refused、
  0 unknown。健康 A `existing_resident`、健康 B `fresh_retrieval` 各提交 revision 1，
  unhealthy_features / non_millimeter_units / external_dependencies / duplicate_source
  依序拒绝，普通拒绝后 B 仍成功；保存重载、源字节和窗口保持。
  原驱动最后只读盘点遇另一个 `startup_build` 的结构化 busy，整轮 guard 失败保留，
  不计为完整套件通过；没有重提收养。占用结束后另做只读盘点及原键回放，仍返回
  同一父作业/同一 items；源文件独立重 hash、当前窗口与 before 一致。
  原报告 `canonical/build/file_adoption_integration_20261026T011251Z_cd0f3abe/report.json`
  SHA256 `c0e814196e95a7055d4fb85836bb9b2530a03609bf3ba6e4951a1ff010838fa2`；
  补充报告 `md050/build/release_060_live_a2a3913/adoption_readback_report.json`
  SHA256 `baff97588a82d038121edacfe16c8ea1b5d7144ed407e5c5ad8d45d0f6cf057d`。
- 矩阵驱动 `canonical/build/assembly_matrix_live_20261026T012221Z/report.json`
  success=true，SHA256 `0dfff71cad71edbd1661ee0262ee7a115bdb64feffafb09e4b7acd8f81811015`。
  38 父作业（37 success + 1 预设普通失败成功回滚），装配
  `5b7df58dbd2c40f396ce26037185bb5c`，11 姿态的实际矩阵、基向量/已知点、Euler
  兼容、revision、约束数字码+符号名、保存重载、原生体积 330 均通过。失败作业
  `36cdaa653df24943a9eba352da9bdd3a` 的 rollback_succeeded=true、快照及 revision
  恢复，后续合法更新和 regenerate 成功至 revision 36。
- 管线 `canonical/build/assembly_pipeline_live_20261026T012751Zb428049a/report.json`
  success=true，10 父作业全部成功；SHA256
  `553d1c667fc359a3a69af321dc0becc90cfa4dc9ef4ba08bf67f573ccfc0d3da`。
  三 occurrence 含 B 重复实例，真实路径/矩阵重建、单作业三组件、摘要与数字约束+
  type_name、保存重载通过。源 A 7200→7800 后装配 regenerate+保存重载仍 12384；
  用新唯一 label 重插后装配 `48808ed604b24372bfbd6076eed3556f` revision 4、体积
  12984；作业 `d85ec20545ae41bd9e711f4c5636d92c` 报 removed feature 40、added
  feature 49/source_revision 2。原装配与只读源件不改写。
- 成功 guard `canonical/build/guarded_live_20261026T012159849599/report.json`：三个
  子进程均 exit 0，55 个新发现作业全终态（54 success + 上述预设 failed），
  quiet/released，无 worker 存活；SHA256
  `75a3fdbc3b5abc22927c31e30bb0bbe1f935ed97586eb6b7e084f33448eea8a6`。
  失败 guard `guarded_live_20261026T011249848472` 原件保留，不改标通过。

## 未测与限制

WorkBuddy 未执行；其他 Creo（9 无 SDK、10 未复验且非门槛）、并发交错、unknown
故障注入、modified/wrong-origin/token 超时等准入分支本轮不泛化。矩阵数值 NaN/
Infinity 只离线覆盖，32 次标准 JSON 非法输入真实入口证据见
[综合证据](../development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md)第 6 节。AABB 是
源盒与查询矩阵的派生预期，不是独立 Creo 装配 bbox 实测。
BUG-078、BUG-082 及其他既有问题按[版本说明](../RELEASE_NOTES_0.6.0.md)保留。

## 主干与附件核对

正式两包必须从本批实际 main 合并提交生成，tag 为 v0.6.0。确定性种子包 SHA256
`e17563e66e24a1f879ecab91fff0b98ed7cfca94821ea103516e5e9bcc87166a`，须与 seeds.py
一致。实际 main 提交、两包完整 SHA256、四附件及下载核对，以
[本次 GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.6.0)
正文和同名校验附件为交付记录。源码包包含本文，因此不把其自身 SHA256 再写回包内，
也不为发布后补录另造一个未随 Release 交付的 main 提交。
