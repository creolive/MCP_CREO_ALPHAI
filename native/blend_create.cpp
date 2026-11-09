// Creo 10 ordinary Blend: asynchronous orchestration with a small synchronous
// external-selection callback. All references are resolved before the dashboard.
#include <ProToolkitDll.h>
#include <ProSelbuffer.h>
#include <ProMenu.h>
#include <ProUtil.h>
#include "callback_runtime.h"

// F01/B1: a client rejected by the resident-callback preflight must be able to
// discover the callback-free seed route at the point of failure. This is guidance
// only; it never loads a DLL and never changes Creo security settings.
static const char *const SEED_ROUTE_NOTE =
    "Callback-free alternative: creo_new_loft_part creates a NEW part by rebinding a "
    "published native Blend seed and does not need a resident DLL callback. Call "
    "creo_list_seeds to read callback_free_route and compare section_count, "
    "interpolation and seed_feature_id with the plan before submitting; "
    "creo_validate_seed checks the installed bytes. This route cannot append a Blend "
    "to an existing model, and available seeds do not prove the current Creo session "
    "can load them.";

static ProToolkitDllHandle resident_blend_callback(const std::filesystem::path &build,
                                                   std::string &command) {
    ProToolkitDllHandle module = nullptr;
    J status = callback_runtime_status(build, module, command);
    log("BLEND_CALLBACK_PREFLIGHT=%s\n", status.dump().c_str());
    if (!module) {
        J route = J::object();
        route["tool"] = "creo_new_loft_part";
        route["callback_required"] = false;
        route["preflight_tools"] = J::array({"creo_list_seeds", "creo_validate_seed"});
        route["note"] = SEED_ROUTE_NOTE;
        status["callback_free_route"] = route;
        throw std::runtime_error("BLEND_CALLBACK_SETUP_REQUIRED: " + status.dump());
    }
    return module;
}

[[noreturn]] static void require_blend_callback_setup(const std::filesystem::path &build) {
    ProName option = L"open_protk_unsigned_apps";
    ProPath value = L"";
    ProError code =
        trace_blend_call("blend_loader_policy", [&] { return ProConfigoptionGet(option, value); });
    std::wstring policy = value;
    for (auto &c : policy)
        if (c >= L'A' && c <= L'Z')
            c += L'a' - L'A';
    log("BLEND_LOADER_POLICY code=%d policy=%s\n", code, utf8(policy).c_str());
    throw std::runtime_error(
        "BLEND_CALLBACK_SETUP_REQUIRED: No DLL load or Blend creation was attempted. "
        "The unsigned Toolkit callback is not initialized, and Creo loader policy is " +
        (code ? std::string("unverified (Toolkit code ") + std::to_string(code) + ")"
              : utf8(policy)) +
        ". Modeling never loads a DLL, including under ALWAYS policy. Register and "
        "start the callback using Creo Auxiliary Applications and " +
        utf8((build / L"blend_callback_setup.json").wstring()) +
        " (registry_file), review its DLL prompt before modeling, then retry a new "
        "confirmed request. MCP never changes Creo security settings. " +
        std::string(SEED_ROUTE_NOTE));
}

static void resident_blend_task(ProToolkitDllHandle module, const char *function,
                                const std::wstring &request_file) {
    ProArgument *inputs = nullptr, *outputs = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProArgument), 1, (ProArray *)&inputs));
    inputs[0] = {};
    wcscpy_s(inputs[0].label, L"request_file");
    inputs[0].value.type = PRO_VALUE_TYPE_WSTRING;
    try {
        CK(ProValuedataWstringSet(&inputs[0].value, const_cast<wchar_t *>(request_file.c_str())));
        ProCharPath name;
        strcpy_s(name, function);
        ProError returned = PRO_TK_GENERAL_ERROR;
        ProError code = trace_blend_call(function, [&] {
            return ProToolkitTaskExecute(module, name, inputs, &outputs, &returned);
        });
        if (code || returned)
            throw std::runtime_error(
                std::string(function) + " rejected the resident callback request (Toolkit code " +
                std::to_string(code) + ", callback code " + std::to_string(returned) +
                "); inspect the active model/window and the previous Blend "
                "job before retrying; unknown requests are never reset automatically");
    } catch (...) {
        if (outputs)
            ProArgumentProarrayFree(&outputs);
        ProArgumentProarrayFree(&inputs);
        throw;
    }
    if (outputs)
        CK(ProArgumentProarrayFree(&outputs));
    CK(ProArgumentProarrayFree(&inputs));
}

static void generic_loft(const J &op) {
    if (op.value("mode", "add") != "add" || op.value("new_body", false))
        throw std::runtime_error(
            "Direct Blend currently supports solid add into the default body only");
    wchar_t executable[MAX_PATH];
    GetModuleFileNameW(nullptr, executable, MAX_PATH);
    const auto build = std::filesystem::path(executable).parent_path();
    J before = inspection(), curves = J::array();
    double previous_z = -HUGE_VAL;
    for (auto reference : op.at("sections")) {
        int id = feature_id(reference);
        J meta;
        for (auto item : aliases)
            if (item.value("feature_id", -1) == id &&
                (item.value("op", "") == "sketch" || item.value("op", "") == "airfoil_sketch"))
                meta = item;
        if (meta.is_null() || !meta.contains("origin") || !meta.contains("normal"))
            throw std::runtime_error("Direct Blend requires MCP-owned independent XY sketches");
        V normal = vec(meta["normal"]), origin = vec(meta["origin"]), u = vec(meta["u_axis"]);
        if (fabs(normal[0]) + fabs(normal[1]) + fabs(normal[2] - 1) + fabs(u[0] - 1) + fabs(u[1]) +
                fabs(u[2]) + fabs(origin[0]) + fabs(origin[1]) >
            1e-7)
            throw std::runtime_error("Blend sections require XY frames with strictly increasing Z");
        ProFeature profile;
        CK(ProFeatureInit((ProSolid)board, id, &profile));
        ProFeattype type;
        CK(ProFeatureTypeGet(&profile, &type));
        if (type != PRO_FEAT_CURVE)
            throw std::runtime_error("Blend section is not an independent sketch");
        ProSection actual = nullptr;
        CK(ProFeatureSectionCopy(&profile, 0, &actual));
        ProMatrix location;
        ProError positioned = ProSectionLocationGet(actual, location);
        CK(ProSectionFree(&actual));
        check(positioned, "InspectActualBlendSectionPlane");
        if (fabs(location[2][0]) + fabs(location[2][1]) + fabs(fabs(location[2][2]) - 1) +
                    fabs(location[3][0]) + fabs(location[3][1]) >
                1e-7 ||
            location[3][2] <= previous_z)
            throw std::runtime_error(
                "Actual Blend section planes require XY frames with strictly increasing Z");
        previous_z = location[3][2];
        log("BLEND_ACTUAL_SECTION_PLANE feature=%d z=%.12f\n", id, previous_z);
        J items = J::array();
        CK(ProFeatureGeomitemVisit(&profile, PRO_CURVE, collect_geom_ids, nullptr, &items));
        bool found = false;
        for (auto item : items) {
            ProCurve curve;
            CK(ProCurveInit((ProSolid)board, item["id"], &curve));
            ProEnttype kind;
            CK(ProCurveTypeGet(curve, &kind));
            if (kind != PRO_ENT_CMP_CRV) {
                curves.push_back(item["id"]);
                found = true;
                break;
            }
        }
        if (!found)
            throw std::runtime_error("Blend section has no selectable curve");
    }
    std::string resident_command;
    ProToolkitDllHandle module = resident_blend_callback(build, resident_command);
    if (!module)
        require_blend_callback_setup(build);
    activate_blend_context();
    CK(ProSelbufferClear());
    std::string token = "MechDogBlend_" + std::to_string(GetCurrentProcessId()) + "_" +
                        std::to_string(GetTickCount64());
    std::string command = resident_command;
    std::filesystem::path callback_dir = std::filesystem::path(generic_job) / token;
    std::filesystem::create_directory(callback_dir);
    std::ofstream request(callback_dir / L"callback_request.json", std::ios::binary);
    request << J{
        {"protocol", mechdog_callback::protocol},
        {"model_name", utf8(model_name)},
        {"command", command},
        {"curve_ids",
         curves}}.dump(2);
    request.close();
    bool prepared = false;
    log("BLEND_CALLBACK_MODE=resident\n");
    try {
        resident_blend_task(module, "MechDogBlendPrepare",
                            (callback_dir / L"callback_request.json").wstring());
        prepared = true;
        std::wstring macro =
            L"~ Command `ProCmdFtPBlend`; ~ Activate `main_dlg_cur` `chkbn.blend_sectionspage.0` "
            L"1; ~ Select `blend_sectionspage.0.0` `PH.sketchselopt` 1 `Selected`; ~ Activate `UI "
            L"Message Dialog` `confirm`;";
        for (size_t i = 0; i < curves.size(); i++) {
            if (i)
                macro += L"~ Activate `blend_sectionspage.0.0` `PH.insertbtn`;";
            macro += L"~ Focus `blend_sectionspage.0.0` `PH.curve_coll_repr`; ~ Select "
                     L"`blend_sectionspage.0.0` `PH.curve_coll_repr` 0; ~ Activate "
                     L"`blend_sectionspage.0.0` `PH.chain_btn`; ~ Select `chain_dlg` `ChainMethod` "
                     L"1 `others`; ~ Select `chain_dlg` `RuleOptions` 1 `all_curves_in_feature`; ~ "
                     L"Command `" +
                     wide(command) + L"`; ~ Activate `chain_dlg` `OKButton`;";
        }
        macro += L"~ Activate `main_dlg_cur` `chkbn.blend_optionspage.0` 1; ~ Select "
                 L"`blend_optionspage.0.0` `PH.blendoptions` 1 `" +
                 wide(op.value("interpolation", "straight") == "smooth" ? "Smooth" : "Straight") +
                 L"`; ~ Activate `main_dlg_cur` `dashInst0.Done`; ~ Activate `main_dlg_cur` "
                 L"`dashInst0.Quit`; ~ Activate `UI Message Dialog` `yes`;";
        CK(trace_blend_call("blend_macro_submit", [&] { return ProMacroLoad(macro.data()); }));
        log("PHASE=blend_feature_validation\n");
        J after = inspection();
        std::ifstream file(callback_dir / L"callback_result.json");
        J selected;
        file >> selected;
        if (selected.value("selected", 0) != (int)curves.size() ||
            selected.value("exception", false))
            throw std::runtime_error(
                "Blend callback did not select every section; inspect callback_result.json");
        std::set<int> original;
        for (auto f : before["features"])
            original.insert(f["id"].get<int>());
        std::vector<int> candidates;
        for (auto f : after["features"])
            if (!original.count(f["id"]) && f["type"].get<int>() == PRO_FEAT_PROTRUSION) {
                ProFeature native;
                CK(ProFeatureInit((ProSolid)board, f["id"], &native));
                ProLine subtype;
                CK(ProFeatureSubtypeGet(&native, subtype));
                if (!wcscmp(subtype, L"\u6df7\u5408") || !_wcsicmp(subtype, L"Blend"))
                    candidates.push_back(native.id);
            }
        if (candidates.size() != 1)
            throw std::runtime_error(
                "Blend command did not create exactly one active native solid Blend");
        ProFeature created;
        CK(ProFeatureInit((ProSolid)board, candidates[0], &created));
        int count = 0;
        CK(ProFeatureNumSectionsGet(&created, &count));
        if (count != (int)curves.size())
            throw std::runtime_error("Created Blend section count differs from request");
        if (read_blend_setting(created.id, L"created")["interpolation"] !=
            op.value("interpolation", "straight"))
            throw std::runtime_error("Created Blend interpolation differs from request");
        ProName label;
        wcscpy_s(label, wide(op["label"]).c_str());
        CK(ProModelitemNameSet(&created, label));
        remember(op, created,
                 {{"sections", op["sections"]},
                  {"interpolation", op.value("interpolation", "straight")},
                  {"construction", "native_blend_synchronous_selection"}});
    } catch (...) {
        if (prepared) {
            try {
                resident_blend_task(module, "MechDogBlendRelease",
                                    (callback_dir / L"callback_request.json").wstring());
            } catch (...) {
                log("RESIDENT_BLEND_RELEASE_FAILED=1\n");
            }
        }
        throw;
    }
    resident_blend_task(module, "MechDogBlendRelease",
                        (callback_dir / L"callback_request.json").wstring());
}
