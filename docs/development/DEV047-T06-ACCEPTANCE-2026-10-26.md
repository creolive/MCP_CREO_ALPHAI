# DEV-047 / T06 多闭环截面与诊断离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[BUG-049](../work-items/BUG-049.md)（主项）、[FEAT-006](../work-items/FEAT-006.md)（诊断子项）。任务分支：`codex/dev047-t06-multi-contours`，基线 `27eebd1`（集成分支 `codex/dev047-feedback052`，含 T00/T01/T02/T03/T04/T05）。源码提交 `38c1606`（实现）与 `7182ef0`（最终受测，补充无闭合轮廓拒绝）。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。

## 范围与素材边界

外部报告 R3 §4 的 `gear10.json`、`sketch_entities.json` 等原始附件当前缺失，本轮**没有**逐字复放原案例，也未把报告中的采样结论当成已验证事实。夹具全部为独立解析输入：坐标、半径、圆心与弧角完全给定，固定 XY 平面、固定深度 8 mm，只改变闭环数量和类型。

本任务**未连接 Toolkit、未启动/结束 Creo、未做会话探测或故障注入、未清理 unknown 保护**。实机驱动已编写但未运行。

## 改动与接口

- 新增 `src/creo_mechdog/profile_diagnostics.py`：对草图输入做解析分析，返回可确认的实体数、闭环/开链数、每个闭环的解析面积与嵌套深度，以及分类：
  - `intersecting`：两个闭环边界实质交叉；
  - `self_intersecting`：同一闭环自交；
  - `tangent`：两个不同闭环相切/接触，或同一闭环非相邻部分接触；
  - `zero_area`：闭环解析面积不超过 1e-9 mm²；
  - `near_tolerance`：端点仅在闭合容差 1e-4 mm 内相接；
  - `open` / `branched`：未闭合或单点连接超过两条曲线；没有可确认闭环时另记 `no_closed_contour`。
  相邻图元之间的正常相切（例如圆弧与直线相切连接）不在 `tangent` 中报告，避免把 G1 连续误判为非法；椭圆/样条等未实现解析的图元记为 `unsupported` 并使 `analysis="partial"`，此时不做静态拒绝。
- `schema.validate_operations` 对**同一计划内定义**的实体草图与其后的实心 `extrude`/`revolve` 做准入检查：只拒绝上述已由输入证明非法的组合；没有任何可确认闭环的草图同样拒绝；`mode="surface"`、`thin`（允许开链）以及引用计划外既有草图的实体不做静态判定。准入拒绝发生在作业创建前，不产生 job/model。
- `near_tolerance` 仅在显式 `dimensioning="coordinates"` 时视为致命：坐标模式的原生求解 epsilon 为 1e-9 mm，1e-4 级别的缝隙会以开链进入内核；`auto`/`autodim` 的 1e-4 epsilon 由原生决定，本轮不以静态检查替代。
- 合法多环（分离与合法嵌套）不分组、不并集、不吸附顶点，也没有新增“最多两个轮廓”的限制；一次 `extrude`/`revolve` 仍只引用一张草图并生成一个原生特征。
- 原生 `generic.cpp` 新增 `section_profile_summary`：按本机 SDK 头文件核对后使用 `ProSectionEntityIdsGet`、`ProSectionEntityGet`、`ProSectionEntityIsConstruction`、`ProSectionEntityIsProjection` 读取**求解后的 section**。统计排除构造几何、投影参照与坐标系实体，按 1e-6 mm 端点聚类给出 `entities`、`curves`、`standalone_curves`、`contours`、`closed_contours`、`open_ends`、`branched_points` 及查询/释放码，日志前缀 `SECTION_PROFILE`、`SECTION_PROFILE_OPEN`。空/失败查询只记录 `available=false` 与原始码，不使草图创建失败。
- 草图操作结果新增 `native_section`（上述真实计数）。`operation_results.annotate_profiles` 在持久化前为草图结果附加 `profile`（输入解析的环数、实体数、面积、各分类计数），`server.py`/`bridge.py` 的 compact 投影保留 `profile` 与 `native_section`。T02 的 `index`、`execution_status`、`effect_status` 及回滚语义未改。
- `section_create_failure` 不再断言“轮廓必须构成有效闭合截面”。有原生 section 计数时返回实际环数/实体数/开端点；`open_ends>0` 才明确说明不是闭合截面，否则明确“计数不能定位原因、原因未确定”，并保留 `ProFeatureWithoptionsCreate` 原码。该修改针对 R3 §4.2 的误导性报错，不以裸 -1 推断重叠或 contour 标记原因。
- `capabilities.py` 与 `creo_create_sketch` 说明补充多环支持、准入边界与诊断字段。未新增/停用 MCP 工具，未改忙拒、不排队、不重试、unknown 保护、T03 帧字段、T04 坐标回读门槛、T05 轴字段。

### 未实施的原生修复及理由

离线代码核对未发现按轮廓数量分支、自动分组/并集/吸附或 `PRO_E_STD_SECTION` 数量上限；多环输入走同一条实体添加与草图引用路径。R3 §4.1 的“5/10 个四弧环在 `ProFeatureWithoptionsCreate` 失败”在本轮无实机条件复现，缺少原始坐标包与原生日志，无法据此定位是闭合、方向、标注还是特征树缺口。按任务约定，先固定最小复现（现由 `tools/test_t06_native.py` 提供）再决定修复；本轮没有对弧构造、求解顺序或拉伸算法做猜测性改动。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4.0.0 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t06_multi_contours -q` | 15 项通过；覆盖 2/5/10 圆、5/10 四弧环、2 圆+5 四弧环、合法嵌套、五个非法类别分别拒绝、无闭合轮廓拒绝、近似容差在 coordinates/autodim 的差异、开链薄拉伸、surface/既有草图边界、椭圆跳过、结果与 compact 投影、按标签匹配 |
| `python -m unittest discover -s tests -q` | 837 项通过，耗时 217.784 秒（dev_check 内 204.828 秒）；既有套件无回归 |
| 变更 Python 的 Ruff check / format --check | 10 个文件通过，未新增风格基线豁免 |
| 项目 clang-format 23.1.3 对 `native/generic.cpp` | 通过；格式化差异只落在本次新增/修改行，无存量格式清理 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `AE3480D89918C651D9893580497C100EB4C2BD0FE7E69CA621CAD47C3444D5E8`，该生成物不入库 |
| `python tools/test_t06_native.py` | 输出 `OFFLINE ONLY`，未创建 MCP 客户端、未连接 Toolkit |
| `python tools/dev_check.py --work-item BUG-049` | exit 0、`success=true`、`unit_tests=passed`、`native_validation=not_run`；`style_summary` 为既有基线（lint 30、未格式化 16），无新增违规；证据 `build/development_check.json`、`build/t06-devcheck.log` |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `7182ef0b5008b5dcf63ae803a80727a667d45ad0`（dirty=true，仅既有 `session_activity.json` 本地改写与未跟踪运行文件），受测源码 `checked_source_sha256=50a030557cbe573ff9d26cafe13fb354b689ce41fcd23d26b6ee7f7d336c67ca`，生成时间 `2026-10-26T16:02:35Z`；单元结果 `Ran 837 tests in 204.828s` → `OK`。提交后仅追加本记录与台账文档，未再改源码。

### 夹具与解析断言（离线）

| 夹具 | 轮廓/实体 | 解析面积 | 深度 8 mm 体积 |
| --- | --- | --- | --- |
| 2 个独立圆，r=3 | 2 / 2 | `2πr²` | `2πr²·8` |
| 5 个独立圆 | 5 / 5 | `5πr²` | `5πr²·8` |
| 10 个独立圆 | 10 / 10 | `10πr²` | `10πr²·8` |
| 5 个四弧闭环 | 5 / 20 | `5πr²` | `5πr²·8` |
| 10 个四弧闭环 | 10 / 40 | `10πr²` | `10πr²·8` |
| 2 圆 + 5 四弧环 | 7 / 22 | `7πr²` | `7πr²·8` |
| 合法嵌套 R=10, r=4 | 2 / 2 | `π(R²−r²)` | `π(R²−r²)·8` |
| 非法：两圆相交 | — | — | 准入拒绝 `intersecting` |
| 非法：四线自交 | — | — | 准入拒绝 `self_intersecting` |
| 非法：零面积闭环 | — | — | 准入拒绝 `zero_area` |
| 非法：两圆外切 | — | — | 准入拒绝 `tangent` |
| 非法：1e-6 mm 缝隙 | — | — | coordinates 拒绝 `near_tolerance`；autodim 仅记录 |

单测直接断言环数、实体数、解析面积与各分类计数；未把 Python 解析当作 Creo 内核判定。原生侧的真实环数/实体数只能由实机 `native_section` 提供。

## 未测范围与 T13 实机矩阵（本次未执行）

1. 对每个合法夹具：先建立草图作业，断言 `native_section.closed_contours/entities/open_ends` 与输入一致；再以第二次作业拉伸，核对 `saved_file_reloaded_and_verified=true`、体积等于解析面积×深度、特征增量恰为 1 个 `protrusion`。
2. 基板 120×80×10 上用 2 圆与混合夹具做 `cut + through_all`，核对特征增量恰为 1 个 `cut`、体积为基板减解析面积×10。
3. 5 类非法输入与开链输入经 `creo_execute_plan` 返回 `isError`，信息含分类、环数/实体数与 `operations[index]`；不创建作业。
4. 基板上提交远离实体的切除，要求作业 failed、`rollback_succeeded=true`，revision/aliases/体积恢复，随后合法 2 圆切除成功。
5. 特别记录 5/10 四弧环在当前 Creo 12.4 上是否仍失败；失败时保存 `ProFeatureWithoptionsCreate` 原码、`native_section` 计数与完整报错，不据此推断根因。外部 Creo 10 原案例因附件缺失不复放，本机通过不外推到其他版本。

本次验收结论：**T06 离线实现完成，实机未验收，live 驱动未运行**。R3 §4.1 的 5/10 环失败未被本机复现，也没有据此修改原生几何算法；合法多环的单特征、体积、回滚与保存重载仍待 T13 在同一集成源码上取证。`docs/validation/` 历史原件、`session_activity.json` 本地修改及未跟踪运行文件保持原状。
