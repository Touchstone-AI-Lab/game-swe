"""Task-neutral completeness and strict observation checks."""
from __future__ import annotations
import math


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite observation')
    if isinstance(value, dict):
        for child in value.values(): finite(child)
    if isinstance(value, (tuple, list)):
        for child in value: finite(child)


def check(checks, case, observed, expected):
    finite(observed); finite(expected)
    checks.append({'id': case, 'observed': observed, 'expected': expected, 'passed': observed == expected})


def verdict(checks: list[dict], required: tuple[str, ...], finished: bool) -> dict:
    ids = [c.get('id') for c in checks]
    valid = all(type(c.get('passed')) is bool and 'observed' in c and 'expected' in c for c in checks)
    finite(checks)
    complete = finished and valid and len(ids) == len(required) and set(ids) == set(required)
    passed = complete and all(c['passed'] and c['observed'] == c['expected'] for c in checks)
    return {'complete': complete, 'passed': passed,
            'classification': 'pass' if passed else 'behavior_mismatch' if complete else 'incomplete_execution',
            'not_executed': [case for case in required if case not in ids]}
