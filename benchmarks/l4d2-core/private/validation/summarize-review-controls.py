"""Publish sanitized receipts only after the revised maintenance controls agree."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parents[1]
spec = importlib.util.spec_from_file_location("review_runner", HERE / "run-review-control.py")
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

REQUIRED = {
    "l4d2-competitive-release-regressions-easy": {
        "gold": True,
        "nop": False,
        "empty-timestamp-rewrite": False,
    },
    "l4d2-left4dhooks-api-regressions-medium": {"gold": True, "nop": False, "equivalent-long-docs": True},
    "l4d2-infected-bots-release-regressions-medium": {
        "gold": True,
        "nop": False,
        "four-second-replacement": False,
    },
    "l4d2-mutant-tanks-release-regressions-hard": {
        "gold": True,
        "nop": False,
        "deferred-half-second": True,
        "deferred-too-late": False,
    },
    "l4d2-vslib-scheduler-persistence-hard": {
        "gold": True,
        "nop": False,
        "alternative": True,
        "reject-opaque-payloads": False,
    },
    "l4d2-confogl-cvar-transactions-hard": {
        "gold": True,
        "nop": False,
        "alternative": True,
        "minus-bounded-string": False,
    },
    "l4d2-library-map-tank-state-hard": {
        "gold": True,
        "nop": False,
        "alternative": True,
        "minus-syntax-validation": False,
    },
}
TARGETS = {
    "empty-timestamp-rewrite": "incap_empty_clip_leaves_reload_unblocked",
    "four-second-replacement": "initial_timer_not_overwritten_by_normal_delay",
    "reject-opaque-payloads": "timer-moresi-team-refresh",
    "minus-bounded-string": "bounded-string-finite-writeback",
    "minus-syntax-validation": "failed-reload-keeps-image",
    "deferred-too-late": "hypno_respawn_uses_new_shield_entref",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_roots", type=Path, nargs="+")
    args = parser.parse_args()
    catalog = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    counts = {t["id"]: t["expected_cases"] for t in catalog["tasks"]}
    found = {}
    current_hashes = {}
    for root in args.evidence_roots:
        for path in sorted(root.glob("*/receipt.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("task") not in REQUIRED:
                continue
            # Only publish evidence for exactly the current authored inputs.
            task = PACK / "private/harbor" / record["task"]
            expected_components = {
                "instruction.md",
                "task.toml",
                "environment",
                "tests",
                "solution",
                "validation/case-contracts.tsv",
            }
            assert set(record["component_hashes"]) == expected_components, path
            if record["task"] not in current_hashes:
                current_hashes[record["task"]] = {
                    name: runner.digest(task / name) for name in expected_components
                }
            if current_hashes[record["task"]] != record["component_hashes"]:
                continue
            assert record["tests_hash"] == record["component_hashes"]["tests"], path
            # Early receipts predate logs_copied. Verify the retained bytes,
            # rather than guessing that an omitted metadata flag means success.
            assert record["server_log_hashes"], path
            for name, digest in record["server_log_hashes"].items():
                log = path.parent / "logs" / name
                assert hashlib.sha256(log.read_bytes()).hexdigest() == digest, log
            record.setdefault("logs_copied", True)
            record["retained_server_log_hashes_verified"] = True
            record["evidence_directory"] = path.parent.name
            record.setdefault("profile", "full")
            found[record["task"], record["candidate"]] = record
    output = []
    for task_id, candidates in REQUIRED.items():
        task = PACK / "private/harbor" / task_id
        with (task / "validation/case-contracts.tsv").open(encoding="utf-8", newline="") as stream:
            all_names = {row["case"] for row in csv.DictReader(stream, delimiter="\t")}
        records = []
        for candidate, should_pass in candidates.items():
            record = found[task_id, candidate]
            full = record["profile"] == "full"
            assert not record.get("timed_out", False), (task_id, candidate, "timeout")
            assert record["logs_copied"] and record["server_log_hashes"], (
                task_id,
                candidate,
                "missing engine logs",
            )
            expected = counts[task_id] if full else 7
            assert record["total"] == expected, (task_id, candidate, "missing verdicts")
            assert len({c["case"] for c in record["cases"]}) == expected
            expected_names = all_names if full else {name for name in all_names if name.startswith("hypno_")}
            assert {c["case"] for c in record["cases"]} == expected_names
            assert all(c["status"] in ("PASS", "FAIL") for c in record["cases"])
            assert record["passed"] == sum(c["status"] == "PASS" for c in record["cases"])
            passed = record["exit_code"] == 0 and record["passed"] == expected
            assert passed == should_pass, (task_id, candidate, "unexpected verdict")
            if not should_pass:
                assert record["exit_code"] == 1, (task_id, candidate, "infrastructure failure")
            failures = {c["case"] for c in record["cases"] if c["status"] == "FAIL"}
            if candidate in TARGETS:
                assert TARGETS[candidate] in failures, (task_id, candidate, failures)
            if candidate == "minus-syntax-validation":
                assert failures == {"failed-reload-keeps-image"}, failures
            record["expected_outcome_confirmed"] = True
            record["expected_cases_in_selected_scope"] = expected
            record["emitted_exact_verdict_count"] = True
            records.append(record)
        task = PACK / "private/harbor" / task_id
        (task / "validation/revision-controls.json").write_text(
            json.dumps(
                {"scope": "2026-09-21 maintainer controls, not model calibration", "records": records},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        output.extend(records)
    (PACK / "validation/review-controls.json").write_text(
        json.dumps({"pack_version": catalog["version"], "records": output}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Published {len(output)} verified maintenance controls across {len(REQUIRED)} revised tasks")


if __name__ == "__main__":
    main()
