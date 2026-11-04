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

#include <cmath>

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
