#include "assembly_pose.h"
#include "constraint_names.h"

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
static void generic_draft(const J &op) {
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
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
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
static void generic_sheetmetal_wall(const J &op) {
    // Preserve the editable driving sketch, then convert its thin native extrusion.
    J state = inspection();
    if (state["has_solid"].get<bool>())
        throw std::runtime_error(
            "sheetmetal_wall creates the first wall; attach later walls with sheetmetal_flange");
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
    J face;
    double best = -1;
    for (auto surf : state["surfaces"])
        if (surf.contains("normal")) {
            V a = vec(surf["bbox"][1]), b = vec(surf["bbox"][0]),
              d = {a[0] - b[0], a[1] - b[1], a[2] - b[2]};
            std::array<double, 3> e = {fabs(d[0]), fabs(d[1]), fabs(d[2])};
            std::sort(e.begin(), e.end());
            double area = e[1] * e[2];
            if (area > best) {
                best = area;
                face = surf;
            }
        }
    if (face.is_null())
        throw std::runtime_error("Sheetmetal conversion needs a planar driving face");
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
    remember(op, f,
             {{"base_feature", base},
              {"construction", "thin_extrude_then_native_sheetmetal_conversion"}});
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
static void generic_sheetmetal_flange(const J &op) {
    ProSection section;
    CK(ProSection2DAlloc(&section));
    ProName section_name;
    wcscpy_s(section_name, wide(op["label"]).c_str());
    CK(ProSectionNameSet(section, section_name));
    double a = (90 - op["angle"].get<double>()) * acos(-1.0) / 180, h = op["height"];
    J profile = {{"profile", J::array({{{"type", "centerline"},
                                        {"name", "attachment"},
                                        {"start", J::array({-10, 0})},
                                        {"end", J::array({10, 0})}},
                                       {{"type", "line"},
                                        {"name", "wall"},
                                        {"start", J::array({0, 0})},
                                        {"end", J::array({h * cos(a), h * sin(a)})}}})},
                 {"dimensions", J::array({{{"name", "height"},
                                           {"type", "length"},
                                           {"refs", J::array({{{"entity", "wall"}}})},
                                           {"value", h},
                                           {"position", J::array({h * 0.5 + 2, h * 0.5 + 2})}}})},
                 {"constraints", J::array()}};
    J extra = populate_profile(section, profile);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_WALL);
    integer(root, PRO_E_SMT_WALL_TYPE, PRO_SMT_WALL_TYPE_FLANGE);
    integer(root, PRO_E_SMT_FLANGE_TYPE, PRO_FLANGE_WALL_TYPE_2D_SWEPT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection edge = resolve(op["edge"]);
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
    integer(root, PRO_E_SMT_FLANGE_TRAJ_CRV_NORM,
            op.value("flip", false) ? PRO_FLANGE_TRAJ_NORM_FLIP : PRO_FLANGE_TRAJ_NORM_NO_FLIP);
    ProElement sec = node(root, PRO_E_STD_SECTION);
    integer(sec, PRO_E_STD_SEC_METHOD, PRO_SEC_SKETCH);
    CK(ProElementSpecialvalueSet(node(sec, PRO_E_SKETCHER), (ProAppData)section));
    integer(root, PRO_E_SMT_WALL_SHARPS_TO_BENDS, PRO_B_TRUE);
    integer(root, PRO_E_SMT_FLANGE_SEC_FLIP, PRO_B_FALSE);
    ProElement depth = node(root, PRO_E_SMT_FLANGE_DEPTH);
    integer(node(depth, PRO_E_SMT_FLANGE_SIDE_1_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
            PRO_WALL_LEN_TYPE_TO_END);
    integer(node(depth, PRO_E_SMT_FLANGE_SIDE_2_DEPTH), PRO_E_SMT_FLANGE_DEPTH_TYPE,
            PRO_WALL_LEN_TYPE_TO_END);
    ProElement fillet = node(root, PRO_E_SMT_FILLETS);
    integer(fillet, PRO_E_SMT_FILLETS_USE_RAD, PRO_B_TRUE);
    integer(fillet, PRO_E_SMT_FILLETS_SIDE, PRO_BEND_RAD_INSIDE);
    real(fillet, PRO_E_SMT_FILLETS_VALUE, op["radius"]);
    integer(node(root, PRO_E_SMT_WALL_HEIGHT), PRO_E_SMT_WALL_HEIGHT_TYPE,
            PRO_SMT_WALL_HEIGHT_NONE);
    integer(root, PRO_E_SMT_WALL_THICKNESS_FLIP, PRO_B_FALSE);
    ProElement relief = node(root, PRO_E_SMT_BEND_RELIEF);
    for (int side : {PRO_E_SMT_BEND_RELIEF_SIDE1, PRO_E_SMT_BEND_RELIEF_SIDE2})
        integer(node(relief, side), PRO_E_BEND_RELIEF_TYPE, PRO_BEND_RLF_NONE);
    ProElement dev = node(root, PRO_E_SMT_DEV_LEN_CALCULATION);
    integer(dev, PRO_E_SMT_DEV_LEN_SOURCE, PRO_DVL_SRC_FEAT_YF_ONLY);
    real(node(dev, PRO_E_SMT_DEV_LEN_Y_FACTOR), PRO_E_SMT_DEV_LEN_Y_FACTOR_VALUE,
         op.value("y_factor", 0.5));
    ProFeature f = create(root);
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    CK(ProElementFree(&root));
    extra["section_path"] = J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER});
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
    ProMdlName copy_name;
    std::wstring token = std::filesystem::path(generic_job).filename().wstring();
    swprintf_s(copy_name, L"c_%s_%u", token.substr(0, 16).c_str(),
               (unsigned)generated_identity_index());
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
    remember(op, comp,
             {{"source_model_id", op["source_model_id"]},
              {"source_revision", source["revision"]},
              {"placement", placement},
              {"source_snapshot", true},
              {"component_aliases", source["aliases"]}});
}
static J constraint_reference(ProSelection ref) {
    if (!ref)
        return nullptr;
    ProModelitem mi;
    if (ProSelectionModelitemGet(ref, &mi))
        return nullptr;
    ProName owner;
    CK(ProMdlNameGet(mi.owner, owner));
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
            ProMdl child;
            CK(ProAsmcompMdlGet(&comp, &child));
            ProName name;
            CK(ProMdlNameGet(child, name));
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
            components.push_back({{"feature_id", comp.id},
                                  {"model_name", utf8(name)},
                                  {"transform", matrix},
                                  {"transform_source", "component_to_assembly"},
                                  {"initial_transform", initial_matrix},
                                  {"packaged", packaged == PRO_B_TRUE},
                                  {"underconstrained", under == PRO_B_TRUE},
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
