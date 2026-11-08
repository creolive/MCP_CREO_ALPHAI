# 0.18.1 文件夹反馈离线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对比三份反馈和当前实现，补齐可离线验证内容，留下准确可执行的接手清单。

**Architecture:** 保留 server/bridge/native 边界；错误映射放包内统一校验边界，质量属性回执及原生类型守卫各自负责，不能模拟原生几何。已有 DEV-074 成果先验证再复用。

**Tech Stack:** Python 3.12+ / unittest / Ruff / C++17 / Windows（SDK仅离线编译）。

**Spec:** `docs/work-items/DEV-075.md` 与三份归档反馈。

## Global Constraints

- 不联网、不连接 Creo/Toolkit、不故障注入、不清 unknown、不修改本机配置，不合入 main、不发布、不改版本。
- 保留开始时五处用户未提交内容；历史 validation 原件逐字节不变。
- 未知数据为 null，计算/测量/外部证据区分，Toolkit busy 语义不变。

## Review Focus

独立工具与计划错误定位、错误中的业务数据泄漏、旧原生质量回执兼容、装配显式密度绕过、负 ID 与钣金原生能力混淆。

## Tasks

- [x] T1：新分支、三份原件字节归档、先登记；并行只读核对现有条目与实现。
- [x] T2：在 `src/creo_mechdog/schema.py` 与包内错误映射模块补简洁安全的 `validate_operations` 诊断，覆盖字段错误、模型级错误、多操作路径、未知 op；独立入口复用，不在 server 写业务逻辑。
- [x] T3：`mass_properties.py`、`generic_bridge.py`、原生 `mass_properties` 路径补类型拒绝、权威值单位/来源及专项单测；保留旧单位字段语义，以新增字段避免误读，未知不补猜。
- [x] T4：body 负 ID 拒绝改为准确能力诊断；补能力/语法/钣金 thin/revolve 边界说明和针对性回归；未验证原生融合不放行。
- [x] T5：核对 DEV-074 无 Git 降级等已有成果；修正当前入口与 FEAT-057 状态口径；归档报告外部正证据，逐章对照，不改历史发布记录。
- [x] T6：专项/全量单测、样式门禁、适用编译、无 Git 分发回归与独立审查；写验收记录、接手清单，只提交本批文件。

## 接口与预检

T2/T4 共享 schema，由同一实施者串行修改。T3 新增质量字段须由 compact/独立接口完整保留；类型守卫 Python 与原生各做一次，不能依赖任一层猜模型类型。T5 共享工作卡/台账由主代理汇总。

用户已明确要求先离线完成，本轮直接按现有报告和项目架构实施，不等待新的设计审批；具体实现选择和未完成项写入工作卡及交接记录。

## 执行记录

- `64b48d2`：校验、质量、body边界与反馈归档/台账。
- `6bc58a3`：完整保留已有plane提示、补7个遗漏原生测试源码夹具；兼容/打包100项通过。
- 独立审查发现MCP外层校验绕过新映射，已用SDK公开call_tool覆盖层修复，保留typed schema；后续自审补输出校验崩溃维持SDK遮蔽的反例。
- 工作区初轮2869项有3条诊断截短失败及2条运行中源码变化身份失败；前者已修，后者以冻结快照及独立身份回归48项通过处理，不能把初轮写成通过。
- 最终分发回归使用独立venv及持久导入路径，无.git、PATH无Git；修复仅依赖PYTHONPATH导致子进程导入另一checkout的初轮环境错误。

T6完成：最终冻结分发2878项0失败/0错误、2项SDK跳过，本机SDK2/2；样式success=true。首次原生编译成功、后续新组合busy未受理，真实几何/保存重载/远端仍由H01—H07交接。受测身份与失败轮次均见DEV-075-ACCEPTANCE.md。
