from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pack_fixtures import sample_pack_fixture  # noqa: F401
from rhenium_minecraft.catalog import MinecraftCatalog, MinecraftTask
from rhenium_minecraft.evaluator import MinecraftEvaluator
from rhenium_minecraft.runtime_builder import MinecraftRuntimeBuilder

from rhenium.core.evaluation import normalize_evaluation
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog

IMAGE = "sha256:" + "c" * 64
BASE = "sha256:" + "b" * 64
KEY = "minecraft/paper-1.21.11-132"


def make_evaluator(pack: Path, tmp_path: Path) -> MinecraftEvaluator:
    context = BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return MinecraftEvaluator(context, MinecraftCatalog.load(pack))


def prepared(evaluator: MinecraftEvaluator, task: MinecraftTask) -> dict[str, RuntimeArtifact]:
    """A runtime record whose task image carries the labels `prepare` gives it today.

    Docker image inspection is faked: the image exists and has those labels, so a later
    change to the task's `tests/` tree makes the image stale.
    """
    spec = RuntimeCatalog.load(evaluator.context.pack_root, "runtimes.json").runtimes[0]
    builder = MinecraftRuntimeBuilder(evaluator.context, evaluator.catalog)
    source = str(spec.source["sha256"])
    context = builder._tree_fingerprint(builder._task_context(task))
    labels = {IMAGE: builder._labels(spec, task.id, context, source)}
    images = {task.id: IMAGE}

    def image_id(reference: str) -> str:
        return reference

    def image_labels(reference: str) -> dict[str, str]:
        return dict(labels.get(reference, {}))

    evaluator.runtime.image_id = image_id  # type: ignore[method-assign]
    evaluator.runtime.image_labels = image_labels  # type: ignore[method-assign]
    # Preparation required the operator's own EULA record, and evaluation still does.
    builder.eula_record.parent.mkdir(parents=True, exist_ok=True)
    builder.eula_record.write_text("eula=true\n", encoding="utf-8")
    return {
        KEY: RuntimeArtifact(
            runtime_key=KEY,
            fingerprint=builder._fingerprint(spec),
            kind="docker-images",
            identity=builder._artifact_identity(BASE, images),
            metadata={"baseImage": BASE, "images": images, "sourceSha256": source},
        )
    }


def submission_from(pack: Path, tmp_path: Path) -> Path:
    submission = tmp_path / "submission"
    shutil.copytree(pack / "private/harbor/sample-count-command/environment/plugin", submission / "plugin")
    return submission


def verifier_result(
    *,
    unit: list[dict] | None,
    live: list[dict] | None,
    build: str = "passed",
    complete: bool = True,
    passed: bool = False,
) -> dict:
    return {
        "schemaVersion": 1,
        "taskId": "sample-count-command",
        "pluginName": "Sample",
        "build": {"status": build, "tool": "gradle", "artifact": "build/libs/Sample.jar"},
        "unit": {
            "status": "passed" if unit and all(c["passed"] for c in unit) else "failed",
            "cases": unit or [],
        },
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


UNIT_OK = [{"name": "dev.sample.CounterTest.counts", "passed": True, "message": "ok"}]
LIVE_OK = [
    {"name": "plugin is enabled", "passed": True, "message": "ok"},
    {"name": "count command reports two", "passed": True, "message": "ok"},
]


def test_full_pass_scores_100_with_layered_weights(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    evaluator.runtime.run = fake_run(verifier_result(unit=UNIT_OK, live=LIVE_OK, passed=True))  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    runtimes = prepared(evaluator, task)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    normalize_evaluation(report)
    assert report["complete"] and report["passed"] and report["score"] == 100.0
    assert [c["maximum"] for c in report["checks"]] == [0.0, 10.0, 30.0, 60.0]
    assert report["runtime"]["passedAssertions"] == 3 and report["runtime"]["failedAssertions"] == 0
    assert set(report["runtime"]["caseOutcomes"]) == {"dev.sample.CounterTest.counts", *task.server_cases}


def test_failed_target_case_is_complete_but_not_passed(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    live = [dict(LIVE_OK[0]), {"name": "count command reports two", "passed": False, "message": "expected 2"}]
    evaluator.runtime.run = fake_run(verifier_result(unit=UNIT_OK, live=live))  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    runtimes = prepared(evaluator, task)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    normalize_evaluation(report)
    assert report["complete"] and not report["passed"]
    assert report["score"] == 40.0  # build 10 + unit 30
    assert report["runtime"]["caseOutcomes"]["count command reports two"] is False
    assert report["runtime"]["failedAssertions"] == 1


def test_unexpected_case_set_is_incomplete(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    live = [*LIVE_OK, {"name": "forged extra", "passed": True, "message": "ok"}]
    evaluator.runtime.run = fake_run(verifier_result(unit=UNIT_OK, live=live))  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    runtimes = prepared(evaluator, task)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    assert not report["complete"] and not report["passed"]
    assert report["runtime"]["caseOutcomes"] == {}
    assert report["checks"][3]["status"] == "incomplete"


def test_build_failure_is_incomplete_with_zero_score(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    evaluator.runtime.run = fake_run(verifier_result(unit=None, live=None, build="failed", complete=False))  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    runtimes = prepared(evaluator, task)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    normalize_evaluation(report)
    assert report["score"] == 0.0 and not report["complete"]
    assert report["checks"][1]["status"] == "failed"


def test_inconsistent_reward_is_rejected(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    forged = verifier_result(unit=UNIT_OK, live=LIVE_OK, passed=True)
    forged["passed"] = False  # reward says 1, result says not passed
    evaluator.runtime.run = fake_run(forged)  # type: ignore[assignment]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    runtimes = prepared(evaluator, task)
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    assert not report["complete"] and "trusted report" in report["checks"][1]["message"]


def test_core_profile_and_missing_runtime_are_incomplete(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    core = evaluator.evaluate(submission, task, "core", prepared(evaluator, task))
    assert not core["complete"] and core["checks"][1]["status"] == "skipped"
    missing = evaluator.evaluate(submission, task, "full", None)
    assert not missing["complete"] and "runtime prepare minecraft/paper-1.21.11-132" in missing["runtime_log"]


def refuse_to_run(
    submission: Path, logs: Path, image_id: str
) -> tuple[subprocess.CompletedProcess[str], str]:
    raise AssertionError(f"an unverified verifier image must not run: {submission} {logs} {image_id}")


def test_image_built_from_an_older_suite_fails_closed_before_running(
    sample_pack: Path, tmp_path: Path
) -> None:
    """A suite or frozen case set changed after `runtime prepare` must not be graded by the old image.

    The runtime fingerprint covers only runtimes.json and the plugin version, so the record
    stays ready; the old image would report its own older case set and every result would
    come back incomplete (or, with unchanged case names, graded by outdated assertions).
    """
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    runtimes = prepared(evaluator, task)
    suite = sample_pack / "private/harbor/sample-count-command/tests/suite/SampleSuite.java"
    suite.write_text(suite.read_text(encoding="utf-8") + "// a case added after prepare\n", encoding="utf-8")
    evaluator.runtime.run = refuse_to_run  # type: ignore[method-assign]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    normalize_evaluation(report)
    assert not report["complete"] and not report["passed"] and report["score"] == 0.0
    assert [check["status"] for check in report["checks"][1:]] == ["unavailable"] * 3
    assert "does not match this task's current verifier" in report["checks"][3]["message"]
    assert "different build context" in report["runtime_log"]
    assert "run rhenium runtime prepare minecraft/paper-1.21.11-132" in report["runtime_log"]


def test_image_missing_from_docker_fails_closed_before_running(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    runtimes = prepared(evaluator, task)

    def gone(reference: str) -> str:
        raise RuntimeError(f"Minecraft evaluator image is unavailable: {reference}")

    evaluator.runtime.image_id = gone  # type: ignore[method-assign]
    evaluator.runtime.run = refuse_to_run  # type: ignore[method-assign]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    assert not report["complete"] and report["checks"][3]["status"] == "unavailable"
    assert "verifier image for sample-count-command is unavailable in Docker" in report["runtime_log"]


def test_withdrawn_eula_acceptance_fails_closed_before_running(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    runtimes = prepared(evaluator, task)
    (tmp_path / "state" / "eula.txt").write_text("eula=false\n", encoding="utf-8")
    evaluator.runtime.run = refuse_to_run  # type: ignore[method-assign]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", runtimes)
    assert not report["complete"] and not report["passed"]
    assert report["checks"][3]["status"] == "unavailable"
    assert "record your acceptance by writing eula=true" in report["runtime_log"]


def test_record_from_another_runtime_specification_fails_closed(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    record = prepared(evaluator, task)[KEY]
    foreign = {KEY: record.model_copy(update={"fingerprint": "0" * 64})}
    evaluator.runtime.run = refuse_to_run  # type: ignore[method-assign]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    report = evaluator.evaluate(submission_from(sample_pack, tmp_path), task, "full", foreign)
    assert not report["complete"] and report["checks"][3]["status"] == "unavailable"
    assert "runtime artifact is stale" in report["runtime_log"]


def test_shape_rejects_compiled_artifacts_and_symlinks(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    (submission / "plugin" / "Evil.class").write_bytes(b"\xca\xfe")
    ok, check = MinecraftEvaluator._static_check(submission, task)
    assert not ok and "compiled artifacts" in check["message"]
    (submission / "plugin" / "Evil.class").unlink()
    (submission / "plugin" / "build").mkdir()
    (submission / "plugin" / "build" / "Fine.class").write_bytes(b"\xca\xfe")
    (submission / "plugin" / "link").symlink_to("/etc/hostname")
    ok, check = MinecraftEvaluator._static_check(submission, task)
    assert not ok and "symbolic links" in check["message"]


def test_docker_create_arguments_isolate_the_verifier(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    submission = submission_from(sample_pack, tmp_path)
    commands: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(arguments)
        if arguments[0] == "create":
            return subprocess.CompletedProcess(arguments, 0, "a" * 64 + "\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    evaluator.runtime._docker = docker  # type: ignore[method-assign]
    evaluator.runtime.run(submission, tmp_path / "logs", IMAGE)
    create = commands[0]
    assert create[0] == "create" and "--network=none" in create and "--cap-drop=ALL" in create
    assert create[create.index("--env") + 1] == "GCB_SERVER_TIMEOUT=1200"
    assert any(
        item.startswith("type=bind,source=") and item.endswith("/plugin,target=/submission/plugin,readonly")
        for item in create
    )
    assert (
        commands[1][:2] == ["start", "--attach"]
        and commands[2][0] == "cp"
        and commands[3][:2] == ["rm", "--force"]
    )


@pytest.mark.parametrize("profile", ["fast", "extended"])
def test_unknown_profiles_are_rejected(sample_pack: Path, tmp_path: Path, profile: str) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    with pytest.raises(ValueError):
        evaluator.evaluate(tmp_path, evaluator.catalog.tasks[0], profile, None)


def test_shape_allows_the_gradle_wrapper_jar(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    (submission / "plugin" / "gradle" / "wrapper").mkdir(parents=True)
    (submission / "plugin" / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"PK")
    ok, _check = MinecraftEvaluator._static_check(submission, task)
    assert ok
    (submission / "plugin" / "gradle" / "extra.jar").write_bytes(b"PK")
    ok, check = MinecraftEvaluator._static_check(submission, task)
    assert not ok and "extra.jar" in check["message"]
