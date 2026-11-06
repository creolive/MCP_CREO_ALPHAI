// FEAT-058: native rectangular unattached planar wall and its in-place resize.
// See native/planar_wall.h for the measured basis and the tree rationale.

#include <set>

// R03: the walls this job created. The resize context is decided by execution
// order, not by a label: a wall created earlier in the same plan was never
// saved and reloaded, so its gauge belongs to ``current_plan``.
static std::set<std::string> planar_walls_created_this_job;

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

// The wall's body is the only sheetmetal body that carries geometry; the stock
// template keeps an empty body next to it. Gauge and part link are read from
// that body - never taken from the request - so a wall that ignores the
// requested thickness cannot look verified. SDK generations that do not declare
// the body reads stay compilable through the generated capability macros; there
// the thickness is reported as unverified instead of being invented.
struct PlanarWallBodies {
    int total = 0;
    int sheetmetal = 0;
    int material = 0;
    double thickness = 0;
    bool thickness_known = false;
    int thickness_code = 0;
    // FEAT-058/R03: how the gauge was (or was not) obtained. A missing SDK
    // declaration and a failed call both used to publish one null, so the
    // receipt could not say which had happened.
    std::string gauge_source = "not_measured";
    std::string gauge_reason;
    // R03: the material body's measured outline. It is the only independent
    // gauge when this SDK generation declares no body thickness API.
    ProOutline outline = {};
    bool outline_known = false;
    double geometry_span = 0;
    bool geometry_known = false;
    bool linked = false;
    bool linked_known = false;
};

static PlanarWallBodies planar_wall_bodies() {
    PlanarWallBodies evidence;
    ProSolidBody *bodies = nullptr;
    CK(ProSolidBodiesCollect((ProSolid)board, &bodies));
    int count = 0;
    CK(ProArraySizeGet((ProArray)bodies, &count));
    evidence.total = count;
    int material_index = -1;
    double material_size = 0;
    for (int i = 0; i < count; i++) {
        ProBoolean smt = PRO_B_FALSE;
        if (ProSolidBodyIsSheetmetal(&bodies[i], &smt) != PRO_TK_NO_ERROR || !smt)
            continue;
        evidence.sheetmetal++;
        ProOutline outline = {};
        if (ProSolidBodyOutlineGet(&bodies[i], outline) != PRO_TK_NO_ERROR)
            continue;
        double size = 0;
        for (int axis = 0; axis < 3; axis++)
            size += fabs(outline[1][axis] - outline[0][axis]);
        if (size <= PLANAR_WALL_ENVELOPE_TOLERANCE)
            continue;
        evidence.material++;
        if (size > material_size) {
            material_size = size;
            material_index = i;
            for (int row = 0; row < 2; row++)
                for (int axis = 0; axis < 3; axis++)
                    evidence.outline[row][axis] = outline[row][axis];
            evidence.outline_known = true;
        }
    }
    if (evidence.material != 1) {
        // The gauge belongs to the wall, so exactly one body may carry its
        // material. Reading the largest of several would publish a number that
        // cannot be attributed to this wall.
        evidence.gauge_reason = "thickness_material_body_not_unique";
    } else {
#if defined(MECHDOG_HAS_ProSmtBodyThicknessValueGet) &&                                            \
    !defined(MECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API)
        evidence.gauge_source = "api";
        double value = 0;
        evidence.thickness_code = ProSmtBodyThicknessValueGet(&bodies[material_index], &value);
        evidence.thickness_known =
            evidence.thickness_code == PRO_TK_NO_ERROR && std::isfinite(value);
        if (evidence.thickness_code != PRO_TK_NO_ERROR)
            evidence.gauge_reason = "thickness_api_query_failed";
        else if (!std::isfinite(value))
            evidence.gauge_reason = "thickness_value_not_finite";
        if (evidence.thickness_known)
            evidence.thickness = value;
#else
        evidence.thickness_code = -1; // -1: this SDK generation declares no body gauge read
        evidence.gauge_source = "missing_api";
        evidence.gauge_reason = "thickness_api_unavailable";
#endif
    }
    if (material_index >= 0) {
#ifdef MECHDOG_HAS_ProSmtBodyIsLinkedToPart
        ProBoolean linked = PRO_B_FALSE;
        if (ProSmtBodyIsLinkedToPart(&bodies[material_index], &linked) == PRO_TK_NO_ERROR) {
            evidence.linked = linked == PRO_B_TRUE;
            evidence.linked_known = true;
        }
#endif
    }
    ProArrayFree((ProArray *)&bodies);
    return evidence;
}

static void planar_wall_log_bodies(const PlanarWallBodies &bodies, const char *phase) {
    log("PLANAR_WALL_BODIES phase=%s total=%d sheetmetal=%d material=%d thickness_mm=%.9f "
        "thickness_known=%d thickness_code=%d gauge_source=%s gauge_reason=%s linked=%d "
        "linked_known=%d\n",
        phase, bodies.total, bodies.sheetmetal, bodies.material, bodies.thickness,
        (int)bodies.thickness_known, bodies.thickness_code, bodies.gauge_source.c_str(),
        bodies.gauge_reason.empty() ? "-" : bodies.gauge_reason.c_str(), (int)bodies.linked,
        (int)bodies.linked_known);
}

// Why the gauge could not be read, for the refusal message. The reason is kept
// next to the raw Toolkit code instead of being replaced by it.
static std::string planar_wall_gauge_failure(const PlanarWallBodies &bodies) {
    if (!bodies.gauge_reason.empty())
        return bodies.gauge_reason;
    return "ProSmtBodyThicknessValueGet=" + std::to_string(bodies.thickness_code);
}

// FEAT-058/R03: one gauge receipt per operation. ``status`` separates a
// verified reading from a missing SDK declaration (unverified), a reading that
// disagrees (mismatch) and a gauge that could not be measured at all
// (unavailable); ``source`` says whether the API answered, was absent or was
// never asked; ``context`` ties the value to this plan or to the loaded file.
// Nothing here invents a value: an unreadable gauge publishes null.
static J planar_wall_thickness_validation(const PlanarWallBodies &bodies, double thickness,
                                          const char *context) {
    J block = {{"status", "unavailable"},
               {"source", bodies.gauge_source},
               {"value_mm", nullptr},
               {"reason", bodies.gauge_reason.empty() ? J(nullptr) : J(bodies.gauge_reason)},
               {"context", context}};
    double measured = bodies.thickness;
    bool known = bodies.thickness_known;
    if (!known && bodies.geometry_known) {
        measured = bodies.geometry_span;
        known = true;
    }
    if (known) {
        block["value_mm"] = measured;
        if (fabs(measured - thickness) <= 1e-6) {
            block["status"] = "verified";
            block["reason"] = nullptr;
        } else {
            block["status"] = "mismatch";
            block["reason"] = "thickness_measured_mismatch";
        }
    } else if (bodies.gauge_source == "missing_api") {
        block["status"] = "unverified";
    }
    return block;
}

// R03: a frame axis is axis-aligned only when exactly one component is a unit
// value. A rotated frame cannot use the box extent as a normal span.
static bool planar_wall_axis_aligned(const V &axis) {
    int unit = 0;
    for (double component : axis) {
        if (!std::isfinite(component))
            return false;
        if (fabs(fabs(component) - 1) <= 1e-6)
            unit++;
        else if (fabs(component) > 1e-6)
            return false;
    }
    return unit == 1;
}

// FEAT-058/R03: when this SDK generation declares no body gauge API, the wall's
// own material extent along the frame normal is the only independent gauge. It
// is accepted only for one material body, a pure rectangle (no downstream
// feature) and an axis-aligned frame; the driving size, signed envelope and
// volume stay cross-checks and never become the source. An API that exists but
// fails never reaches this fallback.
static void planar_wall_geometry_gauge(PlanarWallBodies &bodies, const V &normal, double thickness,
                                       const V &u, const V &v, int child_count) {
    if (bodies.thickness_known || bodies.gauge_source != "missing_api")
        return;
    if (bodies.material != 1 || !bodies.outline_known) {
        bodies.gauge_reason = "thickness_material_body_not_unique";
        return;
    }
    if (child_count != 0) {
        bodies.gauge_reason = "thickness_geometry_has_downstream_features";
        return;
    }
    if (!planar_wall_axis_aligned(u) || !planar_wall_axis_aligned(v) ||
        !planar_wall_axis_aligned(normal)) {
        bodies.gauge_reason = "thickness_geometry_frame_not_axis_aligned";
        return;
    }
    double span = 0;
    for (int axis = 0; axis < 3; axis++)
        span += fabs(normal[axis]) * fabs(bodies.outline[1][axis] - bodies.outline[0][axis]);
    if (!std::isfinite(span) || span <= PLANAR_WALL_ENVELOPE_TOLERANCE) {
        bodies.gauge_reason = "thickness_geometry_span_unavailable";
        return;
    }
    bodies.geometry_span = span;
    bodies.geometry_known = true;
    bodies.gauge_source = "geometry_normal_span";
    bodies.gauge_reason.clear();
    log("PLANAR_WALL_GEOMETRY_GAUGE span_mm=%.9f requested_mm=%.9f\n", span, thickness);
}

// A span-only envelope accepted a wall that grew on the opposite side of the
// sketch plane at the wrong origin offset. The rectangle starts at the sketch
// origin, so the accepted interval is signed: u[0,L], v[0,W] and either
// n[0,t] or n[-t,0].
static void planar_wall_require_envelope(const J &envelope, double length, double width,
                                         double thickness, bool negative, const char *phase) {
    struct Expected {
        const char *axis;
        double low;
        double high;
    } expected[3] = {{"u", 0.0, length},
                     {"v", 0.0, width},
                     {"n", negative ? -thickness : 0.0, negative ? 0.0 : thickness}};
    for (const auto &axis : expected) {
        const J &entry = envelope[axis.axis];
        double low = entry["min"].get<double>();
        double high = entry["max"].get<double>();
        double scale = std::max(std::max(fabs(axis.high - axis.low), 1.0), fabs(low) + fabs(high));
        double tolerance =
            std::max(PLANAR_WALL_ENVELOPE_TOLERANCE, scale * PLANAR_WALL_ENVELOPE_TOLERANCE);
        if (fabs(low - axis.low) > tolerance || fabs(high - axis.high) > tolerance)
            throw std::runtime_error(
                std::string("The ") + phase + " wall envelope on " + axis.axis + " is [" +
                std::to_string(low) + ", " + std::to_string(high) +
                "] mm instead of the requested [" + std::to_string(axis.low) + ", " +
                std::to_string(axis.high) +
                "] mm: the wall grew on the wrong side of the sketch plane or away from the "
                "sketch origin");
    }
    log("PLANAR_WALL_ENVELOPE phase=%s direction=%s u=[%.9f,%.9f] v=[%.9f,%.9f] "
        "n=[%.9f,%.9f]\n",
        phase, negative ? "negative" : "positive", envelope["u"]["min"].get<double>(),
        envelope["u"]["max"].get<double>(), envelope["v"]["min"].get<double>(),
        envelope["v"]["max"].get<double>(), envelope["n"]["min"].get<double>(),
        envelope["n"]["max"].get<double>());
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

// PRO_E_STD_DIRECTION grows along the *support surface* normal, which is not
// always the reported frame normal: the named-plane sketch keeps the requested
// axis as its view normal while the datum plane under it may point the other
// way, so XZ with direction=positive grew toward -n. The wall is documented to
// grow toward +n, so the tree direction is corrected by the support normal the
// sketch really sits on.
static V planar_wall_support_normal(const J &plane) {
    J reference = plane.is_string() ? J{{"kind", "datum_plane"},
                                        {"axis", plane == "XY"   ? "z"
                                                 : plane == "XZ" ? "y"
                                                                 : "x"},
                                        {"offset", 0}}
                                    : plane.at("reference");
    ProSelection support = resolve(reference);
    ProModelitem item;
    CK(ProSelectionModelitemGet(support, &item));
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, item.id, &surface));
    ProSelectionFree(&support);
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    V normal = {0, 0, 0};
    if (data && data->data.p_surface_data && data->data.p_surface_data->type == PRO_SRF_PLANE) {
        auto &axis = data->data.p_surface_data->srf_shape.plane.e3;
        normal = {axis[0], axis[1], axis[2]};
    }
    if (data)
        ProGeomitemdataFree(&data);
    return normalized(normal);
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
    // The internal sketch is a real feature name: creating it while the name is
    // already taken would overwrite a managed alias behind the caller's back.
    if (alias_entry(label) || alias_entry(sketch_name))
        throw std::runtime_error(
            "The planar wall would create " + label + " and " + sketch_name +
            ", but that name already exists in this model; managed labels are never overwritten");
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
    V support_normal = planar_wall_support_normal(op["plane"]);
    bool support_flipped = dot(support_normal, n) < 0;
    // +1 grows along +support_normal. Aligned support: that is +n. Flipped
    // support: the tree sign has to be inverted to still grow toward +n.
    int tree_direction = (support_flipped == negative) ? 1 : -1;
    log("PLANAR_WALL_DIRECTION requested=%s support_flipped=%d tree=%d support_n=%.6f,%.6f,%.6f "
        "frame_n=%.6f,%.6f,%.6f\n",
        negative ? "negative" : "positive", (int)support_flipped, tree_direction, support_normal[0],
        support_normal[1], support_normal[2], n[0], n[1], n[2]);
    integer(root, PRO_E_STD_DIRECTION, tree_direction);
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
    PlanarWallBodies bodies = planar_wall_bodies();
    planar_wall_log_bodies(bodies, "created");
    log("PLANAR_WALL_CREATED feature_id=%d sketch=%s dimensions=%d\n", wall.id, sketch_name.c_str(),
        dimensions);
    if (dimensions < PLANAR_WALL_MIN_DIMENSIONS)
        throw std::runtime_error("The driving sketch carries only " + std::to_string(dimensions) +
                                 " point dimensions; the rectangle would stay under-constrained");
    if (!bodies.sheetmetal)
        throw std::runtime_error(
            "The wall regenerated but no body reports the sheetmetal state; the feature is not a "
            "sheetmetal wall in this part");
    if (!bodies.material)
        throw std::runtime_error(
            "The wall regenerated but no sheetmetal body carries geometry; the feature did not "
            "build a wall body");
    planar_wall_require_envelope(envelope, length, width, thickness, negative, "created");
    // R03: a wall just created by this job has no downstream feature, so the
    // geometry fallback can measure its own material extent.
    planar_wall_geometry_gauge(bodies, n, thickness, u, v, 0);
    // The gauge is read back from the wall's own body. A measured value that
    // disagrees fails the operation; an unreadable one is published as
    // unverified (older SDKs) instead of being replaced by the request.
    if (bodies.thickness_known && fabs(bodies.thickness - thickness) > 1e-6)
        throw std::runtime_error("The wall body carries " + std::to_string(bodies.thickness) +
                                 " mm instead of the requested " + std::to_string(thickness) +
                                 " mm; the sheetmetal gauge was not applied");
    if (bodies.geometry_known && fabs(bodies.geometry_span - thickness) > 1e-6)
        throw std::runtime_error("The wall body spans " + std::to_string(bodies.geometry_span) +
                                 " mm along the normal instead of the requested " +
                                 std::to_string(thickness) +
                                 " mm; the measured geometry does not carry the gauge");
#if defined(MECHDOG_HAS_ProSmtBodyThicknessValueGet) &&                                            \
    !defined(MECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API)
    if (!bodies.thickness_known)
        throw std::runtime_error("The wall body thickness could not be read (" +
                                 planar_wall_gauge_failure(bodies) +
                                 "); the gauge cannot be verified independently");
#endif

    J frame = {{"origin", xyz(origin.data())},
               {"u_axis", xyz(u.data())},
               {"v_axis", xyz(v.data())},
               {"normal", xyz(n.data())}};
    std::string direction = negative ? "negative" : "positive";
    remember(op, wall,
             {{"planar_wall",
               {{"sketch", sketch_name},
                {"length", length},
                {"width", width},
                {"thickness", thickness},
                {"direction", direction},
                {"frame", frame}}}});
    planar_walls_created_this_job.insert(label);
    stage_operation_result(
        {{"op", "sheetmetal_planar_wall"},
         {"feature", label},
         {"feature_id", wall.id},
         {"sketch", sketch_name},
         {"length", length},
         {"width", width},
         {"thickness", thickness},
         {"direction", direction},
         {"square", fabs(length - width) <= 1e-9},
         {"dimension_count", dimensions},
         {"volume_mm3", measured},
         {"frame", frame},
         {"envelope", envelope},
         {"bounds_mm", bounds},
         {"sheetmetal_body", bodies.sheetmetal > 0},
         {"sheetmetal_bodies", bodies.sheetmetal},
         {"material_bodies", bodies.material},
         {"thickness_source", thickness_from_parameter ? "parameter" : "element"},
         {"thickness_measured_mm", bodies.thickness_known ? J(bodies.thickness) : J(nullptr)},
         {"thickness_verified", bodies.thickness_known},
         {"thickness_body_code", bodies.thickness_code},
         {"thickness_geometry_span_mm",
          bodies.geometry_known ? J(bodies.geometry_span) : J(nullptr)},
         {"wall_created_this_job", true},
         {"thickness_validation",
          planar_wall_thickness_validation(bodies, thickness, "current_plan")},
         {"body_linked", bodies.linked_known ? J(bodies.linked) : J(nullptr)}});
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
    bool negative = record.value("direction", "positive") == "negative";
    J frame = record.value("frame", J::object());
    double length = op["length"].get<double>();
    double width = op["width"].get<double>();
    ProFeature wall = feature(label);
    // R03: only a wall loaded from the saved file is a saved read. A wall this
    // job created earlier in the same plan was never saved, so its gauge is the
    // current plan's, even though this resize re-measures it.
    const bool created_this_job = planar_walls_created_this_job.count(label) > 0;
    const char *loaded_context = created_this_job ? "current_plan" : "saved_loaded";

    // The part was loaded from the saved file at the start of this job, so a
    // wall created by an earlier job was read back from disk here.
    PlanarWallBodies loaded = planar_wall_bodies();
    planar_wall_log_bodies(loaded, "loaded");
    if (loaded.thickness_known && fabs(loaded.thickness - thickness) > 1e-6)
        throw std::runtime_error("The saved wall carries " + std::to_string(loaded.thickness) +
                                 " mm instead of the recorded " + std::to_string(thickness) +
                                 " mm; the sheetmetal gauge did not survive save/reload");
#if defined(MECHDOG_HAS_ProSmtBodyThicknessValueGet) &&                                            \
    !defined(MECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API)
    if (!loaded.thickness_known)
        throw std::runtime_error("The saved wall body thickness could not be read (" +
                                 planar_wall_gauge_failure(loaded) +
                                 "); the gauge cannot be verified before resizing");
#endif

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
    // R03: with no body API, the loaded wall is measured from its own material
    // extent. The child count is zero here, so the rectangle has no hole or
    // downstream dependency.
    planar_wall_geometry_gauge(loaded, vec(frame["normal"]), thickness, vec(frame["u_axis"]),
                               vec(frame["v_axis"]), child_count);
    if (loaded.geometry_known && fabs(loaded.geometry_span - thickness) > 1e-6)
        throw std::runtime_error("The saved wall spans " + std::to_string(loaded.geometry_span) +
                                 " mm along the normal instead of the recorded " +
                                 std::to_string(thickness) + " mm");

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
    PlanarWallBodies bodies = planar_wall_bodies();
    planar_wall_log_bodies(bodies, "resized");
    log("PLANAR_WALL_RESIZED feature_before=%d feature_after=%d dimensions=%d volume_mm3=%.9f\n",
        wall.id, after_wall.id, dimensions, measured);
    if (after_wall.id != wall.id)
        throw std::runtime_error("The resize changed the wall feature identity (" +
                                 std::to_string(wall.id) + " -> " + std::to_string(after_wall.id) +
                                 ")");
    if (dimensions < PLANAR_WALL_MIN_DIMENSIONS)
        throw std::runtime_error("The resize left the sketch with only " +
                                 std::to_string(dimensions) + " point dimensions");
    if (!bodies.material)
        throw std::runtime_error("The resize left no sheetmetal body carrying geometry");
    planar_wall_require_envelope(envelope, length, width, thickness, negative, "resized");
    if (bodies.thickness_known && fabs(bodies.thickness - thickness) > 1e-6)
        throw std::runtime_error("The resized wall carries " + std::to_string(bodies.thickness) +
                                 " mm instead of the recorded " + std::to_string(thickness) +
                                 " mm; the in-place resize changed the gauge");
    // R03: the resized wall is a pure rectangle with no downstream feature, so
    // its own material extent can stand in for the missing body API.
    planar_wall_geometry_gauge(bodies, vec(frame["normal"]), thickness, vec(frame["u_axis"]),
                               vec(frame["v_axis"]), 0);
    if (bodies.geometry_known && fabs(bodies.geometry_span - thickness) > 1e-6)
        throw std::runtime_error("The resized wall spans " + std::to_string(bodies.geometry_span) +
                                 " mm along the normal instead of the recorded " +
                                 std::to_string(thickness) + " mm");

    aliases[label]["planar_wall"]["length"] = length;
    aliases[label]["planar_wall"]["width"] = width;
    stage_operation_result(
        {{"op", "resize_sheetmetal_planar_wall"},
         {"feature", label},
         {"feature_id", after_wall.id},
         {"feature_id_before", wall.id},
         {"sketch", sketch_name},
         {"length", length},
         {"width", width},
         {"thickness", thickness},
         {"direction", negative ? "negative" : "positive"},
         {"square", fabs(length - width) <= 1e-9},
         {"dimension_count", dimensions},
         {"volume_mm3", measured},
         {"frame", frame},
         {"envelope", envelope},
         {"bounds_mm", bounds},
         {"sheetmetal_body", bodies.sheetmetal > 0},
         {"sheetmetal_bodies", bodies.sheetmetal},
         {"material_bodies", bodies.material},
         {"thickness_source", record.value("thickness_source", "parameter")},
         {"thickness_measured_mm", bodies.thickness_known ? J(bodies.thickness) : J(nullptr)},
         {"thickness_verified", bodies.thickness_known},
         {"thickness_body_code", bodies.thickness_code},
         {"thickness_geometry_span_mm",
          bodies.geometry_known ? J(bodies.geometry_span) : J(nullptr)},
         {"thickness_loaded_mm", loaded.thickness_known ? J(loaded.thickness) : J(nullptr)},
         {"thickness_loaded_geometry_span_mm",
          loaded.geometry_known ? J(loaded.geometry_span) : J(nullptr)},
         {"wall_created_this_job", created_this_job},
         {"thickness_validation",
          planar_wall_thickness_validation(bodies, thickness, "current_plan")},
         {"thickness_loaded_validation",
          planar_wall_thickness_validation(loaded, thickness, loaded_context)},
         {"body_linked", bodies.linked_known ? J(bodies.linked) : J(nullptr)}});
}
