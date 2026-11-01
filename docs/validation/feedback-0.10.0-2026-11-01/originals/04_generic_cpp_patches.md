# generic.cpp 补丁提取（供作者并入，基于 0.10.0 源码直改）

## 补丁 1：datum_plane 三点定面（offset_plane 内，reference 处理前插入）

```cpp
roFeature offset_plane(const J &reference, double offset, const std::wstring &name,
                               double *angle = nullptr, const J *axis = nullptr) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM);
    text(root, PRO_E_STD_FEATURE_NAME, name.c_str());
    ProElement constraints = node(root, PRO_E_DTMPLN_CONSTRAINTS);
    // Three-point form: {"thru_points": ["labelA","labelB","labelC"]} — each datum_points
    // feature contributes one PRO_DTMPLN_THRU constraint (ProDtmPln.h: THRU accepts PRO_POINT).
    // Three non-collinear points determine a unique plane; this also gives an angled plane
    // through a chord line without needing an axis reference.
    if (reference.is_object() && reference.contains("thru_points")) {
        const J &pts = reference.at("thru_points");
        if (!pts.is_array() || pts.size() < 3)
            throw std::runtime_error(
                "thru_points requires at least 3 datum_points feature labels");
        for (const auto &lbl : pts) {
            ProElement c = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
            integer(c, PRO_E_DTMPLN_CONSTR_TYPE, PRO_DTMPLN_THRU);
            ProSelection s = resolve({{"kind", "datum_point_feature"}, {"label", lbl}});
            ref(c, PRO_E_DTMPLN_CONSTR_REF, s);
            ProSelectionFree(&s);
        }
        ProFeature f = create(root);
        CK(ProElementFree(&root));
        return f;
    }
    ProElement c = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
    ProSelection s = resolve(reference);
    integer(c, PRO_E_DTMPLN_CONSTR_TYPE, angle ? PRO_DTMPLN_ANG : PRO_DTMPLN_OFFS);
    ref(c, PRO_E_DTMPLN_CONSTR_REF, s);
    real(c, angle ? PRO_E_DTMPLN_CONSTR_REF_ANGLE : PRO_E_DTMPLN_CONSTR_REF_OFFSET,
     
```

调用方式（op 分发的 datum_plane 分支不用改，reference 直接透传）：

```json
{"op":"datum_plane","label":"pl","reference":{"thru_points":["dp1","dp2","dp3"]}}
```

要求：`thru_points` 里的每个 label 都必须是本计划内已创建的 `datum_points` 特征标签
（resolve 走 `{"kind":"datum_point_feature","label":...}`，ProFeatureGeomitemVisit 取其唯一 PRO_POINT）。

## 补丁 2：sketch frame 的 UV 基回退（project lambda 前）

```cpp
 loc[row][1], loc[row][2],
            loc[row][3]);
    const bool mirrored = dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) < 0;
    arc_endpoint_swapped.clear();
    arc_logical_swapped.clear();
    // BUG-094 (2026-10-31): on an incomplete feature over an oblique datum
    // plane ProSectionLocationGet still returns the identity, so loc-based UV
    // mapping writes world XY into the section. The frame we used to place the
    // sketch is exact: project with frame.u / frame.v whenever the location
    // matrix is (numerically) the identity.
    bool loc_is_identity = fabs(loc[0][0] - 1) < 1e-12 && fabs(loc[1][1] - 1) < 1e-12 &&
                           fabs(loc[2][2] - 1) < 1e-12 && fabs(loc[0][1]) < 1e-12 &&
                           fabs(loc[0][2]) < 1e-12 && fabs(loc[1][0]) < 1e-12 &&
                           fabs(loc[1][2]) < 1e-12 && fabs(loc[2][0]) < 1e-12 &&
                           fabs(loc[2][1]) < 1e-12 && fabs(loc[3][0]) < 1e-12 &&
                           fabs(loc[3][1]) < 1e-12 && fabs(loc[3][2]) < 1e-12;
    if (loc_is_identity)
        log("SECTION_LOCATION_IDENTITY=1 using_frame_basis\n");
    auto project = [&](const J &p, double *out) {
        V w = add(frame.origin, add(scale(frame.u, p.at(0).get<double>()),
                                    scale(frame.v, p.at(1).get<double>())));
        if (loc_is_identity) {
            V d = add(w, scale(frame.origin, -1));
            out[0] = dot(d, frame.u);
            out[1] = dot(d, frame.v);
            return;
        }
        for (int i = 0; i < 2; i++)
            out[i] = (w[0] - loc[3][0]) * loc[i][0] + (w[1] - loc[3][1]) * loc[i][1] +
                     (w[2] - loc[3][2]) * loc[i][2];
    };
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef cs = {};
    cs.type = PRO_2D_COORD_SYS;
    int csid;
    CK(ProSectionEntityAdd(section, (Pro2dEntde
```

## 实测证据（Creo 10.0.0.0）

- 三点定面：`datum_plane id=47 normal=-0.678,-0.093,0.730 origin=-95.191,40.000,-88.395`（与解析一致）
- UV 回退：`SECTION_LOCATION_IDENTITY=1 using_frame_basis` → `LINE_tri_0=0,0 → 190.382228,22.394433`（与解析一致）
- 已知剩余：正确 UV 后 `ProFeatureWithoptionsRedefine` 在斜面草图仍 -1（BUG-094 L2），建议在 `errors(es)` 处把 `ProErrorlist` 内容带回执定位。
