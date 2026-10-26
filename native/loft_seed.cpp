// Ordinary Blend reuse with a matching number of external sketch sections.
// This does not create Blend element trees or add sections to a smaller seed.
// The caller supplies a saved native seed; only the new owned copy is modified.
#include <ProCurve.h>
static ProMdl load_isolated_loft_seed(const std::wstring &filename, J &observation) {
    observation = {{"status", "not_attempted"}};
    std::filesystem::path source(filename);
    ProPath previous, directory;
    CK(ProDirectoryCurrentGet(previous));
    path(directory, source.parent_path().wstring());
    CK(ProDirectoryChange(directory));
    ProMdl loaded = nullptr;
    try {
        std::wstring basename = source.filename().wstring();
        auto extension = basename.find(L".prt");
        if (extension == std::wstring::npos)
            throw std::runtime_error("Invalid native loft seed filename");
        ProMdlName to;
        std::wstring unique =
            L"ls_" + std::filesystem::path(generic_job).filename().wstring().substr(0, 20);
        wcscpy_s(to, unique.c_str());
        ProMdl existing = nullptr;
        ProError found = ProMdlInit(to, PRO_MDL_PART, &existing);
        if (found != PRO_TK_E_NOT_FOUND)
            throw std::runtime_error(
                "Isolated loft seed name already exists; inspect the previous job");
        // Load the exact snapshotted bytes/version under a unique name. Avoid Creo's
        // name-based file search and collisions with a user's already loaded seed.
        auto isolated = source.parent_path() / (unique + L".prt.1");
        std::filesystem::copy_file(source, isolated);
        ProPath file;
        path(file, isolated.wstring());
        ProError code = ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &loaded);
        observation = {{"status", code ? "load_failed" : "loaded"}, {"toolkit_code", code}};
        check(code, "ProMdlFiletypeLoad");
    } catch (...) {
        ProDirectoryChange(previous);
        throw;
    }
    CK(ProDirectoryChange(previous));
    return loaded;
}

static int blend_profile_owner(ProType type, int id) {
    if (type == PRO_FEATURE)
        return id;
    if (type != PRO_COMP_CRV)
        throw std::runtime_error("Blend sections must select independent sketch features or their "
                                 "complete composite curves");
    ProGeomitem item;
    CK(ProModelitemInit(board, id, PRO_CURVE, &item));
    ProCurve curve;
    CK(ProGeomitemToCurve(&item, &curve));
    ProEnttype curve_type;
    CK(ProCurveTypeGet(curve, &curve_type));
    if (curve_type != PRO_ENT_CMP_CRV)
        throw std::runtime_error("Blend curve reference is not a complete sketch composite");
    ProFeature owner;
    CK(ProGeomitemFeatureGet(&item, &owner));
    return owner.id;
}

static ProError collect_blend_composite(ProGeomitem *item, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProCurve curve;
    CK(ProGeomitemToCurve(item, &curve));
    ProEnttype type;
    CK(ProCurveTypeGet(curve, &type));
    if (type == PRO_ENT_CMP_CRV)
        ((J *)data)->push_back(item->id);
    return PRO_TK_NO_ERROR;
}

static ProSelection blend_profile_selection(int feature_id, ProType type) {
    ProFeature profile;
    CK(ProFeatureInit((ProSolid)board, feature_id, &profile));
    ProSelection selected = nullptr;
    if (type == PRO_FEATURE) {
        CK(ProSelectionAlloc(nullptr, &profile, &selected));
        return selected;
    }
    if (type != PRO_COMP_CRV)
        throw std::runtime_error("Unsupported Blend profile reference type");
    J composites = J::array();
    CK(ProFeatureGeomitemVisit(&profile, PRO_CURVE, collect_blend_composite, nullptr, &composites));
    if (composites.size() != 1)
        throw std::runtime_error(
            "Replacement sketch must contain exactly one complete composite curve");
    ProModelitem composite;
    CK(ProModelitemInit(board, composites[0], PRO_COMP_CRV, &composite));
    CK(ProSelectionAlloc(nullptr, &composite, &selected));
    return selected;
}

static void suppress_seed_for_profiles(int feature_id, bool suppress) {
    // Prevent automatic dimensions from referencing coincident seed solid edges.
    // Only the isolated, new owned copy is affected; the original seed is intact.
    int *ids = nullptr;
    CK(ProArrayAlloc(1, sizeof(int), 1, (ProArray *)&ids));
    ids[0] = feature_id;
    ProError code;
    if (suppress) {
        ProFeatureDeleteOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_DELETE_NO_OPTS;
        code = ProFeatureWithoptionsSuppress((ProSolid)board, ids, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&options);
    } else {
        ProFeatureResumeOptions *options = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProFeatureResumeOptions), 1, (ProArray *)&options));
        options[0] = PRO_FEAT_RESUME_NO_OPTS;
        code = ProFeatureWithoptionsResume((ProSolid)board, ids, options, PRO_REGEN_NO_FLAGS);
        ProArrayFree((ProArray *)&options);
    }
    ProArrayFree((ProArray *)&ids);
    check(code, suppress ? "SuppressSeedDuringSketchCreation" : "ResumeSeedAfterSketchCreation");
    temporarily_suppressed_loft = suppress ? feature_id : -1;
}

static J validate_loft_seed(const J &binding) {
    ProFeature blend;
    CK(ProFeatureInit((ProSolid)board, binding.at("feature_id"), &blend));
    ProFeattype type;
    CK(ProFeatureTypeGet(&blend, &type));
    ProLine subtype = L"";
    CK(ProFeatureSubtypeGet(&blend, subtype));
    if (type != PRO_FEAT_PROTRUSION ||
        (wcscmp(subtype, L"\u6df7\u5408") && _wcsicmp(subtype, L"Blend")))
        throw std::runtime_error(
            "Seed feature must be an ordinary native Blend (Chinese/English Creo supported)");
    int requested = (int)binding.at("sections").size();
    if (requested < 2 || requested > 20)
        throw std::runtime_error("Blend requires between 2 and 20 sections");
    int sections = 0;
    CK(ProFeatureNumSectionsGet(&blend, &sections));
    if (sections != requested)
        throw std::runtime_error("Seed Blend section count does not match requested sections");
    J setting = read_blend_setting(blend.id, L"seed");
    if (setting["interpolation"] != binding.value("interpolation", "straight"))
        throw std::runtime_error("Seed Blend interpolation does not match requested interpolation; "
                                 "supply a matching native seed");
    J state = inspection();
    int solids = 0;
    for (auto b : state["bodies"])
        if (b["state"].get<int>() == PRO_BODY_STATE_ACTIVE)
            solids++;
    if (solids != 1)
        throw std::runtime_error("Seed must contain exactly one active solid body");
    for (auto f : state["features"]) {
        int t = f["type"], id = f["id"];
        if (id != blend.id && t != PRO_FEAT_DATUM && t != PRO_FEAT_CSYS &&
            t != PRO_FEAT_DATUM_AXIS && t != PRO_FEAT_CURVE)
            throw std::runtime_error("Seed contains unsupported additional features; use a "
                                     "dedicated Blend reference part");
    }
    ProReference *refs = nullptr;
    ProError reference_code =
        ProFeatureReferenceEditRefsGet((ProSolid)board, &blend, PRO_EDITREF_REF_TYPE_ALL, &refs);
    log("SeedBlendReferences id=%d current_window=%d code=%d\n", blend.id, win, reference_code);
    if (reference_code) {
        if (refs)
            ProReferencearrayFree(refs);
        throw std::runtime_error("Cannot read seed Blend edit references after activating its "
                                 "model window (Toolkit code " +
                                 std::to_string(reference_code) +
                                 "); finish modal Creo commands, verify the seed uses independent "
                                 "external sketch sections, and inspect native.log");
    }
    J profiles = J::array();
    try {
        int n = 0;
        CK(ProArraySizeGet((ProArray)refs, &n));
        for (int i = 0; i < n; i++) {
            ProType rt;
            int id;
            ProMdl owner;
            CK(ProReferenceTypeGet(refs[i], &rt));
            CK(ProReferenceIdGet(refs[i], &id));
            CK(ProReferenceOwnerGet(refs[i], &owner));
            if (owner != board)
                throw std::runtime_error(
                    "External-model references are not supported in a loft seed");
            if (rt == PRO_FEATURE || rt == PRO_COMP_CRV) {
                int profile = blend_profile_owner(rt, id);
                ProFeature f;
                CK(ProFeatureInit((ProSolid)board, profile, &f));
                ProFeattype ft;
                CK(ProFeatureTypeGet(&f, &ft));
                if (ft != PRO_FEAT_CURVE)
                    throw std::runtime_error("Seed sections must reference independent sketches");
                profiles.push_back(profile);
            } else if (rt != PRO_BODY)
                throw std::runtime_error("Unsupported reference in Blend seed");
        }
    } catch (...) {
        ProReferencearrayFree(refs);
        throw;
    }
    ProReferencearrayFree(refs);
    if ((int)profiles.size() != requested)
        throw std::runtime_error(
            "Seed must reference one independent sketch per requested section");
    // Sort by feature order, matching the documented seed convention: low Z first.
    std::map<int, int> ordered;
    std::set<int> unique;
    for (auto id : profiles) {
        int value = id.get<int>();
        if (!unique.insert(value).second)
            throw std::runtime_error("Seed sketch sections must be distinct");
        ProFeature f;
        CK(ProFeatureInit((ProSolid)board, value, &f));
        int number = 0;
        CK(ProFeatureNumberGet(&f, &number));
        ordered.emplace(number, value);
    }
    if ((int)ordered.size() != requested)
        throw std::runtime_error("Seed section feature order is ambiguous");
    profiles = J::array();
    for (auto item : ordered)
        profiles.push_back(item.second);
    return profiles;
}

static J bind_loft_seed(const J &binding, const J &original_profiles) {
    int section_count = (int)original_profiles.size();
    if (section_count != (int)binding.at("sections").size())
        throw std::runtime_error("Blend section mapping size changed");
    std::map<int, int> replacements;
    for (int i = 0; i < section_count; i++)
        replacements.emplace(original_profiles[i].get<int>(), feature_id(binding["sections"][i]));
    for (auto replacement : replacements) {
        ProFeature profile;
        CK(ProFeatureInit((ProSolid)board, replacement.second, &profile));
        ProIntlist parents = nullptr;
        int count = 0;
        CK(ProFeatureParentsGet(&profile, &parents, &count));
        bool dependent = false;
        for (int i = 0; i < count; i++)
            if (parents[i] == binding["feature_id"].get<int>() || replacements.count(parents[i]))
                dependent = true;
        ProArrayFree((ProArray *)&parents);
        if (dependent)
            throw std::runtime_error(
                "New loft profile unexpectedly references seed geometry; provide independent "
                "sketch dimensions/constraints and inspect native.log");
    }
    int final_sketch = feature_id(binding["sections"].back());
    ProFeature last;
    CK(ProFeatureInit((ProSolid)board, final_sketch, &last));
    int position = 0;
    CK(ProFeatureNumberGet(&last, &position));
    int *ids = nullptr;
    CK(ProArrayAlloc(1, sizeof(int), 1, (ProArray *)&ids));
    ids[0] = binding["feature_id"];
    ProError moved =
        ProFeatureWithoptionsReorder((ProSolid)board, ids, position, PRO_REGEN_NO_FLAGS);
    ProArrayFree((ProArray *)&ids);
    check(moved, "ReorderSeedBlend");
    ProFeature blend;
    CK(ProFeatureInit((ProSolid)board, binding["feature_id"], &blend));
    ProReference *old_refs = nullptr;
    ProReference *new_refs = nullptr;
    CK(ProFeatureReferenceEditRefsGet((ProSolid)board, &blend, PRO_EDITREF_REF_TYPE_ALL,
                                      &old_refs));
    int count = 0;
    CK(ProArraySizeGet((ProArray)old_refs, &count));
    CK(ProArrayAlloc(0, sizeof(ProReference), 1, (ProArray *)&new_refs));
    int replaced = 0;
    try {
        for (int i = 0; i < count; i++) {
            int id;
            ProType type;
            CK(ProReferenceIdGet(old_refs[i], &id));
            CK(ProReferenceTypeGet(old_refs[i], &type));
            ProSelection s = nullptr;
            int profile =
                (type == PRO_FEATURE || type == PRO_COMP_CRV) ? blend_profile_owner(type, id) : -1;
            auto target = replacements.find(profile);
            if (target != replacements.end()) {
                s = blend_profile_selection(target->second, type);
                replaced++;
            } else
                CK(ProReferenceToSelection(old_refs[i], &s));
            ProReference r = nullptr;
            ProError converted = ProSelectionToReference(s, &r);
            ProSelectionFree(&s);
            check(converted, "CopyBlendReference");
            CK(ProArrayObjectAdd((ProArray *)&new_refs, -1, 1, &r));
        }
        if (replaced != section_count)
            throw std::runtime_error("Seed reference identity changed during sketch creation");
        // Creo 10 requires the complete reference array, including unchanged body refs.
        CK(ProFeatureReferenceEdit((ProSolid)board, &blend, old_refs, new_refs,
                                   PRO_REGEN_NO_FLAGS));
    } catch (...) {
        if (new_refs)
            ProReferencearrayFree(new_refs);
        ProReferencearrayFree(old_refs);
        throw;
    }
    ProReferencearrayFree(new_refs);
    ProReferencearrayFree(old_refs);
    CK(ProArrayAlloc(section_count, sizeof(int), 1, (ProArray *)&ids));
    for (int i = 0; i < section_count; i++)
        ids[i] = original_profiles[i].get<int>();
    ProFeatureDeleteOptions *opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&opts));
    opts[0] = PRO_FEAT_DELETE_NO_OPTS;
    ProError removed = ProFeatureWithoptionsDelete((ProSolid)board, ids, opts, PRO_REGEN_NO_FLAGS);
    ProArrayFree((ProArray *)&ids);
    ProArrayFree((ProArray *)&opts);
    check(removed, "RemoveUnusedSeedSketches");
    // Confirm the same native feature still exists after structural edits,
    // before distinguishing an unnamed feature from a missing feature.
    CK(ProFeatureInit((ProSolid)board, binding["feature_id"], &blend));
    ProName name, current_name = L"";
    wcscpy_s(name, wide(binding["label"]).c_str());
    ProError named = ProModelitemNameGet(&blend, current_name);
    log("SEED_BLEND_NAME_GET feature=%d code=%d\n", blend.id, named);
    // A valid native seed feature can have no explicitly assigned item name.
    // SDK E_NOT_FOUND in this query is distinct from a missing feature ID.
    if (named != PRO_TK_E_NOT_FOUND)
        check(named, "ReadSeedBlendName");
    if (named == PRO_TK_E_NOT_FOUND || _wcsicmp(name, current_name))
        CK(ProModelitemNameSet(&blend, name));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    ProFeatStatus status;
    CK(ProFeatureStatusGet(&blend, &status));
    if (status != PRO_FEAT_ACTIVE)
        throw std::runtime_error("Rebound Blend is not active");
    J meta = {{"feature_id", blend.id},
              {"op", "loft_seed"},
              {"sections", binding["sections"]},
              {"interpolation", binding.value("interpolation", "straight")},
              {"construction", "native_multisection_blend_seed_rebinding"},
              {"seed_sha256", binding["snapshot_sha256"]}};
    aliases[binding["label"].get<std::string>()] = meta;
    // The seed binding is a plan-level construction step, not one of the
    // requested operations; it must not add an extra operations[] entry (T02).
    return {{"op", "loft_seed"},
            {"label", binding["label"]},
            {"feature_id", blend.id},
            {"construction", "native_multisection_blend_seed_rebinding"},
            {"seed_sha256", binding["snapshot_sha256"]}};
}
