# 0.17.1 Feedback Offline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复三件反馈中不需要 Creo 会话即可实施的回执、诊断和开发工具问题。

**Architecture:** 保留原生测量来源、精确选边及失败保护，仅增加有依据的说明与候选。发布下载备用路线放包内，CLI 继续兼容。

**Tech Stack:** Python 3.12+ / unittest / urllib；C++17，SDK 无关逻辑测试。

**Spec:** [DEV-072](../../work-items/DEV-072.md)

## Global Constraints

- 不连接 Creo/Toolkit，不构建或替换共享执行器，不修改 runtime 配置、注册与 unknown 保护。
- 保留已有用户工作区修改；不合 main、不推送、不发 Release、不升级 version.py。
- 毫米/度；保留 API 错误和未知值；docs/validation 历史原件逐字节不变。
- 新原生行为未编译、未实机，如实登记。

## Review Focus

- 板厚 API 真实失败时不能伪报几何 fallback；畸形 receipt 不得成为 verified。
- 选边端点可反向；相同误差稳定排序；歧义保持拒绝；候选数量有界。
- 空装配与查询失败区分；有曲面/实体的模型不能跳过预览。
- gh 缺失、下载部分完成、API 失败、缺附件或摘要错误不能报成功。
- 已发布子项与仍开放范围分别写明，不能把整张 FEAT 卡误关。

### Task 1: 板厚来源说明

**Files:** `src/creo_mechdog/native_planar_wall.py`, `server.py`, `tests/unit/test_native_planar_wall.py`。
**Interfaces:** result_projection 保留 thickness_measured_mm/thickness_verified，增加 API scope、失败原因与 fallback 说明，现有 thickness_validation 继续判定。

- [x] 复现报告里的 geometry_normal_span verified + API false/null，增加成功/失败/畸形/旧回执回归。
- [x] 实现兼容说明并更新公开工具文档。
- [x] 运行相关单测与 Ruff。

### Task 2: 几何选边失配诊断与空装配预览

**Files:** `native/advanced.cpp`, `native/preview.h`，必要的纯 C++ helper 和 `tests/native/`、`tests/unit/` 回归。
**Interfaces:** 不改变 edge_geometry 唯一匹配与容差；失配消息最多列五条候选 ID/端点/mm 误差。空装配无几何用现有 skipped_no_geometry。

- [x] 核对原生分支，先为可独立测试的边匹配/预览判定编写失败用例。
- [x] 最小修改并验证反向端点、稳定有界候选、歧义与查询失败。
- [x] 运行 SDK 无关测试；不执行 bridge build 或 live 驱动。

### Task 3: 发布附件 API 下载备用路线

**Files:** `src/creo_mechdog/release_download.py`, `tools/check_release_assets.py`, `tests/unit/test_release_assets.py`。
**Interfaces:** download(tag, directory) 继续兼容，gh 缺失/失败用官方 API 的精确 tag；只下载四个预期安全文件名，仍由 validate_directory 验证。

- [x] mock gh/API，覆盖缺失、失败、partial download、缺件、错摘要及错误下载地址。
- [x] 实现标准库有超时下载，错误保留两路原因。
- [x] 跑专项单测与 Ruff。

### Task 4: 归档、台账与整体验证

**Files:** `docs/BACKLOG.md`, `docs/work-items/DEV-072.md`, `docs/development/RELEASING.md`，新反馈归档目录及映射；受影响能力文档。

- [x] 三件原稿逐字节归档，manifest 校验，映射已交付/本批代码/需实机边界。
- [x] 修正三行台账与相关卡首页，补逐 ID 人工检查与发布后外置核验记录规则，保留历史验证原件。
- [x] 全量中复现真实 busy 影响旧 UDF/非法名称测试，仅在 `tests/test_development_validation.py` / `tests/unit/test_model_naming.py` 隔离通道并断言不启动进程；`tests/unit/test_t07_preview.py` 更新共享 helper 接线断言，67 项专项通过。
- [x] 专项测试、统一 dev_check、独立审查；记录提交、dirty、源码指纹与未编译/未实机范围。

最终统一检查：2744 项全部通过（受测 dirty 快照 SHA256 `bfdac50c351f548fd27cd55c7db89e5024f8a07b72c85e25fd42ad8382d696a9`）。并行协作保存 `ebb59de` 后合入 0.17.3 的组合不在该结论内，详见 DEV-072 最终证据。
