from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from rhenium_slay_the_spire.plugin import SlayTheSpireBenchmarkPlugin
from spire_fixtures import PACK, sample_pack_fixture  # noqa: F401

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
    plugin = SlayTheSpireBenchmarkPlugin()
    assert plugin.descriptor.id == plugin.descriptor.game_id == "slay-the-spire"
    catalog = plugin.load_catalog(sample_pack, "catalog.json")
    assert catalog.id == "slay-the-spire-core"
    raw = json.loads((sample_pack / "catalog.json").read_text(encoding="utf-8"))
    (sample_pack / "catalog.json").write_text(json.dumps({**raw, "id": "other"}), encoding="utf-8")
    with pytest.raises(ValueError, match="catalog id"):
        plugin.load_catalog(sample_pack, "catalog.json")


def test_runtime_builder_only_for_the_declared_runtime(sample_pack: Path, tmp_path: Path) -> None:
    plugin = SlayTheSpireBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    spec = RuntimeCatalog.load(sample_pack, "runtimes.json").runtimes[0]
    assert plugin.create_runtime_builder(context, spec) is not None
    assert plugin.create_runtime_builder(context, spec.model_copy(update={"id": "other"})) is None


def test_starter_and_attempt_materialization(sample_pack: Path, tmp_path: Path) -> None:
    plugin = SlayTheSpireBenchmarkPlugin()
    context = context_for(sample_pack, tmp_path)
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    workspace = tmp_path / "workspace"
    plugin.materialize_starter(task, workspace, context)
    assert (workspace / "modthespire" / "pom.xml").is_file()
    marker = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
    assert marker == {
        "difficulty": "hard",
        "submission": ".",
        "fromScratch": False,
        "language": "java",
    }
    # The public prompt never names the private container path.
    assert "/app/modthespire" not in (workspace / "TASK.md").read_text(encoding="utf-8")
    assert plugin.task_prompt(task).startswith("# Sample regressions")
    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, context)
    assert {path.name for path in attempt.iterdir()} == {
        "modthespire",
        "task.json",
        "EXAM.md",
        "AGENTS.md",
        "CLAUDE.md",
    }
    guidance = (attempt / "AGENTS.md").read_text(encoding="utf-8")
    assert "do not say how many underlying problems" in guidance
    assert "Real-game verification is unavailable" in guidance


def test_public_task_and_result_sanitizer(sample_pack: Path) -> None:
    plugin = SlayTheSpireBenchmarkPlugin()
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    public = plugin.public_task(task)
    assert public["sourceMod"] == "ModTheSpire" and public["javaRelease"] == 8
    assert public["buildTool"] == "maven" and public["fromScratch"] is False
    # The assertion count is private: it never reaches the public view.
    assert "expectedAssertions" not in public and "expected_assertions" not in public
    sanitized = plugin.sanitize_anonymous_result(
        {
            "score": 10.0,
            "runtime_log": "secret",
            "runtime": {"status": "failed", "message": "private", "expectedAssertions": 9},
            "checks": [{"id": "private-suite", "status": "failed", "details": {"cases": ["x"]}}],
        }
    )
    assert "runtime_log" not in sanitized
    assert sanitized["runtime"] == {"status": "failed", "expectedAssertions": 9}
    assert sanitized["checks"] == [{"id": "private-suite", "status": "failed"}]


def test_agent_prompt_and_report_fields_describe_the_offline_grader(sample_pack: Path) -> None:
    plugin = SlayTheSpireBenchmarkPlugin()
    task = plugin.load_catalog(sample_pack, "catalog.json").tasks[0]
    prompt = plugin.agent_system_prompt(task)
    assert "ModTheSpire" in prompt and "without the base game" in prompt
    assert "benchmark scoring is incomplete and cannot pass" in prompt
    assert "JDK 8 Maven evaluator runtime status" in plugin.completion_report_fields()


def test_distribution_is_an_independent_workspace_member() -> None:
    metadata = tomllib.loads(
        (PACK.parents[1] / "plugins/slay-the-spire/pyproject.toml").read_text(encoding="utf-8")
    )
    assert metadata["project"]["name"] == "rhenium-slay-the-spire"
    assert metadata["project"]["dependencies"] == ["rhenium==0.6.0", "rhenium-container==0.1.0"]
    assert list(metadata["project"]["entry-points"]["rhenium.benchmarks"]) == ["slay-the-spire"]


def test_the_shipped_pack_selects_this_plugin() -> None:
    manifest = json.loads((PACK / "benchmark.json").read_text(encoding="utf-8"))
    assert manifest["plugin"] == "slay-the-spire" and manifest["pack_id"] == "core"
    assert manifest["runtime_catalog"] == "runtimes.json"
    # The only binaries in the pack are the upstream Maven wrapper bootstrap jars;
    # nothing from the paid base game is redistributed here.
    assert {path.name for path in PACK.rglob("*.jar")} == {"maven-wrapper.jar"}
    assert all(path.parent.as_posix().endswith(".mvn/wrapper") for path in PACK.rglob("*.jar"))
