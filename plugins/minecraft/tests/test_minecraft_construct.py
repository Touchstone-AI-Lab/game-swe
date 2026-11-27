"""Construct tasks: a whole Paper plugin written into a frozen Maven skeleton."""

from __future__ import annotations

import filecmp
import importlib.util
import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest
from pack_fixtures import HARNESS, PACK, catalog_task
from pydantic import ValidationError
from rhenium_minecraft.catalog import (
    CATALOG_RUNTIME_IDS,
    CONSTRUCT_CATALOG_ID,
    CONSTRUCT_INSTRUCTION_HEADER,
    CORE_CATALOG_ID,
    MinecraftCatalog,
    MinecraftTask,
    task_manifest,
)
from rhenium_minecraft.container import CONSTRUCT_RUNTIME_ID, RUNTIME_IDS
from rhenium_minecraft.plugin import MinecraftBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog

ROOT = Path(__file__).resolve().parents[3]
CONSTRUCT_PACK = ROOT / "benchmarks" / "minecraft-construct"
CONSTRUCT_HARNESS = CONSTRUCT_PACK / "private" / "harbor" / "harness"
CATALOG = MinecraftCatalog.load(CONSTRUCT_PACK)
TASKS = [pytest.param(task, id=task.id) for task in CATALOG.tasks]
CASE = re.compile(r'@GcbCase\(\s*(?:value\s*=\s*)?"([^"]+)"')


def construct_task(task_id: str) -> dict[str, Any]:
    task = catalog_task(task_id, tool="maven", unit=False)
    task.pop("upstream")
    task["task_kind"] = "construct"
    task["required_files"] = [
        "plugin/pom.xml",
        "plugin/src/main/resources/plugin.yml",
        "plugin/src/main/java/dev/sample/SamplePlugin.java",
    ]
    return task


def write_construct_pack(root: Path, tasks: list[dict[str, Any]]) -> Path:
    """A minimal construct pack, materialized with the construct pack's own script."""
    root.mkdir(parents=True)
    (root / "benchmark.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pack_id": "construct",
                "plugin": "minecraft",
                "catalog": "catalog.json",
                "runtime_catalog": "runtimes.json",
            }
        ),
        encoding="utf-8",
    )
    shutil.copytree(CONSTRUCT_PACK / "private" / "runtime", root / "private" / "runtime")
    shutil.copytree(CONSTRUCT_HARNESS, root / "private" / "harbor" / "harness")
    runtimes = json.loads((CONSTRUCT_PACK / "runtimes.json").read_text(encoding="utf-8"))
    runtimes["task_bindings"] = {task["id"]: [CONSTRUCT_RUNTIME_ID] for task in tasks}
    (root / "runtimes.json").write_text(json.dumps(runtimes), encoding="utf-8")
    (root / "catalog.json").write_text(
        json.dumps(
            {
                "id": CONSTRUCT_CATALOG_ID,
                "version": "1.0.0",
                "game": "minecraft",
                "name": {"en": "Sample", "zh": "示例"},
                "description": {"en": "Sample", "zh": "示例"},
                "tasks": tasks,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for task in tasks:
        (root / "exams").mkdir(exist_ok=True)
        (root / "exams" / f"{task['id']}.md").write_text(
            "# Write a plugin: Sample\n\nWrite the sample plugin in `/app/plugin`.\n", encoding="utf-8"
        )
        harbor = root / "private" / "harbor" / task["id"]
        starter = harbor / "environment" / "plugin"
        (starter / "src" / "main" / "resources").mkdir(parents=True)
        (starter / "src" / "main" / "resources" / "plugin.yml").write_text(
            "name: Sample\nmain: dev.sample.SamplePlugin\nversion: 1.0\napi-version: '1.21'\n",
            encoding="utf-8",
        )
        (starter / "src" / "main" / "java" / "dev" / "sample").mkdir(parents=True)
        (starter / "src" / "main" / "java" / "dev" / "sample" / "SamplePlugin.java").write_text(
            "package dev.sample;\n"
            "public final class SamplePlugin extends org.bukkit.plugin.java.JavaPlugin {}\n",
            encoding="utf-8",
        )
        (starter / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        (harbor / "tests" / "suite").mkdir(parents=True)
        (harbor / "tests" / "suite" / "SampleSuite.java").write_text(
            "class SampleSuite {}\n", encoding="utf-8"
        )
        after = harbor / "solution" / "after" / "src" / "main" / "java" / "dev" / "sample"
        after.mkdir(parents=True)
        (after / "SamplePlugin.java").write_text("package dev.sample;\nclass Written {}\n", encoding="utf-8")
        (harbor / "validation").mkdir()
        rows = ["case\tlayer\trole\tpublic_report"]
        rows.extend(f"{name}\tserver\ttarget\tsample" for name in task["server_cases"])
        (harbor / "validation" / "case-contracts.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    scripts = root / "private" / "harbor" / "scripts"
    scripts.mkdir()
    shutil.copyfile(
        CONSTRUCT_PACK / "private" / "harbor" / "scripts" / "materialize.py", scripts / "materialize.py"
    )
    spec = importlib.util.spec_from_file_location(
        "minecraft_construct_materialize", scripts / "materialize.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.materialize()
    return root


def context_for(pack: Path, tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


# --- catalog model --------------------------------------------------------------------------


def test_construct_task_model_rules() -> None:
    task = MinecraftTask.model_validate(construct_task("sample-construct"))
    assert task.is_construct and task.task_kind == "construct" and task.upstream is None
    with_upstream = {**construct_task("x"), "upstream": catalog_task("x")["upstream"]}
    with pytest.raises(ValidationError, match="construct tasks"):
        MinecraftTask.model_validate(with_upstream)
    javac = {
        **construct_task("x"),
        "build": {"tool": "javac", "assemble": "", "test": None, "artifact": "build/libs/Sample.jar"},
    }
    with pytest.raises(ValidationError, match="construct tasks"):
        MinecraftTask.model_validate(javac)
    with pytest.raises(ValidationError, match="construct tasks"):
        MinecraftTask.model_validate({**construct_task("x"), "clean_room_synthetic": True})
    assert MinecraftTask.model_validate(catalog_task("repair")).is_construct is False


def test_construct_catalog_and_runtime_identity() -> None:
    assert CATALOG_RUNTIME_IDS[CONSTRUCT_CATALOG_ID] == CONSTRUCT_RUNTIME_ID == "paper-1.21.11-132-construct"
    assert CONSTRUCT_RUNTIME_ID in RUNTIME_IDS
    assert len(set(CATALOG_RUNTIME_IDS.values())) == len(CATALOG_RUNTIME_IDS)


def test_sample_construct_pack_loads(tmp_path: Path) -> None:
    pack = write_construct_pack(tmp_path / "pack", [construct_task("sample-construct")])
    (task,) = MinecraftCatalog.load(pack).tasks
    assert task.is_construct
    instruction = (pack / "private/harbor/sample-construct/instruction.md").read_text(encoding="utf-8")
    assert instruction.startswith(CONSTRUCT_INSTRUCTION_HEADER)
    toml = tomllib.loads((pack / "private/harbor/sample-construct/task.toml").read_text(encoding="utf-8"))
    assert toml["metadata"]["task_kind"] == "construct" and toml["metadata"]["from_scratch"] is True
    assert "source_repo" not in toml["metadata"]


def test_task_kinds_do_not_mix_between_catalogs(tmp_path: Path) -> None:
    pack = write_construct_pack(tmp_path / "pack", [construct_task("sample-construct")])
    catalog = json.loads((pack / "catalog.json").read_text(encoding="utf-8"))
    (pack / "catalog.json").write_text(json.dumps({**catalog, "id": CORE_CATALOG_ID}), encoding="utf-8")
    with pytest.raises(ValidationError, match="construct tasks belong to the construct catalog"):
        MinecraftCatalog.load(pack)
    repair = catalog_task("repair-in-construct")
    (pack / "catalog.json").write_text(json.dumps({**catalog, "tasks": [repair]}), encoding="utf-8")
    with pytest.raises(ValidationError, match="construct tasks belong to the construct catalog"):
        MinecraftCatalog.load(pack)


def test_construct_instruction_must_carry_the_construct_header(tmp_path: Path) -> None:
    pack = write_construct_pack(tmp_path / "pack", [construct_task("sample-construct")])
    instruction = pack / "private/harbor/sample-construct/instruction.md"
    body = instruction.read_text(encoding="utf-8")[len(CONSTRUCT_INSTRUCTION_HEADER) :]
    instruction.write_text("# Harbor workspace\n\nRepair it.\n\n" + body, encoding="utf-8")
    with pytest.raises(ValueError, match="workspace header"):
        MinecraftCatalog.load(pack)


# --- plugin surface -------------------------------------------------------------------------


def test_construct_starter_attempt_and_public_task(tmp_path: Path) -> None:
    pack = write_construct_pack(tmp_path / "pack", [construct_task("sample-construct")])
    plugin = MinecraftBenchmarkPlugin()
    context = context_for(pack, tmp_path)
    task = plugin.load_catalog(pack, "catalog.json").tasks[0]
    workspace = tmp_path / "workspace"
    plugin.materialize_starter(task, workspace, context)
    marker = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
    assert marker == {"difficulty": "medium", "submission": ".", "fromScratch": True, "language": "java"}
    assert (workspace / "plugin" / "pom.xml").is_file()
    assert "/app/plugin" not in (workspace / "TASK.md").read_text(encoding="utf-8")
    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, context)
    guidance = (attempt / "AGENTS.md").read_text(encoding="utf-8")
    assert "Write the new Paper plugin" in guidance and "pom.xml is frozen" in guidance
    public = plugin.public_task(task)
    assert public["fromScratch"] is True and public["taskKind"] == "construct"
    assert "sourceRepository" not in public and "cleanRoomSynthetic" not in public
    assert "construction benchmark" in plugin.agent_system_prompt(task)
    spec = RuntimeCatalog.load(pack, "runtimes.json").runtimes[0]
    assert spec.id == CONSTRUCT_RUNTIME_ID
    assert plugin.create_runtime_builder(context, spec) is not None


def test_repair_tasks_keep_their_public_shape() -> None:
    plugin = MinecraftBenchmarkPlugin()
    task = MinecraftCatalog.load(PACK).tasks[0]
    public = plugin.public_task(task)
    assert public["fromScratch"] is False and public["taskKind"] == "repository-debugging"
    assert "sourceRepository" in public and "construction" not in plugin.agent_system_prompt(task)


# --- the real construct pack ----------------------------------------------------------------


def test_construct_pack_binds_its_own_runtime() -> None:
    assert CATALOG.id == CONSTRUCT_CATALOG_ID and len(CATALOG.tasks) == 5
    runtimes = RuntimeCatalog.load(CONSTRUCT_PACK, "runtimes.json")
    assert [spec.id for spec in runtimes.runtimes] == [CONSTRUCT_RUNTIME_ID]
    bindings = {task: list(runtime_ids) for task, runtime_ids in runtimes.task_bindings.items()}
    assert bindings == {task.id: [CONSTRUCT_RUNTIME_ID] for task in CATALOG.tasks}
    benchmark = json.loads((CONSTRUCT_PACK / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["pack_id"] == "construct" and benchmark["plugin"] == "minecraft"


def test_construct_pack_shares_the_verified_runtime_and_harness() -> None:
    # Identical build inputs keep the shared base image reproducible across packs.
    core = PACK / "private"
    assert not filecmp.dircmp(core / "runtime", CONSTRUCT_PACK / "private" / "runtime").diff_files
    for name in ("verify.py", "test.sh", "solve.sh"):
        assert filecmp.cmp(HARNESS / name, CONSTRUCT_HARNESS / name, shallow=False), name
    core_sources = sorted(p.relative_to(HARNESS) for p in (HARNESS / "gcb-harness").rglob("*") if p.is_file())
    own_sources = sorted(
        p.relative_to(CONSTRUCT_HARNESS)
        for p in (CONSTRUCT_HARNESS / "gcb-harness").rglob("*")
        if p.is_file()
    )
    assert core_sources == own_sources
    for relative in core_sources:
        assert filecmp.cmp(HARNESS / relative, CONSTRUCT_HARNESS / relative, shallow=False), relative


def test_materialize_header_matches_the_catalog_constant() -> None:
    script = CONSTRUCT_PACK / "private" / "harbor" / "scripts" / "materialize.py"
    spec = importlib.util.spec_from_file_location("minecraft_construct_header", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.INSTRUCTION_HEADER == CONSTRUCT_INSTRUCTION_HEADER


@pytest.mark.parametrize("task", TASKS)
def test_construct_task_package_layout(task: MinecraftTask) -> None:
    root = CONSTRUCT_PACK / "private" / "harbor" / task.id
    assert task.is_construct and task.upstream is None and task.build.tool == "maven"
    assert task.build.artifact == f"target/{task.plugin_name}.jar" and not task.unit_cases
    assert 15 <= len(task.server_cases) <= 30
    for generated in ("tests/test.sh", "tests/verify.py"):
        assert filecmp.cmp(root / generated, CONSTRUCT_HARNESS / Path(generated).name, shallow=False)
    assert filecmp.cmp(root / "solution" / "solve.sh", CONSTRUCT_HARNESS / "solve.sh", shallow=False)
    assert json.loads((root / "tests" / "task.json").read_text(encoding="utf-8")) == task_manifest(task)
    toml = tomllib.loads((root / "task.toml").read_text(encoding="utf-8"))
    assert toml["metadata"]["task_kind"] == "construct" and toml["metadata"]["from_scratch"] is True
    assert toml["verifier"]["environment_mode"] == "separate"
    assert toml["metadata"]["expected_server_cases"] == len(task.server_cases)
    starter = root / "environment" / "plugin"
    mirror = root / "tests" / "starter"
    starter_files = sorted(p.relative_to(starter) for p in starter.rglob("*") if p.is_file())
    assert starter_files == sorted(p.relative_to(mirror) for p in mirror.rglob("*") if p.is_file())
    for relative in starter_files:
        assert filecmp.cmp(starter / relative, mirror / relative, shallow=False), relative


@pytest.mark.parametrize("task", TASKS)
def test_construct_skeleton_is_empty_and_frozen(task: MinecraftTask) -> None:
    starter = CONSTRUCT_PACK / "private" / "harbor" / task.id / "environment" / "plugin"
    files = sorted(p.relative_to(starter).as_posix() for p in starter.rglob("*") if p.is_file())
    main = next(name for name in files if name.endswith(".java"))
    assert files == sorted(["pom.xml", "src/main/resources/plugin.yml", main])
    assert sorted(task.required_files) == sorted(f"plugin/{name}" for name in files)
    source = (starter / main).read_text(encoding="utf-8")
    assert "public void onEnable() {\n    }" in source and "public void onDisable() {\n    }" in source
    metadata = (starter / "src/main/resources/plugin.yml").read_text(encoding="utf-8")
    assert "commands:" not in metadata and "permissions:" not in metadata
    pom = (starter / "pom.xml").read_text(encoding="utf-8")
    assert "<version>1.21.11-R0.1-20260511.115010-91</version>" in pom
    assert f"<finalName>{task.plugin_name}</finalName>" in pom
    assert "pom.xml" in task.build.frozen_paths


@pytest.mark.parametrize("task", TASKS)
def test_construct_reference_is_a_whole_plugin(task: MinecraftTask) -> None:
    root = CONSTRUCT_PACK / "private" / "harbor" / task.id
    after = root / "solution" / "after"
    files = [p for p in after.rglob("*") if p.is_file()]
    assert (after / "src/main/resources/plugin.yml").is_file()
    main = next(name for name in task.required_files if name.endswith(".java"))
    assert (after / main.removeprefix("plugin/")).is_file()
    assert all(not p.relative_to(after).as_posix().startswith(("pom.xml", "src/test")) for p in files)
    lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files if p.suffix == ".java")
    assert lines >= 400, f"{task.id} reference has only {lines} lines of Java"


@pytest.mark.parametrize("task", TASKS)
def test_construct_suite_registers_exactly_the_frozen_cases(task: MinecraftTask) -> None:
    suite = CONSTRUCT_PACK / "private" / "harbor" / task.id / "tests" / "suite"
    names = [
        name
        for path in sorted(suite.glob("*.java"))
        for name in CASE.findall(path.read_text(encoding="utf-8"))
    ]
    assert sorted(names) == sorted(task.server_cases)
    assert task.server_cases[0] == f"{task.plugin_name} is enabled"


@pytest.mark.parametrize("task", TASKS)
def test_construct_study_controls_are_complete(task: MinecraftTask) -> None:
    controls = CONSTRUCT_PACK / "private" / "study-controls" / task.id
    clause_map = json.loads((controls / "clause-map.json").read_text(encoding="utf-8"))
    assert clause_map["task"] == f"minecraft/construct/{task.id}"
    server = [
        case["id"].removeprefix("server:") for case in clause_map["cases"] if case["id"].startswith("server:")
    ]
    assert server == list(task.server_cases)
    assert {case["role"] for case in clause_map["cases"]} <= {"target", "runtime-sentinel", "setup", "static"}
    manifest = (controls / "manifest.tsv").read_text(encoding="utf-8").splitlines()
    kinds = {line.split("\t")[1] for line in manifest[1:]}
    assert {"target-negative", "alternative"} <= kinds
    assert (controls / "NOTES.md").is_file()
