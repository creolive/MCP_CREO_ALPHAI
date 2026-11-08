# DEV-076 曲面报告追加：本轮离线验收

受测起点186883d73b4199e7515f79249f89338475bcf366，dirty=true（本次变更及原用户文档）。版本0.18.4继承基线，未合main/未发布；没有连接/启停Creo、Toolkit故障注入或清unknown。

- 生产group_state_decide原函数提取编译，C++结构仅提供测量输入，无Toolkit链接/调用。先红：返回1（边界可用但reason不可用）；修复后九个分支输入全部通过，测量值/四态阈值/预算未变。
- 工作区专项117项0失败0错误0跳过（21.301s），覆盖state原生执行、SDK元数据、group测量/投影、loft、trim、能力契约与分发清单。
- 新独立无Git分发同117项0失败0错误、1跳过（18.398s）；跳过本机编译配置项已在工作区执行通过。无.git、无config、PATH无Git、PIP_NO_INDEX=1，复用已安装依赖。1601件清单、491代码文件指纹b033be4209ad0def206353398edf7b44372e53d79d30255ab6d68d7a8541034a（sha256-path-lf-filehash-v1），结束和收尾前代码一致；未生成官方ZIP。
- 当前Creo12.4 SDK/MSVC组合构建exit0；Python3.12.14 / Windows x64。实际worker大小/SHA256及身份见[EVIDENCE](EVIDENCE.json)。编译不等于Creo建模通过。
- dev_check --skip-unit成功，21 lint/10未格式化均存量，未扩充基线。记录明确unit_tests=not_run，专项测试另行执行。不借用上一批2976项全量结果，本次未重跑全量。

命令：python -m unittest tests.unit.test_surface_group_state_native tests.unit.test_surface_group_measure tests.unit.test_surface_loft_schema tests.unit.test_surface_trim_kept_side_evidence tests.unit.test_surface_trim_schema tests.unit.test_t01_capability_contracts tests.unit.test_release_integrity -q；python bridge.py build；python tools/dev_check.py --skip-unit --work-item DEV-076。原始日志在build/surface-supplement*.log和build/surface-supplement/，不提交日志/配置/二进制。

取舍：不把开放弧解释当定因，因此仍缺真实交线诊断；不猜枚举/按release放行，因此Creo10放样与动态enabled仍未完成；保留null和采样上限，因此大面overlap仍可能不可用。enabled仍为注册语义，sdk_conditional元数据不能代替实际SDK准入。报告的半圆/mtime描述尚未同载荷/源码身份核对，不据此改revolve校验或历史发布结论。

全部问题逐项见[MAPPING](MAPPING.md)，未完成和验收动作进入[接手H13—H19](../../development/DEV-075-HANDOFF.md)。原件manifest与工作区/Git字节核对；既有validation原件保持不变。用户DEV-054/066和未跟踪本地内容不纳入提交。

独立最终审查（fresh-context gpt-6-astra）：未发现Critical/Important/Minor项；审查只读，不替代本轮测试/编译，也未判断loaded worker SDK、交线机理、Creo10直创和半圆同载荷行为。最终验收JSON/文档由主代理按实际结果核对。

## 2026-11-08 接手追加：H13/H15/H16

起点合并本地 v0.19.0（`006e357`），源码 0.19.0，dirty=true。Creo 12.4.0.0 / release_numeric=44，先做一次有界只读 `session_status(5)` 确认会话可操作（connected=true、toolkit_code=0、disconnect_code=0），随后仅用既有公开工具驱动；未做故障注入、未清 unknown、未结束 Creo。

- H13：`creo_worker.exe build-info` 返回 `source_digest=e69deb…`、`worker_sha256=1a9b70…`、`surface_loft{available:true,state:compiled}`；`session_status` 与 `creo_capabilities` 投影该身份。缺头分支由 `tests/unit/test_optional_loft_header.py` 实际编译 C++ 夹具并断言 `sdk_header_missing` 与 `SURFACE_LOFT_SDK_UNAVAILABLE`；提交前拒绝由 `tests/unit/test_dev076_h13_worker_identity.py` 覆盖。Creo10 缺头实机未验证。
- H15：`tools/test_surface_chain.py --case group --live` 通过，四态组均返回 `sample_budget=20000`、`faces 2/2`、`tests 220/220`、`coverage=1.0`、`budget_exceeded=false`；`overlap_area_mm2` 在不可用时仍为 null。大面真实 `budget_exceeded` 未取得现场样本。
- H16：`tools/test_surface_chain.py --case trim --live` 通过（7 作业）；四个 trim 的 `result_quilt_handle.available=true`、`visit_code=-4`，连续第二次 trim 以 `result_quilt_id=82` 为目标成功，`area_after_mm2=600`、`saved_file_reloaded_and_verified=true`、revision 1→2。
- 回归：全量 Windows 单测 3065 项 0 失败/0 错误/0 跳过（421.8 s）；`bridge.py build` exit 0。`dev_check --skip-unit` 余 5 项未格式化回归，均为并行 DEV-077 未提交文件，本批未改写。
- 未完成：H14 真实交线/拓扑分割诊断无 API 证据；H17 缺 Creo10 `NO_OPTS` 等载荷原件/原始 job JSON；H18 不改 revolve 校验；H19 旧原件/PRT/JPG/原始回执未提供，worker digest 已替代 mtime 作为身份证据。
