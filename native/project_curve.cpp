// project_curve.cpp — FEAT-039/S04: project one curve onto one quilt.
//
// Route evidence (live, 2026-11-04): the local SDK documents no parent-child
// tree for either projection family. The five PRO_E_COPYTRIM_* elements and the
// five PRO_E_PROJ_CRV_* elements appear only in ProElemId.h, and every layout
// built from them is rejected by ProFeatureWithoptionsCreate with -1 (three
// COPYTRIM layouts, four PROJECT layouts). The only documented tree of this
// family is ProDtmCrv.h "INTERSECT" (PRO_CURVE_TYPE_INTSRF), which the same
// machine accepts.
//
// So the projection is built in two documented steps instead of one
// undocumented feature:
//
//   1. sweep the source curve's own sketch along the requested direction as a
//      datum surface (ProExtrude.h tree, symmetric blind depth);
//   2. intersect that surface with the target quilt (ProDtmCrv.h INTERSECT).
//
// The result is the true projection of the source curve along the direction:
// the swept surface contains every point of the curve translated along the
// direction, so its intersection with the quilt is exactly the projected curve.
// The helper surface is a real, reported feature and stays in the model,
// because deleting it would delete the curve that depends on it.
//
// Limitations are reported, never hidden: the direction must be parallel to the
// source sketch normal (the documented extrude tree only sweeps along it), the
// target must really lie on the requested side, and a projection that yields
// zero or several curves fails instead of returning one of them.
#include <ProDtmCrv.h>
#include <ProExtrude.h>
#include <ProGeomitem.h>

// §4.3 direction rules: the vector comes from real geometry (datum plane normal,
// datum axis direction or a straight curve chord), is normalized here, and a
// zero or non-finite vector is refused before any feature is created.
struct ProjectDirection {
    V vector{0.0, 0.0, 0.0};
    const char *basis = "unresolved";
    double length = 0.0;
};

static ProjectDirection project_direction_from_reference(const J &reference) {
    ProjectDirection result;
    std::string kind = reference.at("kind");
    V raw{0.0, 0.0, 0.0};
    if (kind == "datum_feature") {
        ProFeature f = feature(reference.at("label"));
        ProFeattype type;
        CK(ProFeatureTypeGet(&f, &type));
        if (type != PRO_FEAT_DATUM)
            throw std::runtime_error("project_curve direction_ref must name a datum plane or "
                                     "datum axis feature");
        planes.clear();
        CK(ProFeatureGeomitemVisit(&f, PRO_SURFACE, geom_cb, nullptr, nullptr));
        if (planes.size() != 1)
            throw std::runtime_error("project_curve direction_ref datum feature does not own "
                                     "exactly one plane");
        raw = {planes[0].n[0], planes[0].n[1], planes[0].n[2]};
        result.basis = "datum_plane_normal";
    } else if (kind == "datum_axis_feature") {
        ProFeature f = feature(reference.at("label"));
        J ids = J::array();
        CK(ProFeatureGeomitemVisit(&f, PRO_AXIS, collect_geom_ids, nullptr, &ids));
        if (ids.size() != 1)
            throw std::runtime_error("project_curve direction_ref datum axis feature must own "
                                     "exactly one axis");
        ProGeomitem item = {};
        CK(ProModelitemInit(board, ids[0]["id"].get<int>(), PRO_AXIS, &item));
        AxisGeometry geometry = inspect_axis_geometry(&item);
        if (!geometry.known)
            throw std::runtime_error("project_curve direction_ref axis direction is not readable");
        raw = {geometry.direction[0], geometry.direction[1], geometry.direction[2]};
        result.basis = "datum_axis_direction";
    } else if (kind == "curve") {
        ProGeomitem item = {};
        CK(ProModelitemInit(board, reference.at("id").get<int>(), PRO_CURVE, &item));
        ProCurve curve = nullptr;
        CK(ProGeomitemToCurve(&item, &curve));
        MeasurementOutcome ends = curve_endpoints_native(curve);
        if (!ends.available)
            throw std::runtime_error(
                "project_curve direction_ref curve endpoints are not readable");
        double chord[3] = {curve_endpoint_end[0] - curve_endpoint_start[0],
                           curve_endpoint_end[1] - curve_endpoint_start[1],
                           curve_endpoint_end[2] - curve_endpoint_start[2]};
        raw = {chord[0], chord[1], chord[2]};
        result.basis = "straight_curve_chord";
    } else {
        throw std::runtime_error("project_curve direction_ref kind is not supported: " + kind);
    }

    double length = 0.0;
    bool finite = true;
    for (int i = 0; i < 3; i++) {
        finite = finite && std::isfinite(raw[i]);
        length = std::hypot(length, raw[i]);
    }
    result.length = length;
    if (!finite || !(length > 1e-9))
        throw std::runtime_error(
            "project_curve direction must not be zero or non-finite (direction_length=" +
            std::to_string(length) + ", basis=" + result.basis + ")");
    for (int i = 0; i < 3; i++)
        result.vector[i] = raw[i] / length;
    return result;
}

// Target bounds in native units, from the real member faces (§4.4 rule 1).
struct ProjectBounds {
    bool known = false;
    ProVector min{}, max{};
    ProError code = PRO_TK_NO_ERROR;
};
static ProjectBounds project_target_bounds(ProQuilt quilt) {
    ProjectBounds bounds;
    J surface_ids = J::array();
    QuiltFaceAccumulator faces;
    faces.surface_ids = &surface_ids;
    ProError code = ProQuiltSurfaceVisit(quilt, quilt_face_cb, nullptr, &faces);
    bounds.code = code ? code : (faces.bbox_ok ? PRO_TK_NO_ERROR : faces.bbox_code);
    bounds.known = !bounds.code && faces.face_count > 0 && faces.bbox_ok;
    for (int i = 0; i < 3; i++) {
        bounds.min[i] = faces.bb_min[i];
        bounds.max[i] = faces.bb_max[i];
    }
    return bounds;
}

static ProFeature project_helper_surface(const J &op, ProFeature source_owner, double depth,
                                         double sign) {
    ProSelection section = selection(source_owner.id, PRO_FEATURE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_EXTRUDE);
    integer(root, PRO_E_EXT_SURF_CUT_SOLID_TYPE, PRO_EXT_FEAT_TYPE_SURFACE);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label").get<std::string>() + "_sweep").c_str());
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, section);
    ProSelectionFree(&section);
    integer(root, PRO_E_STD_DIRECTION, sign > 0 ? 1 : -1);
    // Symmetric: the swept surface must reach the quilt whichever side of the
    // sketch plane it lies on; `side` is verified against the target bounds
    // instead of being silently assumed.
    ProElement dep = node(root, PRO_E_STD_EXT_DEPTH), from = node(dep, PRO_E_EXT_DEPTH_FROM),
               to = node(dep, PRO_E_EXT_DEPTH_TO);
    integer(from, PRO_E_EXT_DEPTH_FROM_TYPE, PRO_EXT_DEPTH_FROM_NONE);
    integer(to, PRO_E_EXT_DEPTH_TO_TYPE, PRO_EXT_DEPTH_SYMMETRIC);
    real(to, PRO_E_EXT_DEPTH_TO_VALUE, depth);
    ProFeature helper = create(root);
    ProElementFree(&root);
    return helper;
}

// The swept side may be one face (a straight source) or several faces that
// together form the sweep (live 2026-11-04: an arc sweep arrives as five
// cylindrical pieces). ProDtmCrv.h allows both through
// PRO_E_CRV_IP_REF_SEL1_TYPE: WHOLE takes the whole quilt of PF_QUILT, and
// MULTIPLE_SEL takes any number of PF_SURFACE selections.
static ProFeature project_intersect_curve(const J &op, const J &swept_faces, ProSelection second) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CURVE);
    // ProDtmCrv.h §INTERSECT: PRO_E_CRV_IP_REF_TYPE carries the same value as
    // PRO_E_CURVE_TYPE, both PRO_CURVE_TYPE_INTSRF.
    integer(root, PRO_E_CURVE_TYPE, PRO_CURVE_TYPE_INTSRF);
    integer(root, PRO_E_CRV_IP_REF_TYPE, PRO_CURVE_TYPE_INTSRF);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement one = node(root, PRO_E_CRV_IP_COMP_REF1);
    if (swept_faces.size() == 1) {
        ProSelection face = selection(swept_faces[0].get<int>(), PRO_SURFACE);
        ref(one, PRO_E_CRV_IP_REF1, face);
        ProSelectionFree(&face);
        integer(one, PRO_E_CRV_IP_REF_SEL1_TYPE, PRO_CURVE_TYPE_WHOLE);
    } else {
        J faces = J::array();
        for (auto &id : swept_faces)
            faces.push_back({{"kind", "surface"}, {"id", id}});
        set_refs(node(one, PRO_E_CRV_IP_REF1), faces);
        integer(one, PRO_E_CRV_IP_REF_SEL1_TYPE, PRO_CURVE_TYPE_MULTIPLE_SEL);
    }
    ProElement two = node(root, PRO_E_CRV_IP_COMP_REF2);
    ref(two, PRO_E_CRV_IP_REF2, second);
    integer(two, PRO_E_CRV_IP_REF_SEL2_TYPE, PRO_CURVE_TYPE_WHOLE);
    ProFeature curve = create(root);
    ProElementFree(&root);
    return curve;
}

static void generic_project_curve(const J &op) {
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);

    // Exactly one quilt target, exactly one curve source (schema-enforced).
    ProSelection target = resolve_quilt_reference(op.at("target"), (ProSolid)board, units, scale);
    int target_id = quilt_selection_id(target);
    int source_id = op.at("source").at("id").get<int>();
    ProSelection source = selection(source_id, PRO_CURVE);
    ProModelitem source_item = {};
    CK(ProSelectionModelitemGet(source, &source_item));
    ProCurve source_curve = nullptr;
    CK(ProGeomitemToCurve((ProGeomitem *)&source_item, &source_curve));
    MeasurementOutcome source_length = curve_length_native(source_curve);
    MeasurementOutcome source_ends = curve_endpoints_native(source_curve);
    if (!source_ends.available) {
        ProSelectionFree(&source);
        ProSelectionFree(&target);
        throw std::runtime_error(
            "project_curve source curve endpoints are not readable; the source must be a real "
            "single curve from creo_inspect_model");
    }
    double source_start[3] = {curve_endpoint_start[0], curve_endpoint_start[1],
                              curve_endpoint_start[2]};

    ProjectDirection direction = project_direction_from_reference(op.at("direction_ref"));
    std::string side = op.at("side");
    if (side == "negative")
        for (double &component : direction.vector)
            component = -component;

    // §3.2: the target must really lie on the requested side. The signed
    // distance of the quilt corners along the direction is measured, not
    // assumed, and a target entirely behind the source fails.
    ProQuilt target_quilt = nullptr;
    ProjectBounds bounds;
    if (ProQuiltInit((ProSolid)board, target_id, &target_quilt))
        bounds.code = PRO_TK_E_NOT_FOUND;
    else
        bounds = project_target_bounds(target_quilt);
    double reach = 0.0;
    bool target_ahead = false;
    if (bounds.known) {
        for (int corner = 0; corner < 8; corner++) {
            double signed_distance = 0.0;
            for (int axis = 0; axis < 3; axis++) {
                double value = (corner & (1 << axis)) ? bounds.max[axis] : bounds.min[axis];
                signed_distance += (value - source_start[axis]) * direction.vector[axis];
            }
            reach = std::max(reach, std::fabs(signed_distance));
            target_ahead = target_ahead || signed_distance > 1e-6;
        }
    }

    J details = {{"source_curve_id", source_id},
                 {"source_length_mm", source_length.available && scale.known
                                          ? J(source_length.value * scale.scale)
                                          : J(nullptr)},
                 {"source_length_status", measurement_status_json(source_length, units, scale)},
                 {"target_quilt_id", target_id},
                 {"side", side},
                 {"direction", {direction.vector[0], direction.vector[1], direction.vector[2]}},
                 {"direction_basis", direction.basis},
                 {"direction_length", direction.length},
                 {"target_bounds_known", bounds.known},
                 {"target_bounds_code", (int)bounds.code},
                 {"route", "swept_surface_intersect"}};
    if (bounds.known && scale.known) {
        details["target_bounds_mm"] = {xyz_json(bounds.min, scale), xyz_json(bounds.max, scale)};
    }
    if (!bounds.known || !target_ahead) {
        stage_operation_result(details);
        ProSelectionFree(&source);
        ProSelectionFree(&target);
        throw std::runtime_error(
            !bounds.known ? "project_curve cannot measure the target quilt bounds (code " +
                                std::to_string((int)bounds.code) + "); no projection was attempted"
                          : "project_curve target quilt lies behind the source curve for side '" +
                                side + "'; the requested direction does not reach it");
    }

    // The documented extrude tree sweeps along the source sketch normal only.
    // A different direction is refused before a helper surface is created.
    ProFeature owner = {};
    CK(ProGeomitemFeatureGet((ProGeomitem *)&source_item, &owner));
    ProFeattype owner_type;
    CK(ProFeatureTypeGet(&owner, &owner_type));
    if (owner_type != PRO_FEAT_CURVE) {
        ProSelectionFree(&source);
        ProSelectionFree(&target);
        details["source_owner_feature_id"] = (int)owner.id;
        stage_operation_result(details);
        throw std::runtime_error(
            "project_curve source curve must belong to a curve feature (sketch); feature " +
            std::to_string((int)owner.id) +
            " is not one, and the documented sweep route cannot follow an arbitrary direction");
    }

    double depth = 2.0 * (reach + 0.5);
    ProFeature helper = project_helper_surface(op, owner, depth, 1.0);
    details["helper_feature_id"] = (int)helper.id;
    details["helper_sweep_depth"] = depth;
    details["helper_sweep_depth_mm"] = scale.known ? J(depth * scale.scale) : J(nullptr);

    J helper_surfaces = J::array();
    ProError helper_visit =
        ProFeatureGeomitemVisit(&helper, PRO_SURFACE, collect_geom_ids, nullptr, &helper_surfaces);
    details["source_owner_feature_id"] = (int)owner.id;
    details["helper_visit_code"] = (int)helper_visit;
    // The helper carries every face the sweep produced. A plane whose normal
    // runs along the direction is a cap of the sweep (a closed profile), not the
    // swept surface; every other face contains the direction, including curved
    // ones: an arc sweep arrives as several cylindrical pieces (live
    // 2026-11-04, five faces for one arc).
    J helper_records = J::array();
    J swept_faces = J::array();
    for (auto &entry : helper_surfaces) {
        int face_id = entry["id"].get<int>();
        ProGeomitem item = {};
        ProError code = ProModelitemInit(board, face_id, PRO_SURFACE, &item);
        J record = {{"id", face_id}, {"init_code", (int)code}};
        if (!code) {
            ProGeomitemdata *data = nullptr;
            code = ProGeomitemdataGet(&item, &data);
            record["data_code"] = (int)code;
            if (!code && data && data->data.p_surface_data) {
                record["surface_type"] = (int)data->data.p_surface_data->type;
                bool cap = false;
                if (data->data.p_surface_data->type == PRO_SRF_PLANE) {
                    const ProPlanedata &plane = data->data.p_surface_data->srf_shape.plane;
                    V normal = normalized(V{plane.e3[0], plane.e3[1], plane.e3[2]});
                    double along = std::fabs(dot(normal, direction.vector));
                    record["normal"] = {normal[0], normal[1], normal[2]};
                    record["normal_along_direction"] = along;
                    cap = along > 1.0 - 1e-6;
                }
                record["cap"] = cap;
                if (!cap)
                    swept_faces.push_back(face_id);
            } else {
                // Unreadable surface data: count it as swept rather than
                // silently dropping part of the sweep.
                swept_faces.push_back(face_id);
            }
            if (data)
                ProGeomitemdataFree(&data);
        }
        helper_records.push_back(record);
    }
    details["helper_surfaces"] = helper_records;
    details["helper_swept_face_ids"] = swept_faces;
    if (swept_faces.empty()) {
        stage_operation_result(details);
        ProSelectionFree(&source);
        ProSelectionFree(&target);
        throw std::runtime_error("project_curve sweep produced no surface that runs along the "
                                 "direction; no projection was attempted");
    }

    ProFeature curve_feature = project_intersect_curve(op, swept_faces, target);
    ProSelectionFree(&source);
    ProSelectionFree(&target);

    ProFeatStatus status;
    CK(ProFeatureStatusGet(&curve_feature, &status));
    J curve_ids = J::array();
    ProError visit_code =
        ProFeatureGeomitemVisit(&curve_feature, PRO_CURVE, collect_geom_ids, nullptr, &curve_ids);
    J edge_ids = J::array();
    ProError edge_code =
        ProFeatureGeomitemVisit(&curve_feature, PRO_EDGE, collect_geom_ids, nullptr, &edge_ids);

    details["curve_feature_id"] = (int)curve_feature.id;
    details["feature_status"] = (int)status;
    details["curve_ids"] = curve_ids;
    details["curve_visit_code"] = (int)visit_code;
    details["edge_ids"] = edge_ids;
    details["edge_visit_code"] = (int)edge_code;
    details["curve_id"] = nullptr;
    details["curve_length_mm"] = nullptr;
    details["endpoints_mm"] = nullptr;
    details["curve_length_status"] = measurement_status_json({}, units, scale);
    details["endpoints_status"] = measurement_status_json({}, units, scale);

    if (status != PRO_FEAT_ACTIVE) {
        stage_operation_result(details);
        throw std::runtime_error(
            "Projection curve regeneration failed (feature_status=" + std::to_string((int)status) +
            ", feature_id=" + std::to_string((int)curve_feature.id) +
            "); the swept surface does not intersect the target quilt along the direction");
    }
    if (visit_code || curve_ids.empty()) {
        details["curve_count"] = (int)curve_ids.size();
        stage_operation_result(details);
        throw std::runtime_error(
            "Projection produced " + std::to_string((int)curve_ids.size()) +
            " curve geometry items (visit code " + std::to_string((int)visit_code) +
            "); a multi-branch or empty projection is not reported as one curve");
    }

    // Creo publishes an intersect result as more than one curve item: the curve
    // itself plus a composite curve that wraps it (live 2026-11-04: items 122
    // and 123 for one straight projected line). Both are measured, and the
    // simple curve is reported. Two or more *simple* curves are separate
    // branches and are refused instead of picking one.
    struct CurveCandidate {
        int id;
        ProEnttype type;
        bool composite;
        ProCurve curve;
        MeasurementOutcome length;
        bool endpoints_known;
    };
    std::vector<CurveCandidate> candidates;
    J candidate_records = J::array();
    for (auto &entry : curve_ids) {
        CurveCandidate candidate{};
        candidate.id = entry["id"].get<int>();
        ProError init_code = ProCurveInit((ProSolid)board, candidate.id, &candidate.curve);
        J record = {{"id", candidate.id}, {"init_code", (int)init_code}};
        if (!init_code) {
            ProEnttype type;
            ProError type_code = ProCurveTypeGet(candidate.curve, &type);
            candidate.type = type;
            candidate.composite = !type_code && type == PRO_ENT_CMP_CRV;
            record["ent_type"] = (int)type;
            record["type_code"] = (int)type_code;
            record["composite"] = candidate.composite;
            candidate.length = curve_length_native(candidate.curve);
            candidate.endpoints_known =
                curve_endpoints_native(candidate.curve).available && scale.known;
            record["length_mm"] = candidate.length.available && scale.known
                                      ? J(candidate.length.value * scale.scale)
                                      : J(nullptr);
            record["endpoints_mm"] = candidate.endpoints_known
                                         ? J(J::array({xyz_json(curve_endpoint_start, scale),
                                                       xyz_json(curve_endpoint_end, scale)}))
                                         : J(nullptr);
        }
        candidate_records.push_back(record);
        candidates.push_back(candidate);
    }
    details["curve_candidates"] = candidate_records;

    std::vector<size_t> simple;
    for (size_t index = 0; index < candidates.size(); index++)
        if (!candidates[index].composite)
            simple.push_back(index);
    if (simple.size() != 1) {
        details["curve_count"] = (int)candidates.size();
        details["simple_curve_count"] = (int)simple.size();
        stage_operation_result(details);
        throw std::runtime_error(
            "Projection produced " + std::to_string((int)simple.size()) + " separate curves (" +
            std::to_string((int)candidates.size()) +
            " geometry items); a multi-branch projection is not reported as one curve");
    }
    const CurveCandidate &result = candidates[simple[0]];
    J length_json = length_mm_json(result.length, units, scale);
    details["curve_id"] = result.id;
    details["curve_length_mm"] = length_json["length_mm"];
    details["curve_length_status"] = length_json["length_status"];
    J ends = curve_endpoints_json(result.curve, units, scale);
    details["endpoints_mm"] = ends["endpoints_mm"];
    details["endpoints_status"] = ends["endpoints_status"];
    stage_operation_result(details);

    if (!result.length.available)
        throw std::runtime_error(std::string("Projection curve is not measurable") +
                                 (result.length.reason ? ": " : "") +
                                 (result.length.reason ? result.length.reason : ""));
    if (!result.endpoints_known)
        throw std::runtime_error("Projection curve endpoints are not readable; the result cannot "
                                 "be consumed or measured");
    remember(op, curve_feature, {{"curve_id", result.id}, {"helper_feature_id", (int)helper.id}});
}
