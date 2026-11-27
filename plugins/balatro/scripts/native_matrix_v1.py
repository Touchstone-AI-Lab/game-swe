"""Operator-only serial controls through the installed Rhenium CLI, never a model."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rhenium_balatro.bridge import child_environment, load_binding
from rhenium_balatro.catalog import BalatroTask, load_catalog
from rhenium_balatro.files import read_file
from rhenium_balatro.native_assets import adapter_identity, file_sha, json_write_new, verified_assets
from rhenium_balatro.submission import snapshot

TARGETED = {
    "growth-v2": "M03-per-hand",
    "reversible-hand-limit-v1": "M02-no-remove",
    "seeded-effect-stream-v1": "M03-score-advances",
    "bounded-generator-v2": "M02-fixed-release",
    "deck-removal-consistency-v2": "M02-area-only",
    "live-joker-adjacency-v2": "M02-stale-index",
    "isolated-card-wear-v2": "M04-additive-refresh",
    "durable-charge-v2": "M06-display-only",
    "shop-price-coherence-v2": "M04-stale-accepted",
    "pack-choice-commit-v2": "M07-repeat-commit",
}
ALTERNATIVES = {"growth-v2": "alternative", "durable-charge-v2": "gold-journal",
                "shop-price-coherence-v2": "gold-ledger", "pack-choice-commit-v2": "gold-journal"}


def matrix(kind: str, keys: list[str]) -> list[tuple[str, str, int]]:
    if kind == "pilot":
        return [("growth-v2", role, 1) for role in ("gold", "base")]
    if kind == "controls":
        return [(key, role, repetition) for repetition in range(1, 4)
                for key in keys for role in ("gold", "base")]
    return [(key, role, 1) for key, role in (*TARGETED.items(), *ALTERNATIVES.items())]


def cli(arguments: list[str], repository: Path, environment: dict[str, str],
        directory: Path, prefix: str) -> tuple[int, dict[str, Any]]:
    command = [sys.executable, "-I", "-B", "-m", "rhenium.cli", *arguments]
    json_write_new(directory / (prefix + "-command.json"), command)
    with (directory / (prefix + ".json")).open("xb") as out, (
        directory / (prefix + ".stderr")
    ).open("xb") as err:
        result = subprocess.run(command, cwd=repository, env=environment, stdout=out, stderr=err)
    try:
        value = json.loads((directory / (prefix + ".json")).read_bytes())
    except (ValueError, OSError):
        value = {}
    return result.returncode, value


def run(args: argparse.Namespace) -> None:
    repository, evidence = args.repository.resolve(), args.evidence.resolve()
    state = args.state.resolve()
    pack = repository / "benchmarks/balatro"
    native_state = state / "packs/balatro/core"
    binding = load_binding(native_state)
    assets = verified_assets(pack, binding["assets_sha256"])
    catalog = load_catalog(pack, "catalog.json")
    tasks = {task.id: task for task in catalog.tasks}
    plan = matrix(args.matrix, list(assets["tasks"]))
    args.attempts.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=False)
    json_write_new(evidence / "plan.json", {"schema_version": 1, "matrix": args.matrix,
        "adapter_sha256": adapter_identity(), "assets_sha256": binding["assets_sha256"],
        "script_sha256": file_sha(Path(__file__)), "flows": plan,
        "expected_native_processes": sum(assets["tasks"][k]["expected_processes"] for k, _, _ in plan),
        "started_utc": datetime.now(UTC).isoformat(), "security_mode": "honest",
        "source_review_scope": "approved-honest-maintenance-v1"})
    records: list[dict[str, Any]] = []
    for number, (key, role, repetition) in enumerate(plan, 1):
        if (native_state / "native-halt.json").exists():
            raise RuntimeError("native halt marker present; no next control started")
        if adapter_identity() != binding["adapter_sha256"]:
            raise RuntimeError("adapter changed during matrix")
        directory = evidence / f"flow-{number:03d}"
        directory.mkdir()
        attempt = args.attempts / uuid.uuid4().hex
        selected = assets["controls"][key][role]
        environment = child_environment(directory)
        environment.update(RHENIUM_ROOT=str(repository), RHENIUM_STATE_DIR=str(state),
            RHENIUM_CACHE_DIR=str(state.parent / "cache"),
            RHENIUM_DATABASE_URL="sqlite:///" + str(state / "state.sqlite"),
            RHENIUM_BENCHMARK_PATH=str(pack))
        started = time.monotonic()
        json_write_new(directory / "started.json", {"task": key, "role": role,
            "repetition": repetition, "attempt": str(attempt),
            "candidate_sha256": selected["candidate_sha256"],
            "submission_sha256": selected["seal_sha256"], "environment_keys": sorted(environment)})
        print(json.dumps({"event": "started", "flow": number, "total": len(plan),
                          "task": key, "role": role, "repetition": repetition}), flush=True)
        code, prepared = cli(["prepare-attempt", "balatro/core/" + key, str(attempt),
            "--score-command", str(repository / "scripts/score-exam.ps1"), "--mode", "strict"],
            repository, environment, directory, "prepare")
        if code != 0 or not prepared.get("attemptId"):
            raise RuntimeError("platform preparation failed; no evaluation started")
        task = tasks[key]
        assert isinstance(task, BalatroTask)
        source = pack / "private/native-v1" / selected["source"]
        for name in task.editable_files:
            relative = name.removeprefix("starter/")
            (attempt / name).write_bytes(read_file(source, relative))
        snapshot(attempt, task)  # Immutable fields and complete declared file closure.
        operations = native_state / "operations"
        prior = {p.name for p in operations.iterdir()}
        code, public = cli(["run-attempt", str(attempt), "--profile", "full", "--security-mode", "honest"],
                           repository, environment, directory, "run")
        new = [p for p in operations.iterdir() if p.name not in prior]
        operator_match = False
        raw: dict[str, Any] = {}
        private_paths: list[Path] = []
        if len(new) == 1 and (new[0] / "response.json").is_file():
            operation = new[0]
            raw = json.loads((operation / "response.json").read_bytes())["result"].get("evaluation", {})
            checks = {c["id"]: c["passed"] for c in raw.get("checks", [])}
            result = public.get("result", {})
            operator_match = (result.get("complete") is True
                and result.get("passed") is selected["expected_pass"]
                and result.get("submissionSha256") == selected["seal_sha256"]
                and code == (0 if selected["expected_pass"] else 1)
                and all(checks.get(c) is False for c in selected["must_fail"])
                and all(checks.get(c) is True for c in selected["must_pass"]))
            private_paths = [p for p in operation.iterdir() if p.is_file()]
        record = {"flow": number, "task": key, "role": role, "repetition": repetition,
            "platform_run_id": public.get("id"), "public_result": public.get("result"),
            "operator_expectations_match": operator_match, "cli_exit_code": code,
            "elapsed_seconds": time.monotonic() - started,
            "native_processes": len(raw.get("processes", [])),
            "evidence_files": {str(p): file_sha(p) for p in private_paths},
            "flow_files": {p.name: file_sha(p) for p in directory.iterdir() if p.is_file()}}
        json_write_new(directory / "record.json", record)
        records.append(record)
        progress = {"completed_flows": len(records), "expected_flows": len(plan),
                    "native_processes": sum(r["native_processes"] for r in records),
                    "all_expectations_match": all(r["operator_expectations_match"] for r in records),
                    "records": [{"file": f"flow-{r['flow']:03d}/record.json",
                                 "sha256": file_sha(evidence / f"flow-{r['flow']:03d}/record.json")}
                                for r in records]}
        # New version each step; immutable evidence is never overwritten.
        json_write_new(evidence / f"progress-{number:03d}.json", progress)
        print(json.dumps({"event": "finished", **{k: record[k] for k in (
            "flow", "task", "role", "operator_expectations_match", "elapsed_seconds", "native_processes")}}),
            flush=True)
        if not operator_match:
            raise RuntimeError("control incomplete or mismatched; later controls not executed")
    json_write_new(evidence / "complete.json", progress)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True, help="Platform hub state root")
    parser.add_argument("--evidence", type=Path, required=True, help="New private evidence directory")
    parser.add_argument("--attempts", type=Path, required=True, help="Outside the private checkout")
    parser.add_argument("--matrix", choices=("pilot", "controls", "targeted"), required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
