"""Serial, preapproved maintenance controls through the managed core CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from rhenium_balatro import container_host as host
from rhenium_balatro.catalog import load_catalog
from rhenium_balatro.container_builder import BalatroContainerBuilder
from rhenium_balatro.container_operator import runtime_spec
from rhenium_balatro.linux_runtime import sha
from rhenium_balatro.native_assets import json_write_new, verified_assets
from rhenium_balatro.plugin import BalatroBenchmarkPlugin
from rhenium_balatro.review import candidate_identity

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    for name in ("repo", "pack", "state", "artifact", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--group", choices=("pairs", "remaining", "all"), required=True)
    parser.add_argument("--tasks", nargs="+")
    args = parser.parse_args()
    context = BenchmarkContext(project_root=args.repo, pack_root=args.pack,
                               state_dir=args.state / "packs/balatro/core",
                               cache_dir=args.state / "cache/plugins/balatro/core")
    data = json.loads(args.artifact.read_text())
    artifact = RuntimeArtifact.model_validate(data.get("artifact", data))
    builder = BalatroContainerBuilder(context)
    if not builder.verify(runtime_spec(context), artifact)["available"]:
        raise ValueError("Prepared container with current smoke required")
    root, record = host.load_record(artifact)
    assets = verified_assets(args.pack, record["smoke"]["assets_sha256"])
    tasks = [task for task in load_catalog(args.pack, "catalog.json").tasks
             if args.tasks is None or task.id in args.tasks]
    if not tasks or (args.tasks is not None and set(args.tasks) != {task.id for task in tasks}):
        raise ValueError("Unknown task selection")
    selected = [(task, role, control) for task in tasks
                for role, control in assets["controls"][task.id].items()
                if args.group == "all" or ((role in {"gold", "base"}) == (args.group == "pairs"))]
    args.output.mkdir(parents=True, mode=0o700)
    json_write_new(args.output / "request.json", {
        "schema_version": 1, "maintenance_only": True, "group": args.group,
        "controls": [{"task": task.id, "role": role} for task, role, _ in selected],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
        "driver_sha256": sha(Path(__file__)), "artifact_identity": artifact.identity,
        "image_id": record["image_id"], "recipe": record["recipe"],
        "assets_sha256": record["smoke"]["assets_sha256"],
    })
    environment = {
        "PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": str(args.output / "home"),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join(str(path) for path in [
            args.repo / "src", *sorted((args.repo / "plugins").glob("*/src")),
            *sorted((args.repo / "providers").glob("*/src")),
        ]),
        "RHENIUM_ROOT": str(args.repo), "RHENIUM_STATE_DIR": str(args.state),
        "RHENIUM_BENCHMARK_PATH": str(args.pack),
    }
    operations = root / "operator-state/linux/operations"
    containers = context.state_dir / "container-operations"
    outcomes: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for task, role, control in selected:
        if not builder.verify(runtime_spec(context), artifact)["available"]:
            raise ValueError("Execution inputs changed during controls")
        folder = args.output / f"{len(outcomes) + 1:02d}-{uuid.uuid4().hex}"
        folder.mkdir(mode=0o700)
        attempt = folder / "attempt"
        BalatroBenchmarkPlugin().materialize_attempt(task, attempt, context)
        source = args.pack / "private/native-v1" / control["source"]
        for name in control["files"]:
            shutil.copyfile(source / name, attempt / "starter" / name)
        if candidate_identity(attempt / "starter") != (control["seal_sha256"], control["candidate_sha256"]):
            raise ValueError("Reviewed control source changed")
        before = set(operations.iterdir())
        before_containers = set(containers.iterdir()) if containers.exists() else set()
        command = [str(Path(sys.executable).with_name("rhenium")), "run", f"balatro/core/{task.id}",
                   str(attempt), "--profile", "full", "--security-mode", "honest"]
        json_write_new(folder / "command.json", command)
        started = time.monotonic()
        with (folder / "stdout.json").open("xb") as stdout, (folder / "stderr.log").open("xb") as stderr:
            completed = subprocess.run(command, cwd=args.repo, env=environment,
                                       stdout=stdout, stderr=stderr, timeout=2000, check=False)
        new = set(operations.iterdir()) - before
        new_containers = set(containers.iterdir()) - before_containers if containers.exists() else set()
        stdout_file = folder / "stdout.json"
        public = json.loads(stdout_file.read_text()) if stdout_file.stat().st_size else {}
        result = public.get("result", {})
        raw: dict[str, Any] = {}
        envelope: dict[str, Any] = {}
        operation = next(iter(new)) if len(new) == 1 else None
        if operation is not None and (operation / "engine-result.json").exists():
            raw = json.loads((operation / "engine-result.json").read_text())["evaluation"]
        if len(new_containers) == 1:
            outer = next(iter(new_containers))
            if (outer / "response.json").exists():
                envelope = json.loads((outer / "response.json").read_text())
        checks = {item["id"]: item["passed"] for item in raw.get("checks", [])}
        processes = raw.get("processes", [])
        namespace = envelope.get("pid_namespace", "")
        process_ids = {(namespace, item["run_id"]) for item in processes}
        expected = (
            len(new) == len(new_containers) == 1
            and result.get("complete") is True and result.get("passed") is control["expected_pass"]
            and completed.returncode == (0 if control["expected_pass"] else 1)
            and envelope.get("image") == record["image_id"]
            and re.fullmatch(r"pid:\[\d+\]", namespace) is not None
            and len(processes) == len(process_ids) == assets["tasks"][task.id]["expected_processes"]
            and not identities.intersection(process_ids)
            and all(checks.get(case) is False for case in control["must_fail"])
            and all(checks.get(case) is True for case in control["must_pass"])
            and all(item["cleanup"]["normal_exit"] is True
                    and item["cleanup"]["protected_unchanged"] is True for item in processes)
        )
        identities.update(process_ids)
        row = {"task": task.id, "control": role, "core_run_id": public.get("id"),
               "complete": result.get("complete", False), "passed": result.get("passed", False),
               "category": result.get("category"), "reason": result.get("reason"),
               "expected_control_outcome": expected, "exit_code": completed.returncode,
               "elapsed_seconds": round(time.monotonic() - started, 3), "processes": len(processes),
               "required_outcomes": len(checks), "pid_namespace": namespace,
               "operation": operation.name if operation else None,
               "submission_sha256": control["seal_sha256"], "stdout_sha256": sha(folder / "stdout.json")}
        json_write_new(folder / "outcome.json", row)
        outcomes.append(row)
        print(json.dumps(row), flush=True)
        if not expected:
            break
    complete = len(outcomes) == len(selected) and all(row["expected_control_outcome"] for row in outcomes)
    json_write_new(args.output / "summary.json", {"schema_version": 1, "complete": complete,
        "all_expected": complete, "requested_controls": len(selected), "completed_controls": len(outcomes),
        "artifact_identity": artifact.identity, "image_id": record["image_id"], "outcomes": outcomes})
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
