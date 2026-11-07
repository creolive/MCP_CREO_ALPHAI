# FEAT-063：D02离线产品规则规划器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成D02的独立离线内核：脱敏箱体模板和尺寸参数生成经过现有schema验证的建模候选计划。

**Architecture:** 新模块只读白名单JSON模板，使用固定Python配方生成既有sketch/extrude操作；消费调用方提供的能力快照，不探测服务。只读消费既有schema和SOURCE_PATHS。MCP接入、部署清单、打包与原生执行留待集成人统一安排。

**Tech Stack:** Python3.12+、标准库、现有Pydantic schema、unittest/Ruff；无SDK/Toolkit。

**Spec:** 本文接口契约为本阶段具体设计；继承原alphai D02/FEAT-063范围。用户2026-11-04授权继续其他任务并要求不影响曲面完善计划。本阶段只交付离线规划器，不宣称整个D02/MCP或原生模板验收完成。

## Global Constraints

- 基线main@90dbd6c33e9f732d1a5bd969bcf19d30b4b3a62c（0.12.0），分支codex/FEAT-063-offline-product-rules。只操作本次宿主create_worktree创建的独立工作树。
- 许可文件仅src/creo_mechdog/product_rules.py、examples/product_rules/box_frame.json、tests/unit/test_product_rules.py、tools/test_adoption_product_rules.py、docs/PRODUCT_RULES.md、docs/development/ALPHAI-D02-ACCEPTANCE.md、docs/work-items/FEAT-063.md和本计划。
- 不改server.py、schema.py、capabilities、native、bridge/generic_bridge、源码身份/打包/依赖/基线配置、主工作树台账/开发入口、任何曲面S/C/W文件或其他任务；既有schema只能导入调用。
- 不连接/启动/重启Creo，不调用MCP/Toolkit，不编译执行器，不运行live驱动，不合main/推送/发布。不复制native/constants.inc。本工作树只是离线源码环境，不注册为Creo客户端服务。
- 不新增依赖；测试解释器/包resource_root必须属于本工作树。可以建立本工作树忽略的.venv/build/SDD记录，不能更改其他环境。
- 所有数字拒绝bool、NaN、Inf、不能转换的巨大整数；长度毫米、角度度。不执行eval/exec/任意脚本，不接受调用方模板路径。
- 返回可JSON序列化且整体UTF-8大小≤32768字节；超限明确报错，不能截断操作。未知/缺失能力不冒充支持。
- 本任务纯函数不提交作业、不写文件、不占Toolkit锁；无job_id/model_id/revision/几何实测值。模型体积/包络只能标为预期解析值。driver可在显式输出目录/本工作树build写验证报告。

## Review Focus

- 白名单ID不得变成任意路径；模板units/schema/recipe/参数声明错误必须拒绝。
- bool/非有限/巨大数、未知参数和尺寸退化都在生成计划前拒绝。
- 缺能力/未知快照必须executable=false且plan=null，不输出可误用的半计划。
- 开口箱体切除方向、支撑offset与体积公式必须一致；schema通过不等于Creo实机通过。
- 相同资源字节/输入/快照应有同一摘要与计划，不修改调用方字典或引用上次返回对象。

## 本阶段接口与模板

公开包函数：`build_product_plan(template_id: str, parameters: dict, capability_snapshot: dict | None) -> dict`。不注册creo_plan_product_variant。

白名单首版只有`box_frame`，资源为`SOURCE_PATHS.resource_root / examples/product_rules/box_frame.json`；ID严格查表，不拼接用户路径。资源错误/不支持ID和非法参数抛含上下文ValueError。

模板JSON字段：schema_version=1、template_id="box_frame"、template_version="1.0.0"、units={length:"mm",angle:"deg"}、recipe="open_rectangular_box_v1"、operation_allowlist=["sketch","extrude"]、parameters与validation。recipe为实现内固定枚举，不解释模板表达式/代码。

parameters为下面四个字段的default/minimum/maximum声明；调用参数可省略并用默认，但不接受额外字段、字符串、bool或非有限数：

| 字段 | 默认 | 最小 | 最大 |
| --- | --- | --- | --- |
| length_mm | 100 | 10 | 1000 |
| width_mm | 60 | 10 | 1000 |
| height_mm | 40 | 10 | 1000 |
| wall_mm | 2 | 0.5 | 20 |

validation.minimum_cavity_mm=1；L-2t、W-2t、H-t都必须≥1mm。校验资源声明的字段/单位/版本/有限边界及默认值一致性；未知recipe/schema不降级执行。template_sha256为实际读取的模板原始字节SHA256。

固定四操作（label均固定小写、唯一、≤28字符）：

1. outer_profile草图，XY/offset0/coordinates，命名矩形outer_rect，min[0,0]、max[L,W]。
2. outer_body盲拉伸，sketch=outer_profile、depth=H、mode=add、direction=positive。
3. cavity_profile草图，XY/offset=H/coordinates，矩形cavity_rect，min[t,t]、max[L-t,W-t]。
4. cavity_cut盲切除，sketch=cavity_profile、depth=H-t、mode=cut、direction=negative。

生成操作须调用现有`validate_operations`，不改变其契约；plan形状为{"operations": validated_operations}，供未来调用方显式提交。

能力快照适配层最小形状是{"operations":["sketch","extrude",...]}，可含其他元数据；本函数不读取运行时。operations须为list[str]，无快照/无operations为unknown，空表为明确缺能力，其他非法类型ValueError。额外的已知操作不影响输出。缺sketch/extrude时blocking_items逐项说明；不默认为当前版本支持。

返回必需字段：template_id/template_version/template_sha256/normalized_parameters/required_capabilities/plan/blocking_items/executable。额外固定字段expected_geometry={volume_mm3:L*W*H-(L-2t)*(W-2t)*(H-t),bbox_mm:{min:[0,0,0],max:[L,W,H]}}和validation={schema:"passed",native:"not_run",saved_reload:"not_run"}。executable仅表示结构与能力快照准入；绝不表示几何已经执行或验收。缺能力时plan=null、executable=false，blocking_items必须包含可定位code/capability或unknown原因。

默认预期体积35712mm³；第二尺寸120×80×50/t3预期83508mm³。保留能力/资源摘要和预期判据；不引用公司私密数据、气弹簧公式或尚未支持曲面操作。

### Task 1: 离线规则内核、模板与验证

**Files:** 按Global Constraints八个许可文件新增/修改。工作卡状态只记“开发中：离线内核已交付，MCP接入/实机待验”，历史来源不改写。

**Interfaces:** 上述build_product_plan及最小能力快照。固定数据声明与固定配方分离，不写通用表达式解释器/框架，不引入其他建模场景。

- [x] **Step 1:** 新增真实行为回归，先运行`python -m unittest tests.unit.test_product_rules -v`取得缺功能RED。至少覆盖默认/第二尺寸与独立解析体积、现有schema、方向/offset、参数边界/退化、未知ID/参数、路径逃逸、bool/NaN/Inf/巨大整数、模板单位/版本/recipe错误、能力缺失/未知/格式错误、确定性/输入和返回隔离、整体32KiB以及纯函数无写盘/进程/网络/作业提交。
- [x] **Step 2:** 实现白名单模板和最小内核；只读消费schema/paths，禁止导入server/bridge/generic_bridge或创建服务客户端；在返回前校验schema和完整JSON预算。错误要指出字段或模板问题，不能静默猜改。
- [x] **Step 3:** 增加默认离线driver。至少验证两组尺寸、能力缺失blocked和非法参数拒绝；提供可解析报告与相关源码文件哈希，不依赖git/SDK/外部程序。CLI不提供--live，未知参数应在执行前拒绝。默认输出到本工作树build下唯一目录，支持--output供隔离测试；核心函数自身仍不写盘。
- [x] **Step 4:** 专项GREEN、driver报告、改动Python文件Ruff check/format check；运行一次完整`tools/dev_check.py --work-item FEAT-063-offline-product-rules`。若完整检查被环境或既有问题阻断，先核本工作树导入/环境，保留真实结果，不改无关文件或基线；需要时单独全量test_unit补单测证据，不冒充dev_check通过。
- [x] **Step 5:** 文档写明使用示例、能力快照适配形状、executable含义、解析预期与未执行区别、错误/边界和MCP/部署清单/打包/实机接入待办；验收记录实际提交基线/dirty/导入路径/指纹/命令/结果。原始测试与审查日志保存在本工作树build/feat063_offline_product_rules_20261104/。
- [x] **Step 6:** 自查只含八文件并提交到本开发分支，标题带FEAT-063；不推送/合main。交接控制者独立任务审查与最终范围审查；不要自行派生Agent或领取B01/曲面工作。

## 交付边界

离线内核可独立验证。后续集成人再注册MCP工具、登记server源码身份、核资源分发白名单并安排实机；本阶段不因只读设计而越过这些接入要求，也不把未执行模板标原生supported。


## Task 1 执行结果（2026-11-04）

离线实现、专项 9 项、driver 与 Ruff 通过；整仓 dev_check 已运行一次但未通过：
2295 项、0 failures、3 errors、2 skipped，详见本任务验收记录。
三项错误的原始日志已保留，未越界修复环境/其他测试。
状态：开发中：离线内核已交付，MCP接入/实机待验。
作者自查完成，独立审查与最终范围审查由控制者接手，不自行派生 Agent。
