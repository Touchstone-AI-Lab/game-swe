"""Recheck immutable platform evidence and emit an operator-safe native summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from native_matrix_v1 import matrix
from rhenium_balatro.evaluator import classify_native
from rhenium_balatro.native_assets import ASSETS, adapter_identity, file_sha, json_write_new, verified_assets
from rhenium_balatro.protocol import decode_response


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def inspect(directory: Path, kind: str, assets: dict[str, Any], assets_sha: str) -> dict[str, Any]:
    plan, completion = read(directory / "plan.json"), read(directory / "complete.json")
    expected = matrix(kind, list(assets["tasks"]))
    if (plan["flows"] != [list(item) for item in expected] or plan["adapter_sha256"] != adapter_identity()
            or plan["assets_sha256"] != assets_sha
            or plan["script_sha256"] != file_sha(Path(__file__).with_name("native_matrix_v1.py"))
            or completion["completed_flows"] != len(expected)
            or len(completion["records"]) != len(expected)):
        raise ValueError("matrix identity or completeness mismatch")
    counts: Counter[str] = Counter()
    flows = []
    run_ids: set[str] = set()
    for number, (key, role, repetition) in enumerate(expected, 1):
        record_file = directory / f"flow-{number:03d}/record.json"
        binding = completion["records"][number - 1]
        if (binding["file"] != f"flow-{number:03d}/record.json"
                or file_sha(record_file) != binding["sha256"]):
            raise ValueError("flow record changed")
        record = read(record_file)
        if [record["task"], record["role"], record["repetition"]] != [key, role, repetition]:
            raise ValueError("control identity mismatch")
        for name, expected_hash in record["flow_files"].items():
            if file_sha(record_file.parent / name) != expected_hash:
                raise ValueError("CLI evidence changed")
        for name, expected_hash in record["evidence_files"].items():
            if file_sha(Path(name)) != expected_hash:
                raise ValueError("private operation evidence changed")
        paths = {Path(name).name: Path(name) for name in record["evidence_files"]}
        request, supervisor = read(paths["request.json"]), read(paths["supervisor.json"])
        selected = assets["controls"][key][role]
        value = decode_response(paths["response.json"].read_bytes(), request["request_id"],
                                request["nonce"], selected["seal_sha256"])
        result = classify_native(value, assets, key, selected["seal_sha256"])
        checks = {c["id"]: c["passed"] for c in value["evaluation"]["checks"]}
        public = record["public_result"]
        if (request["operation"] != "evaluate" or request["task"] != key
                or request["submission_sha256"] != selected["seal_sha256"]
                or result["complete"] is not True or result["passed"] is not selected["expected_pass"]
                or public["submissionSha256"] != selected["seal_sha256"]
                or any(public[k] != result[k]
                       for k in ("complete", "passed", "score", "category", "reason", "checks"))
                or record["cli_exit_code"] != (0 if selected["expected_pass"] else 1)
                or not all(checks.get(c) is False for c in selected["must_fail"])
                or not all(checks.get(c) is True for c in selected["must_pass"])
                or supervisor["assigned_to_owned_job"] is not True
                or supervisor["forced"] is not False or supervisor["cancelled"] is not False
                or supervisor["exit_code"] != 0 or supervisor["active_before_job_close"] != 0):
            raise ValueError("native result/control/cleanup mismatch")
        processes = value["evaluation"]["processes"]
        for process in processes:
            if process["run_id"] in run_ids:
                raise ValueError("native process evidence reused")
            run_ids.add(process["run_id"])
        counts[key + "/" + role] += 1
        flows.append({"task": key, "role": role, "repetition": repetition,
            "complete": True, "passed": result["passed"], "category": result["category"],
            "submission_sha256": selected["seal_sha256"], "native_processes": len(processes),
            "elapsed_seconds": record["elapsed_seconds"], "record_sha256": file_sha(record_file)})
    return {"matrix": kind, "flows": flows, "workflow_count": len(flows),
            "native_processes": len(run_ids), "counts": dict(counts),
            "elapsed_seconds": sum(f["elapsed_seconds"] for f in flows),
            "completion_sha256": file_sha(directory / "complete.json"), "all_controls_match": True}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--targeted", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = read(args.freeze)
    for name, expected in frozen["files"].items():
        if file_sha(args.repository / name) != expected:
            raise ValueError("final frozen platform source changed: " + name)
    pack = args.repository / "benchmarks/balatro"
    assets_sha = file_sha(pack / ASSETS)
    assets = verified_assets(pack, assets_sha)
    controls = inspect(args.controls, "controls", assets, assets_sha)
    targeted = inspect(args.targeted, "targeted", assets, assets_sha)
    tasks = [{"task": key, "gold_complete_passes": controls["counts"].get(key + "/gold", 0),
              "base_complete_rejections": controls["counts"].get(key + "/base", 0)}
             for key in assets["tasks"]]
    if len(tasks) != 10 or any(t["gold_complete_passes"] != 3 or t["base_complete_rejections"] != 3
                             for t in tasks):
        raise ValueError("ten-task three-repeat requirement missing")
    result = {"schema_version": 1, "version": "balatro-native-maintenance-v1",
        "adapter_sha256": adapter_identity(), "source_freeze_sha256": file_sha(args.freeze),
        "assets_sha256": assets_sha, "environment": assets["environment"], "harness": assets["harness"],
        "security_mode": "honest", "native_matrix_passed": True, "engine_validated_count": 10,
        "calibrated_count": 0, "formal_integration_status": "not_implemented",
        "arbitrary_submissions_supported": False, "untrusted_host_supported": False,
        "tasks": tasks, "controls": controls, "targeted": targeted,
        "whole_repository_checks": "reported_separately_not_implied_by_engine_success"}
    json_write_new(args.output, result)
    print(json.dumps({"native_matrix_passed": True, "engine_validated_count": 10,
                      "workflows": controls["workflow_count"] + targeted["workflow_count"]}))


if __name__ == "__main__":
    main()
