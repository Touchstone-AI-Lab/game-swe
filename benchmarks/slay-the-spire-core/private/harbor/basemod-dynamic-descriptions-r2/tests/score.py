import argparse
import base64
import json
from pathlib import Path

CASES = {'direct-control': ('control', {'text': 'two', 'calls': 1}), 'rightmost-control': ('control', {'text': 'two', 'calls': 1}), 'divisible-control': ('control', {'text': 'multiple', 'calls': 1}), 'suffix-negative-control': ('control', {'text': 'other', 'calls': 1}), 'empty-control': ('control', {'text': '', 'calls': 1}), 'repeat-control': ('control', {'text': 'hahaha', 'calls': 1}), 'zero-repeat-control': ('control', {'text': '', 'calls': 1}), 'negative-control': ('control', {'text': 'negative', 'calls': 1}), 'unmarked-control': ('control', {'text': '{!probe:count!|2=two|@=other}', 'calls': 0}), 'unknown-control': ('control', {'text': '', 'calls': 0}), 'suffix-two': ('numeric', {'text': 'ending', 'calls': 1}), 'suffix-width': ('numeric', {'text': 'ending', 'calls': 1}), 'suffix-leading-width': ('control', {'text': 'short', 'calls': 1}), 'suffix-minimum': ('numeric', {'text': 'ending', 'calls': 1}), 'zero-divisor': ('numeric', {'text': 'safe', 'calls': 1}), 'zero-zero-divisor': ('numeric', {'text': 'safe', 'calls': 1}), 'fraction-operand': ('numeric', {'text': 'safe', 'calls': 1}), 'large-operand': ('numeric', {'text': 'safe', 'calls': 1}), 'decimal-leading-zero': ('numeric', {'text': 'eight', 'calls': 1}), 'literal-dollar': ('literal', {'text': 'cost$5', 'calls': 1}), 'literal-backslash': ('literal', {'text': 'C:\\save', 'calls': 1}), 'payload-equals': ('literal', {'text': 'x=y=z', 'calls': 1}), 'escaped-pipe': ('literal', {'text': 'a|b', 'calls': 1}), 'escaped-braces': ('literal', {'text': '{plain}', 'calls': 1}), 'escaped-backslash': ('literal', {'text': 'a\\b', 'calls': 1}), 'escaped-open': ('literal', {'text': '{!probe:count!|2=two|@=other}', 'calls': 0}), 'nested-selected': ('nested', {'text': 'inner', 'calls': 1}), 'nested-fallback': ('nested', {'text': 'fallback', 'calls': 1}), 'nested-repeat': ('nested', {'text': 'xx', 'calls': 1}), 'inactive-lazy': ('nested', {'text': 'safe', 'calls': 1}), 'overridden-lazy': ('nested', {'text': 'safe', 'calls': 1}), 'zero-repeat-lazy': ('nested', {'text': '', 'calls': 1}), 'repeated-key': ('snapshot', {'text': 'firstsecond', 'calls': 1}), 'cn-direct-control': ('control', {'text': 'two', 'calls': 1}), 'cn-nested': ('nested', {'text': 'inner', 'calls': 1}), 'cn-suffix': ('numeric', {'text': 'ending', 'calls': 1}), 'raw-refresh': ('snapshot', {'before': 'one', 'after': 'two', 'initializedCalls': 1, 'renderCalls': 1}), 'generated-refresh': ('refresh', {'before': 'plainone', 'after': 'plaintwo', 'initializedCalls': 1, 'renderCalls': 1}), 'unmark': ('refresh', {'calls': 0, 'text': '{!probe:count!|2=two|@=other}'}), 'coherent-initialization': ('snapshot', {'calls': 1, 'text': 'firstfirst'}), 'ticking-render': ('snapshot', {'calls': 2, 'before': 'firstfirst', 'after': 'secondsecond'}), 'independent-cards': ('control', {'left': 'left', 'right': 'right'}), 'nested-card': ('snapshot', {'left': 'leftleft', 'right': 'right', 'leftReads': 1, 'rightReads': 1}), 'generated-rewrite': ('refresh', {'before': 'plainold', 'after': 'plainnew'}), 'subscriber-refresh': ('refresh', {'before': 'plainone', 'after': 'plaintwo'})}

def score(text, nonce, exit_code):
    observations, malformed = {}, not nonce
    for line in text.splitlines():
        if not line.startswith(nonce + '|'):
            malformed = True
            continue
        pieces = line[len(nonce) + 1:].split(',')
        fields = {}
        for field in pieces[1:]:
            if '=' not in field:
                malformed = True
                continue
            key, value = field.split('=', 1)
            if key in fields:
                malformed = True
            if key in {'text','before','after','left','right'}:
                try: value = ''.join(base64.b64decode(value, validate=True).decode('utf-8').split())
                except (ValueError, UnicodeDecodeError): malformed = True
            fields[key] = value
        key = pieces[0] + ':' + fields.get('id', '')
        if key in observations:
            malformed = True
        observations[key] = fields
    expected = {'engine:', 'completed=true:'} | {'case:' + name for name in CASES}
    complete = not malformed and set(observations) == expected and exit_code == 0
    cases = [{'id': 'engine', 'group': 'control', 'passed': observations.get('engine:', {}).get('gl') == 'true'}]
    for name, (group, fields) in CASES.items():
        observed = observations.get('case:' + name, {})
        passed = observed.get('error') == 'none' and all(observed.get(k) == str(v) for k, v in fields.items())
        cases.append({'id': name, 'group': group, 'passed': passed})
    passed = sum(c['passed'] for c in cases)
    return {'complete': complete, 'passed': passed, 'failed': len(cases) - passed, 'expected': len(cases),
        'reward': int(complete and passed == len(cases)), 'entrypoint_exit': exit_code, 'cases': cases}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['observations', 'nonce-file', 'exit-file', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = score(args.observations.read_text() if args.observations.exists() else '', args.nonce_file.read_text().strip(), int(args.exit_file.read_text()))
    args.output.mkdir(exist_ok=True, parents=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    (args.output / 'reward.txt').write_text(str(result['reward']) + '\n')
    (args.output / 'summary.txt').write_text(f"complete={result['complete']} passed={result['passed']} failed={result['failed']} expected={result['expected']}\n")
