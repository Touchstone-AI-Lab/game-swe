from __future__ import annotations

import json
from pathlib import Path

import pytest
from pack_fixtures import catalog_task, sample_pack_fixture, write_pack  # noqa: F401
from rhenium_minecraft.catalog import SYNTH_CATALOG_ID
from rhenium_minecraft.plugin import MinecraftBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog


def context_for(pack: Path, tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def test_descriptor_and_catalog_identity(sample_pack: Path) -> None:
    plugin = MinecraftBenchmarkPlugin()
    assert plugin.descriptor.id == plugin.descriptor.game_id == "minecraft"
    catalog = plugin.load_catalog(sample_pack, "catalog.json")
    assert catalog.id == "rhenium-minecraft-v1"
    (sample_pack / "catalog.json").write_text(
        json.dumps({**json.loads((sample_pack / "catalog.json").read_text()), "id": "other"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="catalog id"):
        plugin.load_catalog(sample_pack, "catalog.json")


def test_runtime_builder_only_for_known_runtime_ids(sample_pack: Path, tmp_path: Path) -> None:
    plugin = MinecraftBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    spec = RuntimeCatalog.load(sample_pack, "runtimes.json").runtimes[0]
    assert plugin.create_runtime_builder(context, spec) is not None
    assert (
        plugin.create_runtime_builder(context, spec.model_copy(update={"id": "paper-1.21.11-132-synth"}))
        is not None
    )
    assert plugin.create_runtime_builder(context, spec.model_copy(update={"id": "other"})) is None


def test_starter_and_attempt_materialization(sample_pack: Path, tmp_path: Path) -> None:
    plugin = MinecraftBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    workspace = tmp_path / "workspace"
    plugin.materialize_starter(task, workspace, context)
    assert (workspace / "plugin" / "src" / "main" / "resources" / "plugin.yml").is_file()
    marker = json.loads((workspace / "task.json").read_text())
    assert marker == {"difficulty": "medium", "submission": ".", "fromScratch": False, "language": "java"}
    assert "/app/plugin" not in (workspace / "TASK.md").read_text()
    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, context)
    assert {p.name for p in attempt.iterdir()} == {"plugin", "task.json", "EXAM.md", "AGENTS.md", "CLAUDE.md"}
    assert "frozen" in (attempt / "AGENTS.md").read_text()
    assert plugin.task_prompt(task).startswith("# Sample repair")


def test_public_task_and_sanitizer(sample_pack: Path) -> None:
    plugin = MinecraftBenchmarkPlugin()
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    public = plugin.public_task(task)
    assert public["sourceRepository"] == "https://github.com/example/sample-plugin"
    assert public["buildTool"] == "gradle" and public["serverCases"] == 2
    sanitized = plugin.sanitize_anonymous_result(
        {
            "score": 40.0,
            "runtime_log": "secret",
            "runtime": {
                "status": "failed",
                "cases": [{"name": "private"}],
                "caseOutcomes": {"private": True},
            },
            "checks": [{"id": "live-server", "status": "failed", "details": {"cases": ["private"]}}],
        }
    )
    assert "runtime_log" not in sanitized
    assert sanitized["runtime"] == {"status": "failed"}
    assert sanitized["checks"] == [{"id": "live-server", "status": "failed"}]


def test_synthetic_task_copies_the_pack_license(tmp_path: Path) -> None:
    task = catalog_task("synthetic-one", tool="javac", unit=False, synthetic=True)
    task["required_files"] = ["plugin/src/main/resources/plugin.yml"]
    pack = write_pack(tmp_path / "synth", [task], catalog_id=SYNTH_CATALOG_ID)
    (pack / "private/harbor/synthetic-one/tests/TaskSuite.java").write_text("class TaskSuite {}\n")
    plugin = MinecraftBenchmarkPlugin()
    loaded = plugin.load_catalog(pack, "catalog.json").tasks[0]
    workspace = tmp_path / "workspace"
    plugin.materialize_starter(loaded, workspace, context_for(pack, tmp_path))
    assert (workspace / "LICENSE").is_file()
    assert plugin.public_task(loaded)["cleanRoomSynthetic"] is True
    assert "clean-room synthetic" in plugin.agent_system_prompt(loaded)
