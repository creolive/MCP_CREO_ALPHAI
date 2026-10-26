#pragma once

#include <cmath>
#include <stdexcept>

// Shared by the production assembly entries and the offline harness. Row-vector
// local-to-parent mapping; translation is the last row. Never repair input poses.
template <typename Json> inline void assembly_rigid_transform(const Json &op, double matrix[4][4]) {
    auto vector3 = [](const Json &value) {
        if (!value.is_array() || value.size() != 3)
            throw std::runtime_error("Assembly pose requires a three-element vector");
        for (const auto &number : value)
            if (!number.is_number() || !std::isfinite(number.template get<double>()))
                throw std::runtime_error("Assembly pose requires finite real numbers");
    };
    const Json zero = Json::array({0, 0, 0});
    const auto &translation = op.contains("translation") ? op.at("translation") : zero;
    vector3(translation);
    const bool has_matrix = op.contains("rotation_matrix") && !op.at("rotation_matrix").is_null();
    const bool has_euler = op.contains("rotation") && !op.at("rotation").is_null();
    if (has_matrix && has_euler)
        throw std::runtime_error("rotation and rotation_matrix are mutually exclusive");
    double rotation[3][3];
    if (has_matrix) {
        const auto &input = op.at("rotation_matrix");
        if (!input.is_array() || input.size() != 3)
            throw std::runtime_error("rotation_matrix must be a nested 3x3 array");
        for (int i = 0; i < 3; ++i) {
            vector3(input[i]);
            for (int j = 0; j < 3; ++j)
                rotation[i][j] = input[i][j].template get<double>();
        }
        for (int i = 0; i < 3; ++i)
            for (int j = 0; j < 3; ++j) {
                double dot = 0;
                for (int k = 0; k < 3; ++k)
                    dot += rotation[i][k] * rotation[j][k];
                if (!std::isfinite(dot) || std::abs(dot - (i == j ? 1.0 : 0.0)) > 1e-6)
                    throw std::runtime_error("rotation_matrix must be orthogonal within 1e-6");
            }
        const auto &a = rotation[0], &b = rotation[1], &c = rotation[2];
        const double det = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) +
                           a[2] * (b[0] * c[1] - b[1] * c[0]);
        if (!std::isfinite(det) || std::abs(det - 1) > 1e-6)
            throw std::runtime_error("rotation_matrix determinant must be +1 within 1e-6");
    } else {
        const auto &euler = has_euler ? op.at("rotation") : zero;
        vector3(euler);
        const double radians = std::acos(-1.0) / 180;
        const double x = euler[0].template get<double>() * radians,
                     y = euler[1].template get<double>() * radians,
                     z = euler[2].template get<double>() * radians;
        const double cx = std::cos(x), sx = std::sin(x), cy = std::cos(y), sy = std::sin(y),
                     cz = std::cos(z), sz = std::sin(z);
        // Preserve the existing Euler transform exactly (transpose of Rz Ry Rx).
        const double column_rotation[3][3] = {
            {cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx},
            {sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx},
            {-sy, cy * sx, cy * cx}};
        for (int i = 0; i < 3; ++i)
            for (int j = 0; j < 3; ++j)
                rotation[i][j] = column_rotation[j][i];
    }
    // All input checks precede even writing the caller's matrix.
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            matrix[i][j] = 0;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            matrix[i][j] = rotation[i][j];
    for (int j = 0; j < 3; ++j)
        matrix[3][j] = translation[j].template get<double>();
    matrix[3][3] = 1;
}
