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


def generation_inventory(build: Path) -> dict:
    """Read-only dry-run inventory of loader generations (DEV-027).

    Identifies the current generation (build stamp), the registered one
    (setup metadata / registry exec_file) and every remaining generation
    directory as a reclaim candidate. Nothing is deleted; reclamation is a
    separate, explicitly reviewed operation.
    """

    def _sha(path: Path) -> str | None:
        try:
            return _digest(path)
        except OSError:
            return None

    stamp = {}
    try:
        stamp = json.loads((build / "blend_loader_build.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        pass
    current_key = stamp.get("generation_key") if isinstance(stamp, dict) else None
    setup = {}
    try:
        setup = json.loads((build / "blend_callback_setup.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        pass
    registered_loader = setup.get("loader_file") if isinstance(setup, dict) else None
    registry_loader = None
    try:
        for line in (build / REGISTRY_FILENAME).read_text(encoding="utf-8-sig").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] == "exec_file":
                registry_loader = parts[1].strip()
    except OSError:
        pass

    generations = []
    candidates = []
    root = build / "blend_loader"
    if root.is_dir():
        for directory in sorted(root.iterdir()):
            if not directory.is_dir():
                continue
            loader = directory / "loader.dll"
            sha = _sha(loader)
            is_current = directory.name == current_key
            is_registered = any(
                registered and loader.is_file() and Path(registered).resolve() == loader.resolve()
                for registered in (registered_loader, registry_loader)
            )
            entry = {
                "generation_key": directory.name,
                "loader_sha256": sha,
                "current": is_current,
                "registered": is_registered,
                "bytes": loader.stat().st_size if loader.is_file() else None,
            }
            generations.append(entry)
            if not is_current and not is_registered:
                candidates.append(entry["generation_key"])
    return {
        "dry_run": True,
        "deleted": False,
        "note": (
            "Reclaim candidates are not deleted by this inventory; loaded "
            "modules and valid registrations are never candidates. Actual "
            "reclamation is a separate reviewed operation"
        ),
        "current_generation_key": current_key,
        "current_loader_sha256": stamp.get("sha256") if isinstance(stamp, dict) else None,
        "registered_loader_file": registered_loader,
        "registry_exec_file": registry_loader,
        "generation_count": len(generations),
        "generations": generations,
        "reclaim_candidates": candidates,
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
