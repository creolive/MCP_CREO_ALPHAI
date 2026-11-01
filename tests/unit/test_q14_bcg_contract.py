"""Offline substitute inputs for Q14; no Toolkit or geometry assertions."""

import unittest

from creo_mechdog.schema import AssemblyPose, validate_operations


class Q14Contract(unittest.TestCase):
    def test_round_explicit_edge_and_surface_pair(self):
        edge = {
            "op": "round",
            "label": "concave_edge",
            "radius": 2,
            "references": [{"edge": {"kind": "edge", "id": 12}}],
        }
        faces = {
            "op": "round",
            "label": "concave_faces",
            "radius": 2,
            "references": [
                {"surfaces": [{"kind": "surface", "id": 21}, {"kind": "surface", "id": 22}]}
            ],
        }
        self.assertEqual(len(validate_operations([edge, faces])), 2)
        for bad in (
            {**edge, "radius": -2},
            {**edge, "references": [{"edge": {"kind": "edge", "id": -1}}]},
        ):
            with self.assertRaises(ValueError):
                validate_operations([bad])

    def test_coordinates_spline_boundary(self):
        sketch = {
            "op": "sketch",
            "label": "curve",
            "dimensioning": "coordinates",
            "entities": [{"type": "spline", "name": "s", "points": [[0, 0], [1, 1], [2, 0]]}],
        }
        with self.assertRaises(ValueError):
            validate_operations([sketch])
        self.assertEqual(len(validate_operations([{**sketch, "dimensioning": "autodim"}])), 1)

    def test_matrix_categories(self):
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        AssemblyPose(rotation_matrix=identity)
        rejected = [
            [[2, 0, 0], [0, 2, 0], [0, 0, 2]],
            [[1e-12, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[1, 0.2, 0], [0, 1, 0], [0, 0, 1]],
            [[2, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[-1, 0, 0], [0, 1, 0], [0, 0, 1]],
        ]
        for matrix in rejected:
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                AssemblyPose(rotation_matrix=matrix)

    def test_frame_direction_schema_boundary(self):
        base = {
            "op": "sketch",
            "label": "frame",
            "plane": {
                "reference": {"kind": "datum_plane", "axis": "z", "offset": 0},
                "u_axis": [2, 0, 0],
            },
            "entities": [{"type": "circle", "name": "c", "center": [0, 0], "radius": 1}],
        }
        validate_operations([base])
        for vector in ([0, 0, 0], [1e-10, 0, 0]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                validate_operations([{**base, "plane": {**base["plane"], "u_axis": vector}}])


if __name__ == "__main__":
    unittest.main()
