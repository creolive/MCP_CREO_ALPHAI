# v0.4.6 发布核对记录

日期：2026-10-21。版本类型：PATCH（用户指定两批统一按 PATCH 发布，含新增公开工具作为本版例外，同 0.4.1/0.4.2 先例）。

- 版本与条目：0.4.6——[0.4.3 反馈完善计划](../development/0.4.3-feedback-improvement-plan-2026-10-21.md) 两批（BUG-076 资料分离精修、BUG-057 锁机制统一、FEAT-046 新工具 `creo_erase_session_models`、FEAT-043/044 会话可观察性、DEV-027 世代盘点 dry-run）+ DEV-043 台账精简；DEV-027/030 与 BUG-076 首批诊断已随 0.4.4/0.4.5 交付未重复。
- 提交/标签/受测源码：发版提交 `b553ab4`（直接提交 main，含全部工作区改动），tag `v0.4.6` 指向该提交；单测与实机验收时工作区 dirty（与提交内容一致，`build/development_check.json` 留源码指纹）。
- 环境：本机 Windows x64 / Python 3.12 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC；工具数 88。
- 命令与结果：
  - `python -m unittest discover -s tests`：502 项全部通过（新增 test_lock_files 9、test_adoption_split 7、test_session_erase 5）。
  - `tools/dev_check.py`：`success=true`，无新增语言问题；变更文件 ruff/clang-format 已格式化。
  - `bridge.py build`：SDK 构建通过（worker 链接新增 bcrypt.lib）。
  - 实机 `tools/test_general.py`：`GENERAL_CORE_SUCCESS=1`（几何断言 BRACKET_VOLUME=10600.0）。
  - 实机改动点冒烟（stdio 直连新 server 实例，[实施记录](FEEDBACK-0.4.3-IMPLEMENTATION-2026-10-21.md)）：open（loaded_session_models/is_current）、收养 inspect（summary+ref）→apply（revision=1）→查询兼容、擦除 blocked（managed）/available→apply→确认消失→重开成功、快照年龄字段。
  - 锁诊断双路径：三状态×双路径各 60 轮均恰好一方获准一方 busy；共享冲突保留 winerror=32、delete-pending 保留 5。
- 原生修改保存重载/参数编辑/回滚：test_general 覆盖保存重载与断言回滚；收养 apply 保存重载链路实机通过。
- 未测模块与限制：BUG-076 原 Creo 10 环境（超限文件类别/字节数/job 及部署身份）；BUG-057 外部 Win10 19045/Python 3.13.14 原环境重跑与双进程各 200 轮；擦除装配多级清单矩阵与幂等重放；`loaded_session_models` 装配打开实机观察；WorkBuddy 公开黑盒（建议发布后复核）。
- 源码包 SHA256：`680a93caf8394ac64a7fc3c084f1232fd3d68c89ca9b85e7f31edfa4fd94d38c`（706 文件）。
- 种子包 SHA256：`4d4a0578c7320e15906b3d962a3daf912ea6c661ec53cf17e9f449d2ee76b2fd`（与 `seeds.py` expected_digest 回填一致；seed_manifest compatible_server_version=0.4.6 双份同步）。
- 发布候选结论：达到发布门槛（单测/检查/构建/实机核心+改动点回归/打包核对），按用户指示发布；未测范围如实标注不外推。
- 合入 main 的提交与标签：`b553ab4` / `v0.4.6`（远端已推送）。
- GitHub Release：[v0.4.6](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.4.6)（Release 419338306，Pre-release，非草稿）。
- 远端附件与 SHA256 核对：双附件已上传（source 4,171,347 字节、seeds 493,394 字节），下载复核 SHA256 与本地完全一致；tag 指向远端 main 提交 `b553ab4`。
