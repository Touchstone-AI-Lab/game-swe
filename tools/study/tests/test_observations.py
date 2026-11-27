from __future__ import annotations

from rhenium_study.observations import case_table, observed_cases


def test_case_outcomes_and_static_checks_are_separate_layers() -> None:
    result = {
        "checks": [
            {"id": "submission-shape", "status": "passed"},
            {"id": "headless-server", "status": "failed"},
        ],
        "runtime": {"caseOutcomes": {"sentinel: loaded": True, "A: repaired": False}},
    }
    assert observed_cases(result) == {
        "case:sentinel: loaded": "P",
        "case:A: repaired": "F",
        "check:submission-shape": "P",
    }


def test_layered_case_details_replace_their_aggregate_check() -> None:
    result = {
        "checks": [
            {"id": "required-files", "status": "passed"},
            {
                "id": "hidden-behavior",
                "status": "failed",
                "details": {
                    "cases": [
                        {"name": "first", "passed": True},
                        {"name": "second", "passed": False},
                    ]
                },
            },
            {"id": "headless-server", "status": "unavailable", "details": {"cases": []}},
        ],
        "runtime": {"status": "unavailable"},
    }
    assert observed_cases(result) == {
        "check:required-files": "P",
        "hidden:first": "P",
        "hidden:second": "F",
    }


def test_anything_not_validly_observed_is_unobserved_never_failed() -> None:
    result = {"checks": [{"id": "lua-syntax", "status": "skipped"}], "runtime": {"caseOutcomes": {}}}
    table = case_table(result, ["check:lua-syntax", "case:never reached", "hidden:absent"])
    assert table == {"check:lua-syntax": "U", "case:never reached": "U", "hidden:absent": "U"}
    assert case_table({}, ["case:x"]) == {"case:x": "U"}


def test_private_suite_cases_are_their_own_layer() -> None:
    result = {
        "checks": [
            {"id": "submission-shape", "status": "passed"},
            {
                "id": "private-suite",
                "status": "failed",
                "details": {
                    "cases": [{"name": "gcb.T.a", "passed": True}, {"name": "gcb.T.b", "passed": False}]
                },
            },
        ],
    }
    assert observed_cases(result) == {
        "check:submission-shape": "P",
        "suite:gcb.T.a": "P",
        "suite:gcb.T.b": "F",
    }


def test_terraria_projection_and_engine_cases_are_separate_layers() -> None:
    result = {
        "checks": [
            {"id": "submission-shape", "status": "passed"},
            {
                "id": "private-source-projection-verifier",
                "status": "failed",
                "details": {"cases": [{"name": "Io.RoundTrip", "passed": False}]},
            },
            {
                "id": "private-real-tmodloader-verifier",
                "status": "passed",
                "details": {"cases": [{"name": "Io.RoundTrip", "passed": True}]},
            },
        ],
    }
    assert observed_cases(result) == {
        "check:submission-shape": "P",
        "projection:Io.RoundTrip": "F",
        "server:Io.RoundTrip": "P",
    }


def test_positional_checks_are_observed_by_position() -> None:
    result = {
        "complete": True,
        "checks": [{"name": "check-1", "passed": True}, {"name": "check-2", "passed": False}],
    }
    assert observed_cases(result) == {"position:1": "P", "position:2": "F"}
    assert case_table(result, ["position:1", "position:2", "position:3"]) == {
        "position:1": "P",
        "position:2": "F",
        "position:3": "U",
    }


def test_an_incomplete_positional_result_observes_nothing() -> None:
    result = {
        "complete": False,
        "checks": [{"name": "evaluation", "passed": False, "detail": "cleanup_failure"}],
    }
    assert observed_cases(result) == {}
