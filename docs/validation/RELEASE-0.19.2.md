# RELEASE 0.19.2 记录

日期：2026-11-08。源码版本：0.19.2（[version.py](../../version.py)）。类型：PATCH。公开工具：107。

本文件是发布前写入源码包的记录；提交号、标签对象、Release 链接与附件摘要由同一交付在发布后回填。源码包内的摘要表可能保留占位，最终以 GitHub Release 正文与 [RELEASE-POSTCHECK-2026-11-07](../development/RELEASE-POSTCHECK-2026-11-07.md) 为准。

## 条目与范围

- [DEV-077](../work-items/DEV-077.md)：R01 草图 `closure_tolerance_mm`、`snap_endpoints` 与几何保真断言；R02 mirror 特征引用与回执；R03 session_health stale 身份降级；R04 quilt_merge 消耗片回执。均为离线交付。
- [DEV-079](../work-items/DEV-079.md)：归档 2026-11-08 下载目录 `0.19.0` 三份 Creo 10 反馈；曲率默认摘要与 `include_samples`、surface_group 结构化失败、quilt_merge 描述同步、`profile.method`、POSTCHECK 旧句。
- 已核对为 0.19.1 已修、不在本版重复：surface_group `state_reason`、`verify_stages` 计时回退、三处裸名导入、DEV-075 卡首页、四版本附件 digest 回填。
- 未交付的 H01—H09 见 [0.19.0 MAPPING](../validation/feedback-0.19.0-2026-11-08/MAPPING.md)。

## 环境与门槛

- 本机 Windows x64、Python 3.12、Creo 12.4.0.0 及匹配 Toolkit SDK。
- `bridge.py build`：原生执行器编译通过；本批未启动 Creo 会话。
- 全量单测：`Ran 3118 tests ... OK`（394.649 s，工作树）。
- `tools/dev_check.py --skip-unit --work-item DEV-079`：成功，仅存量风格基线。
- `git diff --check`：通过。`tools/check_backlog_counts.py`：170（BUG 75 / FEAT 61 / DEV 34）三方一致。
- 未执行：Creo 实机几何/保存重载/回滚、WorkBuddy 黑盒、源码包解压后全量单测、Creo 9/10 实机。

## 打包顺序

1. `tools/package_seeds.py --output <seed.zip>` 生成种子包，回填 `docs/seed_package.json` 的 `seed_archive_sha256` 与 `compatible_server_version=0.19.2`。
2. 重建种子包确认 SHA256 不变。
3. `tools/package.py --seed-archive <seed.zip> --output <source.zip>` 生成源码包与两个 sidecar。
4. 以本次 `main` 提交建立 `v0.19.2` 标签，上传四个附件并核对。

## 附件（发布后回填）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.2-source.zip` | 9,259,802 | `922fb7fdaf8d514f6cdc13b3b71984d1275213047f80afd5032aa495e447b7b5` |
| `MCP_CREO_MechDog-0.19.2-source.zip.sha256` | 101 | `ec17e070ef9cc696893855db77a5b551f568365496a46916291040ff66903279` |
| `MCP_CREO_MechDog-0.19.2-seed-library.zip` | 493,442 | `22a7a32d7636d6babf7b68b9526b6b935f4d97386ff06ba9c2487002f4e71558` |
| `MCP_CREO_MechDog-0.19.2-seed-library.zip.sha256` | 107 | `aeec87c4c01dbb91466253754cfa05c4210c13e1cd097d425c1fc9adb8bd434d` |

## 远端核对

- 提交：`df8e178553348fc1f438559a2d506ae6bfd5a9e0`（`main`，已推送 `origin/main`）
- 标签：`v0.19.2`，annotated tag `fd8159cd5644d5e57f14cd0b80b35e0d5b7a1be0`，指向上述提交
- Release：[v0.19.2](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.2)，id `438226979`，非 draft、非 prerelease；`published_at=2026-11-08T12:19:48Z`
- `tools/check_release_assets.py --tag v0.19.2`：exit 0，「four assets downloaded and verified; both sidecars match」
- 本文件在发布源码包内保留发布前占位；上表为发布后回填，发布后核对原文见 [RELEASE-POSTCHECK-2026-11-07](../development/RELEASE-POSTCHECK-2026-11-07.md#v01922026-11-08-本轮联网实测)。
