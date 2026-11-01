# MCP_CREO_MechDog 0.11.0

0.11.0 交付 [FEAT-052](work-items/FEAT-052.md) 装配按零件族上色（MINOR）：新增公开工具 `creo_recolor_assembly` 与计划操作 `recolor_assembly`，`creo_list_components` 每组件新增三态 `appearance` 字段，公开工具 **94→95**。首版仅覆盖 MCP 受管单层装配；颜色写在装配组件层，源零件文件字节不变。0.10.1 及更早的提交、标签、Release 和附件均保持原样。

## 新能力：装配按零件族上色

- **`creo_recolor_assembly(model_id, expected_revision, palette, families?, dry_run?, limit?, cursor?)`**：省略 `families` 时按组件绑定中唯一的 `source_model_id` 自动分族；显式族表 `families={族名:[组件标签或特征ID]}` 必须无重复且**完整覆盖全部组件**（不完整表在入队前拒绝，实机已验证该拒绝路径）。`palette` 给出各族 RGB（三个 `0..1` 有限数值，拒绝布尔值）。执行走既有作业通道、始终保存、成功后 revision 加一；作业结果新增 `recolor` 证据块（painted/unmatched/family_counts、写前基线、保存前后读回行与容差判定、回滚核验行）。
- **`dry_run=true` 只读预览**：分组预览不连接 Toolkit、不创建作业、不推进 revision；分页 ≤32 KiB，游标绑定 revision 与请求内容（请求或 revision 变化即失效）。执行入口拒绝预览专用参数。
- **计划操作 `recolor_assembly`**：供 `creo_execute_plan` 使用，只选择操作前已存在的组件，不接受预览参数。
- **三态外观检查**：`creo_list_components` 每组件条目新增 `appearance` 字段（`state=present/absent/query_failed`、`rgb`、`query_code`）；保存重载核验纳入外观比对（基线早于本能力的检查点缺外观基线时拒绝写入并指引 `creo_save_model`）。
- **读回与回滚**：写前捕获逐组件外观基线；保存擦除重载前后逐组件读回 RGB 误差 ≤1e-6；任一步失败沿用检查点回滚并核验外观点恢复（含"无组件外观"与"既有颜色"两种基线，实机均已验证），无法证明恢复时保留 unknown 保护。

## 实机验收摘要（本机 Creo 12.4.0.0 / 匹配 SDK / MSVC）

run `assembly_appearance_live_20261101T060336Z558b3546`（报告 `build/assembly_appearance_live_20261101T060336Z558b3546/report.json`，本机生成物）：80 组件/12 族夹具 **28/28 检查通过、退出码 0**——12 源件创建保存重载、80 组件装配、初始全 absent；两个故意失败计划（双 `remove_component` 触发原生失败）分别回滚至"无组件外观"基线与既有 round A 颜色基线（`rollback_succeeded=true`、`rollback_appearance_verified=true`、80/80 行核验）；自动分族与显式合族（crank+fan 合族）两轮上色、第三套色板复涂，读回全部 ≤1e-6、`saved_file_reloaded_and_verified` 全 true；组件身份/位姿/约束/体积全程不变；`component_placement` 移动单组件并保存后全员保色；12 个源零件文件 SHA256 在所有阶段保持不变。目视确认：截屏 `visual_check.png` + 视觉核验（约 8–12 种可辨实色族、网格规整、无弹窗）。

针对性回归：`tools/test_assembly_pipeline.py`（13 断言、10 作业全成功，两跑均绿）与 `tools/test_t07_preview.py --live`（`preview_acceptance=passed`，7 例）通过。实机过程定位并修复三处缺陷（原生外观比对对 `find` 迭代器误用下标 ×2、结果投影缺回滚核验字段、驱动夹具契约 ×2），随版交付。

## 未测范围（保持开放）

WorkBuddy 纯 MCP 黑盒验收未执行；busy/并发通道交错未做实机（沿用全局既有契约）；`dry_run` 预览分页与游标失效、非法输入拒绝、读回错误/失配注入属离线单测/受控范围；Creo 9 本机无 SDK（实机编译与建模运行时未验收）、Creo 10 独立复测不作为门槛；本机 Creo 12.4 通过不外推其他环境。BUG-091 根因未定，实机准入纪律持续有效。

## 附件

| 附件 | SHA256 |
| --- | --- |
| `MCP_CREO_MechDog-0.11.0-source.zip` | `d657c845d6164b99ad20d960cc9659ac6f44c91f6490ab82f57e2f6a2b76477a` |
| `MCP_CREO_MechDog-0.11.0-seed-library.zip` | `3d922e0ec6185a624f3e85155651d0b62c94c66ac89e9bc40da9949423b213cf` |

发布状态见 [发布记录](validation/RELEASE-0.11.0.md)。
