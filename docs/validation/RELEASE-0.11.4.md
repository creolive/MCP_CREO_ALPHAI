# 0.11.4 发布记录

- 版本：**0.11.4**（PATCH，公开工具仍 95）。日期：2026-11-02。批次：0.11.1 第十二轮反馈（R12），[DEV-064](../work-items/DEV-064.md)。
- 分支：`codex/DEV-064-r12-feedback0111`；基线 `main@2ba1e2d`（0.11.3 交付 `7b80a4a` → 回填 `2ba1e2d`）。
- 版本说明：[0.11.4 版本说明](../RELEASE_NOTES_0.11.4.md)；反馈归档：[feedback-0.11.1-2026-11-02](feedback-0.11.1-2026-11-02/MAPPING.md)。

## 交付内容

| 固定 ID | 内容 | 状态 |
| --- | --- | --- |
| [DEV-064](../work-items/DEV-064.md) | 两份原件逐字节归档 2/2、逐章映射、工作区定性、登记与交付编排 | 已完成 |
| [BUG-107](../work-items/BUG-107.md) | `HEADERS` 存在性门控，Creo 10 缺 `Probbl.h` 不再中断构建 | 已修复（离线；Creo 10 未验证） |
| [BUG-108](../work-items/BUG-108.md) | 顶层 `sketch_shifted`、`geometry_deviation.shift_detected`/`accepted_by_request`、原点固定试点 | 部分：可观测已交付，平移未复现、定因未定 |
| [BUG-106](../work-items/BUG-106.md) | save origin / erase `modified` 两处可执行链路文案 | 已修复（文案；链路未复测） |
| [FEAT-054](../work-items/FEAT-054.md)、[FEAT-055](../work-items/FEAT-055.md) | 补建工作卡（沿用既有 ID），保持待规划 | 已登记 |

## 验证矩阵

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 全量单元 | `.venv\Scripts\python.exe -m unittest discover -s tests` | **2 185 项 0 失败**（0.11.3 起点 2 158，新增 27） |
| 单测报告 | `.venv\Scripts\python.exe tools\test_unit.py` | `build/unit_test_report.json`：`tests_run=2185`、`failures=0`、`errors=0`、`success=true`，`version=0.11.4` |
| 开发检查 | `.venv\Scripts\python.exe tools\dev_check.py --work-item 0.11.1-feedback-r12` | `success=true`；单元 `passed`；`style_summary` 无新增回归（既有 30 findings/16 unformatted 均在基线内） |
| 原生构建 | `.venv\Scripts\python.exe bridge.py build` | exit 0；执行器 **13 276 672 B** / `8ab6978e6cc8cacc2c614f9af71684cfed5f2a034383108b38481467824cc16a` |
| 常量生成 | 同上 | `build/generate_constants.log` 无 `MISSING_SDK_HEADER`（本机 SDK 31 头全在），常量 6 563，include 段未变 |
| 种子包 | `.venv\Scripts\python.exe tools\package_seeds.py --output ...` ×3 | 三次同哈希 `666f9c806572717e93f8f6aeda64c471290806997bd0b73093884c14820a3233`（24 files / 9 seeds），`docs/seed_package.json` 校验通过 |
| 实机（Creo 12.4.0.0） | `.venv\Scripts\python.exe tools\test_sketch_shift_batch.py --confirmed-session-usable --output build/sketch_shift_batch_0.11.4.json` | 5 个作业全部 `succeeded`；`saved_file_reloaded_and_verified=true`；4 个细长钝角三角条草图（260×20.9，坐标标注）`sketch_shifted.detected=false`（max 1.43e-31 / 1.88e-33 / 1.26e-47 / 1.42e-14），`SKETCH_ORIGIN_PIN axis=0/1` 生效（`value=0`） |

### 实机 job

| 作业 | job_id |
| --- | --- |
| `creo_new_part` | `e8c72a3df07346ef88ca160ba78ccc57` |
| `s01x`（默认容差） | `f5aec4960df54be984362cb564523048` |
| `s01y`（默认容差） | `d775bf5a975f4289a7c7c3fa8a77a480` |
| `s01z`（默认容差） | `8c1776885bf84b379685809763a25499` |
| `s01t`（请求容差 0.01） | `23a4d61175df4dd4bc748a094ca552c1` |
| `bug108_shift_solid`（挤出 5 mm） | `c47dfcdde16c48b09e0986c06b0f3b3c` |

报告：`build/sketch_shift_batch_0.11.4.json`（含 commit/branch/dirty/`source.sha256`=`d89a2006…`/执行器字节数与 SHA256）。模型 `5e6f9d683d0943bda69c292abb07fa64`。

## 环境

- Windows（本机 x64，2026-11-02）、Creo Parametric **12.4.0.0** 与匹配 Toolkit SDK、MSVC x64（`vcvars64_env` 三键）、Python 3.12+（`.venv`）、Ruff 0.17.0、clang-format 23.1.3。
- 实机会话为人工确认可操作后连接，仅创建本批管理的新零件，未动用户模型；未重启或结束 Creo、未清 unknown、未重提已受理作业。

## 未验证范围

- Creo 10 / Creo 9 实机（本机无 SDK 与许可）：`HEADERS` 缺头跳过路径只用离线夹具与契约测试证明；报告方"跳过 `Probbl.h` 后构建成功"未在本机复现。
- 报告方 0.004 mm 整截面平移未复现（本机 12.4 最大 1.42e-14），原点钉住是否消除该现象**未定因**；`accepted_by_request=true` 的真实样本未取得。
- 报告方 24 条带 194 ops 计划 JSON 未提供；24 条带原件与 P12 正规链路未验证（FEAT-054）。
- G5 三算子未实现（FEAT-055）；同名外部模型 save/erase 两步链路未构造复测；WorkBuddy 黑盒未执行。

## 发布动作（待回填）

| 项 | 值 |
| --- | --- |
| 合入提交 | （待回填） |
| 主干 | （待回填） |
| 标签 | `v0.11.4`（待创建） |
| Release | （待回填 id 与链接） |
| 源码包 | （待回填文件名、字节数、文件数、SHA256） |
| 种子包 | `MCP_CREO_MechDog-0.11.4-seed-library.zip`，内容摘要 `666f9c80…`（发布后核对远端 digest） |
| sidecar | （待回填） |

## 回滚

公开工具与参数签名未变；回退到 0.11.3 时需同时回退种子包到 `MCP_CREO_MechDog-0.11.3-seed-library.zip`（`compatible_server_version=0.11.3`），否则种子版本闸门会拒绝。0.11.3 已发布的标签与附件不得覆盖。
