# DEV-066 新反馈离线补步计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对照新增0.18.1报告与已实现内容，补完当前可离线缺口，余项追加DEV-075-HANDOFF。

**Architecture:** 复用包内source_provenance，保持未知Git身份为null；证据脚本只做编排，报告归一化放包内。会话日志取消跟踪而不移动实际文件，不改Toolkit/建模路径。

**Tech Stack:** Python3.12+ / unittest / Ruff / PowerShell（仅离线测试）。

**Spec:** `docs/work-items/DEV-066.md` 新报告补步与归档原文。

## Global Constraints

- 不联网、不连接Creo/Toolkit、不故障注入、不清unknown、不改本机配置、不合main、不发布、不改版本。
- 现有未提交的来源迁移、原生resize与其它用户修改保留；本轮只提交新增补步，已有未提交成果单列。
- 原报告逐字节归档，历史validation不改；保留runtime日志真实字节。
- Git是可选来源工具，不能因缺Git改变MCP环境ready；目录哈希不能冒充commit。

## Review Focus

无Git/无仓库、父仓库误识别、缺失来源文件、预期负例与真实失败区分、取消跟踪后的实际日志仍可读写。

## Tasks

- [x] T1：原件归档、登记DEV-066增量，核对当前实现与未提交迁移。
- [x] T2：审计剩余Git调用及helper，精准复现代表入口；只补真实缺口。
- [x] T3：tools/test_unit.py与包内report helper增加skipped/原因、duration_seconds、source身份，保留旧字段，补专项回归。
- [x] T4：负例输出捕获、保留真实CLI非零/原错误；session_activity.json取消跟踪并ignore且保留字节；可选Git诊断与文档同步。
- [x] T5：冻结无Git/无.git分发全量、针对性与样式门禁、独立审查；更新对照与DEV-075接手清单，只提交本批。

T2审计者只读现有dirty来源迁移，T3只改报告模块/runner及新测试；T4由主代理处理共享文档和session文件索引。所有来源字段消费source_provenance，不能另造Git实现。用户已明确要求直接离线执行，按现有架构推进，不另设审批。

## 2026-11-08执行记录

暂停后17个未提交迁移已不在当前目录；逐项审阅上轮冻结副本并恢复所需补丁，不恢复无关原生改型。审查R1三个source_commit消费键与R2七个证据投影先RED后GREEN。51项定向通过，样式success=true；代码提交8def1e4。最终冻结分发全量2884项0失败/0错误、2项SDK跳过（本机另补通过），耗时358.797秒；样式门禁通过。

选择：Git是可选来源，保留带scope目录哈希；日志只取消跟踪、实际路径不动，旧版本升级仍需备份；历史g0_driver不可改。详细执行台账build/dev066_20261108/progress.md。
