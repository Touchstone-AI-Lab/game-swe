from __future__ import annotations

from pathlib import Path
from typing import Any

from rhenium_study import adjudicate, aggregate

MARKER = "submission build failed (see build-submission.log)"
HARNESS = "harness build failed (verifier bug, not the submission)"


def _record(outcome: str = "unattributed", runs: tuple[str, ...] = ("run-a", "run-b")) -> dict[str, Any]:
    return {
        "attempt_id": "m--t--r1",
        "task": "stardew-valley/core/t",
        "outcome": outcome,
        "auditedOutcome": outcome,
        "complete": False,
        "cases": {"check:submission-shape": "P", "case:x": "U"},
        "executions": [{"index": i + 1, "runId": run} for i, run in enumerate(runs)],
    }


def _log(state: Path, run: str, text: str) -> None:
    directory = state / "runs" / run
    directory.mkdir(parents=True)
    (directory / "runtime.log").write_text(text, encoding="utf-8")


def test_build_failure_needs_the_marker_in_every_execution(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", f"network=none\n{MARKER}\n")
    _log(tmp_path, "run-b", "network=none\n")
    assert adjudicate.decide(_record(), tmp_path) is None
    (tmp_path / "runs" / "run-b" / "runtime.log").write_text(f"{MARKER}\n", encoding="utf-8")
    decision = adjudicate.decide(_record(), tmp_path)
    assert decision is not None
    assert (decision["from"], decision["to"]) == ("unattributed", "failed")
    assert decision["evidence"]["runIds"] == ["run-a", "run-b"]


def test_verifier_fault_and_other_outcomes_are_never_adjudicated(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", f"{MARKER}\n{HARNESS}\n")
    assert adjudicate.decide(_record(runs=("run-a",)), tmp_path) is None
    (tmp_path / "runs" / "run-a" / "runtime.log").write_text(f"{MARKER}\n", encoding="utf-8")
    assert adjudicate.decide(_record("invalid", ("run-a",)), tmp_path) is None
    assert adjudicate.decide(_record(runs=("../run-a",)), tmp_path) is None
    other = _record(runs=("run-a",)) | {"task": "left-4-dead-2/core/t"}
    assert adjudicate.decide(other, tmp_path) is None
    quoted = tmp_path / "runs" / "run-a" / "runtime.log"
    quoted.write_text(f"error: '{MARKER}' printed by the submission\n", encoding="utf-8")
    assert adjudicate.decide(_record(runs=("run-a",)), tmp_path) is None
    quoted.write_text(f"{MARKER}\n", encoding="utf-8")
    ran = _record(runs=("run-a",))
    ran["cases"] = {"check:submission-shape": "P", "case:x": "P", "case:y": "U"}
    assert adjudicate.decide(ran, tmp_path) is None  # the game ran, so this was no build failure


def test_l4d2_compile_failure_is_separated_from_an_invalid_environment(tmp_path: Path) -> None:
    compile_line = "SUBMISSION_FAILED: SourcePawn compile failed for plugin.sp:"
    record = _record(runs=("run-a",)) | {"task": "left-4-dead-2/core/t"}
    _log(tmp_path, "run-a", f"{compile_line}\nplugin.sp(3) : error 017: undefined symbol\n")
    decision = adjudicate.decide(record, tmp_path)
    assert decision is not None and decision["rule"] == "l4d2-submission-compile-failure"
    log = tmp_path / "runs" / "run-a" / "runtime.log"
    log.write_text("SUBMISSION_FAILED: one or more private behavior cases failed\n", encoding="utf-8")
    assert adjudicate.decide(record, tmp_path) is None
    log.write_text(f"{compile_line}\nINVALID_ENVIRONMENT: port in use\n", encoding="utf-8")
    assert adjudicate.decide(record, tmp_path) is None


def test_rimworld_submission_build_failure_is_separated_from_a_harness_failure(tmp_path: Path) -> None:
    # The lines rhenium_rimworld.evaluator.build_failure_log writes for a failed build.
    submission = "RimWorld submission build failed: the submitted sources did not compile"
    harness = "RimWorld verifier harness build failed (verifier bug, not the submission)"
    record = _record(runs=("run-a",)) | {"task": "rimworld/core/t"}
    _log(tmp_path, "run-a", f"{submission}; private evidence was recorded\n")
    decision = adjudicate.decide(record, tmp_path)
    assert decision is not None and decision["rule"] == "rimworld-submission-build-failure"
    log = tmp_path / "runs" / "run-a" / "runtime.log"
    for text in (f"{harness}; private evidence was recorded\n",
                 "RimWorld build failed; private evidence was recorded\n"):
        log.write_text(text, encoding="utf-8")
        assert adjudicate.decide(record, tmp_path) is None


def test_apply_keeps_the_native_outcome_and_the_case_observations(tmp_path: Path) -> None:
    _log(tmp_path, "run-a", f"{MARKER}\n")
    record = _record(runs=("run-a",))
    decisions = adjudicate.adjudicate([record], tmp_path)
    adjudicate.write(tmp_path, decisions)
    (applied,) = adjudicate.apply([record], adjudicate.load(tmp_path))
    assert applied["outcome"] == "failed"
    assert applied["auditedOutcome"] == "failed"
    assert applied["nativeOutcome"] == "unattributed"
    assert applied["cases"] == record["cases"]
    assert record["outcome"] == "unattributed"
    assert aggregate.environment_valid(applied)
    assert not aggregate.environment_valid(record)


def test_stale_decisions_do_not_override_a_changed_record(tmp_path: Path) -> None:
    decision = {"attempt_id": "m--t--r1", "rule": "r", "from": "unattributed", "to": "failed"}
    (unchanged,) = adjudicate.apply([_record("resolved")], [decision])
    assert unchanged["outcome"] == "resolved"
    assert "nativeOutcome" not in unchanged


def test_manual_decisions_need_an_open_attempt_and_a_rationale(tmp_path: Path) -> None:
    import json

    import pytest

    entry = {
        "attempt_id": "m--t--r1",
        "to": "failed",
        "rationale": "script error in the submission",
        "reviewer": "r",
    }
    (tmp_path / adjudicate.MANUAL_FILE).write_text(json.dumps([entry]), encoding="utf-8")
    (decision,) = adjudicate.manual_decisions(tmp_path, [_record()])
    assert decision["rule"] == "manual-review"
    (applied,) = adjudicate.apply([_record()], [decision])
    assert applied["outcome"] == "failed" and "script error" in applied["outcomeReason"]
    with pytest.raises(ValueError):
        adjudicate.manual_decisions(tmp_path, [_record("resolved")])
    (tmp_path / adjudicate.MANUAL_FILE).write_text(json.dumps([entry | {"rationale": " "}]), encoding="utf-8")
    with pytest.raises(ValueError):
        adjudicate.manual_decisions(tmp_path, [_record()])
