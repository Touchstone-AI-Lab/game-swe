"""The extra control endpoint must fail closed; tests never contact a Steam client."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def console_probe(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    directory = Path(__file__).parents[1] / 'probes/interactive_client_v1'
    monkeypatch.syspath_prepend(str(directory))
    # Earlier probe tests replace these names with isolated fakes.
    for name in ('control', 'namespace_probe_v4', 'shm_probe_v5', 'console_probe_v7'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module('console_probe_v7')


def net_table(address: str, port: int = 8080) -> str:
    return f'header\n0: {address}:{port:04X} 00000000:0000 0A\n'


def test_old_permission_receipt_cannot_enable_cef(console_probe: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / 'approval.json'
    value = {'approved': True, 'seccomp': 'unconfined', 'maximum_process_seconds': 1800}
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='Explicit'):
        console_probe.require_approval(path)
    value.update(cef_control=True, loopback_only=True)
    path.write_text(json.dumps(value))
    assert console_probe.require_approval(path) == value


@pytest.mark.parametrize('field,value', [('approved', False), ('cef_control', False),
                                       ('loopback_only', False), ('maximum_process_seconds', 1801)])
def test_scope_expansion_is_rejected(
    console_probe: ModuleType, tmp_path: Path, field: str, value: object,
) -> None:
    decision = {'approved': True, 'cef_control': True, 'loopback_only': True,
                'maximum_process_seconds': 1800, field: value}
    path = tmp_path / 'approval.json'
    path.write_text(json.dumps(decision))
    with pytest.raises(RuntimeError, match='Explicit'):
        console_probe.require_approval(path)


def test_only_actual_loopback_listener_is_ready(console_probe: ModuleType) -> None:
    assert console_probe.listener_ready(net_table('0100007F'), 'header\n')
    assert console_probe.listener_ready('header\n', net_table('00000000000000000000000001000000'))
    assert not console_probe.listener_ready(net_table('0100007F', 80), 'header\n')


@pytest.mark.parametrize('address', ['00000000', '020011AC', '00000000000000000000000000000000'])
def test_non_loopback_listener_is_rejected(console_probe: ModuleType, address: str) -> None:
    with pytest.raises(RuntimeError, match='loopback'):
        console_probe.listener_ready(net_table(address), 'header\n')
    with pytest.raises(RuntimeError, match='loopback'):
        console_probe.listener_ready(net_table('0100007F') + net_table(address).split('\n', 1)[1], 'header\n')


def test_target_metadata_does_not_export_signin_details(console_probe: ModuleType) -> None:
    secret = 'synthetic-private-value'
    raw = json.dumps([{'title': 'SP', 'type': 'page',
                       'url': f'https://steamloopback.host/index.html?token={secret}',
                       'webSocketDebuggerUrl': 'ws://127.0.0.1:8080/devtools/page/local-id'},
                      {'title': f'Login {secret}', 'url': f'https://example.invalid/login/{secret}'}])
    result = console_probe.summarize_targets(raw)
    assert result == {'target_count': 2, 'main_context_candidates': 1,
                      'loopback_websocket_targets': 1, 'login_target_present': True}
    assert secret not in json.dumps(result) and 'local-id' not in json.dumps(result)


@pytest.mark.parametrize('url', ['ws://192.0.2.1:8080/devtools/page/a',
                                'ws://127.0.0.1:9999/devtools/page/a',
                                'ws://user:secret@127.0.0.1:8080/devtools/page/a',
                                'ws://127.0.0.1:8080/devtools/page/a?secret=value',
                                'https://127.0.0.1:8080/devtools/page/a'])
def test_metadata_cannot_redirect_control_outside_boundary(console_probe: ModuleType, url: str) -> None:
    with pytest.raises(RuntimeError, match='boundary'):
        console_probe.summarize_targets(json.dumps([{'webSocketDebuggerUrl': url}]))


@pytest.mark.parametrize('raw', ['{}', '[1]', '[]' * 131073])
def test_metadata_size_and_shape_are_bounded(console_probe: ModuleType, raw: str) -> None:
    with pytest.raises(RuntimeError):
        console_probe.summarize_targets(raw)


def test_bad_listener_stops_before_any_http_request(
    console_probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake(*args: str, **kwargs: Any) -> str:
        calls.append(args)
        return net_table('00000000') if args[-1] == '/proc/net/tcp' else 'header\n'

    monkeypatch.setattr(console_probe.control, 'inspect', lambda: {'State': {'Running': True}})
    monkeypatch.setattr(console_probe.control, 'docker', fake)
    with pytest.raises(RuntimeError, match='loopback'):
        console_probe.discover()
    assert not any('curl' in args for args in calls)
