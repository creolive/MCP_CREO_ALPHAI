# MCP_CREO_MechDog 0.18.3 版本说明

发布日期：2026-11-07。性质：PATCH，**用户指定编号的例外**：本版新增公开工具，按项目语义化版本约定应为 MINOR，用户明确指定按 0.18.3 发布，后续版本规则不变。公开工具数量 **102→104**：新增 `creo_surface_loft`（两截面直纹曲面放样）与只读 `creo_measure_surface_group`（曲面组级缝合测量）；`creo_quilt_merge` 仍由 `UNAVAILABLE_OPERATIONS` 隐藏，不计入。

## 本版变更

- **FEAT-058 / H01：非零 `origin` 大跨度钣金改型修复。** `native/planar_wall.cpp` 不再用 `fabs()` 猜测坐标尺寸方向，而是用 `ProSecdimReferencesGet` 实测每个尺寸的引用端点与方向后写入有符号值（负值即翻到截面轴另一侧），读回按绝对值比较；新增定位矩阵、角点、尺寸引用与包络诊断，体积/包络/子特征/身份守卫与 `origin=[0,0]` 路径不变。Creo 12.4.0.0 实机 14/14：零/正/负/混合 origin、跨/不跨轴、恒等/缩小/放大/连续改型、XY/XZ/YZ、正负厚度方向、同计划、跨计划与 save/reload 后 resize 均为预期体积并保存重载成功。证据：[FEAT-058-H01-2026-11-07](validation/FEAT-058-H01-2026-11-07/SUMMARY.md)。
- **FEAT-009 / H02：两截面直纹曲面放样 `surface_loft` 与公开工具 `creo_surface_loft`。** 按 G5 §2.1 的 `Probbl.h` 裸树以 `PRO_FEAT_CR_INCOMPLETE_FEAT` 创建、`ProFeatureElemtreeExtract` 抽取、`ProFeatureWithoptionsRedefine` 再生成，由内核补齐表面类型与切线条件；只接受恰好两条单曲线草图截面、`straight`，产出 1 个开放 datum-surface quilt，不产生实体。实机 quilt_id 61、面积 800.0 mm²、`quilt_closed_native=open`、`has_solid=false`、保存重载 id/面积不变；x=20 修剪两侧各 400.0 mm²；2 mm 加厚 1599.9999999999995 mm³。证据：[FEAT-009-H02-2026-11-07](validation/FEAT-009-H02-2026-11-07/SUMMARY.md)。
- **FEAT-039 / H04：曲面组级四态测量，新增 `creo_measure_surface_group`。** 新原生 `native/surface_group.cpp` 依据 `ProQuiltSurfaceVisit`、`ProContourEdgeVisit`、`ProEdgeTessellationGet` 与面网格/`ProSurfaceParamEval` 等给出 `open_edges`、`gap_max_mm`、`overlap_area_mm2` 与 `closed`/`open`/`micro_gap`/`overlap` 四态，每个值带 `*_status`，不用面积或体积反推。实机四例 42 项检查通过：共边 `closed`/gap 0、0.005 mm `micro_gap`、0.5 mm `open`、0.5 mm 重叠 `overlap`（`buried_boundary_edges=2`，面积低于采样分辨率时标 `area_below_sample_resolution`）。证据：[feat039-h04-surface-group-2026-11-07](validation/feat039-h04-surface-group-2026-11-07/EVIDENCE.md)。
- **FEAT-039 / H06：`surface_trim` 保留侧真实几何。** `native/surface_measure.h::quilt_region_geometry` 用修剪后面片面积加权给出真实形心、轴对齐 bbox 与世界方向；`surface_trim` 新增 `target_centroid`/`kept_centroid`/`target_bbox_mm`/`kept_bbox_mm`/`target_direction`/`kept_direction`/`centroid_delta_mm` 与各自状态，非平面区域不冒充方向、未知单位保持 null。实机 6 个 job、41 项检查通过：基准面/quilt 工具 × one/two 四组形心分居工具两侧（+17.5/−2.5 mm）、保存重载成功、失败用例回滚且 revision 1→1。证据：[feat039-h06-kept-side-2026-11-07](validation/feat039-h06-kept-side-2026-11-07/EVIDENCE.md)。
- **FEAT-039 / H03：quilt merge 反证，门禁保持。** 按 H02 的 INCOMPLETE→extract→redefine 路线重试两片共边填充 join：创建/抽取/`ProErrorlist` 均为 0，内核自行补 `PRO_E_SRF_MRG_QUILT_SIDE=1`/`PRO_E_SRF_MRG_TYPE=1`，redefine 后 ACTIVE，但 quilt 访问 -4、0 个 quilt、4 个 `PRO_SURFACE`，与旧一次性创建逐项相同。`quilt_merge` 继续不可用，不声称瓶底可实体化。证据：[feat039-h03-quilt-merge-incomplete-2026-11-07](validation/feat039-h03-quilt-merge-incomplete-2026-11-07/EVIDENCE.md)。
- **DEV-072 / DEV-074 / H11：远端发布独立核对。** 对 `v0.17.3`–`v0.18.2` 五个已发布版本执行 `tools/check_release_assets.py --tag` 与 `gh api` 只读核对：附注标签均指向 main 合并提交、Release 非草稿、四附件齐全，20 个文件本地实算 SHA256 与 sidecar、API digest 三方一致。v0.17.3 body 缺附件 SHA256 与独立环境段的历史瑕疵已记录，按规则不改旧标签/附件。证据：[POSTCHECK-RELEASE](validation/feedback-0.17.4-2026-11-07/POSTCHECK-RELEASE.md)。
- **DEV-066 / DEV-074 / H13：证据工具无 Git 化收尾。** 剩余 17 个仍自行调用 `git rev-parse/ls-files/status` 的证据/驱动函数迁入 `source_provenance.local_provenance`：有 Git 时行为不变并追加 `git_status`，缺 Git/非仓库时 `commit`/`branch`/`dirty` 为 null、来源哈希退化为目录遍历，不伪造身份。与 main 的 `git_evidence` 路线在合并提交 `7d18fca` 中合并。证据：[DEV-074-HANDOFF](development/DEV-074-HANDOFF.md)、[DEV-074](work-items/DEV-074.md)。

## 验收摘要

- 离线全量门禁：`tools/dev_check.py --work-item DEV-074` → `success=true`，单测 **2916 项，0 失败 0 错误**；风格存量基线 24 条 lint / 12 个未格式化文件，无新增；源码指纹 `2aeceda9d390ad60842dc4d2d3adfc25c4ea643b615dd1e20d28dd8269d09120`（dirty 工作树，提交 `7d18fca`）。
- 原生编译：`bridge.py build` → 退出 0，生成 `build/creo_worker.exe`。
- Creo 12.4.0.0 实机：H01 14/14、H02 22/22 检查、H04 42 项检查、H06 41 项检查（详见上列证据目录）。
- H03 反证：两次尝试均为 4 面 0 quilt，未产生可测量结果 quilt。
- 打包：种子包 24 个文件、9 个种子，重建两次摘要一致；源码包 1529 个文件；四附件闸门通过（两个 ZIP 与两个 sidecar）。
- 源码包解压全量单测：解压到短路径 `C:\i0183\MCP_CREO_MechDog`（无 `.git/`，自建 venv 安装 `requirements.txt` 后 `pip install --no-deps -e .`），`python -m unittest discover -s tests` → **2916 项，0 失败 0 错误，3 项 SDK 检查跳过**。首次解压到较长 TEMP 路径时 `test_dev040_blackbox_fixture` 触发 Windows 路径长度限制，改用短路径后全通过，未改产品代码。

## 兼容性与升级

- 服务标识、MCP 工具名（除新增两个）、既有计划 schema 与种子目录格式不变；无需修改客户端配置。
- 新工具为增量：`creo_surface_loft` 只接受两截面、`straight`；`creo_measure_surface_group` 只读，不改变模型 revision。
- `surface_trim` 新增字段为增量，旧字段保留；状态不可用时值为 null，历史 job 不回填。
- 种子包与源码包按同一版本成对发布，`seed_manifest.json` 的 `compatible_server_version` 为 `0.18.3`；种子文件本身未变，0.18.3 服务可读取旧 0.18.2 种子包，发布附件以新版为准。

## 环境

- Windows x64；Creo 12.4.0.0；匹配的 Creo Toolkit SDK；MSVC x64 构建工具；Python 3.12.14（`.venv`）。
- 上述实机证据均为本机单会话串行通道取得，`auto_start_creo=false`，未启动/关闭 Creo、未清 unknown 保护、未做故障注入。

## 未测范围与未完成项

- **未完成**：H05 钣金附着增料/百叶/格栅/凸台/铰链/耳与 corner relief；H07 独立 quilt offset；H08 曲面边圆角/曲率梳/斑马纹；H09 任意非平面填充；H10 五爪整链（多 quilt 实体化/加厚、开口面与 0.3 壁厚）；H12 BUG-115 新诊断的 MCP 实机复验与保存重载；H03 逐片缝合（门禁仍不可用）。
- **H01**：未做字面“会话擦除后重载”（受管模型 erase 被拒绝）；`tools/test_adoption_planar_wall.py --live` 77 项因通道被其它客户端占用未跑完；Creo 9/10 未测。
- **H02**：未验证 ≥3 截面、smooth/闭合、相切/曲率连续性、非平行/扭转/圆弧截面；同一模型先加厚再修剪返回 -1，验收顺序改为 trim 在前或独立模型。
- **H04/H06**：未测 Creo 9/10、非 mm 单位、多面/非平面成员、闭合壳体组；重叠面积为采样估计；`surface_trim` 特征标签下游引用仍为 -4。
- **H03 排查遗留**：本批期间留下一个 `unknown_outcome` 作业（模型 `35576f45…`），按用户决定由用户手动处理 Creo 会话；本版未清除该保护。
- **发布核对**：API asset-ID 作为 `browser_download_url` 失败回退的触发路径仍未做故障注入；v0.17.3 body 的历史瑕疵按规则不改旧发布。
- **Creo 9/10 与 WorkBuddy**：本机无 Creo 9 SDK，Creo 10 未复测；WorkBuddy 公开 MCP 黑盒未执行。

## 附件

四个附件（文件名与完整 SHA256）：

- `MCP_CREO_MechDog-0.18.3-source.zip`（8 650 655 字节）：`042959b54dab8de15044b9991f7defc3abce476c0cee8228997f7f00979b45bb`
- `MCP_CREO_MechDog-0.18.3-source.zip.sha256`（101 字节）：`de4e08b40a4127d483fb4f93d93d62d726c7a2d7f5d8644ebaee1af0678df657`
- `MCP_CREO_MechDog-0.18.3-seed-library.zip`（493 442 字节）：`7325485f26201c0242a315e7aa0291714a3de81e852eccbba6e60f6288831102`
- `MCP_CREO_MechDog-0.18.3-seed-library.zip.sha256`（107 字节）：`06b9ba48b97a240ce4d784e22ee69851f0305b8ac835642a8b77867de165ba6b`

发布核对与逐 ID 状态见 [RELEASE-0.18.3](validation/RELEASE-0.18.3.md)。
