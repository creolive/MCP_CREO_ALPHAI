# DEV-071：0.16.0 三件反馈离线对账

2026-11-07；基线 main `191c05f` / 0.17.1。[manifest](manifest.json) 的三份原件来自用户指定 Downloads/chatgpt，逐字节归档。报告实机结论均为**外部 Creo10 / 0.16.0**，不视为当前版本复测；不执行原件的故障注入、结束进程或自动重交建议。

## F01：四壁盒、板厚、居中

| 原件章节 | 当前处置 |
| --- | --- |
| §一、二：四壁、第二组框边、守卫/预览 | 保留外部正证据；第二组单条框边不是完整多段模型通过 |
| §3.1 missing_api板厚 | 0.16.1已交付受限geometry_normal_span；不重复，Creo10缺API路线仍未实机 |
| §3.2 首壁居中 | 0.17.0 origin与保持原点resize已交付，不重复 |
| §3.3 切角量 | R09有本机定标，更多width/offset/厚度矩阵仍未测，不从元素回执推导实际切除量 |
| §3.4 计划选边 | 0.17.0折边edge_geometry已交付；不扩展为所有round的单锚点匹配 |
| §3.5—五 | relief/end_trim、完整多组框边按原卡继续；模型/job索引保留外部来源 |

## F02：混合线弧53mm、autodim、frame

| 原件章节 | 当前处置 |
| --- | --- |
| P-A / §3 | BUG-050/FEAT-010：缺完整P05输入/native.log，“5线”与DOF估算“8线”不一致，过约束为假设；本轮不改尺寸策略/保真门 |
| P-B / §4 | 初次Solve=-1之后原代码可由Autodim恢复，最终Autodim/Regenerate非零已有拒绝；新增solver各阶段真实码、completed/recovered，不一见-1就失败；autodim告警与显式容差硬门不变 |
| P-C / §5 | 公开原metadata的solver.requested/used，新增selection_reason；新创建/编辑/失败上下文共用，不增同义字段；历史缺阶段时不从最终aliases回填（可能已被后续编辑覆盖） |
| P-D / §6 | O/u/v/n直接建支撑面、round单锚点选择保留独立原生设计；frame求解根因未定 |
| P-E / §7 | 原生已有failed_features的id/name/type/status有界投影到failed_operation；状态不冒充ProError，未知码保持null/unsupported |
| P-F / §7b | Toolkit标注性能未测；BUG-092已有独立runner/离线断开保护，外部进程树终止仍待R12现场，不改超时/unknown保护 |
| §7c I032 | 继续R05/BUG-045；0.16.1有精度分类，1e-6准入不变，内核拒绝根因未定 |
| §8—10 | 规避方案/最终模型为外部记录；TXT、parsed计划和完整job附件缺失，本轮不宣称原案或整车保真通过 |

## F03：收口、miter、更新、曲面链

| 原件章节 | 当前处置 |
| --- | --- |
| §2 正例 | 保留外部长轮询/曲面判据/尺寸守卫等正证据，不外推跨版本完整路线 |
| §3.1 miter仅aliases | FEAT-014/023确认公开链路缺口，白名单已有但原生flange只remember；补收尾与历史受控aliases_ref只读投影，compact/full/operations_result/sections同源，不伪造echo_matches_request |
| §3.2 更新 | FEAT-020：默认5秒总预算，可配环境变量MECHDOG_UPDATE_TIMEOUT_SECONDS有限1..30；force绕过已完成缓存，共用在途请求；回执实际预算/缓存年龄/下次普通重试时间；本地tag不冒充GitHub最新版 |
| §3.3 曲面整链 | R11门禁保持：quilt_merge、多截面surface loft、boundary_blend继续开放 |
| §3.4 offset | 修capabilities/references/语法文案：offset wall可产生实体体积，target_quilt_id为源quilt，不承诺新结果quilt；0.16.1计量闸门保留 |
| §3.5 保存失败 | BUG-113原环境未验；save_failure/rollback_difference恒保留，不新增同义sections或伪造历史原生诊断 |
| §4—附录 | identity unknown与live连接分层、未测项和job索引保留；不读取外部运行目录 |

验证见[DEV-071](../../work-items/DEV-071.md)：独立工作树离线运行，不修改E盘部署/执行器/Toolkit锁；原生诊断未SDK构建/实机，53mm形变及frame求解未关闭。本分支不改版本、不合main或发布。
