"""Attempt classification in the order Appendix B of the study protocol prescribes.

First decide whether the environment and fixture independently produced usable
evidence; only then read the candidate's outcome. The automatic rules are
deliberately conservative: anything they cannot attribute stays ``unattributed``
and is queued for adjudication rather than being counted as a candidate failure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

TaskOutcome = Literal["resolved", "failed", "invalid", "unattributed"]
SetOutcome = Literal["satisfied", "violated", "unknown", "empty"]

_ENVIRONMENT_STATUSES = frozenset({"unavailable", "error", "skipped"})
_STATIC_PREFIX = "check:"


def classify_execution(execution: Mapping[str, Any], table: Mapping[str, str]) -> tuple[TaskOutcome, str]:
    """Outcome of one evaluator execution and the reason for it."""
    if execution.get("evaluatorError"):
        return "invalid", "the evaluator could not run: " + str(execution["evaluatorError"])[:200]
    result = execution.get("result")
    if not isinstance(result, dict) or not result:
        return "invalid", "the evaluator returned no result"
    if result.get("complete") is True:
        if result.get("passed") is True:
            return "resolved", "every required assertion passed through the endpoint"
        return "failed", "a complete run observed at least one failed requirement"
    if any(seen == "F" for case, seen in table.items() if case.startswith(_STATIC_PREFIX)):
        return "failed", "the submission was rejected by a source gate before execution"
    if any(seen == "F" for seen in table.values()):
        return "failed", "a requirement failed and the run then stopped; later cases are unobserved"
    runtime = result.get("runtime")
    status = runtime.get("status") if isinstance(runtime, dict) else None
    if status in _ENVIRONMENT_STATUSES:
        return "invalid", f"the prepared runtime reported {status}"
    return "unattributed", "the run stopped without an observed failure; attribution needs review"


def set_outcome(cases: list[str], table: Mapping[str, str]) -> SetOutcome:
    """H.3: all valid passes satisfy; one valid violation fails; otherwise unknown."""
    if not cases:
        return "empty"
    seen = [table.get(case, "U") for case in cases]
    if any(value == "F" for value in seen):
        return "violated"
    if all(value == "P" for value in seen):
        return "satisfied"
    return "unknown"


def joint_outcome(target: SetOutcome, preserved: SetOutcome) -> str:
    if preserved == "empty":
        return "not-qualified"
    if "unknown" in (target, preserved):
        return "insufficient-observations"
    if target == "satisfied":
        return "both" if preserved == "satisfied" else "target-only"
    return "contracts-only" if preserved == "satisfied" else "neither"


def audited_outcome(native: TaskOutcome, audited_cases: list[str], table: Mapping[str, str]) -> TaskOutcome:
    """Task outcome over the audited cases only.

    An over-constrained case can neither fail an attempt nor block its
    resolution here. A native resolution always stands; otherwise every audited
    case must have a valid pass, and one valid audited failure decides.
    """
    if native == "resolved":
        return "resolved"
    seen = [table.get(case, "U") for case in audited_cases]
    if any(value == "F" for value in seen):
        return "failed"
    if seen and all(value == "P" for value in seen):
        return "resolved"
    return native if native in {"invalid", "unattributed"} else "unattributed"
