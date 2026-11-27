from __future__ import annotations

import json
from pathlib import Path

import pytest
from mindustry_fixtures import sample_pack_fixture  # noqa: F401
from rhenium_mindustry.plugin import MindustryBenchmarkPlugin

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
    plugin = MindustryBenchmarkPlugin()
    assert plugin.descriptor.id == plugin.descriptor.game_id == "mindustry"
    assert "repository-debugging" in plugin.descriptor.capabilities
    catalog = plugin.load_catalog(sample_pack, "catalog.json")
    assert catalog.id == "rhenium-mindustry-v2"
    (sample_pack / "catalog.json").write_text(
        json.dumps({**json.loads((sample_pack / "catalog.json").read_text()), "id": "other"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="catalog id"):
        plugin.load_catalog(sample_pack, "catalog.json")


def test_runtime_builder_only_for_the_pinned_runtime(sample_pack: Path, tmp_path: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    spec = RuntimeCatalog.load(sample_pack, "runtimes.json").runtimes[0]
    assert spec.id == "mindustry-159.7"
    assert plugin.create_runtime_builder(context, spec) is not None
    assert plugin.create_runtime_builder(context, spec.model_copy(update={"id": "mindustry"})) is None


def test_starter_and_attempt_materialization(sample_pack: Path, tmp_path: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    workspace = tmp_path / "workspace"
    plugin.materialize_starter(task, workspace, context)
    assert (workspace / "mindustry" / "core" / "src" / "mindustry" / "Vars.java").is_file()
    assert (workspace / "mindustry" / "LICENSE").is_file()
    marker = json.loads((workspace / "task.json").read_text())
    assert marker == {"difficulty": "medium", "submission": ".", "fromScratch": False, "language": "java"}
    assert "/app/mindustry" not in (workspace / "TASK.md").read_text()
    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, context)
    assert {p.name for p in attempt.iterdir()} == {
        "mindustry",
        "task.json",
        "EXAM.md",
        "AGENTS.md",
        "CLAUDE.md",
    }
    assert "not rebuilt" in (attempt / "AGENTS.md").read_text()
    assert plugin.task_prompt(task).startswith("# Sample repair")


def test_public_task_and_sanitizer(sample_pack: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    public = plugin.public_task(task)
    assert public["sourceRepository"] == "https://github.com/Anuken/Mindustry"
    assert public["sourceRelease"] == "v159.7" and public["licenseSpdx"] == "GPL-3.0"
    assert public["buildTool"] == "mindustry-source" and public["serverCases"] == 4
    assert public["fromScratch"] is False
    sanitized = plugin.sanitize_anonymous_result(
        {
            "score": 10.0,
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
    assert "159.7" in plugin.agent_system_prompt(task)
    assert "dedicated-server runtime status" in plugin.completion_report_fields()
