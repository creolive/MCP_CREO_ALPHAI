# DEV-047 / T04 任意平面 coordinates 创建与编辑离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[FEAT-010](../BACKLOG.md) 本次子项；[BUG-050](../work-items/BUG-050.md)、[BUG-079](../work-items/BUG-079.md)、[BUG-082](../work-items/BUG-082.md) 为受影响回归。任务分支：`codex/dev047-t03-plane-frame` 上 T03 交付 `7741dbb` 之后的连续提交，基于已纳入 T00/T01 的 `1f3ab19`。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。

依赖说明：T04 硬依赖含 T02（原生操作结果统一），T02 尚未实施；按派发表"未就绪时先做不依赖它的部分"执行，本任务不更改操作结果收集/状态契约，仅按现有契约输出。T02 落地时的去重与结果状态实现须保留本任务与 T03 的回读/帧字段。

## 改动与接口

- `dimensioning="coordinates"` 准入不再要求主平面字符串：字典平面（任意有效支撑面）同样通过 Python 校验与原生路由；实体集合（line/centerline/rectangle/polyline/circle/arc）与显式 dimensions/constraints 互斥边界不变，ellipse/spline 仍走 autodim，未在本任务扩展。
- 原生坐标尺寸在 section 局部坐标创建并回读核验（1e-5 mm 门槛不变，不改输入坐标、不静默降级）。创建路径去掉 "Coordinate dimensioning requires principal section axes"：U 轴与 section 轴成任意角度时，输入 u/v 分量按主导 section 轴命名（日志 `COORDINATE_AXES`，阈值 0.7071）。
- 编辑路径（`update_sketch_geometry`）删除非主平面强制 autodim 与显式 coordinates 拒绝；BUG-082 升级路由（auto/autodim → coordinates）对任意平面生效，仍要求实体类型兼容且 section 有坐标系实体；同几何快捷路径与重写路径共用同一坐标变换（T03 实际帧 `origin/u_axis/v_axis` 存于草图别名）。
- 中心线统一按**直线身份核验**：比较方向与两端点到目标无限线的偏移（日志 `COORDINATE_CENTERLINE_IDENTITY`），不再依赖可能被求解器滑动的端点（含原轴平行 skip_axis 分支）；轴平行中心线仍用基准投影线偏移尺寸固定，斜中心线不生成已知不稳定的端点尺寸（日志 `COORDINATE_CENTERLINE_SKEW`），由核验兜底。
- auto 路由启发式（≥10 展开图元或坐标/半径 >1000 mm）不变；此前字典平面无条件退 autodim 的分支删除后，小规模字典平面 auto 仍为 autodim，大/复杂轮廓升级 coordinates。
- `capabilities.py` sketch_dimensioning 摘要、`server.py` 两个工具 docstring 与 `docs/REFERENCE_SYNTAX.md` 新增"任意平面 coordinates 标注"一节同步上述契约。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t04_arbitrary_plane_coordinates tests.unit.test_sketch_stability tests.unit.test_t03_plane_reference -q` | 22 项通过；涵盖字典平面显式/auto 准入、主平面回归、斜中心线准入、实体与互斥拒绝、编辑准入、能力摘要与公开工具描述 |
| `python -m unittest discover -s tests -q` | 795 项通过，耗时 199.9 秒；期间修正根目录 `tests/test_sketch_stability.py` 的旧"字典平面+coordinates 拒绝"断言为接受侧（T04 行为变更），主平面拒绝项保留 |
| 变更 Python/C++ 的 ruff 与 clang-format | 全部通过，无新增语言诊断或格式回归 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `C3373E8DC947DE789089EC61DA2DE626E1859F1C961B0FD55EFF3858337552F4`，该生成物不入库 |
| `python tools/dev_check.py --work-item FEAT-010` | `success=true`、`unit_tests=passed`、`native_validation=not_run`；检查仅含语言与单元，不代表原生建模验收 |

dev_check 指纹（`build/development_check.json`）：基线提交 `7741dbb68ff31c27a4e128554d016cdf2076de3e`（dirty，含本次 T04 改动），受测源码 `checked_source_sha256=027bfbd284f93af114c533a9e103d2518d4ff992af46ae880b31ab7b2158c50b`，生成时间 2026-10-26T10:41:31Z。

### T13 实机验收矩阵（本次未执行）

1. 主平面 XY/XZ/YZ 与倾斜面（法向 `(0.587785,0.809017,0)`）上 coordinates 创建：线/多段线/矩形/圆/弧闭环与共享顶点组合，核对 `solver.coordinate_geometry` 偏差 ≤1e-5、命名尺寸可 `set_sketch_dimensions` 编辑、单原生特征。
2. 正反 U（如 Right 面 `u_axis=[0,0,1]` 与 `[0,0,-1]`）、平移 `origin` 的创建与图元位置核对；`COORDINATE_AXES` 命名与实际 section 轴一致。
3. centerline 三态：轴平行+偏移尺寸、轴上、斜中心线（无端点尺寸）创建后可作 revolve 轴；`COORDINATE_CENTERLINE_IDENTITY` 偏差达标。
4. 倾斜面草图就地编辑（coordinates/auto/autodim）与同几何重提 unchanged；编辑失败回滚、revision、后续合法操作。
5. 上述模型保存重载 `saved_file_reloaded_and_verified=true`；记录实际面 ID、源码提交/dirty/指纹。
6. 主平面 BUG-079/082 路由回归：既有编辑专项主平面用例无回归（升级路由、BUG-079 保真拦截）。

本次验收结论：**T04 离线实现完成，实机未验收**。0.3.5/0.5.2 报告的倾斜面被拒现象在源码层已解除，实机因果与几何保真待上述矩阵取证。未触碰 pre-existing 未跟踪运行文件与既有保护。
