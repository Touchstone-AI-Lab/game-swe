"""Draft clause maps from the packs' own records plus the starter/reference baseline.

A draft is a starting point for a maintainer, not an admitted map: roles come
from recorded labels where a pack has them and otherwise from whether the case
already passes in the unchanged starter. Clause links the pack does not record
are left on a single ``request`` clause for the maintainer to split.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .inventory import StudyTask
from .paths import StudyPaths

_SENTINEL = re.compile(
    r"(sentinel|^runtime_|plugin[-_ ]?(loaded|enabled)|_loaded$|gamemode is loaded|^package_|compile)",
    re.IGNORECASE,
)
_STATIC = frozenset({"required-files", "lua-syntax", "implementation-depth", "submission-shape"})
# GLuaTest suites name a case after the report it covers: "A: ...", "D-enforce: ...".
_REPORT_LETTER = re.compile(r"^([A-Z])(?:-[\w-]+)?: ")
# Issue-style exams mark each report as **[#1234]** or **[A]**.
_REPORT_MARKER = re.compile(r"\*\*\[(#?[\w-]+)\]\*\*")


def _catalog_task(pack: Path, task: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((pack / "benchmark.json").read_text(encoding="utf-8"))
    catalog = json.loads((pack / manifest["catalog"]).read_text(encoding="utf-8"))
    return catalog, next(item for item in catalog["tasks"] if item["id"] == task)


def _contracts(pack: Path, task: str) -> dict[str, dict[str, str]]:
    path = pack / "private" / "harbor" / task / "validation" / "case-contracts.tsv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["case"]: row for row in csv.DictReader(handle, delimiter="\t")}


def _gmod_clauses(pack: Path, task: str) -> dict[str, list[str]]:
    path = pack / "private" / "tasks" / task / "contract-traceability.json"
    if not path.is_file():
        return {}
    layers = {
        "hidden-behavior": "hidden",
        "gmod-integration": "integration",
        "lifecycle-cleanup": "lifecycle",
        "dedicated-server": "server",
    }
    mapping = json.loads(path.read_text(encoding="utf-8"))["caseMappings"]
    return {
        f"{layers[layer]}:{case['name']}": list(case["clauses"])
        for layer, cases in mapping.items()
        for case in cases
    }


def _report_groups(pack: Path, task: str, names: list[str]) -> dict[str, str]:
    """Report letters in case names mapped to the exam's report markers, in order.

    Only a one-to-one match is trusted: the task's distinct letters and the exam's
    distinct markers must be equally many; otherwise each letter stays its own group.
    """
    letters = sorted({match.group(1) for name in names if (match := _REPORT_LETTER.match(name))})
    exam = pack / "exams" / f"{task}.md"
    text = exam.read_text(encoding="utf-8") if exam.is_file() else ""
    markers = list(dict.fromkeys(_REPORT_MARKER.findall(text)))
    if letters and len(letters) == len(markers):
        return {letter: f"[{marker}]" for letter, marker in zip(letters, markers, strict=True)}
    return {letter: f"report-{letter}" for letter in letters}


def draft(
    task: StudyTask, paths: StudyPaths, starter: Mapping[str, str], reference: Mapping[str, str]
) -> dict[str, Any]:
    pack = paths.pack_root(task.pack_dir)
    catalog, entry = _catalog_task(pack, task.task)
    contracts = _contracts(pack, task.task)
    # Evaluators that report per-case outcomes and per-layer details name each case
    # twice; the layer-qualified name is kept so no evidence is counted twice.
    layered = {
        case_id.partition(":")[2] for case_id in reference if not case_id.startswith(("case:", "check:"))
    }
    names = [case_id.partition(":")[2] for case_id in reference]
    reports = _report_groups(pack, task.task, names)
    # Source-pattern gates are declared by the catalog; any other check is an engine verdict.
    gates = {str(item.get("id")) for item in entry.get("integration_checks", []) if isinstance(item, dict)}
    gmod = _gmod_clauses(pack, task.task) if task.pack == "addons" else {}
    clauses: dict[str, dict[str, str]] = {}
    cases: list[dict[str, Any]] = []

    def clause(identifier: str, anchor: str, status: str = "asserted") -> str:
        clauses.setdefault(identifier, {"id": identifier, "anchor": anchor, "status": status})
        return identifier

    for case_id in reference:
        layer, _, name = case_id.partition(":")
        if layer == "case" and name in layered:
            continue
        row = contracts.get(name, {})
        label = row.get("class") or row.get("role") or ""
        group = row.get("report") or row.get("defect_group") or row.get("group") or ""
        if not group and (letter := _REPORT_LETTER.match(name)):
            group = reports[letter.group(1)]
        if layer == "check":
            # A gate the unchanged starter already passes (an offline build, say) is
            # delivery, not evidence for the requested change.
            if name in _STATIC or starter.get(case_id) == "P":
                cases.append({"id": case_id, "role": "static"})
            elif name not in gates:
                # An engine check whose evaluator reports no per-case outcomes: its one
                # verdict is the only evidence for the whole request.
                linked = clause("request", "exam body; split into individual clauses during review")
                cases.append(
                    {
                        "id": case_id,
                        "role": "target",
                        "clauses": [linked],
                        "note": "aggregate engine verdict; the evaluator reports no per-case outcomes",
                    }
                )
            else:
                linked = clause(
                    f"integration:{name}", f"host-integration section; source-pattern gate {name}", "weak"
                )
                cases.append(
                    {
                        "id": case_id,
                        "role": "target",
                        "clauses": [linked],
                        "note": "regular-expression gate over the submitted source, not an execution",
                    }
                )
            continue
        if name.startswith("setup:"):
            cases.append({"id": case_id, "role": "setup"})
        elif label == "runtime" or _SENTINEL.search(name):
            cases.append({"id": case_id, "role": "runtime-sentinel"})
        elif label == "guard" or (not label and starter.get(case_id) == "P"):
            anchor = row.get("public_contract") or "behavior the unchanged starter already provides"
            linked = clause(f"preserve:{group}" if group and group != "-" else "preserve", anchor)
            cases.append({"id": case_id, "role": "preserved", "clauses": [linked]})
        else:
            if case_id in gmod:
                linked_ids = [clause(item, f"exam clause {item}") for item in gmod[case_id]]
            elif group and group != "-":
                linked_ids = [clause(group, row.get("public_contract") or f"exam report {group}")]
            else:
                linked_ids = [clause("request", "exam body; split into individual clauses during review")]
            cases.append({"id": case_id, "role": "target", "clauses": linked_ids})
    return {
        "task": task.key,
        "task_version": str(entry.get("task_version") or entry.get("version") or catalog.get("version")),
        "exam": f"benchmarks/{task.pack_dir}/exams/{task.task}.md",
        "cases": cases,
        "clauses": list(clauses.values()),
        "excluded_clauses": [],
        "known_issues": [],
    }
