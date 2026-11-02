# MCP_CREO_MechDog 0.11.5 版本说明

- 类型：PATCH，兼容性工程整理；公开工具仍 **95 个**，无新增工具或参数变更。
- 条目：[DEV-002 第三批](work-items/DEV-002.md)，种子与能力模块包化；整个 DEV-002 仍为开发中。
- 版本入口：[version.py](../version.py)；配套种子包 `MCP_CREO_MechDog-0.11.5-seed-library.zip`。

## 本版内容

- 将 seeds/capabilities 的唯一业务实现迁入 `src/creo_mechdog/`。根 `seeds.py` 从 236 行减至 19 行，`capabilities.py` 从 572 行减至 15 行，只保留兼容导出与种子 CLI 转发。
- 保持旧导入、函数/常量对象身份、私有种子 helper 访问、默认种子列举和 `seeds.py --install`；CLI 成功仍输出单个 JSON，失败仍非零退出。
- 生产消费者及受影响测试 mock 使用包内定义；标准 editable 安装显式包含根 bridge/seeds/capabilities，仓库外导入不再依赖当前目录。
- 服务源码身份同时覆盖两份根包装和包内实现；资源、配置、任务、模型与构建目录仍属于原安装根，不产生另一套运行数据。
- 修复旧种子重定位测试对预先存在 `.tmp` 的隐式依赖，独立解压副本可单独执行对应回归。
- 同步架构说明、根模块职责和 DEV-002 台账；服务、启动、桥接实现与 C++ 上下文/独立编译仍按后续批次推进。

工具输入 schema、能力数据、种子输出及任务/revision/恢复语义在迁移前后保持一致；无原生建模代码变更。本批并不表示 Python 包已脱离根桥接依赖。

## 验证与边界

- 实现阶段（0.11.4 开发源码）：79 项基线、123 项模块回归、23 项布局回归；95 个工具 schema/能力/种子契约比较一致。最终统一检查 2196 项零失败/错误，独立安装副本 64 项通过，见[实现证据](validation/DEV-002-batch3.md)。这些历史结果不改称 0.11.5 发布版结果。
- 本次 **0.11.5 发布源码**：`tools/dev_check.py --work-item DEV-002-release-0.11.5` success=true、unit_tests=passed；2196 项单测 0 failures / 0 errors；0.11.5 候选源码包全新环境安装及 64 项回归通过；最终附件从实际 main/标签提交生成，独立解压安装验证及远端四附件 SHA256 核对见[发布记录](validation/RELEASE-0.11.5.md)与 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.11.5)。
- 环境：Windows 11 x64 / Python 3.12.14 / Ruff 0.17.0 / clang-format 23.1.3，依赖按锁文件安装；检查无新增风格回归，不代表全库存量严格格式清零。
- **本批真实 stdio、Creo 建模/编辑/保存重载、WorkBuddy、Creo 9/10、并发/恢复实机均未执行。** BUG-001 会话限制继续适用，T5 待当前会话可操作确认；无新 Toolkit 连接，无结束 Creo 或清 unknown。
- 本次不重编原生执行器。相对 0.11.4 正式源码包，35 个原生代码文件和 json.hpp 原字节相同；第三方许可证仅 LF/CRLF 原字节差异，规范化文本相同，未修改第三方文件。DLL/注册信息只有本机只读快照，不外推为当前 live 注册验证。

## 升级

1. 使用成对的 0.11.5 源码包和种子包。种子 PRT 字节不变，但两份清单的 `compatible_server_version` 已更新，旧版本种子包会被版本闸门拒绝。
2. 使用当前安装的虚拟环境重新执行 `python -m pip install --no-deps -e .`，或沿用 setup.ps1；重启 MCP 服务加载新模块。客户端入口仍为根 server.py，已有模型/任务/配置路径保持不变。
3. 本次没有需要迁移的公开工具参数。原生源与回调源未变，不因本批要求重新注册 DLL 或重启 Creo；不要把服务重载误解为可以清除模型保护。
