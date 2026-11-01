# FEAT-053：`datum_plane` 三点定面（`thru_points`）

日期：2026-11-01。类型：功能。优先级：P2。状态：待规划。目标版本：未排期。

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

2026-11-01 登记，无实现。外部证据为 0.10.0 晚间包（Windows 11 x64 / Creo 10.0.0.0 / 外部直改 0.10.0 源码），**未在本仓库复现**。

补记：晚间包 P12 特征树（`p12_v12_native_tree.json`）中 96 个 `datum_plane` 的 `thru_points` 引用的是**点名** `p_a`/`p_b`/`p_c` 而非特征标签，且点名在 48 带中逐带重复；`p12_v12_native_recipe.json` 的 `patch_needed` 字段也明确写出"execute_plan datum_plane op: accept thru_points:[labels] (PRO_DTMPLN_THRU x3)"。这说明首版契约的**单点唯一引用**要求比外部写法更严，配方转换时须以 `(来源特征 label, 点名)` 为映射键生成全局唯一的新标签，不能按裸点名替换。

三点平面成功**不等于**扭叶片可用，也不等于斜面草图已可创建；两条链各自独立验收。
