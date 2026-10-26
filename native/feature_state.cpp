// Part feature lifecycle: delete / suppress / resume with explicit targets.
//
// Included by native/generic.cpp after the shared helpers. The Python layer
// already resolves the same rules against the saved inspection; everything
// here is re-checked against the live model before Toolkit is called, so a
// stale registry or a forged target cannot reach the feature tree.
#include <filesystem>
#include <map>
#include <set>
#include <string>

static std::string feature_state_label_for(int id) {
    for (auto it = aliases.begin(); it != aliases.end(); ++it) {
        if (!it.value().is_object())
            continue;
        auto value = it.value().find("feature_id");
        if (value != it.value().end() && value.value().is_number_integer() &&
            value.value().get<int>() == id)
            return it.key();
    }
    return std::string();
}

static const char *feature_state_job_id() {
    static std::string value = utf8(std::filesystem::path(generic_job).filename().wstring());
    return value.c_str();
}

static int feature_state_flag(const J &feature, const char *key) {
    if (!feature.contains(key) || !feature[key].is_number_integer())
        return -1;
    return feature[key].get<int>();
}

static bool feature_state_member(const J &feature) {
    return feature_state_flag(feature, "group_status") == PRO_GROUP_MEMBER ||
           feature_state_flag(feature, "pattern_status") == PRO_PATTERN_MEMBER ||
           feature_state_flag(feature, "grppattern_status") == PRO_GRP_PATTERN_MEMBER;
}

static int feature_state_target_id(const J &target) {
    if (target.is_number_integer())
        return target.get<int>();
    if (!target.is_string())
        throw std::runtime_error(
            "feature_state targets must be feature labels or nonnegative feature IDs");
    std::string label = target.get<std::string>();
    if (!label.empty() && label.find_first_not_of("0123456789") == std::string::npos) {
        errno = 0;
        char *end = nullptr;
        long long id = std::strtoll(label.c_str(), &end, 10);
        if (!errno && end && !*end && id >= 0 && id <= 2147483647LL)
            return (int)id;
        throw std::runtime_error("feature_state target ID is not a nonnegative 32-bit integer: " +
                                 label);
    }
    if (feature_tombstones.contains(label))
        throw std::runtime_error("Feature label '" + label +
                                 "' is a tombstone of a deleted feature; deleted labels cannot "
                                 "be reused or referenced");
    if (const J *entry = alias_entry(label))
        return entry->at("feature_id").get<int>();
    throw std::runtime_error("Unknown feature label: " + label +
                             "; inspect the model and use a registered label or a native "
                             "feature ID");
}

static void feature_state_remove_suppression(int id) {
    for (auto it = suppressed_features.begin(); it != suppressed_features.end();) {
        if (it.value().is_object() && it.value().contains("feature_id") &&
            it.value()["feature_id"].is_number_integer() &&
            it.value()["feature_id"].get<int>() == id)
            it = suppressed_features.erase(it);
        else
            ++it;
    }
    recorded_suppressed.erase(id);
}

static void feature_state_forget_aliases(int id) {
    for (auto it = aliases.begin(); it != aliases.end();) {
        if (it.value().is_object() && it.value().contains("feature_id") &&
            it.value()["feature_id"].is_number_integer() &&
            it.value()["feature_id"].get<int>() == id)
            it = aliases.erase(it);
        else
            ++it;
    }
}

static void feature_state_add_tombstone(int id, const J &feature) {
    std::string label = feature_state_label_for(id);
    J entry = {{"feature_id", id},
               {"label", label.empty() ? J(nullptr) : J(label)},
               {"name", feature.value("name", "")},
               {"type_name", feature.value("type_name", "")},
               {"job_id", feature_state_job_id()}};
    feature_tombstones[label.empty() ? "#" + std::to_string(id) : label] = entry;
    feature_state_remove_suppression(id);
    feature_state_forget_aliases(id);
}

static void feature_state_record_suppression(int id, const J &feature) {
    std::string label = feature_state_label_for(id);
    J entry = {{"feature_id", id},
               {"label", label.empty() ? J(nullptr) : J(label)},
               {"name", feature.value("name", "")},
               {"type_name", feature.value("type_name", "")},
               {"job_id", feature_state_job_id()}};
    feature_state_remove_suppression(id);
    suppressed_features[label.empty() ? "#" + std::to_string(id) : label] = entry;
    recorded_suppressed.insert(id);
}

static J feature_state_snapshot(const J *feature) {
    if (!feature)
        return {{"present", false},      {"status", nullptr}, {"suppressed", nullptr},
                {"incomplete", nullptr}, {"name", nullptr},   {"type_name", nullptr}};
    int status = feature->value("status", PRO_FEAT_INVALID);
    return {{"present", true},
            {"status", status},
            {"suppressed", status == PRO_FEAT_SUPPRESSED},
            {"incomplete", feature->value("incomplete", false)},
            {"name", feature->value("name", "")},
            {"type_name", feature->value("type_name", "")}};
}

static void feature_state_collect_children(int id, const std::map<int, J> &by_id,
                                           std::set<int> &seen) {
    auto found = by_id.find(id);
    if (found == by_id.end() || !found->second.contains("child_ids"))
        return;
    for (const auto &child : found->second["child_ids"]) {
        if (!child.is_number_integer())
            continue;
        int child_id = child.get<int>();
        if (!seen.insert(child_id).second)
            continue;
        feature_state_collect_children(child_id, by_id, seen);
    }
}

static J generic_feature_state(const J &op) {
    std::string action = op.at("action").get<std::string>();
    if (action != "delete" && action != "suppress" && action != "resume")
        throw std::runtime_error("feature_state action must be delete, suppress or resume");
    J state = inspection(false);
    std::string model_type = state.value("model_type", "part");
    if (model_type != "part" && model_type != "sheetmetal")
        throw std::runtime_error(
            "feature_state supports managed part/sheetmetal models only; assembly components "
            "are changed with remove_component");

    std::map<int, J> by_id;
    for (const auto &feature : state["features"])
        by_id[feature["id"].get<int>()] = feature;

    std::vector<int> ids;
    std::vector<std::string> labels;
    std::set<int> target_set;
    J requested = J::array();
    for (const auto &target : op.at("targets")) {
        int id = feature_state_target_id(target);
        if (!target_set.insert(id).second)
            throw std::runtime_error("feature_state targets must be distinct");
        auto found = by_id.find(id);
        if (found == by_id.end())
            throw std::runtime_error("Feature " + std::to_string(id) +
                                     " is absent from the live model feature tree");
        const J &feature = found->second;
        if (feature.value("system_required", false))
            throw std::runtime_error(
                "Feature " + std::to_string(id) +
                " is a system-required object (default coordinate system or template datum)");
        if (feature_state_member(feature))
            throw std::runtime_error("Feature " + std::to_string(id) +
                                     " is a group/pattern member; target its group or pattern "
                                     "header instead of an individual member");
        if (feature.value("incomplete", false))
            throw std::runtime_error("Feature " + std::to_string(id) +
                                     " is incomplete and cannot be changed");
        int status = feature.value("status", PRO_FEAT_INVALID);
        if (action == "resume" && status != PRO_FEAT_SUPPRESSED)
            throw std::runtime_error("Feature " + std::to_string(id) +
                                     " is not suppressed; resume only applies to suppressed "
                                     "features");
        if (action == "suppress" && status == PRO_FEAT_SUPPRESSED)
            throw std::runtime_error("Feature " + std::to_string(id) + " is already suppressed");
        ids.push_back(id);
        labels.push_back(feature_state_label_for(id));
        requested.push_back(target);
    }

    // Dependency coverage: every affected descendant must be an explicit
    // target. Grouped members cannot be listed individually, so they follow
    // their header instead of being required as separate targets.
    std::set<int> missing;
    if (action == "delete" || action == "suppress") {
        for (int id : ids) {
            std::set<int> descendants;
            feature_state_collect_children(id, by_id, descendants);
            for (int child : descendants) {
                auto found = by_id.find(child);
                if (found == by_id.end() || feature_state_member(found->second))
                    continue;
                if (!target_set.count(child))
                    missing.insert(child);
            }
        }
    } else {
        for (int id : ids) {
            const J &feature = by_id.at(id);
            if (!feature.contains("parent_ids"))
                continue;
            for (const auto &parent : feature["parent_ids"]) {
                if (!parent.is_number_integer())
                    continue;
                int parent_id = parent.get<int>();
                auto found = by_id.find(parent_id);
                if (found == by_id.end())
                    continue;
                if (found->second.value("status", PRO_FEAT_INVALID) != PRO_FEAT_SUPPRESSED)
                    continue;
                if (!target_set.count(parent_id))
                    missing.insert(parent_id);
            }
        }
    }
    if (!missing.empty()) {
        J listed = J::array();
        for (int id : missing) {
            const J &feature = by_id.at(id);
            listed.push_back(
                {{"feature_id", id},
                 {"label", feature_state_label_for(id).empty() ? J(nullptr)
                                                               : J(feature_state_label_for(id))},
                 {"name", feature.value("name", "")},
                 {"type_name", feature.value("type_name", "")},
                 {"status", feature.value("status", PRO_FEAT_INVALID)}});
        }
        log("FEATURE_STATE_MISSING_DEPENDENCIES=%s\n", listed.dump().c_str());
        throw std::runtime_error(
            "feature_state targets do not cover every affected dependency; list these feature "
            "IDs explicitly (no automatic cascade): " +
            listed.dump());
    }

    J before = J::array();
    for (int id : ids)
        before.push_back(feature_state_snapshot(&by_id.at(id)));

    ProError code;
    int *list = nullptr;
    CK(ProArrayAlloc((int)ids.size(), sizeof(int), 1, (ProArray *)&list));
    for (size_t i = 0; i < ids.size(); i++)
        list[i] = ids[i];
    if (action == "delete") {
        ProFeatureDeleteOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_DELETE_NO_OPTS;
        code = ProFeatureWithoptionsDelete((ProSolid)board, list, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&options);
    } else if (action == "suppress") {
        ProFeatureDeleteOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_DELETE_NO_OPTS;
        code = ProFeatureWithoptionsSuppress((ProSolid)board, list, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&options);
    } else {
        ProFeatureResumeOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureResumeOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_RESUME_NO_OPTS;
        code = ProFeatureWithoptionsResume((ProSolid)board, list, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&options);
    }
    ProArrayFree((ProArray *)&list);
    check(code, action == "delete"     ? "FeatureStateDelete"
                : action == "suppress" ? "FeatureStateSuppress"
                                       : "FeatureStateResume");
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));

    J after_state = inspection(false);
    std::map<int, J> after_by_id;
    for (const auto &feature : after_state["features"])
        after_by_id[feature["id"].get<int>()] = feature;

    J details = J::array();
    for (size_t i = 0; i < ids.size(); i++) {
        int id = ids[i];
        auto found = after_by_id.find(id);
        const J *feature = found == after_by_id.end() ? nullptr : &found->second;
        J after = feature_state_snapshot(feature);
        if (action == "delete") {
            if (feature)
                throw std::runtime_error("Feature " + std::to_string(id) +
                                         " is still present after delete");
            feature_state_add_tombstone(id, by_id.at(id));
        } else if (action == "suppress") {
            if (!feature || feature->value("status", PRO_FEAT_INVALID) != PRO_FEAT_SUPPRESSED)
                throw std::runtime_error("Feature " + std::to_string(id) +
                                         " is not suppressed after the operation");
            feature_state_record_suppression(id, *feature);
        } else {
            if (!feature || feature->value("status", PRO_FEAT_INVALID) != PRO_FEAT_ACTIVE)
                throw std::runtime_error("Feature " + std::to_string(id) +
                                         " is not active after resume");
            feature_state_remove_suppression(id);
        }
        details.push_back({{"target", requested[i]},
                           {"feature_id", id},
                           {"label", labels[i].empty() ? J(nullptr) : J(labels[i])},
                           {"before", before[i]},
                           {"after", after},
                           {"effect", action == "delete"     ? "deleted"
                                      : action == "suppress" ? "suppressed"
                                                             : "resumed"}});
    }

    feature_state_touched = true;
    if (action == "delete") {
        J deleted = feature_state_effects.contains("deleted_ids")
                        ? feature_state_effects["deleted_ids"]
                        : J::array();
        for (int id : ids)
            deleted.push_back(id);
        feature_state_effects["deleted_ids"] = deleted;
    } else {
        J expectations = feature_state_effects.contains("status_expectations")
                             ? feature_state_effects["status_expectations"]
                             : J::object();
        for (int id : ids)
            expectations[std::to_string(id)] =
                action == "suppress" ? PRO_FEAT_SUPPRESSED : PRO_FEAT_ACTIVE;
        feature_state_effects["status_expectations"] = expectations;
    }

    log("FEATURE_STATE=%s targets=%s\n", action.c_str(), details.dump().c_str());
    return {{"feature_state",
             {{"action", action},
              {"applied", (int)ids.size()},
              {"explicit_targets", requested},
              {"tombstone_count", (int)feature_tombstones.size()},
              {"suppressed_count", (int)suppressed_features.size()}}},
            {"targets", details},
            {"feature_tombstones", feature_tombstones},
            {"suppressed_features", suppressed_features}};
}
