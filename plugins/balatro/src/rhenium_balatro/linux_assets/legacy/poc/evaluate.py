"""One runner for versioned tasks, including scenarios spanning fresh processes."""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from .checks import verdict
from .runtime import Runtime, ROOT, write
from .rpc import ProtocolError, RPCError
from .tasks import TASKS, Task


class Session:
    def __init__(self, task: Task, candidate: Path | None, label: str):
        self.task, self.candidate, self.label = task, candidate, label
        self.runtimes: list[Runtime] = []
        self.cleanups: list[dict] = []
        self.runtime: Runtime | None = None
        self.client = None
        self.phase = 'prepare/start'
        self.test_started = None

    def start(self):
        self.phase = 'prepare/start'
        runtime = Runtime(self.label, candidate=self.candidate, task_mods=self.task.mods,
                          task_files=self.task.files())
        self.runtime = runtime
        self.runtimes.append(runtime)
        self.client = runtime.start()
        if len(self.runtimes) > 1:
            if runtime.metadata['fingerprints'] != self.runtimes[0].metadata['fingerprints']:
                raise RuntimeError('Inputs changed between task processes')
        self.phase = 'test'
        self.test_started = time.monotonic()
        return self.client

    def close(self):
        if self.runtime is not None:
            if self.test_started is not None:
                self.runtime.timings['test_seconds'] = time.monotonic() - self.test_started
            cleanup = self.runtime.close()
            self.cleanups.append(cleanup)
            self.runtime = None
            self.test_started = None
            if not cleanup['normal_exit'] or not cleanup.get('protected_unchanged'):
                raise RuntimeError('Owned process did not exit cleanly or protected content changed')

    def restart(self):
        self.phase = 'exit'
        self.close()
        return self.start()


def run(task_key: str, candidate: Path | None, label: str) -> dict:
    task = TASKS[task_key]
    scenario = task.scenario()
    session = Session(task, candidate, label)
    result = {'task': task_key, 'candidate_label': label, 'checks': [], 'complete': False,
              'variant': label, 'passed': False, 'classification': 'not_executed'}
    started = time.monotonic()
    finished = False
    try:
        client = session.start()
        scenario.evaluate(session if task.session_api else client, result['checks'])
        finished = True
        result.update(verdict(result['checks'], scenario.REQUIRED, finished))
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        result['failure_phase'] = session.phase
        result['classification'] = ('environment_failure' if session.phase != 'test' else
                                    'test_gap' if isinstance(error, (ProtocolError, AssertionError, KeyError, ValueError))
                                    else 'incomplete_execution')
    finally:
        try:
            session.close()
        except Exception as error:
            result.update(complete=False, passed=False, classification='environment_failure',
                          cleanup_error=f'{type(error).__name__}: {error}')
        result['not_executed'] = [key for key in scenario.REQUIRED if key not in {c['id'] for c in result['checks']}]
        result['processes'] = [{'run_id': r.run_id, 'fingerprints': getattr(r, 'metadata', {}).get('fingerprints'),
                                'timings': r.timings, 'cleanup': cleanup}
                               for r, cleanup in zip(session.runtimes, session.cleanups)]
        result['elapsed_seconds'] = time.monotonic() - started
        result['exit_status'] = 0 if result['passed'] else 1 if result['complete'] else 2
        if session.runtimes:
            result['run_id'] = session.runtimes[0].run_id
            write(session.runtimes[0].directory / 'evaluation-v2.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True, choices=TASKS)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    if not args.task.startswith('probe-') and args.candidate is None:
        parser.error('A candidate is required for evaluation')
    result = run(args.task, args.candidate, args.label)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(result['exit_status'])


if __name__ == '__main__': main()
