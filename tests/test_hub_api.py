from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rhenium.api import create_app
from rhenium.config import Settings
from rhenium.hub import BenchmarkHub, JobManager
from rhenium.models import Job, Run
from rhenium.util import json_dumps
from tests.conftest import FixturePlugin, write_fixture_pack

TASK_KEY = "fixture/core/shared-task"


def _passing_submission(tmp_path: Path) -> Path:
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")
    return submission


def test_hub_materializes_public_assets_only_under_state(hub: BenchmarkHub, settings: Settings) -> None:
    tasks = hub.list_tasks("en")
    loaded = next(iter(hub.benchmarks.values()))

    assert [task["key"] for task in tasks] == [TASK_KEY]
    assert tasks[0]["profiles"] == [
        {"id": "core", "label": "Core checks", "complete_eligible": False},
        {"id": "full", "label": "Full evaluation", "complete_eligible": True},
    ]
    assert loaded.context.state_dir == settings.state_dir / "packs/fixture/core"
    assert (loaded.context.state_dir / "workspaces/shared-task/TASK.md").is_file()
    assert (loaded.context.state_dir / "public/tasks.json").is_file()


def test_api_exposes_explicit_games_packs_tasks_reports_and_health(
    hub: BenchmarkHub, settings: Settings
) -> None:
    with TestClient(create_app(settings, hub=hub)) as client:
        health = client.get("/api/health")
        games = client.get("/api/games")
        packs = client.get("/api/games/fixture/packs")
        tasks = client.get("/api/tasks", params={"game": "fixture", "pack": "core"})
        reports = client.get("/api/reports", params={"game": "fixture", "pack": "core"})

    assert health.status_code == 200
    assert health.json()["pluginCount"] == 1
    assert health.json()["packCount"] == 1
    assert "game" not in health.json() and "runtime" not in health.json()
    assert games.json()["games"][0]["game_id"] == "fixture"
    assert packs.json()["packs"][0]["key"] == "fixture/core"
    assert tasks.json()["tasks"][0]["key"] == TASK_KEY
    assert reports.json()["tasks"] == 1


def test_hierarchical_run_route_validates_key_and_profile(hub: BenchmarkHub, settings: Settings) -> None:
    app = create_app(settings, hub=hub)
    with (
        patch.object(app.state.jobs, "start", return_value={"id": "job-test"}) as start,
        TestClient(app) as client,
    ):
        accepted = client.post(
            "/api/games/fixture/packs/core/tasks/shared-task/runs",
            params={"profile": "core"},
        )
        unknown = client.post("/api/games/fixture/packs/core/tasks/missing/runs")
        invalid_profile = client.post(
            "/api/games/fixture/packs/core/tasks/shared-task/runs",
            params={"profile": "turbo"},
        )

    assert accepted.status_code == 200
    start.assert_called_once_with("model_evaluate", {"taskKey": TASK_KEY, "profile": "core"})
    assert unknown.status_code == 404
    assert invalid_profile.status_code == 400


def test_hierarchical_run_route_forwards_explicit_untrusted_host_policy(
    hub: BenchmarkHub, settings: Settings
) -> None:
    app = create_app(settings, hub=hub)
    with (
        patch.object(app.state.jobs, "start", return_value={"id": "job-test"}) as start,
        TestClient(app) as client,
    ):
        response = client.post(
            "/api/games/fixture/packs/core/tasks/shared-task/runs",
            params={
                "profile": "full",
                "security_mode": "untrusted",
                "host_provider": "fake-disposable",
                "host_image": "sha256:trusted-image",
            },
        )

    assert response.status_code == 200
    start.assert_called_once_with(
        "model_evaluate",
        {
            "taskKey": TASK_KEY,
            "profile": "full",
            "securityMode": "untrusted",
            "hostProvider": "fake-disposable",
            "hostImage": "sha256:trusted-image",
        },
    )


def test_evaluation_host_routes_expose_only_provider_capability(
    hub: BenchmarkHub, settings: Settings
) -> None:
    from tests.evaluation_host_helpers import FakeDisposableHost

    provider = FakeDisposableHost()
    hub.evaluation_hosts[provider.id] = provider
    app = create_app(settings, hub=hub)
    with TestClient(app) as client:
        listed = client.get("/api/evaluation-hosts")
        doctor = client.get(f"/api/evaluation-hosts/{provider.id}/doctor")
        missing = client.get("/api/evaluation-hosts/missing/doctor")

    assert listed.status_code == 200
    assert listed.json()["providers"][0]["id"] == provider.id
    assert doctor.status_code == 200
    assert doctor.json()["capability"]["disposable"] is True
    assert missing.status_code == 404


def test_full_and_core_profiles_have_explicit_completion_semantics(
    hub: BenchmarkHub, fixture_plugin: FixturePlugin, tmp_path: Path
) -> None:
    submission = _passing_submission(tmp_path)

    core = hub.evaluate_task(TASK_KEY, submission, profile="core")
    full = hub.evaluate_task(TASK_KEY, submission, profile="full")

    assert core["status"] == "failed"
    assert core["result"]["complete"] is False
    assert full["status"] == "passed"
    assert full["result"]["profile"] == "full"
    assert fixture_plugin.calls == [("shared-task", "core"), ("shared-task", "full")]
    with pytest.raises(ValueError, match="unknown evaluation profile"):
        hub.evaluate_task(TASK_KEY, submission, profile="turbo")


def test_anonymous_attempt_never_returns_task_or_pack_identity(hub: BenchmarkHub, tmp_path: Path) -> None:
    attempt = tmp_path.parent / f"anonymous-{tmp_path.name}"
    attempt.mkdir()
    (attempt / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")

    registration = hub.register_attempt(TASK_KEY, attempt, "strict")
    loaded = next(iter(hub.benchmarks.values()))
    evaluator_result = {
        "score": 100.0,
        "complete": True,
        "passed": True,
        "checks": [],
        "runtime_log": "private runtime output",
        "diagnostic": {
            "taskKey": TASK_KEY,
            "privatePath": f"{loaded.context.pack_root}/private/assertion.txt",
            "payload": {"public": "preserved-by-default-plugin"},
        },
        "runtime": {
            "phase_a": {
                "passed": True,
                "payload": {"public": "plugin-defined-result"},
            }
        },
    }
    with patch.object(loaded.evaluator, "evaluate", return_value=evaluator_result):
        result = hub.evaluate_attempt(attempt, profile="full")

    serialized = json_dumps({"registration": registration, "result": result})
    assert result["status"] == "passed"
    assert "taskKey" not in result
    assert TASK_KEY not in serialized
    assert "fixture/core" not in serialized
    assert str(loaded.context.pack_root) not in serialized
    assert "taskKey" not in serialized
    assert "[redacted]" in serialized
    assert result["result"]["diagnostic"]["payload"] == {"public": "preserved-by-default-plugin"}
    assert result["result"]["runtime"]["phase_a"]["payload"] == {"public": "plugin-defined-result"}


def test_unregistered_attempt_is_rejected(hub: BenchmarkHub, tmp_path: Path) -> None:
    attempt = tmp_path / "unknown"
    attempt.mkdir()

    with pytest.raises(ValueError, match="registered anonymous attempt"):
        hub.evaluate_attempt(attempt)


def test_prepare_attempt_rejects_repository_and_keeps_identity_private(
    hub: BenchmarkHub, tmp_path: Path
) -> None:
    attempt = tmp_path.parent / f"prepared-{tmp_path.name}"
    scorer = tmp_path / "score"
    scorer.write_text("#!/bin/sh\n", encoding="utf-8")

    result = hub.prepare_attempt(TASK_KEY, attempt, "strict", scorer)
    bundle = "\n".join(path.read_text(encoding="utf-8") for path in attempt.iterdir() if path.is_file())

    assert TASK_KEY not in json_dumps(result)
    assert "shared-task" not in bundle
    assert str(next(iter(hub.benchmarks.values())).context.pack_root) not in bundle
    with pytest.raises(ValueError, match="benchmark code"):
        hub.register_attempt(TASK_KEY, tmp_path, "strict")


def test_prepare_attempt_renders_native_windows_scoring_command(hub: BenchmarkHub, tmp_path: Path) -> None:
    attempt = tmp_path.parent / f"powershell-attempt-{tmp_path.name}"
    scorer = tmp_path / "score-exam.ps1"
    scorer.write_text("param([string]$SubmissionDirectory)\n", encoding="utf-8")

    hub.prepare_attempt(TASK_KEY, attempt, "practice", scorer)

    prompt = (attempt / "PROMPT.md").read_text(encoding="utf-8")
    assert "```powershell" in prompt
    assert f'& "{scorer.resolve()}" (Get-Location).Path' in prompt


def test_duplicate_model_job_reuses_only_matching_task_and_profile(hub: BenchmarkHub) -> None:
    manager = JobManager(hub)
    with hub.database.session_factory() as session:
        session.add(
            Job(
                id="job-existing",
                task_key=TASK_KEY,
                kind="model_evaluate",
                status="running",
                payload_json=json_dumps({"taskKey": TASK_KEY, "profile": "full"}),
            )
        )
        session.commit()

    assert manager.start("model_evaluate", {"taskKey": TASK_KEY, "profile": "full"})["id"] == "job-existing"


def test_model_build_uses_public_contract_and_canonical_result_key(hub: BenchmarkHub, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    class Builder:
        def build(self, workspace: Path, requirement: str, **options: object) -> dict[str, Any]:
            captured["requirement"] = requirement
            captured["system_prompt"] = str(options["system_prompt"])
            (workspace / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")
            return {
                "framework": {
                    "name": "mini-swe-agent",
                    "version": "test",
                    "trajectoryFormat": "mini-swe-agent-1.1",
                },
                "steps": 1,
                "exitStatus": "Submitted",
                "changedFiles": ["answer.txt"],
                "trajectory": {"trajectory_format": "mini-swe-agent-1.1", "messages": []},
            }

    hub.model_runner = Builder()  # type: ignore[assignment]
    hub.update_settings(
        {"modelEnabled": True, "modelBaseUrl": "http://model.test/v1", "modelName": "builder"}
    )

    result = hub.evaluate_model(TASK_KEY)

    assert result["taskKey"] == TASK_KEY
    assert result["evaluation"]["status"] == "passed"
    assert "shared-task" not in captured["requirement"]
    assert "Required files" in captured["requirement"]
    assert "game-engineering implementation benchmark" in captured["system_prompt"]


def test_web_route_does_not_follow_files_outside_dist(
    hub: BenchmarkHub, settings: Settings, tmp_path: Path
) -> None:
    web_dist = tmp_path / "dist"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("app shell", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    (web_dist / "escape").symlink_to(secret)

    with TestClient(create_app(replace(settings, web_dist=web_dist), hub=hub)) as client:
        response = client.get("/escape")

    assert response.status_code == 200
    assert response.text == "app shell"


def test_management_api_can_be_disabled_for_non_loopback_embedding(
    hub: BenchmarkHub, settings: Settings
) -> None:
    with TestClient(create_app(settings, hub=hub, management_enabled=False)) as client:
        response = client.post("/api/auth/providers/fixture/login", json={"account": "default"})

    assert response.status_code == 403


class _AnsweringAgent:
    """Stand in for a coding-agent CLI that writes the expected answer."""

    def __init__(self, answer: str = "fixture-ok\n") -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def run(
        self, provider: str, workspace: Path, prompt: str, log_path: Path, **options: object
    ) -> dict[str, Any]:
        del options
        self.prompts.append(prompt)
        (workspace / "answer.txt").write_text(self.answer, encoding="utf-8")
        log_path.write_text('{"type": "done"}\n', encoding="utf-8")
        return {
            "framework": {"name": provider, "version": "test", "trajectoryFormat": "test-jsonl"},
            "steps": 1,
            "exitStatus": "exit 0",
            "changedFiles": ["answer.txt"],
        }


def test_platform_scored_attempt_prompt_has_no_scorer(hub: BenchmarkHub, tmp_path: Path) -> None:
    attempt = tmp_path.parent / f"platform-{tmp_path.name}"

    hub.prepare_attempt(TASK_KEY, attempt, "strict", None)

    prompt = (attempt / "PROMPT.md").read_text(encoding="utf-8")
    assert "exactly once after you submit" in prompt
    assert "scoring command" not in prompt and "score-exam\"" not in prompt
    with pytest.raises(ValueError, match="strict mode"):
        hub.prepare_attempt(TASK_KEY, tmp_path.parent / f"practice-{tmp_path.name}", "practice", None)


def test_task_selection_accepts_a_game_pack_or_task_without_crossing_games(tmp_path: Path) -> None:
    settings = Settings(
        root=tmp_path,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "state" / "cache",
        database_url=f"sqlite:///{tmp_path / 'state' / 'state.sqlite'}",
        benchmark_paths=(tmp_path / "benchmarks",),
        web_dist=None,
    )
    manifests = (
        write_fixture_pack(settings.benchmark_paths[0], plugin_id="first", game_id="game-a"),
        write_fixture_pack(settings.benchmark_paths[0], plugin_id="second", game_id="game-b"),
        write_fixture_pack(
            settings.benchmark_paths[0], plugin_id="second", game_id="game-b", pack_id="extra"
        ),
    )
    hub = BenchmarkHub(
        settings,
        plugins={"first": FixturePlugin("first", "game-a"), "second": FixturePlugin("second", "game-b")},
        manifest_paths=manifests,
    )

    assert hub.select_task_keys("game-a") == ["game-a/core/shared-task"]
    assert hub.select_task_keys("game-b") == ["game-b/core/shared-task", "game-b/extra/shared-task"]
    assert hub.select_task_keys("game-b/extra") == ["game-b/extra/shared-task"]
    assert hub.select_task_keys("game-a/core/shared-task") == ["game-a/core/shared-task"]
    for selector in ("game-c", "game-a/extra", "game-a//shared-task", "a/b/c/d", ""):
        with pytest.raises(ValueError):
            hub.select_task_keys(selector)


def test_cli_agent_attempt_is_scored_once_by_the_platform_without_identity(
    hub: BenchmarkHub, tmp_path: Path
) -> None:
    attempt = tmp_path.parent / f"codex-{tmp_path.name}"
    hub.prepare_attempt(TASK_KEY, attempt, "strict", None)
    agent = _AnsweringAgent()
    hub.cli_agent_runner = agent  # type: ignore[assignment]

    result = hub.run_agent_attempt(attempt, "codex")

    assert result["evaluation"]["status"] == "passed"
    assert result["exitStatus"] == "exit 0"
    assert result["framework"]["name"] == "codex"
    assert agent.prompts[0].count("exactly once after you submit") == 1
    assert "shared-task" not in agent.prompts[0]
    serialized = json_dumps(result)
    assert TASK_KEY not in serialized and "taskKey" not in serialized
    assert "trajectoryPath" not in serialized
    with hub.database.session_factory() as session:
        runs = session.query(Run).all()
    assert len(runs) == 1 and runs[0].task_key == TASK_KEY
    with pytest.raises(ValueError, match="provider"):
        hub.run_agent_attempt(attempt, "gemini")
