# MCP_CREO_MechDog 反馈材料包（2026-10-31 晚间批次）

发件：WorkBuddy 用户（Creo 10.0.0.0 / Windows 11 x64 / MCP 0.10.0 实测）
收件：MCP_CREO_MechDog 作者

本包是 2026-10-31 一天内对 0.10.0 的两轮实测产出，共四份报告 + 两份源码补丁 + 完整配方工件。
三份材料的关系：**验收报告**（0.10.0 缺陷复核，A–H+N1/N2/N3）→ **G5 方案**（曲面三 op 的实现路线）→ **BUG-094 报告**（直改源码后新发现，含两项已验证补丁）。

## 包内清单

| 文件 | 内容 | 优先级 |
|---|---|---|
| `01_验收报告_0.10.0.md` | 对 0.9.0 八条问题的逐条定点复测：A/D/E 未修、N1/N2 轮询协议小修、确认变好的五处 | 高（A+D 建议一起修） |
| `02_G5曲面能力方案.md` | surface_loft / project_curve / surface_trim 的元素树实现路线（ProSweep.h + COPYTRIM 族），四步补丁与工作量估计 | 中 |
| `03_BUG094报告.md` | 三点定面 + 斜面草图失败的完整定位：L1 已修复（UV 基回退，附源码）、L2 待上游（redefine -1），附最小复现 JSON | 高 |
| `04_generic_cpp_patches.md` | 两处补丁的代码块（基于 0.10.0 源码直改，可直接对照并入） | 高（与 03 配套） |
| `05_上色能力建议包.zip` | recolor_assembly 需求 + 已验证的 Pro/TOOLKIT 上色源码（80/80 组件实测） | 中（N3，独立新增） |
| `06_P12_v12_配方/` | v1.2 扭叶片的两种路线完整配方（逐站三角棱柱 391 项特征树；正规链路的 op 定义） | 低（依赖 BUG-094 修复） |

## 一页速览（作者视角的行动清单）

1. **A + D 一起修**（同一处 SectionRegenerate 比对逻辑的两面）：coordinates 位移>1e-4 整轮廓拒绝 vs autodim 同样位移静默通过且不报告。统一成"比对 + 回显 + 可配置闸值"。
2. **E**：失败事务里擦除孤儿会话对象（本次验收再次被迫改名绕过）。
3. **BUG-094**：先在 `errors(es)` 处把 `ProErrorlist` 内容带回执（一处小改），即可定位斜面草图 redefine -1 的内核抱怨；L1 补丁（04 文件）无副作用可直接并入。
4. **N1/N2**：stage 字段在必败作业上不推进；busy 回包的 retry_after_seconds 至少取占用方历史耗时。
5. **N3 上色**：recolor_assembly（05 包含已验证源码，ProMdlVisibleSideAppearancepropsSet 路线）。
6. **G5 三 op + datum_plane.thru_points**：02 文件的四步路线；thru_points 已在 04 文件含实测源码。

## 复现环境

- Windows 11 x64 / Creo Parametric 10.0.0.0（release_numeric=42）/ MCP_CREO_MechDog 0.10.0
- 编译：MSVC 14.44（BuildTools）/ Windows SDK 10.0.26100 / Pro/TOOLKIT 头与库（protkmd_NU + ptaskyncmd + ucore + udata）
- 全部 job 目录编号在各自报告内，可直接对档。
