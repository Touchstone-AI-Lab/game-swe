from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from minisweagent import Environment, Model
from minisweagent import __version__ as mini_swe_agent_version
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model

from .agent.environment import WorkspaceEnvironment

Progress = Callable[[int, str], None]
ModelFactory = Callable[[dict[str, Any]], Model]
EnvironmentFactory = Callable[[Path, Path, int, dict[str, str]], Environment]

_INSTANCE_TEMPLATE = """Implement the complete task below from scratch.

{{ task }}

Use shell commands to inspect and edit the current workspace. Every response must include at least
one bash tool call. Directory changes do not persist between calls, but every call starts in the
workspace root. When the implementation is complete, run exactly this command by itself:

    echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
"""


class ModelRunnerError(RuntimeError):
    pass


class _ProgressAgent(DefaultAgent):
    def __init__(self, *args: Any, progress: Progress, configured_steps: int, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._progress = progress
        self._configured_steps = configured_steps

    def query(self) -> dict:
        step = self.n_calls + 1
        self._progress(
            min(85, 10 + int(step / self._configured_steps * 70)),
            f"mini-swe-agent step {step}",
        )
        return super().query()


class ModelRunner:
    """Run the model-under-test through mini-swe-agent's standard control loop."""

    def __init__(
        self,
        *,
        model_factory: ModelFactory | None = None,
        environment_factory: EnvironmentFactory | None = None,
    ) -> None:
        self._model_factory = model_factory or (lambda config: get_model(config=config))
        self._environment_factory = environment_factory or self._local_environment

    def build(
        self,
        workspace: Path,
        requirement: str,
        *,
        base_url: str,
        model: str,
        api_key: str,
        model_class: str = "litellm",
        max_steps: int = 100,
        progress: Progress | None = None,
        system_prompt: str | None = None,
        agent_environment: dict[str, str] | None = None,
        command_timeout: int = 180,
        wall_time_limit_seconds: int = 21600,
        request_timeout: int = 600,
    ) -> dict[str, Any]:
        progress = progress or (lambda _value, _phase: None)
        if not model.strip():
            raise ModelRunnerError("The model-under-test name is not configured")
        workspace = workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise ModelRunnerError(f"Model workspace is not a directory: {workspace}")

        step_limit = max(1, min(int(max_steps), 1000))
        before = self._snapshot(workspace)
        with tempfile.TemporaryDirectory(prefix="rhenium-agent-home-") as home_value:
            environment = self._environment_factory(
                workspace,
                Path(home_value),
                max(1, int(command_timeout)),
                dict(agent_environment or {}),
            )
            model_config = self._model_config(
                model, base_url, api_key, model_class, max(1, int(request_timeout))
            )
            mini_model = self._model_factory(model_config)
            agent = _ProgressAgent(
                mini_model,
                environment,
                progress=progress,
                configured_steps=step_limit,
                system_template=system_prompt or self._default_system_prompt(),
                instance_template=_INSTANCE_TEMPLATE,
                step_limit=step_limit,
                cost_limit=0,
                wall_time_limit_seconds=max(0, int(wall_time_limit_seconds)),
                output_path=None,
            )
            result = agent.run(requirement)
            trajectory = self._redact(agent.serialize(), api_key)

        after = self._snapshot(workspace)
        changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
        final_response = str(result.get("submission") or self._last_assistant_content(trajectory))
        return {
            "framework": {
                "name": "mini-swe-agent",
                "version": mini_swe_agent_version,
                "trajectoryFormat": trajectory.get("trajectory_format"),
            },
            "steps": agent.n_calls,
            "exitStatus": str(result.get("exit_status", "")),
            "changedFiles": changed,
            "finalResponse": final_response,
            "trajectory": trajectory,
        }

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are the model under test in a game-engineering implementation benchmark. "
            "Work only on the public task in the current workspace, build the requested project "
            "from scratch, and verify the implementation before submitting. Private evaluator "
            "assets are not available to you."
        )

    @staticmethod
    def _model_config(
        model: str,
        base_url: str,
        api_key: str,
        model_class: str,
        request_timeout: int = 600,
    ) -> dict[str, Any]:
        model_name = model.strip()
        if "/" not in model_name:
            model_name = f"openai/{model_name}"
        model_kwargs: dict[str, Any] = {
            "temperature": 0,
            "drop_params": True,
            # Without this a stalled connection hangs the attempt until the wall-clock
            # limit, hours after the provider stopped answering; a timed-out request
            # fails the step instead and the agent can carry on.
            "timeout": request_timeout,
        }
        if base_url.strip():
            model_kwargs["api_base"] = base_url.rstrip("/")
        if api_key:
            model_kwargs["api_key"] = api_key
        return {
            "model_class": model_class.strip() or "litellm",
            "model_name": model_name,
            "cost_tracking": "ignore_errors",
            "model_kwargs": model_kwargs,
        }

    @staticmethod
    def _local_environment(
        workspace: Path,
        home: Path,
        timeout: int,
        agent_environment: dict[str, str],
    ) -> Environment:
        return WorkspaceEnvironment(
            cwd=str(workspace),
            home=home,
            timeout=timeout,
            env={
                "PAGER": "cat",
                "MANPAGER": "cat",
                "PIP_PROGRESS_BAR": "off",
                "TQDM_DISABLE": "1",
                **agent_environment,
            },
        )

    @staticmethod
    def _snapshot(workspace: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in sorted(workspace.rglob("*")):
            if not path.is_file() or ".git" in path.parts or path.is_symlink():
                continue
            relative = path.relative_to(workspace).as_posix()
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    @classmethod
    def _redact(cls, value: Any, secret: str) -> Any:
        if isinstance(value, dict):
            return {
                key: "***" if key.lower() in {"api_key", "authorization"} else cls._redact(item, secret)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact(item, secret) for item in value]
        if isinstance(value, str) and secret:
            return value.replace(secret, "***")
        return value

    @staticmethod
    def _last_assistant_content(trajectory: dict[str, Any]) -> str:
        messages = trajectory.get("messages", [])
        if not isinstance(messages, list):
            return ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "assistant":
                content = message.get("content")
                return content if isinstance(content, str) else ""
        return ""


MiniSweAgentRunner = ModelRunner

__all__ = ["MiniSweAgentRunner", "ModelRunner", "ModelRunnerError"]
