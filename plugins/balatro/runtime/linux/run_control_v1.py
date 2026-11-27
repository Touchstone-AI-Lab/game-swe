"""Maintenance-only launcher: sealed existing controls, real frozen full scenarios."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from pathlib import Path

from rhenium_balatro.catalog import BalatroTask, load_catalog
from rhenium_balatro.linux_control import execute
from rhenium_balatro.linux_runtime import BalatroLinuxProbeBuilder, sha
from rhenium_balatro.linux_session import LinuxSessionHost
from rhenium_balatro.native_assets import json_write_new
from rhenium_balatro.plugin import BalatroBenchmarkPlugin
from rhenium_balatro.submission import seal_submission, verify_seal

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("prepared", "pack", "state"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--windows-powershell", type=Path)
    parser.add_argument("--operation", choices=("smoke", "evaluate"), required=True)
    parser.add_argument("--task")
    parser.add_argument("--control", choices=("gold", "base", "alternative"))
    parser.add_argument("--smoke", type=Path)
    args = parser.parse_args()
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
    provenance = json.loads((Path(__file__).parent / "save_capability_v1/provenance.json").read_text())
    host = LinuxSessionHost(
        builder=BalatroLinuxProbeBuilder(context),
        spec=spec,
        artifact=artifact,
        pack=args.pack,
        assets_sha256=provenance["assets_sha256"],
        run_root=args.state / "engine-v1",
        windows_powershell=args.windows_powershell,
    )
    operation_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    out = args.state / "controls-v1" / operation_id
    out.mkdir(parents=True)
    sealed = None
    control = None
    if args.operation == "evaluate":
        task = next(task for task in load_catalog(args.pack, "catalog.json").tasks if task.id == args.task)
        if not isinstance(task, BalatroTask):
            raise TypeError("Balatro maintenance control requires its typed task catalog")
        control = host.assets["controls"][task.id][args.control]
        attempt = out / "attempt"
        BalatroBenchmarkPlugin().materialize_attempt(task, attempt, context)
        source = args.pack / "private/native-v1" / control["source"]
        # Populate a maintenance attempt from the reviewed control, without changing
        # the public contract, immutable starter files or private acceptance cases.
        for name in control["files"]:
            destination = attempt / "starter" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination)
        sealed = seal_submission(attempt, task, out / "sealed")
        if sealed.sha256 != control["seal_sha256"]:
            raise ValueError("Control submission seal changed")
    json_write_new(
        out / "request.json",
        {
            "operation": args.operation,
            "task": args.task,
            "control": args.control,
            "driver_sha256": sha(Path(__file__)),
            "submission_sha256": sealed.sha256 if sealed else None,
        },
    )
    result = execute(
        host,
        operation=args.operation,
        output=out / "result.json",
        task_key=args.task or "",
        candidate=sealed.directory if sealed else None,
        smoke=args.smoke,
    )
    if sealed is not None:
        verify_seal(sealed)
    classified = result["classification"]
    expected = classified["complete"] and classified["passed"] == (
        control["expected_pass"] if control else True
    )
    if control:
        checks = {check["id"]: check["passed"] for check in result["evaluation"]["checks"]}
        expected = expected and all(checks.get(key) is False for key in control["must_fail"])
        expected = expected and all(checks.get(key) is True for key in control["must_pass"])
    summary = {
        "result": str(out / "result.json"),
        "task": args.task,
        "control": args.control,
        "complete": classified["complete"],
        "passed": classified["passed"],
        "expected_control_outcome": expected,
        "error": result["evaluation"].get("error"),
        "processes": result["runtime_count"],
    }
    json_write_new(out / "control-outcome.json", summary)
    print(json.dumps(summary))
    return 0 if expected else 2


if __name__ == "__main__":
    raise SystemExit(main())
