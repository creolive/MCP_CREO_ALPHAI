# 0.11.5 发布记录

日期：2026-11-02（Asia/Shanghai）。类型：PATCH；公开工具 **95 个**。范围：[DEV-002 第三批](../work-items/DEV-002.md)离线交付，整个 DEV-002 继续开发中，T5 实机待验。

## 固定发布输入

- 用户在第三批离线验收后明确要求直接合入 main 并发布，取代此前开发阶段不合 main/不推送/不发布的边界。
- 开发分支：`codex/DEV-002-batch3-package`；起点 `0f6c085`；离线交付提交 `46f3399`；0.11.5 仅补版本、双种子清单、受信摘要及发布文档，不改变建模代码。
- [版本说明](../RELEASE_NOTES_0.11.5.md)、[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.5)、[标签对应源码](https://github.com/wudahua/MCP_CREO_MechDog/tree/v0.11.5)。标签 `v0.11.5` 必须指向本次合入后的 main 提交，最终附件必须从该提交源码生成。
- 本文件随发布源码提交冻结；最终主干完整 SHA、Release 对象、两 ZIP 和两 sidecar 的完整 SHA256 在 Release 正文与本轮 `remote_verification.json` 记录，避免为回填自身归档哈希再制造一个未另行发版的 main 提交。
- 本轮原始过程目录：`build/release_0.11.5_20261102T143942Z/`。Git dirty 包含保留的用户 session_activity.json/客户端目录及发布准备文件，不以提交号替代实际源码指纹。

## 验收

| 项 | 本次结果 |
| --- | --- |
| 发布源码统一检查 | `tools/dev_check.py --work-item DEV-002-release-0.11.5` success=true、unit_tests=passed；2196 项单测 0 failures / 0 errors；0.11.5 候选源码包全新环境安装及 64 项回归通过 |
| 受测源码指纹 | `a03b6e42586217974e5da78cc43322781926e063182049a15e0f2d0d07744dc3`；原始开发检查与逐文件源码身份保存在本轮目录 |
| 工具与版本一致性 | 目标 VERSION=0.11.5，公开工具集合与 schema 仍 95，release_status=stable，compact 13436 B、full 24 页最大 28975 B，均不超过 32 KiB |
| 双种子清单 | compatible_server_version=0.11.5，两份清单完全相同，9 个种子本体 SHA256 不变 |
| 受信种子摘要 | 准备阶段测得 `daaa10986339c1065b03ae70d81d3f50d9a69046b7216f9c8de906abd685f115`；回填后两次正常重建均须通过闸门且同哈希 |
| 最终 main 附件 | 从 main/标签提交重新生成源码 ZIP、种子 ZIP 及各自 .sha256；独立副本安装与远端结果在原始报告/Release 正文中逐项核对 |
| 原生与真实 stdio | 本批未执行；无原生修改，不把 0.11.4 实机结果移植为本版证据 |

环境：本机 Windows 11 x64 / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3；独立副本安装锁定依赖。未连接 Toolkit，未执行原生构建或建模，未操作或重启 Creo，未清 unknown 保护。

实现阶段的历史 RED→GREEN、2196 单测与独立副本 64 项结果保留在 [DEV-002-batch3](DEV-002-batch3.md)，不改写其版本/时间。

## 上一正式包身份比较（发布门槛第 9 项）

从 GitHub 下载 0.11.4 正式源码包，先核对其完整 SHA256：`6e9e86c08bcf1a8e6ef8de7052b8bd3b7966de19aa5b2a38961661dca3cd9453`。

- 35 个 `native/*.cpp/*.h/*.hpp` 原字节相同（含 json.hpp），本批未修改 native 源。
- json.hpp 原字节 SHA256 两边均为 `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`。
- LICENSE.nlohmann-json：旧正式包 1076 B / `46a65cffd1ea955132d95a8dd921640714a8d6b537d2e4e482d31145ae95b603`，本机 1097 B / `b9715282b2f1db1359a919bb3a542dd4362fd9e38ae72d421367eb11abe62eec`；仅 LF/CRLF 差异，文本完全相同。本轮没有修改该文件，不声称原字节相同。
- loader/callback 源在既有 `sha256-repo-lf-v1` 规范化口径下相同，指纹算法没有改变；现存构建缓存与注册文件仅作只读快照，完整数据见 `previous_release_identity.json`。
- 当前本机 worker SHA256 `8ab6978e6cc8cacc2c614f9af71684cfed5f2a034383108b38481467824cc16a`；loader `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9`；callback `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662`。本次未重建。
- 正式源码包排除二进制，不能从它证明旧 DLL 的实际字节；本轮也未读取 live 注册状态，不把文件/缓存一致外推为运行时验证。未改 protk 注册文件、实际配置或安装路径。

## 逐 ID 五处核对

| ID | 技术状态与实际交付 | 开放范围 | 对应入口 |
| --- | --- | --- | --- |
| DEV-002 | 第三批实现及离线验收随 0.11.5 交付；整体开发中 | T5 实机、服务/启动/桥接及其余布局继续分批 | [工作卡](../work-items/DEV-002.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.11.5.md)、[开发入口](../DEVELOPMENT.md)、[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.5) |

无新增 FEAT/BUG ID，无新增能力声明。台账唯一行与分类数量保持，未关闭整个 DEV-002。

## 未验范围与发布后操作

T5 真实 MCP 握手/分页、自动选种建模＋编辑、几何/revision/保存重载与种子文件核验仍待会话确认；WorkBuddy、Creo 9/10、并发与恢复实机未执行。用户要求发布不被解释为确认 Creo 已恢复。

升级需安装当前版本 editable 元数据并重启 MCP 服务；本批不要求重新注册原生 DLL、迁移模型登记或重启 Creo。使用与源码配套的 0.11.5 种子包。
