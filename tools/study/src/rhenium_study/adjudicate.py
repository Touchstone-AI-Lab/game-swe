"""Declared adjudication rules for attempts the automatic classifier left open.

The classifier never blames a candidate without an observed failure, so a
submission that does not compile ends ``unattributed``: the verifier stops before
any case is reached. A rule here may close such an attempt only from evidence the
trusted verifier wrote itself, and only when every execution of the attempt agrees.
Decisions are stored beside the ledger, never inside it, and the native outcome
stays on the record. Case observations are not touched: unreached cases stay
unknown, so an adjudicated attempt moves between task outcomes, not joint cells.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ADJUDICATOR = "declared automatic rule, authored with AI assistance; independent human review pending"
DECISIONS_FILE = "adjudication.json"


@dataclass(frozen=True)
class BuildFailureRule:
    """The pack's own verifier reported that the submission failed to build."""

    id: str
    game: str
    submission_prefix: str
    verifier_fault_prefixes: tuple[str, ...]

    def evidence(self, log: str) -> bool:
        lines = [line.strip() for line in log.splitlines()]
        if any(line.startswith(self.verifier_fault_prefixes) for line in lines):
            return False
        return any(line.startswith(self.submission_prefix) for line in lines)


RULES: tuple[BuildFailureRule, ...] = (
    BuildFailureRule(
        id="stardew-submission-build-failure",
        game="stardew-valley",
        submission_prefix="submission build failed (see build-submission.log)",
        verifier_fault_prefixes=("harness build failed (verifier bug, not the submission)",),
    ),
    BuildFailureRule(
        id="l4d2-submission-compile-failure",
        game="left-4-dead-2",
        submission_prefix="SUBMISSION_FAILED: SourcePawn compile failed for ",
        verifier_fault_prefixes=("INVALID_ENVIRONMENT:",),
    ),
    BuildFailureRule(
        id="rimworld-submission-build-failure",
        game="rimworld",
        submission_prefix="RimWorld submission build failed: the submitted sources did not compile",
        verifier_fault_prefixes=(
            "RimWorld verifier harness build failed (verifier bug, not the submission)",
        ),
    ),
)


def _no_case_ran(record: dict[str, Any]) -> bool:
    """A build failure stops the verifier before the game starts: only source gates are observed."""
    cases = record.get("cases")
    if not isinstance(cases, dict) or not cases:
        return False
    return all(seen == "U" for case, seen in cases.items() if not case.startswith("check:"))


def _run_log(state_dir: Path, run_id: object) -> str | None:
    if not isinstance(run_id, str) or not run_id or "/" in run_id or run_id.startswith("."):
        return None
    path = state_dir / "runs" / run_id / "runtime.log"
    if not path.is_file() or path.is_symlink():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def decide(record: dict[str, Any], state_dir: Path) -> dict[str, Any] | None:
    """The decision for one attempt, or ``None`` when no rule applies."""
    if record.get("outcome") != "unattributed" or not _no_case_ran(record):
        return None
    executions = record.get("executions")
    if not isinstance(executions, list) or not executions:
        return None
    game = str(record.get("task", "")).split("/")[0]
    for rule in RULES:
        if rule.game != game:
            continue
        logs = [_run_log(state_dir, item.get("runId")) for item in executions if isinstance(item, dict)]
        if len(logs) != len(executions) or any(log is None or not rule.evidence(log) for log in logs):
            continue
        return {
            "attempt_id": record["attempt_id"],
            "rule": rule.id,
            "from": "unattributed",
            "to": "failed",
            "evidence": {
                "marker": rule.submission_prefix,
                "runIds": [item["runId"] for item in executions],
            },
            "adjudicator": ADJUDICATOR,
        }
    return None


MANUAL_FILE = "adjudication-manual.json"


def manual_decisions(study_root: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reviewed decisions for attempts no rule covers, each with its written rationale.

    An entry may only close an open attempt as failed, must say why, and is refused
    when the attempt is missing or is no longer unattributed.
    """
    path = study_root / MANUAL_FILE
    if not path.is_file():
        return []
    open_attempts = {
        str(record["attempt_id"]) for record in records if record.get("outcome") == "unattributed"
    }
    decisions = []
    for entry in json.loads(path.read_text(encoding="utf-8")):
        attempt_id, rationale = str(entry.get("attempt_id", "")), str(entry.get("rationale", "")).strip()
        if attempt_id not in open_attempts or not rationale or entry.get("to") != "failed":
            raise ValueError(f"manual adjudication entry for {attempt_id!r} is not admissible")
        decisions.append(
            {
                "attempt_id": attempt_id,
                "rule": "manual-review",
                "from": "unattributed",
                "to": "failed",
                "evidence": {"rationale": rationale, "reviewer": str(entry.get("reviewer", ""))},
                "adjudicator": str(entry.get("reviewer", "")) or ADJUDICATOR,
            }
        )
    return decisions


def adjudicate(records: list[dict[str, Any]], state_dir: Path) -> list[dict[str, Any]]:
    return [decision for record in records if (decision := decide(record, state_dir)) is not None]


def write(study_root: Path, decisions: list[dict[str, Any]]) -> Path:
    path = study_root / DECISIONS_FILE
    path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load(study_root: Path) -> list[dict[str, Any]]:
    path = study_root / DECISIONS_FILE
    if not path.is_file():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError(f"{path} must hold a list of decisions")
    return loaded


def apply(records: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Records with decisions applied; the native outcome is kept as ``nativeOutcome``."""
    by_attempt = {str(decision["attempt_id"]): decision for decision in decisions}
    applied = []
    for record in records:
        decision = by_attempt.get(str(record.get("attempt_id")))
        if decision is None or record.get("outcome") != decision["from"]:
            applied.append(record)
            continue
        changed = dict(record)
        changed["nativeOutcome"] = record["outcome"]
        changed["outcome"] = decision["to"]
        if record.get("auditedOutcome") == decision["from"]:
            changed["auditedOutcome"] = decision["to"]
        changed["outcomeReason"] = (
            "adjudicated after review: " + str(decision["evidence"].get("rationale"))
            if decision["rule"] == "manual-review"
            else "adjudicated: the trusted verifier reported a submission build failure"
        )
        changed["adjudication"] = decision["rule"]
        applied.append(changed)
    return applied
