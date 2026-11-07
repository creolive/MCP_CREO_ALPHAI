# RELEASE-0.17.4 发布记录

## 1. 环境与身份

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-07 |
| 版本 | 0.17.4（PATCH，[DEV-072](../work-items/DEV-072.md) 0.17.1 反馈修复批） |
| 源码提交 | `7390f4b`（门禁时；功能提交 `ebb59de`，合入 0.17.3 的合并提交 `12049a6`） |
| 工作区 | dirty=false |
| 源码指纹 | `8fce4d008d4edded9a56d1a64ae3855f1371ef17359331054ae35449068826e7` |
| 系统 | Windows x64 |
| Creo | 12.4.0.0（仅用于匹配 SDK 编译，未建立 Toolkit 连接） |
| 公开工具数 | 100（无新增/删除） |

## 2. 代码与文档变更

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| 板厚回执来源 | `native_planar_wall.py`、`server.py` | 保留原生 API 字段；新增 `thickness_api_scope`/`thickness_api_reason`/`thickness_fallback_source`（resize 为 loaded 对应字段）；旧执行器缺 validation 时不生成说明 |
| 几何选边候选 | `native/advanced.cpp`、`native/geometry_diagnostics.h` | 失配时附最多五条最近直线边（ID、毫米端点、最佳无向配对误差、稳定排序）；严格匹配与容差不变 |
| 空装配预览 | `native/preview.h` | part/assembly 均须特征查询成功且确无可见非基准特征才 `skipped_no_geometry`；查询失败走原路径 |
| 成员检查适配 | `tests/unit/test_t07_preview.py` | 随预览契约更新断言 |
| 附件核对备用路线 | `src/creo_mechdog/release_download.py`、`tools/check_release_assets.py` | gh 30 秒；失败/缺失/资产集合无效转官方 API；严格四件、安全文件名、sidecar SHA256 |
| 台账与规范 | `docs/BACKLOG.md`、`docs/development/RELEASING.md`、DEV-070/FEAT-007/FEAT-039/FEAT-058 工作卡 | 状态回填、逐 ID 字面值核对与发布后外置记录规则 |
| 归档 | `docs/validation/feedback-0.17.1-2026-11-07/` | 三件原件逐字节归档 3/3 + 来源、SHA256、权限、禁止改写标记 |
| 回归 | `tests/unit/test_native_planar_wall.py`、`tests/unit/test_release_assets.py`、`tests/unit/test_release_download.py`、`tests/unit/test_model_naming.py`、`tests/test_development_validation.py`、`tests/native/test_dev072_geometry.cpp` | Python 与 SDK 无关 C++ 覆盖 |

## 3. 验收证据

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 专项单测 | `python -m unittest tests.unit.test_native_planar_wall tests.unit.test_release_assets tests.unit.test_release_download tests.unit.test_model_naming tests.unit.test_t07_preview tests.test_development_validation` | 153 项通过 |
| SDK 无关 C++ | `cl /std:c++17 /W4` + `build\dev072\geometry.exe` | 通过（反向端点、误差、五条上限、稳定排序、NaN 排末、空 part/assembly、未知/有几何反向用例） |
| 组合编译 | `python bridge.py build` | 通过（0.17.3 + 0.17.4 组合源码，产物 `build/creo_worker.exe`） |
| 全量门禁 | `python tools/dev_check.py` | `success=true`：2762 项 0 失败/0 错误，dirty=false，24 lint/12 未格式化（存量基线） |
| 独立审查 | 独立审查代理（非实现方） | 通过：无功能阻塞缺陷；记录一致性问题已修正，并补 `preview.h` 源码身份、候选 NaN 排序、`HTTPException`/`--dir` 错误处理、3 条下载回归与 C++ 反向/NaN 用例 |

## 4. 未验证范围

- Creo 实机：本版未连接 Creo；选边候选、空装配预览、板厚新字段无实机/保存重载证据。组合编译只证明可编译，不等于原生行为通过。
- WorkBuddy 公开 MCP 黑盒按用户决定由其它机器执行。
- Creo 9（本机无 SDK）、Creo 10 实机。
- 真实远端附件下载由发布后 `check_release_assets.py --tag v0.17.4` 核对，mock 路线不等于真实网络。

## 5. 交付清单

- 标签 `v0.17.4`
- 附件：`MCP_CREO_MechDog-0.17.4-source.zip` + `.sha256`、`MCP_CREO_MechDog-0.17.4-seed-library.zip` + `.sha256`
- `tools/check_release_assets.py --tag v0.17.4` 核对结果：待填
