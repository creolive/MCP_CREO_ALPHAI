"""DEV-047 T01: public capability and local release summaries without Toolkit."""

import copy
import json
import unittest
from unittest.mock import patch

import server
from creo_mechdog import capabilities, capability_pages


class CapabilitySummaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        capability_pages.reset_snapshot()

    async def test_shipped_summaries_match_registered_tools_and_family_modes(self):
        tools = {tool.name for tool in await server.mcp.list_tools()}
        self.assertEqual(len(tools), 98)
        status = server._support_status()
        families = capabilities.families()
        for summary, family in (
            ("adoption", "model_adoption"),
            ("file_adoption", "file_adoption"),
            ("session_erase", "session_erase"),
            ("registry_maintenance", "registry_maintenance"),
        ):
            with self.subTest(summary=summary):
                entry = status[summary]
                self.assertTrue(families[family]["enabled"])
                listed = entry.get("tools", [entry.get("tool")])
                self.assertTrue(set(listed) <= tools)
                self.assertNotIn("not_available", entry["status"])
                self.assertNotIn("planned", entry["status"])
        self.assertEqual(status["adoption"]["actions"], ["inspect", "prepare", "apply"])
        self.assertIn("prepare", status["adoption"]["summary"])
        self.assertEqual(status["file_adoption"]["actions"], ["inspect", "apply"])
        self.assertEqual(status["file_adoption"]["maximum_paths"], 20)
        self.assertIn("path", status["file_adoption"]["summary"])
        self.assertIn("inspect", status["session_erase"]["summary"])
        self.assertIn("apply", status["registry_maintenance"]["summary"])

    async def test_disabled_family_does_not_claim_enabled_support(self):
        families = copy.deepcopy(capabilities.families())
        families["file_adoption"]["enabled"] = False
        with patch.object(server, "families", return_value=families):
            self.assertEqual(server._support_status()["file_adoption"]["status"], "not_available")

    async def test_compact_and_full_reconstruct_the_same_public_summary_under_budget(self):
        compact = await server.creo_capabilities()
        registered = {tool.name for tool in await server.mcp.list_tools()}
        self.assertEqual(compact["tool_count"], len(registered))
        self.assertLessEqual(len(json.dumps(compact, ensure_ascii=False).encode("utf-8")), 32768)
        overview = {}
        cursor = None
        while True:
            page = await server.creo_capabilities(
                detail="full", section="overview", limit=2, cursor=cursor
            )
            self.assertLessEqual(len(json.dumps(page, ensure_ascii=False).encode("utf-8")), 32768)
            overview.update({entry["key"]: entry["value"] for entry in page["entries"]})
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        self.assertEqual(compact["support_status"], overview["support_status"])
        self.assertEqual(compact["release_status"], overview["release_status"])
        self.assertEqual(compact["complete_creo_coverage"], overview["complete_creo_coverage"])


class SheetmetalInspectionProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_inspection_publishes_tri_state_and_snapshot_revision(self):
        native = {
            "revision": 4,
            "inspection": {
                "edges": [{"id": 12}],
                "wall_contour_check": {
                    "enabled": True,
                    "bounded": False,
                    "budget": 256,
                    "edges": [{"edge_id": 12, "wall_contour_query_code": 0}],
                },
            },
        }

        async def fake_invoke(*_args):
            return native

        with patch.object(server, "invoke", side_effect=fake_invoke):
            public = await server.creo_inspect_model("model", detail="full")
        check = public["inspection"]["wall_contour_check"]
        self.assertEqual(check["revision"], 4)
        self.assertEqual(check["edges"][0]["wall_contour_status"], "eligible")
        self.assertEqual(check["edges"][0]["wall_contour_query_code"], 0)
        self.assertEqual(native["inspection"]["edges"], [{"id": 12}])

    async def test_paged_metadata_projects_unknown_without_fabricating_edges(self):
        native = {
            "revision": 9,
            "data": {
                "metadata": [
                    {
                        "name": "wall_contour_check",
                        "value": {
                            "enabled": True,
                            "edges": [{"edge_id": 13, "wall_contour_query_code": -2}],
                        },
                    }
                ]
            },
        }

        async def fake_invoke(*_args):
            return native

        with patch.object(server, "invoke", side_effect=fake_invoke):
            public = await server.creo_inspect_model("model", detail="full", section="metadata")
        check = public["data"]["metadata"][0]["value"]
        self.assertEqual(check["revision"], 9)
        self.assertEqual(check["edges"][0]["wall_contour_status"], "unknown")
        self.assertEqual(check["edges"][0]["wall_contour_query_code"], -2)


class LocalReleaseStatusTests(unittest.TestCase):
    def test_local_version_maturity_is_independent_of_remote_update_cache(self):
        remote_cases = [
            {"status": "not_checked", "latest_version": None, "is_prerelease": None},
            {"status": "unknown", "latest_version": None, "is_prerelease": None},
            {
                "status": "checking",
                "latest_version": "0.7.0-rc.1",
                "is_prerelease": True,
                "stale": True,
            },
            {
                "status": "failed",
                "latest_version": "0.7.0-rc.1",
                "is_prerelease": True,
                "stale": True,
            },
            {"status": "up_to_date", "latest_version": "0.6.1", "is_prerelease": False},
        ]
        for version, expected in (
            ("0.6.1", "stable"),
            ("0.7.0+dev", "stable"),
            ("0.7.0-rc.1", "pre-release"),
            ("unparseable", "unknown"),
        ):
            for remote in remote_cases:
                with self.subTest(version=version, remote=remote["status"]):
                    with (
                        patch.object(server, "VERSION", version),
                        patch.object(server.updates, "snapshot", return_value=remote),
                        patch.object(server.seeds, "list_seeds", return_value={"seeds": []}),
                        patch.object(server, "callback_setup_status", return_value={}),
                    ):
                        payload = server._capabilities_payload([])
                    self.assertEqual(payload["release_status"], expected)
                    self.assertEqual(payload["update"], remote)
                    self.assertFalse(payload["complete_creo_coverage"])


def _enum_consts(prop: dict) -> set:
    """Collect literal values from a tool/op schema property (enum or anyOf-const)."""
    values = prop.get("enum")
    if values is not None:
        return set(values)
    return {item["const"] for item in prop.get("anyOf", []) if "const" in item}


class ExtrudeEnumContractTests(unittest.IsolatedAsyncioTestCase):
    """P05/FEAT-008: extrude depth_type/direction enums agree across the registered
    tool schema, the shared plan-operation model and the capabilities payload."""

    async def asyncSetUp(self):
        capability_pages.reset_snapshot()

    async def test_capabilities_express_depth_and_direction_separately(self):
        payload = server._capabilities_payload([])
        self.assertEqual(payload["extrude_depth_types"], ["blind", "through_all"])
        self.assertEqual(payload["extrude_directions"], ["positive", "negative", "symmetric"])
        self.assertEqual(payload["extrude_through_all_modes"], ["cut"])
        self.assertNotIn("extrude_depths", payload)
        # through_all_cut/symmetric must not masquerade as depth enum values
        self.assertNotIn("through_all_cut", payload["extrude_depth_types"])
        self.assertNotIn("symmetric", payload["extrude_depth_types"])

    async def test_tool_schema_enums_match_the_shared_operation_model(self):
        from creo_mechdog.schema import ExtrudeOp

        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        tool_props = tools["creo_extrude"].input_schema["properties"]
        model_props = ExtrudeOp.model_json_schema()["properties"]
        for field in ("mode", "direction", "depth_type"):
            with self.subTest(field=field):
                self.assertEqual(_enum_consts(tool_props[field]), _enum_consts(model_props[field]))

    async def test_standalone_tool_payload_is_a_valid_plan_operation(self):
        from creo_mechdog.schema import validate_operations

        # Exactly the dict the creo_extrude tool submits for a through cut.
        op = {
            "op": "extrude",
            "label": "enum_probe",
            "sketch": "sk",
            "depth": 5,
            "mode": "cut",
            "direction": "negative",
            "depth_type": "through_all",
            "new_body": False,
        }
        validated = validate_operations([op])
        self.assertEqual(validated[0]["depth_type"], "through_all")
        self.assertEqual(validated[0]["direction"], "negative")

    async def test_omitted_defaults_and_illegal_enums(self):
        from creo_mechdog.schema import validate_operations

        base = {"op": "extrude", "label": "enum_probe", "sketch": "sk"}
        defaulted = validate_operations([dict(base)])
        self.assertEqual(defaulted[0]["depth_type"], "blind")
        self.assertEqual(defaulted[0]["direction"], "positive")
        # through_all is a cut-only depth type; add mode is rejected
        with self.assertRaises(ValueError):
            validate_operations([{**base, "depth_type": "through_all", "mode": "add"}])
        for illegal_depth in ("through_all_cut", "symmetric"):
            with self.assertRaises(ValueError):
                validate_operations([{**base, "depth_type": illegal_depth}])
        for illegal_direction in ("blind", "through_all_cut"):
            with self.assertRaises(ValueError):
                validate_operations([{**base, "direction": illegal_direction}])

    async def test_tool_descriptions_state_the_renewed_contracts(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        extrude = tools["creo_extrude"].description
        self.assertIn('depth_type is "blind"', extrude)
        self.assertIn('"through_all" (cut mode only', extrude)
        plan = tools["creo_execute_plan"].description
        self.assertIn("Omit model_id to create a new model", plan)
        self.assertIn("creo_new_sheetmetal", plan)
        self.assertIn("never converts", plan)
        # plane normal filters match existing faces; they do not create planes
        for name in ("creo_datum_plane", "creo_create_sketch"):
            with self.subTest(tool=name):
                self.assertIn("matches an existing planar face", tools[name].description)
        # axis selection examples keep both supported kinds
        revolve = tools["creo_revolve"].description
        self.assertIn("{kind:'datum_axis_feature',", revolve)
        self.assertIn("{kind:'axis',id:N}", revolve)
        # round/chamfer face-pair examples name two existing faces
        for name in ("creo_round", "creo_chamfer"):
            with self.subTest(tool=name):
                references = tools[name].input_schema["properties"]["references"]
                self.assertIn("'surfaces':[{'kind':'surface','id':11}", references["description"])
                self.assertIn("existing faces", references["description"])
        # sheetmetal unbend family documents the bare fixed_surface reference
        for name in (
            "creo_sheetmetal_unbend",
            "creo_sheetmetal_flat_pattern",
            "creo_sheetmetal_bend_back",
        ):
            with self.subTest(tool=name):
                self.assertIn('{"kind":"surface","id":N}', tools[name].description)
        new_sheetmetal = tools["creo_new_sheetmetal"].description
        self.assertIn("terminal state", new_sheetmetal)
        self.assertIn("never converts", new_sheetmetal)
        # DEV-053 P08: the frozen depth/thickness frame contract, the standard
        # YZ recipe and the measured wall echo on the wall tool
        wall = tools["creo_sheetmetal_wall"].description
        self.assertIn("signed sketch normal", wall)
        self.assertIn("centered on the sketch line", wall)
        self.assertIn("examples/sheetmetal_base_yz.json", wall)
        self.assertIn("wall_face_ids", wall)
        self.assertIn("parameter_hint", wall)
        # candidate-edge discovery: tri-state, real query code, never an
        # unconditional flange promise, and edges picked by geometry
        flange = tools["creo_sheetmetal_flange"].description
        self.assertIn("wall_contour_check", flange)
        self.assertIn("eligible|ineligible|unknown", flange)
        self.assertIn("adjacent_bend_ends", flange)
        self.assertIn("green/white wall faces", flange)
        # the unbend family rejects non-surface fixed_surface references and
        # keeps the per-case native decision explicit
        for name in (
            "creo_sheetmetal_unbend",
            "creo_sheetmetal_flat_pattern",
            "creo_sheetmetal_bend_back",
        ):
            with self.subTest(tool=name):
                text = " ".join(tools[name].description.split())
                self.assertIn(
                    "datum_plane or edge reference is rejected before any feature exists", text
                )
                self.assertIn("no blanket", text)
