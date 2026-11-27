from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .catalog import GmodCatalog, GmodTask
from .contracts import GmodTraceability, GmodTraceCase
from .public_assets import PublicExamAsset, path_uses_link_or_junction

_CLAUSE = re.compile(r"\bT[1-5]-[A-Z]+-[0-9]{2}\b")


def _safe_file(root: Path, relative: str, *, task_id: str) -> Path:
    logical = PurePosixPath(relative)
    prefix = PurePosixPath("private") / "tasks" / task_id
    if not logical.is_relative_to(prefix):
        raise ValueError(f"private contract asset belongs to another task: {relative}")
    if path_uses_link_or_junction(root, logical):
        raise ValueError(f"private contract asset must not use links: {relative}")
    candidate = (root / Path(*logical.parts)).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError(f"private contract asset is unavailable: {relative}")
    return candidate


def _names(cases: list[GmodTraceCase]) -> list[str]:
    return [case.name for case in cases]


def _validate_mutations(
    task: GmodTask,
    root: Path,
    trace: GmodTraceability,
) -> None:
    path = _safe_file(root, task.evaluation.mutations, task_id=task.id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"mutation manifest is invalid for {task.id}") from error
    if not isinstance(value, dict) or set(value) != {"version", "base", "mutations"}:
        raise ValueError(f"mutation manifest schema is invalid for {task.id}")
    if value["version"] != 1 or not isinstance(value["mutations"], list) or not value["mutations"]:
        raise ValueError(f"mutation manifest content is invalid for {task.id}")
    base = value["base"]
    if not isinstance(base, str):
        raise ValueError(f"mutation base is invalid for {task.id}")
    base_logical = PurePosixPath("private") / "tasks" / task.id / base
    if ".." in base_logical.parts or path_uses_link_or_junction(root, base_logical):
        raise ValueError(f"mutation base is unsafe for {task.id}")
    base_root = (root / Path(*base_logical.parts)).resolve(strict=True)
    if not base_root.is_relative_to(root) or not base_root.is_dir():
        raise ValueError(f"mutation base is unavailable for {task.id}")

    groups = {
        "hidden-behavior": set(_names(trace.case_mappings.hidden_behavior)),
        "gmod-integration": set(_names(trace.case_mappings.gmod_integration)),
        "lifecycle-cleanup": set(_names(trace.case_mappings.lifecycle_cleanup)),
        "dedicated-server": set(_names(trace.case_mappings.dedicated_server)),
    }
    identifiers: set[str] = set()
    for mutation in value["mutations"]:
        required = {"id", "file", "check", "case", "expectedLayer"}
        if not isinstance(mutation, dict) or not required.issubset(mutation):
            raise ValueError(f"mutation entry is malformed for {task.id}")
        identifier = mutation["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError(f"mutation ID is invalid or duplicated for {task.id}")
        identifiers.add(identifier)
        check = mutation["check"]
        case = mutation["case"]
        if check not in groups or case not in groups[check]:
            raise ValueError(f"mutation catcher is not traceable for {task.id}: {identifier}")
        logical = PurePosixPath(str(mutation["file"]))
        if logical.is_absolute() or ".." in logical.parts or "\\" in str(mutation["file"]):
            raise ValueError(f"mutation target is unsafe for {task.id}: {identifier}")
        target = (base_root / Path(*logical.parts)).resolve(strict=True)
        if not target.is_relative_to(base_root) or not target.is_file():
            raise ValueError(f"mutation target is unavailable for {task.id}: {identifier}")
        if target.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(target)):
            raise ValueError(f"mutation target is linked for {task.id}: {identifier}")
        text = target.read_text(encoding="utf-8")
        replacements: list[dict[str, Any]]
        if "replacements" in mutation:
            replacements = mutation["replacements"]
        elif "old" in mutation and "new" in mutation:
            replacements = [{"old": mutation["old"], "new": mutation["new"]}]
        else:
            raise ValueError(f"mutation replacement is missing for {task.id}: {identifier}")
        if not isinstance(replacements, list) or not replacements:
            raise ValueError(f"mutation replacements are invalid for {task.id}: {identifier}")
        for replacement in replacements:
            if (
                not isinstance(replacement, dict)
                or set(replacement) != {"old", "new"}
                or not isinstance(replacement["old"], str)
                or not replacement["old"]
                or not isinstance(replacement["new"], str)
                or text.count(replacement["old"]) != 1
            ):
                raise ValueError(f"mutation replacement is not unique for {task.id}: {identifier}")


def validate_gmod_private_contracts(
    catalog: GmodCatalog,
    *,
    pack_root: Path,
    public_assets: dict[str, PublicExamAsset],
) -> None:
    root = pack_root.resolve(strict=True)
    for task in catalog.tasks:
        asset = public_assets[task.id]
        expected_exam = (root / "exams" / f"{task.id}.md").resolve(strict=True)
        if asset.path != expected_exam:
            raise ValueError(f"public exam binding drifted for {task.id}")
        trace_path = _safe_file(root, str(task.evaluation.traceability), task_id=task.id)
        try:
            trace = GmodTraceability.model_validate_json(trace_path.read_bytes())
        except (UnicodeError, ValueError) as error:
            raise ValueError(f"contract traceability schema is invalid for {task.id}") from error
        if trace.task_id != task.id or trace.task_version != task.task_version:
            raise ValueError(f"contract traceability identity drifted for {task.id}")
        mappings = trace.case_mappings
        expected = {
            "hidden-behavior": task.evaluation.hidden_cases,
            "gmod-integration": task.evaluation.integration_cases,
            "lifecycle-cleanup": task.evaluation.lifecycle_cases,
            "dedicated-server": task.server_runtime.expected_cases,
        }
        actual = {
            "hidden-behavior": _names(mappings.hidden_behavior),
            "gmod-integration": _names(mappings.gmod_integration),
            "lifecycle-cleanup": _names(mappings.lifecycle_cleanup),
            "dedicated-server": _names(mappings.dedicated_server),
        }
        if actual != expected:
            raise ValueError(f"traceability cases do not exactly match catalog order for {task.id}")

        public_clauses = set(_CLAUSE.findall(asset.text))
        all_cases = (
            mappings.hidden_behavior
            + mappings.gmod_integration
            + mappings.lifecycle_cleanup
            + mappings.dedicated_server
        )
        if any(case.classification == "C" for case in all_cases):
            raise ValueError(f"scored implementation-detail case is forbidden for {task.id}")
        scored_clauses = {clause for case in all_cases for clause in case.clauses}
        api_clauses = {clause for clauses in trace.api_coverage.values() for clause in clauses}
        referenced = scored_clauses | api_clauses
        if not referenced or not referenced.issubset(public_clauses):
            raise ValueError(f"traceability references a non-public clause for {task.id}")
        uncovered = sorted(public_clauses - scored_clauses)
        if uncovered:
            raise ValueError(
                f"public contract clauses lack scored case traceability for {task.id}: {uncovered}"
            )
        if set(trace.api_coverage) != set(task.public_exam.interfaces):
            raise ValueError(f"traceability API keys drifted for {task.id}")
        if any(not clauses for clauses in trace.api_coverage.values()):
            raise ValueError(f"traceability API coverage is empty for {task.id}")
        if set(trace.acceptance_coverage) != set(task.public_exam.acceptance_evidence):
            raise ValueError(f"traceability acceptance keys drifted for {task.id}")
        valid_case_refs = {f"{group}:{name}" for group, names in actual.items() for name in names}
        if any(
            not values or any(reference not in valid_case_refs for reference in values)
            for values in trace.acceptance_coverage.values()
        ):
            raise ValueError(f"traceability acceptance evidence is invalid for {task.id}")
        missing_tokens = [token for token in trace.required_public_tokens if token not in asset.text]
        if missing_tokens:
            raise ValueError(f"canonical exam omits required public tokens for {task.id}: {missing_tokens}")
        _validate_mutations(task, root, trace)
