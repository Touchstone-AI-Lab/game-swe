"""Score the unchanged enum observations, each made inside a launched real game."""
import argparse
import json
from pathlib import Path
import re

# Every case must prove that its fixture ran on the render thread of the CardCrawlGame
# that ModTheSpire launched, with a live GL context and the main menu up.
ENGINE = 'gl=true,listener=com.megacrit.cardcrawl.core.CardCrawlGame,self=true,menu=true'


def score(text, nonce, entrypoint_exit):
    expected = json.loads(Path(__file__).with_name('cases.json').read_text())
    try:
        observed = json.loads(text)
    except (ValueError, TypeError):
        observed = {}
    if not isinstance(observed, dict):
        observed = {}
    rows = observed.get('cases', [])
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        rows = []
    valid = bool(nonce) and entrypoint_exit == 0 and observed.get('nonce') == nonce
    valid = valid and observed.get('fixture_build_exit') == 0
    valid = valid and [r.get('id') for r in rows] == [r['id'] for r in expected]
    valid = valid and all(type(r.get('exit')) is int and r['exit'] == 0 and r.get('timeout') is False for r in rows)
    found = {}
    for row in rows:
        ident = re.escape(str(row.get('id', '')))
        lines = row.get('observation', '')
        lines = lines.splitlines() if isinstance(lines, str) else []
        engine = [s for s in lines if s.startswith('ENUM_ENGINE ')]
        records = [s for s in lines if s.startswith('ENUM_OBSERVATION ')]
        engine_ok = len(engine) == 1 and re.fullmatch(
            r'ENUM_ENGINE ' + re.escape(nonce) + r'\|id=' + ident + ',' + re.escape(ENGINE) + r',frames=[0-9]+',
            engine[0]) is not None
        match = re.fullmatch(
            r'ENUM_OBSERVATION ' + re.escape(nonce) + r'\|id=' + ident + r',loaded=(true|false),value=(.*),error=(.*)',
            records[0]) if len(records) == 1 else None
        if not engine_ok or match is None or len(lines) != 2:
            valid = False
        else:
            found[row['id']] = match.groups()
    cases = []
    for case in expected:
        required = ('true' if case['loaded'] else 'false', case['value'], 'none')
        cases.append({'id': case['id'], 'group': case['group'], 'passed': bool(valid and found.get(case['id']) == required)})
    passed = sum(r['passed'] for r in cases)
    return {'complete': bool(valid), 'expected': len(expected), 'passed': passed, 'failed': len(expected) - passed,
            'reward': int(valid and passed == len(expected)), 'entrypoint_exit': entrypoint_exit, 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['observations', 'nonce-file', 'exit-file', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = score(args.observations.read_text() if args.observations.exists() else '',
                   args.nonce_file.read_text().strip(), int(args.exit_file.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    (args.output / 'reward.txt').write_text(str(result['reward']) + '\n')
    (args.output / 'summary.txt').write_text(
        f"Complete={result['complete']} Passed={result['passed']} Failed={result['failed']} Expected={result['expected']}\n")
