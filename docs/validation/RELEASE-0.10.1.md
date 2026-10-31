# 0.10.1 发布验证记录

日期：2026-11-01。版本入口 [version.py](../../version.py)（`VERSION = "0.10.1"`）、[版本说明](../RELEASE_NOTES_0.10.1.md)、[开发入口](../DEVELOPMENT.md) 与[主台账](../BACKLOG.md)（DEV-053 行）随版一致。本版为 **PATCH**：DEV-053 的 P00–P06、P09 第一阶段、P10/P12 缺件登记与 P14 离线+实机集成；P07/P08/P11 的 MINOR 公开结构（草图原点诊断字段、钣金候选边结构与 `wall_contract` 回显、空件预览 `skipped_no_geometry`）保留在开发分支 `codex/dev053-post0100`，随 0.11.0 候选另行交付，未塞入 PATCH。公开工具仍 94 个。

## 交付提交与标签

- 主干提交：`92ab00a8b7f876e2491ca90635b4409c63f9e84f`（`main`，快进合入自发布分支 `codex/dev053-rel0101`；远端已核对一致）。
- 附注标签：`v0.10.1`（标签对象 `0f2349afe6fedaaf37ab3d43de8663d49ad7cea8`，剥离后指向 `92ab00a`；远端已核对）。
- 合入链：`08064b0`(P00)→`1468ddf`(P01)→`c68d435`(P03)→`f722055`(P10/P12)→`4b96095`(P02)→`98bf5d1`(P05)→`acefe53`(P06)→`256549b`(P04)→`189b933`(P09 一阶段)→`ccc86da`(0.8.5 回填)→`ba2d11e`(格式收口)→`a498a04`(实机收口)→`92ab00a`(版本裁定)；cherry-pick 自开发分支 `codex/dev053-post0100`（离线批 HEAD `bbb1c2d`，其 P11=`53ed968`、P07=`50b34a1`、P08=`28b1447` 与 P14 文档不随本版）。
- 统一检查：`tools/dev_check.py --work-item DEV-053` 在 `92ab00a` 上 success=true（单元 1782/1782、0 失败 0 错误、无新增语言/格式回归；受检源码指纹 `fd3c585a…99c5c9`。此前两次失败为本机 loader DLL 重建竞态的偶发，第三次及独立复跑均确定性通过）。

## 本机实机验收（run `post0100_20261031T234309_rel0101`）

环境：Windows x64、Creo Parametric 12.4.0.0（PID 27320，GUI 经截屏核实功能区/欢迎页/无模态框可操作）、匹配 Toolkit SDK 与许可、MSVC；实机准入清单（唯一 E 盘 dev 客户端、无并行 worker、`toolkit.lock` 未持有、无 unknown 保护现场）逐项核对通过。构建身份：源码指纹 `0ba07f37…49e112`、worker SHA256 `eca0c8e2…4eb5cd0`（`build/post0100_20261031T234309_rel0101/build/identity.json`，本机生成物）。

| 项 | 命令 | 结果 |
| --- | --- | --- |
| P03 五反例+恢复 | `tools/test_arc_direction_live.py --live --confirm-session-usable`（p03/report.json） | 4 例 schema 拒绝无作业；原生开放轮廓例失败回滚、同源体积 1428.0972451017303 mm³ 逐位不变、revision 3→3、model_id 一致；恢复编辑 rev 3→4 误差 3.2e-10 mm³；5 创建例保存重载 true |
| P02 退出核对 | 同上驱动退出后进程核查（p02/exit_check.json） | python/server.py 进程零残留；后续各驱动同核 |
| P06 基准面 | `tools/test_datum_plane_contract.py --live --confirm-session-usable`（p06/report_r2.json） | native_acceptance=passed：±54° 法向 0.5878/±0.8090 对 Rodrigues oracle、零角、offset-only、旋转后偏移、独立工具/plan 双入口；三拒绝例（angle+非零 offset、缺 kind、非法 angle 轴）。首跑 report.json 保留为驱动 feature→geometry 映射缺陷现场（生产零改动） |
| 定向回归 | `test_detail_feature_observation.py` / `test_t09_assembly_replay.py` / `test_t12_examples.py`（regression/*.json） | 圆角/倒角/拔模九例含批中途失败真实回滚；装配回放 passed；T12 官方示例 passed |

## 附件与远端核验

正式 Release（`draft=false`、`prerelease=false`）：https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.10.1 （Release id 430067976；正文直接列两 ZIP 文件名与完整 SHA256）。四附件均从远端逐件下载核对：

| 附件 | 远端字节数 | 下载后 SHA256 | 核验 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.10.1-source.zip` | 6 651 950 | `eb0caf3d4dcb76d05d0ba7a77e93d5fd978893fbae637dc81148397cd37dc55f` | 通过（本地确定性双建同哈希） |
| `MCP_CREO_MechDog-0.10.1-source.zip.sha256` | 101 | `a972698ddfa42e551169bcca639a932f65dfbd5735575bf110291c79ff627c86` | 通过（内容与源码包哈希一致） |
| `MCP_CREO_MechDog-0.10.1-seed-library.zip` | 493 440 | `c35e7602fb85124ab9627e92e5ba2dfa47575bcb407b07f73b9e9a87efc4c6b8` | 通过（确定性构建两次同哈希，24 文件 9 种子） |
| `MCP_CREO_MechDog-0.10.1-seed-library.zip.sha256` | 107 | `eba0075ebb91613236bba6468a891525bbde51a35fbac5409defe321368758f1` | 通过（内容与种子包哈希一致） |

正式附件真实安装核对（发布时待补项就此关闭）：

- 0.10.1 对：解包远端源码 ZIP 后以其自身 `seeds.py install_seed_library(archive_file=远端种子 ZIP)` 真实安装——`installed=true`、9 种子注册到默认路径；篡改单字节的负例在写入目标前被拒（`Seed archive SHA256 differs from the trusted seed package record`），目标目录未创建。
- 0.10.0 对（历史待补）：远端源码 ZIP 内 `seeds.py` 记录的受信摘要 `99e3b9ec…819c3` 与远端 0.10.0 种子附件实际哈希一致，对自洽；version.py/双清单/README 均为 0.10.0。

## 未测范围（保持开放）

BUG-091 根因未定（四现场关键缺证仍在，通道死亡不再复现不等于修复）；四壁/corner/trim/材料端 relief 去料不支持或未证明（P09 A/B 层矩阵待实机）；`gear10`/`gear10_snapped` 原案未验证（原件缺件）；Creo 9/10 实机编译与运行时未验（无本机 SDK、外部证据缺件）；P07/P08/P11 的实机验证随 0.11.0 候选；WorkBuddy 黑盒与真实并发未执行；正式 0.10.0 附件仅核对自洽，未以 0.10.0 源码全流程重装。历史 0.10.0 及更早标签与附件保持原样。
