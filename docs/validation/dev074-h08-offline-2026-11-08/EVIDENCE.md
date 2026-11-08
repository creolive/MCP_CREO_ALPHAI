# DEV-074 H08 `surface_round` 离线实现证据（2026-11-08）

本文件只记录**离线**工作：schema/校验、原生树接线、编译与单元测试。**本轮没有启动或连接 Creo，
没有提交实机作业，也没有做任何 `--live` 运行**；H08 的 C1/C2/C5 实机读数属于
[`dev074-h07-h08-2026-11-08`](../dev074-h07-h08-2026-11-08/EVIDENCE.md) 的契约探针证据，
不是本实现的实机验收。

## 交付范围

- 新公开计划操作 `surface_round` / MCP 工具 `creo_surface_round`（公开工具 104→105）。
- 输入：`target`（一个 quilt：`{kind:"quilt",id}` 或 `{kind:"quilt_feature",label}`）、
  `references`（恰一组 `{"surfaces":[{kind:"surface",id:N},{kind:"surface",id:M}]}`）、
  `radius > 0`（mm，有限实数）。
- 原生：`native/surface_round.cpp` 的 `generic_surface_round`，沿用 H08 实测的
  `PRO_FEAT_ROUND` + `PRO_ROUND_REF_SURF_SURF` + `PRO_E_RNDCH_ATTACH_TYPE=PRO_ROUND_ATTACHED`
  树；创建前用 `ProQuiltSurfaceVisit` 校验两个面是该 quilt 的成员，创建后重测面数、面积与闭合。
- 回滚：不新增机制，失败由 job 级既有检查点恢复处理；面不属于该 quilt、非相邻面对导致再生失败、
  结果不可测量或“圆角没有去掉面积”都抛错并进入该路径。
- 投影：`job_projection.SURFACE_ROUND_KEYS`；`capabilities.families()` 新增 `surface_round`
  家族并把工具列入 `surface_chain`。
- 文档：`G5-NATIVE-CONTRACT.md` §2.11/§4.4.2/§6.1/§6.2、`FEAT-055.md`、`DEV-074-HANDOFF.md`。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe bridge.py build` | exit 0，产出 `build/creo_worker.exe` |
| `.\.venv\Scripts\python.exe -c "... mcp.list_tools()"` | `tool_count=105` |
| `python -m unittest discover -s tests` | **2961 项通过，0 失败 0 错误** |
| 定向单测（`test_surface_round_contract.py`、`test_dev074_h07_h08_surface.py`、`test_t01_capability_contracts.py`、`test_reference_contract.py`、`test_callback_admission.py`、`test_update_check.py`） | 全部通过 |
| `ruff check`（本次改动文件） | All checks passed |
| `ruff format --check`（本次改动文件） | 全部已格式化 |
| `clang-format --style=file --fallback-style=none --dry-run --Werror native/surface_round.cpp` | 无差异 |

## 契约边界（离线）

- 允许：单组、常量半径、一个 quilt 的两个不同成员面。
- 拒绝（schema，无 job）：多组、`edge`/`plane`/`body` 面、face 带 label 或额外键、重复面、
  0/1/3 面、变半径/full/chordal/through-curve/transitions、非 quilt target、非法半径。
- 原生拒绝（无 job 或回滚）：target quilt 无法初始化、面不是该 quilt 成员、面无法解析。
- 由内核判定：两个成员面是否共享一条边。H08 C5 实测非相邻面对再生失败并整体回滚；schema
  不提前猜拓扑。
- 未开放：`PRO_ROUND_REF_EDGE`（无 quilt 边 id 通道）、变半径/full/过渡、圆角后 thicken/solidify 链。

## 未验证

- **实机未验证**：本实现的原生树、成员校验、面数/面积/闭合读数、保存重载与失败回滚都没有在
  Creo 中运行；H08 的 C1/C2/C5 只证明同一棵 generic round 树在探针中可行，不等于本实现已验收。
- 未测：非 mm 单位、弯曲/多面 quilt、跨 quilt 面、Creo 9/10、真实并发/通道占用。
