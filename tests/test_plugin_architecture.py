from __future__ import annotations

import json
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from rhenium.config import Settings
from rhenium.core.registry import discover_plugins
from rhenium.hub import BenchmarkHub
from rhenium.models import Attempt
from tests.conftest import FixturePlugin, write_fixture_pack


def _settings(tmp_path: Path) -> Settings:
    state = tmp_path / "state"
    return Settings(
        root=tmp_path,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(tmp_path / "benchmarks",),
        web_dist=None,
    )


def test_core_can_start_with_no_plugins_or_packs(tmp_path: Path) -> None:
    hub = BenchmarkHub(_settings(tmp_path), plugins={}, manifest_paths=())

    assert hub.list_games() == []
    assert hub.list_packs() == []
    assert hub.list_tasks() == []
    assert hub.health()["ok"] is True


def test_two_plugins_isolate_identical_local_task_ids(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = FixturePlugin("first", "game-a")
    second = FixturePlugin("second", "game-b")
    first_manifest = write_fixture_pack(
        settings.benchmark_paths[0], plugin_id="first", game_id="game-a"
    )
    second_manifest = write_fixture_pack(
        settings.benchmark_paths[0], plugin_id="second", game_id="game-b"
    )
    hub = BenchmarkHub(
        settings,
        plugins={"first": first, "second": second},
        manifest_paths=(first_manifest, second_manifest),
    )
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")

    first_run = hub.evaluate_task("game-a/core/shared-task", submission)
    second_run = hub.evaluate_task("game-b/core/shared-task", submission)
    first_attempt = tmp_path.parent / f"{tmp_path.name}-attempt-a"
    second_attempt = tmp_path.parent / f"{tmp_path.name}-attempt-b"
    first_attempt.mkdir()
    second_attempt.mkdir()
    try:
        hub.register_attempt("game-a/core/shared-task", first_attempt, "strict")
        hub.register_attempt("game-b/core/shared-task", second_attempt, "strict")
        with hub.database.session_factory() as session:
            attempt_keys = {row.task_key for row in session.scalars(select(Attempt)).all()}
    finally:
        first_attempt.rmdir()
        second_attempt.rmdir()

    assert hub.task_keys == ("game-a/core/shared-task", "game-b/core/shared-task")
    assert first_run["taskKey"] != second_run["taskKey"]
    assert attempt_keys == {"game-a/core/shared-task", "game-b/core/shared-task"}
    assert first.contexts[0].state_dir != second.contexts[0].state_dir
    assert hub.report(game_id="game-a")["runs"] == 1
    assert hub.report(game_id="game-b")["runs"] == 1


def test_recursive_scan_isolates_missing_plugin_and_malformed_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    valid = write_fixture_pack(settings.benchmark_paths[0] / "nested")
    missing = settings.benchmark_paths[0] / "missing" / "benchmark.json"
    missing.parent.mkdir(parents=True)
    missing.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pack_id": "missing",
                "plugin": "not-installed",
                "catalog": "catalog.json",
            }
        ),
        encoding="utf-8",
    )
    (missing.parent / "catalog.json").write_text("{}", encoding="utf-8")
    broken = settings.benchmark_paths[0] / "broken" / "benchmark.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("not json\n", encoding="utf-8")

    hub = BenchmarkHub(settings, plugins={"fixture": FixturePlugin()})

    assert hub.task_keys == ("fixture/core/shared-task",)
    health = hub.health()
    assert health["degraded"] is True
    assert len(health["discoveryErrors"]) == 2
    assert any("not installed" in issue["message"] for issue in health["discoveryErrors"])
    assert valid.parent.resolve() == hub.benchmarks[next(iter(hub.benchmarks))].context.pack_root


def test_duplicate_pack_key_disables_every_conflicting_pack(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = write_fixture_pack(settings.benchmark_paths[0], directory="first")
    second = write_fixture_pack(settings.benchmark_paths[0], directory="second")

    hub = BenchmarkHub(
        settings,
        plugins={"fixture": FixturePlugin()},
        manifest_paths=(first, second),
    )

    assert hub.list_packs() == []
    assert hub.list_tasks() == []
    assert len(hub.health()["discoveryErrors"]) == 2
    assert all("duplicate benchmark pack key" in item["message"] for item in hub.discovery_errors)


def test_benchmark_pack_is_treated_as_read_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    manifest = write_fixture_pack(settings.benchmark_paths[0])
    pack_directories = [manifest.parent, *manifest.parent.rglob("*")]
    for path in pack_directories:
        path.chmod(0o555 if path.is_dir() else 0o444)
    before = {
        path.relative_to(manifest.parent): path.read_bytes()
        for path in manifest.parent.rglob("*")
        if path.is_file()
    }
    try:
        hub = BenchmarkHub(
            settings,
            plugins={"fixture": FixturePlugin()},
            manifest_paths=(manifest,),
        )
        submission = tmp_path / "submission"
        submission.mkdir()
        (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")
        result = hub.evaluate_task("fixture/core/shared-task", submission)

        after = {
            path.relative_to(manifest.parent): path.read_bytes()
            for path in manifest.parent.rglob("*")
            if path.is_file()
        }
        context = next(iter(hub.benchmarks.values())).context
        assert result["status"] == "passed"
        assert after == before
        assert context.state_dir.is_relative_to(settings.state_dir)
        assert (context.state_dir / "public/tasks.json").is_file()
        assert (context.state_dir / "workspaces/shared-task/TASK.md").is_file()
    finally:
        for path in reversed(pack_directories):
            path.chmod(0o755 if path.is_dir() else 0o644)


def test_runtime_unavailable_is_a_degradation_not_a_global_failure(tmp_path: Path) -> None:
    class UnavailablePlugin(FixturePlugin):
        def create_evaluator(self, context: Any) -> Any:
            evaluator = super().create_evaluator(context)
            evaluator.runtime_status = lambda: {  # type: ignore[method-assign]
                "id": "missing-engine",
                "available": False,
                "reason": "engine is not installed",
            }
            return evaluator

    settings = _settings(tmp_path)
    manifest = write_fixture_pack(settings.benchmark_paths[0])
    hub = BenchmarkHub(
        settings,
        plugins={"fixture": UnavailablePlugin()},
        manifest_paths=(manifest,),
    )

    health = hub.health()
    assert health["ok"] is True
    assert health["degraded"] is True
    assert health["taskCount"] == 1
    assert health["degradedItems"][0]["id"] == "fixture/core"


class _FakeEntryPoint:
    def __init__(self, name: str, value: object | Exception):
        self.name = name
        self.value = value

    def load(self) -> object:
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def test_entry_point_discovery_isolates_duplicate_and_import_failure() -> None:
    candidates = cast(
        tuple[EntryPoint, ...],
        (
            _FakeEntryPoint("duplicate", FixturePlugin("duplicate", "game-a")),
            _FakeEntryPoint("duplicate", FixturePlugin("duplicate", "game-b")),
            _FakeEntryPoint("broken", ImportError("optional SDK exploded")),
            _FakeEntryPoint("healthy", FixturePlugin("healthy", "healthy-game")),
        ),
    )

    plugins, errors = discover_plugins(candidates)

    assert set(plugins) == {"healthy"}
    assert {item["id"] for item in errors} == {"duplicate", "broken"}
