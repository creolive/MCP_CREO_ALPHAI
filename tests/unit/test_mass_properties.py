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

    def test_center_of_mass_must_be_three_numbers(self):
        result = normalize_mass_properties(reading(center_of_mass_mm=[1.0, 2.0]))
        self.assertIsNone(result["center_of_mass_mm"])


if __name__ == "__main__":
    unittest.main()
