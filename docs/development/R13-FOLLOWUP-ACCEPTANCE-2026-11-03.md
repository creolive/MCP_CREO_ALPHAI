# R13 后续定因与补证：本轮验收记录（离线）

日期：2026-11-03。分支：`codex/BUG-111-r13-followup`（起点 `45780df`）。计划：[R13 后续定因与实机补证](../superpowers/plans/2026-11-03-r13-followup-bug111-108-110.md)。

## 结论摘要

本轮只交付**离线部分**：三个实机驱动按计划完成场景隔离与三态判定改造，新增 23 项纯判定回归。**T1—T4 的实机步骤全部未执行**——没有当次会话授权，按 BUG-001 纪律不新建 Toolkit 连接、不做故障注入、不清 unknown 保护。因此：

| 目标 | 本轮结果 | 是否关闭 |
| --- | --- | --- |
| BUG-111 第五副本定因 | 驱动可隔离复现（C0—C6 各自新建底板），未跑实机；`index=4` 仍以 0.11.6 记录为准 | 否（未定因） |
| BUG-108 `accepted_rigid=true` | 9 个独立候选 + 独立复算 + 严格三态判定已就绪，未跑实机 | 否（未触发） |
| BUG-110 `ack_failure` 成功路径 | 三个 scope 分开、前后快照/重放/后续可用性已就绪，未跑实机 | 否（未覆盖装配） |

## 身份与环境

| 项 | 值 |
| --- | --- |
| HEAD | `45780df`（`DEV-059: reconcile R13 plan, ledger and missing work cards`） |
| 分支 | `codex/BUG-111-r13-followup` |
| 源码指纹（`build/source.sha256`） | `cd22b5633159024d93907a20a3e62c3cd24cda930ef28025be64f290f3adf4c4` |
| 执行器 | `build/creo_worker.exe`，13 323 776 B，SHA256 `0f5565049abfa9f16f742ca1e06c25f45e37670003b951a2093c8920905a64c1` |
| 原生是否重编 | 否（本轮无原生改动；旧 worker 只对应 `cd22b563…` 这批源码） |
| 运行目录 | `build/r13_followup_20261103T161114/baseline.json` |
| 环境 | Windows x64 / Python 3.12.14 / Creo 12.4.0.0 与匹配 SDK（本机） |

## 交付物

| 文件 | 变更 | 离线验证 |
| --- | --- | --- |
| `tools/test_geometry_transform_copies.py` | C0—C6 独立底板、显式 body id、4+3 拆批、选集记录、`judge_copy_case`、`--phase reproduce\|verify` | `tests/unit/test_geometry_transform_copies_driver.py` 6 项 |
| `tools/test_sketch_shift_batch.py` | 9 个独立候选（3 偏移×3）、`rigid_fit` 独立复算、`judge_shift_case`、请求容差仅作对照 | `tests/unit/test_sketch_shift_driver.py` 10 项 |
| `tools/test_assembly_ack_failure.py` | `failure_guard`/`ack_success`/`part_guard` 三 scope、快照不变性、同键重放、后续可用性、`judge_ack_case`、分列覆盖 | `tests/unit/test_assembly_ack_failure_driver.py` 7 项 |
| `.gitignore` | 忽略 `.codebuddy/`、`.workbuddy/`、`.zcode/`（IDE/agent 本地数据，非源码） | 不参与风格发现 |

## 检查命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_geometry_transform_copies_driver tests.unit.test_sketch_shift_driver tests.unit.test_assembly_ack_failure_driver` | 23 项通过 |
| `python tools/dev_check.py --work-item BUG-111-BUG-108-BUG-110-followup` | `success=true`；`build/unit_test_report.json`：2 264 项，0 失败/0 错误；无新增语言问题；风格基线未改 |
| `python tools/test_geometry_transform_copies.py`（无确认参数） | 退出码 2，不启动 stdio |
| `python tools/test_sketch_shift_batch.py`（无确认参数） | 退出码 2 |
| `python tools/test_assembly_ack_failure.py`（无确认参数） | 退出码 2 |

## 判定语义（本轮新增，供实机轮直接套用）

- `reproduce`（副本驱动默认）：证据齐全、失败位置如实记录即 pass；复现到已知失败**不会**让 `verify` 通过（`verify_requires_committed_batch` 判 fail）。
- 三态：缺必要证据 → `unverified`；证据互相矛盾（如 `accepted_rigid=true` 但平移超 1e-2 mm、ack 后 revision/文件/绑定变化、重放产生二次事务）→ `fail`；只有目标分支全部证实才 `pass`。
- 覆盖分离：零件 ack 通过不补齐装配（`covers_assembly=false`）；`failure_guard` 通过不算成功路径；请求容差候选不计入默认闸门覆盖；控制场景 pass 不补齐目标 scope。

## 未执行与阻塞

1. **实机会话授权**：本轮无当次授权，按 BUG-001 只做离线。需要执行人确认会话可操作（GUI 可用、无阻塞对话框、`creo_session_status.connected=true`）后再跑 T1/T3/T4。
2. **BUG-111 定因**：需按 C1—C4 观察失败是否随位置（→ 选集/父链假设）；C5 用显式 body id、C6 拆 4+3 继续区分"选集随体增长"与"位置上限"。未取得对照前不得写"内核最多四次"。
3. **BUG-108 触发**：9 个候选若全部 `rigid=false`，只能交付"正常路径回归、目标分支未验证"，并保留外部 Creo 10 补证；不得提高阈值或人为搬动截面。
4. **BUG-110 装配成功**：若装配仍零变更回滚、造不出 `failed`，如实记缺件并保留零件侧记录；不注入进程故障、不手改注册表。
5. **未测范围**：Creo 9 / Creo 10 / WorkBuddy 均未验；`docs/validation/` 原件未改；历史 0.11.6 实机证据仍属那次批次，不能当本轮结论。

## 剩余顺序（需授权会话）

1. BUG-111：`--phase reproduce` 跑 C1—C4 → 视结果跑 C5/C6 → 有实现缺陷证据才进最小修复（T2）。
2. BUG-108：跑 9 个候选 → 触发则补尺寸编辑与重载 → 未触发则记覆盖缺口。
3. BUG-110：零件 → 装配零变更守卫 → 若可达 `failed` 则走 ack 成功/幂等/后续可用。
4. 汇总后按发布规则另议版本；本批不合 main、不改版本、不发布。
