// surface_measure.h — FEAT-039/S01: the single home of quilt and curve
// measurement helpers shared by quilt_query.h and the surface-chain feature
// modules (surface_trim, quilt_merge, project_curve, quilt_offset,
// boundary_blend). The G5 contract (docs/development/G5-NATIVE-CONTRACT.md
// §4.4.1/§4.4.2/§4.7) freezes the rules implemented here: every value ships
// its unit context, a failure never fabricates zero, and an unknown unit
// scale keeps the mm value null with reason "unit_scale_unknown".
//
// This header is included by generic.cpp after the shared geometry helpers
// (selection, CK, utf8) and J are visible; it defines no entry point.
#pragma once

#include "assembly_units.h"
#include "inspection_units.h"

#include <ProContour.h>
#include <ProCurve.h>
#include <ProQuilt.h>
#include <ProSurface.h>

#include <algorithm>
#include <cmath>
#include <limits>

// One measurement outcome: the native-unit value plus the honest status that
// goes with it. available=false always carries a reason and a query code.
struct MeasurementOutcome {
    bool available = false;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
    double value = 0.0; // native units; meaningless unless available
};

// §4.4.1: every measurement ships its unit context so the Python side can
// tell "measured zero" apart from "could not measure".
static J measurement_status_json(const MeasurementOutcome &outcome,
                                 const InspectionLengthUnits &units, const MillimeterScale &scale) {
    return {{"available", outcome.available},
            {"reason", outcome.reason ? J(outcome.reason) : J(nullptr)},
            {"query_code", (int)outcome.query_code},
            {"scale_to_mm_known", scale.known},
            {"unit_name", units.length.name[0] ? J(utf8(units.length.name)) : J(nullptr)}};
}

// Trimmed-surface area: external contour area minus internal ones
// (ProContourAreaEval; the enclosing loop is the external traversal).
struct SurfaceContourAccumulator {
    ProSurface surface = nullptr;
    double area = 0.0;
    bool ok = true;
    ProError code = PRO_TK_NO_ERROR;
};
static ProError contour_area_cb(ProContour contour, ProError status, ProAppData data) {
    auto *acc = (SurfaceContourAccumulator *)data;
    ProContourTraversal traversal = PRO_CONTOUR_TRAV_EXTERNAL;
    double area = 0.0;
    if (status || ProContourTraversalGet(contour, &traversal) ||
        ProContourAreaEval(acc->surface, contour, &area)) {
        acc->ok = false;
        if (!acc->code)
            acc->code = status ? status : PRO_TK_GENERAL_ERROR;
        return PRO_TK_NO_ERROR;
    }
    acc->area += traversal == PRO_CONTOUR_TRAV_EXTERNAL ? area : -area;
    return PRO_TK_NO_ERROR;
}

// One member face of a quilt. A negative net (a hole without an enclosing
// external loop) is reported as a failure instead of a signed area.
static MeasurementOutcome surface_area_native(ProSurface surface) {
    SurfaceContourAccumulator acc;
    acc.surface = surface;
    ProError code = ProSurfaceContourVisit(surface, contour_area_cb, nullptr, &acc);
    MeasurementOutcome out;
    out.query_code = code ? code : (acc.ok ? PRO_TK_NO_ERROR : acc.code);
    if (out.query_code) {
        out.reason = "contour_area_eval_failed";
        return out;
    }
    if (acc.area < 0.0) {
        out.reason = "negative_net_contour_area";
        return out;
    }
    out.available = true;
    out.value = acc.area;
    return out;
}

struct QuiltAreaAccumulator {
    double area = 0.0;
    int surface_count = 0;
    bool ok = true;
    ProError code = PRO_TK_NO_ERROR;
};
static ProError quilt_area_surface_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *acc = (QuiltAreaAccumulator *)data;
    if (status) {
        acc->ok = false;
        acc->code = status;
        return PRO_TK_NO_ERROR;
    }
    MeasurementOutcome per = surface_area_native(surface);
    if (!per.available) {
        acc->ok = false;
        acc->code = per.query_code;
        return PRO_TK_NO_ERROR;
    }
    acc->surface_count++;
    acc->area += per.value;
    return PRO_TK_NO_ERROR;
}

// Real quilt area: the sum of the member faces' trimmed areas, in native
// units. Empty quilts and per-face failures are failures, never zero.
static MeasurementOutcome quilt_area_native(ProQuilt quilt) {
    QuiltAreaAccumulator acc;
    ProError code = ProQuiltSurfaceVisit(quilt, quilt_area_surface_cb, nullptr, &acc);
    MeasurementOutcome out;
    if (code == PRO_TK_E_NOT_FOUND) {
        out.reason = "quilt_has_no_surfaces";
        return out;
    }
    if (code) {
        out.query_code = code;
        out.reason = "quilt_surface_visit_failed";
        return out;
    }
    if (!acc.ok) {
        out.query_code = acc.code;
        out.reason = "contour_area_eval_failed";
        return out;
    }
    out.available = true;
    out.value = acc.area;
    return out;
}

// Closure probe shared by every quilt consumer (S01 quilts, S03 merge).
// ProQuiltVolumeEval answers only for a closed quilt; an open one reports
// PRO_TK_INVALID_TYPE, and any other failure stays unknown instead of false.
static MeasurementOutcome quilt_closed_native(ProQuilt quilt) {
    MeasurementOutcome out;
    double volume = 0.0;
    out.query_code = ProQuiltVolumeEval(quilt, &volume);
    if (out.query_code == PRO_TK_NO_ERROR) {
        out.available = true;
        out.value = volume;
        return out;
    }
    out.reason =
        out.query_code == PRO_TK_INVALID_TYPE ? "quilt_is_open" : "quilt_volume_eval_failed";
    return out;
}

// true only when the probe explicitly reported an open quilt. Decided from the
// query code: comparing the reason char* with a literal is a pointer compare
// and silently returns false whenever the compiler does not pool the literals.
static bool quilt_closed_is_open(const MeasurementOutcome &closed) {
    return !closed.available && closed.query_code == PRO_TK_INVALID_TYPE;
}

// Curve length in native units (ProCurveLengthEval).
static MeasurementOutcome curve_length_native(ProCurve curve) {
    MeasurementOutcome out;
    double length = 0.0;
    out.query_code = ProCurveLengthEval(curve, &length);
    if (out.query_code) {
        out.reason = "curve_length_eval_failed";
        return out;
    }
    out.available = true;
    out.value = length;
    return out;
}

// Endpoints in native units. The curve parameter is normalized, so the ends
// sit at 0.0 and 1.0 (ProCurveXyzdataEval contract). The derivative outputs are
// always NULL: ProCurveXyzdataEval answers PRO_TK_NOT_IMPLEMENTED for a
// composite curve (a sketch's own edge loop) whenever either derivative array
// is passed, and endpoints never need them (live 2026-11-04, S04 probe).
static ProVector curve_endpoint_start{};
static ProVector curve_endpoint_end{};
static MeasurementOutcome curve_endpoints_native(ProCurve curve) {
    MeasurementOutcome out;
    ProVector start = {};
    ProVector end = {};
    out.query_code = ProCurveXyzdataEval(curve, 0.0, start, nullptr, nullptr);
    if (out.query_code) {
        out.reason = "curve_endpoint_eval_failed";
        return out;
    }
    out.query_code = ProCurveXyzdataEval(curve, 1.0, end, nullptr, nullptr);
    if (out.query_code) {
        out.reason = "curve_endpoint_eval_failed";
        return out;
    }
    out.available = true;
    out.value = 0.0;
    // ProVector is a plain double[3]; carry the endpoints out for the J
    // wrapper, which applies the unit scale.
    for (int i = 0; i < 3; i++) {
        curve_endpoint_start[i] = start[i];
        curve_endpoint_end[i] = end[i];
    }
    return out;
}

static J xyz_json(const ProVector &point, const MillimeterScale &scale) {
    if (!scale.known)
        return nullptr;
    return {point[0] * scale.scale, point[1] * scale.scale, point[2] * scale.scale};
}

// §4.4.2 area projection: mm² only when the length scale is known.
static J area_mm2_json(const MeasurementOutcome &area, const InspectionLengthUnits &units,
                       const MillimeterScale &scale) {
    return {{"area_mm2", area.available && scale.known ? J(area.value * scale.scale * scale.scale)
                                                       : J(nullptr)},
            {"area_status", measurement_status_json(area, units, scale)}};
}

// §4.4.2 area projection under a caller-chosen field pair (surface_trim uses
// area_before/area_after, quilt_merge uses input_area/area). Only the keys
// change; the status structure and the "measured zero is not unknown" rule
// stay in one place.
static J area_fields_json(const MeasurementOutcome &area, const InspectionLengthUnits &units,
                          const MillimeterScale &scale, const char *value_key,
                          const char *status_key) {
    J projected = area_mm2_json(area, units, scale);
    return {{value_key, projected["area_mm2"]}, {status_key, projected["area_status"]}};
}

// §4.4.2 length projection: mm only when the length scale is known.
static J length_mm_json(const MeasurementOutcome &length, const InspectionLengthUnits &units,
                        const MillimeterScale &scale) {
    return {
        {"length_mm", length.available && scale.known ? J(length.value * scale.scale) : J(nullptr)},
        {"length_status", measurement_status_json(length, units, scale)}};
}

static J curve_endpoints_json(ProCurve curve, const InspectionLengthUnits &units,
                              const MillimeterScale &scale) {
    MeasurementOutcome ends = curve_endpoints_native(curve);
    return {{"endpoints_mm", ends.available && scale.known
                                 ? J(J::array({xyz_json(curve_endpoint_start, scale),
                                               xyz_json(curve_endpoint_end, scale)}))
                                 : J(nullptr)},
            {"endpoints_status", measurement_status_json(ends, units, scale)}};
}

// §4.5 kept-side evidence (DEV-074/H06): the area-weighted centroid, the
// axis-aligned bounds and the world normal of a region, sampled from the
// kernel's own tessellation of every member face. The 2026-11-04 note "no
// quilt centroid query" still holds for the ProQuilt family itself, but
// ProQuiltSurfaceVisit exposes the faces, and ProSurfaceTessellationGet returns
// real vertices/facets for the trimmed face. Nothing is estimated from a
// bounding box: centroid, bounds and normal all come from the same sampled
// triangles. A curved region reports no direction (a mean normal is not a
// normal anywhere) with reason "region_not_planar".
static constexpr double REGION_PLANAR_TOLERANCE_DEG = 0.5;
static constexpr double RADIANS_TO_DEGREES = 57.29577951308232;

struct RegionGeometry {
    bool available = false;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
    bool incomplete_tessellation = false;
    int face_count = 0;
    long long triangle_count = 0;
    double area = 0.0; // sampled triangle area in native units², diagnostic only
    double centroid[3] = {0.0, 0.0, 0.0};
    double bb_min[3] = {0.0, 0.0, 0.0};
    double bb_max[3] = {0.0, 0.0, 0.0};
    double normal[3] = {0.0, 0.0, 0.0};
    bool planar = false;
    double max_normal_deviation_deg = 0.0;
};

struct RegionTessellationAccumulator {
    RegionGeometry region;
    double moment[3] = {0.0, 0.0, 0.0};
    double normal_sum[3] = {0.0, 0.0, 0.0};
    double bb_min[3] = {std::numeric_limits<double>::max(), std::numeric_limits<double>::max(),
                        std::numeric_limits<double>::max()};
    double bb_max[3] = {-std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(),
                        -std::numeric_limits<double>::max()};
    bool has_reference_normal = false;
    double reference_normal[3] = {0.0, 0.0, 0.0};
    bool ok = true;
    ProError code = PRO_TK_NO_ERROR;
};

// One tessellation triangle: area, area-weighted centroid contribution, bounds
// and a winding-aligned normal. Degenerate triangles carry no area and are
// skipped; they never become a zero-area vote for a direction.
static void region_add_triangle(RegionTessellationAccumulator &acc, const Pro3dPnt &a,
                                const Pro3dPnt &b, const Pro3dPnt &c) {
    const double u[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]};
    const double v[3] = {c[0] - a[0], c[1] - a[1], c[2] - a[2]};
    const double n[3] = {u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                         u[0] * v[1] - u[1] * v[0]};
    const double twice_area = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    const double area = 0.5 * twice_area;
    if (!(area > 1e-12) || !std::isfinite(area))
        return;
    acc.region.area += area;
    for (int i = 0; i < 3; i++) {
        acc.moment[i] += area * (a[i] + b[i] + c[i]) / 3.0;
        acc.bb_min[i] = std::min({acc.bb_min[i], a[i], b[i], c[i]});
        acc.bb_max[i] = std::max({acc.bb_max[i], a[i], b[i], c[i]});
    }
    const double unit[3] = {n[0] / twice_area, n[1] / twice_area, n[2] / twice_area};
    if (!acc.has_reference_normal) {
        for (int i = 0; i < 3; i++)
            acc.reference_normal[i] = unit[i];
        acc.has_reference_normal = true;
    }
    const double alignment = acc.reference_normal[0] * unit[0] + acc.reference_normal[1] * unit[1] +
                             acc.reference_normal[2] * unit[2];
    // Facet winding is not guaranteed to agree, so planarity is judged against
    // the reference axis (|cos|) while the sum follows one consistent sign.
    const double cosine = std::fabs(alignment) > 1.0 ? 1.0 : std::fabs(alignment);
    const double deviation = std::acos(cosine) * RADIANS_TO_DEGREES;
    if (deviation > acc.region.max_normal_deviation_deg)
        acc.region.max_normal_deviation_deg = deviation;
    const double sign = alignment < 0.0 ? -1.0 : 1.0;
    for (int i = 0; i < 3; i++)
        acc.normal_sum[i] += area * sign * unit[i];
    acc.region.triangle_count++;
}

static void region_tessellate_surface(ProSurface surface, RegionTessellationAccumulator &acc) {
    if (!acc.ok)
        return;
    ProSurfaceTessellationInput input = nullptr;
    ProError code = ProSurfacetessellationinputAlloc(&input);
    if (code) {
        acc.ok = false;
        acc.code = code;
        return;
    }
    // The default chord height is the shading tessellation Creo itself uses;
    // no accuracy level is claimed beyond it.
    ProSurfacetessellationinputChordheightSet(input, PRO_SRFTESS_CHORD_HT_DEFAULT);
    ProTessellation tessellation = nullptr;
    code = ProSurfaceTessellationGet(surface, input, &tessellation);
    ProSurfacetessellationinputFree(input);
    if (code == PRO_TK_INCOMPLETE_TESS)
        acc.region.incomplete_tessellation = true;
    else if (code != PRO_TK_NO_ERROR) {
        acc.ok = false;
        acc.code = code;
        return;
    }
    if (!tessellation) {
        acc.ok = false;
        acc.code = PRO_TK_GENERAL_ERROR;
        return;
    }
    Pro3dPnt *vertices = nullptr;
    ProTriangle *facets = nullptr;
    const bool arrays_ok = ProTessellationVerticesGet(tessellation, &vertices) == PRO_TK_NO_ERROR &&
                           ProTessellationFacetsGet(tessellation, &facets) == PRO_TK_NO_ERROR &&
                           vertices && facets;
    if (!arrays_ok) {
        acc.ok = false;
        acc.code = PRO_TK_GENERAL_ERROR;
        ProTessellationFree(tessellation);
        return;
    }
    int vertex_count = 0;
    int facet_count = 0;
    ProArraySizeGet((ProArray)vertices, &vertex_count);
    ProArraySizeGet((ProArray)facets, &facet_count);
    for (int facet = 0; facet < facet_count; facet++) {
        const int *indices = facets[facet];
        if (indices[0] < 0 || indices[1] < 0 || indices[2] < 0 || indices[0] >= vertex_count ||
            indices[1] >= vertex_count || indices[2] >= vertex_count)
            continue;
        region_add_triangle(acc, vertices[indices[0]], vertices[indices[1]], vertices[indices[2]]);
    }
    ProArrayFree((ProArray *)&vertices);
    ProArrayFree((ProArray *)&facets);
    ProTessellationFree(tessellation);
    acc.region.face_count++;
}

static ProError region_surface_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *acc = (RegionTessellationAccumulator *)data;
    if (status) {
        acc->ok = false;
        acc->code = status;
        return PRO_TK_NO_ERROR;
    }
    region_tessellate_surface(surface, *acc);
    return PRO_TK_NO_ERROR;
}

// Real region geometry for one quilt. Every failure keeps the values null with
// a reason and the raw query code; there is no zero fallback.
static RegionGeometry quilt_region_geometry(ProQuilt quilt) {
    RegionTessellationAccumulator acc;
    ProError visit_code = ProQuiltSurfaceVisit(quilt, region_surface_cb, nullptr, &acc);
    RegionGeometry geometry;
    if (visit_code == PRO_TK_E_NOT_FOUND) {
        geometry.reason = "quilt_has_no_surfaces";
        return geometry;
    }
    if (visit_code) {
        geometry.query_code = visit_code;
        geometry.reason = "quilt_surface_visit_failed";
        return geometry;
    }
    if (!acc.ok) {
        geometry.query_code = acc.code;
        geometry.reason = "surface_tessellation_failed";
        return geometry;
    }
    if (acc.region.triangle_count == 0 || !(acc.region.area > 0.0)) {
        geometry.reason = "no_tessellation_triangles";
        return geometry;
    }
    geometry = acc.region;
    geometry.available = true;
    geometry.reason = nullptr;
    for (int i = 0; i < 3; i++) {
        geometry.centroid[i] = acc.moment[i] / acc.region.area;
        geometry.bb_min[i] = acc.bb_min[i];
        geometry.bb_max[i] = acc.bb_max[i];
    }
    const double length =
        std::sqrt(acc.normal_sum[0] * acc.normal_sum[0] + acc.normal_sum[1] * acc.normal_sum[1] +
                  acc.normal_sum[2] * acc.normal_sum[2]);
    if (length > 1e-12) {
        for (int i = 0; i < 3; i++)
            geometry.normal[i] = acc.normal_sum[i] / length;
        geometry.planar = geometry.max_normal_deviation_deg <= REGION_PLANAR_TOLERANCE_DEG;
    }
    if (!geometry.incomplete_tessellation)
        geometry.incomplete_tessellation = acc.region.incomplete_tessellation;
    return geometry;
}

// §4.4.1 projection of the region geometry. The centroid and bounds are null
// when the region was not measured or the unit scale is unknown; the direction
// is unitless, so it needs no scale but is null for a non-planar region.
static J region_centroid_json(const RegionGeometry &geometry, const MillimeterScale &scale) {
    if (!geometry.available || !scale.known)
        return nullptr;
    return xyz_json(geometry.centroid, scale);
}

static J region_bbox_json(const RegionGeometry &geometry, const MillimeterScale &scale) {
    if (!geometry.available || !scale.known)
        return nullptr;
    const double size[3] = {geometry.bb_max[0] - geometry.bb_min[0],
                            geometry.bb_max[1] - geometry.bb_min[1],
                            geometry.bb_max[2] - geometry.bb_min[2]};
    return {{"min", xyz_json(geometry.bb_min, scale)},
            {"max", xyz_json(geometry.bb_max, scale)},
            {"size", xyz_json(size, scale)}};
}

static J region_direction_json(const RegionGeometry &geometry) {
    if (!geometry.available || !geometry.planar)
        return nullptr;
    return J::array({geometry.normal[0], geometry.normal[1], geometry.normal[2]});
}

static J region_status_json(const RegionGeometry &geometry, const InspectionLengthUnits &units,
                            const MillimeterScale &scale) {
    MeasurementOutcome outcome{geometry.available, geometry.query_code, geometry.reason,
                               geometry.area};
    J status = measurement_status_json(outcome, units, scale);
    status["source"] = geometry.available ? J("surface_tessellation") : J(nullptr);
    status["face_count"] = geometry.available ? J(geometry.face_count) : J(nullptr);
    status["triangle_count"] =
        geometry.available ? J((long long)geometry.triangle_count) : J(nullptr);
    status["tessellation_complete"] =
        geometry.available ? J(!geometry.incomplete_tessellation) : J(nullptr);
    return status;
}

static J region_direction_status_json(const RegionGeometry &geometry,
                                      const InspectionLengthUnits &units,
                                      const MillimeterScale &scale) {
    MeasurementOutcome outcome;
    outcome.available = geometry.available && geometry.planar;
    outcome.query_code = geometry.query_code;
    outcome.reason =
        geometry.available ? (geometry.planar ? nullptr : "region_not_planar") : geometry.reason;
    J status = measurement_status_json(outcome, units, scale);
    status["source"] = geometry.available ? J("surface_tessellation") : J(nullptr);
    status["planar"] = geometry.available ? J(geometry.planar) : J(nullptr);
    status["max_normal_deviation_deg"] =
        geometry.available ? J(geometry.max_normal_deviation_deg) : J(nullptr);
    return status;
}
