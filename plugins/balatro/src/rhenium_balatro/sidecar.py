"""Fixed Python 3.13 tool boundary. Reads one request after parent job assignment.

Only stdlib and the hash-checked existing PoC controller are imported. No Rhenium,
Pydantic, engine dependency installation or source modification is performed.
"""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rhenium_balatro.files import read_json
from rhenium_balatro.native_assets import (
    adapter_identity,
    json_write_new,
    verified_assets,
    verify_controller,
)
from rhenium_balatro.protocol import PROTOCOL
from rhenium_balatro.review import candidate_identity, candidate_reviewed


def clone(function: Any, replacements: dict[str, Any]) -> Any:
    copied = types.FunctionType(function.__code__, {**function.__globals__, **replacements},
                                function.__name__, function.__defaults__, function.__closure__)
    copied.__kwdefaults__ = function.__kwdefaults__
    return copied


def install_adapter(native: Path, cancel: Path, marker: Path, code_hash: str) -> tuple[Any, list[Any]]:
    runtime: Any = importlib.import_module("poc.runtime")
    rpc: Any = importlib.import_module("poc.rpc")
    smoke: Any = importlib.import_module("poc.smoke")
    evaluate: Any = importlib.import_module("poc.evaluate")
    initializer = clone(runtime.Runtime.__init__, {"ROOT": native})
    runtimes: list[Any] = []

    runtime_base: Any = runtime.Runtime
    client_base: Any = rpc.Client

    class PlatformRuntime(runtime_base):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Reuse the exact pinned initializer with its sole filesystem root changed.
            initializer(self, *args, **kwargs)
            runtimes.append(self)

    class CancellableClient(client_base):
        def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
            if cancel.exists() and method != "poc.quit":
                raise RuntimeError("maintenance operation cancelled")
            return super().call(method, *args, **kwargs)

    verifier = clone(smoke.require_smoke, {"ROOT": native})

    def require_smoke(environment: str) -> dict[str, Any]:
        stamp = read_json(marker.parent, marker.name)
        if stamp.get("adapter_sha256") != code_hash:
            raise ValueError("platform smoke adapter mismatch")
        return verifier(environment, marker)

    runtime.Runtime = PlatformRuntime
    runtime.Client = CancellableClient
    evaluate.Runtime = PlatformRuntime
    smoke.require_smoke = require_smoke
    return smoke, runtimes


def load_task(pack: Path, key: str, assets: dict[str, Any]) -> Any:
    root = pack / "private/native-v1"
    item = assets["tasks"][key]
    namespace = types.ModuleType("tasks")
    namespace.__path__ = [str(root / "fixtures/tasks")]
    if any(name == "tasks" or name.startswith("tasks.") for name in sys.modules):
        raise ValueError("task namespace already populated")
    sys.modules["tasks"] = namespace
    module = importlib.import_module(item["module"])
    if list(module.REQUIRED) != item["required"]:
        raise ValueError("required cases changed")
    for name, loaded in sys.modules.items():
        filename = getattr(loaded, "__file__", None)
        if (name.startswith("tasks.") and isinstance(filename, str)
                and not Path(filename).resolve().is_relative_to(root.resolve())):
            raise ValueError("task import escaped pack")
    return types.SimpleNamespace(key=key, module=item["module"], session_api=item["session_api"],
        mods={name: root / path for name, path in item["mods"].items()},
        files=lambda: dict(item["task_files"]), scenario=lambda: module)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("protocol") != PROTOCOL or sys.version_info[:2] != (3, 13):
        raise ValueError("fixed controller protocol/Python mismatch")
    binding = request["binding"]
    pack = Path(request["pack"])
    root = Path(binding["controller_root"])
    assets = verified_assets(pack, binding["assets_sha256"])
    verify_controller(root, assets)
    if adapter_identity() != binding["adapter_sha256"]:
        raise ValueError("adapter changed")
    sys.path.insert(0, str(root))
    runtime = importlib.import_module("poc.runtime")
    integrity = importlib.import_module("poc.integrity")
    runtime.protected_check()
    dependencies = integrity.verify_dependencies()
    baseline = integrity.fingerprints(dependencies, {}, None)
    if any(baseline[key] != assets[key] for key in ("environment", "harness")):
        raise ValueError("environment/controller fingerprint mismatch")
    operation = request["operation"]
    if operation == "probe":
        native = Path(request["native_state"])
        if (native.parent / "native-halt.json").exists():
            raise ValueError("native execution halted")
        marker = Path(binding["smoke_marker"])
        smoke = importlib.import_module("poc.smoke")
        if read_json(marker.parent, marker.name).get("adapter_sha256") != binding["adapter_sha256"]:
            raise ValueError("smoke adapter mismatch")
        clone(smoke.require_smoke, {"ROOT": native})(baseline["environment"], marker)
        return {"protected_unchanged": True, "dependencies_verified": True, "matching_smoke": True}
    if operation == "audit":
        for key in assets["tasks"]:
            for name in tuple(sys.modules):
                if name == "tasks" or name.startswith("tasks."):
                    del sys.modules[name]
            load_task(pack, key, assets)
        return {"protected_unchanged": True, "dependencies_verified": True, "fingerprints": baseline,
                "task_imports_verified": len(assets["tasks"])}
    native = Path(request["native_state"])
    work = Path(request["work"])
    marker = Path(binding["smoke_marker"])
    smoke, instances = install_adapter(native, work / "cancel", marker, binding["adapter_sha256"])
    if operation == "smoke":
        if marker.exists():
            raise ValueError("refuse smoke evidence overwrite")
        status = 2
        try:
            clone(smoke.main, {"MARKER": marker})()
        except SystemExit as ended:
            status = ended.code
        if len(instances) != 1:
            raise ValueError("unexpected smoke runtime count")
        result = read_json(instances[0].directory, "smoke-v2-result.json")
        if status == 0 and result.get("passed") is True:
            stamp = read_json(marker.parent, marker.name)
            stamp["adapter_sha256"] = binding["adapter_sha256"]
            marker.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        return {"smoke": result, "fingerprints": baseline}
    if operation != "evaluate":
        raise ValueError("unsupported operation")
    candidate = Path(request["candidate"])
    candidate_hash, candidate_fingerprint = candidate_identity(candidate)
    key = request["task"]
    if (candidate_hash != request["submission_sha256"] or not candidate_reviewed(
        native.parent, assets, binding["assets_sha256"], key, candidate_hash, candidate_fingerprint
    )):
        raise ValueError("candidate bytes are outside the approved review set")
    task = load_task(pack, key, assets)
    evaluate = importlib.import_module("poc.evaluate")
    evaluate.TASKS[key] = task
    before = integrity.fingerprints(dependencies, task.files(), candidate)
    if before["candidate"] != candidate_fingerprint:
        raise ValueError("candidate fingerprint differs across controller boundary")
    result = evaluate.run(key, candidate, "platform-" + request["request_id"])
    after = integrity.fingerprints(integrity.verify_dependencies(), task.files(), candidate)
    runtime.protected_check()
    verified_assets(pack, binding["assets_sha256"])
    verify_controller(root, assets)
    if before != after or adapter_identity() != binding["adapter_sha256"]:
        raise ValueError("evaluation inputs changed")
    result["platform_inputs_unchanged"] = True
    return {"evaluation": result, "fingerprints": before, "runtime_count": len(instances)}


def main() -> None:
    # Parent sends this only after assigning our handle to its owned Job Object.
    line = sys.stdin.buffer.readline(512 * 1024 + 1)
    if len(line) > 512 * 1024 or not line.endswith(b"\n"):
        raise ValueError("invalid request size/framing")
    request = json.loads(line)
    readonly = sys.argv[1:] == ["--probe"]
    if readonly and request.get("operation") != "probe":
        raise ValueError("read-only entry only accepts probe")
    if not readonly and request.get("operation") == "probe":
        raise ValueError("probe requires the read-only entry")
    result: dict[str, Any]
    try:
        result = execute(request)
    except Exception as error:
        result = {"bridge_error": type(error).__name__, "private_detail": str(error)}
    response = {"protocol": PROTOCOL, "request_id": request["request_id"], "nonce": request["nonce"],
                "submission_sha256": request["submission_sha256"], "result": result}
    if readonly:
        print(json.dumps(response, ensure_ascii=False))
    else:
        json_write_new(Path(request["work"]) / "response.json", response)


if __name__ == "__main__":
    main()
