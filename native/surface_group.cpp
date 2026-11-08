// surface_group.cpp — FEAT-039/H04: group-level boundary measurement for a set
// of quilts.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §4.4.1/§4.4.2 (every value
// ships its unit context, a failure never fabricates zero) and §4.8 (the group
// fields frozen for this module). A quilt's own ProQuiltVolumeEval answer is
// per-face closure; it cannot say whether two members are joined, slightly
// apart or overlapping, so this module measures the actual boundary topology:
//
//   * every member face's contours are visited with ProSurfaceContourVisit and
//     every boundary edge with ProContourEdgeVisit (ProEdge handles);
//   * an edge referenced by two group faces is topologically shared (an
//     internal seam); an edge referenced once is a boundary candidate;
//   * two boundary edges from different faces are compared with their sampled
//     polylines (ProEdgeTessellationGet, falling back to ProEdgeXyzdataEval):
//     the lateral distance and the longitudinal overlap decide whether they
//     form a seam candidate. A candidate within tolerance is joined; one
//     between tolerance and gap_search is a measured gap; anything else is
//     unrelated (no fabricated gap for an isolated patch);
//   * overlap is measured by sampling the kernel's own face tessellation and
//     asking the other face (ProSurfaceParamEval + ProSurfaceXyzdataEval +
//     ProSurfaceUvpntVerify) whether the sample lies on it, inside its
//     trimmed contour. Nothing is inferred from volume or area.
//
// This file is included by generic.cpp after the shared measurement helpers;
// it defines no entry point of its own beyond generic_surface_group_measure.
#include <ProContour.h>
#include <ProEdge.h>
#include <ProSurface.h>
#include <ProUvStat.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <vector>

// Sampling and bounding constants. They are deliberately small and explicit:
// a curved edge is judged from its chord and its sampled polyline, and a group
// that would need more overlap samples than the budget reports "unavailable"
// instead of extrapolating.
static constexpr int SURFACE_GROUP_EDGE_SAMPLES = 17;
static constexpr int SURFACE_GROUP_OVERLAP_SUBDIVISION = 10;
static constexpr int SURFACE_GROUP_OVERLAP_SAMPLE_BUDGET = 20000;
static constexpr int SURFACE_GROUP_OVERLAP_PAIR_LIMIT = 20;
static constexpr double SURFACE_GROUP_MIN_SHARED_RATIO = 0.1;
static constexpr double SURFACE_GROUP_PARALLEL_RATIO = 0.9;
static constexpr double SURFACE_GROUP_COINCIDENT_EPSILON_MM = 1e-6;

struct GroupPoint {
    double v[3] = {0.0, 0.0, 0.0};
};

struct GroupFaceRecord {
    ProSurface surface = nullptr;
    int surface_id = -1;
    int quilt_index = -1;
};

struct GroupBoundaryEdge {
    long long key = 0;
    int edge_id = -1;
    int surface_id = -1;
    int face_index = -1;
    int quilt_index = -1;
    int face_references = 1;
    double length = 0.0; // native units
    std::vector<GroupPoint> points;
    bool joined = false;
};

struct SurfaceGroupAccumulator {
    std::vector<GroupFaceRecord> faces;
    std::vector<GroupBoundaryEdge> edges;
    std::map<long long, int> edge_index;
    int current_quilt_index = -1;
    bool visits_ok = true;
    int sample_failures = 0;
    ProError query_code = PRO_TK_NO_ERROR;
    const char *reason = nullptr;
};

struct GroupContourContext {
    SurfaceGroupAccumulator *acc = nullptr;
    ProSurface surface = nullptr;
    int face_index = -1;
};

static double group_point_distance(const GroupPoint &a, const GroupPoint &b) {
    const double dx = a.v[0] - b.v[0];
    const double dy = a.v[1] - b.v[1];
    const double dz = a.v[2] - b.v[2];
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

static double group_polyline_length(const std::vector<GroupPoint> &points) {
    double length = 0.0;
    for (size_t index = 1; index < points.size(); index++)
        length += group_point_distance(points[index - 1], points[index]);
    return length;
}

// Distance from one point to one polyline segment (real 3D distance, not a
// screen-space or axis-aligned approximation).
static double group_point_segment_distance(const GroupPoint &point, const GroupPoint &a,
                                           const GroupPoint &b) {
    double segment[3] = {b.v[0] - a.v[0], b.v[1] - a.v[1], b.v[2] - a.v[2]};
    const double squared =
        segment[0] * segment[0] + segment[1] * segment[1] + segment[2] * segment[2];
    if (!(squared > 1e-24))
        return group_point_distance(point, a);
    const double to_point[3] = {point.v[0] - a.v[0], point.v[1] - a.v[1], point.v[2] - a.v[2]};
    double parameter =
        (to_point[0] * segment[0] + to_point[1] * segment[1] + to_point[2] * segment[2]) / squared;
    parameter = std::max(0.0, std::min(1.0, parameter));
    GroupPoint closest;
    for (int i = 0; i < 3; i++)
        closest.v[i] = a.v[i] + parameter * segment[i];
    return group_point_distance(point, closest);
}

static double group_point_polyline_distance(const GroupPoint &point,
                                            const std::vector<GroupPoint> &polyline) {
    if (polyline.empty())
        return std::numeric_limits<double>::infinity();
    if (polyline.size() == 1)
        return group_point_distance(point, polyline[0]);
    double best = std::numeric_limits<double>::infinity();
    for (size_t index = 1; index < polyline.size(); index++)
        best = std::min(best,
                        group_point_segment_distance(point, polyline[index - 1], polyline[index]));
    return best;
}

// Symmetric minimum distance between two sampled polylines.
static double group_polyline_distance(const std::vector<GroupPoint> &a,
                                      const std::vector<GroupPoint> &b) {
    double best = std::numeric_limits<double>::infinity();
    for (const auto &point : a)
        best = std::min(best, group_point_polyline_distance(point, b));
    for (const auto &point : b)
        best = std::min(best, group_point_polyline_distance(point, a));
    return best;
}

// Chord direction and the part of the edge that actually runs along it. A
// perpendicular neighbour (a corner contact) cannot become a seam candidate.
static void group_edge_chord(const std::vector<GroupPoint> &points, double direction[3],
                             double &span) {
    span = 0.0;
    direction[0] = direction[1] = direction[2] = 0.0;
    if (points.size() < 2)
        return;
    direction[0] = points.back().v[0] - points.front().v[0];
    direction[1] = points.back().v[1] - points.front().v[1];
    direction[2] = points.back().v[2] - points.front().v[2];
    const double length = std::sqrt(direction[0] * direction[0] + direction[1] * direction[1] +
                                    direction[2] * direction[2]);
    if (!(length > 1e-12)) {
        direction[0] = direction[1] = direction[2] = 0.0;
        return;
    }
    for (int i = 0; i < 3; i++)
        direction[i] /= length;
    double low = std::numeric_limits<double>::infinity();
    double high = -std::numeric_limits<double>::infinity();
    for (const auto &point : points) {
        const double projection =
            point.v[0] * direction[0] + point.v[1] * direction[1] + point.v[2] * direction[2];
        low = std::min(low, projection);
        high = std::max(high, projection);
    }
    span = high - low;
}

// Fraction of the shorter edge that faces the other edge along the common
// chord direction. Collinear overlap approaches 1; a corner touch approaches 0,
// so touching corners never become a seam.
static bool group_edges_are_parallel_candidates(const GroupBoundaryEdge &first,
                                                const GroupBoundaryEdge &second,
                                                double &overlap_ratio) {
    overlap_ratio = 0.0;
    double direction_a[3], direction_b[3];
    double span_a = 0.0, span_b = 0.0;
    group_edge_chord(first.points, direction_a, span_a);
    group_edge_chord(second.points, direction_b, span_b);
    if (!(first.length > 1e-12) || !(second.length > 1e-12))
        return false;
    const double dot = direction_a[0] * direction_b[0] + direction_a[1] * direction_b[1] +
                       direction_a[2] * direction_b[2];
    if (std::fabs(dot) < SURFACE_GROUP_PARALLEL_RATIO)
        return false;
    if (span_a / first.length < SURFACE_GROUP_PARALLEL_RATIO ||
        span_b / second.length < SURFACE_GROUP_PARALLEL_RATIO)
        return false;
    double low_a = std::numeric_limits<double>::infinity();
    double high_a = -std::numeric_limits<double>::infinity();
    double low_b = std::numeric_limits<double>::infinity();
    double high_b = -std::numeric_limits<double>::infinity();
    for (const auto &point : first.points) {
        const double projection =
            point.v[0] * direction_a[0] + point.v[1] * direction_a[1] + point.v[2] * direction_a[2];
        low_a = std::min(low_a, projection);
        high_a = std::max(high_a, projection);
    }
    for (const auto &point : second.points) {
        const double projection =
            point.v[0] * direction_a[0] + point.v[1] * direction_a[1] + point.v[2] * direction_a[2];
        low_b = std::min(low_b, projection);
        high_b = std::max(high_b, projection);
    }
    const double overlap = std::min(high_a, high_b) - std::max(low_a, low_b);
    if (!(overlap > 0.0))
        return false;
    const double shorter = std::min(span_a, span_b);
    if (!(shorter > 1e-12))
        return false;
    overlap_ratio = overlap / shorter;
    return overlap_ratio >= SURFACE_GROUP_MIN_SHARED_RATIO;
}

// Sample one edge. The kernel tessellation is the first choice (it is the
// geometry the kernel itself displays); a direct parameter sweep is the
// fallback. Both give points in model units.
static bool group_sample_edge(ProEdge edge, std::vector<GroupPoint> &points, double &length,
                              ProError &code) {
    points.clear();
    length = 0.0;
    Pro3dPnt *tessellation = nullptr;
    int count = 0;
    code = ProEdgeTessellationGet(edge, &tessellation, nullptr, nullptr, nullptr, &count);
    // A straight edge tessellates to its two endpoints only, which are exactly
    // the points most likely to sit on a neighbour's corner or boundary. The
    // parameter sweep gives interior samples, so both distance and containment
    // tests see the middle of the edge.
    if (code == PRO_TK_NO_ERROR && tessellation && count >= 5) {
        for (int index = 0; index < count; index++)
            points.push_back(
                {{tessellation[index][0], tessellation[index][1], tessellation[index][2]}});
    }
    if (tessellation)
        ProArrayFree((ProArray *)&tessellation);
    if (points.size() < 2) {
        points.clear();
        for (int index = 0; index < SURFACE_GROUP_EDGE_SAMPLES; index++) {
            ProVector point = {0.0, 0.0, 0.0};
            ProVector deriv1 = {0.0, 0.0, 0.0};
            ProVector deriv2 = {0.0, 0.0, 0.0};
            ProVector direction = {0.0, 0.0, 0.0};
            const double parameter = (double)index / (double)(SURFACE_GROUP_EDGE_SAMPLES - 1);
            code = ProEdgeXyzdataEval(edge, parameter, point, deriv1, deriv2, direction);
            if (code) {
                if (index == 0)
                    return false;
                break;
            }
            points.push_back({{point[0], point[1], point[2]}});
        }
    }
    if (points.size() < 2) {
        if (!code)
            code = PRO_TK_GENERAL_ERROR;
        points.clear();
        return false;
    }
    double measured = 0.0;
    if (ProEdgeLengthEval(edge, &measured) == PRO_TK_NO_ERROR && measured > 0.0)
        length = measured;
    else
        length = group_polyline_length(points);
    if (!(length > 0.0)) {
        code = PRO_TK_GENERAL_ERROR;
        return false;
    }
    code = PRO_TK_NO_ERROR;
    return true;
}

static ProError group_edge_cb(ProEdge edge, ProError status, ProAppData data) {
    auto *context = (GroupContourContext *)data;
    if (status || !edge || !context || !context->acc)
        return PRO_TK_NO_ERROR;
    SurfaceGroupAccumulator &acc = *context->acc;
    int edge_id = -1;
    if (ProEdgeIdGet(edge, &edge_id))
        edge_id = -1;
    // Edge ids are unique in a part; when this SDK cannot name a datum-surface
    // edge the handle itself identifies the same edge on two faces.
    const long long key = edge_id >= 0 ? (long long)edge_id : -(long long)(intptr_t)edge - 1;
    auto found = acc.edge_index.find(key);
    if (found != acc.edge_index.end()) {
        acc.edges[found->second].face_references++;
        return PRO_TK_NO_ERROR;
    }
    GroupBoundaryEdge record;
    record.key = key;
    record.edge_id = edge_id;
    record.face_index = context->face_index;
    record.quilt_index = acc.current_quilt_index;
    if (context->face_index >= 0 && context->face_index < (int)acc.faces.size())
        record.surface_id = acc.faces[context->face_index].surface_id;
    ProError sample_code = PRO_TK_NO_ERROR;
    if (!group_sample_edge(edge, record.points, record.length, sample_code)) {
        acc.sample_failures++;
        if (!acc.query_code)
            acc.query_code = sample_code ? sample_code : PRO_TK_GENERAL_ERROR;
        record.points.clear();
    }
    acc.edge_index[key] = (int)acc.edges.size();
    acc.edges.push_back(std::move(record));
    return PRO_TK_NO_ERROR;
}

static ProError group_contour_cb(ProContour contour, ProError status, ProAppData data) {
    auto *context = (GroupContourContext *)data;
    if (status || !context || !context->acc)
        return PRO_TK_NO_ERROR;
    ProError code = ProContourEdgeVisit(context->surface, contour, group_edge_cb, nullptr, context);
    if (code == PRO_TK_E_NOT_FOUND)
        return PRO_TK_NO_ERROR;
    if (code) {
        SurfaceGroupAccumulator &acc = *context->acc;
        acc.visits_ok = false;
        if (!acc.query_code)
            acc.query_code = code;
        if (!acc.reason)
            acc.reason = "contour_edge_visit_failed";
    }
    return PRO_TK_NO_ERROR;
}

static ProError group_surface_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *acc = (SurfaceGroupAccumulator *)data;
    if (!acc)
        return PRO_TK_NO_ERROR;
    if (status || !surface) {
        acc->visits_ok = false;
        if (!acc->query_code && status)
            acc->query_code = status;
        if (!acc->reason)
            acc->reason = "quilt_surface_visit_failed";
        return PRO_TK_NO_ERROR;
    }
    GroupFaceRecord face;
    face.surface = surface;
    face.quilt_index = acc->current_quilt_index;
    ProSurfaceIdGet(surface, &face.surface_id);
    acc->faces.push_back(face);
    GroupContourContext context;
    context.acc = acc;
    context.surface = surface;
    context.face_index = (int)acc->faces.size() - 1;
    ProError code = ProSurfaceContourVisit(surface, group_contour_cb, nullptr, &context);
    if (code == PRO_TK_E_NOT_FOUND) {
        acc->visits_ok = false;
        if (!acc->query_code)
            acc->query_code = code;
        if (!acc->reason)
            acc->reason = "quilt_surface_has_no_contour";
    } else if (code) {
        acc->visits_ok = false;
        if (!acc->query_code)
            acc->query_code = code;
        if (!acc->reason)
            acc->reason = "surface_contour_visit_failed";
    }
    return PRO_TK_NO_ERROR;
}

// One seam-candidate pair. `joined` pairs are within tolerance; gapped pairs are
// within the search window but outside tolerance. Both are real measured
// boundary-to-boundary distances.
struct GroupPairedEdge {
    int first = -1;
    int second = -1;
    double distance = 0.0;
};

// One overlap sample: a point on a member face plus the surface area that
// sample represents (the face tessellation subdivided evenly).
struct GroupFaceSample {
    GroupPoint point;
    double area = 0.0; // native units²
};

static bool group_face_samples(ProSurface surface, std::vector<GroupFaceSample> &samples,
                               ProError &code) {
    samples.clear();
    ProSurfaceTessellationInput input = nullptr;
    code = ProSurfacetessellationinputAlloc(&input);
    if (code)
        return false;
    ProSurfacetessellationinputChordheightSet(input, PRO_SRFTESS_CHORD_HT_DEFAULT);
    ProTessellation tessellation = nullptr;
    code = ProSurfaceTessellationGet(surface, input, &tessellation);
    ProSurfacetessellationinputFree(input);
    if (code == PRO_TK_INCOMPLETE_TESS)
        code = PRO_TK_NO_ERROR;
    if (code || !tessellation)
        return false;
    Pro3dPnt *vertices = nullptr;
    ProTriangle *facets = nullptr;
    const bool arrays_ok = ProTessellationVerticesGet(tessellation, &vertices) == PRO_TK_NO_ERROR &&
                           ProTessellationFacetsGet(tessellation, &facets) == PRO_TK_NO_ERROR &&
                           vertices && facets;
    if (!arrays_ok) {
        ProTessellationFree(tessellation);
        code = PRO_TK_GENERAL_ERROR;
        return false;
    }
    int vertex_count = 0;
    int facet_count = 0;
    ProArraySizeGet((ProArray)vertices, &vertex_count);
    ProArraySizeGet((ProArray)facets, &facet_count);
    const int subdivision = SURFACE_GROUP_OVERLAP_SUBDIVISION;
    const double per_sample = 1.0 / (double)(subdivision * (subdivision + 1) / 2);
    for (int facet = 0; facet < facet_count; facet++) {
        const int *indices = facets[facet];
        if (indices[0] < 0 || indices[1] < 0 || indices[2] < 0 || indices[0] >= vertex_count ||
            indices[1] >= vertex_count || indices[2] >= vertex_count)
            continue;
        const Pro3dPnt &a = vertices[indices[0]];
        const Pro3dPnt &b = vertices[indices[1]];
        const Pro3dPnt &c = vertices[indices[2]];
        const double triangle_u[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]};
        const double triangle_v[3] = {c[0] - a[0], c[1] - a[1], c[2] - a[2]};
        const double normal[3] = {triangle_u[1] * triangle_v[2] - triangle_u[2] * triangle_v[1],
                                  triangle_u[2] * triangle_v[0] - triangle_u[0] * triangle_v[2],
                                  triangle_u[0] * triangle_v[1] - triangle_u[1] * triangle_v[0]};
        const double area =
            0.5 * std::sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]);
        if (!(area > 1e-12) || !std::isfinite(area))
            continue;
        for (int row = 0; row < subdivision; row++) {
            for (int column = 0; column < subdivision - row; column++) {
                const double bary_u = (row + 1.0 / 3.0) / subdivision;
                const double bary_v = (column + 1.0 / 3.0) / subdivision;
                const double bary_w = 1.0 - bary_u - bary_v;
                GroupFaceSample sample;
                for (int axis = 0; axis < 3; axis++)
                    sample.point.v[axis] = a[axis] * bary_w + b[axis] * bary_u + c[axis] * bary_v;
                sample.area = area * per_sample;
                samples.push_back(sample);
            }
        }
    }
    ProArrayFree((ProArray *)&vertices);
    ProArrayFree((ProArray *)&facets);
    ProTessellationFree(tessellation);
    if (samples.empty()) {
        code = PRO_TK_GENERAL_ERROR;
        return false;
    }
    code = PRO_TK_NO_ERROR;
    return true;
}

// Relation of one sample point to a trimmed face. The distinction between "not
// on the surface", "on the surface but outside the contour" and "the kernel
// could not answer" is kept because only the last one is a measurement failure.
enum GroupPointRelation {
    GROUP_POINT_ERROR = -2,
    GROUP_POINT_OFF_SURFACE = -1,
    GROUP_POINT_OUTSIDE = 0,
    GROUP_POINT_INSIDE = 1,
};

// ProSurfaceParamEval returns the closest UV on the underlying geometry, so the
// point must also be within the tolerance of that surface and its UV must be
// inside the face contour (ProSurfaceUvpntVerify).
static int group_point_relation(ProSolid solid, ProSurface surface, const GroupPoint &point,
                                double tolerance, ProError &code) {
    ProVector xyz = {point.v[0], point.v[1], point.v[2]};
    ProUvParam uv = {0.0, 0.0};
    code = ProSurfaceParamEval(solid, surface, xyz, uv);
    if (code)
        return GROUP_POINT_ERROR;
    ProVector evaluated = {0.0, 0.0, 0.0};
    ProVector deriv1[2] = {};
    ProVector deriv2[3] = {};
    ProVector normal = {0.0, 0.0, 0.0};
    code = ProSurfaceXyzdataEval(surface, uv, evaluated, deriv1, deriv2, normal);
    if (code)
        return GROUP_POINT_ERROR;
    GroupPoint other;
    other.v[0] = evaluated[0];
    other.v[1] = evaluated[1];
    other.v[2] = evaluated[2];
    if (group_point_distance(point, other) > tolerance)
        return GROUP_POINT_OFF_SURFACE;
    ProUvStatus status = PRO_UV_OUTSIDE;
    code = ProSurfaceUvpntVerify(solid, surface, uv, &status);
    if (code)
        return GROUP_POINT_ERROR;
    return status == PRO_UV_INSIDE ? GROUP_POINT_INSIDE : GROUP_POINT_OUTSIDE;
}

static bool group_point_on_face(ProSolid solid, ProSurface surface, const GroupPoint &point,
                                double tolerance, ProError &code) {
    return group_point_relation(solid, surface, point, tolerance, code) == GROUP_POINT_INSIDE;
}

struct SurfaceGroupMeasurement {
    bool edges_available = false;
    ProError edges_code = PRO_TK_NO_ERROR;
    const char *edges_reason = nullptr;
    int face_count = 0;
    int boundary_edges = 0;
    int joined_edges = 0;
    int open_edges = 0;
    int topological_joined_edges = 0;
    int sample_failures = 0;

    bool gap_available = false;
    ProError gap_code = PRO_TK_NO_ERROR;
    const char *gap_reason = nullptr;
    double gap_max = 0.0; // native units
    int candidate_pairs = 0;
    int joined_pairs = 0;
    int gap_pairs = 0;
    double max_joined_gap = 0.0; // native units

    bool overlap_available = false;
    ProError overlap_code = PRO_TK_NO_ERROR;
    const char *overlap_reason = nullptr;
    double overlap_area = 0.0; // native units²
    int overlap_pairs = 0;
    int buried_boundary_edges = 0;
    bool overlap_detected = false;
    int face_pairs_tested = 0;
    long long overlap_samples = 0;
    int containment_inside = 0;
    int containment_errors = 0;
    int containment_off_surface = 0;
    int containment_outside = 0;
    ProError containment_code = PRO_TK_NO_ERROR;
    double sample_resolution = 0.0; // native units² per overlap sample
    J overlap_pair_records = J::array();

    const char *state = nullptr;
    const char *state_reason = nullptr;
};

static void group_measure_boundaries(SurfaceGroupAccumulator &acc, double tolerance,
                                     double gap_search, SurfaceGroupMeasurement &out) {
    out.face_count = (int)acc.faces.size();
    out.boundary_edges = (int)acc.edges.size();
    out.sample_failures = acc.sample_failures;
    // A failed face/contour visit makes the boundary incomplete: counts would
    // silently describe part of the group, so nothing is published then.
    out.edges_available = acc.visits_ok && acc.reason == nullptr && !acc.edges.empty();
    out.edges_reason = acc.reason          ? acc.reason
                       : acc.edges.empty() ? "group_has_no_boundary_edges"
                                           : nullptr;
    out.edges_code = acc.query_code;

    for (auto &edge : acc.edges)
        if (edge.face_references >= 2)
            edge.joined = true;

    std::vector<GroupPairedEdge> joined_pairs;
    std::vector<GroupPairedEdge> gap_pairs;
    if (out.edges_available && out.sample_failures == 0 && acc.edges.size() > 1) {
        for (size_t first = 0; first < acc.edges.size(); first++) {
            const GroupBoundaryEdge &a = acc.edges[first];
            if (a.points.size() < 2)
                continue;
            for (size_t second = first + 1; second < acc.edges.size(); second++) {
                const GroupBoundaryEdge &b = acc.edges[second];
                if (b.points.size() < 2)
                    continue;
                if (a.face_index == b.face_index)
                    continue;
                double overlap_ratio = 0.0;
                if (!group_edges_are_parallel_candidates(a, b, overlap_ratio))
                    continue;
                const double distance = group_polyline_distance(a.points, b.points);
                if (!std::isfinite(distance))
                    continue;
                GroupPairedEdge pair;
                pair.first = (int)first;
                pair.second = (int)second;
                pair.distance = distance;
                if (distance <= tolerance)
                    joined_pairs.push_back(pair);
                else if (distance <= gap_search)
                    gap_pairs.push_back(pair);
            }
        }
        // Greedy one-to-one matching on the smallest distance: an edge can be
        // joined to one partner only, so a T-junction cannot claim every
        // neighbour as a seam.
        std::sort(joined_pairs.begin(), joined_pairs.end(),
                  [](const GroupPairedEdge &left, const GroupPairedEdge &right) {
                      return left.distance < right.distance;
                  });
        std::vector<bool> used(acc.edges.size(), false);
        for (const auto &pair : joined_pairs) {
            if (used[pair.first] || used[pair.second])
                continue;
            used[pair.first] = true;
            used[pair.second] = true;
            acc.edges[pair.first].joined = true;
            acc.edges[pair.second].joined = true;
            out.joined_pairs++;
            out.max_joined_gap = std::max(out.max_joined_gap, pair.distance);
        }
        out.gap_available = true;
        out.candidate_pairs = out.joined_pairs + (int)gap_pairs.size();
        out.gap_pairs = (int)gap_pairs.size();
        double gap_max = 0.0;
        for (const auto &pair : joined_pairs) {
            if (used[pair.first] && used[pair.second])
                gap_max = std::max(gap_max, pair.distance);
        }
        for (const auto &pair : gap_pairs)
            gap_max = std::max(gap_max, pair.distance);
        out.gap_max = gap_max;
        if (out.candidate_pairs == 0) {
            out.gap_available = false;
            out.gap_reason = "no_member_seam_candidate";
        }
    } else if (out.edges_available) {
        out.gap_available = false;
        out.gap_reason =
            out.sample_failures ? "boundary_edge_sampling_failed" : "boundary_edges_missing";
        out.gap_code = acc.query_code;
    }

    out.joined_edges = 0;
    out.open_edges = 0;
    for (const auto &edge : acc.edges) {
        if (edge.joined)
            out.joined_edges++;
        else
            out.open_edges++;
    }
    out.topological_joined_edges = 0;
    for (const auto &edge : acc.edges)
        if (edge.face_references >= 2)
            out.topological_joined_edges++;
}

// A member boundary that is buried inside another member (on its surface and
// inside its trimmed contour, farther than `tolerance` from that member's own
// boundary) is overlap evidence that does not depend on the sampling grid being
// finer than the shared sliver. Coincident or nearly coincident seams are not
// buried: their points sit on the neighbour boundary itself.
static int group_buried_boundary_edges(ProSolid solid, SurfaceGroupAccumulator &acc,
                                       double tolerance, ProError &code) {
    int buried = 0;
    for (const auto &edge : acc.edges) {
        if (edge.face_references >= 2 || edge.points.size() < 2)
            continue;
        bool is_buried = false;
        for (size_t face_index = 0; face_index < acc.faces.size() && !is_buried; face_index++) {
            if ((int)face_index == edge.face_index)
                continue;
            const ProSurface other = acc.faces[face_index].surface;
            for (const auto &point : edge.points) {
                ProError point_code = PRO_TK_NO_ERROR;
                if (group_point_relation(solid, other, point, tolerance, point_code) !=
                    GROUP_POINT_INSIDE)
                    continue;
                double boundary_distance = std::numeric_limits<double>::infinity();
                for (const auto &candidate : acc.edges) {
                    if (candidate.face_index != (int)face_index || candidate.points.size() < 2)
                        continue;
                    boundary_distance = std::min(
                        boundary_distance, group_point_polyline_distance(point, candidate.points));
                }
                if (boundary_distance > tolerance) {
                    is_buried = true;
                    break;
                }
            }
        }
        if (is_buried)
            buried++;
    }
    code = PRO_TK_NO_ERROR;
    return buried;
}

static void group_measure_overlap(ProSolid solid, SurfaceGroupAccumulator &acc, double tolerance,
                                  SurfaceGroupMeasurement &out) {
    if (acc.faces.size() < 2) {
        out.overlap_reason = "group_has_fewer_than_two_faces";
        return;
    }
    std::vector<std::vector<GroupFaceSample>> samples(acc.faces.size());
    for (size_t index = 0; index < acc.faces.size(); index++) {
        ProError code = PRO_TK_NO_ERROR;
        if (!group_face_samples(acc.faces[index].surface, samples[index], code)) {
            out.overlap_code = code;
            out.overlap_reason = "face_tessellation_failed";
            return;
        }
    }
    long long sample_tests = 0;
    double overlap_area = 0.0;
    int pairs = 0;
    J records = J::array();
    for (size_t first = 0; first < acc.faces.size(); first++) {
        for (size_t second = 0; second < acc.faces.size(); second++) {
            if (first == second)
                continue;
            if (sample_tests + (long long)samples[first].size() >
                SURFACE_GROUP_OVERLAP_SAMPLE_BUDGET) {
                out.overlap_code = PRO_TK_GENERAL_ERROR;
                out.overlap_reason = "overlap_sample_budget_exceeded";
                return;
            }
            double area = 0.0;
            for (const auto &sample : samples[first]) {
                sample_tests++;
                ProError code = PRO_TK_NO_ERROR;
                const int relation = group_point_relation(solid, acc.faces[second].surface,
                                                          sample.point, tolerance, code);
                if (relation == GROUP_POINT_ERROR) {
                    out.containment_errors++;
                    if (!out.containment_code)
                        out.containment_code = code;
                    continue;
                }
                if (relation == GROUP_POINT_OFF_SURFACE) {
                    out.containment_off_surface++;
                    continue;
                }
                if (relation != GROUP_POINT_INSIDE) {
                    out.containment_outside++;
                    continue;
                }
                out.containment_inside++;
                area += sample.area;
            }
            if (first < second) {
                out.face_pairs_tested++;
                if (area > 0.0) {
                    overlap_area += area;
                    pairs++;
                    if ((int)records.size() < SURFACE_GROUP_OVERLAP_PAIR_LIMIT)
                        records.push_back({{"first_surface_id", acc.faces[first].surface_id},
                                           {"second_surface_id", acc.faces[second].surface_id},
                                           {"first_quilt_index", acc.faces[first].quilt_index},
                                           {"second_quilt_index", acc.faces[second].quilt_index},
                                           {"area_mm2_native_units", area}});
                }
            }
        }
    }
    double sample_area = 0.0;
    long long sample_count = 0;
    for (const auto &face_samples : samples) {
        for (const auto &sample : face_samples) {
            sample_area += sample.area;
            sample_count++;
        }
    }
    out.sample_resolution = sample_count > 0 ? sample_area / (double)sample_count : 0.0;
    ProError buried_code = PRO_TK_NO_ERROR;
    out.buried_boundary_edges = group_buried_boundary_edges(solid, acc, tolerance, buried_code);
    if (buried_code && !out.overlap_code)
        out.overlap_code = buried_code;
    out.overlap_available = true;
    out.overlap_area = overlap_area;
    out.overlap_pairs = pairs;
    out.overlap_detected = pairs > 0 || out.buried_boundary_edges > 0;
    out.overlap_samples = sample_tests;
    out.overlap_pair_records = records;
}

// Group-state decision. It describes the member seams, not the outer shell: a
// flat two-patch group can have closed seams and still be an open sheet, so
// `boundary_closed` (open_edges == 0) is reported separately.
static void group_state_decide(const SurfaceGroupMeasurement &measurement, double tolerance,
                               double coincidence_epsilon, SurfaceGroupMeasurement &out) {
    if (!measurement.edges_available) {
        out.state_reason =
            measurement.edges_reason ? measurement.edges_reason : "boundary_edges_unavailable";
        return;
    }
    if (measurement.overlap_available && measurement.overlap_detected) {
        out.state = "overlap";
        return;
    }
    if (measurement.sample_failures > 0) {
        out.state_reason = "boundary_edge_sampling_failed";
        return;
    }
    if (measurement.open_edges == 0) {
        out.state = "closed";
        return;
    }
    if (measurement.gap_available && measurement.gap_max > tolerance + coincidence_epsilon) {
        out.state = "open";
        return;
    }
    if (measurement.joined_pairs > 0 && measurement.max_joined_gap > coincidence_epsilon) {
        out.state = "micro_gap";
        return;
    }
    if (measurement.joined_pairs > 0) {
        out.state = "closed";
        return;
    }
    out.state = "open";
    // Boundary traversal succeeded. A missing inter-member gap candidate does
    // not make the measured open boundary unavailable.
    out.state_reason = "open_edges_present";
}

// Project the measurement into the §4.4.1 status shape. Every value carries its
// own status; an unknown unit scale keeps the mm value null.
static J surface_group_receipt(const std::vector<int> &quilt_ids, double tolerance_mm,
                               double gap_search_mm) {
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    const bool scaled = scale.known;

    SurfaceGroupAccumulator acc;
    std::vector<int> resolved;
    for (int quilt_id : quilt_ids) {
        ProQuilt quilt = nullptr;
        if (quilt_id < 0 || ProQuiltInit((ProSolid)board, quilt_id, &quilt)) {
            acc.visits_ok = false;
            if (!acc.reason)
                acc.reason = "quilt_init_failed";
            if (!acc.query_code)
                acc.query_code = PRO_TK_BAD_INPUTS;
            continue;
        }
        acc.current_quilt_index = (int)resolved.size();
        resolved.push_back(quilt_id);
        ProError code = ProQuiltSurfaceVisit(quilt, group_surface_cb, nullptr, &acc);
        if (code == PRO_TK_E_NOT_FOUND) {
            acc.visits_ok = false;
            if (!acc.reason)
                acc.reason = "quilt_has_no_surfaces";
            if (!acc.query_code)
                acc.query_code = code;
        } else if (code) {
            acc.visits_ok = false;
            if (!acc.reason)
                acc.reason = "quilt_surface_visit_failed";
            if (!acc.query_code)
                acc.query_code = code;
        }
    }
    acc.current_quilt_index = -1;

    SurfaceGroupMeasurement measurement;
    double tolerance_native = 0.0;
    double gap_search_native = 0.0;
    if (scaled) {
        tolerance_native = tolerance_mm / scale.scale;
        gap_search_native = std::max(gap_search_mm / scale.scale, tolerance_native);
    }
    group_measure_boundaries(acc, tolerance_native, gap_search_native, measurement);

    if (scaled) {
        group_measure_overlap((ProSolid)board, acc, tolerance_native, measurement);
        group_state_decide(measurement, tolerance_native,
                           SURFACE_GROUP_COINCIDENT_EPSILON_MM / scale.scale, measurement);
    } else {
        measurement.overlap_available = false;
        measurement.overlap_reason = "unit_scale_unknown";
        measurement.gap_available = false;
        measurement.gap_reason = "unit_scale_unknown";
        measurement.state = nullptr;
        measurement.state_reason =
            measurement.edges_available ? "unit_scale_unknown" : measurement.edges_reason;
    }

    MeasurementOutcome open_edges_outcome;
    open_edges_outcome.available = measurement.edges_available;
    open_edges_outcome.query_code = measurement.edges_code;
    open_edges_outcome.reason = measurement.edges_available ? nullptr : measurement.edges_reason;
    open_edges_outcome.value = (double)measurement.open_edges;
    J open_edges_status = measurement_status_json(open_edges_outcome, units, scale);
    open_edges_status["boundary_edges"] =
        measurement.edges_available ? J(measurement.boundary_edges) : J(nullptr);
    open_edges_status["joined_edges"] =
        measurement.edges_available ? J(measurement.joined_edges) : J(nullptr);
    open_edges_status["topologically_shared_edges"] =
        measurement.edges_available ? J(measurement.topological_joined_edges) : J(nullptr);

    MeasurementOutcome gap_outcome;
    gap_outcome.available = measurement.gap_available && scaled;
    gap_outcome.query_code = measurement.gap_code;
    gap_outcome.reason = !scaled ? "unit_scale_unknown" : measurement.gap_reason;
    gap_outcome.value = measurement.gap_max;
    J gap_max_mm = gap_outcome.available ? J(measurement.gap_max * scale.scale) : J(nullptr);
    J gap_status = measurement_status_json(gap_outcome, units, scale);
    gap_status["tolerance_mm"] = tolerance_mm;
    gap_status["gap_search_mm"] = gap_search_mm;
    gap_status["candidate_pairs"] =
        measurement.gap_available ? J(measurement.candidate_pairs) : J(nullptr);
    gap_status["joined_pairs"] =
        measurement.gap_available ? J(measurement.joined_pairs) : J(nullptr);
    gap_status["gap_pairs"] = measurement.gap_available ? J(measurement.gap_pairs) : J(nullptr);
    gap_status["within_tolerance"] =
        gap_outcome.available ? J(measurement.gap_max <= tolerance_native) : J(nullptr);

    MeasurementOutcome overlap_outcome;
    overlap_outcome.available = measurement.overlap_available && scaled;
    overlap_outcome.query_code = measurement.overlap_code;
    overlap_outcome.reason = !scaled ? "unit_scale_unknown" : measurement.overlap_reason;
    overlap_outcome.value = measurement.overlap_area;
    J overlap_area_mm2 = overlap_outcome.available
                             ? J(measurement.overlap_area * scale.scale * scale.scale)
                             : J(nullptr);
    J overlap_status = measurement_status_json(overlap_outcome, units, scale);
    overlap_status["method"] =
        measurement.overlap_available ? J("face_tessellation_sample_containment") : J(nullptr);
    overlap_status["tolerance_mm"] = tolerance_mm;
    overlap_status["face_pairs_tested"] =
        measurement.overlap_available ? J(measurement.face_pairs_tested) : J(nullptr);
    overlap_status["sample_tests"] =
        measurement.overlap_available ? J((long long)measurement.overlap_samples) : J(nullptr);
    overlap_status["overlapping_face_pairs"] =
        measurement.overlap_available ? J(measurement.overlap_pairs) : J(nullptr);
    overlap_status["buried_boundary_edges"] =
        measurement.overlap_available ? J(measurement.buried_boundary_edges) : J(nullptr);
    overlap_status["sample_resolution_mm2"] =
        measurement.overlap_available && scaled
            ? J(measurement.sample_resolution * scale.scale * scale.scale)
            : J(nullptr);
    overlap_status["detected"] =
        measurement.overlap_available ? J(measurement.overlap_detected) : J(nullptr);
    overlap_status["area_is_estimate"] = measurement.overlap_available ? J(true) : J(nullptr);
    // A sliver thinner than the sample spacing can be detected from a buried
    // boundary while its area estimate rounds to zero; say so instead of
    // letting 0.0 read as "no overlap area".
    overlap_status["area_below_sample_resolution"] =
        measurement.overlap_available
            ? J(measurement.overlap_detected && measurement.overlap_area <= 0.0)
            : J(nullptr);
    overlap_status["containment_inside_samples"] =
        measurement.overlap_available ? J(measurement.containment_inside) : J(nullptr);
    overlap_status["containment_errors"] =
        measurement.overlap_available ? J(measurement.containment_errors) : J(nullptr);
    overlap_status["containment_error_code"] =
        measurement.overlap_available
            ? J(measurement.containment_errors ? (int)measurement.containment_code : 0)
            : J(nullptr);
    overlap_status["containment_off_surface"] =
        measurement.overlap_available ? J(measurement.containment_off_surface) : J(nullptr);
    overlap_status["containment_outside"] =
        measurement.overlap_available ? J(measurement.containment_outside) : J(nullptr);

    J faces = J::array();
    for (const auto &face : acc.faces)
        faces.push_back({{"surface_id", face.surface_id}, {"quilt_index", face.quilt_index}});
    for (auto &record : measurement.overlap_pair_records) {
        if (!record.contains("area_mm2_native_units"))
            continue;
        const double native_area = record["area_mm2_native_units"].get<double>();
        record["area_mm2"] = scaled ? J(native_area * scale.scale * scale.scale) : J(nullptr);
        record.erase("area_mm2_native_units");
    }
    J resolved_ids = J::array();
    for (int quilt_id : resolved)
        resolved_ids.push_back(quilt_id);

    J group = {
        {"quilt_ids", resolved_ids},
        {"quilt_count", (int)resolved.size()},
        {"face_count", measurement.face_count},
        {"faces", faces},
        {"boundary_edges",
         measurement.edges_available ? J(measurement.boundary_edges) : J(nullptr)},
        {"joined_edges", measurement.edges_available ? J(measurement.joined_edges) : J(nullptr)},
        {"open_edges", measurement.edges_available ? J(measurement.open_edges) : J(nullptr)},
        {"open_edges_status", open_edges_status},
        {"gap_max_mm", gap_max_mm},
        {"gap_max_status", gap_status},
        {"overlap_area_mm2", overlap_area_mm2},
        {"overlap_status", overlap_status},
        {"overlap_pairs", measurement.overlap_pair_records},
        {"state", measurement.state ? J(measurement.state) : J(nullptr)},
        {"state_reason", measurement.state_reason ? J(measurement.state_reason) : J(nullptr)},
        {"boundary_closed",
         measurement.edges_available ? J(measurement.open_edges == 0) : J(nullptr)},
        {"tolerance_mm", tolerance_mm},
        {"gap_search_mm", gap_search_mm}};
    return {{"unit_name", units.length.name[0] ? J(utf8(units.length.name)) : J(nullptr)},
            {"length_scale_to_mm", scaled ? J(scale.scale) : J(nullptr)},
            {"group", group}};
}

static void generic_surface_group_measure(const J &op) {
    const J &references = op.at("references");
    if (!references.is_array() || references.empty())
        throw std::runtime_error("surface_group_measure requires at least one quilt reference");
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    std::vector<int> quilt_ids;
    for (const auto &reference : references) {
        ProSelection resolved = resolve_quilt_reference(reference, (ProSolid)board, units, scale);
        const int quilt_id = quilt_selection_id(resolved);
        if (std::find(quilt_ids.begin(), quilt_ids.end(), quilt_id) != quilt_ids.end())
            throw std::runtime_error("surface_group_measure references quilt " +
                                     std::to_string(quilt_id) + " more than once");
        quilt_ids.push_back(quilt_id);
    }
    const double tolerance_mm = op.value("tolerance_mm", 0.01);
    const double gap_search_mm = op.value("gap_search_mm", 1.0);
    if (!(tolerance_mm > 0.0) || !(gap_search_mm >= tolerance_mm))
        throw std::runtime_error("surface_group_measure needs tolerance_mm > 0 and "
                                 "gap_search_mm >= tolerance_mm");

    J details = surface_group_receipt(quilt_ids, tolerance_mm, gap_search_mm);
    details["op"] = "surface_group_measure";
    details["tolerance_mm"] = tolerance_mm;
    details["gap_search_mm"] = gap_search_mm;
    stage_operation_result(details);

    // A group whose boundary could not be visited is a failed operation:
    // success with a shape of nulls would hide that nothing was read.
    const J &status = details["group"]["open_edges_status"];
    if (!status["available"].get<bool>())
        throw std::runtime_error(
            std::string("surface_group_measure could not visit the group boundary") +
            (status["reason"].is_string() ? ": " + status["reason"].get<std::string>() : ""));
}
