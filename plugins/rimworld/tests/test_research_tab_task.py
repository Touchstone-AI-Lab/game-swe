"""Registration, runtime-input and control-tool checks for the research-tab task, without engine evidence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError
from rhenium_rimworld.assertions import load_assertion_manifest
from rhenium_rimworld.catalog import RimWorldCatalog, RimWorldTask
from rhenium_rimworld.evaluator import RimWorldEvaluator
from rhenium_rimworld.plugin import RimWorldBenchmarkPlugin
from rhenium_rimworld.runtime_builder import RimWorldRuntimeBuilder
from rhenium_rimworld.safe_files import secure_tree_hash

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks/rimworld-core"
TASK_ID = "research-organized-tab-state"
TASK_RELATIVE = f"private/harbor/{TASK_ID}"
TASK_ROOT = PACK / TASK_RELATIVE
SCRIPT = TASK_ROOT / "validation/reference_compile.py"
SOURCE = "Source/ResearchOrganizedMain.cs"
RUNTIME_XML = (
    "tests/ModMetadata/ResearchOrganized/Defs/ResearchTabs.xml",
    "tests/ModMetadata/ResearchOrganized/Defs/TechTreeConfig.xml",
)


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("research_reference_compile", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Loading must not leave a bytecode cache inside the benchmark pack.
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _task(pack: Path = PACK) -> RimWorldTask:
    return next(task for task in RimWorldCatalog.load(pack).tasks if task.id == TASK_ID)


def _context(pack: Path, state: Path) -> BenchmarkContext:
    return BenchmarkContext(project_root=ROOT, pack_root=pack,
                            state_dir=state / "hub", cache_dir=state / "cache")


def _pack_copy(tmp_path: Path) -> Path:
    """A writable pack inside a fixture repository, so the tool's repository guard still applies."""
    repository = tmp_path / "repository"
    pack = repository / "benchmarks/rimworld-core"
    shutil.copytree(PACK, pack)
    (repository / "AGENTS.md").write_text("authoring fixture")
    return pack


def _invoke(pack: Path, state: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    script = pack / TASK_RELATIVE / "validation/reference_compile.py"
    return subprocess.run([sys.executable, str(script), str(state), *arguments],
                          text=True, capture_output=True, check=False)


@pytest.fixture
def materialized(tmp_path: Path) -> Path:
    state = tmp_path / "controls-state"
    _script().materialize_controls(PACK, state)
    return state


def test_task_is_registered_with_its_runtime_definitions() -> None:
    catalog = RimWorldCatalog.load(PACK)
    runtime = RuntimeCatalog.load(PACK, "runtimes.json")
    task = _task()
    assert catalog.version == "0.5.0"
    assert task.expected_assertions == 22
    assert tuple(task.runtime_data_files) == RUNTIME_XML
    assert runtime.task_bindings[TASK_ID] == ("rimworld-1.6.4871-linux-x64",)
    # Every other task keeps the default: no task-owned runtime definitions.
    assert all(item.runtime_data_files == [] for item in catalog.tasks if item.id != TASK_ID)
    assert not (PACK / "drafts").exists()


def test_complete_source_inventory_is_exact_and_only_fix_files_differ() -> None:
    provenance = json.loads((TASK_ROOT / "validation/provenance.json").read_text())
    changed = []
    for name, expected in provenance["sourceUnits"]["base"].items():
        base = (TASK_ROOT / "environment/ResearchOrganized" / name).read_bytes()
        reference = (TASK_ROOT / "solution/after/ResearchOrganized" / name).read_bytes()
        assert hashlib.sha256(base).hexdigest() == expected
        assert hashlib.sha256(reference).hexdigest() == provenance["sourceUnits"]["reference"][name]
        if base != reference:
            changed.append(name)
    assert len(list((TASK_ROOT / "environment/ResearchOrganized").rglob("*.cs"))) == 13
    assert changed == [SOURCE, "Source/ResearchOrganizedMod.cs"]


def test_runtime_definitions_are_the_unchanged_upstream_files() -> None:
    for relative in RUNTIME_XML:
        upstream = TASK_ROOT / "validation/audit/base/1.6/Defs" / Path(relative).name
        assert (TASK_ROOT / relative).read_bytes() == upstream.read_bytes()
        assert upstream.read_bytes() == (
            TASK_ROOT / "validation/audit/reference/1.6/Defs" / Path(relative).name
        ).read_bytes()


def test_input_manifest_pins_every_authored_input() -> None:
    manifest = json.loads((TASK_ROOT / "validation/input-manifest.json").read_text())
    assert manifest["schemaVersion"] == 2
    expected = {f"exams/{TASK_ID}.md"} | {
        path.relative_to(PACK).as_posix() for path in TASK_ROOT.rglob("*") if path.is_file()
    }
    # The evidence record and the manifest itself change after inputs are pinned.
    expected -= {
        f"{TASK_RELATIVE}/validation/controls.json",
        f"{TASK_RELATIVE}/validation/input-manifest.json",
    }
    assert set(manifest["files"]) == expected
    for relative, digest in manifest["files"].items():
        assert hashlib.sha256((PACK / relative).read_bytes()).hexdigest() == digest, relative


def test_plugin_materializes_only_public_english_attempt(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir(mode=0o700)
    RimWorldBenchmarkPlugin().materialize_attempt(_task(), attempt, _context(PACK, tmp_path))
    assert (attempt / "EXAM.md").read_text().startswith("# Keep research-tab state")
    assert {p.name for p in attempt.iterdir()} == {
        "EXAM.md", "AGENTS.md", "CLAUDE.md", "task.json", "ResearchOrganized"
    }
    assert len(list(attempt.rglob("*.cs"))) == 13
    assert not list(attempt.rglob("assertions.json"))
    assert not list(attempt.rglob("*.xml"))


def test_controls_are_independent_and_do_not_modify_sources(materialized: Path) -> None:
    controls = materialized / "controls"
    assert secure_tree_hash(controls / "base") == secure_tree_hash(controls / "nop")
    assert not os.path.samefile(
        controls / "base/ResearchOrganized" / SOURCE, controls / "nop/ResearchOrganized" / SOURCE
    )
    assert secure_tree_hash(controls / "base/ResearchOrganized") == secure_tree_hash(
        TASK_ROOT / "environment/ResearchOrganized"
    )
    assert secure_tree_hash(controls / "oracle/ResearchOrganized") == secure_tree_hash(
        TASK_ROOT / "solution/after/ResearchOrganized"
    )
    record = json.loads((materialized / "materialization.json").read_text())
    assert len({item["materializationId"] for item in record["controls"]}) == 8
    assert record["compileValidated"] is False and record["engineValidated"] is False
    assert record["catalogVersion"] == "0.5.0"


def test_normal_full_evaluator_fails_closed_without_runtime(materialized: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    evaluator = RimWorldEvaluator(_context(PACK, materialized), catalog)
    verdict = evaluator.evaluate(materialized / "controls/oracle", _task(), profile="full")
    assert verdict["complete"] is False
    assert verdict["passed"] is False
    assert verdict["runtime"]["engineAssertionsRan"] is False


@pytest.mark.parametrize("paths", [
    ["../outside.xml"], ["/absolute.xml"],
    ["tests/ModMetadata/Other/Defs/Choice.xml"],
    ["tests/ModMetadata/ResearchOrganized/Defs/Code.cs"],
    ["tests/ModMetadata/ResearchOrganized/Defs/../About.xml"],
    ["tests/ModMetadata/ResearchOrganized/Defs/Choice.xml"] * 2,
    [f"tests/ModMetadata/ResearchOrganized/Defs/Choice{index}.xml" for index in range(65)],
])
def test_runtime_xml_paths_are_task_owned(paths: list[str]) -> None:
    catalog = json.loads((PACK / "catalog.json").read_text())
    task = next(item for item in catalog["tasks"] if item["id"] == TASK_ID)
    with pytest.raises(ValidationError):
        RimWorldTask.model_validate(task | {"runtime_data_files": paths})


def test_runtime_xml_changes_adapter_identity(tmp_path: Path) -> None:
    pack = _pack_copy(tmp_path)
    catalog = RimWorldCatalog.load(pack)
    task = _task(pack)
    builder = RimWorldRuntimeBuilder(_context(pack, tmp_path), catalog)
    before = builder._current_adapter_evidence(task)
    asset = pack / TASK_RELATIVE / task.runtime_data_files[0]
    asset.write_bytes(asset.read_bytes() + b"\n<!-- authored change -->\n")
    assert builder._current_adapter_evidence(task) != before


def test_runtime_builder_stages_xml_without_private_manifest(tmp_path: Path) -> None:
    catalog = RimWorldCatalog.load(PACK)
    task = _task()
    builder = RimWorldRuntimeBuilder(_context(PACK, tmp_path), catalog)
    source = tmp_path / "fake-acquired-unit-fixture"
    runtime = RuntimeCatalog.load(PACK, "runtimes.json").runtimes[0]
    for name in runtime.source["expectedFiles"]:
        path = source / str(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    staged = tmp_path / "build-context"
    staged.mkdir()
    builder._stage_build_context(task, source, staged)
    assert all((staged / name).read_bytes() == (TASK_ROOT / name).read_bytes()
               for name in task.runtime_data_files)
    assert not list(staged.rglob("assertions.json"))
    assert not list(staged.rglob("solution"))
    assert not list(staged.rglob("validation"))


@pytest.mark.parametrize("damage", ["source", "xml", "symlink"])
def test_tampered_input_is_rejected_before_output(tmp_path: Path, damage: str) -> None:
    pack = _pack_copy(tmp_path)
    task = pack / TASK_RELATIVE
    path = task / "environment/ResearchOrganized" / SOURCE
    if damage == "xml":
        path = task / RUNTIME_XML[0]
    if damage == "symlink":
        moved = path.with_name("original.cs")
        path.rename(moved)
        path.symlink_to(moved)
    else:
        path.write_bytes(path.read_bytes() + b"\nchanged\n")
    state = tmp_path / "rejected"
    assert _invoke(pack, state).returncode != 0
    assert not state.exists()


def test_missing_runtime_xml_cannot_load_catalog(tmp_path: Path) -> None:
    pack = _pack_copy(tmp_path)
    (pack / TASK_RELATIVE / RUNTIME_XML[0]).unlink()
    with pytest.raises(ValueError, match="runtime definition"):
        RimWorldCatalog.load(pack)


def test_existing_and_repository_destinations_are_rejected(materialized: Path) -> None:
    assert _invoke(PACK, materialized).returncode != 0
    forbidden = ROOT / "forbidden-research-controls"
    assert _invoke(PACK, forbidden).returncode != 0
    assert not forbidden.exists()


def test_missing_compiler_leaves_compile_and_game_false(tmp_path: Path) -> None:
    state = tmp_path / "missing-compiler"
    process = _invoke(PACK, state, "--compile", "--dotnet", str(tmp_path / "absent-dotnet"))
    assert process.returncode == 2
    report = json.loads((state / "compile.json").read_text())
    assert report["status"] == "unavailable"
    assert report["compileValidated"] is False and report["engineValidated"] is False


@pytest.mark.parametrize("failure", ["sdk", "restore", "build"])
def test_failed_toolchain_cannot_produce_compile_success(
    materialized: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    module = _script()

    def run(executable: str, arguments: list[str], state: Path, label: str) -> int:
        del executable
        if arguments == ["--version"]:
            (state / "sdk-version.log").write_text("9.0.100" if failure == "sdk" else "8.0.422")
            return 0
        return 1 if arguments[0] == failure else 0

    monkeypatch.setattr(module, "_run", run)
    monkeypatch.setattr(module.shutil, "which", lambda _name: sys.executable)
    report = json.loads((materialized / "materialization.json").read_text())
    assert module.compile_controls(materialized, report, "dotnet") == 2
    assert report["compileValidated"] is False and report["engineValidated"] is False


@pytest.mark.parametrize("failure", ["missing", "sdk", "probe", "restore", "build", "spawn", "timeout"])
def test_previous_success_cannot_survive_a_failed_compilation(
    materialized: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    module = _script()
    report = json.loads((materialized / "materialization.json").read_text())
    report.update(status="compile-validated", compileValidated=True, engineValidated=True,
                  reason="stale failure reason")
    for control in report["controls"]:
        control.update(status="compile-validated", compileValidated=True, engineValidated=True,
                       assemblies={"candidate": "stale", "verifier": "stale"},
                       failedRole="stale", failedOperation="stale")

    def run(executable: str, arguments: list[str], state: Path, label: str) -> int:
        del executable, label
        if failure == "spawn":
            raise OSError("compiler fixture could not start")
        if arguments == ["--version"]:
            (state / "sdk-version.log").write_text("9.0.100" if failure == "sdk" else "8.0.422")
            return 124 if failure == "timeout" else int(failure == "probe")
        return int(arguments[0] == failure)

    monkeypatch.setattr(module, "_run", run)
    monkeypatch.setattr(
        module.shutil, "which", lambda _name: None if failure == "missing" else sys.executable
    )
    assert module.compile_controls(materialized, report, "dotnet") == 2
    saved = json.loads((materialized / "compile.json").read_text())
    assert saved["compileValidated"] is False and saved["engineValidated"] is False
    assert all(not item["compileValidated"] and not item["engineValidated"] for item in saved["controls"])
    assert all(item["assemblies"] == {} for item in saved["controls"])
    assert all(item.get("failedRole") != "stale" and item.get("failedOperation") != "stale"
               for item in saved["controls"])


def test_successful_recompile_replaces_failed_control_evidence(
    materialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script()
    report = json.loads((materialized / "materialization.json").read_text())
    report.update(status="failed", reason="stale failure reason")
    for control in report["controls"]:
        control.update(status="failed", failedRole="candidate", failedOperation="restore")

    def run(executable: str, arguments: list[str], state: Path, label: str) -> int:
        del executable, label
        if arguments == ["--version"]:
            (state / "sdk-version.log").write_text("8.0.422")
        elif arguments[0] == "build":
            output = Path(next(value.removeprefix("-p:OutputPath=") for value in arguments
                               if value.startswith("-p:OutputPath=")))
            output.mkdir(parents=True, exist_ok=True)
            name = "ResearchOrganized.dll" if output.name == "candidate" else "RheniumRimWorldVerifier.dll"
            (output / name).write_bytes(b"unit compiler output; no native game evidence")
        return 0

    monkeypatch.setattr(module, "_run", run)
    monkeypatch.setattr(module.shutil, "which", lambda _name: sys.executable)
    assert module.compile_controls(materialized, report, "dotnet") == 0
    saved = json.loads((materialized / "compile.json").read_text())
    assert saved["compileValidated"] is True and saved["engineValidated"] is False
    assert "reason" not in saved
    assert all(item["status"] == "compile-validated" and set(item["assemblies"]) == {"candidate", "verifier"}
               and "failedRole" not in item and "failedOperation" not in item for item in saved["controls"])


def test_negative_control_plan_binds_existing_native_cases(materialized: Path) -> None:
    assertions = load_assertion_manifest(PACK, TASK_ID)
    plan = json.loads((TASK_ROOT / "validation/negative-controls.json").read_text())
    controls = {item["control"]: set(item["mustFailCases"]) for item in plan["controls"]}
    names = set(assertions.case_names)
    assert controls["stale-view"] == {"closed-view-recomputed", "open-view-recomputed"}
    assert controls["closed-window-only"] == {
        "open-view-recomputed", "open-window-relayout", "explicit-open-refresh"
    }
    assert all(expected and expected <= names for expected in controls.values())
    assert set(controls) == set(_script().CONTROL_NAMES) - {"base", "oracle", "nop"}
    source_hashes = {secure_tree_hash(materialized / "controls" / name) for name in controls}
    assert len(source_hashes) == len(controls)
