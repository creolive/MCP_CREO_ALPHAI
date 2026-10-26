# DEV-047 / T00 文档准备验收

日期：2026-10-26（Asia/Shanghai）。范围：原文归档、章节映射、共享接口基线、既有条目来源补录；不含 T01—T13 的业务实现或功能验收。

## 交付与来源身份

- 依赖集成分支 `codex/dev047-feedback052`，起点 `8508dce2b323762c1c0eebed654b823a63bc1392`；任务分支 `codex/dev047-t00-archive`。业务对照基线 main `2af3853531ebba29fe2fa458f5a432224323ce76` / 0.6.1。任务交回集成负责人纳入；本任务不合入 main、不发布。
- 起始 dirty：既有 `session_activity.json` 修改、`.codebuddy/`、`.workbuddy/`、`.zcode/`、`examples/wb_unsaved_03.prt.1` 和 `session_erase/` 的未跟踪运行文件。均保留且不纳入交付；详细起始状态记录在 `build/dev047_t00_20261026/baseline.json`。
- 本机文件/文档检查环境详见 [manifest](../validation/feedback-0.5.2-2026-10-26/manifest.json) 的 archive_environment。本次不启动 server、不导入服务入口、不调用 MCP/Toolkit，不执行 SDK 构建、单元测试、dev_check 或建模回归；这些检查与文档改动无关，留相应实施任务及 T13。
- 受核对源码：214 个 Git 已跟踪 `src/`、`native/` 或 `.py/.ps1/.toml/.lock` 文件（去重）；原始字节逐文件与起始快照相等。按排序 UTF-8 相对路径 + NUL + 原始 SHA256 二进制摘要串联再做 SHA256，聚合值为 `1388f2a29073cc260ead3f43d193fd005b3d91206cf1b6055a19ceaab447f12a`。这是 T00 只读内容身份，不能冒充 Toolkit 构建或实机受测指纹。
- 另以 AST 读取 `server._SOURCE_NAMES`，不导入 server，按服务 CRLF→LF 的既有算法核对 59 个源码文件，结果留 `build/dev047_t00_20261026/runtime_source_fingerprints.json`。本次不确认任何已运行客户端加载身份。

## 归档与覆盖

原件来自 `C:\Users\Administrator\Downloads\0.5.2`，保留原文件名，以原始字节复制；`.gitattributes` 为本目录三个 `2026*.md` 原件单独设 `-text`，防止 Git 后续转换行尾。映射和 manifest 是新增说明，不修改原文。

| 原件 | 字节数 | 完整 SHA256 |
| --- | --- | --- |
| R1：support_status / unchanged | 8453 | `6119ecb509ce357d71033d01652a38aea045cbeac1f8084bddb68849623687b3` |
| R2：单位契约 / BUG-078 | 12380 | `b5675b59c52fe13eafb57aac2013c220c0f8ea0f8c3e04be08e4ccc1d94e27e0` |
| R3：非主轴面 / 多轮廓 | 14493 | `28ff1d9b6ae711faef7505d6ebbbcbb3e7458ddc896e7db0a08a0737c5d8fe87` |

[映射](../validation/feedback-0.5.2-2026-10-26/MAPPING.md)逐项覆盖 R1 的16个、R2的17个、R3的26个标题（含父节、报告标题及未编号“未验证”小节），共59项；另细分R1 §5五项旧请求，列出用户明确纳入的旧P1—P8（含P3.1/P3.2、P5求交轴）、倾斜尺寸对照和父卡范围边界。每项明确当前分类、所属已有ID、任务与验收。

R2无Toolkit连接，不得补成实机通过；R1/R3为外部报告所述实机，不等于本轮独立复验。原始TXT、截图、MCP日志和草图JSON没有随这三份Markdown提供；未来用独立夹具不得称为原案例逐字复放。报告推测“全局Z”“两环上限”与“体积相加=无干涉”等已在映射中澄清。

## 接口与条目补录

[DEV-047](../work-items/DEV-047.md#interface-baseline)固定六项共享接口：显式平面ID互斥与真实帧、执行/最终效果双状态、feature_state、只读约束回放规划、三态session_health、inspect/apply世代回收；另写入unchanged适用范围、既有revision/事务、单位迁移和集成纪律。上述为已确认的目标契约，不宣称新能力已经公开。

22张既有卡追加本批来源与子项；主台账中的BUG-003、BUG-018、FEAT-010、FEAT-027四项就地补来源。主台账仅补链接及T00进度，不重算分类、关闭父卡、调整版本；方案和派发表同步T00完成及依赖尚待纳入状态。未新建工作卡或占用新ID。

## 核验方法与证据

本轮使用 Python 标准库的文件/JSON/SHA256/Markdown链接检查，脚本和机器结果存放于本机生成目录：

```powershell
.\.venv\Scripts\python.exe -X utf8 build\dev047_t00_20261026\verify_t00.py
git diff --check -- .gitattributes docs
```

检查原件/归档逐字节和三组预期SHA、manifest环境与未测范围、59标题的原文/行号/锚点一一对应、新增文档链接、既有卡来源、全部历史validation文件、业务源码和既有运行文件不变性。暂存后增加 `--staged`，独立读取Git blob核对三个原件及交付文件字节，验证非文本属性生效且未混入运行数据。最终结果见本机 `build/dev047_t00_20261026/verification.json` 与本次提交的最终差异核对。

2026-10-26 文档核验全部通过，工作区及 Git 暂存内容分别检查：

| 检查 | 结果 |
| --- | --- |
| 三原件 / 归档 / Git blob | 3/3 字节与预期完整 SHA256 一致，Git text 属性均为 unset |
| 标题 / 行号 / 映射锚点 | 59/59 一一对应，R1 五旧请求及用户纳入旧问题齐全 |
| 来源补录 | 22张既有卡 + 4条台账内条目，未新增工作卡或ID |
| 新增链接 | 126处本地链接及适用显式锚点均有效 |
| 历史 validation | 340个已跟踪文件字节数和原始 SHA256 全部保持 |
| 业务源码及既有运行修改 | 214个源码文件和既有 session_activity.json 字节保持 |
| 提交范围与空白 | 33个交付文件，仅文档及归档保护属性；git diff/cached diff --check 通过，未混入运行数据 |

## 未测与交回事项

未执行任何新的 Creo 12.4/10/9 建模、保存重载、约束、生命周期、健康或回收运行验收，也未执行 WorkBuddy；本批功能交付仍由 T01—T13 推进。三个历史现场未被 inspect/apply 或清保护。

发现一处既有文档冲突：FEAT-006的2026-10-24段写三旧现场已accept收口，BUG-078与已确认总计划仍写待操作者选择。已在DEV-047和映射交回T10/T13核对，不新增ID、不改写历史现场结论。T00文档核验不能解除现有Toolkit会话限制。
