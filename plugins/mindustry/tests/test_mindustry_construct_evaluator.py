import json
import subprocess
from pathlib import Path

import pytest
from rhenium_mindustry.construct_catalog import (
    MindustryConstructCatalog,
    MindustryConstructTask,
    expected_case_names,
)
from rhenium_mindustry.construct_evaluator import RUNTIME_KEY, MindustryConstructEvaluator

from rhenium.core.evaluation import normalize_evaluation
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

PACK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
TASK_IDS = (
    "transactional-core-router",
    "build-quota-auditor",
    "unit-lease-scheduler",
    "power-grid-controller",
    "wave-threat-arbiter",
    "item-reservation-ledger",
    "wave-budget-planner",
    "logic-link-registry",
    "core-failover-coordinator",
    "blueprint-layout-reconciler",
)


def test_static_check_rejects_missing_submission(tmp_path: Path) -> None:
    task = MindustryConstructTask.model_construct(required_files=["plugin.hjson", "solve.sh"])
    ok, check = MindustryConstructEvaluator._static_check(tmp_path, task)
    assert not ok
    assert check["status"] == "failed"


def test_static_check_accepts_source_submission(tmp_path: Path) -> None:
    (tmp_path / "plugin.hjson").write_text('name: "x"\n', encoding="utf-8")
    (tmp_path / "solve.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    task = MindustryConstructTask.model_construct(required_files=["plugin.hjson", "solve.sh"])
    ok, check = MindustryConstructEvaluator._static_check(tmp_path, task)
    assert ok
    assert check["status"] == "passed"


def test_router_model_workspace_shape_matches_authored_prompt(tmp_path: Path) -> None:
    catalog = MindustryConstructCatalog.load(PACK_ROOT)
    task = next(item for item in catalog.tasks if item.id == "transactional-core-router")
    (tmp_path / "plugin.hjson").write_text("name: router\n", encoding="utf-8")
    source = tmp_path / "src"
    source.mkdir()
    (source / "TransferEngine.java").write_text("class TransferEngine {}\n", encoding="utf-8")
    (source / "TransactionalCoreRouterPlugin.java").write_text(
        "class TransactionalCoreRouterPlugin {}\n", encoding="utf-8"
    )

    ok, check = MindustryConstructEvaluator._static_check(tmp_path, task)
    assert ok
    assert check["status"] == "passed"


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_build_outputs_do_not_fail_source_shape(tmp_path: Path, task_id: str) -> None:
    catalog = MindustryConstructCatalog.load(PACK_ROOT)
    task = next(item for item in catalog.tasks if item.id == task_id)
    for relative in task.required_files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")
    classes = tmp_path / "build" / "candidate" / "classes"
    classes.mkdir(parents=True)
    (classes / "Generated.class").write_bytes(b"class")
    (tmp_path / "build" / "candidate" / "candidate.jar").write_bytes(b"jar")

    ok, check = MindustryConstructEvaluator._static_check(tmp_path, task)
    assert ok
    assert check["status"] == "passed"


@pytest.mark.parametrize("task_id", TASK_IDS)
@pytest.mark.parametrize("outcome", ("passed", "failed", "incomplete"))
def test_full_report_contract_for_every_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    task_id: str,
    outcome: str,
) -> None:
    catalog = MindustryConstructCatalog.load(PACK_ROOT)
    task = next(item for item in catalog.tasks if item.id == task_id)
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = MindustryConstructEvaluator(context, catalog)
    submission = tmp_path / "submission"
    submission.mkdir()
    for relative in task.required_files:
        path = submission / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")

    names = expected_case_names(PACK_ROOT, task)
    observed = names[:-1] if outcome == "incomplete" else names
    output = "\n".join(
        json.dumps({"name": name, "passed": outcome == "passed" or index > 0})
        for index, name in enumerate(observed)
    )

    def fake_run(
        _task: object, _submission: Path, logs: Path, _image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        verifier = logs / "verifier"
        verifier.mkdir(parents=True)
        (verifier / "reward.txt").write_text(
            "1" if outcome == "passed" else "0", encoding="utf-8"
        )
        return subprocess.CompletedProcess([], 0 if outcome == "passed" else 1, output, ""), ""

    monkeypatch.setattr(evaluator.runtime, "run", fake_run)
    artifact = RuntimeArtifact(
        runtime_key=RUNTIME_KEY,
        fingerprint="test",
        kind="docker-image",
        identity="sha256:" + "a" * 64,
        metadata={"images": {task.id: "sha256:" + "a" * 64}},
    )
    report = normalize_evaluation(
        evaluator.evaluate(submission, task, runtimes={RUNTIME_KEY: artifact})
    )
    assert report["complete"] is (outcome != "incomplete")
    assert report["passed"] is (outcome == "passed")
    assert report["score"] == (100.0 if outcome == "passed" else 10.0)
    assert report["criteriaMaximum"] == 1 + len(names)
    expected_criteria = 1 + len(names) if outcome == "passed" else 1
    if outcome == "failed":
        expected_criteria = len(names)
    assert report["criteriaScore"] == expected_criteria


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_reduced_and_invalid_reports_are_incomplete(tmp_path: Path, task_id: str) -> None:
    catalog = MindustryConstructCatalog.load(PACK_ROOT)
    task = next(item for item in catalog.tasks if item.id == task_id)
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = MindustryConstructEvaluator(context, catalog)
    submission = tmp_path / "submission"
    submission.mkdir()
    for relative in task.required_files:
        path = submission / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")

    core = normalize_evaluation(evaluator.evaluate(submission, task, profile="core"))
    assert core["complete"] is False
    assert core["passed"] is False

    (submission / task.required_files[-1]).unlink()
    invalid = normalize_evaluation(evaluator.evaluate(submission, task))
    assert invalid["complete"] is False
    assert invalid["passed"] is False


def test_verifier_container_overlays_the_submission_on_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The starter never contains solve.sh, so the runner must stage the submission itself."""
    catalog = MindustryConstructCatalog.load(PACK_ROOT)
    task = next(item for item in catalog.tasks if item.id == "wave-threat-arbiter")
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = MindustryConstructEvaluator(context, catalog)
    submission = tmp_path / "submission"
    submission.mkdir()
    commands: list[list[str]] = []

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "f" * 64 if args[0] == "create" else "", "")

    monkeypatch.setattr(evaluator.runtime, "_docker", fake_docker)
    evaluator.runtime.run(task, submission, tmp_path / "logs", "sha256:" + "a" * 64)

    created = commands[0]
    script = created[-1]
    assert "cp -R /solution/. /workspace/mindustry/" in script
    assert "install -d -m 0755 /logs /logs/verifier" in script
    assert "/tests/test.sh" in script
    assert "solve.sh" not in script
    assert "--network=none" in created
    assert f"type=bind,source={submission.resolve()},target=/solution,readonly" in created
    # Every capability is dropped, so reports are copied out instead of bound from the host.
    assert not any("target=/logs" in argument for argument in created)
    assert ["cp", f"{'f' * 64}:/logs/.", str((tmp_path / "logs").resolve())] == commands[2][:3]
