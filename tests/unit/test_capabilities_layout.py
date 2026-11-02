"""DEV-002: capability exports retain one implementation and admission rules."""

import importlib
import unittest
from unittest.mock import patch

import bridge
import generic_bridge


class CapabilitiesLayoutTests(unittest.TestCase):
    def test_legacy_exports_share_objects(self):
        implementation = importlib.import_module("creo_mechdog.capabilities")
        legacy = importlib.import_module("capabilities")
        for name in (
            "REGISTERED_OPERATIONS",
            "UNAVAILABLE_OPERATIONS",
            "require_available",
            "families",
        ):
            with self.subTest(export=name):
                self.assertIs(getattr(legacy, name), getattr(implementation, name))

    def test_unavailable_operation_still_rejected_before_submission(self):
        implementation = importlib.import_module("creo_mechdog.capabilities")
        with (
            patch.dict(implementation.UNAVAILABLE_OPERATIONS, {"loft": "fixture gate"}),
            patch.object(bridge, "toolkit_lock") as lock,
            patch("pathlib.Path.mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(ValueError, "no native job was queued"):
                generic_bridge.submit(
                    [{"op": "loft", "label": "transition", "sections": ["first", "second"]}]
                )
            lock.assert_not_called()
            mkdir.assert_not_called()

    def test_legacy_and_package_capability_data_agree(self):
        implementation = importlib.import_module("creo_mechdog.capabilities")
        legacy = importlib.import_module("capabilities")
        self.assertEqual(legacy.families(), implementation.families())
        self.assertEqual(
            len(set(implementation.REGISTERED_OPERATIONS)),
            len(implementation.REGISTERED_OPERATIONS),
        )


if __name__ == "__main__":
    unittest.main()
