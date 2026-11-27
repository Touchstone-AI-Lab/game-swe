import argparse
import base64
import json
from pathlib import Path

CASES = {'player-plain': ('control', {'block': 13, 'stacks': 'B:4;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'player-specific': ('control', {'block': 18, 'stacks': 'A:5;B:4;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': ''}), 'player-zero-specific': ('targeting', {'block': 19, 'stacks': 'A:3;B:7;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': ''}), 'player-refund': ('settlement', {'block': 17, 'stacks': 'B:4;C:9;plain:4;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'player-nested-loss': ('settlement', {'block': 11, 'stacks': 'B:2;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'player-nested-specific': ('settlement', {'block': 11, 'stacks': 'B:2;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'player-cross-owner': ('settlement', {'block': 16, 'stacks': 'B:7;C:9;', 'otherBlock': 8, 'otherStacks': 'B:8;', 'hpLost': 0, 'events': 'A/0;'}), 'player-attenuate': ('control', {'block': 9, 'stacks': 'C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/13;B/0;'}), 'player-cap-multiple': ('capacity', {'block': 999, 'stacks': 'A:700;B:299;', 'events': ''}), 'player-cap-full': ('capacity', {'block': 999, 'stacks': 'A:999;', 'events': ''}), 'player-cap-plain': ('capacity', {'block': 999, 'stacks': 'A:700;plain:299;', 'events': ''}), 'player-cap-loss': ('capacity', {'block': 991, 'stacks': 'A:692;B:299;', 'events': ''}), 'player-zero-gain': ('capacity', {'block': 7, 'stacks': 'A:7;', 'events': ''}), 'monster-plain': ('control', {'block': 13, 'stacks': 'B:4;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'monster-specific': ('control', {'block': 18, 'stacks': 'A:5;B:4;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': ''}), 'monster-zero-specific': ('targeting', {'block': 19, 'stacks': 'A:3;B:7;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': ''}), 'monster-refund': ('settlement', {'block': 17, 'stacks': 'B:4;C:9;plain:4;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'monster-nested-loss': ('settlement', {'block': 11, 'stacks': 'B:2;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'monster-nested-specific': ('settlement', {'block': 11, 'stacks': 'B:2;C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/3;'}), 'monster-cross-owner': ('settlement', {'block': 16, 'stacks': 'B:7;C:9;', 'otherBlock': 8, 'otherStacks': 'B:8;', 'hpLost': 0, 'events': 'A/0;'}), 'monster-attenuate': ('control', {'block': 9, 'stacks': 'C:9;', 'otherBlock': 10, 'otherStacks': 'B:10;', 'hpLost': 0, 'events': 'A/13;B/0;'}), 'monster-cap-multiple': ('capacity', {'block': 999, 'stacks': 'A:700;B:299;', 'events': ''}), 'monster-cap-full': ('capacity', {'block': 999, 'stacks': 'A:999;', 'events': ''}), 'monster-cap-plain': ('capacity', {'block': 999, 'stacks': 'A:700;plain:299;', 'events': ''}), 'monster-cap-loss': ('capacity', {'block': 991, 'stacks': 'A:692;B:299;', 'events': ''}), 'monster-zero-gain': ('capacity', {'block': 7, 'stacks': 'A:7;', 'events': ''})}

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
