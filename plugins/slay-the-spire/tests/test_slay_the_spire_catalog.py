from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from rhenium_slay_the_spire.catalog import (
    SlayTheSpireCatalog,
    SlayTheSpireTask,
    expected_assertion_count,
)
from spire_fixtures import catalog_task, sample_pack_fixture, write_pack  # noqa: F401


def test_sample_pack_loads_with_its_verifier_assertion_count(sample_pack: Path) -> None:
    catalog = SlayTheSpireCatalog.load(sample_pack)
    (task,) = catalog.tasks
    assert task.task_kind == "debugging" and task.source_mod == "ModTheSpire"
    assert task.starter_name == "modthespire"
    assert task.container_destination == "/app/modthespire"
    # The pass criterion is read from the authored verifier, never restated here.
    assert task.expected_assertions == 4
    assert expected_assertion_count(sample_pack, task) == 4
    assert "Repair every reported problem" in task.authored_prompt


def test_catalog_rejects_an_unknown_identity(tmp_path: Path) -> None:
    pack = write_pack(tmp_path / "other", [catalog_task()], catalog_id="slay-the-spire-v9")
    with pytest.raises(ValueError, match="catalog id"):
        SlayTheSpireCatalog.load(pack)


@pytest.mark.parametrize(
    ("removed", "message"),
    [
        ("private/harbor/sample-regressions/environment/modthespire", "starter"),
        ("private/harbor/sample-regressions/environment/Dockerfile", "Dockerfile"),
        ("private/harbor/sample-regressions/tests/test.sh", "verifier"),
        ("private/harbor/sample-regressions/solution/after", "reference"),
        ("private/harbor/sample-regressions/solution/solve.sh", "oracle script"),
        ("exams/sample-regressions.md", "exam"),
    ],
)
def test_every_required_task_artifact_must_exist(sample_pack: Path, removed: str, message: str) -> None:
    import shutil

    target = sample_pack / removed
    shutil.rmtree(target) if target.is_dir() else target.unlink()
    with pytest.raises(ValueError, match=message):
        SlayTheSpireCatalog.load(sample_pack)


def test_missing_required_file_is_rejected(sample_pack: Path) -> None:
    (sample_pack / "private/harbor/sample-regressions/environment/modthespire/pom.xml").unlink()
    with pytest.raises(ValueError, match="required file"):
        SlayTheSpireCatalog.load(sample_pack)


def test_verifier_without_a_single_assertion_count_is_rejected(sample_pack: Path) -> None:
    verifier = sample_pack / "private/harbor/sample-regressions/tests/test.sh"
    verifier.write_text("#!/bin/bash\nmvn -B -o clean test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="assertion count"):
        SlayTheSpireCatalog.load(sample_pack)
    verifier.write_text("#!/bin/bash\nEXPECTED=4\nEXPECTED=5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="assertion count"):
        SlayTheSpireCatalog.load(sample_pack)


def test_public_exam_must_match_the_harbor_instruction(sample_pack: Path) -> None:
    (sample_pack / "exams/sample-regressions.md").write_text("# Different\n", encoding="utf-8")
    with pytest.raises(ValueError, match="drifted from the Harbor instruction"):
        SlayTheSpireCatalog.load(sample_pack)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda task: task.update(task_kind="construction"), "task_kind"),
        (lambda task: task.update(source_mod=""), "source_mod"),
        (lambda task: task.update(source_commit="not a ref!"), "source_commit"),
        (lambda task: task.update(required_files=["../escape"]), "required_files"),
    ],
)
def test_task_model_rules(mutation: Callable[[dict[str, Any]], object], message: str) -> None:
    task = catalog_task()
    mutation(task)
    with pytest.raises(ValidationError, match=message):
        SlayTheSpireTask.model_validate(task)


def test_real_pack_binds_its_container_tasks_and_lists_the_native_ones() -> None:
    from spire_fixtures import PACK

    catalog = SlayTheSpireCatalog.load(PACK)
    assert catalog.id == "slay-the-spire-core" and catalog.game == "slay-the-spire"
    container = catalog.container_tasks
    assert [task.expected_assertions for task in container] == []
    assert all(task.difficulty == "hard" for task in catalog.tasks)
    native = [task for task in catalog.tasks if task.native_runtime]
    assert len(native) == 9 and all(task.starter_name == "project" for task in native)
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    container_runtime, native_runtime = runtimes["runtimes"]
    assert container_runtime["provider"] == "container"
    assert "@sha256:" in container_runtime["source"]["image"]
    assert native_runtime["provider"] == "steam" and native_runtime["restricted"] is True
    bindings = runtimes["task_bindings"]
    assert {task for task, ids in bindings.items() if ids == [container_runtime["id"]]} == set()
    assert {task for task, ids in bindings.items() if ids == [native_runtime["id"]]} == {
        task.id for task in native if task.game_backed
    }

    unavailable = {task.id for task in catalog.tasks if not task.game_backed}
    assert len(unavailable) == 0
    assert all(task not in bindings for task in unavailable)
    assert len([task for task in native if task.game_backed]) == 9


def test_enum_r3_replaces_the_retired_loader_only_enum_probe() -> None:
    from rhenium_slay_the_spire.catalog import GAME_BACKED_TASKS
    from spire_fixtures import PACK

    catalog = SlayTheSpireCatalog.load(PACK)
    tasks = {task.id: task for task in catalog.tasks}
    assert "mts-enum-identity-r2" not in tasks and "mts-enum-identity-r2" not in GAME_BACKED_TASKS
    enum = tasks["mts-enum-identity-r3"]
    assert enum.native_runtime and enum.game_backed and enum.starter_name == "project"
    assert enum.required_files == ["project/pom.xml"] and enum.source_mod == "ModTheSpire"
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    assert set(runtimes["task_bindings"]) == GAME_BACKED_TASKS
