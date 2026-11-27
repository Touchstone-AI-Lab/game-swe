"""Explicit inspection/review for a prepared container; no automatic source approval."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec

from . import container_host as host
from .catalog import BalatroTask, load_catalog
from .container_builder import BalatroContainerBuilder
from .linux_bridge import serial_lock
from .review import candidate_identity
from .submission import seal_submission


def runtime_spec(context: BenchmarkContext) -> RuntimeSpec:
    data = json.loads((context.pack_root / "runtimes.json").read_text())
    return RuntimeSpec.model_validate(next(value for value in data["runtimes"]
                                          if value["id"] == host.RUNTIME_ID))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("inspect", "review"))
    for name in ("pack", "state", "cache", "artifact", "submission"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--reviewed-sha")
    parser.add_argument("--source-reviewed", action="store_true")
    args = parser.parse_args()
    context = BenchmarkContext(project_root=args.pack.parent, pack_root=args.pack,
                               state_dir=args.state, cache_dir=args.cache)
    data = json.loads(args.artifact.read_text())
    artifact = RuntimeArtifact.model_validate(data.get("artifact", data))
    if not BalatroContainerBuilder(context).verify(runtime_spec(context), artifact)["available"]:
        raise ValueError("Prepared container and matching smoke are required")
    task = next(t for t in load_catalog(args.pack, "catalog.json").tasks if t.id == args.task)
    if not isinstance(task, BalatroTask):
        raise ValueError("Incompatible task")
    root, record = host.load_record(artifact)
    sealed = seal_submission(args.submission, task, root / "operator-state/submissions")
    seal, _ = candidate_identity(sealed.directory)
    if args.operation == "inspect":
        print(json.dumps({"submissionSha256": seal, "files": sorted(sealed.files)}))
        return
    if not args.source_reviewed or args.reviewed_sha != seal:
        raise ValueError("Review the actual source and supply its matching seal explicitly")
    with serial_lock(root / "host-serial"):
        work = args.state / "container-review-operations" / uuid.uuid4().hex
        result = host.run_worker(
            record["image_id"], {"operation": "review", "image": record["image_id"],
                "context": context.model_dump(mode="json"), "root": str(root),
                "native": record["native"], "submission": str(args.submission.resolve()),
                "task": task.id, "reviewed_sha": seal}, work,
            readonly=(args.pack, root, args.submission.resolve()),
            writable=(root / "operator-state", root / "plugin-cache", work),
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
