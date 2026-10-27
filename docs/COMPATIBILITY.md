# Creo 兼容与验收矩阵

## 当前验收规则（2026-10-15）

按用户要求取消全项目 Creo 10 独立复测、双版本验收及正式基线门槛。当前开发、合入和发布按本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK 的实际改动范围验收；朋友反馈具体问题后再登记或沿用 ID 跟进。历史测试环境和未测事实保留，旧复测安排不再作为当前任务的前置条件，也不表示 Creo 10 新增了通过证据。条目见 [DEV-018](work-items/DEV-018.md)。

## 0.7.0 验收范围（2026-10-27）

DEV-047（0.5.2 三份反馈完整交付）在 Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC 下完成离线全量（966 项单元测试、dev_check、SDK 构建）与本机实机矩阵：T05 毫米几何矩阵 18/18 与非毫米（inch）只读覆盖（单位/换算/原始英寸重心与轴坐标、volume_mm3 按 BUG-072 契约为 null）、T06 多环、T07 预览（含留存图目视复核）、T08 特征生命周期、T09 约束回放、T12 官方示例全部通过；装配单位专项离线+实机复跑通过；实机另修复四处集成缺陷与收养拒绝单位元数据缺陷。BUG-078 三现场只读落定（仅 restore_baseline 可用，未 apply）；T11 真实世代只读盘点。WorkBuddy 按用户 2026-10-26 决定未执行；Creo 9 无本机 SDK，实机编译与运行时未验收；Creo 10 独立复测非门槛。详细证据及发布检查见 [RELEASE-0.7.0](validation/RELEASE-0.7.0.md)。

## 0.6.1 验收范围（2026-10-26）

BUG-082 修复批在 Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 SDK 下编辑专项 16/16 通过，含成功保存重载及独立非法几何失败回滚。主平面受支持实体的 auto/autodim 编辑使用坐标尺寸并报告 requested/used。种子矩阵仅部分完成，随后 Toolkit 通道断开；剩余场景、WorkBuddy 与其他 Creo 版本未验收。Creo 9 无本机 SDK，实机编译与运行时未验收；Creo 10 独立复测非门槛。详细证据及发布检查见 [RELEASE-0.6.1](validation/RELEASE-0.6.1.md)。

## 已有证据与历史范围

2026-10-15 BUG-022追加验证：Creo12.4及匹配SDK下复现边参考孔定位侧不稳定、板外孔无去料却成功；显式选择点及无去料保护的修复，按[独立记录](validation/BUG-022.md)完成开发验证，用户随后确认[WorkBuddy四场景](validation/BUG-022-WorkBuddy-retest-20261015.md)全部通过。本环境边参考修复验收完成；原Creo10来源及公开接口未提供的构建/失败文件哈希仍保留验证边界，不据此改变公开0.3.0附件或其他环境的支持范围。

历史记录日期：2026-10-14，服务源码版本 0.3.0。可使用 Creo 9、10 或 Creo 12；Creo 12 已验证可用，已记录的实机版本为 12.4.0.0，具体功能按下表的已测范围声明。Creo 9 与匹配 Toolkit 9 按 2026-10-16 决定纳入支持/要求范围，[BUG-033](work-items/BUG-033.md) 编译探测修复现已实现；本机无 Creo 9 SDK，实机编译和建模运行时均未验收。

本次按用户确认补充 Creo 12 可用性说明，文档条目见 [DEV-012](work-items/DEV-012.md)。这次文档修订未执行新的实机测试；以下历史测试与 0.2.6 发布复测各自保留原日期和结果。

后续BUG-007开发验证单列：Creo12.4 / release=44下复现600秒DLL确认等待；65ccf3e移除建模中的DLL加载。常驻初始化后两/三截面straight/smooth、三轮串行、已有底座追加、标签/ID引用、计划入口、原特征/revision/失败回滚和保存重载通过；未初始化及非XY拒绝、后续小件、两/三截面straight种子编辑回归通过。WorkBuddy最终本环境标签放样核心已通过，整数公开引用失败独立为BUG-028；Creo10、外部模态及NEVER/ALWAYS实际场景未测。详细源码身份和实测范围见 [本项记录](validation/BUG-007.md)，不外推到历史发布或所有参数分支。

| 环境 | 支持定位 | 证据与范围 | 本轮状态 |
| --- | --- | --- | --- |
| Windows x64 / Creo 10.0.0.0 / Python 3.12 / VS 2022 | 历史实测环境；功能按已有范围声明，后续按反馈跟进 | [0.2.5 逐项记录](PROGRESS_025.md)、[增量证据](validation_increment_025.json)、`capabilities.py` 中的限制；历史其他套件各自保留日期 | DEV-001 仅验证开发检查与单元，未重跑原生套件；不作为当前验收门槛 |
| Windows x64 / Creo 12.4.0.0 / 匹配 SDK | 已验证可用，功能按已测范围声明 | [BUG-002 验证](validation/BUG-002.md)：登记并发轮询下新建、参数修改、保存重载、失败回滚和 stale revision；[FEAT-019 WorkBuddy 报告](validation/FEAT-019-WorkBuddy-report.md)：自动启动、Toolkit 就绪、草图/拉伸、尺寸驱动、倒角、保存重载与导出 | 上述专项实测通过；发布时另一次冷启动复测失败，保留 BUG-005；两截面种子等其他分支仍由 BUG-004、DEV-005、DEV-006 核实 |
| Windows x64 / Creo 12 其他维护版本 / 匹配 SDK | 需目标机验证 | 当前成功记录限定 12.4.0.0，其他维护版本没有独立实机证据 | 未逐版验收 |
| Windows x64 / Creo 9.0.0.0 / 匹配 Toolkit 9 | 已纳入支持/要求范围，编译探测已支持 | [BUG-033](work-items/BUG-033.md) 的常量存在/缺失夹具已通过，修复与安装闭环见 [DEV-028](work-items/DEV-028.md)；第三方 [Creo 9 SDK 编译反馈](validation/2026-10-15_CREO_0.3.0_旧版ToolkitSDK原生编译失败.md) 与 [0.3.2 报告](validation/FEEDBACK-0.3.2.md) 保留原环境结论 | 本机无 Creo 9 SDK；0.3.5 外部环境编译与安装已通过（见 2026-10-18 补录），其中 1 个单元测试失败登记 [BUG-057](work-items/BUG-057.md)；建模运行时仍未验收，不外推为已通过 |
| 其他 Creo、SDK 或操作系统 | 尚未承诺 | 单元检查与安装成功不能推导原生兼容 | 未验收 |

安装要求保留匹配 SDK、公制模板、MSVC x64 和许可。升级 SDK 或维护版本后要按本机环境重新构建与验证。后续矩阵按工具家族、具体参数分支、环境、源码、命令和结果细化；“接口存在”“已测代表用例”和“全部参数覆盖”分别记录。

BUG-008（2026-10-15～16）：按本机 Creo 12.4 / 匹配 SDK 已验证范围完成，见 [关闭复核](validation/BUG-008-closure-2026-10-16.md)。分层证据包含原生断开/结果交付受控回归、246 项单元、同实现真实冷态自动归档旧 NUL 记录/重建/单次启动，以及新 WorkBuddy 单次/重叠 retry、120 mm³ 新件/参数/保存重载和 unknown 保护通过。同次开机损坏或证据不确定仍保留人工处理分支；WorkBuddy 冷态及异常环境、历史完整挂死链和其他环境未验证，不外推为所有受损 Creo 已自动恢复，也不把开发者冷态结果写成 WorkBuddy 通过。

FEAT-019 专项（2026-10-13）：Creo 12.4 / 匹配 SDK 已构建，121 项 Windows 单元与语言检查通过。用户接受 WorkBuddy 最终 MCP 实测：自动启动、Toolkit 就绪、草图/拉伸、尺寸驱动、倒角、保存重载和导出通过；Codex 通过开发版 MCP 只读复核 6 个成功任务与最终模型。该结果支持 Creo 12.4 在所列范围内可用；该专项未取得 Creo 10 实测结果，真实多客户端并发启动和全部客户端退出后的成功重连未验证。Codex 新一轮冷启动连接失败单列 [BUG-005](work-items/BUG-005.md)，不能单凭错误码归因为许可或版本。原报告中的“实验兼容”保留其当时定位，见 [原记录](validation/FEAT-019.md)。

0.2.6 发布候选：合并上述实现，保留历史实机日期；本轮 Windows、包验证和连接结果见 [发布验收](validation/RELEASE-0.2.6.md)。Creo 10 尚未复测，BUG-005 未修复。

FEAT-020 专项（2026-10-14）：Windows / Python 3.12 的版本、缓存、网络分支及 stdio MCP 更新接口已验证；当时本机没有 Creo 10 环境，Creo 12.4 的联网失败下原生建模仍待实际 Toolkit 就绪验证。新功能不修改 C++，但历史原生成功不能替代本项集成验收；最终状态见 [本次证据](validation/FEAT-020.md)。

0.3.0（2026-10-14）：BUG-006 N1 按用户确认的 WorkBuddy 测试记为通过，未提供详细新报告；FEAT-020 的 [WorkBuddy 原报告](validation/FEAT-020-WorkBuddy-report.md) 在 Creo 12.4 / 0.2.6 开发服务验证更新接口、缓存、实际并发和联网条件下板件保存重载，高版本及断网场景未测。原 C++ 未变，本次没有全量原生回归；当时另列的 Creo 10 外部复测未补录，该安排现已取消。DEV-002 第一批仅迁移 Python 更新模块与测试；整体继续开发。发布源码及分发检查见 [0.3.0 记录](validation/RELEASE-0.3.0.md)，BUG-005 仍待核实。

2026-10-14 P1联合开发验证：Windows/Python3.12.14/Creo12.4安装及匹配SDK，公开release_numeric=44；引用兼容、简单/含放样件尺寸关系及回滚、基准面/边参考孔、合法原生筋、真实inspection与查询分页通过。原始Creo10尺寸/关系及合法基准面孔失败未在本机复现，保留历史来源；当时尚待最终WorkBuddy，后续验收与收尾以[主台账](BACKLOG.md)为准。逐轮源码/构建身份、dirty及未测范围见[联合证据](validation/P1-MODELING-REPAIR.md)，不外推到公开0.3.0附件。

## 2026-10-16：0.3.3 外部构建与本机恢复复现

[新构建反馈](validation/FEEDBACK-0.3.3-BUILD.md)保留Windows10/Creo10.0.0.0/Python3.13/VS2022与reg.exe受限的来源：三键vcvars64_env使官方构建成功，一个三截面自动匹配保存重载通过；完整job/model、构建日志及完整安装记录未提供，本机未复验。缺回调直接放样为快速拒绝，不计成功；常量生成仅覆盖该Creo10 SDK，不证明Creo9目标场景，DEV-020/022未触发。

用户另行完成的[BUG-001复现](validation/BUG-001-repro-2026-10-16.md)在本机Creo12.4/0.3.3隔离矩阵确认未知结果保护后的模型协调缺口，采用12s预算及过程注入而非复刻Creo10原601s模型。该结果是缺陷复现，不是恢复修复通过，也不是WorkBuddy黑盒；BUG-008原锁释放/通道恢复关闭范围保持。其他版本支持范围和独立复测规则不变。

## 2026-10-17：恢复开发分支验收中

BUG-001/FEAT-018 已实现正式协调与普通写保护，284项单元及四动作部分本机Creo12.4实机通过；随后connect -11及用户报告Creo卡死，最新代码最终实机与WorkBuddy未完成。详见[本次验证记录](validation/BUG-001-recovery-2026-10-17.md)。仅为未发布开发改动，不外推Creo9/10或公开0.3.3已提供该工具；未关闭、合并或发布。

## 2026-10-17 FEAT-029集成分支

稳定注册/回调状态已集成E盘开发源码，297项单元、匹配Creo12.4 SDK编译、独立载荷ABI及stdio离线检查通过。原分支2026-10-16的[生命周期/WorkBuddy记录](validation/FEAT-029-closure-2026-10-16.md)保留历史范围；本次集成环境尚未复跑实机，不能外推为Creo9/10或当前会话已就绪。见[集成证据](validation/FEAT-029-integration-2026-10-17.md)。

## 2026-10-17：0.3.4主干交付范围

0.3.4汇总恢复与回调实现及原始反馈，BUG-001按用户决定关闭；FEAT-018/029继续验收中。本版仅重新执行适用离线、单元、构建与分发检查，不新增Creo连接或原生/WorkBuddy验收。原始卡死及根因未定事实保持，旧证据不外推为最新集成实机通过。见[本版说明](RELEASE_NOTES_0.3.4.md)和[发布检查](validation/RELEASE-0.3.4.md)。

## 2026-10-17：0.3.5 已测范围与已知通道问题

BUG-054/DEV-033的本机Creo12.4实体extrude/revolve cut开发、保存重载/回滚及WorkBuddy已测场景通过；BUG-055/DEV-034的真实stdio、MCP恢复正例及WorkBuddy核心契约通过。M2终态与稳定通道下对照未取得，BUG-056仍为P1待核实，FEAT-018/029完整恢复/生命周期未完成。外部Creo9与Creo10未据本版重新复测，种子/筋等历史失败来源保持。本轮只补离线/SDK/安装与分发检查，见[0.3.5验收](validation/RELEASE-0.3.5.md)。

## 2026-10-18：0.3.5 外部 Creo 9 SDK 反馈补录

[外部反馈](validation/FEEDBACK-0.3.5-2026-10-17.md)（Windows 10 19045 / Python 3.13.14 / MSVC 19.44.35229 + Windows SDK 10.0.26100 / Creo 9.0.0.0 Toolkit SDK）首次提供 Creo 9 SDK 实机编译证据：`bridge.py build` 一次通过，`constants.inc` 探针宏 0 个（BUG-033 修复行为正确），安装后 84 工具、9 个种子 SHA256 校验通过。307 个单元测试 306 通过，唯一失败为并发准入测试报 `PermissionError [Errno 13]`，已登记 [BUG-057](work-items/BUG-057.md)。该失败为单元测试，与 Creo 版本无关；本次未连接 Creo 会话，切除守卫、恢复 MCP 的实机行为及全部建模运行时仍未验收，种子哈希校验也不代表 Creo 9 可加载（BUG-034 的 -16 保持）。

## 2026-10-18：0.3.5 外部 Creo 9 实机与 Creo 10 反馈补录

[Creo 10 反馈](validation/FEEDBACK-0.3.5-CREO10-2026-10-18.md)（Windows 10 / VS2022 BuildTools 14.44 / Python 3.13）按"停止新的 Toolkit 连接"约束未连实机：源码/种子包 sha256 与发布说明双一致，覆盖 546 文件零真实差异，编译经三键 `vcvars64_env` 一次成功；**文件层实证 0.3.4→0.3.5 升级（含 worker 重编）完全不触碰回调注册**（protk.dat、exec_file、loader 指纹/sha、两个 DLL 大小、payload 指纹均未变），补上"每次重编译注册失效已解决"的升级场景一环；cut 守卫仅读码核对一致，未实机。vcvars64_env 三键限制第三次未修（DEV-030），payload 目录保持 6 个未新增但清理机制仍不存在（DEV-027）；实机建模、cut 行为、恢复契约、回调加载与通道稳定性全部未验证，不作通过结论。该反馈引用的发布说明"BUG-056 未修"已被当日后续 DEV-036 调查取代（nmsd 根因、复测通过、关闭归档）。

[Creo 9 实机反馈](validation/FEEDBACK-0.3.5-CREO9-2026-10-18.md)（9.0.0.0 / release 41 / stdio）：**BUG-054 切除守卫与 BUG-055 恢复契约（含 restore_baseline 与三条空值路径）实机验收通过**，数值精确（去料 π×5²×10、revision/体积保持），补齐两卡外部 Creo 9 未测项；孔、参数、关系、工程图 PDF、翼型、UDF、种子清单与运行身份指纹核对全部通过。通道稳定性出现新现象：上一请求成功约 33 秒后 `connect_creo` 返回 **-11**，Creo 进程存活但无主窗口，自动重连不能自愈，人工结束残留进程后恢复——与已关闭 BUG-056（nmsd 层 -4）为不同层失败，登记 [BUG-058](work-items/BUG-058.md)；恢复执行前拒绝被标 `unknown_outcome` 的问题登记 [BUG-059](work-items/BUG-059.md)。历史未修项第六轮确认：种子加载仍 -16（BUG-034）、筋材料侧仍失败（BUG-017）、loft 仍需人工注册（FEAT-029）、component_constraints 仍不求解（BUG-036）、round 参数名仍未统一（BUG-019）；这些不因上述通过项而改变范围。

## 2026-10-18：0.3.5 外部建模能力边界反馈补录

[能力边界反馈](validation/FEEDBACK-0.3.5-CAPABILITY-2026-10-18.md)（Creo 10.0.0.0 / release 42 / stdio / ready，依据纯文本规格从空白重建 4 零件 + 8 实例虹膜式机构，全部几何来自文本坐标、无外部模型输入）：4 个零件完成 2 个（齿形摩擦片实测 18569.9426 / 记录 18570.1 偏差 −0.0009%；小齿轮 1490.7023 / 1490.8 偏差 −0.0066%），2 个部分完成（星形架 +28.06% 因阵列失败、摆杆 −36.29% 因基准面草图失败），装配未进行。**多环截面（含互不相交）失败**扩展 [BUG-049](work-items/BUG-049.md)；新登记 [BUG-063](work-items/BUG-063.md)（非原点轴阵列静默几何错误，体积量化）、[BUG-064](work-items/BUG-064.md)（基准面草图 surface 引用与纯轴向 u_axis 硬失败）、[BUG-065](work-items/BUG-065.md)（datum_axis 两平面求交退化、轴不可观测）、[BUG-066](work-items/BUG-066.md)（preview.jpg 与实际几何不符）。反馈称"无批量接口"与 `creo_execute_plan` 已存在的事实不符，按能力发现不足记录（FEAT-008）。

**正向回归基线（外部实测精确）**：主轴面 coordinates 闭环（20/4/6 段）、extrude add/cut 全模式、revolve 构造中心线 symmetric 67°（Pappus 估算差 0.45%）、**过原点轴** axis_pattern（40×9° 与 5×72° 逐实例精确）、datum_plane offset/angled（法向逐位吻合）、柱面取轴 datum_axis、inspect surfaces（圆柱面 axis/origin/radius）、material_removed_mm3 逐次精确。这些不因上述缺陷改变，可作为后续修复的对照基线；本机 Creo 12.4 对应复现另行安排。

## 2026-10-18：0.3.5 外部曲面链路反馈补录

[曲面链路反馈](validation/feedback-0.3.5-surface-2026-10-18/report.md)（Creo 10.0.0.0 / release 42 / 84 工具 / 60 operations，附[可乐瓶五爪花瓣瓶底任务书](validation/feedback-0.3.5-surface-2026-10-18/可乐瓶五爪花瓣瓶底建模任务书.docx)与参考图集，原件 SHA256 见 [manifest](validation/feedback-0.3.5-surface-2026-10-18/manifest.json)）执行纯曲面法任务书后确认：8 步中 5 步无对应工具（surface_trim / quilt_merge / boundary_blend / quilt_offset，loft 无曲面模式），链路几何上不可执行，登记 [FEAT-039](work-items/FEAT-039.md)（含按投入产出比排序的 MVR：merge 常量已齐只差封装）；回转类草图不可就地编辑（update_sketch_geometry 不支持 centerline，job `085e56a7…` 双路径矛盾）登记 [BUG-062](work-items/BUG-062.md)；变半径圆角缺口（两个 R2 失败 job，近切收敛几何上恒定半径无解）登记 [FEAT-040](work-items/FEAT-040.md)，交付/预览体验归拢 [FEAT-041](work-items/FEAT-041.md)。正向旁证：`boolean_bodies` subtract 单 tool 成功（407,482.40 mm³，与手算差 0.6 mm³）、实体法链路完整走通且加料版抽壳成功、`revolve{new_body}` 可绕道生成独立爪实体；两个模型的 STL 已随外部保留，可作 FEAT-039 回归基准。shell 求差版两连败的另一半原因在任务书尺寸链自身（0.357 mm 刀口），反馈自认非 MCP 缺陷，其"失败无根因"诉求归 FEAT-006。本机 Creo 12.4 的曲面链路验收待 FEAT-039 实施后另行安排，本节不外推。

## 2026-10-18：0.3.5 外部钣金第四轮回归补录

[钣金回归反馈](validation/FEEDBACK-0.3.5-SHEETMETAL-2026-10-18.md)（0.3.5，报告未声明 Creo 版本，延续 0.3.1～0.3.3 同一外部环境与配电箱/履带用例；本轮附 job/model 可复查）对前三轮缺陷逐条最小复现：**S1 钣金件增料（BUG-046）、S3 四壁折边（FEAT-014）、S5 depth 被厚度覆盖（BUG-032）连续第四个版本未修**，反馈总结钣金侧 0.3.1→0.3.5 无一项修复进展；P5 旋转反手以实机回读第四次确认（BUG-045）。本轮用例已排除 S1 的"无重叠/仅共面"误判（增料块与实体真实体积重叠仍失败、同件切除成功），S3 新增厚底板第 1 道即失败的边界发现（折边折向驱动面侧落入既有实体，佐证 BUG-047）。P11 打包导出（FEAT-031）、S10 失败空 operations（BUG-018）、N1 钣金 bodies 恒 2（BUG-040）、S7 起始 checking（FEAT-001）同步补第四轮证据；S6（unbend fixed_surface 不接受 datum_plane）与 P3（草图字典平面 offset 被拒）沿用 0.3.3 实测、本轮未复测，分别登记 [BUG-060](work-items/BUG-060.md)、[BUG-061](work-items/BUG-061.md)。正向项：list_components 紧凑化保持已修，0.3.2 已修的多区域增料/共面合并/polyline 未回归。既有交付物（out/、out2/ 与三轮反馈文档）不受影响。本节不改变任何条目的已测/未测边界，钣金链路在本机 Creo 12.4 的对应验收另行安排。

## 2026-10-18：0.3.5 外部 Creo 10 实机验收补录

[Creo 10 实机反馈](validation/FEEDBACK-0.3.5-CREO10-2026-10-18-2.md)（10.0.0.0 / release_numeric=42 / Python 3.13 / connected=true）为实机验收（8 个作业、5 个新建诊断零件，全部 job_id 可复查）：**BUG-054 切除守卫 6/6 用例通过**（合法/部分重叠/revolve 合法数值精确，板外/管外/hole 板外三例守卫触发且回滚、revision 保持、不落盘、体积逐位不变，失败后可继续编辑），同轮复测 BUG-022 hole 守卫与 BUG-013 `list_models` 分页闭环；已关闭的 BUG-056 现象在本轮 8 作业约 8 分钟连续建模中未复现（仅数据点，不改变其 nmsd 根因结论）。既有交付物未受影响：齿轮泵 11 零件与装配 revision=7 未变，18 实例变换抽样与 0.3.3 读回值逐位一致无漂移。未修项按既有条目补证据：**弧方向静默主弧（FEAT-034，第三次报告，实机对照 142.699 vs 1428.097 mm³ 相差 10 倍且零警告）**、自交轮廓无结构化诊断（FEAT-006）、组件清单丢 label（FEAT-023）、旋转仅欧拉角且 BUG-045 角度方向再确认（FEAT-012/BUG-045）、hole 无沉孔锥孔（FEAT-035）、revolve 轴不回显（FEAT-008）、新件 rollback_succeeded=false 误读（BUG-012）。本轮通过项不外推为该环境其他工具或参数分支已验收。

## 2026-10-18：0.3.7 Creo 13 反馈问题 1 复现定性（BUG-067）

[0.3.7 / Creo 13.4.1.0（自报，release_numeric=45）反馈](validation/FEEDBACK-0.3.7-CREO13-2026-10-18.md)报告 `creo_revolve` 恒返回 `ProFeatureWithoptionsCreate=-1` 并推测 Creo 13 元素树不兼容。本机 Creo 12.4 / 匹配 SDK 经同一公开 MCP 接口复放（[证据](validation/BUG-067-repro-2026-10-18.md)）：两例报告输入均为**非法跨轴旋转截面**（闭合区域与直径实体跨越竖直旋转轴），在 12.4 同码复现失败且回滚正常；合法画法（轴与直径边界重合）得精确球体、参数可编辑、保存重载通过。**结论：失败由输入几何非法导致，与 Creo 版本无关，不成立"Creo 13 旋转元素树不兼容"**。同轮修复"拒绝但不解释"：旋转/拉伸创建失败现返回跨轴/中心线/闭合提示与草图标签（元素级错误如有可能时附上），拒绝、回滚与 revision 保护不变；`tools/dev_check.py` 与 `tools/test_general.py` 回归通过。**Creo 13 维持"尚未承诺、未验收"**：该环境合法画法复测待外部条件具备后执行，本节不据本机结果改变支持矩阵，也不外推该环境其他工具已通过。

## 2026-10-18：纳管第二阶段开发分支

FEAT-042无盘prepare/apply、FEAT-043会话枚举及BUG-071预检收尾已实现；403项Python单元与统一检查、匹配Creo12.4 SDK构建通过。用户确认现场后首次9秒就绪探测超时，未提交纳管或抽壳任务，未做新一轮原生几何/保存重载验收。无盘001、未保存修改、外部目录及钣金仍未实机验收，WorkBuddy未执行；不改变其他环境支持声明或旧验证结论。详见[本轮证据](validation/ADOPTION-COMPLETION-2026-10-18.md)。

## 2026-10-25：种子来源与加载兼容性（FEAT-030 / BUG-034）

种子相关结论按"文件证据"与"原生加载证据"分开记录，两者不互相替代。

**当前口径（逐字引用）**：外部 Creo 9 已报告受测种子 -16；另有 Creo 10 三截面成功历史；当前会话/其他种子未验证。

- 外部环境为 Windows 10 / Creo 9.0.0.0（release 41）/ 服务 0.5.0、0.5.1：`creo_new_airfoil_blade` 与 `creo_new_loft_part`（种子放样）均报 `ProMdlFiletypeLoad failed with code -16 during connect`。记录口径为**该受测环境两条放样路径均未成功**，不外推为所有 Creo 9 放样均不可用；`-16` 本身不足以唯一归因为版本不兼容。
- Creo 10.0.0.0 有三截面自动匹配混合成功且 `saved_file_reloaded_and_verified=true` 的历史记录（2026-10-17 报告），无 job/model 标识，不外推为完整 Creo 10 运行时验收或全部九个种子在该环境可加载。
- **不写未经证实的最低 Creo 要求，也不写笼统的"Creo 10+ 已验证"。** 本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 的成功记录只覆盖本机已测范围。

### 来源与生产版本

- `seed_build_version` 只接受**可追溯生成记录**（`docs/seed_manifest.json` 中与该种子 SHA256 绑定的条目）或**可靠原生证据**（`build/seed_provenance/<sha256>/` 下由原生会话写下的记录），两者都必须与**实际种子 SHA256** 绑定；文件字节变化后不再归属，原值回到 null。
- 当前九个已发布种子**没有**可追溯的生成记录，因此 `seed_build_version` 保持 null。UGC 头里的 `PART 2128 …` 等数值只作为 `seed_file_diagnostic.ugc_part_version_token` 诊断线索保留，没有已证明的版本对应关系，不建立 2128=12.4 之类映射，也永不用于填 `seed_build_version`。
- 种子库重生成是另列的环境受阻子项：本机无匹配旧版生成/验收环境时不承诺完成，也不新增双版本发布门槛。

### 查询与失败诊断

- `creo_list_seeds` / `creo_validate_seed` 的 `available` 只表示**文件字节与 SHA256 有效**，不代表当前 Creo 可加载；普通查询不建立 Toolkit 连接、不隐式试载（`native_load_probe = not_performed`）。`native_compatibility.status` 恒为 `not_verified_for_current_session`，历史加载记录按种子 SHA256 隔离，只说明"别的会话里发生过什么"。
- 放样/翼型加载失败时保留原始 API、错误码、实际阶段、种子标识与 SHA256、可取得的运行版本（`creo_release_numeric` / `session_fingerprint`），并提示核对兼容性与来源。只有当存在与该 SHA256 绑定的来源记录且其 release 高于当前会话 release 时，才给出有界的版本提示；否则 `cause = undetermined_by_error_alone`，不硬写"由 Creo 12.4 构建，当前版本无法加载"。加载成功与后续建模成功分别记录（`seed_load_succeeded` / `modeling_succeeded`）。
- 诊断写入失败不改变建模终态，失败原因保留在 `seed_load_evidence.evidence_error`。

本轮为开发分支改动，未连接 Creo 会话、未执行实机建模与保存重载；实机成功核对留给回归收口任务。详见 [FEAT-030](work-items/FEAT-030.md)、[BUG-034](work-items/BUG-034.md) 与[本轮验证记录](validation/FEAT030-BUG034-SEED-TRANSPARENCY-2026-10-25.md)。
