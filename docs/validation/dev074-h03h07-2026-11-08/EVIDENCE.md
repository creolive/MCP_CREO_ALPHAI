# DEV-074 H03 / H07 实机证据（Creo 12.4.0.0，2026-11-08）

环境：本机 Windows x64、Creo 12.4.0.0（release numeric 44）、匹配 Toolkit SDK；Creo 由用户手工启动，本轮未启动/关闭 Creo、未清 unknown 保护、未故障注入。所有作业经公开 MCP 工具串行提交，一次受理后只轮询，不重试。

源码状态：分支 `codex/DEV-074-forming`；本轮改动 `native/quilt_merge.cpp`、`native/quilt_query.h`、`src/creo_mechdog/capabilities.py`（详见提交）。`bridge.py build` 退出 0；最终构建下重新跑过 H03 验收作业。

## H03：`quilt_merge` 结果 quilt 归属修复（已交付）

### 机理（新发现）

`ProMerge.h` 数组树创建的特征 `feature_status=0`（ACTIVE），但 `ProFeatureGeomitemVisit(PRO_QUILT)` 返回 **-4**、`quilt_item_ids=[]`，同时拥有 4 个 `PRO_SURFACE`（132/134/136/138）。本轮改用 `ProSurfaceQuiltGet` + `ProQuiltIdGet` 探测“成员面所属 quilt”，并对比合并前后目标 quilt 的面积，得到结论：内核把第二片 **join 进目标 quilt**，目标面积 400 → 800 mm²，工具 quilt 变为不可测（`area_mm2=null`，`ProContourAreaEval=-4`）。因此旧实现“必须拥有单个 PRO_QUILT 项”的判据是错误的，与树本身无关。

### 新判据（`native/quilt_merge.cpp`）

`result_quilt_source` 逐级解析，全部来自实测：

1. `feature_quilt_geomitem`：特征拥有恰好 1 个 `PRO_QUILT` 项（历史路径）。
2. `member_surface_quilt`：`native/quilt_query.h::feature_member_surface_quilt` 用 `ProSurfaceQuiltGet` 在特征拥有的面里找所属 quilt。
3. `retrimmed_target_quilt`：重新测量目标 quilt，只有面积**严格增长**（`> target_before + 1e-6`）才认作结果；静默 no-op 面积不变，仍判失败并回滚。

### 实机结果

两片 20×20 共面填充（quilt 82 / 127，各 400 mm²）→ `creo_quilt_merge`：

| 项 | 值 |
| --- | --- |
| job | `6a3facb773e44bfca8492e482deacb5b`（最终构建复跑；首轮 `8c1cd77b…` 字段相同） |
| `result_quilt_id` | 82（目标） |
| `result_quilt_source` | `retrimmed_target_quilt` |
| `area_mm2` / `input_area_mm2` | 800.0 / 800.0 |
| `closed` | false（`ProQuiltVolumeEval=-18`，开放） |
| `feature_status` / `feature_id` | 0 / 129 |
| `saved_file_reloaded_and_verified` | true，revision 2 |
| `quilt_item_ids` / `surface_item_ids` | [] / 4 |

后续：同模型 2 mm `thicken`（job `1449c18b68ef46199bdf24bd165a92ef`）成功，body bbox `[[0,0,−1],[40,20,1]]`、6 面，证明结果 quilt 可被下游消费。

负例（第二片右移 2 mm，不相邻）：`ProFeatureWithoptionsCreate` 返回 **-1**，作业失败并回滚，两片仍各 400 mm²、revision 1→1（`h03_merge_followup.json`）。

面级引用（`PRO_E_SRF_MRG_QUILT_REF` 指向 `PRO_SURFACE`）不是新路线：创建阶段直接 **-1**，两片 quilt 不变（`h03_merge_tree_probe.json`）。

公开工具数：106 → **107**（`creo_quilt_merge` 重新出现在 MCP 面；`capabilities.UNAVAILABLE_OPERATIONS` 只保留 `surface_boundary_fill`）。

### 边界

只支持 JOIN、恰好两片、必须真实接触或相交；不提供容差/缝隙参数；`INTERSECT`、三片以上、链式合并、闭合壳体与瓶底整链未验收。工具 quilt 在合并后留下不可测的悬空记录属内核行为，不在本修复范围。

## H07：独立 quilt 偏置仍不可用（门禁保持）

### 路线 1：文档化 Offset Geometry（`ProFlexOffset.h`）

`PRO_FEAT_FLX_OGF`（1263）的完整树：`PRO_E_STD_SURF_COLLECTION_APPL`（源面集合）+ `PRO_E_OGF_OFFSET_VAL=5.0` + `PRO_E_OGF_DIR_OPT=1` + `ProFlxmdlOpts.h` 的 mandatory 选项（`TRF_SEL_ATT_GEOM`、`ATTACH_GEOM`、`CR_RND_GEOM`、`PROPAGATE_TANGENCY`、`DFLT_CONDITIONS`、`MAINTAIN_TOPO`）。

- 完整 create：V1（面集合）与 V2（quilt 选择）均 **-1**（`h07_ogf_complete.json`）。
- `PRO_FEAT_CR_INCOMPLETE_FEAT` 骨架：create=**0**、extract=**0**、36 元素；内核补齐 `PRO_E_FLEX_OPTS_CMPND`（`5763=0`、`5473=0`、`5474=1` 即 ATTACH_GEOM=YES、`5475=1`、`5476=0`、`5612=0`、`5613=0`、`5152` SOL_INDEX、`5536=0` 等）。说明缺的不是元素本身，而是再生前的补全（`h07_ogf_incomplete_create.json`）。
- 用 extract 树 redefine（CompleteFeature）：attach=0 与 attach=1 两种配置均 **-1**，无 quilt/面几何，作业失败回滚（`h07_ogf_incomplete_redefine.json`）。

结论：`ProFlxmdlOpts.h` 虽把 OGF 元素树写全，但该树在本机不能再生为偏置面/quilt，`PRO_E_FLEX_SOL_INDEX` 也被文档标为 Toolkit 不可设置。该路线判定不成立。

### 路线 2：SDK 其它创建入口

`ProQuilt.h` 只有查询；`ProSurfaceQuiltGet` 只回答归属；`ProQuiltdata.h` 是数据结构；`ProUnifySurf.h` 是“Unify Surfaces”（面区域），`ProSurfReg.h` 是拆分曲面；`ProMerge.h` 只描述面合并树。UI 命令 `ProCmdFtMerge` / `ProCmdSurfMerge` 存在于 `xtop.exe` 字符串表，但面板路线需要已加载的驻留选择回调（`blend_callback` 未在本会话加载，`callback_result.json` 不存在），且 H03 已在 API 层解决合并需求，本轮未启动面板探针。

### 路线 3：复制 + 平移（公开 `creo_geometry_transform`）

40×20 平面 loft（quilt 61，800 mm²）用 `references=[quilt 61]`、`translation=[0,5,0]`、`keep_original=true`：

| 项 | 值 |
| --- | --- |
| 作业 | succeeded，`saved_file_reloaded_and_verified=true` |
| 新 quilt | 94，1 面，面积 800.0 mm²，bbox `y∈[5,5]` |
| 源 quilt | 61 保留，面积/位置不变 |
| 与源面距离 | 5.000 mm（沿法向平移） |

同一命令沿面内方向平移（`[0,0,5]`）时新 quilt 与源面共面（距离 0），说明这是**平移副本**：仅对平面源等价于等距偏置，曲线源会得到平移副本而非等距面。因此不新增 `quilt_offset`，`surface_trim.offset_mm/offset_side` 门禁保持。

## 证据文件（SHA256）

| 文件 | SHA256 |
| --- | --- |
| `h03_merge_live.json` | `9A6F58EA3295BE4C4CCB6A4DAF8A83D913064A53920C48A311E866D57B606984` |
| `h03_merge_followup.json` | `F8D8F445B3FF27699CF1CD28240544D8C33B8399E960D2139A36CBEDD9A61605` |
| `h03_merge_tree_probe.json` | `187A2BBA522BB68FB1FA06410331650E8F7E919A2D12725A45BCBAF77BBBEC54` |
| `h07_ogf_complete.json` | `B0DAA0A8F632D5A17112654E9F9389FED7FA98A58585D2F24E7CEFC055F74C63` |
| `h07_ogf_incomplete_create.json` | `35EAE7FD83C24E46F4F6D0B7873393AC31E04DC9417163C23DA4ED70331FBA15` |
| `h07_ogf_incomplete_redefine.json` | `A9A366708D2547885B9B3E827CE6D5FE47329A1E02449B506B385B54CD95B2DA` |
| `h07_copy_translate.json` | `5AE9D37FA0151AD762C169EDBB3F551C1D6BD792DC4E2D07962492575015317A` |

说明：以上 JSON 以 LF 行尾保存，哈希对提交字节计算。

## 未覆盖

- H03：`INTERSECT` 合并、三片以上/链式、闭合壳体、整体实体化、非 mm 单位、Creo 9/10、失败回滚的其它分支。
- H07：非 mm 单位、弯曲源 quilt 的“复制+平移”读数、面板命令路线（驻留回调未加载，未执行）、Creo 9/10。
- 两项均未做 WorkBuddy 黑盒验收。
