"""Immutable callback payloads and an operator-started, persistent registration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL = 3
LOADER_ABI = 1
CONTRACT = "blend-selection-v3-ordered-curves-mm"
REGISTRY_FILENAME = "blend_callback_protk.dat"
# A loader generation key is the normalized fingerprint, optionally with a
# -<sha256[:12]> suffix when a rebuilt (nondeterministic) DLL must coexist
# with the historical immutable copy recorded under the same fingerprint.
GENERATION_KEY = re.compile(r"[0-9a-f]{64}(?:-[0-9a-f]{12})?\Z")
# A callback result file fresher than this is treated as recent runtime
# evidence and keeps its loader generation out of reclaim candidates.
_READY_FRESH_SECONDS = 30 * 24 * 3600


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _publish(path: Path, content: str) -> None:
    """Replace metadata atomically; never touch a published binary."""
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _immutable(source: Path, target: Path, digest: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if _digest(target) != digest:
            raise ValueError("Immutable Blend callback copy was changed; inspect it before setup")
        return
    # A hard link publishes a complete file without replacing an existing image.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(source.read_bytes())
            output.flush()
            os.fsync(output.fileno())
        if _digest(temporary) != digest:
            raise ValueError("Callback build changed while preparing immutable artifacts")
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_callback(build: Path, dll_sha256: str, loader_fingerprint: str) -> dict:
    """Prepare a future operator startup; never load, unload or replace loaded DLLs."""
    dll = build / "creo_blend_sync.dll"
    loader = build / "creo_blend_loader.dll"
    if not re.fullmatch("[0-9a-f]{64}", dll_sha256) or _digest(dll) != dll_sha256:
        raise ValueError("Blend callback hash does not match the current build")
    if not GENERATION_KEY.fullmatch(loader_fingerprint):
        raise ValueError("Invalid callback loader generation")
    root = build.parent.resolve()
    directory = build / "blend_callback" / dll_sha256
    loader_directory = build / "blend_loader" / loader_fingerprint
    target = directory / "callback.dll"
    loader_target = loader_directory / "loader.dll"
    loader_sha256 = _digest(loader)
    if (
        len(str(target.resolve())) >= 260
        or len(str(loader_target.resolve())) >= 260
        or any(c in str(root) for c in "\r\n")
    ):
        raise ValueError("Blend callback setup path is too long or contains a newline")
    _immutable(dll, target, dll_sha256)
    _immutable(loader, loader_target, loader_sha256)
    root_tag = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:8]
    command = "MechDogBlend_" + dll_sha256[:24] + "_" + root_tag
    bootstrap = {
        "protocol": PROTOCOL,
        "contract": CONTRACT,
        "command": command,
        "resource_root": str(root),
        "dll_sha256": dll_sha256,
    }
    metadata = {
        **bootstrap,
        "loader_abi": LOADER_ABI,
        "loader_fingerprint": loader_fingerprint,
        "loader_sha256": loader_sha256,
        "loader_file": str(loader_target.resolve()),
        "module_file": str(target.resolve()),
        "ready_file": str((loader_directory / "callback_result.json").resolve()),
        "registry_file": str((build / REGISTRY_FILENAME).resolve()),
        "registry_generation_file": str((loader_directory / "protk.dat").resolve()),
        "registry_shortcut": str((build / REGISTRY_FILENAME).resolve()),
        "persistent_registration_config": str((build / "blend_callback.config.pro").resolve()),
        "setup": (
            "One-time setup: in Creo Auxiliary Applications register registry_file "
            "(build/blend_callback_protk.dat), Start it once and review the DLL prompt "
            "yourself. For persistence across Creo restarts, merge the protkdat line from "
            "build/blend_callback.config.pro into the config.pro your Creo actually loads; "
            "the snippet is never loaded automatically. If the entry disappears after "
            "restart, fix that persistent configuration once; repeatedly selecting the dat "
            "file is temporary. An existing entry that is not running needs manual Start "
            "(delay_start true). After a payload upgrade, normally restart Creo and start "
            "the same registered application; keep its registry_file unchanged. Legacy "
            "protocol-2 registration requires one explicit migration. A changed loader/SDK "
            "generation needs a fresh Creo startup reading the same persistent registry "
            "file; a session-only registration may need selecting that file again. Query "
            "creo_callback_status before a direct Blend; only readiness=ready allows it "
            "(seed lofts via creo_new_loft_part need no callback). MCP never changes "
            "security policy."
        ),
    }
    bootstrap_file = directory / "callback_bootstrap.json"
    bootstrap_text = json.dumps(bootstrap, indent=2) + "\n"
    if bootstrap_file.exists() and bootstrap_file.read_text(encoding="utf-8") != bootstrap_text:
        raise ValueError("Immutable callback bootstrap changed; inspect it before setup")
    _publish(bootstrap_file, bootstrap_text)
    registry = (
        f"name MCP_CREO_MechDog Blend {root_tag}\nstartup dll\n"
        f"exec_file {metadata['loader_file']}\ntext_dir {loader_directory.resolve()}\n"
        "allow_stop true\ndelay_start true\nend\n"
    )
    _publish(loader_directory / "protk.dat", registry)
    _publish(build / REGISTRY_FILENAME, registry)
    _publish(build / "blend_callback.config.pro", f"protkdat {metadata['registry_file']}\n")
    # Publish the selection only after every immutable artifact is complete. Old
    # payloads/loader generations remain available for an explicit rollback.
    _publish(
        loader_directory / "deployment.json",
        json.dumps({"loader_abi": LOADER_ABI, "dll_sha256": dll_sha256}, indent=2) + "\n",
    )
    _publish(build / "blend_callback_setup.json", json.dumps(metadata, indent=2) + "\n")
    return metadata


def generation_inventory(build: Path, *, probe_readiness: str | None = None) -> dict:
    """Read-only dry-run inventory of loader and payload generations (DEV-027).

    References are classified instead of guessed: a local registration
    reference (setup metadata and registry exec_file, tracked separately),
    runtime evidence (a locked DLL image, a fresh callback result file, or a
    ready native probe), and an unknown state for anything the local records
    cannot prove. A generation is a reclaim candidate only when every
    dimension is provably unreferenced. Missing, corrupt or conflicting local
    records keep the affected generations; anything that cannot be proven
    unreferenced goes to needs_review. Nothing is deleted; reclamation is a
    separate, explicitly reviewed operation.
    """

    def _sha(path: Path) -> str | None:
        try:
            return _digest(path)
        except OSError:
            return None

    def _read_json(path: Path):
        try:
            return True, json.loads(path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return False, None
        except (OSError, ValueError):
            return True, None

    def _locked(path: Path) -> bool:
        # Windows locks a loaded DLL image against write access; a plain
        # exclusive open attempt therefore detects a resident module without
        # loading or changing anything.
        if not path.is_file():
            return False
        try:
            handle = open(path, "r+b")
        except OSError:
            return True
        handle.close()
        return False

    def _fresh(path: Path, max_age_seconds: int) -> bool:
        try:
            age = datetime.now().timestamp() - path.stat().st_mtime
        except OSError:
            return False
        return 0 <= age <= max_age_seconds

    stamp_present, stamp = _read_json(build / "blend_loader_build.json")
    stamp_ok = stamp_present and isinstance(stamp, dict)
    setup_present, setup = _read_json(build / "blend_callback_setup.json")
    setup_ok = setup_present and isinstance(setup, dict)
    records_status = {
        "build_stamp": "ok" if stamp_ok else ("missing" if not stamp_present else "corrupt"),
        "setup": "ok" if setup_ok else ("missing" if not setup_present else "corrupt"),
    }
    current_key = stamp.get("generation_key") if stamp_ok else None
    registered_loader = setup.get("loader_file") if setup_ok else None
    registered_module = setup.get("module_file") if setup_ok else None
    registry_loader = None
    registry_lines = None
    try:
        registry_lines = (build / REGISTRY_FILENAME).read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        records_status["registry"] = "missing"
    except OSError:
        records_status["registry"] = "corrupt"
    else:
        for line in registry_lines:
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] == "exec_file":
                registry_loader = parts[1].strip()
        records_status["registry"] = "ok"

    def _generation_of(loader_file: str | None) -> str | None:
        if not loader_file:
            return None
        try:
            parent = Path(loader_file).resolve().parent
        except OSError:
            return None
        if parent.parent == (build / "blend_loader").resolve():
            return parent.name
        return None

    referenced = {
        source: _generation_of(value)
        for source, value in (
            ("setup", registered_loader),
            ("registry", registry_loader),
        )
    }
    referenced = {k: v for k, v in referenced.items() if v}
    conflict_keys = set(referenced.values())
    record_conflict = len(conflict_keys) > 1
    conflict_keys = conflict_keys if record_conflict else set()
    records_definitive = (
        records_status["build_stamp"] == "ok"
        and records_status["setup"] == "ok"
        and records_status["registry"] == "ok"
        and not record_conflict
    )

    # Runtime evidence from the native probe, when the caller shares it: a
    # ready probe proves the setup-recorded loader and payload are resident.
    runtime_probe = {
        "readiness": probe_readiness,
        "running_generation": (
            _generation_of(registered_loader) if probe_readiness == "ready" and setup_ok else None
        ),
    }

    generations = []
    candidates = []
    needs_review = []
    payload_usage: dict[str, list[str]] = {}
    root = build / "blend_loader"
    if root.is_dir():
        for directory in sorted(root.iterdir()):
            if not directory.is_dir():
                continue
            loader = directory / "loader.dll"
            sha = _sha(loader)
            reasons: list[str] = []
            is_current = directory.name == current_key if current_key else None
            if records_status["build_stamp"] != "ok":
                reasons.append(f"build_stamp_{records_status['build_stamp']}")
            if records_status["setup"] != "ok":
                reasons.append(f"setup_{records_status['setup']}")
            if records_status["registry"] != "ok":
                reasons.append(f"registry_{records_status['registry']}")
            if directory.name in conflict_keys:
                reasons.append("record_conflict")
            sources = [source for source, key in referenced.items() if key == directory.name]
            deployment_present, deployment = _read_json(directory / "deployment.json")
            deployment_ok = deployment_present and isinstance(deployment, dict)
            if not deployment_present:
                reasons.append("deployment_missing")
            elif not deployment_ok:
                reasons.append("deployment_corrupt")
            payload_key = deployment.get("dll_sha256") if deployment_ok else None
            if payload_key:
                payload_usage.setdefault(payload_key, []).append(directory.name)
                payload_dll = build / "blend_callback" / payload_key / "callback.dll"
                if not payload_dll.is_file():
                    reasons.append("deployment_payload_missing")
                elif _sha(payload_dll) != payload_key:
                    reasons.append("deployment_payload_mismatch")
            elif deployment_ok:
                reasons.append("deployment_payload_unrecorded")
            evidence: list[str] = []
            if sha is not None and _locked(loader):
                evidence.append("file_locked")
            if _fresh(directory / "callback_result.json", _READY_FRESH_SECONDS):
                evidence.append("recent_ready_file")
            if runtime_probe["running_generation"] == directory.name:
                evidence.append("probe_ready")
            is_referenced = bool(sources) or bool(evidence)
            if sha is None:
                reasons.append("loader_dll_unreadable")
            entry = {
                "generation_key": directory.name,
                "loader_sha256": sha,
                "current": bool(is_current),
                "registered": bool(sources),
                "registered_by": sources,
                "runtime_evidence": evidence,
                "referenced": is_referenced,
                "deployment_dll_sha256": payload_key,
                "bytes": loader.stat().st_size if loader.is_file() else None,
                "needs_review": bool(reasons),
                "review_reasons": reasons,
            }
            generations.append(entry)
            if reasons:
                needs_review.append(directory.name)
            elif not is_referenced and is_current is False:
                candidates.append(directory.name)

    payloads = []
    payload_candidates = []
    payload_review = []
    payload_root = build / "blend_callback"
    if payload_root.is_dir():
        for directory in sorted(payload_root.iterdir()):
            if not directory.is_dir():
                continue
            dll = directory / "callback.dll"
            sha = _sha(dll)
            reasons: list[str] = []
            if sha is None:
                reasons.append("callback_dll_unreadable")
            elif sha != directory.name:
                reasons.append("callback_dll_mismatch")
            if not (directory / "callback_bootstrap.json").is_file():
                reasons.append("bootstrap_missing")
            used_by = payload_usage.get(directory.name, [])
            locked = sha is not None and _locked(dll)
            current_payload = None
            if setup_ok and registered_module:
                try:
                    current_payload = (
                        Path(registered_module).resolve().parent.name
                        if (build / "blend_callback").resolve()
                        in Path(registered_module).resolve().parents
                        else None
                    )
                except OSError:
                    current_payload = None
            payload_referenced = bool(used_by) or directory.name == current_payload or locked
            if not payload_referenced and not records_definitive:
                # Only definitive records can prove a payload generation is
                # referenced by no surviving loader deployment or selection.
                reasons.append("records_not_definitive")
            entry = {
                "payload_sha256": directory.name,
                "callback_dll_sha256": sha,
                "bytes": dll.stat().st_size if dll.is_file() else None,
                "referenced_by_loader_generations": used_by,
                "current": directory.name == current_payload,
                "runtime_evidence": ["file_locked"] if locked else [],
                "referenced": payload_referenced,
                "needs_review": bool(reasons),
                "review_reasons": reasons,
            }
            payloads.append(entry)
            if reasons:
                payload_review.append(directory.name)
            elif not payload_referenced:
                payload_candidates.append(directory.name)

    return {
        "dry_run": True,
        "deleted": False,
        "note": (
            "Reclaim candidates require every reference dimension provably "
            "unreferenced: definitive local records, no registration reference, "
            "no runtime evidence and a consistent deployment record. Missing, "
            "corrupt or conflicting records keep the affected generations; "
            "anything unprovable is listed in needs_review. Nothing is deleted; "
            "actual reclamation is a separate reviewed operation"
        ),
        "records_status": records_status,
        "records_definitive": records_definitive,
        "record_conflict": record_conflict,
        "conflict_generations": sorted(conflict_keys),
        "current_generation_key": current_key,
        "current_loader_sha256": stamp.get("sha256") if stamp_ok else None,
        "registered_loader_file": registered_loader,
        "registry_exec_file": registry_loader,
        "runtime_probe": runtime_probe,
        "generation_count": len(generations),
        "generations": generations,
        "reclaim_candidates": candidates,
        "needs_review": needs_review,
        "payload_generation_count": len(payloads),
        "payload_generations": payloads,
        "reclaim_candidates_payload": payload_candidates,
        "needs_review_payload": payload_review,
    }


def callback_setup_status(build: Path) -> dict:
    """Artifact inspection is separate from a live, nonce-verified session probe."""
    base = {
        "readiness": "unknown",
        "registration_status": "unknown",
        "runtime_readiness": "Call creo_callback_status for a live read-only probe",
        "status_tool": "creo_callback_status",
    }
    try:
        data = json.loads((build / "blend_callback_setup.json").read_text(encoding="utf-8"))
        if data.get("protocol") == 2:
            return {
                **base,
                "artifact_status": "legacy",
                "reason": "legacy_registration",
                "instruction": "Build this version, then migrate once to its stable loader registration",
            }
        if (
            data["protocol"] != PROTOCOL
            or data["contract"] != CONTRACT
            or data["loader_abi"] != LOADER_ABI
            or _digest(Path(data["module_file"])) != data["dll_sha256"]
            or _digest(Path(data["loader_file"])) != data["loader_sha256"]
            or Path(data["resource_root"]).resolve() != build.parent.resolve()
            or json.loads(
                (Path(data["loader_file"]).parent / "deployment.json").read_text(encoding="utf-8")
            )
            != {"loader_abi": LOADER_ABI, "dll_sha256": data["dll_sha256"]}
            or not Path(data["registry_file"]).is_file()
        ):
            raise ValueError("Invalid callback setup")
        return {
            **base,
            **{
                key: data[key]
                for key in (
                    "protocol",
                    "contract",
                    "loader_abi",
                    "loader_fingerprint",
                    "loader_sha256",
                    "registry_file",
                    "registry_generation_file",
                    "registry_shortcut",
                    "persistent_registration_config",
                    "loader_file",
                    "module_file",
                    "dll_sha256",
                    "resource_root",
                )
            },
            "artifact_status": "prepared",
            "manual_setup_when_not_loaded": True,
            "instruction": data["setup"],
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {
            **base,
            "artifact_status": "not_prepared",
            "instruction": "Build the native worker to create verified callback setup artifacts",
        }


def unknown_readiness(artifacts: dict, reason: str, **details) -> dict:
    """Never infer GUI registration or runtime load state from a failed probe."""
    return {
        **artifacts,
        "readiness": "unknown",
        "reason": reason,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": True,
        "instruction": (
            "Inspect session/channel details and finish modal commands, then query again. "
            "Registration and loaded state cannot be inferred from this failed probe. "
            "Preserve unknown jobs/models; do not resubmit unknown_outcome."
        ),
        **details,
    }
