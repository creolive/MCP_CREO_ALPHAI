# 0.17.1 发布记录（2026-11-07）

- 条目：[BUG-115](../work-items/BUG-115.md)（同计划 `fill → trim → thicken` 提交前准入）、[FEAT-005](../work-items/FEAT-005.md)（过期 revision 回执补齐三个字段），PATCH 性质；公开工具仍 **100**，无新增/删除工具，无必填参数变化。
- 基线：上一已发布版本 **0.17.0**（`main` 提交 `21622d5`，标签 `v0.17.0`，见 [RELEASE-0.17.0](RELEASE-0.17.0.md)）。
- 开发分支：`codex/0.17.1-offline-batch`，基于 `21622d5`。
- 目标版本：`v0.17.1`、Release 与四份附件。最终发布提交、标签对象与附件远端核对结果记录在本次发布的 Release body 与交付说明中。
- 验收方式：离线。按 BUG-001 纪律**未连接 Creo、未新建 Toolkit 通道、未做故障注入、未清 unknown 保护**。

## 验收范围

| 项目 | 结果 |
| --- | --- |
| 原生编译 `bridge.py build` | 退出 0，`build/creo_worker.exe` 未因本版变更重编（本版未改 `native/`） |
| 全量单元测试 `tools/dev_check.py` | **2726 项通过**，0 失败 0 错误（0.17.0 起点 2723，本版新增 3 条 BUG-115 回归）；`success=true` |
| 语言与格式 | 未高于 `style-baseline.json`；首次检查有 2 个格式回归（`src/creo_mechdog/schema.py`、`tools/test_surface_save_recovery.py`），执行 `ruff format` 后复查通过 |
| 种子包 `tools/package_seeds.py` | 24 文件、9 种子；两次确定性构建同为 SHA256 `83d4b6162894fe61015c74bba231cad73b36ccaa74e82cb7f35a9f31f82db74f`；`docs/seed_package.json` 回填后二次构建校验通过 |
| 源码包 `tools/package.py --seed-archive …` | 见下方交付清单（摘要与 Release body 一致） |

源码身份：`version.py` = 0.17.1；受测源码为发布分支提交加版本元数据/文档改动（`dirty=true`，仅版本与发布文档，未改原生代码）；**最终受测提交以合入 `main` 的 0.17.1 发布提交为准**，附件由该提交源码生成。

## 交付内容

| 内容 | 结论 | 依据 |
| --- | --- | --- |
| BUG-115 同计划准入 | ✅ 已合入 | `validate_operations`：`thicken` 引用同计划较早 `surface_trim` 且该 trim 的 `target` 也是同计划新建 quilt 时，提交前拒绝并给“拆分提交或显式 quilt id”替代；投影依赖组、`fill → thicken`、显式 quilt id 不受影响 |
| BUG-115 驱动适配 | ✅ 已合入 | `tools/test_surface_save_recovery.py --live` 把该组提交前拒绝记为 `model_status=refused_expected` 并给出拆分动作，不再计为原生失败；本轮未执行该 live 驱动 |
| FEAT-005 revision 回执 | ✅ 已合入 | `generic_bridge` 拒绝文本含 `model_id`/`current_revision`/`expected_revision`，仍不创建 job；`tests/test_registry_io.py` 精确断言 |
| 回归用例 | ✅ 已合入 | `tests/unit/test_surface_trim_schema.py` 三条 BUG-115 用例；全量 2726 项通过 |
| R12 断流/取消离线覆盖 | ✅ 既有覆盖 | `tests/unit/test_stdio_lifecycle.py` 的客户端突死、未消费管道、EOF 收尾；本版未改生产代码 |

## 未验证范围

- Creo 实机（本轮未连接）：BUG-115 的原生根因、准入后投影依赖组复验、`thicken` 引用 `surface_offset` 产物的组合。
- R12 真实断流与客户端取消。
- WorkBuddy 公开 MCP 黑盒（用户决定由其它机器单独测试）。
- Creo 9（本机无 SDK）与 Creo 10 实机。
- 台账已登记但仍阻塞的条目：DEV-002 剩余 `server.py`/`bridge.py`/`generic_bridge.py`/`creo_startup.py` 包化（需 MCP stdio 握手与会话级验证）、装配 bbox/erase 耗时/rename/managed delete、R11 quilt merge 与多截面 `surface_loft`、DEV-030 履带 G2—G4、FEAT-014 corner relief/relief 材料几何与 `offset_mm` 带移除语义、其余需失败原件或 Creo 会话复现的 P1/BUG 项。

## 附件与远端核对

应有四个文件：`MCP_CREO_MechDog-0.17.1-source.zip`、`MCP_CREO_MechDog-0.17.1-source.zip.sha256`、`MCP_CREO_MechDog-0.17.1-seed-library.zip`、`MCP_CREO_MechDog-0.17.1-seed-library.zip.sha256`。逐个列出文件名上传（禁止 `*.zip` 通配），并用 `python tools/check_release_assets.py --tag v0.17.1` 核对四附件齐全、两个 sidecar 与对应 ZIP 摘要一致。

种子包 SHA256：`83d4b6162894fe61015c74bba231cad73b36ccaa74e82cb7f35a9f31f82db74f`（24 文件、9 种子；内容除两份清单的 `compatible_server_version` 外未变）。源码包 SHA256 由最终提交源码生成，写入 Release body 与 `MCP_CREO_MechDog-0.17.1-source.zip.sha256`。

当前状态：**准备发布**（本文随 0.17.1 发布提交进入 `main`）；合并提交、标签、Release 链接与附件核对结果记录在发布交付说明。
