from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_scope_keeps_all_remaining_pairs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    scope = importlib.import_module("native_scope_v3")
    keys = ["growth-v2", *(f"task-{n}" for n in range(9))]
    plan = scope.remaining(keys)
    assert len(plan) == 18
    assert plan == [(k, role, 1) for k in keys[1:] for role in ("gold", "base")]
    with pytest.raises(ValueError):
        scope.remaining(keys[:-1])
    with pytest.raises(ValueError):
        scope.remaining([*keys[:-1], keys[-2]])


@pytest.mark.parametrize("defect", [None, "missing", "duplicate", "wrong_role", "wrong_task"])
def test_scope_requires_exact_control_coverage(monkeypatch: pytest.MonkeyPatch, defect: str | None) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    verifier = importlib.import_module("summarize_scope_v3")
    keys = [f"task-{n}" for n in range(10)]
    flows = [{"task": k, "role": role} for k in keys for role in ("gold", "base")]
    if defect == "missing":
        flows.pop()
    elif defect == "duplicate":
        flows[-1] = flows[0].copy()
    elif defect == "wrong_role":
        flows[-1]["role"] = "alternative"
    elif defect == "wrong_task":
        flows[-1]["task"] = "unrelated"
    if defect:
        with pytest.raises(ValueError):
            verifier.validate_coverage(flows, keys)
    else:
        verifier.validate_coverage(flows, keys)
