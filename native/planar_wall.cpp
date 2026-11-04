// FEAT-058: native rectangular unattached planar wall and its in-place resize.
// See native/planar_wall.h for the measured basis and the tree rationale.

// The primary wall is a sheetmetal feature: CREO refuses it (or creates a
// feature that cannot regenerate) outside a sheetmetal part, so the subtype is
// checked before anything is written to the model.
static bool planar_wall_part_is_sheetmetal(ProError *code = nullptr) {
    ProMdlsubtype subtype = PROMDLSTYPE_PART_SOLID;
    ProError query = ProMdlSubtypeGet(board, &subtype);
    if (code)
        *code = query;
    return query == PRO_TK_NO_ERROR && subtype == PROMDLSTYPE_PART_SHEETMETAL;
}

static void planar_wall_require_empty_sheetmetal(const char *op) {
    ProError code = PRO_TK_NO_ERROR;
    if (!planar_wall_part_is_sheetmetal(&code))
        throw std::runtime_error(
            std::string(op) +
            " needs a sheetmetal part: the native unattached planar wall only regenerates in "
            "one (ProMdlSubtypeGet=" +
            std::to_string((int)code) + "); create the model from the sheetmetal template");
    J state = inspection();
    if (state["has_solid"].get<bool>())
        throw std::runtime_error(std::string(op) +
                                 " creates the first wall; this model already has geometry");
}

// ProFlatSrf.h Table 4 and the wall-feature help: PRO_E_STD_SMT_THICKNESS is
// refused once the part owns the sheetmetal thickness parameter. Drive the
// parameter first and let the element be written only when it does not exist.
static bool planar_wall_drive_thickness(double thickness) {
    ProModelitem owner;
    if (ProMdlToModelitem(board, &owner) != PRO_TK_NO_ERROR)
        return false;
    ProName name;
    wcscpy_s(name, L"SMT_THICKNESS");
    ProParameter parameter;
    if (ProParameterInit(&owner, name, &parameter) != PRO_TK_NO_ERROR)
        return false;
    ProParamvalue value = {};
    value.type = PRO_PARAM_DOUBLE;
    value.value.d_val = thickness;
    ProError code = ProParameterValueWithUnitsSet(&parameter, &value, nullptr);
    log("PLANAR_WALL_THICKNESS source=parameter code=%d mm=%.9f\n", (int)code, thickness);
    if (code != PRO_TK_NO_ERROR)
        throw std::runtime_error("Setting the sheetmetal thickness parameter failed with code " +
                                 std::to_string((int)code));
    return true;
}

// Signed extents of the wall's box along the sketch frame. The envelope is the
// only shape evidence that separates length from width on a rotated frame, so
// it is measured per axis and never sorted into a world bounding box.
static J planar_wall_envelope(const J &bounds, const V &origin, const V &u, const V &v,
                              const V &n) {
    V low = vec(bounds[0]), high = vec(bounds[1]);
    auto extent = [&](const V &axis) {
        double lo = 0, hi = 0;
        bool first = true;
        for (int corner = 0; corner < 8; corner++) {
            V point = {corner & 1 ? high[0] : low[0], corner & 2 ? high[1] : low[1],
                       corner & 4 ? high[2] : low[2]};
            V offset = {point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]};
            double value = dot(offset, axis);
            if (first || value < lo)
                lo = value;
            if (first || value > hi)
                hi = value;
            first = false;
        }
        return J{{"min", lo}, {"max", hi}};
    };
    return J{{"u", extent(u)}, {"v", extent(v)}, {"n", extent(n)}};
}

// Union of the boxes of the bodies that carry material: the sheetmetal
// template may keep an empty body next to the new wall body.
static J planar_wall_material_bounds(const J &state) {
    bool found = false;
    V low = {0, 0, 0}, high = {0, 0, 0};
    for (const auto &body : state["bodies"]) {
        if (!body.contains("bbox") || !body["bbox"].is_array())
            continue;
        V a = vec(body["bbox"][0]), b = vec(body["bbox"][1]);
        for (int axis = 0; axis < 3; axis++) {
            low[axis] = found ? std::min(low[axis], a[axis]) : a[axis];
            high[axis] = found ? std::max(high[axis], b[axis]) : b[axis];
        }
        found = true;
    }
    if (!found)
        throw std::runtime_error("The wall was created but no body carries geometry");
    return J::array({J::array({low[0], low[1], low[2]}), J::array({high[0], high[1], high[2]})});
}

static int planar_wall_sheetmetal_bodies() {
    ProSolidBody *bodies = nullptr;
    CK(ProSolidBodiesCollect((ProSolid)board, &bodies));
    int count = 0, sheetmetal = 0;
    CK(ProArraySizeGet((ProArray)bodies, &count));
    for (int i = 0; i < count; i++) {
        ProBoolean smt = PRO_B_FALSE;
        if (ProSolidBodyIsSheetmetal(&bodies[i], &smt) == PRO_TK_NO_ERROR && smt)
            sheetmetal++;
    }
    ProArrayFree((ProArray *)&bodies);
    return sheetmetal;
}

// Count the point dimensions the driving sketch actually carries. A rectangle
// solved with fewer than four leaves the section free to move, which must never
// look like a verified wall (FEAT-058 square case).
static int planar_wall_dimension_count(const std::string &sketch_name) {
    const J *meta = alias_entry(sketch_name);
    if (!meta || !meta->contains("dimension_ids") || !(*meta)["dimension_ids"].is_object())
        return 0;
    int count = 0;
    for (auto it = (*meta)["dimension_ids"].begin(); it != (*meta)["dimension_ids"].end(); ++it) {
        const std::string &name = it.key();
        if (name.rfind("coord_origin_", 0) == 0)
            continue;
        if (name.size() > 2 && (name.compare(name.size() - 2, 2, "_x") == 0 ||
                                name.compare(name.size() - 2, 2, "_y") == 0))
            count++;
    }
    return count;
}

static double planar_wall_measured_volume(const J &state) {
    if (!state["volume_mm3"].is_number())
        throw std::runtime_error(
            "The wall exists but the solid volume could not be measured (volume_query_code=" +
            (state["volume_query_code"].is_number()
                 ? std::to_string(state["volume_query_code"].get<int>())
                 : std::string("null")) +
            ")");
    return state["volume_mm3"].get<double>();
}

static void planar_wall_require_volume(double measured, double length, double width,
                                       double thickness, const char *phase) {
    double expected = length * width * thickness;
    double tolerance = std::max(0.01, fabs(expected) * PLANAR_WALL_VOLUME_TOLERANCE);
    log("PLANAR_WALL_VOLUME phase=%s measured_mm3=%.9f expected_mm3=%.9f tolerance=%.9f\n", phase,
        measured, expected, tolerance);
    if (fabs(measured - expected) > tolerance)
        throw std::runtime_error(std::string("The ") + phase + " wall volume " +
                                 std::to_string(measured) + " mm3 does not match length*width*" +
                                 "thickness = " + std::to_string(expected) + " mm3");
}

static void generic_sheetmetal_planar_wall(const J &op) {
    planar_wall_require_empty_sheetmetal("sheetmetal_planar_wall");
    std::string label = op["label"].get<std::string>();
    double length = op["length"].get<double>();
    double width = op["width"].get<double>();
    double thickness = op["thickness"].get<double>();
    bool negative = op.value("direction", "positive") == "negative";

    // 1) The driving sketch: one rectangle covering 0..length by 0..width, fully
    //    dimensioned by coordinates so a later resize can drive its dimensions.
    std::string sketch_name = label + "_sk";
    J sketch_op = {{"op", "sketch"},
                   {"label", sketch_name},
                   {"plane", op["plane"]},
                   {"entities", J::array({J{{"type", "rectangle"},
                                            {"name", "wall"},
                                            {"min", J::array({0.0, 0.0})},
                                            {"max", J::array({length, width})}}})},
                   {"dimensioning", "coordinates"}};
    J sketch_details = sketch(sketch_op);
    ProFeature sketch_feature = feature(sketch_name);
    V origin = vec(sketch_details["origin"]), u = vec(sketch_details["u_axis"]),
      v = vec(sketch_details["v_axis"]), n = vec(sketch_details["normal"]);

    // 2) The wall itself: the Fill tree with the sheetmetal branch.
    bool thickness_from_parameter = planar_wall_drive_thickness(thickness);
    ProSelection reference = selection(sketch_feature.id, PRO_FEATURE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_FLAT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(label).c_str());
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, reference);
    ProSelectionFree(&reference);
    integer(root, PRO_E_IS_UNATTACHED_WALL, PRO_B_TRUE);
    integer(root, PRO_E_STD_DIRECTION, negative ? -1 : 1);
    integer(root, PRO_E_STD_SMT_SWAP_DRV_SIDE, PRO_B_FALSE);
    integer(node(root, PRO_E_BODY), PRO_E_BODY_USE, PRO_BODY_USE_NEW);
    // PRO_E_SMT_NEW_BODY_LINKED is documented as PRO_B_TRUE with a new body while
    // ProExtrude.h types the element as an option; report the write code instead
    // of hiding a disagreement behind a blanket cast.
    ProError linked = ProElementIntegerSet(node(root, PRO_E_SMT_NEW_BODY_LINKED), PRO_B_TRUE);
    log("PLANAR_WALL_LINKED code=%d\n", (int)linked);
    if (!thickness_from_parameter)
        real(root, PRO_E_STD_SMT_THICKNESS, thickness);
    ProFeature wall = create(root);
    CK(ProElementFree(&root));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));

    // 3) The wall is accepted only on measured evidence.
    J state = inspection();
    double measured = planar_wall_measured_volume(state);
    planar_wall_require_volume(measured, length, width, thickness, "created");
    J bounds = planar_wall_material_bounds(state);
    J envelope = planar_wall_envelope(bounds, origin, u, v, n);
    int dimensions = planar_wall_dimension_count(sketch_name);
    int sheetmetal_bodies = planar_wall_sheetmetal_bodies();
    log("PLANAR_WALL_CREATED feature_id=%d sketch=%s dimensions=%d sheetmetal_bodies=%d "
        "envelope_u=%.9f envelope_v=%.9f envelope_n=%.9f\n",
        wall.id, sketch_name.c_str(), dimensions, sheetmetal_bodies,
        envelope["u"]["max"].get<double>() - envelope["u"]["min"].get<double>(),
        envelope["v"]["max"].get<double>() - envelope["v"]["min"].get<double>(),
        envelope["n"]["max"].get<double>() - envelope["n"]["min"].get<double>());
    if (dimensions < PLANAR_WALL_MIN_DIMENSIONS)
        throw std::runtime_error("The driving sketch carries only " + std::to_string(dimensions) +
                                 " point dimensions; the rectangle would stay under-constrained");
    if (!sheetmetal_bodies)
        throw std::runtime_error(
            "The wall regenerated but no body reports the sheetmetal state; the feature is not a "
            "sheetmetal wall in this part");

    J frame = {{"origin", xyz(origin.data())},
               {"u_axis", xyz(u.data())},
               {"v_axis", xyz(v.data())},
               {"normal", xyz(n.data())}};
    remember(op, wall,
             {{"planar_wall",
               {{"sketch", sketch_name},
                {"length", length},
                {"width", width},
                {"thickness", thickness},
                {"direction", negative ? "negative" : "positive"},
                {"frame", frame}}}});
    stage_operation_result(
        {{"op", "sheetmetal_planar_wall"},
         {"feature", label},
         {"feature_id", wall.id},
         {"sketch", sketch_name},
         {"length", length},
         {"width", width},
         {"thickness", thickness},
         {"square", fabs(length - width) <= 1e-9},
         {"dimension_count", dimensions},
         {"volume_mm3", measured},
         {"frame", frame},
         {"envelope", envelope},
         {"bounds_mm", bounds},
         {"sheetmetal_body", true},
         {"sheetmetal_bodies", sheetmetal_bodies},
         {"thickness_source", thickness_from_parameter ? "parameter" : "element"}});
}

// Resize drives the existing sketch's coordinate dimensions: the wall keeps its
// feature id and its thickness, and unrelated constraints are never rebuilt.
static void generic_resize_sheetmetal_planar_wall(const J &op) {
    std::string label = op["feature"].get<std::string>();
    const J *wall_meta = alias_entry(label);
    if (!wall_meta || !wall_meta->contains("planar_wall"))
        throw std::runtime_error(
            "resize_sheetmetal_planar_wall only resizes walls created by sheetmetal_planar_wall: " +
            label);
    J record = (*wall_meta)["planar_wall"];
    std::string sketch_name = record["sketch"].get<std::string>();
    double thickness = record["thickness"].get<double>();
    J frame = record.value("frame", J::object());
    double length = op["length"].get<double>();
    double width = op["width"].get<double>();
    ProFeature wall = feature(label);

    // A downstream feature would be silently rebuilt by an in-place reshape.
    int *children = nullptr, child_count = 0;
    CK(ProFeatureChildrenGet(&wall, &children, &child_count));
    J child_ids = J::array();
    for (int i = 0; i < child_count; i++)
        child_ids.push_back(children[i]);
    if (child_count)
        ProArrayFree((ProArray *)&children);
    log("PLANAR_WALL_RESIZE feature_id=%d children=%d\n", wall.id, child_count);
    if (child_count)
        throw std::runtime_error("Feature " + label + " has downstream dependencies " +
                                 child_ids.dump() +
                                 "; the in-place resize is refused so they are not rebuilt");

    const J *sketch_meta = alias_entry(sketch_name);
    if (!sketch_meta || !sketch_meta->contains("dimension_ids"))
        throw std::runtime_error("The driving sketch " + sketch_name +
                                 " has no recorded dimensions to drive");
    J ids = (*sketch_meta)["dimension_ids"];
    ProFeature sketch_feature = feature(sketch_name);
    ProElement root = nullptr;
    CK(ProFeatureElemtreeExtract(&sketch_feature, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    J path = sketch_meta->value("section_path", J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER}));
    ProElement section_element = get_path(root, path);
    ProSection section = nullptr;
    CK(ProElementSpecialvalueGet(section_element, nullptr, (ProAppData *)&section));

    // Read every dimension before writing any, so a partially readable section
    // leaves the model untouched.
    struct Target {
        int id;
        double value;
        char axis;
    };
    std::vector<Target> reads;
    double observed_length = 0, observed_width = 0;
    for (auto it = ids.begin(); it != ids.end(); ++it) {
        const std::string &name = it.key();
        if (name.rfind("coord_origin_", 0) == 0)
            continue;
        char axis = 0;
        if (name.size() > 2 && name.compare(name.size() - 2, 2, "_x") == 0)
            axis = 'x';
        else if (name.size() > 2 && name.compare(name.size() - 2, 2, "_y") == 0)
            axis = 'y';
        else
            continue;
        double value = 0;
        CK(ProSecdimValueGet(section, it.value().get<int>(), &value));
        reads.push_back({it.value().get<int>(), fabs(value), axis});
        if (axis == 'x')
            observed_length = std::max(observed_length, fabs(value));
        else
            observed_width = std::max(observed_width, fabs(value));
    }
    if (observed_length <= 0 || observed_width <= 0)
        throw std::runtime_error("The driving sketch dimensions cannot be read (" +
                                 std::to_string(reads.size()) +
                                 " point dimensions); the wall was left unchanged");
    double factor_u = length / observed_length, factor_v = width / observed_width;
    log("PLANAR_WALL_RESIZE observed_u=%.9f observed_v=%.9f factor_u=%.9f factor_v=%.9f\n",
        observed_length, observed_width, factor_u, factor_v);

    for (const auto &target : reads)
        CK(ProSecdimValueSet(section, target.id,
                             target.value * (target.axis == 'x' ? factor_u : factor_v)));
    ProWSecerror error = nullptr;
    CK(ProSecerrorAlloc(&error));
    CK(ProSectionRegenerate(section, &error));
    ProSecerrorFree(&error);
    CK(ProElementSpecialvalueSet(section_element, (ProAppData)section));
    redefine(&sketch_feature, root);
    CK(ProFeatureElemtreeFree(&sketch_feature, root));
    mark_sketch_geometry_stale();
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));

    // The wall must still be the same feature, at the same thickness, with the
    // new extent; all three come from the model, not from the request.
    ProFeature after_wall = feature(label);
    J state = inspection();
    double measured = planar_wall_measured_volume(state);
    planar_wall_require_volume(measured, length, width, thickness, "resized");
    J bounds = planar_wall_material_bounds(state);
    J envelope = planar_wall_envelope(bounds, vec(frame["origin"]), vec(frame["u_axis"]),
                                      vec(frame["v_axis"]), vec(frame["normal"]));
    int dimensions = planar_wall_dimension_count(sketch_name);
    log("PLANAR_WALL_RESIZED feature_before=%d feature_after=%d dimensions=%d volume_mm3=%.9f\n",
        wall.id, after_wall.id, dimensions, measured);
    if (after_wall.id != wall.id)
        throw std::runtime_error("The resize changed the wall feature identity (" +
                                 std::to_string(wall.id) + " -> " + std::to_string(after_wall.id) +
                                 ")");
    if (dimensions < PLANAR_WALL_MIN_DIMENSIONS)
        throw std::runtime_error("The resize left the sketch with only " +
                                 std::to_string(dimensions) + " point dimensions");

    aliases[label]["planar_wall"]["length"] = length;
    aliases[label]["planar_wall"]["width"] = width;
    stage_operation_result({{"op", "resize_sheetmetal_planar_wall"},
                            {"feature", label},
                            {"feature_id", after_wall.id},
                            {"feature_id_before", wall.id},
                            {"sketch", sketch_name},
                            {"length", length},
                            {"width", width},
                            {"thickness", thickness},
                            {"square", fabs(length - width) <= 1e-9},
                            {"dimension_count", dimensions},
                            {"volume_mm3", measured},
                            {"frame", frame},
                            {"envelope", envelope},
                            {"bounds_mm", bounds},
                            {"sheetmetal_body", true},
                            {"thickness_source", record.value("thickness_source", "parameter")}});
}
