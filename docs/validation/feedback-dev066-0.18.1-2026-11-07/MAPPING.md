# DEV-066 / 0.18.1 新报告与当前源码对照

报告日期2026-11-07，续做日期2026-11-08；原件与SHA256见[manifest](manifest.json)。报告针对已发布`main@9d72569` / 0.18.1，不代表当前本地未发布分支；本批不联网核对该提交/标签。实现沿用DEV-066，补步归DEV-075。

| 原文 | 当前核对与处理 | 证据 / 余项 |
| --- | --- | --- |
| §一更新、种子、Creo9 SDK、102工具、2830单测通过 | 仅报告方外部正证据，原件保留。没有本次Creo9 SDK/Creo实机/远端重验，2830是报告方时点，不改历史发布记录。 | 真实运行/发布核对继续交接 |
| §二1“仅登记，未实现” | 当前HEAD已有DEV-074公共helper与25入口。暂停前另17处迁移曾存在于未提交目录/冻结副本；续做时源码已不含它们，本批对比后恢复并审阅，修了3个消费端键错误，不因工作卡文字断言实现存在。 | 本批代码8def1e4；旧0.18.1不倒填已修 |
| §二2“38→43个脚本、5新增” | 旧统计是字面包含Git的文件数，不能等同全部硬依赖。当前AST审计tools没有直接Git进程调用；43个tools文件直接消费共同helper（含新增test_unit），guarded_live_run/test_editing_closeout间接复用dev_check.git_state。包内helper是唯一实现；保留各脚本旧报告字段。 | `build/dev066_20261108/git-audit.json` |
| §二3 arc/update_check无Git崩溃 | helper先which，缺Git/无仓库/父仓库不匹配时Git身份null；目录源码哈希有scope，读不到指定源文件时incomplete/null指纹与缺失路径，不崩溃/伪造完整哈希。arc默认离线CLI实跑通过；update_check只验证来源构建，网络更新流程未运行。 | 新单元回归、arc CLI；联网更新留H08 |
| §二4负例裸ERROR | seed_record_gate测试捕获并断言原ERROR及非零退出；新runner失败夹具也捕获stderr。生产CLI未降级真实错误。完整单测日志以汇总/机器报告为准。 | 最终全量及裸ERROR扫描见验收记录 |
| §二4/三/四Git前置和耗时 | README/INSTALL/DEVELOPMENT写明Git可选，服务不需要；缺Git仍有目录指纹。给出9–18分钟历史实测参考、可调整1800秒预算、保留PowerShell和离线wheel的步骤；不是耗时承诺。 | 文档当前说明，不改历史数字 |
| §三1 session_activity跟踪 | git rm --cached并ignore，实际文件路径不改，取消跟踪操作前后逐字节一致，历史提交不重写。源码白名单原已不含本机日志。旧版升级需先备份；真实升级保留行为未演练。 | session-preserved.json；H09 |
| §三2 AGENTS工具98 | 去掉易过期固定数，公开工具数以capabilities为准。未新增/移除公开工具。 | AGENTS.md |
| §三3机器报告少字段 | 保留原六字段，新增skipped、skipped_tests、duration_seconds和source（Git身份、指纹范围、完整性等）；失败仍exit1；耗时按单测执行的monotonic时间计，不含前置收集/发现。 | unit_report.py / test_unit.py |
| §三4工作区形态/耗时 | 本次证据记录源码提交、dirty、冻结分发目录/导入路径、配置缺失导致跳过、耗时、指纹及命令，不修改历史validation中的发布结论。 | DEV-066-ACCEPTANCE-2026-11-08 |
| §四3 Git环境诊断 | development_tools.git_available仅可选提示；git_required_for_mcp=false，不计入ready_to_build。单测SDK文件齐全但无Git仍ready。公开客户端观察留WorkBuddy。 | bridge.check_environment；H05/H08 |
| §五未验证 | 不连接Creo/Toolkit、不故障注入；真实更新联网路径/旧版升级/WorkBuddy/Creo9建模不由离线单测替代。不可改历史g0_driver仍有Git调用。 | DEV-075-HANDOFF新增H08—H09 |

完整验收见[本批验收记录](../../development/DEV-066-ACCEPTANCE-2026-11-08.md)，未完范围追加到用户指定的[接手清单](../../development/DEV-075-HANDOFF.md)。
