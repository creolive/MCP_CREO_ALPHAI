# MCP_CREO_MechDog 0.18.2 版本说明

发布日期：2026-11-07。性质：PATCH（离线反馈修复与发布规范补记）。公开工具数量不变：**102**。

## 本版变更

- **`DEV-075` / `DEV-066`（部分）：源码包无 `.git/` 时不再中断证据驱动。** `tools/test_t07_preview.py` 及其余离线驱动的来源记录改为共享实现 `creo_mechdog.git_evidence`：git 可用时输出与旧版一致，并新增 `provenance_mode="git"`、`git_unavailable=false`；git 缺失或目录非仓库时降级为文件系统遍历，`commit`/`branch` 记空、`dirty` 记 null、`git_unavailable=true`，报告照常写出。官方 `source.zip` 内的 `tests.unit.test_t07_preview` 不再出现 13 项 ERROR。
- **发布门禁补齐。** `RELEASING.md` 第 5 步新增「官方 `source.zip` 解压后跑同一份全量单测」独立门禁，与 git 工作树结论分开记录；第 8 步逐 ID 清单纳入 `RELEASING.md`「当前版本为 X」行。
- **附件回退通道。** `creo_mechdog.release_download`（`tools/check_release_assets.py` 的 API 回退）在 `browser_download_url` 不安全或 `github.com` 直连失败、且资产带正整数 `id` 时，改用 `https://api.github.com/repos/<repo>/releases/assets/<id>` 并带 `Accept: application/octet-stream`；仍只接受四个安全文件名并校验 sidecar。两条通道都失败时同时报告两段原因。
- **发布后记录。** 新增 [RELEASE-POSTCHECK-2026-11-07](development/RELEASE-POSTCHECK-2026-11-07.md)，用 `check_release_assets.py --tag` 实际重下并重算 v0.17.4/v0.18.0/v0.18.1 的四个附件（exit 0、sidecar 一致）；`RELEASING.md` 的逐 ID 核对表按本版实际交付填写。
- **文档修正。** [RELEASE-0.18.0](validation/RELEASE-0.18.0.md) 回归行列的 `tests/unit/test_hole_standards.py` 更正为实际文件 `tests/unit/test_standard_holes.py`；[FEAT-059](work-items/FEAT-059.md) 与主台账改为「已交付 0.18.0 子项；剩余范围未排期」；0.17.4 历史段的「离线门禁 2744 项」标注为 DEV-072 单批合并前快照（合入 0.17.3 后组合源码 2762 项）。

## 兼容性与升级

- 服务标识、MCP 工具名、计划 schema 与种子目录格式不变；无需改客户端配置。
- 种子包与源码包按同一版本成对发布，`common` 清单的 `compatible_server_version` 为 `0.18.2`。旧版 0.18.1 种子包仍可被 0.18.2 服务读取，但发布附件以新版为准。
- 证据报告的 `provenance` 块新增两个键；旧消费方按未知键忽略即可。`dirty` 在无 git 环境下为 null，不再是布尔值。

## 验证范围

- 离线门禁：工作树全量单测 0 失败 0 错误；官方 `source.zip` 解压到无 `.git/` 目录后全量单测 0 失败 0 错误（本次新增门禁）；`tools/dev_check.py` 语言与单测检查通过。
- 代码审查：本次无原生代码改动，未重新编译执行器，未连接 Creo/Toolkit，未启停 Creo，未改动注册表或保护状态。
- 未验证：Creo 9/10/12 实机建模与保存重载（本批为纯 Python 与文档修复）；其余 `tools/` 驱动在无 git 环境下的行为仅按 DEV-066 登记，未逐项改造。

## 附件

- `MCP_CREO_MechDog-0.18.2-source.zip` 与 `.sha256`
- `MCP_CREO_MechDog-0.18.2-seed-library.zip` 与 `.sha256`

发布后核对结果见 [0.18.2 发布记录](validation/RELEASE-0.18.2.md)与[发布后附件核对](development/RELEASE-POSTCHECK-2026-11-07.md)。
