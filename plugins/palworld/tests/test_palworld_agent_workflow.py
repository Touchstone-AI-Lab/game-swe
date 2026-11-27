from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PREPARE = ROOT / "scripts/prepare-exam"
SCORE = ROOT / "scripts/score-exam"
# The launchers are POSIX shell. Palworld only claims a Windows scoring host,
# so they are exercised through an available bash there rather than skipped.
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="the exam launchers require bash")
TASK_IDS = (
    "guild-storage-ledger",
    "base-containment-mincut",
    "raid-dispatch-queue",
    "server-rule-ballot",
    "guild-draft-canonical-order",
    "outbox-receipt-recovery",
    "pal-workforce-optimal-matching",
    "raid-event-watermark",
    "guild-consistent-checkpoint",
    "world-epoch-fenced-timers",
)
TASK_KEYS = tuple(f"palworld/core/{task_id}" for task_id in TASK_IDS)


def _launcher(script: Path, *arguments: str) -> list[str]:
    return [str(BASH), script.as_posix(), *arguments]


def _isolated_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    state = tmp_path / "state"
    environment["RHENIUM_STATE_DIR"] = str(state)
    environment["RHENIUM_CACHE_DIR"] = str(state / "cache")
    environment["RHENIUM_DATABASE_URL"] = f"sqlite:///{state / 'state.sqlite'}"
    environment["RHENIUM_BENCHMARK_PATH"] = str(ROOT / "benchmarks")
    environment["PATH"] = os.pathsep.join(
        (str(Path(sys.executable).parent), environment.get("PATH", ""))
    )
    return environment


def test_prepare_exam_creates_anonymous_public_bundle_with_ue4ss_api(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    completed = subprocess.run(
        _launcher(PREPARE, TASK_KEYS[0], str(attempt), "practice"),
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_environment(tmp_path),
    )

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in attempt.iterdir()} == {
        "AGENTS.md",
        "CLAUDE.md",
        "EXAM.md",
        "PROMPT.md",
    }
    bundle = "\n".join(path.read_text(encoding="utf-8") for path in attempt.iterdir())
    assert all(task_id not in bundle for task_id in TASK_IDS)
    assert "order:" not in bundle and "第 1 题" not in bundle
    assert "UE4SS API usage contract" in bundle
    assert "RegisterConsoleCommandGlobalHandler" in bundle
    assert "IsDedicatedServer" in bundle
    assert "RheniumService" in bundle
    assert "汇报 Task ID" not in bundle
    assert "anonymous run ID" in bundle
    assert 'score-exam" "$PWD"' in bundle
    assert "Mode: `practice`" in bundle


def test_prepare_exam_bundles_every_palworld_task_without_private_assets(tmp_path: Path) -> None:
    for index, task_key in enumerate(TASK_KEYS):
        attempt = tmp_path / f"attempt-{index}"
        completed = subprocess.run(
            _launcher(PREPARE, task_key, str(attempt)),
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_environment(tmp_path),
        )

        assert completed.returncode == 0, completed.stderr
        bundle = "\n".join(path.read_text(encoding="utf-8") for path in attempt.iterdir())
        assert "ctx:case(" not in bundle, task_key
        assert "load_submission" not in bundle, task_key
        assert "@@RHENIUM_SERVER@@" not in bundle, task_key
        assert "hidden/" not in bundle and "server/" not in bundle, task_key
        assert not list(attempt.rglob("*.lua")), task_key


def test_prepare_exam_refuses_nonempty_attempt(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "keep.txt").write_text("user data\n", encoding="utf-8")
    completed = subprocess.run(
        _launcher(PREPARE, TASK_KEYS[0], str(attempt)),
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_environment(tmp_path),
    )
    assert completed.returncode == 2
    assert "not empty" in completed.stderr
    assert (attempt / "keep.txt").read_text(encoding="utf-8") == "user data\n"


def test_score_exam_command_contains_no_palworld_task_id(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_devenv = fake_bin / "devenv"
    fake_devenv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    fake_devenv.chmod(0o755)
    environment = _isolated_environment(tmp_path)
    environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"

    completed = subprocess.run(
        _launcher(SCORE, str(submission)),
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    emitted = completed.stdout.splitlines()[-4:]
    assert emitted[:3] == ["--", "rhenium", "run-attempt"]
    # The launcher resolves the submission with `pwd -P`, which prints a POSIX
    # path even when the caller passed a native one.
    assert Path(emitted[3]).name == submission.name
    assert all(task_id not in completed.stdout for task_id in TASK_IDS)
