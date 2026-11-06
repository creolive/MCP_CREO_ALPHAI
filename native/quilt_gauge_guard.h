// quilt_gauge_guard.h — BUG-112: the one rule deciding whether a quilt opened
// by ProQuiltInit may be handed to the area measurement. ProQuiltInit answers
// through both a return code and a handle, and neither alone is proof: a failed
// Init can leave a handle behind, and a handle is useless when the code failed.
// Only PRO_TK_NO_ERROR (0) with a non-null handle allows a measurement; every
// other combination stays unmeasured instead of feeding a bad quilt into
// quilt_area_native() and fabricating a finite offset distance.
//
// Kept as a plain predicate so the production branch in surfaces.cpp and the
// offline stub (tests/native/test_surface_measure_guard.cpp, built by
// tools/test_surface_measure_guard.py) execute the same rule without a Toolkit
// connection.
#pragma once

static bool quilt_gauge_ready(int init_code, const void *handle) {
    return init_code == 0 && handle != nullptr;
}
