"""Materialize an authoring mutation; never compile, run an engine or grade it.

Run with the repository's existing Python environment and plugin on PYTHONPATH:
  python materialize_control.py omit-equipped-sync /absolute/owned/state
The new task-owned output contains candidate/, adapter/ and private-plan.json.
No expected observations enter candidate/ or adapter/.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from rhenium_rimworld.assertions import generated_dispatch_source, load_assertion_manifest
from rhenium_rimworld.safe_files import (
    ensure_directory_nofollow,
    secure_copy_file,
    secure_inventory,
    secure_read_bytes,
    secure_tree_hash,
    write_owner_file,
)
from rhenium_rimworld.supervisor import strict_json_object


def materialize(task: Path, control_id: str, state: Path) -> Path:
    task = task.resolve(strict=True)
    pack = task.parents[2]
    state = state.resolve()
    if state.is_relative_to(pack) or pack.is_relative_to(state):
        raise ValueError("control state must be outside the benchmark pack")
    plan = strict_json_object(secure_read_bytes(task, "validation/mutation-controls.json"))
    controls = [item for item in plan["mutations"] + plan["fixtureMutations"]
                if item["id"] == control_id]
    if len(controls) != 1 or not control_id.replace("-", "").isalnum():
        raise ValueError("unknown or ambiguous control")
    control: dict[str, Any] = controls[0]
    fixture_mutation = "source" in control
    relative = control["source"] if fixture_mutation else plan["source"]
    source = secure_read_bytes(task if fixture_mutation else task / "solution/after", relative)
    expected_hash = control["inputSha256"] if fixture_mutation else plan["oracleSha256"]
    if hashlib.sha256(source).hexdigest() != expected_hash:
        raise ValueError("control input source hash mismatch")
    old, new = control["replaceOnce"].encode(), control["with"].encode()
    if source.count(old) != 1:
        raise ValueError("mutation anchor is not unique")
    mutated = source.replace(old, new, 1)
    if hashlib.sha256(mutated).hexdigest() != control["mutatedSha256"]:
        raise ValueError("mutation output hash mismatch")
    manifest = load_assertion_manifest(pack, task.name)
    if not set(control["mustFailCases"]) <= set(manifest.case_names):
        raise ValueError("control refers to unknown cases")
    output = state.joinpath(*manifest.task_key.split("/"), control_id)
    if output.exists() or output.is_symlink():
        raise ValueError("control output already exists")
    ensure_directory_nofollow(output)
    for entry in secure_inventory(task / "solution/after"):
        if not entry.is_dir:
            if not fixture_mutation and entry.relative == relative:
                write_owner_file(output / "candidate" / relative, mutated)
            else:
                secure_copy_file(task / "solution/after", entry.relative, output / "candidate")
    # Adapter authoring source is private; only generated dispatch enters an image.
    ensure_directory_nofollow(output / "adapter")
    for entry in secure_inventory(task / "tests"):
        if not entry.is_dir and entry.relative != "assertions.json":
            if fixture_mutation and "tests/" + entry.relative == relative:
                write_owner_file(output / "adapter" / entry.relative, mutated)
            else:
                secure_copy_file(task / "tests", entry.relative, output / "adapter")
    write_owner_file(output / "adapter/Harness/GeneratedAssertions.cs", generated_dispatch_source(manifest))
    private_plan = {
        "status": "not-run", "authoringExpectationsOnly": True,
        "taskKey": manifest.task_key,
        "control": control, "manifestCaseCount": len(manifest.cases),
        "candidateSource": secure_tree_hash(output / "candidate"),
        "adapterSource": secure_tree_hash(output / "adapter"),
        "rubric": manifest.rubric_hash(),
        "nextStep": (
            "Separately authorized reference compile and real-engine evaluation with fresh immutable identity"
        ),
    }
    write_owner_file(output / "private-plan.json", (json.dumps(private_plan, indent=2) + "\n").encode())
    return output


if __name__ == "__main__":
    selected, destination = sys.argv[1:]
    print(materialize(Path(__file__).resolve().parent.parent, selected, Path(destination)))
