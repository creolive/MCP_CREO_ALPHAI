# FEAT-039/H03 两片 quilt 合并反证（2026-11-07）

结论先行：按 `surface_loft` 的「INCOMPLETE 骨架 → 抽取 → redefine」方法论重试后，
`quilt_merge` 的失败形态与历史完全一致——特征 `PRO_FEAT_ACTIVE`、0 个 `PRO_QUILT`、
4 个 `PRO_SURFACE`、quilt 访问码 `-4`。没有可测量的结果 quilt，因此 `quilt_merge`
**继续保持 `UNAVAILABLE_OPERATIONS` 门禁**，本轮不解除、不声称瓶底可实体化。

## 环境与命令

- Windows x64；Creo 12.4.0.0（已手工启动并授权）；本机匹配 Toolkit SDK；单位 mm；单会话串行。
- `config.json`：`auto_start_creo=false`；本轮未启动/关闭 Creo，未清 unknown 保护，未做故障注入。
- 构建：`.\.venv\Scripts\python.exe bridge.py build` → 退出 0。
- 探针：`build/_probe_quilt_merge.py`（临时脚本，不入库），经 stdio MCP 提交
  `sketch + sketch + surface_fill + surface_fill + quilt_merge` 的计划。
- 为提交被门禁的算子，故意门禁只在**工作树内临时**移除；探针结束后已把
  `src/creo_mechdog/capabilities.py` 与 `native/quilt_merge.cpp` 还原到 HEAD，
  最终提交不含任何门禁或原生行为改动。
- 证据原始值：[merge_probe_report.json](merge_probe_report.json)，10739 B，SHA256
  `1634C5637E5B8641CC379D28EAD907A7B8241244B93B9CA4E2C1CBC4B6E26FEC`。

构造：两张共面 20×20 `surface_fill`，A 覆盖 x∈[0,20]、B 覆盖 x∈[20,40]，z=0，
沿 x=20 共边；输入 quilt 91/127，输入面积合计 **800.0 mm²**（`input_area_status.available=true`）。

## 两次尝试的真实返回码

| 尝试 | job_id | create | extract | ProErrorlist | feature_status | quilt 访问 | quilt | surface | 作业终态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ① HEAD 现状：数组树一次性创建 | `0065877624af4cf4932a8179682908b3` | 未单独记录（旧实现） | — | — | **0**（ACTIVE） | **-4** | **0** | 4（132/134/136/138，type=5） | failed（新模型清理确认） |
| ② INCOMPLETE 创建 → 抽取 → redefine | `80adc5a5ae714cf5bc40f9936ec6122d` | **0** | **0** | **total=0** | **0**（ACTIVE） | **-4** | **0** | 4（132/134/136/138，type=5） | failed（新模型清理确认） |

两次的 `result_quilt_id=null`、`area_mm2=null`（`area_status.reason="result_quilt_visit_failed"`）、
`closed=null`；`surface_visit_code=0`。也就是说：合并特征确实再生成功并拥有 4 个面项，
但**不拥有任何 quilt 项**，模型层也没有可交给 `thicken`/`solidify` 的结果 quilt。

## 内核补全后的元素树（尝试 ② 的抽取结果）

`ProFeatureElemtreeExtract` 返回 0，共 11 个元素：

| 元素 id | 元素名 | 实测值 |
| --- | --- | --- |
| 387 | `PRO_E_FEATURE_TYPE` | 946 = `PRO_FEAT_DATUM_QUILT` |
| 3723 | `PRO_E_SRF_MRG_QUILT_ARR` | 数组，2 个成员 |
| 3722 | `PRO_E_SRF_MRG_QUILT_CMPD` | compound（每个成员一个） |
| 3721 | `PRO_E_SRF_MRG_QUILT_REF` | `PRO_VALUE_TYPE_SELECTION`，`reference_count=1` |
| 3729 | `PRO_E_SRF_MRG_QUILT_SIDE` | 1 = `PRO_SRF_MRG_QLT_SIDE_1`（**内核自己补的**） |
| 1116 | `PRO_E_SRF_MRG_TYPE` | 1 = `PRO_SRF_MRG_JOIN` |
| 1964 | `PRO_E_STD_FEATURE_NAME` | `"PROBE_MERGE"` |

关键事实：这条路线里两个成员的 `PRO_E_SRF_MRG_QUILT_SIDE` 与 `PRO_E_SRF_MRG_TYPE`
**不是我们预先写死的**，而是 INCOMPLETE 创建后由内核补全的；补全结果与 HEAD 旧实现
（显式写 JOIN、不写 SIDE）等价（内核同样给出 SIDE=1）。因此 `surface_loft` 成功的
根因（创建前手写可选值）**不适用于** `quilt_merge`：即使让内核自己补全，结果仍是
4 个面、0 个 quilt。这与 G5 §2.4/§2.9 的历史结论一致，不是树形写法问题。

## 一次失败的诊断尝试（如实记录）

为回答「quilt 是否存在于另一个 id 空间」，在原生侧临时加入「扫描 1..feature_id+40 的
`ProQuiltInit`」诊断并重新编译。该诊断本身有缺陷：`ProQuiltInit` 遇到非 quilt 的 id 后
内核挂起，作业 `9b64c0fb330b49a285200d286934bc06` 在 `ProFeatureStatusGet=0` 之后
超时，终态 **`unknown_outcome`**（`Native worker timed out`）。按 BUG-001 约定：
未重试该作业、未清除 unknown 保护、未改动模型；诊断代码已删除并还原原生文件。
该作业不构成几何结论，只作为「扫描 id 空间不可用」的过程记录。

## 未覆盖

- 链式三片、保存重载后 quilt id/面积不变、两片不相邻/引用无效的 revision 回滚：
  在拿到结果 quilt 之前不存在可验收对象，本轮未做。
- 手工 Merge 参照树：本机种子库无 Merge 参照件；若要继续，应先在 Creo 界面手工建一个
  Merge 特征并用 `tools/read_reference_tree.py` 读回真实树，再判断是否存在当前文档之外的
  「结果 quilt」元素/类型。
- Creo 9 / Creo 10；非 mm 单位；曲面（非平面）成员。
