// endpoint_weld.h - FEAT-039/W01: the controlled endpoint weld.
//
// The kernel exposes no displacement limit for a sketch constraint, so a
// controlled weld cannot be delegated to the solver. Instead the request
// coordinates are regularised before the entities are written: each welded
// endpoint moves half the gap towards its partner, so the move is bounded by
// construction and the bound is the one the caller asked for. The kernel is
// then asked to solve a profile whose endpoints already coincide, and the
// residual is measured from the solved section afterwards.
//
// This header is included by generic.cpp and sketch_edit.cpp after J and the
// section helpers are visible; it defines no entry point.
#pragma once

#include <ProSection.h>

#include <cmath>
#include <map>
#include <string>

// Applies the weld plan to a mutable copy of the request entities and returns
// the report the operation publishes. An empty report means no weld was
// requested.
static J apply_endpoint_weld(const J &op, J &spec) {
    J report = J::object();
    if (op.value("endpoint_policy", "report") != "weld")
        return report;
    const double bound = op.value("max_endpoint_move_mm", 0.0);
    auto entity_by_name = [&](const std::string &name) -> J * {
        for (auto &item : spec)
            if (item.value("name", std::string()) == name)
                return &item;
        return nullptr;
    };
    auto endpoint_of = [](J &entity, const std::string &point, double *out) -> bool {
        const std::string type = entity.value("type", std::string());
        if (type != "line" && type != "centerline")
            return false;
        const std::string key = point == "start" ? "start" : "end";
        if (!entity.contains(key))
            return false;
        const J &value = entity.at(key);
        if (!value.is_array() || value.size() < 2)
            return false;
        out[0] = value[0].get<double>();
        out[1] = value[1].get<double>();
        return true;
    };
    J applied_detail = J::array();
    J skipped = J::array();
    double max_move = 0.0;
    int applied_pairs = 0;
    for (auto pair : op.value("weld_pairs", J::array())) {
        const J side_a = pair.value("a", J::object());
        const J side_b = pair.value("b", J::object());
        const std::string a_name = side_a.value("entity", std::string());
        const std::string b_name = side_b.value("entity", std::string());
        const std::string a_point = side_a.value("point", std::string("start"));
        const std::string b_point = side_b.value("point", std::string("end"));
        J *first = entity_by_name(a_name);
        J *second = entity_by_name(b_name);
        double pa[2] = {0.0, 0.0};
        double pb[2] = {0.0, 0.0};
        if (!first || !second || !endpoint_of(*first, a_point, pa) ||
            !endpoint_of(*second, b_point, pb)) {
            skipped.push_back({{"entities", J::array({a_name, b_name})},
                               {"reason", "unsupported_entity_or_point"}});
            continue;
        }
        const double gap = std::hypot(pb[0] - pa[0], pb[1] - pa[1]);
        if (gap <= 0.0) {
            skipped.push_back(
                {{"entities", J::array({a_name, b_name})}, {"reason", "already_coincident"}});
            continue;
        }
        const double move = gap / 2.0;
        if (bound > 0.0 && move > bound) {
            skipped.push_back({{"entities", J::array({a_name, b_name})},
                               {"reason", "over_bound"},
                               {"gap_mm", gap},
                               {"move_mm", move}});
            continue;
        }
        const double mid[2] = {(pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0};
        (*first)[a_point] = J::array({mid[0], mid[1]});
        (*second)[b_point] = J::array({mid[0], mid[1]});
        if (move > max_move)
            max_move = move;
        applied_pairs += 1;
        applied_detail.push_back({{"entities", J::array({a_name, b_name})},
                                  {"points", J::array({a_point, b_point})},
                                  {"gap_mm", gap},
                                  {"move_mm", move}});
    }
    report = {{"requested", true},
              {"method", "coordinate_regularisation_before_write"},
              {"bound_mm", bound},
              {"applied_pairs", applied_pairs},
              {"applied_pair_detail", applied_detail},
              {"skipped", skipped},
              {"max_move_mm", max_move}};
    return report;
}
// Measures the distance between the welded endpoints of the solved section.
static double endpoint_weld_residual(const ProSection section,
                                     const std::map<std::string, int> &entities, const J &report) {
    auto solved_endpoint = [&](int id, const std::string &point, double *out) -> bool {
        Pro2dEntdef *def = nullptr;
        if (ProSectionEntityGet(section, id, &def) || !def)
            return false;
        if (def->type != PRO_2D_LINE && def->type != PRO_2D_CENTER_LINE)
            return false;
        auto line = (Pro2dLinedef *)def;
        const double *p = point == "start" ? line->end1 : line->end2;
        out[0] = p[0];
        out[1] = p[1];
        return true;
    };
    double residual = 0.0;
    for (auto pair : report.value("applied_pair_detail", J::array())) {
        const J names = pair.value("entities", J::array());
        const J points = pair.value("points", J::array());
        if (names.size() < 2 || points.size() < 2)
            return -1.0;
        auto first = entities.find(names[0].get<std::string>());
        auto second = entities.find(names[1].get<std::string>());
        if (first == entities.end() || second == entities.end())
            return -1.0;
        double pa[2] = {0.0, 0.0};
        double pb[2] = {0.0, 0.0};
        if (!solved_endpoint(first->second, points[0].get<std::string>(), pa) ||
            !solved_endpoint(second->second, points[1].get<std::string>(), pb))
            return -1.0;
        const double gap = std::hypot(pb[0] - pa[0], pb[1] - pa[1]);
        if (gap > residual)
            residual = gap;
    }
    return residual;
}