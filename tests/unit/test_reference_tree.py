"""The reference tree reader keeps its evidence shape."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "read_reference_tree.py"


class ReferenceTreeReaderTests(unittest.TestCase):
    def test_the_tool_exists_and_documents_the_route(self):
        text = TOOL.read_text(encoding="utf-8")
        self.assertIn("creo_adopt_file", text)
        self.assertIn("dump_tree", text)
        self.assertIn("--model-id", text)

    def test_the_tree_summary_reports_the_elements(self):
        import sys

        sys.path.insert(0, str(ROOT / "tools"))
        from read_reference_tree import summarize_tree

        xml_text = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<PRO_E_FEATURE_TREE type="compound">\n'
            '  <PRO_E_FEATURE_TYPE type="int">PRO_FEAT_CURVE</PRO_E_FEATURE_TYPE>\n'
            '  <PRO_E_STD_FEATURE_NAME type="wstring">LOFT_BOTTOM</PRO_E_STD_FEATURE_NAME>\n'
            '  <PRO_E_STD_SECTION type="compound">\n'
            '    <PRO_E_STD_SEC_BLN_VERTS type="selection"></PRO_E_STD_SEC_BLN_VERTS>\n'
            "  </PRO_E_STD_SECTION>\n"
            "</PRO_E_FEATURE_TREE>\n"
        )
        summary = summarize_tree(xml_text)
        self.assertEqual(summary["feature_type"], "PRO_FEAT_CURVE")
        self.assertEqual(summary["feature_name"], "LOFT_BOTTOM")
        self.assertIn("PRO_E_STD_SEC_BLN_VERTS", summary["elements"])
        self.assertFalse(summary["has_blend_elements"])

    def test_the_contract_records_the_blend_verdict(self):
        contract = (ROOT / "docs" / "development" / "G5-NATIVE-CONTRACT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("ProFeatureElemtreeExtract", contract)
        self.assertIn("-18", contract)

    def test_the_loft_gate_cites_the_measured_verdict(self):
        from creo_mechdog.capabilities import require_available

        with self.assertRaises(ValueError) as caught:
            require_available(
                [
                    {
                        "op": "loft",
                        "label": "loft_surface",
                        "sections": ["a"],
                        "mode": "surface",
                    }
                ]
            )
        self.assertIn("-18", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
