#include "adoption_source.h"
#include <iostream>

using Json = mechdog_adoption::Json;

int main() {
    const Json inspected = {{"origin", "C:\\parts\\source.prt.3"},
                            {"sha256", "inspected-file-sha"},
                            {"session_model_id", 0},
                            {"version_stamp", "inspected-version"},
                            {"modified", false},
                            {"provenance", "existing_resident"},
                            {"disk_resident_content_equality", "unknown"}};
    int checks = 0;
    mechdog_adoption::require_source_state(inspected, inspected);
    ++checks; // Native model id zero is a valid identity.
    for (const char *key : {"origin", "sha256", "session_model_id", "version_stamp", "modified"}) {
        Json changed = inspected;
        changed[key] = std::string(key) == "modified" ? Json(true) : Json("different");
        bool refused = false;
        try {
            mechdog_adoption::require_source_state(changed, inspected);
        } catch (const std::runtime_error &) {
            refused = true;
        }
        if (!refused)
            return 1;
        ++checks;
        changed = inspected;
        changed.erase(key);
        refused = false;
        try {
            mechdog_adoption::require_source_state(changed, inspected);
        } catch (const std::runtime_error &) {
            refused = true;
        }
        if (!refused)
            return 2;
        ++checks;
    }
    Json fresh = inspected;
    fresh["provenance"] = "fresh_retrieval";
    mechdog_adoption::require_source_state(inspected, fresh);
    ++checks; // A newly retrieved source becomes resident without changing identity.
    std::cout << "PASS " << checks << " source-state admission checks; no Toolkit calls\n";
    return 0;
}
