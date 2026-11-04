// FEAT-058: native rectangular unattached planar wall (the sheetmetal primary
// wall), plus its in-place resize.
//
// Basis (measured 2026-11-04 on Creo 12.4.0.0, docs/work-items/FEAT-058.md):
//   * the primary wall is the Fill feature tree, not PRO_FEAT_WALL:
//     PRO_E_FEATURE_TYPE = PRO_FEAT_DATUM_SURF, PRO_E_FEATURE_FORM = PRO_FLAT,
//     PRO_E_STD_SECTION = PRO_E_SEC_USE_SKETCH, plus the sheetmetal branch
//     PRO_E_IS_UNATTACHED_WALL, PRO_E_STD_DIRECTION,
//     PRO_E_STD_SMT_SWAP_DRV_SIDE,
//     PRO_E_BODY{PRO_E_BODY_USE = PRO_BODY_USE_NEW} and
//     PRO_E_SMT_NEW_BODY_LINKED (see ProFlatSrf.h Table 4 and
//     online_help/creo_toolkit/user_guide/
//     Unattached_Planar_Wall_based_on_the_Fill_Tool.html);
//   * PRO_E_STD_SMT_THICKNESS is refused once the part owns the sheetmetal
//     thickness parameter, so the parameter is driven first and the element is
//     written only when the part exposes none;
//   * the same tree in a solid part is created but fails regeneration, so the
//     part subtype is checked before anything is written;
//   * the resize drives the driving sketch's coordinate dimensions, which keeps
//     the wall feature id and the thickness untouched instead of rebuilding the
//     feature and re-solving unrelated constraints.
//
// Everything here is evidence: the wall is accepted only after regeneration,
// a measured volume and a frame-signed envelope agree with the request.
//
// The envelope is compared as a *signed* interval, not as a span: the rectangle
// starts at the sketch origin and the material grows one side of the sketch
// plane, so a correct wall reads u[0, length], v[0, width] and either
// n[0, thickness] (direction=positive) or n[-thickness, 0] (direction=negative).
// Comparing spans alone accepted a wall that grew on the opposite side of the
// plane, which the review reproduced.

#pragma once

// Relative tolerance accepted for length*width*thickness against the measured
// solid volume; anything looser would hide a wrong gauge.
static const double PLANAR_WALL_VOLUME_TOLERANCE = 1e-6;
// Absolute floor for the signed envelope comparison, in model units (mm).
static const double PLANAR_WALL_ENVELOPE_TOLERANCE = 1e-6;
// The rectangle is four lines with four corners; fewer point dimensions leave
// the section under-constrained and the wall must not be reported as verified.
static const int PLANAR_WALL_MIN_DIMENSIONS = 4;
