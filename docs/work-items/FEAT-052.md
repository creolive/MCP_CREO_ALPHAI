# FEAT-052：装配按零件族上色（自动分族 / 显式族表、预览与读回）

日期：2026-11-01（Asia/Shanghai）。类型：功能。优先级：P2。状态：已交付（0.11.0；本机实机 28/28，保留未测范围）。目标版本：0.11.0。

来源与关联：[装配按零件族上色功能计划](../superpowers/plans/2026-10-31-assembly-recolor-plan.md) 全文（建议包 `creo_recolor_assembly_proposal` 作为技术参考及外部测试资料保存，其测试回执不替代本项目验收）。关联 [FEAT-012](FEAT-012.md)（装配矩阵与位姿）、[FEAT-023](FEAT-023.md)（组件身份与 `source_model_id` 投影）、[FEAT-031](FEAT-031.md)（装配导出）、[FEAT-045](FEAT-045.md)（装配只读检查）、[DEV-002](DEV-002.md)（Python 包迁移）。

当前状态：已随 0.11.0 正式发布，详见 [版本说明](../RELEASE_NOTES_0.11.0.md)与[发布记录](../validation/RELEASE-0.11.0.md)。WorkBuddy、真实 busy/并发及 Creo 9/10 未验；以下分类依据是登记时的历史状态。

历史分类依据：范围与接口已在计划文件中明确固定（目标、参数、预览/执行语义、验收项），按模板「修改范围明确后填『待开发』」进入「开发中」。当时为**离线开发中**：未连接 Creo、未编译、未实机验收。

## 问题或目标

**目标**：给 **MCP 受管的单层装配**按零件族上色，并让调用方在写入前后都能自证结果。

- 默认**自动分族**：按组件绑定中唯一的 `source_model_id` 分组，`palette` 的键为该来源 ID。
- 支持**显式族表**：`families={族名: [组件标签或特征ID]}`，`palette={族名: [r,g,b]}`；族名沿用项目标签规范（`^[a-z][a-z0-9_]{0,27}$`）。
- 提供**分组预览、颜色读回、保存重载及失败回滚**。
- 首版聚焦装配组件外观；独立零件、面级、嵌套及外部装配另行扩展。

**硬约束**：颜色写在**装配组件层**，源零件文件保持原字节不变。

## 范围

**MCP 接口**（计划文件「MCP 接口」节为准）：

```python
creo_recolor_assembly(
    model_id,
    expected_revision,
    palette=None,
    families=None,
    dry_run=False,
    limit=50,
    cursor=None,
)
```

- **自动分族**：省略 `families`，按组件绑定中唯一的 `source_model_id` 分组；`palette` 的键为该来源 ID。
- **显式族表**：`families={族名: [组件标签或特征ID]}`，`palette={族名: [r,g,b]}`；族表必须**无重复、完整覆盖组件**。
- **颜色**：RGB 必须为三个**有限数值**，范围 `0..1`，**拒绝布尔值**；写入时色板必须**完整匹配所有族**。
- **预览**：`dry_run=true` 可省略色板；读取已验证快照，分页返回分组、计数及未匹配项，**不连接 Toolkit、不创建作业、不推进 revision**；游标绑定 revision 和请求内容，变更后旧游标失效。
- **执行**：返回现有 `job_id/model_id`，通过 `creo_get_job` 轮询；**始终保存**，成功后 revision 增加一次；分页参数只用于预览。
- **计划操作**：同步增加 `recolor_assembly` 计划操作，供 `creo_execute_plan` 使用；仅选择操作前已经存在的组件，**计划操作不接受预览参数**。

**实现方式要点**（计划文件「实现方式」节）：

1. **登记与隔离**：实施前登记 `FEAT-052`；在独立开发分支和隔离工作树开展离线开发，保留当前 DEV-053 的未提交内容。业务逻辑放入 `src/creo_mechdog/appearance.py`；工具注册、操作校验、装配白名单和能力声明同步接入。
2. **原生批量上色**：在 `native/appearance.h` 实现组件定位、外观设置和读回，接入现有执行器；使用实际组件模型类型构造 `ProAsmitem`（修正建议包仍传 `PRO_FEATURE` 的问题）；写入前在通道锁内重新核对 revision、组件身份、全部分组及原有外观，再开始设置；采用建议包的显示参数（ambient `0.4`、diffuse `0.7`、highlite `0.5`、shininess `0.4`、transparency/reflection `0`，高光颜色随 RGB 更新）；颜色写在装配组件层，刷新目标装配窗口；源零件文件保持原字节。
3. **保存、基线与回滚**：组件检查快照增加外观属性及原始查询码，区分「存在」「不存在」「查询失败」；设置后逐组件读回，保存并擦除重载后再次读回，RGB 绝对误差须不超过 `1e-6`；将外观纳入装配入场、保存重载和回滚核验，后续改位置、保存等操作也必须保持颜色；旧登记缺少外观基线时，提示先通过现有 `creo_save_model` 建立并验证检查点，再执行上色；任一步失败沿用检查点回滚并核对恢复后的外观，无法证明恢复成功时保留现有 unknown 保护。
4. **查询与说明**：作业结果提供上色数、未匹配项、各族计数及两次读回结果；compact 仅保留数量和核验状态；完整逐组件结果通过 full job 查询；当前颜色通过现有组件检查分页读取；明确**组件外观读回与屏幕实际显示分别验收**。

**不包含**

- 独立零件上色、面级上色、嵌套装配、外部装配——不在此版，另行扩展。
- 按遍历顺序或随机副本名称**猜测**分组：来源缺失或冲突时要求显式族表，不静默降级。
- 不承诺颜色以外的外观属性（透明度、反射等在首版固定为 `0`，随 RGB 联动的高光颜色除外）。
- 不新增并发或调度原语：Toolkit 通道忙时立即拒绝，不排队、不自动重试（边界见 [BUG-009](BUG-009.md)）。
- 本阶段为离线开发，不连接、不操作 Creo，不启动 MCP 服务。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `tools/dev_check.py` 与针对性格归 | 检查无新增问题，回归通过 |
| 本机 Creo 12.4 / 匹配 SDK | 对应实机测试（`tools/test_assembly_appearance.py`） | 原生组件外观设置有效、颜色读回正确、保存擦除重载后颜色一致；适用失败路径回滚验证 |

按计划文件「验收」节，新增 `tools/test_assembly_appearance.py` 覆盖：

- **输入与分组**：自动分族、显式合族、多标签同来源、来源冲突、重复或遗漏组件、非法 RGB、过期 revision、非装配及缺件拒绝。
- **预览与协议**：无 Toolkit 调用、无作业及 revision 变化；分页不超过 32 KiB，变更后旧游标失效；busy 沿用立即拒绝契约。
- **实机正例**：新建 80 组件、12 族夹具，采用建议包的颜色和族计数；核对保存擦除重载后的颜色、源零件哈希，以及组件身份、位置、约束和几何不变。
- **持续编辑与失败**：再次换色、后续改位置及保存均保色；原生执行中途失败后恢复原有颜色及「无组件外观」状态。读回错误和失配另用离线受控用例覆盖。

实机成功必须同时具备**颜色核验**和 `saved_file_reloaded_and_verified=true`，并目视确认显示效果；组件外观读回与屏幕实际显示**分别验收**。

**当前执行状态**：上述验收项**全部未执行**。本阶段仅完成台账登记、工作卡与文档/示例收尾；离线实现、匹配 SDK 构建与本机实机验收均待后续安排。按当前项目规则，不要求 Creo 10 独立复测或双版本验收；其他环境收到具体反馈后再跟进，证据始终标明实际环境。禁止只写「能运行」或引用历史成功数代替本次验收。

## 实现与证据

**2026-11-01（离线实现落地，隔离工作树分支 `codex/FEAT-052-assembly-recolor`，提交 7f944ad / b3db096 / 1d37aff，基于 89ee542）**

- Python 侧：`src/creo_mechdog/appearance.py` 承载全部业务逻辑（RGB/族名校验、自动分族按绑定唯一 `source_model_id`、显式族表完整覆盖与去重、注册表只读预览分页（≤32 KiB、游标绑定 revision+请求+快照指纹）、作业提交与 full/compact 结果投影、外观基线缺失时拒绝执行并指引 `creo_save_model`）；`server.py` 注册 `creo_recolor_assembly`；`schema.py` 新增 `RecolorAssemblyOp` 并在计划校验中拒绝引用计划内后建组件；`generic_bridge.py`/`bridge.py` 接入通道锁内准入与 compact 投影；`capabilities.py` 登记 `recolor_assembly` 操作与 `assembly_appearance` 能力族。
- 原生侧：`native/appearance.h` 组件外观设置与读回（`ProMdlTypeGet` 取实际类型构造 `ProAsmitem`，修正建议包传 `PRO_FEATURE` 的问题；`ProMdlVisibleSideAppearancepropsGet` 的 `PRO_TK_NOT_EXIST` 区分「无组件外观」）、写前三态基线、写后与保存擦除重载后两阶段读回（容差 1e-6）、失败回滚外观核对；`generic.cpp` 分发与保存核验/回滚接入；`advanced.cpp` 组件检查条目增加三态 `appearance` 字段；`preview.h` 提取共享窗口绑定/重绘链。只按 Python 显式 `assignments` 定位，不按遍历序或名称前缀猜族。
- 集成期修正两处接缝问题：① `schema.py` 顶层 import `appearance.py` 会拖入根目录 `bridge`，破坏「包导入不依赖工作目录」契约（`test_helper_layout` 失败）——纯校验函数移入 `schema.py`、依赖反转为 appearance→schema；② 显式族表按特征 ID 引用（组件无标签时唯一途径）时 `assignments[].label` 为整数，原生按字符串取值会抛类型异常——原生接受 string|int 双引用并优先使用附带 `feature_id` 复核，去重键改为解析后特征 ID。
- 命令与结果（隔离工作树独立 `.venv`，Python 3.12.14 / ruff 0.17.0 / clang-format 23.1.3 / MSVC，匹配 Creo 12.4.0.0 SDK；源码提交后 clean）：

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | 0 | `build\creo_worker.exe` 产出；基线（实现前）同样通过 |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests` | 0 | **1812 tests OK**（基线 1782 OK；+30 为 `tests/unit/test_assembly_appearance.py`；多轮复跑均 OK，期间一次单例瞬时失败复跑消失） |
| `.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit` | 0 | `success=true`，0 新增诊断，无未格式化新增文件 |
| `.\.venv\Scripts\clang-format.exe --dry-run --Werror native\appearance.h native\generic.cpp native\advanced.cpp native\preview.h` | 0 | 格式通过 |

- 口径更新：`capabilities.py` 已登记 95 个工具（94 既有 + `creo_recolor_assembly`）；工具已在离线单测下可用，但**实机行为全部未验证**。
- 未测范围：`tools/test_assembly_appearance.py` 已编写但**未运行**（本阶段按计划不连接 Creo）——80 组件/12 族夹具、写色与两阶段读回、保存擦除重载保色、源零件字节不变、身份/位置/约束/几何不变、再次换色与后续改位置/保存保色、中途失败回滚恢复、屏幕显示目视确认均待实机；原生 `recolor` 块真实返回形状未联调（离线单测用契约替身）；busy/并发沿用全局既有契约测试；WorkBuddy 黑盒验收、Creo 9/10 未测。

下一步：实机阶段遵循 BUG-001／BUG-091 会话准入要求，由用户重新发起后运行 `tools/test_assembly_appearance.py` 与装配针对性回归；合入 `main` 时按项目规则完成新版本发布。

### 2026-11-01 实机验收收口（run `assembly_appearance_live_20261101T060336Z558b3546`，28/28 通过）

**会话准入（BUG-001/BUG-091 四门槛逐项核对）**：本轮用户指派后经 `creo_startup.py` 受限 Explorer/PSF 路径**仅请求一次**启动（parametric 9140 / xtop 7072 / nmsd 9792 / pro_comm_msg 19684，2026-11-01 12:57:53–12:58:00 本地）；GUI 核验——xtop 唯一可见顶层窗口 "Creo Parametric 12"、`IsHungAppWindow=false`、无模态/警告弹窗、四进程 `Responding=True`；唯一 E 盘 dev 客户端（Codex 配置 C 盘旧项 `enabled=false`）、无并行构建/worker 替换/活动原生作业，工作树 `jobs/`/`models/` 空；主仓库历史 unknown 保护原样保留未触碰；驱动 `wait_for_startup` 实测 `startup=ready/connected=true` 后才提交任何作业。

**受测源码**：分支工作树 `c68beb2`+三项修复（提交 `3c4fa9d`/`e9ddc6d`/`b21dbb6`，文件内容与实机受测时一致，实机后按逻辑分组提交）；native `build/source.sha256=f7affbcb…8e36ecbc`、worker SHA256 `00730F45…`（R1/R2 轮）/`1FD68071…`（R3/R4 轮）。

**四轮时间线（UTC 报告目录即 run tag）**：

| 轮次 | 结果 | 定位与处置 |
| --- | --- | --- |
| R1 `20261101T050234Z74ca4441` | 14 作业全成功、3 检查过后中止 | 驱动"失败计划 1"误用三成员显式族表，被生产端在输入校验层**正确拒绝**（is_error、未建作业、revision 不变）——"族表必须无重复、完整覆盖组件"契约（计划文档）的活体证据；驱动改自动分族全量上色 |
| R2 `20261101T051854Z4ebece26` | 失败计划 1 全过（9 检查）后 round A 失败 | 作业 `f4d0d50c` 在 `save_and_reload` 阶段 `[json.exception.invalid_iterator.208] cannot use operator[] for object iterators`——`native/appearance.h` 保存重载比对与回滚比对两处对 `.find()` 迭代器误用下标（R1 未触发是因基线全 absent 不走 RGB 比较）；修复为 `(*a)[i]`/`(*b)[i]`（提交 `3c4fa9d`）。上色与读回本身已成功（painted=80、容差内、失败巡检颜色 present） |
| R3 `20261101T053544Z61515f3a` | 23 检查、1 项失败后放置段中止 | 失败计划 2 原生侧 `rollback_succeeded=true` 且 80/80 行核验通过，但顶层 `result.recolor` 经 `project_recolor` 白名单投影后**丢失** `rollback_appearance_verified/check`（操作条目块完整）——修复 `e9ddc6d` 透传两字段（+2 单测锁定不伪造）；驱动 `component_placement` 误带 schema 外 `placement` 字段被正确拒绝——驱动去字段（`b21dbb6`）。驱动 `ok = ok and check(...)` 短路导致依赖检查跳过，系驱动模式非生产缺陷 |
| R4 `20261101T060336Z558b3546` | **28/28 检查通过、退出码 0** | 全部验收项通过（见下） |

**R4 验收清单（全过）**：12 源件创建+保存重载 true；80 组件装配；初始全 absent（三态检查）；失败计划 1 全量自动分族上色→双 `remove_component` 原生失败→`rollback_succeeded=true`、`effect_status=rolled_back`、80 条 absent 基线、回滚后全员无组件外观、80 组件与身份恢复；round A 自动分族 80 painted 无 unmatched、12 族计数与建议包逐族一致、保存擦除重载前后读回 ≤1e-6、`saved_file_reloaded_and_verified=true`、revision+1；round B 显式族表+合族（`exp_crank_fan` 计 2 等 11 族）；round C 第三套色板复涂（读回与计数不变）；失败计划 2 显式全量表上色→原生失败→`rollback_appearance_verified=true`、回滚后全员回到 round A 颜色；`component_placement` 移动 c01 并保存后全员保色、仅 c01 位姿变化、体积不变、保存重载 true；12 源零件文件 SHA256 在（创建后/round A 后/B+C 后/最终）四个时点全部不变。

**目视确认**：截屏 `build/assembly_appearance_live_20261101T060336Z558b3546/visual_check.png`（本机生成物）；编排方视觉核验——3D 区域呈现约 8–12 种可辨实色族（紫/蓝/绿/橙/青等）、网格规整、无弹窗无警告。

**针对性回归（同会话串行）**：`tools/test_assembly_pipeline.py --session-health-verified` 两跑均 success=true（13 断言、10 作业全 succeeded，报告 `build/assembly_pipeline_live_20261101T061539Z75cf1bfe/report.json`）；`tools/test_t07_preview.py --live --confirm-session-usable` `preview_acceptance=passed`（7 例、`empty_part` 按预期 `skipped_no_geometry`，报告 `build/t07_preview_feat052_regress_20261101.json`）。覆盖本次触碰的装配检查（含新外观字段）与 preview 共享链。

**修复后离线验证**：`-m unittest discover -s tests` **1814/1814 OK**（1812 基线+2 投影锁定新增）；`tools/dev_check.py` success=true（0 新增语言/格式回归）；`clang-format 23.1.3 --dry-run --Werror native/appearance.h` 通过。

**未测范围（保持开放）**：busy/并发通道交错；`dry_run` 预览分页与游标失效的实机路径（离线单测范围）；非法输入拒绝的实机路径（生产拒绝已在 R1 以真实族表拒绝形式覆盖一类，其余离线单测范围）；读回错误/失配故障注入（离线受控范围）；WorkBuddy 纯 MCP 黑盒验收（按项目约定单独执行）；除本机 Creo 12.4.0.0 外所有版本（Creo 9 无 SDK、Creo 10 不作门槛）；实机成功不外推其他环境。

**结论**：FEAT-052 实机验收通过，随 **0.11.0**（MINOR，公开工具 94→95）交付；版本入口/版本说明/台账/兼容矩阵/README 已同步。

**2026-11-01（登记，仅文档与示例，无代码变更）**

- 依据计划文件登记本卡；在 [BACKLOG](../BACKLOG.md) 新增 FEAT-052 行（P2，状态「开发中」）。
- 能力说明同步：README 建模能力表补入 `creo_recolor_assembly` 条目与边界，开发分支工具数记为 95（已发布的 0.10.1 仍为 94）；`AGENTS.md` 的「本开发分支94个」改为「95个」；兼容矩阵的开发分支边界节预告本项增量。
- 新增调用示例 `examples/assembly_recolor_families.json`（单层装配显式族表 + 色板）。
- 本轮**未修改任何生产代码**（`capabilities.py`、`server.py`、`native/**` 均未动），**未连接 Creo**、未启动 MCP 服务、未编译执行器、未运行单元测试。

**命令与结果（2026-11-01，Windows x64 / `.venv` Python 3.12.14 / MSVC 未涉及；工作区 dirty=是）**

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit --work-item FEAT-052` | 0 | style 阶段通过（`success=true`），无新增 lint、无新增未格式化文件；unit 阶段按 `--skip-unit` 未执行 |
| `.\.venv\Scripts\python.exe -m ruff format --check`（本轮修改与新建的 6 个 Markdown） | 0 | 6 files already formatted（ruff 0.17.0 会格式化 Markdown 代码块，已核对无差异） |

说明：本机 `.venv` 原先未安装 `ruff==0.17.0` 与 `clang-format==23.1.3`（`requirements-dev.txt` 已锁定该版本），为执行上述检查临时安装、完成后已卸载，`.venv` 恢复到原状。`build/development_check.json` 为本机生成物（`.gitignore` 已排除），不进入源码包。

**口径说明**：本卡的 95 是**开发分支登记口径**（工具随本条目的实现落地）。当前 `capabilities.py` 仍只注册 94 个工具，`creo_recolor_assembly` 尚未接入工具注册与能力声明；实施完成前 `creo_capabilities` 实际可见清单仍是 94 个，不得据此宣称工具已可用。

**未测范围（全部）**：自动分族与显式族表的实际分组结果、族表重复/遗漏拒绝、非法 RGB 拒绝、过期 revision 拒绝、非装配与缺件拒绝；预览的无 Toolkit 调用、无作业、无 revision 变化与 32 KiB 分页、游标失效；实机 80 组件 / 12 族夹具的写色、逐组件读回、保存擦除重载后颜色（RGB 绝对误差 ≤ `1e-6`）与源零件字节不变；再次换色与后续改位置/保存保色；原生中途失败后的颜色恢复；屏幕显示效果的目视确认；单元测试、匹配 SDK 构建、Creo 9/10 与 WorkBuddy 范围。

下一步：按计划文件实施离线实现（`src/creo_mechdog/appearance.py`、`native/appearance.h`）、工具注册与计划操作接入，随后安排匹配 SDK 构建与本机实机验收。
