"""Offline regressions for the BUG-110 acknowledgement driver (no Creo, no MCP).

The driver keeps three scopes apart (failure guard, ack success, part versus
assembly). These tests pin that separation: a handled failure, a part
acknowledgement or a clean script exit can never stand in for an assembly
acknowledgement success.
"""

import unittest

import tools.test_assembly_ack_failure as driver


def ack_success_case() -> dict:
    return {
        "case_id": "ASM",
        "scope": "ack_success",
        "model_type": "assembly",
        "failure": {"job_id": "job-1", "status": "failed"},
        "state_after_failure": {"status": "failed", "revision": 3, "pending_job": ""},
        "actions": [
            {"action": "retry_failed_job", "available": False, "reason": "unknown_outcome"},
            {"action": "ack_failure", "available": True, "reason": None},
        ],
        "apply": {
            "arguments": {"idempotency_key": "key-1", "confirm_failure_ack": True},
            "result": {"status": "ready", "action": "ack_failure", "revision": 3, "mode": "apply"},
            "before": {
                "revision": 3,
                "file_sha256": "a" * 64,
                "bindings": [{"component_id": 40, "feature_id": 7}],
            },
            "after": {
                "revision": 3,
                "file_sha256": "a" * 64,
                "bindings": [{"component_id": 40, "feature_id": 7}],
            },
        },
        "replay": {"same_key": True, "same_result": True, "second_mutation": False},
        "followup": {"status": "succeeded", "revision": 4},
        "verification_level": "live",
    }


def guard_case() -> dict:
    return {
        "case_id": "ASM",
        "scope": "failure_guard",
        "model_type": "assembly",
        "failure": {"job_id": "job-2", "status": "failed"},
        "state_after_failure": {"status": "ready", "revision": 3, "pending_job": ""},
        "actions": [{"action": "ack_failure", "available": False, "reason": "model is ready"}],
        "ack_refusal": {"message": "model is ready; nothing to acknowledge", "is_error": True},
        "verification_level": "live",
    }


class Coverage(unittest.TestCase):
    def test_ready_refusal_does_not_cover_ack_success(self):
        judged = driver.judge_ack_case(guard_case(), model_type="assembly")
        self.assertEqual(judged["verdict"], "pass", judged)
        self.assertFalse(judged["coverage"]["covers_ack_success"])
        self.assertEqual(judged["coverage"]["scope"], "failure_guard")

    def test_part_success_does_not_close_assembly_coverage(self):
        judged = driver.judge_ack_case(ack_success_case(), model_type="part")
        self.assertEqual(judged["verdict"], "pass", judged)
        self.assertTrue(judged["coverage"]["covers_ack_success"])
        self.assertFalse(judged["coverage"]["covers_assembly"])


class Invariance(unittest.TestCase):
    def test_ack_requires_unchanged_revision_files_and_bindings(self):
        case = ack_success_case()
        case["apply"]["after"]["revision"] = 4
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "fail", judged)
        self.assertIn(
            "revision_unchanged",
            [item["check"] for item in judged["checks"] if item["result"] == "fail"],
        )

        case = ack_success_case()
        case["apply"]["after"]["file_sha256"] = "b" * 64
        self.assertEqual(driver.judge_ack_case(case)["verdict"], "fail")

        case = ack_success_case()
        case["apply"]["after"]["bindings"] = [{"component_id": 41, "feature_id": 7}]
        self.assertEqual(driver.judge_ack_case(case)["verdict"], "fail")

    def test_missing_snapshot_fields_are_unverified(self):
        case = ack_success_case()
        case["apply"]["before"].pop("file_sha256")
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)


class Replay(unittest.TestCase):
    def test_ack_replay_uses_identical_arguments(self):
        case = ack_success_case()
        case["replay"]["second_mutation"] = True
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "fail", judged)
        self.assertIn(
            "replay_single_transaction",
            [item["check"] for item in judged["checks"] if item["result"] == "fail"],
        )

    def test_unknown_replay_key_is_unverified(self):
        case = ack_success_case()
        case["replay"] = {"same_key": False, "second_mutation": False, "same_result": True}
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)

    def test_replay_mutation_fails_even_without_same_key(self):
        case = ack_success_case()
        case["replay"] = {"same_key": False, "second_mutation": True, "same_result": True}
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "fail", judged)
        self.assertIn(
            "replay_single_transaction",
            [item["check"] for item in judged["checks"] if item["result"] == "fail"],
        )

    def test_replay_changed_result_fails_even_without_same_key(self):
        case = ack_success_case()
        case["replay"] = {"same_key": False, "second_mutation": False, "same_result": False}
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "fail", judged)
        self.assertIn(
            "replay_same_result",
            [item["check"] for item in judged["checks"] if item["result"] == "fail"],
        )

    def test_replay_without_outcome_evidence_is_unverified(self):
        case = ack_success_case()
        case["replay"] = {"same_key": True}
        judged = driver.judge_ack_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)

    def test_complete_acknowledgement_passes(self):
        judged = driver.judge_ack_case(ack_success_case(), model_type="assembly")
        self.assertEqual(judged["verdict"], "pass", judged)


if __name__ == "__main__":
    unittest.main()
