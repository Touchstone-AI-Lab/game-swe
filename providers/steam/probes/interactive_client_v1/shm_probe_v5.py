"""One separately approved shared-memory comparison, using the existing controller."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import control
import namespace_probe_v4


def launch_args(root: Path, script: Path, name: str, image_id: str) -> tuple[str, ...]:
    args = list(namespace_probe_v4.launch_args(root, script, name, image_id))
    position = args.index('--pids-limit')
    args[position:position] = ['--shm-size', '1g']
    return tuple(args)


def require_approval(path: Path) -> dict[str, object]:
    decision: dict[str, object] = json.loads(path.read_text(encoding='utf-8'))
    if (decision.get('approved') is not True or decision.get('seccomp') != 'unconfined'
            or decision.get('maximum_attempts') != 1 or decision.get('maximum_seconds') != 900
            or decision.get('shm_size_bytes') != 1073741824):
        raise RuntimeError('Explicit single-attempt shared-memory comparison approval required')
    return decision


def main() -> None:
    os.umask(0o077)
    evidence = Path(__file__).parents[4] / '.test-state/linux-runtime-v1/official-client-v1-20261031'
    approval = evidence / 'shm-v5-approval.json'
    require_approval(approval)
    if os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError('Verified WSL user required')
    root = control.ROOT
    for name in (control.NAME, 'rhenium-steam-interactive-diagnostic-v2-20261031',
                 'rhenium-steam-interactive-foreground-v3-20261031',
                 'rhenium-steam-interactive-namespace-v4-20261031'):
        control.NAME = name
        if control.inspect()['State']['Running']:
            raise RuntimeError('Prior client still active')
    client = root / 'home/.steam/debian-installation'
    if (client / 'config/loginusers.vdf').exists():
        raise RuntimeError('Unexpected account marker; do not repeat authentication')
    previous_path = evidence / 'final-metadata-v5.json'
    previous = json.loads(previous_path.read_text())
    for relative, expected in previous['client_files_sha256'].items():
        path = client / relative
        observed = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if observed != expected:
            raise RuntimeError('Client bytes changed before the comparison')
    attempt = root / 'attempts/shm-v5'
    attempt.mkdir(mode=0o700, parents=True, exist_ok=False)
    (attempt / 'evidence').mkdir(mode=0o700)
    script = Path(__file__).with_name('shm-launch-v5.sh')
    image_id = previous['image_id']
    control.NAME = 'rhenium-steam-interactive-shm-v5-20261031'
    control.ROOT = attempt
    request = {'image_id': image_id, 'maximum_seconds': 900, 'shm_size_bytes': 1073741824,
               'seccomp': 'unconfined', 'approval_sha256': hashlib.sha256(approval.read_bytes()).hexdigest(),
               'previous_metadata_sha256': hashlib.sha256(previous_path.read_bytes()).hexdigest(),
               'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                   Path(__file__), script, Path(control.__file__), Path(namespace_probe_v4.__file__))}}
    with (attempt / 'evidence/request.json').open('x') as file:
        json.dump(request, file, indent=2)
    identifier = control.docker(*launch_args(root, script, control.NAME, image_id))
    print(json.dumps({'stage': 'shared_memory_comparison_started', 'container_id': identifier}), flush=True)
    print(json.dumps(control.supervise()), flush=True)


if __name__ == '__main__':
    main()
