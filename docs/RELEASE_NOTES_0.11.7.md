# MCP_CREO_MechDog 0.11.7 版本说明

- 类型：PATCH，诊断可观测性与开发者判定口径修正；公开工具仍 **95 个**，无新增工具，无不兼容接口变更。
- 条目：[BUG-111](work-items/BUG-111.md)（`keep_original` 第 5 副本失败的定因与诊断）、[BUG-108](work-items/BUG-108.md) 与 [BUG-110](work-items/BUG-110.md)（实机补证轮，仍开放）；实施计划见 [R13 后续定因与实机补证](superpowers/plans/2026-11-03-r13-followup-bug111-108-110.md)，验收摘要见 [R13-FOLLOWUP-ACCEPTANCE-2026-11-03](development/R13-FOLLOWUP-ACCEPTANCE-2026-11-03.md)。
- 版本入口：[version.py](../version.py)；配套种子包 `MCP_CREO_MechDog-0.11.7-seed-library.zip`。
- 面向调用方：**建模行为不变**，本版只增加失败诊断字段与文档结论；无需改请求参数。

## 本版内容

- **第 5 个 `keep_original` 副本失败已定因（BUG-111）**：本机 Creo 12.4.0.0 实机对照（C0—C6 七个独立底板）显示，4 个独立模型在"已存在 45/90/135/180 副本后追加 −135"这一步同型失败于 index 4；而把 −135 放在首位时 5 个副本**全部成功**、拆成 4+3 两批仍在批 B 首个 op 失败。结论：**失败不跟随位置或角度，而跟随"体已含多副本 + 该角度"的组合**——`keep_original` 复制的是**整个当前体**（同一 body 内累积凸块，特征数 +1/副本），追加副本与既有凸块重合／交叠时触发再生失败。据此**撤销** 0.11.6 起的"单批 ≤4 个副本、下一批重新引用当前 body"变通建议（拆批实测无效）。本版**不做行为修复**，只交付诊断与能力边界。
- **失败回执带选集证据（BUG-111，诊断增强）**：`geometry_transform` 失败回执的 `failed_transform` 新增有界 `selection` 块——`requested_body_ids`（请求的 body id）、`selected_surface_count`（实际被选面数）、`model_counts_at_start`（op 开始时的 bodies/features/surfaces 计数，执行器上下文不可用时记 -1，不造数）。实机对照中失败 op 的 `selected_surface_count=26`（整个累积体），而新建底板只有 6 面，**"复制的是整个当前体"由此在失败回执里直接可见**。原生日志另增只读 `TRANSFORM_SELECTION` 行。
- **重放判据修正（BUG-110，判定逻辑）**：同键重放的判定不再由"key 相同"推断结果，而按实际证据判定——**确认出现二次事务或结果变化判 fail，只有缺少证据才判 unverified**；配套新增 3 项专项回归。
- **副本夹具判定口径与命令增强（开发者工具，不影响公开工具）**：`tools/test_geometry_transform_copies.py` 的判定改按**特征增量 + 单 body 语义**（副本不新增 body），新增 `--cases` 子集过滤与 `--model-suffix`（重跑避让会话中已存在模型名）；`tests/unit/test_geometry_transform_copies_driver.py` 增至 7 项，`tests/unit/test_assembly_ack_failure_driver.py` 增至 10 项。

## 验证与边界

- 离线：全量 **2268 项单测 0 失败/0 错误**（起点 2264，新增 4 项）、`tools/dev_check.py --work-item BUG-111-BUG-108-BUG-110-followup` `success=true`（风格基线未改）、`bridge.py build` exit 0（执行器 13 328 384 B / SHA256 `7071b947…`，源码指纹 `cc2aa38d…`）。
- 本机 **Creo 12.4.0.0 实机（2026-11-03，用户授权会话）**：C0—C6 七个独立底板全部成档（`t1_reproduce.json`）——C0 225° 提交前拒绝且单个 −135° 成功；C1 四副本成功（bbox 出现未请求方向，证明复制整个当前体）；C2/C3/C5 在 index 4 失败且整批干净回滚、后续合法编辑正常；C4 五副本全部成功；C6 批 A 成功、批 B 首个 op 失败。诊断增强后以最终执行器复跑 C2/C4，行为与前一轮一致（`t2_rerun.json`）。T3 草图平移 9/9 候选未触发（`sketch_shift.json`）；T4 零件与装配均为零变更守卫、`ack_success` 未发生（`assembly_ack.json`）。
- **未验证**：Creo 9/10 的构建与建模（本机无 Creo 9 SDK，Creo 10 不要求独立复测）；WorkBuddy 黑盒验收；`accepted_rigid=true` 实机分支（9/9 未触发，保留外部补证）；`ack_failure` 成功路径与幂等实机证据（仅单测覆盖）；`keep_original` 复制**固定原件**的副本语义（现有实现复制整个当前体，需要固定原件副本时应另建模型）；"恰好重合 vs 部分交叠"的内核判据。
- 环境：Windows 11 x64 / PowerShell / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / MSVC x64；检查无新增风格回归，不代表全库存量严格格式清零。
- 本版含原生改动（`native/placement.cpp`、`native/generic.cpp`，**诊断只读、不改几何与再生时机**），需重新编译执行器；第三方文件未修改。

## 升级

1. 使用成对的 0.11.7 源码包与种子包；种子 PRT 字节不变，两份清单的 `compatible_server_version` 已更新，旧种子包会被版本闸门拒绝。
2. 重新运行 `setup.ps1`，或在安装虚拟环境执行 `python -m pip install --no-deps -e .` 后重启 MCP 服务加载新模块。原生代码有变更，首次启动会重建/校验 `build/creo_worker.exe`。
3. 调用方需要复核的语义变化：**无**。新增的 `failed_transform.selection` 只增不改，旧回执缺该块保持缺省、不推导。**唯一需要留意的是能力边界**：`keep_original` 副本累积在同一 body 内，能否继续追加取决于既有副本集合与角度组合，"≤4/批再重新引用"的做法已实测无效。
