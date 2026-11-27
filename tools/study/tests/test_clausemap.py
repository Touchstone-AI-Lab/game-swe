from __future__ import annotations

import pytest
from pydantic import ValidationError
from rhenium_study.clausemap import ClauseMap


def _map(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "task": "game/pack/task",
        "task_version": "1.0.0",
        "exam": "exams/task.md",
        "cases": [
            {"id": "case:repaired", "role": "target", "clauses": ["#1"]},
            {"id": "case:still works", "role": "preserved", "clauses": ["preserve"]},
            {"id": "case:loaded", "role": "runtime-sentinel"},
        ],
        "clauses": [
            {"id": "#1", "anchor": "Reports [#1]", "status": "asserted"},
            {"id": "preserve", "anchor": "Task, last sentence", "status": "asserted"},
            {"id": "#2", "anchor": "Reports [#2]", "status": "unasserted"},
        ],
        "excluded_clauses": ["#2"],
    }
    return {**base, **overrides}


def test_roles_select_cases_and_unasserted_clauses_are_explicit() -> None:
    clause_map = ClauseMap.model_validate(_map())
    assert clause_map.case_ids("target") == ["case:repaired"]
    assert clause_map.case_ids("preserved") == ["case:still works"]
    assert len(clause_map.case_ids()) == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"cases": [{"id": "case:x", "role": "target", "clauses": []}]},
        {"cases": [{"id": "case:x", "role": "target", "clauses": ["#missing"]}]},
        {"cases": [{"id": "case:x", "role": "target", "clauses": ["#1"]}] * 2},
        {
            "clauses": [
                {"id": "#1", "anchor": "a", "status": "unasserted"},
                {"id": "preserve", "anchor": "b", "status": "asserted"},
                {"id": "#2", "anchor": "c", "status": "unasserted"},
            ]
        },
        {
            "clauses": [
                {"id": "#1", "anchor": "a", "status": "asserted"},
                {"id": "preserve", "anchor": "b", "status": "asserted"},
                {"id": "#2", "anchor": "c", "status": "weak"},
            ]
        },
        {"excluded_clauses": ["#unknown"]},
    ],
)
def test_inconsistent_maps_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClauseMap.model_validate(_map(**overrides))


def test_audited_selection_leaves_out_over_constrained_cases() -> None:
    document = _map()
    cases = list(document["cases"])  # type: ignore[call-overload]
    cases[0] = {**cases[0], "over_constrained": True}
    clause_map = ClauseMap.model_validate({**document, "cases": cases})
    assert clause_map.case_ids("target") == ["case:repaired"]
    assert clause_map.case_ids("target", audited=True) == []
    assert clause_map.case_ids(audited=True) == ["case:still works", "case:loaded"]
