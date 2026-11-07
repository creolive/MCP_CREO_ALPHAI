#include "../../native/geometry_diagnostics.h"
#include <cmath>
#include <cstdio>
#include <limits>

namespace {
int failures = 0;

void check(bool condition, const char *message) {
    if (!condition) {
        std::fprintf(stderr, "FAILED: %s\n", message);
        ++failures;
    }
}

bool near(double left, double right) {
    return std::fabs(left - right) < 1e-12;
}
} // namespace

int main() {
    using namespace geometry_diagnostics;
    Point wanted[2] = {{{0, 0, 0}}, {{10, 0, 0}}};

    auto reversed = candidate(8, Point{{10.2, 0, 0}}, Point{{0.1, 0, 0}}, wanted);
    check(near(reversed.error_mm, 0.2), "reversed endpoints use the smaller pairing");
    check(near(reversed.endpoint_errors_mm[0], 0.2), "reversed first endpoint error");
    check(near(reversed.endpoint_errors_mm[1], 0.1), "reversed second endpoint error");

    std::vector<Candidate> found;
    for (int id = 9; id >= 1; --id)
        found.push_back(candidate(id, Point{{0, 0, 0}}, Point{{10.1, 0, 0}}, wanted));
    auto nearest = nearest_candidates(found);
    check(nearest.size() == 5, "at most five candidates");
    check(nearest[0].id == 1 && nearest[4].id == 5, "equal errors fall back to ascending id");
    check(nearest[0].error_mm > 1e-6, "equal-error candidates keep their measured error");

    const double nan = std::numeric_limits<double>::quiet_NaN();
    std::vector<Candidate> non_finite = {
        candidate(4, Point{{nan, 0, 0}}, Point{{0, 0, 0}}, wanted),
        candidate(3, Point{{0, 0, 0}}, Point{{10.5, 0, 0}}, wanted),
        candidate(2, Point{{nan, nan, nan}}, Point{{nan, nan, nan}}, wanted),
        candidate(1, Point{{0, 0, 0}}, Point{{10, 0, 0}}, wanted),
    };
    auto ordered = nearest_candidates(non_finite);
    check(ordered.size() == 4, "finite and non-finite candidates are both kept");
    check(ordered[0].id == 1 && ordered[1].id == 3, "finite candidates sort before non-finite");
    check(ordered[2].id == 2 && ordered[3].id == 4, "non-finite candidates keep id order last");

    check(preview_skip(true, false, false, true), "empty part is skipped");
    check(preview_skip(false, true, false, true), "empty assembly is skipped");
    check(!preview_skip(false, true, true, true), "assembly with geometry is not skipped");
    check(!preview_skip(true, false, true, true), "part with geometry is not skipped");
    check(!preview_skip(false, true, false, false), "failed query is not reported as empty");
    check(!preview_skip(false, false, false, true), "unknown model type is not skipped");

    if (failures != 0)
        return 1;
    std::printf("geometry diagnostics: all checks passed\n");
    return 0;
}
