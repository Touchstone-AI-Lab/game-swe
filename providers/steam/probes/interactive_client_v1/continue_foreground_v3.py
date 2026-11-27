"""Approved deadline handoff for the SAME client; never starts/restarts a container."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import signal
import subprocess
from pathlib import Path

import control


def main() -> None:
    os.umask(0o077)
    root = control.ROOT
    evidence = Path(__file__).parents[4] / '.test-state/linux-runtime-v1/official-client-v1-20261031'
    approval = evidence / 'foreground-v3-extension-approval.json'
    decision = json.loads(approval.read_text(encoding='utf-8'))
    if decision.get('approved') is not True or decision.get('maximum_total_seconds') != 2700:
        raise RuntimeError('Explicit 45-minute approval required')
    control.NAME = 'rhenium-steam-interactive-foreground-v3-20261031'
    obj = control.inspect()
    if not obj['State']['Running']:
        raise RuntimeError('Client has already exited; no retry permitted')
    started = datetime.datetime.fromisoformat(obj['State']['StartedAt'].replace('Z', '+00:00'))
    elapsed = (datetime.datetime.now(datetime.UTC) - started).total_seconds()
    remaining = math.floor(2700 - elapsed)
    if not 1 <= remaining <= 2700:
        raise RuntimeError('Extended total deadline already expired')
    original = str(Path(__file__).with_name('resume_foreground_v3.py'))
    expected_parent = ['/home/psy/balatro-linux-v1/venv/bin/python', original]
    pattern = '^' + re.escape(' '.join(expected_parent)) + '$'
    matches = subprocess.check_output(['/usr/bin/pgrep', '-f', pattern], text=True, timeout=5).split()
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one original supervisor')
    parent = int(matches[0])
    def argv(pid: int) -> list[str]:
        return Path(f'/proc/{pid}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    if argv(parent) != expected_parent:
        raise RuntimeError('Supervisor identity mismatch')
    children = [int(pid) for pid in Path(f'/proc/{parent}/task/{parent}/children').read_text().split()]
    waiters = [pid for pid in children if argv(pid) == ['docker', 'wait', control.NAME]]
    if len(waiters) != 1:
        raise RuntimeError('Expected exactly one owned Docker wait subprocess')
    child = waiters[0]
    attempt = root / 'attempts/foreground-v3'
    request = {'same_container_id': obj['Id'], 'elapsed_seconds': elapsed,
               'remaining_seconds': remaining, 'maximum_total_seconds': 2700,
               'old_supervisor_pid': parent, 'old_wait_pid': child,
               'approval_sha256': hashlib.sha256(approval.read_bytes()).hexdigest(),
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'control_sha256': hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest(),
               'client_started_or_restarted': False}
    with (attempt / 'evidence/deadline-handoff-request.json').open('x') as file:
        json.dump(request, file, indent=2)
    # This process is already the new foreground WSL owner. Terminate ONLY the
    # old `docker wait` observer; its parent exits on the nonzero wait result.
    # No signal goes to the client/container and there is no WSL lifetime gap.
    if argv(child) != ['docker', 'wait', control.NAME]:
        raise RuntimeError('Wait subprocess identity changed')
    os.kill(child, signal.SIGTERM)
    control.ROOT = attempt
    print(json.dumps({'stage': 'same_client_deadline_handoff', 'remaining_seconds': remaining}), flush=True)
    print(json.dumps(control.supervise(remaining)), flush=True)


if __name__ == '__main__':
    main()
