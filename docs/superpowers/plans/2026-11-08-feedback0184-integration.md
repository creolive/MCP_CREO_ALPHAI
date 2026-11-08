# 0.18.4 三件反馈分支整合计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将用户指定补丁与报告问题解决到当前开发分支，保留分支已有修复和用户未提交内容。

**Architecture:** 本地v0.18.4合入；SDK头条件编译在native可选特征内部，Python导入遵循tools命名空间，历史发布材料以新勘误和统一索引关联。

**Tech Stack:** Python3.12+ / unittest / Ruff / C++17 / 本机Creo12.4 SDK/MSVC（仅编译）。

**Spec:** docs/work-items/DEV-076.md及三件归档原文。

## Global Constraints

- 不联网、不连接Creo/Toolkit、不故障注入、不清unknown、不修改main或发布对象。
- 保留用户原有dirty文档及未跟踪计划；历史validation原件不改。
- 保留DEV-066报告字段、source_commit消费键修复、目录指纹范围/完整性、unit_report新字段和会话日志取消跟踪。
- 原生缺头分支只返回明确不可用，不造几何；不添加仅凭编译得出的运行时通过结论。

## Review Focus

缺Probbl.h导致整个worker失败、宏覆盖误禁正常SDK、有/无包上下文的导入、Git merge丢失分支修复、把外部/发布前数据写为本轮远端实测。

## Tasks

- [ ] T1：备份/stash、三件归档、登记、合并本地v0.18.4并解决冲突，恢复用户内容。
- [ ] T2：缺头实际编译反例、最小条件编译补丁、源码契约和当前SDK编译。
- [ ] T3：三个裸名导入的独立进程反例与修复，CLI模式保持。
- [ ] T4：卡首页、台账计数、POSTCHECK指定路径、发布勘误与未测清单。
- [ ] T5：最终组合专项/全量、样式、无Git分发、独立审查、身份与交接记录，提交本地分支。
