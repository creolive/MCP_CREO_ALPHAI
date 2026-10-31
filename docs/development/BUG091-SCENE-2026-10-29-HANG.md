# BUG-091 现场二：2026-10-29 作业内挂起与后续会话消失

2026-10-31 P01 离线复核。依据 [T11 §3.5/§4.1](DEV051-T11-ACCEPTANCE.md)、`build/sheetmetal_relief/20261029T165319_74073f09/report.json`、`jobs/bb5543fb3c66404e95172876fa1ac9aa/` 及[前次调查](BUG091-OFFLINE-EVIDENCE-2026-10-30.md#现场-b2026-10-29第三道折边作业内挂起及会话消失)。时间为 Asia/Shanghai，UTC 减八小时。

| 字段 | 已核实与限度 |
| --- | --- |
| 环境与指纹 | Creo 12.4.0.0，报告服务 `current_version=0.8.3`。T11 记运行执行器由 16:53 源码构建；后来 `source.sha256=541a9657…` 属整理后的构建。事故运行 worker 的 SHA256 **缺失**。 |
| PID | `native_owner.json` 历史记录 PID 20408、session fingerprint `2194098641453425411`；挂起作业 runner PID 21140，两字段不能互认。Creo 两进程的事故创建时间、worker PID/创建和退出、nmsd 6504 创建/父进程、pro_comm_msg 身份**缺失**。 |
| 最后成功 | 底板 `579dc118…`、`f_px` `07b5ec25…`、`f_nx` `b57c115d…` 在 16:53:33–54 succeeded，模型 rev 3、保存重载 true。 |
| 首异常 | 第三道 `f_ny` 作业 `bb5543fb3c66404e95172876fa1ac9aa` 于 16:54:04 建立，`native.log` 最后为成功的 `ProArrayAlloc`；没有 `ProFeatureWithoptionsCreate` 入口/返回记录，不能断言卡在其内部。17:01:05 轮询 420 秒仍 running，`toolkit.lock` 当时据 T11 被作业持有；作业文件仍无持久化终态。 |
| 原码 | 挂起本身**没有** `-4/exit 20`。19:51:03 WER 1001/1002 `AppHangB1` 记录 `xtop` 被关闭（仓库无 evtx/XML 原件）；19:53/20:06 两次 tasklist 无 Creo 两进程；20:04 后续只读探测才返回 `not_found_or_unreadable/-4/exit 20` 且 `processes=[]`。 |
| GUI 与重启附记 | 17:01–19:51 菜单/视图、窗口、用户动作和等待链**缺失**。历史附记称随后重启可起、几分钟后自退出，只留 pro_comm_msg；每次新 PID/时间/事件原件**缺失**。22:05 后另有新 PID 15156 和成功作业，不填补中间空窗。 |

**区分假说。** 几何/再生调用阻塞：需原生调用入口与返回、Creo trail、等待链/dump；目前只能定位到最后一个已记录的 `ProArrayAlloc`。GUI 模态或交互阻塞：需挂起时窗口与人工操作原件，现缺。进程被 WER/人工处置后连接消失：WER 原件、进程退出顺序与锁快照能区分，现只有历史转述和两次进程清单。重启后短命另属生命周期观察，需每次 PID/创建退出和事件，不并作本作业原因。

**完备度：部分。** 作业阶段与最后成功清楚；挂起期间 GUI、运行 worker 指纹、事件原件及会话消失前后锁/unknown 缺。20:04 的 `-4/exit 20` 是后果层映射。
