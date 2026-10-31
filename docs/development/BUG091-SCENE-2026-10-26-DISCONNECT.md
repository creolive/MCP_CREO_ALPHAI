# BUG-091 现场一：2026-10-26 0.6.1 验收断连

本页为 2026-10-31 P01 离线复核。原始时间线见 [BUG-091 前次调查](BUG091-OFFLINE-EVIDENCE-2026-10-30.md#现场-a2026-10-26061-验收断连)及 [BUG-085 证据](BUG085-OFFLINE-EVIDENCE-2026-10-30.md#2-事故-a-时间线061-断连2026-10-26utc--asiashanghaiutc8)。不修改这些原件。时间均为 Asia/Shanghai，UTC 减八小时。

| 字段 | 已核实与限度 |
| --- | --- |
| 环境与身份 | 本机 Creo 12.4.0.0；称 0.6.1 验收，但 `build/installation_loft_validation.json` 元数据为 `version=0.6.0`。事故时源码 dirty；04:36:29 对应 12:36:29 提交 `f54cda8`，不能倒推运行 worker 的逐位身份。事故时 `build/source.sha256`、worker SHA256、构建和替换时刻均**缺失**；当前 build 文件是后续构建。 |
| Creo PID | `parametric.exe` 20180 创建于 08:07:11.125；`xtop.exe` 20164 创建于 08:07:11.802。12:38 快照仍存在；nmsd、pro_comm_msg、worker 的 PID/创建时间/父进程**缺失**。 |
| 最后成功 | 第二轮四作业均 succeeded、保存重载 true，最后 `14560f1b98bd41f4abda91d0ff2a6b8c` 于 12:30:44.689 完成；trail 最后一次 IPC 12:30:42。`jobs/<id>/job.json` 与 `native.log`，见 [DEV049 T01](DEV049-T01-ACCEPTANCE.md) §2–3。 |
| 首异常与原码 | 12:30:48 进入 `building_worker` 后约 4 分 37 秒无状态；12:35:31 一次 `ready connected=True`，但 trail 无相应 IPC；12:36:29 首次明确 `connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`。第三轮 `cases={}`、`jobs=[]`，无建模提交。 |
| GUI / 锁 / unknown | 12:38 `parametric` hidden 且观测到 hung 窗口，`xtop` 可见且未报 hung；人工菜单/视图操作、截图、事故时 OS 锁持有和 unknown 快照**缺失**。13:48 trail 记录人工退出，不能推广为本次可重启授权。 |

**区分假说。** 运行期源码改动或 worker 替换干扰连接：需要事故前后 worker 文件 SHA、构建日志及进程创建时间，现缺；`f54cda8` 提交时间本身不足。旧 nmsd/IPC 端点残留：需要名字服务 PID 创建/父进程及同一时段 trail/worker 原生日志，现缺。GUI 阻塞导致通信不可用：需 12:30–12:36 的菜单操作、窗口/等待链或 dump，现只有 12:38 单点窗口状态。三者均未定位。

**完备度：部分。** 成功作业、时间线、Creo 两 PID 和失败映射可追溯；运行 worker 指纹、名字服务身份、失败窗口 GUI 与锁/unknown 均缺。`-4/exit 20` 是探测失败映射，不能证明 worker 崩溃，也不能与其他现场判同根。
