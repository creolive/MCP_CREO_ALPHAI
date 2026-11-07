import unittest

from creo_mechdog.mass_properties import normalize_mass_properties


def reading(**overrides):
    base = {
        "volume_mm3": 6000.0,
        "mass_g": 47.1,
        "density_g_cm3": 7.85,
        "density_source": "request",
        "center_of_mass_mm": [5.0, 10.0, 15.0],
        "material_assigned": True,
        "mass_unit": "kg",
        "hint": None,
        "volume_query_code": 0,
        "mass_query_code": 0,
        "units_query_code": 0,
    }
    base.update(overrides)
    return base


class NormalizeMassPropertiesTest(unittest.TestCase):
    def test_request_density_receipt(self):
        result = normalize_mass_properties(reading())
        self.assertEqual(result["volume_mm3"], 6000.0)
        self.assertEqual(result["mass_g"], 47.1)
        self.assertEqual(result["density_source"], "request")
        self.assertEqual(result["center_of_mass_mm"], [5.0, 10.0, 15.0])
        self.assertEqual(result["query_codes"]["volume"], 0)

    def test_material_density_receipt(self):
        result = normalize_mass_properties(
            reading(density_source="model_material", mass_g=47.1, density_g_cm3=7.85)
        )
        self.assertEqual(result["density_source"], "model_material")

    def test_no_density_keeps_mass_empty(self):
        result = normalize_mass_properties(
            reading(
                mass_g=None,
                density_g_cm3=None,
                density_source="none",
                mass_query_code=-1,
                hint="Assign a material with a density",
            )
        )
        self.assertIsNone(result["mass_g"])
        self.assertIsNone(result["density_g_cm3"])
        self.assertEqual(result["density_source"], "none")
        self.assertIn("material", result["hint"])

    def test_mass_without_density_source_is_refused(self):
        with self.assertRaises(ValueError):
            normalize_mass_properties(reading(density_source="none"))

    def test_mass_inconsistent_with_volume_is_refused(self):
        with self.assertRaises(ValueError):
            normalize_mass_properties(reading(mass_g=48.0))

    def test_unknown_density_source_is_refused(self):
        with self.assertRaises(ValueError):
            normalize_mass_properties(reading(density_source="assumed"))

    def test_missing_volume_with_density_is_refused(self):
        with self.assertRaises(ValueError):
            normalize_mass_properties(reading(volume_mm3=None))

    def test_missing_reading_is_refused(self):
        with self.assertRaises(ValueError):
            normalize_mass_properties(None)

    def test_nonfinite_scalars_are_refused_with_field_context(self):
        for source in ("request", "model_material", "none"):
            for field in ("volume_mm3", "mass_g", "density_g_cm3"):
                for value in (float("nan"), float("inf"), -float("inf")):
                    with self.subTest(source=source, field=field, value=value):
                        raw = reading(density_source=source)
                        if source == "none":
                            raw.update(mass_g=None, density_g_cm3=None)
                        raw[field] = value
                        with self.assertRaisesRegex(ValueError, field):
                            normalize_mass_properties(raw)

    def test_nonfinite_center_coordinates_are_refused_with_position(self):
        for container in (list, tuple):
            for index in range(3):
                for value in (float("nan"), float("inf"), -float("inf")):
                    with self.subTest(container=container, index=index, value=value):
                        center = [5, 10, 15]
                        center[index] = value
                        with self.assertRaisesRegex(ValueError, rf"center_of_mass_mm\[{index}\]"):
                            normalize_mass_properties(reading(center_of_mass_mm=container(center)))

    def test_scalar_float_conversion_overflow_is_value_error(self):
        for source in ("request", "model_material", "none"):
            for field in ("volume_mm3", "mass_g", "density_g_cm3"):
                with self.subTest(source=source, field=field):
                    raw = reading(density_source=source)
                    if source == "none":
                        raw.update(mass_g=None, density_g_cm3=None)
                    raw[field] = 10**400
                    with self.assertRaisesRegex(ValueError, field):
                        normalize_mass_properties(raw)

    def test_center_float_conversion_overflow_is_value_error(self):
        for index in range(3):
            with self.subTest(index=index):
                center = [5, 10, 15]
                center[index] = 10**400
                with self.assertRaisesRegex(ValueError, rf"center_of_mass_mm\[{index}\]"):
                    normalize_mass_properties(reading(center_of_mass_mm=center))

    def test_mass_calculation_overflow_is_refused(self):
        for source in ("request", "model_material"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "volume_mm3.*density_g_cm3"):
                    normalize_mass_properties(
                        reading(
                            density_source=source,
                            volume_mm3=1e308,
                            density_g_cm3=1000.0,
                            mass_g=1e308,
                        )
                    )

    def test_mass_difference_overflow_is_refused_with_field_context(self):
        with self.assertRaisesRegex(ValueError, "mass_g"):
            normalize_mass_properties(
                reading(volume_mm3=1e308, density_g_cm3=1.0, mass_g=-1.7976931348623157e308)
            )

    def test_finite_center_coordinates_remain_float_lists(self):
        for center in ([-5, 0, 15], (-5, 0, 15)):
            with self.subTest(center=center):
                result = normalize_mass_properties(reading(center_of_mass_mm=center))
                self.assertEqual(result["center_of_mass_mm"], [-5.0, 0.0, 15.0])
                self.assertTrue(all(type(item) is float for item in result["center_of_mass_mm"]))

    def test_missing_or_malformed_center_remains_none(self):
        for center in (None, [], [1, 2], [1, 2, 3, 4], "123", [1, "2", 3], [1, True, 3]):
            with self.subTest(center=center):
                result = normalize_mass_properties(reading(center_of_mass_mm=center))
                self.assertIsNone(result["center_of_mass_mm"])
        raw = reading()
        del raw["center_of_mass_mm"]
        self.assertIsNone(normalize_mass_properties(raw)["center_of_mass_mm"])

    def test_nullable_or_nonnumeric_scalars_keep_no_density_semantics(self):
        for value in (None, True, False, "1", []):
            with self.subTest(value=value):
                result = normalize_mass_properties(
                    reading(
                        density_source="none", volume_mm3=value, mass_g=value, density_g_cm3=value
                    )
                )
                for field in ("volume_mm3", "mass_g", "density_g_cm3"):
                    self.assertIsNone(result[field])
        raw = reading(density_source="none")
        for field in ("volume_mm3", "mass_g", "density_g_cm3"):
            del raw[field]
        result = normalize_mass_properties(raw)
        for field in ("volume_mm3", "mass_g", "density_g_cm3"):
            self.assertIsNone(result[field])

    def test_consistency_tolerance_is_preserved(self):
        for volume, density, mass in ((6000, 7.85, 47.1), (1, 1, 0.001)):
            expected = volume * density / 1000.0
            tolerance = max(1e-9, abs(expected) * 1e-9)
            raw = reading(volume_mm3=volume, density_g_cm3=density, mass_g=mass + tolerance / 2)
            normalize_mass_properties(raw)
            raw["mass_g"] = mass + tolerance * 2
            with self.assertRaises(ValueError):
                normalize_mass_properties(raw)

    def test_receipt_metadata_is_preserved(self):
        result = normalize_mass_properties(
            reading(volume_query_code=2, mass_query_code=-1, units_query_code=3, hint="raw hint")
        )
        self.assertEqual(result["query_codes"], {"volume": 2, "mass": -1, "units": 3})
        self.assertEqual(result["hint"], "raw hint")
        self.assertEqual(result["mass_unit"], "kg")
        self.assertTrue(result["material_assigned"])
        self.assertEqual(result["density_g_cm3"], 7.85)

    def test_center_of_mass_must_be_three_numbers(self):
        result = normalize_mass_properties(reading(center_of_mass_mm=[1.0, 2.0]))
        self.assertIsNone(result["center_of_mass_mm"])


if __name__ == "__main__":
    unittest.main()
