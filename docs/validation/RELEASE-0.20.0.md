# RELEASE 0.20.0 记录

日期：2026-11-10。源码版本：0.20.0（[version.py](../../version.py)）。类型：MINOR。公开工具：107。

本文件随本版源码包发布；提交号、标签对象、Release 链接与附件摘要由同一交付在发布后回填。源码包内的摘要表保留占位，最终以 GitHub Release 正文与发布后回填版为准；回填不改变已上传的四附件。

## 条目与范围

- [DEV-081](../work-items/DEV-081.md)：B 批原生/实机四项与 C1 契约冻结。
  - B1/F01：提交放样前的 seed 兼容性预检与无 callback 路线说明（`tools/test_installation_loft.py` 实机正负例）。
  - B2/F11：零去料切除的结构化几何回执（原点、法向、方向符号、有效深度区间、`cut_geometry_context`）。
  - B3/F06：compact 阶段进度 `operation_index`/`operation_total` 与日志体积、`truncated` 标记。
  - B4/F08：选择性切除作用域公开参数 `scope`、`scope_applied` 特征树回读、`F08_SCOPE_RESOLVE_FAILED`/`F08_SCOPE_NON_TARGET_CHANGED` 回滚，以及 `known_limitations.cut_scope`、REFERENCE_SYNTAX、COMPATIBILITY 文档。
  - C1：F08/F09/F10 公开契约冻结（`f08_contract`、`f09_contract`、`f10_contract`），不含 F09/F10 实现。
- 不交付：B5/F09 着色预览与 B6/F10 锥台实现、C 批 WorkBuddy 黑盒、Creo 9/10 复测。
- 逐 ID 状态/目标版本核对：DEV-081 工作卡首页与 BACKLOG 表行均改为「B1/B2/B3/B4 已随 0.20.0 实机验收交付；B5/B6 与 C 批黑盒待做」，目标版本 0.20.0；`version.py`、README 标题与当前正式版段、DEVELOPMENT 入口、RELEASING「当前版本为 0.20.0」行一致。本版不涉及其它 BUG/FEAT 卡的状态变化。

## 环境与门槛

- 本机 Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可；`bridge.py status` → `connected=true`、`toolkit_code=0`。
- 实机执行经用户 2026-11-10 当次明确确认；未结束或重启 Creo/nmsd、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型与历史证据。
- 原生执行器：`bridge.py build` → `source_digest=5cbb3685…`、`worker_sha256=a7408483…`（B4 验收所用构建；本次版本与文档变更不触及 `native/*.cpp`）。
- 全量单元测试：`Ran 3263 tests in 372.635s ... OK`（工作树）。
- `tools/dev_check.py --work-item DEV-081 --unit-timeout-seconds 1800`：EXIT=0、`success=true`、`unit_tests=passed`、`native_validation=not_run`、受测源码指纹 `417a0477e95127c5567c65934f361110ce31f86dc9959cc5f20ec538b21488a5`（`source.dirty=true`）；风格基线为存量 21 项 lint / 9 个未格式化文件，无新增诊断。
- `tools/check_backlog_counts.py`：`consistent=true`（172 / BUG 75 / FEAT 61 / DEV 36）；`git diff --check` 通过。
- 实机证据详见 [0.20.0 版本说明](../RELEASE_NOTES_0.20.0.md) 与 [DEV-081](../work-items/DEV-081.md)「B 批实机验收」；工单原始报告在 `build/cut_scope_live.json`、`build/job_progress_live.json`、`build/cut_material_test.json`（`build/` 为忽略目录，不入源码包）。

## 打包顺序

1. `tools/package_seeds.py --output <seed.zip> --allow-record-mismatch` 生成候选种子包，实测 SHA256 `6cde6888e80cf9dd9df1d8d86dec33eb308c193d3c5ca8c1e17af98f41ca0697`，回填 `docs/seed_package.json` 的 `seed_archive_sha256`、`compatible_server_version=0.20.0`、`seed_archive_name`，并同步 `seed_library/seed_manifest.json`、`docs/seed_manifest.json` 的 `compatible_server_version`。
2. 删除候选包后重建种子包，摘要不变、校验通过并生成 `.zip.sha256` sidecar。
3. `tools/package.py --seed-archive <seed.zip> --output <source.zip>` 生成源码包与两个 sidecar。
4. 以本次合入 `main` 后的实际提交建立 `v0.20.0` 标签，逐个上传四个附件（禁止通配），发布后运行 `tools/check_release_assets.py --tag v0.20.0` 核对。

## 附件（发布后回填）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.20.0-source.zip` | 待回填 | 待回填 |
| `MCP_CREO_MechDog-0.20.0-source.zip.sha256` | 待回填 | 待回填 |
| `MCP_CREO_MechDog-0.20.0-seed-library.zip` | 待回填 | `6cde6888e80cf9dd9df1d8d86dec33eb308c193d3c5ca8c1e17af98f41ca0697` |
| `MCP_CREO_MechDog-0.20.0-seed-library.zip.sha256` | 待回填 | 待回填 |

## 远端核对（发布后回填）

- `main` 提交、`origin/main`、标签对象：待回填。
- Release 链接、id、draft/prerelease 状态、发布时间：待回填。
- `tools/check_release_assets.py --tag v0.20.0` 结论：待回填。
