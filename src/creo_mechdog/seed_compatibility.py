"""Seed provenance and historical native load evidence, never an implicit Toolkit probe."""

from __future__ import annotations

import json
import re
from pathlib import Path

import bridge
from creo_mechdog.recovery import file_identity

OBSERVATION_FIELDS = (
    "status",
    "toolkit_code",
    "creo_release_numeric",
    "creo_release_query_code",
    "session_fingerprint",
    "seed_sha256",
    "seed_name",
    "job_id",
    "checked_at",
    "modeling_saved_reloaded_verified",
    "evidence_persisted",
)

# "available" is a statement about file bytes only. A seed whose SHA256 matches the
# published manifest can still be rejected by the running Creo.
AVAILABLE_SCOPE = (
    "available means the seed file bytes match the published SHA256; it does not mean the "
    "current Creo session can load this seed"
)

# Evidence that is on record about seed loading, kept apart from any single session.
COMPATIBILITY_EVIDENCE = (
    "external Creo 9 reported the tested seeds failing with -16; a Creo 10 three-section "
    "success is on record; the current session and the other seeds are unverified"
)

# The UGC header token ("PART 2128 ...") stays an unverified clue. No traceable proof
# ties it to a Creo product version, so it never becomes seed_build_version
# (FEAT-030/BUG-034).
UGC_HEADER_PATTERN = re.compile(r"^#UGC:\d+\s+PART\s+(\d+)")

LOCAL_PROVENANCE_DIRECTORY = "build/seed_provenance"
_DIGEST_PATTERN = r"[a-f0-9]{64}"
_LOAD_API = "ProMdlFiletypeLoad"


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(_DIGEST_PATTERN, value) is not None


def ugc_header_clue(path: Path | None) -> dict:
    """The raw UGC header token as a diagnostic clue, never as a product version."""
    clue = {
        "ugc_header_line": None,
        "ugc_part_version_token": None,
        "ugc_interpretation": "unverified_clue",
        "ugc_note": (
            "UGC header token only; no proven mapping to a Creo product version, so it never "
            "sets seed_build_version"
        ),
    }
    if path is None:
        return clue
    try:
        with Path(path).open("rb") as stream:
            head = stream.read(256)
    except OSError:
        return clue
    line = head.split(b"\n", 1)[0].decode("ascii", errors="replace").strip()[:160]
    clue["ugc_header_line"] = line or None
    match = UGC_HEADER_PATTERN.match(line)
    if match:
        clue["ugc_part_version_token"] = int(match.group(1))
    return clue


def _manifest_provenance(entry: dict, digest: str) -> dict | None:
    """A manifest entry is a traceable generation record only while the file still
    hashes to the recorded SHA256."""
    version = entry.get("seed_build_version")
    if not isinstance(version, str) or not version.strip():
        return None
    if entry.get("sha256") != digest:
        return None
    source = entry.get("seed_build_version_source")
    evidence = entry.get("seed_build_version_evidence")
    return {
        "seed_build_version": version.strip(),
        "source": source.strip() if isinstance(source, str) and source.strip() else "seed_manifest",
        "evidence": evidence
        if isinstance(evidence, str) and evidence.strip()
        else "docs/seed_manifest.json",
        "release_numeric": entry.get("seed_build_version_release_numeric"),
    }


def _native_provenance(digest: str) -> dict | None:
    """Machine-written native evidence bound to these exact seed bytes."""
    directory = bridge.ROOT / LOCAL_PROVENANCE_DIRECTORY / digest
    if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
        return None
    for file in sorted(directory.glob("*.json"), reverse=True)[:2]:
        try:
            if file.is_symlink() or file.stat().st_size > 16384:
                continue
            row = bridge.read_json(file)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if not isinstance(row, dict) or row.get("seed_sha256") != digest:
            continue
        version = row.get("seed_build_version")
        if not isinstance(version, str) or not version.strip():
            continue
        evidence = row.get("job_id")
        return {
            "seed_build_version": version.strip(),
            "source": "native_evidence",
            "evidence": evidence if isinstance(evidence, str) and evidence.strip() else file.name,
            "release_numeric": row.get("release_numeric"),
        }
    return None


def build_version_evidence(digest: str | None, entry: dict | None = None) -> dict:
    """Resolve the seed production version from records bound to this exact digest.

    The production version stays null unless a traceable generation record or
    reliable native evidence names it for these seed bytes.
    """
    unknown = {
        "seed_build_version": None,
        "seed_build_version_source": None,
        "seed_build_version_evidence": None,
        "seed_build_version_status": "unknown",
        "seed_build_version_release_numeric": None,
    }
    if not _is_digest(digest):
        return unknown
    candidates = []
    if entry:
        manifest_row = _manifest_provenance(entry, digest)
        if manifest_row:
            candidates.append(manifest_row)
    native_row = _native_provenance(digest)
    if native_row:
        candidates.append(native_row)
    if not candidates:
        return unknown
    row = candidates[0]
    return {
        "seed_build_version": row["seed_build_version"],
        "seed_build_version_source": row["source"],
        "seed_build_version_evidence": row["evidence"],
        "seed_build_version_status": "resolved",
        "seed_build_version_release_numeric": row["release_numeric"],
    }


def record_native_build_evidence(
    digest: str,
    release_numeric: int,
    *,
    seed_build_version: str,
    job_id: str,
    checked_at: str | None = None,
) -> dict:
    """Store native evidence that a session produced these seed bytes.

    Only a native run that can attest the producing release may call this; the
    record stays bound to the exact seed SHA256 it was written for.
    """
    if not _is_digest(digest):
        raise ValueError("digest must be the 64 hexadecimal SHA256 of the seed bytes")
    if isinstance(release_numeric, bool) or not isinstance(release_numeric, int):
        raise ValueError("release_numeric must be the integer Creo release number")
    if not isinstance(seed_build_version, str) or not seed_build_version.strip():
        raise ValueError("seed_build_version must name the producing Creo version")
    record = {
        "seed_sha256": digest,
        "seed_build_version": seed_build_version.strip(),
        "release_numeric": release_numeric,
        "evidence_kind": "native_evidence",
        "job_id": job_id,
        "checked_at": checked_at or bridge.now(),
    }
    target = bridge.ROOT / LOCAL_PROVENANCE_DIRECTORY / digest / f"{release_numeric}-{job_id}.json"
    if any(parent.is_symlink() or parent.is_junction() for parent in target.parents):
        raise ValueError("Seed provenance directory cannot traverse links")
    target.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_json(target, record)
    return record


def _observations(digest: str | None) -> list[dict]:
    """Bounded history for these exact seed bytes; none of it proves this session."""
    rows: list[dict] = []
    if not _is_digest(digest):
        return rows
    directory = bridge.ROOT / "build/seed_compatibility" / digest
    if directory.is_dir() and not directory.is_symlink() and not directory.is_junction():
        for file in sorted(directory.glob("*.json"), reverse=True)[:2]:
            try:
                if file.is_symlink() or file.stat().st_size > 16384:
                    continue
                row = bridge.read_json(file)
                if row.get("seed_sha256") == digest and row.get("status") in (
                    "loaded",
                    "load_failed",
                ):
                    view = {key: row[key] for key in OBSERVATION_FIELDS if key in row}
                    if len(json.dumps(view, ensure_ascii=False).encode("utf-8")) <= 1024:
                        rows.append(view)
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    return rows


def metadata(
    entry: dict,
    *,
    actual_sha256: str | None = None,
    seed_path: Path | None = None,
) -> dict:
    """Seed provenance and historical load evidence for one manifest entry.

    ``actual_sha256`` is the SHA256 of the seed file on disk. When it is None the
    manifest's recorded SHA256 is used, which describes the published seed rather
    than the file on disk; pass an empty string when no seed file is present.
    """
    digest = entry.get("sha256") if actual_sha256 is None else actual_sha256
    provenance = build_version_evidence(digest, entry)
    return {
        **provenance,
        "seed_file_diagnostic": ugc_header_clue(seed_path),
        "native_compatibility": {
            "status": "not_verified_for_current_session",
            "scope": AVAILABLE_SCOPE,
            "current_session_loadable": None,
            "observations_note": (
                "historical loads recorded for this exact seed SHA256 in other sessions; none "
                "of them proves the current session can load this seed"
            ),
            "observations": _observations(digest),
        },
    }


def load_failure_diagnosis(request: dict, result: dict, observation: dict) -> dict:
    """Preserve the original API, error code, stage, seed identity and runtime version.

    A version cause is only stated when a provenance record and the session release
    support it; the Toolkit error alone never identifies the reason.
    """
    seed = request.get("loft_seed")
    seed = seed if isinstance(seed, dict) else {}
    digest = observation.get("seed_sha256")
    provenance = build_version_evidence(digest)
    current_release = result.get("creo_release_numeric")
    recorded_release = provenance.get("seed_build_version_release_numeric")
    indication = None
    if (
        isinstance(recorded_release, int)
        and not isinstance(recorded_release, bool)
        and isinstance(current_release, int)
        and not isinstance(current_release, bool)
        and current_release < recorded_release
    ):
        indication = {
            "basis": "recorded_seed_release_numeric",
            "recorded_release_numeric": recorded_release,
            "current_release_numeric": current_release,
            "detail": (
                "The provenance record for this seed SHA256 names release_numeric "
                f"{recorded_release}; the current session reports release_numeric "
                f"{current_release}. The Toolkit error alone does not prove the cause."
            ),
        }
    return {
        "seed_load_succeeded": False,
        "modeling_succeeded": observation.get("modeling_succeeded") is True,
        "toolkit_api": result.get("failed_toolkit_call") or _LOAD_API,
        "toolkit_code": observation.get("toolkit_code"),
        "failed_stage": result.get("failed_stage"),
        "native_message": result.get("message"),
        "seed_name": seed.get("seed_name"),
        "seed_sha256": digest,
        "seed_manifest_sha256": seed.get("seed_manifest_sha256"),
        "seed_source": seed.get("seed_source"),
        "creo_release_numeric": current_release,
        "creo_release_query_code": result.get("creo_release_query_code"),
        "session_fingerprint": result.get("session_fingerprint"),
        "seed_build_version": provenance["seed_build_version"],
        "seed_build_version_status": provenance["seed_build_version_status"],
        "version_incompatibility": indication,
        "cause": (
            "undetermined_by_error_alone"
            if indication is None
            else "recorded_release_newer_than_session_release"
        ),
        "guidance": (
            "Native load failed; the original API, error code and stage are preserved. Check "
            "the seed provenance (seed_build_version stays null when unknown) and the "
            "documented compatibility evidence before assuming a version cause."
        ),
    }


def load_failure_message(result: dict) -> str:
    """A bounded failure line that keeps the original native message intact."""
    evidence = result.get("seed_load_evidence")
    diagnosis = evidence.get("failure_diagnosis") if isinstance(evidence, dict) else None
    original = result.get("native_message") or result.get("message") or ""
    if not isinstance(diagnosis, dict):
        return original if isinstance(original, str) else ""
    seed = diagnosis.get("seed_name") or diagnosis.get("seed_sha256") or "unknown seed"
    parts = [original] if isinstance(original, str) and original else []
    parts.append(
        f"seed load failed: seed={seed} sha256={diagnosis.get('seed_sha256')} "
        f"api={diagnosis.get('toolkit_api')} code={diagnosis.get('toolkit_code')} "
        f"stage={diagnosis.get('failed_stage')}"
    )
    release = diagnosis.get("creo_release_numeric")
    parts.append(
        f"session release_numeric={release}"
        if release is not None
        else "session release_numeric=unknown"
    )
    indication = diagnosis.get("version_incompatibility")
    if isinstance(indication, dict) and indication.get("detail"):
        parts.append(str(indication["detail"]))
    parts.append(str(diagnosis.get("guidance") or ""))
    return " | ".join(part for part in parts if part)


def observe_load(request: dict, result: dict, job_id: str) -> dict | None:
    """Record only the actual load API result; later modeling success is separate."""
    seed = request.get("loft_seed")
    native = result.get("seed_native_load")
    if not seed or not isinstance(native, dict):
        return None
    observation = {
        "status": native.get("status", "not_attempted"),
        "toolkit_code": native.get("toolkit_code"),
        "creo_release_numeric": result.get("creo_release_numeric"),
        "creo_release_query_code": result.get("creo_release_query_code"),
        "session_fingerprint": result.get("session_fingerprint"),
        "seed_sha256": seed.get("snapshot_sha256"),
        "seed_name": seed.get("seed_name"),
        "job_id": job_id,
        "checked_at": bridge.now(),
        "seed_load_succeeded": native.get("status") == "loaded",
        "modeling_succeeded": result.get("success") is True,
        "modeling_saved_reloaded_verified": result.get("saved_file_reloaded_and_verified") is True,
        "evidence_persisted": False,
    }
    release = observation["creo_release_numeric"]
    digest = observation["seed_sha256"]
    if (
        observation["status"] not in ("loaded", "load_failed")
        or isinstance(release, bool)
        or not isinstance(release, int)
        or release <= 0
        or not isinstance(digest, str)
        or not re.fullmatch(_DIGEST_PATTERN, digest)
        or not observation["session_fingerprint"]
    ):
        observation["reason"] = (
            "Native load or runtime identity is incomplete; compatibility remains unverified"
        )
        return observation
    try:
        if file_identity(Path(request["template_file"])).get("sha256") != digest:
            raise ValueError(
                "Seed snapshot changed or exceeded diagnostic budget; load evidence is not attributable"
            )
        target = bridge.ROOT / "build/seed_compatibility" / digest / f"{release}-{job_id}.json"
        if any(p.is_symlink() or p.is_junction() for p in target.parents):
            raise ValueError("Seed evidence directory cannot traverse links")
        target.parent.mkdir(parents=True, exist_ok=True)
        observation["evidence_persisted"] = True
        bridge.write_json(target, observation)
    except (OSError, ValueError, KeyError) as error:
        observation.update(evidence_persisted=False, evidence_error=str(error))
    if observation["status"] == "load_failed":
        observation["failure_diagnosis"] = load_failure_diagnosis(request, result, observation)
    return observation
