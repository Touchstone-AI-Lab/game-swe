"""Create independent, hash-bound controls in owned state; never compile or grade."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

# Authoring entry points must not create bytecode caches in pack/source directories.
sys.dont_write_bytecode = True

from rhenium_rimworld.assertions import generated_dispatch_source, load_assertion_manifest  # noqa: E402
from rhenium_rimworld.safe_files import (  # noqa: E402
    ensure_directory_nofollow,
    secure_inventory,
    secure_read_bytes,
    secure_tree_hash,
    write_owner_file,
)
from rhenium_rimworld.supervisor import strict_json_object  # noqa: E402


def materialize(task: Path, control_id: str, state: Path) -> Path:
    task = task.resolve(strict=True)
    pack = task.parents[2]
    state = state.absolute()
    resolved = state.resolve()
    if resolved.is_relative_to(pack) or pack.is_relative_to(resolved):
        raise ValueError("control state must be outside the benchmark pack")
    manifest = load_assertion_manifest(pack, task.name)
    plan = strict_json_object(secure_read_bytes(task, "validation/mutation-controls.json"))
    derivation = strict_json_object(secure_read_bytes(task, "validation/source-derivation.json"))
    if control_id in {"base", "nop", "oracle"}:
        control: dict[str, Any] = {"id": control_id, "status": "not-run"}
    else:
        matches = [item for item in plan["mutations"] + plan["fixtureMutations"]
                   if item["id"] == control_id]
        if len(matches) != 1:
            raise ValueError("unknown or ambiguous control")
        control = matches[0]
    if not control_id.replace("-", "").isalnum():
        raise ValueError("unsafe control ID")
    if not set(control.get("mustFailCases", [])) <= set(manifest.case_names):
        raise ValueError("unknown control case")
    output = state.joinpath(*manifest.task_key.split("/"), control_id)
    if output.exists() or output.is_symlink():
        raise ValueError("control output already exists")
    source_side = "environment" if control_id in {"base", "nop"} else "solution/after"
    source_root = task / source_side / "AdaptiveStorage"
    candidate: dict[str, bytes] = {}
    for item in derivation["files"]:
        raw = secure_read_bytes(source_root, item["path"])
        digest = item["baseSha256" if control_id in {"base", "nop"} else "targetSha256"]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("candidate source hash mismatch")
        candidate["AdaptiveStorage/" + item["path"]] = raw
    license_bytes = secure_read_bytes(task / "environment/AdaptiveStorage", "LICENSE")
    if hashlib.sha256(license_bytes).hexdigest() != derivation["licenseSha256"]:
        raise ValueError("license hash mismatch")
    candidate["AdaptiveStorage/LICENSE"] = license_bytes
    dependencies = strict_json_object(secure_read_bytes(task, "validation/dependencies.json"))
    for notice in dependencies["additionalNotices"]:
        raw = secure_read_bytes(task / "environment/AdaptiveStorage", notice["path"])
        if hashlib.sha256(raw).hexdigest() != notice["sha256"]:
            raise ValueError("notice hash mismatch")
        candidate["AdaptiveStorage/" + notice["path"]] = raw
    adapter = {entry.relative: secure_read_bytes(task / "tests", entry.relative)
               for entry in secure_inventory(task / "tests")
               if not entry.is_dir and entry.relative != "assertions.json"}
    adapter["Harness/GeneratedAssertions.cs"] = generated_dispatch_source(manifest)
    if "replaceOnce" in control:
        surface = adapter if control["surface"] == "adapter" else candidate
        raw = surface[control["source"]]
        if hashlib.sha256(raw).hexdigest() != control["inputSha256"]:
            raise ValueError("mutation input hash mismatch")
        old, new = control["replaceOnce"].encode(), control["with"].encode()
        if raw.count(old) != 1:
            raise ValueError("mutation anchor is not unique")
        raw = raw.replace(old, new, 1)
        if hashlib.sha256(raw).hexdigest() != control["mutatedSha256"]:
            raise ValueError("mutation output hash mismatch")
        surface[control["source"]] = raw
    # All hashes and anchors are checked before touching a new state directory.
    ensure_directory_nofollow(output)
    for name, files in (("candidate", candidate), ("adapter", adapter)):
        for relative, raw in files.items():
            write_owner_file(output / name / relative, raw)
    record = {
        "status": "not-run", "authoringExpectationsOnly": True,
        "materializationId": uuid.uuid4().hex,
        "taskKey": manifest.task_key, "control": control,
        "manifestCaseCount": len(manifest.cases),
        "candidateSource": secure_tree_hash(output / "candidate"),
        "adapterSource": secure_tree_hash(output / "adapter"),
        "rubric": manifest.rubric_hash(),
        "compileValidated": False, "engineValidated": False,
        "nextStep": (
            "Compile these exact sources and adapter; evaluate with new identity and matching immutable "
            "role artifacts. Never reuse canonical adapter evidence for a fixture mutation."
        ),
    }
    write_owner_file(output / "private-plan.json", (json.dumps(record, indent=2) + "\n").encode())
    return output


if __name__ == "__main__":
    selected, destination = sys.argv[1:]
    print(materialize(Path(__file__).resolve().parent.parent, selected, Path(destination)))
