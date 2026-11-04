"""BUG-069: managed model names accept digit-first input and normalize case."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bridge
import generic_bridge as general


class NormalizeModelName(unittest.TestCase):
    def test_accepted_and_normalized_names(self):
        cases = {
            "001": "001",  # digit-first is now accepted (Creo-native style)
            "1": "1",
            "prt001": "prt001",
            "PRT001": "prt001",  # uppercase input is normalized, not rejected
            "1a_b": "1a_b",
            "a" * 31: "a" * 31,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(bridge.normalize_model_name(value), expected)

    def test_rejected_names_carry_the_full_rule(self):
        for value in ("", "A B", "a-b", "a.b", "_lead", "a" * 32, None, 7):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as refused:
                    bridge.normalize_model_name(value)
                self.assertIn("model_name must be 1-31 characters", str(refused.exception))
                self.assertIn("uppercase input is normalized", str(refused.exception))

    def test_plate_spec_normalizes_before_use(self):
        spec = bridge.validate_spec(80, 60, 10, 0, [], model_name="PRT001")
        self.assertEqual(spec["model_name"], "prt001")

    def test_plate_spec_rejects_invalid_names(self):
        with self.assertRaisesRegex(ValueError, "model_name must be 1-31 characters"):
            bridge.validate_spec(80, 60, 10, 0, [], model_name="a b")


class SubmitAdmissionNameRule(unittest.TestCase):
    """The generic submit admission validates names before any channel work."""

    def test_invalid_name_is_refused_before_job_creation(self):
        with self.assertRaisesRegex(ValueError, "uppercase input is normalized"):
            general.submit([], None, "PRT 001")

    def test_digit_first_name_passes_admission(self):
        # Validation happens before job persistence; capture the created model
        # registry entry to confirm the normalized digit-first name stuck. The
        # runner spawn is intercepted so no native/Creo work is attempted.
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory(prefix="bug069_") as temporary:
            real_root, real_jobs, real_models = bridge.ROOT, bridge.JOBS, general.MODELS
            # Admission only needs the template path to exist; the runner below
            # is mocked, so this fixture never reaches Creo or reads SDK data.
            template = Path(temporary) / "Common Files/templates/mmns_part_solid_abs.prt"
            template.parent.mkdir(parents=True)
            template.touch()
            test_config = {"creo_root": temporary}
            bridge.ROOT = Path(temporary)
            bridge.JOBS = Path(temporary) / "jobs"
            general.MODELS = Path(temporary) / "models"
            try:
                with patch.object(bridge, "config", return_value=test_config):
                    with patch.object(
                        bridge, "build_native", return_value=Path(temporary) / "w.exe"
                    ):
                        with patch.object(subprocess, "Popen"):
                            manifest = general.submit([{"op": "regenerate"}], None, "PRT001")
                model = general.model_info(manifest["model_id"])
                self.assertEqual(model["model_name"], "prt001")
            finally:
                bridge.ROOT, bridge.JOBS, general.MODELS = real_root, real_jobs, real_models


if __name__ == "__main__":
    unittest.main()
