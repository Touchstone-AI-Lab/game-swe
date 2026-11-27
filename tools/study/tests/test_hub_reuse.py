from __future__ import annotations

import fcntl
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rhenium_study import attempts, controls, hubs
from rhenium_study.attempts import Scheduled
from rhenium_study.e1config import StudyConfig
from rhenium_study.inventory import task_for
from rhenium_study.paths import StudyPaths

ROOT = Path(__file__).parents[3]
TASK = "slay-the-spire/core/stslib-block-ledger-r1"
PASSED = {"complete": True, "passed": True, "score": 100.0, "checks": []}


def _starter_locked(paths: StudyPaths) -> bool:
    """Whether some open file description holds the starter lock (flock conflicts even in-process)."""
    with (paths.locks / "hub-startup.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False


class _FakeHub:
    """Stands in for BenchmarkHub: counts constructions and where the starter is read."""

    constructed: list[bool] = []
    prepared: list[bool] = []
    evaluated: list[str] = []
    paths: StudyPaths

    def __init__(self, settings: Any) -> None:
        del settings
        _FakeHub.constructed.append(_starter_locked(_FakeHub.paths))
        self.database = SimpleNamespace(engine=SimpleNamespace(dispose=lambda: None))
        plugin = SimpleNamespace(
            task_prompt=lambda _task: "requirement", agent_system_prompt=lambda _task: "system"
        )
        self._loaded = SimpleNamespace(plugin=plugin)

    def prepare_attempt(self, task_key: str, path: Path, mode: str, score_command: Path) -> dict[str, Any]:
        del task_key, mode, score_command
        _FakeHub.prepared.append(_starter_locked(_FakeHub.paths))
        path.mkdir(parents=True, exist_ok=True)
        (path / "EXAM.md").write_text("exam\n", encoding="utf-8")
        return {}

    def _loaded_task(self, task_key: str) -> tuple[str, Any, Any]:
        return task_key, self._loaded, SimpleNamespace()

    def evaluate_task(self, task_key: str, submission: Path, profile: str) -> dict[str, Any]:
        assert profile == "full" and submission.is_dir()
        _FakeHub.evaluated.append(task_key)
        return {"id": f"run-{len(_FakeHub.evaluated)}", "result": PASSED}


@pytest.fixture
def fake_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StudyPaths:
    paths = StudyPaths(project_root=ROOT, data_root=tmp_path / "data")
    monkeypatch.setattr(hubs, "_HUBS", {})
    monkeypatch.setattr(hubs, "BenchmarkHub", _FakeHub)
    monkeypatch.setattr(_FakeHub, "constructed", [])
    monkeypatch.setattr(_FakeHub, "prepared", [])
    monkeypatch.setattr(_FakeHub, "evaluated", [])
    monkeypatch.setattr(_FakeHub, "paths", paths, raising=False)
    return paths


def _config() -> StudyConfig:
    return StudyConfig.model_validate(
        {
            "study_id": "hub-reuse-test",
            "snapshot_commit": "0" * 40,
            "scaffold": "test",
            "repeats": 2,
            "schedule_seed": 1,
            "agent_image": "agent:test",
            "budget": {
                "step_limit": 1,
                "command_timeout_seconds": 1,
                "wall_time_limit_seconds": 60,
                "request_timeout_seconds": 30,
            },
            "models": [
                {"id": "m", "litellm_model": "x", "base_url": "https://example.test", "api_key_file": "k"}
            ],
            "tasks": [TASK],
            "e2_selection_rule": "none",
            "e2_max_cases": 1,
        }
    )


def test_one_process_constructs_its_study_hub_once_for_every_attempt(
    fake_hub: StudyPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_hub

    def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return {"setupFailed": False, "containerExit": 0, "containerFailure": None}

    monkeypatch.setattr(attempts, "_generate", generate)
    monkeypatch.setattr(controls, "runtime_identity", lambda _task, _paths: "runtime=test")
    config = _config()
    for item in attempts.schedule(config):
        record = attempts.run_attempt(paths, config, "digest", item)
        assert record["outcome"] == "resolved"
    # Two prepares and two evaluations, one construction; the construction and every
    # preparation held the starter lock, and nothing kept holding it afterwards.
    assert _FakeHub.constructed == [True]
    assert _FakeHub.prepared == [True, True]
    assert _FakeHub.evaluated == [TASK, TASK]
    assert not _starter_locked(paths)
    # A restored starter reuses the same Hub, again under the lock.
    workspace = paths.data_root / "restored"
    workspace.mkdir()
    (workspace / "EXAM.md").write_text("exam\n", encoding="utf-8")
    starter_digest = controls.tree_digest(workspace)
    (workspace / "EXAM.md").write_text("edited by the interrupted generation\n", encoding="utf-8")
    attempts._restore_starter(paths, Scheduled("m--x--r9", "m", TASK, 9, 9), workspace, starter_digest)
    assert controls.tree_digest(workspace) == starter_digest
    assert _FakeHub.constructed == [True] and _FakeHub.prepared == [True, True, True]


def test_the_hub_is_kept_per_study_data_directory(fake_hub: StudyPaths, tmp_path: Path) -> None:
    first = hubs.open_hub(fake_hub)
    assert hubs.open_hub(StudyPaths(project_root=ROOT, data_root=tmp_path / "data")) is first
    other = StudyPaths(project_root=ROOT, data_root=tmp_path / "other")
    _FakeHub.paths = other
    assert hubs.open_hub(other) is not first
    assert len(_FakeHub.constructed) == 2


def test_a_control_copies_the_shared_starter_under_the_starter_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = StudyPaths(project_root=ROOT, data_root=tmp_path / "data")
    task = task_for(TASK)
    starter = controls.starter_workspace(task, paths)
    assert starter == paths.state_dir / "packs" / task.game / task.pack / "workspaces" / task.task
    starter.mkdir(parents=True)
    (starter / "task.json").write_text("{}\n", encoding="utf-8")
    copies: list[tuple[Path, bool]] = []
    original = shutil.copytree

    def copytree(source: Path, target: Path, **kwargs: Any) -> Any:
        copies.append((Path(source), _starter_locked(paths)))
        return original(source, target, **kwargs)

    monkeypatch.setattr(controls.shutil, "copytree", copytree)
    submission = controls.materialize(task, controls.IMPLICIT[0], paths, starter)
    assert copies == [(starter, True)]
    assert (submission / "task.json").read_text(encoding="utf-8") == "{}\n"
    assert not _starter_locked(paths)


def test_a_generation_the_repeat_guard_stopped_is_failed_without_evaluation(
    fake_hub: StudyPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_hub

    def generate(*args: object, **_kwargs: object) -> dict[str, Any]:
        agent_out = args[4]
        assert isinstance(agent_out, Path)
        (agent_out / "model.json").write_text(
            '{"steps": 5, "exitStatus": "RepeatedActionLoop", "changedFiles": []}', encoding="utf-8"
        )
        (agent_out / "egress.jsonl").write_text('{"event": "allowed"}\n', encoding="utf-8")
        return {"setupFailed": False, "containerExit": 0, "containerFailure": None}

    monkeypatch.setattr(attempts, "_generate", generate)
    base = _config()
    config = base.model_copy(update={"budget": base.budget.model_copy(update={"repeated_action_limit": 5})})
    item = attempts.schedule(config)[0]
    record = attempts.run_attempt(paths, config, "digest", item)
    assert record["outcome"] == record["auditedOutcome"] == "failed"
    assert "5 times in a row" in record["outcomeReason"]
    assert record["generation"]["terminationReason"] == "repeated-action-loop"
    assert record["executions"] == [] and _FakeHub.evaluated == []
