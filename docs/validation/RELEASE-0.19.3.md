# RELEASE 0.19.3 记录

日期：2026-11-09。源码版本：0.19.3（[version.py](../../version.py)）。类型：PATCH。公开工具：107。

本文件是发布前写入源码包的记录；提交号、标签对象、Release 链接与附件摘要由同一交付在发布后回填。源码包内的摘要表保留占位，最终以 GitHub Release 正文与 [RELEASE-POSTCHECK-2026-11-07](../development/RELEASE-POSTCHECK-2026-11-07.md) 为准；仓库内本文件为发布后回填版，回填不改变已上传的四附件。

## 条目与范围

- [DEV-081](../work-items/DEV-081.md)：第四份 0.19.0「简易护卫舰」反馈 F01—F11 的 A 批离线六项（F02 精确圆弧闭合、F03 半径/尺寸 API 上限、F07 更新检查失败指引、F04 connect `-4` 显式 retry 回执、F11 三平面 offset/direction 文档契约、F05 compact 曲面放样限制说明），逐任务独立审查；另建 [B/C 批子计划](../superpowers/plans/2026-11-09-feedback0190-frigate-bc-batches.md)与 [WorkBuddy 黑盒提示词](feedback-0.19.0-frigate-2026-11-08/workbuddy-blackbox-prompt.md)。
- [DEV-080](../work-items/DEV-080.md)：首批离线收口——手写 TU 头门控契约测试、COMPATIBILITY 缺头 SDK 降级说明、台账计数自检进 CI，以及 BACKLOG/工作卡同步。
- [BUG-001/FEAT-018](../work-items/BUG-001-FEAT-018-RECOVERY.md)：2026-11-09 用户决定把本机实机放行改为「用户当次明确确认后即可用 Creo 实机测试」；纯规则/文档变更，不改父卡技术状态、不新增 ID、不改计数，历史原件逐字节保留。
- 不交付 B1—B6 原生实现、C0—C5 黑盒验收、A 批实机效果补证；按用户决定本次会话不执行 WorkBuddy 黑盒。
- 逐 ID 状态/目标版本核对：DEV-080、DEV-081 工作卡首页与 BACKLOG 表行均改为「已随 0.19.3 交付 + 具体余项」，目标版本 0.19.3；BUG-001 卡首页注明规则修订随 0.19.3 交付、技术状态不变；`version.py`、README 标题与当前正式版段、DEVELOPMENT 入口、RELEASING「当前版本为 0.19.3」行一致。

## 环境与门槛

- 本机 Windows x64 / Python 3.12.14；Creo 12.4.0.0 与匹配 Toolkit SDK 为本机既有环境，但本批**未启动 Creo 会话、未编译原生执行器**（未获当次实机确认）。
- 全量单元测试：`Ran 3150 tests in 409.732s ... OK`（工作树）。
- `tools/dev_check.py --work-item DEV-081 --unit-timeout-seconds 1800`：EXIT=0、`success=true`、`unit_tests=passed`、`native_validation=not_run`、源码指纹 `7ebb77e7a1e89f92871a03a175bd262cbd634904b65a11af4e647f7621699d56`（`source.dirty=true`）；发布前 `--skip-unit` 复核 EXIT=0、`unit_tests=not_run`；风格基线为存量 21 项 lint / 10 个未格式化文件。
- `tools/check_backlog_counts.py`：172（BUG 75 / FEAT 61 / DEV 36）三方一致；`git diff --check` 与 `git diff --cached --check` 通过；改动文档 `read_lints` 0；相对链接全部可达。
- 源码包解压后独立门禁：`Ran 3150 tests in 349.484s ... OK`，0 failures / 0 errors / 5 skipped，`tools/test_unit.py` exit 0，`source.git_status=unavailable`、`source_scope=distributed_source`、指纹 `4f36142e…`。前几次解压运行分别因 `PYTHONPATH` 未含解压目录根、venv 的 editable 安装把 `sys.executable -I` 子进程导向原工作树、以及解压路径 288 字符超过 Windows `MAX_PATH` 260 出现假失败；最终以短路径解压并对该目录做一次临时可编辑安装复跑全绿，测试结束后本机 editable 已恢复指向仓库根（`version.py=0.19.3`）。这些失败与源码包内容无关，未据此宣称通过，也不用工作树通过数代替源码包结论。
- 未执行：Creo 实机几何/保存重载/回滚、原生编译与原生集成测试、WorkBuddy 黑盒、Creo 9/10 复测、真实并发。

## 打包顺序

1. `tools/package_seeds.py --output MCP_CREO_MechDog-0.19.3-seed-library.zip` 以 `--allow-record-mismatch` 生成候选包，取实测 SHA256 `bc85958afbf8f3da0affde7144c13a145ebdd95eb04df529015595c59ab1e64a`，回填 `docs/seed_package.json` 的 `seed_archive_sha256` 与 `compatible_server_version=0.19.3`、`seed_archive_name`。
2. 删除候选包后重建种子包，摘要不变、校验通过并生成 `.zip.sha256` sidecar。
3. `tools/package.py --seed-archive <seed.zip> --output <source.zip>` 生成源码包与两个 sidecar，四附件门禁通过。
4. 以本次合入 `main` 后的实际提交建立 `v0.19.3` 标签，逐个上传四个附件（禁止通配），发布后运行 `tools/check_release_assets.py --tag v0.19.3` 核对。

## 附件（已回填）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.3-source.zip` | 9 333 252 | `aed3b422acd815dcf624423d1c9d43640c7fabb28c8a631c2eb2b0d0380df463` |
| `MCP_CREO_MechDog-0.19.3-source.zip.sha256` | 101 | `ddcc3a651173ef293974ffec35eabbb214559a3d7c4c19d56b032dad7f21470e` |
| `MCP_CREO_MechDog-0.19.3-seed-library.zip` | 493 442 | `bc85958afbf8f3da0affde7144c13a145ebdd95eb04df529015595c59ab1e64a` |
| `MCP_CREO_MechDog-0.19.3-seed-library.zip.sha256` | 107 | `8c1299fbb8066d3aefedeb6c3b98b4274a4d594a6a4d0266be4c90847b29f1d5` |

## 远端核对（已回填）

- `main` 提交 `096e86a2a6d9a73c4716ca2e6758e03e9fcfab31`，`origin/main` 同值（fast-forward `f1c0a94..096e86a`）；附注标签对象 `61d1d2b64fd2490853f2b5ec0bfb6ec74085e1d0`（`v0.19.3`，指向上述提交）。
- Release：[v0.19.3](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.3)，id `RE_kwDOU_ueTM4aLAs8`，`isDraft=false`、非 prerelease，`published_at=2026-11-09T12:15:07Z`。
- `tools/check_release_assets.py --tag v0.19.3` → exit 0，「v0.19.3: four assets downloaded and verified; both sidecars match」；[POSTCHECK v0.19.3 段](../development/RELEASE-POSTCHECK-2026-11-07.md) 记录四附件逐个上传与摘要一致性。
- 本回填提交不改变已发布的标签、Release 与附件；`v0.19.3` 仍指向 `096e86a`。
