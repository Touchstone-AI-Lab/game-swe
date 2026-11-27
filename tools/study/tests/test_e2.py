from __future__ import annotations

from pathlib import Path
from typing import Any

from rhenium_study.e1config import StudyConfig
from rhenium_study.e2 import select
from test_schedule_config import CONFIG


def _record(attempt: str, task: str, family: str, target: str, preserved: str, joint: str) -> dict[str, Any]:
    return {
        "attempt_id": attempt,
        "task": task,
        "sourceFamily": family,
        "targetOutcome": target,
        "preservedOutcome": preserved,
        "jointOutcome": joint,
    }


def _config(tmp_path: Path, cap: int) -> StudyConfig:
    path = tmp_path / "study.toml"
    path.write_text(CONFIG.replace("e2_max_cases = 10", f"e2_max_cases = {cap}"), encoding="utf-8")
    return StudyConfig.load(path)[0]


def test_selection_takes_every_target_success_contract_failure_and_pairs_a_control(tmp_path: Path) -> None:
    records = [
        _record("a1", "g/p/t1", "fam-a", "satisfied", "violated", "target-only"),
        _record("a2", "g/p/t1", "fam-a", "satisfied", "satisfied", "both"),
        _record("a3", "g/p/t2", "fam-b", "violated", "violated", "neither"),
        _record("a4", "g/p/t2", "fam-b", "satisfied", "unknown", "insufficient-observations"),
        _record("a5", "g/p/t3", "fam-c", "satisfied", "violated", "target-only"),
    ]
    selection = select(records, _config(tmp_path, 10))
    assert selection["eligible"] == selection["selected"] == ["a1", "a5"]
    assert selection["successfulControls"] == {"a1": "a2", "a5": None}


def test_selection_above_the_cap_is_deterministic_and_spreads_over_source_families(tmp_path: Path) -> None:
    records = [
        _record(
            f"a{index}",
            "g/p/t",
            "big" if index < 8 else f"small-{index}",
            "satisfied",
            "violated",
            "target-only",
        )
        for index in range(10)
    ]
    config = _config(tmp_path, 3)
    first, second = select(records, config), select(records, config)
    assert first == second and len(first["selected"]) == 3 and len(first["eligible"]) == 10
    families = {next(r["sourceFamily"] for r in records if r["attempt_id"] == a) for a in first["selected"]}
    assert len(families) == 3, "one attempt per family before any family is sampled twice"


def test_no_eligible_attempt_is_an_empty_result_not_a_substitute_sample(tmp_path: Path) -> None:
    records = [_record("a1", "g/p/t", "f", "violated", "satisfied", "contracts-only")]
    selection = select(records, _config(tmp_path, 10))
    assert selection["eligible"] == [] and selection["selected"] == []
