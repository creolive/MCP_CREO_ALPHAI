// Path-adoption identity admission shared by the SDK adapter and offline harness.
#pragma once
#include "third_party/json.hpp"
#include <stdexcept>

namespace mechdog_adoption {
using Json = nlohmann::json;

inline void require_source_state(const Json &actual, const Json &expected) {
    for (const char *key : {"origin", "sha256", "session_model_id", "version_stamp"}) {
        if (!actual.contains(key) || actual.at(key).is_null() || !expected.contains(key) ||
            actual.at(key) != expected.at(key))
            throw std::runtime_error("source_changed: path source identity changed before copying");
    }
    if (actual.value("modified", true))
        throw std::runtime_error("modified_source: path source was modified in the session");
}
} // namespace mechdog_adoption
