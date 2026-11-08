# 0.18.1 文件夹三份报告与当前源码对照

日期：2026-11-07，批次 [DEV-075](../../work-items/DEV-075.md)。基线 `828b1f2`，源码版本0.18.0。文件夹名称不代表当前已安装/已发布版本；本次未联网核对0.18.1。三份原件的长度、SHA256及原路径见 [manifest.json](manifest.json)，复制后逐字节一致。

报告方运行环境与本次离线环境分开：F01/F02 的建模实测来自0.18.0 / Creo10，F02对0.18.1仅静态源码推断；F03为Python3.13 / Creo10 SDK安装、编译和文件检查，未连接Creo。本次没有任何新的Creo建模结论。

## F01：参数诊断、质量属性、resize与新增能力

| 原文范围 | 对照与处理 | 归属 |
| --- | --- | --- |
| §1.1 box_frame 原样提交，35712 mm³、重载通过 | 当前规划器及模板目录已存在，capabilities.product_rules.templates已含box_frame，docs/PRODUCT_RULES.md有参数/扩展边界。归档为报告方正证据，不把工具静态native=not_run回填为本机实测。 | FEAT-063 |
| §1.2 ISO/M6螺纹写入读回 | 表、schema、原生thread_readback已存在。报告方证明其Creo10样本通过；本次只回归离线标准孔。 | FEAT-035 |
| §1.3、§3 装配误算、单位冲突、来源和材料失败诊断 | 8d71e6c已补原因枚举，但装配仍可进入原生fallback；本次Python单工具/计划和原生拒绝装配，新增mass_value_unit=g/native_mass_unit/mass_source，保留mass_unit兼容语义；原生request成功清除旧失败原因，无请求时保留真正材料失败原因；重心按实际单位换算（未知为null）。 | FEAT-057 / DEV-075 |
| §2 负密度、表外M7、thread_depth超限倾倒联合类型 | 已离线复现；包内OperationValidationError保留ValidationError类型和errors()接口，str()仅输出有界路径/原因，不序列化输入字典、联合类型标题或Pydantic网址。单操作去掉内部0/op前缀、多操作保留index。 | DEV-075 |
| §4 origin≠0大跨度resize、钣金增料 | 功能未完成。DEV-074已有逐尺寸/包络日志，本轮发现工作区有其它流程正在修改原生resize，不归入本批完成声明。保留体积/包络保护。 | FEAT-058 / FEAT-014 / H01—H02 |
| §4 ID未知却unchanged=true、候选compact截断、板厚多布尔 | DEV-074已有未知ID=null、loaded空键、结构化候选和thickness_verified_effective，不重复实现；新字段实机仍未验。 | DEV-074 / H05 |
| §5.1 depth_scheme_code=-1 | 已有原生读取；未知码不能当作已确认深度方案。本轮不凭206.18 mm³推断原生树，交实机读回。 | FEAT-035 / H04 |
| §5.2只读工具job_id | 工具说明明确同步返回已完成查询，job_id是执行记录标识，不必再轮询。 | FEAT-057 |
| §5.3模板清单 | 当前capabilities和PRODUCT_RULES已有，不新增第二套目录。 | FEAT-063 |
| §6—9钣金/曲面余项与未测范围 | 外部miter/box_frame/螺纹正证据仅归档；out4欠缺、FEAT-059原生骨架、WorkBuddy/并发/性能仍不宣称完成。 | H02/H06，DEV-074-HANDOFF |

## F02：多实体近似与钣金融合

| 原文范围 | 对照与处理 | 归属 |
| --- | --- | --- |
| §1—4、§7 out5独立体增料、正ID实体间union成功 | 已有new_body路径和BUG-046边界；报告方Creo10正证据保留。单实体拓扑没有达成，不能把多实体近似当成精确复原。 | FEAT-014 / BUG-046 |
| A1钣金附着增料、A6连续多边/百叶/格栅/relief/resize | 缺原生路线/验收，继续交接，不放开融合、不新造未实现算子。 | H01/H02 |
| A2负body ID | 保留布尔不支持门禁，校验改为BOOLEAN_BODY_REFERENCE_UNSUPPORTED专项原因；与kind/id格式错误分开。不从负号推断body无效、不把正ID视为保证可融合。inspection尚无可靠原生可用性标记，未制造boolean_referenceable。 | DEV-075 / BUG-040 |
| A3联合类型长报错 | 同F01统一错误映射及回归。 | DEV-075 |
| A4 thin归属、A5 revolve(add)边界 | 文案/语法参考明确thin/revolve不受当前extrude门禁不等于已验证钣金附着，new_body不保证后续融合；准入逻辑保持。merged_into_body_id需真实原生读取，仍未实现。 | H02 |
| §8证据边界 | 0.18.1未装机；不得写成本轮或0.18.1实机通过。 | 全局 |

## F03：版本入口、台账、源码包与发布记录

| 原文范围 | 对照与处理 | 归属 |
| --- | --- | --- |
| §二四附件、1477文件、Creo10 SDK编译、回调/种子/196项 | 仅报告方证据，本次不联网、不重注册，不复述为本机通过。 | DEV-072 / 外部正证据 |
| P1-1、门禁2744/2762/2826 | DEV-074已同步RELEASING到0.18.0并按阶段解释历史数字。本次不重写历史日志，新增勘误索引。 | DEV-074 |
| P1-2 FEAT-057/059卡首页与主台账 | 本次明确已交付0.18.0子项与具体未排期余项，消除当前“未实施”误读。 | DEV-075 |
| P1-3无.git导致T07十三ERROR | DEV-074已修公共source_provenance与T07入口，已有无Git分发2850项证据。本轮再验证当前组合源码，不重复开发既有修复；实际分发全量另发现白名单遗漏7件原生测试C++夹具，已补入tools/package.py并加回归，不改历史包。 | DEV-066/074 |
| P2 DEV-072空表/缺POSTCHECK | 本次填四个实际交付ID本地核对；历史候选表不能补造。另有流程新增POSTCHECK不计本批联网核验；本轮远端仍未查。 | H07 |
| P3 test_hole_standards.py误引 | 历史validation冻结，新增DEV-075-RELEASE-ERRATA.md指向test_standard_holes.py。 | DEV-075 |
| P3台账统计、API asset-ID下载回退、早期原稿 | 历史统计注明日期、asset-ID路线及原稿归档已由DEV-074完成；新增DEV-075按当前行重新统计。未提供的旧原稿不制造。 | DEV-074 / H07 |
| §五未覆盖、§六优先级、§七外部证据路径 | 报告方宿主删除守卫导致未跑全量的限制未在本轮环境复现；没有报告方_local目录原始JSON/日志或实际下载件，不猜API digest/发布状态，不把196项子集写成全量。 | H07 |

本次验证和余项见 [验收记录](../../development/DEV-075-ACCEPTANCE.md)、[接手清单](../../development/DEV-075-HANDOFF.md)。
