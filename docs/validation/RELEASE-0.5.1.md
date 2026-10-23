# 0.5.1 发布核对（2026-10-23）

## 版本与条目

- 版本 `0.5.1`（PATCH，编辑链路缺陷修复批次，无新增工具，工具数 91 不变）。
- 条目：[BUG-062](../work-items/BUG-062.md)（centerline 就地编辑）、[BUG-030](../work-items/BUG-030.md)（同几何守卫修正）、[BUG-029](../work-items/BUG-029.md)（reorder 槽位修正）、[BUG-079](../work-items/BUG-079.md)（就地改弧半径修复）。版本说明见 [RELEASE_NOTES_0.5.1.md](../RELEASE_NOTES_0.5.1.md)。

## 版本链

- 开发分支 `codex/bug062-editing-batch2`（自 main `6d360a4`，0.5.0 已发布），关键提交：`01734af`/`3e27be1`/`f2fde02`/`1ca4e8f`/`0e4513e`（BUG-062/030/029）、`e1e67ee`（BUG-079 修复）、`8863906`（0.5.1 版本定版）、`57ba366`（BUG-078 补录）。
- 合入 main：merge 提交 `0d9715d`。
- 标签 `v0.5.1` → `0d9715d`（与该提交 `version.py=0.5.1` 一致）；远端 main 与标签均已推送（`ls-remote` 核对一致）。
- GitHub Release `421562562`（`MCP_CREO_MechDog 0.5.1`，Pre-release，非草稿）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.5.1

## 环境与验证命令

- 本机 Windows x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 Toolkit SDK 与 MSVC（cl 19.44）。
- `tools/test_editing_closeout.py` 全套 11 项（含新增 `arc_radius_inplace_edit`）通过；BUG-062 夹具 `build/bug062/verify.py` 两入口通过；`wb-r6-repro.py`（变体 C/D）、`wb-r6-extrude.py`、`wb-r6-coords.py` 通过；`tools/test_general.py` 通过；`tools/dev_check.py` 通过（554 单测，无新增语言回归）。
- WorkBuddy 黑盒复验（服务 0.5.0 修复构建，Creo 12.4.0.0/release 44）：场景 1–3 通过（回转 R5→R6→R5、同几何 unchanged、特征 ID 保持），场景 4 经输入勘误后实证修复有效；失败输入回滚干净。复验表见 [BUG-079](../work-items/BUG-079.md)。
- 受测源码：BUG-079 修复提交 `e1e67ee`，执行器 SHA256 `a66ff88c01494bdcb8b3fb9212313e25e0ce443bcb34a7dd7a2e9e7b31aaa27e`；后续提交均为文档/版本元数据。

## 附件与 SHA256（Release body 直接列出，DEV-045 第 7 项）

- 源码包：`MCP_CREO_MechDog-0.5.1-source.zip`（761 文件）SHA256 `8732d98ecbc8528093cc1f2b0edf446577c6909d6cc4a9331e42206df9dac684`。
- 种子包：`MCP_CREO_MechDog-0.5.1-seed-library.zip`（24 文件、9 种子）SHA256 `77f099533a5e27914c619021fa00ed7f5a3339112982f7b46c2a22c998c599a8`（与 `seeds.py` expected_digest 一致；种子内容较 0.5.0 未变，清单版本随版）。
- 各附同名 `.zip.sha256`（内容与哈希一致）。
- 两包均由 tag 指向的主干提交 `0d9715d` 工作区生成；包内抽查 version.py/双清单=0.5.1、RELEASE_NOTES_0.5.1 在包内、无 build/jobs/models/constants.inc、第三方许可在。

## 远端核对

- 四附件已上传（source 4,396,377 字节、seeds 493,394 字节、两个 sha256 文本）。
- 远端附件逐项下载复核：source/seeds SHA256 与本地及 body 记载完全一致（REMOTE_VERIFY: PASS）；两个 `.sha256` 文本与 body 记载一致。

## 未测范围与已知问题

- Creo 9 / Creo 10 实机未测（按 2026-10-15 用户决定不作为发布门槛）。
- 并发能力维持 BUG-009 单通道忙拒边界（无队列）；BUG-058 外部 -11、BUG-063/064 待复现；BUG-078 accept 路径保持随版披露。
- WorkBuddy 未实施并发调用，不作并发结论。

## 结论

达到发布门槛并完成交付：合入 main、标签、Release 与附件均就绪且远端核对通过。本记录为发布后补录提交，不改变 `v0.5.1` 标签与附件。
