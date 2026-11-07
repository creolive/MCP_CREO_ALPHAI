# DEV-071：0.16.0 三件反馈的离线修复范围

2026-11-07。用户明确要求直接实施可离线代码；另一 agent 正占用 Creo，本轮不连接、不构建、不重启服务。基线 main `191c05f` / 0.17.1。

## 目标与已交付去重

读取 Downloads/chatgpt 三件原报告，逐字节归档后接续现有条目。0.16.1 已交付偏置计量保护、板厚几何兜底、清理归因；0.17.0 已交付首壁 origin 与折边 edge_geometry；0.17.1 已交付 BUG-115 准入和 stale revision 文案，均不重复开发。历史报告的受测环境为外部 Creo 10 / 0.16.0，不外推为当前版本实测。

## 方案与决定

选择保留几何求解和默认容差，补齐公开证据与可配置网络检查。直接改线弧尺寸策略缺完整 P05 operations/native.log 与实机证据；放宽保真门或新增 raw/none 会改变可编辑尺寸语义，均不纳入。本轮只实现能由离线测试判断的行为，并将原生新回执标注待 SDK 构建和 Creo 验收。

1. FEAT-014/023：把 aliases 内实际存在的 miter_cuts、adjacent_bend_ends_allowed 投影到对应折边操作；兼容历史已落盘 aliases 的查询；compact/full/sections 可见，缺证据不补成功。偏置文案统一为会产生实体体积的 offset wall，源 quilt id 不冒充新结果 quilt，不推导任意曲面的距离。
2. FEAT-020：保留默认 5 秒总网络预算，允许通过环境变量 MECHDOG_UPDATE_TIMEOUT_SECONDS 配置 1..30 秒；非法值安全回退 5。force 显式绕过失败/unknown 冷却，普通读取保留 15 分钟冷却，并发共享和取消隔离不变。回执给实际预算、缓存年龄和下次自动检查时间；失败无成功数据仍不能称已是最新，不造离线 GitHub 最新版本。
3. FEAT-010/BUG-049/051：复用 solver.requested/used，补 auto 选择原因及 solve/autodim/regenerate 各实际返回码，成功和失败均可见。不把初次 Solve=-1 误判最终失败；不变更 autodim 默认告警契约，显式 geometry_tolerance_mm 继续硬拒绝。失败特征已有状态证据保留，ProFeatureStatus 不冒充 ProError。

## 验证与非目标

新回归先失败后通过；纯 Python、协议投影与静态原生契约检查离线执行。环境和生成报告仅在独立工作树；不修改 E 盘 checkout、部署配置、已有 jobs/models、执行器和 Toolkit 锁。无实际 Creo 几何/保存重载证据；53mm 原案、frame 求解、圆角锚点选择、曲面 merge/loft、真实断流和 I032 内核拒绝保持待验证/原任务，不以本批关闭。

本分支不改版本、不合 main、不推送或发布；合入时按仓库要求单独完成新版本发布。
