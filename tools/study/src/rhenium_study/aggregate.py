"""Aggregation of the attempt ledger under the study protocol.

Every rate is first a per-task fraction of *scheduled* attempts and only then
averaged over tasks with equal weight, so the nine joint-outcome cells of a
task set sum to one. Invalid and unattributed attempts stay in that denominator.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import Any

STATES = ("satisfied", "violated", "unknown")
CELLS = tuple(f"{target}/{preserved}" for target in STATES for preserved in STATES)


def attempt_records(study_root: Path, *, excluded: Collection[str]) -> list[dict[str, Any]]:
    """Every attempt record of the study except those of excluded tasks (left on disk untouched)."""
    records = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((study_root / "attempts").glob("*/attempt.json"))
    )
    return [record for record in records if record["task"] not in excluded]


def load_ledger(
    study_root: Path, *, excluded: Collection[str], adjudicated: bool = True
) -> list[dict[str, Any]]:
    """The scored attempt ledger, with the stored adjudication decisions applied by default.

    Attempts of excluded tasks are dropped before adjudication. Attempts still waiting
    for an evaluation on another host have no result yet and are left out;
    ``pending_evaluation`` lists them.
    """
    from . import adjudicate
    from .attempts import PENDING

    records = [
        record
        for record in attempt_records(study_root, excluded=excluded)
        if record.get("outcome") != PENDING
    ]
    return adjudicate.apply(records, adjudicate.load(study_root)) if adjudicated else records


def pending_evaluation(study_root: Path, *, excluded: Collection[str]) -> list[str]:
    from .attempts import PENDING

    return [
        record["attempt_id"]
        for record in attempt_records(study_root, excluded=excluded)
        if record.get("outcome") == PENDING
    ]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def environment_valid(record: dict[str, Any]) -> bool:
    """Whether the execution is eligible for the valid-environment view.

    Validity of the environment is recorded separately from the task outcome: a
    complete run is valid whatever its verdict, and so is a submission rejected
    by a source gate before launch. A run that stopped early stays ineligible even
    when it retained a valid candidate failure.
    """
    if record.get("complete") is True:
        return True
    if record.get("nativeOutcome") == "unattributed" and record.get("outcome") == "failed":
        # Adjudicated build failure: the verifier rejected the submission before launch.
        return True
    cases = record.get("cases") or {}
    return any(seen == "F" for case, seen in cases.items() if case.startswith("check:"))


def _observation_counts(record: dict[str, Any], prefix_roles: dict[str, str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for case, seen in (record.get("cases") or {}).items():
        role = prefix_roles.get(case)
        if role is None:
            continue
        counts[f"{role}.expected"] += 1
        if seen in {"P", "F", "I"}:
            counts[f"{role}.reached"] += 1
        if seen in {"P", "F"}:
            counts[f"{role}.valid"] += 1
        if seen == "P":
            counts[f"{role}.passed"] += 1
    return counts


def per_task(records: list[dict[str, Any]], scheduled: int) -> list[dict[str, Any]]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        cells[(record["model"], record["task"])].append(record)
    rows = []
    for (model, task), attempts in sorted(cells.items()):
        first = attempts[0]
        qualified = first["preservedOutcome"] != "empty"
        outcomes = Counter(item["outcome"] for item in attempts)
        joint = Counter(
            f"{item['targetOutcome']}/{item['preservedOutcome']}" for item in attempts if qualified
        )
        valid = [item for item in attempts if environment_valid(item)]
        rows.append(
            {
                "model": model,
                "task": task,
                "game": task.split("/")[0],
                "kind": first["kind"],
                "sourceFamily": first["sourceFamily"],
                "qualified": qualified,
                "scheduled": scheduled,
                "recorded": len(attempts),
                "resolved": outcomes["resolved"],
                "failed": outcomes["failed"],
                "invalid": outcomes["invalid"],
                "unattributed": outcomes["unattributed"],
                "adjudicated": sum("nativeOutcome" in item for item in attempts),
                "auditedResolved": sum(item.get("auditedOutcome") == "resolved" for item in attempts),
                "targetSatisfied": sum(item["targetOutcome"] == "satisfied" for item in attempts),
                "preservedSatisfied": sum(item["preservedOutcome"] == "satisfied" for item in attempts),
                "cells": {cell: joint[cell] for cell in CELLS} if qualified else None,
                "validEnvironment": len(valid),
                "validEnvironmentResolved": sum(item["outcome"] == "resolved" for item in valid),
                "usage": {
                    "calls": sum((item.get("usage") or {}).get("calls", 0) for item in attempts),
                    "promptTokens": sum(
                        (item.get("usage") or {}).get("prompt_tokens", 0) for item in attempts
                    ),
                    "completionTokens": sum(
                        (item.get("usage") or {}).get("completion_tokens", 0) for item in attempts
                    ),
                    "generationSeconds": sum(
                        (item.get("generation") or {}).get("durationSeconds") or 0 for item in attempts
                    ),
                },
            }
        )
    return rows


def _balanced(rows: list[dict[str, Any]], numerator: str, *, by: str | None = None) -> float | None:
    rates = [(row[by] if by else None, row[numerator] / row["scheduled"]) for row in rows]
    if not rates:
        return None
    if by is None:
        return _mean([rate for _group, rate in rates])
    groups: dict[Any, list[float]] = defaultdict(list)
    for group, rate in rates:
        groups[group].append(rate)
    return _mean([sum(values) / len(values) for values in groups.values()])


def _cell_means(rows: list[dict[str, Any]]) -> dict[str, float] | None:
    if not rows:
        return None
    return {cell: sum(row["cells"][cell] / row["scheduled"] for row in rows) / len(rows) for cell in CELLS}


def _conditional(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Among requested-change successes, with the primary task weighting kept."""
    if not rows:
        return {"targetSuccess": None, "observedContractViolation": None, "contractOutcomeUnknown": None}
    success = _mean([row["targetSatisfied"] / row["scheduled"] for row in rows])
    violated = _mean([row["cells"]["satisfied/violated"] / row["scheduled"] for row in rows])
    unknown = _mean([row["cells"]["satisfied/unknown"] / row["scheduled"] for row in rows])
    return {
        "targetSuccess": success,
        "observedContractViolation": _ratio(violated, success),
        "contractOutcomeUnknown": _ratio(unknown, success),
        "counts": {
            "targetSatisfied": sum(row["targetSatisfied"] for row in rows),
            "withObservedViolation": sum(row["cells"]["satisfied/violated"] for row in rows),
            "withUnknownContracts": sum(row["cells"]["satisfied/unknown"] for row in rows),
        },
    }


def _valid_environment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    undefined = [row["task"] for row in rows if row["validEnvironment"] == 0]
    if undefined or not rows:
        # Dropping a task would change the comparison, so the full-set score is undefined.
        return {"taskBalanced": None, "tasksWithoutEligibleAttempt": undefined}
    rates = [row["validEnvironmentResolved"] / row["validEnvironment"] for row in rows]
    return {"taskBalanced": _mean(rates), "tasksWithoutEligibleAttempt": []}


def _view(rows: list[dict[str, Any]]) -> dict[str, Any]:
    qualified = [row for row in rows if row["qualified"]]
    families = sorted({row["sourceFamily"] for row in qualified})
    return {
        "tasks": len(rows),
        "fullResolution": {
            "taskBalanced": _balanced(rows, "resolved"),
            "gameBalanced": _balanced(rows, "resolved", by="game"),
            "auditedTaskBalanced": _balanced(rows, "auditedResolved"),
            "auditedGameBalanced": _balanced(rows, "auditedResolved", by="game"),
            "validEnvironment": _valid_environment(rows),
        },
        "nonResolutionFrequency": {
            "invalid": _balanced(rows, "invalid"),
            "unattributed": _balanced(rows, "unattributed"),
            "adjudicatedAttempts": sum(row["adjudicated"] for row in rows),
        },
        "qualifiedTasks": len(qualified),
        "jointCells": _cell_means(qualified),
        "jointCellsGameBalanced": (
            {
                cell: _mean(
                    [
                        sum(row["cells"][cell] / row["scheduled"] for row in group) / len(group)
                        for group in _groups(qualified, "game")
                    ]
                )
                for cell in CELLS
            }
            if qualified
            else None
        ),
        "targetSuccess": _balanced(qualified, "targetSatisfied"),
        "preservedSuccess": _balanced(qualified, "preservedSatisfied"),
        "conditional": _conditional(qualified),
        "sourceFamilySensitivity": {
            "familyBalancedTargetOnly": (
                _mean(
                    [
                        sum(row["cells"]["satisfied/violated"] / row["scheduled"] for row in group)
                        / len(group)
                        for group in _groups(qualified, "sourceFamily")
                    ]
                )
                if qualified
                else None
            ),
            "leaveOneFamilyOut": {
                family: _cell_means([row for row in qualified if row["sourceFamily"] != family])
                for family in families
            },
        },
        "usage": {
            key: sum(row["usage"][key] for row in rows)
            for key in ("calls", "promptTokens", "completionTokens", "generationSeconds")
        },
    }


def _groups(rows: list[dict[str, Any]], key: str) -> list[list[dict[str, Any]]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return list(groups.values())


def summarize(records: list[dict[str, Any]], scheduled: int) -> dict[str, Any]:
    rows = per_task(records, scheduled)
    summary = {}
    for model in sorted({row["model"] for row in rows}):
        for kind in ("construct", "repair"):
            selected = [row for row in rows if row["model"] == model and row["kind"] == kind]
            if selected:
                summary[f"{model}/{kind}"] = _view(selected)
    return {"attempts": len(records), "scheduledPerTask": scheduled, "perTask": rows, "summary": summary}
