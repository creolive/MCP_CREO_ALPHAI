# 0.5.2 发布核对（2026-10-24）

## 版本与条目

- 版本 `0.5.2`（PATCH，0.5.0 反馈整合第一批，无新增公开工具，工具数 91 不变）。
- 条目：[BUG-080](../work-items/BUG-080.md)（装配变换单位契约）、[FEAT-006](../work-items/FEAT-006.md)（收养拒绝有界逐特征诊断）、[DEV-046](../work-items/DEV-046.md)（0.5.0 反馈整合第一批收口）。版本说明见 [RELEASE_NOTES_0.5.2.md](../RELEASE_NOTES_0.5.2.md)。

## 版本链

- 开发分支 `task/2`（自 main `d508444`，0.5.1 已发布），关键提交：`45147e4`/`01363a1`/`fe15bae`（WorkBuddy 三轮归档）、`4a8f590`/`97cf2f6`（整合 dev046 与 FEAT-006 同树）、`b4caf89`/`947f40e`/`886eb0d`/`b09ffc3`（BUG-080 实现）、`62bc4dc`（FEAT-006 实现）、`0ff936f`（0.5.2 定版准备，dev_check 绿）、`6946c1d`（第三轮黑盒收口）。
- 合入 main：merge 提交 `cb0c7b4`；随后主干补提交 `d05e052`（种子清单随版 0.5.1→0.5.2 与 `seeds.py` expected_digest 同步——合入后发现 task/2 缺该随版步骤，`tools/package_seeds.py` 的 `compatible_server_version` 断言拦截后补齐，dev_check 复跑 success=true）。
- 标签 `v0.5.2` → `d05e052`（与该提交 `version.py=0.5.2` 一致）。标签首次打在 `cb0c7b4`，随上述源码修正删除重打（当时 Release 尚未创建，无外部消费者）；远端 main 与标签均已推送（`ls-remote` 核对一致，均为 `d05e052`）。
- GitHub Release `422755820`（`MCP_CREO_MechDog 0.5.2`，Pre-release，非草稿）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.5.2

## 环境与验证命令

- 本机 Windows x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 Toolkit SDK 与 MSVC。
- `tools/test_assembly_units.py`（BUG-080 离线原生夹具：27 个单位/变换 case + 12 个遍历状态 case，SDK 查询替换、无 Toolkit 连接）通过；`tests/unit/test_session_assembly.py` 8 例、收养明细 4 例通过；`tools/dev_check.py` 在定版源码工作区复跑 success=true（含种子分发/兼容单测）。
- 2026-10-24 实机取证与 WorkBuddy 三轮黑盒见[版本说明](../RELEASE_NOTES_0.5.2.md)、[BUG080-FEAT006-LIVE-2026-10-24.md](BUG080-FEAT006-LIVE-2026-10-24.md)（受测执行器与提交/dirty 出处记录于其归档 `report.json` 的 `source` 段）与[第三轮报告](wb080-blackbox-round3-2026-10-24.md)。
- 受测源码：BUG-080/FEAT-006 代码与全部实机/黑盒证据取自整合树 `6946c1d`；定版 `d05e052` 相对 `cb0c7b4` 仅种子清单与 expected_digest 随版（3 文件各 1 行）。

## 附件与 SHA256（Release body 直接列出，DEV-045 第 7 项）

- 源码包：`MCP_CREO_MechDog-0.5.2-source.zip`（787 文件，4,524,611 字节）SHA256 `db28878972f4e0b3ae22b80db33657c659a064bd9b7a3c48c6b1d69a6911f351`。
- 种子包：`MCP_CREO_MechDog-0.5.2-seed-library.zip`（24 文件、9 种子，493,394 字节）SHA256 `a1ac3dd75100bdf45d2ef3d9bfe971783d3cb50b6a22f5b784f15b7ab8da290e`（清单 `compatible_server_version` 随版 0.5.2，种子内容较 0.5.1 未变；与 `seeds.py` expected_digest 一致）。
- 各附同名 `.zip.sha256`（内容与哈希一致）。
- 两包均由 tag 指向的主干提交 `d05e052` 工作区生成；包内抽查 version.py/双清单=0.5.2、RELEASE_NOTES_0.5.2 与第三方许可在包内、无 build/jobs/models/constants.inc 及真实 config/client-config/seed_registry/toolkit.lock。
- 发布过程注记：首次上传四附件时 curl 缺 `@` 前缀只传出路径字符串（36–49 字节），当即将四个废资产删除重传；最终以远端下载复算为准，不影响定稿附件。

## 远端核对

- 四附件已上传（source 4,524,611 字节、seeds 493,394 字节、两个 `.sha256` 文本 101/107 字节），Release 非 Pre-release 之外无异常标记（Pre-release=true 按项目成熟度）。
- 远端附件经公共下载 URL 逐项下载复核：source/seeds SHA256 与本地及 body 记载完全一致（REMOTE_VERIFY: PASS）；两个 `.sha256` 文本与 body 记载一致；`ls-remote` 确认 `refs/heads/main` 与 `refs/tags/v0.5.2` 均为 `d05e052`。

## 未测范围与已知问题

- Creo 9 / Creo 10 实机未测（按 2026-10-15 用户决定不作为发布门槛）。
- BUG-080 多级嵌套装配与缺件/父变换失败/子装配遍历失败三个生产失败分支以离线夹具覆盖，实机未触发（实机单层混合单位已测）；并发能力维持 [BUG-009](../work-items/BUG-009.md) 单通道忙拒边界（无队列）；BUG-058 外部 -11、BUG-063/BUG-064 待复现；[BUG-078](../work-items/BUG-078.md) accept 路径随版披露；WorkBuddy 未实施并发调用，不作并发结论。

## 结论

达到发布门槛并完成交付：合入 main、标签、Release 与附件均就绪且远端核对通过。本记录为发布后补录提交，不改变 `v0.5.2` 标签与附件。
