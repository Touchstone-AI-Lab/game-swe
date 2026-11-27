from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from rhenium_study.attempts import schedule
from rhenium_study.e1config import StudyConfig

CONFIG = """
study_id = "pilot"
snapshot_commit = "0123456789abcdef0123456789abcdef01234567"
scaffold = "mini-swe-agent 2.4.5 via rhenium ModelRunner"
repeats = 3
schedule_seed = 7
agent_image = "rhenium-study-agent:1"
tasks = ["dst/core/world-rule-ballot", "stardew-valley/core/stardew-cp-release-regressions"]
e2_selection_rule = "all target-satisfied and contract-violated attempts"
e2_max_cases = 10

[budget]
step_limit = 100
command_timeout_seconds = 180
wall_time_limit_seconds = 5400
request_timeout_seconds = 1800

[[models]]
id = "model-a"
litellm_model = "openai/model-a"
base_url = "https://a.example/v1"
api_key_file = "/nonexistent/a.txt"

[[models]]
id = "model-b"
litellm_model = "openai/org/model-b"
base_url = "https://b.example/v1"
api_key_file = "/nonexistent/b.txt"
extra_body = { reasoning_effort = "high" }
prompt_caching = true
max_output_tokens = 64000
thinking = { type = "enabled", budget_tokens = 16000 }

[[models]]
id = "model-c"
litellm_model = "anthropic/model-c"
base_url = "https://c.example"
api_key_file = "/nonexistent/c.txt"
thinking = { type = "adaptive", display = "summarized" }
output_config = { effort = "high" }
omit_params = ["temperature"]
"""


def test_schedule_is_complete_deterministic_and_bound_to_the_config_bytes(tmp_path: Path) -> None:
    path = tmp_path / "study.toml"
    path.write_text(CONFIG, encoding="utf-8")
    config, digest = StudyConfig.load(path)
    first, second = schedule(config), schedule(config)
    assert first == second and len(first) == 3 * 2 * 3
    assert len({item.attempt_id for item in first}) == 18
    assert [item.order for item in first] == list(range(1, 19))
    assert {(item.model, item.task, item.repeat) for item in first} == {
        (model.id, task, repeat) for model in config.models for task in config.tasks for repeat in (1, 2, 3)
    }
    assert config.models[1].endpoint_host == "b.example"
    assert [model.prompt_caching for model in config.models] == [False, True, False]
    assert [model.max_output_tokens for model in config.models] == [None, 64000, None]
    assert [model.thinking for model in config.models] == [
        None,
        {"type": "enabled", "budget_tokens": 16000},
        {"type": "adaptive", "display": "summarized"},
    ]
    assert [model.output_config for model in config.models] == [None, None, {"effort": "high"}]
    assert [model.omit_params for model in config.models] == [(), (), ("temperature",)]
    path.write_text(CONFIG.replace("schedule_seed = 7", "schedule_seed = 8"), encoding="utf-8")
    other, other_digest = StudyConfig.load(path)
    assert other_digest != digest and schedule(other) != first


@pytest.mark.parametrize(
    "old,new",
    [
        ('id = "model-b"', 'id = "model-a"'),
        ("repeats = 3", "repeats = 0"),
        ('snapshot_commit = "0123456789abcdef0123456789abcdef01234567"', 'snapshot_commit = "main"'),
        ("step_limit = 100", "step_limit = 100\nsurprise = 1"),
        ("max_output_tokens = 64000", "max_output_tokens = 0"),
        ('omit_params = ["temperature"]', 'omit_params = ["messages"]'),
        ('omit_params = ["temperature"]', 'omit_params = ["temperature", "temperature"]'),
        ('omit_params = ["temperature"]', 'omit_params = "temperature"'),
        ('output_config = { effort = "high" }', 'output_config = "high"'),
    ],
)
def test_invalid_or_unfrozen_conditions_are_rejected(tmp_path: Path, old: str, new: str) -> None:
    path = tmp_path / "study.toml"
    path.write_text(CONFIG.replace(old, new), encoding="utf-8")
    with pytest.raises(ValidationError):
        StudyConfig.load(path)
