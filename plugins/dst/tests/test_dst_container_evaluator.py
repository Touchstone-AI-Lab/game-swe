from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_dst.catalog import DstCatalog
from rhenium_dst.container import RUNTIME_KEY
from rhenium_dst.evaluator import DstEvaluator
from rhenium_dst.runtime import DstRuntimeConfig

from rhenium.core.runtime import RuntimeArtifact

PACK = Path(__file__).parents[3] / "benchmarks/dst"
IMAGE = "sha256:" + "a" * 64


def _submission(tmp_path: Path) -> Path:
    task = DstCatalog.load(PACK).tasks[0]
    submission = tmp_path / "submission"
    shutil.copytree(PACK / "private" / "harbor" / task.id / "environment" / "mod", submission / "mod")
    return submission


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
    task = DstCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))
    evaluator.container.status = lambda: {"available": True}  # type: ignore[method-assign]
    submission = _submission(tmp_path)
    seen: list[str] = []

    def run(mod_root: Path, logs: Path, image_id: str) -> tuple[subprocess.CompletedProcess[str], str]:
        assert mod_root == submission.resolve() / "mod"
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
        runtime_key=RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
        identity="fixture", metadata={"images": {task.id: IMAGE}},
    )
    result = evaluator.evaluate(submission, task, runtimes={RUNTIME_KEY: artifact})

    assert seen == [IMAGE]
    assert result["passed"] is (variant == "gold")
    assert result["complete"] is (variant in {"gold", "broken"})
    if result["complete"]:
        assert result["runtime_log"].startswith("image=fixture\n")
    else:
        assert result["score"] == 0.0
        assert result["checks"][-1]["status"] == "incomplete"
        assert result["runtime"]["caseOutcomes"] == {}


def test_missing_task_image_and_unavailable_docker_fail_closed(tmp_path: Path) -> None:
    task = DstCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))

    def forbidden(
        mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        raise AssertionError("the container must not start")

    evaluator.container.run = forbidden  # type: ignore[method-assign]
    submission = _submission(tmp_path)
    empty = RuntimeArtifact(runtime_key=RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                            identity="fixture", metadata={"images": {}})
    result = evaluator.evaluate(submission, task, runtimes={RUNTIME_KEY: empty})
    assert result["complete"] is False and result["passed"] is False
    assert "runtime prepare" in result["runtime_log"]

    evaluator.container.status = lambda: {"available": False, "reason": "no daemon"}  # type: ignore[method-assign]
    ready = empty.model_copy(update={"metadata": {"images": {task.id: IMAGE}}})
    result = evaluator.evaluate(submission, task, runtimes={RUNTIME_KEY: ready})
    assert result["complete"] is False and result["passed"] is False
    assert "no daemon" in result["runtime_log"]


def test_core_profile_never_uses_the_container(tmp_path: Path) -> None:
    task = DstCatalog.load(PACK).tasks[0]
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=PACK, cache_dir=tmp_path / "cache"))

    def forbidden(
        mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        raise AssertionError("the container must not start")

    evaluator.container.run = forbidden  # type: ignore[method-assign]
    artifact = RuntimeArtifact(runtime_key=RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                               identity="fixture", metadata={"images": {task.id: IMAGE}})
    result = evaluator.evaluate(_submission(tmp_path), task, profile="core", runtimes={RUNTIME_KEY: artifact})
    assert result["complete"] is False and result["passed"] is False


def test_container_is_networkless_capability_free_and_read_only_for_the_submission(
    tmp_path: Path,
) -> None:
    from rhenium_dst.container import DstContainerRuntime

    runtime = DstContainerRuntime()
    runtime.docker = "docker"
    calls: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "b" * 64 if arguments[0] == "create" else "", "")

    runtime._docker = docker  # type: ignore[method-assign]
    runtime.run(tmp_path, tmp_path / "logs", IMAGE)
    create = calls[0]
    assert {"--network=none", "--cap-drop=ALL", "--pull=never",
            "--security-opt=no-new-privileges:true"} <= set(create)
    assert f"type=bind,source={tmp_path.resolve()},target=/app/mod,readonly" in create
    assert calls[-1][:2] == ["rm", "--force"]
    with pytest.raises(RuntimeError, match="immutable"):
        runtime.run(tmp_path, tmp_path / "logs", "rhenium-dst:latest")


def test_docker_calls_allow_a_congested_daemon_five_minutes(tmp_path: Path) -> None:
    from rhenium_dst.container import _DOCKER_TIMEOUT, DstContainerRuntime

    runtime = DstContainerRuntime()
    runtime.docker = "docker"
    timeouts: dict[str, float] = {}

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        timeouts[" ".join(arguments[:2])] = timeout
        replies = {"create": "b" * 64, "image": "sha256:" + "c" * 64, "info": "29.0.0"}
        stdout = replies.get(arguments[0], "")
        if arguments[:2] == ["image", "inspect"] and "{{json .Config.Labels}}" in arguments:
            stdout = "{}"
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    runtime._docker = docker  # type: ignore[method-assign]
    assert runtime.status()["available"] is True
    runtime.image_id("rhenium-dst:task")
    runtime.image_labels("rhenium-dst:task")
    runtime.run(tmp_path, tmp_path / "logs", IMAGE)
    assert _DOCKER_TIMEOUT == 300
    copy_out = "cp " + "b" * 64 + ":/logs/."
    for call in ("info --format", "image inspect", "create --pull=never", copy_out, "rm --force"):
        assert timeouts[call] == _DOCKER_TIMEOUT, call
