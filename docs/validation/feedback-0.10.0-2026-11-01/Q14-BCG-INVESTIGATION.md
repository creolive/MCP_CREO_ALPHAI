# Q14：B/C/G 未复测项调查

日期：2026-11-01。基线 `50636bfc3daee8276e00da55b3f382acfe0679b7`。本文是离线替代验证，不是 0.9.0 原案复现，也不声明 Creo 几何成功。0.10.0 原件 `originals/01_验收报告_0.10.0.md` 明列三项“未复测”；同目录 `MAPPING.md` 缺件表确认原案载荷均不齐。夹具为 `tests/unit/test_q14_bcg_contract.py`。

## B：凹圆棱 round

- **现行契约：** `RoundOp` 要求正的毫米 `size` 或 `radius`（二者互斥）及非空 `references` 集合。`native/generic.cpp::generic_round` 对每组 `surfaces` 采用 `PRO_ROUND_REF_SURF_SURF`，否则对 `edge` 采用 `PRO_ROUND_REF_EDGE` 和曲线集合；常半径、attached、rolling ball。schema 校验引用 ID，不判断两面是否相交、目标棱凹凸、局部半径上限或圆角能否完成。`reference_application` 只按特征树计数，不能单独证明目标棱正确。FEAT-051 既有 `round_concave` 集成证据属于另一用例，不能替代本原案。
- **原始输入是否齐备：** 否。缺原模型/目标边或面 ID、曲面与相邻几何、半径及完整请求回包。
- **复现条件：** 替代夹具设明确目标棱 `edge id=12`、或同一目标棱的相邻 `surface id=21/22`，半径 2 mm；反例是负半径和无效边 ID。ID 仅占位，须在集成人员创建的带凹圆棱模型中由实际几何查询替换，并检查两种引用是否确指同一棱及局部可容纳半径。
- **真实结果（离线可证部分）：** 两种正例通过 schema；两个反例被拒。原生代码显示选择分支，但不能离线证明目标棱、圆角方向、拓扑或体积。原案“面组失败”仍未复现。
- **是否需要下一实施任务：** 先要独立集成调查，输入为最小凹圆棱模型、真实边/面 ID、不同半径与原案（若取得）；输出为每次特征终态、应用组数、体积前后、目标边几何及保存重载证据。测试分别覆盖明确 edge 与 face-pair 的正反例。文件优先为 `tools/test_round_concave.py`、`docs/validation/...`；仅证实产品缺陷后才提改 `native/generic.cpp`、对应 Python 回归。建议关联 FEAT-051/FEAT-008，若证实新缺陷再提新 BUG ID；本调查不占号。

## C：coordinates spline

- **现行契约：** `SketchOp.entities_unique` 明确将 coordinates 限于 line/centerline/rectangle/polyline/circle/arc；autodim 可接收 spline。原生 `generic.cpp` 能创建 spline 实体，但 `sketch_coordinates.cpp::coordinate_dimensions` 只为线、圆、弧取锚点/半径，其余抛错。当前输入 `points` 在 Toolkit `Pro2dSplinedef.point_arr` 中传递；仅凭字段名无法证明它是可逐点驱动的控制点还是插值点。
- **原始输入是否齐备：** 否，缺原 spline 点列、闭合性、支撑面及精度目标。
- **复现条件：** 替代输入三个点 `[0,0],[1,1],[2,0]`；分别选 coordinates 与 autodim。
- **真实结果（离线可证部分）：** coordinates 在 Python schema 被拒，autodim 通过 schema；没有运行求解，也不能证明曲线保真。这是明确未交付的能力扩展，并非现有契约缺陷。
- **是否需要下一实施任务：** 建议在 FEAT-010 下拆 spline 子项。输入需冻结点语义（控制点或插值点）、开/闭曲线、切向/权重是否支持及容差；输出需可回读的求解前后点/曲线偏差、`geometry_deviation` 的 `available/unavailable` 与原因，并与 Q02 默认 1e-5 mm coordinates 拒绝契约对齐。测试要覆盖创建、编辑、求解、保存重载、偏差超限与不可测，明确约束是驱动还是参考。预计文件 `src/creo_mechdog/schema.py`、`native/sketch_coordinates.cpp`、`native/generic.cpp`、对应单元和实机测试及能力文档。不能只删 schema 限制或静默改用 autodim。

## G：正交性闸

- **现行契约：** `AssemblyPose.rotation_matrix` 是局部到父级的行向量 3×3 单位正交矩阵，行内积及行列式 +1 的绝对容差均为 1e-6；不归一化，见 FEAT-012。草图字典平面的 `u_axis` 是单个方向向量：Python 拒绝平方长度 `<1e-18`，原生 `sketch_frame` 再拒绝长度 `<1e-9` 或与面法向近乎平行，投影后归一化。两种输入语义不同。
- **原始输入是否齐备：** 否，缺原接口、矩阵/向量数值和失败回包，因此不能判定旧报告究竟指哪条路径。
- **复现条件：** 分类夹具用单位矩阵、等比例三方向矩阵（2I）、近零首行、剪切、缩放、det=-1 反射；另以草图 `u_axis=[2,0,0]` 与零/近零向量探测方向路径。
- **真实结果（离线可证部分）：** 单位矩阵接受；2I、近零、剪切、缩放、反射均拒绝。草图等比例方向在 schema 接受，零及 `1e-10` 拒绝。原生方向对支撑面的投影、平行检查与求解未实机验证。1e-6 闸对矩阵属既定契约，不能将这些拒绝写成 bug。
- **是否需要下一实施任务：** 若原案确为草图方向输入且给出有效非零值仍被拒，关联 BUG-045 调查，输入原载荷/平面法向/错误阶段；输出明确方向长度与投影诊断；测试 Python、原生边界及实机草图，预计 `src/creo_mechdog/references.py`、`native/generic.cpp` 与测试。若用户要装配方向输入，建议 FEAT-012 单独扩展有名称的 `direction` 形态（明确单方向如何补全右手姿态和退化拒绝），保留 `rotation_matrix` 原样严格校验；测试含缩放、剪切、反射拒绝。不得统一归一化矩阵。

## 登记与验证

| 候选 | 建议 | 当前证据边界 |
| --- | --- | --- |
| B | FEAT-051/FEAT-008 关联的集成调查；若真复现再提新 BUG | 只有替代 schema 夹具及源码分支；原案缺件 |
| C | FEAT-010 spline 子项 | 能力缺口已由 schema 与原生代码证实，未设计/实现 |
| G | 原载荷到手后按 BUG-045（方向）或 FEAT-012（新输入形态）分流 | 矩阵拒绝是当前正确契约；旧报告位置未定 |

命令：工作树 `PYTHONPATH=E:\Projects\MCP_CREO_MechDog_q14;E:\Projects\MCP_CREO_MechDog_q14\src` 下，以共享 `.venv` 运行 `python -m unittest tests.unit.test_q14_bcg_contract -v`，4 项通过。未连接 Creo、未占 Toolkit 通道；未验证原案、几何结果、原生编译、保存重载或 WorkBuddy 黑盒。源码指纹与提交/dirty 见本调查提交交付记录。
