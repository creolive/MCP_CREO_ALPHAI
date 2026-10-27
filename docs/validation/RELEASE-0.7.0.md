# 0.7.0 发布验收记录（2026-10-27）

范围：DEV-047（0.5.2 三份外部反馈完整交付，T00—T13）。用户 2026-10-27 明确指派
最终交付后执行安装冒烟与 0.7.0 发布。前一版为 0.6.1；MINOR（新增公开工具
`creo_plan_assembly_rebuild`、`creo_reclaim_generations`，92→94）。

## 发布候选与检查

- 候选 BASE 为集成分支 `codex/dev047-feedback052` 版本定稿提交（含本记录），
  dirty=true（仅保留的本机运行文件与未跟踪目录）；`tools/dev_check.py --work-item
  DEV-047` exit 0、success=true，966 项单元测试 0 失败 0 错误（独立复跑
  212.532 秒）。增量风格通过，存量 30 lint / 16 未格式化文件未新增容许项，不声称
  全库严格格式通过。`python bridge.py build` 复用/重编 worker 成功。
- development_check.json SHA256
  `f137ea77dc31067616abc185bc0d818c428fe665befccefde445cc8fdf684cec`；
  独立全量日志 build/release_070_unit.log SHA256
  `2927043ff298e4a56918713f7a418024e21509e9aedcc53bf54e72cd8193e745`；
  dev_check 日志 build/release_070_dev_check.log SHA256
  `fb5404e607a8281fcaf5c9e94511cde83dd40df6425b49f83c3c46c9cddb17eb`。
- 版本入口、README 标题与版本段、开发入口、兼容矩阵、两份种子 manifest
  （`compatible_server_version`）同步 0.7.0；9 个种子 PRT 原字节不变；
  `seeds.py expected_digest` 更新为新种子包实测 SHA256。

## 本版实机证据与边界（复用同源码事实）

本发布检查本身不重新连接 Toolkit、不操作 Creo、不清除保护。生产代码相对实机矩阵
基线（T13 集成提交 `55d95f3`）的唯一差异为 T05 收尾的收养拒绝单位元数据修复
（`adoption._refusal_details`，attempt-03 实机暴露、attempt-05 在最终源码上验证）；
其余为版本/文档/驱动变更。矩阵事实：

- T05 毫米几何矩阵 18/18（build/t05-native-05.json）、英寸只读覆盖 attempt-05
  （build/t05-units-live-05.json，SHA256 `38b00c9bee5e842a4a39d66cb97037ec6c767c6711abd1c096b639fcf10dd77b`）；
  T06/T07/T08/T09/T12 驱动实机通过（[T13 阶段记录](../development/DEV047-T13-ACCEPTANCE-2026-10-26.md)）；
  装配单位专项离线+实机复跑（38 作业）通过；T07 留存图目视复核通过。
- BUG-078 三现场只读落定（仅 `restore_baseline` 可用，未 apply、未清保护）；
  T11 真实世代只读盘点，删除仅隔离夹具。成功作业均
  `saved_file_reloaded_and_verified=true`；预期失败作业均 `rollback_succeeded=true`。
- 实机共修复五处生产缺陷：T13 四处（`system_required` 误标、抑制/删除隐式级联
  未拦截、whole 快照缺 `feature_state` 段、回放逐约束生成）+ T05 收尾一处
  （拆分形态拒绝单位元数据降级 unknown）。失败尝试原始报告全部保留于 build/。

## 解包安装与原生编译

从 0.7.0 候选公开源码包（920 文件）解压到
`E:/Projects/md070-install-20261027/MCP_CREO_MechDog`，完整运行 `setup.ps1`
（参数 Python=主仓 .venv、CreoRoot=Creo 12.4.0.0、VcVars64=本机脚本）exit 0：
锁定依赖、editable 安装（wheel `mcp_creo_mechdog-0.7.0-…-editable`）、九种子
SHA256 复核、SDK 常量重新生成、loader DLL 重编与 worker 编译全部成功。用解包
目录自有 `.venv` 导入验证：`version.VERSION=0.7.0`，
`creo_mechdog.__file__` 位于解包目录。安装日志 build/release_070_install.log
SHA256 `f97ab5516465a5fe9fc81564eccc03d2c8e1de15a1ab7ba718fa3e6f384cad7e`；未复制常量或二进制，未注册第二个 MCP
客户端，未执行 Toolkit 探活/建模。正式包从 main 合并提交的 Git 源码生成并逐文件
核对；安装候选与正式包代码按 LF 规范化核对一致。

## 未测与环境问题

WorkBuddy 按用户 2026-10-26 决定本批不执行；外部 Creo 9（本机无 SDK，实机编译与
运行时未验收）与 Creo 10（独立复测非门槛）未复测；unknown 单位/查询失败仅替身与
单元覆盖（健康实机会话不可无注入诱导）；BUG-078 恢复动作未 apply（操作者选择）；
BUG-066 原始失真未复现；FEAT-050 公共比对、嵌套回放、新约束类型、世代二进制
可复现性等父卡其余范围不在本批。旧版本通过数不外推为本版通过。

## 主干、附件与远端核对

种子包 `MCP_CREO_MechDog-0.7.0-seed-library.zip`（24 文件/9 种子）确定性 SHA256：
`515ef9d356a6d5582879fc736c43d0a7408fc15915605f04ded2bb5f991fd114`。源码包、
种子包及各自 .sha256 共四个附件；源码包含本文，不将自身 SHA256 或提交号写回包内
造成循环。tag `v0.7.0` 指向本次实际 main 合并提交，最终两包由该提交的 Git 源码
生成。实际 main 提交、源码包完整 SHA256、验收摘要和远端下载哈希核对结果，以
[GitHub Release v0.7.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0)
正文及校验附件为交付记录；只有远端标签/Release/四附件核对完成才报告交付完成。
