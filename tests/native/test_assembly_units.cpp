// BUG-080/FEAT-045 offline unit-scale and transform-normalization check with
// real SDK declarations and substituted results; no Creo connection.
#include "assembly_units.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cwchar>
#include <limits>

static ProError principal_code = PRO_TK_NO_ERROR;
static ProError length_code = PRO_TK_NO_ERROR;
static const wchar_t *length_name = L"mm";
static ProError mm_init_code = PRO_TK_NO_ERROR;
static ProError conversion_code = PRO_TK_NO_ERROR;
static double conversion_scale = 1.0;
static double conversion_offset = 0.0;
static int mm_init_calls = 0;
static int conversion_calls = 0;

ProError ProMdlPrincipalunitsystemGet(ProMdl, ProUnitsystem *) {
    return principal_code;
}

ProError ProUnitsystemUnitGet(ProUnitsystem *, ProUnitType type, ProUnititem *unit) {
    assert(type == PRO_UNITTYPE_LENGTH);
    if (!length_code)
        wcscpy_s(unit->name, length_name);
    return length_code;
}

ProError ProUnitInit(ProMdl, ProName unit_name, ProUnititem *unit) {
    ++mm_init_calls;
    if (mm_init_code)
        return mm_init_code;
    assert(!wcscmp(unit_name, L"mm"));
    wcscpy_s(unit->name, L"mm");
    return PRO_TK_NO_ERROR;
}

ProError ProUnitConversionCalculate(ProUnititem *, ProUnititem *, ProUnitConversion *conversion) {
    ++conversion_calls;
    if (conversion_code)
        return conversion_code;
    conversion->scale = conversion_scale;
    conversion->offset = conversion_offset;
    return PRO_TK_NO_ERROR;
}

static bool near(double a, double b) {
    return std::fabs(a - b) <= 1e-9 * (1.0 + std::fabs(b));
}

static void expect_point(const ProMatrix m, const double (&p)[3], double x, double y, double z) {
    double out[3];
    transform_point(m, p, out);
    assert(near(out[0], x) && near(out[1], y) && near(out[2], z));
}

// Row-vector Rz(90deg) with translation (2,3,4) in owner units. The linear
// part is scaled by `linear` and the translation by `translation` so the same
// physical pose can be expressed with different source/owner unit pairs.
static void rotation_translation_matrix(ProMatrix m, double linear = 1.0,
                                        double translation = 1.0) {
    const double r[4][4] = {{0.0, linear, 0.0, 0.0},
                            {-linear, 0.0, 0.0, 0.0},
                            {0.0, 0.0, linear, 0.0},
                            {2.0 * translation, 3.0 * translation, 4.0 * translation, 1.0}};
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            m[i][j] = r[i][j];
}

static MillimeterScale query_scale(ProMdl model, const wchar_t *name, double scale) {
    length_name = name;
    conversion_scale = scale;
    return length_scale_to_mm(model, inspect_length_units(model));
}

int main() {
    ProMdl model = nullptr; // Never dereferenced by the substituted SDK calls.

    // 1-3. mm / inch / centimeter scales through the real conversion path.
    auto s = query_scale(model, L"mm", 1.0);
    assert(s.known && s.scale == 1.0 && s.unit_query_code == PRO_TK_NO_ERROR);
    s = query_scale(model, L"in", 25.4);
    assert(s.known && s.scale == 25.4);
    s = query_scale(model, L"cm", 10.0);
    assert(s.known && s.scale == 10.0);

    // 4. Unit query failure: no conversion attempted, codes preserved.
    mm_init_calls = conversion_calls = 0;
    length_code = PRO_TK_E_NOT_FOUND;
    s = length_scale_to_mm(model, inspect_length_units(model));
    assert(!s.known && s.unit_query_code == PRO_TK_E_NOT_FOUND && mm_init_calls == 0);
    length_code = PRO_TK_NO_ERROR;

    // 5. mm unit init failure is reported separately from conversion failure.
    mm_init_code = PRO_TK_BAD_INPUTS;
    s = query_scale(model, L"mm", 1.0);
    assert(!s.known && s.unit_query_code == PRO_TK_NO_ERROR &&
           s.mm_unit_query_code == PRO_TK_BAD_INPUTS && s.conversion_query_code == PRO_TK_NO_ERROR);
    mm_init_code = PRO_TK_NO_ERROR;

    // 6. Conversion failure keeps its own code.
    conversion_code = PRO_TK_GENERAL_ERROR;
    s = query_scale(model, L"in", 25.4);
    assert(!s.known && s.conversion_query_code == PRO_TK_GENERAL_ERROR);
    conversion_code = PRO_TK_NO_ERROR;

    // 7. Non-finite, non-positive scales and a nonzero offset are rejected.
    conversion_scale = 0.0;
    assert(!query_scale(model, L"in", 0.0).known);
    conversion_scale = -25.4;
    assert(!query_scale(model, L"in", -25.4).known);
    conversion_scale = std::nan("");
    assert(!query_scale(model, L"in", std::nan("")).known);
    conversion_scale = std::numeric_limits<double>::infinity();
    assert(!query_scale(model, L"in", std::numeric_limits<double>::infinity()).known);
    conversion_scale = 25.4;
    conversion_offset = 1.0; // temperature-style offset: invalid for length
    assert(!query_scale(model, L"in", 25.4).known);
    conversion_offset = 0.0;

    // 8. mm -> mm normalization is the identity scaling.
    ProMatrix raw = {}, norm = {};
    rotation_translation_matrix(raw);
    assert(normalize_transform_mm(raw, 1.0, 1.0, norm));
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            assert(norm[i][j] == raw[i][j]);

    // 9. Physical pose Rz90 + T(2,3,4) mm, source-inch -> parent-mm. The raw
    // Creo matrix carries 25.4*R (inch inputs) with the (2,3,4) mm translation
    // untouched; the full map restores R and keeps the mm translation. A
    // translation-only scaling would wrongly keep the 25.4 rotation factor.
    ProMatrix raw_inch_source = {};
    rotation_translation_matrix(raw_inch_source, 25.4);
    assert(normalize_transform_mm(raw_inch_source, 25.4, 1.0, norm));
    assert(near(norm[0][1], 1.0) && near(norm[1][0], -1.0));
    assert(near(norm[3][0], 2.0) && near(norm[3][1], 3.0) && near(norm[3][2], 4.0));
    // (50.8,25.4,76.2) mm == (2,1,3) in; hand-computed: (2-25.4, 50.8+3, 76.2+4).
    expect_point(norm, {50.8, 25.4, 76.2}, -23.4, 53.8, 80.2);

    // 10. Three basis vectors plus a non-origin point on the mm/mm map.
    expect_point(raw, {1.0, 0.0, 0.0}, 2.0, 4.0, 4.0);
    expect_point(raw, {0.0, 1.0, 0.0}, 1.0, 3.0, 4.0);
    expect_point(raw, {0.0, 0.0, 1.0}, 2.0, 3.0, 5.0);
    expect_point(raw, {2.0, 1.0, 3.0}, -1.0 + 2.0, 2.0 + 3.0, 3.0 + 4.0);

    // 11. Same physical pose, source-mm -> parent-inch: raw carries R/25.4
    // with the (2,3,4) translation in native inches; the full map restores R
    // and rescales the translation back to millimeters.
    ProMatrix raw_inch_owner = {};
    rotation_translation_matrix(raw_inch_owner, 1.0 / 25.4, 1.0 / 25.4);
    assert(normalize_transform_mm(raw_inch_owner, 1.0, 25.4, norm));
    assert(near(norm[0][1], 1.0) && near(norm[1][0], -1.0));
    assert(near(norm[3][0], 2.0) && near(norm[3][1], 3.0) && near(norm[3][2], 4.0));
    // (25.4,0,0) mm; hand-computed: (2-0, 25.4+3, 0+4).
    expect_point(norm, {25.4, 0.0, 0.0}, 2.0, 28.4, 4.0);

    // 12. Invalid scales refuse normalization instead of emitting garbage.
    assert(!normalize_transform_mm(raw, 0.0, 1.0, norm));
    assert(!normalize_transform_mm(raw, 1.0, -1.0, norm));
    assert(!normalize_transform_mm(raw, std::nan(""), 1.0, norm));

    // 13. Nested source-inch -> parent-cm -> root-mm. First physical transform
    // I + T(10,0,0) mm (raw: 2.54*I linear, (1,0,0) cm translation); second
    // physical transform Rz90 + T(2,3,4) mm (raw: 10*R linear, (2,3,4) mm
    // translation). Both the raw chain and the normalized chain must land on
    // the same hand-computed physical point for p = (1,2,3) mm: (1,2,3) ->
    // (11,2,3) -> (2-2, 11+3, 3+4) = (0,14,7) mm.
    ProMatrix first_raw = {}, second_raw = {}, product_raw = {}, product_norm = {};
    ProMatrix first_norm = {}, second_norm = {};
    first_raw[0][0] = first_raw[1][1] = first_raw[2][2] = 2.54;
    first_raw[3][0] = 1.0;
    first_raw[3][3] = 1.0;
    rotation_translation_matrix(second_raw, 10.0);
    assert(normalize_transform_mm(first_raw, 25.4, 10.0, first_norm));  // inch -> cm
    assert(normalize_transform_mm(second_raw, 10.0, 1.0, second_norm)); // cm -> mm
    multiply_row_vector(first_raw, second_raw, product_raw);
    multiply_row_vector(first_norm, second_norm, product_norm);
    double stage[3], direct_raw[3], direct_norm[3];
    const double p[3] = {1.0, 2.0, 3.0};
    transform_point(first_norm, p, stage);
    transform_point(second_norm, stage, stage); // aliased out==point must be safe
    // The raw chain consumes source-native (inch) coordinates.
    const double p_native[3] = {p[0] / 25.4, p[1] / 25.4, p[2] / 25.4};
    transform_point(product_raw, p_native, direct_raw);
    transform_point(product_norm, p, direct_norm);
    assert(near(stage[0], 0.0) && near(stage[1], 14.0) && near(stage[2], 7.0));
    assert(near(direct_raw[0], 0.0) && near(direct_raw[1], 14.0) && near(direct_raw[2], 7.0));
    assert(near(direct_norm[0], 0.0) && near(direct_norm[1], 14.0) && near(direct_norm[2], 7.0));

    // 14. Non-finite raw entries (NaN/Infinity) refuse normalization instead
    // of emitting JSON-null "known" transforms; the output map is untouched.
    ProMatrix bad = {};
    rotation_translation_matrix(bad);
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            norm[i][j] = -777.0;
    bad[1][2] = std::nan("");
    assert(!normalize_transform_mm(bad, 1.0, 1.0, norm));
    bad[1][2] = std::numeric_limits<double>::infinity();
    assert(!normalize_transform_mm(bad, 1.0, 1.0, norm));
    assert(norm[0][0] == -777.0 && norm[3][3] == -777.0); // rejected: no auto-fix write

    // 15. Finite inputs whose normalization overflows stay unknown as well.
    ProMatrix huge = {};
    huge[0][0] = 1.0e308;
    huge[3][3] = 1.0;
    assert(!normalize_transform_mm(huge, 1.0, 25.4, norm));     // output column overflow
    assert(!normalize_transform_mm(huge, 1.0e-308, 1.0, norm)); // input row overflow

    // 16. Same-unit inch -> inch still rescales the translation: raw R +
    // T(2,3,4) inch with both scales 25.4 yields R + T(50.8,76.2,101.6) mm.
    rotation_translation_matrix(raw); // raw R + T(2,3,4) inch
    assert(normalize_transform_mm(raw, 25.4, 25.4, norm));
    assert(near(norm[3][0], 50.8) && near(norm[3][1], 76.2) && near(norm[3][2], 101.6));
    // (25.4,0,0) mm == (1,0,0) in; hand-computed: (50.8-0, 25.4+76.2, 0+101.6).
    expect_point(norm, {25.4, 0.0, 0.0}, 50.8, 101.6, 101.6);

    // 17. Default root chain: the real identity on both chains with
    // independent known states; a physical point passes through unchanged.
    WalkChain root_chain;
    assert(root_chain.normalized_known && root_chain.raw_known);
    expect_point(root_chain.normalized_mm, {4.0, 5.0, 6.0}, 4.0, 5.0, 6.0);
    expect_point(root_chain.raw, {4.0, 5.0, 6.0}, 4.0, 5.0, 6.0);

    // 18. First-level and nested composition through the shared production
    // helper: pure-mm translations (20,0,0) then (0,5,0), raw and mm chains.
    ProMatrix local_a = {}, local_b = {};
    for (int i = 0; i < 4; ++i)
        local_a[i][i] = local_b[i][i] = 1.0;
    local_a[3][0] = 20.0;
    local_b[3][1] = 5.0;
    WalkChainStep first = walk_chain_compose(root_chain, local_a, true, local_a, true);
    assert(first.root_mm_known && first.root_raw_known);
    expect_point(first.to_root_mm, {1.0, 2.0, 3.0}, 21.0, 2.0, 3.0);
    expect_point(first.to_root_raw, {1.0, 2.0, 3.0}, 21.0, 2.0, 3.0);
    WalkChain level_one = walk_chain_descend(root_chain, first);
    WalkChainStep second = walk_chain_compose(level_one, local_b, true, local_b, true);
    assert(second.root_mm_known && second.root_raw_known);
    expect_point(second.to_root_mm, {1.0, 2.0, 3.0}, 21.0, 7.0, 3.0);
    expect_point(second.to_root_raw, {1.0, 2.0, 3.0}, 21.0, 7.0, 3.0);

    // 19. A failed parent transform poisons the descendant chains: the
    // grandchild's root maps stay unknown even though its own local maps are
    // known, and the failed node's known local map itself stays intact.
    WalkChainStep failed = walk_chain_compose(root_chain, local_a, false, local_a, false);
    assert(!failed.root_raw_known && !failed.root_mm_known);
    WalkChain broken = walk_chain_descend(root_chain, failed);
    assert(!broken.raw_known && !broken.normalized_known);
    WalkChainStep grandchild = walk_chain_compose(broken, local_b, true, local_b, true);
    assert(!grandchild.root_raw_known && !grandchild.root_mm_known);
    expect_point(local_b, {1.0, 2.0, 3.0}, 1.0, 7.0, 3.0); // local map preserved

    // 20. Ancestor unit unknown: the normalized chain stays unknown while
    // the raw chain survives as long as the real raw chain is still valid.
    WalkChain unit_unknown = root_chain;
    unit_unknown.normalized_known = false;
    WalkChainStep kept_raw = walk_chain_compose(unit_unknown, local_a, true, local_a, true);
    assert(kept_raw.root_raw_known && !kept_raw.root_mm_known);

    // 21. Finite inputs whose product overflows poison the chain instead of
    // emitting known maps with null entries: a lone 1e200 local step against
    // the identity root stays finite, so the overflow needs a 1e200 parent
    // chain first and then a second 1e200 local step (1e200 * 1e200 -> inf).
    ProMatrix huge_local = {};
    for (int i = 0; i < 4; ++i)
        huge_local[i][i] = 1.0e200;
    WalkChainStep huge_parent = walk_chain_compose(root_chain, huge_local, true, huge_local, true);
    assert(huge_parent.root_mm_known && huge_parent.root_raw_known);
    WalkChain parent_chain = walk_chain_descend(root_chain, huge_parent);
    WalkChainStep overflow = walk_chain_compose(parent_chain, huge_local, true, huge_local, true);
    assert(!overflow.root_mm_known && !overflow.root_raw_known);
    WalkChain after_overflow = walk_chain_descend(parent_chain, overflow);
    assert(!after_overflow.raw_known && !after_overflow.normalized_known);

    // 22. The single completeness rule: every failure source - truncation,
    // missing component/subtree failure, depth limit, or an unknown root unit
    // on an empty tree - makes the report incomplete.
    assert(walk_report_complete(false, false, false, true));
    assert(!walk_report_complete(true, false, false, true));
    assert(!walk_report_complete(false, true, false, true));
    assert(!walk_report_complete(false, false, true, true));
    assert(!walk_report_complete(false, false, false, false));

    // 23. Query-status truthfulness: a query that never ran serializes as
    // null (never a fake success code); an executed query keeps its code,
    // and a failed mm-unit init means the conversion never ran.
    length_code = PRO_TK_E_NOT_FOUND;
    mm_init_calls = conversion_calls = 0;
    s = length_scale_to_mm(model, inspect_length_units(model));
    assert(!s.known && !s.mm_unit_queried && !s.conversion_queried && mm_init_calls == 0 &&
           conversion_calls == 0);
    assert(sdk_query_code_json(s.mm_unit_queried, s.mm_unit_query_code).is_null());
    assert(sdk_query_code_json(s.conversion_queried, s.conversion_query_code).is_null());
    length_code = PRO_TK_NO_ERROR;
    mm_init_code = PRO_TK_BAD_INPUTS;
    mm_init_calls = conversion_calls = 0;
    s = query_scale(model, L"mm", 1.0);
    assert(s.mm_unit_queried && s.mm_unit_query_code == PRO_TK_BAD_INPUTS &&
           !s.conversion_queried && conversion_calls == 0);
    assert(!sdk_query_code_json(s.mm_unit_queried, s.mm_unit_query_code).is_null());
    assert(sdk_query_code_json(s.conversion_queried, s.conversion_query_code).is_null());
    mm_init_code = PRO_TK_NO_ERROR;

    // 24. Real nested mixed-unit chains (inch -> cm -> mm, case 13 inputs)
    // through the shared production helper. The walk composes the parent step
    // (cm -> root mm) first and the child step (inch -> parent cm) second, so
    // the member-to-root map is local * parent = first * second, landing on
    // the same hand-computed physical point on both chains.
    WalkChainStep chain13a = walk_chain_compose(root_chain, second_raw, true, second_norm, true);
    assert(chain13a.root_mm_known && chain13a.root_raw_known);
    WalkChain chain13_one = walk_chain_descend(root_chain, chain13a);
    WalkChainStep chain13b = walk_chain_compose(chain13_one, first_raw, true, first_norm, true);
    assert(chain13b.root_mm_known && chain13b.root_raw_known);
    double via_chain13_mm[3], via_chain13_raw[3];
    transform_point(chain13b.to_root_mm, p, via_chain13_mm);
    transform_point(chain13b.to_root_raw, p_native, via_chain13_raw);
    assert(near(via_chain13_mm[0], 0.0) && near(via_chain13_mm[1], 14.0) &&
           near(via_chain13_mm[2], 7.0));
    assert(near(via_chain13_raw[0], 0.0) && near(via_chain13_raw[1], 14.0) &&
           near(via_chain13_raw[2], 7.0));

    // 25. BUG-080 follow-up failure determination: a failed transform query
    // (nonzero SDK code) never yields a known raw map, even when the entries
    // are finite; only a successful query with a finite matrix is known.
    assert(!local_transform_known(PRO_TK_GENERAL_ERROR, raw));
    assert(local_transform_known(PRO_TK_NO_ERROR, raw));

    // 26. A successful query that returned NaN/Infinity entries is not known:
    // bad raw values must not be serialized as a valid matrix (the production
    // node emits transform_known=false with a null raw map instead).
    ProMatrix non_finite = {};
    rotation_translation_matrix(non_finite);
    assert(matrix_entries_finite(non_finite));
    non_finite[2][1] = std::nan("");
    assert(!matrix_entries_finite(non_finite));
    assert(!local_transform_known(PRO_TK_NO_ERROR, non_finite));
    non_finite[2][1] = std::numeric_limits<double>::infinity();
    assert(!local_transform_known(PRO_TK_NO_ERROR, non_finite));

    // 27. The production gate feeds the shared chain composer: a non-finite
    // local step rejected by local_transform_known poisons this node's root
    // chains exactly like a failed local transform, while a finite sibling
    // still composes through the same identity root on both chains.
    WalkChainStep poisoned =
        walk_chain_compose(root_chain, non_finite,
                           local_transform_known(PRO_TK_NO_ERROR, non_finite), non_finite, false);
    assert(!poisoned.root_raw_known && !poisoned.root_mm_known);
    WalkChainStep healthy = walk_chain_compose(root_chain, local_b, true, local_b, true);
    assert(healthy.root_raw_known && healthy.root_mm_known);
    expect_point(healthy.to_root_mm, {1.0, 2.0, 3.0}, 1.0, 7.0, 3.0);

    std::puts("ASSEMBLY_UNITS_OK cases=27; SDK calls substituted, no Toolkit connection");
    return 0;
}
