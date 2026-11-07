"""R04/FEAT-023: compact/sections over the real stdio MCP transport.

Offline only. A child process serves the real ``server.py`` against an isolated
data root with pre-built job directories; no job is submitted, no Toolkit
channel is touched and no Creo session is opened. Every assertion reads the
published tool result over stdio, so the response bytes, the protected-evidence
contract and the paging/cursor behaviour are observed as a client sees them.
"""

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bridge
from creo_mechdog.job_projection import LIST_ITEM_BUDGET
from creo_mechdog.model_queries import RESPONSE_BUDGET

MODEL_ID = "c" * 32
LONG_ERROR = "保存后重载校验失败：" + "轮廓在负方向偏移后与相邻壁面相交，" * 120


def operation(index: int, status: str = "succeeded") -> dict:
    return {
        "op": "sketch" if index % 2 == 0 else "extrude",
        "index": index,
        "label": f"op_{index:03d}",
        "succeeded": status == "succeeded",
        "execution_status": status,
        "effect_status": "committed" if status == "succeeded" else "rolled_back",
        "message": "ok",
    }


def manifest(
    job_id: str,
    count: int,
    *,
    status: str = "succeeded",
    failed_index: int | None = None,
    message: str = "Native PRT saved, reloaded and verified",
) -> dict:
    records = [
        operation(index, "failed" if index == failed_index else "succeeded")
        for index in range(count)
    ]
    result = {
        "success": status == "succeeded",
        "message": message,
        "code": 0,
        "toolkit_code": 0,
        "part_file": f"E:/jobs/{job_id}/output/model.prt.1",
        "sha256": "b" * 64,
        "saved_file_reloaded_and_verified": True,
        "rollback_succeeded": None,
        "rollback_status": "not_attempted",
        "model_unchanged": None,
        "preview": {"path": "preview.jpg", "width": 640, "height": 480, "bytes": 23111},
        "inspection": {"healthy": True, "features": []},
        "operations": records,
    }
    if failed_index is not None:
        failed = records[failed_index]
        failed.update(failed_stage="native_feature", failed_toolkit_call="ProFeatureCreate")
        result.update(
            success=False,
            failed_stage="native_feature",
            failed_toolkit_call="ProFeatureCreate",
            failed_operation_index=failed_index,
            failed_operation={
                "index": failed_index,
                "op": failed["op"],
                "label": failed["label"],
                "stage": "native_feature",
                "call": "ProFeatureCreate",
                "code": -1,
                "message": "native feature creation failed",
            },
        )
    return {
        "job_id": job_id,
        "kind": "generic",
        "model_id": MODEL_ID,
        "status": status,
        "revision": 3,
        "readonly": False,
        "created_at": "2026-11-06T00:00:00+00:00",
        "finished_at": "2026-11-06T00:01:00+00:00",
        "message": message,
        "operations": [{"op": "sketch", "label": f"op_{index:03d}"} for index in range(count)],
        "operations_view": "normalized",
        "result": result,
    }


def criteria_manifest(job_id: str) -> dict:
    """One job per judgement family, with the nulls and reasons left as reported."""
    value = manifest(job_id, 0)
    value["result"]["operations"] = [
        {
            "op": "surface_trim",
            "index": 0,
            "label": "trim_a",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "area_before_mm2": 1200.0,
            "area_before_status": "measured",
            "area_after_mm2": None,
            "area_after_status": "unavailable",
            "kept_side_basis": "larger_area",
            "kept_quilt_id": "quilt_b",
        },
        {
            "op": "surface_offset",
            "index": 1,
            "label": "offset_a",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "source_area_mm2": 800.0,
            "source_area_status": "measured",
            "offset_distance_mm": 5.0,
            "measured_offset_distance_mm": None,
            "offset_method": "volume_over_source_area",
        },
        {
            "op": "solidify",
            "index": 2,
            "label": "solidify_a",
            "succeeded": False,
            "execution_status": "failed",
            "effect_status": "rolled_back",
            "closure": {
                "available": False,
                "query_code": -7,
                "reason": "ProQuiltVolumeEval unavailable",
            },
        },
        {
            "op": "sheetmetal_flange",
            "index": 3,
            "label": "flange_a",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "miter_cuts": [{"end": 1, "angle_deg": None, "reason": "not_requested"}],
            "adjacent_bend_ends_allowed": True,
        },
        {
            "op": "assemble_component",
            "index": 4,
            "label": "pose_a",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "rotation_convention": "row_vector",
            "transform": None,
            "transform_source": "readback",
            "transform_code": -5,
            "length_unit": "mm",
        },
    ]
    value["result"]["planar_wall"] = {
        "thickness_validation": {
            "status": "unverified",
            "source": "missing_api",
            "value_mm": None,
            "reason": "ProSolidThicknessGet unavailable",
            "context": "current_plan",
        }
    }
    return value


def prepare_root(directory: Path) -> dict[str, str]:
    (directory / "jobs").mkdir()
    (directory / "models").mkdir()
    (directory / "config.json").write_text(
        json.dumps({"creo_root": "C:\\r04-fixture-creo"}), encoding="utf-8"
    )
    jobs = {
        "big": f"{1:032x}",
        "huge": f"{2:032x}",
        "failure": f"{3:032x}",
        "long_error": f"{4:032x}",
        "criteria": f"{5:032x}",
        "miter": f"{6:032x}",
    }
    fixtures = {
        jobs["big"]: manifest(jobs["big"], 35),
        jobs["huge"]: manifest(jobs["huge"], 1000),
        jobs["failure"]: manifest(jobs["failure"], 35, status="failed", failed_index=34),
        jobs["long_error"]: manifest(jobs["long_error"], 3, status="failed", message=LONG_ERROR),
        jobs["criteria"]: criteria_manifest(jobs["criteria"]),
    }
    legacy_miter = manifest(jobs["miter"], 1)
    legacy_miter["result"]["operations"][0].update(op="sheetmetal_flange", label="wall")
    legacy_miter["result"]["aliases"] = {
        "wall": {
            "miter_cuts": {"add": 1, "requested": True, "width_mm": 1.0, "offset_mm": 1.0},
            "adjacent_bend_ends_allowed": {"allowed_by_miter_cut": True, "edge_id": 266},
        }
    }
    fixtures[jobs["miter"]] = legacy_miter
    # Pad the list to the 50-item query limit with small successful jobs.
    for index in range(7, 53):
        job_id = f"{index:032x}"
        fixtures[job_id] = manifest(job_id, 2)
    for job_id, value in fixtures.items():
        path = directory / "jobs" / job_id
        path.mkdir(parents=True)
        bridge.write_json(path / "job.json", value)
        (path / "native.log").write_text("PHASE=done\n", encoding="utf-8")
    return jobs


def child_serve(directory: Path) -> None:
    """Serve the real server.py over stdio against the isolated data root."""
    import generic_bridge as general
    import server

    bridge.ROOT = directory
    bridge.JOBS = directory / "jobs"
    general.MODELS = directory / "models"
    with patch.object(server.startup, "start"), patch.object(server.updates, "start"):
        server.mcp.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="R04 job query stdio fixture")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.serve:
        child_serve(args.data_root)


class JobQueryProtocol(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="r04_protocol_")
        cls.directory = Path(cls.temporary.name)
        cls.jobs = prepare_root(cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def client(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        return Client(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "tests.unit.test_job_query_protocol",
                    "--data-root",
                    str(self.directory),
                    "--serve",
                ],
                cwd=str(ROOT),
            ),
            read_timeout_seconds=60,
        )

    async def call(self, client, arguments: dict, *, error: bool = False):
        reply = await client.call_tool("creo_get_job", arguments)
        self.assertEqual(bool(reply.is_error), error, reply)
        return reply

    @staticmethod
    def payload(reply) -> bytes:
        return reply.content[0].text.encode("utf-8")

    async def test_compact_projection_is_bounded_utf8(self):
        async with self.client() as client:
            reply = await self.call(client, {"job_id": self.jobs["big"], "detail": "compact"})
            raw = self.payload(reply)
            self.assertLessEqual(len(raw), RESPONSE_BUDGET)
            self.assertEqual(raw.decode("utf-8"), reply.content[0].text)
            job = reply.structured_content
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["detail"], "compact")
            self.assertNotIn("native_log_tail", job)
            result = job["result"]
            self.assertEqual(result["operations_total"], 35)
            self.assertFalse(result["operations_truncated"])
            self.assertNotIn("log_tail", json.dumps(result))

    async def test_legacy_miter_aliases_reach_public_views(self):
        async with self.client() as client:
            for arguments in (
                {"detail": "compact"},
                {"detail": "compact", "sections": ["miter_cuts", "adjacent_bend_ends_allowed"]},
                {"detail": "full"},
                {"detail": "full", "section": "operations_result"},
            ):
                reply = await self.call(client, {"job_id": self.jobs["miter"], **arguments})
                view = reply.structured_content
                self.assertLessEqual(len(self.payload(reply)), RESPONSE_BUDGET)
                records = (
                    view["data"]["operations_result"]
                    if "data" in view
                    else view["result"]["operations"]
                )
                self.assertEqual(records[0]["miter_cuts"]["width_mm"], 1.0)
                self.assertTrue(records[0]["adjacent_bend_ends_allowed"]["allowed_by_miter_cut"])

    async def test_thousand_operation_job_keeps_counts_and_bound(self):
        async with self.client() as client:
            reply = await self.call(client, {"job_id": self.jobs["huge"], "detail": "compact"})
            self.assertLessEqual(len(self.payload(reply)), RESPONSE_BUDGET)
            result = reply.structured_content["result"]
            self.assertEqual(result["operations_total"], 1000)
            self.assertTrue(result["operations_truncated"])
            self.assertLessEqual(len(result["operations"]), 20)
            self.assertEqual(sum(result["operations_status_counts"].values()), 1000)

    async def test_failure_outside_the_sample_keeps_its_evidence(self):
        async with self.client() as client:
            reply = await self.call(client, {"job_id": self.jobs["failure"], "detail": "compact"})
            self.assertLessEqual(len(self.payload(reply)), RESPONSE_BUDGET)
            result = reply.structured_content["result"]
            self.assertEqual(result["failed_operation_index"], 34)
            self.assertEqual(result["failed_operation"]["label"], "op_034")
            records = result["operations"]
            self.assertTrue(any(record["index"] == 34 for record in records), records)
            kept = next(record for record in records if record["index"] == 34)
            self.assertEqual(kept["execution_status"], "failed")
            self.assertEqual(kept["failed_stage"], "native_feature")
            self.assertEqual(kept["failed_toolkit_call"], "ProFeatureCreate")

    async def test_long_chinese_failure_message_is_protected(self):
        async with self.client() as client:
            reply = await self.call(
                client, {"job_id": self.jobs["long_error"], "detail": "compact"}
            )
            raw = self.payload(reply)
            self.assertLessEqual(len(raw), RESPONSE_BUDGET)
            job = reply.structured_content
            self.assertEqual(job["message"], LONG_ERROR)
            self.assertEqual(job["result"]["message"], LONG_ERROR)
            self.assertIn(LONG_ERROR, raw.decode("utf-8"))

    async def test_sections_matrix_and_outcome_consistency(self):
        big = self.jobs["big"]
        async with self.client() as client:
            omitted = (
                await self.call(client, {"job_id": big, "detail": "compact"})
            ).structured_content
            self.assertNotIn("sections_applied", omitted)
            empty = (
                await self.call(client, {"job_id": big, "detail": "compact", "sections": []})
            ).structured_content
            self.assertEqual(empty["sections_applied"], [])
            self.assertNotIn("preview", empty["result"])
            self.assertNotIn("operations", empty["result"])
            selected = (
                await self.call(
                    client, {"job_id": big, "detail": "compact", "sections": ["preview"]}
                )
            ).structured_content
            self.assertEqual(selected["sections_applied"], ["preview"])
            self.assertIn("preview", selected["result"])
            self.assertNotIn("inspection", selected["result"])
            self.assertEqual(selected["result"]["operations_total"], 35)
            self.assertNotIn("profile", selected["result"]["operations"][0])
            operations = (
                await self.call(
                    client, {"job_id": big, "detail": "compact", "sections": ["operations"]}
                )
            ).structured_content
            self.assertEqual(operations["sections_applied"], ["operations"])
            self.assertIn("operations", operations["result"])
            self.assertNotIn("preview", operations["result"])
            rejected = await self.call(
                client,
                {"job_id": big, "detail": "compact", "sections": ["missing_block"]},
                error=True,
            )
            message = str(rejected)
            for name in ("missing_block", "preview", "operations", "extrude_depth"):
                self.assertIn(name, message)
            full = (await self.call(client, {"job_id": big, "detail": "full"})).structured_content
            for key in ("status", "revision", "message", "code", "part_file", "sha256"):
                self.assertEqual(selected.get(key), full.get(key), key)
                self.assertEqual(omitted.get(key), full.get(key), key)

    async def test_compact_criteria_match_full_over_stdio(self):
        criteria = self.jobs["criteria"]
        async with self.client() as client:
            compact = (
                await self.call(client, {"job_id": criteria, "detail": "compact"})
            ).structured_content
            full = (
                await self.call(client, {"job_id": criteria, "detail": "full"})
            ).structured_content
            self.assertEqual(compact["result"]["planar_wall"], full["result"]["planar_wall"])
            self.assertEqual(
                compact["result"]["planar_wall"]["thickness_validation"]["value_mm"], None
            )
            compact_records = {
                record["label"]: record for record in compact["result"]["operations"]
            }
            full_records = {record["label"]: record for record in full["result"]["operations"]}
            for label, record in compact_records.items():
                with self.subTest(label=label):
                    for key, value in record.items():
                        self.assertEqual(full_records[label][key], value, key)
            self.assertIsNone(compact_records["trim_a"]["area_after_mm2"])
            self.assertEqual(compact_records["trim_a"]["area_after_status"], "unavailable")
            self.assertIsNone(compact_records["offset_a"]["measured_offset_distance_mm"])
            self.assertEqual(compact_records["offset_a"]["source_area_status"], "measured")
            self.assertIs(compact_records["solidify_a"]["closure"]["available"], False)
            self.assertEqual(compact_records["solidify_a"]["closure"]["query_code"], -7)
            self.assertEqual(
                compact_records["solidify_a"]["closure"]["reason"],
                "ProQuiltVolumeEval unavailable",
            )
            self.assertIsNone(compact_records["flange_a"]["miter_cuts"][0]["angle_deg"])
            self.assertEqual(
                compact_records["flange_a"]["miter_cuts"][0]["reason"], "not_requested"
            )
            self.assertIsNone(compact_records["pose_a"]["transform"])
            self.assertEqual(compact_records["pose_a"]["transform_code"], -5)

    async def test_full_section_cursor_round_trip(self):
        big = self.jobs["big"]
        async with self.client() as client:
            assembled: list[dict] = []
            cursor = None
            for _ in range(20):
                arguments = {
                    "job_id": big,
                    "detail": "full",
                    "section": "operations_input",
                    "limit": 5,
                }
                if cursor is not None:
                    arguments["cursor"] = cursor
                page = (await self.call(client, arguments)).structured_content
                self.assertEqual(page["operations_view"], "normalized")
                self.assertEqual(page["section"], "operations_input")
                assembled.extend(page["data"]["operations_input"])
                cursor = page["next_cursor"]
                if page["complete"]:
                    break
            self.assertIsNone(cursor)
            self.assertEqual(len(assembled), 35)
            self.assertEqual(
                assembled, [{"op": "sketch", "label": f"op_{index:03d}"} for index in range(35)]
            )

    async def test_fifty_compact_list_items_are_bounded(self):
        async with self.client() as client:
            reply = await client.call_tool("creo_list_jobs", {"limit": 50})
            for item in reply.structured_content["jobs"]:
                with self.subTest(job_id=item["job_id"]):
                    encoded = len(json.dumps(item, ensure_ascii=False).encode("utf-8"))
                    self.assertLessEqual(encoded, LIST_ITEM_BUDGET)
                    self.assertNotIn("result", item)
                    self.assertNotIn("sections_applied", item)


if __name__ == "__main__":
    main()
