# DEV-076 曲面报告增量对照与接手

2026-11-08。报告是外部Creo10反馈，包含MCP回执陈述及源码/SDK分析（含本地补丁）；没有原始JSON，不将整份报告视为符合本项目约定的WorkBuddy验收，不作为本轮原生验收；源文件逐字节归档见manifest.json。这里不执行其建议的枚举值内联或按release解禁。

| 报告项 | 与当前分支对照/本次处理 | 仍未完成 |
| --- | --- | --- |
| P0-1 loft缺头却enabled | 前批已解决整包编译阻断，但缺头仅返回不可用；本次补availability=sdk_conditional、sdk_requirements和enabled含义 | H13：从受信worker构建身份投影动态可用性并在提交前拒绝；不能用Python本机SDK推断已加载worker，也不只按release_numeric猜。Creo10无头完整放样须定位真实枚举/创建路线并验收，不能猜常量 |
| P0-2 开放带面trim | 新增“相交未必能分割区域”的失败排查提示，能力limits同步；不宣称已测交线/已定因，也不一概拒绝开放工具 | H14：真实交线数量/闭环/边界连接/长度及原始码；extend_to_loop需另设计，开放弧是否借目标边界形成有效区域须测 |
| P1-1 state_reason | 已复现生产函数edges_available=true、open_edges=2、gap不可用时错误reason；改open_edges_present，gap_status保持原始原因，四态阈值和预算不变 | H15：overlap预算扩展/进度覆盖范围/误差证据，保留null与budget_exceeded，不改null为0 |
| P1-2 kept_quilt_visit -4 | 当前已知标签下游引用边界，没有因面积/形心成功推断句柄可引用 | H16：result_quilt_id可靠身份、连续trim/merge与保存重载 |
| ProMerge三轮外部正证 | 文案明确Creo12 incomplete/extract/redefine反证与Creo10 direct-create正证是两条路线；保留quilt_merge门禁 | H17：获取完整树载荷/原始job JSON，用NO_OPTS直创对照测面积/引用/回滚/保存重载，再决定版本门控；不外推成多片合并支持 |
| P2-1 半圆旋转 | 报告自列载荷错误；两个端点位于轴上并非一般拒绝条件。Creo12半圆成功不外推Creo10；不建议无条件补闭合线（会改变几何） | H18：同一坐标/轴/弧方向/centerline/模式输入对照。四分之一弧仅半球，不能冒充完整球 |
| P2-2 旧0.18.2报告 | 本次文件描述不能替代旧原件，本轮不冒造历史归档 | H19：取得指定旧原稿/模型/预览和原始回执后校验归档；现仅这份MD，报告列的PRT/JPG未提供 |
| P2-3 构建mtime | 时间戳不证明源码身份；本地补丁与官方构建、作者历史编译各自分开 | H19：worker实际源码指纹/哈希与编译日志关联，不能凭mtime认定说明错误 |
| 正证与新工具余项 | 保留H06 800→700/形心、0.3加厚125.722665、ProMerge4面为外部证据；不重复实现已有组测量/旋转/加厚 | G1桥接、多片/闭合多截面loft、非平面fill、独立offset、公开round及曲率检查沿FEAT-009/039/055开放 |

[本批验证](ACCEPTANCE.md)、[总接手清单](../../development/DEV-075-HANDOFF.md)。
