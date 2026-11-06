// BUG-112 offline check of the shared quilt gauge guard.
//
// The substituted stand-in supplies only a ProQuiltInit result code and a
// handle, so no Creo SDK, Toolkit library or session is involved. The three
// combinations below are exactly the ones the production branch in
// surfaces.cpp::generic_surface_offset decides on; only the third may measure.
#include "quilt_gauge_guard.h"

#include <cassert>
#include <cstdio>

struct FakeQuilt {
    int id;
};

static int measure_calls = 0;

// The test double for the production branch: the measurement runs only when the
// shared guard says the compiler/handle pair is usable.
static bool measure_if_ready(int init_code, const void *handle) {
    if (!quilt_gauge_ready(init_code, handle))
        return false;
    ++measure_calls;
    return true;
}

int main() {
    FakeQuilt quilt{7};
    const void *leftover_handle = &quilt;

    // 1. Init failed yet a handle survived: the handle is not proof of success,
    // so the area measurement must not run against it.
    measure_calls = 0;
    assert(!quilt_gauge_ready(-1, leftover_handle));
    assert(!measure_if_ready(-1, leftover_handle));
    assert(measure_calls == 0);

    // 2. Init reported success but returned no handle: nothing to measure, and
    // a null handle must never be passed on to a quilt query.
    assert(!quilt_gauge_ready(0, nullptr));
    assert(!measure_if_ready(0, nullptr));
    assert(measure_calls == 0);

    // 3. Init reported success with a handle: this, and only this, may measure.
    assert(quilt_gauge_ready(0, leftover_handle));
    assert(measure_if_ready(0, leftover_handle));
    assert(measure_calls == 1);

    // A nonzero code never measures, with or without a handle behind it.
    assert(!quilt_gauge_ready(1, leftover_handle));
    assert(!quilt_gauge_ready(1, nullptr));
    assert(!measure_if_ready(1, leftover_handle));
    assert(measure_calls == 1);

    std::puts("SURFACE_MEASURE_GUARD_OK cases=3; code/handle substituted, no Toolkit connection");
    return 0;
}
