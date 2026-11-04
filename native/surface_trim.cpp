// surface_trim.cpp — FEAT-039/S02: the high-level surface trim.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.3 (the documented
// ProTrim.h "Use Quilt" tree), §3.3 (first-release boundary), §4.4.2/§4.5
// (measurement and retained-side fields). This module reuses the S01 quilt
// reference resolution and the shared quilt measurement; it never enumerates
// quilts itself and never invents a retained side.
//
// First release is the use-quilt variant only: the target is one quilt and
// the tool is one quilt or one datum plane. The use-curve variant is refused
// by the Python contract and is not built here.
//
// This file is included by generic.cpp after the shared element-tree,
// inspection and quilt helpers are visible; it defines no entry point of its
// own beyond generic_surface_trim.
#include <ProTrim.h>

// A trim measurement projected onto the §4.4.2 names. area_mm2_json already
// keeps "measured zero" apart from "could not measure"; only the keys change.
static J trim_area_fields(const MeasurementOutcome &area, const InspectionLengthUnits &units,
                          const MillimeterScale &scale, const char *value_key,
                          const char *status_key) {
    J projected = area_mm2_json(area, units, scale);
    return {{value_key, projected["area_mm2"]}, {status_key, projected["area_status"]}};
}

// The tool side of the trim tree. A quilt reference goes through the S01
// resolver; a datum plane is resolved as its owning feature and also yields
// the real plane normal for kept_side_basis (§4.5).
static ProSelection surface_trim_tool_selection(const J &reference, ProVector normal,
                                                bool &normal_known) {
    std::string kind = reference.value("kind", "");
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    if (kind == "quilt" || kind == "quilt_feature")
        return resolve_quilt_reference(reference, (ProSolid)board, units, scale);
    if (kind == "datum_plane") {
        ProSelection tool = resolve({{"kind", "datum_feature"}, {"label", reference.at("label")}});
        // resolve() leaves exactly one entry in `planes` for a datum feature.
        if (planes.size() == 1) {
            for (int i = 0; i < 3; i++)
                normal[i] = planes[0].n[i];
            normal_known = true;
        }
        return tool;
    }
    throw std::runtime_error(
        "surface_trim tool must be a quilt or a datum plane; the use-curve trimming "
        "variant is not part of this release");
}

static int surface_trim_geometry_id(ProSelection selection) {
    ProModelitem item;
    CK(ProSelectionModelitemGet(selection, &item));
    return item.id;
}

// The retained region after the trim. Review focus 1 of the plan: a trim may
// modify an existing quilt instead of owning a new PRO_QUILT geometry item, so
// zero items are reported through the re-trimmed target, several are refused.
static int surface_trim_kept_quilt(ProFeature feature, int target_id, const char *&source) {
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &ids));
    if (ids.size() == 1) {
        source = "feature_quilt_geomitem";
        return ids[0]["id"];
    }
    if (ids.size() > 1)
        throw std::runtime_error("Trim feature owns " + std::to_string((int)ids.size()) +
                                 " quilts; the retained region is ambiguous");
    // No direct geometry item: the result may be the trimmed target itself.
    ProQuilt requery = nullptr;
    if (ProQuiltInit((ProSolid)board, target_id, &requery))
        return -1;
    source = "retrimmed_target_quilt";
    return target_id;
}

static void generic_surface_trim(const J &op) {
    std::string keep_side = op.at("keep_side");
    if (keep_side != "one" && keep_side != "two")
        throw std::runtime_error("surface_trim keep_side must be one or two");

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);

    // §3.3: one quilt target, one quilt/datum-plane tool.
    ProSelection target_selection =
        resolve_quilt_reference(op.at("target"), (ProSolid)board, units, scale);
    int target_id = surface_trim_geometry_id(target_selection);
    ProQuilt target_quilt = nullptr;
    MeasurementOutcome area_before;
    if (ProQuiltInit((ProSolid)board, target_id, &target_quilt)) {
        area_before.reason = "target_quilt_init_failed";
    } else {
        area_before = quilt_area_native(target_quilt);
    }

    ProVector tool_normal = {0.0, 0.0, 0.0};
    bool tool_normal_known = false;
    ProSelection tool_selection =
        surface_trim_tool_selection(op.at("tool"), tool_normal, tool_normal_known);

    int primary_side = keep_side == "one" ? PRO_TRIM_PRIM_QLT_SIDE_ONE : PRO_TRIM_PRIM_QLT_SIDE_TWO;

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CUT);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    // PRO_E_SRF_TRIM_TYPE is non-redefinable mandatory; both type elements must
    // agree (ProTrim.h §2.1).
    integer(root, PRO_E_SRF_TRIM_TYPE, PRO_SURF_TRIM_USE_QLT);
    integer(root, PRO_E_SURF_TRIM_TYPE, PRO_SURF_TRIM_USE_QLT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ref(root, PRO_E_TRIM_QUILT, target_selection);
    ref(root, PRO_E_STD_USEQLT_QLT, tool_selection);
    // §4.5: material side and "keep trim surface" are fixed in this release;
    // only the primary quilt side follows keep_side.
    integer(root, PRO_E_MATERIAL_SIDE, PRO_TRIM_MATL_SIDE_ONE);
    integer(root, PRO_E_PRIMARY_QLTSIDE, primary_side);
    integer(root, PRO_E_KEEP_TRIM_SURF_OPT, PRO_KEEP_TRIM_SURF_OPT_NO);
    ProFeature feature = create(root);
    ProElementFree(&root);
    ProSelectionFree(&target_selection);
    ProSelectionFree(&tool_selection);

    ProFeatStatus status;
    CK(ProFeatureStatusGet(&feature, &status));

    const char *kept_source = nullptr;
    int kept_id = surface_trim_kept_quilt(feature, target_id, kept_source);
    MeasurementOutcome area_after;
    if (kept_id < 0) {
        area_after.reason = "kept_quilt_unresolved";
    } else {
        ProQuilt kept_quilt = nullptr;
        if (ProQuiltInit((ProSolid)board, kept_id, &kept_quilt))
            area_after.reason = "kept_quilt_init_failed";
        else
            area_after = quilt_area_native(kept_quilt);
    }

    J details =
        trim_area_fields(area_before, units, scale, "area_before_mm2", "area_before_status");
    J after = trim_area_fields(area_after, units, scale, "area_after_mm2", "area_after_status");
    for (auto it = after.begin(); it != after.end(); ++it)
        details[it.key()] = it.value();
    details["keep_side"] = keep_side;
    details["kept_quilt_id"] = kept_id < 0 ? J(nullptr) : J(kept_id);
    details["kept_quilt_source"] = kept_source ? J(kept_source) : J(nullptr);
    // §4.5 kept_side_basis. tool_normal is a real read only for a datum-plane
    // tool; centroids have no documented quilt query here, so they stay null
    // instead of being estimated from a bounding box, and signed_offset_mm is
    // null because it depends on them.
    J tool_normal_json = nullptr;
    if (tool_normal_known && scale.known)
        tool_normal_json = {tool_normal[0] * scale.scale, tool_normal[1] * scale.scale,
                            tool_normal[2] * scale.scale};
    details["kept_side_basis"] = {
        {"keep_side", keep_side},
        {"primary_quilt_side_value", primary_side},
        {"material_side_value", PRO_TRIM_MATL_SIDE_ONE},
        {"tool_normal", tool_normal_json},
        {"target_centroid", nullptr},
        {"kept_centroid", nullptr},
        {"signed_offset_mm", nullptr},
        {"centroid_status",
         {{"available", false},
          {"reason", "quilt_centroid_not_measured"},
          {"note", "the retained-side direction is not enforced until a live serial window "
                   "measures the one/two binding (plan S02 step 3, contract §4.5 P3)"}}},
    };
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE)
        throw std::runtime_error(
            "Surface trim regeneration failed; check that the tool actually intersects the "
            "target quilt and that keep_side names the retained region");
    // Honest success test: a trim that removes nothing is a failure, not a
    // success with equal areas. Unit-unknown runs keep their null areas and
    // are judged by the geometry statuses instead.
    if (area_before.available && area_after.available && area_after.value >= area_before.value)
        throw std::runtime_error(
            "Surface trim removed no area (before=" + std::to_string(area_before.value) +
            " after=" + std::to_string(area_after.value) +
            " native units); the tool does not cut this target quilt");
    if (!area_after.available)
        throw std::runtime_error("Surface trim produced no measurable retained region" +
                                 std::string(area_after.reason ? ": " : "") +
                                 (area_after.reason ? area_after.reason : ""));
    remember(op, feature,
             {{"quilt_id", kept_id < 0 ? J(nullptr) : J(kept_id)},
              {"kept_quilt_source", kept_source ? J(kept_source) : J(nullptr)}});
}
