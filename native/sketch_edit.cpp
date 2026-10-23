// In-place geometry replacement; the native sketch and downstream Blend IDs survive.
static J expanded_geometry(const J &input) {
    J result = J::array();
    for (auto e : input) {
        std::string type = e["type"], name = e["name"];
        if (type == "rectangle" || type == "polyline") {
            J points;
            if (type == "rectangle") {
                auto a = e["min"], b = e["max"];
                points = J::array({a, J::array({b[0], a[1]}), b, J::array({a[0], b[1]})});
            } else
                points = e["points"];
            int n = (int)points.size(),
                segments = n - 1 + (type == "rectangle" || e.value("closed", false) ? 1 : 0);
            for (int i = 0; i < segments; i++)
                result.push_back({{"type", "line"},
                                  {"name", name + "_" + std::to_string(i)},
                                  {"start", points[i]},
                                  {"end", points[(i + 1) % n]},
                                  {"construction", e.value("construction", false)}});
        } else
            result.push_back(e);
    }
    return result;
}

static void generic_sketch_edit(const J &op) {
    std::string label = op.at("sketch");
    if (!aliases.contains(label))
        throw std::runtime_error("Sketch alias is missing");
    J &meta = aliases[label];
    ProFeature f = feature(label);
    int original_id = f.id;
    const std::string requested = op.value("dimensioning", "auto");
    // Older records lack the cache fields. Their solver still records the
    // requested mode, but geometry must always be checked against the native
    // section: submitted JSON alone is not proof that dimensions stayed put.
    const std::string previous =
        meta.value("last_dimensioning", meta.value("solver", J::object()).value("requested", ""));
    J geometry = expanded_geometry(op["entities"]), names = J::object();
    for (auto e : geometry)
        names[e["name"].get<std::string>()] = e["type"];
    if (names.size() != geometry.size() || names.size() != meta.at("entity_ids").size())
        throw std::runtime_error("In-place edit must retain every named sketch entity");
    for (auto it = meta["entity_ids"].begin(); it != meta["entity_ids"].end(); ++it)
        if (!names.contains(it.key()))
            throw std::runtime_error("In-place edit cannot rename sketch entities");
    ProElement root = nullptr;
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    ProElement sk =
        get_path(root, meta.value("section_path", J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER})));
    ProSection section = nullptr;
    CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&section));
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    ProMatrix loc;
    CK(ProSectionLocationGet(section, loc));
    auto project = [&](const J &p, double *xy) {
        V w = vec(meta["origin"]);
        for (int j = 0; j < 3; j++)
            w[j] += meta["u_axis"][j].get<double>() * p[0].get<double>() +
                    meta["v_axis"][j].get<double>() * p[1].get<double>();
        for (int i = 0; i < 2; i++)
            xy[i] = ((w[0] - loc[3][0]) * loc[i][0] + (w[1] - loc[3][1]) * loc[i][1] +
                     (w[2] - loc[3][2]) * loc[i][2]);
    };
    auto geometry_matches = [&]() {
        constexpr double tolerance = 1e-7;
        auto close = [&](double a, double b) {
            return std::isfinite(a) && std::isfinite(b) && fabs(a - b) <= tolerance;
        };
        auto point_matches = [&](const J &p, const double *actual) {
            double expected[2];
            project(p, expected);
            return close(expected[0], actual[0]) && close(expected[1], actual[1]);
        };
        for (const auto &e : geometry) {
            Pro2dEntdef *def = nullptr;
            int id = meta["entity_ids"].at(e.at("name").get<std::string>());
            CK(ProSectionEntityGet(section, id, &def));
            const std::string type = e.at("type");
            ProBoolean construction = PRO_B_FALSE;
            CK(ProSectionEntityIsConstruction(section, id, &construction));
            if (type != "centerline" &&
                (construction == PRO_B_TRUE) != e.value("construction", false))
                return false;
            if (type == "line" || type == "centerline") {
                if (def->type != (type == "line" ? PRO_2D_LINE : PRO_2D_CENTER_LINE))
                    return false;
                auto line = (Pro2dLinedef *)def;
                if (type == "line") {
                    if (!point_matches(e["start"], line->end1) ||
                        !point_matches(e["end"], line->end2))
                        return false;
                } else {
                    // Centerline endpoints may slide along the infinite axis.
                    double a[2], b[2];
                    project(e["start"], a);
                    project(e["end"], b);
                    double dx = b[0] - a[0], dy = b[1] - a[1], length = hypot(dx, dy);
                    if (length <= tolerance || hypot(line->end2[0] - line->end1[0],
                                                     line->end2[1] - line->end1[1]) <= tolerance)
                        return false;
                    for (const double *p : {line->end1, line->end2})
                        if (fabs(dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / length > tolerance)
                            return false;
                }
            } else if (type == "circle") {
                if (def->type != PRO_2D_CIRCLE)
                    return false;
                auto circle = (Pro2dCircledef *)def;
                if (!point_matches(e["center"], circle->center) ||
                    !close(e["radius"], circle->radius))
                    return false;
            } else if (type == "arc") {
                if (def->type != PRO_2D_ARC)
                    return false;
                auto arc = (Pro2dArcdef *)def;
                double radius = e["radius"];
                if (!point_matches(e["center"], arc->center) || !close(radius, arc->radius))
                    return false;
                double center[2], angles[2];
                project(e["center"], center);
                for (int i = 0; i < 2; ++i) {
                    double angle =
                        e[i ? "end_angle" : "start_angle"].get<double>() * acos(-1.0) / 180;
                    double xy[2];
                    project(J::array({e["center"][0].get<double>() + radius * cos(angle),
                                      e["center"][1].get<double>() + radius * sin(angle)}),
                            xy);
                    angles[i] = atan2(xy[1] - center[1], xy[0] - center[0]);
                }
                if (meta.value("section_normal_sign", 1) < 0)
                    std::swap(angles[0], angles[1]);
                if (radius * fabs(remainder(angles[0] - arc->start_angle, 2 * acos(-1.0))) >
                        tolerance ||
                    radius * fabs(remainder(angles[1] - arc->end_angle, 2 * acos(-1.0))) >
                        tolerance)
                    return false;
            } else if (type == "ellipse") {
                if (def->type != PRO_2D_ELLIPSE)
                    return false;
                auto ellipse = (Pro2dEllipsedef *)def;
                double aligned = fabs(dot(vec(meta["u_axis"]), V{loc[0][0], loc[0][1], loc[0][2]}));
                if (aligned <= 0.99999 && aligned >= 0.00001)
                    return false;
                double x = e[aligned > 0.99999 ? "x_radius" : "y_radius"];
                double y = e[aligned > 0.99999 ? "y_radius" : "x_radius"];
                if (!point_matches(e["center"], ellipse->origin) || !close(x, ellipse->x_radius) ||
                    !close(y, ellipse->y_radius))
                    return false;
            } else if (type == "spline") {
                if (def->type != PRO_2D_SPLINE)
                    return false;
                auto spline = (Pro2dSplinedef *)def;
                bool closed = e.value("closed", false);
                if (spline->tangency_type !=
                    (closed ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE))
                    return false;
                // Solved periodic sections may repeat the first point as the
                // closing control point; accept only that exact convention.
                size_t expected = e["points"].size();
                if (closed && spline->n_points == expected + 1) {
                    if (!point_matches(e["points"][0], spline->point_arr[expected]))
                        return false;
                } else if (spline->n_points != expected)
                    return false;
                for (size_t i = 0; i < expected; ++i)
                    if (!point_matches(e["points"][i], spline->point_arr[i]))
                        return false;
            } else
                return false;
        }
        return true;
    };
    // Read-only probe for identical resubmissions that missed the shortcut:
    // record the actually stored section parameters so the mismatch is
    // diagnosable without a native rebuild. Never mutates the session.
    auto verification_probe = [&]() {
        J probe = J::array();
        for (const auto &e : geometry) {
            Pro2dEntdef *def = nullptr;
            int id = meta["entity_ids"].at(e.at("name").get<std::string>());
            if (ProSectionEntityGet(section, id, &def))
                continue;
            J item = {{"name", e.at("name")},
                      {"requested_type", e.at("type")},
                      {"actual_type", def->type},
                      {"requested_id", id}};
            if (def->type == PRO_2D_SPLINE) {
                auto spline = (Pro2dSplinedef *)def;
                item["n_points"] = spline->n_points;
                item["tangency_type"] = spline->tangency_type;
                J points = J::array();
                for (unsigned i = 0; i < spline->n_points && spline->point_arr; ++i)
                    points.push_back({spline->point_arr[i][0], spline->point_arr[i][1]});
                item["stored_points"] = points;
            }
            probe.push_back(item);
        }
        return probe;
    };
    bool identical_payload = meta.value("geometry", J()) == op["entities"] && previous == requested;
    // Capture the probe before any rewrite: replacement invalidates the ids.
    J verification_probe_result = identical_payload ? verification_probe() : J::array();
    // Avoid the identical-redefine Toolkit failure only after read-only native
    // verification. This also safely refreshes legacy or invalidated caches.
    if (identical_payload && geometry_matches()) {
        meta["geometry_stale"] = false;
        meta["last_dimensioning"] = requested;
        CK(ProFeatureElemtreeFree(&f, root));
        operation_results.push_back({{"op", op["op"]},
                                     {"sketch", label},
                                     {"preserved_feature_id", f.id},
                                     {"unchanged", true},
                                     {"native_geometry_verified", true}});
        return;
    }
    ProIntlist dimensions = nullptr;
    int count = 0;
    CK(ProSecdimIdsGet(section, &dimensions, &count));
    for (int i = 0; i < count; i++)
        CK(ProSecdimDelete(section, dimensions[i]));
    if (dimensions)
        ProArrayFree((ProArray *)&dimensions);
    ProIntlist constraints = nullptr;
    CK(ProSectionConstraintsIdsGet(section, &constraints, &count));
    for (int i = 0; i < count; i++)
        CK(ProSectionConstraintDelete(section, constraints[i]));
    if (constraints)
        ProArrayFree((ProArray *)&constraints);
    for (auto e : geometry) {
        std::string name = e["name"], type = e["type"];
        int old = meta["entity_ids"][name], replacement = -1;
        Pro2dEntdef *existing = nullptr;
        CK(ProSectionEntityGet(section, old, &existing));
        Pro2dEntType original = existing->type;
        if (type == "line" || type == "centerline") {
            Pro2dLinedef value = {};
            value.type = type == "line" ? PRO_2D_LINE : PRO_2D_CENTER_LINE;
            if (original != value.type)
                throw std::runtime_error("Entity type cannot change during an in-place edit");
            project(e["start"], value.end1);
            project(e["end"], value.end2);
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
        } else if (type == "spline") {
            if (original != PRO_2D_SPLINE)
                throw std::runtime_error("Entity type cannot change during an in-place edit");
            auto p = e["points"];
            std::vector<std::array<double, 2>> xy(p.size());
            for (size_t i = 0; i < xy.size(); i++)
                project(p[i], xy[i].data());
            Pro2dSplinedef value = {};
            value.type = PRO_2D_SPLINE;
            value.n_points = (unsigned)xy.size();
            value.point_arr = (Pro2dPnt *)xy.data();
            value.tangency_type =
                e.value("closed", false) ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
        } else if (type == "circle") {
            if (original != PRO_2D_CIRCLE)
                throw std::runtime_error("Entity type cannot change during an in-place edit");
            Pro2dCircledef value = {};
            value.type = PRO_2D_CIRCLE;
            project(e["center"], value.center);
            value.radius = e["radius"].get<double>();
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
        } else if (type == "arc") {
            if (original != PRO_2D_ARC)
                throw std::runtime_error("Entity type cannot change during an in-place edit");
            Pro2dArcdef value = {};
            value.type = PRO_2D_ARC;
            project(e["center"], value.center);
            double radius = e["radius"];
            value.radius = radius;
            double xy[2], a = e["start_angle"].get<double>() * acos(-1.0) / 180,
                          b = e["end_angle"].get<double>() * acos(-1.0) / 180;
            J center = e["center"];
            project(J::array({center[0].get<double>() + radius * cos(a),
                              center[1].get<double>() + radius * sin(a)}),
                    xy);
            value.start_angle = atan2(xy[1] - value.center[1], xy[0] - value.center[0]);
            project(J::array({center[0].get<double>() + radius * cos(b),
                              center[1].get<double>() + radius * sin(b)}),
                    xy);
            value.end_angle = atan2(xy[1] - value.center[1], xy[0] - value.center[0]);
            if (meta.value("section_normal_sign", 1) < 0)
                std::swap(value.start_angle, value.end_angle);
            double turn = 2 * acos(-1.0);
            value.start_angle = fmod(value.start_angle + turn, turn);
            value.end_angle = fmod(value.end_angle + turn, turn);
            if (fabs(value.start_angle) < 1e-12)
                value.start_angle = 0;
            if (fabs(value.end_angle) < 1e-12)
                value.end_angle = 0;
            if (value.end_angle <= value.start_angle)
                value.end_angle += turn;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
        } else if (type == "ellipse") {
            if (original != PRO_2D_ELLIPSE)
                throw std::runtime_error("Entity type cannot change during an in-place edit");
            Pro2dEllipsedef value = {};
            value.type = PRO_2D_ELLIPSE;
            project(e["center"], value.origin);
            double align = fabs(dot(vec(meta["u_axis"]), V{loc[0][0], loc[0][1], loc[0][2]}));
            if (align > 0.99999) {
                value.x_radius = e["x_radius"].get<double>();
                value.y_radius = e["y_radius"].get<double>();
            } else if (align < 0.00001) {
                value.x_radius = e["y_radius"].get<double>();
                value.y_radius = e["x_radius"].get<double>();
            } else
                throw std::runtime_error("Ellipse axes must align with section axes");
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
        } else
            throw std::runtime_error("In-place geometry editor currently supports lines, "
                                     "polylines, rectangles, circles, arcs, ellipses and splines");
        CK(ProSectionEntityConstructionSet(
            section, replacement, e.value("construction", false) ? PRO_B_TRUE : PRO_B_FALSE));
        CK(ProSectionEntityReplace(section, old, replacement));
        // Replace retains the original entity identity and consumes the temporary ID.
        Pro2dEntdef *retained = nullptr;
        CK(ProSectionEntityGet(section, old, &retained));
        meta["entity_ids"][name] = old;
    }
    J solving_op = op;
    std::string mode = profile_dimensioning(op);
    double principal = 0;
    for (auto value : meta["normal"])
        principal = std::max(principal, fabs(value.get<double>()));
    if (principal < 0.99999) {
        if (op.value("dimensioning", "auto") == "coordinates")
            throw std::runtime_error("Coordinate editing requires a principal sketch plane");
        mode = "autodim";
    }
    solving_op["dimensioning"] = mode;
    J coordinate_plan;
    if (mode == "coordinates") {
        ProIntlist ids = nullptr;
        int n = 0, origin = -1;
        std::vector<int> anchors;
        CK(ProSectionEntityIdsGet(section, &ids, &n));
        for (int i = 0; i < n; i++) {
            Pro2dEntdef *def = nullptr;
            CK(ProSectionEntityGet(section, ids[i], &def));
            if (def->type == PRO_2D_COORD_SYS) {
                if (origin != -1)
                    throw std::runtime_error(
                        "Coordinate edit requires one section coordinate system");
                origin = ids[i];
            }
            ProBoolean projected = PRO_B_FALSE;
            CK(ProSectionEntityIsProjection(section, ids[i], &projected));
            if (projected == PRO_B_TRUE)
                anchors.push_back(ids[i]);
        }
        if (ids)
            ProArrayFree((ProArray *)&ids);
        if (origin < 0)
            throw std::runtime_error("Coordinate edit requires the section coordinate system");
        std::map<std::string, int> named;
        for (auto it = meta["entity_ids"].begin(); it != meta["entity_ids"].end(); ++it)
            named[it.key()] = it.value();
        double aligned = fabs(dot(vec(meta["u_axis"]), V{loc[0][0], loc[0][1], loc[0][2]}));
        if (aligned > 0.99999)
            coordinate_plan = coordinate_dimensions(section, origin, named, {0, 1}, anchors);
        else if (aligned < 0.00001)
            coordinate_plan = coordinate_dimensions(section, origin, named, {1, 0}, anchors);
        else
            throw std::runtime_error("Coordinate editing requires principal section axes");
    }
    meta["solver"] = solve_profile(section, solving_op);
    meta["solver"]["requested"] = op.value("dimensioning", "auto");
    if (!coordinate_plan.is_null())
        meta["solver"]["coordinate_geometry"] = verify_coordinate_plan(
            section, coordinate_plan["targets"], coordinate_plan["origin_id"]);
    CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    if (!coordinate_plan.is_null()) {
        ProSection saved = nullptr;
        CK(ProFeatureSectionCopy(&f, 0, &saved));
        try {
            meta["solver"]["coordinate_geometry_after_creation"] = verify_coordinate_plan(
                saved, coordinate_plan["targets"], coordinate_plan["origin_id"]);
        } catch (...) {
            ProSectionFree(&saved);
            throw;
        }
        CK(ProSectionFree(&saved));
    }
    if (f.id != original_id)
        throw std::runtime_error("Sketch ID changed during in-place edit");
    meta["geometry"] = op["entities"];
    meta["geometry_stale"] = false;
    meta["last_dimensioning"] = op.value("dimensioning", "auto");
    meta["dimension_ids"] =
        coordinate_plan.is_null() ? J::object() : coordinate_plan["dimension_ids"];
    if (op.contains("profile"))
        meta["airfoil"] = op["profile"];
    else
        meta.erase("airfoil");
    J sketch_result = {{"op", op["op"]},
                       {"sketch", label},
                       {"preserved_feature_id", f.id},
                       {"parameters", meta.value("airfoil", J::object())}};
    if (identical_payload)
        sketch_result["verification_probe"] = verification_probe_result;
    operation_results.push_back(sketch_result);
}
