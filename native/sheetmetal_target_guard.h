#ifndef MECHDOG_SHEETMETAL_TARGET_GUARD_H
#define MECHDOG_SHEETMETAL_TARGET_GUARD_H
#include <cmath>
#include <stdexcept>
#include <vector>

namespace sheetmetal_target {
struct BodyCandidate {
    int id;
    bool material;
};
inline int unique_material_body(const std::vector<BodyCandidate> &bodies, bool queries_known) {
    if (!queries_known)
        throw std::runtime_error("Sheetmetal body queries are unknown or failed");
    int selected = -1, count = 0;
    for (const auto &body : bodies)
        if (body.material) {
            selected = body.id;
            ++count;
        }
    if (count != 1)
        throw std::runtime_error(
            "Sheetmetal candidate requires exactly one nonconstruction material sheetmetal body");
    return selected;
}
inline void require_body_gauge(bool api_available, bool query_ok, double value) {
    if (!api_available)
        throw std::runtime_error(
            "Sheetmetal candidate unsupported: actual body gauge API unavailable in SDK");
    if (!query_ok)
        throw std::runtime_error("Sheetmetal target body gauge query failed");
    if (!std::isfinite(value) || value <= 0)
        throw std::runtime_error(
            "Sheetmetal target body requires finite positive actual body gauge");
}
inline void require_membership(int target_id, int surface_body_id, bool same_owner, bool query_ok) {
    if (!query_ok || !same_owner || target_id != surface_body_id)
        throw std::runtime_error(
            "Corner relief surface does not belong to the target material body");
}
} // namespace sheetmetal_target
#endif
