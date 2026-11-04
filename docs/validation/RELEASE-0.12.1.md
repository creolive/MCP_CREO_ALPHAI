# 0.12.1 发布记录（2026-11-04）

- 条目：[DEV-068](../work-items/DEV-068.md)；PATCH，README 改版与版本元数据；公开工具仍 97，无业务代码或原生代码变更。
- 主干基线：`90dbd6c33e9f732d1a5bd969bcf19d30b4b3a62c`（0.12.0）；用户原 README 的 SHA256：`50cf4da5e07f2bfdf9a97fadbeff36c9a04b545b8fc65546358bf29424cfb08b`，来自未提交工作区。
- 目标版本：`version.py` = `0.12.1`；标签 `v0.12.1`；[目标 Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.12.1)。
- 当前阶段：离线检查与附件准备。验收及发布后更新状态。

## 验收范围

Windows x64 / PowerShell / Python 3.12，运行 `tools/dev_check.py`；检查 README 本地链接、JSON/计划校验、公开工具及版本。源码包从交付源码构建并在新目录解压检查；种子包重建核对摘要和种子原字节。

本次未连接 Creo、未编译原生执行器、未运行建模/安装建模或 WorkBuddy 黑盒验收。Creo 9/10 与 BUG-001 既有未测事实保留；历史成功不计入本版。

## 附件与远端核对

发布四个文件：`MCP_CREO_MechDog-0.12.1-source.zip`、`MCP_CREO_MechDog-0.12.1-source.zip.sha256`、`MCP_CREO_MechDog-0.12.1-seed-library.zip`、`MCP_CREO_MechDog-0.12.1-seed-library.zip.sha256`。Release 正文直接列出两份 ZIP 的完整 SHA256。

为避免源码 ZIP 包含自身摘要造成循环依赖，最终主干提交、标签指向、附件大小/完整 SHA256、远端下载校验、`draft`/`prerelease` 状态在本次 PR 的“主干交付”中记录，并在 Release 正文提供 PR 链接。发布后不额外修改 main 来回填；已发布标签和附件不覆盖。
