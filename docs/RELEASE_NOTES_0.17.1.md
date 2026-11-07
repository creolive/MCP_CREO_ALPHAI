# MCP_CREO_MechDog 0.17.1 版本说明

2026-11-07，PATCH 修复批；条目：[BUG-115](work-items/BUG-115.md)（同计划 `fill → trim → thicken` 准入）与 [FEAT-005](work-items/FEAT-005.md)（过期 revision 回执）。公开工具仍为 **100** 个，无新增工具、无删除工具、无必填参数变化。

本批为离线交付：按 BUG-001 纪律未连接 Creo、未新建 Toolkit 通道。原生根因与实机复验未在本轮完成，相关边界在下方“未验证范围”明确列出。

## BUG-115：同计划 `fill → trim → thicken` 提交前准入

2026-11-06 实机 12 例中，3 例在**同一计划**里新建 `surface_fill` → `surface_trim` → `thicken` 时报
`ProFeatureGeomitemVisit(PRO_QUILT) … -4`，`save_failure=null`、基线不变、保护未释放；而投影依赖组（trim 的 target 来自更早提交）3/3 成功。

`validate_operations` 现在只对“**整条链都在本计划新建**”的组合在创建 job 前拒绝：当 `thicken` 以
`quilt_feature` 引用同计划较早的 `surface_trim`，且该 trim 的 `target` 也是在同计划较早创建的 quilt 时，返回可执行替代：

1. 先提交 `surface_fill` / `surface_trim`，再在第二个计划中让 `thicken` 引用已存在的 quilt 特征；或
2. 使用 `creo_inspect_model` 读回的显式 `{kind:"quilt",id:N}`。

trim 的 target 来自更早提交（投影依赖组）、`fill → thicken` 同计划、显式 quilt id 均不受影响，避免把已知成功的路线一并挡住。该准入是用户侧保护，不是原生根因修复；若后续原生分阶段再生修复，可移除。

## FEAT-005：过期 revision 拒绝补齐三个字段

revision 冲突仍**在创建 job 前拒绝**，拒绝文本改为：

```
Stale revision: model_id=… current_revision=… expected_revision=…; no job was created
```

调用者不必再发一次巡检就能看到是哪个模型、当前版本与期望版本不一致。`tests/test_registry_io.py` 精确断言三个字段。

## R12 断流/取消的离线覆盖

未改生产代码。客户端突死、未消费管道与 EOF 收尾已由 `tests/unit/test_stdio_lifecycle.py` 在离线覆盖；真实网络断流与客户端取消仍属实机未验项。

## 本版验证门禁

- `tools/test_unit.py` 全量 **2726 项通过**，0 失败 0 错误（起点 2723，新增 3 条 BUG-115 回归）。
- 种子内容未变，仅两份清单的 `compatible_server_version` 同步：种子包两次确定性构建同摘要
  `83d4b6162894fe61015c74bba231cad73b36ccaa74e82cb7f35a9f31f82db74f`，已回填 `docs/seed_package.json` 并二次构建确认稳定。
- 受测源码身份、构建退出码与远端核对结果见[发布记录](validation/RELEASE-0.17.1.md)。

未验证范围：Creo 实机（本轮未连接）；BUG-115 的原生根因、投影依赖组在准入后的复验、`thicken` 引用 `surface_offset` 产物的组合；R12 真实断流/客户端取消；WorkBuddy 公开 MCP 黑盒（用户决定由其它机器单独测试）；Creo 9（本机无 SDK）与 Creo 10 实机。DEV-002 剩余包化、装配 bbox/erase 耗时/rename/managed delete、R11 quilt merge 与多截面 `surface_loft`、DEV-030 履带 G2—G4、FEAT-014 corner relief/relief 材料几何与 `offset_mm` 带移除语义仍按台账阻塞登记，不在本版范围。

升级使用配套的 `MCP_CREO_MechDog-0.17.1-source.zip` 与 `MCP_CREO_MechDog-0.17.1-seed-library.zip`，按安装说明更新环境、重编执行器并重启 MCP 服务。旧种子包会被版本闸门拒绝。
