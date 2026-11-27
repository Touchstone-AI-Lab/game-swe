"""Run the frozen initialized-load v3 capability through the Linux Session adapter."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import types
import uuid
from pathlib import Path

from rhenium_balatro.linux_runtime import BalatroLinuxProbeBuilder, sha
from rhenium_balatro.linux_session import LinuxSessionHost
from rhenium_balatro.native_assets import json_write_new
from rhenium_balatro.protocol import classify_poc_result

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("prepared", "pack", "state"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--windows-powershell", type=Path)
    parser.add_argument("--controlled-runtime", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).parent / "save_capability_v1"
    provenance = json.loads((source / "provenance.json").read_text())
    for name, expected in provenance["copied_authored_files"].items():
        file = source / "fixtures" / name
        if file.stat().st_size != expected["size"] or sha(file) != expected["sha256"]:
            raise ValueError("Frozen save capability source changed")
    artifact = RuntimeArtifact.model_validate(json.loads(args.prepared.read_text())["artifact"])
    spec = RuntimeSpec.model_validate(
        next(
            item
            for item in json.loads((args.pack / "runtimes.json").read_text())["runtimes"]
            if artifact.runtime_key.endswith("/" + item["id"])
        )
    )
    context = BenchmarkContext(
        project_root=args.pack.parents[1],
        pack_root=args.pack,
        state_dir=args.state,
        cache_dir=args.state / "cache",
    )
    operation = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    evidence_kind = "save-capability-controlled-v1" if args.controlled_runtime else "save-capability-v1"
    derived = artifact.runtime_key == "balatro/balatro-linux-17459173-controlled-v2"
    if derived:
        if not args.controlled_runtime:
            raise ValueError("Derived runtime requires explicit controlled-runtime selection")
        evidence_kind = "save-capability-controlled-v2"
    out = args.state / evidence_kind / operation
    out.mkdir(parents=True)
    builder: BalatroLinuxProbeBuilder
    if args.controlled_runtime:
        from rhenium_balatro.linux_managed import BalatroLinuxRuntimeBuilder

        if derived:
            from rhenium_balatro.linux_managed_v2 import BalatroLinuxRuntimeBuilderV2

            builder = BalatroLinuxRuntimeBuilderV2(context)
        else:
            builder = BalatroLinuxRuntimeBuilder(context)
    else:
        builder = BalatroLinuxProbeBuilder(context)
    host = LinuxSessionHost(
        builder=builder,
        spec=spec,
        artifact=artifact,
        pack=args.pack,
        assets_sha256=provenance["assets_sha256"],
        run_root=args.state / "engine-v1",
        windows_powershell=args.windows_powershell,
    )
    evaluate = host.install()
    namespace = types.ModuleType("tasks")
    namespace.__path__ = [str(source / "fixtures/tasks")]
    sys.modules["tasks"] = namespace
    module = importlib.import_module("tasks.durable_charge.save_probe_v3.probe")
    key = "probe-save-v3-linux"
    task = types.SimpleNamespace(
        key=key,
        session_api=True,
        mods={"load_diagnostic": source / "fixtures/tasks/durable_charge/load_diag_v1/mod"},
        files=lambda: provenance["copied_authored_files"],
        scenario=lambda: module,
    )
    evaluate.TASKS[key] = task
    json_write_new(
        out / "inputs.json",
        {
            "driver_sha256": sha(Path(__file__)),
            "provenance_sha256": sha(source / "provenance.json"),
            "fingerprints": host.fingerprints(task.files(), None),
            "artifact": artifact.identity,
        },
    )
    raw = evaluate.run(key, None, operation)
    host.verify()
    classified = classify_poc_result(raw, tuple(module.REQUIRED), host.fingerprints(task.files(), None), 2)
    result = {
        "operation": operation,
        "evaluation": raw,
        "classification": classified,
        "frozen_probe_source_unchanged": True,
        "no_task_candidate": True,
    }
    json_write_new(out / "result.json", result)
    print(
        json.dumps(
            {
                "result": str(out / "result.json"),
                "complete": classified["complete"],
                "passed": classified["passed"],
                "error": raw.get("error"),
                "processes": len(raw.get("processes", [])),
            }
        )
    )
    return 0 if classified["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
