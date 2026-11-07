#include "../../native/geometry_diagnostics.h"
#include <cassert>
#include <cmath>
#include <string>

int main() {
    using namespace geometry_diagnostics;
    Point wanted[2] = {{{0, 0, 0}}, {{10, 0, 0}}};
    auto reversed = candidate(8, Point{{10.2, 0, 0}}, Point{{0.1, 0, 0}}, wanted);
    assert(std::fabs(reversed.error_mm - 0.2) < 1e-12);
    assert(std::fabs(reversed.endpoint_errors_mm[0] - 0.2) < 1e-12);
    assert(std::fabs(reversed.endpoint_errors_mm[1] - 0.1) < 1e-12);
    std::vector<Candidate> found;
    for (int id = 9; id >= 1; --id)
        found.push_back(candidate(id, Point{{0, 0, 0}}, Point{{10.1, 0, 0}}, wanted));
    auto nearest = nearest_candidates(found);
    assert(nearest.size() == 5);
    assert(nearest[0].id == 1 && nearest[4].id == 5);
    assert(nearest[0].error_mm > 1e-6);
    assert(preview_skip(true, false, false, true));
    assert(preview_skip(false, true, false, true));
    assert(!preview_skip(false, true, true, true));
    assert(!preview_skip(false, true, false, false));
    assert(!preview_skip(false, false, false, true));
}
