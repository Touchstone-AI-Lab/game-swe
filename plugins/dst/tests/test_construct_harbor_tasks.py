"""Harbor-package tests of the construct pack, restored from the pre-repair plugin."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "dst-construct"
REPAIR_RUNTIME = ROOT / "benchmarks" / "dst" / "private" / "runtime" / "dst-harbor-runtime"
HARBOR = PACK / "private" / "harbor"
RUNTIME = PACK / "private" / "runtime" / "dst-harbor-runtime"
BASE_TAG = "gcb-dst-dedicated-verifier:24700372"

TASKS = (
    "camp-supply-ledger",
    "container-transfer-transaction",
    "rescue-dispatch-queue",
    "world-rule-ballot",
    "combat-target-arbiter",
    "trade-escrow-exchange",
    "status-effect-stack",
    "waystone-route-network",
    "loot-roll-arbiter",
    "fuel-ration-allocator",
)


def _exam_body(task_id: str) -> str:
    source = (PACK / "exams" / f"{task_id}.md").read_text(encoding="utf-8")
    return source.split("---", 2)[2].lstrip() if source.startswith("---\n") else source


def test_harbor_task_set_matches_the_catalog() -> None:
    catalog = json.loads((PACK / "fixed-v1.json").read_text(encoding="utf-8"))
    assert {task["id"] for task in catalog["tasks"]} == set(TASKS)
    assert {path.parent.name for path in HARBOR.glob("*/task.toml")} == set(TASKS)


@pytest.mark.parametrize("task_id", TASKS)
def test_dst_harbor_task_has_schema_1_4_layout(task_id: str) -> None:
    task_root = HARBOR / task_id
    required = {
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/mod/README.md",
        "tests/Dockerfile",
        "tests/test.sh",
        "tests/verify.py",
        "tests/pack/fixed-v1.json",
        "solution/solve.sh",
        "solution/reference/modinfo.lua",
        "solution/reference/modmain.lua",
    }
    assert required <= {
        path.relative_to(task_root).as_posix() for path in task_root.rglob("*") if path.is_file()
    }

    config = tomllib.loads((task_root / "task.toml").read_text(encoding="utf-8"))
    assert config["schema_version"] == "1.4"
    assert config["task"]["name"] == f"gamecodebench/dst-{task_id}"
    assert config["artifacts"] == ["/app/mod"]
    assert config["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["metadata"]["content_reference"] == f"benchmarks/dst-construct/exams/{task_id}.md"
    assert config["metadata"]["content_reference_pack"] == "rhenium-dst-v2"
    assert config["metadata"]["verification_profile"] == "rhenium-dst-full"
    assert config["metadata"]["real_server_validation"].endswith("build 24700372")

    starter = task_root / "environment" / "mod"
    assert not list(starter.rglob("*.lua")), "the agent environment leaked a solution"

    agent_dockerfile = (task_root / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=agent:agent mod /app/mod" in agent_dockerfile
    assert "/tests" not in agent_dockerfile
    assert "/solution" not in agent_dockerfile
    assert "gcb-dst-dedicated-verifier" not in agent_dockerfile

    verifier_dockerfile = (task_root / "tests" / "Dockerfile").read_text(encoding="utf-8")
    first_from = next(
        line.split()[1] for line in verifier_dockerfile.splitlines() if line.upper().startswith("FROM ")
    )
    assert first_from == BASE_TAG
    assert "COPY ." not in verifier_dockerfile


@pytest.mark.parametrize("task_id", TASKS)
def test_materialized_harbor_assets_match_the_canonical_pack(task_id: str) -> None:
    task_root = HARBOR / task_id
    assert (task_root / "instruction.md").read_text(encoding="utf-8") == (
        "# Harbor workspace\n\n"
        "Complete this task in `/app/mod`; every required file must be written under that directory.\n\n"
        + _exam_body(task_id)
    )
    catalog = json.loads((PACK / "fixed-v1.json").read_text(encoding="utf-8"))
    canonical = next(task for task in catalog["tasks"] if task["id"] == task_id)
    single = json.loads((task_root / "tests" / "pack" / "fixed-v1.json").read_text(encoding="utf-8"))
    assert single == {**catalog, "tasks": [canonical]}
    for key in ("hidden_test", "server_test"):
        assert (task_root / "tests" / "pack" / canonical[key]).read_bytes() == (
            PACK / canonical[key]
        ).read_bytes()
    pack_files = {
        path.relative_to(task_root / "tests" / "pack").as_posix()
        for path in (task_root / "tests" / "pack").rglob("*")
        if path.is_file()
    }
    assert pack_files == {"fixed-v1.json", canonical["hidden_test"], canonical["server_test"]}

    harness = HARBOR / "harness"
    for generated, source in (
        ("environment/Dockerfile", "Dockerfile"),
        ("environment/mod/README.md", "starter-README.md"),
        ("tests/Dockerfile", "verifier.Dockerfile"),
        ("tests/test.sh", "test.sh"),
        ("tests/verify.py", "verify.py"),
        ("solution/solve.sh", "solve.sh"),
    ):
        assert (task_root / generated).read_bytes() == (harness / source).read_bytes()


def test_verifier_runtime_vendors_the_evaluator_byte_for_byte() -> None:
    sources = {
        "rhenium/__init__.py": ROOT / "src" / "rhenium" / "__init__.py",
        **{
            f"rhenium/core/{path.name}": path
            for path in (ROOT / "src" / "rhenium" / "core").glob("*.py")
        },
        **{
            f"rhenium_dst/{path.relative_to(ROOT / 'plugins/dst/src/rhenium_dst').as_posix()}": path
            for path in (ROOT / "plugins" / "dst" / "src" / "rhenium_dst").rglob("*.py")
        },
    }
    vendored = {
        path.relative_to(RUNTIME / "evaluator").as_posix(): path
        for path in (RUNTIME / "evaluator").rglob("*")
        if path.is_file()
    }
    assert set(vendored) == set(sources)
    for relative, source in sources.items():
        assert vendored[relative].read_bytes() == source.read_bytes(), relative


def test_runtime_pins_base_image_build_and_python_dependencies() -> None:
    dockerfile = (RUNTIME / "Dockerfile").read_text(encoding="utf-8")
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    first_from = next(
        line.split()[1] for line in dockerfile.splitlines() if line.upper().startswith("FROM ")
    )
    assert first_from == runtimes["runtimes"][0]["source"]["image"]
    assert "@sha256:" in first_from
    assert "ARG DST_BUILD_ID=24700372" in dockerfile
    assert "sha256sum -c" in dockerfile
    assert set(runtimes["task_bindings"]) == set(TASKS)
    requirements = [
        line
        for line in (RUNTIME / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert requirements and all("==" in requirement for requirement in requirements)


def test_construct_runtime_is_bound_to_its_own_key() -> None:
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    repair = json.loads((ROOT / "benchmarks" / "dst" / "runtimes.json").read_text(encoding="utf-8"))
    assert [runtime["id"] for runtime in runtimes["runtimes"]] == ["dst-dedicated-24700372-construct"]
    assert {tuple(value) for value in runtimes["task_bindings"].values()} == {
        ("dst-dedicated-24700372-construct",)
    }
    assert runtimes["runtimes"][0]["source"] == repair["runtimes"][0]["source"]
    manifest = json.loads((PACK / "benchmark.json").read_text(encoding="utf-8"))
    assert manifest["pack_id"] == "construct" and manifest["catalog"] == "fixed-v1.json"


def test_both_packs_share_one_byte_identical_runtime_build_context() -> None:
    # The base image embeds the evaluator; identical contexts keep the pinned
    # server layers shared and both packs on the same evaluator code.
    def tree(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    assert tree(RUNTIME) == tree(REPAIR_RUNTIME)
