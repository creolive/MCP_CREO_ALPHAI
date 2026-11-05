#include <ProDtmCsys.h>
#include <ProDtmPnt.h>
#include <ProFlatsrf.h>
#include <ProThicken.h>
#include <ProSolidify.h>
#include <ProBooleanBodies.h>
#include <ProRib.h>
#include <ProCsys.h>
#include <ProPoint.h>

static void generic_csys(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CSYS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection s = resolve(op.value("reference", J{{"kind", "default_csys"}}));
    ref(node(node(root, PRO_E_CSYS_ORIGIN_CONSTRS), PRO_E_CSYS_ORIGIN_CONSTR),
        PRO_E_CSYS_ORIGIN_CONSTR_REF, s);
    ProSelectionFree(&s);
    integer(root, PRO_E_CSYS_OFFSET_TYPE, PRO_CSYS_OFFSET_CARTESIAN);
    integer(root, PRO_E_CSYS_ORIENT_BY_METHOD, PRO_CSYS_ORIENT_BY_SEL_CSYS_AXES);
    ProElement moves = node(root, PRO_E_CSYS_ORIENTMOVES);
    for (int step = 0; step < 6; step++) {
        int i = (step + 3) % 6;
        ProElement move = node(moves, PRO_E_CSYS_ORIENTMOVE);
        integer(move, PRO_E_CSYS_ORIENTMOVE_MOVE_TYPE, i);
        real(move, PRO_E_CSYS_ORIENTMOVE_MOVE_VAL, op[i < 3 ? "translation" : "rotation"][i % 3]);
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&f, PRO_CSYS, collect_geom_ids, nullptr, &ids));
    if (ids.size() != 1)
        throw std::runtime_error("Coordinate system geometry missing");
    ProCsys cs;
    CK(ProCsysInit((ProSolid)board, ids[0]["id"], &cs));
    ProGeomitemdata *data = nullptr;
    CK(ProCsysDataGet(cs, &data));
    auto c = data->data.p_csys_data;
    stage_operation_result({{"op", "datum_csys"},
                            {"origin", xyz(c->origin)},
                            {"x_axis", xyz(c->x_vector)},
                            {"y_axis", xyz(c->y_vector)},
                            {"z_axis", xyz(c->z_vector)}});
    ProGeomitemdataFree(&data);
}
static void generic_points(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_POINT);
    integer(root, PRO_E_DPOINT_TYPE, PRO_DPOINT_TYPE_OFFSET_CSYS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_DPOINT_OFST_CSYS_TYPE, PRO_DTMPNT_OFFCSYS_CARTESIAN);
    integer(root, PRO_E_DPOINT_OFST_CSYS_WITH_DIMS, PRO_B_TRUE);
    ProSelection s = resolve(op.value("reference", J{{"kind", "default_csys"}}));
    ref(root, PRO_E_DPOINT_OFST_CSYS_REF, s);
    ProSelectionFree(&s);
    ProElement points = node(root, PRO_E_DPOINT_OFST_CSYS_PNTS_ARRAY);
    for (auto point : op["points"]) {
        ProElement p = node(points, PRO_E_DPOINT_OFST_CSYS_PNT);
        text(p, PRO_E_DPOINT_OFST_CSYS_PNT_NAME, wide(point["name"]).c_str());
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR1_VAL, point["position"][0]);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR2_VAL, point["position"][1]);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR3_VAL, point["position"][2]);
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
static void generic_fill(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_FLAT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection s = selection(feature_id(op["sketch"]), PRO_FEATURE);
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
static void generic_surface_solid(const J &op) {
    bool thin = op["op"] == "thicken", cut = op.value("mode", "add") == "cut";
    // S06: a quilt becomes a solid only when it is closed. ProQuiltVolumeEval
    // answers for a closed quilt and returns PRO_TK_INVALID_TYPE for an open
    // one, so the closure is measured, not assumed, and an open quilt is
    // refused with that code instead of a bare feature failure.
    ProSelection s = resolve(op["reference"]);
    int target_quilt_id = -1;
    J closure = J(nullptr);
    if (!thin && !cut) {
        ProModelitem item;
        CK(ProSelectionModelitemGet(s, &item));
        target_quilt_id = item.id;
        ProQuilt target_quilt = nullptr;
        if (ProQuiltInit((ProSolid)board, target_quilt_id, &target_quilt))
            throw std::runtime_error("solidify could not open the referenced quilt (id " +
                                     std::to_string(target_quilt_id) + ")");
        MeasurementOutcome closed = quilt_closed_native(target_quilt);
        closure = {{"available", closed.available},
                   {"query_code", (int)closed.query_code},
                   {"reason", closed.reason ? J(closed.reason) : J(nullptr)}};
        if (quilt_closed_is_open(closed))
            throw std::runtime_error(
                "solidify requires a closed quilt; the referenced quilt is open "
                "(ProQuiltVolumeEval=" +
                std::to_string((int)closed.query_code) +
                (closed.reason ? std::string(", ") + closed.reason : std::string()) + ")");
    }
    // The volume is the solid's own measure, so it is read after the feature
    // exists. A model without a solid yet has no mass property, and that is
    // reported as unknown instead of zero.
    bool volume_before_known = true;
    double volume_before = 0.0;
    try {
        volume_before = volume();
    } catch (...) {
        volume_before_known = false;
    }
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, cut ? PRO_FEAT_CUT : PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    if (thin)
        integer(root, PRO_E_FEAT_FORM_ALWAYS_THIN, PRO_THIN);
    ref(root, thin ? PRO_E_STD_USEQLT_QLT : PRO_E_PATCH_QUILT, s);
    ProSelectionFree(&s);
    if (thin) {
        real(root, PRO_E_THICKNESS, op["thickness"]);
        std::string side = op["side"];
        integer(root, PRO_E_STD_USEQLT_SIDE,
                side == "symmetric"  ? PRO_THICKEN_BOTH_SIDES
                : side == "positive" ? PRO_THICKEN_SIDE_ONE
                                     : PRO_THICKEN_SIDE_TWO);
        integer(root, PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF);
    } else
        integer(root, PRO_E_PATCH_MATERIAL_SIDE,
                op["side"] == "positive" ? PRO_SOLIDIFY_SIDE_ONE : PRO_SOLIDIFY_SIDE_TWO);
    body_options(root, op);
    ProFeature f = create(root);
    ProElementFree(&root);
    J extra = {{"target_quilt_id", target_quilt_id >= 0 ? J(target_quilt_id) : J(nullptr)},
               {"closure", closure},
               {"volume_before_mm3", volume_before_known ? J(volume_before) : J(nullptr)}};
    if (!cut) {
        double volume_after = volume();
        extra["volume_after_mm3"] = volume_after;
    }
    // The operation result is what a client reads, so the measured numbers are
    // staged there as well; remember() only feeds the alias table.
    stage_operation_result(extra);
    remember(op, f, extra);
}
// FEAT-039/S07: a controlled offset of a quilt along its surface normal.
// The documented route (ProThicken.h) is a protrusion with the surface form,
// the thin form, the quilt reference, the distance, the normal offset method
// and one explicit side. The offset distance is measured back from the
// result instead of being echoed from the request.
static void generic_surface_offset(const J &op) {
    ProSelection s = resolve(op["reference"]);
    int quilt_id = -1;
    ProModelitem item;
    CK(ProSelectionModelitemGet(s, &item));
    quilt_id = item.id;
    double source_area = 0.0;
    bool area_known = false;
    {
        ProQuilt quilt = nullptr;
        if (!ProQuiltInit((ProSolid)board, quilt_id, &quilt); quilt) {
            MeasurementOutcome area = quilt_area_native(quilt);
            if (area.available) {
                source_area = area.value;
                area_known = true;
            }
        }
    }
    double volume_before = 0.0;
    bool volume_before_known = true;
    try {
        volume_before = volume();
    } catch (...) {
        volume_before_known = false;
    }
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_FEAT_FORM_ALWAYS_THIN, PRO_THIN);
    ref(root, PRO_E_STD_USEQLT_QLT, s);
    ProSelectionFree(&s);
    real(root, PRO_E_THICKNESS, op["distance"]);
    integer(root, PRO_E_STD_USEQLT_SIDE,
            op["side"] == "negative" ? PRO_THICKEN_SIDE_TWO : PRO_THICKEN_SIDE_ONE);
    integer(root, PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF);
    body_options(root, op);
    ProFeature f = create(root);
    ProElementFree(&root);
    double volume_after = volume();
    const double measured = area_known;
    source_area > 0.0 ? volume_after / source_area : -1.0;
    J extra = {{"target_quilt_id", quilt_id},
               {"source_area_mm2", area_known ? J(source_area) : J(nullptr)},
               {"offset_distance_mm", op["distance"]},
               {"measured_offset_distance_mm", measured >= 0.0 ? J(measured) : J(nullptr)},
               {"direction", op["side"]},
               {"offset_method", "normal_to_surface"},
               {"volume_before_mm3", volume_before_known ? J(volume_before) : J(nullptr)},
               {"volume_after_mm3", volume_after}};
    stage_operation_result(extra);
    remember(op, f, extra);
}
static void generic_boolean(const J &op) {
    std::string method = op["method"];
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_BOOLEANBODIES);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_BOOLEAN_TYPE,
            method == "union"       ? PRO_MERGE_BOOL_TYPE
            : method == "intersect" ? PRO_INTERSECT_BOOL_TYPE
                                    : PRO_SUBTRACT_BOOL_TYPE);
    auto set_bodies = [&](int id, const J &bodies) {
        if (bodies.size() == 1) {
            ProSelection s = resolve(bodies[0]);
            ref(root, id, s);
            ProSelectionFree(&s);
        } else
            set_refs(node(root, id), bodies);
    };
    set_bodies(PRO_E_TARGET_BODY, op["targets"]);
    set_bodies(PRO_E_TOOL_BODIES, op["tools"]);
    if (method == "subtract")
        integer(root, PRO_E_KEEP_TOOLS,
                op.value("keep_tools", false) ? PRO_KEEP_TOOL_YES : PRO_KEEP_TOOL_NO);
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
static void generic_rib(const J &op) {
    J state = inspection();
    if (!state["has_solid"].get<bool>())
        throw std::runtime_error(
            "Rib requires an existing solid body and an intersecting open profile");
    int sketch_id = feature_id(op["sketch"]);
    for (const auto &meta : aliases) {
        if (meta.value("feature_id", -1) != sketch_id || !meta.contains("geometry"))
            continue;
        for (const auto &entity : meta["geometry"]) {
            if (entity.value("construction", false) || entity.value("type", "") == "centerline")
                continue;
            std::string kind = entity.value("type", "");
            if (kind == "circle" || kind == "ellipse" || kind == "rectangle" ||
                ((kind == "polyline" || kind == "spline") && entity.value("closed", false)))
                throw std::runtime_error(
                    "Rib requires an open profile; closed sketch contours are not accepted");
        }
    }
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_RIB);
    integer(root, PRO_E_FEATURE_FORM, PRO_EXTRUDE);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    body_options(root, op);
    ProElement section = node(root, PRO_E_RIB_SECTION_COMP);
    ProSelection s = selection(feature_id(op["sketch"]), PRO_FEATURE);
    ref(node(section, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    // ProRib.h: material side is ignored until the standard section is fully
    // defined. Apply the requested side to the extracted native section below.
    real(root, PRO_E_RIB_THICKNESS, op["thickness"]);
    std::string side = op["side"];
    integer(root, PRO_E_RIB_SIDE_OPTS,
            side == "symmetric"  ? PRO_RIB_SYMMETRIC
            : side == "positive" ? PRO_RIB_SIDE_ONE
                                 : PRO_RIB_SIDE_TWO);
    ProFeature f = create(root, PRO_FEAT_CR_INCOMPLETE_FEAT);
    ProElementFree(&root);
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    CK(ProElementIntegerSet(get(root, {PRO_E_RIB_SECTION_COMP, PRO_E_STD_MATRLSIDE}),
                            op.value("flip", false) ? PRO_RIB_SEC_SIDE_TWO : PRO_RIB_SEC_SIDE_ONE));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    ProFeatStatus status;
    CK(ProFeatureStatusGet(&f, &status));
    if (status != PRO_FEAT_ACTIVE)
        throw std::runtime_error("Rib regeneration failed on the requested material side; check "
                                 "profile/body intersection, flip and thickness side");
    remember(op, f);
}
