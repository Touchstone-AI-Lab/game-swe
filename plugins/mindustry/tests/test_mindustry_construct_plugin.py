import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from rhenium_mindustry import MindustryBenchmarkPlugin
from rhenium_mindustry.catalog import MindustryCatalog, MindustryTask
from rhenium_mindustry.construct_catalog import MindustryConstructCatalog, MindustryConstructTask
from rhenium_mindustry.construct_evaluator import MindustryConstructEvaluator
from rhenium_mindustry.construct_runtime_builder import MindustryConstructRuntimeBuilder
from rhenium_mindustry.evaluator import MindustryEvaluator
from rhenium_mindustry.runtime_builder import MindustryRuntimeBuilder

from rhenium.core.manifest import BenchmarkManifest
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog


def test_descriptor() -> None:
    plugin = MindustryBenchmarkPlugin()
    assert plugin.id == "mindustry"
    assert plugin.game_id == "mindustry"
    assert plugin.descriptor.version == "0.6.0"


def test_every_fresh_attempt_has_empty_src(tmp_path: Path) -> None:
    pack_root = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = MindustryConstructCatalog.load(pack_root)
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=pack_root,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    plugin = MindustryBenchmarkPlugin()

    assert len(catalog.tasks) == 10
    for task in catalog.tasks:
        workspace = tmp_path / task.id
        plugin.materialize_attempt(task, workspace, context)
        source_dir = workspace / "src"
        assert source_dir.is_dir()
        assert list(source_dir.iterdir()) == []


ROOT = Path(__file__).resolve().parents[3]
CONSTRUCT_PACK = ROOT / "benchmarks" / "mindustry-construct"
REPAIR_PACK = ROOT / "benchmarks" / "mindustry-core"


def _context(pack: Path, tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=tmp_path,
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def test_catalog_id_selects_the_catalog_and_evaluator(tmp_path: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    construct = plugin.load_catalog(CONSTRUCT_PACK, "catalog.json")
    repair = plugin.load_catalog(REPAIR_PACK, "catalog.json")

    assert isinstance(construct, MindustryConstructCatalog)
    assert construct.id == "rhenium-mindustry-v1"
    assert all(isinstance(task, MindustryConstructTask) for task in construct.tasks)
    assert isinstance(repair, MindustryCatalog)
    assert repair.id == "rhenium-mindustry-v2"
    assert all(isinstance(task, MindustryTask) for task in repair.tasks)
    construct_evaluator = plugin.create_evaluator(_context(CONSTRUCT_PACK, tmp_path))
    assert isinstance(construct_evaluator, MindustryConstructEvaluator)
    assert isinstance(plugin.create_evaluator(_context(REPAIR_PACK, tmp_path)), MindustryEvaluator)


def test_unknown_catalog_id_is_rejected(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    catalog = json.loads((CONSTRUCT_PACK / "catalog.json").read_text(encoding="utf-8"))
    forged = {**catalog, "id": "rhenium-mindustry-v0"}
    (pack / "catalog.json").write_text(json.dumps(forged), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported Mindustry catalog id"):
        MindustryBenchmarkPlugin().load_catalog(pack, "catalog.json")
    with pytest.raises(ValidationError, match="construct catalog id"):
        MindustryConstructCatalog.load(pack)


def test_each_pack_builds_only_its_own_runtime(tmp_path: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    construct_spec = RuntimeCatalog.load(CONSTRUCT_PACK, "runtimes.json").runtimes[0]
    repair_spec = RuntimeCatalog.load(REPAIR_PACK, "runtimes.json").runtimes[0]
    construct_context = _context(CONSTRUCT_PACK, tmp_path)
    repair_context = _context(REPAIR_PACK, tmp_path)

    # Runtime keys are game/runtime-id; two packs sharing one id would shadow each other.
    assert construct_spec.id == "mindustry"
    assert repair_spec.id == "mindustry-159.7"
    assert isinstance(
        plugin.create_runtime_builder(construct_context, construct_spec), MindustryConstructRuntimeBuilder
    )
    assert isinstance(plugin.create_runtime_builder(repair_context, repair_spec), MindustryRuntimeBuilder)
    assert plugin.create_runtime_builder(construct_context, repair_spec) is None
    assert plugin.create_runtime_builder(repair_context, construct_spec) is None


def test_packs_have_distinct_keys() -> None:
    construct = BenchmarkManifest.load(CONSTRUCT_PACK / "benchmark.json")
    repair = BenchmarkManifest.load(REPAIR_PACK / "benchmark.json")

    assert (construct.plugin, construct.pack_id) == ("mindustry", "construct")
    assert (repair.plugin, repair.pack_id) == ("mindustry", "mindustry-core")


def test_construct_task_surfaces_keep_the_generation_contract(tmp_path: Path) -> None:
    plugin = MindustryBenchmarkPlugin()
    catalog = plugin.load_catalog(CONSTRUCT_PACK, "catalog.json")
    task = next(item for item in catalog.tasks if item.id == "transactional-core-router")
    assert isinstance(task, MindustryConstructTask)

    public = plugin.public_task(task)
    assert public["fromScratch"] is True
    assert public["taskKind"] == "generation"
    assert public["gameVersion"] == "159"
    assert "sourceRepository" not in public
    assert plugin.task_prompt(task) == task.authored_prompt.strip()
    assert "generation benchmark" in plugin.agent_system_prompt(task)

    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, _context(CONSTRUCT_PACK, tmp_path))
    assert {path.name for path in attempt.iterdir()} == {
        "build-reference.sh",
        "plugin.hjson",
        "src",
        "task.json",
        "EXAM.md",
        "AGENTS.md",
        "CLAUDE.md",
    }
    marker = json.loads((attempt / "task.json").read_text(encoding="utf-8"))
    assert marker == {"difficulty": "hard", "submission": ".", "fromScratch": True, "language": "java"}
    assert "Implement the public contract in EXAM.md" in (attempt / "AGENTS.md").read_text(encoding="utf-8")
