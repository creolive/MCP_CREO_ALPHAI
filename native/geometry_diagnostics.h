#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace geometry_diagnostics {
using Point = std::array<double, 3>;

struct Candidate {
    int id;
    Point endpoints[2];
    double endpoint_errors_mm[2];
    double error_mm;
};

inline double distance(const Point &a, const Point &b) {
    double squared = 0;
    for (int axis = 0; axis < 3; ++axis)
        squared += (a[axis] - b[axis]) * (a[axis] - b[axis]);
    return std::sqrt(squared);
}

inline Candidate candidate(int id, Point first, Point second, const Point wanted[2]) {
    double direct[2] = {distance(first, wanted[0]), distance(second, wanted[1])};
    double reverse[2] = {distance(first, wanted[1]), distance(second, wanted[0])};
    bool use_reverse = std::max(reverse[0], reverse[1]) < std::max(direct[0], direct[1]);
    return {id,
            {first, second},
            {use_reverse ? reverse[0] : direct[0], use_reverse ? reverse[1] : direct[1]},
            use_reverse ? std::max(reverse[0], reverse[1]) : std::max(direct[0], direct[1])};
}

inline double sort_error(const Candidate &value) {
    return std::isfinite(value.error_mm) ? value.error_mm
                                         : std::numeric_limits<double>::infinity();
}

inline std::vector<Candidate> nearest_candidates(std::vector<Candidate> candidates) {
    std::sort(candidates.begin(), candidates.end(), [](const Candidate &a, const Candidate &b) {
        const double left = sort_error(a);
        const double right = sort_error(b);
        if (left != right)
            return left < right;
        return a.id < b.id;
    });
    if (candidates.size() > 5)
        candidates.resize(5);
    return candidates;
}

inline bool preview_skip(bool part, bool assembly, bool renderable, bool query_succeeded) {
    return (part || assembly) && query_succeeded && !renderable;
}
} // namespace geometry_diagnostics
