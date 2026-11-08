// surface_curvature.cpp — DEV-074/H08: numerical curvature and G1 analysis for
// the member faces of one quilt.
//
// Context: Creo Toolkit has no zebra-stripe or curvature-comb visualization API
// (2026-11-08 SDK re-check). The equivalent deliverable is numeric: principal
// curvatures from ProSurfacePrincipalCrvtEval at a bounded UV raster, and the
// normal angle across a shared edge sampled with ProSurfaceXyzdataEval. Nothing
// here draws a picture, and nothing is inferred from area or volume.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §4.4.1 (every value ships
// its unit context, a failure never fabricates zero, an unknown unit scale
// keeps the mm value null) and §4.9 (the fields frozen for this module).
//
// Note on the parameter range: this SDK has no ProSurfaceParamRangeGet. The UV
// extents come from the kernel's own surface data
// (ProSurfaceDataGet -> ProSurfacedata.uv_min/uv_max), and every sample is
// checked against the trimmed face with ProSurfaceUvpntVerify so points outside
// the face contour are counted, not measured.
//
// This file is included by generic.cpp after the shared measurement helpers;
// it defines no entry point of its own beyond generic_surface_curvature.
#include <ProContour.h>
#include <ProEdge.h>
#include <ProSurface.h>
#include <ProUvStat.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <vector>

// Sampling bounds are explicit: a density outside 5..50 is refused before a
// job exists, and the G1 seam is sampled at a fixed 17 points.
static constexpr int SURFACE_CURVATURE_MIN_DENSITY = 5;
static constexpr int SURFACE_CURVATURE_MAX_DENSITY = 50;
static constexpr int SURFACE_CURVATURE_G1_SAMPLES = 17;
static constexpr double SURFACE_CURVATURE_G1_THRESHOLD_DEG = 0.5;
static constexpr double SURFACE_CURVATURE_ZERO_CURVATURE = 1e-12;

struct CurvatureMember {
    ProSurface surface = nullptr;
    int surface_id = -1;
};

struct CurvatureMembers {
    std::vector<CurvatureMember> members;
    bool visit_ok = true;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
};

static ProError curvature_member_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *members = (CurvatureMembers *)data;
    if (status || !surface) {
        members->visit_ok = false;
        if (!members->query_code && status)
            members->query_code = status;
        if (!members->reason)
            members->reason = "quilt_surface_visit_failed";
        return PRO_TK_NO_ERROR;
    }
    CurvatureMember member;
    member.surface = surface;
    if (ProSurfaceIdGet(surface, &member.surface_id))
        member.surface_id = -1;
    members->members.push_back(member);
    return PRO_TK_NO_ERROR;
}

static CurvatureMembers curvature_members(ProQuilt quilt) {
    CurvatureMembers members;
    ProError code = ProQuiltSurfaceVisit(quilt, curvature_member_cb, nullptr, &members);
    if (code == PRO_TK_E_NOT_FOUND) {
        members.visit_ok = false;
        members.query_code = code;
        members.reason = "quilt_has_no_surfaces";
    } else if (code) {
        members.visit_ok = false;
        members.query_code = code;
        members.reason = "quilt_surface_visit_failed";
    }
    return members;
}

// The kernel's own UV extents of the underlying surface geometry. A missing or
// degenerate range is a failure with a reason, never a guessed 0..1 box.
struct CurvatureUvRange {
    bool available = false;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
    double u_min = 0.0;
    double u_max = 0.0;
    double v_min = 0.0;
    double v_max = 0.0;
};

static CurvatureUvRange curvature_uv_range(ProSurface surface) {
    CurvatureUvRange range;
    ProGeomitemdata *data = nullptr;
    range.query_code = ProSurfaceDataGet(surface, &data);
    if (range.query_code || !data || !data->data.p_surface_data) {
        if (!range.query_code)
            range.query_code = PRO_TK_GENERAL_ERROR;
        range.reason = "surface_data_get_failed";
        if (data)
            ProGeomitemdataFree(&data);
        return range;
    }
    const ProSurfacedata *surface_data = data->data.p_surface_data;
    range.u_min = surface_data->uv_min[0];
    range.u_max = surface_data->uv_max[0];
    range.v_min = surface_data->uv_min[1];
    range.v_max = surface_data->uv_max[1];
    ProGeomitemdataFree(&data);
    const bool finite = std::isfinite(range.u_min) && std::isfinite(range.u_max) &&
                        std::isfinite(range.v_min) && std::isfinite(range.v_max);
    if (!finite || !(range.u_max > range.u_min) || !(range.v_max > range.v_min)) {
        range.query_code = PRO_TK_GENERAL_ERROR;
        range.reason = "surface_uv_range_unavailable";
        return range;
    }
    range.available = true;
    return range;
}

struct CurvatureFaceSummary {
    bool available = false;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
    int sample_count = 0;
    int failure_count = 0;
    int outside_count = 0;
    bool values_available = false;
    double max_abs_curvature_native = 0.0;
    bool radius_available = false;
    double min_curvature_radius_native = 0.0;
};

// One face's raster. Points are sampled at cell centres so a sample never sits
// on the UV box corner; only samples that pass ProSurfaceUvpntVerify are
// evaluated. An outside point is a count, a failed evaluation is a failure,
// and neither becomes a zero curvature.
static J curvature_face_block(ProSolid solid, const CurvatureMember &member, int density,
                              const InspectionLengthUnits &units, const MillimeterScale &scale,
                              CurvatureFaceSummary &out) {
    CurvatureUvRange range = curvature_uv_range(member.surface);
    J points = J::array();
    double max_abs = 0.0;
    bool has_radius = false;
    double min_radius = 0.0;
    ProError first_failure = PRO_TK_NO_ERROR;

    if (range.available) {
        const double du = (range.u_max - range.u_min) / (double)density;
        const double dv = (range.v_max - range.v_min) / (double)density;
        for (int iu = 0; iu < density; iu++) {
            for (int iv = 0; iv < density; iv++) {
                ProUvParam uv = {range.u_min + ((double)iu + 0.5) * du,
                                 range.v_min + ((double)iv + 0.5) * dv};
                ProUvStatus uv_status = PRO_UV_OUTSIDE;
                ProError verify = ProSurfaceUvpntVerify(solid, member.surface, uv, &uv_status);
                if (verify) {
                    out.failure_count++;
                    if (!first_failure)
                        first_failure = verify;
                    continue;
                }
                if (uv_status != PRO_UV_INSIDE) {
                    out.outside_count++;
                    continue;
                }
                double max_curvature = 0.0;
                double min_curvature = 0.0;
                ProVector directions[2] = {{0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}};
                ProError eval_code = ProSurfacePrincipalCrvtEval(member.surface, uv, &max_curvature,
                                                                 &min_curvature, directions);
                if (eval_code || !std::isfinite(max_curvature) || !std::isfinite(min_curvature)) {
                    out.failure_count++;
                    if (!first_failure)
                        first_failure = eval_code ? eval_code : PRO_TK_GENERAL_ERROR;
                    continue;
                }
                out.sample_count++;
                const double abs_max = std::max(std::fabs(max_curvature), std::fabs(min_curvature));
                max_abs = std::max(max_abs, abs_max);
                if (abs_max > SURFACE_CURVATURE_ZERO_CURVATURE) {
                    const double radius = 1.0 / abs_max;
                    if (!has_radius || radius < min_radius) {
                        min_radius = radius;
                        has_radius = true;
                    }
                }
                MeasurementOutcome point_outcome;
                point_outcome.available = scale.known;
                point_outcome.reason = scale.known ? nullptr : "unit_scale_unknown";
                J point_status = measurement_status_json(point_outcome, units, scale);
                point_status["curvature_unit"] = "1/mm";
                point_status["radius_unit"] = "mm";
                const bool max_radius_known =
                    scale.known && std::fabs(max_curvature) > SURFACE_CURVATURE_ZERO_CURVATURE;
                const bool min_radius_known =
                    scale.known && std::fabs(min_curvature) > SURFACE_CURVATURE_ZERO_CURVATURE;
                J point = {
                    {"u", uv[0]},
                    {"v", uv[1]},
                    {"max_curvature_per_mm",
                     scale.known ? J(max_curvature / scale.scale) : J(nullptr)},
                    {"min_curvature_per_mm",
                     scale.known ? J(min_curvature / scale.scale) : J(nullptr)},
                    {"max_radius_mm",
                     max_radius_known ? J(scale.scale / std::fabs(max_curvature)) : J(nullptr)},
                    {"min_radius_mm",
                     min_radius_known ? J(scale.scale / std::fabs(min_curvature)) : J(nullptr)},
                    {"max_direction",
                     J::array({directions[0][0], directions[0][1], directions[0][2]})},
                    {"min_direction",
                     J::array({directions[1][0], directions[1][1], directions[1][2]})},
                    {"status", point_status}};
                points.push_back(point);
            }
        }
    }

    out.available = range.available && out.sample_count > 0;
    out.query_code = range.available ? first_failure : range.query_code;
    out.reason = !range.available        ? range.reason
                 : out.sample_count > 0  ? nullptr
                 : out.failure_count > 0 ? "principal_curvature_eval_failed"
                                         : "no_curvature_samples_inside_face";
    out.values_available = out.available && scale.known;
    out.max_abs_curvature_native = max_abs;
    out.radius_available = out.values_available && has_radius;
    out.min_curvature_radius_native = min_radius;

    MeasurementOutcome range_outcome;
    range_outcome.available = range.available;
    range_outcome.query_code = range.query_code;
    range_outcome.reason = range.available ? nullptr : range.reason;
    J range_status = measurement_status_json(range_outcome, units, scale);
    range_status["uv_range_order"] = "u_min,u_max,v_min,v_max";

    MeasurementOutcome face_outcome;
    face_outcome.available = out.available;
    face_outcome.query_code = out.query_code;
    face_outcome.reason = out.reason;
    J face_status = measurement_status_json(face_outcome, units, scale);
    face_status["curvature_unit"] = "1/mm";
    face_status["radius_unit"] = "mm";
    face_status["samples_per_direction"] = density;
    face_status["sampled_point_count"] = range.available ? J(density * density) : J(nullptr);

    MeasurementOutcome value_outcome;
    value_outcome.available = out.values_available;
    value_outcome.query_code = out.query_code;
    value_outcome.reason = !scale.known ? "unit_scale_unknown" : out.reason;
    value_outcome.value = max_abs;
    J value_status = measurement_status_json(value_outcome, units, scale);
    value_status["curvature_unit"] = "1/mm";

    MeasurementOutcome radius_outcome;
    radius_outcome.available = out.radius_available;
    radius_outcome.query_code = out.query_code;
    radius_outcome.reason = !scale.known                   ? "unit_scale_unknown"
                            : out.available && !has_radius ? "zero_curvature"
                                                           : out.reason;
    radius_outcome.value = min_radius;
    J radius_status = measurement_status_json(radius_outcome, units, scale);
    radius_status["radius_unit"] = "mm";

    return {{"surface_id", member.surface_id},
            {"uv_range_mm_surface_parameters",
             range.available ? J::array({range.u_min, range.u_max, range.v_min, range.v_max})
                             : J(nullptr)},
            {"uv_range_status", range_status},
            {"status", face_status},
            {"sample_count", range.available ? J(out.sample_count) : J(nullptr)},
            {"failure_count", range.available ? J(out.failure_count) : J(nullptr)},
            {"outside_contour_count", range.available ? J(out.outside_count) : J(nullptr)},
            {"max_abs_curvature_per_mm",
             value_outcome.available ? J(max_abs / scale.scale) : J(nullptr)},
            {"max_abs_curvature_status", value_status},
            {"min_curvature_radius_mm",
             radius_outcome.available ? J(min_radius * scale.scale) : J(nullptr)},
            {"min_curvature_radius_status", radius_status},
            {"points", points}};
}

struct CurvatureEdge {
    long long key = 0;
    ProEdge edge = nullptr;
};

struct CurvatureEdgeContext {
    std::vector<CurvatureEdge> *edges = nullptr;
};

static ProError curvature_edge_cb(ProEdge edge, ProError status, ProAppData data) {
    auto *context = (CurvatureEdgeContext *)data;
    if (status || !edge || !context || !context->edges)
        return PRO_TK_NO_ERROR;
    int edge_id = -1;
    ProError code = ProEdgeIdGet(edge, &edge_id);
    // Edge ids are unique in a part; when the SDK cannot name one, the handle
    // itself identifies the same edge on two faces.
    const long long key =
        (!code && edge_id >= 0) ? (long long)edge_id : -(long long)(intptr_t)edge - 1;
    context->edges->push_back({key, edge});
    return PRO_TK_NO_ERROR;
}

struct CurvatureContourContext {
    std::vector<CurvatureEdge> *edges = nullptr;
    ProSurface surface = nullptr;
};

static ProError curvature_contour_cb(ProContour contour, ProError status, ProAppData data) {
    auto *context = (CurvatureContourContext *)data;
    if (status || !context || !context->edges)
        return PRO_TK_NO_ERROR;
    ProError code =
        ProContourEdgeVisit(context->surface, contour, curvature_edge_cb, nullptr, context);
    if (code && code != PRO_TK_E_NOT_FOUND)
        return PRO_TK_NO_ERROR;
    return PRO_TK_NO_ERROR;
}

static bool curvature_face_edges(ProSurface surface, std::vector<CurvatureEdge> &edges,
                                 ProError &code) {
    edges.clear();
    CurvatureContourContext context;
    context.edges = &edges;
    context.surface = surface;
    code = ProSurfaceContourVisit(surface, curvature_contour_cb, nullptr, &context);
    if (code == PRO_TK_E_NOT_FOUND) {
        code = PRO_TK_NO_ERROR;
        return !edges.empty();
    }
    return code == PRO_TK_NO_ERROR && !edges.empty();
}

// One unit normal and its UV on one face at a 3D point. ProSurfaceParamEval
// returns the closest UV on the geometric surface, which is what a seam point
// needs; the caller does not claim the point is interior.
static bool curvature_normal_at(ProSolid solid, ProSurface surface, const ProVector &point,
                                ProVector normal, ProUvParam uv_out, ProError &code) {
    ProUvParam uv = {0.0, 0.0};
    code = ProSurfaceParamEval(solid, surface, (double *)point, uv);
    if (code)
        return false;
    ProVector xyz = {0.0, 0.0, 0.0};
    ProVector deriv1[2] = {};
    ProVector deriv2[3] = {};
    code = ProSurfaceXyzdataEval(surface, uv, xyz, deriv1, deriv2, normal);
    if (code)
        return false;
    const double length =
        std::sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]);
    if (!(length > 1e-12)) {
        code = PRO_TK_GENERAL_ERROR;
        return false;
    }
    for (int i = 0; i < 3; i++)
        normal[i] /= length;
    uv_out[0] = uv[0];
    uv_out[1] = uv[1];
    return true;
}

struct CurvatureG1Summary {
    bool available = false;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
    int shared_edge_count = 0;
    int sample_count = 0;
    int failure_count = 0;
    double max_angle_deg = 0.0;
    J points = J::array();
};

static J curvature_g1_block(ProSolid solid, const CurvatureMember &first,
                            const CurvatureMember &second, const MillimeterScale &scale,
                            const InspectionLengthUnits &units, CurvatureG1Summary &out) {
    std::vector<CurvatureEdge> first_edges;
    std::vector<CurvatureEdge> second_edges;
    ProError first_code = PRO_TK_NO_ERROR;
    ProError second_code = PRO_TK_NO_ERROR;
    const bool first_ok = curvature_face_edges(first.surface, first_edges, first_code);
    const bool second_ok = curvature_face_edges(second.surface, second_edges, second_code);
    if (!first_ok || !second_ok) {
        out.query_code = !first_ok ? first_code : second_code;
        out.reason = "boundary_edge_visit_failed";
        return J::array();
    }
    std::map<long long, ProEdge> second_by_key;
    for (const auto &edge : second_edges)
        second_by_key[edge.key] = edge.edge;

    ProError first_failure = PRO_TK_NO_ERROR;
    for (const auto &edge : first_edges) {
        auto found = second_by_key.find(edge.key);
        if (found == second_by_key.end())
            continue;
        out.shared_edge_count++;
        for (int index = 0; index < SURFACE_CURVATURE_G1_SAMPLES; index++) {
            const double parameter = (double)index / (double)(SURFACE_CURVATURE_G1_SAMPLES - 1);
            ProVector point = {0.0, 0.0, 0.0};
            ProVector deriv1 = {0.0, 0.0, 0.0};
            ProVector deriv2 = {0.0, 0.0, 0.0};
            ProVector direction = {0.0, 0.0, 0.0};
            ProError edge_code =
                ProEdgeXyzdataEval(edge.edge, parameter, point, deriv1, deriv2, direction);
            if (edge_code) {
                out.failure_count++;
                if (!first_failure)
                    first_failure = edge_code;
                continue;
            }
            ProVector first_normal = {0.0, 0.0, 0.0};
            ProVector second_normal = {0.0, 0.0, 0.0};
            ProUvParam first_uv = {0.0, 0.0};
            ProUvParam second_uv = {0.0, 0.0};
            ProError normal_code = PRO_TK_NO_ERROR;
            const bool first_normal_ok = curvature_normal_at(solid, first.surface, point,
                                                             first_normal, first_uv, normal_code);
            if (!first_normal_ok) {
                out.failure_count++;
                if (!first_failure)
                    first_failure = normal_code;
                continue;
            }
            const bool second_normal_ok = curvature_normal_at(
                solid, second.surface, point, second_normal, second_uv, normal_code);
            if (!second_normal_ok) {
                out.failure_count++;
                if (!first_failure)
                    first_failure = normal_code;
                continue;
            }
            double dot = first_normal[0] * second_normal[0] + first_normal[1] * second_normal[1] +
                         first_normal[2] * second_normal[2];
            dot = std::max(-1.0, std::min(1.0, dot));
            const double angle = std::acos(dot) * RADIANS_TO_DEGREES;
            out.sample_count++;
            out.max_angle_deg = std::max(out.max_angle_deg, angle);
            out.points.push_back({{"edge_id", edge.key >= 0 ? J(edge.key) : J(nullptr)},
                                  {"edge_parameter", parameter},
                                  {"point_mm", xyz_json(point, scale)},
                                  {"first_uv", J::array({first_uv[0], first_uv[1]})},
                                  {"second_uv", J::array({second_uv[0], second_uv[1]})},
                                  {"angle_deg", angle}});
        }
    }
    out.query_code = first_failure;
    out.available = out.shared_edge_count > 0 && out.sample_count > 0;
    out.reason = out.shared_edge_count == 0 ? "no_shared_edge"
                 : out.sample_count == 0    ? "g1_sampling_failed"
                                            : nullptr;
    return out.points;
}

static J surface_curvature_receipt(ProSolid solid, int quilt_id, const CurvatureMembers &members,
                                   const std::vector<int> &face_indices, int density,
                                   const InspectionLengthUnits &units,
                                   const MillimeterScale &scale) {
    const bool scaled = scale.known;
    J faces = J::array();
    double global_max_abs = 0.0;
    bool global_has_radius = false;
    double global_min_radius = 0.0;
    bool any_face_available = false;
    int total_samples = 0;
    int total_failures = 0;
    ProError first_face_code = PRO_TK_NO_ERROR;

    for (int index : face_indices) {
        CurvatureFaceSummary summary;
        J block =
            curvature_face_block(solid, members.members[index], density, units, scale, summary);
        faces.push_back(block);
        if (summary.available) {
            if (any_face_available) {
                global_max_abs = std::max(global_max_abs, summary.max_abs_curvature_native);
            } else {
                global_max_abs = summary.max_abs_curvature_native;
            }
            if (summary.radius_available) {
                if (!global_has_radius || summary.min_curvature_radius_native < global_min_radius)
                    global_min_radius = summary.min_curvature_radius_native;
                global_has_radius = true;
            }
            any_face_available = true;
        }
        total_samples += summary.sample_count;
        total_failures += summary.failure_count;
        if (!first_face_code && summary.query_code)
            first_face_code = summary.query_code;
    }

    MeasurementOutcome summary_outcome;
    summary_outcome.available = any_face_available && scaled;
    summary_outcome.query_code = first_face_code;
    summary_outcome.reason = !any_face_available
                                 ? (total_failures > 0 ? "principal_curvature_eval_failed"
                                                       : "no_curvature_samples_inside_face")
                             : !scaled ? "unit_scale_unknown"
                                       : nullptr;
    summary_outcome.value = global_max_abs;
    J summary_status = measurement_status_json(summary_outcome, units, scale);
    summary_status["curvature_unit"] = "1/mm";
    summary_status["face_count"] = (int)face_indices.size();

    MeasurementOutcome radius_outcome;
    radius_outcome.available = any_face_available && scaled && global_has_radius;
    radius_outcome.query_code = first_face_code;
    radius_outcome.reason = !any_face_available
                                ? (total_failures > 0 ? "principal_curvature_eval_failed"
                                                      : "no_curvature_samples_inside_face")
                            : !scaled            ? "unit_scale_unknown"
                            : !global_has_radius ? "zero_curvature"
                                                 : nullptr;
    radius_outcome.value = global_min_radius;
    J radius_status = measurement_status_json(radius_outcome, units, scale);
    radius_status["radius_unit"] = "mm";

    CurvatureG1Summary g1;
    J g1_points = J::array();
    if (face_indices.size() == 2) {
        g1_points = curvature_g1_block(solid, members.members[face_indices[0]],
                                       members.members[face_indices[1]], scale, units, g1);
    } else {
        g1.reason = "two_faces_required";
    }
    MeasurementOutcome g1_outcome;
    g1_outcome.available = g1.available;
    g1_outcome.query_code = g1.query_code;
    g1_outcome.reason = g1.available ? nullptr : g1.reason;
    J g1_status = measurement_status_json(g1_outcome, units, scale);
    g1_status["angle_unit"] = "deg";
    g1_status["threshold_deg"] = SURFACE_CURVATURE_G1_THRESHOLD_DEG;
    g1_status["shared_edge_count"] =
        face_indices.size() == 2 && !g1.reason ? J(g1.shared_edge_count) : J(nullptr);
    g1_status["sample_count"] =
        face_indices.size() == 2 && g1.available ? J(g1.sample_count) : J(nullptr);
    g1_status["failure_count"] =
        face_indices.size() == 2 && g1.available ? J(g1.failure_count) : J(nullptr);

    J summary = {{"max_abs_curvature_per_mm",
                  summary_outcome.available ? J(global_max_abs / scale.scale) : J(nullptr)},
                 {"max_abs_curvature_status", summary_status},
                 {"min_curvature_radius_mm",
                  radius_outcome.available ? J(global_min_radius * scale.scale) : J(nullptr)},
                 {"min_curvature_radius_status", radius_status},
                 {"sample_count", any_face_available ? J(total_samples) : J(nullptr)},
                 {"failure_count", any_face_available ? J(total_failures) : J(nullptr)},
                 {"face_count", (int)face_indices.size()}};

    return {{"unit_name", units.length.name[0] ? J(utf8(units.length.name)) : J(nullptr)},
            {"length_scale_to_mm", scaled ? J(scale.scale) : J(nullptr)},
            {"quilt_id", quilt_id},
            {"samples_per_direction", density},
            {"curvature_unit", "1/mm"},
            {"radius_unit", "mm"},
            {"faces", faces},
            {"summary", summary},
            {"g1_max_angle_deg", g1_outcome.available ? J(g1.max_angle_deg) : J(nullptr)},
            {"g1_status", g1_status},
            {"g1_threshold_deg", SURFACE_CURVATURE_G1_THRESHOLD_DEG},
            {"within_g1", g1_outcome.available
                              ? J(g1.max_angle_deg <= SURFACE_CURVATURE_G1_THRESHOLD_DEG)
                              : J(nullptr)},
            {"g1_points", g1_points}};
}

static void generic_surface_curvature(const J &op) {
    const J &faces = op.at("faces");
    if (!faces.is_array() || faces.empty() || faces.size() > 2)
        throw std::runtime_error("surface_curvature requires one or two member faces as "
                                 "{kind:\"surface\",id:N} or a zero-based member index");

    const J &raw_density =
        op.contains("samples_per_direction") ? op.at("samples_per_direction") : J(12);
    if (!raw_density.is_number_integer())
        throw std::runtime_error("surface_curvature samples_per_direction must be an integer");
    const int density = raw_density.get<int>();
    if (density < SURFACE_CURVATURE_MIN_DENSITY || density > SURFACE_CURVATURE_MAX_DENSITY)
        throw std::runtime_error(
            "surface_curvature samples_per_direction must be between 5 and 50");

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    ProSelection target = resolve_quilt_reference(op.at("target"), (ProSolid)board, units, scale);
    const int quilt_id = quilt_selection_id(target);
    ProSelectionFree(&target);
    ProQuilt quilt = nullptr;
    ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
    if (init_code)
        throw std::runtime_error("surface_curvature target quilt " + std::to_string(quilt_id) +
                                 " could not be initialised (code " +
                                 std::to_string((int)init_code) + ")");
    CurvatureMembers members = curvature_members(quilt);
    if (!members.visit_ok || members.query_code || members.members.empty())
        throw std::runtime_error(
            std::string("surface_curvature could not read the quilt member faces") +
            (members.reason ? ": " + std::string(members.reason) : ""));

    std::vector<int> face_indices;
    for (const auto &reference : faces) {
        int index = -1;
        if (reference.is_number_integer()) {
            const long long raw = reference.get<long long>();
            if (raw < 0 || raw >= (long long)members.members.size())
                throw std::runtime_error("surface_curvature member index " + std::to_string(raw) +
                                         " is outside the quilt's " +
                                         std::to_string(members.members.size()) + " member faces");
            index = (int)raw;
        } else if (reference.is_object()) {
            if (!reference.contains("kind") || reference.at("kind") != "surface")
                throw std::runtime_error(
                    "surface_curvature faces must be {kind:\"surface\",id:N} or a member index");
            const J &raw_id = reference.at("id");
            if (!raw_id.is_number_integer() || raw_id < 0 || raw_id > 2147483647)
                throw std::runtime_error(
                    "surface_curvature face id must be a nonnegative 32-bit integer");
            const int surface_id = raw_id.get<int>();
            for (size_t position = 0; position < members.members.size(); position++) {
                if (members.members[position].surface_id == surface_id) {
                    index = (int)position;
                    break;
                }
            }
            if (index < 0)
                throw std::runtime_error("surface_curvature face " + std::to_string(surface_id) +
                                         " is not a member of quilt " + std::to_string(quilt_id));
        } else {
            throw std::runtime_error(
                "surface_curvature faces must be {kind:\"surface\",id:N} or a member index");
        }
        if (std::find(face_indices.begin(), face_indices.end(), index) != face_indices.end())
            throw std::runtime_error("surface_curvature faces must be two different member faces");
        face_indices.push_back(index);
    }

    J details = surface_curvature_receipt((ProSolid)board, quilt_id, members, face_indices, density,
                                          units, scale);
    details["op"] = "surface_curvature";
    stage_operation_result(details);

    // A read-only query that sampled nothing is a failure: success with a shape
    // of nulls would hide that no curvature was read. An unknown unit scale is
    // not a sampling failure (directions and counts are still real), so it
    // keeps the success receipt with null mm values.
    const J &summary_status = details["summary"]["max_abs_curvature_status"];
    const bool sampled = !(summary_status["reason"] == "no_curvature_samples_inside_face" ||
                           summary_status["reason"] == "principal_curvature_eval_failed");
    if (!sampled)
        throw std::runtime_error("surface_curvature could not sample any member face: " +
                                 (summary_status["reason"].is_string()
                                      ? summary_status["reason"].get<std::string>()
                                      : std::string("no_curvature_samples")));
}
