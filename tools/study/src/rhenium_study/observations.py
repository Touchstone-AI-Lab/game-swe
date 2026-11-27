from __future__ import annotations

import re
from typing import Any, Literal

Observation = Literal["P", "F", "U", "I"]

# Checks whose cases are reported individually; their aggregate row would
# otherwise count the same evidence twice.
_CASE_LAYER = {
    "hidden-behavior": "hidden",
    "headless-server": "server",
    "dedicated-server": "server",
    "gmod-integration": "integration",
    "lifecycle-cleanup": "lifecycle",
    "upstream-tests": "unit",
    "live-server": "server",
    "private-suite": "suite",
    "private-source-projection-verifier": "projection",
    "private-real-tmodloader-verifier": "server",
}
# An evaluator that publishes no case names reports its cases as ``check-<n>``, in the fixed
# order of the task's scenario. The clause map says which case each position is.
_POSITIONAL_CHECK = re.compile(r"check-([1-9][0-9]*)")
_ENGINE_AGGREGATES = frozenset(
    {"headless-server", "headless-game", "native-game", "real-game", "dedicated-server"}
)


def observed_cases(result: dict[str, Any]) -> dict[str, Observation]:
    """Name-level observations of one evaluator result.

    Only valid observations appear: ``P`` for a passed case and ``F`` for an
    observed failure. A case that is absent was not observed; the caller decides
    against the task's frozen case list whether it was unreached or interrupted.
    Identifiers are layer-qualified (``hidden:``, ``server:``, ``integration:``,
    ``lifecycle:``, ``projection:``, ``case:``, ``position:``) or ``check:`` for a static gate.
    """
    observed: dict[str, Observation] = {}
    runtime = result.get("runtime")
    outcomes = runtime.get("caseOutcomes") if isinstance(runtime, dict) else None
    has_outcomes = isinstance(outcomes, dict) and bool(outcomes)
    if isinstance(outcomes, dict):
        for name, passed in outcomes.items():
            if isinstance(name, str) and isinstance(passed, bool):
                observed[f"case:{name}"] = "P" if passed else "F"

    checks = result.get("checks")
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict):
            continue
        name = check.get("name")
        position = _POSITIONAL_CHECK.fullmatch(name) if isinstance(name, str) else None
        if position is not None and isinstance(check.get("passed"), bool):
            observed[f"position:{position.group(1)}"] = "P" if check["passed"] else "F"
            continue
        if not isinstance(check.get("id"), str):
            continue
        check_id, status = check["id"], check.get("status")
        details = check.get("details")
        cases = details.get("cases") if isinstance(details, dict) else None
        layer = _CASE_LAYER.get(check_id)
        if layer is not None and isinstance(cases, list):
            for case in cases:
                if (
                    isinstance(case, dict)
                    and isinstance(case.get("name"), str)
                    and isinstance(case.get("passed"), bool)
                ):
                    observed[f"{layer}:{case['name']}"] = "P" if case["passed"] else "F"
            continue
        if check_id in _ENGINE_AGGREGATES and (has_outcomes or layer is not None):
            continue
        if status == "passed":
            observed[f"check:{check_id}"] = "P"
        elif status == "failed":
            observed[f"check:{check_id}"] = "F"
    return observed


def case_table(result: dict[str, Any], expected: list[str]) -> dict[str, Observation]:
    """Observations for every frozen case; anything not validly observed is ``U``."""
    observed = observed_cases(result)
    return {case: observed.get(case, "U") for case in expected}
