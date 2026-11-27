from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

from minisweagent.models.test_models import DeterministicModel, make_output
from pytest import MonkeyPatch

from rhenium.model_runner import ModelRunner


def _factory(
    outputs: list[dict[str, Any]],
    captured: list[dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], DeterministicModel]:
    def create(config: dict[str, Any]) -> DeterministicModel:
        if captured is not None:
            captured.append(config)
        return DeterministicModel(outputs=outputs, cost_per_call=0)

    return create


def test_model_runner_uses_mini_swe_agent_to_create_submission(tmp_path: Path) -> None:
    (tmp_path / "TASK.md").write_text("Build a server mod from scratch.\n", encoding="utf-8")
    command = """cat > modinfo.lua <<'EOF'
name = "Fresh Build"
api_version = 10
dst_compatible = true
EOF
cat > modmain.lua <<'EOF'
AddPrefabPostInit("world", function(inst) end)
EOF"""
    outputs = [
        make_output("Creating the required files.", [{"command": command}], cost=0),
        make_output(
            "The implementation is complete.",
            [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}],
            cost=0,
        ),
    ]
    captured: list[dict[str, Any]] = []
    result = ModelRunner(model_factory=_factory(outputs, captured)).build(
        tmp_path,
        "Implement the complete server mod.",
        base_url="http://model.test/v1",
        model="test-model",
        api_key="test-key",
        max_steps=4,
    )

    assert (tmp_path / "modinfo.lua").is_file()
    assert (tmp_path / "modmain.lua").is_file()
    assert result["framework"]["name"] == "mini-swe-agent"
    assert result["framework"]["version"] == version("mini-swe-agent")
    assert result["framework"]["trajectoryFormat"] == "mini-swe-agent-1.1"
    assert result["exitStatus"] == "Submitted"
    assert result["steps"] == 2
    assert result["changedFiles"] == ["modinfo.lua", "modmain.lua"]
    assert captured[0]["model_name"] == "openai/test-model"
    assert captured[0]["model_kwargs"]["api_base"] == "http://model.test/v1"
    assert captured[0]["model_kwargs"]["api_key"] == "test-key"
    # A stalled provider connection must fail its step, not hang the whole attempt.
    assert captured[0]["model_kwargs"]["timeout"] == 600
    assert "test-key" not in str(result["trajectory"])


def test_workspace_environment_does_not_inherit_host_credentials(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "host-secret-must-not-leak")
    outputs = [
        make_output("Inspecting environment.", [{"command": "env > environment.txt"}], cost=0),
        make_output("Done.", [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}], cost=0),
    ]

    ModelRunner(model_factory=_factory(outputs)).build(
        tmp_path,
        "Create a file.",
        base_url="http://model.test/v1",
        model="test-model",
        api_key="model-secret",
        max_steps=3,
        agent_environment={
            "GAME_SDK_ROOT": "/opt/example-game-sdk",
            "GAME_LICENSE_TOKEN": "plugin-secret-must-not-leak",
            "RHENIUM_BENCHMARK_PATH": "/private/evaluator-assets",
        },
    )

    environment = (tmp_path / "environment.txt").read_text(encoding="utf-8")
    assert "GAME_SDK_ROOT=/opt/example-game-sdk" in environment
    assert "OPENAI_API_KEY" not in environment
    assert "host-secret-must-not-leak" not in environment
    assert "model-secret" not in environment
    assert "plugin-secret-must-not-leak" not in environment
    assert "/private/evaluator-assets" not in environment


def test_model_runner_honors_configured_steps_above_fifty(tmp_path: Path) -> None:
    outputs = [make_output("Continuing.", [{"command": "true"}], cost=0) for _ in range(50)]
    outputs.append(
        make_output("Done.", [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}], cost=0)
    )

    result = ModelRunner(model_factory=_factory(outputs)).build(
        tmp_path,
        "Implement the complete project.",
        base_url="http://model.test/v1",
        model="test-model",
        api_key="",
        max_steps=51,
    )

    assert result["steps"] == 51
    assert result["exitStatus"] == "Submitted"


def test_step_limit_keeps_partial_workspace_and_trajectory(tmp_path: Path) -> None:
    outputs = [make_output("Starting.", [{"command": "printf partial > result.txt"}], cost=0)]

    result = ModelRunner(model_factory=_factory(outputs)).build(
        tmp_path,
        "Implement as much as possible.",
        base_url="",
        model="test-model",
        api_key="",
        max_steps=1,
    )

    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "partial"
    assert result["exitStatus"] == "LimitsExceeded"
    assert result["changedFiles"] == ["result.txt"]
    assert result["trajectory"]["info"]["exit_status"] == "LimitsExceeded"
