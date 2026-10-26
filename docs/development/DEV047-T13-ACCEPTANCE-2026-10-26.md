# DEV-047 / T13 集成、离线全量与本机实机矩阵（阶段交付）

日期：2026-10-26（Asia/Shanghai）。条目：DEV-047 T13（进行中——实机几何/生命周期/回放矩阵已通过，发布与若干专项待收口）。基线 `402821e`（T00—T12 已纳入）；分支 `codex/dev047-feedback052`；本阶段集成提交 `55d95f3`。版本仍为 0.6.1，0.7.0 发布未执行。

执行方式：实现任务 T02、T06—T12 由用户指派的实现子代理完成（其中 T11/T12 因子代理后端连续拒绝，分别由集成负责人核对收尾/直接实现，已在各任务记录注明）。本 T13 阶段由集成负责人在同一集成源码上完成离线全量验证与本机 Creo 12.4 串行实机矩阵；实机前按纪律先以只读探针观察（首探与后台构建冲突呈现 building_worker，构建结束后重探仍处准备态，改由各驱动自身 wait_ready 只读观察把关，ready 前零建模提交）。全程串行占用 Toolkit 通道；未重启/结束 Creo、未清 unknown 保护；config.json 的 auto_start_creo 探测前置（临时置 false，finally/事后恢复原始字节，已核对恢复）。

## 实机矩阵结果（本机 Creo 12.4.0.0，E 盘 dev 工作区）

| 驱动 | 结果 | 关键证据 |
| --- | --- | --- |
| `tools/test_t12_examples.py --live` | 通过 | 批量 6 操作→6 条零基结果（succeeded/committed），revision 1→2 恰 +1，体积 18217.256661176918 与解析逐位一致；Ø6×3 凸台 11° 拔模双方向断言：默认方向外张 102.3792320079577、flip 内收 69.40338944368688，均与圆台公式吻合（真实面 id 57 来自巡检）。报告 `build/t12-examples-live.json` |
| `tools/test_t06_native.py --live` | 通过 | 合法多环 9/9（2/5/10 圆、5/10 四弧环、2 圆+5 四弧、嵌套）单原生特征体积=面积×深度；6 类非法输入（相交/相切/零面积/自交/近容差/开链）准入拒绝并给类别与计数；失败回滚后合法操作可用。`native_acceptance=passed`、geometry/admission 矩阵 passed。报告 `build/t06-native-live.json` |
| `tools/test_t07_preview.py --live` | 通过 | 盘体/切除/阵列三阶段预览 written+file_verified、全部捕获步骤返回码 0、窗口↔模型一致；显式 JPEG 导出成功且操作级携带导出文件；失败与保存解耦。`preview_acceptance=passed`，图像内容留人工复核（`build/t07-preview/*.jpg` 5 张）。报告 `build/t07_preview_acceptance.json` |
| `tools/test_t08_feature_state.py --live` | 通过 | 抑制/恢复/删除/墓碑/过期 revision/失败回滚/删除后合法编辑全链路；级联发现：首次抑制被拒并列出 Creo 连带抑制的伴随基准面（id 81/88）且真实回滚，补列后成功，登记键集与体积/回滚一致。报告 `build/t08_feature_state.json` |
| `tools/test_t09_assembly_replay.py --live` | 通过 | 六类约束+default 完整回放到新装配（先插入后约束）；同层兄弟引用（assembly_component=t_base）；真实随动（mate_offset 25→40 与源件尺寸编辑两条驱动路径）；缺失映射/缺根引用/快照过期/旧 schema/源件变化五类拒绝；源件与目标模型不变性（目标 revision 不变、源件体积不变）。报告 `build/t09_assembly_replay.json` |

T05 毫米几何矩阵此前已在该通道通过（18/18，见 T05 记录 Live03）。失败尝试原始报告全部保留（`build/t06-native-live-attempt1-failed.json`、`build/t12-examples-live-attempt*.json`、`build/t09-assembly-replay-attempt*.json` 等），不以下游修复掩盖首次失败形态。

## 实机发现的缺陷与修复（提交 55d95f3）

1. **system_required 误标（native/generic.cpp）**：原分类把一切无父基准面当模板几何；实机中本服务为草图/拉伸创建的伴随基准面也无父，导致"被 Creo 连带抑制却不可显式列出"的死锁。修正为仅初始特征块内（首个非基准/非坐标系特征之前）的无父基准面计为模板。
2. **抑制/删除隐式级联未拦截（native/feature_state.cpp）**：Creo 会连同伴随基准面一起抑制/删除目标特征，原实现只登记显式目标，健康检查因"未登记的抑制"失败。新增执行后实测集校验：实际受影响集合超出显式目标（或已登记集）即拒绝并列出清单，保持"不自动级联"契约；T08 驱动据此自适应补列。
3. **full 快照 whole 快路径缺 feature_state 段（src/creo_mechdog/model_queries.py）**：与 T05 修过的 BUG-077 同类形态分歧；whole 快路径现与分页形态携带同一有界 feature_state 段，新增单测 `test_whole_full_shape_carries_feature_state_section`。
4. **回放规划器逐约束生成 component_constraints（src/creo_mechdog/assembly_replay.py）**：原生 ProAsmcompConstraintsSet 整组替换，逐约束操作只剩最后一条；改为每组件一条操作（两个既有单测更新为新契约）。
5. **驱动/夹具缺陷**（不影响生产语义）：T06 拒绝案例悬空草图引用、T07 导出操作级 preview 预期、T08 凸台位于基体内部、T08/T09 多处大小写与路径/异步作业轮询、T09 pin 夹具无平面侧脸与底面法向假设、T12 拔模方向常量以实测修正为双方向断言。
6. 示例 `dev047_t12_draft_boss.json` 方向说明按实测定论更新（默认外张、flip 内收）。

## 离线全量验证（同一集成源码 55d95f3）

| 命令/检查 | 结果 |
| --- | --- |
| `python bridge.py build` | 通过；`creo_worker.exe` SHA256 `B08851C3E7734295AD1E5874E3AF748DE500B3DEE0962E43DBB6A454908D6A7B`（含修复 1/2 重编） |
| `python -m unittest discover -s tests -q` | 965 项通过，205.428 秒，exit 0（`build/t13-unit2.log`） |
| `python tools/dev_check.py --work-item DEV-047` | exit 0、`success=true`、`unit_tests=passed`；`checked_source_sha256=d4b68c1ace7be6863cebeb64d149f5966a6469878d073cb89df4a268bbd358ad`；style 维持既有基线（lint 30 / 未格式化 16），一次中间运行暴露的未格式化文件已按格式化修复后复跑通过 |

工作区仅余 `session_activity.json` 用户运行数据修改与既有未跟踪运行文件；`docs/validation/` 原件未动。

## 未测与保留范围（T13 未完成项）

- **T05 尾项**：原生非毫米坐标、unknown 单位/查询失败覆盖仍 pending（毫米矩阵已过）。
- **T07**：预览图像内容的目视复核待操作者确认（图像已留存）。
- **T10 三现场**：FEAT-006/BUG-078 口径冲突的只读 `creo_reconcile_model(mode="inspect")` 落定未执行。
- **T11**：真实世代目录的只读盘点（inspect）未执行；删除仍仅限隔离夹具。
- 装配矩阵/单位驱动（test_assembly_matrix/units）在新结果契约下的重跑、既有编辑/装配管线专项复跑尚未执行。
- 外部 Creo 9/10、WorkBuddy 黑盒、安装解包冒烟与 0.7.0 版本/发布（含 main 合入、标签、附件与 Release）未执行——发布须按派发表在全部约定验收完成且用户指派最终交付后实施。
- 实现子代理（写程序高手）自 T11 起持续 spawn 即拒（child_refusal ×5），用户侧待修复；T11 收尾与 T12 由集成负责人完成并全程记录。
