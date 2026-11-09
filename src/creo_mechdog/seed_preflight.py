"""B1/F01: offline, queryable compatibility preflight for native loft seeds.

This module never connects to Creo, never trial-loads a seed and never claims
the current session can load one. It compares the requested section geometry
with the published seed metadata and the bytes on disk, so an incompatible
explicit seed is refused *before* a job is submitted.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from creo_mechdog import seeds


def preflight(
    section_count: int,
    interpolation: str,
    seed_file: str,
    seed_feature_id: int,
) -> dict:
    """Return a queryable preflight verdict for one seed/section combination."""
    source = Path(seed_file).expanduser()
    try:
        digest: str | None = hashlib.sha256(source.read_bytes()).hexdigest()
        read_error: str | None = None
    except OSError as error:
        digest, read_error = None, str(error)
    entry = seeds.manifest_entry_by_digest(digest) if digest else None
    reasons: list[str] = []
    seed = {
        "seed_file": str(source),
        "sha256": digest,
        "name": None,
        "relative_path": None,
        "section_count": None,
        "interpolation": None,
        "seed_feature_id": None,
    }
    if entry is None:
        verdict = "unverified"
        reasons.append(
            f"Seed bytes could not be read ({read_error}); section count and "
            "interpolation cannot be checked before submission"
            if read_error
            else "Seed bytes are not in the published manifest; section count and "
            "interpolation cannot be checked before submission"
        )
    else:
        seed.update(
            {
                "name": entry.get("name"),
                "relative_path": entry.get("relative_path"),
                "section_count": entry.get("section_count"),
                "interpolation": entry.get("interpolation"),
                "seed_feature_id": entry.get("seed_feature_id"),
            }
        )
        if entry.get("section_count") != section_count:
            reasons.append(
                f"Seed requires {entry.get('section_count')} sections but the plan has {section_count}"
            )
        if entry.get("interpolation") != interpolation:
            reasons.append(
                f"Seed interpolation is {entry.get('interpolation')!r} but the plan requests {interpolation!r}"
            )
        if entry.get("seed_feature_id") != seed_feature_id:
            reasons.append(
                f"seed_feature_id {seed_feature_id} does not match the manifest id "
                f"{entry.get('seed_feature_id')}"
            )
        verdict = "incompatible" if reasons else "compatible"
    next_steps = [
        "Omit seed_file/seed_feature_id to let creo_new_loft_part select a matching seed",
        "Call creo_list_seeds to see the published section counts and interpolation modes",
    ]
    if verdict == "incompatible":
        next_steps.insert(0, "Fix the seed/section mismatch before submitting a job")
    return {
        "verdict": verdict,
        "checked_without_session": True,
        "callback_required": False,
        "callback_free_route": seeds.CALLBACK_FREE_ROUTE,
        "session_loadable": None,
        "section_count": section_count,
        "interpolation": interpolation,
        "seed": seed,
        "reasons": reasons,
        "next_steps": next_steps,
        "available_scope": seeds.AVAILABLE_SCOPE,
        "native_validation": seeds.NO_NATIVE_PROBE,
    }
