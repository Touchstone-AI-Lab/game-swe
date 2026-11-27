from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from .agent.environment import _PRIVATE_PREFIXES
from .model_runner import ModelRunner

Progress = Callable[[int, str], None]

CLI_AGENT_PROVIDERS = ("codex", "claude")
AGENT_PROVIDERS = ("api", *CLI_AGENT_PROVIDERS)

_FRAMEWORKS = {
    "codex": ("codex", "codex-exec-jsonl"),
    "claude": ("claude-code", "claude-stream-json"),
}
_MODEL_VARIABLES = {"codex": "CODEX_MODEL", "claude": "ANTHROPIC_MODEL"}
_SECRET_VARIABLES = ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class CliAgentError(RuntimeError):
    pass


def cli_agent_command(provider: str, environment: Mapping[str, str]) -> list[str]:
    """Return the unattended command line for a coding-agent CLI; the prompt goes to stdin."""
    if provider == "codex":
        command = ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "--json"]
        if environment.get("OPENAI_BASE_URL"):
            command += ["--config", f"openai_base_url={environment['OPENAI_BASE_URL']}"]
        if environment.get("CODEX_MODEL"):
            command += ["--model", environment["CODEX_MODEL"]]
        return [*command, "-"]
    if provider == "claude":
        return [
            "claude",
            "--print",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            "Bash",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
    raise CliAgentError(f"unknown agent CLI provider: {provider}")


def cli_agent_model(provider: str, environment: Mapping[str, str]) -> str:
    """Name the model a CLI agent uses: its configured model, or the CLI's own default."""
    return environment.get(_MODEL_VARIABLES[provider], "") or f"{provider} default"


class CliAgentRunner:
    """Run Codex or Claude Code unattended in an attempt directory.

    The agent only implements; the Hub scores the attempt afterwards. Rhenium's own
    variables (state and benchmark paths, model settings) are withheld from the agent.
    This is credential and identity hygiene, not an operating-system sandbox: Codex
    confines writes with its workspace-write sandbox, while Claude Code may run any
    shell command, like the mini-swe-agent ``api`` provider.
    """

    def run(
        self,
        provider: str,
        workspace: Path,
        prompt: str,
        log_path: Path,
        *,
        progress: Progress | None = None,
        timeout_seconds: int = 21600,
    ) -> dict[str, Any]:
        progress = progress or (lambda _value, _phase: None)
        environment = {
            name: value for name, value in os.environ.items() if not name.startswith(_PRIVATE_PREFIXES)
        }
        command = cli_agent_command(provider, environment)
        executable = shutil.which(command[0], path=environment.get("PATH"))
        if executable is None:
            raise CliAgentError(f"{command[0]} is not installed or is not on PATH")
        command[0] = executable
        secrets = [environment[name] for name in _SECRET_VARIABLES if environment.get(name)]
        before = ModelRunner._snapshot(workspace)
        timed_out = threading.Event()
        events = 0

        progress(5, f"starting {provider}")
        with (
            log_path.open("w", encoding="utf-8") as log,
            subprocess.Popen(
                command,
                cwd=workspace,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
            ) as process,
        ):
            timer = threading.Timer(max(1, timeout_seconds), self._stop, (process, timed_out))
            timer.start()
            try:
                assert process.stdin is not None and process.stdout is not None
                try:
                    process.stdin.write(prompt)
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                for line in process.stdout:
                    for secret in secrets:
                        line = line.replace(secret, "***")
                    log.write(line)
                    events += 1
                    progress(min(85, 10 + events // 4), f"{provider} event {events}")
                returncode = process.wait()
            finally:
                timer.cancel()

        after = ModelRunner._snapshot(workspace)
        changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
        name, trajectory_format = _FRAMEWORKS[provider]
        return {
            "framework": {
                "name": name,
                "version": self._version(executable, environment),
                "trajectoryFormat": trajectory_format,
            },
            "steps": events,
            "exitStatus": "timeout" if timed_out.is_set() else f"exit {returncode}",
            "changedFiles": changed,
        }

    @staticmethod
    def _stop(process: subprocess.Popen[str], timed_out: threading.Event) -> None:
        timed_out.set()
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass

    @staticmethod
    def _version(executable: str, environment: Mapping[str, str]) -> str:
        try:
            completed = subprocess.run(
                [executable, "--version"],
                env=dict(environment),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"
        lines = completed.stdout.strip().splitlines()
        return lines[0] if lines else "unknown"


__all__ = [
    "AGENT_PROVIDERS",
    "CLI_AGENT_PROVIDERS",
    "CliAgentError",
    "CliAgentRunner",
    "cli_agent_command",
    "cli_agent_model",
]
