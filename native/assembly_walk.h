// BUG-080/FEAT-045: shared assembly-walk bookkeeping state. The production
// walk callback in generic.cpp and the offline harness
// (tests/native/test_assembly_walk.cpp) execute these exact state changes, so
// the failure-path coverage exercises the shipped code instead of a copy.
#pragma once

#include "assembly_units.h"

// Hard depth limit for the assembly walk: a sub-assembly exactly at this
// depth is recorded but its subtree is not visited.
inline constexpr int kAssemblyWalkMaxDepth = 32;

// The walk report's mutable state: recorded nodes plus the truncated /
// incomplete / depth_limited judgements the production callback makes. Every
// mutation the walk performs on this state lives here and only here.
struct AssemblyWalkState {
    nlohmann::json components = nlohmann::json::array();
    bool truncated = false;
    bool incomplete = false;
    bool depth_limited = false;
    int budget = 0;

    // Records one fully-built node and applies the budget rule: the node is
    // kept, but once the budget is reached the walk stops after it. Returns
    // the node's index for later in-place diagnosis updates.
    size_t record_node(const nlohmann::json &item) {
        components.push_back(item);
        if ((int)components.size() >= budget)
            truncated = true;
        return components.size() - 1;
    }

    // Missing component model: the node stays observable, stamped here with
    // resolved=false and subtree_not_visited=true (the single place those
    // flags are decided), its whole subtree is unvisited, and the report can
    // no longer claim completeness. The caller passes only the node's known
    // unresolved identity shape (null name/model type, empty constraints).
    size_t record_missing_component(const nlohmann::json &item) {
        nlohmann::json node = item;
        node["resolved"] = false;
        node["subtree_not_visited"] = true;
        const size_t index = record_node(node);
        incomplete = true;
        return index;
    }

    // Any per-node query failure (feature type/status, child model type, or
    // an unconfirmed transform/unit chain): the node stays observable but
    // completeness is dropped; already-recorded siblings are never removed.
    void mark_incomplete() {
        incomplete = true;
    }

    // Applies one real SDK query outcome — the same judgement the production
    // callback makes for feature type, feature status and child model type
    // queries: a non-zero code drops completeness while the node stays
    // observable; PRO_TK_NO_ERROR changes nothing. Returns whether the query
    // succeeded so callers can keep their per-code branches.
    bool apply_query_outcome(ProError code) {
        if (code != PRO_TK_NO_ERROR) {
            incomplete = true;
            return false;
        }
        return true;
    }

    // A failed sub-assembly visit is diagnosed on the stored node at
    // node_index — never on components.back(), which later descendants may
    // already have shifted.
    void record_subassembly_visit_failure(size_t node_index, ProError code) {
        components[node_index]["subassembly_visit_code"] = (int)code;
        incomplete = true;
    }

    // Depth hard limit: a sub-assembly at the limit is recorded but its
    // subtree is not visited.
    bool descend_allowed(int depth) const {
        return depth < kAssemblyWalkMaxDepth;
    }
    void record_depth_limit() {
        depth_limited = true;
    }

    // The single sub-tree visit operation, shared by the production callback
    // (around ProSolidFeatVisit) and the offline harness: the depth limit is
    // enforced before the visitor ever runs, and a non-zero visit outcome is
    // diagnosed on the stored node at node_index — never on
    // components.back(), which later descendants may already have shifted.
    // Returns true when the visitor actually ran.
    template <typename Visitor> bool visit_subtree(int depth, size_t node_index, Visitor visitor) {
        if (!descend_allowed(depth)) {
            record_depth_limit();
            return false;
        }
        const ProError code = visitor();
        if (code != PRO_TK_NO_ERROR)
            record_subassembly_visit_failure(node_index, code);
        return true;
    }

    // Root-level initialization, shared with the offline harness: the root
    // chain's normalized validity is exactly the root unit's knownness (the
    // raw chain stays the real identity), and an unknown root unit marks the
    // report incomplete here — the single place that judgement is made, so
    // even an empty tree is globally incomplete then. Returns the root unit
    // knownness for the report's complete rule.
    bool init_root_chain(WalkChain &chain, const MillimeterScale &root_scale) {
        chain.normalized_known = root_scale.known;
        if (!root_scale.known)
            record_root_unit_unknown();
        return root_scale.known;
    }

    // Root-level failures keep every already-recorded node observable.
    void record_root_visit_failure() {
        incomplete = true;
    }
    void record_root_unit_unknown() {
        incomplete = true;
    }

    bool complete(bool root_unit_known) const {
        return walk_report_complete(truncated, incomplete, depth_limited, root_unit_known);
    }
};
