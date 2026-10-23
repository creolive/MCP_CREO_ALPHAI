# BUG-078 根因定位与恢复 accept 路径实机闭环记录

日期：2026-10-22（下午批次）。开发者侧实机验证，接续 [BUG-077 恢复链路记录](BUG077-RECOVERY-2026-10-22.md) 第 4/5 节发现的 BUG-078。

## 环境

- Windows x64 / Creo 12.4.0.0（release_numeric 44）/ E 盘 dev 服务 `MCP_CREO_MechDog_dev` 0.5.0
- 验证会话：2026-10-22 12:48 本地启动（协调器 attempt 28），会话指纹 `13822995897450650751`；trail `build/creo_session/trail.txt.49`
- 夹具脚本：`build/bug078/repro.py`（悬挂构造+reconcile inspect/apply+同键重放+恢复后编辑）与 `build/bug078/baseline.py`（创建+编辑对照），各自拒绝重复执行；报告 JSON 留存于同目录

## 1. 历史证据核对结论（步骤 1）

对 2026-10-22 上午会话（trail `trail.txt.45`，07:49 本地启动、指纹 `6265530161255170365`）内 7 次 `ProMdlnameBackup=-1`（4 次恢复 accept + 3 次编辑偶发）与全部成功对照逐阶段比对：

- 两条 accept 路径 Backup 前的状态：accept_live 为"会话内遗留 dirty 现场（ProMdlInit 找到即用）"；accept_saved 为"erase 会话 live→ProMdlFiletypeLoad source→Regenerate→verify"。与卡片登记一致，两路径构造不同，不能预先合并归因。
- 失败编辑（`9506cdce`/`dc9537e2`/`446a3381`）与成功编辑（`01061826`/`67c1c7d7`/`fd3acfb6`/`f169fc21` 等）的 native PHASE 序列完全同构（会话找到→set_sketch_dimensions→regenerate→verify→Backup），同一会话内一成一败，日志层无差异。
- 失败编辑的 rollback 段（erase→load checkpoint→verify）报 `Saved dimension value changed`，且现场保持 dirty——即该会话内 erase→load 后校验看到的是旧内存对象，佐证会话内部状态异常（非本服务代码路径缺陷）。

## 2. 决定性证据：trail 对照（根因）

- **事故会话 `trail.txt.45`：共 70 条 `dbg_err_crash() - continuing from serious error (ORDER_DEBUG)`**（5 组×14 条：08:01:11、08:05:59、08:08:21、08:09:19、08:13:22），全部紧跟在**成功**保存（`save_and_reload` 的 Backup=0）之后；该会话 7 次 Backup=-1 之外另有 13 次保存成功，即保存子系统整体带伤运行。该会话即 BUG-077 第 0 节记录的"无人桌面期事故后协调器重启、复用 07:14 孤儿 nmsd"的会话。
- **健康会话对照**：`trail.txt.46`（0.4.7 发布回归，test_general 7/7）与 `trail.txt.49`（本次验证会话）dbg_err_crash 均为 0；本次验证会话 52 次成功保存零内部错误。
- 结论：**BUG-078 的全部失败集中在一个内部状态已损坏的 Creo 会话**；`ProMdlnameBackup` 返回 `PRO_TK_GENERAL_ERROR(-1)` 与 rollback 的 dimension 异常均为该损坏的外部表现。MCP 侧建模/恢复序列（含此前最大嫌疑的 erase→load→Backup 邻接）无罪——PTC 头文件确认 Backup 等价于 Creo"文件→备份"命令，损坏会话内该命令失败属会话级故障；网络检索该签名无公开已知 API 缺陷（见下方来源）。
- 因此"根据对照修最小根因"落不到 native 序列改动：增加延迟、重试、换保存接口均被对照排除，本批次对建模/恢复代码**零行为改动**。

## 3. 独立夹具复现与专项回归（步骤 2/4/7）

当前健康会话内，两种 accept 各用独立夹具（delayed 悬挂：提交编辑 1.5s 后仅杀 Python runner，执行器孤儿自然完成保存 `.prt.3`）连续三轮，全部通过：

| 轮次 | 动作 | 恢复作业 | 结果 | revision | saved_file_reloaded_and_verified |
| --- | --- | --- | --- | --- | --- |
| bug078_sv1 | accept_saved | `e72709b0…` | succeeded | 1→2（仅一次） | true（`.prt.4`） |
| bug078_sv2 | accept_saved | `07b80d34…` | succeeded | 1→2 | true |
| bug078_sv3 | accept_saved | （见 repro 报告） | succeeded | 1→2 | true |
| bug078_lv1 | accept_live | `98f2da4b…` | succeeded | 1→2 | true |
| bug078_lv2 | accept_live | （见 repro 报告） | succeeded | 1→2 | true |
| bug078_lv3 | accept_live | （见 repro 报告） | succeeded | 1→2 | true |

- **同键重放**（sv2/sv3/lv2/lv3）：相同 idempotency_key 重新 apply 返回原恢复作业 job_id，不产生新作业。
- **恢复后继续编辑**（sv2/sv3/lv2/lv3）：恢复提交后 set_sketch_dimensions(24) 成功、保存重载 verified、revision 再推进一档。
- 失败保护语义未被触碰：本批次未修改任何保护/恢复代码；restore_baseline、abandon_new、活动 owner 拒绝与证据过期路径维持 0.4.7 已验收行为（[BUG-077 恢复链路记录](BUG077-RECOVERY-2026-10-22.md) 第 1-3 节），未在本批次重测矩阵全量（按本任务范围不关闭完整恢复矩阵）。

## 4. 正常路径对照与"偶发 -1"子项（步骤 4）

- `baseline.py`：10 个隔离模型 ×（创建 d16 → 编辑 d20 → 编辑 d24）= 30 作业全部 succeeded、`saved_file_reloaded_and_verified=true`、toolkit_code=0；含与失败组同构的"创建后立即编辑"模式。
- 编辑路径偶发 -1 本轮**未复现**：连续 10 组对照（30 次保存）零失败。按任务要求保留为 BUG-078 子项：3 个历史失败样本已归因于同一损坏会话（trail 佐证），健康会话连续通过不构成其根因在健康环境已解决的证明，仅在损坏会话场景下被复现路径封闭。
- 完整性验证：单元测试 544 全过（`unittest discover -s tests`）；`tools/dev_check.py` success=true（无新增语言问题；本批次未改动源码）。

## 5. 三个挂起现场核对（步骤 5，收尾动作待操作者选择）

当前会话对三个旧现场逐一 live inspect（只读，未 apply；旧会话 live 已随会话消失）：

| 模型 | 状态 | recovery_pending | baseline 核验 | live | owners | 可用动作 |
| --- | --- | --- | --- | --- | --- | --- |
| `de6f0bb5…` wb047_rec_r1 | failed rev1 | `3a219968…`（失败 accept_live） | `.prt.2` SHA256 verified | not loaded | stopped | **仅 restore_baseline** |
| `bebe7e2b…` wb047_rec_probe | failed rev2 | `ee170974…`（失败 accept_live） | `.prt.3` SHA256 verified | not loaded | stopped | **仅 restore_baseline** |
| `57294ff8…` wb047_rec_r1b | failed rev1 | null（已有一次 restore_baseline 解决记录） | `.prt.2` SHA256 verified | not loaded | stopped | **仅 restore_baseline** |

- 三者 accept_live 均因 live not loaded 不可用、accept_saved 因无 candidate 不可用；dirty 现场（d17/d19/d20）的内存修改随损坏会话结束丢失，磁盘无对应保存件。
- 唯一收尾路径为 restore_baseline（live 缺失仍可用，先例 `e5009037` 第二轮）：erase（无 live）→load 基线→verify→display→登记恢复，原始异常历史保留。**等待操作者明确选择后执行**；证据不足时继续保护。

## 6. 未验证与保留范围

- 损坏会话的再制造（复用孤儿 nmsd 的无人桌面期启动）未在本批次实施；nmsd 生命周期治理按卡片"不包含"保持范围外。
- 编辑路径偶发 -1 保留为子项（第 4 节）；完整恢复矩阵与 BUG-074 跨启动身份验证不在本任务范围。
- 触发 Backup -1 的会话级损坏无 Toolkit 可观测前兆（连接探测正常、regenerate 正常），暂不加检测代码。

## 参考

- [ProToolkitErrors.h（PTC 官方错误码表）](https://support.ptc.com/help/creo_toolkit/protoolkit_plus/usascii/creo_toolkit/api/dita/protoolkiterrors_h.html)
- [PTC 社区：Creo fatal error 讨论（trail/traceback 诊断建议）](https://community.ptc.com/3d-part-assembly-design-327/what-are-the-possible-reasons-for-fatal-error-working-with-creo-37738)
