"""Container-path tests of the construct pack, restored from the pre-repair plugin.

Construct tasks are bound to their own runtime key, and the whole workspace (the
mod root) is mounted as the submission.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_dst.construct_catalog import DstConstructCatalog
from rhenium_dst.container import CONSTRUCT_RUNTIME_KEY, RUNTIME_KEY
from rhenium_dst.evaluator import DstEvaluator
from rhenium_dst.runtime import DstRuntimeConfig

from rhenium.core.runtime import RuntimeArtifact

PACK = Path(__file__).parents[3] / "benchmarks/dst-construct"
IMAGE = "sha256:" + "a" * 64


def _report(*, complete: bool, passed: bool) -> dict[str, Any]:
    return {
        "score": 100.0 if passed else 35.0,
        "complete": complete,
        "passed": passed,
        "checks": [{"id": "headless-server", "status": "passed" if passed else "failed"}],
        "runtime": {"status": "passed" if passed else "failed"},
        "runtime_log": "server log tail",
    }


@pytest.mark.parametrize(
    "variant",
    [
        "gold", "broken", "missing-report", "missing-reward", "bad-reward", "reward-mismatch",
        "passed-but-incomplete", "invalid-json", "invalid-shape", "nonzero", "symlink", "oversized",
    ],
)
def test_container_verdict_requires_a_consistent_trusted_report(tmp_path: Path, variant: str) -> None:
    task = DstConstructCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))
    evaluator.container.status = lambda: {"available": True}  # type: ignore[method-assign]
    submission = tmp_path / "submission"
    submission.mkdir()
    seen: list[str] = []

    def run(mod_root: Path, logs: Path, image_id: str) -> tuple[subprocess.CompletedProcess[str], str]:
        assert mod_root == submission.resolve()
        seen.append(image_id)
        verifier = logs / "verifier"
        verifier.mkdir()
        report: Any = _report(complete=True, passed=variant != "broken")
        reward = "0" if variant == "broken" else "1"
        if variant == "bad-reward":
            reward = "success"
        elif variant == "reward-mismatch":
            reward = "0"
        elif variant == "passed-but-incomplete":
            report = _report(complete=False, passed=True)
        elif variant == "invalid-shape":
            report = ["not", "an", "object"]
        content = "{not json" if variant == "invalid-json" else json.dumps(report)
        if variant == "oversized":
            content = json.dumps({**report, "runtime_log": "X" * 8_100_000})
        if variant != "missing-report":
            (verifier / "evaluation.json").write_text(content)
        if variant == "symlink":
            private = tmp_path / "private"
            private.write_text("1")
            (verifier / "reward.txt").symlink_to(private)
        elif variant != "missing-reward":
            (verifier / "reward.txt").write_text(reward)
        return subprocess.CompletedProcess([], 1 if variant == "nonzero" else 0, "", ""), "image=fixture\n"

    evaluator.container.run = run  # type: ignore[method-assign]
    artifact = RuntimeArtifact(
        runtime_key=CONSTRUCT_RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
        identity="fixture", metadata={"images": {task.id: IMAGE}},
    )
    result = evaluator.evaluate(submission, task, runtimes={CONSTRUCT_RUNTIME_KEY: artifact})

    assert seen == [IMAGE]
    assert result["passed"] is (variant == "gold")
    assert result["complete"] is (variant in {"gold", "broken"})
    if result["complete"]:
        assert result["runtime_log"].startswith("image=fixture\n")
    else:
        assert result["score"] == 0.0
        assert result["checks"][0]["status"] == "unavailable"


def test_missing_task_image_and_unavailable_docker_fail_closed(tmp_path: Path) -> None:
    task = DstConstructCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))

    def forbidden(
        mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        raise AssertionError("the container must not start")

    evaluator.container.run = forbidden  # type: ignore[method-assign]
    submission = tmp_path / "submission"
    submission.mkdir()
    empty = RuntimeArtifact(runtime_key=CONSTRUCT_RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                            identity="fixture", metadata={"images": {}})
    result = evaluator.evaluate(submission, task, runtimes={CONSTRUCT_RUNTIME_KEY: empty})
    assert result["complete"] is False and result["passed"] is False
    assert "runtime prepare" in result["runtime_log"]

    evaluator.container.status = lambda: {"available": False, "reason": "no daemon"}  # type: ignore[method-assign]
    ready = empty.model_copy(update={"metadata": {"images": {task.id: IMAGE}}})
    result = evaluator.evaluate(submission, task, runtimes={CONSTRUCT_RUNTIME_KEY: ready})
    assert result["complete"] is False and result["passed"] is False
    assert "no daemon" in result["runtime_log"]


def test_core_profile_never_uses_the_container(tmp_path: Path, sample_mod: Path) -> None:
    task = DstConstructCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))

    def forbidden(
        mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        raise AssertionError("the container must not start")

    evaluator.container.run = forbidden  # type: ignore[method-assign]
    artifact = RuntimeArtifact(runtime_key=CONSTRUCT_RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                               identity="fixture", metadata={"images": {task.id: IMAGE}})
    result = evaluator.evaluate(sample_mod, task, profile="core", runtimes={CONSTRUCT_RUNTIME_KEY: artifact})
    assert result["complete"] is False and result["passed"] is False


def test_construct_tasks_ignore_an_artifact_of_the_repair_runtime(tmp_path: Path) -> None:
    task = DstConstructCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))

    def forbidden(
        mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        raise AssertionError("the repair runtime must not evaluate a construct task")

    evaluator.container.run = forbidden  # type: ignore[method-assign]
    submission = tmp_path / "submission"
    submission.mkdir()
    foreign = RuntimeArtifact(runtime_key=RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                              identity="fixture", metadata={"images": {task.id: IMAGE}})
    result = evaluator.evaluate(submission, task, profile="full", runtimes={RUNTIME_KEY: foreign})
    assert result["complete"] is False and result["passed"] is False
    # Without its own runtime the construct evaluator falls back to a native
    # server, which this configuration does not have.
    assert result["runtime"]["status"] == "unavailable"
