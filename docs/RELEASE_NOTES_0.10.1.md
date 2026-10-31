# MCP_CREO_MechDog 0.10.1

0.10.1 交付 [DEV-053](work-items/DEV-053.md) 中按 PATCH 归属的批次：0.10.0 发布后五份 0.9.0 反馈（[F1–F5 归档](validation/feedback-0.9.0-2026-10-31/MAPPING.md)）的对账、稳定性与取证修复、发布防复发闸门、工具说明/枚举对齐，以及基准面非法参数的明确拒绝。无新增公开工具，公开工具仍为 **94** 个；不含新增公开结果结构——草图原点诊断字段、钣金候选边结构与空件预览新状态（[BUG-095](work-items/BUG-095.md)/[BUG-032](work-items/BUG-032.md)/[BUG-088](work-items/BUG-088.md) 的 MINOR 部分）已在开发分支实现，随下一 MINOR 版本（候选 0.11.0）另行交付。0.10.0 及更早的提交、标签、Release 和附件均保持原样。

## 升级必读

- **基准面非法参数明确拒绝（[BUG-094](work-items/BUG-094.md)）**：`datum_plane` 引用的 `angle is not None && offset != 0` 组合此前会被**静默丢弃 `offset` 后“成功”**，现在在共享校验（`src/creo_mechdog/references.py`/`schema.py`）入队前拒绝，原生执行器兜底；`angle=0` 也属显式角度模式（合法）。`angle` 只接受 `{"kind":"axis","id":N}` 与 `{"kind":"datum_axis_feature","label":...}` 两种轴引用；引用缺 `kind`、`kind` 非字符串、轴标签指向面或不存在时给出可判断的带路径错误，不再以执行器 JSON 缺键异常透出。保留输入：offset-only、angle-only、`angle+offset=0`、`datum_feature` 面引用（面语义未变）。**迁移**：旧脚本里 `angle` 与非零 `offset` 同时出现的请求需拆为两次操作（先建角度平面，再以该平面为引用做偏移）。
- **`creo_capabilities` 概览枚举三键化（[FEAT-008](work-items/FEAT-008.md)）**：概览中旧的 `extrude_depths` 键（内容为 `blind/through_all_cut/symmetric`，与 `depth_type` 实际契约不符）移除，改为 `extrude_depth_types`（`blind/through_all`，`through_all` 仅 cut）、`extrude_directions`（`positive/negative/symmetric`）、`extrude_through_all_modes` 以实际为准（当前 `["cut"]`）三键分别表达。读取旧键的客户端需改读新键；工具 schema 与共享 op 模型的逐字段枚举对照已由单测锁定。
- **stdio 服务有界退出（[BUG-092](work-items/BUG-092.md)）**：客户端关闭输入或异常退出而输出未被消费时，服务此前会因 stdout 管道写阻塞无限挂起并残留进程；现由 `StdioExitGuard` 在宽限 1.5 s 后解除阻塞写、兜底 2 s 内退出，**不终止任何子进程**——已受理建模任务在独立 runner 进程中继续登记终态。客户端无需动作。
- **种子安装与源码打包受信闸门（[BUG-089](work-items/BUG-089.md) 防复发）**：`creo_install_seed_library` 按 archive 安装时先校验受信摘要（来源 `docs/seed_package.json`，随源码分发）再写入目标；篡改字节、摘要失配、版本不一致、双清单不一致、README 版本段滞后均拒绝。源码打包命令**必填** `--seed-archive`：

  ```
  旧: python tools/package.py --output <new-source.zip>
  新: python tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>
  ```

  缺参或失配时 exit 非零且不创建源码 ZIP/stage 文件；迁移示例见 [RELEASING](development/RELEASING.md)。

## 行为与判定修复

- **拒绝后的同源体积证据（[BUG-093](work-items/BUG-093.md)）**：实机驱动此前读不到 BUG-077 拆分后 `inspection_summary` 层的 `volume_mm3`，把“体积证据缺失”误报为 `volume_missing`。定因为驱动读错层，生产代码零改动；驱动 `measured_volume_mm3()` 改选定层语义（缺字段即缺证据，不跨层抄值）、排除 bool/NaN，并新增 model_id 与终态一致性判定。
- **异步 revision 误读关闭（[FEAT-008](work-items/FEAT-008.md)）**：对 4035 份本机历史作业/模型记录的离线审计证明“新建受理 revision=0、随即 current=1”是**未等终态的读取时序**（新建受理即记 revision 0，成功终态全部 ≥1、失败保持 0，登记与作业链逐模型一致），非生产缺陷；使用说明补入 README（等终态后再按最新值续编）。
- **0.8.5 发布后核验回填**：补记 2026-10-29 的 v0.8.5 远端核验记录（主干提交、附注标签、四附件哈希逐件下载核对），该内容此前仅存在于工作区未提交状态。

## 调查、登记与文档

- **[BUG-091](work-items/BUG-091.md)**：0.6.1 断连、10-29 挂起、10-31 两次通道死亡四个现场分开调查，各自给出已取得证据/关键缺证表与可证伪假说；根因未定，实机准入纪律持续有效。
- **[FEAT-014](work-items/FEAT-014.md) P09 第一阶段**：四壁/端部 trim/材料端 relief 的离线证据核对——`trim_ignored`（语义缺输入）、邻接端拒绝（可继续）、relief 元素保留（自由端已证、材料端缺证）、真实去料（缺证）四现象定性；四壁整体保持不支持，A/B 两层对照矩阵草案就绪。
- **[BUG-049](work-items/BUG-049.md)/[BUG-090](work-items/BUG-090.md)**：原 `gear10`/`gear10_snapped` 原件与外部 Creo 10 构建日志/SDK 均缺件，原案与定向编译维持“未验证”，触发条件已写入卡内。
- **五份 0.9.0 反馈原件**逐字节归档并核 SHA256（5/5），逐章映射到固定 ID（[归档目录](validation/feedback-0.9.0-2026-10-31/MAPPING.md)）；N12 性能口径（small 每类 n=3；large 两轮分别 n=2 与 n=3，分开统计）在当前入口澄清。

## 实机验收摘要

环境：本机 Windows x64、Creo Parametric 12.4.0.0、匹配 Toolkit SDK 与许可、MSVC；受测分支 `codex/dev053-rel0101`，实机 run `post0100_20261031T234309_rel0101`（源码指纹 `0ba07f37…49e112`、worker SHA256 `eca0c8e2…4eb5cd0`，[身份记录](../build/post0100_20261031T234309_rel0101/build/identity.json) 为本机生成物）。

| 范围 | 结果 |
| --- | --- |
| 非法弧方向五反例 + 恢复（BUG-093 收口） | 4 例 schema 拒绝无作业；原生开放轮廓例失败回滚，拒绝后同源体积 1428.0972451017303 mm³ 逐位不变、revision 3→3、model_id 一致；恢复编辑成功（rev 3→4，体积误差 3.2e-10 mm³）；5 创建例保存重载全 true |
| stdio 退出核对（BUG-092 收口） | 实机驱动退出后 python/server.py 进程零残留；后续各驱动同核 |
| 基准面契约（BUG-094 实机） | ±54°（实测法向 0.5878/±0.8090 与 Rodrigues oracle 一致）、零角、offset-only、旋转后显式偏移、独立工具/plan 双入口全过；angle+非零 offset、缺 kind、非法 angle 轴类型三拒绝例成立（驱动自身的 feature→geometry 映射缺陷已修，生产零改动） |
| 定向回归 | 圆角/倒角/拔模九例（FEAT-051，含批中途失败真实回滚）、装配回放（T09，native_acceptance=passed）、T12 官方示例（passed） |

## 未测范围

BUG-091 根因未定（四次通道死亡现场缺运行期 worker 指纹等关键证据）；四壁/corner/trim/材料端 relief 去料不支持或未证明；`gear10` 原案未验证（原件缺件）；Creo 9/10 实机编译与运行时未验（本机无对应 SDK，外部证据缺件）；P07 草图原点诊断、P08 钣金帧/候选边、P11 空件预览新状态的实机验证随 0.11.0 候选在开发分支另行安排；正式远端 0.10.0 附件的离线安装核对仍待补；WorkBuddy 黑盒与真实并发未执行、未验证。升级请使用 0.10.1 种子包。

## 附件校验和

源码包及种子包 SHA256（文件名与完整哈希，与 Release body 一致）：

- `MCP_CREO_MechDog-0.10.1-source.zip`：`eb0caf3d4dcb76d05d0ba7a77e93d5fd978893fbae637dc81148397cd37dc55f`
- `MCP_CREO_MechDog-0.10.1-seed-library.zip`：`c35e7602fb85124ab9627e92e5ba2dfa47575bcb407b07f73b9e9a87efc4c6b8`（确定性构建两次同哈希）

GitHub Release 链接与发布状态：[v0.10.1 已正式发布](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.10.1)（非草稿、非预发布；四附件远端哈希逐件核对通过，详见[发布验证记录](validation/RELEASE-0.10.1.md)）。
