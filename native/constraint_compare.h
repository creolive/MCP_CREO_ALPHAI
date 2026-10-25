// Saved-assembly constraint verification comparison (FEAT-008 batch 2 stage 3).
//
// verify_saved (generic.cpp) compares a persisted checkpoint inspection against
// a freshly queried inspection. Checkpoints recorded before inspect_constraints
// (advanced.cpp) added the display-only "type_name" symbol carry only the
// numeric fields (for example {"type":13}), while new queries carry the same
// numeric fields plus the readable symbol ({"type":13,"type_name":"fix"}). A
// strict whole-JSON compare then misreports unchanged constraints as "Saved
// assembly constraints changed" and blocks every later edit of those old
// assemblies.
//
// This helper projects ONLY the display-only "type_name" key out of the
// compatibility comparison. The numeric SDK type code, offsets, assembly and
// component references, datum sides, and the constraint count and order stay
// fully verified; no stored checkpoint is rewritten and constraint verification
// as a whole is never skipped.
#pragma once

#include "third_party/json.hpp"

namespace mechdog_constraints {

// Constraint snapshot without display-only symbols. "type_name" is the only
// projected key; everything else (numeric type, offset, assembly/component
// references, sides) is preserved for the equality check. Non-array payloads
// pass through unchanged so a malformed comparison still fails closed.
inline nlohmann::json verification_view(const nlohmann::json &constraints) {
    nlohmann::json projected = constraints;
    if (projected.is_array()) {
        for (auto &item : projected) {
            if (item.is_object())
                item.erase("type_name");
        }
    }
    return projected;
}

// Compatibility equality for saved-reload constraint verification. The
// display-only type_name may differ between an old checkpoint and a new query
// describing the same physical constraint; every other field, the element
// count and the element order must match exactly.
inline bool match_for_verification(const nlohmann::json &before, const nlohmann::json &after) {
    return verification_view(before) == verification_view(after);
}

} // namespace mechdog_constraints
