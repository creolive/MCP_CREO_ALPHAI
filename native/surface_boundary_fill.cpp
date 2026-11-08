// surface_boundary_fill.cpp — DEV-074/H09: fill one closed non-planar boundary.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.12 (offline rationale and
// open questions), §4.4.2 (status-shaped measurements). The route reuses the
// only documented boundary-blend tree on this SDK (Probbl.h, §2.1): the same
// bare skeleton surface_loft already creates through
// PRO_FEAT_CR_INCOMPLETE_FEAT/extract/redefine, with one chain holder per
// boundary curve and PRO_E_BBL_ADD_CLOSED set for the closed loop. Probbl.h
// documents PRO_E_BBL_ADD_CLOSED as workable from three curves, which is why
// the schema and this entry point both require at least three.
//
// The input is one ordered closed chain of curve geometry ids. This file
// samples each curve's endpoints with ProCurveXyzdataEval and refuses a chain
// that is open, out of order or repeated, so a typo never becomes a silently
// different surface. It does not write any optional value the kernel owns
// (tangency conditions are still filled by the extracted tree).
//
// This file is included by generic.cpp after the shared element-tree,
// selection, quilt and measurement helpers are visible; it defines no entry
// point of its own beyond generic_surface_boundary_fill.
#include <ProCurve.h>

static constexpr int SURFACE_BOUNDARY_FILL_MIN_CURVES = 3;
static constexpr int SURFACE_BOUNDARY_FILL_MAX_CURVES = 200;
// Same join tolerance surface_group_measure publishes as its default: a chain
// whose endpoints are farther apart than this is not one closed loop.
static constexpr double SURFACE_BOUNDARY_FILL_TOLERANCE_MM = 0.01;
static constexpr double SURFACE_BOUNDARY_FILL_GROUP_TOLERANCE_MM = 0.01;
static constexpr double SURFACE_BOUNDARY_FILL_GROUP_GAP_SEARCH_MM = 1.0;

struct BoundaryFillCurve {
    int id = -1;
    double start[3] = {0.0, 0.0, 0.0};
    double end[3] = {0.0, 0.0, 0.0};
};

struct BoundaryFillFaces {
    std::vector<int> ids;
    bool visit_ok = true;
    ProError query_code = PRO_TK_NO_ERROR;
};

static double boundary_fill_distance(const double a[3], const double b[3]) {
    const double dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

static void boundary_fill_copy(double target[3], const double source[3]) {
    for (int axis = 0; axis < 3; axis++)
        target[axis] = source[axis];
}

// One boundary item is one curve geometry id. ProCurveInit is the admission
// test: a quilt, a solid face or an edge id does not initialize as a curve.
static BoundaryFillCurve boundary_fill_curve(const J &reference, int index) {
    const std::string where = "surface_boundary_fill boundary[" + std::to_string(index) + "]";
    if (!reference.is_object() || reference.value("kind", std::string()) != "curve")
        throw std::runtime_error(
            where + " must be {kind:\"curve\",id:N}; a quilt, face, edge, body or feature "
                    "label is not a boundary curve");
    const J &raw_id = reference.at("id");
    if (!raw_id.is_number_integer() || raw_id < 0 || raw_id > 2147483647)
        throw std::runtime_error(where + ".id must be a nonnegative 32-bit integer");
    BoundaryFillCurve result;
    result.id = raw_id.get<int>();
    ProCurve curve = nullptr;
    ProError init_code = ProCurveInit((ProSolid)board, result.id, &curve);
    if (init_code || !curve)
        throw std::runtime_error(
            where + " curve " + std::to_string(result.id) +
            " is not a resolvable curve geometry id (code " + std::to_string((int)init_code) +
            "); pass the {kind:\"curve\",id:N} item from creo_inspect_model, not a quilt, face "
            "or edge, and build a missing edge with creo_project_curve");
    ProVector start, end;
    CK(ProCurveXyzdataEval(curve, 0.0, start, nullptr, nullptr));
    CK(ProCurveXyzdataEval(curve, 1.0, end, nullptr, nullptr));
    boundary_fill_copy(result.start, start);
    boundary_fill_copy(result.end, end);
    return result;
}

// Closest distance between the two curves' endpoint sets. Curve parameter
// direction is not part of the public reference syntax, so a matched end may be
// either endpoint; order is still enforced because only consecutive curves may
// touch.
static double boundary_fill_link_gap(const BoundaryFillCurve &a, const BoundaryFillCurve &b) {
    double gap = boundary_fill_distance(a.end, b.start);
    gap = std::min(gap, boundary_fill_distance(a.end, b.end));
    gap = std::min(gap, boundary_fill_distance(a.start, b.start));
    gap = std::min(gap, boundary_fill_distance(a.start, b.end));
    return gap;
}

static std::string boundary_fill_pair(const std::vector<BoundaryFillCurve> &curves, size_t second) {
    return std::to_string(curves[second - 1].id) + " and " + std::to_string(curves[second].id);
}

// Returns the largest measured link gap in native units. `scale` converts the
// message distances to mm; the caller already refused an unknown unit.
static double boundary_fill_check_chain(const std::vector<BoundaryFillCurve> &curves,
                                        double tolerance_native, double scale) {
    double max_gap = 0.0;
    for (size_t index = 1; index < curves.size(); index++) {
        const double gap = boundary_fill_link_gap(curves[index - 1], curves[index]);
        max_gap = std::max(max_gap, gap);
        if (gap > tolerance_native)
            throw std::runtime_error(
                "surface_boundary_fill boundary curves " + boundary_fill_pair(curves, index) +
                " are not connected in the submitted order (closest endpoints are " +
                std::to_string(gap * scale) + " mm apart, tolerance " +
                std::to_string(SURFACE_BOUNDARY_FILL_TOLERANCE_MM) +
                " mm); reorder the chain so each curve meets the next one, or rebuild the "
                "missing edge with creo_project_curve / creo_surface_loft");
    }
    const double closing = boundary_fill_link_gap(curves.back(), curves.front());
    max_gap = std::max(max_gap, closing);
    if (closing > tolerance_native)
        throw std::runtime_error(
            "surface_boundary_fill boundary chain is open: the last curve " +
            std::to_string(curves.back().id) + " does not meet the first curve " +
            std::to_string(curves.front().id) + " (gap " + std::to_string(closing * scale) +
            " mm, tolerance " + std::to_string(SURFACE_BOUNDARY_FILL_TOLERANCE_MM) +
            " mm); surface_boundary_fill fills a closed loop only - close the boundary first, "
            "or use creo_surface_loft for a surface between two sections");
    return max_gap;
}

static ProError boundary_fill_face_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *faces = (BoundaryFillFaces *)data;
    if (status) {
        faces->visit_ok = false;
        faces->query_code = status;
        return PRO_TK_NO_ERROR;
    }
    int id = -1;
    if (!ProSurfaceIdGet(surface, &id))
        faces->ids.push_back(id);
    return PRO_TK_NO_ERROR;
}

static BoundaryFillFaces boundary_fill_faces(ProQuilt quilt) {
    BoundaryFillFaces faces;
    ProError code = ProQuiltSurfaceVisit(quilt, boundary_fill_face_cb, nullptr, &faces);
    if (code) {
        faces.visit_ok = false;
        faces.query_code = code;
    }
    return faces;
}

// §4.4.2 face count projection: a failed visit or an empty quilt is null with
// its own reason, never a fabricated zero.
static J boundary_fill_face_count_status(const BoundaryFillFaces &faces,
                                         const InspectionLengthUnits &units,
                                         const MillimeterScale &scale) {
    MeasurementOutcome outcome;
    outcome.available = faces.visit_ok && faces.query_code == PRO_TK_NO_ERROR && !faces.ids.empty();
    outcome.query_code = faces.query_code;
    outcome.reason = !faces.visit_ok || faces.query_code ? "quilt_surface_visit_failed"
                     : faces.ids.empty()                 ? "quilt_has_no_surfaces"
                                                         : nullptr;
    outcome.value = (double)faces.ids.size();
    return measurement_status_json(outcome, units, scale);
}

static J boundary_fill_tree_json(ProElement root) {
    int budget = SURFACE_LOFT_TREE_SAMPLE_LIMIT;
    return {{"limit", SURFACE_LOFT_TREE_SAMPLE_LIMIT},
            {"truncated", false},
            {"root", loft_element_json(root, 0, budget)},
            {"elements_read", SURFACE_LOFT_TREE_SAMPLE_LIMIT - budget}};
}

static void generic_surface_boundary_fill(const J &op) {
    const J &boundary = op.at("boundary");
    if (!boundary.is_array() || (int)boundary.size() < SURFACE_BOUNDARY_FILL_MIN_CURVES)
        throw std::runtime_error(
            "surface_boundary_fill needs at least " +
            std::to_string(SURFACE_BOUNDARY_FILL_MIN_CURVES) +
            " ordered boundary curves (the closed blend flag is only workable from 3 curves); "
            "split the loop into 3 or more curves, or use surface_loft for a two-curve boundary");
    if ((int)boundary.size() > SURFACE_BOUNDARY_FILL_MAX_CURVES)
        throw std::runtime_error("surface_boundary_fill accepts at most " +
                                 std::to_string(SURFACE_BOUNDARY_FILL_MAX_CURVES) +
                                 " boundary curves");

    std::vector<BoundaryFillCurve> curves;
    curves.reserve(boundary.size());
    std::set<int> seen;
    for (int index = 0; index < (int)boundary.size(); index++) {
        const BoundaryFillCurve curve = boundary_fill_curve(boundary[index], index);
        if (!seen.insert(curve.id).second)
            throw std::runtime_error(
                "surface_boundary_fill boundary curve " + std::to_string(curve.id) +
                " is repeated; remove the duplicate edge so every curve appears once");
        curves.push_back(curve);
    }

    // The published closure/order tolerance is in millimetres, so an unknown
    // length unit cannot be judged and is refused instead of guessed.
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    if (!scale.known || !std::isfinite(scale.scale) || !(scale.scale > 0.0))
        throw std::runtime_error(
            "surface_boundary_fill cannot verify the closed chain or report its area because "
            "the model's length unit is unknown (unit query code " +
            std::to_string((int)scale.unit_query_code) +
            "); set the model length unit (mm recommended) and retry");
    const double tolerance_native = SURFACE_BOUNDARY_FILL_TOLERANCE_MM / scale.scale;
    const double chain_gap_max = boundary_fill_check_chain(curves, tolerance_native, scale.scale);

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    integer(root, PRO_E_DTM_SRF_TYPE, PRO_E_DTM_SRF_TYPE_BND_BLEND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProElement blend = node(root, PRO_E_BNBLN_CURVES);
    ProElement direction = node(blend, PRO_E_BNBLN_1DIR);
    ProElement holders = node(direction, PRO_E_BNBLN_DIR_CURVES);
    for (const auto &curve : curves) {
        ProElement holder = node(holders, PRO_E_STD_CHAIN_HOLDER);
        curve_collection(node(holder, PRO_E_STD_CURVE_COLLECTION_APPL),
                         J::array({{{"kind", "curve"}, {"id", curve.id}}}));
    }
    // Probbl.h: this closes the surface across the first direction and is
    // documented as workable from three curves. The ordered chain supplies the
    // boundary; the kernel owns every other optional value.
    integer(direction, PRO_E_BBL_ADD_CLOSED, PRO_B_TRUE);

    J details = {{"op", "surface_boundary_fill"},
                 {"boundary", boundary},
                 {"boundary_curve_ids", J::array()},
                 {"boundary_edges", (int)curves.size()},
                 {"boundary_closed", true},
                 {"boundary_tolerance_mm", SURFACE_BOUNDARY_FILL_TOLERANCE_MM},
                 {"chain_gap_max_mm", chain_gap_max * scale.scale},
                 {"route", "probbl_boundary_blend_closed_chain"},
                 {"add_closed", true}};
    for (const auto &curve : curves)
        details["boundary_curve_ids"].push_back(curve.id);

    // INCOMPLETE lets the kernel fill the defaults it owns; the extracted tree
    // is then the completed tree for ProFeatureWithoptionsRedefine. A failed
    // create keeps its element-error list in the receipt instead of only in
    // native.log.
    ProModelitem item;
    CK(ProMdlToModelitem(board, &item));
    ProSelection solid_selection = nullptr;
    CK(ProSelectionAlloc(nullptr, &item, &solid_selection));
    ProFeatureCreateOptions *options = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&options));
    options[0] = PRO_FEAT_CR_INCOMPLETE_FEAT;
    ProFeature feature = {};
    ProErrorlist element_errors = {};
    ProError created = ProFeatureWithoptionsCreate(solid_selection, root, options,
                                                   PRO_REGEN_NO_FLAGS, &feature, &element_errors);
    errors(element_errors);
    ProArrayFree((ProArray *)&options);
    ProSelectionFree(&solid_selection);
    details["create_code"] = (int)created;
    J create_sample = J::array();
    for (int index = 0; index < element_errors.error_number && index < FEATURE_ERROR_SAMPLE_LIMIT;
         index++)
        create_sample.push_back({{"element", element_errors.error_list[index].err_item_id},
                                 {"type", element_errors.error_list[index].err_item_type},
                                 {"error", element_errors.error_list[index].error}});
    details["create_element_errors"] = {{"total", element_errors.error_number},
                                        {"sample", create_sample}};
    if (created != PRO_TK_NO_ERROR) {
        last_feature_error_report = feature_error_report("ProFeatureWithoptionsCreate", created,
                                                         "surface_boundary_fill_create");
        stage_operation_result(details);
        throw std::runtime_error(
            "surface_boundary_fill boundary blend create failed (code " +
            std::to_string((int)created) + ", " + std::to_string((int)curves.size()) +
            " boundary curves); the kernel may reject this closed chain as one blend direction "
            "- see create_element_errors");
    }
    ProElementFree(&root);

    ProElement extracted = nullptr;
    ProError extract_code =
        ProFeatureElemtreeExtract(&feature, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &extracted);
    details["extract_code"] = (int)extract_code;
    if (extract_code || !extracted) {
        stage_operation_result(details);
        throw std::runtime_error(
            "surface_boundary_fill cannot extract the created feature tree (code " +
            std::to_string((int)extract_code) + ")");
    }
    J tree_json = boundary_fill_tree_json(extracted);
    log("SURFACE_BOUNDARY_FILL_TREE=%s\n", tree_json.dump().c_str());
    details["tree_elements_read"] = tree_json["elements_read"];

    // The extracted tree carries the kernel's own defaults; redefining with it
    // is the regeneration the incomplete create skipped. A failure keeps the
    // tree sample so the missing element is visible.
    try {
        redefine(&feature, extracted);
    } catch (...) {
        details["extracted_tree"] = tree_json;
        stage_operation_result(details);
        CK(ProFeatureElemtreeFree(&feature, extracted));
        throw;
    }
    CK(ProFeatureElemtreeFree(&feature, extracted));

    ProFeatStatus status = PRO_FEAT_ACTIVE;
    CK(ProFeatureStatusGet(&feature, &status));
    details["feature_id"] = (int)feature.id;
    details["feature_status"] = (int)status;
    ProFeattype feature_type = 0;
    CK(ProFeatureTypeGet(&feature, &feature_type));
    details["feature_type"] = (int)feature_type;

    J quilts = J::array();
    ProError quilt_visit =
        ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &quilts);
    details["quilt_visit_code"] = (int)quilt_visit;
    details["quilt_count"] = (int)quilts.size();
    details["quilt_ids"] = quilts;
    const int quilt_id = quilts.size() == 1 ? quilts[0]["id"].get<int>() : -1;
    details["quilt_id"] = quilt_id < 0 ? J(nullptr) : J(quilt_id);

    MeasurementOutcome area, closed;
    BoundaryFillFaces faces;
    if (quilt_id >= 0) {
        ProQuilt quilt = nullptr;
        ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
        details["quilt_init_code"] = (int)init_code;
        if (!init_code) {
            area = quilt_area_native(quilt);
            closed = quilt_closed_native(quilt);
            faces = boundary_fill_faces(quilt);
        } else {
            area.reason = "quilt_init_failed";
            area.query_code = init_code;
            closed.reason = "quilt_init_failed";
            closed.query_code = init_code;
            faces.visit_ok = false;
            faces.query_code = init_code;
        }
    } else {
        area.reason = "quilt_geometry_missing";
        closed.reason = "quilt_geometry_missing";
        faces.visit_ok = false;
        faces.query_code = PRO_TK_E_NOT_FOUND;
    }
    details.update(area_fields_json(area, units, scale, "surface_area_mm2", "surface_area_status"));
    const char *closure = quilt_closed_is_open(closed) ? "open"
                          : closed.available           ? "closed"
                                                       : "unknown";
    details["quilt_closed_native"] = closure;
    details["closure"] = {{"available", closed.available},
                          {"query_code", (int)closed.query_code},
                          {"reason", closed.reason ? J(closed.reason) : J(nullptr)}};
    details["face_count"] =
        faces.visit_ok && faces.query_code == PRO_TK_NO_ERROR && !faces.ids.empty()
            ? J((int)faces.ids.size())
            : J(nullptr);
    details["face_count_status"] = boundary_fill_face_count_status(faces, units, scale);
    J state = inspection(false);
    details["has_solid"] = state["has_solid"];
    details["solid_surface_count"] = state.contains("surfaces") && state["surfaces"].is_array()
                                         ? J((int)state["surfaces"].size())
                                         : J(nullptr);
    details["surface_type"] =
        feature_type == PRO_FEAT_DATUM_SURF ? J("datum_surface") : J("unknown");
    // The result quilt's own boundary is a group too, so the boundary edge
    // count is measured rather than assumed. A single filled quilt reports its
    // exposed edges; an unavailable measurement stays null with a reason.
    J group = quilt_id >= 0
                  ? surface_group_receipt({quilt_id}, SURFACE_BOUNDARY_FILL_GROUP_TOLERANCE_MM,
                                          SURFACE_BOUNDARY_FILL_GROUP_GAP_SEARCH_MM)
                  : J(nullptr);
    details["surface_group"] = group;
    if (group.is_object() && group.contains("group") && group["group"].is_object() &&
        group["group"].contains("boundary_edges"))
        details["boundary_edges"] = group["group"]["boundary_edges"];
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE) {
        details["extracted_tree"] = tree_json;
        stage_operation_result(details);
        last_feature_error_report = feature_error_report("ProFeatureStatusGet", (ProError)status,
                                                         "surface_boundary_fill_regeneration");
        throw std::runtime_error(
            "surface_boundary_fill boundary blend regeneration failed (feature_status=" +
            std::to_string((int)status) + ", feature_id=" + std::to_string((int)feature.id) +
            ", quilt_count=" + std::to_string((int)quilts.size()) +
            "); the closed chain did not produce a regenerated surface");
    }
    if (feature_type != PRO_FEAT_DATUM_SURF)
        throw std::runtime_error("surface_boundary_fill produced feature type " +
                                 std::to_string((int)feature_type) + " instead of a datum surface");
    if (quilts.size() != 1)
        throw std::runtime_error(
            "surface_boundary_fill produced " + std::to_string((int)quilts.size()) +
            " quilt geometry items (visit code " + std::to_string((int)quilt_visit) +
            "); exactly one filled surface is required");
    if (!area.available)
        throw std::runtime_error(std::string("surface_boundary_fill surface is not measurable") +
                                 (area.reason ? ": " : "") + (area.reason ? area.reason : ""));
    if (details["has_solid"].get<bool>())
        throw std::runtime_error(
            "surface_boundary_fill created solid material; a boundary fill must not");
    if (!quilt_closed_is_open(closed))
        throw std::runtime_error(
            "surface_boundary_fill result must be an open quilt; ProQuiltVolumeEval reported " +
            std::string(closure) + " (code " + std::to_string((int)closed.query_code) + ")");
    if (!faces.visit_ok || faces.query_code != PRO_TK_NO_ERROR || faces.ids.empty())
        throw std::runtime_error("surface_boundary_fill cannot read the result quilt faces (code " +
                                 std::to_string((int)faces.query_code) +
                                 "); the boundary blend produced no measurable face");

    remember(op, feature,
             {{"quilt_id", quilt_id}, {"boundary_curve_ids", details["boundary_curve_ids"]}});
}
