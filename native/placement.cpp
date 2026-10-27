// Generic native groups, axis patterns, and rigid geometry placement.
#include <ProGroup.h>
#include <ProMove.h>
#include <ProFlexMove.h>
#include <ProD3Elem.h>

static std::map<int, int> top_feature_order() {
    std::map<int, int> result;
    J state = inspection();
    for (auto row : state["features"]) {
        ProFeature f = feature(row["id"]);
        ProBoolean embedded = PRO_B_FALSE;
        CK(ProFeatureIsEmbedded(&f, &embedded));
        if (embedded)
            continue;
        int number = 0;
        ProError code = ProFeatureNumberGet(&f, &number);
        if (code == PRO_TK_BAD_INPUTS)
            continue;
        check(code, "GetTopLevelFeatureOrder");
        result.emplace(number, f.id);
    }
    return result;
}

static void generic_reorder(const J &op) {
    bool before = op.contains("before");
    int anchor = feature_id(before ? op["before"] : op["after"]);
    ProFeature other = feature(anchor);
    std::set<int> unique;
    std::vector<int> values;
    for (auto item : op["features"]) {
        int id = feature_id(item);
        if (id == anchor || !unique.insert(id).second)
            throw std::runtime_error("Reorder needs distinct features and a separate anchor");
        values.push_back(id);
    }
    // SDK contract: feat_ids must form one contiguous range, and new_feat_num is
    // an insertion slot of the tree with the moved features removed.
    auto ordered = top_feature_order();
    std::map<int, int> number_of;
    for (auto &item : ordered)
        number_of.emplace(item.second, item.first);
    if (!number_of.count(anchor))
        throw std::runtime_error("Reorder anchor is not a top-level feature");
    std::vector<int> slots;
    for (int id : values) {
        if (!number_of.count(id))
            throw std::runtime_error("Reorder targets must be top-level features");
        slots.push_back(number_of[id]);
    }
    std::sort(slots.begin(), slots.end());
    for (size_t i = 1; i < slots.size(); i++)
        if (slots[i] != slots[i - 1] + 1)
            throw std::runtime_error("Reorder features must be contiguous in the model tree");
    int anchor_number = number_of[anchor];
    // ProFeatureWithoptionsReorder takes new_feat_num in ORIGINAL tree
    // numbering; the moved block lands before that slot when moving forward
    // and after it when moving backward, and the slot may not point at a
    // member of the moved set (observed PRO_TK_BAD_INPUTS otherwise).
    int first_slot = slots.front();
    int position;
    if (before)
        position = first_slot > anchor_number ? anchor_number : anchor_number - 1;
    else
        position = first_slot > anchor_number ? anchor_number + 1 : anchor_number;
    // A computed slot inside the moved range can only mean the block already
    // sits at the requested position; the SDK rejects such a call, so answer
    // the no-op reorder directly and keep the tree untouched.
    if (position >= slots.front() && position <= slots.back()) {
        log("REORDER_DIAG noop ids=%d anchor=%d anchor_number=%d slots=%s\n", (int)values.size(),
            anchor, anchor_number, J(slots).dump().c_str());
        stage_operation_result({{"op", op["op"]}, {"reordered", false}, {"unchanged", true}});
        return;
    }
    log("REORDER_DIAG ids=%d anchor=%d anchor_number=%d slots=%s position=%d top=%d\n",
        (int)values.size(), anchor, anchor_number, J(slots).dump().c_str(), position,
        (int)ordered.size());
    int *ids = nullptr;
    CK(ProArrayAlloc((int)values.size(), sizeof(int), 1, (ProArray *)&ids));
    for (size_t i = 0; i < values.size(); i++)
        ids[i] = values[i];
    ProError code =
        ProFeatureWithoptionsReorder((ProSolid)board, ids, position, PRO_REGEN_NO_FLAGS);
    ProArrayFree((ProArray *)&ids);
    check(code, "ReorderNativeFeatures");
    stage_operation_result({{"op", op["op"]}, {"reordered", true}});
}

static void generic_group(const J &op) {
    std::set<int> requested;
    J state = inspection();
    for (auto item : op["features"]) {
        int id = feature_id(item);
        if (!requested.insert(id).second)
            throw std::runtime_error("Group feature references must be distinct");
        if (op.value("include_support_planes", true) && item.is_string()) {
            std::wstring support = wide(item.get<std::string>() + "_plane");
            for (auto row : state["features"])
                if (!_wcsicmp(wide(row["name"]).c_str(), support.c_str()))
                    requested.insert(row["id"].get<int>());
        }
    }
    auto ordered = top_feature_order();
    int first = INT_MAX, last = -1;
    for (auto item : ordered)
        if (requested.count(item.second)) {
            first = std::min(first, item.first);
            last = std::max(last, item.first);
        }
    if (last < 0)
        throw std::runtime_error("No top-level features can be grouped");
    std::vector<int> members;
    for (auto item : ordered)
        if (item.first >= first && item.first <= last) {
            if (!op.value("include_between", false) && !requested.count(item.second))
                throw std::runtime_error("Group members must be contiguous; explicitly set "
                                         "include_between to include intervening features");
            members.push_back(item.second);
        }
    int *ids = nullptr;
    CK(ProArrayAlloc((int)members.size(), sizeof(int), 1, (ProArray *)&ids));
    for (size_t i = 0; i < members.size(); i++)
        ids[i] = members[i];
    ProGroup group;
    ProName name;
    wcscpy_s(name, wide(op["label"]).c_str());
    ProError code = ProLocalGroupCreate((ProSolid)board, ids, (int)members.size(), name, &group);
    ProArrayFree((ProArray *)&ids);
    check(code, "CreateNativeFeatureGroup");
    ProFeature leader = feature(group.id);
    remember(op, leader, {{"member_ids", members}});
}

static void generic_axis_pattern(const J &op) {
    ProFeature leader = feature(op["leader"]);
    ProFeattype leader_type;
    CK(ProFeatureTypeGet(&leader, &leader_type));
    bool group = leader_type == PRO_FEAT_GROUP_HEAD;
    ProSelection selected = resolve(op["axis"]);
    ProElement root = node(nullptr, PRO_E_PATTERN_ROOT);
    integer(root, PRO_E_GENPAT_TYPE, PRO_GENPAT_AXIS_DRIVEN);
    integer(root, PRO_E_GENPAT_REGEN_METHOD, PRO_PAT_GENERAL);
    ProElement settings = node(root, PRO_E_GENPAT_AXIS);
    ref(settings, PRO_E_GENPAT_AXIS_REF, selected);
    ProSelectionFree(&selected);
    double increment = op["increment_deg"];
    real(settings, PRO_E_GENPAT_AXIS1_INC, fabs(increment));
    integer(settings, PRO_E_AXIS_PAT_DIR1_FLIP, increment < 0 ? 1 : 0);
    integer(settings, PRO_E_GENPAT_DIM_FIRST_DIR_NUM_INST, op["count"]);
    real(settings, PRO_E_GENPAT_AXIS2_INC, 0);
    integer(settings, PRO_E_AXIS_PAT_DIR2_FLIP, 0);
    integer(settings, PRO_E_GENPAT_DIM_SECOND_DIR_NUM_INST, 1);
    ProPatternClass kind = group ? PRO_GROUP_PATTERN : PRO_FEAT_PATTERN;
    ProError code = ProPatternCreate(&leader, kind, root);
    ProElementFree(&root);
    check(code, "CreateNativeAxisPattern");
    ProPattern pattern;
    ProFeature head;
    CK(ProFeaturePatternGet(&leader, kind, &pattern));
    CK(ProPatternHeaderGet(&pattern, &head));
    ProName name;
    wcscpy_s(name, wide(op["label"]).c_str());
    CK(ProModelitemNameSet(&head, name));
    remember(op, head,
             {{"leader_id", leader.id}, {"count", op["count"]}, {"increment_deg", increment}});
}

static ProFeature axis_on_csys(const J &coordinate_system, int axis, const std::string &name) {
    // The legacy CSYS-axis constraint is rejected by Creo 10. Use two native
    // offset points, so the axis remains parametrically attached to the frame.
    ProElement points_root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(points_root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_POINT);
    integer(points_root, PRO_E_DPOINT_TYPE, PRO_DPOINT_TYPE_OFFSET_CSYS);
    text(points_root, PRO_E_STD_FEATURE_NAME, wide(name + "_p").c_str());
    integer(points_root, PRO_E_DPOINT_OFST_CSYS_TYPE, PRO_DTMPNT_OFFCSYS_CARTESIAN);
    integer(points_root, PRO_E_DPOINT_OFST_CSYS_WITH_DIMS, PRO_B_TRUE);
    ProSelection selected = resolve(coordinate_system);
    ref(points_root, PRO_E_DPOINT_OFST_CSYS_REF, selected);
    ProSelectionFree(&selected);
    ProElement points = node(points_root, PRO_E_DPOINT_OFST_CSYS_PNTS_ARRAY);
    for (int i = 0; i < 2; i++) {
        ProElement p = node(points, PRO_E_DPOINT_OFST_CSYS_PNT);
        text(p, PRO_E_DPOINT_OFST_CSYS_PNT_NAME, wide(name + (i ? "_d" : "_o")).c_str());
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR1_VAL, i && axis == 0 ? 1 : 0);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR2_VAL, i && axis == 1 ? 1 : 0);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR3_VAL, i && axis == 2 ? 1 : 0);
    }
    ProFeature pf = create(points_root);
    ProElementFree(&points_root);
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&pf, PRO_POINT, collect_geom_ids, nullptr, &ids));
    if (ids.size() != 2)
        throw std::runtime_error("Transform frame points are missing");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_AXIS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(name).c_str());
    ProElement constraints = node(root, PRO_E_DTMAXIS_CONSTRAINTS);
    for (auto id : ids) {
        ProElement constraint = node(constraints, PRO_E_DTMAXIS_CONSTRAINT);
        integer(constraint, PRO_E_DTMAXIS_CONSTR_TYPE, PRO_DTMAXIS_CONSTR_TYPE_THRU);
        ProSelection point = selection(id["id"], PRO_POINT);
        ref(constraint, PRO_E_DTMAXIS_CONSTR_REF, point);
        ProSelectionFree(&point);
    }
    ProFeature result = create(root);
    ProElementFree(&root);
    return result;
}

static void flex_transform_values(ProElement root, const J &translation, const J &rotation) {
    ProElement sets = node(root, PRO_E_D3ELEM_SETS), set = node(sets, PRO_E_D3ELEM_SET);
    integer(set, PRO_E_D3ELEM_LOCATION, PRO_D3_LOCATION_FIXED);
    ProElement moves = node(set, PRO_E_D3ELEM_MOVES);
    for (int i = 0; i < 6; i++) {
        int axis = i % 3;
        ProElement move = node(moves, PRO_E_D3ELEM_MOVE);
        integer(move, PRO_E_D3ELEM_MOVE_TYPE,
                i < 3 ? PRO_D3_MOVE_TYPE_XROTATE + axis : PRO_D3_MOVE_TYPE_XMOVE + axis);
        double value = i < 3 ? rotation[axis].get<double>() : translation[axis].get<double>();
        if (i < 3 && value < 0)
            value += 360;
        real(move, PRO_E_D3ELEM_MOVE_VALUE, value);
    }
}

static void generic_transform(const J &op) {
    bool body = op["references"][0]["kind"] == "body";
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    std::string backend;
    if (body) {
        backend = "flex_move";
        integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_FLEXMOVE);
        J surfaces = J::array(), state = inspection();
        std::set<int> requested;
        for (auto r : op["references"]) {
            int id = -1;
            if (r.contains("id"))
                id = r["id"];
            else {
                for (auto b : state["bodies"])
                    if (b["state"].get<int>() == PRO_BODY_STATE_ACTIVE) {
                        if (id >= 0)
                            throw std::runtime_error(
                                "Explicit body IDs are required when several active bodies exist");
                        id = b["id"];
                    }
            }
            if (id < 0 || !requested.insert(id).second)
                throw std::runtime_error("Transform needs distinct existing body IDs");
        }
        for (int id : requested) {
            int n = 0;
            for (auto face : state["surfaces"])
                if (face["body_id"].get<int>() == id) {
                    surfaces.push_back({{"kind", "surface"}, {"id", face["id"]}});
                    n++;
                }
            if (!n)
                throw std::runtime_error("Selected body has no active solid surfaces");
        }
        surface_collection(
            node(node(root, PRO_E_FLEXMOVE_MOVED_GEOMETRY), PRO_E_STD_SURF_COLLECTION_APPL),
            surfaces);
        integer(root, PRO_E_FLEXMOVE_DEFINE_METHOD, PRO_FLEXMOVE_DEF_METHOD_3D_DRAG);
        flex_transform_values(root, op["translation"], op["rotation"]);
        ProElement set = get(root, {PRO_E_D3ELEM_SETS, PRO_E_D3ELEM_SET});
        ProSelection csys = resolve(op["coordinate_system"]);
        ref(set, PRO_E_D3ELEM_PLACEMENT_REFERENCE, csys);
        ref(set, PRO_E_D3ELEM_ORIENTATION_REFERENCE, csys);
        ProSelectionFree(&csys);
        // Attached geometry modifies the solid. Detached FlexMove merely creates a quilt.
        ProElement options = node(root, PRO_E_FLEX_OPTS_CMPND);
        integer(options, PRO_E_FLEX_ATTACH_GEOM, PRO_FLEXMODEL_OPT_YES);
        integer(options, PRO_E_FLEX_TRF_SEL_ATT_GEOM, PRO_FLEXMODEL_OPT_YES);
        integer(options, PRO_E_FLEX_CR_RND_GEOM, PRO_FLEXMODEL_OPT_NO);
        integer(options, PRO_E_FLEX_KEEP_ORIG_GEOM,
                op.value("keep_original", false) ? PRO_FLEXMODEL_OPT_YES : PRO_FLEXMODEL_OPT_NO);
        integer(options, PRO_E_FLEX_PROPAGATE_TANGENCY, PRO_FLEXMODEL_OPT_NO);
        integer(options, PRO_E_FLEX_DFLT_CONDITIONS, PRO_FLEXMODEL_OPT_YES);
        integer(options, PRO_E_FLEX_MAINTAIN_TOPO, PRO_FLEXMODEL_OPT_YES);
    } else {
        backend = "geometry_move";
        integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_SRF_MDL);
        integer(root, PRO_E_SRF_TRANS_TYPE, PRO_SURF_TRANS_TYPE_MOVE);
        set_refs(node(root, PRO_E_SRF_TR_SURF_SELECTION), op["references"]);
        integer(root, PRO_E_MOVE_WITH_COPY,
                op.value("keep_original", false) ? PRO_MOVE_KEEP_ORIGINAL : PRO_MOVE_HIDE_ORIGINAL);
        ProFeature axes[3];
        for (int i = 0; i < 3; i++)
            axes[i] = axis_on_csys(op["coordinate_system"], i,
                                   op["label"].get<std::string>().substr(0, 19) + "_axis_" +
                                       std::to_string(i));
        ProElement moves = node(root, PRO_E_MOVE_GEOM_TRF_ARR);
        for (int i = 0; i < 6; i++) {
            int axis = i % 3;
            ProElement move = node(moves, PRO_E_MOVE_GEOM_TRF);
            integer(move, PRO_E_SRF_TR_MOVE_TYPE, i < 3 ? PRO_MOVE_TYPE_ROT : PRO_MOVE_TYPE_TRANS);
            ProElement direction = node(move, PRO_E_DIRECTION_COMPOUND);
            J ids = J::array();
            CK(ProFeatureGeomitemVisit(&axes[axis], PRO_AXIS, collect_geom_ids, nullptr, &ids));
            if (ids.size() != 1)
                throw std::runtime_error("Transform support axis is missing");
            ProSelection selected = selection(ids[0]["id"], PRO_AXIS);
            ref(direction, PRO_E_DIRECTION_REFERENCE, selected);
            ProSelectionFree(&selected);
            integer(direction, PRO_E_DIRECTION_FLIP, PRO_DIRECTION_FLIP_ALONG);
            real(move, PRO_E_SRF_TR_VAL_ELEM,
                 i < 3 ? op["rotation"][axis].get<double>()
                       : op["translation"][axis].get<double>());
        }
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f,
             {{"backend", backend},
              {"translation", op["translation"]},
              {"rotation", op["rotation"]},
              {"coordinate_system", op["coordinate_system"]},
              {"references", op["references"]},
              {"keep_original", op["keep_original"]}});
}

static ProElement indexed_element(ProElement root,
                                  std::initializer_list<std::pair<int, int>> items) {
    std::vector<ProElempathItem> path_items;
    for (auto pair : items) {
        ProElempathItem item = {};
        item.type = pair.first < 0 ? PRO_ELEM_PATH_ITEM_TYPE_INDEX : PRO_ELEM_PATH_ITEM_TYPE_ID;
        if (pair.first < 0)
            item.path_item.elem_index = pair.second;
        else
            item.path_item.elem_id = (ProElemId)pair.first;
        path_items.push_back(item);
    }
    ProElempath path = nullptr;
    CK(ProElempathAlloc(&path));
    CK(ProElempathDataSet(path, path_items.data(), (int)path_items.size()));
    ProElement result;
    CK(ProElemtreeElementGet(root, path, &result));
    ProElempathFree(&path);
    return result;
}

static void generic_transform_update(const J &op) {
    std::string label = op["feature"];
    if (!aliases.contains(label) || aliases[label].value("op", "") != "geometry_transform")
        throw std::runtime_error("Feature is not an MCP geometry transformation");
    J &meta = aliases[label];
    bool flex = meta["backend"] == "flex_move";
    ProFeature f = feature(label);
    int id = f.id;
    ProElement root = nullptr;
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    for (int i = 0; i < 6; i++) {
        int axis = i % 3;
        ProElement value =
            flex ? indexed_element(root, {{PRO_E_D3ELEM_SETS, 0},
                                          {-1, 0},
                                          {PRO_E_D3ELEM_MOVES, 0},
                                          {-1, i},
                                          {PRO_E_D3ELEM_MOVE_VALUE, 0}})
                 : indexed_element(
                       root, {{PRO_E_MOVE_GEOM_TRF_ARR, 0}, {-1, i}, {PRO_E_SRF_TR_VAL_ELEM, 0}});
        double number =
            i < 3 ? op["rotation"][axis].get<double>() : op["translation"][axis].get<double>();
        if (flex && i < 3 && number < 0)
            number += 360;
        CK(ProElementDoubleSet(value, number));
    }
    redefine(&f, root);
    ProFeatureElemtreeFree(&f, root);
    if (f.id != id)
        throw std::runtime_error("Native transform ID changed");
    meta["translation"] = op["translation"];
    meta["rotation"] = op["rotation"];
}
