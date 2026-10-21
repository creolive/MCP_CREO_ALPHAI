# MCP_CREO_MechDog

开发维护从 [开发入口](docs/DEVELOPMENT.md) 和 [统一功能台账](docs/BACKLOG.md) 开始。每项工作先定义验收；语言与单元检查、Creo 实机验收分别记录。项目采用渐进布局整理，当前支持环境见 [兼容矩阵](docs/COMPATIBILITY.md)。

本地 Windows MCP 服务，按需启动或连接 Creo Parametric 9 / 10 / 12，通过官方 C/C++ Toolkit 创建、查询和修改**原生参数化特征**。当前开发与发布按本机 Creo 12.4.0.0 的改动范围验收；Creo 10 不再要求独立复测。Creo 9 与 Toolkit 9 已纳入支持／要求范围，编译探测修复已实现，但本机无 Creo 9 SDK，实机编译与建模运行时均未验收。各环境已测和未测范围见[兼容矩阵](docs/COMPATIBILITY.md)。典型建模流程为：新建零件 → 草图 → 拉伸／旋转 → 切除／孔 → 后续特征；底板接口保留为快捷工具。

当前注册 **87 个工具**，实际可见清单以 `creo_capabilities` 为准。接口覆盖常见实体特征、磁盘模型打开、受管副本接管、会话枚举、受控恢复及直接混合，**尚未完成所有 Creo 操作和参数组合的覆盖**。禁用操作从工具列表隐藏，并在提交前拒绝。服务使用官方 Python MCP SDK 2.3.0、stdio 传输，采用 [MIT 许可证](LICENSE)。使用者在自己的 Windows 电脑上安装依赖并编译 Toolkit 执行器，由本地 AI 客户端调用。

当前服务／源码版本为 **0.4.6**，交付内容、验收环境及未测范围见[版本说明](docs/RELEASE_NOTES_0.4.6.md)和[发布核对](docs/validation/RELEASE-0.4.6.md)。收养链路已把控制元数据与完整检查资料分离（BUG-076 精修）：结果、令牌、请求和登记只保存摘要及受控文件引用（路径/SHA256/字节数），完整几何资料留在所属目录按内容寻址的 sidecar 文件中，源模型、复制后与保存重载的带容差比较保持不变；引用被篡改、缺失或过期时明确拒绝。旧内联记录继续兼容读取；仍有文件超过 16 MiB 预算时返回 `ADOPTION_METADATA_BUDGET_EXCEEDED`（携带 `metadata_kind`、实际字节数、预算、失败阶段和恢复指引），该诊断不提高限额。空窗口收养返回结构化 `NO_CURRENT_MODEL`。原环境复验及 WorkBuddy 黑盒等剩余工作见[统一台账](docs/BACKLOG.md)。

服务后台检测已有会话、协调启动并检查建模就绪；成功建模及保存重载才证明相应操作在该环境可用。启动配置和排错见[安装说明](docs/INSTALL.md)。

普通混合可直接创建或追加，范围见 [直接混合](docs/DIRECT_BLEND_0.2.5.md)；种子复用见 [调用说明](docs/LOFT_SEED.md)、[多截面](docs/MULTISECTION_BLEND.md)。草图支持 `dimensioning="auto" / "autodim" / "coordinates"`，坐标模式的范围与尺寸编辑规则见 [草图说明](docs/SKETCH_STABILITY_0.2.5.md)。迁移步骤见 [种子库](docs/SEED_LIBRARY.md) 和 [换电脑、换 Agent](docs/MIGRATION.md)。

直接混合使用固定注册入口与升级预检：按下文一次性设置及[生命周期说明](docs/CALLBACK_LIFECYCLE.md)完成正式注册、持久配置与手动启动，再查 `creo_callback_status`；只有实时 `ready` 才提交直接混合。查询和建模不加载 DLL、不修改安全策略。升级、回退及多目录并存等剩余验收见[统一台账](docs/BACKLOG.md)。新建种子放样不需要此回调。

工程图、曲面、布尔、筋、UDF、钣金和装配各有验收范围，见[兼容矩阵](docs/COMPATIBILITY.md)；旧版测试与来源见[历史资料](docs/BACKLOG_COMPLETED.md)。新版本不会改写已发布的 GitHub 源码或附件。

[版本检查与提醒](docs/UPDATE_CHECK.md)的断网期间建模、高版本提示及客户端展示等剩余验收仍按台账跟进。0.2.6 旧发布需先手动升级一次才可收到后续更新提醒。

Python 包迁移前两批已完成，更新检查、输入模型及轮廓／翼型辅助实现位于 `src/creo_mechdog/`，整体迁移仍继续。现有开发环境更新源码后执行 `python -m pip install --no-deps -e .`；正常安装由 `setup.ps1` 完成。根入口和数据位置保留，见[迁移任务卡](docs/work-items/DEV-002.md)。

模型引用须按具体工具的参数形状选择，见[引用格式](docs/REFERENCE_SYNTAX.md)。

## 安装

升级后先重启目标 MCP 连接器，再核对实际路径、启动指纹和工具清单；现有模型接管流程与未测边界见[接管说明](docs/ADOPTION.md)。

准备 Windows x64、Python 3.12+ x64、Creo Parametric 9、10 或 12 及匹配的 Toolkit SDK、MSVC x64 C++ 构建工具和可用的 PTC 许可。Creo 9 与 Toolkit 9 的编译探测修复已实现，实机编译与建模运行时未在本机验收。Creo 软件、SDK、模板和许可需要自行取得；MIT 适用于本项目代码、文档及种子库的原创内容，不提供 PTC 软件授权。第三方依赖和 PTC 前置条件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

1. 下载源码，解压到较短的可写目录，例如 `C:\MCP_CREO_MechDog`；下列命令在该目录执行。
2. 运行安装脚本，填写自己的 Creo 安装根目录：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
   ```

   Creo 12.4 的安装示例：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 12.4.0.0'
   ```

   按自己的安装位置替换路径，使用对应版本的 Toolkit SDK 在目标机重新构建。

   如果 Python 没有加入 PATH，可加 `-Python 'C:\Path\To\python.exe'`。如果编译器没有自动找到，可加 `-VcVars64 'C:\Path\To\vcvars64.bat'`。这两个示例路径需要替换。
3. 安装成功后，脚本生成本机 `config.json`、`.venv/`、`build/` 和 `client-config.json`。将 `client-config.json` 中的服务配置加入支持本地 stdio MCP 的 AI 客户端。
4. 启动客户端中的 MCP 服务，服务自动复用已有 Creo 或按配置启动。让 AI 调用 `creo_startup_status` 等待 `state == "ready"`，再用 `creo_session_status` 确认连接后提交建模计划。若 Creo 显示启动对话框，由使用者处理。成功建模及保存重载验证才证明相应操作在该环境可用。

脚本不修改全局客户端配置。完整安装与排错说明见 [docs/INSTALL.md](docs/INSTALL.md)；GitHub 源码发布步骤见 [docs/PUBLISH_GITHUB.md](docs/PUBLISH_GITHUB.md)。GitHub 仓库用于分发源码，服务在使用者的电脑运行。

### 直接混合（Blend）的一次性回调设置

`creo_loft` / 计划内 `loft`（直接混合）依赖一个常驻回调 DLL，须由使用者完成一次正式注册；未就绪时建模前会被明确拒绝（`BLEND_CALLBACK_SETUP_REQUIRED`）。**新建种子放样（`creo_new_loft_part`、`creo_new_airfoil_blade`）不需要此回调**。一次性步骤：

1. 构建后在 `build\blend_callback_setup.json` 或 `creo_callback_status` 返回中确认 `registry_file`（固定入口 `<安装目录>\build\blend_callback_protk.dat`）。
2. 在 Creo 的「辅助应用程序」（Auxiliary Applications）对话框注册该 `registry_file` 一次，手动启动它并亲自确认 DLL 安全提示；不要直接注册 `module_file`。
3. 跨 Creo 重启保持条目：把 `build\blend_callback.config.pro` 中的 `protkdat <注册文件绝对路径>` 一行合入实际加载的 config.pro（生成片段不会被自动读取）。
4. 正常重启 Creo 后条目应自动出现（`delay_start true` 仍需手动 Start）。
5. 查询 `creo_callback_status`：`readiness=ready` 才提交直接混合；`not_loaded`（可确定未加载，含首次）的 `instruction` 首行即注册入口，`unknown` 表示无法确认，保守处理。

MCP 不会代为注册、加载 DLL 或修改 Creo 安全策略。完整流程、升级/回退与限制见 [生命周期说明](docs/CALLBACK_LIFECYCLE.md)。

## 建模能力

| 类别 | 工具及能力 |
| --- | --- |
| 零件与建模计划 | `creo_new_part`、`creo_execute_plan`：新建毫米零件，或对已有 MCP 零件逐步追加特征 |
| 草图 | `creo_create_sketch`：直线、中心线、圆、圆弧、矩形、多段线、样条、椭圆；显式尺寸和约束；auto/autodim/coordinates 尺寸策略 |
| 拉伸 | `creo_extrude`：实体增材、切除、贯穿切除、曲面、薄壁、正/反向、对称深度、新实体；切除未去料（板外草图、方向/深度错误或已去除区域）时失败回滚，成功操作详情返回material_removed_mm3 |
| 旋转 | `creo_revolve`：实体旋转、旋转切除、指定角度，使用草图中心线或外部轴；提供曲面、薄壁和对称角度分支；切除零去料同样失败回滚并返回material_removed_mm3 |
| 孔 | `creo_hole`：原生直孔，平面定位，两条独立平面参考或共面直边及有符号偏置；边参考用放置面中心明确定位侧。通孔或指定深度盲孔，flip反转原生切削侧；无去料时失败回滚，成功操作详情返回孔轴及material_removed_mm3 |
| 修饰特征 | `creo_round`、`creo_chamfer`、`creo_shell`：恒定半径圆角、等距倒角、恒定厚度抽壳；用查询得到的边/面 ID 选引用 |
| 基准与重复 | `creo_datum_plane`、`creo_datum_axis`、`creo_dimension_pattern`：偏移/角度基准面、基准轴、一方向尺寸阵列 |
| 镜像、扫掠、拔模 | `creo_mirror`：整体/几何镜像；`creo_sweep`：恒定截面及命名截面尺寸；`creo_draft`：恒角、不分割拔模 |
| 钣金 | `creo_new_sheetmetal`、`creo_sheetmetal_wall`、`creo_sheetmetal_flange`、`creo_sheetmetal_unbend`、`creo_sheetmetal_bend_back`、`creo_sheetmetal_flat_pattern`：首壁、弯曲法兰、展开、折弯回去和平展；保留原生特征树 |
| 装配 | `creo_new_assembly`、`creo_assemble_component`、`creo_component_placement`、`creo_component_constraints`、`creo_remove_component`、`creo_list_components`：组件版本副本、定位、约束、删除和查询 |
| 新增曲面与实体 | `creo_surface_fill`、`creo_thicken`、`creo_solidify`、`creo_boolean_bodies`、`creo_rib` |
| 新增基准 | `creo_datum_csys`、`creo_datum_points` |
| 原生工程图 | `creo_new_drawing`；图纸、一般/投影视图、尺寸显示、注释、表格及编辑/删除；原生 DRW 与 PDF 输出 |
| UDF 特征库 | `creo_inspect_udf`、`creo_create_udf`：查询并复用用户的 .gph，保留组内原生参数特征 |
| 普通混合种子复用 | `creo_new_loft_part`：按新 XY 截面和模式自动选择随包种子；自动匹配 2/3/4/6 的直线和平滑及 5 的平滑，其他数量需显式兼容种子或使用直接混合；`creo_list_seeds`、`creo_validate_seed`、`creo_install_seed_library` |
| 翼型与几何编辑 | `creo_create_airfoil_section`、`creo_new_airfoil_blade`、`creo_set_airfoil_parameters`、`creo_update_sketch_geometry`；原生草图和 Blend，弦长/厚度/扭转/原点参数 |
| 定位及特征组织 | `creo_transform_geometry`、`creo_set_geometry_transform`、`creo_group_features`、`creo_reorder_features`、`creo_axis_pattern`；完整实体/quilt 原生定位、原生局部组和轴阵列 |
| 直接混合及追加 | `creo_loft`：独立 XY 草图按 Z 递增，直线/平滑原生实体混合；支持受管零件的默认实体增材 |
| 参数化修改 | `creo_set_dimensions`、`creo_set_sketch_dimensions`、`creo_set_parameters`、`creo_set_relations`：编辑特征尺寸/草图尺寸、零件参数、简单算术关系式，重新生成依赖特征 |
| 特征树与拓扑查询 | `creo_inspect_model`、`creo_refresh_model`、`creo_list_models`：特征 ID、名称、类型、状态、尺寸、草图尺寸、几何引用 ID、面/边/实体、体积、包围盒、参数和版本 |
| 高级原生特征接口 | `creo_create_feature_tree`、`creo_lookup_constants`、`creo_dump_feature_tree`：按照本机 SDK 的 Element Tree 结构创建特征，查询常量、导出特征 XML |
| 保存与导出 | `creo_regenerate`、`creo_save_model`、`creo_export_model`：保存原生 PRT/ASM，导出 STEP、IGES、STL、JPEG；装配的所有导出格式组合未验证 |
| 环境与任务 | `creo_check_environment`、`creo_session_status`、`creo_capabilities`、`creo_get_job`、`creo_list_jobs`：环境、实际 Toolkit 连接、能力和任务进度 |
| 磁盘模型打开 | `creo_open_file`：只读检索并显示磁盘既有 `.prt`/`.asm`（显式 `.N` 版本或目录内最高数字版本）；同名同类型会话模型与非空会话装配拒绝，冲突提示含装配依赖加载来源；缺件装配报残留对象、缺件清单标记未知；不保存、不擦除、不接管，成功返回 `model_id=null`，并附有界 `loaded_session_models` 摘要（区分会话模型数与组件实例数） |
| 会话模型擦除 | `creo_erase_session_models`：显式擦除选定的会话模型清单。`inspect(targets)` 返回每项目标身份、阻断原因、装配先于组件的擦除顺序、预期剩余对象和 600 秒令牌；`apply(evidence_token, idempotency_key)` 只执行令牌中的清单并返回 `job_id`。仅限有盘、未修改、非受管、无清单外引用与依赖环的对象；逐项复核后经两次独立查询确认消失；中途失败停止并明确报告已完成/未确认清单。不保存模型、不删除磁盘文件 |
| 快捷底板 | `creo_create_plate`：兼容此前矩形底板、角圆角、独立通孔接口 |

特征保存为 Creo 可编辑的草图、拉伸、旋转、孔、圆角等，保留尺寸及依赖。多段线和矩形会展开为原生直线，不能将 `polyline` 名字当作单个尺寸引用；例如 `box_0` 是矩形第一条边。

提供接口不等于所有参数组合都已验证。[直线混合摘要](docs/validation_loft_seed.json) 与 [平滑混合摘要](docs/validation_loft_smooth.json) 保留两截面的历史测试；[其他开发功能摘要](docs/validation_development.json) 和 `build/capability_evidence.json` 是此前测试的历史证据，本轮未重跑其完整套件。已测试非矩形支架、带内孔和沟槽的轴类件、多实体圆弧/椭圆实体、样条拉伸曲面、薄壁对称拉伸、抽壳、边圆角和倒角、尺寸阵列及参数关系驱动。高级树接口需要符合 SDK 的具体特征定义，不能自动补齐任意缺失的草图或集合。

## 接入与调用

把以下本地 stdio 服务配置加入支持 MCP 的客户端：

```json
{
  "command": "C:\\MCP_CREO_MechDog\\.venv\\Scripts\\python.exe",
  "args": ["C:\\MCP_CREO_MechDog\\server.py"]
}
```

上述路径仅为示例，以安装生成的实际路径为准。服务名称及客户端注册键为 `MCP_CREO_MechDog`。`client-config.json` 是同一配置的 `mcpServers` 格式；不同客户端的配置格式可能需要转换，必须保留相同的 command/args。服务启动后客户端可发现工具的完整 JSON Schema。服务从自然语言规划器接收结构化建模操作；自然语言理解由调用它的 AI 客户端完成。

典型流程：

1. 调用 `creo_check_environment`、`creo_session_status` 检查本机环境并实际连接。
2. 使用 `creo_execute_plan` 一次创建完整零件，或用 `creo_new_part` 后分步调用草图及特征工具。
3. 建模工具立即返回 `job_id`；轮询 `creo_get_job(job_id, detail="compact")`，等待 `status == "succeeded"`，并检查 `result.saved_file_reloaded_and_verified == true`。需要完整几何和尺寸时使用 `detail="full"`；该值仍是单任务查询的默认值。`creo_list_jobs` 默认返回精简结果。
4. 保留 `model_id` 和最新 `revision`。修改已有零件时提供 `expected_revision`；版本不一致会拒绝旧请求。
5. 查询实际面/边/尺寸 ID 后追加特征。引用发生变化时重新查询，不复用猜测的拓扑 ID。

Toolkit 操作共用一个通道，提交时忙碌会立即拒绝；响应保持 MCP `isError=true`，JSON 文本与 `structuredContent` 同时给出 `status="busy"`、`accepted=false`、`blocking_job_id`、`blocking_model_id`、`blocking_operation`、`retry_after_seconds` 和 `retry_guidance`。未创建新任务。占用者可能是任务、提交登记、连接探针或构建；无法确定时 ID 为 null，不能猜测最近的任务就是占用者。1 秒是建议重查间隔，不是完成时间承诺。已接受的任务只轮询，不重新提交；未知结果先检查模型。

任务模型登记（revision、pending_job、保存结果）在锁内收尾，释放通道后才发布持久化终态。观察到旧任务 succeeded 后，其他客户端仍可能取得通道，此时按新响应的占用者处理。`creo_get_job`、`creo_list_jobs`、`creo_inspect_model`、`creo_list_models` 读取持久化快照，不等待 Toolkit；`creo_refresh_model`、导出和实际连接检查仍需要通道。已接受后台 runner 最多等锁 120 秒；没有公开 FIFO、容量或排队顺序保证，本次没有增加队列能力。开发与 WorkBuddy 验收范围见 [BUG-009](docs/work-items/BUG-009.md)。

例如创建有原生特征树的圆柱：

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

随后 `creo_set_sketch_dimensions` 使用 `sketch:"profile", values:{"diameter":24}` 修改直径；拉伸实体随之更新。`creo_set_dimensions` 接收查询结果中的模型尺寸 ID，例如 `values:[{"id":18,"value":40}]`；实际 ID 由 Creo 生成。

完整案例在 `examples/`；0.21 新增镜像、扫掠、拔模和钣金首壁计划。装配调用步骤见 [docs/MODELING_0.21.md](docs/MODELING_0.21.md)。尺寸阵列先建立引导孔，再查询其定位尺寸 ID，调用 `creo_dimension_pattern`，指定包含引导成员的总数量和每次增量。

## 坐标、引用与参数

长度使用毫米，角度使用度。草图输入是平面内的 `(u,v)`：

| 平面 | u | v | 正向法线 | offset |
| --- | --- | --- | --- | --- |
| XY | +X | +Y | +Z | 世界 Z 坐标 |
| XZ | +X | +Z | −Y | 世界 Y 坐标 |
| YZ | +Y | +Z | +X | 世界 X 坐标 |

`direction:"positive"` 沿表中正向法线，`negative` 反向。对称拉伸的 `depth` 是总深度。圆弧起止角以输入平面 u 轴为零度，沿 u→v 逆时针。

平面也可传入 `{"reference":{"kind":"surface","id":实际ID},"origin":[x,y,z],"u_axis":[x,y,z]}`，用于已有平面面或基准面。默认原点是世界原点到该平面的垂足；指定原点必须在平面内。基准面的方向和生成几何由 Toolkit 决定，应按查询结果使用。

常用引用：

```json
{"kind":"datum_plane","axis":"x","offset":0}
{"kind":"plane","axis":"z","offset":30}
{"kind":"surface","id":123}
{"kind":"edge","id":456}
{"kind":"axis","id":78}
{"kind":"datum_feature","label":"offset_plane"}
{"kind":"datum_axis_feature","label":"axis"}
```

`plane` 选择实际实体平面面，必须唯一；有多个匹配面时使用查询得到的 `surface` ID。`datum_plane` 的零偏移主平面选择模板中最早的对应基准，避免与 Creo 自动生成的内部基准混淆。非零偏移仍要求唯一。草图/拉伸等特征间用 `label` 引用；标签由小写字母、数字和下划线组成，以字母开头，最多 28 字符。

显式尺寸支持长度、半径、直径、点间距离/水平距离/垂直距离、线间距离、夹角、圆弧角度和椭圆半轴。约束接口包含水平、垂直、重合、点在线上、相切、垂直、等半径、平行、等长、共线；实测包括水平/垂直约束及驱动直径尺寸，其余组合由原生求解器验证。

关系式当前接受简单算术赋值，例如 `d18 = LENGTH / 2`；替换零件当前关系式集合。参数支持数字、布尔值和字符串。

## 验证、恢复与当前边界

每次修改成功后，执行器检查单位、所有原生特征的活动/完整状态及实体状态；保存 `.prt.N` 或 `.asm.N`，擦除该 MCP 零件的内存模型，从实际保存文件重载、重新生成，再对比特征 ID/类型/名称、尺寸值、实体数量、体积和参数。可额外提供 `require_solid`、`volume_mm3`、`volume_tolerance` 断言。体积计算临时使用密度 1，不修改材料。

**默认摘要与分页接口一览。** 以下三个查询接口默认返回 compact 摘要（小体积、可直接整读），需要全量内容时显式请求并按页遍历；依赖旧全量返回的调用方会静默拿到摘要，不会报错：

| 接口 | 默认 | 取全量 |
| --- | --- | --- |
| `creo_list_models` | compact 模型清单摘要 | `detail="full"`，必要时沿 `next_cursor` 分页 |
| `creo_inspect_model` | compact 快照摘要（身份/revision/体积/计数） | `detail="full"` + `section="dimensions"`/`"surfaces"`/`"edges"`/`"features"` 等，沿 `next_cursor` 分页 |
| `creo_capabilities` | compact 能力摘要页 | `detail="full"` + `section="tools"`/`"families"`/`"references"` 等，沿 `next_cursor` 分页 |

通用规则：单页响应预算 32 KiB，超预算会分页或对单条超限项显式标记；出现 `next_cursor` 时保持相同 `detail`/`section` 继续翻页，翻完即 `complete=true`。`creo_inspect_model` 的分页绑定已保存快照，模型改变后游标失效，应重新查询；`creo_capabilities` 的分页绑定进程内约 600 秒冻结快照，过期 cursor 被拒绝并提示重新首查。

`creo_list_session_models` 的 cursor 语义另有两态：不带 `cursor` 调用时实时重新采集会话清单；携带上次返回的 `cursor` 时读取约 10 分钟的冻结快照分页，不反映快照创建后的会话变化。因此"打开/擦除模型后要确认会话现状"时应省略 `cursor` 重新查询；需要稳定遍历时沿用 `cursor`。结果中的 `snapshot_age_seconds`/`expires_in_seconds`/`refresh_guidance` 说明快照年龄与刷新方式；`service_session_changes` 列出本服务自快照以来记录的会话内容变化（跨进程、有界），GUI 手工变化不在其中、未实时复核。`creo_open_file` 成功结果的 `open_file.opened_session_model` 直接提供刚打开模型的单条会话观察（字段与会话枚举条目一致，另含 `observed_at`）；`open_file.loaded_session_models` 提供打开后的有界会话摘要（会话模型数、组件实例数与详情入口），不必立即发起全量枚举。

`creo_list_models` 与 `creo_inspect_model` 默认返回 compact 摘要，保留身份、revision、状态、体积、真实计数和快照时间。需要几何时显式使用 `detail="full"`，可指定 `section="dimensions"`、`"surfaces"`、`"edges"`、`"features"` 等。详情默认每页50条、最多200条，响应预算32 KiB；出现 `next_cursor` 时保持 detail/section 继续分页，模型改变后重新查询。大快照的 `data` 按 section 返回；特征内的尺寸、几何项和草图尺寸分别分页，未知计数为 null，不能当作0。小快照的 full 保留原 inspection/aliases 布局。Python调用方可用 `creo_mechdog.query_client.read_full_model` 收集全部页并重建快照。

`creo_inspect_model` 返回最近已验证的保存快照，snapshot明确不代表实时状态；人工在 Creo 修改后，用 `creo_refresh_model` 获取实况。实时查询不会替换已保存模型的基线，也不会保存或接受人工修改。已有模型修改前会检测模型与记录是否一致；因任务失败或人工修改而不一致时，不应盲目重复提交。失败作业的 inspection 仅在恢复并验证成功时代表恢复模型；失败中间状态另列 failure_inspection，无法取得真实状态时为 null。

恢复失败按实际阶段返回原因：执行器派发前的证据校验拒绝返回 `failed` / `before_native`，在锁内仅释放本次恢复占位；原生执行器可能已开始时仍为 `unknown_outcome` 并保留保护。原生会话指纹拒绝发生在连接之后，不能因消息含 refused 就自动重试。见[恢复契约](docs/MODEL_RECOVERY.md)。[隔离 MCP 契约验收](docs/validation/DEV-040-isolated-contract-2026-10-18.md)已通过，不代表真实 Creo 会话切换、中断、几何或并发恢复已全部验收；剩余范围按台账跟进。

`creo_loft.sections` 和计划中 `op="loft"` 支持草图标签、整数feature_id，以及为客户端兼容接受的纯十进制数字字符串；例如 `[40,"49"]` 归一化为整数ID。归一化后的重复引用被拒绝，不影响其他参数的字符串语义。原生几何与公开客户端验收范围仍分别记录。

现有 MCP 零件任务失败，会尝试从任务开始前的保存文件恢复；只有 `rollback_succeeded` 确认成功才能继续。版本号不随失败增加。辅助进程崩溃、超时或结果不能确认时标记 `unknown_outcome`，保留现场供检查。新零件失败可能留下本任务的部分模型。

未知作业保留 `pending_job`，`creo_get_job` 的 `recovery` 提供执行器身份、断开前检查点及已保存基线；检查点不等于成功，也不自动提交 revision。原生断开有 20 秒 helper 看门狗，只退出自有 helper，不关闭 Creo。`creo_startup_status(retry=true)` 只重新核实通道及安全启动条件，不能解锁或重放未知作业。启动等待区分 `waiting_for_channel` 与 `building_worker`，preparation 为 180 秒，总预算为 180 秒加配置的启动预算；到期仍在执行时说明 in-flight，继续保留保护。状态快照带 `verified_at`、`verification_age_seconds`、`stale`；`creo_session_status` 的独立探针预算为 9 秒，超时返回 `probe_timeout` 和处理指引。

共享启动历史损坏时，仅在核实记录早于本次 Windows 启动、双锁已取得且没有现有 Creo 后，备份原字节并重建启动状态，再由协调器启动 Creo；`startup_recovery` 提供归档与重启依据。同次开机损坏、时钟／会话不确定或备份失败仍返回 `startup_state_unreadable` 和处理说明，已有会话可只读重连。未知任务和模型保护不随启动历史重建而清除，验证范围见[重启恢复记录](docs/validation/BUG-008-reboot-recovery.md)。

目前高层工具覆盖上述常见实体特征，仍有明确范围：

- 持续修改支持本服务创建、登记的零件、钣金模型和装配；用户已在 Creo 打开的未登记模型可通过 `creo_adopt_current_model` 显式接管为受管副本（原件与原会话对象不动，首批独立 part/钣金、mm 单位、无外部依赖；身份按 origin 路径 + 文件哈希 + live 快照证明，不信任显示名）。
- 各类尺寸/约束的复杂组合、极端几何及外部人工修改的自动接管仍需后续扩展。
- 孔为直孔，尚未封装螺纹、沉头、沉孔标准孔；倒角为等距，阵列支持一方向尺寸阵列和原生轴阵列。
- 普通混合支持平行 XY 截面的种子复用及直接创建/追加。随包九个种子覆盖 2/3/4/6 截面的直线和平滑，以及 5 截面平滑；其他数量需显式兼容种子或直接创建并本机验证。直接混合仅支持受管草图、Z 严格递增和默认实体增材。不支持自动增减种子截面、转换连接模式、非平行截面或端点相切/曲率控制。数量上限不代表每种数量都已实测。新零件整体可用原生定位特征移动或旋转。
- 钣金已验证首壁、90° 法兰、高度编辑、展开、折弯回去和平展；其他形状和折弯规则未全部验证。镜像、扫掠、拔模、装配、筋和工程图各自具有明确范围，见能力说明；复杂自由曲面及专业模块仍未完整封装。
- 装配插入源模型的版本快照，源模型后续修改不更新组件；子装配复制尚未开放。
- `creo_create_feature_tree` 可扩展符合本机 SDK 的特征结构，但无法保证所有 PTC 特征类型和选项均可创建。
- 不承诺任意文字描述都自动成功。AI 需要规划有效的轮廓、基准、尺寸和特征顺序；无效几何由 Creo 返回错误。

服务串行执行 Toolkit 操作，后台检测并复用已有会话，无会话时按配置启动；连接确认前拒绝建模提交，不自动关闭 Creo。输出保存在项目运行数据目录内：`models/`（受管模型登记与输出）、`jobs/`（作业请求/结果/日志）、`open_file/`（磁盘打开的幂等意图登记）、`session_erase/`（会话擦除的令牌与意图登记）和 `session_activity.json`（本服务引起的会话内容变化记录）；升级到新版本时保留这些目录，不要手工删除或合并它们。不提供任意命令／代码执行工具，不输出许可服务器内容或修改安装目录。正在交互建模或有模态对话框时，应先处理该会话状态。

## 开发与测试

安装脚本创建虚拟环境、安装锁定依赖、验证/注册随包种子库、读取本机 SDK 生成常量表、编译执行器并生成客户端配置。首次运行或原生源码改变时也会自动重新编译。`native/constants.inc` 由本机 SDK 生成；不随源码分发。源码包含九个项目原创 MIT 种子 PRT，不含 Creo SDK 库、许可内容、虚拟环境、编译二进制或其他本机测试模型。第三方 JSON 头文件附带其原始 MIT 许可。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\test_mcp.py --classic
.\.venv\Scripts\python.exe tools\test_general.py
.\.venv\Scripts\python.exe tools\test_extended.py
.\.venv\Scripts\python.exe tools\test_guards.py
.\.venv\Scripts\python.exe tools\test_v021.py
.\.venv\Scripts\python.exe tools\test_unit.py
```

除输入验证外，上述集成测试会实际连接 Creo 并创建或修改独立测试模型。`test_v021.py` 默认验证启用功能和禁用接口的拒绝行为；禁用接口的拒绝测试不是建模成功证明。日志位于任务 `native.log`/`runner.log`/`job.json` 和 `build/build.log`；证据在 `build/*integration_test.json`。保存目录较长时应缩短项目路径。

Windows 登记文件读取允许共享删除，写入使用单步原子替换；短暂占用最多重试 1 秒，持续失败保留旧登记并报错，不会自动重复原生操作。登记读写压力与并发实机轮询可分别运行 `tools/test_registry_io.py` 和 `tools/test_registry_native.py --readers 3`。Creo 12.4 结果及历史交接记录见 [BUG-002 验证与交接](docs/validation/BUG-002.md)。

实现依据：[PTC 草图特征 Element Tree 文档](https://support.ptc.com/help/creo_toolkit/protoolkit_plus/usascii/creo_toolkit/user_guide/Element_Tree_for_Sketched_Features.html)、本机 Creo 10 Toolkit 头文件与示例、[官方 MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。实际本机建模成功、保存重载成功的记录才证明该路径可用，SDK/许可环境文件存在本身不能证明许可可用。

完成普通放样实机测试后，可生成它的独立摘要；打包会重新生成本地同版本压缩包：

```powershell
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py --interpolation smooth
.\.venv\Scripts\python.exe tools\package.py
```

摘要命令需要已经完成相应的实机测试；打包命令只选择公开源码及文档。`config.json`、`client-config.json`、虚拟环境、构建结果、任务和模型目录已在 `.gitignore` 中排除。
