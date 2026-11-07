// Complete coordinate dimensions for exact, fully supplied profile geometry.
// Accepted native profiles include large polygons, axis-aligned/rotated arcs and circles.
static J profile_dimensioning_choice(const J &op) {
    std::string requested = op.value("dimensioning", "auto");
    auto choice = [&](const std::string &used, const char *reason) -> J {
        return {{"requested", requested}, {"used", used}, {"selection_reason", reason}};
    };
    if (requested != "auto")
        return choice(requested, "explicit");
    if (!op.value("dimensions", J::array()).empty() || !op.value("constraints", J::array()).empty())
        return choice("autodim", "supplied_dimensions_or_constraints");
    double extent = 0;
    int count = 0;
    for (auto e : op.at("entities")) {
        std::string type = e.at("type");
        if (type != "line" && type != "centerline" && type != "rectangle" && type != "polyline" &&
            type != "circle" && type != "arc")
            return choice("autodim", "unsupported_coordinate_entity");
        count += type == "rectangle" ? 4
                 : type == "polyline"
                     ? (int)e["points"].size() - 1 + (e.value("closed", false) ? 1 : 0)
                     : 1;
        for (auto key : {"start", "end", "min", "max", "center"})
            if (e.contains(key))
                for (auto value : e[key])
                    extent = std::max(extent, fabs(value.get<double>()));
        if (e.contains("points"))
            for (auto point : e["points"])
                for (auto value : point)
                    extent = std::max(extent, fabs(value.get<double>()));
        if (e.contains("radius"))
            extent = std::max(extent, e["radius"].get<double>());
    }
    if (count >= 10)
        return choice("coordinates", "entity_count");
    if (extent > 1000)
        return choice("coordinates", "extent");
    return choice("autodim", "small_profile");
}
static std::string profile_dimensioning(const J &op) {
    return profile_dimensioning_choice(op).at("used").get<std::string>();
}
// BUG-108: the coordinate-system entity carries no position constraint of its
// own, so a solve may translate it, and the whole profile with it. Pin it
// against the projected reference lines when both section axes are covered; a
// partial or unavailable frame is reported and the previous behaviour is kept.
static void pin_coordinate_origin(ProSection section, int origin, const std::vector<int> &anchors,
                                  J &dimensions) {
    Pro2dEntdef *entity = nullptr;
    if (ProSectionEntityGet(section, origin, &entity) != PRO_TK_NO_ERROR || !entity) {
        log("SKETCH_ORIGIN_PIN_UNAVAILABLE reason=origin_not_readable\n");
        return;
    }
    auto cs = (Pro2dCoordSysdef *)entity;
    struct Candidate {
        int axis;
        int anchor;
        double value;
    };
    std::vector<Candidate> candidates;
    bool covered[2] = {false, false};
    for (int anchor : anchors) {
        if (covered[0] && covered[1])
            break;
        Pro2dEntdef *def = nullptr;
        if (ProSectionEntityGet(section, anchor, &def) != PRO_TK_NO_ERROR || !def)
            continue;
        if (def->type != PRO_2D_LINE && def->type != PRO_2D_CENTER_LINE)
            continue;
        auto line = (Pro2dLinedef *)def;
        for (int axis = 0; axis < 2; axis++) {
            // Only an axis-aligned projection defines one section axis; an
            // oblique reference cannot pin anything without a second dimension.
            if (covered[axis] || fabs(line->end1[axis] - line->end2[axis]) > 1e-8)
                continue;
            candidates.push_back({axis, anchor, fabs(cs->pnt[axis] - line->end1[axis])});
            covered[axis] = true;
        }
    }
    if (candidates.size() < 2) {
        log("SKETCH_ORIGIN_PIN_UNAVAILABLE u=%d v=%d anchors=%d\n", (int)covered[0],
            (int)covered[1], (int)anchors.size());
        return;
    }
    for (auto &candidate : candidates) {
        ProSectionPointType senses[] = {PRO_ENT_WHOLE, PRO_ENT_CENTER};
        int ids[] = {candidate.anchor, origin};
        Pro2dPnt place = {cs->pnt[0], cs->pnt[1]};
        int dim;
        ProError code =
            ProSecdimCreate(section, ids, senses, 2, PRO_TK_DIM_LINE_POINT, place, &dim);
        if (code == PRO_TK_NO_ERROR)
            code = ProSecdimValueSet(section, dim, candidate.value);
        if (code != PRO_TK_NO_ERROR) {
            log("SKETCH_ORIGIN_PIN_FAILED axis=%d code=%d\n", candidate.axis, (int)code);
            continue;
        }
        dimensions[candidate.axis ? "coord_origin_v" : "coord_origin_u"] = dim;
        log("SKETCH_ORIGIN_PIN axis=%d value=%.12f\n", candidate.axis, candidate.value);
    }
}
static J coordinate_dimensions(ProSection section, int origin,
                               const std::map<std::string, int> &entities,
                               const std::array<int, 2> &axes, const std::vector<int> &anchors) {
    CK(ProSectionEpsilonSet(section, 0.000000001));
    J dimensions = J::object(), snapshot = J::array();
    for (auto item : entities) {
        Pro2dEntdef *def = nullptr;
        CK(ProSectionEntityGet(section, item.second, &def));
        J row = {{"name", item.first}, {"id", item.second}, {"type", (int)def->type}};
        if (def->type == PRO_2D_LINE || def->type == PRO_2D_CENTER_LINE) {
            auto line = (Pro2dLinedef *)def;
            row["points"] = {
                {{"sense", PRO_ENT_START},
                 {"key", "start"},
                 {"xy", {line->end1[0], line->end1[1]}}},
                {{"sense", PRO_ENT_END}, {"key", "end"}, {"xy", {line->end2[0], line->end2[1]}}}};
        } else if (def->type == PRO_2D_CIRCLE) {
            auto circle = (Pro2dCircledef *)def;
            row["points"] = {{{"sense", PRO_ENT_CENTER},
                              {"key", "center"},
                              {"xy", {circle->center[0], circle->center[1]}}}};
            row["radius"] = circle->radius;
        } else if (def->type == PRO_2D_ARC) {
            auto arc = (Pro2dArcdef *)def;
            row["points"] = {{{"sense", PRO_ENT_CENTER},
                              {"key", "center"},
                              {"xy", {arc->center[0], arc->center[1]}}}};
            row["radius"] = arc->radius;
            row["angles"] = {arc->start_angle, arc->end_angle};
        } else
            throw std::runtime_error("Coordinate dimensioning accepts lines, polylines, "
                                     "rectangles, circles and arcs only");
        snapshot.push_back(row);
    }
    // The solve treats a construction centerline as an infinite axis: it slides
    // the endpoints along the line and rejects endpoint-based dims (BUG-050), so
    // pin only its offset from a projected datum line. Shared polyline vertices
    // are dimensioned once so adjacent segments cannot over-constrain them.
    std::vector<std::array<double, 2>> placed;
    pin_coordinate_origin(section, origin, anchors, dimensions);
    for (auto row : snapshot) {
        int entity = row["id"];
        std::string prefix = "coord_" + row["name"].get<std::string>();
        if (row["type"].get<int>() == PRO_2D_CENTER_LINE) {
            double s0 = row["points"][0]["xy"][0].get<double>(),
                   s1 = row["points"][0]["xy"][1].get<double>(),
                   e0 = row["points"][1]["xy"][0].get<double>(),
                   e1 = row["points"][1]["xy"][1].get<double>();
            int fixed_axis = fabs(s0 - e0) < 1e-12 ? 0 : (fabs(s1 - e1) < 1e-12 ? 1 : -1);
            if (fixed_axis >= 0) {
                double offset = row["points"][0]["xy"][fixed_axis];
                if (fabs(offset) > 1e-10) {
                    for (int anchor : anchors) {
                        Pro2dEntdef *def = nullptr;
                        CK(ProSectionEntityGet(section, anchor, &def));
                        if (def->type != PRO_2D_LINE && def->type != PRO_2D_CENTER_LINE)
                            continue;
                        auto line = (Pro2dLinedef *)def;
                        if (fabs(line->end1[fixed_axis] - line->end2[fixed_axis]) < 1e-8 &&
                            fabs(line->end1[fixed_axis]) < 1e-8) {
                            ProSectionPointType whole[] = {PRO_ENT_WHOLE, PRO_ENT_WHOLE};
                            int ids[] = {anchor, entity}, dim;
                            Pro2dPnt place = {(s0 + e0) / 2, (s1 + e1) / 2};
                            CK(ProSecdimCreate(section, ids, whole, 2, PRO_TK_DIM_LINE_LINE, place,
                                               &dim));
                            CK(ProSecdimValueSet(section, dim, fabs(offset)));
                            dimensions[prefix + "_offset"] = dim;
                            log("COORDINATE_CENTERLINE_OFFSET=%s axis=%d value=%.12f\n",
                                prefix.c_str(), fixed_axis, fabs(offset));
                            break;
                        }
                    }
                } else
                    log("COORDINATE_CENTERLINE_ON_DATUM=%s axis=%d\n", prefix.c_str(), fixed_axis);
            } else
                // Endpoint dimensions on a skewed centerline are the known-unstable
                // BUG-050 shape: the solve slides endpoints along the infinite axis.
                // Pin nothing here; the infinite-line verification owns the
                // direction/offset comparison for every centerline orientation.
                log("COORDINATE_CENTERLINE_SKEW=%s\n", prefix.c_str());
            continue;
        }
        for (auto point : row["points"]) {
            double px = point["xy"][0].get<double>(), py = point["xy"][1].get<double>();
            bool shared = false;
            for (auto &v : placed)
                if (fabs(v[0] - px) < 1e-9 && fabs(v[1] - py) < 1e-9)
                    shared = true;
            if (shared) {
                log("COORDINATE_SHARED_VERTEX_SKIPPED=%s_%s\n", prefix.c_str(),
                    point["key"].get<std::string>().c_str());
                continue;
            }
            placed.push_back({px, py});
            for (int label_axis = 0; label_axis < 2; label_axis++) {
                int axis = axes[label_axis], ids[] = {origin, entity}, dim;
                ProSectionPointType endpoint = (ProSectionPointType)point["sense"].get<int>(),
                                    points[] = {PRO_ENT_CENTER, endpoint};
                double value = point["xy"][axis];
                if (endpoint == PRO_ENT_END && row["points"].size() == 2 &&
                    fabs(value - row["points"][0]["xy"][axis].get<double>()) < 1e-12) {
                    log("COORDINATE_AXIS_LINE_SHARED=%s axis=%d\n", prefix.c_str(), axis);
                    continue;
                }
                ProSecdimType type = axis ? PRO_TK_DIM_PNT_PNT_VERT : PRO_TK_DIM_PNT_PNT_HORIZ;
                if (endpoint == PRO_ENT_CENTER && fabs(value) < 1e-10)
                    for (int anchor : anchors) {
                        Pro2dEntdef *def = nullptr;
                        CK(ProSectionEntityGet(section, anchor, &def));
                        if (def->type != PRO_2D_LINE && def->type != PRO_2D_CENTER_LINE)
                            continue;
                        auto line = (Pro2dLinedef *)def;
                        if (fabs(line->end1[axis] - line->end2[axis]) < 1e-8 &&
                            fabs(line->end1[axis]) < 1e-8) {
                            ids[0] = anchor;
                            points[0] = PRO_ENT_WHOLE;
                            type = PRO_TK_DIM_LINE_POINT;
                            break;
                        }
                    }
                Pro2dPnt place = {point["xy"][0], point["xy"][1]};
                CK(ProSecdimCreate(section, ids, points, 2, type, place, &dim));
                CK(ProSecdimValueSet(section, dim, fabs(value)));
                dimensions[prefix + "_" + point["key"].get<std::string>() +
                           (label_axis ? "_y" : "_x")] = dim;
            }
        }
        if (row.contains("radius")) {
            ProSectionPointType whole = PRO_ENT_WHOLE;
            int dim;
            Pro2dPnt place = {0, 0};
            CK(ProSecdimCreate(section, &entity, &whole, 1, PRO_TK_DIM_RAD, place, &dim));
            CK(ProSecdimValueSet(section, dim, row["radius"]));
            dimensions[prefix + "_radius"] = dim;
        }
        if (row.contains("angles")) {
            // FEAT-034/T02: the dimension names follow the user's logical
            // endpoints, so a swapped representation labels the stored start
            // point as the logical end and keeps its value on that endpoint.
            auto swapped_entry = arc_logical_swapped.find(row["name"].get<std::string>());
            bool swapped = swapped_entry != arc_logical_swapped.end() && swapped_entry->second;
            for (int i = 0; i < 2; i++) {
                int ids[] = {entity, entity}, dim;
                ProSectionPointType points[] = {PRO_ENT_CENTER, i ? PRO_ENT_END : PRO_ENT_START};
                double angle = row["angles"][i], radius = row["radius"];
                Pro2dPnt place = {row["points"][0]["xy"][0].get<double>() + radius * cos(angle),
                                  row["points"][0]["xy"][1].get<double>() + radius * sin(angle)};
                CK(ProSecdimCreate(section, ids, points, 2, PRO_TK_DIM_ANG_POLAR, place, &dim));
                double degrees;
                CK(ProSecdimValueGet(section, dim, &degrees));
                log("COORDINATE_ARC_POLAR=%s_%d value=%.12f\n", prefix.c_str(), i, degrees);
                if (fabs(remainder(degrees * acos(-1.0) / 180 - angle, 2 * acos(-1.0))) > 1e-8)
                    throw std::runtime_error(
                        "Native polar dimension does not match the supplied arc angle");
                CK(ProSecdimValueSet(section, dim, degrees));
                std::string key = i ? "end_angle" : "start_angle";
                if (swapped)
                    key = i ? "start_angle" : "end_angle";
                dimensions[prefix + "_" + key] = dim;
            }
        }
    }
    return {{"dimension_ids", dimensions}, {"targets", snapshot}, {"origin_id", origin}};
}
// BUG-108/R13: solver noise translates a whole solved profile by tens of microns
// (1.6e-5 .. 4e-3 mm were measured externally), which a 1e-5 mm point gate reads as
// "geometry changed". A provable rigid translation is not a shape change, so it is
// accepted up to this magnitude. The shape gate itself stays at 1e-5 mm: deformed
// profiles are still rejected, and this is a judgement fix, not a looser precision.
static constexpr double RIGID_TRANSLATION_LIMIT_MM = 0.01;

static J verify_coordinate_plan(ProSection section, const J &targets, int origin,
                                double tolerance_mm = 0.00001) {
    double deviation = 0;
    int points = 0;
    // BUG-108: per-point (du,dv) offsets feed the rigid/common-mode verdict.
    std::vector<std::array<double, 2>> offsets;
    J shift_sample = J::array();
    bool shift_truncated = false;
    Pro2dEntdef *coordinate = nullptr;
    CK(ProSectionEntityGet(section, origin, &coordinate));
    auto cs = (Pro2dCoordSysdef *)coordinate;
    log("COORDINATE_ORIGIN=%.12f,%.12f\n", cs->pnt[0], cs->pnt[1]);
    for (auto row : targets) {
        Pro2dEntdef *def = nullptr;
        CK(ProSectionEntityGet(section, row["id"], &def));
        if ((int)def->type != row["type"].get<int>())
            throw std::runtime_error("Coordinate dimensioning changed an entity type");
        // A construction centerline is an infinite axis in any orientation: the
        // solve may slide or trim its endpoints freely, so verify its line
        // identity (direction and offset of both stored endpoints from the
        // requested infinite line) instead of unstable endpoint positions.
        if (def->type == PRO_2D_CENTER_LINE && row["points"].size() == 2) {
            auto line = (Pro2dLinedef *)def;
            double a0 = row["points"][0]["xy"][0].get<double>(),
                   a1 = row["points"][0]["xy"][1].get<double>(),
                   b0 = row["points"][1]["xy"][0].get<double>(),
                   b1 = row["points"][1]["xy"][1].get<double>();
            double dx = b0 - a0, dy = b1 - a1, length = hypot(dx, dy),
                   ux = line->end2[0] - line->end1[0], uy = line->end2[1] - line->end1[1],
                   stored = hypot(ux, uy);
            if (length < 1e-12 || stored < 1e-12)
                throw std::runtime_error("Coordinate verification found a degenerate centerline");
            double turn = fabs(dx * uy - dy * ux) / (length * stored),
                   off1 = fabs(dx * (line->end1[1] - a1) - dy * (line->end1[0] - a0)) / length,
                   off2 = fabs(dx * (line->end2[1] - a1) - dy * (line->end2[0] - a0)) / length;
            log("COORDINATE_CENTERLINE_IDENTITY=%s turn=%.12f offset=%.12f,%.12f\n",
                row["name"].get<std::string>().c_str(), turn, off1, off2);
            deviation = std::max({deviation, turn * length, off1, off2});
            continue;
        }
        for (auto point : row["points"]) {
            double *actual = nullptr;
            if (def->type == PRO_2D_CIRCLE)
                actual = ((Pro2dCircledef *)def)->center;
            else if (def->type == PRO_2D_ARC)
                actual = ((Pro2dArcdef *)def)->center;
            else
                actual = point["sense"].get<int>() == PRO_ENT_START ? ((Pro2dLinedef *)def)->end1
                                                                    : ((Pro2dLinedef *)def)->end2;
            offsets.push_back({actual[0] - point["xy"][0].get<double>(),
                               actual[1] - point["xy"][1].get<double>()});
            for (int axis = 0; axis < 2; axis++) {
                double moved = fabs(actual[axis] - point["xy"][axis].get<double>());
                deviation = std::max(deviation, moved);
                if (moved > 1e-9) {
                    log("COORDINATE_DEVIATION entity=%s point=%s axis=%d moved=%.12f\n",
                        row["name"].get<std::string>().c_str(),
                        point["key"].get<std::string>().c_str(), axis, moved);
                    if ((int)shift_sample.size() < 20)
                        shift_sample.push_back({{"entity", row["name"]},
                                                {"point", point["key"]},
                                                {"axis", axis},
                                                {"moved_mm", moved}});
                    else
                        shift_truncated = true;
                }
            }
            points++;
        }
        if (row.contains("radius"))
            deviation = std::max(deviation,
                                 fabs((def->type == PRO_2D_ARC ? ((Pro2dArcdef *)def)->radius
                                                               : ((Pro2dCircledef *)def)->radius) -
                                      row["radius"].get<double>()));
        if (row.contains("angles")) {
            auto arc = (Pro2dArcdef *)def;
            double actual[] = {arc->start_angle, arc->end_angle};
            for (int i = 0; i < 2; i++)
                deviation = std::max(deviation,
                                     row["radius"].get<double>() *
                                         fabs(remainder(actual[i] - row["angles"][i].get<double>(),
                                                        2 * acos(-1.0))));
        }
    }
    // BUG-108: separate a whole-profile translation from a deformation. The
    // 0.11.1 Creo 10 report showed every entity moving by the same 0.004 mm in
    // u: the supplied shape was moved as a rigid body, not re-solved.
    double max_point = 0, sum_u = 0, sum_v = 0;
    for (auto &offset : offsets) {
        max_point = std::max(max_point, hypot(offset[0], offset[1]));
        sum_u += offset[0];
        sum_v += offset[1];
    }
    const double mean_u = offsets.empty() ? 0.0 : sum_u / (double)offsets.size();
    const double mean_v = offsets.empty() ? 0.0 : sum_v / (double)offsets.size();
    double residual = 0;
    for (auto &offset : offsets)
        residual = std::max(residual, hypot(offset[0] - mean_u, offset[1] - mean_v));
    const bool shifted = max_point > 1e-9;
    const bool rigid = shifted && residual <= 1e-9;
    if (rigid)
        log("SKETCH_SHIFT_RIGID u=%.12f v=%.12f points=%d\n", mean_u, mean_v, points);
    else if (shifted)
        log("SKETCH_SHIFT_DEFORMED max=%.12f residual=%.12f\n", max_point, residual);
    const double translation = rigid ? hypot(mean_u, mean_v) : 0.0;
    const bool rigid_accepted = rigid && translation <= RIGID_TRANSLATION_LIMIT_MM;
    J shift = {{"detected", shifted},
               {"rigid", shifted ? J(rigid) : J(nullptr)},
               {"translation_mm", rigid ? J{{"u", mean_u}, {"v", mean_v}} : J(nullptr)},
               {"translation_magnitude_mm", rigid ? J(translation) : J(nullptr)},
               {"residual_mm", residual},
               {"shape_deviation_mm", residual},
               {"accepted_rigid", rigid_accepted},
               {"max_point_mm", max_point},
               {"point_count", points},
               {"sample", shift_sample},
               {"truncated", shift_truncated},
               {"measurement_scope", "named_section_entities"}};
    if (deviation > tolerance_mm && !rigid_accepted) {
        std::string message =
            "Coordinate dimensioning changed the supplied geometry; maximum deviation mm=" +
            std::to_string(deviation);
        if (rigid)
            message += " (the whole profile translated by u=" + std::to_string(mean_u) +
                       " v=" + std::to_string(mean_v) +
                       " mm, beyond the rigid translation limit of " +
                       std::to_string(RIGID_TRANSLATION_LIMIT_MM) + " mm; it was not re-solved)";
        throw std::runtime_error(message);
    }
    if (deviation > tolerance_mm)
        log("GEOMETRY_DEVIATION_RIGID_ACCEPTED stage=section_regenerate translation=%.12f "
            "residual=%.12f tolerance=%.12f\n",
            translation, residual, tolerance_mm);
    return {{"point_count", points},
            {"max_deviation_mm", deviation},
            {"shape_deviation_mm", residual},
            {"residual_mm", residual},
            {"rigid", shifted ? J(rigid) : J(nullptr)},
            {"translation_mm", rigid ? J{{"u", mean_u}, {"v", mean_v}} : J(nullptr)},
            {"translation_magnitude_mm", rigid ? J(translation) : J(nullptr)},
            {"accepted_rigid", rigid_accepted},
            {"tolerance_mm", tolerance_mm},
            {"shift", shift}};
}
// BUG-108: the public top-level verdict for one sketch record. Measurement stays
// in verify_coordinate_plan; this adds only the policy context, so a caller can
// see that an explicit request tolerance is what let a moved sketch through.
static J sketch_shift_block(const J &verification, const char *tolerance_source) {
    J shift = verification.is_object() && verification.contains("shift")
                  ? verification["shift"]
                  : J{{"detected", nullptr},           {"rigid", nullptr},
                      {"translation_mm", nullptr},     {"residual_mm", nullptr},
                      {"shape_deviation_mm", nullptr}, {"accepted_rigid", false},
                      {"max_point_mm", nullptr},       {"point_count", nullptr},
                      {"sample", J::array()},          {"truncated", false},
                      {"measurement_scope", nullptr}};
    const bool detected = shift["detected"].is_boolean() && shift["detected"].get<bool>();
    const bool rigid = shift["rigid"].is_boolean() && shift["rigid"].get<bool>();
    const std::string source = tolerance_source ? tolerance_source : "";
    const bool accepted = detected && rigid && source == "request";
    // BUG-108/R13: a rigid move inside the translation limit is accepted as a
    // rigid move, independent of whether an explicit request tolerance was set.
    double magnitude = 0;
    if (rigid && shift["translation_mm"].is_object()) {
        double u = shift["translation_mm"]["u"].get<double>();
        double v = shift["translation_mm"]["v"].get<double>();
        magnitude = hypot(u, v);
    }
    const bool accepted_rigid = detected && rigid && magnitude <= RIGID_TRANSLATION_LIMIT_MM;
    shift["total"] = shift.contains("point_count") ? shift["point_count"] : J(nullptr);
    shift["tolerance_source"] = source.empty() ? J(nullptr) : J(source);
    shift["accepted_by_request"] = accepted;
    shift["accepted_rigid"] = accepted_rigid;
    shift["translation_magnitude_mm"] = rigid ? J(magnitude) : J(nullptr);
    if (!detected)
        shift["note"] = "no post-solve shift was measured";
    else if (accepted)
        shift["note"] =
            "the solved profile translated as a rigid body; the request tolerance accepted it, "
            "this is not an exact solve";
    else if (accepted_rigid)
        shift["note"] =
            "the solved profile translated as a rigid body; the move was accepted as a rigid "
            "translation, the shape itself was not re-solved";
    else if (rigid)
        shift["note"] =
            "the solved profile translated as a rigid body, beyond the rigid translation limit";
    else
        shift["note"] = "the solved profile deformed; per-point deviations differ";
    return shift;
}

// FEAT-010/BUG-049: post-solve geometry fidelity reporting. The snapshot and
// report below measure the solved section against what it held before the
// solve, for every dimensioning mode, at both verification points
// (SectionRegenerate and CompleteFeature). Measurement failures stay
// unavailable with a reason; they never degrade to an all-zero pass.
static const char *entity_kind_name(int type) {
    switch (type) {
    case PRO_2D_LINE:
        return "line";
    case PRO_2D_CENTER_LINE:
        return "centerline";
    case PRO_2D_CIRCLE:
        return "circle";
    case PRO_2D_ARC:
        return "arc";
    case PRO_2D_ELLIPSE:
        return "ellipse";
    case PRO_2D_SPLINE:
        return "spline";
    default:
        return "unknown";
    }
}

// Pre-solve target snapshot for any mode. Records what the section actually
// holds (already projected into section coordinates, with the stored arc
// representation) so the solved geometry is compared against the same named
// entities. Types without a measurement formula are marked unmeasurable
// instead of being silently skipped.
static J section_target_snapshot(ProSection section, const std::map<std::string, int> &entities) {
    J snapshot = J::array();
    for (auto item : entities) {
        Pro2dEntdef *def = nullptr;
        CK(ProSectionEntityGet(section, item.second, &def));
        J row = {{"name", item.first}, {"id", item.second}, {"type", (int)def->type}};
        if (def->type == PRO_2D_LINE || def->type == PRO_2D_CENTER_LINE) {
            auto line = (Pro2dLinedef *)def;
            row["points"] = {
                {{"sense", PRO_ENT_START},
                 {"key", "start"},
                 {"xy", {line->end1[0], line->end1[1]}}},
                {{"sense", PRO_ENT_END}, {"key", "end"}, {"xy", {line->end2[0], line->end2[1]}}}};
        } else if (def->type == PRO_2D_CIRCLE) {
            auto circle = (Pro2dCircledef *)def;
            row["points"] = {{{"sense", PRO_ENT_CENTER},
                              {"key", "center"},
                              {"xy", {circle->center[0], circle->center[1]}}}};
            row["radius"] = circle->radius;
        } else if (def->type == PRO_2D_ARC) {
            auto arc = (Pro2dArcdef *)def;
            row["points"] = {{{"sense", PRO_ENT_CENTER},
                              {"key", "center"},
                              {"xy", {arc->center[0], arc->center[1]}}}};
            row["radius"] = arc->radius;
            row["angles"] = {arc->start_angle, arc->end_angle};
        } else if (def->type == PRO_2D_ELLIPSE) {
            auto ellipse = (Pro2dEllipsedef *)def;
            row["points"] = {{{"sense", PRO_ENT_CENTER},
                              {"key", "center"},
                              {"xy", {ellipse->origin[0], ellipse->origin[1]}}}};
            row["radii"] = {ellipse->x_radius, ellipse->y_radius};
        } else if (def->type == PRO_2D_SPLINE) {
            auto spline = (Pro2dSplinedef *)def;
            row["n_points"] = (int)spline->n_points;
            J points = J::array();
            for (unsigned i = 0; spline->point_arr && i < spline->n_points; i++)
                points.push_back({spline->point_arr[i][0], spline->point_arr[i][1]});
            row["points_xy"] = points;
        } else
            row["unmeasurable"] = "unsupported entity type for deviation measurement";
        snapshot.push_back(row);
    }
    return snapshot;
}

// One verification point: compare every named target against the section.
// Non-throwing by design; per-entity failures are recorded with a reason.
static J unavailable_deviation_stage(const std::string &reason) {
    return {{"available", false},
            {"max_deviation_mm", nullptr},
            {"shape_deviation_mm", nullptr},
            {"residual_mm", nullptr},
            {"rigid", nullptr},
            {"translation_mm", nullptr},
            {"translation_magnitude_mm", nullptr},
            {"point_count", nullptr},
            {"total", 0},
            {"sample", J::array()},
            {"truncated", false},
            {"unavailable_reason", reason}};
}
static J geometry_deviation_stage(ProSection section, const J &targets) {
    J sample = J::array();
    bool truncated = false, any_measured = false;
    double worst = 0;
    int total = 0;
    std::string failure;
    // BUG-108/R13: per-point (du,dv) offsets feed the shape-versus-translation
    // verdict. Deviations that a common translation cannot explain (radius,
    // angles, a centerline's line identity) are tracked separately, and any
    // target that could not be measured keeps the stage from claiming rigidity.
    std::vector<std::array<double, 2>> offsets;
    double non_translation = 0;
    bool everything_measured = true;
    for (const auto &row : targets) {
        J entry = {{"entity", row["name"]},
                   {"kind", entity_kind_name(row["type"].get<int>())},
                   {"measurement", nullptr},
                   {"deviation_mm", nullptr},
                   {"reason", nullptr}};
        auto keep = [&]() {
            if (sample.size() < 20)
                sample.push_back(entry);
            else
                truncated = true;
        };
        if (row.contains("unmeasurable")) {
            entry["reason"] = row["unmeasurable"];
            everything_measured = false;
            keep();
            continue;
        }
        Pro2dEntdef *def = nullptr;
        ProError code = ProSectionEntityGet(section, row["id"], &def);
        if (code != PRO_TK_NO_ERROR) {
            entry["reason"] = "ProSectionEntityGet failed (code " + std::to_string((int)code) + ")";
            if (failure.empty())
                failure = entry["reason"].get<std::string>();
            everything_measured = false;
            keep();
            total++;
            continue;
        }
        int type = row["type"].get<int>();
        if ((int)def->type != type) {
            entry["reason"] = "entity type changed during the solve";
            everything_measured = false;
            keep();
            total++;
            continue;
        }
        double moved = 0;
        const char *measurement = nullptr;
        bool measured = true;
        if (type == PRO_2D_CENTER_LINE && row.contains("points") && row["points"].size() == 2) {
            // A construction centerline is an infinite axis: the solve may
            // slide its endpoints, so compare the line identity (direction
            // and offsets) instead of endpoint positions (BUG-050).
            auto line = (Pro2dLinedef *)def;
            double a0 = row["points"][0]["xy"][0].get<double>(),
                   a1 = row["points"][0]["xy"][1].get<double>(),
                   b0 = row["points"][1]["xy"][0].get<double>(),
                   b1 = row["points"][1]["xy"][1].get<double>();
            double dx = b0 - a0, dy = b1 - a1, length = hypot(dx, dy),
                   ux = line->end2[0] - line->end1[0], uy = line->end2[1] - line->end1[1],
                   stored = hypot(ux, uy);
            if (length < 1e-12 || stored < 1e-12) {
                measured = false;
                everything_measured = false;
                entry["reason"] = "degenerate centerline after the solve";
            } else {
                double turn = fabs(dx * uy - dy * ux) / (length * stored),
                       off1 = fabs(dx * (line->end1[1] - a1) - dy * (line->end1[0] - a0)) / length,
                       off2 = fabs(dx * (line->end2[1] - a1) - dy * (line->end2[0] - a0)) / length;
                moved = std::max({turn * length, off1, off2});
                non_translation = std::max(non_translation, moved);
                measurement = "line_identity";
            }
        } else if (type == PRO_2D_LINE) {
            auto line = (Pro2dLinedef *)def;
            for (const auto &point : row["points"]) {
                const double *actual =
                    point["sense"].get<int>() == PRO_ENT_START ? line->end1 : line->end2;
                offsets.push_back({actual[0] - point["xy"][0].get<double>(),
                                   actual[1] - point["xy"][1].get<double>()});
                for (int axis = 0; axis < 2; axis++)
                    moved = std::max(moved, fabs(actual[axis] - point["xy"][axis].get<double>()));
            }
            measurement = "endpoints";
        } else if (type == PRO_2D_CIRCLE) {
            auto circle = (Pro2dCircledef *)def;
            offsets.push_back({circle->center[0] - row["points"][0]["xy"][0].get<double>(),
                               circle->center[1] - row["points"][0]["xy"][1].get<double>()});
            moved = std::max(fabs(circle->center[0] - row["points"][0]["xy"][0].get<double>()),
                             fabs(circle->center[1] - row["points"][0]["xy"][1].get<double>()));
            const double radius = fabs(circle->radius - row["radius"].get<double>());
            non_translation = std::max(non_translation, radius);
            moved = std::max(moved, radius);
            measurement = "center_radius";
        } else if (type == PRO_2D_ARC) {
            auto arc = (Pro2dArcdef *)def;
            offsets.push_back({arc->center[0] - row["points"][0]["xy"][0].get<double>(),
                               arc->center[1] - row["points"][0]["xy"][1].get<double>()});
            moved = std::max(fabs(arc->center[0] - row["points"][0]["xy"][0].get<double>()),
                             fabs(arc->center[1] - row["points"][0]["xy"][1].get<double>()));
            const double radius = fabs(arc->radius - row["radius"].get<double>());
            non_translation = std::max(non_translation, radius);
            moved = std::max(moved, radius);
            double actual[] = {arc->start_angle, arc->end_angle};
            for (int i = 0; i < 2; i++) {
                const double swept =
                    row["radius"].get<double>() *
                    fabs(remainder(actual[i] - row["angles"][i].get<double>(), 2 * acos(-1.0)));
                non_translation = std::max(non_translation, swept);
                moved = std::max(moved, swept);
            }
            measurement = "center_radius_angles";
        } else if (type == PRO_2D_ELLIPSE) {
            auto ellipse = (Pro2dEllipsedef *)def;
            offsets.push_back({ellipse->origin[0] - row["points"][0]["xy"][0].get<double>(),
                               ellipse->origin[1] - row["points"][0]["xy"][1].get<double>()});
            moved = std::max(fabs(ellipse->origin[0] - row["points"][0]["xy"][0].get<double>()),
                             fabs(ellipse->origin[1] - row["points"][0]["xy"][1].get<double>()));
            const double x_radius = fabs(ellipse->x_radius - row["radii"][0].get<double>());
            const double y_radius = fabs(ellipse->y_radius - row["radii"][1].get<double>());
            non_translation = std::max({non_translation, x_radius, y_radius});
            moved = std::max({moved, x_radius, y_radius});
            measurement = "origin_radii";
        } else if (type == PRO_2D_SPLINE) {
            auto spline = (Pro2dSplinedef *)def;
            if ((int)spline->n_points != row["n_points"].get<int>()) {
                measured = false;
                everything_measured = false;
                entry["reason"] = "spline point count changed during the solve";
            } else {
                for (unsigned i = 0; spline->point_arr && i < spline->n_points; i++) {
                    offsets.push_back(
                        {spline->point_arr[i][0] - row["points_xy"][i][0].get<double>(),
                         spline->point_arr[i][1] - row["points_xy"][i][1].get<double>()});
                    moved = std::max(
                        {moved,
                         fabs(spline->point_arr[i][0] - row["points_xy"][i][0].get<double>()),
                         fabs(spline->point_arr[i][1] - row["points_xy"][i][1].get<double>())});
                }
                measurement = "control_points";
            }
        } else {
            measured = false;
            everything_measured = false;
            entry["reason"] = "unsupported entity type for deviation measurement";
        }
        if (measured) {
            entry["measurement"] = measurement;
            entry["deviation_mm"] = moved;
            worst = std::max(worst, moved);
            any_measured = true;
        } else {
            everything_measured = false;
        }
        keep();
        total++;
    }
    // Shape = what is left after removing a common translation. A rigid move
    // leaves shape at machine noise; a re-solve that really changed the profile
    // (or changed a radius/angle/axis) shows up immediately.
    double max_point = 0, sum_u = 0, sum_v = 0;
    for (const auto &offset : offsets) {
        max_point = std::max(max_point, hypot(offset[0], offset[1]));
        sum_u += offset[0];
        sum_v += offset[1];
    }
    const double mean_u = offsets.empty() ? 0.0 : sum_u / (double)offsets.size();
    const double mean_v = offsets.empty() ? 0.0 : sum_v / (double)offsets.size();
    double residual = 0;
    for (const auto &offset : offsets)
        residual = std::max(residual, hypot(offset[0] - mean_u, offset[1] - mean_v));
    const double shape = std::max(residual, non_translation);
    const double translation = hypot(mean_u, mean_v);
    const bool rigid = everything_measured && any_measured && !offsets.empty() &&
                       translation > 1e-9 && shape <= 1e-9;
    if (any_measured)
        log("GEOMETRY_STAGE_SHAPE points=%d translation=%.12f shape=%.12f rigid=%d total=%d\n",
            (int)offsets.size(), translation, shape, rigid ? 1 : 0, total);
    return {
        {"available", any_measured},
        {"max_deviation_mm", any_measured ? J(worst) : J(nullptr)},
        {"shape_deviation_mm", any_measured ? J(shape) : J(nullptr)},
        {"residual_mm", any_measured ? J(residual) : J(nullptr)},
        {"rigid", any_measured ? J(rigid) : J(nullptr)},
        {"translation_mm", (any_measured && rigid) ? J{{"u", mean_u}, {"v", mean_v}} : J(nullptr)},
        {"translation_magnitude_mm", (any_measured && rigid) ? J(translation) : J(nullptr)},
        {"point_count", (int)offsets.size()},
        {"total", total},
        {"sample", sample},
        {"truncated", truncated},
        {"unavailable_reason",
         any_measured
             ? J(nullptr)
             : J(failure.empty() ? "no measurable entities in the target snapshot" : failure)}};
}

// Merges both verification points into the published geometry_deviation
// block. The worst deviation across SectionRegenerate and CompleteFeature is
// reported; the per-stage detail stays available for diagnosis.
static J skipped_geometry_deviation(const std::string &reason) {
    // A path that never re-solved (identical payload shortcut) publishes an
    // explicitly unavailable report instead of implying a fresh measurement.
    return {{"available", false},
            {"unavailable_reason", reason},
            {"measurement_scope", "named_section_entities"},
            {"warning_threshold_mm", nullptr},
            {"max_deviation_mm", nullptr},
            {"exceeds_warning", nullptr},
            {"shape_deviation_mm", nullptr},
            {"residual_mm", nullptr},
            {"rigid", nullptr},
            {"translation_mm", nullptr},
            {"accepted_rigid", nullptr},
            {"total", 0},
            {"sample", J::array()},
            {"truncated", false},
            {"enforced", false},
            {"tolerance_source", nullptr},
            {"stages", J::object()}};
}
static J geometry_deviation_report(const J &regenerate_stage, const J &feature_stage,
                                   double tolerance_mm, bool enforce, const char *source) {
    bool available =
        regenerate_stage["available"].get<bool>() || feature_stage["available"].get<bool>();
    double worst = 0;
    bool has = false;
    for (const J *stage : {&regenerate_stage, &feature_stage}) {
        if (stage->at("available").get<bool>()) {
            worst = std::max(worst, stage->at("max_deviation_mm").get<double>());
            has = true;
        }
    }
    J sample = J::array();
    bool truncated = false;
    int total = 0;
    std::string reason;
    for (const J *stage : {&regenerate_stage, &feature_stage}) {
        for (const auto &entry : stage->at("sample")) {
            if (sample.size() < 20)
                sample.push_back(entry);
            else
                truncated = true;
        }
        truncated = truncated || stage->at("truncated").get<bool>();
        total += stage->at("total").get<int>();
        if (!stage->at("available").get<bool>()) {
            const std::string &why = stage->at("unavailable_reason").get<std::string>();
            if (!why.empty())
                reason = reason.empty() ? why : reason + "; " + why;
        }
    }
    // BUG-108/R13: publish the shape-versus-translation verdict beside the
    // deviation. A stage only proves rigidity when it measured every target, and
    // two disagreeing stages resolve to "not rigid" rather than a hopeful yes.
    const J *primary = nullptr;
    double primary_deviation = -1;
    bool rigid_known = false, rigid_all = true;
    double shape = 0;
    for (const J *stage : {&regenerate_stage, &feature_stage}) {
        if (!stage->at("available").get<bool>())
            continue;
        rigid_known = true;
        const bool stage_rigid = stage->at("rigid").is_boolean() && stage->at("rigid").get<bool>();
        rigid_all = rigid_all && stage_rigid;
        shape = std::max(shape, stage->at("shape_deviation_mm").get<double>());
        const double deviation = stage->at("max_deviation_mm").get<double>();
        if (deviation > primary_deviation) {
            primary = stage;
            primary_deviation = deviation;
        }
    }
    const bool rigid = has && rigid_known && rigid_all;
    double magnitude = 0;
    J translation = J(nullptr);
    if (rigid && primary) {
        translation = primary->at("translation_mm");
        magnitude = primary->at("translation_magnitude_mm").get<double>();
    }
    const bool accepted_rigid = rigid && magnitude <= RIGID_TRANSLATION_LIMIT_MM;
    return {{"available", available},
            {"unavailable_reason", available ? J(nullptr) : J(reason)},
            {"measurement_scope", "named_section_entities"},
            {"warning_threshold_mm", tolerance_mm},
            {"max_deviation_mm", has ? J(worst) : J(nullptr)},
            {"exceeds_warning", has ? J(worst > tolerance_mm) : J(nullptr)},
            {"shape_deviation_mm", has ? J(shape) : J(nullptr)},
            {"residual_mm", has ? J(shape) : J(nullptr)},
            {"rigid", has ? J(rigid) : J(nullptr)},
            {"translation_mm", translation},
            {"accepted_rigid", has ? J(accepted_rigid) : J(nullptr)},
            {"total", total},
            {"sample", sample},
            {"truncated", truncated},
            {"enforced", enforce},
            {"tolerance_source", source},
            {"stages",
             {{"section_regenerate", regenerate_stage}, {"complete_feature", feature_stage}}}};
}

// Resolves the FEAT-010/BUG-049 tolerance policy for one sketch operation.
// An explicit request value is validated (finite, strictly positive, no
// bool/NaN/Inf) and enforced as a hard cap in any mode; the coordinates
// default keeps the current 1e-5 mm rejection gate; other modes stay
// creatable and warn above 1e-3 mm.
struct DeviationPolicy {
    double tolerance;
    bool enforce;
    const char *source;
};
static DeviationPolicy resolve_geometry_tolerance(const J &op, const std::string &mode) {
    auto it = op.find("geometry_tolerance_mm");
    if (it != op.end() && !it->is_null()) {
        if (!it->is_number())
            throw std::runtime_error(
                "geometry_tolerance_mm must be a finite positive number of millimeters");
        double value = it->get<double>();
        if (!std::isfinite(value) || value <= 0)
            throw std::runtime_error(
                "geometry_tolerance_mm must be a finite positive number of millimeters");
        return {value, true, "request"};
    }
    if (mode == "coordinates")
        return {0.00001, true, "default_coordinates"};
    return {0.001, false, "default_autodim"};
}

// Applies the policy to the merged report. An enforced policy is a strict
// guarantee: a stage that could not measure is also a rejection, never a
// silent pass. BUG-108/R13: a provable rigid translation inside the limit is
// the one documented exception — the profile was moved, not re-solved, so the
// shape gate (shape deviation, not point displacement) still has to pass.
static void enforce_geometry_deviation(const J &report, const char *context) {
    if (!report["enforced"].get<bool>())
        return;
    double tolerance = report["warning_threshold_mm"].get<double>();
    const bool accepted_rigid =
        report["accepted_rigid"].is_boolean() && report["accepted_rigid"].get<bool>();
    for (const char *name : {"section_regenerate", "complete_feature"}) {
        const J &stage = report["stages"][name];
        if (!stage["available"].get<bool>())
            throw std::runtime_error(
                std::string(context) +
                ": the requested geometry tolerance requires measurable geometry; " +
                stage["unavailable_reason"].get<std::string>());
        if (stage["max_deviation_mm"].get<double>() > tolerance) {
            const bool stage_rigid = stage["rigid"].is_boolean() && stage["rigid"].get<bool>();
            const bool shape_ok = stage["shape_deviation_mm"].is_number() &&
                                  stage["shape_deviation_mm"].get<double>() <= tolerance;
            if (accepted_rigid && stage_rigid && shape_ok) {
                log("GEOMETRY_DEVIATION_RIGID_ACCEPTED stage=%s max=%.12f shape=%.12f "
                    "translation=%.12f tolerance=%.12f\n",
                    name, stage["max_deviation_mm"].get<double>(),
                    stage["shape_deviation_mm"].get<double>(),
                    stage["translation_magnitude_mm"].get<double>(), tolerance);
                continue;
            }
            log("GEOMETRY_DEVIATION_REJECTED stage=%s max=%.12f tolerance=%.12f\n", name,
                stage["max_deviation_mm"].get<double>(), tolerance);
            std::string message = std::string(context) +
                                  " changed the supplied geometry; maximum deviation mm=" +
                                  std::to_string(stage["max_deviation_mm"].get<double>());
            if (stage_rigid)
                message += " (the whole profile translated as a rigid body by " +
                           std::to_string(stage["translation_magnitude_mm"].get<double>()) +
                           " mm, beyond the rigid translation limit of " +
                           std::to_string(RIGID_TRANSLATION_LIMIT_MM) + " mm)";
            throw std::runtime_error(message);
        }
    }
}
