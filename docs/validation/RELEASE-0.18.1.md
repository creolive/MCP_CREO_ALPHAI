# RELEASE-0.18.1 发布记录

## 1. 环境与身份

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07 |
| 版本 | 0.18.1（PATCH：FEAT-057 质量属性密度/单位/缺失原因契约；DEV-073 台账复核与文档精简） |
| 源码提交 | 门禁提交 `282a69a`；发布提交为本次合入 `main` 的合并提交 |
| 工作区 | 门禁时 dirty=false（短路径独立工作树 `C:\i0181`） |
| 源码指纹 | `f3d5eef8e4404961ca30ffb2ad47728c46048fd74c695227e26338ced128fab7` |
| 系统 | Windows x64 |
| Creo | 12.4.0.0（仅用于匹配 SDK 编译，未建立 Toolkit 连接） |
| 公开工具数 | 102（无新增/删除） |

## 2. 代码与文档变更

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| 质量属性契约 | `native/generic.cpp`、`src/creo_mechdog/mass_properties.py`、`server.py`、`tests/unit/test_mass_properties.py` | 新增 `mass_unavailable_reason` 与对应提示；原因枚举校验、矛盾组合拒绝、旧回执缺字段保留 `null`；单位口径写入工具说明 |
| 台账复核 | `docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、`docs/development/PENDING-2026-11-07.md`、`docs/work-items/DEV-073.md` 及其余被复核工作卡 | 88 项 BUG 重新分类；入口文档收敛，历史归档保留 |
| 版本与发布 | `version.py`、`README.md`、`docs/development/RELEASING.md`、`docs/seed_manifest.json`、`seed_library/seed_manifest.json`、`docs/seed_package.json`、`docs/work-items/FEAT-057.md` | 版本号、当前版本段、种子兼容版本与摘要同步；FEAT-057 状态回填 |
| 回归 | `tests/unit/test_mass_properties.py` 等既有用例 | 本版无测试删除；全量 2830 项通过 |

## 3. 验收证据

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 全量单测 | `python -m unittest discover -s tests` | 2830 项，0 失败、0 错误、2 跳过 |
| 全量门禁 | `python tools/dev_check.py` | `success=true`：unit_tests=passed，24 lint / 12 未格式化（存量基线），dirty=false |
| 原生组合编译 | `python bridge.py build` | 通过，产物 `build/creo_worker.exe` |
| 种子包 | `python tools/package_seeds.py` 两次 | 24 个文件、9 个种子，同摘要 `8e5f5125…`，回填 `docs/seed_package.json` |

## 4. 未验证范围

- Creo 实机：本版未连接 Creo/Toolkit；原生原因分支、真实材料密度、英寸/磅单位模型、保存重载均无实机证据。
- FEAT-057 主惯量、装配 occurrence 汇总与 `complete` 契约。
- WorkBuddy 公开 MCP 黑盒按用户决定由其它机器执行；Creo 9（本机无 SDK）、Creo 10 实机。
- DEV-073 的链接与 ID 核验在合入前分支执行，合入 main 后未重跑全量链接检查。
- 真实远端附件下载由发布后 `tools/check_release_assets.py --tag v0.18.1` 核对。

## 5. 交付清单

- 标签 `v0.18.1`（指向本次合入 `main` 的合并提交）
- 附件：`MCP_CREO_MechDog-0.18.1-source.zip` + `.sha256`、`MCP_CREO_MechDog-0.18.1-seed-library.zip` + `.sha256`
- 发布时 SHA256 写入 Release 说明与两个 `.sha256` 附件。
