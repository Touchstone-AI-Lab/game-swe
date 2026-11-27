"""Single approved fixed-depot capability probe through the owned Steam client.

This is provider development evidence, not yet `rhenium runtime prepare` support.
No operator-controlled commands, account fields, or credential extraction.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import console_probe_v7 as probe
import control
from cef_transport_v1 import CEF

ROOT = Path('/home/psy/balatro-linux-v1/state/official-client-v1-20261031')
ATTEMPT = ROOT / 'attempts/console-v7/fixed-depot-v1'
SOURCE = ROOT / 'home/.steam/debian-installation/steamapps/content/app_2379780/depot_2379781'
MANIFEST = '3512319404653808464'
EXPECTED = '0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47'
COMMAND = 'download_depot 2379780 2379781 3512319404653808464'
LOGIN = '''new Promise(resolve=>{
  let handle;let ended=false;
  const finish=value=>{if(ended)return;ended=true;clearTimeout(timer);
    queueMicrotask(()=>handle?.unregister());resolve(value)};
  const timer=setTimeout(()=>finish({received:false}),5000);
  handle=SteamClient.User.RegisterForLoginStateChange((account,state,result)=>finish({received:true,state:Number(state),result:Number(result)}));
})'''
# The installed client supplies {spew,spew_type}. Its compiled completion message
# is: Depot download complete : "%s" (manifest %llu). Manifest stays a string.
START = r'''(()=>{
  if(window.__rheniumDepotV1)throw new Error('Already attempted');
  const state={phase:'waiting',completeEvents:0,failureEvents:0,manifest:null,pathMatches:false};
  window.__rheniumDepotV1=state;
  let handle;
  const finish=()=>{clearTimeout(timer);queueMicrotask(()=>handle?.unregister())};
  const timer=setTimeout(()=>{if(state.phase==='waiting'){state.phase='observer_timeout';finish()}},900000);
  handle=SteamClient.Console.RegisterForSpewOutput(event=>{
    if(typeof event.spew!=='string'||event.spew.length>4096)return;
    for(const line of event.spew.split('\n')){
      const complete=line.trim().match(/^Depot download complete : "([^"]+)" \(manifest ([0-9]+)\)\s*$/);
      if(complete){
        state.completeEvents++;state.manifest=complete[2];
        state.pathMatches=complete[1]==='/home/steamprobe/.steam/debian-installation/steamapps/content/app_2379780/depot_2379781';
        state.phase='console_complete';finish();
      }else if(line.trim().startsWith('Depot download failed :')){
        state.failureEvents++;state.phase='download_failed';finish();
      }
    }
  });
  SteamClient.Console.ExecCommand('download_depot 2379780 2379781 3512319404653808464');
  return {issued:true};
})()'''
POLL = '''(()=>{const s=window.__rheniumDepotV1;if(!s)return null;return {
 phase:s.phase,completeEvents:s.completeEvents,failureEvents:s.failureEvents,
 manifest:s.manifest,pathMatches:s.pathMatches}})()'''


def stamp() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def record(name: str, data: dict[str, Any]) -> None:
    with (ATTEMPT / name).open('x', encoding='utf-8') as file:
        json.dump(data, file, indent=2)


def completion_matches(signal: Any) -> bool:
    return isinstance(signal, dict) and (
        signal.get('phase') == 'console_complete'
        and signal.get('completeEvents') == 1 and signal.get('failureEvents') == 0
        and signal.get('manifest') == MANIFEST and signal.get('pathMatches') is True
    )


def verify_source(source: Path, owner: Path, expected: str = EXPECTED) -> dict[str, Any]:
    if not source.resolve().is_relative_to(owner.resolve()):
        raise RuntimeError('Source escaped the provider-owned home')
    target = source / 'Balatro.exe'
    if target.is_symlink() or not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError('Expected game file missing or unsafe')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError('Pinned game hash mismatch')
    return {'expected_file': 'Balatro.exe', 'bytes': target.stat().st_size, 'sha256': digest}


def main() -> None:
    control.NAME = probe.NAME
    obj = control.inspect()
    started = dt.datetime.fromisoformat(obj['State']['StartedAt'].replace('Z', '+00:00'))
    remaining = min(900, int(1800-(dt.datetime.now(dt.UTC)-started).total_seconds()-120))
    if not obj['State']['Running'] or remaining < 180 or obj['HostConfig'].get('PortBindings'):
        raise RuntimeError('No bounded owned preparation process available')
    if SOURCE.exists():
        raise RuntimeError('Pre-existing depot requires read-only reconciliation, not a resend')
    assert probe.listener_ready(control.docker('exec', probe.NAME, 'cat', '/proc/net/tcp'),
                                control.docker('exec', probe.NAME, 'cat', '/proc/net/tcp6'))
    raw = control.docker('exec', probe.NAME, 'curl', '--noproxy', '*', '--silent', '--fail',
                         '--max-time', '5', '--max-filesize', '262144', 'http://127.0.0.1:8080/json/list')
    if probe.summarize_targets(raw)['login_target_present']:
        raise RuntimeError('Cached sign-in is not usable; no reauthentication')
    targets = [t for t in json.loads(raw) if t.get('title') in {'SP', 'SharedJSContext'}]
    if len(targets) != 1:
        raise RuntimeError('Native shared context is ambiguous')
    channel = CEF(urlsplit(targets[0]['webSocketDebuggerUrl']).path)
    attempted = False
    try:
        login = channel.evaluate(LOGIN, await_promise=True)
        if login != {'received': True, 'state': 5, 'result': 1}:
            raise RuntimeError('Current client login state not confirmed')
        ATTEMPT.mkdir(mode=0o700, exist_ok=False)
        record('request.json', {'schema': 1, 'recorded_utc': stamp(), 'app_id': 2379780,
            'depot_id': 2379781, 'manifest_id': MANIFEST, 'build_id': 17459173,
            'game_sha256': EXPECTED, 'login_state': login, 'maximum_wait_seconds': remaining,
            'controller_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'mutation_policy': 'one command only; uncertain requests are never resent'})
        attempted = True
        response = channel.evaluate(START)
        record('issued-response.json', {'recorded_utc': stamp(), 'response': response})
        if response != {'issued': True}:
            raise RuntimeError('Command issue response not confirmed')
        deadline = time.monotonic() + remaining
        last_notice = 0.0
        signal: Any = None
        while time.monotonic() < deadline:
            signal = channel.evaluate(POLL)
            if not isinstance(signal, dict):
                raise RuntimeError('Observer state missing')
            if signal.get('phase') != 'waiting':
                break
            if time.monotonic()-last_notice >= 10:
                files = list(SOURCE.glob('*')) if SOURCE.is_dir() else []
                print(json.dumps({'stage': 'fixed_depot_wait', 'elapsed_files': len(files),
                    'file_bytes': sum(p.stat().st_size for p in files if p.is_file())}), flush=True)
                last_notice = time.monotonic()
            time.sleep(1)
        record('completion-observation.json', {'recorded_utc': stamp(), 'signal': signal})
        if not completion_matches(signal):
            raise RuntimeError('Fixed-depot completion not confirmed')
        verified = verify_source(SOURCE, ROOT / 'home')
        record('verified-source.json', {'recorded_utc': stamp(), 'status': 'capability_passed',
            'manifest_id': MANIFEST, 'source_verified': verified, 'managed_prepare_completed': False})
        print(json.dumps({'stage': 'fixed_depot_verified', **verified}), flush=True)
    except Exception as error:
        if attempted:
            record('incomplete.json', {'recorded_utc': stamp(), 'status': 'incomplete',
                'error_type': type(error).__name__, 'command_may_have_run': True,
                'retry_allowed': False})
        raise RuntimeError('Fixed-depot probe incomplete; inspect sanitized receipts, never resend') from None
    finally:
        channel.close()


if __name__ == '__main__':
    main()
