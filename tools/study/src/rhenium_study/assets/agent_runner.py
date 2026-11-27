"""Run mini-swe-agent through Rhenium's ModelRunner inside the agent container."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import litellm
from minisweagent.models import get_model

from rhenium.model_runner import ModelRunner

workspace, prompt_path, output = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
condition = json.loads(os.environ["RHENIUM_STUDY_CONDITION"])
prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
api_key = os.environ.pop("RHENIUM_MODEL_API_KEY", "")
started = time.time()


REPEATED_ACTION_EXIT = "RepeatedActionLoop"


class RepeatedActionGuard:
    """Wrap a mini-swe-agent model and end the run once the same commands repeat.

    When the model issues exactly the same commands ``limit`` times in a row, the run
    ends with exit status ``RepeatedActionLoop``; the last response is kept in the
    trajectory. Every other attribute is the wrapped model's.
    """

    def __init__(self, model: Any, limit: int) -> None:
        self._model = model
        self._limit = limit
        self._recent: list[tuple[str, ...]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        message = self._model.query(messages, **kwargs)
        actions = message.get("extra", {}).get("actions", [])
        commands = tuple(str(action.get("command", "")) for action in actions)
        self._recent = [*self._recent, commands][-self._limit :]
        if commands and len(self._recent) == self._limit and len(set(self._recent)) == 1:
            from minisweagent.exceptions import InterruptAgentFlow

            raise InterruptAgentFlow(
                message,
                {
                    "role": "exit",
                    "content": REPEATED_ACTION_EXIT,
                    "extra": {"exit_status": REPEATED_ACTION_EXIT, "submission": ""},
                },
            )
        return message


def stream_responses(model: Any) -> Any:
    """Have a mini-swe-agent LitellmModel stream each request and assemble each response.

    The agent receives the object a non-streaming request returns, so the conversation and
    the recorded usage do not depend on the transport. litellm reports a stream that ended
    without a finish reason as a normal stop; that is a cut-off response, so it is raised
    as the connection failure the model's own retry loop treats as a failed request.
    """
    request = model._query

    def query(messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        stream = request(messages, stream=True, stream_options={"include_usage": True}, **kwargs)
        chunks = list(stream)
        if not stream.received_finish_reason:
            raise litellm.exceptions.APIConnectionError(
                message="the response stream ended before the model finished",
                llm_provider="openai",
                model=model.config.model_name,
            )
        return litellm.stream_chunk_builder(chunks, messages=messages)

    model._query = query
    return model


def model_factory(config: dict[str, Any]) -> Any:
    kwargs = dict(config.get("model_kwargs", {}))
    if condition.get("extra_body"):
        kwargs["extra_body"] = condition["extra_body"]
    if condition.get("max_output_tokens"):
        kwargs["max_tokens"] = int(condition["max_output_tokens"])
    if condition.get("thinking"):
        kwargs["thinking"] = condition["thinking"]
        # litellm drops `thinking` under drop_params for an Anthropic model missing from its
        # model map; allowing it explicitly keeps it in the request.
        kwargs["allowed_openai_params"] = [*kwargs.get("allowed_openai_params", []), "thinking"]
    if condition.get("output_config"):
        # A top-level litellm argument reaches the Anthropic request body as is; through
        # extra_body it would be nested under a literal "extra_body" key.
        kwargs["output_config"] = condition["output_config"]
    if condition.get("omit_params"):
        # ModelRunner always sets temperature 0; litellm removes these before the request.
        kwargs["additional_drop_params"] = [
            *kwargs.get("additional_drop_params", []),
            *condition["omit_params"],
        ]
    if condition.get("prompt_caching"):
        config = {**config, "set_cache_control": "default_end"}
    model = get_model(config={**config, "model_kwargs": kwargs})
    if condition.get("stream_responses"):
        model = stream_responses(model)
    if condition.get("repeated_action_limit"):
        return RepeatedActionGuard(model, int(condition["repeated_action_limit"]))
    return model


def write(name: str, value: object) -> None:
    path = output / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def progress(value: int, phase: str) -> None:
    print(json.dumps({"t": round(time.time() - started), "progress": value, "phase": phase}), flush=True)


try:
    result = ModelRunner(model_factory=model_factory).build(
        workspace,
        prompt["requirement"],
        base_url=condition["base_url"],
        model=condition["litellm_model"],
        api_key=api_key,
        model_class="litellm",
        max_steps=int(condition["step_limit"]),
        progress=progress,
        system_prompt=prompt["systemPrompt"],
        agent_environment=(
            {"PYTHONPATH": os.environ["RHENIUM_STUDY_COMMAND_PYTHONPATH"]}
            if os.environ.get("RHENIUM_STUDY_COMMAND_PYTHONPATH")
            else {}
        ),
        command_timeout=int(condition["command_timeout_seconds"]),
        wall_time_limit_seconds=int(condition["wall_time_limit_seconds"]),
        request_timeout=int(condition["request_timeout_seconds"]),
    )
except Exception as error:  # noqa: BLE001 - recorded as a generation failure, never raised as success
    message = str(error)
    if api_key:
        message = message.replace(api_key, "***")
    write(
        "model.json",
        {
            "error": type(error).__name__,
            "message": message[:4000],
            "durationSeconds": round(time.time() - started),
        },
    )
    raise SystemExit(3) from None
trajectory = result.pop("trajectory")
write("trajectory.json", trajectory)
write("model.json", {**result, "durationSeconds": round(time.time() - started)})
print(json.dumps({"steps": result["steps"], "exitStatus": result["exitStatus"]}), flush=True)
