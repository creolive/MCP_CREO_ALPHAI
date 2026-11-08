import unittest
from unittest.mock import patch

import generic_bridge


class MassAssemblyAdmissionTest(unittest.TestCase):
    def test_query_refuses_managed_assembly_before_submission(self):
        with (
            patch.object(generic_bridge, "model_info", return_value={"model_type": "assembly"}),
            patch.object(generic_bridge, "submit") as submit,
            self.assertRaisesRegex(ValueError, "assemblies are unsupported"),
        ):
            generic_bridge.get_mass_properties("a" * 32, 7.85)
        submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
