from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from rhenium_study import hubs
from rhenium_study.e1config import Budget

ROOT = Path(__file__).parents[3]
RUNNER = ROOT / "tools/study/src/rhenium_study/assets/agent_runner.py"


def _runner_names(*names: str) -> dict[str, Any]:
    """Selected top-level definitions of the container runner, without running the script."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    body: list[ast.stmt] = [
        node
        for node in tree.body
        if (isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names)
        or (isinstance(node, ast.Assign) and any(getattr(t, "id", "") in names for t in node.targets))
    ]
    namespace: dict[str, Any] = {"Any": Any, "condition": {}, "get_model": lambda config: config}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(RUNNER), "exec"), namespace)
    return namespace


class _Model:
    """Returns one scripted command list per query, like mini-swe-agent's LitellmModel."""

    def __init__(self, commands: list[list[str]]) -> None:
        self.commands = commands
        self.config = "kept"

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        del messages, kwargs
        actions = [{"command": command} for command in self.commands.pop(0)]
        return {"role": "assistant", "content": "", "extra": {"actions": actions}}


def test_the_same_commands_limit_times_in_a_row_end_the_run() -> None:
    exceptions = pytest.importorskip("minisweagent.exceptions")
    names = _runner_names("RepeatedActionGuard", "REPEATED_ACTION_EXIT")
    guard = names["RepeatedActionGuard"](_Model([["ls"], ["ls"], ["ls"]]), 3)
    assert guard.config == "kept"
    assert guard.query([])["extra"]["actions"] == [{"command": "ls"}]
    guard.query([])
    with pytest.raises(exceptions.InterruptAgentFlow) as raised:
        guard.query([])
    last, exit_message = raised.value.messages
    assert last["extra"]["actions"] == [{"command": "ls"}]
    assert exit_message["role"] == "exit"
    assert exit_message["extra"]["exit_status"] == names["REPEATED_ACTION_EXIT"] == "RepeatedActionLoop"


def test_a_different_command_or_an_empty_response_breaks_the_run_of_repeats() -> None:
    pytest.importorskip("minisweagent.exceptions")
    names = _runner_names("RepeatedActionGuard", "REPEATED_ACTION_EXIT")
    script = [["make"], ["make"], ["cat log"], ["make"], ["make"], [], ["make"], ["make"]]
    guard = names["RepeatedActionGuard"](_Model(script), 3)
    for _ in script:
        guard.query([])


def test_the_runner_wraps_the_model_only_when_the_budget_sets_a_limit() -> None:
    names = _runner_names("RepeatedActionGuard", "REPEATED_ACTION_EXIT", "model_factory")
    config: dict[str, Any] = {"model_kwargs": {}}
    assert names["model_factory"](config) == {"model_kwargs": {}}
    names["condition"].update(repeated_action_limit=5)
    wrapped = names["model_factory"](config)
    assert isinstance(wrapped, names["RepeatedActionGuard"]) and wrapped._limit == 5


def test_the_budget_limit_is_optional_and_at_least_two() -> None:
    base = {
        "step_limit": 100,
        "command_timeout_seconds": 180,
        "wall_time_limit_seconds": 3600,
        "request_timeout_seconds": 1800,
    }
    assert Budget.model_validate(base).repeated_action_limit is None
    assert Budget.model_validate({**base, "repeated_action_limit": 5}).repeated_action_limit == 5
    with pytest.raises(ValidationError):
        Budget.model_validate({**base, "repeated_action_limit": 1})


def test_engine_slots_follow_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RHENIUM_STUDY_ENGINE_SLOTS", "2")
    with hubs.engine_slot(tmp_path, "game-pack") as first, hubs.engine_slot(tmp_path, "game-pack") as second:
        assert {first, second} == {0, 1}
    locks = sorted(path.name for path in tmp_path.iterdir())
    assert locks == ["engine-game-pack-0.lock", "engine-game-pack-1.lock"]
    monkeypatch.setenv("RHENIUM_STUDY_ENGINE_SLOTS", "0")
    with pytest.raises(ValueError), hubs.engine_slot(tmp_path, "game-pack"):
        pass
