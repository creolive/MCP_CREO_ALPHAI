"""DEV-049 T06: offline contract for the seed matrix driver and evidence gates."""

import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from creo_mechdog import inspection_refs
from tools import test_installation_loft as driver
from tools.test_feedback037_modeling import seeds
from tools.test_installation_loft import native_result_details, seed_cases

ROOT = Path(__file__).resolve().parents[2]

DISPATCH_POSITIVES = (
    "matrix_five_smooth",
    "matrix_four_smooth",
    "matrix_four_straight",
    "matrix_six_smooth",
    "matrix_six_straight",
    "matrix_three_smooth",
    "matrix_three_straight",
    "matrix_two_smooth",
    "matrix_two_straight",
    "rectangle_empty_A",
    "rectangle_explicit_B",
    "rectangle_empty_C",
    "rectangle_smooth_empty",
    "five_rectangle_empty",
    "five_airfoil_empty",
)
DISPATCH_NEGATIVES = ("invalid_seed_feature_id", "interpolation_mismatch")


def manifest():
    return json.loads((ROOT / "seed_library/seed_manifest.json").read_text("utf-8"))


class SeedRegressionContract(unittest.IsolatedAsyncioTestCase):
    def test_inline_result_and_missing_details(self):
        inspection = {"healthy": True, "features": [{"id": 60}], "volume_mm3": 7000}
        aliases = {"blend": {"feature_id": 60}}
        self.assertEqual(
            native_result_details({"result": {"inspection": inspection, "aliases": aliases}}),
            (inspection, aliases),
        )
        with self.assertRaisesRegex(AssertionError, "inspection"):
            native_result_details({"result": {"inspection_summary": {"healthy": True}}})

    def test_controlled_references_and_tampered_file(self):
        inspection = {"healthy": True, "features": [{"id": 60}], "volume_mm3": 7000}
        aliases = {"blend": {"feature_id": 60}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("bridge.ROOT", root):
                ref = inspection_refs.make_ref(inspection, root, "native")
                alias_ref = inspection_refs.make_ref(aliases, root, "aliases", prefix="detail")
                job = {"result": {"inspection_ref": ref, "aliases_ref": alias_ref}}
                self.assertEqual(native_result_details(job), (inspection, aliases))
                Path(ref["file"]).write_bytes(b"changed")
                with self.assertRaises(inspection_refs.InspectionRefInvalid):
                    native_result_details(job)

    async def test_seed_smoke_accepts_summary_and_legacy_inline(self):
        job_ids = ["a" * 32, "b" * 32]
        for field in ("inspection_summary", "inspection"):
            jobs = [
                {
                    "job_id": job_id,
                    "result": {
                        field: {"volume_mm3": 4900 * math.pi / 3},
                        "seed_load_evidence": {
                            "status": "loaded",
                            "evidence_persisted": True,
                            "creo_release_numeric": 44,
                        },
                    },
                }
                for job_id in job_ids
            ]
            validations = [
                {
                    "available": True,
                    "native_compatibility": {
                        "status": "not_verified_for_current_session",
                        "observations": [
                            {
                                "job_id": job_id,
                                "status": "loaded",
                                "seed_sha256": "7d" + "0" * 62,
                            }
                        ],
                    },
                }
                for job_id in job_ids
            ]
            probe = SimpleNamespace(
                job=AsyncMock(side_effect=jobs), call=AsyncMock(side_effect=validations)
            )
            await seeds(probe)
            self.assertEqual(probe.job.await_count, 2)
            self.assertEqual(probe.call.await_count, 2)

    def test_nine_distinct_baselines_and_six_extra_cases(self):
        cases = seed_cases(manifest())
        names = [name for case, name, _, _ in cases if case.startswith("matrix_")]
        expected = {
            "two_straight",
            "two_smooth",
            "three_straight",
            "three_smooth",
            "four_straight",
            "four_smooth",
            "five_smooth",
            "six_straight",
            "six_smooth",
        }
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), 9)
        self.assertEqual(len(cases) - len(names), 6)


class DispatchTableContract(unittest.TestCase):
    def test_positive_order_matches_the_dispatch_table(self):
        self.assertEqual(tuple(driver.POSITIVE_CASE_ORDER), DISPATCH_POSITIVES)
        self.assertEqual(tuple(driver.NEGATIVE_CASE_ORDER), DISPATCH_NEGATIVES)
        self.assertEqual(tuple(driver.ALL_CASE_ORDER), DISPATCH_POSITIVES + DISPATCH_NEGATIVES)

    def test_seed_cases_follow_the_fixed_order_and_cover_15_plus_2(self):
        cases = seed_cases(manifest())
        self.assertEqual([case for case, _, _, _ in cases], list(DISPATCH_POSITIVES))
        self.assertEqual(len(cases), 15)
        self.assertEqual(len(driver.ALL_CASE_ORDER), 17)

    def test_matrix_cases_carry_their_manifest_seed(self):
        names = {row["name"] for row in manifest()["seeds"]}
        for case, name, _, _ in seed_cases(manifest()):
            self.assertIn(name, names)
            if case.startswith("matrix_"):
                self.assertEqual(case, "matrix_" + name)

    def test_manifest_lists_nine_seeds_with_verifiable_hashes(self):
        library = driver.load_seed_library(ROOT / "seed_library")
        self.assertEqual(len(library["seeds"]), 9)
        self.assertEqual(len(library["hashes"]), 9)
        for record in library["seed_records"]:
            self.assertTrue(record["sha256_matches_manifest"])
            self.assertEqual(record["sha256"], library["seeds"][record["name"]]["sha256"])

    def test_a_tampered_seed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ROOT / "seed_library"
            (root / "seed_manifest.json").write_bytes((source / "seed_manifest.json").read_bytes())
            for row in manifest()["seeds"]:
                target = root / row["relative_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((source / row["relative_path"]).read_bytes())
            broken = root / manifest()["seeds"][0]["relative_path"]
            broken.write_bytes(broken.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                driver.load_seed_library(root)


class NegativeInputContract(unittest.TestCase):
    def setUp(self):
        self.library = driver.load_seed_library(ROOT / "seed_library")

    def test_negative_cases_change_exactly_one_field(self):
        for case in DISPATCH_NEGATIVES:
            with self.subTest(case=case):
                args = driver.negative_case_args(
                    case, self.library["seeds"], self.library["source_files"]
                )
                difference = driver.validate_negative_args(
                    case, args, self.library["seeds"], self.library["source_files"]
                )
                expected = (
                    ["seed_feature_id"] if case == "invalid_seed_feature_id" else ["interpolation"]
                )
                self.assertEqual(difference["expected_difference"], expected)
                self.assertEqual(difference["actual_difference"], expected)

    def test_invalid_feature_id_case_uses_the_stable_value(self):
        args = driver.negative_case_args(
            "invalid_seed_feature_id", self.library["seeds"], self.library["source_files"]
        )
        self.assertEqual(args["seed_feature_id"], 2147483647)
        self.assertEqual(args["seed_file"], str(self.library["source_files"]["two_straight"]))

    def test_interpolation_mismatch_opposes_the_seed(self):
        args = driver.negative_case_args(
            "interpolation_mismatch", self.library["seeds"], self.library["source_files"]
        )
        self.assertEqual(args["interpolation"], "smooth")
        self.assertEqual(self.library["seeds"]["two_straight"]["interpolation"], "straight")

    def test_negative_inputs_do_not_depend_on_loop_residue(self):
        stale = driver.create_args(
            self.library["seeds"]["five_smooth"],
            self.library["source_files"]["five_smooth"],
            dimensions=True,
            foil=True,
            model_name="t06_15_deadbeef",
        )
        stale["sections"][0]["dimensions"] = [{"name": "poison"}]
        stale["seed_feature_id"] = 7
        for case in DISPATCH_NEGATIVES:
            with self.subTest(case=case):
                args = driver.negative_case_args(
                    case, self.library["seeds"], self.library["source_files"]
                )
                self.assertEqual(
                    args["seed_file"], str(self.library["source_files"]["two_straight"])
                )
                self.assertEqual(len(args["sections"]), 2)
                self.assertEqual(args["sections"][0]["dimensions"], [])

    def test_each_negative_call_builds_an_independent_input(self):
        first = driver.negative_case_args(
            "invalid_seed_feature_id", self.library["seeds"], self.library["source_files"]
        )
        first["sections"][0]["offset"] = -1
        second = driver.negative_case_args(
            "invalid_seed_feature_id", self.library["seeds"], self.library["source_files"]
        )
        self.assertIsNot(first, second)
        self.assertIsNot(first["sections"], second["sections"])
        self.assertEqual(second["sections"][0]["offset"], 0)

    def test_an_illegal_negative_case_is_refused(self):
        with self.assertRaises(ValueError):
            driver.negative_case_args(
                "invalid_seed_feature_id_extra",
                self.library["seeds"],
                self.library["source_files"],
            )

    def test_a_negative_input_that_drifts_from_the_base_is_refused(self):
        args = driver.negative_case_args(
            "interpolation_mismatch", self.library["seeds"], self.library["source_files"]
        )
        args["label"] = "other"
        with self.assertRaisesRegex(ValueError, "only in"):
            driver.validate_negative_args(
                "interpolation_mismatch", args, self.library["seeds"], self.library["source_files"]
            )


class OutputPathContract(unittest.TestCase):
    def test_default_output_is_unique_per_run(self):
        first = driver.resolve_output(None, "run_aaa")
        second = driver.resolve_output(None, "run_bbb")
        self.assertNotEqual(first, second)
        self.assertEqual(first, ROOT / "build" / "dev049_t06" / "run_aaa" / "report.json")
        self.assertEqual(second, ROOT / "build" / "dev049_t06" / "run_bbb" / "report.json")

    def test_an_existing_report_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                driver.resolve_output(stale, "run_ccc")


class OfflineEntryContract(unittest.TestCase):
    def run_main(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = driver.main(argv)
        return code, output.getvalue()

    def offline_argv(self, *extra):
        return ["--seed-library", str(ROOT / "seed_library"), *extra]

    def test_default_run_is_offline_and_never_builds_a_client(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                with patch.object(driver, "live", new=AsyncMock()) as live:
                    code, text = self.run_main(self.offline_argv("--output", str(target)))
            self.assertEqual(code, 0)
            self.assertIn("OFFLINE ONLY", text)
            self.assertIn("hashes_verified=9", text)
            self.assertIn("positive_cases=15 negative_cases=2 validated", text)
            self.assertIn("LIVE NOT RUN", text)
            live.assert_not_awaited()
            client.assert_not_called()

    def test_offline_report_records_the_full_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            self.run_main(self.offline_argv("--output", str(target)))
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertFalse(report["live_run"])
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertEqual(len(report["source_hashes"]), 9)
            self.assertEqual([case["case"] for case in report["cases"]], list(DISPATCH_POSITIVES))
            self.assertEqual(
                [case["case"] for case in report["negative_case_inputs"]], list(DISPATCH_NEGATIVES)
            )
            for case in report["cases"]:
                self.assertTrue(case["validated"])
                self.assertTrue(case["seed_sha256_verified"])
            self.assertEqual(
                report["offline_checks"],
                {
                    "hashes_verified": 9,
                    "positive_cases_validated": 15,
                    "negative_cases_validated": 2,
                },
            )
            self.assertIn("source_fingerprint", report["provenance"])

    def test_a_single_live_flag_cannot_connect(self):
        for argv in (["--live"], ["--confirm-session-usable"]):
            with self.subTest(argv=argv):
                with tempfile.TemporaryDirectory() as directory:
                    target = Path(directory) / "report.json"
                    client = Mock(side_effect=AssertionError("MCP client must not be created"))
                    with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                        with patch.object(driver, "live", new=AsyncMock()) as live:
                            code, text = self.run_main(
                                self.offline_argv(*argv, "--output", str(target))
                            )
                self.assertEqual(code, 0)
                self.assertIn("OFFLINE ONLY", text)
                self.assertIn("both --live and --confirm-session-usable are required", text)
                live.assert_not_awaited()
                client.assert_not_called()

    def test_both_flags_reach_the_live_entry_point_only(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            with patch.object(driver, "live", new=AsyncMock()) as live:
                code, text = self.run_main(
                    self.offline_argv("--live", "--confirm-session-usable", "--output", str(target))
                )
        self.assertEqual(code, 0)
        self.assertEqual(text, f"report={target}\n")
        live.assert_awaited_once()

    def test_unknown_case_names_are_refused_before_connection(self):
        for argv in (["--case", "nope"], ["--case", "matrix_five_smooth", "--case", "nope"]):
            with self.subTest(argv=argv):
                client = Mock(side_effect=AssertionError("MCP client must not be created"))
                with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                    with patch.object(driver, "live", new=AsyncMock()) as live:
                        code, text = self.run_main(self.offline_argv(*argv))
                self.assertEqual(code, 2)
                self.assertIn("REFUSED BEFORE CONNECTION", text)
                self.assertIn("Unknown case name", text)
                live.assert_not_awaited()
                client.assert_not_called()

    def test_a_case_selected_twice_is_refused(self):
        code, text = self.run_main(
            self.offline_argv("--case", "matrix_five_smooth", "--case", "matrix_five_smooth")
        )
        self.assertEqual(code, 2)
        self.assertIn("never resubmit", text)

    def test_case_selection_runs_only_the_selected_items(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            code, text = self.run_main(
                self.offline_argv(
                    "--case",
                    "invalid_seed_feature_id",
                    "--case",
                    "matrix_five_smooth",
                    "--output",
                    str(target),
                )
            )
            self.assertEqual(code, 0)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["selection"], ["matrix_five_smooth", "invalid_seed_feature_id"])
            self.assertEqual([case["case"] for case in report["cases"]], ["matrix_five_smooth"])
            self.assertEqual(
                [case["case"] for case in report["negative_case_inputs"]],
                ["invalid_seed_feature_id"],
            )

    def test_an_existing_report_is_refused_before_any_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            for argv in ([], ["--live", "--confirm-session-usable"]):
                with self.subTest(argv=argv):
                    with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                        with patch.object(driver, "live", new=AsyncMock()) as live:
                            code, text = self.run_main(
                                self.offline_argv(*argv, "--output", str(stale))
                            )
                    self.assertEqual(code, 2)
                    self.assertIn("REFUSED BEFORE CONNECTION", text)
                    self.assertIn("Refusing to overwrite", text)
                    live.assert_not_awaited()
                    client.assert_not_called()


class ReportCombinationContract(unittest.TestCase):
    def test_one_source_fingerprint_may_be_summarized(self):
        summary = driver.summarize_reports(
            [
                {
                    "provenance": {"source_fingerprint": "abc"},
                    "cases": [{"case": "matrix_five_smooth", "passed": True}],
                },
                {
                    "provenance": {"source_fingerprint": "abc"},
                    "cases": [{"case": "matrix_four_smooth", "passed": False}],
                },
            ]
        )
        self.assertEqual(summary["source_fingerprint"], "abc")
        self.assertEqual(summary["passed_cases"], ["matrix_five_smooth"])

    def test_mixed_source_fingerprints_are_never_combined(self):
        with self.assertRaisesRegex(ValueError, "source_fingerprint"):
            driver.summarize_reports(
                [
                    {"provenance": {"source_fingerprint": "abc"}, "cases": []},
                    {"provenance": {"source_fingerprint": "def"}, "cases": []},
                ]
            )
