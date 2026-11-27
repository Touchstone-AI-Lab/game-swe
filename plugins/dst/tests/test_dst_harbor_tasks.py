from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "dst"
HARBOR = PACK / "private" / "harbor"
RUNTIME = PACK / "private" / "runtime" / "dst-harbor-runtime"
BASE_TAG = "gcb-dst-dedicated-verifier:24700372"

TASKS = (
    "dst-fixed-bundle-regressions",
    "dst-fixed-module-regressions",
    "composting-together-regressions",
    "dsmmo-release-regressions",
    "glassic-api-regressions",
)


def _materialize() -> ModuleType:
    path = HARBOR / "scripts" / "materialize.py"
    spec = importlib.util.spec_from_file_location("dst_materialize", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve annotations through sys.modules while the class is built.
    sys.modules[spec.name] = module
    # The pack is read-only input; never leave a __pycache__ inside it.
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _catalog() -> dict[str, object]:
    value = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_harbor_task_set_matches_the_catalog() -> None:
    catalog = _catalog()
    tasks = catalog["tasks"]
    assert isinstance(tasks, list)
    assert {task["id"] for task in tasks} == set(TASKS)
    assert {path.parent.name for path in HARBOR.glob("*/task.toml")} == set(TASKS)
    assert set(_materialize().TASKS) == set(TASKS)


@pytest.mark.parametrize("task_id", TASKS)
def test_dst_harbor_task_has_the_repair_layout(task_id: str) -> None:
    task_root = HARBOR / task_id
    required = {
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/mod/modinfo.lua",
        "environment/mod/modmain.lua",
        "environment/mod/LICENSE",
        "solution/after/modinfo.lua",
        "solution/after/modmain.lua",
        "solution/after/LICENSE",
        "solution/gold.patch",
        "solution/solve.sh",
        "tests/Dockerfile",
        "tests/test.sh",
        "tests/verify.py",
        "tests/pack/catalog.json",
    }
    present = {path.relative_to(task_root).as_posix() for path in task_root.rglob("*") if path.is_file()}
    assert required <= present
    assert not any(path.is_symlink() for path in task_root.rglob("*"))

    config = tomllib.loads((task_root / "task.toml").read_text(encoding="utf-8"))
    catalog_task = next(task for task in _catalog()["tasks"] if task["id"] == task_id)  # type: ignore[attr-defined]
    assert config["schema_version"] == "1.4"
    assert config["task"]["name"] == f"gamecodebench/dst-{task_id}"
    assert config["artifacts"] == ["/app/mod"]
    assert config["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"
    metadata = config["metadata"]
    assert metadata["task_kind"] == "repository-debugging"
    assert metadata["content_reference"] == f"benchmarks/dst/exams/{task_id}.md"
    assert metadata["verification_profile"] == "rhenium-dst-full"
    assert metadata["real_server_validation"].endswith("build 24700372")
    assert metadata["source_repo"] == catalog_task["upstream"]["repository"]
    assert metadata["base_commit"] == catalog_task["upstream"]["base_commit"]
    assert metadata["reverted_fix_commits"] == catalog_task["upstream"]["fix_commits"]
    assert metadata["expected_server_cases"] == len(catalog_task["server_cases"])

    agent_dockerfile = (task_root / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=agent:agent mod /app/mod" in agent_dockerfile
    assert "/tests" not in agent_dockerfile and "/solution" not in agent_dockerfile
    assert "gcb-dst-dedicated-verifier" not in agent_dockerfile

    verifier_dockerfile = (task_root / "tests" / "Dockerfile").read_text(encoding="utf-8")
    first_from = next(
        line.split()[1] for line in verifier_dockerfile.splitlines() if line.upper().startswith("FROM ")
    )
    assert first_from == BASE_TAG
    assert "COPY ." not in verifier_dockerfile


@pytest.mark.parametrize("task_id", TASKS)
def test_starter_is_the_reference_with_fixes_reverted_and_leaks_nothing(task_id: str) -> None:
    task_root = HARBOR / task_id
    starter = task_root / "environment" / "mod"
    reference = task_root / "solution" / "after"
    starter_files = {path.relative_to(starter).as_posix() for path in starter.rglob("*") if path.is_file()}
    reference_files = {
        path.relative_to(reference).as_posix() for path in reference.rglob("*") if path.is_file()
    }
    assert starter_files == reference_files
    changed = [
        relative
        for relative in sorted(starter_files)
        if (starter / relative).read_bytes() != (reference / relative).read_bytes()
    ]
    assert changed and all(relative.endswith(".lua") for relative in changed)
    assert (starter / "LICENSE").read_bytes() == (reference / "LICENSE").read_bytes()
    forbidden = (task_id, "dst/core", "rhenium_server_test", "@@RHENIUM")
    for path in starter.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert not any(value in text for value in forbidden), path


@pytest.mark.parametrize("task_id", TASKS)
def test_materialized_harbor_assets_match_the_canonical_pack(task_id: str) -> None:
    materialize = _materialize()
    task_root = HARBOR / task_id
    assert (task_root / "instruction.md").read_text(encoding="utf-8") == materialize.instruction(task_id)
    catalog = _catalog()
    tasks = catalog["tasks"]
    assert isinstance(tasks, list)
    canonical = next(task for task in tasks if task["id"] == task_id)
    single = json.loads((task_root / "tests" / "pack" / "catalog.json").read_text(encoding="utf-8"))
    assert single == {**catalog, "tasks": [canonical]}
    suite = canonical["server_test"]
    assert (task_root / "tests" / "pack" / suite).read_bytes() == (PACK / suite).read_bytes()
    pack_files = {
        path.relative_to(task_root / "tests" / "pack").as_posix()
        for path in (task_root / "tests" / "pack").rglob("*")
        if path.is_file()
    }
    assert pack_files == {"catalog.json", suite}

    harness = HARBOR / "harness"
    for generated, source in (
        ("environment/Dockerfile", "Dockerfile"),
        ("tests/Dockerfile", "verifier.Dockerfile"),
        ("tests/test.sh", "test.sh"),
        ("tests/verify.py", "verify.py"),
        ("solution/solve.sh", "solve.sh"),
    ):
        assert (task_root / generated).read_bytes() == (harness / source).read_bytes()
    assert (task_root / "solution" / "gold.patch").read_text(encoding="utf-8") == materialize.gold_patch(
        task_root / "environment" / "mod", task_root / "solution" / "after"
    )


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


def test_gold_patch_generation_is_deterministic_and_rejects_binary_drift(tmp_path: Path) -> None:
    materialize = _materialize()
    before = tmp_path / "before"
    after = tmp_path / "after"
    for root in (before, after):
        (root / "scripts").mkdir(parents=True)
    (before / "scripts" / "a.lua").write_text("return 1\n", encoding="utf-8")
    (after / "scripts" / "a.lua").write_text("return 2", encoding="utf-8")
    patch = materialize.gold_patch(before, after)
    assert patch.startswith("diff --git a/mod/scripts/a.lua b/mod/scripts/a.lua\n")
    assert "-return 1\n+return 2\n\\ No newline at end of file\n" in patch
    assert materialize.gold_patch(before, after) == patch

    (before / "icon.tex").write_bytes(b"\x00\xff")
    (after / "icon.tex").write_bytes(b"\x00\xfe")
    with pytest.raises(ValueError, match="binary files differ"):
        materialize.gold_patch(before, after)
