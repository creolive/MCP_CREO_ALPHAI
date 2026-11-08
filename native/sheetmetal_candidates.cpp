#include "sheetmetal_target_guard.h"
// DEV-078: offline candidate trees. Public capability admission remains unavailable.
#if __has_include(<ProSmtCornerRelief.h>) && __has_include(<ProSmtPunchQuilt.h>)
#include <ProSmtCornerRelief.h>
#include <ProSmtPunchQuilt.h>
#define MECHDOG_HAS_SMT_CANDIDATE_HEADERS 1
#endif

#ifdef MECHDOG_HAS_SMT_CANDIDATE_HEADERS
struct SmtCandidateResources {
    ProElement tree = nullptr;
    std::vector<ProSelection> selections;
    ~SmtCandidateResources() {
        for (auto &selection : selections)
            if (selection)
                ProSelectionFree(&selection);
        if (tree)
            ProElementFree(&tree);
    }
    ProSelection select(const J &reference) {
        ProSelection selected = resolve(reference);
        selections.push_back(selected);
        return selected;
    }
};

struct SmtCandidateTarget {
    ProSolidBody body = {};
    double scale = 0;
};

static ProError smt_candidate_count_surface(ProSurface, ProError status, ProAppData data) {
    if (status != PRO_TK_NO_ERROR)
        return status;
    ++*static_cast<int *>(data);
    return PRO_TK_NO_ERROR;
}

static SmtCandidateTarget smt_candidate_target() {
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    if (!scale.known || !std::isfinite(scale.scale) || scale.scale <= 0)
        throw std::runtime_error("Sheetmetal candidate requires a known model length unit");
#if defined(MECHDOG_HAS_ProSmtBodyThicknessValueGet) &&                                            \
    !defined(MECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API)
    struct BodyArray {
        ProSolidBody *items = nullptr;
        ~BodyArray() {
            if (items)
                ProArrayFree((ProArray *)&items);
        }
    } bodies;
    CK(ProSolidBodiesCollect((ProSolid)board, &bodies.items));
    int count = 0;
    CK(ProArraySizeGet((ProArray)bodies.items, &count));
    SmtCandidateTarget target;
    target.scale = scale.scale;
    std::vector<sheetmetal_target::BodyCandidate> candidates;
    for (int index = 0; index < count; ++index) {
        ProSolidBody &body = bodies.items[index];
        candidates.push_back({body.id, false});
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&body, &state));
        // Empty stock/default bodies (including NO_GEOMETRY) do not select the target.
        if (state != PRO_BODY_STATE_ACTIVE)
            continue;
        ProBoolean construction = PRO_B_FALSE, sheetmetal = PRO_B_FALSE;
        CK(ProSolidBodyIsConstruction(&body, &construction));
        if (construction)
            continue;
        CK(ProSolidBodyIsSheetmetal(&body, &sheetmetal));
        if (!sheetmetal)
            continue;
        int surfaces = 0;
        ProError code = ProSolidBodySurfaceVisit(&body, smt_candidate_count_surface, &surfaces);
        if (code != PRO_TK_NO_ERROR && code != PRO_TK_E_NOT_FOUND)
            CK(code);
        if (!surfaces)
            continue;
        // Only validate that material has a usable outline; never derive gauge from its box.
        ProOutline outline = {};
        CK(ProSolidBodyOutlineGet(&body, outline));
        for (int axis = 0; axis < 3; ++axis)
            if (!std::isfinite(outline[0][axis]) || !std::isfinite(outline[1][axis]) ||
                outline[1][axis] <= outline[0][axis])
                throw std::runtime_error("Sheetmetal material body has an invalid outline");
        candidates.back().material = true;
    }
    int selected_id = sheetmetal_target::unique_material_body(candidates, true);
    for (int index = 0; index < count; ++index)
        if (bodies.items[index].id == selected_id)
            target.body = bodies.items[index];
    double thickness = 0;
    ProError gauge_code = ProSmtBodyThicknessValueGet(&target.body, &thickness);
    CK(gauge_code);
    sheetmetal_target::require_body_gauge(true, gauge_code == PRO_TK_NO_ERROR, thickness);
    return target;
#else
    sheetmetal_target::require_body_gauge(false, false, 0);
    throw std::runtime_error("Unreachable missing body gauge API");
#endif
}

static void smt_candidate_body_options(ProElement root, const ProSolidBody &body,
                                       SmtCandidateResources &resources) {
    ProElement options = node(root, PRO_E_BODY);
    integer(options, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
    ProSelection selected = resources.select({{"kind", "body"}, {"id", body.id}});
    ref(options, PRO_E_BODY_SELECT, selected);
}

static void smt_candidate_surface(ProSelection selected, ProSrftype expected,
                                  const ProSolidBody &target) {
    ProModelitem item;
    CK(ProSelectionModelitemGet(selected, &item));
    if (item.owner != board || item.type != PRO_SURFACE)
        throw std::runtime_error("Sheetmetal candidate surface must belong to the current model");
    ProSolidBody owner;
    CK(ProGeomitemBodyGet(&item, &owner));
    sheetmetal_target::require_membership(target.id, owner.id, owner.owner == target.owner, true);
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, item.id, &surface));
    ProSrftype actual;
    CK(ProSurfaceTypeGet(surface, &actual));
    if (actual != expected)
        throw std::runtime_error("Corner relief requires a flat plane and two cylindrical bends");
}

static int smt_candidate_id(const J &reference, const char *kind) {
    if (!reference.is_object() || reference.size() != 2 || reference.value("kind", "") != kind ||
        !reference.contains("id") || !reference["id"].is_number_integer() || reference["id"] < 0 ||
        reference["id"] > 2147483647)
        throw std::runtime_error(
            "Sheetmetal candidate requires an exact typed 32-bit geometry reference");
    return reference["id"].get<int>();
}
#endif

static void generic_sheetmetal_corner_relief(const J &op) {
#ifndef MECHDOG_HAS_SMT_CANDIDATE_HEADERS
    throw std::runtime_error(
        "sheetmetal_corner_relief unsupported: SDK candidate headers unavailable");
#else
    SmtCandidateTarget target = smt_candidate_target();
    double scale = target.scale;
    const J &bends = op.at("bends");
    if (!bends.is_array() || bends.size() != 2)
        throw std::runtime_error("Corner relief requires exactly two bends");
    int flat_id = smt_candidate_id(op.at("flat"), "surface");
    int first = smt_candidate_id(bends[0], "surface");
    int second = smt_candidate_id(bends[1], "surface");
    if (flat_id == first || flat_id == second || first == second)
        throw std::runtime_error("Corner relief requires three distinct surfaces");
    for (const char *key : {"width", "depth"})
        if (!op.at(key).is_number() || !std::isfinite(op.at(key).get<double>()) ||
            op.at(key).get<double>() <= 0)
            throw std::runtime_error(
                "Corner relief dimensions must be finite positive millimetres");
    std::string state = op.value("state", "formed");
    if (state != "formed" && state != "unbent")
        throw std::runtime_error("Corner relief state must be formed or unbent");
    SmtCandidateResources resources;
    ProSelection flat = resources.select(op.at("flat"));
    ProSelection bend1 = resources.select(bends[0]);
    ProSelection bend2 = resources.select(bends[1]);
    smt_candidate_surface(flat, PRO_SRF_PLANE, target.body);
    smt_candidate_surface(bend1, PRO_SRF_CYL, target.body);
    smt_candidate_surface(bend2, PRO_SRF_CYL, target.body);
    ProElement root = resources.tree = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_SMT_CRN_REL);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement reliefs = node(root, PRO_E_CORNER_RELIEFS);
    integer(reliefs, PRO_E_CORNER_RELIEFS_CR_STATE,
            state == "formed" ? PRO_CRN_REL_CR_IN_FORMED : PRO_CRN_REL_CR_IN_UNBEND_ONLY);
    ProElement set = node(node(reliefs, PRO_E_CORNER_RELIEFS_ARR), PRO_E_CORNER_RELIEF_SET);
    ProElement references =
        node(node(set, PRO_E_CORNER_RELIEF_REF_ARR), PRO_E_CORNER_RELIEF_REF_SET);
    integer(references, PRO_E_CORNER_RELIEF_REF_TYPE, PRO_CRN_REL_3_SURFACES);
    ref(references, PRO_E_CORNER_RELIEF_REF_FLAT, flat);
    ref(references, PRO_E_CORNER_RELIEF_REF_BND_1, bend1);
    ref(references, PRO_E_CORNER_RELIEF_REF_BND_2, bend2);
    ProElement definition = node(node(set, PRO_E_CORNER_RELIEF_DEFINE), PRO_E_SMT_CORNER_RELIEF);
    integer(definition, PRO_E_SMT_CORNER_RELIEF_TYPE, PRO_CORNER_RELIEF_RECTANGULAR);
    ProElement width = node(definition, PRO_E_SMT_CORNER_RELIEF_WIDTH);
    integer(width, PRO_E_SMT_CORNER_RELIEF_WIDTH_TYPE, PRO_DIM_ENTER);
    real(width, PRO_E_SMT_CORNER_RELIEF_WIDTH_VAL, op.at("width").get<double>() / scale);
    ProElement depth = node(definition, PRO_E_SMT_CORNER_RELIEF_DEPTH);
    integer(depth, PRO_E_SMT_CORNER_RELIEF_DEPTH_TYPE, PRO_CRN_RLF_DEPTH_BLIND);
    real(depth, PRO_E_SMT_CORNER_RELIEF_DEPTH_VAL, op.at("depth").get<double>() / scale);
    integer(node(definition, PRO_E_SMT_CORNER_RELIEF_ROTATE), PRO_E_SMT_CORNER_RELIEF_ROTATE_ADD,
            PRO_B_FALSE);
    integer(node(definition, PRO_E_SMT_CORNER_RELIEF_OFFSET), PRO_E_SMT_CORNER_RELIEF_OFFSET_ADD,
            PRO_B_FALSE);
    integer(definition, PRO_E_CORNER_RELIEFS_DIM_SCHEME, PRO_CRN_REL_DIM_REF_BEND_AXES_XSECTION);
    integer(definition, PRO_E_CORNER_RELIEF_ORIENT_REF, PRO_CRN_REL_INT_BEND_EDGS_N_LINES);
    smt_candidate_body_options(root, target.body, resources);
    // A real rip is an official geometric precondition, checked by Creo regeneration.
    // No caller assertion can prove it; this candidate stays unavailable until live acceptance.
    ProFeature feature = create(root);
    remember(op, feature);
#endif
}

static void generic_sheetmetal_quilt_form(const J &op) {
#ifndef MECHDOG_HAS_SMT_CANDIDATE_HEADERS
    throw std::runtime_error(
        "sheetmetal_quilt_form unsupported: SDK candidate headers unavailable");
#else
    SmtCandidateTarget target = smt_candidate_target();
    const J &quilt_ref = op.at("quilt");
    if (quilt_ref.value("kind", "") == "quilt")
        (void)smt_candidate_id(quilt_ref, "quilt");
    else if (!quilt_ref.is_object() || quilt_ref.size() != 2 ||
             quilt_ref.value("kind", "") != "quilt_feature" || !quilt_ref.contains("label") ||
             !quilt_ref["label"].is_string())
        throw std::runtime_error("Quilt form requires an exact quilt ID or quilt_feature label");
    std::string side = op.value("side", "face");
    std::string material = op.value("material_side", "outside");
    if ((side != "face" && side != "offset") || (material != "inside" && material != "outside"))
        throw std::runtime_error("Quilt form side or material_side is invalid");
    for (const char *key : {"keep_quilt", "trim_sides"})
        if (op.contains(key) && !op.at(key).is_boolean())
            throw std::runtime_error("Quilt form flags require raw booleans");
    SmtCandidateResources resources;
    ProSelection quilt = resources.select(quilt_ref);
    ProModelitem item;
    CK(ProSelectionModelitemGet(quilt, &item));
    if (item.owner != board || item.type != PRO_QUILT)
        throw std::runtime_error("Quilt form reference must be a quilt in the current model");
    ProElement root = resources.tree = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_PUNCH_QUILT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ref(root, PRO_E_FORM_PUNCH_QUILT, quilt);
    integer(root, PRO_E_FORM_PUNCH_SIDE, side == "face" ? PRO_SMT_SURF_FACE : PRO_SMT_SURF_OFFSET);
    integer(root, PRO_E_FORM_PUNCH_MATERIAL_SIDE,
            material == "inside" ? PRO_SMT_PUNCH_MAT_INSIDE : PRO_SMT_PUNCH_MAT_OUTSIDE);
    integer(root, PRO_E_FORM_PUNCH_HIDE_QUILT,
            op.value("keep_quilt", true) ? PRO_SMT_PUNCH_KEEP_ORIGINAL
                                         : PRO_SMT_PUNCH_HIDE_ORIGINAL);
    integer(root, PRO_E_SMT_TRIM_FORM_SIDES,
            op.value("trim_sides", false) ? PRO_B_TRUE : PRO_B_FALSE);
    integer(node(root, PRO_E_SMT_FILLET_INTERSECT), PRO_E_SMT_FILLET_RADIUS_USEFLAG, PRO_B_FALSE);
    integer(node(root, PRO_E_SMT_FILLET_QUILT), PRO_E_SMT_FILLET_RADIUS_USEFLAG, PRO_B_FALSE);
    smt_candidate_body_options(root, target.body, resources);
    ProFeature feature = create(root);
    remember(op, feature);
#endif
}
