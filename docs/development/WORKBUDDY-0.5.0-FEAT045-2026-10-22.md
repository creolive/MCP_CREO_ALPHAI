# WorkBuddy 黑盒验收提示词：FEAT-045 装配只读检查（0.5.0）

以下提示词交给 WorkBuddy 直接通过已连接的 MCP 工具执行，对最终用户可见行为做黑盒验收。WorkBuddy 不查看源码、不执行本地脚本/单测/开发检查；环境、版本与工具清单通过 MCP 公开接口确认；无法由 MCP 观察的项目记"未验证"。

---

## 提示词

你在本机通过 MCP_CREO_MechDog 连接 Creo 做黑盒验收。只调用 MCP 工具，不读仓库、不运行本地脚本。

1. 用 `creo_session_status` 确认服务版本（预期 0.5.0）与连接状态；用 `creo_capabilities`（detail=compact）确认 tool_count（预期 91）。
2. 用 `creo_list_session_models` 列出会话模型；如果会话里没有装配，先用 `creo_erase_session_models`（inspect→apply 两步）清空非托管会话模型，再 `creo_open_file` 打开一个你环境中的装配文件（绝对路径，例如 ASM_MX 或其他 .asm）。
3. 调用 `creo_inspect_session_assembly`，name 填该装配名：
   a. 首次 limit=50：核对返回的 assembly 根信息（name/model_type/origin/modified）、components 列表（每项 occurrence_path/parent_path/name/model_type/resolved/suppressed/packaged/constraints/transform_to_parent/transform_to_root）、total、complete、transform_convention 说明（行向量、平移末行、毫米）。
   b. 用 limit=2 翻页直到 next_cursor=null，核对每页组件之和等于 total、无重复无遗漏、快照 id 一致。
   c. 若装配含子装配（嵌套），核对 depth≥1 组件的 occurrence_path 长度与 parent_path；若有同一组件的重复实例，核对它们分别成条且各自有变换。
   d. 任选一个组件，把它的 transform_to_parent 末行（平移）与你在 Creo 中看到的该组件位置比对（如可行）。
   e. 对比 inspect 前后的 `creo_list_session_models`：会话内容应无变化；确认没有新的受管 model_id 产生（inspect 不收养）。
4. 拒绝路径：`creo_inspect_session_assembly` 用一个不存在的名字（如 "no_such_asm_xyz"）→ 预期结构化错误 SESSION_ASSEMBLY_NOT_FOUND；用一个零件名（非装配）→ 预期类型不匹配错误。
5. 报告：逐项列出工具调用、输入、返回摘要（total/complete/每页数量）、变换末行数值、约束类型列表、会话前后对比结论；无法由 MCP 观察的项明确记"未验证"；不做任何保存、擦除（除第 2 步的清场外）、编辑或收养操作。
