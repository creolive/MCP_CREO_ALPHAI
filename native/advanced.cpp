#include "assembly_pose.h"
#include "constraint_names.h"
#include "geometry_diagnostics.h"
#include <iomanip>
#include <sstream>

// Native feature families added for version 0.21. Included after generic helpers.
static J component_sources = J::object();
static std::map<int, J> component_aliases_in_flight;
static ProElement get_path(ProElement root, const J &ids) {
    std::vector<ProElempathItem> items;
    for (auto id : ids) {
        ProElempathItem i = {};
        i.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
        i.path_item.elem_id = (ProElemId)id.get<int>();
        items.push_back(i);
    }
    ProElempath p;
    CK(ProElempathAlloc(&p));
    CK(ProElempathDataSet(p, items.data(), (int)items.size()));
    ProElement e;
    CK(ProElemtreeElementGet(root, p, &e));
    ProElempathFree(&p);
    return e;
}
static J sketch_curve_refs(const J &value) {
    if (value.is_array())
        return value;
    ProFeature f = feature(value);
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&f, PRO_CURVE, collect_geom_ids, nullptr, &ids));
    J refs = J::array();
    for (auto id : ids)
        refs.push_back({{"kind", "curve"}, {"id", id["id"]}});
    if (refs.empty())
        throw std::runtime_error("Selected sketch has no native trajectory curves");
    return refs;
}
static void surface_collection(ProElement element, const J &refs) {
    ProCollection coll;
    CK(ProSrfcollectionAlloc(&coll));
    for (auto item : refs) {
        ProSelection s = resolve(item);
        ProReference r;
        CK(ProSelectionToReference(s, &r));
        ProSrfcollref cr;
        CK(ProSrfcollrefAlloc(PRO_SURFCOLL_REF_SINGLE, r, &cr));
        ProSrfcollinstr instruction;
        CK(ProSrfcollinstrAlloc(PRO_SURFCOLL_SINGLE_SURF, PRO_B_TRUE, &instruction));
        CK(ProSrfcollinstrReferenceAdd(instruction, cr));
        CK(ProSrfcollectionInstructionAdd(coll, instruction));
        ProSelectionFree(&s);
    }
    CK(ProElementCollectionSet(element, coll));
    ProCollectionFree(&coll);
}
static void generic_mirror(const J &op) {
    J refs = op.value("references", J::array());
    if (refs.empty())
        refs.push_back({{"kind", "part"}});
    bool whole = false;
    for (auto r : refs)
        if (r.at("kind") == "part")
            whole = true;
    if (whole && refs.size() != 1)
        throw std::runtime_error("Whole-part mirror cannot be mixed with geometry selections");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, whole ? PRO_FEAT_GEN_MERGE : PRO_FEAT_SRF_MDL);
    integer(root, PRO_E_SRF_TRANS_TYPE,
            whole ? PRO_SURF_TRANS_TYPE_PART_MIRROR : PRO_SURF_TRANS_TYPE_MIRROR);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    set_refs(node(root, PRO_E_MIRROR_REF_ITEMS), refs);
    ProSelection plane = resolve(op["plane"]);
    ref(root, PRO_E_MIRROR_REF_PLANE, plane);
    ProSelectionFree(&plane);
    integer(root, PRO_E_COPY_NO_COPY,
            op.value("keep_original", true) ? PRO_MIRROR_KEEP_ORIGINAL : PRO_MIRROR_HIDE_ORIGINAL);
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
// FEAT-051: read the created draft's own element tree. Only what the tree
// contains is reported; unreadable fields stay null with their raw query
// codes. No global taper conclusion is drawn here: the pull vector is the
// reference geometry's own direction and the flip is read as stored, so a
// multi-surface draft never pretends to have one 内收/外扩 answer.
static J draft_reference_json(ProElement element, ProError code) {
    J entry = {{"type", nullptr}, {"id", nullptr}, {"query_code", (int)code}};
    if (code != PRO_TK_NO_ERROR || !element)
        return entry;
    ProReference reference = nullptr;
    ProError local = ProElementReferenceGet(element, nullptr, &reference);
    entry["query_code"] = (int)local;
    if (local != PRO_TK_NO_ERROR || !reference)
        return entry;
    ProType type = PRO_TYPE_UNUSED;
    int id = 0;
    ProError type_code = ProReferenceTypeGet(reference, &type);
    ProError id_code = ProReferenceIdGet(reference, &id);
    entry["query_code"] = (int)(type_code ? type_code : id_code);
    if (!type_code && !id_code) {
        entry["type"] = (int)type;
        entry["id"] = id;
        entry["query_code"] = (int)PRO_TK_NO_ERROR;
    }
    return entry;
}
static J draft_pull_vector_json(ProElement element, ProError code) {
    J block = {
        {"frame", "model"}, {"vector", nullptr}, {"source", "unknown"}, {"query_code", nullptr}};
    if (code != PRO_TK_NO_ERROR || !element) {
        if (code != PRO_TK_NO_ERROR)
            block["query_code"] = (int)code;
        return block;
    }
    ProReference reference = nullptr;
    ProError local = ProElementReferenceGet(element, nullptr, &reference);
    if (local != PRO_TK_NO_ERROR || !reference) {
        block["query_code"] = (int)local;
        return block;
    }
    ProSelection selection = nullptr;
    local = ProReferenceToSelection(reference, &selection);
    if (local != PRO_TK_NO_ERROR || !selection) {
        block["query_code"] = (int)local;
        return block;
    }
    ProModelitem item = {};
    local = ProSelectionModelitemGet(selection, &item);
    ProSelectionFree(&selection);
    block["query_code"] = (int)local;
    if (local != PRO_TK_NO_ERROR)
        return block;
    if (item.type == PRO_SURFACE) {
        ProSurface surface;
        local = ProSurfaceInit((ProSolid)board, item.id, &surface);
        if (local != PRO_TK_NO_ERROR) {
            block["query_code"] = (int)local;
            return block;
        }
        ProGeomitemdata *data = nullptr;
        local = ProSurfaceDataGet(surface, &data);
        block["query_code"] = (int)local;
        if (local == PRO_TK_NO_ERROR && data && data->data.p_surface_data &&
            data->data.p_surface_data->type == PRO_SRF_PLANE) {
            block["source"] = "plane_normal";
            block["vector"] = xyz(data->data.p_surface_data->srf_shape.plane.e3);
        }
        if (data)
            ProGeomitemdataFree(&data);
        return block;
    }
    if (item.type == PRO_AXIS) {
        AxisGeometry geometry = inspect_axis_geometry((ProGeomitem *)&item);
        block["query_code"] = (int)geometry.data_code;
        if (geometry.known) {
            block["source"] = "axis_direction";
            block["vector"] = xyz(geometry.direction.data());
        }
    }
    return block;
}
// BUG-102: `flip` is the value the feature tree ended up with, so echoing only
// that left a caller unable to tell a requested false from an applied true.
// `requested_flip` is the caller's own value and `effective_flip` is the tree
// readback; neither is derived from the other and an unreadable tree keeps null.
static J draft_geometry_json(ProFeature &f, bool requested_flip) {
    J block = {{"source", "unknown"},      {"query_code", nullptr},
               {"neutral_plane", nullptr}, {"pull_direction", nullptr},
               {"flip", nullptr},          {"angle_deg", nullptr},
               {"pull_vector", nullptr},   {"requested_flip", requested_flip},
               {"effective_flip", nullptr}};
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    block["query_code"] = (int)code;
    if (code != PRO_TK_NO_ERROR)
        return block;
    block["source"] = "feature_tree";
    ProError path_code = PRO_TK_NO_ERROR;
    ProElement neutral =
        get_optional(tree, {PRO_E_DRAFT_SIDE_1, PRO_E_DRAFT_NEUTRAL_PLANE_1}, &path_code);
    block["neutral_plane"] = draft_reference_json(neutral, path_code);
    ProElement pull =
        get_optional(tree, {PRO_E_DIRECTION_COMPOUND, PRO_E_DIRECTION_REFERENCE}, &path_code);
    block["pull_direction"] = draft_reference_json(pull, path_code);
    block["pull_vector"] = draft_pull_vector_json(pull, path_code);
    ProElement flip =
        get_optional(tree, {PRO_E_DIRECTION_COMPOUND, PRO_E_DIRECTION_FLIP}, &path_code);
    if (path_code == PRO_TK_NO_ERROR && flip) {
        int value = 0;
        if (!ProElementIntegerGet(flip, nullptr, &value)) {
            block["flip"] = value != 0;
            block["effective_flip"] = value != 0;
        }
    }
    ProElement angle = get_optional(tree, {PRO_E_DRAFT_SIDE_1, PRO_E_DRAFT_ANGLE_1}, &path_code);
    if (path_code == PRO_TK_NO_ERROR && angle) {
        double value = 0;
        if (!ProElementDoubleGet(angle, nullptr, &value))
            block["angle_deg"] = value;
    }
    ProFeatureElemtreeFree(&f, tree);
    return block;
}
static J draft_reference_application(ProFeature &f, int requested) {
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    if (code != PRO_TK_NO_ERROR)
        return reference_application_block(requested, nullptr, "unknown", code);
    J applied = nullptr;
    const char *source = "unknown";
    ProElement appl = get_optional(tree, {PRO_E_STD_SURF_COLLECTION_APPL}, &code);
    if (code == PRO_TK_NO_ERROR && appl) {
        ProCollection collection = nullptr;
        code = ProElementCollectionGet(appl, nullptr, &collection);
        if (code == PRO_TK_NO_ERROR && collection) {
            ProSrfcollinstr *instructions = nullptr;
            code = ProSrfcollectionInstructionsGet(collection, &instructions);
            if (code == PRO_TK_NO_ERROR && instructions) {
                int count = 0;
                ProError size_code = ProArraySizeGet((ProArray)instructions, &count);
                if (size_code == PRO_TK_NO_ERROR && !(count == 0 && requested > 0)) {
                    applied = count;
                    source = "feature_tree";
                } else if (size_code != PRO_TK_NO_ERROR)
                    code = size_code;
                ProSrfcollinstrArrayFree(instructions);
            }
            ProCollectionFree(&collection);
        }
    }
    ProFeatureElemtreeFree(&f, tree);
    return reference_application_block(requested, applied, source, code);
}
static J generic_draft(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DRAFT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_DRAFT_TWEAK_OR_INTERSEC, PRO_DRAFT_UI_INTERSECT);
    integer(root, PRO_E_DRAFT_EXTEND, PRO_DRAFT_UI_NO_EXTEND);
    integer(root, PRO_E_DRAFT_SPLIT, PRO_DRAFT_UI_SPLIT_NONE);
    integer(root, PRO_E_DRAFT_CONSTANT_OR_VARIABLE, PRO_DRAFT_UI_CONSTANT);
    integer(root, PRO_E_DRAFT_INCLUDE_TANGENT,
            op.value("include_tangent", false) ? PRO_DRAFT_UI_INC_TANG : PRO_DRAFT_UI_NOT_INC_TANG);
    surface_collection(node(root, PRO_E_STD_SURF_COLLECTION_APPL), op["surfaces"]);
    ProElement direction = node(root, PRO_E_DIRECTION_COMPOUND);
    ProSelection pull = resolve(op.value("pull_direction", op["neutral_plane"]));
    ref(direction, PRO_E_DIRECTION_REFERENCE, pull);
    ProSelectionFree(&pull);
    integer(direction, PRO_E_DIRECTION_FLIP, op.value("flip", false) ? PRO_B_TRUE : PRO_B_FALSE);
    ProElement side = node(root, PRO_E_DRAFT_SIDE_1);
    integer(side, PRO_E_DRAFT_NEUTRAL_OBJECT_TYPE_1, PRO_DRAFT_UI_PLANE);
    ProSelection neutral = resolve(op["neutral_plane"]);
    ref(side, PRO_E_DRAFT_NEUTRAL_PLANE_1, neutral);
    ProSelectionFree(&neutral);
    integer(side, PRO_E_DRAFT_DEPENDENT_1, PRO_DRAFT_UI_INDEPENDENT);
    real(side, PRO_E_DRAFT_ANGLE_1, op["angle"]);
    ProFeature f = {};
    try {
        f = create(root);
    } catch (...) {
        // BUG-102: a bare ProFeatureWithoptionsCreate=-1 gives the caller
        // nothing to act on. Publish the request beside the kernel's own
        // element diagnostics and let the caller see which case it is; the
        // original Toolkit error is rethrown unchanged.
        J failure = J::object();
        failure["api"] = "ProFeatureWithoptionsCreate";
        failure["requested_flip"] = op.value("flip", false);
        failure["angle_deg"] = op["angle"];
        failure["surface_count"] = (int)op["surfaces"].size();
        J sample = J::array();
        for (const auto &entry : feature_error_entries)
            sample.push_back(
                {{"element", entry.element}, {"type", entry.type}, {"error", entry.error}});
        failure["element_errors"] = {{"total", feature_error_total},
                                     {"truncated", feature_error_total > (int)sample.size()},
                                     {"sample", sample}};
        failure["classification"] = sample.empty() ? "no_element_evidence" : "kernel_element_error";
        failure["note"] =
            sample.empty()
                ? "The kernel returned no element diagnostics. On a face bounded by rounds or "
                  "chamfers this usually means the requested angle cannot be built there; try a "
                  "smaller angle, remove the adjacent round/chamfer first, or re-read the surface "
                  "ids with creo_inspect_model before retrying."
                : "The kernel rejected the listed element(s); re-read the neutral/pull references "
                  "and the surface ids with creo_inspect_model before retrying.";
        stage_operation_result({{"draft_failure", failure}});
        ProElementFree(&root);
        throw;
    }
    ProElementFree(&root);
    remember(op, f);
    // FEAT-051: report the tree-proven reference application and the actual
    // draft parameters/direction evidence beside the unchanged request.
    J details = J::object();
    details["draft_geometry"] = draft_geometry_json(f, op.value("flip", false));
    details["reference_application"] = draft_reference_application(f, (int)op["surfaces"].size());
    return details;
}
static void generic_sweep(const J &op) {
    std::string mode = op.value("mode", "add");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE,
            mode == "surface" ? PRO_FEAT_DATUM_SURF
            : mode == "cut"   ? PRO_FEAT_CUT
                              : PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_SWEEP);
    integer(root, PRO_E_SWEEP_TYPE, PRO_SWEEP_TYPE_MULTI_TRAJ);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_EXT_SURF_CUT_SOLID_TYPE,
            mode == "surface" ? PRO_SWEEP_FEAT_TYPE_SURFACE : PRO_SWEEP_FEAT_TYPE_SOLID);
    integer(root, PRO_E_REMOVE_MATERIAL,
            mode == "cut" ? PRO_SWEEP_MATERIAL_REMOVE : PRO_SWEEP_MATERIAL_ADD);
    integer(root, PRO_E_FEAT_FORM_IS_THIN,
            op.contains("thin") ? PRO_SWEEP_FEAT_FORM_THIN : PRO_SWEEP_FEAT_FORM_NO_THIN);
    if (op.contains("thin")) {
        real(root, PRO_E_THICKNESS, op["thin"]);
        integer(root, PRO_E_STD_MATRLSIDE, PRO_SWEEP_MATERIAL_BOTH_SIDES);
    } else if (mode == "cut")
        integer(root, PRO_E_STD_MATRLSIDE, PRO_SWEEP_MATERIAL_SIDE_ONE);
    ProElement frame = node(root, PRO_E_SWEEP_FRAME_COMP),
               trajectory = node(node(frame, PRO_E_FRM_OPT_TRAJ), PRO_E_OPT_TRAJ);
    integer(trajectory, PRO_E_STD_SEC_METHOD, PRO_SEC_SELECT);
    curve_collection(node(node(trajectory, PRO_E_STD_SEC_SELECT), PRO_E_STD_CURVE_COLLECTION_APPL),
                     sketch_curve_refs(op["trajectory"]));
    ProElement setup = node(frame, PRO_E_FRAME_SETUP);
    integer(setup, PRO_E_FRM_NORMAL, PRO_FRAME_NORM_ORIGIN);
    integer(setup, PRO_E_FRM_ORIENT, PRO_FRAME_MIN);
    integer(setup, PRO_E_FRM_USER_X, PRO_FRAME_DEFAULT_START_X);
    ProElement profile = node(root, PRO_E_SWEEP_PROF_COMP);
    integer(profile, PRO_E_SWP_SEC_TYPE, PRO_SWEEP_CONST_SECTION);
    integer(node(profile, PRO_E_SWEEP_SECTION), PRO_E_STD_SEC_METHOD, PRO_SEC_SKETCH);
    if (mode == "surface")
        integer(node(root, PRO_E_SWP_ATTR), PRO_E_END_SRF_ATTR,
                op.value("capped", false) ? PRO_SWEEP_END_SRF_CAPPED : PRO_SWEEP_END_SRF_OPEN);
    else
        body_options(root, op);
    ProFeature f = create(root, PRO_FEAT_CR_INCOMPLETE_FEAT);
    ProElementFree(&root);
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    // Creo initializes thin material side while creating an incomplete sweep.
    // Reapply the requested symmetric side when completing its profile.
    if (op.contains("thin")) {
        ProElement side = get(root, {PRO_E_STD_MATRLSIDE});
        int current = 0;
        CK(ProElementIntegerGet(side, nullptr, &current));
        log("SWEEP_THIN_INITIAL_SIDE=%d\n", current);
        CK(ProElementIntegerSet(side, PRO_SWEEP_MATERIAL_BOTH_SIDES));
        CK(ProElementDoubleSet(get(root, {PRO_E_THICKNESS}), op["thin"]));
    }
    J path = J::array({PRO_E_SWEEP_PROF_COMP, PRO_E_SWEEP_SECTION, PRO_E_SKETCHER});
    ProElement sk = get_path(root, path);
    ProSection section;
    CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&section));
    J extra = populate_profile(section, op);
    CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    extra["section_path"] = path;
    remember(op, f, extra);
}
// T03/BUG-032: the first wall is one thin extrusion of one open straight line,
// converted into a native sheetmetal wall. The conversion re-drives the body from
// a single driving face, so a closed contour, an arc or a chain has no defined
// depth/thickness geometry and its depth would be silently replaced by the
// thickness (the reported closed rectangle kept one volume for depth 1 and 30).
// Reject those sections before any feature is created; the independent tool and
// execute_plan share this native path. Only real geometry counts: every section
// built by native/generic.cpp also carries the PRO_2D_COORD_SYS placement entity,
// and ProSectionEntityIdsGet lists it as an entity, so counting raw ids rejected
// every legal one-line section with "2 drawing entities (1 straight lines)".
static double first_wall_line_length(ProFeature sketch) {
    ProSection section = nullptr;
    ProError code = ProFeatureSectionCopy(&sketch, 0, &section);
    if (code)
        throw std::runtime_error("sheetmetal_wall could not read the first wall sketch section "
                                 "(code " +
                                 std::to_string(code) + ")");
    ProIntlist ids = nullptr;
    int count = 0;
    code = ProSectionEntityIdsGet(section, &ids, &count);
    std::string problem;
    if (code)
        problem = "sheetmetal_wall could not list the first wall section entities (code " +
                  std::to_string(code) + ")";
    int curves = 0, lines = 0;
    double length = 0;
    for (int index = 0; problem.empty() && index < count; index++) {
        ProBoolean construction = PRO_B_FALSE, projection = PRO_B_FALSE;
        if (!ProSectionEntityIsConstruction(section, ids[index], &construction) && construction)
            continue;
        if (!ProSectionEntityIsProjection(section, ids[index], &projection) && projection)
            continue;
        Pro2dEntdef *def = nullptr;
        if (ProSectionEntityGet(section, ids[index], &def) || !def) {
            problem = "sheetmetal_wall could not read first wall section entity " +
                      std::to_string(ids[index]);
            break;
        }
        // The section coordinate system is the sketch placement marker added by
        // the section builder, and a point is no curve: neither is first wall
        // geometry, so neither may count as a drawing entity. Every other type
        // (line, arc, circle, spline, polyline, composite curve) still counts, so
        // the "exactly one open straight line" rule keeps rejecting closed
        // contours, arcs and multi-entity chains.
        if (def->type == PRO_2D_COORD_SYS || def->type == PRO_2D_POINT)
            continue;
        if (def->type == PRO_2D_CENTER_LINE)
            continue;
        curves++;
        if (def->type != PRO_2D_LINE)
            continue;
        auto line = (Pro2dLinedef *)def;
        lines++;
        length = hypot(line->end2[0] - line->end1[0], line->end2[1] - line->end1[1]);
    }
    if (ids)
        ProArrayFree((ProArray *)&ids);
    ProSectionFree(&section);
    if (problem.empty() && (curves != 1 || lines != 1))
        problem = "sheetmetal_wall creates the first wall from exactly one open straight line; "
                  "the section has " +
                  std::to_string(curves) + " drawing entities (" + std::to_string(lines) +
                  " straight lines). Closed contours, arcs, splines and multi-entity chains are "
                  "not supported for the first wall";
    if (problem.empty() && !(length > 0))
        problem = "sheetmetal_wall requires a straight line with a nonzero length";
    if (!problem.empty())
        throw std::runtime_error(problem);
    log("SHEETMETAL_WALL_LINE_LENGTH_MM=%.12f\n", length);
    return length;
}
// BUG-090: ProSmtPartThicknessValueGet is not declared in every SDK generation
// (Creo 10 lacks it, 2026-10-29/30 external build reports). The generated
// MECHDOG_HAS_ capability macros keep missing APIs out of the compile unit, and
// every caller here reads the part-level thickness through this one helper.
// Without the value getter the fallbacks read the same model state through the
// thickness dimension or the SMT_THICKNESS parameter that drives it
// (BUG-032/T03), so the value still comes from the model and never from the
// request. When no path can read a value the caller must treat the thickness as
// unknown: the first wall then fails explicitly and only informational fields
// may degrade to null.
static bool part_thickness_read(double *mm) {
#ifdef MECHDOG_HAS_ProSmtPartThicknessValueGet
    return ProSmtPartThicknessValueGet(ProMdlToPart(board), mm) == PRO_TK_NO_ERROR;
#else
#ifdef MECHDOG_HAS_ProSmtPartThicknessGet
    ProDimension dimension;
    if (ProSmtPartThicknessGet(ProMdlToPart(board), &dimension) == PRO_TK_NO_ERROR &&
        ProDimensionValueGet(&dimension, mm) == PRO_TK_NO_ERROR)
        return true;
#endif
    ProModelitem owner;
    if (ProMdlToModelitem(board, &owner) != PRO_TK_NO_ERROR)
        return false;
    ProName param_name;
    wcscpy_s(param_name, L"SMT_THICKNESS");
    ProParameter param;
    if (ProParameterInit(&owner, param_name, &param) != PRO_TK_NO_ERROR)
        return false;
    ProParamvalue value = {};
    if (ProParameterValueWithUnitsGet(&param, &value, nullptr) != PRO_TK_NO_ERROR ||
        value.type != PRO_PARAM_DOUBLE)
        return false;
    *mm = value.value.d_val;
    return true;
#endif
}
static void generic_sheetmetal_wall(const J &op) {
    // Preserve the editable driving sketch, then convert its thin native extrusion.
    J state = inspection();
    if (state["has_solid"].get<bool>())
        throw std::runtime_error(
            "sheetmetal_wall creates the first wall; attach later walls with sheetmetal_flange");
    double thickness = op["thickness"].get<double>();
    double depth = op["depth"].get<double>();
    double line_length = first_wall_line_length(feature(op["sketch"]));
    std::string base = "b_" + op["label"].get<std::string>().substr(0, 25);
    J extrude = {{"op", "extrude"},
                 {"label", base},
                 {"sketch", op["sketch"]},
                 {"depth", op["depth"]},
                 {"mode", "add"},
                 {"direction", op.value("direction", "positive")},
                 {"thin", op["thickness"]},
                 {"new_body", true},
                 {"skip_empty_body_cleanup", true}};
    extrude_or_revolve(extrude, false);
    state = inspection();
    int active = -1;
    for (auto item : state["bodies"])
        if (item["state"].get<int>() == PRO_BODY_STATE_ACTIVE)
            active = item["id"];
    if (active < 0)
        throw std::runtime_error("No active thin body");
    ProSelection body = selection(active, PRO_BODY);
    // The conversion re-thickens the body along the driving face normal with
    // PRO_E_STD_SMT_THICKNESS. Driving from the largest face replaced the requested
    // depth with the thickness whenever thickness > depth (185x232x1 became
    // 185x232x232 = 9957440 mm3, BUG-032), so the driving face must be normal to
    // the sheet thickness axis and let the conversion keep the thin section.
    J body_box;
    for (auto item : state["bodies"])
        if (item["id"].get<int>() == active && item.contains("bbox"))
            body_box = item["bbox"];
    if (!body_box.is_array() || body_box.size() != 2)
        throw std::runtime_error("Sheetmetal conversion needs the new wall body outline");
    V extent = {}, low = vec(body_box[0]), high = vec(body_box[1]);
    for (int i = 0; i < 3; i++)
        extent[i] = fabs(high[i] - low[i]);
    int axis = -1;
    double closest = 1e9;
    for (int i = 0; i < 3; i++) {
        double relative = fabs(extent[i] - thickness) / thickness;
        if (relative < closest) {
            closest = relative;
            axis = i;
        }
    }
    if (axis < 0 || closest > 0.02)
        throw std::runtime_error(
            "Sheetmetal conversion could not identify the sheet thickness axis of the new wall; "
            "the body extents do not contain the requested thickness " +
            std::to_string(thickness) +
            " mm, so the wall cannot keep the requested depth and thickness");
    J face;
    double best = -1;
    for (auto surf : state["surfaces"]) {
        if (!surf.contains("normal"))
            continue;
        V normal = vec(surf["normal"]);
        if (fabs(normal[axis]) < 0.999)
            continue;
        V a = vec(surf["bbox"][1]), b = vec(surf["bbox"][0]);
        if (fabs(a[axis] - b[axis]) > 1e-6)
            continue; // Only faces bounding the body on the thickness axis.
        double area = 1;
        for (int i = 0; i < 3; i++)
            if (i != axis)
                area *= fabs(a[i] - b[i]);
        if (area > best) {
            best = area;
            face = surf;
        }
    }
    if (face.is_null())
        throw std::runtime_error("Sheetmetal conversion needs a planar driving face normal to "
                                 "the sheet thickness axis");
    log("SHEETMETAL_WALL_DRIVING_FACE id=%d axis=%d normal=%.9f,%.9f,%.9f area_mm2=%.9f\n",
        face["id"].get<int>(), axis, vec(face["normal"])[0], vec(face["normal"])[1],
        vec(face["normal"])[2], best);
    ProSelection drive = selection(face["id"], PRO_SURFACE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_DTM_SRF_TYPE, PRO_DTM_SRF_AS_WALL);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ref(root, PRO_E_SMT_CONV_BODY, body);
    ref(root, PRO_E_SMT_DRV_SURF, drive);
    real(root, PRO_E_STD_SMT_THICKNESS, op["thickness"]);
    integer(root, PRO_E_STD_MATRLSIDE, 0);
    integer(root, PRO_E_STD_SMT_SWAP_DRV_SIDE, 0);
    integer(root, PRO_E_SMT_ADJACENT_RND_OPTS, PRO_SMT_ADJ_RND_RECREATE);
    integer(root, PRO_E_SMT_KEEP_NOT_CLASS_SURFS, PRO_SMT_IGNORE_NOT_CLASS_SURFS);
    ProFeature f = create(root);
    ProElementFree(&root);
    ProSelectionFree(&body);
    ProSelectionFree(&drive);
    state = inspection();
    bool native_smt = false;
    ProSolidBody *bodies = nullptr;
    CK(ProSolidBodiesCollect((ProSolid)board, &bodies));
    int count;
    CK(ProArraySizeGet((ProArray)bodies, &count));
    for (int i = 0; i < count; i++) {
        ProBoolean smt;
        if (!ProSolidBodyIsSheetmetal(&bodies[i], &smt) && smt)
            native_smt = true;
    }
    ProArrayFree((ProArray *)&bodies);
    if (!native_smt)
        throw std::runtime_error("No native sheetmetal body was produced");
    // Supported first walls keep the declared parameters: one straight line of
    // length L, thin width = thickness, extrusion depth = depth, so the wall is
    // L x thickness x depth. Anything else means the conversion traded one
    // parameter for another, which must not surface as a silent success.
    double expected = line_length * thickness * depth, measured = volume();
    log("SHEETMETAL_WALL_VOLUME line_mm=%.9f thickness_mm=%.9f depth_mm=%.9f expected_mm3=%.9f "
        "measured_mm3=%.9f\n",
        line_length, thickness, depth, expected, measured);
    if (fabs(measured - expected) > std::max(0.01, expected * 1e-3))
        throw std::runtime_error(
            "Sheetmetal wall volume " + std::to_string(measured) +
            " mm3 does not match line length x thickness x depth (" + std::to_string(expected) +
            " mm3); the native conversion changed the requested depth or thickness");
    // BUG-032/T03: the PRO_E_STD_SMT_THICKNESS element above only drives the
    // converted body geometry. The part-level sheetmetal thickness - the
    // dimension ProSmtPartThicknessGet returns and ProSmtPartThicknessValueGet
    // reads - keeps the template default (3.71 mm was read back on a 1 mm wall,
    // T11 round 6), so every downstream thickness rule computes against the
    // wrong value. Sync that dimension to the requested thickness, re-prove the
    // geometry, and fail when either side disagrees; wall_contract records what
    // the part actually reports, never a request echo.
    double part_before = 0;
    if (!part_thickness_read(&part_before))
        throw std::runtime_error(
            "sheetmetal_wall could not read the part-level sheetmetal thickness after the "
            "conversion, so the requested thickness cannot be proven to be in effect");
    log("SHEETMETAL_WALL_PART_THICKNESS before_mm=%.9f requested_mm=%.9f\n", part_before,
        thickness);
    bool synced = false;
    if (fabs(part_before - thickness) > 1e-6) {
        // BUG-032/T03 live (2026-10-30): setting the dimension returned by
        // ProSmtPartThicknessGet reports PRO_TK_NO_ERROR but has no effect - the
        // regeneration that follows recomputes the sheetmetal relations and puts the
        // template default back (3.71 mm stayed on every case). The part thickness is
        // driven by the SMT_THICKNESS parameter, so set that and keep the dimension
        // write only as a fallback for a part that does not expose the parameter.
        ProModelitem owner;
        CK(ProMdlToModelitem(board, &owner));
        ProName param_name;
        wcscpy_s(param_name, L"SMT_THICKNESS");
        ProParameter param;
        if (ProParameterInit(&owner, param_name, &param) == PRO_TK_NO_ERROR) {
            ProParamvalue value = {};
            value.type = PRO_PARAM_DOUBLE;
            value.value.d_val = thickness;
            CK(ProParameterValueWithUnitsSet(&param, &value, nullptr));
            log("SHEETMETAL_WALL_PART_THICKNESS driver=SMT_THICKNESS set_mm=%.9f\n", thickness);
        } else {
#ifdef MECHDOG_HAS_ProSmtPartThicknessGet
            ProDimension dimension;
            CK(ProSmtPartThicknessGet(ProMdlToPart(board), &dimension));
            CK(ProDimensionValueSet(&dimension, thickness));
            log("SHEETMETAL_WALL_PART_THICKNESS driver=dimension_fallback set_mm=%.9f\n",
                thickness);
#else
            throw std::runtime_error(
                "sheetmetal_wall cannot sync the part thickness: the model exposes no "
                "SMT_THICKNESS parameter and this SDK build has no "
                "ProSmtPartThicknessGet dimension fallback");
#endif
        }
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        double regenerated = volume();
        log("SHEETMETAL_WALL_PART_THICKNESS synced_mm=%.9f regenerated_mm3=%.9f\n", thickness,
            regenerated);
        if (fabs(regenerated - expected) > std::max(0.01, expected * 1e-3))
            throw std::runtime_error(
                "sheetmetal_wall part thickness sync changed the wall geometry: volume " +
                std::to_string(regenerated) +
                " mm3 no longer matches line length x thickness x depth (" +
                std::to_string(expected) + " mm3)");
        measured = regenerated;
        synced = true;
    }
    double part_after = 0;
    if (!part_thickness_read(&part_after))
        throw std::runtime_error("sheetmetal_wall could not re-read the part-level sheetmetal "
                                 "thickness after the sync");
    if (fabs(part_after - thickness) > 1e-6)
        throw std::runtime_error(
            "sheetmetal_wall left the part-level sheetmetal thickness at " +
            std::to_string(part_after) + " mm instead of the requested wall thickness " +
            std::to_string(thickness) +
            " mm; the conversion did not sync the part thickness parameter, so thickness "
            "rules must not run against this wall");
    // P08/BUG-032/FEAT-008: publish the measured frame and the measured wall
    // faces. Every value comes from the created model (the sketch's recorded
    // frame, the converted body bbox and the sheetmetal surface types); the
    // request is never echoed as evidence. A correct volume alone cannot show
    // a swapped depth/thickness pair or an unexpected wall-face orientation -
    // the 2026-10-31 feedback built a geometrically perfect 185x232x1 plate
    // whose green/white wall faces were the 185x1 rim strips.
    J frame = nullptr;
    J wall_face_ids = J::array();
    bool wall_faces_complete = true;
    V wall_center = {};
    bool wall_center_known = false;
    for (auto item : state["bodies"])
        if (item.contains("bbox") && item["bbox"].is_array() && item["bbox"].size() == 2) {
            V low = vec(item["bbox"][0]), high = vec(item["bbox"][1]);
            wall_center = scale(add(low, high), 0.5);
            wall_center_known = true;
            break;
        }
    for (auto surf : state["surfaces"]) {
        if (!surf.contains("sheetmetal_type")) {
            wall_faces_complete = false;
            continue;
        }
        int smt_type = surf["sheetmetal_type"].get<int>();
        if ((smt_type == PRO_SMT_SURF_FACE || smt_type == PRO_SMT_SURF_OFFSET) &&
            wall_face_ids.size() < 64)
            wall_face_ids.push_back(surf["id"]);
    }
    const J *sketch_record =
        op["sketch"].is_string() ? alias_entry(op["sketch"].get<std::string>()) : nullptr;
    if (sketch_record && sketch_record->contains("normal") && sketch_record->contains("origin") &&
        wall_center_known) {
        V sketch_normal = normalized(vec((*sketch_record)["normal"]));
        V sketch_origin = vec((*sketch_record)["origin"]);
        V delta = add(wall_center, scale(sketch_origin, -1));
        V depth_direction = scale(sketch_normal, dot(delta, sketch_normal) >= 0 ? 1.0 : -1.0);
        V thickness_direction = vec(face["normal"]);
        V face_origin = face.contains("origin") ? vec(face["origin"]) : wall_center;
        double material = dot(add(wall_center, scale(face_origin, -1)), thickness_direction);
        frame = {{"sketch_normal", xyz(sketch_normal.data())},
                 {"sketch_origin", xyz(sketch_origin.data())},
                 {"depth_direction", xyz(depth_direction.data())},
                 {"thickness_direction", xyz(thickness_direction.data())},
                 {"material_side",
                  material < 0 ? "opposite_thickness_direction" : "along_thickness_direction"}};
    }
    // Evidence-based, non-blocking hint: thickness >= depth is exactly the
    // signature of the historical depth/thickness swap (BUG-032 T03), but a
    // thick gauge is a legal input, so this only restates the measured axes
    // and the standard recipe - it never rejects.
    J parameter_hint = nullptr;
    if (!frame.is_null() && thickness >= depth)
        parameter_hint =
            "thickness >= depth: thickness is the sheet gauge spread centered on the sketch "
            "line and depth grows one-sided along the signed sketch normal, so a gauge larger "
            "than the depth means the wall faces (wall_face_ids) are not the largest faces. "
            "Flanges attach on those green/white wall faces. For the standard horizontal base "
            "plate recipe see examples/sheetmetal_base_yz.json. This hint does not reject the "
            "wall.";
    remember(op, f,
             {{"base_feature", base},
              {"construction", "thin_extrude_then_native_sheetmetal_conversion"},
              {"wall_contract",
               {{"line_length_mm", line_length},
                {"expected_volume_mm3", expected},
                {"measured_volume_mm3", measured},
                {"driving_face_id", face["id"]},
                {"driving_axis", axis},
                {"part_thickness_before_mm", part_before},
                {"part_thickness_mm", part_after},
                {"part_thickness_synced", synced},
                {"frame", frame},
                {"wall_face_ids", wall_face_ids},
                {"wall_face_ids_complete", wall_faces_complete},
                {"parameter_hint", parameter_hint}}}});
}
static void generic_sheetmetal_unbend(const J &op) {
    bool back = op["op"] == "sheetmetal_bend_back", flat = op["op"] == "sheetmetal_flat_pattern";
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE,
            back   ? PRO_FEAT_BEND_BACK
            : flat ? PRO_FEAT_FLAT_PAT
                   : PRO_FEAT_UNBEND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    bool all = op["references"].empty();
    integer(root, back ? PRO_E_SMT_BEND_BACK_SUB_TYPE : PRO_E_SMT_UNBEND_SUB_TYPE, all ? 0 : 1);
    ProElement fixed = node(root, PRO_E_SMT_PRIMARY_FIXED_GEOM);
    ProSelection s = resolve(op["fixed_surface"]);
    ref(fixed, PRO_E_SMT_FIXED_REF, s);
    ProSelectionFree(&s);
    integer(fixed, PRO_E_SMT_FIXED_REF_SIDE, PRO_SMT_FIXED_SIDE_UNDEF);
    if (!all) {
        ProElement arr = node(root, back ? PRO_E_SMT_BBACK_REF_ARR : PRO_E_SMT_UNBEND_REF_ARR);
        for (auto reference : op["references"]) {
            ProElement item = node(arr, back ? PRO_E_SMT_BBACK_REF : PRO_E_SMT_UNBEND_REF);
            s = resolve(reference);
            ref(item, back ? PRO_E_SMT_BBACK_SINGLE_REF : PRO_E_SMT_UNBEND_SINGLE_REF, s);
            ProSelectionFree(&s);
        }
    }
    if (!back) {
        ProElement relief = node(root, PRO_E_SMT_ADD_CORNER_RELIEFS_OPTS);
        CK(ProElementBooleanSet(node(relief, PRO_E_SMT_ADD_CORNER_RELIEFS), PRO_B_FALSE));
        CK(ProElementBooleanSet(node(root, PRO_E_SMT_FLATTEN_FORM_WALLS), PRO_B_FALSE));
        CK(ProElementBooleanSet(node(root, PRO_E_SMT_FLATTEN_ALL_FORMS), PRO_B_FALSE));
        CK(ProElementBooleanSet(node(root, PRO_E_SMT_FLATTEN_PROJ_CUTS), PRO_B_FALSE));
        CK(ProElementBooleanSet(node(root, PRO_E_SMT_MERGE_SAME_SIDES), PRO_B_TRUE));
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
// DEV-051 T11 / FEAT-014: bend-end relief. The Creo 12.4 SDK exposes one relief
// compound per bend end (ProSmtFlangeWall.h PRO_E_SMT_BEND_RELIEF_SIDE1/SIDE2)
// with PRO_BEND_RLF_NONE/RIP/STRETCH/RECTANGULAR/OBROUND/PARAM. Only the pre-T11
// tree (both ends NONE) and a rectangular notch with an explicit blind width and
// depth are implemented. Width and depth stay absolute model units and are never
// scaled by the sheet thickness; corner relief, miter cuts and edge rips exist in
// the SDK but are deliberately absent here, so nothing is guessed from the edge
// or corner geometry.
struct FlangeReliefRequest {
    std::string type = "none";
    std::string ends = "both";
    double width = 0;
    double depth = 0;
    bool side1 = false;
    bool side2 = false;
};

static FlangeReliefRequest flange_relief_request(const J &op) {
    FlangeReliefRequest request;
    if (!op.contains("relief") || op.at("relief").is_null())
        return request;
    const J &relief = op.at("relief");
    if (!relief.is_object())
        throw std::runtime_error("relief must be an object");
    request.type = relief.value("type", "none");
    request.ends = relief.value("ends", "both");
    if (request.type == "none") {
        if (relief.contains("width") || relief.contains("depth"))
            throw std::runtime_error("relief type none cannot carry width or depth");
        if (request.ends != "both")
            throw std::runtime_error("relief type none has no ends to select");
        return request;
    }
    if (request.type != "rectangular")
        throw std::runtime_error("Unsupported sheetmetal flange relief type: " + request.type +
                                 " (supported: none, rectangular)");
    if (!relief.contains("width") || !relief.contains("depth"))
        throw std::runtime_error("relief type rectangular requires width and depth in model units");
    request.width = relief.at("width").get<double>();
    request.depth = relief.at("depth").get<double>();
    if (!(request.width > 0))
        throw std::runtime_error("relief width must be greater than zero");
    if (!(request.depth >= 0))
        throw std::runtime_error("relief depth must be zero or greater");
    if (request.ends == "both")
        request.side1 = request.side2 = true;
    else if (request.ends == "side1")
        request.side1 = true;
    else if (request.ends == "side2")
        request.side2 = true;
    else
        throw std::runtime_error("relief ends must be both, side1 or side2");
    return request;
}

// FEAT-014 2026-11-06: the miter-cut route for a wall whose attachment-edge ends
// meet existing bends. ProSmtFlangeWall.h exposes PRO_E_SMT_MTR_CUTS on the same
// wall feature, so the cut is requested together with the flange instead of a
// separate ProSmtCornerRelief feature. Width/offset are written as BLIND
// (PRO_DIM_ENTER) so the literal value in model units is stored: the first live
// run wrote GAP, and Creo reset both types to PARAM with values 0, so GAP is not
// a literal-length type in this context. The live geometry meaning of the value
// is measured by the box driver before any capability is claimed.
struct FlangeMiterRequest {
    bool requested = false;
    double width = 0;
    double offset = 0;
};

static FlangeMiterRequest flange_miter_request(const J &op) {
    FlangeMiterRequest request;
    if (!op.contains("miter_cuts") || op.at("miter_cuts").is_null())
        return request;
    const J &miter = op.at("miter_cuts");
    if (!miter.is_object())
        throw std::runtime_error("miter_cuts must be an object with width and optional offset");
    if (miter.contains("type") && miter.at("type") != "gap")
        throw std::runtime_error("Unsupported sheetmetal flange miter_cuts type: " +
                                 miter.at("type").dump() + " (supported: gap)");
    request.requested = true;
    if (!miter.contains("width"))
        throw std::runtime_error("miter_cuts requires width in model units");
    request.width = miter.at("width").get<double>();
    request.offset = miter.contains("offset") ? miter.at("offset").get<double>() : request.width;
    if (!(request.width > 0))
        throw std::runtime_error("miter_cuts width must be greater than zero");
    if (!(request.offset >= 0))
        throw std::runtime_error("miter_cuts offset must be zero or greater");
    return request;
}

static void flange_relief_side(ProElement relief, int side, bool enabled, double width,
                               double depth) {
    ProElement item = node(relief, side);
    integer(item, PRO_E_BEND_RELIEF_TYPE, enabled ? PRO_BEND_RLF_RECTANGULAR : PRO_BEND_RLF_NONE);
    if (!enabled)
        return;
    // SDK note: width and depth type are mandatory for every type except rip, and
    // blind depth is the only depth value the caller controls. Depth is measured
    // from the bend edge.
    real(item, PRO_E_BEND_RELIEF_WIDTH, width);
    integer(item, PRO_E_BEND_RELIEF_DEPTH_TYPE, PRO_BEND_RLF_DEPTH_BLIND);
    real(item, PRO_E_BEND_RELIEF_DEPTH, depth);
}

// DEV-051 T11 2026-10-30: Creo fills every relief element the tree omits with part
// defaults - the flange_expected.xml probes show PARAM (5) and all-zero values - so a
// silently reset request would leave a plain wall while the caller still reads
// "rectangular" from its own request echo. After a successful create the relief
// section is read back out of the created feature tree: values are recorded and the
// request-vs-created comparison fails the feature when the written values did not
// persist. Length type, length and angle are recorded but not asserted; leaving them
// unset is deliberate and their effective defaults remain an open live question.
static J flange_relief_side_echo(ProElement relief, int side) {
    ProElement item = get_path(relief, J::array({side}));
    int type = -1, depth_type = -1, length_type = -1;
    double width = 0, depth = 0, length = 0, angle = 0;
    CK(ProElementIntegerGet(get_path(item, J::array({PRO_E_BEND_RELIEF_TYPE})), nullptr, &type));
    CK(ProElementDoubleGet(get_path(item, J::array({PRO_E_BEND_RELIEF_WIDTH})), nullptr, &width));
    CK(ProElementIntegerGet(get_path(item, J::array({PRO_E_BEND_RELIEF_DEPTH_TYPE})), nullptr,
                            &depth_type));
    CK(ProElementDoubleGet(get_path(item, J::array({PRO_E_BEND_RELIEF_DEPTH})), nullptr, &depth));
    CK(ProElementIntegerGet(get_path(item, J::array({PRO_E_BEND_RELIEF_LENGTH_TYPE})), nullptr,
                            &length_type));
    CK(ProElementDoubleGet(get_path(item, J::array({PRO_E_BEND_RELIEF_LENGTH})), nullptr, &length));
    CK(ProElementDoubleGet(get_path(item, J::array({PRO_E_BEND_RELIEF_ANGLE})), nullptr, &angle));
    return {{"type", type},      {"width_mm", width},          {"depth_type", depth_type},
            {"depth_mm", depth}, {"length_type", length_type}, {"length_mm", length},
            {"angle", angle}};
}

static void flange_relief_expect(const char *name, const J &side, bool enabled,
                                 const FlangeReliefRequest &request) {
    int expected_type = enabled ? PRO_BEND_RLF_RECTANGULAR : PRO_BEND_RLF_NONE;
    int type = side.at("type").get<int>();
    if (type == expected_type &&
        (!enabled || (side.at("depth_type").get<int>() == PRO_BEND_RLF_DEPTH_BLIND &&
                      fabs(side.at("width_mm").get<double>() - request.width) <= 1e-6 &&
                      fabs(side.at("depth_mm").get<double>() - request.depth) <= 1e-6)))
        return;
    throw std::runtime_error(
        "flange relief did not persist into the created feature: " + std::string(name) +
        " recorded type=" + std::to_string(type) +
        " width=" + std::to_string(side.at("width_mm").get<double>()) +
        " depth_type=" + std::to_string(side.at("depth_type").get<int>()) +
        " depth=" + std::to_string(side.at("depth_mm").get<double>()) + "; requested " +
        (enabled ? "rectangular" : "none") + " width=" + std::to_string(request.width) +
        " depth=" + std::to_string(request.depth));
}

// FEAT-014: Creo fills omitted tree elements with defaults, so the miter section is
// read back out of the created feature and the request-vs-created comparison fails
// the feature when the written values did not persist. KEEP_DEF_AREAS is left
// unset on purpose (the SDK marks it optional); the echo records what Creo stored
// so a default it applies is visible instead of guessed.
static J flange_miter_echo(ProElement miter) {
    int add = -1, width_type = -1, offset_type = -1;
    double width = 0, offset = 0;
    CK(ProElementIntegerGet(get_path(miter, J::array({PRO_E_SMT_MTR_CUTS_ADD})), nullptr, &add));
    CK(ProElementIntegerGet(
        get_path(miter, J::array({PRO_E_SMT_MTR_CUTS_WIDTH, PRO_E_SMT_MTR_CUTS_WIDTH_TYPE})),
        nullptr, &width_type));
    CK(ProElementDoubleGet(
        get_path(miter, J::array({PRO_E_SMT_MTR_CUTS_WIDTH, PRO_E_SMT_MTR_CUTS_WIDTH_VAL})),
        nullptr, &width));
    CK(ProElementIntegerGet(
        get_path(miter, J::array({PRO_E_SMT_MTR_CUTS_OFFSET, PRO_E_SMT_MTR_CUTS_OFFSET_TYPE})),
        nullptr, &offset_type));
    CK(ProElementDoubleGet(
        get_path(miter, J::array({PRO_E_SMT_MTR_CUTS_OFFSET, PRO_E_SMT_MTR_CUTS_OFFSET_VAL})),
        nullptr, &offset));
    return {{"add", add},
            {"width_type", width_type},
            {"width_mm", width},
            {"offset_type", offset_type},
            {"offset_mm", offset}};
}

static void flange_miter_expect(const J &echo, const FlangeMiterRequest &request) {
    if (echo.at("add").get<int>() == PRO_B_TRUE &&
        echo.at("width_type").get<int>() == PRO_MITER_CUT_WIDTH_TYPE_BLIND &&
        echo.at("offset_type").get<int>() == PRO_MITER_CUT_OFFSET_TYPE_BLIND &&
        fabs(echo.at("width_mm").get<double>() - request.width) <= 1e-6 &&
        fabs(echo.at("offset_mm").get<double>() - request.offset) <= 1e-6)
        return;
    throw std::runtime_error("flange miter cuts did not persist into the created feature: add=" +
                             std::to_string(echo.at("add").get<int>()) +
                             " width_type=" + std::to_string(echo.at("width_type").get<int>()) +
                             " width=" + std::to_string(echo.at("width_mm").get<double>()) +
                             " offset_type=" + std::to_string(echo.at("offset_type").get<int>()) +
                             " offset=" + std::to_string(echo.at("offset_mm").get<double>()) +
                             "; requested gap width=" + std::to_string(request.width) +
                             " offset=" + std::to_string(request.offset));
}

// DEV-051 T11 2026-10-30: the only measured value here stays the part thickness; the
// corner run and the two comparisons are request arithmetic against the T05 overlap
// bound ((height - radius) x thickness^2 at a shared corner), not native geometry.
static J flange_relief_record(const J &op, const FlangeReliefRequest &request) {
    J sides = J::array();
    for (int index = 0; index < 2; index++) {
        bool enabled = index ? request.side2 : request.side1;
        J row = {{"side", index ? "side2" : "side1"},
                 {"relief_type", enabled ? "rectangular" : "none"}};
        if (enabled) {
            row["width_mm"] = request.width;
            row["depth_type"] = "blind";
            row["depth_mm"] = request.depth;
        }
        sides.push_back(row);
    }
    double thickness = 0;
    bool thickness_known = part_thickness_read(&thickness);
    bool enabled = request.side1 || request.side2;
    double corner_run = std::max(0.0, op["height"].get<double>() - op["radius"].get<double>());
    return {{"type", request.type},
            {"ends", request.ends},
            {"sides", sides},
            {"part_thickness_mm", thickness_known ? J(thickness) : J()},
            {"corner_overlap_run_mm", corner_run},
            {"width_at_least_thickness",
             thickness_known && enabled ? J(request.width >= thickness) : J()},
            {"depth_covers_corner_run", enabled ? J(request.depth >= corner_run) : J()}};
}

// DEV-052 N05: forward declaration - the failing create path records the same
// edge forensics as the unhealthy-feature path below.
static J flange_edge_forensics(const J &op);

// DEV-051 T05/T11: a flange wall can only attach to an edge that borders a
// sheetmetal face, so record Creo's own sheetmetal typing of the body's surfaces and
// the attachment edge's sheetmetal contour code next to the element trees.
// DEV-052 N05: staged forensics must stay bounded. Every surface is still logged
// above; the staged record carries at most this many rows.
static const int FLANGE_EVIDENCE_MAX_SURFACES = 64;
static ProError smt_surface_type_cb(ProSurface s, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    J *out = (J *)data;
    int id = -1;
    ProSurfaceIdGet(s, &id);
    ProSmtSurfType type = PRO_SMT_SURF_NON_SMT;
    ProError code = ProSmtSurfaceTypeGet((ProPart)board, s, &type);
    log("FLANGE_BODY_SURFACE id=%d smt_type=%d code=%d\n", id, (int)type, code);
    if (out->size() < FLANGE_EVIDENCE_MAX_SURFACES)
        out->push_back({{"id", id}, {"smt_type", (int)type}, {"code", code}});
    return PRO_TK_NO_ERROR;
}
// R10: resolves both edge reference shapes; defined with the geometry matcher
// below, declared here because the flange evidence helpers resolve first.
static ProSelection resolve_flange_edge(const J &edge_ref);
static void flange_attachment_evidence(const J &op, J *evidence) {
    try {
        ProSelection sel = resolve_flange_edge(op["edge"]);
        ProModelitem item;
        CK(ProSelectionModelitemGet(sel, &item));
        ProSelectionFree(&sel);
        ProEdge edge;
        CK(ProEdgeInit((ProSolid)board, item.id, &edge));
        ProEdge *contour = nullptr;
        ProError code = ProSmtedgeContourGet((ProPart)board, edge, &contour);
        int count = 0;
        if (!code) {
            CK(ProArraySizeGet((ProArray)contour, &count));
            ProArrayFree((ProArray *)&contour);
        }
        log("FLANGE_ATTACH_EDGE id=%d smt_contour_code=%d contour=%d\n", item.id, code, count);
        (*evidence)["attachment_edge"] = {
            {"id", item.id}, {"smt_edge_contour_code", code}, {"smt_edge_contour_count", count}};
    } catch (ProError code) {
        log("FLANGE_ATTACH_EDGE_FAILED=%d\n", code);
        (*evidence)["attachment_edge"] = {{"edge_error", code}};
    }
    try {
        auto body = active_body();
        J types = J::array();
        ProError code = ProSolidBodySurfaceVisit(&body, smt_surface_type_cb, &types);
        log("FLANGE_BODY_SURFACES code=%d count=%d\n", code, (int)types.size());
        (*evidence)["body_surface_code"] = code;
        (*evidence)["body_surfaces"] = types;
    } catch (ProError code) {
        log("FLANGE_BODY_SURFACES_FAILED=%d\n", code);
        (*evidence)["body_surface_code"] = code;
    }
}
// DEV-051 T05/T11 evidence: Creo answers the flange create with a bare -1
// (PRO_TK_GENERAL_ERROR) and an empty ProFeature error list, so neither the code nor
// the element errors name the rejected element. On the failing path only, this records
// both sides of the comparison the card asks for:
//   flange_attempt.xml  - the tree this implementation builds, before create;
//   flange_expected.xml - the tree Creo itself completes for a minimal incomplete
//                         flange feature (PRO_FEAT_CR_INCOMPLETE_FEAT + extract).
// Both files go to the job output directory and their paths, with every raw code, are
// staged into the failed operation record so the MCP result carries them. The probe
// feature is deleted again; a probe failure is logged and never replaces the original
// create error.
static void flange_tree_evidence(ProElement attempted, const J &op) {
    J evidence = J::object();
    flange_attachment_evidence(op, &evidence);
    try {
        evidence["edge_forensics"] = flange_edge_forensics(op);
    } catch (...) {
        log("FLANGE_EDGE_FORENSICS_FAILED=exception\n");
        evidence["edge_forensics"] = J();
    }
    auto dump = [&](ProElement root, const std::wstring &name, const std::string &key) {
        ProPath output;
        path(output, generic_job + L"\\output\\" + name);
        ProError code = ProElemtreeWrite(root, PRO_ELEMTREE_XML, output);
        log("FLANGE_TREE_%s code=%d file=%s\n", key.c_str(), code, utf8(output).c_str());
        evidence[key] = {{"code", code}, {"file", utf8(output)}};
    };
    dump(attempted, L"flange_attempt.xml", "attempted");
    ProElement probe = nullptr;
    try {
        probe = node(nullptr, PRO_E_FEATURE_TREE);
        integer(probe, PRO_E_FEATURE_TYPE, PRO_FEAT_WALL);
        integer(probe, PRO_E_SMT_WALL_TYPE, PRO_SMT_WALL_TYPE_FLANGE);
        integer(probe, PRO_E_SMT_FLANGE_TYPE, PRO_FLANGE_WALL_TYPE_2D_SWEPT);
        text(probe, PRO_E_STD_FEATURE_NAME,
             wide(op["label"].get<std::string>() + "_probe").c_str());
        ProFeature incomplete = create(probe, PRO_FEAT_CR_INCOMPLETE_FEAT);
        CK(ProElementFree(&probe));
        probe = nullptr;
        evidence["probe_feature_id"] = incomplete.id;
        ProElement expected = nullptr;
        ProError extracted =
            ProFeatureElemtreeExtract(&incomplete, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &expected);
        log("FLANGE_TREE_EXTRACT_INCOMPLETE_FEAT=%d\n", extracted);
        evidence["extract_code"] = extracted;
        if (!extracted && expected) {
            dump(expected, L"flange_expected.xml", "expected");
            ProFeatureElemtreeFree(&incomplete, expected);
        }
        ProIntlist ids = nullptr;
        CK(ProArrayAlloc(1, sizeof(int), 1, (ProArray *)&ids));
        ids[0] = incomplete.id;
        ProFeatureDeleteOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_DELETE_NO_OPTS;
        ProError removed =
            ProFeatureWithoptionsDelete((ProSolid)board, ids, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&ids);
        ProArrayFree((ProArray *)&options);
        log("FLANGE_TREE_PROBE_DELETE=%d\n", removed);
        evidence["probe_delete_code"] = removed;
    } catch (ProError code) {
        log("FLANGE_TREE_PROBE_FAILED=%d\n", code);
        evidence["probe_error"] = code;
        if (probe)
            ProElementFree(&probe);
    } catch (...) {
        log("FLANGE_TREE_PROBE_FAILED=exception\n");
        evidence["probe_error"] = "exception";
        if (probe)
            ProElementFree(&probe);
    }
    // DEV-052 N06: stage the evidence under the key the drivers read
    // (operations[].flange_failure_evidence). Staging the bare block flat made
    // the 2026-10-31 rerun report native_failure_evidence=null even though the
    // native log carried FLANGE_FAILURE_EVIDENCE.
    stage_operation_result({{"flange_failure_evidence", evidence}});
}

// DEV-052 N05 (2026-10-30): third-wall failure forensics. The 2026-10-30 live
// contrast proved the trigger - an attachment-edge end adjacent to an existing
// bend fails even alone - but not the mechanism: whether the section lands out of
// the bendable area or the wall material overlaps a neighbour is not decidable
// from a bare -1 or a status=6 result. These helpers record, on the failing path
// only and with every query failure left null, the measured facts N06 needs:
//   - the attachment edge's length and both end points (normalized params 0/1);
//   - the two faces sharing that edge with Creo's sheetmetal typing, and the
//     two contour-neighbour edges;
//   - the created feature's status and geometry item count right after the
//     regenerate (round six: PRO_FEAT_UNREGENERATED = 6, no geometry items);
//   - the sketch-frame section leg this implementation wrote (request echo; the
//     measured wall placement comes from the driver's inspection, not here).
// Nothing here changes create/regenerate behaviour, the health check verdict or
// the rollback; a forensics failure is logged and never replaces the original
// error.
static J flange_point_json(const ProVector &point, ProError code) {
    if (code)
        return J();
    return {{"x_mm", point[0]}, {"y_mm", point[1]}, {"z_mm", point[2]}};
}

// Reads a face's surface type and id for the adjacency diagnostics. Returns
// the ProSurfacedata type (PRO_SRF_* from ProSurfacedata.h) or -1 when the
// data cannot be read; *face_id is -1 when the id cannot be read.
static int flange_face_type_id(ProSurface face, int *face_id) {
    *face_id = -1;
    ProSurfaceIdGet(face, face_id);
    ProGeomitemdata *sdata = nullptr;
    if (ProSurfaceDataGet(face, &sdata) != PRO_TK_NO_ERROR || !sdata)
        return -1;
    ProSurfacedata *surf = PRO_SURF_DATA(sdata);
    int type = surf ? (int)surf->type : -1;
    ProGeomitemdataFree(&sdata);
    return type;
}

static J flange_edge_forensics(const J &op) {
    J evidence = J::object();
    ProSelection sel = resolve_flange_edge(op["edge"]);
    ProModelitem item;
    CK(ProSelectionModelitemGet(sel, &item));
    ProSelectionFree(&sel);
    ProEdge edge;
    CK(ProEdgeInit((ProSolid)board, item.id, &edge));
    evidence["id"] = item.id;
    double length = 0;
    ProError length_code = ProEdgeLengthEval(edge, &length);
    log("FLANGE_EDGE_FORENSICS id=%d length_code=%d\n", item.id, length_code);
    evidence["length_mm"] = length_code ? J() : J(length);
    ProVector start = {0, 0, 0}, start_d1, start_d2, start_dir;
    ProVector end = {0, 0, 0}, end_d1, end_d2, end_dir;
    ProError start_code = ProEdgeXyzdataEval(edge, 0.0, start, start_d1, start_d2, start_dir);
    ProError end_code = ProEdgeXyzdataEval(edge, 1.0, end, end_d1, end_d2, end_dir);
    log("FLANGE_EDGE_FORENSICS end_code=%d,%d\n", start_code, end_code);
    evidence["end0_mm"] = flange_point_json(start, start_code);
    evidence["end1_mm"] = flange_point_json(end, end_code);
    ProEdge neighbour1 = nullptr, neighbour2 = nullptr;
    ProSurface face1 = nullptr, face2 = nullptr;
    ProError neighbours_code = ProEdgeNeighborsGet(edge, &neighbour1, &neighbour2, &face1, &face2);
    evidence["neighbors_code"] = neighbours_code;
    if (neighbours_code) {
        log("FLANGE_EDGE_FORENSICS neighbors_code=%d\n", neighbours_code);
        evidence["adjacent_faces"] = J();
        evidence["adjacent_edges"] = J();
        return evidence;
    }
    J faces = J::array();
    for (ProSurface face : {face1, face2}) {
        int id = -1;
        ProSmtSurfType type = PRO_SMT_SURF_NON_SMT;
        ProError id_code = ProSurfaceIdGet(face, &id);
        ProError type_code = ProSmtSurfaceTypeGet((ProPart)board, face, &type);
        faces.push_back({{"id", id_code ? J() : J(id)},
                         {"smt_type", type_code ? J() : J((int)type)},
                         {"type_code", type_code}});
    }
    J edges = J::array();
    for (ProEdge neighbour : {neighbour1, neighbour2}) {
        int id = -1;
        ProError id_code = ProEdgeIdGet(neighbour, &id);
        edges.push_back({{"id", id_code ? J() : J(id)}, {"id_code", id_code}});
    }
    evidence["adjacent_faces"] = faces;
    evidence["adjacent_edges"] = edges;
    return evidence;
}

static void flange_created_feature_evidence(const J &op, const ProFeature &created) {
    ProFeature feature = created;
    ProFeatStatus status = PRO_FEAT_INACTIVE;
    ProError status_code = ProFeatureStatusGet(&feature, &status);
    if (status_code)
        log("FLANGE_CREATED_STATUS_QUERY code=%d\n", status_code);
    if (status_code || status == PRO_FEAT_ACTIVE)
        return; // healthy or unqueryable: the shared health check stays the judge
    J evidence = J::object();
    evidence["stage"] = "after_regenerate";
    evidence["feature_status"] = (int)status;
    evidence["feature_status_name"] = status == PRO_FEAT_UNREGENERATED ? "unregenerated" : "other";
    evidence["feature_id"] = feature.id;
    J geometry = J::array();
    ProError geometry_code =
        ProFeatureGeomitemVisit(&feature, PRO_TYPE_UNUSED, collect_geom_ids, nullptr, &geometry);
    evidence["geometry_visit_code"] = geometry_code;
    evidence["geometry_item_count"] = geometry.size();
    log("FLANGE_CREATED_UNHEALTHY id=%d status=%d geometry=%d geom_code=%d\n", feature.id,
        (int)status, (int)geometry.size(), geometry_code);
    try {
        evidence["edge_forensics"] = flange_edge_forensics(op);
        double a = op["angle"].get<double>() * acos(-1.0) / 180;
        double h = op["height"].get<double>();
        evidence["section_leg_sketch"] = {
            {"leg_dx", h * sin(a)},
            {"leg_dy", h * cos(a)},
            {"angle_deg", op["angle"]},
            {"height_mm", h},
            {"note", "request echo of the sketch-frame leg; measured wall placement comes "
                     "from the driver's inspection, not from here"}};
    } catch (...) {
        log("FLANGE_EDGE_FORENSICS_FAILED=exception\n");
        evidence["edge_forensics"] = J();
    }
    log("FLANGE_FAILURE_EVIDENCE=%s\n", evidence.dump().c_str());
    // DEV-052 N06: nested under the key the drivers read; see the note in
    // flange_tree_evidence about the flat-staging propagation gap.
    stage_operation_result({{"flange_failure_evidence", evidence}});
}

// DEV-052 N06 (FEAT-014): the 2026-10-31 N05 rerun proved, on real plate-top
// edges, that a flange whose attachment-edge end abuts an existing bend fails
// inside regeneration (feature_status=6, geometry_item_count=0) while the free
// edge builds, and the failure evidence cannot separate section overrun from
// neighbouring-material overlap - the SDK offers no proven corner relief/miter
// API for this create path. This pre-check therefore repairs nothing. Before
// any element tree exists it looks for the confirmed trigger shape at each end
// of the attachment edge and requires BOTH positive signals:
//   1. adjacency - an edge meeting the attachment edge at that end (vertex
//      fan, ProEdgeVertexdataGet) is an arc that borders a cylindrical face
//      (the bend region's boundary);
//   2. consumption - the arc radius stays within the bend-setback bound
//      radius <= 2*(radius + thickness) + tolerance, so the end was consumed by
//      a bend and not by unrelated curvature. The confirmed 2026-10-31 walls
//      consumed exactly radius+thickness = 3.54 mm of flat per end against the
//      2*(2.54+1) = 7.08 mm bound; for bends up to 90 degrees the flat setback
//      never exceeds the outside arc radius, so the radius bound implements the
//      prescribed "edge shortening <= 2*(R+t) + tolerance" conservatively.
// One end suffices: the live contrast showed a single adjacent end already
// fails the wall. Every query failure, a missing part thickness (read through
// part_thickness_read, which BUG-032 notes can be the part-level default rather
// than the wall thickness - the bound is deliberately generous) or a straight
// neighbour leaves the check silent and returns an empty object, so free-edge
// walls (the T03 first-wall contract included) keep the old behaviour exactly.
// The rejection itself happens in generic_sheetmetal_flange, which stages this
// evidence under flange_failure_evidence and fails the job with
// failure_reason=adjacent_bend_ends before any feature is created.
static const double FLANGE_ADJACENT_BEND_TOLERANCE_MM = 1e-3;

static J flange_adjacent_bend_end_evidence(const J &op, int edge_id) {
    J evidence = J::object();
    try {
        double radius = op["radius"].get<double>();
        double thickness = 0;
        bool thickness_known = part_thickness_read(&thickness);
        if (!thickness_known) {
            log("FLANGE_ADJACENT_BEND skip=thickness_unknown\n");
            return J::object();
        }
        double bound = 2 * (radius + thickness) + FLANGE_ADJACENT_BEND_TOLERANCE_MM;
        ProEdge edge;
        CK(ProEdgeInit((ProSolid)board, edge_id, &edge));
        double length = 0;
        ProError length_code = ProEdgeLengthEval(edge, &length);
        ProVector end0, d0a, d0b, d0c, end1, d1a, d1b, d1c;
        ProError end0_code = ProEdgeXyzdataEval(edge, 0.0, end0, d0a, d0b, d0c);
        ProError end1_code = ProEdgeXyzdataEval(edge, 1.0, end1, d1a, d1b, d1c);
        J ends = J::array({{{"end", 0},
                            {"point_mm", flange_point_json(end0, end0_code)},
                            {"adjacent_bend_end", false}},
                           {{"end", 1},
                            {"point_mm", flange_point_json(end1, end1_code)},
                            {"adjacent_bend_end", false}}});
        bool any_hit = false;
        // ProEdge.h semantics, verified against the SDK header (2026-10-31):
        // ProEdgeNeighborsGet's p_edge1/p_edge2 are "the next edge in the
        // contour on p_face1/p_face2" - the contour walk direction is a face
        // storage detail, so BOTH returned edges can sit at the SAME end of
        // the input edge. The 2026-10-31 live rerun hit exactly that on
        // plate-top edge 197: neighbours 207/104 both resolved to the free
        // corner, the bend-side arc was never examined, and unmatched=0 only
        // meant "matched some end". ProEdgeVertexdataGet is the documented
        // per-end primitive - for PRO_EDGE_START / PRO_EDGE_END it returns
        // every edge meeting at that end (p_vertex_arr) plus the surfaces
        // adjacent to those edges (p_surf_arr) - which is the enumeration the
        // adjacency criterion always meant.
        for (ProType end_query : {PRO_EDGE_START, PRO_EDGE_END}) {
            int which = end_query == PRO_EDGE_START ? 0 : 1;
            ProEdgelist end_edges = nullptr;
            ProType *end_types = nullptr;
            ProSurflist end_surfs = nullptr;
            int end_count = 0;
            ProError vertex_code = ProEdgeVertexdataGet(edge, end_query, &end_edges, &end_types,
                                                        &end_surfs, &end_count);
            if (vertex_code) {
                log("FLANGE_ADJACENT_BEND end=%d vertex_code=%d\n", which, vertex_code);
                continue;
            }
            std::string end_faces;
            for (int i = 0; i < end_count && i < 16; ++i) {
                int face_id = -1;
                int face_type = flange_face_type_id(end_surfs[i], &face_id);
                end_faces += (end_faces.empty() ? "" : ";");
                end_faces += std::to_string(face_id) + ":" + std::to_string(face_type);
            }
            log("FLANGE_ADJACENT_BEND_END end=%d edges=%d faces=%s\n", which, end_count,
                end_faces.c_str());
            bool end_hit = ends[which].value("adjacent_bend_end", false);
            for (int i = 0; i < end_count && i < 16; ++i) {
                ProEdge nb = end_edges[i];
                int nb_id = -1;
                ProEdgeIdGet(nb, &nb_id);
                if (nb_id == edge_id)
                    continue; // the attachment edge meets at its own end
                ProGeomitemdata *data = nullptr;
                ProError data_code = ProEdgeDataGet(nb, &data);
                ProCurvedata *curve = data ? PRO_CURVE_DATA(data) : nullptr;
                // ProCurvedata is a union (ProCurvedata.h) - it has no top-level
                // "type" member; the SDK accessor ProCurvedataTypeGet reads the
                // type shared by every union arm (ProObjects.h: PRO_ENT_ARC = 3).
                ProEnttype curve_ent = PRO_ENT_NONE;
                int curve_type =
                    (curve && ProCurvedataTypeGet(curve, &curve_ent) == PRO_TK_NO_ERROR)
                        ? (int)curve_ent
                        : -1;
                double arc_radius = 0;
                ProVector arc_v1, arc_v2, arc_origin;
                double arc_start = 0, arc_end = 0;
                bool is_arc = !data_code && curve && curve_type == PRO_ENT_ARC &&
                              ProArcdataGet(curve, arc_v1, arc_v2, arc_origin, &arc_start, &arc_end,
                                            &arc_radius) == PRO_TK_NO_ERROR;
                // The neighbour edge's own two faces: ProEdge.h documents
                // ProEdgeNeighborsGet's p_face1/p_face2 as the input edge's
                // adjacent surfaces ("The first/second adjacent surface"), so
                // calling it on the neighbour returns exactly the faces that
                // neighbour borders - the cylinder check keeps its pairing to
                // the arc instead of scanning the whole vertex fan.
                J bend_faces = J::array();
                std::string nb_faces;
                {
                    ProEdge fa1 = nullptr, fa2 = nullptr;
                    ProSurface sfa = nullptr, sfb = nullptr;
                    ProError nb_faces_code = ProEdgeNeighborsGet(nb, &fa1, &fa2, &sfa, &sfb);
                    if (nb_faces_code) {
                        nb_faces = "code=" + std::to_string((int)nb_faces_code);
                    } else {
                        for (ProSurface face : {sfa, sfb}) {
                            if (!face)
                                continue;
                            int face_id = -1;
                            int face_type = flange_face_type_id(face, &face_id);
                            nb_faces += (nb_faces.empty() ? "" : ";");
                            nb_faces += std::to_string(face_id) + ":" + std::to_string(face_type);
                            if (face_type == PRO_SRF_CYL)
                                bend_faces.push_back(face_id);
                        }
                    }
                }
                if (data)
                    ProGeomitemdataFree(&data);
                bool adjacent = is_arc && !bend_faces.empty() && arc_radius <= bound;
                log("FLANGE_ADJACENT_BEND_NB end=%d id=%d curve_type=%d is_arc=%d "
                    "radius=%.4f faces=%s\n",
                    which, nb_id, curve_type, is_arc ? 1 : 0, is_arc ? arc_radius : 0.0,
                    nb_faces.c_str());
                // Keep the first adjacency hit's evidence for this end: a
                // later non-adjacent neighbour (e.g. the straight edge after
                // the bend arc in the vertex fan) must not overwrite the arc's
                // radius with null - the summary reads it as a number.
                if (!end_hit || adjacent) {
                    J row = {{"neighbor_edge_id", nb_id},
                             {"neighbor_edge_type", curve_type},
                             {"neighbor_arc", is_arc},
                             {"neighbor_radius_mm", is_arc ? J(arc_radius) : J()},
                             {"radius_bound_mm", bound},
                             {"bend_face_ids", bend_faces},
                             {"adjacent_bend_end", adjacent}};
                    row["point_mm"] = ends[which].at("point_mm");
                    ends[which].update(row);
                }
                if (adjacent) {
                    end_hit = true;
                    any_hit = true;
                }
                ends[which]["adjacent_bend_end"] = end_hit;
            }
            ProArrayFree((ProArray *)&end_edges);
            ProArrayFree((ProArray *)&end_types);
            ProArrayFree((ProArray *)&end_surfs);
        }
        log("FLANGE_ADJACENT_BEND edge=%d end0=%d end1=%d\n", edge_id,
            ends[0].value("adjacent_bend_end", false) ? 1 : 0,
            ends[1].value("adjacent_bend_end", false) ? 1 : 0);
        if (!any_hit)
            return J::object();
        evidence["stage"] = "before_create";
        evidence["edge_id"] = edge_id;
        evidence["edge_length_mm"] = length_code ? J() : J(length);
        evidence["radius_mm"] = radius;
        evidence["part_thickness_mm"] = thickness;
        evidence["radius_bound_mm"] = bound;
        evidence["tolerance_mm"] = FLANGE_ADJACENT_BEND_TOLERANCE_MM;
        evidence["ends"] = ends;
        return evidence;
    } catch (ProError code) {
        log("FLANGE_ADJACENT_BEND_FAILED=%d\n", code);
        return J::object();
    } catch (...) {
        log("FLANGE_ADJACENT_BEND_FAILED=exception\n");
        return J::object();
    }
}

static std::string flange_adjacent_ends_summary(const J &evidence) {
    std::string summary;
    // Copy, not pointer: value() returns a temporary that would dangle in a
    // pointer initializer_list before the loop body runs.
    const J rows = evidence.value("ends", J::array());
    for (const auto &row : rows) {
        if (!row.value("adjacent_bend_end", false))
            continue;
        summary += (summary.empty() ? "" : "; ");
        summary += "end";
        summary += row.contains("end") && row["end"].is_number()
                       ? std::to_string(row["end"].get<int>())
                       : std::string("?");
        summary += ": neighbour arc edge ";
        summary += row.contains("neighbor_edge_id") && row["neighbor_edge_id"].is_number()
                       ? std::to_string(row["neighbor_edge_id"].get<int>())
                       : std::string("?");
        summary += " radius ";
        summary += row.contains("neighbor_radius_mm") && row["neighbor_radius_mm"].is_number()
                       ? std::to_string(row["neighbor_radius_mm"].get<double>())
                       : std::string("?");
        summary += " mm within the bend-setback bound ";
        summary += row.contains("radius_bound_mm") && row["radius_bound_mm"].is_number()
                       ? std::to_string(row["radius_bound_mm"].get<double>())
                       : std::string("?");
        summary += " mm, bend faces ";
        summary += row["bend_face_ids"].dump();
    }
    return summary;
}

// R09 (FEAT-014, 0.13.0 feedback §3.3): the pre-create error must not hand a
// native_planar model the conversion-only wall_contract recipe. The first-wall
// source is recorded in the model's aliases: wall_contract only for the
// thin-extrusion conversion (creo_sheetmetal_wall), planar_wall only for
// creo_sheetmetal_planar_wall. When neither is present the source is unknown,
// so no first-wall recipe is offered instead of defaulting to the old one.
static std::string flange_first_wall_guide() {
    bool planar = false, conversion = false;
    for (auto item = aliases.begin(); item != aliases.end(); ++item) {
        const J &record = item.value();
        if (!record.is_object())
            continue;
        if (record.contains("planar_wall") && record["planar_wall"].is_object())
            planar = true;
        if (record.contains("wall_contract") && record["wall_contract"].is_object())
            conversion = true;
    }
    if (planar && !conversion)
        return "This model's first wall was created by creo_sheetmetal_planar_wall "
               "(template='native_planar'); that wall's result carries the measured frame "
               "(origin/u_axis/v_axis/normal) and envelope. Pick an edge on a green/white wall "
               "face boundary of that wall; this model has no wall_contract.";
    if (conversion && !planar)
        return "Frame contract: depth grows one-sided along the signed sketch normal and "
               "thickness is the sheet gauge spread centered on the sketch line, so the "
               "green/white wall faces are the gauge faces (see wall_contract.wall_face_ids). "
               "To build a horizontal base plate whose large faces are the wall faces, sketch "
               "on the YZ plane (or a YZ plane with offset) one line along +Y and call "
               "sheetmetal_wall with depth=plate size along the normal and thickness=sheet "
               "thickness; the frozen recipe with coordinates is "
               "examples/sheetmetal_base_yz.json. Confirm the result via wall_contract.frame "
               "and wall_face_ids before attaching flanges.";
    return "This model does not report which first wall created it, so no first-wall recipe is "
           "given here. Re-read the wall faces with creo_inspect_model and pick an edge on a "
           "green/white wall face boundary.";
}

static std::string flange_edge_reference_contract() {
    const int index = generated_identity_index();
    return "operations[i].edge must be {kind:'edge',id:N} whose id is the current edge id read "
           "from creo_inspect_model, or {kind:'edge_geometry',endpoints_mm:[[x,y,z],[x,y,z]],"
           "tolerance_mm:1e-6} whose two straight-edge endpoints match exactly one current model "
           "edge; here i=" +
           std::to_string(index) + " (operations[" + std::to_string(index) + "].edge)";
}

// R10: edge ids change whenever the model rebuilds, so a plan that must keep
// targeting one physical edge can name its two straight-edge endpoints in
// millimetres instead. The match is undirected, must be unique and is re-queried
// on every operation; non-straight edges and an unknown model length unit are
// refused rather than guessed. {kind:'edge',id:N} keeps working unchanged.
struct FlangeEdgeScan {
    V points[2];
    double tolerance = 1e-6;
    double scale = 1;
    std::set<int> seen;
    std::set<int> matches;
    std::vector<geometry_diagnostics::Candidate> candidates;
    int straight = 0;
};
static bool flange_point_within(const V &actual, const V &expected, double tolerance) {
    return fabs(actual[0] - expected[0]) <= tolerance &&
           fabs(actual[1] - expected[1]) <= tolerance && fabs(actual[2] - expected[2]) <= tolerance;
}
static ProError flange_match_edge(ProEdge edge, ProError status, ProAppData data) {
    auto *scan = (FlangeEdgeScan *)data;
    int id = -1;
    if (status || ProEdgeIdGet(edge, &id))
        return PRO_TK_NO_ERROR;
    ProGeomitemdata *geometry = nullptr;
    if (ProEdgeDataGet(edge, &geometry) || !geometry)
        return PRO_TK_NO_ERROR;
    Pro3dPnt start = {}, end = {};
    auto curve = geometry->data.p_curve_data;
    bool straight = curve && !ProLinedataGet(curve, start, end);
    ProGeomitemdataFree(&geometry);
    if (!straight || !scan->seen.insert(id).second)
        return PRO_TK_NO_ERROR;
    scan->straight++;
    V first = {start[0] * scan->scale, start[1] * scan->scale, start[2] * scan->scale};
    V second = {end[0] * scan->scale, end[1] * scan->scale, end[2] * scan->scale};
    scan->candidates.push_back(geometry_diagnostics::candidate(id, first, second, scan->points));
    if ((flange_point_within(first, scan->points[0], scan->tolerance) &&
         flange_point_within(second, scan->points[1], scan->tolerance)) ||
        (flange_point_within(second, scan->points[0], scan->tolerance) &&
         flange_point_within(first, scan->points[1], scan->tolerance)))
        scan->matches.insert(id);
    return PRO_TK_NO_ERROR;
}
struct FlangeSurfaceScan {
    ProSurface surface;
    FlangeEdgeScan *scan;
};
static ProError flange_match_contour(ProContour contour, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    auto *context = (FlangeSurfaceScan *)data;
    return ProContourEdgeVisit(context->surface, contour, flange_match_edge, nullptr,
                               context->scan);
}
static ProError flange_match_surface(ProSurface surface, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    FlangeSurfaceScan context{surface, (FlangeEdgeScan *)data};
    return ProSurfaceContourVisit(surface, flange_match_contour, nullptr, &context);
}
static int flange_geometry_edge_id(const J &edge_ref) {
    FlangeEdgeScan scan;
    scan.tolerance = edge_ref.value("tolerance_mm", 1e-6);
    for (int end = 0; end < 2; end++) {
        auto point = edge_ref.at("endpoints_mm").at(end);
        scan.points[end] = {point.at(0).get<double>(), point.at(1).get<double>(),
                            point.at(2).get<double>()};
    }
    InspectionLengthUnits units = inspect_length_units((ProMdl)board);
    MillimeterScale scale = length_scale_to_mm((ProMdl)board, units);
    if (!scale.known)
        throw std::runtime_error(
            "sheetmetal_flange edge_geometry cannot convert the model length unit to "
            "millimetres; pass {kind:'edge',id:N} from creo_inspect_model instead");
    scan.scale = scale.scale;
    ProSolidBody *bodies = nullptr;
    int count = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &bodies));
    CK(ProArraySizeGet((ProArray)bodies, &count));
    for (int index = 0; index < count; index++) {
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&bodies[index], &state));
        if (state != PRO_BODY_STATE_ACTIVE)
            continue;
        CK(ProSolidBodySurfaceVisit(&bodies[index], flange_match_surface, (ProAppData)&scan));
    }
    auto point_text = [&scan](int end) {
        return "[" + std::to_string(scan.points[end][0]) + ", " +
               std::to_string(scan.points[end][1]) + ", " + std::to_string(scan.points[end][2]) +
               "]";
    };
    log("FLANGE_EDGE_GEOMETRY straight=%d matches=%d tolerance=%.9f\n", scan.straight,
        (int)scan.matches.size(), scan.tolerance);
    if (scan.matches.size() == 1)
        return *scan.matches.begin();
    if (scan.matches.empty()) {
        std::string nearest;
        J nearest_edges = J::array();
        auto mm = [](double value) {
            std::ostringstream stream;
            stream << std::setprecision(12) << value;
            return stream.str();
        };
        for (const auto &item : geometry_diagnostics::nearest_candidates(scan.candidates)) {
            nearest_edges.push_back(
                {{"id", item.id},
                 {"endpoints_mm", J::array({J::array({item.endpoints[0][0], item.endpoints[0][1],
                                                      item.endpoints[0][2]}),
                                            J::array({item.endpoints[1][0], item.endpoints[1][1],
                                                      item.endpoints[1][2]})})},
                 {"endpoint_errors_mm",
                  J::array({item.endpoint_errors_mm[0], item.endpoint_errors_mm[1]})}});
            auto point = [&mm](const geometry_diagnostics::Point &value) {
                return "[" + mm(value[0]) + ", " + mm(value[1]) + ", " + mm(value[2]) + "]";
            };
            nearest += (nearest.empty() ? "" : "; ") + std::string("id=") +
                       std::to_string(item.id) + " endpoints_mm=" + point(item.endpoints[0]) + "," +
                       point(item.endpoints[1]) + " endpoint_errors_mm=[" +
                       mm(item.endpoint_errors_mm[0]) + ", " + mm(item.endpoint_errors_mm[1]) + "]";
        }
        stage_operation_result({{"edge_geometry_diagnostic",
                                 {{"nearest_edges", nearest_edges},
                                  {"tolerance_mm", scan.tolerance},
                                  {"candidate_limit", 5},
                                  {"straight_edge_count", scan.straight}}}});
        throw std::runtime_error(
            "sheetmetal_flange edge_geometry endpoints " + point_text(0) + " and " + point_text(1) +
            " matched none of the " + std::to_string(scan.straight) +
            " straight model edges (tolerance_mm=" + std::to_string(scan.tolerance) +
            "); nearest straight edges (diagnostic only; endpoint errors use the best "
            "undirected one-to-one request pairing): " +
            (nearest.empty() ? "none" : nearest) +
            "; edge ids and geometry change when the model rebuilds, so re-read "
            "creo_inspect_model edges[].start/end and pass current coordinates");
    }
    std::string ids;
    for (int id : scan.matches)
        ids += (ids.empty() ? "" : ", ") + std::to_string(id);
    throw std::runtime_error(
        "sheetmetal_flange edge_geometry endpoints " + point_text(0) + " and " + point_text(1) +
        " matched " + std::to_string(scan.matches.size()) + " edges (ids " + ids +
        "); use a smaller tolerance_mm or endpoints that belong to exactly one edge");
}
static ProSelection resolve_flange_edge(const J &edge_ref) {
    if (edge_ref.value("kind", "") == "edge")
        return resolve(edge_ref);
    return selection(flange_geometry_edge_id(edge_ref), PRO_EDGE);
}

static void generic_sheetmetal_flange(const J &op) {
    // Validate the relief request before any feature exists so an unsupported
    // combination cannot leave a created-but-wrong wall behind.
    FlangeReliefRequest relief_request = flange_relief_request(op);
    // FEAT-014: the miter request is the only documented release for the
    // adjacent-bend-ends guard below; it is validated here for the same reason.
    FlangeMiterRequest miter_request = flange_miter_request(op);
    J adjacent_allowed;
    int edge_id = -1;
    // R09/R10: name the plan position and the accepted reference shapes before
    // the generic resolver can answer with a bare {kind:...} message.
    {
        J edge_ref = op.value("edge", J());
        bool valid =
            edge_ref.is_object() && edge_ref.contains("kind") && edge_ref["kind"].is_string();
        if (valid && edge_ref["kind"] == "edge")
            valid = edge_ref.contains("id") && edge_ref["id"].is_number_integer() &&
                    edge_ref["id"].get<long long>() >= 0 &&
                    edge_ref["id"].get<long long>() <= 2147483647LL;
        else if (valid && edge_ref["kind"] == "edge_geometry") {
            J endpoints = edge_ref.contains("endpoints_mm") ? edge_ref["endpoints_mm"] : J::array();
            valid = endpoints.is_array() && endpoints.size() == 2;
            for (auto point : endpoints) {
                valid = valid && point.is_array() && point.size() == 3;
                for (auto coordinate : point)
                    valid =
                        valid && coordinate.is_number() && std::isfinite(coordinate.get<double>());
            }
            double tolerance = edge_ref.value("tolerance_mm", 1e-6);
            valid = valid && std::isfinite(tolerance) && tolerance >= 1e-9 && tolerance <= 1000;
        } else
            valid = false;
        if (!valid)
            throw std::runtime_error("sheetmetal_flange " + flange_edge_reference_contract() +
                                     "; got " + edge_ref.dump());
    }
    // DEV-051 T05/T11: a flange can only attach to an edge that borders a sheetmetal
    // wall face. Creo's own query answers PRO_TK_BAD_CONTEXT (-8) for an edge of a side
    // (rim) surface, and ProFeatureWithoptionsCreate then fails with a bare -1 and an
    // empty element error list. Reject that input here, carrying the raw code, so the
    // caller is not sent back to guessing.
    {
        ProSelection probe = resolve_flange_edge(op["edge"]);
        ProModelitem item;
        CK(ProSelectionModelitemGet(probe, &item));
        ProSelectionFree(&probe);
        edge_id = item.id;
        ProEdge handle;
        CK(ProEdgeInit((ProSolid)board, item.id, &handle));
        ProEdge *contour = nullptr;
        ProError code = ProSmtedgeContourGet((ProPart)board, handle, &contour);
        int count = 0;
        if (!code) {
            CK(ProArraySizeGet((ProArray)contour, &count));
            ProArrayFree((ProArray *)&contour);
        }
        log("FLANGE_ATTACH_EDGE id=%d smt_contour_code=%d smt_contour=%d\n", item.id, code, count);
        if (code == PRO_TK_BAD_CONTEXT)
            throw std::runtime_error(
                "sheetmetal_flange cannot attach to edge " + std::to_string(item.id) + " (" +
                flange_edge_reference_contract() +
                "): ProSmtedgeContourGet returned PRO_TK_BAD_CONTEXT (-8), so this edge is not "
                "on a sheetmetal wall face (green/white contour). Pick an edge on a wall face "
                "boundary: an edge shared by two side/rim surfaces cannot carry a flange. " +
                flange_first_wall_guide());
    }
    // DEV-052 N06 (FEAT-014): the confirmed trigger shape - an attachment-edge
    // end adjacent to an existing bend - is refused here, before any feature
    // exists, instead of failing inside regeneration and rolling back. See
    // flange_adjacent_bend_end_evidence for the dual-evidence criterion and its
    // default compatibility: a silent check never blocks the stock path.
    // R09 (0.13.0 feedback §3.1): a supplied bend-end relief parameter
    // (relief_request) never bypasses the refusal, because that relief is not
    // proven to remove corner overlap. FEAT-014 (2026-11-06) adds exactly one
    // release: an explicit miter_cuts request, which puts PRO_E_SMT_MTR_CUTS on
    // the same wall feature so Creo cuts the overlap itself. Without that
    // request the guard behaves exactly as before.
    {
        J adjacency = flange_adjacent_bend_end_evidence(op, edge_id);
        if (!adjacency.empty() && !miter_request.requested) {
            adjacency["failure_reason"] = "adjacent_bend_ends";
            std::string summary = flange_adjacent_ends_summary(adjacency);
            stage_operation_result({{"flange_failure_evidence", adjacency}});
            log("FLANGE_ADJACENT_BEND_REJECT edge=%d %s\n", adjacency["edge_id"].get<int>(),
                summary.c_str());
            throw std::runtime_error(
                "sheetmetal_flange rejected before create (failure_reason=adjacent_bend_ends): "
                "attachment edge " +
                std::to_string(adjacency["edge_id"].get<int>()) +
                " has end(s) adjacent to existing bends: " + summary +
                ". The 2026-10-31 live probes proved this shape fails inside regeneration "
                "(feature_status=6, no geometry) and the failure evidence cannot separate "
                "section overrun from neighbouring-material overlap. The current bend-end relief "
                "is not proven to resolve this corner "
                "overlap: it trims a bend end, not "
                "a corner run or miter. To build such a wall, pass miter_cuts {width, offset} "
                "(FEAT-014): that adds the native PRO_E_SMT_MTR_CUTS gap to this flange so Creo "
                "cuts the end overlap; without it the adjacent guard refuses the wall before "
                "submission whatever relief the caller passes. Attach the flange to an edge "
                "whose ends are clear of existing bends, or request miter_cuts.");
        }
        if (!adjacency.empty()) {
            // Allowed only by the explicit miter request; the evidence is kept in
            // the operation extra so the release is visible in the result.
            adjacency["failure_reason"] = "adjacent_bend_ends";
            adjacency["allowed_by_miter_cut"] = true;
            log("FLANGE_ADJACENT_BEND_ALLOWED edge=%d miter=on\n", adjacency["edge_id"].get<int>());
            adjacent_allowed = adjacency;
        }
    }
    ProSection section;
    CK(ProSection2DAlloc(&section));
    ProName section_name;
    wcscpy_s(section_name, wide(op["label"]).c_str());
    CK(ProSectionNameSet(section, section_name));
    // DEV-051 T05/T11 fourth round: build the section like the stock shapes in
    // <creo_root>/Common Files/text/smt/flange_shapes - every one of them holds a single
    // line, one coordinate system and one length dimension, and none holds a centerline.
    // The leg is measured from the plane normal, not from the parent wall plane: Creo
    // sweeps the section along the edge, sketch +x is the direction normal to the parent
    // wall and sketch +y lies inside the parent wall. Angle 90 therefore needs the leg on
    // sketch +x, and angle 0 is a straight in-plane continuation. The drawn sign does not
    // pick the bend side (Creo normalises it); PRO_E_SMT_FLANGE_SEC_FLIP does, see below.
    double a = op["angle"].get<double>() * acos(-1.0) / 180, h = op["height"];
    double leg[2] = {h * sin(a), h * cos(a)};
    J profile = {{"profile", J::array({{{"type", "line"},
                                        {"name", "wall"},
                                        {"start", J::array({0, 0})},
                                        {"end", J::array({leg[0], leg[1]})}}})},
                 {"dimensions", J::array({{{"name", "height"},
                                           {"type", "length"},
                                           {"refs", J::array({{{"entity", "wall"}}})},
                                           {"value", h},
                                           {"position", J::array({leg[0] * 0.5 + 2 * cos(a),
                                                                  leg[1] * 0.5 - 2 * sin(a)})}}})},
                 {"constraints", J::array()}};
    J extra = populate_profile(section, profile);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_WALL);
    integer(root, PRO_E_SMT_WALL_TYPE, PRO_SMT_WALL_TYPE_FLANGE);
    integer(root, PRO_E_SMT_FLANGE_TYPE, PRO_FLANGE_WALL_TYPE_2D_SWEPT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection edge = resolve_flange_edge(op["edge"]);
    ProReference edge_ref;
    CK(ProSelectionToReference(edge, &edge_ref));
    ProCollection chain;
    CK(ProCrvcollectionAlloc(&chain));
    ProCrvcollinstr instruction;
    CK(ProCrvcollinstrAlloc(PRO_CURVCOLL_TAN_INSTR, &instruction));
    CK(ProCrvcollinstrReferenceAdd(instruction, edge_ref));
    CK(ProCrvcollectionInstructionAdd(chain, instruction));
    CK(ProElementCollectionSet(node(root, PRO_E_STD_CURVE_COLLECTION_APPL), chain));
    ProCollectionFree(&chain);
    ProSelectionFree(&edge);
    // BUG-047 / DEV-051 A: the edge chain normal is not the direction switch. With
    // flip=false (PRO_FLANGE_TRAJ_NORM_NO_FLIP = 1) and flip=true (-1) the 2026-10-29
    // 22:06 run produced identical bbox, identical volume and the same side, and
    // ProSmtFlangeWall.h lists only PRO_B_TRUE/PRO_B_FALSE for this element, so -1 is not
    // a usable second value. It stays at the stock NO_FLIP like ptu_featcreat's
    // UgSmtFlgWallCreate.c. PRO_E_SMT_FLANGE_SEC_FLIP is what moves the bend, measured on
    // the same h80/R2.54/Y0.5 flange: top edge FALSE -> down, TRUE -> up; bottom edge
    // FALSE -> up, TRUE -> down. The rule is relative to the attachment face, so TRUE is
    // "out of the face you selected" and is the default; `flip` asks for the material side.
    integer(root, PRO_E_SMT_FLANGE_TRAJ_CRV_NORM, PRO_FLANGE_TRAJ_NORM_NO_FLIP);
    ProElement sec = node(root, PRO_E_STD_SECTION);
    integer(sec, PRO_E_STD_SEC_METHOD, PRO_SEC_SKETCH);
    CK(ProElementSpecialvalueSet(node(sec, PRO_E_SKETCHER), (ProAppData)section));
    integer(root, PRO_E_SMT_WALL_SHARPS_TO_BENDS, PRO_B_TRUE);
    int sec_flip = op.value("flip", false) ? PRO_B_FALSE : PRO_B_TRUE;
    integer(root, PRO_E_SMT_FLANGE_SEC_FLIP, sec_flip);
    log("FLANGE_SIDE sec_flip=%d bend_side=%s\n", sec_flip,
        sec_flip == PRO_B_TRUE ? "outward" : "inward");
    // DEV-051 T05 (2026-10-30): the third-wall trimmed contrast needs a flange that
    // stops short of both chain ends. Without end_trim_mm the tree is byte-for-byte
    // the old one (both sides TO_END, same as the stock UgSmtFlgWallCreate.c). With
    // it, both sides become blind with the requested offset. ProSmtFlangeWall.h only
    // documents DEPTH_OFFSET as "double", so whether Creo measures that offset as a
    // setback from each chain end or a wall length from the section is not decidable
    // offline: the T05 box driver first probes the semantics on a free first wall
    // (measured volume classifies the interpretation) and only then uses the trim on
    // the third wall. This branch exists to make that mandated contrast runnable.
    bool trim_requested = op.contains("end_trim_mm") && !op.at("end_trim_mm").is_null();
    double trim = 0.0;
    if (trim_requested) {
        trim = op.at("end_trim_mm").get<double>();
        if (!(trim > 0.0))
            throw std::runtime_error(
                "sheetmetal_flange end_trim_mm must be a number greater than 0 in model "
                "units; omit it for the full-edge wall");
        log("FLANGE_END_TRIM requested_mm=%.6f\n", trim);
    }
    ProElement depth = node(root, PRO_E_SMT_FLANGE_DEPTH);
    if (trim_requested) {
        integer(node(depth, PRO_E_SMT_FLANGE_SIDE_1_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
                PRO_WALL_LEN_TYPE_BLIND);
        real(node(depth, PRO_E_SMT_FLANGE_SIDE_1_DEPTH), PRO_E_SMT_FLANGE_DEPTH_OFFSET, trim);
        integer(node(depth, PRO_E_SMT_FLANGE_SIDE_2_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
                PRO_WALL_LEN_TYPE_BLIND);
        real(node(depth, PRO_E_SMT_FLANGE_SIDE_2_DEPTH), PRO_E_SMT_FLANGE_DEPTH_OFFSET, trim);
    } else {
        integer(node(depth, PRO_E_SMT_FLANGE_SIDE_1_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
                PRO_WALL_LEN_TYPE_TO_END);
        integer(node(depth, PRO_E_SMT_FLANGE_SIDE_2_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
                PRO_WALL_LEN_TYPE_TO_END);
    }
    ProElement fillet = node(root, PRO_E_SMT_FILLETS);
    integer(fillet, PRO_E_SMT_FILLETS_USE_RAD, PRO_B_TRUE);
    integer(fillet, PRO_E_SMT_FILLETS_SIDE, PRO_BEND_RAD_INSIDE);
    real(fillet, PRO_E_SMT_FILLETS_VALUE, op["radius"]);
    integer(node(root, PRO_E_SMT_WALL_HEIGHT), PRO_E_SMT_WALL_HEIGHT_TYPE,
            PRO_SMT_WALL_HEIGHT_NONE);
    integer(root, PRO_E_SMT_WALL_THICKNESS_FLIP, PRO_B_FALSE);
    ProElement relief = node(root, PRO_E_SMT_BEND_RELIEF);
    flange_relief_side(relief, PRO_E_SMT_BEND_RELIEF_SIDE1, relief_request.side1,
                       relief_request.width, relief_request.depth);
    flange_relief_side(relief, PRO_E_SMT_BEND_RELIEF_SIDE2, relief_request.side2,
                       relief_request.width, relief_request.depth);
    // FEAT-014: the miter section is written only when requested, so a call
    // without miter_cuts keeps the pre-FEAT-014 element tree byte-for-byte.
    // KEEP_DEF_AREAS is intentionally omitted (SDK: optional).
    if (miter_request.requested) {
        ProElement miter = node(root, PRO_E_SMT_MTR_CUTS);
        integer(miter, PRO_E_SMT_MTR_CUTS_ADD, PRO_B_TRUE);
        ProElement miter_width = node(miter, PRO_E_SMT_MTR_CUTS_WIDTH);
        integer(miter_width, PRO_E_SMT_MTR_CUTS_WIDTH_TYPE, PRO_MITER_CUT_WIDTH_TYPE_BLIND);
        real(miter_width, PRO_E_SMT_MTR_CUTS_WIDTH_VAL, miter_request.width);
        ProElement miter_offset = node(miter, PRO_E_SMT_MTR_CUTS_OFFSET);
        integer(miter_offset, PRO_E_SMT_MTR_CUTS_OFFSET_TYPE, PRO_MITER_CUT_OFFSET_TYPE_BLIND);
        real(miter_offset, PRO_E_SMT_MTR_CUTS_OFFSET_VAL, miter_request.offset);
    }
    ProElement dev = node(root, PRO_E_SMT_DEV_LEN_CALCULATION);
    integer(dev, PRO_E_SMT_DEV_LEN_SOURCE, PRO_DVL_SRC_FEAT_YF_ONLY);
    real(node(dev, PRO_E_SMT_DEV_LEN_Y_FACTOR), PRO_E_SMT_DEV_LEN_Y_FACTOR_VALUE,
         op.value("y_factor", 0.5));
    ProFeature f = {};
    try {
        f = create(root);
    } catch (...) {
        // Record both element trees before the failure leaves this scope; the original
        // Toolkit error is rethrown unchanged.
        flange_tree_evidence(root, op);
        throw;
    }
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    // DEV-052 N05: round six left the third wall created but PRO_FEAT_UNREGENERATED
    // (status 6, no geometry) and only the shared health check saw it. Snapshot the
    // created feature right here so the failing record carries the forensics while
    // the feature still exists, before the health check fails the job and the
    // rollback removes it. Healthy features return without staging anything.
    flange_created_feature_evidence(op, f);
    CK(ProElementFree(&root));
    // DEV-051 T11 2026-10-30: read the relief section back out of the created feature
    // tree. A silent Creo-side reset to the part defaults would otherwise leave a plain
    // wall while the request echo still says rectangular, so divergence fails here
    // instead of passing a relief that is not in the model.
    if (relief_request.side1 || relief_request.side2 || miter_request.requested) {
        ProElement created = nullptr;
        CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &created));
        J side1, side2;
        if (relief_request.side1 || relief_request.side2) {
            ProElement relief_tree = get_path(created, J::array({PRO_E_SMT_BEND_RELIEF}));
            side1 = flange_relief_side_echo(relief_tree, PRO_E_SMT_BEND_RELIEF_SIDE1);
            side2 = flange_relief_side_echo(relief_tree, PRO_E_SMT_BEND_RELIEF_SIDE2);
        }
        J miter_echo;
        if (miter_request.requested) {
            ProElement miter_tree = get_path(created, J::array({PRO_E_SMT_MTR_CUTS}));
            miter_echo = flange_miter_echo(miter_tree);
        }
        CK(ProFeatureElemtreeFree(&f, created));
        if (relief_request.side1 || relief_request.side2) {
            flange_relief_expect("side1", side1, relief_request.side1, relief_request);
            flange_relief_expect("side2", side2, relief_request.side2, relief_request);
            log("SHEETMETAL_FLANGE_RELIEF_ELEMS side1_type=%d side1_width=%.6f "
                "side1_depth_type=%d side1_depth=%.6f side1_length_type=%d side2_type=%d "
                "side2_width=%.6f side2_depth_type=%d side2_depth=%.6f side2_length_type=%d\n",
                side1.at("type").get<int>(), side1.at("width_mm").get<double>(),
                side1.at("depth_type").get<int>(), side1.at("depth_mm").get<double>(),
                side1.at("length_type").get<int>(), side2.at("type").get<int>(),
                side2.at("width_mm").get<double>(), side2.at("depth_type").get<int>(),
                side2.at("depth_mm").get<double>(), side2.at("length_type").get<int>());
            extra["relief_element_echo"] = {{"side1", side1}, {"side2", side2}};
        }
        if (miter_request.requested) {
            flange_miter_expect(miter_echo, miter_request);
            log("SHEETMETAL_FLANGE_MITER_ELEMS add=%d width_type=%d width=%.6f "
                "offset_type=%d offset=%.6f\n",
                miter_echo.at("add").get<int>(), miter_echo.at("width_type").get<int>(),
                miter_echo.at("width_mm").get<double>(), miter_echo.at("offset_type").get<int>(),
                miter_echo.at("offset_mm").get<double>());
            miter_echo["requested"] = true;
            extra["miter_cuts"] = miter_echo;
        }
    }
    extra["section_path"] = J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER});
    if (trim_requested)
        // Request echo next to the measured geometry: the driver's trim-semantics
        // probe classifies the interpretation from the measured volume, not from
        // this echo, so a misread offset shows up as a geometry mismatch.
        extra["depth_trim"] = {{"end_trim_mm", trim},
                               {"side1_depth_type", PRO_WALL_LEN_TYPE_BLIND},
                               {"side2_depth_type", PRO_WALL_LEN_TYPE_BLIND}};
    extra["bend_side"] = sec_flip == PRO_B_TRUE ? "outward" : "inward";
    extra["sec_flip_element"] = sec_flip;
    extra["flip_input"] = op.value("flip", false);
    if (op.contains("relief") && !op.at("relief").is_null())
        extra["relief"] = flange_relief_record(op, relief_request);
    // FEAT-014: the adjacency evidence that the miter request released. It is an
    // operation extra, never a failure block: the wall was created.
    if (!adjacent_allowed.is_null())
        extra["adjacent_bend_ends_allowed"] = adjacent_allowed;
    remember(op, f, extra);
}
static void fix_component(ProAsmcomp *c) {
    ProAsmcompconstraint *list = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProAsmcompconstraint), 1, (ProArray *)&list));
    CK(ProAsmcompconstraintAlloc(&list[0]));
    CK(ProAsmcompconstraintTypeSet(list[0], PRO_ASM_FIX));
    ProError e = ProAsmcompConstraintsSet(nullptr, c, list);
    ProAsmcompconstraintArrayFree(list);
    check(e, "FixComponent");
}
static J component_aliases_for(int component_id, const J &saved_aliases) {
    J result = J::object();
    for (auto item : saved_aliases)
        if (item.value("feature_id", -1) == component_id)
            result = item.value("component_aliases", J::object());
    if (component_aliases_in_flight.count(component_id))
        result = component_aliases_in_flight.at(component_id);
    return result;
}
static ProSelection component_reference(ProAsmcomp *component, const J &reference) {
    ProMdl child;
    CK(ProAsmcompMdlGet(component, &child));
    ProMdl saved = board;
    J saved_aliases = aliases;
    ProSelection local;
    board = child;
    aliases = component_aliases_for(component->id, saved_aliases);
    try {
        local = resolve(reference);
    } catch (...) {
        board = saved;
        aliases = saved_aliases;
        throw;
    }
    board = saved;
    aliases = saved_aliases;
    ProModelitem mi;
    CK(ProSelectionModelitemGet(local, &mi));
    ProSelectionFree(&local);
    ProIdTable ids = {};
    ids[0] = component->id;
    ProAsmcomppath path;
    CK(ProAsmcomppathInit((ProSolid)board, ids, 1, &path));
    ProSelection contextual;
    CK(ProSelectionAlloc(&path, &mi, &contextual));
    return contextual;
}
// T09: the assembly side of a constraint is either the assembly's own geometry
// (no assembly_component) or a same-level sibling component named explicitly by
// label or feature id. The sibling's model is the resolution context, so a
// reference such as {kind:surface,id:...} means that component's own geometry;
// identity is never inferred from an item_id in another model.
static ProSelection assembly_reference(const J &constraint) {
    const J &reference = constraint.at("assembly_reference");
    const bool sibling =
        constraint.contains("assembly_component") && !constraint.at("assembly_component").is_null();
    ProMdl saved = board;
    J saved_aliases = aliases;
    ProFeature sibling_row = {};
    ProAsmcomp *sibling_component = nullptr;
    if (sibling) {
        sibling_row = feature(constraint.at("assembly_component"));
        ProFeattype type;
        CK(ProFeatureTypeGet(&sibling_row, &type));
        if (type != PRO_FEAT_COMPONENT)
            throw std::runtime_error("assembly_component must name a component of this assembly");
        sibling_component = (ProAsmcomp *)&sibling_row;
        ProMdl child;
        CK(ProAsmcompMdlGet(sibling_component, &child));
        board = child;
        aliases = component_aliases_for(sibling_component->id, saved_aliases);
    }
    ProSelection local;
    try {
        local = resolve(reference);
    } catch (...) {
        board = saved;
        aliases = saved_aliases;
        throw;
    }
    board = saved;
    aliases = saved_aliases;
    ProModelitem mi;
    CK(ProSelectionModelitemGet(local, &mi));
    ProSelectionFree(&local);
    ProIdTable ids = {};
    int levels = 0;
    if (sibling_component) {
        ids[0] = sibling_component->id;
        levels = 1;
    }
    ProAsmcomppath context;
    CK(ProAsmcomppathInit((ProSolid)board, ids, levels, &context));
    ProSelection result;
    CK(ProSelectionAlloc(&context, &mi, &result));
    return result;
}
static ProDatumside constraint_side(const J &spec, const char *key) {
    std::string value = spec.value(key, "yellow");
    if (value == "yellow")
        return PRO_DATUM_SIDE_YELLOW;
    if (value == "red")
        return PRO_DATUM_SIDE_RED;
    if (value == "none")
        return PRO_DATUM_SIDE_NONE;
    throw std::runtime_error(std::string(key) + " must be yellow, red or none");
}
static void component_constraints(ProAsmcomp *c, const J &constraints) {
    ProAsmcompconstraint *list = nullptr;
    CK(ProArrayAlloc((int)constraints.size(), sizeof(ProAsmcompconstraint), 1, (ProArray *)&list));
    std::map<std::string, ProAsmcompConstrType> types = {{"mate", PRO_ASM_MATE},
                                                         {"align", PRO_ASM_ALIGN},
                                                         {"mate_offset", PRO_ASM_MATE_OFF},
                                                         {"align_offset", PRO_ASM_ALIGN_OFF},
                                                         {"insert", PRO_ASM_INSERT},
                                                         {"csys", PRO_ASM_CSYS}};
    for (size_t i = 0; i < constraints.size(); i++) {
        auto spec = constraints[i];
        const std::string type = spec.value("type", "");
        auto found = types.find(type);
        if (found == types.end())
            throw std::runtime_error("Unsupported assembly constraint type: " + type);
        if (spec.contains("assembly_component") && !spec.at("assembly_component").is_null() &&
            feature_id(spec.at("assembly_component")) == c->id)
            throw std::runtime_error("A component constraint cannot reference its own component "
                                     "as the assembly side");
        CK(ProAsmcompconstraintAlloc(&list[i]));
        CK(ProAsmcompconstraintTypeSet(list[i], found->second));
        ProSelection a = assembly_reference(spec),
                     b = component_reference(c, spec["component_reference"]);
        CK(ProAsmcompconstraintAsmreferenceSet(list[i], a, constraint_side(spec, "assembly_side")));
        CK(ProAsmcompconstraintCompreferenceSet(list[i], b,
                                                constraint_side(spec, "component_side")));
        ProSelectionFree(&a);
        ProSelectionFree(&b);
        CK(ProAsmcompconstraintOffsetSet(list[i], spec.value("offset", 0.0)));
    }
    ProError e = ProAsmcompConstraintsSet(nullptr, c, list);
    ProAsmcompconstraintArrayFree(list);
    check(e, "ComponentConstraints");
}
// T09: a replay plan binds the source revision and file digest. The Python
// admission already re-read the registry and file bytes; the native executor
// re-checks the revision it actually received before loading the source so a
// plan cannot silently rebuild from a different revision.
static void verify_rebuild_binding(const J &op, const J &source) {
    if (!op.contains("rebuild_binding") || op.at("rebuild_binding").is_null())
        return;
    const J &binding = op.at("rebuild_binding");
    if (!binding.is_object())
        throw std::runtime_error("rebuild_binding must be an object");
    const std::string model_id = op.at("source_model_id").get<std::string>();
    if (binding.value("source_model_id", "") != model_id)
        throw std::runtime_error(
            "Rebuild binding names a different source model than source_model_id");
    const int bound = binding.value("source_revision", -1);
    const int current = source.value("revision", -1);
    if (bound != current)
        throw std::runtime_error("Rebuild source revision changed after planning (bound " +
                                 std::to_string(bound) + ", current " + std::to_string(current) +
                                 "); collect a new snapshot and plan again instead of rebuilding "
                                 "from a different revision");
}
// R05 (BUG-045/FEAT-012): the placement receipt names the row-vector convention
// and reports the transform the kernel actually stored — a fresh query, never a
// copy of the requested pose. An unreadable transform stays null with its raw
// query code instead of echoing the request as if it had been measured.
static J assembly_pose_receipt(ProAsmcomp *component) {
    ProMatrix position = {};
    const ProError code = component_to_assembly_transform(component, position);
    auto units = inspect_length_units((ProMdl)board);
    MillimeterScale scale = length_scale_to_mm((ProMdl)board, units);
    return {{"rotation_convention", assembly_rotation_convention()},
            {"transform", code ? J(nullptr) : matrix_json(position)},
            {"transform_source", "component_to_assembly"},
            {"transform_code", (int)code},
            {"length_unit", length_unit_json(units, scale)}};
}
static void assemble_component(const J &op) {
    ProMatrix position;
    assembly_rigid_transform(op, position);
    J source = component_sources.at(op["source_model_id"].get<std::string>());
    verify_rebuild_binding(op, source);
    ProPath file;
    path(file, wide(source["part_file"]));
    ProMdl child;
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &child));
    ProMdl owner = board;
    board = child;
    try {
        verify_saved(source["inspection"], inspection());
    } catch (...) {
        board = owner;
        throw;
    }
    board = owner;
    // Assembly backups change component origins. Isolate a revision snapshot so
    // inserting a component never moves the separately editable source model.
    ProMdlType child_type;
    CK(ProMdlTypeGet(child, &child_type));
    if (child_type == PRO_MDL_ASSEMBLY)
        throw std::runtime_error(
            "Nested assembly copying is not yet supported; insert owned part/sheetmetal models");
    // T13: this exact string is the copy's identity and the stem Creo writes on
    // Backup (c_<job16>_<n>.prt.N). It is captured before the copy call because
    // ProMdlnameCopy takes a non-const name buffer, and it is recorded so the
    // bundle looks the file up from the same source as the file name instead of
    // a name read back later.
    std::wstring token = std::filesystem::path(generic_job).filename().wstring();
    wchar_t copy_text[PRO_MDLNAME_SIZE] = {};
    swprintf_s(copy_text, L"c_%s_%u", token.substr(0, 16).c_str(),
               (unsigned)generated_identity_index());
    const std::wstring snapshot(copy_text);
    ProMdlName copy_name;
    wcscpy_s(copy_name, snapshot.c_str());
    ProMdl copy;
    CK(ProMdlnameCopy(child, copy_name, &copy));
    child = copy;
    ProAsmcomp comp;
    CK(ProAsmcompAssemble((ProAssembly)board, (ProSolid)child, position, &comp));
    component_aliases_in_flight[comp.id] = source["aliases"];
    std::string placement = op.value("placement", "fixed");
    if (placement == "fixed")
        fix_component(&comp);
    else if (placement == "constraints")
        component_constraints(&comp, op["constraints"]);
    else {
        ProAsmcompconstraint *list = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProAsmcompconstraint), 1, (ProArray *)&list));
        CK(ProAsmcompconstraintAlloc(&list[0]));
        CK(ProAsmcompconstraintTypeSet(list[0], PRO_ASM_DEF_PLACEMENT));
        ProError e = ProAsmcompConstraintsSet(nullptr, &comp, list);
        ProAsmcompconstraintArrayFree(list);
        check(e, "DefaultPlacement");
    }
    ProName name;
    wcscpy_s(name, wide(op["label"]).c_str());
    CK(ProModelitemNameSet(&comp, name));
    stage_operation_result(assembly_pose_receipt(&comp));
    remember(op, comp,
             {{"source_model_id", op["source_model_id"]},
              {"source_revision", source["revision"]},
              {"placement", placement},
              {"source_snapshot", true},
              {"snapshot_name", utf8(std::filesystem::path(snapshot))},
              {"component_aliases", source["aliases"]}});
}
static J constraint_reference(ProSelection ref) {
    if (!ref)
        return nullptr;
    ProModelitem mi;
    if (ProSelectionModelitemGet(ref, &mi))
        return nullptr;
    // BUG-070: the deprecated ProMdlNameGet left an uninitialized ProName
    // untouched and stale bytes surfaced as a garbled model name. The
    // successor fills a zeroed buffer (see worker.cpp).
    ProMdlName owner = {};
    CK(ProMdlMdlnameGet(mi.owner, owner));
    J result = {{"id", mi.id}, {"type", (int)mi.type}, {"owner", utf8(owner)}};
    ProAsmcomppath context;
    if (!ProSelectionAsmcomppathGet(ref, &context)) {
        J ids = J::array();
        for (int i = 0; i < context.table_num; i++)
            ids.push_back(context.comp_id_table[i]);
        result["component_path"] = ids;
    }
    return result;
}
static J inspect_constraints(ProAsmcomp *comp) {
    ProAsmcompconstraint *list = nullptr;
    ProError collected = ProAsmcompConstraintsWithDtmOrientGet(comp, &list);
    if (collected == PRO_TK_E_NOT_FOUND)
        return J::array();
    check(collected, "CollectComponentConstraints");
    int n = 0;
    CK(ProArraySizeGet((ProArray)list, &n));
    J result = J::array();
    for (int i = 0; i < n; i++) {
        ProAsmcompConstrType type;
        CK(ProAsmcompconstraintTypeGet(list[i], &type));
        J item = {{"type", (int)type}};
        // Keep the numeric SDK code and add the shared readable symbol; an
        // unrecognized code stays numeric with an explicit "unknown" symbol.
        const char *type_name = assembly_constraint_type_name((int)type);
        item["type_name"] = type_name ? type_name : "unknown";
        if (type == PRO_ASM_FIX || type == PRO_ASM_DEF_PLACEMENT) {
            result.push_back(item);
            continue;
        }
        double offset = 0;
        if (!ProAsmcompconstraintOffsetGet(list[i], &offset))
            item["offset"] = offset;
        ProSelection r = nullptr;
        ProDatumside side;
        if (!ProAsmcompconstraintAsmreferenceGet(list[i], &r, &side) && r) {
            item["assembly_reference"] = constraint_reference(r);
            item["assembly_side"] = (int)side;
            ProSelectionFree(&r);
        }
        r = nullptr;
        if (!ProAsmcompconstraintCompreferenceGet(list[i], &r, &side) && r) {
            item["component_reference"] = constraint_reference(r);
            item["component_side"] = (int)side;
            ProSelectionFree(&r);
        }
        result.push_back(item);
    }
    ProAsmcompconstraintArrayFree(list);
    return result;
}
static J assembly_inspection() {
    J components = J::array();
    for (auto item : gfeatures)
        if (item["type"].get<int>() == PRO_FEAT_COMPONENT) {
            ProAsmcomp comp;
            CK(ProModelitemInit(board, item["id"], PRO_FEATURE, &comp));
            ProMdl child = nullptr;
            ProError child_code = ProAsmcompMdlGet(&comp, &child);
            if (child_code || !child) {
                // FEAT-052: an unresolvable component model cannot be queried
                // for appearance; the record keeps the three-state shape with
                // the raw model query code instead of a fabricated state.
                components.push_back({{"feature_id", comp.id},
                                      {"model_name", nullptr},
                                      {"model_type", nullptr},
                                      {"missing", true},
                                      {"model_query_code", (int)child_code},
                                      {"appearance",
                                       {{"state", "query_failed"},
                                        {"rgb", nullptr},
                                        {"query_code", (int)child_code}}}});
                continue;
            }
            ProMdlType child_type;
            CK(ProMdlTypeGet(child, &child_type));
            // BUG-070: the deprecated ProMdlNameGet left an uninitialized
            // ProName untouched and stale bytes surfaced as a garbled model
            // name. The successor fills a zeroed buffer (see worker.cpp).
            ProMdlName name = {};
            ProError name_code = ProMdlMdlnameGet(child, name);
            if (name_code) {
                components.push_back({{"feature_id", comp.id},
                                      {"model_name", nullptr},
                                      {"model_type", nullptr},
                                      {"missing", true},
                                      {"model_query_code", (int)name_code},
                                      {"appearance",
                                       {{"state", "query_failed"},
                                        {"rgb", nullptr},
                                        {"query_code", (int)name_code}}}});
                continue;
            }
            ProMatrix position;
            CK(component_to_assembly_transform(&comp, position));
            ProMatrix initial;
            CK(ProAsmcompPositionGet(&comp, initial));
            J matrix = J::array();
            J initial_matrix = J::array();
            for (int i = 0; i < 4; i++) {
                matrix.push_back(
                    J::array({position[i][0], position[i][1], position[i][2], position[i][3]}));
                initial_matrix.push_back(
                    J::array({initial[i][0], initial[i][1], initial[i][2], initial[i][3]}));
            }
            ProBoolean packaged = PRO_B_FALSE, under = PRO_B_FALSE;
            ProAsmcompIsPackaged(&comp, &packaged);
            ProAsmcompIsUnderconstrained(&comp, &under);
            components.push_back(
                {{"feature_id", comp.id},
                 {"model_name", utf8(name)},
                 {"model_type", child_type == PRO_MDL_ASSEMBLY ? "assembly" : "part"},
                 {"transform", matrix},
                 {"transform_source", "component_to_assembly"},
                 {"initial_transform", initial_matrix},
                 {"packaged", packaged == PRO_B_TRUE},
                 {"underconstrained", under == PRO_B_TRUE},
                 // FEAT-052: three-state component appearance record
                 // (present / absent / query_failed) with the raw query code.
                 {"appearance", component_appearance_record(&comp, child)},
                 {"constraints", inspect_constraints(&comp)}});
        }
    return components;
}
static void modify_component(const J &op) {
    ProAsmcomp comp = feature(op["component"]);
    ProFeattype type;
    CK(ProFeatureTypeGet(&comp, &type));
    if (type != PRO_FEAT_COMPONENT)
        throw std::runtime_error("Reference is not an assembly component");
    std::string action = op["op"];
    if (action == "component_constraints")
        component_constraints(&comp, op["constraints"]);
    else if (action == "component_placement") {
        ProMatrix position;
        assembly_rigid_transform(op, position);
        CK(ProAsmcompAllConstrRemove(&comp));
        CK(ProAsmcompPositionSet(nullptr, &comp, position));
        fix_component(&comp);
        stage_operation_result(assembly_pose_receipt(&comp));
    } else {
        int *ids = nullptr;
        ProFeatureDeleteOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(int), 1, (ProArray *)&ids));
        ids[0] = comp.id;
        CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_DELETE_NO_OPTS;
        ProError e = ProFeatureWithoptionsDelete((ProSolid)board, ids, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&ids);
        ProArrayFree((ProArray *)&options);
        check(e, "RemoveComponent");
        std::vector<std::string> obsolete;
        for (auto it = aliases.begin(); it != aliases.end(); ++it)
            if (it.value()["feature_id"] == comp.id)
                obsolete.push_back(it.key());
        for (auto key : obsolete)
            aliases.erase(key);
    }
}
