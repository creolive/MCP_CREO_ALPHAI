// Offline regression for the saved-assembly constraint verification comparison
// (native/constraint_compare.h). Compiles without Toolkit headers: the helper
// only projects the display-only "type_name" key out of the compatibility
// comparison so old checkpoints (numeric fields only) stay equivalent to new
// queries, while every real constraint change is still rejected. The first
// block reproduces the production defect that strict whole-JSON equality had.
#include "constraint_compare.h"

#include <cassert>
#include <cstdio>

using mechdog_constraints::match_for_verification;
using mechdog_constraints::verification_view;

int main() {
    // Production defect reproduction: a checkpoint recorded before
    // inspect_constraints added type_name holds only the numeric fields; the
    // new query of the same physical constraint adds the readable symbol.
    const nlohmann::json old_checkpoint = nlohmann::json::parse(R"([{"type":13}])");
    const nlohmann::json new_query = nlohmann::json::parse(R"([{"type":13,"type_name":"fix"}])");
    assert(old_checkpoint != new_query); // strict compare misreports changed
    assert(match_for_verification(old_checkpoint, new_query)); // compatible
    assert(match_for_verification(new_query, old_checkpoint)); // symmetric

    // Full constraint records: offset, both references and both sides stay
    // verified; only the display-only symbol is projected.
    const nlohmann::json old_mate = nlohmann::json::parse(R"([
        {"type":0,"offset":20.0,
         "assembly_reference":{"id":11,"type":1,"owner":"asm_a"},
         "assembly_side":1,
         "component_reference":{"id":7,"type":1,"owner":"part_b"},
         "component_side":2}
    ])");
    nlohmann::json new_mate = old_mate;
    new_mate[0]["type_name"] = "mate";
    assert(match_for_verification(old_mate, new_mate));
    // The projection must not mutate the caller's documents.
    assert(!old_mate[0].contains("type_name"));
    assert(new_mate[0].contains("type_name"));
    assert(verification_view(new_mate)[0].size() == old_mate[0].size());

    // Real changes must keep failing verification.
    auto reject = [](nlohmann::json before, nlohmann::json after) {
        assert(!match_for_verification(before, after));
        assert(!match_for_verification(after, before));
    };
    nlohmann::json changed = new_query;
    changed[0]["type"] = 0; // numeric type change (fix -> mate)
    reject(old_checkpoint, changed);
    changed = new_mate;
    changed[0]["offset"] = 21.0; // offset change
    reject(old_mate, changed);
    changed = new_mate;
    changed[0].erase("offset"); // offset disappeared
    reject(old_mate, changed);
    changed = new_mate;
    changed[0]["offset"] = nullptr; // offset became unknown
    reject(old_mate, changed);
    changed = new_mate;
    changed[0]["assembly_reference"]["id"] = 12; // reference change
    reject(old_mate, changed);
    changed = new_mate;
    changed[0]["component_reference"]["owner"] = "part_c"; // owner change
    reject(old_mate, changed);
    changed = new_mate;
    changed[0]["assembly_side"] = 2; // datum side change
    reject(old_mate, changed);
    changed = new_mate;
    changed[0]["component_path"] = nlohmann::json::array({5}); // added field
    reject(old_mate, changed);

    // Count and order stay verified.
    reject(old_checkpoint, nlohmann::json::parse(R"([{"type":13},{"type":13}])"));
    reject(new_mate, nlohmann::json::parse(R"([])"));
    reject(nlohmann::json::parse(R"([{"type":0},{"type":13}])"),
           nlohmann::json::parse(R"([{"type":13},{"type":0}])"));
    // A named symbol replacing "unknown" is display-only and stays compatible.
    assert(match_for_verification(nlohmann::json::parse(R"([{"type":999,"type_name":"unknown"}])"),
                                  nlohmann::json::parse(R"([{"type":999,"type_name":"new_symbol"}])")));
    // A symbol change that renames a KNOWN type is still only display-level;
    // the numeric code is authoritative and stays equal.
    assert(match_for_verification(nlohmann::json::parse(R"([{"type":13,"type_name":"fix"}])"),
                                  nlohmann::json::parse(R"([{"type":13,"type_name":"renamed"}])")));
    // Unknown codes stay numeric; a numeric change is always rejected even
    // when both sides keep an "unknown" symbol.
    reject(nlohmann::json::parse(R"([{"type":999,"type_name":"unknown"}])"),
           nlohmann::json::parse(R"([{"type":998,"type_name":"unknown"}])"));
    // Malformed payloads fail closed instead of comparing equal.
    assert(!match_for_verification(nlohmann::json::parse(R"([{"type":13}])"), nullptr));
    assert(!match_for_verification(nullptr, nlohmann::json::parse(R"([{"type":13}])")));

    std::puts("constraint_compare: all checks passed");
    return 0;
}
