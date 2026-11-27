"""One bounded Linux operation, using the same frozen acceptance implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec

from .linux_control import execute, require_smoke
from .linux_managed import RUNTIME_ID, BalatroLinuxRuntimeBuilder
from .linux_managed_v2 import RUNTIME_ID as V2
from .linux_managed_v2 import BalatroLinuxRuntimeBuilderV2
from .linux_session import LinuxSessionHost
from .native_assets import json_write_new
from .protocol import PROTOCOL


def make_host(
    context: BenchmarkContext, artifact: RuntimeArtifact, binding: dict[str, Any]
) -> LinuxSessionHost:
    values = json.loads((context.pack_root / "runtimes.json").read_text())["runtimes"]
    runtime_id = artifact.runtime_key.removeprefix("balatro/")
    if runtime_id not in {RUNTIME_ID, V2}:
        raise ValueError("Unsupported managed runtime")
    spec = RuntimeSpec.model_validate(next(value for value in values if value["id"] == runtime_id))
    guard = binding.get("windows_powershell")
    return LinuxSessionHost(
        builder=(BalatroLinuxRuntimeBuilderV2 if runtime_id == V2 else BalatroLinuxRuntimeBuilder)(context),
        spec=spec,
        artifact=artifact,
        pack=context.pack_root,
        assets_sha256=binding["assets_sha256"],
        run_root=context.state_dir / "linux/engine-v1",
        windows_powershell=Path(guard) if guard else None,
        review_state=context.state_dir,
    )


def verify_binding(host: LinuxSessionHost, binding: dict[str, Any]) -> None:
    if (
        binding.get("schema_version") != 1
        or binding.get("scope") != "source-reviewed-native-linux"
        or binding.get("environment") != host.environment
        or binding.get("harness") != host.harness
        or binding.get("artifact_identity") != host.artifact.identity
    ):
        raise ValueError("Linux operator binding is absent or stale")
    marker = Path(binding["smoke_marker"])
    if not marker.resolve().is_relative_to((host.review_state / "linux/operations").resolve()):
        raise ValueError("Smoke marker escaped operator state")
    require_smoke(host, marker)


def main() -> None:
    line = sys.stdin.buffer.readline(512 * 1024 + 1)
    if len(line) > 512 * 1024 or not line.endswith(b"\n"):
        raise ValueError("Invalid request framing")
    request = json.loads(line)
    if request["protocol"] != PROTOCOL:
        raise ValueError("Invalid controller protocol")
    work, state, pack = (Path(request[key]) for key in ("work", "state", "pack"))
    if work != state / "linux/operations" / request["request_id"]:
        raise ValueError("Operation directory mismatch")
    context = BenchmarkContext(
        project_root=pack.parent, pack_root=pack, state_dir=state, cache_dir=Path(request["cache"])
    )
    result: dict[str, Any]
    try:
        host = make_host(context, RuntimeArtifact.model_validate(request["artifact"]), request["binding"])
        if request["operation"] != "smoke":
            verify_binding(host, request["binding"])
        if request["operation"] == "probe":
            result = {"verified": True, "environment": host.environment, "harness": host.harness}
        else:
            candidate = Path(request["candidate"]) if request["candidate"] else None
            result = execute(
                host,
                operation=request["operation"],
                output=work / "engine-result.json",
                task_key=request["task"],
                candidate=candidate,
                smoke=Path(request["binding"]["smoke_marker"]) if request["operation"] != "smoke" else None,
            )
    except Exception as error:
        result = {"bridge_error": type(error).__name__, "private_detail": str(error)}
    json_write_new(
        work / "response.json",
        {
            "protocol": PROTOCOL,
            "request_id": request["request_id"],
            "nonce": request["nonce"],
            "submission_sha256": request["submission_sha256"],
            "result": result,
        },
    )


if __name__ == "__main__":
    main()
