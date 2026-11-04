# MCP_CREO_MechDog 0.12.2 版本说明

2026-11-04，MINOR；条目：[FEAT-039](work-items/FEAT-039.md)（曲面链 S02 修剪），随附 [DEV-045](work-items/DEV-045.md)（发布附件校验）与 [DEV-067](work-items/DEV-067.md)（规划与审计记录）。

新增公开算子 `creo_surface_trim`（曲面修剪 / use-quilt），公开工具由 97 增至 **98**。该算子在 2026-11-04 本机 Creo 12.4.0.0 上完成 P3 实机验收后解除门禁。

- `keep_side` 语义已由实机测定：`one` 保留工具面法向正侧，`two` 保留负侧。40×20 平面填充（800 mm²）被 x=5 基准面修剪后分别为 700 mm²（外框 x∈[5,40]）与 100 mm²（x∈[0,5]）；圆柱曲面（1256.64 mm²）被 z=5 平面修剪后分别为 314.16 mm² 与 942.48 mm²；两次均 `saved_file_reloaded_and_verified=true`。
- 修复保留侧不生效：原实现只让 `PRO_E_PRIMARY_QLTSIDE` 跟随 `keep_side`，`PRO_E_MATERIAL_SIDE` 固定为 ONE，实机两侧得到同一区域；现在两个元素同时跟随 `keep_side`，不允许互相矛盾。
- 修复基准面引用被静默改写：`{kind:'datum_plane',label:...}` 的标签会被几何解析丢弃，默认轴过滤选中 TOP，修剪随后停在 `PRO_FEAT_UNREGENERATED`。Python 契约与原生解析现在都拒绝在几何类引用上携带标签，指引用 `{kind:'datum_feature',label:...}`。
- 修剪再生失败改为可诊断：返回 `regeneration`（失败阶段、特征 ID 与状态、目标 quilt、工具种类、两侧枚举值、结果特征 quilt 访问码与 ID 列表），失败消息带同一组数值；已测得的面积字段在失败记录中保留。
- `creo_quilt_merge` 仍为门禁状态，未公开。版本入口、两份种子清单与受信摘要同步至 **0.12.2**；种子包确定性重建 SHA256 为 `044f1da0f78c52cf3fe11993486184063ceafac82615e77c28a02368f17ea2eb`（24 文件、9 种子），与两份清单一致，详见[发布记录](validation/RELEASE-0.12.2.md)。

验证命令为 `python tools/test_unit.py`（2353 项通过）、`python tools/dev_check.py --skip-unit`、`python bridge.py build`，外加实机 `build/_live_trim.py` 与 `python tools/test_surface_chain.py --case trim --live --confirm-session-usable`。结果与受测源码身份见[发布记录](validation/RELEASE-0.12.2.md)。

本版实机验收只覆盖修剪的再生、面积/位置、保存与重载；修剪结果在重载后被 `thicken` 消费、质心判据（本机无 quilt 质心查询，`signed_offset_mm` 保持 null）、失败回滚的实机表现、`use_curve` 投影—修剪串联均未验证。Creo 9 无本机 SDK，构建与运行时未验收；Creo 10 不要求独立复测；BUG-001 的既有边界继续适用。

升级使用配套的 `MCP_CREO_MechDog-0.12.2-source.zip` 与 `MCP_CREO_MechDog-0.12.2-seed-library.zip`，按安装说明更新环境并重启 MCP 服务。旧种子包会被版本闸门拒绝；本版新增一个公开工具，无回调注册变化、无参数迁移、无新增原生编译要求。
