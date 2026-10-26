"""Local, file-backed job runner for the Creo Toolkit worker. Never logs licenses."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import msvcrt
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, TextIO

from capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
from creo_mechdog.blend_callback import callback_setup_status, prepare_callback, unknown_readiness
from creo_mechdog.build_fingerprints import (
    FINGERPRINT_ALGORITHM,
    legacy_digest_candidates,
    match_cached_fingerprint,
    normalize_lf,
    normalized_digest,
    read_dependency_snapshot,
)
from creo_mechdog.build_support import (
    compiler_setup_script,
    diagnose_build_failure,
    read_build_log_tail,
    validate_compiler_env,
    validate_local_path,
)
from creo_mechdog.lock_files import open_lock_file
from creo_mechdog.recovery import job_evidence, process_identity

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
MODEL_NAME = re.compile(r"[a-z0-9][a-z0-9_]{0,30}\Z")
MODEL_NAME_RULE = (
    "model_name must be 1-31 characters of lowercase letters, digits and "
    "underscores, starting with a letter or digit; uppercase input is normalized "
    "to lowercase (BUG-069)"
)


def normalize_model_name(value: str) -> str:
    """Validate and normalize a managed model name (see MODEL_NAME_RULE)."""
    if not isinstance(value, str):
        raise ValueError(MODEL_NAME_RULE)
    normalized = value.lower()
    if not MODEL_NAME.fullmatch(normalized):
        raise ValueError(MODEL_NAME_RULE)
    return normalized


JSON_REPLACE_TIMEOUT = 1.0
JSON_REPLACE_MAX_ATTEMPTS = 25

if os.name == "nt":
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_file = _kernel32.CreateFileW
    _create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _create_file.restype = wintypes.HANDLE
    _close_handle = _kernel32.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL
    _set_file_information = _kernel32.SetFileInformationByHandle
    _set_file_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    _set_file_information.restype = wintypes.BOOL

    class _FileRenameInfo(ctypes.Structure):
        _fields_ = (
            ("flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("name_length", wintypes.DWORD),
            ("name", wintypes.WCHAR * 1),
        )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_json_reader(path: Path) -> TextIO:
    if os.name != "nt":
        return path.open(encoding="utf-8-sig")
    # CRT readers omit FILE_SHARE_DELETE and can block an otherwise atomic rename.
    # Share read/write/delete; the handle still reads one complete file version.
    handle = _create_file(str(path), 0x80000000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = str(path)
        raise error
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _close_handle(handle)
        raise
    # open_osfhandle transfers ownership to the descriptor; never close both.
    try:
        return os.fdopen(descriptor, encoding="utf-8-sig")
    except BaseException:
        os.close(descriptor)
        raise


def read_json(path: Path) -> dict:
    with _open_json_reader(path) as stream:
        return json.load(stream)


def _atomic_replace(temp: Path, path: Path) -> None:
    if os.name != "nt":
        os.replace(temp, path)
        return
    # MoveFileEx (os.replace) rejects an open destination even with shared delete.
    # FileRenameInfoEx replaces in one filesystem operation, keeping old readers
    # on the old file. Do not use ReplaceFileW: some failures remove the target.
    handle = _create_file(str(temp), 0x10000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = str(temp)
        raise error
    try:
        name = str(path.absolute()).encode("utf-16-le")
        buffer = ctypes.create_string_buffer(
            max(ctypes.sizeof(_FileRenameInfo), _FileRenameInfo.name.offset + len(name) + 2)
        )
        info = _FileRenameInfo.from_buffer(buffer)
        info.flags = 0x1 | 0x2  # REPLACE_IF_EXISTS | POSIX_SEMANTICS; respects read-only/ACLs.
        info.name_length = len(name)
        ctypes.memmove(ctypes.addressof(buffer) + _FileRenameInfo.name.offset, name, len(name))
        if not _set_file_information(handle, 22, buffer, len(buffer)):  # FileRenameInfoEx
            code = ctypes.get_last_error()
            if code in (1, 50, 87):  # Filesystem/Windows lacks the extended rename API.
                os.replace(temp, path)
            else:
                error = ctypes.WinError(code)
                error.filename = str(temp)
                error.filename2 = str(path)
                raise error
    finally:
        _close_handle(handle)


def _replace_json(temp: Path, path: Path) -> None:
    deadline = time.monotonic() + JSON_REPLACE_TIMEOUT
    delay = 0.005
    for attempt in range(1, JSON_REPLACE_MAX_ATTEMPTS + 1):
        try:
            _atomic_replace(temp, path)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            retryable = os.name == "nt" and winerror in (5, 32, 33)
            # WinError 5 also covers permanent ACL/read-only failures. Read-only
            # is identifiable; ambiguous ACL/external-handle cases share a bound.
            if retryable and winerror == 5:
                try:
                    retryable = not (path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
                except OSError:
                    retryable = False
            remaining = deadline - time.monotonic()
            if not retryable or remaining <= 0 or attempt == JSON_REPLACE_MAX_ATTEMPTS:
                exc.add_note(
                    f"JSON atomic replace failed: {path}; attempts={attempt}; budget={JSON_REPLACE_TIMEOUT}s"
                )
                raise
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 0.05)


def write_json(path: Path, value: dict, *, durable: bool = False) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2)
    temp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    owned = False
    try:
        with temp.open("x", encoding="utf-8") as stream:
            owned = True
            stream.write(content)
            if durable:
                stream.flush()
                os.fsync(stream.fileno())
        _replace_json(temp, path)
    except BaseException as exc:
        if owned:
            try:
                temp.unlink(missing_ok=True)
            except OSError as cleanup_error:
                exc.add_note(
                    f"Could not remove this writer's temporary file {temp}: {cleanup_error}"
                )
        raise


def _write_stamp_text(path: Path, text: str) -> None:
    """Replace a plain-text cache marker atomically."""
    temp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def config() -> dict:
    if not (ROOT / "config.json").is_file():
        raise ValueError(
            "Missing config.json: run setup.ps1, or copy config.example.json and set your installation paths"
        )
    value = read_json(ROOT / "config.json")
    validate_local_path(value.get("creo_root"), "creo_root")
    value["vcvars64_env"] = validate_compiler_env(value.get("vcvars64_env"))
    if value["vcvars64_env"] is None:
        validate_local_path(value.get("vcvars64"), "vcvars64")
    return value


def job_path(job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError(
            "job_id must be the 32 hexadecimal characters returned by an MCP modeling tool"
        )
    path = JOBS / job_id
    if path.is_symlink() or path.is_junction():
        raise ValueError("Job directories cannot be links")
    return path


def validate_spec(
    length: float,
    width: float,
    thickness: float,
    radius: float,
    holes: list[dict],
    model_name: str | None = None,
) -> dict:
    values = {"length": length, "width": width, "thickness": thickness, "radius": radius}
    for name, v in values.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{name} must be a finite number in mm")
    if not 1 <= length <= 1000 or not 1 <= width <= 1000 or not 0.1 <= thickness <= 1000:
        raise ValueError("Supported size: length/width 1–1000 mm, thickness 0.1–1000 mm")
    if radius < 0 or radius >= min(length, width) / 2:
        raise ValueError("corner_radius must be >= 0 and less than half the shorter side")
    if model_name is not None:
        model_name = normalize_model_name(model_name)
    if len(holes) > 50:
        raise ValueError("At most 50 through holes are supported")
    checked: list[dict] = []
    for i, h in enumerate(holes):
        if set(h) != {"x", "y", "diameter"}:
            raise ValueError(f"Hole {i + 1} requires exactly x, y and diameter")
        for v in h.values():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"Hole {i + 1} contains a non-finite number")
        if h["diameter"] <= 0:
            raise ValueError(f"Hole {i + 1}: diameter must be positive")
        qx = abs(h["x"]) - (length / 2 - radius)
        qy = abs(h["y"]) - (width / 2 - radius)
        signed_distance = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
        if signed_distance + h["diameter"] / 2 >= -1e-4:
            raise ValueError(f"Hole {i + 1} intersects or touches the outer boundary")
        for j, prior in enumerate(checked):
            if (
                math.hypot(h["x"] - prior["x"], h["y"] - prior["y"])
                <= (h["diameter"] + prior["diameter"]) / 2 + 1e-4
            ):
                raise ValueError(f"Holes {j + 1} and {i + 1} overlap or touch")
        checked.append({k: float(v) for k, v in h.items()})
    return {**{k: float(v) for k, v in values.items()}, "holes": checked, "model_name": model_name}


def toolkit_owner() -> dict:
    """Best-effort owner snapshot; only a failed OS lock proves channel contention."""
    try:
        value = read_json(ROOT / "toolkit-owner.lock")
    except (OSError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in ("job_id", "model_id", "operation", "pid", "since")
        if key in value
    }


def _open_toolkit_lock(path: Path) -> BinaryIO:
    """Open via the shared lock-file discipline (BUG-057: OPEN_EXISTING, then
    CREATE_NEW, one shared-open fallback on the first-create race)."""
    return open_lock_file(path)


@contextmanager
def toolkit_lock(
    wait_seconds: float = 0,
    *,
    operation: str = "native_operation",
    job_id: str | None = None,
    model_id: str | None = None,
):
    """Serialize all native calls across MCP clients and detached jobs."""
    lock = ROOT / "toolkit.lock"
    with _open_toolkit_lock(lock) as f:
        # Windows byte-range locking also covers empty files; no pre-lock write.
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise ToolkitBusy(holder=toolkit_owner()) from None
                time.sleep(0.25)
        try:
            write_json(
                ROOT / "toolkit-owner.lock",
                {
                    "job_id": job_id,
                    "model_id": model_id,
                    "operation": operation,
                    "pid": os.getpid(),
                    "since": now(),
                },
            )
            yield
        finally:
            try:
                # Remove before unlock: deleting afterwards could erase the next owner.
                (ROOT / "toolkit-owner.lock").unlink(missing_ok=True)
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


class ToolkitBusy(RuntimeError):
    """A native call is active; startup must wait without launching another Creo."""

    def __init__(self, message: str | None = None, *, holder: dict | None = None):
        holder = holder or {}
        job_id = holder.get("job_id")
        guidance = (
            f"Poll creo_get_job(job_id='{job_id}', detail='compact') until terminal; "
            "inspect unknown_outcome before retrying. "
            if job_id
            else "No occupying job could be determined; the owner may be a session probe, "
            "build or another client. "
        )
        guidance += (
            "This request was not accepted. Retry this request after 1 second only when "
            "the occupying operation has finished; re-read the model revision before writing. "
            "Do not resubmit an already accepted job."
        )
        self.payload = {
            "status": "busy",
            "code": "toolkit_busy",
            "accepted": False,
            "blocking_job_id": job_id,
            "blocking_model_id": holder.get("model_id"),
            "blocking_operation": holder.get("operation"),
            "owner_snapshot": holder or None,
            "owner_determined": bool(holder),
            "retry_after_seconds": 1,
            "retry_guidance": guidance,
            "message": message or "Creo Toolkit is busy with another operation",
        }
        super().__init__(f"{self.payload['message']}. {guidance}")


def license_setting_state(value: str | None) -> str:
    """Describe local paths/server specs without exposing the license value."""
    if not value or not value.strip():
        return "unset"
    states = []
    for item in value.split(";"):
        item = os.path.expandvars(item.strip().strip('"'))
        if not item:
            continue
        if re.fullmatch(r"(?:\d+)?@[^\s;]+", item):
            states.append("server_unverified")
        elif Path(item).is_file():
            states.append("local_file_exists")
        elif Path(item).is_dir():
            states.append("local_directory_exists")
        elif any(c in item for c in "\\/:") or item.lower().endswith((".dat", ".lic")):
            states.append("missing_local_path")
        else:
            states.append("unrecognized_unverified")
    if not states:
        return "unset"
    if len(set(states)) == 1:
        return states[0]
    return "partially_missing" if "missing_local_path" in states else "mixed_unverified"


def resolve_license_environment() -> tuple[str | None, dict]:
    """Fallback only for an unset value or an entirely missing local path list."""
    configured = os.environ.get("PTC_D_LICENSE_FILE")
    env_state = license_setting_state(configured)
    psf_value = None
    psf = Path(config()["creo_root"]) / "Parametric/bin/parametric.psf"
    if psf.is_file():
        for line in psf.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.search(r"PTC_D_LICENSE_FILE[^=]*=(.+)$", line, re.I)
            if match and not line.lstrip().startswith("#"):
                psf_value = match[1].strip()
                break
    psf_state = license_setting_state(psf_value)
    use_psf = env_state in ("unset", "missing_local_path") and psf_state not in (
        "unset",
        "missing_local_path",
    )
    selected = psf_value if use_psf else configured
    selected_state = psf_state if use_psf else env_state
    warnings = []
    if env_state == "missing_local_path":
        warnings.append(
            "Environment license paths do not exist; using parametric.psf"
            if use_psf
            else "Environment license paths do not exist and parametric.psf has no usable fallback; correct the local license setting"
        )
    if selected_state == "partially_missing":
        warnings.append("Some local license paths do not exist; retained other configured entries")
    return selected, {
        "source": "parametric.psf" if use_psf else ("environment" if configured else "unset"),
        "environment_state": env_state,
        "psf_state": psf_state,
        "selected_state": selected_state,
        "fallback_used": use_psf and env_state != "unset",
        "warnings": warnings,
    }


def windows_process_environment() -> dict[str, str]:
    """Supply Windows prerequisites omitted by restricted stdio host environments."""
    import win32api
    import win32profile
    import win32security

    env = os.environ.copy()
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 10)
    try:
        defaults = win32profile.CreateEnvironmentBlock(token, False)
    finally:
        token.Close()
    # Restore only Windows runtime variables, without importing unrelated user
    # credentials, third-party configuration or overriding the MCP host's PATH.
    prerequisites = {
        "ALLUSERSPROFILE",
        "COMPUTERNAME",
        "COMSPEC",
        "COMMONPROGRAMFILES",
        "COMMONPROGRAMFILES(X86)",
        "COMMONPROGRAMW6432",
        "NUMBER_OF_PROCESSORS",
        "OS",
        "PROCESSOR_IDENTIFIER",
        "PROCESSOR_LEVEL",
        "PROCESSOR_REVISION",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "PUBLIC",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "TMP",
        "USERDOMAIN",
        "USERDOMAIN_ROAMINGPROFILE",
        "WINDIR",
    }
    for key, value in defaults.items():
        if key.upper() in prerequisites:
            env.setdefault(key.upper(), value)
    windows_root = env.get("SYSTEMROOT") or env.get("SystemRoot")
    if not windows_root:
        raise ValueError("SYSTEMROOT is required for Creo processes")
    env.setdefault("COMSPEC", str(Path(windows_root) / "System32/cmd.exe"))
    if "TEMP" in env and "TMP" not in os.environ:
        env["TMP"] = env["TEMP"]
    return env


def native_environment() -> dict[str, str]:
    common = Path(config()["creo_root"]) / "Common Files"
    env = windows_process_environment()
    selected = config().get("creo_session_id")
    if selected:
        env["MECHDOG_CREO_SESSION_ID"] = selected
    else:
        env.pop("MECHDOG_CREO_SESSION_ID", None)
    env["PRO_COMM_MSG_EXE"] = str(common / "x86e_win64/obj/pro_comm_msg.exe")
    env["PATH"] = (
        os.pathsep.join(
            str(common / p) for p in ("x86e_win64/lib", "x86e_win64/obj", "libs/dfor/lib")
        )
        + os.pathsep
        + env.get("PATH", "")
    )
    # Child-process environment only; do not return or log the license value.
    license_value, _ = resolve_license_environment()
    if license_value:
        env["PTC_D_LICENSE_FILE"] = license_value
    return env


def check_environment() -> dict:
    c = config()
    root = Path(c["creo_root"])
    common = root / "Common Files"
    sdk = common / "protoolkit"
    files = {
        "creo_executable": root / "Parametric/bin/parametric.exe",
        "toolkit_headers": sdk / "includes/ProToolkit.h",
        "async_library": sdk / "x86e_win64/obj/ptasyncmd.lib",
        "toolkit_library": sdk / "x86e_win64/obj/protkmd_NU.lib",
        "toolkit_dll_library": sdk / "x86e_win64/obj/protk_dllmd_NU.lib",
        "ucore_library": sdk / "x86e_win64/obj/ucore.lib",
        "udata_library": sdk / "x86e_win64/obj/udata.lib",
        "communication_executable": common / "x86e_win64/obj/pro_comm_msg.exe",
        "metric_template": common / "templates/mmns_part_solid_abs.prt",
        "metric_assembly_template": common / "templates/mmns_asm_design_abs.asm",
    }
    checks = {key: {"exists": p.is_file(), "path": str(p)} for key, p in files.items()}
    explicit_env = validate_compiler_env(c.get("vcvars64_env")) is not None
    checks["compiler_setup"] = (
        {"exists": True, "path": "config.json:vcvars64_env", "source": "vcvars64_env"}
        if explicit_env
        else {"exists": Path(c["vcvars64"]).is_file(), "path": c["vcvars64"]}
    )
    license_value, license_diagnostics = resolve_license_environment()
    return {
        "platform": sys.platform,
        "creo_root": str(root),
        "checks": checks,
        "ready_to_build": all(item["exists"] for item in checks.values()),
        "compiler_environment": (
            "unverified_here; build uses explicit vcvars64_env and checks compiler, UCRT and Windows SDK"
            if explicit_env
            else "unverified_here; build runs vcvars64 and checks compiler, UCRT and Windows SDK"
        ),
        "license_setting_present": bool(license_value),
        "license_diagnostics": license_diagnostics,
        "license_usable": "unverified_here; only successful native feature creation proves it",
        "transport": "stdio",
        "supported_features": [
            op for op in REGISTERED_OPERATIONS if op not in UNAVAILABLE_OPERATIONS
        ],
        "complete_creo_coverage": False,
    }


def build_native() -> Path:
    """Caller holds toolkit_lock. Source hash invalidates the local build."""
    c = config()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    exe = build / "creo_worker.exe"
    blend_dll = build / "creo_blend_sync.dll"
    loader_dll = build / "creo_blend_loader.dll"
    # Always refresh before checking the cached binary. The generator only writes
    # changed content, so upgrades and SDK changes cannot retain an obsolete map.
    with (build / "generate_constants.log").open("wb") as log:
        generated = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_constants.py")],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=30,
            creationflags=HIDDEN,
        )
    if generated.returncode:
        raise RuntimeError(
            f"SDK constant generation failed; see {build / 'generate_constants.log'}"
        )
    # Repository-native text dependencies hash CRLF→LF-normalized content so a
    # line-ending-only change never invalidates the build or the registered
    # loader generation (DEV-027). SDK headers, effective settings and every
    # binary integrity digest below keep using raw bytes.
    digest = hashlib.sha256()
    for p in sorted(
        p for p in (ROOT / "native").rglob("*") if p.suffix in (".cpp", ".h", ".hpp", ".inc")
    ):
        digest.update(normalize_lf(p.read_bytes()))
    # Enum values and ABI declarations come from SDK headers. A names-only map
    # can stay identical while these change during an SDK maintenance upgrade.
    includes = Path(c["creo_root"]) / "Common Files/protoolkit/includes"
    abi = hashlib.sha256()
    for p in sorted(includes.rglob("*.h")):
        data = b"\0SDK_HEADER\0" + p.relative_to(includes).as_posix().encode() + p.read_bytes()
        digest.update(data)
        abi.update(data)
    startup_keys = {"auto_start_creo", "creo_startup_timeout_seconds", "creo_startup_psf"}
    settings = json.dumps(
        {key: value for key, value in c.items() if key not in startup_keys}, sort_keys=True
    ).encode()
    digest.update(settings)
    abi.update(settings)
    callback_relatives = (
        "native/blend_sync.cpp",
        "native/callback_identity.h",
        "native/callback_api.h",
        "native/third_party/json.hpp",
    )
    loader_relatives = (
        "native/blend_loader.cpp",
        "native/callback_identity.h",
        "native/callback_api.h",
        "native/third_party/json.hpp",
    )
    # One consistent snapshot backs the current fingerprints and the legacy
    # comparison, so a concurrent file edit cannot split one decision.
    snapshot = read_dependency_snapshot(ROOT, callback_relatives + loader_relatives)
    callback_snapshot = {r: snapshot[r] for r in callback_relatives if r in snapshot}
    loader_snapshot = {r: snapshot[r] for r in loader_relatives if r in snapshot}
    callback_fingerprint = normalized_digest(b"MSVC17_MD_DLL_v2", abi.digest(), callback_snapshot)
    callback_stamp = build / "blend_sync_build.json"
    loader_fingerprint = normalized_digest(b"MSVC17_MD_LOADER_v2", abi.digest(), loader_snapshot)
    loader_stamp = build / "blend_loader_build.json"
    callback_cache = read_json(callback_stamp) if callback_stamp.is_file() else {}
    loader_cache = read_json(loader_stamp) if loader_stamp.is_file() else {}
    # A legacy cache proves line-ending-only equivalence when its raw-byte
    # fingerprint reappears among the original/LF/CRLF recombinations.
    callback_matched, _ = match_cached_fingerprint(
        callback_cache,
        callback_fingerprint,
        legacy_digest_candidates(b"MSVC17_MD_DLL_v1", abi.digest(), callback_snapshot),
    )
    loader_matched, cached_loader_generation = match_cached_fingerprint(
        loader_cache,
        loader_fingerprint,
        legacy_digest_candidates(b"MSVC17_MD_LOADER_v1", abi.digest(), loader_snapshot),
    )
    reuse_callback = (
        blend_dll.is_file()
        and callback_matched
        and callback_cache.get("sha256") == hashlib.sha256(blend_dll.read_bytes()).hexdigest()
    )
    # The physical generation key keeps the registered loader directory stable:
    # it only becomes the normalized fingerprint when a rebuild is unavoidable.
    loader_generation = loader_fingerprint
    reuse_loader = False
    if loader_matched:
        cached_sha = loader_cache.get("sha256")
        if (
            loader_dll.is_file()
            and hashlib.sha256(loader_dll.read_bytes()).hexdigest() == cached_sha
        ):
            loader_generation = cached_loader_generation
            reuse_loader = True
        else:
            pinned_loader = build / "blend_loader" / cached_loader_generation / "loader.dll"
            if (
                pinned_loader.is_file()
                and hashlib.sha256(pinned_loader.read_bytes()).hexdigest() == cached_sha
            ):
                # Recover the disposable build output from the verified immutable
                # image; never relink or modify the registered loader for an
                # unchanged generation.
                shutil.copyfile(pinned_loader, loader_dll)
                loader_generation = cached_loader_generation
                reuse_loader = True
            else:
                print(
                    "loader cache could not be verified against the DLL or its immutable "
                    "copy; rebuilding the loader DLL",
                    file=sys.stderr,
                )
    else:
        print(
            "loader fingerprint changed under the normalized algorithm; rebuilding the loader DLL",
            file=sys.stderr,
        )

    def record_callback():
        """Publish metadata first; cache markers only after full success."""
        callback_sha256 = hashlib.sha256(blend_dll.read_bytes()).hexdigest()
        loader_sha256 = hashlib.sha256(loader_dll.read_bytes()).hexdigest()
        generation = loader_generation
        historical = build / "blend_loader" / generation / "loader.dll"
        if historical.is_file() and (
            hashlib.sha256(historical.read_bytes()).hexdigest() != loader_sha256
        ):
            # A rebuilt DLL meets an immutable copy recorded under the same
            # fingerprint (the cache moved on and back). Keep the historical
            # directory untouched and publish under a distinct physical key.
            generation = f"{generation}-{loader_sha256[:12]}"
            print(
                "loader generation directory already holds a different image; "
                f"publishing under {generation}",
                file=sys.stderr,
            )
        prepare_callback(build, callback_sha256, generation)
        write_json(
            callback_stamp,
            {
                "algorithm": FINGERPRINT_ALGORITHM,
                "fingerprint": callback_fingerprint,
                "sha256": callback_sha256,
            },
        )
        write_json(
            loader_stamp,
            {
                "algorithm": FINGERPRINT_ALGORITHM,
                "fingerprint": loader_fingerprint,
                "generation_key": generation,
                "sha256": loader_sha256,
            },
        )

    fingerprint = digest.hexdigest()
    stamp = build / "source.sha256"
    if (
        exe.exists()
        and reuse_callback
        and reuse_loader
        and stamp.exists()
        and stamp.read_text() == fingerprint
    ):
        # Fully verified combined cache: republish metadata idempotently and
        # keep the identical DLL images in place. A reused legacy generation
        # upgrades its cache markers to the current format on the way out.
        cache_current = (
            callback_cache.get("algorithm") == FINGERPRINT_ALGORITHM
            and callback_cache.get("fingerprint") == callback_fingerprint
            and loader_cache.get("algorithm") == FINGERPRINT_ALGORITHM
            and loader_cache.get("fingerprint") == loader_fingerprint
            and loader_cache.get("generation_key") == loader_generation
        )
        if cache_current:
            prepare_callback(build, callback_cache["sha256"], loader_generation)
        else:
            record_callback()
        return exe
    if not check_environment()["ready_to_build"]:
        raise RuntimeError("Creo SDK, template or MSVC is missing; call creo_check_environment")
    sdk = Path(c["creo_root"]) / "Common Files/protoolkit"
    libs = " ".join(
        f'"{sdk / "x86e_win64/obj" / name}"'
        for name in ("protkmd_NU.lib", "ptasyncmd.lib", "ucore.lib", "udata.lib")
    )
    dll_libs = " ".join(
        f'"{sdk / "x86e_win64/obj" / name}"'
        for name in ("protk_dllmd_NU.lib", "ucore.lib", "udata.lib")
    )
    callback_script = (
        ""
        if reuse_callback
        else f'''
cl /nologo /MD /EHsc /std:c++17 /W3 /DPRO_MACHINE=36 /DPRO_OS=4 /I"{sdk / "includes"}" /c "{ROOT / "native/blend_sync.cpp"}" /Fo"{build / "blend_sync.obj"}"
if errorlevel 1 exit /b 2
link /nologo /DLL /MACHINE:X64 /OUT:"{blend_dll}" "{build / "blend_sync.obj"}" kernel32.lib user32.lib wsock32.lib advapi32.lib mpr.lib winspool.lib netapi32.lib psapi.lib gdi32.lib shell32.lib comdlg32.lib ole32.lib ws2_32.lib
if errorlevel 1 exit /b 3
'''
    )
    loader_script = (
        ""
        if reuse_loader
        else f'''
cl /nologo /MD /EHsc /std:c++17 /W3 /DPRO_MACHINE=36 /DPRO_OS=4 /I"{sdk / "includes"}" /c "{ROOT / "native/blend_loader.cpp"}" /Fo"{build / "blend_loader.obj"}"
if errorlevel 1 exit /b 2
link /nologo /DLL /MACHINE:X64 /OUT:"{loader_dll}" "{build / "blend_loader.obj"}" {dll_libs} kernel32.lib user32.lib wsock32.lib advapi32.lib mpr.lib winspool.lib netapi32.lib psapi.lib gdi32.lib shell32.lib comdlg32.lib ole32.lib ws2_32.lib
if errorlevel 1 exit /b 3
'''
    )
    script = build / "build.cmd"
    script.write_text(
        f'''@echo off
setlocal DisableDelayedExpansion
{compiler_setup_script(c)}
"{sys.executable}" "{ROOT / "tools/compiler_preflight.py"}"
if errorlevel 1 exit /b 4
cl /nologo /MD /EHsc /std:c++17 /bigobj /W3 /DPRO_MACHINE=36 /DPRO_OS=4 /DPRO_USE_VAR_ARGS /I"{sdk / "includes"}" /c "{ROOT / "native/worker.cpp"}" /Fo"{build / "worker.obj"}"
if errorlevel 1 exit /b 2
link /nologo /MACHINE:X64 /SUBSYSTEM:CONSOLE /OUT:"{exe}" "{build / "worker.obj"}" {libs} bcrypt.lib kernel32.lib user32.lib wsock32.lib advapi32.lib mpr.lib winspool.lib netapi32.lib psapi.lib gdi32.lib shell32.lib comdlg32.lib ole32.lib ws2_32.lib
if errorlevel 1 exit /b 3
{callback_script}
{loader_script}
exit /b 0
''',
        encoding="utf-8",
    )
    with (build / "build.log").open("wb") as log:
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(script)],
            cwd=build,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            creationflags=HIDDEN,
        )
    if result.returncode:
        diagnostic = diagnose_build_failure(
            result.returncode, read_build_log_tail(build / "build.log")
        )
        if result.returncode == 4:
            raise RuntimeError(
                f"MSVC/Windows SDK environment preflight failed; inspect {build / 'build.log'} (SDK discovery or registry access may be blocked)\n{diagnostic}"
            )
        raise RuntimeError(
            f"Native build failed ({result.returncode}); see {build / 'build.log'}\n{diagnostic}"
        )
    # Publish callback metadata and DLL cache markers first; the worker cache
    # marker lands only after every earlier step succeeded, so an interrupted
    # publish is re-verified by the next locked build instead of trusted.
    record_callback()
    _write_stamp_text(stamp, fingerprint)
    constants = subprocess.run(
        [str(exe), "constants"],
        env=native_environment(),
        capture_output=True,
        timeout=20,
        creationflags=HIDDEN,
    )
    if constants.returncode == 0:
        (build / "constants.json").write_bytes(constants.stdout)
    return exe


def channel_health() -> dict:
    try:
        return read_json(ROOT / "build/toolkit_health.json")
    except (OSError, ValueError):
        return {}


def record_channel_health(connected: bool, **fields) -> dict:
    value = {"connected": connected, "checked_at": now(), **fields}
    (ROOT / "build").mkdir(exist_ok=True)
    write_json(ROOT / "build/toolkit_health.json", value)
    return value


def note_native_outcome(manifest: dict) -> None:
    result = manifest.get("result", {})
    if (
        manifest["status"] == "unknown_outcome"
        or result.get("connected") is False
        or result.get("toolkit_code") == -38
        or result.get("disconnect_code") not in (None, 0)
    ):
        record_channel_health(
            False,
            job_id=manifest["job_id"],
            model_id=manifest.get("model_id"),
            connection_state="recheck_required",
            message=manifest.get("message"),
        )


def session_status(connect_timeout_seconds: int = 30, *, build_worker: bool = True) -> dict:
    if (
        isinstance(connect_timeout_seconds, bool)
        or not isinstance(connect_timeout_seconds, int)
        or not 1 <= connect_timeout_seconds <= 30
    ):
        raise ValueError("connect_timeout_seconds must be 1–30")
    with toolkit_lock(operation="session_status"):
        exe = build_native() if build_worker else ROOT / "build/creo_worker.exe"
        if not build_worker and not exe.is_file():
            return {
                "connected": False,
                "connection_state": "worker_unavailable",
                "message": "Native worker is unavailable; request creo_startup_status(retry=true)",
            }
        budget = connect_timeout_seconds + min(connect_timeout_seconds, 15) + 5
        try:
            result = subprocess.run(
                [str(exe), "status", str(connect_timeout_seconds)],
                cwd=ROOT / "build",
                env=native_environment(),
                capture_output=True,
                timeout=budget,
                creationflags=HIDDEN,
            )
        except subprocess.TimeoutExpired:
            return record_channel_health(
                False,
                connection_state="probe_timeout",
                toolkit_code=None,
                probe_budget_seconds=budget,
                message="Toolkit connection probe timed out; only this probe helper was stopped. "
                "Inspect Creo dialogs and occupying jobs; preserve unknown jobs/models, then "
                "request creo_startup_status(retry=true). No Creo process was closed.",
            )
        return _record_probe_result(result)


def _record_probe_result(result: subprocess.CompletedProcess) -> dict:
    try:
        value = json.loads(result.stdout.decode("utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("connected"), bool):
            raise ValueError("Invalid status object")
    except (ValueError, UnicodeDecodeError):
        return record_channel_health(
            False,
            connection_state="invalid_probe_result",
            worker_exit_code=result.returncode,
            message="Toolkit worker returned no valid status result; inspect the Creo session and runtime libraries, then request explicit startup retry",
        )
    value["worker_exit_code"] = result.returncode
    if result.returncode != 0 and value.get("connected"):
        value.update(connected=False, connection_state="probe_worker_failed")
    if value.get("disconnect_code") not in (None, 0):
        value.update(connected=False, connection_state="disconnect_failed")
    record_channel_health(
        bool(value.get("connected")), **{k: v for k, v in value.items() if k != "connected"}
    )
    return value


def callback_status() -> dict:
    """Nine-second read-only native probe; no build, DLL loading or GUI launch."""
    build = ROOT / "build"
    artifacts = callback_setup_status(build)
    if artifacts["artifact_status"] != "prepared":
        return {
            **artifacts,
            "reason": artifacts.get("reason", "artifacts_not_prepared"),
            "checked_at": now(),
            "snapshot": True,
        }
    exe = build / "creo_worker.exe"
    if not exe.is_file():
        return unknown_readiness(artifacts, "worker_unavailable")
    try:
        with toolkit_lock(operation="callback_status"):
            result = subprocess.run(
                [str(exe), "callback-status", "2"],
                cwd=build,
                env=native_environment(),
                capture_output=True,
                timeout=9,
                creationflags=HIDDEN,
            )
            session = _record_probe_result(result)
    except ToolkitBusy as exc:
        return unknown_readiness(
            artifacts, "channel_busy", session=exc.payload, probe_budget_seconds=9
        )
    except subprocess.TimeoutExpired:
        record_channel_health(False, connection_state="callback_probe_timeout")
        return unknown_readiness(artifacts, "probe_timeout", probe_budget_seconds=9)
    except (OSError, RuntimeError) as exc:
        return unknown_readiness(
            artifacts, "probe_failed", probe_error=str(exc), probe_budget_seconds=9
        )
    native = session.pop("direct_blend_callback", None)
    if not session.get("connected"):
        return unknown_readiness(
            artifacts,
            session.get("connection_state", "connection_failed"),
            session=session,
            probe_budget_seconds=9,
        )
    if not isinstance(native, dict) or native.get("readiness") not in (
        "ready",
        "not_loaded",
        "version_mismatch",
        "unknown",
    ):
        return unknown_readiness(artifacts, "invalid_probe_result", session=session)
    if callback_setup_status(build) != artifacts:
        return unknown_readiness(artifacts, "deployment_changed_during_probe", session=session)
    return {
        **artifacts,
        **native,
        "session": session,
        "checked_at": now(),
        "snapshot": True,
        "probe_budget_seconds": 9,
    }


def create_job(spec: dict) -> dict:
    with toolkit_lock(operation="submit_plate"):
        JOBS.mkdir(exist_ok=True)
        job_id = uuid.uuid4().hex
        directory = job_path(job_id)
        directory.mkdir()
        output = directory / "output"
        output.mkdir()
        if len(str(output)) >= 230:
            raise ValueError("Project path is too long for this Creo Toolkit build")
        spec = dict(spec)
        spec["model_name"] = spec["model_name"] or f"ai_plate_{job_id[:12]}"
        manifest = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now(),
            "spec": spec,
            "job_directory": str(directory),
            "output_directory": str(output),
            "message": "Call creo_get_job until succeeded, failed or unknown_outcome. Do not repeat create_plate to poll.",
        }
        write_json(directory / "job.json", manifest)
        try:
            with (directory / "runner.log").open("ab") as log:
                subprocess.Popen(
                    [sys.executable, str(ROOT / "bridge.py"), "run-job", job_id],
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=HIDDEN,
                    close_fds=True,
                )
        except Exception as exc:
            manifest.update(status="failed", message=str(exc), finished_at=now())
            write_json(directory / "job.json", manifest)
            raise
        return manifest


def run_job(job_id: str) -> None:
    directory = job_path(job_id)
    manifest = read_json(directory / "job.json")
    manifest.update(runner_identity=process_identity(os.getpid()), stage="waiting_for_channel")
    write_json(directory / "job.json", manifest)
    if manifest.get("kind") == "reconciliation":
        from creo_mechdog.reconciliation import run

        run(job_id, manifest)
        return
    if manifest.get("kind") == "adoption_file":
        from creo_mechdog.file_adoption import run

        run(job_id, manifest)
        return
    if manifest.get("kind") == "adoption":
        from creo_mechdog.adoption import run

        run(job_id, manifest)
        return
    if manifest.get("kind") == "open_file":
        from creo_mechdog.open_file import run

        run(job_id, manifest)
        return
    if manifest.get("kind") == "session_erase":
        from creo_mechdog.session_erase import run

        run(job_id, manifest)
        return
    if manifest.get("kind") == "generic":
        from generic_bridge import run_generic_job

        run_generic_job(job_id, manifest)
        return
    worker_started = False
    try:
        with toolkit_lock(wait_seconds=120, operation="create_plate", job_id=job_id):
            manifest.update(
                status="running", stage="building_worker", started_at=now(), runner_pid=os.getpid()
            )
            write_json(directory / "job.json", manifest)
            exe = build_native()
            spec = validate_spec(
                **{
                    k: manifest["spec"][k]
                    for k in ("length", "width", "thickness", "radius", "holes", "model_name")
                }
            )
            common = Path(config()["creo_root"]) / "Common Files"
            lines = [
                spec["model_name"],
                manifest["output_directory"],
                str(common / "templates/mmns_part_solid_abs.prt"),
                " ".join(
                    format(spec[k], ".17g") for k in ("length", "width", "thickness", "radius")
                ),
                str(len(spec["holes"])),
            ]
            lines.extend(
                " ".join(format(h[k], ".17g") for k in ("x", "y", "diameter"))
                for h in spec["holes"]
            )
            (directory / "native_spec.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest.update(stage="creating_native_features")
            write_json(directory / "job.json", manifest)
            with (directory / "worker.log").open("wb") as log:
                worker_started = True
                proc = subprocess.run(
                    [str(exe), "create", str(directory)],
                    cwd=directory,
                    env=native_environment(),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=config()["native_timeout_seconds"],
                    creationflags=HIDDEN,
                )
            result_path = directory / "native_result.json"
            if not result_path.exists():
                manifest.update(
                    status="unknown_outcome",
                    message=f"Worker exited {proc.returncode} without a result; inspect Creo and native.log before retrying",
                )
            else:
                result = read_json(result_path)
                manifest["result"] = result
                if (
                    result.get("disconnect_code") not in (None, 0)
                    or result.get("delivery_complete") is False
                ):
                    manifest.update(
                        status="unknown_outcome",
                        message="Native finalization was not confirmed; preserve saved files and inspect the checkpoint",
                    )
                elif (
                    proc.returncode == 0
                    and result.get("success")
                    and result.get("saved_file_reloaded_and_verified")
                ):
                    part = Path(result["part_file"])
                    if (
                        part.parent.resolve() != (directory / "output").resolve()
                        or not part.is_file()
                    ):
                        raise RuntimeError(
                            "Native result references a missing or unexpected part file"
                        )
                    result["sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
                    result["preview_file"] = (
                        str(directory / "output/preview.jpg")
                        if result["preview_code"] == 0
                        else None
                    )
                    manifest.update(
                        status="succeeded",
                        stage="verified",
                        message="Native PRT saved, reloaded and verified; sketch/extrude/round/hole features are editable",
                    )
                else:
                    manifest.update(
                        status="failed",
                        message=f"Toolkit code {result['toolkit_code']}; inspect native.log. Partial new model may remain in Creo. Do not blindly retry.",
                    )
    except subprocess.TimeoutExpired:
        manifest.update(
            status="unknown_outcome" if worker_started else "failed",
            message="Native helper timed out and was stopped; inspect native checkpoint and Creo before retrying."
            if worker_started
            else "Native build exceeded its subprocess budget; inspect build logs. No native modeling worker started.",
        )
    except Exception as exc:
        manifest.update(status="unknown_outcome" if worker_started else "failed", message=str(exc))
    note_native_outcome(manifest)
    manifest["finished_at"] = now()
    write_json(directory / "job.json", manifest)


def get_job(job_id: str, detail: str = "full") -> dict:
    if detail not in ("compact", "full"):
        raise ValueError("detail must be compact or full")
    directory = job_path(job_id)
    if not (directory / "job.json").exists():
        raise ValueError("Unknown job_id")
    manifest = read_json(directory / "job.json")
    if manifest.get("kind") == "reconciliation":
        from creo_mechdog.reconciliation import resume_committed

        manifest = resume_committed(job_id) or manifest
    elif manifest.get("kind") == "adoption":
        from creo_mechdog.adoption import resume_committed

        manifest = resume_committed(job_id) or manifest
    elif manifest.get("kind") == "adoption_file":
        from creo_mechdog.file_adoption import resume_committed

        manifest = resume_committed(job_id) or manifest
    native_log = directory / "native.log"
    if native_log.exists():
        tail = native_log.read_bytes()[-8000:].decode("utf-8", errors="replace")
        stages = re.findall(r"PHASE=([^\r\n]+)", tail)
        if stages and manifest["status"] == "running":
            manifest["stage"] = stages[-1]
        if manifest["status"] in ("failed", "unknown_outcome"):
            manifest["native_log_tail"] = tail[-4000:]
    if manifest["status"] in ("queued", "running"):
        age = (
            datetime.now(timezone.utc) - datetime.fromisoformat(manifest["created_at"])
        ).total_seconds()
        if manifest.get("kind") in ("adoption_file", "adoption_file_inspect"):
            from creo_mechdog.file_adoption import lifetime_seconds

            lifetime = lifetime_seconds(manifest["item_count"])
        else:
            timeout = (
                config().get("generic_timeout_seconds", 600)
                if manifest.get("kind") in ("generic", "reconciliation", "adoption", "open_file")
                else config()["native_timeout_seconds"]
            )
            lifetime = 120 + 180 + timeout + 30
        if age > lifetime:
            manifest.update(
                status="unknown_outcome",
                message="Job exceeded its expected lifetime; inspect runner.log and Creo before retrying",
            )
    if manifest["status"] == "unknown_outcome" or manifest.get("recovery_required"):
        model = None
        if manifest.get("model_id"):
            from generic_bridge import model_info

            try:
                model = model_info(manifest["model_id"])
            except (OSError, ValueError) as exc:
                manifest["model_evidence_error"] = (
                    f"Model registry could not be read ({type(exc).__name__}); preserve it for operator reconciliation"
                )
        manifest["recovery"] = job_evidence(directory, manifest, model)
        manifest.setdefault(
            "recovery_required",
            ("Outcome is unconfirmed; preserve reservation and inspect recovery evidence"),
        )
    if detail == "compact":
        manifest = compact_job(manifest)
    return manifest


def compact_job(manifest: dict) -> dict:
    """Bound polling payloads without losing the outcome or recovery information."""
    keys = (
        "job_id",
        "kind",
        "model_id",
        "status",
        "stage",
        "revision",
        "readonly",
        "created_at",
        "started_at",
        "finished_at",
        "message",
        "reason",
        "reason_details",
        "failure_read_budget_exceeded",
        "commit_read_budget_exceeded",
        "failure_phase",
        "recovery_pending_released",
        "recovery_pending_cleanup_error",
        "channel_finalization_error",
        "construction",
        "busy",
        "recovery_required",
        "recovery",
        "runner_identity",
        "recovery_id",
        "commit_pending",
        "action",
        "idempotency_key",
        "adoption_action",
        "parent_job_id",
        "batch_id",
        "items",
        "item_count",
        "item_counts",
        "all_adopted",
        "partial_result",
        "evidence_token",
        "expires_in_seconds",
        "available",
        "model_evidence_error",
        "component_changes",
    )
    summary = {key: manifest[key] for key in keys if key in manifest}
    summary["detail"] = "compact"
    summary["operation_count"] = len(manifest.get("operations", []))
    result = manifest.get("result")
    if result:
        result_keys = (
            "success",
            "seed_load_evidence",
            "loft_seed_feature",
            "creo_release_numeric",
            "creo_release_query_code",
            "code",
            "toolkit_code",
            "message",
            "part_file",
            "sha256",
            "saved_file_reloaded_and_verified",
            "rollback_succeeded",
            "model_unchanged",
            "rollback_message",
            "rollback_code",
            "preview_file",
            "connected",
            "volume_mm3",
            "expected_volume_mm3",
            "extrude_count",
            "round_count",
            "hole_count",
            "failed_stage",
            "failed_toolkit_call",
            "failed_operation_index",
            "inspection_source",
            "adoption",
            "adopted",
            "open_file",
            "session_erase",
            "loaded",
            "session_fingerprint",
        )
        native = {key: result[key] for key in result_keys if key in result}
        from creo_mechdog.model_queries import inspection_summary

        # Legacy results inline a full inspection; split results carry only a
        # summary plus a controlled reference (BUG-076). Both stay small here.
        native["inspection"] = inspection_summary(result.get("inspection"))
        if "inspection_summary" in result:
            native["inspection_summary"] = result["inspection_summary"]
        if "inspection_ref" in result:
            native["inspection_ref"] = result["inspection_ref"]
        if "aliases_ref" in result:
            # Split job results carry a controlled aliases reference (BUG-077).
            native["aliases_ref"] = result["aliases_ref"]
            native["alias_count"] = result.get("alias_count")
        live = result.get("live")
        if isinstance(live, dict):
            visible = dict(live)
            inline = visible.pop("inspection", None)
            if inline is not None:
                visible.setdefault("inspection_summary", inspection_summary(inline))
            native["live"] = visible
        native["operations"] = [
            {
                key: op[key]
                for key in (
                    "op",
                    "index",
                    "label",
                    "succeeded",
                    "execution_status",
                    "effect_status",
                    "unchanged",
                    "native_geometry_verified",
                    "size",
                    "file",
                    "feature_id",
                    "preserved_feature_id",
                    "reordered",
                    "sheet",
                    "parameters",
                    "metadata",
                    "material_removed_mm3",
                    "surface_id",
                    "origin",
                    "normal",
                    "u_axis",
                    "v_axis",
                    "datum_axes",
                    "axes_query_code",
                    "length_unit",
                    "elapsed_seconds",
                    "message",
                )
                if key in op
            }
            for op in result.get("operations", [])
        ]
        summary["result"] = native
    if "native_log_tail" in manifest:
        summary["native_log_tail"] = manifest["native_log_tail"][-2000:]
    summary["full_result_available"] = bool(result)
    return summary


def list_jobs(limit: int = 10, detail: str = "compact") -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    if detail not in ("compact", "full"):
        raise ValueError("detail must be compact or full")
    paths = sorted(JOBS.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [get_job(p.parent.name, detail=detail) for p in paths[:limit]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "status", "environment", "run-job"])
    parser.add_argument("job_id", nargs="?")
    args = parser.parse_args()
    if args.action == "run-job":
        run_job(args.job_id)
    elif args.action == "build":
        with toolkit_lock(operation="build_native"):
            print(build_native())
    else:
        print(
            json.dumps(
                session_status() if args.action == "status" else check_environment(),
                ensure_ascii=False,
                indent=2,
            )
        )
