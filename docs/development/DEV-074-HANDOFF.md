# DEV-074：0.17.4 反馈离线结果与接手清单

日期：2026-11-07。工作分支：`codex/DEV-074-feedback0174-offline`，起点 `8d71e6c` / 0.18.0。用户要求先对照现有实现、先离线完成、把余项交另一个 AI。工作卡：[DEV-074](../work-items/DEV-074.md)；四份原件与完整逐章对照：[MAPPING](../validation/feedback-0.17.4-2026-11-07/MAPPING.md)。

## 已有内容与本次增量

开始前已存在 DEV-071/072 的 miter 公开投影、更新 force/预算、板厚来源、最近五条边文本诊断、空模型预览 skip、API 精确 tag 下载备用路线及台账修正；四份报告补有 Creo 10 的外部正证据，本轮未重复实现。

本轮离线补齐：无 Git 来源降级、日志头尾阶段归因、失败 ID 与 loaded 回执、有效板厚判据、空预览路径/字节/判定依据、过期 startup 提示、更新检查在途字段、曲面能力与门禁文案、附件 API 二级备用路线、发布勘误与统计口径。原生 resize 仅补诊断，**功能缺陷仍开放**。

## 验证结果

仓库内 `tools/dev_check.py --work-item DEV-074` 已通过：2850项单测、0失败、0错误，风格24条lint/12个未格式化文件为既有基线，没有新增基线问题；`bridge.py build`退出0。最终源码在无`.git`、PATH无Git的独立分发目录全量2850项、0失败/0错误、2项SDK检查跳过；464个源码文件与工作树一致。完整来源、命令与审查限制见[验收记录](DEV-074-ACCEPTANCE.md)。本轮没有连接 Creo；所有新原生字段、非零原点 resize、真实附件下载、WorkBuddy、Creo 9/10/12 新实机结果均不能记为通过。

## 未完成清单（接手顺序）

| 编号 / 条目 | 未完成内容与当前文件 | 下一动作与验收 |
| --- | --- | --- |
| H01 / FEAT-058，P1 | **非零原点大跨度 resize 尚未修复**。`native/planar_wall.cpp` 对 secdim 写绝对值，本轮仅新增 `PLANAR_WALL_RESIZE_DIMENSION`。现象：origin=[-92.5,-116]，185×232×1→100×60×1 得17200而非6000，已被体积守卫回滚。 | 先确认 Creo 会话可操作并取得实机授权；记录5个尺寸的名称/ID、有向目标和写值，确定解算分支。优先最小原生修复，保持 feature ID、origin、厚度与回滚。矩阵覆盖零/正/负/混合 origin、跨/不跨轴、恒等/缩小/放大、XY/XZ/YZ、正负厚度方向、同/跨计划、保存擦除重载和失败后继续编辑。不得删除体积/包络守卫。 |
| H02 / FEAT-009、FEAT-055，主线阻塞 | 多截面曲面 loft / boundary blend / G1 桥接没有可用路线。`native/surfaces.cpp`、`docs/development/G5-NATIVE-CONTRACT.md`。 | 先用可复现手工参考树定位原生元素，最小交付2截面直纹，再G1；取得真实quilt ID、面积、保存重载和后续 trim 证据后才能公开。 |
| H03 / FEAT-039，主线阻塞 | `quilt_merge` 保持门禁，既有树无可用结果 quilt，不能逐片缝合封闭。 | 原生 join/intersect 两片→链式，测 result_quilt_id、面积、闭合、失败回滚；修复前不解除 unavailable，不声称最终瓶底可实体化。 |
| H04 / FEAT-039/055 | 曲面组闭合、公差0.01、缝隙/重叠缺组级测量。 | 定义并实现 open_edges/gap_max/overlap 测量，实机区分开放、闭合、微缝与重叠；逐片 closed 不能替代组级通过。 |
| H05 / FEAT-014 | 钣金附着增料、百叶/格栅/凸台/铰链/耳、连续多边与 corner relief 尚缺原生能力/验收。`src/creo_mechdog/sheetmetal.py`、`native/advanced.cpp`。 | 先核查已有 FEAT-014 计划和用户未提交计划，避免重写。Creo 10 增料未实际尝试，12.4已有失败；不得直接开放 opt-in 或宣称 new_body+union 可用。分项定义树、材料连续性、板厚、角部实际去料量、展开回折与重载矩阵。 |
| H06 / FEAT-039 | trim 特征标签下游引用 visit -4；保留侧缺 centroid/bbox/世界方向。 | 修 native 结果 quilt 解析，读真实保留区域几何；quilt/平面工具、one/two 两侧、失败回滚、跨计划标签复用均验；不以面积减小证明“外侧”。 |
| H07 / FEAT-039 | 独立 quilt offset、弯曲源实测偏置距离/0.3壁厚未实现。现有 surface_offset 是偏置壁。 | 分开设计 offset wall 与 quilt offset；测真实结果quilt及曲面距离，mm/in/混合/未知单位矩阵；未知保持null，不能用体积/面积估算冒充局部厚度。 |
| H08 / FEAT-055 | 曲面边圆角、曲率梳/斑马纹、跨边G1偏差尚无接口。 | 各自登记最小契约，取得曲面边选择/几何结果或分析图、方向/曲率数值及保存重载证据。实体 round 不等于曲面 fillet。 |
| H09 / FEAT-039 | 任意非平面 fill 未支持。 | 先交付明确替代：旋转球面用于中心R8场景；任意闭合边界的非平面填充需新原生路线，单独验收，不放宽现有 planar fill。 |
| H10 / FEAT-039 | 多quilt实体化/加厚、开口面与0.3壁厚整链验收未完成。 | H02/H03/H04完成后再跑完整五爪任务；验证闭合、无缝/重叠、质量/厚度、开口面、保存重载与后续编辑。 |
| H11 / DEV-072/074 | 0.17.4与当前版本的真实远端 tag/main/Release/四附件/body 后核对尚未独立实施；新 API asset-ID 路线仅离线mock。 | 有网络时执行 `tools/check_release_assets.py --tag v0.17.4 --version 0.17.4`，记录Asia/Shanghai查询时间、提交、大小、API digest、本地SHA256与sidecar/body；写新POSTCHECK文件，保留旧validation/tag/附件字节。本轮[勘误](DEV-074-RELEASE-ERRATA.md)区分报告方实测与本机未查。 |
| H12 / BUG-115、BUG-109、DEV-074 | BUG-115原生根因和Creo10精确失败形态未知；新诊断/回执/预览依据尚无本轮MCP实机、保存重载与新WorkBuddy证据。 | 先确认健康会话，重编译后用MCP复验新字段及原始失败样本；默认保护保持。若按release收窄或新增opt-out，先补原生证据及独立设计。真实断流/原生并发/保存失败不得以单元mock记通过。 |
| H13 / DEV-066及历史反馈 | 其它证据工具全面无Git化、负例日志降噪、缺失的旧反馈原稿与原始失败现场仍按既有卡开放。 | 本轮明确修复范围见最终测试；逐脚本迁移不要把25个来源入口通过等同于37工具全部完成。仅有本次四份md，缺失旧原件不能制造；需要时向原报告方取得原稿后校验归档。 |

结构化最近候选边已完成原生失败结果、compact白名单与保护证据链路；仅离线测试/编译，实机失配场景仍由H12接手，不从错误message正则提取“测量值”代替原生结构化证据。

## 接手约束

本机只使用 `MCP_CREO_MechDog_dev`，不擅自连接、结束Creo、清unknown或故障注入。当前服务版本保持0.18.0，本次不合main、不发Release；后续用户授权合main时必须遵守项目同次Release交付规则。开始时用户已有 `docs/work-items/DEV-054.md`、`.trae/`、`docs/superpowers/plans/2026-11-06-feat-014-miter-cuts-route.md` 未提交内容，不属于本批提交。
