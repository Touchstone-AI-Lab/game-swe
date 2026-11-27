from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_study import controls, deferred
from rhenium_study.aggregate import load_ledger, pending_evaluation
from rhenium_study.attempts import PENDING
from rhenium_study.e1config import StudyConfig
from rhenium_study.paths import StudyPaths

ROOT = Path(__file__).parents[3]
TASK = "slay-the-spire/core/stslib-block-ledger-r1"


def _config() -> StudyConfig:
    return StudyConfig.model_validate(
        {
            "study_id": "deferred-test",
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
            "deferred_evaluation": ["slay-the-spire"],
        }
    )


def _pending_attempt(paths: StudyPaths, config: StudyConfig, attempt: str) -> str:
    root = paths.data_root / "e1" / config.study_id / "attempts" / attempt
    submission = root / "submission"
    (submission / "plugin").mkdir(parents=True)
    (submission / "plugin" / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    digest = controls.tree_digest(submission)
    record = {"attempt_id": attempt, "task": TASK, "submissionDigest": digest, "outcome": PENDING}
    (root / "attempt.json").write_text(json.dumps(record), encoding="utf-8")
    return digest


def _run(complete: bool, passed: bool) -> dict[str, object]:
    return {
        "id": "run-x",
        "taskKey": TASK,
        "status": "passed" if passed else "failed",
        "result": {"complete": complete, "passed": passed, "checks": [], "runtime": {"status": "incomplete"}},
    }


def test_pending_attempts_leave_the_ledger_until_imported(tmp_path: Path) -> None:
    paths = StudyPaths(project_root=ROOT, data_root=tmp_path / "data")
    config = _config()
    digest = _pending_attempt(paths, config, "m--a--r1")
    study_root = paths.data_root / "e1" / config.study_id
    assert load_ledger(study_root, excluded=()) == []
    assert pending_evaluation(study_root, excluded=()) == ["m--a--r1"]

    kit = tmp_path / "kit"
    assert deferred.export(paths, config, "digest", kit, excluded=())["attempts"] == 1
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["attempts"][0]["submissionDigest"] == digest
    assert (kit / "attempts" / "m--a--r1" / "submission" / "plugin" / "Main.java").is_file()
    assert {"README.md", "evaluate.ps1", "evaluate.sh"} <= {path.name for path in kit.iterdir()}
    with pytest.raises(ValueError, match="already exists"):
        deferred.export(paths, config, "digest", kit, excluded=())

    with pytest.raises(ValueError, match="different study"):
        deferred.import_results(paths, config, "other-digest", kit, "win11", excluded=())

    # An incomplete first run is followed by the one permitted retry, as locally.
    results = kit / "attempts" / "m--a--r1"
    (results / "result-1.json").write_text("\ufeff" + json.dumps(_run(False, False)), encoding="utf-8")
    (results / "result-2.json").write_text(json.dumps(_run(True, True)), encoding="utf-8")
    imported = deferred.import_results(paths, config, "digest", kit, "win11", excluded=())
    assert imported == [{"attemptId": "m--a--r1", "outcome": "resolved"}]
    record = json.loads((study_root / "attempts" / "m--a--r1" / "attempt.json").read_text(encoding="utf-8"))
    assert [item["outcome"] for item in record["executions"]] == ["unattributed", "resolved"]
    assert record["evaluationHost"] == "win11" and pending_evaluation(study_root, excluded=()) == []
    assert deferred.import_results(paths, config, "digest", kit, "win11", excluded=()) == []


def test_a_kit_that_evaluated_another_task_is_rejected(tmp_path: Path) -> None:
    paths = StudyPaths(project_root=ROOT, data_root=tmp_path / "data")
    config = _config()
    _pending_attempt(paths, config, "m--a--r1")
    kit = tmp_path / "kit"
    deferred.export(paths, config, "digest", kit, excluded=())
    wrong = {**_run(True, True), "taskKey": "slay-the-spire/core/other"}
    (kit / "attempts" / "m--a--r1" / "result-1.json").write_text(json.dumps(wrong), encoding="utf-8")
    with pytest.raises(ValueError, match="different task"):
        deferred.import_results(paths, config, "digest", kit, "win11", excluded=())
