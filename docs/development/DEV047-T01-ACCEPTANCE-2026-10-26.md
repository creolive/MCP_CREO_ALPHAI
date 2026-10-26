# DEV-047 / T01 能力与契约离线验收

日期：2026-10-26（Asia/Shanghai）。条目：FEAT-008、DEV-047。任务分支：`codex/dev047-t01-contracts`，依赖 T00 `90421c66bddab30191ac84490f0084e679f4483b`。受测源码版本仍为 `version.py` 的 0.6.1，0.7.0 由 T13 集成发布。

## 改动与边界

- `src/creo_mechdog/capability_summary.py` 根据 `capabilities.families()` 生成支持摘要，`server.py` 仅适配现有接口；补 model adoption prepare、文件路径批量收养 inspect/apply、会话擦除、登记健康及迁移。禁用家族显示 `not_available`，已启用工具与动作由登记项取得。文件收养描述如实区分 0.6.0 开发者实机验收与未执行的 WorkBuddy。
- 本地 `release_status` 由 `VERSION` 语义版本后缀判定 stable / pre-release / unknown；`complete_creo_coverage` 独立，`update` 仍反映远端版本和缓存状态。
- 标签原正则、JSON Schema 模式及合法名称保持；只替换模式错误说明，包含字段路径、28 字符上限、字符集和小写示例。非法输入在提交和 Toolkit 锁之前拒绝。
- README 说明毫米归一化与 raw 矩阵、混合单位的完整坐标变换、未知单位与 `unchanged` 的原生核验适用范围；开发、编码、发布清单加入单位证据与非毫米验收要求。本次不改原生代码或 T02 的操作结果状态。

## 验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3。仅离线 Python 和文档核对；Creo、SDK、MSVC、Toolkit 连接、原生构建及实机建模均未执行。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| T01 专项先红后绿 | 初始 9 项暴露缺失摘要、固定成熟度文案及标签提示；实现后 9/9 通过；最终补 JSON Schema 与非字符串类型边界后 10/10 通过 |
| `python tools/dev_check.py` | success；769 个单元测试通过，`native_validation=not_run`；检查源码为 T00 `90421c6` + dirty，检查时指纹 `384da6c91d57c946315b5ddea182687d3e5bb341efaecc528caf77eb0ada1dec` |
| 最终 `python tools/dev_check.py --work-item FEAT-008 --skip-unit` | success；最终 Python/native 检查源码 SHA256 `1f6d7684560b25bea2533431c2f8735be8ee6c07cad7f2bbc5bdb4a340cd0bfe`，`unit_tests=not_run` 仅指该次风格复核，不覆盖前次 769 项结果 |
| 专项 Ruff check/format | 6 个变更 Python 文件全部通过；全库现存 30 项 lint、17 个未格式化文件均按既有基线核对，无新增豁免 |
| 原件和工作区隔离 | 三份 T00 原件重新计算 SHA256 均与 manifest 一致；历史 validation 已跟踪文件保持，预存 `session_activity.json` 与未跟踪运行文件未改、未暂存 |

上述 `checked_source_sha256` 是 `tools/dev_check.py` 按其源码范围计算的当前离线检查指纹，非 Creo 运行载入身份。检查前原工作区已有运行数据 dirty，本轮只将明确列出的源码、测试及文档提交到任务分支；不能单靠依赖提交代表受测源码。

## 交回

T01 的离线契约已实现；功能范围、单位矩阵真实数值及非毫米建模仍需 T13 在满足既有会话核对条件后按改动范围实机验收。T02—T12 仍按派发表处理，T13 负责一次 0.7.0 主干合入、发布和附件核验。T01 未连接 Toolkit、未关闭或清理当前会话及 unknown 保护、未修改历史 validation 原件。
