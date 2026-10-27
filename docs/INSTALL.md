# 源码安装与接入

当前服务／源码版本为 0.7.1（DEV-048 反馈修复），以 [version.py](../version.py) 为准；功能与边界见[版本说明](RELEASE_NOTES_0.7.1.md)，发布与安装证据见[发布验收记录](validation/RELEASE-0.7.1.md)。安装或升级后请按下文「升级与部署核对」确认所装版本、实际路径、启动身份和工具清单，不要只凭版本号判断。0.6.1 验收中出现的通道断连（[BUG-085](work-items/BUG-085.md)）根因未定，发布不意味着完整兼容或稳定性已验收。

## 需要的环境

可使用 Creo 9、10 或 Creo 12。当前开发与发布按本机 Creo 12.4.0.0 的改动范围验收，Creo 10 独立复测不作为项目门槛；Creo 9 与匹配 Toolkit 9 已纳入支持/要求范围，[BUG-033](work-items/BUG-033.md) 编译探测修复已实现。本机无 Creo 9 SDK，Creo 9 实机编译与建模运行时均未验收，支持声明不代表本机测试通过。其他环境收到具体测试反馈后再跟进；具体已测范围与未测项见 [兼容矩阵](COMPATIBILITY.md)。仅做 Python 单元和语言检查的开发环境见 [开发入口](DEVELOPMENT.md)，不必先运行完整 Creo 安装流程。

- Windows x64；Creo Parametric 9、10 或 12，使用与目标安装匹配的 SDK。Creo 12.4 已有自动启动、建模、参数编辑和保存重载的成功实机记录；0.2.6 发布时另一次冷启动复测失败，保留原结果见 [发布验收](validation/RELEASE-0.2.6.md)。Creo 9 编译探测已支持，实机编译及运行时未在本机验收。
- Python 3.12+ x64；本版安装实测使用 Python 3.12。
- 与 Creo 安装匹配的 C/C++ Toolkit SDK，包括头文件和 x64 链接库。
- Creo 公制模板 `Common Files/templates/mmns_part_solid_abs.prt` 和 `mmns_asm_design_abs.asm`。安装器与环境检查都要求这两份文件，即使首次只建零件，也需安装公制装配模板。
- Visual Studio C++ Build Tools，包含 MSVC x64 和 Windows SDK；本版实测 VS 2022。
- 可用于当前 Toolkit 开发与运行路径的 PTC 许可。
- 能运行本地 stdio MCP 服务的 AI 客户端。

本项目不提供 Creo、SDK、许可证或已解锁的二进制。项目 MIT 许可证及第三方条件见 [LICENSE](../LICENSE) 和 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

安装 VS 2022 Build Tools 时，在管理员 PowerShell 中使用已下载的官方安装器，包含推荐组件：

```powershell
.\vs_buildtools.exe --quiet --wait --norestart `
  --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
```

仅指定工作负载默认只安装 Required 组件；推荐组件包含 C++ 编译工具和 Windows SDK，具体随安装器版本变化。遗漏 `--includeRecommended` 时，可能出现安装器退出码为 0，但找不到 `cl.exe`、`vcvars64.bat` 或缺少 `stdio.h` / `kernel32.lib` 的“静默假成功”。检查实际组件并补装；退出码本身不能证明编译环境完整。参数及组件来源：[微软安装参数](https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio?view=vs-2022)、[Build Tools 组件清单](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools?view=vs-2022)。

## 安装步骤

下载源码 ZIP，解压后应能直接看到 `README.md`、`setup.ps1` 和 `server.py`。建议使用较短的可写路径，例如 `C:\MCP_CREO_MechDog`。

在该目录打开 PowerShell，执行：

```powershell
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
```

Creo 12.4 的安装示例：

```powershell
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 12.4.0.0'
```

Creo 9 的安装示例（使用匹配的 Toolkit 9 SDK；本机未验收该环境）：

```powershell
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 9.0.0.0'
```

`-CreoRoot` 指向包含 `Common Files` 和 `Parametric` 的安装目录，按实际位置替换。脚本优先使用明确提供的参数，其次使用已有本机 `config.json`；首次安装参考 `config.example.json`。编译器可由 Visual Studio 的 `vswhere` 检测。

可以明确指定所有程序路径：

```powershell
.\setup.ps1 `
  -Python 'C:\Path\To\python.exe' `
  -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0' `
  -VcVars64 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
```

`C:\Path\To\python.exe` 必须替换为已安装的 Python。仅检查前置文件与 Python 架构而不执行安装时，在命令末尾加 `-CheckOnly`；这项检查不会连接 Creo，也不验证许可。

若 `vcvars64.bat` 的 SDK 注册表探测受到限制，可提供完整的本机编译环境。先在可正常编译的 x64 开发者 PowerShell 中取得 INCLUDE、LIB、PATH，然后传入：

```powershell
$compilerEnv = @{ INCLUDE = $env:INCLUDE; LIB = $env:LIB; PATH = $env:PATH }
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 12.4.0.0' -VcVars64Env $compilerEnv
```

也可在本机 `config.json` 中添加 `"vcvars64_env": {"INCLUDE": "完整头文件目录列表", "LIB": "完整库目录列表", "PATH": "完整工具目录列表"}`，目录间用分号分隔，JSON 路径中的反斜杠写成 `\\`。当前0.3.3只接受恰好这三个键，必须大写、完整、非空；“完整环境”指这三个值中的完整路径列表，不是vcvars的全部变量转储。WindowsSdkDir、WindowsSDKVersion等额外键目前会被拒绝，并未实现忽略或透传。值不能包含引号、百分号、换行或 NUL；使用展开后的绝对路径，不写 `%PATH%`。默认 `null` 使用 vcvars64。显式环境分支不调用或要求 vcvars64 文件，仍运行 compiler_preflight 检查 cl/link、UCRT 与 Windows SDK，`-CheckOnly` 只核对配置和前置文件，不执行编译自检。

外部[Creo10/0.3.3反馈](validation/FEEDBACK-0.3.3-BUILD.md)记录了reg.exe受限时三键环境的官方编译成功正例。额外键兼容和日志展示仍是待核对的后续请求；该外部记录不等于受限机器完整安装或其他SDK均已验收。

`-VcVars64Env` 优先于同次提供的 `-VcVars64`；只显式提供 `-VcVars64` 时切回批处理分支并清除持久化环境，`-VcVars64Env $null` 也可恢复自动发现。未提供这两个参数时沿用本机配置。安装会回写选定环境并保留已有额外属性，`-CheckOnly` 不写配置。完整 PATH 必须包含 MSVC、Windows SDK 及必要系统工具；本机受限环境仍需管理员核实，不修改全局策略。

如果 Windows PowerShell 的脚本执行策略阻止运行，可在查看源码后，仅对这次安装进程指定策略：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
```

脚本保留已有本机配置中的额外选项，创建项目内的 Python 虚拟环境及客户端配置，再安装锁定依赖、更新本机 SDK 常量并编译执行器。同步混合回调 DLL 独立校验缓存，只有自身源码、ABI/SDK、构建参数或 DLL 内容改变才重建。BUG-007开发版在build/blend_callback中生成按DLL哈希分开的初始化副本和protk.dat；所有策略下，直接Blend前由使用者通过Creo辅助应用程序完成一次初始化，PROMPT下的安全确认也在该阶段完成，否则建模任务明确拒绝。一次性注册步骤（含固定入口 `<安装目录>\build\blend_callback_protk.dat` 与 config.pro 持久化）见 README「直接混合（Blend）的一次性回调设置」小节与[生命周期说明](CALLBACK_LIFECYCLE.md)；`creo_callback_status` 的 `not_loaded` 状态 instruction 首行即注册入口。注册文件路径由creo_capabilities.direct_blend_callback返回，构建副本存在不代表DLL已加载；MCP不修改Creo安全策略，NEVER策略由管理员处理。新建种子放样不需要该回调。每次构建先按当前 SDK 更新常量，并将 SDK 头文件内容计入缓存指纹；源码、配置及头文件都不变时复用现有二进制。不需要把 Creo 安装到示例路径；不修改 PTC 安装目录或全局 AI 客户端配置。

安装中断会输出 `INSTALL_INCOMPLETE`、失败阶段、已完成步骤和重跑方法。修复错误后在同一目录重跑相同安装命令即可，不必删除 `.venv`、模型或任务。`client-config.json` 提前生成便于接入与诊断；它存在不代表依赖、原生执行器或许可验证已完成。

## AI 客户端配置

安装成功后打开 `client-config.json`，将其中的 `MCP_CREO_MechDog` 服务添加到支持本地 stdio MCP 的客户端。示例格式：

```json
{
  "mcpServers": {
    "MCP_CREO_MechDog": {
      "command": "C:\\MCP_CREO_MechDog\\.venv\\Scripts\\python.exe",
      "args": ["C:\\MCP_CREO_MechDog\\server.py"]
    }
  }
}
```

以脚本生成的实际路径为准。客户端如果使用其他配置格式，保留相同的执行命令和参数。stdio 客户端会启动本地子进程，因此不需要手动长期运行 `server.py`；不要将 GitHub 仓库 URL 填成 MCP 服务地址。[官方 MCP Python SDK 本地主机说明](https://py.sdk.modelcontextprotocol.io/get-started/real-host/)

启动客户端中的 MCP 服务，后台自动复用已有会话或启动配置的 Creo。处理启动时出现的登录、许可及其他模态对话框，然后让 AI：

1. 调用 `creo_capabilities`，确认运行版本与所装 Release 标签一致、工具数与清单符合该版本（0.7.1 为 94 个工具）；核对 `runtime.python_executable`、`runtime.server_entry`、`runtime.code_root` 的实际路径与 `runtime.source_changed_since_startup`，再查看 `families`、`seed_library` 和 `unavailable_operations`。直接混合及已有零件追加已开放，受范围限制；见 [版本说明](RELEASE_NOTES_0.7.1.md)。
2. 调用 `creo_check_environment`，确认 SDK、模板和编译器路径正确。
3. 调用 `creo_startup_status` 等待 `state == "ready"`，再调用 `creo_session_status` 确认 `connected == true`。等待时建模请求明确拒绝，未创建任务。
4. 提交一个新零件建模计划；只提交一次，使用 `creo_get_job` 查询任务进度。
5. 确认任务 `status == "succeeded"`，修改结果包含 `saved_file_reloaded_and_verified == true`。

可以使用提示词：

> 用 MCP_CREO_MechDog 新建毫米零件：在 XY 面画一个直径 20 mm 的圆，拉伸 30 mm，保留原生草图和拉伸特征。先检查环境和 Creo 会话，再提交一次计划并查询到完成，最后报告原生 PRT 文件及保存重载验证结果。

连接成功证明当前连接路径可用；实际特征成功仍需建模验证。PTC 对 Toolkit 许可及编译应用解锁的要求独立于本项目 MIT 许可。[PTC Toolkit 解锁说明](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/user_guide/Unlocking_a_Creo_Toolkit_Application.html)

## 常见问题

### MCP 自动启动 Creo（FEAT-019）

同时存在安装版和开发版时，重启客户端中的目标 MCP 服务后调用 `creo_capabilities`，核对 `runtime.python_executable`、`runtime.server_entry` 和 `runtime.code_root` 的实际路径。`runtime.source_fingerprints_at_startup` 记录服务初始化时的源码指纹（统一换行后计算），`runtime.source_changed_since_startup=true` 表示磁盘源码已变化，应重启服务再验收。服务名称和同为 `0.2.6` 的版本号不能区分两份源码；客户端配置改动也不会替换已运行的服务进程。

`config.json` 可设置以下选项，重跑安装会保留已有值：

| 选项 | 缺省值 | 作用 |
| --- | --- | --- |
| `auto_start_creo` | `true` | 自动检测、复用；确认没有目标会话时启动 Creo。`false` 时由使用者手动打开 |
| `creo_startup_timeout_seconds` | `120` | 原生准备完成后的连接等待，整数 10～600 秒 |
| `creo_startup_psf` | `null` | 使用安装内 `Parametric/bin/parametric.psf`；可指定绝对 `.psf` 路径 |

后台初始化不会等待 Creo 启动完成才响应 MCP 握手。`creo_startup_status` 返回 `checking`、`building_worker`、`starting`、`waiting_for_connection` 或终态；只有实际 Toolkit 连接成功才返回 `ready`。原生准备另有 180 秒等待上限及构建子进程超时。等待或失败时建模入口拒绝入队，历史任务查询和能力查询仍可用。

服务通过现有 Explorer 的 `ShellExecute` 启动配置安装内的 `parametric.exe`，PSF 经 Windows 参数编码单独传入，支持含空格路径，不拼接 `cmd.exe` 命令。自动启动需要同一用户、同一 Windows 会话中可访问的 Explorer 桌面。Creo 作为独立桌面程序保留，关闭 MCP 客户端不会主动关闭它。GUI 继承 Explorer 的桌面环境，并使用自身 PSF；原生 worker 所需的 Windows 环境变量会从当前用户环境补齐，许可值不进入诊断。没有可用桌面时可手动启动 Creo，再请求重新检测。

同一用户会话、安装和 PSF 的多个服务共享 `%LOCALAPPDATA%/MCP_CREO_MechDog/startup/<目标摘要>/` 下的锁、`state.json` 和 `startup.log`。启动预留先于实际拉起写入；先前结果不确定且当前没有进程时，需要显式调用 `creo_startup_status(retry=true)`。重试会复查实际进程，正在启动或已有 Creo 时继续等待，不重复创建。日志不包含许可或敏感会话 ID。冷启动时先依据进程检查拉起 GUI，再进行真实 Toolkit 探测，避免首次探测创建的名称服务随 MCP 主机退出而被清理。Explorer 启动接口不提供子进程退出码；请求异常记录为失败，无就绪确认则有界超时，不将启动请求返回当作成功。

`timeout` 时先处理 Creo 对话框或检查启动环境，再请求重试。`selection_required` 时核对安装和 `creo_session_id`：多会话不随机选择，失效的指定 ID 不会被替换为其他实例。开关关闭后，手动打开 Creo，再调用 `creo_startup_status(retry=true)` 或 `creo_session_status` 重新检测。工具不会自动关闭会话或恢复失联任务；后者仍属 BUG-001 的独立范围。

| 现象 | 处理 |
| --- | --- |
| 找不到 Python 或提示 WindowsApps / Microsoft Store placeholder | 命中 WindowsApps 路径时，安装器在执行前拒绝商店占位程序；安装 Python 3.12+ x64，使用 `-Python` 指定真实 `python.exe` |
| 缺少 Toolkit 头文件或库 | 给对应 Creo 安装补装匹配的 Toolkit SDK |
| 找不到 `vcvars64.bat` | 安装 C++ Build Tools 及 Windows SDK，使用 `-VcVars64` 指定位置 |
| Build Tools 安装退出码 0，但没有编译器或 SDK | 安装命令补 `--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended`，核对实际组件，不以退出码代替编译自检 |
| 依赖下载失败 | 检查访问 PyPI 的网络，再运行安装脚本 |
| 原生编译失败 | 查看 `build/generate_constants.log` 和 `build/build.log`；编译前检查 `cl.exe`、`link.exe`、UCRT 的 `stdio.h`、Windows SDK 的 `windows.h` 及 x64 库 |
| `vcvars64` 成功但缺少 `stdio.h` / SDK 库 | 核对推荐组件、Windows SDK 与注册表 / `reg.exe` 探测；由管理员修复环境，或用 `vcvars64_env` / `-VcVars64Env` 提供完整环境，仍须通过编译前置自检 |
| 原生构建 `error C2065`，名称为 `PRO_*` | 检查失败消息中的 SDK 版本方向提示和末尾最多 15 条 error 摘要；提示只表示可能使用了较新 SDK 常量，不能直接断言所需版本。完整错误保留在 `build/build.log` |
| 文件检查通过但 Toolkit 连接失败 | 确认只打开一个 Creo 会话，处理模态对话框，再核查当前 PTC 许可；检查 `license_diagnostics`，路径拼写错误可能导致许可文件不存在 |
| 客户端发现工具但调用报缺少 `config.json` | 在同一源码目录完成 `setup.ps1`，核查客户端 command/args |
| 参数变化后版本不匹配 | 查询最新模型 revision；修改现有零件时提供 `expected_revision` |
| Creo 路径长度错误 | 将源码放入较短路径，并重新安装及生成客户端配置 |

模型保存在 `models/` 或任务输出目录，任务记录位于 `jobs/`。迁移电脑或移动项目目录后重新运行安装脚本并更新客户端配置；已有模型与记录需要一起保留。`.venv/` 不应从另一台电脑直接复制。

许可诊断仅返回状态，不返回许可值、服务器名或文件位置。环境变量 `PTC_D_LICENSE_FILE` 未设置，或其中所有本地路径都不存在时，子进程会尝试使用 `parametric.psf` 的有效路径或服务器配置；不改系统环境变量。有效文件、目录、`端口@服务器` 及仍含有效项的列表保持原配置。文件存在或服务器字符串可解析仍不证明能取得 Toolkit 许可，需要实际建模验证。

## 升级与部署核对

升级保持本机配置与运行数据：停止新提交，等待正在运行的建模任务结束（已受理作业只轮询，不重新提交），保留 `config.json`、`models/`、`jobs/`、`open_file/`、`session_erase/` 与 `session_activity.json`，用目标 Release 的公开源码更新代码与文档，重跑 `setup.ps1`，再重启客户端中的 MCP 服务。不要手工删除 `native/constants.inc`，构建会按本机 SDK 重新生成。

重启后核对以下四项，任一不符按未完成部署处理：

1. **版本**：`creo_capabilities` 的 `version` 等于所装 Release 标签去掉 `v` 前缀（例如标签 `v0.7.1` → `0.7.1`），并与该源码 `version.py` 一致。版本号本身不足以证明部署正确。
2. **路径**：`runtime.python_executable`、`runtime.server_entry`、`runtime.code_root` 指向本次解压目录及其 `.venv`，不是其他副本；移动目录后必须重跑安装。
3. **启动身份**：`runtime.source_changed_since_startup=false`，`runtime.source_fingerprints_at_startup` 已生成；为 `true` 时磁盘源码已变化，重启服务再验收。客户端配置改动不会替换已运行的服务进程。
4. **工具清单**：`creo_capabilities` 的工具数与 `unavailable_operations` 与该版本说明一致（0.7.1 为 94 个工具），而不是沿用上一版本的可见清单。

随后按「安装步骤」第 4 条用 `creo_startup_status` 等到 `ready`、`creo_session_status` 确认 `connected=true`，并完成一次保存重载验证。

## 从 0.2.0 升级到 0.21

停止 MCP 客户端中的服务并等待正在运行的建模任务结束。保留项目内 `config.json`、`models/`、`jobs/`，用 0.21 的公开源码更新代码及文档，重新运行安装脚本，再重启客户端服务。模型类型未记录的旧模型按零件处理；原有底板接口仍保留。

0.21 是预发布候选版；放样仍未完成，不能作为支持所有 Creo 操作的稳定版。完整边界见 [COVERAGE_0.21.md](COVERAGE_0.21.md)。


## 升级到 0.3.0

升级流程同上，保留本机配置、模型和任务目录，等待原生任务完成后更新代码并重跑 `setup.ps1`。不必手动删除 `native/constants.inc`；构建会自动更新。新接口及限制见 [版本说明](RELEASE_NOTES_0.3.0.md)。更新源码后重启客户端中的 MCP 服务，调用 `creo_capabilities` 核对版本与该 Release 一致；本节保留 0.3.0 当时的历史说明，当前核对项见上文「升级与部署核对」，不再要求 `version == "0.3.0"`。只打开一个 Creo 会话；高级配置 `creo_session_id` 可固定 Toolkit 连接目标，重启会话后需重新取得有效 ID，程序拒绝连接回退。重跑安装保留已有 ID，不会自动猜测新的连接目标。

包含本次建模增量的源码内附 MIT 种子库，安装器验证并注册，`creo_new_loft_part` 按数量/模式自动选择，不要求手填路径和特征 ID。库内有九个原生 PRT：2/3/4/6 截面的直线和平滑，以及 5 截面平滑；详细步骤见 [SEED_LIBRARY.md](SEED_LIBRARY.md)。新电脑需要重新安装并验证，不直接复制旧 `.venv`、二进制、配置或会话 ID；同机换客户端可以共用安装目录，见 [MIGRATION.md](MIGRATION.md)。

## Python 包的渐进迁移（DEV-002）

当前源码的更新检查实现位于 `src/creo_mechdog/update_check.py`，新的业务模块继续放入此包。`setup.ps1` 安装运行依赖后通过 `pip install --no-deps --editable <源码目录>` 安装包；开发环境可执行 `python -m pip install -r requirements-dev.txt`。根 `server.py`、`bridge.py` 和 `version.py` 入口继续保留，客户端命令无需改为 src 路径。

已有开发环境更新源码后，需要用该环境的 Python 执行 `python -m pip install --no-deps -e .`，再重启 MCP。移动整个安装目录后重跑安装，不直接复制旧虚拟环境；服务拒绝混用来自另一源码目录的包。当前安装方式以完整源码目录为基础，包元数据用于本地安装，不代表单独 wheel 已包含 SDK、种子与原生执行器。

能力查询 `runtime.python_package_root` 标明 Python 包位置，`resource_root` 和 `data_root` 默认仍为原安装目录；旧 `runtime.code_root` 保留原源码根语义。配置、模型、任务和构建仍在原目录，第一批不会在 src 下生成另一套数据。

## 版本检查与升级提醒（FEAT-020）

包含此功能的源码提供 `creo_check_update(force=false)`，能力查询与启动状态增加 `update` 快照；启动和建模不等待联网。检查包含公开预发布、使用 24 小时进程缓存，失败冷却 15 分钟。字段、超时边界及完整升级步骤见 [版本检查说明](UPDATE_CHECK.md)。旧版必须先手动升级一次，才能收到后续版本提醒；0.3.0 已包含此功能，0.2.6 为 81 个工具。

## 引用参数核对（BUG-006）

使用 capabilities.references.by_tool 查询工具特定种类和结构。axis_pattern.axis 支持几何轴 ID、datum_axis_feature 标签，并兼容 datum_feature 轴标签；其它参数中的 datum_feature 仍为基准平面。钣金边是裸引用，倒圆/倒角是集合数组，草图字典支撑面使用 reference 包装。更新源码后重启 MCP，并核对 schema、runtime 指纹及 [引用说明](REFERENCE_SYNTAX.md)；0.2.6 开发安装不能仅由版本号确认本项修复；0.3.0 包含本修复。

## 本机开发恢复联调（2026-10-17）

2026-10-20修复合集（0.4.3）：本版87工具不变（0.3.7 反馈修复 BUG-036/057/074 与观察性增强）；0.4.2 引入磁盘打开补充（87 工具）：`creo_open_file`（磁盘 .prt/.asm 只读检索显示）与 capabilities compact/分页、session_status `server_version`、接管结构化拒绝随 0.4.2 发布。更新安装后必须重启目标 MCP 连接器（工具数从 86 变 87；capabilities 默认返回 compact 摘要页，旧全量消费者按 section 遍历迁移）。上一轮 2026-10-19 纳管补充（0.4.1，86 工具）：无盘 prepare 模式与会话枚举。更新安装后必须重启目标MCP连接器，核对实际路径、启动指纹、`source_changed_since_startup=false`及新工具/模式；只更新磁盘文件或配置不会替换运行实例。先按[接管说明](ADOPTION.md)选择有文件或无盘流程。下面保留2026-10-17当轮部署边界。

按用户要求，WorkBuddy/Codex 只启用 `MCP_CREO_MechDog_dev`，启动 E盘项目的 `.venv\Scripts\python.exe` 与 `server.py`；C盘旧副本和test项保持禁用。注册名不等于发布版本，当前源码VERSION为0.4.3；用实际入口、源码指纹和87工具辨认部署。不要在同一Creo会话混用不同安装根的客户端：它们的根目录Toolkit锁互不共享。正式使用恢复入口前，先看[恢复说明](MODEL_RECOVERY.md)与[本轮中断记录](validation/BUG-001-recovery-2026-10-17.md)。目前实机测试已停止，卡死原因未定位。

## FEAT-029开发集成后的回调入口

0.3.4共84工具，新增只读creo_callback_status；运行实例需重连才会加载新定义。构建准备固定 `build/blend_callback_protk.dat`，其指向不可变引导及部署载荷，不代表Creo已注册或加载。首次及旧protocol 2迁移仍需使用者一次正式注册；将生成的blend_callback.config.pro片段合入实际加载的config.pro，delay_start true仍需手动启动。兼容升级通常需正常重启Creo并启动同一条目，无须为载荷哈希重新选择注册文件。具体步骤、拒绝/未知分支和限制见[生命周期说明](CALLBACK_LIFECYCLE.md)；当前卡死限制下只完成[离线集成](validation/FEAT-029-integration-2026-10-17.md)，本轮不执行这些GUI操作或实机复验。
