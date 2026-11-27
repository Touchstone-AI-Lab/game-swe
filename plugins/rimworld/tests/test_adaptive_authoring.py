"""Integrity and materialization tests, explicitly not C# behavior evidence."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from rhenium_rimworld.safe_files import secure_tree_hash

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "benchmarks/rimworld-core/private/harbor/adaptive-storage-slot-limit-restore"
PLAN = json.loads((TASK / "validation/mutation-controls.json").read_text())
CONTROLS = ["base", "nop", "oracle"] + [
    item["id"] for item in PLAN["mutations"] + PLAN["fixtureMutations"]
]


def invoke(tool: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(tool), *args], text=True,
                          capture_output=True, check=False)


@pytest.mark.parametrize("control", CONTROLS)
def test_control_is_independent_and_bound_to_current_sources(tmp_path: Path, control: str) -> None:
    before = secure_tree_hash(TASK)
    tool = TASK / "validation/materialize_control.py"
    result = invoke(tool, control, str(tmp_path))
    assert result.returncode == 0, result.stderr
    output = tmp_path / "rimworld/core" / TASK.name / control
    record = json.loads((output / "private-plan.json").read_text())
    assert record["candidateSource"] == secure_tree_hash(output / "candidate")
    assert record["adapterSource"] == secure_tree_hash(output / "adapter")
    assert record["status"] == "not-run" and record["compileValidated"] is False
    assert record["engineValidated"] is False and record["manifestCaseCount"] == 15
    assert not list((output / "candidate").rglob("assertions.json"))
    assert not list((output / "adapter").rglob("assertions.json"))
    assert not list(output.rglob("ThingClass 2.cs"))
    item = record["control"]
    if "mutatedSha256" in item:
        assert hashlib.sha256((output / item["surface"] / item["source"]).read_bytes()).hexdigest() == (
            item["mutatedSha256"]
        )
    assert "already exists" in invoke(tool, control, str(tmp_path)).stderr
    assert secure_tree_hash(TASK) == before


def test_base_nop_are_independently_materialized(tmp_path: Path) -> None:
    tool = TASK / "validation/materialize_control.py"
    for control in ["base", "nop"]:
        assert invoke(tool, control, str(tmp_path)).returncode == 0
    base = tmp_path / "rimworld/core" / TASK.name / "base"
    nop = base.with_name("nop")
    assert secure_tree_hash(base / "candidate") == secure_tree_hash(nop / "candidate")
    assert json.loads((base / "private-plan.json").read_text())["materializationId"] != (
        json.loads((nop / "private-plan.json").read_text())["materializationId"]
    )
    a = base / "candidate/AdaptiveStorage/Source/AdaptiveStorage/ThingClass.cs"
    b = nop / a.relative_to(base)
    assert not os.path.samefile(a, b)


@pytest.mark.parametrize("variant", ["base", "oracle"])
def test_reconstruction_replays_same_fixed_inputs(tmp_path: Path, variant: str) -> None:
    # The source snapshot is itself pinned by the derivation manifest. Network is not required.
    upstream = tmp_path / "input"
    shutil.copytree(TASK / "solution/after/AdaptiveStorage", upstream)
    shutil.copyfile(TASK / "environment/AdaptiveStorage/LICENSE", upstream / "LICENSE")
    plan = json.loads((TASK / "validation/source-derivation.json").read_text())
    for item in plan["files"]:
        source = upstream / item["path"]
        raw = source.read_bytes()
        for adaptation in reversed(item.get("adaptations", [])):
            assert raw.count(adaptation["with"].encode()) == 1
            raw = raw.replace(adaptation["with"].encode(), adaptation["replaceOnce"].encode(), 1)
        assert hashlib.sha256(raw).hexdigest() == item["upstreamSha256"]
        source.write_bytes(raw)
    tool = TASK / "validation/reconstruct_source.py"
    output = tmp_path / "output"
    result = invoke(tool, str(upstream), str(output), variant)
    assert result.returncode == 0, result.stderr
    side = "environment" if variant == "base" else "solution/after"
    for item in plan["files"]:
        assert (output / "AdaptiveStorage" / item["path"]).read_bytes() == (
            TASK / side / "AdaptiveStorage" / item["path"]
        ).read_bytes()
    assert "already exists" in invoke(tool, str(upstream), str(output), variant).stderr
    source = upstream / "Source/AdaptiveStorage/ThingClass.cs"
    source.write_bytes(source.read_bytes() + b"\n// tampered\n")
    rejected = tmp_path / "rejected"
    assert "hash mismatch" in invoke(tool, str(upstream), str(rejected), variant).stderr
    assert not rejected.exists()


@pytest.mark.parametrize("damage", ["dependency", "adapter", "license", "source-symlink"])
def test_controls_reject_unreviewed_bytes_before_output(tmp_path: Path, damage: str) -> None:
    copied = tmp_path / "pack/private/harbor" / TASK.name
    shutil.copytree(TASK, copied)
    if damage == "dependency":
        p = copied / "solution/after/AdaptiveStorage/Source/AdaptiveStorage/ThingCollection.cs"
    elif damage == "adapter":
        p = copied / "tests/Harness/Verifier.cs"
    elif damage == "license":
        p = copied / "environment/AdaptiveStorage/LICENSE"
    else:
        p = copied / "solution/after/AdaptiveStorage/Source/AdaptiveStorage/ThingClass.cs"
        saved = p.with_name("linked.cs")
        p.rename(saved)
        p.symlink_to(saved)
    if damage != "source-symlink":
        p.write_bytes(p.read_bytes() + b"\n// unreviewed\n")
    state = tmp_path / "state"
    result = invoke(copied / "validation/materialize_control.py", "extra-rand-push", str(state))
    assert result.returncode != 0
    assert not state.exists()


def test_authoring_tools_reject_pack_destination(tmp_path: Path) -> None:
    state = TASK / "forbidden-output"
    result = invoke(TASK / "validation/materialize_control.py", "base", str(state))
    assert "outside the benchmark pack" in result.stderr
    assert not state.exists()
    result = invoke(TASK / "validation/reconstruct_source.py", str(tmp_path), str(state), "base")
    assert "outside the benchmark pack" in result.stderr
    assert not state.exists()
    result = invoke(TASK / "validation/reference_compile.py", str(state))
    assert "outside the benchmark pack" in result.stderr
    assert not state.exists()


def test_missing_compiler_is_unavailable_and_cannot_reuse_output(tmp_path: Path) -> None:
    tool = TASK / "validation/reference_compile.py"
    output = tmp_path / "compile"
    result = invoke(tool, str(output), "--dotnet", str(tmp_path / "missing-dotnet"))
    assert result.returncode == 2
    report = json.loads((output / "compile.json").read_text())
    assert report["status"] == "unavailable"
    assert report["commands"] == [] and report["controls"] == []
    assert report["compileValidated"] is False and report["engineValidated"] is False
    assert "already exists" in invoke(tool, str(output)).stderr


def test_compile_entry_point_does_not_write_bytecode_into_pack(tmp_path: Path) -> None:
    copied = tmp_path / "pack/private/harbor" / TASK.name
    shutil.copytree(TASK, copied)
    assert not list(copied.rglob("*.pyc"))
    env = os.environ.copy()
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    result = subprocess.run(
        [sys.executable, str(copied / "validation/reference_compile.py"),
         str(tmp_path / "compile"), "--dotnet", str(tmp_path / "missing-dotnet")],
        env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert not list(copied.rglob("*.pyc"))


def test_candidate_and_verifier_locks_match_reviewed_dependency_content() -> None:
    audit = json.loads((TASK / "validation/closure-audit.json").read_text())
    packages = {item["id"]: item for item in audit["packages"]}
    for path in [TASK / "tests/packages.lock.json", TASK / "tests/Harness/packages.lock.json"]:
        lock = json.loads(path.read_text())["dependencies"][".NETFramework,Version=v4.7.2"]
        for name, item in lock.items():
            reviewed = packages[name]
            assert item["resolved"] == reviewed["version"].split("+", 1)[0]
            assert item["contentHash"] == reviewed["contentHash"]
            assert item["contentHash"] != reviewed["archiveSha512"]
