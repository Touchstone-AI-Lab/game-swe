"""Approval-gated, read-only discovery of the owned Steam CEF control endpoint."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import control
import shm_probe_v5

PORT = 8080
NAME = 'rhenium-steam-interactive-console-v7-20261031'


def require_approval(path: Path) -> dict[str, object]:
    value: dict[str, object] = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('approved') is not True or value.get('cef_control') is not True
            or value.get('loopback_only') is not True
            or value.get('maximum_process_seconds') != 1800):
        raise RuntimeError('Explicit container-local CEF control approval required')
    return value


def listener_ready(tcp: str, tcp6: str) -> bool:
    found = False
    for data, allowed in ((tcp, '0100007F'), (tcp6, '00000000000000000000000001000000')):
        for line in data.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != '0A':
                continue
            address, port = fields[1].split(':')
            if int(port, 16) != PORT:
                continue
            if address != allowed:
                raise RuntimeError('CEF listener is not confined to loopback')
            found = True
    return found


def summarize_targets(raw: str) -> dict[str, Any]:
    if len(raw.encode()) > 262144:
        raise RuntimeError('CEF metadata exceeded the bounded response size')
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) > 32:
        raise RuntimeError('Unexpected CEF metadata shape')
    result: dict[str, Any] = {'target_count': len(value), 'main_context_candidates': 0,
                             'loopback_websocket_targets': 0, 'login_target_present': False}
    for target in value:
        if not isinstance(target, dict):
            raise RuntimeError('Unexpected CEF target shape')
        # Never return raw titles, URLs, IDs or page content, including login challenges.
        title = str(target.get('title', ''))
        parsed = urlsplit(str(target.get('url', '')))
        if 'login' in title.lower() or 'login' in parsed.path.lower():
            result['login_target_present'] = True
        if title in {'SP', 'SharedJSContext'}:
            result['main_context_candidates'] += 1
        socket_url = target.get('webSocketDebuggerUrl')
        if socket_url:
            endpoint = urlsplit(str(socket_url))
            if (endpoint.scheme != 'ws' or endpoint.hostname not in {'127.0.0.1', 'localhost', '::1'}
                    or endpoint.port != PORT or endpoint.username or endpoint.password
                    or endpoint.query or endpoint.fragment
                    or not endpoint.path.startswith('/devtools/page/')):
                raise RuntimeError('CEF WebSocket endpoint escaped the local boundary')
            result['loopback_websocket_targets'] += 1
    return result


def discover(timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not control.inspect()['State']['Running']:
            raise RuntimeError('Official client exited before interface discovery')
        tcp = control.docker('exec', NAME, 'cat', '/proc/net/tcp')
        tcp6 = control.docker('exec', NAME, 'cat', '/proc/net/tcp6')
        if listener_ready(tcp, tcp6):
            raw = control.docker('exec', NAME, 'curl', '--noproxy', '*', '--silent', '--fail',
                                 '--max-time', '5', '--max-filesize', '262144',
                                 f'http://127.0.0.1:{PORT}/json/list', timeout=10)
            result = summarize_targets(raw)
            result['listener_loopback_verified'] = True
            result['authentication_validated'] = False
            result['acquisition_executed'] = False
            return result
        time.sleep(1)
    raise TimeoutError('CEF endpoint not available within the bounded discovery period')


def main() -> None:
    os.umask(0o077)
    evidence = Path(__file__).parents[4] / '.test-state/linux-runtime-v1/official-client-v1-20261031'
    approval = evidence / 'console-v7-approval.json'
    require_approval(approval)
    if os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError('Verified WSL user required')
    root = control.ROOT
    for name in (control.NAME, 'rhenium-steam-interactive-diagnostic-v2-20261031',
                 'rhenium-steam-interactive-foreground-v3-20261031',
                 'rhenium-steam-interactive-namespace-v4-20261031',
                 'rhenium-steam-interactive-shm-v5-20261031'):
        control.NAME = name
        if control.inspect()['State']['Running']:
            raise RuntimeError('Prior client still active')
    previous = json.loads((evidence / 'final-metadata-v6.json').read_text(encoding='utf-8'))
    client = root / 'home/.steam/debian-installation'
    if not (client / 'config/loginusers.vdf').is_file():
        raise RuntimeError('Reusable client state absent; no new login will be requested')
    for relative, expected in previous['client_files_sha256'].items():
        path = client / relative
        observed = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if observed != expected:
            raise RuntimeError('Sampled client bytes changed before interface discovery')
    attempt = root / 'attempts/console-v7'
    attempt.mkdir(parents=True, mode=0o700, exist_ok=False)
    (attempt / 'evidence').mkdir(mode=0o700)
    script = Path(__file__).with_name('console-launch-v7.sh')
    control.NAME, control.ROOT = NAME, attempt
    record = {'maximum_process_seconds': 1800, 'cef_control': True,
              'approval_sha256': hashlib.sha256(approval.read_bytes()).hexdigest(),
              'image_id': previous['image_id'],
              'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                  Path(__file__), script, Path(control.__file__), Path(shm_probe_v5.__file__),
                  Path(shm_probe_v5.namespace_probe_v4.__file__))}}
    with (attempt / 'evidence/request.json').open('x') as file:
        json.dump(record, file, indent=2)
    started = time.monotonic()
    stage = 'launch'
    try:
        identifier = control.docker(*shm_probe_v5.launch_args(root, script, NAME, previous['image_id']))
        print(json.dumps({'stage': 'owned_console_client_started', 'container_id': identifier}), flush=True)
        stage = 'read_only_interface_discovery'
        result = discover()
        with (attempt / 'evidence/interface-result.json').open('x') as file:
            json.dump(result, file, indent=2)
        print(json.dumps(result), flush=True)
        if result['login_target_present']:
            raise RuntimeError('Login UI detected; do not authenticate again')
        remaining = max(1, 1800 - int(time.monotonic() - started))
        stage = 'bounded_supervision'
        print(json.dumps(control.supervise(remaining)), flush=True)
    except Exception as error:
        # Fail closed and stop this owned client; never relay raw client response content.
        cleanup = 'not_confirmed'
        try:
            if control.inspect()['State']['Running']:
                control.stop()
            cleanup = 'owned_container_stopped'
        except Exception:
            pass
        with (attempt / 'evidence/failure.json').open('x') as file:
            json.dump({'stage': stage, 'error_type': type(error).__name__, 'cleanup': cleanup,
                       'authentication_validated': False, 'acquisition_executed': False}, file, indent=2)
        raise RuntimeError('Console capability probe incomplete; owned cleanup requested') from None


if __name__ == '__main__':
    main()
