"""BUG-113 / R02: directed save-and-rollback failure repro driver.

Default mode is offline: it freezes the repro matrix, replays the four existing
offline error classes, and applies the R02 decision table to synthetic evidence.
Nothing here connects to Creo unless both ``--live`` and
``--confirm-session-usable`` are given, and the live run never injects a hang,
restarts Creo, clears IPC state, retries a failed Backup or acknowledges a
failure automatically.

Frozen matrix (2 routes x 2 tool kinds x 3 independent models = 12 cases):

* ``single_plan`` groups the surface -> trim -> thicken chain into the fewest
  submissions that runtime curve ids allow (independent plane: 1; projected
  curve: 3 because the projection output id is only known after it runs);
* ``incremental`` appends one operation group per job to the saved model
  (independent plane: 3; projected curve: 4).
* ``independent_plane`` trims with a datum plane built from the base planes;
  ``projected_dependency`` trims with the curve produced by ``project_curve``.

Every case allows one attempt per submission and records the attempt list; a
failure is recorded and the driver moves on to the next independent model.

The legacy offline regressions live in
``tests/unit/test_surface_save_recovery.py``; the added R02 judgments live in
``tests/unit/test_surface_save_recovery.py`` too, and this driver imports the
same production helpers instead of re-implementing the decision.

Example (PowerShell, from the repo root):
.venv\\Scripts\\python.exe tools\\test_surface_save_recovery.py
.venv\\Scripts\\python.exe tools\\test_surface_save_recovery.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import (
        call_tool,
        curve_id_of,
        feature_named,
        section,
        submit_plan,
    )
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import (
        call_tool,
        curve_id_of,
        feature_named,
        section,
        submit_plan,
    )
sys.path.insert(0, str(ROOT))

import generic_bridge as general  # noqa: E402
from creo_mechdog import operation_results  # noqa: E402
from version import VERSION  # noqa: E402

BUSY_EXIT = 2
OVERWRITE_EXIT = 3

ROUTES = ("single_plan", "incremental")
TOOL_KINDS = ("independent_plane", "projected_dependency")
MODELS_PER_CASE = 3
CHAIN = ("surface_fill", "surface_trim", "thicken")
SUBMIT_BUDGETS = {
    ("single_plan", "independent_plane"): 1,
    ("single_plan", "projected_dependency"): 3,
    ("incremental", "independent_plane"): 3,
    ("incremental", "projected_dependency"): 4,
}
EVIDENCE_KEYS = (
    "save_failure",
    "rollback_difference",
    "part_sha256",
    "revision",
    "recovery_action",
)
SNAPSHOT_KEYS = ("part_file", "part_sha256", "revision")

LIVE_WIDTH = 40.0
LIVE_HEIGHT = 20.0
LIVE_X = 5.0
LIVE_THICKNESS = 2.0
LIVE_SOURCE_Z = 10.0


def frozen_cases() -> list[dict]:
    """The R02 matrix. Every case is a fresh model; nothing is reused."""
    return [
        {
            "case_id": f"{route}:{tool}:m{index}",
            "route": route,
            "tool": tool,
            "model_index": index,
            "chain": list(CHAIN),
            "submit_budget": SUBMIT_BUDGETS[(route, tool)],
            "max_attempts_per_submission": 1,
            "resubmit_on_failure": False,
            "required_evidence": list(EVIDENCE_KEYS),
        }
        for route in ROUTES
        for tool in TOOL_KINDS
        for index in range(MODELS_PER_CASE)
    ]


def baseline_snapshot(model: dict | None) -> dict:
    """The saved identity a failed job must leave untouched."""
    model = model or {}
    return {key: model.get(key) for key in SNAPSHOT_KEYS}


def baseline_invariants(before: dict, after: dict) -> dict:
    checks = {key: before.get(key) == after.get(key) for key in SNAPSHOT_KEYS}
    return {
        "unchanged": all(checks.values()),
        "checks": checks,
        "before": before,
        "after": after,
    }


def failure_verdict(request: dict, manifest: dict, result: dict, before: dict, after: dict) -> dict:
    """Apply the R02 decision table to the evidence the driver actually read.

    ``unknown_outcome`` keeps its protection: nothing is cleared. A failed job
    may be ``ready`` only when the existing native rule allows it AND every
    saved identity field is unchanged. A matched feature/body count or an equal
    volume is diagnostic only; on its own it never clears the protection.
    """
    status = manifest.get("status")
    invariants = baseline_invariants(before, after)
    if status == "unknown_outcome":
        return {
            "model_status": "unknown_outcome",
            "protection": "unknown_outcome",
            "reasons": ["the native outcome was not confirmed; do not resubmit"],
            "baseline": invariants,
        }
    if status == "succeeded":
        return {
            "model_status": "ready",
            "protection": None,
            "reasons": ["the job succeeded and reported a verified save"],
            "baseline": invariants,
        }
    annotated = operation_results.annotate_native_result(
        dict(result), readonly=bool(request.get("readonly"))
    )
    rule_status = general.failed_model_status(
        request, annotated, {"part_file": before.get("part_file")}
    )
    ready = rule_status == "ready" and invariants["unchanged"]
    reasons: list[str] = []
    if (
        annotated.get("rollback_succeeded") is not True
        and annotated.get("model_unchanged") is not True
    ):
        reasons.append("the checkpoint restore was not verified")
    if not invariants["unchanged"]:
        changed = [key for key, ok in invariants["checks"].items() if not ok]
        reasons.append("the saved identity changed: " + ", ".join(changed))
    difference = annotated.get("rollback_difference") or {}
    if difference.get("status") == "matched":
        reasons.append("matched counts/volume are diagnostic only")
    return {
        "model_status": "ready" if ready else "failed",
        "rule_status": rule_status,
        "protection": None if ready else "failed",
        "rollback_succeeded": annotated.get("rollback_succeeded") is True,
        "difference_status": difference.get("status"),
        "save_failure": annotated.get("save_failure"),
        "baseline": invariants,
        "reasons": reasons,
    }


def checks():
    items: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        items.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    return items, check


# ---------------------------------------------------------------------------
# Reused offline fixtures (the four existing BUG-113 error classes).
# ---------------------------------------------------------------------------


def save_failure_block(**overrides) -> dict:
    block = {
        "call": "ProMdlnameBackup",
        "code": -1,
        "stage": "verify_model_save",
        "destination": "recovery.prt",
        "source_checkpoint": "recovery.prt.4",
        "candidate_files": {
            "available": True,
            "total": 1,
            "truncated": False,
            "sample": ["recovery.prt.4"],
        },
    }
    block.update(overrides)
    return block


def collection(before_ids: list[int], after_ids: list[int], **overrides) -> dict:
    missing = [item for item in before_ids if item not in after_ids]
    added = [item for item in after_ids if item not in before_ids]
    block = {
        "available": True,
        "before": len(before_ids),
        "after": len(after_ids),
        "missing_ids": {"total": len(missing), "truncated": False, "sample": missing},
        "added_ids": {"total": len(added), "truncated": False, "sample": added},
        "reason": None,
    }
    block.update(overrides)
    return block


def difference_block(**overrides) -> dict:
    block = {
        "available": True,
        "status": "mismatch",
        "reason": "Saved feature/body count changed",
        "features": collection([1, 2, 3], [1, 2, 3, 4]),
        "bodies": collection([10], [10]),
        "volume_mm3": {"available": True, "before": 1000.0, "after": 1000.0, "reason": None},
    }
    block.update(overrides)
    return block


def matched_block(**overrides) -> dict:
    block = difference_block(
        status="matched",
        reason=None,
        features=collection([1, 2, 3], [1, 2, 3]),
        bodies=collection([10], [10]),
        volume_mm3={"available": True, "before": 1000.0, "after": 1000.0, "reason": None},
    )
    block.update(overrides)
    return block


def failed_result(**overrides) -> dict:
    result = {
        "success": False,
        "saved_file_reloaded_and_verified": False,
        "rollback_succeeded": False,
        "message": "Toolkit call ProMdlnameBackup(board, destination) failed with code -1 "
        "during verify_model_save",
        "toolkit_code": -1,
        "operations": [
            {
                "op": "thicken",
                "index": 0,
                "label": "recovery_solid",
                "succeeded": False,
                "execution_status": "failed",
            }
        ],
    }
    result.update(overrides)
    return result


def baseline_model(**overrides) -> dict:
    model = {
        "model_id": "m" * 32,
        "status": "ready",
        "part_file": r"E:\models\recovery\output\recovery.prt.4",
        "part_sha256": "a" * 64,
        "revision": 7,
    }
    model.update(overrides)
    return model


def case_matrix_offline() -> dict:
    """The matrix is frozen data; drift is a failure, not a new scenario."""
    items, check = checks()
    cases = frozen_cases()
    check("twelve_independent_cases", len(cases) == 12, {"count": len(cases)})
    check(
        "case_ids_unique",
        len({case["case_id"] for case in cases}) == len(cases),
    )
    by_route: dict[str, dict[str, int]] = {}
    for case in cases:
        by_route.setdefault(case["route"], {})
        by_route[case["route"]][case["tool"]] = by_route[case["route"]].get(case["tool"], 0) + 1
    check(
        "three_models_per_route_and_tool",
        all(
            by_route.get(route, {}).get(tool) == MODELS_PER_CASE
            for route in ROUTES
            for tool in TOOL_KINDS
        ),
        {"by_route": by_route},
    )
    check(
        "submit_budgets_frozen",
        all(
            case["submit_budget"] == SUBMIT_BUDGETS[(case["route"], case["tool"])] for case in cases
        ),
        {
            "budgets": [
                f"{route}:{tool}={budget}" for (route, tool), budget in SUBMIT_BUDGETS.items()
            ]
        },
    )
    check(
        "one_attempt_per_submission",
        all(case["max_attempts_per_submission"] == 1 for case in cases),
    )
    check(
        "no_automatic_resubmission",
        all(case["resubmit_on_failure"] is False for case in cases),
    )
    check(
        "evidence_requirements_frozen",
        all(tuple(case["required_evidence"]) == EVIDENCE_KEYS for case in cases),
    )
    check("chain_is_surface_trim_thicken", all(tuple(case["chain"]) == CHAIN for case in cases))
    check(
        "model_indexes_are_independent_slots",
        sorted({case["model_index"] for case in cases}) == list(range(MODELS_PER_CASE)),
    )
    passed = all(item["ok"] for item in items)
    return {
        "mode": "offline",
        "passed": passed,
        "native_save_recovery": "not_verified",
        "checks": items,
    }


def case_existing_regressions_offline() -> dict:
    """The four error classes already covered by the retained unit module."""
    items, check = checks()
    model = baseline_model()
    before = baseline_snapshot(model)

    normalized = operation_results.normalize_save_failure(save_failure_block())
    check(
        "failed_backup_keeps_raw_call_code_stage",
        normalized["call"] == "ProMdlnameBackup"
        and normalized["code"] == -1
        and normalized["stage"] == "verify_model_save",
        {"save_failure": normalized},
    )
    annotated = operation_results.annotate_native_result(
        failed_result(save_failure=save_failure_block()), readonly=False
    )
    check(
        "failed_backup_does_not_rewrite_the_message",
        "ProMdlnameBackup" in annotated["message"] and annotated["toolkit_code"] == -1,
        {"message": annotated["message"]},
    )
    verdict = failure_verdict({}, {"status": "failed"}, annotated, before, baseline_snapshot(model))
    check(
        "failed_backup_without_restore_stays_failed",
        verdict["model_status"] == "failed",
        {"verdict": verdict},
    )

    load_failure = {
        "available": False,
        "status": "unavailable",
        "reason": "checkpoint reload failed with code -27",
        "features": {
            "available": False,
            "before": None,
            "after": None,
            "missing_ids": None,
            "added_ids": None,
            "reason": "baseline inspection carries no features",
        },
        "bodies": {
            "available": False,
            "before": None,
            "after": None,
            "missing_ids": None,
            "added_ids": None,
            "reason": "baseline inspection carries no bodies",
        },
        "volume_mm3": {
            "available": False,
            "before": None,
            "after": None,
            "reason": "volume was not measured on both sides",
        },
    }
    normalized = operation_results.normalize_rollback_difference(load_failure)
    check(
        "checkpoint_reload_failure_is_unavailable_with_reason",
        normalized["status"] == "unavailable" and "code -27" in normalized["reason"],
        {"rollback_difference": normalized},
    )
    annotated = operation_results.annotate_native_result(
        failed_result(rollback_code=-27, rollback_difference=load_failure), readonly=False
    )
    check(
        "checkpoint_reload_failure_keeps_effect_unknown",
        annotated["rollback_succeeded"] is False
        and annotated["operations"][0]["effect_status"] == "unknown",
        {"result": annotated},
    )

    mismatch = operation_results.normalize_rollback_difference(difference_block())
    check(
        "count_mismatch_with_equal_volume_is_a_mismatch",
        mismatch["status"] == "mismatch" and mismatch["features"]["added_ids"]["sample"] == [4],
        {"rollback_difference": mismatch},
    )
    annotated = operation_results.annotate_native_result(
        failed_result(rollback_difference=difference_block()), readonly=False
    )
    verdict = failure_verdict({}, {"status": "failed"}, annotated, before, baseline_snapshot(model))
    check(
        "count_mismatch_cannot_become_ready",
        verdict["model_status"] == "failed" and verdict["difference_status"] == "mismatch",
        {"verdict": verdict},
    )

    annotated = operation_results.annotate_native_result(
        failed_result(rollback_succeeded=True, rollback_difference=matched_block()), readonly=False
    )
    verdict = failure_verdict({}, {"status": "failed"}, annotated, before, baseline_snapshot(model))
    check(
        "verified_restore_keeps_the_existing_ready_rule",
        verdict["model_status"] == "ready"
        and annotated["operations"][0]["effect_status"] == "rolled_back",
        {"verdict": verdict},
    )

    passed = all(item["ok"] for item in items)
    return {
        "mode": "offline",
        "passed": passed,
        "native_save_recovery": "not_verified",
        "checks": items,
    }


def case_r02_judgments_offline() -> dict:
    """The new R02 scenarios: unknown protection and baseline identity."""
    items, check = checks()
    model = baseline_model()
    before = baseline_snapshot(model)

    unknown = failure_verdict({}, {"status": "unknown_outcome"}, {}, before, before)
    check(
        "unknown_outcome_is_never_ready",
        unknown["model_status"] == "unknown_outcome" and unknown["protection"] == "unknown_outcome",
        {"verdict": unknown},
    )
    matched_unknown = failure_verdict(
        {},
        {"status": "unknown_outcome"},
        failed_result(rollback_difference=matched_block()),
        before,
        before,
    )
    check(
        "matched_counts_do_not_clear_unknown_outcome",
        matched_unknown["model_status"] == "unknown_outcome",
        {"verdict": matched_unknown},
    )

    annotated = operation_results.annotate_native_result(
        failed_result(rollback_succeeded=False, rollback_difference=matched_block()), readonly=False
    )
    verdict = failure_verdict({}, {"status": "failed"}, annotated, before, baseline_snapshot(model))
    check(
        "matched_counts_without_a_verified_restore_stay_failed",
        verdict["model_status"] == "failed"
        and any("diagnostic only" in reason for reason in verdict["reasons"]),
        {"verdict": verdict},
    )

    equal_volume = difference_block(
        features=collection([1, 2, 3], [1, 2, 3, 4]),
        volume_mm3={"available": True, "before": 1000.0, "after": 1000.0, "reason": None},
    )
    verdict = failure_verdict(
        {},
        {"status": "failed"},
        operation_results.annotate_native_result(
            failed_result(rollback_difference=equal_volume), readonly=False
        ),
        before,
        baseline_snapshot(model),
    )
    check(
        "equal_volume_alone_does_not_clear_the_protection",
        verdict["model_status"] == "failed" and verdict["difference_status"] == "mismatch",
        {"verdict": verdict},
    )

    annotated = operation_results.annotate_native_result(
        failed_result(rollback_succeeded=True), readonly=False
    )
    changed_hash = failure_verdict(
        {},
        {"status": "failed"},
        annotated,
        before,
        baseline_snapshot(baseline_model(part_sha256="b" * 64)),
    )
    check(
        "changed_baseline_hash_blocks_ready",
        changed_hash["model_status"] == "failed"
        and changed_hash["baseline"]["checks"]["part_sha256"] is False,
        {"verdict": changed_hash},
    )
    changed_revision = failure_verdict(
        {},
        {"status": "failed"},
        annotated,
        before,
        baseline_snapshot(baseline_model(revision=8)),
    )
    check(
        "changed_baseline_revision_blocks_ready",
        changed_revision["model_status"] == "failed"
        and changed_revision["baseline"]["checks"]["revision"] is False,
        {"verdict": changed_revision},
    )

    unchanged = failure_verdict(
        {},
        {"status": "failed"},
        annotated,
        before,
        baseline_snapshot(baseline_model()),
    )
    check(
        "all_baseline_invariants_and_verified_restore_allow_ready",
        unchanged["model_status"] == "ready" and unchanged["baseline"]["unchanged"] is True,
        {"verdict": unchanged},
    )

    new_model = baseline_snapshot(None)
    erased = failure_verdict(
        {},
        {"status": "failed"},
        operation_results.annotate_native_result(
            failed_result(save_failure=save_failure_block(), part_file=None), readonly=False
        ),
        new_model,
        baseline_snapshot({"part_file": None, "part_sha256": None, "revision": 0}),
    )
    check(
        "new_model_failure_records_absence_without_a_ready_verdict",
        erased["model_status"] == "failed" and erased["baseline"]["after"]["part_sha256"] is None,
        {"verdict": erased},
    )

    passed = all(item["ok"] for item in items)
    return {
        "mode": "offline",
        "passed": passed,
        "native_save_recovery": "not_verified",
        "checks": items,
    }


def case_native_wiring_offline() -> dict:
    """The executor still records the failure before it throws."""
    items, check = checks()
    generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
    start = generic.index('generic_substage("verify_model_save");')
    body = generic[start : generic.index("saved = latest_model_file();", start)]
    check(
        "backup_failure_recorded_before_the_throw",
        body.index('report["save_failure"]') < body.index("check(backup,"),
    )
    check(
        "backup_call_and_text_frozen",
        "ProError backup = ProMdlnameBackup(board, destination);" in body
        and 'check(backup, "ProMdlnameBackup(board, destination)");' in body,
    )
    rollback = generic[generic.index("J rollback_baseline = nullptr;") :]
    rollback = rollback[: rollback.index('report["rollback_code"] = loaded;')]
    check(
        "restore_is_verified_before_success_is_recorded",
        rollback.index("verify_saved(rollback_baseline, restored);")
        < rollback.index('report["rollback_succeeded"] = true;'),
    )
    check(
        "both_restore_catches_publish_the_difference",
        rollback.count('report["rollback_difference"] =') >= 2,
    )
    passed = all(item["ok"] for item in items)
    return {
        "mode": "offline",
        "passed": passed,
        "native_save_recovery": "not_verified",
        "checks": items,
    }


# ---------------------------------------------------------------------------
# Live route plans. No flag means no connection at all.
# ---------------------------------------------------------------------------


def _profile() -> dict:
    return {
        "op": "sketch",
        "label": "recovery_profile",
        "plane": "XY",
        "entities": [
            {
                "type": "rectangle",
                "name": "rect",
                "min": [0.0, 0.0],
                "max": [LIVE_WIDTH, LIVE_HEIGHT],
            }
        ],
    }


def _base() -> list[dict]:
    return [
        _profile(),
        {"op": "surface_fill", "label": "recovery_base", "sketch": "recovery_profile"},
    ]


def _independent_tool() -> list[dict]:
    return [
        {
            "op": "datum_plane",
            "label": "recovery_cut",
            "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
            "offset": LIVE_X,
        }
    ]


def _independent_trim() -> list[dict]:
    return [
        {
            "op": "surface_trim",
            "label": "recovery_trim",
            "target": {"kind": "quilt_feature", "label": "recovery_base"},
            "tool": {"kind": "datum_plane", "label": "recovery_cut"},
            "keep_side": "one",
        }
    ]


def _thicken() -> list[dict]:
    return [
        {
            "op": "thicken",
            "label": "recovery_solid",
            "reference": {"kind": "quilt_feature", "label": "recovery_trim"},
            "thickness": LIVE_THICKNESS,
            "side": "symmetric",
        }
    ]


def _projection_inputs() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "recovery_source",
            "plane": "XY",
            "offset": LIVE_SOURCE_Z,
            "entities": [{"type": "line", "name": "src", "start": [-5.0, 5.0], "end": [45.0, 5.0]}],
        },
        {
            "op": "datum_plane",
            "label": "recovery_dir",
            "reference": {"kind": "datum_plane", "axis": "z", "offset": 0},
            "offset": LIVE_SOURCE_Z + 20.0,
        },
    ]


def _projection() -> list[dict]:
    return [
        {
            "op": "project_curve",
            "label": "recovery_projection",
            "target": {"kind": "quilt_feature", "label": "recovery_base"},
            "source": {"kind": "curve", "id": "recovery_source"},
            "direction_ref": {"kind": "datum_feature", "label": "recovery_dir"},
            "side": "negative",
        }
    ]


def _projected_trim() -> list[dict]:
    plan = _independent_trim()
    plan[0]["tool"] = {"kind": "curve", "id": "recovery_projection"}
    plan[0]["keep_side"] = "two"
    return plan


def live_jobs(route: str, tool: str) -> list[list[dict]]:
    """The frozen submission groups; placeholders resolve from measured curves."""
    if tool == "independent_plane":
        if route == "single_plan":
            return [_base() + _independent_tool() + _independent_trim() + _thicken()]
        return [_base(), _independent_tool() + _independent_trim(), _thicken()]
    if route == "single_plan":
        return [
            _base() + _projection_inputs(),
            _projection(),
            _projected_trim() + _thicken(),
        ]
    return [_base(), _projection_inputs(), _projection(), _projected_trim() + _thicken()]


def resolve_placeholders(plan: list[dict], curves: dict[str, int | None]) -> list[dict]:
    """Replace runtime curve placeholders without inventing a value."""
    resolved = json.loads(json.dumps(plan))
    for operation in resolved:
        source = operation.get("source")
        if isinstance(source, dict) and isinstance(source.get("id"), str):
            source["id"] = curves[source["id"]]
            if source["id"] is None:
                raise ValueError("source curve id was not measured")
        tool = operation.get("tool")
        if isinstance(tool, dict) and isinstance(tool.get("id"), str):
            tool["id"] = curves[tool["id"]]
            if tool["id"] is None:
                raise ValueError("projected curve id was not measured")
    return resolved


async def model_snapshot(client, model_id: str | None) -> dict:
    if not model_id:
        return baseline_snapshot(None)
    page = await call_tool(client, "creo_list_models", {"limit": 50, "detail": "compact"})
    for model in page.get("models") or []:
        if model.get("model_id") == model_id:
            return baseline_snapshot(model)
    return baseline_snapshot(None)


async def measure_curves(client, model_id: str) -> dict[str, int | None]:
    features = await section(client, model_id, "features")
    geometry = await section(client, model_id, "feature_geometry")
    return {
        label: curve_id_of(geometry, feature_named(features, label))
        for label in ("recovery_source", "recovery_projection")
    }


async def live_case(client, case: dict, jobs: list[str]) -> dict:
    record: dict[str, Any] = {
        "case_id": case["case_id"],
        "route": case["route"],
        "tool": case["tool"],
        "model_index": case["model_index"],
        "attempts": [],
        "baseline_before": baseline_snapshot(None),
        "baseline_after": baseline_snapshot(None),
        "verdict": None,
        "recovery_action": None,
        "resubmitted": False,
    }
    model_id: str | None = None
    revision: int | None = None
    curves: dict[str, int | None] = {"recovery_source": None, "recovery_projection": None}
    plans = live_jobs(case["route"], case["tool"])
    if len(plans) > case["submit_budget"]:
        record["verdict"] = {"model_status": "failed", "reasons": ["frozen budget exceeded"]}
        return record
    record["baseline_before"] = await model_snapshot(client, model_id)
    for index, plan in enumerate(plans):
        if index:
            record["baseline_before"] = await model_snapshot(client, model_id)
        if isinstance(plan[0].get("tool"), dict) or any(
            operation.get("op") == "project_curve" for operation in plan
        ):
            plan = resolve_placeholders(plan, curves)
        state = await submit_plan(client, plan, jobs, model_id, revision)
        if state.get("status") == "refused":
            # BUG-115 guard: the all-new same-plan fill -> trim -> thicken chain
            # is refused before a job exists, so no save/rollback evidence can be
            # produced for this route. Record the expected refusal instead of a
            # native failure and keep the executable split as the next action.
            message = str(state.get("message") or "")
            record["attempts"].append(
                {
                    "submit_index": index,
                    "job_id": None,
                    "status": "refused",
                    "message": message[:300],
                    "saved_verified": None,
                    "result": {},
                }
            )
            record["baseline_after"] = await model_snapshot(client, model_id)
            if "BUG-115" in message:
                record["verdict"] = {
                    "model_status": "refused_expected",
                    "reasons": [
                        "BUG-115 guard: the all-new same-plan fill -> trim -> thicken "
                        "chain is refused before a job exists"
                    ],
                }
                record["recovery_action"] = {
                    "tools": ["creo_execute_plan"],
                    "automatic_retry": False,
                    "note": "submit fill/trim first, then thicken in a second plan",
                }
            else:
                record["verdict"] = {
                    "model_status": "failed",
                    "reasons": ["pre-submission refusal", message[:200]],
                }
            return record
        attempt = {
            "submit_index": index,
            "job_id": (jobs[-1] if jobs else None),
            "status": state.get("status"),
            "message": str(state.get("message"))[:300],
            "saved_verified": state.get("saved_verified"),
            "result": {
                key: (state.get("result") or {}).get(key)
                for key in (
                    "save_failure",
                    "rollback_difference",
                    "rollback_succeeded",
                    "rollback_code",
                    "model_unchanged",
                    "saved_file_reloaded_and_verified",
                    "sha256",
                )
            },
        }
        record["attempts"].append(attempt)
        if state.get("status") == "succeeded" and state.get("saved_verified"):
            model_id = state.get("model_id") or model_id
            revision = state.get("revision")
            curves = await measure_curves(client, model_id) if model_id else curves
            continue
        if state.get("status") == "succeeded":
            record["verdict"] = {
                "model_status": "failed",
                "reasons": ["the job succeeded without a verified save"],
            }
            record["baseline_after"] = await model_snapshot(client, model_id)
            return record
        request = {"readonly": False}
        record["baseline_after"] = await model_snapshot(client, model_id)
        record["verdict"] = failure_verdict(
            request,
            state,
            state.get("result") or {},
            record["baseline_before"],
            record["baseline_after"],
        )
        record["recovery_action"] = {
            "tools": ["creo_get_job", "creo_inspect_model", "creo_reconcile_model"],
            "automatic_retry": False,
            "note": "inspect the recorded evidence before any recovery; never resubmit blindly",
        }
        return record
    record["baseline_after"] = await model_snapshot(client, model_id)
    record["verdict"] = {"model_status": "ready", "reasons": ["all frozen submissions succeeded"]}
    return record


async def case_live(selected: list[dict]) -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from tools.test_surface_chain import wait_ready

    items, check = checks()
    jobs: list[str] = []
    records: list[dict] = []
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_save_recovery": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": items,
            }
        for case in selected:
            record = await live_case(client, case, jobs)
            records.append(record)
            check(
                f"{case['case_id']}:no_auto_resubmit",
                record["resubmitted"] is False,
            )
            check(
                f"{case['case_id']}:within_budget",
                len(record["attempts"]) <= case["submit_budget"],
                {"attempts": len(record["attempts"]), "budget": case["submit_budget"]},
            )
            check(
                f"{case['case_id']}:terminal",
                all(
                    attempt["status"] in ("succeeded", "failed", "unknown_outcome", "refused")
                    for attempt in record["attempts"]
                ),
                {"attempts": record["attempts"]},
            )
            check(
                f"{case['case_id']}:baseline_recorded",
                isinstance(record["baseline_before"], dict)
                and isinstance(record["baseline_after"], dict),
            )
            if record["verdict"] and record["verdict"].get("model_status") != "ready":
                check(
                    f"{case['case_id']}:recovery_action_recorded",
                    isinstance(record["recovery_action"], dict)
                    and record["recovery_action"].get("automatic_retry") is False,
                    {"recovery_action": record["recovery_action"]},
                )
    passed = all(item["ok"] for item in items)
    return {
        "mode": "live",
        "passed": passed,
        "native_save_recovery": "verified" if passed else "failed",
        "jobs": jobs,
        "cases": records,
        "checks": items,
    }


def run_offline(selected: list[dict]) -> dict:
    parts = [
        case_matrix_offline(),
        case_existing_regressions_offline(),
        case_r02_judgments_offline(),
        case_native_wiring_offline(),
    ]
    items = [item for part in parts for item in part["checks"]]
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in items),
        "native_save_recovery": "not_verified",
        "matrix": selected,
        "checks": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="", help="only run case ids starting with this prefix")
    parser.add_argument(
        "--live", action="store_true", help="run against the connected Creo session"
    )
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="second required key that the session was verified usable",
    )
    args = parser.parse_args()
    if args.live != args.confirm_session_usable:
        parser.exit(BUSY_EXIT, "--live and --confirm-session-usable must be given together\n")
    selected = [case for case in frozen_cases() if case["case_id"].startswith(args.case)]
    if not selected:
        parser.exit(BUSY_EXIT, f"no frozen case matches prefix: {args.case}\n")

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"
    )
    run_dir = ROOT / "build" / "surface_save_recovery" / run_id
    if run_dir.exists():
        parser.exit(OVERWRITE_EXIT, f"run directory already exists: {run_dir}\n")
    run_dir.mkdir(parents=True)

    report = {
        "run_id": run_id,
        "mode": "live" if args.live else "offline",
        "version": VERSION,
        "command": "tools/test_surface_save_recovery.py " + " ".join(sys.argv[1:]),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "matrix": selected,
    }
    outcome = asyncio.run(case_live(selected)) if args.live else run_offline(selected)
    report.update(outcome)
    path = run_dir / "report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "report": str(path), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
