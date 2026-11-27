"""Read-only reconciliation of v1's incorrect Steam working-directory assumption."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import acquire_fixed_depot_v1 as acquisition
import console_probe_v7 as probe
import control


def owned_source(home: Path, cwd: str) -> Path:
    relative = Path(cwd).relative_to('/home/steamprobe')
    if '..' in relative.parts:
        raise ValueError('Unsafe Steam working directory')
    result = home / relative / 'steamapps/content/app_2379780/depot_2379781'
    if not result.resolve().is_relative_to(home.resolve()):
        raise ValueError('Depot escapes the owned home')
    return result


def main() -> None:
    control.NAME = probe.NAME
    obj = control.inspect()
    if not obj['State']['Running']:
        raise RuntimeError('Current process evidence is required')
    request_path = acquisition.ATTEMPT / 'request.json'
    observed_path = acquisition.ATTEMPT / 'completion-observation.json'
    request = json.loads(request_path.read_text())
    observed = json.loads(observed_path.read_text())['signal']
    if (request['manifest_id'] != acquisition.MANIFEST or observed['manifest'] != acquisition.MANIFEST
            or observed['phase'] != 'console_complete' or observed['completeEvents'] != 1
            or observed['failureEvents'] != 0 or observed['pathMatches'] is not False):
        raise RuntimeError('This reconciliation does not apply to the recorded observation')
    pids = control.docker('exec', probe.NAME, 'pgrep', '-x', 'steam').splitlines()
    if len(pids) != 1 or not pids[0].isdecimal():
        raise RuntimeError('Steam process identity is ambiguous')
    cwd = control.docker('exec', probe.NAME, 'readlink', f'/proc/{pids[0]}/cwd')
    home = acquisition.ROOT / 'home'
    source = owned_source(home, cwd)
    verified = acquisition.verify_source(source, home)
    result = {'schema': 2, 'recorded_utc': acquisition.stamp(),
        'status': 'verified_acquisition_after_readonly_reconciliation',
        'app_id': request['app_id'], 'depot_id': request['depot_id'],
        'manifest_id': request['manifest_id'], 'build_id': request['build_id'],
        'source_relative_to_owned_home': source.relative_to(home).as_posix(),
        'source_verified': verified, 'command_count': 1, 'command_resent': False,
        'original_probe_status': 'incomplete',
        'diagnosis': 'Steam downloads relative to its actual ubuntu12_32 working directory',
        'completion_path_string_retained': False,
        'provenance_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (request_path, observed_path)},
        'managed_prepare_completed': False}
    with (acquisition.ATTEMPT / 'reconciled-source-v2.json').open('x', encoding='utf-8') as file:
        json.dump(result, file, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
