# 0.17.4 反馈离线修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对比四份 0.17.4 反馈与当前代码，修复可离线验证的缺陷，交付具体剩余工作清单。

**Architecture:** 保持 server/bridge/native 既有边界，使用包内实现及有界诊断；分派互不重叠的文件组并在最后统一回归与独立审查。原生几何能力保持证据门禁。

**Tech Stack:** Python 3.12+ / unittest / Ruff / C++17 / Windows Toolkit SDK（仅编译）。

**Spec:** `docs/work-items/DEV-074.md` 与归档的四份反馈。

## Global Constraints

- 不连接 Creo、不故障注入、不清 unknown 保护、不修改本机配置，不合入 main、不发布、不更改版本。
- 保留开始时 `DEV-054.md`、`.trae/` 与已有 FEAT-014 计划的用户修改。
- 历史 `docs/validation/` 原件保持字节不变；未知数据为 null。
- Toolkit 单通道忙碌立即拒绝，不自动重试、不排队。

## Review Focus

无 Git 与无仓库、头尾截断/半行/阶段跨越、无特征 ID 的失败、非零原点跨轴 resize、几何未知与实际已测证据混淆。

## Tasks

- [x] T1：四份原件归档、SHA256 清单、逐章比对与已有条目映射；先登记再实施。
- [x] T2：DEV-066 来源采集与发布记录缺口：复现 Git 缺失/无仓库，补降级与测试；修正文档口径并保留远端未查事实。
- [x] T3：BUG-109 头部连接计时与尾部当前阶段归因，补长日志/阶段误归因回归；修正曲面能力描述及明确门禁。
- [x] T4：FEAT-058 非零 origin resize 的离线计算核对、失败回执与厚度权威字段；候选结构化与空预览证据按可验证范围完善。
- [x] T5：空预览悬空路径、过期 startup 快照与在途更新说明的离线修复及回归。
- [x] T6：全量单测、开发检查、适用原生编译、独立差异审查；更新台账、映射与接手清单，提交仅本次文件。

## 接口与分工

T2 修改来源工具/下载模块/相应测试和发布勘误；T3 修改 native_stage/曲面 capability 文案；T4 修改 planar_wall/result_projection/edge diagnostics/native preview；T5 修改 Python preview/startup/update。共享文档仅主代理汇总，避免覆盖；根模块 server.py 文案由 T3 所有。

预检：T4 的原生 preview 新证据由 T5 Python 白名单消费，双方保持字段同名；T4 的 planar_wall 块已在 compact 白名单，无需扩大通用响应预算。

## 执行补充

T2真实分发测试发现弧方向/轮廓重放/斜面切除还有相同Git硬依赖，范围按DEV-066最终覆盖25个来源入口（24个同契约、1个精简契约），共用包内source_provenance模块。T4非零origin根因无法离线证实，只增加逐尺寸日志、保留体积守卫，H01开放；结构化最近边已完成失败投影。T5保留startup旧字段历史语义，以新增当前验证字段和明确过期提示解决误读，不改变内部准入。

独立审查代理因额度不足未完成；最终采用主代理逐文件自审，发现并补测有效板厚布尔未比较请求厚度的缺口（RED→GREEN），以及格式化敏感的既有源码断言。该自审弱于独立审查，合入前可另行审查。本轮不合入main、不发布。

最终验证：Git全量2850项、最终无Git分发全量2850项（2项SDK检查跳过）均0失败/0错误；最终样式门禁、原生编译通过。最终源码指纹7602302e1f59e22108bc9be4aba2f8dd5c7beca7995e0e2be83f3892ede9c8a8。
