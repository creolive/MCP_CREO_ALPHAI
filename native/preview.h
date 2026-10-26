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
#include <ProToolkit.h>
#include <ProUtil.h>
#include <ProView.h>
#include <ProWindows.h>
#include <Windows.h>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <string>

// Canonical 3/4 view used by every preview and export. Each row is unit length
// and the rows are orthogonal, which the SDK view-matrix setter requires.
// Mutable only because the SDK signature takes a non-const ProMatrix.
static ProMatrix preview_isometric_view = {
    {0.7071067811865476, -0.4082482904638631, 0.5773502691896258, 0},
    {0.7071067811865476, 0.4082482904638631, -0.5773502691896258, 0},
    {0, 0.8164965809277260, 0.5773502691896258, 0},
    {0, 0, 0, 1}};

struct PreviewStepOutcome {
    std::wstring path;
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
    std::string failed_step;
    int failed_code = 0;
};

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

static bool preview_rotation_matches(const ProMatrix actual) {
    for (int row = 0; row < 3; row++)
        for (int column = 0; column < 3; column++)
            if (std::fabs(actual[row][column] - preview_isometric_view[row][column]) > 1e-3)
                return false;
    return true;
}

// One capture attempt. apply_view_matrix is false for drawings, whose view is
// owned by the drawing view rather than by the model orientation.
static PreviewStepOutcome capture_preview(ProMdl model, const std::wstring &file,
                                          bool apply_view_matrix, double width_inches,
                                          double height_inches, ProRasterType type) {
    PreviewStepOutcome outcome;
    outcome.path = file;
    int code = ProMdlDisplay(model);
    outcome.display_code = code;
    preview_record(outcome, "display", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    code = ProMdlWindowGet(model, &outcome.window);
    outcome.window_get_code = code;
    preview_record(outcome, "window_get", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

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
        return outcome;
    if (!outcome.window_matches_model) {
        outcome.failed_step = "window_model_mismatch";
        outcome.failed_code = PRO_TK_GENERAL_ERROR;
        return outcome;
    }

    code = ProWindowCurrentSet(outcome.window);
    outcome.current_set_code = code;
    preview_record(outcome, "current_set", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    int current = -1;
    code = ProWindowCurrentGet(&current);
    outcome.current_get_code = code;
    preview_record(outcome, "current_get", code);
    outcome.current_window_matches = code == PRO_TK_NO_ERROR && current == outcome.window;
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    // ProWindowActivate only takes effect after control returns to Creo, so it
    // is recorded but never treated as a step that can fail the capture.
    outcome.activate_code = ProWindowActivate(outcome.window);

    if (apply_view_matrix) {
        code = ProViewMatrixSet(model, nullptr, preview_isometric_view);
        outcome.view_matrix_set_code = code;
        preview_record(outcome, "view_matrix_set", code);
        if (code != PRO_TK_NO_ERROR)
            return outcome;
        ProMatrix actual = {};
        code = ProViewMatrixGet(model, nullptr, actual);
        outcome.view_matrix_get_code = code;
        preview_record(outcome, "view_matrix_get", code);
        if (code != PRO_TK_NO_ERROR)
            return outcome;
        // Creo applies its own shift and scale to the requested matrix, so only
        // the rotation can be compared. A mismatch is reported, not fatal.
        outcome.view_matrix_matches = preview_rotation_matches(actual);
    }

    code = ProWindowRefit(outcome.window);
    outcome.refit_code = code;
    preview_record(outcome, "refit", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    // Refresh clears temporary graphics without dropping highlights; Repaint is
    // the full redraw. Both are recorded because a display-list capture that
    // runs before them is exactly the stale/blank image BUG-066 reports.
    outcome.refresh_code = ProWindowRefresh(outcome.window);
    code = ProWindowRepaint(outcome.window);
    outcome.repaint_code = code;
    preview_record(outcome, "repaint", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    if (file.size() >= PRO_PATH_SIZE) {
        outcome.failed_step = "output_path";
        outcome.failed_code = PRO_TK_BAD_INPUTS;
        return outcome;
    }
    ProPath output;
    wcscpy_s(output, PRO_PATH_SIZE, file.c_str());
    code = ProRasterFileWrite(outcome.window, PRORASTERDEPTH_24, width_inches, height_inches,
                              PRORASTERDPI_100, type, output);
    outcome.raster_code = code;
    preview_record(outcome, "raster", code);
    if (code != PRO_TK_NO_ERROR)
        return outcome;

    std::error_code error;
    auto size = std::filesystem::file_size(std::filesystem::path(file), error);
    outcome.file_bytes = error ? -1 : static_cast<long long>(size);
    if (error || outcome.file_bytes <= 0) {
        outcome.failed_step = "output_file";
        outcome.failed_code = error ? PRO_TK_E_NOT_FOUND : PRO_TK_GENERAL_ERROR;
    }
    return outcome;
}

static bool preview_written(const PreviewStepOutcome &outcome) {
    return outcome.failed_step.empty() && outcome.raster_code == PRO_TK_NO_ERROR &&
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
    return {{"status", preview_written(outcome) ? "written" : "failed"},
            {"path", outcome.path.empty() ? nlohmann::json(nullptr)
                                          : nlohmann::json(preview_utf8(outcome.path))},
            {"bytes", outcome.file_bytes},
            {"window", outcome.window},
            {"window_matches_model", outcome.window_matches_model},
            {"current_window_matches", outcome.current_window_matches},
            {"view_matrix_matches", outcome.view_matrix_matches},
            {"codes", codes},
            {"failed_step", outcome.failed_step.empty() ? nlohmann::json(nullptr)
                                                        : nlohmann::json(outcome.failed_step)},
            {"failed_code", outcome.failed_code}};
}
