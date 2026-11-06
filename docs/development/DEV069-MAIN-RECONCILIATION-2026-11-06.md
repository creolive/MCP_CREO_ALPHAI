# DEV-069：按最新 main / 0.16.0 对账

日期：2026-11-06；目的：响应用户“获取当前main和项目最新内容，与修复计划比较并重新完善”。本次只读取远端Git/Release、当前源码及已有报告，修改规划资料；没有运行产品测试、连接Creo或发布。

## 取得的当前身份

| 项目 | 本次结果 |
| --- | --- |
| 获取远端 | `git fetch origin main --tags` 成功 |
| HEAD / main / origin/main | 均为 `4517e3650fdfbe89a97f4d8d5b905c5da248ac05`，左右差异0/0 |
| 版本 / 标签 | `version.py=0.16.0`；`v0.16.0^{commit}`同一提交 |
| 当前工作区 | main；起始修改仅文档/未跟踪资料，产品源码与origin/main一致 |
| Release实时查询 | `gh release view v0.16.0 --json ...`；非草稿/非预发布，2026-11-06 17:09:11北京时间已发布 |
| Release附件元数据 | 两ZIP及两个sidecar均uploaded；源码ZIP 8,106,399 B，API digest `2599964ac3c0713e7f1fc43fd61a4676500a2bbd55e2a71283e4b4909700b9e5`；种子ZIP 493,442 B，API digest `472ea06440d35ff9e6c77f3e3ce9cba8263c255ffbe25563593e26d59e364c53` |
| 本次附件内容校验 | 未下载ZIP/sidecar重算，不能把API digest当本次本地SHA256实算 |

[远端发布页](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.16.0)。仓库RELEASE-0.16.0仍有“准备发布”是发布前成文时点；此次API查询已确认发布存在，不为了回填历史说明再提交/重发旧版。

## 与旧计划逐项比较

| 计划项 | 主干证据 | 当前剩余处置 |
| --- | --- | --- |
| R00 | 四件归档/MAPPING/卡已跟踪；`7c0f6bd`补0.12.0归档 | 不重复归档；原件字节不改 |
| R01 | `942e3f2`、`native/surfaces.cpp`显式Init code+handle、`quilt_gauge_guard.h`、/we4552；`source_area_status`已接线 | Init缺陷退出开发；`volume_after/source_area`仍在，无已有实体/曲面通用计量保护 |
| R02 | native保存/回滚有界差异及operation_results投影、`test_surface_save_recovery.py`单元模块 | 诊断已实现；tools/下无专项复现驱动，未找到当前基线对照实机报告；不把“未复现”理解为专项已跑通过 |
| R03 | `d854fdf`；`PlanarWallBodies.gauge_source/gauge_reason`、双validation、`GaugeReceiptTest` | `#else`缺API仍设missing_api/null；**没有原生几何兜底**。卡/版本说明中的“回执离线”不能写成“兜底已实现待验” |
| R04 | `22a1c26`/`d854fdf`；job_projection/compact_sections、曲面criteria、full_detail_hint、LIST_ITEM_BUDGET=620 | 真实stdio字节/sections/full分页补证，不重建投影 |
| R05 | `bfdc8a3`；AssemblyPose description、assembly_pose_receipt/rotation_convention、failed_operation | 任意角实读、原载荷与失败回滚补证 |
| R06 | `2547c4e`；CreoStartup retry身份/预算/阻塞原因，health事实分层 | 真实失联现场未验；session_status仍经受限live探测，默认离线上下文属于D01后续设计 |
| R07 | surface_chain/reference族与FEAT-039首页已有0.13/0.14/0.15交付口径 | 本次补0.16状态对账；保留历史说明，不重复引用体系 |
| R08 | release_integrity包内统一校验，package硬失败、sidecar ASCII/LF、gh→--dir指引；0.15/0.16有发布 | 退出剩余开发；未来用现有闸门 |
| R09 | `e3f7b66`→0.16.0；BLIND miter树、显式放行与创建后回显核对，163234四墙实机成功 | 不能仍称四壁blocked；补native_planar路径、真实切角/间隙定标、展开折回和编辑回滚 |
| R10 | 首壁无公开origin；坐标尺寸有fabs；但sketch_frame显式plane可带origin，resize存frame | fabs只是风险，撤销“必先全局重构”的阻塞结论；先验证frame平移。计划内原生几何选边仍未实现 |
| R11 | quilt_merge继续gated，blend无新成立路线，现有offset产物是壁 | 保持blocked，等待新依据，不重复失败树 |
| R12 | `bfdc8a3`长轮询、`4201f84`connect计时；FEAT-007已有卡/9项离线测试 | 只补协议/原生证据；bbox/erase观察/rename/delete独立待办 |
| R99 | 0.15.0、0.15.1、0.16.0主干提交与标签，0.16远端Release元数据已确认 | 过去批次退出“未发布”；未来每批仍按全局规则发布 |

## 已有报告的本次只读核验

- `build/unit_test_report.json`：0.16.0，2646项，success=true，0 failures/0 errors；本次未重跑。SHA256 `926c8433af4b82cd6e0dc3fcf6ba4c6ccbd87887de8afa58f6b944b55fc111cb`。
- `build/development_check.json`：0.16.0，success=true；只读历史报告，不代表本轮新验证。SHA256 `bfd82a90f84c9c141f2b9b7e2d33b0f7017d2908508653b02f37b555ff87e013`。
- 四壁主证据：`build/post090_n05/20261106T163234_c086ae9d/report.json`，SHA256 `a83f6eead04a6e7b5a5bb0e3c741e7cd95fde121bb282c29dfc8fbe8a24a6758`。顶层passed与four_walls_complete均true；模型 `916f7818b8364d3d93933634dd30ca66`；四墙job为 `8417a79aae5746d787769b2e2a5d92f0`、`d5eb4a2283db406cb814df27622e82f5`、`7a41ee4f3b4941108a58395cb380fc7c`、`2db8d8504c2c4f899346d668bc15712b`；revision2/3/4/5、保存重载全true，终体积106499.15656044203 mm³。
- 该驱动base是 `wall_sketch()+wall_base_op()`（conversion `sheetmetal_wall`），不是原反馈D的 `native_planar+sheetmetal_planar_wall+resize`，不能外推原反馈全链已通过。
- `161949_61da6c2a`报告顶层 `capability_claim.four_walls_complete=false`，但miter_box组true，与163234不能当作“两次整体同结果”。原报告不改，后续修正驱动汇总并重验。
- 163234报告缺commit/dirty/source_fingerprint/worker SHA256字段；当前源码/发布卡可解释路线，但不能反向补写这些字段冒充当时记录。新报告必须补身份。
- 未跟踪 `2026-11-06-feat-014-miter-cuts-route.md` 是过时调研草案，含GAP、0.15.0版本回退建议；BLIND才是主干当前实现。文件保留，不按其命令执行或覆盖现场。

## 其他工作树与范围去重

`git worktree list --porcelain`与本地分支核对：A02 `90d2c3e`尺寸守卫已通过 `051a65a`进入0.16.0；只保留rebase后实机缺口，不再派“集成A02”。A01 `c2520fd`、A03 `9520903`、B01 `77bbb4e`与FEAT-063离线规则 `6c12898`分别是其他分支，未据此称主干交付；这些工作树本次status均无输出。完整独立分支集成不自动纳入DEV-069本次修复范围。

## 本次文档变更边界

更新同一修复计划、设计、DEV-069、映射当前提示与台账当前入口；修正相关卡中0.16四壁/A02状态交叉指引。无新增ID、无产品代码、无SDK构建/单元或实机执行。初始旧曲面计划、RELEASE-0.13.0、DEV-054和未跟踪miter草案保留SHA256；原件与manifest不改。后续直接按更新计划R01/R03/R02优先安排，不重复已交付代码。

文档检查结果：16个相对链接均存在；四份原件/归档字节、大小与SHA256一致；台账182行/182个唯一ID、分类合计182。`git diff --check`退出0（仅既有换行提示）；原有四份修改/未跟踪文档的SHA256保持，产品Python/C++/版本/工作流没有本轮差异。收尾`git ls-remote origin refs/heads/main`仍为4517e36；以上不是产品或原生测试。

## 续：合并0.14.0两件反馈（后续用户请求）

上述182行/无新增ID等是前一主干对账阶段的记录；随后用户要求合并Downloads/0.14.0，本阶段新增两件原始归档，总计六件，[新增映射](../validation/feedback-0.14.0-2026-11-06/MAPPING.md)与原计划共用R编号。新增BUG-114为第183个唯一任务；矩阵准入沿用FEAT-012/BUG-045，无第二个矩阵ID。

- A运行报告18,068 B，SHA256 `1a3f9acea007823c21465e03945a02662dd1e6069f2835f686c0bc5b134f23e3`；B离线报告16,491 B，SHA256 `8ee30a1b2547c4ac7612c278cb7844e194e1d6bacbea362f55dc5a04e4211bdf`。字节复制、受测版本0.14.0与复核源码0.16.0分列，manifest不套用旧包身份。
- 精确I032矩阵纯数学复算的最大正交残差/det误差为2.2408500011117383e-7，det=1.0000002240850001，行范数1.0000001120424937；Python/native 1e-6仍放行。外部-2与30°高精度成功是关联，非内核阈值或唯一根因证明。R05改为P1准入兼容设计+两层边界验收，不自动正交化。
- 独立只读审阅确认component_changes/finalize缺少可信cleanup上下文；BUG-114/R13只在完整failed终态、job自建未保存所有权与双查询无副作用范围内判断model no_effect。checkpoint未回滚的bool/status与session擦除成功并不矛盾，不删除兼容字段或全局unknown，不自动重试/清保护。
- 0.14.0 A补充through_all命中/null/去料100与jpeg只读/人工目视正证据，限外部对应样例；B保持离线未验证。其余C4552/闸门/LF/schema重复问题按0.15.0已实现去重，0.12.1原件仍缺。
- 提交仍回传normalized operations而requested depth可为null，R04补来源元数据与省略/显式默认/through_all四例，不替换worker执行输入或假称full页是原始请求。
- 本阶段仍只做文档、归档、数学复算与静态审阅，未运行产品测试、构建、Creo或WorkBuddy；当前main远端查询仍为4517e36。现有四份其他任务文档继续保留SHA256。

本阶段检查：六件原件/归档逐字节、大小及SHA256一致；新增/更新入口20个相对链接均存在；台账183行/183唯一ID、分类表合计183（BUG-112交付状态纠偏，新增BUG-114；其余沿原统计口径）。独立审阅要求R13显式传operations/effect_scope，已补模型与外部输出分域及“先export再失败清理”回归。git diff --check退出0，产品源码/版本/工作流无差异，原有四份其他任务文档SHA256保持。
