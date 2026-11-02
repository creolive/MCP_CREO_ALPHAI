# MCP_CREO_MechDog 0.11.3 发布记录

发布日期：2026-11-02。版本：`0.11.3`（PATCH，公开工具仍 95）。条目：[DEV-062](work-items/DEV-062.md)（R11 归档与登记）、[BUG-104](work-items/BUG-104.md)、[BUG-105](work-items/BUG-105.md)、[FEAT-056](work-items/FEAT-056.md)；[BUG-106](work-items/BUG-106.md)、[DEV-063](work-items/DEV-063.md) 仅登记。版本说明：[RELEASE_NOTES_0.11.3.md](../RELEASE_NOTES_0.11.3.md)。

## 交付内容

- 三份 v0.11.0 第十一轮反馈原件逐字节归档（3/3 长度与 SHA256 一致）+ 逐章映射与缺件表；与 `feedback-0.10.0-2026-10-31`、`feedback-0.10.0-2026-11-01` 并存不合并。
- `creo_recolor_assembly` 新增 `refresh_baseline`：缺组件 `appearance` 的旧检查点可显式以作业前实读外观建立回滚基线，回执 `baseline_source`，`dry_run` 给 `next_action`（BUG-104）。
- 失败终态收紧 + 新增 `creo_reconcile_model(action="ack_no_mutation", confirm_zero_mutation=true)`：零变更失败保持 ready；已 `failed` 的现场可用纯注册表事务复位并写审计块（BUG-105）。
- 上色取色：自动分族接受唯一组件标签键，新增 `random`（与 `palette` 互斥、确定性、回显解析结果），作业记录显式调色板（FEAT-056）。
- 台账与口径：`RELEASING.md` 第 8 步纳入 FEAT 卡状态核对；修正 BUG-089/BUG-102/DEV-061 卡头滞后与 DEVELOPMENT 版本行；155→161 行、分类重算。

## 验证

### 离线与静态

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 全量单元测试 | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | **2 158 项，OK，0 失败**（本批新增 27 项） |
| 开发检查 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item 0.11.0-feedback-r11` | `success=true`、`unit_tests=passed`、样式无回归（30 findings / 16 unformatted 均在基线内，未重建基线） |
| 受测源码指纹 | `build/development_check.json`（`c85aa8d` + 本批改动，dirty） | `7da8595254c8ccf22276817257dda776d693478e834994480a02c5bbb1045c36` |
| 原生构建 | `.\.venv\Scripts\python.exe bridge.py build` | exit 0；`build/creo_worker.exe` 13 250 048 B，SHA256 `a61fad90170af76a1ceab0e9f034ed840457d8f56bb54c50b1ede958faec3aad` |
| 种子包重建 | `.\.venv\Scripts\python.exe tools\package_seeds.py --output …` | 24 files / 9 seeds，`926c5a4f37d76f1c33923ed9aa182e457a9d06fe16f97e0fb458b9eb16b1375c`，与回填后的 `docs/seed_package.json` 二次重建一致 |

### 本机实机

**本版未执行实机验收。** BUG-104/BUG-105/FEAT-056 只完成离线实现与单元测试；本机 Creo 12.4.0.0 会话未连接、未编译运行实机驱动、未在 Creo 中观察 `baseline_source`、随机配色、`ack_no_mutation` 恢复与保存重载。

## 附件

| 附件 | 大小 | SHA256 |
| --- | --- | --- |
| `MCP_CREO_MechDog-0.11.3-source.zip` | （打包后回填） | （打包后回填） |
| `MCP_CREO_MechDog-0.11.3-seed-library.zip` | 24 files / 9 seeds | `926c5a4f37d76f1c33923ed9aa182e457a9d06fe16f97e0fb458b9eb16b1375c` |

种子包摘要已回填 `docs/seed_package.json` 并二次重建一致；源码包由本记录所属提交源码生成，`tools/package.py --seed-archive` 受信摘要闸门通过。源码包哈希无法写进它自身（自引用），故两项在打包后回填；回填提交只改文档，不替换已发布附件。

## 未验证范围

- `refresh_baseline` 的原生实读填基线与 `baseline_source=adopted_live` 实机回执、0.10.x 检查点一次性上色后的保存重载核验。
- 随机上色在 80 组件夹具的写后读回、族色区分与保存重载。
- connect 阶段零变更失败后 `ack_no_mutation` 的真实恢复，以及审计块在实机作业中的持久化。
- 反馈方 Creo 10 的 `-1` 拉伸、draft `flip=true` 方向失败与元素树 A/B、空件预览现场；Creo 9 / Creo 10 实机与 WorkBuddy 黑盒。
- 本批未新增公开工具，`creo_capabilities` 仍为 95；busy/并发实机未重复。

## 交付核对

- 分支：`codex/DEV-062-r11-followup`；本记录随合入提交进入主干。
- 合入提交、标签 `v0.11.3`、Release 链接与远端附件逐件哈希核对结果见下节“发布动作回填”。

## 发布动作回填

- 合入提交：（发布后回填）。
- 标签：（发布后回填）。
- Release：（发布后回填）。
- 远端附件哈希核对：（发布后回填）。
- 本地生成物（正文与附件）保留在 `E:\Projects\release-0.11.3\`（仓库外，不入库）。
