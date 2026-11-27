from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from rhenium_contract.plugin import ContractBenchmarkPlugin
from rhenium_rimworld.assertions import generated_dispatch_source
from rhenium_rimworld.catalog import (
    RimWorldCatalog,
    assertion_manifest,
    expected_case_names,
)
from rhenium_rimworld.evaluator import (
    RUNTIME_KEY,
    SUBMISSION_BUILD_FAILED,
    VERIFIER_BUILD_FAILED,
    RimWorldEvaluator,
    RimWorldRuntime,
    RuntimeExecution,
    build_failure_log,
)
from rhenium_rimworld.plugin import RimWorldBenchmarkPlugin
from rhenium_rimworld.runtime_builder import RimWorldRuntimeBuilder
from rhenium_rimworld.safe_files import UnsafePathError, secure_read_bytes, secure_tree_hash
from rhenium_rimworld.supervisor import (
    ADAPTER,
    EvidenceError,
    collect_observations,
    encode_private_verdict,
    strict_json_object,
    validate_private_verdict,
)

from rhenium.config import Settings
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog
from rhenium.hub import BenchmarkHub

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "rimworld-core"
TASK_ID = "r4-uncraftable-material-basis"
EMPTY_HASH = "sha256:" + hashlib.sha256(b"").hexdigest()


def _context(tmp_path: Path, pack: Path = PACK) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def _submission(tmp_path: Path, pack: Path = PACK) -> Path:
    destination = tmp_path / "submission"
    destination.mkdir()
    catalog = RimWorldCatalog.load(pack)
    RimWorldBenchmarkPlugin().materialize_attempt(
        catalog.tasks[0], destination, _context(tmp_path, pack)
    )
    return destination


def _identity() -> dict[str, str]:
    identity = {
        field: "sha256:" + hashlib.sha256(field.encode()).hexdigest()
        for field in (
            "catalog",
            "rubric",
            "submission",
            "candidateAssembly",
            "adapterAssembly",
            "runtimeFingerprint",
            "runtimeArtifact",
            "builderImage",
            "evaluatorImage",
            "buildEvidence",
            "adapterEvidence",
            "sourceEvidence",
        )
    }
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    identity["rubric"] = assertions.rubric_hash()
    return identity


def _observation(
    names: tuple[str, ...],
    *,
    evaluation_id: str,
    nonce: str,
    task_key: str,
    failed_case: str | None = None,
) -> bytes:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    cases = []
    for name in names:
        spec = assertions.by_id[name]
        observed: list[dict[str, Any]] = [
            {
                "channel": output.channel,
                "entries": [
                    {"defName": entry.def_name, "count": entry.count}
                    for entry in output.entries
                ],
            }
            for output in spec.expected.outputs
        ]
        if name == failed_case and observed:
            observed[0]["entries"][0]["count"] += 1
        cases.append(
            {
                "id": name,
                "error": "",
                "facts": [
                    {"name": fact.name, "value": fact.value}
                    for fact in spec.expected.facts
                ],
                "scalars": [
                    {
                        "name": scalar_name,
                        "value": float(index + 1),
                        "bits": f"{struct.unpack('<I', struct.pack('<f', float(index + 1)))[0]:08x}",
                    }
                    for index, scalar_name in enumerate(spec.scalars)
                ],
                "outputs": observed,
            }
        )
    return json.dumps(
        {
            "schema": 2,
            "adapter": ADAPTER,
            "evaluationId": evaluation_id,
            "nonce": nonce,
            "taskKey": task_key,
            "realGame": True,
            "gameVersion": "1.6.4871 rev-test",
            "unityVersion": "2022.3.35f1",
            "terminalMarker": f"RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}",
            "fatal": "",
            "cases": cases,
        },
        separators=(",", ":"),
    ).encode()


def _observation_for_manifest(
    assertions: Any, *, evaluation_id: str, nonce: str, task_key: str
) -> bytes:
    cases = [
        {
            "id": case.id,
            "error": "",
            "facts": [
                {"name": fact.name, "value": fact.value}
                for fact in case.expected.facts
            ],
            "scalars": [],
            "outputs": [
                {
                    "channel": output.channel,
                    "entries": [
                        {"defName": entry.def_name, "count": entry.count}
                        for entry in output.entries
                    ],
                }
                for output in case.expected.outputs
            ],
        }
        for case in assertions.cases
    ]
    return json.dumps(
        {
            "schema": assertions.schema_version,
            "adapter": assertions.adapter,
            "evaluationId": evaluation_id,
            "nonce": nonce,
            "taskKey": task_key,
            "realGame": True,
            "gameVersion": "1.6.4871 rev-test",
            "unityVersion": "2022.3.35f1",
            "terminalMarker": f"RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}",
            "fatal": "",
            "cases": cases,
        },
        separators=(",", ":"),
    ).encode()


def test_catalog_and_plugin_contract() -> None:
    catalog = RimWorldCatalog.load(PACK)
    runtime_catalog = RuntimeCatalog.load(PACK, "runtimes.json")
    task = catalog.tasks[0]
    plugin = RimWorldBenchmarkPlugin()

    assert catalog.id == "rimworld-core"
    assert catalog.version == "0.5.0"
    assert catalog.game == "rimworld"
    assert len(catalog.tasks) == 10
    assert len({item.id for item in catalog.tasks}) == 10
    assert len({item.starter_root for item in catalog.tasks}) == 9
    assert len({item.package_id for item in catalog.tasks}) == 9
    assert set(runtime_catalog.task_bindings) == {item.id for item in catalog.tasks}
    assert all(
        bindings == ("rimworld-1.6.4871-linux-x64",)
        for bindings in runtime_catalog.task_bindings.values()
    )
    assert task.id == TASK_ID
    assert task.source_commit == "db9e85bc758c402e53c55dd19ca8a588899f139c"
    assert task.source_target_commit == "7fbf158f4b988a6f806cc609282175143a3a41a6"
    assert task.source_license == "MIT"
    assert task.private_protocol == "rhenium-rimworld-private-v2"
    assert task.expected_assertions == 38
    assert plugin.descriptor.id == "rimworld"
    assert plugin.task_prompt(task) == task.authored_prompt.strip()
    assert plugin.public_task(task)["gameVersion"] == "1.6.4871"


def test_catalog_drives_starter_metadata_and_assertion_counts_per_task() -> None:
    catalog = RimWorldCatalog.load(PACK)
    counts = {task.id: task.expected_assertions for task in catalog.tasks}
    assert counts == {
        "r4-uncraftable-material-basis": 38,
        "r4-small-bench-ingredient-consumption": 16,
        "project-rimfactory-cultivator-environment": 12,
        "adaptive-storage-slot-limit-restore": 15,
        "combat-readiness-colony-wealth": 16,
        "customize-weapon-ability-tracker": 18,
        "total-control-vanilla-gear-generation": 18,
        "bill-autopilot-repeat-mode-ownership": 17,
        "playwright-nonbulk-trade-accounting": 14,
        "research-organized-tab-state": 22,
    }
    for task in catalog.tasks:
        assertions = assertion_manifest(PACK, task)
        assert len(assertions.cases) == task.expected_assertions
        assert assertions.protocol == task.private_protocol
        assert task.mod_metadata_path == (
            f"tests/ModMetadata/{task.starter_root}/About.xml"
        )
        assert all(path.startswith(f"{task.starter_root}/") for path in task.required_files)
        assert sum(case.gate for case in assertions.cases) == 2
        assert assertions.weights.submission_shape == 10
        assert assertions.weights.engine_assertions == 90


def test_submission_projects_compile_only_catalog_required_sources() -> None:
    catalog = RimWorldCatalog.load(PACK)
    for task in catalog.tasks:
        project = (
            PACK
            / "private"
            / "harbor"
            / task.id
            / "tests"
            / "Submission.csproj"
        ).read_text(encoding="utf-8")
        assert "<EnableDefaultCompileItems>false</EnableDefaultCompileItems>" in project
        assert "**" not in project
        assert "<ProjectReference" not in project
        assert "Directory.Build" not in project
        assert "assertions.json" not in project
        for required in task.required_files:
            relative = required.removeprefix(f"{task.starter_root}/")
            assert project.count(f'$(SubmissionRoot)/{relative}') == 1


def test_protocol_v3_is_distinct_and_dispatch_has_no_expected_values() -> None:
    catalog = RimWorldCatalog.load(PACK)
    for task in catalog.tasks[1:]:
        assertions = assertion_manifest(PACK, task)
        generated = generated_dispatch_source(assertions).decode("utf-8")
        task_root = PACK / "private" / "harbor" / task.id
        verifier = (task_root / "tests/Harness/Verifier.cs").read_text(encoding="utf-8")
        test_script = (task_root / "tests/test.sh").read_text(encoding="utf-8")
        assert assertions.schema_version == 3
        assert assertions.adapter == "rhenium-rimworld-observer-v3"
        assert assertions.collector == "rhenium-rimworld-supervisor-v3"
        assert "expected" not in generated
        assert all(generated.count(f'"{case.id}"') == 1 for case in assertions.cases)
        assert all(case.id not in verifier for case in assertions.cases)
        assert all(case.id not in test_script for case in assertions.cases)


def test_task_controls_record_engine_evidence_and_prompts_stay_nonrevealing() -> None:
    catalog = RimWorldCatalog.load(PACK)
    for task in catalog.tasks:
        task_root = PACK / "private" / "harbor" / task.id
        assertion_path = task_root / "tests/assertions.json"
        controls = json.loads(
            (task_root / "validation/controls.json").read_text(encoding="utf-8")
        )
        assertions = assertion_manifest(PACK, task)
        prompt = (PACK / "exams" / f"{task.id}.md").read_text(encoding="utf-8")
        assert controls["assertionManifestSha256"] == hashlib.sha256(
            assertion_path.read_bytes()
        ).hexdigest()
        assert controls["plannedMatrix"]["oracle"] == {
            "expectedPassed": task.expected_assertions,
            "expectedFailed": 0,
        }
        assert not any(case.id in prompt for case in assertions.cases)
        assert list(task_root.rglob("assertions.json")) == [assertion_path]
        if task.id == "adaptive-storage-slot-limit-restore":
            # Revision 6 ran in the game; revision 5's compile-only record stays as history.
            assert controls["authoringRevision"] == 6
            assert controls["history"][-1]["evidenceGeneration"]["status"] == "blocked"
            assert controls["history"][-1]["engineAssertionsRan"] is False
            planned = {item["id"]: item for item in json.loads(
                (task_root / "validation/mutation-controls.json").read_text(encoding="utf-8")
            )["mutations"]}
            behavioral = controls["negativeControls"]["behavioral"]
            assert {item["control"] for item in behavioral} == set(planned)
            for item in behavioral:
                assert item["complete"] is True and item["detectedIntendedDefect"] is True
                assert set(planned[item["control"]]["mustFailCases"]) <= set(item["failedCases"])
            fixtures = controls["negativeControls"]["fixture"]
            assert len(fixtures) == 5
            assert all(item["complete"] is False and item["failedClosed"] is True for item in fixtures)
        # Every task ran two-way in the pinned game; the record names its runs.
        assert controls["engineAssertionsRan"] is True
        assert controls["evidenceGeneration"]["status"] == "run"
        for name in ("referenceCompile", "containerBuild", "realEngine"):
            if name in controls:
                assert controls[name]["status"] == "passed"
        oracle = controls["oracle"]
        assert oracle["status"] == "passed"
        assert oracle["identicalCaseOutcomes"] is True
        assert len(set(oracle["runs"])) == 3
        assert (oracle["passed"], oracle["failed"]) == (task.expected_assertions, 0)
        for control_name in ("base", "nop"):
            observed = controls[control_name]
            assert observed["status"] == "failed-targets-only"
            assert observed["passed"] + observed["failed"] == task.expected_assertions
            assert observed["failed"] == len(observed["failedCases"]) > 0
            assert set(observed["failedCases"]) <= set(assertions.case_names)
        assert controls["base"]["failedCases"] == controls["nop"]["failedCases"]


def test_supervisor_binds_v3_evidence_to_task_and_rubric() -> None:
    task = RimWorldCatalog.load(PACK).tasks[3]
    assertions = assertion_manifest(PACK, task)
    evaluation_id = "evaluation-" + "3" * 24
    nonce = "4" * 48
    task_key = f"rimworld/core/{task.id}"
    identity = _identity()
    identity["rubric"] = assertions.rubric_hash()
    raw = _observation_for_manifest(
        assertions, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key
    )
    verdict = collect_observations(
        raw,
        assertions=assertions,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        process_status=0,
        player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
        identity=identity,
    )
    assert verdict["schema"] == 3
    assert verdict["collector"] == "rhenium-rimworld-supervisor-v3"
    assert verdict["complete"] is True
    assert verdict["reward"] == 1

    with pytest.raises(EvidenceError, match="task identity"):
        collect_observations(
            raw,
            assertions=assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[4]),
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
            process_status=0,
            player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=identity,
        )


def test_private_protocol_v2_has_one_38_case_source_of_truth() -> None:
    task = RimWorldCatalog.load(PACK).tasks[0]
    assertions = assertion_manifest(PACK, task)
    generated = generated_dispatch_source(assertions).decode("utf-8")
    verifier = (
        PACK / "private" / "harbor" / TASK_ID / "tests" / "Harness" / "Verifier.cs"
    ).read_text(encoding="utf-8")
    test_script = (
        PACK / "private" / "harbor" / TASK_ID / "tests" / "test.sh"
    ).read_text(encoding="utf-8")

    assert len(assertions.cases) == 38
    assert assertions.weights.submission_shape == 10
    assert assertions.weights.engine_assertions == 90
    assert sum(case.gate for case in assertions.cases) == 2
    assert "expected" not in generated
    assert "ThingDefOf" not in generated
    for case in assertions.cases:
        assert generated.count(f'"{case.id}"') == 1
        assert f'"{case.id}"' not in verifier
        assert case.id not in test_script

    task_root = PACK / "private" / "harbor" / TASK_ID
    assertions_raw = (task_root / "tests" / "assertions.json").read_bytes()
    controls = json.loads(
        (task_root / "validation" / "controls.json").read_text(encoding="utf-8")
    )
    assert controls["schemaVersion"] == 2
    assert controls["catalogVersion"] == "0.2.0"
    assert controls["privateProtocol"] == assertions.protocol
    assert controls["assertionManifestSha256"] == hashlib.sha256(
        assertions_raw
    ).hexdigest()
    assert controls["plannedMatrix"] == {
        "oracle": {"expectedPassed": 38, "expectedFailed": 0},
        "base": {"expectedPassed": 7, "expectedFailed": 31},
        "nop": {"expectedPassed": 7, "expectedFailed": 31},
    }
    # The 2026-09-24 real-game runs observed exactly the planned v2 matrix.
    assert controls["engineAssertionsRan"] is True
    assert controls["oracle"]["status"] == "passed"
    assert (controls["oracle"]["passed"], controls["oracle"]["failed"]) == (38, 0)
    for name in ("base", "nop"):
        assert controls[name]["status"] == "failed-targets-only"
        assert (controls[name]["passed"], controls[name]["failed"]) == (7, 31)


def test_catalog_rejects_traversal_and_pack_symlinks(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="normalized and relative"):
        RimWorldCatalog.load(PACK, "../catalog.json")

    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    raw = json.loads((copied / "catalog.json").read_text(encoding="utf-8"))
    raw["tasks"][0]["required_files"] = ["R4/../private/test.cs"]
    (copied / "catalog.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="required_files"):
        RimWorldCatalog.load(copied)

    shutil.rmtree(copied)
    shutil.copytree(PACK, copied)
    target = copied / "catalog.real.json"
    (copied / "catalog.json").replace(target)
    (copied / "catalog.json").symlink_to(target.name)
    with pytest.raises(ValueError, match="symbolic link"):
        RimWorldCatalog.load(copied)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ('"version": "0.5.0", "version": "0.5.0"', "duplicate RimWorld catalog key"),
        ('"estimated_minutes": NaN', "non-finite RimWorld catalog value"),
        ('"estimated_minutes": Infinity', "non-finite RimWorld catalog value"),
        ('"estimated_minutes":', "malformed"),
    ],
)
def test_catalog_rejects_duplicate_nonfinite_and_malformed_json(
    tmp_path: Path, replacement: str, message: str
) -> None:
    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    catalog_path = copied / "catalog.json"
    text = catalog_path.read_text(encoding="utf-8")
    if replacement.startswith('"version"'):
        text = text.replace('"version": "0.5.0"', replacement, 1)
    else:
        text = text.replace('"estimated_minutes": 120', replacement, 1)
    catalog_path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        RimWorldCatalog.load(copied)


def test_catalog_rejects_malformed_private_assertion_manifest(tmp_path: Path) -> None:
    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    assertions = copied / "private" / "harbor" / TASK_ID / "tests" / "assertions.json"
    text = assertions.read_text(encoding="utf-8")
    assertions.write_text(
        text.replace(
            '"schemaVersion": 2,',
            '"schemaVersion": 2, "schemaVersion": 2,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate assertion manifest key"):
        RimWorldCatalog.load(copied)

    shutil.rmtree(copied)
    shutil.copytree(PACK, copied)
    assertions = copied / "private" / "harbor" / TASK_ID / "tests" / "assertions.json"
    payload = json.loads(assertions.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    assertions.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected"):
        RimWorldCatalog.load(copied)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_assertions", 99, "fixture declaration"),
        ("private_protocol", "rhenium-rimworld-private-v2", "fixture declaration"),
        ("mod_metadata_path", "tests/ModMetadata/Other/About.xml", "task-owned path"),
        ("starter_root", "../escape", "string_pattern_mismatch"),
    ],
)
def test_catalog_rejects_task_metadata_manifest_mismatch(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    catalog_path = copied / "catalog.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    payload["tasks"][1][field] = value
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        RimWorldCatalog.load(copied)


def test_materializer_uses_only_task_owned_targets(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    task = catalog.tasks[0]
    plugin = RimWorldBenchmarkPlugin()
    arbitrary = tmp_path / "arbitrary"
    arbitrary.mkdir()
    marker = arbitrary / "user.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="task-owned"):
        plugin.materialize_starter(task, arbitrary, _context(tmp_path))
    assert marker.read_text(encoding="utf-8") == "preserve"

    owned = _context(tmp_path).state_dir / "workspaces" / task.id
    plugin.materialize_starter(task, owned, _context(tmp_path))
    assert (owned / "R4" / "Source" / "Utility" / "MaterialUtility.cs").is_file()


def test_materializer_uses_each_catalog_starter_root(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    plugin = RimWorldBenchmarkPlugin()
    for task in (catalog.tasks[2], catalog.tasks[8]):
        context = _context(tmp_path / task.id)
        owned = context.state_dir / "workspaces" / task.id
        plugin.materialize_starter(task, owned, context)
        assert (owned / task.starter_root / "LICENSE").is_file()
        assert {
            path.relative_to(owned).as_posix()
            for path in owned.rglob("*.cs")
        } == set(task.required_files)


def test_materialized_attempt_contains_only_public_files(tmp_path: Path) -> None:
    destination = _submission(tmp_path)
    files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    assert files == {
        "AGENTS.md",
        "CLAUDE.md",
        "EXAM.md",
        "R4/LICENSE",
        "R4/Source/Defs/R4MaterialCostExtension.cs",
        "R4/Source/Utility/MaterialUtility.cs",
        "task.json",
    }
    text = "\n".join(path.read_text(encoding="utf-8") for path in destination.rglob("*") if path.is_file())
    assert str(PACK) not in text
    assert TASK_ID not in text
    assert "private/harbor" not in text
    assert "Verifier.cs" not in text


def test_submission_snapshot_rejects_symlinks_special_files_and_binaries(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    task = catalog.tasks[0]
    submission = _submission(tmp_path)
    outside = tmp_path / "outside.cs"
    outside.write_text("private host content", encoding="utf-8")
    (submission / "R4" / "escape.cs").symlink_to(outside)
    digest, check = RimWorldEvaluator._snapshot_submission(
        submission, task, tmp_path / "snapshot"
    )
    assert digest == EMPTY_HASH
    assert check["status"] == "failed"

    (submission / "R4" / "escape.cs").unlink()
    os.mkfifo(submission / "R4" / "pipe")
    digest, _check = RimWorldEvaluator._snapshot_submission(
        submission, task, tmp_path / "snapshot-special"
    )
    assert digest == EMPTY_HASH
    (submission / "R4" / "pipe").unlink()

    (submission / "R4" / "candidate.dll").write_bytes(b"not a dll")
    digest, _check = RimWorldEvaluator._snapshot_submission(
        submission, task, tmp_path / "snapshot-binary"
    )
    assert digest == EMPTY_HASH


def test_safe_snapshot_rejects_hardlinks_and_mid_read_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = root / "source.cs"
    source.write_bytes(b"source")
    os.link(source, root / "alias.cs")
    with pytest.raises(UnsafePathError, match="non-linked regular file"):
        secure_read_bytes(root, "source.cs")

    (root / "alias.cs").unlink()
    real_fstat = os.fstat
    calls = 0

    def changed_fstat(fd: int) -> os.stat_result:
        nonlocal calls
        value = real_fstat(fd)
        calls += 1
        if calls == 2:
            fields = list(value)
            fields[8] = value.st_mtime + 1
            return os.stat_result(fields)
        return value

    monkeypatch.setattr("rhenium_rimworld.safe_files.os.fstat", changed_fstat)
    with pytest.raises(UnsafePathError, match="changed while"):
        secure_read_bytes(root, "source.cs")


def test_snapshot_compiles_only_the_bytes_that_were_hashed(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    task = catalog.tasks[0]
    submission = _submission(tmp_path)
    (submission / "candidate.csproj").write_text("<Project>hostile</Project>", encoding="utf-8")
    (submission / "Directory.Build.targets").write_text("hostile", encoding="utf-8")
    snapshot = tmp_path / "snapshot"

    digest, check = RimWorldEvaluator._snapshot_submission(submission, task, snapshot)
    snapshotted = {
        path.relative_to(snapshot).as_posix()
        for path in snapshot.rglob("*")
        if path.is_file()
    }
    assert check["status"] == "passed"
    assert digest.startswith("sha256:")
    assert snapshotted == set(task.required_files)


def test_core_and_invalid_profiles_fail_closed_without_docker(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    task = catalog.tasks[0]
    evaluator = RimWorldEvaluator(_context(tmp_path), catalog)
    evaluator.runtime.status = lambda: (_ for _ in ()).throw(AssertionError("no Docker"))  # type: ignore[method-assign]

    core = evaluator.evaluate(_submission(tmp_path), task, profile="core")
    invalid = evaluator.evaluate(tmp_path / "missing", task, profile="full")
    assert core["score"] == 10.0
    assert core["complete"] is False
    assert invalid["score"] == 0.0
    assert invalid["complete"] is False
    assert re.fullmatch(r"evaluation-[0-9a-f]{24}", core["evaluationId"])


def test_full_profile_fails_closed_without_runtime_artifact(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    result = RimWorldEvaluator(_context(tmp_path), catalog).evaluate(
        _submission(tmp_path), catalog.tasks[0], profile="full", runtimes={}
    )
    assert result["complete"] is False
    assert result["passed"] is False
    assert result["runtime"]["engineAssertionsRan"] is False
    assert result["runtime"]["caseOutcomes"] == {}
    assert f"runtime prepare {RUNTIME_KEY}" in result["runtime_log"]


def test_supervisor_accepts_complete_behavior_failure_but_rejects_replay() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    raw = _observation(
        names,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        failed_case="craftable-cost-preserved",
    )
    raw_object = json.loads(raw)
    assert "reward" not in raw_object
    assert "expected" not in raw_object
    assert all("status" not in case for case in raw_object["cases"])
    verdict = collect_observations(
        raw,
        assertions=assertions,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        process_status=0,
        player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
        identity=_identity(),
    )
    assert verdict["complete"] is True
    assert verdict["reward"] == 0
    assert verdict["failed"] == 1

    with pytest.raises(EvidenceError, match="identity"):
        collect_observations(
            raw,
            assertions=assertions,
            evaluation_id="evaluation-" + "c" * 24,
            nonce=nonce,
            task_key=task_key,
            process_status=0,
            player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=_identity(),
        )

    stale_identity = _identity()
    stale_identity["rubric"] = "sha256:" + "0" * 64
    with pytest.raises(EvidenceError, match="rubric identity"):
        collect_observations(
            raw,
            assertions=assertions,
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
            process_status=0,
            player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=stale_identity,
        )


def test_supervisor_rejects_multiple_terminals_and_abnormal_exit() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    raw = _observation(
        names,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
    )
    marker = f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n"
    for process_status, log in ((0, marker * 2), (2, marker)):
        verdict = collect_observations(
            raw,
            assertions=assertions,
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
            process_status=process_status,
            player_log=log,
            identity=_identity(),
        )
        assert verdict["complete"] is False
        assert verdict["reward"] == 0
        assert verdict["cases"] == []


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":2,"schema":2}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'[]',
    ],
)
def test_strict_json_rejects_duplicate_nonfinite_or_wrong_top_level(raw: bytes) -> None:
    with pytest.raises(EvidenceError):
        strict_json_object(raw)


def test_supervisor_rejects_missing_extra_duplicate_and_unknown_case_fields() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    base = json.loads(
        _observation(names, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key)
    )
    variants = []
    for cases in (
        base["cases"][:-1],
        [*base["cases"], {**base["cases"][0], "id": "extra"}],
        [*base["cases"], base["cases"][0]],
    ):
        variant = dict(base)
        variant["cases"] = cases
        variants.append(variant)
    unknown = dict(base)
    unknown["cases"] = [dict(base["cases"][0], unexpected=True), *base["cases"][1:]]
    variants.append(unknown)

    for variant in variants:
        try:
            verdict = collect_observations(
                json.dumps(variant).encode(),
                assertions=assertions,
                evaluation_id=evaluation_id,
                nonce=nonce,
                task_key=task_key,
                process_status=0,
                player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
                identity=_identity(),
            )
        except EvidenceError:
            continue
        assert verdict["complete"] is False


def test_supervisor_rejects_values_outside_float32_range() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    observation = json.loads(
        _observation(names, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key)
    )
    observation["cases"][7]["scalars"][0]["value"] = 1e308

    with pytest.raises(EvidenceError, match="float32"):
        collect_observations(
            json.dumps(observation).encode(),
            assertions=assertions,
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
            process_status=0,
            player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=_identity(),
        )


def test_supervisor_rejects_scalar_bit_mismatch_and_fails_closed_on_gate() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    observation = json.loads(
        _observation(names, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key)
    )
    observation["cases"][7]["scalars"][0]["bits"] = "00000000"
    with pytest.raises(EvidenceError, match="float32 bits"):
        collect_observations(
            json.dumps(observation).encode(),
            assertions=assertions,
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
            process_status=0,
            player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=_identity(),
        )

    gate_failure = json.loads(
        _observation(names, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key)
    )
    gate_failure["cases"][0]["facts"][0]["value"] = "false"
    verdict = collect_observations(
        json.dumps(gate_failure).encode(),
        assertions=assertions,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        process_status=0,
        player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
        identity=_identity(),
    )
    assert verdict["complete"] is False
    assert verdict["cases"] == []


def test_private_verdict_rejects_count_and_reward_contradictions() -> None:
    assertions = assertion_manifest(PACK, RimWorldCatalog.load(PACK).tasks[0])
    names = assertions.case_names
    evaluation_id = "evaluation-" + "a" * 24
    nonce = "b" * 48
    task_key = f"rimworld/core/{TASK_ID}"
    verdict = collect_observations(
        _observation(names, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key),
        assertions=assertions,
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        process_status=0,
        player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
        identity=_identity(),
    )
    for field, value in (("passed", 0), ("failed", 1), ("reward", 0)):
        malformed = {**verdict, field: value}
        with pytest.raises(EvidenceError, match="contradictory"):
            validate_private_verdict(encode_private_verdict(malformed), assertions)


def test_runtime_command_is_sandboxed_and_uses_only_snapshot_assemblies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = RimWorldCatalog.load(PACK)
    runtime = RimWorldRuntime(_context(tmp_path), catalog)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    for relative in catalog.tasks[0].required_files:
        path = snapshot / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    calls: list[list[str]] = []
    nonce = "b" * 48
    evaluation_id = "evaluation-" + "a" * 24
    task_key = f"rimworld/core/{TASK_ID}"

    def fake_run(
        arguments: list[str], *, name: str, labels: dict[str, str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        del name, labels, timeout
        calls.append(arguments)
        if "/opt/rhenium/build.sh" in arguments:
            output = evidence / "build-output"
            (output / "candidate").mkdir(parents=True, exist_ok=True)
            (output / "verifier").mkdir(parents=True, exist_ok=True)
            (output / "candidate" / "RRRR.dll").write_bytes(b"candidate")
            (output / "verifier" / "RheniumRimWorldVerifier.dll").write_bytes(b"adapter")
        else:
            logs = evidence / "runtime" / "verifier"
            logs.mkdir(parents=True, exist_ok=True)
            names = expected_case_names(PACK, catalog.tasks[0])
            (logs / "observations.json").write_bytes(
                _observation(
                    names,
                    evaluation_id=evaluation_id,
                    nonce=nonce,
                    task_key=task_key,
                )
            )
            (logs / "Player.log").write_text(
                f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(arguments, 0, "", "")

    def fake_inspect(
        arguments: list[str], *, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        assert arguments[:2] == ["container", "inspect"]
        return subprocess.CompletedProcess(arguments, 1, "", "No such container")

    monkeypatch.setattr(runtime, "_docker", fake_inspect)
    monkeypatch.setattr(runtime, "_run_container", fake_run)
    monkeypatch.setattr(runtime, "_copy_owned_logs", lambda *_args: None)
    execution = runtime.execute(
        catalog.tasks[0],
        snapshot=snapshot,
        evidence_dir=evidence,
        images={"builder": "sha256:" + "1" * 64, "evaluator": "sha256:" + "2" * 64},
        evaluation_id=evaluation_id,
        nonce=nonce,
        task_key=task_key,
        submission_hash=EMPTY_HASH,
    )

    assert execution.engine_process is not None
    for command in calls:
        assert "--network=none" in command
        assert "--read-only" in command
        assert "--cap-drop=ALL" in command
        assert "--security-opt=no-new-privileges:true" in command
        assert "--pull=never" in command
        assert "/var/run/docker.sock" not in "\n".join(command)
    assert f"type=bind,source={snapshot},target=/submission,readonly" in calls[0]
    assert all("target=/submission" not in value for value in calls[1])
    assert any("target=/assemblies,readonly" in value for value in calls[1])
    # Evidence is bind-mounted: a tmpfs would vanish with the container before it is read.
    assert any("target=/logs" in value and "readonly" not in value for value in calls[1])
    assert not any(value.startswith("/logs:") for value in calls[1])
    # Unity needs a writable HOME or it dies before the first assertion.
    assert "HOME=/tmp" in calls[1]


class TimeoutDocker:
    def __init__(self, *, owned: bool = True, status: str = "running") -> None:
        self.calls: list[list[str]] = []
        self.owned = owned
        self.removed = False
        self.status = status

    def __call__(
        self, arguments: list[str], *, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(arguments)
        if arguments[0] == "run":
            raise subprocess.TimeoutExpired(arguments, timeout)
        if arguments[:2] == ["container", "inspect"]:
            if self.removed:
                return subprocess.CompletedProcess(arguments, 1, "", "No such container")
            name = arguments[2]
            role = "builder" if "build" in name else "evaluator"
            labels = RimWorldRuntime._container_identity(
                f"rimworld/core/{TASK_ID}", "evaluation-" + "a" * 24, role
            )
            if not self.owned:
                labels["io.rhenium.evaluation.id"] = "evaluation-" + "c" * 24
            payload = {
                "Id": "d" * 64,
                "State": {"Status": self.status},
                "Config": {"Labels": labels},
            }
            return subprocess.CompletedProcess(arguments, 0, json.dumps(payload), "")
        if arguments[:3] == ["container", "rm", "--force"]:
            self.removed = True
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[:2] == ["container", "cp"]:
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)


def test_timeout_cleanup_checks_ownership_and_confirms_removal(tmp_path: Path) -> None:
    runtime = RimWorldRuntime(_context(tmp_path), RimWorldCatalog.load(PACK))
    fake = TimeoutDocker()
    runtime._docker = fake  # type: ignore[method-assign]
    labels = runtime._container_identity(
        f"rimworld/core/{TASK_ID}", "evaluation-" + "a" * 24, "builder"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        runtime._run_container(
            ["run"], name="rhenium-rimworld-build-test", labels=labels, timeout=1
        )
    assert fake.removed is True
    assert fake.calls[-1][:2] == ["container", "inspect"]

    unowned = TimeoutDocker(owned=False)
    runtime._docker = unowned  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="unowned"):
        runtime._run_container(
            ["run"], name="rhenium-rimworld-build-test", labels=labels, timeout=1
        )
    assert unowned.removed is False


def test_log_collection_uses_owned_container_id_then_removes_it(tmp_path: Path) -> None:
    runtime = RimWorldRuntime(_context(tmp_path), RimWorldCatalog.load(PACK))
    fake = TimeoutDocker(status="exited")
    runtime._docker = fake  # type: ignore[method-assign]
    labels = runtime._container_identity(
        f"rimworld/core/{TASK_ID}", "evaluation-" + "a" * 24, "evaluator"
    )
    destination = tmp_path / "logs"
    destination.mkdir()

    runtime._copy_owned_logs("rhenium-rimworld-run-test", labels, destination)

    copies = [arguments for arguments in fake.calls if arguments[:2] == ["container", "cp"]]
    assert copies == [["container", "cp", f"{'d' * 64}:/logs/.", str(destination)]]
    assert fake.removed is True
    assert fake.calls[-1][:2] == ["container", "inspect"]


def test_fake_full_pipeline_persists_private_identity_and_returns_generic_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_before = secure_tree_hash(PACK)
    catalog = RimWorldCatalog.load(PACK)
    task = catalog.tasks[0]
    evaluator = RimWorldEvaluator(_context(tmp_path), catalog)
    spec = RuntimeCatalog.load(PACK, "runtimes.json").runtimes[0]
    fake_identity = _identity()
    artifact = RuntimeArtifact(
        runtime_key=RUNTIME_KEY,
        fingerprint=spec.fingerprint(plugin_id="rimworld", plugin_version="0.6.0"),
        kind="docker-image-roles",
        identity=fake_identity["runtimeArtifact"],
        metadata={},
    )
    monkeypatch.setattr(evaluator.runtime, "status", lambda: {"available": True})
    monkeypatch.setattr(RimWorldRuntimeBuilder, "verify", lambda *_args: {"available": True})
    monkeypatch.setattr(
        RimWorldRuntimeBuilder,
        "artifact_task_images",
        lambda *_args: (
            {
                "builder": fake_identity["builderImage"],
                "evaluator": fake_identity["evaluatorImage"],
            },
            {
                "build": fake_identity["buildEvidence"],
                "adapter": fake_identity["adapterEvidence"],
                "source": fake_identity["sourceEvidence"],
            },
        ),
    )

    def fake_execute(
        _task: object,
        *,
        snapshot: Path,
        evidence_dir: Path,
        images: dict[str, str],
        evaluation_id: str,
        nonce: str,
        task_key: str,
        submission_hash: str,
    ) -> RuntimeExecution:
        del _task, snapshot, evidence_dir, images, submission_hash
        names = expected_case_names(PACK, task)
        observation = _observation(
            names,
            evaluation_id=evaluation_id,
            nonce=nonce,
            task_key=task_key,
        )
        return RuntimeExecution(
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            fake_identity["candidateAssembly"],
            fake_identity["adapterAssembly"],
            observation,
            f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            "private stack /secret/path",
        )

    monkeypatch.setattr(evaluator.runtime, "execute", fake_execute)
    result = evaluator.evaluate(
        _submission(tmp_path), task, profile="full", runtimes={RUNTIME_KEY: artifact}
    )
    assert result["complete"] is True
    assert result["passed"] is True
    assert result["score"] == 100.0
    assert result["runtime"]["caseOutcomes"] == {
        name: True for name in expected_case_names(PACK, task)
    }
    anonymous = RimWorldBenchmarkPlugin().sanitize_anonymous_result(
        {"id": "run-1", "result": result}
    )
    assert "caseOutcomes" not in json.dumps(anonymous)
    assert anonymous["result"]["runtime"]["engineAssertionsRan"] is True
    evidence = _context(tmp_path).state_dir / "evaluations" / result["evaluationId"]
    private = json.loads((evidence / "result.private.json").read_text(encoding="utf-8"))
    assert private["taskKey"] == f"rimworld/core/{TASK_ID}"
    assert private["identity"]["runtimeFingerprint"].startswith("sha256:")
    assert (evidence.stat().st_mode & 0o777) == 0o700
    assert ((evidence / "result.private.json").stat().st_mode & 0o777) == 0o600
    assert (evidence / "runtime.private.log").read_text(encoding="utf-8") == (
        "private stack /secret/path"
    )
    assert secure_tree_hash(PACK) == pack_before
    assert "private stack" not in json.dumps(result)
    assert "/secret/path" not in json.dumps(result)


def test_hub_discovers_contract_and_rimworld_with_same_local_task_id(tmp_path: Path) -> None:
    contract_pack = tmp_path / "contract-pack"
    shutil.copytree(ROOT / "benchmarks" / "contract", contract_pack)
    catalog_path = contract_pack / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["tasks"][0]["id"] = TASK_ID
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    state = tmp_path / "state"
    settings = Settings(
        root=tmp_path,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(tmp_path,),
        web_dist=None,
    )
    hub = BenchmarkHub(
        settings,
        plugins={
            "contract": ContractBenchmarkPlugin(),
            "rimworld": RimWorldBenchmarkPlugin(),
        },
        auth_providers={},
        manifest_paths=(contract_pack / "benchmark.json", PACK / "benchmark.json"),
    )
    assert f"contract/conformance/{TASK_ID}" in hub.task_keys
    assert f"rimworld/core/{TASK_ID}" in hub.task_keys


def test_anonymous_core_result_does_not_leak_pack_or_private_evidence(tmp_path: Path) -> None:
    state = tmp_path / "state"
    settings = Settings(
        root=tmp_path,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(PACK.parent,),
        web_dist=None,
    )
    hub = BenchmarkHub(
        settings,
        plugins={"rimworld": RimWorldBenchmarkPlugin()},
        auth_providers={},
        manifest_paths=(PACK / "benchmark.json",),
    )
    attempt = tmp_path.parent / f"rimworld-anonymous-{uuid.uuid4().hex}"
    attempt.mkdir()
    try:
        hub.prepare_attempt(
            f"rimworld/core/{TASK_ID}", attempt, "strict", ROOT / "scripts" / "score-exam"
        )
        result = hub.evaluate_attempt(attempt, profile="core")
    finally:
        shutil.rmtree(attempt)
    public = json.dumps(result)
    assert TASK_ID not in public
    assert str(PACK) not in public
    assert "private/harbor" not in public
    assert "private detail" not in public
    assert "taskKey" not in result
    assert re.fullmatch(r"evaluation-[0-9a-f]{24}", result["result"]["evaluationId"])


def test_pack_source_hashes_and_license_bytes_remain_fixed() -> None:
    task_root = PACK / "private" / "harbor" / TASK_ID
    expected = {
        "environment/R4/Source/Utility/MaterialUtility.cs":
            "44fdab7467d6e2a4127b63a553bd480122c34b714a5571f4750accff20a93000",
        "solution/after/R4/Source/Utility/MaterialUtility.cs":
            "e991f533730cb8b3eb6d78d8a948f04343df83b2f6706253a5300a91cf72efb5",
        "environment/R4/Source/Defs/R4MaterialCostExtension.cs":
            "35c317b1bef1b4a0719fe0aa71533bb7fe7c912ecf0373d0df07ab798e63a746",
        "solution/after/R4/Source/Defs/R4MaterialCostExtension.cs":
            "35c317b1bef1b4a0719fe0aa71533bb7fe7c912ecf0373d0df07ab798e63a746",
        "environment/R4/LICENSE":
            "d9ee28c96b86b3595e4590b77720ac85c37c6fad824217a1b5946b1e1cc48e89",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((task_root / relative).read_bytes()).hexdigest() == digest


def test_new_task_source_and_license_hashes_match_audited_snapshots() -> None:
    expected = {
        "r4-small-bench-ingredient-consumption": (
            "R4/Source/Utility/MaterialUtility.cs",
            "3bc706b83b4234a6f9ff4c6368a0d2cc6624e8b73acb1773a085fd6e9927fd61",
            "9f13adbfc1e21220cc90942408c26fbcf001cc3998a0e2c302f501a2b47a98a0",
            "d94dffcf4684d8dc6f9a0f0b1c18696d8be625a21c0940c037d042daf2160f66",
        ),
        "project-rimfactory-cultivator-environment": (
            "ProjectRimFactory/Source/ProjectRimFactory/CultivatorTools/Building_Cultivator.cs",
            "c3dc20a9bb83a35349268adcc302062e9af894b81a2fea6bb4561e8a5e3d6dab",
            "3876bd2f030854c3c7f45dd5885da0f8f7071a8ac0e3df53bdcef1da6e268a80",
            "6fd82a094b92b574ae9fba95ead292ba191b6ce0922da883cd07552fb9e5e5a0",
        ),
        "adaptive-storage-slot-limit-restore": (
            "AdaptiveStorage/Source/AdaptiveStorage/ThingClass.cs",
            "dbea56f31b75e62a1f0a3e394f4c93e55adaa0923627ca5f5c365f1c2aafe953",
            "7106bc1cbbddc4d7c3c4f55df92ad131520aa2b2411022475bc0c1326744467d",
            "c2f35bfff8d6afe40c93119455bcb6eb3b15f77e71cb31952984157076ec42b2",
        ),
        "combat-readiness-colony-wealth": (
            "CombatReadinessCheck/Source/CRC_Revivified/MarvsMapWealthForStoryTeller.cs",
            "118411801616bdc9bd233fba223b606a8cc42513c478badd8477d9f14c28b21e",
            "69d0d4afe5e9500e36fac1a590b806f8011774797db475f368b0e5b14d124431",
            "b93b4ab4758761c1f6c02e7bd2b6ef7b0ea8491a23c122040533a11de29e4023",
        ),
        "customize-weapon-ability-tracker": (
            "CustomizeWeapon/Source/ThingComps/CompAbilityProvider.cs",
            "d24b82c8db2a663161e1d6691675b46a23e2adfbe161f5afc6327d53b46e330d",
            "c1d6358828bc2e76f24bc93238775a95921813242f526cd68918bd2c689a78f7",
            "deb6a149028b58c009caafe4dd2de2c45df78b28fcfb73c66c06a0ea7fc78ee7",
        ),
        "playwright-nonbulk-trade-accounting": (
            "Playwright/Source/Playwright/Patches/TradeablePatches.cs",
            "81196772511b2ac722dbff465d75900adae2375ac0e812e58fd799347cb9e021",
            "84022baa6ac226a076d0a6924139bf0fb9527181ae39b7c948b70e8735d53ac4",
            "2406e3c1eb097fae75b2bf8aa408604181720b3bed452c5d34abccfdf0fe3add",
        ),
        "zombieland-dynamic-needs-capacities": (
            "Zombieland/Source/Patches.cs",
            "cc09e90121bb8f8d224c55bdf6a3e38afeb9890981d3da4b947184fa64e40c4d",
            "f70510b3c49ef0ba714d5250a55c396b0939774751c14aa96e8076040aed83ec",
            "a5883d0c45eb7e176d3d1631220e7f96e958e37064773d40245ae6db560bbd6d",
        ),
    }
    for task_id, (relative, base_hash, target_hash, license_hash) in expected.items():
        task_root = PACK / "private" / "harbor" / task_id
        root = relative.split("/", 1)[0]
        assert hashlib.sha256(
            (task_root / "environment" / relative).read_bytes()
        ).hexdigest() == base_hash
        assert hashlib.sha256(
            (task_root / "solution/after" / relative).read_bytes()
        ).hexdigest() == target_hash
        assert hashlib.sha256(
            (task_root / "environment" / root / "LICENSE").read_bytes()
        ).hexdigest() == license_hash

    multi_file_expected = {
        "total-control-vanilla-gear-generation": {
            "TotalControl/Source/Patches/ApparelGenPatch.cs": (
                "c8b8d9f2608ed1bc9dcb4ce94dd7d9714c185243f5fc2d42307a19f947db56d5",
                "2c9d5ab4bfb2236ba2228e370ac3ecbbfc2babd0d79fd6bd0d1c92fe3d81a309",
            ),
            "TotalControl/Source/Patches/WeaponGenPatch.cs": (
                "50907f00e606293fff70d995e144d8733e22b06e04a40fa03793cefbd1a75cb1",
                "ae39332bd7cde69ba8a0c5c752a4db1a6b7621c19ae28829455881ddcf0c0fd7",
            ),
        },
        "bill-autopilot-repeat-mode-ownership": {
            "BillAutopilot/Source/Runtime/AutoBillSync.cs": (
                "40ee5323b8eac98cb2dad194b4598f2eb6ed6d111cde3daed981e0aeb6792420",
                "958d89377c714cbdd3575d1a5eec8a6e4c46760a9b6c4590581dca19ebae810c",
            ),
            "BillAutopilot/Source/Runtime/BillMemory.cs": (
                "2e890714c4b567c8c9872b25a0d642d938259224332d04742e9a0a88dbc2debe",
                "953229961b462843805db6761b948eb50a9afe0d3ede8bfe53f3644c002e8f6e",
            ),
            "BillAutopilot/Source/Runtime/RecipeProbe.cs": (
                "a2016b492032bba7081b9d3ed016b57c97c1c9b1fba4c922c5aecb6224a63695",
                "6ae5480e5d486fbef7823815b9beefad867589959879466838e356a41403fafd",
            ),
        },
    }
    license_hashes = {
        "total-control-vanilla-gear-generation": (
            "4c7a76096097621ff71c65b0fbfae1f883800c5ff62679bbfc371f681f2027fb"
        ),
        "bill-autopilot-repeat-mode-ownership": (
            "1a24db0b016bf77e6d15fda1bf27b20c76f9b14f1a21458ba36f2bb3a7d2c908"
        ),
    }
    for task_id, files in multi_file_expected.items():
        task_root = PACK / "private" / "harbor" / task_id
        starter_root = next(
            task.starter_root for task in RimWorldCatalog.load(PACK).tasks
            if task.id == task_id
        )
        for relative, (base_hash, target_hash) in files.items():
            assert hashlib.sha256(
                (task_root / "environment" / relative).read_bytes()
            ).hexdigest() == base_hash
            assert hashlib.sha256(
                (task_root / "solution/after" / relative).read_bytes()
            ).hexdigest() == target_hash
        assert hashlib.sha256(
            (task_root / "environment" / starter_root / "LICENSE").read_bytes()
        ).hexdigest() == license_hashes[task_id]


def test_pack_contains_no_proprietary_or_excluded_assets() -> None:
    forbidden_parts = {"textures", "sounds", "workshop", "steamapps"}
    forbidden_suffixes = {".dll", ".exe", ".so", ".dylib", ".png", ".jpg", ".jpeg"}
    for path in PACK.rglob("*"):
        relative = path.relative_to(PACK)
        assert not ({part.lower() for part in relative.parts} & forbidden_parts)
        if path.is_file():
            assert path.suffix.lower() not in forbidden_suffixes


@pytest.mark.parametrize("index", range(1, 10))
@pytest.mark.parametrize(
    "failure", ["mismatch", "fixture", "cleanup", "gate", "missing", "duplicate", "extra"]
)
def test_v3_fixture_integrity_and_mismatch_are_distinct(index: int, failure: str) -> None:
    """Supervisor contract only; synthetic observations are not engine evidence."""
    task = RimWorldCatalog.load(PACK).tasks[index]
    assertions = assertion_manifest(PACK, task)
    evaluation_id, nonce = "evaluation-" + "8" * 24, "9" * 48
    task_key = f"rimworld/core/{task.id}"
    identity = _identity()
    identity["rubric"] = assertions.rubric_hash()
    observation = json.loads(_observation_for_manifest(
        assertions, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key
    ))
    if failure == "mismatch":
        observation["cases"][1]["facts"][0]["value"] = "production mismatch"
    elif failure in {"fixture", "cleanup"}:
        observation["fatal"] = f"{failure} failed"
    elif failure == "gate":
        observation["cases"][-1]["facts"][0]["value"] = "residual state"
    elif failure == "missing":
        observation["cases"].pop(1)
    elif failure == "duplicate":
        observation["cases"].append(observation["cases"][1])
    else:
        observation["cases"].append({**observation["cases"][1], "id": "unregistered-case"})
    try:
        verdict = collect_observations(
            json.dumps(observation).encode(), assertions=assertions,
            evaluation_id=evaluation_id, nonce=nonce, task_key=task_key,
            process_status=0, player_log=f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n",
            identity=identity,
        )
    except EvidenceError:
        assert failure in {"duplicate", "extra"}
        return
    assert verdict["complete"] is (failure == "mismatch")
    if failure == "mismatch":
        assert verdict["failed"] == 1
    else:
        assert verdict["reward"] == 0
        assert verdict["fatal"] is not None


@pytest.mark.parametrize("index", range(1, 10))
def test_v3_rejects_cleanup_gate_before_behavior(index: int) -> None:
    task = RimWorldCatalog.load(PACK).tasks[index]
    assertions = assertion_manifest(PACK, task)
    value = assertions.model_dump(by_alias=True)
    value["cases"].insert(1, value["cases"].pop())
    with pytest.raises(ValueError, match="gates must bracket"):
        type(assertions).model_validate(value)


@pytest.mark.parametrize("index", range(1, 10))
def test_each_task_adapter_identity_invalidates_after_fixture_edit(tmp_path: Path, index: int) -> None:
    task = RimWorldCatalog.load(PACK).tasks[index]
    copy = tmp_path / "pack"
    shutil.copytree(PACK, copy)
    task_root = copy / "private/harbor" / task.id
    before = RimWorldRuntimeBuilder._adapter_evidence(task_root, task)
    support = task_root / "tests/Support.cs"
    support.write_bytes(support.read_bytes() + b"\n// fixture revision identity probe\n")
    after = RimWorldRuntimeBuilder._adapter_evidence(task_root, task)
    assert before != after
    assert before == RimWorldRuntimeBuilder._adapter_evidence(PACK / "private/harbor" / task.id, task)


def test_frozen_r4_manifest_is_unchanged() -> None:
    raw = (PACK / "private/harbor" / TASK_ID / "tests/assertions.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "ab0f4ca774ce0a626ac0e83849c2eec177f898b32170da0bb85d2320ca0c1be7"
    )


@pytest.mark.parametrize("index", range(1, 10))
@pytest.mark.parametrize(
    "corruption", ["unknown", "duplicate-key", "nan", "infinity", "malformed", "terminals"]
)
def test_v3_rejects_malformed_or_ambiguous_runtime_evidence(index: int, corruption: str) -> None:
    task = RimWorldCatalog.load(PACK).tasks[index]
    assertions = assertion_manifest(PACK, task)
    evaluation_id, nonce = "evaluation-" + "a" * 24, "b" * 48
    task_key = f"rimworld/core/{task.id}"
    identity = _identity()
    identity["rubric"] = assertions.rubric_hash()
    raw = _observation_for_manifest(
        assertions, evaluation_id=evaluation_id, nonce=nonce, task_key=task_key
    )
    log = f"[GCB_RIMWORLD] RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}\n"
    if corruption == "unknown":
        raw = raw.replace(b'{"schema":', b'{"unexpected":true,"schema":', 1)
    elif corruption == "duplicate-key":
        raw = raw.replace(b'{"schema":', b'{"schema":3,"schema":', 1)
    elif corruption in {"nan", "infinity"}:
        value = b"NaN" if corruption == "nan" else b"Infinity"
        raw = raw.replace(b'"realGame":true', b'"realGame":' + value)
    elif corruption == "malformed":
        raw = raw[:-1]
    else:
        log += log
    try:
        verdict = collect_observations(
            raw, assertions=assertions, evaluation_id=evaluation_id, nonce=nonce,
            task_key=task_key, process_status=0, player_log=log, identity=identity,
        )
    except EvidenceError:
        return
    assert verdict["complete"] is False
    assert verdict["reward"] == 0


def test_adaptive_dependency_inventory_matches_both_snapshots_and_compile_inputs() -> None:
    """Source/provenance integrity only; this does not check C# compile closure."""
    task = next(t for t in RimWorldCatalog.load(PACK).tasks
                if t.id == "adaptive-storage-slot-limit-restore")
    root = PACK / "private/harbor" / task.id
    inventory = strict_json_object((root / "validation/dependencies.json").read_bytes())
    assert inventory["status"] == "reference-compiled-engine-unvalidated"
    compiled = {node.attrib["Include"] for node in ET.parse(root / "tests/Submission.csproj").iter("Compile")}
    for item in inventory["dependencies"]:
        relative = item["path"]
        assert f"$(SubmissionRoot)/{relative}" in compiled
        assert f"AdaptiveStorage/{relative}" in task.required_files
        for variant, side in (("base", "environment"), ("target", "solution/after")):
            raw = (root / side / "AdaptiveStorage" / relative).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == item[variant + "Sha256"]
    assert compiled == {"Support.cs", "$(SubmissionRoot)/Source/AdaptiveStorage/ThingClass.cs"} | {
        "$(SubmissionRoot)/" + item["path"] for item in inventory["dependencies"]
    }
    license_hash = hashlib.sha256((root / "environment/AdaptiveStorage/LICENSE").read_bytes()).hexdigest()
    assert license_hash == inventory["licenseSha256"]


def test_adaptive_dependency_edit_changes_build_identity_without_changing_rubric(tmp_path: Path) -> None:
    task = next(t for t in RimWorldCatalog.load(PACK).tasks
                if t.id == "adaptive-storage-slot-limit-restore")
    source = PACK / "private/harbor" / task.id / "environment/AdaptiveStorage"
    copied = tmp_path / "candidate"
    shutil.copytree(source, copied)
    old_source = secure_tree_hash(copied)
    dependency = copied / "Source/AdaptiveStorage/ThingCollection.cs"
    dependency.write_bytes(dependency.read_bytes() + b"\n// dependency identity probe\n")
    new_source = secure_tree_hash(copied)
    assert old_source != new_source
    adapter = RimWorldRuntimeBuilder._adapter_evidence(source.parent.parent, task)
    rubric = assertion_manifest(PACK, task).rubric_hash()
    combine = RimWorldRuntimeBuilder._combined_evidence
    old_build = combine(adapter, EMPTY_HASH, rubric, old_source)
    assert old_build != combine(adapter, EMPTY_HASH, rubric, new_source)
    assert secure_tree_hash(source) == old_source


@pytest.mark.parametrize("control_id", [
    "omit-equipped-sync", "break-holder", "omit-state-save", "omit-postload-clear",
    "break-scribe-transport", "omit-loaded-holder-restoration", "throw-during-restoration",
    "leave-stored-state", "extra-rand-push",
])
def test_authoring_control_materialization_is_hash_bound_and_not_engine_evidence(
    tmp_path: Path, control_id: str,
) -> None:
    task_id = "customize-weapon-ability-tracker"
    task_root = PACK / "private/harbor" / task_id
    before = secure_tree_hash(task_root)
    command = [sys.executable, str(task_root / "validation/materialize_control.py"),
               control_id, str(tmp_path)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = tmp_path / "rimworld/core" / task_id / control_id
    plan = strict_json_object((output / "private-plan.json").read_bytes())
    assert plan["status"] == "not-run" and plan["authoringExpectationsOnly"] is True
    assert plan["manifestCaseCount"] == 18
    assert plan["taskKey"] == f"rimworld/core/{task_id}"
    assert plan["candidateSource"] == secure_tree_hash(output / "candidate")
    assert plan["adapterSource"] == secure_tree_hash(output / "adapter")
    assert not list((output / "candidate").rglob("assertions.json"))
    assert not list((output / "adapter").rglob("assertions.json"))
    item = plan["control"]
    mutation_file = (output / "adapter" / item["source"].removeprefix("tests/")) if "source" in item else (
        output / "candidate/CustomizeWeapon/Source/ThingComps/CompAbilityProvider.cs"
    )
    assert hashlib.sha256(mutation_file.read_bytes()).hexdigest() == item["mutatedSha256"]
    # Existing output is never overwritten; evidence and pack inputs stay unchanged.
    again = subprocess.run(command, check=False, capture_output=True, text=True)
    assert again.returncode != 0 and "already exists" in again.stderr
    assert secure_tree_hash(task_root) == before


def test_control_materializer_rejects_modified_oracle_before_writing(tmp_path: Path) -> None:
    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    task = copied / "private/harbor/customize-weapon-ability-tracker"
    oracle = task / "solution/after/CustomizeWeapon/Source/ThingComps/CompAbilityProvider.cs"
    oracle.write_bytes(oracle.read_bytes() + b"\n// unreviewed source\n")
    state = tmp_path / "state"
    result = subprocess.run([sys.executable, str(task / "validation/materialize_control.py"),
                             "omit-equipped-sync", str(state)], capture_output=True, text=True, check=False)
    assert result.returncode != 0 and "source hash mismatch" in result.stderr
    assert not state.exists()


SUBMISSION_ERROR = (
    "/submission/Mod/Source/A.cs(3,5): error CS0117: 'X' has no 'Y' "
    "[/opt/rhenium/tests/Submission.csproj]"
)


@pytest.mark.parametrize(
    ("errors", "expected"),
    [
        ([SUBMISSION_ERROR], SUBMISSION_BUILD_FAILED),
        (["/opt/rhenium/tests/Harness/Verifier.cs(9,1): error CS1002: ; expected "
          "[/opt/rhenium/tests/Harness/Harness.csproj]"], VERIFIER_BUILD_FAILED),
        ([SUBMISSION_ERROR,
          "/opt/rhenium/tests/Harness/Verifier.cs(9,1): error CS1002: ; expected "
          "[/opt/rhenium/tests/Harness/Harness.csproj]"], VERIFIER_BUILD_FAILED),
        (["docker: Error response from daemon: no space left on device"], "RimWorld build failed"),
    ],
)
def test_build_failure_log_attributes_only_compiler_errors(errors: list[str], expected: str) -> None:
    log = build_failure_log("\n".join(["Determining projects to restore...", *errors, "Build FAILED."]))
    assert log.startswith(expected) and log.endswith("; private evidence was recorded\n")
    # The study adjudicates on this exact line; it never carries compiler output.
    assert "error" not in log.removeprefix(expected)
