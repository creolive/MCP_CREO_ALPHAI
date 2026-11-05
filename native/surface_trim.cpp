// surface_trim.cpp — FEAT-039/S02: the high-level surface trim.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.3 (the documented
// ProTrim.h trees), §3.3 (first-release boundary), §4.4.2/§4.5 (measurement and
// retained-side fields). This module reuses the S01 quilt reference resolution
// and the shared quilt measurement; it never enumerates quilts itself and never
// invents a retained side.
//
// Two documented variants are built: "Use Quilt" (tool = quilt or datum plane)
// and "Use Curve" (tool = one curve, ProTrim.h §3.1/§3.2). The curve variant is
// what lets a projected curve trim the quilt it was projected onto.
//
// This file is included by generic.cpp after the shared element-tree,
// inspection and quilt helpers are visible; it defines no entry point of its
// own beyond generic_surface_trim.
#include <ProTrim.h>

struct SurfaceTrimTool {
    ProSelection selection = nullptr;
    std::string kind; // "quilt" | "datum_plane" | "curve"
    ProVector normal = {0.0, 0.0, 0.0};
    bool normal_known = false;
    int curve_id = -1;
};

// The tool side of the trim tree. A quilt reference goes through the S01
// resolver; a datum plane is resolved as its owning feature and also yields
// the real plane normal for kept_side_basis (§4.5); a curve is resolved as the
// curve geometry item itself, which is what PRO_E_STD_CURVE_COLLECTION_APPL
// takes.
static SurfaceTrimTool surface_trim_tool(const J &reference) {
    SurfaceTrimTool tool;
    std::string kind = reference.value("kind", "");
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    if (kind == "quilt" || kind == "quilt_feature") {
        tool.kind = "quilt";
        tool.selection = resolve_quilt_reference(reference, (ProSolid)board, units, scale);
        return tool;
    }
    if (kind == "datum_plane") {
        tool.kind = "datum_plane";
        tool.selection = resolve({{"kind", "datum_feature"}, {"label", reference.at("label")}});
        // resolve() leaves exactly one entry in `planes` for a datum feature.
        if (planes.size() == 1) {
            for (int i = 0; i < 3; i++)
                tool.normal[i] = planes[0].n[i];
            tool.normal_known = true;
        }
        return tool;
    }
    if (kind == "curve" || kind == "curve_feature") {
        tool.kind = "curve";
        tool.selection = resolve(reference);
        tool.curve_id = reference.contains("id") ? reference["id"].get<int>() : -1;
        return tool;
    }
    throw std::runtime_error("surface_trim tool must be one quilt, one datum plane or one "
                             "curve; kind '" +
                             kind + "' is not a trimming tool");
}

// The retained region after the trim. Review focus 1 of the plan, confirmed on
// hardware (2026-11-04): visiting PRO_QUILT on a trim feature returns -4, the
// same failure 0.11.7 F03 reported. A trim re-trims the target quilt instead
// of owning a new geometry item, so a failed visit is not fatal: fall back to
// the target quilt and record the visit code plus where the id came from.
static int surface_trim_kept_quilt(ProFeature feature, int target_id, const char *&source,
                                   ProError &visit_code) {
    J ids = J::array();
    visit_code = ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &ids);
    if (visit_code == PRO_TK_NO_ERROR) {
        if (ids.size() == 1) {
            source = "feature_quilt_geomitem";
            return ids[0]["id"];
        }
        if (ids.size() > 1)
            throw std::runtime_error("Trim feature owns " + std::to_string((int)ids.size()) +
                                     " quilts; the retained region is ambiguous");
    }
    // No directly owned geometry item: the result is the re-trimmed target.
    ProQuilt requery = nullptr;
    if (ProQuiltInit((ProSolid)board, target_id, &requery))
        return -1;
    source = visit_code == PRO_TK_NO_ERROR ? "retrimmed_target_quilt"
                                           : "retrimmed_target_quilt_visit_failed";
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
    int target_id = quilt_selection_id(target_selection);
    ProQuilt target_quilt = nullptr;
    MeasurementOutcome area_before;
    if (ProQuiltInit((ProSolid)board, target_id, &target_quilt)) {
        area_before.reason = "target_quilt_init_failed";
    } else {
        area_before = quilt_area_native(target_quilt);
    }

    SurfaceTrimTool tool = surface_trim_tool(op.at("tool"));

    // §4.5: keep_side selects the retained region. The 2026-11-04 live probe
    // (build/_live_trim_probe.py) measured that PRO_E_PRIMARY_QLTSIDE alone does
    // not move the retained region: keep_side one and two both kept the same
    // 700 mm2 side of an asymmetric plane cut through the 40x20 fill. The
    // material side is the element that flips it, so both elements follow
    // keep_side and can never disagree.
    int primary_side = keep_side == "one" ? PRO_TRIM_PRIM_QLT_SIDE_ONE : PRO_TRIM_PRIM_QLT_SIDE_TWO;
    int material_side = keep_side == "one" ? PRO_TRIM_MATL_SIDE_ONE : PRO_TRIM_MATL_SIDE_TWO;

    bool curve_tool = tool.kind == "curve";
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CUT);
    if (!curve_tool)
        integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    // PRO_E_SRF_TRIM_TYPE is non-redefinable mandatory; both type elements must
    // agree (ProTrim.h §2.1/§3.1). The use-curve tree has no FEATURE_FORM and
    // takes its trimming geometry from PRO_E_STD_CURVE_COLLECTION_APPL.
    integer(root, PRO_E_SRF_TRIM_TYPE, curve_tool ? PRO_SURF_TRIM_USE_CRV : PRO_SURF_TRIM_USE_QLT);
    integer(root, PRO_E_SURF_TRIM_TYPE, curve_tool ? PRO_SURF_TRIM_USE_CRV : PRO_SURF_TRIM_USE_QLT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ref(root, PRO_E_TRIM_QUILT, target_selection);
    if (curve_tool)
        curve_collection(node(root, PRO_E_STD_CURVE_COLLECTION_APPL), J::array({op.at("tool")}));
    else
        ref(root, PRO_E_STD_USEQLT_QLT, tool.selection);
    // "Keep trim surface" stays off in this release; only the two side
    // elements follow keep_side.
    integer(root, PRO_E_MATERIAL_SIDE, material_side);
    integer(root, PRO_E_PRIMARY_QLTSIDE, primary_side);
    if (!curve_tool)
        integer(root, PRO_E_KEEP_TRIM_SURF_OPT, PRO_KEEP_TRIM_SURF_OPT_NO);
    // FEAT-039/S07: the documented thin-trim route (ProTrim.h §4.1) offsets the
    // trimming surface by PRO_E_THICKNESS along PRO_E_STD_USEQLT_SIDE before it
    // cuts, so the distance and its direction are explicit instead of inherited
    // from a GUI view.
    bool offset_tool = !curve_tool && op.contains("offset_mm");
    if (offset_tool) {
        real(root, PRO_E_THICKNESS, op["offset_mm"]);
        integer(root, PRO_E_STD_USEQLT_SIDE,
                op["offset_side"] == "one" ? PRO_TRIM_STD_QUILT_SIDE_ONE
                                           : PRO_TRIM_STD_QUILT_SIDE_TWO);
        integer(root, PRO_E_SRF_OFFS_METHOD, PRO_TRIM_SRF_OFFS_METH_NORMTOSURF);
    }
    ProFeature feature = create(root);
    ProElementFree(&root);
    ProSelectionFree(&target_selection);
    ProSelectionFree(&tool.selection);

    // A use-curve trim resolves its trimming geometry during regeneration: read
    // straight after creation and the feature is PRO_FEAT_FAILED even though
    // the kernel accepted the tree (live 2026-11-04, feature_status=6 with an
    // unchanged area). The use-quilt variant is active at that point, so only
    // the curve variant pays for the extra regenerate.
    if (curve_tool)
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));

    ProFeatStatus status;
    CK(ProFeatureStatusGet(&feature, &status));

    const char *kept_source = nullptr;
    ProError kept_visit_code = PRO_TK_NO_ERROR;
    int kept_id = surface_trim_kept_quilt(feature, target_id, kept_source, kept_visit_code);
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
        area_fields_json(area_before, units, scale, "area_before_mm2", "area_before_status");
    J after = area_fields_json(area_after, units, scale, "area_after_mm2", "area_after_status");
    for (auto it = after.begin(); it != after.end(); ++it)
        details[it.key()] = it.value();
    details["keep_side"] = keep_side;
    details["offset_mm"] = offset_tool ? op["offset_mm"] : J(nullptr);
    details["offset_side"] = offset_tool ? op["offset_side"] : J(nullptr);
    details["kept_quilt_id"] = kept_id < 0 ? J(nullptr) : J(kept_id);
    details["kept_quilt_source"] = kept_source ? J(kept_source) : J(nullptr);
    // Where the retained id came from, and what the direct visit said. F03's
    // -4 stays visible instead of being hidden behind a fallback.
    details["kept_quilt_visit_code"] = (int)kept_visit_code;
    // §4.5 kept_side_basis. tool_normal is a real read only for a datum-plane
    // tool; centroids have no documented quilt query here, so they stay null
    // instead of being estimated from a bounding box, and signed_offset_mm is
    // null because it depends on them.
    J tool_normal_json = nullptr;
    if (tool.normal_known && scale.known)
        tool_normal_json = {tool.normal[0] * scale.scale, tool.normal[1] * scale.scale,
                            tool.normal[2] * scale.scale};
    details["kept_side_basis"] = {
        {"keep_side", keep_side},
        {"tool_kind", tool.kind},
        {"tool_curve_id", curve_tool && tool.curve_id >= 0 ? J(tool.curve_id) : J(nullptr)},
        // A curve tool has no normal of its own: ProTrim.h defines its two sides
        // along the curve direction, so nothing is reported where a plane normal
        // would be.
        {"side_reference", curve_tool ? "curve_direction" : "tool_plane_normal"},
        {"primary_quilt_side_value", primary_side},
        {"material_side_value", material_side},
        {"tool_normal", tool_normal_json},
        {"target_centroid", nullptr},
        {"kept_centroid", nullptr},
        {"signed_offset_mm", nullptr},
        {"centroid_status",
         {{"available", false},
          {"reason", "quilt_centroid_not_measured"},
          {"note", "the retained side is proven by the measured area of the two independent "
                   "keep_side runs; a quilt centroid query is still unavailable"}}},
    };
    // A trim that does not regenerate is a hard failure, but the caller needs
    // the raw reason instead of a guess: the status code, the resolved ids and
    // whether the tool was a datum plane or a quilt. The block is staged with
    // the measurement fields already taken, so the failed operation record
    // carries both sides (execute_operation keeps the staged result).
    if (status != PRO_FEAT_ACTIVE) {
        J owned = J::array();
        ProError owned_code =
            ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &owned);
        details["regeneration"] = {{"failed_stage", "surface_trim_regeneration"},
                                   {"feature_id", feature.id},
                                   {"feature_status", (int)status},
                                   {"target_quilt_id", target_id},
                                   {"tool_kind", tool.kind},
                                   {"primary_quilt_side_value", primary_side},
                                   {"material_side_value", material_side},
                                   {"owned_quilt_visit_code", (int)owned_code},
                                   {"owned_quilt_ids", owned}};
        stage_operation_result(details);
        throw std::runtime_error(
            "Surface trim regeneration failed (feature_status=" + std::to_string((int)status) +
            ", feature_id=" + std::to_string(feature.id) + ", target_quilt_id=" +
            std::to_string(target_id) + ", tool=" + tool.kind + ", keep_side=" + keep_side +
            "); check that the tool actually intersects the target quilt");
    }
    stage_operation_result(details);
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
