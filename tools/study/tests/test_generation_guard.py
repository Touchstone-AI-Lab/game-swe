from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_study import attempts
from rhenium_study.inventory import TASKS


def test_container_names_are_dns_labels_for_every_scheduled_attempt() -> None:
    names = set()
    for task in TASKS:
        for model in ("gpt-6-astra", "a-much-longer-model-condition-identifier"):
            attempt_id = f"{model}--{task.task}--r3"
            for name in attempts.container_names(attempt_id, "0a1b2c3d"):
                assert len(name) <= 63
                assert name == name.lower()
                names.add(name)
    assert len(names) == 3 * 2 * len(TASKS)


def _egress(directory: Path, *events: str) -> None:
    lines = [json.dumps({"t": 1.0, "event": event, "target": "host:443"}) for event in events]
    (directory / "egress.jsonl").write_text("\n".join([*lines, "not json"]) + "\n", encoding="utf-8")


def test_a_start_that_never_reached_the_model_is_not_a_generation(tmp_path: Path) -> None:
    ok = {"setupFailed": False}
    error = {"error": "InternalServerError"}
    assert attempts.never_started({"setupFailed": True}, {}, tmp_path)
    assert attempts.never_started(ok, error, tmp_path)  # no egress log at all
    _egress(tmp_path, "denied")
    assert attempts.never_started(ok, error, tmp_path)
    assert not attempts.never_started(ok, {}, tmp_path)  # the agent finished without an error
    _egress(tmp_path, "denied", "allowed")
    assert attempts.endpoint_reached(tmp_path)
    # Reached, but every request was refused (a rate limit or an unavailable model).
    progress = [json.dumps({"t": 3, "progress": 10, "phase": "mini-swe-agent step 1"}), "RateLimitError"]
    (tmp_path / "agent.log").write_text("\n".join(progress) + "\n", encoding="utf-8")
    assert not attempts.model_answered(tmp_path)
    assert attempts.never_started(ok, error, tmp_path)
    progress.append(json.dumps({"t": 9, "progress": 11, "phase": "mini-swe-agent step 2"}))
    (tmp_path / "agent.log").write_text("\n".join(progress) + "\n", encoding="utf-8")
    assert attempts.model_answered(tmp_path)
    assert not attempts.never_started(ok, error, tmp_path)  # a provider error after sampling began


def test_attempt_subnets_are_small_private_and_vary_with_the_salt() -> None:
    import ipaddress

    first = ipaddress.IPv4Network(attempts._subnet("m--t--r1", 0))
    assert first.prefixlen == 28
    assert first.subnet_of(ipaddress.IPv4Network("10.96.0.0/12"))
    assert len({attempts._subnet("m--t--r1", salt) for salt in range(8)}) > 1


def test_context_exhaustion_is_a_termination_not_an_infrastructure_error() -> None:
    assert attempts.context_exhausted({"error": "ContextWindowExceededError", "message": "too long"})
    assert attempts.context_exhausted({"error": "BadRequestError", "message": "请求内容超过模型上下文窗口"})
    assert attempts.context_exhausted({"error": "BadRequestError", "message": "maximum context length is 1"})
    assert not attempts.context_exhausted({"error": "InternalServerError", "message": "Connection error."})
    assert not attempts.context_exhausted({"exitStatus": "Submitted", "message": "context window"})


def test_a_restart_first_removes_what_an_earlier_start_left_behind(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    calls: list[list[str]] = []
    listed = {"ps": "c1\nc2\n", "network": "n1\n"}

    def fake_docker(
        arguments: list[str], *, timeout: float, env: object = None
    ) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if "--filter" in arguments:
            return subprocess.CompletedProcess(arguments, 0, listed[arguments[0]], "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(attempts, "_docker", fake_docker)
    assert attempts.remove_leftovers("m--t--r1") == []
    label = "label=io.rhenium.study.attempt=m--t--r1"
    assert calls == [
        ["ps", "--all", "--quiet", "--filter", label],
        ["rm", "--force", "c1", "c2"],
        ["network", "ls", "--quiet", "--filter", label],
        ["network", "rm", "n1"],
    ]
    # Each start takes fresh names, so a proxy still being removed cannot block the next one.
    assert attempts.container_names("m--t--r1", "aa") != attempts.container_names("m--t--r1", "bb")


def test_a_setup_failure_keeps_dockers_error_rather_than_its_usage_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    stderr = (
        "docker: Error response from daemon: Conflict. The name is in use.\n"
        "\nRun 'docker run --help' for more information\n"
    )

    def fake_docker(
        arguments: list[str], *, timeout: float, env: object = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, 125, "", stderr)

    monkeypatch.setattr(attempts, "_docker", fake_docker)
    with pytest.raises(attempts._GenerationSetupError, match="Conflict. The name is in use"):
        attempts._setup(["run", "x"], "the egress proxy could not be started")


def test_only_games_with_a_public_check_get_its_module_path() -> None:
    assert attempts.public_check_python_path("palworld").split(":")[0] == "/opt/rhenium/plugins/palworld"
    assert attempts.public_check_python_path("dst").split(":")[0] == "/opt/rhenium/plugins/dst"
    assert attempts.public_check_python_path("minecraft") == ""


def test_a_provider_interruption_after_sampling_is_restarted_not_scored(tmp_path: Path) -> None:
    steps = [
        json.dumps({"t": t, "progress": 10, "phase": f"mini-swe-agent step {n}"}) for t, n in ((1, 1), (9, 2))
    ]
    (tmp_path / "agent.log").write_text("\n".join(steps) + "\n", encoding="utf-8")
    assert attempts.provider_interrupted({"error": "RateLimitError"}, tmp_path)
    assert attempts.provider_interrupted({"error": "ServiceUnavailableError"}, tmp_path)
    # An error the model's own requests can cause is not a provider interruption.
    assert not attempts.provider_interrupted({"error": "BadRequestError"}, tmp_path)
    assert not attempts.provider_interrupted({"error": "ContextWindowExceededError"}, tmp_path)
    assert not attempts.provider_interrupted({}, tmp_path)
    # Before any answer it is a start that never reached the model, handled by never_started.
    (tmp_path / "agent.log").write_text(steps[0] + "\n", encoding="utf-8")
    assert not attempts.provider_interrupted({"error": "RateLimitError"}, tmp_path)


def test_the_model_condition_reaches_the_runner_and_the_key_only_its_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from rhenium_study.e1config import StudyConfig
    from rhenium_study.paths import StudyPaths

    key = tmp_path / "anthropic-key.txt"
    key.write_text("sk-test-secret\n", encoding="utf-8")
    config = StudyConfig.model_validate(
        {
            "study_id": "condition-test",
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
                {
                    "id": "claude-opus-5",
                    "litellm_model": "anthropic/claude-opus-5",
                    "base_url": "https://api.anthropic.com",
                    "api_key_file": str(key),
                    "thinking": {"type": "adaptive", "display": "summarized"},
                    "output_config": {"effort": "high"},
                    "omit_params": ["temperature"],
                    "max_output_tokens": 64000,
                    "stream_responses": True,
                }
            ],
            "tasks": ["slay-the-spire/core/mts-load-order-regressions"],
            "e2_selection_rule": "none",
            "e2_max_cases": 1,
        }
    )
    runs: list[tuple[list[str], dict[str, str]]] = []

    def fake_docker(
        arguments: list[str], *, timeout: float, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        if arguments[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(arguments, 0, "sha256:agent\n", "")
        if env is not None:
            runs.append((arguments, env))
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(attempts, "_docker", fake_docker)
    out = tmp_path / "agent"
    out.mkdir()
    paths = StudyPaths(project_root=Path(__file__).parents[3], data_root=tmp_path / "data")
    generation = attempts._generate(paths, config, config.models[0], tmp_path, out, "claude-opus-5--t--r1")
    assert generation["containerExit"] == 0 and not generation["setupFailed"]
    [(arguments, env)] = runs
    condition = json.loads(env["RHENIUM_STUDY_CONDITION"])
    assert condition["output_config"] == {"effort": "high"}
    assert condition["omit_params"] == ["temperature"]
    assert condition["stream_responses"] is True
    assert condition["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert condition["base_url"] == "https://api.anthropic.com"
    assert env["RHENIUM_MODEL_API_KEY"] == "sk-test-secret"
    assert "sk-test-secret" not in env["RHENIUM_STUDY_CONDITION"]
    assert not any("sk-test-secret" in argument for argument in arguments)
