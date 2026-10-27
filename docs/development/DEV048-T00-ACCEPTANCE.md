# DEV-048 / T00 文档基线验收

日期：2026-10-27（Asia/Shanghai）。范围：四份原件归档、逐章映射、共享接口约定、条目登记与台账登记行；不含 T01—T05 的业务实现、测试或实机验收。

## 交付与来源身份

- 基线：main 与 `v0.7.0^{}` 均为 `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d`，`version.py` 为 0.7.0；本任务从该提交建立 `codex/dev048-feedback060`，只补文档。
- 起始 dirty：`session_activity.json` 已有修改；`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/` 下 30 个运行证据/意向 JSON，以及两份尚未跟踪的计划文档。运行数据全部保留、不纳入提交；两份计划文档按用户要求纳入本次文档基线。
- 本任务未启动 server、未导入服务入口、未调用 MCP/Toolkit、未执行单元测试、`dev_check`、SDK 构建或建模回归，也未连接 Creo。
- 环境：Windows 11 x64（10.0.26100）、Python 3.12.14、Git 2.50.1.windows.1、工作区 `E:\Projects\MCP_CREO_MechDog`。

## 归档与覆盖

原件来自 `C:\Users\Administrator\Downloads\0.6.0`，保留原文件名并以原始字节复制；复制后逐份与源目录比较字节数和完整 SHA256。`.gitattributes` 为本目录四个 `2026*.md` 原件单独设 `-text`；`MAPPING.md` 与 `manifest.json` 是新增说明，不修改原文，也不对历史目录或新撰写文档做批量换行改动。

| 原件 | 报告 | 字节数 | 完整 SHA256 |
| --- | --- | --- | --- |
| `2026-10-25CREO10.0.0.0-0.5.3工作条目未随发布回填与P1诊断代偿.md` | R1（0.5.3，升级/静态） | 11198 | `1e5639f210063215366b290331af13e6919b35ded31f784c060d7c2d92aa23e0` |
| `2026-10-26CREO10.0.0.0-0.6.0换行归一化已波及thirdparty与工作条目状态第2次未回填.md` | R2（0.6.0，升级/静态） | 11073 | `13696ecd2ce6b90a2547066621ac8c2e5f7a22e21161d0aa9712f5c73c773080` |
| `2026-10-26_CREO10_v0.6.0_support_status未覆盖adopt_file且版本成熟度仍矛盾.md` | R3（0.6.0，MCP 实机） | 10231 | `f2f5f57dbc266f1f0024a6349c80ad01a54c825e51e309f3b4b7eb9c5a7145fb` |
| `20261026_CREO_v0.6.0_三项既有阻断未修_非主轴面拉伸方向仍错误.md` | R4（0.6.0，MCP 定向实机） | 12077 | `f0a582aa244d9caa59ab31ce118268f4abe813939c299a19cf38ec3b3ce27836` |

四份原件均为 LF、无 BOM、以换行结尾；归档副本与源目录逐字节一致，未做解码、重编码或格式化。

[映射](../validation/feedback-0.6.0-2026-10-27/MAPPING.md)覆盖 R1 的 14 个、R2 的 15 个、R3 的 15 个、R4 的 17 个标题（含报告标题、父章节与未编号“未验证”小节），共 **61 项**；另单列 R1/R2 的 **11 条**回复请求结论。每项标注已交付、本批修复（T01/T02）、文档回填（T03）、定向补证（T04）、推断不成立或保留未测，并给出归属任务与验收方式。

R1、R2 明确未连接 Toolkit，只按升级/静态证据收录；R3、R4 为外部 Creo 10.0.0.0 的 MCP 实机报告，不等于本机复验。R4 的 `sketchgen.py`、`sketch_entities.json`、`gear10.json`、`dogbone_yz.json` 未随附，原案例不可重放，映射中已写明“原输入未重放”。

## 接口与登记

[DEV-048](../work-items/DEV-048.md#interface-baseline) 固定本批三项共享约定：`inspection_warnings` 的字段、原因码与上限；兼容与语义边界（不改变成功/revision/保存重载/保护，旧结果兼容）；`split_result`、`add_warning`、`warnings_of` 的签名与既有 `make_ref`/`split`/`load_ref` 不变量。三者均为目标契约，未宣称已实现。

登记改动：

- 新建 DEV-048 工作卡：目标、范围、环境、阶段验收、共享接口与 T00 记录；阶段表对 T01—T05 明确写“未开始”。
- [BUG-076](../work-items/BUG-076.md) 追加“本批来源子项”，把 sidecar 完整性、同名校验与拒绝后引用生命周期与本卡 0.7.0 的单位摘要修复分开，附当前代码事实与待复现前提；卡状态保持“验收中”。
- 主台账新增本批“当前安排”条目与 DEV-048 登记行；分类数量与唯一 ID 统计按派发表留给 T03，不在本批重算。
- 两份原未跟踪的计划文档（[完善计划](0.6.0-FEEDBACK-PLAN-2026-10-27.md)、[派发表](0.6.0-FEEDBACK-TASKS-2026-10-27.md)）随本任务提交，供后续任务直接读取。
## 核验方法与结果

使用 PowerShell 复制与哈希、Python 标准库的 JSON/SHA256/正则检查，以及 Git 自身的属性与空白检查；机器结果保存在本机生成目录 `build/dev048_t00_20261027/`（不入库）：

```powershell
Get-ChildItem -LiteralPath $src -File -Filter *.md | Copy-Item -Destination $dest
.\.venv\Scripts\python.exe -X utf8 build\_t00_verify.py
git check-attr text eol -- "docs/validation/feedback-0.6.0-2026-10-27/2026-10-25CREO10.0.0.0-0.5.3工作条目未随发布回填与P1诊断代偿.md" "docs/validation/feedback-0.6.0-2026-10-27/MAPPING.md"
git diff --check
git status --porcelain
```

| 检查 | 结果 |
| --- | --- |
| 原件 / 归档副本字节与 SHA256 | 4/4 字节相等，SHA256 与 manifest 一致（见上表与 `verification.json.archive`） |
| manifest 章节标题与行号 | 61/61 与原文逐行一致，报告数 4，声明计数与实测一致 |
| 映射锚点 | 61 个 `R*-NN` 锚点全部存在，正文 61 行，与 manifest 的 `mapping` 一一对应 |
| 回复请求 | 11 条（R1-Q1—Q6、R2-Q1—Q5）各有结论与归属 |
| 新增/修改文档本地链接 | 224 处本地链接解析，除本记录（当时尚未创建）外无失效；创建后复跑为 0 失效 |
| 原件换行保护 | `git check-attr text` 对四份原件为 `unset`，对 `MAPPING.md` 为 `set`（`eol: lf`） |
| 空白与差异 | `git diff --check` 无输出 |
| 提交范围 | 仅 `.gitattributes`、`docs/` 下文档与归档；`session_activity.json` 及未跟踪运行文件保持未暂存 |

未纳入提交的内容：`session_activity.json` 的既有修改、`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1`、`session_erase/` 下的运行证据文件，以及 `build/` 下的本机生成物。

## 提交

- 基线提交：`2a7835808e1ea2981df411c7e2a4e94d1fd4d92d`（main / `v0.7.0^{}`），`version.py` 0.7.0，未改动。
- 本任务提交：`d28d5f4`，分支 `codex/dev048-feedback060`。该提交包含本记录、DEV-048 卡、四份原件与 manifest/MAPPING、两份计划文档、`.gitattributes`、台账登记行与 BUG-076 子项；SHA 于提交后回填。
- 未合入 main、未创建标签、未发布、未改版本号、未启动其他任务。

## 未测与交回

- 未执行任何单元测试、`dev_check`、SDK 构建、MCP 调用或 Creo/Toolkit 操作；本记录不构成任何建模、几何或安装证据。
- R1/R2 的升级与静态结论、R3/R4 的外部 Creo 10 实机结论均为外部证据；本机未复现，也不据此改写 0.7.0 的已交付事实。
- T01 sidecar 完整性、T02 引用生命周期、T03 台账与发布检查、T04 Right 面 ±Z、T05 集成与发布均未开始，须用户逐项指派；本批共享接口与阶段表只是目标与分工，不代表已实现。
- 主台账的分类数量、唯一 ID 统计与 DEV-047 首页状态未在本批调整，按派发表由 T03 回填；当前台账首段仍描述 0.6.1，属已知待回填项，不是本批引入的错误。