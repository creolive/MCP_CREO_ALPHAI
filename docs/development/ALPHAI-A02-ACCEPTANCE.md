# A02 / FEAT-004 尺寸守卫：验收摘要

日期：2026-11-03。分支 `codex/FEAT-004-dimension-guards`，实机基线提交 `7b3d90e`（本轮仅补验证据与文档）。环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK，单会话串行。

驱动：`tools/test_adoption_dimension_guards.py`。默认离线只跑 `check_dimension_guard` 共享判定；`--live --confirm-session-usable` 另建 50×30×10 方块，从 `inspect_model(detail="full", section="dimensions")` 读真实尺寸 id/symbol/owner/value 后逐例取证。证据 `build/acceptance_dimension_guards.json`，SHA256 `8e46c4d8ad97a658d6a97978ac8fb4b8621e965eb50c98ca7d479757071c91aa`（最终驱动重跑），19 例全部通过。

## 一 实机逐例

| 用例 | 载荷要点 | 实测 |
| --- | --- | --- |
| `matching_pin_accepted` | `d9` 10→12，pin value=10/symbol=d9/owner=DIMBLK | succeeded，尺寸读回 `12.0`，`saved_file_reloaded_and_verified=true` |
| `stale_value_refused` | 沿用已过期的 `expected_value=10`（活值已是 12） | failed：`Dimension 9 guard failed on value: expected 10, current 12, owner DIMBLK`，值仍为 12 |
| `wrong_owner_refused` | `expected_owner="NOT_THE_OWNER"` | failed：`guard failed on owner: expected "NOT_THE_OWNER", current DIMBLK (id …)` |
| `wrong_symbol_refused` | `expected_symbol="d0"`（实际 d9） | failed：`guard failed on symbol: expected "d0", current "d9"` |
| `legacy_payload_accepted` | 不带任何 pin 的旧载荷 11 | succeeded，读回 `11.0`（旧行为不变） |
| `batch_rollback` | 第一项改宽度 50→55（无 pin），第二项把深度 pin 到 10（实为 11） | 整计划 failed，`rollback_succeeded=true`，宽度与深度都保持原值 |
| `relation_driven_refused` | `set_relations "d9 = 9"` 后再改 d9 | 关系生效（`relation_driven=true`），编辑 failed：`Dimension 9 is controlled by relations`，值保持关系值 |
| `model_still_editable` | 失败后改另一尺寸 | succeeded，模型未被锁死 |

入口侧：四类拒绝都发生在**受理后的原生守卫**（job 已生成、`rollback_succeeded=true`），不是 Python 预检，因此"先受理再拒绝"的路径与契约一致；schema 层的 bool/非有限值拒绝由 `tests/unit/test_dimension_guards.py` 覆盖。

## 二 契约符合性

- `DimensionValue` 仍保留 `id:int, value:float`，新增三个可选 pin；旧载荷不带 pin 时行为与之前完全一致（`legacy_payload_accepted`）。
- 容差 `max(1e-8, |expected|*1e-8)`；离线用例覆盖边界内通过/边界外拒绝。
- 拒绝消息含尺寸 id、预期与实际值、归属与原始查询信息；归属未知时拒绝而不是当作匹配。
- 关系驱动尺寸即使不带 pin 也拒绝（关系值不可直接改），消息给出改驱动参数的指引。
- 一个 op 内先读全部目标再写；批内后项不符时整计划回滚，回执如实写 `effect_status`/`rollback_succeeded`。

## 三 未验证范围

- Creo 9 / Creo 10 实机。
- 装配级尺寸、骨架驱动尺寸与族表（family table）驱动尺寸的守卫行为。
- 同一计划内 `set_parameters` 先改参数再对同一尺寸下 pin 的先后语义（当前批次只测了 `set_dimensions` × 2）。
- WorkBuddy 黑盒客户端验收；本摘要为原生 + MCP 通道证据。
