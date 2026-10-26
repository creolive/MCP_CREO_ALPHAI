# 第二批可靠装配重建管线 0.6.0 发布计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付用户限定的第二批管线，合入 main，并发布 v0.6.0、源码/种子附件及 SHA256。

**Architecture:** 保留既有第二批实现与提交，只更新版本元数据和当前文档；开发者回归、SDK 与实机证据继续适用。发布附件从实际 main 提交生成，已发布标签与附件不覆盖。

**Tech Stack:** Windows PowerShell、Python 3.12、Creo 12.4 Toolkit、MSVC、Git、GitHub REST。

**Spec:** 原第二批范围见 [反馈计划](../../development/0.5.0-FEEDBACK-PLAN-2026-10-22.md)；发布规范见 [RELEASING](../../development/RELEASING.md)。2026-10-26 用户明确取消本批 WorkBuddy 测试，并授权符合条件后直接合入 main 和发布 Release。

## Global Constraints

- 编程工作只经 Codeg `delegate_to_agent(assistant_id=3)` 交给“写程序高手”，不使用原生子代理，不指定 agent_type；该助手的模型配置由用户管理。
- 工作树 `E:\Projects\md050`、分支 `codex/feat012-matrix-pipeline`；本地 MCP dev 唯一指向 canonical `E:\Projects\MCP_CREO_MechDog`。
- WorkBuddy 本批取消且未执行；不把开发者 MCP 结果称为 WorkBuddy，通过说明应明确该限制。
- 原 21 暂存文件 tree `08ba93a34409f539145686ea91541ce34fb34102` 已由 d563958 保全；保留全部现有提交、历史验证原件与运行数据。
- 不结束/重启 Creo、不擦除驻留模型、不清 unknown/pending 保护、不故障注入。已受理作业只轮询，不重提；busy 即停。
- 全量单测与实机 guard 串行，不并行争用 Toolkit 锁。当前源码基线 b86 的 748 项通过；不得以旧数字冒充新一轮检查。
- 本批不含显式源件更新 API、嵌套装配、FEAT-049/050 或世代回收；父卡未覆盖子项继续开放。
- Creo 9 SDK/实机不可用，Creo 10 未复验且不是门槛；存量风格基线保持，不把默认 dev_check 描述为全库严格零问题。
- `version.py` 统一为 0.6.0；两份种子 manifest 的 compatible_server_version 同步，9 个 PRT 原字节不变。
- main 每次合入必须同流程发布 Release；tag 指向该 main 提交，附件从该提交生成，body 列出两包完整文件名及 64 位 SHA256，下载复核。

### Task 1: 准备版本、当前文档与最终离线候选

**Files:**
- Modify: `version.py`, `seeds.py`, `seed_library/seed_manifest.json`, `docs/seed_manifest.json`。
- Modify: `README.md`, `docs/DEVELOPMENT.md`, `docs/development/RELEASING.md`, `docs/BACKLOG.md`, `docs/BACKLOG_COMPLETED.md`（只按实际子项移档），`docs/work-items/FEAT-012.md`, `docs/work-items/BUG-045.md`, `docs/work-items/FEAT-048.md`, `docs/work-items/FEAT-008.md`, `docs/work-items/DEV-046.md`, `docs/ASSEMBLY_REBUILD.md`, `docs/FILE_ADOPTION.md`。
- Create: `docs/RELEASE_NOTES_0.6.0.md`；新增当前发布证据，不修改 `docs/validation/` 既有文件。
- Current evidence: `docs/development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md` 仅追加用户取消 WorkBuddy 的最新决定，保留旧验收发生时的事实。

**Interfaces:** 输入为 d3941cf 的完整第二批实现与证据；输出为可复核候选提交、完整检查报告、确定性种子包 SHA256，以及实际变更清单。

- [ ] Step 1: 读取 AGENTS.md、发布规范与综合证据，检查 main b5ad5d5 仍为祖先，确认不改变业务实现。
- [ ] Step 2: 将 `version.py` 的 `VERSION = "0.5.3"` 改为 `VERSION = "0.6.0"`，两份 manifest 的 `compatible_server_version` 改为 `0.6.0`，PRT/hash 条目保持原样。
- [ ] Step 3: 运行 `.\.venv\Scripts\python.exe tools\package_seeds.py --output <本次新建build目录>\MCP_CREO_MechDog-0.6.0-seed-library.zip`；用实测摘要更新 `seeds.py` 的 `expected_digest`，保留格式、算法与种子逻辑。
- [ ] Step 4: 更新当前入口、工作卡及台账，以 0.6.0 候选描述已交付范围，取消 WorkBuddy 阻断但保留“未执行”；旧阶段日志及历史发布说明不改写。源码发布前不冒称远端 Release 已存在，使用明确候选状态，发布后由控制者核对实际远端。
- [ ] Step 5: 在新目录保留日志，串行运行 `tools/dev_check.py` 和 `bridge.py build`；记录受测 commit、dirty 与源码指纹、真实单测总数、风格存量、SDK worker/native source 指纹。不得放宽基线；不增加只镜像常量的测试。
- [ ] Step 6: 核对 9 个种子 hash、当前链接、版本一致性和分发白名单。只显式 stage 本次文件，提交候选；不切换 canonical、不做实机/远端变更。报告完整保存在 task brief 指定位置，返回短摘要。

### Task 2: 独立复审、最终实机范围核对、主干与发布

**Files:** 新增发布摘要 `docs/validation/RELEASE-0.6.0.md`（若尚不存在），保留原件；正式附件在全新忽略目录。

**Interfaces:** 消费 Task 1 提交与检查报告；输出远端 main/tag、published Release、四个附件（两包与各自 sha256）及下载核验。

- [ ] Step 1: 控制者生成 Task 1 diff 文件，委派独立规格/质量复审及第二批整体发布审查；不重复运行同一源码已通过的测试。发现真实阻断时交 assistant 3 修复并复审。
- [ ] Step 2: 确认 canonical 当前可操作会话、旧保护不变；候选版本 metadata 之外生产源码与已验收 b86 一致。按最终候选串行完成必要实机与安装/解包核验，适用保存重载/rollback/revision 取真实结果。既有失败驱动报告保留，不计通过。
- [ ] Step 3: 拉取/复核 origin/main；如有新提交，合并到候选并复核受影响范围。所有检查通过后更新候选文档为发布状态并完整保留授权来源，再将候选合入本地 main（不改写既有历史）。
- [ ] Step 4: 从实际 main 提交在新目录执行 `tools/package_seeds.py --output <新路径>` 与 `tools/package.py --output <新路径>`；核对种子 digest、排除本机配置/常量/二进制/日志/models/jobs、解包入口与 9 个种子。
- [ ] Step 5: 非强推推送 main，创建并推送未使用的 v0.6.0 tag。GitHub Release body 写明功能、开发者验收、WorkBuddy 取消未执行、环境/未测范围，以及源码包和种子包的完整 SHA256；上传两包和校验文件，发布非草稿 Release。
- [ ] Step 6: 读取远端 main/tag/Release/assets 并下载两包及校验文件，逐字节 SHA256 对比；最终回报版本、main commit、Release 链接、附件校验结果及未执行的 WorkBuddy。任一步未完成均不宣称交付完成。
