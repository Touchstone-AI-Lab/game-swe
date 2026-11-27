"""Compile the unchanged fixture mods, then run each one in a fresh real game.

Every case starts the licensed game through the submitted ModTheSpire with exactly that
case's fixture mod and the observer mod. The observer runs the fixture on the game's render
thread once the main menu is live. Cases share only read-only inputs, never a process,
home directory, temporary directory or mod list. A launch that times out or exits
unsuccessfully makes the result incomplete, so the remaining cases are not started.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

CASE_TIMEOUT = 150
LOG_TAIL = 20000
GAME = Path('/opt/sts/lib/desktop-1.0.jar')
BASELINE = Path('/opt/sts/lib/ModTheSpire.jar')
JRE = Path('/opt/java/openjdk/jre')

parser = argparse.ArgumentParser()
for name in ['jar', 'runtime', 'nonce-file', 'output', 'engine-log']:
    parser.add_argument('--' + name, type=Path, required=True)
args = parser.parse_args()
tests = Path(__file__).resolve().parent
cases = json.loads((tests / 'cases.json').read_text())
runtime = args.runtime
runtime.mkdir()
report = {'nonce': args.nonce_file.read_text().strip(), 'fixture_build_exit': 255, 'cases': []}
compile_log = []


def command(values):
    result = subprocess.run(values, capture_output=True, text=True)
    compile_log.append(result.stdout + result.stderr)
    if result.returncode:
        report['fixture_build_exit'] = result.returncode
        args.output.write_text(json.dumps(report, indent=2))
        (args.output.parent / 'probe-build.log').write_text('\n'.join(compile_log))
        raise RuntimeError('Immutable fixture compilation failed')


def package(source, metadata, jar):
    # Mods are compiled against the original public SDK, as in r2, so a submission that
    # breaks existing compiled mods fails a real compatibility contract.
    classes = jar.with_suffix('.classes')
    classes.mkdir()
    command(['javac', '-g', '-encoding', 'UTF-8', '-source', '8', '-target', '8',
             '-cp', str(BASELINE) + ':' + str(GAME), '-d', str(classes), str(source)])
    shutil.copyfile(metadata, classes / 'ModTheSpire.json')
    command(['jar', 'cf', str(jar), '-C', str(classes), '.'])


observer = runtime / 'enumobserver.jar'
package(tests / 'observer' / 'Observer.java', tests / 'observer' / 'ModTheSpire.json', observer)
for case in cases:
    folder = runtime / case['id']
    folder.mkdir()
    package(tests / case['id'] / 'Fixture.java', tests / case['id'] / 'ModTheSpire.json', folder / 'fixture.jar')
report['fixture_build_exit'] = 0
(args.output.parent / 'probe-build.log').write_text('\n'.join(compile_log))
runtime.chmod(0o755)
args.engine_log.write_text('')

for case in cases:
    folder = runtime / case['id']
    play = folder / 'game'
    for directory in ['mods', 'home', 'tmp']:
        (play / directory).mkdir(parents=True)
    shutil.copyfile(args.jar, play / 'ModTheSpire.jar')
    shutil.copyfile(folder / 'fixture.jar', play / 'mods' / 'enumscout.jar')
    shutil.copyfile(observer, play / 'mods' / 'enumobserver.jar')
    for path in [play, *play.rglob('*')]:
        shutil.chown(path, 'nobody', 'nogroup')
    # The read-only game JAR and JRE are shared; links are created after ownership changes.
    (play / 'desktop-1.0.jar').symlink_to(GAME)
    (play / 'jre').symlink_to(JRE)
    observation = play / 'observation.txt'
    values = ['timeout', '-k', '5s', str(CASE_TIMEOUT), 'runuser', '-u', 'nobody', '--',
              'xvfb-run', '-a', '-s', '-screen 0 1280x720x24',
              'java', '-Xmx1200m', '-Duser.home=' + str(play / 'home'), '-Djava.io.tmpdir=' + str(play / 'tmp'),
              '-Dsts.verify.nonce=' + report['nonce'], '-Dsts.verify.case=' + case['id'],
              '-Dsts.verify.output=' + str(observation),
              '-jar', 'ModTheSpire.jar', '--imgui', '--skip-launcher', '--skip-intro', '--mods', 'enumscout,enumobserver']
    log_path = folder / 'engine.log'
    started = time.monotonic()
    with log_path.open('wb') as log:
        try:
            code = subprocess.run(values, cwd=play, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=CASE_TIMEOUT + 30).returncode
        except subprocess.TimeoutExpired:
            code = 124
    text = ''
    if observation.is_file() and not observation.is_symlink():
        text = observation.read_text(encoding='utf-8', errors='replace')
    row = {'id': case['id'], 'exit': code, 'timeout': code in (124, 137), 'observation': text,
           'seconds': round(time.monotonic() - started, 1)}
    report['cases'].append(row)
    args.output.write_text(json.dumps(report, indent=2))
    tail = log_path.read_text(encoding='utf-8', errors='replace')[-LOG_TAIL:]
    with args.engine_log.open('a', encoding='utf-8') as engine:
        engine.write(f'== {case["id"]} exit={code} seconds={row["seconds"]} ==\n{tail}\n')
    if code != 0:
        # One failed launch already makes the whole result incomplete. Stop instead of
        # spending the remaining cases' game timeouts on a loader that cannot launch.
        break
print(json.dumps({'observed': len(report['cases']), 'timed_out': any(r['timeout'] for r in report['cases'])}))
