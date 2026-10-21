# CREO 10.0.0.0 · MCP 0.4.4：DEV-027/DEV-030 正式落地实测通过，两项多轮遗留正式闭环

> 反馈人：终端用户（非项目作者）
> 记录日期：2026-10-21
> 实测版本：**0.4.4**（2026-10-21 10:52 发布，PATCH，"两份 Creo 10 构建侧反馈的完善计划实施"），从 0.4.3 升级
> 环境：Windows 10 x64 / **Creo Parametric 10.0.0.0** / VS2022 BuildTools 14.44.35207 / Windows SDK 10.0.26100.0 / Python 3.13
> ⚠️ **验证范围声明**：沿用 2026-10-17 用户约束（停止新的 Toolkit 连接/故障注入），本轮**未发起任何 Creo 连接、未做建模回测**。
> 结论来自源码校验、编译、文件层面对比与两项针对性实测。
> 仓库：https://github.com/wudahua/MCP_CREO_MechDog
>
> **0.4.4 的两项主修复（DEV-027/DEV-030）正是本人 10-18 至 10-21 多轮报告的问题。** 本文档是这两项的闭环确认。

---

## 0. 摘要

| 项 | 0.4.4 状态 |
| --- | --- |
| 升级本身（校验/覆盖/安装/编译） | ✅ 全部成功，87 工具 / 9 种子 |
| **DEV-027 指纹归一化（json.hpp 换行致注册失效）** | ✅ **正式落地，实测通过**（本机恰好是理想试金石，见 §1） |
| **DEV-030 vcvars64_env 多余键接受** | ✅ **正式落地，实测通过**（用上轮被拒的原样输入复测，见 §2） |
| **本轮回调注册是否失效** | ✅ **连续第四版未失效**（protk.dat 未变，见 §1.3） |
| payload/loader 目录清理 | 🟡 仍无机制（本轮未新增：7 / 2），但 DEV-027 落地后世代切换频率大降，影响随之减小 |
| 附件 SHA256 | 🟡 Release body 本版未直接给出，需从 main 的 RELEASE-0.4.4.md 取（0.4.1/0.4.2 的好做法没延续，见 §4） |

---

## 1. ✅ DEV-027 落地实测：换行翻转不再触发重建与注册失效

### 1.1 为什么本机是理想试金石

0.4.4 相对 0.4.3 的原生改动**恰好只有一项**：`native/third_party/json.hpp` 的换行翻转（LF→CRLF，归一化后逐字节相同），
其余 25 个原生文件全部 SAME。这正是 0.4.0 事故的**完全同款场景**：

- 0.4.0 时（旧算法）：这种差异导致 loader/payload 指纹换代 → `protk.dat` 重新生成 → **注册失效一次**；
- 0.4.4 时（新算法 `sha256-repo-lf-v1`，按 CRLF→LF 归一化内容计算）：预期零重建、注册不动。

### 1.2 实测结果

升级（覆盖 684 文件 + `pip install -e .` + `bridge.py build`）后与 0.4.3 基线对比：

| 观测项 | 0.4.3 基线 | 0.4.4 | 解读 |
| --- | --- | --- | --- |
| `blend_callback_protk.dat` sha 前 16 | `fc62f1548f4a1895` | `fc62f1548f4a1895` | **注册路径未变 ✅** |
| `loader_fingerprint`（缓存记录） | `d26fa82164596688…`（旧算法） | `cf5ab07ebedf46bb…`（新算法 `sha256-repo-lf-v1`） | 指纹**标识**切换为新算法，**预期行为** |
| `generation_key` | —（旧格式无此字段） | `d26fa82164596688` | **旧世代键被保留**：迁移逻辑正确识别等价性 ✅ |
| `creo_blend_loader.dll` sha 前 16 | `350d68a5982f984b` | `350d68a5982f984b` | **未重编 ✅**（换行翻转未触发重建） |
| `creo_blend_sync.dll` sha 前 16 | `07c5e5c5d7538a94` | `07c5e5c5d7538a94` | **未重编 ✅** |
| `build/blend_loader/` 目录数 | 2 | 2 | 未新增世代 ✅ |
| `build/blend_callback/` 目录数 | 7 | 7 | 未新增 payload ✅ |
| `creo_worker.exe` | 9,047,552 B | 9,047,552 B（sha 变为新指纹 `320c216d…`） | worker 指纹按新算法重记，字节未变 |

**判定：DEV-027 在"旧格式缓存迁移 + json.hpp 换行翻转"双重场景下工作正常。**
指纹标识切换到新算法属预期（`algorithm: sha256-repo-lf-v1` 已写入缓存戳），
关键的行为指标 —— DLL 字节、`protk.dat`、目录数 —— 全部稳定。

### 1.3 对用户的意义

从此以后，**任何发版只要不动 `blend_loader.cpp` / `blend_sync.cpp` / `callback_*.h` 的实际内容，
无论 vendored 库或换行怎么变，用户的 Creo 注册都保持有效。**
0.4.0 那类"纯格式发布打断注册"的事故从机制上被消除。

---

## 2. ✅ DEV-030 落地实测：多余键从"拒绝"变为"接受并忽略"

### 2.1 新实现（读码确认）

`src/creo_mechdog/build_support.py` 的 `validate_compiler_env` 重写为：

- **必须包含大写 `INCLUDE` / `LIB` / `PATH`**；缺失时错误信息**列出缺失项 + 最小配置示例**；
- **其余键接受并忽略**（不执行、不透传、不影响构建指纹）；忽略提示走 stderr、只列键名不回显值；
- 安装回写时规范化为三键并保留其他配置属性。

### 2.2 实测：用上轮被拒的原样输入复测

我把 0.4.3 报告里被 `ValueError` 拒绝的同款配置（三键 + `WindowsSdkDir` / `WindowsSDKVersion` /
`UniversalCRTSdkDir` / `VCToolsInstallDir` 共 7 键）写入 config.json 后执行构建：

```
RC = 0
BUILD_OK
vcvars64_env: ignoring extra keys not used by the build: UniversalCRTSdkDir, VCToolsInstallDir,
              WindowsSDKVersion, WindowsSdkDir
```

**构建成功，且给出了明确、克制（不回显值）的忽略提示。** 测试后 config.json 已还原为三键形态。
**判定：DEV-030 实测通过。** 六轮报告至此闭环。

---

## 3. 升级与静态验证

| 项 | 结果 |
| --- | --- |
| 源码包 sha256 | `eed874c0cbe70314f1a2fc92bfe1e0cd34a5caf8a218d3953cb4f569ac1ff259` ✅（与 main 上 RELEASE-0.4.4.md 一致） |
| 种子包 sha256 | `00b1bae07f4b751bce8138450ee2776bf18f09f66d4bf75bcef3fca5e83a0724` ✅ 同上 |
| 覆盖 | 684 文件；复核新增/真实差异/换行差异均为 0 |
| editable 安装 | `Successfully installed MCP_CREO_MechDog-0.4.4` |
| 编译 | `vcvars64_env` 三键一次成功；`creo_worker.exe` 9,047,552 B（字节与 0.4.3 相同，原生 SAME） |
| `@mcp.tool` 装饰器 | **87**（无新增工具，与发布说明一致） |
| 种子清单 | 9 |
| 新模块 | ✅ `src/creo_mechdog/build_fingerprints.py` + `tests/unit/test_build_fingerprints.py`（8 用例） |

### 未验证（按实机冻结约束）

`json.hpp` 变化后"在已加载回调的 Creo 会话里直接放样"这条端到端链路（需 GUI 注册 + 实机连接）；
DEV-027 剩余范围（同源码二进制可复现性、payload 目录累积盘点与安全回收）；FEAT-044 钣金打开等补验收场景。

---

## 4. 🟡 小观察

1. **附件 SHA256 的呈现方式又不一致**：0.4.1/0.4.2 直接写在 Release body（我建议过并获采纳），0.4.3 也在 body，
   **0.4.4 的 body 没写**，需要去 main 分支的 `docs/validation/RELEASE-0.4.4.md` 取。建议固定为"Release body 必含两包 SHA256"。
2. **payload/loader 目录清理**仍未实施（7 / 2）。DEV-027 落地后世代切换将大幅减少，此项优先级已很低，
   但 `payload 目录随内容变化仍会 +1` 的行为仍在，建议与 DEV-027 剩余范围（官方未测清单里已列"payload 目录累积盘点与安全回收"）一并处理。
3. 发布说明质量持续向好：0.4.4 的说明把修复动机、迁移语义（旧缓存等价复用）、未测范围都写清楚了，且直接引用了改进计划的文档 —— 这对下游使用者非常友好。

---

## 5. 需要作者回复的问题

1. **§4.1**：Release body 附两包 SHA256 能否固化为发布检查单的一项？（0.4.4 又漏了）
2. **§4.2**：payload 目录"累积盘点与安全回收"是否已有排期（DEV-027 剩余范围）？
3. 本机（Win10 + reg.exe 拦截 + 三键 vcvars64_env + 旧格式缓存迁移 + json.hpp 翻转）的实测结果可直接作为
   发布说明里"未测：外部 Creo 10 / Win10 受限环境（reg.exe 拦截）复验"这条的**部分补验**；
   如需完整证据包（各阶段指纹、protk.dat、缓存戳、build 日志），我可整理提供。
