from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pack_fixtures import catalog_task, sample_pack_fixture, write_pack  # noqa: F401
from pydantic import ValidationError
from rhenium_minecraft.catalog import (
    SYNTH_CATALOG_ID,
    BuildSpec,
    MinecraftCatalog,
    MinecraftTask,
    task_manifest,
)


def test_sample_pack_loads_and_freezes_case_sets(sample_pack: Path) -> None:
    catalog = MinecraftCatalog.load(sample_pack)
    (task,) = catalog.tasks
    assert task.plugin_name == "Sample"
    assert task.unit_cases == ("dev.sample.CounterTest.counts",)
    assert task.server_cases == ("plugin is enabled", "count command reports two")
    assert task.starter_name == "plugin" and task.container_destination == "/app/plugin"
    assert "Fix the count command" in task.authored_prompt
    manifest = json.loads(
        (sample_pack / "private/harbor" / task.id / "tests/task.json").read_text(encoding="utf-8")
    )
    assert manifest == task_manifest(task)
    assert manifest["build"]["frozenPaths"][-1] == "src/test"


def test_task_json_drift_is_rejected(sample_pack: Path) -> None:
    manifest = sample_pack / "private/harbor/sample-count-command/tests/task.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["serverCases"].append("forged")
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="drifted"):
        MinecraftCatalog.load(sample_pack)


def test_plugin_yml_name_must_match(sample_pack: Path) -> None:
    metadata = (
        sample_pack / "private/harbor/sample-count-command/environment/plugin/src/main/resources/plugin.yml"
    )
    metadata.write_text("name: Other\nmain: dev.sample.SamplePlugin\n", encoding="utf-8")
    with pytest.raises(ValueError, match="plugin_name"):
        MinecraftCatalog.load(sample_pack)


def test_case_contracts_must_cover_both_layers(sample_pack: Path) -> None:
    contracts = sample_pack / "private/harbor/sample-count-command/validation/case-contracts.tsv"
    contracts.write_text("case\tlayer\trole\tpublic_report\nplugin is enabled\tserver\ttarget\tx\n")
    with pytest.raises(ValueError, match="case contracts"):
        MinecraftCatalog.load(sample_pack)


def test_exam_must_match_instruction(sample_pack: Path) -> None:
    (sample_pack / "exams/sample-count-command.md").write_text("# Different\n", encoding="utf-8")
    with pytest.raises(ValueError, match="drifted from Harbor instruction"):
        MinecraftCatalog.load(sample_pack)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda t: t.update(required_files=["src/main/resources/plugin.yml"]), "below plugin/"),
        (lambda t: t.update(server_cases=["a", "a"]), "unique"),
        (lambda t: t.update(unit_cases=["plugin is enabled"]), "disjoint"),
        (lambda t: t.update(unit_cases=[]), "test task"),
        (lambda t: t.update(clean_room_synthetic=True), "synthetic tasks"),
        (lambda t: t.pop("upstream"), "repository tasks"),
        (
            lambda t: t.update(hidden_unit_overlay=True, unit_cases=[], build={**t["build"], "test": None}),
            "overlay",
        ),
    ],
)
def test_task_model_rules(mutation: Callable[[dict[str, Any]], object], message: str) -> None:
    task = catalog_task("rules")
    mutation(task)
    with pytest.raises(ValidationError, match=message):
        MinecraftTask.model_validate(task)


def test_build_spec_rules() -> None:
    with pytest.raises(ValidationError, match="tool_version"):
        BuildSpec(tool="gradle", wrapper=False, artifact="build/libs/x.jar")
    with pytest.raises(ValidationError, match="assemble"):
        BuildSpec(tool="javac", test=None, artifact="build/libs/x.jar")
    with pytest.raises(ValidationError, match="normalized"):
        BuildSpec(tool="gradle", artifact="../x.jar")
    spec = BuildSpec(tool="javac", assemble="", test=None, artifact="build/libs/x.jar")
    assert spec.frozen_paths[0] == "build.gradle"


def test_synthetic_catalog_uses_javac_and_no_upstream(tmp_path: Path) -> None:
    task = catalog_task("synthetic-one", tool="javac", unit=False, synthetic=True)
    task["required_files"] = ["plugin/src/main/resources/plugin.yml"]
    pack = write_pack(tmp_path / "synth", [task], catalog_id=SYNTH_CATALOG_ID)
    (pack / "private/harbor/synthetic-one/tests/TaskSuite.java").write_text("class TaskSuite {}\n")
    catalog = MinecraftCatalog.load(pack)
    assert catalog.tasks[0].clean_room_synthetic is True
    assert catalog.tasks[0].upstream is None
    assert catalog.tasks[0].build.tool == "javac"


def test_catalog_rejects_unknown_id(tmp_path: Path) -> None:
    pack = write_pack(tmp_path / "bad", [catalog_task("x")], catalog_id="rhenium-minecraft-v9")
    with pytest.raises(ValidationError, match="catalog id"):
        MinecraftCatalog.load(pack)


def test_materialize_header_matches_catalog_constant() -> None:
    import importlib.util

    from pack_fixtures import PACK
    from rhenium_minecraft.catalog import HARBOR_INSTRUCTION_HEADER

    spec = importlib.util.spec_from_file_location(
        "minecraft_materialize_header", PACK / "private" / "harbor" / "scripts" / "materialize.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.INSTRUCTION_HEADER == HARBOR_INSTRUCTION_HEADER


def test_plugin_metadata_is_found_in_a_sub_module(tmp_path: Path) -> None:
    from rhenium_minecraft.catalog import plugin_metadata_file

    starter = tmp_path / "plugin"
    (starter / "spigot" / "src" / "main" / "resources").mkdir(parents=True)
    (starter / "api" / "src" / "main" / "java").mkdir(parents=True)
    assert plugin_metadata_file(starter) is None
    metadata = starter / "spigot" / "src" / "main" / "resources" / "plugin.yml"
    metadata.write_text("name: Sample\n", encoding="utf-8")
    assert plugin_metadata_file(starter) == metadata
    assert plugin_metadata_file(starter, "spigot") == metadata
    root = starter / "src" / "main" / "resources" / "paper-plugin.yml"
    root.parent.mkdir(parents=True)
    root.write_text("name: Root\n", encoding="utf-8")
    assert plugin_metadata_file(starter) == root


def test_a_build_time_placeholder_name_is_accepted(sample_pack: Path) -> None:
    # Maven resource filtering fills the name in; the verifier checks the built jar.
    metadata = (
        sample_pack / "private/harbor/sample-count-command/environment/plugin/src/main/resources/plugin.yml"
    )
    metadata.write_text("name: ${project.name}\nmain: dev.sample.SamplePlugin\n", encoding="utf-8")
    assert MinecraftCatalog.load(sample_pack).tasks[0].plugin_name == "Sample"
