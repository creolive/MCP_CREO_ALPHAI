# GitHub 更新与源码发布

未来发布遵循 [分支与版本规则](development/RELEASING.md)。下述 0.2.5 文件名和操作保留为历史示例；已发布标签及同名附件保持不变，新改动通过新版本发布。

当前成果版本为 **v0.2.5**。本地生成了源码 ZIP、九种子 ZIP、两份 SHA256，以及可直接上传的公开源码目录。本地打包不修改 GitHub；历史标签和附件可以保留。

## 发布附件（所有新版本固定四个）

每个版本的 Release 附件都必须是四个文件，其中两个 `.sha256` sidecar 由打包脚本在 ZIP 同目录生成：

- `MCP_CREO_MechDog-<版本>-source.zip`
- `MCP_CREO_MechDog-<版本>-source.zip.sha256`
- `MCP_CREO_MechDog-<版本>-seed-library.zip`
- `MCP_CREO_MechDog-<版本>-seed-library.zip.sha256`

sidecar 内容为一行 `<64 位 SHA256>  <ZIP 文件名>`。上传时逐个列出四个文件名，不要用 `*.zip` 通配（会漏掉 sidecar）：

```powershell
gh release create v<版本> `
  MCP_CREO_MechDog-<版本>-source.zip `
  MCP_CREO_MechDog-<版本>-source.zip.sha256 `
  MCP_CREO_MechDog-<版本>-seed-library.zip `
  MCP_CREO_MechDog-<版本>-seed-library.zip.sha256 `
  --title "MCP_CREO_MechDog <版本>" --notes-file <Release 正文文件>
```

上传后运行 `python tools\check_release_assets.py --tag v<版本>`（或 `gh release view <tag> --json assets`）核对四个附件齐全、sidecar 哈希与对应 ZIP 摘要一致；缺任何一个 sidecar 都视为未完成发布。0.11.7 与 0.12.0 曾只上传两个 ZIP，属于该缺口，新版本不得重复。

## 更新仓库文件

1. 使用 `MCP_CREO_MechDog-0.2.5-github-upload` 内的**内容**更新仓库根目录。根目录应直接看到 `README.md`、`server.py`、`setup.ps1`，不要再包一层目录，也不要把整个源码 ZIP 当成仓库源码上传。
2. 同步所有公开文件与目录，包括 `native/`、`tools/`、`tests/`、`examples/`、`docs/` 和完整 `seed_library/`。用 Git 或 GitHub Desktop 更新整个目录更便于核对；网页上传时可分批提交。[GitHub 上传文件说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
3. 提交说明可填写 `Release v0.2.5: native Blend, sketch stability and nine seeds`。不要上传本机 `config.json`、`client-config.json`、`.venv/`、`build/`、`jobs/`、`models/` 或 SDK/许可材料。
4. 检查根目录 `version.py` 为 `VERSION = "0.2.5"`；两个种子清单版本一致，均有九个条目。新 PRT 原文件名及 `.prt.N` 后缀保持不变。

## 新建 Release

仓库源码更新完成后，新建标签 **v0.2.5**，选择包含本次源码的提交。标题填写 **MCP_CREO_MechDog v0.2.5 — MIT 源码与九种子库**，说明使用 [RELEASE_NOTES_0.2.5.md](RELEASE_NOTES_0.2.5.md) 的内容。完整 Creo 覆盖尚未完成，建议保持 **Pre-release**。

0.2.5 历史示例的上传清单（文件名按当时版本；新版本按上节规则）：

- `MCP_CREO_MechDog-0.2.5-source.zip`
- `MCP_CREO_MechDog-0.2.5-source.zip.sha256`
- `MCP_CREO_MechDog-0.2.5-seed-library.zip`
- `MCP_CREO_MechDog-0.2.5-seed-library.zip.sha256`

源码 ZIP 已内附九个种子；独立种子 ZIP 是迁移用途，不是额外必需下载。只有仓库也包含 `seed_library/` 时，GitHub 自动生成的 Source code ZIP 才包含这些 PRT；附件内容不会自动加入仓库。旧 v0.2.4 三种子附件保留为历史，不能替代新版库。发布操作见 [GitHub 官方说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。

## 用户升级

等待正在运行的任务完成，停止客户端中的 MCP 服务，保留本机配置、`models/` 和 `jobs/`，更新公开源码并重跑 `setup.ps1`。重启客户端，检查 `creo_capabilities.version == "0.2.5"`、80 个可用工具及九个种子。安装与跨电脑说明见 [INSTALL.md](INSTALL.md)、[MIGRATION.md](MIGRATION.md)。
