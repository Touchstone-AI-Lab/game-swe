"""Serial owned Linux controller process; no account environment reaches it."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .files import reject_links, validate_state
from .linux_process import arm_parent_death
from .native_assets import json_write_new
from .protocol import MAX_RESPONSE_BYTES, PROTOCOL, decode_response

BINDING_NAME = "linux-binding-v1.json"


@contextmanager
def serial_lock(state: Path) -> Iterator[None]:
    import fcntl

    state.mkdir(parents=True, exist_ok=True)
    path = state / "linux-serial.lock"
    reject_links(path)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def child_environment(work: Path) -> dict[str, str]:
    import rhenium.core.plugin

    for name in ("home", "tmp"):
        (work / name).mkdir(mode=0o700)
    core = Path(rhenium.core.plugin.__file__).resolve().parents[2]
    plugin = Path(__file__).resolve().parents[1]
    env = {
        "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(work / "home"),
        "TMPDIR": str(work / "tmp"),
        "PYTHONPATH": str(core) + ":" + str(plugin),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    interop = Path(os.environ.get("WSL_INTEROP", ""))
    if interop.is_absolute() and interop.parent == Path("/run/WSL") and interop.is_socket():
        env["WSL_INTEROP"] = str(interop)
    return env


def invoke(
    context: BenchmarkContext,
    artifact: RuntimeArtifact,
    binding: dict[str, Any],
    operation: str,
    *,
    task: str = "",
    candidate: Path | None = None,
    submission_sha256: str = "",
    timeout: float = 1800,
) -> tuple[dict[str, Any], Path]:
    validate_state(context.pack_root, context.state_dir)
    if not 0 < timeout <= 1800:
        raise ValueError("Controller timeout exceeds the declared bound")
    identifier, nonce = uuid.uuid4().hex, uuid.uuid4().hex
    work = context.state_dir / "linux/operations" / identifier
    work.mkdir(parents=True, mode=0o700)
    request = {
        "protocol": PROTOCOL,
        "request_id": identifier,
        "nonce": nonce,
        "submission_sha256": submission_sha256,
        "operation": operation,
        "task": task,
        "candidate": str(candidate) if candidate is not None else None,
        "binding": binding,
        "artifact": artifact.model_dump(mode="json"),
        "pack": str(context.pack_root),
        "state": str(context.state_dir),
        "work": str(work),
        "cache": str(context.cache_dir),
    }
    json_write_new(work / "request.json", request)
    command = [sys.executable, "-m", "rhenium_balatro.linux_worker"]
    with (work / "controller.log").open("xb") as log:
        parent = os.getpid()
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
            cwd=work,
            env=child_environment(work),
            start_new_session=True,
            preexec_fn=lambda: arm_parent_death(parent),
        )
        try:
            process.communicate((json.dumps(request) + "\n").encode(), timeout=timeout)
        except BaseException:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            raise
    if process.returncode != 0:
        raise RuntimeError("Owned Linux controller did not exit normally")
    response = work / "response.json"
    reject_links(response)
    with response.open("rb") as stream:
        data = stream.read(MAX_RESPONSE_BYTES + 1)
    return decode_response(data, identifier, nonce, submission_sha256), work
