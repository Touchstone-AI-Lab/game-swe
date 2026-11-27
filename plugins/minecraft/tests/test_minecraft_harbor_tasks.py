"""Layout and provenance checks over the real Minecraft Harbor packages."""

from __future__ import annotations

import filecmp
import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest
from pack_fixtures import HARNESS, PACK
from rhenium_minecraft.catalog import (
    HARBOR_INSTRUCTION_HEADER,
    MinecraftCatalog,
    MinecraftTask,
    task_manifest,
)
from rhenium_minecraft.container import RESULT_MARKER

CATALOG = MinecraftCatalog.load(PACK)
TASKS = [pytest.param(task, id=task.id) for task in CATALOG.tasks]
BINARY_SUFFIXES = {".class", ".jar", ".zip", ".so", ".dll", ".exe"}
WRAPPER_JARS = {"gradle/wrapper/gradle-wrapper.jar", ".mvn/wrapper/maven-wrapper.jar"}
LICENSE_MARKERS = {
    "MIT": "MIT License",
    "Apache-2.0": "Apache License",
    "BSD-2-Clause": "Redistribution and use",
    "BSD-3-Clause": "Redistribution and use",
    "ISC": "ISC License",
}


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.mark.parametrize("task", TASKS)
def test_generated_files_match_the_harness_copies(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    assert filecmp.cmp(root / "tests" / "test.sh", HARNESS / "test.sh", shallow=False)
    assert filecmp.cmp(root / "tests" / "verify.py", HARNESS / "verify.py", shallow=False)
    assert filecmp.cmp(root / "solution" / "solve.sh", HARNESS / "solve.sh", shallow=False)
    manifest = json.loads((root / "tests" / "task.json").read_text(encoding="utf-8"))
    assert manifest == task_manifest(task)
    instruction = (root / "instruction.md").read_text(encoding="utf-8")
    assert instruction.startswith(HARBOR_INSTRUCTION_HEADER)
    toml = tomllib.loads((root / "task.toml").read_text(encoding="utf-8"))
    assert toml["verifier"]["environment_mode"] == "separate"
    assert toml["metadata"]["plugin_name"] == task.plugin_name
    assert task.upstream is not None
    assert toml["metadata"]["source_repo"] == task.upstream.repository
    assert toml["metadata"]["base_commit"] == task.upstream.base_commit
    assert toml["metadata"]["expected_unit_cases"] == len(task.unit_cases)
    assert toml["metadata"]["expected_server_cases"] == len(task.server_cases)


@pytest.mark.parametrize("task", TASKS)
def test_tests_starter_mirrors_the_environment_starter(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    starter = root / "environment" / "plugin"
    mirror = root / "tests" / "starter"
    starter_files = sorted(p.relative_to(starter) for p in starter.rglob("*") if p.is_file())
    mirror_files = sorted(p.relative_to(mirror) for p in mirror.rglob("*") if p.is_file())
    assert starter_files == mirror_files
    for relative in starter_files:
        assert filecmp.cmp(starter / relative, mirror / relative, shallow=False), relative
    assert any((starter / declared).exists() for declared in task.build.frozen_paths)


@pytest.mark.parametrize("task", TASKS)
def test_solution_after_repairs_the_starter_without_touching_frozen_paths(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    starter = root / "environment" / "plugin"
    after = root / "solution" / "after"
    changed = [p for p in after.rglob("*") if p.is_file()]
    assert changed, "the reference fix must change at least one file"
    touches_existing = False
    for path in changed:
        relative = path.relative_to(after)
        assert not any(relative.as_posix().startswith(f) for f in task.build.frozen_paths), relative
        assert relative.suffix in {".java", ".yml", ".yaml", ".properties", ".json"}, relative
        starter_file = starter / relative
        if starter_file.is_file():
            touches_existing = True
            assert not filecmp.cmp(path, starter_file, shallow=False), f"{relative} is unchanged"
    assert touches_existing, "the fix must modify at least one existing starter file"


@pytest.mark.parametrize("task", TASKS)
def test_starter_has_no_binaries_symlinks_or_git_state(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    for path in (root / "environment" / "plugin").rglob("*"):
        assert not path.is_symlink(), path
        if path.is_file():
            relative = path.relative_to(root / "environment" / "plugin").as_posix()
            assert path.suffix not in BINARY_SUFFIXES or relative in WRAPPER_JARS, path
            assert ".git" not in path.parts and "build" not in path.parts and "target" not in path.parts


@pytest.mark.parametrize("task", TASKS)
def test_license_matches_declared_spdx(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    assert task.upstream is not None
    text = (root / "environment" / "plugin" / task.upstream.license_file).read_text(
        encoding="utf-8", errors="replace"
    )
    assert LICENSE_MARKERS[task.upstream.license_spdx] in text
    upstream = task.upstream
    assert upstream is not None
    assert re.fullmatch(r"[0-9a-f]{40}", upstream.base_commit)
    assert upstream.fix_commit is not None
    assert re.fullmatch(r"[0-9a-f]{40}", upstream.fix_commit)


@pytest.mark.parametrize("task", TASKS)
def test_suite_registers_exactly_the_frozen_server_cases(task: MinecraftTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    names: list[str] = []
    for source in sorted((root / "tests" / "suite").glob("*.java")):
        names.extend(
            re.findall(r'@GcbCase\(\s*(?:value\s*=\s*)?"([^"]+)"', source.read_text(encoding="utf-8"))
        )
    assert sorted(names) == sorted(task.server_cases)


def test_tasks_do_not_share_fixes_or_suites() -> None:
    fixes = {}
    suites = {}
    for task in CATALOG.tasks:
        root = PACK / "private" / "harbor" / task.id
        fixes[task.id] = _tree_digest(root / "solution" / "after")
        suites[task.id] = _tree_digest(root / "tests" / "suite")
    assert len(set(fixes.values())) == len(fixes)
    assert len(set(suites.values())) == len(suites)


def test_result_marker_is_shared_by_harness_verifier_and_plugin() -> None:
    verify = (HARNESS / "verify.py").read_text(encoding="utf-8")
    assert f'MARKER = "{RESULT_MARKER}"' in verify
    java = list((HARNESS / "gcb-harness" / "src").rglob("*.java"))
    assert any(RESULT_MARKER.strip() in path.read_text(encoding="utf-8") for path in java)


def test_agent_image_frees_uid_1000_before_creating_the_agent_user() -> None:
    # The pinned Temurin base is Ubuntu 26.04, whose stock `ubuntu` user already
    # holds UID 1000; `useradd --uid 1000 agent` fails unless that user is removed.
    template = (HARNESS / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
    rendered = [
        (PACK / "private" / "harbor" / task.id / "environment" / "Dockerfile").read_text(encoding="utf-8")
        for task in CATALOG.tasks
    ]
    for text in (template, *rendered):
        assert text.index("userdel --remove ubuntu") < text.index("useradd --create-home --uid 1000 agent")
