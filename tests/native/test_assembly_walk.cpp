// BUG-080/FEAT-045 offline assembly-walk bookkeeping check: drives the exact
// AssemblyWalkState implementation the production callback in generic.cpp
// executes (native/assembly_walk.h), with substituted SDK unit queries and no
// Creo connection.
#include "assembly_walk.h"

#include <cassert>
#include <cstdio>
#include <cwchar>

static ProError principal_code = PRO_TK_NO_ERROR;
static ProError length_code = PRO_TK_NO_ERROR;
static const wchar_t *length_name = L"mm";
static ProError mm_init_code = PRO_TK_NO_ERROR;
static ProError conversion_code = PRO_TK_NO_ERROR;
static double conversion_scale = 1.0;
static double conversion_offset = 0.0;

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
    if (mm_init_code)
        return mm_init_code;
    assert(!wcscmp(unit_name, L"mm"));
    wcscpy_s(unit->name, L"mm");
    return PRO_TK_NO_ERROR;
}

ProError ProUnitConversionCalculate(ProUnititem *, ProUnititem *, ProUnitConversion *conversion) {
    if (conversion_code)
        return conversion_code;
    conversion->scale = conversion_scale;
    conversion->offset = conversion_offset;
    return PRO_TK_NO_ERROR;
}

static nlohmann::json resolved_node(int id) {
    return {{"component_id", id}, {"resolved", true}};
}

// The bare unresolved-node identity shape the production callback builds for
// a missing component model: null name/model type and empty constraints. The
// resolved/subtree flags are deliberately absent — stamping them is the
// behavior of the shared production operation under test.
static nlohmann::json unresolved_node(int id) {
    return {{"component_id", id},
            {"name", nullptr},
            {"model_type", nullptr},
            {"constraints", nlohmann::json::array()}};
}

int main() {
    ProMdl model = nullptr; // Never dereferenced by the substituted SDK calls.

    // 1. Healthy walk through the production state: nodes record in order and
    //    the report is complete only with a known root unit.
    {
        AssemblyWalkState walk;
        walk.budget = 4096;
        for (int id = 1; id <= 3; ++id)
            walk.record_node(resolved_node(id));
        assert(walk.components.size() == 3);
        assert(!walk.truncated && !walk.incomplete && !walk.depth_limited);
        assert(walk.complete(true));
        assert(!walk.complete(false)); // unknown root unit: never complete
    }

    // 2. Budget contract at the production value: node 4096 is recorded, and
    //    only then does the walk turn truncated.
    {
        AssemblyWalkState walk;
        walk.budget = 4096;
        for (int id = 1; id < 4096; ++id)
            walk.record_node(resolved_node(id));
        assert(walk.components.size() == 4095 && !walk.truncated);
        walk.record_node(resolved_node(4096));
        assert(walk.components.size() == 4096 && walk.truncated);
        assert(!walk.complete(true));
    }

    // 3. Small-budget boundary: the walk stops right after the budget-th node.
    {
        AssemblyWalkState walk;
        walk.budget = 3;
        walk.record_node(resolved_node(1));
        walk.record_node(resolved_node(2));
        assert(!walk.truncated);
        walk.record_node(resolved_node(3));
        assert(walk.truncated && walk.components.size() == 3);
    }

    // 4. Missing component: the shared production operation itself stamps
    //    resolved=false and subtree_not_visited on the node it records, drops
    //    completeness, and a sibling recorded after the failure stays
    //    observable.
    {
        AssemblyWalkState walk;
        walk.budget = 4096;
        walk.record_node(resolved_node(1));
        const size_t missing = walk.record_missing_component(unresolved_node(2));
        walk.record_node(resolved_node(3));
        assert(missing == 1);
        assert(walk.components[1].value("resolved", true) == false);
        assert(walk.components[1].value("subtree_not_visited", false));
        assert(walk.incomplete && !walk.truncated);
        assert(walk.components.size() == 3); // sibling nodes are not lost
        assert(!walk.complete(true));
    }

    // 5. Missing component at budget: truncated and incomplete together.
    {
        AssemblyWalkState walk;
        walk.budget = 2;
        walk.record_node(resolved_node(1));
        walk.record_missing_component(unresolved_node(2));
        assert(walk.incomplete && walk.truncated);
    }

    // 6. Per-query outcomes through the shared production judgement: each
    //    real non-zero SDK code drops completeness on its own fresh state
    //    while already-recorded siblings stay observable, and the real
    //    success code leaves completeness untouched.
    {
        const ProError failures[] = {PRO_TK_GENERAL_ERROR, PRO_TK_E_NOT_FOUND};
        for (ProError code : failures) {
            AssemblyWalkState walk;
            walk.budget = 4096;
            walk.record_node(resolved_node(1));
            assert(!walk.apply_query_outcome(code));
            walk.record_node(resolved_node(2));
            assert(walk.incomplete && walk.components.size() == 2);
            assert(!walk.complete(true));
        }
        AssemblyWalkState ok;
        ok.budget = 4096;
        assert(ok.apply_query_outcome(PRO_TK_NO_ERROR));
        assert(!ok.incomplete);
        ok.record_node(resolved_node(1));
        assert(ok.complete(true));
    }

    // 7. Sub-assembly visit failure lands on the actual node: descendants are
    //    recorded after the parent (shifting components.back()), and the code
    //    must still be written to node_index, never to the last element.
    {
        AssemblyWalkState walk;
        walk.budget = 4096;
        const size_t parent = walk.record_node(resolved_node(10));
        walk.record_node(resolved_node(11)); // nested visit records children
        walk.record_node(resolved_node(12));
        walk.record_subassembly_visit_failure(parent, PRO_TK_GENERAL_ERROR);
        assert(walk.components[parent].value("subassembly_visit_code", 0) ==
               (int)PRO_TK_GENERAL_ERROR);
        assert(!walk.components[1].contains("subassembly_visit_code"));
        assert(!walk.components[2].contains("subassembly_visit_code"));
        assert(walk.incomplete && !walk.truncated && !walk.depth_limited);
        assert(!walk.complete(true));
    }

    // 8. Depth boundary at the production limit 32 through the shared visit
    //    operation: the injected visitor genuinely is not invoked at depths
    //    32/33 (no descendant nodes can appear) and depth_limited is reported;
    //    at depth 31 the visitor runs once, appends descendants, and its
    //    failure code is diagnosed on the parent node index — never on the
    //    nodes appended after the parent.
    {
        AssemblyWalkState limited;
        limited.budget = 4096;
        int limited_calls = 0;
        const size_t limited_node = limited.record_node(resolved_node(1));
        const bool ran_at_32 = limited.visit_subtree(32, limited_node, [&]() -> ProError {
            ++limited_calls;
            return PRO_TK_NO_ERROR;
        });
        assert(!ran_at_32 && limited_calls == 0); // subtree genuinely not visited
        assert(limited.depth_limited);
        assert(limited.components.size() == 1);
        assert(!limited.incomplete); // depth limit is not incompleteness
        assert(!limited.complete(true));

        AssemblyWalkState failed;
        failed.budget = 4096;
        const size_t parent = failed.record_node(resolved_node(2));
        int failed_calls = 0;
        assert(failed.visit_subtree(31, parent, [&]() -> ProError {
            ++failed_calls;
            failed.record_node(resolved_node(3)); // descendants appended by the visit
            failed.record_node(resolved_node(4));
            return PRO_TK_GENERAL_ERROR; // ... which then fails
        }));
        assert(failed_calls == 1);
        assert(failed.components[parent].value("subassembly_visit_code", 0) ==
               (int)PRO_TK_GENERAL_ERROR);
        assert(!failed.components[parent + 1].contains("subassembly_visit_code"));
        assert(!failed.components[parent + 2].contains("subassembly_visit_code"));
        assert(failed.incomplete && !failed.depth_limited);
        assert(!failed.complete(true));

        AssemblyWalkState deep;
        deep.budget = 4096;
        int deep_calls = 0;
        assert(!deep.visit_subtree(33, 0, [&]() -> ProError {
            ++deep_calls;
            return PRO_TK_NO_ERROR;
        }));
        assert(deep_calls == 0 && deep.depth_limited);
    }

    // 9. Root visit failure keeps the already-recorded sibling nodes (the
    //    report is incomplete, not discarded).
    {
        AssemblyWalkState walk;
        walk.budget = 4096;
        walk.record_node(resolved_node(1));
        walk.record_node(resolved_node(2));
        walk.record_root_visit_failure();
        assert(walk.incomplete && walk.components.size() == 2);
        assert(!walk.complete(true));
    }

    // 10. Root unit known: invoked with the real root_scale from
    //     length_scale_to_mm against the substituted SDK, the shared root
    //     initialization composes a real first-level root map on both chains
    //     and an empty tree stays complete.
    {
        principal_code = PRO_TK_NO_ERROR;
        length_code = PRO_TK_NO_ERROR;
        mm_init_code = PRO_TK_NO_ERROR;
        conversion_code = PRO_TK_NO_ERROR;
        length_name = L"mm";
        conversion_scale = 1.0;
        conversion_offset = 0.0;
        MillimeterScale root_scale = length_scale_to_mm(model, inspect_length_units(model));
        assert(root_scale.known);
        AssemblyWalkState walk;
        walk.budget = 4096;
        WalkChain root_chain;
        assert(walk.init_root_chain(root_chain, root_scale));
        assert(root_chain.normalized_known);
        ProMatrix local = {};
        for (int i = 0; i < 4; ++i)
            local[i][i] = 1.0;
        local[3][0] = 20.0;
        WalkChainStep step = walk_chain_compose(root_chain, local, true, local, true);
        assert(step.root_mm_known && step.root_raw_known);
        assert(walk.complete(root_scale.known));
    }

    // 11. Root unit query fails for real (substituted SDK error): the same
    //     shared initialization makes the root mm chain unknown while the
    //     raw chain survives, marks the report incomplete itself, and the
    //     complete rule fires.
    {
        length_code = PRO_TK_E_NOT_FOUND;
        MillimeterScale root_scale = length_scale_to_mm(model, inspect_length_units(model));
        assert(!root_scale.known);
        AssemblyWalkState walk;
        walk.budget = 4096;
        WalkChain root_chain;
        assert(!walk.init_root_chain(root_chain, root_scale));
        assert(!root_chain.normalized_known);
        ProMatrix local = {};
        for (int i = 0; i < 4; ++i)
            local[i][i] = 1.0;
        local[3][0] = 20.0;
        WalkChainStep step = walk_chain_compose(root_chain, local, true, local, true);
        assert(!step.root_mm_known && step.root_raw_known);
        assert(walk.incomplete); // the shared initialization marked it
        assert(!walk.complete(root_scale.known));
        length_code = PRO_TK_NO_ERROR;
    }

    // 12. Truncation does not mask a depth limit or incompleteness: the
    //     shared complete rule reports incomplete whenever any flag is set.
    {
        AssemblyWalkState walk;
        walk.budget = 1;
        walk.record_missing_component(unresolved_node(1));
        assert(walk.truncated && walk.incomplete);
        walk.record_depth_limit();
        assert(!walk.complete(true));
    }

    std::puts("ASSEMBLY_WALK_OK cases=12; shared production walk state, SDK calls "
              "substituted, no Toolkit connection");
    return 0;
}
