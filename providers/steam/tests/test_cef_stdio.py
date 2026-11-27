from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from rhenium_steam import cef_stdio as transport


def test_transport_checks_upgrade_identity_and_bounds_before_starting() -> None:
    header = (
        b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
    )
    transport.validate_upgrade(header, "dGhlIHNhbXBsZSBub25jZQ==")
    with pytest.raises(transport.CEFError):
        transport.validate_upgrade(header, base64.b64encode(b"other").decode())
    with pytest.raises(transport.CEFError):
        transport.CEF("/bad", command=[], env={})
    with pytest.raises(transport.CEFError):
        transport.frame(b"x" * (transport.LIMIT + 1))


def test_partial_pipe_writes_preserve_one_complete_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    parts: list[bytes] = []

    class Pipe:
        def write(self, value: bytes | memoryview) -> int:
            parts.append(bytes(value[:3]))
            return len(value[:3])

        def flush(self) -> None:
            pass

    client = transport.CEF.__new__(transport.CEF)
    monkeypatch.setattr(client, "process", SimpleNamespace(stdin=Pipe()), raising=False)
    client.write(b"0123456789")
    assert b"".join(parts) == b"0123456789"


def test_evaluate_ignores_other_ids_and_never_accepts_exception_as_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = transport.CEF.__new__(transport.CEF)
    client.sequence = 0
    client.timeout = 1
    messages = iter(
        [
            {"id": 9, "result": {"result": {"value": "wrong"}}},
            {"id": 1, "result": {"result": {"value": {"received": True}}}},
        ]
    )
    monkeypatch.setattr(client, "write", lambda _: None)
    monkeypatch.setattr(client, "receive", lambda _: json.dumps(next(messages)).encode())
    assert client.evaluate("fixed-test") == {"received": True}
    monkeypatch.setattr(client, "receive", lambda _: b'{"id":2,"result":{"exceptionDetails":{}}}')
    with pytest.raises(transport.CEFError, match="failed"):
        client.evaluate("fixed-test")
