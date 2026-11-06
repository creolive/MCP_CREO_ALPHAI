# MCP_CREO_MechDog 0.17.0 版本说明

2026-11-07，MINOR 功能批；条目：[FEAT-058](work-items/FEAT-058.md)（原生矩形首壁的草图定位 `origin`）与 [FEAT-014](work-items/FEAT-014.md)（折边按几何端点选边 `edge_geometry`）。公开工具仍为 **100** 个，无新增工具、无删除工具、无必填参数变化；两处均为可选入参，省略时行为与 0.17.0 之前一致。

两条能力在同一开发分支 `codex/R10-first-wall-origin`（基线 `main@34dbcb1`，`version.py=0.16.1`）上分两个独立提交实现，本次一并合入 `main` 并发布。

## FEAT-058：首壁 `origin` 定位

`creo_sheetmetal_planar_wall` 新增可选 `origin: [u0, v0]`：

- **语义**：草图局部坐标毫米，默认 `[0,0]`；创建时矩形由 `0..L / 0..W` 改为 `u0..u0+L / v0..v0+W`，仍按命名平面原有 u/v/n 建帧，板厚生长侧不变。`origin` 必须是两个有限数且 `|值|≤1e6`；显式平面字典自带 origin，因此与非零 `origin` 互斥，由 schema 拒绝。
- **改型**：`creo_resize_sheetmetal_planar_wall` 保持原点不动。坐标尺寸是"到截面轴的距离"，矩形跨过截面原点时两侧尺寸同值（实测 92.5/92.5、116/116），不能靠 min/max 猜测区间；实现改为读取草图截面定位矩阵，把记录的 frame 映射到截面轴，再按 `wall_0..wall_3` 角点表把每个尺寸名还原到 frame 角点，逐项核对旧值后写入。旧记录缺 `origin` 时按 `[0,0]` 处理。
- **未采用"平移 sketch frame"路线**：原生探针显示 XY/YZ 可以复现 offset 几何，但 XZ 的显式平面取支撑法向 +Y（命名约定为 −Y），几何落到 `z[-348,-116]`；因此保留命名帧、移动矩形，与 `sketch_frame` 既有约定不冲突。
- **实机结果**（本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK / 许可）：`tools/test_first_wall_origin.py --live --confirm-session-usable` **112/112**，报告 `build/first_wall_origin/20261106T152859Z/origin_live.json`。185×232×1 在 `origin=[-92.5,-116]` 下 bbox `[-92.5,-116,0]..[92.5,116,1]`、质心 `[0,0,0.5]`、体积 42 920 mm³；省略 `origin` 时几何与 0.16.0 一致；XZ/YZ、负方向、同计划与跨计划 resize 200×250、第二面墙拒绝后继续 resize 全部通过，保存重载均为 true。

## FEAT-014：折边 `edge_geometry` 几何选边

`creo_sheetmetal_flange.edge` 现在有两种形态，二者都不得再包 `edge`/`reference`：

- `{"kind":"edge","id":N}`：当前巡检的边 ID，语义不变；
- `{"kind":"edge_geometry","endpoints_mm":[[x,y,z],[x,y,z]],"tolerance_mm":1e-6}`：当前模型坐标毫米的两端点点名一条**直线边**。`tolerance_mm` 可省略（默认 `1e-6`，允许 `1e-9..1000`），对象只接受 `endpoints_mm`/`tolerance_mm` 两键，不接受单位字段；坐标必须有限、两端不重合。

原生在**每个 op 执行前**重新遍历当前 body→surface→contour→edge：`ProEdgeIdGet` 去重、`ProEdgeDataGet`+`ProLinedataGet` 取端点，按 `inspect_length_units` 换算到 mm 后做**无向**端点对比较。恰好一条候选才创建；0 条、多条、模型长度单位不可换算都在创建前拒绝，0 条文案给出扫描的直线边数与 tolerance，多条给出候选 id。因此计划不再依赖提交时的 edge id，同一条物理边在重建后改变 id 仍可按几何选中。

实机 Creo 12.4.0.0（`tools/test_flange_edge_geometry.py --live --confirm-session-usable`，**17/17**）：

- 185×232×1 首壁（模型 `cbbcd27acf374b9c82534c3764b3aa51`）；`+x`、`-x` 两道非干涉折边都用**任何折边创建前**采集的端点提交，两面墙顶面 232 mm、与贴边 `matches`，均 `saved_file_reloaded_and_verified=true`；
- 两道折边把 `-y` 顶边从 185 缩短到 177.92 mm，id 由 **85 变为 267**，旧 id 已不在当前边表；随后同一物理边用当前几何端点加显式 `miter_cuts{width:1,offset:1}` 建成并保存重载 true；
- 不存在的几何被拒，文案报"扫描 86 条直线边、匹配 0 条"，revision 与体积不变、回滚 `succeeded`；
- 报告 `build/flange_edge_geometry/20261106T235931_f44fd733/report.json`（SHA256 `b84b3e0f5908f6af8932babf70803bbb81982f7ef2bbadf90341db917f13f4ea`）。

几何选边只解决"选哪条边"，不改变 `adjacent_bend_ends` 与 miter 的几何门槛。

## 本版验证门禁

`bridge.py build` 退出 0（原生改动重编执行器）；`tools/test_unit.py` 全量 **2723 项通过**，0 失败 0 错误；`tools/dev_check.py` `success=true`。种子内容未变，仅两份清单的 `compatible_server_version` 同步：种子包 24 文件、9 种子，两次确定性构建同摘要 `2f75aba0599b86f5c657cb48f27c95dac5d807b3c684807a25cd3b5ec09a3382`，已回填 `docs/seed_package.json` 并二次构建确认稳定。受测源码身份与远端核对结果见[发布记录](validation/RELEASE-0.17.0.md)。

未验证范围：Creo 9（本机无 SDK）与 Creo 10 实机；显式平面字典与非零 `origin` 的组合（schema 明确拒绝，未实机执行）；斜置/非轴对齐 frame 的 resize（原生会以"截面轴与记录 frame 不对齐"拒绝，未取实机证据）；`edge_geometry` 的多候选歧义与未知长度单位的实机拒绝（仅单测）、非轴对齐/斜置边、跨计划重放与真实重启后的 id 重排；WorkBuddy 黑盒；BUG-001 的会话边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.17.0-source.zip` 与 `MCP_CREO_MechDog-0.17.0-seed-library.zip`，按安装说明更新环境、重编执行器并重启 MCP 服务。旧种子包会被版本闸门拒绝。
