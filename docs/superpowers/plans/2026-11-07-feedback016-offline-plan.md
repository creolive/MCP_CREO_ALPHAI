# DEV-071 0.16.0 反馈离线修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task.

**Goal:** 在已交付 0.17.1 上补齐 miter 公开回执、更新检查语义与草图求解上下文。
**Architecture:** 复用 native aliases、operation_results、compact_sections、job_projection 和 UpdateChecker；不模拟 Creo 几何。
**Tech Stack:** Windows / Python 3.12 / unittest / C++17 源码（本轮不构建）。
**Spec:** [设计](../specs/2026-11-07-feedback016-offline-design.md)。

## Global Constraints

- 用户要求不使用 Creo；不调用 MCP/Toolkit、不构建、不改部署配置或 E 盘实机 checkout。
- mm / degree；缺证据保持缺省/null；历史原件逐字节保留。
- 保留 1e-6 矩阵准入、coordinates 1e-5 拒绝、autodim 1e-3 告警及显式容差硬门。
- 只提交独立分支，不改版本、不合 main、不推送或发布。

## Review Focus

1. aliases 映射必须按 op/label 绑定，失败或未执行步骤不能得到历史成功证据。
2. 冷却、force、并发取消和可配置总网络预算之间不泄漏请求/凭据。
3. 草图初次 solve 失败后恢复成功，应保留全过程且不误报最终失败。
4. 历史作业缺新字段不补造原生测量/求解结果。
5. compact sections 与预算不得丢失败/回滚证据，full 分页保留实际回执。

### Task 1: miter 投影与 offset 契约

**Files:** operation_results.py、compact_sections.py、job_projection.py、受影响 job 查询入口；现有投影/分页单测及新增 test_feedback016_receipts.py；capabilities.py、references.py、REFERENCE_SYNTAX.md。
**Interfaces:** 生产/读取统一 annotate_native_result，原生字段名 miter_cuts/adjacent_bend_ends_allowed 不变。
- [ ] 新增 aliases-only 折边回执在 compact/full/sections 可见的失败测试；错误 label/缺字段/未执行不补造。
- [ ] 实现最小映射和字段白名单；统一 offset 的实体体积与源 quilt 文案，保留缺测量状态。
- [ ] 定向测试通过，提交 FEAT-014/023 修复。

### Task 2: 更新检查预算与缓存语义

**Files:** src/creo_mechdog/update_check.py、tests/unit/test_update_check.py、docs/UPDATE_CHECK.md；必要时 server.py 仅改工具说明。
**Interfaces:** UpdateChecker.check(force=False) 不变；环境变量 MECHDOG_UPDATE_TIMEOUT_SECONDS；snapshot 增 network_timeout_seconds/cache_age_seconds/retry_after_at。
- [ ] 新增 force 绕过失败/unknown 冷却、预算配置非法/1/30、失败缓存年龄及自动重试时间的失败测试。
- [ ] 实现有界配置与回执；单个总预算涵盖全部分页；不联网运行测试。
- [ ] 保留并发共用、取消隔离、旧缓存失败降级测试，更新文档并提交 FEAT-020。

### Task 3: 草图求解上下文

**Files:** native/sketch_coordinates.cpp、sketch_solver.cpp、generic.cpp、sketch_edit.cpp；operation_results.py、compact_sections.py、failure_context.py；草图/失败上下文单测。
**Interfaces:** solver 复用 requested/used，新增 selection_reason、阶段返回码；失败同块进入 failed_operation，未调用阶段为 null。
- [ ] 补模式选择/恢复成功/最终失败/缺失旧字段的离线契约与投影测试。
- [ ] 在既有求解调用处捕获真实码并发布；选择原因由原生原选择算法产生，不另写 Python 猜测器。
- [ ] 定向回归通过，明确原生未构建/未实机，提交 FEAT-010 诊断。

### Task 4: 验证与交接

**Files:** DEV-071 工作卡、BACKLOG、反馈 MAPPING/manifest、离线验证记录。
- [ ] 完整离线单元与语言检查，仅在独立工作树执行；记录源码身份、命令、结果及环境限制。
- [ ] 独立 reviewer 核查全分支；修复重要问题，提交文档并给用户分支/提交/未实机范围。
