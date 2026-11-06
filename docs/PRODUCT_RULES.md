# 产品规则（FEAT-063，只读规划器）

2026-11-06：只读规划器软件已完成，开发分支未发布，原生模板未验。

MCP 调用：`creo_plan_product_variant(template_id="box_frame", parameters={})`。
接口只有 template_id 和 parameters；能力快照由服务的 REGISTERED_OPERATIONS 扣除
UNAVAILABLE_OPERATIONS 构造，客户端不能自报启用能力。工具使用 READ 注解。
以下 Python 内核接口用于离线嵌入，能力快照责任仅适用于直接调用内核。

```python
from creo_mechdog.product_rules import build_product_plan

result = build_product_plan(
    "box_frame",
    {"length_mm": 120, "width_mm": 80, "height_mm": 50, "wall_mm": 3},
    {"operations": ["sketch", "extrude"]},
)
assert result["executable"]
operations = result["plan"]["operations"]
```

此调用只读资源和构造数据，不提交作业、不写盘、不获取 Toolkit 锁。
无 job_id/model_id/revision，也不读取当前运行时。executable 只表示结构和调用方能力快照准入。
它不能说明 Creo 已执行或几何已验收。validation.schema=passed，native/saved_reload=not_run。

能力适配最小形状为 {"operations": ["sketch", "extrude"]}，允许额外元数据及操作名称。
调用方负责快照来源与新鲜度；内核不查询运行时。None 或缺 operations 为未知，空列表明确缺能力。
未知或缺能力时 executable=false、plan=null，blocking_items 包含 code 和具体 capability 或未知原因。
operations 非 list[str] 抛 ValueError；禁止把未知快照当作当前版本支持。

首版白名单只有 box_frame；ID 不解析为路径。资源固定在
SOURCE_PATHS.resource_root/examples/product_rules/box_frame.json。
模板版本 1.0.0，schema_version=1，单位 mm/deg，固定 open_rectangular_box_v1 配方。
不执行模板表达式或代码，不接受调用方模板路径。template_sha256 是实际资源原始字节的 SHA256。
声明和配方分离；未知字段、版本、单位、recipe、参数声明均拒绝，不降级猜改。

参数默认 length_mm=100、width_mm=60、height_mm=40、wall_mm=2。
前三项闭区间 [10,1000] mm，壁厚 [0.5,20] mm；省略使用默认值。
只接受 int/float，拒绝 bool、字符串、NaN、Inf、无法表示的巨大整数、额外参数。
L-2t、W-2t、H-t 均须至少 1 mm；错误以带字段/模板上下文的 ValueError 返回。

固定四操作依次为 outer_profile、outer_body、cavity_profile、cavity_cut。
外矩形在 XY/offset=0，以正方向盲拉伸 H；内矩形在 XY/offset=H，
以负方向盲切除 H-t，因此底板厚度 t，顶部开口。
计划经现有 validate_operations 校验，形状为 {"operations": [...]}。
整份返回按 ensure_ascii=False JSON 编码计算 UTF-8 大小，上限 32768 字节；超限报错，不截断操作。

expected_geometry 是预期解析值：体积 LWH-(L-2t)(W-2t)(H-t)，包络 [0,0,0] 到 [L,W,H]。
默认体积 35712 mm³；第二组 120×80×50/t3 为 83508 mm³。
这些值未由 Creo 测量，schema 通过不能替代原生执行、参数回读和保存重载。

运行 `python tools/test_adoption_product_rules.py` 默认在本工作树 build 下创建唯一目录并写 report.json。
可用 `--output <directory>` 指定报告目录；没有 --live，未知参数在执行前拒绝。
报告包含两组尺寸、缺 extrude 阻断、bool 拒绝、UTC 时间、版本、平台及相关源码原始字节 SHA256。
run_checks 不调用外部程序；CLI 只读 Git 记录 commit/dirty，无法读取时显式记录未知。
report.json 使用独占创建；已有同名报告时拒绝，保留原证据。

MCP 工具已注册；开发分支工具总数 101，原生操作数量不变。实现和固定 JSON 已纳入 server
源码身份；递归源码分发白名单已包含二者。回归从独立源码副本导入并运行默认规划，
证明资源定位独立于原工作树；尚未进行全新环境安装或原生模板验收。
见 [验收记录](development/ALPHAI-D02-ACCEPTANCE.md)。
