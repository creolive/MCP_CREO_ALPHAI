# MCP_CREO_MechDog 0.18.0 版本说明

2026-11-07，MINOR：**本地功能分支集成批**。本版把四个已实现但未进入主干的本地分支合入，并按版本约定新增两项公开能力，公开工具 **100→102**：离线产品变体规划 `creo_plan_product_variant`（[FEAT-063](work-items/FEAT-063.md)）与只读质量属性 `creo_get_mass_properties`（[FEAT-057](work-items/FEAT-057.md)）；同时合入标准螺纹孔定义（[FEAT-035](work-items/FEAT-035.md)）与多模型事务日志底座（[FEAT-059](work-items/FEAT-059.md)）。原生执行器源码有变更，本版只完成离线门禁与组合编译，**未连接 Creo 实机**。

## 本版内容

| 条目 | 本版结果 | 证据 |
| --- | --- | --- |
| [FEAT-063](work-items/FEAT-063.md) 离线产品变体规划 | 新增只读工具 `creo_plan_product_variant`（`template_id` + `parameters`），服务端静态启用操作快照与 `product_rules` 能力族；固定模板 `box_frame` 输出参数、操作序列与解析期望几何；不连接 Creo、不提交任务 | `src/creo_mechdog/product_rules.py`、`examples/product_rules/box_frame.json`、[PRODUCT_RULES](PRODUCT_RULES.md) |
| [FEAT-035](work-items/FEAT-035.md) 标准螺纹孔定义 | `creo_hole` 新增可选 `standard={series,size,thread_depth}`（此时 `diameter` 可省略），由冻结的 ISO 粗牙表解析底孔直径与深度上限，返回表标识/表指纹/底孔/深度上限；与沉孔/沉头互斥，直径须等于名义值；原生写入螺纹元素树并在操作回执发布 `thread_metadata`/`thread_metadata_verified`/`thread_readback` | `src/creo_mechdog/hole_standards.py`、`native/generic.cpp`、`src/creo_mechdog/compact_sections.py` |
| [FEAT-057](work-items/FEAT-057.md) 只读质量属性 | 新增 `creo_get_mass_properties(model_id, density_g_cm3=null)`：体积、质量、密度、重心；密度优先取模型材料，`density_g_cm3` 仅作显式 what-if 兜底，两者皆无时质量返回 `null` 而不是伪造值；仅零件；数值守卫拒绝 NaN/±Inf 与溢出 | `src/creo_mechdog/mass_properties.py`、`native/mass_properties.h`、`native/generic.cpp` |
| [FEAT-059](work-items/FEAT-059.md) 多模型事务日志底座 | `model_transaction.py` 冻结 `prepare/finish/load` 与 prepared→native_saved→registry_committed/recovered/recovery_required 阶段；检查点仅在成功后推进，未证实一律不报 rolled_back，重复请求幂等；**原生骨架创建与 `inspect_skeleton_binding` 未实现** | `src/creo_mechdog/model_transaction.py`、[骨架契约](development/ALPHAI-B01-SKELETON-CONTRACT.md) |

## 兼容性与接口

- 新增两个公开工具（100→102），其余工具名称与参数不变；capabilities 新增 `product_rules` 与 `mass_properties` 两个能力族。
- `creo_hole` 的 `standard` 为可选项；提供时 `diameter` 可省略，且不能与 `counterbore`/`countersink` 同时使用。标准孔原生螺纹元素树的实机写入尚未验证，校验层对表外几何仍拒绝而不是退化为普通直孔。
- 质量属性只支持受管零件；装配/钣金的多实体与 occurrence 汇总、材料密度来源与单位契约仍开放。
- 原生执行器源码有变更（螺纹元素树、质量属性），升级需按 `bridge.py build` 重新编译。
- `creo_plan_product_variant` 为纯离线规划器，返回的 `expected_geometry` 是解析期望值，不是原生测量。

## 门禁

- 合并四个分支后的组合源码全量单测 **2826 项，0 失败、0 错误**。
- `tools/dev_check.py` `success=true`（提交 `1cf9d3f`、dirty=true——仅叠加本批发布文档与本机用户未提交的 DEV-054 记录/未跟踪文件；源码指纹 `80f2bb8d…`），24 条 lint / 12 个未格式化文件为存量基线。
- `python bridge.py build` 在 Windows x64、Creo 12.4.0.0 匹配 Toolkit SDK 下编译通过（`build/creo_worker.exe`）。
- 种子包确定性构建两次同摘要，已回填 `docs/seed_package.json`。

## 未验证范围

- **Creo 实机**：本版未连接 Creo/Toolkit，标准螺纹孔原生树、质量属性原生读取与保存重载均无实机证据；`bridge.py build` 只证明可编译。
- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试，本轮不执行）。
- Creo 9（本机无 SDK）与 Creo 10 实机。
- FEAT-057 材料密度来源/单位/装配汇总契约；FEAT-059 原生骨架创建与多模型事务；FEAT-063 原生模板与保存重载。
- 真实远端附件下载由发布后 `tools/check_release_assets.py --tag v0.18.0` 另行核对。

## 升级

1. 拉取本版本源码并执行 `python -m pip install --no-deps -e .`。
2. 执行 `python bridge.py build` 重新编译执行器（原生源码有变更）。
3. 重启 MCP 服务；旧客户端可忽略新增工具与回执字段。
