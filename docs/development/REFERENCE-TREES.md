# 参照树：S03 / S05 / S07 的元素树依据（2026-11-05）

这些树不是猜的，也不是从外部文件借的：**它们是从本服务自己能建出的特征上读回的**
（`tools/read_reference_tree.py` 的读取链路：adopt → inspect → dump_tree）。

复现：先建一个模型（`build/_own_trees.py` 的计划：填充面 + 加厚 + 曲面扫掠），
再对它的每个特征跑 `dump_tree`，即可得到下表。

## S07 偏置：加厚特征里的真实偏置元素

`PAD`（`PRO_FEAT_PROTRUSION`，由 `thicken` 生成）：

```xml
<PRO_E_THICKEN_TYPE type="int">917</PRO_E_THICKEN_TYPE>
<PRO_E_THICKNESS type="double">2.00</PRO_E_THICKNESS>
<PRO_E_SRF_OFFS_METHOD type="int">1</PRO_E_SRF_OFFS_METHOD>
<PRO_E_SRF_OFFS_CTRLFIT type="compound">
  <PRO_E_SRF_OFFS_SCALINGCSYS type="selection"></PRO_E_SRF_OFFS_SCALINGCSYS>
</PRO_E_SRF_OFFS_CTRLFIT>
<PRO_E_SRF_OFFS_AXES type="int">0</PRO_E_SRF_OFFS_AXISES>
<PRO_E_SRF_OFFS_HANDLINGS type="array"></PRO_E_SRF_OFFS_HANDLINGS>
```

要点：偏置元素挂在**加厚/凸台特征树**下（`PRO_E_SRF_OFFS_METHOD` = 1、
`PRO_E_SRF_OFFS_CTRLFIT` 是 compound、内含坐标系选择、`PRO_E_SRF_OFFS_AXES` = 0、
`PRO_E_SRF_OFFS_HANDLINGS` 是数组）。此前 12 个候选把 `PRO_E_SRF_OFFS_*` 挂在
`PRO_FEAT_DATUM_SURF` 或 `PRO_FEAT_OFFSET` 下，被内核以 -1/-2 拒绝——**挂载位置错了**。

## S03 合并：曲面特征里的真实合并元素

`SWEPT`（`PRO_FEAT_DATUM_SURF`）与 `LOW_FACE` / `HIGH_FACE`（同为 `PRO_FEAT_DATUM_SURF`）：

```xml
<PRO_E_SWP_ATTR type="compound">
  <PRO_E_END_SRF_ATTR type="int">14</PRO_E_END_SRF_ATTR>
</PRO_E_SWP_ATTR>
<PRO_E_SWP_INNER_SRF type="int">0</PRO_E_SWP_INNER_SRF>
<PRO_E_SWP_MERGE_ENDS type="int">0</PRO_E_SWP_MERGE_ENDS>
<PRO_E_TRIM_QUILT type="selection"></PRO_E_TRIM_QUILT>
<PRO_E_SMT_MERGE_DATA type="compound">
  <PRO_E_SMT_MERGE_AUTO type="int">0</PRO_E_SMT_MERGE_AUTO>
  <PRO_E_SMT_MERGE_KEEP_LINES type="int">0</PRO_E_SMT_MERGE_KEEP_LINES>
  <PRO_E_SMT_MERGE_KEEP_BEND_EDGES type="int">0</PRO_E_SMT_MERGE_KEEP_BEND_EDGES>
</PRO_E_SMT_MERGE_DATA>
```

要点：`PRO_E_SMT_MERGE_DATA`（compound）挂在**曲面特征树**下并带三个开关，
`PRO_E_TRIM_QUILT` 是 quilt 的 selection，`PRO_E_SWP_MERGE_ENDS` 控制扫掠端面合并。
此前 4 条合并路线（`ProMerge.h` 的数组树）建出的是 4 个 `PRO_SURFACE`、0 个 `PRO_QUILT`，
说明那条"独立 Merge 特征"的思路与本机的实际数据结构不合。

## S05 混合：Direct Blend 没有元素树（-18）

种子放样参照件（`seed_library/seeds/two_straight/mechdog_loft_reference.prt.5`）里：

| 特征 | 类型 | 元素树 |
| --- | --- | --- |
| `RIGHT`/`TOP`/`FRONT`/`LOFT_TOP_PLANE` | `PRO_FEAT_DATUM` | 读回成功 |
| `LOFT_BOTTOM`/`LOFT_TOP` | `PRO_FEAT_CURVE` | 读回成功；截面含 `PRO_E_STD_SEC_BLN_VERTS`（混合顶点的选择） |
| Direct Blend 本体（id 60） | — | **`ProFeatureElemtreeExtract` 返回 -18** |

即：混合特征**没有可抽取的元素树**，面板路线是唯一路线（已交付的 `loft` 即面板驱动）。

## 规格来源（文档头文件）

`ProThicken.h` 完整记录了加厚/偏移树：元素树、取值表与映射表（三种偏移方法
`PRO_OFFS_METH_NORMTOSURF` / `PRO_OFFS_METH_AUTOSCALE` / `PRO_OFFS_METH_MANUALSCALE`），
方向元素是 `PRO_E_STD_USEQLT_SIDE`，逐面偏置用 `PRO_E_SRF_OFFS_HANDLING`（`PRO_E_SRF_OFFS_REF_SEL`
+ `PRO_E_SRF_OFFS_ACTION`）。自建特征的 `PAD` 树与该规格逐项吻合。

## 尚未解除的缺口

- **偏置特征本体**（`PRO_FEAT_OFFSET`）的树：仍无参照件，只能继续用加厚树的偏置元素推。
- **合并特征本体**：本机看起来没有独立的"合并面"特征，合并语义落在
  `PRO_E_SMT_MERGE_DATA` / `PRO_E_SWP_MERGE_ENDS` 这类曲面特征元素上。
- 种子库只有两个放样参照件，没有 Merge/Offset 参照件；手工件到位后上面同一工具一次读回。
