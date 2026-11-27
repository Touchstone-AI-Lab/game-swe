from __future__ import annotations

from typing import Any

import pytest
from rhenium_study import classify
from rhenium_study.aggregate import summarize
from rhenium_study.usage import token_usage

COMPLETE_PASS = {"result": {"complete": True, "passed": True}, "evaluatorError": None}


@pytest.mark.parametrize(
    "execution,table,outcome",
    [
        (COMPLETE_PASS, {"case:a": "P"}, "resolved"),
        ({"result": {"complete": True, "passed": False}, "evaluatorError": None}, {"case:a": "F"}, "failed"),
        ({"result": {}, "evaluatorError": "RuntimeError: runtime not prepared"}, {}, "invalid"),
        (
            {"result": {"complete": False, "runtime": {"status": "unavailable"}}, "evaluatorError": None},
            {"case:a": "U"},
            "invalid",
        ),
        # a rejected source tree is the candidate's failure, not a broken environment
        (
            {"result": {"complete": False, "runtime": {"status": "skipped"}}, "evaluatorError": None},
            {"check:submission-shape": "F", "case:a": "U"},
            "failed",
        ),
        # a requirement failed and the run then stopped: failed, later cases stay unobserved
        (
            {"result": {"complete": False, "runtime": {"status": "incomplete"}}, "evaluatorError": None},
            {"case:a": "P", "case:b": "F", "case:c": "U"},
            "failed",
        ),
        # passes then an unexplained stop: never silently a candidate failure
        (
            {"result": {"complete": False, "runtime": {"status": "incomplete"}}, "evaluatorError": None},
            {"case:a": "P", "case:b": "U"},
            "unattributed",
        ),
    ],
)
def test_execution_classification_follows_the_protocol_order(
    execution: dict[str, Any], table: dict[str, str], outcome: str
) -> None:
    assert classify.classify_execution(execution, table)[0] == outcome


def test_obligation_sets_need_every_valid_pass_and_one_violation_decides() -> None:
    table = {"a": "P", "b": "P", "c": "U", "d": "F"}
    assert classify.set_outcome(["a", "b"], table) == "satisfied"
    assert classify.set_outcome(["a", "c"], table) == "unknown"
    assert classify.set_outcome(["c", "d"], table) == "violated"
    assert classify.set_outcome([], table) == "empty"
    assert classify.joint_outcome("satisfied", "satisfied") == "both"
    assert classify.joint_outcome("satisfied", "violated") == "target-only"
    assert classify.joint_outcome("violated", "satisfied") == "contracts-only"
    assert classify.joint_outcome("violated", "violated") == "neither"
    assert classify.joint_outcome("satisfied", "unknown") == "insufficient-observations"
    # an empty contract set is never a compatibility pass
    assert classify.joint_outcome("satisfied", "empty") == "not-qualified"


def _attempt(
    task: str,
    outcome: str,
    target: str,
    preserved: str,
    kind: str = "repair",
    family: str = "f",
    complete: bool = True,
) -> dict[str, Any]:
    return {
        "model": "m",
        "task": task,
        "kind": kind,
        "sourceFamily": family,
        "outcome": outcome,
        "auditedOutcome": outcome,
        "complete": complete,
        "cases": {},
        "targetOutcome": target,
        "preservedOutcome": preserved,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "calls": 2},
        "generation": {"durationSeconds": 3},
    }


def test_nine_cells_are_task_weighted_over_scheduled_attempts_and_sum_to_one() -> None:
    records = [
        _attempt("g1/p/a", "resolved", "satisfied", "satisfied"),
        _attempt("g1/p/a", "invalid", "unknown", "unknown", complete=False),
        _attempt("g2/p/b", "failed", "satisfied", "violated"),
        _attempt("g2/p/b", "failed", "violated", "satisfied"),
    ]
    view = summarize(records, scheduled=2)["summary"]["m/repair"]
    cells = view["jointCells"]
    assert sum(cells.values()) == pytest.approx(1.0)
    assert cells["satisfied/satisfied"] == pytest.approx(0.25)
    assert cells["satisfied/violated"] == pytest.approx(0.25)
    assert cells["violated/satisfied"] == pytest.approx(0.25)
    assert cells["unknown/unknown"] == pytest.approx(0.25)
    # invalid attempts stay in the primary denominator
    assert view["fullResolution"]["taskBalanced"] == pytest.approx((0.5 + 0.0) / 2)
    assert view["nonResolutionFrequency"]["invalid"] == pytest.approx(0.25)
    # valid-environment view: task a has one eligible attempt, which resolved
    assert view["fullResolution"]["validEnvironment"]["taskBalanced"] == pytest.approx((1.0 + 0.0) / 2)


def test_conditional_rates_keep_the_task_weighting() -> None:
    records = [
        *[_attempt("g/p/a", "failed", "satisfied", "violated") for _ in range(2)],
        _attempt("g/p/b", "resolved", "satisfied", "satisfied"),
        _attempt("g/p/b", "failed", "violated", "satisfied"),
    ]
    conditional = summarize(records, scheduled=2)["summary"]["m/repair"]["conditional"]
    # target success: mean(1.0, 0.5); with violation: mean(1.0, 0.0)
    assert conditional["targetSuccess"] == pytest.approx(0.75)
    assert conditional["observedContractViolation"] == pytest.approx(0.5 / 0.75)
    assert conditional["contractOutcomeUnknown"] == pytest.approx(0.0)
    assert conditional["counts"] == {
        "targetSatisfied": 3,
        "withObservedViolation": 2,
        "withUnknownContracts": 0,
    }


def test_a_missing_attempt_still_counts_in_the_scheduled_denominator() -> None:
    records = [_attempt("g/p/a", "resolved", "satisfied", "satisfied")]
    view = summarize(records, scheduled=3)["summary"]["m/repair"]
    assert view["fullResolution"]["taskBalanced"] == pytest.approx(1 / 3)
    assert sum(view["jointCells"].values()) == pytest.approx(1 / 3)


def test_a_task_without_an_eligible_attempt_makes_the_secondary_view_undefined() -> None:
    records = [
        _attempt("g/p/a", "resolved", "satisfied", "satisfied"),
        _attempt("g/p/b", "invalid", "unknown", "unknown", complete=False),
    ]
    secondary = summarize(records, scheduled=1)["summary"]["m/repair"]["fullResolution"]["validEnvironment"]
    assert secondary == {"taskBalanced": None, "tasksWithoutEligibleAttempt": ["g/p/b"]}


def test_tasks_without_preserved_contracts_only_enter_general_completion() -> None:
    records = [_attempt("g/p/c", "resolved", "satisfied", "empty", kind="construct")]
    view = summarize(records, scheduled=1)["summary"]["m/construct"]
    assert view["qualifiedTasks"] == 0 and view["jointCells"] is None
    assert view["fullResolution"]["taskBalanced"] == pytest.approx(1.0)
    assert view["conditional"]["observedContractViolation"] is None


def test_source_family_sensitivity_reports_each_family_left_out() -> None:
    records = [
        _attempt("g/p/a", "failed", "satisfied", "violated", family="big"),
        _attempt("g/p/b", "failed", "satisfied", "violated", family="big"),
        _attempt("g/p/c", "resolved", "satisfied", "satisfied", family="small"),
    ]
    view = summarize(records, scheduled=1)["summary"]["m/repair"]
    assert view["jointCells"]["satisfied/violated"] == pytest.approx(2 / 3)
    sensitivity = view["sourceFamilySensitivity"]
    assert sensitivity["familyBalancedTargetOnly"] == pytest.approx(0.5)
    assert sensitivity["leaveOneFamilyOut"]["big"]["satisfied/violated"] == pytest.approx(0.0)
    assert sensitivity["leaveOneFamilyOut"]["small"]["satisfied/violated"] == pytest.approx(1.0)


def test_token_usage_sums_provider_counts_and_flags_missing_usage() -> None:
    trajectory = {
        "messages": [
            {"role": "user"},
            {
                "role": "assistant",
                "extra": {
                    "timestamp": 10.0,
                    "response": {
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 20,
                            "completion_tokens_details": {"reasoning_tokens": 8},
                            "prompt_tokens_details": {"cached_tokens": 40},
                        }
                    },
                },
            },
            {"role": "assistant", "extra": {"timestamp": 25.0, "response": {}}},
        ]
    }
    usage = token_usage(trajectory)
    assert (usage["calls"], usage["prompt_tokens"], usage["completion_tokens"]) == (2, 100, 20)
    assert (usage["reasoning_tokens"], usage["cached_prompt_tokens"], usage["calls_without_usage"]) == (
        8,
        40,
        1,
    )
    assert (usage["first_call_at"], usage["last_call_at"]) == (10.0, 25.0)


def test_an_over_constrained_case_neither_fails_nor_blocks_the_audited_outcome() -> None:
    audited = ["case:a", "case:b"]
    # the only failure is a flagged case that is outside the audited list
    assert (
        classify.audited_outcome("failed", audited, {"case:a": "P", "case:b": "P", "case:x": "F"})
        == "resolved"
    )
    assert classify.audited_outcome("failed", audited, {"case:a": "P", "case:b": "F"}) == "failed"
    # unobserved audited evidence is never promoted to a resolution
    assert classify.audited_outcome("failed", audited, {"case:a": "P", "case:b": "U"}) == "unattributed"
    assert classify.audited_outcome("invalid", audited, {"case:a": "U", "case:b": "U"}) == "invalid"
    assert classify.audited_outcome("resolved", audited, {"case:a": "P", "case:b": "P"}) == "resolved"
