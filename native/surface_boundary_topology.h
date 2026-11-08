// DEV-078: Toolkit-free endpoint topology, shared by executor and offline tests.
#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace boundary_patch {
struct Curve {
    int id = -1;
    double start[3] = {0, 0, 0};
    double end[3] = {0, 0, 0};
};
inline double distance(const double *a, const double *b) {
    double sum = 0;
    for (int k = 0; k < 3; ++k)
        sum += (a[k] - b[k]) * (a[k] - b[k]);
    return std::sqrt(sum);
}
struct Layout {
    // Opposite sides; second pair order follows the first pair's start/end.
    int sides[2][2] = {{0, 2}, {3, 1}};
    bool reverse[4] = {};
    double max_gap = 0;
};
inline Layout layout(const std::vector<Curve> &curves, double tolerance) {
    if (curves.size() != 4 || !std::isfinite(tolerance) || tolerance <= 0)
        throw std::runtime_error("four curves and positive finite tolerance required");
    for (const auto &c : curves) {
        for (int k = 0; k < 3; ++k)
            if (!std::isfinite(c.start[k]) || !std::isfinite(c.end[k]))
                throw std::runtime_error("nonfinite boundary endpoint");
        if (distance(c.start, c.end) <= tolerance)
            throw std::runtime_error("collapsed or individually closed perimeter side");
    }
    double best_gap = -1;
    // Enumerate endpoint orientations; unlike closest-pair adjacency this
    // cannot reuse one endpoint for both neighbours (a star is not a loop).
    for (int candidate = 0; candidate < 16; ++candidate) {
        const int mask = candidate ^ 12;
        Layout result;
        bool connected = true;
        for (int i = 0; i < 4; ++i) {
            int next = (i + 1) % 4;
            double gap = distance((mask & (1 << i)) ? curves[i].start : curves[i].end,
                                  (mask & (1 << next)) ? curves[next].end : curves[next].start);
            result.max_gap = std::max(result.max_gap, gap);
            connected = connected && gap <= tolerance;
            // 2 and 3 are traversed opposite to perimeter winding to align
            // both pairs' parameter origins at the same patch corner.
            result.reverse[i] = bool(mask & (1 << i)) != (i >= 2);
        }
        if (best_gap < 0 || result.max_gap < best_gap)
            best_gap = result.max_gap;
        if (connected)
            return result;
    }
    throw std::runtime_error("boundary chain is open or not connected in the submitted order; "
                             "best maximum endpoint gap (model units) " +
                             std::to_string(best_gap));
}
} // namespace boundary_patch
