# DEV-047 / T05 轴几何与倾斜拉伸解析验收准备

日期：2026-10-26（Asia/Shanghai）。条目：BUG-063/064/065，关联 BUG-084。基线 `479ee5a`（T00/T01/T03/T04 已纳入）；分支 `codex/dev047-t05-axis-geometry`；本次源码版本仍为 0.6.1，目标 0.7.0 的集成和发布留待后续交付。

## 首次离线交付阶段结论（截至 1a53f34）

轴几何观测、单位/质量查询元数据、公共投影和解析验收驱动已离线实现。**没有连接 Toolkit，也没有完成 T05 原生验收。** 现有 BUG-001 会话限制保持，没有会话探测、故障注入、清理 unknown 保护或结束 Creo。原报告中的拉伸全局 Z、两平面建轴退化和独立阵列算法缺陷均未被本次证实；本次没有修改这些算法。

## 接口与实现

- `datum_axis` 成功操作详情提供 `datum_axes`、`axes_query_code`、`length_unit`，compact `creo_get_job` 保留这些字段。保持原 `operations` 集合，后续 T02 去重须保留新字段。
- 原生巡检提供 `datum_axes` 段，可经 `creo_inspect_model(detail="full", section="datum_axes")` 使用既有快照、游标和 32 KiB 预算分页。每条含轴几何 `id`、所属 `feature_id`、`origin`、单位方向 `direction`、`geometry_known` 与枚举/数据/直线/释放原始查询码；特征段保留 `axes_query_code`，包括枚举失败而没有轴记录的情况。
- 轴由 `ProFeatureGeomitemVisit(PRO_AXIS)` → `ProGeomitemdataGet` → `ProLinedataGet` 读取。`origin` 为原生无限轴线上一个点，方向由真实两端点差归一化，不使用约束或选择条件猜测。退化、非有限、查询失败或无可用数据均使几何未知；未执行的查询码是 null。任何已分配的数据均尝试释放，释放码不隐藏。
- 操作同层/巡检同层 `length_unit` 提供实际名称、原始单位查询码、`scale_to_mm`、`scale_to_mm_known` 和毫米单位/转换原码。未知名称或查询失败不会默认毫米；未执行的转换原码为 null。轴原点、实体边界、曲面原点及 `center_of_gravity` 均保留原生坐标。质量查询未执行或失败时重心为 null，`volume_query_code` 为实际码或 null。原有 `volume_mm3` 的仅毫米策略不变。
- worker 构建依赖扫描会包含新头文件；公共服务源码身份清单同步纳入实际修改的轴/单位头文件。SDK 替身不连接 Creo。

## 解析驱动与断言

`tools/test_t05_native.py` 导入或默认执行只走离线路径，不创建 MCP 客户端。实机入口需要显式 `--live --confirm-session-usable`，并确认本机配置禁用自动 Creo 启动后才创建客户端；不得用等待超时当作人工会话确认。服务仍执行既有后台准备，驱动在 180 秒预算内只读轮询 `creo_startup_status`，busy/unknown/waiting_for_channel 等非准备态即停止，不提交启动或 retry 指令；ready 后再显式探测既有会话。实际执行后保存原始调用、输入、job/model、终态、快照及 provenance。只轮询已受理作业；busy/错误立即停止，无重提或自动重试。

1. 固定倾斜法向 `(0.587785,0.809017,0)`（先核对实际平面与请求平行），U 为 +Z；10×20 居中截面、4 mm 盲深度，覆盖正/反/对称。使用实际 T03 frame 计算完整八顶点 AABB、重心和 800 mm³；对称 depth 为总深度，主平面作对照。不能仅凭体积判方向正确。
2. 同一截面建立跨越草图两侧的 12 mm 对称实体，再以 2×4 截面正向/反向/对称 through_all 切除。预期分别去料 48/48/96 mm³，核对完整边界及重心；这会区分单向和双向贯穿。当前元素树的 symmetric+through_all 设置尚待实测，未凭静态疑点改算法。
3. 偏心 `(4,-3)` 的两平面交线轴与直径 60 基体柱面轴各自读取真实几何；平面先查真实法向/几何 ID，再按显式 ID 建轴。操作结果为保存前测量，巡检是保存重载后测量；按无限直线共线及平行性核对，不要求无限线上原点坐标完全相等。
4. 半径 1、穿越 6 mm 基体的孔绕半径 12 的轨道阵列；两种轴来源 × count=2/10 × ±36°，另加过原点对照。Rodrigues 公式使用保存快照的有向轴，每个实际孔的圆柱面轴心必须和解析位置完整一一对应；少孔、多孔、重复和错位均拒绝。额外去料为 `(count-1)×π×1²×6`，没有通用百分比或 5 倍阈值。
5. 每个成功作业要求 `saved_file_reloaded_and_verified=true`；每组阵列后提交不相交切除，要求 failed、真实 rollback_succeeded、revision/aliases/孔位置/体积恢复。现有 native `verify_saved` 未新增一般轴比较；驱动显式比较实际轴和所有孔的重载几何，因此不能把原有保存标志单独当作轴几何通过。

该驱动尚未实跑，原生 API/角度有向约定及实际拓扑可能暴露需核对之处。斜交平面、单平面法向建轴、surface+autodim 与 Right ±Z 的完整历史回归，以及英寸模型上的真实轴/重心查询也未执行；离线 inch/unknown 单位替身不能替代这些实机结论。混合单位零件轴本身无定义（每个零件有一个主长度单位），装配混合单位仍归既有接口范围。

## 已执行的离线检查

环境：Windows x64，Python 3.12.14；匹配 Creo 12.4.0.0 Toolkit SDK / MSVC x64，仅编译与替身链接。生成的执行器、日志及测试报告保存在忽略的 `build/`，不入源码或附件。

| 命令/检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_t05_geometry tests.unit.test_model_queries tests.unit.test_t03_plane_reference -v` | 首轮 30 项通过；覆盖 compact 轴/失败码、快照分页、CG/单位未知值、解析方向/深度/完整匹配和双标志保护；最终加入 `tests.unit.test_helper_layout` 后 40 项全部通过（1.797 秒），含源码身份/禁自动启动/provenance、只读准备观察及非 ready/超时不重提回归 |
| `python tools/test_axis_geometry.py` | 13 个替身案例通过；真实 SDK 声明，替换几何与单位查询；非原点/负向轴、零长/非有限/读取失败、分配释放、mm/in/空名/单位失败/转换失败；不是 Creo 建模证据 |
| `python tools/test_t05_native.py` | 输出 OFFLINE ONLY，没有创建 MCP 客户端或连接 Toolkit |
| 变更 Python 的 Ruff 检查与格式检查、原生 clang-format 检查 | 6 个 Python 文件和 4 个原生文件最终检查通过；只格式化本次新增行/文件，没有存量格式清理或基线豁免 |
| `python bridge.py build` | 初轮和最终匹配 SDK 原生执行器构建通过；最终 `creo_worker.exe` SHA256 `873AA876FBE761328604E451CC2507C9C795A521BD2D7B27168DD5CD520207D4`；`build/source.sha256=1eb1b8f4887d08de18b7de6a8f750f2d93f203278243bdc96c9bf7d0bac48921`。构建保留既有非 ASCII 注释引发的 C4819 警告（assembly_units/assembly_walk/generic），无本次新增诊断类别 |
| 集成负责人 `python tools/dev_check.py --work-item BUG-065` | exit 0、success=true、unit_tests=passed；795 项完整单元，0 失败/0 错误、227.585 秒，native_validation=not_run。证据 `build/t05-development-check-full.json`、`build/t05-unit-test-report.json` |
| 集成负责人 `python tools/dev_check.py --work-item BUG-065 --skip-unit` | 最终源码上 exit 0、success=true、unit_tests=not_run、native_validation=not_run；证据 `build/t05-development-check-final.json`。完整单元早于最后的驱动/provenance/源码身份诊断改动，最后这些改动由 40 项专项和本次最终语言检查覆盖，没有声称再次全量单元 |

SDK 替身首次链接遇到 `ProUnitInit` 声明中 `wchar_t *` 与替身 `const wchar_t *` 不匹配，已按安装 SDK 更正，后续替身编译/执行通过。首次 worker 编译通过后又加入空单位名 guard 与无重复查询元数据收敛，最终构建已覆盖这些变更。

完整 dev_check 指纹：基线提交 `479ee5a7fa6574f237d32e33a8f2a358c478a654`、dirty=true，时间 `2026-10-26T12:06:25.778463+00:00`，`checked_source_sha256=f17b7c8953bb97aafea152796cdc5bcce278b370f4f900a01686e6d65f93153c`。最终语言检查相同基线、dirty=true，`checked_source_sha256=4e6f16f6b8cbc82c1fad41258af4d178f2f3655a4ea550771c97b4c089c335bc`（覆盖并替代较早 `9048b1fc...` 的中间诊断检查）。后者包含最终源码身份、驱动安全/证据和准备态观察变更。替身报告 `build/axis_geometry_test/report.json` 另记录实际源码/协作头文件与三个 SDK 头文件 SHA256。

工作区原有 `session_activity.json` 内容 SHA256 为 `CF869B454E9492DD314FD10B296F6995334E2C6128803A28365FFCB1E1028378`，保持不变。未跟踪 `.codebuddy/`、`.workbuddy/`、`.zcode/`、PRT 和 session_erase 运行记录保持原状。历史 `docs/validation/` 不变；源码提交与最终 dirty/指纹由任务报告及后续集成记录补录。

## 人工确认后的 Live01 尝试与审查修正

用户随后明确确认 Creo 已恢复并授权继续本次实机测试。根协调者独占 Toolkit 通道运行受控驱动；运行包装临时将忽略的本机配置 `auto_start_creo` 设为 false，并在 finally 恢复原始文件字节。本实现者和审查者没有额外连接 Toolkit、重试、关闭 Creo 或清除保护。

Live01 受测提交 `1a53f3419c31767e678c8e7d1b81b85c0fb193d0`、dirty=true，驱动 provenance 源码指纹 `7d6367a493c40f3f18a2e3889b25d1edb8fc5cc926b0d8715d5605d4500decd4`。原始证据 `build/t05-native-01.json`（SHA256 `FD82406D7D72126CFE69046CF670E5D60ACF2D16102E8640AC2B43F503A6E5CB`）及 `build/t05-native-01.log`（SHA256 `9849591807939C2DECD469B5EC4A6F0675BAB3E92B373B62E729080D65B5A495`）保持不变。报告记录 14 次公开能力/环境/启动状态调用，**0 次 execute_plan、0 个几何案例**。启动准备的 9 秒状态探测于 `2026-10-26T12:29:50Z` 返回 `probe_timeout`、`toolkit_code=null`，未取得可用连接核验结果，驱动在非 ready 状态停止。探测覆盖连接、当前模型、版本和断开等原生步骤，现有证据无法定位停在哪一个调用，也不能证明从未建立过连接。没有模型提交或几何失败可以据此分析；它不能证明 T05 通过、不能证明建模算法存在缺陷，也不能把探测超时等同 Creo 已卡死。

根协调者补充的桌面观察：Computer Use 读到 Creo 12 欢迎页，截图为黑色；激活尝试遇到 `GetCursorPos` 拒绝访问 `0x80070005`。这些观察未确定原因或证明会话可操作；人工桌面核对仍待完成，不据此主动重启、结束进程或清除保护。

独立审查未发现重要生产代码缺陷，指出 P2 驱动完成毫米矩阵后不能报告整个 T05 native_acceptance=passed，以及 P3 客户端异常时未记录实际尝试调用。本次只修正驱动报告与证据逻辑：毫米矩阵成功时为 `metric_geometry_matrix=passed`，整体为 `native_acceptance=partial`；实际非毫米坐标、unknown 单位/查询失败原生覆盖明确 pending，混合单位标为单零件矩阵不适用并要求独立装配证据。非毫米验收需要另行限定的只读原生夹具，本次不扩展非毫米受管编辑。

每次工具尝试在 await 前持久化工具名/输入和 response_received=false/outcome=unknown；传输异常保留类型/消息，仍为未收到响应、结果未知，不合成原生结果、不声称提交被拒绝、不自动重试。离线模拟覆盖完整毫米矩阵也不能产生整体 passed，并在抛出 TimeoutError 前检查磁盘已有调用输入，抛出后检查异常与 unknown 保留且只尝试一次。

复核命令：`python -m unittest tests.unit.test_t05_geometry tests.unit.test_model_queries tests.unit.test_t03_plane_reference tests.unit.test_helper_layout -q`，42 项通过（1.931 秒）；两项变更文件 Ruff check 与 format 通过。本次没有再运行原生驱动或 SDK 构建，生产原生源码未改；最终语言检查与定向复审由根协调者补录。**T05 几何与原生非毫米/unknown 验收均仍未完成。**
