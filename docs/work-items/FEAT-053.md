# FEAT-053：`datum_plane` 三点定面（`thru_points`）

日期：2026-11-01。类型：功能。优先级：P2。状态：离线实现完成（2026-11-01，Q05 分支），实机待验收。目标版本：未排期。

来源：[0.10.0 晚间包 02_G5 曲面能力方案](../validation/feedback-0.10.0-2026-11-01/originals/02_G5曲面能力方案.md) §4、[03_BUG094报告](../validation/feedback-0.10.0-2026-11-01/originals/03_BUG094报告.md) §二/§六 与 [04_generic_cpp_patches](../validation/feedback-0.10.0-2026-11-01/originals/04_generic_cpp_patches.md) §补丁 1；[逐章映射](../validation/feedback-0.10.0-2026-11-01/MAPPING.md)。关联 [FEAT-008](FEAT-008.md)、[BUG-097](BUG-097.md)、[BUG-094](BUG-094.md)、[FEAT-009](FEAT-009.md)、[FEAT-039](FEAT-039.md)。

## 目标与范围

`datum_plane` 增加三点定面形式，首版建议 `reference={kind:'through_points', points:['dpa','dpb','dpc']}`：严格三个标签，每个标签唯一指向一个 `datum_points` 特征贡献的单个 `PRO_POINT`。

外部报告在 Creo 10 直改环境实现并实测：三个 `PRO_DTMPLN_THRU` 约束各引用一个点，`datum_plane` 创建成功且几何与解析逐位一致（`id=47, normal=(-0.678,-0.093,0.730), origin=(-95.191,40.000,-88.395)`）。该几何正确性是**外部来源**，本仓库尚未实现与验证。

范围：

- 三点定面本身（独立入口与 plan 同契约）。
- 与 `angle`、`axis`、非零 `offset` **互斥**；缺 `kind`、angle+非零 offset 的既有拒绝语义保持不变。
- 不支持四点拟合；不猜取多点特征的第一点。
- **外部写法不能原样放行**：晚间包出现三种不等价写法——`reference={"thru_points":[…]}`（02/03 报告）、`thru_points` 直挂（04 补丁）、`{"kind":"datum_point_feature","label":…}`（04 补丁的解析目标）。须经明确转换进入统一契约，不接受缺 `kind` 的绕过。
- 三点平面对**任意斜面草图**的解锁属通用增益，但其草图侧的 UV 映射与特征完成问题归 [BUG-097](BUG-097.md)；曲面放样/投影/剪裁归 [FEAT-009](FEAT-009.md)/[FEAT-039](FEAT-039.md)；扭叶片逐站棱柱路线的配方转换归 DEV-053 场景。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `python -m unittest tests.unit.test_datum_plane_through_points -v` | 正反例齐备：2 点/4 点、重复标签、空值/bool、未来引用、错误特征类型、多点特征、angle/偏移混用均按契约拒绝或接受，错误可判读 |
| 本机 Creo 12.4 / 匹配 SDK | 主平面、斜面、大/小尺度、点序颠倒、错误引用 | 原生回读点坐标、单位与唯一性正确；三点到平面距离、法向与叉积方向等价性成立；特征引用有效 |
| 本机 Creo 12.4 / 匹配 SDK | 失败路径 | 失败前后 revision 与特征集合不变；不回滚即建错特征 |
| 本机 Creo 12.4 / 匹配 SDK | 保存擦除重载 | 重载后三点平面与引用仍有效，保存重载 `saved_file_reloaded_and_verified == true` |

**近共线三点**的容差与尺度说明须记录入本卡，不以固定世界坐标大小猜测；共线/重复/无法判定的三点明确拒绝。原报告给出的 `normal`/`origin` 只作旁证，不作本机断言基准。

## 实现与证据

### 2026-11-01 登记（初始）

2026-11-01 登记，登记时无实现。外部证据为 0.10.0 晚间包（Windows 11 x64 / Creo 10.0.0.0 / 外部直改 0.10.0 源码），**未在本仓库复现**。

补记：晚间包 P12 特征树（`p12_v12_native_tree.json`）中 96 个 `datum_plane` 的 `thru_points` 引用的是**点名** `p_a`/`p_b`/`p_c` 而非特征标签，且点名在 48 带中逐带重复；`p12_v12_native_recipe.json` 的 `patch_needed` 字段也明确写出"execute_plan datum_plane op: accept thru_points:[labels] (PRO_DTMPLN_THRU x3)"。这说明首版契约的**单点唯一引用**要求比外部写法更严，配方转换时须以 `(来源特征 label, 点名)` 为映射键生成全局唯一的新标签，不能按裸点名替换。

三点平面成功**不等于**扭叶片可用，也不等于斜面草图已可创建；两条链各自独立验收。

### 2026-11-01 Q05 离线交付（分支 `codex/q05-datum-plane-points`）

**契约（已实现，独立工具与 plan op 同源同契约）**：`datum_plane.reference={"kind":"through_points","points":[label_a,label_b,label_c]}`。

- 严格三个**互不相同**的特征标签，每个标签是**同一计划内早于该 `datum_plane` 的 `datum_points` 操作**创建的**单点**特征；缺此条件（前向引用、计划不创建、错误特征类型、多点特征）在准入即拒绝，错误可判读。多点特征不猜取第一点；不支持四点拟合。
- 与 `angle`（含 0）、`axis`、非零 `offset` 互斥；缺 `kind` 拒绝、`angle`+非零 `offset` 拒绝的既有语义不变。
- 外部三种写法不原样放行：无 kind 的 `{"thru_points":[…]}` 与执行器内部的 `{"kind":"datum_point_feature","label":…}` 均被拒绝并给出转换指引，须转换为 `kind:'through_points'` 显式形式（转换器见下）。
- 跨作业 label 不在本契约内：standalone 单操作提交无法满足"同计划内已创建"，三点形式须用 `creo_execute_plan` 把三个 `datum_points` 与 `datum_plane` 放进同一计划（Q11 分批时须把引用的点与其平面同批）。

修改面：`src/creo_mechdog/references.py`（kind 白名单、`through_points` 形状校验、转换指引文案）、`src/creo_mechdog/schema.py`（`PlaneOp` 互斥、`validate_operations` 计划内生产者校验、引用遍历放行 `through_points` kind）、`native/generic.cpp`（`through_points_plane`：单点解析、创建前判读、三个 `PRO_DTMPLN_THRU` 约束、创建后回读验证与真实帧回执、外部写法 backstop）、`server.py`/`capabilities.py`（`creo_datum_plane` 与 datums 能力描述）、`tests/unit/test_datum_plane_through_points.py`（46 项正反例与桩测试）、`tools/test_datum_plane_through_points.py`（离线判定/断言/转换 + live 矩阵）。

**近共线判定容差与尺度依据**（原生创建前判定，`native/generic.cpp` 常量 `kThruPoints*`；离线镜像见驱动 `tools/test_datum_plane_through_points.py`，两者由单测锁定）：

- 判据全部是三点**自身间距的无量纲比值**，不以固定世界坐标大小猜测；同一形状在 1e-3 与 1e6 缩放下判读一致（单测覆盖）。设 L = 三点两两距离的最大值，d_min = 最小值，h = 最小高 = |AB×AC|/L。
- **重复点**：d_min ≤ 1e-9·L（`kThruPointsDuplicateRatio`）拒绝。依据：双精度下相对整体尺度低于 1e-9 的间距已无法稳定区分两点，法向由数值噪声主导。
- **近共线**：h ≤ 1e-6·L（`kThruPointsCollinearRatio`）拒绝。依据：法向 = normalize((B−A)×(C−A))，坐标相对误差 ~1e-15 传入叉积后法向方向误差约 (L/h)·1e-15；要求 h/L ≥ 1e-6 使方向误差 ≤ ~1e-9，同时远低于任何真实设计三角形（smoke 原案 h/L ≈ 0.04，安全通过）。
- **无法判定**：坐标非有限、L=0（三点重合/不可测）或长度单位查询失败（scale 未知）→ 拒绝，不猜测。
- **创建后回读验证**（失败即抛错走作业回滚，失败回执保留已取得证据）：
  - 点到平面距离 |(P−O)·N| ≤ max(1e-6 mm, 1e-9·L_mm)（`kThruPointsDistanceFloorMm`/`kThruPointsDistanceRatio`，毫米口径）；
  - 法向与叉积方向等价 |abs(N·normalize((B−A)×(C−A))) − 1| ≤ 1e-9（`kThruPointsAlignTolerance`；**符号不作要求**，点序颠倒产生同一几何平面）；
  - 特征引用正确：提取创建特征元素树，核对恰 3 个 `PRO_DTMPLN_THRU` 约束、各引用一个 `PRO_POINT` 且 id 集合等于三点 id 集合。

**离线证据（2026-11-01，本机 Windows x64 / Python 3.12，工作树 `E:\Projects\MCP_CREO_MechDog_q05`，PYTHONPATH 隔离，原生未编译）**：

- `python -m unittest tests.unit.test_datum_plane_through_points -v`：46/46 通过（正反例、smoke 转换、判定/回读桩、原生源码常量与拒绝语句对账）。
- `python -m unittest tests.unit.test_datum_plane_contract tests.unit.test_reference_contract tests.unit.test_t03_plane_reference tests.unit.test_t04_arbitrary_plane_coordinates`：42/42 通过（缺 kind 与 angle+offset 旧行为保持）。
- `python tools/test_datum_plane_through_points.py`：4/4 离线检查通过（smoke 原案转换后可准入、未转换原案被拒、判定尺度无关、回读断言与失败不变式）。

**未测范围（留给集成人/实机，未执行）**：

- 原生编译（`bridge.py build`）与 Creo 12.4 实机矩阵：主平面、斜面、大/小尺度、点序颠倒、错误引用、重复/近共线拒绝、失败前后 revision 与特征集合不变、保存擦除重载 `saved_file_reloaded_and_verified==true`。live 驱动：`python tools/test_datum_plane_through_points.py --live --confirm-session-usable`（需会话准入）。
- Creo 9/10、WorkBuddy 黑盒未验；外部报告的 `id=47, normal=(-0.678,-0.093,0.730), origin=(-95.191,40.000,-88.395)` 仍只作旁证，不作本机断言基准。

**下游接口（Q06/Q11）**：

- 原案转换：`tools/test_datum_plane_through_points.py::convert_plane_operation` / `converted_smoke_operations()`——`{"thru_points":[…]}` → `{"kind":"through_points","points":[…]}`；转换后的 smoke 计划可直接 `validate_operations`（单测已锁定）。
- 真实帧：操作回执 `operations[].plane_frame`（`surface_id`/`normal`/`origin`/`length_unit`，创建特征回读、毫米）；亦可经 `inspect_model(datum_planes)` 按 `surface_id` 查询。**禁止从输入点或矩阵表象重建帧**（Review Focus 3）。
- 三点平面成功不代表斜面草图可创建（[BUG-097](BUG-097.md)）；Q11 拆点后须保证每个 `datum_plane` 与其三个单点 `datum_points` 在同一计划内（按真实依赖分批）。

## 2026-11-01 Q15 离线集成状态

离线开发完成，待实机验收。来源及合并提交见 [Q15 集成报告](DEV-053-Q15-integration-2026-11-01.md)。此状态不表示原生构建、Creo 实机、主干合入或发布完成。
