"""Explicit smoke/binding and exact-byte review; never authenticates or acquires."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import BalatroTask, load_catalog
from .files import read_json
from .linux_bridge import BINDING_NAME, invoke, serial_lock
from .linux_worker import make_host, verify_binding
from .native_assets import file_sha, json_write_new
from .review import candidate_identity, record_review
from .submission import seal_submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("smoke", "review"))
    for name in ("pack", "state", "cache"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--windows-powershell", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--reviewed-sha")
    args = parser.parse_args()
    context = BenchmarkContext(
        project_root=args.pack.parent, pack_root=args.pack, state_dir=args.state, cache_dir=args.cache
    )
    with serial_lock(args.state):
        if (args.state / "linux-halt.json").exists():
            raise ValueError("Incomplete operation requires explicit diagnosis before a new binding")
        if args.operation == "smoke":
            if args.artifact is None or (args.state / BINDING_NAME).exists():
                raise ValueError("Prepared artifact required; existing binding must be preserved")
            data = json.loads(args.artifact.read_text())
            artifact = RuntimeArtifact.model_validate(data.get("artifact", data))
            binding: dict[str, Any] = {
                "assets_sha256": file_sha(args.pack / "private/native-v1/assets.json"),
                "windows_powershell": str(args.windows_powershell) if args.windows_powershell else None,
            }
            result, work = invoke(context, artifact, binding, "smoke")
            if "bridge_error" in result or result["classification"]["passed"] is not True:
                raise RuntimeError(f"Smoke incomplete; inspect the private operation {work.name}")
            binding.update(
                {
                    "schema_version": 1,
                    "scope": "source-reviewed-native-linux",
                    "environment": result["fingerprints"]["environment"],
                    "harness": result["fingerprints"]["harness"],
                    "artifact_identity": artifact.identity,
                    "artifact": artifact.model_dump(mode="json"),
                    "smoke_marker": str(work / "engine-result.json"),
                }
            )
            host = make_host(context, artifact, binding)
            verify_binding(host, binding)
            json_write_new(args.state / BINDING_NAME, binding)
            print(
                json.dumps(
                    {"smoke_complete": True, "operation": work.name, "artifact_identity": artifact.identity}
                )
            )
        else:
            binding = read_json(args.state, BINDING_NAME)
            artifact = RuntimeArtifact.model_validate(binding["artifact"])
            host = make_host(context, artifact, binding)
            verify_binding(host, binding)
            if args.submission is None or args.task is None or args.reviewed_sha is None:
                raise ValueError("Explicit submission, task and source-reviewed seal are required")
            task = next(
                task for task in load_catalog(args.pack, "catalog.json").tasks if task.id == args.task
            )
            if not isinstance(task, BalatroTask):
                raise ValueError("Incompatible task")
            sealed = seal_submission(args.submission, task, args.state / "submissions")
            seal, candidate_hash = candidate_identity(sealed.directory)
            scoped = {**host.assets, "environment": host.environment, "harness": host.harness}
            record = record_review(
                args.state, scoped, host.assets_sha256, task.id, seal, candidate_hash, args.reviewed_sha
            )
            print(json.dumps({"review_recorded": True, "submission_sha256": record["submission_sha256"]}))


if __name__ == "__main__":
    main()
