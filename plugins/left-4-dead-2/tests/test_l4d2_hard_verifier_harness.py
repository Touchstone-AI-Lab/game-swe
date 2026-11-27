"""Harness regressions found by the Hub full-profile runs of the five hard tasks.

The private verifiers run inside the task images; these tests import them on the host
only to exercise their plumbing helpers, never a behavior suite.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

HARBOR = Path(__file__).parents[3] / "benchmarks/l4d2-core/private/harbor"
SOURCEPAWN = (
    "l4d2-competitive-score-lifecycle-hard",
    "l4d2-confogl-cvar-transactions-hard",
    "l4d2-library-map-tank-state-hard",
)
VSCRIPT = ("l4d2-linge-director-state-hard", "l4d2-vslib-scheduler-persistence-hard")


def _verifier(task: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    tests = HARBOR / task / "tests"
    monkeypatch.setenv("GCB_TESTS", str(tests))
    name = f"l4d2_verify_{task.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, tests / "verify.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _SlowReap:
    """A killed server whose threads are torn down only after a long wait."""

    def __init__(self, reap_after: float) -> None:
        self.pid = 4242
        self.reap_after = reap_after
        self.waits: list[float | None] = []

    def poll(self) -> int | None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        if timeout is None or timeout < self.reap_after:
            raise subprocess.TimeoutExpired("srcds_run", timeout or 0.0)
        return -9


@pytest.mark.parametrize("task", SOURCEPAWN + VSCRIPT)
def test_slow_teardown_after_sigkill_is_waited_for(task: str, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _verifier(task, monkeypatch)
    signals: list[int] = []
    monkeypatch.setattr(verify.os, "killpg", lambda _pid, sig: signals.append(sig))
    process = _SlowReap(reap_after=30.0)
    verify.stop_process(process)
    assert signals == [verify.signal.SIGTERM, verify.signal.SIGKILL]
    assert process.waits == [5, verify.SERVER_REAP_SECONDS]


@pytest.mark.parametrize("task", SOURCEPAWN + VSCRIPT)
def test_unreaped_server_is_an_environment_failure(task: str, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _verifier(task, monkeypatch)
    monkeypatch.setattr(verify.os, "killpg", lambda _pid, _sig: None)
    with pytest.raises(verify.EnvironmentFailure):
        verify.stop_process(_SlowReap(reap_after=float("inf")))


@pytest.mark.parametrize("task", SOURCEPAWN)
def test_failure_detail_names_the_rejection_not_engine_noise(
    task: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = _verifier(task, monkeypatch)
    noise = "Invalid counterterrorist spawnpoint at (2303.4,2816.0,2816.0)"
    exception = "\n".join([
        noise,
        "L 09/23/2026 - 17:05:04: [SM] Exception reported: ",
        "==========",
        "Native 'L4D_GetVersusMaxCompletionScore' should not be used before OnMapStart",
        "==========",
        noise,
    ])
    detail = verify.failure_detail(exception)
    assert "[SM] Exception reported" in detail and "should not be used before OnMapStart" in detail
    # The detail is printed after "FAIL <case>:", so it must stay on one line.
    assert "\n" not in detail
    boot_noise = "\n".join([
        noise,
        "Using breakpad crash handler",
        "dlopen failed trying to load:",
        "with error:",
        "[UPDATER] --- END ERRORS FROM AUTOMATIC UPDATER ---",
    ])
    assert verify.failure_detail(boot_noise) == "suite did not complete its exact case contract"
    assert verify.failure_detail(boot_noise, reported_final=False) == (
        "server exited or timed out before the suite reported FINAL"
    )


def test_score_plugins_are_staged_in_numbered_load_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = _verifier("l4d2-competitive-score-lifecycle-hard", monkeypatch)
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    monkeypatch.setattr(verify, "PLUGIN_DIR", plugins)
    names = ("00_left4dhooks.smx", "01_l4d2lib.smx", "l4d2_hybrid_scoremod_zone.smx", "99_gcb_scoring.smx")
    staged = []
    for name in names:
        source = tmp_path / f"compiled-{name}"
        source.write_bytes(name.encode())
        staged.append((source, plugins / name))
    created: list[str] = []
    real_copy = verify.shutil.copy2

    def record(source: Path, destination: Path) -> Any:
        created.append(Path(destination).name)
        return real_copy(source, destination)

    monkeypatch.setattr(verify.shutil, "copy2", record)
    # SourceMod autoloads raw directory order; model a creation-ordered directory.
    monkeypatch.setattr(verify.os, "listdir", lambda _path: list(created))
    verify.stage_in_load_order(tuple(staged))
    assert created == list(names)

    # A filesystem that enumerates entries in another order must fail closed.
    for name in names:
        (plugins / name).unlink()
    created.clear()
    monkeypatch.setattr(verify.os, "listdir", lambda _path: sorted(created, reverse=True))
    with pytest.raises(verify.EnvironmentFailure, match="out of order"):
        verify.stage_in_load_order(tuple(staged))


def test_score_verifier_no_longer_creates_the_consumer_before_its_dependency() -> None:
    # Regression for the Hub run where a copy-on-write filesystem listed the score
    # plugin first and its OnMapStart called Left4DHooks before that plugin started.
    source = (HARBOR / "l4d2-competitive-score-lifecycle-hard/tests/verify.py").read_text(encoding="utf-8")
    assert "shutil.copy2(target_binary, target_plugin)" not in source
    staging = source[source.index("stage_in_load_order(("):]
    names = ("core_plugin", "library_plugin", "target_plugin", "suite_plugin")
    order = [staging.index(name) for name in names]
    assert order == sorted(order)


@pytest.mark.parametrize("task", SOURCEPAWN + VSCRIPT)
def test_boot_deadline_leaves_room_for_a_congested_host(task: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # A healthy boot reaches FINAL in 5-15 s; the old 55 s budget turned a stalled
    # plugin load on a busy host into a complete failing verdict for SourcePawn suites.
    verify = _verifier(task, monkeypatch)
    assert verify.SUITE_DEADLINE_SECONDS >= 240
    source = (HARBOR / task / "tests/verify.py").read_text(encoding="utf-8")
    if task in SOURCEPAWN:
        assert "timeout: int = SUITE_DEADLINE_SECONDS" in source
    else:
        assert "collect_server(process, nonce, timeout=SUITE_DEADLINE_SECONDS)" in source
