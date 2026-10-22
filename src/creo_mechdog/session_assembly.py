"""Bounded, read-only inspection of a resident session assembly (FEAT-045)."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

import bridge
from creo_mechdog.model_queries import decode_cursor, encode_cursor, fingerprint

SNAPSHOT_SECONDS = 600
PAGE_BYTES = 32 * 1024
REFRESH_GUIDANCE = (
    "Omit cursor to re-collect the assembly snapshot; a query carrying a cursor "
    "keeps reading its frozen snapshot and never reflects later session changes"
)


def _selection() -> str:
    config = bridge.config()
    return fingerprint({key: config.get(key) for key in ("creo_root", "creo_session_id")})


def _probe(directory: Path) -> dict:
    exe = bridge.build_native()
    with (directory / "worker.log").open("wb") as log:
        proc = subprocess.run(
            [str(exe), "generic", str(directory)],
            cwd=directory,
            env=bridge.native_environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=115,
            creationflags=bridge.HIDDEN,
        )
    result = bridge.read_json(directory / "native_result.json")
    if (
        proc.returncode
        or result.get("delivery_complete") is not True
        or result.get("disconnect_code") != 0
        or result.get("success") is not True
    ):
        raise RuntimeError(result.get("message", "Assembly inspection could not be confirmed"))
    return result


def inspect_session_assembly(name: str, limit: int = 20, cursor: str | None = None) -> dict:
    if not isinstance(name, str) or not name.strip() or len(name) > 256:
        raise ValueError("name must be a non-empty assembly name (1-256 chars)")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1-50")
    page = decode_cursor(cursor)
    if page is None:
        with bridge.toolkit_lock(operation="inspect_session_assembly"):
            job_id = uuid.uuid4().hex
            directory = bridge.job_path(job_id)
            (directory / "output").mkdir(parents=True)
            model = {
                "model_id": None,
                "model_name": "session_assembly_inspection",
                "aliases": {},
                "output_directory": str(directory / "output"),
                "part_file": None,
            }
            request = {
                "model": model,
                "new": False,
                "operations": [],
                "readonly": True,
                "template_file": "",
                "components": {},
                "session_assembly": {"name": name},
            }
            manifest = {
                "job_id": job_id,
                "kind": "session_assembly_inspection",
                "status": "running",
                "created_at": bridge.now(),
                "requested_assembly": name,
            }
            bridge.write_json(directory / "request.json", request)
            bridge.write_json(directory / "job.json", manifest)
            try:
                selection = _selection()
                result = _probe(directory)
                snapshot = {
                    "assembly": result["assembly"],
                    "components": result["components"],
                    "created": time.time(),
                    "checked_at": bridge.now(),
                    "session_fingerprint": result["session_fingerprint"],
                    "selection": selection,
                    "complete": result.get("complete", False),
                    "truncated": result.get("truncated", False),
                    "incomplete": result.get("incomplete", False),
                }
                bridge.write_json(directory / "session_assembly.json", snapshot, durable=True)
                manifest["status"] = "succeeded"
            except Exception as error:
                manifest.update(status="failed", message=str(error))
                raise
            finally:
                manifest["finished_at"] = bridge.now()
                bridge.write_json(directory / "job.json", manifest, durable=True)
        offset = 0
    else:
        if page.get("kind") != "session_assembly" or not bridge.JOB_ID.fullmatch(
            page.get("snapshot", "")
        ):
            raise ValueError("Invalid session assembly cursor")
        job_id = page["snapshot"]
        file = bridge.job_path(job_id) / "session_assembly.json"
        if not file.is_file() or file.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Assembly snapshot is unavailable; inspect again without cursor")
        snapshot = bridge.read_json(file)
        if (
            time.time() - snapshot["created"] > SNAPSHOT_SECONDS
            or snapshot["selection"] != _selection()
        ):
            raise ValueError(
                "Assembly snapshot expired or session selection changed; inspect again"
            )
        if page.get("fingerprint") != fingerprint(snapshot):
            raise ValueError("Assembly snapshot changed; inspect again")
        if page.get("name") != name:
            raise ValueError("Assembly cursor belongs to a different assembly name")
        offset = page["offset"]
    components = snapshot["components"]
    if offset > len(components):
        raise ValueError("Invalid session assembly cursor offset")
    response = {
        "assembly": snapshot["assembly"],
        "components": [],
        "total": len(components),
        "checked_at": snapshot["checked_at"],
        "session_fingerprint": snapshot["session_fingerprint"],
        "snapshot_id": job_id,
        "complete": snapshot["complete"],
        "truncated": snapshot["truncated"],
        "incomplete": snapshot["incomplete"],
        "next_cursor": None,
        "snapshot_only": True,
        "snapshot_age_seconds": max(0, int(time.time() - snapshot["created"])),
        "expires_in_seconds": max(0, int(SNAPSHOT_SECONDS - (time.time() - snapshot["created"]))),
        "refresh_guidance": REFRESH_GUIDANCE,
        "transform_convention": (
            "row-vector 4x4 matrices in Creo ProMatrix order (p' = p * M); translation "
            "occupies the last row; units follow the assembly (mm); transform_to_parent "
            "maps member coordinates into the owning assembly, transform_to_root into "
            "the inspected root assembly"
        ),
        "readonly_note": (
            "inspection only: no component loading, activation, regeneration, save, "
            "adoption or managed revision; repeated component instances are listed "
            "separately with their own occurrence paths and transforms"
        ),
    }
    for item in components[offset : offset + limit]:
        response["components"].append(item)
        if len(json.dumps(response, ensure_ascii=False).encode("utf-8")) > PAGE_BYTES - 1024:
            response["components"].pop()
            if not response["components"]:
                raise ValueError("One assembly component exceeds the response byte budget")
            break
    next_offset = offset + len(response["components"])
    if next_offset < len(components):
        response["next_cursor"] = encode_cursor(
            {
                "kind": "session_assembly",
                "snapshot": job_id,
                "offset": next_offset,
                "fingerprint": fingerprint(snapshot),
                "name": name,
            }
        )
    return response
