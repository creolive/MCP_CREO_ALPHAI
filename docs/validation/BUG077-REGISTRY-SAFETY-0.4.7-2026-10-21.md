# BUG-077 / FEAT-047：0.4.7 审查补修记录

日期：2026-10-21（Asia/Shanghai）。分支 `codex/bug077-registry-split`，实施起点 `2a28d2e`；本轮验证时工作区 dirty，不能只用提交号代表源码。版本 0.4.7 为用户明确指定的 PATCH 例外，含本批两个公开工具，尚未合入 main 或发布。

## 已复现的问题

- 持有真实 OS 通道锁时，旧迁移 apply 仍改写隔离条目，没有返回 busy。
- `targets=["../foreign"]` 和绝对路径在旧 inspect 被接受，未使用合法 model_id 的目录归属规则。
- 旧 health 在 50 条损坏记录、limit=50 时序列化响应 56,208 B；旧迁移 inspect 在 485 条隔离记录时为 83,624 B，均超出 32,768 B。
- 修改前定向运行三个回归，记录到 6 处失败（路径子场景分别计入），与审查现象一致。

## 本次改动

- apply 的重新读取、owner/作业身份预检、备份、详情/控制发布、迁移日志与幂等结果登记都持有 `bridge.toolkit_lock`。实际锁竞争立即 busy；所有选定条目先预检，待运行作业、活动或无法证明停止的 owner 不改写。可证明停止的保护记录只迁移存储形态，不清 pending/unknown。
- 复用 `general.model_path` 的 32-hex ID 与链接检查，另核对直属目录、登记身份、作业/请求模型绑定及详情目录。备份原字节先 flush/fsync，再原子发布；幂等结果使用持久化原子 JSON 写入。
- health、迁移 inspect、apply/回放共用实际 JSON 序列化预算分页；完整计数不变，缩短问题预览或页面行数。过大单条保留身份和省略说明；游标绑定报告内容与调用范围，变化后明确要求重新查询。
- 版本入口、双份种子清单、种子包预期摘要、README、开发入口、工作卡和版本说明同步为 0.4.7。纠正“同一文件直接阻断 reconcile”“已证实无界累积”“三阶段全部完成”的当前表述；原报告及旧证据原字节不变。

## 本次验证

- 定向注册表、协调及 MCP 协议回归：68 项通过，包括 17 MiB/revision 16 迁移、原字节备份、详情解析、控制发布中断续作、真实锁竞争、链接/越界、活动/未知 owner 拒绝、已停保护保留、485 条分页及幂等回放无重无漏。
- `.venv/Scripts/python.exe tools/dev_check.py --work-item BUG-077`：success=true；530 项全量单测通过（本轮新增 14 项），无新增语言问题，未重建风格基线。存量 21 个未格式化文件不在本次通过结论中。
- `.venv/Scripts/python.exe bridge.py build`：成功返回既有 worker 路径；本轮无 C++ 源码改动，不把构建成功当作建模验收。
- 序列化响应测量：485 条迁移 inspect 共 10 页、最大 9,177 B；485 条中包含 50 条损坏记录的 health 共 10 页、最大 32,763 B，完整遍历均为 485 个唯一 ID；均 ≤32,768 B。
- `.venv/Scripts/python.exe -m pip install --no-deps -e .`：安装元数据已同步为 0.4.7。双份种子清单版本一致；候选种子包（24 文件／9 种子）SHA256 为 `5f91b8d2c0b2c65e274d13405fc4edfd8d483e212e205b45306f00c535659b74`，预期摘要已同步，仅本机候选文件，非发布附件。
- 受测源码：开始提交 `2a28d2ebaef51a789f4d74a32c9b3ebb9a0dc1cf`、dirty=true；开发检查源码指纹 `cfbea270a03a9eb34a6890fbaca987b8ce4fa2c053b7abd2fc91046022739f81`。逐文件 SHA256 见 `build/bug077-safety/response_evidence.json`，原始日志在同目录。两份反馈归档与 Downloads 原件 SHA256 逐字节一致；历史验证文件未改写。

## 环境与未测范围

本机 Windows x64 / Python 3.12 / Creo 12.4 匹配 SDK/MSVC。所有迁移回归均在临时目录运行，没有对本机真实 485 条历史登记执行批量迁移。

本轮只读核对发现 Creo 进程仍在；已有 `build/toolkit_health.json` 记录 `probe_timeout`，不能据进程存在判断会话可操作。根级规范仍要求先核对会话；未取得当前可操作确认前，不新发 Toolkit 连接、故障注入，不结束 Creo 或清保护。

原生编辑、装配、图纸及恢复链路、真实外部 Creo 10/21.4MB 原件和 WorkBuddy 黑盒仍未由本轮证据验证。离线夹具不替代原生几何、参数、revision 和保存重载验收。DEV-027 可复现性及安全回收另期保持开放。
