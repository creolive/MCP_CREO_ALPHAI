// Live-session fixture for DEV-047 T05 non-millimeter unit acceptance.
//
// Mode (one Toolkit connection per run, connect pattern copied from
// wb080_live_fixture):
//   inch <source_prt_path> <new_name> <output_dir>
//       Load the unmanaged millimeter source part from disk (its name must
//       not be resident in the session; the driver erases its copy first),
//       add two 25.4 mm offset datum planes and one datum axis through them,
//       convert the model to inch units keeping the physical size
//       (PRO_UNITCONVERT_SAME_SIZE), rename it to <new_name>, back it up into
//       <output_dir> and erase the in-memory copy. The source file on disk is
//       never saved or modified.
//
// The fixture never touches managed models (the driver only passes its own
// build-directory copies), never erases anything but the object it just
// loaded, never writes outside <output_dir>, and reports every Toolkit code
// as one JSON object on stdout. Any failure aborts without saving.

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
#include <ProMdlUnits.h>
#include <ProModelitem.h>
#include <ProSolid.h>
#include <ProFeature.h>
#include <ProFeatType.h>
#include <ProSelection.h>
#include <ProElement.h>
#include <ProElemId.h>
#include <ProValue.h>
#include <ProReference.h>
#include <ProDtmPln.h>
#include <ProDtmAxis.h>

namespace {

ProMdl board = nullptr;

std::wstring widen(const char *text) {
    std::size_t size = std::mbstowcs(nullptr, text, 0) + 1;
    std::wstring out(size, L'\0');
    std::mbstowcs(out.data(), text, size);
    out.resize(std::wcslen(out.c_str()));
    return out;
}

struct ToolkitFailure {
    ProError code;
};

void check(ProError code) {
    if (code != PRO_TK_NO_ERROR)
        throw ToolkitFailure{code};
}

#define CK(x) check((x))

ProElement node(ProElement parent, int id) {
    ProElement e = nullptr;
    CK(ProElementAlloc((ProElemId)id, &e));
    if (parent)
        CK(ProElemtreeElementAdd(parent, nullptr, e));
    return e;
}

void integer(ProElement parent, int id, int value) {
    CK(ProElementIntegerSet(node(parent, id), value));
}

void real_value(ProElement parent, int id, double value) {
    ProElement e = node(parent, id);
    CK(ProElementDecimalsSet(e, 6));
    CK(ProElementDoubleSet(e, value));
}

void text(ProElement parent, int id, const wchar_t *value) {
    CK(ProElementWstringSet(node(parent, id), const_cast<wchar_t *>(value)));
}

ProSelection selection(int id, ProType type) {
    ProModelitem item;
    CK(ProModelitemInit(board, id, type, &item));
    ProSelection s = nullptr;
    CK(ProSelectionAlloc(nullptr, &item, &s));
    return s;
}

void ref(ProElement parent, int id, ProSelection s) {
    ProReference r = nullptr;
    CK(ProSelectionToReference(s, &r));
    CK(ProElementReferenceSet(node(parent, id), r));
}

// First two datum-plane features (visit order = ascending id) that own
// exactly one surface geometry item; the stock seed template places the two
// mutually orthogonal base planes there.
struct SurfaceCollector {
    int id;
    int count;
};

ProError count_surface(ProGeomitem *item, ProError status, ProAppData data) {
    if (status == PRO_TK_NO_ERROR) {
        SurfaceCollector *collector = (SurfaceCollector *)data;
        collector->id = item->id;
        collector->count++;
    }
    return PRO_TK_NO_ERROR;
}

struct PlaneVisit {
    int feature_ids[2] = {};
    int surface_ids[2] = {};
    int found = 0;
};

ProError plane_filter(ProFeature *feature, ProAppData data) {
    ProFeattype type;
    if (ProFeatureTypeGet(feature, &type) != PRO_TK_NO_ERROR || type != PRO_FEAT_DATUM)
        return PRO_TK_CONTINUE;
    SurfaceCollector collector = {0, 0};
    if (ProFeatureGeomitemVisit(feature, PRO_SURFACE, count_surface, nullptr, &collector) !=
        PRO_TK_NO_ERROR)
        return PRO_TK_CONTINUE;
    if (collector.count != 1)
        return PRO_TK_CONTINUE;
    PlaneVisit *state = (PlaneVisit *)data;
    if (state->found < 2) {
        state->feature_ids[state->found] = feature->id;
        state->surface_ids[state->found] = collector.id;
    }
    state->found++;
    return PRO_TK_NO_ERROR;
}

ProError plane_visitor(ProFeature *, ProError, ProAppData) {
    return PRO_TK_NO_ERROR;
}

int surface_of_feature(int feature_id) {
    ProFeature feature;
    CK(ProModelitemInit(board, feature_id, PRO_FEATURE, (ProModelitem *)&feature));
    SurfaceCollector collector = {0, 0};
    CK(ProFeatureGeomitemVisit(&feature, PRO_SURFACE, count_surface, nullptr, &collector));
    if (collector.count != 1)
        throw ToolkitFailure{PRO_TK_GENERAL_ERROR};
    return collector.id;
}

ProFeature create(ProElement root) {
    ProModelitem owner;
    CK(ProMdlToModelitem(board, &owner));
    ProSelection s = nullptr;
    CK(ProSelectionAlloc(nullptr, &owner, &s));
    ProFeatureCreateOptions *opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&opts));
    opts[0] = PRO_FEAT_CR_NO_OPTS;
    ProFeature feature = {};
    ProErrorlist errors = {};
    ProError code = ProFeatureWithoptionsCreate(s, root, opts, PRO_REGEN_NO_FLAGS, &feature,
                                                &errors);
    ProArrayFree((ProArray *)&opts);
    ProSelectionFree(&s);
    if (code != PRO_TK_NO_ERROR) {
        std::printf("{\"step\":\"create_errors\",\"first\":%d}\n",
                    errors.error_number ? errors.error_list[0].error : 0);
        throw ToolkitFailure{code};
    }
    return feature;
}

ProFeature offset_plane(int reference_surface, double offset, const wchar_t *name) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM);
    text(root, PRO_E_STD_FEATURE_NAME, name);
    ProElement constraints = node(root, PRO_E_DTMPLN_CONSTRAINTS);
    ProElement constraint = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
    integer(constraint, PRO_E_DTMPLN_CONSTR_TYPE, PRO_DTMPLN_OFFS);
    ProSelection s = selection(reference_surface, PRO_SURFACE);
    ref(constraint, PRO_E_DTMPLN_CONSTR_REF, s);
    real_value(constraint, PRO_E_DTMPLN_CONSTR_REF_OFFSET, offset);
    ProSelectionFree(&s);
    ProFeature feature = create(root);
    CK(ProElementFree(&root));
    return feature;
}

ProFeature axis_through(int first_surface, int second_surface, const wchar_t *name) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_AXIS);
    text(root, PRO_E_STD_FEATURE_NAME, name);
    ProElement constraints = node(root, PRO_E_DTMAXIS_CONSTRAINTS);
    for (int surface : {first_surface, second_surface}) {
        ProElement constraint = node(constraints, PRO_E_DTMAXIS_CONSTRAINT);
        integer(constraint, PRO_E_DTMAXIS_CONSTR_TYPE, PRO_DTMAXIS_CONSTR_TYPE_THRU);
        ProSelection s = selection(surface, PRO_SURFACE);
        ref(constraint, PRO_E_DTMAXIS_CONSTR_REF, s);
        ProSelectionFree(&s);
    }
    ProFeature feature = create(root);
    CK(ProElementFree(&root));
    return feature;
}

void abort_with_erase(ProMdl mdl, std::wstring *error, const wchar_t *message, int code) {
    *error = message;
    ProMdlErase(mdl);
    board = nullptr;
}

int run_inch(const char *source_path, const char *new_name_text, const char *output_dir_text,
             std::wstring *error) {
    ProMdl mdl = nullptr;
    ProPath source = {};
    wcsncpy_s(source, widen(source_path).c_str(), _TRUNCATE);
    ProPath output_dir = {};
    wcsncpy_s(output_dir, widen(output_dir_text).c_str(), _TRUNCATE);
    ProName new_name = {};
    wcsncpy_s(new_name, widen(new_name_text).c_str(), _TRUNCATE);

    ProError load_code = ProMdlFiletypeLoad(source, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &mdl);
    if (load_code != PRO_TK_NO_ERROR) {
        *error = L"source file could not be loaded (resident same-name model?)";
        return 10;
    }
    board = mdl;
    ProPath origin = {};
    CK(ProMdlOriginGet(mdl, origin));
    if (_wcsicmp(origin, source) != 0) {
        abort_with_erase(mdl, error,
                         L"loaded model origin does not match the requested source file; "
                         L"aborting before any change",
                         11);
        return 11;
    }

    PlaneVisit planes = {};
    ProError visit_code = ProSolidFeatVisit((ProSolid)mdl, plane_visitor, plane_filter, &planes);
    std::printf("{\"step\":\"base_planes\",\"visit\":%d,\"found\":%d,\"feature_a\":%d,"
                "\"feature_b\":%d,\"surface_a\":%d,\"surface_b\":%d}\n",
                visit_code, planes.found, planes.feature_ids[0], planes.feature_ids[1],
                planes.surface_ids[0], planes.surface_ids[1]);
    if (visit_code != PRO_TK_NO_ERROR || planes.found < 2) {
        abort_with_erase(mdl, error,
                         L"two datum plane features with one surface each were not found", 12);
        return 12;
    }

    // 25.4 mm offsets become exactly 1.0 inch after the SAME_SIZE conversion,
    // giving the acceptance driver a non-trivial raw-inch axis coordinate.
    ProError step = PRO_TK_NO_ERROR;
    try {
        ProFeature offset_a = offset_plane(planes.surface_ids[0], 25.4, L"t05_off_a");
        ProFeature offset_b = offset_plane(planes.surface_ids[1], 25.4, L"t05_off_b");
        int offset_surface_a = surface_of_feature(offset_a.id);
        int offset_surface_b = surface_of_feature(offset_b.id);
        std::printf("{\"step\":\"offset_planes\",\"feature_a\":%d,\"feature_b\":%d,"
                    "\"surface_a\":%d,\"surface_b\":%d}\n",
                    offset_a.id, offset_b.id, offset_surface_a, offset_surface_b);
        ProFeature axis = axis_through(offset_surface_a, offset_surface_b, L"t05_inch_axis");
        std::printf("{\"step\":\"datum_axis\",\"feature_id\":%d}\n", axis.id);
    } catch (ToolkitFailure failure) {
        step = failure.code;
    }
    if (step != PRO_TK_NO_ERROR) {
        abort_with_erase(mdl, error, L"datum feature creation on the private copy failed", 13);
        return 13;
    }

    step = PRO_TK_NO_ERROR;
    ProError unit_init_code = PRO_TK_GENERAL_ERROR;
    ProError unit_create_code = PRO_TK_GENERAL_ERROR;
    ProError unit_resolved_code = PRO_TK_GENERAL_ERROR;
    ProUnititem inch = {};
    try {
        unit_init_code = ProUnitInitByExpression(mdl, L"inch", &inch);
        if (unit_init_code == PRO_TK_NO_ERROR) {
            unit_resolved_code = PRO_TK_NO_ERROR;
        } else {
            // A pure millimeter model does not carry the inch unit in its unit
            // table; create it explicitly: 1 inch = 25.4 mm, referenced to mm.
            ProUnitConversion conversion = {25.4, 0.0};
            unit_create_code = ProUnitCreate(mdl, L"inch", &conversion, L"mm", &inch);
            unit_resolved_code = unit_create_code;
        }
    } catch (ToolkitFailure failure) {
        step = failure.code;
    }
    std::printf("{\"step\":\"unit_init\",\"expression\":%d,\"create\":%d,\"resolved\":%d}\n",
                unit_init_code, unit_create_code, unit_resolved_code);
    if (step != PRO_TK_NO_ERROR || unit_resolved_code != PRO_TK_NO_ERROR) {
        abort_with_erase(mdl, error, L"the inch unit could not be resolved in the model", 14);
        return 14;
    }

    ProError system_code = PRO_TK_GENERAL_ERROR;
    ProError convert_code = PRO_TK_GENERAL_ERROR;
    ProError verify_code = PRO_TK_GENERAL_ERROR;
    ProName length_name = L"?";
    try {
        ProUnitsystem system = {};
        system.owner = mdl;
        wcscpy_s(system.name, L"t05_inch_system");
        ProUnititem *units = nullptr;
        CK(ProArrayAlloc(1, sizeof(ProUnititem), 1, (ProArray *)&units));
        units[0] = inch;
        system_code = ProMdlUnitsystemCreate(mdl, PRO_UNITSYSTEM_MLT, L"t05_inch_system", units,
                                             &system);
        ProArrayFree((ProArray *)&units);
        std::printf("{\"step\":\"unit_system\",\"create\":%d}\n", system_code);
        if (system_code == PRO_TK_NO_ERROR)
            convert_code = ProMdlPrincipalunitsystemSet(
                mdl, &system, PRO_UNITCONVERT_SAME_SIZE, PRO_B_FALSE, PRO_VALUE_UNUSED);
        std::printf("{\"step\":\"unit_convert\",\"set\":%d}\n", convert_code);
        if (convert_code == PRO_TK_NO_ERROR) {
            ProUnitsystem principal = {};
            ProUnititem length = {};
            verify_code = ProMdlPrincipalunitsystemGet(mdl, &principal);
            if (verify_code == PRO_TK_NO_ERROR)
                verify_code = ProUnitsystemUnitGet(&principal, PRO_UNITTYPE_LENGTH, &length);
            if (verify_code == PRO_TK_NO_ERROR)
                wcscpy_s(length_name, length.name);
        }
        std::printf("{\"step\":\"unit_verify\",\"get\":%d,\"length_unit\":\"%ls\"}\n", verify_code,
                    length_name);
    } catch (ToolkitFailure failure) {
        step = failure.code;
    }
    if (step != PRO_TK_NO_ERROR || system_code != PRO_TK_NO_ERROR ||
        convert_code != PRO_TK_NO_ERROR || verify_code != PRO_TK_NO_ERROR) {
        abort_with_erase(mdl, error, L"SAME_SIZE inch conversion did not verify", 15);
        return 15;
    }

    ProError rename_code = ProMdlnameRename(mdl, new_name);
    std::printf("{\"step\":\"rename\",\"code\":%d}\n", rename_code);
    if (rename_code != PRO_TK_NO_ERROR) {
        abort_with_erase(mdl, error, L"renaming the converted copy failed", 16);
        return 16;
    }
    ProError backup_code = ProMdlnameBackup(mdl, output_dir);
    std::printf("{\"step\":\"backup\",\"code\":%d}\n", backup_code);
    if (backup_code != PRO_TK_NO_ERROR) {
        abort_with_erase(mdl, error, L"backing up the converted copy failed", 17);
        return 17;
    }
    ProError erase_code = ProMdlErase(mdl);
    board = nullptr;
    std::printf("{\"step\":\"erase\",\"code\":%d}\n", erase_code);
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    if (argc != 5 || std::strcmp(argv[1], "inch") != 0) {
        std::printf("{\"error\":\"usage: t05_units_fixture inch <source.prt> <new_name> "
                    "<output_dir>\"}\n");
        return 2;
    }
    char empty[] = "";
    ProBoolean random = PRO_B_FALSE;
    ProProcessHandle process;
    ProError connect_code =
        ProEngineerConnect(empty, nullptr, nullptr, empty, PRO_B_FALSE, 5, &random, &process);
    if (connect_code != PRO_TK_NO_ERROR) {
        std::printf("{\"mode\":\"inch\",\"connect\":%d,\"error\":\"connect failed\"}\n",
                    connect_code);
        return 3;
    }
    std::wstring error;
    int result = 0;
    try {
        result = run_inch(argv[2], argv[3], argv[4], &error);
    } catch (ToolkitFailure failure) {
        std::printf("{\"error\":\"toolkit call failed with code %d\"}\n", failure.code);
        if (board) {
            ProMdlErase(board);
            board = nullptr;
        }
        result = 18;
    }
    if (!error.empty())
        std::printf("{\"error\":\"%ls\"}\n", error.c_str());
    ProError disconnect_code = ProEngineerDisconnect(&process, 5);
    std::printf("{\"connect\":%d,\"disconnect\":%d}\n", connect_code, disconnect_code);
    return result;
}
