# 0.19.1 发布记录

日期：2026-11-08。性质：PATCH。版本入口 `version.py` = `0.19.1`。本记录由 DEV-076 / DEV-077 交付批生成；发布后核对在统一 [RELEASE-POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md) 的 v0.19.1 段回填。

## 1. 范围

- DEV-076 H13：worker `build-info` 构建身份、动态 `surface_loft` 可用性、提交前拒绝。
- DEV-076 H15：overlap 预算/覆盖/部分诊断，面积不可用仍为 null。
- DEV-076 H16：`surface_trim.result_quilt_id` / `result_quilt_handle` 与连续 trim。
- DEV-077 R01 部分：`rotation_tolerance` 可配，默认严格语义不变。
- DEV-077 R02 部分：装配质量属性替代工具提示、`creo_get_job.wait_seconds` 0–300、`known_limitations`、`plan_examples`。
- DEV-077 既有离线补漏：质量属性诊断、`stall_report` 回退、台账计数门禁、0.18.2 归档与文档回填。

## 2. 离线门禁

- 全量 Windows 单测：3071 项，0 失败 / 0 错误 / 0 跳过。
- `tools/dev_check.py --skip-unit --work-item DEV-077`：success=true；无新增 lint 或未格式化项。
- `tools/check_backlog_counts.py`：exit 0，台账 168（BUG 75 / FEAT 61 / DEV 32）。
- `bridge.py build`：exit 0，Creo 12.4.0.0 SDK / MSVC x64。

## 3. 实机证据（Creo 12.4.0.0，release_numeric=44）

- `bridge.session_status(5)`：connected=true、toolkit_code=0、disconnect_code=0；`worker_build_identity.identity_status=verified`，`surface_loft.available=true`。
- `tools/test_surface_chain.py --case trim --live --confirm-session-usable`：7 作业，passed=true；四个 trim `result_quilt_handle.available=true`、`visit_code=-4`；连续第二次 trim `area_after_mm2=600`、保存重载 true、revision 1→2。
- `tools/test_surface_chain.py --case group --live --confirm-session-usable`：passed=true；四态组均返回 `sample_budget=20000`、`faces 2/2`、`tests 220/220`、`coverage=1.0`、`budget_exceeded=false`。

未做故障注入、未清 unknown、未结束 Creo。Creo 9/10、WorkBuddy 黑盒、源码包解压全量单测未执行。

## 4. 打包

- 源包：`MCP_CREO_MechDog-0.19.1-source.zip` + `.sha256`
- 种子包：`MCP_CREO_MechDog-0.19.1-seed-library.zip` + `.sha256`
- 生成命令：`tools/package_seeds.py`、`tools/package.py`；四附件上传后由 `tools/check_release_assets.py --tag v0.19.1` 核对。

## 5. 附件 SHA256

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.1-source.zip` | 待打包 | 待打包 |
| `MCP_CREO_MechDog-0.19.1-source.zip.sha256` | 待打包 | 待打包 |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip` | 待打包 | 待打包 |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip.sha256` | 待打包 | 待打包 |

## 6. 未测范围

- Creo 9 / Creo 10 真实 SDK 构建、缺头公开 MCP 拒绝与运行时几何。
- WorkBuddy 公开 MCP 黑盒；源码包解压后的全量单测。
- R01 草图容差链与任意平面工具、R02 mirror 子树与无 callback loft、R03 session_health 策略、R04 曲面剩余项。
- 大面 overlap 真实预算耗尽样本、surface_trim 开放弧交线诊断。

## 10. 合入 main 的提交、版本标签及指向

待发布后回填：合入提交 `____`；标签 `v0.19.1` 指向 `____`；Release 链接 `____`。

## 11. GitHub Release 链接与发布状态

待发布后回填（草稿/已发布、Pre-release 标记）。

## 12. 远端附件与 SHA256 核对结果

待发布后执行 `python tools/check_release_assets.py --tag v0.19.1` 并回填：四个附件齐全、两个 sidecar 与对应 ZIP 摘要一致、Release body 含第 5 节 SHA256。
