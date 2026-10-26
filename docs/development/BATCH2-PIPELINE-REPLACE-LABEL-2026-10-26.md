# 第二批实机收口：管线快照刷新改用新唯一 label（2026-10-26）

范围：FEAT-008/012 管线实机驱动 step 9e 被拒（现有别名预检契约）的最小修复与
离线回归。不连接 Toolkit、不启动真实 MCP server、不故障注入、不改客户端配置、
不改 `generic_bridge.py` 生产规则、不合并不推送、不改版本、不发布；历史
`docs/validation/` 原件未改写，本文件为独立新证据。

## 1. 实机现象（真实报告，只读）

报告：`E:/Projects/MCP_CREO_MechDog/build/assembly_pipeline_live_20261025T162553Z6eec525a/report.json`
（guard：`E:/Projects/MCP_CREO_MechDog/build/guarded_live_20261025T162020624286`，
child_1.log 只读未改）。源码基准：canonical detached `fc86231`
（md050 分支 `codex/feat012-matrix-pipeline` 同点，工作树干净起改）。

9 个父作业全部成功：两源件、两项独立收养、原装配三组件（重复 occurrence +
非对称组合旋转）、只读检查、重建 3 组件位姿与体积匹配、收养源追加凸台
体积 +600、装配 regenerate（revision+1）后仍旧快照。最后 step 9e 把同一
execute_plan `[remove_component component='plate_a',
assemble_component label='plate_a'（同一已编辑源、原位姿）]` 再次提交，入口返回
工具级错误 `Feature labels already exist: ['plate_a']`（isError=true），未受理、
无新 job、无模型变化。

## 2. 契约判定与修复边界

入口按计划内 assemble label 与目标既有别名求交拒绝（`generic_bridge.py`
submit 预检），**即使同一计划先 remove 该 label**——这是现有生产契约。本批
不为它扩展生产功能（不放宽、不特判 remove-first），也不包含显式 source 更新
API；`generic_bridge.py` 未改一字节（SHA256
`3F76263415E8FF6FA6D6E576C71CDFA2E0459820CF229EA9BAB5A6838AD91A78`）。

## 3. 最小修复（md050 离线）

- `tools/test_assembly_pipeline.py`：`replace_operations` 改为一个原子作业内
  remove 旧 `plate_a` + 以**新唯一 label** `plate_a_refreshed` 重新 assemble
  ——同一 `source_model_id`（当前 revision）、原冻结位姿、`op` 字段保留、
  输入 pose 不被 builder 篡改。step 9e 下游断言全部按新 label 读取：
  `component_changes` 保留 removed（旧 label、旧 feature_id）+ added（新 label、
  新 feature_id、当前 source_revision、`source_model_id` 不变）；最终 aliases
  中旧 label 已消失（防止后续按旧键读取 KeyError）；新组件 4×4 变换匹配冻结
  快照、`model_name` 为全新原生副本名；装配体积 origin+600；step 6/8 的约束
  数字码 + `type_name` 断言不变。
- 需保留原 label 的用户说明：先 remove 一个作业、再 assemble 另一个作业，
  各自 revision+1、独立提交；第二步失败不会撤销第一步。文档明确不得声称
  同 label 同作业可行。
- 文档/示例同步（只改快照更新方式相关语句）：`docs/ASSEMBLY_REBUILD.md`
  （source_snapshot 再生成方式、净重插摘要语义前提）、
  `docs/WORKBUDDY_FEAT008_PIPELINE.md` step 6、
  `examples/assembly_rebuild_pipeline.json` step 8（label `plate_b_refreshed`
  与两步替代路径）、`docs/work-items/FEAT-008.md` 本节登记、
  `docs/BACKLOG.md` FEAT-008 行。单作业插入多组件主重建流程、原装配只读、
  嵌套/FEAT-049/050/世代回收排除范围不变。

## 4. 离线回归（新增/更新）

- 新增 `tests/unit/test_pipeline_replace_alias_precheck.py`（3 项）：真实
  `generic_bridge.submit` 预检、临时 model registry（真实样式 32-hex
  model_id、`output/<name>.asm.1` 托管命名、`part_sha256` 基线、组件别名
  sidecar、就绪源件），native runner `subprocess.Popen` mock（只入队不执行），
  无真实 server、无 Creo：
  1. 复现原 remove+同 label 计划被既有别名拒绝（报文一致）、无作业目录、
     无 runner 调用、模型无 pending_job；
  2. 新 remove+新 label 计划在**同样既有别名环境**通过同一预检并入队：
     返回 queued manifest、request.json 操作/源引用/位姿正确、组件图含真实
     源件、模型登记 pending_job；
  3. 普通 reassemble 既有 label 同样被拒（预检非 remove+assemble 特有）。
- 更新 `tests/unit/test_assembly_pipeline_requests.py`：replace 断言改为
  新唯一 label + remove 目标旧 label，补 builder 不篡改输入 pose。

## 5. 环境与命令

Windows 11 x64 / Python 3.12.14 / md050 自有 venv；分支
`codex/feat012-matrix-pipeline`，基准 HEAD `fc86231`（
`FEAT-008/012: fix driver response-contract reads found in 2026-10-25 live runs`），
本次改动在 fc86231 之上，提交前工作树仅含本文件登记的 8 个路径。

```
.\.venv\Scripts\python.exe -m unittest tests.unit.test_pipeline_replace_alias_precheck tests.unit.test_assembly_pipeline_requests -v   # 23 项 OK
.\.venv\Scripts\python.exe -m unittest tests.unit.test_assembly_examples tests.unit.test_component_changes -v                          # 示例契约与摘要回归 OK
.\.venv\Scripts\python.exe tools\test_assembly_pipeline.py --help                                                                       # 正常
ruff check <改动文件>                                                                                                                    # 无新增诊断
```

改后 SHA256（Ruff format 后）：`tools/test_assembly_pipeline.py`
`193FB8B9236DF4EC67B1A7FB3A2E43D2D0BC3F63CAFEBA8715CFE171B134306C`；
`tests/unit/test_assembly_pipeline_requests.py`
`918D81F9AFD8FE83C3FCD5D4B913CBC9003162D66B935E93DE35C2B473AD32FD`；
`tests/unit/test_pipeline_replace_alias_precheck.py`
`9BA70CBDC12BCCBF15A3BB9CC87024F52CE17CA560DB19069E2153B30C7EA4DD`。

## 6. 未测范围（主代理负责）

pipeline 实机重跑（matrix 源码未变无需重跑）、独立全量 dev_check、WorkBuddy
纯 MCP 黑盒、合入/发布。本文件不声称新实机已通过——step 9e 的新 label 路径
仅完成离线预检与驱动修复，实机终态以主代理重跑报告为准。
