from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rhenium_study import attempts, controls
from rhenium_study.clausemap import ClauseMap
from rhenium_study.e1config import StudyConfig
from rhenium_study.inventory import task_for
from rhenium_study.paths import StudyPaths

ROOT = Path(__file__).parents[3]
TASK = "slay-the-spire/core/stslib-block-ledger-r1"
CREATE_TIMEOUT = (
    "runtime error: Command '['/usr/bin/docker', 'create', '--network=none', 'sha256:abc', "
    "'bash', '-c', 'exec bash /tests/test.sh']' timed out after 300 seconds\n"
)
START_TIMEOUT = (
    "runtime error: Command '['/usr/bin/docker', 'start', '--attach', 'abc']' timed out after 1200 seconds\n"
)


def _paths(tmp_path: Path) -> StudyPaths:
    return StudyPaths(project_root=ROOT, data_root=tmp_path / "data")


def _log(paths: StudyPaths, run_id: str, text: str) -> None:
    log = paths.state_dir / "runs" / run_id / "runtime.log"
    log.parent.mkdir(parents=True)
    log.write_text(text, encoding="utf-8")


def _stopped(run_id: str) -> dict[str, Any]:
    return {"index": 1, "runId": run_id, "outcome": "unattributed", "result": {"complete": False}}


def test_only_an_evaluator_that_never_started_is_voided(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _log(paths, "run-create", CREATE_TIMEOUT)
    _log(paths, "run-start", START_TIMEOUT)
    assert attempts.evaluator_never_started(_stopped("run-create"), paths)
    # The container existed and the verifier ran out of time: that is an observation.
    assert not attempts.evaluator_never_started(_stopped("run-start"), paths)
    assert not attempts.evaluator_never_started(_stopped("run-missing"), paths)
    # A valid outcome is never voided, whatever its log says.
    assert not attempts.evaluator_never_started({**_stopped("run-create"), "outcome": "failed"}, paths)
    plugin_message = {
        "index": 1,
        "outcome": "unattributed",
        "result": {"checks": [{"id": "x", "message": "could not create the isolated Terraria verifier"}]},
    }
    assert attempts.evaluator_never_started(plugin_message, paths)


def _rimworld_failure(paths: StudyPaths, evaluation: str, text: str) -> None:
    record = paths.state_dir / "packs/rimworld/core/evaluations" / evaluation / "failure.private.txt"
    record.parent.mkdir(parents=True)
    record.write_text(text, encoding="utf-8")


def test_a_rimworld_runtime_that_failed_verification_is_voided(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    unverified, integrity = "evaluation-" + "a" * 24, "evaluation-" + "b" * 24
    _rimworld_failure(paths, unverified, "RuntimeError: runtime artifact verification failed\n")
    # Evidence that failed validation after the game ran is an observation, not a void.
    _rimworld_failure(paths, integrity, "EvidenceError: observation identity does not match the evaluation\n")

    def stopped(evaluation: str) -> dict[str, Any]:
        result = {"evaluationId": evaluation, "complete": False}
        return {"index": 1, "outcome": "unattributed", "result": result}

    assert attempts.evaluator_never_started(stopped(unverified), paths)
    assert not attempts.evaluator_never_started(stopped(integrity), paths)
    assert not attempts.evaluator_never_started(stopped("evaluation-" + "c" * 24), paths)
    assert not attempts.evaluator_never_started(stopped("../" + unverified), paths)
    assert not attempts.evaluator_never_started({**stopped(unverified), "outcome": "failed"}, paths)


def _fake_evaluations(
    monkeypatch: pytest.MonkeyPatch, paths: StudyPaths, runs: list[tuple[str, dict[str, Any]]]
) -> None:
    queue = list(runs)

    def evaluate(_task: object, _submission: Path, _paths: StudyPaths) -> dict[str, Any]:
        run_id, result = queue.pop(0)
        return {"id": run_id, "result": result}

    monkeypatch.setattr(controls, "evaluate", evaluate)
    monkeypatch.setattr(controls, "runtime_identity", lambda _task, _paths: {"runtime": "test"})
    monkeypatch.setattr(attempts, "EVALUATION_VOID_BACKOFF_SECONDS", 0)


PASSED = {"complete": True, "passed": True, "score": 100.0, "checks": []}
STOPPED = {"complete": False, "passed": False, "score": 0.0, "checks": []}


def test_a_voided_execution_does_not_use_up_the_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    _log(paths, "run-1", CREATE_TIMEOUT)
    _fake_evaluations(monkeypatch, paths, [("run-1", STOPPED), ("run-2", PASSED)])
    task = task_for(TASK)
    clause_map = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
    root = tmp_path / "attempt"
    scored = attempts._score(paths, task, clause_map, root / "submission", "digest", root)
    assert [item["outcome"] for item in scored["executions"]] == ["resolved"]
    assert [item["index"] for item in scored["voided"]] == [1]
    assert (root / "executions" / "voided" / "1.json").is_file()
    assert (root / "executions" / "2.json").is_file()


def _config() -> StudyConfig:
    return StudyConfig.model_validate(
        {
            "study_id": "reevaluate-test",
            "snapshot_commit": "0" * 40,
            "scaffold": "test",
            "repeats": 1,
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


def test_reevaluate_voids_recorded_executions_and_scores_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    config = _config()
    root = paths.data_root / "e1" / config.study_id / "attempts" / "m--a--r1"
    submission = root / "submission"
    submission.mkdir(parents=True)
    (submission / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    digest = controls.tree_digest(submission)
    for index in (1, 2):
        _log(paths, f"run-{index}", CREATE_TIMEOUT)
        execution = {**_stopped(f"run-{index}"), "index": index, "reason": "stopped", "runtimeIdentity": {}}
        (root / "executions").mkdir(exist_ok=True)
        (root / "executions" / f"{index}.json").write_text(json.dumps(execution), encoding="utf-8")
    record = {
        "attempt_id": "m--a--r1",
        "task": TASK,
        "submissionDigest": digest,
        "outcome": "unattributed",
        "executions": [
            {"index": index, "outcome": "unattributed", "reason": "stopped", "runId": f"run-{index}"}
            for index in (1, 2)
        ],
    }
    (root / "attempt.json").write_text(json.dumps(record), encoding="utf-8")
    _fake_evaluations(monkeypatch, paths, [("run-3", PASSED)])

    updated = attempts.reevaluate(paths, config, "m--a--r1", excluded=())
    assert updated is not None
    assert updated["outcome"] == "resolved" and updated["selectedExecution"] == 3
    assert [item["index"] for item in updated["voidedExecutions"]] == [1, 2]
    assert "reevaluatedAt" in updated
    # Nothing is left to void, so a second pass changes nothing.
    assert attempts.reevaluate(paths, config, "m--a--r1", excluded=()) is None
