"""Score visible native campfire outcomes, not private selection flags."""
import argparse
import json
from pathlib import Path

CASES = json.loads(Path(__file__).with_name('expectations.json').read_text())['cases']


def matches(row, expected):
    for key, value in expected.items():
        actual = row.get(key)
        if key in {'deck', 'target'}:
            if not isinstance(actual, str) or sorted(actual.split(';')) != sorted(value.split(';')):
                return False
        elif actual != value:
            return False
    return True


def score(text, nonce, exit_code):
    valid = bool(nonce) and exit_code == 0
    rows = {}
    engine = None
    completed = False
    for line in text.splitlines():
        if not line.startswith(nonce + '|'):
            valid = False
            continue
        payload = line[len(nonce) + 1:]
        if payload == 'completed=true':
            valid = valid and not completed
            completed = True
            continue
        if completed:
            valid = False
        try:
            tag, *parts = payload.split(',')
            fields = {}
            for part in parts:
                key, value = part.split('=', 1)
                if key in fields:
                    valid = False
                fields[key] = value
            if tag == 'engine':
                valid = valid and engine is None
                engine = fields
            elif tag == 'case':
                name = fields.pop('id')
                valid = valid and name in CASES and name not in rows
                rows[name] = fields
            else:
                valid = False
        except (KeyError, ValueError):
            valid = False
    complete = valid and completed and set(rows) == set(CASES) and engine is not None
    engine_ok = complete and engine.get('gl') == 'true'
    results = [{'id': 'engine', 'group': 'control', 'passed': engine_ok}]
    for name, case in CASES.items():
        results.append({'id': name, 'group': case['group'],
                        'passed': engine_ok and matches(rows.get(name, {}), case['expected'])})
    passed = sum(row['passed'] for row in results)
    return {'complete': complete, 'passed': passed, 'failed': len(results) - passed,
            'expected': len(results), 'reward': int(complete and passed == len(results)),
            'entrypoint_exit': exit_code, 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--observations', required=True, type=Path)
    parser.add_argument('--nonce-file', required=True, type=Path)
    parser.add_argument('--exit-file', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    text = args.observations.read_text() if args.observations.exists() else ''
    result = score(text, args.nonce_file.read_text().strip(), int(args.exit_file.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    (args.output / 'reward.txt').write_text(str(result['reward']) + '\n')
