"""Layout, provenance and hygiene checks over the real Mindustry Harbor packages."""

from __future__ import annotations

import csv
import filecmp
import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest
from mindustry_fixtures import HARNESS, PACK
from rhenium_mindustry.catalog import (
    HARBOR_INSTRUCTION_HEADER,
    MindustryCatalog,
    MindustryTask,
    task_manifest,
)
from rhenium_mindustry.container import RESULT_MARKER

CATALOG = MindustryCatalog.load(PACK)
TASKS = [pytest.param(task, id=task.id) for task in CATALOG.tasks]
BINARY_SUFFIXES = {".class", ".jar", ".zip", ".so", ".dll", ".exe"}


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_pack_has_at_least_five_repair_tasks() -> None:
    assert len(CATALOG.tasks) >= 5
    assert all(task.task_kind == "repository-debugging" for task in CATALOG.tasks)
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    assert runtimes["task_bindings"] == {task.id: ["mindustry-159.7"] for task in CATALOG.tasks}


@pytest.mark.parametrize("task", TASKS)
def test_generated_files_match_the_harness_copies(task: MindustryTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    assert filecmp.cmp(root / "tests" / "test.sh", HARNESS / "test.sh", shallow=False)
    assert filecmp.cmp(root / "tests" / "verify.py", HARNESS / "verify.py", shallow=False)
    assert filecmp.cmp(root / "tests" / "Dockerfile", HARNESS / "verifier.Dockerfile.tmpl", shallow=False)
    assert filecmp.cmp(root / "environment" / "Dockerfile", HARNESS / "agent.Dockerfile.tmpl", shallow=False)
    assert filecmp.cmp(root / "solution" / "solve.sh", HARNESS / "solve.sh", shallow=False)
    manifest = json.loads((root / "tests" / "task.json").read_text(encoding="utf-8"))
    assert manifest == task_manifest(task)
    assert (root / "instruction.md").read_text(encoding="utf-8").startswith(HARBOR_INSTRUCTION_HEADER)
    toml = tomllib.loads((root / "task.toml").read_text(encoding="utf-8"))
    assert toml["verifier"]["environment_mode"] == "separate"
    assert toml["verifier"]["network_mode"] == "no-network"
    assert toml["metadata"]["source_repo"] == task.upstream.repository
    assert toml["metadata"]["base_commit"] == task.upstream.base_commit
    assert toml["metadata"]["fix_commits"] == list(task.upstream.fix_commits)
    assert toml["metadata"]["expected_server_cases"] == len(task.server_cases)


@pytest.mark.parametrize("task", TASKS)
def test_suite_registers_exactly_the_frozen_cases(task: MindustryTask) -> None:
    suite = PACK / "private" / "harbor" / task.id / "tests" / "suite"
    names: list[str] = []
    for source in sorted(suite.rglob("*.java")):
        names.extend(re.findall(r'suite\.test\(\s*"([^"]+)"', source.read_text(encoding="utf-8")))
    assert names == list(task.server_cases)


@pytest.mark.parametrize("task", TASKS)
def test_case_contracts_follow_the_suite_order_and_roles(task: MindustryTask) -> None:
    path = PACK / "private" / "harbor" / task.id / "validation" / "case-contracts.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["case"] for row in rows] == list(task.server_cases)
    roles = [row["role"] for row in rows]
    assert roles[0] == "sentinel" and roles.count("sentinel") == 1
    assert roles.count("target") >= 2 and roles.count("preserved") >= 2


@pytest.mark.parametrize("task", TASKS)
def test_reference_only_touches_existing_game_sources(task: MindustryTask) -> None:
    root = PACK / "private" / "harbor" / task.id
    starter = root / "environment" / "mindustry"
    after = root / "solution" / "after"
    changed = sorted(p for p in after.rglob("*") if p.is_file())
    assert changed, "the reference fix must change at least one file"
    for path in changed:
        relative = path.relative_to(after)
        assert relative.suffix == ".java", relative
        assert relative.parts[:2] in {("core", "src"), ("server", "src")}, relative
        assert "comp" not in relative.parts, "generated entity components cannot be repaired"
        starter_file = starter / relative
        assert starter_file.is_file(), relative
        assert not filecmp.cmp(path, starter_file, shallow=False), f"{relative} is unchanged"


@pytest.mark.parametrize("task", TASKS)
def test_starter_is_a_clean_game_source_tree(task: MindustryTask) -> None:
    starter = PACK / "private" / "harbor" / task.id / "environment" / "mindustry"
    top = {path.name for path in starter.iterdir()}
    assert top == {"LICENSE", "README.md", "annotations", "core", "server"}
    for path in starter.rglob("*"):
        assert not path.is_symlink(), path
        if path.is_file():
            assert path.suffix not in BINARY_SUFFIXES, path
            assert ".git" not in path.parts and "build" not in path.parts, path
    license_text = (starter / task.upstream.license_file).read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text and "Version 3" in license_text


def test_starters_differ_from_each_other_only_in_repaired_files() -> None:
    first, *others = CATALOG.tasks
    base = PACK / "private" / "harbor" / first.id / "environment" / "mindustry"
    base_files = sorted(p.relative_to(base) for p in base.rglob("*") if p.is_file())
    for task in others:
        starter = PACK / "private" / "harbor" / task.id / "environment" / "mindustry"
        files = sorted(p.relative_to(starter) for p in starter.rglob("*") if p.is_file())
        assert files == base_files, task.id
        touched = {
            p.relative_to(PACK / "private" / "harbor" / t.id / "solution" / "after")
            for t in (first, task)
            for p in (PACK / "private" / "harbor" / t.id / "solution" / "after").rglob("*")
            if p.is_file()
        }
        for relative in base_files:
            if relative not in touched:
                assert filecmp.cmp(base / relative, starter / relative, shallow=False), (task.id, relative)


@pytest.mark.parametrize("task", TASKS)
def test_exam_hides_fix_provenance(task: MindustryTask) -> None:
    exam = (PACK / "exams" / f"{task.id}.md").read_text(encoding="utf-8")
    assert "mindustry/" in exam
    for commit in task.upstream.fix_commits:
        assert commit[:7] not in exam
    assert not re.search(r"#\d{3,}", exam), "issue or PR numbers must not appear in the exam"
    assert "github.com/Anuken/Mindustry/" not in exam.replace("github.com/Anuken/Mindustry>", "")


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
    java = list((HARNESS / "rhenium-harness" / "src").rglob("*.java"))
    assert any(f'"{RESULT_MARKER}"' in path.read_text(encoding="utf-8") for path in java)


def test_agent_image_frees_uid_1000_before_creating_the_agent_user() -> None:
    template = (HARNESS / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
    assert template.index("userdel --remove ubuntu") < template.index(
        "useradd --create-home --uid 1000 agent"
    )
