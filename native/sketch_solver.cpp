// Automatic solve diagnostics. Failed experimental conditioning/rigid paths are not exposed.
// DEV-071: reset for every operation; preserve only actual attempted call codes
// when a throw prevents the ordinary sketch result from being returned.
static J last_sketch_solver_info = nullptr;
static J sketch_solver_receipt(const J &info) {
    J stages = info.value("stages", J::object());
    return {{"requested", info.value("requested", J(nullptr))},
            {"used", info.value("used", J(nullptr))},
            {"selection_reason", info.value("selection_reason", J(nullptr))},
            {"stages",
             {{"initial_solve", stages.value("initial_solve", J(nullptr))},
              {"retry_without_inference", stages.value("retry_without_inference", J(nullptr))},
              {"autodimension", stages.value("autodimension", J(nullptr))},
              {"section_regenerate", stages.value("section_regenerate", J(nullptr))}}},
            {"completed", info.value("completed", false)},
            {"recovered", info.value("recovered", false)}};
}
static void section_errors(ProWSecerror error, const char *phase) {
    int n = 0;
    ProSecerrorCount(&error, &n);
    log("SECTION_ERRORS phase=%s count=%d\n", phase, n);
    for (int i = 0; i < n; i++) {
        ProMsg msg = {};
        ProSecerrorMsgGet(error, i, msg);
        char utf8[4096] = {};
        WideCharToMultiByte(CP_UTF8, 0, msg, -1, utf8, sizeof(utf8), nullptr, nullptr);
        log("SECTION_ERROR phase=%s message=%s\n", phase, utf8);
        // BUG-097 L2: keep the original section messages for the structured
        // CompleteFeature failure receipt (bounded capture, see geometry.cpp).
        capture_section_error(phase, utf8);
    }
}
static J solve_profile(ProSection section, const J &op) {
    if (op.contains("solver") || op.contains("normalize"))
        throw std::runtime_error(
            "Experimental sketch solver requests are disabled pending native acceptance");
    std::string mode = op.value("dimensioning", "auto");
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    // FEAT-039/W01: the sketch epsilon is reported for the record. The
    // 2026-11-05 live measurement showed it is NOT the endpoint coincidence
    // tolerance: a 5e-4 mm gap stayed open with the epsilon raised to 2e-3 mm,
    // while an 8.2e-7 mm gap closes in the default path. The epsilon is
    // therefore left at the mode default and the controlled weld stays gated.
    double epsilon = mode == "coordinates" ? 0.000000001 : 0.0001;
    bool weld_requested = op.value("endpoint_policy", "report") == "weld";
    CK(ProSectionEpsilonSet(section, epsilon));
    // BUG-097 L2: this solve is the section-error provenance for a possible
    // CompleteFeature failure later in the same operation; start a fresh
    // bounded capture so a previous operation's messages cannot leak in.
    reset_section_error_capture();
    ProWSecerror error = nullptr;
    CK(ProSecerrorAlloc(&error));
    J info = {{"requested", mode},
              {"used", mode},
              {"final_units", "mm"},
              {"coordinate_scaling", false},
              {"epsilon_mm", epsilon},
              {"weld_requested", weld_requested},
              {"epsilon_source", "mode_default"}};
    if (last_sketch_solver_info.is_object()) {
        info["requested"] = last_sketch_solver_info.value("requested", J(mode));
        info["selection_reason"] = last_sketch_solver_info.value("selection_reason", J(nullptr));
    }
    info["stages"] = J::object();
    info["completed"] = false;
    info["recovered"] = false;
    last_sketch_solver_info = info;
    try {
        ProError solved = ProSectionSolve(section, &error);
        info["stages"]["initial_solve"] = solved;
        last_sketch_solver_info = info;
        log("SKETCH_SOLVE=%d mode=%s\n", solved, mode.c_str());
        if (solved)
            section_errors(error, "solve");
        if (mode == "coordinates" && solved) {
            ProIntlist ids = nullptr;
            int count = 0;
            CK(ProSectionConstraintsIdsGet(section, &ids, &count));
            log("COORDINATE_INFERRED_CONSTRAINTS=%d\n", count);
            for (int i = 0; i < count; i++) {
                ProConstraintType type;
                ProConstraintStatus status;
                int n = 0, *entities = nullptr;
                ProSectionPointType *points = nullptr;
                CK(ProSectionConstraintsGet(section, ids[i], &type, &status, &n, &entities,
                                            &points));
                log("COORDINATE_CONSTRAINT id=%d type=%d status=%d refs=%d\n", ids[i], (int)type,
                    (int)status, n);
                for (int j = 0; j < n; j++)
                    log("COORDINATE_CONSTRAINT_REF id=%d entity=%d sense=%d\n", ids[i], entities[j],
                        points[j]);
                if (entities)
                    ProArrayFree((ProArray *)&entities);
                if (points)
                    ProArrayFree((ProArray *)&points);
                if (type == PRO_CONSTRAINT_TANGENT_ENTS || type == PRO_CONSTRAINT_COLLINEAR_LINES)
                    CK(ProSectionConstraintDeny(section, ids[i]));
            }
            if (ids)
                ProArrayFree((ProArray *)&ids);
            solved = ProSectionSolve(section, &error);
            info["stages"]["retry_without_inference"] = solved;
            last_sketch_solver_info = info;
            log("SKETCH_SOLVE_WITHOUT_INFERENCE=%d\n", solved);
            if (solved)
                section_errors(error, "coordinate_without_inference");
        }
        if (mode != "coordinates" || solved) {
            solved = ProSectionAutodim(section, &error);
            info["stages"]["autodimension"] = solved;
            last_sketch_solver_info = info;
            log("AutodimensionSketch=%d\n", solved);
            if (solved)
                section_errors(error, "autodimension");
            check(solved, "AutodimensionSketch");
        } else
            log("AutodimensionSketch=SKIPPED_COMPLETE_COORDINATE_DIMENSIONS\n");
        ProError regenerated = ProSectionRegenerate(section, &error);
        info["stages"]["section_regenerate"] = regenerated;
        last_sketch_solver_info = info;
        log("SectionRegenerate=%d mode=%s\n", regenerated, mode.c_str());
        if (regenerated)
            section_errors(error, "regenerate");
        check(regenerated, "RegenerateSolvedSketch");
        info["completed"] = true;
        info["recovered"] = info["stages"]["initial_solve"].get<int>() != PRO_TK_NO_ERROR;
        last_sketch_solver_info = info;
    } catch (...) {
        ProSecerrorFree(&error);
        throw;
    }
    CK(ProSecerrorFree(&error));
    return info;
}
