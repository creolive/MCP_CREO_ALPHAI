# 0.11.1 发布记录

版本与条目：0.11.1（PATCH，用户指定编号）——DEV-053 0.10.0 晚间反馈批 Q00–Q15：BUG-096（失败模型清理与同名复用 + `rollback_status`）、BUG-097/098（斜面草图与三点定面读取修复）、FEAT-053（三点定面 `through_points`）、FEAT-010 增量（草图显式容差 `geometry_tolerance_mm`）、FEAT-033 增量（作业 `stage` 上报）、FEAT-008 增量（结果有界回执与 compact 32 KiB/full 游标分页）、BUG-100（背靠背提交竞态修复）、BUG-099（定因披露，无代码变更）；工程项：Q00 十件原件归档、G5 契约冻结、P12 配方转换与分级验收、DEV-055、`docs/superpowers` 行尾规范化。

提交、dirty 标志、受测源码指纹：主干 `6f3cc0a`（`task/11` FF 合入；发布时工作树除既有本机 `session_activity.json` 本地修改外干净，该文件不入库内容与交付无关）。dev_check `source.commit=6f3cc0a`、`dirty=true` 仅因该本地文件。

日期与 Windows/Python/Creo/SDK/MSVC 环境：2026-11-02（Asia/Shanghai）。Windows 11 Enterprise x64、Python 3.12.14（工作树 `.venv`）、Creo Parametric 12.4.0.0（`release_numeric=44`）、匹配 Toolkit SDK、MSVC x64（`C:\MCP_CREO_MechDog\vcvars64_local.cmd`）。

命令及结果（单元／原生／安装／源码包）：

- 单元与语言：`tools/dev_check.py` **success=true**（单元 **2096 项 0 failures**；本批变更文件全部过 ruff format/clang-format；30 findings/16 unformatted 均为基线内存量）。
- 原生实机（四轮，[DEV-053-Q15-live 记录](DEV-053-Q15-live-2026-11-01.md)）：Q05 三点定面 8/8；Q06 斜面草图 L1/L2（体积相对偏差 1.45e-8、保存重载 true）；Q03 S1/S2/S3（清理 erased+absence_verified、同名重试 succeeded、S3 `rollback_status=succeeded`）；Q13 预览/分页全套（`disk_cut_pattern` rev 3、体积 45238.934 mm³、保存重载 true）；Q02 15/15；Q04 真实并发 busy 回执完整；Q01 P07 3+3 / P08 9/9+2/2 / P11 覆盖；Q11 P12 一带通过（四带 2.91e-4 mm 超默认阈值 29 倍如实拒绝，边界见 [P12-BLADE-ACCEPTANCE](../development/P12-BLADE-ACCEPTANCE.md)）；BUG-100 复验三项通过（背靠背 11.913 ms 即拒、并发 busy、预约终态释放）。
- 打包：种子包确定性**三建同哈希**（task-11 双建 + 主干重建）`f1794794d3abed1f8c8ec4de0f3ff2a8338f5d8d9118c5323ec5fef4b075820f`（24 文件/9 种子；与 0.11.0 种子库内容一致，仅 zip 内版本前缀不同故哈希不同，受信摘要已回填 `docs/seed_package.json`）；源码包 `tools/package.py --seed-archive` 成对生成（1179 文件），解包抽检 `version.py=0.11.1`、种子 9 件、双清单在包内一致。

原生修改保存重载、参数编辑、回滚证据：上表所列实机均含 `saved_file_reloaded_and_verified=true`；回滚证据——Q03 S2 预存对象保留、S3 revision 不变 + `rollback_status=succeeded`；0.11.0 复测的 recolor 回滚语义未受本批影响（回归面见 WORKBUDDY-0.11.1 场景 7，本轮未执行）。

未测模块、失败用例、兼容限制：WorkBuddy 黑盒未执行（[提示词已备](WORKBUDDY-0.11.1.md)）；同模型空窗陈旧 revision 竞态、>2 并发未做实机；Q08–Q10 三曲面链、Q11 四带/全叶片；Creo 9 本机无 SDK、Creo 10 独立复测不作为门槛；本机 Creo 12.4 通过不外推其他环境；BUG-091 根因未定，准入纪律持续有效；`tools/test_stdio_lifecycle` 存在已知时序 flaky（单跑通过）。

源码包及种子包 SHA256（文件名与完整哈希，写入 Release body）：

| 附件 | SHA256 |
| --- | --- |
| `MCP_CREO_MechDog-0.11.1-source.zip`（7 035 605 字节） | `042e581395b262679ac73309eb7d1e920cac2722cb8a1db2fa06ed1ff7720c3c` |
| `MCP_CREO_MechDog-0.11.1-seed-library.zip`（493 442 字节） | `f1794794d3abed1f8c8ec4de0f3ff2a8338f5d8d9118c5323ec5fef4b075820f` |

发布候选验收结论：**通过**（轮3 实机负责人结论"0.11.1 可发布"：BUG-100 两时序复验符合 `reject_busy_without_creating_a_job`，三项冒烟全绿）。

合入 main 的提交、版本标签及指向：`main` FF 至 `6f3cc0a`（`2f6aab7..6f3cc0a` 推送）；标签 `v0.11.1`（附注对象 `058fc12f`）剥离后指向 `6f3cc0a`，与 `version.py` 一致；远端 `refs/heads/main`=`6f3cc0a` 已核。

GitHub Release 链接与发布状态：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.1 （Release id **431182491**；`draft=false`、`prerelease=false`；正文含两 ZIP 文件名与完整 SHA256，已核）。

远端附件与 SHA256 核对结果（body 记载与远端附件逐项一致）：四附件（源码包/种子包及各自 `.sha256` sidecar）`state=uploaded`，远端逐件下载哈希与本地构建一致（源码包 `042e5813…`、种子包 `f1794794…` 均 match=true）。

逐 ID 状态核对（候选态 / 发布后各一次）：

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-096 | 已交付（S1/S2/S3 实机） | 0.11.1 | WorkBuddy 黑盒、擦除失败路径实机 | 已交付（0.11.1） | 已交付（0.11.1） | 修复与增量首条 | 0.11.1 当前正式版条目 | v0.11.1 已发布 |
| BUG-097 | 已修复（L1/L2 实机） | 0.11.1 | 原始 v1.2 TXT/中间件缺件 | 已修复（0.11.1 交付） | 同左 | 同上 | 同上 | 同上 |
| BUG-098 | 已修复（Q05 8/8） | 0.11.1 | 引用逐条核对未验证 | 已修复（0.11.1 交付） | 同左 | 同上 | 同上 | 同上 |
| BUG-099 | 已定因（无代码变更） | 0.11.1 | 无（worker/源码一致性建议已记录） | 已定因（0.11.1 随版披露） | 同左 | 定因披露条目 | 同上 | 同上 |
| BUG-100 | 已修复（离线+实机复验） | 0.11.1 | 同模型空窗陈旧 revision、>2 并发 | 已修复（0.11.1 交付） | 同左 | 通道预约条目 | 同上 | 同上 |
| FEAT-053 | 已交付（Q05 8/8） | 0.11.1 | 装配/图纸上下文未扩展 | 已交付（0.11.1） | 同左 | 三点定面条目 | 同上 | 同上 |
| FEAT-010（增量） | 部分交付（显式容差） | 0.11.1 | 卡内其余子项保持待规划 | 增量注明 | 待规划行含增量 | 显式容差条目 | 同上 | 同上 |
| FEAT-033（增量） | 部分交付（stage 上报） | 0.11.1 | 公开预算/阶段耗时契约未实施 | 增量注明 | 验收中行含增量 | stage 条目 | 同上 | 同上 |
| FEAT-008（增量） | 部分交付（有界回执/分页） | 0.11.1 | 预览图像内容人工复核等 | 增量注明 | 未收口行含增量 | 有界回执条目 | 同上 | 同上 |

相对上一正式包核对（上一版本：0.11.0，正式源码包 `d657c845…`）：

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| native/third_party 原字节（含 json.hpp、第三方许可） | 2 文件 | 2 文件，逐字节一致 | 未变 |
| 回调指纹（sha256-repo-lf-v1） | — | 本批 `native/*.cpp`/头有变更，指纹必然变化 | 以新源码重建即可 |
| loader/callback/worker 二进制 | 本机构建产物，不入源码包 | 同左 | 升级重跑 `setup.ps1` 重新编译 |
| protk.dat / 注册表路径 | — | `creo_startup.py`/注册相关产品文件无变更（仅 `tests/test_registry_io.py` 测试变更） | 实际注册影响：**未变**（无需迁移/重注册，重启服务生效） |

本机生成物原件（Release body、发布脚本、四附件）在 `E:\Projects\MCP_CREO_MechDog-release-0.11.1\`（仓库外），不入库。
