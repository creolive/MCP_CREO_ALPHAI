# MCP_CREO_MechDog 0.6.0 版本说明（发布候选）

日期：2026-10-26。**本文件描述合入 main 前的发布候选；远端 GitHub Release 尚不存在，
发布由控制者在合入实际主干提交后按 [RELEASING](development/RELEASING.md) 执行并核对。**
本次为 0.5.0 反馈整合计划第二批（可靠的装配重建管线，MINOR），基于 0.5.3。当前注册
公开工具 92 个（前一版本 0.5.3 为 91，本版新增
`creo_adopt_file`，实际可见清单以 `creo_capabilities` 为准）。

## 变更

- **FEAT-012/BUG-045 装配姿态矩阵输入与方向契约**（[FEAT-012](work-items/FEAT-012.md) /
  [BUG-045](work-items/BUG-045.md)）：`creo_assemble_component`、
  `creo_component_placement` 及 `creo_execute_plan` 新增唯一嵌套 3×3
  `rotation_matrix`（行向量、局部到父级，平移独立按毫米），与显式 Euler `rotation`
  互斥；有限实数、正交性与行列式 +1 以绝对容差 `1e-6` 校验，拒绝反射/缩放，容差内
  按原值使用、不转置不修正。旧 Euler 的 XYZ 依次主动旋转语义与角度符号不变。
- **FEAT-048 按路径及批量收养**（[FEAT-048](work-items/FEAT-048.md)）：新增公开工具
  `creo_adopt_file(file_path, mode="inspect"|"apply", evidence_token, idempotency_key)`，
  支持 1-20 个绝对路径批量收养；不要求也不改变当前窗口，源文件只读；inspect/apply
  两阶段、600 秒证据令牌、幂等键回放；每件独立 durable 提交与独立结果，普通拒绝
  继续、unknown 停止剩余并保留保护，不排队不重试；通道忙碌在昂贵选择/哈希前即
  拒绝且零接受状态遗留。仅健康、毫米、无外部依赖的零件/钣金件准入，含
  `fresh_retrieval`/`existing_resident` 显式来源 provenance。契约见
  [FILE_ADOPTION.md](FILE_ADOPTION.md)。
- **FEAT-008 官方装配重建管线配套**（[FEAT-008](work-items/FEAT-008.md)）：
  `examples/assembly_rebuild_pipeline.json` 与 `assembly_multicomponent_plan.json`
  官方示例、`docs/ASSEMBLY_REBUILD.md` 说明（毫米行向量 4×4 约定、source_snapshot
  语义与再生成方式、组件变更摘要、约束符号名）；含组件操作的作业结果新增有界
  `component_changes`（committed/rolled_back/no_effect/unknown_outcome/unavailable，
  按原生证据区分、不编造回滚）；`creo_list_components` 约束新增 `type_name`
  可读符号（与 `creo_inspect_session_assembly` 共用映射，未知码保留数字并标
  `unknown`）；旧装配保存检查点兼容比较生产 helper（新增展示符号不回填误报
  constraints_changed）；guard 实机入口终态确认释放语义强化。
- **版本与种子元数据**：`version.py` 0.6.0；两份种子 manifest 的
  `compatible_server_version` 同步为 0.6.0；9 个种子 PRT 原字节不变；
  种子安装包按 0.6.0 确定性重打包，`seeds.py` 的 `expected_digest` 更新为
  新包实测 SHA256（算法与校验逻辑不变）。

## 兼容与迁移

- 新增公开工具 `creo_adopt_file`（工具数 91→92）；既有工具入口与响应字段保持
  兼容。`rotation_matrix` 与 `rotation` 互斥，省略/None 保持旧默认行为。
- `component_changes`、`type_name` 及收养诊断字段均为新增结构，旧客户端可忽略。
- 计划内 remove+同 label 重新 assemble 仍被入口拒绝（既有生产契约，本版未扩展）；
  快照再生成须使用新的唯一 label，或拆两个独立作业；详见
  [ASSEMBLY_REBUILD.md](ASSEMBLY_REBUILD.md)。

## 验证与未测

- 开发者实机验收（本机 Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 匹配
  SDK+MSVC，受测源码 b86fa4a，证据与文件 SHA256 见
  [BATCH2-LIVE-ACCEPTANCE-2026-10-26.md](development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md)）：
  矩阵实机 38 父作业（37 成功 + 1 故意普通失败成功回滚）、11 组姿态基向量/已知点、
  Euler/矩阵互斥拒绝、4 次真实改变位姿 rev 36→40、32 次矩阵非法输入入口拒绝；
  批量收养两批真实夹具（2+1 成功、3+2 拒绝、0 unknown、rev 1、窗口/源字节不变、
  same-key 回放、依赖探针分支）；最终管线 10 父作业全成功（快照刷新新唯一 label，
  7200→7800、12384→12984、装配 rev 3→4）；独立全量 dev_check 748 项 0 失败 0 错误
  （b86 干净树）。以上均为开发者 MCP 实机证据，**不是 WorkBuddy 黑盒**。
- WorkBuddy 黑盒：用户已于 2026-10-26 明确取消本批 WorkBuddy 测试，**未执行**，
  不记为通过。
- 发布候选检查：0.6.0 元数据工作树（BASE beb8408、dirty=true）全量 dev_check
  748 项通过，0 失败 0 错误，受测源码 SHA256
  `f4dd3524c864ce6679bf02703bece60f4657c393781af0e555c83f122223e9e5`；
  SDK 构建成功，原生源码未变、复用匹配执行器。报告与完整日志见
  `build/release_candidate_0.6.0_20261026T005954Z/`。默认风格增量检查通过，
  存量 31 lint / 19 未格式化文件保持原样，不声明全库严格零问题。
- 未测范围（如实披露）：并发/通道忙交错、unknown 自然分支与断连故障注入、其他
  Creo 版本（9 无 SDK 未验收、10 未复验且非门槛）；modified/wrong-origin/token 超时
  等收养准入分支（仅离线）；嵌套子装配、FEAT-012 显式源件更新、第三批 FEAT-049/050、
  DEV-027 世代回收；FEAT-008 首批底板 holes/对称深度/平面引用。派生 AABB 非独立
  几何实测。

## 已知问题（随版披露）

- [BUG-078](work-items/BUG-078.md)（P1）：恢复 accept 路径 `ProMdlnameBackup` 稳定
  -1（损坏会话级，建模代码零改动）。
- [BUG-082](work-items/BUG-082.md)（P1）：在轴扇形 autodim 改角再生失败本体仍在
  （已带 `failed_features` 特征级诊断，coordinates 路径成功）。
- [BUG-058](work-items/BUG-058.md)/[BUG-063](work-items/BUG-063.md)/
  [BUG-064](work-items/BUG-064.md)：外部 -11、非原点轴阵列、surface 平面引用
  待复现。

## 附件（发布后由控制者核对）

- 源码包 `MCP_CREO_MechDog-0.6.0-source.zip` 与种子包
  `MCP_CREO_MechDog-0.6.0-seed-library.zip` 须从合入后的实际 main 提交生成；
  Release body 必须列出两包完整文件名与 64 位 SHA256 并回下载核对。
- 候选阶段种子包（本批源码生成，9 种子、24 文件）：
  `build/release_candidate_0.6.0_20261026T005954Z/MCP_CREO_MechDog-0.6.0-seed-library.zip`，
  SHA256 `e17563e66e24a1f879ecab91fff0b98ed7cfca94821ea103516e5e9bcc87166a`
  （最终发布附件从实际主干提交重打，必须与上述哈希及 `seeds.py` 一致）。
