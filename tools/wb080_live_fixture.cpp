// Live-session fixture for the 0.5.2 acceptance evidence (BUG-080 + FEAT-006).
//
// Modes (one Toolkit connection per run, unique-filter connect like the worker):
//   suppress <model_name> <feature_id>
//       Suppress exactly one feature of the named session part, regenerate and
//       save. Aborts without changes when the model is not found.
//   asm <assembly_file_path> <component_model_name>
//       Load the assembly file (an inch template copy prepared by the driver),
//       place the named session part as a component with identity rotation and
//       translation (1, 2, 3) in assembly units, regenerate, save and display.
//
// The fixture never creates or erases models, never closes windows, never writes
// a model whose name does not match the arguments, and reports every Toolkit
// code as one JSON object on stdout.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <string>

#include <ProToolkit.h>
#include <ProCore.h>
#include <ProUtil.h>
#include <ProArray.h>
#include <ProMdl.h>
#include <ProSolid.h>
#include <ProFeature.h>
#include <ProAsmcomp.h>

namespace {

std::wstring widen(const char *text) {
    std::size_t size = std::mbstowcs(nullptr, text, 0) + 1;
    std::wstring out(size, L'\0');
    std::mbstowcs(out.data(), text, size);
    out.resize(std::wcslen(out.c_str()));
    return out;
}

ProError find_session_model(const std::wstring &name, ProMdlType type, ProMdl *found) {
    ProMdl *list = nullptr;
    int listed = 0;
    ProError code = ProSessionMdlList(type, &list, &listed);
    if (code != PRO_TK_NO_ERROR)
        return code;
    ProError match = PRO_TK_E_NOT_FOUND;
    for (int i = 0; i < listed; ++i) {
        ProMdlName current = {};
        if (ProMdlMdlnameGet(list[i], current) == PRO_TK_NO_ERROR &&
            _wcsicmp(current, name.c_str()) == 0) {
            *found = list[i];
            match = PRO_TK_NO_ERROR;
            break;
        }
    }
    ProArrayFree((ProArray *)&list);
    return match;
}

struct LastFeature {
    int id;
};

ProError track_last_feature(ProFeature *feature, ProError status, ProAppData data) {
    if (status != PRO_TK_NO_ERROR)
        return PRO_TK_NO_ERROR;
    LastFeature *last = (LastFeature *)data;
    if (feature->id > last->id)
        last->id = feature->id;
    return PRO_TK_NO_ERROR;
}

int run_suppress(const char *model_name, const char *feature_text, std::wstring *error) {
    ProMdl model = nullptr;
    ProError find_code = find_session_model(widen(model_name), PRO_MDL_PART, &model);
    if (find_code != PRO_TK_NO_ERROR) {
        *error = L"model not found in session";
        return 10;
    }
    int feature_id = std::atoi(feature_text);
    if (std::strcmp(feature_text, "max") == 0) {
        LastFeature last = {};
        if (ProSolidFeatVisit((ProSolid)model, track_last_feature, nullptr, &last) !=
                PRO_TK_NO_ERROR ||
            last.id <= 0) {
            *error = L"no feature could be visited";
            return 12;
        }
        feature_id = last.id;
    }
    int *ids = nullptr;
    ProArrayAlloc(0, sizeof(int), 1, (ProArray *)&ids);
    ProArrayObjectAdd((ProArray *)&ids, -1, 1, &feature_id);
    ProFeatureDeleteOptions *options = nullptr;
    ProArrayAlloc(0, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options);
    ProError suppress_code = ProFeatureWithoptionsSuppress((ProSolid)model, ids, options, 0);
    ProError regenerate_code = suppress_code == PRO_TK_NO_ERROR
                                  ? ProSolidRegenerate((ProSolid)model, PRO_B_TRUE)
                                  : PRO_TK_NO_ERROR;
    ProError save_code = suppress_code == PRO_TK_NO_ERROR ? ProMdlSave(model) : PRO_TK_NO_ERROR;
    ProArrayFree((ProArray *)&ids);
    ProArrayFree((ProArray *)&options);
    // ProFeatureWithoptionsSuppress already brings the solid up to date; the
    // explicit regenerate is recorded but not treated as failure (Creo answers
    // PRO_TK_BAD_CONTEXT when there is nothing left to regenerate).
    std::printf(
        "{\"mode\":\"suppress\",\"find\":%d,\"feature_id\":%d,\"suppress\":%d,"
        "\"regenerate\":%d,\"save\":%d}\n",
        find_code, feature_id, suppress_code, regenerate_code, save_code);
    return suppress_code || save_code ? 11 : 0;
}

int run_assembly(const char *assembly_path, const char *component_name, std::wstring *error) {
    std::wstring assembly_wide = widen(assembly_path);
    wchar_t assembly_file[PRO_PATH_SIZE] = {};
    wcsncpy(assembly_file, assembly_wide.c_str(), PRO_PATH_SIZE - 1);
    ProMdl assembly = nullptr;
    ProError load_code =
        ProMdlFiletypeLoad(assembly_file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &assembly);
    if (load_code != PRO_TK_NO_ERROR) {
        *error = L"assembly template copy could not be loaded";
        return 20;
    }
    ProMdl component = nullptr;
    ProError find_code = find_session_model(widen(component_name), PRO_MDL_PART, &component);
    if (find_code != PRO_TK_NO_ERROR) {
        *error = L"component model not found in session";
        return 21;
    }
    ProError display_code = ProMdlDisplay(assembly);
    ProMatrix placement = {};
    placement[0][0] = 1.0;
    placement[1][1] = 1.0;
    placement[2][2] = 1.0;
    placement[3][0] = 1.0;
    placement[3][1] = 2.0;
    placement[3][2] = 3.0;
    ProAsmcomp placed = {};
    ProError assemble_code =
        ProAsmcompAssemble((ProAssembly)assembly, (ProSolid)component, placement, &placed);
    ProError regenerate_code =
        assemble_code == PRO_TK_NO_ERROR ? ProSolidRegenerate((ProSolid)assembly, PRO_B_TRUE)
                                         : PRO_TK_NO_ERROR;
    ProError save_code =
        assemble_code == PRO_TK_NO_ERROR ? ProMdlSave(assembly) : PRO_TK_NO_ERROR;
    std::printf(
        "{\"mode\":\"asm\",\"load\":%d,\"find\":%d,\"display\":%d,\"assemble\":%d,"
        "\"component_feature_id\":%d,\"regenerate\":%d,\"save\":%d}\n",
        load_code, find_code, display_code, assemble_code, placed.id, regenerate_code,
        save_code);
    return assemble_code || save_code ? 22 : 0;
}

}  // namespace

int main(int argc, char **argv) {
    if (argc != 4 || (std::strcmp(argv[1], "suppress") && std::strcmp(argv[1], "asm"))) {
        std::printf("{\"error\":\"usage: wb080_live_fixture suppress|asm <arg1> <arg2>\"}\n");
        return 2;
    }
    char empty[] = "";
    ProBoolean random = PRO_B_FALSE;
    ProProcessHandle process;
    ProError connect_code =
        ProEngineerConnect(empty, nullptr, nullptr, empty, PRO_B_FALSE, 5, &random, &process);
    if (connect_code != PRO_TK_NO_ERROR) {
        std::printf("{\"mode\":\"%s\",\"connect\":%d,\"error\":\"connect failed\"}\n", argv[1],
                    connect_code);
        return 3;
    }
    std::wstring error;
    int result = std::strcmp(argv[1], "suppress") == 0
                     ? run_suppress(argv[2], argv[3], &error)
                     : run_assembly(argv[2], argv[3], &error);
    if (!error.empty())
        std::printf("{\"error\":\"%ls\"}\n", error.c_str());
    ProError disconnect_code = ProEngineerDisconnect(&process, 5);
    std::printf("{\"connect\":%d,\"disconnect\":%d}\n", connect_code, disconnect_code);
    return result;
}
