# FEAT-012 / BUG-045 Task 4 离线实施证据

日期：2026-10-24。条目：[FEAT-012](../work-items/FEAT-012.md)、
[BUG-045](../work-items/BUG-045.md)、[DEV-046](../work-items/DEV-046.md)。

环境：Windows 11 x64 (10.0.26100)、Python 3.12.14、独立工作树
`E:\Projects\md050` 的 `.venv` 与 editable 安装；本地 Creo 12.4.0.0 SDK、
MSVC x64。原开发服务环境未更改。受测源码为 BASE
`a70a0d43adf92e83fb2f849de6b4e7c4faeff8fd` 加本次 dirty 改动，
dev_check 的 LF 正规化代码指纹 checked_source_sha256：
`cd70cbd7f8658275d67cb4392314618c51c41c666746897691d44f01cfd8c50b`。
该值覆盖受检 Python/C++，不是 Git tree 或发布附件哈希。

## 实现

公开创建/更新与 execute_plan 支持唯一嵌套 3×3 `rotation_matrix`，与显式 Euler
互斥，默认/None 兼容；矩阵请求不序列化默认 Euler。Python 在类型转换前拒绝
bool/string；有限值、行内积正交性和 det +1 绝对容差 `1e-6`。容差内按原值
使用，不转置或修正；平移独立按 mm，旧 Euler 顺序和角度符号保持。

生产 `native/assembly_pose.h` 由创建/更新共同使用：创建在加载/复制源件前，
更新在移除约束前校验。头文件进入 server 源码身份；bridge 既有递归 `.h`
构建指纹及源码打包遍历覆盖它，测试验证该头文件的源码变化检测。新原生 harness
测试源单独加入显式分发清单，避免已分发的 Python 驱动缺少测试源。
单 Toolkit 通道、busy 拒绝、revision 和回滚仍沿原路径。

## 实际验证

在工作树根 PowerShell 执行，解释器为本工作树 `.venv\Scripts\python.exe`。

| 命令/检查 | 实际结果及本地日志 |
| --- | --- |
| 独立 `-m venv .venv`，`-m pip install -r requirements-dev.txt` | 成功，editable 路径为本工作树 `src/creo_mechdog`，未重定向原服务环境 |
| 原有 `test_general_validation`、`test_session_assembly` | 初始 14 项通过 |
| 只读执行 `git show a70a0d4:src/creo_mechdog/schema.py` 中的验证器 | 两个装配 op 均拒绝 matrix 额外字段，默认 Euler 为零；`build/task4_baseline_reproduction.log`。没有复现物理放置方向缺陷 |
| `-m unittest tests.unit.test_assembly_pose tests.unit.test_general_validation tests.unit.test_session_assembly tests.unit.test_helper_layout tests.unit.test_build_fingerprints -v` | 33 项通过；`build/task4_focused.log` |
| `tools/test_assembly_pose.py` | C++17 编译/运行成功，11 组姿态及非法/容差输入通过；`build/assembly_pose_test/report.json`、`build/assembly_pose_test/build.log` |
| `tools/generate_constants.py`、`bridge.py build` | 从本地 SDK 生成 6521 个常量，离线执行器/回调构建成功；`build/task4_native_build.log`、`build/build.log` |
| Ruff 检查/格式检查、clang-format `--dry-run --Werror`、集成脚本 py_compile | 变更代码全部通过 |
| `tools/dev_check.py --work-item FEAT-012` | 最终通过，567 项单测、0 failures/errors；`build/development_check.json`、`build/unit_test_report.json`、`build/task4_dev_check.log` |
| `git diff --check`、历史文件核对 | 通过；docs/validation、版本、基线、发布附件未修改 |
| `-m unittest tests.unit.test_helper_layout -v`（最终打包清单调整后） | 5 项通过，包括新头文件、原生测试源、Python 测试和两个驱动的分发完整性；`build/task4_package_regression.log` |

初次 dev_check 在样式阶段发现驱动脚本未使用的 Path 导入，未启动单测。删除后
重跑最终检查通过；初次失败保留在 `build/task4_dev_check_initial.log/json`。
未修改 style-baseline。最终 31 项存量诊断和 19 个存量未格式化文件均属既有
基线，没有新增诊断或未格式化的变更文件。

自查分发清单时发现 tests 下只遍历 `.py`，新 C++ harness 源文件最初未包含。
已单独加入显式 allowlist，未扩大其他文件范围；此前绿色完整检查留在
`build/task4_dev_check_before_package.log/json`，最终再次完整检查上述打包修正。

SDK 编译保留未改动的 assembly_units.h、assembly_walk.h、generic.cpp 的既有
C4819 代码页警告；本次 helper 没有新警告。生成常量与二进制均只在忽略目录。

生产 helper SHA256：
`73ce38218dd29afd88e2f57e686a2b361086912554421b89b781bccd9f6ba5de`。
schema SHA256：
`18ceeccd2170243faa3106ad763d724d4dc42cb995d384ece9d4803acc84aa5e`。

## 覆盖及未验证范围

原生 harness 直接调用生产 helper，覆盖单位阵、XYZ ±90°、组合及正负 Euler
奇异姿态（含非整角组合），三个基向量、已知点和逆映射、默认值、容差内原值
保留、形状/类型、NaN/Inf、溢出量、非正交、缩放、反射，以及正交性通过而
det 超差的输入；拒绝时输出矩阵不变。

Python 6 项新回归覆盖两个 op、共享根导出、旧 Euler、矩阵无默认 Euler 序列化、
错误输入在提交锁前拒绝。通过 `server.mcp.call_tool` 的真实注册工具参数校验
覆盖 bool/string 拒绝，创建/更新与 execute_plan 及公开嵌套矩阵 schema。
submit/readiness 被替换，这不是运行中 stdio 服务或 WorkBuddy 黑盒验收。

新增 `tools/test_assembly_matrix.py` 实机场景但未运行：11 组姿态交替通过公开
工具和 execute_plan 创建/更新、Euler 对照、实际 list_components 映射、revision
递增、保存重载 true，以及非法请求保持 revision/约束/位置。执行前必须按
AGENTS.md 独立核实健康会话与授权，再显式加 `--session-health-verified`。

本次未连接 Toolkit、执行进程/恢复操作或故障注入。实际 Creo 几何放置/查询、
revision、回滚、保存重载、WorkBuddy、Creo 9/10 均未验证，不由离线通过外推。
BUG-045 实机范围继续开放，FEAT-012 显式源件更新及嵌套子装配未实施。
没有合并、推送、标签、版本变更或发布。
