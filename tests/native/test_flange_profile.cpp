#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include "../../native/third_party/json.hpp"
using J = nlohmann::json;
#include "../../native/flange_profile.h"

int main() {
    int failures = 0;
    J line = {{"type", "line"}, {"name", "a"}, {"start", {0, 0}}, {"end", {1, 0}}};
    J arc = {{"type", "arc"},      {"name", "b"},    {"center", {1, 1}}, {"radius", 1},
             {"start_angle", -90}, {"end_angle", 0}, {"dir", 1}};
    auto run = [&](J direction, bool accept) {
        J a = arc;
        a["dir"] = direction;
        bool accepted = true;
        try {
            double extent;
            auto result = flange_profile_request({{"entities", J::array({line, a})}}, extent);
            if (result.at("profile").size() != 2 || extent < 2)
                accepted = false;
        } catch (const std::exception &) {
            accepted = false;
        }
        if (accepted != accept) {
            std::fprintf(stderr, "dir=%s expected=%d actual=%d\n", direction.dump().c_str(), accept,
                         accepted);
            ++failures;
        }
    };
    run(1, true);
    run(-1, true);
    for (const J &direction :
         J::array({true, 1.0, "1", 0, 4294967297LL, -4294967295LL, 2147483648LL,
                   9223372036854775807LL, 18446744073709551615ULL}))
        run(direction, false);
    std::printf("flange native parity: %d failures\n", failures);
    return failures ? 1 : 0;
}
