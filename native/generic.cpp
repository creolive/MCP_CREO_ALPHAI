// Composable Creo feature operations, using the installed Creo 10 Toolkit.
#include "third_party/json.hpp"
#include "callback_identity.h"
#include "recovery_deadline.h"
#include "inspection_units.h"
#include "assembly_units.h"
#include "assembly_walk.h"
#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cstdlib>
#include <memory>
#include <map>
#include <set>
#include <array>
#include <ProDtmCrv.h>
#include <ProDtmPln.h>
#include <ProDtmAxis.h>
#include <ProRevolve.h>
#include <ProChamfer.h>
#include <ProShell.h>
#include <ProPattern.h>
#include <ProDimension.h>
#include <ProSecconstr.h>
#include <ProParameter.h>
#include <ProParamval.h>
#include <ProRelSet.h>
#include <ProContour.h>
#include <ProEdge.h>
#include <ProCurvedata.h>
#include <ProIntf3dExport.h>
#include <ProPart.h>
#include <ProCollect.h>
#include <ProCrvcollection.h>
#include <ProMirror.h>
#include <ProSweep.h>
#include <ProDraft.h>
#include <ProSrfcollection.h>
#include <ProSmtFlangeWall.h>
#include <ProSmtFlatWall.h>
#include <ProRegularUnbend.h>
#include <ProSmtBendBack.h>
#include <ProAsmcomp.h>
#include <ProAsmcomppath.h>
#include <ProSheetmetal.h>
#include <ProSmtDrvSurf.h>
using J = nlohmann::json;
using V = std::array<double, 3>;
static J aliases = J::object(), gfeatures = J::array(), gsurfaces = J::array(), gedges = J::array();
static std::set<int> visited_edges;
static std::wstring generic_job;
static int temporarily_suppressed_loft = -1;
static J operation_results = J::array();
static std::string generic_phase = "loading_request";
static void generic_stage(const std::string &phase) {
    generic_phase = phase;
    log("PHASE=%s\n", phase.c_str());
}
static V vec(const J &j) {
    return {j.at(0).get<double>(), j.at(1).get<double>(), j.at(2).get<double>()};
}
static double dot(const V &a, const V &b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
static V cross(const V &a, const V &b) {
    return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
}
static V scale(const V &a, double s) {
    return {a[0] * s, a[1] * s, a[2] * s};
}
static V add(const V &a, const V &b) {
    return {a[0] + b[0], a[1] + b[1], a[2] + b[2]};
}
static V normalized(const V &a) {
    double n = sqrt(dot(a, a));
    if (n < 1e-9)
        throw std::runtime_error("Zero direction vector");
    return scale(a, 1 / n);
}
static J xyz(const double *a) {
    return J::array({a[0], a[1], a[2]});
}
static int constant(const J &value) {
    if (value.is_number_integer())
        return value.get<int>();
    auto it = tk_constants.find(value.get<std::string>());
    if (it == tk_constants.end())
        throw std::runtime_error("Unknown Toolkit constant: " + value.get<std::string>());
    return it->second;
}
// Resolve a user-supplied label to its registered alias entry. Creo
// uppercases PRO_E_STD_FEATURE_NAME, so inspect_model(features).name differs
// in case from the registered alias; both spellings must resolve to the same
// entry, and callers reading alias metadata must use this canonical lookup
// instead of indexing aliases[] with the raw string (which yields null).
static const J *alias_entry(const std::string &label) {
    auto it = aliases.find(label);
    if (it == aliases.end()) {
        std::string lower(label);
        std::transform(lower.begin(), lower.end(), lower.begin(),
                       [](unsigned char c) { return (char)std::tolower(c); });
        if (lower != label)
            it = aliases.find(lower);
    }
    return it == aliases.end() ? nullptr : &it.value();
}
static int feature_id(const J &ref) {
    if (ref.is_number_integer())
        return ref.get<int>();
    std::string label = ref.get<std::string>();
    // Some public clients stringify the integer branch of str|int anyOf
    // (BUG-073); digit-only strings cannot be feature labels, so normalize
    // them to feature IDs like the Python-side LoftOp contract does.
    if (!label.empty() && label.find_first_not_of("0123456789") == std::string::npos) {
        errno = 0;
        char *end = nullptr;
        long long id = std::strtoll(label.c_str(), &end, 10);
        if (!errno && end && !*end && id >= 0 && id <= 2147483647LL)
            return (int)id;
        throw std::runtime_error("Sketch feature ID is not a nonnegative 32-bit integer: " + label);
    }
    if (const J *entry = alias_entry(label))
        return entry->at("feature_id").get<int>();
    std::string known;
    int count = 0;
    for (auto it = aliases.begin(); it != aliases.end() && count < 10; ++it, ++count)
        known += (count ? ", " : "") + it.key();
    throw std::runtime_error(
        "Unknown feature label: " + label +
        (known.empty() ? "; this model has no registered aliases; reference features by "
                         "numeric ID from inspect_model(features)"
                       : "; available labels: " + known + (aliases.size() > 10 ? ", ..." : "")));
}
static ProFeature feature(const J &ref) {
    ProFeature f;
    CK(ProModelitemInit(board, feature_id(ref), PRO_FEATURE, &f));
    return f;
}
static std::string type_name(int t) {
    if (t == PRO_FEAT_CURVE)
        return "sketch_or_curve";
    if (t == PRO_FEAT_PROTRUSION || t == PRO_FEAT_FIRST_FEAT)
        return "protrusion";
    if (t == PRO_FEAT_CUT)
        return "cut";
    if (t == PRO_FEAT_ROUND)
        return "round";
    if (t == PRO_FEAT_CHAMFER)
        return "chamfer";
    if (t == PRO_FEAT_HOLE)
        return "hole";
    if (t == PRO_FEAT_SHELL)
        return "shell";
    if (t == PRO_FEAT_DATUM)
        return "datum_plane";
    if (t == PRO_FEAT_DATUM_AXIS)
        return "datum_axis";
    return "other";
}
static ProError dimension_cb(ProDimension *dim, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    J *list = (J *)data;
    double value;
    ProName symbol = L"";
    ProDimensiontype type;
    ProError e = ProDimensionValueGet(dim, &value);
    if (!e) {
        ProDimensionSymbolGet(dim, symbol);
        ProDimensionTypeGet(dim, &type);
        ProBoolean relation_driven = PRO_B_FALSE;
        ProError relation_code = ProDimensionIsReldriven(dim, &relation_driven);
        list->push_back(
            {{"id", dim->id},
             {"value", value},
             {"symbol", utf8(symbol)},
             {"type", (int)type},
             {"relation_query_code", relation_code},
             {"relation_driven",
              relation_code == PRO_TK_NO_ERROR ? J(relation_driven == PRO_B_TRUE) : J(nullptr)}});
    }
    return PRO_TK_NO_ERROR;
}
static ProError collect_geom_ids(ProGeomitem *item, ProError status, ProAppData data) {
    if (!status)
        ((J *)data)->push_back({{"id", item->id}, {"type", (int)item->type}});
    return PRO_TK_NO_ERROR;
}
static ProError inspect_feature(ProFeature *f, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProFeattype t;
    ProFeatStatus state;
    ProName name = L"";
    ProBoolean incomplete = PRO_B_FALSE;
    CK(ProFeatureTypeGet(f, &t));
    CK(ProFeatureStatusGet(f, &state));
    CK(ProFeatureIsIncomplete(f, &incomplete));
    ProModelitemNameGet(f, name);
    J item = {{"id", f->id},
              {"type", (int)t},
              {"type_name", type_name(t)},
              {"status", (int)state},
              {"incomplete", incomplete == PRO_B_TRUE},
              {"name", utf8(name)}};
    J dims = J::array();
    ProFeatureDimensionVisit(f, dimension_cb, nullptr, &dims);
    item["dimensions"] = dims;
    if (t == PRO_FEAT_CURVE) {
        ProSection section = nullptr;
        if (!ProFeatureSectionCopy(f, 0, &section)) {
            J sd = J::array();
            ProIntlist ids = nullptr;
            int count = 0;
            if (!ProSecdimIdsGet(section, &ids, &count)) {
                for (int i = 0; i < count; i++) {
                    double v;
                    ProSecdimType dt;
                    if (!ProSecdimValueGet(section, ids[i], &v)) {
                        ProSecdimTypeGet(section, ids[i], &dt);
                        sd.push_back({{"id", ids[i]}, {"value", v}, {"type", (int)dt}});
                    }
                }
                ProArrayFree((ProArray *)&ids);
            }
            item["sketch_dimensions"] = sd;
            ProIntlist cs = nullptr;
            int nc = 0;
            if (!ProSectionConstraintsIdsGet(section, &cs, &nc)) {
                item["sketch_constraint_count"] = nc;
                ProArrayFree((ProArray *)&cs);
            }
            ProSectionFree(&section);
        }
    }
    J geometry = J::array();
    ProFeatureGeomitemVisit(f, PRO_TYPE_UNUSED, collect_geom_ids, nullptr, &geometry);
    item["geometry_items"] = geometry;
    gfeatures.push_back(item);
    return PRO_TK_NO_ERROR;
}
static ProError inspect_edge(ProEdge edge, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    int id;
    CK(ProEdgeIdGet(edge, &id));
    if (!visited_edges.insert(id).second)
        return PRO_TK_NO_ERROR;
    J item = {{"id", id}};
    ProGeomitemdata *data = nullptr;
    ProEnttype curve_type;
    ProEdgeTypeGet(edge, &curve_type);
    item["type"] = (int)curve_type;
    if (!ProEdgeDataGet(edge, &data) && data) {
        auto c = data->data.p_curve_data;
        if (c) {
            Pro3dPnt a, b;
            if (!ProLinedataGet(c, a, b)) {
                item["start"] = xyz(a);
                item["end"] = xyz(b);
            }
        }
        ProGeomitemdataFree(&data);
    }
    ProEdge ea, eb;
    ProSurface sa, sb;
    if (!ProEdgeNeighborsGet(edge, &ea, &eb, &sa, &sb)) {
        int a, b;
        ProSurfaceIdGet(sa, &a);
        ProSurfaceIdGet(sb, &b);
        item["adjacent_surfaces"] = J::array({a, b});
    }
    gedges.push_back(item);
    return PRO_TK_NO_ERROR;
}
static ProError inspect_contour(ProContour contour, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    return ProContourEdgeVisit((ProSurface)data, contour, inspect_edge, nullptr, nullptr);
}
static ProError inspect_surface(ProSurface surface, ProError status, ProAppData body_id) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    auto p = data->data.p_surface_data;
    int id;
    CK(ProSurfaceIdGet(surface, &id));
    J item = {{"id", id}, {"body_id", (int)(intptr_t)body_id}};
    if (p) {
        item["type"] = (int)p->type;
        item["bbox"] = J::array({xyz(p->xyz_min), xyz(p->xyz_max)});
        if (p->type == PRO_SRF_PLANE) {
            item["normal"] = xyz(p->srf_shape.plane.e3);
            item["origin"] = xyz(p->srf_shape.plane.origin);
        }
        if (p->type == PRO_SRF_CYL) {
            item["radius"] = p->srf_shape.cylinder.radius;
            item["origin"] = xyz(p->srf_shape.cylinder.origin);
            item["axis"] = xyz(p->srf_shape.cylinder.e3);
        }
    }
    ProSmtSurfType st;
    if (!ProSmtSurfaceTypeGet((ProPart)board, surface, &st))
        item["sheetmetal_type"] = (int)st;
    gsurfaces.push_back(item);
    ProGeomitemdataFree(&data);
    CK(ProSurfaceContourVisit(surface, inspect_contour, nullptr, surface));
    return PRO_TK_NO_ERROR;
}
static ProError parameter_cb(ProParameter *param, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProParamvalue value;
    ProUnititem unit;
    J *params = (J *)data;
    if (!ProParameterValueWithUnitsGet(param, &value, &unit)) {
        J v;
        if (value.type == PRO_PARAM_DOUBLE)
            v = value.value.d_val;
        else if (value.type == PRO_PARAM_INTEGER)
            v = value.value.i_val;
        else if (value.type == PRO_PARAM_BOOLEAN)
            v = value.value.l_val != 0;
        else if (value.type == PRO_PARAM_STRING)
            v = utf8(value.value.s_val);
        else
            return PRO_TK_NO_ERROR;
        (*params)[utf8(param->id)] = {{"value", v}, {"type", (int)value.type}};
    }
    return PRO_TK_NO_ERROR;
}
static J assembly_inspection();
static void verify_saved(const J &before, const J &after);
static bool assembly_model() {
    ProMdlType t;
    CK(ProMdlTypeGet(board, &t));
    return t == PRO_MDL_ASSEMBLY;
}
static J inspection(bool require_healthy = true) {
    gfeatures = J::array();
    gsurfaces = J::array();
    gedges = J::array();
    visited_edges.clear();
    CK(ProSolidFeatVisit((ProSolid)board, inspect_feature, nullptr, nullptr));
    bool healthy = true;
    for (auto &f : gfeatures)
        if (f["incomplete"].get<bool>() || f["status"].get<int>() != PRO_FEAT_ACTIVE)
            healthy = false;
    if (require_healthy && !healthy) {
        bool expected_only = true;
        for (auto f : gfeatures)
            if (f["incomplete"].get<bool>() || (f["status"].get<int>() != PRO_FEAT_ACTIVE &&
                                                f["id"].get<int>() != temporarily_suppressed_loft))
                expected_only = false;
        if (!expected_only) {
            log("UNHEALTHY_FEATURES=%s\n", gfeatures.dump().c_str());
            throw std::runtime_error(
                "Regeneration produced a failed, suppressed or incomplete feature");
        }
    }
    J bodies = J::array();
    bool isasm = assembly_model(), solid = false;
    ProSolidBody *list = nullptr;
    int n = 0;
    if (!isasm) {
        CK(ProSolidBodiesCollect((ProSolid)board, &list));
        CK(ProArraySizeGet((ProArray)list, &n));
    }
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&list[i], &state));
        J b = {{"id", list[i].id}, {"state", (int)state}};
        if (state == PRO_BODY_STATE_ACTIVE) {
            size_t previous_surfaces = gsurfaces.size();
            CK(ProSolidBodySurfaceVisit(&list[i], inspect_surface,
                                        (ProAppData)(intptr_t)list[i].id));
            b["has_geometry"] = gsurfaces.size() > previous_surfaces;
            if (b["has_geometry"].get<bool>()) {
                solid = true;
                Pro3dPnt bounds[2];
                CK(ProSolidBodyOutlineGet(&list[i], bounds));
                b["bbox"] = J::array({xyz(bounds[0]), xyz(bounds[1])});
            }
        }
        bodies.push_back(b);
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    if (isasm)
        for (auto f : gfeatures)
            if (f["type"].get<int>() == PRO_FEAT_COMPONENT)
                solid = true;
    auto length_units = inspect_length_units(board);
    // Coordinates/dimensions retain model units. Do not label native in^3 as mm^3.
    J units = length_units.code || !length_units.length.name[0] ? J(nullptr)
                                                                : J(utf8(length_units.length.name));
    J result = {{"features", gfeatures},
                {"surfaces", gsurfaces},
                {"edges", gedges},
                {"bodies", bodies},
                {"healthy", healthy},
                {"units", units},
                {"units_query_code", length_units.code},
                {"has_solid", solid},
                {"volume_mm3", nullptr}};
    result["model_type"] = isasm ? "assembly" : "part";
    if (isasm)
        result["components"] = assembly_inspection();
    else {
        ProMdlsubtype subtype;
        if (!ProMdlSubtypeGet(board, &subtype) && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            result["model_type"] = "sheetmetal";
    }
    if (solid) {
        ProMassProperty mp;
        ProError e = ProSolidMassPropertyWithDensityGet((ProSolid)board, nullptr,
                                                        PRO_MP_DENS_USE_ALWAYS, 1, &mp);
        result["volume_query_code"] = e;
        if (!e) {
            auto volume = length_units.volume_mm3(mp.volume);
            if (volume)
                result["volume_mm3"] = *volume;
        }
    }
    planes.clear();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb, nullptr, nullptr));
    J ds = J::array();
    for (auto p : planes)
        ds.push_back({{"id", p.id}, {"normal", xyz(p.n)}, {"origin", xyz(p.o)}});
    result["datum_planes"] = ds;
    ProModelitem owner;
    CK(ProMdlToModelitem(board, &owner));
    J params = J::object();
    ProParameterVisit(&owner, nullptr, parameter_cb, &params);
    result["parameters"] = params;
    return result;
}
static ProSelection resolve(const J &r) {
    if (r.at("kind") == "default_csys") {
        J state = inspection(false);
        for (auto f : state["features"])
            if (f["type"].get<int>() == PRO_FEAT_CSYS)
                for (auto g : f["geometry_items"])
                    if (g["type"].get<int>() == PRO_CSYS)
                        return selection(g["id"], PRO_CSYS);
        throw std::runtime_error("No default coordinate system found");
    }
    if (r.at("kind") == "quilt_feature" || r.at("kind") == "datum_csys_feature" ||
        r.at("kind") == "datum_point_feature") {
        ProType type = r["kind"] == "quilt_feature"        ? PRO_QUILT
                       : r["kind"] == "datum_csys_feature" ? PRO_CSYS
                                                           : PRO_POINT;
        ProFeature f = feature(r.at("label"));
        J ids = J::array();
        CK(ProFeatureGeomitemVisit(&f, type, collect_geom_ids, nullptr, &ids));
        if (ids.size() != 1)
            throw std::runtime_error("Feature reference must identify exactly one geometry item");
        return selection(ids[0]["id"], type);
    }
    std::string kind = r.at("kind");
    if (kind == "part") {
        ProModelitem mi;
        CK(ProMdlToModelitem(board, &mi));
        ProSelection s;
        CK(ProSelectionAlloc(nullptr, &mi, &s));
        return s;
    }
    if (kind == "csys" || kind == "point" || kind == "quilt")
        return selection(r.at("id"), kind == "csys"    ? PRO_CSYS
                                     : kind == "point" ? PRO_POINT
                                                       : PRO_QUILT);
    if (kind == "feature")
        return selection(feature_id(r.contains("label") ? r["label"] : r["id"]), PRO_FEATURE);
    if (kind == "body") {
        int id = r.value("id", -1);
        if (id < 0) {
            ProSolidBody b;
            CK(ProSolidDefaultBodyGet((ProSolid)board, &b));
            id = b.id;
        }
        return selection(id, PRO_BODY);
    }
    if (kind == "surface" || kind == "edge" || kind == "axis" || kind == "curve" ||
        kind == "dimension") {
        int id = r.at("id");
        return selection(id, kind == "surface" ? PRO_SURFACE
                             : kind == "edge"  ? PRO_EDGE
                             : kind == "axis"  ? PRO_AXIS
                             : kind == "curve" ? PRO_CURVE
                                               : PRO_DIMENSION);
    }
    if (kind == "plane" || kind == "datum_plane") {
        J state = inspection(false);
        J candidates = kind == "datum_plane" ? state["datum_planes"] : state["surfaces"];
        V desired;
        if (r.contains("normal"))
            desired = normalized(vec(r["normal"]));
        else {
            std::string axis = r.value("axis", "z");
            desired = axis == "x" ? V{1, 0, 0} : axis == "y" ? V{0, 1, 0} : V{0, 0, 1};
        }
        double offset = r.value("offset", 0.0);
        std::vector<int> matches;
        for (auto &p : candidates) {
            if (!p.contains("normal"))
                continue;
            V normal = normalized(vec(p["normal"])), origin = vec(p["origin"]);
            if (fabs(fabs(dot(normal, desired)) - 1) < 1e-7 &&
                fabs(dot(origin, desired) - offset) < 1e-6)
                matches.push_back(p["id"].get<int>());
        }
        if (kind == "datum_plane" && fabs(offset) < 1e-9 && matches.size() > 1)
            matches = {*std::min_element(matches.begin(), matches.end())};
        if (matches.size() != 1)
            throw std::runtime_error("Plane reference must identify exactly one surface; inspect "
                                     "the model and use a surface ID");
        return selection(matches[0], PRO_SURFACE);
    }
    if (kind == "datum_axis_feature") {
        ProFeature f = feature(r.at("label"));
        J ids = J::array();
        CK(ProFeatureGeomitemVisit(&f, PRO_AXIS, collect_geom_ids, nullptr, &ids));
        if (ids.size() != 1)
            throw std::runtime_error("Datum feature must have one axis");
        return selection(ids[0]["id"], PRO_AXIS);
    }
    if (kind == "datum_feature") {
        int fid = feature_id(r.at("label"));
        ProFeature f = feature(fid);
        planes.clear();
        CK(ProFeatureGeomitemVisit(&f, PRO_SURFACE, geom_cb, nullptr, nullptr));
        if (planes.size() != 1)
            throw std::runtime_error("Datum feature does not contain one plane");
        return selection(planes[0].id, PRO_SURFACE);
    }
    throw std::runtime_error("Unknown model reference kind: " + kind);
}
static void set_refs(ProElement e, const J &refs) {
    ProReference *values = nullptr;
    CK(ProArrayAlloc((int)refs.size(), sizeof(ProReference), 1, (ProArray *)&values));
    for (size_t i = 0; i < refs.size(); i++) {
        ProSelection s = resolve(refs[i]);
        CK(ProSelectionToReference(s, &values[i]));
        ProSelectionFree(&s);
    }
    CK(ProElementReferencesSet(e, values));
    ProArrayFree((ProArray *)&values);
}
static void remember(const J &op, ProFeature f, J extra = J::object()) {
    std::string label = op.at("label");
    extra["feature_id"] = f.id;
    extra["op"] = op.at("op");
    aliases[label] = extra;
}
// Dimension and relation edits reshape sketch entities behind the recorded
// entity payloads; mark every sketch alias so a later byte-identical
// replacement cannot be mistaken for a no-op against the live section.
static void mark_sketch_geometry_stale() {
    for (auto it = aliases.begin(); it != aliases.end(); ++it)
        if (it.value().contains("entity_ids"))
            it.value()["geometry_stale"] = true;
}
static void body_options(ProElement root, const J &op) {
    std::string mode = op.value("mode", "add");
    bool new_body = op.value("new_body", false);
    ProElement b = node(root, PRO_E_BODY);
    if (mode == "cut") {
        integer(b, PRO_E_BODY_USE, PRO_BODY_USE_ALL);
        return;
    }
    J state = inspection();
    if (!state["has_solid"].get<bool>() || new_body)
        integer(b, PRO_E_BODY_USE, PRO_BODY_USE_NEW);
    else {
        integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
        ProSelection s = resolve({{"kind", "body"}});
        ref(b, PRO_E_BODY_SELECT, s);
        ProSelectionFree(&s);
    }
}
static ProFeature offset_plane(const J &reference, double offset, const std::wstring &name,
                               double *angle = nullptr, const J *axis = nullptr) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM);
    text(root, PRO_E_STD_FEATURE_NAME, name.c_str());
    ProElement constraints = node(root, PRO_E_DTMPLN_CONSTRAINTS);
    ProElement c = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
    ProSelection s = resolve(reference);
    integer(c, PRO_E_DTMPLN_CONSTR_TYPE, angle ? PRO_DTMPLN_ANG : PRO_DTMPLN_OFFS);
    ref(c, PRO_E_DTMPLN_CONSTR_REF, s);
    real(c, angle ? PRO_E_DTMPLN_CONSTR_REF_ANGLE : PRO_E_DTMPLN_CONSTR_REF_OFFSET,
         angle ? *angle : offset);
    ProSelectionFree(&s);
    if (angle) {
        if (!axis)
            throw std::runtime_error("Angled plane requires an axis");
        ProElement through = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
        integer(through, PRO_E_DTMPLN_CONSTR_TYPE, PRO_DTMPLN_THRU);
        s = resolve(*axis);
        ref(through, PRO_E_DTMPLN_CONSTR_REF, s);
        ProSelectionFree(&s);
    }
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    return f;
}
struct Frame {
    V origin, u, v, n;
    int surface, orientation;
};
static Frame sketch_frame(const J &op) {
    Frame f = {};
    J p = op.at("plane");
    if (p.is_string()) {
        std::string name = p;
        int axis = name == "XY" ? 2 : name == "XZ" ? 1 : 0;
        f.n = axis == 2 ? V{0, 0, 1} : axis == 1 ? V{0, -1, 0} : V{1, 0, 0};
        f.u = axis == 0 ? V{0, 1, 0} : V{1, 0, 0};
        f.v = cross(f.n, f.u);
        double offset = op.value("offset", 0.0);
        f.origin = axis == 2 ? V{0, 0, offset} : axis == 1 ? V{0, offset, 0} : V{offset, 0, 0};
        J reference = {{"kind", "datum_plane"},
                       {"axis", axis == 0   ? "x"
                                : axis == 1 ? "y"
                                            : "z"},
                       {"offset", 0}};
        if (fabs(offset) > 1e-9) {
            auto df =
                offset_plane(reference, offset, wide(op.at("label").get<std::string>() + "_plane"));
            planes.clear();
            CK(ProFeatureGeomitemVisit(&df, PRO_SURFACE, geom_cb, nullptr, nullptr));
            if (planes.size() != 1)
                throw PRO_TK_GENERAL_ERROR;
            f.surface = planes[0].id;
        } else {
            ProSelection s = resolve(reference);
            ProModelitem mi;
            CK(ProSelectionModelitemGet(s, &mi));
            f.surface = mi.id;
            ProSelectionFree(&s);
        }
    } else {
        ProSelection s = resolve(p.at("reference"));
        ProModelitem mi;
        CK(ProSelectionModelitemGet(s, &mi));
        f.surface = mi.id;
        ProSurface sf;
        CK(ProSurfaceInit((ProSolid)board, f.surface, &sf));
        ProGeomitemdata *d;
        CK(ProSurfaceDataGet(sf, &d));
        auto shape = d->data.p_surface_data;
        if (!shape || shape->type != PRO_SRF_PLANE)
            throw std::runtime_error("Sketch support must be planar");
        f.n = normalized({shape->srf_shape.plane.e3[0], shape->srf_shape.plane.e3[1],
                          shape->srf_shape.plane.e3[2]});
        double dist = dot(f.n, {shape->srf_shape.plane.origin[0], shape->srf_shape.plane.origin[1],
                                shape->srf_shape.plane.origin[2]});
        f.origin = p.contains("origin") ? vec(p["origin"]) : scale(f.n, dist);
        if (fabs(dot(f.n, f.origin) - dist) > 1e-6)
            throw std::runtime_error("Sketch origin is outside support plane");
        V preferred = p.contains("u_axis") ? vec(p["u_axis"])
                                           : (fabs(f.n[0]) < 0.9 ? V{1, 0, 0} : V{0, 1, 0});
        f.u = normalized(add(preferred, scale(f.n, -dot(preferred, f.n))));
        f.v = cross(f.n, f.u);
        ProGeomitemdataFree(&d);
        ProSelectionFree(&s);
    }
    double best = 10;
    f.orientation = -1;
    planes.clear();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb, nullptr, nullptr));
    for (auto p : planes) {
        V normal = {p.n[0], p.n[1], p.n[2]};
        double d = fabs(dot(f.n, normal));
        if (d < best && d < 0.95) {
            best = d;
            f.orientation = p.id;
        }
    }
    if (f.orientation < 0)
        throw std::runtime_error("No sketch orientation reference");
    return f;
}
static ProSectionPointType point_type(const std::string &s) {
    return s == "start"    ? PRO_ENT_START
           : s == "end"    ? PRO_ENT_END
           : s == "center" ? PRO_ENT_CENTER
                           : PRO_ENT_WHOLE;
}
// Constraint references need a real location on the referenced entity; the
// section origin degenerates with arcs centered there (BUG-068) and idx_pnt
// must stay unused for non-spline entities per the Toolkit contract.
static ProSelection selected(ProSection section, int id, ProSectionPointType type) {
    Pro2dEntdef *def = nullptr;
    CK(ProSectionEntityGet(section, id, &def));
    Pro2dPnt p;
    bool have = false;
    if (def->type == PRO_2D_LINE || def->type == PRO_2D_CENTER_LINE) {
        auto line = (Pro2dLinedef *)def;
        if (type == PRO_ENT_END) {
            p[0] = line->end2[0];
            p[1] = line->end2[1];
        } else if (type == PRO_ENT_START) {
            p[0] = line->end1[0];
            p[1] = line->end1[1];
        } else {
            p[0] = (line->end1[0] + line->end2[0]) / 2;
            p[1] = (line->end1[1] + line->end2[1]) / 2;
        }
        have = true;
    } else if (def->type == PRO_2D_CIRCLE) {
        auto circle = (Pro2dCircledef *)def;
        if (type == PRO_ENT_CENTER) {
            p[0] = circle->center[0];
            p[1] = circle->center[1];
        } else {
            p[0] = circle->center[0] + circle->radius;
            p[1] = circle->center[1];
        }
        have = true;
    } else if (def->type == PRO_2D_ARC) {
        auto arc = (Pro2dArcdef *)def;
        if (type == PRO_ENT_START || type == PRO_ENT_END) {
            double a = type == PRO_ENT_START ? arc->start_angle : arc->end_angle;
            p[0] = arc->center[0] + arc->radius * cos(a);
            p[1] = arc->center[1] + arc->radius * sin(a);
        } else if (type == PRO_ENT_CENTER) {
            p[0] = arc->center[0];
            p[1] = arc->center[1];
        } else {
            double a = (arc->start_angle + arc->end_angle) / 2;
            p[0] = arc->center[0] + arc->radius * cos(a);
            p[1] = arc->center[1] + arc->radius * sin(a);
        }
        have = true;
    }
    ProSelection s = nullptr;
    CK(ProSectionEntityGetSelected(section, id, type, have ? p : nullptr, PRO_VALUE_UNUSED, &s));
    return s;
}
static void redefine(ProFeature *f, ProElement root) {
    ProFeatureCreateOptions *options = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&options));
    options[0] = PRO_FEAT_CR_NO_OPTS;
    ProErrorlist es = {};
    ProError e = ProFeatureWithoptionsRedefine(nullptr, f, root, options, PRO_REGEN_NO_FLAGS, &es);
    errors(es);
    ProArrayFree((ProArray *)&options);
    check(e, "CompleteFeature");
}
#include "sketch_coordinates.cpp"
#include "sketch_solver.cpp"
static void sketch(const J &op) {
    Frame frame = sketch_frame(op);
    ProSelection plane_ref = selection(frame.surface, PRO_SURFACE),
                 orient = selection(frame.orientation, PRO_SURFACE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CURVE);
    integer(root, PRO_E_CURVE_TYPE, PRO_CURVE_TYPE_SKETCHED);
    std::wstring label = wide(op.at("label"));
    text(root, PRO_E_STD_FEATURE_NAME, label.c_str());
    ProElement setup = node(node(root, PRO_E_STD_SECTION), PRO_E_STD_SEC_SETUP_PLANE);
    ref(setup, PRO_E_STD_SEC_PLANE, plane_ref);
    integer(setup, PRO_E_STD_SEC_PLANE_VIEW_DIR, PRO_SEC_VIEW_DIR_SIDE_ONE);
    integer(setup, PRO_E_STD_SEC_PLANE_ORIENT_DIR, PRO_SEC_ORIENT_DIR_UP);
    ref(setup, PRO_E_STD_SEC_PLANE_ORIENT_REF, orient);
    ProFeature f = create(root, PRO_FEAT_CR_INCOMPLETE_FEAT);
    CK(ProElementFree(&root));
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    ProElement sk = get(root, {PRO_E_STD_SECTION, PRO_E_SKETCHER});
    ProSection section = nullptr;
    CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&section));
    int projected;
    CK(ProSectionEntityFromProjection(section, orient, &projected));
    std::vector<int> coordinate_anchors = {projected};
    planes.clear();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb, nullptr, nullptr));
    for (auto p : planes) {
        V n = {p.n[0], p.n[1], p.n[2]};
        if (p.id != frame.orientation && fabs(dot(n, frame.n)) < 0.95) {
            ProSelection s = selection(p.id, PRO_SURFACE);
            ProError e = ProSectionEntityFromProjection(section, s, &projected);
            ProSelectionFree(&s);
            log("PROJECT_REFERENCE=%d code=%d entity=%d\n", p.id, e, projected);
            if (!e) {
                coordinate_anchors.push_back(projected);
                break;
            }
        }
    }
    ProMatrix loc;
    CK(ProSectionLocationGet(section, loc));
    for (int row = 0; row < 4; row++)
        log("SECTION_MATRIX_%d=%.9f,%.9f,%.9f,%.9f\n", row, loc[row][0], loc[row][1], loc[row][2],
            loc[row][3]);
    auto project = [&](const J &p, double *out) {
        V w = add(frame.origin, add(scale(frame.u, p.at(0).get<double>()),
                                    scale(frame.v, p.at(1).get<double>())));
        for (int i = 0; i < 2; i++)
            out[i] = (w[0] - loc[3][0]) * loc[i][0] + (w[1] - loc[3][1]) * loc[i][1] +
                     (w[2] - loc[3][2]) * loc[i][2];
    };
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef cs = {};
    cs.type = PRO_2D_COORD_SYS;
    int csid;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&cs, &csid));
    std::map<std::string, int> entities;
    auto add_line = [&](const std::string &name, const J &a, const J &b, bool centerline,
                        bool construction) {
        Pro2dLinedef l = {};
        l.type = centerline ? PRO_2D_CENTER_LINE : PRO_2D_LINE;
        project(a, l.end1);
        project(b, l.end2);
        log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n", name.c_str(), l.end1[0], l.end1[1], l.end2[0],
            l.end2[1]);
        int id;
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&l, &id));
        if (!centerline)
            CK(ProSectionEntityConstructionSet(section, id,
                                               construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    };
    for (auto e : op.at("entities")) {
        std::string type = e.at("type"), name = e.at("name");
        bool construction = e.value("construction", false);
        int id = -1;
        if (type == "line" || type == "centerline") {
            add_line(name, e["start"], e["end"], type == "centerline", construction);
            continue;
        }
        if (type == "rectangle" || type == "polyline") {
            J points;
            if (type == "rectangle") {
                auto a = e["min"], b = e["max"];
                points = J::array({a, J::array({b[0], a[1]}), b, J::array({a[0], b[1]})});
            } else
                points = e["points"];
            int count = (int)points.size(),
                segments = count - 1 + ((type == "rectangle" || e.value("closed", false)) ? 1 : 0);
            for (int i = 0; i < segments; i++)
                add_line(name + "_" + std::to_string(i), points[i], points[(i + 1) % count], false,
                         construction);
            continue;
        }
        if (type == "circle") {
            Pro2dCircledef c = {};
            c.type = PRO_2D_CIRCLE;
            project(e["center"], c.center);
            c.radius = e["radius"];
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&c, &id));
        } else if (type == "arc") {
            Pro2dArcdef a = {};
            a.type = PRO_2D_ARC;
            project(e["center"], a.center);
            a.radius = e["radius"];
            double start = e["start_angle"].get<double>() * acos(-1.0) / 180,
                   end = e["end_angle"].get<double>() * acos(-1.0) / 180;
            double p[2], q[2];
            J center = e["center"];
            project(J::array({center[0].get<double>() + a.radius * cos(start),
                              center[1].get<double>() + a.radius * sin(start)}),
                    p);
            project(J::array({center[0].get<double>() + a.radius * cos(end),
                              center[1].get<double>() + a.radius * sin(end)}),
                    q);
            a.start_angle = atan2(p[1] - a.center[1], p[0] - a.center[0]);
            a.end_angle = atan2(q[1] - a.center[1], q[0] - a.center[0]);
            if (dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) < 0)
                std::swap(a.start_angle, a.end_angle);
            double turn = 2 * acos(-1.0);
            a.start_angle = fmod(a.start_angle + turn, turn);
            a.end_angle = fmod(a.end_angle + turn, turn);
            if (fabs(a.start_angle) < 1e-12)
                a.start_angle = 0;
            if (fabs(a.end_angle) < 1e-12)
                a.end_angle = 0;
            if (a.end_angle <= a.start_angle)
                a.end_angle += turn;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&a, &id));
        } else if (type == "spline") {
            auto points = e["points"];
            std::vector<std::array<double, 2>> xy(points.size());
            for (size_t i = 0; i < xy.size(); i++)
                project(points[i], xy[i].data());
            Pro2dSplinedef s = {};
            s.type = PRO_2D_SPLINE;
            s.tangency_type =
                e.value("closed", false) ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE;
            s.n_points = (unsigned)xy.size();
            s.point_arr = (Pro2dPnt *)xy.data();
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&s, &id));
        } else if (type == "ellipse") {
            Pro2dEllipsedef ell = {};
            ell.type = PRO_2D_ELLIPSE;
            project(e["center"], ell.origin);
            double align = fabs(dot(frame.u, V{loc[0][0], loc[0][1], loc[0][2]}));
            if (align > 0.99999) {
                ell.x_radius = e["x_radius"];
                ell.y_radius = e["y_radius"];
            } else if (align < 0.00001) {
                ell.x_radius = e["y_radius"];
                ell.y_radius = e["x_radius"];
            } else
                throw std::runtime_error("Ellipse axes must align with the section axes");
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&ell, &id));
        } else
            throw std::runtime_error("Unknown sketch entity type");
        CK(ProSectionEntityConstructionSet(section, id, construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    }
    if (!op.value("constraints", J::array()).empty()) {
        CK(ProSectionIntentManagerModeSet(section, PRO_B_TRUE));
        std::map<std::string, ProConstraintType> ct = {
            {"coincident", PRO_CONSTRAINT_SAME_POINT},
            {"horizontal", PRO_CONSTRAINT_HORIZONTAL_ENT},
            {"vertical", PRO_CONSTRAINT_VERTICAL_ENT},
            {"point_on", PRO_CONSTRAINT_PNT_ON_ENT},
            {"tangent", PRO_CONSTRAINT_TANGENT_ENTS},
            {"perpendicular", PRO_CONSTRAINT_ORTHOG_ENTS},
            {"equal_radius", PRO_CONSTRAINT_EQUAL_RADII},
            {"parallel", PRO_CONSTRAINT_PARALLEL_ENTS},
            {"equal_length", PRO_CONSTRAINT_EQUAL_SEGMENTS},
            {"collinear", PRO_CONSTRAINT_COLLINEAR_LINES}};
        for (auto c : op["constraints"]) {
            std::vector<ProSelection> refs;
            for (auto r : c["refs"]) {
                ProSelection s = selected(section, entities.at(r["entity"].get<std::string>()),
                                          point_type(r.value("point", "whole")));
                refs.push_back(s);
            }
            int cid;
            ProError err = ProSectionConstraintCreate(section, refs.data(), (int)refs.size(),
                                                      ct.at(c["type"]), &cid);
            for (auto s : refs)
                ProSelectionFree(&s);
            if (err != PRO_TK_E_FOUND)
                check(err, "CreateSketchConstraint");
        }
        CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    }
    std::map<std::string, ProSecdimType> dt = {{"length", PRO_TK_DIM_LINE},
                                               {"radius", PRO_TK_DIM_RAD},
                                               {"diameter", PRO_TK_DIM_DIA},
                                               {"distance", PRO_TK_DIM_PNT_PNT},
                                               {"horizontal", PRO_TK_DIM_PNT_PNT_HORIZ},
                                               {"vertical", PRO_TK_DIM_PNT_PNT_VERT},
                                               {"line_distance", PRO_TK_DIM_LINE_LINE},
                                               {"angle", PRO_TK_DIM_LINES_ANGLE},
                                               {"arc_angle", PRO_TK_DIM_ARC_ANGLE},
                                               {"ellipse_x_radius", PRO_TK_DIM_ELLIPSE_X_RADIUS},
                                               {"ellipse_y_radius", PRO_TK_DIM_ELLIPSE_Y_RADIUS}};
    J dims = J::object();
    J coordinate_plan;
    J solving_op = op;
    solving_op["dimensioning"] = profile_dimensioning(op);
    if (solving_op["dimensioning"] == "coordinates") {
        if (!op.value("dimensions", J::array()).empty() ||
            !op.value("constraints", J::array()).empty())
            throw std::runtime_error(
                "Coordinate dimensioning cannot be combined with supplied dimensions/constraints");
        double aligned = fabs(dot(frame.u, V{loc[0][0], loc[0][1], loc[0][2]}));
        if (aligned > 0.99999)
            coordinate_plan =
                coordinate_dimensions(section, csid, entities, {0, 1}, coordinate_anchors);
        else if (aligned < 0.00001)
            coordinate_plan =
                coordinate_dimensions(section, csid, entities, {1, 0}, coordinate_anchors);
        else
            throw std::runtime_error("Coordinate dimensioning requires principal section axes");
        dims = coordinate_plan["dimension_ids"];
    }
    for (auto d : op.value("dimensions", J::array())) {
        std::vector<int> ids;
        std::vector<ProSectionPointType> senses;
        for (auto r : d["refs"]) {
            ids.push_back(entities.at(r["entity"].get<std::string>()));
            senses.push_back(point_type(r.value("point", "whole")));
        }
        double place[2];
        project(d["position"], place);
        int id;
        CK(ProSecdimCreate(section, ids.data(), senses.data(), (int)ids.size(), dt.at(d["type"]),
                           place, &id));
        CK(ProSecdimValueSet(section, id, d["value"]));
        dims[d["name"].get<std::string>()] = id;
    }
    J solver_info = solve_profile(section, solving_op);
    solver_info["requested"] = op.value("dimensioning", "auto");
    if (!coordinate_plan.is_null())
        solver_info["coordinate_geometry"] = verify_coordinate_plan(
            section, coordinate_plan["targets"], coordinate_plan["origin_id"]);
    CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    ProSelectionFree(&plane_ref);
    ProSelectionFree(&orient);
    if (!coordinate_plan.is_null()) {
        ProSection saved = nullptr;
        CK(ProFeatureSectionCopy(&f, 0, &saved));
        try {
            solver_info["coordinate_geometry_after_creation"] = verify_coordinate_plan(
                saved, coordinate_plan["targets"], coordinate_plan["origin_id"]);
        } catch (...) {
            ProSectionFree(&saved);
            throw;
        }
        CK(ProSectionFree(&saved));
    }
    J ids = J::object();
    for (auto item : entities)
        ids[item.first] = item.second;
    remember(
        op, f,
        {{"entity_ids", ids},
         {"dimension_ids", dims},
         {"solver", solver_info},
         {"geometry", op["entities"]},
         {"geometry_stale", false},
         {"last_dimensioning", op.value("dimensioning", "auto")},
         {"normal", frame.n},
         {"origin", frame.origin},
         {"u_axis", frame.u},
         {"v_axis", frame.v},
         {"section_normal_sign", dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) > 0 ? 1 : -1}});
    if (op.contains("profile"))
        aliases[op["label"].get<std::string>()]["airfoil"] = op["profile"];
}
// ProFeatureWithoptionsCreate reports an invalid section only as a bare code;
// Toolkit validation stays authoritative, so explain the likely causes here
// instead of duplicating the check.
static std::string section_create_failure(const J &op, bool revolve, ProError error) {
    std::string m = revolve ? "Revolve" : "Extrude";
    m += " feature creation failed (ProFeatureWithoptionsCreate=" + std::to_string(error) + ")";
    if (revolve) {
        m += ". The closed profile must lie entirely on one side of the revolve axis and must "
             "not cross it; entities may touch the axis. The sketch must contain a centerline, "
             "or an explicit axis must be supplied, and the profile must be closed.";
    } else {
        m += ". The profile must form a valid closed section.";
    }
    if (op["sketch"].is_string())
        m += " Sketch: '" + op["sketch"].get<std::string>() + "'.";
    if (!last_feature_errors.empty())
        m += " Element errors: " + last_feature_errors + ".";
    return m;
}
static J extrude_or_revolve(const J &op, bool revolve) {
    ProFeature sketch_f = feature(op.at("sketch"));
    bool cut = op.value("mode", "add") == "cut";
    double before_volume = cut ? volume() : 0.0;
    ProSelection s = selection(sketch_f.id, PRO_FEATURE);
    std::string mode = op.value("mode", "add"), direction = op.value("direction", "positive");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE,
            mode == "cut"       ? PRO_FEAT_CUT
            : mode == "surface" ? PRO_FEAT_DATUM_SURF
                                : PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, revolve ? PRO_REVOLVE : PRO_EXTRUDE);
    integer(root, PRO_E_EXT_SURF_CUT_SOLID_TYPE,
            mode == "surface" ? PRO_EXT_FEAT_TYPE_SURFACE : PRO_EXT_FEAT_TYPE_SOLID);
    integer(root, PRO_E_REMOVE_MATERIAL,
            mode == "cut" ? PRO_EXT_MATERIAL_REMOVE : PRO_EXT_MATERIAL_ADD);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    if (mode != "surface")
        body_options(root, op);
    int sign = 1;
    if (op["sketch"].is_string()) {
        if (const J *entry = alias_entry(op["sketch"].get<std::string>()))
            sign = entry->value("section_normal_sign", 1);
    }
    if (direction == "negative")
        sign = -sign;
    log("DIRECTION_SIGN=%d\n", sign);
    integer(root, PRO_E_STD_DIRECTION, sign > 0 ? 1 : -1);
    if (op.contains("thin")) {
        integer(root, PRO_E_FEAT_FORM_IS_THIN,
                revolve ? PRO_REV_FEAT_FORM_THIN : PRO_EXT_FEAT_FORM_THIN);
        real(root, PRO_E_THICKNESS, op["thin"]);
        integer(root, PRO_E_STD_MATRLSIDE,
                revolve ? PRO_REV_MATERIAL_BOTH_SIDES : PRO_EXT_MATERIAL_BOTH_SIDES);
    }
    if (revolve) {
        if (op.contains("axis")) {
            integer(root, PRO_E_REVOLVE_AXIS_OPT, PRO_REV_AXIS_EXT_REF);
            ProSelection a = resolve(op["axis"]);
            ref(root, PRO_E_REVOLVE_AXIS, a);
            ProSelectionFree(&a);
        } else
            integer(root, PRO_E_REVOLVE_AXIS_OPT, PRO_REV_AXIS_INT_REF);
        ProElement angles = node(root, PRO_E_REV_ANGLE), from = node(angles, PRO_E_REV_ANGLE_FROM),
                   to = node(angles, PRO_E_REV_ANGLE_TO);
        integer(from, PRO_E_REV_ANGLE_FROM_TYPE, PRO_REV_ANG_FROM_NONE);
        integer(to, PRO_E_REV_ANGLE_TO_TYPE,
                direction == "symmetric" ? PRO_REV_ANG_SYMMETRIC : PRO_REV_ANG_TO_ANGLE);
        real(to, PRO_E_REV_ANGLE_TO_VAL, op.value("angle", 360.0));
    } else {
        ProElement dep = node(root, PRO_E_STD_EXT_DEPTH), from = node(dep, PRO_E_EXT_DEPTH_FROM),
                   to = node(dep, PRO_E_EXT_DEPTH_TO);
        integer(from, PRO_E_EXT_DEPTH_FROM_TYPE, PRO_EXT_DEPTH_FROM_NONE);
        integer(to, PRO_E_EXT_DEPTH_TO_TYPE,
                op.value("depth_type", "blind") == "through_all" ? PRO_EXT_DEPTH_TO_ALL
                : direction == "symmetric"                       ? PRO_EXT_DEPTH_SYMMETRIC
                                                                 : PRO_EXT_DEPTH_TO_BLIND);
        if (op.value("depth_type", "blind") != "through_all")
            real(to, PRO_E_EXT_DEPTH_TO_VALUE, op.at("depth"));
    }
    ProFeature f = {};
    try {
        f = create(root);
    } catch (ProError error) {
        ProElementFree(&root);
        if (last_toolkit_error != "ProFeatureWithoptionsCreate")
            throw;
        throw std::runtime_error(section_create_failure(op, revolve, error));
    }
    CK(ProElementFree(&root));
    remember(op, f);
    J details = J::object();
    if (cut) {
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        double removed = before_volume - volume();
        log("CUT_MATERIAL_REMOVED_MM3=%.12f\n", removed);
        if (removed <= std::max(1e-9, fabs(before_volume) * 1e-12))
            throw std::runtime_error(
                std::string(revolve ? "Revolve" : "Extrude") +
                " cut removes no material; check the sketch position, direction and depth "
                "against existing geometry");
        details["material_removed_mm3"] = removed;
    }
    J state = inspection();
    int active = 0;
    for (auto b : state["bodies"])
        if (b["state"].get<int>() == PRO_BODY_STATE_ACTIVE)
            active++;
    if (active == 1 && !op.value("skip_empty_body_cleanup", false))
        remove_empty_body();
    return details;
}
static bool hole_plane_normal(ProSelection selection, V &normal, const char *role) {
    ProModelitem item;
    CK(ProSelectionModelitemGet(selection, &item));
    if (item.type != PRO_SURFACE)
        return false; // Edge/axis references retain Toolkit's own validation.
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, item.id, &surface));
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    bool planar =
        data && data->data.p_surface_data && data->data.p_surface_data->type == PRO_SRF_PLANE;
    if (planar) {
        const auto &plane = data->data.p_surface_data->srf_shape.plane;
        normal = {plane.e3[0], plane.e3[1], plane.e3[2]};
    }
    if (data)
        CK(ProGeomitemdataFree(&data));
    if (!planar)
        throw std::runtime_error(std::string("Linear hole ") + role +
                                 " must be planar; use a plane/straight edge reference");
    normal = normalized(normal);
    return true;
}
static void validate_hole_planes(ProSelection face, ProSelection first, ProSelection second) {
    V primary, normals[2];
    if (!hole_plane_normal(face, primary, "placement"))
        throw std::runtime_error("Linear hole placement must be a planar surface or datum plane");
    bool planar[2] = {hole_plane_normal(first, normals[0], "reference1"),
                      hole_plane_normal(second, normals[1], "reference2")};
    ProSelection references[] = {first, second};
    for (int i = 0; i < 2; ++i) {
        ProModelitem item;
        CK(ProSelectionModelitemGet(references[i], &item));
        if (item.type == PRO_EDGE) {
            ProEdge edge;
            CK(ProEdgeInit((ProSolid)board, item.id, &edge));
            ProGeomitemdata *data = nullptr;
            CK(ProEdgeDataGet(edge, &data));
            Pro3dPnt start, end;
            ProError line = ProLinedataGet(data->data.p_curve_data, start, end);
            CK(ProGeomitemdataFree(&data));
            if (line)
                throw std::runtime_error("Linear hole requires straight edge references");
            V direction = normalized(add(vec(xyz(end)), scale(vec(xyz(start)), -1)));
            if (fabs(dot(primary, direction)) > 1e-7)
                throw std::runtime_error("Hole edge references must lie in the placement plane");
            normals[i] = normalized(cross(primary, direction));
            planar[i] = true;
        }
        if (!planar[i])
            continue;
        V projected = add(normals[i], scale(primary, -dot(primary, normals[i])));
        if (dot(projected, projected) < 1e-14)
            throw std::runtime_error(
                "Hole reference" + std::to_string(i + 1) +
                " is parallel to placement; choose a plane crossing the placement plane");
        normals[i] = normalized(projected);
    }
    if (planar[0] && planar[1] && fabs(dot(normals[0], normals[1])) > 1 - 1e-7)
        throw std::runtime_error(
            "Hole secondary references do not provide independent location constraints");
}
static void seed_hole_edge_selections(ProSelection &face, ProSelection &first,
                                      ProSelection &second) {
    ProModelitem refs[2];
    CK(ProSelectionModelitemGet(first, &refs[0]));
    CK(ProSelectionModelitemGet(second, &refs[1]));
    if (refs[0].type != PRO_EDGE && refs[1].type != PRO_EDGE)
        return;
    ProModelitem primary;
    CK(ProSelectionModelitemGet(face, &primary));
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, primary.id, &surface));
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    V origin = vec(xyz(data->data.p_surface_data->srf_shape.plane.origin));
    V normal = normalized(vec(xyz(data->data.p_surface_data->srf_shape.plane.e3)));
    ProPoint3d pick;
    for (int i = 0; i < 3; ++i)
        pick[i] =
            (data->data.p_surface_data->xyz_min[i] + data->data.p_surface_data->xyz_max[i]) / 2;
    CK(ProGeomitemdataFree(&data));
    CK(ProSelectionPoint3dSet(pick, &face));
    ProUvParam uv;
    CK(ProSurfaceParamEval((ProSolid)board, surface, pick, uv));
    CK(ProSelectionUvParamSet(face, uv));
    // Creo uses the selected points to choose the signed side of edge-derived planes.
    // An ID-only selection can choose an outward side on an identical later request.
    log("HOLE_PLACEMENT_PICK=%.9f,%.9f,%.9f\n", pick[0], pick[1], pick[2]);
    ProSelection *selections[] = {&first, &second};
    for (int i = 0; i < 2; ++i) {
        if (refs[i].type != PRO_EDGE)
            continue;
        ProEdge edge;
        CK(ProEdgeInit((ProSolid)board, refs[i].id, &edge));
        ProVector derivative, second_derivative, direction;
        CK(ProEdgeXyzdataEval(edge, 0.5, pick, derivative, second_derivative, direction));
        if (fabs(dot(add(vec(xyz(pick)), scale(origin, -1)), normal)) > 1e-6)
            throw std::runtime_error("Hole edge references must lie in the placement plane");
        CK(ProSelectionPoint3dSet(pick, selections[i]));
    }
}
static J generic_hole(const J &op) {
    double before_volume = volume();
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_HOLE);
    integer(root, PRO_E_FEATURE_FORM, PRO_HLE_TYPE_STRAIGHT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement com = node(root, PRO_E_HLE_COM);
    integer(com, PRO_E_HLE_TYPE_NEW, PRO_HLE_NEW_TYPE_STRAIGHT);
    integer(com, PRO_E_HLE_MAKE_LIGHTWT, PRO_HLE_REGULAR);
    real(com, PRO_E_DIAMETER, op.at("diameter"));
    ProElement dep = node(com, PRO_E_HOLE_STD_DEPTH);
    ProElement to = node(dep, PRO_E_HOLE_DEPTH_TO);
    integer(to, PRO_E_HOLE_DEPTH_TO_TYPE,
            op.contains("depth") ? PRO_HLE_STRGHT_BLIND_DEPTH : PRO_HLE_STRGHT_THRU_ALL_DEPTH);
    if (op.contains("depth"))
        real(to, PRO_E_EXT_DEPTH_TO_VALUE, op.at("depth"));
    integer(node(dep, PRO_E_HOLE_DEPTH_FROM), PRO_E_HOLE_DEPTH_FROM_TYPE,
            PRO_HLE_STRGHT_NONE_DEPTH);
    integer(com, PRO_E_HLE_CRDIR_FLIP,
            op.value("flip", false) ? PRO_HLE_CR_IN_SIDE_TWO : PRO_HLE_CR_IN_SIDE_ONE);
    integer(com, PRO_E_HLE_TOP_CLEARANCE, PRO_HOLE_GEN_CLRNCE);
#if defined(MECHDOG_HAS_PRO_E_HLE_ADD_PARAMETERS) &&                                               \
    defined(MECHDOG_HAS_PRO_HOLE_NO_PARAMETERS_FLAG)
    integer(com, PRO_E_HLE_ADD_PARAMETERS, PRO_HOLE_NO_PARAMETERS_FLAG);
#endif
    integer(com, PRO_E_HLE_ADD_NOTE, PRO_HOLE_NO_NOTE_FLAG);
    ProElement placement = node(root, PRO_E_HLE_PLACEMENT);
    ProSelection face = nullptr, r1 = nullptr, r2 = nullptr;
    try {
        face = resolve(op["placement"]);
        r1 = resolve(op["reference1"]);
        r2 = resolve(op["reference2"]);
        validate_hole_planes(face, r1, r2);
        seed_hole_edge_selections(face, r1, r2);
        ref(placement, PRO_E_HLE_PRIM_REF, face);
        integer(placement, PRO_E_HLE_PL_TYPE, PRO_HLE_PL_TYPE_LIN);
        ref(placement, PRO_E_HLE_DIM_REF1, r1);
        ref(placement, PRO_E_HLE_DIM_REF2, r2);
        double a = op.value("offset1", 0.0), b = op.value("offset2", 0.0);
        integer(placement, PRO_E_HLE_PLC_ALIGN_OPT1,
                a == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
        integer(placement, PRO_E_HLE_PLC_ALIGN_OPT2,
                b == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
        real(placement, PRO_E_HLE_DIM_DIST1, a);
        real(placement, PRO_E_HLE_DIM_DIST2, b);
        integer(node(root, PRO_E_BODY), PRO_E_BODY_USE, PRO_BODY_USE_ALL);
        ProFeature f = create(root);
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        double removed = before_volume - volume();
        log("HOLE_MATERIAL_REMOVED_MM3=%.12f\n", removed);
        if (removed <= std::max(1e-9, fabs(before_volume) * 1e-12))
            throw std::runtime_error("Hole removes no material; check reference offsets, "
                                     "placement, flip and overlap with existing holes");
        J axes = J::array();
        J geometry = J::array();
        CK(ProFeatureGeomitemVisit(&f, PRO_AXIS, collect_geom_ids, nullptr, &axes));
        for (const auto &axis : axes) {
            ProGeomitem item;
            CK(ProModelitemInit(board, axis["id"], PRO_AXIS, &item));
            ProGeomitemdata *data = nullptr;
            CK(ProGeomitemdataGet(&item, &data));
            Pro3dPnt start, end;
            CK(ProLinedataGet(data->data.p_curve_data, start, end));
            log("HOLE_AXIS id=%d start=%.9f,%.9f,%.9f end=%.9f,%.9f,%.9f\n", axis["id"].get<int>(),
                start[0], start[1], start[2], end[0], end[1], end[2]);
            geometry.push_back({{"id", axis["id"]}, {"start", xyz(start)}, {"end", xyz(end)}});
            CK(ProGeomitemdataFree(&data));
        }
        CK(ProElementFree(&root));
        ProSelectionFree(&face);
        ProSelectionFree(&r1);
        ProSelectionFree(&r2);
        remember(op, f);
        return {{"feature_id", f.id}, {"material_removed_mm3", removed}, {"axes", geometry}};
    } catch (...) {
        if (face)
            ProSelectionFree(&face);
        if (r1)
            ProSelectionFree(&r1);
        if (r2)
            ProSelectionFree(&r2);
        if (root)
            ProElementFree(&root);
        throw;
    }
}
static void curve_collection(ProElement element, const J &refs) {
    ProCollection coll;
    CK(ProCrvcollectionAlloc(&coll));
    for (auto item : refs) {
        ProSelection s = resolve(item);
        ProReference reference;
        CK(ProSelectionToReference(s, &reference));
        ProCrvcollinstr instr;
        CK(ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_ONE_INSTR, &instr));
        CK(ProCrvcollinstrReferenceAdd(instr, reference));
        CK(ProCrvcollectionInstructionAdd(coll, instr));
        CK(ProCrvcollinstrFree(instr));
        ProSelectionFree(&s);
    }
    CK(ProElementCollectionSet(element, coll));
    CK(ProCollectionFree(&coll));
}
static J generic_round(const J &op, bool chamfer) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, chamfer ? PRO_FEAT_CHAMFER : PRO_FEAT_ROUND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement sets = node(root, PRO_E_RNDCH_SETS);
    for (auto refs : op["references"]) {
        ProElement set = node(sets, PRO_E_RNDCH_SET);
        if (chamfer) {
            integer(set, PRO_E_RNDCH_DIMENSIONAL_SCHEMA, PRO_CHM_D_X_D);
            integer(set, PRO_E_RNDCH_CHAMFER_SHAPE, PRO_CHM_TANGENT_LEGS);
        } else {
            integer(set, PRO_E_RNDCH_SHAPE_OPTIONS, PRO_ROUND_TYPE_CONSTANT);
            integer(node(set, PRO_E_RNDCH_COMPOUND_CONIC), PRO_E_RNDCH_CONIC_TYPE,
                    PRO_ROUND_CONIC_DISABLE);
            integer(node(set, PRO_E_RNDCH_COMPOUND_SPINE), PRO_E_RNDCH_BALL_SPINE,
                    PRO_ROUND_ROLLING_BALL);
        }
        ProElement r = node(set, PRO_E_RNDCH_REFERENCES);
        if (refs.contains("surfaces")) {
            integer(r, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_SURF_SURF);
            ProSelection a = resolve(refs["surfaces"][0]), b = resolve(refs["surfaces"][1]);
            ref(r, PRO_E_RNDCH_REFERENCE_SURFACE1, a);
            ref(r, PRO_E_RNDCH_REFERENCE_SURFACE2, b);
            ProSelectionFree(&a);
            ProSelectionFree(&b);
        } else {
            integer(r, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_EDGE);
            ProSelection e = resolve(refs.at("edge"));
            ProSelectionFree(&e);
            curve_collection(node(r, PRO_E_STD_CURVE_COLLECTION_APPL), J::array({refs.at("edge")}));
        }
        ProElement radius = node(node(set, PRO_E_RNDCH_RADII), PRO_E_RNDCH_RADIUS),
                   leg = node(radius, PRO_E_RNDCH_LEG1);
        integer(leg, PRO_E_RNDCH_LEG_TYPE, PRO_ROUND_RADIUS_TYPE_VALUE);
        real(leg, PRO_E_RNDCH_LEG_VALUE, op.at("size"));
    }
    integer(root, PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED);
    node(root, PRO_E_RNDCH_TRANSITIONS);
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    remember(op, f);
    // Echo the applied leg value so callers can compare it with their input.
    return {{"size", op.at("size")}};
}
static void generic_shell(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_SHELL);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement b = node(root, PRO_E_BODY);
    integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
    ProSelection body = resolve({{"kind", "body"}});
    ref(b, PRO_E_BODY_SELECT, body);
    ProSelectionFree(&body);
    real(root, PRO_E_SHELL_THICK, op.at("thickness"));
    integer(root, PRO_E_SHELL_FLIP,
            op.value("outward", false) ? PRO_SHELL_OUTSIDE : PRO_SHELL_INSIDE);
    if (!op["remove_surfaces"].empty())
        set_refs(node(root, PRO_E_SHELL_SRF), op["remove_surfaces"]);
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    remember(op, f);
}
static ProElement tree_from_json(const J &spec, ProElement parent = nullptr, int depth = 0) {
    if (depth > 40)
        throw std::runtime_error("Element tree is too deep");
    ProElement e = node(parent, constant(spec.at("id")));
    if (spec.contains("integer"))
        CK(ProElementIntegerSet(e, constant(spec["integer"])));
    if (spec.contains("double")) {
        CK(ProElementDecimalsSet(e, 8));
        CK(ProElementDoubleSet(e, spec["double"]));
    }
    if (spec.contains("string"))
        CK(ProElementWstringSet(e, const_cast<wchar_t *>(wide(spec["string"]).c_str())));
    if (spec.contains("reference")) {
        ProSelection s = resolve(spec["reference"]);
        ProReference r;
        CK(ProSelectionToReference(s, &r));
        CK(ProElementReferenceSet(e, r));
        ProSelectionFree(&s);
    }
    if (spec.contains("references"))
        set_refs(e, spec["references"]);
    if (spec.contains("curve_collection"))
        curve_collection(e, spec["curve_collection"]);
    for (auto child : spec.value("children", J::array()))
        tree_from_json(child, e, depth + 1);
    return e;
}
static void parameters(const J &op) {
    ProModelitem owner;
    CK(ProMdlToModelitem(board, &owner));
    for (auto it = op["values"].begin(); it != op["values"].end(); ++it) {
        ProName name;
        wcscpy_s(name, wide(it.key()).c_str());
        ProParamvalue v = {};
        J value = it.value();
        if (value.is_boolean()) {
            v.type = PRO_PARAM_BOOLEAN;
            v.value.l_val = value.get<bool>() ? 1 : 0;
        } else if (value.is_number_integer()) {
            v.type = PRO_PARAM_INTEGER;
            v.value.i_val = value.get<int>();
        } else if (value.is_number()) {
            v.type = PRO_PARAM_DOUBLE;
            v.value.d_val = value.get<double>();
        } else {
            v.type = PRO_PARAM_STRING;
            wcscpy_s(v.value.s_val, wide(value).c_str());
        }
        ProParameter param;
        ProError e = ProParameterInit(&owner, name, &param);
        if (e == PRO_TK_E_NOT_FOUND)
            CK(ProParameterWithUnitsCreate(&owner, name, &v, nullptr, &param));
        else {
            check(e, "FindParameter");
            CK(ProParameterValueWithUnitsSet(&param, &v, nullptr));
        }
    }
}
static void write_stl(const std::wstring &file) {
    ProSurfaceTessellationData *surfaces = nullptr;
    CK(ProPartTessellate((ProPart)board, 0.05, 0.1, PRO_B_FALSE, &surfaces));
    int n;
    CK(ProArraySizeGet((ProArray)surfaces, &n));
    std::ofstream out(file);
    if (!out)
        throw std::runtime_error("Cannot open STL output");
    out.precision(12);
    out << "solid creo_native\n";
    int count = 0;
    for (int i = 0; i < n; i++) {
        auto s = surfaces[i];
        for (int j = 0; j < s.n_facets; j++) {
            auto indices = s.facets[j];
            V a = {s.vertices[indices[0]][0], s.vertices[indices[0]][1], s.vertices[indices[0]][2]},
              b = {s.vertices[indices[1]][0], s.vertices[indices[1]][1], s.vertices[indices[1]][2]},
              c = {s.vertices[indices[2]][0], s.vertices[indices[2]][1], s.vertices[indices[2]][2]};
            V normal = normalized(cross(add(b, scale(a, -1)), add(c, scale(a, -1))));
            out << "facet normal " << normal[0] << ' ' << normal[1] << ' ' << normal[2]
                << "\n outer loop\n";
            for (auto v : {a, b, c})
                out << " vertex " << v[0] << ' ' << v[1] << ' ' << v[2] << '\n';
            out << " endloop\nendfacet\n";
            count++;
        }
    }
    out << "endsolid creo_native\n";
    out.close();
    CK(ProPartTessellationFree(&surfaces));
    if (!count)
        throw std::runtime_error("No solid facets to export");
}
static void generic_pattern(const J &op) {
    ProFeature leader = feature(op["feature"]);
    ProElement root = node(nullptr, PRO_E_PATTERN_ROOT);
    integer(root, PRO_E_GENPAT_TYPE, PRO_GENPAT_DIM_DRIVEN);
    integer(root, PRO_E_GENPAT_REGEN_METHOD, PRO_PAT_GENERAL);
    ProElement dims = node(root, PRO_E_GENPAT_DIM), dir = node(dims, PRO_E_GENPAT_DIM_FIRST_DIR),
               item = node(dir, PRO_E_GENPAT_DIM_DIR_COMPOUND);
    ProSelection d = resolve({{"kind", "dimension"}, {"id", op["dimension_id"]}});
    ref(item, PRO_E_GENPAT_DIR_DIMENSION, d);
    ProSelectionFree(&d);
    integer(item, PRO_E_GENPAT_DIR_VAR_TYPE, PRO_PAT_VALUE_DRIVEN);
    real(item, PRO_E_GENPAT_DIR_VAR_VALUE, op["increment"]);
    integer(dims, PRO_E_GENPAT_DIM_FIRST_DIR_NUM_INST, op["count"]);
    CK(ProPatternCreate(&leader, PRO_FEAT_PATTERN, root));
    CK(ProElementFree(&root));
    ProPattern pat;
    ProFeature head;
    CK(ProFeaturePatternGet(&leader, PRO_FEAT_PATTERN, &pat));
    CK(ProPatternHeaderGet(&pat, &head));
    ProName name;
    wcscpy_s(name, wide(op["label"]).c_str());
    CK(ProModelitemNameSet(&head, name));
    remember(op, head, {{"leader_id", leader.id}});
}
static J populate_profile(ProSection section, const J &op) {
    J entities_spec = op.at("profile");
    Frame frame = {};
    frame.n = {0, 0, 1};
    frame.u = {1, 0, 0};
    ProMatrix loc = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, 1}};
    auto project = [](const J &p, double *out) {
        out[0] = p.at(0).get<double>();
        out[1] = p.at(1).get<double>();
    };
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef cs = {};
    cs.type = PRO_2D_COORD_SYS;
    int csid;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&cs, &csid));
    std::map<std::string, int> entities;
    auto add_line = [&](const std::string &name, const J &a, const J &b, bool centerline,
                        bool construction) {
        Pro2dLinedef l = {};
        l.type = centerline ? PRO_2D_CENTER_LINE : PRO_2D_LINE;
        project(a, l.end1);
        project(b, l.end2);
        log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n", name.c_str(), l.end1[0], l.end1[1], l.end2[0],
            l.end2[1]);
        int id;
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&l, &id));
        if (!centerline)
            CK(ProSectionEntityConstructionSet(section, id,
                                               construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    };
    for (auto e : entities_spec) {
        std::string type = e.at("type"), name = e.at("name");
        bool construction = e.value("construction", false);
        int id = -1;
        if (type == "line" || type == "centerline") {
            add_line(name, e["start"], e["end"], type == "centerline", construction);
            continue;
        }
        if (type == "rectangle" || type == "polyline") {
            J points;
            if (type == "rectangle") {
                auto a = e["min"], b = e["max"];
                points = J::array({a, J::array({b[0], a[1]}), b, J::array({a[0], b[1]})});
            } else
                points = e["points"];
            int count = (int)points.size(),
                segments = count - 1 + ((type == "rectangle" || e.value("closed", false)) ? 1 : 0);
            for (int i = 0; i < segments; i++)
                add_line(name + "_" + std::to_string(i), points[i], points[(i + 1) % count], false,
                         construction);
            continue;
        }
        if (type == "circle") {
            Pro2dCircledef c = {};
            c.type = PRO_2D_CIRCLE;
            project(e["center"], c.center);
            c.radius = e["radius"];
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&c, &id));
        } else if (type == "arc") {
            Pro2dArcdef a = {};
            a.type = PRO_2D_ARC;
            project(e["center"], a.center);
            a.radius = e["radius"];
            double start = e["start_angle"].get<double>() * acos(-1.0) / 180,
                   end = e["end_angle"].get<double>() * acos(-1.0) / 180;
            double p[2], q[2];
            J center = e["center"];
            project(J::array({center[0].get<double>() + a.radius * cos(start),
                              center[1].get<double>() + a.radius * sin(start)}),
                    p);
            project(J::array({center[0].get<double>() + a.radius * cos(end),
                              center[1].get<double>() + a.radius * sin(end)}),
                    q);
            a.start_angle = atan2(p[1] - a.center[1], p[0] - a.center[0]);
            a.end_angle = atan2(q[1] - a.center[1], q[0] - a.center[0]);
            if (dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) < 0)
                std::swap(a.start_angle, a.end_angle);
            double turn = 2 * acos(-1.0);
            a.start_angle = fmod(a.start_angle + turn, turn);
            a.end_angle = fmod(a.end_angle + turn, turn);
            if (fabs(a.start_angle) < 1e-12)
                a.start_angle = 0;
            if (fabs(a.end_angle) < 1e-12)
                a.end_angle = 0;
            if (a.end_angle <= a.start_angle)
                a.end_angle += turn;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&a, &id));
        } else if (type == "spline") {
            auto points = e["points"];
            std::vector<std::array<double, 2>> xy(points.size());
            for (size_t i = 0; i < xy.size(); i++)
                project(points[i], xy[i].data());
            Pro2dSplinedef s = {};
            s.type = PRO_2D_SPLINE;
            s.tangency_type =
                e.value("closed", false) ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE;
            s.n_points = (unsigned)xy.size();
            s.point_arr = (Pro2dPnt *)xy.data();
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&s, &id));
        } else if (type == "ellipse") {
            Pro2dEllipsedef ell = {};
            ell.type = PRO_2D_ELLIPSE;
            project(e["center"], ell.origin);
            double align = fabs(dot(frame.u, V{loc[0][0], loc[0][1], loc[0][2]}));
            if (align > 0.99999) {
                ell.x_radius = e["x_radius"];
                ell.y_radius = e["y_radius"];
            } else if (align < 0.00001) {
                ell.x_radius = e["y_radius"];
                ell.y_radius = e["x_radius"];
            } else
                throw std::runtime_error("Ellipse axes must align with the section axes");
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&ell, &id));
        } else
            throw std::runtime_error("Unknown sketch entity type");
        CK(ProSectionEntityConstructionSet(section, id, construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    }
    if (!op.value("constraints", J::array()).empty()) {
        CK(ProSectionIntentManagerModeSet(section, PRO_B_TRUE));
        std::map<std::string, ProConstraintType> ct = {
            {"coincident", PRO_CONSTRAINT_SAME_POINT},
            {"horizontal", PRO_CONSTRAINT_HORIZONTAL_ENT},
            {"vertical", PRO_CONSTRAINT_VERTICAL_ENT},
            {"point_on", PRO_CONSTRAINT_PNT_ON_ENT},
            {"tangent", PRO_CONSTRAINT_TANGENT_ENTS},
            {"perpendicular", PRO_CONSTRAINT_ORTHOG_ENTS},
            {"equal_radius", PRO_CONSTRAINT_EQUAL_RADII},
            {"parallel", PRO_CONSTRAINT_PARALLEL_ENTS},
            {"equal_length", PRO_CONSTRAINT_EQUAL_SEGMENTS},
            {"collinear", PRO_CONSTRAINT_COLLINEAR_LINES}};
        for (auto c : op["constraints"]) {
            std::vector<ProSelection> refs;
            for (auto r : c["refs"]) {
                ProSelection s = selected(section, entities.at(r["entity"].get<std::string>()),
                                          point_type(r.value("point", "whole")));
                refs.push_back(s);
            }
            int cid;
            ProError err = ProSectionConstraintCreate(section, refs.data(), (int)refs.size(),
                                                      ct.at(c["type"]), &cid);
            for (auto s : refs)
                ProSelectionFree(&s);
            if (err != PRO_TK_E_FOUND)
                check(err, "CreateSketchConstraint");
        }
        CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    }
    std::map<std::string, ProSecdimType> dt = {{"length", PRO_TK_DIM_LINE},
                                               {"radius", PRO_TK_DIM_RAD},
                                               {"diameter", PRO_TK_DIM_DIA},
                                               {"distance", PRO_TK_DIM_PNT_PNT},
                                               {"horizontal", PRO_TK_DIM_PNT_PNT_HORIZ},
                                               {"vertical", PRO_TK_DIM_PNT_PNT_VERT},
                                               {"line_distance", PRO_TK_DIM_LINE_LINE},
                                               {"angle", PRO_TK_DIM_LINES_ANGLE},
                                               {"arc_angle", PRO_TK_DIM_ARC_ANGLE},
                                               {"ellipse_x_radius", PRO_TK_DIM_ELLIPSE_X_RADIUS},
                                               {"ellipse_y_radius", PRO_TK_DIM_ELLIPSE_Y_RADIUS}};
    J dims = J::object();
    for (auto d : op.value("dimensions", J::array())) {
        std::vector<int> ids;
        std::vector<ProSectionPointType> senses;
        for (auto r : d["refs"]) {
            ids.push_back(entities.at(r["entity"].get<std::string>()));
            senses.push_back(point_type(r.value("point", "whole")));
        }
        double place[2];
        project(d["position"], place);
        int id;
        CK(ProSecdimCreate(section, ids.data(), senses.data(), (int)ids.size(), dt.at(d["type"]),
                           place, &id));
        CK(ProSecdimValueSet(section, id, d["value"]));
        dims[d["name"].get<std::string>()] = id;
    }

    J solver_info = solve_profile(section, op);
    J ids = J::object();
    for (auto item : entities)
        ids[item.first] = item.second;
    return {{"entity_ids", ids}, {"dimension_ids", dims}, {"solver", solver_info}};
}
#include "component_transform.h"
// Result split helpers are defined after the feature modules; forward declared
// here so component sources can resolve controlled detail references (BUG-077).
static J read_inspection_ref(const J &ref);
static J choice_inspection(const J &holder, const char *key);
#include "advanced.cpp"
#include "surfaces.cpp"
#include "udf.cpp"
#include "loft_mode.cpp"
#include "loft_seed.cpp"
#include "blend_create.cpp"
#include "sketch_edit.cpp"
#include "placement.cpp"
static void execute_operation(const J &op) {
    std::string kind = op.at("op");
    J details = J::object();
    log("PHASE=%s%s%s\n", kind.c_str(), op.contains("label") ? ":" : "",
        op.value("label", "").c_str());
    if (kind == "sketch" || kind == "airfoil_sketch")
        sketch(op);
    else if (kind == "update_sketch_geometry" || kind == "update_airfoil")
        generic_sketch_edit(op);
    else if (kind == "feature_group")
        generic_group(op);
    else if (kind == "reorder_features")
        generic_reorder(op);
    else if (kind == "axis_pattern")
        generic_axis_pattern(op);
    else if (kind == "geometry_transform")
        generic_transform(op);
    else if (kind == "set_geometry_transform")
        generic_transform_update(op);
    else if (kind == "extrude" || kind == "revolve")
        details = extrude_or_revolve(op, kind == "revolve");
    else if (kind == "hole")
        details = generic_hole(op);
    else if (kind == "round" || kind == "chamfer")
        details = generic_round(op, kind == "chamfer");
    else if (kind == "shell")
        generic_shell(op);
    else if (kind == "dimension_pattern")
        generic_pattern(op);
    else if (kind == "mirror")
        generic_mirror(op);
    else if (kind == "draft")
        generic_draft(op);
    else if (kind == "sweep")
        generic_sweep(op);
    else if (kind == "loft")
        generic_loft(op);
    else if (kind == "udf_inspect" || kind == "udf_create")
        generic_udf(op);
    else if (kind == "datum_csys")
        generic_csys(op);
    else if (kind == "datum_points")
        generic_points(op);
    else if (kind == "surface_fill")
        generic_fill(op);
    else if (kind == "thicken" || kind == "solidify")
        generic_surface_solid(op);
    else if (kind == "boolean_bodies")
        generic_boolean(op);
    else if (kind == "rib")
        generic_rib(op);
    else if (kind == "sheetmetal_wall")
        generic_sheetmetal_wall(op);
    else if (kind == "sheetmetal_flange")
        generic_sheetmetal_flange(op);
    else if (kind == "sheetmetal_unbend" || kind == "sheetmetal_flat_pattern" ||
             kind == "sheetmetal_bend_back")
        generic_sheetmetal_unbend(op);
    else if (kind == "assemble_component")
        assemble_component(op);
    else if (kind == "component_placement" || kind == "component_constraints" ||
             kind == "remove_component")
        modify_component(op);
    else if (kind == "datum_plane") {
        double angle = op.value("angle", 0.0);
        J axis = op.value("axis", J());
        auto f = offset_plane(op["reference"], op.value("offset", 0.0), wide(op["label"]),
                              op.contains("angle") ? &angle : nullptr,
                              op.contains("axis") ? &axis : nullptr);
        remember(op, f);
    } else if (kind == "datum_axis") {
        ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
        integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_AXIS);
        text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
        ProElement cs = node(root, PRO_E_DTMAXIS_CONSTRAINTS);
        for (auto r : op["references"]) {
            ProElement c = node(cs, PRO_E_DTMAXIS_CONSTRAINT);
            integer(c, PRO_E_DTMAXIS_CONSTR_TYPE, PRO_DTMAXIS_CONSTR_TYPE_THRU);
            ProSelection s = resolve(r);
            ref(c, PRO_E_DTMAXIS_CONSTR_REF, s);
            ProSelectionFree(&s);
        }
        ProFeature f = create(root);
        CK(ProElementFree(&root));
        remember(op, f);
    } else if (kind == "set_dimensions") {
        for (auto v : op["values"]) {
            ProDimension d;
            CK(ProModelitemInit(board, v["id"], PRO_DIMENSION, &d));
            ProBoolean relation_driven = PRO_B_FALSE;
            CK(ProDimensionIsReldriven(&d, &relation_driven));
            if (relation_driven)
                throw std::runtime_error("Dimension " + std::to_string(v["id"].get<int>()) +
                                         " is controlled by relations; edit its driving parameter "
                                         "or relation instead");
            CK(ProDimensionValueSet(&d, v["value"]));
        }
        mark_sketch_geometry_stale();
    } else if (kind == "set_sketch_dimensions") {
        ProFeature f = feature(op["sketch"]);
        ProElement root = nullptr;
        CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
        const J *meta =
            op["sketch"].is_string() ? alias_entry(op["sketch"].get<std::string>()) : nullptr;
        J saved_path =
            meta ? meta->value("section_path", J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER}))
                 : J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER});
        ProElement sk = get_path(root, saved_path);
        ProSection s = nullptr;
        CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&s));
        J ids = meta ? meta->value("dimension_ids", J::object()) : J::object();
        for (auto it = op["values"].begin(); it != op["values"].end(); ++it) {
            int id = ids.contains(it.key()) ? ids[it.key()].get<int>() : std::stoi(it.key());
            CK(ProSecdimValueSet(s, id, it.value()));
        }
        ProWSecerror err = nullptr;
        CK(ProSecerrorAlloc(&err));
        CK(ProSectionRegenerate(s, &err));
        ProSecerrorFree(&err);
        CK(ProElementSpecialvalueSet(sk, (ProAppData)s));
        redefine(&f, root);
        CK(ProFeatureElemtreeFree(&f, root));
        // Numeric references and relations to other sketches need the same
        // invalidation as label-based edits.
        mark_sketch_geometry_stale();
    } else if (kind == "set_parameters") {
        parameters(op);
        mark_sketch_geometry_stale();
    } else if (kind == "set_relations") {
        ProModelitem owner;
        CK(ProMdlToModelitem(board, &owner));
        ProRelset rel;
        ProError e = ProModelitemToRelset(&owner, &rel);
        if (e == PRO_TK_E_NOT_FOUND)
            CK(ProRelsetCreate(&owner, &rel));
        else
            check(e, "GetRelations");
        std::vector<std::wstring> storage;
        for (auto line : op["lines"])
            storage.push_back(wide(line));
        std::vector<ProWstring> ptrs;
        for (auto &line : storage)
            ptrs.push_back(const_cast<wchar_t *>(line.c_str()));
        CK(ProRelsetRelationsSet(&rel, ptrs.data(), (int)ptrs.size()));
        CK(ProRelsetRegenerate(&rel));
        mark_sketch_geometry_stale();
    } else if (kind == "feature_tree") {
        ProElement root = tree_from_json(op["tree"]);
        ProFeature f = create(root);
        CK(ProElementFree(&root));
        remember(op, f);
    } else if (kind == "export") {
        std::string format = op["format"], extension = format == "step"   ? ".stp"
                                                       : format == "stl"  ? ".stl"
                                                       : format == "iges" ? ".igs"
                                                                          : ".jpg";
        ProPath output;
        path(output, generic_job + L"\\output\\" + model_name + wide(extension));
        if (format == "jpeg") {
            CK(ProMdlDisplay(board));
            CK(ProMdlWindowGet(board, &win));
            CK(ProWindowRefit(win));
            CK(ProWindowRepaint(win));
            CK(ProRasterFileWrite(win, PRORASTERDEPTH_24, 8, 6, PRORASTERDPI_100,
                                  PRORASTERTYPE_JPEG, output));
        } else if (format == "stl")
            write_stl(output);
        else {
            ProIntf3DExportType t = format == "step" ? PRO_INTF_EXPORT_STEP : PRO_INTF_EXPORT_IGES;
            CK(ProIntf3DFileWriteWithDefaultProfile((ProSolid)board, t, output));
        }
        operation_results.push_back({{"op", kind}, {"file", utf8(output)}});
    } else if (kind == "dump_tree") {
        ProFeature f = feature(op["feature"]);
        ProElement root;
        CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
        ProPath output;
        path(output, generic_job + L"\\output\\feature_" + std::to_wstring(f.id) + L".xml");
        CK(ProElemtreeWrite(root, PRO_ELEMTREE_XML, output));
        CK(ProFeatureElemtreeFree(&f, root));
        operation_results.push_back({{"op", kind}, {"file", utf8(output)}});
    } else if (kind != "regenerate" && kind != "save")
        throw std::runtime_error("Operation is not implemented: " + kind);
    if (kind != "export" && kind != "dump_tree" && kind != "udf_inspect")
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    inspection();
    details.update({{"op", kind}, {"label", op.value("label", "")}, {"succeeded", true}});
    operation_results.push_back(details);
}
static void verify_assertions(const J &state, const J &a) {
    if (a.contains("volume_mm3")) {
        if (state["volume_mm3"].is_null() ||
            fabs(state["volume_mm3"].get<double>() - a["volume_mm3"].get<double>()) >
                a.value("volume_tolerance", 0.01))
            throw std::runtime_error("Volume assertion failed");
    }
    if (a.value("require_solid", false) && !state["has_solid"].get<bool>())
        throw std::runtime_error("Solid assertion failed");
}
static void verify_saved(const J &before, const J &after) {
    if (before["features"].size() != after["features"].size() ||
        before["bodies"].size() != after["bodies"].size())
        throw std::runtime_error("Saved feature/body count changed");
    for (size_t i = 0; i < before["features"].size(); i++) {
        auto a = before["features"][i], b = after["features"][i];
        if (a["id"] != b["id"] || a["type"] != b["type"] || a["name"] != b["name"] ||
            a["dimensions"].size() != b["dimensions"].size())
            throw std::runtime_error("Saved feature or dimensions changed");
        for (size_t j = 0; j < a["dimensions"].size(); j++)
            if (a["dimensions"][j]["id"] != b["dimensions"][j]["id"] ||
                fabs(a["dimensions"][j]["value"].get<double>() -
                     b["dimensions"][j]["value"].get<double>()) > 1e-6)
                throw std::runtime_error("Saved dimension value changed");
    }
    if (!before["volume_mm3"].is_null() &&
        (after["volume_mm3"].is_null() ||
         fabs(before["volume_mm3"].get<double>() - after["volume_mm3"].get<double>()) > 0.01))
        throw std::runtime_error("Saved solid volume changed");
    if (before["parameters"].size() != after["parameters"].size())
        throw std::runtime_error("Saved parameter count changed");
    for (auto it = before["parameters"].begin(); it != before["parameters"].end(); ++it) {
        if (!after["parameters"].contains(it.key()))
            throw std::runtime_error("Saved parameter disappeared: " + it.key());
        auto a = it.value(), b = after["parameters"][it.key()];
        bool equal = a["type"] == b["type"];
        if (equal && a["type"].get<int>() == PRO_PARAM_DOUBLE) {
            double x = a["value"], y = b["value"];
            equal = fabs(x - y) <= 1e-10 * std::max(1.0, std::max(fabs(x), fabs(y)));
        } else
            equal = equal && a["value"] == b["value"];
        if (!equal)
            throw std::runtime_error("Saved parameter value changed: " + it.key());
    }
    if (before.contains("components"))
        for (size_t i = 0; i < before["components"].size(); i++) {
            if (i >= after["components"].size())
                throw std::runtime_error("Saved component count changed");
            auto a = before["components"][i], b = after["components"][i];
            if (a.value("packaged", false) != b.value("packaged", false) ||
                a.value("underconstrained", false) != b.value("underconstrained", false))
                throw std::runtime_error("Saved assembly placement state changed");
            if (a.contains("constraints") && a["constraints"] != b["constraints"])
                throw std::runtime_error("Saved assembly constraints changed");
        }
    if (before.value("model_type", "part") != after.value("model_type", "part"))
        throw std::runtime_error("Saved model type changed");
    if (before.contains("components")) {
        if (before["components"].size() != after["components"].size())
            throw std::runtime_error("Saved component count changed");
        for (size_t i = 0; i < before["components"].size(); i++) {
            auto a = before["components"][i], b = after["components"][i];
            if (a["feature_id"] != b["feature_id"] || a["model_name"] != b["model_name"])
                throw std::runtime_error("Saved component changed");
            const auto &verified_transform = component_transform_for_verification(a, b);
            for (int r = 0; r < 4; r++)
                for (int c = 0; c < 4; c++)
                    if (fabs(a["transform"][r][c].get<double>() -
                             verified_transform[r][c].get<double>()) > 1e-7)
                        throw std::runtime_error("Saved component transform changed");
        }
    }
}
static std::wstring latest_model_file() {
    std::wstring extension = assembly_model() ? L".asm." : L".prt.",
                 mask = folder + L"\\" + model_name + extension + L"*";
    WIN32_FIND_DATAW info;
    HANDLE search = FindFirstFileW(mask.c_str(), &info);
    if (search == INVALID_HANDLE_VALUE)
        throw std::runtime_error("Saved model not found");
    int best = -1;
    std::wstring found;
    do {
        std::wstring name = info.cFileName;
        auto pos = name.rfind(extension);
        if (pos == std::wstring::npos)
            continue;
        try {
            int version = std::stoi(name.substr(pos + extension.size()));
            if (version > best) {
                best = version;
                found = folder + L"\\" + name;
            }
        } catch (...) {
        }
    } while (FindNextFileW(search, &info));
    FindClose(search);
    if (found.empty())
        throw std::runtime_error("Saved native model version not found");
    return found;
}
// The only path allowed to replace a diverged owned session model. Python has
// already bound the selected source and explicit action to a durable intent.
static bool recovery_geometry_equal(const J &a, const J &b) {
    if (a.is_number_integer() && b.is_number_integer())
        return a == b;
    if (a.is_number() && b.is_number()) {
        double x = a.get<double>(), y = b.get<double>();
        return std::isfinite(x) && std::isfinite(y) &&
               fabs(x - y) <= 1e-6 * std::max(1.0, std::max(fabs(x), fabs(y)));
    }
    if (a.type() != b.type() || a.size() != b.size())
        return false;
    if (a.is_object()) {
        for (auto it = a.begin(); it != a.end(); ++it)
            if (!b.contains(it.key()) || !recovery_geometry_equal(it.value(), b.at(it.key())))
                return false;
        return true;
    }
    if (a.is_array()) {
        for (size_t i = 0; i < a.size(); ++i)
            if (!recovery_geometry_equal(a[i], b[i]))
                return false;
        return true;
    }
    return a == b;
}

static void verify_recovery(const J &before, const J &after) {
    verify_saved(before, after);
    for (const char *key : {"bodies", "surfaces", "edges", "datum_planes"})
        if (!recovery_geometry_equal(before.at(key), after.at(key)))
            throw std::runtime_error(std::string("Recovery geometry changed: ") + key);
}

static std::string recovery_session_fingerprint() {
    ProConnectionId value;
    CK(ProEngineerConnectIdGet(value));
    // Bind the session without persisting or returning its connection secret.
    return std::to_string(std::hash<std::string>{}(std::string(value)));
}

static bool dependency_free(ProMdl mdl) {
    CK(ProMdlDependenciesCleanup(mdl));
    ProMdlnameShortdata *names = nullptr;
    ProMdlfileType *types = nullptr;
    int count = 0;
    ProError code = ProMdlDependenciesDataList(mdl, &names, &types, &count);
    if (names)
        ProArrayFree((ProArray *)&names);
    if (types)
        ProArrayFree((ProArray *)&types);
    if (code == PRO_TK_E_NOT_FOUND)
        return true;
    check(code, "RecoveryDependencies");
    return count == 0;
}

static bool recovery_dependency_free() {
    return dependency_free(board);
}

// Controlled inspection references (BUG-076): full payloads stay next to the
// job as sidecar files; control results carry only {file, sha256, bytes} and
// the Python closeout adds a small summary. Legacy inline payloads inside
// requests keep working through choice_inspection.
static J write_inspection_ref(const J &value, const char *stem) {
    const std::string data = value.dump(2);
    std::filesystem::path directory(folder);
    std::filesystem::path temp = directory / ("inspection-" + std::string(stem) + "-" +
                                              std::to_string(GetCurrentProcessId()) + "-" +
                                              std::to_string(GetTickCount()) + ".tmp");
    {
        std::ofstream output(temp, std::ios::binary | std::ios::trunc);
        output << data;
        output.flush();
        if (!output.good())
            throw std::runtime_error("Cannot write the inspection sidecar file");
    }
    // Content-addressed name: identical payloads reuse one file, a different
    // payload never overwrites a reference an earlier record still points to.
    const std::string digest = mechdog_callback::sha256(temp);
    std::filesystem::path file =
        directory / ("inspection-" + std::string(stem) + "-" + digest.substr(0, 16) + ".json");
    std::error_code rename_error;
    std::filesystem::rename(temp, file, rename_error);
    if (rename_error) {
        if (std::filesystem::exists(file))
            std::filesystem::remove(temp); // Same content is already stored.
        else {
            std::filesystem::remove(temp);
            throw std::runtime_error("Cannot publish the inspection sidecar file");
        }
    }
    return {{"file", utf8(file.wstring())}, {"sha256", digest}, {"bytes", (long long)data.size()}};
}

static J read_inspection_ref(const J &ref) {
    if (!ref.is_object() || !ref.contains("file") || !ref.contains("sha256"))
        throw std::runtime_error("Inspection reference is malformed");
    const std::filesystem::path file(wide(ref.at("file").get<std::string>()));
    if (mechdog_callback::sha256(file) != ref.at("sha256").get<std::string>())
        throw std::runtime_error(
            "Inspection reference hash mismatch: the referenced full inspection "
            "changed since it was recorded");
    std::ifstream input(file, std::ios::binary);
    if (!input)
        throw std::runtime_error("Inspection reference file is missing");
    J value;
    input >> value;
    return value;
}

static J choice_inspection(const J &holder, const char *key) {
    const std::string ref_key = std::string(key) + "_ref";
    if (holder.contains(ref_key))
        return read_inspection_ref(holder.at(ref_key));
    if (holder.contains(key))
        return holder.at(key);
    throw std::runtime_error(std::string("Request is missing ") + key);
}

static void split_report_inspections(const J &request, J &report) {
    // Keep full inspection payloads out of adoption/reconciliation control
    // results: move them into controlled sidecars and leave references
    // (BUG-076). Ordinary modeling plans keep their inline inspection: the
    // registry/query snapshot contract for created models is unchanged. Any
    // sidecar failure keeps the inline payload; the Python closeout splits
    // it again.
    if (!request.contains("adoption") && !request.contains("reconciliation"))
        return;
    try {
        if (report.contains("live") && report["live"].contains("inspection") &&
            report["live"]["inspection"].is_object() && !report["live"]["inspection"].empty()) {
            report["live"]["inspection_ref"] =
                write_inspection_ref(report["live"]["inspection"], "live");
            report["live"].erase("inspection");
        }
        if (report.contains("inspection") && report["inspection"].is_object() &&
            !report["inspection"].empty()) {
            report["inspection_ref"] = write_inspection_ref(report["inspection"], "verified");
            report.erase("inspection");
        }
    } catch (const std::exception &error) {
        log("INSPECTION_SPLIT_FAILED=%s\n", error.what());
    }
}

static bool millimeter_units(ProMdl mdl) {
    ProUnitsystem us;
    ProUnititem unit;
    CK(ProMdlPrincipalunitsystemGet(mdl, &us));
    CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
    return !wcscmp(unit.name, L"mm");
}

static void reconcile_native(const J &request, J &report) {
    const J &choice = request.at("reconciliation");
    const std::string action = choice.at("action");
    const std::string session = recovery_session_fingerprint();
    if (choice.contains("session_fingerprint") && choice["session_fingerprint"] != session)
        throw std::runtime_error("Recovery refused: Creo session changed since recorded evidence");
    ProName name;
    wcscpy_s(name, model_name.c_str());
    ProMdlType type = request["model"].value("model_type", "part") == "assembly" ? PRO_MDL_ASSEMBLY
                                                                                 : PRO_MDL_PART;
    ProError found = ProMdlInit(name, type, &board);
    if (found != PRO_TK_E_NOT_FOUND)
        check(found, "FindRecoveryModel");
    bool loaded = found == PRO_TK_NO_ERROR, owned = false;
    std::wstring origin;
    if (loaded) {
        ProPath value;
        CK(ProMdlOriginGet(board, value));
        origin = value;
        std::wstring prefix = folder + L"\\";
        owned = !_wcsnicmp(origin.c_str(), prefix.c_str(), prefix.size());
    }
    report["live"] = {{"loaded", loaded},
                      {"owned", owned},
                      {"origin", utf8(origin)},
                      {"session_fingerprint", session}};
    if (action == "inspect") {
        if (loaded && owned) {
            report["live"]["inspection"] = inspection(false);
            ProUnitsystem us;
            ProUnititem unit;
            CK(ProMdlPrincipalunitsystemGet(board, &us));
            CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
            report["live"]["millimeter_units"] = !wcscmp(unit.name, L"mm");
            report["live"]["dependency_free"] = recovery_dependency_free();
            try {
                if (request["model"].contains("inspection") ||
                    request["model"].contains("inspection_ref")) {
                    verify_recovery(choice_inspection(request["model"], "inspection"),
                                    report["live"]["inspection"]);
                    report["live"]["matches_baseline"] = true;
                }
            } catch (const std::exception &error) {
                report["live"]["matches_baseline"] = false;
                report["live"]["baseline_mismatch"] = error.what();
            }
        }
        report["success"] = true;
        return;
    }
    if (loaded && !owned)
        throw std::runtime_error("Recovery refused: session model origin is not owned");
    if (action == "abandon_new") {
        if (loaded) {
            CK(ProMdlErase(board));
            board = nullptr;
        }
        report.update({{"success", true}, {"abandoned", true}, {"files_preserved", true}});
        return;
    }
    if (action == "accept_live") {
        if (!loaded ||
            (!choice.contains("live_inspection") && !choice.contains("live_inspection_ref")))
            throw std::runtime_error(
                "accept_live requires an owned loaded model and live evidence");
        verify_recovery(choice_inspection(choice, "live_inspection"), inspection());
    } else if (action == "restore_baseline" || action == "accept_saved") {
        if (loaded) {
            CK(ProMdlErase(board));
            board = nullptr;
        }
        ProPath source;
        path(source, wide(choice.at("source_file")));
        CK(ProMdlFiletypeLoad(source, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    } else
        throw std::runtime_error("Unknown reconciliation action");
    ProUnitsystem us;
    ProUnititem unit;
    CK(ProMdlPrincipalunitsystemGet(board, &us));
    CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
    if (wcscmp(unit.name, L"mm"))
        throw std::runtime_error("Recovery requires millimeter model units");
    if (!recovery_dependency_free())
        throw std::runtime_error(
            "Recovery refused: external dependencies require separate ownership verification");
    generic_stage("recovery_verify_source");
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    J before = inspection();
    if (action != "accept_live")
        verify_recovery(choice_inspection(choice, "source_inspection"), before);
    report["loft_checks"]["recovery_source"] = verify_loft_settings(L"recovery_source");
    std::wstring saved = action == "restore_baseline" ? wide(choice.at("source_file")) : L"";
    if (action != "restore_baseline") {
        generic_stage("recovery_save_and_reload");
        ProPath destination;
        path(destination, folder);
        CK(ProMdlnameBackup(board, destination));
        saved = latest_model_file(); // Only select the output of this acknowledged save.
        CK(ProMdlErase(board));
        board = nullptr;
        ProPath file;
        path(file, saved);
        CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    }
    J after = inspection();
    verify_recovery(before, after);
    report["loft_checks"]["recovery_reloaded"] = verify_loft_settings(L"recovery_reloaded");
    after["inspection_source"] = "reconciliation_verified";
    after["inspection_available"] = true;
    CK(ProMdlDisplay(board));
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", aliases},
                   {"part_file", utf8(saved)}});
}

// Explicit adoption of the user's current window model as a managed copy. The
// source model is never erased, saved or renamed; adoption copies the in-memory
// state into this job's output directory and verifies the copy like any save.
static void display_adopted_model() {
    CK(ProMdlDisplay(board));
    int window = -1;
    CK(ProMdlWindowGet(board, &window));
    CK(ProWindowCurrentSet(window));
    CK(ProWindowRefit(window));
    CK(ProWindowRepaint(window));
    CK(ProWindowActivate(window));
}

static void confirm_adoption_snapshot(const J &choice, J &report) {
    std::wstring saved = wide(choice.at("source_file"));
    auto candidate = std::filesystem::path(saved).lexically_normal();
    auto output = std::filesystem::path(folder).lexically_normal();
    if (!candidate.is_absolute() || _wcsicmp(candidate.parent_path().c_str(), output.c_str()) ||
        candidate.filename().wstring().find(model_name + L".prt.") != 0)
        throw std::runtime_error("Prepared snapshot is outside its owned output");
    ProMdlName name = {};
    wcscpy_s(name, model_name.c_str());
    ProError found = ProMdlInit(name, PRO_MDL_PART, &board);
    if (found == PRO_TK_NO_ERROR) {
        ProPath origin = {};
        CK(ProMdlOriginGet(board, origin));
        if (_wcsicmp(origin, saved.c_str()))
            throw std::runtime_error("Prepared snapshot name conflicts with another session model");
        // Refuse rather than discard manual changes to the staged copy.
        verify_recovery(choice_inspection(choice, "source_inspection"), inspection(false));
        CK(ProMdlErase(board));
        board = nullptr;
    } else if (found != PRO_TK_E_NOT_FOUND)
        check(found, "FindPreparedSnapshot");
    ProPath file;
    path(file, saved);
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    if (!millimeter_units(board) || !dependency_free(board))
        throw std::runtime_error("Prepared snapshot units or dependencies changed");
    J after = inspection();
    verify_recovery(choice_inspection(choice, "source_inspection"), after);
    after["inspection_source"] = "adoption_snapshot_verified";
    after["inspection_available"] = true;
    display_adopted_model();
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", J::object()},
                   {"part_file", utf8(saved)},
                   {"adopted", true}});
}

struct SessionInventory {
    J models = J::array();
    J type_errors = J::array();
    bool truncated = false;
    int current_code = 0;
};

// Single-handle session observation shared by the session inventory and the
// open-file result; the field set stays identical so clients can compare
// entries from either source. current_code mirrors ProMdlCurrentGet's own
// outcome: when it failed, is_current is null rather than a guess.
static J observe_session_model(ProMdl mdl, const char *model_type, ProMdl current,
                               int current_code) {
    ProMdlName name = {};
    ProPath origin = {};
    ProBoolean modified = PRO_B_FALSE;
    int id = -1;
    ProError nc = ProMdlMdlnameGet(mdl, name);
    ProError oc = ProMdlOriginGet(mdl, origin);
    ProError mc = ProMdlModificationVerify(mdl, &modified);
    ProError ic = ProMdlIdGet(mdl, &id);
    return {{"name", nc ? J(nullptr) : J(utf8(name))},
            {"model_type", model_type},
            {"is_current", current_code ? J(nullptr) : J(mdl == current)},
            {"origin", oc ? J(nullptr) : J(utf8(origin))},
            {"has_saved_origin", oc ? J(nullptr) : J(origin[0] != 0)},
            {"modified", mc ? J(nullptr) : J(modified == PRO_B_TRUE)},
            {"session_model_id", ic ? J(nullptr) : J(id)},
            {"query_codes", {{"name", nc}, {"origin", oc}, {"modified", mc}, {"id", ic}}}};
}

static void collect_session_models(SessionInventory &inventory) {
    ProMdl current = nullptr;
    inventory.current_code = ProMdlCurrentGet(&current);
    J models = J::array(), errors = J::array();
    const std::pair<ProMdlType, const char *> types[] = {{PRO_MDL_PART, "part"},
                                                         {PRO_MDL_ASSEMBLY, "assembly"},
                                                         {PRO_MDL_DRAWING, "drawing"},
                                                         {PRO_MDL_3DSECTION, "section3d"},
                                                         {PRO_MDL_2DSECTION, "section2d"},
                                                         {PRO_MDL_LAYOUT, "notebook"},
                                                         {PRO_MDL_DWGFORM, "drawing_format"},
                                                         {PRO_MDL_MFG, "manufacturing"},
                                                         {PRO_MDL_REPORT, "report"},
                                                         {PRO_MDL_MARKUP, "markup"},
                                                         {PRO_MDL_DIAGRAM, "diagram"}};
    bool truncated = false;
    for (const auto &entry : types) {
        ProMdl *list = nullptr;
        int count = 0;
        ProError listed = ProSessionMdlList(entry.first, &list, &count);
        if (listed != PRO_TK_NO_ERROR && listed != PRO_TK_E_NOT_FOUND) {
            errors.push_back({{"model_type", entry.second}, {"code", listed}});
        } else if (listed == PRO_TK_NO_ERROR) {
            try {
                for (int i = 0; i < count; ++i) {
                    if (models.size() >= 4096) {
                        truncated = true;
                        break;
                    }
                    J item = observe_session_model(list[i], entry.second, current,
                                                   inventory.current_code);
                    if (entry.first == PRO_MDL_PART) {
                        ProMdlsubtype subtype;
                        ProError sc = ProMdlSubtypeGet(list[i], &subtype);
                        item["query_codes"]["subtype"] = sc;
                        if (!sc && subtype == PROMDLSTYPE_PART_SHEETMETAL)
                            item["model_type"] = "sheetmetal";
                    }
                    models.push_back(item);
                }
            } catch (...) {
                if (list)
                    ProArrayFree((ProArray *)&list);
                throw;
            }
        }
        if (list)
            CK(ProArrayFree((ProArray *)&list));
    }
    inventory.models = models;
    inventory.type_errors = errors;
    inventory.truncated = truncated;
}

static void session_models_native(J &report) {
    SessionInventory inventory;
    collect_session_models(inventory);
    report.update({{"success", true},
                   {"models", inventory.models},
                   {"type_errors", inventory.type_errors},
                   {"complete", inventory.type_errors.empty() && !inventory.truncated},
                   {"truncated", inventory.truncated},
                   {"current_model_code", inventory.current_code}});
}

// FEAT-045: read-only inspection of a resident assembly. The walk selects an
// already-loaded assembly by name, never loads, activates, regenerates, saves
// or adopts anything, and reports every node in tree order with occurrence
// paths, resolved 4x4 transforms and constraint snapshots. Per-node failures
// are marked with their raw query codes instead of failing the whole report.
// The walk's mutable report state (recorded nodes plus the truncated/
// incomplete/depth_limited judgements) is the shared AssemblyWalkState from
// assembly_walk.h, executed by the offline harness too.

// BUG-080: the walk carries both the raw member-to-root chain (member length
// unit -> root length unit) and the millimeter-normalized chain. Either chain
// stops being trustworthy once an ancestor transform or unit query failed, so
// descendants report an unknown root transform instead of inheriting a
// grandparent matrix as if it were their own.
struct WalkContext {
    ProSolid owner = nullptr;
    std::vector<int> path; // component feature ids from the root assembly
    // BUG-080 follow-up: both member-to-root chains with independent
    // validity; WalkChain defaults to the real identity instead of the old
    // zero-initialized raw root.
    WalkChain chain;
    AssemblyWalkState *walk = nullptr;
    ProMdl current = nullptr;
    int current_code = -1;
    int depth = 0;
};

// Creo ProMatrix is row-major with row-vector convention p' = p * M, so the
// translation lives in the last row. BUG-080: entries are raw Creo values in
// the source/target model length units (see assembly_units.h); millimeter
// maps are produced separately and stay null when units are unknown.
static J matrix_json(const ProMatrix matrix) {
    J rows = J::array();
    for (int r = 0; r < 4; ++r) {
        J row = J::array();
        for (int c = 0; c < 4; ++c)
            row.push_back(matrix[r][c]);
        rows.push_back(row);
    }
    return rows;
}

// BUG-080: one model's real length unit with its millimeter scale and every
// raw query code; name and scale stay null on failure instead of pretending
// millimeters.
static J length_unit_json(const InspectionLengthUnits &units, const MillimeterScale &scale) {
    return {{"name", units.code ? J(nullptr) : J(utf8(units.length.name))},
            {"query_code", units.code},
            {"scale_to_mm", scale.known ? J(scale.scale) : J(nullptr)},
            {"scale_to_mm_known", scale.known},
            {"scale_query_codes",
             {{"unit", scale.unit_query_code},
              {"mm_unit", sdk_query_code_json(scale.mm_unit_queried, scale.mm_unit_query_code)},
              {"conversion",
               sdk_query_code_json(scale.conversion_queried, scale.conversion_query_code)}}}};
}

static J assembly_selection_json(ProSelection selection) {
    J reference = J::object();
    ProAsmcomppath component_path;
    ProError path_code = ProSelectionAsmcomppathGet(selection, &component_path);
    reference["comppath_query_code"] = path_code;
    if (!path_code) {
        ProMdlName owner_name = {};
        if (!ProMdlMdlnameGet(component_path.owner, owner_name)) {
            reference["owner_name"] = utf8(owner_name);
            J ids = J::array();
            int levels = component_path.table_num;
            if (levels > PRO_MAX_ASSEM_LEVEL)
                levels = PRO_MAX_ASSEM_LEVEL; // clamp a garbage count defensively
            for (int i = 0; i < levels; ++i)
                ids.push_back(component_path.comp_id_table[i]);
            reference["occurrence_path"] = ids;
        }
    }
    ProModelitem item;
    ProError item_code = ProSelectionModelitemGet(selection, &item);
    reference["item_query_code"] = item_code;
    if (!item_code) {
        reference["item_type"] = item.type;
        reference["item_id"] = item.id;
    }
    return reference;
}

static J constraint_json(ProAsmcompconstraint constraint) {
    static const std::map<int, const char *> type_names = {
        {PRO_ASM_FIX, "fix"},
        {PRO_ASM_MATE, "mate"},
        {PRO_ASM_MATE_OFF, "mate_offset"},
        {PRO_ASM_ALIGN, "align"},
        {PRO_ASM_ALIGN_OFF, "align_offset"},
        {PRO_ASM_INSERT, "insert"},
        {PRO_ASM_ORIENT, "orient"},
        {PRO_ASM_CSYS, "csys"},
        {PRO_ASM_TANGENT, "tangent"},
        {PRO_ASM_PNT_ON_SRF, "pnt_on_srf"},
        {PRO_ASM_EDGE_ON_SRF, "edge_on_srf"},
        {PRO_ASM_DEF_PLACEMENT, "default"},
        {PRO_ASM_AUTO, "auto"},
    };
    J item = J::object();
    J codes = J::object();
    ProAsmcompConstrType type = PRO_ASM_FIX;
    int type_code = ProAsmcompconstraintTypeGet(constraint, &type);
    codes["type"] = type_code;
    if (!type_code) {
        auto found = type_names.find(type);
        item["type"] = found != type_names.end() ? found->second : "unknown";
        item["type_code"] = (int)type;
    } else {
        item["type"] = nullptr;
    }
    double offset = 0.0;
    int offset_code = ProAsmcompconstraintOffsetGet(constraint, &offset);
    codes["offset"] = offset_code;
    item["offset"] = offset_code ? J(nullptr) : J(offset);
    ProSelection selection = nullptr;
    ProDatumside side = PRO_DATUM_SIDE_NONE;
    int asm_code = ProAsmcompconstraintAsmreferenceGet(constraint, &selection, &side);
    codes["asm_reference"] = asm_code;
    item["asm_reference"] = asm_code ? J(nullptr) : assembly_selection_json(selection);
    int comp_code = ProAsmcompconstraintCompreferenceGet(constraint, &selection, &side);
    codes["comp_reference"] = comp_code;
    item["comp_reference"] = comp_code ? J(nullptr) : assembly_selection_json(selection);
    static const std::map<int, const char *> side_names = {{PRO_DATUM_SIDE_YELLOW, "yellow"},
                                                           {PRO_DATUM_SIDE_RED, "red"},
                                                           {PRO_DATUM_SIDE_NONE, "none"}};
    if (!asm_code || !comp_code) {
        auto found = side_names.find(side);
        item["orientation"] = found != side_names.end() ? found->second : "unknown";
    }
    item["query_codes"] = codes;
    return item;
}

static J component_constraints_json(ProAsmcomp *component, J &codes) {
    J constraints = J::array();
    ProAsmcompconstraint *list = nullptr;
    // The comppath form with the owning-assembly path is the supported read;
    // a NULL path crashed native runs on Creo 12, so the path is always built.
    ProIdTable ids = {};
    ids[0] = component->id;
    ProAsmcomppath owner_path;
    ProError path_code = ProAsmcomppathInit((ProSolid)component->owner, ids, 1, &owner_path);
    codes["constraint_comppath"] = path_code;
    ProError code =
        path_code ? path_code : ProAsmcompConstraintsWithComppathGet(component, &owner_path, &list);
    codes["constraints"] = code;
    if (code == PRO_TK_NO_ERROR && list) {
        int count = 0;
        if (!ProArraySizeGet((ProArray)list, &count))
            for (int i = 0; i < count; ++i) {
                constraints.push_back(constraint_json(list[i]));
            }
        ProAsmcompconstraintArrayFree(list);
    } else if (code == PRO_TK_E_NOT_FOUND) {
        codes["constraints"] = 0; // no constraints recorded: packaged placement
    }
    return constraints;
}

static ProError assembly_feature_callback(ProFeature *feature, ProError status, ProAppData data) {
    auto *context = (WalkContext *)data;
    AssemblyWalkState &walk = *context->walk;
    if (status)
        return status;
    if (walk.truncated)
        return PRO_TK_NO_ERROR;
    ProFeattype type;
    ProError type_code = ProFeatureTypeGet(feature, &type);
    if (!walk.apply_query_outcome(type_code)) {
        // An unclassifiable feature may be a component whose whole subtree
        // would silently drop out of the walk; keep visiting siblings but
        // drop the tree completeness claim.
        log("WALK_TYPE_QUERY_FAILED=%d\n", (int)type_code);
        return PRO_TK_NO_ERROR;
    }
    if (type != PRO_FEAT_COMPONENT)
        return PRO_TK_NO_ERROR;
    auto *component = (ProAsmcomp *)feature;
    J item = J::object();
    J codes = J::object();
    std::vector<int> occurrence = context->path;
    occurrence.push_back(feature->id);
    J path_json = J::array();
    for (int id : occurrence)
        path_json.push_back(id);
    J parent_json = J::array();
    for (int id : context->path)
        parent_json.push_back(id);
    item["component_id"] = feature->id;
    item["occurrence_path"] = path_json;
    item["parent_path"] = parent_json;
    item["depth"] = context->depth;
    ProFeatStatus feature_status = PRO_FEAT_ACTIVE;
    int status_code = ProFeatureStatusGet(feature, &feature_status);
    codes["feature_status"] = status_code;
    item["feature_status"] = status_code ? J(nullptr) : J((int)feature_status);
    // The component's own feature state (active or suppressed) must stay
    // confirmable; a failed query drops completeness through the shared
    // query outcome judgement instead of a duplicated condition (BUG-080).
    walk.apply_query_outcome((ProError)status_code);
    item["suppressed"] = status_code ? J(nullptr)
                                     : J(feature_status == PRO_FEAT_SUPPRESSED ||
                                         feature_status == PRO_FEAT_FAMTAB_SUPPRESSED ||
                                         feature_status == PRO_FEAT_SIMP_REP_SUPPRESSED ||
                                         feature_status == PRO_FEAT_PROG_SUPPRESSED);
    ProBoolean packaged = PRO_B_FALSE;
    int packaged_code = ProAsmcompIsPackaged(component, &packaged);
    codes["packaged"] = packaged_code;
    item["packaged"] = packaged_code ? J(nullptr) : J(packaged == PRO_B_TRUE);
    ProMdl child = nullptr;
    ProError model_code = ProAsmcompMdlGet(component, &child);
    codes["model"] = model_code;
    if (model_code || !child) {
        // The component feature exists but its model did not resolve (for
        // example a missing file); keep the node observable instead of
        // failing. The shared missing-node operation stamps the resolved /
        // subtree flags itself and drops completeness.
        item.update({{"name", nullptr}, {"model_type", nullptr}, {"constraints", J::array()}});
        item["query_codes"] = codes;
        walk.record_missing_component(item);
        return PRO_TK_NO_ERROR;
    }
    item["resolved"] = true;
    J observed = observe_session_model(child, "", context->current, context->current_code);
    ProMdlType kind = PRO_MDL_PART;
    ProError kind_code = ProMdlTypeGet(child, &kind);
    codes["model_type"] = kind_code;
    // An unclassifiable child model may hide a whole sub-assembly; the node
    // stays observable but the tree completeness claim is dropped through
    // the shared query outcome judgement.
    walk.apply_query_outcome(kind_code);
    const char *kind_name = kind_code ? "" : kind == PRO_MDL_ASSEMBLY ? "assembly" : "part";
    observed["model_type"] = kind_code ? J(nullptr) : J(kind_name);
    ProMdlsubtype subtype = PROMDLSTYPE_PART_SOLID;
    if (!kind_code && kind == PRO_MDL_PART && !ProMdlSubtypeGet(child, &subtype) &&
        subtype == PROMDLSTYPE_PART_SHEETMETAL)
        observed["model_type"] = "sheetmetal";
    for (auto it = observed.begin(); it != observed.end(); ++it)
        item[it.key()] = it.value();
    // observed carries the child's session-identity query codes
    // (name/origin/modified/id); merge them into the node codes so that
    // executed diagnosis survives instead of being overwritten below.
    if (observed.contains("query_codes")) {
        for (auto it = observed["query_codes"].begin(); it != observed["query_codes"].end(); ++it)
            codes[it.key()] = it.value();
    }
    // BUG-080: query the real component/owner units next to the transform and
    // normalize to a full millimeter coordinate map; the raw matrix is always
    // kept, and the normalized map stays null (never pretend-mm) whenever the
    // transform or any required unit scale is unknown.
    InspectionLengthUnits component_units = inspect_length_units(child);
    InspectionLengthUnits parent_units = inspect_length_units((ProMdl)component->owner);
    MillimeterScale component_scale = length_scale_to_mm(child, component_units);
    MillimeterScale parent_scale = length_scale_to_mm((ProMdl)component->owner, parent_units);
    item["units"] = {{"component", length_unit_json(component_units, component_scale)},
                     {"parent", length_unit_json(parent_units, parent_scale)}};
    ProMatrix to_parent = {};
    ProError transform_code = component_to_assembly_transform(component, to_parent);
    codes["transform"] = transform_code;
    // BUG-080 follow-up: a successful query whose returned matrix contains
    // NaN/Infinity is not a known map; serializing it would emit null entries
    // while transform_known stayed true, so the raw map is dropped instead.
    const bool raw_map_known = local_transform_known(transform_code, to_parent);
    ProMatrix to_parent_mm = {};
    bool parent_map_known =
        raw_map_known && component_scale.known && parent_scale.known &&
        normalize_transform_mm(to_parent, component_scale.scale, parent_scale.scale, to_parent_mm);
    item["transform_to_parent"] = parent_map_known ? matrix_json(to_parent_mm) : J(nullptr);
    item["transform_to_parent_raw"] = raw_map_known ? matrix_json(to_parent) : J(nullptr);
    item["transform_known"] = raw_map_known;
    item["transform_mm_known"] = parent_map_known;
    if (!transform_code && !parent_map_known)
        item["transform_unknown_reason"] = !raw_map_known ? "non_finite"
                                           : (!component_scale.known || !parent_scale.known)
                                               ? "unknown_units"
                                               : "invalid_scale";
    // Root maps come from the shared chain composition: a chain exists only
    // while this local map and every ancestor step stayed known, and finite
    // overflow poisons the chain instead of serializing null inside a
    // "known" transform. A failed parent transform or unknown ancestor unit
    // therefore yields null root maps here, never a reused grandparent.
    WalkChainStep step = walk_chain_compose(context->chain, to_parent, raw_map_known, to_parent_mm,
                                            parent_map_known);
    item["transform_to_root_raw"] =
        step.root_raw_known ? matrix_json(step.to_root_raw) : J(nullptr);
    item["transform_to_root"] = step.root_mm_known ? matrix_json(step.to_root_mm) : J(nullptr);
    item["transform_root_known"] = step.root_mm_known;
    // An unknown local or root chain, or an overflowing combination, makes
    // the report incomplete; the node's own known local maps stay observable.
    if (!parent_map_known || !step.root_mm_known || !step.root_raw_known)
        walk.mark_incomplete();
    item["constraints"] = component_constraints_json(component, codes);
    item["query_codes"] = codes;
    const size_t node_index = walk.record_node(item);
    if (walk.truncated)
        return PRO_TK_NO_ERROR;
    if (!kind_code && kind == PRO_MDL_ASSEMBLY) {
        WalkContext sub;
        sub.owner = (ProSolid)child;
        sub.path = occurrence;
        // Propagate both chains through the shared step: a failed local
        // transform, unknown unit or overflow poisons the descendant
        // root maps instead of reusing the grandparent matrix.
        sub.chain = walk_chain_descend(context->chain, step);
        sub.walk = context->walk;
        sub.current = context->current;
        sub.current_code = context->current_code;
        sub.depth = context->depth + 1;
        // The shared visit operation enforces the depth limit before the
        // visit and diagnoses a failed sub-assembly walk on the stored node
        // (node_index) instead of failing the whole report — sibling
        // components stay observable.
        walk.visit_subtree(context->depth, node_index, [&sub]() -> ProError {
            return ProSolidFeatVisit(sub.owner, assembly_feature_callback, nullptr,
                                     (ProAppData)&sub);
        });
    }
    return PRO_TK_NO_ERROR;
}

static void session_assembly_native(const J &request, J &report) {
    const J &choice = request.at("session_assembly");
    std::wstring requested = wide(choice.at("name").get<std::string>());
    if (requested.empty())
        throw std::runtime_error("SESSION_ASSEMBLY_NAME_REQUIRED: pass the resident "
                                 "assembly name from creo_list_session_models");
    ProName name = {};
    wcscpy_s(name, requested.c_str());
    ProMdl mdl = nullptr;
    ProError found = ProMdlInit(name, PRO_MDL_ASSEMBLY, &mdl);
    if (found == PRO_TK_E_NOT_FOUND)
        throw std::runtime_error("SESSION_ASSEMBLY_NOT_FOUND: no resident assembly with that name; "
                                 "select one from creo_list_session_models");
    check(found, "ProMdlInit");
    ProMdlType kind = PRO_MDL_ASSEMBLY;
    check(ProMdlTypeGet(mdl, &kind), "ProMdlTypeGet");
    if (kind != PRO_MDL_ASSEMBLY)
        throw std::runtime_error("SESSION_ASSEMBLY_TYPE_MISMATCH: the resident model "
                                 "with that name is not an assembly");
    ProMdl current = nullptr;
    int current_code = ProMdlCurrentGet(&current);
    AssemblyWalkState walk;
    walk.budget = 4096;
    // Query the root length unit before the walk: it decides whether the
    // normalized root chain is interpretable at all. The shared root
    // initialization ties the root chain validity to the real root unit and
    // marks an unknown root unit incomplete up front, so even an empty tree
    // is globally incomplete then.
    InspectionLengthUnits root_units = inspect_length_units(mdl);
    MillimeterScale root_scale = length_scale_to_mm(mdl, root_units);
    WalkContext context;
    context.owner = (ProSolid)mdl;
    context.walk = &walk;
    context.current = current;
    context.current_code = current_code;
    walk.init_root_chain(context.chain, root_scale);
    // A failed root visit makes the report incomplete (root_visit_code)
    // instead of throwing away the whole inspection.
    int root_visit_code =
        ProSolidFeatVisit(context.owner, assembly_feature_callback, nullptr, (ProAppData)&context);
    if (root_visit_code)
        walk.record_root_visit_failure();
    J root = observe_session_model(mdl, "assembly", current, current_code);
    root["length_unit"] = length_unit_json(root_units, root_scale);
    report.update(
        {{"success", true},
         {"assembly", root},
         {"components", walk.components},
         {"component_count", walk.components.size()},
         {"truncated", walk.truncated},
         {"depth_limited", walk.depth_limited},
         {"root_visit_code", root_visit_code},
         {"incomplete", walk.incomplete},
         {"complete", walk.complete(root_scale.known)},
         {"transform_convention",
          "row-vector 4x4 matrices in Creo ProMatrix order (p' = p * M); translation occupies "
          "the last row; transform_to_parent and transform_to_root are normalized full "
          "coordinate maps with input and output coordinates in millimeters; "
          "transform_to_parent_raw and transform_to_root_raw keep the raw Creo matrices "
          "mapping member-solid coordinates (member length unit) into owner/root-solid "
          "coordinates (owner/root length unit); per-node units.component/units.parent and "
          "assembly.length_unit carry the real unit names, query codes and millimeter scales "
          "and are null when unknown - normalized transforms are then null too instead of "
          "pretending millimeters; constraint offsets stay in the owning assembly length "
          "unit; raw cross-unit matrix semantics follow the local SDK member-transform "
          "documentation and remain pending real mixed-unit machine verification"},
         {"readonly_note", "inspection only: no component loading, activation, "
                           "regeneration, save, adoption or managed revision"}});
}

// FEAT-046: explicit, evidence-bound erasure of selected session models.
// No saves and no disk deletion; assemblies erase before their components;
// every item re-verifies identity, modification state and references, and
// each erasure is confirmed absent through two independent queries before
// success is reported. The whole job runs under one Toolkit channel lock.
struct EraseModel {
    std::wstring name;
    std::string model_type;
    std::string key; // lowercase name + "|" + family (part|assembly)
    ProMdl mdl = nullptr;
    ProPath origin = {};
    bool modified = false;
    bool has_origin = false;
};

static std::string erase_family(const std::string &model_type) {
    return model_type == "assembly" ? "assembly" : "part";
}

static std::string erase_key(const std::wstring &name, const std::string &model_type) {
    std::string lowered;
    for (wchar_t c : name)
        lowered += static_cast<char>(towlower(c));
    return lowered + "|" + erase_family(model_type);
}

// One dependency enumeration over every session part/assembly: each entry maps
// a session key to the set of session keys it depends on.
static std::map<std::string, std::vector<std::string>> session_dependency_graph(
    const std::vector<EraseModel> &models, J &query_errors) {
    std::map<std::string, std::vector<std::string>> graph;
    for (const auto &model : models) {
        ProMdlnameShortdata *names = nullptr;
        ProMdlfileType *types = nullptr;
        int count = 0;
        ProError code = ProMdlDependenciesDataList(model.mdl, &names, &types, &count);
        if (code == PRO_TK_E_NOT_FOUND) {
            graph[model.key] = {};
            continue;
        }
        if (code != PRO_TK_NO_ERROR) {
            query_errors.push_back({{"key", model.key}, {"code", code}});
            graph[model.key] = {};
            continue;
        }
        try {
            std::vector<std::string> dependencies;
            for (int i = 0; i < count; ++i) {
                std::string family = types[i] == PRO_MDLFILE_ASSEMBLY ? "assembly" : "part";
                dependencies.push_back(erase_key(std::wstring(names[i].name), family));
            }
            graph[model.key] = dependencies;
        } catch (...) {
            ProArrayFree((ProArray *)&names);
            ProArrayFree((ProArray *)&types);
            throw;
        }
        ProArrayFree((ProArray *)&names);
        ProArrayFree((ProArray *)&types);
    }
    return graph;
}

static void session_erase_native(const J &request, J &report) {
    const J &choice = request.at("session_erase");
    const std::string action = choice.at("action");
    if (action != "inspect" && action != "apply")
        throw std::runtime_error("Unknown session-erase action");
    generic_stage("session_erase_inventory");
    SessionInventory inventory;
    collect_session_models(inventory);
    if (!inventory.type_errors.empty() || inventory.truncated)
        throw std::runtime_error(
            "SESSION_ENUMERATION_INCOMPLETE: the session inventory could not be "
            "completed, so erase preconditions cannot be proven; nothing was erased");
    // Fresh handles for every session part/assembly (the inventory above only
    // keeps names).
    ProMdl current = nullptr;
    int current_code = ProMdlCurrentGet(&current);
    std::vector<EraseModel> session;
    std::vector<std::wstring> managed_roots;
    if (choice.contains("managed_roots"))
        for (const auto &root : choice.at("managed_roots"))
            managed_roots.push_back(wide(root.get<std::string>()));
    for (const auto &pair : std::initializer_list<std::pair<ProMdlType, const char *>>{
             {PRO_MDL_PART, "part"}, {PRO_MDL_ASSEMBLY, "assembly"}}) {
        ProMdl *list = nullptr;
        int count = 0;
        ProError listed = ProSessionMdlList(pair.first, &list, &count);
        if (listed == PRO_TK_E_NOT_FOUND)
            continue;
        check(listed, "ProSessionMdlList(erase)");
        try {
            for (int i = 0; i < count; ++i) {
                EraseModel model;
                model.model_type = pair.second;
                if (pair.first == PRO_MDL_PART) {
                    ProMdlsubtype subtype;
                    if (!ProMdlSubtypeGet(list[i], &subtype) &&
                        subtype == PROMDLSTYPE_PART_SHEETMETAL)
                        model.model_type = "sheetmetal";
                }
                ProMdlName name = {};
                if (!ProMdlMdlnameGet(list[i], name))
                    model.name = name;
                ProError oc = ProMdlOriginGet(list[i], model.origin);
                model.has_origin = !oc && model.origin[0] != 0;
                ProBoolean modified = PRO_B_FALSE;
                model.modified =
                    !ProMdlModificationVerify(list[i], &modified) && modified == PRO_B_TRUE;
                model.mdl = list[i];
                model.key = erase_key(model.name, model.model_type);
                session.push_back(model);
            }
        } catch (...) {
            if (list)
                ProArrayFree((ProArray *)&list);
            throw;
        }
        if (list)
            CK(ProArrayFree((ProArray *)&list));
    }
    auto find = [&](const std::wstring &name, const std::string &model_type) {
        std::string wanted = erase_key(name, model_type);
        const EraseModel *found = nullptr;
        for (const auto &model : session)
            if (model.key == wanted) {
                if (found)
                    throw std::runtime_error(
                        "SESSION_ERASE_AMBIGUOUS: more than one session model matches a "
                        "target; refuse instead of picking one");
                found = &model;
            }
        return found;
    };
    auto is_managed = [&](const EraseModel &model) {
        for (const auto &root : managed_roots) {
            std::wstring prefix = root;
            if (!prefix.empty() && prefix.back() != L'\\')
                prefix += L"\\";
            if (!_wcsnicmp(model.origin, prefix.c_str(), prefix.size()))
                return true;
        }
        return false;
    };

    J targets = J::array();
    std::vector<const EraseModel *> manifest;
    for (const auto &target : choice.at("targets")) {
        std::wstring name = wide(target.at("name").get<std::string>());
        std::string model_type = target.value("model_type", "part");
        const EraseModel *model = find(name, model_type);
        J entry = {{"name", utf8(name)}, {"model_type", model_type}};
        if (!model) {
            entry["blocked"] = {{"reason", "not_in_session"},
                                {"message", "No session model matches this name and type"}};
        } else {
            int id = -1;
            ProMdlIdGet(model->mdl, &id);
            entry.update({
                {"session_model_id", id},
                {"origin", model->has_origin ? J(utf8(model->origin)) : J(nullptr)},
                {"modified", model->modified},
                {"is_current", current_code ? J(nullptr) : J(model->mdl == current)},
            });
            if (!model->has_origin)
                entry["blocked"] = {{"reason", "never_saved"},
                                    {"message",
                                     "The model has no saved origin; explicit erase covers "
                                     "saved session objects only"}};
            else if (model->modified)
                entry["blocked"] = {{"reason", "modified"},
                                    {"message", "The model has unsaved changes; save or "
                                                "discard them in Creo first"}};
            else if (is_managed(*model))
                entry["blocked"] = {{"reason", "managed"},
                                    {"message",
                                     "The model belongs to this service's managed output; use "
                                     "creo_reconcile_model instead of erasing it here"}};
            else
                manifest.push_back(model);
        }
        targets.push_back(entry);
    }
    // Bind a reference: json value semantics would detach every later update
    // of the summary from the report.
    report["session_erase"] = {{"targets", targets}, {"action", action}};
    J &summary = report["session_erase"];
    if (action == "inspect") {
        // Reference graph over the whole session: an outside model referencing
        // a manifest target, or a cycle inside the manifest, blocks erasure.
        generic_stage("session_erase_reference_check");
        J query_errors = J::array();
        auto graph = session_dependency_graph(session, query_errors);
        if (!query_errors.empty())
            throw std::runtime_error(
                "SESSION_ERASE_DEPENDENCY_QUERY_FAILED: dependency enumeration "
                "failed for at least one session model; preconditions cannot be "
                "proven; nothing was erased");
        std::set<std::string> manifest_keys;
        for (const EraseModel *model : manifest)
            manifest_keys.insert(model->key);
        bool blocked = false;
        for (auto &entry : targets)
            if (!entry.contains("blocked")) {
                std::string key = erase_key(wide(entry["name"].get<std::string>()),
                                            entry["model_type"].get<std::string>());
                for (const auto &[holder, dependencies] : graph) {
                    if (manifest_keys.count(holder))
                        continue;
                    for (const auto &dependency : dependencies)
                        if (dependency == key) {
                            blocked = true;
                            entry["blocked"] = {
                                {"reason", "referenced_outside_manifest"},
                                {"message",
                                 "A session model outside the erase manifest references "
                                 "this target; add it to the manifest or erase it in Creo"}};
                        }
                }
            }
        // Topological erase order: a model no in-manifest model depends on
        // goes first; dependents always erase before their dependencies.
        std::map<std::string, int> dependents;
        for (const auto &key : manifest_keys)
            dependents[key] = 0;
        for (const auto &key : manifest_keys)
            for (const auto &dependency : graph[key])
                if (dependents.count(dependency))
                    dependents[dependency] += 1;
        std::vector<std::string> order;
        std::set<std::string> placed;
        while (order.size() < manifest_keys.size()) {
            bool progressed = false;
            for (const auto &key : manifest_keys) {
                if (placed.count(key) || dependents[key] > 0)
                    continue;
                placed.insert(key);
                order.push_back(key);
                for (const auto &dependency : graph[key])
                    if (dependents.count(dependency))
                        dependents[dependency] -= 1;
                progressed = true;
            }
            if (!progressed) {
                summary.update({
                    {"available", false},
                    {"reason_code", "dependency_cycle"},
                    {"message", "The manifest contains a dependency cycle; no erase order "
                                "exists; nothing was erased"},
                });
                return;
            }
        }
        J erase_order = J::array();
        for (const auto &key : order) {
            for (const auto &entry : targets)
                if (!entry.contains("blocked") &&
                    erase_key(wide(entry["name"].get<std::string>()),
                              entry["model_type"].get<std::string>()) == key)
                    erase_order.push_back({{"name", entry["name"]},
                                           {"model_type", entry["model_type"]},
                                           {"origin", entry["origin"]},
                                           {"modified", entry["modified"]}});
        }
        J remaining = J::array();
        for (const auto &model : session) {
            if (!manifest_keys.count(model.key))
                remaining.push_back({{"name", utf8(model.name)},
                                     {"model_type", model.model_type},
                                     {"modified", model.modified}});
        }
        bool any_blocked = false;
        for (const auto &entry : targets)
            if (entry.contains("blocked"))
                any_blocked = true;
        summary.update({
            {"available", !any_blocked},
            {"reason_code", any_blocked ? J("blocked_targets") : J(nullptr)},
            {"erase_order", erase_order},
            {"remaining_after", remaining},
            {"message", any_blocked ? "One or more targets are blocked; nothing was erased; "
                                      "resolve the blocking reasons and inspect again"
                                    : "Erase plan verified; apply with the evidence token to "
                                      "execute exactly this manifest"},
        });
        report["success"] = true;
        return;
    }

    // apply: execute exactly the manifest from the token, one item at a time.
    generic_stage("session_erase_apply");
    J erased = J::array();
    J unconfirmed = nullptr;
    std::set<std::string> done;
    for (const auto &item : choice.at("erase_order")) {
        std::wstring name = wide(item.at("name").get<std::string>());
        std::string model_type = item.at("model_type");
        std::string key = erase_key(name, model_type);
        const EraseModel *model = find(name, model_type);
        if (!model) {
            if (done.empty())
                throw std::runtime_error(
                    "SESSION_ERASE_IDENTITY_CHANGED: the first manifest item is no "
                    "longer in the session; refuse instead of erasing a changed "
                    "session; nothing was erased");
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "relocate"},
                           {"message", "The item disappeared from the session before its "
                                       "turn; earlier items stay erased"}};
            break;
        }
        if (model->modified) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "modification_recheck"},
                           {"message", "The item reports unsaved changes now; it was not "
                                       "erased; earlier items stay erased"}};
            break;
        }
        std::wstring expected = wide(item.at("origin").get<std::string>());
        if (model->has_origin && _wcsicmp(model->origin, expected.c_str())) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "origin_recheck"},
                           {"message", "The item's origin changed since the token was "
                                       "issued; it was not erased; earlier items stay "
                                       "erased"}};
            break;
        }
        if (is_managed(*model)) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "managed_recheck"},
                           {"message", "The item now looks managed by this service; it "
                                       "was not erased; earlier items stay erased"}};
            break;
        }
        CK(ProMdlErase(model->mdl));
        // Confirm absence through two independent queries; a zero return from
        // ProMdlErase alone never reports success.
        ProMdl probe = nullptr;
        ProName locate = {};
        wcsncpy_s(locate, model->name.c_str(), _TRUNCATE);
        ProError first =
            ProMdlInit(locate, model_type == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART, &probe);
        ProMdl *residue = nullptr;
        int residue_count = 0;
        ProError listed = ProSessionMdlList(
            model_type == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART, &residue, &residue_count);
        bool absent = first == PRO_TK_E_NOT_FOUND;
        if (listed == PRO_TK_NO_ERROR) {
            for (int i = 0; i < residue_count && absent; ++i) {
                ProMdlName other = {};
                if (!ProMdlMdlnameGet(residue[i], other) && !_wcsicmp(other, model->name.c_str()))
                    absent = false;
            }
            ProArrayFree((ProArray *)&residue);
        } else if (listed != PRO_TK_E_NOT_FOUND) {
            check(listed, "ProSessionMdlList(erase-confirm)");
        }
        if (!absent) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "absence_confirmation"},
                           {"message", "ProMdlErase returned success but the model is "
                                       "still observable in the session; it stays listed "
                                       "as not confirmed erased"}};
            break;
        }
        done.insert(key);
        erased.push_back({{"name", item.at("name")}, {"model_type", model_type}});
    }
    SessionInventory after;
    collect_session_models(after);
    J remaining_after = J::array();
    for (const auto &item2 : after.models)
        remaining_after.push_back(item2);
    summary.update({
        {"erased", erased},
        {"unconfirmed", unconfirmed},
        {"remaining_after", remaining_after},
        {"stopped_early", !unconfirmed.is_null()},
        {"message", unconfirmed.is_null()
                        ? "Manifest erased and confirmed absent; nothing was saved and "
                          "no disk file was deleted"
                        : "Erasure stopped at an item; erased items stay erased; "
                          "unconfirmed and remaining items are listed explicitly"},
    });
    report["success"] = unconfirmed.is_null();
    if (!unconfirmed.is_null())
        report["message"] = summary["message"];
}

static int components_total = 0;
static int components_missing = 0;
static ProError component_probe(ProFeature *feature, ProError status, ProAppData) {
    if (status)
        return status;
    ProFeattype type;
    if (ProFeatureTypeGet(feature, &type))
        return PRO_TK_NO_ERROR;
    if (type != PRO_FEAT_COMPONENT)
        return PRO_TK_NO_ERROR;
    components_total++;
    ProMdl component = nullptr;
    if (ProAsmcompMdlGet((ProAsmcomp *)feature, &component) != PRO_TK_NO_ERROR)
        components_missing++;
    return PRO_TK_NO_ERROR;
}

// Read-only retrieval and display of an existing on-disk native model. The file
// is never saved, erased, renamed or adopted; success creates no managed model.
static void open_file_native(const J &request, J &report) {
    const J &choice = request.at("open_file");
    std::wstring requested = wide(choice.at("requested_path").get<std::string>());
    std::wstring selected = wide(choice.at("selected_file").get<std::string>());
    bool assembly = choice.at("model_kind").get<std::string>() == "assembly";
    std::filesystem::path file_path(selected);
    std::wstring base = file_path.filename().wstring();
    if (size_t dot = base.rfind(L'.'); dot != std::wstring::npos) {
        std::wstring tail = base.substr(dot + 1);
        if (!tail.empty() && tail.find_first_not_of(L"0123456789") == std::wstring::npos)
            base = base.substr(0, dot);
        if (dot = base.rfind(L'.'); dot != std::wstring::npos) {
            std::wstring ext = base.substr(dot + 1);
            if (!_wcsicmp(ext.c_str(), L"prt") || !_wcsicmp(ext.c_str(), L"asm"))
                base = base.substr(0, dot);
        }
    }
    if (base.empty() || base.find_first_of(L".") != std::wstring::npos)
        throw std::runtime_error("Cannot derive a model name from the selected file path");
    J summary = {{"requested_path", utf8(requested)},
                 {"selected_file", utf8(selected)},
                 {"model_kind", assembly ? "assembly" : "part"},
                 {"model_name", utf8(base)}};
    report["open_file"] = summary;
    // Pre-checks and retrieval share one Toolkit channel: the session state the
    // checks observed is the state retrieval starts from.
    generic_stage("open_file_session_check");
    SessionInventory inventory;
    collect_session_models(inventory);
    if (!inventory.type_errors.empty() || inventory.truncated) {
        report["session_inventory"] = {{"type_errors", inventory.type_errors},
                                       {"truncated", inventory.truncated}};
        throw std::runtime_error(
            "SESSION_ENUMERATION_INCOMPLETE: the session inventory could not be "
            "completed, so open-file preconditions cannot be proven; no file was "
            "retrieved");
    }
    for (const auto &item : inventory.models) {
        if (item["name"].is_null())
            continue;
        bool same_name = !_wcsicmp(wide(item["name"].get<std::string>()).c_str(), base.c_str());
        std::string kind = item["model_type"];
        bool same_family = assembly ? kind == "assembly" : (kind == "part" || kind == "sheetmetal");
        if (same_name && same_family) {
            report["open_file"]["conflicting_session_model"] = item;
            throw std::runtime_error(
                "SESSION_NAME_CONFLICT: a " + kind +
                " model with this name is already in the Creo session; the file was "
                "not retrieved. Close or erase it in Creo first, or switch to it "
                "directly. A previously retrieved assembly may have loaded this "
                "name as a dependency (check creo_list_session_models; assembly "
                "components stay in the session even after their window closes)");
        }
    }
    if (assembly) {
        for (const auto &item : inventory.models) {
            std::string kind = item["model_type"];
            if (kind == "part" || kind == "sheetmetal" || kind == "assembly")
                throw std::runtime_error(
                    "ASSEMBLY_REQUIRES_EMPTY_SESSION: the session already holds a "
                    "part or assembly; assembly retrieval needs a session without "
                    "parts/assemblies so partial loading stays observable. No file "
                    "was retrieved");
        }
    }
    generic_stage("open_file_retrieve");
    ProMdl opened = nullptr;
    ProPath file;
    path(file, selected);
    ProError load_code = ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &opened);
    if (load_code != PRO_TK_NO_ERROR) {
        // Retrieval of an incomplete assembly can leave components in the session.
        // Report them explicitly; the missing-component list is unknown to Toolkit.
        SessionInventory after;
        collect_session_models(after);
        J remaining = J::array();
        for (const auto &item : after.models) {
            std::string kind = item["model_type"];
            if (kind == "part" || kind == "sheetmetal" || kind == "assembly")
                remaining.push_back(item);
        }
        report["loaded"] = false;
        report["open_file"]["loaded"] = false;
        report["open_file"]["missing_components"] = "unknown";
        report["open_file"]["remaining_session_models"] = remaining;
        report["open_file"]["remaining_models_note"] =
            "retrieval failed; listed part/assembly objects may be partial residues of "
            "this attempt and are not erased automatically";
        throw std::runtime_error(
            "RETRIEVE_FAILED: ProMdlFiletypeLoad returned " + std::to_string(load_code) +
            " for the selected file; assemblies failing here usually miss components "
            "(list unavailable, marked unknown). Inspect remaining_session_models; "
            "nothing was saved or erased");
    }
    report["loaded"] = true;
    report["open_file"]["loaded"] = true;
    ProMdlType kind = PRO_MDL_PART;
    check(ProMdlTypeGet(opened, &kind), "ProMdlTypeGet");
    if (kind != (assembly ? PRO_MDL_ASSEMBLY : PRO_MDL_PART)) {
        report["open_file"]["actual_model_type_code"] = kind;
        throw std::runtime_error(
            "MODEL_TYPE_MISMATCH: the retrieved file is not the requested model kind; "
            "the loaded object stays in the session, nothing was saved or erased");
    }
    if (assembly) {
        // Toolkit retrieves an incomplete assembly without error; the component
        // features exist but their models stay unresolved. Refuse to report a
        // complete open in that case and leave the residues observable.
        generic_stage("open_file_component_check");
        components_total = 0;
        components_missing = 0;
        check(ProSolidFeatVisit((ProSolid)opened, component_probe, nullptr, nullptr),
              "ProSolidFeatVisit");
        report["open_file"]["component_count"] = components_total;
        if (components_missing > 0) {
            SessionInventory after;
            collect_session_models(after);
            J remaining = J::array();
            for (const auto &item : after.models) {
                std::string item_kind = item["model_type"];
                if (item_kind == "part" || item_kind == "sheetmetal" || item_kind == "assembly")
                    remaining.push_back(item);
            }
            report["open_file"].update(
                {{"displayed", false},
                 {"missing_component_count", components_missing},
                 {"missing_components",
                  {{"count", components_missing},
                   {"total", components_total},
                   {"names", "unknown"}}},
                 {"remaining_session_models", remaining},
                 {"remaining_models_note",
                  "retrieval incomplete; the assembly object stays in the session "
                  "(not displayed, not erased); listed part/assembly objects may be "
                  "partial residues"}});
            throw std::runtime_error(
                "RETRIEVE_INCOMPLETE: the assembly was retrieved but " +
                std::to_string(components_missing) + " of " + std::to_string(components_total) +
                " components did not resolve (names unavailable, marked unknown). The "
                "assembly is not displayed; inspect remaining_session_models; nothing "
                "was saved or erased");
        }
    }
    std::string model_type = assembly ? "assembly" : "part";
    if (kind == PRO_MDL_PART) {
        ProMdlsubtype subtype;
        ProError sc = ProMdlSubtypeGet(opened, &subtype);
        if (!sc && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            model_type = "sheetmetal";
    }
    ProPath origin = {};
    check(ProMdlOriginGet(opened, origin), "ProMdlOriginGet");
    ProMdlName display = {};
    ProError name_code = ProMdlMdlnameGet(opened, display);
    report["open_file"].update(
        {{"model_type", model_type},
         {"origin", utf8(origin)},
         {"origin_matches_selected_file", !_wcsicmp(origin, selected.c_str())},
         {"display_name", name_code ? J(nullptr) : J(utf8(display))}});
    generic_stage("open_file_display");
    bool displayed = false;
    std::string display_message;
    try {
        CK(ProMdlDisplay(opened));
        int window = -1;
        CK(ProMdlWindowGet(opened, &window));
        CK(ProWindowCurrentSet(window));
        CK(ProWindowRefit(window));
        CK(ProWindowRepaint(window));
        CK(ProWindowActivate(window));
        displayed = true;
    } catch (ProError error) {
        display_message = "Toolkit call " + last_toolkit_error + " failed with code " +
                          std::to_string(error) + " during open_file_display";
    } catch (const std::exception &error) {
        display_message = error.what();
    }
    report["open_file"]["displayed"] = displayed;
    if (!displayed) {
        report["open_file"]["display_message"] = display_message;
        report["message"] =
            "Loaded the model into the session but could not display it: " + display_message +
            "; the object remains in the session (query creo_list_session_models); "
            "nothing was saved or erased";
        return;
    }
    // Single-handle observation of the just-opened model: the same fields as a
    // session-inventory entry, read directly from the opened handle without a
    // fresh full enumeration. The Python closeout stamps observed_at.
    ProMdl window_model = nullptr;
    int window_code = ProMdlCurrentGet(&window_model);
    report["open_file"]["opened_session_model"] =
        observe_session_model(opened, model_type.c_str(), window_model, window_code);
    // Bounded post-open session summary (FEAT-044): one full enumeration
    // distinguishes session model objects from the component instances an
    // assembly retrieval brings in. The bounded page is a summary; the
    // complete, refreshable inventory is creo_list_session_models.
    {
        SessionInventory after;
        collect_session_models(after);
        J page = J::array();
        constexpr size_t page_limit = 20;
        for (const auto &item : after.models) {
            if (page.size() >= page_limit)
                break;
            page.push_back(item);
        }
        report["open_file"]["loaded_session_models"] = {
            {"session_model_count", after.models.size()},
            {"component_instance_count", assembly ? J(components_total) : J(nullptr)},
            {"component_instance_scope",
             assembly ? "component features of the assembly opened by this job"
                      : "not an assembly open"},
            {"models", page},
            {"page_limit", page_limit},
            {"complete", after.models.size() <= page_limit},
            {"has_more", after.models.size() > page_limit},
            {"detail", "creo_list_session_models without cursor re-collects the live "
                       "inventory; its cursor pages read a frozen snapshot"}};
    }
    report["success"] = true;
}

// Raw ProFeatureStatusGet codes are the queryable truth; the label is only a
// readability hint and stays "unknown_status_code" outside the SDK enum.
static const char *feat_status_name(int status) {
    switch (status) {
    case PRO_FEAT_INVALID:
        return "invalid";
    case PRO_FEAT_ACTIVE:
        return "active";
    case PRO_FEAT_INACTIVE:
        return "inactive";
    case PRO_FEAT_FAMTAB_SUPPRESSED:
        return "famtab_suppressed";
    case PRO_FEAT_SIMP_REP_SUPPRESSED:
        return "simplified_rep_suppressed";
    case PRO_FEAT_PROG_SUPPRESSED:
        return "program_suppressed";
    case PRO_FEAT_SUPPRESSED:
        return "suppressed";
    case PRO_FEAT_UNREGENERATED:
        return "unregenerated";
    default:
        return "unknown_status_code";
    }
}

// Bounded per-feature diagnosis for the unhealthy_features refusal (FEAT-006):
// every failed, suppressed or incomplete feature keeps its id, name, type and
// raw status code, but only the first item_limit entries travel in control
// metadata; unhealthy_total and truncated keep the omitted remainder countable.
// The health admission rule itself does not change.
static J health_details(const J &features) {
    constexpr size_t item_limit = 20;
    J items = J::array();
    size_t total = 0;
    for (const auto &f : features) {
        bool incomplete = f.value("incomplete", false);
        int status = f.value("status", PRO_FEAT_ACTIVE);
        if (!incomplete && status == PRO_FEAT_ACTIVE)
            continue;
        total++;
        if (items.size() >= item_limit)
            continue;
        items.push_back({{"id", f.value("id", 0)},
                         {"name", f.value("name", "")},
                         {"type_name", f.value("type_name", "")},
                         {"status_code", status},
                         {"status", feat_status_name(status)},
                         {"incomplete", incomplete}});
    }
    return {{"unhealthy_total", total},
            {"returned", items.size()},
            {"item_limit", item_limit},
            {"truncated", total > items.size()},
            {"items", items}};
}

static void adopt_native(const J &request, J &report) {
    const J &choice = request.at("adoption");
    const std::string action = choice.at("action");
    if (action == "confirm_snapshot") {
        confirm_adoption_snapshot(choice, report);
        return;
    }
    bool preparing = action == "prepare";
    const std::string session = recovery_session_fingerprint();
    if (choice.contains("session_fingerprint") && choice["session_fingerprint"] != session)
        throw std::runtime_error("Adoption refused: Creo session changed since recorded evidence");
    ProMdl current = nullptr;
    ProError current_code = ProMdlCurrentGet(&current);
    if (current_code == PRO_TK_BAD_CONTEXT)
        // -8 is "no current model", not a connection failure; keep the call name
        // and raw code so the original evidence stays machine-checkable.
        throw std::runtime_error(
            "NO_CURRENT_MODEL: the Creo window has no current model "
            "(ProMdlCurrentGet(&current) returned -8 PRO_TK_BAD_CONTEXT during " +
            generic_phase +
            "); switch to a model in Creo first; creo_list_session_models shows the "
            "session inventory");
    check(current_code, "ProMdlCurrentGet(&current)");
    ProMdlType kind = PRO_MDL_PART;
    CK(ProMdlTypeGet(current, &kind));
    if (kind != PRO_MDL_PART)
        throw std::runtime_error(
            "unsupported_model_type: only part or sheetmetal models can be adopted; "
            "assemblies and drawings keep their own ownership (adoption refused)");
    ProPath origin = {};
    CK(ProMdlOriginGet(current, origin));
    std::wstring origin_text = origin;
    if (choice.contains("origin") &&
        _wcsicmp(wide(choice.at("origin").get<std::string>()).c_str(), origin_text.c_str()))
        throw std::runtime_error(
            "Adoption refused: the current model is not the inspected model; inspect again");
    board = current; // Borrow the handle read-only, exactly like reconciliation inspect.
    J live = inspection(false);
    bool millimeters = live["units"] == "mm";
    bool dependency_clean = dependency_free(board);
    std::string model_type = live.value("model_type", "part");
    bool supported = model_type == "part" || model_type == "sheetmetal";
    ProMdlName display = {};
    ProError name_code = ProMdlMdlnameGet(current, display);
    J diagnosis = health_details(live["features"]);
    report["live"] = {{"origin", utf8(origin_text)},
                      {"model_type", model_type},
                      {"healthy", live.at("healthy")},
                      {"feature_count", live.at("features").size()},
                      {"volume_mm3", live.contains("volume_mm3") ? live["volume_mm3"] : J(nullptr)},
                      {"millimeter_units", millimeters},
                      {"dependency_free", dependency_clean},
                      {"session_fingerprint", session},
                      {"health_details", diagnosis},
                      {"inspection", live}};
    if (name_code == PRO_TK_NO_ERROR)
        report["live"]["display_name"] = utf8(display);
    if (action == "inspect") {
        board = nullptr;
        report["success"] = true;
        return;
    }
    if (action != "apply" && !preparing)
        throw std::runtime_error("Unknown adoption action");
    if (choice.contains("live_inspection") || choice.contains("live_inspection_ref"))
        verify_recovery(choice_inspection(choice, "live_inspection"), live);
    board = nullptr; // The user's model is never the managed target again past this point.
    if (preparing && !origin_text.empty())
        throw std::runtime_error(
            "prepare requires a never-saved model; use inspect/apply for a file source");
    if (!preparing && origin_text.empty())
        throw std::runtime_error(
            "Never-saved model requires explicit prepare, then confirm its frozen snapshot");
    if (!live.value("healthy", false))
        throw std::runtime_error(
            "unhealthy_features: source has failed, suppressed or incomplete features (" +
            std::to_string(diagnosis["unhealthy_total"].get<size_t>()) + " unhealthy; first " +
            std::to_string(diagnosis["returned"].get<size_t>()) +
            " listed in live.health_details) (adoption refused)");
    if (!supported)
        throw std::runtime_error("unsupported_model_type: only independent part or sheetmetal "
                                 "models are supported (adoption refused)");
    if (!millimeters)
        throw std::runtime_error(
            "non_millimeter_units: millimeter model units are required (adoption refused)");
    if (!dependency_clean)
        throw std::runtime_error("external_dependencies: external dependencies require separate "
                                 "ownership verification (adoption refused)");
    struct WindowRestore {
        int window = -1;
        ~WindowRestore() {
            if (window >= 0) {
                ProError selected = ProWindowCurrentSet(window);
                ProError activated = ProWindowActivate(window);
                log("ADOPTION_WINDOW_RESTORE=%d,%d\n", selected, activated);
            }
        }
    } window_restore;
    int original_window = -1;
    if (preparing) {
        CK(ProWindowCurrentGet(&original_window));
        if (original_window < 0)
            throw std::runtime_error("Snapshot preparation requires a current model window");
        window_restore.window = original_window;
    }
    ProName adopted;
    wcscpy_s(adopted, model_name.c_str());
    ProMdl clash = nullptr;
    ProError found = ProMdlInit(adopted, PRO_MDL_PART, &clash);
    if (found == PRO_TK_NO_ERROR)
        throw std::runtime_error("session_name_conflict: the managed model name already exists in "
                                 "this Creo session (adoption refused)");
    if (found != PRO_TK_E_NOT_FOUND)
        check(found, "CheckAdoptedName");
    CK(ProMdlnameCopy(current, adopted, &board));
    if (!millimeter_units(board))
        throw std::runtime_error(
            "non_millimeter_units: copied model units are not millimeter (adoption refused)");
    if (!dependency_free(board))
        throw std::runtime_error("external_dependencies: the copied model carries external "
                                 "dependencies (adoption refused)");
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    J before = inspection();
    verify_recovery(live, before); // Prove the copy includes the live source state.
    generic_stage("adoption_save_and_reload");
    ProPath destination;
    path(destination, folder);
    CK(ProMdlnameBackup(board, destination));
    std::wstring saved = latest_model_file(); // Only select the output of this adoption save.
    CK(ProMdlErase(board));
    board = nullptr;
    ProPath file;
    path(file, saved);
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    J after = inspection();
    verify_recovery(before, after);
    after["inspection_source"] = "adoption_verified";
    after["inspection_available"] = true;
    if (preparing) {
        CK(ProWindowCurrentSet(original_window));
        CK(ProWindowActivate(original_window));
        window_restore.window = -1;
    } else
        display_adopted_model();
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", J::object()},
                   {"part_file", utf8(saved)},
                   {"adopted", !preparing}});
}

static int run_generic(const std::wstring &job) {
    generic_job = job;
    generic_phase = "loading_request";
    last_toolkit_error.clear();
    J report = {{"success", false},
                {"saved_file_reloaded_and_verified", false},
                {"rollback_succeeded", false}};
    J request;
    ProProcessHandle process = {};
    bool connected = false, mutated = false;
    std::unique_ptr<RecoveryDeadline> recovery_deadline;
    int operation_index = -1;
    bool executing_operation = false;
    std::wstring checkpoint;
    board_log = _wfsopen((job + L"\\native.log").c_str(), L"w", _SH_DENYNO);
    if (!board_log)
        return 3;
    try {
        std::ifstream input(job + L"\\request.json");
        input >> request;
        FILETIME created, exited, kernel, user;
        if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user) ||
            !publish_native_json(
                job + L"\\native_owner.json",
                {{"pid", GetCurrentProcessId()},
                 {"created", (static_cast<unsigned long long>(created.dwHighDateTime) << 32) |
                                 created.dwLowDateTime}}))
            throw std::runtime_error("Cannot persist native process identity");
        if (request.contains("reconciliation")) {
            recovery_deadline = std::make_unique<RecoveryDeadline>(job);
        }
        auto model = request.at("model");
        model_name = wide(model.at("model_name"));
        folder = wide(model.at("output_directory"));
        // Split registry records pass a controlled reference instead of an
        // inline aliases payload; legacy requests keep the inline dict (BUG-077).
        aliases = model.contains("aliases_ref") ? read_inspection_ref(model.at("aliases_ref"))
                                                : model.at("aliases");
        component_sources = request.value("components", J::object());
        for (auto item = component_sources.begin(); item != component_sources.end(); ++item) {
            if (item.value().contains("aliases_ref"))
                item.value()["aliases"] = read_inspection_ref(item.value().at("aliases_ref"));
            if (item.value().contains("inspection_ref"))
                item.value()["inspection"] = read_inspection_ref(item.value().at("inspection_ref"));
        }
        template_file = wide(request.at("template_file"));
        if (!model["part_file"].is_null())
            checkpoint = wide(model["part_file"]);
        char empty[] = "";
        ProBoolean random = PRO_B_FALSE;
        generic_stage("connect");
        CK(connect_creo(&process));
        connected = true;
        report["connected"] = true;
        int release_numeric = 0;
        ProError release_code = ProEngineerReleaseNumericversionGet(&release_numeric);
        report["creo_release_query_code"] = release_code;
        report["creo_release_numeric"] = release_code ? J(nullptr) : J(release_numeric);
        report["session_fingerprint"] = recovery_session_fingerprint();
        if (!publish_native_json(
                job + L"\\native_owner.json",
                {{"pid", GetCurrentProcessId()},
                 {"created", (static_cast<unsigned long long>(created.dwHighDateTime) << 32) |
                                 created.dwLowDateTime},
                 {"session_fingerprint", report["session_fingerprint"]}}))
            throw std::runtime_error("Cannot persist connected session ownership evidence");
        if (request.contains("reconciliation")) {
            generic_stage("recovery_" + request["reconciliation"]["action"].get<std::string>());
            reconcile_native(request, report);
        } else if (request.contains("session_models")) {
            generic_stage("list_session_models");
            session_models_native(report);
        } else if (request.contains("session_assembly")) {
            generic_stage("inspect_session_assembly");
            session_assembly_native(request, report);
        } else if (request.contains("open_file")) {
            generic_stage("open_file_" + request["open_file"]["model_kind"].get<std::string>());
            open_file_native(request, report);
        } else if (request.contains("session_erase")) {
            generic_stage("session_erase_" + request["session_erase"]["action"].get<std::string>());
            session_erase_native(request, report);
        } else if (request.contains("adoption")) {
            generic_stage("adoption_" + request["adoption"]["action"].get<std::string>());
            adopt_native(request, report);
        } else {
            // Recovery has its own evidence-bound path. Check callback readiness
            // only for a normal plan that will create a direct Blend.
            for (const auto &operation : request.at("operations")) {
                if (operation.value("op", "") == "loft") {
                    generic_stage("callback_preflight");
                    wchar_t executable[MAX_PATH];
                    GetModuleFileNameW(nullptr, executable, MAX_PATH);
                    std::string command;
                    resident_blend_callback(std::filesystem::path(executable).parent_path(),
                                            command);
                    break;
                }
            }
            ProName name;
            wcscpy_s(name, model_name.c_str());
            ProMdlType mdltype =
                model.value("model_type", "part") == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART;
            ProError found = ProMdlInit(name, mdltype, &board);
            if (request.at("new").get<bool>()) {
                if (found == PRO_TK_NO_ERROR)
                    throw std::runtime_error("New model name already exists in the Creo session");
                if (found != PRO_TK_E_NOT_FOUND)
                    check(found, "CheckNewModelName");
                ProPath original, destination, tfile;
                CK(ProDirectoryCurrentGet(original));
                path(destination, folder);
                path(tfile, template_file);
                CK(ProDirectoryChange(destination));
                try {
                    ProMdl templ;
                    if (request.contains("loft_seed"))
                        templ = load_isolated_loft_seed(template_file, report["seed_native_load"]);
                    else
                        CK(ProMdlFiletypeLoad(tfile, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &templ));
                    ProMdlName new_name;
                    wcscpy_s(new_name, model_name.c_str());
                    CK(ProMdlnameCopy(templ, new_name, &board));
                    if (request.contains("loft_seed"))
                        CK(ProMdlErase(templ));
                } catch (...) {
                    ProDirectoryChange(original);
                    throw;
                }
                CK(ProDirectoryChange(original));
                mutated = true;
            } else {
                if (found == PRO_TK_E_NOT_FOUND) {
                    if (checkpoint.empty())
                        throw std::runtime_error(
                            "model_reconciliation_required: no saved baseline");
                    ProPath file;
                    path(file, checkpoint);
                    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
                } else
                    check(found, "FindOwnedModel");
                if (checkpoint.empty() && !request.value("readonly", false))
                    throw std::runtime_error("model_reconciliation_required: refusing to adopt a "
                                             "checkpointless session model");
                ProPath origin;
                CK(ProMdlOriginGet(board, origin));
                std::wstring actual = origin, prefix = folder + L"\\";
                if (_wcsnicmp(actual.c_str(), prefix.c_str(), prefix.size()))
                    throw std::runtime_error(
                        "Loaded model origin does not match this MCP model's output directory");
                if ((model.contains("inspection") || model.contains("inspection_ref")) &&
                    !request.value("readonly", false)) {
                    try {
                        verify_saved(choice_inspection(model, "inspection"), inspection());
                    } catch (const std::exception &error) {
                        throw std::runtime_error(std::string("model_reconciliation_required: ") +
                                                 error.what());
                    }
                }
            }
            ProUnitsystem us;
            ProUnititem unit;
            CK(ProMdlPrincipalunitsystemGet(board, &us));
            CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
            if (wcscmp(unit.name, L"mm"))
                throw std::runtime_error("Expected millimeter model units");
            generic_stage("loaded_blend_validation");
            report["loft_checks"]["loaded"] = verify_loft_settings(L"loaded");
            J seed_profiles;
            if (request.contains("loft_seed")) {
                if (!request.at("new").get<bool>() || request.value("readonly", false))
                    throw std::runtime_error("Loft seed binding requires a new writable part");
                seed_profiles = validate_loft_seed(request["loft_seed"]);
                suppress_seed_for_profiles(request["loft_seed"]["feature_id"], true);
            }
            for (auto op : request["operations"]) {
                ++operation_index;
                executing_operation = true;
                generic_stage("execute_" + op["op"].get<std::string>());
                log("OPERATION_INDEX=%d INPUT=%s\n", operation_index, op.dump().c_str());
                if (!request.value("readonly", false))
                    mutated = true;
                execute_operation(op);
                executing_operation = false;
            }
            generic_stage("verify_model");
            if (request.contains("loft_seed")) {
                suppress_seed_for_profiles(request["loft_seed"]["feature_id"], false);
                bind_loft_seed(request["loft_seed"], seed_profiles);
            }
            if (!request.value("readonly", false))
                CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
            J state = inspection();
            report["inspection"] = state;
            report["aliases"] = aliases;
            verify_assertions(state, request.value("assertions", J::object()));
            std::wstring saved = checkpoint;
            if (!request.value("readonly", false)) {
                generic_stage("before_save_blend_validation");
                report["loft_checks"]["before_save"] = verify_loft_settings(L"before_save");
                generic_stage("save_and_reload");
                ProPath destination;
                path(destination, folder);
                CK(ProMdlnameBackup(board, destination));
                saved = latest_model_file();
                J before = state;
                CK(ProMdlErase(board));
                board = nullptr;
                ProPath file;
                path(file, saved);
                CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
                CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
                state = inspection();
                verify_saved(before, state);
                verify_assertions(state, request.value("assertions", J::object()));
                generic_stage("after_reload_blend_validation");
                report["loft_checks"]["after_reload"] = verify_loft_settings(L"after_reload");
                report["saved_file_reloaded_and_verified"] = true;
            }
            state["inspection_source"] =
                request.value("readonly", false) ? "live_query" : "saved_reloaded";
            state["inspection_available"] = true;
            generic_stage("display_preview");
            CK(ProMdlDisplay(board));
            CK(ProMdlWindowGet(board, &win));
            CK(ProWindowCurrentSet(win));
            double a = sqrt(.5), b = sqrt(1.0 / 6), c = sqrt(1.0 / 3), d = sqrt(2.0 / 3);
            ProMatrix view = {{a, -b, c, 0}, {a, b, -c, 0}, {0, d, c, 0}, {0, 0, 0, 1}};
            CK(ProViewMatrixSet(board, nullptr, view));
            ProWindowRefit(win);
            ProWindowRepaint(win);
            ProWindowActivate(win);
            ProPath preview;
            path(preview, job + L"\\output\\preview.jpg");
            int preview_code = ProRasterFileWrite(win, PRORASTERDEPTH_24, 8, 6, PRORASTERDPI_100,
                                                  PRORASTERTYPE_JPEG, preview);
            report.update({{"success", true},
                           {"toolkit_code", 0},
                           {"inspection", state},
                           {"aliases", aliases},
                           {"part_file", utf8(saved)},
                           {"preview_code", preview_code},
                           {"preview_file", preview_code == 0 ? J(utf8(preview)) : J(nullptr)},
                           {"operations", operation_results}});
            log("BUILD_SUCCESS=1\n");
        }
    } catch (ProError error) {
        report["toolkit_code"] = error;
        report["message"] = "Toolkit call " + last_toolkit_error + " failed with code " +
                            std::to_string(error) + " during " + generic_phase;
        log("BUILD_FAILED=%d\n", error);
    } catch (const std::exception &error) {
        report["message"] = error.what();
        if (std::string(error.what()).find("model_reconciliation_required:") == 0)
            report["code"] = "model_reconciliation_required";
        report["toolkit_code"] = PRO_TK_GENERAL_ERROR;
        log("BUILD_FAILED=%s\n", error.what());
    }
    if (!report["success"].get<bool>()) {
        if (generic_phase == "callback_preflight" && !mutated)
            report["model_unchanged"] = true;
        report["failed_stage"] = generic_phase;
        report["failed_toolkit_call"] =
            last_toolkit_error.empty() ? J(nullptr) : J(last_toolkit_error);
        report["failed_operation_index"] = executing_operation ? J(operation_index) : J(nullptr);
        // An intermediate inspection is useful diagnostic evidence but is not
        // the restored/current model. Publish it separately, never as a baseline.
        if (report.contains("inspection"))
            report["failure_inspection"] = report["inspection"];
        report["inspection"] = nullptr;
        report["inspection_source"] = "unavailable";
    }
    if (!report["success"].get<bool>() && connected && mutated && !checkpoint.empty()) {
        log("PHASE=rollback_to_saved_checkpoint\n");
        ProError erased = board ? ProMdlErase(board) : PRO_TK_NO_ERROR;
        board = nullptr;
        ProPath file;
        path(file, checkpoint);
        ProError loaded =
            erased ? erased : ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board);
        if (!loaded) {
            try {
                CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
                J restored = inspection();
                const J &rollback_model = request["model"];
                verify_saved(rollback_model.contains("inspection_ref")
                                 ? read_inspection_ref(rollback_model.at("inspection_ref"))
                                 : rollback_model["inspection"],
                             restored);
                aliases = rollback_model.contains("aliases_ref")
                              ? read_inspection_ref(rollback_model.at("aliases_ref"))
                              : rollback_model["aliases"];
                report["loft_checks"]["rollback"] = verify_loft_settings(L"rollback");
                CK(ProMdlDisplay(board));
                restored["inspection_source"] = "rollback_verified";
                restored["inspection_available"] = true;
                report["inspection"] = restored;
                report["inspection_source"] = "rollback_verified";
                report["aliases"] = aliases;
                report["rollback_succeeded"] = true;
            } catch (const std::exception &e) {
                report["rollback_message"] = e.what();
            } catch (ProError e) {
                report["rollback_code"] = e;
                report["rollback_message"] = "Restored file could not be regenerated and verified "
                                             "against its saved baseline";
            }
        } else
            report["rollback_code"] = loaded;
    }
    generic_stage("disconnect");
    if (recovery_deadline)
        recovery_deadline->complete();
    split_report_inspections(request, report);
    int delivered = deliver_native_result(job, report, connected, [&]() {
        int code = ProEngineerDisconnect(&process, 15);
        log("DISCONNECT=%d\n", code);
        return code;
    });
    generic_stage("result_delivery_complete");
    fclose(board_log);
    board_log = nullptr;
    return delivered;
}
