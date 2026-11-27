from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch
from typer.testing import CliRunner, Result

from rhenium import cli
from rhenium.hub import BenchmarkHub

RUNNER = CliRunner()


class _Auth:
    """Stand in for the Hub auth service and replay two challenges from a provider."""

    @staticmethod
    def login(provider_id: str, account_alias: str, **kwargs: Any) -> dict[str, Any]:
        challenge = kwargs["challenge"]
        for uri in ("https://s.team/q/1/first", "https://s.team/q/1/second"):
            challenge(type("Challenge", (), {"uri": uri, "message": "Scan with the app"})())
        return {"providerId": provider_id, "accountAlias": account_alias, "status": "ready"}


class _Hub:
    auth = _Auth()


def test_auth_login_marks_a_replaced_qr_code_as_expired(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_hub", _Hub)

    result = RUNNER.invoke(cli.app, ["auth", "login", "steam"], catch_exceptions=False)

    assert result.exit_code == 0
    # Only the second code is live, and the first one is still on screen above it.
    assert result.stderr.count("Scan with the app") == 2
    assert result.stderr.count("every code further up has expired") == 1
    assert '"status": "ready"' in result.stdout


class _FailingAuth:
    @staticmethod
    def login(provider_id: str, account_alias: str, **kwargs: Any) -> dict[str, Any]:
        del provider_id, account_alias, kwargs
        raise RuntimeError("Steam QR login failed: session expired")


class _FailingHub:
    auth = _FailingAuth()


def test_auth_login_reports_a_failed_sign_in_without_a_traceback(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_hub", _FailingHub)

    result = RUNNER.invoke(cli.app, ["auth", "login", "steam"], catch_exceptions=False)

    assert result.exit_code == 2
    assert "Traceback" not in result.stdout + result.stderr
    assert '"status": "failed"' in result.stdout
    assert "session expired" in result.stdout
    assert "Run 'rhenium auth login steam' again" in result.stderr


class _WritingAgent:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def run(
        self, provider: str, workspace: Path, prompt: str, log_path: Path, **options: object
    ) -> dict[str, Any]:
        del prompt, options
        (workspace / "answer.txt").write_text(self.answer, encoding="utf-8")
        log_path.write_text("{}\n", encoding="utf-8")
        return {
            "framework": {"name": provider, "version": "test", "trajectoryFormat": "test-jsonl"},
            "steps": 1,
            "exitStatus": "exit 0",
            "changedFiles": ["answer.txt"],
        }


def _benchmark(
    monkeypatch: MonkeyPatch, hub: BenchmarkHub, tmp_path: Path, *arguments: str
) -> Result:
    monkeypatch.setattr(cli, "_hub", lambda: hub)
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv("RHENIUM_ROOT", str(hub.settings.root))
    attempts = tmp_path.parent / f"attempts-{tmp_path.name}"
    return RUNNER.invoke(
        cli.app, ["benchmark", *arguments, "--attempts-dir", str(attempts)], catch_exceptions=False
    )


def test_benchmark_runs_every_task_of_a_game_with_a_cli_agent(
    monkeypatch: MonkeyPatch, hub: BenchmarkHub, tmp_path: Path
) -> None:
    hub.cli_agent_runner = _WritingAgent("fixture-ok\n")  # type: ignore[assignment]

    result = _benchmark(monkeypatch, hub, tmp_path, "fixture", "--provider", "claude")

    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert (summary["provider"], summary["passed"], summary["total"]) == ("claude", 1, 1)
    task = summary["tasks"][0]
    assert task["taskKey"] == "fixture/core/shared-task" and task["status"] == "passed"
    assert Path(task["attempt"]).parent == (tmp_path.parent / f"attempts-{tmp_path.name}")
    assert "shared-task" not in Path(task["attempt"]).name
    assert "== [1/1] fixture/core/shared-task (claude)" in result.stderr


def test_benchmark_exits_nonzero_when_a_task_fails(
    monkeypatch: MonkeyPatch, hub: BenchmarkHub, tmp_path: Path
) -> None:
    hub.cli_agent_runner = _WritingAgent("wrong\n")  # type: ignore[assignment]

    result = _benchmark(monkeypatch, hub, tmp_path, "fixture/core", "--provider", "codex")

    assert result.exit_code == 1
    assert json.loads(result.stdout)["tasks"][0]["status"] == "failed"


def test_benchmark_rejects_an_unknown_provider_or_selector(
    monkeypatch: MonkeyPatch, hub: BenchmarkHub, tmp_path: Path
) -> None:
    unknown_provider = _benchmark(monkeypatch, hub, tmp_path, "fixture", "--provider", "gemini")
    assert unknown_provider.exit_code == 2
    assert "api, codex, or claude" in unknown_provider.output

    unknown_game = _benchmark(monkeypatch, hub, tmp_path, "missing")
    assert unknown_game.exit_code == 2
    assert "no task matches missing" in unknown_game.stderr


def test_benchmark_reads_simple_dotenv_lines_without_overriding(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# Codex API\n"
        "OPENAI_API_KEY='sk-from-file'\n"
        'export CODEX_MODEL="gateway model"  # trailing comment\n'
        "ANTHROPIC_MODEL=set-in-file\n"
        "not a variable\n"
        "BROKEN='unterminated\n",
        encoding="utf-8",
    )
    environment = {"ANTHROPIC_MODEL": "already-set"}

    cli._load_dotenv(dotenv, environment)
    cli._load_dotenv(tmp_path / "missing.env", environment)

    assert environment == {
        "ANTHROPIC_MODEL": "already-set",
        "OPENAI_API_KEY": "sk-from-file",
        "CODEX_MODEL": "gateway model",
    }
