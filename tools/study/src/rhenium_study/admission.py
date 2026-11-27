"""E0 admission: decided from clause maps and control records, never from an agent score."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from . import controls
from .clausemap import ClauseMap
from .inventory import TASKS, StudyTask
from .paths import StudyPaths


def _records(task: StudyTask, paths: StudyPaths) -> dict[str, dict[str, Any]]:
    found = {}
    for path in sorted(controls.record_dir(task, paths).glob("*.json")):
        if path.name.endswith(".execution.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        found[str(record["control"])] = record
    return found


def assess(task: StudyTask, paths: StudyPaths) -> dict[str, Any]:
    directory = paths.study_controls(task.pack_dir, task.task)
    base: dict[str, Any] = {"task": task.key, "kind": task.kind, "sourceFamily": task.source_family}
    try:
        clause_map = ClauseMap.load(directory / "clause-map.json")
        specs = controls.load_manifest(directory)
    except (OSError, ValueError) as error:
        return {
            **base,
            "admitted": False,
            "compatibilityQualified": False,
            "reasons": [f"no valid clause map or manifest: {str(error)[:200]}"],
        }
    records = _records(task, paths)
    rows, reasons = [], []
    admissible: Counter[str] = Counter()
    for spec in specs:
        record = records.get(spec.control)
        if record is None:
            rows.append({"control": spec.control, "kind": spec.kind, "run": False, "problems": ["not run"]})
            continue
        ok = not record["problems"]
        # A strict-reading alternative documents an over-constraining assertion; it is
        # evidence about the suite and is not required to pass.
        informational = spec.control.startswith("alternative-strict-reading")
        if ok and not informational:
            admissible[spec.kind] += 1
        rows.append(
            {
                "control": spec.control,
                "kind": spec.kind,
                "run": True,
                "admissible": ok,
                "informational": informational,
                "score": record["score"],
                "complete": record["complete"],
                "problems": record["problems"],
            }
        )
    for kind in ("starter", "reference", "target-negative", "alternative"):
        if admissible[kind] == 0:
            reasons.append(f"no admissible {kind} control")
    flagged = [case.id for case in clause_map.cases if case.over_constrained]
    preserved = clause_map.case_ids("preserved", audited=True)
    if not clause_map.case_ids("target", audited=True):
        reasons.append("every target case is over-constrained; nothing audited remains to measure")
    qualified = not reasons and bool(preserved) and admissible["compat-negative"] > 0
    statuses = Counter(clause.status for clause in clause_map.clauses)
    return {
        **base,
        "taskVersion": clause_map.task_version,
        "admitted": not reasons,
        "compatibilityQualified": qualified,
        "reasons": reasons,
        "notQualifiedBecause": (
            None
            if qualified
            else "not admitted"
            if reasons
            else "no preserved contract with a passing starter baseline"
            if not preserved
            else "no admissible compatibility-specific negative"
        ),
        "cases": dict(Counter(case.role for case in clause_map.cases)),
        "overlapCases": sum(case.overlap for case in clause_map.cases),
        "overConstrainedCases": flagged,
        "clauses": dict(statuses),
        "excludedClauses": list(clause_map.excluded_clauses),
        "knownIssues": list(clause_map.known_issues),
        "controls": rows,
    }


def report(paths: StudyPaths) -> dict[str, Any]:
    tasks = [assess(task, paths) for task in TASKS]
    families = Counter(item["sourceFamily"] for item in tasks if item["admitted"])
    return {
        "registered": len(tasks),
        "admitted": [item["task"] for item in tasks if item["admitted"]],
        "compatibilityQualified": [item["task"] for item in tasks if item["compatibilityQualified"]],
        "excluded": {item["task"]: item["reasons"] for item in tasks if not item["admitted"]},
        "admittedSourceFamilies": dict(families),
        "tasks": tasks,
    }


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# E0 admission report",
        "",
        f"Registered tasks: {summary['registered']}. Admitted: {len(summary['admitted'])}. "
        f"Qualified for the joint compatibility analysis: {len(summary['compatibilityQualified'])}.",
        "",
        "Admission is decided from clause maps and control runs only; no agent score was consulted.",
        "",
        "| Task | Kind | Admitted | Joint-qualified | Target / preserved cases | Clauses asserted / weak / "
        "unasserted | Controls admissible |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in summary["tasks"]:
        cases, clauses = item.get("cases", {}), item.get("clauses", {})
        good = sum(
            1 for row in item.get("controls", []) if row.get("admissible") and not row.get("informational")
        )
        total = sum(1 for row in item.get("controls", []) if not row.get("informational"))
        lines.append(
            f"| `{item['task']}` | {item['kind']} | {'yes' if item['admitted'] else 'no'} | "
            f"{'yes' if item['compatibilityQualified'] else 'no'} | "
            f"{cases.get('target', 0)} / {cases.get('preserved', 0)} | "
            f"{clauses.get('asserted', 0)} / {clauses.get('weak', 0)} / {clauses.get('unasserted', 0)} | "
            f"{good}/{total} |"
        )
    lines += ["", "## Exclusions and reasons", ""]
    for task, reasons in summary["excluded"].items():
        lines.append(f"- `{task}`: " + "; ".join(reasons))
    lines += ["", "## Not joint-qualified", ""]
    for item in summary["tasks"]:
        if item["admitted"] and not item["compatibilityQualified"]:
            lines.append(f"- `{item['task']}`: {item['notQualifiedBecause']}")
    lines += ["", "## Over-constrained cases (kept out of the audited obligation sets)", ""]
    for item in summary["tasks"]:
        for case in item.get("overConstrainedCases", []):
            lines.append(f"- `{item['task']}`: `{case}`")
    lines += ["", "## Excluded clauses and known issues", ""]
    for item in summary["tasks"]:
        for clause in item.get("excludedClauses", []):
            lines.append(
                f"- `{item['task']}` clause `{clause}` has no assertion and is outside the target set"
            )
        for issue in item.get("knownIssues", []):
            lines.append(f"- `{item['task']}`: {issue}")
    return "\n".join(lines) + "\n"
