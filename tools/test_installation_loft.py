"""DEV-049 T06 seed matrix driver: offline evidence gates plus the 15+2 run.

Evidence boundaries fixed by this task:

* Default is strictly offline: the manifest, the nine seed SHA256 values and
  the 15 positive + 2 negative case inputs are validated without creating any
  MCP client and without touching Toolkit/Creo.
* A live run requires BOTH --live and --confirm-session-usable. A single
  switch never connects. The driver never starts or stops Creo, never clears
  protection and never resubmits or replays a job.
* --case NAME (repeatable) selects not-yet-done items and always creates new
  independent models; unknown names are refused before any connection.
* Every run writes its own build/dev049_t06/<run_id>/report.json (or --output).
  An existing report is refused at startup so history is never overwritten.
* Inputs and job IDs are persisted at admission and terminal states at every
  stage, so a failure or an interrupt still leaves a report behind.
* Reports from different source fingerprints are never merged into a single
  all-pass result (see CROSS_REPORT_POLICY / summarize_reports).

The 15 positives run in the fixed dispatch-table order of
docs/development/0.6.1-FEEDBACK-TASKS-2026-10-27.md (T06). The two negatives
are stable named cases built from an explicit, freshly constructed two_straight
base input: invalid_seed_feature_id and interpolation_mismatch.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog import inspection_refs, model_registry
from creo_mechdog.paths import SOURCE_PATHS
from tools.test_loft_seed import sections
from tools.test_multisection_blend import profiles

ROOT = SOURCE_PATHS.resource_root

MATRIX_CASE_ORDER = (
    "matrix_five_smooth",
    "matrix_four_smooth",
    "matrix_four_straight",
    "matrix_six_smooth",
    "matrix_six_straight",
    "matrix_three_smooth",
    "matrix_three_straight",
    "matrix_two_smooth",
    "matrix_two_straight",
)

EXTRA_CASES = (
    ("rectangle_empty_A", "two_straight", False, False),
    ("rectangle_explicit_B", "two_straight", True, False),
    ("rectangle_empty_C", "two_straight", False, False),
    ("rectangle_smooth_empty", "two_smooth", False, False),
    ("five_rectangle_empty", "five_smooth", False, False),
    ("five_airfoil_empty", "five_smooth", False, True),
)
EXTRA_BY_NAME = {case: (seed, dimensions, foil) for case, seed, dimensions, foil in EXTRA_CASES}

POSITIVE_CASE_ORDER = MATRIX_CASE_ORDER + tuple(row[0] for row in EXTRA_CASES)
NEGATIVE_CASE_ORDER = ("invalid_seed_feature_id", "interpolation_mismatch")
ALL_CASE_ORDER = POSITIVE_CASE_ORDER + NEGATIVE_CASE_ORDER

NEGATIVE_SEED = "two_straight"
INVALID_SEED_FEATURE_ID = 2147483647
TWO_SECTION_VOLUME_MM3 = 7000

CROSS_REPORT_POLICY = (
    "One report covers exactly one run_id on one source fingerprint; reports whose "
    "provenance.source_fingerprint differ must never be merged into one all-pass result."
)


def native_result_details(job: dict) -> tuple[dict, dict]:
    result = job["result"]
    inspection = inspection_refs.full_inspection(result)
    if inspection is None:
        raise AssertionError("Native result has no full inspection evidence")
    return inspection, model_registry.aliases_of(result)


def seed_cases(manifest: dict) -> list[tuple[str, str, bool, bool]]:
    """Return (case, seed_name, dimensions, foil) in the fixed dispatch order."""
    names = {row["name"] for row in manifest["seeds"]}
    cases: list[tuple[str, str, bool, bool]] = []
    for case in POSITIVE_CASE_ORDER:
        if case.startswith("matrix_"):
            seed_name = case[len("matrix_") :]
            entry = (case, seed_name, False, False)
        else:
            seed_name, dimensions, foil = EXTRA_BY_NAME[case]
            entry = (case, seed_name, dimensions, foil)
        if seed_name not in names:
            raise ValueError(f"Manifest has no seed for case {case}: {seed_name}")
        cases.append(entry)
    return cases


def section_operations(count: int, dimensions: bool, foil: bool) -> list[dict]:
    ops = sections("rectangle") if count == 2 else profiles(count, foil)[0]
    ops = copy.deepcopy(ops)
    if not dimensions:
        for op in ops:
            op["dimensions"] = []
    return ops


def create_args(
    seed: dict, source_file: Path, dimensions: bool, foil: bool, model_name: str | None = None
) -> dict:
    count = seed["section_count"]
    args = {
        "seed_file": str(source_file),
        "seed_feature_id": seed["seed_feature_id"],
        "sections": section_operations(count, dimensions, foil),
        "label": "blend",
        "interpolation": seed["interpolation"],
        "assertions": {"require_solid": True},
    }
    if count == 2:
        args["assertions"]["volume_mm3"] = TWO_SECTION_VOLUME_MM3
    if model_name is not None:
        args["model_name"] = model_name
    return args


def negative_base_args(seed: dict, source_file: Path) -> dict:
    """Explicit, valid two_straight input; built fresh on every call.

    Negative cases must never depend on whatever the previous loop iteration
    left behind, so this base is always reconstructed from scratch.
    """
    return create_args(seed, source_file, dimensions=False, foil=False)


def negative_case_args(
    case: str, seeds: dict, source_files: dict, model_name: str | None = None
) -> dict:
    if case not in NEGATIVE_CASE_ORDER:
        raise ValueError(f"Unknown negative case: {case}")
    seed = seeds[NEGATIVE_SEED]
    args = negative_base_args(seed, source_files[NEGATIVE_SEED])
    if case == "invalid_seed_feature_id":
        args["seed_feature_id"] = INVALID_SEED_FEATURE_ID
    else:
        args["interpolation"] = "smooth" if seed["interpolation"] == "straight" else "straight"
    if model_name is not None:
        args["model_name"] = model_name
    return args


def validate_model_name(name: str) -> None:
    if not isinstance(name, str) or not name or len(name) > 31:
        raise ValueError(f"model_name must be 1-31 characters: {name!r}")
    if not name[0].isalnum() or name[0].isupper():
        raise ValueError(f"Invalid model_name {name!r}")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in name):
        raise ValueError(f"Invalid model_name {name!r}")


def validate_case_inputs(case: str, args: dict, seed: dict) -> None:
    label = args.get("label")
    if not isinstance(label, str) or not label or not label[0].islower() or len(label) > 28:
        raise ValueError(f"Invalid feature label for {case}: {label!r}")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in label):
        raise ValueError(f"Invalid feature label for {case}: {label!r}")
    ops = args.get("sections")
    if not isinstance(ops, list) or len(ops) != seed["section_count"]:
        raise ValueError(f"Section count for {case} does not match the seed: {ops!r}")
    for op in ops:
        if not isinstance(op.get("dimensions"), list):
            raise ValueError(f"Section input for {case} has no dimensions list: {op!r}")
    if args.get("interpolation") != seed["interpolation"]:
        raise ValueError(f"Interpolation for {case} does not match the seed")
    if args.get("seed_feature_id") != seed["seed_feature_id"]:
        raise ValueError(f"seed_feature_id for {case} does not match the manifest entry")
    if args.get("model_name") is not None:
        validate_model_name(args["model_name"])


def validate_negative_args(case: str, args: dict, seeds: dict, source_files: dict) -> dict:
    base = negative_base_args(seeds[NEGATIVE_SEED], source_files[NEGATIVE_SEED])
    base.pop("model_name", None)
    candidate = dict(args)
    candidate.pop("model_name", None)
    differences = sorted(
        key for key in set(base) | set(candidate) if base.get(key) != candidate.get(key)
    )
    expected = ["seed_feature_id"] if case == "invalid_seed_feature_id" else ["interpolation"]
    if differences != expected:
        raise ValueError(
            f"Negative case {case} must differ from the explicit two_straight base only in "
            f"{expected}, got {differences}"
        )
    if case == "invalid_seed_feature_id" and args["seed_feature_id"] != INVALID_SEED_FEATURE_ID:
        raise ValueError(f"invalid_seed_feature_id must use {INVALID_SEED_FEATURE_ID}")
    if (
        case == "interpolation_mismatch"
        and args["interpolation"] == seeds[NEGATIVE_SEED]["interpolation"]
    ):
        raise ValueError("interpolation_mismatch must request the opposite interpolation")
    if args.get("model_name") is not None:
        validate_model_name(args["model_name"])
    return {"expected_difference": expected, "actual_difference": differences}


def load_seed_library(library: Path) -> dict:
    if not library.is_dir():
        raise ValueError(f"Seed library directory not found: {library}")
    manifest_path = library / "seed_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Seed manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    rows = manifest.get("seeds")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Seed manifest has no seeds")
    names = [row.get("name") for row in rows]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Seed manifest has an unnamed entry")
    if len(names) != len(set(names)):
        raise ValueError("Seed manifest has duplicate seed names")
    seeds: dict[str, dict] = {}
    source_files: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    records: list[dict] = []
    for row in rows:
        name = row["name"]
        for key in ("relative_path", "sha256", "section_count", "interpolation", "seed_feature_id"):
            if key not in row:
                raise ValueError(f"Seed {name} misses manifest field {key}")
        relative = Path(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Seed {name} has an unsafe relative_path: {row['relative_path']}")
        path = library / relative
        if not path.is_file():
            raise ValueError(f"Seed file missing for {name}: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"Seed {name} SHA256 mismatch: {digest} != {row['sha256']}")
        seeds[name] = row
        source_files[name] = path
        hashes[name] = digest
        records.append(
            {
                "name": name,
                "relative_path": row["relative_path"],
                "sha256": digest,
                "sha256_matches_manifest": True,
                "section_count": row["section_count"],
                "interpolation": row["interpolation"],
                "seed_feature_id": row["seed_feature_id"],
                "bytes": path.stat().st_size,
            }
        )
    return {
        "library": library,
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "seeds": seeds,
        "source_files": source_files,
        "hashes": hashes,
        "seed_records": records,
    }


def resolve_selection(requested: list[str] | None) -> list[str]:
    if not requested:
        return list(ALL_CASE_ORDER)
    unknown = sorted({name for name in requested if name not in ALL_CASE_ORDER})
    if unknown:
        raise ValueError(f"Unknown case name(s): {', '.join(unknown)}")
    duplicates = sorted({name for name in requested if requested.count(name) > 1})
    if duplicates:
        raise ValueError(f"Case selected twice (never resubmit): {', '.join(duplicates)}")
    return [case for case in ALL_CASE_ORDER if case in set(requested)]


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def model_tag(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]


def model_name_for(case: str, run_tag: str) -> str:
    name = f"t06_{ALL_CASE_ORDER.index(case) + 1:02d}_{run_tag}"
    validate_model_name(name)
    return name


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before any connection is made."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "dev049_t06" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(("tools/test_installation_loft.py", "tests/unit/test_seed_regression_contract.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


def summarize_reports(reports: list[dict]) -> dict:
    """Combine per-run evidence only when it comes from one source fingerprint."""
    if not reports:
        raise ValueError("No reports to summarize")
    fingerprints = {report.get("provenance", {}).get("source_fingerprint") for report in reports}
    if len(fingerprints) != 1 or None in fingerprints:
        raise ValueError(CROSS_REPORT_POLICY)
    passed = {
        case.get("case")
        for report in reports
        for case in report.get("cases", [])
        if case.get("passed")
    }
    return {
        "source_fingerprint": fingerprints.pop(),
        "reports": len(reports),
        "passed_cases": [case for case in ALL_CASE_ORDER if case in passed],
        "policy": CROSS_REPORT_POLICY,
    }


def offline_checks(library_info: dict, selection: list[str], run_id: str) -> dict:
    """Validate manifest, hashes and every selected case input without a client."""
    manifest = library_info["manifest"]
    seeds = library_info["seeds"]
    source_files = library_info["source_files"]
    tag = model_tag(run_id)
    positives: list[dict] = []
    negatives: list[dict] = []
    for case, name, dimensions, foil in seed_cases(manifest):
        if case not in selection:
            continue
        seed = seeds[name]
        args = create_args(seed, source_files[name], dimensions, foil, model_name_for(case, tag))
        validate_case_inputs(case, args, seed)
        positives.append(
            {
                "case": case,
                "kind": "positive",
                "seed_name": name,
                "seed_sha256": library_info["hashes"][name],
                "seed_sha256_verified": True,
                "section_count": seed["section_count"],
                "interpolation": seed["interpolation"],
                "dimensions": dimensions,
                "airfoil_sections": foil,
                "model_name": args["model_name"],
                "input": args,
                "validated": True,
            }
        )
    for case in NEGATIVE_CASE_ORDER:
        if case not in selection:
            continue
        args = negative_case_args(case, seeds, source_files, model_name_for(case, tag))
        difference = validate_negative_args(case, args, seeds, source_files)
        negatives.append(
            {
                "case": case,
                "kind": "negative",
                "base_seed_name": NEGATIVE_SEED,
                "base_input": "explicit fresh two_straight input (no loop residue)",
                "model_name": args["model_name"],
                "input": args,
                "difference": difference,
                "validated": True,
            }
        )
    return {
        "run_id": run_id,
        "manifest_seed_count": len(seeds),
        "hashes_verified": len(library_info["hashes"]),
        "positive_cases": positives,
        "negative_cases": negatives,
    }


def write_offline_report(
    output: Path, run_id: str, selection: list[str], library_info: dict, results: dict
) -> dict:
    manifest = library_info["manifest"]
    from version import VERSION

    report = {
        "task": "DEV-049 T06",
        "scope": "seed driver evidence boundary tightening and the 15+2 seed matrix",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: manifest, nine seed SHA256 values and the selected 15+2 case "
            "inputs validated; no MCP client was created, no Toolkit connection and no native "
            "geometry result. Historical 0.6.1 results are not claimed as this run's evidence."
        ),
        "selection": selection,
        "case_order": list(POSITIVE_CASE_ORDER),
        "negative_cases": list(NEGATIVE_CASE_ORDER),
        "seed_library": str(library_info["library"]),
        "manifest": {
            "path": library_info["manifest_path"],
            "name": manifest.get("name"),
            "compatible_server_version": manifest.get("compatible_server_version"),
            "seed_count": len(library_info["seeds"]),
        },
        "manifest_matches_server_version": manifest.get("compatible_server_version") == VERSION,
        "source_hashes": library_info["hashes"],
        "seed_records": library_info["seed_records"],
        "offline_checks": {
            "hashes_verified": results["hashes_verified"],
            "positive_cases_validated": len(results["positive_cases"]),
            "negative_cases_validated": len(results["negative_cases"]),
        },
        "cases": results["positive_cases"],
        "negative_case_inputs": results["negative_cases"],
        "cross_report_policy": CROSS_REPORT_POLICY,
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


class SeedMatrixRunner:
    """Serial 15+2 live runner. Persists input, job id and terminal states."""

    def __init__(
        self, client: Any, output: Path, run_id: str, selection: list[str], library_info: dict
    ):
        self.client = client
        self.output = output
        self.run_id = run_id
        self.selection = list(selection)
        self.library = library_info
        self.submitted: set[str] = set()
        self.report: dict = {
            "task": "DEV-049 T06",
            "scope": "seed driver evidence boundary tightening and the 15+2 seed matrix",
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "native_acceptance": "running",
            "selection": self.selection,
            "case_order": list(POSITIVE_CASE_ORDER),
            "negative_cases": list(NEGATIVE_CASE_ORDER),
            "source_hashes": library_info["hashes"],
            "cases": [],
            "calls": [],
            "cross_report_policy": CROSS_REPORT_POLICY,
            "five_smooth_gate": "pending",
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict) -> Any:
        response = await self.client.call_tool(name, args)
        self.report["calls"].append(
            {"tool": name, "args": args, "is_error": bool(response.is_error), "at": time.time()}
        )
        self.save()
        return response

    def model_name(self, case: str) -> str:
        return model_name_for(case, model_tag(self.run_id))

    async def admit(self, case_key: str, tool: str, args: dict, entry: dict, stage: str) -> dict:
        """Submit exactly once; persist the input and any job id immediately."""
        if case_key in self.submitted:
            raise RuntimeError(f"{case_key} already submitted; never resubmit")
        self.submitted.add(case_key)
        record = {"tool": tool, "input": args, "state": "submitted", "at": time.time()}
        entry.setdefault("stages", {})[stage] = record
        self.save()
        response = await self.call(tool, args)
        payload = (
            response.structured_content if isinstance(response.structured_content, dict) else {}
        )
        record["is_error"] = bool(response.is_error)
        if payload.get("job_id"):
            record["job_id"] = payload["job_id"]
            record["state"] = "accepted"
        else:
            record["state"] = "rejected_at_admission"
            record["message"] = payload.get("message") or str(response)[:4000]
        self.save()
        return record

    async def wait_job(self, job_id: str, budget: float = 600) -> dict:
        """Poll one accepted job to a terminal state. Never resubmits anything."""
        deadline = time.monotonic() + budget
        while True:
            response = await self.call("creo_get_job", {"job_id": job_id})
            state = (
                response.structured_content if isinstance(response.structured_content, dict) else {}
            )
            status = state.get("status")
            if status not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} still {status}; budget exhausted, do not resubmit"
                )
            await asyncio.sleep(1)
        if status not in ("succeeded", "failed"):
            raise RuntimeError(
                f"Job {job_id} returned an unknown terminal status {status!r}; recorded as-is, "
                "do not resubmit"
            )
        return state

    @staticmethod
    def terminal_summary(state: dict) -> dict:
        result = state.get("result") or {}
        return {
            "status": state.get("status"),
            "job_id": state.get("job_id"),
            "model_id": state.get("model_id"),
            "revision": state.get("revision"),
            "message": state.get("message"),
            "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
        }

    def check(
        self, state: dict, seed: dict, expected_fid: int | None = None
    ) -> tuple[int, dict, float]:
        result = state["result"]
        inspection, aliases = native_result_details(state)
        setting = result["loft_checks"]["after_reload"]["blend"]
        assert setting["interpolation"] == seed["interpolation"], setting
        assert setting["section_count"] == seed["section_count"], setting
        actual = aliases["blend"]["feature_id"]
        assert expected_fid is None or actual == expected_fid, (actual, expected_fid)
        feature = next(f for f in inspection["features"] if f["id"] == actual)
        assert feature["type"] == 917 and feature["status"] == 0 and not feature["incomplete"], (
            feature
        )
        assert (
            inspection["healthy"] and len([b for b in inspection["bodies"] if b["state"] == 4]) == 1
        )
        return actual, feature, inspection["volume_mm3"]

    async def run_positive(self, case: str, name: str, dimensions: bool, foil: bool) -> None:
        seed = self.library["seeds"][name]
        count = seed["section_count"]
        args = create_args(
            seed,
            self.library["source_files"][name],
            dimensions,
            foil,
            model_name=self.model_name(case),
        )
        validate_case_inputs(case, args, seed)
        entry = {
            "case": case,
            "kind": "positive",
            "seed_name": name,
            "seed_sha256": self.library["hashes"][name],
            "section_count": count,
            "interpolation": seed["interpolation"],
            "model_name": args["model_name"],
            "passed": False,
            "stages": {},
        }
        self.report["cases"].append(entry)
        self.save()

        create = await self.admit(f"{case}:create", "creo_new_loft_part", args, entry, "create")
        if create["state"] != "accepted":
            raise RuntimeError(f"{case} create rejected at admission: {create.get('message')}")
        state = await self.wait_job(create["job_id"])
        entry["stages"]["create"]["terminal"] = self.terminal_summary(state)
        self.save()
        assert state["status"] == "succeeded", state.get("message")
        assert state["result"]["saved_file_reloaded_and_verified"], state
        fid, feature, initial_volume = self.check(state, seed)

        if dimensions:
            edit = {
                "op": "set_sketch_dimensions",
                "sketch": "top",
                "values": {"width": 12, "height": 12},
            }
            assertions = {"volume_mm3": 7840}
        elif count == 2:
            inspection, _ = native_result_details(state)
            plane = next(f for f in inspection["features"] if f["name"] == "TOP_PLANE")
            assert plane["dimensions"], plane
            dim = plane["dimensions"][0]
            edit = {
                "op": "set_dimensions",
                "values": [{"id": dim["id"], "value": dim["value"] + 5}],
            }
            assertions = {"volume_mm3": TWO_SECTION_VOLUME_MM3 * 35 / 30}
        else:
            # Multi-section seed datums (four/six/three/two) do not drive the
            # blend, so edit a real nonzero sketch dimension of section_1.
            inspection, section_aliases = native_result_details(state)
            sketch = next(
                f
                for f in inspection["features"]
                if f["id"] == section_aliases["section_1"]["feature_id"]
            )
            dims = [d for d in sketch["dimensions"] if d["value"] > 1e-6]
            assert dims, sketch
            dim = max(dims, key=lambda d: d["value"])
            edit = {
                "op": "set_dimensions",
                "values": [{"id": dim["id"], "value": dim["value"] + 5}],
            }
            assertions = {"require_solid": True}
        edit_args = {
            "model_id": state["model_id"],
            "expected_revision": state["revision"],
            "operations": [edit],
            "assertions": assertions,
        }
        edit_record = await self.admit(
            f"{case}:edit", "creo_execute_plan", edit_args, entry, "edit"
        )
        if edit_record["state"] != "accepted":
            raise RuntimeError(f"{case} edit rejected at admission: {edit_record.get('message')}")
        edited = await self.wait_job(edit_record["job_id"])
        entry["stages"]["edit"]["terminal"] = self.terminal_summary(edited)
        self.save()
        assert edited["status"] == "succeeded", edited.get("message")
        assert edited["result"]["saved_file_reloaded_and_verified"], edited
        assert edited["revision"] == state["revision"] + 1, (state["revision"], edited["revision"])
        _, _, edited_volume = self.check(edited, seed, fid)
        assert abs(edited_volume - initial_volume) > 0.01, (initial_volume, edited_volume)

        source_unchanged = (
            hashlib.sha256(self.library["source_files"][name].read_bytes()).hexdigest()
            == seed["sha256"]
        )
        entry.update(
            {
                "passed": True,
                "seed_sha256_verified": source_unchanged,
                "create_job_id": create["job_id"],
                "edit_job_id": edit_record["job_id"],
                "model_id": state["model_id"],
                "create_revision": state["revision"],
                "edit_revision": edited["revision"],
                "native_blend_id": fid,
                "blend_feature": {
                    "id": feature["id"],
                    "type": feature["type"],
                    "status": feature["status"],
                    "incomplete": feature["incomplete"],
                },
                "initial_volume_mm3": initial_volume,
                "edited_volume_mm3": edited_volume,
                "volume_changed_by_edit": True,
                "parameter_edit": edit,
                "create_saved_reloaded_verified": True,
                "edit_saved_reloaded_verified": True,
            }
        )
        self.save()

    async def run_negative(self, case: str) -> None:
        args = negative_case_args(
            case,
            self.library["seeds"],
            self.library["source_files"],
            model_name=self.model_name(case),
        )
        difference = validate_negative_args(
            case, args, self.library["seeds"], self.library["source_files"]
        )
        entry = {
            "case": case,
            "kind": "negative",
            "base_seed_name": NEGATIVE_SEED,
            "base_input": "explicit fresh two_straight input (no loop residue)",
            "difference": difference,
            "model_name": args["model_name"],
            "passed": False,
            "stages": {},
        }
        self.report["cases"].append(entry)
        self.save()
        record = await self.admit(f"{case}:create", "creo_new_loft_part", args, entry, "create")
        if record["state"] == "accepted":
            state = await self.wait_job(record["job_id"])
            entry["stages"]["create"]["terminal"] = self.terminal_summary(state)
            entry["stages"]["create"]["full_terminal"] = state
            entry["job_id"] = record["job_id"]
            entry["rejection_stage"] = "native_execution"
            entry["message"] = state.get("message")
            entry["saved_file_reloaded_and_verified"] = (state.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            )
            entry["passed"] = state.get("status") == "failed"
            if entry["passed"]:
                assert entry["saved_file_reloaded_and_verified"] is not True, state
        else:
            entry["job_id"] = None
            entry["rejection_stage"] = "request_admission"
            entry["message"] = record.get("message")
            entry["passed"] = True
        self.save()

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = (await self.call("creo_capabilities", {})).structured_content
        self.report["environment"] = (
            await self.call("creo_check_environment", {})
        ).structured_content
        self.save()
        await wait_for_startup(self.client, self.report, self.output)
        try:
            matrix = dict(
                (case, (name, dimensions, foil))
                for case, name, dimensions, foil in seed_cases(self.library["manifest"])
            )
            if "matrix_five_smooth" not in self.selection:
                self.report["five_smooth_gate"] = "not_in_selection"
            for case in self.selection:
                if case in NEGATIVE_CASE_ORDER:
                    await self.run_negative(case)
                    continue
                name, dimensions, foil = matrix[case]
                try:
                    await self.run_positive(case, name, dimensions, foil)
                except Exception:
                    if case == "matrix_five_smooth":
                        # T01 handover: without a closed first five_smooth the
                        # remaining 14 items must not be started.
                        self.report["five_smooth_gate"] = "not_closed"
                        self.report["stopping_reason"] = (
                            "matrix_five_smooth did not close create+edit with "
                            "saved_file_reloaded_and_verified=true; remaining cases not started"
                        )
                    self.save()
                    raise
                if case == "matrix_five_smooth":
                    self.report["five_smooth_gate"] = "closed_loop"
                    self.save()
            self.report["source_files_unchanged"] = all(
                hashlib.sha256(self.library["source_files"][name].read_bytes()).hexdigest()
                == self.library["seeds"][name]["sha256"]
                for name in self.library["seeds"]
            )
            assert self.report["source_files_unchanged"]
            self.report["native_acceptance"] = "recorded"
            self.report["success"] = True
        except Exception as error:
            self.report["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            self.save()


async def live(output: Path, run_id: str, selection: list[str], library_info: dict) -> None:
    from tools.test_t05_native import require_manual_start

    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
        ),
        read_timeout_seconds=60,
    ) as client:
        runner = SeedMatrixRunner(client, output, run_id, selection, library_info)
        runner.save()
        await runner.run_all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-library", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--case", action="append", dest="cases", default=None, metavar="NAME")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    run_id = new_run_id()
    try:
        selection = resolve_selection(args.cases)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2
    try:
        library_info = load_seed_library(args.seed_library.resolve())
        results = offline_checks(library_info, selection, run_id)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2
    try:
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2

    if not (args.live and args.confirm_session_usable):
        reason = (
            "both --live and --confirm-session-usable are required"
            if (args.live or args.confirm_session_usable)
            else "no live flags given"
        )
        print(f"OFFLINE ONLY ({reason}): no MCP client, no Toolkit call, no Creo connection.")
        write_offline_report(output, run_id, selection, library_info, results)
        print(
            f"manifest_seed_count={results['manifest_seed_count']} "
            f"hashes_verified={results['hashes_verified']}"
        )
        print(
            f"positive_cases={len(results['positive_cases'])} "
            f"negative_cases={len(results['negative_cases'])} validated"
        )
        print(f"report={output}")
        print("LIVE NOT RUN: no 15+2 native result was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id, selection, library_info))
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
