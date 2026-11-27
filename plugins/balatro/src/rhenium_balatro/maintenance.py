"""Explicit local operator preparation; never downloads or changes fixed inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bridge import BINDING_NAME, invoke, load_binding, serial_lock
from .catalog import BalatroTask, load_catalog
from .files import digest, read_file, read_json, validate_state
from .native_assets import (
    ASSETS,
    adapter_identity,
    file_sha,
    json_write_new,
    verified_assets,
    verify_controller,
)
from .readiness import runtime_status
from .review import candidate_identity, record_review
from .submission import seal_submission, snapshot, verify_seal


def prepare(pack: Path, state: Path, root: Path, reviewed_freeze: str) -> dict[str, Any]:
    validate_state(pack, state)
    assets_hash = digest(read_file(pack, ASSETS))
    assets = verified_assets(pack, assets_hash)
    if assets["source_freeze_sha256"] != reviewed_freeze:
        raise ValueError("reviewed source freeze mismatch")
    verify_controller(root, assets)
    python = root / ".venv/Scripts/python.exe"
    binding = {"schema_version": 2, "scope": "reviewed-local-honest-v2",
               "controller_root": str(root.resolve()), "python": str(python.resolve()),
               "python_sha256": file_sha(python), "assets_sha256": assets_hash,
               "adapter_sha256": adapter_identity(),
               "smoke_marker": str((state / "native/smoke.json").resolve())}
    with serial_lock(state):
        if (state / BINDING_NAME).exists():
            raise ValueError("refuse existing runtime binding overwrite; use a new platform state")
        audit, work = invoke(pack, state, binding, "audit", timeout=120)
        if audit.get("dependencies_verified") is not True or audit.get("protected_unchanged") is not True:
            raise RuntimeError("fixed external runtime audit failed: " + work.name)
        json_write_new(state / BINDING_NAME, binding)
    return {"prepared": True, "adapter_sha256": binding["adapter_sha256"], "game_started": False}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=("prepare", "audit", "smoke", "doctor",
                                           "inspect-submission", "review-submission"))
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--controller-root", type=Path)
    parser.add_argument("--reviewed-freeze-sha256")
    parser.add_argument("--task")
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--reviewed-submission-sha256")
    parser.add_argument("--source-reviewed", action="store_true",
                        help="Attest operator review of these exact source bytes; this tool does not review.")
    args = parser.parse_args()
    validate_state(args.pack, args.state)
    if args.command == "doctor":
        result = runtime_status(args.pack, args.state)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result["available"] else 2)
    if args.command in {"inspect-submission", "review-submission"}:
        if args.task is None or args.submission is None:
            parser.error("submission inspection/review requires task and submission")
        task = next((t for t in load_catalog(args.pack, "catalog.json").tasks if t.id == args.task), None)
        if not isinstance(task, BalatroTask):
            parser.error("unknown task")
        snapshot(args.submission, task)  # Immutable metadata and public file allowlist.
        submission_sha, candidate_sha = candidate_identity(args.submission / "starter")
        if args.command == "inspect-submission":
            result = {"submissionSha256": submission_sha, "candidateSha256": candidate_sha,
                      "sourceReviewPerformed": False, "gameStarted": False}
        else:
            if not args.source_reviewed or args.reviewed_submission_sha256 is None:
                parser.error("review requires source-reviewed and reviewed-submission-sha256")
            with serial_lock(args.state):
                binding = load_binding(args.state)
                assets = verified_assets(args.pack, binding["assets_sha256"])
                sealed = seal_submission(args.submission, task, args.state / "review-submissions")
                actual, candidate_sha = candidate_identity(sealed.directory)
                verify_seal(sealed)
                record_review(args.state, assets, binding["assets_sha256"], task.id, actual,
                              candidate_sha, args.reviewed_submission_sha256)
                result = {"reviewRecorded": True, "submissionSha256": actual, "gameStarted": False}
    elif args.command == "prepare":
        if args.controller_root is None or args.reviewed_freeze_sha256 is None:
            parser.error("prepare requires controller-root and reviewed-freeze-sha256")
        result = prepare(args.pack, args.state, args.controller_root, args.reviewed_freeze_sha256)
    else:
        with serial_lock(args.state):
            binding = load_binding(args.state)
            value, work = invoke(args.pack, args.state, binding, args.command, timeout=180)
            if "bridge_error" in value:
                raise RuntimeError("native operation failed; private record " + work.name)
            if args.command == "smoke":
                if value.get("smoke", {}).get("passed") is not True:
                    raise RuntimeError("bounded smoke incomplete; private record " + work.name)
                stamp = read_json(Path(binding["smoke_marker"]).parent, "smoke.json")
                result = {"passed": True, "run_id": stamp["run_id"], "adapter_sha256": adapter_identity()}
            else:
                result = value
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
