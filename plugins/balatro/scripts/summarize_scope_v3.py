"""Verify the amended 22-workflow scope without relabelling the old partial matrix."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from native_matrix_v1 import matrix
from native_scope_v3 import remaining
from rhenium_balatro.evaluator import classify_native
from rhenium_balatro.native_assets import ASSETS, adapter_identity, file_sha, json_write_new, verified_assets
from rhenium_balatro.review import candidate_identity, candidate_reviewed, review_identity
from summarize_branch_v2 import read, verify_operation


def validate_coverage(flows: list[dict[str, Any]], keys: list[str]) -> None:
    actual = Counter((row["task"], row["role"]) for row in flows)
    expected = Counter((key, role) for key in keys for role in ("gold", "base"))
    if len(keys) != 10 or len(set(keys)) != 10 or actual != expected:
        raise ValueError("exactly one full gold/base flow per frozen task required")


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    for name in ("repository", "initial-batch", "batch", "freeze", "orchestration-freeze", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    repo, initial, batch = args.repository.resolve(), args.initial_batch.resolve(), args.batch.resolve()
    for freeze in (args.freeze, args.orchestration_freeze):
        for name, expected in read(freeze)["files"].items():
            if file_sha(repo / name) != expected:
                raise ValueError("frozen source changed: " + name)
    pack, state = repo / "benchmarks/balatro", batch / "hub/packs/balatro/core"
    assets_sha = file_sha(pack / ASSETS)
    assets = verified_assets(pack, assets_sha)
    scope = read(batch / "scope-v3.json")
    plan = [("growth-v2", role, 1) for role in ("gold", "base")] + remaining(list(assets["tasks"]))
    if (scope["flows"] != [list(v) for v in plan[2:]]
            or scope["adapter_sha256"] != adapter_identity()
            or scope["driver_sha256"] != file_sha(Path(__file__).with_name("native_scope_v3.py"))):
        raise ValueError("amended scope identity mismatch")
    prefix = read(initial / "controls/progress-002.json")
    rest = read(batch / "controls/complete.json")
    if (prefix["completed_flows"] != 2 or rest["completed_flows"] != 18
            or len(prefix["records"]) != 2 or len(rest["records"]) != 18
            or (initial / "controls/complete.json").exists()):
        raise ValueError("partial/complete matrix boundaries mismatch")
    if read(initial / "hub/packs/balatro/core/native-halt.json")["reason"] != (
        "operator_scope_replan_after_current_flow"
    ):
        raise ValueError("original scheduling stop not preserved")
    for folder, expected_plan in ((initial, [list(v) for v in matrix("controls", list(assets["tasks"]))]),
                                  (batch, [list(v) for v in plan[2:]])):
        recorded = read(folder / "controls/plan.json")
        if (recorded["adapter_sha256"] != adapter_identity() or recorded["assets_sha256"] != assets_sha
                or recorded["flows"] != expected_plan):
            raise ValueError("matrix plan mismatch")
    paths = [(initial / "controls" / b["file"], b["sha256"]) for b in prefix["records"]]
    paths += [(batch / "controls" / b["file"], b["sha256"]) for b in rest["records"]]
    wrapper = repo / "scripts/score-exam.ps1"
    wrapper_args = ["-NoProfile", "-NonInteractive", "-File", str(wrapper)]
    processes, flows, reviewed = [], [], []
    checks = 0
    record_bindings = {}
    for number, ((path, digest), (key, role, repetition)) in enumerate(zip(paths, plan, strict=True)):
        if file_sha(path) != digest:
            raise ValueError("control record changed")
        record = read(path)
        if (record["task"], record["role"], record["repetition"]) != (key, role, repetition):
            raise ValueError("control identity mismatch")
        for name, expected in record["flow_files"].items():
            if file_sha(path.parent / name) != expected:
                raise ValueError("CLI evidence changed")
        entry = read((initial if number < 2 else batch) / "controls-entry-v2.json")
        command = read(path.parent / "run-command.json")
        if (entry["driver_sha256"] != file_sha(Path(__file__).with_name("native_matrix_v2.py"))
                or entry["wrapper_sha256"] != file_sha(wrapper)
                or command[1:5] != wrapper_args
                or command[6:] != ["-Profile", "full", "-SecurityMode", "honest"]
                or file_sha(Path(command[0])) != entry["powershell_sha256"]):
            raise ValueError("actual wrapper identity mismatch")
        request, result = verify_operation(record)
        selected = assets["controls"][key][role]
        seal, candidate = candidate_identity(Path(request["candidate"]))
        actual = classify_native(result, assets, key, seal, candidate)
        outcomes = {c["id"]: c["passed"] for c in result["evaluation"]["checks"]}
        public = record["public_result"]
        if (request["operation"] != "evaluate" or request["task"] != key
                or request["submission_sha256"] != seal
                or (seal, candidate) != (selected["seal_sha256"], selected["candidate_sha256"])
                or actual["complete"] is not True or actual["passed"] is not selected["expected_pass"]
                or public["submissionSha256"] != seal
                or any(public[k] != actual[k] for k in ("complete", "passed", "score", "category", "checks"))
                or record["cli_exit_code"] != (0 if role == "gold" else 1)
                or not all(outcomes[c] is False for c in selected["must_fail"])
                or not all(outcomes[c] is True for c in selected["must_pass"])):
            raise ValueError("control is incomplete or behavior differs")
        if key == "durable-charge-v2":
            review_path = state / "reviews" / f"{key}-{seal}.json"
            expected = review_identity(assets, assets_sha, key, seal, candidate)
            review = read(review_path)
            if (file_sha(review_path) != scope["durable_explicit_reviews"][role]
                    or {k: review.get(k) for k in expected} != expected
                    or not candidate_reviewed(state, assets, assets_sha, key, seal, candidate)):
                raise ValueError("durable explicit review not proven")
        processes.extend(result["evaluation"]["processes"])
        checks += len(result["evaluation"]["checks"])
        record_bindings[path.relative_to(repo).as_posix()] = digest
        flows.append({"task": key, "role": role, "complete": True, "passed": actual["passed"],
                      "submission_sha256": seal, "record_sha256": digest})
    validate_coverage(flows, list(assets["tasks"]))
    probe_plan = read(batch / "reviewed/plan.json")
    if (probe_plan["script_sha256"] != file_sha(Path(__file__).with_name("reviewed_submission_probe_v2.py"))
            or probe_plan["adapter_sha256"] != adapter_identity()
            or probe_plan["wrapper_sha256"] != file_sha(wrapper)):
        raise ValueError("reviewed probe source mismatch")
    completion = read(batch / "reviewed/complete.json")
    if completion["completed_flows"] != 2 or len(completion["records"]) != 2:
        raise ValueError("reviewed probes incomplete")
    for role, binding in zip(("gold", "base"), completion["records"], strict=True):
        path = batch / "reviewed" / binding["file"]
        if file_sha(path) != binding["sha256"]:
            raise ValueError("review probe record changed")
        record = read(path)
        for name, expected in record["flow_files"].items():
            if file_sha(path.parent / name) != expected:
                raise ValueError("review CLI evidence changed")
        request, result = verify_operation(record)
        seal, candidate = candidate_identity(Path(request["candidate"]))
        actual = classify_native(result, assets, "growth-v2", seal, candidate)
        public = read(path.parent / "score.json")["result"]
        command = read(path.parent / "score-command.json")
        selected = assets["controls"]["growth-v2"][role]
        outcomes = {c["id"]: c["passed"] for c in result["evaluation"]["checks"]}
        if (record["role"] != role or request["task"] != "growth-v2" or request["operation"] != "evaluate"
                or (seal, candidate) != (record["submission_sha256"], record["candidate_sha256"])
                or seal in {c["seal_sha256"] for c in assets["controls"]["growth-v2"].values()}
                or request["submission_sha256"] != seal or record["initially_unreviewed"] is not True
                or file_sha(state / "reviews" / f"growth-v2-{seal}.json") != record["review_record_sha256"]
                or not candidate_reviewed(state, assets, assets_sha, "growth-v2", seal, candidate)
                or actual["complete"] is not True or actual["passed"] is not selected["expected_pass"]
                or public["submissionSha256"] != seal
                or record["score_exit_code"] != (0 if role == "gold" else 1)
                or command[1:5] != wrapper_args
                or command[6:] != ["-Profile", "full", "-SecurityMode", "honest"]
                or any(public[k] != actual[k] for k in ("complete", "passed", "score", "category", "checks"))
                or not all(outcomes[c] is False for c in selected["must_fail"])
                or not all(outcomes[c] is True for c in selected["must_pass"])):
            raise ValueError("new-byte review or result not proven")
        processes.extend(result["evaluation"]["processes"])
        checks += len(result["evaluation"]["checks"])
        record_bindings[path.relative_to(repo).as_posix()] = file_sha(path)
        reviewed.append({"role": role, "complete": True, "passed": actual["passed"],
                         "submission_sha256": seal, "candidate_sha256": candidate,
                         "record_sha256": file_sha(path)})
    if len(processes) != 58 or len({p["run_id"] for p in processes}) != 58:
        raise ValueError("distinct complete native lifecycle count mismatch")
    json_write_new(args.output, {
        "schema_version": 3, "version": "balatro-branch-v2-scope-v3", "wrapper_matrix_passed": True,
        "adapter_sha256": adapter_identity(), "source_freeze_sha256": file_sha(args.freeze),
        "orchestration_freeze_sha256": file_sha(args.orchestration_freeze), "assets_sha256": assets_sha,
        "environment": assets["environment"], "harness": assets["harness"],
        "workflow_count": len(flows) + len(reviewed), "native_process_count": len(processes),
        "required_check_outcomes": checks, "engine_validated_count": 10, "packaged_count": 10,
        "calibrated_count": 0, "formal_integration_status": "not_implemented", "security_mode": "honest",
        "tasks": [{"task": k, "gold_passes": 1, "base_rejections": 1} for k in assets["tasks"]],
        "controls": flows, "new_reviewed_byte_identities": reviewed, "record_bindings": record_bindings,
        "superseded_batch_status": "partial operator scope stop; not candidate/environment failure",
        "not_rerun_on_current_adapter": "repetitions 2/3; ten mutations and four alternatives",
        "whole_repository_gates": "reported separately; not implied by native success",
    })
    print("Verified 22 complete wrapper workflows and 58 unique native lifecycles.")


if __name__ == "__main__":
    main()
