# MCP_CREO_MechDog 0.7.2 版本说明

日期：2026-10-28。本版为 DEV-049（0.6.1 两份反馈后续 PATCH）批次交付，基于 0.7.1。开发、实机与安装证据见
[发布验收记录](validation/RELEASE-0.7.2.md)，主干提交、正式附件与完整 SHA256 见
[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.2)。
当前注册公开工具 94 个，与 0.7.1 相同，本版不新增工具，实际可见清单以 `creo_capabilities` 为准。

## 变更

- **DEV-049 T00—T07 反馈归档与文档基线**：两份 0.6.1 反馈原件逐字节归档
  （`docs/validation/feedback-0.6.1-2026-10-27/`，manifest 与 32 章节 + 5 回复请求映射齐全）；
  T01 断连事故离线核对结论为**证据不足、根因未定**（BUG-085）；T05 多环/预览查缺与替代夹具
  离线就绪（原输入缺失，实机差项未跑）；T07 完成台账与文档一致性收口。本版同时覆盖 0.7.1
  发布后的主干回填提交 `d2e37b0`（GAP-1/GAP-2：该提交不属于 0.7.1 附件，其台账/文档差异由本版统一覆盖）。
- **DEV-050 `dev_check` 单元超时修复**：`tools/dev_check.py` 单元阶段原 300 秒硬超时（完整套件实测
  347 秒被误判 `timed_out`）改为 `--unit-timeout-seconds`，默认 900 秒，非法值参数阶段拒绝。
  本版全量统一检查实跑 1128 项单元测试通过，无 timed_out。
- **BUG-086 安装误报修复（含 T08 批内补充）**：Windows PowerShell 5.1 在 stderr 重定向下把外部命令的
  通知性 stderr 转成终止错误，导致底层成功却报 `INSTALL_INCOMPLETE`。T03 先封装两个 pip 步骤；
  T08 安装验证发现同类残留在其余非 pip 外部调用，随本批补充修复：`setup.ps1` 的全部 8 处外部调用
  （pip 依赖、pip editable、vswhere 工具链探测、Python 版本探测、venv 创建、导入检查、种子安装、
  原生构建）统一经 `Invoke-ExternalStep` 按真实退出码判定——局部容错 stderr ErrorRecord、调用前清除
  旧退出码、启动失败/无退出码/非零一律失败、finally 恢复错误偏好，不吞 stderr、不匹配特定文本。
  新目录安装验证以 `2> err.log` 重定向形式完整通过（pip 与非 pip 阶段均无误报）。
- **BUG-087 草图框架修复与原斜槽六例**：按 `datum_plane` ID 引用 + 自定义面内 `u_axis` 时第二参照
  选到与 orient 参照同法向的重复基准面，截面仅剩一条参考线导致 `ProSectionSolve` 全模式 -1；
  修复为候选基准面与 orient 面法向不平行否则跳过（`native/generic.cpp`），不改 `datum_feature`
  标签路径与轴对齐 `u_axis`。修复后 DEV-049 T04 原斜槽六例（autodim×3 + coordinates×3，R20/54°/4×6）
  **6/6 实机通过**（去料体积 238.390260127791／476.780520255582 mm³ 基准、实际帧 v=n×u、参考线、
  revision、保存重载全满足），Right 面 ±Z 回归无退化。
- **T06 种子矩阵 15+2 与 FEAT-030**：FEAT-030 九种子矩阵 15 正例 + 2 负例实机全部通过（单一受测源码），
  种子清单九项 SHA256 核对一致；FEAT-030 转「已验收（未收口）」，生产来源/外部环境加载证据继续开放。
- **种子与版本随版**：两份 `seed_manifest.json` 的 `compatible_server_version` 同步 0.7.2，9 个种子 PRT
  原字节不变；种子包按 0.7.2 确定性重建（两次构建 SHA256 一致），`seeds.py` `expected_digest` 同步。

## 未测范围

- 外部 Creo 9/10 未复测（本机无 Creo 9 SDK，Creo 9 仅保留支持声明）；BUG-085 断连事故根因未定，
  13 正例 + 2 负例编辑闭环缺口由该卡继续承载。
- BUG-066 预览失真待复现（无原模型与原始图像）；T05 多环/预览差项实机未执行（原输入缺失）。
- WorkBuddy 黑盒按用户 2026-10-26 决定未执行；DEV-047 完整历史矩阵未重跑。
- 安装验证未连接 Toolkit/Creo，未注册第二套客户端；Creo 9 实机编译与建模运行时仍未验收。
- BUG-001 恢复条件与 unknown 保护保持，未做新的 Toolkit 连接或故障注入。

## 升级说明

本版不改变公开工具数量与既有工具签名，无 MCP 接口变更。`setup.ps1` 对失败的判定更严格：外部命令
非零退出或无法启动一律失败（含 vswhere 工具链探测），stderr 通知不再误报；建议升级后在新目录重跑
`setup.ps1` 取得安装证据。原生侧仅 `native/generic.cpp` 草图第二参照选择逻辑变化，升级需重新编译
执行器（`bridge.py build`）并重启 MCP 服务；`protk.dat`/注册表/安装路径未变更。