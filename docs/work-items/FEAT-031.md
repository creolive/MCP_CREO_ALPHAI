# FEAT-031：装配交付打包导出（自包含快照）

日期：2026-10-16。类型：能力。优先级：P2。状态：验收中（两件装配导出与隔离回导已通过；嵌套/外部引用仍开放）。目标版本：未排期。

来源：[0.3.2 钣金增料与四壁折边验收报告](../validation/feedback-0.3.2/2026-10-16_CREO_0.3.2_钣金增料与四壁折边仍未修复验收报告.md) P11；[补录](../validation/FEEDBACK-0.3.2.md)。关联 FEAT-012、FEAT-023、BUG-020；与 BUG-020 的导出副产物清理边界分别验收。

## 问题或目标

外部报告指出：`creo_export_model` 目前仅支持 step/stl/iges/jpeg/pdf，装配交付需要人工携带会话生成的 `C_*.prt` 快照，否则对方无法重建装配引用。报告建议增加 `native_bundle`（.asm 与引用件一起导出），或在文档中明确"交付装配必须携带快照"的边界。

目标：让装配交付可以一次取得自包含的产物集合（装配 + 其引用的零件快照），并让调用方对产物清单、缺失引用和目录结构可预期；若经核实不适合一次打包，则把交付边界写清并给出可操作的替代步骤。

范围待细化：产物清单与命名、目录结构与覆盖策略、外部/缺失/只读引用的处理、与现有 step/stl/iges/jpeg/pdf 及 `out/` 交付习惯的兼容、输出体量与分页预算、本机绝对路径泄露、失败时的检查点与已产出文件回收。

不改变现有导出工具的默认行为；不承诺跨机自动重建引用关系，不代替用户确认 Creo 许可与文件权限。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| 本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK | 单层与嵌套装配（含外部/缺失引用件）一次打包导出 | 产物清单与实际文件一致、装配可被 Creo 打开且引用解析正确、缺失引用明确报出而非静默省略；保存重载 true，revision 不变 |
| 本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK | 既有 step/stl/iges/jpeg/pdf 回归 | 原有导出格式与返回契约不受影响；新增产物不遗留自有临时文件 |
| Windows / Python | `tools/dev_check.py` 与针对性回归 | 无新增检查问题；输出体量在预算内并保留产物/详情入口 |

其他环境按收到的反馈补录；证据标明实际环境与源码指纹，不用工具数量代替正向覆盖。

## 实现与证据

本次只登记来源与候选范围，未设计接口、未实现或测试，也未确认现有导出实现能否复用装配遍历能力。报告中的建议方案（`native_bundle`）作为来源记录，不作为已选方案。

## DEV-051 T13 离线阶段（2026-10-29）

新增显式 `native_bundle` 只读导出格式：在本次 job 的独立目录从所属模型 `output` 内的原生版本快照收集已知装配引用，写相对路径、SHA256 和缺失状态 manifest。原有五种导出格式和默认 `step` 不变。离线夹具与匹配 SDK 构建通过；真实装配新目录打开、引用解析、嵌套遍历完整性、源件实际哈希、revision 与重载尚未连接 Creo 验收。详见 [T13 验收卡](../development/DEV051-T13-ACCEPTANCE.md)。状态保持实现待原生验收。

## 2026-10-29 实机：两件装配打包失败（组件身份无法解析）

`tools/test_assembly_bundle.py --live --confirm-session-usable`，报告 `build/assembly_bundle/20261029T231622_7cbf542e/report.json`（SHA256 `8a50e8b0…b00105`）：

- 装配与组件记录正常（`part_alpha`/`part_beta`，`feature_id` 40/43，变换矩阵与标签正确），导出 job `0856a754151544f08bbd489d7d7398be` 成功。
- 但 `native_bundle.complete=false`、`files=1`、`missing=2`，清单两条 `{name:null,status:missing,reason:unresolved_identity}`；包里只有 `.asm`，两个 `c_<token>_<n>.prt` 源件没有进包。
- 原因：磁盘副本名是 `c_fec6a06a17f54953_0.prt.1`（与装配 job 前 16 位一致，符合契约），而巡检 `model_name` 返回 `\u25a9C_FEC6A06A17F549530001`（前导 U+25A9、全大写、后缀 `0001` 而非 `_0`），`_references` 的 `[a-z][a-z0-9_]{0,30}` 校验失败。
- 回导未完成：同名装配仍在会话中，`creo_open_file` 返回 `SESSION_NAME_CONFLICT`（`open_file_session_check`、`toolkit_code=-1`）；未擅自擦除会话模型。
- 本轮**未**放宽校验或猜测名字映射（会把不完整包伪装成自包含），也未改原生名称读取。修复方向：让巡检名与磁盘文件名同源（核对 `ProMdlNameGet` 缓冲区与前导 U+25A9 是否未初始化内存），再补"擦除会话模型 + 新目录打开"的回导验收。本条仍开放。

## DEV-051 T13 离线阶段（2026-10-30）：身份链路定因与最小修复

定因（带行号）：磁盘名来自 `native/advanced.cpp` `insert_component` 自己生成的复制名 `c_<job16>_<n>`（`ProMdlnameCopy` → `ProMdlnameBackup` 逐字落盘）；巡检名来自另一条独立读取 `ProMdlNameGet`（自 Creo 3 废弃）+ 未初始化 `ProName`，两者不同源。该废弃调用即本仓库 BUG-070（`native/worker.cpp`）已定因并修过的同一缺陷，`assembly_inspection`/`constraint_reference` 未跟上。全量取样 1483 个 `model_name` 无一正常，形状恒为 `U+25A9` + 名字形字符串；其内部成因离线无法证实，记**未定因**，未据此实现任何字符串映射。

最小修复：复制名在生成时登记进持久化别名记录（`snapshot_name`），打包按 `feature_id` 取回该字符串逐字符精确定位自有源件；名称读取改用 `ProMdlMdlnameGet` + 清零缓冲；补异常身份/重复 occurrence/缺件/只读源/未知嵌套闭包回归，完整性不足一律 `complete=false`；驱动改为残包立即记失败且不回导。离线 9/9、全量 1482/1482 通过，`bridge.py build` 通过。实机回导待验（新目录打开、组件/位姿/体积/哈希、源 revision 不变、不得擦用户模型）。详见 [T13 验收卡](../development/DEV051-T13-ACCEPTANCE.md)。状态保持离线实现完成、实机未验。

## 2026-10-31 当前状态补记

[T13 实机卡末节](../development/DEV051-T13-ACCEPTANCE.md)记录两段式实机：导出 bundle `complete=true`、3 文件、两组件位姿与隔离会话新目录回导通过。上文“未重跑”属于 2026-10-30 离线阶段时点；同会话受管模型不可擦且装配检索要求空会话。嵌套闭包、外部/缺失引用实机仍开放，不能外推跨机完整支持。
