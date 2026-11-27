from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from rhenium_dst.analyzer import ModAnalyzer
from rhenium_dst.catalog import DstCatalog

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "dst"
TASK_IDS = [
    "dst-fixed-bundle-regressions",
    "dst-fixed-module-regressions",
    "composting-together-regressions",
    "dsmmo-release-regressions",
    "glassic-api-regressions",
]


def _raw_catalog() -> dict[str, object]:
    value = json.loads((DATASET / "catalog.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_dst_catalog_contains_only_upstream_repair_tasks() -> None:
    catalog = DstCatalog.load(DATASET)

    assert catalog.id == "dst-core"
    assert catalog.game == "dst"
    assert [task.id for task in catalog.tasks] == TASK_IDS
    for task in catalog.tasks:
        assert task.task_kind == "repository-debugging"
        assert task.upstream.repository.startswith("https://github.com/")
        assert task.upstream.fix_commits
        assert task.authored_prompt.startswith("# ")
        assert "/app/mod" in task.authored_prompt
        assert task.required_files[:2] == ["mod/modinfo.lua", "mod/modmain.lua"]


def test_every_task_declares_exactly_the_cases_its_suite_defines() -> None:
    catalog = DstCatalog.load(DATASET)

    for task in catalog.tasks:
        suite = (DATASET / task.server_test).read_text(encoding="utf-8")
        declared = re.findall(r'ctx:case\("([^"]+)"', suite)
        assert list(task.server_cases) == declared, task.id
        assert sum(name.startswith("sentinel:") for name in declared) == 1, task.id


def test_hidden_suites_and_vendored_trees_parse() -> None:
    analyzer = ModAnalyzer()

    assert analyzer.analyze(DATASET / "server")["syntax_errors"] == []
    for task_id in TASK_IDS:
        task_root = DATASET / "private" / "harbor" / task_id
        for tree in (task_root / "environment" / "mod", task_root / "solution" / "after"):
            analysis = analyzer.analyze(tree)
            assert analysis["valid"], (task_id, tree, analysis["syntax_errors"])


def test_schema_rejects_extra_fields_misplaced_files_and_bad_options() -> None:
    leaked = copy.deepcopy(_raw_catalog())
    tasks = leaked["tasks"]
    assert isinstance(tasks, list) and isinstance(tasks[0], dict)
    tasks[0]["order"] = 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        DstCatalog.model_validate(leaked)

    outside = copy.deepcopy(_raw_catalog())
    outside_tasks = outside["tasks"]
    assert isinstance(outside_tasks, list) and isinstance(outside_tasks[0], dict)
    outside_tasks[0]["required_files"] = ["modinfo.lua", "modmain.lua"]
    with pytest.raises(ValidationError, match="required_files must be below mod/"):
        DstCatalog.model_validate(outside)

    quoted = copy.deepcopy(_raw_catalog())
    quoted_tasks = quoted["tasks"]
    assert isinstance(quoted_tasks, list) and isinstance(quoted_tasks[0], dict)
    quoted_tasks[0]["mod_options"] = {"SMARTUNWRAP": 'x" } os.exit() --'}
    with pytest.raises(ValidationError, match="quotes"):
        DstCatalog.model_validate(quoted)

    unhashed = copy.deepcopy(_raw_catalog())
    unhashed_tasks = unhashed["tasks"]
    assert isinstance(unhashed_tasks, list) and isinstance(unhashed_tasks[0], dict)
    upstream = unhashed_tasks[0]["upstream"]
    assert isinstance(upstream, dict)
    upstream["fix_commits"] = ["abc123"]
    with pytest.raises(ValidationError, match="full lower-case commit hashes"):
        DstCatalog.model_validate(unhashed)


def test_load_fails_closed_when_private_assets_are_missing(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(DATASET, pack, ignore=shutil.ignore_patterns("study-controls"))
    task_id = TASK_IDS[0]

    (pack / "server" / f"{task_id}.lua").unlink()
    with pytest.raises(ValueError, match="server suite is missing"):
        DstCatalog.load(pack)
    shutil.copyfile(DATASET / "server" / f"{task_id}.lua", pack / "server" / f"{task_id}.lua")

    (pack / "private" / "harbor" / task_id / "environment" / "mod" / "LICENSE").unlink()
    with pytest.raises(ValueError, match="upstream licence is missing"):
        DstCatalog.load(pack)

    shutil.rmtree(pack / "private" / "harbor" / task_id / "solution" / "after")
    with pytest.raises(ValueError, match="reference is missing"):
        DstCatalog.load(pack)


def test_verifier_pack_loads_without_public_assets() -> None:
    for task_id in TASK_IDS:
        pack = DATASET / "private" / "harbor" / task_id / "tests" / "pack"
        catalog = DstCatalog.load(pack, verifier_pack=True)
        assert [task.id for task in catalog.tasks] == [task_id]
        assert catalog.tasks[0].authored_prompt == ""
        with pytest.raises(ValueError, match="public exam is missing"):
            DstCatalog.load(pack)
