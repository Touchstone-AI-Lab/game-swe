import base64
import json
import subprocess
from pathlib import Path

import pytest
from rhenium_terraria.catalog import (
    TerrariaCatalog,
    TerrariaTask,
    expected_case_names,
    expected_engine_case_names,
)
from rhenium_terraria.evaluator import (
    ENGINE_RUNTIME_KEY,
    RUNTIME_KEY,
    TerrariaEvaluator,
)

from rhenium.core.evaluation import normalize_evaluation
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

PACK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "terraria-core"


def _evaluator(tmp_path: Path) -> tuple[TerrariaEvaluator, TerrariaTask]:
    catalog = TerrariaCatalog.load(PACK_ROOT)
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return TerrariaEvaluator(context, catalog), catalog.tasks[0]


def _submission(root: Path, task: TerrariaTask) -> Path:
    root.mkdir()
    for relative in task.required_files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")
    return root


def test_static_check_accepts_source_and_rejects_build_output(tmp_path: Path) -> None:
    evaluator, task = _evaluator(tmp_path)
    submission = _submission(tmp_path / "submission", task)
    ok, check = evaluator._static_check(submission, task)
    assert ok and check["status"] == "passed"

    output = submission / task.starter_name / "obj"
    output.mkdir()
    (output / "project.assets.json").write_text("{}", encoding="utf-8")
    ok, check = evaluator._static_check(submission, task)
    assert not ok and check["status"] == "failed"


@pytest.mark.parametrize("outcome", ("passed", "failed", "incomplete"))
def test_full_report_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    evaluator, task = _evaluator(tmp_path)
    submission = _submission(tmp_path / "submission", task)
    names = expected_case_names(PACK_ROOT, task)
    engine_names = expected_engine_case_names(PACK_ROOT, task)
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
        # The real test.sh tees this exact stream to both stdout and the log.
        # The evaluator must prefer the log instead of counting every case twice.
        (verifier / "verifier.log").write_text(output, encoding="utf-8")
        return subprocess.CompletedProcess([], 0, output, ""), "network=none\n"

    monkeypatch.setattr(evaluator.runtime, "run", fake_run)

    def fake_engine_run(
        _image_id: str,
        reports: Path,
        submission: Path | None = None,
        *,
        timeout: float = 1800,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        del submission, timeout
        reports.mkdir(parents=True)
        observed_engine = engine_names[:-1] if outcome == "incomplete" else engine_names
        engine_passed = outcome == "passed"
        cases = [
            {
                "name": name,
                "status": "passed" if engine_passed or index > 0 else "failed",
                "error": None if engine_passed or index > 0 else "expected failure",
            }
            for index, name in enumerate(observed_engine)
        ]
        (reports / "engine-report.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "complete": True,
                    "passed": engine_passed,
                    "terrariaVersion": "v1.4.4.9",
                    "tModLoaderVersion": "2026.7.3.0",
                    "dedicatedServer": True,
                    "cases": cases,
                }
            ),
            encoding="utf-8",
        )
        return (
            subprocess.CompletedProcess([], 0 if engine_passed else 90, "", ""),
            "network=none\n",
        )

    monkeypatch.setattr(evaluator.engine_runtime, "run_image", fake_engine_run)
    image_id = "sha256:" + "a" * 64
    source_artifact = RuntimeArtifact(
        runtime_key=RUNTIME_KEY,
        fingerprint="test",
        kind="docker-images",
        identity=image_id,
        metadata={"images": {task.id: image_id}},
    )
    engine_artifact = RuntimeArtifact(
        runtime_key=ENGINE_RUNTIME_KEY,
        fingerprint="test",
        kind="docker-images",
        identity="sha256:" + "b" * 64,
        metadata={"images": {task.id: "sha256:" + "b" * 64}},
    )
    report = normalize_evaluation(
        evaluator.evaluate(
            submission,
            task,
            runtimes={RUNTIME_KEY: source_artifact, ENGINE_RUNTIME_KEY: engine_artifact},
        )
    )
    assert report["complete"] is (outcome != "incomplete")
    assert report["passed"] is (outcome == "passed")
    assert report["score"] == (100.0 if outcome == "passed" else 10.0)
    projection, engine = report["checks"][1], report["checks"][2]
    if outcome == "incomplete":
        # A partial case set is never reported case by case.
        assert "details" not in projection and "details" not in engine
    else:
        cases = projection["details"]["cases"]
        assert [case["name"] for case in cases] == list(names)
        assert cases[0]["passed"] is (outcome == "passed") and all(case["passed"] for case in cases[1:])
        engine_cases = engine["details"]["cases"]
        assert [case["name"] for case in engine_cases] == list(engine_names)
        assert engine_cases[0]["passed"] is (outcome == "passed")


def test_full_report_fails_closed_without_engine_runtime(tmp_path: Path) -> None:
    evaluator, task = _evaluator(tmp_path)
    submission = _submission(tmp_path / "submission", task)
    report = normalize_evaluation(evaluator.evaluate(submission, task, runtimes={}))
    assert report["complete"] is False
    assert report["passed"] is False
    assert report["checks"][2]["status"] == "incomplete"


def test_verifier_overlays_attempt_without_private_harbor_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator, task = _evaluator(tmp_path)
    submission = tmp_path / "submission"
    submission.mkdir()
    commands: list[list[str]] = []

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(args)
        return subprocess.CompletedProcess(
            args, 0, "f" * 64 if args[0] == "create" else "", ""
        )

    monkeypatch.setattr(evaluator.runtime, "_docker", fake_docker)
    evaluator.runtime.run(task, submission, tmp_path / "logs", "sha256:" + "a" * 64)
    created = commands[0]
    assert "cp -R /solution/. /workspace/" in created[-1]
    assert "--network=none" in created
    assert not any("target=/harbor" in argument for argument in created)
    assert any("target=/tests,readonly" in argument for argument in created)


def test_docker_control_operations_wait_for_a_congested_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator, task = _evaluator(tmp_path)
    submission = tmp_path / "submission"
    submission.mkdir()
    timeouts: dict[str, float] = {}

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        timeouts[args[0]] = timeout
        return subprocess.CompletedProcess(
            args, 0, "f" * 64 if args[0] == "create" else "", ""
        )

    monkeypatch.setattr(evaluator.runtime, "_docker", fake_docker)
    evaluator.runtime.run(task, submission, tmp_path / "logs", "sha256:" + "a" * 64)
    assert timeouts["create"] >= 300 and timeouts["cp"] >= 300 and timeouts["rm"] >= 300


def test_engine_runtime_is_read_only_and_uses_bounded_report_tmpfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator, _task = _evaluator(tmp_path)
    submission = tmp_path / "submission"
    submission.mkdir()
    commands: list[list[str]] = []

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(args)
        return subprocess.CompletedProcess(
            args, 0, "f" * 64 if args[0] == "create" else "", ""
        )

    monkeypatch.setattr(evaluator.engine_runtime, "_docker", fake_docker)
    evaluator.engine_runtime.run_image(
        "sha256:" + "a" * 64,
        tmp_path / "reports",
        submission=submission,
    )
    created = commands[0]
    assert "--read-only" in created
    assert "--network=none" in created
    assert any(
        argument.startswith("/reports:rw,noexec,nosuid,size=16m,") for argument in created
    )
    assert any(
        argument.startswith("/opt/tmodloader/tModLoader-Logs:rw,noexec,nosuid,size=64m,")
        for argument in created
    )
    assert any("target=/solution,readonly" in argument for argument in created)
    assert not any(command[:1] == ["cp"] for command in commands)


def test_engine_runtime_collects_one_bounded_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator, _task = _evaluator(tmp_path)
    payload = b'{"schemaVersion":1}'
    marker = "GCB_TERRARIA_REPORT_V1=" + base64.b64encode(payload).decode()

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        if args[0] == "create":
            return subprocess.CompletedProcess(args, 0, "f" * 64, "")
        if args[:2] == ["start", "--attach"]:
            return subprocess.CompletedProcess(args, 0, f"engine log\n{marker}\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(evaluator.engine_runtime, "_docker", fake_docker)
    reports = tmp_path / "reports"
    evaluator.engine_runtime.run_image("sha256:" + "a" * 64, reports)
    assert (reports / "engine-report.json").read_bytes() == payload


def test_engine_runtime_rejects_multiple_or_oversized_reports(tmp_path: Path) -> None:
    evaluator, _task = _evaluator(tmp_path)
    marker = "GCB_TERRARIA_REPORT_V1=e30="
    with pytest.raises(RuntimeError, match="multiple reports"):
        evaluator.engine_runtime._collect_report(f"{marker}\n{marker}\n", tmp_path)

    oversized = base64.b64encode(b"x" * 262_145).decode()
    with pytest.raises(RuntimeError, match="size limit"):
        evaluator.engine_runtime._collect_report(
            "GCB_TERRARIA_REPORT_V1=" + oversized, tmp_path
        )
