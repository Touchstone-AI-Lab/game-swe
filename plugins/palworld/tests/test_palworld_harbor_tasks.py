from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "palworld"
HARBOR = PACK / "private" / "harbor"

TASKS = (
    "guild-storage-ledger",
    "base-containment-mincut",
    "raid-dispatch-queue",
    "server-rule-ballot",
    "guild-draft-canonical-order",
    "outbox-receipt-recovery",
    "pal-workforce-optimal-matching",
    "raid-event-watermark",
    "guild-consistent-checkpoint",
    "world-epoch-fenced-timers",
)

FORBIDDEN_SOURCE_MARKERS = (
    "game-swe",
    "Touchstone-AI-Lab",
    "benchmarks/dst/",
    "camp-supply-ledger",
    "container-transfer-transaction",
    "rescue-dispatch-queue",
    "world-rule-ballot",
    "combat-target-arbiter",
    "Don't Starve",
    "饥荒",
)


def _load_verifier() -> ModuleType:
    harness = HARBOR / "harness"
    spec = importlib.util.spec_from_file_location("palworld_harbor_verify", harness / "verify.py")
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(harness))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(harness))
    return module


def _exam_body(task_id: str) -> str:
    source = (PACK / "exams" / f"{task_id}.md").read_text(encoding="utf-8")
    return source.split("---", 2)[2].lstrip() if source.startswith("---\n") else source


@pytest.mark.parametrize("task_id", TASKS)
def test_palworld_harbor_task_has_schema_1_4_layout(task_id: str) -> None:
    task_root = HARBOR / task_id
    required = {
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/mod/README.md",
        "tests/Dockerfile",
        "tests/test.sh",
        "solution/solve.sh",
    }
    assert required <= {
        path.relative_to(task_root).as_posix() for path in task_root.rglob("*") if path.is_file()
    }

    config = tomllib.loads((task_root / "task.toml").read_text(encoding="utf-8"))
    assert config["schema_version"] == "1.4"
    assert config["task"]["name"] == f"gamecodebench/palworld-{task_id}"
    assert config["task"]["version"] == "1.0.0"
    assert config["artifacts"] == ["/app/mod"]
    assert config["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["metadata"]["content_reference"] == f"benchmarks/palworld/exams/{task_id}.md"
    assert config["metadata"]["content_reference_pack"] == "rhenium-palworld-v1"
    assert config["metadata"]["verification_profile"].startswith("portable-lua-5.4")

    starter = task_root / "environment" / "mod"
    assert not list(starter.rglob("*.lua")), "the agent environment leaked a solution"
    assert (task_root / "solution" / "reference" / "scripts" / "main.lua").is_file()

    agent_dockerfile = (task_root / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=agent:agent mod /app/mod" in agent_dockerfile
    assert "/tests" not in agent_dockerfile
    assert "/solution" not in agent_dockerfile

    verifier_dockerfile = (task_root / "tests" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY behavior.lua lua_runner.py server.lua spec.json verify.py /tests/" in verifier_dockerfile
    assert "COPY --chmod=755 test.sh /tests/test.sh" in verifier_dockerfile
    assert "WORKDIR /app/mod" in verifier_dockerfile
    assert "COPY ." not in verifier_dockerfile


@pytest.mark.parametrize("task_id", TASKS)
def test_agent_instruction_has_no_external_benchmark_provenance(task_id: str) -> None:
    task_root = HARBOR / task_id
    instruction = (task_root / "instruction.md").read_text(encoding="utf-8")
    config_source = (task_root / "task.toml").read_text(encoding="utf-8")

    assert instruction == (
        "# Harbor workspace\n\n"
        "Complete this task in `/app/mod`; every required file must be written under that directory.\n\n"
        + _exam_body(task_id)
    )
    for marker in FORBIDDEN_SOURCE_MARKERS:
        assert marker not in instruction
        assert marker not in config_source


@pytest.mark.parametrize("task_id", TASKS)
def test_materialized_harbor_assets_match_the_canonical_pack(task_id: str) -> None:
    task_root = HARBOR / task_id
    assert (task_root / "instruction.md").read_text(encoding="utf-8").endswith(_exam_body(task_id))
    assert (task_root / "tests" / "behavior.lua").read_bytes() == (
        PACK / "hidden" / f"{task_id}.lua"
    ).read_bytes()
    assert (task_root / "tests" / "server.lua").read_bytes() == (
        PACK / "server" / f"{task_id}.lua"
    ).read_bytes()
    assert (task_root / "environment" / "Dockerfile").read_bytes() == (
        HARBOR / "harness" / "Dockerfile"
    ).read_bytes()
    assert (task_root / "tests" / "Dockerfile").read_bytes() == (
        HARBOR / "harness" / "verifier.Dockerfile"
    ).read_bytes()
    for filename in ("lua_runner.py", "verify.py", "test.sh"):
        assert (task_root / "tests" / filename).read_bytes() == (HARBOR / "harness" / filename).read_bytes()
    assert (task_root / "solution" / "solve.sh").read_bytes() == (
        HARBOR / "harness" / "solve.sh"
    ).read_bytes()

    catalog = json.loads((PACK / "fixed-v1.json").read_text(encoding="utf-8"))
    canonical = next(task for task in catalog["tasks"] if task["id"] == task_id)
    spec = json.loads((task_root / "tests" / "spec.json").read_text(encoding="utf-8"))
    assert spec == {
        "task_id": task_id,
        "required_files": canonical["required_files"],
        "minimum_lua_lines": canonical["minimum_lua_lines"],
        "integration_checks": canonical["integration_checks"],
    }


@pytest.mark.parametrize("task_id", TASKS)
def test_reference_passes_and_empty_starter_fails(task_id: str) -> None:
    verifier = _load_verifier()
    task_root = HARBOR / task_id
    arguments = (
        task_root / "tests" / "spec.json",
        task_root / "tests" / "behavior.lua",
        task_root / "tests" / "server.lua",
    )

    reference = verifier.verify(task_root / "solution" / "reference", *arguments)
    empty = verifier.verify(task_root / "environment" / "mod", *arguments)

    assert reference["status"] == "passed"
    assert reference["failed"] == 0
    assert reference["lua_runtime_version"] == "Lua 5.4"
    assert reference["real_palworld_server_ran"] is False
    assert empty["status"] == "failed"
    assert empty["failed"] > 0
    assert any(
        not case["passed"] and case["name"] == "all required mod files are present" for case in empty["cases"]
    )


def test_simulated_server_keeps_trusted_context_isolated(tmp_path: Path) -> None:
    verifier = _load_verifier()
    submission = tmp_path / "submission"
    scripts = submission / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "main.lua").write_text(
        'local helpers = require("UEHelpers")\n'
        "helpers.GetWorld = function() return nil end\n"
        'RheniumService = { string_metatable_hidden = getmetatable("") == nil }\n',
        encoding="utf-8",
    )
    suite = tmp_path / "server.lua"
    suite.write_text(
        "return function(ctx)\n"
        '  ctx:case("trusted helpers", function()\n'
        "    assert(ctx.helpers.GetWorld():IsValid())\n"
        "  end)\n"
        '  ctx:case("protected primitives", function()\n'
        "    assert(RheniumService.string_metatable_hidden)\n"
        "  end)\n"
        "end\n",
        encoding="utf-8",
    )

    result = verifier.run_mock_server(submission, suite)

    assert result["status"] == "passed"
    assert all(case["passed"] for case in result["cases"])
