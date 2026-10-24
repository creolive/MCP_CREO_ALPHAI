# WB080 黑盒验收报告 · 第三轮（BUG-080 整合树复验）

- 验收时间：2026-10-24 12:11（GMT+8）
- 服务标识：MCP_CREO_MechDog_dev
- 方式：仅 MCP 公开工具，不读源码、不读本地文件、不运行本地脚本；全程只读。

## 步骤 1｜环境确认（不通过 → 停止）

- 调用：`creo_capabilities`（detail="compact"）
- 输入：无业务参数。
- 关键输出：name="MCP_CREO_MechDog"，version="0.5.1"，server_version="0.5.1"，update.status="up_to_date"（current=latest=0.5.1，is_prerelease=true），tool_count=91，unit="mm"，angle_unit="degrees"。
- 预期：server_version=0.5.2。
- 实测：server_version=0.5.1，**服务未切换**。

## 结论

**服务未切换，本轮未执行。**

按验收规程，server_version 仍报 0.5.1（非预期的 0.5.2），视为服务未切换到整合树构建，立即停止：未调用 creo_list_session_models、未调用 creo_inspect_session_assembly，步骤 2～5 全部未执行，前置未确认，亦未做任何模型创建或会话写操作。

## 未执行项说明

- 步骤 2（前置确认，装配 WB080_INCH_WB104102 是否存在）：未执行。
- 步骤 3（BUG-080 五项核验）：未执行。
- 步骤 4（重复性核验）：未执行。
- 步骤 5（无副作用核验）：未执行。

以上各项本轮一律记"未执行"，不推测通过。

## 无法确认项

- 整合树构建是否真实存在、是否已部署：无法由 MCP 观察，记"无法确认"。
- 服务进程对应的源码版本/构建身份：无法由 MCP 观察，记"无法确认"。

## 下一步建议

切换 MCP_CREO_MechDog_dev 至整合树构建（server_version=0.5.2）后重跑第三轮验收脚本。
