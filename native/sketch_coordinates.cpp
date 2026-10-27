// Complete coordinate dimensions for exact, fully supplied profile geometry.
// Accepted native profiles include large polygons, axis-aligned/rotated arcs and circles.
static std::string profile_dimensioning(const J &op) {
    std::string requested = op.value("dimensioning", "auto");
    if (requested != "auto")
        return requested;
    if (!op.value("dimensions", J::array()).empty() || !op.value("constraints", J::array()).empty())
        return "autodim";
    double extent = 0;
    int count = 0;
    for (auto e : op.at("entities")) {
        std::string type = e.at("type");
        if (type != "line" && type != "centerline" && type != "rectangle" && type != "polyline" &&
            type != "circle" && type != "arc")
            return "autodim";
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
    return count >= 10 || extent > 1000 ? "coordinates" : "autodim";
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
        if (row.contains("angles"))
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
                dimensions[prefix + (i ? "_end_angle" : "_start_angle")] = dim;
            }
    }
    return {{"dimension_ids", dimensions}, {"targets", snapshot}, {"origin_id", origin}};
}
static J verify_coordinate_plan(ProSection section, const J &targets, int origin) {
    double deviation = 0;
    int points = 0;
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
            for (int axis = 0; axis < 2; axis++) {
                double moved = fabs(actual[axis] - point["xy"][axis].get<double>());
                deviation = std::max(deviation, moved);
                if (moved > 1e-9)
                    log("COORDINATE_DEVIATION entity=%s point=%s axis=%d moved=%.12f\n",
                        row["name"].get<std::string>().c_str(),
                        point["key"].get<std::string>().c_str(), axis, moved);
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
    if (deviation > 0.00001)
        throw std::runtime_error(
            "Coordinate dimensioning changed the supplied geometry; maximum deviation mm=" +
            std::to_string(deviation));
    return {{"point_count", points}, {"max_deviation_mm", deviation}, {"tolerance_mm", 0.00001}};
}
