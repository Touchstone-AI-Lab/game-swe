from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr
from rhenium_authoring.config import ModelSecrets
from rhenium_authoring.model_client import ModelClient
from rhenium_authoring.models import AuthoredPrompt


@pytest.mark.parametrize(
    "finish_reason,reason,statuses",
    [
        # A truncated turn escalates max_tokens once, then fails on the budget.
        ("length", "truncated by max_tokens", ["requesting", "failed", "requesting", "failed"]),
        ("tool_calls", "invalid structured response", ["requesting", "failed"]),
        ("content_filter", "invalid structured response", ["requesting", "failed"]),
    ],
)
def test_incomplete_openai_response_cannot_pass_even_with_valid_json(
    finish_reason: str, reason: str, statuses: list[str]
) -> None:
    events: list[dict[str, object]] = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": finish_reason,
                            "message": {"content": '{"markdown":"valid JSON but incomplete turn"}'},
                        }
                    ]
                },
            )
        )
    ) as http:
        client = ModelClient(
            ModelSecrets(base_url="https://model.invalid/v1", api_key=SecretStr("private-token")),
            client=http,
            max_attempts=1,
            on_event=events.append,
        )
        with pytest.raises(RuntimeError, match=reason):
            client.complete(AuthoredPrompt, role="author", payload={})
    assert [event["status"] for event in events] == statuses


def test_stage_receipts_do_not_log_model_content_or_credentials() -> None:
    events: list[dict[str, object]] = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "model": "kimi-k3",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": '{"markdown":"private-generated-content"}'},
                        }
                    ],
                },
            )
        )
    ) as http:
        client = ModelClient(
            ModelSecrets(base_url="https://model.invalid/v1", api_key=SecretStr("private-token")),
            client=http,
            on_event=events.append,
        )
        result = client.complete(AuthoredPrompt, role="author", payload={"input": "private-source"})
    assert result.markdown == "private-generated-content"
    assert [event["status"] for event in events] == ["requesting", "received"]
    assert all(
        secret not in json.dumps(events)
        for secret in (
            "private-generated-content",
            "private-token",
            "private-source",
        )
    )
