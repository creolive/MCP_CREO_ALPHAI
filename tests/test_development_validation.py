import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creo_mechdog.schema import validate_operations
from generic_bridge import submit


class DevelopmentValidation(unittest.TestCase):
    def test_wrong_model_type_rejected_before_files_or_jobs(self):
        for op, model_type in [
            ({"op": "drawing_note", "label": "n", "lines": ["abc"], "position": [10, 20]}, "part"),
            ({"op": "export", "format": "pdf"}, "part"),
            ({"op": "export", "format": "step"}, "drawing"),
            ({"op": "extrude", "label": "e", "sketch": "s", "depth": 10}, "drawing"),
        ]:
            with (
                self.subTest(op=op),
                patch("generic_bridge.bridge.toolkit_lock"),
                patch("pathlib.Path.mkdir") as mkdir,
                patch("generic_bridge.subprocess.Popen") as start,
            ):
                with self.assertRaises(ValueError):
                    submit([op], model_type=model_type)
                mkdir.assert_not_called()
                start.assert_not_called()

    def test_udf_nonfinite_and_invalid_references(self):
        op = {
            "op": "udf_create",
            "label": "u",
            "file_path": "library.gph",
            "references": {"REF_CSYS": {"kind": "default_csys"}},
        }
        validate_operations([op])
        for change in [
            {"dimensions": {"d1": math.inf}},
            {"references": {"REF_CSYS": {"kind": "csys", "id": -1}}},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_operations([{**op, **change}])
        with (
            patch("generic_bridge.bridge.toolkit_lock"),
            patch("generic_bridge.bridge.admission_holder", return_value=None) as holder,
            patch("pathlib.Path.is_file", return_value=True),
            patch("generic_bridge.bridge.config", return_value={"creo_root": "C:/Creo"}),
            patch("pathlib.Path.mkdir") as mkdir,
            patch("generic_bridge.subprocess.Popen") as start,
        ):
            with self.assertRaisesRegex(ValueError, "absolute path"):
                submit([op])
            holder.assert_called_once_with()
            mkdir.assert_not_called()
            start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
