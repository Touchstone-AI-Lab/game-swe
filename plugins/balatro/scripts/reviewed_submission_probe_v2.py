"""Two source-reviewed, previously unlisted byte identities via the public wrapper.

Only a Lua comment is appended to authored growth controls. This tests admission,
not new task coverage, a new implementation, or a new mutation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from native_matrix_v1 import cli
from rhenium_balatro.bridge import child_environment, load_binding
from rhenium_balatro.catalog import BalatroTask, load_catalog
from rhenium_balatro.evaluator import classify_native
from rhenium_balatro.files import read_file
from rhenium_balatro.native_assets import file_sha, json_write_new, verified_assets
from rhenium_balatro.protocol import decode_response
from rhenium_balatro.review import candidate_identity, candidate_reviewed
from rhenium_balatro.winjob import hidden_creation_flags


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    for name in ("repository", "state", "evidence", "attempts", "powershell"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    repo, evidence = args.repository.resolve(), args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    pack = repo / "benchmarks/balatro"
    state = args.state.resolve() / "packs/balatro/core"
    binding = load_binding(state)
    assets = verified_assets(pack, binding["assets_sha256"])
    task = next(t for t in load_catalog(pack, "catalog.json").tasks if t.id == "growth-v2")
    assert isinstance(task, BalatroTask)
    wrapper = repo / "scripts/score-exam.ps1"
    json_write_new(evidence / "plan.json", {"schema_version": 2, "roles": ["gold", "base"],
        "script_sha256": file_sha(Path(__file__)), "wrapper_sha256": file_sha(wrapper),
        "adapter_sha256": binding["adapter_sha256"], "not_new_semantic_coverage": True})
    records = []
    for role in ("gold", "base"):
        started = time.monotonic()
        work = evidence / role
        work.mkdir()
        attempt = args.attempts.resolve() / uuid.uuid4().hex
        attempt.parent.mkdir(parents=True, exist_ok=True)
        env = child_environment(work)
        env.update(RHENIUM_ROOT=str(repo), RHENIUM_STATE_DIR=str(args.state.resolve()),
                   RHENIUM_CACHE_DIR=str(args.state.resolve().parent / "cache"),
                   RHENIUM_DATABASE_URL="sqlite:///" + str(args.state.resolve() / "state.sqlite"),
                   RHENIUM_BENCHMARK_PATH=str(pack))
        code, _ = cli(["prepare-attempt", "balatro/core/" + task.id, str(attempt),
                       "--score-command", str(wrapper), "--mode", "strict"], repo, env, work, "prepare")
        if code != 0:
            raise RuntimeError("anonymous preparation failed")
        selected = assets["controls"][task.id][role]
        source = pack / "private/native-v1" / selected["source"]
        for name in task.editable_files:
            data = read_file(source, name.removeprefix("starter/"))
            comment = b"\n-- Source-reviewed admission probe; semantics unchanged.\n"
            (attempt / name).write_bytes(data + comment)
        seal, candidate = candidate_identity(attempt / "starter")
        if candidate_reviewed(state, assets, binding["assets_sha256"], task.id, seal, candidate):
            raise ValueError("probe bytes must begin unreviewed")
        review = [sys.executable, "-I", "-B", "-m", "rhenium_balatro.maintenance", "review-submission",
                  "--pack", str(pack), "--state", str(state), "--task", task.id,
                  "--submission", str(attempt), "--source-reviewed", "--reviewed-submission-sha256", seal]
        result = subprocess.run(review, capture_output=True, env=env, check=False,
                                creationflags=hidden_creation_flags())
        json_write_new(work / "review-command.json", review)
        (work / "review.json").write_bytes(result.stdout)
        (work / "review.stderr").write_bytes(result.stderr)
        if result.returncode or not candidate_reviewed(state, assets, binding["assets_sha256"],
                                                       task.id, seal, candidate):
            raise RuntimeError("explicit review failed")
        prior = {p.name for p in (state / "operations").iterdir()}
        command = [str(args.powershell), "-NoProfile", "-NonInteractive", "-File", str(wrapper),
                   str(attempt), "-Profile", "full", "-SecurityMode", "honest"]
        json_write_new(work / "score-command.json", command)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
        env["PATHEXT"] = ".EXE"
        result = subprocess.run(command, capture_output=True, env=env, check=False,
                                creationflags=hidden_creation_flags())
        (work / "score.json").write_bytes(result.stdout)
        (work / "score.stderr").write_bytes(result.stderr)
        new = [p for p in (state / "operations").iterdir() if p.name not in prior]
        if len(new) != 1:
            raise RuntimeError("expected one native operation")
        operation = new[0]
        request = json.loads((operation / "request.json").read_bytes())
        response = decode_response((operation / "response.json").read_bytes(),
                                   request["request_id"], request["nonce"], seal)
        actual = classify_native(response, assets, task.id, seal, candidate)
        public = json.loads(result.stdout)["result"]
        checks = {c["id"]: c["passed"] for c in response["evaluation"]["checks"]}
        if (actual["complete"] is not True or actual["passed"] is not selected["expected_pass"]
                or public["complete"] is not True or public["passed"] is not selected["expected_pass"]
                or public["submissionSha256"] != seal or result.returncode != (0 if role == "gold" else 1)
                or not all(checks.get(c) is True for c in selected["must_pass"])
                or not all(checks.get(c) is False for c in selected["must_fail"])):
            raise RuntimeError("reviewed submission incomplete or behavior mismatch")
        record = {"role": role, "complete": True, "passed": actual["passed"],
            "score_exit_code": result.returncode,
            "submission_sha256": seal, "candidate_sha256": candidate, "original_control_sha256":
            selected["candidate_sha256"], "initially_unreviewed": True,
            "elapsed_seconds": time.monotonic() - started,
            "review_record_sha256": file_sha(state / "reviews" / f"{task.id}-{seal}.json"),
            "native_processes": len(response["evaluation"]["processes"]),
            "operation_files": {str(p): file_sha(p) for p in operation.iterdir() if p.is_file()},
            "flow_files": {p.name: file_sha(p) for p in work.iterdir() if p.is_file()}}
        json_write_new(work / "record.json", record)
        records.append({"file": role + "/record.json", "sha256": file_sha(work / "record.json")})
        print(json.dumps({"event": "reviewed_submission_finished", "role": role, "complete": True,
                          "passed": actual["passed"]}), flush=True)
    json_write_new(evidence / "complete.json", {"completed_flows": 2, "records": records})


if __name__ == "__main__":
    main()
