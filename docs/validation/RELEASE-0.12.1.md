# 0.12.1 发布记录（2026-11-04）

- 条目：[DEV-068](../work-items/DEV-068.md)；PATCH，README 改版与版本元数据；公开工具仍 97，无业务代码或原生代码变更。
- 主干基线：`90dbd6c33e9f732d1a5bd969bcf19d30b4b3a62c`（0.12.0）；用户原 README 的 SHA256：`50cf4da5e07f2bfdf9a97fadbeff36c9a04b545b8fc65546358bf29424cfb08b`，来自未提交工作区。
- 目标版本：`version.py` = `0.12.1`；标签 `v0.12.1`；[目标 Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.12.1)。
- 交付核对：[PR #12](https://github.com/wudahua/MCP_CREO_MechDog/pull/12)，在同一流程内回填实际主干提交、验收报告、Release 与附件核对，不再为回填修改 main。

## 验收范围

Windows x64 / PowerShell / Python 3.12，运行 `tools/dev_check.py`；检查 README 本地链接、JSON/计划校验、公开工具及版本。源码包从交付源码构建并在新目录解压检查；种子包重建核对摘要和种子原字节。

本次未连接 Creo、未编译原生执行器、未运行建模/安装建模或 WorkBuddy 黑盒验收。Creo 9/10 与 BUG-001 既有未测事实保留；历史成功不计入本版。

## 附件与远端核对

发布四个文件：`MCP_CREO_MechDog-0.12.1-source.zip`、`MCP_CREO_MechDog-0.12.1-source.zip.sha256`、`MCP_CREO_MechDog-0.12.1-seed-library.zip`、`MCP_CREO_MechDog-0.12.1-seed-library.zip.sha256`。Release 正文直接列出两份 ZIP 的完整 SHA256。

为避免源码 ZIP 包含自身摘要造成循环依赖，最终主干提交、标签指向、附件大小/完整 SHA256、远端下载校验、`draft`/`prerelease` 状态在[PR #12](https://github.com/wudahua/MCP_CREO_MechDog/pull/12) 的“主干交付”中记录，并在 Release 正文提供 PR 链接。发布后不额外修改 main 来回填；已发布标签和附件不覆盖。

## 源码身份与检查记录

- 本次受检 Python/C++ 规范化源码指纹：`718c580766791877d1ae4f4050b0615312269ff8c07d2b61e8ab3e516ac4a7a1`；README 当前检出字节 SHA256：`22a090b5a85b23457e1dda63d98f9ccadb3e9d71cac16164b2a4f43719446a40`。实际受测提交与 dirty 状态、全量检查结果见 PR #12 的原始报告摘要。
- README 的 23 个本地链接、2 段 JSON、2 个计划操作及 34 个引用工具名已离线核对，公开工具登记数 97；标题/当前版本与 version.py 一致。
- 配套种子包：24 文件、9 种子，确定性重建 SHA256 `ede9e9f3f3dadb09928045ec14f045d40fef86260deca34ad8ed6de627b59cb5`；受信记录与两份清单一致。
- 初次复用其他 checkout 的环境导致 3 failures/24 errors；独立安装后剩缺配置与长路径 3 errors。短路径工作树与本地禁用自动启动配置补齐后重跑，最终结果以 PR 为准。主干 CI 原有的 2 项缺配置错误与后续模板路径依赖由本版测试隔离修复处理，见 DEV-068 的复现记录。
- 语言债务基线仍为 24 条 lint 与 13 个未格式化文件；不宣称全库严格格式清零。本轮无 native、src、tools 或运行入口实现修改；只调整两条离线单元测试的依赖夹具。
