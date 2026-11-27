"""Score frozen public-action observations; reject partial or malformed transcripts."""
import argparse
import json
from pathlib import Path

CASES = json.loads(Path(__file__).with_name('expectations.json').read_text())['cases']


def score(text, nonce, exit_code):
    rows = {}
    engine = False
    completed = False
    valid = bool(nonce) and exit_code == 0
    for line in text.splitlines():
        if not line.startswith(nonce + '|'):
            valid = False
            continue
        payload = line[len(nonce) + 1:]
        if payload.startswith('engine,'):
            if 'engine' in rows:
                valid = False
            rows['engine'] = {}
            fields = payload.split(',')[1:]
            engine = 'gl=true' in fields
        elif payload == 'completed=true':
            if completed:
                valid = False
            completed = True
        elif payload.startswith('case,'):
            if completed:
                valid = False
            fields = {}
            try:
                for value in payload.split(',')[1:]:
                    key, item = value.split('=', 1)
                    if key in fields:
                        valid = False
                    fields[key] = item
                name = fields.pop('id')
            except (ValueError, KeyError):
                valid = False
                continue
            if name not in CASES or name in rows:
                valid = False
            rows[name] = fields
        else:
            valid = False
    complete = valid and completed and set(rows) == {'engine', *CASES}
    results = [{'id': 'engine', 'group': 'control', 'passed': engine and complete}]
    for name, case in CASES.items():
        actual = rows.get(name, {})
        passed = complete and all(actual.get(key) == value for key, value in case['expected'].items())
        results.append({'id': name, 'group': case['group'], 'passed': passed})
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
