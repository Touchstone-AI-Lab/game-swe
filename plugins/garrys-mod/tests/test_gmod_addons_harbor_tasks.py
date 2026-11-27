from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "gmod"
HARBOR = PACK / "private" / "harbor"
RUNTIME = PACK / "private" / "runtime" / "gmod-harbor-runtime"
BASE_TAG = "gcb-gmod-addons-verifier:23150012"
PLUGIN_SOURCE = ROOT / "plugins" / "garrys-mod" / "src" / "rhenium_garrys_mod"

TASKS = (
    "prop-ownership-quota-registry",
    "staged-prop-alignment",
    "persistent-loadout-profiles",
    "hot-object-round-controller",
    "contraption-blueprint-duplicator",
)


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _exam_body(relative: str) -> str:
    source = (PACK / relative).read_text(encoding="utf-8")
    return source.split("---", 2)[2].lstrip() if source.startswith("---\n") else source


def _catalog_task(task_id: str) -> tuple[dict[str, object], dict[str, object]]:
    catalog = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    return catalog, next(task for task in catalog["tasks"] if task["id"] == task_id)


def test_harbor_task_set_matches_the_catalog() -> None:
    catalog = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    assert {task["id"] for task in catalog["tasks"]} == set(TASKS)
    assert {path.parent.name for path in HARBOR.glob("*/task.toml")} == set(TASKS)


@pytest.mark.parametrize("task_id", TASKS)
def test_gmod_harbor_task_has_schema_1_4_layout(task_id: str) -> None:
    task_root = HARBOR / task_id
    catalog, task = _catalog_task(task_id)
    present = set(_files(task_root))
    assert {
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/addon/TASK.md",
        "tests/Dockerfile",
        "tests/test.sh",
        "tests/verify.py",
        "tests/pack/catalog.json",
        "solution/solve.sh",
        "solution/reference/addon.json",
    } <= present

    config = tomllib.loads((task_root / "task.toml").read_text(encoding="utf-8"))
    assert config["schema_version"] == "1.4"
    assert config["task"]["name"] == f"gamecodebench/gmod-{task_id}"
    assert config["artifacts"] == ["/app/addon"]
    assert config["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["metadata"]["difficulty"] == task["difficulty"]
    assert config["metadata"]["content_reference"] == f"benchmarks/gmod/exams/{task_id}.md"
    assert config["metadata"]["content_reference_task_version"] == task["task_version"]
    assert config["metadata"]["real_server_validation"].endswith(
        f"build {catalog['runtime']['linux_build_id']}"  # type: ignore[index]
    )
    server_runtime = task["server_runtime"]
    assert isinstance(server_runtime, dict)
    assert config["verifier"]["timeout_sec"] >= server_runtime["timeout_seconds"] * len(
        server_runtime["phases"]
    )

    starter = _files(task_root / "environment" / "addon")
    assert set(starter) == {"TASK.md"}, "the agent environment leaked task assets"

    agent_dockerfile = (task_root / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=agent:agent addon /app/addon" in agent_dockerfile
    assert "/tests" not in agent_dockerfile
    assert "/solution" not in agent_dockerfile
    assert "gcb-gmod-addons-verifier" not in agent_dockerfile

    verifier_dockerfile = (task_root / "tests" / "Dockerfile").read_text(encoding="utf-8")
    first_from = next(
        line.split()[1] for line in verifier_dockerfile.splitlines() if line.upper().startswith("FROM ")
    )
    assert first_from == BASE_TAG
    assert "COPY ." not in verifier_dockerfile


@pytest.mark.parametrize("task_id", TASKS)
def test_materialized_harbor_assets_match_the_canonical_pack(task_id: str) -> None:
    task_root = HARBOR / task_id
    catalog, task = _catalog_task(task_id)
    public_exam = task["public_exam"]
    source = task["source"]
    assert isinstance(public_exam, dict) and isinstance(source, dict)
    assert (task_root / "instruction.md").read_text(encoding="utf-8") == (
        "# Harbor workspace\n\n"
        "Complete this task in `/app/addon`; every required file must be written under that directory.\n\n"
        + _exam_body(str(public_exam["path"]))
    )

    pack = task_root / "tests" / "pack"
    expected_pack = {
        "catalog.json": (
            json.dumps({**catalog, "tasks": [task]}, ensure_ascii=False, indent=2) + "\n"
        ).encode(),
        str(public_exam["path"]): (PACK / str(public_exam["path"])).read_bytes(),
        str(source["path"]): (PACK / str(source["path"])).read_bytes(),
        **{
            f"private/tasks/{task_id}/{relative}": content
            for relative, content in _files(PACK / "private" / "tasks" / task_id).items()
        },
    }
    assert _files(pack) == expected_pack

    references = sorted(
        path for path in (PACK / "private" / "tasks" / task_id / "references").iterdir() if path.is_dir()
    )
    assert _files(task_root / "solution" / "reference") == _files(references[0])

    harness = HARBOR / "harness"
    for generated, harness_name in (
        ("environment/Dockerfile", "Dockerfile"),
        ("environment/addon/TASK.md", "starter-TASK.md"),
        ("tests/Dockerfile", "verifier.Dockerfile"),
        ("tests/test.sh", "test.sh"),
        ("tests/verify.py", "verify.py"),
        ("solution/solve.sh", "solve.sh"),
    ):
        assert (task_root / generated).read_bytes() == (harness / harness_name).read_bytes()


@pytest.mark.parametrize("task_id", TASKS)
def test_single_task_verifier_pack_passes_the_unmodified_catalog_loader(task_id: str) -> None:
    from rhenium_garrys_mod.addons.catalog import GmodCatalog

    catalog = GmodCatalog.load(HARBOR / task_id / "tests" / "pack", "catalog.json")
    assert [task.id for task in catalog.tasks] == [task_id]
    assert catalog.contract_traceability_required is True


def test_verifier_runtime_vendors_the_evaluator_byte_for_byte() -> None:
    suffixes = {".py", ".lua", ".json"}
    sources = {
        "rhenium/__init__.py": ROOT / "src" / "rhenium" / "__init__.py",
        **{
            f"rhenium/core/{path.relative_to(ROOT / 'src/rhenium/core').as_posix()}": path
            for path in (ROOT / "src" / "rhenium" / "core").rglob("*")
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts
        },
        **{
            f"rhenium_garrys_mod/{path.relative_to(PLUGIN_SOURCE).as_posix()}": path
            for path in PLUGIN_SOURCE.rglob("*")
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts
        },
    }
    vendored = _files(RUNTIME / "evaluator")
    assert set(vendored) == set(sources)
    for relative, source in sources.items():
        assert vendored[relative] == source.read_bytes(), relative


def test_runtime_image_is_pinned_and_never_acquires_the_server() -> None:
    dockerfile = (RUNTIME / "Dockerfile").read_text(encoding="utf-8")
    catalog = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    first_from = next(
        line.split()[1] for line in dockerfile.splitlines() if line.upper().startswith("FROM ")
    )
    assert "@sha256:" in first_from
    assert f"ARG GMOD_BUILD_ID={catalog['runtime']['linux_build_id']}" in dockerfile
    assert "COPY --from=server / /opt/gmod/server" in dockerfile
    for forbidden in ("steamcmd", "app_update", "+login"):
        assert forbidden not in dockerfile.lower()
        assert forbidden not in (RUNTIME / "build-image.sh").read_text(encoding="utf-8").lower()
    requirements = [
        line
        for line in (RUNTIME / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert requirements and all("==" in requirement for requirement in requirements)


@pytest.mark.parametrize("scenario", ["relative", "missing-manifest", "wrong-build", "windows-only"])
def test_build_script_refuses_anything_but_the_pinned_linux_install(tmp_path: Path, scenario: str) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    server = tmp_path / "server"
    (server / "steamapps").mkdir(parents=True)
    if scenario != "missing-manifest":
        build = "1" if scenario == "wrong-build" else "23150012"
        (server / "steamapps" / "appmanifest_4020.acf").write_text(f'"buildid"\t\t"{build}"\n')
    if scenario != "windows-only":
        binary = server / "srcds_linux"
        binary.touch()
        binary.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text("#!/bin/sh\necho docker-must-not-run >&2\nexit 97\n")
    docker.chmod(0o755)
    argument = "server" if scenario == "relative" else str(server)
    result = subprocess.run(
        [bash, str(RUNTIME / "build-image.sh"), argument],
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        capture_output=True, text=True, check=False, cwd=tmp_path,
    )
    assert result.returncode == (2 if scenario == "relative" else 1)
    assert "docker-must-not-run" not in result.stderr
