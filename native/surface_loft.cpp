// surface_loft.cpp — FEAT-009 (H02): the minimal two-section boundary blend.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.1 (candidate tree), §3.1
// (first-release boundary), §4.4.2 (surface_area_mm2/status, surface_type,
// sections) and §6.2 (this entry point). The tree comes from Probbl.h, the only
// documented boundary-blend tree on this SDK. The 2026-11-01 probe added
// PRO_E_EXT_SURF_CUT_SOLID_TYPE/PRO_E_BNBLN_TAN_COND* to the §2.1 skeleton and
// the feature stayed PRO_FEAT_UNREGENERATED; §2.1 explicitly forbids both, so
// this implementation builds the bare skeleton first and completes it from the
// extracted tree instead of guessing element values.
//
// This file is included by generic.cpp after the shared element-tree,
// selection, quilt and measurement helpers are visible; it defines no entry
// point of its own beyond generic_surface_loft.
#include <Probbl.h>

// Bounded element-tree readback. The extracted tree is the only honest source
// of the kernel's own defaults, so it is published as evidence instead of being
// discarded when regeneration fails.
static constexpr int SURFACE_LOFT_TREE_SAMPLE_LIMIT = 160;

static J loft_element_json(ProElement element, int depth, int &budget) {
    J record = J::object();
    if (!element || budget <= 0)
        return record;
    budget--;
    ProElemId id = 0;
    if (!ProElementIdGet(element, &id))
        record["id"] = (int)id;
    ProBoolean compound = PRO_B_FALSE, array = PRO_B_FALSE;
    if (!ProElementIsCompound(element, nullptr, &compound))
        record["compound"] = compound == PRO_B_TRUE;
    if (!ProElementIsArray(element, nullptr, &array))
        record["array"] = array == PRO_B_TRUE;
    if (compound != PRO_B_TRUE && array != PRO_B_TRUE) {
        ProValueDataType type = PRO_VALUE_TYPE_INT;
        ProError type_code = ProElementValuetypeGet(element, &type);
        record["value_type"] = (int)type;
        record["value_code"] = (int)type_code;
        if (!type_code) {
            if (type == PRO_VALUE_TYPE_INT) {
                int value = 0;
                if (!ProElementIntegerGet(element, nullptr, &value))
                    record["integer"] = value;
            } else if (type == PRO_VALUE_TYPE_DOUBLE) {
                double value = 0.0;
                if (!ProElementDoubleGet(element, nullptr, &value))
                    record["double"] = value;
            } else if (type == PRO_VALUE_TYPE_BOOLEAN) {
                ProBoolean value = PRO_B_FALSE;
                if (!ProElementBooleanGet(element, nullptr, &value))
                    record["boolean"] = value == PRO_B_TRUE;
            } else if (type == PRO_VALUE_TYPE_WSTRING) {
                wchar_t *value = nullptr;
                if (!ProElementWstringGet(element, nullptr, &value) && value) {
                    record["string"] = utf8(std::wstring(value));
                    ProWstringFree(value);
                }
            } else if (type == PRO_VALUE_TYPE_SELECTION) {
                ProReference *refs = nullptr;
                if (!ProElementReferencesGet(element, nullptr, &refs)) {
                    int count = 0;
                    if (!ProArraySizeGet((ProArray)refs, &count))
                        record["reference_count"] = count;
                }
                if (refs)
                    ProArrayFree((ProArray *)&refs);
            }
        }
    }
    if (depth < 12 && budget > 0) {
        ProElement *children = nullptr;
        ProArrayAlloc(0, sizeof(ProElement), 1, (ProArray *)&children);
        ProError code = array == PRO_B_TRUE ? ProElementArrayGet(element, nullptr, &children)
                                            : ProElementChildrenGet(element, nullptr, &children);
        int count = 0;
        if (!code)
            ProArraySizeGet((ProArray)children, &count);
        if (count > 0) {
            J items = J::array();
            for (int index = 0; index < count && budget > 0; index++)
                items.push_back(loft_element_json(children[index], depth + 1, budget));
            record["children"] = items;
        }
        if (children)
            ProArrayFree((ProArray *)&children);
    }
    return record;
}

static J loft_tree_json(ProElement root) {
    int budget = SURFACE_LOFT_TREE_SAMPLE_LIMIT;
    return {{"limit", SURFACE_LOFT_TREE_SAMPLE_LIMIT},
            {"truncated", false},
            {"root", loft_element_json(root, 0, budget)},
            {"elements_read", SURFACE_LOFT_TREE_SAMPLE_LIMIT - budget}};
}

// One section = one sketch feature holding exactly one non-composite curve.
// This is the same admission blend_create.cpp already applies to a solid Blend;
// a composite curve, zero curves or several curves are refused instead of
// picking one.
static int surface_loft_curve(const J &reference, const char *role) {
    int id = feature_id(reference);
    ProFeature sketch;
    CK(ProFeatureInit((ProSolid)board, id, &sketch));
    ProFeattype type;
    CK(ProFeatureTypeGet(&sketch, &type));
    if (type != PRO_FEAT_CURVE)
        throw std::runtime_error(std::string("surface_loft ") + role +
                                 " section is not an independent sketch (feature " +
                                 std::to_string(id) + ")");
    J items = J::array();
    CK(ProFeatureGeomitemVisit(&sketch, PRO_CURVE, collect_geom_ids, nullptr, &items));
    std::vector<int> simple;
    for (auto item : items) {
        ProCurve curve = nullptr;
        if (ProCurveInit((ProSolid)board, item["id"].get<int>(), &curve))
            continue;
        ProEnttype kind;
        if (ProCurveTypeGet(curve, &kind) == PRO_TK_NO_ERROR && kind != PRO_ENT_CMP_CRV)
            simple.push_back(item["id"].get<int>());
    }
    if (simple.size() != 1)
        throw std::runtime_error(std::string("surface_loft ") + role +
                                 " section must own exactly one non-composite curve; feature " +
                                 std::to_string(id) + " owns " +
                                 std::to_string((int)simple.size()));
    return simple[0];
}

static void generic_surface_loft(const J &op) {
    const J &sections = op.at("sections");
    if (sections.size() != 2)
        throw std::runtime_error("surface_loft requires exactly two sections");
    if (op.value("interpolation", "straight") != "straight")
        throw std::runtime_error("surface_loft supports interpolation 'straight' only");

    int first_curve = surface_loft_curve(sections[0], "first");
    int second_curve = surface_loft_curve(sections[1], "second");
    if (first_curve == second_curve)
        throw std::runtime_error("surface_loft sections must be two different curves");

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    integer(root, PRO_E_DTM_SRF_TYPE, PRO_E_DTM_SRF_TYPE_BND_BLEND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProElement curves = node(root, PRO_E_BNBLN_CURVES);
    ProElement direction = node(curves, PRO_E_BNBLN_1DIR);
    ProElement holders = node(direction, PRO_E_BNBLN_DIR_CURVES);
    for (int curve_id : {first_curve, second_curve}) {
        ProElement holder = node(holders, PRO_E_STD_CHAIN_HOLDER);
        curve_collection(node(holder, PRO_E_STD_CURVE_COLLECTION_APPL),
                         J::array({{{"kind", "curve"}, {"id", curve_id}}}));
    }

    J details = {{"op", "surface_loft"},
                 {"sections", sections},
                 {"section_curve_ids", J::array({first_curve, second_curve})},
                 {"interpolation", "straight"},
                 {"route", "probbl_boundary_blend"}};

    // INCOMPLETE lets the kernel fill the defaults it owns; the extracted tree
    // is then the completed tree for ProFeatureWithoptionsRedefine. A failed
    // create keeps its element-error list in the receipt instead of only in
    // native.log.
    ProModelitem item;
    CK(ProMdlToModelitem(board, &item));
    ProSelection solid_selection = nullptr;
    CK(ProSelectionAlloc(nullptr, &item, &solid_selection));
    ProFeatureCreateOptions *options = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&options));
    options[0] = PRO_FEAT_CR_INCOMPLETE_FEAT;
    ProFeature feature = {};
    ProErrorlist element_errors = {};
    ProError created = ProFeatureWithoptionsCreate(solid_selection, root, options,
                                                   PRO_REGEN_NO_FLAGS, &feature, &element_errors);
    errors(element_errors);
    ProArrayFree((ProArray *)&options);
    ProSelectionFree(&solid_selection);
    details["create_code"] = (int)created;
    details["create_element_errors"] = {{"total", element_errors.error_number},
                                        {"sample", J::array({})}};
    J create_sample = J::array();
    for (int index = 0; index < element_errors.error_number && index < FEATURE_ERROR_SAMPLE_LIMIT;
         index++)
        create_sample.push_back({{"element", element_errors.error_list[index].err_item_id},
                                 {"type", element_errors.error_list[index].err_item_type},
                                 {"error", element_errors.error_list[index].error}});
    details["create_element_errors"]["sample"] = create_sample;
    if (created != PRO_TK_NO_ERROR) {
        last_feature_error_report =
            feature_error_report("ProFeatureWithoptionsCreate", created, "surface_loft_create");
        stage_operation_result(details);
        throw std::runtime_error("surface_loft boundary blend create failed (code " +
                                 std::to_string((int)created) +
                                 ", first_curve=" + std::to_string(first_curve) +
                                 ", second_curve=" + std::to_string(second_curve) + ")");
    }
    ProElementFree(&root);

    ProElement extracted = nullptr;
    ProError extract_code =
        ProFeatureElemtreeExtract(&feature, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &extracted);
    details["extract_code"] = (int)extract_code;
    if (extract_code || !extracted) {
        stage_operation_result(details);
        throw std::runtime_error("surface_loft cannot extract the created feature tree (code " +
                                 std::to_string((int)extract_code) + ")");
    }
    // The tree is logged in full and kept in the receipt only when the
    // regeneration fails; a successful job must not carry a 30 KB element tree
    // that inflates every poll of its result.
    J tree_json = loft_tree_json(extracted);
    log("SURFACE_LOFT_TREE=%s\n", tree_json.dump().c_str());
    details["tree_elements_read"] = tree_json["elements_read"];

    // The extracted tree is completed by the kernel's own defaults; redefining
    // with it is the regeneration the incomplete create skipped. A failure here
    // keeps the tree sample so the missing element is visible.
    try {
        redefine(&feature, extracted);
    } catch (...) {
        details["extracted_tree"] = tree_json;
        stage_operation_result(details);
        CK(ProFeatureElemtreeFree(&feature, extracted));
        throw;
    }
    CK(ProFeatureElemtreeFree(&feature, extracted));

    ProFeatStatus status = PRO_FEAT_ACTIVE;
    CK(ProFeatureStatusGet(&feature, &status));
    details["feature_id"] = (int)feature.id;
    details["feature_status"] = (int)status;
    ProFeattype feature_type = 0;
    CK(ProFeatureTypeGet(&feature, &feature_type));
    details["feature_type"] = (int)feature_type;

    J quilts = J::array();
    ProError quilt_visit =
        ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &quilts);
    details["quilt_visit_code"] = (int)quilt_visit;
    details["quilt_count"] = (int)quilts.size();
    details["quilt_ids"] = quilts;
    int quilt_id = quilts.size() == 1 ? quilts[0]["id"].get<int>() : -1;
    details["quilt_id"] = quilt_id < 0 ? J(nullptr) : J(quilt_id);

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    MeasurementOutcome area, closed;
    if (quilt_id >= 0) {
        ProQuilt quilt = nullptr;
        ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
        details["quilt_init_code"] = (int)init_code;
        if (!init_code) {
            area = quilt_area_native(quilt);
            closed = quilt_closed_native(quilt);
        } else {
            area.reason = "quilt_init_failed";
            area.query_code = init_code;
            closed.reason = "quilt_init_failed";
            closed.query_code = init_code;
        }
    } else {
        area.reason = "quilt_geometry_missing";
        closed.reason = "quilt_geometry_missing";
    }
    details.update(area_fields_json(area, units, scale, "surface_area_mm2", "surface_area_status"));
    const char *closure = quilt_closed_is_open(closed) ? "open"
                          : closed.available           ? "closed"
                                                       : "unknown";
    details["quilt_closed_native"] = closure;
    details["closure"] = {{"available", closed.available},
                          {"query_code", (int)closed.query_code},
                          {"reason", closed.reason ? J(closed.reason) : J(nullptr)}};
    // FEAT-039/H04: the quilt's own faces are a group too, so the boundary
    // measurement is published beside the boolean closure probe. A single
    // boundary-blend quilt reports its exposed edges; the seam fields stay
    // null with a reason instead of a fabricated zero.
    details["surface_group"] =
        quilt_id >= 0 ? surface_group_receipt({quilt_id}, 0.01, 1.0) : J(nullptr);
    details["has_solid"] = inspection(false)["has_solid"];
    details["surface_type"] =
        feature_type == PRO_FEAT_DATUM_SURF ? J("datum_surface") : J("unknown");
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE) {
        details["extracted_tree"] = tree_json;
        stage_operation_result(details);
        last_feature_error_report = feature_error_report("ProFeatureStatusGet", (ProError)status,
                                                         "surface_loft_regeneration");
        throw std::runtime_error(
            "surface_loft boundary blend regeneration failed (feature_status=" +
            std::to_string((int)status) + ", feature_id=" + std::to_string((int)feature.id) +
            ", quilt_count=" + std::to_string((int)quilts.size()) +
            "); the created tree did not produce a regenerated surface");
    }
    if (feature_type != PRO_FEAT_DATUM_SURF)
        throw std::runtime_error("surface_loft produced feature type " +
                                 std::to_string((int)feature_type) + " instead of a datum surface");
    if (quilts.size() != 1)
        throw std::runtime_error("surface_loft produced " + std::to_string((int)quilts.size()) +
                                 " quilt geometry items (visit code " +
                                 std::to_string((int)quilt_visit) +
                                 "); exactly one boundary-blend surface is required");
    if (!area.available)
        throw std::runtime_error(std::string("surface_loft surface is not measurable") +
                                 (area.reason ? ": " : "") + (area.reason ? area.reason : ""));
    if (details["has_solid"].get<bool>())
        throw std::runtime_error("surface_loft created solid material; a surface loft must not");
    if (!quilt_closed_is_open(closed))
        throw std::runtime_error(
            "surface_loft result must be an open quilt; ProQuiltVolumeEval reported " +
            std::string(closure) + " (code " + std::to_string((int)closed.query_code) + ")");

    remember(
        op, feature,
        {{"quilt_id", quilt_id}, {"section_curve_ids", J::array({first_curve, second_curve})}});
}
