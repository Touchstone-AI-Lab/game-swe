from __future__ import annotations

import json
from pathlib import Path

from rhenium_study import mapgen
from rhenium_study.clausemap import ClauseMap
from rhenium_study.inventory import StudyTask
from rhenium_study.paths import StudyPaths


def _pack(root: Path, exam: str) -> StudyPaths:
    pack = root / "benchmarks" / "demo"
    (pack / "exams").mkdir(parents=True)
    (pack / "benchmark.json").write_text(json.dumps({"catalog": "catalog.json"}), encoding="utf-8")
    catalog = {"version": "1.0.0", "tasks": [{"id": "demo-task"}]}
    (pack / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    (pack / "exams" / "demo-task.md").write_text(exam, encoding="utf-8")
    return StudyPaths(project_root=root, data_root=root / "data")


TASK = StudyTask("game", "demo", "demo-task", "repair", "demo", "demo", "src", True)


def test_report_letters_follow_the_exam_markers_and_duplicates_are_dropped(tmp_path: Path) -> None:
    paths = _pack(tmp_path, "> **[#11]** first report\n\n> **[#12]** second report\n")
    reference = {
        "case:sentinel: the addon is loaded": "P",
        "case:A: the first thing works": "P",
        "case:A: an old path still works": "P",
        "case:B: the second thing works": "P",
        "check:submission-shape": "P",
    }
    starter = {**reference, "case:A: the first thing works": "F", "case:B: the second thing works": "F"}
    drafted = mapgen.draft(TASK, paths, starter, reference)
    roles = {case["id"]: (case["role"], case.get("clauses", [])) for case in drafted["cases"]}
    assert roles["case:sentinel: the addon is loaded"][0] == "runtime-sentinel"
    assert roles["case:A: the first thing works"] == ("target", ["[#11]"])
    assert roles["case:B: the second thing works"] == ("target", ["[#12]"])
    assert roles["case:A: an old path still works"] == ("preserved", ["preserve:[#11]"])
    ClauseMap.model_validate(drafted)


def test_layered_names_win_and_passing_gates_are_delivery(tmp_path: Path) -> None:
    paths = _pack(tmp_path, "## 1. Something is wrong\n")
    reference = {
        "case:thing_works": "P",
        "server:thing_works": "P",
        "server:old_thing_works": "P",
        "server:sentinel_plugin_enabled": "P",
        "server:plugin-enabled": "P",
        "server:pluginEnabledSentinel": "P",
        "check:offline-build": "P",
    }
    starter = {**reference, "case:thing_works": "F", "server:thing_works": "F"}
    drafted = mapgen.draft(TASK, paths, starter, reference)
    roles = {case["id"]: case["role"] for case in drafted["cases"]}
    assert "case:thing_works" not in roles
    assert roles == {
        "server:thing_works": "target",
        "server:old_thing_works": "preserved",
        "server:sentinel_plugin_enabled": "runtime-sentinel",
        "server:plugin-enabled": "runtime-sentinel",
        "server:pluginEnabledSentinel": "runtime-sentinel",
        "check:offline-build": "static",
    }
    ClauseMap.model_validate(drafted)


def test_letters_without_a_matching_marker_count_stay_separate(tmp_path: Path) -> None:
    paths = _pack(tmp_path, "> **[#11]** only one marker\n")
    reference = {"case:A: one": "P", "case:B: two": "P"}
    drafted = mapgen.draft(TASK, paths, {"case:A: one": "F", "case:B: two": "F"}, reference)
    assert {case["id"]: case["clauses"] for case in drafted["cases"]} == {
        "case:A: one": ["report-A"],
        "case:B: two": ["report-B"],
    }


def test_an_engine_check_without_cases_is_the_request_and_catalog_gates_stay_weak(tmp_path: Path) -> None:
    paths = _pack(tmp_path, "## Build a thing\n")
    catalog = {"version": "1.0.0", "tasks": [{"id": "demo-task", "integration_checks": [{"id": "hooks"}]}]}
    (tmp_path / "benchmarks" / "demo" / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    reference = {"check:submission-shape": "P", "check:private-headless-verifier": "P", "check:hooks": "P"}
    drafted = mapgen.draft(TASK, paths, {}, reference)
    cases = {case["id"]: case for case in drafted["cases"]}
    assert cases["check:private-headless-verifier"]["role"] == "target"
    assert cases["check:private-headless-verifier"]["clauses"] == ["request"]
    assert cases["check:hooks"]["clauses"] == ["integration:hooks"]
    assert {clause["id"]: clause["status"] for clause in drafted["clauses"]}["integration:hooks"] == "weak"
    ClauseMap.model_validate(drafted)
