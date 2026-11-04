// quilt_merge.cpp — FEAT-039/S03: join two quilts into one surface merge.
//
// Tree source: ProMerge.h §(1) "Feature element tree" of the current (array)
// surface merge, which is fully documented by the local SDK:
//
//   PRO_E_FEATURE_TREE
//    ├ PRO_E_FEATURE_TYPE      = PRO_FEAT_DATUM_QUILT
//    ├ PRO_E_SRF_MRG_QUILT_ARR (array, at least two members)
//    │   └ PRO_E_SRF_MRG_QUILT_CMPD
//    │       ├ PRO_E_SRF_MRG_QUILT_REF  (PRO_QUILT selection, mandatory)
//    │       └ PRO_E_SRF_MRG_QUILT_SIDE (ProSrfMrgQltSide, optional)
//    ├ PRO_E_SRF_MRG_TYPE      = ProSrfMrgType (default INTERSECT)
//    └ PRO_E_STD_FEATURE_NAME
//
// The first release joins exactly two quilts. ProMerge.h Note-3 documents
// INTERSECT as the default, so JOIN is written explicitly. No tolerance and no
// gap measurement are offered: an unproved tolerance would be silently
// ignored, and closure is reported only from the real volume probe.
#include <ProMerge.h>

// Path of a direct child element of the feature tree, used for array members.
static ProElempath quilt_merge_array_path(int element_id) {
    ProElempathItem item = {};
    item.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
    item.path_item.elem_id = (ProElemId)element_id;
    ProElempath path = nullptr;
    CK(ProElempathAlloc(&path));
    CK(ProElempathDataSet(path, &item, 1));
    return path;
}

// One array member: a quilt compound holding the mandatory reference. The
// per-quilt side element is optional and left at the SDK default, so the
// retained region is whatever the documented default produces and is measured
// rather than assumed.
static ProElement quilt_merge_member(ProSelection quilt) {
    ProElement member = node(nullptr, PRO_E_SRF_MRG_QUILT_CMPD);
    ref(member, PRO_E_SRF_MRG_QUILT_REF, quilt);
    return member;
}

static void generic_quilt_merge(const J &op) {
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);

    // Two type-explicit, distinct quilts (the schema refuses anything else).
    ProSelection first = resolve_quilt_reference(op.at("target"), (ProSolid)board, units, scale);
    ProSelection second = resolve_quilt_reference(op.at("tool"), (ProSolid)board, units, scale);
    int first_id = quilt_selection_id(first);
    int second_id = quilt_selection_id(second);
    if (first_id == second_id)
        throw std::runtime_error("quilt_merge needs two distinct quilts; both references name " +
                                 std::to_string(first_id));

    // Input areas are measured before the merge consumes them.
    MeasurementOutcome input_area;
    {
        ProQuilt quilt = nullptr;
        ProQuilt other = nullptr;
        MeasurementOutcome a, b;
        if (!ProQuiltInit((ProSolid)board, first_id, &quilt))
            a = quilt_area_native(quilt);
        else
            a.reason = "target_quilt_init_failed";
        if (!ProQuiltInit((ProSolid)board, second_id, &other))
            b = quilt_area_native(other);
        else
            b.reason = "tool_quilt_init_failed";
        if (a.available && b.available) {
            input_area.available = true;
            input_area.value = a.value + b.value;
        } else {
            input_area.reason = !a.available ? a.reason : b.reason;
            input_area.query_code = !a.available ? a.query_code : b.query_code;
        }
    }

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_QUILT);
    integer(root, PRO_E_SRF_MRG_TYPE, PRO_SRF_MRG_JOIN);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    node(root, PRO_E_SRF_MRG_QUILT_ARR);
    ProElement *members = nullptr;
    CK(ProArrayAlloc(2, sizeof(ProElement), 1, (ProArray *)&members));
    members[0] = quilt_merge_member(first);
    members[1] = quilt_merge_member(second);
    ProElempath array_path = quilt_merge_array_path(PRO_E_SRF_MRG_QUILT_ARR);
    CK(ProElementArraySet(root, array_path, members));
    CK(ProElempathFree(&array_path));
    ProArrayFree((ProArray *)&members);
    ProFeature feature = create(root);
    ProElementFree(&root);
    ProSelectionFree(&first);
    ProSelectionFree(&second);

    ProFeatStatus status;
    CK(ProFeatureStatusGet(&feature, &status));

    // The merge owns the resulting quilt; zero or several is not a result we
    // can hand to thicken or report on.
    J ids = J::array();
    // A trim re-trims its target and answers -4 here (live 2026-11-04); a merge
    // owns a new quilt in this release, so a failed visit is reported instead of
    // being raised as a raw Toolkit error.
    ProError result_visit =
        ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &ids);
    int result_id = -1;
    if (result_visit == PRO_TK_NO_ERROR && ids.size() == 1)
        result_id = ids[0]["id"];
    MeasurementOutcome area;
    MeasurementOutcome closed;
    if (result_id < 0) {
        area.reason = result_visit != PRO_TK_NO_ERROR
                          ? "result_quilt_visit_failed"
                          : (ids.size() > 1 ? "result_quilt_ambiguous" : "result_quilt_missing");
        closed.reason = area.reason;
    } else {
        ProQuilt result = nullptr;
        if (ProQuiltInit((ProSolid)board, result_id, &result)) {
            area.reason = "result_quilt_init_failed";
            closed.reason = area.reason;
        } else {
            area = quilt_area_native(result);
            closed = quilt_closed_native(result);
        }
    }

    J details = area_fields_json(input_area, units, scale, "input_area_mm2", "input_area_status");
    J merged = area_fields_json(area, units, scale, "area_mm2", "area_status");
    for (auto it = merged.begin(); it != merged.end(); ++it)
        details[it.key()] = it.value();
    bool is_open = quilt_closed_is_open(closed);
    details["result_quilt_id"] = result_id < 0 ? J(nullptr) : J(result_id);
    details["result_quilt_visit_code"] = (int)result_visit;
    // Branch-by-branch: a bool/nullptr ternary folds into nullptr on MSVC and
    // reports null for an open quilt (live 2026-11-04 on the quilts section).
    J closed_json = nullptr;
    if (closed.available)
        closed_json = true;
    else if (is_open)
        closed_json = false;
    details["closed"] = closed_json;
    details["closed_status"] = measurement_status_json(closed, units, scale);
    details["merge_type"] = "join";
    details["inputs"] = {{"target_quilt_id", first_id}, {"tool_quilt_id", second_id}};
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE)
        throw std::runtime_error(
            "Surface merge regeneration failed; check that the two quilts share a boundary or "
            "intersect where the join expects them");
    if (result_id < 0)
        throw std::runtime_error(
            "Surface merge produced no single result quilt; the feature owns " +
            std::to_string((int)ids.size()) + " quilt geometry items");
    if (!area.available)
        throw std::runtime_error(std::string("Surface merge result is not measurable") +
                                 (area.reason ? ": " : "") + (area.reason ? area.reason : ""));
    remember(op, feature, {{"quilt_id", result_id}});
}
