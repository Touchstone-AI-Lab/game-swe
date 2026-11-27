from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from rhenium_slay_the_spire.catalog import SlayTheSpireCatalog
from rhenium_slay_the_spire.evaluator import SlayTheSpireEvaluator, parse_surefire_reports
from spire_fixtures import sample_pack_fixture  # noqa: F401

from rhenium.core.evaluation import normalize_evaluation
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

IMAGE = "sha256:" + "c" * 64
KEY = "slay-the-spire/modthespire-jdk8-maven"


def make_evaluator(pack: Path, tmp_path: Path) -> SlayTheSpireEvaluator:
    context = BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return SlayTheSpireEvaluator(context, SlayTheSpireCatalog.load(pack))


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
    if not (submission / "modthespire").is_dir():
        shutil.copytree(
            pack / "private/harbor/sample-regressions/environment/modthespire",
            submission / "modthespire",
        )
    return submission


def surefire_report(cases: dict[str, str | None]) -> str:
    """A Surefire XML report; each value is ``None`` (pass), ``failure`` or ``error``."""
    body = []
    for name, problem in cases.items():
        owner, method = name.rsplit(".", 1)
        inner = f'<{problem} message="boom"/>' if problem else ""
        body.append(f'<testcase name="{method}" classname="{owner}">{inner}</testcase>')
    return f'<?xml version="1.0"?><testsuite>{"".join(body)}</testsuite>'


SAMPLE_CASES: dict[str, str | None] = {
    "gcb.SampleTest.a": None,
    "gcb.SampleTest.b": None,
    "gcb.OtherTest.c": None,
    "gcb.OtherTest.d": None,
}


def fake_run(
    summary: str | None, reward: str, reports: dict[str, str] | None = None
) -> Callable[..., tuple[subprocess.CompletedProcess[str], str]]:
    def run(task, submission: Path, logs: Path, image_id: str):  # type: ignore[no-untyped-def]
        del task, submission
        assert image_id == IMAGE
        verifier = logs / "verifier"
        verifier.mkdir(parents=True, exist_ok=True)
        if reports is not None:
            (verifier / "surefire").mkdir()
            for filename, text in reports.items():
                (verifier / "surefire" / filename).write_text(text, encoding="utf-8")
        if summary is not None:
            (verifier / "summary.txt").write_text(summary + "\n", encoding="utf-8")
        (verifier / "reward.txt").write_text(reward + "\n", encoding="utf-8")
        (verifier / "maven.log").write_text("[INFO] BUILD\n", encoding="utf-8")
        return subprocess.CompletedProcess(["docker"], 0, "", ""), "image=x\n"

    return run


# Exercise the historical JUnit parser internally; public evaluation must reject
# loader-only tasks even when every one of these diagnostic assertions passes.
def evaluate(evaluator: SlayTheSpireEvaluator, pack: Path, tmp_path: Path, **kwargs):  # type: ignore[no-untyped-def]
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    task = evaluator.catalog.tasks[0]
    return evaluator._evaluate_loader_diagnostic(
        submission_from(pack, tmp_path), task, "full", artifact(task.id), **kwargs
    )


def test_a_complete_loader_diagnostic_scores_one_hundred(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=0 Tests run: 4, Failures: 0, Errors: 0, Skipped: 0", "1"
    )
    report = evaluate(evaluator, sample_pack, tmp_path)
    normalize_evaluation(report)
    assert report["complete"] and report["passed"] and report["score"] == 100.0
    assert [check["maximum"] for check in report["checks"]] == [10.0, 90.0]
    assert report["runtime"]["passedAssertions"] == 4
    assert report["runtime"]["failedAssertions"] == 0
    assert report["runtime"]["expectedAssertions"] == 4


def test_failed_assertions_are_complete_but_not_passing(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=1 Tests run: 4, Failures: 1, Errors: 1, Skipped: 0", "0"
    )
    report = evaluate(evaluator, sample_pack, tmp_path)
    normalize_evaluation(report)
    assert report["complete"] and not report["passed"] and report["score"] == 10.0
    assert report["runtime"]["passedAssertions"] == 2
    assert report["runtime"]["failedAssertions"] == 2
    assert "2/4 private assertions passed" in report["checks"][1]["message"]


@pytest.mark.parametrize(
    ("summary", "reward", "why"),
    [
        (None, "0", "a submission that does not compile writes no summary"),
        ("entrypoint_exit=0 Tests run: 3, Failures: 0, Errors: 0, Skipped: 0", "1", "fewer cases"),
        ("entrypoint_exit=0 Tests run: 4, Failures: 0, Errors: 0, Skipped: 1", "1", "skipped case"),
    ],
)
def test_an_unobserved_assertion_set_is_incomplete(
    sample_pack: Path, tmp_path: Path, summary: str | None, reward: str, why: str
) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    evaluator.runtime.run = fake_run(summary, reward)  # type: ignore[method-assign]
    report = evaluate(evaluator, sample_pack, tmp_path)
    assert not report["complete"] and not report["passed"], why
    assert report["checks"][1]["status"] == "incomplete"
    assert report["score"] == 10.0


def test_a_forged_reward_without_a_clean_suite_does_not_pass(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    # The verifier's own exit status and Surefire counts must agree with the reward.
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=1 Tests run: 4, Failures: 0, Errors: 0, Skipped: 0", "1"
    )
    report = evaluate(evaluator, sample_pack, tmp_path)
    assert report["complete"] and not report["passed"]
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=0 Tests run: 4, Failures: 0, Errors: 0, Skipped: 0", "0"
    )
    assert not evaluate(evaluator, sample_pack, tmp_path)["passed"]


def test_core_profile_and_missing_runtime_are_incomplete(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    core = evaluator._evaluate_loader_diagnostic(submission, task, "core", artifact(task.id))
    assert not core["complete"] and core["checks"][1]["status"] == "skipped"
    missing = evaluator._evaluate_loader_diagnostic(submission, task, "full", None)
    assert not missing["complete"]
    assert "runtime prepare slay-the-spire/modthespire-jdk8-maven" in missing["runtime_log"]


def test_shape_rejects_symlinks_compiled_artifacts_and_missing_files(
    sample_pack: Path, tmp_path: Path
) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    ok, check = SlayTheSpireEvaluator._static_check(submission, task)
    assert ok and check["score"] == 10.0
    (submission / "modthespire" / "Evil.class").write_bytes(b"\xca\xfe")
    ok, check = SlayTheSpireEvaluator._static_check(submission, task)
    assert not ok and "compiled artifacts" in check["message"]
    (submission / "modthespire" / "Evil.class").unlink()
    (submission / "modthespire" / "target").mkdir()
    (submission / "modthespire" / "target" / "Fine.class").write_bytes(b"\xca\xfe")
    wrapper = submission / "modthespire" / ".mvn" / "wrapper"
    wrapper.mkdir(parents=True)
    (wrapper / "maven-wrapper.jar").write_bytes(b"PK")
    ok, _check = SlayTheSpireEvaluator._static_check(submission, task)
    assert ok, "build output and the Maven wrapper jar are part of an upstream tree"
    (submission / "modthespire" / "link").symlink_to("/etc/hostname")
    ok, check = SlayTheSpireEvaluator._static_check(submission, task)
    assert not ok and "symbolic links" in check["message"]


def test_missing_required_file_fails_the_shape_gate(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    task = evaluator.catalog.tasks[0]
    submission = submission_from(sample_pack, tmp_path)
    (submission / "modthespire" / "pom.xml").unlink()
    ok, check = SlayTheSpireEvaluator._static_check(submission, task)
    assert not ok and "pom.xml" in check["message"]


def test_docker_run_arguments_isolate_the_verifier(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    commands: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    evaluator.runtime._docker = docker  # type: ignore[method-assign]
    logs = tmp_path / "logs"
    logs.mkdir()
    evaluator.runtime.run(evaluator.catalog.tasks[0], submission_from(sample_pack, tmp_path), logs, IMAGE)
    (run,) = commands
    assert run[0] == "run" and "--network=none" in run and "--cap-drop=ALL" in run
    assert "--pull=never" in run
    assert any(item.endswith("target=/submission,readonly") for item in run)
    assert any(item.endswith("target=/tests,readonly") for item in run)
    staging = run[-1]
    assert "bash /tests/test.sh" in staging
    # The pinned Maven image has no rsync; staging must use coreutils only and must
    # not try to preserve ownership, which needs a capability the container drops.
    assert "rsync" not in staging
    assert "cp -R --preserve=mode,timestamps" in staging
    assert "cp -a" not in staging
    assert "surefire-reports/TEST-*.xml /logs/verifier/surefire/" in staging
    # The container's root creates the report directory; the host must be able to remove it.
    assert "mkdir -p -m 0777 /logs/verifier/surefire" in staging


@pytest.mark.parametrize("profile", ["fast", "extended"])
def test_unknown_profiles_are_rejected(sample_pack: Path, tmp_path: Path, profile: str) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    with pytest.raises(ValueError):
        evaluator.evaluate(tmp_path, evaluator.catalog.tasks[0], profile, None)


def test_surefire_reports_name_every_counted_case(sample_pack: Path, tmp_path: Path) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    cases = {**SAMPLE_CASES, "gcb.OtherTest.c": "failure", "gcb.OtherTest.d": "error"}
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=1 Tests run: 4, Failures: 1, Errors: 1, Skipped: 0",
        "0",
        {"TEST-gcb.xml": surefire_report(cases)},
    )
    report = evaluate(evaluator, sample_pack, tmp_path)
    normalize_evaluation(report)
    assert report["complete"] and not report["passed"]
    assert report["runtime"]["caseOutcomes"] == {
        "gcb.SampleTest.a": True,
        "gcb.SampleTest.b": True,
        "gcb.OtherTest.c": False,
        "gcb.OtherTest.d": False,
    }
    assert [case["name"] for case in report["checks"][1]["details"]["cases"]] == list(cases)


@pytest.mark.parametrize(
    "reports",
    [
        None,
        {"TEST-a.xml": surefire_report({"gcb.SampleTest.a": None})},
        {
            "TEST-a.xml": surefire_report(SAMPLE_CASES),
            "TEST-b.xml": surefire_report({"gcb.SampleTest.a": None}),
        },
        {"TEST-a.xml": "<testsuite><testcase"},
        {"TEST-a.xml": surefire_report({**SAMPLE_CASES, "gcb.SampleTest.a": "failure"})},
    ],
)
def test_case_names_that_disagree_with_the_summary_are_withheld(
    sample_pack: Path, tmp_path: Path, reports: dict[str, str] | None
) -> None:
    evaluator = make_evaluator(sample_pack, tmp_path)
    evaluator.runtime.run = fake_run(  # type: ignore[method-assign]
        "entrypoint_exit=0 Tests run: 4, Failures: 0, Errors: 0, Skipped: 0", "1", reports
    )
    report = evaluate(evaluator, sample_pack, tmp_path)
    assert report["passed"], "case names are reporting only and never change the verdict"
    assert report["runtime"]["caseOutcomes"] == {}
    assert "details" not in report["checks"][1]


def test_surefire_parser_strips_junit5_parentheses_and_rejects_skips(tmp_path: Path) -> None:
    (tmp_path / "TEST-x.xml").write_text(
        '<testsuite><testcase name="works()" classname="gcb.X"/></testsuite>', encoding="utf-8"
    )
    assert parse_surefire_reports(tmp_path) == [{"name": "gcb.X.works", "passed": True, "message": "ok"}]
    (tmp_path / "TEST-y.xml").write_text(
        '<testsuite><testcase name="later" classname="gcb.Y"><skipped/></testcase></testsuite>',
        encoding="utf-8",
    )
    assert parse_surefire_reports(tmp_path) is None
    assert parse_surefire_reports(tmp_path / "absent") is None


def test_an_invalid_native_submission_is_incomplete_and_never_passes(tmp_path: Path) -> None:
    from spire_fixtures import PACK

    context = BenchmarkContext(
        project_root=PACK.parents[1],
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = SlayTheSpireEvaluator(context, SlayTheSpireCatalog.load(PACK))
    native = next(task for task in evaluator.catalog.tasks if task.native_runtime)
    report = evaluator.evaluate(tmp_path, native, "full", None)
    assert report["complete"] is False and report["passed"] is False and report["score"] == 0.0
    assert [check["id"] for check in report["checks"]] == ["submission-shape", "native-engine"]


@pytest.mark.parametrize("profile", ["core", "full"])
def test_loader_only_tasks_cannot_produce_full_results(
    sample_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    # The real pack no longer has a loader-only task; the sample pack keeps that path covered.
    evaluator = make_evaluator(sample_pack, tmp_path)
    (task,) = evaluator.catalog.tasks
    assert not task.native_runtime and not task.game_backed
    submission = tmp_path / "submission"
    shutil.copytree(sample_pack / "private" / "harbor" / task.id / "environment" / task.starter_name,
                    submission / task.starter_name)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a loader-only task must not run a verifier as the real game")

    monkeypatch.setattr(evaluator, "_evaluate_loader_diagnostic", forbidden)
    monkeypatch.setattr(evaluator, "_evaluate_native", forbidden)
    report = evaluator.evaluate(submission, task, profile, artifact(task.id))
    normalize_evaluation(report)
    assert report["complete"] is False and report["passed"] is False
    assert report["score"] == 10.0
    assert report["checks"][1]["status"] == "incomplete"
    assert "no real-game verifier" in report["checks"][1]["message"]
