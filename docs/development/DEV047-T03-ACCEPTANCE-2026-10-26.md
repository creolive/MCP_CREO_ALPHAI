# DEV-047 / T03 公共平面引用与坐标帧离线验收

日期：2026-10-26（Asia/Shanghai）。条目：[BUG-084](../work-items/BUG-084.md)、[BUG-064](../work-items/BUG-064.md) 的引用和 U 轴子项。任务分支：`codex/dev047-t03-plane-frame`，基于已纳入 T00/T01 的 `1f3ab19e222abb81cae3b4969fa9f79efb404a11`。受测服务源码版本仍为 0.6.1，目标 0.7.0 的集成与 Release 由 T13 完成。

## 改动与接口

- `plane.id` 从当前模型的平面几何中精确选择，`datum_plane.id` 仅从巡检 `datum_planes` 的基准平面几何 ID 选择。`surface.id` 保持面几何引用，`datum_feature` 保持特征标签；不把特征 ID 猜成几何 ID。
- Python 准入与原生边界均拒绝 `plane`/`datum_plane` 的显式 ID 与 `axis`、`normal`、`offset` 同现，包含默认值；ID 须为非负 32 位整数。无 ID 保留原 axis/normal/offset 筛选。不存在的 ID 与非平面几何在原生解析中准确失败，不回退默认 Z。
- 草图从原生选中的支撑面读取 `surface_id`、支撑面原点和法向，再按面内 U 向构造正交 V 向。成功操作在 full 与 compact 结果中保留 `surface_id`、`origin`、`normal`、`u_axis`、`v_axis`。字典草图平面须有 `reference` 容器；U 轴零向量与实际法向平行分别报错，±Z 可作为 Right 面的有效面内方向。
- 更新逐工具引用示例及公开 MCP 输入描述。T04 的任意平面 coordinates 和 T05 的拉伸、轴、阵列算法没有在此任务更改；T02 后续去重及结果状态实现须保留本任务增加的帧字段。

## 离线验证

环境：Windows x64；Python 3.12.14；Ruff 0.17.0；clang-format 23.1.3；本机匹配的 Creo 12.4 Toolkit SDK 与 MSVC x64 仅用于原生编译。测试不连接 Toolkit、不启动新 Creo 会话、不做故障注入、不清理当前会话或 unknown 保护。WorkBuddy 未执行。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.unit.test_reference_contract tests.unit.test_t03_plane_reference -q` | 18 项通过；专项涵盖 ID/筛选互斥、非法类型准入、两个公共工具、纯 Z 正反向透传及 compact 帧字段 |
| `python -m unittest discover -s tests -q` | 最终完整重跑 779 项通过，耗时 252.529 秒；首次开发检查在代码仍改动期间出现一项失败，最终静态源码下未复现 |
| 变更 Python 的 `ruff check` 与 `ruff format --check` | 5 个文件通过，无新增格式清理或风格基线豁免 |
| `python bridge.py build` | 匹配 SDK 原生执行器构建通过；`build/creo_worker.exe` SHA256 `C4E2AEADACC1E888E59376FA5974D9BB682CB9F55CE7EF8F69F6FA166803EEB7`，该生成物不入库 |
| `python tools/dev_check.py --work-item BUG-084` | `success=true`、`unit_tests=passed`、`native_validation=not_run`；检查仅含语言与单元，不代表原生建模验收 |

最终 dev_check 指纹（`build/development_check.json`）：基线提交 `1f3ab19e222abb81cae3b4969fa9f79efb404a11`（dirty，含本次 T03 改动），受测源码 `checked_source_sha256=9f14a9abe76a559cbf6d50280f64ca7dadb1655f5cc5b74b961163e4e5d053d0`，生成时间 2026-10-26T10:15:35Z。本次重跑的专项、Ruff、dev_check 与上表命令一致；`python bridge.py build` 复用既有执行器，复核 `creo_worker.exe` 哈希仍为上表 SHA256。

### T13 实机验收矩阵（本次未执行）

1. 在实际模型建立 Right 面和法向 `(0.587785,0.809017,0)` 的倾斜面，并加入默认 XY 与同偏移干扰平面。分别以 `datum_plane.id`、`plane.id`、`surface.id` 和 `datum_feature` 标签选择同一真实支撑面，核对解析的 `surface_id`、`origin`、`normal`、`u_axis`、`v_axis` 与实际几何；不能只比请求回显。
2. Right 面以 `u_axis=[0,0,1]` 和 `[0,0,-1]` 创建真实草图，核对 U/V 手性、图元位置；零向量、实际法向平行、错误类型 ID、存在但非平面的 ID、未找到 ID 分别准确拒绝。对已受理的原生失败检查 revision、回滚、模型可继续操作。
3. 对合法 Right/倾斜草图保存重载并验证原生几何，记录 `saved_file_reloaded_and_verified`、实际面 ID、源码提交/dirty/指纹。T05 单独验证倾斜去料方向、两平面交线轴和偏心阵列，不能借本卡离线结果代替。

本次验收结论：**T03 离线实现完成，实机未验收**。外部 0.5.2 报告的现象因果仍是待实机核对的推断。既有运行账本和历史 `docs/validation/` 原件保持原状；未触碰 pre-existing 未跟踪运行文件。
