# MCP_CREO_MechDog 0.7.0 版本说明

日期：2026-10-27。本版为 0.5.2 三份外部反馈的完整交付（DEV-047，MINOR），基于
0.6.1。开发、实机与安装证据见
[发布验收记录](validation/RELEASE-0.7.0.md)，主干提交、正式附件与完整 SHA256 见
[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0)。
当前注册公开工具 94 个（前一版本 0.6.1 为 92，本版新增
`creo_plan_assembly_rebuild` 与 `creo_reclaim_generations`，实际可见清单以
`creo_capabilities` 为准）。

## 变更

- **T02 统一操作结果状态**（[DEV-047 基线 §2](work-items/DEV-047.md#interface-baseline)）：
  每个输入操作发布恰好一条带零基 `index` 的结果，新增
  `execution_status`（succeeded/failed/not_executed/unknown）与
  `effect_status`（committed/rolled_back/no_effect/unknown）；失败作业也返回完整
  operations 列表，失败项之后的输入补 `not_executed`+`no_effect`；
  `rolled_back` 仅在本机回滚实际恢复并核对保存基线后填写。种子绑定改挂
  `loft_seed_feature`，派生名称改用操作位置。
- **T03 平面引用显式化（BUG-084/FEAT-010）**：`datum_plane.id`/`plane.id` 与
  `axis`/`normal`/`offset` 筛选字段同时出现即拒绝（含默认值），Python 准入与
  原生边界同规则；草图结果回显实际解析的 `surface_id` 与 `origin/normal/u_axis/
  v_axis` 五项真实帧；Right/倾斜面用 ID、surface、标签引用得到同一物理帧。
- **T04 任意平面坐标标注（FEAT-010）**：字典平面 `coordinates` 准入解除主平面/
  section 轴对齐限制，非主平面不再拒绝或强制 autodim；中心线按无限线方向/偏移
  核验，斜中心线不生成端点尺寸；1e-5 mm 回读门槛与互斥边界不变。
- **T05 轴几何、方向与单位元数据（BUG-063/064/065 相关观测接口）**：巡检暴露
  基准轴 `origin/direction/geometry_known` 与 `data/line/free` 查询码；拉伸
  正负、对称总深与双向贯穿按实际帧验收；偏心轴阵列以有向轴旋转闭环。单位元数据
  （`units`、`units_query_code`、`length_unit.name/scale_to_mm/query codes`、
  `center_of_gravity`、`volume_mm3/volume_query_code`）报告真实值：毫米与英寸
  实机矩阵均通过（英寸件经 SAME_SIZE 夹具转换，原始英寸重心/轴坐标与 25.4 换算
  闭环；非毫米 `volume_mm3` 按契约为 null，不把 in³ 标成 mm³）；unknown 单位
  仅替身/单元覆盖（实机不可无注入诱导）。收养拒绝的单位元数据在拆分形态下不再
  把已知单位报 unknown（随版修复）。
- **T06 多环截面诊断**：计划内实心拉伸/回转的草图输入给出闭环/开链数、实体数、
  解析面积与嵌套深度，分类记录相交/自交/相切/零面积/近容差/开链/分叉；
  `section_profile_summary` 按 section 真实图元统计并回显 `native_section`；
  `section_create_failure` 引用真实计数，只有 `open_ends>0` 才判定非闭合。合法
  多环不分组、不并集、不吸附、无两环上限。
- **T07 预览投影（BUG-066 相关）**：作业与操作结果新增 `preview`/`preview_status`
  （written/failed/not_attempted），只在有原生证据时投影；声明 written 但文件
  缺失/空字节降级 failed；compact 保留 `preview`/`preview_file` 等字段。本机统一
  预览路径的实体轮廓完整性经留存图像逐张目视复核（对象/视图正确、阵列孔数与解析
  体积互证）；原始报告的星形架失真形态未复现，BUG-066 维持待复现。
- **T08 零件特征生命周期（FEAT-036/027）**：`creo_execute_plan` 新增
  `op="feature_state"`（action=delete/suppress/resume，targets 显式标签或特征
  ID）。抑制保留身份、删除保留标签墓碑且旧名不可复用；`targets` 未覆盖受影响
  依赖时返回依赖清单并拒绝，原生执行前复核，**不自动级联**（Creo 对伴随基准的
  隐式抑制/删除会被拦截并要求显式列出）。有意抑制集合参与健康、保存重载与回滚
  比较；full 快照 whole 路径同样携带 `feature_state` 段。
- **T09 约束回放规划（FEAT-049，新增工具 `creo_plan_assembly_rebuild`）**：只读
  规划器把冻结装配快照+显式 component_mapping/reference_mapping 转为
  `creo_execute_plan` 可用的操作序列；装配侧同层兄弟引用以
  `assembly_component` 显式表达；先插入全部组件再按组件**整组**设置约束
  （原生 setter 替换整组约束集，逐约束生成会静默丢失）；六类既有约束+fixed/default
  真实语义；绑定源件 revision/摘要并在提交时复核。规划不加载、不收养、不修改
  原装配。
- **T10 会话健康证据（BUG-078）**：公开状态新增 `session_health`
  （unknown/suspected_damage/no_failure_observed）与 `next_steps`；只读路径不触发
  新 Toolkit 调用。三历史现场经一次只读 inspect 落定（均仅 `restore_baseline`
  可用，未 apply、未清保护），恢复按操作者选择执行。
- **T11 显式世代回收（DEV-027，新增工具 `creo_reclaim_generations`）**：
  `mode=inspect|apply` 显式选择 loader/payload 世代；600 秒证据令牌绑定目标、目录
  内容摘要与引用证据；apply 复用通道锁互斥、路径限定 `build/blend_loader|blend_callback`
  自有根、拒绝穿越/重解析点，幂等键回放不重复删除；当前/注册/运行中/回退保留世代
  一律保留。启动与普通查询不自动清理。
- **T12 官方示例与单位回归**：新增
  `examples/dev047_t12_batch_append.json`（一次计划 6 特征、单次 revision、整作业
  回滚）与 `examples/dev047_t12_draft_boss.json`（巡检取得圆柱面真实几何 ID 后
  11° 拔模，圆台/圆柱/外扩三向体积解析断言；默认方向外扩、flip 收窄为实测事实）；
  README 固定毫米/英寸/混合/未知单位矩阵验收模板。
- **T13 集成矩阵与五处生产修复**：实机矩阵暴露并修复——`system_required` 误标
  导致抑制死锁、抑制/删除隐式级联未拦截、full 快照 whole 路径缺 `feature_state`
  段、回放规划逐约束生成致整组替换只留最后一条、收养拒绝在拆分形态下把已知单位
  报 unknown。失败尝试原始报告全部保留。
- **版本与种子元数据**：`version.py` 0.7.0；两份种子 manifest 的
  `compatible_server_version` 同步 0.7.0；9 个种子 PRT 原字节不变；种子包按
  0.7.0 确定性重打包，`seeds.py` 的 `expected_digest` 更新为新包实测 SHA256
  （`515ef9d356a6d5582879fc736c43d0a7408fc15915605f04ded2bb5f991fd114`）。

## 兼容与迁移

- 新增公开工具 2 个（92→94）；既有工具入口保持兼容，`execution_status`/
  `effect_status`/`preview`/`component_changes` 等均为新增结构，旧客户端可忽略。
- **准入收紧（不兼容边缘）**：`datum_plane`/`plane` 引用中显式 `id` 与任何筛选
  字段（含默认值）同时出现现在**拒绝**；旧调用同时传两者时原先忽略筛选、现在须
  删除其一。
- **feature_state 语义**：抑制/删除不再自动级联到伴随基准——Creo 会隐式抑制/删除
  的每个特征都必须显式列入 `targets`，否则整批拒绝并返回依赖清单（响应消息含
  `feature_id` 列表）。
- 非毫米模型的 `volume_mm3` 为 `null`（查询码 0），毫米换算经 `length_unit.
  scale_to_mm` 由调用方完成；坐标/重心保留模型原单位。
- 种子包/源码包按 0.7.0 重打包；0.6.1 及更早版本种子包不再被
  `creo_install_seed_library` 接受（按版本与摘要校验，属既有契约）。

## 验证与未测

- 本机 Windows 11 x64 / Python 3.12.14 / Creo 12.4.0.0 / 匹配 SDK 与 MSVC：
  全量 **966 项单元测试通过**（0 失败 0 错误），dev_check 增量风格通过（存量
  30 lint/16 未格式化文件基线未新增容许项），SDK 离线构建通过。
- 本机实机矩阵（单一 Toolkit 通道串行、先只读核验会话）：T05 毫米几何矩阵 18/18
  与英寸只读覆盖、T06 多环、T07 预览+图像目视、T08 生命周期（含级联发现与失败
  回滚）、T09 约束回放（随动/方向/单位/保存重载）、T12 批量/拔模双方向、装配
  单位专项复跑（38 作业）全部通过；成功作业均 `saved_file_reloaded_and_verified`
  、预期失败作业均 `rollback_succeeded`。
- 安装/解包：0.7.0 公开源码包在新目录完整 `setup.ps1`（依赖、editable 安装、
  九种子哈希、常量生成、loader/callback/worker 编译）exit 0，版本导入为 0.7.0；
  详见[发布验收记录](validation/RELEASE-0.7.0.md)。
- **未测**：WorkBuddy 黑盒验收按用户 2026-10-26 决定本批不执行；外部 Creo 9
  （本机无 SDK，实机编译与运行时未验收）与 Creo 10（独立复测非门槛）未复测；
  unknown 单位/查询失败仅离线替身与单元覆盖；BUG-078 三个历史现场仅只读落定、
  未 apply；BUG-066 原始失真未复现；FEAT-050 公共装配比对、嵌套回放、新约束
  类型、世代二进制可复现性等父卡其余范围不在本批。旧版本通过数不外推为本版
  通过。
