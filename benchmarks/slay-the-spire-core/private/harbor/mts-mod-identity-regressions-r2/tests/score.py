"""Score the unchanged private JUnit suite, run inside the launched real game."""
import argparse
import json
from pathlib import Path
import re

EXPECTED = json.loads(Path(__file__).with_name('expectations.json').read_text())['cases']
# The suite must have run on the render thread of the CardCrawlGame that ModTheSpire
# launched, with a live GL context and the main menu up.
ENGINE = r'gl=true,listener=com\.megacrit\.cardcrawl\.core\.CardCrawlGame,self=true,menu=true,frames=[0-9]+'


def score(text, nonce, exit_code):
    valid = bool(nonce) and exit_code == 0
    engine = done = 0
    statuses = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        tag, _, rest = line.partition(' ')
        if not rest.startswith(nonce + '|'):
            valid = False
            continue
        payload = rest[len(nonce) + 1:]
        if tag == 'SUITE_ENGINE':
            engine += 1
            valid = valid and index == 0 and re.fullmatch(ENGINE, payload) is not None
        elif tag == 'SUITE_CASE':
            match = re.fullmatch(r'id=([A-Za-z0-9_.$]+),status=(SUCCESSFUL|FAILED|ABORTED|SKIPPED)', payload)
            if match is None or match.group(1) in statuses:
                valid = False
            else:
                statuses[match.group(1)] = match.group(2)
        elif tag == 'SUITE_DONE':
            done += 1
            valid = valid and index == len(lines) - 1 and payload == f'tests={len(statuses)}'
        else:
            # A failed container, a launcher error or anything unexpected leaves cases unobserved.
            valid = False
    # Surefire's run counted every case once and none skipped; aborted cases are skipped there.
    complete = bool(valid and engine == 1 and done == 1 and set(statuses) == set(EXPECTED)
                    and all(status in {'SUCCESSFUL', 'FAILED'} for status in statuses.values()))
    cases = [{'id': name, 'passed': complete and statuses.get(name) == 'SUCCESSFUL'} for name in EXPECTED]
    passed = sum(case['passed'] for case in cases)
    return {'complete': complete, 'passed': passed, 'failed': len(cases) - passed, 'expected': len(cases),
            'reward': int(complete and passed == len(cases)), 'entrypoint_exit': exit_code, 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['observations', 'nonce-file', 'exit-file', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    observed = args.observations.read_text() if args.observations.exists() else ''
    result = score(observed, args.nonce_file.read_text().strip(), int(args.exit_file.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    (args.output / 'reward.txt').write_text(str(result['reward']) + '\n')
    (args.output / 'summary.txt').write_text(
        f"Complete={result['complete']} Passed={result['passed']} Failed={result['failed']} Expected={result['expected']}\n")
