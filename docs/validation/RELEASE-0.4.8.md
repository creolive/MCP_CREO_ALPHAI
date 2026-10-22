# RELEASE 0.4.8 发布核对（2026-10-22）

## 交付内容

0.4.6 反馈整合计划第一批（PATCH，无新增公开工具，工具数保持 90）：DEV-027 世代盘点口径补齐 + 三份外部反馈原件归档与证据补录 + DEV-045 命名核对结论。见[版本说明](../RELEASE_NOTES_0.4.8.md)与[盘点验证记录](DEV027-INVENTORY-2026-10-22.md)。

## 版本链

- 开发分支 `codex/dev044-feedback046` 提交 `8fcb1b2`（自 main `62e6654`，0.4.7 已发布）。
- 合入 main：merge 提交 `a92fa06` + 种子清单/expected digest 定版 `b99ce2f`。
- 标签 `v0.4.8` → `b99ce2f`（与该提交 `version.py` 一致）；远端 main 已推送至 `b99ce2f`。
- GitHub Release `420244170`（`MCP_CREO_MechDog 0.4.8`，Pre-release，非草稿）。

## 附件与 SHA256（Release body 直接列出，DEV-045 第 7 项）

- 源码包：`MCP_CREO_MechDog-0.4.8-source.zip`（745 文件）SHA256 `36830863df6b13c795d35aaf4b245147e7d6dc057fad6f4139b433a9e1fc1909`。
- 种子包：`MCP_CREO_MechDog-0.4.8-seed-library.zip`（24 文件、9 种子）SHA256 `1dd37e1e2dc746f8d5115973a6cfe51ac50c2fc2da24d658d8dbab371d816dcd`（与 `seeds.py` expected_digest 一致，种子内容较 0.4.7 未变）。
- 各附同名 `.zip.sha256`。

## 远端核对

- 四附件已上传（source 4,321,112 字节、seeds 493,394 字节、两个 sha256 文本）。
- 远端附件逐项下载复核：source/seeds 哈希与本地及 body 记载完全一致（REMOTE_VERIFY: PASS）。
- 发布后补录：本记录与回填提交在 Release 发布后进入 main，不改变 `v0.4.8` 标签与附件。

## 验收与环境

- 单元 539 项（含盘点新增 9 项）、`tools/dev_check.py` 通过；本机 Windows x64 / Creo Parametric 12.4.0.0 / E 盘 dev 服务（stdio 直连）实机验证盘点输出。
- 未测范围（随版披露，不外推）：`file_locked` 运行证据分支未在实机出现；外部 Win10/Creo 10 环境盘点复核、BUG-077 原环境（track_p01b 21.4MB）迁移复测、BUG-078（恢复 accept 路径 `ProMdlnameBackup` 稳定 -1）继续开放；485 条真实旧登记未批量迁移。
- 下一批次：FEAT-045 装配只读检查（新增 `creo_inspect_session_assembly`），按 MINOR 规则独立交付。
