# v0.4.7 发布核对记录

日期：2026-10-22。版本类型：PATCH（用户 2026-10-21 指定，含新增两个公开工具作为本版例外，同 0.4.1/0.4.2/0.4.6 先例，工具数 88→90）。

- 版本与条目：0.4.7——BUG-077 注册表拆分与迁移（`model_registry` 控制记录+内容寻址 sidecar、`creo_migrate_registry`、收养冲突扫描改控制记录、reconcile 预算错误结构化、请求侧详情引用化、`run_drawing` 与 `owned_file` 图纸消费点修复、test_general 适配结果摘要化结构）、FEAT-047 只读 `creo_registry_health`、DEV-044 计划整合与 DEV-045 Release body 双包 SHA256 固化；BUG-078（恢复 accept 路径 ProMdlnameBackup 稳定 -1）随版登记并披露，不阻断发布决策。
- 提交/标签/受测源码：主干合并提交 `d23866a`（merge `codex/bug077-registry-split`，分支头 `5df1509`），tag `v0.4.7` 指向该提交；单测与实机验收基于分支 `5df1509` 工作区（内容与合并结果一致），`build/development_check.json` 留源码指纹。
- 环境：本机 Windows x64 / Python 3.12 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC；工具数 90。
- 命令与结果：
  - `python -m unittest discover -s tests`：530 项全部通过（新增 test_model_registry 等）。
  - `tools/dev_check.py`：`success=true`，无新增语言问题（`tools/test_general.py` 变更后 ruff format 通过）。
  - `bridge.py build`：SDK 构建通过（含 drawing.cpp 引用化修复）。
  - 实机 `tools/test_general.py`：`GENERAL_CORE_SUCCESS=1`、7/7 用例（BRACKET_VOLUME=10600.0；体积断言改读 `inspection_summary`、bbox/特征经模型快照分节、plate 独立工具保持内联断言）。
  - 实机专项（0.4.7 五组验收）：[>16 MiB 超限迁移→收养→编辑](BUG077-OVERSIZE-MIGRATION-2026-10-21.md)、[恢复链路四动作矩阵](BUG077-RECOVERY-2026-10-22.md)、[图纸引用消费点](BUG077-DRAWING-2026-10-22.md)、[health 预警/损坏/超限/32 KiB](BUG077-HEALTH-2026-10-22.md)，另有 [WorkBuddy 黑盒](WORKBUDDY-0.4.7-2026-10-21.md)与[小型非空迁移](WORKBUDDY-0.4.7-NONEMPTY-2026-10-21.md)。
- 原生修改保存重载/参数编辑/回滚：超限迁移后直径 16→20/20→22/22→24 编辑保存重载 verified（revision 1→4）；图纸编辑链 rev 2→4 每步保存重载 verified；restore_baseline×2 与 abandon_new 恢复收尾实机通过；编辑失败回滚路径多轮真实观测（含回滚不完全进入恢复通道的边界）。
- 未测模块与限制：BUG-078 accept_saved/accept_live 实机不可用（dirty 现场三模型保护挂起）；编辑路径同日 3 次偶发 `ProMdlnameBackup -1` 未定位；外部 Creo 10 原环境（track_p01b 21.4 MB）复测；Creo 9 实机；DEV-027 二进制可复现性与目录安全回收；WorkBuddy 对图纸修复与本批 health 场景的黑盒复核；485 条真实历史旧登记未批量迁移。
- 源码包：`MCP_CREO_MechDog-0.4.7-source.zip`（737 文件）SHA256 `d8550540751deec739d99dc6e19ec862af858f3a1c98dfcee2e9bcd7e6feeb0a`。
- 种子包：`MCP_CREO_MechDog-0.4.7-seed-library.zip`（24 文件、9 种子）SHA256 `5f91b8d2c0b2c65e274d13405fc4edfd8d483e212e205b45306f00c535659b74`（与 `seeds.py` expected_digest 一致，种子内容较 0.4.6 未变）。
- 两包均由 tag 指向的主干提交 `d23866a` 工作区生成（merge 后在 main 重打）。
- 发布候选结论：达到发布门槛（单测/检查/构建/实机核心+专项五组/打包核对），已知缺陷 BUG-078 及未测范围如实披露不外推。
- 合入 main 的提交与标签：`d23866a` / `v0.4.7`（远端已推送，`e3a7480..d23866a`）。
- GitHub Release：[v0.4.7](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.4.7)（Release 420203117，Pre-release，非草稿；body 含两包文件名与完整 SHA256）。
- 远端附件与 SHA256 核对：双附件已上传（source 4,290,379 字节、seeds 493,394 字节），下载复核 SHA256 与本地及 body 记载完全一致。
- 发布后补录：本记录与回填提交在 Release 发布后进入 main，不改变 `v0.4.7` 标签与附件。
