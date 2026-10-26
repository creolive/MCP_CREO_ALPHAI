# 0.6.1 发布验收记录（2026-10-26）

范围：BUG-082 在轴扇形主平面 autodim 就地编辑修复、编辑回滚证据与 FEAT-030
种子回归驱动适配。用户要求审核剩余必要工作，无发布阻断则发布新版本。
公开工具仍为 92 个，未扩展生产建模功能。前一版为 0.6.0。

## 发布候选与检查

- 本次检查 BASE `1cbba11faccc1cf3510385229a9e8a6c4ecd07d0`，dirty=true（版本/文档修改与保留的本机
  文件）；受测语言源码 SHA256 `dc3c36698d7afe75513c49c07002182a9836616b06013365afe369b959dec8ac`。
- Windows 11 Enterprise x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 Toolkit SDK、
  MSVC。`tools/dev_check.py --work-item BUG-082` exit 0、success=true；
  **760 项单元测试，0 失败 0 错误**。增量风格通过，存量 30 lint / 17 未格式化
  文件未新增容许项，不声称全库严格风格通过。
- development_check.json SHA256 `4cf68d25158a2d283d4d9812b041afd1094834590cf1082239e5a124673724c9`；
  unit_test_report.json SHA256 `c968c72282ed7f3999ef6e380f9651b8b4cdd4c89ffd49ede556c8c236cf4632`；
  完整日志 build/release_061_dev_check.log SHA256
  `a66474029b4a830fb62398bb439ad6e96fc825aa2ee4217641997eb4b2e52ab5`。
- 版本入口、README 标题和版本段、开发入口、两份种子 manifest、种子包安装期望
  摘要同步 0.6.1；PRT 原字节未变。BUG-082 台账从旧“待根因修复”改为已修复范围，
  FEAT-030 按 15 个正向场景重新核数，剩余实机验证继续开放。
- 运行账本 session_activity.json 保留本机内容，本次 main 树保持原 main 内容；
  不把分支误带的运行记录增量纳入此次主干差异。客户端目录、session_erase 记录、
  测试模型均不入附件，不删除本机数据。

## 修复批实机证据的复用与边界

本次不重新连接 Toolkit、不操作 Creo、不清除保护。复用同日、断连前取得的本修复批
专项证据，不把 0.6.0 元数据下取得的报告改名为 0.6.1 新实机。相对修复提交
f54cda8，当前 native/、server.py 及 tools/test_editing_closeout.py 无后续业务差异；
本次仅版本/种子元数据及文档改变。原报告记录 BASE 83bd7b6、dirty=true，并未内嵌
当时完整源码指纹；这一缺口保留。本次回顾核对以修复记录、原生日志/响应行为、
保留的 worker 及源码一致性为证，不补造历史受测指纹。

- 原报告 build/editing-closeout/7134da5c214141f3bbdbb130f4fe36c4/report.json，
  SHA256 `daeeac19a51ede151e5a3c3cae69a79b5375df2dd5ea264260e30f9bc66110a6`。
  **16/16 CASE_PASS**，62 个不同终态作业：61 succeeded，1 预期非法开环 failed；
  61 个成功作业全部 `saved_file_reloaded_and_verified=true`。
- 失败作业 `7412f5e0e0274d9ba617d015262eedbe`：rollback_succeeded=true，
  failed_features 含 REV1 id51 status6。完整 before/after 快照相同：revision 1、
  status ready、无 pending/recovery，part/inspection/aliases SHA256 与特征 ID 不变；
  作业级 revision 缺失仍为 null，不推造数值。
- 回归含 BUG-079 离轴弧、BUG-062 中心线、legacy、reorder no-op、auto→autodim、
  autodim/auto 改角及改半径回程。显式 autodim 编辑响应记录 used=coordinates。
- 本次回顾取得的 native 快照 SHA256（按排序路径、NUL、LF 规范化文件字节串联，
  含 native 下 .cpp/.hpp/.h）为
  `320cedaa1f46e89105bf0dacaf83b9ed60b59530f330e8992436f0448889eb04`；
  留存 worker SHA256 `631c5314650415140f2f070301470018959a84f45ee7837399d1364a6fd1e529`。
  原因分析与具体接口边界见[根因记录](../development/BUG082-AUTODIM-ROOT-CAUSE.md)。

## 解包安装与原生编译

从本次候选公开源码预打包解压到 E:/Projects/md061-install-20261026/MCP_CREO_MechDog，
完整运行 setup.ps1，参数 Python=主仓 .venv/Scripts/python.exe、
CreoRoot=C:/Program Files/PTC/Creo 12.4.0.0、
VcVars64=C:/MCP_CREO_MechDog/vcvars64_local.cmd。exit 0：锁定依赖、editable 安装、
九种子哈希、SDK 常量重新生成、loader/callback/worker 编译全部成功。
未复制常量或二进制，未注册第二个 MCP 客户端，也未执行 Toolkit 探活/建模。
导入 version 与包元数据均为 0.6.1，creo_mechdog.__file__ 位于解包目录。
安装日志 build/release_061_install.log SHA256
`389fd1b95ea0af4633d7075e17d528533de7a6383500b44a51d1e4caccce77d5`。
正式包从 main 的 Git 源码快照生成，并逐文件与该提交核对；安装候选与正式包的代码
按 LF 规范化核对一致，新增发布记录与文档差异不改变已验收安装实现。

## 未测与环境问题

种子 smoke two_straight/two_smooth 已通过；矩阵 matrix_five_smooth 完整通过，
matrix_four_smooth 创建成功，但 SECTION datum 不驱动 Blend，驱动已适配真实草图
尺寸，该编辑闭环尚未完成。随后 worker exit20 / IPC 不可读，coordinator 两次显式
重试超时。驱动为 9+6=15 个正向场景，仅 1 个完整通过：尚缺 four 的编辑闭环、
其后 13 个正向场景及 2 个负例；第三次空汇总不代表通过，jobs 原件保留。
用户需人工检查 Creo 并满足 BUG-001 恢复纪律后再安排后续验证。

WorkBuddy 本批未执行；外部 Creo 9 未复测，本机无 Creo 9 SDK，实机编译与运行时
未验收；Creo 10 未独立复测且非门槛。本轮不重跑其他原生模块，不外推历史通过数。
非主平面或不受坐标模式支持实体的 autodim 编辑、外部 coordinates/半径失败、
半圆/球体基线、种子生产来源/重生成、BUG-034 与 BUG-078 等剩余问题继续按卡跟进。

## 主干、附件与远端核对

tag v0.6.1 指向本次实际 main 合并提交，最终两包由该提交的 Git 源码生成。
种子包 MCP_CREO_MechDog-0.6.1-seed-library.zip 的确定性 SHA256：
`d53e33cd47292ab8b2948344460583425191d3e5bef9c2d3e8031539dd3d4e6d`。
源码包、种子包及各自 .sha256 共四个附件。源码包含本文，不将其自身 SHA256 或
自身提交号写回包内造成循环，也不在发布后另造未随版交付的 main 提交。
实际 main 提交、源码包完整 SHA256、验收摘要和远端下载哈希结果，以
[GitHub Release v0.6.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.6.1)
正文及校验附件为交付记录。只有远端标签/Release/四附件核对完成才报告交付完成。
