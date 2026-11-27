"""Serial, bounded invocation of the reviewed external controller."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .files import read_json, reject_links, validate_state
from .native_assets import adapter_identity, file_sha, json_write_new
from .protocol import MAX_RESPONSE_BYTES, PROTOCOL, decode_response
from .winjob import OwnedJob, hidden_creation_flags

BINDING_NAME = "native-binding-v2.json"


def load_binding(state: Path) -> dict[str, Any]:
    value = read_json(state, BINDING_NAME)
    if (value.get("schema_version") != 2 or value.get("scope") != "reviewed-local-honest-v2"
            or value.get("adapter_sha256") != adapter_identity()):
        raise ValueError("native binding is absent or stale")
    python = Path(value["python"])
    if not python.is_absolute() or file_sha(python) != value["python_sha256"]:
        raise ValueError("fixed Python executable changed")
    if Path(value["smoke_marker"]).parent.resolve() != (state / "native").resolve():
        raise ValueError("smoke evidence escaped platform state")
    return value


def _lock_file(descriptor: int, *, unlock: bool = False) -> None:
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK, 1)
    else:
        raise OSError("native Windows required")


@contextmanager
def serial_lock(state: Path) -> Iterator[None]:
    if os.name != "nt":
        raise OSError("native Windows required")
    state.mkdir(parents=True, exist_ok=True)
    path = state / "native-serial.lock"
    reject_links(path)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        _lock_file(stream.fileno())
        try:
            yield
        finally:
            stream.seek(0)
            _lock_file(stream.fileno(), unlock=True)


def child_environment(work: Path) -> dict[str, str]:
    system = Path(os.environ.get("SYSTEMROOT", ""))
    if not system.is_absolute() or not (system / "System32/kernel32.dll").is_file():
        raise ValueError("invalid Windows SystemRoot")
    system = system.resolve()
    for name in ("tmp", "profile", "appdata", "localappdata"):
        (work / name).mkdir()
    return {"SystemRoot": str(system), "WINDIR": str(system), "SystemDrive": system.drive,
            "PATH": os.pathsep.join((str(system / "System32"), str(system))),
            "TEMP": str(work / "tmp"), "TMP": str(work / "tmp"), "USERPROFILE": str(work / "profile"),
            "APPDATA": str(work / "appdata"), "LOCALAPPDATA": str(work / "localappdata"),
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}


def invoke(
    pack: Path, state: Path, binding: dict[str, Any], operation: str, *,
    task: str = "", candidate: Path | None = None, submission_hash: str = "",
    timeout: float = 1800,
) -> tuple[dict[str, Any], Path]:
    validate_state(pack, state)
    if operation != "audit" and (state / "native-halt.json").exists():
        raise RuntimeError("native execution halted; investigate prior incomplete cleanup")
    work = state / "operations" / uuid.uuid4().hex
    reject_links(work)
    work.mkdir(parents=True)
    native = state / "native"
    native.mkdir(exist_ok=True)
    request_id, nonce = uuid.uuid4().hex, uuid.uuid4().hex
    request = {"protocol": PROTOCOL, "request_id": request_id, "nonce": nonce,
               "submission_sha256": submission_hash, "binding": binding, "operation": operation,
               "pack": str(pack.resolve()), "native_state": str(native.resolve()),
               "work": str(work.resolve()),
               "task": task, "candidate": str(candidate.resolve()) if candidate else None}
    json_write_new(work / "request.json", request)
    job = OwnedJob()
    process: subprocess.Popen[bytes] | None = None
    forced, cancelled, active, assigned = False, False, 0, False
    started = time.monotonic()
    try:
        with (work / "sidecar.log").open("xb") as log:
            process = subprocess.Popen(
                [binding["python"], "-I", "-B", str(Path(__file__).with_name("sidecar.py"))],
                cwd=work, env=child_environment(work), stdin=subprocess.PIPE, stdout=log, stderr=log,
                creationflags=hidden_creation_flags(),
            )
            owned_process: Any = process
            job.assign(int(owned_process._handle))  # Windows Popen-owned handle.
            assigned = True
            assert process.stdin is not None
            process.stdin.write(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
            process.stdin.close()
            deadline = started + timeout
            cancellation_deadline: float | None = None
            while process.poll() is None:
                if time.monotonic() >= deadline or (work / "sidecar.log").stat().st_size > 1024 * 1024:
                    if cancellation_deadline is None:
                        (work / "cancel").write_bytes(b"cancel\n")
                        cancelled = True
                        cancellation_deadline = time.monotonic() + 80
                    elif time.monotonic() >= cancellation_deadline:
                        forced = True
                        job.terminate()
                        process.wait(timeout=10)
                        break
                time.sleep(.1)
            drain = time.monotonic() + 3
            while job.active() and time.monotonic() < drain:
                time.sleep(.05)
            active = job.active()
            if active:
                forced = True
                job.terminate()
            if cancelled or forced or process.returncode != 0:
                raise RuntimeError("sidecar cancelled, abnormal, or left owned processes")
        response = work / "response.json"
        if response.stat().st_size > MAX_RESPONSE_BYTES:
            raise ValueError("oversize sidecar response")
        result = decode_response(response.read_bytes(), request_id, nonce, submission_hash)
        return result, work
    finally:
        if process is not None and process.poll() is None:
            forced = True
            if assigned:
                job.terminate()
            else:
                process.terminate()  # Child cannot launch descendants before the stdin handshake.
            process.wait(timeout=10)
        residual = job.active()
        job.close()
        audit = {"protocol": PROTOCOL, "request_id": request_id, "assigned_to_owned_job": assigned,
                 "sidecar_pid": process.pid if process else None,
                 "exit_code": process.returncode if process else None,
                 "cancelled": cancelled, "forced": forced, "active_before_job_close": residual,
                 "elapsed_seconds": time.monotonic() - started,
                 "directory_bytes": sum(p.stat().st_size for p in work.rglob("*") if p.is_file())}
        json_write_new(work / "supervisor.json", audit)
        if forced or residual:
            path = state / "native-halt.json"
            if not path.exists():
                json_write_new(path, {"reason": "owned_process_cleanup_requires_review",
                                      "operation": work.name, "supervisor": audit})
