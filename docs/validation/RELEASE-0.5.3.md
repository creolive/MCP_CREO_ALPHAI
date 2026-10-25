# 0.5.3 发布核对（2026-10-25）

## 版本与条目

- 版本 `0.5.3`（PATCH，0.5.0/0.5.1 外部 Creo 9 反馈整合：阶段一登记 + 阶段三兼容修复与说明，无新增公开工具，工具数 91 不变）。
- 条目：[BUG-081](../work-items/BUG-081.md)（迁移 owner 拒绝诊断与 inspect 预检）、[BUG-082](../work-items/BUG-082.md)（在轴剖面编辑失败特征级诊断，autodim 改角失败本体随版披露）、[BUG-083](../work-items/BUG-083.md)（revolve.axis 入口预检）、[FEAT-030](../work-items/FEAT-030.md)/[BUG-034](../work-items/BUG-034.md)（种子来源与兼容信息透明化）、FEAT-045/BUG-058/FEAT-020/BUG-019 四项小修，及阶段一登记（两份原件逐字节归档、十组既有卡证据补录）。版本说明见 [RELEASE_NOTES_0.5.3.md](../RELEASE_NOTES_0.5.3.md)。

## 版本链

- 开发分支 `codex/feedback05051-phase1`（自 origin/main `a70a0d4`，0.5.2 已发布）。关键提交：`2f3eb6e`（阶段一：归档+建卡+台账）、`0729fee`（阶段三小修，工作副本 `codex/chores053-wording` 同树，已清理）、`50a3c94`（BUG-083 实现）、`b6238b2`+`a6d3fb3`（BUG-081 实现与 task/5 合并）、`399fe48`+`d448afe`（BUG-082 实现与 task/6 合并）、`e2bba08`（FEAT-030/BUG-034，task/10 交付）、`ccc2dc4`+`2fcf20c`（task/9 阶段三收口：全量回归+实机矩阵+台账）、`e2e9ff5`（0.5.3 定版准备，dev_check 绿）。
- 合入 main：merge 提交 `60c1895`（`Merge branch 'codex/feedback05051-phase1' for 0.5.3`），树与 phase1 尖端逐字节一致（`git diff` 为空）。
- 标签 `v0.5.3` → `60c1895`（轻量标签，与 v0.5.2 同型；该提交 `version.py=0.5.3`）。远端 main 与标签均已推送，`ls-remote` 核对均为 `60c1895d47eb6645ebe850f33f67de9b34c645bf`。
- GitHub Release `423245388`（名称 `0.5.3`，非草稿、非 Pre-release，与 v0.5.2 现状一致）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.5.3

## 环境与验证命令

- 本机 Windows x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 Toolkit SDK 与 MSVC；开发联调仅 `MCP_CREO_MechDog_dev` 指向 E 盘。
- 定版候选（`e2e9ff5` 工作区，源码内容与 `e2bba08` 集成尖一致+版本文档随版）：`tools/dev_check.py` success=true、unit_tests=passed（lint 31/未格式化 19 为既有基线）。
- 离线全量与实机矩阵（集成尖 `e2bba08`，task/9 收口）：612 项单元测试、`tools/test_unit.py`（success=true）、`bridge.py build` 复编、实机编辑收口 13/13、BUG-082 在轴扇形 7/7、BUG-083 双路径、FEAT-030 两种子加载——命令、job_id/model_id/revision/体积/哈希与偏差处置见 [PHASE3-CLOSEOUT-2026-10-25.md](PHASE3-CLOSEOUT-2026-10-25.md)。
- 合并后复核：`git diff 60c1895 codex/feedback05051-phase1` 为空；两附件在 `60c1895` 工作区复建，种子包哈希与首次构建一致（确定性），源码包差异经定位仅为 `docs/RELEASE_NOTES_0.5.3.md` 行尾 LF→CRLF（git autocrlf 规范化），采用复建版为正式附件。
- 新目录解压抽查（`build/release-0.5.3/xcheck2`）：804 文件、`version.py=0.5.3`、双 `seed_manifest.json compatible_server_version=0.5.3`、`seeds.py` expected_digest=种子包哈希、RELEASE_NOTES_0.5.3 与第三方许可在包内、PHASE3-CLOSEOUT 证据在包内、无 constants.inc/真实 config/client-config/seed_registry/toolkit.lock 及 build/jobs/models/.venv（`client-config.example.json` 为随包分发模板，属预期）。

## 附件与 SHA256（Release body 直接列出，DEV-045 第 7 项）

- 源码包：`MCP_CREO_MechDog-0.5.3-source.zip`（804 文件，4,632,838 字节）SHA256 `c9a7b0bf0455ad2fcf5a3f6cd082e2b7c7049b8fe2f5b406541d77c8580d55c3`。
- 种子包：`MCP_CREO_MechDog-0.5.3-seed-library.zip`（24 文件、9 种子，493,394 字节）SHA256 `cf46f2f32b8e4b337e3272cbe37631b388980ace1307e3a393f2b8d5c6964976`（清单 `compatible_server_version` 随版 0.5.3，种子内容较 0.5.2 未变；与 `seeds.py` expected_digest 一致）。
- 各附同名 `.zip.sha256`（100/106 字节）。
- 两包均由标签指向的主干提交 `60c1895` 工作区生成。

## 远端核对

- 四附件已上传且字节数与本地一致（source 4,632,838、seeds 493,394、.sha256 100/106）；无废资产（curl 均带 `@` 前缀，未复现 v0.5.2 首传路径字符串问题）。
- 远端附件经 GitHub API 资产元数据的服务端 `digest` 字段复核：source `c9a7b0bf…`、seeds `cf46f2f3…` 与本地、Release body 记载逐项一致；两个 `.sha256` 文本资产 digest 亦与本地一致（`b18920d8…`/`e02895d3…`）。REMOTE_VERIFY: PASS。注：本机网络对 `objects.githubusercontent.com` 直连下载超时，故以 API digest（GitHub 上传时服务端计算）为复核依据，等效于下载复算。
- `ls-remote`：`refs/heads/main` 与 `refs/tags/v0.5.3` 均为 `60c1895`；Release 423245388 非草稿、非 Pre-release。

## 未测范围与已知问题

- Creo 9 全部未复验（本机无 Creo 9 SDK，按 2026-10-15 决定不新增双版本发布门槛）；Creo 10 亦未复测（按同决定）。
- BUG-082 autodim 改角再生失败本体未修复（随版披露）；外部「coordinates/改半径也失败」未在本机复现，保留外部待核对；球体/半圆贴轴基线失败另立条目。
- 编辑矩阵失败作业 revision 字段未取得（报告格式不含）；种子重生成（环境受阻）与 9 种子安装库回归未执行。
- BUG-081 实机 MCP 拒绝时序未复现（无同型残留 worker 现场，单测直接断言 `owner_block` payload）；BUG-083 原生 `validate_revolve_axis` 分支在真实执行器未触发（Python 预检先拒）。
- 并发能力维持 [BUG-009](../work-items/BUG-009.md) 单通道忙拒边界（无队列）；BUG-078 accept 路径、BUG-058 外部 -11、BUG-063/BUG-064 待复现项随版披露；WorkBuddy 黑盒本轮未执行，不作并发或黑盒结论。

## 结论

达到发布门槛并完成交付：合入 main（`60c1895`）、标签 `v0.5.3`、Release `423245388` 与四附件均就绪且远端核对通过。本记录为发布后补录提交，不改变 `v0.5.3` 标签与附件。
