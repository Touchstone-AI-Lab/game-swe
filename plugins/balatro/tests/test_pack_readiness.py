"""Cross-game readiness for the actual independently packaged plugins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from rhenium_balatro.plugin import BalatroBenchmarkPlugin
from rhenium_slay_the_spire.plugin import SlayTheSpireBenchmarkPlugin

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("missing_game", [None, "balatro", "slay-the-spire"])
def test_required_runtime_readiness_across_two_packaged_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_game: str | None,
) -> None:
    state = tmp_path / "state"
    settings = Settings(root=tmp_path, state_dir=state, cache_dir=state / "cache",
                        database_url=f"sqlite:///{state / 'state.sqlite'}",
                        benchmark_paths=(), web_dist=None)
    plugins = [BalatroBenchmarkPlugin(), SlayTheSpireBenchmarkPlugin()]
    hub = BenchmarkHub(settings, plugins={plugin.id: plugin for plugin in plugins},
        auth_providers={}, evaluation_hosts={}, manifest_paths=tuple(
            ROOT / "benchmarks" / name / "benchmark.json" for name in ("balatro", "slay-the-spire-core")
        ))
    assert not hub.discovery_errors
    assert len(hub.benchmarks) == 2
    required: dict[str, set[str]] = {}
    for key, loaded in hub.benchmarks.items():
        assert loaded.runtime_catalog is not None
        catalog = loaded.runtime_catalog
        required[key.game_id] = {runtime for bindings in catalog.task_bindings.values()
                                 for runtime in bindings}
        assert required[key.game_id]
        assert {spec.id for spec in catalog.runtimes} - required[key.game_id]
    original = hub.runtime_manager.list

    def metadata(game_id: str | None = None) -> list[dict[str, Any]]:
        assert game_id is not None
        return [{**row, "ready": game_id != missing_game and row["id"] in required[game_id]}
                for row in original(game_id)]

    monkeypatch.setattr(hub.runtime_manager, "list", metadata)
    for pack in hub.list_packs():
        assert pack["runtime"]["available"] is (pack["gameId"] != missing_game)
        assert any(not row["ready"] for row in pack["runtime"]["runtimes"])
