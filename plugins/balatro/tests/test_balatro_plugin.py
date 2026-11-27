from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from rhenium_balatro.catalog import BalatroTask, anonymous_document
from rhenium_balatro.files import digest, read_file, read_json, relative_path
from rhenium_balatro.plugin import BalatroBenchmarkPlugin
from rhenium_balatro.results import anonymous_result
from rhenium_balatro.submission import seal_submission, verify_seal
from sqlalchemy import select

from rhenium.config import Settings
from rhenium.core.catalog import BenchmarkTask
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.registry import discover_plugins
from rhenium.hub import BenchmarkHub
from rhenium.models import Run

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks/balatro"


@pytest.fixture
def plugin() -> BalatroBenchmarkPlugin:
    return BalatroBenchmarkPlugin()


@pytest.fixture
def context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(project_root=ROOT, pack_root=PACK,
                            state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")


def test_installed_entry_points_coexist() -> None:
    found, errors = discover_plugins()
    assert not errors
    assert {"balatro", "contract"} <= found.keys()
    assert isinstance(found["balatro"], BalatroBenchmarkPlugin)


def test_all_ten_materials_are_anonymous_and_byte_preserved(
    plugin: BalatroBenchmarkPlugin, context: BenchmarkContext, tmp_path: Path,
) -> None:
    catalog = plugin.load_catalog(PACK, "catalog.json")
    assert len(catalog.tasks) == 10
    for index, task in enumerate(catalog.tasks):
        assert isinstance(task, BalatroTask)
        destination = tmp_path / f"attempt-{index}"
        plugin.materialize_attempt(task, destination, context)
        paths = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
        assert paths == {*task.required_files, "EXAM.md", "AGENTS.md", "CLAUDE.md",
                         *(n for n in task.public_documents if n != "CONTRACT.md")}
        for name in task.required_files:
            assert digest(read_file(destination, name)) == task.snapshot_files[name]
        for name in paths:
            data = read_file(destination, name)
            assert task.id.encode() not in data
            assert b"C:\\Touchstone" not in data
        original = read_file(PACK / task.package, "CONTRACT.md").decode("utf-8")
        assert plugin.task_prompt(task).startswith(anonymous_document(original, task.id))
        sealed = seal_submission(destination, task, context.state_dir / "sealed")
        verify_seal(sealed)
        assert all(not n.startswith("starter/") for n in sealed.files)


@pytest.mark.parametrize("name", ["../a", "a/../b", "/abs", "C:/escape", "a\\b", "a//b", "con.lua"])
def test_reject_unsafe_paths(name: str) -> None:
    with pytest.raises(ValueError):
        relative_path(name)


def test_duplicate_json_keys_fail(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text('{"x": 1, "x": 2}')
    with pytest.raises(ValueError, match="duplicate"):
        read_json(tmp_path, "bad.json")


def test_starter_reuses_exact_bytes_preserves_conflicting_edits(
    plugin: BalatroBenchmarkPlugin, context: BenchmarkContext, tmp_path: Path,
) -> None:
    task = plugin.load_catalog(PACK, "catalog.json").tasks[0]
    target = tmp_path / "work"
    plugin.materialize_starter(task, target, context)
    plugin.materialize_starter(task, target, context)
    file = target / "starter/joker.lua"
    file.write_text("user edits")
    with pytest.raises(ValueError, match="existing starter differs"):
        plugin.materialize_starter(task, target, context)
    assert file.read_text() == "user edits"


@pytest.mark.parametrize("change", ["immutable", "extra", "missing"])
def test_invalid_submission_rejected(
    plugin: BalatroBenchmarkPlugin, context: BenchmarkContext, tmp_path: Path, change: str,
) -> None:
    task = plugin.load_catalog(PACK, "catalog.json").tasks[0]
    assert isinstance(task, BalatroTask)
    target = tmp_path / "attempt"
    plugin.materialize_attempt(task, target, context)
    if change == "immutable":
        (target / task.immutable_files[0]).write_text("changed")
    elif change == "extra":
        (target / "starter/extra.lua").write_text("unreviewed")
    else:
        (target / task.editable_files[0]).unlink()
    with pytest.raises(ValueError):
        seal_submission(target, task, context.state_dir)


def test_catalog_rejects_snapshot_drift(plugin: BalatroBenchmarkPlugin, tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(PACK, pack)
    (pack / "public/v02/growth-v2/starter/joker.lua").write_text("changed")
    with pytest.raises(ValueError, match="frozen public asset changed"):
        plugin.load_catalog(pack, "catalog.json")


def test_result_projection_drops_private_strings() -> None:
    result = anonymous_result({"id": "run-" + "a" * 16, "taskKey": "balatro/core/private-task",
        "error": "C:\\private\\gold.lua", "result": {"score": 0, "passed": False,
        "complete": False, "category": "incomplete", "reason": "environment_failure",
        "privateExpected": "secret", "checks": [{"id": "hidden-case", "passed": False,
        "expected": "secret", "detail": "C:\\private"}], "runtime_log": "secret"}})
    text = json.dumps(result)
    assert not any(x in text for x in ("private", "secret", "hidden-case", "balatro"))
    assert result["id"] == "run-" + "a" * 16
    assert result["result"]["complete"] is False


@pytest.mark.parametrize("bad", [[], "unknown"])
def test_projection_rejects_inconsistent_outcome(bad: object) -> None:
    value = anonymous_result({"status": "passed", "result": {
        "complete": True, "passed": True, "score": 1, "category": bad, "reason": "none"}})
    assert value["status"] == "failed"
    assert value["result"]["complete"] is False and value["result"]["passed"] is False


def test_real_hub_prepare_and_incomplete_full_without_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"
    state = project / "state"
    settings = Settings(root=project, state_dir=state, cache_dir=state / "cache",
                        database_url=f"sqlite:///{state / 'db.sqlite'}",
                        benchmark_paths=(PACK,), web_dist=None)
    hub = BenchmarkHub(settings, manifest_paths=(PACK / "benchmark.json",))
    assert len(hub.task_keys) == 10
    before = {p: digest(p.read_bytes()) for p in PACK.rglob("*") if p.is_file()}
    for index, key in enumerate(hub.task_keys):
        attempt = tmp_path / f"anon-{index}"
        hub.prepare_attempt(key, attempt, mode="strict", score_command=project / "score-wrapper")
        # Managed runtimes are gated by core before the evaluator is entered.
        # The former unbound Windows route returned an evaluator-level incomplete.
        with pytest.raises(RuntimeError, match="runtime balatro/.* is not prepared") as caught:
            hub.evaluate_attempt(attempt, profile="full")
        text = str(caught.value)
        assert key not in text and key.split("/")[-1] not in text
        with hub.database.session_factory() as session:
            row = session.scalars(select(Run).where(Run.task_key == key)).one()
            assert row.status == "error" and row.score == 0
            assert json.loads(row.result_json).get("passed") is not True
    BenchmarkHub(settings, manifest_paths=(PACK / "benchmark.json",))
    assert before == {p: digest(p.read_bytes()) for p in PACK.rglob("*") if p.is_file()}


def test_actual_independent_plugins_isolate_same_local_id_and_failures(tmp_path: Path) -> None:
    plugins, errors = discover_plugins()
    assert not errors
    source = plugins["balatro"].load_catalog(PACK, "catalog.json").tasks[0]
    contract_task = BenchmarkTask.model_validate({
        key: getattr(source, key) for key in BenchmarkTask.model_fields
    }).model_copy(update={"required_files": ["answer.txt"]})
    project = tmp_path / "project"
    contract_pack = project / "benchmarks/contract"
    contract_pack.mkdir(parents=True)
    (contract_pack / "benchmark.json").write_text(json.dumps({"schema_version": 2, "pack_id": "core",
        "plugin": "contract", "catalog": "catalog.json"}))
    (contract_pack / "catalog.json").write_text(json.dumps({"id": "core", "version": "1.0.0",
        "game": "contract", "name": {"en": "Fixture", "zh": "Fixture"},
        "description": {"en": "Fixture", "zh": "Fixture"},
        "tasks": [contract_task.model_dump(mode="json")]}), encoding="utf-8")
    (contract_pack / "expected.txt").write_text("fixture-ok")
    state = project / "state"
    settings = Settings(root=project, state_dir=state, cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'db.sqlite'}", benchmark_paths=(), web_dist=None)
    hub = BenchmarkHub(settings, plugins=plugins,
        manifest_paths=(PACK / "benchmark.json", contract_pack / "benchmark.json"))
    first = tmp_path / "first"
    second = tmp_path / "second"
    for game, attempt in (("balatro", first), ("contract", second)):
        hub.prepare_attempt(f"{game}/core/{source.id}", attempt, "strict", project / "score-wrapper")
    (second / "answer.txt").write_text("fixture-ok")
    with pytest.raises(RuntimeError, match="runtime balatro/.* is not prepared"):
        hub.evaluate_attempt(first, profile="full")
    passed = hub.evaluate_attempt(second, profile="full")
    assert passed["result"]["passed"] is True
    with hub.database.session_factory() as session:
        failed = session.scalars(select(Run).where(Run.task_key == f"balatro/core/{source.id}")).one()
        assert failed.status == "error" and failed.score == 0
        assert json.loads(failed.result_json).get("passed") is not True
        assert failed.id != passed["id"]
    assert f"balatro/core/{source.id}" in hub.task_keys
    assert f"contract/core/{source.id}" in hub.task_keys
    assert hub.report(game_id="balatro")["runs"] == 1
    assert hub.report(game_id="contract")["runs"] == 1


def test_seal_detects_postcopy_tampering(
    plugin: BalatroBenchmarkPlugin, context: BenchmarkContext, tmp_path: Path,
) -> None:
    task = plugin.load_catalog(PACK, "catalog.json").tasks[0]
    assert isinstance(task, BalatroTask)
    target = tmp_path / "attempt"
    plugin.materialize_attempt(task, target, context)
    sealed = seal_submission(target, task, context.state_dir)
    (sealed.directory / "joker.lua").write_text("tampered")
    with pytest.raises(ValueError, match="sealed submission changed"):
        verify_seal(sealed)
