from __future__ import annotations
from poc.checks import check
from scripts.audit import sha

REQUIRED = ('actions', 'saved_file', 'new_process', 'restored', 'continued_play', 'file_unchanged')


def stable(state):
    return {key: state[key] for key in ('state', 'seed', 'round', 'hand')}


def evaluate(session, checks):
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
    check(checks, 'saved_file', {'success': response.get('success'), 'nonempty': file.stat().st_size > 0},
          {'success': True, 'nonempty': True})
    first = session.runtime
    client = session.restart()
    check(checks, 'new_process', {'different_pid': first.process.pid != session.runtime.process.pid,
                                'different_nonce': first.nonce != session.runtime.nonce,
                                'first_exited': first.process.returncode == 0,
                                'different_save_dir': first.directory != session.runtime.directory},
          {'different_pid': True, 'different_nonce': True, 'first_exited': True, 'different_save_dir': True})
    response = client.action('load', {'path': str(file)})
    if response.get('success') is not True: raise RuntimeError('Game load did not succeed')
    restored = client.wait(lambda s: s['state'] == 'SELECTING_HAND')
    check(checks, 'restored', stable(restored), stable(saved))
    client.action('play', {'cards': [0]})
    after = client.wait(lambda s: s['state'] in {'SELECTING_HAND', 'ROUND_EVAL'})
    check(checks, 'continued_play', after['round']['hands_played']-restored['round']['hands_played'], 1)
    check(checks, 'file_unchanged', sha(file), digest)
