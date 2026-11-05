// quilt_query.h — FEAT-055/S01: the single home of model quilt enumeration,
// explicit reference resolution and bounded candidate diagnostics.
// surface_trim, quilt_merge, project_curve, quilt_offset and boundary_blend
// consume these helpers instead of re-enumerating quilts themselves.
// The G5 contract (docs/development/G5-NATIVE-CONTRACT.md §4.1/§4.6 with the
// S00 revision) freezes the rules implemented here:
//   * quilt ids and surface ids never share a namespace;
//   * a reference must identify exactly one quilt — zero or several is
//     rejected with a bounded candidate list, never auto-picked;
//   * a runtime reference failure is a job failure with rollback, not a
//     schema rejection, so the message only guides, it does not guess.
//
// This header is included by generic.cpp after surface_measure.h's
// dependencies, feature(), collect_geom_ids(), selection() and J are visible;
// it defines no entry point.
#pragma once

#include "surface_measure.h"

#include <ProFeature.h>
#include <ProQuilt.h>
#include <ProSelection.h>
#include <ProSolid.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>

// Bounded diagnostics (§0.1 R3): a candidate list never grows without limit.
static constexpr int QUILT_CANDIDATE_SAMPLE_LIMIT = 20;

struct QuiltFaceAccumulator {
    J *surface_ids = nullptr;
    int face_count = 0;
    ProVector bb_min{std::numeric_limits<double>::max(), std::numeric_limits<double>::max(),
                     std::numeric_limits<double>::max()};
    ProVector bb_max{-std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(),
                     -std::numeric_limits<double>::max()};
    bool bbox_ok = true;
    ProError bbox_code = PRO_TK_NO_ERROR;
};
static ProError quilt_face_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *acc = (QuiltFaceAccumulator *)data;
    if (status) {
        acc->bbox_ok = false;
        acc->bbox_code = status;
        return PRO_TK_NO_ERROR;
    }
    acc->face_count++;
    int id = -1;
    ProSurfaceIdGet(surface, &id);
    acc->surface_ids->push_back(id);
    // Per-surface axis-aligned bounds from the real surface data; the quilt
    // bounds are their union (not a parametric guess).
    ProGeomitemdata *surface_data = nullptr;
    if (ProSurfaceDataGet(surface, &surface_data) || !surface_data ||
        !surface_data->data.p_surface_data) {
        acc->bbox_ok = false;
        if (!acc->bbox_code)
            acc->bbox_code = PRO_TK_GENERAL_ERROR;
        return PRO_TK_NO_ERROR;
    }
    for (int i = 0; i < 3; i++) {
        acc->bb_min[i] = std::min(acc->bb_min[i], surface_data->data.p_surface_data->xyz_min[i]);
        acc->bb_max[i] = std::max(acc->bb_max[i], surface_data->data.p_surface_data->xyz_max[i]);
    }
    ProGeomitemdataFree(&surface_data);
    return PRO_TK_NO_ERROR;
}

// One quilt record for inspection.quilts. face_count/surface_ids/area/closed/
// bbox all carry their own status; unknown stays null, never zero.
static J quilt_record(ProSolid solid, int quilt_id, const J &feature_ids,
                      const InspectionLengthUnits &units, const MillimeterScale &scale) {
    ProQuilt quilt = nullptr;
    ProError init_code = ProQuiltInit(solid, quilt_id, &quilt);
    J surface_ids = J::array();
    QuiltFaceAccumulator faces;
    faces.surface_ids = &surface_ids;
    ProError visit_code =
        init_code ? PRO_TK_BAD_INPUTS : ProQuiltSurfaceVisit(quilt, quilt_face_cb, nullptr, &faces);
    MeasurementOutcome area = init_code ? MeasurementOutcome{} : quilt_area_native(quilt);
    MeasurementOutcome closed = {false, init_code ? init_code : PRO_TK_NO_ERROR,
                                 init_code ? "quilt_init_failed" : nullptr, 0.0};
    if (!init_code)
        closed = quilt_closed_native(quilt);
    J bbox_mm = nullptr;
    if (visit_code == PRO_TK_NO_ERROR && faces.bbox_ok && faces.face_count > 0 && scale.known) {
        bbox_mm = {xyz_json(faces.bb_min, scale), xyz_json(faces.bb_max, scale)};
    }
    J bbox_status = measurement_status_json(
        {visit_code == PRO_TK_NO_ERROR && faces.bbox_ok && faces.face_count > 0,
         visit_code ? visit_code : faces.bbox_code,
         visit_code              ? "quilt_surface_visit_failed"
         : !faces.bbox_ok        ? "surface_data_get_failed"
         : faces.face_count == 0 ? "quilt_has_no_surfaces"
                                 : (scale.known ? nullptr : "unit_scale_unknown")},
        units, scale);
    // Live 2026-11-04: an open quilt must report false, not null. The decision
    // lives in surface_measure.h so trim and merge cannot drift. The value is
    // assigned branch by branch: `cond ? false : nullptr` made MSVC fold the
    // bool into the null pointer constant and serialized null either way.
    bool is_open = quilt_closed_is_open(closed);
    J closed_json = nullptr;
    if (closed.available)
        closed_json = true;
    else if (is_open)
        closed_json = false;
    J record = {{"quilt_id", quilt_id},
                {"feature_ids", feature_ids},
                {"face_count", visit_code ? nullptr : J(faces.face_count)},
                {"surface_ids", visit_code ? nullptr : J(surface_ids)},
                {"surfaces_visit_code", visit_code},
                {"closed", closed_json},
                {"closed_status", measurement_status_json(closed, units, scale)},
                {"bbox_mm", bbox_mm},
                {"bbox_status", bbox_status}};
    J area_json = area_mm2_json(area, units, scale);
    record["area_mm2"] = area_json["area_mm2"];
    record["area_status"] = area_json["area_status"];
    return record;
}

struct QuiltMembership {
    std::map<int, J> features_of; // quilt id -> owning feature ids (ordered)
    bool visit_failed = false;
    ProError visit_code = PRO_TK_NO_ERROR;
};
struct QuiltFeatureScan {
    QuiltMembership *membership;
    int feature_id;
};
static ProError quilt_member_cb(ProGeomitem *item, ProError status, ProAppData data) {
    auto *scan = (QuiltFeatureScan *)data;
    if (status || item->type != PRO_QUILT)
        return PRO_TK_NO_ERROR;
    J &owners = scan->membership->features_of[item->id];
    bool present = false;
    for (const auto &owner : owners)
        present = present || owner == scan->feature_id;
    if (!present)
        owners.push_back(scan->feature_id);
    return PRO_TK_NO_ERROR;
}
static ProError quilt_membership_cb(ProFeature *f, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    QuiltFeatureScan scan{(QuiltMembership *)data, f->id};
    ProError code = ProFeatureGeomitemVisit(f, PRO_QUILT, quilt_member_cb, nullptr, &scan);
    if (code) {
        auto *membership = (QuiltMembership *)data;
        membership->visit_failed = true;
        membership->visit_code = code;
    }
    return PRO_TK_NO_ERROR;
}

// Every quilt in the part, with real membership, face and measurement data.
// Assemblies never call this; the inspection result carries null there.
static J collect_model_quilts(ProSolid solid, const InspectionLengthUnits &units,
                              const MillimeterScale &scale) {
    QuiltMembership membership;
    ProError visit_code = ProSolidFeatVisit(solid, quilt_membership_cb, nullptr, &membership);
    J records = J::array();
    for (const auto &[quilt_id, owners] : membership.features_of)
        records.push_back(quilt_record(solid, quilt_id, owners, units, scale));
    return {{"records", records},
            {"visit_failed", membership.visit_failed || visit_code != PRO_TK_NO_ERROR},
            {"visit_code", visit_code ? visit_code : membership.visit_code}};
}

// Bounded diagnostic list (§0.1 R3). Consumed only inside rejected-reference
// error messages; never used to auto-pick a quilt.
static J quilt_reference_candidates(ProSolid solid, const InspectionLengthUnits &units,
                                    const MillimeterScale &scale) {
    J result = collect_model_quilts(solid, units, scale);
    J candidates = J::array();
    for (const auto &record : result["records"]) {
        if ((int)candidates.size() >= QUILT_CANDIDATE_SAMPLE_LIMIT)
            break;
        candidates.push_back({{"quilt_id", record["quilt_id"]},
                              {"feature_ids", record["feature_ids"]},
                              {"face_count", record["face_count"]},
                              {"area_mm2", record["area_mm2"]}});
    }
    return candidates;
}

static std::string quilt_candidates_hint(ProSolid solid, const InspectionLengthUnits &units,
                                         const MillimeterScale &scale) {
    J candidates = quilt_reference_candidates(solid, units, scale);
    return " Inspect the model and use {kind:\"quilt\",id:<quilt_id>}; known quilts: " +
           candidates.dump();
}

// The geometry id behind a resolved quilt selection. Every consumer that needs
// to re-measure or record a quilt id uses this instead of keeping its own
// ProSelectionModelitemGet copy.
static int quilt_selection_id(ProSelection selection) {
    ProModelitem item;
    CK(ProSelectionModelitemGet(selection, &item));
    return item.id;
}

// §4.1 quilt references, S00 revision. kind:"quilt" carries an explicit quilt
// geometry id from inspection.quilts; kind:"quilt_feature" resolves through a
// feature label and must identify exactly one PRO_QUILT geometry item.
static ProSelection resolve_quilt_reference(const J &r, ProSolid solid,
                                            const InspectionLengthUnits &units,
                                            const MillimeterScale &scale) {
    std::string kind = r.at("kind");
    if (kind == "quilt") {
        const J &raw_id = r.at("id");
        if (!raw_id.is_number_integer() || raw_id < 0 || raw_id > 2147483647)
            throw std::runtime_error("Quilt reference id must be a nonnegative 32-bit integer");
        int id = raw_id.get<int>();
        ProQuilt quilt = nullptr;
        if (ProQuiltInit(solid, id, &quilt))
            throw std::runtime_error("Quilt geometry id not found: " + std::to_string(id) +
                                     quilt_candidates_hint(solid, units, scale));
        return selection(id, PRO_QUILT);
    }
    ProFeature f = feature(r.at("label"));
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&f, PRO_QUILT, collect_geom_ids, nullptr, &ids));
    if (ids.size() == 0)
        throw std::runtime_error(
            "Feature contains no quilt geometry item; a trim result is not always a usable "
            "quilt feature" +
            quilt_candidates_hint(solid, units, scale));
    if (ids.size() > 1)
        throw std::runtime_error("Feature reference identifies " + std::to_string((int)ids.size()) +
                                 " quilts; name the intended one explicitly" +
                                 quilt_candidates_hint(solid, units, scale));
    return selection(ids[0]["id"], PRO_QUILT);
}
