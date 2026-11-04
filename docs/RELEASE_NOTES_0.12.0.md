# MCP_CREO_MechDog 0.12.0 版本说明

- 类型：MINOR，新增公开能力；公开工具 **95 → 97 个**，无破坏性接口变更。
- 条目：[FEAT-058](work-items/FEAT-058.md)（原生矩形钣金首壁与就地改型）；契约说明见 [FEAT058-PLANAR-WALL-CONTRACT](development/FEAT058-PLANAR-WALL-CONTRACT.md)。
- 版本入口：[version.py](../version.py)；配套种子包 `MCP_CREO_MechDog-0.12.0-seed-library.zip`。
- 面向调用方：新增两个工具与一个可选模板值；既有 `sheetmetal_wall` 默认路线与请求参数不变。

## 本版内容

- **新增 `creo_sheetmetal_planar_wall`（矩形首壁）**：在**空钣金零件**上按 Fill 首壁树创建矩形平面壁——`plane` 仅 XY/XZ/YZ，`length/width/thickness>0`，`direction=positive|negative` 决定板厚沿草图法向哪一侧生长；厚度先写零件 `SMT_THICKNESS` 参数，参数不存在时才写元素；原生要求重生成后体积＝长×宽×厚、body 报钣金、草图点尺寸 ≥4。实体零件、非空钣金零件与已存在的受管标签在建 job 前拒绝。
- **新增 `creo_resize_sheetmetal_planar_wall`（就地改型）**：按当前尺寸比例驱动首壁草图的点坐标尺寸后重定义草图，**feature id 与板厚保持不变**；改型前从已保存文件重读板厚并与记录比对；壁存在下游子特征时拒绝，不静默重建。
- **`creo_new_sheetmetal` 新增 `template="native_planar"`**：默认值仍为原转换模板，旧调用不受影响。
- **job 结果发布 `planar_wall` 判定块**：`feature`/`feature_id`/`sketch`、`length`/`width`/`thickness`/`square`/`dimension_count`、`direction`、`volume_mm3`、有符号 frame 包络 `u[0,L]`/`v[0,W]`/`n[0,t]`（`negative` 为 `n[-t,0]`）、`thickness_measured_mm`/`thickness_verified`/`thickness_body_code`；改型另有 `feature_id_before`/`feature_id_unchanged`/`thickness_loaded_mm`。`verified` 仅在无 `problems` 时为 true，compact 与 full 轮询都能看到该块。
- **判定强化（复核收口，兼容但更严格）**：尺寸缺失不再短路体积/板厚/包络检查，而是自身记为问题；NaN/Inf 不再等价于"数值一致"（投影里发布 `null`）；改型必须带回读自存档的 `thickness_loaded_mm`。此前"证据缺失也算通过"的结果现在会返回 `verified=false`。
- **源码身份**：`native/planar_wall.{h,cpp}` 与 `src/creo_mechdog/native_planar_wall.py` 进入部署指纹与运行时源码清单（`server._SOURCE_NAMES`）。

## 验证与边界

- 离线：全量 **2286 项单测** 0 失败/0 错误（`tools/test_unit.py`，报告 `build/unit_test_report.json`；含 FEAT-058 专项 18 项与三处复核反例回归）；`tools/dev_check.py` `success=true`（存量 lint/格式基线照旧，不宣称全库严格格式清零）；`bridge.py build` exit 0（执行器 SHA256 `9099e7f8…`、`build/source.sha256` 前缀 `ddf4717f…`）；平面壁驱动离线 20 项通过（`build/planar_wall/20261104T041850Z/adoption_offline.json`）。
- 本机 **Creo 12.4.0.0 实机**（`release_numeric` 见发布记录，运行目录 `build/planar_wall/20261104T042412Z/`），命令 `python tools\test_adoption_planar_wall.py --live --confirm-session-usable`，**67/67 检查通过**：
  - 创建 100×60×1 → 6000 mm³，`feature_id=49`，`dimension_count=5`，包络 `u[0,100]/v[0,60]/n[0,1]`，`saved_file_reloaded_and_verified=true`；
  - 就地改型 120×80 → 9600 mm³，`feature_id_unchanged=true`，`thickness_measured_mm=1.0`、`thickness_loaded_mm=1.0`；
  - `direction=negative` 6000 mm³（`n[-1,0]`）、XZ/YZ 各 6000 mm³、方形 60×60 → 3600 mm³ 后改 90×60 → 5400 mm³ 且 `square` 由 true 变 false；
  - 下游依赖：原生壁挂折边成功（`edge_id=59`）后改型在建模前被拒；
  - 原生拒绝回滚后旧 `sheetmetal_wall` 首壁仍成功 42920 mm³；旧首壁+折边 47178.64 mm³ 且保存重载为 true。
  - **过程披露**：首轮实机在 `connect_creo` 以 `-38` 失败（`build/planar_wall/20261104T041859Z/`，作业 `d580ff17…`，`failed_stage=connect`、`effect_status=no_effect`，未执行任何操作），会话仍响应后重跑一次即全部通过；该失败属会话连接问题，不是本版建模回归。
- **未验证**：非矩形与多环截面；四壁与第二折边；`plane` 显式支撑面并覆写 origin；Creo 9/10 的构建与建模（本机无 Creo 9 SDK，Creo 10 不要求独立复测）；WorkBuddy 黑盒验收。
- 环境：Windows x64 / PowerShell / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3 / Creo 12.4.0.0 与匹配 Toolkit SDK / MSVC x64。
- 本版含原生新增（`native/planar_wall.{h,cpp}`、`native/generic.cpp` 分发），需重新编译执行器；第三方文件未修改。

## 升级

1. 使用成对的 0.12.0 源码包与种子包；种子 PRT 字节不变，两份清单的 `compatible_server_version` 已更新为 0.12.0，旧种子包会被版本闸门拒绝。
2. 重新运行 `setup.ps1`，或在安装虚拟环境执行 `python -m pip install --no-deps -e .` 后重启 MCP 服务加载新模块；原生代码有变更，首次启动会重建/校验 `build/creo_worker.exe`。
3. 调用方需要复核的语义变化：**无破坏性变更**。新增两个工具与 `template="native_planar"`；请把 `planar_wall.verified=false` 当作**未验证**处理（旧判定的"证据缺失即通过"已移除），并在使用首壁前确认模型来源为空钣金零件。
