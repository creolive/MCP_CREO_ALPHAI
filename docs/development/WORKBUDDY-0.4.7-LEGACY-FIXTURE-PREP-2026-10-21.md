# WorkBuddy：0.4.7 非空迁移测试模型准备

目的：仅创建一个独立的、保存重载验证通过的受管圆盘，回传完整身份。随后由开发侧只对该新模型无损还原旧内联元数据，才具备非空迁移条件。本提示词不要求或授权 WorkBuddy 修改存储格式。

请仅通过已连接的 `MCP_CREO_MechDog_dev` 公开工具实际操作，不读源码、配置、文件、Git或日志，不执行终端或本地脚本。

1. 通过公开接口确认服务0.4.7及E盘dev部署。版本不符、工具缓存未更新时停止报告；不要调用其他MCP服务代替。
2. 原生调用前取得操作者对当前Creo界面正常响应、无阻塞对话框、无正在执行任务的确认。先查 `creo_startup_status(retry=false)`；building/checking时只轮询同次启动状态，最多60秒。timeout/failed/busy/unknown或始终未ready即停止，不主动retry=true，不重启或结束Creo。ready后查询 `creo_session_status`，必须connected=true。
3. 仅创建一个新测试模型，名称用 `wb047_legacy_prep_` 加唯一小写数字字母后缀，总长≤31。不要使用create_plate，不选择已有模型，不迁移任何历史记录。
4. 调用一次 `creo_execute_plan`，省略model_id，使用下面的operations及assertions：

```json
{
  "model_name": "wb047_legacy_prep_1021a",
  "operations": [
    {
      "op": "sketch",
      "label": "disk_profile",
      "plane": "XY",
      "entities": [{"type": "circle", "name": "disk", "center": [0, 0], "radius": 8}],
      "dimensions": [{"name": "diameter", "type": "diameter", "refs": [{"entity": "disk"}], "value": 16, "position": [12, 0]}]
    },
    {"op": "extrude", "label": "disk_solid", "sketch": "disk_profile", "depth": 10}
  ],
  "assertions": {"require_solid": true}
}
```

名称发生冲突时停止并说明，不向同名既有模型追加操作。请求被受理后仅轮询原 `creo_get_job(job_id, detail="compact")`，不得重复提交。busy记录原始字段并停止；unknown_outcome、连接超时或界面异常时停止所有后续原生操作，保留现场。

5. 成功必须同时满足：status=succeeded，存在完整model_id和job_id，`saved_file_reloaded_and_verified=true`，体积约2010.6192982974674 mm³（容差0.01）。revision以实际返回为准，不猜测。
6. 用 `creo_inspect_model(detail="compact")` 核对ready/revision/体积；再用 `detail="full", section="aliases"` 确认disk_profile、disk_solid及diameter尺寸别名可见。必要时仅通过get_job full补取公开返回的完整SHA256，不读磁盘。
7. 到此停止，不改尺寸、不regenerate、不做迁移inspect/apply、不擦除或删除模型；不要转用其他既有模型。特别是不要在开发侧还原旧格式前做空迁移。
8. 返回：实际工具调用与输入、服务/Creo版本、会话前置条件、模型名、完整32位model_id、完整job_id、revision、体积、status、saved_file_reloaded_and_verified、公开SHA256、别名和尺寸名称及第一次原始错误。ID不得写成省略号。

最终只报告“新受管模型准备完成，待开发侧还原旧格式”或明确失败/前置条件未满足；不能报告旧格式、非空迁移或超限迁移已经通过。受测源码提交或内部机制公开接口未提供时写“无法确认”。
