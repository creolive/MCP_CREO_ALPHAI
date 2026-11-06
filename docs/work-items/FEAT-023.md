# FEAT-023：控制工具返回体积——capabilities 摘要与分页实施卡

日期：2026-10-20 细化（原为统一台账条目）；2026-10-31 0.10.0 更新。类型：功能。优先级：P2。状态：T09A 已交付（0.10.0：组件身份投影与保存重载/删除重插实机通过）；capabilities 子项已闭环；**0.15.0 已交付** compact 判据白名单、列表预算与 `full_detail_hint`（离线，真实 stdio 字节核对未跑）；其余体积议题未完成。目标版本：0.4.2（用户指定 PATCH 例外，同 FEAT-044）/0.10.0/0.15.0。

## 当前剩余范围（2026-10-21）

capabilities摘要/分页已随0.4.2交付、0.4.4补验收闭环；0.4.5的README摘要接口用法已交付，见[发布记录](../validation/RELEASE-0.4.5.md)。旧实施段中的“过期/跨实例未实测”仅描述早期阶段，不再是当前缺口。

剩余jobs compact日志、组件清单内联业务label及source_model_id/source_revision、翼型/履带请求与日志、union校验错误体量。历史触发量包括jobs日志超过4KiB、两组件列表170512字符、翼型请求/计划超过30KiB、union错误约96KB；0.3.5组件清单model_name仍是C_…_0派生名，业务label需从aliases恢复。后续按UTF-8预算核对，保留job/model/revision、身份/实际矩阵/放置、错误及详情入口，评估truncated/complete；不能用裁剪输出代替BUG-053计算优化，也不能把自动命名直接认定为数据丢失。

来源：多轮能力边界反馈；最新 [v0.4.1 / Creo 10 反馈](../validation/FEEDBACK-0.4.1-CREO10-2026-10-20.md) P2-1（capabilities 单次 106,380 字符，超宿主单次工具结果上限被截断落盘）。

## 目标与范围

本卡为 FEAT-023 中 **`creo_capabilities` 摘要与分页** 的实施部分。其余体积议题（jobs compact 日志、组件清单内联身份、翼型请求体量、union 校验错误、履带请求与日志）仍留台账原条目，随各自触发项处理，不在本轮范围。

## 实施契约

- `creo_capabilities(detail="compact"|"full", section=None, limit=50, cursor=None)`；默认 `detail=compact`。
- compact 返回顶层摘要：名称、版本、更新、工具计数、scope、顶层支持状态表、operations 与 families 名录、section 清单与查询示例、分页说明。单次控制在既有序列化口径内。
- detail=full 按 section 分页：`overview`（除下列大节外的顶层契约）、`tools`（工具清单与 unavailable）、`families`（能力族）、`references`（引用格式）、`seeds`（种子库）、`evidence`（验证证据）、`runtime`（运行身份与源码指纹）。
- 单页按现有序列化口径限制 32 KiB（UTF-8 字节，含分页元数据）；超大集合按条目拆分，不静默截断；单条自身超预算时明确报错并给指引。
- 详情使用进程内冻结快照：600 秒过期；服务重启、cursor 过期/失效、快照指纹变化时明确拒绝并指引重新以无 cursor 查询。
- compact 与 full 的 overview 字段保持一致（同一快照派生）。
- 同步修改默认返回结构变化的迁移指引（capabilities 说明与 README）。

## 验收标准

| 场景 | 可判断的预期结果 |
| --- | --- |
| 默认 compact | 无参调用返回摘要页，显著小于旧全量输出，含 section 清单与 next_cursor 指引 |
| 分页遍历 | 逐 cursor 翻完每个 section 无遗漏、无重复；页大小不超 32 KiB |
| 超大单项 | 单条超预算明确报错/标记，不静默截断 |
| 错误 cursor | 未知 section、非法 cursor、快照变更后拒绝并指引 |
| 过期与重启 | 超过 600 秒或服务重启后旧 cursor 拒绝 |
| compact/full 一致 | 摘要字段与 full/overview 同源一致 |
| 迁移指引 | 文档说明默认结构变化与旧消费者迁移方式 |

开发侧以单元测试覆盖分页/游标/过期/一致性；实机仅验证真实调用路径（compact + 至少一个 full section）。

## 实现与证据

2026-10-20 实施：包内 `creo_mechdog/capability_pages.py`（进程内冻结快照 600 秒+实例 id、compact 摘要、七 section 条目化分页、32 KiB 预算、oversize 显式标记、cursor 失效拒绝）；server `creo_capabilities(detail,section,limit,cursor)` 默认 compact 并携带迁移说明；README 开发分支段同步迁移指引。证据：新增 8 项单元（遍历无遗漏/oversize/过期/快照变化/一致性）；stdio 直连实测 compact 10,471 字节（旧 106,380）、references 9 页翻完、tools 87 条 complete、非法输入拒绝，见[验证记录](../validation/FEAT-044-live-2026-10-20.md)第二节。600 秒过期与重启拒绝由单元覆盖，实机等待注入与超大真实 evidence 单项观察未执行；其余体积议题仍留台账原条目。

## 2026-10-21 补验收：过期、跨实例与超大实际内容

按[完善计划](../development/CREO10-0.4.1-FEEDBACK-IMPROVEMENT-PLAN-2026-10-20.md)补齐 capabilities 分页此前仅单测覆盖的场景（`build/feat023_paging.py`，stdio 直连实机）：篡改 cursor 拒绝、跨实例（等价服务重启）旧 cursor 拒绝、**610 秒真实等待后的过期 cursor 拒绝**、tools 节 13 页翻完 87 条无遗漏（单页峰值 32768 字节，32KiB 上限生效）。详见[验证记录](../validation/DEV-027-030-IMPROVEMENT-2026-10-21.md)。本子项闭环；jobs 日志、组件内联身份等其余体积议题仍留本卡。

## 2026-10-23 外部 Creo 9 证据补录（第八轮，2026-10-25 归档登记）

- 外部第八轮确认：capabilities 104KB 问题已修（compact 摘要 + 分节），外部按 compact/detail 正常消费。归档见 [feedback-0.5.0-0.5.1-2026-10-23](../validation/feedback-0.5.0-0.5.1-2026-10-23/manifest.json)。

## 2026-10-28 DEV-051 T09A：组件清单内联业务 label 与源件身份（离线实现）

本卡剩余范围中的“组件清单内联业务 label 及 source_model_id/source_revision”已按 [0.7.0 派发表](../development/0.7.0-FEEDBACK-TASKS-2026-10-28.md) T09A 离线实现（FEAT-023/008）：

- 关联键固定为**模型身份（model_id）+ feature_id**，label 不作身份；多标签以 label_state="multi" + bindings 表达，已删除身份以 deleted_identities（reason=feature_id_not_in_verified_components）独立表达，旧引用不会误指重插后的新组件。
- 查询投影实现于包内 `src/creo_mechdog/component_identity.py`，接入 `creo_list_components`（组件记录内联 label/labels/label_state/source_model_id/source_revision/bindings，顶层新增 deleted_identities/identity_key）与 `creo_inspect_model` 的 components 节/整页快照；不修改 C_<job> 物理副本命名，不改写存储载荷。
- 离线证据：`tests/unit/test_component_identity.py` 16 项 + 既有 86 项定向回归通过；compact 不展开、full 分页与整页一致、aliases_ref 详情引用解析、40 组件分页全程 ≤ 32 KiB。详见[验收记录](../development/DEV051-T09A-ACCEPTANCE.md)。
- 未关闭本卡其余体积议题（jobs compact 日志、翼型/履带请求体量、union 校验错误）；实机跨作业装配查询/保存重载与大装配体量验证待统一安排，工具描述/README 补充由 T01 收口。

## 2026-10-30 DEV-051 T09A：保存重载关联与删除重插不误指（离线回归锁定，生产零改动）

提交 `a8fbf40`，基线 `7c650cf`。本轮**未改生产代码**（只改 `tests/unit/test_component_identity.py` 与 `tools/test_component_labels_live.py`），未连接 MCP/Toolkit、未启动 Creo、未改版本、未合 main、未 push、未发布。

- 依据原生既有保护判定无需生产修改：保存作业原生即 `ProMdlnameBackup` → `ProMdlErase` → 从磁盘重载 → `verify_saved`，其中逐组件比较前后 `feature_id` 与 `model_name`，id/名漂移直接作业失败；删除组件时原生即删除该 feature_id 的全部别名条目。绑定存登记侧，重载不重写。
- 新增 3 项回归（16→19 例）：保存重载后同 id 记录标签与镜像完全不变且 `deleted_identities=[]`；重载后 id 重排时当前记录全部 unlabeled、旧 id 落 `deleted_identities`、绝不改绑新记录；remove 后同 label 重插只绑新 id、旧 id 不出现在任何当前记录或 `deleted_identities`。
- 驱动强化：live `cross_job` 现在要求 save 作业 `saved_file_reloaded_and_verified=true` 且两组件 identity/source 镜像逐项不变；live `rename_reinsert` 新增 `old_label_observable` 记录旧标签可观测落点（预期 `absent`）。
- 离线证据：19 项单测 OK、77 项定向回归 OK、离线驱动 exit 0（`build/component_labels/20261030T100437_7052fa7b/report.json`，projection 4 项 true、reload_guard 3 项 true）、`bridge.py build` 通过。
- **仍未测**：实机保存重载后关联、删除重插复验、多标签挂同一 feature_id、被篡改 `aliases_ref`、40 组件大清单分页、compact/full 一致性、Creo 9/10、WorkBuddy。
- 本卡其余体积议题（jobs compact 日志、翼型/履带请求体量、union 校验错误）仍未做。

详见 [T09A 验收卡](../development/DEV051-T09A-ACCEPTANCE.md) 2026-10-30 节。本条保持开放（实机重载与删除重插复验未执行）。

## 2026-10-31：N09 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n09/run1/report.json`（SHA256 `d2fe2233…ec4ef`，`run_id=20261031T132838_ae4d387e`，`mode=live`，`passed=true`，`stopped=null`）。本节只追加，不改写 2026-10-28/30 的离线记录。

- **双组件创建通过**：`two_components`，装配作业 `a272ed6046ea4d6aae60d9c5c772fcad`、model `15e103e217d14c5f879a17084839c345`、rev 1、status succeeded。`part_alpha` 解到 feature ID 40（源 `25831b7c7d694efeb57dacc05b34f63e`、源 rev 1），`part_beta` 解到 feature ID 43（源 `6ac989cd03414b54bfbd413a95a2e0c2`、源 rev 1）；两个 label 的 `label_state` 均为 `single`，`source_models_match=true`。
- **跨作业保存重载通过**：`cross_job`，保存作业 `5328f322486446c5a14d842b19d7ad59`（kind=save）succeeded、`saved_file_reloaded_and_verified=true`、重载后 rev 2、标签集合仍为 `part_alpha`+`part_beta`，`identities_unchanged=true` 且 **`identity_mirrors_unchanged=true`**——2026-10-31 早先的 canonical sort key 修复（`018f9c3`）实机生效，上一轮的 `TypeError: '<' not supported between instances of 'dict' and 'dict'` 不再出现。
- **删除重插不误指通过**：`rename_reinsert`，删除作业 `442b6fa5502a4639b264d8a826d46879` succeeded、重插作业 `16d90da61d3d440190dcacef4f79bbb7` succeeded，rev 2→4。`part_alpha` 仍绑 feature ID 40，新 `part_gamma` 绑 feature ID 46（源仍是 `6ac989cd03414b54bfbd413a95a2e0c2`）；`deleted_identities=[]`、`old_label_observable="absent"`、`old_label_on_new_component=false`、`stale_binding_on_new_id=false`——旧 label `part_beta` 没有落到新 ID 上。
- **未知 label 拒绝通过**：`unknown_label`，作业 `3f55cef59a374cf59ba8e027be8795a0` failed，`toolkit_code=-1`、`failed_stage=execute_component_placement`、`rollback_succeeded=true`，原生消息 "Unknown feature label: part_beta; available labels: part_alpha, part_gamma"；revision 4→4 未变，`labels_after` 仍为 `part_alpha`+`part_gamma`。注意 `rejected_at_admission=false`——拒绝发生在原生放置阶段而非入口准入，消息按实际可用标签给出。
- **`id_renumbering` 半场景限制保持**：本轮 live 矩阵不含独立的 `id_renumbering` 判定行，原生在保存路径上拒绝重编号，**只能观察拒绝、不得整体记为实机通过**的限制不变。

本卡"组件清单内联业务 label 及 source_model_id/source_revision"子项的实机四例本轮全部按预期通过；本卡其余体积议题（jobs compact 日志、翼型/履带请求体量、union 校验错误）仍未做，整卡保持开放。

## 2026-11-06 compact sections 投影（Q06/R04，离线实现，未实机）

- 新增 `src/creo_mechdog/compact_sections.py`：从 `bridge.compact_job` 抽出结果块/操作块名单，提供 `resolve_sections`（非法名报错并列出全部已知块）与 `apply_sections`（只删未点名块、不改数据、不增数据）。
- `creo_get_job` 与 `creo_list_jobs`（detail=compact）新增可选 `sections: list[str]`；响应顶层新增 `sections_applied` 与 `omitted_sections`；`sections=[]` 只留结果证据；未点名块不出现；`detail=full` 传 `sections` 直接拒绝。
- 证据字段不可被裁：status/revision/message/code/toolkit_code、回滚与保存重载证据、每条 operation 的身份与失败证据（`feature_errors`/`failed_stage`/`failed_toolkit_call`/`failed_operation`）恒保留；投影先于 32 KiB 预算与 20 条采样上限执行。
- 未知块名在读取 job 目录前拒绝，`job.json` 字节不变（单测断言）。
- 验证：新增 `tests/unit/test_compact_sections.py` 14 项；连同既有 compact/budget/分页回归 109 项通过；全量 `tools/test_unit.py` 2477 项通过（0 失败 0 错误）；`dev_check.py --skip-unit` `success=true`。
- 未验证：实机 Creo、MCP stdio 客户端、WorkBuddy 黑盒均未跑。本卡其余体积议题（jobs compact 日志、翼型/履带请求体量、union 校验错误）仍开放。

## 2026-11-06 R04：compact 判据可见、列表项有界（FEAT-023/FEAT-039，离线实现）

- 新增 `src/creo_mechdog/job_projection.py`：`compact_operation`/`compact_progress`/`compact_job_list_item` 纯白名单投影，只复制原生已产生的键，`null` 与 `reason` 原样保留，缺失不补 0。判据键：`surface_trim` 的面积前后值与状态、`kept_side_basis`/`kept_quilt_*`；`surface_offset` 的 `source_area_mm2`/`source_area_status`/`measured_offset_distance_mm`/`direction`/`offset_method`/`target_quilt_id`；`project_curve` 的 `source_length_mm`/`curve_length_mm`/`endpoints_mm`/`curve_id`/`helper_*`/`route`；`solidify` 的 `closure`。
- compact 不再返回 `native_log_tail`，`native_progress` 只留阶段/计时（不含 `log_tail`）；`detail=full` 的日志与分页路径不变。compact 顶层新增 `full_detail_hint`，写明 `detail="full", section="operations_result", limit, cursor`。
- 顺序：先按 `sections` 选块，再做 operation 投影与采样/32 KiB 预算；`sections=[]` 仍只留结果证据。每条 operation 的 `failed_operation` 加入失败证据白名单；预算裁剪额外保留样本窗外的失败记录（仍以 `operations_total`/`operations_truncated` 报总体）。
- `creo_list_jobs` 的 compact 改为固定有界条目（job/model id、status、stage、时间、outcome、≤200 字 message；`job_id` 即详情入口）。`sections` 仅为兼容校验，对固定条目不再生效，需用 `creo_get_job` 取块。实测 50 条最大单条 618 B、整列表 32102 B；1000 op 的 compact 为 5828 B（保留 20 条 + 总体标记）。这一变化取代本节 2026-11-06 sections 段中“list_jobs compact 应用 sections”的描述。
- 验证：新增 `tests/unit/test_job_projection.py` 18 项，更新 `test_compact_sections.py`/`test_job_query.py` 的列表与日志断言；连同既有 compact/budget/分页/operation 回归 91 项通过。
- 未验证：实机 Creo、MCP stdio、WorkBuddy、native 实测判据值均未跑；本卡其余体积议题仍开放。

## 2026-11-06 R04：协议验收与请求/执行视图分离（离线 stdio，未实机）

- 新增 `tests/unit/test_job_query_protocol.py`（8 项）：子进程 `python -m ... --serve` 启动真实 `server.py`，数据根隔离、预置 52 个 job 目录，全部断言经真实 MCP stdio 客户端读取结果；未提交作业、未占 Toolkit 通道、未启动 Creo。
- 字节：compact 35 op 与 1000 op 均 ≤ 32 KiB（千 op 报 `operations_total=1000`/`operations_truncated=true`/样本 ≤20/状态计数合计 1000）；`creo_list_jobs` 50 条逐项 ≤620 B 且不含 `result`/`sections_applied`。
- 保护：失败位于样本窗外（index 34）仍保留该记录及 `failed_stage`/`failed_toolkit_call`；约 3 KB 中文长错误在 `message` 与 `result.message` 原文保留且仍是合法 UTF-8。
- sections：省略无 `sections_applied`；`[]` 只留结果证据；`["preview"]` 保留 preview 与精简 operations；`["operations"]` 反之；非法名 `isError` 并列出已知块名；保护字段与 full 一致。
- full 分页：`section="operations_input", limit=5` 逐 cursor 取回 35 条无遗漏，最终 `next_cursor=null`；surface_trim/surface_offset/solidify/flange miter/assembly pose 与 `planar_wall.thickness_validation` 的 null、状态码与 reason 与 full 逐键一致。
- **请求/执行视图分离（0.14.0）**：`generic_bridge.submit` 写 manifest 时新增 `operations_view="normalized"`；`job_pages` 的 full 分页摘要同步携带（历史作业无此键则不补造）。省略 depth 的归一化执行值仍为 1，但 `defaulted_fields` 标出省略来源，`extrude_depth.requested_depth_mm=null` 的既有语义不变；未新增 `depth_ignored` 同义块。
- 新测试 `test_submission_distinguishes_omitted_and_explicit_depth`：省略 depth、显式 depth=1、through_all 省略 depth、through_all 显式 depth=10 四例 × `creo_extrude`/`creo_execute_plan` 两入口；入口层省略字段保持缺失，提交回执、提交后 full 与 full 分页读到同一 normalized 视图。35 op 提交回执序列化仍 < 32 KiB，故未改提交投影。
- 验证：两模块定向 23 项 OK；全量 `tools/test_unit.py` 2672 项 OK；`dev_check.py --skip-unit --work-item FEAT-023` `success=true`。
- 未验证：实机 Creo、WorkBuddy 黑盒、真实客户端取消/断流；本卡其余体积议题仍开放。
