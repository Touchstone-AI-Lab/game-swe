from __future__ import annotations

import ast
import importlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[3]
RUNNER = ROOT / "tools/study/src/rhenium_study/assets/agent_runner.py"


def _model_factory(condition: dict[str, Any]) -> Any:
    """The container runner's own model_factory, bound to a fake get_model that returns its config."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "model_factory"
    )
    namespace: dict[str, Any] = {"condition": condition, "get_model": lambda config: config, "Any": Any}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(RUNNER), "exec"), namespace)
    return namespace["model_factory"]


_ANTHROPIC_REPLY = {
    "id": "msg_x",
    "type": "message",
    "role": "assistant",
    "model": "claude-test",
    "content": [{"type": "text", "text": "ok"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}
_OPENAI_REPLY = {
    "id": "chatcmpl-x",
    "object": "chat.completion",
    "created": 0,
    "model": "test",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


def _capture(model: str, model_kwargs: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Send one completion through litellm to a local fake endpoint; return path, headers and body.

    The request has the shape mini-swe-agent's LitellmModel._query sends: its bash tool
    plus the model_kwargs. Anthropic routes (``/v1/messages``) get an Anthropic reply,
    every other route an OpenAI chat completion.
    """
    litellm = pytest.importorskip("litellm")
    toolcall = pytest.importorskip("minisweagent.models.utils.actions_toolcall")
    captured: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append((self.path, {key.lower(): value for key, value in self.headers.items()}, body))
            reply = _ANTHROPIC_REPLY if self.path.endswith("/messages") else _OPENAI_REPLY
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            tools=[toolcall.BASH_TOOL],
            **{**model_kwargs, "api_base": base, "api_key": "test"},
        )
    finally:
        server.shutdown()
    assert len(captured) == 1
    return captured[0]


def _sent_body(model_kwargs: dict[str, Any]) -> dict[str, Any]:
    return _capture("anthropic/claude-test-unmapped", model_kwargs)[2]


def _runner_request(model: str, condition: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
    """What the container runner sends: ModelRunner's own model config through model_factory."""
    runner = importlib.import_module("rhenium.model_runner").ModelRunner
    config = _model_factory(condition)(
        runner._model_config(model, "http://placeholder", "test", "litellm", request_timeout=30)
    )
    return _capture(config["model_name"], config["model_kwargs"])


def test_the_thinking_condition_reaches_the_request_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    thinking = {"type": "enabled", "budget_tokens": 16000}
    factory = _model_factory({"thinking": thinking, "max_output_tokens": 64000})
    config = factory({"model_kwargs": {"temperature": 0, "drop_params": True}})
    body = _sent_body(config["model_kwargs"])
    assert body["thinking"] == thinking and body["max_tokens"] == 64000
    # Without the explicit allowance litellm drops it for a model missing from its map.
    config = _model_factory({})(
        {"model_kwargs": {"temperature": 0, "drop_params": True, "thinking": thinking}}
    )
    assert "thinking" not in _sent_body(config["model_kwargs"])


def test_output_config_and_omitted_temperature_reach_the_anthropic_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The direct-API Claude Opus 5 condition: adaptive thinking with a top-level effort.

    Opus 5 rejects `thinking.type = "enabled"`, and with adaptive thinking it rejects any
    temperature but 1, while ModelRunner always sends temperature 0.
    """
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    thinking = {"type": "adaptive", "display": "summarized"}
    path, headers, body = _runner_request(
        "anthropic/claude-opus-5",
        {
            "thinking": thinking,
            "output_config": {"effort": "high"},
            "omit_params": ["temperature"],
            "max_output_tokens": 64000,
        },
    )
    assert path == "/v1/messages"
    assert body["output_config"] == {"effort": "high"}
    assert body["thinking"] == thinking
    assert body["max_tokens"] == 64000
    assert "temperature" not in body and "extra_body" not in body
    # The one beta header litellm adds for output_config.effort on a model its map does
    # not mark as adaptive (the README states it); the direct API accepts it.
    assert headers.get("anthropic-beta") == "effort-2025-11-24"
    # Without the condition fields the scaffold's temperature 0 is still sent.
    _path, _headers, plain = _runner_request("anthropic/claude-opus-5", {"thinking": thinking})
    assert plain["temperature"] == 0 and "output_config" not in plain


def test_extra_body_on_the_anthropic_route_is_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    """Why output_config is its own field: through extra_body it never reaches the top level."""
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    _path, _headers, body = _runner_request(
        "anthropic/claude-opus-5", {"extra_body": {"output_config": {"effort": "high"}}}
    )
    assert "output_config" not in body
    assert body["extra_body"] == {"output_config": {"effort": "high"}}


def test_an_openai_route_keeps_temperature_zero_and_merges_extra_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    extra_body = {"reasoning_effort": "high", "chat_template_kwargs": {"enable_thinking": True}}
    path, _headers, body = _runner_request("openai/org/model-b", {"extra_body": extra_body})
    assert path == "/chat/completions"
    assert body["temperature"] == 0
    assert body["reasoning_effort"] == "high"
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    assert "extra_body" not in body and "output_config" not in body
