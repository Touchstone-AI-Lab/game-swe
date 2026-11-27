from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from rhenium_left_4_dead_2.catalog import Left4Dead2Catalog
from rhenium_left_4_dead_2.evaluator import Left4Dead2Evaluator, Left4Dead2Runtime
from rhenium_left_4_dead_2.plugin import Left4Dead2BenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks/l4d2-core"
TASK_IDS = {
    "l4d2-competitive-release-regressions-easy",
    "l4d2-left4dhooks-api-regressions-medium",
    "l4d2-infected-bots-release-regressions-medium",
    "l4d2-linge-release-regressions-hard-v3",
    "l4d2-mutant-tanks-release-regressions-hard",
    "l4d2-linge-director-state-hard",
    "l4d2-competitive-score-lifecycle-hard",
    "l4d2-vslib-scheduler-persistence-hard",
    "l4d2-confogl-cvar-transactions-hard",
    "l4d2-library-map-tank-state-hard",
}


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def test_catalog_matches_frozen_harbor_contracts() -> None:
    catalog = Left4Dead2Catalog.load(PACK)

    assert catalog.game == "left-4-dead-2"
    assert {task.id for task in catalog.tasks} == TASK_IDS
    assert sum(task.expected_cases for task in catalog.tasks) == 444
    assert sum(task.defect_groups for task in catalog.tasks) == 76
    for task in catalog.tasks:
        harbor = PACK / "private/harbor" / task.id
        assert (PACK / "exams" / f"{task.id}.md").read_bytes() == (
            harbor / "instruction.md"
        ).read_bytes()


def test_materialization_exposes_source_and_prompt_only(tmp_path: Path) -> None:
    plugin = Left4Dead2BenchmarkPlugin()
    task = Left4Dead2Catalog.load(PACK).tasks[0]
    workspace = tmp_path / "workspace"

    plugin.materialize_attempt(task, workspace, _context(tmp_path))

    assert (workspace / task.starter_name).is_dir()
    assert (workspace / "EXAM.md").is_file()
    assert not (workspace / "tests").exists()
    assert not (workspace / "solution").exists()
    assert not (workspace / "validation").exists()
    assert task.container_destination not in (workspace / "EXAM.md").read_text(encoding="utf-8")


def test_static_profile_requires_source_only_shape(tmp_path: Path) -> None:
    plugin = Left4Dead2BenchmarkPlugin()
    task = Left4Dead2Catalog.load(PACK).tasks[0]
    submission = tmp_path / "submission"
    context = _context(tmp_path)
    plugin.materialize_starter(task, submission, context)
    evaluator = Left4Dead2Evaluator(context, Left4Dead2Catalog.load(PACK))

    result = evaluator.evaluate(submission, task, profile="core")
    assert result["score"] == 10.0
    assert result["complete"] is False
    assert result["checks"][0]["status"] == "passed"

    (submission / task.starter_name / "forbidden.smx").write_bytes(b"binary")
    rejected = evaluator.evaluate(submission, task, profile="core")
    assert rejected["score"] == 0.0
    assert rejected["checks"][0]["status"] == "failed"


def test_runtime_invocation_is_offline_read_only_and_capability_bounded(tmp_path: Path) -> None:
    catalog = Left4Dead2Catalog.load(PACK)
    task = catalog.tasks[0]
    runtime = Left4Dead2Runtime(_context(tmp_path), catalog)
    submission = tmp_path / "submission"
    (submission / task.starter_name).mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()
    recorded: list[list[str]] = []

    def capture(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        recorded.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "a" * 64 if arguments[0] == "create" else "", "")

    runtime._docker = capture  # type: ignore[method-assign]
    runtime.image_id = lambda reference: reference  # type: ignore[method-assign]
    runtime.run(task, submission, logs, "sha256:" + "a" * 64)

    command = recorded[0]
    assert command[0] == "create"
    assert "--pull=never" in command
    assert "--user=0:0" in command
    assert "0700 /logs /logs/verifier" in command[-1]
    assert not any("target=/logs" in value for value in command)
    assert recorded[-1] == ["rm", "--force", "a" * 64]
    assert "--network=none" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges:true" in command
    assert any(value.endswith(",readonly") for value in command)
    assert {value.split("=", 1)[1] for value in command if value.startswith("--cap-add=")} == {
        "CHOWN",
        "DAC_OVERRIDE",
        "FOWNER",
        "FSETID",
        "KILL",
        "SETGID",
        "SETUID",
    }


@pytest.mark.parametrize("failure", ["start", "cp", "rm"])
def test_runtime_cleans_up_exact_owned_container_on_failure(tmp_path: Path, failure: str) -> None:
    catalog = Left4Dead2Catalog.load(PACK)
    runtime = Left4Dead2Runtime(_context(tmp_path), catalog)
    calls: list[list[str]] = []

    def invoke(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if arguments[0] == failure:
            if failure == "start":
                raise subprocess.TimeoutExpired("docker start", timeout)
            return subprocess.CompletedProcess(arguments, 1, "", "failure")
        return subprocess.CompletedProcess(arguments, 0, "a" * 64 if arguments[0] == "create" else "", "")

    runtime._docker = invoke  # type: ignore[method-assign]
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        runtime.run(catalog.tasks[0], tmp_path / "submission", tmp_path / "logs", "sha256:" + "b" * 64)
    assert calls[-1] == ["rm", "--force", "a" * 64]


def test_report_reader_rejects_symlinks_escape_and_oversized_files(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("must-not-read")
    link = logs / "link"
    link.symlink_to(secret)
    for path in (link, secret):
        with pytest.raises(ValueError, match="unsafe"):
            Left4Dead2Evaluator._read_report(path, logs)
    large = logs / "large"
    large.write_text("X" * 17)
    with pytest.raises(ValueError, match="oversized"):
        Left4Dead2Evaluator._read_report(large, logs, limit=16)
    assert Left4Dead2Evaluator._read_report(logs / "missing", logs) == ""
