# 0.14.0 两件反馈合并映射（DEV-069）

日期：2026-11-06。受评源码：main `4517e36` / 0.16.0；本轮未做产品测试或Creo连接。两件原件逐字节存放 `originals/`，大小和完整SHA256见[manifest](manifest.json)。统一进入[原修复计划](../../superpowers/plans/2026-11-06-0.13.0-feedback-repair-plan.md)，不另建平行实现计划。

来源A：`2026-11-06+CREO+0.14.0+旋转阵缺陷跨版未修与失败事务标注自相矛盾.md`，18,068 B，外部Creo10运行时反馈；来源B：`2026-11-06CREO10.0.0.0-0.14.0-上版反馈四项跨版未修与C4552二次重现.md`，16,491 B，安装/编译/离线反馈且明确未连接Creo。两份验证边界分别保留。

## 核心增量

| 来源 | 内容 | 对照0.16.0的结论与处置 | 归属 |
| --- | --- | --- | --- |
| A §4.1 | I032截断矩阵放行后装配-2 | Python与原生均仍用1e-6，仍会接受此输入；高精度30°可用不等于任意截断阵可用。补准入兼容设计与原生边界，不能只补诊断 | FEAT-012/BUG-045，R05升P1 |
| A §4.2 | 已验证擦除的新件仍effect unknown/component_changes unknown_outcome | 当前finalize只看rollback、component_changes也不消费cleanup证据，静态缺口仍在。新增BUG-114/R13，作用域限定受管模型，保持真实未知保护 | BUG-114，关联BUG-096/FEAT-008/023 |
| A §4.3 | 失败op缺ProError/矩阵/残差 | 0.15.0已有顶层failed_operation，含pro_error/input_matrix/residual/det；逐op字段仍有投影/定位待验。复用现名，不新造matrix_echo等同义字段 | R05/R04 |
| A §4.4 | compact内联日志 | 0.15.0已有独立列表投影与日志去除，当前退出开发，只补真实协议/负载证据 | FEAT-023，R04 |
| A §4.5/§4.6 P-11 | through_all省略depth却提交响应含depth=1 | validate_operations归一化后仍写manifest.operations并返回，0.16.0仍有来源区分问题；明确requested/normalized视图与defaulted_fields，不以默认值冒充原请求 | FEAT-008/023/039，R04增量 |
| A §4.6 P-1 | execute_plan旋转约定未声明 | 当前已在schema透出row-vector公式与rotation_convention/assembly_pose_receipt，退出重复开发 | R05保留实读验收 |
| A §4.6 P-6 | 装配无bbox | 尚未实现真实整体bbox；沿用原剩余任务 | FEAT-008/BUG-013，R12 |
| A §4.6 P-8 | connected但health stale/unknown | 新重试/health分层已有；成功连接不能强制总体health=ok，保留真实现场和事实层验收 | FEAT-001，R06 |
| A P-9 | 本轮busy未复现 | 不以busy=false宣布已修；唯一通道语义保持 | BUG-009/FEAT-001 |
| A P-10 | managed rename/delete仍无 | rename沿FEAT-062，delete仍待独立设计；不拿erase_session代替 | R12 |
| A P-7/§6 | 组件来源映射、70组件旧成果快照未漂移 | 正面历史证据，不重做映射；快照读取不等于live重算 | FEAT-023/FEAT-008 |
| A P-3/§7 | 共面相切本轮未复现、部分场景未测 | 不推断根治；保留替代夹具与原案边界 | R05/相关旧卡 |
| B §4.1 | C4552/Init错误二次重现 | 发生在0.14.0；0.15.0 BUG-112已修并加/we4552，记跨版证据，不重新实施 | BUG-112，R01仅计量余项 |
| B §4.2 | FEAT-039/DEV-067首页未回填 | 当前卡已对齐至0.16.0/A02，保留旧失配事实；发布卡首页与实际版本仍随交付核对 | DEV-062/069，R07/R99 |
| B §4.3 | 四附件闸门未接打包/CI、无gh | 现包内统一校验/package硬闸门、gh失败--dir降级及离线测试已实现；API备用下载仍可选，不再强制新造流程 | DEV-070，R08 |
| B §4.4 | sidecar CRLF | 当前write_sidecar固定ASCII/LF且读旧CRLF兼容；不覆盖已发布0.14附件 | DEV-070，已退出开发 |
| B §4.5 | 0.12.0/0.12.1/0.13.0归档积压 | 0.12.0与0.13.0已归档，0.14.0本次2件归档；0.12.1原件不在本次目录，仍标缺件，不虚填 | DEV-069/R00 |
| B §3 | README链接/100工具/台账版本已对齐 | 当前0.16.0仍已对齐，作为保持项，不重复开发 | DEV-062/069 |
| B §4.6 | PATCH性质/MINOR号措辞 | 观察/文档问题，后续按真实接口变化核定版本；历史发布文案不改成新证据 | R07/R99 |
| B §4.6 | API列表发现新版本延迟 | 报告自身标观察非项目缺陷；不确定是缓存、排序、代理或网络，不据此改更新算法。可记录tag直查/checked_at/stale交叉核对 | 观察，不新增BUG |
| B §1/§6 | 新能力运行时全部未验证 | 只限B的离线轮；不得用A的实跑改写B，也不得把B的未测当全项目未测 | 证据分层 |

## A/B矩阵回归载荷（保留原值）

```json
{
  "truncated_i032": [[0, 0.307383, -0.951586], [0, 0.951586, 0.307383], [1, 0, 0]],
  "orthogonal_30deg": [[0.8660254037844387, 0.5, 0], [-0.5, 0.8660254037844387, 0], [0, 0, 1]]
}
```

本次纯数学复算：I032最大正交残差 `2.2408500011117383e-7`、det `1.0000002240850001`、行范数 `1.0000001120424937`。当前Python和native的1e-6检查都会接受。外部0.14.0 job前缀017c62e4返回ProAsmcompAssemble=-2，高精度30°的bfc3551e成功；这支持“可接受输入与内核行为存在缺口”，**不能直接证明1e-9是内核要求或-2仅由该残差导致**。不自动正交化、不增加continue_on_error部分提交。

## 外部正证据增量（不冒充本轮/当前版本验证）

- A §3.1，0.14.0 / Creo10 / job前缀614486aa：40×40×1减10×10×1，volume=1499.9999999999995 mm³、removed=100.0；省略深度回执blind/1mm，through_all的effective_depth_mm=null，saved_file_reloaded_and_verified=true。只覆盖报告所列命中案例，不替代完整正/负/对称矩阵。
- A §3.2，job前缀1c5aa1c2：jpeg只读、revision1→1、preview written、渲染码全0；外部操作者人工目视确认20×10×5长方体，非空白/错误画面。只读saved_file_reloaded_and_verified=false符合契约。它只关闭该外部样例的human_review_pending，不关闭作者所有预览图的人工复核。
- A §3.3：017c62e4的失败新装配cleanup erased/absence_verified=true是清理正证据，但事务标签矛盾归BUG-114；不是已有检查点回滚成功。
- B §2/§3：0.14.0官方包1354/1354字节一致、SDK零补丁编译、种子9/9与附件校验/回调指纹稳定，均限该安装环境，不外推新运行时。

## 缺件与统计边界

A自述7个作业，但作业表只列A0—A4五项，且大多只给8位job/model前缀；未提供完整job/native/preview附件。保存原文，不补造第6/7项或完整UUID。前序“0.13.0旋转容差报告”不在这两件原目录内；本次已有精确矩阵可固化替代回归，原始现场完整记录仍待补。B的本机_local路径仅是报告索引，本轮未访问另一环境配置。
