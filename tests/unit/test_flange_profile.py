import unittest

from pydantic import ValidationError

from creo_mechdog.flange_profile import FlangeProfile


def line(a, b, name="a"):
    return dict(type="line", name=name, start=a, end=b)


class FlangeProfileTests(unittest.TestCase):
    def test_line_arc_degrees_and_winding(self):
        arc = dict(
            type="arc", name="b", center=[1, 1], radius=1, start_angle=-90, end_angle=0, dir=1
        )
        p = FlangeProfile(entities=[line([0, 0], [1, 0]), arc])
        self.assertEqual(p.to_profile()["profile"][1]["end_angle"], 0)
        self.assertGreaterEqual(p.extent, 2)
        arc.update(start_angle=-90, end_angle=180, dir=-1)
        FlangeProfile(entities=[line([0, 0], [1, 0]), arc])

    def test_rejections(self):
        cases = [
            [line([0, 0], [0, 0]), line([0, 0], [1, 0], "b")],
            [line([0, 0], [1, 0]), line([2, 0], [3, 0], "b")],
            [line([0, 0], [1, 0]), line([1, 0], [0, 0], "b")],
            [line([0, 0], [1, 1]), line([1, 1], [0, 1], "b"), line([0, 1], [1, 0], "c")],
            [line([False, 0], [1, 0]), line([1, 0], [2, 0], "b")],
            [line([0, 0], [float("inf"), 0]), line([1, 0], [2, 0], "b")],
        ]
        for entities in cases:
            with self.subTest(entities=entities), self.assertRaises(ValidationError):
                FlangeProfile(entities=entities)

    def test_arc_crossing_and_strict_direction(self):
        arc = dict(
            type="arc", name="b", center=[1, 1], radius=1, start_angle=-90, end_angle=180, dir=1
        )
        with self.assertRaises(ValidationError):
            FlangeProfile(entities=[line([0, 0], [1, 0]), arc, line([0, 1], [2, 0], "c")])
        arc["dir"] = True
        with self.assertRaises(ValidationError):
            FlangeProfile(entities=[line([0, 0], [1, 0]), arc])

    def test_size_names_extras_and_arc_overlap(self):
        good = [line([0, 0], [1, 0]), line([1, 0], [2, 0], "b")]
        for entities in (
            [good[0]],
            good * 17,
            [good[0], line([1, 0], [2, 0])],
            [dict(good[0], construction=True), good[1]],
        ):
            with self.subTest(entities=entities), self.assertRaises(ValidationError):
                FlangeProfile(entities=entities)
        a = dict(type="arc", name="a", center=[0, 1], radius=1, start_angle=-90, end_angle=0, dir=1)
        b = dict(a, name="b", start_angle=0, end_angle=90)
        with self.assertRaisesRegex(ValidationError, "coincident-circle"):
            FlangeProfile(entities=[a, b])

    def test_wrapped_clockwise_arc_roundtrip(self):
        arc = dict(
            type="arc", name="b", center=[1, 1], radius=1, start_angle=270, end_angle=180, dir=-1
        )
        p = FlangeProfile(entities=[line([0, 0], [1, 0]), arc])
        self.assertEqual(p.to_profile()["profile"][1]["dir"], -1)
        self.assertEqual(p.to_profile()["dimensions"], [])
        self.assertEqual(FlangeProfile.model_validate(p.model_dump()), p)
        for direction in (
            True,
            1.0,
            "1",
            0,
            4294967297,
            -4294967295,
            2147483648,
            9223372036854775807,
            18446744073709551615,
        ):
            with self.subTest(direction=direction), self.assertRaises(ValidationError):
                FlangeProfile(entities=[line([0, 0], [1, 0]), dict(arc, dir=direction)])

    def test_arc_arc_tangency_and_crossing(self):
        a = dict(type="arc", name="a", center=[0, 1], radius=1, start_angle=-90, end_angle=0, dir=1)
        b = dict(
            type="arc", name="b", center=[2, 1], radius=1, start_angle=180, end_angle=90, dir=-1
        )
        FlangeProfile(entities=[a, b])
        b.update(center=[1, 0], start_angle=90, end_angle=270, dir=1)
        with self.assertRaises(ValidationError):
            FlangeProfile(entities=[a, b])

    def test_enormous_integers_are_validation_errors(self):
        for value in (10**400, -(10**400)):
            for field in ("coordinate", "radius", "start_angle", "end_angle"):
                a = line([0, 0], [1, 0])
                b = dict(
                    type="arc",
                    name="b",
                    center=[1, 1],
                    radius=1,
                    start_angle=-90,
                    end_angle=0,
                    dir=1,
                )
                if field == "coordinate":
                    a["start"][0] = value
                else:
                    b[field] = value
                with self.subTest(field=field, sign=value > 0), self.assertRaises(ValidationError):
                    FlangeProfile(entities=[a, b])
