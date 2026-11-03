"""Offline regressions for the BUG-111 copy-batch driver (no Creo, no MCP).

The driver's live cases are data (``scenario_specs``) and its judgement is a
pure function (``judge_copy_case``), so both can be checked here. A ``pass``
verdict from a synthetic dictionary is a statement about the judgement only; it
never counts as live coverage of the fifth-copy failure.
"""

import unittest

import tools.test_geometry_transform_copies as driver

SAMPLE_POINTS = [[0, 0], [260, 0], [130, 20.9]]


def snapshot(revision=2, volume=28800.0, bodies=1) -> dict:
    return {
        "revision": revision,
        "status": "ready",
        "volume_mm3": volume,
        "counts": {"bodies": bodies, "features": 3, "surfaces": 6, "edges": 12},
    }


def failed_case(index: int = 4, *, rollback=True) -> dict:
    result = {
        "failed_operation_index": index,
        "failed_transform": {"operation_index": index, "angle_deg": -135.0},
    }
    if rollback:
        result.update({"rollback_status": "succeeded", "model_unchanged": True})
    return {
        "case_id": "C2",
        "scope": "copy_batch",
        "job_id": "job-1",
        "model_id": "model-1",
        "expectation": {"known_failure_index": 4},
        "request": {"operations": [[{"op": "geometry_transform", "rotation": [0, 0, -135.0]}]]},
        "receipt": {"status": "failed", "revision": 2, "result": result},
        "snapshots": {"before": snapshot(1, 28800.0, 1), "after": snapshot(2, 28800.0, 1)},
        "committed_operations": [0, 1, 2, 3],
    }


def succeeded_case(*, ops=4, reloaded=True, after=None) -> dict:
    return {
        "case_id": "C1",
        "scope": "copy_batch",
        "job_id": "job-2",
        "model_id": "model-2",
        "expectation": {"known_failure_index": None},
        "request": {"operations": []},
        "receipt": {
            "status": "succeeded",
            "revision": 2,
            "result": {"saved_file_reloaded_and_verified": reloaded},
        },
        "snapshots": {
            "before": snapshot(1, 28800.0, 1),
            "after": after if after is not None else snapshot(2, 30000.0, 1 + ops),
        },
        "committed_operations": list(range(ops)),
    }


class CaseTable(unittest.TestCase):
    def test_cases_use_independent_base_models(self):
        specs = driver.scenario_specs()
        self.assertEqual(
            [spec["case_id"] for spec in specs], ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
        )
        names = [spec["model_name"] for spec in specs]
        self.assertEqual(len(names), len(set(names)), "each case builds its own base model")
        for spec in specs:
            self.assertNotIn("model_id", spec, "cases must not inherit a previous model id")
            self.assertTrue(spec["model_name"])


class AngleAndLabelGrammar(unittest.TestCase):
    def test_in_range_angles_and_labels(self):
        for spec in driver.scenario_specs():
            refusal = spec.get("refusal_angle")
            if refusal is not None:
                self.assertGreater(refusal, 180.0, "the out-of-range control stays out of range")
            batches = spec.get("batches") or [spec["ops"]]
            for ops in batches:
                for op in ops:
                    angle = op["rotation"][2]
                    self.assertGreaterEqual(angle, -180.0)
                    self.assertLessEqual(angle, 180.0)
                    self.assertRegex(op["label"], driver.LABEL)
        labels = [
            op["label"]
            for spec in driver.scenario_specs()
            for ops in (spec.get("batches") or [spec["ops"]])
            for op in ops
        ]
        self.assertEqual(len(labels), len(set(labels)), "operation labels stay unique per run")


class Judgment(unittest.TestCase):
    def test_known_failure_only_passes_reproduction(self):
        case = failed_case()
        reproduce = driver.judge_copy_case(case, phase="reproduce")
        self.assertEqual(reproduce["verdict"], "pass", reproduce)
        verify = driver.judge_copy_case(case, phase="verify")
        self.assertEqual(verify["verdict"], "fail", verify)
        self.assertEqual(
            [item["check"] for item in verify["checks"] if item["result"] == "fail"],
            ["verify_requires_committed_batch"],
        )

    def test_missing_geometry_or_rollback_is_unverified(self):
        without_rollback = failed_case(rollback=False)
        judged = driver.judge_copy_case(without_rollback, phase="reproduce")
        self.assertEqual(judged["verdict"], "unverified", judged)

        incomplete = succeeded_case(after={"revision": 2})
        judged = driver.judge_copy_case(incomplete, phase="verify")
        self.assertEqual(judged["verdict"], "unverified", judged)

    def test_committed_batch_passes_verify_with_recorded_geometry(self):
        judged = driver.judge_copy_case(succeeded_case(ops=4), phase="verify")
        self.assertEqual(judged["verdict"], "pass", judged)

    def test_unknown_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            driver.judge_copy_case(succeeded_case(), phase="fixed")


if __name__ == "__main__":
    unittest.main()
