# RELEASE-0.18.2 发布记录

## 1. 环境与身份

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07 |
| 版本 | 0.18.2（PATCH：DEV-075 0.18.0 升级复核反馈；DEV-066 t07 子项） |
| 源码提交 | 门禁提交 `9e57b05`（`dirty=false`，源码指纹 `e3afe4a9…`）；发布提交为本次合入 `main` 的合并提交 |
| 工作区 | 短路径独立工作树 `C:\i0182`，基于 `origin/main`（`9d72569`） |
| 系统 | Windows x64 |
| Python | 3.12.14（`.venv`） |
| Creo | 未启动、未连接（本批无原生代码改动） |
| 公开工具数 | 102（无新增/删除） |

## 2. 代码与文档变更

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| 来源记录降级 | `src/creo_mechdog/git_evidence.py`（新增）、`tools/test_t07_preview.py`、`tools/test_arc_direction.py`、`tools/test_dev049_profile_replay.py`、`tools/test_dev049_tilted_cut.py`、`tools/test_plan_performance.py`、`tools/test_installation_loft.py`、`tools/test_t05_native.py`、`tools/test_tilted_sketch_lifecycle.py` | 无 git 时目录遍历 + `provenance_mode`/`git_unavailable`；git 可用时行为不变并追加两个标记键；t05 只记录本分发实际存在的文件 |
| 附件回退 | `src/creo_mechdog/release_download.py` | `browser_download_url` 不安全或 `github.com` 失败时转 `api.github.com/repos/<repo>/releases/assets/<id>`（`Accept: application/octet-stream`），仍只认四个安全文件名并校验 sidecar |
| 回归 | `tests/unit/test_t07_preview.py`、`tests/unit/test_release_download.py` | 新增无 git 降级、git 检出保留、asset API 两个成功路径与双通道失败用例 |
| 发布规范 | `docs/development/RELEASING.md` | 第 5 步新增源码包解压全量门禁；第 8 步纳入「当前版本为 X」行；DEV-072 逐 ID 表按本版填写；0.17.4 段的 2744 标注为合并前快照 |
| 发布后记录 | `docs/development/RELEASE-POSTCHECK-2026-11-07.md`（新增） | v0.17.4/v0.18.0/v0.18.1 的 `--tag` 实际重下与重算结果 |
| 台账与卡 | `docs/BACKLOG.md`、`docs/work-items/DEV-075.md`（新增）、`DEV-066.md`、`FEAT-059.md` | 登记、状态与未排期范围；FEAT-059 改为「已交付 0.18.0 子项」 |
| 文档修正 | `docs/validation/RELEASE-0.18.0.md` | `test_hole_standards.py` → `test_standard_holes.py` |
| 版本与发布 | `version.py`、`README.md`、`docs/DEVELOPMENT.md`、`docs/seed_manifest.json`、`seed_library/seed_manifest.json`、`docs/seed_package.json`、`docs/RELEASE_NOTES_0.18.2.md` | 版本号、当前版本段、种子兼容版本与摘要同步 |

## 3. 验收证据

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 工作树全量单测 | `python -m unittest discover -s tests` | 2835 项，0 失败、0 错误 |
| 全量门禁 | `python tools/dev_check.py` | 门禁提交 `9e57b05`、`dirty=false`、源码指纹 `e3afe4a9…`；`success=true`：unit_tests=passed，version=0.18.2，24 lint / 12 未格式化（存量基线） |
| 源码包解压全量单测（新门禁） | 解压 `MCP_CREO_MechDog-0.18.2-source.zip` 到无 `.git/` 目录后 `python -m unittest discover -s tests` | 2835 项，0 失败、0 错误，exit 0 |
| 种子包 | `python tools/package_seeds.py` 两次 | 24 个文件、9 个种子，同摘要 `676536ca…`，已回填 `docs/seed_package.json` |
| 附件闸门 | `python tools/package.py --seed-archive … --stage …` | exit 0：源码包与 sidecar 生成，种子摘要、版本与两份清单一致 |
| 原生编译 | — | 本批无原生改动，未重编译，未连接 Creo |

## 4. 未验证范围

- Creo 9/10/12 实机建模、保存重载与 Toolkit 连接：本批未连接 Creo，未启停 Creo，未改动注册表或 unknown 保护。
- `DEV-066` 剩余范围：其余 `tools/` 离线驱动未逐项改造，只覆盖单元测试实际调用的 7 个驱动；无 git 环境下的负例输出整理仍未做。
- `release_download` 的 asset API 通道仅由单测覆盖；真实远端直连失败场景无法在离线门禁复现，发布后核对走正常 `github.com` 通道。
- WorkBuddy 公开 MCP 黑盒、Creo 9（本机无 SDK）与 Creo 10 实机。

## 5. 交付清单

- 标签 `v0.18.2`（指向本次合入 `main` 的合并提交）
- 附件：`MCP_CREO_MechDog-0.18.2-source.zip` + `.sha256`、`MCP_CREO_MechDog-0.18.2-seed-library.zip` + `.sha256`
- 发布后核对：`tools/check_release_assets.py --tag v0.18.2`，结果补记到 `docs/development/RELEASE-POSTCHECK-2026-11-07.md`
