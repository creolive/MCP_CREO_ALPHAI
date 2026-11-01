// FEAT-052: assembly component appearance - family recolor with baseline
// capture, two-phase readback and rollback evidence for the native executor.
//
// Mid-file unit (included right before advanced.cpp in generic.cpp, like
// placement.cpp): it relies on declarations earlier in the same translation
// unit - J (nlohmann::json), board, wide, CK/check, log, feature_id,
// alias_entry, operation_position, operation_results and
// stage_operation_result - and on the PreviewStepOutcome helpers from
// preview.h.
//
// Plan: docs/superpowers/plans/2026-10-31-assembly-recolor-plan.md
// ("实现方式" 2/3). Deliberate deviations from the external proposal
// recolor_worker.cpp:
// - components are located ONLY by the explicit label assignments the Python
//   side sends, each resolved through the same label machinery as
//   component_placement and re-checked against its registered alias identity.
//   The proposal's walk-index family table (g_comp_family[80]) guesses
//   families from traversal order and is deliberately not reproduced;
// - ProAsmitem is built from the component model's REAL type via
//   ProMdlTypeGet → PRO_PART / PRO_ASSEMBLY. The proposal passes PRO_FEATURE,
//   which makes every later ProMdlVisibleSideAppearancepropsSet/Get fail with
//   PRO_TK_INVALID_TYPE (its own README documents this trap);
// - appearance readback uses ProMdlVisibleSideAppearancepropsGet (ProMdl.h,
//   verified present in the local Creo 12.4 headers alongside the setter).
//   Its documented PRO_TK_NOT_EXIST ("The property does not exists") is the
//   exact "no component-level appearance" outcome and gives the three-state
//   baseline: present / absent / query_failed;
// - every Toolkit return code is reported verbatim; nothing is swallowed and
//   no readback mismatch is repaired silently - failures fall into the
//   existing checkpoint rollback.
#pragma once

#include <ProAsmcomp.h>
#include <ProAsmcomppath.h>
#include <ProMdl.h>
#include <ProSurface.h>
#include <ProToolkit.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <cwchar>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

// Fixed display parameters (plan: the proposal paint_one props).
inline constexpr double kAppearanceAmbient = 0.4;
inline constexpr double kAppearanceDiffuse = 0.7;
inline constexpr double kAppearanceHighlite = 0.5;
inline constexpr double kAppearanceShininess = 0.4;
// Absolute RGB readback tolerance for both readback phases (plan: 1e-6).
inline constexpr double kAppearanceReadbackTolerance = 1e-6;

// ---- three-state appearance record ------------------------------------------

// Reads the component-level appearance of one assembly component. The
// component model's real type decides the ProAsmitem item type and a
// single-level component path (one id) is enough for MCP-managed assemblies.
// The three states are exact SDK outcomes, never merged or guessed:
//   present      - ProMdlVisibleSideAppearancepropsGet returned NO_ERROR;
//   absent       - it returned PRO_TK_NOT_EXIST (no explicit appearance);
//   query_failed - any other code, or an earlier ProAsmitem construction
//                  step failed; query_code carries the raw code.
static J component_appearance_record(ProAsmcomp *comp, ProMdl child) {
    ProMdlType child_type = PRO_MDL_PART;
    ProType item_type = PRO_PART;
    ProError code = child ? ProMdlTypeGet(child, &child_type) : PRO_TK_BAD_INPUTS;
    if (code == PRO_TK_NO_ERROR) {
        switch (child_type) {
        case PRO_MDL_PART:
            item_type = PRO_PART;
            break;
        case PRO_MDL_ASSEMBLY:
            item_type = PRO_ASSEMBLY;
            break;
        default:
            code = PRO_TK_INVALID_TYPE;
            break;
        }
    }
    ProIdTable ids = {};
    ProAsmcomppath path;
    if (code == PRO_TK_NO_ERROR) {
        ids[0] = comp->id;
        code = ProAsmcomppathInit((ProSolid)comp->owner, ids, 1, &path);
    }
    ProAsmitem item;
    memset(&item, 0, sizeof(item));
    if (code == PRO_TK_NO_ERROR) {
        ProName empty_name = L"";
        code = ProAsmcompAsmitemInit(comp->owner, comp->id, item_type, empty_name, &path, &item);
    }
    ProSurfaceAppearanceProps props;
    memset(&props, 0, sizeof(props));
    if (code == PRO_TK_NO_ERROR)
        code = ProMdlVisibleSideAppearancepropsGet(&item, 0, &props);
    if (code == PRO_TK_NO_ERROR)
        return {{"state", "present"},
                {"rgb", J::array({props.color_rgb[0], props.color_rgb[1], props.color_rgb[2]})},
                {"query_code", 0}};
    return {{"state", code == PRO_TK_NOT_EXIST ? "absent" : "query_failed"},
            {"rgb", nullptr},
            {"query_code", (int)code}};
}

// Save/reload and rollback comparison rule for one appearance record: the
// state must match, and a present appearance must keep its RGB within the
// readback tolerance. Baselines recorded before FEAT-052 carry no appearance
// field; verify_saved skips them (the recolor op refuses components without
// an appearance baseline instead).
static bool appearance_records_equal(const J &before, const J &after) {
    const std::string before_state = before.value("state", "");
    if (before_state != after.value("state", ""))
        return false;
    if (before_state != "present")
        return true;
    auto a = before.find("rgb");
    auto b = after.find("rgb");
    if (a == before.end() || b == after.end() || !a->is_array() || !b->is_array() ||
        a->size() != 3 || b->size() != 3)
        return false;
    for (int i = 0; i < 3; i++)
        if (fabs((*a)[i].get<double>() - (*b)[i].get<double>()) > kAppearanceReadbackTolerance)
            return false;
    return true;
}

// ---- recolor operation -------------------------------------------------------

struct RecolorTarget {
    std::string label;
    std::string family;
    int feature_id = -1;
    double rgb[3] = {0.0, 0.0, 0.0};
};

// Job-scoped recolor evidence. The executor runs one request per process, but
// the state is still reset per job so recovery paths never see stale targets.
struct RecolorState {
    bool active = false;
    int operation_index = -1;
    std::vector<RecolorTarget> targets;
    J baseline = J::array();
    std::map<std::string, J> baseline_by_label;
    J block = J::object();
};
static RecolorState g_recolor;
// Admission inspection appearance records by feature_id, captured before any
// operation runs. The recolor op refuses components without this baseline:
// only the admission registration can prove that a later rollback restored
// the pre-job appearance.
static J g_recolor_admission = J::object();
static bool g_recolor_readonly = false;

static void recolor_reset() {
    g_recolor = RecolorState{};
    g_recolor_admission = J::object();
    g_recolor_readonly = false;
}

static void recolor_set_admission(const J &admission) {
    if (!admission.contains("components") || !admission["components"].is_array())
        return;
    for (const auto &comp : admission["components"])
        if (comp.contains("feature_id") && comp.contains("appearance"))
            g_recolor_admission[std::to_string(comp["feature_id"].get<int>())] = comp["appearance"];
}

// One readback row: what was requested vs what the SDK reports, with the raw
// query code. rgb_read/abs_err stay null unless the component reports a
// present three-channel appearance.
static J recolor_readback_entry(const RecolorTarget &target, const J &appearance) {
    J entry = {{"label", target.label},
               {"family", target.family},
               {"rgb_requested", J::array({target.rgb[0], target.rgb[1], target.rgb[2]})},
               {"rgb_read", nullptr},
               {"abs_err", nullptr},
               {"query_code", nullptr}};
    auto code = appearance.find("query_code");
    if (code != appearance.end() && code->is_number_integer())
        entry["query_code"] = code->get<int>();
    auto rgb = appearance.find("rgb");
    if (appearance.value("state", "") == "present" && rgb != appearance.end() && rgb->is_array() &&
        rgb->size() == 3) {
        double err = 0;
        for (int i = 0; i < 3; i++)
            err = std::max(err, fabs((*rgb)[i].get<double>() - target.rgb[i]));
        entry["rgb_read"] = *rgb;
        entry["abs_err"] = err;
    }
    return entry;
}

static bool recolor_entry_within(const J &entry) {
    auto err = entry.find("abs_err");
    return err != entry.end() && !err->is_null() &&
           err->get<double>() <= kAppearanceReadbackTolerance;
}

static void recolor_validate_assignment(const J &item, const std::string &label) {
    auto rgb = item.find("rgb");
    if (rgb == item.end() || !rgb->is_array() || rgb->size() != 3)
        throw std::runtime_error("recolor_assembly assignment '" + label +
                                 "' needs an rgb array of three channels");
    for (int i = 0; i < 3; i++) {
        const J &channel = (*rgb)[i];
        if (!channel.is_number() || channel.is_boolean())
            throw std::runtime_error("recolor_assembly assignment '" + label +
                                     "' has a non-numeric rgb channel");
        double value = channel.get<double>();
        if (!std::isfinite(value) || value < 0.0 || value > 1.0)
            throw std::runtime_error("recolor_assembly assignment '" + label +
                                     "' rgb channels must be finite numbers within 0..1");
    }
}

// Paints one component at the assembly component layer. The ProAsmitem is
// constructed from the component model's real type; highlight_color follows
// color_rgb and the display parameters are the fixed proposal values.
static void recolor_paint_one(const RecolorTarget &target) {
    ProAsmcomp comp;
    CK(ProModelitemInit(board, target.feature_id, PRO_FEATURE, &comp));
    ProMdl child = nullptr;
    CK(ProAsmcompMdlGet(&comp, &child));
    ProMdlType child_type;
    CK(ProMdlTypeGet(child, &child_type));
    if (child_type != PRO_MDL_PART && child_type != PRO_MDL_ASSEMBLY)
        throw std::runtime_error("Component model type cannot receive an assembly-level "
                                 "appearance");
    ProType item_type = child_type == PRO_MDL_ASSEMBLY ? PRO_ASSEMBLY : PRO_PART;
    ProIdTable ids = {};
    ids[0] = comp.id;
    ProAsmcomppath path;
    CK(ProAsmcomppathInit((ProSolid)board, ids, 1, &path));
    ProAsmitem item;
    memset(&item, 0, sizeof(item));
    ProName empty_name = L"";
    CK(ProAsmcompAsmitemInit(board, comp.id, item_type, empty_name, &path, &item));
    ProSurfaceAppearanceProps props;
    memset(&props, 0, sizeof(props));
    props.ambient = kAppearanceAmbient;
    props.diffuse = kAppearanceDiffuse;
    props.highlite = kAppearanceHighlite;
    props.shininess = kAppearanceShininess;
    props.transparency = 0.0;
    props.reflection = 0.0;
    for (int i = 0; i < 3; i++) {
        props.color_rgb[i] = target.rgb[i];
        props.highlight_color[i] = target.rgb[i];
    }
    // The family name identifies the appearance on the component; description
    // and keywords follow the proposal's paint_one filler values.
    std::wstring family = wide(target.family);
    wcsncpy_s(props.name, PRO_PATH_SIZE, family.c_str(), _TRUNCATE);
    wcsncpy_s(props.label, PRO_PATH_SIZE, family.c_str(), _TRUNCATE);
    wcsncpy_s(props.description, PRO_PATH_SIZE, L"mechdog family color", _TRUNCATE);
    wcsncpy_s(props.keywords, PRO_PATH_SIZE, L"mechdog", _TRUNCATE);
    CK(ProMdlVisibleSideAppearancepropsSet(&item, 0, &props));
}

static void recolor_assembly(const J &op) {
    g_recolor.active = true;
    g_recolor.operation_index = operation_position;
    J &block = g_recolor.block;
    block = {{"painted", 0},
             {"unmatched", J::array()},
             {"family_counts", J::object()},
             {"readback_before_save", J::array()},
             {"readback_after_reload", nullptr},
             {"readback_tolerance", kAppearanceReadbackTolerance},
             {"readback_all_within_tolerance", false},
             {"component_appearance_baseline", J::array()},
             {"window_refresh", nullptr}};
    try {
        if (g_recolor_readonly)
            throw std::runtime_error("recolor_assembly cannot run in a read-only job");
        if (!op.contains("assignments") || !op["assignments"].is_array() ||
            op["assignments"].empty())
            throw std::runtime_error("recolor_assembly requires a non-empty assignments array");
        std::set<std::string> declared;
        if (op.contains("families") && !op["families"].is_null()) {
            if (!op["families"].is_array())
                throw std::runtime_error("recolor_assembly families must be an array of names");
            for (const auto &name : op["families"]) {
                if (!name.is_string() || name.get<std::string>().empty())
                    throw std::runtime_error(
                        "recolor_assembly family names must be non-empty strings");
                declared.insert(name.get<std::string>());
            }
        }
        // Resolve every assignment BEFORE any appearance write. A member
        // reference is a component label (string) or a feature ID (integer),
        // mirroring the Python side; an explicit feature_id field wins and is
        // cross-checked against an integer label. Each resolved component is
        // re-checked against PRO_FEAT_COMPONENT and the admission appearance
        // baseline; duplicates are refused by resolved feature ID.
        std::set<int> seen_feature_ids;
        for (const auto &item : op["assignments"]) {
            std::string label;
            int label_feature_id = -1;
            if (!item.contains("label") || item["label"].is_null())
                throw std::runtime_error("recolor_assembly assignments need a label and a family");
            if (item["label"].is_string()) {
                label = item["label"].get<std::string>();
            } else if (item["label"].is_number_integer()) {
                label_feature_id = item["label"].get<int>();
                label = std::to_string(label_feature_id);
            } else {
                throw std::runtime_error(
                    "recolor_assembly assignment label must be a component label or feature ID");
            }
            const std::string family = item.value("family", "");
            if (label.empty() || family.empty())
                throw std::runtime_error("recolor_assembly assignments need a label and a family");
            recolor_validate_assignment(item, label);
            if (!declared.empty() && !declared.count(family)) {
                block["unmatched"].push_back(
                    {{"label", label},
                     {"reason", "family '" + family + "' is not in the families list"}});
                continue;
            }
            RecolorTarget target;
            target.label = label;
            target.family = family;
            for (int i = 0; i < 3; i++)
                target.rgb[i] = item["rgb"][i].get<double>();
            try {
                if (item.contains("feature_id") && item["feature_id"].is_number_integer()) {
                    target.feature_id = item["feature_id"].get<int>();
                    if (label_feature_id >= 0 && label_feature_id != target.feature_id)
                        throw std::runtime_error(
                            "assignment feature_id disagrees with the integer label reference");
                } else if (label_feature_id >= 0) {
                    target.feature_id = label_feature_id;
                } else {
                    target.feature_id = feature_id(label);
                }
            } catch (const std::exception &error) {
                block["unmatched"].push_back({{"label", label}, {"reason", error.what()}});
                continue;
            }
            if (!seen_feature_ids.insert(target.feature_id).second)
                throw std::runtime_error("recolor_assembly assigns one component twice: feature " +
                                         std::to_string(target.feature_id));
            ProAsmcomp comp;
            ProError init_code = ProModelitemInit(board, target.feature_id, PRO_FEATURE, &comp);
            ProFeattype type = PRO_FEAT_COMPONENT;
            if (init_code == PRO_TK_NO_ERROR) {
                ProError type_code = ProFeatureTypeGet(&comp, &type);
                if (type_code != PRO_TK_NO_ERROR)
                    init_code = type_code;
            }
            if (init_code != PRO_TK_NO_ERROR || type != PRO_FEAT_COMPONENT) {
                block["unmatched"].push_back(
                    {{"label", label},
                     {"reason",
                      init_code != PRO_TK_NO_ERROR
                          ? "component lookup failed with code " + std::to_string((int)init_code)
                          : "label does not resolve to an assembly component"}});
                continue;
            }
            const std::string key = std::to_string(target.feature_id);
            if (!g_recolor_admission.contains(key))
                throw std::runtime_error(
                    "Component '" + label +
                    "' has no appearance baseline in this model's registration; save the model "
                    "with creo_save_model to establish a verified checkpoint including "
                    "appearance, then resubmit the recolor");
            if (g_recolor_admission[key].value("state", "query_failed") == "query_failed")
                throw std::runtime_error(
                    "Appearance baseline query failed for component '" + label +
                    "'; re-save the checkpoint with creo_save_model, then resubmit");
            g_recolor.targets.push_back(target);
        }
        if (g_recolor.targets.empty())
            throw std::runtime_error(
                "recolor_assembly resolved none of the assignments to paintable components");

        // Baseline capture for every resolved component BEFORE any appearance
        // write; this runs inside the toolkit channel lock.
        for (const auto &target : g_recolor.targets) {
            ProAsmcomp comp;
            CK(ProModelitemInit(board, target.feature_id, PRO_FEATURE, &comp));
            ProMdl child = nullptr;
            ProError child_code = ProAsmcompMdlGet(&comp, &child);
            J appearance = child_code == PRO_TK_NO_ERROR && child
                               ? component_appearance_record(&comp, child)
                               : J{{"state", "query_failed"},
                                   {"rgb", nullptr},
                                   {"query_code", (int)child_code}};
            g_recolor.baseline.push_back({{"label", target.label}, {"appearance", appearance}});
            g_recolor.baseline_by_label[target.label] = appearance;
        }
        block["component_appearance_baseline"] = g_recolor.baseline;

        // Paint. A failed appearance write fails the whole operation so the
        // existing checkpoint rollback restores the captured baseline.
        std::map<std::string, int> counts;
        for (const auto &target : g_recolor.targets) {
            recolor_paint_one(target);
            block["painted"] = block["painted"].get<int>() + 1;
            counts[target.family] += 1;
            block["family_counts"][target.family] = counts[target.family];
        }
        for (const auto &name : declared)
            if (!block["family_counts"].contains(name))
                block["family_counts"][name] = 0;

        // Reuse the shared window bind + repaint chain from preview.h; the
        // SDK requires a repaint after appearance changes for the UI to show
        // them. A failed repaint is recorded, not fatal: the appearance data
        // is already written and the job preview would report the same codes.
        PreviewStepOutcome refresh;
        const bool refreshed =
            bind_model_window(board, refresh) && repaint_bound_window(refresh.window, refresh);
        block["window_refresh"] = preview_window_codes_json(refresh);
        (void)refreshed;

        // Readback before save: every painted component must report the
        // requested RGB within the tolerance, or the operation fails and the
        // checkpoint rollback restores the baseline.
        bool within = true;
        for (const auto &target : g_recolor.targets) {
            ProAsmcomp comp;
            CK(ProModelitemInit(board, target.feature_id, PRO_FEATURE, &comp));
            ProMdl child = nullptr;
            ProError child_code = ProAsmcompMdlGet(&comp, &child);
            J appearance = child_code == PRO_TK_NO_ERROR && child
                               ? component_appearance_record(&comp, child)
                               : J{{"state", "query_failed"},
                                   {"rgb", nullptr},
                                   {"query_code", (int)child_code}};
            J entry = recolor_readback_entry(target, appearance);
            if (!recolor_entry_within(entry))
                within = false;
            block["readback_before_save"].push_back(entry);
        }
        block["readback_all_within_tolerance"] = within;
        if (!within)
            throw std::runtime_error(
                "Post-paint appearance readback is outside the 1e-6 tolerance; rolling back to "
                "the saved checkpoint");
        stage_operation_result({{"op", op.at("op")}, {"recolor", block}});
    } catch (...) {
        stage_operation_result({{"op", op.at("op")}, {"recolor", block}});
        throw;
    }
}

// Publishes the current recolor block into the terminal state: the owning
// operation's record and a job-level mirror for the finalizer.
static void recolor_publish(J &report) {
    if (!g_recolor.active)
        return;
    if (g_recolor.operation_index >= 0 && g_recolor.operation_index < (int)operation_results.size())
        operation_results[g_recolor.operation_index]["recolor"] = g_recolor.block;
    if (report.contains("operations"))
        report["operations"] = operation_results;
    report["recolor"] = g_recolor.block;
}

// FEAT-052: after the job's save/erase/reload, read the persisted appearance
// back from the reloaded inspection and extend the recolor block. Runs before
// verify_saved so the evidence exists even when the comparison throws.
static void recolor_after_reload(const J &state, J &report) {
    if (!g_recolor.active || g_recolor.block.is_null())
        return;
    std::map<int, const J *> components;
    if (state.contains("components"))
        for (const auto &comp : state["components"])
            if (comp.contains("feature_id"))
                components.emplace(comp["feature_id"].get<int>(), &comp);
    J entries = J::array();
    bool within = g_recolor.block.value("readback_all_within_tolerance", false);
    for (const auto &target : g_recolor.targets) {
        auto found = components.find(target.feature_id);
        const J *appearance = nullptr;
        if (found != components.end()) {
            auto field = found->second->find("appearance");
            if (field != found->second->end())
                appearance = &*field;
        }
        J entry = recolor_readback_entry(target, appearance ? *appearance : J::object());
        if (!recolor_entry_within(entry))
            within = false;
        entries.push_back(entry);
    }
    g_recolor.block["readback_after_reload"] = entries;
    g_recolor.block["readback_all_within_tolerance"] = within;
    recolor_publish(report);
    if (!within)
        throw std::runtime_error(
            "Saved appearance readback is outside the 1e-6 tolerance after erase/reload; "
            "rolling back to the saved checkpoint");
}

// FEAT-052 rollback evidence: after the checkpoint reload, compare every
// baseline entry against the restored inspection. Baseline entries whose own
// capture already failed (state "query_failed") cannot prove anything and are
// reported as unverifiable instead of guessed; a proven mismatch fails the
// rollback, which keeps the job's existing unknown protection.
static void recolor_rollback_check(const J &restored) {
    if (!g_recolor.active || g_recolor.baseline.empty())
        return;
    std::map<int, const J *> components;
    if (restored.contains("components"))
        for (const auto &comp : restored["components"])
            if (comp.contains("feature_id"))
                components.emplace(comp["feature_id"].get<int>(), &comp);
    J checks = J::array();
    bool verified = true;
    for (const auto &target : g_recolor.targets) {
        auto baseline = g_recolor.baseline_by_label.find(target.label);
        auto found = components.find(target.feature_id);
        const J *appearance = nullptr;
        if (found != components.end()) {
            auto field = found->second->find("appearance");
            if (field != found->second->end())
                appearance = &*field;
        }
        J check = {{"label", target.label},       {"baseline_state", nullptr},
                   {"restored_state", nullptr},   {"abs_err", nullptr},
                   {"within_tolerance", nullptr}, {"verified", false}};
        if (baseline == g_recolor.baseline_by_label.end() || !appearance) {
            checks.push_back(check);
            verified = false;
            continue;
        }
        const std::string baseline_state = baseline->second.value("state", "query_failed");
        const std::string restored_state = appearance->value("state", "query_failed");
        check["baseline_state"] = baseline_state;
        check["restored_state"] = restored_state;
        if (baseline_state == "query_failed" || restored_state == "query_failed") {
            // Cannot prove; the unknown protection stays in effect.
            checks.push_back(check);
            verified = false;
            continue;
        }
        bool within = baseline_state == restored_state;
        if (within && baseline_state == "present") {
            auto a = baseline->second.find("rgb");
            auto b = appearance->find("rgb");
            if (a == baseline->second.end() || b == appearance->end() || !a->is_array() ||
                !b->is_array() || a->size() != 3 || b->size() != 3) {
                within = false;
            } else {
                double err = 0;
                for (int i = 0; i < 3; i++)
                    err = std::max(err, fabs((*a)[i].get<double>() - (*b)[i].get<double>()));
                check["abs_err"] = err;
                within = err <= kAppearanceReadbackTolerance;
            }
        }
        check["within_tolerance"] = within;
        check["verified"] = within;
        if (!within)
            verified = false;
        checks.push_back(check);
    }
    g_recolor.block["rollback_appearance_check"] = checks;
    g_recolor.block["rollback_appearance_verified"] = verified;
    if (!verified)
        throw std::runtime_error(
            "Restored component appearance could not be verified against the captured "
            "baseline; the rollback effect stays unknown");
}
