"""Preserve the v1 experiment; collect observations even when load times out."""
from tasks.durable_charge.probe import REQUIRED, evaluate as original_evaluate
from scripts.audit import write


def collect(session):
    if session.runtime is not None:
        try:
            data = session.client.call('poc.load_diagnostic')
            write(session.runtime.directory / 'load-diagnostic-final.json', data)
        except Exception as error:
            write(session.runtime.directory / 'load-diagnostic-query-error.json',
                  {'error': type(error).__name__, 'message': str(error)})


def evaluate(session, checks):
    try:
        original_evaluate(session, checks)
    finally:
        collect(session)
