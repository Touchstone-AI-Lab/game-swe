from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mindustry_fixtures import SERVER_CASES, sample_pack_fixture  # noqa: F401
from rhenium_mindustry.catalog import MindustryCatalog
from rhenium_mindustry.evaluator import MindustryEvaluator

from rhenium.core.evaluation import normalize_evaluation
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

IMAGE = "sha256:" + "c" * 64
KEY = "mindustry/mindustry-159.7"


def make_evaluator(pack: Path, tmp_path: Path) -> MindustryEvaluator:
    context = BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return MindustryEvaluator(context, MindustryCatalog.load(pack))


def artifact(task_id: str) -> dict[str, RuntimeArtifact]:
    return {
        KEY: RuntimeArtifact(
            runtime_key=KEY,
            fingerprint="f",
            kind="docker-images",
            identity="sha256:" + "d" * 64,
            metadata={"images": {task_id: IMAGE}},
        )
    }


def submission_from(pack: Path, tmp_path: Path) -> Path:
    submission = tmp_path / "submission"
    shutil.copytree(
        pack / "private/harbor/sample-count-command/environment/mindustry", submission / "mindustry"
    )
    return submission


def verifier_result(
    *, live: list[dict[str, Any]] | None, build: str = "passed", complete: bool = True, passed: bool = False
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": "sample-count-command",
        "build": {"status": build},
        "live": {
            "status": "passed" if live and all(c["passed"] for c in live) else "failed",
            "cases": live or [],
        },
        "complete": complete,
        "passed": passed,
        "reward": 1 if passed else 0,
    }


def fake_run(
    result: dict[str, Any],
) -> Callable[[Path, Path, str], tuple[subprocess.CompletedProcess[str], str]]:
    def run(submission: Path, logs: Path, image_id: str) -> tuple[subprocess.CompletedProcess[str], str]:
        del submission
        assert image_id == IMAGE
        verifier = logs / "verifier"
        verifier.mkdir(parents=True)
        (verifier / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (verifier / "reward.txt").write_text(f"{result['reward']}\n", encoding="utf-8")
        (verifier / "verifier.log").write_text("VERIFICATION\n", encoding="utf-8")
        return subprocess.CompletedProcess(["docker"], 0 if result["passed"] else 1, "", ""), "image=x\n"

    return run


LIVE_OK = [{"name": name, "passed": True, "message": "ok"} for name in SERVER_CASES]


def prepared(evaluator: MindustryEvaluator, result: dict[str, Any]) -> None:
    evaluator.runtime.run = fake_run(result)  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]


def test_full_pass_scores_100(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    prepared(evaluator, verifier_result(live=LIVE_OK, passed=True))
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", artifact(task.id))
    normalize_evaluation(report)
    assert report["complete"] and report["passed"] and report["score"] == 100.0
    assert [c["maximum"] for c in report["checks"]] == [0.0, 10.0, 90.0]
    assert report["runtime"]["passedAssertions"] == 4 and report["runtime"]["failedAssertions"] == 0
    assert set(report["runtime"]["caseOutcomes"]) == set(task.server_cases)
    assert report["runtime"]["mindustryVersion"] == "159.7"


def test_failed_target_case_is_complete_but_not_passed(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    live = [dict(case) for case in LIVE_OK]
    live[1] = {"name": SERVER_CASES[1], "passed": False, "message": "expected 2"}
    prepared(evaluator, verifier_result(live=live))
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", artifact(task.id))
    normalize_evaluation(report)
    assert report["complete"] and not report["passed"]
    assert report["score"] == 10.0
    assert report["runtime"]["caseOutcomes"][SERVER_CASES[1]] is False
    assert report["runtime"]["failedAssertions"] == 1
    assert report["checks"][2]["status"] == "failed"


def test_unexpected_case_set_is_incomplete(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    prepared(evaluator, verifier_result(live=[*LIVE_OK, {"name": "forged extra", "passed": True}]))
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", artifact(task.id))
    assert not report["complete"] and not report["passed"] and report["score"] == 0.0
    assert report["runtime"]["caseOutcomes"] == {}
    assert report["checks"][2]["status"] == "incomplete"


def test_build_failure_is_incomplete_with_zero_score(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    prepared(evaluator, verifier_result(live=None, build="failed", complete=False))
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", artifact(task.id))
    normalize_evaluation(report)
    assert report["score"] == 0.0 and not report["complete"]
    assert report["checks"][1]["status"] == "failed"


def test_inconsistent_reward_is_rejected(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    forged = verifier_result(live=LIVE_OK, passed=True)
    forged["passed"] = False  # reward says 1, result says not passed
    prepared(evaluator, forged)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", artifact(task.id))
    assert not report["complete"] and "trusted report" in report["checks"][1]["message"]


def test_core_profile_and_missing_runtime_are_incomplete(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    core = evaluator.evaluate(submission, task, "core", artifact(task.id))
    assert not core["complete"] and core["checks"][1]["status"] == "skipped"
    missing = evaluator.evaluate(submission, task, "full", None)
    assert not missing["complete"] and "runtime prepare mindustry/mindustry-159.7" in missing["runtime_log"]
    evaluator.runtime.status = lambda: {"available": False, "reason": "no docker"}  # type: ignore[method-assign]
    down = evaluator.evaluate(submission, task, "full", artifact(task.id))
    assert not down["complete"] and down["checks"][2]["status"] == "unavailable"


def test_shape_rejects_compiled_artifacts_symlinks_and_missing_roots(
    sample_pack: Path, tmp_path: Path
) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    ok, check = MindustryEvaluator._static_check(submission, task)
    assert ok, check
    (submission / "mindustry" / "Evil.class").write_bytes(b"\xca\xfe")
    ok, check = MindustryEvaluator._static_check(submission, task)
    assert not ok and "compiled artifacts" in check["message"]
    (submission / "mindustry" / "Evil.class").unlink()
    (submission / "mindustry" / "link").symlink_to("/etc/hostname")
    ok, check = MindustryEvaluator._static_check(submission, task)
    assert not ok and "symbolic links" in check["message"]
    (submission / "mindustry" / "link").unlink()
    shutil.rmtree(submission / "mindustry" / "server")
    ok, check = MindustryEvaluator._static_check(submission, task)
    assert not ok and "server/src" in check["message"]
    report = evaluator.evaluate(submission, task, "full", artifact(task.id))
    assert not report["complete"] and report["checks"][0]["status"] == "failed"


def test_docker_create_arguments_isolate_the_verifier(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    submission = submission_from(sample_pack, tmp_path)
    commands: list[list[str]] = []
    timeouts: list[float] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        commands.append(arguments)
        timeouts.append(timeout)
        if arguments[0] == "create":
            return subprocess.CompletedProcess(arguments, 0, "a" * 64 + "\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    evaluator.runtime._docker = docker  # type: ignore[method-assign]
    evaluator.runtime.run(submission, tmp_path / "logs", IMAGE)
    create = commands[0]
    assert create[0] == "create" and "--network=none" in create and "--cap-drop=ALL" in create
    assert any(
        item.startswith("type=bind,source=")
        and item.endswith("/mindustry,target=/submission/mindustry,readonly")
        for item in create
    )
    assert (
        commands[1][:2] == ["start", "--attach"]
        and commands[2][0] == "cp"
        and commands[3][:2] == ["rm", "--force"]
    )
    assert timeouts[0] >= 300 and timeouts[3] >= 300
    with pytest.raises(RuntimeError, match="immutable"):
        evaluator.runtime.run(submission, tmp_path / "logs", "rhenium-mindustry:latest")


@pytest.mark.parametrize("profile", ["fast", "extended"])
def test_unknown_profiles_are_rejected(sample_pack: Path, tmp_path: Path, profile: str) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    with pytest.raises(ValueError):
        evaluator.evaluate(tmp_path, evaluator.catalog.tasks[0], profile, None)


def test_create_timeout_removes_the_labelled_container(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    submission = submission_from(sample_pack, tmp_path)
    commands: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        commands.append(arguments)
        if arguments[0] == "create":
            raise subprocess.TimeoutExpired(arguments, timeout)
        if arguments[0] == "ps":
            return subprocess.CompletedProcess(arguments, 0, "b" * 64 + "\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    evaluator.runtime._docker = docker  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="did not answer"):
        evaluator.runtime.run(submission, tmp_path / "logs", IMAGE)
    label = commands[0][commands[0].index("--label") + 1]
    assert label.startswith("io.rhenium.mindustry.run=")
    assert commands[1][:2] == ["ps", "--all"] and f"label={label}" in commands[1]
    assert commands[2] == ["rm", "--force", "b" * 64]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    task = evaluator.catalog.tasks[0]
    report = evaluator.evaluate(submission, task, "full", artifact(task.id))
    assert not report["complete"] and "trusted report" in report["checks"][1]["message"]
