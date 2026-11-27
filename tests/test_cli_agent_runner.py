from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from rhenium.cli_agent_runner import CliAgentError, CliAgentRunner, cli_agent_command, cli_agent_model


def _install(bin_dir: Path, name: str, body: str) -> None:
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / name
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "' + name + ' 9.9.9"; exit 0; fi\n' + body,
        encoding="utf-8",
    )
    script.chmod(0o755)


def test_codex_runs_unattended_in_its_workspace_sandbox() -> None:
    command = cli_agent_command(
        "codex", {"OPENAI_BASE_URL": "https://gateway.example/v1", "CODEX_MODEL": "gateway-model"}
    )

    assert command == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--json",
        "--config",
        "openai_base_url=https://gateway.example/v1",
        "--model",
        "gateway-model",
        "-",
    ]
    assert cli_agent_model("codex", {"CODEX_MODEL": "gateway-model"}) == "gateway-model"
    assert cli_agent_model("codex", {}) == "codex default"


def test_claude_reads_its_prompt_from_stdin_and_never_bypasses_permissions() -> None:
    command = cli_agent_command("claude", {"ANTHROPIC_MODEL": "claude-gateway-model"})

    assert command[:2] == ["claude", "--print"]
    assert "--permission-mode" in command and "acceptEdits" in command
    assert "bypassPermissions" not in command
    assert not any("dangerously" in part for part in command)
    assert cli_agent_model("claude", {"ANTHROPIC_MODEL": "claude-gateway-model"}) == "claude-gateway-model"
    with pytest.raises(CliAgentError, match="unknown"):
        cli_agent_command("gemini", {})


def test_runner_withholds_rhenium_state_and_redacts_secrets(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    _install(
        bin_dir,
        "codex",
        'cat > prompt.seen\nprintf \'fixture-ok\\n\' > answer.txt\n'
        'printf \'{"state": "%s", "key": "%s"}\\n\' "$RHENIUM_STATE_DIR" "$OPENAI_API_KEY"\n'
        "printf '{\"type\": \"done\"}\\n'\n",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RHENIUM_STATE_DIR", "/private/rhenium/state")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    log = tmp_path / "trajectory.jsonl"

    result = CliAgentRunner().run("codex", workspace, "solve the exam\n", log)

    assert result["exitStatus"] == "exit 0"
    assert result["framework"] == {
        "name": "codex",
        "version": "codex 9.9.9",
        "trajectoryFormat": "codex-exec-jsonl",
    }
    assert result["steps"] == 2
    assert result["changedFiles"] == ["answer.txt", "prompt.seen"]
    assert (workspace / "prompt.seen").read_text(encoding="utf-8") == "solve the exam\n"
    trajectory = log.read_text(encoding="utf-8")
    assert "/private/rhenium/state" not in trajectory
    assert "sk-secret-value" not in trajectory and '"key": "***"' in trajectory


def test_runner_stops_an_agent_that_exceeds_its_time_limit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    _install(bin_dir, "claude", "cat > /dev/null\nsleep 30\n")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    workspace = tmp_path / "attempt"
    workspace.mkdir()

    started = time.monotonic()
    result = CliAgentRunner().run("claude", workspace, "prompt", tmp_path / "log.jsonl", timeout_seconds=1)

    assert result["exitStatus"] == "timeout"
    assert time.monotonic() - started < 20


def test_runner_fails_closed_without_the_agent_cli(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    workspace = tmp_path / "attempt"
    workspace.mkdir()

    with pytest.raises(CliAgentError, match="claude is not installed"):
        CliAgentRunner().run("claude", workspace, "prompt", tmp_path / "log.jsonl")
