# DEV-074 H10：五爪整瓶曲面链整链实机验收（Creo 12.4.0.0，2026-11-08）

环境：本机 Windows x64、Creo 12.4.0.0（release numeric 44）、匹配 Toolkit SDK；Creo 由用户手工启动，本轮未启动/关闭 Creo、未清 unknown 保护、未故障注入。所有作业经公开 MCP 工具串行提交（`tools/test_five_claw_bottle.py --live`），一次受理后只轮询，不重试、不重提；通道未出现 busy / unknown_outcome。

源码：分支 `codex/DEV-074-forming`，起点 `2945baf`；本轮只新增验收驱动与文档，**原生代码零改动**，`bridge.py build` 退出 0。公开工具数 107。

## 几何定义与解析口径

| 部件 | 构造 | 解析面积 |
| --- | --- | --- |
| 筒身 `body_tube` | R20 圆草图 → `extrude{mode=surface}` 高 40 | 2π·20·40 = 5026.548245743669 mm² |
| 五爪 `petal0..4` | 每条 72° 扇形直纹放样：z=0 处 R20 圆弧 → z=−10 处 R8 圆弧 | π(20+8)·√(12²+10²) = 1374.0508882537029 mm²（每爪 274.81017765074057） |
| 瓶底 `foot_disc` | z=−10 处 R8 圆 → `surface_fill` | π·8² = 201.06192982974676 mm² |
| 瓶盖 `top_cap` | z=40 处 R20 圆 → `surface_fill` | π·20² = 1256.6370614359173 mm² |
| 合并后闭合壳体 | 以上 8 片逐片 `quilt_merge` | 7858.298125263036 mm² |
| 实体化体积 | 圆柱 + 圆台 | π·20²·40 + π·10/3·(20²+20·8+8²) = 56799.99517690347 mm³ |

每条接缝都是**整段重合边**：相邻爪共享一条径向直线，瓶底整圆与五条爪底弧重合，筒身下圆与五条爪顶弧重合、上圆与瓶盖边界重合。因此合并只按实测面积增长判定，不引入容差。

## 1. 构造：逐片 quilt id、面积与合并结果（模型 A `663abd7f…`）

爪（每爪一个作业，保存重载均 true）：

| 爪 | job_id | quilt_id | 面积 mm² |
| --- | --- | --- | --- |
| petal0 | `f32318979560461b9e7ad5ed9c0a77da` | 60 | 274.81017765074046 |
| petal1 | `1002ed04637f4bd8a221af7e807595c2` | 86 | 274.81017765074034 |
| petal2 | `845ad76754cb46f2a0c754342f6d106e` | 112 | 274.81017765074046 |
| petal3 | `af7f029b248645f5bf1fc270f5473ae7` | 138 | 274.8101776507404 |
| petal4 | `aedf930d9b7e4c2bba5a744cde79dad1` | 164 | 274.8101776507404 |

筒身/瓶底/瓶盖（一个作业 `a85bb964…`，保存重载 true）：quilt 192 = 5026.548245743668、quilt 225 = 201.06192982974665、quilt 253 = 1256.6370614359175。构建后 `quilts` 共 8 片，面积逐一命中解析值。

合并链（全部 `result_quilt_source=retrimmed_target_quilt`，结果 quilt 恒为 60，每步保存重载 true）：

| 步骤 | job_id | target → tool | 合并前（input）mm² | 合并后 mm² | 解析期望 mm² |
| --- | --- | --- | --- | --- | --- |
| merge_petal1 | `7332e8140daf4b7586da9dc1ce056f2b` | 60 → 86 | 549.6203553014809 | 549.6203553014808 | 549.6203553014811 |
| merge_petal2 | `c2881d45d51d46e5b2ede67eb0bf1526` | 60 → 112 | 824.4305329522213 | 824.4305329522213 | 824.4305329522217 |
| merge_petal3 | `bf89a97eecd74d12a2c711598cdb3156` | 60 → 138 | 1099.2407106029618 | 1099.2407106029616 | 1099.2407106029623 |
| merge_petal4 | `ebfb39dfe4b44f36a12d6e8f59e69367` | 60 → 164 | 1374.050888253702 | 1374.050888253702 | 1374.0508882537029 |
| merge_foot_disc | `c137047f10ca4fd2aca6f099865d2171` | 60 → 225 | 1575.1128180834485 | 1575.1128180512596 | 1575.1128180834496 |
| merge_body_tube | `9481fcd018b147c7a418385e6038116e` | 60 → 192 | 6601.661063794927 | 6601.661063794929 | 6601.661063827119 |
| merge_top_cap | `fdd063622eb742088342f4efcd786236` | 60 → 253 | 7858.298125230845 | 7858.298125230911 | 7858.298125263036 |

末步 `closed=true`（`ProQuiltVolumeEval` 成功），quilt 60 实测 `face_count=6`、`closed=true`、bbox `[−20.020…,−20,−10]…[20.020…,20,40]`（x 向 ±0.02 为扇形端点采样偏差，z 精确 −10/40）。链式合并（7 次连续 join 同一目标）本轮首次实机通过。

同一几何在模型 B `9d7a9ed5…`、模型 C `04d6e50d…` 重复构建，逐爪 id/面积与全部合并面积逐位一致（见报告 `chain_b`/`chain_c`）。

## 2. 组级检查（`creo_measure_surface_group`）

对最终组（1 个参考 quilt 60）作业 `c9848d5a79874c4182b7c792c394405b`，只读、revision 13 未变：

| 项 | 值 | 说明 |
| --- | --- | --- |
| `state` | `closed` | 四态之一 |
| `open_edges` | 0 | 无开放边 |
| `boundary_edges` / `joined_edges` | 12 / 12 | 全部边界边成对缝合 |
| `boundary_closed` | true | 整组边界为闭合壳 |
| `gap_max_mm` | null | `gap_max_status.reason=no_member_seam_candidate`（无开放边即无缝隙可量，不填 0） |
| `overlap` | null，`detected=null` | `overlap_status.reason=overlap_sample_budget_exceeded`、`query_code=-1`：6 面 7858 mm² 的组超出重叠采样预算，未给出结论（**不得**当作“无重叠”） |

容差：`tolerance_mm=0.01`、`gap_search_mm=1.0`（提交值，回执原样回读）。

## 3. 加厚（0.3 mm / 2 mm 各一次，均作为该模型的第一个实体）

| 项 | 模型 A：0.3 mm | 模型 B：2 mm |
| --- | --- | --- |
| job_id | `0d995136a51746929751b5d61a937a6e` | `4f8eec1204ac4e6da4bd6f079b6135f4` |
| 状态 / 保存重载 | succeeded / true | succeeded / true |
| revision | 13 → 14 | 13 → 14 |
| `volume_after_mm3` | 2357.526186516854 | 15727.484826184516 |
| 解析期望（面积×厚度） | 2357.489437578911（+0.016%） | 15716.596250526072（+0.069%） |
| body 面数 | 12（6 面壳体 × 内外） | 12 |
| 板厚读回（bbox z 跨距） | 50.3 mm（50 + 0.3） | 52.0 mm（50 + 2.0） |
| bbox | x/y ±20.15、z −10.15…40.15 | x/y ±21.0、z −11…41 |

闭合性/开口面：加厚前 quilt 60 `closed=true`、`open_edges=0`；加厚后 body 为闭合壳（12 面，无开放边界）。0.3 mm 未出现自交，无需回滚。

**已知边界（本轮实测）**：
- 同一 quilt 在已有加厚实体后再做第二次加厚（含 `new_body=true`）在再生成阶段失败，回执 message 为 `Regeneration produced a failed, suppressed or incomplete feature`（本轮较早的试跑 `761f5dee2b1e44fd8e76c1ce2a665271`，未给出具体 Toolkit 码），整体回滚：体积保持 2357.526186516854 mm³、revision 保持 14。因此 0.3 与 2 mm 分别在两个独立模型上取得。
- 加厚后 quilt 60 的**记录**被内核重新关联：id 与 `closed=true` 不变，但 `area_mm2` 报 1099.2407106029616、`face_count=1`；整面壳由 body 承载（12 面）。加厚前 7858.298125230911 mm² 的读数只对开放/未加厚状态成立。

## 4. 后续编辑：加厚模型上的圆角

| 项 | 模型 A（0.3 mm 壳） | 模型 B（2 mm 壳） |
| --- | --- | --- |
| 边选择 | quilt 边界圆与顶平面相交的外缘边 id 356（R20.15 圆柱 + z=40.15 平面） | 同一边 id 356（R21 圆柱 + z=41 平面） |
| job_id | `00be5a02d1fa4659b45463b9319a72b7` | `66ebaa860f10447b8e2dad0fd59642d9` |
| 半径 | 0.1 mm | 0.5 mm |
| 体积 before → after | 2357.526186516854 → 2357.254786398942 | 15727.484826184516 → 15720.443452138248 |
| `material_delta_mm3` | −0.2714001179119805 | −7.041374046268174 |
| 保存重载 / revision | true / 15 | true / 15 |
| 重载后 body | 14 面、z 跨距 50.3 mm | 14 面、z 跨距 52.0 mm |

两处圆角体积减少量与解析估计同量级（外缘 R0.5 圆角约 −7.04 mm³），说明加厚后的实体仍可被常规特征编辑，链路可用。

## 5. 实体化

| 场景 | job_id | 结果 |
| --- | --- | --- |
| 模型 C：闭合 quilt（未加厚）直接 `solidify` | `9d39112e7c474e2ebfe4ea273dee4a4e` | **succeeded**，`volume_after_mm3=56799.99517675038`（解析 56799.99517690347，差 1.5e−7 mm³），保存重载 true，revision 14，body 6 面、bbox z −10…40 |
| 模型 A：已加厚 quilt 再 `solidify` | `a87985a421ec4528a58b29b8d54d1d08` | **failed**：`ProFeatureWithoptionsCreate=-1 during execute_solidify`，整体回滚（revision 保持 15、体积不变） |

结论：闭合的五爪壳体本身可以被实体化为**实心**瓶体（体积与解析值逐位一致）；但已被 thicken 消费的 quilt 不能再走 solidify。

## 6. 保存-重载复查

每个作业的 `saved_file_reloaded_and_verified` 均为 true；重载后：

- 模型 A：revision 15、body 1 个（14 面、z 50.3）、quilt 60 记录仍为 closed、id 不变（面积见 §3 边界）。
- 模型 B：revision 15、body 1 个（14 面、z 52.0）、quilt 60 记录 id/closed 不变。
- 模型 C：revision 14、body 1 个（6 面、z 50.0，实心）。

## 7. 判定与边界

**能完成到哪一步**：`表面构造 → 逐片 quilt_merge（链式，7 次）→ 组级四态检查 → 0.3/2 mm 加厚成壳 → 实体圆角编辑 → 保存重载` 全链在本机 Creo 12.4.0.0 通过（63 项检查 0 失败，46 个作业）；闭合壳还可以直接 `solidify` 成实心瓶体（体积逐位命中解析值 56799.995 mm³）。

**仍不成立 / 必须等新原生能力**：

1. **真正的五瓣爪形**：本轮的“五爪”是五个 72° **直纹锥扇面**拼成的连续圆台，爪与爪之间没有凹谷、没有独立爪尖。要做凹谷花瓣底（非直纹、带曲率的花瓣面）需要多截面/边界混合或非平面填充，当前 `surface_loft` 只接受两条单曲线截面、`surface_fill` 只做平面（`surface_boundary_fill` 仍被门禁）。
2. **独立 quilt 偏置**：H07 两轮反证，`PRO_FEAT_FLX_OGF` 与三条 copy/offset 树均不产物；瓶底内外壁的等距面无法单独生成。
3. **同一 quilt 二次加厚**：已有加厚实体后再 thicken 同一 quilt 返回 −1（本轮 `761f5dee…`）。
4. **已加厚 quilt 的 solidify**：`ProFeatureWithoptionsCreate=-1`（本轮 `a87985a4…`）。
5. **组级重叠结论**：6 面 7858 mm² 的闭合组超出重叠采样预算（`overlap_sample_budget_exceeded`，code −1），大组“是否有重叠”仍无法判定。
6. **加厚后 quilt 记录**：quilt 面积/面数被内核重关联（7858.298 → 1099.2407、6 面 → 1 面），下游若按“加厚后 quilt 面积不变”决策会读错；只能读 body。
7. **瓶口/螺纹/壁厚均匀性**：瓶盖为平面填充，瓶体为恒半径筒身；真实瓶型的收口、变径、标签面等无对应能力。

**未覆盖**：Creo 9/10、非 mm 单位、三角/异形瓶身、真实花瓣凹谷、INTERSECT 合并、多工具 trim、WorkBuddy 黑盒；`saved_file_reloaded_and_verified` 只证明保存重载一致，不等于外部客户端读回一致。

## 8. 证据文件

| 文件 | SHA256 |
| --- | --- |
| `report.json`（本次运行 `20261108-134309-f44608`，46 作业 / 63 检查全通过） | `6CBC278E30B8BD8E24180849A89359A6375336C31E8ED16520408C77E4656DEC` |

说明：`report.json` 由 `tools/test_five_claw_bottle.py --live --confirm-session-usable --output docs/validation/dev074-h10-five-claw-2026-11-08/report.json` 生成（LF 行尾，53844 字节），含每个作业的 job_id、quilt id、面积、体积、bbox、revision 与保存重载标志；哈希按提交字节（LF）计算。

驱动：`tools/test_five_claw_bottle.py`。离线契约（`--live` 之外）校验计划 schema、能力登记/门禁与解析常量，不连接 Creo。
