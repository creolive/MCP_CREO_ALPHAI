// DEV-078: offline candidate admission. All geometry is request-derived, in mm.
// Coincident-circle arcs are deliberately unsupported (same as Python admission).
struct FlangeProfileEntity {
    bool arc = false;
    std::array<double, 2> s{}, e{}, c{};
    double r = 0, angle = 0, sweep = 0;
    int dir = 1;
};
static double fp_cross(std::array<double, 2> a, std::array<double, 2> b) {
    return a[0] * b[1] - a[1] * b[0];
}
static std::array<double, 2> fp_sub(std::array<double, 2> a, std::array<double, 2> b) {
    return {a[0] - b[0], a[1] - b[1]};
}
static double fp_dot(std::array<double, 2> a, std::array<double, 2> b) {
    return a[0] * b[0] + a[1] * b[1];
}
static double fp_dist(std::array<double, 2> a, std::array<double, 2> b) {
    return hypot(a[0] - b[0], a[1] - b[1]);
}
static double fp_mod(double a) {
    return fmod(fmod(a, 360.0) + 360.0, 360.0);
}
static double fp_number(const J &v) {
    if (!v.is_number() || !std::isfinite(v.get<double>()) || fabs(v.get<double>()) > 1e6)
        throw std::runtime_error("flange profile requires finite real numbers within +/-1e6");
    return v.get<double>();
}
static std::array<double, 2> fp_point(const J &v) {
    if (!v.is_array() || v.size() != 2)
        throw std::runtime_error("flange profile point needs 2 coordinates");
    return {fp_number(v.at(0)), fp_number(v.at(1))};
}
static bool fp_on(const FlangeProfileEntity &a, std::array<double, 2> p) {
    auto d = fp_sub(a.e, a.s), q = fp_sub(p, a.s);
    if (!a.arc)
        return fabs(fp_cross(d, q)) <= 1e-8 * hypot(d[0], d[1]) && fp_dot(q, d) >= -1e-8 &&
               fp_dot(q, d) <= fp_dot(d, d) + 1e-8;
    if (fabs(fp_dist(p, a.c) - a.r) > 1e-8)
        return false;
    double angle = atan2(p[1] - a.c[1], p[0] - a.c[0]) * 180 / acos(-1.0);
    double sweep = fp_mod((angle - a.angle) * a.dir);
    return sweep <= a.sweep + 1e-8 || 360 - sweep <= 1e-8;
}
static std::vector<std::array<double, 2>> fp_hits(FlangeProfileEntity a, FlangeProfileEntity b) {
    if (a.arc && !b.arc)
        std::swap(a, b);
    std::vector<std::array<double, 2>> candidates, result;
    if (!a.arc && !b.arc) {
        auto d = fp_sub(a.e, a.s), f = fp_sub(b.e, b.s), q = fp_sub(b.s, a.s);
        double den = fp_cross(d, f);
        if (den == 0)
            candidates = {a.s, a.e, b.s, b.e};
        else {
            double t = fp_cross(q, f) / den;
            candidates.push_back({a.s[0] + t * d[0], a.s[1] + t * d[1]});
        }
    } else if (!a.arc) {
        auto d = fp_sub(a.e, a.s), q = fp_sub(a.s, b.c);
        double aa = fp_dot(d, d), bb = 2 * fp_dot(q, d),
               disc = bb * bb - 4 * aa * (fp_dot(q, q) - b.r * b.r);
        if (disc < -1e-8)
            return result;
        for (int sign : {-1, 1}) {
            double t = (-bb + sign * sqrt(std::max(0.0, disc))) / (2 * aa);
            candidates.push_back({a.s[0] + t * d[0], a.s[1] + t * d[1]});
        }
    } else {
        double d = fp_dist(a.c, b.c);
        if (d <= 1e-8) {
            if (fabs(a.r - b.r) <= 1e-8)
                throw std::runtime_error("coincident-circle flange arcs unsupported offline");
            return result;
        }
        if (d > a.r + b.r + 1e-8 || d < fabs(a.r - b.r) - 1e-8)
            return result;
        double x = (a.r * a.r - b.r * b.r + d * d) / (2 * d),
               h = sqrt(std::max(0.0, a.r * a.r - x * x));
        auto u = fp_sub(b.c, a.c);
        u[0] /= d;
        u[1] /= d;
        for (int sign : {-1, 1})
            candidates.push_back(
                {a.c[0] + x * u[0] - sign * h * u[1], a.c[1] + x * u[1] + sign * h * u[0]});
    }
    for (auto p : candidates)
        if (fp_on(a, p) && fp_on(b, p))
            result.push_back(p);
    return result;
}
static J flange_profile_request(const J &request, double &extent) {
    if (!request.is_object() || request.size() != 1 || !request.contains("entities"))
        throw std::runtime_error("flange profile requires only entities");
    const J &entities = request.at("entities");
    if (!entities.is_array() || entities.size() < 2 || entities.size() > 32)
        throw std::runtime_error("flange profile requires 2-32 entities");
    std::vector<FlangeProfileEntity> parsed;
    std::set<std::string> names;
    extent = 0;
    for (const J &e : entities) {
        if (!e.is_object())
            throw std::runtime_error("flange entity must be object");
        std::string type = e.at("type").get<std::string>(), name = e.at("name").get<std::string>();
        if (name.empty() || name.size() > 28 || name[0] < 'a' || name[0] > 'z' ||
            !names.insert(name).second)
            throw std::runtime_error("invalid or duplicate flange entity name");
        for (char c : name)
            if (!(c >= 'a' && c <= 'z') && !(c >= '0' && c <= '9') && c != '_')
                throw std::runtime_error("invalid flange entity name");
        FlangeProfileEntity a;
        if (type == "line") {
            a.s = fp_point(e.at("start"));
            a.e = fp_point(e.at("end"));
        } else if (type == "arc") {
            a.arc = true;
            a.c = fp_point(e.at("center"));
            a.r = fp_number(e.at("radius"));
            if (a.r <= 1e-8 || a.r > 100000)
                throw std::runtime_error("invalid flange arc radius");
            a.angle = fp_number(e.at("start_angle"));
            double end = fp_number(e.at("end_angle"));
            if (e.contains("dir")) {
                const J &direction = e.at("dir");
                // Validate in the JSON storage width before narrowing to int.
                // Keep unsigned separate: UINT64_MAX must never alias signed -1.
                bool valid_direction =
                    direction.is_number_integer() &&
                    (direction.is_number_unsigned() ? direction.get<std::uint64_t>() == 1
                                                    : (direction.get<std::int64_t>() == 1 ||
                                                       direction.get<std::int64_t>() == -1));
                if (!valid_direction)
                    throw std::runtime_error("invalid flange arc dir");
                a.dir = direction.get<int>();
            }
            if (a.dir != 1 && a.dir != -1)
                throw std::runtime_error("invalid flange arc dir");
            a.sweep = fp_mod((end - a.angle) * a.dir);
            if (a.sweep < 1e-8)
                throw std::runtime_error("zero/full flange arc");
            auto at = [&](double deg) {
                double t = deg * acos(-1.0) / 180;
                return std::array<double, 2>{a.c[0] + a.r * cos(t), a.c[1] + a.r * sin(t)};
            };
            a.s = at(a.angle);
            a.e = at(end);
        } else
            throw std::runtime_error("flange section allows line/arc only");
        for (auto it = e.begin(); it != e.end(); ++it) {
            const std::string k = it.key();
            bool allowed = k == "type" || k == "name" || (!a.arc && (k == "start" || k == "end")) ||
                           (a.arc && (k == "center" || k == "radius" || k == "start_angle" ||
                                      k == "end_angle" || k == "dir"));
            if (!allowed)
                throw std::runtime_error("unknown flange entity field");
        }
        if (fp_dist(a.s, a.e) <= 1e-8 ||
            (parsed.empty() ? hypot(a.s[0], a.s[1]) > 1e-8 : fp_dist(parsed.back().e, a.s) > 1e-8))
            throw std::runtime_error("flange section zero length or discontinuous/origin mismatch");
        for (size_t j = 0; j < parsed.size(); ++j)
            for (auto p : fp_hits(parsed[j], a))
                if (j + 1 != parsed.size() || fp_dist(p, a.s) > 1e-8)
                    throw std::runtime_error("flange section self intersection/overlap/closure");
        extent = std::max(extent, a.arc ? hypot(a.c[0], a.c[1]) + a.r
                                        : std::max(hypot(a.s[0], a.s[1]), hypot(a.e[0], a.e[1])));
        parsed.push_back(a);
    }
    return {{"profile", entities}, {"dimensions", J::array()}, {"constraints", J::array()}};
}
