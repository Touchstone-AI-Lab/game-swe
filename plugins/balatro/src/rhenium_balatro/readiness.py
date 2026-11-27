"""Live read-only runtime probe. No game launch and no state/cache creation."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .bridge import BINDING_NAME, load_binding
from .native_assets import verified_assets
from .protocol import PROTOCOL, decode_response
from .winjob import hidden_creation_flags


def runtime_status(pack: Path, state: Path) -> dict[str, Any]:
    status: dict[str, Any] = {"available": False, "status": "action_required",
        "reason": "native_binding_and_matching_smoke_required", "prepared": False,
        "engineValidated": False, "untrustedHostSupported": False, "gameStarted": False}
    if os.name != "nt":
        return {**status, "reason": "native_windows_required"}
    if not (state / BINDING_NAME).is_file():
        return status
    status["prepared"] = True
    try:
        if (state / "native-halt.json").exists():
            return {**status, "reason": "native_execution_halted"}
        binding = load_binding(state)
        verified_assets(pack, binding["assets_sha256"])
        system = Path(os.environ.get("SYSTEMROOT", ""))
        if not system.is_absolute() or not (system / "System32/kernel32.dll").is_file():
            raise ValueError("invalid SystemRoot")
        system = system.resolve()
        env = {"SystemRoot": str(system), "WINDIR": str(system),
               "PATH": os.pathsep.join((str(system / "System32"), str(system))),
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        request_id, nonce = uuid.uuid4().hex, uuid.uuid4().hex
        request = {"protocol": PROTOCOL, "request_id": request_id, "nonce": nonce,
                   "submission_sha256": "", "operation": "probe", "binding": binding,
                   "pack": str(pack.resolve()), "native_state": str((state / "native").resolve())}
        output = subprocess.run(
            [binding["python"], "-I", "-B", str(Path(__file__).with_name("sidecar.py")), "--probe"],
            input=json.dumps(request).encode() + b"\n", capture_output=True, env=env,
            cwd=state, timeout=120, creationflags=hidden_creation_flags(), check=False)
        if output.returncode != 0 or output.stderr:
            raise ValueError("read-only probe failed")
        result = decode_response(output.stdout, request_id, nonce, "")
        if (result.get("dependencies_verified") is not True
                or result.get("protected_unchanged") is not True
                or result.get("matching_smoke") is not True):
            raise ValueError("runtime not ready")
        return {**status, "available": True, "status": "ready", "reason": "verified_local_honest_runtime",
                "engineValidated": True, "checks": {"fixedDependencies": True,
                "protectedData": True, "matchingSmoke": True}, "securityMode": "honest"}
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired):
        return {**status, "reason": "runtime_verification_failed"}
