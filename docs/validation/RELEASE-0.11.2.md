# MCP_CREO_MechDog 0.11.2 发布记录

发布日期：2026-11-02。版本：`0.11.2`（PATCH）。条目：[DEV-060](work-items/DEV-060.md)（R10 归档与交付）、[BUG-101](work-items/BUG-101.md)、[BUG-102](work-items/BUG-102.md)、[BUG-103](work-items/BUG-103.md)、[DEV-061](work-items/DEV-061.md)、[FEAT-035](work-items/FEAT-035.md) 增量。版本说明：[RELEASE_NOTES_0.11.2.md](../RELEASE_NOTES_0.11.2.md)。

## 交付内容

- 三份 v0.10.0 第十轮反馈原件逐字节归档（3/3 长度与 SHA256 一致）+ 逐章映射，与晚间包 `feedback-0.10.0-2026-11-01` 并存不合并。
- 草图 `profile.weldability` 风险标记（阈值 1e-9 mm 已测安全界，只报告不拒绝）+ 原生拉伸失败簇内间隙归因。
- `draft_geometry.requested_flip`/`effective_flip` + 失败 `draft_failure`（分类 + 元素证据 + 下一步）。
- 孔 `depth_basis`/`depth_scheme_code`/`depth_scheme_query`（特征树实读，普通直孔 null）。
- 种子摘要仓库级闸门（`assert_repo_record_matches`、`package_seeds` 默认校验、`test_seed_record_gate`）。
- 台账 150→155 行、155 唯一 ID；示例/README 壁面口径纠偏。

## 验证

### 离线与静态

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 全量单元测试 | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | **2 131 项，OK，0 失败** |
| 开发检查 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item R10` | `success=true`、`unit_tests=passed`、样式无回归（未改 baseline） |
| 受测源码指纹 | `build/development_check.json` | `3febe52707a5de11535f93a6d3302699f5a6c55626e617ddefd5dcfe70accb95` |
| 原生构建 | `.\.venv\Scripts\python.exe bridge.py build` | exit 0，`build/creo_worker.exe`，`build/source.sha256=ffe75d9b8cfee046e4436714280ded1df28df1a45c056fe379959e98bf889b16` |
| 可焊性离线驱动 | `tools/test_endpoint_weld_gate.py` | PASS（6 组间隙样本） |
| draft 离线驱动 | `tools/test_draft_regression.py` | PASS（四变体与失败回执字段） |
| 种子闸门 | `tools/package_seeds.py --output …` | 仓库记录与重建一致（`e8f68aaa…`），默认校验通过 |

### 本机实机（Windows x64 / Creo 12.4.0.0 / 匹配 SDK，用户 2026-11-02 授权）

| 用例 | 结果 |
| --- | --- |
| 草图 8.21534262415399e-7 mm 间隙 + 拉伸 5 mm | `succeeded`（**未复现**报告方 Creo 10 的 `-1`）；`profile.weldability.weldable=false`、`exceeding_pairs.total=1`（`s0`/`s3`） |
| 吸附对照 7.83e-13 mm + 拉伸 5 mm | `succeeded`，体积 500.0 mm³ |
| 40×30×10 方块，素面侧边 10° 拔模 `flip=false` | `succeeded`，`requested_flip=false`、`effective_flip=true`、`material_delta_mm3=+264.490471` |
| YZ 底板（offset 92.5、单线、depth 185、thickness 1、negative） | 体积 42920.0 mm³；四条下边 104/105/106/107 全部 `eligible`（`query_code=0`），另有 122/123/125/127 `ineligible`（−8） |
| 对报告方失败边 106 挂 `creo_sheetmetal_flange(height=80, radius=2.54, y_factor=0.5)` | `succeeded`，体积 57293.615854821175 mm³，无回滚 |

驱动报告：`build/r10_live/20261102T171745/report.json`（含 `report.sha256`）、`build/r10_live/20261102T172228/report.json`、`build/r10_live/*_flange/report.json`；这些为临时实机探针（脚本在 `build/`，不入库），结论已回填到工作卡。

## 附件

| 附件 | 大小 | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.11.2-source.zip` | 1200 files | `942fcf0b21a91292e01234aa77d344c49f1fa86241904e66cbfb932ae65b977e` |
| `MCP_CREO_MechDog-0.11.2-seed-library.zip` | 24 files / 9 seeds | `e8f68aaa18cd5884cacca36fd04ff6846284d88eae7d633b1a403e46e7bacebd` |

种子包摘要已回填 `docs/seed_package.json` 并二次重建一致；源码包由同一提交源码生成，`tools/package.py --seed-archive` 受信摘要闸门通过。

## 未验证范围

- 报告方环境的 Creo 10 现象（8.2e-7 `-1`、四边仅短边可挂）本机不可复现，跨版本差异未定因；`gear10` 原件仍缺。
- 带 chamfer+R3 的 10° 拔模失败与 `PRO_E_DRAFT_*` 元素树 A/B 未执行。
- 盲孔 custom 盲孔的 `depth_basis=tip` 实机回执未单独验证。
- 原生“簇内间隙”失败文案未被实机命中（本机无失败样本）。
- Creo 9 / Creo 10 实机、WorkBuddy 黑盒未执行；四壁与角部 relief 仍不支持。

## 交付核对

- 分支：`codex/DEV-060-r10-followup`；本记录随合入提交进入主干。
- 合入提交、标签 `v0.11.2`、Release 链接与远端附件逐件哈希核对结果见下节“发布动作回填”。

## 发布动作回填

- 合入提交：`76ddb83`（`main` 上 `--no-ff` 合并 `codex/DEV-060-r10-followup`，已推送 `64e28f1..76ddb83`）；本记录与本节回填提交（`0b6fbca` 及后续发布回填）只改文档，不涉及 `v0.11.2` 附件内容。
- 标签：`v0.11.2`（指向 `76ddb83`，已推送 `* [new tag] v0.11.2`）。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.2>（Release id **431347397**；`draft=false`、`prerelease=false`；tag `v0.11.2`；创建于 2026-11-02T10:30:19Z）。正文列出两个 ZIP 的文件名与完整 SHA256，并附实机验收摘要、环境、未测范围与升级说明。
- 远端附件哈希核对（正文记载与远端附件逐项一致）：四附件均 `state=uploaded` —— `MCP_CREO_MechDog-0.11.2-source.zip` `sha256:942fcf0b…`（7 122 125 字节 / 1200 files）、`MCP_CREO_MechDog-0.11.2-seed-library.zip` `sha256:e8f68aaa…`（493 442 字节 / 24 files / 9 seeds），另有两份 `.sha256` sidecar（`2831b538…` / `1159c00a…`），sidecar 本地哈希与远端记录一致。
- 前置故障与恢复：2026-11-02 `gh auth login --web` 首次因 device-code 端点 TCP 超时失败（`wsarecv`，代理直连探测均 200），重试后登录成功（账号 `118119019`，scopes `gist, read:org, repo, workflow`，对仓库 `WRITE`）；随后以 `gh release create --verify-tag` 创建，未重建标签、未改动已推送提交与正文之外的历史发布。
- 本地生成物（Release 正文、四附件）保留在 `E:\Projects\release-0.11.2\`（仓库外，不入库）。
