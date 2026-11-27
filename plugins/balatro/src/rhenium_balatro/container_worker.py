"""One bounded, source-reviewed operation in the prepared Linux image."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .container_builder import native_spec
from .container_host import native_context
from .linux_bridge import BINDING_NAME
from .linux_evaluator import BalatroLinuxEvaluator
from .linux_managed_v2 import RUNTIME_KEY as NATIVE_KEY
from .linux_managed_v2 import BalatroLinuxRuntimeBuilderV2
from .linux_operator import main as operator_main
from .linux_runtime import sha
from .native_assets import json_write_new


def operator(operation: str, context: BenchmarkContext, extra: list[str]) -> None:
    sys.argv = ["linux_operator", operation, "--pack", str(context.pack_root),
                "--state", str(context.state_dir), "--cache", str(context.cache_dir), *extra]
    operator_main()


def execute(request: dict[str, Any]) -> dict[str, Any]:
    context = BenchmarkContext.model_validate(request["context"])
    root = Path(request["root"])
    local = native_context(context, root)
    operation = request["operation"]
    if operation == "prepare":
        artifact = BalatroLinuxRuntimeBuilderV2(context).prepare(
            native_spec(context), Path(request["source"]), root / "native-v2",
            progress=lambda *_: None,
        )
        return {"artifact": artifact.model_dump(mode="json")}
    artifact = RuntimeArtifact.model_validate(request["native"])
    if operation == "smoke":
        record = root / "prepared-native.json"
        json_write_new(record, artifact.model_dump(mode="json"))
        operator("smoke", local, ["--artifact", str(record)])
        binding = json.loads((local.state_dir / BINDING_NAME).read_text())
        return {"binding": binding, "smoke_sha256": sha(Path(binding["smoke_marker"]))}
    if operation == "review":
        operator("review", local, ["--task", request["task"],
                                  "--submission", request["submission"],
                                  "--reviewed-sha", request["reviewed_sha"]])
        return {"review_recorded": True}
    if operation == "evaluate":
        from .catalog import load_catalog

        task = next(t for t in load_catalog(context.pack_root, "catalog.json").tasks
                    if t.id == request["task"])
        # Reuse every native preflight, review, assertion and cleanup check. Only the
        # constructor's selected runtime/context differ for this outer host profile.
        evaluator = BalatroLinuxEvaluator.with_prepared_context(local, NATIVE_KEY)
        return evaluator.evaluate(Path(request["submission"]), task, profile="full",
                                  runtimes={NATIVE_KEY: artifact})
    raise ValueError("Unsupported container operation")


def main() -> None:
    line = sys.stdin.buffer.readline(512 * 1024 + 1)
    if len(line) > 512 * 1024 or not line.endswith(b"\n"):
        raise ValueError("Invalid request framing")
    request = json.loads(line)
    response = Path(request["response"])
    display: subprocess.Popen[bytes] | None = None
    try:
        if request["operation"] != "prepare":
            frames = response.parent / "display"
            frames.mkdir(mode=0o700)
            with (response.parent / "display.log").open("xb") as log:
                display = subprocess.Popen(["Xvfb", ":0", "-screen", "0", "1024x768x24",
                                            "-nolisten", "tcp", "-ac", "-noreset",
                                            "-fbdir", str(frames)], stdout=log, stderr=log)
            deadline = time.monotonic() + 10
            while not Path("/tmp/.X11-unix/X0").is_socket():
                if display.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Owned rendered display did not start")
                time.sleep(0.05)
        result = execute(request)
        value = {"nonce": request["nonce"], "image": request["image"], "result": result,
                 "pid_namespace": os.readlink("/proc/self/ns/pid")}
    except Exception as error:
        value = {"nonce": request["nonce"], "image": request["image"],
                 "error": type(error).__name__, "private_detail": str(error)}
    finally:
        if display is not None:
            display.terminate()
            try:
                display.wait(timeout=5)
            except subprocess.TimeoutExpired:
                display.kill()
                display.wait(timeout=5)
    json_write_new(response, value)


if __name__ == "__main__":
    main()
