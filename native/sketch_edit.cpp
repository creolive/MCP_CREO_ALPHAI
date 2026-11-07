// In-place geometry replacement; the native sketch and downstream Blend IDs survive.
// BUG-082 read-only diagnostics: bounded section-state traces per edit phase.
// Queries only; a failed query records its raw code and never masks a
// modeling error raised elsewhere.
static void trace_section_ids(ProSection section, const char *phase) {
    ProIntlist ids = nullptr;
    int count = 0;
    ProError code = ProSecdimIdsGet(section, &ids, &count);
    log("BUG082_DIMENSIONS phase=%s code=%d count=%d truncated=%d\n", phase, code, count,
        count > 128);
    if (code == PRO_TK_NO_ERROR)
        for (int i = 0; i < count && i < 128; ++i)
            log("BUG082_DIMENSION phase=%s id=%d\n", phase, ids[i]);
    if (ids)
        ProArrayFree((ProArray *)&ids);
}

static void trace_section_constraints(ProSection section, const char *phase) {
    ProIntlist ids = nullptr;
    int count = 0;
    ProError code = ProSectionConstraintsIdsGet(section, &ids, &count);
    log("BUG082_CONSTRAINTS phase=%s code=%d count=%d truncated=%d\n", phase, code, count,
        count > 128);
    if (code == PRO_TK_NO_ERROR)
        for (int i = 0; i < count && i < 128; ++i) {
            ProConstraintType type;
            ProConstraintStatus status;
            int n = 0, *entities = nullptr;
            ProSectionPointType *points = nullptr;
            if (ProSectionConstraintsGet(section, ids[i], &type, &status, &n, &entities, &points)) {
                log("BUG082_CONSTRAINT phase=%s id=%d get_failed\n", phase, ids[i]);
                continue;
            }
            log("BUG082_CONSTRAINT phase=%s id=%d type=%d status=%d refs=%d\n", phase, ids[i],
                (int)type, (int)status, n);
            for (int j = 0; j < n; ++j)
                log("BUG082_CONSTRAINT_REF phase=%s id=%d entity=%d sense=%d\n", phase, ids[i],
                    entities[j], points[j]);
            if (entities)
                ProArrayFree((ProArray *)&entities);
            if (points)
                ProArrayFree((ProArray *)&points);
        }
    if (ids)
        ProArrayFree((ProArray *)&ids);
}

static void trace_section_entities(ProSection section, const char *phase) {
    ProIntlist ids = nullptr;
    int count = 0;
    ProError code = ProSectionEntityIdsGet(section, &ids, &count);
    log("BUG082_ENTITIES phase=%s code=%d count=%d truncated=%d\n", phase, code, count,
        count > 128);
    if (code == PRO_TK_NO_ERROR)
        for (int i = 0; i < count && i < 128; ++i) {
            Pro2dEntdef *def = nullptr;
            if (ProSectionEntityGet(section, ids[i], &def)) {
                log("BUG082_ENTITY phase=%s id=%d get_failed\n", phase, ids[i]);
                continue;
            }
            log("BUG082_ENTITY phase=%s id=%d type=%d\n", phase, ids[i], (int)def->type);
        }
    if (ids)
        ProArrayFree((ProArray *)&ids);
}

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
    // FEAT-039/W01: the controlled weld regularises the request coordinates
    // before the geometry is expanded and rebuilt, exactly as on the create
    // path, so the move stays inside the requested bound.
    J weld_spec = op.at("entities");
    J weld_report = apply_endpoint_weld(op, weld_spec);
    J geometry = expanded_geometry(weld_spec), names = J::object();
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
    const bool mirrored = meta.value("section_normal_sign", 1) < 0;
    // Plain vector form of the section x axis for the lambdas below; the
    // MSVC legacy lambda processor (std:c++17) mis-registers captures whose
    // first reference sits deep inside a long branch chain (C2065), so the
    // vector is also referenced early in the entity_matches body.
    V section_x{loc[0][0], loc[0][1], loc[0][2]};
    auto project = [&](const J &p, double *xy) {
        V w = vec(meta["origin"]);
        for (int j = 0; j < 3; j++)
            w[j] += meta["u_axis"][j].get<double>() * p[0].get<double>() +
                    meta["v_axis"][j].get<double>() * p[1].get<double>();
        for (int i = 0; i < 2; i++)
            xy[i] = ((w[0] - loc[3][0]) * loc[i][0] + (w[1] - loc[3][1]) * loc[i][1] +
                     (w[2] - loc[3][2]) * loc[i][2]);
    };
    constexpr double kMatchTolerance = 1e-7;
    auto close_enough = [&](double a, double b) {
        return std::isfinite(a) && std::isfinite(b) && fabs(a - b) <= kMatchTolerance;
    };
    auto point_matches = [&](const J &p, const double *actual) {
        double expected[2];
        project(p, expected);
        return close_enough(expected[0], actual[0]) && close_enough(expected[1], actual[1]);
    };
    // FEAT-034/T02: one dir/mirror normalization shared by the match check, the
    // rebuild and the logical endpoint bookkeeping, so a swapped stored
    // representation never detaches the user's start/end names or references.
    auto arc_rep = [&](const J &e) {
        // Referenced up front for the same MSVC lambda capture reason as
        // section_x above: a first reference inside the return expression
        // leaves the capture unregistered (C2065).
        const bool use_mirrored = mirrored;
        double radius = e["radius"];
        J center = e["center"];
        double center_xy[2], angles[2];
        project(center, center_xy);
        for (int i = 0; i < 2; ++i) {
            double angle = e[i ? "end_angle" : "start_angle"].get<double>() * acos(-1.0) / 180;
            double xy[2];
            project(J::array({center[0].get<double>() + radius * cos(angle),
                              center[1].get<double>() + radius * sin(angle)}),
                    xy);
            angles[i] = atan2(xy[1] - center_xy[1], xy[0] - center_xy[0]);
        }
        return arc_representation(angles[0], angles[1], arc_direction(e), use_mirrored);
    };
    // FEAT-034/T02: record each named arc's logical endpoint swap for this edit,
    // rebuilt or not, so names, start/end references and dimensions stay on the
    // user's own endpoints. A degenerate request fails here, before any
    // mutation.
    std::map<std::string, int> named_ids;
    arc_endpoint_swapped.clear();
    arc_logical_swapped.clear();
    for (auto it = meta["entity_ids"].begin(); it != meta["entity_ids"].end(); ++it)
        named_ids[it.key()] = it.value();
    for (auto e : geometry) {
        if (e["type"] != "arc")
            continue;
        std::string arc_name = e["name"];
        bool swapped = arc_rep(e).swapped;
        arc_logical_swapped[arc_name] = swapped;
        arc_endpoint_swapped[named_ids.at(arc_name)] = swapped;
    }
    // Compares a stored section entity against a requested entity description.
    // Shared by the unchanged shortcut and the rewrite path (to skip entities
    // whose geometry already matches).
    auto entity_matches = [&](int id, const J &e) -> bool {
        constexpr double tolerance = 1e-7;
        auto close = [&](double a, double b) {
            return std::isfinite(a) && std::isfinite(b) && fabs(a - b) <= tolerance;
        };
        Pro2dEntdef *def = nullptr;
        CK(ProSectionEntityGet(section, id, &def));
        // Section-x alignment of the sketch u axis; used by the ellipse
        // branch. Computed up front because the MSVC legacy lambda processor
        // (std:c++17) drops captures whose first reference sits deep in this
        // branch chain (C2065 "undeclared identifier").
        double u_alignment = fabs(dot(vec(meta["u_axis"]), section_x));
        const std::string type = e.at("type");
        ProBoolean construction = PRO_B_FALSE;
        CK(ProSectionEntityIsConstruction(section, id, &construction));
        if (type != "centerline" && (construction == PRO_B_TRUE) != e.value("construction", false))
            return false;
        if (type == "line" || type == "centerline") {
            if (def->type != (type == "line" ? PRO_2D_LINE : PRO_2D_CENTER_LINE))
                return false;
            auto line = (Pro2dLinedef *)def;
            if (type == "line") {
                if (!point_matches(e["start"], line->end1) || !point_matches(e["end"], line->end2))
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
            if (!point_matches(e["center"], circle->center) || !close(e["radius"], circle->radius))
                return false;
        } else if (type == "arc") {
            if (def->type != PRO_2D_ARC)
                return false;
            auto arc = (Pro2dArcdef *)def;
            double radius = e["radius"];
            if (!point_matches(e["center"], arc->center) || !close(radius, arc->radius))
                return false;
            // FEAT-034/T02: compare against the stored representation the same
            // way it was built; a representation mismatch changes the logical
            // endpoints even when the curve itself coincides.
            ArcRepresentation rep = arc_rep(e);
            if (radius * fabs(remainder(rep.start_angle - arc->start_angle, 2 * acos(-1.0))) >
                    tolerance ||
                radius * fabs(remainder(rep.end_angle - arc->end_angle, 2 * acos(-1.0))) >
                    tolerance)
                return false;
        } else if (type == "ellipse") {
            if (def->type != PRO_2D_ELLIPSE)
                return false;
            auto ellipse = (Pro2dEllipsedef *)def;
            double aligned = u_alignment;
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
        return true;
    };
    auto geometry_matches = [&]() {
        for (const auto &e : geometry)
            if (!entity_matches(meta["entity_ids"].at(e.at("name").get<std::string>()), e))
                return false;
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
        // FEAT-034/T02: measure before the section handle goes away.
        J unchanged = {{"op", op["op"]},
                       {"sketch", label},
                       {"preserved_feature_id", f.id},
                       {"unchanged", true},
                       {"native_geometry_verified", true}};
        unchanged["frame"] = {{"origin", meta["origin"]},
                              {"u_axis", meta["u_axis"]},
                              {"v_axis", meta["v_axis"]},
                              {"normal", meta.value("normal", J())}};
        unchanged["arc_geometry"] =
            arc_geometry_report(section, PRO_TK_NO_ERROR, geometry, named_ids, vec(meta["origin"]),
                                vec(meta["u_axis"]), vec(meta["v_axis"]), loc, mirrored);
        // No re-solve happened for an identical payload; the fidelity report
        // stays explicitly unavailable instead of implying a fresh measurement.
        unchanged["geometry_deviation"] = skipped_geometry_deviation(
            "identical payload; no re-solve was performed (geometry verified at 1e-7 mm)");
        CK(ProFeatureElemtreeFree(&f, root));
        stage_operation_result(unchanged);
        return;
    }
    trace_section_ids(section, "before_delete");
    trace_section_constraints(section, "before_delete");
    trace_section_entities(section, "before_delete");
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
        // BUG-079: entities whose stored geometry already matches keep their
        // identity untouched; rebuilding unchanged entities perturbs the
        // solver's dimension mapping and broke feature regeneration.
        if (entity_matches(old, e))
            continue;
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
            ArcRepresentation rep = arc_rep(e);
            value.start_angle = rep.start_angle;
            value.end_angle = rep.end_angle;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&value, &replacement));
            arc_endpoint_swapped[replacement] = rep.swapped;
            arc_logical_swapped[name] = rep.swapped;
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
        if (type == "centerline") {
            // Replace retains the original entity identity so the revolve
            // axis reference survives (BUG-062).
            CK(ProSectionEntityReplace(section, old, replacement));
            Pro2dEntdef *retained = nullptr;
            CK(ProSectionEntityGet(section, old, &retained));
            meta["entity_ids"][name] = old;
        } else {
            // BUG-079: Replace on a geometry-changing entity leaves stale
            // solver/dimension state on the section and failed feature
            // regeneration; adopt the freshly added entity instead.
            CK(ProSectionEntityDelete(section, old));
            meta["entity_ids"][name] = replacement;
        }
    }
    // FEAT-034/T02 (N07 2026-10-31): the loop above replaced the entities whose
    // stored geometry changed and recorded their new section ids in
    // meta["entity_ids"]; the pre-edit snapshot in named_ids still held the
    // deleted ids, so the post-edit arc echo queried the rebuilt section with
    // PRO_TK_E_NOT_FOUND (-2) and degraded to source="unknown" while the edit
    // itself succeeded. Re-snapshot so the echo reads the rebuilt section by
    // the ids that now exist.
    named_ids.clear();
    for (auto it = meta["entity_ids"].begin(); it != meta["entity_ids"].end(); ++it)
        named_ids[it.key()] = it.value();
    trace_section_ids(section, "after_rebuild");
    trace_section_constraints(section, "after_rebuild");
    trace_section_entities(section, "after_rebuild");
    J solving_op = op;
    last_sketch_solver_info = profile_dimensioning_choice(op);
    std::string mode = profile_dimensioning(op);
    if (mode == "autodim" && op.value("dimensioning", "auto") != "coordinates") {
        // BUG-079: autodim after an in-place rebuild can under-dimension the
        // redefined section (an arc radius change dropped the position
        // dimension), leaving an orphaned sketch-feature dimension that fails
        // feature regeneration. Exact coordinate dimensions fully constrain
        // the section and remap cleanly, so prefer them for automatic edits
        // on principal planes when every entity type supports them.
        // BUG-082: an explicit "autodim" edit rides the same route.
        // ProSectionAutodim left 0-1 dimensions on the rebuilt on-axis sector; the section-level
        // regenerate tolerated it, but ProFeatureWithoptionsRedefine forces the
        // feature to re-solve from the dimension scheme and REV_SK plus the
        // downstream revolve stayed PRO_FEAT_UNREGENERATED (status 6, values
        // zeroed) while the identical creation succeeded because a new feature
        // adopts the section geometry directly. The upgrade is recorded in the
        // solver info (requested=autodim, used=coordinates), never silent.
        bool coordinate_compatible = true;
        for (auto it = names.begin(); it != names.end(); ++it) {
            std::string type = it.value();
            if (type != "line" && type != "centerline" && type != "circle" && type != "arc") {
                coordinate_compatible = false;
                break;
            }
        }
        if (coordinate_compatible) {
            bool has_origin = false;
            ProIntlist ids = nullptr;
            int n = 0;
            CK(ProSectionEntityIdsGet(section, &ids, &n));
            for (int i = 0; i < n && !has_origin; i++) {
                Pro2dEntdef *def = nullptr;
                CK(ProSectionEntityGet(section, ids[i], &def));
                has_origin = def->type == PRO_2D_COORD_SYS;
            }
            if (ids)
                ProArrayFree((ProArray *)&ids);
            if (has_origin)
                mode = "coordinates";
        }
    }
    solving_op["dimensioning"] = mode;
    if (mode != last_sketch_solver_info["used"].get<std::string>())
        last_sketch_solver_info["selection_reason"] = "edit_coordinate_upgrade";
    last_sketch_solver_info["used"] = mode;
    // FEAT-010/BUG-049: resolve the deviation policy on the final mode (the
    // autodim upgrade above may have switched this edit to coordinates) and
    // snapshot the pre-solve section so the solved geometry is measured
    // against the same named entities.
    const DeviationPolicy deviation_policy = resolve_geometry_tolerance(op, mode);
    const char *deviation_context = std::string(deviation_policy.source) == "request"
                                        ? "geometry_tolerance_mm"
                                        : "Coordinate dimensioning";
    J coordinate_plan;
    J deviation_targets;
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
        // Same naming rule as creation: dimension in native section coordinates
        // and name the input u/v components after their dominant section axis,
        // whatever angle the stored sketch frame meets the section axes at.
        double u_to_section_x = dot(vec(meta["u_axis"]), V{loc[0][0], loc[0][1], loc[0][2]});
        std::array<int, 2> axes =
            fabs(u_to_section_x) >= sqrt(0.5) ? std::array<int, 2>{0, 1} : std::array<int, 2>{1, 0};
        log("COORDINATE_AXES u_to_section_x=%.9f axes=%d,%d\n", u_to_section_x, axes[0], axes[1]);
        coordinate_plan = coordinate_dimensions(section, origin, named, axes, anchors);
        deviation_targets = coordinate_plan["targets"];
    }
    // Non-coordinates edits snapshot the rebuilt pre-solve section by name.
    if (deviation_targets.is_null())
        deviation_targets = section_target_snapshot(section, named_ids);
    meta["solver"] = solve_profile(section, solving_op);
    trace_section_ids(section, "after_solve");
    trace_section_constraints(section, "after_solve");
    meta["solver"]["requested"] = op.value("dimensioning", "auto");
    J deviation_regenerate = geometry_deviation_stage(section, deviation_targets);
    if (!coordinate_plan.is_null())
        meta["solver"]["coordinate_geometry"] =
            verify_coordinate_plan(section, coordinate_plan["targets"],
                                   coordinate_plan["origin_id"], deviation_policy.tolerance);
    CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    {
        // BUG-082: the live section pointer may be stale after a redefine, so
        // the after_redefine phase traces a fresh read-only copy of the saved
        // feature section instead of the pre-redefine handle.
        ProSection traced = nullptr;
        ProError copy_code = ProFeatureSectionCopy(&f, 0, &traced);
        log("BUG082_PHASE phase=after_redefine section_copy=%d\n", copy_code);
        if (copy_code == PRO_TK_NO_ERROR) {
            try {
                trace_section_ids(traced, "after_redefine");
                trace_section_constraints(traced, "after_redefine");
            } catch (...) {
                ProSectionFree(&traced);
                throw;
            }
            CK(ProSectionFree(&traced));
        }
    }
    // CompleteFeature stage: measure the redefined feature's saved section.
    // Coordinates edits keep the strict copy requirement; other modes record
    // an explicit unavailable stage when the copy fails.
    J deviation_feature;
    {
        ProSection saved = nullptr;
        ProError copy_code = ProFeatureSectionCopy(&f, 0, &saved);
        if (copy_code != PRO_TK_NO_ERROR) {
            if (!coordinate_plan.is_null())
                check(copy_code, "CopySketchSection");
            deviation_feature = unavailable_deviation_stage(
                "the redefined feature section could not be copied (code " +
                std::to_string((int)copy_code) + ")");
        } else {
            try {
                if (!coordinate_plan.is_null())
                    meta["solver"]["coordinate_geometry_after_creation"] = verify_coordinate_plan(
                        saved, coordinate_plan["targets"], coordinate_plan["origin_id"],
                        deviation_policy.tolerance);
                deviation_feature = geometry_deviation_stage(saved, deviation_targets);
            } catch (...) {
                ProSectionFree(&saved);
                throw;
            }
            CK(ProSectionFree(&saved));
        }
    }
    // FEAT-010/BUG-049: publish the two-stage fidelity report on the edit
    // result; an enforced policy rejects the edit before it ships.
    J geometry_deviation = geometry_deviation_report(
        deviation_regenerate, deviation_feature, deviation_policy.tolerance,
        deviation_policy.enforce, deviation_policy.source);
    // BUG-108: same top-level verdict as sketch creation, published before the
    // policy is enforced so an edit that moved as a rigid body is judged by the
    // coordinates verdict rather than by point displacement alone.
    J sketch_shifted;
    if (!coordinate_plan.is_null()) {
        const J &verification = meta["solver"].contains("coordinate_geometry_after_creation")
                                    ? meta["solver"]["coordinate_geometry_after_creation"]
                                    : meta["solver"]["coordinate_geometry"];
        sketch_shifted = sketch_shift_block(verification, deviation_policy.source);
        geometry_deviation["shift_detected"] = sketch_shifted["detected"];
        geometry_deviation["accepted_by_request"] = sketch_shifted["accepted_by_request"];
        geometry_deviation["accepted_rigid"] = sketch_shifted["accepted_rigid"];
        if (sketch_shifted["rigid"].is_boolean()) {
            geometry_deviation["rigid"] = sketch_shifted["rigid"];
            geometry_deviation["translation_mm"] = sketch_shifted["translation_mm"];
            geometry_deviation["translation_magnitude_mm"] =
                sketch_shifted["translation_magnitude_mm"];
            if (sketch_shifted["residual_mm"].is_number()) {
                geometry_deviation["shape_deviation_mm"] = sketch_shifted["residual_mm"];
                geometry_deviation["residual_mm"] = sketch_shifted["residual_mm"];
            }
        }
    } else {
        geometry_deviation["shift_detected"] = nullptr;
        geometry_deviation["accepted_by_request"] = nullptr;
        geometry_deviation["accepted_rigid"] = false;
    }
    enforce_geometry_deviation(geometry_deviation, deviation_context);
    meta["solver"]["geometry_deviation"] = geometry_deviation;
    meta["solver"]["sketch_shifted"] = sketch_shifted;
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
    if (weld_report.value("applied_pairs", 0) > 0) {
        std::map<std::string, int> weld_ids;
        for (auto item : meta["entity_ids"].items())
            weld_ids[item.key()] = item.value().get<int>();
        const double residual = endpoint_weld_residual(section, weld_ids, weld_report);
        weld_report["max_residual_mm"] = residual >= 0.0 ? J(residual) : J(nullptr);
        weld_report["applied"] = true;
    }
    J sketch_result = {{"op", op["op"]},
                       {"solver", sketch_solver_receipt(meta["solver"])},
                       {"endpoint_weld_native", weld_report},
                       {"sketch", label},
                       {"preserved_feature_id", f.id},
                       {"parameters", meta.value("airfoil", J::object())}};
    if (identical_payload)
        sketch_result["verification_probe"] = verification_probe_result;
    sketch_result["geometry_deviation"] = geometry_deviation;
    if (!sketch_shifted.is_null())
        sketch_result["sketch_shifted"] = sketch_shifted;
    sketch_result["frame"] = {{"origin", meta["origin"]},
                              {"u_axis", meta["u_axis"]},
                              {"v_axis", meta["v_axis"]},
                              {"normal", meta.value("normal", J())}};
    {
        // FEAT-034/T02: measure the rebuilt section in the user's own frame.
        ProSection saved = nullptr;
        ProError copy_code = ProFeatureSectionCopy(&f, 0, &saved);
        sketch_result["arc_geometry"] = arc_geometry_report(
            copy_code ? nullptr : saved, copy_code, geometry, named_ids, vec(meta["origin"]),
            vec(meta["u_axis"]), vec(meta["v_axis"]), loc, mirrored);
        if (!copy_code)
            CK(ProSectionFree(&saved));
    }
    stage_operation_result(sketch_result);
}
