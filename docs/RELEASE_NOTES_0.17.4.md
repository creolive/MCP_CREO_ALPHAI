# MCP_CREO_MechDog 0.17.4 版本说明

2026-11-07，PATCH：**反馈修复批**。本轮交付 [DEV-072](work-items/DEV-072.md) 的 0.17.1 三件反馈离线修复，并完成 DEV-070/FEAT-007/FEAT-039/FEAT-058 台账与发布规范回填。公开工具仍为 **100**，无新增/删除工具；变更集中在既有回执字段、失配诊断、预览判定与发布核对工具。原生源码有变更，但本版**未连接 Creo 实机**，只完成离线门禁与匹配 SDK 的组合编译。

## 本版内容

| 条目 | 本版结果 | 证据 |
| --- | --- | --- |
| [DEV-072](work-items/DEV-072.md) 板厚回执来源 | 保留原生 API 原始字段，新增 `thickness_api_scope` / `thickness_api_reason` / `thickness_fallback_source`（resize 为 loaded 对应字段）；权威判据仍是有来源的 `thickness_validation`，几何兜底不冒充 API 读数；旧执行器缺 validation 时不生成新说明 | `src/creo_mechdog/native_planar_wall.py`、`server.py` |
| [DEV-072](work-items/DEV-072.md) 几何选边候选 | `sheetmetal_flange.edge` 失配时附最多五条最近直线边（ID、实际毫米端点、最佳无向一对一配对误差，按最大端点误差后 ID 稳定排序）；严格唯一匹配与原容差不变，不自动吸附被折边改变的拓扑 | `native/advanced.cpp`、`native/geometry_diagnostics.h` |
| [DEV-072](work-items/DEV-072.md) 空装配预览 | part/assembly 都须特征查询成功且确认无可显示非基准特征才返回 `skipped_no_geometry`；查询失败走原截图路径，有曲面/草图/组件不因零体积判空 | `native/preview.h` |
| [DEV-072](work-items/DEV-072.md) 附件下载备用路线 | [tools/check_release_assets.py](../tools/check_release_assets.py) 先用 gh（30 秒），失败/缺失/资产集合无效时转官方 GitHub API 精确 tag 下载；严格恰四件、安全文件名与地址、sidecar SHA256；网络与复制错误非零并给 `--dir` 指引 | `src/creo_mechdog/release_download.py`、`tests/unit/test_release_download.py` |
| [DEV-072](work-items/DEV-072.md) 台账与发布规范 | DEV-070、FEAT-007、FEAT-039、FEAT-058 状态回填；发布规范增加逐 ID 字面值核对与外置发布后记录规则；三件反馈原件逐字节归档 3/3 | [映射](validation/feedback-0.17.1-2026-11-07/MAPPING.md)、`docs/BACKLOG.md` |

## 兼容性与接口

- 无新增/删除工具，无参数重命名；新增字段均为附加回执，旧客户端忽略即可。
- 旧版原生执行器不返回 `thickness_validation` 时，新 Python 侧不补写来源说明，行为与旧版一致。
- 原生执行器源码有变更（选边候选、预览判定），升级需按 `bridge.py build` 重新编译。
- `tools/check_release_assets.py` 在 gh 不可用时不再直接失败，新增官方 API 下载路线；四附件集合与安全文件名约束不变。

## 门禁

- 合并 0.17.3 后的组合源码全量单测 **2759 项，0 失败、0 错误**；`tools/dev_check.py` `success=true`（提交 `38b9c9f`、dirty=false、源码指纹 `b06caf3a…`），24 条 lint / 12 个未格式化文件均为存量基线。
- `python bridge.py build` 在本机 Windows x64 / Creo 12.4.0.0 匹配 Toolkit SDK 下编译通过（产物 `build/creo_worker.exe`）。
- SDK 无关 C++ 测试（反向端点、误差、五条上限与稳定排序、空 part/assembly 与未知/有几何场景）通过。
- 种子包确定性构建两次同摘要，已回填 `docs/seed_package.json`。

## 未验证范围

- WorkBuddy 公开 MCP 黑盒（按用户决定由其它机器单独测试，本轮不执行）。
- Creo 实机：本版未连接 Creo，选边候选、空装配预览与板厚新字段均无实机/保存重载证据；`bridge.py build` 只证明可编译，不等于原生行为通过。
- Creo 9（本机无 SDK）与 Creo 10 实机。
- 真实远端附件下载：gh 与官方 API 两条路线只用 mock 网络验证，发布后由 `check_release_assets.py --tag v0.17.4` 另行核对。
- 钣金附着增料、同段共享角部、格栅/百叶成形、miter/end_trim 实际去料与旧版本远端附件复核仍留待独立环境。

## 升级

1. 拉取本版本源码并执行 `python -m pip install --no-deps -e .`。
2. 执行 `python bridge.py build` 重新编译执行器（原生源码有变更）。
3. 重启 MCP 服务；客户端可忽略新增回执字段。
