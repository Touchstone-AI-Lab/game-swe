from __future__ import annotations

import ast
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from rhenium_study.e1config import ModelCondition

ROOT = Path(__file__).parents[3]
RUNNER = ROOT / "tools/study/src/rhenium_study/assets/agent_runner.py"

_USAGE = {
    "prompt_tokens": 10,
    "completion_tokens": 7,
    "total_tokens": 17,
    "completion_tokens_details": {"reasoning_tokens": 5},
}
_ENVELOPE = {"id": "chatcmpl-x", "created": 0, "model": "test"}
_MESSAGE = {
    "role": "assistant",
    "content": None,
    "refusal": None,
    "reasoning_content": "weighing it",
    "tool_calls": [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "bash", "arguments": '{"command": "ls"}'},
        }
    ],
}
_PLAIN = {
    **_ENVELOPE,
    "object": "chat.completion",
    "choices": [{"index": 0, "finish_reason": "tool_calls", "message": _MESSAGE}],
    "usage": _USAGE,
}


def _chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
    choice = {"index": 0, "delta": delta, "finish_reason": finish_reason}
    return {**_ENVELOPE, "object": "chat.completion.chunk", "choices": [choice]}


_BODY_CHUNKS = [
    _chunk({"role": "assistant", "reasoning_content": "weighing "}),
    _chunk({"reasoning_content": "it"}),
    _chunk(
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"comm'},
                }
            ]
        }
    ),
    _chunk({"tool_calls": [{"index": 0, "function": {"arguments": 'and": "ls"}'}}]}),
]
_END_CHUNKS = [
    _chunk({}, "tool_calls"),
    {**_ENVELOPE, "object": "chat.completion.chunk", "choices": [], "usage": _USAGE},
]


class _Gateway:
    """A local OpenAI-style endpoint: plain JSON, or SSE for a streaming request."""

    def __init__(self, chunks: list[dict[str, Any]], *, finished: bool = True) -> None:
        self.requests: list[dict[str, Any]] = []
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server API
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gateway.requests.append(body)
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(b": keep-alive\n\n")
                    for chunk in chunks:
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    if finished:
                        self.wfile.write(b"data: [DONE]\n\n")
                    return
                data = json.dumps(_PLAIN).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.fixture
def gateways(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[_Gateway]]:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "1")
    started: list[_Gateway] = []
    yield started
    for gateway in started:
        gateway.server.shutdown()


def _serve(
    gateways: list[_Gateway], chunks: list[dict[str, Any]], *, finished: bool = True
) -> _Gateway:
    gateway = _Gateway(chunks, finished=finished)
    gateways.append(gateway)
    return gateway


def _stream_responses() -> Any:
    """The container runner's own stream_responses, without running the script."""
    litellm = pytest.importorskip("litellm")
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "stream_responses"
    )
    namespace: dict[str, Any] = {"Any": Any, "litellm": litellm}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(RUNNER), "exec"), namespace)
    return namespace["stream_responses"]


def _model(base: str) -> Any:
    """A real LitellmModel with the request settings of ModelRunner and an effort condition."""
    module = pytest.importorskip("minisweagent.models.litellm_model")
    kwargs = {
        "api_base": base,
        "api_key": "test",
        "temperature": 0,
        "drop_params": True,
        "extra_body": {"reasoning_effort": "xhigh"},
    }
    return module.LitellmModel(
        model_name="openai/test", model_kwargs=kwargs, cost_tracking="ignore_errors"
    )


_USER = [{"role": "user", "content": "hi"}]


def _agent_view(message: dict[str, Any]) -> dict[str, Any]:
    """What the next request repeats of a message: everything but the agent's own bookkeeping."""
    return {key: value for key, value in message.items() if key != "extra"}


def test_a_streamed_response_reaches_the_agent_as_a_finished_response(
    gateways: list[_Gateway],
) -> None:
    gateway = _serve(gateways, [*_BODY_CHUNKS, *_END_CHUNKS])
    message = _stream_responses()(_model(gateway.base)).query(_USER)

    [body] = gateway.requests
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
    assert body["reasoning_effort"] == "xhigh" and body["temperature"] == 0
    assert [tool["function"]["name"] for tool in body["tools"]] == ["bash"]

    assert [action["command"] for action in message["extra"]["actions"]] == ["ls"]
    usage = message["extra"]["response"]["usage"]
    assert usage["prompt_tokens"] == 10 and usage["completion_tokens"] == 7
    assert usage["completion_tokens_details"]["reasoning_tokens"] == 5


def test_the_transport_does_not_change_the_conversation(gateways: list[_Gateway]) -> None:
    """The next request repeats the same assistant message whichever transport delivered it."""
    streamed = _serve(gateways, [*_BODY_CHUNKS, *_END_CHUNKS])
    plain = _serve(gateways, [])
    streamed_model = _stream_responses()(_model(streamed.base))
    plain_model = _model(plain.base)

    streamed_message = streamed_model.query(_USER)
    plain_message = plain_model.query(_USER)

    def repeated(message: dict[str, Any]) -> list[dict[str, Any]]:
        observation = {"role": "tool", "tool_call_id": "call_1", "content": "done"}
        return [*_USER, _agent_view(message), observation]

    streamed_model.query(repeated(streamed_message))
    plain_model.query(repeated(plain_message))
    sent = [gateway.requests[-1]["messages"] for gateway in (streamed, plain)]
    # litellm files the gateway's empty `refusal` here and repeats it; no model reads it.
    assert sent[1][1].pop("provider_specific_fields") == {"refusal": None}
    assert sent[0] == sent[1]


def test_a_stream_cut_off_before_a_finish_reason_is_a_failed_request(
    gateways: list[_Gateway],
) -> None:
    litellm = pytest.importorskip("litellm")
    gateway = _serve(gateways, _BODY_CHUNKS, finished=False)
    with pytest.raises(litellm.exceptions.APIConnectionError, match="before the model finished"):
        _stream_responses()(_model(gateway.base)).query(_USER)


def test_streaming_is_off_unless_the_condition_asks_for_it(gateways: list[_Gateway]) -> None:
    condition = ModelCondition(
        id="m", litellm_model="openai/m", base_url="http://x", api_key_file=Path("k")
    )
    assert condition.stream_responses is False
    gateway = _serve(gateways, [])
    _model(gateway.base).query(_USER)
    assert "stream" not in gateway.requests[0]
