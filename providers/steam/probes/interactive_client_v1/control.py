"""Local bounded probe control. Never accepts credentials or reads client logs."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path('/home/psy/balatro-linux-v1/state/official-client-v1-20261031')
NAME = 'rhenium-steam-interactive-probe-v1-20261031'
ENV = {
    'PATH': '/usr/bin:/bin',
    'HOME': str(ROOT / 'control'),
    'DOCKER_HOST': 'unix:///var/run/docker.sock',
}


def docker(*args: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ['docker', *args], env=ENV, text=True, capture_output=True, timeout=timeout,
    )
    if result.returncode:
        # Never relay arbitrary CLI errors. No client output is requested here.
        raise RuntimeError(f'Docker {args[0]} failed (exit {result.returncode})')
    return result.stdout.strip()


def inspect() -> dict[str, Any]:
    obj: dict[str, Any] = json.loads(docker('inspect', NAME))[0]
    labels = obj['Config'].get('Labels') or {}
    if labels.get('org.rhenium.probe') != 'steam-interactive-v1-20261031':
        raise RuntimeError('Refusing an unowned container')
    return obj


def status() -> dict[str, Any]:
    obj = inspect()
    state = obj['State']
    return {
        'running': state['Running'], 'status': state['Status'],
        'exit_code': state['ExitCode'], 'oom_killed': state['OOMKilled'],
        'started_at': state['StartedAt'], 'finished_at': state['FinishedAt'],
        # Process basenames only: no command lines, window content or client logs.
        'process_names': sorted({line.split(maxsplit=1)[1]
                                 for line in docker('top', NAME, '-eo', 'pid,comm').splitlines()[1:]})
        if state['Running'] else [],
        'authenticated': 'not_validated',
    }


def start() -> dict[str, Any]:
    prepared = json.loads((ROOT / 'evidence/preparation-result.json').read_text())
    if prepared['status'] != 'image_built':
        raise RuntimeError('Image preparation did not pass')
    image_id = prepared['image_id']
    # Exclusive record prevents automatic retries after any ambiguous run result.
    with (ROOT / 'evidence/launch-request.json').open('x') as file:
        json.dump({'image_id': image_id,
                   'controller_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'requested_utc': datetime.datetime.now(datetime.UTC).isoformat()}, file)
    container_id = docker(
        'run', '--detach', '--name', NAME,
        '--label', 'org.rhenium.probe=steam-interactive-v1-20261031',
        '--user', '1000:1000', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '512',
        '--memory', '3g', '--cpus', '2', '--network', 'bridge',
        '--mount', f'type=bind,src={ROOT / "home"},dst=/home/steamprobe',
        '--mount', 'type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly',
        '--env', 'HOME=/home/steamprobe', '--env', 'DISPLAY=:0',
        '--env', 'XDG_RUNTIME_DIR=/tmp/steam-probe-runtime',
        '--env', 'LIBGL_ALWAYS_SOFTWARE=1', '--env', 'GDK_BACKEND=x11',
        '--env', 'SDL_VIDEODRIVER=x11', '--env', 'GTK_A11Y=none', image_id,
    )
    obj = inspect()
    host = obj['HostConfig']
    receipt = {
        'container_id': container_id, 'image_id': obj['Image'],
        'user': obj['Config']['User'], 'privileged': host['Privileged'],
        'cap_drop': host['CapDrop'], 'cap_add': host['CapAdd'],
        'security_opt': host['SecurityOpt'], 'devices': host['Devices'],
        'network_mode': host['NetworkMode'],
        'mounts': [{k: m[k] for k in ('Source', 'Destination', 'RW')}
                   for m in obj['Mounts']],
        'capture_enabled': False, 'authentication_validated': False,
    }
    with (ROOT / 'evidence/launch-result.json').open('x') as file:
        json.dump(receipt, file, indent=2)
    return receipt


def stop() -> dict[str, Any]:
    was_running = inspect()['State']['Running']
    ipc_result: int | str | None = None
    if was_running:
        # Official client's shutdown IPC, confined to this container and home.
        try:
            ipc_result = subprocess.run([
                'docker', 'exec', NAME,
                '/home/steamprobe/.steam/debian-installation/steam.sh', '-shutdown',
            ], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30, check=False).returncode
        except subprocess.TimeoutExpired:
            ipc_result = 'timeout'
        deadline = time.monotonic() + 30
        while inspect()['State']['Running'] and time.monotonic() < deadline:
            time.sleep(1)
    exited = not inspect()['State']['Running']
    if not exited:
        docker('stop', '--time', '15', NAME, timeout=25)
    result = status()
    result['running_before_shutdown'] = was_running
    result['shutdown_ipc_result'] = ipc_result
    result['normal_shutdown_confirmed'] = bool(was_running and ipc_result == 0 and exited
                                             and result['exit_code'] == 0)
    result['container_stop_required'] = not exited
    with (ROOT / 'evidence/shutdown-result.json').open('x') as file:
        json.dump(result, file, indent=2)
    return result


def supervise(timeout_seconds: int = 900) -> dict[str, Any]:
    """Keep the foreground WSL invocation alive for this owned client only."""
    if not 1 <= timeout_seconds <= 2700:
        raise ValueError('Supervision must be bounded to at most 2700 seconds')
    inspect()
    try:
        exit_text = docker('wait', NAME, timeout=timeout_seconds)
        if not exit_text.isdecimal():
            raise RuntimeError('Invalid container wait response')
        result = status()
        result['wait_exit_code'] = int(exit_text)
        result['deadline_exceeded'] = False
    except subprocess.TimeoutExpired:
        result = stop()
        result['deadline_exceeded'] = True
    with (ROOT / 'evidence/supervision-result.json').open('x') as file:
        json.dump(result, file, indent=2)
    return result


def start_session() -> dict[str, Any]:
    # Returning after `docker run --detach` lets WSL stop this distro and its
    # Docker service. This foreground wait is bounded and changes no host setting.
    print(json.dumps(start()), flush=True)
    return supervise()


if __name__ == '__main__':
    os.umask(0o077)
    if len(sys.argv) != 2 or sys.argv[1] not in {'start', 'status', 'stop'}:
        raise SystemExit('Usage: control.py {start|status|stop}')
    if sys.platform != 'linux' or os.getuid() != 1000 or os.getgid() != 1000:
        raise SystemExit('This probe requires the verified WSL uid/gid 1000')
    print(json.dumps({'start': start_session, 'status': status, 'stop': stop}[sys.argv[1]]()))
