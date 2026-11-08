// surface_round.cpp — DEV-074/H08: constant round on the edge shared by two
// member faces of one quilt.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.11 (the measured H08
// route), §4.4.2 (surface_round fields). The tree is the same documented
// PRO_FEAT_ROUND tree generic_round already builds for a face pair:
// PRO_ROUND_REF_SURF_SURF with PRO_E_RNDCH_REFERENCE_SURFACE1/2 and
// PRO_E_RNDCH_ATTACH_TYPE = PRO_ROUND_ATTACHED. The 2026-11-08 hardware probe
// (docs/validation/dev074-h07-h08-2026-11-08) went through that exact generic
// round tree on a 4-face quilt: the two adjacent pairs reduced the quilt to
// 5 faces / 1187.1238898038469 mm2 and the non-adjacent pair failed
// regeneration and rolled back. This module only publishes that route for a
// quilt target; it does not invent a second round tree.
//
// This file is included by generic.cpp after the shared element-tree, quilt
// and measurement helpers are visible; it defines no entry point of its own
// beyond generic_surface_round.
#include <ProRound.h>

// Member face ids of the target quilt. The membership test below is what
// refuses a solid face or another quilt's face; a face id that the quilt does
// not own is never handed to the round tree.
struct SurfaceRoundMembers {
    std::vector<int> ids;
    bool visit_ok = true;
    ProError query_code = PRO_TK_NO_ERROR;
};

static ProError surface_round_member_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *members = (SurfaceRoundMembers *)data;
    if (status) {
        members->visit_ok = false;
        members->query_code = status;
        return PRO_TK_NO_ERROR;
    }
    int id = -1;
    if (!ProSurfaceIdGet(surface, &id))
        members->ids.push_back(id);
    return PRO_TK_NO_ERROR;
}

static SurfaceRoundMembers surface_round_members(ProQuilt quilt) {
    SurfaceRoundMembers members;
    ProError code = ProQuiltSurfaceVisit(quilt, surface_round_member_cb, nullptr, &members);
    if (code) {
        members.visit_ok = false;
        members.query_code = code;
    }
    return members;
}

// §4.4.2 face count projection: a visit failure or an empty quilt is null with
// its own status, never a fabricated zero.
static J surface_round_face_count_status(const SurfaceRoundMembers &members,
                                         const InspectionLengthUnits &units,
                                         const MillimeterScale &scale) {
    MeasurementOutcome outcome;
    outcome.available =
        members.visit_ok && members.query_code == PRO_TK_NO_ERROR && !members.ids.empty();
    outcome.query_code = members.query_code;
    outcome.reason = !members.visit_ok || members.query_code ? "quilt_surface_visit_failed"
                     : members.ids.empty()                   ? "quilt_has_no_surfaces"
                                                             : nullptr;
    outcome.value = (double)members.ids.size();
    return measurement_status_json(outcome, units, scale);
}

static void surface_round_ids(const J &faces, int ids[2]) {
    for (int index = 0; index < 2; index++) {
        const J &face = faces[index];
        if (!face.is_object() || face.value("kind", std::string()) != "surface")
            throw std::runtime_error(
                "surface_round faces must be two {kind:\"surface\",id:N} members of one quilt");
        const J &raw_id = face.at("id");
        if (!raw_id.is_number_integer() || raw_id < 0 || raw_id > 2147483647)
            throw std::runtime_error("surface_round face id must be a nonnegative 32-bit integer");
        ids[index] = raw_id.get<int>();
    }
    if (ids[0] == ids[1])
        throw std::runtime_error("surface_round needs two different member faces");
}

// One set, constant radius, two-face surface reference. Variable radius, full
// round, edge chains and transitions have no element here on purpose.
static ProFeature surface_round_create(const J &op, const J &faces, double radius_mm) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_ROUND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement set = node(node(root, PRO_E_RNDCH_SETS), PRO_E_RNDCH_SET);
    integer(set, PRO_E_RNDCH_SHAPE_OPTIONS, PRO_ROUND_TYPE_CONSTANT);
    integer(node(set, PRO_E_RNDCH_COMPOUND_CONIC), PRO_E_RNDCH_CONIC_TYPE, PRO_ROUND_CONIC_DISABLE);
    integer(node(set, PRO_E_RNDCH_COMPOUND_SPINE), PRO_E_RNDCH_BALL_SPINE, PRO_ROUND_ROLLING_BALL);
    ProElement references = node(set, PRO_E_RNDCH_REFERENCES);
    integer(references, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_SURF_SURF);
    ProSelection first = resolve(faces[0]), second = resolve(faces[1]);
    ref(references, PRO_E_RNDCH_REFERENCE_SURFACE1, first);
    ref(references, PRO_E_RNDCH_REFERENCE_SURFACE2, second);
    ProSelectionFree(&first);
    ProSelectionFree(&second);
    ProElement leg = node(node(node(set, PRO_E_RNDCH_RADII), PRO_E_RNDCH_RADIUS), PRO_E_RNDCH_LEG1);
    integer(leg, PRO_E_RNDCH_LEG_TYPE, PRO_ROUND_RADIUS_TYPE_VALUE);
    real(leg, PRO_E_RNDCH_LEG_VALUE, radius_mm);
    integer(root, PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED);
    node(root, PRO_E_RNDCH_TRANSITIONS);
    ProFeature feature = create(root);
    CK(ProElementFree(&root));
    return feature;
}

static void generic_surface_round(const J &op) {
    const J &references = op.at("references");
    if (references.size() != 1 || !references[0].is_object() || !references[0].contains("surfaces"))
        throw std::runtime_error(
            "surface_round accepts exactly one {\"surfaces\":[...]} reference set; "
            "edge chains, multiple sets and transitions are not accepted");
    const J &faces = references[0]["surfaces"];
    if (!faces.is_array() || faces.size() != 2)
        throw std::runtime_error("surface_round requires exactly two member faces");
    const J &raw_radius = op.at("radius");
    if (!raw_radius.is_number() || !std::isfinite(raw_radius.get<double>()) ||
        !(raw_radius.get<double>() > 0.0))
        throw std::runtime_error("surface_round radius must be a finite value greater than zero");
    const double radius_mm = raw_radius.get<double>();

    int face_ids[2] = {-1, -1};
    surface_round_ids(faces, face_ids);

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    ProSelection target = resolve_quilt_reference(op.at("target"), (ProSolid)board, units, scale);
    int quilt_id = quilt_selection_id(target);
    ProSelectionFree(&target);
    ProQuilt quilt = nullptr;
    ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
    if (init_code)
        throw std::runtime_error("surface_round target quilt " + std::to_string(quilt_id) +
                                 " could not be initialised (code " +
                                 std::to_string((int)init_code) + ")");
    SurfaceRoundMembers before = surface_round_members(quilt);
    if (!before.visit_ok || before.query_code)
        throw std::runtime_error("surface_round cannot enumerate the faces of quilt " +
                                 std::to_string(quilt_id) + " (code " +
                                 std::to_string((int)before.query_code) + ")");
    if (before.ids.empty())
        throw std::runtime_error("surface_round target quilt " + std::to_string(quilt_id) +
                                 " has no faces; it is not a usable surface");
    for (int id : face_ids) {
        if (std::find(before.ids.begin(), before.ids.end(), id) == before.ids.end())
            throw std::runtime_error(
                "surface_round face id " + std::to_string(id) + " is not a member of quilt " +
                std::to_string(quilt_id) +
                "; pass two PRO_SURFACE member faces of that quilt, not a solid face or "
                "another quilt's face");
    }
    MeasurementOutcome area_before = quilt_area_native(quilt);
    MeasurementOutcome closed_before = quilt_closed_native(quilt);

    ProFeature feature = surface_round_create(op, faces, radius_mm);
    ProFeatStatus status = PRO_FEAT_ACTIVE;
    CK(ProFeatureStatusGet(&feature, &status));
    ProFeattype feature_type = 0;
    CK(ProFeatureTypeGet(&feature, &feature_type));

    ProQuilt result_quilt = nullptr;
    ProError result_init = ProQuiltInit((ProSolid)board, quilt_id, &result_quilt);
    SurfaceRoundMembers after;
    MeasurementOutcome area_after, closed_after;
    if (result_init) {
        after.visit_ok = false;
        after.query_code = result_init;
        area_after.reason = "quilt_init_failed";
        area_after.query_code = result_init;
        closed_after.reason = "quilt_init_failed";
        closed_after.query_code = result_init;
    } else {
        after = surface_round_members(result_quilt);
        area_after = quilt_area_native(result_quilt);
        closed_after = quilt_closed_native(result_quilt);
    }
    const char *closure = quilt_closed_is_open(closed_after) ? "open"
                          : closed_after.available           ? "closed"
                                                             : "unknown";
    // Solid-face evidence is read from the kernel's own solid-face collection;
    // a quilt round must leave the quilt a quilt, so a nonzero count is
    // reported rather than inferred away.
    J state = inspection(false);
    J solid_faces = state.contains("surfaces") && state["surfaces"].is_array()
                        ? J((int)state["surfaces"].size())
                        : J(nullptr);

    J details = {{"radius", radius_mm},
                 {"quilt_id", quilt_id},
                 {"face_ids", J::array({face_ids[0], face_ids[1]})},
                 {"feature_id", (int)feature.id},
                 {"feature_status", (int)status},
                 {"feature_type", (int)feature_type},
                 {"face_count_before",
                  before.visit_ok && before.query_code == PRO_TK_NO_ERROR && !before.ids.empty()
                      ? J((int)before.ids.size())
                      : J(nullptr)},
                 {"closed", quilt_closed_is_open(closed_after) ? J(false)
                            : closed_after.available           ? J(true)
                                                               : J(nullptr)},
                 {"closed_status", measurement_status_json(closed_after, units, scale)},
                 {"quilt_closed_native", closure},
                 {"has_solid", state["has_solid"]},
                 {"solid_surface_count", solid_faces},
                 {"reference_application", round_reference_application(feature, 1)}};
    J before_closed = nullptr;
    if (closed_before.available)
        before_closed = true;
    else if (quilt_closed_is_open(closed_before))
        before_closed = false;
    details["closed_before"] = before_closed;
    J before_fields =
        area_fields_json(area_before, units, scale, "area_before_mm2", "area_before_status");
    for (auto it = before_fields.begin(); it != before_fields.end(); ++it)
        details[it.key()] = it.value();
    J after_fields = area_fields_json(area_after, units, scale, "area_mm2", "area_status");
    for (auto it = after_fields.begin(); it != after_fields.end(); ++it)
        details[it.key()] = it.value();
    details["face_count_before_status"] = surface_round_face_count_status(before, units, scale);
    details["face_count"] =
        after.visit_ok && after.query_code == PRO_TK_NO_ERROR && !after.ids.empty()
            ? J((int)after.ids.size())
            : J(nullptr);
    details["face_count_status"] = surface_round_face_count_status(after, units, scale);
    // The failed feature's record keeps the ids and the measured before side,
    // so a caller can tell "the faces do not share an edge" apart from an
    // unmeasured quilt.
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE) {
        last_feature_error_report = feature_error_report("ProFeatureStatusGet", (ProError)status,
                                                         "surface_round_regeneration");
        throw std::runtime_error(
            "surface_round regeneration failed (feature_status=" + std::to_string((int)status) +
            ", feature_id=" + std::to_string((int)feature.id) +
            ", quilt_id=" + std::to_string(quilt_id) + ", faces=" + std::to_string(face_ids[0]) +
            "/" + std::to_string(face_ids[1]) +
            "); the two faces must share an edge of that quilt (2026-11-08 H08: a "
            "non-adjacent pair fails regeneration and rolls back)");
    }
    if (feature_type != PRO_FEAT_ROUND)
        throw std::runtime_error("surface_round produced feature type " +
                                 std::to_string((int)feature_type) + " instead of a round");
    if (!after.visit_ok || after.query_code)
        throw std::runtime_error("surface_round cannot re-read the result quilt faces (code " +
                                 std::to_string((int)after.query_code) + ")");
    if (!area_after.available)
        throw std::runtime_error(std::string("surface_round result quilt is not measurable") +
                                 (area_after.reason ? ": " : "") +
                                 (area_after.reason ? area_after.reason : ""));
    // A round removes a corner from the quilt; an unchanged or larger area is
    // a silent no-op, not a success. Unknown unit scale keeps the judgement
    // out of the way (the statuses carry the reason).
    if (area_before.available && area_after.available && area_after.value >= area_before.value)
        throw std::runtime_error(
            "surface_round removed no area (before=" + std::to_string(area_before.value) +
            " after=" + std::to_string(area_after.value) +
            " native units); the faces may not share the selected edge or the radius may "
            "not cut this quilt");
    remember(op, feature, {{"quilt_id", quilt_id}});
}
