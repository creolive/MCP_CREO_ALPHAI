// BUG-080/FEAT-045: real length-unit queries for assembly walk nodes and
// millimeter normalization of member-to-owner transforms. Read-only: queries
// unit metadata and conversions, never loads, modifies or regenerates models.
#pragma once

#include "inspection_units.h"

#include "third_party/json.hpp"

#include <ProMdlUnits.h>

#include <cmath>
#include <cwchar>

// Millimeter scale for one model's length unit: value_mm = native * scale.
// Every SDK query keeps its raw code so callers can tell a failed unit query
// apart from a failed conversion, and a queried flag so serialization can
// tell a query that never ran apart from a real success; known=false means
// the scale must not be guessed (BUG-080: never default unknown units to
// millimeters, and never report an unexecuted query as PRO_TK_NO_ERROR).
struct MillimeterScale {
    bool known = false;
    double scale = 1.0;
    ProError unit_query_code = PRO_TK_NO_ERROR;
    bool mm_unit_queried = false;
    ProError mm_unit_query_code = PRO_TK_NO_ERROR;
    bool conversion_queried = false;
    ProError conversion_query_code = PRO_TK_NO_ERROR;
};

// Converts the model's principal length unit to millimeters via the real SDK
// conversion: ProUnitInit for the model's own "mm" unit, then
// ProUnitConversionCalculate. Length conversions must be a finite positive
// pure scale (offset is temperature-only); anything else stays unknown.
inline MillimeterScale length_scale_to_mm(ProMdl mdl, const InspectionLengthUnits &units) {
    MillimeterScale result;
    result.unit_query_code = units.code;
    if (units.code != PRO_TK_NO_ERROR)
        return result;
    ProUnititem mm_unit = {};
    result.mm_unit_queried = true;
    result.mm_unit_query_code = ProUnitInit(mdl, L"mm", &mm_unit);
    if (result.mm_unit_query_code != PRO_TK_NO_ERROR)
        return result;
    ProUnititem from = units.length;
    ProUnitConversion conversion = {};
    result.conversion_queried = true;
    result.conversion_query_code = ProUnitConversionCalculate(&from, &mm_unit, &conversion);
    if (result.conversion_query_code != PRO_TK_NO_ERROR)
        return result;
    if (!std::isfinite(conversion.scale) || conversion.scale <= 0.0 || conversion.offset != 0.0)
        return result; // not a usable length scale: stay unknown, keep codes
    result.known = true;
    result.scale = conversion.scale;
    return result;
}

// Row-vector 4x4 composition out = a * b (p' = (p * a) * b). Single shared
// implementation used by the production assembly walk and the offline nested
// composition check, so both exercise the exact accumulation order of chained
// member-to-root maps (no duplicated logic, no divergent semantics).
inline void multiply_row_vector(const ProMatrix a, const ProMatrix b, ProMatrix out) {
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c) {
            double sum = 0.0;
            for (int k = 0; k < 4; ++k)
                sum += a[r][k] * b[k][c];
            out[r][c] = sum;
        }
}

// Serializes one SDK query outcome honestly (BUG-080 follow-up): null when
// the query never ran, the raw code when it did. A skipped mm-unit or
// conversion query must not surface as a fake PRO_TK_NO_ERROR success.
inline nlohmann::json sdk_query_code_json(bool queried, ProError code) {
    return queried ? nlohmann::json((int)code) : nlohmann::json(nullptr);
}

// BUG-080 follow-up: the assembly walk accumulates two independent
// member-to-root chains per node. The default state is the real identity on
// both chains with independent known flags: a lone assembly maps member
// coordinates to itself, and first-level root products are genuine
// transforms instead of zero-matrix artifacts.
struct WalkChain {
    ProMatrix normalized_mm = {
        {1.0, 0.0, 0.0, 0.0}, {0.0, 1.0, 0.0, 0.0}, {0.0, 0.0, 1.0, 0.0}, {0.0, 0.0, 0.0, 1.0}};
    ProMatrix raw = {
        {1.0, 0.0, 0.0, 0.0}, {0.0, 1.0, 0.0, 0.0}, {0.0, 0.0, 1.0, 0.0}, {0.0, 0.0, 0.0, 1.0}};
    bool normalized_known = true; // false once any ancestor mm chain step failed
    bool raw_known = true;        // false once any ancestor raw transform failed
};

inline bool matrix_entries_finite(const ProMatrix matrix) {
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c)
            if (!std::isfinite(matrix[r][c]))
                return false;
    return true;
}

// BUG-080 follow-up: the local raw map counts as known only when the query
// succeeded and every returned entry is finite; NaN/Infinity values would
// otherwise serialize as null inside a transform_known=true node. The matrix
// is inspected, never auto-fixed.
inline bool local_transform_known(ProError query_code, const ProMatrix matrix) {
    return query_code == PRO_TK_NO_ERROR && matrix_entries_finite(matrix);
}

// Per-node result of composing one member-to-parent step into the parent's
// accumulated chains. A root product exists only while every ancestor step
// and this node's local map stayed known; finite-input overflow poisons the
// chain (the product is dropped instead of being serialized as a known
// transform whose JSON values became null).
struct WalkChainStep {
    ProMatrix to_root_mm = {};
    ProMatrix to_root_raw = {};
    bool root_mm_known = false;
    bool root_raw_known = false;
};

// The single composition used by the production walk and the offline check:
// member-to-root = local member-to-parent * parent member-to-root. The raw
// chain needs only the raw local map; the millimeter chain additionally
// needs a confirmed local normalized map. Unknown ancestors never donate
// their matrix to descendants.
inline WalkChainStep walk_chain_compose(const WalkChain &parent, const ProMatrix &to_parent_raw,
                                        bool local_raw_known, const ProMatrix &to_parent_mm,
                                        bool local_mm_known) {
    WalkChainStep step;
    if (local_raw_known && parent.raw_known) {
        multiply_row_vector(to_parent_raw, parent.raw, step.to_root_raw);
        step.root_raw_known = matrix_entries_finite(step.to_root_raw);
    }
    if (local_mm_known && parent.normalized_known) {
        multiply_row_vector(to_parent_mm, parent.normalized_mm, step.to_root_mm);
        step.root_mm_known = matrix_entries_finite(step.to_root_mm);
    }
    return step;
}

// Descendant chain: only products that stayed known are carried down a
// level. The child's own known local maps stay intact — the failure is
// inherited as "root unknown", never as a reused grandparent matrix.
inline WalkChain walk_chain_descend(const WalkChain &parent, const WalkChainStep &step) {
    WalkChain sub = parent;
    sub.raw_known = step.root_raw_known;
    sub.normalized_known = step.root_mm_known;
    if (step.root_raw_known)
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 4; ++c)
                sub.raw[r][c] = step.to_root_raw[r][c];
    if (step.root_mm_known)
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 4; ++c)
                sub.normalized_mm[r][c] = step.to_root_mm[r][c];
    return sub;
}

// The single completeness rule for the walk report (shared with the offline
// harness): complete only when nothing truncated or depth-limited the walk,
// no node/subtree failure was recorded, and the root length unit is known —
// without it every normalized root map is uninterpretable, even on an empty
// tree.
inline bool walk_report_complete(bool truncated, bool incomplete, bool depth_limited,
                                 bool root_unit_known) {
    return !truncated && !incomplete && !depth_limited && root_unit_known;
}

// Row-vector convention p' = p * M (translation in the last row). The raw
// Creo member-to-owner matrix maps member-solid coordinates expressed in the
// member model's length unit into owner-solid coordinates expressed in the
// owner model's length unit. Normalization divides the first three input rows
// by member_scale and multiplies the first three output columns by
// owner_scale, yielding a full coordinate map with millimeters on both sides
// (rotation and translation both participate). Both scales must be known and
// positive; otherwise the caller reports the transform as unknown instead of
// emitting a fake millimeter matrix. BUG-080 follow-up: a non-finite raw
// entry, or finite inputs whose normalization overflows, is an unconfirmable
// map and is rejected as well (JSON would otherwise serialize NaN/Infinity as
// null and report a known transform). The output matrix is only written once
// every entry is verified finite; a rejected call never auto-fixes the map.
inline bool normalize_transform_mm(const ProMatrix raw, double member_scale, double owner_scale,
                                   ProMatrix out) {
    if (!std::isfinite(member_scale) || !std::isfinite(owner_scale) || member_scale <= 0.0 ||
        owner_scale <= 0.0)
        return false;
    ProMatrix normalized = {};
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c) {
            double value = raw[r][c];
            if (!std::isfinite(value))
                return false;
            if (r < 3)
                value /= member_scale;
            if (c < 3)
                value *= owner_scale;
            if (!std::isfinite(value))
                return false; // finite raw values overflowed: unconfirmable map
            normalized[r][c] = value;
        }
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c)
            out[r][c] = normalized[r][c];
    return true;
}

// Applies a row-vector 4x4 map to a physical point (implicit w = 1). The
// output may alias the input point (transform_point(m, p, p)); each output
// coordinate is fully computed into a local before any write, so an aliased
// call never reads a coordinate already overwritten by an earlier column.
inline void transform_point(const ProMatrix matrix, const double point[3], double out[3]) {
    const double x =
        point[0] * matrix[0][0] + point[1] * matrix[1][0] + point[2] * matrix[2][0] + matrix[3][0];
    const double y =
        point[0] * matrix[0][1] + point[1] * matrix[1][1] + point[2] * matrix[2][1] + matrix[3][1];
    const double z =
        point[0] * matrix[0][2] + point[1] * matrix[1][2] + point[2] * matrix[2][2] + matrix[3][2];
    out[0] = x;
    out[1] = y;
    out[2] = z;
}
