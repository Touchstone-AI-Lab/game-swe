"""Verify final wrapper matrices, explicit reviews and independently sealed new submissions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rhenium_balatro.evaluator import classify_native
from rhenium_balatro.native_assets import ASSETS, adapter_identity, file_sha, json_write_new, verified_assets
from rhenium_balatro.protocol import decode_response
from rhenium_balatro.review import candidate_identity, candidate_reviewed, review_identity
from summarize_native_v1 import inspect


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def verify_operation(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    files = record.get("evidence_files", record.get("operation_files"))
    if not isinstance(files, dict):
        raise ValueError("missing operation file bindings")
    paths = {Path(name).name: Path(name) for name in files}
    for name, expected in files.items():
        if file_sha(Path(name)) != expected:
            raise ValueError("operation evidence changed")
    request, supervisor = read(paths["request.json"]), read(paths["supervisor.json"])
    if (supervisor["forced"] is not False or supervisor["cancelled"] is not False
            or supervisor["exit_code"] != 0 or supervisor["active_before_job_close"] != 0
            or supervisor["assigned_to_owned_job"] is not True):
        raise ValueError("owned process cleanup failed")
    result = decode_response(paths["response.json"].read_bytes(), request["request_id"], request["nonce"],
                             request["submission_sha256"])
    return request, result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    for name in ("repository", "batch", "freeze", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    repo, batch = args.repository.resolve(), args.batch.resolve()
    frozen = read(args.freeze)
    for name, expected in frozen["files"].items():
        if file_sha(repo / name) != expected:
            raise ValueError("final source changed: " + name)
    pack, state = repo / "benchmarks/balatro", batch / "hub/packs/balatro/core"
    wrapper_entry = ["-NoProfile", "-NonInteractive", "-File", str(repo / "scripts/score-exam.ps1")]
    assets_sha = file_sha(pack / ASSETS)
    assets = verified_assets(pack, assets_sha)
    summaries = {kind: inspect(batch / kind, kind, assets, assets_sha) for kind in ("controls", "targeted")}
    run_ids: set[str] = set()
    checks = 0
    processes = []
    for kind in summaries:
        directory = batch / kind
        entry = read(batch / (kind + "-entry-v2.json"))
        if (entry["driver_sha256"] != file_sha(Path(__file__).with_name("native_matrix_v2.py"))
                or entry["wrapper_sha256"] != file_sha(repo / "scripts/score-exam.ps1")
                or entry["entry"] != "scripts/score-exam.ps1"):
            raise ValueError("wrapper matrix identity changed")
        for binding in read(directory / "complete.json")["records"]:
            path = directory / binding["file"]
            record = read(path)
            command = read(path.parent / "run-command.json")
            if (command[1:5] != wrapper_entry
                    or command[6:] != ["-Profile", "full", "-SecurityMode", "honest"]
                    or file_sha(Path(command[0])) != entry["powershell_sha256"]):
                raise ValueError("flow did not use the declared anonymous wrapper")
            request, result = verify_operation(record)
            if kind == "targeted":
                selected = assets["controls"][record["task"]][record["role"]]
                expected = review_identity(assets, assets_sha, record["task"],
                                           selected["seal_sha256"], selected["candidate_sha256"])
                review = read(path.parent / "source-review-v2.json")
                if ({key: review.get(key) for key in expected} != expected
                        or not candidate_reviewed(state, assets, assets_sha, record["task"],
                                                  selected["seal_sha256"], selected["candidate_sha256"])):
                    raise ValueError("targeted source review mismatch")
            checks += len(result["evaluation"]["checks"])
            processes.extend(result["evaluation"]["processes"])
    reviewed = []
    review_plan = read(batch / "reviewed/plan.json")
    if (review_plan["script_sha256"] != file_sha(Path(__file__).with_name("reviewed_submission_probe_v2.py"))
            or review_plan["adapter_sha256"] != adapter_identity()
            or review_plan["wrapper_sha256"] != file_sha(repo / "scripts/score-exam.ps1")):
        raise ValueError("review probe source identity changed")
    completion = read(batch / "reviewed/complete.json")
    if completion["completed_flows"] != 2 or len(completion["records"]) != 2:
        raise ValueError("reviewed submission probes incomplete")
    for role, binding in zip(("gold", "base"), completion["records"], strict=True):
        path = batch / "reviewed" / binding["file"]
        if file_sha(path) != binding["sha256"]:
            raise ValueError("review probe record changed")
        record = read(path)
        for name, expected in record["flow_files"].items():
            if file_sha(path.parent / name) != expected:
                raise ValueError("review probe CLI evidence changed")
        request, result = verify_operation(record)
        seal, candidate = candidate_identity(Path(request["candidate"]))
        if (record["role"] != role or request["task"] != "growth-v2"
                or (seal, candidate) != (record["submission_sha256"], record["candidate_sha256"])
                or seal in {c["seal_sha256"] for c in assets["controls"]["growth-v2"].values()}
                or record["initially_unreviewed"] is not True
                or file_sha(state / "reviews" / f"growth-v2-{seal}.json") != record["review_record_sha256"]
                or not candidate_reviewed(state, assets, assets_sha, "growth-v2", seal, candidate)):
            raise ValueError("new reviewed candidate identity not proven")
        actual = classify_native(result, assets, "growth-v2", seal, candidate)
        selected = assets["controls"]["growth-v2"][role]
        outcomes = {c["id"]: c["passed"] for c in result["evaluation"]["checks"]}
        public = read(path.parent / "score.json")["result"]
        command = read(path.parent / "score-command.json")
        if (actual["complete"] is not True or actual["passed"] is not selected["expected_pass"]
                or public["submissionSha256"] != seal
                or record["score_exit_code"] != (0 if role == "gold" else 1)
                or command[1:5] != wrapper_entry
                or command[6:] != ["-Profile", "full", "-SecurityMode", "honest"]
                or any(public[key] != actual[key] for key in ("complete", "passed", "score", "category"))
                or not all(outcomes[c] is False for c in selected["must_fail"])
                or not all(outcomes[c] is True for c in selected["must_pass"])):
            raise ValueError("new reviewed submission result mismatch")
        checks += len(result["evaluation"]["checks"])
        processes.extend(result["evaluation"]["processes"])
        reviewed.append({"role": role, "complete": True, "passed": actual["passed"],
                         "submission_sha256": seal, "record_sha256": file_sha(path)})
    for process in processes:
        if process["run_id"] in run_ids:
            raise ValueError("native process evidence reused")
        run_ids.add(process["run_id"])
    tasks = [{"task": key, "gold_passes": summaries["controls"]["counts"].get(key + "/gold", 0),
              "base_rejections": summaries["controls"]["counts"].get(key + "/base", 0)}
             for key in assets["tasks"]]
    if len(tasks) != 10 or any(t["gold_passes"] != 3 or t["base_rejections"] != 3 for t in tasks):
        raise ValueError("final three-repeat ten-task requirement missing")
    value = {"schema_version": 2, "version": "balatro-branch-v2", "wrapper_matrix_passed": True,
        "adapter_sha256": adapter_identity(), "source_freeze_sha256": file_sha(args.freeze),
        "assets_sha256": assets_sha, "environment": assets["environment"], "harness": assets["harness"],
        "engine_validated_count": 10, "packaged_count": 10, "calibrated_count": 0,
        "formal_integration_status": "not_implemented", "security_mode": "honest",
        "workflow_count": sum(v["workflow_count"] for v in summaries.values()) + len(reviewed),
        "native_process_count": len(run_ids), "required_check_outcomes": checks,
        "tasks": tasks, **summaries, "new_reviewed_byte_identities": reviewed,
        "not_new_semantic_coverage": True,
        "whole_repository_gates": "reported_separately; not implied by native success"}
    json_write_new(args.output, value)
    print(json.dumps({key: value[key] for key in ("wrapper_matrix_passed", "workflow_count",
                                               "native_process_count", "required_check_outcomes")}))


if __name__ == "__main__":
    main()
