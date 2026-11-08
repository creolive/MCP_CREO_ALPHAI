# MCP_CREO_MechDog 0.18.1 版本说明

2026-11-07，PATCH：**质量属性回执契约与台账精简批**。本版为 [FEAT-057](work-items/FEAT-057.md) 补齐材料密度、质量单位与“质量不可用原因”的回执契约，并合入 [DEV-073](work-items/DEV-073.md) 的 BUG 台账复核与开发文档精简。公开工具仍 **102**，无新增/删除工具。原生执行器源码有变更，升级需重新编译；本版只完成离线门禁与原生组合编译，**未连接 Creo 实机**。

## 本版内容

| 条目 | 本版结果 | 证据 |
| --- | --- | --- |
| [FEAT-057](work-items/FEAT-057.md) 密度/单位/缺失原因契约 | `creo_get_mass_properties` 回执新增 `mass_unavailable_reason`：`material_query_failed`、`unsupported_mass_unit`、`material_density_unavailable`、`volume_unavailable`、`no_density`，并给出对应提示；Python 归一化拒绝未知原因和“有密度来源却带原因”的矛盾组合，旧原生回执缺字段时保留 `null`。单位口径固定：`mass_g` 恒为克、`density_g_cm3` 恒为 g/cm³，`mass_unit` 是模型自身单位名，仅 `g`/`kg`/`tonne` 参与换算 | `native/generic.cpp`、`src/creo_mechdog/mass_properties.py`、`tests/unit/test_mass_properties.py`（24 例）、`server.py` 工具说明 |
| [DEV-073](work-items/DEV-073.md) 台账复核与文档精简 | 88 项 BUG 按“仍需修复 / 待复现核实 / 已有修复待验收 / 观察 / 其它 agent 范围 / 完成归档”重新分类并逐项写入台账；`docs/DEVELOPMENT.md` 收敛为入口（约 8 KB），`docs/BACKLOG.md` 收敛为当前台账（约 37 KB），历史进展保留在既有归档文件。合并时保留 0.18.0 发布记录与版本事实 | 77 个 Markdown 文件与 DEV-073 工作卡；当次分支核验 1507 个本地链接、165 个当前唯一 ID、486 份历史文件字节一致 |

## 兼容性与接口

- 无工具增删，公开工具仍 **102**；`creo_get_mass_properties` 签名与既有字段不变，仅新增 `mass_unavailable_reason`（仅质量不可用时非空）。
- 旧原生执行器回执缺少新字段时按 `null` 处理，不误判为版本错误；新回执带未知原因会被拒绝。
- 文档入口变化：当前待办只查 `docs/BACKLOG.md`，开发规则查 `docs/DEVELOPMENT.md`；历史逐版记录保留在版本说明与 `docs/validation/RELEASE-*.md`。
- 原生执行器源码有变更（质量属性原因分支），升级需按 `bridge.py build` 重新编译。

## 门禁

- 全量单元测试 **2830 项，0 失败、0 错误、2 跳过**。
- `tools/dev_check.py` `success=true`（提交 `282a69a`、dirty=false、源码指纹 `f3d5eef8…`；24 条 lint / 12 个未格式化文件为存量基线）。
- `python bridge.py build` 在 Windows x64、Creo 12.4.0.0 匹配 Toolkit SDK 下编译通过（`build/creo_worker.exe`）。
- 种子包 24 个文件、9 个种子，两次构建同摘要 `8e5f5125…`，已回填 `docs/seed_package.json`。

## 未验证范围

- **Creo 实机**：本版未连接 Creo/Toolkit；原生原因分支、真实材料密度、英寸/磅单位模型、保存与重载均无实机证据，组合编译只证明可编译。
- FEAT-057 主惯量、装配 occurrence 汇总与 `complete` 契约仍开放。
- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器执行）；Creo 9（本机无 SDK）与 Creo 10 实机。
- DEV-073 的链接与 ID 核验在合入前的文档分支执行；合入 main 后未重跑全量链接检查。

## 升级

1. 拉取本版本源码并执行 `python -m pip install --no-deps -e .`。
2. 执行 `python bridge.py build` 重新编译执行器（原生源码有变更）。
3. 重启 MCP 服务；旧客户端可忽略新增回执字段。
