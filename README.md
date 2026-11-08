# MCP_CREO_MechDog 0.19.0

![version](https://img.shields.io/badge/version-0.19.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) ![platform](https://img.shields.io/badge/platform-Windows%20x64-lightgrey) ![python](https://img.shields.io/badge/python-3.12%2B-blue) ![Creo](https://img.shields.io/badge/Creo-9%20%2F%2010%20%2F%2012-orange) ![MCP](https://img.shields.io/badge/MCP-stdio-purple)

当前正式版 **0.19.0**（MINOR——DEV-074 曲面与整链批：新增公开工具 `creo_surface_round`（曲面边圆角）与只读 `creo_measure_surface_curvature`（数值曲率/G1），解除门禁并公开 `creo_quilt_merge`（quilt 合并），公开工具 **104→107**；五爪整瓶整链 46 个作业、63 项实机检查通过；钣金成形类、独立 quilt 偏置、任意非平面边界填充仍不可用，门禁保持） · [版本说明](docs/RELEASE_NOTES_0.19.0.md) · [Releases](https://github.com/wudahua/MCP_CREO_MechDog/releases)

> 让 AI 客户端通过 MCP，直接在 Creo Parametric 里创建**原生可编辑的参数化特征**——不是导出网格，也不是脚本模拟。

MCP_CREO_MechDog 是运行在你自己 Windows 电脑上的本地 MCP 服务（stdio）。它把 Creo 官方 C/C++ Toolkit 封装成 107 个公开工具（以 `creo_capabilities` 的 `tool_count` 为准；`creo_surface_boundary_fill` 已定义但门禁隐藏），供 WorkBuddy、Claude Desktop、Cursor 等支持 MCP 的 AI 客户端调用：从一句需求出发，生成带草图、尺寸、约束与特征树的 `.prt` / `.asm`，并保存到磁盘。

**适合**：重复性参数化建模、批量零件、AI 驱动的草图→拉伸→孔→装配流程、接管已有模型继续修改。
**不适合**：任意复杂自由曲面、专业模块的完整封装、没有真实 Creo 与许可的「云端建模」。

## 特性

- **原生参数化**：Creo 内可编辑的草图、拉伸、旋转、孔、圆角、抽壳、钣金、装配，保留尺寸与依赖关系。
- **107 个公开工具**（以 `creo_capabilities` 返回为准；`creo_surface_boundary_fill` 已定义但门禁隐藏，不计入）：实体特征、装配、工程图、放样／翼型、曲面修剪／投影曲线／法向偏置、两截面直纹曲面放样、quilt 合并、曲面边圆角、曲面组级缝合测量、数值曲率/G1 分析（不提供斑马纹/曲率梳图像）、参数与关系式、特征树查询、标准螺纹孔、只读质量属性、离线产品变体规划、保存与导出。
- **保存即校验**：每次修改后保存 `.prt.N` / `.asm.N`、从磁盘重载并比对特征、尺寸、体积与参数（`saved_file_reloaded_and_verified`）。
- **可回滚**：revision 保护、失败自动回滚、`unknown_outcome` 保留现场，旧请求不会改坏模型。
- **本地可控**：几何计算全在 Creo 进程内完成；服务不执行任意命令、不改动 Creo 安装目录、不上传模型。

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 系统 | Windows x64 |
| Python | 3.12+ x64 |
| CAD | Creo Parametric 9 / 10 / 12，及匹配的 Toolkit SDK |
| 构建 | MSVC x64 C++ 构建工具 |
| 许可 | 可用的 PTC 许可 |

Creo 软件、SDK、模板与许可需自行取得；MIT 只覆盖本项目原创代码、文档与种子库。当前开发与发布按本机 Creo 12.4.0.0 的改动范围验收，Creo 9/10 的已测与未测范围见[兼容矩阵](docs/COMPATIBILITY.md)。

## 安装

1. 下载源码，解压到较短的可写目录（如 `C:\MCP_CREO_MechDog`），在该目录执行后续命令。
2. 运行安装脚本，换成自己的 Creo 安装根目录：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 12.4.0.0'
   ```

   脚本会创建 `.venv/`、编译 Toolkit 执行器、生成 `config.json` 与 `client-config.json`。Python 不在 PATH 时可加 `-Python '...\python.exe'`，编译器未自动找到时可加 `-VcVars64 '...\vcvars64.bat'`。
3. 把 `client-config.json` 中的服务配置加入支持本地 stdio MCP 的 AI 客户端并启动。

完整步骤与排错见 [docs/INSTALL.md](docs/INSTALL.md)。升级后先重启 MCP 连接器，再核对路径、启动指纹与工具清单。

## 快速开始

客户端配置（路径以安装生成的为准；本机开发联调按约定使用 `MCP_CREO_MechDog_dev`）：

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

服务启动后，让 AI 调用 `creo_startup_status` 等 `state == "ready"`、`creo_session_status` 确认连接，再调用 `creo_execute_plan`，例如创建 Ø20×30 的圆柱：

```json
{
  "operations": [
    {"op":"sketch","label":"profile","plane":"XY",
     "entities":[{"type":"circle","name":"circle","center":[0,0],"radius":10}],
     "dimensions":[{"name":"diameter","type":"diameter","refs":[{"entity":"circle"}],"value":20,"position":[15,0]}]},
    {"op":"extrude","label":"solid","sketch":"profile","depth":30}
  ],
  "assertions":{"require_solid":true,"volume_mm3":9424.77796076938}
}
```

建模工具立即返回 `job_id`；轮询 `creo_get_job(job_id, detail="compact")` 到 `status == "succeeded"`，确认 `result.saved_file_reloaded_and_verified == true`。随后调用 `creo_set_sketch_dimensions(model_id=返回的模型ID, expected_revision=最新revision, sketch="profile", values={"diameter":24})`，拉伸实体随之更新。

> 两个约定：修改已有模型要传最新 `expected_revision`；Toolkit 单通道忙碌时**立即**返回 `status="busy"`（不排队、不自动重试），已接受的任务只轮询、不重新提交。

长度单位为毫米、角度为度；引用格式见[引用格式](docs/REFERENCE_SYNTAX.md)，更多可复制方案见 [`examples/`](examples/)。

## 功能一览

| 类别 | 代表工具 |
| --- | --- |
| 零件与计划 | `creo_new_part`、`creo_execute_plan` |
| 草图与实体 | `creo_create_sketch`、`creo_extrude`、`creo_revolve`、`creo_hole` |
| 修饰与基准 | `creo_round`、`creo_chamfer`、`creo_shell`、`creo_datum_plane`、`creo_dimension_pattern` |
| 钣金 | `creo_new_sheetmetal`、`creo_sheetmetal_wall`、`creo_sheetmetal_planar_wall`、`creo_resize_sheetmetal_planar_wall`、`creo_sheetmetal_flange` |
| 装配 | `creo_new_assembly`、`creo_assemble_component`、`creo_list_components`、`creo_recolor_assembly` |
| 放样与翼型 | `creo_new_loft_part`、`creo_loft`、`creo_new_airfoil_blade` |
| 参数化修改 | `creo_set_dimensions`、`creo_set_parameters`、`creo_set_relations`、`creo_set_sketch_dimensions` |
| 查询与导出 | `creo_inspect_model`、`creo_save_model`、`creo_export_model`、`creo_get_job` |

完整清单以 `creo_capabilities` 为准；各类能力的验收范围与边界见[兼容矩阵](docs/COMPATIBILITY.md)与[语法参考](docs/REFERENCE_SYNTAX.md)。

## 文档

| 我想… | 看这里 |
| --- | --- |
| 安装、排错、升级 | [docs/INSTALL.md](docs/INSTALL.md) |
| 查工具参数与引用格式 | [docs/REFERENCE_SYNTAX.md](docs/REFERENCE_SYNTAX.md)、[docs/MODELING_0.21.md](docs/MODELING_0.21.md) |
| 找可复制的建模方案 | [examples/](examples/) |
| 确认哪些功能已实测 | [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) |
| 种子库 / 换电脑换 Agent | [docs/SEED_LIBRARY.md](docs/SEED_LIBRARY.md)、[docs/MIGRATION.md](docs/MIGRATION.md) |
| 直接混合的一次性回调 | [docs/CALLBACK_LIFECYCLE.md](docs/CALLBACK_LIFECYCLE.md) |
| 查看版本变更 | [Releases](https://github.com/wudahua/MCP_CREO_MechDog/releases)、[0.19.0 版本说明](docs/RELEASE_NOTES_0.19.0.md) |
| 参与开发 / 看台账 | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)、[docs/BACKLOG.md](docs/BACKLOG.md) |

## 已知限制

- 不是所有参数组合与几何都已实机验证；无效轮廓、基准或特征顺序由 Creo 返回错误，AI 需自行规划。
- Creo 9 编译探测修复已实现，但本机无 Creo 9 SDK，实机编译与建模运行时未验收；Creo 10 不再要求独立复测。
- 钣金四壁、relief 去料、嵌套装配、面级上色等仍有明确边界；直接混合（`creo_loft`）需一次性回调注册，种子放样不需要。
- 串行单通道，无队列、FIFO 或容量保证；未测与开放项按[统一台账](docs/BACKLOG.md)跟进。
- 不提供任意命令／代码执行，不输出许可服务器内容；正在交互建模或有模态对话框时应先处理该会话状态。

## 开发

开发维护从[开发入口](docs/DEVELOPMENT.md)与[统一功能台账](docs/BACKLOG.md)开始，每项工作先定义验收。常用命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\dev_check.py
.\.venv\Scripts\python.exe tools\test_general.py
```

`tools/test_general.py` 等集成测试会真实连接 Creo 并创建测试模型；语言／单元检查与 Creo 实机验收分别记录证据。

## 许可证

[MIT](LICENSE)。第三方依赖与 PTC 前置条件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；Creo 软件、SDK、模板与许可不包含在本项目中，需自行取得。
