"""Serial maintenance controls through the real core CLI, never model attempts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from rhenium_balatro.catalog import BalatroTask, load_catalog
from rhenium_balatro.linux_layout import execution_context
from rhenium_balatro.linux_runtime import sha
from rhenium_balatro.native_assets import adapter_identity, json_write_new, verified_assets
from rhenium_balatro.plugin import BalatroBenchmarkPlugin
from rhenium_balatro.review import candidate_identity

from rhenium.core.plugin import BenchmarkContext


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("repo", "pack", "state"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    catalog = load_catalog(args.pack, "catalog.json")
    tasks = [task for task in catalog.tasks if args.tasks is None or task.id in args.tasks]
    if not tasks or (args.tasks is not None and set(args.tasks) != {task.id for task in tasks}):
        raise ValueError("Unknown task selection")
    pack_state = args.state / "packs/balatro/core"
    context = execution_context(
        BenchmarkContext(
            project_root=args.repo,
            pack_root=args.pack,
            state_dir=pack_state,
            cache_dir=args.state / "cache/plugins/balatro/core",
        )
    )
    pack_state = context.state_dir
    binding = json.loads((pack_state / "linux-binding-v1.json").read_text())
    assets = verified_assets(args.pack, binding["assets_sha256"])
    version = "v2-window-v2" if pack_state.name == "linux-controlled-v2-window-v2" else (
        "v2" if pack_state.name == "linux-controlled-v2" else "v1"
    )
    out = (
        args.state / f"platform-controls-{version}" / (time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
    )
    out.mkdir(parents=True, mode=0o700)
    frozen_adapter = adapter_identity()
    json_write_new(
        out / "request.json",
        {
            "schema_version": 1,
            "maintenance_controls_only": True,
            "round": args.round,
            "tasks": [task.id for task in tasks],
            "roles": ["gold", "base"],
            "driver_sha256": sha(Path(__file__)),
            "adapter_sha256": frozen_adapter,
            "binding_sha256": sha(pack_state / "linux-binding-v1.json"),
        },
    )
    env = {
        "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(out / "control-home"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": ":".join(str(args.repo / name) for name in ("src", "plugins/balatro/src")),
        "RHENIUM_ROOT": str(args.repo),
        "RHENIUM_STATE_DIR": str(args.state),
        "RHENIUM_BENCHMARK_PATH": str(args.pack),
    }
    interop = Path(os.environ.get("WSL_INTEROP", ""))
    if interop.is_absolute() and interop.parent == Path("/run/WSL") and interop.is_socket():
        env["WSL_INTEROP"] = str(interop)
    outcomes: list[dict[str, Any]] = []
    stopped = False
    for task in tasks:
        if not isinstance(task, BalatroTask):
            raise ValueError("Incompatible task")
        for role in ("gold", "base"):
            if adapter_identity() != frozen_adapter:
                raise ValueError("Controller source changed during the batch")
            control = assets["controls"][task.id][role]
            folder = out / f"{len(outcomes) + 1:02d}-{task.id}-{role}"
            folder.mkdir()
            attempt = folder / "attempt"
            BalatroBenchmarkPlugin().materialize_attempt(task, attempt, context)
            source = args.pack / "private/native-v1" / control["source"]
            for name in control["files"]:
                destination = attempt / "starter" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, destination)
            if candidate_identity(attempt / "starter") != (
                control["seal_sha256"],
                control["candidate_sha256"],
            ):
                raise ValueError("Reviewed control bytes changed")
            operations = pack_state / "linux/operations"
            before = set(operations.iterdir())
            command = [
                str(Path(sys.executable).with_name("rhenium")),
                "run",
                f"balatro/core/{task.id}",
                str(attempt),
                "--profile",
                "full",
                "--security-mode",
                "honest",
            ]
            json_write_new(folder / "command.json", command)
            started = time.monotonic()
            with (folder / "stdout.json").open("xb") as stdout, (folder / "stderr.log").open("xb") as stderr:
                completed = subprocess.run(
                    command, cwd=args.repo, env=env, stdout=stdout, stderr=stderr, timeout=1900
                )
            elapsed = time.monotonic() - started
            new = set(operations.iterdir()) - before
            public = (
                json.loads((folder / "stdout.json").read_text())
                if (folder / "stdout.json").stat().st_size
                else {}
            )
            result = public.get("result", {})
            raw: dict[str, Any] = {}
            operation = None
            if len(new) == 1:
                operation = next(iter(new))
                if (operation / "engine-result.json").exists():
                    raw = json.loads((operation / "engine-result.json").read_text())["evaluation"]
            checks = {item["id"]: item["passed"] for item in raw.get("checks", [])}
            expected = (
                len(new) == 1
                and result.get("complete") is True
                and result.get("passed") is control["expected_pass"]
                and completed.returncode == (0 if control["expected_pass"] else 1)
                and all(checks.get(key) is False for key in control["must_fail"])
                and all(checks.get(key) is True for key in control["must_pass"])
                and len(raw.get("processes", [])) == assets["tasks"][task.id]["expected_processes"]
            )
            row = {
                "task": task.id,
                "control": role,
                "round": args.round,
                "core_run_id": public.get("id"),
                "complete": result.get("complete", False),
                "passed": result.get("passed", False),
                "category": result.get("category"),
                "reason": result.get("reason"),
                "expected_control_outcome": expected,
                "exit_code": completed.returncode,
                "elapsed_seconds": round(elapsed, 3),
                "processes": len(raw.get("processes", [])),
                "operation": operation.name if operation else None,
                "submission_sha256": control["seal_sha256"],
                "stdout_sha256": sha(folder / "stdout.json"),
            }
            json_write_new(folder / "outcome.json", row)
            outcomes.append(row)
            print(json.dumps(row), flush=True)
            if not expected:
                stopped = True
                break
        if stopped:
            break
    summary = {
        "schema_version": 1,
        "round": args.round,
        "adapter_sha256": frozen_adapter,
        "requested_controls": len(tasks) * 2,
        "completed_controls": len(outcomes),
        "outcomes": outcomes,
        "complete": not stopped and len(outcomes) == len(tasks) * 2,
        "all_expected": not stopped and all(row["expected_control_outcome"] for row in outcomes),
        "model_calibration": False,
    }
    json_write_new(out / "summary.json", summary)
    print(
        json.dumps({"summary": str(out / "summary.json"), "all_expected": summary["all_expected"]}),
        flush=True,
    )
    return 0 if summary["all_expected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
