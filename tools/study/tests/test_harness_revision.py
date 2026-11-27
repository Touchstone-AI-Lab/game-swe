from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_study import attempts
from rhenium_study.attempts import Scheduled
from rhenium_study.e1config import StudyConfig
from rhenium_study.paths import StudyPaths

ROOT = Path(__file__).parents[3]


def test_a_recorded_attempt_is_not_resumed_under_another_configuration(tmp_path: Path) -> None:
    paths = StudyPaths(project_root=ROOT, data_root=tmp_path / "data")
    config = StudyConfig.model_validate(
        {
            "study_id": "resume-test",
            "snapshot_commit": "0" * 40,
            "scaffold": "test",
            "repeats": 1,
            "schedule_seed": 1,
            "agent_image": "agent:test",
            "budget": {
                "step_limit": 1,
                "command_timeout_seconds": 1,
                "wall_time_limit_seconds": 60,
                "request_timeout_seconds": 30,
            },
            "models": [
                {"id": "m", "litellm_model": "x", "base_url": "https://example.test", "api_key_file": "k"}
            ],
            "tasks": ["slay-the-spire/core/mts-load-order-regressions"],
            "e2_selection_rule": "none",
            "e2_max_cases": 1,
        }
    )
    item = Scheduled(
        attempt_id="m--a--r1",
        model="m",
        task="slay-the-spire/core/mts-load-order-regressions",
        repeat=1,
        order=1,
    )
    root = paths.data_root / "e1" / config.study_id / "attempts" / item.attempt_id
    root.mkdir(parents=True)
    (root / "attempt.json").write_text(
        json.dumps({"configDigest": "old", "outcome": "failed"}), encoding="utf-8"
    )
    assert attempts.run_attempt(paths, config, "old", item)["outcome"] == "failed"
    with pytest.raises(ValueError, match="another configuration"):
        attempts.run_attempt(paths, config, "new", item)


def test_the_harness_revision_names_a_commit() -> None:
    revision = attempts.harness_revision(StudyPaths(project_root=ROOT, data_root=ROOT.parent / "unused"))
    assert len(revision["commit"]) == 40 and isinstance(revision["dirty"], bool)
