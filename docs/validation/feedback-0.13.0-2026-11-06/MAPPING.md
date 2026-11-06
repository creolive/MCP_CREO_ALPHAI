# 0.13.0 四件反馈逐项映射（DEV-069）

> **当前复核：** 本文下方保留0.14.0起草时点的原始映射；它不再描述当前源码。2026-11-06已fetch并核对main/0.16.0（`4517e36`）：Init/回执/矩阵/长轮询/附件闸门已有实现，四壁BLIND miter基础已交付；原生板厚几何兜底仍未实现。最新逐项差异见[主干对账](../../development/DEV069-MAIN-RECONCILIATION-2026-11-06.md)，剩余任务见[更新计划](../../superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)。原件和manifest逐字节保持，不覆盖原外部结论。

核对日期：2026-11-06；本地源码 `7002575` / 0.14.0。原件逐字节存放 `originals/`，完整文件名、大小和 SHA256 见 [manifest](manifest.json)。本轮只读源码和历史文档，不调用 Toolkit、不执行产品测试；下列“确认”仅指外部报告或当前静态状态。

来源简称：A＝会话断连与 execute_plan 旋转约定（18 272 B）；B＝偏置错误码与发布闸门（20 658 B）；C＝曲面链通过但保存失败（25 001 B）；D＝闭合首壁与四壁被拒（12 912 B）。报告 A/B 的“未验证”与 C/D 的后续实跑各自保留，不能改写为同轮全测通过。

## 逐项去向

Rxx 指 [本轮计划](../../superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)；Qxx 指 [既有剩余计划](../../superpowers/plans/2026-11-04-0.12.0-feedback-reconciliation-plan.md)。固定 ID 以主台账唯一行登记，以下是子项索引。

| 来源 | 反馈 | 当前核对与处置 | 固定 ID / 执行入口 |
| --- | --- | --- | --- |
| A N-1 / C §4.3 | IPC 不通、retry 不可操作 | 外部阻塞事实明确；重编译与断连因果未证，不强制全员重启 | FEAT-001、BUG-091；R06 |
| A §1.3 | 机器可读重试进度/终态 | launch_attempt 是启动次数不能直接替代 retry_id；补独立回执与预算语义 | FEAT-001；R06 |
| A §1.3 | hung 窗口/PID/标题、自动恢复入口 | 保留可核查事实和 suspicion；标题需有界只读设计，不据此自动重启/清 IPC；重建会话动作不纳入本轮 | BUG-091、BUG-001；R06 |
| A P-1 / N-2 | execute_plan 未声明旋转约定 | AssemblyPose.rotation_matrix 仍无 description；底座已存在 | BUG-045、FEAT-012；R05 |
| A P-2 | 17.9° 正交矩阵装配 -2 | 1e-6 正交/det 校验已有；外部任意角根因未定，需完整/舍入矩阵对照 | FEAT-012；R05、Q02 |
| A P-3 | 拉伸失败缺上下文 | 逐 op 结果已有，缺可定位的结构化 failed_operation，不能把旧字段当新修复 | FEAT-008；R05、Q02 |
| A P-4 | through_all 的方向/depth 语义 | 0.14.0 已有 extrude_depth；effective_depth_mm=null 的实机与未命中诊断仍缺 | FEAT-039、FEAT-008；R12、Q06 |
| A P-5 / N-3 / N-4 | compact 冗长、列表日志、无取全提示 | compact 白名单和列表复用路径仍在；8192 是读日志预算，实际响应量需测 | FEAT-023；R04 |
| A P-6 | 装配整体 bbox 缺失 | 旧 helper 仅有预期派生 bbox；需原生测量，不能由组件拼装冒充 | FEAT-008、BUG-013；R12、Q06 |
| A P-7 | 组件来源映射 | 外部已确认，当前底座存在；不再开发 | FEAT-023/T09A；仅回归 |
| A P-8 | connected 与 health unknown/stale 混杂 | 当前连接、历史保存与总体健康不能强行合成 ok | FEAT-001；R06 |
| A P-9 | session_status 占通道 | 单通道设计的一部分；默认缓存/明确 live 语义可改善，不新增旁路并发 | FEAT-001、BUG-009；R06 |
| A P-10 | managed rename/delete | rename 已有独立 FEAT-062 计划；delete 无现成同义能力，先登记设计，不能拿 erase 代替 | FEAT-062、DEV-069；R12 |
| A P-11 | 提交回显约 25 KB | 本报告未验证；先测真实 stdio 响应，勿误将客户端请求展示算响应 | FEAT-023、FEAT-008；R04 |
| A N-5 / B §4.5 | gated 在 compact 可见性 | 门禁透明但摘要可更明确，保持计数口径分离 | FEAT-039、FEAT-023；R07 |
| B §4.1 | Init 返回码丢失 | 本地同一错误仍在，确定代码缺陷；无运行时错误面积实证 | BUG-112；R01 |
| B §4.1 | C4552 编译闸门 | 有针对性升级自有源码警告，不全量升级 SDK/第三方 | BUG-112；R01 |
| B §4.2 | FEAT-039/DEV-067 首页落后 | 卡与台账仍有历史首页/未排期内容，须按子项版本回填 | DEV-069、DEV-062；R07 |
| B §4.2 | README 链接标题 0.12.2 | 当前已指向 0.14.0，退出修复；版本一致性回归保留 | DEV-062；R07/R08 |
| B §4.3 | 打包/CI 未调用四附件闸门 | 当前 package 只警告缺 seed sidecar，仍需自动失败 | DEV-070；R08 |
| B §4.3 | 无 gh / github 直连受限 | 首批可操作 --dir 降级；API 下载备用属可选后续，不能把离线校验当远端通过 | DEV-070；R08 |
| B §4.4 | sidecar CRLF | 当前 write_text 未固定 newline，Windows 可复发；输出 LF、读取兼容 CRLF | DEV-070；R08 |
| B §3 | 0.12.0/0.12.1 归档未见 | 0.12.0 Q00 已有待办，0.12.1 原件不在本次目录；保留去向，不假称本次补齐 | DEV-069；R00/既有 Q00 |
| C §2 | trim/offset/project 与 trim→thicken 在 Creo 10 通过 | 外部新增专项正证据，引用其原 job；不记成本机或全能力验证 | FEAT-039；R07 证据回填 |
| C §3.1 / A §4 | quilt_merge 仍 gated | 已知未交付边界，不是回归；实体并集不是合并 quilt | FEAT-039；R11、Q03 |
| C §3.2 | surface loft / boundary_blend 缺失 | schema 形态存在但准入拒绝；维持门禁，明确 solid add only | FEAT-039、FEAT-009；R11/R07 |
| C §4.1 | Backup -1 + 回滚失败 | 新登记，普通平面 trim/thicken 与自依赖投影链分别复现 | BUG-113；R02 |
| C §4.2 | 三曲面算子判据 compact 不见 | 本地白名单确实缺；与体量改进同一任务实现 | FEAT-023、FEAT-039；R04 |
| C §4.4 | families/reference 旧说明 | scope/limits 仍旧，需补三工具引用及环境范围 | FEAT-039、DEV-069；R07 |
| C §4.5 | W01 说明冲突 | 当前两处已一致为策略+本体交付；不再修复，不由默认 applied=false 推断缺能力 | FEAT-039；R07 只核一致性 |
| C §4.6 | 无长轮询 | 旧计划 C04/FEAT-007 已登记，接续不重复实现 | FEAT-007、BUG-109；R12 |
| C §4.6 | connect idle_seconds=null | 旧日志无时间时 null 正确；新日志补有来源计时，不伪造 | BUG-109；R12 |
| C §4.7 | erase 偶发 21 s | 单样本性能观察，不预判缺陷、不去掉擦除重载 | BUG-109、FEAT-033；R12 |
| D §1 | native 首壁/resize/逐边资格/方向可控 | 0.12.0 已交付，D 外部补证；不新建“0.13.0 新增首壁”记录 | FEAT-058、BUG-103；R07 |
| D §2 | 第三道 adjacent_bend_ends 拒绝 | 保护按现有边界工作，四壁仍是能力缺口；不能删 guard | FEAT-014；R09 |
| D §2.2/2.3 / §3.6 | relief 接受却无几何效果 | bend-end/corner/miter 区分，去料缺口证据待建立；干净边同体积不足以认定 bug | FEAT-014；R09 |
| D §3.1 | gauge null/verified=false 但 job 成功 | API 缺失降级的已知缺口，沿用 Q01；job 执行与测量验证分层并给 reason | FEAT-058；R03 |
| D §3.2 | 首壁无法居中 | 新能力，origin 默认兼容、resize 保持坐标系 | FEAT-058；R10 |
| D §3.3 | native_planar 错误导向 conversion | 按实际来源分派报错，未知来源不猜模板 | FEAT-014、FEAT-058；R09 文案子项 |
| D §3.4 | 单计划固定 edge id 失效 | 拒绝历史 ID 正确；新增几何选边需唯一匹配及逐 op 原生解析 | FEAT-008、FEAT-014；R10 |
| D §3.5 | edge={id} 缺 kind、报错不定位 | 增参数路径与正确示例，不恢复歧义引用 | FEAT-008；R09 文案子项 |
| D §3.5 | 0.13 notes 未写钣金变更 | 首壁来自 0.12.0，relief/guard 更早；补导航和真实首次版本，不虚报新增/参数迁移 | DEV-069；R07 |
| D 历史 S2/N3/S1 | flip/预览/add | 方向已有外部正证；预览本轮未复现失败；sheetmetal add 明确拒绝可接受 | BUG-047、BUG-088、BUG-046；仅保留范围 |
| D 历史 S6/P3/P5/P11 | unbend/plane offset/装配方向/native_bundle | 本轮没测；分别接续 BUG-060/061/045、FEAT-031；native_bundle 已交付，不能仍称无工具 | 既有 ID；R12 去向核对 |

## 缺件与结论边界

外部 C 的完整 native.log/job.json/检查点、D 所引 TXT、17.9° 精确原矩阵、gear10 原输入、受测 worker 完整身份未随本次四件提供。实施先使用明确标注的最小替代夹具，并可索取原 MCP 输入/输出；不能自动访问报告中另一机器的本地路径来补齐。若 WorkBuddy 验收，只要求公开 MCP 证据。

已发布标签/附件本轮不改。报告 B 的升级与哈希成功、A 的旧模型快照未漂移、C 的曲面正例、D 的首壁正例均作为各自环境的历史正证据，不重新安排完整能力开发。
