"""Prepared permission experiment. Explicit approval receipt is mandatory."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import control


def launch_args(root: Path, script: Path, name: str, image_id: str) -> tuple[str, ...]:
    return (
        'run', '--detach', '--name', name,
        '--label', 'org.rhenium.probe=steam-interactive-v1-20261031',
        '--user', '1000:1000', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--security-opt', 'seccomp=unconfined',
        '--pids-limit', '512', '--memory', '3g', '--cpus', '2', '--network', 'bridge',
        '--mount', f'type=bind,src={root / "home"},dst=/home/steamprobe',
        '--mount', 'type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly',
        '--mount', f'type=bind,src={script},dst=/opt/steam-probe/namespace.sh,readonly',
        '--env', 'HOME=/home/steamprobe', '--env', 'DISPLAY=:0',
        '--env', 'XDG_RUNTIME_DIR=/tmp/steam-probe-runtime',
        '--env', 'LIBGL_ALWAYS_SOFTWARE=1', '--env', 'GDK_BACKEND=x11',
        '--env', 'SDL_VIDEODRIVER=x11', '--env', 'GTK_A11Y=none',
        '--entrypoint', '/bin/bash', image_id, '/opt/steam-probe/namespace.sh',
    )


def require_approval(path: Path) -> dict[str, object]:
    decision: dict[str, object] = json.loads(path.read_text(encoding='utf-8'))
    if (decision.get('approved') is not True or decision.get('seccomp') != 'unconfined'
            or decision.get('maximum_attempts') != 1 or decision.get('maximum_seconds') != 900):
        raise RuntimeError('Explicit single-attempt namespace permission approval required')
    return decision


def main() -> None:
    os.umask(0o077)
    evidence = Path(__file__).parents[4] / '.test-state/linux-runtime-v1/official-client-v1-20261031'
    approval = evidence / 'namespace-v4-approval.json'
    require_approval(approval)
    if os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError('Verified WSL user required')
    root = control.ROOT
    for name in (control.NAME, 'rhenium-steam-interactive-diagnostic-v2-20261031',
                 'rhenium-steam-interactive-foreground-v3-20261031'):
        control.NAME = name
        if control.inspect()['State']['Running']:
            raise RuntimeError('Prior client still active')
    if (root / 'home/.steam/debian-installation/config/loginusers.vdf').exists():
        raise RuntimeError('Unexpected account marker; do not repeat authentication')
    attempt = root / 'attempts/namespace-v4'
    attempt.mkdir(mode=0o700, parents=True, exist_ok=False)
    (attempt / 'evidence').mkdir(mode=0o700)
    script = Path(__file__).with_name('namespace-launch-v4.sh')
    image_id = json.loads((root / 'evidence/preparation-result.json').read_text())['image_id']
    control.NAME = 'rhenium-steam-interactive-namespace-v4-20261031'
    control.ROOT = attempt
    request = {'image_id': image_id, 'maximum_seconds': 900, 'seccomp': 'unconfined',
               'approval_sha256': hashlib.sha256(approval.read_bytes()).hexdigest(),
               'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'launch_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
               'control_sha256': hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest()}
    with (attempt / 'evidence/request.json').open('x') as file:
        json.dump(request, file, indent=2)
    identifier = control.docker(*launch_args(root, script, control.NAME, image_id))
    print(json.dumps({'stage': 'namespace_permission_probe_started',
                      'container_id': identifier, 'seccomp': 'unconfined'}), flush=True)
    print(json.dumps(control.supervise()), flush=True)


if __name__ == '__main__':
    main()
