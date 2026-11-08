# FEAT-014 / DEV-074 钣金成形类路线 SDK 勘察与实机探针（2026-11-08）

## 结论摘要

| 目标项 | 结论 | 依据 |
| --- | --- | --- |
| corner relief（折边特征内 `PRO_E_SMT_CORNER_RELIEF`） | **不可用** | 矩形 3×3、矩形 1×1、`PARAM` 默认三变体均 create 后再生失败（`toolkit_code=-1`）并回滚；同一条边的 `miter_cuts` 对照成功 |
| 百叶 / 成形（`PRO_FEAT_SMT_SKETCH_FORM`） | **本轮不可用** | 三种元素树变体（基准面草图、壁面草图、壁面草图+`PRO_E_BODY`）均在 `ProFeatureWithoptionsCreate` 返回 `-1`，回滚 |
| hem / jog | **不可用** | 本机 Creo 12.4 SDK 无任何 Hem/Jog 头文件，`ProFeatType.h` 无对应特征常量；只存在 `text\smt\flange_shapes` 的截面形状 |
| 格栅（现有 cut） | **本轮未取证** | 三种截面/深度组合均报 “removes no material”，体积不变；与 BUG-046 的 −100 mm³ 正证据矛盾，判定为驱动/截面配置问题，不据此改写既有 cut 口径 |
| 凸台 / 铰链 / 门板耳 | **不可用** | 引用 H05 反证，不重复长探针 |

**公开面零变化**：本轮未新增工具或参数，公开工具保持 **107**；corner relief 的探针代码（原生元素写入 + 邻接保护放行 + schema/server/投影字段）在三次失败后全部回退，门禁不放宽。原始数值见 [evidence.json](evidence.json)。

## 环境与源码身份

- Windows x64；Creo 12.4.0.0 由用户手工启动并确认可用；`config.json` `auto_start_creo=false`；mm；单通道串行，一次只提交一个作业。
- worktree `e:\Projects\MCP_CREO_MechDog-d074`，分支 `codex/DEV-074-forming`，探针时 HEAD `2aab4af`（工作树仅本轮临时探针改动，结束前已 `git checkout` 回退）。
- 本轮未启动、关闭或重启 Creo，未清 unknown 保护，未做故障注入，未重提已接受作业；busy/unknown 未出现。
- `bridge.py build` 退出 0（回退后再次构建仍为 0），执行器 `build/creo_worker.exe` 由本轮源码生成。

## 1. SDK 勘察（只按头文件实际声明）

头文件目录 `C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit\includes`，`ProSmt*` 共 26 个头文件：`ProSmtBend`、`ProSmtBendBack`、`ProSmtConnectRip`、`ProSmtCornerRelief`、`ProSmtDrvSurf`、`ProSmtEdgeBend`、`ProSmtEdgeRip`、`ProSmtEditBend`、`ProSmtEditBendRelief`、`ProSmtEditCornerRelief`、`ProSmtEditCornerSeam`、`ProSmtExtendWall`、`ProSmtFlangeWall`、`ProSmtFlattenForm`、`ProSmtFlatWall`、`ProSmtForm`、`ProSmtJoinWalls`、`ProSmtMergeWalls`、`ProSmtPunchQuilt`、`ProSmtRecognition`、`ProSmtRegularRip`、`ProSmtShell`、`ProSmtSketchForm`、`ProSmtSplitArea`、`ProSmtSurfaceRip`、`ProSmtTwist`。**没有** `ProSmtWall.h`、**没有** 任何 Hem/Jog 头。

- **`ProSmtFlangeWall.h`（`PRO_FEAT_WALL` + `PRO_SMT_WALL_TYPE_FLANGE=17`）**：折边同特征内并列三类角部/端部入口——`PRO_E_SMT_BEND_RELIEF_SIDE1/SIDE2`（`ProBendRlfType` NONE 0/RIP 1/STRETCH 2/RECTANGULAR 3/OBROUND 4/PARAM 5）、`PRO_E_SMT_CORNER_RELIEF`（`TYPE`+`WIDTH(_TYPE/_VAL)`+`DEPTH(_TYPE/_VAL)`，`ProCornerRelType`：V_NOTCH 0、CIRCULAR 1、RECTANGULAR 2、OBROUND 3、NO 5、PARAM 6、SQUARE 7、NORMAL 8；尺寸类型 `PRO_DIM_ENTER=-4`、`PRO_DIM_DEF_CRN_REL_WIDTH=-10`、`PRO_DIM_DEF_CRN_REL_DEPTH=-11`）、`PRO_E_SMT_MTR_CUTS`（已交付路线）、`PRO_E_SMT_CORNERS_ARR`/`PRO_E_SMT_EDGE_RIP`（`ProEdgeRipType` OPEN 0x10/BLIND 0x20/MITER_CUT 0x30/OVERLAP 0x40/PARAM 0x50）。
- **`ProSmtCornerRelief.h`（`PRO_FEAT_SMT_CRN_REL=1098`）**：独立角部释放特征，必须给 `PRO_E_CORNER_RELIEF_REF_FLAT`（平面）+ `PRO_E_CORNER_RELIEF_REF_BND_1/2`（两个折弯圆柱面）；`ProCrnRelRefType` 3_SURFACES 0 / ALL 1；`ProCrnRelCrState` IN_FORMED 0 / IN_UNBEND_ONLY 1。**未探针**：需要三面引用，本轮先验的同特征路线已失败。
- **`ProSmtEditCornerRelief.h`（`PRO_FEAT_EDIT_CORNER_RELIEF`）**：`PRO_E_EDIT_CORNER_RELIEF_SEL_OPT/GEOMS` + 同一 `PRO_E_SMT_CORNER_RELIEF` 定义，`ROTATE` 0–360、`OFFSET`，仅改既有释放。
- **`ProSmtSketchForm.h`（`PRO_FEAT_SMT_SKETCH_FORM=1270`）**：草图成形，**不需要工具件**；`PRO_E_STD_SECTION`、`PRO_E_SKETCH_FORM_TYPE`（`ProSketchFormType` PUNCH 1 / PIERCING 2）、`PRO_E_SKETCH_FORM_DEPTH_PUNCH` / `_PIERCING`、`PRO_E_SKETCH_FORM_DIR`、`PRO_E_FORM_PUNCH_MATERIAL_SIDE`、`PRO_E_SMT_FILLET_INTERSECT/QUILT`、`PRO_E_SMT_TRIM_FORM_SIDES`。
- **`ProSmtForm.h`（`PRO_FEAT_GEN_MERGE`）**：工具件成形，`PRO_E_GMRG_SMT_TYPE` = `PRO_GEN_MERGE_SMT_TYPE_FORM_PUNCH=1` / `FORM_DIE=2`，必须引用**参考零件模型** `PRO_E_DSF_REF_MDL`/`PRO_E_DSF_SEL_REF_MDL`（冲头/凹模件）+ `PRO_E_FORM_TOOL_CSYS`。这是“必须依赖工具件”的路线。
- **`ProSmtPunchQuilt.h`（`PRO_FEAT_PUNCH_QUILT`）**：`PRO_E_FORM_PUNCH_QUILT` + `PRO_E_FORM_PUNCH_SIDE`（`ProSmtSurfType` FACE 2/OFFSET 3）+ `PRO_E_FORM_PUNCH_MATERIAL_SIDE`（OUTSIDE 0/INSIDE 1）+ `PRO_E_FORM_PUNCH_HIDE_QUILT`。
- **`ProSmtFlattenForm.h`（`PRO_FEAT_FLATTEN`）**：展平/取消展平，与成形引用相关但非成形创建。
- **hem / jog**：`ProFeatType.h` 全文无 HEM/JOG 常量；SDK 无对应 `.h`。Creo 侧只以**折边截面形状**存在：`Common Files\text\smt\flange_shapes` 的 `c_hem.sec`、`duck_hem.sec`、`flushed_hem.sec`、`joggle_hem.sec`、`open_hem.sec`、`z_hem.sec`（另有 `arc_wall.sec`、`i_wall.sec`、`s_wall.sec`）。当前 flange 实现只写单线截面，无法表达多实体 hem 截面。
- 另见 `PRO_FEAT_CUT_SMT=955`（钣金专用 cut），本机 SDK 无对应元素树文档，未尝试。

## 2. 实机探针

### 2a. corner relief（折边特征内元素；探针期临时实现，已回退）

夹具：185×232×1 首壁 → `+x` 自由折边（h80/R2.54，体积 60 945.29123405193 mm³，rev 2）→ 在 `-y` 顶边（id 197，端点 `[0,-232,0.5]`–`[181.46,-232,0.5]`，跨度 181.46 mm，端部邻接折弯）再建一道折边。

| 变体 | job | 结果 | revision | 体积 | 增量 | 重载 |
| --- | --- | --- | --- | --- | --- | --- |
| 矩形 3×3（BLIND） | `62d1c9bf…` | failed `-1` | 2→2 | 60 945.291234 | 0 | false |
| 矩形 1×1（BLIND） | `15e7befa…` | failed `-1` | 2→2 | 60 945.291234 | 0 | false |
| `PARAM` 默认（`PRO_CORNER_RELIEF_PARAM`，宽深取零件默认 −10/−11） | `cbba5b26…` | failed `-1` | 2→2 | 60 945.291234 | 0 | false |
| **`miter_cuts{1,1}` 对照** | `8b38c051…` | **succeeded** | 2→**3** | **75 014.2426845472** | **+14 068.95145049526** | **true** |

三次失败均 `failed_stage=execute_sheetmetal_flange`、`message="Regeneration produced a failed, suppressed or incomplete feature"`、`rollback_succeeded=true`，`corner_relief` 回显为 null（未进入建立后的回读），`adjacent_bend_ends_allowed` 亦为 null（取证在失败记录的 `flange_failure_evidence`）。对照例证明同一夹具、同一条边、同一作业序列可以成功——失败特定于角部释放请求，而不是模型/选边/驱动。

**结论：不可用。** 同特征 `PRO_E_SMT_CORNER_RELIEF` 不解除该形状的再生失败，也不能替代 `miter_cuts`。探针实现（原生写入/回读/保护放行 + schema/server/投影字段）已全部回退，`adjacent_bend_ends` 仍只由 `miter_cuts` 放行。

未做（本轮停止条件）：独立 `PRO_FEAT_SMT_CRN_REL`（平面 + 两个折弯圆柱面三引用）路线；四壁盒真实角部（两条折弯相交）上的释放几何。

### 2b. 百叶 / 成形（`PRO_FEAT_SMT_SKETCH_FORM`，无需工具件）

夹具：`native_planar` 100×60×1 平壁（6 000 mm³，rev 2）→ 10×6 mm 矩形草图 → `feature_tree` 提交成形元素树（`PRO_E_STD_SECTION` 引用草图、`PRO_E_SKETCH_FORM_TYPE=1`、深度 2 mm、`PRO_E_SKETCH_FORM_DIR=1`，含 `PRO_E_SMT_FILLET_INTERSECT` 与 `PRO_E_SMT_TRIM_FORM_SIDES`）。

| 变体 | 草图支撑 | 结果 |
| --- | --- | --- |
| `punch_top` | XY 基准面偏移 1.0 | failed：`execute_feature_tree`，`ProFeatureWithoptionsCreate=-1`，rev 2→2，6 000 mm³，回滚 |
| `punch_surface` | 首壁顶面（surface 84） | 同上 |
| `punch_body` | 顶面 + `PRO_E_BODY`（SELECTED + 默认体） | 同上 |

三次均 `toolkit_code=-1`、元素错误列表为空、`rollback_succeeded=true`，模型与体积不变。**结论：本轮不可用**；`ProSmtSketchForm` 的树是否还需其它强制元素（如截面方法/驱动面选择）未定，按“连续三次失败即停”记录，不宣称成形能力。工具件路线（`ProSmtForm` + 参考零件）未尝试，因需另建冲头零件与装配引用。

### 2c. hem / jog

无 SDK 入口（见 §1），未做元素试探。hem/jog 若要走通，只能把折边截面换成库存 `*_hem.sec` 的多段（线+弧）截面——现有 flange 只写单线，属新实现工作量，本轮不做。**结论：不可用（附 API 反证）。**

### 2d. 格栅（既有 cut）

夹具：185×232×1 首壁 + `+x` 折边 h20（47 025.29123380686 mm³）→ XY 草图 3×3 个 6×4 矩形（期望去料 216 mm³）→ `extrude{mode:"cut"}`。

| 变体 | 结果 |
| --- | --- |
| 3×3 孔、`through_all`、symmetric | failed：“Extrude cut removes no material”，体积 47 025.29123380686 不变，回滚 |
| 1 孔、`through_all`、positive | 同上 |
| 1 孔、blind 5 mm、symmetric、草图在中面 | 同上 |

三次均未去料。**结论：本轮未取证，不改变既有口径。** BUG-046 曾记录钣金件上 cut 成功（−100 mm³），因此这里是驱动/截面配置问题（草图所在基准面与首壁转换体的关系、`through_all` 方向、或截面被判定为空），不是“钣金件不能 cut”的证据；格栅仍只是“可能的一组 cut 孔”，不作为已交付能力。

附带发现：9 孔草图的 `creo_get_job detail="full"` 返回 `Query metadata exceeds response budget`，需用 `detail="compact"` 轮询。

### 2e. 凸台 / 铰链 / 门板耳

直接引用 [H05 反证](feat014-h05-sheetmetal-solid-add-2026-11-07/EVIDENCE.md)：实体增料 `-1`；`new_body` 只出独立体；正向 union `-1`；反向 union 吞并钣金身份（壁面候选边 8→0、`unbend` 失败）。**不可用，门禁保持**，本轮未重复探针。

## 3. 能力与门禁

- 公开工具 **107 → 107**（无新增）；`creo_sheetmetal_flange` 参数集合与元素树不变。
- `adjacent_bend_ends` 仍为创建前拒绝，唯一放行方式仍是显式 `miter_cuts`。
- 以下仍未交付、且本轮无新增通道：corner relief（含独立特征路线）、百叶/成形、hem、jog、格栅孔、凸台/铰链/门板耳。

## 4. 未覆盖

独立 `PRO_FEAT_SMT_CRN_REL`（三面引用）；`ProSmtForm` 工具件路线；`ProSmtPunchQuilt`；hem/jog 多段截面；`PRO_FEAT_CUT_SMT`；Creo 9/10；非 mm；其他板厚/半径；四壁真实相交角部上的释放几何；WorkBuddy 黑盒验收。
