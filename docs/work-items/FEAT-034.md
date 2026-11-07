# FEAT-034：草图弧方向、扫角与实际几何回显

## 当前摘要（2026-11-07，DEV-073 复核）

状态：**已完成**。结论：BUG-093 后续五非法例及恢复编辑实机通过，原卡首页滞后。剩余：本卡无保留范围；其它卡的范围不重复派工。

最新分段记录：[同卡 2026-10-31：N07 第二轮实机复测（编排方串行）](#dev073-latest-evidence)。

证据：[原始登记与证据](#dev073-history)；[BUG-093 后续五非法例及恢复编辑](BUG-093.md)。本轮仅文档复核，历史环境和未测事实保留，不作为本次重跑结论。

<a id="dev073-history"></a>

## 原始登记与历史过程

以下为原时点记录，当前以本摘要及 [BACKLOG](../BACKLOG.md) 为准。

日期：2026-10-17；当前核对：2026-10-31。类型：功能。优先级：P1。状态：已交付（0.8.0 实现；2026-10-29 创建例实机 4/4；**2026-10-31 N07 第二轮创建 5/5 + 方向编辑 3/3 实机通过**，`named_ids` 再快照修复生效；**`illegal_dir_zero` 反例判定未过待查 [BUG-093](BUG-093.md)**，其余 4 非法例与恢复编辑未执行）。目标版本：0.8.0/0.8.3/0.10.0；剩余与 WorkBuddy 验收继续开放。

当前实现与真实检查结果见 [DEV051-T02-ACCEPTANCE](../development/DEV051-T02-ACCEPTANCE.md)，提交 `a3c1f4b`；后续按 [0.7.2 续版计划 T02](../development/0.7.2-FEEDBACK-PLAN-2026-10-28.md)补真实集成实机入口。29项专项和构建通过不代表原生闭环；T02较早的1项安装沙箱网络错误保留为历史，[T03验收卡](../development/DEV051-T03-ACCEPTANCE.md)已提供后续全量检查通过记录，按各自指纹解释。已随 0.8.0 交付离线实现，但不能据此宣布原生验收通过。下文保留最初登记时的目标与证据，已定契约以T02验收卡为准。

来源：[0.3.3 反馈补录](../validation/FEEDBACK-0.3.3-2026-10-17.md)报告 B 第 4 节；关联 FEAT-008、BUG-050/051。

## 目标与范围

报告在 Creo 10 / MCP 0.3.3 对 R10、弧加弦封闭截面拉伸 5 mm：角度 0→90 得 `142.699081698 mm³`，90→0 得 `1428.097245102 mm³`，均成功。报告称现有 start/end 按逆时针归一化；两个输入对应不同扫角，不能据体积约差 10 倍认定数值计算错误。合法大于 180° 的弧继续允许。

评估显式 `dir` 或 `sweep_deg`，先确定字段、正负/跨零/整圆及互斥规则；保留旧 start/end 请求的明确兼容语义。回显实际起止点、方向、扫角及其坐标系；可选提供大弧提示，不能把 >180° 一律当错。统一草图创建、计划及几何更新入口，不以端点四舍五入掩盖闭合/精度问题。

## 验收标准

| 环境 / 用例 | 可判断的预期结果 |
| --- | --- |
| Windows / schema 与回归 | 旧角度请求语义稳定；新字段和冲突/零扫角/超范围输入有明确契约；运行统一开发检查 |
| 本机 Creo 12.4 / 匹配 SDK | 顺/逆时针、小弧/大弧、跨 0°、半圆及明确支持的整圆分别核对端点、切向、扫角；弧加弦截面体积符合所选扇段解析值 |
| 编辑与持久化 | 修改方向/扫角后几何、下游特征、revision 及保存重载正确；非法输入保留检查点；提示不拒绝合法大弧 |
| WorkBuddy | 仅 MCP 输入与几何/参数回读验收；报告实际扫角、体积、job/model、保存重载及原始错误 |

## 实现与证据

本次仅登记能力建议，未选择接口或改变原生弧方向。外部 0.3.3 对照不代表当前 0.3.4 已复测；来源原件与摘要见补录。实机执行须先满足当前会话安全约束。

## 2026-10-30：T02 弧方向编辑与保存重载补验——离线阶段（实机未验）

分支 `codex/dev051-feedback070`，提交 `3851963`。基线 `641edb3`。本节只改驱动与单元（`tools/test_arc_direction_live.py`、新增 `tests/unit/test_arc_direction_live.py`），**未改生产代码**、未连 MCP/Toolkit、未启动 Creo、未改版本、未合 main、未 push、未发布。

- **修掉两个判定缺陷**：①驱动「只看体积即可 passed」；②「从 terminal 顶层取 `saved_file_reloaded_and_verified`」——该字段实际只在 `result` 块，顶层永远为 null。改为要求 job succeeded ∧ 实测体积对上独立 oracle ∧ `arc_geometry` 原生回显 ∧ `result.saved_file_reloaded_and_verified is True`，缺任一项即 `passed=false`；回归 `test_missing_native_arc_echo_cannot_pass`、`test_missing_reload_evidence_cannot_pass`、`test_volume_only_evidence_cannot_pass`、`test_top_level_reload_flag_is_not_evidence`。
- **补覆盖**：方向编辑（就地切 dir、跨零、XZ 倾斜帧）、下游特征跟随（体积变为 to_dir oracle 且 revision 恰好 +1、feature_id 不变）、非法编辑（模型体积与 revision 不变、须有回滚证据，随后合法回切并保存重载）、保存重载后方向与几何仍正确。旧四例数值以回归钉死，未放宽。
- **离线证据**：145 项定向单测 OK、离线驱动 exit 0、ruff 通过。
- **仍未测（本节零 MCP/Toolkit/Creo 调用）**：真实 `arc_geometry` 原生回显、方向编辑后的下游再生体积、revision 递增语义、保存重载、非法编辑的原生拒绝/回滚字段形态、busy/单通道（须真实并行调用才可报告）、WorkBuddy、Creo 9/10。
- 实机入口：`.\.venv\Scripts\python.exe tools\test_arc_direction_live.py --live --confirm-session-usable`（唯一 dev 服务 `MCP_CREO_MechDog_dev`，先满足 BUG-001 会话条件）。

详见 [T02 验收卡](../development/DEV051-T02-ACCEPTANCE.md) 2026-10-30 节。本条保持开放（编辑/下游/重载/非法编辑实机未验）。

<a id="dev073-latest-evidence"></a>

## 2026-10-31：N07 第二轮实机复测（编排方串行）

分支 `codex/dev051-feedback070`，受测提交 `49decae`（工作区 dirty），原始报告 `build/post090_live2_20261031T115830/n07/report.json`（SHA256 `b9942a89…dde4de`，`provenance.source_fingerprint=734d2c1c…b901`）。本节只追加，不改写 2026-10-30 离线节与首轮记录。

**创建例 5/5 通过**（`arc_echo.source="native"`、`query_code=0`、各阶段保存重载 true）：

| 用例 | job | model | rev | 实测 / oracle 体积 (mm³) | 误差 |
| --- | --- | --- | --- | --- | --- |
| `legacy_0_to_90` | `8ae9dc7798ee465fa46e4777506be822` | `5e9c9d35035940bca9a4703dfc5931e2` | 1 | 142.69908169840258 / 142.69908169872414 | 3.22e-10 |
| `legacy_90_to_0` | `8d0f3abe3380402b82e055e64a4fe8c9` | `0632662c335948b0b521ded3576f0c41` | 1 | 1428.09724510173 / 1428.0972450961724 | 5.56e-09 |
| `dir_minus1_90_to_0` | `162dca88025c481a860fb6600a945b60` | `ec24ad7c31dc4cb087ba707fd28e14e6` | 1 | 142.69908169840258 / 142.69908169872414 | 3.22e-10 |
| `dir_minus1_0_to_90` | `2fe5cc9fb9e84d6d9a0dafa989c180d9` | `3df1c0e88de340ff80f4ae2ba8e673b6` | 1 | 1428.09724510173 / 1428.0972450961724 | 5.56e-09 |
| `tilted_xz_dir_minus1_0_to_90` | `aee9189d0b6c499698b63a84c6e2aa68` | `c30e8212bd9c47178a5fc63bab25a389` | 1 | 1428.0972450906143 / 1428.0972450961724 | 5.56e-09 |

**编辑例 3/3 通过**——2026-10-31 早先的 `named_ids` 修复实机生效，编辑后回显不再是 `unknown`/`query_code=-2`：

| 用例 | job | model | rev | 实测 / oracle 体积 (mm³) | 回显 |
| --- | --- | --- | --- | --- | --- |
| `edit_switch_dir_0_to_90` | `effd024f149e43fda8b06d5e1a6fc947` | `6aa751d862cf4de1ad513e32ea22f583` | 1→2 | 1428.0972451017303 / 1428.0972450961724 | native、query_code=0、dir=-1、sweep 270° |
| `edit_switch_dir_cross_zero` | `5d96fde8db5f43bd9fb64bc5cc2a3cb1` | `0fe34708ae2b44ce9a852e09a90c4b24` | 1→2 | 1569.0348997575504 / 1569.0349000265974 | native、query_code=0、dir=-1、sweep 340° |
| `edit_switch_dir_tilted_xz` | `0de57535e7d841e29f7c8161a888b375` | `65cb00f32c524d9d80f277855b0a473c` | 1→2 | 1428.0972450906143 / 1428.0972450961724 | native、query_code=0、dir=-1、sweep 270° |

三例的 `preserved_feature_id=40` 保持，revision 恰好 +1，各阶段保存重载 true。

**非法编辑反例判定未过，待查。** 本轮 `illegal_edits` 只执行到第一例 `illegal_dir_zero`（`kind=schema`）即 `passed=false`、`failures=["volume_missing"]`，原始形态为：工具入参被 **schema 层显式校验拒绝**（pydantic `value_error`："Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise) … input_value=0"），**未产生作业**（`job_id=null`、`terminal_status=null`、`rollback=null`），模型 revision 3→3 未变、基线体积 1428.0972451017303 保持。判定失败缺的是"拒绝之后的同源实测体积"这一证据：驱动在拒绝后用 `creo_refresh_model` 取体积，本次该结果块未带 `volume_mm3`（`measured_volume_mm3=null`），故判 `volume_missing`。**不是"作业失败"，也不是"非法编辑被接受"**；但按严格判定该反例**未通过**，驱动随即 `raise AssertionError` 终止，本段其余 4 个非法例（`illegal_dir_float`、`illegal_zero_sweep`、`illegal_full_circle`、`illegal_open_profile`）与 stage 5 恢复编辑/保存重载**未执行**。

因此本条状态口径更新为：**创建 5/5 与方向编辑 3/3 实机通过（回显、revision、下游体积、保存重载均成立）；非法编辑反例判定未过、待查；恢复编辑与保存重载阶段未执行**。不得因"拒绝确实发生了"就把反例记为通过，也不得据此放宽判定。
