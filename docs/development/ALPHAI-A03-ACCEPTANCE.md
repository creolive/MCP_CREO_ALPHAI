# A03 / FEAT-035 标准螺纹孔：验收摘要

日期：2026-11-03。分支 `codex/FEAT-035-standard-holes`，实机基线提交 `0c7c6d6` 加本轮未提交改动。环境：本机 Windows x64 / Creo 12.4.0.0 / 匹配 Toolkit SDK，单一 A03 会话串行执行。

驱动：`tools/test_adoption_standard_holes.py`。默认离线只校验用例表、schema 守卫与体积 oracle；`--live --confirm-session-usable` 另建 60×60×12 底板并逐例取证。证据文件 `build/acceptance_standard_holes.json`，SHA256 `c1abf15ce44d2897868e9284b9d06fe71c1136cc3785f7efcb6b7e39a1036d9f`（最终格式化源码 `bridge.py build` 后重跑），20 例全部通过。

## 一 实机逐例

| 用例 | 期望 | 实测 |
| --- | --- | --- |
| `iso_m6x1` | 建 M6×1 螺纹孔，读回一致 | succeeded，去料 `206.1811 mm³`（Ø5×10 圆柱 196.35 + 118° 钻尖 9.83），`thread_metadata_verified=true`，保存重载 true |
| `iso_m8x1_25` | 第二个枚举规格 | succeeded，去料 `435.8025 mm³`（Ø6.8×12，深度取满板厚故钻尖落在板外），读回 `M8x1.25`，verified=true |
| `iso_m5x0_8_flip` | 翻向成立 | succeeded，去料 `116.6626 mm³`（Ø4.2×8 + 钻尖，全在板内），轴向 z 跨 0–8，verified=true |
| `flip_off_no_material` | 同一基准面不放翻向必须切不到料 | failed：`Hole removes no material`，无 feature 产生 |
| `plain_straight` / `plain_counterbore` / `plain_countersink` | 旧孔型回执不变 | 三例 succeeded，去料 339.29 / 1310.04 / 1110.63 mm³，回执内**没有** `thread_metadata*` 字段 |
| `unknown_size` / `path_escape` / `over_table_limit` / `beyond_tip` | 入口拒绝且不产生 job | 四例均在 schema 层 ValueError，无 job |
| `chart_missing_size` | 表外型号由安装孔表拒绝 | 原生返回 failed：`Standard hole size M6x9 is not in the installed ISO hole chart (code -22)`，revision 不变 |
| `deliberate_failure_rollback` | 两操作计划后项失败整计划回滚 | failed（`Datum plane geometry id not found: 999999`），`rollback_succeeded=true`，revision 不变，随后合法编辑 succeeded |

每例标准孔另核：`feature_id` 严格递增（新特征成立）、`saved_file_reloaded_and_verified=true`、`thread_metadata` 的 series/size/表标识与冻结表一致。

## 二 本轮确认的两条原生行为

1. **安装孔表是唯一权威**。`ProElementHoleScrewSizeSet` 按名解析实际 `.hol`：`M7x1` 在本机 ISO 表里存在（底孔 6.0），因此表外但在表内的型号能正常建孔；真正不存在的 `M6x9` 返回 `-22 (PRO_TK_INVALID_NAME)`，原生抛错且不退化成长普通直孔。冻结表只决定"我们对外提供哪些行"，不决定机器可用性。
2. **`flip` 是方向开关，不是面属性**。同一 z=0 基准面放置，`flip=true` 切进板内（去料与 oracle 吻合），`flip=false` 报 `Hole removes no material`。因此"翻向"用例必须以对照形式取证，不能只跑成功那一侧。

## 三 回执形态

- `thread_metadata{series,size,thread_depth_mm,table_id,table_sha256}`：实际套用的冻结表行（P00 冻结字段）。
- `thread_metadata_verified`：只由原生对**创建后特征树**的回读决定，缺失或不符一律 `false`。
- `thread_readback{...}`：附加诊断块（add_thread/standard_type/series_name/screw_size_name/thread_depth/depth_type/verified），用于定位"螺纹没落地"的具体元素，不属于冻结契约。
- 普通孔回执不变；`bridge.compact_job` 白名单同步三个字段。

## 四 契约实现说明与偏差

- `diameter` 在 `standard` 分支可省略，`standard=None` 时仍必填（P00 冻结）；`creo_hole` 的形参顺序因此改为 `placement/reference1/reference2/diameter=...`，MCP 客户端按名传参不受影响。
- 标准孔要求显式 `depth`：`thread_depth` 必须严格小于钻尖深度（`depth + 钻尖锥高`），并同时受表内螺纹深度上限约束。
- 原生实现放在 `native/generic.cpp` 的 `standard_hole_elements()` 与 `hole_thread_json()`，未按 P00 的"新建 `native/standard_hole.h/.cpp`"拆分：该文件的孔路由与元素树辅助本就集中在 `generic.cpp`，拆分会复制两份 `get_optional`/`log` 走线。此为文件归属偏差，功能与契约不受影响，记录在此供集成人复核。
- 冻结表新增 `fastener_id`（孔表 `FASTENER_ID`）与 `tap_drill_mm`；`hole_standards.prepare()` 在提交前把行值注入操作，原生不再自行推导底孔或型号。

## 五 未验证范围

- Creo 9 / Creo 10 实机（本机只有 12.4）。
- 冻结表其余规格 M3 / M4 / M10 / M12 的实机（表值已离线校验，未逐例建孔）。
- 通孔（thru-all）标准孔：schema 现要求盲孔 depth，通孔标准孔未建模也未测。
- 出口沉头、双端沉孔、`PRO_E_HLE_ADD_PARAMETERS` 参数化、孔注释。
- WorkBuddy 黑盒客户端验收；本摘要仅为原生 + MCP 通道证据。
