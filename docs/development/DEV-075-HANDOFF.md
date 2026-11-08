# DEV-075：离线结果与另一 AI 接手清单

日期：2026-11-07。分支：`codex/DEV-075-feedback0181-offline`；起点：`828b1f2`，版本保持0.18.0。[工作卡](../work-items/DEV-075.md)、[逐项对照](../validation/feedback-0.18.1-2026-11-07/MAPPING.md)、[验证结果](DEV-075-ACCEPTANCE.md)。最终冻结分发2878项0失败/0错误、2项SDK跳过后本机另补通过；样式门禁通过，详见验收记录。本次未合main、未发布；若后续合main，必须另定未发布版本并在同一交付流程正式发布Release。

## 已完成或已有成果

本批补齐有界参数诊断（保留ValidationError接口）、装配质量查询拒绝、质量克值单位/原生单位/来源、材料失败原因与请求兜底清理、负body ID专项拒绝、thin/revolve/new_body准确边界、只读job_id说明、FEAT-057/059交付子项和版本台账、DEV-072本地逐ID表及历史测试路径勘误；源码包补齐遗漏的7个原生测试C++夹具，SDK输出校验崩溃继续保留其遮蔽行为。

此前DEV-074已完成无Git来源降级、结构化最近边、未知特征ID语义、有效板厚布尔、空预览依据与过期快照说明。本轮复用，不重复认领；报告方Creo10的box_frame/ISO M6/new_body/实体间union成功只作为外部证据。

## 未完成，按接手顺序

| 编号 / 条目 | 当前事实 | 下一动作与验收 |
| --- | --- | --- |
| H01 / FEAT-058，P1 | origin=[-92.5,-116]大跨度resize的17200≠6000缺陷未由本批修复。工作区另有流程改动native/planar_wall.cpp，不属于本批提交，接手先核对实际分支/差异，避免覆盖。 | 先读DEV-074-HANDOFF H01和现有PLANAR_WALL_RESIZE_DIMENSION日志；确认会话健康并获实机授权后核5个坐标尺寸符号/解算分支，再最小修复。覆盖零/正/负/混合origin、跨/不跨轴、恒等/缩放、XY/XZ/YZ、厚度方向、同/跨计划、保存擦除重载、失败回滚后继续编辑。保留体积和包络守卫。 |
| H02 / FEAT-014、BUG-046/040，P1 | 钣金主体与实体材料融合、附着凸台/百叶/铰链/耳没有已验证原生路线；负ID现为准确拒绝，仍未开放。thin/revolve增料body归属、merged_into_body_id、inspection.boolean_referenceable未实现。 | 原生核对真实body类型/选择/目标body，不以ID正负或当前活动体猜测可融合；显式区分格式错误、未支持、空占位与实际body。先测solid-solid、sheetmetal-solid两个方向、native_planar/conversion、thin/revolve、new_body，有真实归属和保存重载证据再加字段/开放路线。连续多边/共享角/relief、12百叶/64格栅/4凸台、X侧框边/止口、0.2 mm角缝与R2.54/R3圆角逐项安排；out5多实体近似不能宣称单体精确复原。 |
| H03 / FEAT-057，P1 | 本批装配拒绝、材料失败原因、质量来源/单位和重心换算仅离线单测/编译。英寸体积仍为null，未交付英寸质量换算；主惯量、complete和occurrence汇总尚未交付。 | 重编译并重启正确dev服务后，通过公开MCP验证空/有组件装配（含显式密度）拒绝且不改revision/源文件；零件/钣金测原生材料、缺密度、材料查询失败+显式fallback、g/kg/tonne/未知质量单位、mm/in/未知长度单位，核mass_value_unit=g、native_mass_unit、mass_source、原始查询码、null原因和重心，保存重载。装配汇总需单独设计完整性契约，不能恢复整装配均质fallback。 |
| H04 / FEAT-035 | Creo10 depth_scheme_code=-1仍缺可信元素树读回；正向M6线程证据来自报告方0.18.0。 | 实机核PRO_E_HLE_DEPTH_DIM_TYPE存在性、路径和查询码，覆盖tip/not_tip/unknown；未知保持明确未知，不能以体积推断作为元素树读回。 |
| H05 / DEV-074/075、FEAT-058/014 | 新错误文本/负ID诊断、结构化候选compact、有效板厚和失败ID字段没有本轮WorkBuddy验收。 | WorkBuddy只调用公开MCP，不看源码/配置、不跑本地测试。测负/零密度、M7/超深孔、负bodyID、故意失配edge_geometry与失败resize；记录原始调用/输入、job/model/revision、终态、回滚和保存重载。没有真实并发调用就不能报并发通过。 |
| H06 / FEAT-059/063及曲面历史余项 | 事务日志已交付，原生骨架/绑定未实现；box_frame仅唯一固定模板。曲面loft/merge/闭合测量/非平面fill/曲面fillet/薄壁整链继续开放。 | 先复用现有计划和DEV-074-HANDOFF H02—H10，按原生路线逐项取得几何/保存重载证据；不要因本目录反馈扩写未授权新工具或绕过门禁。 |
| H07 / DEV-072/074/075 | 本轮未核远端0.18.1/tag/main/Release/四附件/body。报告有外部下载通过陈述，没有其_local原始JSON/日志。其它流程新增的POSTCHECK须独立检查来源和时间。 | 联网后执行check_release_assets精确tag，记录Asia/Shanghai时间、tag提交/主干、四件名/大小/API digest、本地SHA256/sidecar/body。写新POSTCHECK，不移动标签或覆盖附件，不把外部摘要冒充本地实算。需补旧原稿时索取真实文件再归档。 |

## 2026-11-08 新增DEV-066报告的后续工作

新增报告及逐项对照见[归档映射](../validation/feedback-dev066-0.18.1-2026-11-07/MAPPING.md)，本批实测见[DEV-066验收记录](DEV-066-ACCEPTANCE-2026-11-08.md)：无Git/无.git全量2884项0失败/0错误、2项SDK在本机补测通过；新报告记录跳过原因和358.797秒耗时，日志无裸ERROR。当前代码8def1e4补齐tools来源读取迁移、报告跳过项/耗时/来源、可选Git环境提示、负例capture和会话日志取消跟踪；缺Git仍保留目录SHA256，Git身份null且标明scope。原生resize的暂停前未提交修改在续做时已不在当前源码，未在本批恢复，不得据旧卡文字判为当前已交付。

| 编号 / 条目 | 本次未做与下一步 | 验收边界 |
| --- | --- | --- |
| H08 / DEV-066、FEAT-020 | `test_update_check`只验证无Git来源构建，真实联网检查流程未运行；`startup_retry`/`toolkit_channel`/`toolkit_recovery`仅用拦截客户端的离线入口回归。需要客户端/健康Creo时再按既有授权条件执行。冻结历史`docs/validation/.../g0_driver.py`仍有Git调用，不改原件；需要时用当前受支持驱动或为历史复现提供本机Git。 | 来源降级通过不等于更新网络、重启恢复、真实并发/故障注入通过。WorkBuddy只调用公开MCP观察`creo_check_environment.development_tools`，不读源码/配置、不运行本地脚本。 |
| H09 / DEV-066 | 取消跟踪保留了当前`session_activity.json`原路径和字节，未演练从仍跟踪该文件的旧tag升级。历史tag/附件不重写；旧版本操作前仍先备份。原卡的`lock_files.open_lock_file`瞬时WinError5低优先级问题没有当前复现，不当作已修。 | 在隔离副本演练旧版tracked日志→新版ignore（先自带夹具和备份，不碰真实日志），核丢失/覆盖保护和读取兼容；锁问题先复现并保留并发/保护语义，未确认前不得清锁或unknown。 |

本批尚未合main或发布；旧0.18.1仍是报告方受测代码，不能标成包含本地修复。需要发布时选未发布版本、对齐各卡与元数据，并按同次Release/四附件规则完成远端后核对，沿用H07。

## 接手约束

本机只启用MCP_CREO_MechDog_dev并指向本仓库。执行前先核BUG-001恢复记录和可操作会话；不得擅自连接、结束Creo、清unknown或做故障注入。本次未进行Creo建模或远端核对，最后分发回归禁止pip访问索引；编译不等于运行时验收。

用户原有DEV-054、tools/test_toolkit_recovery.py、tools/test_update_check.py、.trae/及FEAT-014计划未纳入本批；开发期间另有流程修改原生resize和多个测试来源入口，均保留，不随本批提交。接手先git status/diff，测试证据须注明实际组合源码与dirty状态。

运行期间出现的toolkit-channel.json是未跟踪运行数据，不纳入本批，未清理占用或unknown。另有流程文件仅做过格式整理，未带入本批提交。原始反馈提到的宿主删除守卫干扰属于其环境事实，本次隔离分发验证不等于修复或复现了该宿主限制。
