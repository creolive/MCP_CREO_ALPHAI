# alphai D：会话上下文、产品规则和版本文件工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供可追溯的会话上下文、脱敏规则到只读计划、受保护的模型文件版本清理。

**Architecture:** D01 聚合现有状态，显式 live 才进原生只读通道；D02 为纯规则转换，不提交建模；D03 沿用 inspect/apply、证据和幂等范式，处理文件回收并保护受管恢复资料。

**Tech Stack:** Python 3.12+ / unittest、现有 stdio MCP、受控 Windows 回收站适配；仅 D01 live 涉及 Toolkit。

**Spec:** [设计依据](../specs/2026-11-03-alphai-capability-adoption-design.md)；[主计划](2026-11-03-alphai-capability-adoption-plan.md)。

## Global Constraints

继承设计/主计划全部约束；不改正常用户工作目录，不复制对方“最大 PID”选择规则，不把历史证据当 live。D02 不读取公司原始资料到公开包，D03 不清任意目录/用户文件/unknown。不新增自动清理或后台任务。实机先满足 BUG-001 条件。

## Review Focus

- D01：旧 ready、跨进程身份、空窗口、多 Creo 会话与 busy，要逐字段说明时效/来源，不自动切会话。
- D02：未知字段、单位错误、模板越权、能力缺失、参数边界，不生成貌似可执行的半成计划。
- D03：路径穿越、重解析点、token 过期、引用变化、文件占用都要保留并解释。
- D03：相同幂等键重放不能重复回收；部分回收失败不声称原子回滚。
- 所有输出遵守 32 KiB；内部文件清理和占用注入不能混入 WorkBuddy 通过结论。

---

## D01 / FEAT-001：统一会话上下文

**Files:** Create `src/creo_mechdog/session_context.py`；Modify 现有 `creo_session_status` 包内聚合接入、`server.py` 参数映射/能力说明；必要原生查询加到现有读取分发；Test `tests/unit/test_session_context.py`、`tools/test_adoption_session_context.py`，复用 `tests/unit/test_t10_session_health.py`；Docs FEAT-001 卡及 `docs/development/ALPHAI-D01-ACCEPTANCE.md`。

**Interfaces:** 保持现有 `creo_session_status` 返回兼容，拟增可选 `context:bool=False, live:bool=False`；包内 `session_context_snapshot(*, live: bool=False) -> dict`。context 下逐字段返回 `value/source/checked_at/age_seconds/status`，status 为 known/unknown/stale；已知会话身份、工作目录、当前模型、顶层装配、骨架各自可未知。live=false 默认不连接 Toolkit；live=true 同一锁/有界超时读取，busy 使用既有拒绝，不排队。顶层装配不能按文件名五个零猜定；没有 API/显式绑定就 unknown。

- [ ] **1. 写回归** `test_default_does_not_connect`、`test_old_ready_is_not_live_health`、`test_pid_reuse_start_time_mismatch_unknown`、`test_multiple_sessions_not_latest_pid`、`test_no_current_model_is_explicit`、`test_busy_live_does_not_enqueue`；`live=true,context=false` 必须在入口拒绝，不能忽略请求或意外连接。运行 `python -m unittest tests.unit.test_session_context tests.unit.test_t10_session_health -v`。
- [ ] **2. 实现聚合**：复用现有 session_health/启动身份与查询时间，不改其恢复结论；字段来源有冲突就标未知，不能给旧数据重打当前时间当新鲜。live 查询不显示/保存模型、不改变工作目录/活动模型、不加载常驻 DLL；查询失败保留原 API/码与检查时间。
- [ ] **3. 验证**：离线桩覆盖关闭/重启/多会话/旧记录；默认离线驱动只查投影判据，不连接。获窗口后串行验证默认无连接、live 当前模型/工作目录与 API 一致、空窗口和错误回包。记录源文件/revision/窗口不变；不重启 Creo 制造场景，不宣称多会话实机通过。无需保存重载指标，查询无修改本身为验收。
- [ ] **4. 提交** `FEAT-001: expose sourced session context`；本项不自动关闭 BUG-011 的旧环境问题或 FEAT-001 启动/重连全部范围。

## D02 / FEAT-063：产品规则与只读改型计划

**Files:** Create `src/creo_mechdog/product_rules.py`、`examples/product_rules/box_frame.json`、`docs/PRODUCT_RULES.md`；Modify schema/能力及 `server.py` 只读注册、资源打包白名单（确有需要才改）；Test `tests/unit/test_product_rules.py`、`tools/test_adoption_product_rules.py`；Docs FEAT-063 卡及 `docs/development/ALPHAI-D02-ACCEPTANCE.md`。

**Interfaces:** 拟 `creo_plan_product_variant(template_id: str, parameters: dict) -> dict`，包内 `build_product_plan(template_id: str, parameters: dict, capability_snapshot: dict) -> dict`。只读取随源码交付的白名单模板，不接受任意模板路径/脚本。返回 `template_id/template_version/template_sha256/normalized_parameters/required_capabilities/plan/blocking_items/executable`；首版仅用已支持操作生成新的箱体/机架独立模型计划。executable=false 时计划明确禁止直接执行，不能凭规则存在标完成。

- [ ] **1. 冻结模板格式并写回归**：模板含 schema_version、单位、参数范围、固定操作白名单、验证条件；禁止 eval/exec/任意表达式和模型名拼路径。`test_unknown_template_or_parameter_refused`、`test_mm_degree_units_required`、`test_out_of_range_and_boolean_refused`、`test_missing_capability_blocks_plan`、`test_same_inputs_same_digest_and_plan`、`test_planner_never_connects_or_submits`；运行 `python -m unittest tests.unit.test_product_rules -v`。
- [ ] **2. 实现**：参数到 schema 校验过的 execute_plan 操作转换，保留模板版本/摘要和独立几何判据；响应超预算按现有分页/文件回执方式处理，不能截断操作。旧公司型号库、气弹簧力学公式和未实现 B02 操作不进入首版默认模板。
- [ ] **3. 验证**：专项、默认离线驱动，无 SDK 可独立验收规划器；默认箱体/机架至少两种尺寸，生成计划经过现有 schema，预期体积来自独立解析，不依赖工具成功字段。若要声明建模模板可用，由会话负责人另行通过公开 execute_plan 执行一次并核几何/保存重载；没有该证据只交付“规则与规划器已测”。
- [ ] **4. 提交** `FEAT-063: plan variants from versioned product rules`；模板参数范围/未实现步骤与对方历史数据分开，不报告 14 步自动改型完成。

## D03 / FEAT-064：模型族历史版本清理

**Files:** Create `src/creo_mechdog/model_version_reclaim.py`、`src/creo_mechdog/windows_recycle.py`；Modify 既有注册/检查点/依赖查询只读接入、能力和 `server.py`；Test `tests/unit/test_model_version_reclaim.py`、`tools/test_adoption_model_version_reclaim.py`；Docs FEAT-064 卡及 `docs/development/ALPHAI-D03-RECLAIM-CONTRACT.md`。

**Interfaces:** 拟 `creo_reclaim_model_versions(action:'inspect'|'apply', model_id:str, keep_versions:list[str]|None=None, evidence_token:str|None=None, idempotency_key:str|None=None, limit:int=20, cursor:str|None=None) -> dict`。只在注册可证明属于本项目的受管目录扫描该模型族直接子文件；inspect 不连接 Toolkit、不移动文件，证据有效期600秒，绑定目录/模型/引用/文件身份。apply 通过既有通道锁防止建模并发，但不进入 Toolkit。输出逐项 kept/recycled/failed/unknown 和原因；回收站失败不退成永久删除。

- [ ] **1. 先冻结保护集并写回归**：当前文件、所有检查点/回退/源文件/组件快照、B01/B02/C04 事务中和 unknown 引用全部保留；不能完整枚举保护集时拒绝 apply。`test_keep_checkpoint_and_snapshot`、`test_token_expires_at_600_seconds`、`test_changed_file_or_reference_refused`、`test_reparse_or_path_escape_refused`、`test_casefold_family_exact_match`、`test_occupied_file_kept`、`test_same_key_does_not_recycle_twice`、`test_partial_failure_not_rolled_back`；运行 `python -m unittest tests.unit.test_model_version_reclaim -v`。
- [ ] **2. 实现**：保留具体文件身份与哈希/大小/mtime 的检查证据，在锁内重查引用和文件再移动。Windows 全流程使用经过验证的绝对 LiteralPath/原生文件 API，不跨 shell 拼删除命令；先验证解析路径仍在允许的受管目录。文件系统竞态/占用无法排除时跳过并报告，不放宽保护。分页内容绑定冻结快照，证据过期/文件变动拒绝。
- [ ] **3. 验证**：先默认离线驱动，在专用临时目录模拟同族版本、无关族、检查点/快照、占用/变化/幂等/超时/部分失败。回收站真实调用只对本次创建且路径验证过的夹具，记录保留/回收清单，不拿用户模型作实验。核任意文件与未知引用均未动；此任务不连接 Creo，不套用几何保存重载验收。
- [ ] **4. 提交** `FEAT-064: inspect and recycle eligible model versions`；默认不随保存、启动或升级触发，不能借用现有 DLL 世代回收工具扩大删除范围。WorkBuddy 仅验证 MCP 预览/回执，内部占用和回收证明留开发者报告。

所有 `python` 命令使用项目 `.venv\Scripts\python.exe`。D02/D03 无需新 Toolkit 会话；D01 live 仅由会话负责人安排。
