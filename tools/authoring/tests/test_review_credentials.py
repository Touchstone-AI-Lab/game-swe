from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from pydantic import SecretStr, TypeAdapter
from rhenium_authoring import cli
from rhenium_authoring.cleanroom import CleanRoomSynthesizer
from rhenium_authoring.config import AuthoringSecrets, ModelSecrets
from rhenium_authoring.model_client import ModelClient
from rhenium_authoring.models import (
    HistoricalFix,
    RunMode,
    RunStatus,
    SynthesisBundle,
    SynthInterfaceContract,
)
from rhenium_authoring.state import AuthoringStore
from typer.testing import CliRunner


def _mock_owned_http_clients(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Client]:
    client_type = httpx.Client
    clients: list[httpx.Client] = []

    def create(**kwargs: Any) -> httpx.Client:
        client = client_type(**kwargs, transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    monkeypatch.setattr("rhenium_authoring.model_client.httpx.Client", create)
    return clients


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
@pytest.mark.parametrize("separate_review_key", [False, True])
def test_review_credential_routes_only_independent_review(
    monkeypatch: pytest.MonkeyPatch,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
    protocol: Literal["openai", "anthropic"],
    separate_review_key: bool,
) -> None:
    observed: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system = (
            body["system"] if protocol == "anthropic" else body["messages"][0]["content"]
        )
        payload = json.loads(body["messages"][-1]["content"])
        reviewing = "contract reviewer" in system
        expected_key = (
            "review-fixture-key" if reviewing and separate_review_key else "primary-fixture-key"
        )
        assert request.headers["authorization"] == f"Bearer {expected_key}"
        assert body["model"] == "kimi-fixture"
        assert body["max_tokens"] == 512
        assert len(body["messages"]) == (1 if protocol == "anthropic" else 2)
        assert "primary-fixture-key" not in request.content.decode()
        assert "review-fixture-key" not in request.content.decode()
        if reviewing:
            assert "private_sources" in payload
            assert payload["public_candidate"]["interface_contract"] == (
                dst_interface_contract.model_dump(mode="json")
            )
            output: dict[str, object] = {
                "approved": True,
                "leakage_findings": [],
                "contract_findings": [],
                "rationale": "Independent generated behavior matches the contract.",
            }
        else:
            assert "private_sources" not in payload
            assert "github.com" not in request.content.decode()
            output = {"markdown": "Repair the observed gameplay behaviors."}
        observed.append(("review" if reviewing else "author", expected_key))
        if protocol == "anthropic":
            assert request.url.path == "/v1/messages"
            assert request.headers["anthropic-version"] == "2023-06-01"
            response = {
                "type": "message",
                "role": "assistant",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": json.dumps(output)}],
            }
        else:
            assert request.url.path == "/v1/chat/completions"
            assert body["reasoning_effort"] == "medium"
            response = {"choices": [{"message": {"content": json.dumps(output)}}]}
        return httpx.Response(200, json=response)

    clients = _mock_owned_http_clients(monkeypatch, handler)
    secrets = AuthoringSecrets(
        model=ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("primary-fixture-key"),
            review_api_key=SecretStr("review-fixture-key") if separate_review_key else None,
            model="kimi-fixture",
            protocol=protocol,
            reasoning_effort="medium",
            max_tokens=512,
        )
    )
    with cli._synthesizer(secrets) as synthesizer:
        prompt = synthesizer.author_prompt(dst_bundle.candidate, dst_interface_contract)
        decision = synthesizer.review(
            dst_bundle.provenance,
            dst_bundle.candidate,
            dst_bundle.fixed,
            dst_bundle.base,
            dst_bundle.verifier,
            prompt,
            dst_interface_contract,
        )
        assert decision.approved
        assert all(not client.is_closed for client in clients)
    assert len(clients) == (2 if separate_review_key else 1)
    assert all(client.is_closed for client in clients)
    assert observed == [
        ("author", "primary-fixture-key"),
        ("review", "review-fixture-key" if separate_review_key else "primary-fixture-key"),
    ]


def test_review_clients_close_after_generation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _mock_owned_http_clients(monkeypatch, lambda _request: httpx.Response(500))
    secrets = AuthoringSecrets(
        model=ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("primary-fixture-key"),
            review_api_key=SecretStr("review-fixture-key"),
        )
    )
    with pytest.raises(RuntimeError, match="generation failed"), cli._synthesizer(secrets):
        raise RuntimeError("generation failed")
    assert len(clients) == 2
    assert all(client.is_closed for client in clients)


def test_primary_client_closes_if_reviewer_cannot_start(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _mock_owned_http_clients(monkeypatch, lambda _request: httpx.Response(500))
    secrets = AuthoringSecrets(
        model=ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("primary-fixture-key"),
            review_api_key=SecretStr("review-fixture-key"),
        )
    )

    def create(config: ModelSecrets, **kwargs: Any) -> ModelClient:
        if config.api_key.get_secret_value() == "review-fixture-key":
            raise RuntimeError("reviewer cannot start")
        return ModelClient(config, **kwargs)

    monkeypatch.setattr(cli, "ModelClient", create)
    with pytest.raises(RuntimeError, match="reviewer cannot start"), cli._synthesizer(secrets):
        pytest.fail("a synthesizer must not start without its configured reviewer")
    assert len(clients) == 1
    assert clients[0].is_closed


@pytest.mark.parametrize("command", ["run", "generate", "retry"])
def test_cli_generation_commands_configure_the_review_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dst_bundle: SynthesisBundle,
    command: str,
) -> None:
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    secrets = AuthoringSecrets(
        model=ModelSecrets(
            base_url="https://model.invalid/v1",
            api_key=SecretStr("primary-fixture-key"),
            review_api_key=SecretStr("review-fixture-key"),
        )
    )
    monkeypatch.setattr(cli, "_context", lambda: (tmp_path, store))
    monkeypatch.setattr(cli.AuthoringSecrets, "load", lambda _root: secrets)
    clients = _mock_owned_http_clients(monkeypatch, lambda _request: httpx.Response(500))
    received: list[CleanRoomSynthesizer] = []

    class Pipeline:
        def __init__(
            self,
            root: Path,
            state: AuthoringStore,
            synthesizer: CleanRoomSynthesizer,
            *args: object,
            **kwargs: object,
        ) -> None:
            del root, state, args, kwargs
            received.append(synthesizer)

        def run(self, **kwargs: object) -> str:
            del kwargs
            return "author-generated"

    monkeypatch.setattr(cli, "AuthoringPipeline", Pipeline)
    args = [command]
    if command in ("generate", "retry"):
        if command == "retry":
            run_id = store.create_run(RunMode.REVIEW)
            store.update_run(run_id, RunStatus.FAILED)
            path = tmp_path / ".rhenium/authoring/runs" / run_id / "historical-fixes.json"
            path.parent.mkdir(parents=True)
            args.append(run_id)
        else:
            path = tmp_path / "input.json"
            args.extend(["--input", str(path)])
        path.write_bytes(TypeAdapter(list[HistoricalFix]).dump_json(list(dst_bundle.provenance)))
    else:
        args.extend(["--sources", "github", "--games", "dst", "--limit", "2"])
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert "author-generated" in result.output
    assert len(received) == 1
    assert received[0].client.secrets.api_key.get_secret_value() == "primary-fixture-key"
    assert received[0].reviewer.secrets.api_key.get_secret_value() == "review-fixture-key"
    assert received[0].reviewer is not received[0].client
    assert all(client.is_closed for client in clients)
