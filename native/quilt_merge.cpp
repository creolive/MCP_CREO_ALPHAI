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

// ProMerge.h documents two trees. The flat legacy tree
// (PRO_E_SRF_MRG_PRNT_QLT / PRO_E_SRF_MRG_ADTL_QLT) is rejected by
// ProFeatureWithoptionsCreate with -1 on this machine, so the array tree is the
// only usable form. It creates an ACTIVE feature that owns four PRO_SURFACE
// items and no quilt until the solid is regenerated, which is why the flow
// below forces a full regenerate before it looks for the result quilt.
static ProElempath quilt_merge_array_path(int element_id) {
    ProElempathItem item = {};
    item.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
    item.path_item.elem_id = (ProElemId)element_id;
    ProElempath path = nullptr;
    CK(ProElempathAlloc(&path));
    CK(ProElempathDataSet(path, &item, 1));
    return path;
}

static ProElement quilt_merge_member(ProSelection quilt) {
    ProElement member = node(nullptr, PRO_E_SRF_MRG_QUILT_CMPD);
    ref(member, PRO_E_SRF_MRG_QUILT_REF, quilt);
    integer(member, PRO_E_SRF_MRG_QUILT_SIDE, PRO_SRF_MRG_QLT_SIDE_1);
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

    // Input areas are measured before the merge consumes them. The target area
    // is kept on its own: a join may modify the target quilt in place instead
    // of creating a new quilt item (live 2026-11-08).
    MeasurementOutcome input_area;
    MeasurementOutcome target_before;
    {
        ProQuilt quilt = nullptr;
        ProQuilt other = nullptr;
        MeasurementOutcome a, b;
        if (!ProQuiltInit((ProSolid)board, first_id, &quilt))
            a = quilt_area_native(quilt);
        else
            a.reason = "target_quilt_init_failed";
        target_before = a;
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

    // A forced full regenerate does not change the outcome: the feature stays
    // ACTIVE and still owns only surface items (live 2026-11-04), so no extra
    // regenerate is issued here.

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
    // Live 2026-11-04: the join feature regenerates ACTIVE but reports no quilt
    // item, so the diagnostic has to distinguish "quilt type filter wrong" from
    // "the feature really owns nothing" - surface items are counted as well.
    J surface_ids = J::array();
    ProError surface_visit =
        ProFeatureGeomitemVisit(&feature, PRO_SURFACE, collect_geom_ids, nullptr, &surface_ids);
    int result_id = -1;
    const char *result_source = nullptr;
    if (result_visit == PRO_TK_NO_ERROR && ids.size() == 1) {
        result_id = ids[0]["id"];
        result_source = "feature_quilt_geomitem";
    } else if (!surface_ids.empty() &&
               !feature_member_surface_quilt((ProSolid)board, surface_ids, result_id)) {
        // Live 2026-11-08: an accepted merge feature owns its member surfaces
        // instead of a PRO_QUILT geomitem (-4). The result quilt is still
        // resolvable from those surfaces when the kernel keeps them in one.
        result_source = "member_surface_quilt";
    } else if (target_before.available) {
        // Otherwise the join may have merged the tool into the target quilt in
        // place: the target's measured area then grows past its own pre-merge
        // area. A silent no-op keeps the area unchanged and stays a failure.
        ProQuilt retrimmed = nullptr;
        if (!ProQuiltInit((ProSolid)board, first_id, &retrimmed)) {
            MeasurementOutcome after = quilt_area_native(retrimmed);
            if (after.available && after.value > target_before.value + 1e-6) {
                result_id = first_id;
                result_source = "retrimmed_target_quilt";
            }
        }
    }
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
    details["result_quilt_source"] = result_source ? J(result_source) : J(nullptr);
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
    details["merge_tree"] = "array";
    details["feature_status"] = (int)status;
    details["feature_id"] = (int)feature.id;
    details["quilt_item_ids"] = ids;
    details["surface_item_ids"] = surface_ids;
    details["surface_visit_code"] = (int)surface_visit;
    details["inputs"] = {{"target_quilt_id", first_id}, {"tool_quilt_id", second_id}};
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE)
        throw std::runtime_error(
            "Surface merge regeneration failed; check that the two quilts share a boundary or "
            "intersect where the join expects them");
    if (result_id < 0)
        throw std::runtime_error("Surface merge produced no result quilt: the feature owns " +
                                 std::to_string((int)ids.size()) + " quilt geomitems (visit code " +
                                 std::to_string((int)result_visit) + ") and " +
                                 std::to_string((int)surface_ids.size()) +
                                 " surfaces, none of which reports an owning quilt");
    if (!area.available)
        throw std::runtime_error(std::string("Surface merge result is not measurable") +
                                 (area.reason ? ": " : "") + (area.reason ? area.reason : ""));
    remember(op, feature, {{"quilt_id", result_id}});
}
