import json
from pathlib import Path

from rhenium_terraria import TerrariaBenchmarkPlugin
from rhenium_terraria.catalog import TerrariaCatalog

from rhenium.core.plugin import BenchmarkContext

PACK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "terraria-core"


def test_descriptor() -> None:
    plugin = TerrariaBenchmarkPlugin()
    assert plugin.id == "terraria"
    assert plugin.game_id == "terraria"
    assert plugin.descriptor.version == "0.7.0"


def test_materialized_attempt_contains_only_selected_snapshot(tmp_path: Path) -> None:
    catalog = TerrariaCatalog.load(PACK_ROOT)
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    task = catalog.tasks[0]
    destination = tmp_path / "attempt"
    TerrariaBenchmarkPlugin().materialize_attempt(task, destination, context)

    assert (destination / task.starter_name / "Common" / "IO" / "ValueWriter.cs").is_file()
    assert (destination / "EXAM.md").is_file()
    assert not (destination / "tests").exists()
    assert not (destination / "solution").exists()
    assert not (destination / "validation").exists()

    marker = json.loads((destination / "task.json").read_text(encoding="utf-8"))
    assert marker["tModLoaderApi"] == "1.4.4 stable API"
    assert marker["evaluationBoundary"].startswith("layered offline .NET 8")


def test_public_metadata_discloses_real_game_runtime_and_exclusions() -> None:
    plugin = TerrariaBenchmarkPlugin()
    task = TerrariaCatalog.load(PACK_ROOT).tasks[0]
    public = plugin.public_task(task)
    assert public["evaluationBoundary"] == task.evaluation_boundary
    assert public["tModLoaderVersion"] == "2026.7.3.0"
    assert public["engineMode"] == "dedicated-server"
    assert public["realEngineCases"] == 3
    assert isinstance(public["clientOnlyExclusions"], list)
