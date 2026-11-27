"""Prepared review artifact. Do not execute without approval for one extra run."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import control


def main() -> None:
    os.umask(0o077)
    root = control.ROOT
    if os.getuid() != 1000 or os.getgid() != 1000:
        raise SystemExit('Verified WSL user required')
    for name in (control.NAME, 'rhenium-steam-interactive-diagnostic-v2-20261031'):
        control.NAME = name
        if control.inspect()['State']['Running']:
            raise RuntimeError('Prior client must have exited')
    if (root / 'home/.steam/debian-installation/config/loginusers.vdf').exists():
        raise RuntimeError('Unexpected account marker; do not repeat authentication')
    attempt = root / 'attempts/foreground-v3'
    attempt.mkdir(mode=0o700, parents=True, exist_ok=False)
    (attempt / 'evidence').mkdir(mode=0o700)
    script = Path(__file__).with_name('resume-launch-v3.sh')
    image_id = json.loads((root / 'evidence/preparation-result.json').read_text())['image_id']
    control.NAME = 'rhenium-steam-interactive-foreground-v3-20261031'
    control.ROOT = attempt
    with (attempt / 'evidence/request.json').open('x') as file:
        json.dump({'image_id': image_id, 'deadline_seconds': 900,
                   'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
                   'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'control_sha256': hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest()}, file)
    identifier = control.docker(
        'run', '--detach', '--name', control.NAME,
        '--label', 'org.rhenium.probe=steam-interactive-v1-20261031',
        '--user', '1000:1000', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '512',
        '--memory', '3g', '--cpus', '2', '--network', 'bridge',
        '--mount', f'type=bind,src={root / "home"},dst=/home/steamprobe',
        '--mount', 'type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly',
        '--mount', f'type=bind,src={script},dst=/opt/steam-probe/resume.sh,readonly',
        '--env', 'HOME=/home/steamprobe', '--env', 'DISPLAY=:0',
        '--env', 'XDG_RUNTIME_DIR=/tmp/steam-probe-runtime',
        '--env', 'LIBGL_ALWAYS_SOFTWARE=1', '--env', 'GDK_BACKEND=x11',
        '--env', 'SDL_VIDEODRIVER=x11', '--env', 'GTK_A11Y=none',
        '--entrypoint', '/bin/bash', image_id, '/opt/steam-probe/resume.sh',
    )
    print(json.dumps({'stage': 'foreground_supervision_started', 'container_id': identifier}), flush=True)
    print(json.dumps(control.supervise()), flush=True)


if __name__ == '__main__':
    main()
