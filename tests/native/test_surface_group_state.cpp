// Execute the production decision function without any Toolkit calls.
#include <cstring>
struct SurfaceGroupMeasurement {
    bool edges_available = true, overlap_available = false, overlap_detected = false;
    bool gap_available = false;
    int sample_failures = 0, open_edges = 2, joined_pairs = 0;
    double gap_max = 0, max_joined_gap = 0;
    const char *edges_reason = nullptr, *state = nullptr, *state_reason = nullptr;
};
#include "group_state_under_test.inc"
static bool same(const char *a, const char *b) {
    return a && std::strcmp(a, b) == 0;
}
int main() {
    SurfaceGroupMeasurement m;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state, "open") || !same(m.state_reason, "open_edges_present"))
        return 1;
    m = {};
    m.gap_available = true;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state_reason, "open_edges_present"))
        return 2;
    m = {};
    m.edges_available = false;
    group_state_decide(m, .01, .000001, m);
    if (m.state || !same(m.state_reason, "boundary_edges_unavailable"))
        return 3;
    m = {};
    m.open_edges = 0;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state, "closed"))
        return 4;
    m = {};
    m.overlap_available = m.overlap_detected = true;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state, "overlap"))
        return 5;
    m = {};
    m.joined_pairs = 1;
    m.max_joined_gap = .001;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state, "micro_gap"))
        return 6;
    m = {};
    m.sample_failures = 1;
    group_state_decide(m, .01, .000001, m);
    if (m.state || !same(m.state_reason, "boundary_edge_sampling_failed"))
        return 7;
    m = {};
    m.gap_available = true;
    m.gap_max = .1;
    group_state_decide(m, .01, .000001, m);
    if (!same(m.state, "open"))
        return 8;
    m = {};
    m.joined_pairs = 1;
    group_state_decide(m, .01, .000001, m);
    return same(m.state, "closed") ? 0 : 9;
}
