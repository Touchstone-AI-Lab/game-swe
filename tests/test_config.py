from __future__ import annotations

import os
from pathlib import Path

from pytest import MonkeyPatch

from rhenium.config import Settings


def test_defaults_are_game_neutral_and_local(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings.load()

    assert settings.root == tmp_path
    assert settings.state_dir == tmp_path / ".rhenium/hub"
    assert settings.cache_dir == tmp_path / ".rhenium/hub/cache"
    assert settings.database_url == f"sqlite:///{tmp_path / '.rhenium/hub/state.sqlite'}"
    assert settings.benchmark_paths == (tmp_path / "benchmarks",)


def test_benchmark_path_accepts_multiple_system_separated_roots(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("RHENIUM_BENCHMARK_PATH", os.pathsep.join((str(first), str(second))))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "runtime"))

    settings = Settings.load(tmp_path)

    assert settings.benchmark_paths == (first, second)
    assert settings.state_dir == tmp_path / "runtime"


def test_core_creates_state_but_never_benchmark_directories(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path)

    settings.ensure_directories()

    assert settings.state_dir.is_dir()
    assert settings.cache_dir.is_dir()
    assert not (tmp_path / "benchmarks").exists()
