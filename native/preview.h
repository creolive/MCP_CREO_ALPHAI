// Shared raster preview step (DEV-047 T07 / BUG-066).
//
// The automatic job preview and every explicit JPEG export must take the same
// screenshot of the same target window: bind the model to a window, prove that
// window belongs to that model, make it current, apply the fixed view matrix,
// refit/refresh/repaint in one order and then call ProRasterFileWrite. Keeping
// the sequence here is what stops the two paths from drifting apart again.
//
// Nothing in this header throws or aborts a job. Each Toolkit call is recorded
// with its raw return code so a failed capture can be reported beside a model
// save that did succeed (preview failure is not a modeling failure).
#pragma once
#include "third_party/json.hpp"
#include <ProMdl.h>
#include <ProFeature.h>
#include <ProFeatType.h>
#include <ProSolid.h>
#include <ProToolkit.h>
#include <ProUtil.h>
#include <ProView.h>
#include <ProWindows.h>
#include <Windows.h>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

// Canonical 3/4 view used by every preview and export. Each row is unit length
// and the rows are orthogonal, which the SDK view-matrix setter requires.
// Mutable only because the SDK signature takes a non-const ProMatrix.
static ProMatrix preview_isometric_view = {
    {0.7071067811865476, -0.4082482904638631, 0.5773502691896258, 0},
    {0.7071067811865476, 0.4082482904638631, -0.5773502691896258, 0},
    {0, 0.8164965809277260, 0.5773502691896258, 0},
    {0, 0, 0, 1}};

// One session display option behind the datum display (planes, axes, points,
// coordinate systems). The previous value is read first so it can be put back
// exactly as it was; an option whose previous value cannot be read is never
// hidden, because it could not be restored afterwards.
struct PreviewDatumOptionOutcome {
    std::wstring name;
    int get_code = 0;
    int hide_code = 0;
    int restore_code = 0;
    std::wstring previous_value;
    bool previous_known = false;
    bool hidden = false;
    bool restored = false;
};

struct PreviewStepOutcome {
    std::wstring path;
    bool skipped_no_geometry = false;
    int window = -1;
    int display_code = 0;
    int window_get_code = 0;
    int window_model_code = 0;
    int current_set_code = 0;
    int current_get_code = 0;
    int activate_code = 0;
    int view_matrix_set_code = 0;
    int view_matrix_get_code = 0;
    int refit_code = 0;
    int refresh_code = 0;
    int repaint_code = 0;
    int raster_code = 0;
    bool window_matches_model = false;
    bool current_window_matches = false;
    bool view_matrix_matches = false;
    long long file_bytes = -1;
    // Filesystem confirmation of the raster output, recorded separately from
    // the raster code: a zero return only says Creo accepted the request, and a
    // failed confirmation must show its own real error instead of a single
    // borrowed "not found" code (BUG-088).
    bool file_check_absolute = false;
    bool file_check_parent_exists = false;
    bool file_check_exists = false;
    bool file_check_regular = false;
    long long file_check_size = -1;
    int file_check_code = 0;
    std::string file_check_category;
    std::string file_check_message;
    std::string failed_step;
    int failed_code = 0;
    // FEAT-008/BUG-088 (H): datum-occlusion diagnostics in a separate block.
    // These fields never rewrite the capture status or the raw codes above;
    // the empty-model skip states of P11 stay a separate concern.
    std::string datum_model_type = "unknown";
    int datum_type_query_code = 0;
    bool datum_applicable = false;
    bool datum_attempted = false;
    std::string datum_hide_status = "not_attempted";
    std::string datum_restore_status = "not_attempted";
    std::vector<PreviewDatumOptionOutcome> datum_options;
};

// A zero solid volume is not an empty preview: sketches and surfaces are
// visible too. Only an inspected part with no active feature beyond datum
// planes/axes/points and coordinate systems is safe to skip. Query failures
// leave the answer unknown and preserve the original capture path.
struct PreviewGeometryProbe {
    bool renderable = false;
    bool unknown = false;
};

static ProError preview_geometry_feature(ProFeature *feature, ProError status, ProAppData data) {
    auto *probe = static_cast<PreviewGeometryProbe *>(data);
    if (status != PRO_TK_NO_ERROR) {
        probe->unknown = true;
        return PRO_TK_NO_ERROR;
    }
    ProFeattype type;
    ProFeatStatus state;
    if (ProFeatureTypeGet(feature, &type) != PRO_TK_NO_ERROR ||
        ProFeatureStatusGet(feature, &state) != PRO_TK_NO_ERROR) {
        probe->unknown = true;
        return PRO_TK_NO_ERROR;
    }
    if (state != PRO_FEAT_ACTIVE) {
        if (state != PRO_FEAT_SUPPRESSED)
            probe->unknown = true;
        return PRO_TK_NO_ERROR;
    }
    if (type != PRO_FEAT_CSYS && type != PRO_FEAT_DATUM && type != PRO_FEAT_DATUM_AXIS &&
        type != PRO_FEAT_DATUM_POINT)
        probe->renderable = true;
    return PRO_TK_NO_ERROR;
}

static bool preview_has_no_geometry(ProMdl model) {
    ProMdlType kind;
    if (ProMdlTypeGet(model, &kind) != PRO_TK_NO_ERROR || kind != PRO_MDL_PART)
        return false;
    PreviewGeometryProbe probe;
    ProError code = ProSolidFeatVisit((ProSolid)model, preview_geometry_feature, nullptr, &probe);
    // The SDK also returns NOT_FOUND when a solid has no features at all.
    return (code == PRO_TK_NO_ERROR || code == PRO_TK_E_NOT_FOUND) && !probe.unknown &&
           !probe.renderable;
}

static std::string preview_utf8(const std::wstring &value) {
    int size = WideCharToMultiByte(CP_UTF8, 0, value.data(), (int)value.size(), nullptr, 0, nullptr,
                                   nullptr);
    std::string result(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), (int)value.size(), result.data(), size, nullptr,
                        nullptr);
    return result;
}

// Return codes are recorded, never thrown: the caller decides whether a failed
// capture is fatal (explicit export) or only diagnostic (automatic preview).
static void preview_record(PreviewStepOutcome &outcome, const char *step, int code) {
    if (code != PRO_TK_NO_ERROR && outcome.failed_step.empty()) {
        outcome.failed_step = step;
        outcome.failed_code = code;
    }
}

// Windows/localized system messages can be long; the diagnostic keeps its
// first characters so the response budget is not spent on one string.
static std::string preview_truncate(const std::string &value, size_t limit = 160) {
    if (value.size() <= limit)
        return value;
    return value.substr(0, limit);
}

// "Nothing at that path" is a specific filesystem outcome, not every failure.
// Comparison covers both the generic and the Windows system category because
// std::filesystem reports ENOENT either way depending on the call.
static bool preview_is_missing(const std::error_code &error) {
    if (!error)
        return true;
    return error == std::errc::no_such_file_or_directory || error.value() == ERROR_FILE_NOT_FOUND ||
           error.value() == ERROR_PATH_NOT_FOUND;
}

static bool preview_rotation_matches(const ProMatrix actual) {
    for (int row = 0; row < 3; row++)
        for (int column = 0; column < 3; column++)
            if (std::fabs(actual[row][column] - preview_isometric_view[row][column]) > 1e-3)
                return false;
    return true;
}

// FEAT-008/BUG-088 (H): temporary datum-display hide/restore around an
// assembly capture. Assemblies drown their preview in displayed datums, so
// the session display options behind planes, axes, points and coordinate
// systems are read first, set to "no" for the duration of the capture and put
// back exactly as they were. ProConfigoptSet only changes the session value:
// the user's config.pro is never written. The guard restores on every exit
// path of the capture, failed steps included (its destructor is the safety
// net), and the per-option codes land in the separate `datum_display` block -
// preview.status and the raw capture codes are never rewritten by it.
static wchar_t preview_datum_option_names[][PRO_NAME_SIZE] = {
    L"DATUM_DISPLAY", L"AXIS_DISPLAY", L"DATUM_POINT_DISPLAY", L"DISPLAY_COORDINATE_SYS"};

struct PreviewDatumDisplayGuard {
    PreviewStepOutcome &outcome;
    bool armed = false;

    explicit PreviewDatumDisplayGuard(PreviewStepOutcome &target) : outcome(target) {
    }
    ~PreviewDatumDisplayGuard() {
        restore();
    }

    void hide(ProMdl model) {
        ProMdlType model_type = PRO_MDL_UNUSED;
        outcome.datum_type_query_code = ProMdlTypeGet(model, &model_type);
        if (outcome.datum_type_query_code != PRO_TK_NO_ERROR) {
            outcome.datum_hide_status = "unknown";
            outcome.datum_restore_status = "unknown";
            return;
        }
        outcome.datum_model_type = model_type == PRO_ASSEMBLY  ? "assembly"
                                   : model_type == PRO_PART    ? "part"
                                   : model_type == PRO_DRAWING ? "drawing"
                                                               : "other";
        // Datum-occlusion handling belongs to the correct assembly preview
        // path; parts and drawings keep their existing capture, and the
        // empty-model skip states of P11 stay a separate concern.
        if (model_type != PRO_ASSEMBLY) {
            outcome.datum_hide_status = "not_applicable";
            outcome.datum_restore_status = "not_applicable";
            return;
        }
        outcome.datum_applicable = true;
        outcome.datum_attempted = true;
        int hidden_count = 0;
        for (size_t index = 0;
             index < sizeof(preview_datum_option_names) / sizeof(preview_datum_option_names[0]);
             index++) {
            PreviewDatumOptionOutcome option;
            option.name = preview_datum_option_names[index];
            ProPath value = {};
            option.get_code = ProConfigoptionGet(preview_datum_option_names[index], value);
            if (option.get_code == PRO_TK_NO_ERROR) {
                option.previous_value = value;
                option.previous_known = true;
                ProPath hidden_value = {};
                wcscpy_s(hidden_value, PRO_PATH_SIZE, L"no");
                option.hide_code = ProConfigoptSet(preview_datum_option_names[index], hidden_value);
                option.hidden = option.hide_code == PRO_TK_NO_ERROR;
                if (option.hidden) {
                    armed = true;
                    hidden_count++;
                }
            }
            // An option whose previous value cannot be read is never hidden:
            // it could not be restored afterwards. Its codes stay recorded.
            outcome.datum_options.push_back(option);
        }
        outcome.datum_hide_status = hidden_count == 0 ? "failed"
                                    : hidden_count == (int)(sizeof(preview_datum_option_names) /
                                                            sizeof(preview_datum_option_names[0]))
                                        ? "hidden"
                                        : "partial";
    }

    void restore() {
        if (!armed)
            return;
        armed = false;
        int hidden_count = 0;
        int restored_count = 0;
        for (PreviewDatumOptionOutcome &option : outcome.datum_options) {
            if (!option.hidden)
                continue;
            hidden_count++;
            ProName key = {};
            ProPath value = {};
            wcscpy_s(key, PRO_NAME_SIZE, option.name.c_str());
            if (option.previous_known) {
                wcscpy_s(value, PRO_PATH_SIZE, option.previous_value.c_str());
                option.restore_code = ProConfigoptSet(key, value);
            } else {
                option.restore_code = PRO_TK_BAD_INPUTS;
            }
            option.restored = option.restore_code == PRO_TK_NO_ERROR;
            if (option.restored)
                restored_count++;
        }
        outcome.datum_restore_status = restored_count == hidden_count ? "restored"
                                       : restored_count == 0          ? "failed"
                                                                      : "partial";
    }
};

// Filesystem confirmation of the raster output (BUG-088). This is a separate
// stage from the raster call: the probe records the target path shape, the
// parent directory, existence, size and the real std::error_code, so a failed
// confirmation shows why it failed instead of a single borrowed code. Nothing
// here retries the capture or the modeling job.
static void preview_confirm_file(PreviewStepOutcome &outcome) {
    const std::filesystem::path target(outcome.path);
    outcome.file_check_absolute = target.is_absolute();
    std::error_code parent_error;
    outcome.file_check_parent_exists =
        std::filesystem::is_directory(target.parent_path(), parent_error);
    std::error_code error;
    bool exists = std::filesystem::exists(target, error);
    outcome.file_check_exists = !error && exists;
    if (!error) {
        std::error_code size_error;
        auto size = std::filesystem::file_size(target, size_error);
        if (size_error) {
            error = size_error;
        } else {
            outcome.file_bytes = static_cast<long long>(size);
            outcome.file_check_size = outcome.file_bytes;
            std::error_code type_error;
            outcome.file_check_regular = std::filesystem::is_regular_file(target, type_error);
        }
    }
    if (error) {
        outcome.file_check_code = error.value();
        outcome.file_check_category = error.category().name();
        outcome.file_check_message = preview_truncate(error.message());
    }
    if (error || outcome.file_bytes <= 0) {
        outcome.failed_step = "output_file";
        // Only "nothing at that path" maps to NOT_FOUND. A sharing violation,
        // access denial or I/O failure keeps its own code and message.
        outcome.failed_code = (!error || preview_is_missing(error)) && !outcome.file_check_exists
                                  ? PRO_TK_E_NOT_FOUND
                                  : PRO_TK_GENERAL_ERROR;
    }
}

    int code = ProMdlDisplay(model);
    outcome.display_code = code;
    preview_record(outcome, "display", code);
    if (code != PRO_TK_NO_ERROR)
        return false;

    code = ProMdlWindowGet(model, &outcome.window);
    outcome.window_get_code = code;
    preview_record(outcome, "window_get", code);
    if (code != PRO_TK_NO_ERROR)
        return false;

    // Target-window selection: the window must show this very model. A stale
    // window left over from another job would capture the wrong solid even
    // though every later call succeeds.
    ProMdl window_model = nullptr;
    code = ProWindowMdlGet(outcome.window, &window_model);
    outcome.window_model_code = code;
    preview_record(outcome, "window_model_get", code);
    outcome.window_matches_model = code == PRO_TK_NO_ERROR && window_model == model;
    if (code == PRO_TK_NO_ERROR && !outcome.window_matches_model) {
        // Two handles can differ while naming the same session model; compare
        // names before reporting a stale window.
        ProMdlName window_name = {}, model_named = {};
        if (ProMdlMdlnameGet(window_model, window_name) == PRO_TK_NO_ERROR &&
            ProMdlMdlnameGet(model, model_named) == PRO_TK_NO_ERROR)
            outcome.window_matches_model = !wcscmp(window_name, model_named);
    }
    if (code != PRO_TK_NO_ERROR)
        return false;
    if (!outcome.window_matches_model) {
        outcome.failed_step = "window_model_mismatch";
        outcome.failed_code = PRO_TK_GENERAL_ERROR;
        return false;
    }

    code = ProWindowCurrentSet(outcome.window);
    outcome.current_set_code = code;
    preview_record(outcome, "current_set", code);
    if (code != PRO_TK_NO_ERROR)
        return false;

    int current = -1;
    code = ProWindowCurrentGet(&current);
    outcome.current_get_code = code;
    preview_record(outcome, "current_get", code);
    outcome.current_window_matches = code == PRO_TK_NO_ERROR && current == outcome.window;
    if (code != PRO_TK_NO_ERROR)
        return false;

    // ProWindowActivate only takes effect after control returns to Creo, so it
    // is recorded but never treated as a step that can fail the capture.
    outcome.activate_code = ProWindowActivate(outcome.window);
    return true;
}

// FEAT-052: the refit/refresh/repaint tail shared by the raster capture and
// the display-only repaint after appearance changes.
static bool repaint_bound_window(int window, PreviewStepOutcome &outcome) {
    int code = ProWindowRefit(window);
    outcome.refit_code = code;
    preview_record(outcome, "refit", code);
    if (code != PRO_TK_NO_ERROR)
        return false;

    // Refresh clears temporary graphics without dropping highlights; Repaint is
    // the full redraw. Both are recorded because a display-list capture that
    // runs before them is exactly the stale/blank image BUG-066 reports.
    outcome.refresh_code = ProWindowRefresh(window);
    code = ProWindowRepaint(window);
    outcome.repaint_code = code;
    preview_record(outcome, "repaint", code);
    return code == PRO_TK_NO_ERROR;
}

// Compact raw-code report for the display-only repaint path (FEAT-052): the
// same recorded steps as the raster capture minus the raster itself.
static nlohmann::json preview_window_codes_json(const PreviewStepOutcome &outcome) {
    return {{"display", outcome.display_code},
            {"window_get", outcome.window_get_code},
            {"window_model_get", outcome.window_model_code},
            {"current_set", outcome.current_set_code},
            {"current_get", outcome.current_get_code},
            {"activate", outcome.activate_code},
            {"refit", outcome.refit_code},
            {"refresh", outcome.refresh_code},
            {"repaint", outcome.repaint_code},
            {"window_matches_model", outcome.window_matches_model},
            {"failed_step", outcome.failed_step.empty() ? nlohmann::json(nullptr)
                                                        : nlohmann::json(outcome.failed_step)},
            {"failed_code", outcome.failed_code}};
}

// One capture attempt. Shared step body: the datum-display guard writes its
// restore evidence into `outcome` by reference, so every exit path - failed
// steps included - leaves the original display state restored.
static void capture_preview_steps(ProMdl model, const std::wstring &file, bool apply_view_matrix,
                                  double width_inches, double height_inches, ProRasterType type,
                                  PreviewStepOutcome &outcome) {
    outcome.path = file;
    if (preview_has_no_geometry(model)) {
        outcome.skipped_no_geometry = true;
        outcome.raster_code = PRO_TK_GENERAL_ERROR; // no raster call was made
        return outcome;
    }
    if (!bind_model_window(model, outcome))
        return;

    PreviewDatumDisplayGuard datums(outcome);
    datums.hide(model);

    if (apply_view_matrix) {
        int code = ProViewMatrixSet(model, nullptr, preview_isometric_view);
        outcome.view_matrix_set_code = code;
        preview_record(outcome, "view_matrix_set", code);
        if (code != PRO_TK_NO_ERROR)
            return;
        ProMatrix actual = {};
        code = ProViewMatrixGet(model, nullptr, actual);
        outcome.view_matrix_get_code = code;
        preview_record(outcome, "view_matrix_get", code);
        if (code != PRO_TK_NO_ERROR)
            return;
        // Creo applies its own shift and scale to the requested matrix, so only
        // the rotation can be compared. A mismatch is reported, not fatal.
        outcome.view_matrix_matches = preview_rotation_matches(actual);
    }

    if (!repaint_bound_window(outcome.window, outcome))
        return;

    if (file.size() >= PRO_PATH_SIZE) {
        outcome.failed_step = "output_path";
        outcome.failed_code = PRO_TK_BAD_INPUTS;
        return;
    }
    ProPath output;
    wcscpy_s(output, PRO_PATH_SIZE, file.c_str());
    int code = ProRasterFileWrite(outcome.window, PRORASTERDEPTH_24, width_inches, height_inches,
                                  PRORASTERDPI_100, type, output);
    outcome.raster_code = code;
    preview_record(outcome, "raster", code);
    if (code != PRO_TK_NO_ERROR)
        return;

    preview_confirm_file(outcome);
}

// One capture attempt. apply_view_matrix is false for drawings, whose view is
// owned by the drawing view rather than by the model orientation.
static PreviewStepOutcome capture_preview(ProMdl model, const std::wstring &file,
                                          bool apply_view_matrix, double width_inches,
                                          double height_inches, ProRasterType type) {
    PreviewStepOutcome outcome;
    capture_preview_steps(model, file, apply_view_matrix, width_inches, height_inches, type,
                          outcome);
    return outcome;
}

static bool preview_written(const PreviewStepOutcome &outcome) {
    return !outcome.skipped_no_geometry && outcome.failed_step.empty() &&
           outcome.raster_code == PRO_TK_NO_ERROR &&
           outcome.file_bytes > 0;
}

// Result/diagnostic block. Raw codes are kept as returned; status is derived
// only from them plus the written file size, never from assumptions.
static nlohmann::json preview_outcome_json(const PreviewStepOutcome &outcome) {
    nlohmann::json codes = {{"display", outcome.display_code},
                            {"window_get", outcome.window_get_code},
                            {"window_model_get", outcome.window_model_code},
                            {"current_set", outcome.current_set_code},
                            {"current_get", outcome.current_get_code},
                            {"activate", outcome.activate_code},
                            {"view_matrix_set", outcome.view_matrix_set_code},
                            {"view_matrix_get", outcome.view_matrix_get_code},
                            {"refit", outcome.refit_code},
                            {"refresh", outcome.refresh_code},
                            {"repaint", outcome.repaint_code},
                            {"raster", outcome.raster_code}};
    // The filesystem stage is only meaningful after a zero raster code; before
    // that there is no file to confirm and the block stays null.
    nlohmann::json file_check = nullptr;
    if (!outcome.skipped_no_geometry && outcome.raster_code == PRO_TK_NO_ERROR)
        file_check = {{"stage", "after_raster"},
                      {"absolute", outcome.file_check_absolute},
                      {"parent_exists", outcome.file_check_parent_exists},
                      {"exists", outcome.file_check_exists},
                      {"is_file", outcome.file_check_regular},
                      {"size", outcome.file_check_size},
                      {"error_code", outcome.file_check_code},
                      {"error_category", outcome.file_check_category.empty()
                                             ? nlohmann::json(nullptr)
                                             : nlohmann::json(outcome.file_check_category)},
                      {"error_message", outcome.file_check_message.empty()
                                            ? nlohmann::json(nullptr)
                                            : nlohmann::json(outcome.file_check_message)}};
<<<<<<< HEAD
    if (outcome.skipped_no_geometry)
        for (auto &entry : codes.items())
            entry.value() = nullptr; // no Toolkit capture step was attempted
    return {{"status", outcome.skipped_no_geometry
                           ? "skipped_no_geometry"
                           : preview_written(outcome) ? "written" : "failed"},
=======
    // FEAT-008/BUG-088 (H): occlusion diagnostics in their own block. The
    // capture status and the raw codes above are never rewritten here.
    nlohmann::json datum_options = nlohmann::json::array();
    for (const PreviewDatumOptionOutcome &option : outcome.datum_options) {
        datum_options.push_back(
            {{"name", preview_utf8(option.name)},
             {"get_code", option.get_code},
             {"hide_code", option.hide_code},
             {"restore_code", option.restore_code},
             {"previous_value", option.previous_known
                                    ? nlohmann::json(preview_utf8(option.previous_value))
                                    : nlohmann::json(nullptr)},
             {"hidden", option.hidden},
             {"restored", option.restored}});
    }
    return {{"status", preview_written(outcome) ? "written" : "failed"},
>>>>>>> codex/q13-result-budget
            {"path", outcome.path.empty() ? nlohmann::json(nullptr)
                                          : nlohmann::json(preview_utf8(outcome.path))},
            {"bytes", outcome.file_bytes},
            {"file_check", file_check},
            {"window", outcome.window},
            {"window_matches_model", outcome.window_matches_model},
            {"current_window_matches", outcome.current_window_matches},
            {"view_matrix_matches", outcome.view_matrix_matches},
            {"codes", codes},
            {"failed_step", outcome.failed_step.empty() ? nlohmann::json(nullptr)
                                                        : nlohmann::json(outcome.failed_step)},
<<<<<<< HEAD
            {"failed_code", outcome.skipped_no_geometry ? nlohmann::json(nullptr)
                                                        : nlohmann::json(outcome.failed_code)}};
=======
            {"failed_code", outcome.failed_code},
            {"datum_display",
             {{"model_type", outcome.datum_model_type},
              {"type_query_code", outcome.datum_type_query_code},
              {"applicable", outcome.datum_applicable},
              {"attempted", outcome.datum_attempted},
              {"hide_status", outcome.datum_hide_status},
              {"restore_status", outcome.datum_restore_status},
              {"options", datum_options},
              // Session display options only: ProConfigoptSet changes the
              // session value and the guard restores it; the user's config.pro
              // is never written by a capture.
              {"config_file_written", false}}}};
>>>>>>> codex/q13-result-budget
}
