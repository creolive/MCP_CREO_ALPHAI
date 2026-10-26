// Automatic solve diagnostics. Failed experimental conditioning/rigid paths are not exposed.
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
    }
}
static J solve_profile(ProSection section, const J &op) {
    if (op.contains("solver") || op.contains("normalize"))
        throw std::runtime_error(
            "Experimental sketch solver requests are disabled pending native acceptance");
    std::string mode = op.value("dimensioning", "auto");
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    CK(ProSectionEpsilonSet(section, mode == "coordinates" ? 0.000000001 : 0.0001));
    ProWSecerror error = nullptr;
    CK(ProSecerrorAlloc(&error));
    J info = {
        {"requested", mode}, {"used", mode}, {"final_units", "mm"}, {"coordinate_scaling", false}};
    try {
        ProError solved = ProSectionSolve(section, &error);
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
            log("SKETCH_SOLVE_WITHOUT_INFERENCE=%d\n", solved);
            if (solved)
                section_errors(error, "coordinate_without_inference");
        }
        if (mode != "coordinates" || solved) {
            solved = ProSectionAutodim(section, &error);
            log("AutodimensionSketch=%d\n", solved);
            if (solved)
                section_errors(error, "autodimension");
            check(solved, "AutodimensionSketch");
        } else
            log("AutodimensionSketch=SKIPPED_COMPLETE_COORDINATE_DIMENSIONS\n");
        ProError regenerated = ProSectionRegenerate(section, &error);
        if (regenerated)
            section_errors(error, "regenerate");
        check(regenerated, "RegenerateSolvedSketch");
    } catch (...) {
        ProSecerrorFree(&error);
        throw;
    }
    CK(ProSecerrorFree(&error));
    return info;
}
