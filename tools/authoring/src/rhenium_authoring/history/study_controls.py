"""E0 inputs for a published history task: manifest, patches, alternative, clause map.

The layout matches ``benchmarks/minecraft-core/private/study-controls/<task>``
so ``rhenium-study e0`` can replay every control once the task is registered
in the study inventory. The clause map is a draft in the same shape the study
tooling validates: one asserted clause per target case, one for the preserved
behaviour the exam names and one for the frozen upstream tests.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .engine import ControlOutcome
from .minecraft_pack import HistoryTask


def _diff(relative: str, old: str, new: str) -> str:
    """A ``patch -p1`` unified diff of one file (GNU diff keeps newline markers)."""
    with tempfile.TemporaryDirectory(prefix="history-diff-") as raw:
        before, after = Path(raw) / "a", Path(raw) / "b"
        before.write_text(old, encoding="utf-8")
        after.write_text(new, encoding="utf-8")
        completed = subprocess.run(
            ["diff", "-u", "--label", f"a/{relative}", "--label", f"b/{relative}", str(before), str(after)],
            capture_output=True,
            text=True,
            check=False,
        )
    if completed.returncode not in (0, 1):
        raise RuntimeError("diff failed while writing a study control")
    return completed.stdout


def _text(path: Path) -> str:
    """A file's text, or empty for a file the control adds."""
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _patch(tree: Path, files: dict[str, Any]) -> str:
    return "".join(
        _diff(relative, _text(tree / relative), str(text)) for relative, text in sorted(files.items())
    )


def clause_map(task: HistoryTask) -> dict[str, Any]:
    targets = [case for case in task.authored.cases if case.role == "target"]
    cases: list[dict[str, Any]] = [
        {
            "id": "check:submission-shape",
            "role": "static",
            "clauses": [],
            "overlap": False,
            "note": "required files present, no symlinks or compiled artifacts",
        },
        {
            "id": "check:offline-build",
            "role": "static",
            "clauses": [],
            "overlap": False,
            "note": "repository builds offline after frozen paths are restored",
        },
    ]
    clauses: list[dict[str, Any]] = []
    for index, case in enumerate(targets, 1):
        clauses.append({"id": f"task-{index}", "anchor": f"Task: {case.public_report}", "status": "asserted"})
    for case in task.authored.cases:
        if case.role == "sentinel":
            cases.append(
                {
                    "id": f"server:{case.case}",
                    "role": "runtime-sentinel",
                    "clauses": [],
                    "overlap": False,
                    "note": "",
                }
            )
        elif case.role == "target":
            clause = f"task-{targets.index(case) + 1}"
            cases.append(
                {
                    "id": f"server:{case.case}",
                    "role": "target",
                    "clauses": [clause],
                    "overlap": False,
                    "note": "",
                }
            )
        else:
            cases.append(
                {
                    "id": f"server:{case.case}",
                    "role": "preserved",
                    "clauses": ["preserve"],
                    "overlap": False,
                    "note": "",
                }
            )
    if any(case.role == "preserved" for case in task.authored.cases):
        clauses.append(
            {"id": "preserve", "anchor": "Task: behaviour that must keep working", "status": "asserted"}
        )
    for name in task.probe.unit_cases:
        cases.append(
            {
                "id": f"unit:{name}",
                "role": "preserved",
                "clauses": ["scope-tests"],
                "overlap": False,
                "note": "",
            }
        )
    if task.probe.unit_cases:
        clauses.append(
            {
                "id": "scope-tests",
                "anchor": "Task: the existing upstream tests keep passing",
                "status": "asserted",
            }
        )
    return {
        "task": f"minecraft/history/{task.task_id}",
        "task_version": "0.1.0",
        "exam": f"benchmarks/minecraft-history/exams/{task.task_id}.md",
        "cases": cases,
        "clauses": clauses,
        "excluded_clauses": [],
        "known_issues": [],
    }


def controls_markdown(task: HistoryTask, outcomes: list[ControlOutcome]) -> str:
    lines = [
        f"# Acceptance gates: {task.task_id}",
        "",
        "Real Paper 1.21.11 build 132 server through the Rhenium evaluator (networkless), run by "
        "rhenium-author project-history mode. Every row is one full-profile evaluation.",
        "",
        "| Control | Kind | Complete | Passed | Score | Failed cases | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for outcome in outcomes:
        failed = ", ".join(f"`{name}`" for name in outcome.failed) or "none"
        lines.append(
            f"| `{outcome.label}` | {outcome.kind} | {outcome.complete} | {outcome.passed} | "
            f"{outcome.score} | {failed} | {'admissible' if outcome.admissible else outcome.reason} |"
        )
    return "\n".join(lines) + "\n"


def write_study_controls(
    pack: Path, candidate_root: Path, task: HistoryTask, outcomes: list[ControlOutcome]
) -> None:
    target = pack / "private" / "study-controls" / task.task_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    rows = ["control\tkind\tbase\toverlay\troot\tnote"]
    alternative = json.loads((candidate_root / "alternative.json").read_text(encoding="utf-8"))
    for relative, text in alternative["files"].items():
        path = target / "alternative-a" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    rows.append(
        "alternative-a\talternative\tstarter\ttree:alternative-a\tplugin\t"
        "written by the alternative role from the exam, without the upstream fix"
    )
    negative = json.loads((candidate_root / "target-negative.json").read_text(encoding="utf-8"))
    (target / "target-negative-hunk.patch").write_text(_patch(task.reference_tree, negative["files"]))
    origin = str(negative.get("origin") or "reverted hunk")
    note = (
        "reference with one hunk of the upstream fix reverted"
        if origin == "reverted hunk"
        else "reference with a model-written partial repair: "
        + " ".join(str(negative.get("rationale", "")).split())[:160]
    )
    rows.append(
        f"target-negative-hunk\ttarget-negative\treference\tpatch:target-negative-hunk.patch\tplugin\t{note}"
    )
    compat_path = candidate_root / "compat-negative.json"
    if compat_path.is_file() and any(outcome.kind == "compat-negative" for outcome in outcomes):
        compat = json.loads(compat_path.read_text(encoding="utf-8"))
        (target / "compat-negative-model.patch").write_text(_patch(task.reference_tree, compat["files"]))
        note = " ".join(str(compat.get("rationale", "")).split())[:200] or "breaks one preserved case"
        rows.append(
            f"compat-negative-model\tcompat-negative\treference\tpatch:compat-negative-model.patch\t"
            f"plugin\t{note}"
        )
    (target / "manifest.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (target / "clause-map.json").write_text(
        json.dumps(clause_map(task), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    kinds = {outcome.label: outcome for outcome in outcomes}
    summary = [
        f"# minecraft/history/{task.task_id} — E0 notes",
        "",
        f"Authored by rhenium-author project-history mode from {str(task.fix.repository_url).rstrip('/')} "
        f"(`{task.fix.fixed_sha[:12]}`). Controls below were run by the authoring pipeline; rerun them "
        "with `rhenium-study e0 run` once the task is in the study inventory.",
        "",
        *[
            f"- `{label}`: {'admissible' if item.admissible else item.reason}"
            for label, item in kinds.items()
        ],
    ]
    (target / "NOTES.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
