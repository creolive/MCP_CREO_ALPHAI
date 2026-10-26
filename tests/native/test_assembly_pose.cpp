#include "assembly_pose.h"
#include "third_party/json.hpp"

#include <cassert>
#include <cstdio>
#include <limits>

using J = nlohmann::json;

static void close(double actual, double expected) {
    assert(std::abs(actual - expected) < 1e-12);
}

static void pose(const J &euler, const J &rows, const J &point_expected) {
    const J translation = {7, -8, 9};
    double from_euler[4][4], from_matrix[4][4];
    assembly_rigid_transform(J{{"rotation", euler}, {"translation", translation}}, from_euler);
    assembly_rigid_transform(J{{"rotation_matrix", rows}, {"translation", translation}},
                             from_matrix);
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j) {
            close(from_euler[i][j], from_matrix[i][j]);
            if (i < 3 && j < 3)
                close(from_matrix[i][j], rows[i][j]);
        }
    // Each basis vector maps to the corresponding supplied row, plus offset.
    for (int basis = 0; basis < 3; ++basis)
        for (int j = 0; j < 3; ++j)
            close(from_matrix[basis][j] + from_matrix[3][j],
                  rows[basis][j].get<double>() + translation[j].get<double>());
    const double point[] = {2, 3, 5};
    double mapped[3];
    for (int j = 0; j < 3; ++j) {
        mapped[j] = from_matrix[3][j];
        for (int k = 0; k < 3; ++k)
            mapped[j] += point[k] * from_matrix[k][j];
        close(mapped[j], point_expected[j].get<double>() + translation[j].get<double>());
    }
    // Inverse mapping uses the transpose for orthogonal rotations only.
    for (int j = 0; j < 3; ++j) {
        double inverse = 0;
        for (int k = 0; k < 3; ++k)
            inverse += (mapped[k] - from_matrix[3][k]) * from_matrix[j][k];
        close(inverse, point[j]);
    }
    close(from_matrix[3][3], 1);
}

static void rejected(const J &op) {
    double matrix[4][4];
    for (auto &row : matrix)
        for (auto &number : row)
            number = 123;
    bool refused = false;
    try {
        assembly_rigid_transform(op, matrix);
    } catch (const std::exception &) {
        refused = true;
    }
    assert(refused);
    for (auto &row : matrix)
        for (double number : row)
            assert(number == 123); // checks precede output mutation
}

int main() {
    const J identity = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    pose({0, 0, 0}, identity, {2, 3, 5});
    pose({90, 0, 0}, {{1, 0, 0}, {0, 0, 1}, {0, -1, 0}}, {2, -5, 3});
    pose({-90, 0, 0}, {{1, 0, 0}, {0, 0, -1}, {0, 1, 0}}, {2, 5, -3});
    pose({0, 90, 0}, {{0, 0, -1}, {0, 1, 0}, {1, 0, 0}}, {5, 3, -2});
    pose({0, -90, 0}, {{0, 0, 1}, {0, 1, 0}, {-1, 0, 0}}, {-5, 3, 2});
    pose({0, 0, 90}, {{0, 1, 0}, {-1, 0, 0}, {0, 0, 1}}, {-3, 2, 5});
    pose({0, 0, -90}, {{0, -1, 0}, {1, 0, 0}, {0, 0, 1}}, {3, -2, 5});
    pose({90, 0, 90}, {{0, 1, 0}, {0, 0, 1}, {1, 0, 0}}, {5, 2, 3});
    pose({90, 90, 90}, {{0, 0, -1}, {0, 1, 0}, {1, 0, 0}}, {5, 3, -2});
    pose({90, -90, 90}, {{0, 0, 1}, {0, -1, 0}, {1, 0, 0}}, {5, -3, 2});
    const double h = std::sqrt(3.0) / 2;
    pose({30, 90, 60}, {{0, 0, -1}, {-0.5, h, 0}, {h, 0.5, 0}}, {-1.5 + 5 * h, 3 * h + 2.5, -2});

    double matrix[4][4];
    assembly_rigid_transform(J::object(), matrix);
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            close(matrix[i][j], i == j ? 1 : 0);
    J near = identity;
    near[0][0] = 1 + 1e-7;
    assembly_rigid_transform(J{{"rotation_matrix", near}}, matrix);
    assert(matrix[0][0] == near[0][0].get<double>()); // no reorthogonalization
    rejected({{"rotation", {0, 0, 0}}, {"rotation_matrix", identity}});
    for (const J &invalid : J::array({J::array(), J::array({1, 0, 0, 0, 1, 0, 0, 0, 1}),
                                      J::array({{1, 0}, {0, 1}, {0, 0}}),
                                      J::array({{1, 0, 0}, {0, 1, 0}}), J("identity")}))
        rejected({{"rotation_matrix", invalid}});
    for (const J &number : J::array({J(true), J("1"), J(nullptr), J(2), J(-1), J(1 + 1e-6),
                                     J(1e308), J(std::numeric_limits<double>::infinity()),
                                     J(std::numeric_limits<double>::quiet_NaN())})) {
        J invalid = identity;
        invalid[0][0] = number;
        rejected({{"rotation_matrix", invalid}});
    }
    J skew = identity;
    skew[0][1] = 1e-4;
    rejected({{"rotation_matrix", skew}});
    J scaled = identity;
    for (int i = 0; i < 3; ++i)
        scaled[i][i] = 1 + 4e-7; // Gram passes, determinant alone exceeds tolerance
    rejected({{"rotation_matrix", scaled}});
    rejected({{"rotation_matrix", identity}, {"translation", {0, true, 0}}});
    rejected({{"rotation", {0, 0}}});
    rejected({{"rotation", {0, std::numeric_limits<double>::infinity(), 0}}});
    std::puts("assembly_pose: 11 Euler/matrix poses, basis/known-point/inverse maps, defaults, "
              "tolerance preservation and invalid-input checks passed; no Toolkit connection");
}
