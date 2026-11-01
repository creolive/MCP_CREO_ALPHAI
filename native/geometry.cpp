#include <cstdio>
#include <cstdarg>
#include <cmath>
#include <cstring>
#include <vector>
#include <stdexcept>
#include <share.h>
#include <windows.h>
#include <ProToolkit.h>
#include <ProCore.h>
#include <ProView.h>
#include <ProSecdim.h>
#include <fstream>
#include <sstream>
#include <string>
#include <algorithm>
#include <ProMdl.h>
#include <ProMdlUnits.h>
#include <ProModelitem.h>
#include <ProSolid.h>
#include <ProSolidBody.h>
#include <ProFeature.h>
#include <ProFeatType.h>
#include <ProSelection.h>
#include <ProElement.h>
#include <ProElemId.h>
#include <ProElempath.h>
#include <ProValue.h>
#include <ProReference.h>
#include <ProArray.h>
#include <ProExtrude.h>
#include <ProStdSection.h>
#include <ProSection.h>
#include <ProSecdim.h>
#include <ProSecerror.h>
#include <Pro2dEntdef.h>
#include <ProSurface.h>
#include <ProGeomitem.h>
#include <ProGeomitemdata.h>
#include <ProSurfacedata.h>
#include <ProRound.h>
#include <ProHole.h>
#include <ProBodyOpts.h>
#include <ProUtil.h>
#include <ProWindows.h>
#include <map>
// Both the plate and generic hole implementations need the SDK probes.
#include "constants.inc"

static FILE *board_log = nullptr;
static ProMdl board = nullptr;
static int win = -1;

static std::wstring folder, model_name, template_file;
static double length_mm = 80, width_mm = 60, thickness_mm = 20, radius_mm = 5;
struct Hole {
    double x, y, diameter;
};
static std::vector<Hole> holes;
static void log(const char *fmt, ...) {
    if (!board_log)
        return;
    va_list a;
    va_start(a, fmt);
    vfprintf(board_log, fmt, a);
    va_end(a);
    fflush(board_log);
}
static std::string last_toolkit_error;
static std::string last_feature_errors;
// BUG-097 L2: the ProErrorlist traversal below has always existed; what was
// missing was a bounded, structured copy of it for the failure receipt. The
// last CompleteFeature/create error list is kept here element by element (the
// sample is capped, the total is not) so generic.cpp can publish
// element/type/error triples instead of leaving them in native.log only.
struct FeatureErrorEntry {
    int element, type, error;
};
static std::vector<FeatureErrorEntry> feature_error_entries;
static int feature_error_total = 0;
static const int FEATURE_ERROR_SAMPLE_LIMIT = 20;
// BUG-097 L2: bounded capture of the raw section solver messages (solve,
// autodimension, regenerate phases). sketch_solver.cpp's section_errors()
// appends here; a CompleteFeature failure receipt carries them as the
// original section errors instead of forcing a log dig.
static std::vector<std::string> section_error_messages;
static int section_error_total = 0;
static bool section_error_captured = false;
static const int SECTION_ERROR_SAMPLE_LIMIT = 20;
static void reset_section_error_capture() {
    section_error_messages.clear();
    section_error_total = 0;
    section_error_captured = false;
}
static void capture_section_error(const char *phase, const char *message) {
    section_error_captured = true;
    section_error_total++;
    if ((int)section_error_messages.size() < SECTION_ERROR_SAMPLE_LIMIT) {
        std::string entry = phase;
        entry += ": ";
        entry += message;
        section_error_messages.push_back(std::move(entry));
    }
}
static void check(ProError e, const char *op) {
    log("%s=%d\n", op, e);
    if (e != PRO_TK_NO_ERROR) {
        last_toolkit_error = op;
        throw e;
    }
}
#define CK(x) check((x), #x)
static ProElement node(ProElement parent, int id) {
    ProElement e = nullptr;
    CK(ProElementAlloc((ProElemId)id, &e));
    if (parent)
        CK(ProElemtreeElementAdd(parent, nullptr, e));
    return e;
}
static void integer(ProElement p, int id, int v) {
    CK(ProElementIntegerSet(node(p, id), v));
}
static void real(ProElement p, int id, double v) {
    ProElement e = node(p, id);
    CK(ProElementDecimalsSet(e, 6));
    CK(ProElementDoubleSet(e, v));
}
static void text(ProElement p, int id, const wchar_t *v) {
    CK(ProElementWstringSet(node(p, id), const_cast<wchar_t *>(v)));
}
static ProSelection selection(int id, ProType t) {
    ProModelitem mi;
    CK(ProModelitemInit(board, id, t, &mi));
    ProSelection s = nullptr;
    CK(ProSelectionAlloc(nullptr, &mi, &s));
    return s;
}
static void ref(ProElement p, int id, ProSelection s) {
    ProReference r = nullptr;
    CK(ProSelectionToReference(s, &r));
    CK(ProElementReferenceSet(node(p, id), r));
}
static ProElement get(ProElement root, std::initializer_list<int> ids) {
    std::vector<ProElempathItem> items;
    for (int id : ids) {
        ProElempathItem p = {};
        p.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
        p.path_item.elem_id = (ProElemId)id;
        items.push_back(p);
    }
    ProElempath path = nullptr;
    CK(ProElempathAlloc(&path));
    CK(ProElempathDataSet(path, items.data(), (int)items.size()));
    ProElement result = nullptr;
    CK(ProElemtreeElementGet(root, path, &result));
    CK(ProElempathFree(&path));
    return result;
}
static void errors(const ProErrorlist &es) {
    last_feature_errors.clear();
    feature_error_entries.clear();
    feature_error_total = es.error_number;
    for (int i = 0; i < es.error_number; i++) {
        log("feature_error element=%d type=%d error=%d\n", es.error_list[i].err_item_id,
            es.error_list[i].err_item_type, es.error_list[i].error);
        if (i)
            last_feature_errors += "; ";
        last_feature_errors += "element=" + std::to_string(es.error_list[i].err_item_id) +
                               " type=" + std::to_string(es.error_list[i].err_item_type) +
                               " error=" + std::to_string(es.error_list[i].error);
        // Bounded structured sample: the full list stays in the log line above
        // and in last_feature_errors; the receipt carries at most the cap and
        // flags truncation through feature_error_total.
        if ((int)feature_error_entries.size() < FEATURE_ERROR_SAMPLE_LIMIT)
            feature_error_entries.push_back({es.error_list[i].err_item_id,
                                             es.error_list[i].err_item_type,
                                             es.error_list[i].error});
    }
}
static ProFeature create(ProElement root, ProFeatureCreateOptions opt = PRO_FEAT_CR_NO_OPTS) {
    ProModelitem mi;
    CK(ProMdlToModelitem(board, &mi));
    ProSelection s = nullptr;
    CK(ProSelectionAlloc(nullptr, &mi, &s));
    ProFeatureCreateOptions *opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&opts));
    opts[0] = opt;
    ProFeature feat = {};
    ProErrorlist es = {};
    ProError err = ProFeatureWithoptionsCreate(s, root, opts, PRO_REGEN_NO_FLAGS, &feat, &es);
    errors(es);
    ProArrayFree((ProArray *)&opts);
    ProSelectionFree(&s);
    check(err, "ProFeatureWithoptionsCreate");
    log("created_feature_id=%d\n", feat.id);
    return feat;
}

struct Plane {
    int id;
    double n[3], o[3];
};
static std::vector<Plane> planes;
static ProError geom_cb(ProGeomitem *gi, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProGeomitemdata *d = nullptr;
    if (ProGeomitemdataGet(gi, &d) == PRO_TK_NO_ERROR && d) {
        if (d->obj_type == PRO_SURFACE && d->data.p_surface_data &&
            d->data.p_surface_data->type == PRO_SRF_PLANE) {
            const ProPlanedata &p = d->data.p_surface_data->srf_shape.plane;
            Plane q = {};
            q.id = gi->id;
            memcpy(q.n, p.e3, sizeof(q.n));
            memcpy(q.o, p.origin, sizeof(q.o));
            planes.push_back(q);
            log("datum_plane id=%d normal=%.3f,%.3f,%.3f origin=%.3f,%.3f,%.3f\n", q.id, q.n[0],
                q.n[1], q.n[2], q.o[0], q.o[1], q.o[2]);
        }
        ProGeomitemdataFree(&d);
    }
    return PRO_TK_NO_ERROR;
}
static ProError datum_cb(ProFeature *f, ProError status, ProAppData) {
    ProFeattype type;
    if (!status && ProFeatureTypeGet(f, &type) == PRO_TK_NO_ERROR && type == PRO_FEAT_DATUM)
        ProFeatureGeomitemVisit(f, PRO_SURFACE, geom_cb, nullptr, nullptr);
    return PRO_TK_NO_ERROR;
}
static ProError surf_cb(ProSurface s, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProGeomitemdata *d = nullptr;
    if (ProSurfaceDataGet(s, &d) == PRO_TK_NO_ERROR && d) {
        auto p = d->data.p_surface_data;
        int id = 0;
        ProSurfaceIdGet(s, &id);
        if (p && p->type == PRO_SRF_PLANE) {
            Plane q = {};
            q.id = id;
            memcpy(q.n, p->srf_shape.plane.e3, sizeof(q.n));
            memcpy(q.o, p->srf_shape.plane.origin, sizeof(q.o));
            planes.push_back(q);
            log("solid_plane id=%d normal=%.3f,%.3f,%.3f origin=%.3f,%.3f,%.3f\n", q.id, q.n[0],
                q.n[1], q.n[2], q.o[0], q.o[1], q.o[2]);
        } else if (p && p->type == PRO_SRF_CYL) {
            auto c = p->srf_shape.cylinder;
            log("cylinder id=%d radius=%.9f origin=%.9f,%.9f,%.9f axis=%.6f,%.6f,%.6f\n", id,
                c.radius, c.origin[0], c.origin[1], c.origin[2], c.e3[0], c.e3[1], c.e3[2]);
        }
        ProGeomitemdataFree(&d);
    }
    return PRO_TK_NO_ERROR;
}
static int plane(int axis, double pos) {
    for (auto &p : planes)
        if (fabs(fabs(p.n[axis]) - 1) < 1e-7 && fabs(p.o[axis] - pos) < 1e-6)
            return p.id;
    log("MISSING_PLANE axis=%d pos=%f\n", axis, pos);
    throw PRO_TK_E_NOT_FOUND;
}
static ProSolidBody active_body() {
    ProSolidBody *all = nullptr;
    CK(ProSolidBodiesCollect((ProSolid)board, &all));
    int n = 0;
    ProArraySizeGet((ProArray)all, &n);
    ProSolidBody chosen = {};
    bool found = false;
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&all[i], &state));
        log("body id=%d state=%d\n", all[i].id, state);
        if (state == PRO_BODY_STATE_ACTIVE) {
            if (found)
                throw PRO_TK_GENERAL_ERROR;
            chosen = all[i];
            found = true;
        }
    }
    ProArrayFree((ProArray *)&all);
    if (!found)
        throw PRO_TK_E_NOT_FOUND;
    return chosen;
}
static ProError outline(Pro3dPnt bounds[2]) {
    auto body = active_body();
    return ProSolidBodyOutlineGet(&body, bounds);
}
static void remove_empty_body() {
    auto body = active_body();
    ProError def = ProSolidDefaultBodySet(&body);
    if (def != PRO_TK_NO_ERROR && def != PRO_TK_NO_CHANGE)
        check(def, "SetDefaultBody");
    ProSolidBody *all = nullptr;
    CK(ProSolidBodiesCollect((ProSolid)board, &all));
    int n = 0;
    ProArraySizeGet((ProArray)all, &n);
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state;
        ProSolidBodyStateGet(&all[i], &state);
        if ((state == PRO_BODY_STATE_NO_CONTR_FEAT || state == PRO_BODY_STATE_NO_GEOMETRY))
            CK(ProSolidBodyDelete(&all[i]));
    }
    ProArrayFree((ProArray *)&all);
}
static void refresh_planes() {
    planes.clear();
    auto b = active_body();
    CK(ProSolidBodySurfaceVisit(&b, surf_cb, nullptr));
}
static double volume() {
    ProMassProperty p = {};
    CK(ProSolidMassPropertyWithDensityGet((ProSolid)board, nullptr, PRO_MP_DENS_USE_ALWAYS, 1.0,
                                          &p));
    log("volume_mm3=%.12f\n", p.volume);
    return p.volume;
}
static void expect_volume(double wanted) {
    double v = volume();
    log("expected_volume_mm3=%.12f\n", wanted);
    if (fabs(v - wanted) > 0.01)
        throw PRO_TK_GENERAL_ERROR;
}

static void extrude() {
    planes.clear();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb, nullptr, nullptr));
    ProSelection z = selection(plane(2, 0), PRO_SURFACE), y = selection(plane(1, 0), PRO_SURFACE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_EXTRUDE);
    integer(root, PRO_E_EXT_SURF_CUT_SOLID_TYPE, PRO_EXT_FEAT_TYPE_SOLID);
    integer(root, PRO_E_REMOVE_MATERIAL, PRO_EXT_MATERIAL_ADD);
    text(root, PRO_E_STD_FEATURE_NAME, L"BASE_EXTRUDE");
    ProElement sec = node(root, PRO_E_STD_SECTION), setup = node(sec, PRO_E_STD_SEC_SETUP_PLANE);
    ref(setup, PRO_E_STD_SEC_PLANE, z);
    integer(setup, PRO_E_STD_SEC_PLANE_VIEW_DIR, PRO_SEC_VIEW_DIR_SIDE_ONE);
    integer(setup, PRO_E_STD_SEC_PLANE_ORIENT_DIR, PRO_SEC_ORIENT_DIR_UP);
    ref(setup, PRO_E_STD_SEC_PLANE_ORIENT_REF, y);
    ProElement depth = node(root, PRO_E_STD_EXT_DEPTH), from = node(depth, PRO_E_EXT_DEPTH_FROM),
               to = node(depth, PRO_E_EXT_DEPTH_TO);
    integer(from, PRO_E_EXT_DEPTH_FROM_TYPE, PRO_EXT_DEPTH_FROM_NONE);
    integer(to, PRO_E_EXT_DEPTH_TO_TYPE, PRO_EXT_DEPTH_TO_BLIND);
    real(to, PRO_E_EXT_DEPTH_TO_VALUE, thickness_mm);
    integer(node(root, PRO_E_BODY), PRO_E_BODY_USE, PRO_BODY_USE_NEW);
    ProFeature f = create(root, PRO_FEAT_CR_INCOMPLETE_FEAT);
    CK(ProElementFree(&root));
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    ProElement sketch = get(root, {PRO_E_STD_SECTION, PRO_E_SKETCHER});
    ProSection section = nullptr;
    CK(ProElementSpecialvalueGet(sketch, nullptr, (ProAppData *)&section));
    int ref_id;
    CK(ProSectionEntityFromProjection(section, y, &ref_id));
    ProSelection xref = selection(plane(0, 0), PRO_SURFACE);
    CK(ProSectionEntityFromProjection(section, xref, &ref_id));
    ProSelectionFree(&xref);
    ProMatrix loc;
    CK(ProSectionLocationGet(section, loc));
    for (int i = 0; i < 4; i++)
        log("section_matrix_%d=%.6f,%.6f,%.6f,%.6f\n", i, loc[i][0], loc[i][1], loc[i][2],
            loc[i][3]);
    // Project model XY corners into the section's orthonormal frame.
    double xy[4][2] = {{-length_mm / 2, -width_mm / 2},
                       {length_mm / 2, -width_mm / 2},
                       {length_mm / 2, width_mm / 2},
                       {-length_mm / 2, width_mm / 2}};
    double uv[4][2];
    for (int i = 0; i < 4; i++) {
        double p[3] = {xy[i][0] - loc[3][0], xy[i][1] - loc[3][1], -loc[3][2]};
        for (int j = 0; j < 2; j++)
            uv[i][j] = p[0] * loc[j][0] + p[1] * loc[j][1] + p[2] * loc[j][2];
    }
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef origin = {};
    origin.type = PRO_2D_COORD_SYS;
    origin.pnt[0] = 0;
    origin.pnt[1] = 0;
    int origin_id;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&origin, &origin_id));
    int ids[4];
    for (int i = 0; i < 4; i++) {
        Pro2dLinedef l = {};
        l.type = PRO_2D_LINE;
        memcpy(l.end1, uv[i], sizeof(l.end1));
        memcpy(l.end2, uv[(i + 1) % 4], sizeof(l.end2));
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&l, &ids[i]));
    }
    CK(ProSectionEpsilonSet(section, std::min(0.1, std::min(length_mm, width_mm) * 0.01)));
    for (int id : ids) {
        CK(ProSectionEntityConstructionSet(section, id, PRO_B_FALSE));
        Pro2dEntdef *entity = nullptr;
        CK(ProSectionEntityGet(section, id, &entity));
        auto l = (Pro2dLinedef *)entity;
        log("sketch_line id=%d a=%.9f,%.9f b=%.9f,%.9f\n", id, l->end1[0], l->end1[1], l->end2[0],
            l->end2[1]);
    }
    ProWSecerror se = nullptr;
    CK(ProSecerrorAlloc(&se));
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    ProError solve = ProSectionSolve(section, &se);
    log("ProSectionSolve=%d\n", solve);
    ProError err = ProSectionAutodim(section, &se);
    int count = 0;
    log("ProSecerrorCount=%d\n", ProSecerrorCount(&se, &count));
    log("section_error_count=%d\n", count);
    for (int i = 0; i < count; i++) {
        ProMsg msg;
        ProSecerrorMsgGet(se, i, msg);
        log("section_error=%ls\n", msg);
    }
    check(err, "section_solve");
    CK(ProSectionRegenerate(section, &se));
    CK(ProSecerrorFree(&se));
    CK(ProElementSpecialvalueSet(sketch, (ProAppData)section));
    ProFeatureCreateOptions *opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&opts));
    opts[0] = PRO_FEAT_CR_DEFINE_MISS_ELEMS;
    ProErrorlist es = {};
    err = ProFeatureWithoptionsRedefine(nullptr, &f, root, opts, PRO_REGEN_NO_FLAGS, &es);
    errors(es);
    ProArrayFree((ProArray *)&opts);
    check(err, "extrude_complete");
    ProFeatureElemtreeFree(&f, root);
    ProSelectionFree(&z);
    ProSelectionFree(&y);
    expect_volume(length_mm * width_mm * thickness_mm);
}
static void rounds() {
    refresh_planes();
    ProSelection sides[4] = {selection(plane(0, -length_mm / 2), PRO_SURFACE),
                             selection(plane(0, length_mm / 2), PRO_SURFACE),
                             selection(plane(1, -width_mm / 2), PRO_SURFACE),
                             selection(plane(1, width_mm / 2), PRO_SURFACE)};
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_ROUND);
    text(root, PRO_E_STD_FEATURE_NAME, L"FOUR_CORNERS_ROUND");
    ProElement sets = node(root, PRO_E_RNDCH_SETS);
    for (int i = 0; i < 4; i++) {
        ProElement set = node(sets, PRO_E_RNDCH_SET);
        integer(set, PRO_E_RNDCH_SHAPE_OPTIONS, PRO_ROUND_TYPE_CONSTANT);
        integer(node(set, PRO_E_RNDCH_COMPOUND_CONIC), PRO_E_RNDCH_CONIC_TYPE,
                PRO_ROUND_CONIC_DISABLE);
        ProElement refs = node(set, PRO_E_RNDCH_REFERENCES);
        integer(refs, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_SURF_SURF);
        ref(refs, PRO_E_RNDCH_REFERENCE_SURFACE1, sides[i / 2]);
        ref(refs, PRO_E_RNDCH_REFERENCE_SURFACE2, sides[2 + i % 2]);
        integer(node(set, PRO_E_RNDCH_COMPOUND_SPINE), PRO_E_RNDCH_BALL_SPINE,
                PRO_ROUND_ROLLING_BALL);
        ProElement radii = node(set, PRO_E_RNDCH_RADII), radius = node(radii, PRO_E_RNDCH_RADIUS),
                   leg = node(radius, PRO_E_RNDCH_LEG1);
        integer(leg, PRO_E_RNDCH_LEG_TYPE, PRO_ROUND_RADIUS_TYPE_VALUE);
        real(leg, PRO_E_RNDCH_LEG_VALUE, radius_mm);
    }
    integer(root, PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED);
    node(root, PRO_E_RNDCH_TRANSITIONS);
    create(root);
    CK(ProElementFree(&root));
    for (auto s : sides)
        ProSelectionFree(&s);
    expect_volume((length_mm * width_mm - (4 - acos(-1.0)) * radius_mm * radius_mm) * thickness_mm);
}
static void hole(int index, double x, double y, double dia) {
    refresh_planes();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb, nullptr, nullptr));
    Pro3dPnt box[2];
    CK(outline(box));
    double top = box[1][2];
    ProSelection face = selection(plane(2, top), PRO_SURFACE),
                 sx = selection(plane(0, 0), PRO_SURFACE), sy = selection(plane(1, 0), PRO_SURFACE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_HOLE);
    integer(root, PRO_E_FEATURE_FORM, PRO_HLE_TYPE_STRAIGHT);
    wchar_t name[80];
    swprintf_s(name, L"HOLE_%d_D%g_THRU", index, dia);
    text(root, PRO_E_STD_FEATURE_NAME, name);
    ProElement com = node(root, PRO_E_HLE_COM);
    integer(com, PRO_E_HLE_TYPE_NEW, PRO_HLE_NEW_TYPE_STRAIGHT);
    integer(com, PRO_E_HLE_MAKE_LIGHTWT, PRO_HLE_REGULAR);
    real(com, PRO_E_DIAMETER, dia);
    ProElement dep = node(com, PRO_E_HOLE_STD_DEPTH);
    integer(node(dep, PRO_E_HOLE_DEPTH_TO), PRO_E_HOLE_DEPTH_TO_TYPE,
            PRO_HLE_STRGHT_THRU_ALL_DEPTH);
    integer(node(dep, PRO_E_HOLE_DEPTH_FROM), PRO_E_HOLE_DEPTH_FROM_TYPE,
            PRO_HLE_STRGHT_NONE_DEPTH);
    integer(com, PRO_E_HLE_CRDIR_FLIP, PRO_HLE_CR_IN_SIDE_ONE);
    integer(com, PRO_E_HLE_TOP_CLEARANCE, PRO_HOLE_GEN_CLRNCE);
#if defined(MECHDOG_HAS_PRO_E_HLE_ADD_PARAMETERS) &&                                               \
    defined(MECHDOG_HAS_PRO_HOLE_NO_PARAMETERS_FLAG)
    integer(com, PRO_E_HLE_ADD_PARAMETERS, PRO_HOLE_NO_PARAMETERS_FLAG);
#endif
    integer(com, PRO_E_HLE_ADD_NOTE, PRO_HOLE_NO_NOTE_FLAG);
    ProElement place = node(root, PRO_E_HLE_PLACEMENT);
    ref(place, PRO_E_HLE_PRIM_REF, face);
    integer(place, PRO_E_HLE_PL_TYPE, PRO_HLE_PL_TYPE_LIN);
    ref(place, PRO_E_HLE_DIM_REF1, sx);
    integer(place, PRO_E_HLE_PLC_ALIGN_OPT1, x == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
    real(place, PRO_E_HLE_DIM_DIST1, x);
    ref(place, PRO_E_HLE_DIM_REF2, sy);
    integer(place, PRO_E_HLE_PLC_ALIGN_OPT2, y == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
    real(place, PRO_E_HLE_DIM_DIST2, y);
    integer(node(root, PRO_E_BODY), PRO_E_BODY_USE, PRO_BODY_USE_ALL);
    double before = volume();
    create(root);
    CK(ProElementFree(&root));
    ProSelectionFree(&face);
    ProSelectionFree(&sx);
    ProSelectionFree(&sy);
    expect_volume(before - acos(-1.0) * dia * dia / 4 * thickness_mm);
}
static int counts[3];
static ProError audit_cb(ProFeature *f, ProError status, ProAppData) {
    ProFeattype type;
    ProFeatStatus fs;
    ProName name = L"";
    ProFeatureTypeGet(f, &type);
    ProFeatureStatusGet(f, &fs);
    ProModelitemNameGet(f, name);
    ProBoolean incomplete = PRO_B_FALSE;
    ProFeatureIsIncomplete(f, &incomplete);
    if (incomplete) {
        log("incomplete_feature=%d\n", f->id);
        return PRO_TK_NO_ERROR;
    }
    log("feature id=%d type=%d status=%d name=%ls\n", f->id, type, fs, name);
    if ((type == PRO_FEAT_PROTRUSION || type == PRO_FEAT_FIRST_FEAT) && fs == PRO_FEAT_ACTIVE)
        counts[0]++;
    if (type == PRO_FEAT_ROUND && fs == PRO_FEAT_ACTIVE)
        counts[1]++;
    if (type == PRO_FEAT_HOLE && fs == PRO_FEAT_ACTIVE)
        counts[2]++;
    return PRO_TK_NO_ERROR;
}
