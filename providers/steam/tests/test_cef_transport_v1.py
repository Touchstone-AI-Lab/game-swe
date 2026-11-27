from __future__ import annotations

import importlib
import struct
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'probes/interactive_client_v1'))
    return importlib.import_module('cef_transport_v1')


@pytest.mark.parametrize('size', [0, 125, 126, 65535, 65536])
def test_client_frames_mask_every_byte(transport: ModuleType, size: int) -> None:
    payload = b'x' * size
    wire = transport.frame(payload)
    assert wire[0] == 129 and wire[1] & 128
    offset = 2
    length = wire[1] & 127
    if length == 126:
        length = struct.unpack('!H', wire[2:4])[0]
        offset = 4
    elif length == 127:
        length = struct.unpack('!Q', wire[2:10])[0]
        offset = 10
    mask = wire[offset:offset+4]
    assert length == size
    assert bytes(v ^ mask[i%4] for i,v in enumerate(wire[offset+4:])) == payload


def test_upgrade_verifies_server_nonce_response(transport: ModuleType) -> None:
    header = (b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
              b'Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=')
    transport.validate_upgrade(header, 'dGhlIHNhbXBsZSBub25jZQ==')
    with pytest.raises(transport.CEFError, match='identity'):
        transport.validate_upgrade(header, 'different-key')


def test_bounded_size_and_endpoint_rejected_before_docker(transport: ModuleType) -> None:
    with pytest.raises(transport.CEFError):
        transport.frame(b'x'*(transport.LIMIT+1))
    with pytest.raises(transport.CEFError):
        transport.CEF('/devtools/page/a\r\nInjected: yes')


def test_fragmented_server_text_and_invalid_continuation(transport: ModuleType) -> None:
    reader = transport.CEF.__new__(transport.CEF)
    reader.buffer = bytearray(b'\x01\x03abc\x80\x03def')
    assert reader.receive(0) == b'abcdef'
    reader.buffer = bytearray(b'\x80\x03abc')
    with pytest.raises(transport.CEFError, match='continuation'):
        reader.receive(0)
    reader.buffer = bytearray(b'\x81\xff')
    with pytest.raises(transport.CEFError, match='server frame'):
        reader.receive(0)
