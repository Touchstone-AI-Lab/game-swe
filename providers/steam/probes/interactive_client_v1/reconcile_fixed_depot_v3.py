"""Verify the unique discovered owned depot, preserving v1/v2 diagnostic failures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import acquire_fixed_depot_v1 as acquisition
import console_probe_v7 as probe
import control


def main() -> None:
    control.NAME = probe.NAME
    control.inspect()
    evidence = Path(__file__).parents[4] / '.test-state/linux-runtime-v1'
    location_file = evidence / 'owned-depot-location-v8.json'
    locations = json.loads(location_file.read_text())['matches']
    if len(locations) != 1:
        raise RuntimeError('Source location is ambiguous')
    relative = Path(locations[0]['relative_file'])
    expected_tail = ('steamapps', 'content', 'app_2379780', 'depot_2379781', 'Balatro.exe')
    if relative.is_absolute() or '..' in relative.parts or relative.parts[-5:] != expected_tail:
        raise RuntimeError('Source is outside the observed fixed depot layout')
    home = acquisition.ROOT / 'home'
    source = home / relative.parent
    verified = acquisition.verify_source(source, home)
    request_file = acquisition.ATTEMPT / 'request.json'
    completion_file = acquisition.ATTEMPT / 'completion-observation.json'
    request = json.loads(request_file.read_text())
    observed = json.loads(completion_file.read_text())['signal']
    if (request['app_id'] != 2379780 or request['depot_id'] != 2379781
            or request['manifest_id'] != acquisition.MANIFEST
            or observed['manifest'] != acquisition.MANIFEST
            or observed['phase'] != 'console_complete' or observed['completeEvents'] != 1
            or observed['failureEvents'] != 0):
        raise RuntimeError('Source acquisition identity is not confirmed')
    steam_pids = control.docker('exec', probe.NAME, 'pgrep', '-x', 'steam').splitlines()
    if len(steam_pids) != 1 or not steam_pids[0].isdecimal():
        raise RuntimeError('Steam process identity is ambiguous')
    cwd = control.docker('exec', probe.NAME, 'readlink', f'/proc/{steam_pids[0]}/cwd')
    result = {'schema': 3, 'recorded_utc': acquisition.stamp(),
        'status': 'verified_acquisition_after_readonly_reconciliation',
        'app_id': 2379780, 'depot_id': 2379781, 'manifest_id': acquisition.MANIFEST, 'build_id': 17459173,
        'source_relative_to_owned_home': source.relative_to(home).as_posix(),
        'source_verified': verified, 'command_count': 1, 'command_resent': False,
        'observed_steam_cwd_relative_to_container_home': str(Path(cwd).relative_to('/home/steamprobe')),
        'original_probe_status': 'incomplete', 'completion_path_string_retained': False,
        'diagnosis': 'Actual depot is under ubuntu12_32; the original path assumption was incorrect',
        'provenance_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (request_file, completion_file, location_file)},
        'managed_prepare_completed': False}
    with (acquisition.ATTEMPT / 'reconciled-source-v3.json').open('x', encoding='utf-8') as file:
        json.dump(result, file, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
