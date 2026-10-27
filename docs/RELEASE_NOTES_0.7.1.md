# MCP_CREO_MechDog 0.7.1 版本说明

日期：2026-10-27。本版为 DEV-048 反馈修复批次（PATCH），基于 0.7.0。开发、实机与安装证据见
[发布验收记录](validation/RELEASE-0.7.1.md)，主干提交、正式附件与完整 SHA256 见
[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.1)。
当前注册公开工具 94 个，与 0.7.0 相同，本版不新增工具，实际可见清单以 `creo_capabilities` 为准。

## 变更

- **T01 收养侧车完整性与回退（BUG-076 本批子项）**：侧车复用判定由"同名即复用"改为
  「自有普通文件 + 大小 + 完整 SHA256」三者同时匹配，符号链接与目录一律不当作可复用侧车；
  冲突时保留原文件、改以完整摘要命名发布，两个名字都被占用则报 `sidecar_publish_failed`。
  发布改为临时文件写入→校验→原子链接，不再用 `os.replace` 覆盖他人文件；原生侧改用
  `MoveFileExW`（不带替换语义），失败时重新核验目标实际身份并记 `native_sidecar_publish_failed`。
  `live` 与 `verified` 两阶段各自独立收尾，前者失败不再静默跳过后者。新增有界诊断
  `inspection_warnings`：固定四个原因码、按 `(stage, reason_code)` 去重、每结果最多 4 条、
  message 最长 256 字节且不截断字符，贯通收养、恢复、批量每项与 `creo_get_job` 的 compact/full。
- **T02 拒绝后的引用生命周期**：窗口收养拒绝清理本次自有 staging 后，只移除确已无法校验的
  `inspection_ref` 并记 `inspection_ref_removed_after_refusal` + `fallback_status=not_attempted`，
  仍可校验的证据（含路径收养）保持不动；拒绝前先补算并保留已知单位/体积摘要，使
  `refusal_details.actual_units_known` 不再把已知单位报成未知。清理失败如实记录
  `staging_cleanup.state=failed` 与原始错误，不声称文件已消失。该字段只写 job.json/预检 manifest，
  不进入公开 MCP 响应。批量中引用不可读按已知拒绝处理，不产生半登记或额外 revision；
  中间结果不确定时后项 `not_attempted` 且保护不释放。同时恢复 0.7.0 `split()` 的语义：
  原生已给出可验证引用时仍补齐 `inspection_summary`（T01 收尾曾漏掉这一步）。
- **T03 工作卡与发布检查回填**：DEV-047 按实际 Release 与标签回填"已随 0.7.0 交付"并移入完成
  档案；BUG-079/081/082 分别回填 0.5.1/0.5.3/0.6.1 的交付与仍开放范围；核对主台账唯一 ID
  统计（120 行/120 唯一，完成档案 56，合计 176）；发布清单扩为逐 ID 五处核对（候选态与
  发布后各一次）并新增"相对上一正式包"的第三方原字节、回调指纹、DLL 身份与注册路径核对。
- **T04 Right 面 ±Z 定向证据**：新增 `tools/test_dev048_plane_frame.py` 与配套离线用例，
  真机在 Creo 12.4.0.0 上通过 Right 面 `u_axis=[0,0,1]`、`[0,0,-1]` 两例：实际帧回显
  `u`、`v=N×U`、体积 800 mm³、八点 AABB 与重心、保存重载 `true`、`revision=2`；
  平行法向 `[1,0,0]` 一例由原生边界拒绝并真实回滚（`revision` 1→1、别名不变）。
  驱动默认离线，实机路径必须同时给出 `--live` 与 `--confirm-session-usable` 才可能连接。

## 未测范围

- WorkBuddy 黑盒按用户 2026-10-26 决定取消，本版未执行。
- 外部 Creo 9/10 未复测；本机无 Creo 9 SDK，CREO 9 只保留支持声明。
- T04 只覆盖 Right 面 ±Z 的定向补证，未重跑 DEV-047 完整历史矩阵（`native_acceptance=partial`）。
- 未做真实 worker 超时/断连注入、真实文件锁下的清理失败注入、未知单位实机诱导。
- 倾斜面、多轮廓、纯 Z `u_axis` 的历史现象（0.6.0 报告 R4 项）不在本版验证范围。

## 升级说明

本版不改变公开工具数量与既有工具签名，`inspection_warnings` 为新增可缺省字段，旧调用方无需改动。
`staging_cleanup` 只出现在 job.json/预检 manifest，不在公开响应中。侧车文件复用变得更严格：
以前靠同名复用、实际内容不同的场景现在会改为新建侧车文件，不会覆盖既有文件。