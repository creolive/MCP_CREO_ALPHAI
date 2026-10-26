# MCP_CREO_MechDog 0.6.1 版本说明

日期：2026-10-26。BUG-082 草图就地编辑修复，PATCH，基于 0.6.0，公开工具仍为 92 个。
验收见[发布记录](validation/RELEASE-0.6.1.md)，主干提交、正式附件与完整 SHA256 见
[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.6.1)。

## 变更

- **BUG-082**：主平面、受坐标模式支持实体的显式 `autodim` 就地编辑，复用
  BUG-079 已有坐标尺寸升级路由，修复在轴扇形改角后草图与下游回转再生失败。
  响应 solver 明确记录 `requested="autodim"`、`used="coordinates"`；创建路径和显式
  coordinates 语义不变。原生诊断增加四阶段截面尺寸/约束/实体及再生返回码。
  根因与修复范围见[根因记录](development/BUG082-AUTODIM-ROOT-CAUSE.md)。
- **编辑验收驱动**：失败前后记录 revision、文件实字节 SHA256、inspection/aliases
  摘要及特征身份、pending/recovery；旧缺陷成功回归与独立非法开环失败夹具分开，
  验证干净回滚和 `failed_features`，不依赖保留旧缺陷来证明失败保护。
- **FEAT-030**：种子回归驱动按现有 summary/受控 ref 读取真实证据，以 manifest
  驱动九种子及附加场景。four 类种子的 SECTION 平面不驱动 Blend，改为编辑实际草图
  尺寸；驱动适配完成不等于全部矩阵通过。种子 PRT 字节、来源与 available 语义不变。
- 版本及两份 manifest 同步 0.6.1；种子包确定性重打包并同步安装期望 SHA256。
  当前台账与工作卡同步已修复范围和剩余验收，保留历史证据原件。

## 验证与边界

- 修复批 Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 SDK、MSVC：
  编辑专项 **16/16** 通过，覆盖 BUG-079/062、legacy、reorder、主平面 autodim
  改角/改半径及回程；成功路径保存擦除重载，非法开环失败回滚通过。原报告及本次
  源码一致性核对见发布记录；该证据取得时服务元数据仍为 0.6.0。
- 种子 smoke 两种子通过；九种子矩阵 `matrix_five_smooth` 完整通过、
  `matrix_four_smooth` 创建成功。随后 worker exit 20、IPC 不可读，两次 coordinator
  重试超时。**matrix_four_smooth 的编辑闭环、其后 13 个场景及 2 个负例未完成验收**，空汇总不代表通过，作业原件保留。
- 本轮发布不连接 Toolkit、不操作 Creo、不清除保护。会话断连根因未确定，需用户
  人工检查并按 BUG-001 纪律满足恢复条件后，才补剩余实机验证。
- WorkBuddy 本批未执行；外部 Creo 9 未复测（本机无 Creo 9 SDK，实机编译与运行时
  均未验收）；Creo 10 未独立复测且不作为门槛。本机通过不外推到其他版本。
- 非主平面、含不受坐标模式支持实体的 autodim 编辑保持既有边界；外部报告的
  coordinates/改半径失败未在本机复现。半圆/球体贴轴创建基线、种子生产版本可追溯
  与重生成、BUG-034 的 Creo 9 加载 -16 及 BUG-078 恢复问题继续开放。
- 完整开发检查、SDK 构建及新目录安装结果、源码指纹和附件核对见发布记录。

## 升级

在使用者确认会话可操作、任务已结束后，停止客户端 MCP 服务，保留本机配置、
models/jobs，更新源码并重跑 setup.ps1。重启客户端确认版本 0.6.1；遇既有断连先
人工检查 Creo，不把升级或重复连接当作恢复手段。本次无新增公开工具或输入迁移。
