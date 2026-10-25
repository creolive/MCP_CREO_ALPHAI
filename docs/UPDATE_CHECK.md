# 版本检查与手动升级（FEAT-020）

0.3.0 已加入只读工具 `creo_check_update(force=false)`，工具总数为 82。0.2.6 不包含此功能，需先手动升级一次。本项开发及 WorkBuddy 实测的范围与未测场景见 [本次证据](validation/FEAT-020.md)，发布检查见 [0.3.0 验收](validation/RELEASE-0.3.0.md)。

服务启动时在独立异步任务中查询 `wudahua/MCP_CREO_MechDog` 的公开 GitHub Release 列表，包含正式版和 Pre-release，排除草稿与未发布内容。分页结果按 SemVer 比较，接受 `v` 前缀和 `0.3.0-rc.1` 等候选格式；数字候选序号按数值排序，正式版高于同版本候选，构建元数据不改变优先级。历史 `v0.22` 和日期后缀等不规范标签不参与比较。当前版本高于公开版本时无需降级；没有有效候选时返回无法确认。

## 工具与字段

`creo_check_update` 返回更新对象。`creo_capabilities.update` 与 `creo_startup_status.update` 使用相同字段，读取内存缓存快照，立即返回，不等待 GitHub。原有启动状态、就绪判定及建模 revision 契约保持不变。

| 字段 | 契约 |
| --- | --- |
| `status` | `not_checked` 尚未开始；`checking` 正在检查；`update_available` 有更高版本；`up_to_date` 当前等于或高于最高可比较公开版本；`failed` 本次检查失败，明确表示**未取得最新版本信息**，不代表已是最新版本；`unknown` 当前版本或发布数据不可比较 |
| `current_version` | 当前运行的 `version.py.VERSION` |
| `latest_version` | 最高有效公开版本（去除 `v` 前缀）；没有可靠数据时为 null。失败后可保留上次成功结果，必须结合 `status/stale/error` 使用 |
| `is_prerelease` | 目标 Release 的 GitHub Pre-release 标记；无目标时为 null |
| `release_url` | 目标官方 GitHub Release 页面；无目标时为 null |
| `download_url` | 对应的 `MCP_CREO_MechDog-<version>-source.zip` 已上传官方附件；未识别到时使用 Release 页面；无目标时为 null |
| `checked_at` | 最近一次检查完成的 UTC ISO 8601 时间；尚未完成时为 null |
| `last_success_at` | 当前保留的目标上次成功取得的 UTC 时间；无可靠目标时为 null |
| `from_cache` | 快照或缓存命中为 true；本次新检查及共享正在进行的请求完成后为 false |
| `stale` | 已有目标超过成功缓存期限，或最近检查失败时为 true；无目标时为 false，不代表已确认最新版 |
| `message` / `error` | 可转述的说明及失败原因；不输出代理凭据、本机配置或原始网络异常；无错误时 `error=null` |

缓存仅存于当前服务进程内，重启后重新检查，不写配置、模型、任务或源码。成功缓存有效期为 24 小时，后台到期刷新；`force=true` 请求重新检查。失败及无有效数据后冷却 15 分钟，期间包括 `force=true` 在内均复用失败结果，避免高频重试。并发刷新共享同一请求；单个调用取消不取消共享请求；服务退出取消后台检查。

一次完整检查共用 5 秒异步网络预算，涵盖所有分页与响应读取，不是每页各等 5 秒。每页最多 100 条、4 MiB，最多 20 页；超过大小/分页上限返回失败，绝不使用截断列表宣称最新版。不携带 GitHub 凭据，不跟随重定向或任意分页外链；联网工具声明 `open_world_hint=true`。网络断开、超时、限流、无效 JSON 等只影响更新检查：失败返回 `status=failed`、`latest_version=null`（此前无成功检查时）并携带实际错误与"15 分钟后可重试"的重试规则，`message` 明确"未取得最新版本信息"；此前成功过的字段按过期缓存保留并置 `stale=true`，须结合 `status`/`error` 使用。任何失败都不写成"已是最新"，也不阻塞启动、能力查询或建模。

## 客户端提醒与升级

服务 instructions 引导客户端首次使用时调用更新工具；仅在 `status=update_available` 且 `stale=false` 时提醒当前版本、新版本、预发布标记和两个链接。同一客户端会话对同一 `latest_version` 只提醒一次，此去重由客户端执行。MCP 提供数据与指引，实际展示由客户端决定，不保证弹窗。

已安装此功能后，后续更高的公开版本才会被检查到。**不包含此功能的旧安装必须先手动升级一次**，无法主动提示首次升级。

等待建模任务完成，停止 MCP 服务，备份并保留 `config.json`、`client-config.json`、模型、任务记录及已注册种子信息；下载目标源码并按 [安装说明](INSTALL.md) 使用目标 Creo 对应的 SDK 重新运行 `setup.ps1`，然后重启 MCP。核对 `creo_capabilities` 的版本、工具列表和 runtime 指纹，再检查启动就绪并创建小零件验证保存重载。升级方法也适用于 [迁移场景](MIGRATION.md)。更新检查工具不下载或安装附件、不关闭 Creo、不强制停止建模。

开发者回归入口为 `tools/test_update_check.py`；`--network-failure` 是开发者受控故障注入，不是实际操作系统断网。WorkBuddy 只调用公开 MCP 工具，测试约定见 [开发入口](DEVELOPMENT.md#workbuddy-测试约定)，不能据此推断内部缓存时长或重试机制。

实现依据：[GitHub Release 列表 API](https://docs.github.com/en/rest/releases/releases#list-releases)、[SemVer 2.0.0](https://semver.org/lang/zh-CN/)。
