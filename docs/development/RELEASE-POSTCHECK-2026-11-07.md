# 发布后附件核对记录（2026-11-07）

本文件补记 [DEV-075](DEV-075.md) 指出的缺口：`RELEASING.md` 第 7 步要求「发布后用 `gh release view` 或 `tools/check_release_assets.py --tag <tag>` 核对远端恰有四个附件、两个 sidecar 与对应远端 ZIP 摘要一致，核对结果写入发布记录」，但此前只在各版 `RELEASE-*.md` 里记结论，没有可复核的发布后留存。本文件只记录**发布之后**对远端实际对象的重新下载与重算结果；发布前的本地打包、CI 与验收结论仍以各版版本说明和发布记录为准。

## 方法与范围

- 工具：`tools/check_release_assets.py --tag <tag> --version <version>`（gh 取 API 元数据 → 精确 tag 附件 → 下载四文件 → 重算 SHA256 → 比对 sidecar 内容）。
- 时间：2026-11-07T16:58:23Z 起（本机 +08:00），逐版连续执行，exit code 均为 0。
- 环境：Windows x64；Python 3.12 虚拟环境（`.venv`）；`gh` 已登录；源码目录 `C:\i0182`（`origin/main` 的独立工作树，0.18.2 开发分支），核对对象是已发布远端 Release，不受工作区改动影响。
- 命令输出原文见本轮 `build/postcheck/postcheck.log`；下表 digest 由 GitHub Release API 的 `assets[].digest` 读出，与本地重算结果一致。

## v0.17.4

- 标签对象：`v0.17.4` → 提交 `b57dbdac7747c670433b964a5294f8373b6c757b`；发布 2026-11-07T05:24:16Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.17.4-source.zip` | `8f8f649c2d7c8420145d23a79f1f0749a525bae4f5f348a97401b71fea4fbc09` | 8 382 351 |
| `MCP_CREO_MechDog-0.17.4-source.zip.sha256` | `34e00b85164135df86fdab798dfa39b413e33a45581618c829f75ca2d9652bd8` | 101 |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip` | `a6c633b49cb243ca1f58e6f3b8756f30a9e0b32eefebcc0e185bec1bd79a3583` | 493 442 |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip.sha256` | `f53acf87a22b9641d9ae2d8b732993451b3ecc05d0ef760150b0c3b23e3e64b2` | 107 |

## v0.18.0

- 标签对象：`v0.18.0` → 提交 `58dd76b2d47e180e7e54d701cfaa4449aae49654`；发布 2026-11-07T07:04:07Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.0-source.zip` | `dab4ca04ee58ae643e4e492ef3870d04d8724921c57be8e554c96136ee874849` | 8 485 592 |
| `MCP_CREO_MechDog-0.18.0-source.zip.sha256` | `3c4bd463dadc967eba2d3fd52f66b8c2998bb4d0186834ff811fef731fed9dfa` | 101 |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip` | `b6acab41fd727bb555ec6bb825116df2eab1e81e214db1c7c804e4f5e709a05b` | 493 442 |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip.sha256` | `02c3823da9f59a745b3a3685c82d7342abf24d95b4260ffa06d046aa6069b51b` | 107 |

## v0.18.1

- 标签对象：`v0.18.1` → 提交 `9d725691c556c8063316a2cdf4d506c818a7baf7`；发布 2026-11-07T08:53:07Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.1-source.zip` | `658950c837895f96e4ec254610d18b8fe5012ae585d5a567cc5c2409940d08a7` | 8 444 988 |
| `MCP_CREO_MechDog-0.18.1-source.zip.sha256` | `ea9b403e87d9139fe299b7f5f61770dbac6ecb5eb46093508496bdddb3daf901` | 101 |
| `MCP_CREO_MechDog-0.18.1-seed-library.zip` | `8e5f512571de9ff494db3a0964f7ff00d0c49a4c5f9767f93e08f385436a640e` | 493 442 |
| `MCP_CREO_MechDog-0.18.1-seed-library.zip.sha256` | `c2b3df7825c85203990722b51ab5e80fae589f444845f292b503e8c62bc1f937` | 107 |

## v0.18.2

见 [0.18.2 发布记录](../validation/RELEASE-0.18.2.md)：该版本发布后在同一台账补充本节，记录标签提交、四个附件 digest 与 `--tag v0.18.2` 的退出码。

## 未覆盖

- 本核对只证明**远端附件与 sidecar、摘要三者一致**，不重新验证包内功能、Creo 实机或安装结果；这些结论分别属于各版 `docs/validation/RELEASE-*.md` 的实际范围。
- 只核对 GitHub Release 平台对象；镜像、本地下载缓存和客户端侧校验不在本文件范围。
- 本文件为首次补记，未回改 v0.17.4/v0.18.0/v0.18.1 已发布附件或原发布记录中的日期与结论。
