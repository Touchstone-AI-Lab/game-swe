from __future__ import annotations
from poc.checks import check
from scripts.audit import sha, write
from poc.rpc import ProtocolError
from tasks.durable_charge.load_diag_v1.probe import collect

REQUIRED = ('actions', 'saved_file', 'new_process', 'restored', 'continued_play', 'file_unchanged')


def stable(state):
    return {key: state[key] for key in ('state', 'seed', 'round', 'hand')}


def run_probe(session, checks):
    client = session.client
    client.wait(lambda s: s['state'] == 'MENU')
    client.action('start', {'deck': 'RED', 'stake': 'WHITE', 'seed': 'POC2026A'})
    client.wait(lambda s: s['state'] == 'BLIND_SELECT')
    client.action('select'); before = client.wait(lambda s: s['state'] == 'SELECTING_HAND')
    client.action('discard', {'cards': [0]}); client.wait(lambda s: s['state'] == 'SELECTING_HAND')
    client.action('play', {'cards': [0]}); saved = client.wait(lambda s: s['state'] == 'SELECTING_HAND')
    check(checks, 'actions', [saved['round']['hands_played']-before['round']['hands_played'],
                            saved['round']['discards_used']-before['round']['discards_used']], [1, 1])
    file = session.runtime.directory / 'checkpoint.jkr'
    response = client.action('save', {'path': str(file)})
    digest = sha(file)
    write(session.runtime.directory / 'checkpoint-evidence.json',
          {'sha256_before': digest, 'bytes': file.stat().st_size, 'save_response': response})
    if response.get('path') != str(file): raise ProtocolError('Save response path mismatch')
    check(checks, 'saved_file', {'success': response.get('success'), 'nonempty': file.stat().st_size > 0},
          {'success': True, 'nonempty': True})
    first = session.runtime
    client = session.restart()
    check(checks, 'new_process', {'different_pid': first.process.pid != session.runtime.process.pid,
                                'different_nonce': first.nonce != session.runtime.nonce,
                                'first_exited': first.process.returncode == 0,
                                'different_save_dir': first.directory != session.runtime.directory},
          {'different_pid': True, 'different_nonce': True, 'first_exited': True, 'different_save_dir': True})
    # Fixed load from a virgin MENU triggers an unhandled first-continue unlock.
    # Prime through the public, real start lifecycle; never write saved state or locks.
    client.wait(lambda s: s['state'] == 'MENU')
    client.action('start', {'deck': 'BLUE', 'stake': 'WHITE', 'seed': 'LOADPREP'})
    primed = client.wait(lambda s: s['state'] == 'BLIND_SELECT')
    if primed['seed'] != 'LOADPREP' or primed['seed'] == saved['seed']:
        raise ProtocolError('Independent load initialization seed not established')
    readiness = client.wait(lambda d:
        d['state']['state_name'] == 'BLIND_SELECT'
        and d['state']['state_complete'] == {'type': 'boolean', 'value': True}
        and d['state']['locked'] == {'type': 'boolean', 'value': False}
        and d['state']['paused'] == {'type': 'boolean', 'value': False}
        and d['state']['overlay']['type'] == 'nil'
        and d['state']['screenwipe']['type'] == 'nil'
        and d['state']['locks'].get('load', {}).get('value') is not True,
        method='poc.load_diagnostic', timeout=30)
    write(session.runtime.directory / 'load-entry-readiness.json', readiness)
    write(session.runtime.directory / 'load-entry-evidence.json',
          {'policy': 'public-start-blue-LOADPREP-quiescent-before-single-load-v2',
           'initial_state': stable(primed), 'expected_restored': stable(saved),
           'first_save_dir': first.metadata['save_dir'],
           'second_save_dir': session.runtime.metadata['save_dir']})
    if first.metadata['save_dir'] == session.runtime.metadata['save_dir']:
        raise ProtocolError('Save directory reused')
    response = client.action('load', {'path': str(file)})
    write(session.runtime.directory / 'load-response-evidence.json', response)
    if response.get('path') != str(file): raise ProtocolError('Load response path mismatch')
    if response.get('success') is not True: raise RuntimeError('Game load did not succeed')
    restored = client.wait(lambda s: s['state'] == 'SELECTING_HAND')
    check(checks, 'restored', stable(restored), stable(saved))
    client.action('play', {'cards': [0]})
    after = client.wait(lambda s: s['state'] in {'SELECTING_HAND', 'ROUND_EVAL'})
    check(checks, 'continued_play', after['round']['hands_played']-restored['round']['hands_played'], 1)
    after_digest = sha(file)
    check(checks, 'file_unchanged', after_digest, digest)
    write(session.runtime.directory / 'checkpoint-after.json',
          {'sha256_before': digest, 'sha256_after': after_digest, 'bytes': file.stat().st_size})


def evaluate(session, checks):
    try:
        run_probe(session, checks)
    finally:
        collect(session)
