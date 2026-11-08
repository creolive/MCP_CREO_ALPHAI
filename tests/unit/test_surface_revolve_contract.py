"""FEAT-039/H09 surface-of-revolution contract tests.

Offline only: the published admission surface for ``revolve{mode="surface"}``,
the unchanged planar ``surface_fill`` shape and the native source-level route
are locked here. Live geometry belongs to ``tools/test_surface_revolve.py
--live --confirm-session-usable``; these tests never claim a native feature was
built.
"""

import unittest
from pathlib import Path

from creo_mechdog.capabilities import (
    REGISTERED_OPERATIONS,
    UNAVAILABLE_OPERATIONS,
    require_available,
)
from creo_mechdog.schema import FillOp, validate_operations

ROOT = Path(__file__).resolve().parents[2]
GENERIC = ROOT / "native" / "generic.cpp"
SURFACES = ROOT / "native" / "surfaces.cpp"
SERVER = ROOT / "server.py"
DRIVER = ROOT / "tools" / "test_surface_revolve.py"


def meridian_sketch(closed_extra: list[dict] | None = None) -> dict:
    entities = [
        {
            "type": "centerline",
            "name": "revolve_axis",
            "start": [-12.0, 0.0],
            "end": [12.0, 0.0],
        },
        {
            "type": "arc",
            "name": "meridian_half",
            "center": [0.0, 0.0],
            "radius": 8.0,
            "start_angle": 0.0,
            "end_angle": 180.0,
            "dir": 1,
        },
    ]
    return {
        "op": "sketch",
        "label": "meridian_profile",
        "plane": "XY",
        "entities": entities + (closed_extra or []),
    }


def revolve_plan(**overrides) -> list[dict]:
    operation = {
        "op": "revolve",
        "label": "sphere_quilt",
        "sketch": "meridian_profile",
        "angle": 360,
        "mode": "surface",
    }
    operation.update(overrides)
    return [meridian_sketch(), operation]


class SurfaceRevolveAdmissionTests(unittest.TestCase):
    def test_accepts_meridian_arc_and_construction_axis(self):
        validated = validate_operations(revolve_plan())
        self.assertEqual(validated[1]["op"], "revolve")
        self.assertEqual(validated[1]["mode"], "surface")
        self.assertEqual(validated[1]["angle"], 360)

    def test_surface_mode_accepts_an_open_meridian(self):
        # A sphere is revolved from an open arc; only solid mode requires a
        # closed profile, so surface admission must not inherit that gate.
        validated = validate_operations(revolve_plan())
        self.assertEqual(validated[0]["entities"][1]["type"], "arc")

    def test_solid_revolve_still_requires_a_closed_profile(self):
        with self.assertRaises(ValueError):
            validate_operations(revolve_plan(mode="add"))

    def test_partial_angle_is_still_admitted(self):
        validated = validate_operations(revolve_plan(angle=90))
        self.assertEqual(validated[1]["angle"], 90)

    def test_mode_is_limited_to_add_cut_surface(self):
        for mode in ("surface_only", "sheet", "solid"):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    validate_operations(revolve_plan(mode=mode))


class PlanarFillUnchangedTests(unittest.TestCase):
    def test_fill_accepts_only_a_planar_sketch(self):
        self.assertEqual(set(FillOp.model_fields), {"op", "label", "sketch"})

    def test_fill_refuses_a_nonplanar_boundary_channel(self):
        # There is no 3D closed-boundary input at all: every attempt to carry
        # one is refused before a job exists.
        for extra in (
            {"boundary": {"kind": "quilt", "id": 12}},
            {"edges": [{"kind": "edge", "id": 5}]},
            {"sections": ["a", "b", "c"]},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    validate_operations(
                        [{"op": "surface_fill", "label": "patch", "sketch": "p", **extra}]
                    )

    def test_planar_fill_plan_is_unchanged(self):
        plan = [
            {
                "op": "sketch",
                "label": "planar_profile",
                "plane": "XY",
                "entities": [
                    {"type": "rectangle", "name": "rect", "min": [0.0, 0.0], "max": [40.0, 20.0]}
                ],
            },
            {"op": "surface_fill", "label": "planar_patch", "sketch": "planar_profile"},
        ]
        validated = validate_operations(plan)
        require_available(validated)
        self.assertEqual(validated[1]["op"], "surface_fill")


class SurfaceRevolveCapabilityTests(unittest.TestCase):
    def test_revolve_is_registered_and_published(self):
        self.assertIn("revolve", REGISTERED_OPERATIONS)
        self.assertNotIn("revolve", UNAVAILABLE_OPERATIONS)

    def test_surface_fill_is_still_published(self):
        self.assertNotIn("surface_fill", UNAVAILABLE_OPERATIONS)

    def test_server_exposes_surface_mode_on_revolve(self):
        text = SERVER.read_text(encoding="utf-8")
        index = text.index("async def creo_revolve(")
        block = text[index : index + 900]
        self.assertIn('mode: Literal["add", "cut", "surface"]', block)


class SurfaceRevolveNativeRouteTests(unittest.TestCase):
    def test_revolve_branch_builds_a_datum_surface(self):
        text = GENERIC.read_text(encoding="utf-8")
        self.assertIn("PRO_E_FEATURE_FORM, revolve ? PRO_REVOLVE : PRO_EXTRUDE", text)
        self.assertIn('mode == "surface" ? PRO_FEAT_DATUM_SURF', text)
        self.assertIn("PRO_EXT_FEAT_TYPE_SURFACE", text)
        # The revolve axis is explicit and reported, never guessed.
        self.assertIn("PRO_E_REVOLVE_AXIS_OPT", text)
        self.assertIn("PRO_REV_AXIS_EXT_REF", text)
        self.assertIn("revolve_axis_report", text)

    def test_fill_remains_a_flat_sketch_surface(self):
        text = SURFACES.read_text(encoding="utf-8")
        self.assertIn("integer(root, PRO_E_FEATURE_FORM, PRO_FLAT)", text)
        self.assertIn("PRO_E_SEC_USE_SKETCH", text)
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
        self.assertNotIn("PRO_E_BNDRY", code)
        self.assertNotIn("PRO_E_FILL", code)

    def test_driver_exposes_the_offline_and_live_modes(self):
        text = DRIVER.read_text(encoding="utf-8")
        self.assertIn("--confirm-session-usable", text)
        self.assertIn('mode": "surface', text)
        self.assertIn("cap_shell_volume", text)


if __name__ == "__main__":
    unittest.main()
