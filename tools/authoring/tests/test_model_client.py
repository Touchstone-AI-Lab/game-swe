from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from rhenium_authoring.config import ModelSecrets
from rhenium_authoring.model_client import ModelClient
from rhenium_authoring.models import AuthoredPrompt


def test_kimi_retries_invalid_json_and_returns_strict_model() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["authorization"] == "Bearer top-secret"
        payload = json.loads(request.content)
        assert payload["reasoning_effort"] == "low"
        assert payload["max_tokens"] == 16384
        assert "response_format" not in payload
        content = (
            "not-json"
            if attempts == 1
            else "```json\n" + json.dumps({"markdown": "# Repair reports"}) + "\n```"
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets(base_url="https://model.invalid/v1", api_key=SecretStr("top-secret")),
        client=http,
    )
    result = client.complete(AuthoredPrompt, role="test", payload={"safe": True})
    assert result.markdown == "# Repair reports"
    assert attempts == 2


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
def test_kimi_failure_message_never_contains_key_or_response(protocol: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="top-secret reflected by server")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets.model_validate(
            {
                "base_url": "https://model.invalid/v1",
                "api_key": "top-secret",
                "protocol": protocol,
            }
        ),
        client=http,
        max_attempts=1,
    )
    try:
        client.complete(AuthoredPrompt, role="test", payload={})
    except RuntimeError as error:
        assert "top-secret" not in str(error)
        assert "reflected" not in str(error)
    else:
        raise AssertionError("expected a safe Kimi error")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://model.invalid",
        "https://model.invalid/",
        "https://model.invalid/v1",
        "https://model.invalid/v1/",
    ],
)
def test_anthropic_request_uses_messages_protocol(base_url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://model.invalid/v1/messages"
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert request.headers["content-type"] == "application/json"
        body = json.loads(request.content)
        assert set(body) == {"model", "system", "messages", "max_tokens"}
        assert body["model"] == "kimi-k3"
        assert body["max_tokens"] == 1024
        assert "isolated symptom author stage" in body["system"]
        assert '"additionalProperties": false' in body["system"]
        assert body["messages"] == [
            {"role": "user", "content": '{"symptom": "重复请求"}'}
        ]
        return httpx.Response(
            200,
            json=_anthropic_message(
                content=[
                    {"type": "thinking", "thinking": "Ignored private reasoning"},
                    {"type": "redacted_thinking", "data": "ignored"},
                    {"type": "text", "text": '{"markdown":'},
                    {"type": "text", "text": '"# Repair reports"}'},
                ]
            ),
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets(
            base_url=base_url,
            api_key=SecretStr("test-token"),
            protocol="anthropic",
            max_tokens=1024,
        ),
        client=http,
    )
    result = client.complete(
        AuthoredPrompt, role="symptom author", payload={"symptom": "重复请求"}
    )
    assert result.markdown == "# Repair reports"


def _anthropic_message(**overrides: object) -> dict[str, object]:
    return {
        "type": "message",
        "role": "assistant",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": '{"markdown":"# Repair reports"}'}],
        **overrides,
    }


@pytest.mark.parametrize(
    "response",
    [
        _anthropic_message(stop_reason="max_tokens"),
        _anthropic_message(stop_reason="tool_use"),
        _anthropic_message(stop_reason="pause_turn"),
        _anthropic_message(stop_reason=None),
        _anthropic_message(role="user"),
        _anthropic_message(content=[]),
        _anthropic_message(content="not-blocks"),
        _anthropic_message(content=[{"type": "text", "text": {"markdown": "bad"}}]),
        _anthropic_message(content=[{"type": "thinking", "thinking": "no text"}]),
        _anthropic_message(
            content=[
                {"type": "text", "text": '{"markdown":"# Repair reports"}'},
                {"type": "tool_use", "name": "unexpected", "input": {}},
            ]
        ),
        {"type": "error", "error": {"message": "top-secret reflected by server"}},
    ],
)
def test_anthropic_rejects_incomplete_or_non_text_responses(
    response: dict[str, object],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets(
            base_url="https://model.invalid",
            api_key=SecretStr("top-secret"),
            protocol="anthropic",
        ),
        client=http,
        max_attempts=1,
    )
    with pytest.raises(RuntimeError, match="invalid structured response") as failure:
        client.complete(AuthoredPrompt, role="test", payload={})
    assert "top-secret" not in str(failure.value)
    assert "reflected" not in str(failure.value)


def test_anthropic_retries_strict_schema_errors_without_reusing_response() -> None:
    requests: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.content)
        content = (
            '{"markdown":"rejected", "unknown":"extra field"}'
            if len(requests) == 1
            else '```json\n{"markdown":"# Repair reports"}\n```'
        )
        return httpx.Response(
            200,
            json=_anthropic_message(content=[{"type": "text", "text": content}]),
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets(
            base_url="https://model.invalid",
            api_key=SecretStr("test-token"),
            protocol="anthropic",
        ),
        client=http,
    )
    result = client.complete(AuthoredPrompt, role="test", payload={"safe": True})
    assert result.markdown == "# Repair reports"
    assert len(requests) == 2
    assert requests[0] == requests[1]


def test_kimi_protocol_is_explicit_and_preserves_tls_defaults() -> None:
    secrets = {"base_url": "https://model.invalid/v1", "api_key": "test-token"}
    config = ModelSecrets.model_validate(secrets)
    assert config.protocol == "openai"
    assert config.verify_tls is True
    with pytest.raises(ValidationError):
        ModelSecrets.model_validate({**secrets, "protocol": "unknown"})


@pytest.mark.parametrize("error,reason", [
    (httpx.ReadTimeout, "model response timeout"),
    (httpx.ConnectTimeout, "connection timeout"),
    (httpx.WriteTimeout, "request transport timeout"),
    (httpx.ConnectError, "connection or TLS failure"),
])
def test_transport_failures_report_safe_specific_category(
    error: type[httpx.HTTPError], reason: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("secret reflected in transport error", request=request)

    events: list[dict[str, object]] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = ModelClient(
            ModelSecrets(base_url="https://model.invalid", api_key=SecretStr("secret")),
            client=http, max_attempts=1, on_event=events.append,
        )
        with pytest.raises(RuntimeError, match=reason):
            client.complete(AuthoredPrompt, role="test", payload={})
    assert events[-1]["reason"] == reason
    assert "secret" not in str(events)


def _openai_response(
    content: str,
    *,
    finish_reason: str = "stop",
    reasoning: str | None = None,
    usage: dict[str, object] | None = None,
) -> dict[str, object]:
    message: dict[str, object] = {"content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    body: dict[str, object] = {
        "model": "red-lobster-7636/ds-test2",
        "choices": [{"message": message, "finish_reason": finish_reason}],
    }
    if usage is not None:
        body["usage"] = usage
    return body


def _client(
    handler: object,
    *,
    events: list[dict[str, object]] | None = None,
    sleeps: list[float] | None = None,
    max_attempts: int = 3,
    transport_attempts: int | None = None,
    max_tokens: int = 16384,
) -> ModelClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return ModelClient(
        ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("top-secret"),
            max_tokens=max_tokens,
        ),
        client=http,
        max_attempts=max_attempts,
        transport_attempts=transport_attempts,
        on_event=(events.append if events is not None else None),
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
        jitter=lambda: 0.0,
    )


def test_reasoning_content_is_ignored_and_receipts_stay_numeric() -> None:
    reasoning = "private chain of thought that must never leak"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openai_response(
                '{"markdown":"# Repair reports"}',
                reasoning=reasoning,
                usage={
                    "completion_tokens": 900,
                    "completion_tokens_details": {"reasoning_tokens": 850},
                },
            ),
        )

    events: list[dict[str, object]] = []
    client = _client(handler, events=events)
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"
    received = events[-1]
    assert received["status"] == "received"
    assert received["reasoning_characters"] == len(reasoning)
    assert received["reasoning_tokens"] == 850
    assert received["completion_tokens"] == 900
    assert "chain of thought" not in str(events)


def test_truncated_response_escalates_max_tokens_once() -> None:
    seen_max_tokens: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen_max_tokens.append(body["max_tokens"])
        if len(seen_max_tokens) == 1:
            return httpx.Response(
                200, json=_openai_response("", finish_reason="length")
            )
        return httpx.Response(
            200, json=_openai_response('{"markdown":"# Repair reports"}')
        )

    events: list[dict[str, object]] = []
    client = _client(handler, events=events)
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"
    assert seen_max_tokens == [16384, 32768]
    truncated = [event for event in events if event.get("reason") == "truncated"]
    assert truncated == [
        {
            "stage": "test",
            "attempt": 1,
            "status": "failed",
            "reason": "truncated",
            "max_tokens": 16384,
            "escalated_to": 32768,
        }
    ]


def test_double_truncation_fails_with_safe_budget_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openai_response("secret partial content", finish_reason="length"),
        )

    events: list[dict[str, object]] = []
    client = _client(handler, events=events)
    with pytest.raises(RuntimeError, match="truncated by max_tokens") as failure:
        client.complete(AuthoredPrompt, role="test", payload={})
    assert "secret partial content" not in str(failure.value)
    assert "raise [model].max_tokens" in str(failure.value)
    assert events[-1]["max_tokens"] == 32768


def test_escalation_respects_configured_ceiling() -> None:
    seen_max_tokens: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen_max_tokens.append(body["max_tokens"])
        return httpx.Response(200, json=_openai_response("", finish_reason="length"))

    client = _client(handler, max_tokens=131072)
    with pytest.raises(RuntimeError, match="truncated by max_tokens"):
        client.complete(AuthoredPrompt, role="test", payload={})
    assert seen_max_tokens == [131072]


def test_rate_limit_honors_retry_after_header() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, text="slow down")
        return httpx.Response(
            200, json=_openai_response('{"markdown":"# Repair reports"}')
        )

    events: list[dict[str, object]] = []
    sleeps: list[float] = []
    client = _client(handler, events=events, sleeps=sleeps)
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"
    assert sleeps == [2.0]
    backoff = [event for event in events if event.get("status") == "backoff"]
    assert backoff == [
        {
            "stage": "test",
            "attempt": 1,
            "status": "backoff",
            "reason": "HTTP 429",
            "delay_seconds": 2.0,
        }
    ]


def test_cold_start_conflict_backs_off_exponentially() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, text="No deployments are ready to serve this endpoint")

    events: list[dict[str, object]] = []
    sleeps: list[float] = []
    client = _client(handler, events=events, sleeps=sleeps)
    with pytest.raises(RuntimeError, match="HTTP 409") as failure:
        client.complete(AuthoredPrompt, role="test", payload={})
    assert sleeps == [1.0, 2.0, 4.0, 8.0]
    assert "deployments" not in str(failure.value)
    assert "deployments" not in str(events)


def test_unreasonable_retry_after_falls_back_to_backoff() -> None:
    headers = iter([{"Retry-After": "0"}, {"Retry-After": "3600"}, {"Retry-After": "soon"}])

    def handler(_request: httpx.Request) -> httpx.Response:
        try:
            return httpx.Response(429, headers=next(headers))
        except StopIteration:
            return httpx.Response(
                200, json=_openai_response('{"markdown":"# Repair reports"}')
            )

    sleeps: list[float] = []
    client = _client(handler, sleeps=sleeps)
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"
    assert sleeps == [1.0, 2.0, 4.0]


def test_server_errors_share_the_transport_budget() -> None:
    codes = iter([503, 500])

    def handler(_request: httpx.Request) -> httpx.Response:
        try:
            return httpx.Response(next(codes), text="secret upstream detail")
        except StopIteration:
            return httpx.Response(
                200, json=_openai_response('{"markdown":"# Repair reports"}')
            )

    sleeps: list[float] = []
    client = _client(handler, sleeps=sleeps)
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"
    assert sleeps == [1.0, 2.0]


def test_bad_request_fails_fast_without_retry() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, text="reasoning_effort: unsupported value")

    sleeps: list[float] = []
    client = _client(handler, sleeps=sleeps)
    with pytest.raises(RuntimeError, match="HTTP 400") as failure:
        client.complete(AuthoredPrompt, role="test", payload={})
    assert attempts == 1
    assert sleeps == []
    assert "unsupported value" not in str(failure.value)


def test_max_reasoning_effort_is_sent_verbatim() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "max"
        assert "response_format" not in body
        return httpx.Response(
            200, json=_openai_response('{"markdown":"# Repair reports"}')
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ModelClient(
        ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("top-secret"),
            reasoning_effort="max",
        ),
        client=http,
    )
    result = client.complete(AuthoredPrompt, role="test", payload={})
    assert result.markdown == "# Repair reports"


def test_json_answer_followed_by_native_tool_markup_is_parsed() -> None:
    from rhenium_authoring.model_client import _json_content

    raw = (
        '{"tool": "list_dir", "arguments": {"tree": "base", "path": ""}}\n\n'
        "<|DSML| calls>\n<|DSML| invoke name=\"list_dir\">\n"
        '<|DSML| parameter name="arguments" string="false">{"tree": "base", "path": ""}</|DSML| parameter>\n'
        "</|DSML| invoke>\n</|DSML| calls>"
    )
    assert json.loads(_json_content(raw)) == {"tool": "list_dir", "arguments": {"tree": "base", "path": ""}}
    fenced = '```json\n{"a": {"b": 1}}\n```'
    assert _json_content(fenced) == '{"a": {"b": 1}}'
