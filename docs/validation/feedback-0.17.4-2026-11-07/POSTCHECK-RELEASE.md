# 0.17.4 与后续版本远端发布后独立核对（2026-11-07）

本文件补 [DEV-074](../development/DEV-074-HANDOFF.md) H11：0.17.4 与当前版本的远端 tag / main / Release / 四附件 / body 此前未由本机独立核对，`release_download` 的 GitHub API asset-ID 路线只在离线 mock 中验证过。本轮为**只读**核对：不修改生产代码、不连接 Creo、不提交 git、不改动本目录既有 `originals/` 与 `manifest.json`。

- 查询窗口：2026-11-07 18:50–19:00（Asia/Shanghai，UTC+08:00）；最后一条核查命令完成于 2026-11-07T18:59:20+08:00（10:59:20Z）。
- 仓库：`e:\Projects\MCP_CREO_MechDog`，分支 `codex/DEV-074-feedback0174-offline`，HEAD `828b1f2`。
- 远端：`https://github.com/wudahua/MCP_CREO_MechDog`；`refs/heads/main` = `43862f00237d1aac34bce5cc1e576e2424c3ba39`。
- 工作树状态：核对开始时仅 `docs/work-items/DEV-054.md` 修改与 `.trae/` 未跟踪；19:00 前复查发现 `native/planar_wall.cpp`（18:59:15）、`tools/test_*.py`（18:57 起）等并发改动，时间戳落在本轮窗口内但**非本轮产生**——本轮只新建本文件并写 Git 忽略的 `build/release-postcheck/`。核对对象是远端已发布对象，不受该工作树改动影响。
- **版本口径注意**：本分支 `version.py` 为 `0.18.0`，且本分支不含 main 上的 `v0.18.1`/`v0.18.2` 提交；远端最新正式版本是 `v0.18.2`（main HEAD 即其合并提交）。因此本轮把 `v0.17.3`、`v0.17.4`、`v0.18.0`、`v0.18.1`、`v0.18.2` 全部纳入。
- 网络：`https://api.github.com/rate_limit` 直连 200、经 `http://127.0.0.1:10808` 代理亦 200；`gh` 已登录（`118119019`，scopes 含 `repo`）。全程未安装新软件。

## 1. 命令与输出（本机本轮实测）

| # | 命令 | 退出码 | 输出摘要 |
| --- | --- | --- | --- |
| C1 | `python tools/check_release_assets.py --tag v0.17.4 --version 0.17.4` | 0 | `v0.17.4: four assets downloaded and verified; both sidecars match` |
| C2 | `python tools/check_release_assets.py --tag v0.17.3 --version 0.17.3` | 0 | `v0.17.3: four assets downloaded and verified; both sidecars match` |
| C3 | `python tools/check_release_assets.py --tag v0.18.0 --version 0.18.0` | 0 | `v0.18.0: four assets downloaded and verified; both sidecars match` |
| C4 | `python tools/check_release_assets.py --tag v0.18.1 --version 0.18.1` | 0 | `v0.18.1: four assets downloaded and verified; both sidecars match` |
| C5 | `python tools/check_release_assets.py --tag v0.18.2 --version 0.18.2` | 0 | `v0.18.2: four assets downloaded and verified; both sidecars match` |
| C6 | `git ls-remote --tags origin` | 0 | `v0.17.3`/`v0.17.4`/`v0.18.0`/`v0.18.1`/`v0.18.2` 均有 `^{}` 剥离行（附注标签）；`v0.17.0`/`v0.17.1` 无剥离行（轻量标签，未纳入本轮核对） |
| C7 | `gh api repos/wudahua/MCP_CREO_MechDog/releases/tags/<tag>` ×5 | 0 | 5 个 Release 均非草稿、非 Pre-release，各恰 4 个 `uploaded` 附件且带 `sha256:` digest |
| C8 | `gh api repos/wudahua/MCP_CREO_MechDog/git/ref/tags/<tag>` ×5 | 0 | 5 个 `object.type` 均为 `tag`（附注标签对象），非直接指向提交 |
| C9 | `python build/release-postcheck/apicheck.py v0.17.3 v0.17.4 v0.18.0 v0.18.1 v0.18.2` | 0 | 走 `https://api.github.com/repos/.../releases/assets/<id>`（`Accept: application/octet-stream`）实下 20 个文件，逐件本地 SHA256 与 sidecar、API digest 三方一致；5 次 `validate_directory: PASS` |
| C10 | `python build/release-postcheck/bodycheck.py` / `zipcheck.py` | 0 | body 小节与 SHA256 字面值比对；源码包内 `version.py`、种子包内 `seed_manifest.json` 版本比对 |

C9 的临时脚本与下载件位于 Git 忽略的 `build/release-postcheck/`（本机生成物，不入库）。

## 2. tag 与 main

| tag | 标签对象 | 指向提交 | 提交在 main 上 | Release | 发布时间（UTC） |
| --- | --- | --- | --- | --- | --- |
| v0.17.3 | `11bc878`（附注） | `08a7970` | 是 | 437325183，非草稿/非预发布 | 2026-11-07T04:16:20Z |
| v0.17.4 | `33070fc`（附注） | `b57dbda` | 是 | 437358349，非草稿/非预发布 | 2026-11-07T05:24:16Z |
| v0.18.0 | `ba2c580`（附注） | `58dd76b` | 是 | 437402966，非草稿/非预发布 | 2026-11-07T07:04:07Z |
| v0.18.1 | `83dfdb2`（附注） | `9d72569` | 是 | 437451848，非草稿/非预发布 | 2026-11-07T08:53:07Z |
| v0.18.2 | `4c659f5`（附注） | `43862f0` | 是（= main HEAD） | 437496513，非草稿/非预发布 | 2026-11-07T10:18:16Z |

对应合并提交主题依次为 PR #18–#22。标签指向的提交全部是 main 上的合并提交，无错指。

## 3. 四附件与哈希三方比对（本机本轮实测）

「本地」= 经 API asset-ID 端点下载后重算的 SHA256；「sidecar」= 同名 `.sha256` 文本内摘要；「API」= Release API `assets[].digest`。

### v0.17.4

| 附件 | 字节 | 本地 / sidecar / API | 结论 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.17.4-source.zip` | 8 382 351 | `8f8f649c2d7c8420145d23a79f1f0749a525bae4f5f348a97401b71fea4fbc09`（三者一致） | PASS |
| `MCP_CREO_MechDog-0.17.4-source.zip.sha256` | 101 | `34e00b85164135df86fdab798dfa39b413e33a45581618c829f75ca2d9652bd8`（本地=API） | PASS |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip` | 493 442 | `a6c633b49cb243ca1f58e6f3b8756f30a9e0b32eefebcc0e185bec1bd79a3583`（三者一致） | PASS |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip.sha256` | 107 | `f53acf87a22b9641d9ae2d8b732993451b3ecc05d0ef760150b0c3b23e3e64b2`（本地=API） | PASS |

sidecar 内文件名分别为 `MCP_CREO_MechDog-0.17.4-source.zip`、`MCP_CREO_MechDog-0.17.4-seed-library.zip`，与被摘要文件同名。

### v0.18.0

| 附件 | 字节 | 本地 / sidecar / API | 结论 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.18.0-source.zip` | 8 485 592 | `dab4ca04ee58ae643e4e492ef3870d04d8724921c57be8e554c96136ee874849`（三者一致） | PASS |
| `MCP_CREO_MechDog-0.18.0-source.zip.sha256` | 101 | `3c4bd463dadc967eba2d3fd52f66b8c2998bb4d0186834ff811fef731fed9dfa`（本地=API） | PASS |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip` | 493 442 | `b6acab41fd727bb555ec6bb825116df2eab1e81e214db1c7c804e4f5e709a05b`（三者一致） | PASS |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip.sha256` | 107 | `02c3823da9f59a745b3a3685c82d7342abf24d95b4260ffa06d046aa6069b51b`（本地=API） | PASS |

### v0.17.3 / v0.18.1 / v0.18.2（摘要）

| tag | source.zip 字节 / SHA256 | seed-library.zip 字节 / SHA256 |
| --- | --- | --- |
| v0.17.3 | 8 331 304 / `3ad2e17f52b491bdcdfc09e14b0d2954a7938a6614f8cf75a460031922608ac7` | 493 442 / `983843ae55e36c8f2ce53939dd24561149098891e49e312f0f7ef90c041132af` |
| v0.18.1 | 8 444 988 / `658950c837895f96e4ec254610d18b8fe5012ae585d5a567cc5c2409940d08a7` | 493 442 / `8e5f512571de9ff494db3a0964f7ff00d0c49a4c5f9767f93e08f385436a640e` |
| v0.18.2 | 8 458 979 / `4e33ebc713be62485d932267766eb8a1092b2b01f918876848925ef1c55d673b` | 493 442 / `676536ca85601d0ce7e954a000fad0af8a73b7579f02ab27f1a8f2bbac606a1a` |

三件均满足「本地 = sidecar = API digest」，两个 sidecar 文件的本地哈希也等于 API digest，`validate_directory` 全部 PASS。

### 包内版本自证

| tag | 源码包 `version.py` | 种子包 `seed_manifest.json` `compatible_server_version` | 种子数 | 含 `.git/` |
| --- | --- | --- | ---: | --- |
| v0.17.3 | 0.17.3 | 0.17.3 | 9 | 否 |
| v0.17.4 | 0.17.4 | 0.17.4 | 9 | 否 |
| v0.18.0 | 0.18.0 | 0.18.0 | 9 | 否 |
| v0.18.1 | 0.18.1 | 0.18.1 | 9 | 否 |
| v0.18.2 | 0.18.2 | 0.18.2 | 9 | 否 |

## 4. Release body 逐项

| tag | 版本说明 | 验收/门禁摘要 | 环境 | 未验证范围 | 附件 SHA256 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| v0.17.3 | PASS | PASS（`## 门禁`） | **FAIL**（无独立环境小节；仅正文提及 Creo 12.4.0.0） | PASS | **FAIL**（无附件 SHA256 段；仅种子包摘要出现在门禁文字中） | 缺 2 项 |
| v0.17.4 | PASS | PASS（`## 验证`） | **FAIL**（无独立环境小节；正文仅写 Creo 12.4.0.0 匹配 SDK） | PASS | PASS（两 ZIP 摘要与远端一致） | 缺 1 项 |
| v0.18.0 | PASS | PASS（`## 门禁`） | **部分**（环境信息写在门禁段：Windows x64 / Creo 12.4.0.0） | PASS | PASS | 环境未单列 |
| v0.18.1 | PASS | PASS（`## 门禁`） | **部分**（同上） | PASS | PASS | 环境未单列 |
| v0.18.2 | PASS | PASS（`## 验收摘要`） | PASS（`## 环境`） | PASS | PASS（含字节数） | PASS |

补充观察：

- 5 个 body 均未出现「验收摘要」这一字面标题的只有 v0.17.3–v0.18.1，其等价小节标题为 `## 门禁`/`## 验证`，内容含条目、数字与命令，判定为等价通过。
- v0.18.0 body 首字符为 `U+FEFF`（UTF-8 BOM），渲染不可见，属排版瑕疵，不影响内容核对。
- v0.18.2 body 声称「新增 `docs/development/RELEASE-POSTCHECK-2026-11-07.md`」。该文件在 main/tag `v0.18.2` 上**确实存在**，但**不在当前分支**（本分支落后于 main），本轮无法在本工作树读到，已从 `43862f0` 对象读取确认。其中已记录的 v0.17.4/v0.18.0/v0.18.1 摘要与本轮 C1/C3/C4 结果一致。

## 5. 逐项判定

| 检查项 | 结论 | 依据 |
| --- | --- | --- |
| v0.17.4 tag 存在且为附注标签 | PASS | C6/C8，`object.type=tag`，`33070fc` → `b57dbda` |
| v0.17.4 tag 指向正确（main 上的合并提交） | PASS | `b57dbda` 为 main 祖先，PR #19 |
| v0.17.4 Release 非草稿、非 Pre-release | PASS | C7 |
| v0.17.4 四附件齐全、名称正确、大小与 API 一致 | PASS | C7/C9 |
| v0.17.4 本地/SHA256 sidecar/API digest 三方一致 | PASS | C9 |
| v0.17.4 body 含版本说明/验收摘要/未测范围/SHA256 | PASS（4/5，环境未单列） | 第 4 节 |
| v0.18.0 同上一组（tag/指向/状态/附件/哈希/body） | PASS（body 环境未单列） | C3/C6/C7/C8/C9 |
| v0.18.1、v0.18.2 同上 | PASS | C4/C5/C6/C7/C8/C9 |
| v0.17.3 附件与哈希 | PASS | C2/C9 |
| v0.17.3 body 完整性 | **FAIL**（缺附件 SHA256 段与独立环境段） | 第 4 节 |
| main 指向最新版本合并提交 | PASS | main HEAD = `43862f0` = v0.18.2 提交 |
| API asset-ID 下载路线真实可用 | PASS（实际下载 20/20） | C9 |
| API asset-ID 作为「browser_download_url 失败」回退的触发路径 | **无法确认** | 本轮未做故障注入，且项目规则禁止新的 Toolkit/故障注入类操作；仅证明端点本身可用 |
| 附件由 tag 对应提交源码生成 | **部分确认** | 包内 `version.py`/`seed_manifest.json` 与 tag 版本一致、无 `.git/`；未逐字节重建比对源码树 |

## 6. 报告方实测 vs 本机本轮实测

- **报告方实测（非本机证据）**：反馈原件称在其环境执行 `python tools/check_release_assets.py --tag v0.17.4 --version 0.17.4` 得到四附件下载与 sidecar 校验通过，并称在无 `.git/` 的源码包中 `tests.unit.test_t07_preview` 出现 13 项 ERROR。本文件不把这些结论当作本机证据，也不改写原件。
- **本机本轮实测**：C1–C10 的实际退出码、附件字节数、本地 SHA256、sidecar 内容、API digest、tag 类型与指向、Release 状态、body 小节判定，均由本机在 2026-11-07 18:50–19:00 重新取得。与报告方结论在「v0.17.4 附件与 sidecar 一致」上相符，但本机额外取得 tag/Release/API digest 与 body 证据。
- **本机未做**：未在官方源码包解压目录中重跑单测（不属 H11 核对范围，且需另立条目）；未连接 Creo；未验证附件内功能行为。

## 7. 结论与需用户决策

- 5 个版本的 tag、tag 指向、main、Release 状态、四附件、三种哈希全部一致，**无缺失、无哈希不一致、无错指、无草稿**，因此不触发「重新发布」动作；历史标签与附件字节一律保持不变。
- 唯一 FAIL 是 **v0.17.3 body 缺附件 SHA256 段与独立环境段**，另有 v0.17.3–v0.18.1 的「环境」未单列。这属于已发布版本的历史正文，按项目规则不得覆盖同名标签与附件；**需用户决策**：是接受为历史瑕疵并在台账备注，还是以后续版本的勘误文档补记（不改正文）。
- **需用户决策**：`RELEASING.md` 是否把「body 必须含独立环境小节与附件 SHA256」写成可执行检查项（当前仅靠人工）。本轮不修改规范文件。
- 另一项待办：API asset-ID 作为回退通路的**触发**仍未实机复现（仅端点可用性已证）。若要闭环，建议在离线单测中保持现状，另在有隔离环境时用可控的 `browser_download_url` 404 注入复现；本轮按只读约束未执行。
