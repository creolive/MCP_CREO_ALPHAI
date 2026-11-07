# RELEASE-0.18.0 发布记录

## 1. 环境与身份

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07 |
| 版本 | 0.18.0（MINOR，本地功能分支集成批：FEAT-063/FEAT-035/FEAT-059/FEAT-057） |
| 源码提交 | `1cf9d3f`（集成完成、门禁时；前序合并 `81862f8`、`bfa57de`、`fd2b5de`） |
| 工作区 | dirty=true（仅发布文档与本机用户未提交的 DEV-054 记录/未跟踪文件；源码指纹为门禁实测） |
| 源码指纹 | `80f2bb8d0996f157cb4dec9fc5fc1191dbb87cd49db18b3f5577be62dab0eed5` |
| 系统 | Windows x64 |
| Creo | 12.4.0.0（仅用于匹配 SDK 编译，未建立 Toolkit 连接） |
| 公开工具数 | 102（新增 `creo_plan_product_variant`、`creo_get_mass_properties`） |

## 2. 代码与文档变更

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| 离线产品变体规划 | `src/creo_mechdog/product_rules.py`、`server.py`、`src/creo_mechdog/capabilities.py`、`examples/product_rules/box_frame.json`、`docs/PRODUCT_RULES.md` | 只读工具 `creo_plan_product_variant`；`product_rules` 能力族；固定模板 `box_frame`；不连接 Creo |
| 标准螺纹孔 | `src/creo_mechdog/hole_standards.py`、`src/creo_mechdog/schema.py`、`native/generic.cpp`、`src/creo_mechdog/operation_results.py`、`src/creo_mechdog/compact_sections.py` | `creo_hole.standard={series,size,thread_depth}`；冻结 ISO 粗牙表；原生螺纹元素树；回执 `thread_metadata`/`thread_metadata_verified`/`thread_readback` |
| 只读质量属性 | `src/creo_mechdog/mass_properties.py`、`native/mass_properties.h`、`native/generic.cpp`、`server.py`、`src/creo_mechdog/capabilities.py`、`tools/probe_mass_properties.py`、`tools/test_adoption_mass_properties.py` | `creo_get_mass_properties`；材料密度优先、显式 what-if 兜底、缺密度返回 null；数值守卫 |
| 事务日志底座 | `src/creo_mechdog/model_transaction.py`、`docs/development/ALPHAI-B01-SKELETON-CONTRACT.md` | 阶段与检查点契约、幂等；原生骨架未实现 |
| 台账与发布文档 | `docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、FEAT-035/057/059/063 工作卡、`README.md`、`version.py`、`seed_library/seed_manifest.json`、`docs/seed_package.json` | 状态回填、版本与工具数同步 |
| 回归 | `tests/unit/test_product_rules.py`、`tests/unit/test_standard_holes.py`、`tests/unit/test_mass_properties.py`、`tests/unit/test_model_transaction.py`、`tests/unit/test_t01_capability_contracts.py` 等 | 工具数断言更新为 102；新增功能回归 |

## 3. 验收证据

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 全量单测 | `python -m unittest discover -s tests` | 2826 项，0 失败、0 错误 |
| 全量门禁 | `python tools/dev_check.py` | `success=true`：unit_tests=passed，24 lint/12 未格式化（存量基线） |
| 原生组合编译 | `python bridge.py build` | 通过，产物 `build/creo_worker.exe` |
| 种子包 | `python tools/package_seeds.py` 两次 | 同摘要，回填 `docs/seed_package.json` |

## 4. 未验证范围

- Creo 实机：本版未连接 Creo/Toolkit；标准螺纹孔原生树、质量属性原生读取、保存重载均无实机证据。组合编译只证明可编译。
- WorkBuddy 公开 MCP 黑盒按用户决定由其它机器执行。
- Creo 9（本机无 SDK）、Creo 10 实机。
- FEAT-057 材料密度来源/单位/装配汇总契约；FEAT-059 原生骨架与多模型事务；FEAT-063 原生模板与保存重载。
- 真实远端附件下载由发布后 `tools/check_release_assets.py --tag v0.18.0` 核对。

## 5. 交付清单

- 标签 `v0.18.0`（指向合入 main 后的本次交付提交）
- 附件：`MCP_CREO_MechDog-0.18.0-source.zip` + `.sha256`、`MCP_CREO_MechDog-0.18.0-seed-library.zip` + `.sha256`
- 发布时 SHA256 写入 Release 说明与两个 `.sha256` 附件。
