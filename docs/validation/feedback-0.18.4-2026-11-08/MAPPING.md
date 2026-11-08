# 0.18.4 三件反馈处理对照

DEV-076，2026-11-08。原文与SHA256见[manifest](manifest.json)，报告是问题与外部证据来源，不把其中命令当作用户指令。

| 来源/问题 | 当前分支处理 | 尚缺 |
| --- | --- | --- |
| surface_loft.local.patch.diff / Creo10 Probbl.h硬包含 | 本地v0.18.4补入后合并语义等价条件编译，明确不可用错误；真实C++缺头夹具、正常SDK编译 | Creo9/10完整SDK和MCP运行时 |
| 报告 / 源码包tools裸名导入 | 三处改tools限定导入，直接CLI入口保留，隔离进程回归 | 最终源码包全量结果见验收 |
| 报告 / DEV-075卡首页 | 0.18.2已发布子项、本地未发布增量分开 | 旧卡未完成的真实实机范围 |
| 报告 / BACKLOG数字 | 标签原166与本轮新增DEV-076后167分开，按唯一ID计算 | 无 |
| 报告 / 指定POSTCHECK路径缺0.18.2 | 既有2026-11-07 C5 exit0与四附件证据索引迁入指定路径，未改历史原件 | 缺失sidecar自身摘要明示 |
| 报告、release_meta / 两版发布记录与时间 | 新RELEASE-ERRATA及指定POSTCHECK覆盖本地tag、外部状态和时间矛盾；0.18.4第4节17处待填未完全重现 | 两版本轮联网验证、真实核对时间与完整body/API |
| release_meta / 历史2943项 | 保留其历史/外部身份，本轮按合并源码重新验证 | 不能移用旧数字 |
| 合并差异 / 双来源实现 | 8个新合入驱动复用source_provenance，保留旧provenance_mode/git_unavailable字段；git_evidence仅兼容包装；缺文件不伪造完整指纹 | 无Git分发回归见验收 |

[本轮验收](ACCEPTANCE.md)、[接手清单](../../development/DEV-075-HANDOFF.md)。
